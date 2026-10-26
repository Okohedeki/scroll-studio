"""Optional: an image embedding (OpenCLIP ViT-H/14, LAION-2B) of the film's sampled frames, so style drift can also be
measured as a distance in embedding space. Local only, and only when its weights are already in the Hugging Face cache:
nothing is downloaded (the engine fails with the file name instead). CPU is fine: about a second a frame.

    pip install open_clip_torch        weights: laion/CLIP-ViT-H-14-laion2B-s32B-b79K (open_clip_pytorch_model.bin, 3.9 GB)
"""
from __future__ import annotations

import os
from typing import Callable

import cv2
import numpy as np

from . import analyze as A

MODEL, PRETRAINED = "ViT-H-14", "laion2b_s32b_b79k"
JND = 0.12                      # embedding cosine distance that counts as one noticeable step (set on the test page, see ENGINE.md)
                                # against the beat's own start, and only while the picture hardly moves: a push, a new
                                # framing or a different person in shot moves an embedding as far as a new style does
EVERY = 2                       # embed every 2nd sample (two frames a second)


class EmbedUnavailable(RuntimeError):
    pass


def load():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")           # never download from here
    try:
        import open_clip
        import torch
    except ImportError as e:
        raise EmbedUnavailable("--embed needs open_clip_torch (pip install open_clip_torch)") from e
    try:
        model, _, pre = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED)
    except Exception as e:
        raise EmbedUnavailable(f"--embed needs the OpenCLIP weights laion/CLIP-ViT-H-14-laion2B-s32B-b79K "
                               f"(open_clip_pytorch_model.bin, 3.9 GB) in the Hugging Face cache; not found ({type(e).__name__}). "
                               f"Nothing is downloaded automatically.") from e
    model.eval()
    return model, pre, torch


def embed_samples(sc: A.Scan, spans, fade: float, log: Callable[[str], None] = print) -> dict | None:
    try:
        model, pre, torch = load()
    except EmbedUnavailable as e:
        log(f"  embedding skipped: {e}")
        return None
    from PIL import Image
    ks = sorted(sc.samples)[::EVERY]
    want = set(ks)
    cap = A.open_film(sc.path)
    vecs = {}
    batch, idx = [], []
    i = 0
    with torch.no_grad():
        def flush():
            if not batch:
                return
            e = model.encode_image(torch.stack(batch)).float()
            e = e / e.norm(dim=-1, keepdim=True)
            for k, v in zip(idx, e.numpy()):
                vecs[k] = v
            batch.clear(); idx.clear()
        while True:
            ok, f = cap.read()
            if not ok:
                break
            if i in want:
                batch.append(pre(Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))))
                idx.append(i)
                if len(batch) >= 8:
                    flush()
            i += 1
        flush()
    cap.release()
    refs = {}                      # every beat's own first second: drift is judged against where the shot started
    for i, sp in enumerate(spans):
        lo = sp.start + (fade if i > 0 else 0.0)
        ks_b = [k for k in ks if lo <= k / sc.fps < lo + 1.0] or [min(ks, key=lambda k: abs(k / sc.fps - lo))]
        v = np.mean([vecs[k] for k in ks_b], 0)
        refs[sp.id] = v / np.linalg.norm(v)
    return {"frame": vecs, "beat_ref": refs, "jnd": JND}
