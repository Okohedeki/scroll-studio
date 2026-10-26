"""The finishing pass over a film (`finish:`, engine/finish.py): the spec, the FFmpeg clean-up chain, the ComfyUI graphs
(SeedVR2 restore settings, frame interpolation), the interpolator choice, the slow-motion test, the plan and the cache.
No ComfyUI and no GPU: ComfyUI's model lists are stubbed; FFmpeg runs where it is installed."""
from __future__ import annotations

import shutil

import numpy as np
import pytest
from pydantic import ValidationError

from engine import finish
from engine.spec import FilmScene, Finish

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")

BEATS = [{"id": "a", "prompt": "p", "motion": "m", "seconds": 3}]


def film(**kw) -> FilmScene:
    return FilmScene.model_validate({"id": "s", "beats": BEATS, **kw})


# ---------------------------------------------------------------- spec

def test_finish_true_takes_the_defaults_and_old_films_have_none():
    assert film().finish is None
    f = film(finish=True).finish
    assert f == Finish() and f.restore == 1088 and f.deflicker and f.denoise > 0 and f.interpolate == "off"
    assert film(finish=False).finish is None
    assert "finish" not in film().model_dump(mode="json", exclude_defaults=True)


def test_finish_settings_validate():
    assert Finish(restore=None).restore is None
    with pytest.raises(ValidationError, match="4n\\+1"):
        Finish(batch=20)
    with pytest.raises(ValidationError):
        Finish(restore=4000)
    with pytest.raises(ValidationError):
        Finish(interpolate="sometimes")


# ---------------------------------------------------------------- the FFmpeg chain

def test_clean_filter_follows_the_settings():
    chain = finish.clean_filter(Finish())
    assert chain.startswith("deflicker=size=5") and "atadenoise=" in chain and "unsharp" not in chain
    assert finish.clean_filter(Finish(deflicker=False, denoise=0)) is None
    strong, light = finish.clean_filter(Finish(denoise=1, deflicker=False)), finish.clean_filter(Finish(denoise=0.1, deflicker=False))
    a = lambda c: float(c.split("0a=")[1].split(":")[0])
    assert a(strong) > a(light)                                   # stronger: a wider threshold
    assert "unsharp=5:5:0.36" in finish.clean_filter(Finish(sharpen=0.3))


@needs_ffmpeg
def test_ffmpeg_accepts_every_chain(tmp_path):
    from engine.project import ffmpeg
    for f in (Finish(), Finish(denoise=1, sharpen=1), Finish(deflicker=False, denoise=0.05)):
        ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=0.5", "-vf", finish.clean_filter(f),
               tmp_path / "o.mp4")
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=0.5", "-vf", finish.minterpolate_filter(24),
           tmp_path / "i.mp4")
    from engine.project import probe
    assert probe(tmp_path / "i.mp4")["r_frame_rate"] == "48/1"


# ---------------------------------------------------------------- ComfyUI graphs

def test_restore_settings_make_a_seedvr2_graph_with_bigger_batches():
    from engine.backends import comfy
    ucfg = finish.restore_settings(Finish(batch=21), 24, 4.0)
    assert ucfg["method"] == "seedvr2" and ucfg["resolution"] == 1088 and ucfg["batch_size"] == 21
    assert ucfg["chunk"] % 21 != 0 or ucfg["chunk"] >= 21
    g = comfy.build_seedvr2_graph(ucfg, "clip.mp4", "p")
    up = g["up"]["inputs"]
    assert g["up"]["class_type"] == "SeedVR2VideoUpscaler" and up["batch_size"] == 21 and up["resolution"] == 1088
    assert up["temporal_overlap"] == 4 and up["color_correction"] == "lab" and up["image"] == ["comp", 0]
    assert g["vid"]["inputs"]["file"] == "clip.mp4" and g["save"]["inputs"]["images"] == ["up", 0]


def test_interpolate_graph_shape():
    g = finish.interpolate_graph("film.mp4", "rife49.safetensors", 2, "pre")
    assert [g[k]["class_type"] for k in ("vid", "comp", "model", "interp", "save")] == [
        "LoadVideo", "GetVideoComponents", "FrameInterpolationModelLoader", "FrameInterpolate", "SaveImage"]
    assert g["interp"]["inputs"] == {"interp_model": ["model", 0], "images": ["comp", 0], "multiplier": 2}
    assert g["model"]["inputs"]["model_name"] == "rife49.safetensors" and g["save"]["inputs"]["images"] == ["interp", 0]


def test_the_interpolator_is_comfys_model_when_there_is_one(monkeypatch):
    from engine.backends import comfy
    from engine.project import BuildError
    monkeypatch.setattr(comfy, "listed", lambda folder: [])
    assert finish.interpolator(Finish()) == ("ffmpeg", None)
    monkeypatch.setattr(comfy, "listed", lambda folder: ["rife49.safetensors", "film_net_fp16.safetensors"])
    assert finish.interpolator(Finish()) == ("comfy", "film_net_fp16.safetensors")
    assert finish.interpolator(Finish(interpolator="rife49.safetensors")) == ("comfy", "rife49.safetensors")
    with pytest.raises(BuildError, match="models/\\s*frame_interpolation|frame_interpolation/"):
        finish.interpolator(Finish(interpolator="nope.pth"))


def test_auto_interpolates_only_slow_motion():
    assert finish.wants_interpolation(Finish(interpolate="on"), 50.0)
    assert not finish.wants_interpolation(Finish(interpolate="off"), 0.1)
    assert finish.wants_interpolation(Finish(interpolate="auto", slow=6), 3.0)
    assert not finish.wants_interpolation(Finish(interpolate="auto", slow=6), 9.0)


def _moving(path, dx: int, n=12, w=320, h=180):
    import cv2
    rng = np.random.default_rng(2)
    base = cv2.GaussianBlur(rng.integers(0, 255, (h, w * 3, 3), dtype=np.uint8), (0, 0), 2.0)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24, (w, h))
    for i in range(n):
        out.write(np.ascontiguousarray(base[:, i * dx:i * dx + w]))
    out.release()


def test_motion_is_measured_in_pixels_at_1920(tmp_path):
    _moving(tmp_path / "slow.mp4", 1)
    _moving(tmp_path / "fast.mp4", 6)
    slow, fast = finish.motion_px(tmp_path / "slow.mp4", 6), finish.motion_px(tmp_path / "fast.mp4", 6)
    assert 3 < slow < 9 and 25 < fast < 45                        # 1 and 6 px at 320 wide are 6 and 36 at 1920
    assert finish.motion_px(tmp_path / "missing.mp4") == 0.0


# ---------------------------------------------------------------- plan and cache

def test_the_plan_lists_the_finish_before_the_encode():
    from engine import plan
    names = plan.expected(film(finish={"interpolate": "auto", "sharpen": 0.2}))
    i = names.index("encode")
    assert names[i - 3:i] == ["finish_restore", "finish_clean", "finish_interpolate"]
    assert "finish_restore" not in plan.expected(film())
    assert plan.expected(film(finish={"restore": None, "deflicker": False, "denoise": 0})).count("finish_clean") == 0
    sec = film(finish={"restore": 2160})
    kind, units = plan.units(sec, "finish_restore")
    assert kind == "film:finish_restore" and units == pytest.approx(3 * (2160 / 1088) ** 2, rel=0.01)   # 2x the height: 4x the work
    assert plan.units(sec, "finish_clean") == ("film:finish_clean", 3.0)


@needs_ffmpeg
def test_the_clean_stage_is_cached_by_the_film_and_its_settings(tmp_path):
    from engine.project import BuildContext, Project, ffmpeg, probe
    proj = Project(tmp_path / "p")
    (tmp_path / "p").mkdir()
    src = tmp_path / "film.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=0.5", "-pix_fmt", "yuv420p", src)
    logs: list[str] = []
    ctx = BuildContext(proj, "s", log=logs.append)
    sec = film(finish={"restore": None})
    out = finish.run(sec, ctx, src)
    assert out.name == "clean.mp4" and probe(out)["width"] == 160
    assert any("finish_clean: running" in m for m in logs)
    logs.clear()
    assert finish.run(sec, ctx, src) == out and any("finish_clean: up to date" in m for m in logs)
    logs.clear()
    finish.run(film(finish={"restore": None, "denoise": 0.6}), ctx, src)
    assert any("finish_clean: running" in m for m in logs)
    logs.clear()
    auto = film(finish={"restore": None, "interpolate": "auto", "slow": 0.0001})
    assert finish.run(auto, ctx, src).name == "clean.mp4"                 # testsrc moves: not slow, so not interpolated
    assert any("skipped" in m for m in logs)


def test_doctor_notes_the_interpolator(monkeypatch):
    from engine import doctor
    from engine.backends import comfy
    monkeypatch.setattr(comfy, "listed", lambda folder: [])
    row = doctor.interpolation_checks()[0]
    assert row["ok"] and "minterpolate" in row["detail"]
    monkeypatch.setattr(comfy, "listed", lambda folder: ["rife49.safetensors"])
    assert doctor.interpolation_checks()[0]["detail"] == "frame_interpolation/rife49.safetensors"
    monkeypatch.setattr(comfy, "listed", lambda folder: None)
    assert not doctor.interpolation_checks()[0]["ok"]


@needs_ffmpeg
def test_auto_never_falls_back_to_minterpolate(tmp_path, monkeypatch):
    from engine.backends import comfy
    from engine.project import BuildContext, Project, ffmpeg
    monkeypatch.setattr(comfy, "listed", lambda folder: [])
    monkeypatch.setattr(finish, "motion_px", lambda p, *a, **k: 0.5)      # slow
    (tmp_path / "p").mkdir()
    src = tmp_path / "film.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=0.5", "-pix_fmt", "yuv420p", src)
    logs: list[str] = []
    ctx = BuildContext(Project(tmp_path / "p"), "s", log=logs.append)
    out = finish.run(film(finish={"restore": None, "deflicker": False, "denoise": 0, "interpolate": "auto"}), ctx, src)
    assert out == src and any("no RIFE or FILM" in m for m in logs)
    out = finish.run(film(finish={"restore": None, "deflicker": False, "denoise": 0, "interpolate": "on"}), ctx, src)
    from engine.project import probe
    assert out.name == "smooth.mp4" and probe(out)["r_frame_rate"] == "48/1"
