"""Named camera moves on frozen moments (`freeze.move`): the spec, the render along the move's rig, the beat's stage and
cache, and what the storyboard, the stand-ins and the polish report read as its camera. No ComfyUI and no GPU: the render
runs on torch's CPU and depth is stubbed."""
from __future__ import annotations

import shutil
import textwrap

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from engine import camera_moves as cm
from engine import freeze as fz
from engine import freeze_beats as fb
from engine.project import Project
from engine.spec import Beat

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def beat(**freeze) -> Beat:
    return Beat.model_validate({"id": "f", "seconds": 4, "freeze": {"image": "x.png", **freeze}})


# ---------------------------------------------------------------- spec

def test_move_by_name_or_with_settings():
    assert beat(move="dolly-zoom").freeze.move.move == "dolly-zoom"
    m = beat(move={"move": "orbit-left", "amount": 0.8, "at": [0.4, 0.6]}).freeze.move
    assert (m.move, m.amount, m.at) == ("orbit-left", 0.8, (0.4, 0.6))
    b = beat(move="crane-up")
    assert Beat.model_validate(b.model_dump(mode="json", by_alias=True)).freeze.move.move == "crane-up"   # round trip
    assert beat().freeze.move is None


@pytest.mark.parametrize("freeze, msg", [
    ({"move": "dolly-zoom", "camera": [{"t": 0, "box": [0, 0, 1, 1]}]}, "not both"),
    ({"move": "dolly-zoom", "detail": {}}, "detail"),
    ({"move": "orbit-left", "layers": "auto"}, "layers"),
    ({"move": {"move": "dolly-in", "at": [1.2, 0.5]}}, "inside 0-1"),
    ({"move": "spin"}, "move"),
    ({"move": {"move": "dolly-in", "amount": 3}}, "amount"),
])
def test_move_errors(freeze, msg):
    with pytest.raises(ValidationError, match=msg):
        beat(**freeze)


# ---------------------------------------------------------------- the render

def _scene(w=192, h=128):
    """A textured frame: far on the left, near on the right, and a subject strip in the middle at mid depth."""
    rng = np.random.default_rng(1)
    rgb = (rng.random((h, w, 3)) * 255).astype(np.uint8)
    depth = np.full((h, w), 0.1, np.float32)
    depth[:, int(w * 0.62):] = 0.9
    depth[:, int(w * 0.42):int(w * 0.58)] = 0.5
    return rgb, depth


def _diff(a, b, x0, x1):
    w = a.shape[1]
    return float(np.abs(a[:, int(w * x0):int(w * x1)].astype(int) - b[:, int(w * x0):int(w * x1)].astype(int)).mean())


def test_render_has_the_beats_frames_and_is_deterministic():
    rgb, depth = _scene()
    kw = dict(size=(96, 64), seconds=1.0, at=(0.5, 0.5), grain=0.02)
    a = list(fz.render_move_frames(rgb, depth, "dolly-zoom", device="cpu", **kw))
    b = list(fz.render_move_frames(rgb, depth, "dolly-zoom", device="cpu", **kw))
    assert len(a) == 24 and a[0].shape == (64, 96, 3)
    assert all(np.array_equal(x, y) for x, y in zip(a, b))
    cut = list(fz.render_move_frames(rgb, depth, "dolly-zoom", device="cpu", first_frame=6, **kw))
    assert len(cut) == 18 and np.array_equal(cut[0], a[6])


def test_dolly_zoom_keeps_the_subject_and_moves_the_rest():
    """The rig's push cancels on the focus plane (the subject's depth at `at`): the subject strip holds while the near
    and far sides change."""
    rgb, depth = _scene()
    fr = list(fz.render_move_frames(rgb, depth, "dolly-zoom", device="cpu", size=(192, 128), seconds=1.0, at=(0.5, 0.5)))
    first, last = fr[0], fr[-1]
    subject = _diff(first, last, 0.46, 0.54)
    near = _diff(first, last, 0.7, 0.9)
    assert near > 3 * max(subject, 1.0)


def test_orbit_pivots_on_the_subject():
    rgb, depth = _scene()
    fr = list(fz.render_move_frames(rgb, depth, "orbit-left", device="cpu", size=(192, 128), seconds=1.0, at=(0.5, 0.5)))
    assert _diff(fr[0], fr[-1], 0.7, 0.9) > 3 * max(_diff(fr[0], fr[-1], 0.46, 0.54), 1.0)


def test_the_move_follows_the_same_rig_as_a_generated_beats_guide():
    """Frame by frame, the render is the renderer at the rig's camera (what camera_moves.render flies for a guide)."""
    rgb, depth = _scene()
    n = 12
    ours = list(fz.render_move_frames(rgb, depth, "dolly-in", device="cpu", size=(96, 64), seconds=n / 24, at=(0.5, 0.5)))
    focus = cm.focus_depth(depth, (0.5, 0.5))
    theirs = list(cm.render(rgb, depth, cm.rig("dolly-in", n, 1.0, (0.5, 0.5)), size=(96, 64), focus=focus, device="cpu"))
    assert len(ours) == n and all(np.array_equal(x, y) for x, y in zip(ours, theirs))


def test_a_whip_pan_carries_its_recipes_motion_blur():
    rgb, depth = _scene()
    sharp = list(fz.render_move_frames(rgb, depth, "dolly-in", device="cpu", size=(96, 64), seconds=1.0))
    whip = list(fz.render_move_frames(rgb, depth, "whip-pan", device="cpu", size=(96, 64), seconds=1.0))
    assert len(whip) == len(sharp)
    # mid-pan, the blurred frame has less fine detail than the source at the same scale
    lap = lambda im: float(np.abs(np.diff(im.astype(float), axis=1)).mean())
    assert lap(whip[11]) < lap(sharp[0])


# ---------------------------------------------------------------- in a project

SPEC = textwrap.dedent("""\
    name: T
    theme: { preset: night }
    sections:
      - id: story
        type: film
        beat_res: [128, 96]
        beats:
          - id: still
            seconds: 1
            freeze:
              image: inputs/still.png
              move: { move: dolly-zoom, at: [0.5, 0.5] }
          - id: keyed
            seconds: 1
            freeze:
              image: inputs/still.png
              camera: [{ t: 0, box: [0, 0, 1, 1] }, { t: 1, box: [0.25, 0.25, 0.75, 0.75] }]
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


def test_camera_keys_are_the_moves_view_for_a_move_and_the_keys_otherwise(project):
    sec = project.load().sections[0]
    mv, keyed = sec.beats[0].freeze, sec.beats[1].freeze
    keys = fb.camera_keys(mv)
    assert keys == cm.view_keys("dolly-zoom", 1.0, (0.5, 0.5))
    v = fb.camera_path(mv).at(1.0)
    assert abs(v.w - 0.7) < 1e-6                                      # a dolly zoom flies a constant 0.7 view
    assert fb.camera_keys(keyed) == list(keyed.camera)
    assert fb.camera_path(keyed).at(1.0).w == pytest.approx(0.5)


@needs_ffmpeg
def test_a_moving_freeze_renders_and_caches_by_step(project):
    sec = project.load().sections[0]
    b = sec.beats[0]
    logs = []
    clip = fb.render_beat(project, sec, b, logs.append)
    bdir = fb.beat_dir(project, sec, b)
    assert clip.exists() and (bdir / "first.png").exists() and (bdir / "last.png").exists()
    stamp = clip.stat().st_mtime_ns
    logs.clear()
    fb.render_beat(project, sec, b, logs.append)
    assert clip.stat().st_mtime_ns == stamp and any("up to date" in m for m in logs)
    # a new amount redoes only the render: the frozen frame, upscale and depth are kept
    kept = {n: (bdir / n).stat().st_mtime_ns for n in ("frozen.png", "up.png", "depth.npy")}
    spec = yaml.safe_load((project.root / "site.yaml").read_text())
    spec["sections"][0]["beats"][0]["freeze"]["move"]["amount"] = 0.5
    project.save(spec)
    sec2 = project.load().sections[0]
    fb.render_beat(project, sec2, sec2.beats[0], logs.append)
    assert {n: (bdir / n).stat().st_mtime_ns for n in kept} == kept
    assert clip.stat().st_mtime_ns != stamp


def test_a_keyed_freezes_render_key_is_unchanged_by_the_new_field(project):
    """Keyed frozen beats rendered before `move` existed keep their stamps: the field is in the render key only when set."""
    sec = project.load().sections[0]
    assert "move" not in fb.beat_key(project, sec, sec.beats[1])["freeze"]
    assert fb.beat_key(project, sec, sec.beats[0])["freeze"]["move"]["move"] == "dolly-zoom"


@needs_ffmpeg
def test_stand_in_and_storyboard_read_the_move(project):
    from engine.storyboard.cards import _box
    sec = project.load().sections[0]
    out = fb.beat_dir(project, sec, sec.beats[0]) / "standin.mp4"
    fb.standin_clip(project, sec, sec.beats[0], out, (128, 96), lambda m: None)
    assert out.exists()
    assert _box({"box": [0, 0, 1, 1]}) == [0, 0, 1, 1]


def test_polish_reads_the_moves_tightest_view(project):
    from engine.polish.run import beat_zoom
    sec = project.load().sections[0]
    assert beat_zoom(sec.beats[0], sec) == pytest.approx(0.7)
    assert beat_zoom(sec.beats[1], sec) == pytest.approx(0.5)
