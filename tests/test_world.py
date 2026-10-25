"""type in the world: the spec (`place: {kind: behind | surface | sky}`), the geometry (surfaces, planes, matrices, occlusion),
planar tracking, steady depth, and the whole build of a film's `world` config with the models replaced by synthetic ones
(depth, SAM masks, Florence-2 boxes): stages, caching, the atlas video, the plan, the page markup, the report.
No ComfyUI, Blender or GPU is needed."""
from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from engine import world, world_depth, world_math as wm, world_track as wt
from engine.config import settings
from engine.project import BuildContext, BuildError, Project
from engine.spec import FilmScene, ParallaxScene, Site, Step, WorldPlace

FFMPEG = shutil.which(settings()["ffmpeg"]) or shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg is not on the PATH")


# ---------------------------------------------------------------- the spec

STEPS = yaml.safe_load(textwrap.dedent('''\
    - { title: "Cold from <em>the source.</em>", at: [0.0, 0.2], intro: true }
    - title: "Down to <em>the water.</em>"
      at: [0.3, 0.5]
      place: { kind: behind, at: "the spruce tree", x: 0.58, y: 0.3, size: 0.6 }
    - title: "Stay <em>cold.</em>"
      at: [0.55, 0.75]
      place: { kind: surface, at: "the wooden deck floor", size: 0.62, y: 0.74 }
    - { title: "Still cold <em>at noon.</em>", at: [0.8, 0.98], place: sky }
    - { title: "Kept as it was", at: [0.2, 0.3], place: bottom-left }
'''))


def test_the_documented_example_validates():
    f = FilmScene.model_validate({"id": "s", "type": "film", "video": "a.mp4", "layout": "overlay", "steps": STEPS})
    kinds = [st.world.kind if st.world else None for st in f.steps]
    assert kinds == [None, "behind", "surface", "sky", None]
    assert f.steps[1].world.at == "the spruce tree" and f.steps[1].world.size == 0.6
    assert f.steps[3].world.kind == "sky" and f.steps[3].corner is None           # `place: sky` is shorthand
    assert f.steps[4].corner == "bottom-left" and f.steps[4].world is None         # caption positions work as they always did
    assert f.steps[0].place is None and f.steps[0].corner is None


def test_a_caption_without_place_or_with_a_corner_is_unchanged():
    assert Step.model_validate({"title": "x"}).place is None
    for corner in ("left", "right", "center", "top-left", "top-right", "bottom-left", "bottom-right"):
        st = Step.model_validate({"title": "x", "place": corner})
        assert st.place == corner and st.corner == corner and st.world is None
    with pytest.raises(ValidationError):
        Step.model_validate({"title": "x", "place": "middle"})


@pytest.mark.parametrize("patch", [
    {"kind": "floating"}, {"kind": "behind", "nope": 1}, {"kind": "sky", "size": 0}, {"kind": "sky", "haze": 2},
    {"kind": "sky", "lines": 9}, {"kind": "surface", "quad": [[0, 0], [1, 0]]}, {"kind": "sky", "color": 3}, {},
])
def test_bad_placements_are_refused(patch):
    with pytest.raises(ValidationError):
        WorldPlace.model_validate(patch)


def test_defaults_and_the_schema_document_the_fields():
    w = WorldPlace.model_validate({"kind": "behind"})
    assert w.align == "center" and w.color == "auto" and w.gap == 0.05 and w.at is None and w.anchor is None
    assert world.resolved(w) == {"kind": "behind", "x": 0.5, "y": 0.5, "size": 0.5, "track": 0.0, "haze": 0.12}
    assert world.resolved(WorldPlace.model_validate({"kind": "sky"}))["y"] == 0.3
    schema = Site.model_json_schema()
    wp = schema["$defs"]["WorldPlace"]
    assert set(wp["properties"]) >= {"kind", "at", "x", "y", "size", "lines", "align", "caps", "track", "weight", "color", "anchor", "gap",
                                     "follow", "haze", "fog", "blur", "wear", "relief", "quad", "angle", "slant", "track_model"}
    assert wp["properties"]["kind"]["enum"] == ["behind", "surface", "sky"]
    assert all(p.get("description") for p in wp["properties"].values())             # the schema is the contract for the UI and MCP
    assert "WorldPlace" in json.dumps(schema["$defs"]["Step"]["properties"]["place"])
    assert "depth_model" in schema["$defs"]["FilmScene"]["properties"]


def test_the_title_round_trips_through_yaml_dumps():
    f = FilmScene.model_validate({"id": "s", "type": "film", "video": "a.mp4", "steps": STEPS})
    back = FilmScene.model_validate(json.loads(f.model_dump_json()))
    assert back.steps[1].world.at == "the spruce tree" and back.steps[3].world.kind == "sky"
    dumped = f.model_dump(mode="json", include={"steps"})["steps"][2]["place"]
    assert dumped["kind"] == "surface" and dumped["size"] == 0.62                    # what the page's config carries


# ---------------------------------------------------------------- what cannot work is refused before anything renders

def _film(steps, **kw):
    return Site.model_validate({"name": "t", "sections": [{"id": "s", "type": "film", "video": "a.mp4", "layout": "overlay",
                                                            "steps": steps, **kw}]}).sections[0]


@pytest.mark.parametrize("steps, kw, why", [
    ([{"title": "a", "at": [0, 1], "place": {"kind": "sky"}}], {"layout": "cards"}, "layout: overlay"),
    ([{"title": "a", "place": {"kind": "sky"}}], {}, "needs a window"),
    ([{"title": "a", "at": [0, 1], "place": {"kind": "surface"}}], {}, "a surface needs"),
    ([{"title": "a", "at": [0, 1], "place": {"kind": "surface", "at": 0.4}}], {}, "not a number"),
    ([{"title": "a", "at": [0, 1], "place": {"kind": "sky", "at": "the sky"}}], {}, "not a prompt"),
    ([{"title": "a", "at": [0, 1], "place": {"kind": "behind", "quad": [[0, 0], [1, 0], [1, 1], [0, 1]]}}], {}, "`quad` is for a surface"),
    ([{"title": str(i), "at": [0, 1], "place": {"kind": "surface", "at": "the wall"}} for i in range(5)], {}, "at most 4"),
])
def test_impossible_placements_are_refused(steps, kw, why):
    with pytest.raises(BuildError, match=why):
        world.validate(_film(steps, **kw))


def test_a_film_without_in_world_type_is_not_touched():
    sec = _film([{"title": "a", "at": [0, 1], "place": "left"}, {"title": "b"}])
    assert not world.active(sec) and world.world_steps(sec) == []
    world.validate(sec)                                                              # nothing to refuse


# ---------------------------------------------------------------- the geometry

def _persp(pts_world: np.ndarray, rot=(0.0, 0.0, 0.0), t=(0.0, 0.0, 3.0), f=0.85 * 960):
    """Project plane points (x, y, 0) through a camera turned by rot (degrees about x, y, z) and moved by t: pixels of 960x540."""
    r, _ = cv2.Rodrigues(np.deg2rad(np.array(rot, dtype=np.float64)))
    p = (r @ np.c_[pts_world, np.zeros(len(pts_world))].T).T + np.array(t)
    return np.c_[f * p[:, 0] / p[:, 2] + 480, f * p[:, 1] / p[:, 2] + 270]


def test_a_quadrilateral_is_ordered_clockwise_from_the_top_left():
    q = np.array([[10, 90], [90, 10], [90, 90], [10, 10]], float)
    assert np.allclose(wm.order_quad(q), [[10, 10], [90, 10], [90, 90], [10, 90]])
    rng = np.random.default_rng(1)
    assert np.allclose(wm.order_quad(q[rng.permutation(4)]), [[10, 10], [90, 10], [90, 90], [10, 90]])


def test_the_corners_of_a_mask_are_found_and_pulled_in():
    m = np.zeros((540, 960), np.uint8)
    pts = np.array([[200, 150], [700, 170], [760, 440], [140, 420]], np.int32)
    cv2.fillPoly(m, [pts], 255)
    cv2.circle(m, (450, 290), 60, 0, -1)                                             # a hole does not change the hull
    q = wm.surface_quad(m, inset=0.0)
    assert np.abs(q - wm.order_quad(pts)).max() < 8
    inset = wm.surface_quad(m, inset=0.1)
    assert cv2.contourArea(inset.astype(np.float32)) < cv2.contourArea(q.astype(np.float32)) * 0.85
    with pytest.raises(ValueError):
        wm.surface_quad(np.zeros((540, 960), np.uint8))


@pytest.mark.parametrize("rot", [(0, 0, 0), (35, 0, 0), (30, 25, 0), (-20, 15, 8)])
def test_a_slanted_rectangle_gives_back_its_aspect(rot):
    rect = np.array([[-1.0, -0.5], [1.0, -0.5], [1.0, 0.5], [-1.0, 0.5]])           # 2 : 1
    q = _persp(rect, rot=rot)
    assert wm.plane_aspect(q) == pytest.approx(2.0, rel=0.18)
    R = wm.rectify(q, wm.plane_aspect(q))
    out = cv2.perspectiveTransform(q.reshape(1, 4, 2).astype(np.float32), R).reshape(4, 2)
    a = wm.plane_aspect(q)
    assert np.allclose(out, [[0, 0], [1, 0], [1, 1 / a], [0, 1 / a]], atol=1e-4)


def test_a_plane_facing_the_camera_is_the_frame_and_a_floor_slants_the_type():
    P = wm.plane_frame(np.array([0.0, 0.0, 1.0]), (480, 270))
    assert np.allclose(P, [[960, 0, 480], [0, 960, 270], [0, 0, 1]], atol=1e-6)      # a unit is the frame's width; v runs down
    floor = wm.plane_frame(np.array([0.0, 0.98, 0.19]), (480, 400))
    # a letter's width at the centre is still the asked share of the frame, its height is foreshortened, v still runs down
    row = cv2.perspectiveTransform(np.float32([[[-0.25, 0], [0.25, 0]]]), floor).reshape(2, 2)
    col = cv2.perspectiveTransform(np.float32([[[0, -0.05], [0, 0.05]]]), floor).reshape(2, 2)
    assert abs(np.linalg.norm(row[1] - row[0]) - 480) < 30
    assert 5 < col[1][1] - col[0][1] < 0.5 * 0.1 * 960
    assert abs(row[1][1] - row[0][1]) < 1.0                                          # the horizontal stays horizontal
    # the centre is the plane's (0, 0)
    assert np.allclose(cv2.perspectiveTransform(np.float32([[[0, 0]]]), floor).ravel(), [480, 400], atol=1e-3)


def test_a_planes_depth_fit_recovers_its_normal_up_to_scale():
    # a floor seen by a level camera: disparity grows linearly down the picture from zero at the horizon (y = 270)
    ys, xs = np.mgrid[0:540, 0:960]
    f = wm.FOCAL * 960
    n_true = np.array([0.0, 1.0, 0.0])
    d = np.clip((ys - 270.0) / f * 2.0, 0, 1).astype(np.float32)
    mask = ((ys > 330) * 255).astype(np.uint8)
    sol = wm.fit_disparity_plane(d, mask)
    n = sol / np.linalg.norm(sol)
    assert np.allclose(np.abs(n), n_true, atol=0.02)
    assert wm.fit_disparity_plane(d, np.zeros((540, 960), np.uint8)) is None


def test_the_matrix_is_signed_so_the_type_is_on_the_right_side_of_the_horizon():
    floor = wm.plane_frame(np.array([0.0, 0.98, 0.19]), (480, 400))
    R = np.linalg.inv(floor)
    M = wm.screen_matrix(R, np.eye(3))
    packed = wm.pack_matrix(M, (0.0, 0.0))
    assert len(packed) == 9 and abs(np.linalg.norm(packed) - 1) < 1e-3
    Mp = wm.unpack_matrix(packed)
    below = wm.apply(Mp, 0.5, 400 / 540)                                              # the type's own place
    assert below is not None and abs(below[0]) < 1e-3 and abs(below[1]) < 1e-3
    assert wm.apply(Mp, 0.5, 0.02) is None                                           # the sky above the horizon is not the floor
    flipped = wm.pack_matrix(-M, (0.0, 0.0))
    assert np.allclose(flipped, packed)                                              # the sign is fixed, whatever the scale did


def test_a_frame_plane_matrix_is_the_identity_up_to_scale():
    M = wm.screen_matrix(wm.frame_plane(), np.eye(3))
    u, v = wm.apply(wm.unpack_matrix(wm.pack_matrix(M, (0.5, 0.28))), 0.25, 0.5)
    assert (u, v) == pytest.approx((0.25, 0.5 * 540 / 960), abs=1e-5)                 # plane units are frame widths
    # turn the type on its plane about its centre
    turned = wm.screen_matrix(wm.frame_plane(), np.eye(3), (0.5, 0.28, 90.0))
    a = wm.apply(turned, 0.5 + 0.1, 0.28 * 960 / 540)
    assert a is not None and abs(a[0] - 0.5) < 1e-6 and abs(abs(a[1] - 0.28) - 0.1) < 1e-6


def test_occlusion_is_a_soft_step_at_the_types_depth():
    d = np.array([0.0, 0.1, 0.3, 0.5, 1.0])
    v = wm.visibility(d, 0.3, 0.04)
    assert v[0] == v[1] == 1.0 and v[4] == 0.0 and v[3] == 0.0
    assert v[2] == pytest.approx(0.5)
    assert np.all(np.diff(v) <= 0)
    soft = wm.visibility(np.array([0.33]), 0.3, 0.09)[0]
    assert 0 < soft < 1 and soft > wm.visibility(np.array([0.33]), 0.3, 0.02)[0]


def test_the_estimate_of_a_titles_lines_stays_inside_its_height():
    n, h = wm.estimate_lines(18, None, 0.5625, 0.6)
    assert n >= 1 and h <= 0.3 * 0.5625 + 1e-9
    assert wm.estimate_lines(18, 3, 0.5625, 0.3)[0] == 3
    for chars in (2, 4, 18, 40, 90):
        lines, height = wm.estimate_lines(chars, None, 0.5625, 0.5)
        assert 1 <= lines <= 5 and 0 < height <= 0.3 * 0.5625 + 1e-9               # a short title is cut to the height, a long one wraps
    assert wm.estimate_lines(90, None, 0.5625, 0.5)[0] >= wm.estimate_lines(18, None, 0.5625, 0.5)[0]


# ---------------------------------------------------------------- planar tracking

def _scene(w=960, h=540, seed=5):
    rng = np.random.default_rng(seed)
    base = cv2.GaussianBlur(rng.integers(0, 255, (h * 2, w * 2), dtype=np.uint8), (0, 0), 1.6)
    for _ in range(300):                                                              # corners to follow
        x, y, s = int(rng.integers(0, w * 2 - 60)), int(rng.integers(0, h * 2 - 60)), int(rng.integers(12, 50))
        cv2.rectangle(base, (x, y), (x + s, y + s), int(rng.integers(0, 255)), -1)
    return base


def _warp(base, H, w=960, h=540):
    return cv2.warpPerspective(base, H, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def test_a_similarity_is_followed_through_a_zoom_and_a_pan():
    base = _scene()
    truth = []
    frames = []
    for t in range(24):
        s = 1.0 + 0.012 * t
        H = np.array([[s, 0, -3.0 * t + 100], [0, s, 1.5 * t + 80], [0, 0, 1.0]])
        truth.append(H)
        frames.append(_warp(base, H))
    gray = np.stack(frames)
    mask = np.zeros((540, 960), np.uint8)
    mask[150:400, 250:700] = 255
    Hs, conf = wt.track(gray, 10, 0, 23, lambda f: mask if f == 10 else None, "similarity")
    probe = np.float32([[[300, 200], [650, 380], [480, 290]]])
    for t in (0, 5, 17, 23):
        rel = truth[t] @ np.linalg.inv(truth[10])
        want = cv2.perspectiveTransform(probe, rel)
        got = cv2.perspectiveTransform(probe, Hs[t])
        assert np.abs(want - got).max() < 1.5, t
    assert conf[0] > 0.5 and conf[23] > 0.5 and conf[10] == 1.0


def test_a_plane_in_perspective_is_followed_by_a_homography():
    base = _scene(seed=9)
    frames, truth = [], []
    for t in range(20):
        H = np.array([[1.0 + 0.004 * t, 0.002 * t, 40 - 2.0 * t], [0.001 * t, 1.0, 30 + 1.0 * t], [1e-5 * t, 2e-5 * t, 1.0]])
        truth.append(H)
        frames.append(_warp(base, H))
    mask = np.zeros((540, 960), np.uint8)
    mask[100:440, 200:760] = 255
    Hs, _ = wt.track(np.stack(frames), 0, 0, 19, lambda f: mask if f == 0 else None, "homography")
    probe = np.float32([[[260, 160], [700, 400], [480, 300]]])
    want = cv2.perspectiveTransform(probe, truth[19] @ np.linalg.inv(truth[0]))
    assert np.abs(want - cv2.perspectiveTransform(probe, Hs[19])).max() < 2.0


def test_a_track_stays_inside_its_shot_and_is_nan_outside():
    base = _scene(seed=2)
    gray = np.stack([_warp(base, np.array([[1, 0, -2.0 * t], [0, 1, 0], [0, 0, 1.0]])) for t in range(30)])
    mask = np.zeros((540, 960), np.uint8)
    mask[100:400, 300:700] = 255
    Hs, conf = wt.track(gray, 15, 8, 20, lambda f: mask if f == 15 else None, "similarity")
    assert np.isnan(Hs[:8]).all() and np.isnan(Hs[21:]).all() and not np.isnan(Hs[8:21]).any()
    assert np.allclose(Hs[15], np.eye(3))


def test_a_blank_patch_holds_the_last_pose_and_says_it_is_lost():
    gray = np.full((20, 540, 960), 128, np.uint8)
    mask = np.zeros((540, 960), np.uint8)
    mask[100:400, 300:700] = 255
    Hs, conf = wt.track(gray, 10, 0, 19, lambda f: mask, "homography")
    assert not np.isnan(Hs).any() and np.allclose(Hs[3], np.eye(3)) and conf[3] == 0.0


def test_smoothing_removes_noise_and_keeps_an_accelerating_camera():
    rng = np.random.default_rng(4)
    n = 60
    t = np.arange(n)
    corners = np.array([[300, 100], [600, 100], [600, 200], [300, 200]], float)
    path = 0.05 * t ** 2                                                              # a camera speeding up
    H = np.zeros((n, 3, 3))
    for i in range(n):
        H[i] = np.array([[1, 0, path[i] + rng.normal(0, 1.2)], [0, 1, 0.5 * i + rng.normal(0, 1.2)], [0, 0, 1.0]])
    S = wt.smooth_poses(H, np.ones(n), corners, window=15)
    got = np.array([S[i][0, 2] for i in range(n)])
    raw = np.array([H[i][0, 2] for i in range(n)])
    err_s, err_r = np.abs(got[8:-8] - path[8:-8]), np.abs(raw[8:-8] - path[8:-8])
    assert err_s.mean() < 0.5 * err_r.mean() and err_s.max() < 1.6                    # the curve is kept, the noise is not


def test_a_far_layer_follows_the_camera_less_and_follow_one_follows_it_all():
    H = np.array([[1.1, 0, 30], [0, 1.1, -20], [0, 0, 1.0]])
    assert np.allclose(wt.damp_similarity(H, 1.0, (400, 200)), H)
    half = wt.damp_similarity(H, 0.5, (400, 200))
    c = np.array([400, 200, 1.0])
    moved_full, moved_half = (H @ c)[:2] - c[:2], (half @ c)[:2] - c[:2]
    assert np.allclose(moved_half, moved_full * 0.5, atol=1e-6)
    assert np.sqrt(abs(np.linalg.det(half[:2, :2]))) == pytest.approx(1.1 ** 0.5)
    still = wt.damp_similarity(H, 0.0, (400, 200))
    assert np.allclose(still, np.eye(3), atol=1e-9)


# ---------------------------------------------------------------- steady depth

def _moving_scene(n, w=160, h=90):
    """Frames of a textured scene drifting left, and the true depth map of each (a near block, a far ground)."""
    rng = np.random.default_rng(8)
    tex = cv2.GaussianBlur(rng.integers(60, 200, (h, w + 4 * n, 3), dtype=np.uint8), (0, 0), 1.2)
    depth = np.tile(np.linspace(0.0, 1.0, h)[:, None], (1, w + 4 * n)).astype(np.float32)      # near at the bottom
    depth[30:60, 60 + 2 * n: 100 + 2 * n] = 0.9                                              # a near block
    tex[30:60, 60 + 2 * n: 100 + 2 * n] = (240, 230, 40)
    frames = [np.ascontiguousarray(tex[:, 2 * i: 2 * i + w]) for i in range(n)]
    return frames, [depth[:, 2 * i: 2 * i + w] for i in range(n)]


def test_per_frame_depth_that_breathes_is_made_steady():
    n = 24
    frames, truth = _moving_scene(n)
    rng = np.random.default_rng(2)
    scales = rng.uniform(0.5, 2.0, n)
    shifts = rng.uniform(-0.3, 0.6, n)
    fields = [cv2.GaussianBlur(rng.normal(0, 1, (90, 160)).astype(np.float32), (0, 0), 9) * 1.4 for _ in range(n)]   # per-frame wobble
    calls = {"i": 0}
    raws = [truth[i] * scales[i] + shifts[i] + 0.25 * scales[i] * fields[i] for i in range(n)]

    def estimate(fr):
        i = calls["i"]
        calls["i"] += 1
        return raws[i]

    out = world_depth.steady_depth(frames, estimate, radius=3, eps=1e-3)
    assert out.shape == (n, 90, 160) and out.dtype == np.uint8
    per_frame = np.stack([(r - np.percentile(r, 2)) / (np.percentile(r, 99.5) - np.percentile(r, 2)) for r in raws]) * 255
    # a patch of the far ground, frame to frame: the picture drifts sideways under it, the depth along x does not vary
    steady = np.abs(np.diff(out[:, 5:15, 20:120].astype(np.float32).mean(axis=(1, 2)))).mean()
    breathing = np.abs(np.diff(per_frame[:, 5:15, 20:120].mean(axis=(1, 2)))).mean()
    assert steady < breathing * 0.75, (steady, breathing)
    assert out.min() < 40 and out.max() > 215
    # near stays nearer than far
    assert out[:, 35:55, 80:90].mean() > out[:, 5:15, 20:120].mean() + 60


def test_a_cut_starts_a_new_range():
    frames_a, truth_a = _moving_scene(8)
    frames_b = [np.ascontiguousarray(f[::-1]) for f in frames_a]
    truth_b = [np.ascontiguousarray(t[::-1]) for t in truth_a]
    frames, truth = frames_a + frames_b, truth_a + truth_b
    calls = {"i": 0}

    def estimate(fr):
        i = calls["i"]
        calls["i"] += 1
        return truth[i] * (1.0 if i < 8 else 4.0)

    out = world_depth.steady_depth(frames, estimate, cuts={8}, radius=3, eps=1e-3)
    assert abs(float(out[7].mean()) - float(out[0].mean())) < 25
    assert abs(float(out[8].mean()) - float(out[15].mean())) < 25
    assert out.max() > 230 and out.min() < 25                                         # each shot uses the whole range


def test_a_cut_nobody_listed_is_found_by_the_flow_and_starts_a_new_range():
    frames_a, truth_a = _moving_scene(8)
    rng = np.random.default_rng(12)
    frames_b = [np.ascontiguousarray(rng.integers(0, 255, f.shape, dtype=np.uint8)) for f in frames_a]      # nothing like the shot before
    truth_b = [np.ascontiguousarray(t[::-1]) for t in truth_a]
    frames, truth = frames_a + frames_b, truth_a + truth_b
    calls = {"i": 0}

    def estimate(fr):
        i = calls["i"]
        calls["i"] += 1
        return truth[i] * (1.0 if i < 8 else 5.0)

    out = world_depth.steady_depth(frames, estimate, radius=3, eps=1e-3)                  # no `cuts`
    assert out[8:].max() > 200 and out[8:].min() < 50                                      # the second shot has its own range
    assert abs(float(out[8:].mean()) - 127) < 60


# ---------------------------------------------------------------- the whole build, with the models replaced

W, H, NF = 960, 540, 36


def _make_film(path: Path):
    base = _scene(seed=3)
    raw = b""
    for t in range(NF):
        s = 1.0 + 0.004 * t
        g = _warp(base, np.array([[s, 0, 60 - 3.0 * t], [0, s, 40 + 1.0 * t], [0, 0, 1.0]]))
        raw += np.dstack([g, np.roll(g, 7, axis=1), np.roll(g, 13, axis=0)]).tobytes()
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "24", "-i", "-",
                    "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-g", "6", str(path)], input=raw, check=True)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A project with a synthetic film and the three models (depth, Florence-2 + SAM image masks, SAM video tracking) replaced."""
    proj = tmp_path / "p"
    (proj / "inputs").mkdir(parents=True)
    spec = {"name": "t", "sections": [{"id": "s", "type": "film", "video": "inputs/film.mp4", "layout": "overlay", "gop": 6,
                                       "steps": [{"title": "Down to <em>the water.</em>", "at": [0.2, 0.8], "place": {"kind": "behind", "at": "the post", "y": 0.3, "size": 0.5}},
                                                 {"title": "Stay <em>cold.</em>", "at": [0.1, 0.9], "place": {"kind": "surface", "at": "the floor", "y": 0.78, "size": 0.5}},
                                                 {"title": "Plain", "at": [0.0, 0.1]}]}]}
    (proj / "site.yaml").write_text(yaml.safe_dump(spec))
    _make_film(proj / "inputs" / "film.mp4")
    calls = {"depth": 0, "find": 0, "track": 0}

    from engine.backends import depth as depthmod
    from engine import reveal, region

    def fake_depth(img, size="small"):
        calls["depth"] += 1
        a = np.asarray(img.convert("L"), np.float32) / 255
        h = a.shape[0]
        return (np.linspace(0.05, 1.0, h)[:, None] * np.ones((1, a.shape[1]), np.float32)) * 3.0 + 0.2

    def fake_find(project, src, reg, log=print):
        calls["find"] += 1
        from PIL import Image
        m = np.zeros((540, 960), np.uint8)
        m[180:300, 520:600] = 255                                                       # "the post"
        out = Path(project.build) / "_generated" / "fake_region.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(m).save(out)
        return out

    def fake_track(sec, ctx, rv, rg, src, clip, nframes, fps, spans, shots):
        out = ctx.work / "reveal" / rg.id / "masks.npz"

        def run():                                                                       # a stage, as the real one is
            calls["track"] += 1
            m = np.zeros((nframes, 540, 960), np.uint8)
            m[:, 330:520, 80:900] = 255                                                 # "the floor"
            out.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(out, masks=m)
        ctx.stage(f"reveal_track_{rg.id}", {"frame": rg.at.frame, "prompt": rg.prompt}, [out], run)
        return [out]

    monkeypatch.setattr(depthmod, "estimate_raw", fake_depth)
    monkeypatch.setattr(region, "find", fake_find)
    monkeypatch.setattr(reveal, "track_region", fake_track)
    return SimpleNamespace(proj=Project(proj), calls=calls)


def _build(rig, **kw):
    sec = rig.proj.load().sections[0]
    ctx = BuildContext(rig.proj, "s", log=lambda m: None, **kw)
    return sec, ctx, world.build(sec, ctx, rig.proj.path("inputs/film.mp4"), {})


@needs_ffmpeg
def test_the_build_makes_the_worlds_config_and_its_atlas(rig):
    sec, ctx, cfg = _build(rig)
    assert cfg["frames"] == NF and cfg["fps"] == 24.0
    texts = {t["i"]: t for t in cfg["texts"]}
    assert set(texts) == {0, 1}                                                       # the plain step has none
    b, s = texts[0], texts[1]
    assert b["kind"] == "behind" and s["kind"] == "surface"
    assert b["slot"] == "depth" and s["slot"] == "s1" and cfg["atlas"]["slots"] == ["depth", "s1"]
    # a window of 0.2-0.8 of 36 frames, a few frames either side, inside the shot
    assert b["f0"] == max(0, round(0.2 * (NF - 1)) - world.MARGIN) and b["f1"] == min(NF - 1, round(0.8 * (NF - 1)) + world.MARGIN)
    assert len(b["m"]) == b["f1"] - b["f0"] + 1 == len(b["c"]) and all(len(m) == 9 for m in b["m"])
    assert b["anchor"] == (round(0.2 * (NF - 1)) + round(0.8 * (NF - 1))) // 2
    # behind the post: its depth is the post's depth minus the gap, and the title is well formed
    assert b["depth"] == pytest.approx(b["thing_depth"] - 0.05, abs=1e-3) and 0 < b["depth"] < 1
    assert b["plane"] == [1.0, 0.5625] and b["box"][2] == 0.5 and b["soft"] == world.SOFT["behind"]
    assert b["style"]["track"] == 0.0 and b["style"]["haze"] == 0.12 and 0 <= b["tone"] <= 1
    assert s["tilt"] > 30 and s["ppp"] == 1.0 and s["style"]["wear"] == 0.35 and s["box"][:2] == [0.0, 0.0]
    assert min(s["c"]) > 0.3 and "quad" not in s
    # the matrix at the anchor puts the type's centre where the spec said (surface: y 0.78 of the frame)
    Ms = wm.unpack_matrix(s["m"][s["anchor"] - s["f0"]])
    plane = wm.apply(Ms, 0.5, 0.78)
    assert plane is not None and abs(plane[0]) < 0.01 and abs(plane[1]) < 0.01
    Mb = wm.unpack_matrix(b["m"][b["anchor"] - b["f0"]])
    assert wm.apply(Mb, 0.5, 0.3) == pytest.approx((0.5, 0.3 * 540 / 960), abs=1e-3)   # the anchor frame is the plane itself
    # the atlas: the film's frame count and rate, the depth tile survives the codec
    atlas = cfg["atlas"]
    info = json.loads(subprocess.run([settings()["ffprobe"], "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                      "stream=width,height,r_frame_rate,nb_read_frames", "-of", "json", str(ctx.web / "world.mp4")],
                                     capture_output=True, text=True, check=True).stdout)["streams"][0]
    assert (info["width"], info["height"]) == (1920, 544) and info["nb_read_frames"] == str(NF) and info["r_frame_rate"] == "24/1"
    assert (ctx.web / "world-mobile.mp4").exists() and atlas["cols"] == 2 and atlas["rows"] == 1 and atlas["video"].endswith("world.mp4")
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(ctx.web / "world.mp4"), "-vf", "select=eq(n\\,12)", "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    tile = np.frombuffer(raw, np.uint8).reshape(544, 1920)[:, :960]
    assert tile[500, 100] > tile[40, 100] + 60                                        # near at the bottom (the fake gradient)
    mask = np.frombuffer(raw, np.uint8).reshape(544, 1920)[:, 960:]
    assert mask[400, 400] > 200 and mask[20, 400] < 30                                # the floor's mask tile


@needs_ffmpeg
def test_nothing_is_redone_when_nothing_changed_and_a_title_only_redoes_its_own_stage(rig):
    sec, ctx, cfg = _build(rig)
    first = dict(rig.calls)
    assert first["depth"] == NF and first["track"] == 1 and first["find"] >= 1
    _, _, again = _build(rig)
    assert rig.calls == first                                                         # every stage up to date
    assert again["texts"][0]["m"] == cfg["texts"][0]["m"]
    # change one title's placement: its own stage runs, the depth and the surface's masks are kept
    spec = rig.proj.raw()
    spec["sections"][0]["steps"][0]["place"]["x"] = 0.4
    rig.proj.spec_path.write_text(yaml.safe_dump(spec))
    _build(rig)
    assert rig.calls["depth"] == first["depth"] and rig.calls["track"] == first["track"]
    # the headline's own words only matter by their length: changing them to another of the same length keeps the cache
    spec["sections"][0]["steps"][0]["title"] = "Back to <em>the shore.</em>"
    rig.proj.spec_path.write_text(yaml.safe_dump(spec))
    stamps = {p.name: p.read_text() for p in (rig.proj.build / "s" / "stamps").glob("world_text_*.json")}
    _build(rig)
    assert {p.name: p.read_text() for p in (rig.proj.build / "s" / "stamps").glob("world_text_*.json")} == stamps


@needs_ffmpeg
def test_a_dry_run_plans_the_world_stages_and_touches_no_file(rig):
    from engine import plan
    sec = rig.proj.load().sections[0]
    names = plan.expected(sec)
    assert names[:2] == ["encode", "reveal_work"] and "reveal_cuts" in names and "world_depth" in names
    assert "world_text_0" in names and "world_text_1" in names and "reveal_track_world1" in names and names[-1] == "world_pack"
    assert "world_text_2" not in names
    assert plan.units(sec, "world_depth")[0] == "film:world_depth" and plan.units(sec, "world_text_1")[0] == "film:world_text"
    assert plan.units(sec, "world_pack")[0] == "film:world_pack"
    p = plan.plan_build(rig.proj, only=["s"])
    assert any(st.name.startswith("world_") for st in p.stages)
    assert not (rig.proj.build / "s" / "world").exists() or not (rig.proj.build / "s" / "world" / "depth.npz").exists()
    # an up-to-date film has none stale
    _build(rig)
    assert [st.name for st in plan.plan_build(rig.proj, only=["s"]).stale() if st.name.startswith(("world_", "reveal_"))] == []


@needs_ffmpeg
def test_the_report_draws_the_track_on_the_films_own_frames(rig):
    from engine import world_report
    cfg = _build(rig)[2]
    (rig.proj.build / "s" / "config.json").write_text(json.dumps({"world": cfg}))
    rep = world_report.check(rig.proj, None, 4, lambda m: None)[0]
    assert Path(rep["sheet"]).exists() and Path(rep["json"]).exists()
    assert {t["kind"] for t in rep["texts"]} == {"behind", "surface"}
    for t in rep["texts"]:
        assert t["jitter_px_p95"] < 1.5 and t["on_screen"] > 0.5
    im = cv2.imread(rep["sheet"])
    assert im.shape[1] >= 4 * 480 - 8
    with pytest.raises(BuildError, match="not been built"):
        world_report.check_film(rig.proj, "nope", 4)


# ---------------------------------------------------------------- the page

def _render(sec, cfg=None):
    from engine.compile.compiler import _env
    mod = _env().get_template("scene.html.j2").module
    sdata = sec.model_dump(mode="json", include={"hud", "steps", "layout", "length"})
    return mod.render(sec, cfg or {}, sdata)


def test_the_page_marks_in_world_titles_and_keeps_the_captions_that_were_there():
    sec = FilmScene.model_validate({"id": "s", "type": "film", "video": "a.mp4", "layout": "overlay", "steps": STEPS})
    html = _render(sec)
    assert html.count("data-world=") == 3 and 'data-world="1"' in html and 'data-world="2"' in html and 'data-world="3"' in html
    assert "ss-has-world" in html
    assert "ss-captions--bottom-left" in html                                         # a corner caption is where it was
    # the title stays in the page as text, whatever the player does
    assert "Down to <em>the water.</em>" in html and "Stay <em>cold.</em>" in html
    cfg = json.loads(html.split('class="ss-section">')[1].split("</script>")[0])
    assert cfg["steps"][1]["place"]["kind"] == "behind"
    plain = _render(FilmScene.model_validate({"id": "s", "type": "film", "video": "a.mp4", "layout": "overlay",
                                              "steps": [{"title": "x", "at": [0, 1], "place": "right"}, {"title": "y", "at": [0, 1]}]}))
    assert "data-world" not in plain and "ss-has-world" not in plain and "ss-captions--right" in plain


def test_parallax_cards_carry_the_marker_too():
    sec = ParallaxScene.model_validate({"id": "p", "type": "parallax", "steps": [
        {"title": "a", "image": "x.jpg", "place": {"kind": "sky"}}, {"title": "b", "image": "y.jpg"}]})
    html = _render(sec)
    assert html.count("data-world=") == 1 and 'class="ss-step ss-has-world"' in html


# ---------------------------------------------------------------- the engine's cache is untouched for films without it

def test_the_film_encode_key_does_not_know_about_world(monkeypatch):
    """film.build calls world only for a section that has in-world type: others do not even import its work."""
    from engine.scenes import film
    calls = []
    monkeypatch.setattr(world, "build", lambda *a, **k: calls.append("build"))
    monkeypatch.setattr(world, "preflight", lambda *a, **k: calls.append("preflight"))
    sec = _film([{"title": "a", "at": [0, 1], "place": "left"}])
    assert not world.active(sec)
    import inspect
    src = inspect.getsource(film.build)
    assert "typeworld.active(sec)" in src and src.index("typeworld.active") < src.index("encode(src")


# ---------------------------------------------------------------- a photograph (parallax)

@pytest.fixture
def photo_rig(tmp_path, monkeypatch):
    from PIL import Image
    from engine import region
    proj = tmp_path / "pp"
    proj.mkdir()
    (proj / "site.yaml").write_text("name: t\nsections: []\n")
    ctx = BuildContext(Project(proj), "stay", log=lambda m: None)
    rng = np.random.default_rng(6)
    img = cv2.GaussianBlur(rng.integers(40, 220, (720, 1280, 3), dtype=np.uint8), (0, 0), 2)
    photo = ctx.web / "photo0.jpg"
    Image.fromarray(img).save(photo, quality=92)
    depth = np.tile(np.linspace(0, 255, 720, dtype=np.uint8)[:, None], (1, 1280))
    depth[200:500, 700:900] = 230                                                      # a near post
    dpng = ctx.web / "photo0-depth.png"
    Image.fromarray(depth).save(dpng)
    calls = {"find": 0}

    def fake_find(project, src, reg, log=print):
        calls["find"] += 1
        m = np.zeros((720, 1280), np.uint8)
        if reg.prompt and "post" in reg.prompt:
            m[200:500, 700:900] = 255
        else:
            m[360:700, 100:1200] = 255                                                 # a floor
        out = Path(project.build) / "_generated" / f"fake_{calls['find']}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(m).save(out)
        return out

    monkeypatch.setattr(region, "find", fake_find)
    return SimpleNamespace(ctx=ctx, photo=photo, dpng=dpng, calls=calls)


def _step(**place):
    return Step.model_validate({"title": "Breakfast <em>at the edge.</em>", "place": place})


def test_a_photographs_title_is_laid_out_static_with_its_depth_or_its_surface(photo_rig):
    sec = SimpleNamespace(id="stay")
    r = photo_rig
    b = world.build_photo(sec, r.ctx, 0, 1, _step(kind="behind", at="the post", y=0.3, size=0.6), r.photo, r.dpng)
    assert b["kind"] == "behind" and b["plane"] == [1.0, pytest.approx(720 / 1280, abs=1e-4)] and b["box"][2] == 0.6
    assert b["depth"] == pytest.approx(b["thing_depth"] - 0.05, abs=1e-3) and b["thing_depth"] > 0.8
    M = wm.unpack_matrix(b["m"])
    assert wm.apply(M, 0.5, 0.3) == pytest.approx((0.5, 0.3 * 720 / 1280), abs=1e-4)      # photo uv -> plane: a frame plane, static
    assert 0 <= b["tone"] <= 1 and "mask" not in b
    s = world.build_photo(sec, r.ctx, 1, 2, _step(kind="sky", y=0.25), r.photo, r.dpng)
    assert s["depth"] == 0.07 and s["soft"] == world.SOFT["sky"] and s["style"]["haze"] == 0.35
    f = world.build_photo(sec, r.ctx, 2, 3, _step(kind="surface", at="the floor", x=0.5, y=0.8, size=0.5), r.photo, r.dpng)
    assert f["kind"] == "surface" and f["mask"].endswith("photo2-mask.png") and (r.ctx.web / "photo2-mask.png").exists()
    Mf = wm.unpack_matrix(f["m"])
    centre = wm.apply(Mf, 0.5, 0.8)
    assert centre is not None and abs(centre[0]) < 0.02 and abs(centre[1]) < 0.02       # the plane's origin is where the type was asked for
    assert f["tilt"] > 20 and f["box"][:2] == [0.0, 0.0]


def test_a_photographs_title_is_cached_per_chapter(photo_rig):
    sec = SimpleNamespace(id="stay")
    r = photo_rig
    st = _step(kind="behind", at="the post")
    world.build_photo(sec, r.ctx, 0, 1, st, r.photo, r.dpng)
    n = r.calls["find"]
    world.build_photo(sec, r.ctx, 0, 1, st, r.photo, r.dpng)
    assert r.calls["find"] == n                                                        # up to date: nothing found again
    world.build_photo(sec, r.ctx, 0, 1, _step(kind="behind", at="the post", x=0.3), r.photo, r.dpng)
    assert r.calls["find"] == n + 1                                                    # a new placement is a new stage run


def test_a_photographs_impossible_placements_are_refused(photo_rig):
    sec = SimpleNamespace(id="stay")
    r = photo_rig
    with pytest.raises(BuildError, match="a surface needs"):
        world.build_photo(sec, r.ctx, 0, 1, _step(kind="surface"), r.photo, r.dpng)
    with pytest.raises(BuildError, match="not a prompt"):
        world.build_photo(sec, r.ctx, 0, 1, _step(kind="sky", at="the sky"), r.photo, r.dpng)


def test_the_depth_snap_works_without_opencv_contrib(monkeypatch):
    rng = np.random.default_rng(1)
    guide = cv2.GaussianBlur(rng.integers(0, 255, (60, 80, 3), dtype=np.uint8), (0, 0), 1.0)
    depth = np.tile(np.linspace(0, 1, 80, dtype=np.float32)[None, :], (60, 1))
    with_contrib = world_depth.snap(depth, guide, 4, 1e-3)
    monkeypatch.setattr(cv2, "ximgproc", None, raising=False)                           # no contrib module: the box-filter fallback
    plain = world_depth.snap(depth, guide, 4, 1e-3)
    assert plain.shape == depth.shape and np.abs(plain - depth).mean() < 0.05
    assert np.abs(plain - with_contrib).mean() < 0.05


# ---------------------------------------------------------------- a sequence: a product on a clear backdrop

@needs_ffmpeg
def test_a_sequences_alpha_is_the_silhouette_the_type_sits_behind(tmp_path):
    from PIL import Image
    from engine.spec import SequenceScene
    proj = tmp_path / "sq"
    proj.mkdir()
    (proj / "site.yaml").write_text("name: t\nsections: []\n")
    p = Project(proj)
    ctx = BuildContext(p, "set", log=lambda m: None)
    frames = []
    n = 12
    for i in range(n):                                                                  # a turning "product": a block, alpha 0 around it
        im = np.zeros((540, 960, 4), np.uint8)
        x0 = 380 + 6 * i
        im[150:450, x0:x0 + 200] = (200, 120, 40, 255)
        im[150:450, x0 + 200:x0 + 204, 3] = 128                                         # an anti-aliased edge
        f = ctx.work / "render" / "frames" / f"{i + 1:04d}.png"
        f.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(im, "RGBA").save(f)
        frames.append(f)
    sec = SequenceScene.model_validate({"id": "set", "type": "sequence", "layout": "overlay", "frames": n, "steps": [
        {"title": "Thirty-two <em>pieces.</em>", "at": [0.0, 1.0], "place": {"kind": "behind", "x": 0.5, "y": 0.3, "size": 0.7}}]})
    src, alpha, urls = world.sequence_film(sec, ctx, frames, "#0b0b0d")
    a = np.load(alpha)["depth"]
    assert a.shape == (n, 540, 960) and a[0, 300, 480] == 255 and a[0, 300, 100] == 0 and a[0, 20, 20] == 0
    assert 100 < a[0, 300, 380 + 200 + 2] < 160                                       # the edge keeps its own softness
    assert urls["video"].endswith("film.mp4") and (ctx.web / "film.mp4").exists() and (ctx.web / "film-mobile.mp4").exists()
    cfg = world.build(sec, ctx, src, {}, silhouette=alpha)
    t = cfg["texts"][0]
    assert t["kind"] == "behind" and t["depth"] == 0.5                                # behind the silhouette: no model, no guess
    assert all(np.allclose(wm.unpack_matrix(m), wm.unpack_matrix(t["m"][0]), atol=1e-6) for m in t["m"])   # a plain backdrop: the type stays on the screen
    assert cfg["atlas"]["slots"] == ["depth"] and cfg["frames"] == n
    # a sequence in the cards layout cannot hold in-world type
    bad = SequenceScene.model_validate({"id": "set", "type": "sequence", "layout": "cards", "steps": sec.model_dump(mode="json")["steps"]})
    with pytest.raises(BuildError, match="needs `layout: overlay` on a sequence"):
        world.validate(bad)
