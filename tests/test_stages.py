"""stages: one subject through its states, scrolled through in order (engine/scenes/stages.py)."""
from __future__ import annotations

import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from engine.project import BuildContext, Project
from engine.spec import Site, StageReveal, StagesScene


def scene(**over) -> dict:
    sec = {"id": "make", "type": "stages", "layout": "overlay",
           "stages": ["inputs/a.png", {"image": "inputs/b.png", "reveal": "wipe"},
                      {"id": "done", "image": "inputs/c.png",
                       "reveal": {"kind": "map", "map": "inputs/order.png", "front": {"color": "accent", "where": "change"}}}],
           "steps": [{"title": "Drawn"}, {"title": "Made"}, {"title": "Finished", "state": {"stage": "done"}}]}
    sec.update(over)
    return sec


@pytest.fixture
def project(tmp_path):
    (tmp_path / "inputs").mkdir()
    for name, colour in (("a", (240, 240, 240)), ("b", (20, 40, 90)), ("c", (60, 60, 60))):
        Image.new("RGB", (640, 480), colour).save(tmp_path / "inputs" / f"{name}.png")
    Image.new("L", (320, 240), 128).save(tmp_path / "inputs" / "order.png")        # half the size: fitted to the stages
    Image.new("RGB", (300, 300), (0, 0, 0)).save(tmp_path / "inputs" / "square.png")  # not the stages' shape
    return tmp_path


def _build(root, sec, theme=None):
    (root / "site.yaml").write_text(yaml.safe_dump({"name": "x", "sections": [sec]}))
    p = Project(root)
    from engine.scenes import stages as builder
    logs: list[str] = []
    s = p.load().sections[0]
    cfg = builder.build(s, BuildContext(p, s.id, log=logs.append), theme or {"colors": {"accent": "#0085e0", "bg": "#eceef0", "ink": "#232833"}})
    return cfg, p, s, logs


# ---------------------------------------------------------------- the spec

def test_a_bare_string_is_a_stage_and_a_bare_reveal_is_its_kind():
    s = StagesScene.model_validate(scene())
    assert [st.id for st in s.stages] == ["s0", "s1", "done"]
    assert s.stages[1].reveal.kind == "wipe" and s.stages[0].reveal.kind == "fade"
    assert StageReveal.model_validate("wipe").kind == "wipe"


def test_what_the_spec_refuses():
    with pytest.raises(ValidationError, match="kind map needs `map`"):
        StageReveal.model_validate({"kind": "map"})
    with pytest.raises(ValidationError, match="theme role"):
        StagesScene.model_validate(scene(stages=["inputs/a.png", {"image": "inputs/b.png",
                                                                  "reveal": {"kind": "wipe", "front": {"color": "plum"}}}]))
    with pytest.raises(ValidationError, match="not one of the stages"):
        StagesScene.model_validate(scene(steps=[{"title": "x", "state": {"stage": "nowhere"}}]))
    with pytest.raises(ValidationError, match="not one of the stages"):
        StagesScene.model_validate(scene(steps=[{"title": "x", "state": {"stage": 7}}]))
    with pytest.raises(ValidationError, match="two stages are called"):
        StagesScene.model_validate(scene(stages=[{"id": "a", "image": "inputs/a.png"}, {"id": "a", "image": "inputs/b.png"}]))
    with pytest.raises(ValidationError):
        StagesScene.model_validate(scene(stages=["inputs/a.png"]))                 # one stage is a picture, not a sequence


def test_it_is_a_scene_of_the_site():
    site = Site.model_validate({"name": "x", "sections": [scene()]})
    assert site.sections[0].type == "stages"


# ---------------------------------------------------------------- timing

def test_steps_spread_over_the_stages_or_sit_where_they_are_pinned():
    from engine.scenes.stages import schedule, stage_at
    s = StagesScene.model_validate(scene())
    stages, holds = schedule(s)
    assert stages == [0, 0, 2]                     # a pin anywhere: unpinned steps follow the step before
    assert s.length == pytest.approx(2.2 * 3)
    s2 = StagesScene.model_validate(scene(steps=[{"title": "a"}, {"title": "b"}, {"title": "c"}]))
    stages2, holds2 = schedule(s2)
    assert stages2 == [0, 1, 2]
    # still through each hold, eased between them, never past the last stage
    for h in holds2:
        assert stage_at((h["a"] + h["b"]) / 2, holds2) == h["t"]
    mid = (holds2[0]["b"] + holds2[1]["a"]) / 2
    assert stage_at(mid, holds2) == pytest.approx(0.5)
    assert stage_at(0.0, holds2) == 0 and stage_at(1.0, holds2) == 2
    # every overlay caption is on screen while its stage holds still
    for st, h in zip(s2.steps, holds2):
        a, b = st.at
        assert a <= h["a"] and b >= h["b"]


# ---------------------------------------------------------------- the build

def test_every_stage_and_map_is_fitted_to_the_first_stage(project):
    cfg, p, s, logs = _build(project, scene(stages=["inputs/a.png", {"image": "inputs/square.png", "reveal": "fade"},
                                                    {"id": "done", "image": "inputs/c.png", "reveal": {"kind": "map", "map": "inputs/order.png"}}]))
    web = p.build / "make" / "web"
    sizes = {Image.open(web / f"s{i}.webp").size for i in range(3)}
    assert sizes == {(640, 480)}
    assert Image.open(web / "s0-s.webp").size == (480, 360)
    assert Image.open(web / "map2.png").mode == "L" and Image.open(web / "map2.png").size == (480, 360)
    assert any("stage 1 is not the shape of stage 0" in m for m in logs)
    assert [st["reveal"]["kind"] for st in cfg["stages"]] == ["none", "fade", "map"]
    assert cfg["stages"][2]["reveal"]["map"].endswith("map2.png")
    assert cfg["poster"].endswith("poster.jpg") and cfg["end"] == cfg["stages"][-1]["img"]


def test_a_front_takes_the_site_colours_and_the_lens_one_picture(project):
    sec = scene(pointer={"mode": "lens", "layer": "inputs/square.png"})
    cfg, p, s, logs = _build(project, sec)
    front = cfg["stages"][2]["reveal"]["front"]
    assert front == {"color": "#0085e0", "width": 0.02, "strength": 0.8, "where": "change"}
    assert cfg["pointer"]["layers"][0].endswith("layer.webp")
    assert Image.open(p.build / "make" / "web" / "layer.webp").size == (640, 480)
    assert cfg["fit"] == {"fit": "cover", "position": [0.5, 0.5], "zoom": 1.0} and cfg["phone"] == cfg["fit"]
    sec = scene(fit={"fit": "contain", "position": [1, 0.5]}, phone={"fit": "contain", "position": [0.5, 1], "zoom": 0.9})
    cfg, *_ = _build(project, sec)
    assert cfg["fit"]["fit"] == "contain" and cfg["phone"] == {"fit": "contain", "position": [0.5, 1.0], "zoom": 0.9}


def test_front_colours():
    from engine.scenes.stages import front_colour
    c = {"accent": "#0085e0", "bg": "#eceef0", "ink": "#232833"}
    assert front_colour("#FF8A3D", c) == "#ff8a3d"
    assert front_colour("light", c) == "#eceef0" and front_colour("dark", c) == "#232833"
    assert front_colour("accent2", c) == "#0085e0"            # a role the site does not set falls back to its accent


def test_shade_none_holds_on_a_phone():
    """The narrow-screen gradient over overlay scenes must not undo a scene's `shade: none` (it is later in the file, so it
    needs its own rule after it)."""
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / "runtime" / "src" / "styles.css").read_text(encoding="utf-8")
    narrow = css[css.index("@media (max-width: 900px)"):]
    over = narrow.index(".ss-overlay .ss-shade {")
    assert ".ss-shade-none .ss-shade { background: none; }" in narrow[over:over + 400]
