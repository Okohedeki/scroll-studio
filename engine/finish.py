"""finish: the finishing pass over a finished film (`finish:` on a film section).

A generated film comes out of the video model soft (LTX-2.3 runs near 1024x576 under a camera guide), with a little
grain that shimmers from frame to frame and, now and then, a brightness flicker. The finishing pass is three cached
stages over the film file, in the section's work folder:

    gen/finish/restore.mp4   SeedVR2 (7B sharp) at `restore` height: one diffusion step over batches of `batch` frames
                             that redraws fine detail and cleans grain, temporally consistent inside a batch (larger
                             batches shimmer less); chunked and cross-faded like every SeedVR2 pass (film_build.stage_upscale)
    gen/finish/clean.mp4     FFmpeg: deflicker (brightness evened over 5 frames), atadenoise (adaptive temporal averaging:
                             a pixel is averaged with its neighbours in time only while it stays within a threshold of
                             them, so shimmer goes and motion stays) and an optional unsharp mask
    gen/finish/smooth.mp4    frame interpolation to twice the frame rate: ComfyUI's FrameInterpolate (a RIFE or FILM
                             checkpoint in models/frame_interpolation) when one is installed, else FFmpeg minterpolate
                             (motion compensated); `auto` only when the film's motion is slow

`studio inspect` measures the result (softness, pops and flicker, morphs): docs/scenes.md has before/after numbers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

VERSION = 1


# ---------------------------------------------------------------- the FFmpeg clean-up

def clean_filter(fin) -> Optional[str]:
    """The FFmpeg filter chain of the clean-up stage (None when it has nothing to do)."""
    parts = []
    if fin.deflicker:
        parts.append("deflicker=size=5:mode=pm")
    if fin.denoise > 0:
        k = float(fin.denoise)
        # thresholds of atadenoise on 0-1 values: a: how far a pixel may differ from a neighbour in time and still be
        # averaged with it (shimmer is a few levels; motion is many), b: the summed limit; s: frames averaged
        a = round(0.006 + 0.03 * k, 4)
        b = round(0.02 + 0.08 * k, 4)
        s = 2 * int(round(2 + 4 * k)) + 1
        parts.append(f"atadenoise=0a={a}:0b={b}:1a={a}:1b={b}:2a={a}:2b={b}:s={s}")
    if fin.sharpen > 0:
        parts.append(f"unsharp=5:5:{round(1.2 * float(fin.sharpen), 3)}:5:5:0")
    return ",".join(parts) or None


def minterpolate_filter(fps: float, factor: int = 2) -> str:
    """FFmpeg's motion-compensated interpolation to `factor` times the frame rate (no model needed)."""
    return (f"minterpolate=fps={fps * factor:g}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:me=epzs:vsbmc=1:scd=fdiff:"
            "scd_threshold=8")


# ---------------------------------------------------------------- ComfyUI graphs

def restore_settings(fin, fps: float, duration: float) -> dict:
    """The SeedVR2 settings of the restore stage (film_build.stage_upscale's `shot["upscale"]`)."""
    chunk = 2 * fin.batch - 1 if fin.batch <= 25 else fin.batch      # whole batches per chunk (with SeedVR2's overlap)
    return {"method": "seedvr2", "resolution": int(fin.restore), "batch_size": int(fin.batch), "chunk": int(chunk),
            "overlap": 8, "temporal_overlap": 4, "color_correction": "lab"}


def interpolate_graph(video: str, model: str, multiplier: int = 2, prefix: str = "studio/finish_interp") -> dict:
    """ComfyUI graph: a video's frames through a frame interpolation model (ComfyUI's own FrameInterpolate: RIFE or
    FILM), `multiplier` times as many frames out."""
    return {
        "vid": {"class_type": "LoadVideo", "inputs": {"file": video}},
        "comp": {"class_type": "GetVideoComponents", "inputs": {"video": ["vid", 0]}},
        "model": {"class_type": "FrameInterpolationModelLoader", "inputs": {"model_name": model}},
        "interp": {"class_type": "FrameInterpolate", "inputs": {"interp_model": ["model", 0], "images": ["comp", 0],
                                                                "multiplier": int(multiplier)}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["interp", 0], "filename_prefix": prefix}},
    }


def interpolator(fin) -> tuple[str, Optional[str]]:
    """('comfy', checkpoint) when ComfyUI has a frame interpolation model (the named one, or the first it lists), else
    ('ffmpeg', None). A named checkpoint ComfyUI cannot see is an error that says where it goes."""
    from .backends import comfy
    from .project import BuildError
    have = comfy.listed("frame_interpolation") or []
    if fin.interpolator:
        if have and fin.interpolator not in have:
            raise BuildError(f"finish.interpolator: ComfyUI can't see frame_interpolation/{fin.interpolator} (it lists "
                             f"{', '.join(have) or 'none'}): put the RIFE or FILM checkpoint in <ComfyUI>/models/"
                             "frame_interpolation/ and restart ComfyUI, or leave `interpolator` out for FFmpeg's")
        return "comfy", fin.interpolator
    return ("comfy", sorted(have)[0]) if have else ("ffmpeg", None)


# ---------------------------------------------------------------- motion: is it slow?

def motion_px(path: Path, samples: int = 24, width: int = 384) -> float:
    """The film's median motion in pixels a frame at 1920 wide: dense optical flow between `samples` pairs of
    consecutive frames spread over the film, the mean magnitude of each, the median of those."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    mags = []
    for k in range(samples):
        i = int(k * max(n - 2, 0) / max(samples - 1, 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok_a, a = cap.read()
        ok_b, b = cap.read()
        if not (ok_a and ok_b):
            continue
        h = max(16, round(a.shape[0] * width / a.shape[1]))
        ga = cv2.cvtColor(cv2.resize(a, (width, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(cv2.resize(b, (width, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        fl = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mags.append(float(np.hypot(fl[..., 0], fl[..., 1]).mean()) * 1920.0 / width)
    cap.release()
    return float(np.median(mags)) if mags else 0.0


def wants_interpolation(fin, motion: Optional[float]) -> bool:
    if fin.interpolate == "on":
        return True
    if fin.interpolate == "off":
        return False
    return motion is not None and motion <= fin.slow


# ---------------------------------------------------------------- the stages

def stage_names(fin) -> list[str]:
    """The stages a film's `finish` runs (what `studio build --plan` lists)."""
    out = []
    if fin.restore:
        out.append("finish_restore")
    if clean_filter(fin):
        out.append("finish_clean")
    if fin.interpolate != "off":
        out.append("finish_interpolate")
    return out


def run(sec, ctx, src: Path) -> Path:
    """The finished film: `src` through the section's `finish` stages (each cached). Returns the last stage's file."""
    import shutil
    from .project import ffmpeg, file_key, probe
    from .scenes import film_build as fb
    fin = sec.finish
    fdir = ctx.work / "gen" / "finish"
    info = probe(src)
    num, _, den = str(info.get("r_frame_rate") or "24/1").partition("/")
    fps = float(num) / float(den or 1)
    duration = float(info.get("duration") or 0)
    cur = src
    if fin.restore:
        out = fdir / "restore.mp4"
        ucfg = restore_settings(fin, fps, duration)

        def restore(cur=cur, out=out, ucfg=ucfg):
            from .scenes.film import _restore_args
            rdir = fdir / "restore"
            rdir.mkdir(parents=True, exist_ok=True)
            shot = {"id": f"finish-{sec.id}", "fps": fps, "duration": duration, "ltx": {}, "upscale": ucfg}
            fb.stage_upscale(shot, str(rdir), _restore_args(ctx, cur))
            shutil.copy(rdir / "gen" / "gen_sr.mp4", out)
        ctx.stage("finish_restore", {"src": file_key(cur), "seedvr2": ucfg, "v": VERSION}, [out], restore)
        cur = out
    chain = clean_filter(fin)
    if chain:
        out = fdir / "clean.mp4"

        def clean(cur=cur, out=out, chain=chain):
            out.parent.mkdir(parents=True, exist_ok=True)
            ffmpeg("-i", cur, "-vf", chain, "-c:v", "libx264", "-crf", "12", "-preset", "slow", "-pix_fmt", "yuv420p", out,
                   log=ctx.log)
        ctx.stage("finish_clean", {"src": file_key(cur), "filter": chain, "v": VERSION}, [out], clean)
        cur = out
    if fin.interpolate != "off":
        motion = motion_px(cur) if fin.interpolate == "auto" else None
        if not wants_interpolation(fin, motion):
            ctx.log(f"  finish_interpolate: skipped, the film moves {motion:.1f} px a frame (slow is {fin.slow:g} or less); "
                    "interpolating fast motion morphs it")
            return cur
        kind, model = interpolator(fin)
        out = fdir / "smooth.mp4"

        def smooth(cur=cur, out=out, kind=kind, model=model):
            out.parent.mkdir(parents=True, exist_ok=True)
            if kind == "ffmpeg":
                ffmpeg("-i", cur, "-vf", minterpolate_filter(fps), "-c:v", "libx264", "-crf", "12", "-preset", "slow",
                       "-pix_fmt", "yuv420p", out, log=ctx.log)
                return
            from .backends import comfy
            frames = fdir / "smooth_frames"
            if frames.exists():
                shutil.rmtree(frames)
            comfy.free()
            images = comfy.run(interpolate_graph(comfy.upload(str(cur)), model, 2, f"studio/finish_{sec.id}"), poll=3)
            comfy.fetch(images, str(frames))
            comfy.free()
            ffmpeg("-framerate", f"{fps * 2:g}", "-i", frames / "%04d.png", "-c:v", "libx264", "-crf", "12", "-preset",
                   "slow", "-pix_fmt", "yuv420p", out, log=ctx.log)
            shutil.rmtree(frames, ignore_errors=True)
        ctx.log(f"  finish_interpolate: {kind}{f' ({model})' if model else ''}"
                + (f", the film moves {motion:.1f} px a frame" if motion is not None else ""))
        ctx.stage("finish_interpolate", {"src": file_key(cur), "with": [kind, model], "x": 2, "v": VERSION}, [out], smooth)
        cur = out
    return cur
