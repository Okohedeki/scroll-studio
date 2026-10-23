"""Layered depth (`freeze.layers`): the planes' maths, the plate, the plane render, and the spec. No ComfyUI and no GPU:
the subjects are given (not found by Florence-2), the plate is filled smoothly, the render runs on torch's CPU."""
from __future__ import annotations

import numpy as np

from engine import layers as L
from engine import zoom_render


def test_push_pull_fills_a_hole_from_its_surroundings_and_leaves_the_rest():
    x = np.tile(np.linspace(0, 200, 96, dtype=np.float32), (64, 1))
    valid = np.ones((64, 96), np.float32)
    valid[20:44, 30:60] = 0
    damaged = x.copy()
    damaged[valid == 0] = 999
    out = L.push_pull(damaged, valid)
    assert np.abs(out[valid == 1] - x[valid == 1]).max() < 1e-4              # outside the hole: unchanged
    assert np.abs(out[valid == 0] - x[valid == 0]).mean() < 12               # inside: the surrounding gradient continued


def test_a_subject_is_a_card_with_no_tear_even_when_the_depth_map_has_a_step_in_it():
    depth = np.zeros((80, 120), np.float32)
    depth[:, :60] = 0.2
    depth[:, 60:] = 0.9                                                       # a depth step across the subject (a glitch)
    alpha = np.zeros_like(depth)
    alpha[10:70, 40:80] = 1.0
    pd = L.plane_depth(depth, [alpha])
    inside = pd[10:70, 40:80]
    assert np.abs(np.diff(inside, axis=1)).max() < 0.02                       # one card: no step at all across it
    assert 0.2 < inside.mean() < 0.9
    assert abs(pd[40, 90] - pd[40, 81]) < 0.15                                # and it carries on past the edge, no cliff
    near = np.zeros_like(depth)
    near[10:70, 100:115] = 1.0                                                # a second subject of the plane, at its own depth
    both = L.plane_depth(depth, [alpha, near])
    assert abs(both[40, 107] - 0.9) < 0.05 and abs(both[40, 60] - inside.mean()) < 0.05


def test_background_depth_has_no_hole():
    depth = np.full((60, 90), 0.1, np.float32)
    hole = np.zeros_like(depth)
    hole[10:50, 30:60] = 1
    depth[hole > 0] = 0.9                                                     # the subject's depth sits in the hole
    bg = L.background_depth(depth, hole)
    assert bg[30, 45] < 0.2


def test_group_planes_splits_at_the_biggest_gaps():
    items = [("a", 0.10), ("b", 0.12), ("c", 0.55), ("d", 0.57), ("e", 0.58), ("f", 0.95)]
    groups = L.group_planes(items, 3)
    names = [[items[i][0] for i in g] for g in groups]
    assert names == [["a", "b"], ["c", "d", "e"], ["f"]]                       # farthest first
    assert [[items[i][0] for i in g] for g in L.group_planes(items[:2], 3)] == [["a"], ["b"]]


def test_foreground_estimate_recovers_the_subjects_colour_at_a_soft_edge():
    fg = np.zeros((20, 40, 3), np.float32)                                    # black ink
    plate = np.full((20, 40, 3), 200, np.float32)
    a = np.zeros((20, 40), np.float32)
    a[:, 10:30] = 1
    a[:, 8:10] = [0.25, 0.7]
    a[:, 30:32] = [0.7, 0.25]
    pixel = a[..., None] * fg + (1 - a[..., None]) * plate
    est = L.estimate_foreground(pixel, a, plate)
    edge = est[:, 8:10]
    assert edge.max() < 12                                                    # the edge pixels are the ink, not ink + fog
    over = a[..., None] * est + (1 - a[..., None]) * plate
    assert np.abs(over - pixel).max() < 1.5                                   # composited over the plate: the frame again


def test_alpha_refines_to_the_tiles_own_edge():
    rgb = np.full((60, 120, 3), 230, np.uint8)
    rgb[:, 60:] = 20                                                          # the subject's edge is at x = 60
    parent = np.zeros((60, 120), np.float32)
    parent[:, 62:] = 1.0                                                      # the enlarged parent alpha is 2 px off
    a = L.refine_alpha(parent, rgb)
    assert a[30, 50] < 0.1 and a[30, 70] > 0.9
    assert a[30, 60:62].mean() > parent[30, 60:62].mean() + 0.2               # pulled back towards the edge


# ---------------------------------------------------------------- the render

def _scene(W=192, H=112):
    """A banded background, a near person-sized block with a dark outline, their depth, and the plate (background only)."""
    xs = np.arange(W)
    bg = np.zeros((H, W, 3), np.uint8)
    bg[:] = (np.where((xs // 12) % 2 == 0, 190, 150))[None, :, None]
    bg[..., 2] = 215
    frame = bg.copy()
    fg = (slice(30, 100), slice(80, 112))
    frame[fg] = (60, 90, 130)
    frame[30:100, 80:82] = 0
    frame[30:100, 110:112] = 0
    depth = np.full((H, W), 0.15, np.float32)
    depth[fg] = 0.85
    alpha = np.zeros((H, W), np.float32)
    alpha[fg] = 1.0
    return frame, bg, depth, alpha


def _layerset(frame, bg, depth, alpha):
    import cv2
    hole = cv2.dilate(alpha, np.ones((5, 5), np.uint8))
    return L.LayerSet(alpha[None], L.plane_depth(depth, [alpha])[None], hole, bg, L.background_depth(depth, hole), [["person"]])


def test_layered_render_at_rest_is_the_frame_and_in_motion_reveals_the_plate():
    frame, bg, depth, alpha = _scene()
    ls = _layerset(frame, bg, depth, alpha)
    cam = [{"t": 0, "box": [0.15, 0.15, 0.85, 0.85]}]
    kw = dict(size=(192, 112), seconds=3.0, device="cpu")
    flat = list(zoom_render.render_frames(frame, depth, [], cam, parallax=0.0, layers=ls, **kw))[0]
    assert flat.shape == (112, 192, 3)
    # a plain render of the same scene and a layered one, at the peak of the sway
    plain = list(zoom_render.render_frames(frame, depth, [], cam, parallax=2.0, **kw))[18]
    layered = list(zoom_render.render_frames(frame, depth, [], cam, parallax=2.0, layers=ls, **kw))[18]

    def off_palette(img):
        """Share of the strip beside the subject (background only there) whose colour is neither of the background's two
        bands: smeared subject, stretched edge, halo."""
        band = img[40:90, 40:70].astype(int)
        d = np.minimum(np.abs(band - [190, 190, 215]).sum(-1), np.abs(band - [150, 150, 215]).sum(-1))
        return float((d > 60).mean())
    assert off_palette(plain) > 0.05                                           # the plain warp smears at the depth jump
    assert off_palette(layered) < off_palette(plain) / 3
    assert off_palette(layered) < 0.02


def test_layered_render_has_no_fringe_of_the_old_background_on_a_moving_subject():
    frame, bg, depth, alpha = _scene()
    import cv2
    soft = cv2.GaussianBlur(alpha, (0, 0), 1.2)                                # an antialiased cut-out
    comp = bg.astype(np.float32) * (1 - soft[..., None]) + np.array([60, 90, 130], np.float32) * soft[..., None]
    ls = _layerset(comp.astype(np.uint8), bg, depth, soft)
    cam = [{"t": 0, "box": [0.15, 0.15, 0.85, 0.85]}]
    out = list(zoom_render.render_frames(comp.astype(np.uint8), depth, [], cam, size=(192, 112), seconds=3.0, parallax=2.0,
                                         layers=ls, device="cpu"))[18]
    assert out.shape == (112, 192, 3)
    assert np.isfinite(out).all()


# ---------------------------------------------------------------- a layered pyramid, end to end (no ComfyUI)

def test_layered_deep_zoom_builds_tiles_with_planes_and_renders(tmp_path, monkeypatch):
    from engine import zoom_build
    from engine.backends import comfy
    from engine.spec import Freeze
    monkeypatch.setattr(comfy, "alive", lambda: False)                          # the plate is filled smoothly, nothing else is called
    frame, bg, depth, alpha = _scene(192, 96)
    spec = Freeze.model_validate({"image": "x.png", "detail": {"strength": 0, "tile": 1.25},
                                  "layers": [{"box": [0.4, 0.3, 0.6, 0.9]}],
                                  "camera": [{"t": 0, "box": [0, 0, 1, 1]}, {"t": 0.5, "box": [0.42, 0.40, 0.50, 0.48], "hold": 0.2},
                                             {"t": 1, "box": [0, 0, 1, 1]}]})
    subj = [L.Subject("s1", alpha)]
    ls = L.build_planes(frame, depth, spec.layers, 7, tmp_path, lambda m: None, subjects=subj)
    assert ls.alpha.shape == (1, 96, 192) and ls.plate.shape == frame.shape and ls.bg_depth.shape == depth.shape
    assert ls.plate[50, 95].astype(int).sum() > 0 and abs(int(ls.plate[50, 95, 0]) - int(bg[50, 95, 0])) < 80    # painted out, roughly the background
    base = zoom_build.Level0(frame, depth, "k", ls)
    built = zoom_build.build_pyramid(tmp_path, base, spec, 2.0, (192, 96), "lanczos", lambda m: None)
    assert built and all(b.alpha is not None and b.alpha.shape[0] == 1 and b.bg.shape == b.rgb.shape for b in built)
    assert all(b.pdepth.shape[0] == 1 and b.bgdepth.shape == b.depth.shape for b in built)
    # reloading finds every tile (planes included) in the cache
    again = zoom_build.build_pyramid(tmp_path, base, spec, 2.0, (192, 96), "lanczos", lambda m: None)
    assert [b.key for b in again] == [b.key for b in built] and np.array_equal(again[0].alpha, built[0].alpha)
    frames = list(zoom_render.render_frames(frame, depth, [b.image() for b in built], spec.camera, size=(192, 96), seconds=2.0,
                                            parallax=0.8, device="cpu", layers=ls))
    assert len(frames) == 48 and all(np.isfinite(f).all() for f in frames)


def test_harmonize_matches_the_plates_tone_to_the_frame_at_the_hole_edge():
    H, W = 120, 160
    frame = np.tile(np.linspace(100, 200, W, dtype=np.float32), (H, 1))[..., None].repeat(3, axis=2).astype(np.uint8)
    hole = np.zeros((H, W), np.float32)
    hole[30:90, 60:100] = 1
    plate = frame.copy()
    plate[hole > 0] = np.clip(frame[hole > 0].astype(int) + 30, 0, 255)          # the editor made the hole 30 levels lighter
    fixed = L.harmonize(plate, frame, hole)
    edge = np.zeros_like(hole, bool)
    edge[32:88, 62:98] = True
    edge[40:80, 70:90] = False                                                   # the inside edge band
    assert np.abs(plate.astype(int) - frame.astype(int))[edge].mean() > 20
    assert np.abs(fixed.astype(int) - frame.astype(int))[edge].mean() < 8
    assert np.array_equal(fixed[hole == 0][:50], plate[hole == 0][:50])           # outside the hole: untouched


def test_planes_are_cached_and_only_the_shaping_settings_redo_the_cheap_part(tmp_path, monkeypatch):
    """The frame's planes are kept; asking again finds them; the subjects are found once even when `grow` changes."""
    from engine.backends import comfy
    from engine.spec import FreezeLayers
    monkeypatch.setattr(comfy, "alive", lambda: False)
    frame, bg, depth, alpha = _scene(192, 96)
    calls = []

    def fake_find(png, layers, work, log):
        calls.append(1)
        return [L.Subject("s1", alpha)]
    monkeypatch.setattr(L, "find_subjects", fake_find)
    png = tmp_path / "f.png"
    png.write_bytes(b"x")
    spec = FreezeLayers.model_validate({"subjects": [{"box": [0.4, 0.3, 0.6, 0.9]}]})
    a = L.build_cached(tmp_path, png, frame, depth, spec, 7, "k", lambda m: None)
    b = L.build_cached(tmp_path, png, frame, depth, spec, 7, "k", lambda m: None)
    assert len(calls) == 1 and np.array_equal(a.alpha > 0.5, b.alpha > 0.5) and b.ids == [["s1"]]
    wider = FreezeLayers.model_validate({"subjects": [{"box": [0.4, 0.3, 0.6, 0.9]}], "grow": 9})
    c = L.build_cached(tmp_path, png, frame, depth, wider, 7, "k", lambda m: None)
    assert len(calls) == 1                                                    # the subjects were not looked for again
    assert c.hole.sum() > a.hole.sum()
    assert (tmp_path / "layers" / "planes.jpg").exists()
