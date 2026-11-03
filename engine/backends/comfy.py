"""Local LTX-2.3 generation through a running ComfyUI server (no API keys).

Graph = Lightricks' "LTX-2.3 IC-LoRA Union Control (distilled)" example, with the
depth estimator swapped for the exact depth pass rendered by Blender, and an
optional detailed keyframe as the first frame.

Env: COMFY_URL (default http://127.0.0.1:8188)
"""
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

from ..config import settings

COMFY = settings()["comfy_url"]

# Default model files (names inside ComfyUI's model folders); see engine/models.yaml.
ZIMAGE = {
    "model": "z_image_turbo_bf16.safetensors",
    "text_encoder": "qwen_3_4b_fp8_mixed.safetensors",
    "vae": "ae.safetensors",
    "controlnet": "Z-Image-Turbo-Fun-Controlnet-Union-2.1-2602-8steps.safetensors",
    "steps": 8,
}
LTX = {
    "checkpoint": "ltx-2.3-22b-distilled-fp8.safetensors",
    "text_encoder": "gemma_3_12B_it_fp8_scaled.safetensors",
    "control_lora": "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
    "upscaler": "ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
}

# Wan 2.2 A14B (the second video model; `video_model: wan`). Two 14B experts: the high-noise one lays out the motion
# for the first half of the steps, the low-noise one paints the detail for the rest. Names are what ComfyUI lists;
# override any of them in studio.toml under [wan] (e.g. control_high = "wan_h/wan2.2_fun_control_high_...") and a
# file moved to another subfolder is still found by its base name (wan_model_names()).
WAN = {
    "i2v_high": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "i2v_low": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    "control_high": "wan2.2_fun_control_high_noise_14B_fp8_scaled.safetensors",
    "control_low": "wan2.2_fun_control_low_noise_14B_fp8_scaled.safetensors",
    "text_encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "vae": "wan_2.1_vae.safetensors",
    "lora_high": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    "lora_low": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
}
WAN_FOLDERS = {"i2v_high": "diffusion_models", "i2v_low": "diffusion_models", "control_high": "diffusion_models",
               "control_low": "diffusion_models", "text_encoder": "text_encoders", "vae": "vae",
               "lora_high": "loras", "lora_low": "loras"}
WAN_FPS = 16          # Wan's native frame rate
WAN_MAX_FRAMES = 81   # one clip (~5 s); longer shots are chained
# fast: the lightx2v 4-step distillation LoRAs on both experts, cfg 1 (negative prompt unused).
# full: no LoRAs, real CFG, ~20 steps; about 10x slower, for when the fast path smears fine texture.
WAN_QUALITY = {"fast": {"steps": 4, "cfg": 1.0, "shift": 5.0, "lora": True},
               "full": {"steps": 20, "cfg": 3.5, "shift": 8.0, "lora": False}}


DISTILLED_SIGMAS ="1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
REFINE_SIGMAS = "0.909375, 0.725, 0.421875, 0.0"


def _req(path, data=None, headers=None):
    req = urllib.request.Request(COMFY + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


MODEL_SUFFIXES = (".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin")

# The model files on the GPU after our last job (None: none, or unknown before this process's first job), and every
# job's timings for `build --profile`.
_RESIDENT = None
JOBS: list = []


def free(deep=False):
    """Release ComfyUI's VRAM. Call before switching model families (Z-Image <-> LTX) or handing the GPU to other
    work (Blender, a depth model): with ~19.5 GB usable, keeping one family resident while loading the other stalls.

    ComfyUI keeps its cache of loaded weights in system RAM, so the next job on the same models moves them back to
    the GPU in seconds instead of reading them from disk again (issue #4). `deep=True` also drops that cache, for
    when system RAM itself is short."""
    global _RESIDENT
    _req("/free", json.dumps({"unload_models": True, "free_memory": bool(deep)}).encode(),
         {"Content-Type": "application/json"})
    _RESIDENT = None


def models_of(graph):
    """The model files a graph loads: every node input that names a weights file."""
    names = set()
    for node in graph.values():
        for value in (node.get("inputs") or {}).values():
            if isinstance(value, str) and value.lower().endswith(MODEL_SUFFIXES):
                names.add(value.replace("\\", "/"))
    return frozenset(names)


def model_label(models):
    """A short name for a graph's models in the profile: its main weights file (the largest by name), no folder."""
    if not models:
        return "no model"
    small = ("vae", "encoder", "clip", "lora", "upscal", "umt5", "gemma", "qwen_2.5_vl", "qwen_3_4b", "ae.")
    main = sorted(models, key=lambda m: (any(k in m.lower() for k in small), m))[0]
    return os.path.splitext(main.rsplit("/", 1)[-1])[0]


def _prepare(models):
    """True when this job's models were not already on the GPU (it loads them, from RAM or from disk)."""
    global _RESIDENT
    loads = _RESIDENT is None or models != _RESIDENT
    _RESIDENT = models
    return loads


def jobs_since(t0):
    """The ComfyUI jobs this process ran since `t0` (time.time()), for `build --profile`."""
    return [j for j in JOBS if j["at"] >= t0 - 1]


def _timings(status, submitted):
    """(seconds waiting in ComfyUI's queue, seconds running) from a finished prompt's status messages."""
    stamps = {m[0]: m[1].get("timestamp") for m in status.get("messages", [])
              if isinstance(m, (list, tuple)) and len(m) == 2 and isinstance(m[1], dict)}
    start, end = stamps.get("execution_start"), stamps.get("execution_success")
    if start is None or end is None:
        return None, None
    return round(max(0.0, start / 1000 - submitted), 2), round((end - start) / 1000, 2)


def upload(path):
    """Send a local file into ComfyUI's input folder; returns the stored name."""
    boundary = uuid.uuid4().hex
    name = os.path.basename(path)
    with open(path, "rb") as f:
        payload = f.read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    res = json.loads(_req("/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    return res["name"]


def build_keyframe_graph(kcfg, prompt, depth_image, width, height, seed, prefix):
    """Z-Image Turbo + Fun ControlNet Union (depth): one detailed still that matches the blockout."""
    return {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": kcfg["model"], "weight_dtype": "default"}},
        "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.0}},
        # Text encoder on CPU: runs once per still, and keeps ~5 GB of VRAM free for the diffusion model.
        "clip": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": kcfg["text_encoder"], "type": "lumina2", "device": kcfg.get("text_encoder_device", "cpu")}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": kcfg["vae"]}},
        "patch": {"class_type": "ModelPatchLoader", "inputs": {"name": kcfg["controlnet"]}},
        "depth": {"class_type": "LoadImage", "inputs": {"image": depth_image}},
        "cn": {"class_type": "ZImageFunControlnet", "inputs": {
            "model": ["shift", 0], "model_patch": ["patch", 0], "vae": ["vae", 0],
            "strength": kcfg.get("control_strength", 0.8), "image": ["depth", 0]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos", 0]}},
        "latent": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "ks": {"class_type": "KSampler", "inputs": {
            "model": ["cn", 0], "seed": seed, "steps": kcfg.get("steps", 8), "cfg": 1.0,
            "sampler_name": kcfg.get("sampler", "res_multistep"), "scheduler": "simple",
            "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0], "denoise": 1.0}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}},
    }


def build_txt2img_graph(prompt, width, height, seed, prefix, cfg=None):
    """Z-Image Turbo text-to-image: photoreal stills for any image input (`generate:` in the spec)."""
    k = dict(ZIMAGE, **(cfg or {}))
    return {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": k["model"], "weight_dtype": "default"}},
        "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": k.get("shift", 3.0)}},
        "clip": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": k["text_encoder"], "type": "lumina2", "device": k.get("text_encoder_device", "cpu")}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": k["vae"]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos", 0]}},
        "latent": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "ks": {"class_type": "KSampler", "inputs": {
            "model": ["shift", 0], "seed": seed, "steps": k["steps"], "cfg": 1.0,
            "sampler_name": k.get("sampler", "res_multistep"), "scheduler": "simple",
            "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0], "denoise": 1.0}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}},
    }


def alive():
    try:
        _req("/system_stats")
        return True
    except Exception:
        return False


def build_graph(cfg, guide_video, first_image, frames, width, height, fps, prefix, guides=()):
    """ComfyUI API-format graph. Node ids are arbitrary strings.

    guides: (uploaded_image_name, frame_idx, strength) keyframes pinned after the first frame;
    frame_idx -1 = last frame. Mid-shot indices should be multiples of 8 (one latent frame).
    """
    use_keyframe = bool(cfg.get("keyframe_strength")) and first_image is not None
    g = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": cfg["checkpoint"]}},
        "te": {"class_type": "LTXAVTextEncoderLoader", "inputs": {
            "text_encoder": cfg["text_encoder"], "ckpt_name": cfg["checkpoint"], "device": "default"}},
        "avae": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": cfg["checkpoint"]}},
        "iclora": {"class_type": "LTXICLoRALoaderModelOnly", "inputs": {
            "model": ["ckpt", 0], "lora_name": cfg["control_lora"], "strength_model": cfg.get("control_strength", 1.0)}},

        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": cfg["prompt"], "clip": ["te", 0]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": cfg.get("negative_prompt", ""), "clip": ["te", 0]}},
        "cond": {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["pos", 0], "negative": ["neg", 0], "frame_rate": float(fps)}},

        "guide_vid": {"class_type": "LoadVideo", "inputs": {"file": guide_video}},
        "guide": {"class_type": "GetVideoComponents", "inputs": {"video": ["guide_vid", 0]}},
        "first": {"class_type": "LoadImage", "inputs": {"image": first_image}},

        "latent": {"class_type": "EmptyLTXVLatentVideo", "inputs": {
            "width": width, "height": height, "length": frames, "batch_size": 1}},
        "i2v": {"class_type": "LTXVImgToVideoConditionOnly", "inputs": {
            "vae": ["ckpt", 2], "image": ["first", 0], "latent": ["latent", 0],
            "strength": float(cfg.get("keyframe_strength") or 1.0), "bypass": not use_keyframe}},
        "addguide": {"class_type": "LTXAddVideoICLoRAGuide", "inputs": {
            "positive": ["cond", 0], "negative": ["cond", 1], "vae": ["ckpt", 2], "latent": ["i2v", 0],
            "image": ["guide", 0], "frame_idx": 0, "strength": cfg.get("guide_strength", 1.0),
            "latent_downscale_factor": ["iclora", 1], "crop": "disabled",
            "use_tiled_encode": False, "tile_size": 256, "tile_overlap": 64}},

    }
    guided = "addguide"
    for i, (image, frame_idx, strength) in enumerate(guides):
        g[f"kimg{i}"] = {"class_type": "LoadImage", "inputs": {"image": image}}
        g[f"kguide{i}"] = {"class_type": "LTXVAddGuide", "inputs": {
            "positive": [guided, 0], "negative": [guided, 1], "vae": ["ckpt", 2],
            "latent": [guided, 2], "image": [f"kimg{i}", 0], "frame_idx": frame_idx,
            "strength": float(strength)}}
        guided = f"kguide{i}"
    g.update({
        "alat": {"class_type": "LTXVEmptyLatentAudio", "inputs": {
            "frames_number": frames, "frame_rate": int(fps), "batch_size": 1, "audio_vae": ["avae", 0]}},
        "av": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": [guided, 2], "audio_latent": ["alat", 0]}},

        "guider": {"class_type": "CFGGuider", "inputs": {
            "model": ["iclora", 0], "positive": [guided, 0], "negative": [guided, 1], "cfg": 1.0}},
        # euler_ancestral re-injects noise every step, which survives 8 distilled steps as grain;
        # euler_cfg_pp is the deterministic variant.
        "sampler": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": cfg.get("sampler", "euler_ancestral_cfg_pp")}},
        "sigmas": {"class_type": "ManualSigmas", "inputs": {"sigmas": DISTILLED_SIGMAS}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": cfg.get("seed", 42)}},
        "sample": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler", 0],
            "sigmas": ["sigmas", 0], "latent_image": ["av", 0]}},
        "split": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["sample", 0]}},
        "crop": {"class_type": "LTXVCropGuides", "inputs": {
            "positive": [guided, 0], "negative": [guided, 1], "latent": ["split", 0]}},
    })
    video_latent = ["crop", 2]

    if cfg.get("upscale"):
        # Stage 2: 2x latent upscale, then a short refine pass with the same guide.
        g.update({
            "upm": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": cfg["upscaler"]}},
            "up": {"class_type": "LTXVLatentUpsampler", "inputs": {
                "samples": video_latent, "upscale_model": ["upm", 0], "vae": ["ckpt", 2]}},
            "i2v2": {"class_type": "LTXVImgToVideoConditionOnly", "inputs": {
                "vae": ["ckpt", 2], "image": ["first", 0], "latent": ["up", 0],
                "strength": float(cfg.get("keyframe_strength") or 1.0), "bypass": not use_keyframe}},
            "addguide2": {"class_type": "LTXAddVideoICLoRAGuide", "inputs": {
                "positive": ["crop", 0], "negative": ["crop", 1], "vae": ["ckpt", 2], "latent": ["i2v2", 0],
                "image": ["guide", 0], "frame_idx": 0, "strength": cfg.get("guide_strength", 1.0),
                "latent_downscale_factor": ["iclora", 1], "crop": "disabled",
                "use_tiled_encode": True, "tile_size": 256, "tile_overlap": 64}},
            "av2": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["addguide2", 2], "audio_latent": ["split", 1]}},
            "guider2": {"class_type": "CFGGuider", "inputs": {
                "model": ["iclora", 0], "positive": ["addguide2", 0], "negative": ["addguide2", 1], "cfg": 1.0}},
            "sigmas2": {"class_type": "ManualSigmas", "inputs": {"sigmas": REFINE_SIGMAS}},
            "sample2": {"class_type": "SamplerCustomAdvanced", "inputs": {
                "noise": ["noise", 0], "guider": ["guider2", 0], "sampler": ["sampler", 0],
                "sigmas": ["sigmas2", 0], "latent_image": ["av2", 0]}},
            "split2": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["sample2", 0]}},
            "crop2": {"class_type": "LTXVCropGuides", "inputs": {
                "positive": ["addguide2", 0], "negative": ["addguide2", 1], "latent": ["split2", 0]}},
        })
        video_latent = ["crop2", 2]

    g["decode"] = {"class_type": "LTXVTiledVAEDecode", "inputs": {
        "vae": ["ckpt", 2], "latents": video_latent, "horizontal_tiles": 2, "vertical_tiles": 2,
        "overlap": 6, "last_frame_fix": False, "working_device": "auto", "working_dtype": "auto"}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}}
    return g


def build_i2v_graph(cfg, first_image, frames, width, height, fps, prompt, negative, seed, prefix, strength=1.0,
                    end_image=None, end_strength=1.0):
    """LTX-2.3 image-to-video without a depth guide: animate one still into a short clip (theme.art, film beats).
    `end_image` pins the last frame too, so the motion lands where it should (a door that ends open)."""
    g = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": cfg["checkpoint"]}},
        "te": {"class_type": "LTXAVTextEncoderLoader", "inputs": {
            "text_encoder": cfg["text_encoder"], "ckpt_name": cfg["checkpoint"], "device": "default"}},
        "avae": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": cfg["checkpoint"]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["te", 0]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["te", 0]}},
        "cond": {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["pos", 0], "negative": ["neg", 0], "frame_rate": float(fps)}},
        "first": {"class_type": "LoadImage", "inputs": {"image": first_image}},
        "latent": {"class_type": "EmptyLTXVLatentVideo", "inputs": {
            "width": width, "height": height, "length": frames, "batch_size": 1}},
        "i2v": {"class_type": "LTXVImgToVideoConditionOnly", "inputs": {
            "vae": ["ckpt", 2], "image": ["first", 0], "latent": ["latent", 0], "strength": float(strength), "bypass": False}},
        "alat": {"class_type": "LTXVEmptyLatentAudio", "inputs": {
            "frames_number": frames, "frame_rate": int(fps), "batch_size": 1, "audio_vae": ["avae", 0]}},
        "av": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["i2v", 0], "audio_latent": ["alat", 0]}},
        "guider": {"class_type": "CFGGuider", "inputs": {
            "model": ["ckpt", 0], "positive": ["cond", 0], "negative": ["cond", 1], "cfg": 1.0}},
        "sampler": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": cfg.get("sampler", "euler_cfg_pp")}},
        "sigmas": {"class_type": "ManualSigmas", "inputs": {"sigmas": DISTILLED_SIGMAS}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "sample": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler", 0],
            "sigmas": ["sigmas", 0], "latent_image": ["av", 0]}},
        "split": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["sample", 0]}},
        "decode": {"class_type": "LTXVTiledVAEDecode", "inputs": {
            "vae": ["ckpt", 2], "latents": ["split", 0], "horizontal_tiles": 2, "vertical_tiles": 2,
            "overlap": 6, "last_frame_fix": False, "working_device": "auto", "working_dtype": "auto"}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}},
    }
    if end_image:
        g["last"] = {"class_type": "LoadImage", "inputs": {"image": end_image}}
        g["endguide"] = {"class_type": "LTXVAddGuide", "inputs": {
            "positive": ["cond", 0], "negative": ["cond", 1], "vae": ["ckpt", 2], "latent": ["i2v", 0],
            "image": ["last", 0], "frame_idx": -1, "strength": float(end_strength)}}
        g["av"]["inputs"]["video_latent"] = ["endguide", 2]
        g["guider"]["inputs"].update(positive=["endguide", 0], negative=["endguide", 1])
        g["crop"] = {"class_type": "LTXVCropGuides", "inputs": {
            "positive": ["endguide", 0], "negative": ["endguide", 1], "latent": ["split", 0]}}
        g["decode"]["inputs"]["latents"] = ["crop", 2]
    return g


def listed(folder):
    """File names ComfyUI can load from one of its model folders (subfolders included), or None if it is not up."""
    try:
        return json.loads(_req(f"/models/{folder}"))
    except Exception:
        return None


def wan_model_names(cfg=None, need=None):
    """The Wan file names to put in a graph: WAN, then studio.toml [wan], then `cfg`; each checked against what
    ComfyUI lists, and a file that moved to another subfolder is matched by its base name. Raises SystemExit naming
    every missing file (with where to get it) when `need` lists keys that ComfyUI can't see."""
    names = dict(WAN, **{k: v for k, v in (settings().get("wan") or {}).items() if k in WAN}, **{k: v for k, v in (cfg or {}).items() if k in WAN})
    cache, missing = {}, []
    for key in need or ():
        folder = WAN_FOLDERS[key]
        if folder not in cache:
            cache[folder] = listed(folder)
        have = cache[folder]
        if have is None:
            continue    # ComfyUI not reachable; the run itself will say so
        want = names[key]
        if want in have:
            continue
        base = want.replace("\\", "/").rsplit("/", 1)[-1]
        alt = [h for h in have if h.replace("\\", "/").rsplit("/", 1)[-1] == base]
        if alt:
            names[key] = alt[0]
        else:
            missing.append(f"{folder}/{want}")
    if missing:
        raise SystemExit("video_model wan: ComfyUI can't see " + ", ".join(missing) + ". Download them from "
                         "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged (see engine/models.yaml), or "
                         "point studio.toml [wan] at the names ComfyUI lists. `studio doctor` checks them all.")
    return names


def build_wan_graph(cfg, prompt, negative, width, height, frames, seed, prefix, start_image=None, end_image=None,
                    control_video=None, ref_image=None):
    """Wan 2.2 A14B video: image-to-video (start image, optional end image) or Fun Control (a control video, e.g. the
    take's Blender depth guide, with the start image and a reference still).

    Two-stage MoE sampling: KSamplerAdvanced on the high-noise expert for steps [0, split), returning the leftover
    noise, then the low-noise expert for [split, steps). cfg: quality (fast|full), steps, cfg, shift, split, sampler,
    scheduler, lora_strength and any WAN file name. `frames` must be 4k+1 (<= 81 for one clip).
    """
    q = dict(WAN_QUALITY[cfg.get("quality", "fast")])
    q.update({k: cfg[k] for k in ("steps", "cfg", "shift") if cfg.get(k) is not None})
    control = control_video is not None
    hi_key, lo_key = ("control_high", "control_low") if control else ("i2v_high", "i2v_low")
    use_lora = q["lora"] and cfg.get("lora", True)
    names = wan_model_names(cfg, need=[hi_key, lo_key, "text_encoder", "vae"] + (["lora_high", "lora_low"] if use_lora else []))
    steps = int(q["steps"])
    split = int(cfg.get("split") or max(1, steps // 2))
    g = {
        "unet_hi": {"class_type": "UNETLoader", "inputs": {"unet_name": names[hi_key], "weight_dtype": "default"}},
        "unet_lo": {"class_type": "UNETLoader", "inputs": {"unet_name": names[lo_key], "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": names["text_encoder"], "type": "wan", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": names["vae"]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": negative or "", "clip": ["clip", 0]}},
    }
    m_hi, m_lo = ["unet_hi", 0], ["unet_lo", 0]
    if use_lora:
        s = float(cfg.get("lora_strength", 1.0))
        g["lora_hi"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": m_hi, "lora_name": names["lora_high"], "strength_model": s}}
        g["lora_lo"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": m_lo, "lora_name": names["lora_low"], "strength_model": s}}
        m_hi, m_lo = ["lora_hi", 0], ["lora_lo", 0]
    g["shift_hi"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": m_hi, "shift": float(q["shift"])}}
    g["shift_lo"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": m_lo, "shift": float(q["shift"])}}
    common = {"positive": ["pos", 0], "negative": ["neg", 0], "vae": ["vae", 0], "width": width, "height": height,
              "length": frames, "batch_size": 1}
    if start_image:
        g["first"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
    if control:
        g["ctl_vid"] = {"class_type": "LoadVideo", "inputs": {"file": control_video}}
        g["ctl"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["ctl_vid", 0]}}
        cond = dict(common, control_video=["ctl", 0])
        if ref_image:
            g["ref"] = {"class_type": "LoadImage", "inputs": {"image": ref_image}}
            cond["ref_image"] = ["ref", 0]
        if start_image:
            # Wan22FunControlToVideo's execute() takes start_image (the first latent frame is pinned to it) although
            # its schema doesn't list it; ComfyUI passes linked inputs through, which is what chains the segments.
            cond["start_image"] = ["first", 0]
        g["cond"] = {"class_type": "Wan22FunControlToVideo", "inputs": cond}
    elif end_image:
        g["last"] = {"class_type": "LoadImage", "inputs": {"image": end_image}}
        g["cond"] = {"class_type": "WanFirstLastFrameToVideo", "inputs": dict(
            common, start_image=["first", 0], end_image=["last", 0])}
    else:
        g["cond"] = {"class_type": "WanImageToVideo", "inputs": dict(common, **({"start_image": ["first", 0]} if start_image else {}))}
    ks = {"noise_seed": int(seed), "steps": steps, "cfg": float(q["cfg"]),
          "sampler_name": cfg.get("sampler", "euler"), "scheduler": cfg.get("scheduler", "simple"),
          "positive": ["cond", 0], "negative": ["cond", 1]}
    g["ks_hi"] = {"class_type": "KSamplerAdvanced", "inputs": dict(
        ks, model=["shift_hi", 0], add_noise="enable", latent_image=["cond", 2],
        start_at_step=0, end_at_step=split, return_with_leftover_noise="enable")}
    g["ks_lo"] = {"class_type": "KSamplerAdvanced", "inputs": dict(
        ks, model=["shift_lo", 0], add_noise="disable", latent_image=["ks_hi", 0],
        start_at_step=split, end_at_step=10000, return_with_leftover_noise="disable")}
    g["decode"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks_lo", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}}
    return g


QWEN_EDIT = {"unet": "qwen_image_edit_2511_fp8mixed.safetensors", "clip": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
             "vae": "qwen_image_vae.safetensors"}


def build_qwen_edit_graph(images, instruction, seed, steps, prefix, megapixels=1.6, cfg=QWEN_EDIT, denoise=1.0):
    """Qwen-Image-Edit: edit images[0] following `instruction`; images[1:] (up to two) are references it can use.
    denoise < 1 starts the sampler from images[0]'s own latent, partly noised (SDEdit): the layout stays where it was, so a
    relight cannot move the place (`light` scenes); 1 starts from pure noise, as every other edit does."""
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": cfg["unet"], "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": cfg["clip"], "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": cfg["vae"]}},
        "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.1}},
        "norm": {"class_type": "CFGNorm", "inputs": {"model": ["shift", 0], "strength": 1.0}},
    }
    enc = {}
    for i, name in enumerate(images[:3]):
        g[f"img{i}"] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[f"sc{i}"] = {"class_type": "ImageScaleToTotalPixels", "inputs": {
            "image": [f"img{i}", 0], "upscale_method": "lanczos", "megapixels": megapixels if i == 0 else 1.0,
            "resolution_steps": 16}}
        enc[f"image{i + 1}"] = [f"sc{i}", 0]
    g["pos"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": dict(clip=["clip", 0], prompt=instruction, vae=["vae", 0], **enc)}
    g["neg"] = {"class_type": "TextEncodeQwenImageEditPlus", "inputs": dict(clip=["clip", 0], prompt="", vae=["vae", 0], **enc)}
    g["lat"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["sc0", 0], "vae": ["vae", 0]}}
    g["ks"] = {"class_type": "KSampler", "inputs": {
        "model": ["norm", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0],
        "seed": seed, "steps": steps, "cfg": 4.0, "sampler_name": "euler", "scheduler": "simple", "denoise": denoise}}
    g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": prefix}}
    return g


def build_upscale_graph(cfg, video, frames, fps, prompt, prefix):
    """Second-stage upscale of a finished clip: encode -> 2x latent upsampler -> short refine -> decode.

    This is LTX's own stage 2, run on already-generated footage. Refining from a partial sigma keeps
    the shot faithful to the input while adding detail that a pixel resize can't.
    """
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": cfg["checkpoint"]}},
        "te": {"class_type": "LTXAVTextEncoderLoader", "inputs": {
            "text_encoder": cfg["text_encoder"], "ckpt_name": cfg["checkpoint"], "device": "default"}},
        "avae": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": cfg["checkpoint"]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["te", 0]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": cfg.get("negative_prompt", ""), "clip": ["te", 0]}},
        "cond": {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["pos", 0], "negative": ["neg", 0], "frame_rate": float(fps)}},

        "vid": {"class_type": "LoadVideo", "inputs": {"file": video}},
        "comp": {"class_type": "GetVideoComponents", "inputs": {"video": ["vid", 0]}},
        "enc": {"class_type": "VAEEncodeTiled", "inputs": {
            "pixels": ["comp", 0], "vae": ["ckpt", 2], "tile_size": 512, "overlap": 64,
            "temporal_size": 64, "temporal_overlap": 8}},
        "upm": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": cfg["upscaler"]}},
        "up": {"class_type": "LTXVLatentUpsampler", "inputs": {
            "samples": ["enc", 0], "upscale_model": ["upm", 0], "vae": ["ckpt", 2]}},
        "alat": {"class_type": "LTXVEmptyLatentAudio", "inputs": {
            "frames_number": frames, "frame_rate": int(fps), "batch_size": 1, "audio_vae": ["avae", 0]}},
        "av": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["up", 0], "audio_latent": ["alat", 0]}},

        "guider": {"class_type": "CFGGuider", "inputs": {
            "model": ["ckpt", 0], "positive": ["cond", 0], "negative": ["cond", 1], "cfg": 1.0}},
        "sampler": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": cfg.get("sampler", "euler_cfg_pp")}},
        "sigmas": {"class_type": "ManualSigmas", "inputs": {"sigmas": cfg.get("sigmas", "0.725, 0.421875, 0.0")}},
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": cfg.get("seed", 42)}},
        "sample": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler", 0],
            "sigmas": ["sigmas", 0], "latent_image": ["av", 0]}},
        "split": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["sample", 0]}},
        "decode": {"class_type": "LTXVTiledVAEDecode", "inputs": {
            "vae": ["ckpt", 2], "latents": ["split", 0], "horizontal_tiles": 3, "vertical_tiles": 2,
            "overlap": 6, "last_frame_fix": False, "working_device": "auto", "working_dtype": "auto"}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}},
    }


def build_seedvr2_graph(ucfg, video, prefix, image=None):
    """SeedVR2 video restoration + upscale (one diffusion step, temporally consistent).

    Removes the render's noise and compression mush and redraws fine detail at the target short side
    (2160 = 4K UHD). Weights are block-swapped to CPU and the VAE is tiled so 4K fits in ~19 GB.
    With `image` (an uploaded image's name) it restores that one image instead (a frozen moment's frame).
    """
    src = ({"vid": {"class_type": "LoadImage", "inputs": {"image": image}}} if image else
           {"vid": {"class_type": "LoadVideo", "inputs": {"file": video}},
            "comp": {"class_type": "GetVideoComponents", "inputs": {"video": ["vid", 0]}}})
    return {
        **src,
        "dit": {"class_type": "SeedVR2LoadDiTModel", "inputs": {
            "model": ucfg.get("model", "seedvr2_ema_7b_sharp_fp8_e4m3fn.safetensors"), "device": "cuda:0",
            "blocks_to_swap": ucfg.get("blocks_to_swap", 32), "swap_io_components": False,
            "offload_device": "cpu", "cache_model": False, "attention_mode": "sdpa"}},
        "vae": {"class_type": "SeedVR2LoadVAEModel", "inputs": {
            "model": ucfg.get("vae", "ema_vae_fp16.safetensors"), "device": "cuda:0",
            "encode_tiled": True, "encode_tile_size": 1024, "encode_tile_overlap": 128,
            "decode_tiled": True, "decode_tile_size": ucfg.get("decode_tile", 768), "decode_tile_overlap": 128,
            "tile_debug": "false", "offload_device": "cpu", "cache_model": False}},
        "up": {"class_type": "SeedVR2VideoUpscaler", "inputs": {
            "image": ["vid", 0] if image else ["comp", 0], "dit": ["dit", 0], "vae": ["vae", 0], "seed": ucfg.get("seed", 42),
            "resolution": ucfg.get("resolution", 2160), "max_resolution": 0,
            "batch_size": ucfg.get("batch_size", 9), "uniform_batch_size": True,
            "color_correction": ucfg.get("color_correction", "lab"), "temporal_overlap": ucfg.get("temporal_overlap", 3),
            "prepend_frames": 0, "input_noise_scale": 0.0, "latent_noise_scale": 0.0,
            "offload_device": "cpu", "enable_debug": False}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["up", 0], "filename_prefix": prefix}},
    }


def interrupt(prompt_id=None):
    """Stop the running job. With prompt_id, only when that job is the one running (ComfyUI may be shared)."""
    body = json.dumps({"prompt_id": prompt_id} if prompt_id else {}).encode()
    _req("/interrupt", body, {"Content-Type": "application/json"})


def _queue_state(pid):
    """'running', 'pending' (with how many jobs are ahead) or None (finished or unknown)."""
    q = json.loads(_req("/queue"))
    if any(x[1] == pid for x in q.get("queue_running", [])):
        return "running", 0
    pending = sorted(q.get("queue_pending", []), key=lambda x: x[0])
    for i, x in enumerate(pending):
        if x[1] == pid:
            return "pending", i + len(q.get("queue_running", []))
    return None, 0


def run(graph, poll=5, timeout=45 * 60):
    """Queue a graph and block until it finishes; returns the list of saved image records (node `save`).

    ComfyUI may be shared with other jobs: time spent waiting in its queue does not count towards `timeout`
    (which limits our own execution), and a timed-out job is interrupted only while it is the one running, or
    taken out of the queue while it is still waiting."""
    return run_outputs(graph, poll, timeout)["save"]["images"]


def run_outputs(graph, poll=5, timeout=45 * 60):
    """`run`, returning every output node's record ({node id: {"images": [...], "text": [...]}}); for graphs whose
    answer is not an image (a text node, a mask batch saved as images under another node id)."""
    models = models_of(graph)
    loads = _prepare(models)
    submitted = time.time()
    body = json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode()
    try:
        res = json.loads(_req("/prompt", body, {"Content-Type": "application/json"}))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ComfyUI rejected the graph: {e.read().decode(errors='replace')}")
    pid = res["prompt_id"]
    start = time.time()
    run_start, told = None, start          # the "still waiting" notice comes after 5 min, not at once
    while run_start is None or time.time() - run_start < timeout:
        hist = json.loads(_req(f"/history/{pid}"))
        if pid in hist:
            status = hist[pid].get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                raise SystemExit(f"ComfyUI error: {json.dumps(msgs, indent=1)[:3000]}")
            if status.get("completed"):
                print(f"  done in {int(time.time() - start)}s", flush=True)
                queued, ran = _timings(status, submitted)
                JOBS.append({"at": round(submitted, 1), "model": model_label(models), "loads": loads,
                             "seconds": round(time.time() - submitted, 2), "queued": queued, "ran": ran})
                return hist[pid]["outputs"]
        if run_start is None:
            state, ahead = _queue_state(pid)
            if state == "running" or (state is None and pid not in hist):
                run_start = time.time()
            elif state == "pending" and time.time() - told > 300:
                print(f"  waiting in ComfyUI's queue ({ahead} job(s) ahead)", flush=True)
                told = time.time()
        time.sleep(poll)
    state, _ = _queue_state(pid)
    if state == "running":
        interrupt(pid)   # don't leave a stalled job hogging the GPU (only ours)
    elif state == "pending":
        _req("/queue", json.dumps({"delete": [pid]}).encode(), {"Content-Type": "application/json"})
    raise SystemExit(f"Timed out after {timeout // 60} min of ComfyUI running prompt {pid}, and cancelled it. "
                     "A render this slow usually means VRAM overflowed into system RAM: split the segment "
                     "or lower ltx.res, and close games or other GPU apps.")


def fetch(images, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for i, im in enumerate(images):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im["subfolder"], "type": im["type"]})
        with open(os.path.join(out_dir, f"{i + 1:04d}.png"), "wb") as f:
            f.write(_req(f"/view?{q}"))
    return out_dir
