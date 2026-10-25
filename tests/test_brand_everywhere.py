"""A brand reaches every part of a style (issue #125): not only its stylesheet (themes.reskin) but the colours its templates
write into the markup and the colours its runtime draws in canvas, SVG and WebGL.

- templates: a style's .j2 files are read through the same colour swap as its stylesheet when the theme wears a brand;
- runtime: the compiler sets --skin-<role> on the page for each role of the style's palette the brand re-colours, and the
  runtime reads it (`skin` in runtime/src/styles/_kit.ts) with the style's own colour as the value when there is none;
- with no brand nothing changes: no --skin-* variable, templates read as written.
No GPU, no browser."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.compile import themes as T
from engine.compile.layout_snapshot import page_html
from test_conformance import kitchen_sink

ROOT = Path(__file__).resolve().parent.parent
STYLES_TS = ROOT / "runtime" / "src" / "styles"
DARK = {"mode": "dark", "colors": {"bg": "#0d1117", "ink": "#e6edf3", "accent": "#2ea043", "accent2": "#a371f7"}}
LIGHT = {"colors": {"bg": "#fbfaf7", "ink": "#1b1b1f", "accent": "#0057b8", "accent2": "#f2a541"}}


def brand_for(style: str) -> dict:
    return DARK if T.styles()[style].get("requires", {}).get("mode") == "dark" else LIGHT


# ---------------------------------------------------------------- the page says what the brand changed

def test_a_brand_sets_a_variable_for_each_palette_role_it_recolours():
    t = T.resolve(kitchen_sink("bauhaus", LIGHT).theme)
    roles, own = t["skin"]["roles"], T.styles()["bauhaus"]["colors"]
    for role in ("bg", "bg2", "ink", "accent", "accent2"):        # each as the theme has it, which is what the stylesheet is swapped to
        assert roles[role] == t["colors"][role] != own[role]
    assert roles["accent"] == "#0057b8" and roles["bg"] == "#fbfaf7"
    css = T.css_vars(t)
    assert f"--skin-accent: {roles['accent']};" in css and f"--skin-accent2: {roles['accent2']};" in css
    assert "--skin-accent-text:" in css                                   # accent_text is written with a hyphen, like every CSS variable


@pytest.mark.parametrize("style", sorted(T.styles()))
def test_a_page_with_no_brand_sets_no_skin_variable(style):
    css = T.css_vars(T.resolve(kitchen_sink(style).theme))
    assert "--skin-" not in css


def test_a_role_the_brand_leaves_as_it_was_has_no_variable():
    own = T.styles()["bauhaus"]["colors"]
    brand = {"colors": {"accent": own["accent"], "accent2": "#f2a541"}}
    t = T.resolve(kitchen_sink("bauhaus", brand).theme)
    assert "accent" not in t["skin"]["roles"] and t["skin"]["roles"]["accent2"] == t["colors"]["accent2"]


# ---------------------------------------------------------------- templates

@pytest.mark.parametrize("style,old", [("neon-glow", "#ff2a6d"), ("neon-glow", "#05d9e8"), ("clay-3d", "#9d86ff"),
                                       ("comic-book", "#e8262b"), ("comic-book", "#1b4f9c"), ("halftone", "#ec008c"),
                                       ("halftone", "#00aeef")])
def test_a_style_wearing_a_brand_has_its_templates_in_the_brands_colours(style, old):
    sources = "".join(p.read_text(encoding="utf-8").lower() for p in (ROOT / "engine" / "styles" / style).glob("*.j2"))
    assert old in sources, f"{style}: {old} is no longer in its templates (update this test)"
    assert old in page_html(kitchen_sink(style)).lower()               # no brand: the markup is as written
    site = kitchen_sink(style, brand_for(style))
    t = T.resolve(site.theme)
    new = t["skin"]["colors"][old]
    html = page_html(site).lower()
    assert old not in html, f"{style}: {old} is still in the page"
    assert new in html, f"{style}: {new} (the brand's) is not in the page"


def test_templates_are_read_as_written_with_no_brand():
    from engine.compile.compiler import _env
    for style in T.styles():
        env = _env(T.style_dir(style))
        for f in ("blocks.html.j2", "chrome.html.j2", "scenes.html.j2"):
            p = T.style_dir(style) / f
            if p.exists():
                assert env.loader.get_source(env, f"style/{f}")[0].rstrip() == p.read_text(encoding="utf-8").rstrip()


# ---------------------------------------------------------------- the runtime reads the palette it is given

CALL = re.compile(r"\bskin(?:Rgb|Rgba|Num)?\(\s*\"(\w+)\"\s*,\s*(?:\"(#[0-9a-fA-F]{6})\"|0x([0-9a-fA-F]{6}))")
WEAR = re.compile(r"\bwear\(\s*\"(\w+)\"\s*,\s*\[[^\]]*\"(#[0-9a-fA-F]{6})\"\s*\]")
OWNER = {"_film-draw": "scratch-film", "_flipbook-draw": "flipbook"}


def owner(stem: str) -> str:
    """The style a module draws for: its own name, or the style a helper module (_film-draw...) belongs to."""
    return OWNER.get(stem) or ("zoetrope" if stem.startswith("_zoetrope") else stem)


def calls() -> list[tuple[str, str, str, str]]:
    out = []
    for f in sorted(STYLES_TS.glob("*.ts")):
        if f.stem == "_kit":
            continue
        text = f.read_text(encoding="utf-8")
        for m in CALL.finditer(text):
            out.append((f.stem, m.group(1), (m.group(2) or "#" + m.group(3)).lower(), m.group(0)))
        for m in WEAR.finditer(text):
            out.append((f.stem, m.group(1), m.group(2).lower(), m.group(0)))
    return out


def test_the_styles_that_read_a_brand_are_found():
    assert {c[0] for c in calls()} >= {"bauhaus", "neon-glow", "wireframe-3d", "zoetrope", "_zoetrope-figures", "_film-draw"}


@pytest.mark.parametrize("module,role,own", sorted({c[:3] for c in calls()}))
def test_what_a_style_reads_is_a_role_of_its_own_palette_in_its_own_colour(module, role, own):
    """`skin("accent", "#be1e2d")`: the role is one of the style's palette (style.yaml) and the colour is that role's, or,
    for a colour drawn a shade off the palette (a print's red), close to it. A colour that is exactly another role's is a mixup."""
    name = owner(module)
    palette = T.styles()[name]["colors"]
    assert role in palette, f"{module}: {role!r} is not in {name}'s style.yaml colors ({sorted(palette)})"
    rgb = T._rgb(own)
    off = max(abs(a - b) for a, b in zip(rgb, T._rgb(palette[role])))
    assert off <= 40, f"{module}: skin({role!r}, {own}) but {name}'s {role} is {palette[role]}"
    exact = [r for r, c in palette.items() if str(c).lower() == own and r != role]
    assert not exact or palette[role].lower() == own, f"{module}: {own} is {name}'s {exact[0]}, not its {role}"
