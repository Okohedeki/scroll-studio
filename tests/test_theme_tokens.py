"""The resolved theme stays byte-identical (issue #117): every example, every old spec, every preset and every preset with
every style resolves to the same tokens, CSS variables and font links as it did before themes became layered token sets.

tests/fixtures/theme_baseline.json was recorded from main before the refactor. New tokens may be added to the resolved
theme (they default to what the stylesheet hard-coded, so nothing moves); every token in the baseline must keep its
value, and the CSS and font links must not change by one byte. Re-recording is not a fix: a difference here means an
existing spec now builds a different page.

    python tests/test_theme_tokens.py    # (re)writes the baseline, only ever from main
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).parent / "fixtures" / "theme_baseline.json"
if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))


def cases() -> dict:
    """{case name: Theme} for every theme an existing spec or look can resolve to."""
    from engine.compile import themes as T
    from engine.spec import Site, Theme
    out = {}
    for p in sorted((ROOT / "examples").glob("*/site.yaml")):
        out[f"example:{p.parent.name}"] = Site.model_validate(yaml.safe_load(p.read_text(encoding="utf-8"))).theme
    for p in sorted((ROOT / "tests" / "fixtures" / "old_specs").glob("v*/*.yaml")):
        out[f"old:{p.parent.name}/{p.stem}"] = Site.model_validate(yaml.safe_load(p.read_text(encoding="utf-8"))).theme
    for preset in sorted(T.presets()):
        out[f"preset:{preset}"] = Theme(preset=preset)
        for style in sorted(T.styles()):
            out[f"preset:{preset}+style:{style}"] = Theme(preset=preset, style=style)
    return out


def dump(theme) -> dict:
    from engine.compile import themes as T
    t = T.resolve(theme)
    css = T.css_vars(t)
    return {"theme": json.loads(json.dumps(t)), "css": _digest(css), "fonts": _digest(" ".join(T.font_links(t)))}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:20]


CASES = cases()
BASE = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}


def test_the_baseline_covers_every_case():
    base = BASE
    assert base, "tests/fixtures/theme_baseline.json is missing"
    assert set(CASES) >= set(base), f"cases gone from the baseline: {sorted(set(base) - set(CASES))[:10]}"


@pytest.mark.parametrize("name", sorted(BASE))
def test_the_resolved_theme_is_unchanged(name):
    was = BASE[name]
    now = dump(CASES[name])
    changed = {k: (v, now["theme"].get(k, "<missing>")) for k, v in was["theme"].items() if now["theme"].get(k, "<missing>") != v}
    assert not changed, f"{name}: tokens changed (was, now): {changed}"
    assert now["css"] == was["css"], f"{name}: the CSS variables changed (diff css_vars() against main to see where)"
    assert now["fonts"] == was["fonts"], f"{name}: the font links changed (diff font_links() against main)"


def test_layers_go_defaults_preset_style_then_site_yaml():
    from engine.compile import themes as T
    from engine.spec import Theme
    theme = Theme(preset="paper", style="bauhaus", colors={"accent": "#123456"}, radius="9px")
    assert [name for name, _ in T.layers(theme)] == ["defaults", "preset paper", "style bauhaus", "site.yaml"]
    t = T.resolve(theme)
    assert t["colors"]["accent"] == "#123456"                                   # site.yaml over the style
    assert t["colors"]["bg"] == T.styles()["bauhaus"]["colors"]["bg"]           # the style over the preset
    assert t["fonts"]["display"] == "Jost" and t["radius"] == "9px" and t["labels"] == "caps"   # ... over the defaults
    assert T.layer({"colors": {"a": 1}, "radius": "1px"}, {"colors": {"b": 2}, "radius": None}) == {"colors": {"a": 1, "b": 2}, "radius": "1px"}



# ---------------------------------------------------------------- the tokens from #15: space, type, shade, motion, grain, phone

def test_new_tokens_default_to_what_the_stylesheet_declares():
    """runtime/src/styles.css declares each token's default; the theme's defaults must say the same, or a theme that
    sets a token back to its documented default would move the page."""
    import re

    from engine.compile import themes as T
    css = (ROOT / "runtime" / "src" / "styles.css").read_text(encoding="utf-8")
    block = re.search(r":where\(:root\) \{(.*?)\}", css, re.S).group(1)
    declared = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))
    for (group, k), var in T.CSS_TOKENS.items():
        assert declared.get(var) == str(T.DEFAULTS[group][k]), f"{var}: studio.css says {declared.get(var)!r}, themes.DEFAULTS {T.DEFAULTS[group][k]!r}"


def test_a_theme_that_sets_no_new_token_writes_nothing_new():
    from engine.compile import themes as T
    from engine.spec import Theme
    t = T.resolve(Theme())
    assert t["runtime"] == {} and t["grain"] == 0 and t["phone"] is None
    assert not any(var in T.css_vars(t) for var in T.CSS_TOKENS.values())


def test_new_tokens_reach_the_css_the_runtime_and_the_page():
    from engine.compile import themes as T
    from engine.compile.layout_snapshot import page_html
    from engine.spec import Site
    site = Site.model_validate({"name": "Tokens", "theme": {
        "space": {"gutter": "24px", "caption": "560px"}, "type": {"scale": 1.2, "body": "18px"}, "shade": {"strength": 0.5},
        "motion": {"ease": "ease-out", "enter": 0.3}, "grain": 0.2, "phone": 820},
        "sections": [{"type": "hero", "id": "hero", "title": "Hi"}]})
    t = T.resolve(site.theme)
    css = T.css_vars(t)
    for line in ("--gutter: 24px;", "--caption-w: 560px;", "--type-scale: 1.2;", "--body-size: 18px;", "--shade-strength: 0.5;",
                 "--ease: ease-out;"):
        assert line in css
    assert "--max:" not in css                                  # a token left alone stays the stylesheet's
    assert t["runtime"] == {"phone": 820, "enter": 0.3}
    html = page_html(site)
    assert 'window.__ssTheme = {"enter": 0.3, "phone": 820}' in html or 'window.__ssTheme = {"phone": 820, "enter": 0.3}' in html
    assert 'class="ss-grain"' in html and "@media (max-width: 820px)" in html
    built = T.phone_css("@media (max-width:900px){a{}}@media (max-width:760px){b{}}@media (max-width: 700px){c{}}"
                        "@media (max-width:600px){d{}}", 820)
    assert built.count("(max-width: 820px)") == 3 and "600px" in built   # the three phone widths become one; others stay


def test_new_token_values_must_be_plain_css():
    from pydantic import ValidationError

    from engine.spec import Theme
    for bad in ({"space": {"gutter": "1px;}</style><script>x</script>"}}, {"type": {"body": "x{}"}},
                {"motion": {"ease": "url(javascript:x)"}}, {"phone": 100}, {"grain": 2}, {"shade": {"strength": -1}}):
        with pytest.raises(ValidationError):
            Theme.model_validate(bad)


def test_phone_rewrites_the_runtime_stylesheet_of_a_build(tmp_path, monkeypatch):
    from engine.compile import compiler, fonts
    from engine.project import Project
    (tmp_path / "site.yaml").write_text(yaml.safe_dump({"name": "P", "theme": {"phone": 820},
                                                        "sections": [{"type": "hero", "id": "hero", "title": "Hi"}]}),
                                        encoding="utf-8")
    monkeypatch.setattr(fonts, "vendor", lambda links, dist, log=print: None)     # no network in tests
    compiler.build_site(Project(tmp_path), log=lambda m: None)
    css = (tmp_path / "dist" / "runtime" / "studio.css").read_text(encoding="utf-8")
    assert "(max-width: 820px)" in css and "max-width:900px" not in css and "max-width:760px" not in css


if __name__ == "__main__":
    rows = [f"{json.dumps(k)}: {json.dumps(dump(t), sort_keys=True, separators=(',', ':'))}" for k, t in sorted(cases().items())]
    BASELINE.write_text("{\n" + ",\n".join(rows) + "\n}\n", encoding="utf-8", newline="\n")     # one case per line
    print(f"wrote {BASELINE}")
