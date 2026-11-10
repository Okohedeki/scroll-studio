"""DesignAI's ComfyUI nodes (AGPL-3.0, part of DesignAI: https://github.com/Okohedeki/designai).

Installed by `studio setup-comfy` (copies this folder into ComfyUI/custom_nodes/) and used by the engine's `reveal`
(region masks for scroll-driven colour) and `faces` (face repair) stages. They are thin glue over models that are
installed as ComfyUI custom nodes of their own:

  SSRevealGround   Florence-2 (kijai/ComfyUI-Florence2, MIT): a phrase -> boxes on one frame
  SSRevealTrack    SAM 2.1 video predictor (kijai/ComfyUI-segment-anything-2, Apache-2.0): boxes/points on one frame
                   -> a soft mask for every frame, tracked forward and backward from that frame
  SSFaceRestore    GFPGAN v1.4 (Apache-2.0) over the faces of a frame batch, blended back, temporally smoothed

Why not the stock nodes: kijai's video node seeds points only (no boxes), tracks forward only, skips SAM 2's input
normalisation and returns hard masks; here a region is seeded on any frame by a box or points, tracked both ways, and
returned soft.
"""
from __future__ import annotations

import json

import torch

import comfy.model_management as mm
from comfy.utils import ProgressBar, common_upscale

CATEGORY = "ScrollStudio"
_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)


def _free():
    mm.soft_empty_cache()
    torch.cuda.empty_cache()


class SSRevealGround:
    """Florence-2 phrase grounding on one image: returns JSON {"raw": str, "boxes": [{"box": [x0,y0,x1,y1] (0-1), "label": str}]}."""

    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "image": ("IMAGE",), "florence2_model": ("FL2MODEL",),
            "text": ("STRING", {"default": "", "multiline": True}),
            "task": (["caption_to_phrase_grounding", "open_vocabulary_detection"],),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("boxes",)
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = CATEGORY

    def run(self, image, florence2_model, text, task):
        processor, patcher, dtype = florence2_model["processor"], florence2_model["patcher"], florence2_model["dtype"]
        mm.load_model_gpu(patcher)
        model = patcher.model
        _, H, W, _ = image.shape
        token = {"caption_to_phrase_grounding": "<CAPTION_TO_PHRASE_GROUNDING>",
                 "open_vocabulary_detection": "<OPEN_VOCABULARY_DETECTION>"}[task]
        img = image[:1].permute(0, 3, 1, 2)
        inputs = processor(text=token + " " + text, images=img)
        dev = patcher.load_device
        ids = model.generate(input_ids=inputs["input_ids"].to(dev), pixel_values=inputs["pixel_values"].to(dtype=dtype, device=dev),
                             max_new_tokens=256, do_sample=False, num_beams=3)
        raw = processor.batch_decode(ids, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(raw, task=token, image_size=(W, H))[token]
        out = []
        boxes = parsed.get("bboxes", [])
        labels = parsed.get("bboxes_labels") if task == "open_vocabulary_detection" else parsed.get("labels")
        for b, l in zip(boxes, labels or [""] * len(boxes)):
            out.append({"box": [b[0] / W, b[1] / H, b[2] / W, b[3] / H], "label": l})
        text_out = json.dumps({"raw": raw, "boxes": out})
        _free()
        return {"ui": {"text": [text_out]}, "result": (text_out,)}


class SSRevealTrack:
    """SAM 2.1 video predictor. `prompts` is JSON: [{"box": [x0,y0,x1,y1], "points": [[x,y],...], "labels": [1,0,...]}, ...]
    in 0-1 coordinates of the seed frame; every entry is one object, all seeded on `frame_index`, and the result is the
    union of them for every frame (soft, 0-1). Tracks forward to `end` and backward to `start` (a shot: tracking never
    runs across a cut, where the thing it follows is gone). Returns the masks of frames start..end only."""

    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "sam2_model": ("SAM2MODEL",), "images": ("IMAGE",),
            "frame_index": ("INT", {"default": 0, "min": 0}),
            "prompts": ("STRING", {"default": "[]", "multiline": True}),
        }, "optional": {
            "start": ("INT", {"default": 0, "min": 0, "tooltip": "first frame to track (a shot's first frame)"}),
            "end": ("INT", {"default": -1, "min": -1, "tooltip": "last frame to track, inclusive (-1: the last frame)"}),
        }}

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("masks",)
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(self, sam2_model, images, frame_index, prompts, start=0, end=-1):
        if sam2_model["segmentor"] != "video":
            raise ValueError("SSRevealTrack needs a SAM2 model loaded with segmentor = video")
        model, device, dtype = sam2_model["model"], sam2_model["device"], sam2_model["dtype"]
        total, H, W, _ = images.shape
        end = total - 1 if end < 0 else min(end, total - 1)
        if not 0 <= start <= frame_index <= end:
            raise ValueError(f"frame_index {frame_index} is outside the range {start}-{end} of the {total} frames")
        images, frame_index, N = images[start:end + 1], frame_index - start, end - start + 1
        items = json.loads(prompts)
        if not items:
            raise ValueError("no prompts")
        size = model.image_size
        x = common_upscale(images.movedim(-1, 1), size, size, "bilinear", "disabled")
        mean = torch.tensor(_MEAN).view(1, 3, 1, 1)
        std = torch.tensor(_STD).view(1, 3, 1, 1)
        x = ((x - mean) / std).half().contiguous()      # on the CPU: the predictor moves one frame at a time
        model.to(device)
        masks = torch.zeros(N, H, W)
        pbar = ProgressBar(N)
        with torch.inference_mode(), torch.autocast(device.type, dtype=dtype):
            state = model.init_state(x, H, W, device=device)
            for oid, it in enumerate(items, start=1):
                pts = it.get("points") or []
                kw = {}
                if pts:
                    kw["points"] = [[p[0] * W, p[1] * H] for p in pts]
                    kw["labels"] = it.get("labels") or [1] * len(pts)
                if it.get("box"):
                    b = it["box"]
                    kw["box"] = [b[0] * W, b[1] * H, b[2] * W, b[3] * H]
                model.add_new_points_or_box(state, frame_idx=frame_index, obj_id=oid, **kw)
            for reverse in (False, True):
                for fi, _ids, logits in model.propagate_in_video(state, start_frame_idx=frame_index, reverse=reverse):
                    m = torch.sigmoid(logits.float()).amax(dim=0)[0].cpu()     # union over the objects
                    masks[fi] = m
                    pbar.update(1)
            model.reset_state(state)
        del state, x
        model.to(mm.unet_offload_device())
        _free()
        return (masks,)


class SSFaceRestore:
    """GFPGAN v1.4 over the faces in a frame batch (facexlib detection and alignment), blended back softly.
    Faces smaller than `min_face` pixels are left alone; the blend weight follows the previous frame's (smoothing) so the
    repair never flickers. Returns the repaired frames, and a mask of where a face was repaired."""

    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "images": ("IMAGE",), "model_name": ("STRING", {"default": "GFPGANv1.4.pth"}),
            "strength": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.05}),
            "min_face": ("INT", {"default": 96, "min": 16, "max": 2048}),
            "smooth": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 0.95, "step": 0.05}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("images", "faces")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(self, images, model_name, strength, min_face, smooth):
        from .faces import restore_batch
        out, masks = restore_batch(images, model_name, strength, min_face, smooth, ProgressBar(len(images)))
        _free()
        return (out, masks)


NODE_CLASS_MAPPINGS = {"SSRevealGround": SSRevealGround, "SSRevealTrack": SSRevealTrack, "SSFaceRestore": SSFaceRestore}
NODE_DISPLAY_NAME_MAPPINGS = {"SSRevealGround": "DesignAI: ground phrase", "SSRevealTrack": "DesignAI: track region",
                              "SSFaceRestore": "DesignAI: restore faces"}
