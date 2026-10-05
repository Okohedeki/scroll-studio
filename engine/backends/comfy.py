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

DISTILLED_SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
REFINE_SIGMAS = "0.909375, 0.725, 0.421875, 0.0"


def _req(path, data=None, headers=None):
    req = urllib.request.Request(COMFY + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def free():
    """Unload every model from VRAM. Call before switching model families (Z-Image <-> LTX):
    with ~19.5 GB usable, keeping one family resident while loading the other stalls ComfyUI."""
    _req("/free", json.dumps({"unload_models": True, "free_memory": True}).encode(),
         {"Content-Type": "application/json"})


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


def build_seedvr2_graph(ucfg, video, prefix):
    """SeedVR2 video restoration + upscale (one diffusion step, temporally consistent).

    Removes the render's noise and compression mush and redraws fine detail at the target short side
    (2160 = 4K UHD). Weights are block-swapped to CPU and the VAE is tiled so 4K fits in ~19 GB.
    """
    return {
        "vid": {"class_type": "LoadVideo", "inputs": {"file": video}},
        "comp": {"class_type": "GetVideoComponents", "inputs": {"video": ["vid", 0]}},
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
            "image": ["comp", 0], "dit": ["dit", 0], "vae": ["vae", 0], "seed": ucfg.get("seed", 42),
            "resolution": ucfg.get("resolution", 2160), "max_resolution": 0,
            "batch_size": ucfg.get("batch_size", 9), "uniform_batch_size": True,
            "color_correction": ucfg.get("color_correction", "lab"), "temporal_overlap": ucfg.get("temporal_overlap", 3),
            "prepend_frames": 0, "input_noise_scale": 0.0, "latent_noise_scale": 0.0,
            "offload_device": "cpu", "enable_debug": False}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["up", 0], "filename_prefix": prefix}},
    }


def interrupt():
    _req("/interrupt", b"{}", {"Content-Type": "application/json"})


def run(graph, poll=5, timeout=45 * 60):
    """Queue a graph and block until it finishes; returns the list of saved image records."""
    body = json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode()
    try:
        res = json.loads(_req("/prompt", body, {"Content-Type": "application/json"}))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ComfyUI rejected the graph: {e.read().decode(errors='replace')}")
    pid = res["prompt_id"]
    start = time.time()
    while time.time() - start < timeout:
        hist = json.loads(_req(f"/history/{pid}"))
        if pid in hist:
            status = hist[pid].get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                raise SystemExit(f"ComfyUI error: {json.dumps(msgs, indent=1)[:3000]}")
            if status.get("completed"):
                print(f"  done in {int(time.time() - start)}s", flush=True)
                return hist[pid]["outputs"]["save"]["images"]
        time.sleep(poll)
    interrupt()  # don't leave a stalled job hogging the GPU
    raise SystemExit(f"Timed out after {timeout // 60} min waiting for ComfyUI prompt {pid} and cancelled it. "
                     "A render this slow usually means VRAM overflowed into system RAM: split the segment "
                     "or lower ltx.res, and close games or other GPU apps.")


def fetch(images, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for i, im in enumerate(images):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im["subfolder"], "type": im["type"]})
        with open(os.path.join(out_dir, f"{i + 1:04d}.png"), "wb") as f:
            f.write(_req(f"/view?{q}"))
    return out_dir
