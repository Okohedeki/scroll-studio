"""theme.art: artwork a style renders in its own medium (ascii-art prints it in characters, particles forms it in points).

The image is generated locally from a prompt (Z-Image) or taken from a file; with `motion:` the video model (LTX-2.3 or Wan
2.2, `video_model`) animates it into a short loop. The page gets one grayscale sprite sheet (frames stacked top to
bottom, auto-contrasted) plus the facts the runtime needs; the runtime turns those frames into characters or points at whatever size the screen has.

Cached under .build/_art/<digest>/; only the sheet is copied into the site.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

from .inputs import resolve_image, resolve_path
from .project import BuildError, Project
from .spec import Art, ImageInput

def _animate(still: Path, art: Art, work: Path, log: Callable[[str], None], model: str = "ltx",
             wan: dict | None = None) -> list[Path]:
    from .animate import animate
    from .backends import comfy
    if not comfy.alive():
        raise BuildError("theme.art has `motion:`, which is animated locally with a video model in ComfyUI, but ComfyUI "
                         "is not running. Start it (docs/INSTALL.md) or remove `motion:` for a still.")
    return animate(still, art.prompt or "", f"{art.motion}, the camera stays still", art.seconds, art.seed, work, log,
                   model=model, wan=wan)


def _paths(project: Project, art: Art, log: Callable[[str], None], site_video_model: str | None,
           site_wan: dict | None):
    """(digest, work dir, clip dir, model, wan settings) of a theme.art."""
    from .animate import video_model, wan_settings
    model = video_model(art.video_model, site_video_model) if art.motion else "ltx"
    wan = wan_settings(site_wan) if model == "wan" else None
    dump = art.model_dump(mode="json")
    dump.pop("video_model", None)   # keyed below only when it is not ltx, so art built before it existed stays cached
    if model != "ltx":
        dump["video"] = [model, wan]
    key = json.dumps(dump, sort_keys=True)
    if art.file:
        src = resolve_path(project, art.file, log)
        key += f"{src.stat().st_size}:{int(src.stat().st_mtime)}"
    digest = hashlib.sha1((key + ":7").encode()).hexdigest()[:12]
    work = project.build / "_art" / digest
    # the generated clip depends only on what was asked for, not on how it is shipped (frames, width)
    vkey = json.dumps([art.prompt, art.file, art.motion, art.seconds, list(art.size), art.seed]
                      + ([model, wan] if model != "ltx" else []), sort_keys=True)
    vwork = project.build / "_art" / ("v_" + hashlib.sha1(vkey.encode()).hexdigest()[:12])
    return digest, work, vwork, model, wan


def cached(project: Project, art: Art, site_video_model: str | None = None, site_wan: dict | None = None) -> bool:
    """True when the art's sprite sheet is built (a build would only copy it)."""
    _, work, _, _, _ = _paths(project, art, lambda m: None, site_video_model, site_wan)
    return (work / "sheet.png").exists() and (work / "meta.json").exists()


def build(project: Project, art: Art, dist: Path, log: Callable[[str], None] = print,
          site_video_model: str | None = None, site_wan: dict | None = None) -> dict:
    from PIL import Image
    if not art.prompt and not art.file:
        raise BuildError("theme.art needs a `prompt` (generated locally) or a `file`")
    digest, work, vwork, model, wan = _paths(project, art, log, site_video_model, site_wan)
    sheet = work / "sheet.png"
    meta_file = work / "meta.json"
    if not (sheet.exists() and meta_file.exists()):
        from .fidelity import would_render
        would_render("art", (art.prompt or art.file or "")[:60])
        work.mkdir(parents=True, exist_ok=True)
        still = (resolve_path(project, art.file, log) if art.file
                 else resolve_image(project, ImageInput(generate=art.prompt, size=art.size, seed=art.seed), log))
        if art.motion:
            paths = sorted((vwork / "frames").glob("*.png"))
            if not paths:
                vwork.mkdir(parents=True, exist_ok=True)
                paths = _animate(Path(still), art, vwork, log, model, wan)
            paths = _loop_span(paths)
        else:
            paths = [Path(still)]
        n = min(art.frames, len(paths))
        picks = [paths[round(i * (len(paths) - 1) / max(1, n - 1))] for i in range(n)] if n > 1 else paths[:1]
        frames = []
        for p in picks:
            im = Image.open(p).convert("L")
            fh = max(8, round(art.width * im.height / im.width))
            frames.append(im.resize((art.width, fh), Image.LANCZOS))
        if len(frames) >= 10:
            # a seamless loop: the span already ends close to where it starts; a short crossfade hides the rest
            k = max(2, len(frames) // 10)
            head, tail, middle = frames[:k], frames[-k:], frames[k:-k]
            frames = middle + [Image.blend(tail[j], head[j], (j + 1) / (k + 1)) for j in range(k)]
        fw, fh = frames[0].size
        lut = _tone_curve(frames[0])   # one curve for every frame (from the first), so the loop doesn't pulse
        out = Image.new("L", (fw, fh * len(frames)))
        for i, f in enumerate(frames):
            out.paste(f.point(lut), (0, i * fh))
        out.save(sheet, optimize=True)
        # the curve already maps the background to black; kept for sheets that end up light anyway
        edge = _edge(frames[0].point(lut))
        meta = {"frames": len(frames), "w": fw, "h": fh, "invert": sum(edge) / len(edge) > 128,
                "fps": 12 if len(frames) > 1 else 0}
        meta_file.write_text(json.dumps(meta))
        log(f"  art: {len(frames)} frame(s) at {fw}x{fh}")
    meta = json.loads(meta_file.read_text())
    target = dist / "assets" / "_art"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(sheet, target / f"{digest}.png")
    label = art.label or (art.prompt or Path(art.file or "art").stem)
    return dict(meta, sheet=f"assets/_art/{digest}.png", label=label[:80])


def _edge(im) -> list[int]:
    w, h = im.size
    return [im.getpixel((x, y)) for x in range(w) for y in (0, h - 1)] + \
           [im.getpixel((x, y)) for y in range(h) for x in (0, w - 1)]


def _tone_curve(im) -> list[int]:
    """Background to 0, subject spread over the rest. The background level is read from the frame's border (so a dim
    floor or noise drops out), and a gamma lifts a dark subject (a dark jersey on black) until its middle tone sits
    mid-way, so it prints as a solid figure rather than a few bright highlights. A light background is flipped, so the
    sheet is always subject-bright on black."""
    import math
    from PIL import ImageOps
    edge = sorted(_edge(im))
    light = sum(edge) / len(edge) > 128
    if light:
        im = ImageOps.invert(im)
        edge = sorted(255 - v for v in edge)
    lo, hi = _percentiles(im, 2, 99.5)
    lo = max(lo, min(hi - 32, edge[int(len(edge) * 0.75)] + 6))   # a floor or table along the border drops out; smoke or a limb crossing it stays
    span = max(1, hi - lo)
    subj = sorted((v - lo) / span for v in im.getdata() if v > lo)
    gamma = 1.0
    if len(subj) > 50:
        med = min(0.95, max(0.02, subj[len(subj) // 2]))
        gamma = max(0.45, min(1.0, math.log(0.55) / math.log(med)))
    curve = [0 if v <= lo else round(255 * min(1.0, (v - lo) / span) ** gamma) for v in range(256)]
    return curve[::-1] if light else curve   # indexed by the original (unflipped) value


def _loop_span(paths: list[Path], min_frac: float = 0.55) -> list[Path]:
    """The stretch of the clip whose last frame looks most like its first, so the loop cuts where the motion repeats
    (a dribble at the same height, a step on the same foot) instead of blending two different poses. It must keep most
    of the clip's movement: a still stretch matches itself perfectly but is not the point."""
    import numpy as np
    from PIL import Image
    n = len(paths)
    if n < 16:
        return paths
    th = np.stack([np.asarray(Image.open(p).convert("L").resize((64, 48)), dtype=np.float32) for p in paths])
    span = max(8, int(n * min_frac))
    motion = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(th, axis=0)).mean(axis=(1, 2)))])   # motion up to frame i
    best, ab = None, (0, n - 1)
    for need in (0.75, 0.5, 0.0):
        for a in range(0, n - span):
            ends = np.arange(a + span, n)
            ok = (motion[ends] - motion[a]) >= need * motion[-1]
            if not ok.any():
                continue
            d = np.abs(th[ends] - th[a]).mean(axis=(1, 2))
            d[~ok] = np.inf
            j = int(d.argmin())
            # tiny preference for longer loops so near-ties keep more motion
            score = float(d[j]) - 0.02 * (j + span) / n
            if best is None or score < best:
                best, ab = score, (a, int(ends[j]))
        if best is not None:
            break
    a, b = ab
    return paths[a:b]   # b looks like a, so it is left out: the loop wraps from b-1 back to a


def _percentiles(im, lo_pct: float, hi_pct: float) -> tuple[int, int]:
    hist = im.histogram()
    total = sum(hist)
    acc, lo, hi = 0, 0, 255
    for v, c in enumerate(hist):
        acc += c
        if acc >= total * lo_pct / 100:
            lo = v
            break
    acc = 0
    for v in range(255, -1, -1):
        acc += hist[v]
        if acc >= total * (100 - hi_pct) / 100:
            hi = v
            break
    return lo, hi
