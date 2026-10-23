"""region: let an image edit change only part of the picture.

A plain Qwen-Image-Edit pass redraws everything a little: the whole frame drifts, and two versions of the same frame
shimmer when one dissolves into the other. With `edit.region` the edit is confined to a region of the SOURCE image and
the rest of the result is the source itself, byte for byte. In order:

  find     the region's prompt -> boxes on the source (Florence-2, through ComfyUI), or the spec's `box` / `points`;
           SAM 2.1 (image mode: a one-frame video through Scroll Studio's own SSRevealTrack node, so no new ComfyUI
           node is needed) cuts the thing out; soft mask at the source's resolution. Cached by the source's content and
           what names the region (`region_<digest>.png`, plus the boxes drawn on the source for review).
  shape    `grow` dilates it (pixels of the source), `feather` softens its edge; `invert` swaps it for everything else.
           The 8-bit result IS the compositing weight, saved as `edit_<digest>.mask.png` beside the edit.
  edit     Qwen-Image-Edit as always, but on a padded CROP around the region (`scope: crop`, the default): the editor
           scales its input to a fixed working size (~1.6 megapixels), so a small region in a big picture is seen up to
           several times larger than a whole-image pass would show it, and has room for real detail (rich shoes, a
           hand). `scope: image` (and always with `invert`) edits the whole picture instead.
  composite  result x mask + source x (1 - mask), integer arithmetic at the source's own size: where the mask is 0 the
           output pixel is the source pixel, exactly; where it is 255 it is the edit's.

Matching the colour and tone of the edit to its surroundings at the seam is the edit's own job (the instruction); the
feather only hides the join.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np

from .project import BuildError, file_key
from .spec import EditRegion

if TYPE_CHECKING:
    from PIL import Image

VERSION = 1                 # bump when a region would come out differently for the same inputs
WORK_MAX = 2048             # the long side SAM 2.1 and Florence-2 are shown (both resize internally anyway)
MIN_CROP = 448              # the smallest crop the editor is given on either axis: it needs surroundings to match
MAX_CROP_ASPECT = 2.4       # a sliver of a region is given a squarer crop than its own shape


# ---------------------------------------------------------------- keys

def find_spec(region: EditRegion) -> dict:
    """What names the region on the source image (everything but how it is shaped and what edits it)."""
    d = region.model_dump(mode="json")
    return {k: d[k] for k in ("prompt", "points", "negative_points", "box", "pick", "within")}


def edit_key(region: EditRegion) -> list:
    """The part of an edit's cache key that the region adds (only ever present when the edit has a region)."""
    return ["region", VERSION, region.model_dump(mode="json")]


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- finding the region on the source

def seg_graph(image_name: str, prompts: list[dict], tracker: str, prefix: str) -> dict:
    """SAM 2.1 on one image: the video predictor over a one-frame video (SSRevealTrack), so boxes and points both work."""
    from .reveal import TRACKERS
    return {
        "img": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "sam": {"class_type": "DownloadAndLoadSAM2Model", "inputs": {"model": TRACKERS[tracker], "segmentor": "video",
                                                                       "device": "cuda", "precision": "fp16"}},
        "tr": {"class_type": "SSRevealTrack", "inputs": {"sam2_model": ["sam", 0], "images": ["img", 0], "frame_index": 0,
                                                          "prompts": json.dumps(prompts), "start": 0, "end": -1}},
        "mask": {"class_type": "MaskToImage", "inputs": {"mask": ["tr", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["mask", 0], "filename_prefix": prefix}},
    }


def find(project, src: Path, region: EditRegion, log=print) -> Path:
    """The soft mask (L, 0-255, the source's size) of the thing the region names on `src`, found once and cached."""
    from PIL import Image, ImageOps
    spec = find_spec(region)
    digest = _digest([file_key(src), spec, "large", VERSION])
    gdir = project.build / "_generated"
    out = gdir / f"region_{digest}.png"
    if out.exists():
        return out
    from .backends import comfy
    from .reveal import _draw_boxes, _need_nodes, find_boxes, region_prompts
    _need_nodes(log)
    gdir.mkdir(parents=True, exist_ok=True)
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")      # as ComfyUI's LoadImage sees it
    work = im
    if max(im.size) > WORK_MAX:
        s = WORK_MAX / max(im.size)
        work = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    wpng = gdir / f"_region_{digest}_work.png"
    work.save(wpng)
    try:
        found: list = []
        if region.box:
            found = [list(region.box)]
        elif region.prompt:
            log(f"  finding the region (Florence-2): {region.prompt[:80]}")
            found, _all, _owners = find_boxes(wpng, region.prompt, region.pick, region.within, log)
            if not found:
                raise BuildError(f"edit region: nothing matching \"{region.prompt}\" on the source image. Reword the prompt, "
                                 "or give `box` / `points`.")
            _draw_boxes(wpng, found, gdir / f"region_{digest}.boxes.jpg")
        prompts = region_prompts(region, found)
        log(f"  cutting the region out (SAM 2.1, {len(prompts)} object(s))")
        name = comfy.upload(str(wpng))
        images = comfy.run(seg_graph(name, prompts, "large", f"studio/region_{digest}"), poll=2)
        got = Path(comfy.fetch(images, str(gdir / f"_region_{digest}")))
        try:
            files = sorted(got.glob("*.png"))
            if not files:
                raise BuildError("the segmentation returned no mask")
            m = Image.open(files[0]).convert("L")
        finally:
            import shutil
            shutil.rmtree(got, ignore_errors=True)
    finally:
        wpng.unlink(missing_ok=True)
    if m.size != im.size:
        m = m.resize(im.size, Image.BILINEAR)
    arr = np.asarray(m)
    if (arr > 127).mean() < 2e-5:
        what = f' "{region.prompt}"' if region.prompt else ""
        raise BuildError(f"edit region{what}: the mask came out empty. Give `points` on the thing, or a `box` around it.")
    m.save(out)
    return out


# ---------------------------------------------------------------- shaping and compositing (pure numpy/cv2)

def despeckle(m: np.ndarray, share: float = 0.01) -> np.ndarray:
    """Drop the specks a segmentation leaves far from the thing: connected parts smaller than `share` of the biggest
    part (two shoes stay, a stray dot goes; a speck would otherwise stretch the crop the editor is shown)."""
    import cv2
    n, lab, stats, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), connectivity=8)
    if n <= 2:
        return m
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = np.concatenate([[False], areas >= max(16, share * areas.max())])
    return np.where(keep[lab], m, 0).astype(np.uint8)


def shape(raw: np.ndarray, grow: int, feather: int, invert: bool = False) -> np.ndarray:
    """A finished mask (uint8, 0 = keep the source, 255 = take the edit) from the raw soft mask (uint8, SAM's output):
    thresholded, despeckled, grown by `grow` pixels (negative shrinks), blurred so the edge fades over about `feather` pixels, then
    inverted if asked. The edge sits where the grown region ends (half weight there)."""
    import cv2
    m = despeckle((np.asarray(raw) > 127).astype(np.uint8) * 255)
    if grow:
        r = max(1, int(round(abs(grow))))
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        m = cv2.dilate(m, k) if grow > 0 else cv2.erode(m, k)
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather / 2)
    if invert:
        m = 255 - m
    return m


def composite(src: np.ndarray, edit: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """src, edit: uint8 HxWxC of one size; mask: uint8 HxW. Integer blend: mask 0 gives the source pixel exactly,
    mask 255 the edit's."""
    w = mask.astype(np.uint16)[..., None]
    out = (src.astype(np.uint16) * (255 - w) + edit.astype(np.uint16) * w + 127) // 255
    out = out.astype(np.uint8)
    return np.where(w == 0, src, out)


def crop_box(mask: np.ndarray, context: float) -> tuple[int, int, int, int]:
    """The crop (x0, y0, x1, y1) the editor is shown: the mask's extent plus `context` x its size on every side, at least
    MIN_CROP across (as far as the picture goes), not much wider than tall or the reverse, inside the picture."""
    H, W = mask.shape
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise BuildError("edit region: the mask is empty")
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    bw, bh = x1 - x0, y1 - y0
    cx0, cx1 = x0 - context * bw, x1 + context * bw
    cy0, cy1 = y0 - context * bh, y1 + context * bh

    def widen(lo, hi, want, limit):
        if hi - lo < want:
            mid = (lo + hi) / 2
            lo, hi = mid - want / 2, mid + want / 2
        return lo, hi

    cx0, cx1 = widen(cx0, cx1, min(MIN_CROP, W), W)
    cy0, cy1 = widen(cy0, cy1, min(MIN_CROP, H), H)
    w, h = cx1 - cx0, cy1 - cy0
    if w > h * MAX_CROP_ASPECT:
        cy0, cy1 = widen(cy0, cy1, min(w / MAX_CROP_ASPECT, H), H)
    elif h > w * MAX_CROP_ASPECT:
        cx0, cx1 = widen(cx0, cx1, min(h / MAX_CROP_ASPECT, W), W)

    def clamp(lo, hi, limit):
        lo, hi = int(np.floor(lo)), int(np.ceil(hi))
        if hi - lo >= limit:
            return 0, limit
        if lo < 0:
            lo, hi = 0, hi - lo
        if hi > limit:
            lo, hi = lo - (hi - limit), limit
        return max(0, lo), min(limit, hi)

    (a, b), (c, d) = clamp(cx0, cx1, W), clamp(cy0, cy1, H)
    return a, c, b, d


def outline(mask: np.ndarray, color=(255, 40, 80)) -> "Image.Image":
    """An RGBA overlay for review: the mask's edge (where it passes half weight) as a line, a faint tint inside."""
    import cv2
    from PIL import Image
    H, W = mask.shape
    solid = (mask >= 128).astype(np.uint8)
    cnts, _ = cv2.findContours(solid, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    layer = np.zeros((H, W, 4), dtype=np.uint8)
    layer[..., :3] = color
    layer[..., 3] = (np.asarray(mask).astype(np.float32) * (46 / 255)).astype(np.uint8)
    line = np.zeros((H, W), dtype=np.uint8)
    cv2.drawContours(line, cnts, -1, 255, max(2, W // 640), cv2.LINE_AA)
    layer[..., 3] = np.maximum(layer[..., 3], line)
    return Image.fromarray(layer, "RGBA")


def sidecars(edit_png: Path) -> tuple[Path, Path]:
    """The mask and the review outline kept beside an edit: edit_<digest>.mask.png, edit_<digest>.outline.png."""
    return edit_png.with_suffix(".mask.png"), edit_png.with_suffix(".outline.png")


def copy_sidecars(src_img: Path, dst_img: Path) -> None:
    """Keep an edit's mask and outline with a copy of the image (variants, picking an old variant back)."""
    import shutil
    for a, b in zip(sidecars(src_img), sidecars(dst_img)):
        if a.exists():
            shutil.copy2(a, b)


def outline_of(image_path: Path) -> Optional[Path]:
    """The review outline kept beside an edited image, if it has one."""
    p = sidecars(image_path)[1]
    return p if p.exists() else None


# ---------------------------------------------------------------- the edit

def apply(project, src: Path, region: EditRegion, out: Path, run_editor: Callable[[Path], Path], log=print) -> Path:
    """Write the region edit of `src` to `out`. `run_editor(png)` edits one image with the instruction (Qwen-Image-Edit)
    and returns the path of its result at any size; it is given a crop of `src` or `src` itself."""
    from PIL import Image, ImageOps
    raw_path = find(project, src, region, log)
    raw = np.asarray(Image.open(raw_path).convert("L"))
    mask = shape(raw, region.grow, region.feather, region.invert)
    if not mask.any():
        raise BuildError("edit region: nothing is left of the mask after `grow` and `feather`")
    if mask.min() == 255 and not region.invert:
        log("  note: the region covers the whole picture; the edit replaces all of it")
    srcim = ImageOps.exif_transpose(Image.open(src))
    has_alpha = srcim.mode in ("RGBA", "LA") or (srcim.mode == "P" and "transparency" in srcim.info)
    base = srcim.convert("RGBA" if has_alpha else "RGB")
    arr = np.asarray(base)
    H, W = mask.shape
    if (W, H) != base.size:
        raise BuildError("edit region: the mask and the source differ in size")
    gdir = out.parent
    if region.scope == "crop" and not region.invert:
        x0, y0, x1, y1 = crop_box(mask, region.context)
    else:
        x0, y0, x1, y1 = 0, 0, W, H
    crop_png = src
    if (x0, y0, x1, y1) != (0, 0, W, H):
        crop_png = gdir / f"_{out.stem}_crop.png"
        base.crop((x0, y0, x1, y1)).convert("RGB").save(crop_png)
        log(f"  editing a {x1 - x0}x{y1 - y0} crop around the region (of {W}x{H})")
    elif has_alpha:
        crop_png = gdir / f"_{out.stem}_rgb.png"
        base.convert("RGB").save(crop_png)
    try:
        res = Image.open(run_editor(crop_png)).convert("RGB")
    finally:
        if crop_png != src:
            crop_png.unlink(missing_ok=True)
    cw, ch = x1 - x0, y1 - y0
    if res.size != (cw, ch):
        res = res.resize((cw, ch), Image.LANCZOS)
    c = arr.shape[2]
    edited = arr.copy()
    edited[y0:y1, x0:x1, :3] = np.asarray(res)
    done = composite(arr, edited, mask)
    mpath, opath = sidecars(out)
    Image.fromarray(mask, "L").save(mpath)
    outline(mask).save(opath)
    tmp = out.with_name(out.stem + ".tmp.png")
    Image.fromarray(done, "RGBA" if c == 4 else "RGB").save(tmp)
    tmp.replace(out)
    return out
