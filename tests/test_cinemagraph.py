"""Cinemagraphs: `cinemagraph:` on an image input.

The spec, the cache keys (an image without one is keyed exactly as before), the pure parts of the builder (seam measure,
loop closing, stabilising, tone matching, the mask), the stages with the models replaced by fakes (what is cached, what a
changed field redoes, that the page's composite leaves the still's pixels alone outside the mask), and the page wiring
(data-cine on the still in every markup, the video and mask copied in). No ComfyUI, GPU or browser needed."""
from __future__ import annotations

import json
import textwrap

import numpy as np
import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from engine import cinemagraph as C
from engine.inputs import image_key, stable_dump
from engine.project import BuildError, Project
from engine.spec import Cinemagraph, ImageInput, Site


# ---------------------------------------------------------------- the spec

def test_the_documented_example_validates():
    img = ImageInput.model_validate(yaml.safe_load(textwrap.dedent('''\
        generate: "a cup of coffee on an oak table, steam rising, window light"
        cinemagraph: { moves: "the steam above the cup", motion: "slow, curling upward", seconds: 4, loop: seamless, strength: 0.8 }
        ''')))
    c = img.cinemagraph
    assert c.moves == "the steam above the cup" and c.seconds == 4 and c.loop == "seamless" and c.strength == 0.8
    assert c.track and c.grow == 10 and c.feather == 28 and c.model is None


def test_bounds_and_unknown_fields_are_refused():
    for bad in ({"moves": "x", "loop": "forever"}, {"moves": "x", "seconds": 60}, {"moves": "x", "strength": 0}, {"seconds": 4},
                {"moves": "x", "colour": "red"}):
        with pytest.raises(ValidationError):
            Cinemagraph.model_validate(bad)


def test_wherever_an_image_is_used():
    site = Site.model_validate(yaml.safe_load(textwrap.dedent('''\
        name: T
        sections:
          - {type: hero, title: A, image: {generate: x, cinemagraph: {moves: the steam}}}
          - {type: product, title: B, image: {file: a.png, cinemagraph: {moves: the flame}}, backdrop: {file: b.png, cinemagraph: {moves: the water}}}
          - {type: strip, items: [{image: {generate: y}}, {image: {generate: z, cinemagraph: {moves: the curtain}}}]}
          - {type: gallery, items: [{title: One, href: "#", image: {generate: q, cinemagraph: {moves: smoke}}}, {title: Two, href: "#", image: p.png}]}
        ''')))
    found = C.collect(site)
    assert sorted(i.cinemagraph.moves for _, i in found) == ["smoke", "the curtain", "the flame", "the steam", "the water"]
    assert {w.split(".")[0].split("[")[0] for w, _ in found} == {"sections"}


# ---------------------------------------------------------------- cache keys: plain images are untouched

def test_a_plain_image_is_keyed_as_before():
    plain = ImageInput(generate="a lamp", seed=3)
    assert "cinemagraph" not in stable_dump(plain)
    assert image_key(plain) == image_key(ImageInput(generate="a lamp", seed=3))
    moving = ImageInput(generate="a lamp", seed=3, cinemagraph=Cinemagraph(moves="the flame"))
    assert image_key(moving) == image_key(plain)            # the picture is the same picture; only the page moves part of it
    assert "cinemagraph" in stable_dump(moving)


# ---------------------------------------------------------------- the pure parts

def _scene(H=240, W=320, T=48, seed=1):
    """A textured still, and a clip of it in which a blob swings once round (a loop by construction)."""
    import cv2
    rng = np.random.default_rng(seed)
    still = cv2.GaussianBlur((rng.random((H, W, 3)) * 80 + 90).astype(np.uint8), (0, 0), 2.5)
    frames = np.repeat(still[None], T, 0).copy()
    for t in range(T):
        cx = W / 2 + 40 * np.sin(2 * np.pi * t / T)
        cv2.circle(frames[t], (int(cx), H // 2), 26, (230, 205, 150), -1)
        frames[t] = cv2.GaussianBlur(frames[t], (0, 0), 1.6)
    seed_mask = np.zeros((H, W), np.uint8)
    cv2.circle(seed_mask, (W // 2, H // 2), 30, 255, -1)
    return still, frames, seed_mask


def test_the_seam_measure_tells_a_loop_from_a_cut():
    still, frames, seed = _scene()
    m, _ = C.final_mask(seed, C.motion_energy(frames), 6, 16)
    closed = C.seam_report(frames, m)
    cut = C.seam_report(frames[:34], m)                     # a clip stopped part-way round: its end is not its start
    assert closed["ratio"] <= C.SEAM_OK < cut["ratio"]


def test_closing_a_loop_and_pingpong_remove_the_seam():
    still, frames, seed = _scene()
    m, _ = C.final_mask(seed, C.motion_energy(frames), 6, 16)
    cut = frames[:34]
    assert C.seam_report(cut, m)["ratio"] > 3
    for flow in (False, True):
        closed = C.close_loop(cut, 8, flow=flow)
        assert len(closed) == 34 - 8
        assert C.seam_report(closed, m)["ratio"] < C.seam_report(cut, m)["ratio"] / 2
    pp = C.pingpong(cut)
    assert len(pp) == 34 + 32 and C.seam_report(pp, m)["ratio"] <= C.SEAM_OK


def test_damping_scales_the_motion_about_its_mean():
    _, frames, _ = _scene()
    calm = C.damp(frames, 0.5)
    assert np.std(calm.astype(float), axis=0).mean() < 0.6 * np.std(frames.astype(float), axis=0).mean()
    assert C.damp(frames, 1.0) is frames


def test_a_video_models_camera_move_is_taken_out():
    import cv2
    still, _, _ = _scene(H=320, W=400)
    T, (H, W) = 6, still.shape[:2]
    # a push in with a pan: 1.5 % zoom and 5 px by the last frame
    moved = np.stack([cv2.warpAffine(still, np.array([[1 + 0.003 * t, 0, 1.0 * t], [0, 1 + 0.003 * t, -0.6 * t]], np.float32),
                                     (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE) for t in range(T)])
    keep = np.full((H, W), 255, np.uint8)
    keep[80:200, 120:260] = 0
    fixed, shifts = C.stabilise_flow(moved, still, keep)
    assert shifts.max() > 2 and len(shifts) == T
    err = lambda a: np.abs(a[-1].astype(float) - still)[keep > 0].mean()
    assert err(fixed) < err(moved) / 3


def test_a_clip_is_cut_where_it_stops_being_a_cinemagraph():
    still, frames, seed = _scene(T=48)
    sharpen = lambda a: np.clip(128 + (a.astype(np.float32) - 110) * 6, 0, 255).astype(np.uint8)    # texture a registration can see
    still, frames = sharpen(still), sharpen(frames)
    # the picture around the moving part stays put for 20 frames, then the "camera" moves
    clip = frames.copy()
    for t in range(20, 48):
        clip[t] = np.roll(frames[t], 3 + (t - 20), axis=1)
    cut, info = C.trim_to_budget(clip, still, seed, 1.0, region_budget=False)
    assert 12 <= info["kept"] <= 24 and info["cut_because"].startswith("the picture")
    whole, wi = C.trim_to_budget(frames, still, seed, 1.0, region_budget=False)
    assert wi["kept"] == 48 and wi["cut_because"] is None


def test_a_pingpong_clip_is_cut_where_the_motion_has_gone_far_enough():
    still, frames, seed = _scene(T=48)
    cut, info = C.trim_to_budget(frames, still, seed, 1.0, region_budget=True)
    assert info["of"] == 48 and C.FPS // 2 <= info["kept"] <= 48
    tight, ti = C.trim_to_budget(frames, still, seed, 0.2, region_budget=True)   # a tighter budget cuts sooner, never below the floor
    assert C.FPS // 2 <= ti["kept"] <= info["kept"]
    calm, ci = C.trim_to_budget(np.repeat(still[None], 30, 0), still, seed, 1.0, region_budget=True)  # nothing moves: kept whole
    assert ci["kept"] == 30


def test_slowing_a_clip_fills_the_loop_without_changing_its_ends():
    _, frames, _ = _scene(T=20)
    slowed = C.slow(frames, 36)
    assert len(slowed) == 36 and (slowed[0] == frames[0]).all() and (slowed[-1] == frames[-1]).all()
    assert C.slow(frames, 10) is frames


def test_tone_matching_removes_a_global_shade():
    still, frames, seed = _scene()
    m, _ = C.final_mask(seed, C.motion_energy(frames), 6, 16)
    shaded = np.clip(frames.astype(int) * 1.05 + 6, 0, 255).astype(np.uint8)
    matched = C.tone_match(shaded, still, m, 12)
    ring = (m == 0)
    assert np.abs(matched[:, ring].astype(float) - still[ring]).mean() < np.abs(shaded[:, ring].astype(float) - still[ring]).mean() / 3


def test_a_clip_that_moves_nowhere_is_an_error():
    still, _, seed = _scene()
    flat = np.repeat(still[None], 12, 0)
    with pytest.raises(BuildError, match="nothing in the region moves"):
        C.final_mask(seed, C.motion_energy(flat), 6, 16)


def test_the_mask_follows_motion_beyond_the_found_region():
    still, frames, seed = _scene()
    small = np.zeros_like(seed)
    small[110:130, 150:170] = 255                           # the region found is only a part of what moves
    m, info = C.final_mask(small, C.motion_energy(frames), 6, 16)
    assert (m > 127).sum() > 3 * (small > 0).sum()
    assert m[0, 0] == 0 and m.max() == 255                  # the far corner is the still; the blob is the video
    # and a region that does not move is left as the still
    still_part = np.zeros_like(seed)
    still_part[10:40, 10:40] = 255
    m2, _ = C.final_mask(seed | still_part, C.motion_energy(frames), 6, 16)
    assert m2[20, 20] == 0


def test_outside_the_mask_the_page_shows_the_still_exactly():
    still, frames, seed = _scene()
    m, _ = C.final_mask(seed, C.motion_energy(frames), 6, 16)
    video = C.composite_video(frames, still, m)
    z = m == 0
    assert (video[:, z] == still[z]).all()                  # the file itself holds the still outside the mask
    for t in (0, 11, 23):
        shown = C.page_composite(still, frames[t], m)       # what the browser shows: poster x (1 - mask) + video x mask
        assert (shown[z] == still[z]).all()
        assert (shown[m == 255] == frames[t][m == 255]).all()


def test_lossless_clips_and_the_encoded_video_read_back(tmp_path):
    still, frames, seed = _scene(H=240, W=320, T=24)
    C.write_lossless(frames, tmp_path / "c.mkv")
    assert (C.read_video(tmp_path / "c.mkv") == frames).all()
    C.encode_h264(frames, tmp_path / "c.mp4")
    back = C.read_video(tmp_path / "c.mp4")
    assert back.shape == frames.shape and np.abs(back.astype(float) - frames).mean() < 4
    assert (tmp_path / "c.mp4").stat().st_size < 120_000
    m, _ = C.final_mask(seed, C.motion_energy(frames), 6, 16)
    C.save_mask(m, tmp_path / "m.webp")
    got = np.asarray(Image.open(tmp_path / "m.webp").convert("RGBA"))[..., 3]
    assert (got == m).all()                                 # lossless: the weights are the measured ones


# ---------------------------------------------------------------- the stages, with the models faked

@pytest.fixture()
def fake(tmp_path, monkeypatch):
    """A project with a still file; Florence/SAM (region.find) and the video model (animate.animate) replaced."""
    import cv2
    from engine import animate, region
    still, frames, seed = _scene(H=480, W=640, T=25)
    root = tmp_path / "proj"
    (root / "inputs").mkdir(parents=True)
    Image.fromarray(still).save(root / "inputs" / "still.png")
    (root / "site.yaml").write_text("name: T\nsections: [{type: intro, title: x}]\n", encoding="utf-8")
    calls = {"animate": 0, "find": 0}
    big_seed = cv2.resize(seed, (640, 480), interpolation=cv2.INTER_NEAREST)

    def find(project, src, reg, log=print):
        calls["find"] += 1
        from engine.project import file_key
        out = project.build / "_generated" / f"region_{region._digest([file_key(src), region.find_spec(reg), 'large', region.VERSION])}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(big_seed).save(out)
        return out

    def anim(still_png, prompt, motion, seconds, seed_, work, log=print, size=None, negative="", strength=1.0, end_image=None,
             model="ltx", wan=None, timeout=0):
        calls["animate"] += 1
        calls["last"] = {"motion": motion, "end": end_image is not None, "size": size, "model": model, "seconds": seconds}
        crop = np.asarray(Image.open(still_png).convert("RGB"))
        h, w = crop.shape[:2]
        d = work / "frames"
        d.mkdir(parents=True, exist_ok=True)
        out = []
        for t in range(25):
            f = crop.copy()
            cx = w // 2 + int(40 * np.sin(2 * np.pi * t / 24))
            cv2.circle(f, (cx, h // 2), 26, (230, 205, 150), -1)
            p = d / f"{t + 1:04d}.png"
            Image.fromarray(f).save(p)
            out.append(p)
        return out

    monkeypatch.setattr(region, "find", find)
    monkeypatch.setattr(animate, "animate", anim)
    monkeypatch.setattr(C, "_track", lambda *a, **k: (_ for _ in ()).throw(BuildError("no ComfyUI in tests")))
    return Project(root), calls


def _ref(**kw):
    return ImageInput(file="inputs/still.png", cinemagraph=Cinemagraph(moves="the swinging blob", **kw))


def test_a_cinemagraph_builds_and_every_stage_is_cached(fake):
    project, calls = fake
    b = C.build(project, _ref(seconds=1.0), lambda m: None)
    assert b["video"].exists() and b["mask"].exists()
    rep = b["data"]
    assert rep["loop"]["seamless"] and rep["held"]["max_change_outside_mask"] == 0
    assert 0.0 < rep["mask"]["share_of_still"] < 0.5 and rep["motion"]["temporal_std"] > 3
    assert calls["animate"] == 1 and calls["last"]["end"] is False           # a free clip, closed afterwards
    x0, y0, x1, y1 = b["box"]
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1 and b["still"] == [640, 480]
    again = C.build(project, _ref(seconds=1.0), lambda m: None)
    assert calls["animate"] == 1 and again["id"] == b["id"]                  # nothing rebuilt


def test_a_changed_field_redoes_only_what_follows_it(fake):
    project, calls = fake
    first = C.build(project, _ref(seconds=4.0), lambda m: None)
    C.build(project, _ref(seconds=4.0, strength=0.5), lambda m: None)       # damping: no new clip
    C.build(project, _ref(seconds=4.0, feather=40, grow=14), lambda m: None)    # the mask's shape: the clip is kept
    assert calls["animate"] == 1
    pp = C.build(project, _ref(seconds=4.0, loop="pingpong"), lambda m: None)   # a pingpong asks the model for half the loop
    assert calls["animate"] == 2 and calls["last"]["seconds"] == 2.0 and pp["id"] != first["id"]
    C.build(project, _ref(seconds=4.0), lambda m: None)                     # going back finds the first clip again
    assert calls["animate"] == 2


def test_only_cached_never_runs_a_model(fake):
    project, calls = fake
    assert C.build(project, _ref(seconds=1.0), lambda m: None, only_cached=True) is None
    assert calls["animate"] == 0
    C.build(project, _ref(seconds=1.0), lambda m: None)
    assert C.build(project, _ref(seconds=1.0), lambda m: None, only_cached=True) is not None


def test_pingpong_has_no_seam_and_is_twice_as_long(fake):
    project, calls = fake
    b = C.build(project, _ref(seconds=4.0, loop="pingpong"), lambda m: None)
    assert calls["last"]["seconds"] == 2.0 and calls["last"]["end"] is False   # half the loop, one way, no end frame
    m = b["data"]["motion"]
    assert b["data"]["loop"]["seamless"] and b["data"]["frames"] == 2 * m["played_frames"] - 2
    assert m["kept_frames"] <= m["played_frames"] <= 2 * m["kept_frames"]      # maybe cut short, then played slower to fill the loop


# ---------------------------------------------------------------- the page

def test_the_page_marks_the_still_wherever_it_is_shown(tmp_path, monkeypatch):
    from engine.compile.compiler import build_site
    root = tmp_path / "site"
    (root / "inputs").mkdir(parents=True)
    Image.fromarray(np.full((200, 300, 3), 120, np.uint8)).save(root / "inputs" / "a.png")
    (root / "site.yaml").write_text(textwrap.dedent('''\
        name: Cine
        theme: {preset: night}
        sections:
          - type: hero
            title: Steam
            image: {file: inputs/a.png, cinemagraph: {moves: the steam}}
          - type: intro
            title: Calm
            backdrop: {file: inputs/a.png, cinemagraph: {moves: the steam}}
          - type: gallery
            items: [{title: One, href: "#", image: {file: inputs/a.png}}]
        '''), encoding="utf-8")
    built = tmp_path / "fake"
    built.mkdir()
    (built / "v.mp4").write_bytes(b"v")
    (built / "m.webp").write_bytes(b"m")
    monkeypatch.setattr(C, "build", lambda project, ref, log, **kw: C.Built(
        video=built / "v.mp4", mask=built / "m.webp", box=[0.2, 0.1, 0.6, 0.7], still=[300, 200], id="x",
        data={"moves": "the steam", "seconds": 4, "model": "ltx", "bytes": 10, "mask": {"share_of_still": 0.1},
              "held": {"max_change_outside_mask": 0}, "loop": {"mode": "seamless", "closed_by": "as generated", "seamless": True,
                                                              "encoded": {"ratio": 1.0}}}))
    out = build_site(Project(root), log=lambda m: None)
    html = out.read_text(encoding="utf-8")
    tagged = html.count("data-cine=")
    assert tagged == 2                                      # the hero's <img> and the backdrop; the plain gallery tile is not marked
    assert (root / "dist" / "assets" / "_media" / "v.mp4").exists() and (root / "dist" / "assets" / "_media" / "m.webp").exists()
    import html as htmllib, re
    entry = json.loads(htmllib.unescape(re.search(r'data-cine="([^"]+)"', html).group(1)))
    assert entry["v"] == "assets/_media/v.mp4" and entry["b"] == [0.2, 0.1, 0.4, 0.6] and entry["r"] == 1.5
    assert html.count("<img") >= 2 and "ss-hero__media" in html            # the still is still the page


def test_wiring_leaves_other_markup_alone():
    from engine.compile.compiler import wire_cinemagraphs
    h = '<img src="assets/_media/zzz.webp" alt=""><p style="background-image: url(assets/_media/zzz2.webp)"></p>'
    assert wire_cinemagraphs(h, {"assets/_media/abc.webp": {"v": "a"}}) == h
