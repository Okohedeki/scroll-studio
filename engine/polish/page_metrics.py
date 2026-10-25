"""Measurements and rules for the page polish report (`studio inspect --page`), with no browser in them.

The browser side (page.py) loads the built page and hands over facts: where each line of text sits, the pixels behind it
with the text hidden, how big each picture is on screen. Everything here turns those facts into numbers and findings, so
it is tested on pictures drawn with PIL and on made-up facts.

A finding is a dict: severity (`fail` | `warn`), check, section, viewport, what (with the numbers), fix (in the engine's
terms), and where on the screenshot it is (`shot`, `box` in CSS pixels) so the contact sheet can mark it.
"""
from __future__ import annotations

import statistics
from typing import Optional

import cv2
import numpy as np

# ---- thresholds: one place, named, so the report and the docs say the same numbers
BUSY_WARN = 60                 # busy-ness (0-100) of the picture behind text at which text is hard to place
CONTRAST_NORMAL, CONTRAST_LARGE = 4.5, 3.0     # WCAG AA for text under 24 px (or 18.66 px bold) and for larger text
LARGE_PX, LARGE_BOLD_PX = 24.0, 18.66
SCRIM_RAW_MAX = 3.0            # a scrim does the work when the picture alone is below this and the page passes with it
SCRIM_MIN_SHIFT = 0.10         # ... and the scrim moved the backdrop's luminance by at least this much (0-1)
LINE_WIDE, LINE_NARROW = 80, 35               # characters per line of body copy
HEADLINE_LINES_WARN, HEADLINE_LINES_FAIL = 5, 7   # lines of a headline on a phone
RATIO_WEAK = 1.6               # headline size / body size under this: the hierarchy is flat
UPSCALE_WARN, UPSCALE_FAIL = 1.3, 2.0         # pixels the screen needs per pixel the picture has
FACE_CUT_MIN, FACE_CUT_MAX = 0.05, 0.95       # share of a face inside the frame that counts as "cut by the edge"
OVERLAP_MIN = 0.25             # share of the smaller line box two lines of text must cover each other to be flagged


# ---------------------------------------------------------------- colour

def _linear(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb) -> np.ndarray:
    """WCAG relative luminance (0 black, 1 white) of an (..., 3) array of sRGB values 0-255."""
    lin = _linear(rgb)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def ratio(a, b):
    """WCAG contrast ratio of two relative luminances (arrays or numbers), 1 to 21."""
    hi, lo = np.maximum(a, b), np.minimum(a, b)
    return (hi + 0.05) / (lo + 0.05)


def needed_contrast(size_px: float, weight: int = 400) -> float:
    return CONTRAST_LARGE if size_px >= LARGE_PX or (size_px >= LARGE_BOLD_PX and weight >= 700) else CONTRAST_NORMAL


def text_contrast(backdrop: np.ndarray, color, alpha: float = 1.0) -> dict:
    """Contrast of text colour `color` (r, g, b; `alpha` its opacity as drawn) against the pixels behind it (an HxWx3
    uint8 array, the page with the text hidden). `typical` is against the backdrop's median pixel; `worst` is what the
    worst tenth of the pixels give (the bright patch under one word). The text is blended over each pixel by its alpha,
    as the browser draws it."""
    px = backdrop.reshape(-1, 3).astype(np.float32)
    fg = np.asarray(color, np.float32)
    drawn = alpha * fg + (1 - alpha) * px
    per_pixel = ratio(luminance(drawn), luminance(px))
    med = np.median(px, axis=0)
    typical = float(ratio(luminance(alpha * fg + (1 - alpha) * med), luminance(med)))
    return {"typical": round(typical, 2), "worst": round(float(np.percentile(per_pixel, 10)), 2),
            "backdrop_lum": round(float(luminance(med)), 3)}


# ---------------------------------------------------------------- busy-ness

def busyness(rgb: np.ndarray) -> dict:
    """How busy a picture is where text would sit. `edge` is the share of pixels on an edge (a gradient of more than 6
    grey levels a pixel, after a 1 px blur that ignores grain); `detail` is the spread of what is left once the slow
    changes (a sky's gradient, a vignette) are taken out, in grey levels. `score` 0-100 mixes the two: 0 a flat or gently
    graded surface, 100 foliage, a crowd, a pattern."""
    g = cv2.cvtColor(np.ascontiguousarray(rgb, dtype=np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    if min(g.shape) < 4:
        return {"edge": 0.0, "detail": 0.0, "score": 0}
    b = cv2.GaussianBlur(g, (0, 0), 1.0)
    mag = np.hypot(cv2.Sobel(b, cv2.CV_32F, 1, 0, ksize=3) / 8.0, cv2.Sobel(b, cv2.CV_32F, 0, 1, ksize=3) / 8.0)
    edge = float((mag > 6.0).mean())
    detail = float((g - cv2.GaussianBlur(g, (0, 0), 5.0)).std())
    score = 100 * (0.5 * min(1.0, edge / 0.15) + 0.5 * min(1.0, detail / 12.0))
    return {"edge": round(edge, 3), "detail": round(detail, 1), "score": int(round(score))}


def calmest_side(rgb: np.ndarray, rows: tuple[int, int]) -> dict:
    """Busy-ness of the left, centre and right thirds of a screenshot, over the rows a caption sits in: where a caption
    would be easier to read."""
    h, w = rgb.shape[:2]
    y0, y1 = max(0, rows[0]), min(h, max(rows[1], rows[0] + 8))
    return {name: busyness(rgb[y0:y1, int(w * a):int(w * b)])["score"]
            for name, (a, b) in {"left": (0.0, 1 / 3), "center": (1 / 3, 2 / 3), "right": (2 / 3, 1.0)}.items()}


# ---------------------------------------------------------------- type

def line_length(chars_per_line: list[int]) -> Optional[int]:
    """Characters in a typical full line of a paragraph: the mean of every line but the last (which is short). None for a
    paragraph of fewer than two lines: it has no measure."""
    if len(chars_per_line) < 2:
        return None
    return int(round(statistics.fmean(chars_per_line[:-1])))


def type_ratio(headline_px: float, body_px: float) -> float:
    return round(headline_px / body_px, 2) if body_px else 0.0


# ---------------------------------------------------------------- pictures

def upscale(natural: tuple[int, int], box: tuple[float, float], dpr: float, fit: str = "cover") -> float:
    """How many screen pixels each pixel of the picture has to cover: 1 is exact, 2 is blown up to twice the size. `box` is
    the picture's box on screen in CSS pixels, `fit` how the picture sits in it (cover, contain, fill, none)."""
    nw, nh = max(natural[0], 1), max(natural[1], 1)
    sx, sy = box[0] / nw, box[1] / nh
    scale = {"contain": min(sx, sy), "scale-down": min(sx, sy, 1 / dpr), "none": 1 / dpr}.get(fit, max(sx, sy))
    return round(scale * dpr, 2)


def crop_window(natural: tuple[int, int], box: tuple[float, float], fit: str, position: tuple[float, float]) -> tuple[float, float, float, float]:
    """The part of a picture a box shows, as (x0, y0, x1, y1) in 0-1 of the picture. Only `cover` crops."""
    nw, nh = max(natural[0], 1), max(natural[1], 1)
    if fit != "cover" or box[0] <= 0 or box[1] <= 0:
        return (0.0, 0.0, 1.0, 1.0)
    s = max(box[0] / nw, box[1] / nh)
    vw, vh = min(1.0, box[0] / s / nw), min(1.0, box[1] / s / nh)
    x0, y0 = (1 - vw) * position[0], (1 - vh) * position[1]
    return (x0, y0, x0 + vw, y0 + vh)


def face_in_frame(face: tuple[float, float, float, float], window: tuple[float, float, float, float]) -> float:
    """Share (0-1) of a face box (x0, y0, x1, y1 in 0-1 of the picture) that lies inside the part the page shows."""
    ax0, ay0, ax1, ay1 = face
    bx0, by0, bx1, by1 = window
    w, h = min(ax1, bx1) - max(ax0, bx0), min(ay1, by1) - max(ay0, by0)
    area = (ax1 - ax0) * (ay1 - ay0)
    return max(0.0, w) * max(0.0, h) / area if area > 0 else 1.0


def face_overlap(face: tuple[float, float, float, float], box: tuple[float, float, float, float]) -> float:
    """Share (0-1) of a face box that a box of text covers (both x0, y0, x1, y1 in the same units)."""
    w, h = min(face[2], box[2]) - max(face[0], box[0]), min(face[3], box[3]) - max(face[1], box[1])
    area = (face[2] - face[0]) * (face[3] - face[1])
    return max(0.0, w) * max(0.0, h) / area if area > 0 else 0.0


def overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Share of the smaller of two boxes (x0, y0, x1, y1) that the other covers."""
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    if w <= 1 or h <= 1:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / small if small > 0 else 0.0


# ---------------------------------------------------------------- findings

def finding(severity: str, check: str, section: str, viewport: str, what: str, fix: str, shot: Optional[int] = None,
            box: Optional[list[float]] = None, subject: Optional[str] = None) -> dict:
    """`subject` names the thing found (a headline, a picture): the same thing seen at two stops is one finding."""
    return {"severity": severity, "check": check, "section": section, "viewport": viewport, "what": what, "fix": fix,
            "shot": shot, "box": [round(v) for v in box] if box else None, "subject": subject or what[:60]}


def _quote(text: str, n: int = 38) -> str:
    text = " ".join(text.split())
    return '"' + (text if len(text) <= n else text[:n - 3].rstrip() + "...") + '"'


def text_findings(t: dict) -> list[dict]:
    """Findings for one piece of text over a picture. `t`: text, role, size, weight, caption (a scene caption or step),
    hero, section, viewport, shot, box, busy (score), contrast {typical, worst}, raw {typical, worst, shift} (the
    picture with its scrims hidden, when it has any), calm {left, center, right}, side (where the text sits now)."""
    out = []
    need = needed_contrast(t["size"], t.get("weight", 400))
    c = t["contrast"]
    where = dict(section=t["section"], viewport=t["viewport"], shot=t.get("shot"), box=t.get("box"))
    name = f"{t['role']} {_quote(t['text'])}"
    fix = _contrast_fix(t, need)

    def add(sev, check, what, fx=fix):
        out.append(finding(sev, check, what=what, fix=fx, subject=name, **where))
    if c["typical"] < need * 0.9:
        add("fail", "contrast", f"{name} has {c['typical']}:1 against the picture behind it (needs {need:g}:1)")
    elif c["typical"] < need:
        add("warn", "contrast", f"{name} has {c['typical']}:1 against the picture behind it, just under the {need:g}:1 it needs")
    elif c["worst"] < need * 0.8:
        add("warn", "contrast", f"{name} passes on most of the picture ({c['typical']}:1) but only {c['worst']}:1 on its "
                                 f"brightest or darkest tenth (needs {need:g}:1)")
    raw = t.get("raw")
    if raw and c["typical"] >= need and raw["typical"] < SCRIM_RAW_MAX and raw["shift"] >= SCRIM_MIN_SHIFT:
        add("warn", "scrim", f"{name} reads only because of the scrim: {c['typical']}:1 with it, {raw['typical']}:1 on the "
                              f"picture alone (the scrim moves the backdrop's brightness by {round(raw['shift'] * 100)}%)")
    if t["busy"] >= BUSY_WARN and t["role"] != "cta":
        add("warn", "busy", f"{name} sits on a busy part of the picture (busy-ness {t['busy']} of 100, flag from {BUSY_WARN})")
    return out


def _contrast_fix(t: dict, need: float) -> str:
    calm, side = t.get("calm") or {}, t.get("side", "left")
    better = min((s for s in ("left", "right") if s != side), key=lambda s: calm.get(s, 100), default=None)
    ok = better and calm.get(better, 100) + 15 <= t["busy"]
    if t["section"] == "nav":
        return ("the nav's words sit straight on the picture at the top of the page: regenerate that picture with a calm, "
                "darker top edge, or start the page with a section whose `surface:` suits the picture")
    if t.get("caption"):
        bits = []
        if ok:
            bits.append(f"move the caption to the calm side with `place: {better}` ({better} third busy-ness "
                        f"{calm[better]}, here {t['busy']})")
        bits.append("give the step `surface: dark` (or `light`) for a soft glow behind the words, or set the scene "
                    "`shade: strong`")
        bits.append("or regenerate the shot with calm space where the words sit")
        return "; ".join(bits)
    if t.get("hero"):
        note = ""
        if ok:
            note = f" (the {better} third is calmer: busy-ness {calm[better]}, here {t['busy']}"
            note += "; `align: left` puts the copy there)" if better == "left" else ")"
        return (f"regenerate the picture with calm space behind the copy{note}, or set the section `surface: dark` "
                "(or `light`) so the words take the colour that fits the picture")
    return ("regenerate the picture with calm space behind the words, set the section `surface: dark` (or `light`), or "
            "move the words off the picture")


def type_findings(section: str, viewport: str, headline_px: Optional[float], body_px: Optional[float], bodies: list[dict],
                  headlines: list[dict]) -> list[dict]:
    """Findings from a section's type: the ratio of headline to body size, the line length of each paragraph, and (for
    phones) how many lines each headline runs to. `bodies` / `headlines`: {text, lines (chars per line), nlines, shot, box}."""
    out = []
    if headline_px and body_px and type_ratio(headline_px, body_px) < RATIO_WEAK:
        out.append(finding("warn", "hierarchy", section, viewport,
                           f"the headline ({headline_px:g} px) is only {type_ratio(headline_px, body_px)}x the body "
                           f"({body_px:g} px): the hierarchy is flat (flag under {RATIO_WEAK}x)",
                           "raise `theme.type.scale` (headlines) or lower `theme.type.body`, or make the headline shorter"))
    for b in bodies:
        n = line_length(b["lines"])
        if n is None:
            continue
        if n > LINE_WIDE:
            out.append(finding("warn", "line-length", section, viewport,
                               f"{_quote(b['text'])} runs {n} characters a line (flag over {LINE_WIDE})",
                               "break the copy into two shorter paragraphs, or give it a narrower column: "
                               "`layout: split` on a scene, `side:` on a product block, or a smaller `theme.space.max`",
                               b.get("shot"), b.get("box")))
        elif n < LINE_NARROW and b["nlines"] >= 4:
            out.append(finding("warn", "line-length", section, viewport,
                               f"{_quote(b['text'])} runs {n} characters a line over {b['nlines']} lines (flag under {LINE_NARROW})",
                               "give the copy a wider column (`theme.space.caption` for scene captions) or cut it down",
                               b.get("shot"), b.get("box")))
    if viewport == "phone":
        for h in headlines:
            if h["nlines"] > HEADLINE_LINES_WARN:
                sev = "fail" if h["nlines"] > HEADLINE_LINES_FAIL else "warn"
                out.append(finding(sev, "headline-lines", section, viewport,
                                   f"the headline {_quote(h['text'])} takes {h['nlines']} lines on a phone (flag over {HEADLINE_LINES_WARN})",
                                   "shorten the headline, or lower `theme.type.scale`", h.get("shot"), h.get("box")))
    return out


def image_findings(im: dict) -> list[dict]:
    """`im`: src, section, viewport, natural (w, h), box (w, h on screen), dpr, fit, shot; face: share of a face inside the
    frame (None when no face was found)."""
    out = []
    u = upscale(tuple(im["natural"]), tuple(im["box"]), im["dpr"], im["fit"])
    if u > UPSCALE_WARN:
        need_w = int(round(im["natural"][0] * u, -1))
        sev = "fail" if u > UPSCALE_FAIL else "warn"
        x0, y0, x1, y1 = crop_window(tuple(im["natural"]), tuple(im["box"]), im["fit"], (0.5, 0.5))
        shows = min(x1 - x0, y1 - y0)
        shape = (f"; or use a picture shaped for this screen (here the frame shows only {round(shows * 100)}% of the "
                 f"picture's {'width' if x1 - x0 < y1 - y0 else 'height'})" if shows < 0.75 else "")
        out.append(finding(sev, "upscaled", im["section"], im["viewport"],
                           f"{im['src']} is {im['natural'][0]}x{im['natural'][1]} px but is drawn {round(im['box'][0])}x"
                           f"{round(im['box'][1])} css px at {im['dpr']:g}x: blown up {u}x (flag over {UPSCALE_WARN}x)",
                           f"use a larger source image: about {need_w} px wide here (a `generate:` image takes `size: "
                           f"[{need_w}, {int(round(im['natural'][1] * u, -1))}]`, a file needs the bigger original){shape}",
                           im.get("shot"), im.get("rect")))
    f = im.get("face")
    if f is not None and FACE_CUT_MIN < f < FACE_CUT_MAX:
        out.append(finding("warn", "face-cut", im["section"], im["viewport"],
                           f"{im['src']}: a face is cut by the frame edge, {round(f * 100)}% of it shows at {im['viewport']} size",
                           "regenerate the picture with the subject nearer the centre, or crop it first with `crop: [x0, y0, x1, y1]`",
                           im.get("shot"), im.get("rect")))
    return out


def layout_findings(section: str, viewport: str, shot: Optional[int], overflow: Optional[dict], cta: Optional[dict],
                    overlaps: list[dict]) -> list[dict]:
    """Findings from the layout facts of a section: `overflow` {px, culprits}, the hero's first button `cta` {label, top,
    bottom, fold}, and pairs of text boxes that cover each other (`overlaps`: {a, b, share, box})."""
    out = []
    if overflow:
        cul = ", ".join(overflow["culprits"][:3]) or "unknown element"
        out.append(finding("fail", "overflow", section, viewport,
                           f"the page is {overflow['px']} px wider than the {viewport} screen (widest: {cul})",
                           "find the element that runs off the edge (named above) and give it `max-width: 100%`, or shorten "
                           "its text; a media or table block takes `overflow: hidden` on its wrapper", shot))
    if cta and cta["bottom"] > cta["fold"]:
        below = cta["top"] >= cta["fold"]
        out.append(finding("fail" if below else "warn", "cta-fold", section, viewport,
                           f"the hero button {_quote(cta['label'], 24)} is {'below the fold' if below else 'cut by the fold'} on a "
                           f"{viewport}: it spans y={round(cta['top'])}-{round(cta['bottom'])} on a {round(cta['fold'])} px screen",
                           "shorten the hero's title or body, or drop a second button, so the first button sits above the fold",
                           shot, cta.get("box")))
    for o in overlaps:
        out.append(finding("fail", "overlap", section, viewport,
                           f"{_quote(o['a'], 28)} and {_quote(o['b'], 28)} overlap ({round(o['share'] * 100)}% of the smaller box)",
                           "move one of them: change `place:` on the caption, shorten the copy, or give the section more length",
                           shot, o.get("box")))
    return out


def verdict(findings: list[dict]) -> str:
    return "fail" if any(f["severity"] == "fail" for f in findings) else "warn" if findings else "clean"
