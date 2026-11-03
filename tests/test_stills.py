"""Product stills (engine/stills, issue #175): the whole flow runs on a laptop (local directions, drawn backdrops),
critics score fixed images, and the product's pixels survive compositing. No network, no GPU."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

from engine.project import BuildError, Project
from engine.router import core
from engine.stills import compose, critics, directions, run, shortlist
from engine.stills.cutout import CutoutError, cutout, key_plain_backdrop


@pytest.fixture(autouse=True)
def no_backends(monkeypatch):
    """No backend can run: the laptop path."""
    monkeypatch.setattr(core, "backends", lambda: [])


def product_photo(path: Path, bg=(246, 246, 244)) -> Path:
    im = Image.new("RGB", (300, 360), bg)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((90, 110, 210, 320), radius=20, fill=(60, 110, 90))
    d.rectangle((100, 200, 200, 214), fill=(230, 214, 170))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


def project(tmp_path: Path, **stills) -> Project:
    root = tmp_path / "shop"
    product_photo(root / "inputs" / "product.png")
    spec = {"name": "Example Shop", "brief": "Autumn range",
            "outputs": {"stills": {"photo": "inputs/product.png", "describe": "a planter", "directions": 2,
                                   "candidates": 1, "keep": 2, "size": [320, 320], **stills}}}
    (root / "project.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    return Project(root)


# ---------------------------------------------------------------- cutout

def test_a_plain_backdrop_is_keyed_out(tmp_path):
    p = cutout(product_photo(tmp_path / "p.png"))
    assert p.mode == "RGBA" and p.size[0] < 160          # cropped to the product
    a = np.asarray(p.getchannel("A"))
    assert a[a.shape[0] // 2, a.shape[1] // 2] == 255 and a[0, 0] < 30


def test_a_transparent_png_is_used_as_is(tmp_path):
    im = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((10, 10, 30, 40), fill=(200, 10, 10, 255))
    im.save(tmp_path / "c.png")
    assert cutout(tmp_path / "c.png").size == (25, 35)


def test_a_busy_photo_is_refused_without_rembg(tmp_path):
    rng = np.random.default_rng(1)
    Image.fromarray(rng.integers(0, 255, (100, 100, 3), dtype=np.uint8)).save(tmp_path / "busy.png")
    with pytest.raises(CutoutError, match="plain backdrop"):
        key_plain_backdrop(Image.open(tmp_path / "busy.png"))


# ---------------------------------------------------------------- directions

def test_local_directions_are_seeded_and_spread():
    a, b = directions.local(5, 3), directions.local(5, 3)
    assert a == b and directions.local(5, 4) != a
    assert len({d.setting for d in a}) == 5 and len({d.light for d in a}) == 5


def test_local_directions_avoid_names_already_used():
    first = directions.local(4, 1)
    second = directions.local(4, 2, avoid=directions.named(first))
    assert not set(directions.named(first)) & set(directions.named(second))


def test_parse_reads_a_text_backends_answer():
    text = 'Here: [{"name": "Salt flat", "setting": "white salt flat", "light": "noon", ' \
           '"palette": ["#ffffff", "#eeeeee", "#123456"], "mood": "stark"}]'
    [d] = directions.parse(text, 1, 9, "anthropic")
    assert d.name == "Salt flat" and d.palette == ("#ffffff", "#eeeeee", "#123456") and d.source == "anthropic"
    with pytest.raises(ValueError):
        directions.parse('[{"name": "x", "palette": ["red"]}]', 1, 9, "x")
    with pytest.raises(ValueError):
        directions.parse("no json", 1, 9, "x")


def test_write_falls_back_to_local_without_a_text_backend():
    assert directions.write(3, 1, "a planter", "", log=lambda m: None) == directions.local(3, 1)


# ---------------------------------------------------------------- compositing keeps the product's pixels

def test_the_composite_keeps_the_product_exactly(tmp_path):
    prod = cutout(product_photo(tmp_path / "p.png"))
    d = directions.local(1, 1)[0]
    made = compose.make(prod, "lifestyle", d, 1, (320, 320), "a planter", tmp_path / "w", "c1", log=lambda m: None)
    assert made.backend == "local" and not made.harmonised and made.notes
    img, mask = Image.open(made.image), Image.open(made.mask)
    p, (x, y) = compose.place(prod, "lifestyle", (320, 320), 1)
    solid = np.asarray(p.getchannel("A")) == 255
    got = np.asarray(img.crop((x, y, x + p.width, y + p.height)))[solid]
    want = np.asarray(p.convert("RGB"))[solid]
    assert np.abs(got.astype(int) - want.astype(int)).max() <= 1
    assert np.asarray(mask).max() == 255


@pytest.mark.parametrize("shot", ["packshot", "lifestyle", "detail"])
def test_each_shot_frames_the_product_for_its_kind(tmp_path, shot):
    prod = cutout(product_photo(tmp_path / "p.png"))
    made = compose.make(prod, shot, directions.local(1, 1)[0], 1, (320, 320), "", tmp_path / "w", shot,
                        log=lambda m: None)
    assert critics.framing(Image.open(made.mask), shot) > 0.5


# ---------------------------------------------------------------- critics

def test_product_change_and_fidelity():
    a = Image.new("RGB", (10, 10), (100, 100, 100))
    b = Image.new("RGB", (10, 10), (100, 100, 100))
    b.paste((200, 100, 100), (0, 0, 5, 10))
    mask = Image.new("L", (10, 10), 0)
    mask.paste(255, (0, 0, 5, 10))
    change = critics.product_change(a, b, mask)
    assert change == pytest.approx(100 / 255 / 3, abs=1e-3)
    assert critics.fidelity(change, 0.06) == 0.0 and critics.fidelity(0.0, 0.06) == 1.0


def test_framing_penalises_a_product_cut_off_by_the_frame():
    inside, edge = Image.new("L", (100, 100), 0), Image.new("L", (100, 100), 0)
    inside.paste(255, (30, 30, 70, 80))
    edge.paste(255, (30, 50, 70, 100))
    assert critics.framing(inside, "packshot") == 1.0 and critics.framing(edge, "packshot") < 0.5
    assert critics.framing(edge, "detail") < 1.0       # too small for a detail, but not penalised for the edge


def test_contrast_tells_a_lost_product_from_a_clear_one():
    mask = Image.new("L", (100, 100), 0)
    mask.paste(255, (30, 30, 70, 70))
    clear = Image.new("RGB", (100, 100), (240, 240, 240))
    clear.paste((20, 20, 20), (30, 30, 70, 70))
    lost = Image.new("RGB", (100, 100), (120, 120, 120))
    assert critics.contrast(clear, mask) > 0.9 and critics.contrast(lost, mask) < 0.1


def test_shortlist_skips_near_duplicates_and_failures():
    v = {"a": np.zeros(4), "b": np.zeros(4) + 0.001, "c": np.ones(4), "d": np.ones(4) * 0.5}
    cands = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.89}, {"id": "c", "score": 0.5}, {"id": "d", "score": 0.0}]
    assert shortlist.pick(cands, v, keep=3) == ["a", "c"]
    assert shortlist.pick(cands, v, keep=1) == ["a"]


# ---------------------------------------------------------------- the whole flow

def test_make_builds_candidates_shortlist_and_board(tmp_path):
    p = project(tmp_path)
    st = run.make(p, log=lambda m: None)
    assert len(st["candidates"]) == 3 * 2 * 1
    assert set(st["shortlist"]) == {"packshot", "lifestyle", "detail"}
    assert all(1 <= len(v) <= 2 for v in st["shortlist"].values())
    saved = json.loads((p.root / "stills" / "stills.json").read_text(encoding="utf-8"))
    c = saved["candidates"][0]
    assert {"direction", "seed", "backend", "model", "prompt", "scores", "image"} <= set(c)
    assert (p.root / "stills" / c["image"]).exists()
    board = (p.root / "stills" / "board.html").read_text(encoding="utf-8")
    assert "Example Shop" in board and "Shortlist" in board and c["image"] in board


def test_a_rerun_makes_nothing_new(tmp_path):
    p = project(tmp_path)
    run.make(p, log=lambda m: None)
    lines: list[str] = []
    st = run.make(p, log=lines.append)
    assert len(st["candidates"]) == 6 and "0 candidates to make" in lines[0]


def test_more_different_and_pick(tmp_path):
    p = project(tmp_path)
    st = run.make(p, log=lambda m: None)
    first = st["candidates"][0]["id"]
    st = run.make(p, more=first, log=lambda m: None)
    assert len(st["candidates"]) == 7 and st["candidates"][-1]["seed"] == 2
    st = run.make(p, different=True, log=lambda m: None)
    assert len(st["directions"]) == 4 and len(st["candidates"]) == 7 + 6
    st = run.make(p, pick=first, log=lambda m: None)
    assert st["picked"][first.split("-")[0]] == first
    assert "picked" in (p.root / "stills" / "board.html").read_text(encoding="utf-8")
    with pytest.raises(BuildError, match="no candidate"):
        run.make(p, pick="nope", log=lambda m: None)


def test_a_site_yaml_project_is_told_how_to_add_stills(tmp_path):
    (tmp_path / "s").mkdir()
    (tmp_path / "s" / "site.yaml").write_text("name: T\nsections: []\n", encoding="utf-8")
    with pytest.raises(BuildError, match="studio migrate"):
        run.make(Project(tmp_path / "s"), log=lambda m: None)


def test_a_missing_photo_is_a_build_error(tmp_path):
    p = project(tmp_path, photo="inputs/none.png")
    with pytest.raises(BuildError, match="outputs.stills.photo"):
        run.make(p, log=lambda m: None)


def test_generated_scenes_go_through_the_router(tmp_path, monkeypatch):
    from engine.router.core import Result

    class Painter:
        name, local, kinds = "painter", True, ("image",)

        def available(self):
            return True, ""

        def model(self, kind):
            return "p1"

        def run(self, job, out, model=None):
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (job.width, job.height), (90, 120, 160)).save(out)
            return Result(self.name, "p1", 0.0, path=out)

    monkeypatch.setattr(core, "backends", lambda: [Painter()])
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)
    p = project(tmp_path, shots=["lifestyle"])
    st = run.make(p, log=lambda m: None)
    assert {c["backend"] for c in st["candidates"]} == {"painter"}
    assert all("empty clear surface" in c["prompt"] for c in st["candidates"])
