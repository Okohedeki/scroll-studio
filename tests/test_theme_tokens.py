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


if __name__ == "__main__":
    rows = [f"{json.dumps(k)}: {json.dumps(dump(t), sort_keys=True, separators=(',', ':'))}" for k, t in sorted(cases().items())]
    BASELINE.write_text("{\n" + ",\n".join(rows) + "\n}\n", encoding="utf-8", newline="\n")     # one case per line
    print(f"wrote {BASELINE}")
