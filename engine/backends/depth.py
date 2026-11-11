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


NON_COMMERCIAL = {"base", "large"}


def commercial_only() -> bool:
    """STUDIO_COMMERCIAL_ONLY=1 (set on the DesignAI cloud's build machine, which is a paid service) keeps every
    model with a non-commercial licence out of the build: those requests get the commercial-friendly model."""
    return os.environ.get("STUDIO_COMMERCIAL_ONLY", "").strip().lower() in ("1", "true", "yes")


def _size(size: str) -> str:
    if size in NON_COMMERCIAL and commercial_only():
        import warnings
        warnings.warn(f"depth_model: {size} is non-commercial (CC-BY-NC), so this build uses small (Apache-2.0) instead")
        return "small"
    return size


def _load(size: str):
    return _load_size(_size(size))


@lru_cache(maxsize=2)
def _load_size(size: str):
    os.environ.setdefault("HF_HOME", str(Path(settings()["model_dir"]) / "hf"))
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    except ImportError as e:
        from ..project import BuildError
        if e.name in ("torch", "transformers"):
            raise BuildError(f"photo parallax estimates depth with PyTorch and transformers, and {e.name} is not installed: "
                             "run `pip install torch transformers` (the CPU build is enough; docs/laptop.md)") from None
        cause = e.__cause__ or e.__context__ or e      # installed, but something it imports is broken
        raise BuildError("photo parallax estimates depth with transformers, which is installed but failed to import: "
                         f"{type(cause).__name__}: {cause}. Repair or upgrade the package it names "
                         "(`pip install -U <package>`)") from None
    name = MODELS[size]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    # safetensors only: never fall back to a pickled pytorch_model.bin, which can run code when loaded
    model = AutoModelForDepthEstimation.from_pretrained(name, use_safetensors=True).to(dev).eval()
    return AutoImageProcessor.from_pretrained(name), model, dev


def estimate(img: Image.Image, size: str = "small") -> np.ndarray:
    """Relative depth, 0 (far) .. 1 (near), at the image's own resolution."""
    proc, model, dev = _load(size)
    import torch
    inputs = proc(images=img.convert("RGB"), return_tensors="pt").to(dev)
    with torch.inference_mode():
        pred = model(**inputs).predicted_depth
    d = torch.nn.functional.interpolate(pred[:, None], size=(img.height, img.width), mode="bicubic", align_corners=False)[0, 0]
    d = d.float().cpu().numpy()
    lo, hi = np.percentile(d, [1, 99.5])
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)


def estimate_raw(img: Image.Image, size: str = "small") -> np.ndarray:
    """The model's own relative inverse depth (larger = nearer), at the image's resolution and NOT normalised: the
    scale differs from frame to frame, which is what engine/world_depth.py aligns for a film."""
    proc, model, dev = _load(size)
    import torch
    inputs = proc(images=img.convert("RGB"), return_tensors="pt").to(dev)
    with torch.inference_mode():
        pred = model(**inputs).predicted_depth
    d = torch.nn.functional.interpolate(pred[:, None], size=(img.height, img.width), mode="bicubic", align_corners=False)[0, 0]
    return d.float().cpu().numpy()


_load.cache_clear = _load_size.cache_clear     # type: ignore[attr-defined]
