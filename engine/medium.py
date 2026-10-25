"""Art direction in one medium: every generated image on a page drawn by the same hand, in the brand's colours.

`imagery.medium` may name one of the media below instead of describing one in words. A named medium is a tested local
recipe in two halves:

  * prompt words for Z-Image Turbo (what the picture is made of, its inks named in words), added where `imagery:` is
    added to every prompt (engine/imagery.py), and
  * a deterministic post-process over the generated still (numpy + OpenCV, CPU, seconds), which is what makes a page
    read as one hand: risograph is separated into two inks, its tints screened by grain and one drum misregistered;
    toile and engraving are printed in one ink on paper; halftone is a real dot screen; gouache is flattened into
    matte shapes; watercolour pools on its paper; ink is brush work with washes in the accent.

The inks come from the theme (`theme.from` brand tokens included): a toile is printed in the brand's accent, a
risograph in accent and accent2, an engraving in the text colour. `imagery.inks` / `imagery.paper` override them.

Hero composition: an image with `calm:` (set by the engine on a left-aligned hero in a named medium) asks the model
for quiet space on that side, measures how busy that side came out, and mirrors or regenerates (next seeds) until the
headline has room; the calmest try wins when none passes, and the build says so.

Results are cached under .build/_generated/med_<digest>.png, keyed by the raw still, recipe, palette and side.
"""
from __future__ import annotations

import colorsys
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .spec import MEDIUM_NAMES, medium_name

# bump when a recipe's prompt or post-process changes, so cached results are redone
VERSION = 1


@dataclass(frozen=True)
class Recipe:
    name: str
    prompt: str          # {inks} and {paper} are replaced by colour words
    grain: float         # default paper/ink texture, 0-1
    roles: tuple         # which palette roles the medium prints with (see palette())


RECIPES: dict[str, Recipe] = {r.name: r for r in (
    Recipe("risograph",
           "Risograph print illustration, two-colour riso print in {inks}, flat overlapping shapes of solid ink, coarse "
           "grain, simple graphic forms, the picture fills the whole canvas to every edge, no border, no frame, no text",
           0.6, ("accent", "accent2")),
    Recipe("toile",
           "Toile de Jouy illustration, single-colour copperplate engraving printed in {inks} on {paper} cotton, fine "
           "line hatching, delicate pastoral scene, monochrome, the picture fills the whole canvas to every edge, "
           "no border, no frame, no text",
           0.35, ("accent",)),
    Recipe("engraving",
           "Antique copper engraving, intaglio etching, fine crosshatching and parallel line shading, {inks} ink on "
           "{paper} paper, monochrome, nineteenth-century book plate, the picture fills the whole canvas to every edge, "
           "no border, no frame, no text",
           0.35, ("dark",)),
    Recipe("gouache",
           "Gouache painting, opaque matte paint, flat colour shapes, visible brush strokes, soft painterly edges, on "
           "textured paper, mid-century illustration, palette of {inks} and {paper}, full-bleed, no border, no text",
           0.45, ("dark", "accent", "accent2")),
    Recipe("watercolour",
           "Watercolour and ink illustration, loose transparent washes, wet-in-wet blooms, fine pen outlines, white "
           "paper showing through, hand-painted, washes of {inks}, full-bleed, no border, no text",
           0.5, ("dark", "accent", "accent2")),
    Recipe("halftone",
           "Bold graphic poster illustration, strong light and shadow, high contrast, simple shapes, two colours, "
           "{inks} on {paper}, vintage print, the picture fills the whole canvas to every edge, no border, no text",
           0.25, ("dark", "accent")),
    Recipe("ink",
           "Brush and ink drawing, bold sumi ink line work and solid fills, dry brush texture, ink washes in {inks}, "
           "on {paper} paper, minimal, full-bleed, no border, no seal, no signature, no text",
           0.3, ("dark", "accent")),
)}
NAMES = tuple(RECIPES)
assert NAMES == MEDIUM_NAMES, "engine/spec.py MEDIUM_NAMES and the recipes here name the same media"


def recipe(name: Optional[str]) -> Optional[Recipe]:
    """The recipe a medium names (case and the aliases in engine/spec.py forgiven), or None for a medium in words."""
    key = medium_name(name)
    return RECIPES[key] if key else None


# ---------------------------------------------------------------- colour

def rgb(c) -> tuple[int, int, int]:
    """#hex, rgb(...) or a CSS colour name as 0-255 RGB."""
    if isinstance(c, (tuple, list)):
        return tuple(int(v) for v in c[:3])
    from PIL import ImageColor
    return ImageColor.getrgb(str(c).strip())[:3]


def hexc(c) -> str:
    return "#" + "".join(f"{int(round(v)):02x}" for v in rgb(c))


def _lum(c) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _hls(c):
    r, g, b = (v / 255 for v in rgb(c))
    return colorsys.rgb_to_hls(r, g, b)


def _from_hls(h, l, s) -> tuple[int, int, int]:
    return tuple(round(v * 255) for v in colorsys.hls_to_rgb(h % 1, min(1, max(0, l)), min(1, max(0, s))))


def _hue_gap(a, b) -> float:
    """Distance between two hues in degrees (0-180); greys count as far from everything."""
    ha, _, sa = _hls(a)
    hb, _, sb = _hls(b)
    if sa < 0.15 or sb < 0.15:
        return 180.0
    d = abs(ha - hb) * 360
    return min(d, 360 - d)


PAPER = (243, 236, 223)          # warm off-white, when the theme's own background is not a paper
# Riso inks a second ink is chosen from when the brand has no accent2 far enough from its accent
RISO_INKS = {"fluorescent pink": (255, 72, 176), "yellow": (255, 232, 0), "orange": (255, 108, 47),
             "teal": (0, 131, 138), "blue": (0, 120, 191), "red": (255, 102, 94), "green": (0, 169, 92),
             "federal blue": (61, 85, 136)}


def _ink_on(c, paper, least: float) -> tuple[int, int, int]:
    """`c`, darkened just enough to stand `least` contrast against `paper` (a pale ink would vanish); on a dark paper a
    light ink is lightened instead (a dark one is left alone: it is not the medium's main ink there)."""
    h, l, s = _hls(c)
    col = rgb(c)
    up = _lum(col) > _lum(paper)
    while contrast(col, paper) < least and (0.05 < l < 0.95):
        l += 0.03 if up else -0.03
        col = _from_hls(h, l, s)
    return col


def palette(name: str, colors: dict, inks: Optional[list] = None, paper: Optional[str] = None) -> dict:
    """{'paper': rgb, 'inks': [rgb, ...]} the medium prints with, from the theme's resolved colours.

    Roles: accent and accent2 are the brand's colours; dark is the darker of the text and the background (the text on
    a light page, the background on a dark one). `inks` entries may be #hex or role names (accent, accent2, ink, bg,
    bg2, dark)."""
    r = recipe(name)
    if r is None:
        raise ValueError(f"{name!r} is not a named medium ({', '.join(NAMES)})")
    c = {k: rgb(v) for k, v in colors.items() if isinstance(v, str) and v.strip()}
    bg, ink = c.get("bg", (250, 250, 248)), c.get("ink", (20, 20, 24))
    light, dark = (bg, ink) if _lum(bg) >= _lum(ink) else (ink, bg)
    roles = {**c, "dark": dark, "light": light}

    def role(v):
        return roles[v] if isinstance(v, str) and v in roles else rgb(v)
    if paper:
        pap = role(paper)
    else:
        pap = light if _lum(light) > 0.72 else PAPER
    if inks:
        out = [role(v) for v in inks]
    else:
        accent = roles.get("accent", (40, 80, 200))
        out = []
        for want in r.roles:
            if want == "accent2":
                a2 = roles.get("accent2")
                if a2 is None or _hue_gap(a2, accent) < 40 or contrast(a2, pap) < 1.25:
                    # the riso ink farthest in hue from the accent that still shows on the paper
                    a2 = max((v for v in RISO_INKS.values() if contrast(v, pap) >= 1.25),
                             key=lambda v: _hue_gap(v, accent))
                out.append(a2)
            elif want == "accent":
                out.append(accent)
            else:
                out.append(roles[want])
    least = {"toile": 3.0, "engraving": 4.5, "ink": 4.5}.get(r.name, 1.25)
    out = [_ink_on(out[0], pap, least)] + out[1:]
    return {"paper": tuple(pap), "inks": [tuple(v) for v in out]}


_NAMES = [(0, "red"), (14, "vermilion"), (25, "orange"), (40, "ochre"), (52, "yellow"), (75, "chartreuse"),
          (110, "green"), (150, "jade"), (175, "teal"), (195, "cerulean"), (222, "cobalt blue"), (240, "ultramarine"),
          (260, "violet"), (285, "purple"), (310, "magenta"), (330, "pink"), (348, "crimson"), (360, "red")]


def colour_word(c) -> str:
    """A colour in words for the prompt ('deep cobalt blue', 'fluorescent pink', 'warm cream')."""
    h, l, s = _hls(c)
    if s < 0.12 or (l > 0.9 and s < 0.5):
        if l > 0.88:
            r_, _, b_ = rgb(c)
            return "warm cream" if r_ > b_ + 6 else "off-white"
        return "black" if l < 0.14 else ("charcoal grey" if l < 0.4 else "grey")
    deg = h * 360
    word = min(_NAMES, key=lambda n: abs(n[0] - deg))[1]
    if l < 0.22:
        return "navy" if 190 <= deg <= 250 else f"deep {word}" if l > 0.1 else "black"
    if word in ("pink", "crimson", "red", "magenta") and l > 0.6:
        word = "pink"
        if s > 0.8:
            return "fluorescent pink"
    if l > 0.75:
        return f"pale {word}"
    if l < 0.38:
        return f"deep {word}"
    return word


def prompt_head(name: str, pal: Optional[dict] = None) -> str:
    """The recipe's words for the model, its inks named in colour words."""
    r = recipe(name)
    pal = pal or {"paper": PAPER, "inks": [(40, 70, 190), (255, 72, 176), (20, 20, 24)]}
    words = []
    for c in pal["inks"]:
        w = colour_word(c)
        if w not in words:
            words.append(w)
    inks = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return r.prompt.format(inks=inks, paper=colour_word(pal["paper"]))


CALM_WORDS = {
    "left": "The main subject sits in the right third of the picture; the whole left half is open, quiet space, one "
            "flat even colour with nothing in it and no gradient (plain sky or empty ground); the horizon and the "
            "ground stay in the bottom fifth of the picture",
    "right": "The main subject sits in the left third of the picture; the whole right half is open, quiet space, one "
             "flat even colour with nothing in it and no gradient (plain sky or empty ground); the horizon and the "
             "ground stay in the bottom fifth of the picture",
    "center": "The subject stays small near the edges and the bottom; the middle of the picture is open, quiet space, "
              "one flat even colour with nothing in it",
    "top": "The main subject sits in the lower third; the upper half is open, quiet sky, one flat even colour",
    "bottom": "The main subject sits in the upper half; the lower part is open, quiet ground, one flat even colour",
}


# ---------------------------------------------------------------- textures (deterministic per size and seed)

def _blur(a: np.ndarray, sigma: float) -> np.ndarray:
    import cv2
    if sigma <= 0:
        return a
    return cv2.GaussianBlur(a, (0, 0), sigma, borderType=cv2.BORDER_REFLECT)


def _noise(shape, seed: int, sigma: float, salt: int = 0) -> np.ndarray:
    """Smooth noise in 0-1 (rank-normalised, so its histogram is flat whatever the blur)."""
    rng = np.random.default_rng([seed, salt, *shape])
    n = _blur(rng.random(shape, dtype=np.float32), sigma)
    flat = n.ravel()
    order = np.argsort(flat, kind="stable")
    out = np.empty_like(flat)
    out[order] = np.linspace(0, 1, flat.size, dtype=np.float32)
    return out.reshape(shape)


def _paper(shape, seed: int, grain: float) -> np.ndarray:
    """A multiplier around 1: fine fibres and soft mottling of a sheet of paper."""
    if grain <= 0:
        return np.ones(shape, np.float32)
    w = shape[1]
    fine = _noise(shape, seed, max(0.6, w / 2400), 1) - 0.5
    mottle = _noise(shape, seed, w / 120, 2) - 0.5
    return 1 + grain * (0.07 * fine + 0.05 * mottle)


def _grain_field(shape, seed: int, salt: int) -> np.ndarray:
    """The threshold field of a riso drum: soft clumped grain, about 2 px across at 1920 wide."""
    return _noise(shape, seed, max(0.7, shape[1] / 2200), salt)


def _shift(a: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """`a` moved by whole pixels (a drum is off register by whole pixels; no new tints at the edges)."""
    import cv2
    m = np.float32([[1, 0, round(dx)], [0, 1, round(dy)]])
    return cv2.warpAffine(a, m, (a.shape[1], a.shape[0]), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)


def _f(c) -> np.ndarray:
    return np.asarray(rgb(c), np.float32) / 255


def _luma(img: np.ndarray) -> np.ndarray:
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def _levels(lum: np.ndarray, lo_pct: float = 1, hi_pct: float = 99) -> np.ndarray:
    lo, hi = np.percentile(lum, [lo_pct, hi_pct])
    if hi - lo < 0.15:              # a nearly flat picture keeps its tone instead of being stretched to black or white
        return np.clip(lum, 0, 1)
    return np.clip((lum - lo) / (hi - lo), 0, 1)


def _smooth(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def negative(pal: dict) -> bool:
    """A light main ink on a darker paper (`imagery.paper: bg` on a dark site): the print is a negative, so the inks
    go where the picture is light, as a screen print in opaque light inks on dark stock does."""
    return _lum(pal["inks"][0]) > _lum(pal["paper"])


def _lay(out: np.ndarray, cov: np.ndarray, ink, paper) -> np.ndarray:
    """One ink laid over what is printed so far. An ink darker than the paper multiplies (transparent riso and
    letterpress inks); one lighter than the paper is opaque and covers it, since multiplied it would vanish."""
    c = _f(ink)
    if _lum(ink) > _lum(paper):
        return out * (1 - cov) + c * cov
    return out * (1 - cov * (1 - c))


def _print(paper, layers: list[tuple[np.ndarray, tuple]]) -> np.ndarray:
    """Inks overprinted on paper: each layer a coverage map (0-1) of one ink (see _lay)."""
    out = np.ones(layers[0][0].shape + (3,), np.float32) * _f(paper)
    for cov, ink in layers:
        out = _lay(out, cov[..., None], ink, paper)
    return out


def separate(img: np.ndarray, paper, inks: list, overlap: float = 6.0) -> list[np.ndarray]:
    """How much of each ink (0-1) a picture needs at every pixel: the printable mix of the inks on the paper (each ink
    in steps of a tenth) that looks closest to the pixel (CIELAB), where laying one ink over another costs `overlap`
    units of colour difference times the smaller of the two. So a flat tint prints in one ink, as a printer would set
    it, and two inks meet only where the picture needs their mix (a blend, a dark overprint)."""
    import cv2
    from skimage.color import rgb2lab
    k = len(inks)
    steps = {1: 21, 2: 11, 3: 6}.get(k, 4)
    grid = np.stack(np.meshgrid(*[np.linspace(0, 1, steps)] * k, indexing="ij"), -1).reshape(-1, k).astype(np.float32)
    mix = np.ones((len(grid), 3), np.float32) * _f(paper)
    for j in range(k):
        mix = _lay(mix, grid[:, j:j + 1], inks[j], paper)
    lab_mix = rgb2lab(mix[None])[0].astype(np.float32)
    srt = np.sort(grid, 1)
    cost_mix = overlap * srt[:, :-1].sum(1) if k > 1 else np.zeros(len(grid), np.float32)
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA) if w > 64 else img
    lab = rgb2lab(np.clip(small, 0, 1)).reshape(-1, 3).astype(np.float32)
    best = np.empty(len(lab), np.int32)
    for s in range(0, len(lab), 65536):                                # in chunks, to bound memory
        part = lab[s:s + 65536]
        dist = np.sqrt(((part[:, None, :] - lab_mix[None]) ** 2).sum(-1)) + cost_mix[None]
        best[s:s + 65536] = np.argmin(dist, 1)
    d = grid[best].reshape(small.shape[0], small.shape[1], k)
    if small is not img:
        d = cv2.resize(d, (w, h), interpolation=cv2.INTER_LINEAR).reshape(h, w, k)
    return [np.clip(d[..., j], 0, 1) for j in range(k)]


# ---------------------------------------------------------------- the post-processes (float RGB 0-1 in and out)

def risograph(img, pal, seed=7, grain=0.6, levels=4):
    """Two (or more) inks: separated, flats snapped to solid ink or bare paper, every tint screened by the drum's grain
    (with grain 0: posterised to `levels` and printed solid), the second drum a few pixels off register, on paper."""
    h, w = img.shape[:2]
    dens = separate(_blur(img, w / 800), pal["paper"], pal["inks"])     # the model's own grain becomes a tint
    rng = np.random.default_rng([seed, h, w, 9])
    ang = rng.uniform(0, 2 * np.pi)
    off = max(1.0, w * 0.0018)
    layers = []
    for i, (d, ink) in enumerate(zip(dens, pal["inks"])):
        inked = d[d > 0.15]
        if inked.size > d.size * 0.02:          # the picture's fullest flat of this ink prints as a solid
            d = np.clip(d / max(0.5, float(np.percentile(inked, 90))), 0, 1)
        q = _smooth(0.12, 0.82, d)                                            # flats snap, tints stay
        if grain > 0:
            solid = 1 - 0.003 * grain                                         # a solid keeps a few drop-outs
            # one grain for the first two drums, the second read inverted: where one ink fades, the other's grain
            # fills the gaps, as a riso blend of two inks does, instead of muddy overprint and bare paper
            field = _grain_field(d.shape, seed, 20 + i // 2)
            if i % 2:
                field = 1 - field
            cov = (np.minimum(q, solid) > field).astype(np.float32)
            cov = _blur(cov, 0.6)
        else:
            cov = (np.round(q * (levels - 1)) / (levels - 1) >= 0.5).astype(np.float32)
        if i:
            cov = _shift(cov, off * np.cos(ang + i), off * np.sin(ang + i))
        layers.append((cov, ink))
    out = _print(pal["paper"], layers)
    return np.clip(out * _paper((h, w), seed, grain)[..., None], 0, 1)


def mono(img, pal, seed=7, grain=0.35, contrast_=1.0, gamma=1.0):
    """One ink on paper, the picture's tone as how much ink (toile, engraving)."""
    h, w = img.shape[:2]
    lum = _levels(_luma(img), 0.5, 99.5) ** gamma
    tone = lum if negative(pal) else 1 - lum          # how much ink: the dark of the picture, or its light on dark stock
    d = np.clip(0.5 + (tone - 0.5) * contrast_, 0, 1)
    if grain > 0:      # ink sits unevenly in the grain of the plate and the paper
        d = d * (1 - 0.12 * grain * _noise((h, w), seed, max(0.6, w / 2000), 3))
    out = _print(pal["paper"], [(d, pal["inks"][0])])
    return np.clip(out * _paper((h, w), seed, grain)[..., None], 0, 1)


def toile(img, pal, seed=7, grain=0.35):
    return mono(img, pal, seed, grain, contrast_=1.05, gamma=1.1)


def engraving(img, pal, seed=7, grain=0.35):
    import cv2
    sharp = np.clip(cv2.addWeighted(img, 1.6, _blur(img, 1.2), -0.6, 0), 0, 1)
    return mono(sharp, pal, seed, grain, contrast_=1.25, gamma=1.0)


def ink(img, pal, seed=7, grain=0.3):
    """Black (the dark ink) where the brush is loaded, the washes in the accent: ink and one colour."""
    h, w = img.shape[:2]
    lum = _levels(_luma(img), 0.5, 99.5)
    d = lum if negative(pal) else 1 - lum
    black = _smooth(0.42, 0.62, d)
    wash = np.clip(_smooth(0.06, 0.42, d) - black, 0, 1) * 0.8
    if grain > 0:
        dry = _noise((h, w), seed, max(0.6, w / 1800), 4)
        black = black * (1 - 0.25 * grain * (dry > 0.85))
    layers = [(wash, pal["inks"][1] if len(pal["inks"]) > 1 else pal["inks"][0]), (black, pal["inks"][0])]
    out = _print(pal["paper"], layers)
    return np.clip(out * _paper((h, w), seed, grain)[..., None], 0, 1)


def screen(d: np.ndarray, period: float, angle: float) -> np.ndarray:
    """An AM halftone screen of a density map: round dots on a grid `period` px apart at `angle` degrees, each dot's
    area its cell's density (anti-aliased over a pixel)."""
    h, w = d.shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.deg2rad(angle)
    u = (x * np.cos(a) + y * np.sin(a)) / period
    v = (-x * np.sin(a) + y * np.cos(a)) / period
    spot = (np.cos(2 * np.pi * u) + np.cos(2 * np.pi * v)) / 2
    db = _blur(d, period / 3)
    t = 1 - 2 * db
    cov = np.clip((spot - t) / (2 * np.pi / period) + 0.5, 0, 1)
    return cov * np.clip(db * 40, 0, 1)            # no tone, no dot (not even the anti-aliased half pixel)


def halftone(img, pal, seed=7, grain=0.25, period: Optional[float] = None):
    """Two inks as dot screens at different angles: the dark ink carries the picture's tone (45 degrees), the accent
    its colour (15 degrees), so any picture prints, whatever colours it was generated in."""
    import cv2
    h, w = img.shape[:2]
    period = period or max(4.0, w / 210)
    lum = _levels(_luma(img), 1, 99)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    chroma = hsv[..., 1] * hsv[..., 2]                                # saturated and not dark
    tone = lum if negative(pal) else 1 - lum                          # on dark stock the light ink carries the light
    dark = 0.9 * _smooth(0.18, 1.0, tone) ** 1.15           # the darkest shadow keeps small holes: still a screen
    dens = [dark] + [np.clip(_smooth(0.12, 0.7, chroma) * (1 - dark) * 0.85, 0, 1)] * (len(pal["inks"]) - 1)
    angles = [45, 15, 75, 0]
    layers = [(screen(_smooth(0.04, 0.96, d), period, angles[i % 4]), ink_)
              for i, (d, ink_) in enumerate(zip(dens, pal["inks"]))]
    out = _print(pal["paper"], layers[::-1])
    return np.clip(out * _paper((h, w), seed, grain)[..., None], 0, 1)


def _harmonise(colours: np.ndarray, pal, pull: float) -> np.ndarray:
    """Colours moved toward the nearest palette colour (in Lab), the nearer the more, so the picture keeps its own
    colours but takes the brand's as its main notes."""
    from skimage.color import lab2rgb, rgb2lab
    targets = np.array([_f(c) for c in [*pal["inks"], pal["paper"]]], np.float32)
    lab = rgb2lab(colours.reshape(-1, 1, 3)).reshape(-1, 3)
    tl = rgb2lab(targets.reshape(-1, 1, 3)).reshape(-1, 3)
    dist = np.sqrt(((lab[:, None] - tl[None]) ** 2).sum(-1))
    near = np.argmin(dist, 1)
    wgt = pull * np.exp(-dist[np.arange(len(lab)), near] / 45)[:, None]
    out = lab + (tl[near] - lab) * wgt
    return np.clip(lab2rgb(out.reshape(-1, 1, 3)).reshape(colours.shape), 0, 1).astype(np.float32)


def gouache(img, pal, seed=7, grain=0.45):
    """Opaque matte paint: soft gradients flattened into shapes (mean shift), colours pulled toward the brand's, brush
    streaks and the tooth of the paper."""
    import cv2
    h, w = img.shape[:2]
    u8 = np.round(img * 255).astype(np.uint8)
    flat = cv2.pyrMeanShiftFiltering(u8, max(6, round(w / 190)), 22, maxLevel=1).astype(np.float32) / 255
    out = _harmonise(flat.reshape(-1, 3), pal, 0.45).reshape(h, w, 3)
    if grain > 0:
        streak = _noise((h, w), seed, 0.8, 6)
        kernel = np.full((1, max(3, w // 160)), 1 / max(3, w // 160), np.float32)
        streak = cv2.filter2D(streak, -1, kernel, borderType=cv2.BORDER_REFLECT)      # brush direction
        out = out * (1 + grain * 0.12 * (streak - streak.mean()))[..., None]
        out = out * _paper((h, w), seed, grain)[..., None]
    return np.clip(out, 0, 1)


def watercolour(img, pal, seed=7, grain=0.5):
    """Transparent washes on paper: the white of the picture becomes the paper, pigment pools at the edges of a wash
    and granulates in the paper's tooth; colours lean toward the brand's."""
    h, w = img.shape[:2]
    white = np.maximum(np.percentile(img.reshape(-1, 3), 99.5, axis=0), 0.5)
    dens = np.clip(1 - img / white, 0, 1)                            # pigment per channel
    bare = dens.max(-1) < 0.03                                       # untouched paper stays the paper
    flat = _harmonise((1 - dens).reshape(-1, 3), pal, 0.25).reshape(h, w, 3)
    dens = 1 - flat
    dens[bare] = 0
    edge = np.clip(dens - _blur(dens, w / 400), 0, 1)                # pooled at the inside of a wash's edge
    dens = np.clip(dens + 0.7 * edge, 0, 1)
    if grain > 0:
        gran = _noise((h, w), seed, max(0.8, w / 1200), 7)
        dens = dens * (1 + 0.35 * grain * (gran - 0.5))[..., None]
    out = _f(pal["paper"]) * (1 - np.clip(dens, 0, 1))
    return np.clip(out * _paper((h, w), seed, grain)[..., None], 0, 1)


def _margin(lines: np.ndarray, most: int) -> int:
    """How many lines from the edge (lines[0] is the edge) are a paper margin the model drew around its print: pale,
    even lines, then a clear change into the picture (past a thin printed rule, if there is one). 0 when there is none,
    so a pale sky that simply runs to the edge is kept."""
    first = lines[0]
    if first.mean() < 0.72 or first.std() > 0.06:
        return 0
    ref = first.mean()
    n = 0
    while n < most and lines[n].std() < 0.06 and abs(lines[n].mean() - ref) < 0.05:
        n += 1
    if n < 3 or n >= most:
        return 0
    rule = 0          # a ruled border line just inside the margin goes too
    while n + rule < most and rule < max(3, len(lines[0]) // 150) and lines[n + rule].mean() < ref - 0.25:
        rule += 1
    if rule and n + rule < most and abs(lines[n + rule].mean() - ref) < 0.08:
        n += rule
        while n < most and lines[n].std() < 0.06 and abs(lines[n].mean() - ref) < 0.05:
            n += 1
    return n + 2


def trim_margin(img: np.ndarray, most: float = 0.12) -> np.ndarray:
    """The picture without a paper margin drawn around it (on at least two sides), scaled back to cover its size:
    an image model asked for a print often draws the sheet's border too, and a hero must run to the edges."""
    import cv2
    h, w = img.shape[:2]
    g = _luma(img)
    t = _margin(g, int(h * most))
    b = _margin(g[::-1], int(h * most))
    lft = _margin(g.T, int(w * most))
    r = _margin(g.T[::-1], int(w * most))
    if sum(1 for v in (t, b, lft, r) if v) < 2:
        return img
    inner = img[t:h - b, lft:w - r]
    ih, iw = inner.shape[:2]
    s = max(w / iw, h / ih)
    big = cv2.resize(inner, (max(w, round(iw * s)), max(h, round(ih * s))), interpolation=cv2.INTER_CUBIC)
    y0, x0 = (big.shape[0] - h) // 2, (big.shape[1] - w) // 2
    return np.clip(big[y0:y0 + h, x0:x0 + w], 0, 1)


POST: dict[str, Callable] = {"risograph": risograph, "toile": toile, "engraving": engraving, "ink": ink,
                             "halftone": halftone, "gouache": gouache, "watercolour": watercolour}


def _arr(image) -> np.ndarray:
    return (image if isinstance(image, np.ndarray) else np.asarray(image.convert("RGB"), np.float32) / 255).astype(np.float32)


def apply(image, name: str, pal: dict, seed: int = 7, grain: Optional[float] = None, trim: bool = True):
    """A PIL image (or float array) in medium `name`, printed with `pal`; returns a PIL RGB image. Deterministic.
    trim: first cut away a paper margin the model drew around the picture (trim_margin)."""
    from PIL import Image
    r = recipe(name)
    if r is None:
        raise ValueError(f"{name!r} is not a named medium ({', '.join(NAMES)})")
    arr = _arr(image)
    if trim:
        arr = trim_margin(arr)
    out = POST[r.name](arr, pal, seed, r.grain if grain is None else grain)
    return Image.fromarray(np.round(np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- composition: calm space for the headline

# where the headline sits on a full-bleed hero, as x0, y0, x1, y1 in 0-1 of the picture
REGIONS = {"left": (0.04, 0.24, 0.48, 0.76), "right": (0.52, 0.24, 0.96, 0.76), "center": (0.2, 0.26, 0.8, 0.74),
           "top": (0.06, 0.04, 0.94, 0.44), "bottom": (0.06, 0.56, 0.94, 0.96)}
MIRROR = {"left": "right", "right": "left"}
CALM_LIMIT = 0.06


def busyness(image, box) -> float:
    """How busy a part of a picture is for words set over it: the share of it covered by edges at the scale of a
    headline's letters, plus a fifth of its tonal spread (a band of light and dark under one line of type is as bad as
    detail). 0 is a clear flat sky; above 0.06 a headline has to fight. Measured at 320 px wide after a light blur, so
    paper grain, hatching and a dot screen read as the tone they make, not as detail."""
    import cv2
    arr = _arr(image)
    g = _luma(arr)
    g = cv2.resize(g, (320, max(8, round(g.shape[0] * 320 / g.shape[1]))), interpolation=cv2.INTER_AREA)
    g = _blur(g, 1.0)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    h, w = g.shape
    x0, y0, x1, y1 = box
    sl = (slice(round(y0 * h), round(y1 * h)), slice(round(x0 * w), round(x1 * w)))
    part = mag[sl]
    if not part.size:
        return 0.0
    tone_ = _blur(g, 4.0)[sl]
    spread = float(np.percentile(tone_, 95) - np.percentile(tone_, 5))
    return float((part > 0.3).mean()) + 0.2 * spread


def calm(image, side: str, limit: float = CALM_LIMIT) -> tuple[bool, float]:
    """(is the headline's side calm enough, its busyness)."""
    score = busyness(image, REGIONS[side])
    return score <= limit, round(score, 4)


# ---------------------------------------------------------------- the build side

def site_palette(project, name: str, im=None) -> dict:
    """The palette of medium `name` for this project: the theme's resolved colours (preset, style, brand, site.yaml),
    with `imagery.inks` / `imagery.paper` over them."""
    from .compile import themes
    try:
        site = project.load()
        t = themes.resolve(site.theme)
        colors = t["colors"]
    except Exception:          # a spec that does not load is reported by the build; the medium still has its defaults
        colors = {}
    inks = getattr(im, "inks", None) or None
    paper = getattr(im, "paper", None)
    return palette(name, colors, inks, paper)


def key(name: str, pal: dict, grain: Optional[float], calm_side: Optional[str]) -> list:
    return [name, VERSION, [list(pal["paper"]), [list(c) for c in pal["inks"]]], grain, calm_side]


def _open(path: Path, trim: bool):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if not trim:
        return im
    return Image.fromarray(np.round(trim_margin(_arr(im)) * 255).astype(np.uint8), "RGB")


def finish(project, raw: Path, name: Optional[str], pal: Optional[dict], seed: int, grain: Optional[float],
           calm_side: Optional[str], regenerate: Optional[Callable[[int], Path]] = None, tries: int = 3,
           log: Callable[[str], None] = print) -> Path:
    """The image as the page shows it: the composition rule (if `calm_side`), then the medium's post-process (if `name`).
    `regenerate(k)` gives another raw still for try k (a generated image: it may also be mirrored); a file is only
    checked, and the build says when its side is busy."""
    from PIL import Image
    from .project import file_key
    digest = hashlib.sha1(json.dumps([file_key(raw), key(name or "", pal or {"paper": [], "inks": []}, grain,
                                                          calm_side), tries, regenerate is not None]
                                     ).encode()).hexdigest()[:12]
    out = project.build / "_generated" / f"med_{digest}.png"
    if out.exists():
        return out
    from .fidelity import would_render
    would_render("medium", f"{name or 'composition'} {raw.name}")
    im = _open(raw, bool(name))
    note = {}
    if calm_side:
        best = None
        for k in range(tries if regenerate else 1):
            cand = im if k == 0 else _open(regenerate(k), bool(name))
            ok, score = calm(cand, calm_side)
            if best is None or score < best[1]:
                best = (cand, score, k, False)
            if ok:
                break
            if calm_side in MIRROR and regenerate:      # the subject on the headline's side: try it the other way round
                flipped = cand.transpose(Image.FLIP_LEFT_RIGHT)
                ok, score = calm(flipped, calm_side)
                if score < best[1]:
                    best = (flipped, score, k, True)
                if ok:
                    break
        im, score, k, flip = best
        note = {"side": calm_side, "busyness": score, "try": k, "mirrored": flip}
        if score > CALM_LIMIT:
            log(f"  composition: the {calm_side} side is busy ({score:.3f} > {CALM_LIMIT})"
                + (f" after {tries} tries; the calmest is used" if regenerate else "")
                + " (try another seed or a simpler prompt, or put the headline on the other side)")
        else:
            log(f"  composition: {calm_side} side calm ({score:.3f})" + (", mirrored" if flip else "")
                + (f", try {k + 1}" if k else ""))
    if name:
        im = apply(im, name, pal, seed, grain, trim=False)
        log(f"  medium: {name} in {', '.join(hexc(c) for c in pal['inks'])} on {hexc(pal['paper'])}")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    if note:
        out.with_suffix(".json").write_text(json.dumps(note))
    return out


def tone(image, side: str) -> str:
    """'light' or 'dark': what the headline's side of a finished picture is, so the words take the other."""
    arr = _arr(image)
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = REGIONS[side]
    part = _luma(arr[round(y0 * h):round(y1 * h), round(x0 * w):round(x1 * w)])
    return "light" if float(part.mean()) > 0.56 else "dark"
