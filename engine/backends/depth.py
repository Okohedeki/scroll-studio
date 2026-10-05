"""Monocular depth with Depth Anything V2 (transformers). Small = Apache-2.0 (default); Base/Large = CC-BY-NC."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import settings

MODELS = {
    "small": "depth-anything/Depth-Anything-V2-Small-hf",
    "base": "depth-anything/Depth-Anything-V2-Base-hf",
    "large": "depth-anything/Depth-Anything-V2-Large-hf",
}


@lru_cache(maxsize=2)
def _load(size: str):
    os.environ.setdefault("HF_HOME", str(Path(settings()["model_dir"]) / "hf"))
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    name = MODELS[size]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForDepthEstimation.from_pretrained(name).to(dev).eval()
    return AutoImageProcessor.from_pretrained(name), model, dev


def estimate(img: Image.Image, size: str = "small") -> np.ndarray:
    """Relative depth, 0 (far) .. 1 (near), at the image's own resolution."""
    import torch
    proc, model, dev = _load(size)
    inputs = proc(images=img.convert("RGB"), return_tensors="pt").to(dev)
    with torch.inference_mode():
        pred = model(**inputs).predicted_depth
    d = torch.nn.functional.interpolate(pred[:, None], size=(img.height, img.width), mode="bicubic", align_corners=False)[0, 0]
    d = d.float().cpu().numpy()
    lo, hi = np.percentile(d, [1, 99.5])
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
