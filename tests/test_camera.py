"""Camera moves on moving beats (`camera:`): the spec, the camera plan (and chains that continue one another), the guide
renderer, the follow-error measurement and the backends' graphs. No ComfyUI and no GPU: the render runs on torch's CPU,
the 'video model' is a synthetic camera render, and ComfyUI's model lists are stubbed."""
from __future__ import annotations

import math
import shutil

import numpy as np
import pytest
from pydantic import ValidationError

from engine import camera_beats as cb
from engine import camera_guide as cg
from engine.spec import Beat, CameraMove

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")

KEYS = [{"t": 0, "box": [0, 0, 1, 1]}, {"t": 0.5, "box": [0.40, 0.38, 0.62, 0.97]}, {"t": 1, "box": [0, 0, 1, 1]}]


def beat(id="a", seconds=3, **kw) -> Beat:
    return Beat.model_validate({"id": id, "seconds": seconds, "prompt": "a crowd", "motion": "they walk", **kw})


def texture(w=320, h=192, seed=3) -> np.ndarray:
    """A picture with plenty of corners to track: blurred noise with some bright blobs."""
    import cv2
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    a = cv2.GaussianBlur(a, (0, 0), 2.2)
    a = cv2.normalize(a, None, 0, 255, cv2.NORM_MINMAX)
    for _ in range(40):
        cv2.circle(a, (int(rng.integers(0, w)), int(rng.integers(0, h))), int(rng.integers(3, 9)),
                   tuple(int(v) for v in rng.integers(0, 255, 3)), -1)
    return a


# ---------------------------------------------------------------- spec

def test_camera_keys_validate_and_a_bare_list_is_the_keys():
    b = beat(camera=KEYS)
    assert [k.t for k in b.camera.keys] == [0, 0.5, 1] and b.camera.backend == "auto" and b.camera.ease == "inOutSine"
    assert b.camera.subjects == "the people"
    assert Beat.model_validate(b.model_dump(mode="json")).camera.keys[1].box == (0.40, 0.38, 0.62, 0.97)
    full = beat(camera={"keys": KEYS, "backend": "wan", "ease": "flow", "soften": 0.1})
    assert full.camera.backend == "wan" and full.camera.ease == "flow"


def test_camera_keys_must_make_sense():
    with pytest.raises(ValidationError, match="forward in time"):
        beat(camera=[{"t": 0.5, "box": [0, 0, 1, 1]}, {"t": 0.2, "box": [0, 0, 0.5, 0.5]}])
    with pytest.raises(ValidationError, match="inside 0-1"):
        beat(camera=[{"t": 0, "box": [0, 0, 1.2, 1]}])
    with pytest.raises(ValidationError, match="hold runs past"):
        beat(camera=[{"t": 0.9, "box": [0, 0, 1, 1], "hold": 0.3}])
    with pytest.raises(ValidationError, match="end_image"):
        beat(camera=KEYS, end_image="x.png")
    with pytest.raises(ValidationError, match="trim"):
        beat(camera=KEYS, trim=1.0)
    with pytest.raises(ValidationError, match="first key must come after"):
        beat(camera={"keys": KEYS, "continues": True})
    with pytest.raises(ValidationError):
        CameraMove(keys=KEYS, backend="nope")
    with pytest.raises(ValidationError, match="frozen moment has"):
        Beat.model_validate({"id": "f", "camera": KEYS, "freeze": {"image": "x.png"}})


def test_a_plain_beat_has_no_camera_and_dumps_the_same():
    b = beat()
    assert b.camera is None
    assert "camera" not in b.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------- the camera plan

def test_a_beat_alone_is_its_own_path():
    b = beat(camera=KEYS)
    plan = cg.plan_for([b], 0)
    assert plan.at(0).w == pytest.approx(1.0) and plan.at(0.5).w == pytest.approx(0.59, abs=1e-6) and plan.at(1).w == pytest.approx(1.0)
    ks = plan.keys(5)
    assert [k["t"] for k in ks] == [0, 0.25, 0.5, 0.75, 1]
    # the dense keys reproduce the plan under the renderer's own path (linear between frame keys)
    path = cg.CameraPath(ks, "linear")
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert path.at(t).w == pytest.approx(plan.at(t).w, abs=1e-6)


def test_beats_that_continue_share_one_path_and_carry_the_speed():
    a = beat("a", 3, camera=[{"t": 0, "box": [0, 0, 1, 1]}, {"t": 1, "box": [0.15, 0.1, 0.85, 0.8]}])
    b = beat("b", 4, camera={"keys": [{"t": 0.6, "box": [0.40, 0.38, 0.62, 0.97], "hold": 0.1},
                                      {"t": 1, "box": [0, 0, 1, 1]}], "continues": True})
    pa, pb = cg.plan_for([a, b], 0), cg.plan_for([a, b], 1)
    assert cg.chain_of([a, b], 0) == [0, 1] == cg.chain_of([a, b], 1)
    # position carries across the cut
    va, vb = pa.at(1.0), pb.at(0.0)
    assert (va.cx, va.cy, va.w) == pytest.approx((vb.cx, vb.cy, vb.w), abs=1e-9)
    # and so does the speed: the zoom rate (per second) just before the cut equals the rate just after it
    e = 1e-3
    rate_a = (math.log(pa.at(1.0).w) - math.log(pa.at(1 - e).w)) / (e * a.seconds)
    rate_b = (math.log(pb.at(e).w) - math.log(pb.at(0.0).w)) / (e * b.seconds)
    assert abs(rate_a) > 0.05                       # it really is moving at the cut, not resting
    assert rate_b == pytest.approx(rate_a, rel=0.05)
    # alone, the first beat eases to a stop at its end; chained it keeps moving through the cut
    alone = cg.plan_for([a], 0)
    assert abs(math.log(alone.at(1.0).w) - math.log(alone.at(1 - e).w)) / (e * a.seconds) < abs(rate_a) * 0.1
    assert pa.at(0).w == pytest.approx(1.0) and pb.at(1).w == pytest.approx(1.0)


def test_chain_of_needs_camera_beats_in_a_row():
    a = beat("a", camera=KEYS)
    plain = beat("p")
    b = beat("b", camera={"keys": [{"t": 0.5, "box": [0, 0, 1, 1]}], "continues": True})
    assert cg.chain_of([a, plain, b], 2) == [2]
    assert cg.chain_of([a, b, plain], 0) == [0, 1]


# ---------------------------------------------------------------- the guide

def test_soften_subjects_blurs_inside_the_mask_only():
    d = np.zeros((64, 96), np.float32)
    d[:, 40:56] = 1.0
    people = np.zeros((64, 96), np.uint8)
    people[:, 40:56] = 255
    out = cg.soften_subjects(d, people, 6.0)
    assert out[:, :10].max() < 1e-3                       # far from the subject nothing changes
    assert 0.5 < out[32, 48] < 1.0 or out[32, 48] > 0.5   # the subject's depth is kept, softened at its edges
    assert np.abs(out - d).max() > 0.05
    assert cg.soften_subjects(d, people, 0) is d


def test_render_streams_agree_and_start_on_the_picture():
    rgb = texture(160, 96)
    depth = np.tile(np.linspace(0, 1, 160, dtype=np.float32), (96, 1))
    people = np.zeros((96, 160), np.uint8)
    people[20:70, 60:80] = 255
    move = CameraMove(keys=KEYS, parallax=0.3)
    plan = cg.CameraPlan(cg.camera_path(move))
    got = list(cg.render_streams(rgb, depth, people, move, plan, size=(160, 96), n_frames=9, soften=4.0, device="cpu"))
    assert len(got) == 9
    d, c, m = got[0]
    assert d.shape == (96, 160, 3) and c.shape == (96, 160, 3) and m.shape == (96, 160)
    assert np.abs(c.astype(int) - rgb.astype(int)).mean() < 2.5      # the first frame is the picture itself
    assert m[0, 0] == 255 and m[45, 70] == 0                          # static world is 255, the people are 0
    _, c4, _ = got[4]                                                  # mid-move the camera is much closer
    assert np.abs(c4.astype(int) - rgb.astype(int)).mean() > 15


@needs_ffmpeg
def test_write_guide_writes_three_videos(tmp_path):
    rgb = texture(160, 96)
    depth = np.full((96, 160), 0.4, np.float32)
    move = CameraMove(keys=KEYS, parallax=0.0)
    plan = cg.CameraPlan(cg.camera_path(move))
    g = cg.write_guide(tmp_path, rgb, depth, None, move, plan, size=(160, 96), n_frames=9, fps=24, soften=0, name="g")
    assert g.depth.exists() and g.rgb.exists() and g.static.exists() and g.frames == 9
    assert len(cg.read_video(g.rgb)) == 9


# ---------------------------------------------------------------- measuring the camera

def zoomed(img: np.ndarray, v: cg.View) -> np.ndarray:
    import cv2
    H, W = img.shape[:2]
    M = np.float32([[1 / v.w, 0, W / 2 - v.cx * W / v.w], [0, 1 / v.w, H / 2 - v.cy * H / v.w]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def test_follow_error_is_small_for_a_camera_that_follows_and_large_for_one_that_does_not():
    img = texture()
    move = CameraMove(keys=KEYS)
    plan = cg.CameraPlan(cg.camera_path(move))
    n = 13
    good = [zoomed(img, plan.at(i / (n - 1))) for i in range(n)]
    r = cg.follow_error(good, plan)
    assert r["lost"] == 0 and r["zoom_rms"] < 1.0 and r["shift_rms"] < 0.01
    frozen = [img] * n                                   # a model that ignored the camera keys
    bad = cg.follow_error(frozen, plan)
    assert bad["zoom_max"] > 30
    late = [zoomed(img, plan.at(min(1.0, max(0.0, i / (n - 1) - 0.25)))) for i in range(n)]      # a camera a quarter late
    assert cg.follow_error(late, plan)["zoom_rms"] > 5 * r["zoom_rms"]


def test_view_from_transform_roundtrip():
    A = np.array([[2.0, 0, -60.0], [0, 2.0, -20.0]])
    v = cg.view_from_transform(A, (160, 96))
    assert v.w == pytest.approx(0.5) and v.cx == pytest.approx((80 + 60) / (2 * 160)) and v.cy == pytest.approx((48 + 20) / (2 * 96))


def test_people_motion_reads_a_walker_above_the_floor():
    bg = texture(256, 160, seed=5)
    people = np.zeros((160, 256), np.uint8)
    people[50:120, 100:140] = 255
    frames = []
    for i in range(10):
        f = bg.copy()
        x = 100 + i * 2                                   # a block walks two pixels a frame
        f[50:120, x:x + 40] = texture(40, 70, seed=9)
        frames.append(f)
    static = [np.where(people > 0, 0, 255).astype(np.uint8)] * 10
    r = cg.people_motion(frames, people, static)
    assert r["people_px_per_frame"] > 5 * r["static_px_per_frame"] + 0.2


# ---------------------------------------------------------------- tone and grain

def test_tone_match_pulls_a_drifted_clip_back_and_adds_grain():
    ref = texture(160, 96, seed=4)
    drifted = np.clip(ref.astype(np.float32) * 0.8 + 35, 0, 255).astype(np.uint8)        # flatter and brighter
    static = np.full((96, 160), 255, np.uint8)
    out = cg.tone_match([drifted] * 4, [ref] * 4, [static] * 4, 1.0)
    before = abs(float(drifted.mean()) - float(ref.mean()))
    after = abs(float(out[0].mean()) - float(ref.mean()))
    assert after < before * 0.2
    assert abs(float(out[0].std()) - float(ref.std())) < abs(float(drifted.std()) - float(ref.std()))
    same = cg.tone_match([ref] * 3, [ref] * 3, [static] * 3, 0.7)
    assert np.abs(same[0].astype(int) - ref.astype(int)).mean() < 1.5                  # nothing to correct, nothing changed
    assert cg.tone_match([drifted], [ref], [static], 0.0)[0].tolist() == drifted.tolist()


# ---------------------------------------------------------------- sizes and keys

def test_generation_sizes_fit_the_models():
    w, h = cb.gen_size((1920, 1088), "ltx", 121)
    assert (w, h) == (1024, 576) and (w // 32) * (h // 32) * 16 <= 22000
    assert cb.gen_size((1920, 1088), "ltx", 121, (1536, 896)) == (1536, 896)         # the spec's own `res`
    assert cb.gen_size((768, 448), "ltx", 73) == (768, 448)
    w, h = cb.gen_size((1920, 1088), "wan", 81)
    assert w % 16 == 0 and h % 16 == 0 and w * h <= 1280 * 720 * 1.02


def test_the_stage_key_only_exists_for_camera_beats_and_follows_the_keys():
    from engine.spec import FilmScene
    sec = FilmScene.model_validate({"id": "s", "beats": [
        {"id": "a", "prompt": "p", "motion": "m", "seconds": 3, "camera": KEYS},
        {"id": "b", "prompt": "p", "motion": "m", "seconds": 3, "camera": {"keys": KEYS[1:], "continues": True}}]})
    ka, kb = cb.key_of(sec, 0), cb.key_of(sec, 1)
    assert ka["backend"] == "ltx" and "chain" in ka and "chain" in kb       # the first beat's guide depends on who continues it
    sec2 = FilmScene.model_validate({"id": "s", "beats": [{"id": "a", "prompt": "p", "motion": "m", "seconds": 3, "camera": KEYS}]})
    assert "chain" not in cb.key_of(sec2, 0)
    moved = [dict(k) for k in KEYS]
    moved[1] = {"t": 0.5, "box": [0.3, 0.3, 0.6, 0.9]}
    sec3 = FilmScene.model_validate({"id": "s", "beats": [{"id": "a", "prompt": "p", "motion": "m", "seconds": 3, "camera": moved}]})
    assert cb.key_of(sec3, 0) != cb.key_of(sec2, 0)


# ---------------------------------------------------------------- backends

def test_uni3c_without_its_file_names_the_file_the_url_and_where_it_goes(monkeypatch):
    from engine.backends import comfy
    monkeypatch.setattr(comfy, "listed", lambda folder: ["Z-Image-Turbo-Fun-Controlnet-Union-2.1-2602-8steps.safetensors"])
    from engine.project import BuildError
    with pytest.raises(BuildError) as e:
        cg.uni3c_name()
    msg = str(e.value)
    assert "Wan21_Uni3C_controlnet_fp16.safetensors" in msg and "huggingface.co/Kijai/WanVideo_comfy" in msg
    assert "model_patches" in msg and "Apache-2.0" in msg and "2 GB" in msg
    monkeypatch.setattr(comfy, "listed", lambda folder: ["sub/Wan21_Uni3C_controlnet_fp16.safetensors"])
    assert cg.uni3c_name() == "sub/Wan21_Uni3C_controlnet_fp16.safetensors"        # found by base name


def test_uni3c_graph_wraps_both_experts(monkeypatch):
    from engine.backends import comfy
    monkeypatch.setattr(comfy, "listed", lambda folder: None)             # ComfyUI not reachable: the names are not checked
    g = cg.build_uni3c_graph({}, "walk", "", (768, 448), 49, 7, "p", "start.png", "render.mp4", 0.8, "u3c.safetensors")
    assert g["u3c_patch"]["inputs"]["name"] == "u3c.safetensors"
    for tag in ("hi", "lo"):
        assert g[f"u3c_{tag}"]["class_type"] == "WanUni3CControlnetApply"
        assert g[f"u3c_{tag}"]["inputs"]["strength"] == 0.8
        assert g[f"shift_{tag}"]["inputs"]["model"] == [f"u3c_{tag}", 0]
    assert g["cond"]["class_type"] == "WanImageToVideo"


def test_wan_fun_control_graph_carries_the_guide_and_the_start_image(monkeypatch):
    from engine.backends import comfy
    monkeypatch.setattr(comfy, "listed", lambda folder: None)
    g = comfy.build_wan_graph({}, "walk", "", 768, 448, 49, 7, "p", start_image="s.png", ref_image="s.png", control_video="g.mp4")
    assert g["cond"]["class_type"] == "Wan22FunControlToVideo"
    assert g["ctl_vid"]["inputs"]["file"] == "g.mp4" and g["cond"]["inputs"]["start_image"] == ["first", 0]


def test_ltx_graph_is_a_take_guide_with_the_start_image(monkeypatch):
    from engine.backends import comfy
    cfg = dict(comfy.LTX, prompt="walk", negative_prompt="", keyframe_strength=1.0, guide_strength=0.9, seed=3, upscale=False)
    g = comfy.build_graph(cfg, "g.mp4", "s.png", 73, 768, 448, 24, "p")
    assert g["guide_vid"]["inputs"]["file"] == "g.mp4" and g["addguide"]["inputs"]["strength"] == 0.9
    assert g["i2v"]["inputs"]["bypass"] is False


# ---------------------------------------------------------------- stabilising, displacement, the sheet

def test_stabilised_frames_undo_the_camera_and_the_sheet_is_written(tmp_path):
    img = texture()
    move = CameraMove(keys=KEYS)
    plan = cg.CameraPlan(cg.camera_path(move))
    n = 9
    frames = [zoomed(img, plan.at(i / (n - 1))) for i in range(n)]
    st = cg.stabilised(frames)
    mid = st[4]
    assert mid is not None
    # the middle frame (zoomed in) warped back lines up with the first inside the area it sees
    H, W = img.shape[:2]
    cy0, cx0 = H // 2, W // 2
    a = mid[cy0 - 20:cy0 + 20, cx0 - 30:cx0 + 30].astype(int)
    b = img[cy0 - 20:cy0 + 20, cx0 - 30:cx0 + 30].astype(int)
    assert np.abs(a - b).mean() < 14
    cg.contact_sheet([("a", frames), ("b", [f if f is not None else frames[0] for f in st])], tmp_path / "s.jpg", cols=4, cell=96)
    assert (tmp_path / "s.jpg").stat().st_size > 1000


def test_people_displacement_separates_walkers_from_a_frozen_picture():
    bg = texture(256, 160, seed=5)
    people = np.zeros((160, 256), np.uint8)
    people[50:120, 100:140] = 255
    static = [np.where(people > 0, 0, 255).astype(np.uint8)] * 12
    walker = texture(40, 70, seed=9)
    walking = []
    for i in range(12):
        f = bg.copy()
        x = 100 + i * 2
        f[50:120, x:x + 40] = walker
        walking.append(f)
    still = [bg.copy() for _ in range(12)]
    w = cg.people_displacement(walking, people, static)
    s = cg.people_displacement(still, people, static)
    assert w["people_end_px"] > s["people_end_px"] + 1.0
    assert s["people_end_px"] < 1.0


def test_a_beat_that_starts_zoomed_is_measured_against_its_own_first_frame():
    img = texture()
    a = beat("a", 3, camera=[{"t": 0, "box": [0, 0, 1, 1]}, {"t": 1, "box": [0.15, 0.1, 0.85, 0.8]}])
    b = beat("b", 3, camera={"keys": [{"t": 0.5, "box": [0.40, 0.38, 0.62, 0.97]}, {"t": 1, "box": [0, 0, 1, 1]}], "continues": True})
    plan = cg.plan_for([a, b], 1)
    origin = plan.at(0.0)
    assert origin.w < 0.8                                     # it starts zoomed in, where `a` ended
    n = 13
    # what a camera that follows the plan sees, as a picture of the first frame of the beat: render the world, then take
    # the beat's own first frame as the reference
    world = [zoomed(img, plan.at(i / (n - 1))) for i in range(n)]
    r = cg.follow_error(world, plan)
    assert r["lost"] == 0 and r["zoom_rms"] < 1.5 and r["shift_rms"] < 0.02
    rel = cg.relative_view(plan.at(0.0), origin)
    assert (rel.cx, rel.cy, rel.w) == pytest.approx((0.5, 0.5, 1.0))


def test_a_continued_beats_grading_fades_in_and_leaves_frame_zero_alone():
    ref = texture(160, 96, seed=4)
    drifted = np.clip(ref.astype(np.float32) * 0.8 + 35, 0, 255).astype(np.uint8)
    static = np.full((96, 160), 255, np.uint8)
    out = cg.tone_match([drifted] * 12, [ref] * 12, [static] * 12, 1.0, ramp=6)
    assert out[0].tolist() == drifted.tolist()                       # the first frame is the previous beat's last frame, untouched
    steps = [abs(float(o.mean()) - float(drifted.mean())) for o in out]
    assert steps[1] < steps[3] < steps[6] and steps[11] > 5          # the correction arrives gradually, then holds


def test_a_continued_beat_starts_on_the_last_frame_of_the_beat_before():
    from engine.spec import FilmScene
    sec = FilmScene.model_validate({"id": "s", "beats": [
        {"id": "a", "prompt": "p", "motion": "m", "seconds": 3, "image": "x.png", "camera": KEYS},
        {"id": "b", "prompt": "p", "motion": "m", "seconds": 3, "camera": {"keys": KEYS[1:], "continues": True}},
        {"id": "c", "prompt": "p", "motion": "m", "seconds": 3}]})
    assert cb.start_ref(sec, 0, (768, 448)) == "x.png"
    ref = cb.start_ref(sec, 1, (768, 448))
    assert ref.beat_frame.beat == "a" and ref.beat_frame.at == "last"
    assert cb.start_ref(sec, 2, (768, 448)).generate == "p"


def test_continued_beats_join_with_a_frame_not_a_crossfade():
    from engine.scenes.film import beat_spans, join_fades
    from engine.spec import FilmScene
    sec = FilmScene.model_validate({"id": "s", "beat_fade": 0.4, "beats": [
        {"id": "a", "prompt": "p", "motion": "m", "seconds": 3, "camera": KEYS},
        {"id": "b", "prompt": "p", "motion": "m", "seconds": 3, "camera": {"keys": KEYS[1:], "continues": True}},
        {"id": "c", "prompt": "p", "motion": "m", "seconds": 3}]})
    durs = [3.0, 3.0, 3.0]
    fades = join_fades(sec, durs)
    assert fades[0] == pytest.approx(1 / 24) and fades[1] == pytest.approx(0.4)      # a -> b is a hard join, b -> c a crossfade
    spans = beat_spans(sec, durs, fades)
    total = 9.0 - sum(fades)
    assert spans["b"][0] == pytest.approx((3.0 - 1 / 24) / total) and spans["c"][1] == pytest.approx(1.0)
    # the old scalar form still works
    assert beat_spans(sec, durs, 0.4)["c"][0] == pytest.approx((6 - 0.8) / (9 - 0.8))


@needs_ffmpeg
def test_anchors_are_pure_camera_frames_at_latent_boundaries(tmp_path):
    rgb = texture(128, 64)
    depth = np.full((64, 128), 0.4, np.float32)
    move = CameraMove(keys=KEYS, parallax=0.0)
    plan = cg.CameraPlan(cg.camera_path(move))
    g = cg.write_guide(tmp_path, rgb, depth, None, move, plan, size=(128, 64), n_frames=121, fps=24, soften=0, name="g")
    anchors = cb._anchors(g, (128, 64), 0.6, tmp_path)
    idx = [i for _, i, _ in anchors]
    assert idx == [24, 48, 72, 96, -1] and all(s == 0.6 for _, _, s in anchors)
    assert all(i % 8 == 0 for i in idx if i > 0) and all(p.exists() for p, _, _ in anchors)
