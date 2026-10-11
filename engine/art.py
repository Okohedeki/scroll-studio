"""theme.art: artwork a style renders in its own medium (ascii-art prints it in characters, particles forms it in points).

The image is generated locally from a prompt (Z-Image) or taken from a file; with `motion:` LTX-2.3 animates it into a
short loop. The page gets one grayscale sprite sheet (frames stacked top to bottom, auto-contrasted) plus the facts the
runtime needs; the runtime turns those frames into characters or points at whatever size the screen has.

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

FPS = 24
NEGATIVE = "cuts, camera shake, flicker, morphing, warped body, extra limbs, text, watermark, blur"


def _ltx_size(w: int, h: int) -> tuple[int, int]:
    """About 0.44 MP at the art's aspect, both sides multiples of 32 (what LTX-2.3 wants)."""
    scale = (440_000 / (w * h)) ** 0.5
    return max(256, round(w * scale / 32) * 32), max(256, round(h * scale / 32) * 32)


def _animate(still: Path, art: Art, work: Path, log: Callable[[str], None]) -> list[Path]:
    from .backends import comfy
    if not comfy.alive():
        raise BuildError(f"theme.art has `motion:`, which is animated locally with LTX-2.3, but ComfyUI is not running at "
                         f"{comfy.COMFY}. Start it (docs/INSTALL.md) or remove `motion:` for a still.")
    from PIL import Image
    w, h = _ltx_size(*Image.open(still).size)
    frames = max(9, round(art.seconds * FPS / 8) * 8 + 1)
    log(f"  animating art with LTX-2.3 ({w}x{h}, {frames} frames): {art.motion[:80]}")
    comfy.free()
    name = comfy.upload(str(still))
    prompt = f"{art.prompt or 'The subject of the image'}. {art.motion}. Smooth natural motion, the camera stays still."
    graph = comfy.build_i2v_graph(comfy.LTX, name, frames, w, h, FPS, prompt, NEGATIVE, art.seed,
                                  prefix=f"studio/art_{work.name}")
    images = comfy.run(graph, poll=3)
    tmp = Path(comfy.fetch(images, str(work / "frames")))
    comfy.free()
    return sorted(tmp.glob("*.png"))


def build(project: Project, art: Art, dist: Path, log: Callable[[str], None] = print) -> dict:
    from PIL import Image, ImageOps
    if not art.prompt and not art.file:
        raise BuildError("theme.art needs a `prompt` (generated locally) or a `file`")
    key = json.dumps(art.model_dump(mode="json"), sort_keys=True)
    if art.file:
        src = resolve_path(project, art.file, log)
        key += f"{src.stat().st_size}:{int(src.stat().st_mtime)}"
    digest = hashlib.sha1((key + ":2").encode()).hexdigest()[:12]
    work = project.build / "_art" / digest
    # the generated clip depends only on what was asked for, not on how it is shipped (frames, width)
    vkey = json.dumps([art.prompt, art.file, art.motion, art.seconds, list(art.size), art.seed], sort_keys=True)
    vwork = project.build / "_art" / ("v_" + hashlib.sha1(vkey.encode()).hexdigest()[:12])
    sheet = work / "sheet.png"
    meta_file = work / "meta.json"
    if not (sheet.exists() and meta_file.exists()):
        work.mkdir(parents=True, exist_ok=True)
        still = src if art.file else resolve_image(project, ImageInput(generate=art.prompt, size=art.size, seed=art.seed), log)
        if art.motion:
            paths = sorted((vwork / "frames").glob("*.png"))
            if not paths:
                vwork.mkdir(parents=True, exist_ok=True)
                paths = _animate(Path(still), art, vwork, log)
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
            # a seamless loop: the clip's tail crossfades into its head, and playback starts after the head
            k = len(frames) // 5
            head, tail, middle = frames[:k], frames[-k:], frames[k:-k]
            frames = middle + [Image.blend(tail[j], head[j], (j + 1) / (k + 1)) for j in range(k)]
        fw, fh = frames[0].size
        # one tone curve for every frame (from the first), so the loop doesn't pulse
        lo, hi = _percentiles(frames[0], 2, 98)
        lut = [max(0, min(255, round((v - lo) * 255 / max(1, hi - lo)))) for v in range(256)]
        out = Image.new("L", (fw, fh * len(frames)))
        for i, f in enumerate(frames):
            out.paste(f.point(lut), (0, i * fh))
        out.save(sheet, optimize=True)
        # is the background light? then the subject is the dark part (the runtime inverts)
        edge = [frames[0].getpixel((x, y)) for x in range(fw) for y in (0, fh - 1)] + \
               [frames[0].getpixel((x, y)) for y in range(fh) for x in (0, fw - 1)]
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
