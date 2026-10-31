"""The product cut out of its photo, as an RGBA image cropped to the product.

A PNG with transparency is used as it is. Otherwise rembg cuts it out when it is installed (the `ml` extra); without it,
a photo on a plain backdrop (a studio shot: the corners agree) is keyed by its distance from the backdrop colour. A
busy photo with no rembg is refused with what to do instead.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


class CutoutError(ValueError):
    pass


def _has_alpha(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA") and int(np.asarray(im.getchannel("A")).min()) < 250


def _crop(im: Image.Image, pad: int = 2) -> Image.Image:
    a = np.asarray(im.getchannel("A"))
    ys, xs = np.nonzero(a > 8)
    if len(xs) == 0:
        raise CutoutError("nothing was left after cutting out the product: check the photo")
    x0, x1 = max(0, xs.min() - pad), min(im.width, xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(im.height, ys.max() + 1 + pad)
    return im.crop((int(x0), int(y0), int(x1), int(y1)))


def key_plain_backdrop(im: Image.Image, spread_limit: float = 18.0) -> Image.Image:
    """Cut a product off a plain backdrop: the corners' median colour is the backdrop, pixels far from it are kept.
    Raises CutoutError when the corners disagree (not a plain backdrop)."""
    rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
    h, w = rgb.shape[:2]
    k = max(4, min(h, w) // 20)
    corners = np.concatenate([rgb[:k, :k].reshape(-1, 3), rgb[:k, -k:].reshape(-1, 3),
                              rgb[-k:, :k].reshape(-1, 3), rgb[-k:, -k:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    spread = float(np.median(np.linalg.norm(corners - bg, axis=1)))
    if spread > spread_limit:
        raise CutoutError("the photo is not on a plain backdrop, so it can't be cut out here: give a cut-out PNG "
                          "(transparent background) or install the ml extra (rembg)")
    dist = np.linalg.norm(rgb - bg, axis=2)
    lo, hi = spread * 2 + 10, spread * 2 + 38
    alpha = np.clip((dist - lo) / (hi - lo), 0, 1)
    mask = Image.fromarray((alpha * 255).astype(np.uint8))
    mask = mask.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    mask = mask.filter(ImageFilter.GaussianBlur(0.8))
    out = im.convert("RGB").convert("RGBA")
    out.putalpha(mask)
    return out


def cutout(photo: Path) -> Image.Image:
    """The product as RGBA, cropped to it."""
    im = Image.open(photo)
    im.load()
    if _has_alpha(im):
        return _crop(im.convert("RGBA"))
    try:
        from rembg import remove
    except ImportError:
        return _crop(key_plain_backdrop(im))
    return _crop(remove(im.convert("RGB")).convert("RGBA"))
