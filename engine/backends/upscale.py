"""Image upscaling for frozen moments (engine/freeze.py): the frame is enlarged before the camera crops into it, so a
close-up of a hand is still made of real pixels.

seedvr2  SeedVR2 7B restoration through ComfyUI (the same models `beat_restore` uses, run on one image): it redraws
         fine detail while it enlarges. Weights are fetched by the SeedVR2 node on first use.
lanczos  no model: Lanczos resampling and a gentle unsharp mask. Honest enlargement, soft where the source is soft.
auto     seedvr2 when ComfyUI is running and lists the SeedVR2 weights, else lanczos.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

from ..project import BuildError

DIT = "seedvr2_ema_7b_sharp_fp8_e4m3fn.safetensors"
VAE = "ema_vae_fp16.safetensors"


def seedvr2_installed(dit: str = DIT) -> bool:
    """ComfyUI is up and has the SeedVR2 DiT and VAE files (its own model list, wherever the files live)."""
    from . import comfy
    try:
        if not comfy.alive():
            return False
        have = json.loads(comfy._req("/models/seedvr2"))
    except Exception:
        return False
    return dit in have and VAE in have


def resolve_method(method: str) -> str:
    if method == "auto":
        return "seedvr2" if seedvr2_installed() else "lanczos"
    return method


def target_size(size: tuple[int, int], factor: float) -> tuple[int, int]:
    return max(2, round(size[0] * factor / 2) * 2), max(2, round(size[1] * factor / 2) * 2)


def lanczos(src: Path, dst: Path, factor: float) -> None:
    import cv2
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(src).convert("RGB"))
    w, h = target_size((im.shape[1], im.shape[0]), factor)
    up = cv2.resize(im, (w, h), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    blur = cv2.GaussianBlur(up, (0, 0), 0.6 * factor + 0.4)
    out = np.clip(up + 0.6 * (up - blur), 0, 255).astype(np.uint8)
    Image.fromarray(out).save(dst)


def seedvr2(src: Path, dst: Path, factor: float, seed: int, log: Callable[[str], None]) -> None:
    from PIL import Image
    from . import comfy
    if not comfy.alive():
        raise BuildError(f"Upscaling with SeedVR2 needs ComfyUI running at {comfy.COMFY} (docs/INSTALL.md), or set "
                         "freeze.upscale_method: lanczos.")
    w0, h0 = Image.open(src).size
    w, h = target_size((w0, h0), factor)
    short = min(w, h)
    log(f"  upscaling {w0}x{h0} -> {w}x{h} with SeedVR2")
    comfy.free()
    name = comfy.upload(str(src))
    graph = comfy.build_seedvr2_graph({"resolution": short, "batch_size": 1, "temporal_overlap": 0, "seed": seed}, None,
                                      prefix=f"studio/freeze_up_{src.stem}"[:60], image=name)
    images = comfy.run(graph, poll=2)
    tmp = Path(comfy.fetch(images[:1], str(dst.parent / f"_{dst.stem}_sr")))
    out = Image.open(next(tmp.glob("*.png"))).convert("RGB")
    if out.size != (w, h):
        out = out.resize((w, h), Image.LANCZOS)
    out.save(dst)
    shutil.rmtree(tmp, ignore_errors=True)
    comfy.free()


def upscale(src: Path, dst: Path, factor: float, method: str = "auto", seed: int = 7,
            log: Callable[[str], None] = print) -> str:
    """Write `src` enlarged `factor` times to `dst` (PNG). Returns the method that did it."""
    m = resolve_method(method)
    if factor <= 1.0001:
        shutil.copy(src, dst)
        return "none"
    if m == "seedvr2":
        seedvr2(src, dst, factor, seed, log)
    else:
        if method == "auto":
            log("  upscale: SeedVR2 is not available (ComfyUI down or its weights missing): using Lanczos + sharpen")
        lanczos(src, dst, factor)
    return m
