"""Living details: `live:` on an image input (engine/spec.py LiveDetail, engine/live.py, runtime/src/lib/live.ts).

The spec validates what it should and refuses what cannot work; the picture's cache key ignores it; the build resolves
colours from the theme, finds glints on bright specks, takes a prompt's region from the region tooling (or falls back to
the box); the page carries `data-live` only on pictures that have details, and a parallax chapter carries its list only
when its photo has one. No ComfyUI, GPU or browser needed."""
from __future__ import annotations

import html as htmllib
import json
import re
import textwrap

import numpy as np
import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from engine import live as L
from engine.inputs import image_key, stable_dump
from engine.project import BuildContext, Project
from engine.spec import ImageInput, LiveDetail


# ---------------------------------------------------------------- the spec

def test_the_documented_example_validates_and_one_detail_may_stand_alone():
    img = ImageInput.model_validate(yaml.safe_load(textwrap.dedent('''\
        file: inputs/hero.jpg
        live:
          - { kind: drift, box: [0.35, 0.25, 0.55, 0.42], speed: 0.8 }
          - { kind: glint, box: [0.6, 0, 1, 0.3], count: 8, color: accent2 }
          - { kind: sweep, box: [0, 0, 1, 1], origin: [0.1, 0.9] }
        ''')))
    assert [d.kind for d in img.live] == ["drift", "glint", "sweep"]
    d = img.live[0]
    assert (d.speed, d.strength, d.softness, d.angle, d.count, d.color, d.origin) == (0.8, 0.6, 0.25, 0, 12, None, None)
    one = ImageInput.model_validate({"file": "a.png", "live": {"kind": "rise", "box": [0, 0.5, 1, 1]}})
    assert len(one.live) == 1 and one.live[0].kind == "rise"
    assert ImageInput.model_validate({"file": "a.png", "live": {"kind": "flow", "prompt": "the river"}}).live[0].prompt == "the river"


@pytest.mark.parametrize("bad, why", [
    ({"kind": "drift"}, "box"),
    ({"kind": "sparkle", "box": [0, 0, 1, 1]}, "kind"),
    ({"kind": "drift", "box": [0.5, 0, 0.4, 1]}, "x0 < x1"),
    ({"kind": "drift", "box": [0, 0, 1.2, 1]}, "0-1"),
    ({"kind": "glint", "box": [0, 0, 1, 1], "color": "gold"}, "theme token"),
    ({"kind": "drift", "box": [0, 0, 1, 1], "origin": [0.5, 0.5]}, "origin"),
    ({"kind": "drift", "box": [0, 0, 1, 1], "speed": 9}, "speed"),
    ({"kind": "glint", "box": [0, 0, 1, 1], "count": 40}, "count"),
    ({"kind": "drift", "box": [0, 0, 1, 1], "wobble": 1}, "wobble"),
])
def test_bad_details_are_refused(bad, why):
    with pytest.raises(ValidationError, match=why):
        LiveDetail.model_validate(bad)


def test_at_most_four_details_on_a_picture():
    d = {"kind": "glint", "box": [0, 0, 1, 1]}
    ImageInput.model_validate({"file": "a.png", "live": [d] * 4})
    with pytest.raises(ValidationError):
        ImageInput.model_validate({"file": "a.png", "live": [d] * 5})


def test_absent_by_default_and_the_picture_is_keyed_as_before():
    plain = ImageInput(generate="a lamp", seed=3)
    assert plain.live is None and "live" not in plain.model_dump(mode="json") and "live" not in stable_dump(plain)
    alive = ImageInput(generate="a lamp", seed=3, live=[LiveDetail(kind="glint", box=(0, 0, 1, 1))])
    assert image_key(alive) == image_key(plain)              # the page draws it; the picture is the same picture
    assert "live" in alive.model_dump(mode="json")


# ---------------------------------------------------------------- colour

PAPER = {"bg": "#f6f1e7", "ink": "#16203a", "accent": "#2f4fd8", "accent2": "#ff6c8f"}
NIGHT = {"bg": "#050608", "ink": "#eef0f2", "accent": "#ff6b2c"}


def test_colours_come_from_the_theme():
    det = lambda **kw: LiveDetail(box=(0, 0, 1, 1), **{"kind": "glint", **kw})
    assert L.colour(det(), PAPER) == "#f6f1e7"                       # light: the lighter of text and background
    assert L.colour(det(), NIGHT) == "#eef0f2"
    assert L.colour(det(kind="rise"), PAPER) == "#ff6c8f"            # rise: accent2 ...
    assert L.colour(det(kind="rise"), NIGHT) == "#ff6b2c"            # ... or accent when there is none
    assert L.colour(det(color="dark"), PAPER) == "#16203a"
    assert L.colour(det(color="accent"), PAPER) == "#2f4fd8"
    assert L.colour(det(color="#fff"), PAPER) == "#ffffff"
    assert L.colour(det(color="bg2"), PAPER) == "#f6f1e7"            # a token the theme lacks: light


# ---------------------------------------------------------------- glints

def _field(specks, patch=True, H=300, W=400):
    lum = np.full((H, W), 0.25, np.float32)
    if patch:
        lum[40:140, 220:360] = 0.7                                   # a big flat bright shape: not a speck
    for x, y in specks:
        lum[y - 1:y + 1, x - 1:x + 1] = 1.0
    return lum


def test_glints_land_on_bright_specks_not_on_flat_shapes():
    specks = [(60, 60), (200, 230), (160, 120), (330, 250), (60, 230)]     # further apart than the spacing
    pts = L.bright_points(_field(specks), (0, 0, 1, 1), 5)
    assert len(pts) == 5
    for sx, sy in specks:
        assert min(np.hypot(x * 400 - sx, y * 300 - sy) for x, y, _ in pts) <= 2
    assert all(0.5 <= s <= 1 for _, _, s in pts) and max(s for *_, s in pts) == 1


def test_glints_stay_inside_the_box_off_its_soft_edge_and_spaced():
    pts = L.bright_points(_field([(x, y) for x in range(20, 400, 15) for y in range(20, 300, 15)], patch=False), (0.25, 0.25, 0.75, 0.75), 12)
    assert len(pts) == 12
    for x, y, _ in pts:
        assert 0.25 + 0.5 * 0.12 - 0.01 <= x <= 0.75 - 0.5 * 0.12 + 0.01 and 0.25 + 0.06 - 0.01 <= y <= 0.69 + 0.01
    d = min(np.hypot((a[0] - b[0]) * 400, (a[1] - b[1]) * 300) for i, a in enumerate(pts) for b in pts[i + 1:])
    assert d >= 10


def test_a_mask_keeps_glints_inside_it_and_a_flat_region_spreads_them_evenly():
    specks = [(60, 60), (340, 240)]
    weight = np.zeros((10, 10), np.float32)
    weight[:5, :5] = 1                                               # only the top left quarter of the box
    pts = L.bright_points(_field(specks, patch=False), (0, 0, 1, 1), 2, weight)
    assert np.hypot(pts[0][0] * 400 - 60, pts[0][1] * 300 - 60) <= 2
    assert all(x < 0.5 and y < 0.5 for x, y, _ in pts)
    flat = L.bright_points(np.full((100, 100), 0.5, np.float32), (0.2, 0.2, 0.8, 0.8), 6)
    assert len(flat) == 6 and all(0.2 < x < 0.8 and 0.2 < y < 0.8 for x, y, _ in flat)
    assert flat == L.bright_points(np.full((100, 100), 0.5, np.float32), (0.2, 0.2, 0.8, 0.8), 6)   # the same every build


# ---------------------------------------------------------------- the region

def test_a_masks_extent_is_its_box():
    m = np.zeros((100, 200), np.uint8)
    m[20:40, 50:150] = 255
    assert L.mask_box(m, pad=0) == (0.25, 0.2, 0.75, 0.4)
    assert L.mask_box(np.zeros((10, 10), np.uint8)) is None


def test_a_box_is_used_as_given():
    d = LiveDetail(kind="drift", box=(0.1, 0.2, 0.3, 0.4))
    assert L.find_region(None, None, d) == ((0.1, 0.2, 0.3, 0.4), None)


def test_a_prompt_without_comfyui_falls_back_to_its_box_or_is_left_out(tmp_path, monkeypatch):
    from engine import region

    def no_comfy(*a, **k):
        raise RuntimeError("ComfyUI is not running")
    monkeypatch.setattr(region, "find", no_comfy)
    logs: list[str] = []
    both = LiveDetail(kind="drift", prompt="the clouds", box=(0.1, 0.1, 0.5, 0.5))
    assert L.find_region(None, tmp_path / "a.png", both, logs.append) == ((0.1, 0.1, 0.5, 0.5), None)
    assert "using its box" in logs[-1] and "ComfyUI is not running" in logs[-1]
    alone = LiveDetail(kind="drift", prompt="the clouds")
    assert L.find_region(None, tmp_path / "a.png", alone, logs.append) == (None, None)
    assert "left out" in logs[-1]


def test_a_prompt_becomes_the_masks_extent_and_a_small_soft_mask(tmp_path, monkeypatch):
    from engine import region
    raw = np.zeros((400, 600), np.uint8)
    raw[100:200, 300:500] = 255
    Image.fromarray(raw).save(tmp_path / "region.png")
    monkeypatch.setattr(region, "find", lambda project, src, er, log=print: tmp_path / "region.png")
    box, mask = L.find_region(None, tmp_path / "a.png", LiveDetail(kind="drift", prompt="the cloud"))
    assert 0.45 < box[0] < 0.5 and 0.2 < box[1] < 0.25 and 0.83 < box[2] < 0.88 and 0.5 < box[3] < 0.55
    assert mask.shape == (L.MASK_PX, L.MASK_PX) and mask.max() == 255 and mask[0, 0] < 40     # soft edges, solid middle


def test_while_planning_only_an_already_found_region_is_used(tmp_path, monkeypatch):
    from engine import region
    monkeypatch.setattr(region, "find", lambda *a, **k: pytest.fail("ran the region model while planning"))
    (tmp_path / "a.png").write_bytes(b"x")
    logs: list[str] = []
    out = L.find_region(Project(tmp_path), tmp_path / "a.png", LiveDetail(kind="drift", prompt="the cloud", box=(0, 0, 1, 1)),
                        logs.append, only_cached=True)
    assert out == ((0, 0, 1, 1), None) and "not found yet" in logs[-1]


# ---------------------------------------------------------------- the page

def _hero_site(tmp_path, live):
    root = tmp_path / "site"
    (root / "inputs").mkdir(parents=True)
    rng = np.random.default_rng(3)
    a = np.full((300, 480, 3), (40, 70, 200), np.uint8)
    for _ in range(30):
        y, x = rng.integers(5, 295), rng.integers(5, 475)
        a[y - 1:y + 1, x - 1:x + 1] = 250
    Image.fromarray(a).save(root / "inputs" / "a.png")
    image = {"file": "inputs/a.png"}
    if live is not None:
        image["live"] = live
    spec = {"name": "Alive", "theme": {"preset": "paper"}, "sections": [
        {"type": "hero", "title": "Sky", "image": image},
        {"type": "gallery", "items": [{"title": "One", "href": "#", "image": {"file": "inputs/a.png"}}]}]}
    (root / "site.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    return root


def _entries(html: str) -> list[dict]:
    return [json.loads(htmllib.unescape(m)) for m in re.findall(r'data-live="([^"]+)"', html)]


def test_the_page_marks_only_the_picture_that_has_details(tmp_path):
    from engine.compile.compiler import build_site
    root = _hero_site(tmp_path, [{"kind": "drift", "box": [0.1, 0.1, 0.5, 0.5], "angle": 90},
                                 {"kind": "glint", "box": [0.5, 0, 1, 0.5], "count": 5}])
    html = build_site(Project(root), log=lambda m: None).read_text(encoding="utf-8")
    (e,) = _entries(html)
    assert e["r"] == 1.6
    drift, glint = e["d"]
    from engine.compile import themes
    from engine.spec import Theme
    paper = themes.resolve(Theme(preset="paper"))["colors"]
    assert drift == {"kind": "drift", "box": [0.1, 0.1, 0.5, 0.5], "speed": 1.0, "strength": 0.6, "softness": 0.25, "count": 12,
                     "color": paper["bg"].lower(), "angle": 90.0, "origin": None}
    assert glint["kind"] == "glint" and 1 <= len(glint["points"]) <= 5
    assert all(0.5 <= x <= 1 and 0 <= y <= 0.5 for x, y, _ in glint["points"])
    assert re.search(r'ss-hero__media"><img [^>]*data-live=', html)        # on the hero's <img> itself


def test_without_live_the_page_has_no_trace_of_it(tmp_path):
    from engine.compile.compiler import build_site
    html = build_site(Project(_hero_site(tmp_path, None)), log=lambda m: None).read_text(encoding="utf-8")
    assert "data-live" not in html


def test_wiring_leaves_other_markup_alone():
    from engine.compile.compiler import wire_live
    h = '<img src="assets/_media/zzz.webp" alt="">'
    assert wire_live(h, {"assets/_media/abc.webp": {"r": 1}}) == h
    assert wire_live(h, {"assets/_media/zzz.webp": {"r": 1}}) == '<img src="assets/_media/zzz.webp" alt="" data-live="{&quot;r&quot;:1}">'


@pytest.fixture
def photo_project(tmp_path, monkeypatch):
    (tmp_path / "inputs").mkdir()
    Image.new("RGB", (640, 360), (40, 60, 160)).save(tmp_path / "inputs" / "p0.jpg")
    Image.new("RGB", (640, 360), (60, 90, 120)).save(tmp_path / "inputs" / "p1.jpg")
    from engine.backends import depth
    monkeypatch.setattr(depth, "estimate", lambda im, size="small": np.tile(np.linspace(0, 1, im.width, dtype=np.float32), (im.height, 1)))
    return tmp_path


def test_a_parallax_photo_carries_its_details_and_the_others_carry_none(photo_project):
    sec = {"id": "p", "type": "parallax", "steps": [
        {"title": "a", "image": {"file": "inputs/p0.jpg", "live": [{"kind": "flow", "box": [0, 0.6, 1, 1], "angle": 0}]}},
        {"title": "b", "image": "inputs/p1.jpg"}]}
    (photo_project / "site.yaml").write_text(yaml.safe_dump({"name": "x", "sections": [sec]}))
    project = Project(photo_project)
    from engine.scenes import parallax as builder
    cfg = builder.build(project.load().sections[0], BuildContext(project, "p", log=lambda m: None), {"colors": NIGHT})
    first, second = cfg["chapters"]
    assert first["live"] == [{"kind": "flow", "box": [0, 0.6, 1, 1], "speed": 1.0, "strength": 0.6, "softness": 0.25, "count": 12,
                              "color": "#eef0f2", "angle": 0.0, "origin": None}]
    assert "live" not in second
