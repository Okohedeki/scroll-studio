"""`pointer:` (engine/spec.py Pointer): the visitor's pointer reveals the picture, a lens or a torch, on parallax and film
sections. The spec validates what it should and refuses what cannot work; the page carries the settings only when the spec
has them (so every existing spec builds the same page); the parallax builder fits each second picture to its photo."""
from __future__ import annotations

import json
import re

import numpy as np
import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from engine.compile.layout_snapshot import page_html
from engine.project import BuildContext, BuildError, Project
from engine.spec import Pointer, Site


def site(*sections) -> Site:
    return Site.model_validate({"name": "x", "sections": list(sections)})


def parallax(pointer=None, photos=1, **kw) -> dict:
    sec = {"id": "p", "type": "parallax", "steps": [{"title": f"t{i}", "image": f"inputs/p{i}.jpg"} for i in range(photos)], **kw}
    if pointer is not None:
        sec["pointer"] = pointer
    return sec


def film(pointer=None, **kw) -> dict:
    sec = {"id": "f", "type": "film", "video": "inputs/f.mp4", **kw}
    if pointer is not None:
        sec["pointer"] = pointer
    return sec


# ---------------------------------------------------------------- the spec

def test_defaults_and_what_the_page_reads():
    p = Pointer()
    assert (p.mode, p.layer, p.base, p.radius, p.strength, p.softness, p.color, p.rest) == \
        ("lens", "colour", None, None, None, 0.35, "#ffd7a8", (0.62, 0.42))
    assert p.pictures == []
    assert p.page() == {"mode": "lens", "layer": "colour", "base": None, "radius": None, "softness": 0.35, "strength": None,
                        "color": "#ffd7a8", "rest": [0.62, 0.42]}


def test_a_lens_takes_colour_by_either_spelling_one_picture_or_one_per_photo():
    assert Pointer(layer="color").layer == "colour"
    one = Pointer(layer={"file": "inputs/after.jpg"})
    assert len(one.pictures) == 1 and one.page()["layer"] == "picture"
    assert Pointer(layer="inputs/after.jpg").pictures == ["inputs/after.jpg"]
    s = site(parallax({"layer": ["inputs/a.jpg", {"generate": "the same room at night"}]}, photos=2))
    assert len(s.sections[0].pointer.pictures) == 2


@pytest.mark.parametrize("bad, why", [
    ({"mode": "torch"}, "mode"),
    ({"base": "sepia"}, "base is mono, dim, blur, none"),
    ({"color": "warm"}, "hex colour"),
    ({"rest": [1.2, 0.5]}, "0-1 of the picture"),
    ({"radius": 0.01}, "radius"),
    ({"radius": 0.9}, "radius"),
    ({"softness": 2}, "softness"),
    ({"mode": "light", "layer": "inputs/x.jpg"}, "light has no layer"),
    ({"extra": 1}, "extra"),
])
def test_bad_pointers_are_refused(bad, why):
    with pytest.raises(ValidationError, match=why):
        Pointer.model_validate(bad)


def test_a_light_and_a_tinted_lens_validate():
    assert Pointer(mode="light", strength=0.9, radius=0.4, color="#fff").mode == "light"
    assert Pointer(base="#2a4a6a").base == "#2a4a6a"


def test_film_takes_a_lens_on_its_colour_or_a_light_but_not_a_second_picture():
    assert site(film({"mode": "lens", "base": "dim"})).sections[0].pointer.base == "dim"
    assert site(film({"mode": "light"})).sections[0].pointer.mode == "light"
    with pytest.raises(ValidationError, match="a second picture needs a parallax section"):
        site(film({"layer": "inputs/after.jpg"}))


def test_a_parallax_list_has_at_most_one_picture_per_photo():
    with pytest.raises(ValidationError, match="lists 3 pictures for 2 photos"):
        site(parallax({"layer": ["a.jpg", "b.jpg", "c.jpg"]}, photos=2))


def test_only_scenes_that_show_a_picture_take_it():
    with pytest.raises(ValidationError):
        site({"id": "c", "type": "chart", "pointer": {"mode": "lens"}})


def test_absent_by_default_and_not_written_into_a_saved_spec():
    s = site(parallax(), film())
    assert all(sec.pointer is None for sec in s.sections)
    assert "pointer" not in json.dumps(s.model_dump(mode="json", exclude_defaults=True))


# ---------------------------------------------------------------- the page

def _pointer_json(html: str) -> list[dict]:
    return [json.loads(m) for m in re.findall(r'<script type="application/json" class="ss-pointer">(.*?)</script>', html)]


def test_the_page_carries_the_settings_only_where_the_spec_has_them():
    html = page_html(site(parallax({"mode": "light", "radius": 0.3}), film(), {**parallax(), "id": "q"}))
    found = _pointer_json(html)
    assert found == [{"mode": "light", "layer": "colour", "base": None, "radius": 0.3, "softness": 0.35, "strength": None,
                      "color": "#ffd7a8", "rest": [0.62, 0.42]}]
    # it sits in the section it belongs to, beside the scene's own config
    p_section = html[html.index('id="p"'):html.index('id="f"')]
    assert 'class="ss-pointer"' in p_section


def test_a_spec_without_pointer_compiles_to_the_same_page():
    plain = page_html(site(parallax(), film()))
    assert "ss-pointer" not in plain
    lit = page_html(site(parallax({"mode": "lens"}), film()))
    assert re.sub(r'\s*<script type="application/json" class="ss-pointer">.*?</script>', "", lit) == plain


def test_a_second_picture_reaches_the_page_as_the_word_picture_the_builder_resolves_the_file():
    html = page_html(site(parallax({"layer": "inputs/after.jpg"})))
    assert _pointer_json(html)[0]["layer"] == "picture"
    assert "after.jpg" not in html


# ---------------------------------------------------------------- the parallax builder

@pytest.fixture
def photo_project(tmp_path, monkeypatch):
    (tmp_path / "inputs").mkdir()
    Image.new("RGB", (640, 360), (120, 90, 60)).save(tmp_path / "inputs" / "p0.jpg")
    Image.new("RGB", (640, 360), (60, 90, 120)).save(tmp_path / "inputs" / "p1.jpg")
    Image.new("RGB", (400, 400), (250, 250, 250)).save(tmp_path / "inputs" / "square.jpg")   # not the photo's shape
    from engine.backends import depth
    monkeypatch.setattr(depth, "estimate", lambda im, size="small": np.tile(np.linspace(0, 1, im.width, dtype=np.float32), (im.height, 1)))
    return tmp_path


def _build(root, pointer):
    sec = parallax(pointer, photos=2)
    (root / "site.yaml").write_text(yaml.safe_dump({"name": "x", "sections": [sec]}))
    project = Project(root)
    from engine.scenes import parallax as builder
    logs: list[str] = []
    cfg = builder.build(project.load().sections[0], BuildContext(project, "p", log=logs.append), {})
    return cfg, project, logs


def test_each_photo_gets_its_second_picture_at_its_own_size(photo_project):
    cfg, project, logs = _build(photo_project, {"layer": ["inputs/square.jpg", {"file": "inputs/p0.jpg", "credit": "Before photo"}]})
    assert cfg["pointer"] == {"layers": ["assets/p/layer0.jpg", "assets/p/layer1.jpg"]}
    web = project.build / "p" / "web"
    for i in (0, 1):
        assert Image.open(web / f"layer{i}.jpg").size == Image.open(web / f"photo{i}.jpg").size
    assert any("not the shape of photo 0" in m for m in logs)
    assert "Before photo" in cfg["credits"]


def test_a_photo_past_the_list_has_no_lens_and_a_colour_lens_needs_no_files(photo_project):
    cfg, _, _ = _build(photo_project, {"layer": "inputs/p1.jpg"})
    assert cfg["pointer"] == {"layers": ["assets/p/layer0.jpg"]}
    cfg, project, _ = _build(photo_project, {"mode": "light"})
    assert "pointer" not in cfg
    cfg, _, _ = _build(photo_project, None)
    assert "pointer" not in cfg


def test_the_one_take_page_does_not_draw_it():
    from pathlib import Path
    data = yaml.safe_load((Path(__file__).resolve().parent.parent / "examples" / "fenmoor" / "site.yaml").read_text(encoding="utf-8"))
    film_sec = next(s for s in data["sections"] if s.get("journey"))
    film_sec["pointer"] = {"mode": "light"}
    with pytest.raises(ValidationError, match="not drawn on the one-take page"):
        Site.model_validate(data)


def test_steps_without_a_photo_are_captions_over_the_photo_before_them(photo_project):
    sec = {"id": "p", "type": "parallax", "layout": "overlay", "steps": [
        {"title": "First", "image": "inputs/p0.jpg"}, {"title": "Second", "at": {"grid": "5 / span 4", "row": "top"}},
        {"title": "Third", "image": "inputs/p1.jpg"}, {"title": "Fourth"}]}
    (photo_project / "site.yaml").write_text(yaml.safe_dump({"name": "x", "sections": [sec]}))
    project = Project(photo_project)
    from engine.scenes import parallax as builder
    cfg = builder.build(project.load().sections[0], BuildContext(project, "p", log=lambda m: None), {})
    assert [c["step"] for c in cfg["chapters"]] == [0, 2]                 # two photos; steps 1 and 3 hold them
    sec["steps"] = [{"title": "No photo at all"}]
    (photo_project / "site.yaml").write_text(yaml.safe_dump({"name": "x", "sections": [sec]}))
    with pytest.raises(BuildError, match="has no images"):
        builder.build(Project(photo_project).load().sections[0], BuildContext(Project(photo_project), "p"), {})


def test_a_photo_with_a_calm_side_tells_a_phone_where_to_look(photo_project):
    """A parallax photo with `calm: left` gets a `frame` (where a phone's narrow view sits across it): leaning left, as
    far as the words need, as a hero's picture does. A photo without a calm side has none and is shown from the middle."""
    im = Image.new("RGB", (1280, 720), (236, 238, 240))
    px = im.load()
    for x in range(600, 1280):                     # a busy right half: fine stripes where the words would sit
        for y in range(0, 720, 2):
            px[x, y] = (30, 30, 40)
    im.save(photo_project / "inputs" / "plate.png")
    sec = {"id": "p", "type": "parallax", "layout": "overlay", "steps": [
        {"title": "Calm on the left", "image": {"file": "inputs/plate.png", "calm": "left"}},
        {"title": "No calm side", "image": "inputs/p0.jpg"}]}
    (photo_project / "site.yaml").write_text(yaml.safe_dump({"name": "x", "sections": [sec]}))
    project = Project(photo_project)
    from engine.scenes import parallax as builder
    cfg = builder.build(project.load().sections[0], BuildContext(project, "p", log=lambda m: None), {})
    first, second = cfg["chapters"]
    assert 0 <= first["frame"] < 0.5                # toward the calm left
    assert "frame" not in second
