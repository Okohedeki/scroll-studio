"""Generated page layouts (engine/layouts.py, issue #179): the local composer writes distinct, valid layouts from the
project's material; a text backend's layouts are resolved and validated; picking one makes it outputs.site.
Laptop path: no network, no GPU."""
from __future__ import annotations

import json

import pytest
import yaml

from engine import layouts
from engine.project import BuildError
from engine.router import core
from engine.router.core import Result
from engine.spec import Site
from engine.stills import run as stills
from test_stills import project


@pytest.fixture(autouse=True)
def no_backends(monkeypatch):
    monkeypatch.setattr(core, "backends", lambda: [])
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)


def shop(tmp_path, count=3):
    p = project(tmp_path)
    data = yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))
    data["outputs"]["layouts"] = {"count": count}
    data["outputs"]["ads"] = {"headline": "Hello there", "cta": "Shop"}
    p.spec_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    stills.make(p, log=lambda m: None)
    return p


def test_local_layouts_are_valid_distinct_and_use_the_stills(tmp_path):
    p = shop(tmp_path)
    st = layouts.make(p, log=lambda m: None)
    names = [x["name"] for x in st["layouts"]]
    assert len(names) == 3 and len(set(names)) == 3
    orders = {tuple(s["type"] for s in x["sections"]) for x in st["layouts"]}
    assert len(orders) == 3
    for x in st["layouts"]:
        Site.model_validate({"name": "T", "sections": x["sections"]})
        hero = next((s for s in x["sections"] if s["type"] == "hero"), None)
        assert hero and hero["title"] == "Hello there" and (p.root / hero["image"]).exists()
    assert (p.root / "layouts" / "l1.yaml").exists() and (p.root / "layouts" / "board.html").exists()


def test_compose_is_seeded_and_skips():
    m = {"name": "N", "brief": "", "describe": "d", "title": "T", "bullets": ["a"], "description": "D",
         "headline": "H", "cta": "C", "images": {"lifestyle": ["x.png"], "packshot": [], "detail": []}}
    assert layouts.compose(m, 3, 1) == layouts.compose(m, 3, 1)
    assert "Short" not in [x["name"] for x in layouts.compose(m, 4, 1, skip=("Short",))]


def test_placeholders_resolve_and_unknown_ones_drop():
    m = {"images": {"lifestyle": ["a.png", "b.png"], "packshot": [], "detail": []}}
    out = layouts.resolve([{"type": "hero", "title": "t", "image": "@lifestyle:2"},
                           {"type": "hero", "title": "t", "image": "@nothing:1"},
                           {"type": "script", "src": "x"}], m)
    assert out == [{"type": "hero", "title": "t", "image": "b.png"}, {"type": "hero", "title": "t"}]


def test_a_text_backends_layouts_are_validated(tmp_path, monkeypatch):
    class Designer:
        name, local, kinds = "designer", True, ("text",)

        def available(self):
            return True, ""

        def model(self, kind):
            return "d"

        def run(self, job, out, model=None):
            good = {"name": "Bold", "sections": [{"type": "hero", "title": "Big", "image": "@packshot:1"},
                                                  {"type": "cta", "id": "buy", "title": "Go"}]}
            bad = {"name": "Broken", "sections": [{"type": "features"}]}
            return Result("designer", "d", 0.0, text=json.dumps([good, bad]))

    p = shop(tmp_path, count=2)
    monkeypatch.setattr(core, "backends", lambda: [Designer()])
    lines: list[str] = []
    st = layouts.make(p, log=lines.append)
    assert [x["source"] for x in st["layouts"]] == ["designer", "local"]
    assert st["layouts"][0]["sections"][0]["image"].startswith("stills/")
    assert any("dropped 'Broken'" in ln for ln in lines)


def test_pick_writes_outputs_site_and_keeps_the_old_one(tmp_path):
    p = shop(tmp_path)
    data = yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))
    data["outputs"]["site"] = {"sections": [{"type": "intro", "title": "Old"}], "layout": "stack"}
    p.spec_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    st = layouts.make(p, log=lambda m: None)
    layouts.make(p, pick="l2", log=lambda m: None)
    site = p.load()
    want = [s["type"] for s in st["layouts"][1]["sections"]]
    assert site.layout == "stack" and [s.type for s in site.sections] == want
    assert "Old" in (p.root / "layouts" / "site-before-pick.yaml").read_text(encoding="utf-8")
    assert yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))["outputs"]["stills"]
    with pytest.raises(BuildError, match="no layout"):
        layouts.make(p, pick="../x", log=lambda m: None)


def test_needs_outputs_layouts(tmp_path):
    with pytest.raises(BuildError, match="outputs.layouts"):
        layouts.make(project(tmp_path), log=lambda m: None)
