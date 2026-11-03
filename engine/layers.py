"""Layered depth for frozen moments (`freeze.layers`): planes instead of one warped sheet.

A frozen frame warped by one depth map smears at every depth jump: the foreground's edge drags the background with it
(a halo), the background is sometimes sampled from the person (a double edge), and nothing can show what is behind a
person because the picture does not contain it. Here the frame is cut into planes, back to front:

  background plate   the frame with the subjects painted out (Qwen-Image-Edit through the subjects' mask, pixel-exact
                     outside the hole), its depth with the holes filled from the surroundings
  subject planes     one per person or group of people at a similar depth: a soft alpha (SAM 2.1 inside the box Florence-2
                     found, refined to the picture's own edge with the guided filter), a smooth depth of its own (no jump
                     inside a plane, so no internal stretch), and the picture's pixels with the plate's contribution
                     removed at the edge (foreground colour estimation, so no fringe of the old background)
  render             the planes are marched and sampled one after the other, each with its own depth, and composited over
                     each other: at rest the result is the frame itself; when the camera moves, a plane slides over the
                     plate instead of smearing, and the plate shows through where the person was.

The planes are cut from the same picture at render time (not separate images), so with deep zoom (`freeze.detail`) every
tile carries its own alpha, refined at the tile's resolution, and the plate continues down the pyramid: a layered deep
zoom costs one extra tile attribute per plane instead of one pyramid per plane, and every level agrees by construction.
See docs/ENGINE.md, "Layered depth".
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .project import BuildError

VERSION = 1
SEG_VERSION = 2             # bump when the subjects of a frame would be cut out differently

PLATE_INSTRUCTION = ("Remove every person from this picture. Fill the space where they stood with the empty street, "
                     "ground, fog and buildings continuing naturally behind them, in exactly the same drawing style, "
                     "line weight and tones. Do not add anything new and do not change anything else.")


# ---------------------------------------------------------------- pure maths (cv2 / numpy)

def push_pull(img: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Fill the invalid part of `img` (float H x W or H x W x C) from the valid part, smoothly at every scale (push-pull):
    where `valid` (0-1) is 1 the image is unchanged, elsewhere it is the surroundings continued."""
    import cv2
    a = img.astype(np.float32)
    v = valid.astype(np.float32)
    if a.ndim == 2:
        a = a[..., None]
    levels = [(a * v[..., None], v)]
    while min(levels[-1][1].shape) > 6:
        n, d = levels[-1]
        n2 = cv2.pyrDown(n)
        d2 = cv2.pyrDown(d)
        levels.append((n2.reshape(n2.shape[0], n2.shape[1], -1), d2))
    n, d = levels[-1]
    cur = n / np.maximum(d, 1e-6)[..., None]
    if float(d.max()) < 1e-6:
        return img.astype(np.float32)               # nothing to fill from
    for n, d in reversed(levels[:-1]):
        h, w = d.shape
        up = cv2.resize(cur, (w, h), interpolation=cv2.INTER_LINEAR).reshape(h, w, -1)
        known = n / np.maximum(d, 1e-6)[..., None]
        wgt = np.clip(d * 1.5, 0, 1)[..., None]
        cur = known * wgt + up * (1 - wgt)
    out = cur.reshape(a.shape)
    out = a * v[..., None] + out * (1 - v[..., None])
    return out[..., 0] if img.ndim == 2 else out


def soft_alpha(mask: np.ndarray, feather: float) -> np.ndarray:
    """A float 0-1 alpha from a mask (any 0-1 or 0-255 map): thresholded, then softened over about `feather` pixels."""
    import cv2
    m = np.asarray(mask, dtype=np.float32)
    if m.max() > 1.5:
        m = m / 255.0
    m = (m > 0.5).astype(np.float32)
    if feather > 0.2:
        m = cv2.GaussianBlur(m, (0, 0), feather / 2)
    return m


def grow_mask(m: np.ndarray, px: int) -> np.ndarray:
    import cv2
    if px <= 0:
        return m.astype(np.float32)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.dilate((m > 0.5).astype(np.uint8) * 255, k).astype(np.float32) / 255.0


def plane_depth(depth: np.ndarray, masks: list[np.ndarray]) -> np.ndarray:
    """A subject plane's depth: every subject is a card, a plane of its own, not the scene's depth smoothed. A monocular depth
    map has steps and creases inside a person (a bright coat against a dark one reads as two depths), and a plane that follows
    them tears the person apart the moment the camera moves. So each subject takes the median depth of its pixels, with
    the gentle slope down its height that a person standing on the ground has (a line fit in y, clamped), and the card is
    continued smoothly outside the subjects (push-pull), so the march has something sensible past the edge (the alpha cuts the
    colour there). `masks`: float 0-1 maps of the subjects of the plane."""
    full = np.zeros(depth.shape, np.float32)
    valid = np.zeros(depth.shape, np.float32)
    H, W = depth.shape
    for m in masks:
        inside = m > 0.5
        if inside.sum() < 4:
            continue
        ys, xs = np.nonzero(inside)
        d = depth[inside].astype(np.float64)
        lo, hi = np.percentile(d, [10, 90])
        keep = (d >= lo) & (d <= hi)
        y = ys[keep].astype(np.float64)
        if keep.sum() > 8 and y.std() > 2:
            slope, icpt = np.polyfit(y, d[keep], 1)
            slope = float(np.clip(slope, -0.4 / H, 0.4 / H))                   # at most 0.4 of the depth range over the frame's height
            icpt = float(np.median(d[keep] - slope * y))
        else:
            slope, icpt = 0.0, float(np.median(d))
        full[inside] = (icpt + slope * ys).astype(np.float32)
        valid[inside] = 1.0
    if valid.sum() < 4:
        return depth.astype(np.float32)
    return push_pull(full, valid)


def background_depth(depth: np.ndarray, hole: np.ndarray) -> np.ndarray:
    """The scene depth with the subjects' hole filled from the surroundings (what the depth behind them would be)."""
    return push_pull(depth.astype(np.float32), 1.0 - np.clip(hole, 0, 1))


def refine_alpha(parent_up: np.ndarray, rgb: np.ndarray, radius: int = 0, eps: float = 4e-4) -> np.ndarray:
    """A plane's alpha at a tile's resolution: the parent's alpha enlarged (float 0-1, `parent_up`), snapped to the edges
    of the tile's own picture with the guided filter, with a little gain so a half-covered edge pixel reads as an edge."""
    import cv2
    from .freeze import guided_filter
    H, W = rgb.shape[:2]
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    r = radius or max(3, W // 400)
    a = guided_filter(g, np.clip(parent_up.astype(np.float32), 0, 1), r, eps)
    return np.clip((a - 0.5) * 1.25 + 0.5, 0, 1)


def estimate_foreground(rgb: np.ndarray, alpha: np.ndarray, plate: np.ndarray) -> np.ndarray:
    """The subject's own colour at its edge: the picture's pixel is alpha * foreground + (1 - alpha) * plate, so
    foreground = (pixel - (1 - alpha) * plate) / alpha where alpha is solid enough to divide by, the pixel itself elsewhere.
    Composited over the plate again it gives the picture back exactly; over anything else it has no fringe of the old
    background. (float arrays, 0-255)"""
    a = alpha[..., None]
    fg = (rgb - (1 - a) * plate) / np.maximum(a, 0.08)
    fg = np.clip(fg, 0, 255)
    w = np.clip((alpha - 0.04) / 0.2, 0, 1)[..., None]
    return rgb * (1 - w) + fg * w


def group_planes(items: list[tuple[str, float]], max_planes: int) -> list[list[int]]:
    """Group subjects (id, depth) into at most `max_planes` planes of similar depth: sorted by depth, split at the
    largest gaps. Returns lists of indices into `items`, farthest plane first."""
    order = sorted(range(len(items)), key=lambda i: items[i][1])
    if len(order) <= max_planes:
        return [[i] for i in order]
    gaps = sorted(range(1, len(order)), key=lambda k: -(items[order[k]][1] - items[order[k - 1]][1]))[:max_planes - 1]
    cuts = sorted(gaps)
    out, start = [], 0
    for c in [*cuts, len(order)]:
        out.append(order[start:c])
        start = c
    return out


# ---------------------------------------------------------------- finding the subjects (Florence-2 + SAM 2.1)

@dataclass
class Subject:
    id: str
    mask: np.ndarray                    # float 0-1, the frame's size
    layer: int = -1                     # which `subjects` entry named it (-1: auto)


def _segment_many(png: Path, groups: list[list[dict]], work: Path) -> list[np.ndarray]:
    """SAM 2.1 on one image, one soft mask (float 0-1) per group of prompts (the union of the objects its prompts name), all
    in ONE ComfyUI job: the model loads once, and the job is not interleaved with anybody else's."""
    import json as _json
    from PIL import Image
    from .backends import comfy
    from .reveal import TRACKERS
    name = comfy.upload(str(png))
    g: dict = {"img": {"class_type": "LoadImage", "inputs": {"image": name}},
               "sam": {"class_type": "DownloadAndLoadSAM2Model", "inputs": {"model": TRACKERS["large"], "segmentor": "video",
                                                                              "device": "cuda", "precision": "fp16"}}}
    for i, prompts in enumerate(groups):
        g[f"tr{i}"] = {"class_type": "SSRevealTrack", "inputs": {"sam2_model": ["sam", 0], "images": ["img", 0], "frame_index": 0,
                                                                  "prompts": _json.dumps(prompts), "start": 0, "end": -1}}
        g[f"m{i}"] = {"class_type": "MaskToImage", "inputs": {"mask": [f"tr{i}", 0]}}
        g[f"save{i}"] = {"class_type": "SaveImage", "inputs": {"images": [f"m{i}", 0], "filename_prefix": f"studio/layers_seg{i}"}}
    outs = comfy.run_outputs(g, poll=3)
    masks = []
    for i in range(len(groups)):
        got = Path(comfy.fetch(outs[f"save{i}"]["images"][:1], str(work / f"_seg_{i}")))
        try:
            files = sorted(got.glob("*.png"))
            if not files:
                raise BuildError("layers: the segmentation returned no mask")
            masks.append(np.asarray(Image.open(files[0]).convert("L"), dtype=np.float32) / 255.0)
        finally:
            shutil.rmtree(got, ignore_errors=True)
    return masks


def _spine(box) -> dict:
    """Points down the middle of a subject's box (a third, a half and four fifths of the way down) for SAM to take along with
    the box: a box alone lets a person who is nearly the colour of the fog be cut out in part (the rest then stays in the
    background plane and tears off when it moves); points on the body make it the whole person."""
    x0, y0, x1, y1 = box
    cx, h = (x0 + x1) / 2, y1 - y0
    return {"points": [[cx, y0 + 0.3 * h], [cx, y0 + 0.5 * h], [cx, y0 + 0.78 * h]], "labels": [1, 1, 1]}


def find_subjects(png: Path, layers, work: Path, log: Callable) -> list[Subject]:
    """The subjects of a frame, one mask each. `layers.subjects == "auto"`: every person Florence-2 finds; or the named
    subjects (a prompt can match several things: they share a plane, the plane's mask is their union)."""
    from .reveal import _need_nodes, find_boxes
    from .spec import FreezeLayer
    _need_nodes(log)
    specs = [FreezeLayer(prompt="people")] if layers.subjects == "auto" else list(layers.subjects)
    names: list[tuple[str, int]] = []
    groups: list[list[dict]] = []
    for li, sp in enumerate(specs):
        boxes: list[list[float]] = []
        if sp.box:
            boxes = [list(sp.box)]
        elif sp.prompt:
            log(f"  layers: finding {sp.prompt!r} (Florence-2)")
            boxes, _all, _o = find_boxes(png, sp.prompt, "all", None, log)
            if layers.subjects == "auto":
                boxes = [b for b in boxes if (b[2] - b[0]) * (b[3] - b[1]) < 0.4]
        items: list[dict] = [{"box": b, **_spine(b)} for b in boxes]
        for p in sp.points:
            items.append({"points": [list(p)], "labels": [1]})
        if not items:
            raise BuildError(f"layers: nothing found for {sp.prompt or sp.box or sp.points}: reword it, or give a `box` / `points`")
        if layers.subjects == "auto":
            for k, it in enumerate(items):          # each person is cut out alone: planes group them by depth afterwards
                names.append((f"person{len(names) + 1}", li))
                groups.append([it])
        else:
            names.append((sp.id or f"layer{li + 1}", li))
            groups.append(items)
    log(f"  layers: cutting out {len(groups)} subject(s) (SAM 2.1)")
    masks = _segment_many(png, groups, work)
    out = [Subject(n, m, li) for (n, li), m in zip(names, masks)]
    out = [s for s in out if (s.mask > 0.5).mean() > 2e-5]
    if not out:
        raise BuildError("layers: no subject was found on the frame")
    return out


# ---------------------------------------------------------------- the background plate

def harmonize(plate: np.ndarray, frozen: np.ndarray, hole: np.ndarray, band: int = 6) -> np.ndarray:
    """Match the painted-out plate's tone to the frame at the edge of the hole. An image editor drifts a little in tone, and
    the hole's edge then shows as a pale or dark ring around every subject the moment it moves. The mismatch along the inside
    of the hole's edge (the frame continued smoothly into the hole, against the plate) is spread smoothly over the hole
    (push-pull), and subtracted: the plate then continues its surroundings at the edge and keeps its own content inside."""
    import cv2
    core = (hole > 0.5).astype(np.uint8)
    if not core.any() or core.all():
        return plate
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
    inner = core.astype(bool) & ~cv2.erode(core, k).astype(bool)
    outside = (~cv2.dilate(core, k).astype(bool)).astype(np.float32)
    target = push_pull(frozen.astype(np.float32), outside)                      # the frame, continued into the hole
    smooth_plate = cv2.GaussianBlur(plate.astype(np.float32), (0, 0), 3)
    mismatch = target - smooth_plate
    d = push_pull(mismatch, inner.astype(np.float32))
    out = plate.astype(np.float32) + d * cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 1.0)[..., None]
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def paint_out(frozen: np.ndarray, instruction: str, seed: int, work: Path, log: Callable, cache: Optional[tuple[Path, str]] = None
              ) -> Optional[np.ndarray]:
    """Qwen-Image-Edit over the whole frame with `instruction` (uint8, the frame's size), or None when ComfyUI is not running.
    The raw edit does not depend on the subjects' masks (they only decide where it is used), so it is kept
    (`cache` = (path, key)) and changing `grow`, `feather` or `planes` does not ask the editor again."""
    from PIL import Image
    from .backends import comfy
    if cache is not None:
        path, key = cache
        stamp = path.with_name(path.name + ".key")
        if path.exists() and stamp.exists() and stamp.read_text() == key:
            return np.asarray(Image.open(path).convert("RGB"))
    from .router import edit_on_provider
    src = work / "_plate_in.png"
    Image.fromarray(frozen).save(src)
    routed = work / "_plate_routed.png"
    if edit_on_provider([src], instruction, seed, 20, routed, log=log):
        edited = Image.open(routed).convert("RGB")
        src.unlink(missing_ok=True)
        routed.unlink(missing_ok=True)
        if edited.size != (frozen.shape[1], frozen.shape[0]):
            edited = edited.resize((frozen.shape[1], frozen.shape[0]), Image.LANCZOS)
        out = np.asarray(edited)
        if cache is not None:
            Image.fromarray(out).save(cache[0])
            cache[0].with_name(cache[0].name + ".key").write_text(cache[1])
        return out
    if not comfy.alive():
        src.unlink(missing_ok=True)
        return None
    log("  layers: painting the background behind the subjects (Qwen-Image-Edit)")
    comfy.free()
    names = [comfy.upload(str(src))]
    images = comfy.run(comfy.build_qwen_edit_graph(names, instruction, seed, 20, prefix="studio/layers_plate"), poll=2)
    got = Path(comfy.fetch(images, str(work / "_plate_out")))
    try:
        edited = Image.open(next(got.glob("*.png"))).convert("RGB")
    finally:
        shutil.rmtree(got, ignore_errors=True)
        src.unlink(missing_ok=True)
        comfy.free()
    if edited.size != (frozen.shape[1], frozen.shape[0]):
        edited = edited.resize((frozen.shape[1], frozen.shape[0]), Image.LANCZOS)
    out = np.asarray(edited)
    if cache is not None:
        Image.fromarray(out).save(cache[0])
        cache[0].with_name(cache[0].name + ".key").write_text(cache[1])
    return out


def plate_of(frozen: np.ndarray, hole: np.ndarray, instruction: str, seed: int, work: Path, log: Callable,
             cache: Optional[tuple[Path, str]] = None) -> np.ndarray:
    """The frame with the hole painted out: the editor's picture (`paint_out`) kept only inside the hole
    (`region.composite`: outside it the pixel is the frame's, exactly), through a softened edge, its tone matched to the frame
    at the edge (`harmonize`). Without ComfyUI the hole is filled smoothly from its surroundings (push-pull): a gradient, no
    detail, and a say so in the log."""
    from . import region
    mask8 = np.clip(hole * 255, 0, 255).astype(np.uint8)
    edited = paint_out(frozen, instruction, seed, work, log, cache)
    if edited is None:
        log("  layers: ComfyUI is not running: filling the background behind the subjects smoothly from its surroundings")
        fill = np.clip(push_pull(frozen.astype(np.float32), 1.0 - hole), 0, 255).astype(np.uint8)
        return region.composite(frozen, fill, mask8)
    return harmonize(region.composite(frozen, edited, mask8), frozen, hole)


# ---------------------------------------------------------------- the planes of a frame

@dataclass
class LayerSet:
    """The planes of a frame at the beat's size. `alpha`: P soft maps (farthest plane first), `depth`: P plane depths,
    `hole`: where the subjects were (grown), `plate`: the frame with them painted out (uint8), `bg_depth`: the
    background plane's depth. `ids`: the subjects of each plane."""
    alpha: np.ndarray                     # (P, H, W) float32
    depth: np.ndarray                     # (P, H, W) float32
    hole: np.ndarray                      # (H, W) float32
    plate: np.ndarray                     # (H, W, 3) uint8
    bg_depth: np.ndarray                  # (H, W) float32
    ids: list[list[str]] = field(default_factory=list)
    key: str = ""


def _subjects_cached(png: Path, layers, work: Path, log: Callable, key: str) -> list[Subject]:
    """The subjects of a frame, found once: Florence-2 and SAM 2.1 are not asked again when only the planes' settings change."""
    spec = json.dumps([SEG_VERSION, key, layers.subjects if layers.subjects == "auto" else [s.model_dump(mode="json") for s in layers.subjects]],
                      sort_keys=True)
    k = hashlib.sha1(spec.encode()).hexdigest()[:16]
    f = work / "subjects.npz"
    if f.exists():
        with np.load(f, allow_pickle=False) as z:
            if str(z["key"]) == k:
                return [Subject(str(n), m.astype(np.float32) / 255, int(li)) for n, m, li in zip(z["names"], z["masks"], z["layer"])]
    subs = find_subjects(png, layers, work, log)
    np.savez(work / "_subjects.npz", key=k, names=np.array([s.id for s in subs]), layer=np.array([s.layer for s in subs]),
             masks=np.stack([(s.mask * 255 + 0.5).astype(np.uint8) for s in subs]))
    (work / "_subjects.npz").replace(f)
    return subs


def plate_instruction(layers) -> str:
    """What the editor is asked to remove: every person (auto), or the named subjects."""
    base = PLATE_INSTRUCTION
    if layers.subjects != "auto":
        names = [s.prompt for s in layers.subjects if s.prompt]
        if names:
            base = base.replace("Remove every person from this picture.", "Remove " + ", ".join(names) + " from this picture.")
    return base + (" " + layers.plate.strip() if layers.plate.strip() else "")


def build_planes(frozen: np.ndarray, depth_raw: np.ndarray, layers, seed: int, work: Path, log: Callable,
                 subjects: Optional[list[Subject]] = None, png: Optional[Path] = None, key: str = "") -> LayerSet:
    """Cut `frozen` (uint8, beat size) into planes: find the subjects, group them by depth, paint the plate."""
    H, W = frozen.shape[:2]
    if subjects is None:
        subjects = _subjects_cached(png, layers, work, log, key)
    med = []
    for s in subjects:
        m = s.mask > 0.5
        med.append((s.id, float(np.median(depth_raw[m])) if m.any() else 0.0))
    if layers.subjects == "auto":
        groups = group_planes(med, layers.planes)
    else:
        groups = [[i] for i in sorted(range(len(subjects)), key=lambda i: med[i][1])][: layers.planes]
    log(f"  layers: {len(subjects)} subjects in {len(groups)} planes")
    alphas, depths, ids = [], [], []
    for g in groups:
        union = np.max([subjects[i].mask for i in g], axis=0)
        a = soft_alpha(union, layers.feather)
        alphas.append(a)
        depths.append(plane_depth(depth_raw, [subjects[i].mask for i in g]))
        ids.append([subjects[i].id for i in g])
    hole = np.clip(grow_mask(np.max([(a > 0.02).astype(np.float32) for a in alphas], axis=0), layers.grow), 0, 1)
    import cv2
    hole = cv2.GaussianBlur(hole, (0, 0), max(1.0, layers.feather)) if layers.feather > 0 else hole
    instruction = plate_instruction(layers)
    plate = plate_of(frozen, hole, instruction, seed, work, log,
                     (work / "plate_raw.png", hashlib.sha1(json.dumps([VERSION, key, instruction, seed]).encode()).hexdigest()[:16]))
    return LayerSet(np.stack(alphas).astype(np.float32), np.stack(depths).astype(np.float32), hole.astype(np.float32), plate,
                    background_depth(depth_raw, hole), ids)


# ---------------------------------------------------------------- tiles of a layered pyramid

def tile_layers(parent_alpha: np.ndarray, parent_hole: np.ndarray, parent_bg: np.ndarray, rgb: np.ndarray, box_parent, box_tile,
                resample: Callable) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """What a tile adds for the planes, from its parent's (all over the parent's box, `resample(img, src_box, dst_box)` puts
    them over the tile's): alphas refined at the tile's resolution, the hole, and the background picture: the tile's own
    pixels outside the hole, the parent's plate (enlarged) inside it. Returns (alpha (P,H,W) u8, hole (H,W) u8, bg (H,W,3) u8)."""
    P = parent_alpha.shape[0]
    alpha = np.stack([refine_alpha(resample(parent_alpha[p], box_parent, box_tile), rgb) for p in range(P)])
    hole = np.clip(resample(parent_hole, box_parent, box_tile), 0, 1)
    plate_up = resample(parent_bg.astype(np.float32), box_parent, box_tile)
    h = hole[..., None]
    bg = rgb.astype(np.float32) * (1 - h) + plate_up * h
    return (alpha * 255 + 0.5).astype(np.uint8), (hole * 255 + 0.5).astype(np.uint8), np.clip(bg + 0.5, 0, 255).astype(np.uint8)


def base_background(rgb: np.ndarray, ls: LayerSet) -> np.ndarray:
    """The background plane's picture at the base level's size (`rgb`: the upscaled frame, uint8): the frame's own pixels
    outside the hole, the plate (enlarged) inside it."""
    import cv2
    H, W = rgb.shape[:2]
    plate = cv2.resize(ls.plate, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    hole = cv2.resize(ls.hole, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    return np.clip(rgb.astype(np.float32) * (1 - hole) + plate * hole + 0.5, 0, 255).astype(np.uint8)


def tile_plane_depths(depth_raw: np.ndarray, hole_u8: np.ndarray, parent_plane_depth_up: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(plane depths (P,H,W), background depth (H,W)) of a tile, float32. The subjects are cards: smooth, so a tile's are the
    parent's enlarged. The background's depth is the tile's own raw depth with the hole filled from its surroundings (it has
    real edges: a lamp post, a building)."""
    return parent_plane_depth_up.astype(np.float32), background_depth(depth_raw, hole_u8.astype(np.float32) / 255).astype(np.float32)


def build_cached(bdir: Path, frozen_png: Path, frozen: np.ndarray, depth_raw: np.ndarray, layers, seed: int, key: str,
                 log: Callable) -> LayerSet:
    """The frame's planes, made once and kept under bdir/layers/ (keyed by the frame, its depth and the layers settings)."""
    from PIL import Image
    ldir = bdir / "layers"
    ldir.mkdir(parents=True, exist_ok=True)
    stamp, npz, plate = ldir / "planes.key", ldir / "planes.npz", ldir / "plate.png"
    k = hashlib.sha1(json.dumps([VERSION, key, layers.model_dump(mode="json"), seed], sort_keys=True).encode()).hexdigest()[:16]
    if stamp.exists() and stamp.read_text() == k and npz.exists() and plate.exists():
        with np.load(npz, allow_pickle=False) as z:
            return LayerSet(z["alpha"].astype(np.float32) / 255, z["depth"].astype(np.float32), z["hole"].astype(np.float32) / 255,
                            np.asarray(Image.open(plate).convert("RGB")), z["bg_depth"].astype(np.float32),
                            json.loads(str(z["ids"])), k)
    ls = build_planes(frozen, depth_raw, layers, seed, ldir, log, png=frozen_png, key=key)
    review(ldir, frozen, ls)
    np.savez(ldir / "_tmp.npz", alpha=(ls.alpha * 255 + 0.5).astype(np.uint8), depth=ls.depth.astype(np.float16),
             hole=(ls.hole * 255 + 0.5).astype(np.uint8), bg_depth=ls.bg_depth.astype(np.float16), ids=json.dumps(ls.ids))
    (ldir / "_tmp.npz").replace(npz)
    Image.fromarray(ls.plate).save(plate)
    stamp.write_text(k)
    ls.key = k
    return ls


def review(ldir: Path, frozen: np.ndarray, ls: LayerSet) -> None:
    """planes.jpg beside the planes: the frame, the plate, and each plane's alpha tinted over the frame (what to look at
    when a subject was missed or a plate came out wrong)."""
    from PIL import Image
    tints = [(255, 60, 60), (60, 200, 90), (70, 120, 255), (255, 200, 40), (200, 80, 255), (40, 220, 220), (255, 130, 40), (160, 160, 160)]
    over = frozen.astype(np.float32).copy()
    for i, a in enumerate(ls.alpha):
        over = over * (1 - 0.55 * a[..., None]) + np.array(tints[i % len(tints)], np.float32) * 0.55 * a[..., None]
    h, w = frozen.shape[:2]
    sheet = np.concatenate([frozen, np.clip(over, 0, 255).astype(np.uint8), ls.plate], axis=1)
    im = Image.fromarray(sheet)
    im.thumbnail((2400, 700))
    im.save(ldir / "planes.jpg", quality=88)
