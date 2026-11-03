"""Detail passes for deep zoom (engine/zoom.py): the ComfyUI graphs that give a tile fine detail the frame never had.

zimage_img2img   Z-Image Turbo re-diffusion of an image at low denoise: the picture keeps its shapes, colours and
                 composition, and the sampler redraws what is finer than that (stitching, creases, grain of the paper)
                 in the style the prompt names. Fast (a few steps) and run at the tile's full resolution.
qwen_detail      Qwen-Image-Edit asked to add fine detail in the same drawing style (the editor understands what the
                 picture shows, so it can draw laces on a boot; it works at ~1.6 megapixels, then is resized).
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional

from ..project import BuildError


def build_zimage_img2img_graph(image: str, prompt: str, seed: int, denoise: float, prefix: str, steps: int = 8,
                               cfg: Optional[dict] = None) -> dict:
    """Z-Image Turbo img2img: VAE-encode `image` (an uploaded name), sample from `denoise` of the way up the noise
    schedule, decode. `steps` is the number of steps the whole schedule would take; a low denoise runs a share of them."""
    from .comfy import ZIMAGE
    k = dict(ZIMAGE, **(cfg or {}))
    return {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": k["model"], "weight_dtype": "default"}},
        "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": k.get("shift", 3.0)}},
        "clip": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": k["text_encoder"], "type": "lumina2", "device": k.get("text_encoder_device", "cpu")}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": k["vae"]}},
        "img": {"class_type": "LoadImage", "inputs": {"image": image}},
        "enc": {"class_type": "VAEEncode", "inputs": {"pixels": ["img", 0], "vae": ["vae", 0]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos", 0]}},
        "ks": {"class_type": "KSampler", "inputs": {
            "model": ["shift", 0], "seed": seed, "steps": steps, "cfg": 1.0,
            "sampler_name": k.get("sampler", "res_multistep"), "scheduler": "simple",
            "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["enc", 0], "denoise": denoise}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}},
    }


def _run(graph: dict, dst: Path) -> Path:
    from . import comfy
    images = comfy.run(graph, poll=2)
    tmp = Path(comfy.fetch(images[:1], str(dst.parent / f"_{dst.stem}_out")))
    try:
        shutil.move(str(next(tmp.glob("*.png"))), dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dst


def zimage_img2img(src: Path, dst: Path, prompt: str, seed: int, denoise: float, log: Callable = print) -> Path:
    """Re-diffuse `src` (any size, multiples of 16 are best) at `denoise`; writes `dst` at the same size."""
    from PIL import Image
    from . import comfy
    if not comfy.alive():
        raise BuildError(f"Deep zoom needs ComfyUI running at {comfy.COMFY} (docs/INSTALL.md) for its detail pass.")
    w, h = Image.open(src).size
    comfy.free()
    name = comfy.upload(str(src))
    out = _run(build_zimage_img2img_graph(name, prompt, seed, denoise, f"studio/zoom_{src.stem}"[:60]), dst)
    comfy.free()
    im = Image.open(out)
    if im.size != (w, h):
        im.convert("RGB").resize((w, h), Image.LANCZOS).save(out)
    return out


def qwen_detail(src: Path, dst: Path, instruction: str, seed: int, steps: int = 20, megapixels: float = 1.6,
                log: Callable = print) -> Path:
    from PIL import Image
    from ..router import edit_on_provider
    from . import comfy
    w, h = Image.open(src).size
    if edit_on_provider([src], instruction, seed, steps, dst, log=log):
        im = Image.open(dst)
        if im.size != (w, h):
            im.convert("RGB").resize((w, h), Image.LANCZOS).save(dst)
        return dst
    if not comfy.alive():
        raise BuildError(f"Deep zoom needs ComfyUI running at {comfy.COMFY} (docs/INSTALL.md) for its detail pass.")
    comfy.free()
    name = comfy.upload(str(src))
    g = comfy.build_qwen_edit_graph([name], instruction, seed, steps, prefix=f"studio/zoom_{src.stem}"[:60], megapixels=megapixels)
    out = _run(g, dst)
    comfy.free()
    im = Image.open(out)
    if im.size != (w, h):
        im.convert("RGB").resize((w, h), Image.LANCZOS).save(out)
    return out


def build_batch_graph(items: list[dict], prompt: str, seed: int, strength: float, sr: bool, cfg: Optional[dict] = None) -> dict:
    """One ComfyUI graph for a batch of tiles: each is enlarged (SeedVR2, when `sr`), fitted to a multiple of 16 and re-drawn
    (Z-Image img2img at `strength`, when > 0), and saved. The model loaders are shared between the tiles, so each model is
    loaded once for the whole batch, whatever else is in ComfyUI's queue. `items`: {"image": uploaded name, "short": the
    short side of the enlarged tile, "size": (w, h) multiples of 16}."""
    from .comfy import ZIMAGE
    k = dict(ZIMAGE)
    g: dict = {}
    if sr:
        g["dit"] = {"class_type": "SeedVR2LoadDiTModel", "inputs": {
            "model": "seedvr2_ema_7b_sharp_fp8_e4m3fn.safetensors", "device": "cuda:0", "blocks_to_swap": 32,
            "swap_io_components": False, "offload_device": "cpu", "cache_model": False, "attention_mode": "sdpa"}}
        g["svae"] = {"class_type": "SeedVR2LoadVAEModel", "inputs": {
            "model": "ema_vae_fp16.safetensors", "device": "cuda:0", "encode_tiled": True, "encode_tile_size": 1024,
            "encode_tile_overlap": 128, "decode_tiled": True, "decode_tile_size": 768, "decode_tile_overlap": 128,
            "tile_debug": "false", "offload_device": "cpu", "cache_model": False}}
    if strength > 0:
        g.update({
            "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": k["model"], "weight_dtype": "default"}},
            "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": k.get("shift", 3.0)}},
            "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": k["text_encoder"], "type": "lumina2",
                                                            "device": k.get("text_encoder_device", "cpu")}},
            "vae": {"class_type": "VAELoader", "inputs": {"vae_name": k["vae"]}},
            "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
            "neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos", 0]}},
        })
    for i, it in enumerate(items):
        g[f"img{i}"] = {"class_type": "LoadImage", "inputs": {"image": it["image"]}}
        cur = [f"img{i}", 0]
        if sr:
            g[f"sr{i}"] = {"class_type": "SeedVR2VideoUpscaler", "inputs": {
                "image": cur, "dit": ["dit", 0], "vae": ["svae", 0], "seed": seed, "resolution": int(it["short"]),
                "max_resolution": 0, "batch_size": 1, "uniform_batch_size": True, "color_correction": "lab",
                "temporal_overlap": 0, "prepend_frames": 0, "input_noise_scale": 0.0, "latent_noise_scale": 0.0,
                "offload_device": "cpu", "enable_debug": False}}
            cur = [f"sr{i}", 0]
        w, h = it["size"]
        g[f"fit{i}"] = {"class_type": "ImageScale", "inputs": {"image": cur, "upscale_method": "lanczos", "width": int(w),
                                                               "height": int(h), "crop": "disabled"}}
        cur = [f"fit{i}", 0]
        if strength > 0:
            g[f"enc{i}"] = {"class_type": "VAEEncode", "inputs": {"pixels": cur, "vae": ["vae", 0]}}
            g[f"ks{i}"] = {"class_type": "KSampler", "inputs": {
                "model": ["shift", 0], "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": k.get("sampler", "res_multistep"),
                "scheduler": "simple", "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": [f"enc{i}", 0],
                "denoise": strength}}
            g[f"dec{i}"] = {"class_type": "VAEDecode", "inputs": {"samples": [f"ks{i}", 0], "vae": ["vae", 0]}}
            cur = [f"dec{i}", 0]
        g[f"save{i}"] = {"class_type": "SaveImage", "inputs": {"images": cur, "filename_prefix": f"studio/zoomtile_{i}"}}
    return g


def enhance_batch(crops: list[Path], shorts: list[int], sizes: list[tuple[int, int]], prompt: str, seed: int, strength: float,
                  sr: bool, work: Path, log: Callable = print) -> list[Path]:
    """Enlarge and/or re-draw several tiles in ONE ComfyUI job (see build_batch_graph): returns a PNG per crop, at `sizes`."""
    from . import comfy
    if not comfy.alive():
        raise BuildError(f"Deep zoom needs ComfyUI running at {comfy.COMFY} (docs/INSTALL.md) for its enlarge and redraw "
                         "passes (or set freeze.upscale_method: lanczos and detail.strength: 0).")
    comfy.free()
    items = [{"image": comfy.upload(str(c)), "short": s, "size": z} for c, s, z in zip(crops, shorts, sizes)]
    outs = comfy.run_outputs(build_batch_graph(items, prompt, seed, strength, sr), poll=3)
    paths = []
    for i, crop in enumerate(crops):
        got = Path(comfy.fetch(outs[f"save{i}"]["images"][:1], str(work / f"_batch_{i}")))
        dst = work / f"_enh_{i}.png"
        shutil.move(str(next(got.glob("*.png"))), dst)
        shutil.rmtree(got, ignore_errors=True)
        paths.append(dst)
    comfy.free()
    return paths
