"""Themes as layered token sets (defaults, preset, style, brand, site.yaml) -> CSS custom properties and font links."""
from __future__ import annotations

import colorsys
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import yaml

from .. import safety
from ..spec import FontFile, Theme

THEMES_FILE = Path(__file__).resolve().parent.parent / "themes.yaml"
STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"

# Google Fonts css2 axis specs (verified). Unknown families fall back to regular + bold.
FONT_AXES = {
    "Space Grotesk": "wght@300..700",
    "IBM Plex Mono": "ital,wght@0,400;0,500;1,400",
    "IBM Plex Sans": "ital,wght@0,100..700;1,100..700",
    "Instrument Serif": "ital@0;1",
    "Inter Tight": "ital,wght@0,100..900;1,100..900",
    "Inter": "ital,opsz,wght@0,14..32,100..900;1,14..32,100..900",
    "JetBrains Mono": "wght@100..800",
    "Fraunces": "ital,opsz,wght@0,9..144,100..900;1,9..144,100..900",
    "Sora": "wght@100..800",
    "Unbounded": "wght@200..900",
    "Manrope": "wght@200..800",
    "Bricolage Grotesque": "opsz,wght@12..96,200..800",
    "DM Mono": "ital,wght@0,300;0,400;0,500;1,400",
    "Cormorant Garamond": "ital,wght@0,300..700;1,300..700",
    "Figtree": "ital,wght@0,300..900;1,300..900",
    "Archivo": "ital,wght@0,100..900;1,100..900",
    "Space Mono": "ital,wght@0,400;0,700;1,400",
    "Plus Jakarta Sans": "ital,wght@0,200..800;1,200..800",
    "DM Sans": "ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000",
    "Instrument Sans": "ital,wdth,wght@0,75..100,400..700;1,75..100,400..700",
    "Outfit": "wght@100..900",
    "Newsreader": "ital,opsz,wght@0,6..72,200..800;1,6..72,200..800",
    # faces used by the styles (engine/styles.yaml); "" = a single-style family, no axis spec
    "Syne": "wght@400..800",
    "Tilt Neon": "",
    "Anton": "",
    "Fredoka": "wght@300..700",
    "Nunito": "ital,wght@0,200..1000;1,200..1000",
    "Bangers": "",
    "Comic Neue": "ital,wght@0,300;0,400;0,700;1,400",
    "Oswald": "wght@200..700",
    "VT323": "",
    "Archivo Black": "",
    "Josefin Sans": "ital,wght@0,100..700;1,100..700",
    "Press Start 2P": "",
    "Pixelify Sans": "wght@400..700",
    "Limelight": "",
}
# the families `studio directions` pairs (engine/directions/typefaces.py), each with its verified css2 axis spec
from ..directions.typefaces import AXES as _DIRECTION_AXES   # noqa: E402
for _family, _axes in _DIRECTION_AXES.items():
    FONT_AXES.setdefault(_family, _axes)
FALLBACK = {"display": "system-ui, sans-serif", "body": "system-ui, sans-serif", "mono": "ui-monospace, monospace"}
SERIFS = {"Instrument Serif", "Fraunces", "Cormorant Garamond", "Newsreader"}
from ..directions.typefaces import CLASS as _DIRECTION_CLASS   # noqa: E402
SERIFS |= {f for f, c in _DIRECTION_CLASS.items() if c.startswith("serif") or c == "slab"}


@lru_cache(maxsize=1)
def presets() -> dict:
    with open(THEMES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def styles() -> dict:
    """Every engine/styles/<name>/style.yaml, by name (label, about, mode, colors, fonts, font_axes, radius)."""
    out = {}
    for f in sorted(STYLES_DIR.glob("*/style.yaml")):
        with open(f, encoding="utf-8") as fh:
            out[f.parent.name] = yaml.safe_load(fh)
    return out


def style_dir(name: str) -> Path:
    """engine/styles/<name>/: style.css, and optionally blocks.html.j2 (its own markup for some block types),
    chrome.html.j2 (page furniture around the sections) and scenes.html.j2."""
    return STYLES_DIR / name


def style_css(name: str, t: Optional[dict] = None) -> str:
    """The style's stylesheet; in a brand's colours and fonts when the theme `t` wears one (theme.from)."""
    css = (style_dir(name) / "style.css").read_text(encoding="utf-8")
    return reskin(css, t.get("skin")) if t else css


def _hex_rgb(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


# ---------------------------------------------------------------- token sets and their layers
# A theme is a stack of token sets, each laid over the one before: the engine's defaults, the preset, the style, the
# brand (theme.from), then what site.yaml sets on theme. Presets (themes.yaml) and styles (style.yaml) are token sets
# with names.
DEFAULTS = {"mode": "dark", "colors": {}, "fonts": {}, "font_axes": {}, "display_weight": 500, "em_italic": False,
            "display_em": "accent", "labels": "caps", "display_optical_size": None, "radius": "4px",
            # what runtime/src/styles.css and the runtime hard-coded before these were tokens (#15)
            "space": {"gutter": "clamp(20px, 4vw, 64px)", "max": "1600px", "caption": "min(680px, 82vw)"},
            "type": {"scale": 1, "body": "17px"}, "shade": {"strength": 1},
            "motion": {"ease": "cubic-bezier(.22, .8, .2, 1)", "enter": 0.2, "follow": 0.1},
            "grain": 0, "phone": None}
MERGED = ("colors", "fonts", "font_axes", "space", "type", "shade", "motion")   # merge key by key; the rest replace
# the stylesheet's custom property for each token it reads; studio.css declares the defaults
CSS_TOKENS = {("space", "gutter"): "--gutter", ("space", "max"): "--max", ("space", "caption"): "--caption-w",
              ("type", "scale"): "--type-scale", ("type", "body"): "--body-size", ("shade", "strength"): "--shade-strength",
              ("motion", "ease"): "--ease"}
RUNTIME_TOKENS = {"phone": ("phone",), "enter": ("motion", "enter"), "follow": ("motion", "follow")}   # window.__ssTheme
TOKENS = tuple(DEFAULTS)                      # what a style.yaml contributes (the rest of it is about the style itself)


def layer(*sets: dict) -> dict:
    """Lay token sets over each other in order. A token a set leaves out (or sets to None) keeps the value below."""
    out: dict = {}
    for s in sets:
        for k, v in s.items():
            if v is not None:
                out[k] = dict(out.get(k, {}), **v) if k in MERGED else v
    return out


def preset_tokens(name: str) -> dict:
    p = presets().get(name)
    if p is None:
        raise ValueError(f"unknown theme preset '{name}' (have: {', '.join(presets())})")
    return p


def style_tokens(name: str) -> dict:
    st = styles().get(name)
    if st is None:
        raise ValueError(f"unknown style '{name}' (have: {', '.join(styles())})")
    return {k: v for k, v in st.items() if k in TOKENS}


def override_tokens(theme: Theme) -> dict:
    """What site.yaml sets on `theme:` itself, the top layer. An empty value (0, '') never overrode, so it still doesn't."""
    return {"mode": theme.mode or None, "colors": theme.colors, "fonts": theme.fonts, "radius": theme.radius or None,
            "display_weight": theme.display_weight or None, "em_italic": theme.display_italic_em,
            "display_em": theme.display_em or None, "labels": theme.labels or None,
            "display_optical_size": theme.display_optical_size or None,
            **{k: getattr(theme, k).model_dump(exclude_none=True) if getattr(theme, k) else None
               for k in ("space", "type", "shade", "motion")},
            "grain": theme.grain, "phone": theme.phone}


def brand_tokens(theme: Theme) -> Optional[dict]:
    """theme.from as a token set: written inline, or read from its source when the project loaded (engine/brand.py)."""
    if theme.from_ is None:
        return None
    if isinstance(theme.from_, str):
        if theme._brand is None:
            raise ValueError(f"theme.from {theme.from_[:60]!r} is read when the project is loaded (Project.load), "
                             "not from a bare spec")
        return theme._brand
    return theme.from_.model_dump(exclude_none=True)


def layers(theme: Theme) -> list[tuple[str, dict]]:
    """The token sets this theme is made of, bottom first, each named for where it came from."""
    out = [("defaults", DEFAULTS), (f"preset {theme.preset}", preset_tokens(theme.preset))]
    brand = brand_tokens(theme)
    if theme.style:
        st = style_tokens(theme.style)
        if brand and brand.get("colors"):      # the brand's palette replaces the style's whole skin, extras included
            st = {k: v for k, v in st.items() if k != "colors"}
        out.append((f"style {theme.style}", st))
    if brand:
        out.append(("brand", brand_layer(brand, theme.style)))
    out.append(("site.yaml", override_tokens(theme)))
    return out


def resolve(theme: Theme) -> dict:
    tokens = layer(*(s for _, s in layers(theme)))
    colors, radius = tokens["colors"], tokens["radius"]
    brand = brand_tokens(theme)
    fonts, font_files = own_fonts(tokens["fonts"])
    # these end up inside the page's <style> block, so none may carry anything but a plain value (engine/safety.py)
    for k, c in colors.items():
        if not safety.css_value_ok(c):
            raise ValueError(f"theme colour {k}: {str(c)[:40]!r} is not a plain CSS colour (use #hex, rgb(...) or a colour name)")
    for k, f in fonts.items():
        if not safety.CSS_NAME.fullmatch(str(k)) or not safety.FONT_NAME.fullmatch(str(f)):
            raise ValueError(f"theme font {k}: {str(f)[:40]!r} is not a Google Fonts family name")
    if not safety.css_value_ok(radius):
        raise ValueError(f"theme radius {str(radius)[:40]!r} is not a CSS length such as 4px")
    for (group, k) in CSS_TOKENS:
        if not safety.css_value_ok(tokens[group][k]):
            raise ValueError(f"theme {group}.{k}: {str(tokens[group][k])[:40]!r} is not a plain CSS value")
    return {
        "style": theme.style,
        "font_axes": tokens["font_axes"],
        "mode": tokens["mode"],
        "colors": colors,
        "fonts": fonts,
        "font_files": font_files,
        "display_weight": tokens["display_weight"],
        "em_italic": tokens["em_italic"],
        "em": tokens["display_em"],
        "labels": tokens["labels"],
        "display_opsz": tokens.get("display_optical_size"),
        "radius": radius,
        **{k: tokens.get(k) for k in ("space", "type", "shade", "motion", "grain", "phone")},
        # what the runtime reads (window.__ssTheme): only tokens moved off their defaults, so a page that sets none is unchanged
        "runtime": {name: v for name, path in RUNTIME_TOKENS.items()
                    if (v := _at(tokens, path)) != _at(DEFAULTS, path)},
        "logo": (brand or {}).get("logo"),
        "skin": skin(theme.style, colors, fonts) if brand and theme.style else None,
    }


def own_fonts(fonts: dict) -> tuple[dict, list[dict]]:
    """Font roles as family names, and the project's own font files among them ({file: ...} roles), one face each.
    A file's family defaults to its name: fonts/Brand-Sans.woff2 is set as 'Brand Sans'."""
    names, files = {}, []
    for role, f in fonts.items():
        if isinstance(f, dict):
            f = FontFile.model_validate(f)
        if isinstance(f, FontFile):
            family = f.family or re.sub(r"[^\w .+&'-]", "", re.sub(r"[-_\s]+", " ", Path(f.file).stem)).strip()
            if not any(x["file"] == f.file for x in files):
                files.append({"family": family, "file": f.file, "weight": f.weight or "100 900", "style": f.style})
            f = family
        names[role] = f
    return names, files


def _at(d: dict, path: tuple):
    for k in path:
        d = d.get(k) if isinstance(d, dict) else None
    return d


# ---------------------------------------------------------------- contrast (WCAG 2.x)
SMALL_TEXT = 4.5   # AA for body-size text; ink-2, ink-3 and accent-coloured kickers must all clear it


def _rgb(h: str) -> tuple[float, float, float]:
    return tuple(float(v) for v in _hex_rgb(h).split(", "))


def _lum(rgb) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _mix(fg, bg, a: float):
    return tuple(a * x + (1 - a) * y for x, y in zip(fg, bg))


def contrast(fg, bg) -> float:
    la, lb = _lum(fg), _lum(bg)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _min_alpha(ink, bgs, target: float, floor: float) -> float:
    """Smallest opacity of ink (>= floor) that reaches target contrast on every background."""
    a = floor
    while a < 1 and any(contrast(_mix(ink, b, a), b) < target for b in bgs):
        a = round(a + 0.01, 2)
    return min(a, 1.0)


def _readable_accent(accent, ink, bgs, target: float) -> tuple:
    """The accent, moved toward the ink colour only as far as small text needs."""
    k = 0.0
    col = accent
    while k < 1 and any(contrast(col, b) < target for b in bgs):
        k = round(k + 0.02, 2)
        col = _mix(ink, accent, k)
    return col


def _css_rgb(rgb) -> str:
    return "#" + "".join(f"{round(v):02x}" for v in rgb)


def css_vars(t: dict, log=lambda m: None) -> str:
    c, f = t["colors"], t["fonts"]
    ink = _hex_rgb(c["ink"])
    ink_rgb, bgs = _rgb(c["ink"]), [_rgb(c["bg"]), _rgb(c["bg2"])]
    # Secondary text tiers are derived per theme so small labels always stay readable: a fixed opacity
    # passes on dark backgrounds but fails on light ones.
    if t.get("skin"):     # a style wearing a brand may lay its own near-black (or near-white) under the words
        bgs.append((0.0, 0.0, 0.0) if t["mode"] == "dark" else (255.0, 255.0, 255.0))
    a3 = _min_alpha(ink_rgb, bgs, SMALL_TEXT, 0.44)
    a2 = max(_min_alpha(ink_rgb, bgs, SMALL_TEXT, 0.68), min(1.0, round(a3 + 0.14, 2)))   # keep the tiers apart
    for key in ("ink2", "ink3"):
        if key in c and c[key].startswith("#") and any(contrast(_rgb(c[key]), b) < SMALL_TEXT for b in bgs):
            log(f"  warning: theme colour {key} {c[key]} is below {SMALL_TEXT}:1 contrast; small text will be hard to read")
    accent_text = c.get("accent_text") or _css_rgb(_readable_accent(_rgb(c["accent"]), ink_rgb, bgs, SMALL_TEXT))
    tokens = {
        "--bg": c["bg"], "--bg-2": c["bg2"], "--ink": c["ink"],
        "--ink-rgb": ink, "--bg-rgb": _hex_rgb(c["bg"]),
        "--ink-2": c.get("ink2", f"rgba({ink}, {a2})"), "--ink-3": c.get("ink3", f"rgba({ink}, {a3})"),
        "--line": c.get("line", f"rgba({ink}, .13)"),
        "--accent": c["accent"], "--accent-2": c["accent2"], "--accent-ink": c["accent_ink"],
        "--accent-text": accent_text,
        "--accent-rgb": _hex_rgb(c["accent"]),
        "--font-display": f'"{f["display"]}", {"Georgia, serif" if f["display"] in SERIFS else FALLBACK["display"]}',
        "--font-body": f'"{f["body"]}", {"Georgia, serif" if f["body"] in SERIFS else FALLBACK["body"]}',
        "--font-mono": f'"{f["mono"]}", {FALLBACK["mono"]}',
        "--display-weight": str(t["display_weight"]),
        "--em-style": "italic" if t["em_italic"] or t["em"] == "bold" else "normal",
        "--radius": t["radius"],
        "color-scheme": t["mode"],
    }
    for (group, k), var in CSS_TOKENS.items():   # new tokens are written only when moved off the stylesheet's default
        if t[group][k] != DEFAULTS[group][k]:
            tokens[var] = str(t[group][k])
    for role, fam in f.items():   # extra roles a style declares (masthead, script, marquee...): --font-<role>
        if role not in ("display", "body", "mono"):
            tokens[f"--font-{role}"] = f'"{fam}", {"Georgia, serif" if fam in SERIFS else FALLBACK["body"]}'
    out = ":root {\n" + "\n".join(f"  {k}: {v};" for k, v in tokens.items()) + "\n}"
    return out + "\n" + surface_css(c, t["mode"])


def _surface_tokens(bg, bg2, ink, accent, accent2) -> dict:
    """Text tiers, accent text and <em> colour for one surface, all checked against its own background."""
    bgs = [bg, bg2]
    a3 = _min_alpha(ink, bgs, SMALL_TEXT, 0.44)
    a2 = max(_min_alpha(ink, bgs, SMALL_TEXT, 0.68), min(1.0, round(a3 + 0.14, 2)))
    ink_s = ", ".join(str(round(v)) for v in ink)
    em = max((accent, accent2), key=lambda col: min(contrast(col, b) for b in bgs))
    btn = accent if contrast(accent, bg) >= 3 else ink               # primary buttons must stand off the panel
    btn_ink = max((bg, ink, (255, 255, 255), (0, 0, 0)), key=lambda col: contrast(col, btn))
    return {
        "--btn-bg": _css_rgb(btn), "--btn-ink": _css_rgb(btn_ink),
        "--bg": _css_rgb(bg), "--bg-2": _css_rgb(bg2), "--ink": _css_rgb(ink),
        "--ink-rgb": ink_s, "--bg-rgb": ", ".join(str(round(v)) for v in bg),
        "--ink-2": f"rgba({ink_s}, {a2})", "--ink-3": f"rgba({ink_s}, {a3})", "--line": f"rgba({ink_s}, .14)",
        "--accent-text": _css_rgb(_readable_accent(accent, ink, bgs, SMALL_TEXT)),
        "--em-color": _css_rgb(em if min(contrast(em, b) for b in bgs) >= 3 else ink),
    }


def surface_css(c: dict, mode: str) -> str:
    """Per-section colour schemes (`surface:` in the spec) derived from the theme, so a dark panel on a light
    theme gets the same contrast guarantees as the page itself."""
    bg, bg2, ink = _rgb(c["bg"]), _rgb(c["bg2"]), _rgb(c["ink"])
    acc, acc2 = _rgb(c["accent"]), _rgb(c["accent2"])
    if mode == "light":
        dark = (ink, _mix(bg, ink, 0.08), bg)                  # the theme's ink becomes the background
        light = (bg2, bg, ink)
    else:
        dark = (_mix(bg, (0, 0, 0), 0.4), bg, ink)
        light = (ink, _mix(bg, ink, 0.9), bg)                  # inverted: a pale panel on a dark site
    soft = _mix(acc2, (255, 255, 255), 0.55) if mode == "light" else _mix(acc2, bg, 0.25)
    accent_ink = max((ink, bg), key=lambda col: contrast(col, soft))
    accent = (soft, _mix(soft, accent_ink, 0.06), accent_ink)
    css = []
    for name, (s_bg, s_bg2, s_ink) in (("dark", dark), ("light", light), ("accent", accent)):
        tok = _surface_tokens(s_bg, s_bg2, s_ink, acc, acc2)
        body = " ".join(f"{k}: {v};" for k, v in tok.items())
        scheme = "dark" if _lum(s_bg) < 0.2 else "light"
        css.append(f".ss-surface-{name} {{ {body} color-scheme: {scheme}; background: var(--bg); color: var(--ink); }}")
    return "\n".join(css)


# the phone widths the stylesheet grew up with: the layout (900), scenes (760) and one-take pages (700)
PHONE_WIDTHS = re.compile(r"\(max-width:\s*(?:900|760|700)px\)")


def phone_css(css: str, phone: int) -> str:
    """The runtime stylesheet with every phone width set to theme.phone (a media query cannot read a CSS variable)."""
    return PHONE_WIDTHS.sub(f"(max-width: {int(phone)}px)", css)


# ---------------------------------------------------------------- brands (theme.from)
BRAND_ROLES = ("bg", "bg2", "ink", "accent", "accent2", "accent_ink")


def _hls_rgb(h: float, l: float, s: float) -> tuple:
    return tuple(v * 255 for v in colorsys.hls_to_rgb(h, l, s))


def brand_palette(given: dict, mode: Optional[str] = None) -> tuple[dict, str]:
    """A complete colour set from whatever a brand gives (an accent at least), held to the presets' contrast rules:
    ink on bg 7:1, on bg2 4.5:1, button text on the accent 4.5:1. Given colours are kept where they pass; the rest are
    built around the accent's hue. `mode` forces light or dark (a style that requires one)."""
    g = {k: _rgb(v) for k, v in given.items() if k in BRAND_ROLES}
    accent = g.get("accent") or g.get("accent2") or g.get("ink") or _rgb("#1d5fd1")
    if mode is None:
        if "bg" in g:
            mode = "dark" if _lum(g["bg"]) < (_lum(g["ink"]) if "ink" in g else 0.18) else "light"
        else:
            mode = "light"
    bg, ink, bg2 = g.get("bg"), g.get("ink"), g.get("bg2")
    if not (bg and ink and (_lum(bg) < _lum(ink)) == (mode == "dark") and contrast(ink, bg) >= 7):
        h, _, s = colorsys.rgb_to_hls(*(v / 255 for v in accent))      # surfaces and ink tinted with the brand's hue
        if mode == "light":
            bg, ink = _hls_rgb(h, 0.965, min(s, 0.35)), _hls_rgb(h, 0.11, min(s, 0.3))
        else:
            bg, ink = _hls_rgb(h, 0.045, min(s, 0.4)), _hls_rgb(h, 0.95, min(s, 0.25))
        bg2 = None
    if bg2 is None or contrast(ink, bg2) < SMALL_TEXT or (_lum(bg2) < _lum(ink)) != (mode == "dark"):
        bg2 = _mix(ink, bg, 0.05)
    accent2 = g.get("accent2")
    if accent2 is None:                                                 # a lighter accent
        h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in accent))
        accent2 = _hls_rgb(h, min(0.8, l + 0.18), s)
    accent_ink = g.get("accent_ink")
    if accent_ink is None or contrast(accent_ink, accent) < SMALL_TEXT:
        accent_ink = _on(accent, ink, bg)
    cols = dict(zip(BRAND_ROLES, (bg, bg2, ink, accent, accent2, accent_ink)))
    return {k: _css_rgb(v) for k, v in cols.items()}, mode


def _on(colour, ink, bg) -> tuple:
    """The text colour that reads best on a filled colour (a button)."""
    return max((ink, bg, (255.0, 255.0, 255.0), (0.0, 0.0, 0.0)), key=lambda c: contrast(c, colour))


def brand_layer(brand: dict, style: Optional[str]) -> dict:
    """The brand as the token set laid over the style. A style's `requires` (style.yaml) wins over the brand: a style
    that needs a dark room gets the brand's palette rebuilt dark around its accents, and keeps its own fonts where they
    are the mechanic. Under a style the accents are also held to the style's own pairings (accent_partners)."""
    req = styles()[style].get("requires", {}) if style else {}
    out = {k: brand[k] for k in ("fonts", "radius") if brand.get(k)}
    if brand.get("colors"):
        colors, mode = brand_palette(brand["colors"], req.get("mode") or brand.get("mode"))
        if style:
            c = {k: _rgb(v) for k, v in colors.items()}
            for role, partners in accent_partners(style, colors).items():
                c[role] = _hold(c[role], partners)
            if contrast(c["accent_ink"], c["accent"]) < SMALL_TEXT:
                c["accent_ink"] = _on(c["accent"], c["ink"], c["bg"])
            colors = {k: _css_rgb(v) for k, v in c.items()}
        out.update(colors=colors, mode=mode)
    return layer(out, req)


def accent_partners(style: str, colors: dict) -> dict:
    """What each accent must stand against when a brand recolours this style: the colours the style's own accent
    clears 3:1 or more against (its background, its button text), as the page draws them with the brand, each to the
    style's own ratio up to 7:1. A style that sets black words on a pastel accent keeps a pastel accent; one that sets
    a gold accent on black keeps a bright one."""
    sc = {k: _rgb(v) for k, v in styles()[style].get("colors", {}).items() if HEX.fullmatch(str(v))}
    out: dict = {}
    for role in ("accent", "accent2"):
        partners = []
        for other in ("bg", "accent_ink"):
            r = contrast(sc[role], sc[other])
            # the partner as drawn: a palette colour the skin swaps (reskin), else the style's own hex, which stays
            swapped = next((k for k in SKIN_ORDER if k in sc and sc[k] == sc[other] and _css_rgb(sc[k]) not in NEUTRALS), None)
            if r < 3 or swapped in ("accent", "accent2"):
                continue
            partners.append((_rgb(colors[swapped]) if swapped in colors else sc[other], min(r, 7.0)))
        out[role] = partners
    return out


def _hold(col: tuple, partners: list) -> tuple:
    """The colour nearest `col`, mixed toward black or white, that clears every (colour, ratio) partner; the closest
    miss when none does."""
    def score(c):
        return min((contrast(c, p) / t for p, t in partners), default=1.0)
    tries = [_mix(end, col, k / 50) for k in range(51) for end in ((0.0, 0.0, 0.0), (255.0, 255.0, 255.0))]
    return next((c for c in tries if score(c) >= 1), max(tries, key=score))


# accent_ink is left out: a style's button text is usually plain black, white or its background, which the brand's
# accents are held to (accent_partners)
SKIN_ORDER = ("bg", "ink", "accent", "accent2", "bg2", "accent_text", "ink2", "ink3", "line")
NEUTRALS = ("#000000", "#ffffff")     # every stylesheet's black and white, never only the palette's
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"(rgba?\(\s*)(\d{1,3})(\s*,\s*)(\d{1,3})(\s*,\s*)(\d{1,3})\b")


def _hex6(h: str) -> str:
    h = h.lstrip("#").lower()
    return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)


def skin(style: str, colors: dict, fonts: dict) -> dict:
    """What a brand changes in a style's own stylesheet: each colour of the style's palette (style.yaml) and each of its
    display/body/mono families, mapped to the theme's. Most styles write their palette into style.css directly, so this
    is how a brand reaches them; everything else in the stylesheet (the style's mechanics) stays as it is."""
    st = styles()[style]
    final = dict(colors)
    final.setdefault("accent_text", _css_rgb(_readable_accent(_rgb(colors["accent"]), _rgb(colors["ink"]),
                                                              [_rgb(colors["bg"]), _rgb(colors["bg2"])], SMALL_TEXT)))
    cmap: dict = {}
    for role in SKIN_ORDER:            # a hex the style uses for two roles goes with the first (bg before accent)
        old, new = st.get("colors", {}).get(role), final.get(role)
        if old and new and HEX.fullmatch(str(old)) and HEX.fullmatch(str(new)) and _hex6(old) not in NEUTRALS:
            cmap.setdefault(_hex6(old), _hex6(new))
    fmap: dict = {}
    for role in ("display", "body", "mono"):
        old, new = st.get("fonts", {}).get(role), fonts.get(role)
        if old and new:
            fmap.setdefault(old, new)
    return {"colors": {k: v for k, v in cmap.items() if k != v}, "fonts": {k: v for k, v in fmap.items() if k != v}}


def reskin(css: str, sk: Optional[dict]) -> str:
    """A style's stylesheet in the brand's colours and fonts (see skin), in one pass so no colour is swapped twice."""
    if not sk:
        return css
    cmap = sk["colors"]
    rgb = {tuple(int(o[i:i + 2], 16) for i in (1, 3, 5)): tuple(int(n[i:i + 2], 16) for i in (1, 3, 5))
           for o, n in cmap.items()}

    def swap_rgb(m: re.Match) -> str:
        new = rgb.get((int(m.group(2)), int(m.group(4)), int(m.group(6))))
        return m.group(0) if new is None else f"{m.group(1)}{new[0]}{m.group(3)}{new[1]}{m.group(5)}{new[2]}"
    css = HEX.sub(lambda m: cmap.get(_hex6(m.group(0)), m.group(0)), css)
    css = RGB.sub(swap_rgb, css)
    for old, new in sk["fonts"].items():
        css = re.sub(r"([\"'])" + re.escape(old) + r"\1", f'"{new}"', css)
    return css


def font_links(t: dict) -> list[str]:
    seen, links = {f["family"] for f in t.get("font_files", [])}, []      # the project's own files are not on Google
    for fam in t["fonts"].values():
        if fam in seen:
            continue
        seen.add(fam)
        axes = t.get("font_axes", {}).get(fam, FONT_AXES.get(fam, "wght@400;700"))
        links.append(f"https://fonts.googleapis.com/css2?family={quote_plus(fam)}{':' + axes if axes else ''}&display=swap")
    return links
