"""Conformance: every theme preset and every style keeps the rules in CONTRIBUTING.md and engine/styles/README.md, so a
change to one of them cannot quietly break consistency with the rest. Each check names the file and the rule it broke.
No GPU, no browser: tokens are measured, templates are rendered with stand-ins (engine/compile/layout_snapshot.py)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine import spec
from engine.compile import themes as T
from engine.compile.layout_snapshot import page_html

ROOT = Path(__file__).resolve().parent.parent
STYLES = sorted(T.styles())
PRESETS = sorted(T.presets())
HEX = re.compile(r"#[0-9a-fA-F]{6}")
COLOURS = ("bg", "bg2", "ink", "accent", "accent2", "accent_ink")       # every preset sets them; a style may override any
PRESET_KEYS = {"mode", "colors", "fonts", "display_weight", "em_italic", "radius", "display_em", "labels",
               "display_optical_size"}
STYLE_KEYS = PRESET_KEYS | {"label", "about", "font_axes", "cuts"}
BLOCK_TYPES = {m.model_fields["type"].default for m in vars(spec).values()
               if isinstance(m, type) and issubclass(m, spec.BlockBase) and "type" in m.model_fields}
BODY, ROLE_TEXT = 7.0, 4.5      # ink on the page: AAA for body copy; buttons and accent text: AA


def ratio(fg: str, bg: str) -> float:
    return round(T.contrast(T._rgb(fg), T._rgb(bg)), 2)


def colour_rules(name: str, mode: str, c: dict) -> list[str]:
    """The colour contract shared by presets and styles: valid hex, the mode matches the colours, and every pairing the
    page draws passes contrast."""
    bad = [f"{k} {c[k]!r} is not a #rrggbb colour" for k in (*COLOURS, "accent_text") if k in c and not HEX.fullmatch(str(c[k]))]
    if bad:
        return bad
    if (mode == "dark") != (T._lum(T._rgb(c["bg"])) < T._lum(T._rgb(c["ink"]))):
        bad.append(f"mode is {mode} but bg {c['bg']} / ink {c['ink']} say otherwise")
    for k in ("bg", "bg2"):
        if ratio(c["ink"], c[k]) < (BODY if k == "bg" else ROLE_TEXT):
            bad.append(f"ink on {k} is {ratio(c['ink'], c[k])}:1 (needs {BODY if k == 'bg' else ROLE_TEXT})")
    if ratio(c["accent_ink"], c["accent"]) < ROLE_TEXT:
        bad.append(f"button text accent_ink on accent is {ratio(c['accent_ink'], c['accent'])}:1 (needs {ROLE_TEXT})")
    if "accent_text" in c and min(ratio(c["accent_text"], c["bg"]), ratio(c["accent_text"], c["bg2"])) < ROLE_TEXT:
        bad.append(f"accent_text {c['accent_text']} is under {ROLE_TEXT}:1 on bg/bg2")
    return bad


# ---------------------------------------------------------------- theme presets (engine/themes.yaml)

@pytest.mark.parametrize("name", PRESETS)
def test_a_preset_has_every_token_and_nothing_unknown(name):
    p = T.presets()[name]
    assert not set(p) - PRESET_KEYS, f"themes.yaml {name}: unknown keys {set(p) - PRESET_KEYS} (allowed: {sorted(PRESET_KEYS)})"
    assert p.get("mode") in ("light", "dark"), f"themes.yaml {name}: mode must be light or dark"
    assert not set(COLOURS) - set(p["colors"]), f"themes.yaml {name}: missing colours {set(COLOURS) - set(p['colors'])}"
    assert {"display", "body", "mono"} <= set(p["fonts"]), f"themes.yaml {name}: fonts need display, body and mono"


@pytest.mark.parametrize("name", PRESETS)
def test_a_preset_is_readable(name):
    p = T.presets()[name]
    assert not colour_rules(name, p["mode"], p["colors"]), f"themes.yaml {name}: " + "; ".join(colour_rules(name, p["mode"], p["colors"]))
    T.css_vars(T.resolve(spec.Theme(preset=name)))           # resolves and writes its tokens


# ---------------------------------------------------------------- styles (engine/styles/<name>/)

@pytest.mark.parametrize("name", STYLES)
def test_a_style_is_a_complete_folder_with_its_runtime(name):
    d = ROOT / "engine" / "styles" / name
    for f in ("style.yaml", "style.css", "blocks.html.j2"):
        assert (d / f).exists(), f"engine/styles/{name}/{f} is missing (see engine/styles/README.md)"
    assert (ROOT / "runtime" / "src" / "styles" / f"{name}.ts").exists(), f"runtime/src/styles/{name}.ts is missing: a style is an experience, not a skin"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), f"style folder {name!r}: lowercase words joined by hyphens"


def test_every_runtime_style_has_a_style_folder():
    ts = {p.stem for p in (ROOT / "runtime" / "src" / "styles").glob("*.ts") if not p.stem.startswith("_")}
    assert not ts - set(STYLES), f"runtime/src/styles has modules with no engine/styles folder: {sorted(ts - set(STYLES))}"


@pytest.mark.parametrize("name", STYLES)
def test_a_style_declares_only_known_tokens_and_is_readable(name):
    s = T.styles()[name]
    assert not set(s) - STYLE_KEYS, f"engine/styles/{name}/style.yaml: unknown keys {set(s) - STYLE_KEYS}"
    assert s.get("label") and s.get("about"), f"engine/styles/{name}/style.yaml: needs a label and an about line"
    assert s.get("mode") in ("light", "dark"), f"engine/styles/{name}/style.yaml: mode must be light or dark"
    colours = dict(T.presets()["night"]["colors"], **s.get("colors", {}))     # what the page gets when the style is on
    bad = colour_rules(name, s["mode"], colours)
    assert not bad, f"engine/styles/{name}/style.yaml: " + "; ".join(bad)
    fonts = set(s.get("fonts", {}).values())
    assert not set(s.get("font_axes", {})) - fonts, f"engine/styles/{name}/style.yaml: font_axes for fonts it does not use: {set(s['font_axes']) - fonts}"
    assert s.get("cuts", True) in (True, False), f"engine/styles/{name}/style.yaml: cuts is true or false"


@pytest.mark.parametrize("name", STYLES)
def test_a_style_overrides_only_real_block_types_and_has_its_own_motion(name):
    t = (ROOT / "engine" / "styles" / name / "blocks.html.j2").read_text(encoding="utf-8")
    m = re.search(r"set types\s*=\s*\[(.*?)\]", t, re.S)
    assert m, f"engine/styles/{name}/blocks.html.j2: declare the block types it renders ({{% set types = [...] %}})"
    types = set(re.findall(r"[\"'](\w+)[\"']", m.group(1)))
    assert types and not types - BLOCK_TYPES, f"engine/styles/{name}/blocks.html.j2: unknown block types {types - BLOCK_TYPES}"
    for default in ("ss-reveal", "data-count"):
        assert default not in t, f"engine/styles/{name}/blocks.html.j2 uses the default motion `{default}` (rule 2)"


@pytest.mark.parametrize("name", STYLES)
def test_a_style_is_listed_documented_and_researched(name):
    label = T.styles()[name]["label"]
    assert name in spec.Theme.model_fields["style"].description, f"engine/spec.py Theme.style does not list {name} (the UI and MCP read it)"
    styles_md = (ROOT / "docs" / "styles.md").read_text(encoding="utf-8")
    assert name in styles_md or label in styles_md, f"docs/styles.md does not mention {name}"
    research = " ".join(p.read_text(encoding="utf-8") for p in (ROOT / "docs" / "styles").glob("*.md"))
    assert label.lower() in research.lower() or name in research, f"docs/styles/ has no research for {label}"


def test_the_readme_counts_the_styles_there_are():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    counts = {int(n) for n in re.findall(r"(\d+) (?:page experiences|styles)\b", readme)}
    assert counts == {len(STYLES)}, f"README.md says {sorted(counts)} styles; engine/styles has {len(STYLES)}"


# ---------------------------------------------------------------- every style draws every block type

def kitchen_sink(style: str | None) -> spec.Site:
    """A page with every block type, a scene in each layout and a button, so a style meets everything a spec can hold."""
    btn = {"label": "Start", "href": "#"}
    return spec.Site.model_validate({
        "name": "Conformance", "theme": {"style": style} if style else {},
        "sections": [
            {"type": "hero", "id": "hero", "title": "One <em>page</em>", "body": "Every block.", "buttons": [btn]},
            {"type": "intro", "id": "intro", "title": "Intro", "body": "Words."},
            {"type": "features", "id": "features", "items": [{"title": "A"}, {"title": "B", "body": "b"}, {"title": "C"}]},
            {"type": "stats", "id": "stats", "items": [{"value": "12", "label": "Twelve"}, {"value": "3", "unit": "%", "label": "Three"}]},
            {"type": "timeline", "id": "timeline", "items": [{"when": "2024", "title": "Then"}, {"when": "2026", "title": "Now"}]},
            {"type": "quote", "id": "quote", "text": "A line.", "who": "Someone"},
            {"type": "gallery", "id": "gallery", "items": [{"title": "One", "href": "#"}, {"title": "Two", "href": "#"}]},
            {"type": "product", "id": "product", "title": "Product", "body": "It.", "buttons": [btn]},
            {"type": "strip", "id": "strip", "items": [{"image": "a.jpg", "caption": "a"}, {"image": "b.jpg"}]},
            {"type": "orbit", "id": "orbit", "title": "Orbit", "center": "Core", "items": [{"label": "x"}, {"label": "y"}, {"label": "z"}]},
            {"type": "faq", "id": "faq", "items": [{"q": "Why?", "a": "Because."}]},
            {"type": "type", "id": "words", "steps": [{"title": "Overlay", "button": btn}]},
            {"type": "type", "id": "split", "layout": "split", "steps": [{"title": "Split", "fact": "f"}]},
            {"type": "type", "id": "cards", "layout": "cards", "steps": [{"title": "Cards", "body": "c"}]},
            {"type": "cta", "id": "cta", "title": "Done", "button": btn},
        ]})


def test_the_kitchen_sink_page_is_valid_in_the_default_look():
    html = page_html(kitchen_sink(None))
    assert html.count("<h1") == 1


@pytest.mark.parametrize("name", STYLES)
def test_a_style_renders_every_block_type_with_one_h1_and_all_the_words(name):
    site = kitchen_sink(name)
    html = page_html(site)
    assert html.count("<h1") == 1, f"{name}: the page must have exactly one <h1> (README rule 1), found {html.count('<h1')}"
    text = re.sub(r"<[^>]+>", " ", html)
    for word in ("Every block.", "Twelve", "Then", "A line.", "Because.", "Overlay", "Split", "Cards", "Done"):
        assert word in text, f"{name}: {word!r} from the spec is missing from the page (content must be real HTML text)"
