"""Theme presets -> CSS custom properties and Google Fonts links."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import yaml

from ..spec import Theme

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
FALLBACK = {"display": "system-ui, sans-serif", "body": "system-ui, sans-serif", "mono": "ui-monospace, monospace"}
SERIFS = {"Instrument Serif", "Fraunces", "Cormorant Garamond", "Newsreader"}


@lru_cache(maxsize=1)
def presets() -> dict:
    with open(THEMES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def styles() -> dict:
    """Every engine/styles/<name>/style.yaml, by name (label, about, mode, colors, fonts, font_axes, radius, fx...)."""
    out = {}
    for f in sorted(STYLES_DIR.glob("*/style.yaml")):
        with open(f, encoding="utf-8") as fh:
            out[f.parent.name] = yaml.safe_load(fh)
    return out


def style_dir(name: str) -> Path:
    """engine/styles/<name>/: style.css, and optionally blocks.html.j2 (its own markup for some block types),
    chrome.html.j2 (page furniture around the sections) and scenes.html.j2."""
    return STYLES_DIR / name


def style_css(name: str) -> str:
    return (style_dir(name) / "style.css").read_text(encoding="utf-8")


def _hex_rgb(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def resolve(theme: Theme) -> dict:
    base = presets().get(theme.preset)
    if base is None:
        raise ValueError(f"unknown theme preset '{theme.preset}' (have: {', '.join(presets())})")
    st = {}
    if theme.style:
        st = styles().get(theme.style)
        if st is None:
            raise ValueError(f"unknown style '{theme.style}' (have: {', '.join(styles())})")
        # the style's look goes over the preset; anything site.yaml sets still wins
        base = dict(base, **{k: v for k, v in st.items() if k in ("mode", "radius", "display_weight", "em_italic", "display_em")},
                    colors=dict(base["colors"], **st.get("colors", {})), fonts=dict(base["fonts"], **st.get("fonts", {})))
    colors = dict(base["colors"], **theme.colors)
    fonts = dict(base["fonts"], **theme.fonts)
    return {
        "style": theme.style,
        "font_axes": st.get("font_axes", {}),
        "fx": st.get("fx", {}),
        "mode": theme.mode or base.get("mode", "dark"),
        "colors": colors,
        "fonts": fonts,
        "display_weight": theme.display_weight or base.get("display_weight", 500),
        "em_italic": base.get("em_italic", False) if theme.display_italic_em is None else theme.display_italic_em,
        "em": theme.display_em or base.get("display_em", "accent"),
        "display_opsz": theme.display_optical_size or base.get("display_optical_size"),
        "radius": theme.radius or base.get("radius", "4px"),
    }


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


def font_links(t: dict) -> list[str]:
    seen, links = set(), []
    for fam in t["fonts"].values():
        if fam in seen:
            continue
        seen.add(fam)
        axes = t.get("font_axes", {}).get(fam, FONT_AXES.get(fam, "wght@400;700"))
        links.append(f"https://fonts.googleapis.com/css2?family={quote_plus(fam)}{':' + axes if axes else ''}&display=swap")
    return links
