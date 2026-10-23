"""Frozen-moment beats (`freeze:`): the spec, the camera path, the 2.5D render, the beat's stage and cache, `beat_frame`
images, and the storyboard. No ComfyUI and no GPU: the render runs on torch's CPU, depth is stubbed, upscale is off."""
from __future__ import annotations

import shutil
import textwrap

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from engine import freeze as fz
from engine import freeze_beats as fb
from engine.project import Project
from engine.spec import Beat, ImageInput

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")

CAMERA = [{"t": 0, "box": [0, 0, 1, 1]},
          {"t": 0.3, "box": [0.25, 0.2, 0.75, 0.68]},
          {"t": 0.55, "box": [0.26, 0.42, 0.58, 0.753], "hold": 0.1},
          {"t": 0.8, "box": [0.34, 0.732, 0.6, 1.0]},
          {"t": 1, "box": [0.25, 0.2, 0.75, 0.68]}]


def beat(**kw) -> Beat:
    return Beat.model_validate({"id": "f", "seconds": 12, **kw})


# ---------------------------------------------------------------- spec

def test_freeze_beat_validates_and_keeps_the_owners_example():
    b = beat(freeze={"from": "walk", "upscale": 2, "camera": CAMERA, "parallax": 0.6, "ease": "inOutSine"})
    assert b.freeze.from_ == "walk" and b.freeze.upscale == 2 and len(b.freeze.camera) == 5
    assert b.prompt == "" and b.motion == ""          # not needed for a frozen moment
    # round trip through the field name too (Project.save dumps by field name)
    assert Beat.model_validate(b.model_dump(mode="json")).freeze.from_ == "walk"


def test_generated_beats_still_need_prompt_motion_and_at_most_ten_seconds():
    with pytest.raises(ValidationError, match="prompt"):
        Beat.model_validate({"id": "a", "seconds": 4})
    with pytest.raises(ValidationError, match="1 to 10"):
        Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "seconds": 12})
    Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "seconds": 10})


@pytest.mark.parametrize("freeze, msg", [
    ({}, "exactly one of"),
    ({"from": "a", "image": "x.png"}, "exactly one of"),
    ({"from": "f"}, "own frame"),
    ({"from": "a", "camera": [{"t": 0.5, "box": [0.5, 0, 0.4, 1]}]}, "x0 < x1"),
    ({"from": "a", "camera": [{"t": 0.5, "box": [0, 0, 1, 1]}, {"t": 0.4, "box": [0, 0, 1, 1]}]}, "forward in time"),
    ({"from": "a", "camera": [{"t": 0.5, "box": [0, 0, 1, 1], "hold": 0.3}, {"t": 0.7, "box": [0, 0, 1, 1]}]}, "forward in time"),
    ({"from": "a", "camera": [{"t": 0.9, "box": [0, 0, 1, 1], "hold": 0.3}]}, "runs past"),
    ({"from": "a", "upscale": 8}, "upscale"),
])
def test_freeze_spec_errors(freeze, msg):
    with pytest.raises(ValidationError, match=msg):
        beat(freeze=freeze)


def test_freeze_does_not_mix_with_generation_fields():
    with pytest.raises(ValidationError, match="image"):
        beat(image="a.png", freeze={"from": "a"})
    with pytest.raises(ValidationError, match="strength"):
        beat(strength=0.8, freeze={"from": "a"})


def test_beat_frame_input_and_keys_that_did_not_move():
    ref = ImageInput.model_validate({"beat_frame": {"beat": "freeze", "at": "last", "pick": "sharpest"}})
    assert ref.beat_frame.beat == "freeze" and ImageInput(beat_frame={"beat": "x", "at": 2.5}).beat_frame.at == 2.5
    from engine.inputs import image_key, stable_dump
    plain = ImageInput(file="inputs/a.png")
    assert "beat_frame" not in stable_dump(plain)             # an unset new field never reaches an old cache key
    assert image_key("inputs/a.png") == {"file": "inputs/a.png"}


# ---------------------------------------------------------------- the camera path

def test_box_view_widens_to_the_aspect_and_stays_inside_the_frame():
    v = fz.box_view([0.26, 0.42, 0.58, 0.753])               # 0.32 wide, 0.333 tall: widened to the taller side
    assert v.w == pytest.approx(0.333, abs=1e-3)
    assert v.cx == pytest.approx(0.42, abs=1e-3)
    v = fz.box_view([0.8, 0.8, 1.0, 1.0])
    assert v.cx + v.w / 2 <= 1 + 1e-9 and v.cy + v.w / 2 <= 1 + 1e-9
    assert fz.box_view([0, 0, 1, 1]).w == 1.0


@pytest.mark.parametrize("ease", ["inOutSine", "inOutQuad", "inOutCubic", "inOutQuart", "linear", "flow"])
def test_path_reaches_every_key_at_its_time(ease):
    path = fz.CameraPath(CAMERA, ease)
    for k in CAMERA:
        want = fz.box_view(k["box"])
        got = path.at(k["t"])
        assert (got.cx, got.cy, got.w) == pytest.approx((want.cx, want.cy, want.w), abs=1e-6), (ease, k["t"])


def test_hold_rests_and_a_key_before_the_first_t_rests_on_it():
    path = fz.CameraPath(CAMERA, "inOutSine")
    a, b = path.at(0.55), path.at(0.64)
    assert (a.cx, a.cy, a.w) == pytest.approx((b.cx, b.cy, b.w))   # the 0.1 hold
    late = fz.CameraPath([{"t": 0.5, "box": [0.2, 0.2, 0.6, 0.6]}, {"t": 1, "box": [0, 0, 1, 1]}], "inOutSine")
    assert late.at(0.0) == late.at(0.4) == fz.box_view([0.2, 0.2, 0.6, 0.6])
    assert fz.CameraPath([], "flow").at(0.5).w == 1.0             # no camera: the whole frame


@pytest.mark.parametrize("ease", ["inOutSine", "inOutQuad", "inOutCubic", "flow"])
def test_path_has_no_jerk_at_keys(ease):
    """Speed is continuous across every key (no step in velocity), and a flow path really keeps moving through keys."""
    path = fz.CameraPath(CAMERA, ease)
    ts = np.linspace(0, 1, 4801)
    p = np.array([path.params(t) for t in ts])
    v = np.diff(p, axis=0) / np.diff(ts)[:, None]
    assert np.abs(np.diff(v, axis=0)).max() < 0.25 * np.abs(v).max()        # no discontinuity in speed anywhere
    if ease == "flow":
        i = int(np.argmin(abs(ts - 0.3)))
        assert np.abs(v[i]).max() > 0.05                                    # not resting at the 0.3 key (it has no hold)
    i = int(np.argmin(abs(ts - 0.55)))
    assert np.abs(v[i]).max() < 1e-6                                       # resting on the held key


def test_unknown_ease_is_an_error():
    with pytest.raises(Exception, match="ease"):
        fz.CameraPath(CAMERA, "bounce")


# ---------------------------------------------------------------- sharpness

def test_sharpest_prefers_the_sharp_frame_where_the_camera_looks():
    import cv2
    rng = np.random.default_rng(1)
    base = (rng.random((96, 160)) * 255).astype(np.uint8)
    sharp = np.dstack([base] * 3)
    soft = cv2.GaussianBlur(sharp, (0, 0), 2.0)
    assert fz.sharpest([soft, sharp, soft]) == 1
    assert fz.sharpest([sharp, sharp.copy()]) == 1                      # a tie goes to the later frame
    # sharp only inside the box the camera visits: that frame wins even though the other is sharper elsewhere
    a, b = soft.copy(), soft.copy()
    a[:, 80:] = sharp[:, 80:]
    b[:, :80] = sharp[:, :80]
    view = [fz.View(0.75, 0.5, 0.4)]
    assert fz.sharpest([b, a], view) == 1 and fz.sharpest([a, b], view) == 0


# ---------------------------------------------------------------- the render

def _scene(w=96, h=64):
    """A frame with a left half and a right half, and a depth map with the right half near."""
    rgb = np.zeros((h, w, 3), np.uint8)
    rgb[:, : w // 2] = (40, 80, 160)
    rgb[:, w // 2:] = (200, 160, 40)
    rgb[h // 2 - 3: h // 2 + 3] = (255, 255, 255)
    depth = np.zeros((h, w), np.float32)
    depth[:, w // 2:] = 0.9
    return rgb, depth


def test_first_frame_is_the_frozen_frame_and_render_is_deterministic():
    rgb, depth = _scene()
    kw = dict(size=(96, 64), seconds=1.0, parallax=0.8, grain=0.02)
    a = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", **kw))
    b = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", **kw))
    assert len(a) == 24 and a[0].shape == (64, 96, 3)
    assert all(np.array_equal(x, y) for x, y in zip(a, b))
    flat = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", size=(96, 64), seconds=1.0, parallax=0.0))
    # no sway on the full-frame first view: it is the source, to within the resample
    assert np.abs(flat[0].astype(int) - rgb.astype(int)).mean() < 2.0


def test_trim_skips_the_first_frames():
    rgb, depth = _scene()
    full = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", size=(96, 64), seconds=1.0))
    cut = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", size=(96, 64), seconds=1.0, first_frame=6))
    assert len(cut) == len(full) - 6 and np.array_equal(cut[0], full[6])


def test_parallax_moves_near_pixels_more_than_far_ones():
    rgb, depth = _scene(192, 128)
    cam = [{"t": 0, "box": [0.25, 0.25, 0.75, 0.75]}]            # zoomed in: room to sway
    flat = list(fz.render_frames(rgb, depth, cam, device="cpu", size=(192, 128), seconds=3.0, parallax=0.0))
    deep = list(fz.render_frames(rgb, depth, cam, device="cpu", size=(192, 128), seconds=3.0, parallax=2.0))
    i = 18                                                         # a quarter in: the sway is at its peak
    diff = np.abs(deep[i].astype(int) - flat[i].astype(int)).sum(axis=(0, 2))   # per column
    assert diff.max() > 0
    # the flat frame and the deep one agree on the focus plane far from the seam: the shift is at the near/far boundary
    assert np.abs(deep[i].astype(int) - flat[i].astype(int)).mean() < 40


def test_sway_is_zero_where_the_view_cannot_move():
    rgb, depth = _scene()
    tl = fz.Timeline(fz.CameraPath([{"t": 0, "box": [0, 0, 1, 1]}], "inOutSine"), 4.0, depth, 1.0)
    p = tl.at(0.25)
    assert abs(p["sx"]) < 1e-9 and abs(p["sy"]) < 1e-9 and abs(p["e"]) < 1e-9   # a full-frame view cannot sway


def test_motion_blur_and_grain_change_the_frames_not_their_number():
    rgb, depth = _scene()
    base = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", size=(96, 64), seconds=1.0))
    blur = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", size=(96, 64), seconds=1.0, blur=0.5))
    grain = list(fz.render_frames(rgb, depth, CAMERA, device="cpu", size=(96, 64), seconds=1.0, grain=0.05))
    assert len(blur) == len(grain) == len(base)
    assert not np.array_equal(base[10], blur[10]) and not np.array_equal(base[10], grain[10])
    assert not np.array_equal(grain[3], grain[4])                  # the grain is different every frame


# ---------------------------------------------------------------- a project: stage, cache, beat_frame, storyboard

SPEC = textwrap.dedent("""\
    name: T
    theme: { preset: night }
    sections:
      - id: story
        type: film
        beat_res: [128, 96]
        beats:
          - id: walk
            prompt: a crowd
            motion: it walks
            image: inputs/still.png
          - id: freeze
            seconds: 2
            freeze:
              from: walk
              camera:
                - { t: 0, box: [0, 0, 1, 1] }
                - { t: 1, box: [0.25, 0.25, 0.75, 0.75] }
          - id: still
            seconds: 2
            freeze:
              image: inputs/still.png
              camera: [{ t: 0, box: [0.5, 0.5, 1, 1] }]
          - id: walkon
            prompt: they walk on
            motion: they walk
            image: { beat_frame: { beat: freeze, at: last } }
        steps:
          - { title: Hello, state: { beat: freeze } }
""")


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "p"
    (root / "inputs").mkdir(parents=True)
    (root / "site.yaml").write_text(SPEC, encoding="utf-8")
    from PIL import Image
    rng = np.random.default_rng(3)
    Image.fromarray((rng.random((96, 128, 3)) * 255).astype(np.uint8)).save(root / "inputs" / "still.png")
    from engine.backends import depth as depthmod
    monkeypatch.setattr(depthmod, "estimate", lambda img, size="small": np.tile(np.linspace(0, 1, img.width, dtype=np.float32),
                                                                             (img.height, 1)))
    return Project(root)


def _fake_walk_clip(project, n=24):
    """What a rendered generated beat leaves behind: frames/ and clip.mp4 (the last frame brighter than the rest)."""
    from PIL import Image
    sec = project.load().sections[0]
    bdir = fb.beat_dir(project, sec, sec.beats[0])
    (bdir / "frames").mkdir(parents=True)
    for i in range(n):
        Image.fromarray(np.full((96, 128, 3), 10 * i, np.uint8)).save(bdir / "frames" / f"{i + 1:04d}.png")
    from engine.project import ffmpeg
    ffmpeg("-framerate", "24", "-i", bdir / "frames" / "%04d.png", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
           bdir / "clip.mp4")
    return bdir


@needs_ffmpeg
def test_freeze_beat_renders_into_its_clip_and_caches_by_step(project):
    _fake_walk_clip(project)
    site = project.load()
    sec = site.sections[0]
    b = sec.beats[1]
    logs = []
    clip = fb.render_beat(project, sec, b, logs.append)
    bdir = fb.beat_dir(project, sec, b)
    assert clip == bdir / "clip.mp4" and clip.exists()
    info = __import__("engine.project", fromlist=["probe"]).probe(clip)
    assert (int(info["width"]), int(info["height"])) == (128, 96)
    assert round(float(info["duration"]) * 24) == 48                                       # 2 s at 24 fps
    for name in ("frozen.png", "up.png", "depth.npy", "first.png", "last.png"):
        assert (bdir / name).exists(), name
    # nothing changed: nothing is redone
    stamp = (bdir / "clip.mp4").stat().st_mtime_ns
    logs.clear()
    fb.render_beat(project, sec, b, logs.append)
    assert (bdir / "clip.mp4").stat().st_mtime_ns == stamp and any("up to date" in m for m in logs)
    # a new camera redoes only the render: the frozen frame, upscale and depth are kept
    kept = {n: (bdir / n).stat().st_mtime_ns for n in ("frozen.png", "up.png", "depth.npy")}
    spec = yaml.safe_load((project.root / "site.yaml").read_text())
    spec["sections"][0]["beats"][1]["freeze"]["camera"][1]["box"] = [0.3, 0.3, 0.7, 0.7]
    project.save(spec)
    sec2 = project.load().sections[0]
    fb.render_beat(project, sec2, sec2.beats[1], logs.append)
    assert {n: (bdir / n).stat().st_mtime_ns for n in kept} == kept
    assert (bdir / "clip.mp4").stat().st_mtime_ns != stamp


@needs_ffmpeg
def test_stage_key_follows_the_source_clip_and_the_spec(project):
    sec = project.load().sections[0]
    walk, frz, still = sec.beats[0], sec.beats[1], sec.beats[2]
    assert fb.beat_key(project, sec, frz)["from"] is None            # walk is not rendered yet
    _fake_walk_clip(project)
    k1 = fb.beat_key(project, sec, frz)
    assert k1["from"]["path"] == "clip.mp4" and "freeze" in k1 and "prompt" not in k1
    clip = fb.beat_clip_path(project, sec, walk)
    st = clip.stat()
    import os
    os.utime(clip, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))      # walk re-rendered: freeze must re-freeze
    assert fb.beat_key(project, sec, frz) != k1
    assert fb.beat_key(project, sec, still)["image"] == {"path": "still.png", "size": (project.root / "inputs" / "still.png").stat().st_size,
                                                         "mtime": int((project.root / "inputs" / "still.png").stat().st_mtime)}


@needs_ffmpeg
def test_freeze_takes_the_sharpest_of_the_last_frames_of_a_generated_beat(project):
    from PIL import Image
    bdir = _fake_walk_clip(project)
    rng = np.random.default_rng(5)
    noisy = (rng.random((96, 128, 3)) * 255).astype(np.uint8)
    Image.fromarray(noisy).save(bdir / "frames" / "0021.png")           # frame 21 of 24: the only one with detail
    sec = project.load().sections[0]
    fb.render_beat(project, sec, sec.beats[1], lambda m: None)
    frozen = np.asarray(Image.open(fb.beat_dir(project, sec, sec.beats[1]) / "frozen.png"))
    assert np.abs(frozen.astype(int) - noisy.astype(int)).mean() < 1.0          # (the frames were fitted at 128x96: same size)


@needs_ffmpeg
def test_pick_last_takes_the_very_last_frame(project):
    from PIL import Image
    _fake_walk_clip(project)
    spec = yaml.safe_load((project.root / "site.yaml").read_text())
    spec["sections"][0]["beats"][1]["freeze"]["pick"] = "last"
    project.save(spec)
    sec = project.load().sections[0]
    fb.render_beat(project, sec, sec.beats[1], lambda m: None)
    frozen = np.asarray(Image.open(fb.beat_dir(project, sec, sec.beats[1]) / "frozen.png"))
    assert abs(float(frozen.mean()) - 230.0) < 1.0                                 # frame 24 is a flat 230


@needs_ffmpeg
def test_beat_frame_gives_the_frozen_beats_last_frame_and_follows_a_rerender(project):
    from PIL import Image
    from engine.inputs import resolve_image
    _fake_walk_clip(project)
    sec = project.load().sections[0]
    ref = sec.beats[3].image
    assert ref.beat_frame.beat == "freeze"
    p = resolve_image(project, ref, lambda m: None)                 # renders the frozen beat on the way
    last = fb.beat_dir(project, sec, sec.beats[1]) / "last.png"
    assert last.exists()
    assert np.array_equal(np.asarray(Image.open(p)), np.asarray(Image.open(last)))
    assert resolve_image(project, ref, lambda m: None) == p          # cached
    assert fb.beat_frame_deps(project, ref)[0]["clip"]["path"] == "clip.mp4"


def test_beat_frame_of_a_beat_that_is_not_rendered(project):
    from engine.inputs import resolve_image
    from engine.project import BuildError
    ref = ImageInput(beat_frame={"beat": "walk"})
    with pytest.raises(BuildError, match="not rendered"):
        resolve_image(project, ref, lambda m: None)
    fb.set_lenient(True)
    try:                                                              # under --only the storyboard still stands in
        p = resolve_image(project, ref, lambda m: None)
        assert p.name == "still.png"
    finally:
        fb.set_lenient(False)


def test_beat_frame_names_a_beat_that_exists(project):
    from engine.project import BuildError
    with pytest.raises(BuildError, match="not found"):
        fb.find_beat(project, "nope")


def test_stand_in_clip_is_a_flat_camera_move_over_the_storyboard_still(project):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not installed")
    from engine.project import probe
    sec = project.load().sections[0]
    out = fb.beat_dir(project, sec, sec.beats[2]) / "standin.mp4"
    fb.standin_clip(project, sec, sec.beats[2], out, (128, 96), lambda m: None)
    assert out.exists() and round(float(probe(out)["duration"]) * 24) == 48
    stamp = out.stat().st_mtime_ns
    fb.standin_clip(project, sec, sec.beats[2], out, (128, 96), lambda m: None)
    assert out.stat().st_mtime_ns == stamp                              # kept: nothing changed


def test_plan_prices_a_frozen_beat_apart_from_a_generated_one(project):
    from engine import plan as planmod
    sec = project.load().sections[0]
    assert planmod.units(sec, "beat_freeze") == ("film:freeze", 2.0)
    assert planmod.units(sec, "beat_walk")[0] == "film:beat"
    spec = yaml.safe_load((project.root / "site.yaml").read_text())
    spec["sections"][0]["beats"][1]["freeze"]["upscale"] = 2
    project.save(spec)
    assert planmod.units(project.load().sections[0], "beat_freeze")[0] == "film:freeze_up"


def test_storyboard_board_has_fields_for_a_frozen_beat(project):
    from engine.storyboard.edit import shots
    board = shots.build(project)
    s = next(x for x in board.shots if x.id == "freeze")
    names = {f.name for f in s.fields}
    assert {"seconds", "upscale", "parallax", "ease", "pick", "cam0.t", "cam1.x0", "cam1.y1", "grain"} <= names
    assert "prompt" not in names and "motion" not in names
    still = next(x for x in board.shots if x.id == "still")
    assert [sl.label for sl in still.slots] == ["frozen image"] and "pick" not in {f.name for f in still.fields}
    cam = next(f for f in s.fields if f.name == "cam1.x0")
    assert cam.paths[0] == ("sections", 0, "beats", 1, "freeze", "camera", 1, "box", 0)
