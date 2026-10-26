"""Named camera moves (`camera: dolly-in`, engine/camera_moves.py): the spec, the rig maths, the renders on a synthetic
depth map (does an orbit move the foreground against the background around a still subject, does a dolly zoom keep the
subject's size ...), the move measurement, the prompt words and the cache keys. No ComfyUI and no GPU: the render runs on
torch's CPU."""
from __future__ import annotations

import math
import typing

import numpy as np
import pytest
from pydantic import ValidationError

from engine import camera_beats as cb
from engine import camera_guide as cg
from engine import camera_moves as cm
from engine import freeze as fz
from engine.spec import Beat, CameraMove, CameraMoveName, CameraPreset, FilmScene

KEYS = [{"t": 0, "box": [0, 0, 1, 1]}, {"t": 0.5, "box": [0.40, 0.38, 0.62, 0.97]}, {"t": 1, "box": [0, 0, 1, 1]}]


def beat(id="a", **kw) -> Beat:
    return Beat.model_validate({"id": id, "seconds": 3, "prompt": "a cup", "motion": "steam rises", **kw})


# ---------------------------------------------------------------- spec

def test_every_move_has_a_recipe_and_the_spec_lists_the_same_names():
    assert set(typing.get_args(CameraMoveName)) == set(cm.MOVES) == set(cm.RECIPES)


def test_a_move_is_named_by_a_word_or_a_mapping():
    b = beat(camera="dolly-in")
    assert isinstance(b.camera, CameraPreset) and isinstance(b.camera, CameraMove)
    assert b.camera.move == "dolly-in" and b.camera.amount == 1.0 and b.camera.at is None and b.camera.keys == []
    b = beat(camera={"move": "orbit-left", "amount": 0.8, "at": [0.4, 0.55], "subjects": ""})
    assert b.camera.move == "orbit-left" and b.camera.at == (0.4, 0.55) and b.camera.subjects == ""
    again = Beat.model_validate(b.model_dump(mode="json"))          # a saved spec reads back the same
    assert again.camera == b.camera
    assert b.model_dump(mode="json", exclude_defaults=True)["camera"] == {"move": "orbit-left", "amount": 0.8,
                                                                          "at": [0.4, 0.55], "subjects": ""}


def test_keyed_cameras_keep_their_meaning():
    for written in (KEYS, {"keys": KEYS}, {"keys": KEYS, "parallax": 0.2}):
        b = beat(camera=written)
        assert type(b.camera) is CameraMove and len(b.camera.keys) == 3
        assert cm.preset_of(b.camera) is None and cm.phrase(b.camera) == ""
    assert "move" not in CameraMove.model_fields                      # the keyed schema is unchanged


@pytest.mark.parametrize("bad,why", [
    ("zoom-dance", "Input should be"),
    ({"move": "fpv", "keys": KEYS}, "has no `keys`"),
    ({"move": "fpv", "continues": True}, "starts its own shot"),
    ({"move": "fpv", "at": [1.2, 0.5]}, "inside 0-1"),
    ({"move": "fpv", "amount": 3}, "less than or equal"),
])
def test_bad_moves_say_what_is_wrong(bad, why):
    with pytest.raises(ValidationError, match=why):
        beat(camera=bad)


def test_a_named_move_refuses_trim_and_end_image_and_frozen_moments():
    with pytest.raises(ValidationError, match="trim"):
        beat(camera="dolly-in", trim=0.5)
    with pytest.raises(ValidationError, match="end_image"):
        beat(camera="dolly-in", end_image="inputs/x.png")
    with pytest.raises(ValidationError, match="frozen moment"):
        Beat.model_validate({"id": "f", "seconds": 3, "camera": "dolly-in", "freeze": {"from": "x"}})


# ---------------------------------------------------------------- the rig

AMOUNTS = (0.25, 1.0, 2.0)


@pytest.mark.parametrize("move", cm.MOVES)
@pytest.mark.parametrize("amount", AMOUNTS)
def test_every_view_stays_inside_the_picture(move, amount):
    for at in (None, (0.1, 0.9), (0.85, 0.2)):
        for c in cm.rig(move, 33, amount, at):
            assert 0.02 <= c.w <= 1.0
            assert c.cx - c.w / 2 >= -1e-9 and c.cx + c.w / 2 <= 1 + 1e-9
            assert c.cy - c.w / 2 >= -1e-9 and c.cy + c.w / 2 <= 1 + 1e-9
            assert 0 <= c.e <= 1.4 and abs(c.roll) < math.radians(12)


def test_static_holds_and_starts_on_the_picture():
    assert all(c == cm.Cam(0.5, 0.5, 1.0) for c in cm.rig("static", 9))
    for m in ("static", "dolly-in", "crash-zoom", "push-through"):
        assert cm.starts_full(m)
    for m in ("dolly-out", "orbit-left", "crane-up", "fpv", "whip-pan", "dolly-zoom"):
        assert not cm.starts_full(m)


def test_dolly_in_closes_on_the_point_and_dolly_out_is_its_reverse():
    r = cm.rig("dolly-in", 25, 1.0, (0.3, 0.6))
    w = [c.w for c in r]
    assert all(a >= b - 1e-12 for a, b in zip(w, w[1:])) and w[-1] < 0.75
    assert abs(r[-1].cx - 0.3) < 0.05 + r[-1].w / 2 and r[-1].e > 0.2       # aimed at the point, near things grow
    back = cm.rig("dolly-out", 25, 1.0, (0.3, 0.6))
    assert all(abs(a.w - b.w) < 1e-9 and abs(a.cx - b.cx) < 1e-9 for a, b in zip(r, back[::-1]))
    assert cm.rig("dolly-in", 25, 2.0)[-1].w < r[-1].w                    # amount goes further


def test_crash_zoom_snaps_then_holds():
    r = cm.rig("crash-zoom", 97)
    w = np.array([c.w for c in r])
    assert np.allclose(w[:11], 1.0) and np.allclose(w[34:], w[-1])        # still, a snap in a fifth of the beat, a hold
    assert 1 / w[-1] > 2.5 and all(c.e == 0 for c in r)                   # a lens zoom: no parallax


def test_orbit_crane_and_dolly_zoom_move_against_depth_not_the_view():
    for m, field, sign in (("orbit-left", "sx", 1), ("orbit-right", "sx", -1), ("crane-up", "sy", 1), ("crane-down", "sy", -1)):
        r = cm.rig(m, 25)
        vals = [getattr(c, field) for c in r]
        assert sign * (vals[-1] - vals[0]) > 0.12 and len({(c.cx, c.cy, c.w) for c in r}) == 1
    dz = cm.rig("dolly-zoom", 25)
    assert len({c.w for c in dz}) == 1 and dz[0].e == 0 and dz[-1].e > 0.4


def test_orbit_and_crane_start_with_no_shift():
    for m in ("orbit-left", "orbit-right", "crane-up", "crane-down"):
        c = cm.cam_at(m, 0.0)
        assert c.sx == 0 and c.sy == 0 and c.e == 0                         # the first frame is a clean crop, no gaps


def test_anchor_defaults_follow_the_move_and_a_written_one_wins():
    assert cm.anchor_of(beat(camera="dolly-in").camera) == 0.6
    assert cm.anchor_of(beat(camera="orbit-left").camera) == 0.3            # gaps behind near things: pinned lightly
    assert cm.anchor_of(beat(camera={"move": "orbit-left", "anchor": 0.0}).camera) == 0.0
    assert cm.anchor_of(beat(camera=KEYS).camera) == 0.6                    # keyed moves keep their own default
    assert set(cm.RECIPES) == {m for m in cm.MOVES}
    assert all(0 <= r.anchor <= 1 for r in cm.RECIPES.values())


def test_whip_pan_crosses_the_picture_fast_and_lands_on_the_point():
    r = cm.rig("whip-pan", 97)
    x = np.array([c.cx for c in r])
    assert x[-1] - x[0] > 0.3 and np.abs(np.diff(x)).max() > 0.02 and np.allclose(x[:25], x[0])
    land = cm.rig("whip-pan", 97, 1.0, (0.35, 0.5))
    assert abs(land[-1].cx - 0.35) < 1e-6 and land[0].cx > land[-1].cx    # from the far side, onto the point


def test_fpv_banks_and_flies_forward():
    r = cm.rig("fpv", 97)
    assert r[-1].w < 0.6 and max(abs(c.roll) for c in r) > math.radians(2)


def test_view_keys_are_the_rig_view_and_the_plan_follows_them():
    keys = cm.view_keys("dolly-in", 1.0, (0.4, 0.5))
    plan = cg.CameraPlan(cg.camera_path(CameraPreset(move="dolly-in", at=(0.4, 0.5))))
    for t in (0, 0.3, 0.71, 1):
        c, v = cm.cam_at("dolly-in", t, 1.0, (0.4, 0.5)), plan.at(t)
        assert abs(c.w - v.w) < 0.01 and abs(c.cx - v.cx) < 0.01
    assert keys[0]["box"] == [0, 0, 1, 1] or np.allclose(keys[0]["box"], [0, 0, 1, 1])


def test_focus_is_the_depth_at_the_point():
    d = np.zeros((90, 160), np.float32)
    d[30:60, 60:100] = 0.7
    assert cm.focus_depth(d, (0.5, 0.5)) == pytest.approx(0.7)
    assert cm.focus_depth(d, (0.05, 0.05)) == pytest.approx(0.0)
    off = np.zeros((90, 160), np.float32)                                   # a subject low and right of the centre
    off[50:80, 85:110] = 0.6
    assert cm.focus_depth(off, None) == pytest.approx(0.6)                  # is still the focus without `at`
    person = np.zeros((90, 160), np.uint8)
    person[10:30, 10:30] = 255
    off[10:30, 10:30] = 0.33
    assert cm.focus_depth(off, None, subjects=person) == pytest.approx(0.33)   # the named subjects win over the guess
    assert cm.focus_depth(off, (0.6, 0.72), subjects=person) == pytest.approx(0.6)   # and `at` over them


# ---------------------------------------------------------------- renders on a synthetic world

W, H = 192, 108


def world():
    """Three planes, each with a coloured marker: a far wall (yellow dot, depth 0.1), the subject in the middle (red
    square, 0.5) and a near post at the left (green, 0.9)."""
    rgb = np.full((H, W, 3), 70, np.uint8)
    rgb[::6, :, :] = 110                                                   # a little texture on the wall
    d = np.full((H, W), 0.1, np.float32)
    rgb[44:64, 86:106] = (230, 30, 30); d[40:68, 82:110] = 0.5            # subject (depth patch a bit wider than the paint)
    rgb[30:80, 30:44] = (30, 220, 30); d[26:84, 26:48] = 0.9              # near post
    rgb[26:34, 126:134] = (240, 230, 20)                                   # far marker on the wall
    return rgb, d


def centroid(img, colour):
    m = np.all(np.abs(img.astype(int) - np.array(colour)) < 60, axis=2)
    ys, xs = np.nonzero(m)
    return (float(xs.mean()), float(ys.mean()), int(m.sum())) if len(xs) else (float("nan"),) * 3


def frames(move, n=5, amount=1.0, at=(0.5, 0.5)):
    rgb, d = world()
    cams = cm.rig(move, n, amount, at)
    return list(cm.render(rgb, d, cams, size=(W, H), focus=cm.focus_depth(d, at), device="cpu"))


RED, GREEN, YELLOW = (230, 30, 30), (30, 220, 30), (240, 230, 20)


def test_orbit_slides_foreground_against_background_around_a_still_subject():
    f = frames("orbit-left")
    r0, r1 = centroid(f[0], RED), centroid(f[-1], RED)
    g0, g1 = centroid(f[0], GREEN), centroid(f[-1], GREEN)
    y0, y1 = centroid(f[0], YELLOW), centroid(f[-1], YELLOW)
    assert abs(r1[0] - r0[0]) < 2.0                                        # the subject is the pivot
    assert g1[0] - g0[0] > 8 and y1[0] - y0[0] < -4                        # near goes right, far goes left
    fr = frames("orbit-right")
    assert centroid(fr[-1], GREEN)[0] < centroid(fr[0], GREEN)[0]          # the mirror


def test_crane_up_sinks_the_foreground_and_lifts_the_background():
    f = frames("crane-up")
    assert abs(centroid(f[-1], RED)[1] - centroid(f[0], RED)[1]) < 2.0
    assert centroid(f[-1], GREEN)[1] - centroid(f[0], GREEN)[1] > 4.5
    assert centroid(f[-1], YELLOW)[1] - centroid(f[0], YELLOW)[1] < -3


def test_dolly_zoom_keeps_the_subject_size_while_the_background_stretches_away():
    f = frames("dolly-zoom")
    r0, r1 = centroid(f[0], RED), centroid(f[-1], RED)
    assert abs(r1[2] / r0[2] - 1) < 0.08                                   # the subject's area holds
    _, _, ya0 = centroid(f[0], YELLOW)
    _, _, ya1 = centroid(f[-1], YELLOW)
    tall = lambda img: np.ptp(np.nonzero(np.all(np.abs(img.astype(int) - np.array(GREEN)) < 60, axis=2))[0])
    assert ya1 / ya0 < 0.8 and tall(f[-1]) / tall(f[0]) > 1.1              # far shrinks away, near grows (the post is
                                                                           # cut by the frame's edge, so its height)


def test_dolly_zoom_never_needs_picture_from_beyond_the_frame():
    rgb, d = world()
    rgb = rgb.copy()
    rgb[:, :3] = rgb[:, -3:] = rgb[:3] = rgb[-3:] = (255, 0, 255)          # a magenta border: smearing it shows
    cams = cm.rig("dolly-zoom", 5, 1.0, (0.5, 0.5))
    last = list(cm.render(rgb, d, cams, size=(W, H), focus=0.5, device="cpu"))[-1]
    magenta = np.all(np.abs(last.astype(int) - (255, 0, 255)) < 40, axis=2)
    assert magenta.mean() < 0.002


def test_dolly_in_grows_the_near_post_faster_than_the_subject():
    f = frames("dolly-in", at=(0.3, 0.5))
    grow_red = centroid(f[-1], RED)[2] / centroid(f[0], RED)[2]
    grow_green = centroid(f[-1], GREEN)[2] / centroid(f[0], GREEN)[2]
    assert grow_red > 1.3 and grow_green > grow_red * 1.15


def test_static_renders_the_picture_unchanged():
    rgb, _ = world()
    for fr in frames("static", 3):
        assert np.abs(fr.astype(int) - rgb.astype(int)).mean() < 1.5


def test_roll_zero_is_the_old_render_and_a_roll_turns_the_picture():
    rgb, d = world()
    r = fz.Renderer(rgb, d, (W, H), "cpu")
    args = dict(cx=0.5, cy=0.5, w=0.8, sx=0.02, sy=0.0, e=0.1, f=0.5)
    a = r.to_u8(r.frame(**args))
    b = r.to_u8(r.frame(**args, roll=0.0))
    assert np.array_equal(a, b)
    line = np.zeros((H, W, 3), np.uint8)
    line[H // 2 - 1:H // 2 + 1, :] = 255
    rl = fz.Renderer(line, np.zeros((H, W), np.float32), (W, H), "cpu")
    turned = rl.to_u8(rl.frame(0.5, 0.5, 0.7, 0, 0, 0, 0, roll=math.radians(10)))
    ys, xs = np.nonzero(turned[..., 0] > 128)
    slope = np.polyfit(xs, ys, 1)[0]
    assert slope == pytest.approx(-math.tan(math.radians(10)), abs=0.03)   # the camera banks clockwise, the picture turns
                                                                           # the other way, and the turn is not skewed by aspect


def test_a_ray_past_the_edge_sees_the_picture_mirrored_not_a_streak():
    import cv2
    rng = np.random.default_rng(4)
    rgb = cv2.GaussianBlur(rng.integers(0, 255, (H, W, 3), dtype=np.uint8), (0, 0), 1.5)
    d = np.full((H, W), 0.9, np.float32)                                  # all near: a sideways shift reaches past the edge
    args = (0.5, 0.5, 1.0, 0.08, 0.0, 0.0, 0.2)
    clamp = fz.Renderer(rgb, d, (W, H), "cpu")
    mirror = fz.Renderer(rgb, d, (W, H), "cpu", edge="mirror")
    a, b = clamp.to_u8(clamp.frame(*args)), mirror.to_u8(mirror.frame(*args))
    edge_cols = lambda img: float(img[:, :8].astype(np.float32).std(axis=1).mean())   # across the first columns
    assert edge_cols(a) < 1.0 < edge_cols(b)                               # clamp: one colour per row (a streak)
    assert np.array_equal(a[:, 40:], b[:, 40:])                            # inside the picture they agree


def test_motion_blur_averages_sub_frame_cameras():
    rgb, d = world()
    cams = cm.rig("whip-pan", 25)
    sharp = list(cm.render(rgb, d, cams, size=(W, H), focus=0.5, device="cpu"))
    blur = list(cm.render(rgb, d, cams, size=(W, H), focus=0.5, blur=1.5, device="cpu", move="whip-pan"))
    k = int(np.argmax([abs(cams[i + 1].cx - cams[i].cx) for i in range(len(cams) - 1)]))
    import cv2
    lap = lambda im: float(cv2.Sobel(cv2.cvtColor(im, cv2.COLOR_RGB2GRAY), cv2.CV_32F, 1, 0).var())   # across the pan
    assert lap(blur[k]) < lap(sharp[k]) * 0.8                             # blurred where the camera is fast
    assert np.abs(blur[0].astype(int) - sharp[0].astype(int)).mean() < 1.0  # and not where it is still


def test_render_streams_fly_the_named_move():
    rgb, d = world()
    move = CameraPreset(move="orbit-left", subjects="", at=(0.5, 0.5))
    plan = cg.CameraPlan(cg.camera_path(move))
    big = np.repeat(np.repeat(rgb, 2, 0), 2, 1)
    got = list(cg.render_streams(rgb, d, None, move, plan, size=(W, H), n_frames=5, soften=0, device="cpu", rgb_full=big))
    assert len(got) == 5
    assert centroid(got[-1][1], GREEN)[0] - centroid(got[0][1], GREEN)[0] > 8
    assert got[0][2].min() == 255                                          # no subjects: all static world


# ---------------------------------------------------------------- measuring

def _pan(n=13, dx=2):
    rng = np.random.default_rng(1)
    import cv2
    base = cv2.GaussianBlur(rng.integers(0, 255, (120, 400, 3), dtype=np.uint8), (0, 0), 2)
    return [np.ascontiguousarray(base[:, 20 + i * dx:20 + i * dx + 200]) for i in range(n)]


def test_move_agreement_scores_a_follower_high_and_a_still_frame_low():
    ref = _pan()
    same = cm.move_agreement(ref, ref, width=200)
    assert same["gain"] == pytest.approx(1, abs=0.05) and same["cosine"] > 0.95
    still = cm.move_agreement([ref[0]] * len(ref), ref, width=200)
    assert abs(still["gain"]) < 0.2
    assert cm.reads("dolly-in", same) and not cm.reads("dolly-in", still)


def test_a_static_shot_reads_when_it_does_not_drift():
    still = [_pan()[0]] * 9
    held = cm.move_agreement(still, still, width=200)
    assert held["still_steps"] > 0 and held["drift"] < 0.05 and cm.reads("static", held)
    drifting = cm.move_agreement(_pan(9, 3), still, width=200)
    assert drifting["drift"] > 1 and not cm.reads("static", drifting)


# ---------------------------------------------------------------- prompt words and cache keys

def test_named_moves_add_their_words_and_negatives():
    b = beat(camera="orbit-right")
    assert "orbit" in cm.phrase(b.camera).lower()
    assert "static camera" in cm.negative(b.camera, "blur, text")
    s = beat(camera="static")
    neg = cm.negative(s.camera, "static camera, blur")
    assert "static camera" not in neg and "zoom" in neg
    assert cm.negative(beat(camera=KEYS).camera, "blur") == "blur"


def _sec(camera):
    return FilmScene.model_validate({"id": "s", "beats": [{"id": "a", "prompt": "p", "motion": "m", "seconds": 3,
                                                           "camera": camera}]})


def test_stage_keys_change_with_the_move_and_only_then():
    k = lambda cam: cb.key_of(_sec(cam), 0)
    assert k("dolly-in") == k("dolly-in") == k({"move": "dolly-in"})
    assert k("dolly-in") != k("dolly-out")
    assert k("dolly-in") != k({"move": "dolly-in", "amount": 1.2})
    assert k("dolly-in") != k({"move": "dolly-in", "at": [0.3, 0.5]})
    keyed = k(KEYS)                                                       # a keyed beat's key is what it always was
    assert set(keyed) == {"move", "backend", "v"} and set(keyed["move"]) == set(CameraMove.model_fields)
