"""Animate a still with a local video model (ComfyUI): the shared step behind theme.art and film beats.

Two models: LTX-2.3 (`video_model: ltx`, the default) and Wan 2.2 A14B (`video_model: wan`). Wan renders at its native ~1280x720 and 16 fps in clips of up to 81 frames
(chained from each clip's last frame for longer shots); the frames are then retimed to the engine's 24 fps with
FFmpeg's motion-compensated interpolation and scaled to the requested size.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from .project import BuildError

FPS = 24
NEGATIVE = ("cuts, camera shake, flicker, morphing, warped body, extra limbs, new objects appearing, neon tubes, light "
            "rings, text, watermark, blur")
VIDEO_MODELS = ("ltx", "wan")


def video_model(*choices: Optional[str]) -> str:
    """The first model chosen, most specific first (beat/take/art, then the site), else studio.toml, else ltx."""
    from .config import settings
    for c in (*choices, settings().get("video_model"), "ltx"):
        if c:
            if c not in VIDEO_MODELS:
                raise BuildError(f"video_model '{c}': use one of {', '.join(VIDEO_MODELS)}")
            return c
    return "ltx"


def wan_settings(*layers: Optional[dict]) -> dict:
    """Wan settings merged from general to specific (site.wan, then a take's or beat's own); None values skipped."""
    out: dict = {}
    for layer in layers:
        out.update({k: v for k, v in (layer or {}).items() if v is not None})
    return out


def ltx_size(w: int, h: int, mp: float = 0.44) -> tuple[int, int]:
    """About `mp` megapixels at the image's aspect, both sides multiples of 32 (what LTX-2.3 wants)."""
    scale = (mp * 1_000_000 / (w * h)) ** 0.5
    return max(256, round(w * scale / 32) * 32), max(256, round(h * scale / 32) * 32)


def wan_size(w: int, h: int, res: Optional[tuple[int, int]] = None) -> tuple[int, int]:
    """Wan's render size: `res` if given, else 1280x720's pixel count at the image's aspect; multiples of 16."""
    if res:
        return int(res[0]) // 16 * 16, int(res[1]) // 16 * 16
    scale = (1280 * 720 / (w * h)) ** 0.5
    return max(256, round(w * scale / 16) * 16), max(256, round(h * scale / 16) * 16)


def frames_for(seconds: float) -> int:
    return max(9, round(seconds * FPS / 8) * 8 + 1)


def wan_frames(seconds: float, fps: int = 16) -> int:
    """Wan wants 4k+1 frames."""
    return max(5, round(seconds * fps / 4) * 4 + 1)


def wan_split(frames: int, max_frames: int = 81) -> list[int]:
    """Split a 4k+1 frame count into chained clips of at most `max_frames`, as even as possible. Each clip after the
    first starts on the previous clip's last frame, so the lengths (each 4k+1) overlap by one frame."""
    gaps = (frames - 1) // 4
    k = max(1, -(-gaps // ((max_frames - 1) // 4)))
    q, r = divmod(gaps, k)
    return [(q + (1 if i < r else 0)) * 4 + 1 for i in range(k)]


def retime(src_dir: Path, dst_dir: Path, src_fps: float, dst_fps: int, size: Optional[tuple[int, int]] = None,
           mode: str = "mci", log: Callable[[str], None] = print) -> list[Path]:
    """PNG frames at src_fps -> PNG frames at dst_fps (and `size`). mode: mci (FFmpeg minterpolate, motion-compensated:
    in-between frames are synthesised along motion vectors), blend (cross-fades, softer but never tears) or dup
    (repeats frames: exact pixels, slight judder)."""
    import shutil
    from .project import ffmpeg
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True)
    vf = ["tpad=stop_mode=clone:stop=2"]   # minterpolate drops the last in-betweens without a frame to aim at
    if abs(src_fps - dst_fps) > 1e-3:
        vf.append({"mci": f"minterpolate=fps={dst_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
                   "blend": f"minterpolate=fps={dst_fps}:mi_mode=blend",
                   "dup": f"fps={dst_fps}"}[mode])
    if size:
        vf.append(f"scale={size[0]}:{size[1]}:flags=lanczos")
    src = sorted(src_dir.glob("*.png"))
    n_out = round((len(src) - 1) * dst_fps / src_fps) + 1   # first and last frame land on source frames
    ffmpeg("-framerate", f"{src_fps:.4f}".rstrip("0").rstrip("."), "-start_number", "1", "-i", src_dir / "%04d.png",
           "-vf", ",".join(vf), "-frames:v", str(n_out), "-start_number", "1", dst_dir / "%04d.png", log=log)
    return sorted(dst_dir.glob("*.png"))


def clip_frames(clip: Path, dst_dir: Path, seconds: float, size: tuple[int, int],
                log: Callable[[str], None] = print) -> list[Path]:
    """A provider's MP4 -> PNG frames at 24 fps and `size` (scaled to cover, centre-cropped), stretched or squeezed to
    `seconds`: providers render whole seconds in their own lengths, and the scroll timeline wants the asked one."""
    import shutil
    from .project import ffmpeg, probe
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True)
    try:
        made = float(probe(clip).get("duration") or seconds)
    except (ValueError, TypeError):
        made = seconds
    w, h = size
    vf = (f"setpts={seconds / made:.5f}*PTS,fps={FPS},scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={w}:{h},tpad=stop_mode=clone:stop=1")      # one frame past the end: the last frame lands on `seconds`
    ffmpeg("-i", clip, "-vf", vf, "-frames:v", str(round(seconds * FPS) + 1), "-start_number", "1",
           dst_dir / "%04d.png", log=log)
    frames = sorted(dst_dir.glob("*.png"))
    log(f"  provider clip: {made:.1f}s -> {len(frames)} frames at {FPS} fps, {w}x{h}")
    return frames


def animate(still: Path, prompt: str, motion: str, seconds: float, seed: int, work: Path,
            log: Callable[[str], None] = print, size: Optional[tuple[int, int]] = None,
            negative: str = NEGATIVE, strength: float = 1.0, end_image: Optional[Path] = None,
            model: str = "ltx", wan: Optional[dict] = None, timeout: int = 45 * 60,
            end_strength: float = 1.0) -> list[Path]:
    """Frames (PNG paths, in order, 24 fps) of `still` brought to life by `motion`. `end_strength` (ltx): how firmly the last
    frame is held to `end_image` (1 pins it; a cinemagraph loop that must keep moving holds it more loosely)."""
    from PIL import Image
    from .router import video_on_provider
    out_size = size or Image.open(still).size
    clip = work / "provider.mp4"
    text = f"{prompt or 'The subject of the image'}. {motion}. Smooth natural motion."
    if video_on_provider(still, text, seconds, seed, clip, tuple(out_size), end_image, log=log):
        return clip_frames(clip, work / "frames", seconds, tuple(out_size), log)
    from .backends import comfy
    name = "Wan 2.2" if model == "wan" else "LTX-2.3"
    if not comfy.alive():
        raise BuildError(f"Animating needs ComfyUI with {name} running at {comfy.COMFY}. Start it (docs/INSTALL.md).")
    if model == "wan":
        return _animate_wan(still, prompt, motion, seconds, seed, work, log, size, negative, end_image, wan or {})
    from PIL import Image
    w, h = (size[0] // 32 * 32, size[1] // 32 * 32) if size else ltx_size(*Image.open(still).size)
    n = frames_for(seconds)
    log(f"  animating with LTX-2.3 ({w}x{h}, {n} frames): {motion[:80]}")
    comfy.free()
    name = comfy.upload(str(still))
    end_name = comfy.upload(str(end_image)) if end_image else None
    text = f"{prompt or 'The subject of the image'}. {motion}. Smooth natural motion."
    graph = comfy.build_i2v_graph(comfy.LTX, name, n, w, h, FPS, text, negative, seed, prefix=f"studio/anim_{work.name}",
                                  strength=strength, end_image=end_name, end_strength=end_strength)
    images = comfy.run(graph, poll=3, timeout=timeout)   # a storyboard preview gives up sooner than a render
    import shutil
    if (work / "frames").exists():
        shutil.rmtree(work / "frames")
    tmp = Path(comfy.fetch(images, str(work / "frames")))
    comfy.free()
    return sorted(tmp.glob("*.png"))


def _animate_wan(still: Path, prompt: str, motion: str, seconds: float, seed: int, work: Path,
                 log: Callable[[str], None], size: Optional[tuple[int, int]], negative: str,
                 end_image: Optional[Path], wan: dict) -> list[Path]:
    """Wan 2.2 image-to-video: chained clips of <= 81 frames at 16 fps (the last one lands on `end_image`, through
    WanFirstLastFrameToVideo), joined, then retimed to 24 fps at `size`."""
    import shutil
    from PIL import Image
    from .backends import comfy
    src_w, src_h = Image.open(still).size
    out_size = size or (src_w, src_h)
    w, h = wan_size(*out_size, wan.get("res"))
    total = wan_frames(seconds, comfy.WAN_FPS)
    max_f = int(wan.get("max_frames", comfy.WAN_MAX_FRAMES))
    play_fps = comfy.WAN_FPS
    if max_f < total and seconds <= (max_f - 1) / comfy.WAN_FPS * float(wan.get("stretch", 1.35)):
        # A little over one clip: one clip played a bit slower beats two clips joined. A chained clip restarts the
        # motion from a still frame and only the last clip sees the end image (a door opened, shut and re-opened).
        total, play_fps = max_f, (max_f - 1) / seconds
    clips = wan_split(total, max_f)
    q = wan.get("quality", "fast")
    log(f"  animating with Wan 2.2 ({q}, {w}x{h}, {total} frames at {comfy.WAN_FPS} fps in {len(clips)} clip(s)): {motion[:80]}")
    text = f"{prompt or 'The subject of the image'}. {motion}. Smooth natural motion."
    neg = wan.get("negative_prompt") or negative
    raw = work / "frames16"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    comfy.free()

    def fit(src: Path, dst: Path) -> str:
        from PIL import ImageOps
        ImageOps.fit(Image.open(src).convert("RGB"), (w, h), Image.LANCZOS).save(dst)
        return comfy.upload(str(dst))

    start = fit(still, work / f"wan_start_{w}x{h}.png")
    end_name = fit(end_image, work / f"wan_end_{w}x{h}.png") if end_image else None
    n = 0
    for i, frames in enumerate(clips):
        last = i == len(clips) - 1
        t0 = time.time()
        graph = comfy.build_wan_graph(wan, text, neg, w, h, frames, seed + i, prefix=f"studio/wan_{work.name}_{i}",
                                      start_image=start, end_image=end_name if last else None)
        images = comfy.run(graph, poll=3)
        cdir = Path(comfy.fetch(images, str(work / f"_wan{i}")))
        pngs = sorted(cdir.glob("*.png"))
        for p in pngs[1 if i else 0:]:     # a chained clip starts on the previous clip's last frame
            n += 1
            shutil.move(str(p), raw / f"{n:04d}.png")
        log(f"  wan clip {i + 1}/{len(clips)}: {frames} frames in {time.time() - t0:.0f}s")
        if not last:
            start = fit(raw / f"{n:04d}.png", work / f"wan_chain{i}_{w}x{h}.png")
        shutil.rmtree(cdir, ignore_errors=True)
    comfy.free()
    mode = wan.get("interpolate", "mci")
    log(f"  retiming {n} frames {play_fps:.2f} -> {FPS} fps ({mode}) at {out_size[0]}x{out_size[1]}")
    return retime(raw, work / "frames", play_fps, FPS, tuple(out_size), mode, log)
