"""Theme presets -> CSS custom properties and Google Fonts links."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import yaml

from ..spec import Theme

THEMES_FILE = Path(__file__).resolve().parent.parent / "themes.yaml"

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
    "Newsreader": "ital,opsz,wght@0,6..72,200..800;1,6..72,200..800",
}
FALLBACK = {"display": "system-ui, sans-serif", "body": "system-ui, sans-serif", "mono": "ui-monospace, monospace"}
SERIFS = {"Instrument Serif", "Fraunces", "Cormorant Garamond", "Newsreader"}


@lru_cache(maxsize=1)
def presets() -> dict:
    with open(THEMES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _hex_rgb(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def resolve(theme: Theme) -> dict:
    base = presets().get(theme.preset)
    if base is None:
        raise ValueError(f"unknown theme preset '{theme.preset}' (have: {', '.join(presets())})")
    colors = dict(base["colors"], **theme.colors)
    fonts = dict(base["fonts"], **theme.fonts)
    return {
        "mode": base.get("mode", "dark"),
        "colors": colors,
        "fonts": fonts,
        "display_weight": theme.display_weight or base.get("display_weight", 500),
        "em_italic": base.get("em_italic", False) if theme.display_italic_em is None else theme.display_italic_em,
        "radius": theme.radius or base.get("radius", "4px"),
    }


def css_vars(t: dict) -> str:
    c, f = t["colors"], t["fonts"]
    ink = _hex_rgb(c["ink"])
    tokens = {
        "--bg": c["bg"], "--bg-2": c["bg2"], "--ink": c["ink"],
        "--ink-rgb": ink, "--bg-rgb": _hex_rgb(c["bg"]),
        "--ink-2": c.get("ink2", f"rgba({ink}, .68)"), "--ink-3": c.get("ink3", f"rgba({ink}, .44)"),
        "--line": c.get("line", f"rgba({ink}, .13)"),
        "--accent": c["accent"], "--accent-2": c["accent2"], "--accent-ink": c["accent_ink"],
        "--accent-rgb": _hex_rgb(c["accent"]),
        "--font-display": f'"{f["display"]}", {"Georgia, serif" if f["display"] in SERIFS else FALLBACK["display"]}',
        "--font-body": f'"{f["body"]}", {"Georgia, serif" if f["body"] in SERIFS else FALLBACK["body"]}',
        "--font-mono": f'"{f["mono"]}", {FALLBACK["mono"]}',
        "--display-weight": str(t["display_weight"]),
        "--em-style": "italic" if t["em_italic"] else "normal",
        "--radius": t["radius"],
        "color-scheme": t["mode"],
    }
    return ":root {\n" + "\n".join(f"  {k}: {v};" for k, v in tokens.items()) + "\n}"


def font_links(t: dict) -> list[str]:
    seen, links = set(), []
    for fam in t["fonts"].values():
        if fam in seen:
            continue
        seen.add(fam)
        axes = FONT_AXES.get(fam, "wght@400;700")
        links.append(f"https://fonts.googleapis.com/css2?family={quote_plus(fam)}:{axes}&display=swap")
    return links
