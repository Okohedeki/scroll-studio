"""Critics for product stills: each scores a candidate 0-1 (higher is better), with no GPU and no network.

  fidelity   how little the product changed inside its mask after blending (a composite scores 1)
  framing    the product's share of the frame is right for the shot, and it is not cut off where it shouldn't be
  contrast   the product stands apart from what is right around it
  novelty    distance from the other candidates, on a small colour-and-edge descriptor (the shortlist uses it)
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

# the product's share of the frame each shot aims for (low, high)
SHARE = {"packshot": (0.12, 0.45), "lifestyle": (0.05, 0.30), "detail": (0.35, 0.95)}


def _arr(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGB"), np.float32) / 255


def product_change(before: Image.Image, after: Image.Image, mask: Image.Image) -> float:
    """Mean colour change inside the product's mask, 0 (untouched) to 1."""
    m = np.asarray(mask, np.float32) / 255
    if m.sum() < 1:
        return 0.0
    diff = np.abs(_arr(before) - _arr(after)).mean(axis=2)
    return float((diff * m).sum() / m.sum())


def fidelity(change: float, limit: float) -> float:
    return float(np.clip(1 - change / max(limit, 1e-6), 0, 1))


def framing(mask: Image.Image, shot: str) -> float:
    m = np.asarray(mask) > 127
    share = float(m.mean())
    lo, hi = SHARE[shot]
    score = 1.0 if lo <= share <= hi else max(0.0, 1 - min(abs(share - lo), abs(share - hi)) / max(lo, 0.05))
    if shot != "detail":             # only a detail may run off the frame
        edges = m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any()
        score *= 0.4 if edges else 1.0
    return round(float(score), 3)


def contrast(image: Image.Image, mask: Image.Image) -> float:
    """Luminance difference between the product's edge and a ring just outside it."""
    lum = np.asarray(image.convert("L"), np.float32) / 255
    inner = np.asarray(mask.filter(ImageFilter.MinFilter(7)), np.float32) / 255 > 0.5
    outer_band = (np.asarray(mask.filter(ImageFilter.MaxFilter(15)), np.float32) / 255 > 0.5) & ~(np.asarray(mask) > 127)
    edge = (np.asarray(mask) > 127) & ~inner
    if edge.sum() < 10 or outer_band.sum() < 10:
        return 0.5
    d = abs(float(lum[edge].mean()) - float(lum[outer_band].mean()))
    return round(float(np.clip(d / 0.35, 0, 1)), 3)


def descriptor(image: Image.Image) -> np.ndarray:
    """A small vector for telling candidates apart: an 8x8 colour thumbnail and an 8-bin edge orientation histogram."""
    thumb = np.asarray(image.convert("RGB").resize((8, 8), Image.BOX), np.float32).reshape(-1) / 255
    g = np.asarray(image.convert("L").resize((96, 96), Image.BILINEAR), np.float32) / 255
    gy, gx = np.gradient(g)
    mag, ang = np.hypot(gx, gy), (np.arctan2(gy, gx) % np.pi)
    hist, _ = np.histogram(ang, bins=8, range=(0, np.pi), weights=mag)
    hist = hist / (hist.sum() + 1e-6)
    return np.concatenate([thumb, hist * 4]).astype(np.float32)


def distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / np.sqrt(len(a)))


def score(fid: float, fra: float, con: float) -> float:
    """One number to rank by: fidelity gates, framing and contrast weigh in."""
    return round(fid * (0.6 * fra + 0.4 * con), 4)
