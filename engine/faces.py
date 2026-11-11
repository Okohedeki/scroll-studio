"""faces: repair the faces in generated video (`faces: restore` on a film or a beat). Off by default.

A post stage over a finished clip: faces above `min_size` pixels are found in every frame, restored with GFPGAN v1.4
(Apache-2.0; not CodeFormer, whose licence is non-commercial), blended back through a soft face mask, and the change is
smoothed over time in the face's own aligned space so nothing flickers. It runs in ComfyUI through DesignAI's
`SSFaceRestore` node (engine/backends/comfy_nodes/), in chunks of frames that overlap by a few frames so the smoothing has
warmed up where each chunk starts. The result is a new clip with the same frame count and rate, cached by the source clip and
the settings; the film (or the beat's join) then carries on from it.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .project import BuildContext, BuildError, ffmpeg, file_key, probe
from .spec import Faces, FilmScene

CHUNK = 96        # frames per ComfyUI run (a frame batch is held as floats: ~25 MB each at 1920x1088)
OVERLAP = 6       # frames a chunk repeats from the one before it, so the smoothing has settled where it starts
VERSION = 1
NODES = ("SSFaceRestore",)


def preflight(ctx: BuildContext) -> None:
    from .backends import comfy
    from .fidelity import is_planning
    if is_planning() or not comfy.alive():
        return
    for n in NODES:
        try:
            comfy._req(f"/object_info/{n}")
        except Exception:
            raise BuildError("faces: restore needs DesignAI's ComfyUI nodes, which ComfyUI can't see. Run `studio setup-comfy`, "
                             "restart ComfyUI when its queue is empty, then build again (`studio doctor` checks it).")


def graph(video_name: str, f: Faces, prefix: str) -> dict:
    return {
        "vid": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "comp": {"class_type": "GetVideoComponents", "inputs": {"video": ["vid", 0]}},
        "fr": {"class_type": "SSFaceRestore", "inputs": {"images": ["comp", 0], "model_name": "GFPGANv1.4.pth",
                                                          "strength": f.strength, "min_face": f.min_size, "smooth": f.smooth}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["fr", 0], "filename_prefix": prefix}},
    }


def restore_clip(src: Path, dst: Path, f: Faces, work: Path, label: str, log=print) -> None:
    """Every frame of src with its faces repaired, as dst (H.264, same frame rate and count)."""
    from .backends import comfy
    from .reveal import _count_frames, _fps
    n, fps = _count_frames(src), _fps(probe(src, "stream=r_frame_rate").get("r_frame_rate"))
    frames = work / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    starts = list(range(0, n, CHUNK - OVERLAP)) if n > CHUNK else [0]
    done = 0
    for k, a in enumerate(starts):
        b = min(n, a + CHUNK)
        part = work / f"chunk{k}.mp4"
        ffmpeg("-i", src, "-vf", f"trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS", "-an", "-c:v", "libx264", "-crf", "8",
               "-preset", "fast", "-pix_fmt", "yuv420p", part)
        images = comfy.run(graph(comfy.upload(str(part)), f, f"studio/faces_{label}"), poll=2)
        got = Path(comfy.fetch(images, str(work / f"png{k}")))
        pngs = sorted(got.glob("*.png"))
        if len(pngs) != b - a:
            raise BuildError(f"faces: {len(pngs)} frames came back for {b - a}")
        skip = 0 if k == 0 else OVERLAP
        for i, p in enumerate(pngs[skip:], start=a + skip):
            shutil.move(str(p), frames / f"{i:05d}.png")
        shutil.rmtree(got, ignore_errors=True)
        part.unlink()
        done = b
        log(f"  faces {label}: {done}/{n} frames")
        if b >= n:
            break
    ffmpeg("-framerate", f"{fps:.6f}", "-i", frames / "%05d.png", "-c:v", "libx264", "-crf", "13", "-preset", "slow",
           "-pix_fmt", "yuv420p", dst)
    shutil.rmtree(frames, ignore_errors=True)


def _key(src: Path, f: Faces) -> dict:
    return {"src": file_key(src), "f": f.model_dump(mode="json"), "v": VERSION}


def restore_film(sec: FilmScene, ctx: BuildContext, src: Path) -> Path:
    """Stage `faces`: the whole film with its faces repaired (gen/faces.mp4), before it is encoded."""
    dst = ctx.work / "gen" / "faces.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    work = ctx.work / "faces"
    ctx.stage("faces", _key(src, sec.faces), [dst], lambda: (preflight(ctx), restore_clip(src, dst, sec.faces, work, sec.id, ctx.log)))
    return dst


def restore_beat(ctx: BuildContext, beat_id: str, clip: Path, f: Faces) -> Path:
    """Stage `faces_<beat>`: one beat's clip with its faces repaired (beats/<id>/clip_faces.mp4), before the join."""
    dst = clip.with_name("clip_faces.mp4")
    work = clip.parent / "faces"
    ctx.stage(f"faces_{beat_id}", _key(clip, f), [dst], lambda: (preflight(ctx), restore_clip(clip, dst, f, work, f"{ctx.section_id}_{beat_id}", ctx.log)))
    return dst
