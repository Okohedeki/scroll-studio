"""live: living details on a still picture (`live:` on an image input, engine/spec.py LiveDetail).

One small thing alive in an illustration or a photograph: a light sweeping, a cloud drifting, sparks rising, a glint,
water moving. The page draws it (runtime/src/lib/live.ts: inside a parallax photo's own pass, or a small WebGL layer over
a plain <img>), so nothing is rendered here and no GPU is needed. What the build does, all on the CPU:

  region   a `box` is used as given. A `prompt` is found on the picture with the engine's region tooling (engine/region.py:
           Florence-2 + SAM 2.1 through ComfyUI, cached), softened, and cropped to its extent: the box becomes that extent
           and the page gets the soft mask as a small image. Without ComfyUI (or while planning) the `box` is the fallback,
           and a detail with neither is left out with a note.
  colour   a theme token (light, dark, accent, accent2, ink, bg, bg2) or hex, resolved against the site's colours.
  glints   the region's brightest small points (a difference of Gaussians on the shown picture's luminance, strongest
           first, spaced apart), so twinkles land on specks of light and not on flat colour.

The picture itself is untouched and keeps its cache (engine/inputs.py image_key leaves `live` out).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .spec import EditRegion, ImageInput, LiveDetail

VERSION = 1
MASK_PX = 256            # the soft mask the page is given, square (it is stretched over the box)
POINTS_PX = 1600         # the long side the bright points are looked for at (fine enough to see a printed speck)


# ---------------------------------------------------------------- colour

def colour(d: LiveDetail, colors: dict) -> str:
    """The detail's light colour as #rrggbb: its token or hex, else light (sweep, glint) or accent2 (rise)."""
    from .medium import _lum, hexc
    want = d.color or ("accent2" if d.kind == "rise" else "light")
    c = {k: v for k, v in (colors or {}).items() if isinstance(v, str) and v.strip().startswith("#")}
    bg, ink = c.get("bg", "#fafaf8"), c.get("ink", "#141418")
    light, dark = (bg, ink) if _lum(bg) >= _lum(ink) else (ink, bg)
    roles = {**c, "light": light, "dark": dark}
    if want == "accent2" and want not in roles:
        want = "accent"
    return hexc(roles.get(want, want if want.startswith("#") else light))


# ---------------------------------------------------------------- glints

def bright_points(lum: np.ndarray, box, count: int, weight: Optional[np.ndarray] = None,
                  inset: float = 0.12) -> list[list[float]]:
    """Up to `count` bright small points inside `box` (x0, y0, x1, y1 in 0-1) of a luminance image (H x W, 0-1): local
    peaks of a difference of Gaussians (a speck brighter than its surroundings), weighted by brightness and by `weight`
    (the region's mask over the box, any size), the strongest first and spaced so they do not bunch. Kept off the box's
    soft edge (`inset`, a share of the box). A flat region has no peaks: the twinkles are then spread over it evenly (a
    fixed jittered grid). Returns [x, y, size] with x, y in 0-1 of the picture and size 0.5-1 by strength."""
    import cv2
    H, W = lum.shape
    x0, y0 = int(np.floor(box[0] * W)), int(np.floor(box[1] * H))
    x1, y1 = max(x0 + 1, int(np.ceil(box[2] * W))), max(y0 + 1, int(np.ceil(box[3] * H)))
    crop = lum[y0:y1, x0:x1].astype(np.float32)
    ch, cw = crop.shape
    # a speck brighter than what is just around it, more so on a darker field
    score = (cv2.GaussianBlur(crop, (0, 0), 0.6) - cv2.GaussianBlur(crop, (0, 0), 3.0)) * (1.2 - cv2.GaussianBlur(crop, (0, 0), 8.0))
    if weight is not None:
        score *= cv2.resize(weight.astype(np.float32), (cw, ch), interpolation=cv2.INTER_LINEAR)
    ix, iy = int(round(cw * inset)), int(round(ch * inset))
    band = np.zeros_like(score, dtype=bool)
    band[iy:ch - iy, ix:cw - ix] = True
    score = np.where(band, score, -np.inf)
    gap = max(3, int(0.6 * np.sqrt(ch * cw / max(count, 1))))
    found: list[tuple[int, int, float]] = []
    s = score.copy()
    while len(found) < count:
        i = int(np.argmax(s))
        y, x = divmod(i, cw)
        v = float(s[y, x])
        if not np.isfinite(v) or v <= 0.004:
            break
        found.append((x, y, v))
        s[max(0, y - gap):y + gap + 1, max(0, x - gap):x + gap + 1] = -np.inf
    if found:
        top = max(v for _, _, v in found)
        return [[round((x0 + x + 0.5) / W, 4), round((y0 + y + 0.5) / H, 4), round(0.5 + 0.5 * v / top, 3)] for x, y, v in found]
    rng = np.random.default_rng(VERSION)
    cols = max(1, int(round(np.sqrt(count * cw / max(ch, 1)))))
    rows = max(1, int(np.ceil(count / cols)))
    out = []
    for k in range(count):
        gx, gy = k % cols, k // cols
        u = inset + (1 - 2 * inset) * (gx + 0.25 + 0.5 * rng.random()) / cols
        v = inset + (1 - 2 * inset) * (gy + 0.25 + 0.5 * rng.random()) / rows
        out.append([round(box[0] + u * (box[2] - box[0]), 4), round(box[1] + v * (box[3] - box[1]), 4), 0.75])
    return out


def luminance(path: Path) -> np.ndarray:
    """The picture's luminance (0-1), its long side at most POINTS_PX."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(path)).convert("L")
    if max(im.size) > POINTS_PX:
        s = POINTS_PX / max(im.size)
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


# ---------------------------------------------------------------- the region

def mask_box(m: np.ndarray, pad: float = 0.02) -> Optional[tuple[float, float, float, float]]:
    """The extent of a soft mask (uint8 H x W) as x0, y0, x1, y1 in 0-1, padded by `pad` of the picture's short side on
    every side; None when it is empty."""
    H, W = m.shape
    ys, xs = np.nonzero(m > 8)
    if not len(xs):
        return None
    p = pad * min(H, W)
    return (max(0.0, (xs.min() - p) / W), max(0.0, (ys.min() - p) / H), min(1.0, (xs.max() + 1 + p) / W),
            min(1.0, (ys.max() + 1 + p) / H))


def _cached_region(project, src: Path, er: EditRegion) -> Optional[Path]:
    """region.find's result for this source and prompt if it is already made (never runs a model)."""
    from . import region
    from .project import file_key
    digest = region._digest([file_key(src), region.find_spec(er), "large", region.VERSION])
    p = project.build / "_generated" / f"region_{digest}.png"
    return p if p.exists() else None


def find_region(project, src: Path, d: LiveDetail, log: Callable[[str], None] = print, only_cached: bool = False):
    """(box, soft mask over the box as a MASK_PX square uint8 array, or None) for a detail, or (None, None) to leave it out."""
    if not d.prompt:
        return d.box, None
    from PIL import Image
    from . import region
    er = EditRegion(prompt=d.prompt, pick=d.pick)
    try:
        path = _cached_region(project, src, er) if only_cached else region.find(project, src, er, log)
        if path is None:
            raise RuntimeError("not found yet (a full build finds it)")
    except Exception as e:  # no ComfyUI, the models missing, nothing matching: a box still works
        why = str(e).splitlines()[0][:120] if str(e) else type(e).__name__
        if d.box is not None:
            log(f"  note: live {d.kind} \"{d.prompt}\": {why}; using its box")
            return d.box, None
        log(f"  note: live {d.kind} \"{d.prompt}\": {why}; left out (give it a box to draw it without ComfyUI)")
        return None, None
    raw = np.asarray(Image.open(path).convert("L"))
    short = min(raw.shape)
    m = region.shape(raw, grow=int(0.01 * short), feather=int(0.015 * short))
    b = mask_box(m)
    if b is None:
        return (d.box, None) if d.box is not None else (None, None)
    H, W = m.shape
    crop = m[int(b[1] * H):max(int(b[1] * H) + 1, int(np.ceil(b[3] * H))), int(b[0] * W):max(int(b[0] * W) + 1, int(np.ceil(b[2] * W)))]
    small = np.asarray(Image.fromarray(crop).resize((MASK_PX, MASK_PX), Image.BILINEAR))
    return tuple(round(v, 4) for v in b), small


# ---------------------------------------------------------------- what the page reads

def page_detail(d: LiveDetail, box, color: str, mask_url: Optional[str] = None, points: Optional[list] = None) -> dict:
    """One detail as runtime/src/lib/live.ts reads it."""
    out = {"kind": d.kind, "box": [round(float(v), 4) for v in box], "speed": d.speed, "strength": d.strength,
           "softness": d.softness, "count": d.count, "color": color, "angle": d.angle,
           "origin": list(d.origin) if d.origin is not None else None}
    if mask_url:
        out["mask"] = mask_url
    if points is not None:
        out["points"] = points
    return out


def page_details(project, ref: ImageInput, src: Path, shown: Path, colors: dict, url: Callable[[Path], str],
                 log: Callable[[str], None] = print) -> list[dict]:
    """Every detail of an image input, resolved for the page: regions (boxes or found masks, the masks saved under
    .build/_live/ and published with `url`), colours, and glint points on the picture as `shown`. Empty when it has none."""
    if not isinstance(ref, ImageInput) or not ref.live:
        return []
    from PIL import Image
    from .fidelity import is_planning, preview
    only_cached = is_planning() or preview() is not None
    lum = None
    out = []
    for d in ref.live:
        box, mask = find_region(project, src, d, log, only_cached=only_cached)
        if box is None:
            continue
        mask_url = None
        if mask is not None:
            digest = hashlib.sha1(mask.tobytes() + json.dumps([VERSION, list(box)]).encode()).hexdigest()[:12]
            p = project.build / "_live" / f"mask_{digest}.png"
            if not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(mask).save(p)
            mask_url = url(p)
        points = None
        if d.kind == "glint":
            lum = luminance(shown) if lum is None else lum
            local = mask.astype(np.float32) / 255 if mask is not None else None
            points = bright_points(lum, box, d.count, local)
        out.append(page_detail(d, box, colour(d, colors), mask_url, points))
    return out


def page_entry(details: list[dict], shown: Path) -> dict:
    """The `data-live` attribute of a plain picture: its aspect and its details."""
    from PIL import Image
    with Image.open(shown) as im:
        return {"r": round(im.width / im.height, 4), "d": details}


def summary(details: list[dict]) -> str:
    return ", ".join(f"{d['kind']}" + (" (masked)" if d.get("mask") else "") for d in details)
