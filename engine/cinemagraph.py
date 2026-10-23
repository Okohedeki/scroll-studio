"""cinemagraph: a still where only one thing moves, and everything else is held perfectly still.

`image: { ..., cinemagraph: { moves: "the steam above the cup" } }` on any image input. The still stays the picture the
page shows; this builds a small video of the part that moves, and a soft mask, and the page lays one over the other
(runtime/src/lib/cinemagraph.ts), so outside the mask the pixels are the still's and can never change. In stages, each
cached by its own key (an unchanged spec rebuilds nothing; a changed `seconds` or `loop` redoes only what follows it):

  region   `moves` -> the thing on the still (Florence-2 grounding + SAM 2.1, engine/region.py, the same cached stage an
           `edit.region` uses), grown and feathered; the crop around it (plus its surroundings) that the video model sees.
  clip     the crop brought to life by a local video model (LTX-2.3 or Wan 2.2 image-to-video, engine/animate.py), asked
           for low, local motion and a locked camera. `loop: seamless` asks for the whole loop's length and closes it afterwards; `pingpong` asks for half and plays it both ways.
           Kept lossless (FFV1) so every later stage can be redone without the GPU.
  track    SAM 2.1 follows the moving thing through the clip (seeded on the still's mask), so the mask keeps the whole
           path it sweeps (a flame that leans, a curtain that billows out of its first outline).
  mask     the region, the tracked path and where the clip really moves (temporal motion energy), grown and feathered:
           the mask's edge falls where nothing moves, so no seam is cut through the motion.
  encode   frames stabilised against the still (a video model drifts the whole frame a little), tone-matched to the
           still around the mask, the loop closed (a flow-aligned crossfade where the generated loop does not meet
           itself; pingpong has no seam), motion damped or exaggerated by `strength`, then encoded as H.264 and the
           mask as WebP, plus a report that measures the result: the loop's seam (the step from last frame to first,
           against a typical step), how much moves, how much of the picture, bytes.

The video holds only the crop around the moving part; its pixels outside the mask are the still's own, and the mask is the
page's compositing weight, so `still x (1 - mask) + video x mask` has the still's exact pixels wherever the mask is 0.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .project import BuildContext, BuildError, file_key, probe
from .spec import Cinemagraph, EditRegion, ImageInput

VERSION = 1
MASK_VERSION = 7         # bump when the mask or what follows it would come out differently for the same clip (the clip is kept)
FPS = 24
CONTEXT = 0.5            # how much of the surroundings the video model sees: a share of the region's size on every side
LTX_MP = 0.5             # megapixels LTX-2.3 renders the crop at (aspect kept)
MAX_VIDEO_BYTES = 700_000   # the encode steps its quality down (crf 23, 27, 31) until the video is no bigger than this
MAX_VIDEO_W = 1280       # the encoded video's widest side
MIN_SIDE = 320           # the crop is at least this big (as far as the still goes)
CODEC_STEP = 2.5         # levels a lossy encode may add to the wrap step (an I-frame meeting a P-frame) before it counts as a seam
HELD_BUDGET = 3.0        # levels the picture around the moving part may change beyond what its first frame already differs by
REACH = 0.02             # pingpong: how far the region may travel from its first frame (share of the crop's long side) before the clip is cut
MAX_SLOW = 2.0           # a clip cut short is played slower to fill the loop, by at most this much (beyond it flow interpolation smears)
SEAM_OK = 1.5            # a loop whose closing step is at most this many typical steps is seamless
NEGATIVE = ("camera movement, camera shake, zoom, pan, tilt, cuts, flicker, morphing, warping, new objects appearing, "
            "people, text, watermark, blur, motion in the background, changing light")


# ---------------------------------------------------------------- the spec side

def collect(site) -> list[tuple[str, ImageInput]]:
    """Every image input in a site's spec that carries a `cinemagraph`, with where it is: [("sections[0].image", input)]."""
    from pydantic import BaseModel
    found: list[tuple[str, ImageInput]] = []

    def walk(v, path: str):
        if isinstance(v, ImageInput):
            if v.cinemagraph is not None:
                found.append((path, v))
            for name in ("edit", "beat_frame"):      # the source of an edited image is another input
                walk(getattr(v, name, None), f"{path}.{name}")
        elif isinstance(v, BaseModel):
            for name in type(v).model_fields:
                walk(getattr(v, name, None), f"{path}.{name}" if path else name)
        elif isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}")
    walk(site, "")
    return found


def region_of(cg: Cinemagraph) -> EditRegion:
    """The image editor's region (engine/region.py) that names what moves, so the two share one cached search."""
    return EditRegion(prompt=cg.moves if not cg.box else None, box=cg.box, points=list(cg.points),
                      negative_points=list(cg.negative_points), pick=cg.pick, grow=0, feather=0)


def motion_text(cg: Cinemagraph) -> str:
    """What the video model is told: the motion, and that nothing else moves."""
    how = cg.motion or f"gentle, slow, natural motion of {cg.moves}"
    return (f"{how}. Only {cg.moves} moves; everything else in the picture stays perfectly still. "
            "Locked static camera, no camera movement. A calm, subtle cinemagraph loop")


def video_model_for(cg: Cinemagraph, site_model: Optional[str] = None) -> str:
    from .animate import video_model
    return video_model(cg.model, site_model)


# ---------------------------------------------------------------- the pure parts (numpy / OpenCV, no models)

def luma(a: np.ndarray) -> np.ndarray:
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def seam_report(frames: np.ndarray, mask: Optional[np.ndarray] = None) -> dict:
    """How well a loop closes. `step` is the mean absolute difference (0-255 levels, over the mask) between neighbouring
    frames; `seam` is the same between the last frame and the first, the step the loop makes when it wraps. The ratio is
    seam / the steps beside the wrap: about 1 for a loop that is continuous (the wrap is a step like any other), well above
    it for a loop that jumps."""
    f = frames.astype(np.float32)
    w = None if mask is None else (mask.astype(np.float32) / 255.0)

    def mad(a, b):
        d = np.abs(a - b).mean(axis=-1)
        return float((d * w).sum() / max(w.sum(), 1e-6)) if w is not None else float(d.mean())

    steps = [mad(f[i], f[i + 1]) for i in range(len(f) - 1)]
    typical = float(np.median(steps)) if steps else 0.0
    seam = mad(f[-1], f[0])
    # the step the wrap should be, if the loop is continuous: the steps just before and just after it (motion speeds up and
    # slows down, so the median step is the wrong yardstick at one particular place), never less than half a typical step
    local = float(np.mean(steps[-2:] + steps[:2])) if len(steps) >= 4 else typical
    ref = max(local, 0.5 * typical, 1e-3)
    return {"typical_step": round(typical, 3), "max_step": round(max(steps), 3) if steps else 0.0,
            "seam": round(seam, 3), "ref": round(ref, 3), "ratio": round(seam / ref, 2), "frames": int(len(f))}


def stabilise_flow(frames: np.ndarray, ref: np.ndarray, keep: np.ndarray, log=print) -> tuple[np.ndarray, np.ndarray]:
    """Pin the picture around the moving part to the still. A video model moves the camera however it is told not to (a push
    in, a slow drift, the parallax of a dolly), and a cinemagraph's whole point is that nothing but the one thing moves:
    wherever the video meets the still, the two must agree. Per frame, dense optical flow (DIS) to the still is measured on
    the pixels that are held (`keep`, 255 where the mask is zero), smoothed, carried inward across the moving part by
    normalised convolution (the moving part has no flow of its own to measure: it moves), and the frame is warped back
    along it. Returns the frames and each frame's typical shift in pixels (the median over the held pixels)."""
    import cv2
    T, H, W, _ = frames.shape
    s = min(1.0, 640 / max(H, W))
    sw, sh = max(8, round(W * s)), max(8, round(H * s))
    small = lambda a, interp=cv2.INTER_AREA: cv2.resize(a, (sw, sh), interpolation=interp) if s < 1 else a
    gray = lambda a: cv2.GaussianBlur(cv2.cvtColor(small(a), cv2.COLOR_RGB2GRAY), (0, 0), 1.0)
    rg = gray(ref)
    held = small((keep > 200).astype(np.uint8) * 255, cv2.INTER_NEAREST) > 0
    held = cv2.erode(held.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    if held.mean() < 0.05:
        return frames, np.zeros(T)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    wgt = held.astype(np.float32)
    sig = max(6.0, 0.05 * max(sh, sw))
    wblur = cv2.GaussianBlur(wgt, (0, 0), sig) + 1e-4
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    out = frames.copy()
    shifts = np.zeros(T)
    for t in range(T):
        # flow from the still to the frame: sampling the frame at (x + flow) puts its content where the still has it
        fl = dis.calc(rg, gray(frames[t]), None)
        med = float(np.median(np.hypot(fl[..., 0], fl[..., 1])[held]))
        shifts[t] = med / s
        if med / s < 0.4 and float(np.percentile(np.hypot(fl[..., 0], fl[..., 1])[held], 95)) / s < 1.0:
            continue                                        # already registered: resampling would only soften it
        fill = np.stack([cv2.GaussianBlur(fl[..., c] * wgt, (0, 0), sig) / wblur for c in (0, 1)], axis=-1)
        near = cv2.GaussianBlur(wgt, (0, 0), 2.0)
        near = np.clip(near * 1.5, 0, 1)[..., None]
        fh = np.stack([cv2.GaussianBlur(fl[..., c], (0, 0), 2.0) for c in (0, 1)], axis=-1)
        flow = fh * near + fill * (1 - near)               # held pixels keep their own flow; the moving part takes the carried one
        if s < 1:
            flow = cv2.resize(flow, (W, H), interpolation=cv2.INTER_LINEAR) / s
        out[t] = cv2.remap(frames[t], gx + flow[..., 0], gy + flow[..., 1], cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, shifts


def tone_match(frames: np.ndarray, ref: np.ndarray, mask: np.ndarray, ring: int) -> np.ndarray:
    """Make every frame's tone agree with the still around the moving part. A video model returns a picture a shade off
    the one it was given (the encode, a little contrast, a warmer white), and inside the mask that shade would show as a
    patch. Per frame and channel, a gain and offset fitted on the pixels just outside the mask (the ring, where the still
    and the frame should be the same thing), then a smooth residual spread inward from the ring."""
    import cv2
    T, H, W, _ = frames.shape
    m = (mask > 0).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring + 1, 2 * ring + 1))
    near = cv2.dilate(m, k, iterations=2)
    band = (near > 0) & (m == 0)
    if band.sum() < 200:               # the mask reaches the crop's edge all round: fit on everything held
        band = m == 0
    if band.sum() < 200:
        return frames
    refb = ref[band].astype(np.float32)                       # (n, 3)
    out = np.empty_like(frames)
    sig = max(6.0, min(H, W) / 8)
    q = max(1, int(sig // 6))                                 # the residual is smooth: work on a 1/q-size copy of it
    sw, sh = max(2, W // q), max(2, H // q)
    wsmall = cv2.resize(band.astype(np.float32), (sw, sh), interpolation=cv2.INTER_AREA)
    wblur = cv2.GaussianBlur(wsmall, (0, 0), sig / q) + 1e-4
    msmall = cv2.resize((m > 0).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)[..., None]
    refs = ref.astype(np.float32)
    for t in range(T):
        f = frames[t].astype(np.float32)
        fb = f[band]
        g = np.empty(3, np.float32)
        o = np.empty(3, np.float32)
        for c in range(3):
            x, y = fb[:, c], refb[:, c]
            vx = x.var()
            g[c] = np.clip(np.cov(x, y)[0, 1] / vx, 0.85, 1.15) if vx > 1e-3 else 1.0
            o[c] = y.mean() - g[c] * x.mean()
        f = f * g + o
        # what is left, smooth, from the ring inward
        resid = cv2.resize((refs - f) * band[..., None], (sw, sh), interpolation=cv2.INTER_AREA)
        resid = cv2.GaussianBlur(resid, (0, 0), sig / q) / wblur[..., None]
        resid = cv2.resize(resid, (W, H), interpolation=cv2.INTER_LINEAR)
        f = f + resid * msmall
        out[t] = np.clip(f + 0.5, 0, 255).astype(np.uint8)
    return out


def motion_energy(frames: np.ndarray) -> np.ndarray:
    """Where the clip moves, as a 0-255-level map: per pixel, a high percentile over time of how far a (slightly blurred)
    frame is from the clip's own mean. Blurred first so grain and codec noise do not count as motion."""
    import cv2
    T, H, W, _ = frames.shape
    s = min(1.0, 640 / max(H, W))
    small = np.stack([cv2.GaussianBlur(cv2.resize(f, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else f,
                                       (0, 0), 1.5) for f in frames]).astype(np.float32)
    dev = np.abs(small - small.mean(axis=0, keepdims=True)).mean(axis=-1)       # (T, h, w)
    e = np.percentile(dev, 92, axis=0).astype(np.float32)
    if s < 1:
        e = cv2.resize(e, (W, H), interpolation=cv2.INTER_LINEAR)
    return e


def final_mask(seed: np.ndarray, energy: np.ndarray, grow: float, feather: float, tracked: Optional[np.ndarray] = None
               ) -> tuple[np.ndarray, dict]:
    """The mask the page composites through (uint8, 0 = the still, 255 = the video), from the region found on the still
    (`seed`, 0-255), the path the tracker saw it sweep (`tracked`, the union over the clip, or None), and the clip's
    motion energy. The video is kept where the thing is or where it is seen to move, near it; where nothing moves at all
    the still is kept (a patch of the video there would only be softer than the still), and the mask's soft edge falls on
    pixels that do not move, so no seam is cut through the motion."""
    import cv2
    from .region import despeckle, shape
    H, W = seed.shape
    base = seed > 127
    if tracked is not None:
        base = base | (tracked > 127)
    side = min(H, W)
    energy = energy.copy()
    m = max(3, int(0.02 * side))
    energy[:m], energy[-m:], energy[:, :m], energy[:, -m:] = 0, 0, 0, 0       # the edge of a warped frame is not motion
    ell = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    around = cv2.dilate(base.astype(np.uint8), ell(max(6, int(0.07 * side)))) > 0
    # the yardstick is how much the thing itself moves (a flame flickers by a few levels, a curtain by fifty): the peak of the
    # energy around the region, not of the whole picture
    peak = float(np.percentile(energy[around], 99.8)) if around.any() else float(np.percentile(energy, 99.5))
    tau = max(3.0, 0.35 * peak)
    moving = energy > tau
    # one or two pixels wide and long is not a thing that moves: it is the edge of something the registration did not hold
    moving = cv2.morphologyEx(moving.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    # everything that moves AND is joined to the thing (or to its tracked path) is the thing: a curtain's hem lifts, a flame
    # leans, steam climbs well past the box it was found in. Pieces that move but are not joined to it (the model moving
    # something else) are left as the still.
    joined = cv2.dilate(moving.astype(np.uint8), ell(max(2, int(0.01 * side)))) > 0
    n, lab = cv2.connectedComponents(joined.astype(np.uint8), connectivity=8)
    hit = np.unique(lab[base & joined])
    hit = hit[hit > 0]
    parts = np.isin(lab, hit) & moving
    if parts.sum() > 0.7 * H * W:          # most of the picture "moves": the model moved the camera, not a thing; stay near it
        reach = max(6, int(0.07 * side))
        parts = parts & (cv2.dilate(base.astype(np.uint8), ell(reach)) > 0)
    # the region itself is kept only where something moves within a feather's width (a still part of the region stays the still)
    live = cv2.dilate(moving.astype(np.uint8), ell(max(3, int(feather)))) > 0
    where = (base & live) | parts
    info = {"tau": round(tau, 2), "peak": round(peak, 2), "moving_px": int(moving.sum())}
    if where.sum() < max(64, 0.0005 * H * W):
        raise BuildError("the clip does not move where the picture says: nothing in the region moves. Raise `strength`, describe "
                         "the motion in `motion`, or point at the thing with `box` / `points`")
    where = cv2.morphologyEx(where.astype(np.uint8) * 255, cv2.MORPH_CLOSE, ell(max(2, int(grow))))
    where = despeckle(where, 0.08)          # a stray patch that moved (a car outside the window) is not the thing
    return shape(where, int(round(grow)), int(round(feather))), info


def close_loop(frames: np.ndarray, overlap: int, flow: bool = True) -> np.ndarray:
    """Close a clip into a loop by crossfading its tail into its head. Frames 0..T-1 become T-overlap frames, in which
    the first `overlap` frames are the clip's last `overlap` frames dissolving into its first ones: so the wrap
    (last frame -> first) is a step like any other. With `flow`, each blend is made between frames moved halfway toward
    each other (optical flow), so a flame or a fold of cloth slides across the dissolve instead of ghosting; blends
    that flow made worse (it can: soft, translucent subjects) fall back to the plain dissolve."""
    import cv2
    T = len(frames)
    n = int(max(1, min(overlap, T // 2 - 1)))
    L = T - n
    out = [f for f in frames[:L]]
    f32 = frames.astype(np.float32)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM) if flow else None
    gray = lambda a: cv2.cvtColor(np.clip(a, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    H, W = frames.shape[1:3]
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    for i in range(n):
        a, b = f32[L + i], f32[i]             # a: the tail's i-th frame (fading out), b: the head's (fading in)
        w = (i + 1) / (n + 1)
        plain = a * (1 - w) + b * w
        if dis is not None:
            fab = dis.calc(gray(a), gray(b), None)      # a -> b
            fba = dis.calc(gray(b), gray(a), None)      # b -> a
            wa = cv2.remap(a, gx + fab[..., 0] * w, gy + fab[..., 1] * w, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            wb = cv2.remap(b, gx + fba[..., 0] * (1 - w), gy + fba[..., 1] * (1 - w), cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REPLICATE)
            morph = wa * (1 - w) + wb * w
            # the better blend is the one that is closer to both neighbours' appearance in the middle of the dissolve
            ref = (a + b) * 0.5
            pick = morph if np.abs(morph - ref).mean() <= np.abs(plain - ref).mean() * 1.6 else plain
        else:
            pick = plain
        out[i] = np.clip(pick + 0.5, 0, 255).astype(np.uint8)
    return np.stack(out)


def _reach(g0: np.ndarray, frame: np.ndarray, area: np.ndarray, dis, sc: float) -> float:
    """How far (px of the full-size frame) the content of `area` has moved from the first frame to this one: the mean optical
    flow magnitude over the area (g0: the first frame, grey and blurred at scale `sc`)."""
    import cv2
    g = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(frame, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY), (0, 0), 1.0)
    fl = dis.calc(g0, g, None)
    return float(np.hypot(fl[..., 0], fl[..., 1])[area].mean()) / sc


def trim_to_budget(frames: np.ndarray, still: np.ndarray, seed: np.ndarray, strength: float, region_budget: bool,
                   floor: int = FPS // 2) -> tuple[np.ndarray, dict]:
    """Keep the part of the clip that is good for a cinemagraph. A video model starts as asked (the gentle sway, the curl of
    steam) and drifts into what it likes (the camera pushes in, the curtain flies across the room). Frames are kept until

      held      the picture around the moving part has changed from the still by more than HELD_BUDGET levels beyond what
                the first frame already differed by (after the flow stabilisation: what is left is real change, a parallax,
                something coming into view), or
      region    (pingpong only, which only needs the way out) the moving part has travelled from its first frame by more than
                REACH x the crop's long side x `strength` (mean optical-flow magnitude over the region: real displacement, not
                the re-rendered texture a video model "boils" from frame to frame): far enough for one swing,

    but at least `floor` frames. A clip that never gets there is kept whole."""
    import cv2
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * 12 + 1, 2 * 12 + 1))
    near = cv2.dilate((seed > 127).astype(np.uint8), k) > 0
    held = cv2.dilate((seed > 127).astype(np.uint8), np.ones((51, 51), np.uint8)) == 0
    f0 = frames[0].astype(np.float32)
    st = still.astype(np.float32)
    H, W = frames.shape[1:3]
    sc = min(1.0, 480 / max(H, W))
    budget = REACH * max(H, W) * float(strength)         # how far (px, as optical flow) the region may travel from its first frame
    g0 = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(frames[0], None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY), (0, 0), 1.0)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
    near = cv2.resize(near.astype(np.uint8), (g0.shape[1], g0.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    base = float(np.abs(f0 - st).mean(axis=-1)[held].mean()) if held.mean() > 0.05 else 0.0
    keep, why = len(frames), None
    for t in range(1, len(frames)):
        ft = frames[t].astype(np.float32)
        if held.mean() > 0.05 and float(np.abs(ft - st).mean(axis=-1)[held].mean()) > base + HELD_BUDGET:
            keep, why = t, "the picture around it started to change"
        elif region_budget and near.any() and _reach(g0, frames[t], near, dis, sc) > budget:
            keep, why = t + 1, "the region has moved as far as it should"
        if why:
            break
    keep = max(min(floor, len(frames)), keep)
    return frames[:keep], {"kept": int(keep), "of": int(len(frames)), "budget": round(budget, 1), "cut_because": why}


def slow(frames: np.ndarray, n_out: int) -> np.ndarray:
    """Play `frames` over `n_out` frames instead (slower): the in-between frames are made by moving the two neighbours toward
    each other along optical flow (DIS), so cloth and smoke glide rather than dissolve. First and last frames are kept."""
    import cv2
    n = len(frames)
    if n_out <= n or n < 2:
        return frames
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    gray = [cv2.cvtColor(f, cv2.COLOR_RGB2GRAY) for f in frames]
    H, W = frames.shape[1:3]
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    flows: dict[int, tuple] = {}
    out = []
    for k in range(n_out):
        pos = k * (n - 1) / (n_out - 1)
        i = min(int(pos), n - 2)
        w = pos - i
        if w < 1e-3:
            out.append(frames[i])
            continue
        if i not in flows:
            flows[i] = (dis.calc(gray[i], gray[i + 1], None), dis.calc(gray[i + 1], gray[i], None))
        fab, fba = flows[i]
        a = cv2.remap(frames[i], gx + fab[..., 0] * w, gy + fab[..., 1] * w, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        b = cv2.remap(frames[i + 1], gx + fba[..., 0] * (1 - w), gy + fba[..., 1] * (1 - w), cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_REPLICATE)
        out.append(np.clip(a.astype(np.float32) * (1 - w) + b.astype(np.float32) * w + 0.5, 0, 255).astype(np.uint8))
    return np.stack(out)


def pingpong(frames: np.ndarray) -> np.ndarray:
    """Forward, then back without repeating the turning frames: the loop's wrap is a step between neighbours."""
    if len(frames) < 3:
        return frames
    return np.concatenate([frames, frames[-2:0:-1]])


def damp(frames: np.ndarray, k: float) -> np.ndarray:
    """Scale the motion about its resting look (the mean of the loop): k < 1 calms it, k > 1 exaggerates it."""
    if abs(k - 1.0) < 1e-3:
        return frames
    f = frames.astype(np.float32)
    mean = f.mean(axis=0, keepdims=True)
    return np.clip(mean + (f - mean) * k + 0.5, 0, 255).astype(np.uint8)


def composite_video(frames: np.ndarray, still: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """The frames the video holds: the clip where the mask is above zero, the still itself everywhere else (so that the
    encoder has nothing to spend bits on outside the moving part, and the part it does encode is the whole story)."""
    live = (mask > 0)[None, ..., None]
    return np.where(live, frames, still[None])


def page_composite(poster: np.ndarray, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """What the browser shows for one video frame: poster x (1 - mask) + frame x mask (integer arithmetic, the twin of
    region.composite): where the mask is 0 the pixel is the poster's, exactly."""
    from .region import composite
    return composite(poster, frame, mask)


def review_sheet(still: np.ndarray, dec: np.ndarray, mask: np.ndarray, path: Path) -> None:
    """A contact sheet to read: the still with the mask's edge, the mask, six frames as the page composes them, and where the
    pixels change over the loop (bright = moves; black = held exactly)."""
    import cv2
    from PIL import Image
    from .region import outline
    H, W = mask.shape
    tw = min(W, 520)
    th = round(H * tw / W)
    fit = lambda a: cv2.resize(a, (tw, th), interpolation=cv2.INTER_AREA)
    ol = np.asarray(outline(mask))
    base = still.astype(np.float32)
    edge = (base * (1 - ol[..., 3:4] / 255.0) + ol[..., :3] * (ol[..., 3:4] / 255.0)).astype(np.uint8)
    idx = np.linspace(0, len(dec) - 1, 6).astype(int)
    shown = [page_composite(still, dec[i], mask) for i in idx]
    rng = np.abs(np.stack(shown).astype(np.int16) - still[None].astype(np.int16)).max(axis=0).max(axis=-1)
    heat = cv2.applyColorMap(np.clip(rng * 3, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)[..., ::-1]
    tiles = [fit(edge), fit(np.repeat(mask[..., None], 3, axis=2)), *[fit(f) for f in shown], fit(np.ascontiguousarray(heat))]
    cols = 3
    rows = -(-len(tiles) // cols)
    sheet = np.zeros((rows * th, cols * tw, 3), np.uint8)
    for k, t in enumerate(tiles):
        sheet[(k // cols) * th:(k // cols + 1) * th, (k % cols) * tw:(k % cols + 1) * tw] = t
    Image.fromarray(sheet).save(path, quality=88)


# ---------------------------------------------------------------- video in and out

def read_video(path: Path) -> np.ndarray:
    """Every frame of a clip as uint8 RGB (T, H, W, 3), through FFmpeg."""
    from .config import settings
    info = probe(path)
    W, H = int(info["width"]), int(info["height"])
    p = subprocess.run([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True)
    if p.returncode != 0:
        raise BuildError(f"could not read {path.name}: {p.stderr.decode(errors='replace')[-400:]}")
    a = np.frombuffer(p.stdout, np.uint8)
    return a.reshape(-1, H, W, 3)


def write_lossless(frames: np.ndarray, path: Path, fps: int = FPS) -> None:
    """FFV1 in Matroska: the generated clip kept exactly, at a third of the PNGs' size."""
    from .config import settings
    T, H, W, _ = frames.shape
    tmp = path.with_name(path.stem + ".tmp.mkv")
    p = subprocess.Popen([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0",
                          str(tmp)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    _, err = p.communicate(np.ascontiguousarray(frames).tobytes())
    if p.returncode != 0:
        raise BuildError(f"FFV1 encode failed: {err.decode(errors='replace')[-400:]}")
    tmp.replace(path)


def encode_h264(frames: np.ndarray, path: Path, fps: int = FPS, crf: int = 23) -> None:
    """The cinemagraph's video: H.264 (plays everywhere), yuv420p tagged BT.709 so a browser shows its colours the way it
    shows the poster's, faststart, no audio."""
    from .config import settings
    T, H, W, _ = frames.shape
    tmp = path.with_name(path.stem + ".tmp.mp4")
    vf = "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p"
    p = subprocess.Popen([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-vf", vf, "-an", "-c:v", "libx264", "-profile:v", "main",
                          "-preset", "slow", "-crf", str(crf), "-x264-params", "ipratio=1.0:pbratio=1.0", "-g", str(fps * 2), "-colorspace", "bt709", "-color_primaries",
                          "bt709", "-color_trc", "bt709", "-color_range", "tv", "-movflags", "+faststart", str(tmp)],
                         stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    _, err = p.communicate(np.ascontiguousarray(frames).tobytes())
    if p.returncode != 0:
        raise BuildError(f"H.264 encode failed: {err.decode(errors='replace')[-400:]}")
    tmp.replace(path)


def save_mask(mask: np.ndarray, path: Path) -> None:
    """The mask as a WebP the page uses as a CSS mask: white, with the mask as its alpha (lossless: the 8-bit weights are
    exactly what the engine measured)."""
    from PIL import Image
    H, W = mask.shape
    rgba = np.full((H, W, 4), 255, np.uint8)
    rgba[..., 3] = mask
    Image.fromarray(rgba, "RGBA").save(path, "WEBP", lossless=True, method=6, exact=True)


# ---------------------------------------------------------------- stages

def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def region_key(cg: Cinemagraph) -> dict:
    return {"moves": cg.moves, "box": cg.box, "points": [list(p) for p in cg.points],
            "negative_points": [list(p) for p in cg.negative_points], "pick": cg.pick}


def crop_around(mask: np.ndarray, still_size: tuple[int, int], context: float = CONTEXT) -> tuple[int, int, int, int]:
    """The crop of the still the video model is shown: the region plus its surroundings, at least MIN_SIDE across, edges on
    multiples of 8 (so every size derived from it is a whole number of macroblocks)."""
    from .region import crop_box
    W, H = still_size
    x0, y0, x1, y1 = crop_box(mask, context)
    def snap(lo, hi, limit):
        lo, hi = max(0, lo // 8 * 8), min(limit, -(-hi // 8) * 8)
        if hi - lo < min(MIN_SIDE, limit):                     # still a little small: widen about the middle
            mid = (lo + hi) // 2
            lo, hi = max(0, mid - MIN_SIDE // 2), min(limit, mid + MIN_SIDE // 2)
        return lo, hi
    (a, c), (b, d) = snap(x0, x1, W), snap(y0, y1, H)
    return a, b, c, d


def gen_size(cw: int, ch: int, model: str, wan: Optional[dict]) -> tuple[int, int]:
    """What the video model renders the crop at (aspect kept): LTX about LTX_MP megapixels, Wan its own (animate.wan_size)."""
    from .animate import ltx_size, wan_size
    if model == "wan":
        return wan_size(cw, ch, (wan or {}).get("res"))
    return ltx_size(cw, ch, LTX_MP)


def work_size(cw: int, ch: int) -> tuple[int, int]:
    """The size of everything after the clip (and of the encoded video): the crop's own pixels, down to MAX_VIDEO_W, even."""
    s = min(1.0, MAX_VIDEO_W / max(cw, ch))
    return max(2, round(cw * s / 2) * 2), max(2, round(ch * s / 2) * 2)


class Built(dict):
    """What a cinemagraph build gives the page: video, mask (files), box (fractions of the still), sizes, report."""


def build(project, ref: ImageInput, log: Callable[[str], None] = print, force: bool = False,
          options: Optional[dict] = None, site_video_model: Optional[str] = None, site_wan: Optional[dict] = None,
          only_cached: bool = False) -> Optional[Built]:
    """Build (or find in the cache) the cinemagraph of an image input. Returns None when only_cached and nothing is built,
    or when planning. Files are in .build/_cinemagraph/<id>/: cine.mp4, cine.mask.webp, report.json."""
    from . import inputs
    from .fidelity import is_planning
    cg = ref.cinemagraph
    if cg is None:
        return None
    still_path = inputs.resolve_image(project, ref, log)
    from PIL import Image, ImageOps
    sim = ImageOps.exif_transpose(Image.open(still_path)).convert("RGB")
    W, H = sim.size
    model = video_model_for(cg, site_video_model)
    wan = dict(site_wan or {})
    sid = _digest([file_key(still_path), region_key(cg), VERSION])
    ctx = BuildContext(project, f"_cinemagraph/{sid}", log=log, force=force, options=dict(options or {}))
    work = ctx.work
    plan = ctx.options.get("plan")

    # ---- region: the mask on the still, and the crop the model sees
    from . import region as region_mod
    reg = region_of(cg)
    if only_cached or is_planning():
        digest = _digest([file_key(still_path), region_mod.find_spec(reg), "large", region_mod.VERSION])
        if not (project.build / "_generated" / f"region_{digest}.png").exists():
            return None
    raw_path = region_mod.find(project, still_path, reg, log)
    raw = np.asarray(Image.open(raw_path).convert("L"))
    if raw.shape != (H, W):
        raw = np.asarray(Image.fromarray(raw).resize((W, H), Image.BILINEAR))
    seed_full = region_mod.shape(raw, 0, 0)               # the region as found (binary, despeckled), at the still's size
    if (seed_full > 127).mean() > 0.4:
        raise BuildError(f"cinemagraph `moves: {cg.moves}` matched {(seed_full > 127).mean():.0%} of the picture, which is not one "
                         "moving thing. Name the part that moves (\"the flame\", not \"the candle\"), or give `pick: smallest` "
                         "(Florence-2 also returns a box around the whole scene), `box` or `points`")
    box = crop_around(seed_full, (W, H))
    x0, y0, x1, y1 = box
    cw, ch = x1 - x0, y1 - y0
    ww, wh = work_size(cw, ch)
    gw, gh = gen_size(cw, ch, model, wan)
    seconds = float(cg.seconds)
    # Measured, on both models: telling the video model that the clip must END on the picture it began with (first = last frame)
    # does not make a loop. LTX-2.3 returns a clip that hardly moves (the pin wins); with the pin loosened the middle of the
    # clip goes wild and comes back; Wan 2.2 invents an action to get from the still to the still (a hand throws a sheet across
    # the window). So a seamless loop is a free clip, closed afterwards by a flow-aligned crossfade, which is right for what
    # flows (steam, smoke, water, a flame: the same thing a moment later); and a pingpong loop uses only the way out.
    # a pingpong loop plays the clip forward then back, so the model is asked for half of `seconds` (a short clip also stays
    # close to the still: a video model's motion grows the longer it runs)
    # a video model's first second or two are the useful ones (see trim_to_budget): ask for no more than that and play it slower
    gen_seconds = min(2.5, max(1.5, seconds if cg.loop == "seamless" else seconds / 2))
    crop_png = work / "crop.png"
    sim.crop(box).save(crop_png)

    # ---- clip: the video model brings the crop to life
    ckey = {"v": VERSION, "crop": [file_key(still_path), box], "motion": motion_text(cg), "seconds": gen_seconds, "seed": cg.seed,
            "model": model, "wan": wan if model == "wan" else None, "size": [gw, gh]}
    cid = _digest(ckey)
    clip = work / f"clip_{cid}.mkv"            # one file per variant, so going back to an earlier `loop` or `seconds` costs nothing
    if only_cached and ctx.status(f"clip_{cid}", ckey, [clip]) not in ("fresh", "migrated", "locked"):
        return None

    def make_clip():
        from . import animate
        from .fidelity import would_render
        would_render("cinemagraph", cg.moves)
        frames = animate.animate(crop_png, "", motion_text(cg), gen_seconds, cg.seed, work, size=(gw, gh), log=log,
                                 negative=NEGATIVE, strength=1.0, model=model, wan=wan)
        import cv2
        arr = np.stack([cv2.resize(np.asarray(Image.open(p).convert("RGB")), (ww, wh), interpolation=cv2.INTER_AREA
                                   if (ww, wh) < Image.open(p).size else cv2.INTER_CUBIC) for p in frames])
        write_lossless(arr, clip)
        shutil.rmtree(work / "frames", ignore_errors=True)
    ctx.stage(f"clip_{cid}", ckey, [clip], make_clip)
    if plan is not None and not clip.exists():
        return None

    import cv2
    still_c = cv2.resize(np.asarray(sim.crop(box)), (ww, wh), interpolation=cv2.INTER_AREA if (ww, wh) < (cw, ch) else cv2.INTER_CUBIC)
    seed_c = cv2.resize(seed_full[y0:y1, x0:x1], (ww, wh), interpolation=cv2.INTER_LINEAR)
    sc = ww / cw                                           # work pixels per still pixel
    seed_id = hashlib.sha1(seed_c.tobytes()).hexdigest()[:12]

    # ---- prep: the clip as the rest works on it: stabilised against the still, and (pingpong) cut where it has gone far enough
    pid = _digest([ckey, cg.loop, cg.strength, cg.seconds, MASK_VERSION])
    prep, prep_json = work / f"prep_{pid}.mkv", work / f"prep_{pid}.json"

    def run_prep():
        raw = read_video(clip)
        st, shifts = stabilise_flow(raw, still_c, np.where(seed_c > 0, 0, 255).astype(np.uint8), log)
        st, trim = trim_to_budget(st, still_c, seed_c, cg.strength, region_budget=cg.loop == "pingpong")
        shifts = shifts[:trim["kept"]]
        if trim["kept"] < trim["of"]:
            log(f"  the clip is cut at {trim['kept']} of {trim['of']} frames: {trim['cut_because']}")
        want = int(round((cg.seconds / 2 if cg.loop == "pingpong" else cg.seconds) * FPS)) + 1
        n_out = min(want, int(len(st) * MAX_SLOW))
        if n_out > len(st):
            log(f"  played {n_out / len(st):.1f}x slower to fill the {cg.seconds:g} s loop")
            st = slow(st, n_out)
        trim["slowed_to"] = int(len(st))
        write_lossless(st, prep)
        prep_json.write_text(json.dumps({"camera_shift_px": round(float(shifts.max()), 1), **trim}))
    ctx.stage(f"prep_{pid}", {"v": VERSION, "clip": cid, "loop": cg.loop, "strength": cg.strength, "seconds": cg.seconds, "seed": seed_id}, [prep, prep_json], run_prep)
    prep_info = json.loads(prep_json.read_text())

    # ---- track: SAM 2.1 follows the moving thing through the clip
    tr = work / f"track_{pid}.npz"
    if cg.track:
        def run_track():
            try:
                _track(ctx, read_video(prep), seed_c, tr, log)
            except BuildError as e:
                log(f"  note: tracking did not run ({e}); the mask follows the region and the clip's motion instead")
                np.savez_compressed(tr, union=np.zeros((1, 1), np.uint8), ok=False)
        ctx.stage(f"track_{pid}", {"v": VERSION, "prep": pid, "seed": seed_id}, [tr], run_track)

    # ---- mask: where the clip moves, the region and the path it sweeps, grown and feathered
    mid = _digest([pid, cg.track, cg.grow, cg.feather, MASK_VERSION])
    mask_png, mask_json = work / f"mask_{mid}.png", work / f"mask_{mid}.json"

    def run_mask():
        tracked = None
        if cg.track and tr.exists():
            z = np.load(tr)
            tracked = z["union"] if "ok" not in z.files else None
        m, info = final_mask(seed_c, motion_energy(read_video(prep)), cg.grow * sc, cg.feather * sc, tracked)
        Image.fromarray(m, "L").save(mask_png)
        mask_json.write_text(json.dumps({**info, "tracked": tracked is not None}))
    ctx.stage(f"mask_{mid}", {"v": VERSION, "prep": pid, "track": cg.track, "grow": cg.grow, "feather": cg.feather, "m": MASK_VERSION}, [mask_png, mask_json], run_mask)
    if plan is not None and not (mask_png.exists() and prep.exists()):
        return None

    # ---- encode: stabilise, tone-match, close the loop, damp, composite, encode, measure
    out_id = _digest([mid, cg.loop, cg.strength, MASK_VERSION])
    mp4, wp, rep = work / f"cine_{out_id}.mp4", work / f"cine_{out_id}.mask.webp", work / f"cine_{out_id}.json"
    sheet = work / f"cine_{out_id}.sheet.jpg"
    ekey = {"v": VERSION, "out": out_id}

    def run_encode():
        frames_st = read_video(prep)
        T = len(frames_st)
        mask = np.asarray(Image.open(mask_png).convert("L"))
        minfo = json.loads(mask_json.read_text())
        ring = max(8, int(round(cg.feather * sc)))
        fr = tone_match(frames_st, still_c, mask, ring)
        before = seam_report(fr, mask)
        if cg.loop == "pingpong":
            seq, how = pingpong(fr), "pingpong"
            closed = seam_report(seq, mask)
        else:
            if before["ratio"] <= SEAM_OK:
                seq, how, closed = fr, "as generated", before
            else:
                n = int(min(max(8, T // 6), T // 2 - 1))
                seq, how = close_loop(fr, n, flow=True), f"crossfade ({n} frames, flow-aligned)"
                closed = seam_report(seq, mask)
                plain = close_loop(fr, n, flow=False)
                alt = seam_report(plain, mask)
                if alt["ratio"] < closed["ratio"]:
                    seq, how, closed = plain, f"crossfade ({n} frames)", alt
        seq = damp(seq, cg.strength)
        # the video holds only the moving part: the mask's own box (and a pixel or two), not the whole crop the model was shown
        ys, xs = np.nonzero(mask)
        bx0, by0 = max(0, int(xs.min()) - 2) // 2 * 2, max(0, int(ys.min()) - 2) // 2 * 2
        bx1, by1 = min(ww, -(-(int(xs.max()) + 3) // 2) * 2), min(wh, -(-(int(ys.max()) + 3) // 2) * 2)
        seq, mask, still_k = seq[:, by0:by1, bx0:bx1], mask[by0:by1, bx0:bx1], still_c[by0:by1, bx0:bx1]
        rbox = [round(x0 + bx0 / sc), round(y0 + by0 / sc), round(x0 + bx1 / sc), round(y0 + by1 / sc)]
        vid = composite_video(seq, still_k, mask)
        encode_h264(vid, mp4)
        for crf in (27, 31):                                       # fine texture (water, foliage) costs bytes: a page loads this
            if mp4.stat().st_size <= MAX_VIDEO_BYTES:
                break
            encode_h264(vid, mp4, crf=crf)
        save_mask(mask, wp)
        dec = read_video(mp4)                                   # measure what the page will play, not what we meant
        review_sheet(still_k, dec, mask, sheet)
        outside = _outside_change(dec, still_k, mask)
        decoded = seam_report(dec, mask)
        motion = float(np.mean(np.std(seq.astype(np.float32), axis=0).mean(axis=-1)[mask > 127])) if (mask > 127).any() else 0.0
        report = {
            "moves": cg.moves, "model": model, "seconds": round(len(seq) / FPS, 2), "fps": FPS, "frames": int(len(seq)),
            "loop": {"mode": cg.loop, "closed_by": how, "generated": before, "closed": closed, "encoded": decoded,
                     "seamless": decoded["seam"] <= max(SEAM_OK * max(decoded["ref"], decoded["typical_step"]),
                                                  max(decoded["ref"], decoded["typical_step"]) + CODEC_STEP)},
            "still": [W, H], "box": rbox, "video": [bx1 - bx0, by1 - by0], "bytes": mp4.stat().st_size + wp.stat().st_size,
            "mask": {"share_of_still": round(float((mask > 127).sum()) / sc / sc / (W * H), 4), **minfo},
            "motion": {"temporal_std": round(motion, 2), "camera_shift_px_removed": prep_info["camera_shift_px"], "cut_because": prep_info["cut_because"], "kept_frames": prep_info["kept"],
                       "of_generated": prep_info["of"], "played_frames": prep_info.get("slowed_to", prep_info["kept"])},
            "held": {"max_change_outside_mask": outside["page"], "video_file_change_outside_mask": outside["file"]},
        }
        rep.write_text(json.dumps(report, indent=1))
    ctx.stage(f"encode_{out_id}", ekey, [mp4, wp, rep, sheet], run_encode)
    if plan is not None and not rep.exists():
        return None
    report = json.loads(rep.read_text())
    bx0, by0, bx1, by1 = report["box"]
    return Built(video=mp4, mask=wp, report=rep, sheet=sheet, data=report, box=[bx0 / W, by0 / H, bx1 / W, by1 / H], still=[W, H],
                 size=report["video"], poster_crop=crop_png, id=out_id)


def _outside_change(dec: np.ndarray, still: np.ndarray, mask: np.ndarray) -> dict:
    """What is held still. `page`: the largest change from the still, in any frame, of any pixel where the mask is zero, in what
    the page composes from the decoded video (poster x (1 - mask) + video x mask): 0 means those pixels are the still's own.
    `file`: the same over the video file itself, which holds the still there too but through a lossy codec; it is never
    shown where the mask is zero, and tells how clean the encode is next to the moving part."""
    z = mask == 0
    if not z.any():
        return {"page": 0, "file": 0, "share": 0.0}
    page = 0
    for f in dec:
        shown = page_composite(still, f, mask)
        page = max(page, int(np.abs(shown[z].astype(np.int16) - still[z].astype(np.int16)).max()))
    d = np.abs(dec[:, z].astype(np.int16) - still[z].astype(np.int16)[None])
    return {"page": page, "file": int(d.max()), "share": round(float((d.max(axis=(0, 2)) > 0).mean()), 4)}


def _track(ctx: BuildContext, frames: np.ndarray, seed: np.ndarray, out: Path, log) -> None:
    """SAM 2.1 through the clip, seeded on frame 0 with a box (and a point inside) per piece of the region; the union of
    the masks over time is what is saved (`union`, uint8, the clip's size)."""
    import cv2
    from . import reveal
    from .backends import comfy
    from PIL import Image
    T, H, W, _ = frames.shape
    s = min(1.0, 640 / max(H, W))
    tw, th = max(32, round(W * s / 2) * 2), max(32, round(H * s / 2) * 2)
    small = np.stack([cv2.resize(f, (tw, th), interpolation=cv2.INTER_AREA) for f in frames])
    clip = ctx.work / f"track_in_{out.stem[len('track_'):]}.mp4"
    encode_h264(small, clip, crf=12)
    sm = cv2.resize(seed, (tw, th), interpolation=cv2.INTER_LINEAR) > 127
    n, lab, stats, cent = cv2.connectedComponentsWithStats(sm.astype(np.uint8), connectivity=8)
    prompts = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < max(24, 0.02 * stats[1:, cv2.CC_STAT_AREA].max()):
            continue
        x, y, w, h = (int(stats[i, k]) for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        dist = cv2.distanceTransform((lab == i).astype(np.uint8), cv2.DIST_L2, 3)
        py, px = np.unravel_index(int(dist.argmax()), dist.shape)
        prompts.append({"box": [x / tw, y / th, (x + w) / tw, (y + h) / th], "points": [[px / tw, py / th]], "labels": [1]})
    if not prompts:
        raise BuildError("no region to track")
    reveal._need_nodes(log)
    log(f"  tracking the moving part through the clip (SAM 2.1, {len(prompts)} object(s), {T} frames)")
    name = comfy.upload(str(clip))
    images = comfy.run(reveal.track_graph(name, 0, prompts, "large", f"studio/cine_{ctx.section_id.split('/')[-1]}", 0, T - 1), poll=2)
    got = Path(comfy.fetch(images, str(ctx.work / "track_png")))
    try:
        files = sorted(got.glob("*.png"))
        if len(files) != T:
            raise BuildError(f"the tracker returned {len(files)} masks for {T} frames")
        m = np.stack([np.asarray(Image.open(p).convert("L")) for p in files])
    finally:
        shutil.rmtree(got, ignore_errors=True)
    union = m.max(axis=0)
    area0, areaU = float((m[0] > 127).mean()), float((union > 127).mean())
    if area0 < 1e-4 or areaU > 0.9:               # the tracker lost it, or took the picture: keep nothing of it
        raise BuildError(f"the tracker's masks are not usable (first frame {area0:.2%}, union {areaU:.2%})")
    union = cv2.resize(union, (W, H), interpolation=cv2.INTER_LINEAR)
    np.savez_compressed(out, union=union)


# ---------------------------------------------------------------- the page's side

def page_entry(built: Built, media_url: Callable[[Path], str]) -> dict:
    """What the page needs to play it, for the `data-cine` attribute: the files, and where the video sits on the still."""
    x0, y0, x1, y1 = built["box"]
    return {"v": media_url(built["video"]), "m": media_url(built["mask"]),
            "b": [round(x0, 5), round(y0, 5), round(x1 - x0, 5), round(y1 - y0, 5)],
            "r": round(built["still"][0] / built["still"][1], 5), "fps": FPS}


def summary(rep: dict) -> str:
    """One readable line per cinemagraph, for the CLI and the build log."""
    lp = rep["loop"]
    return (f"{rep['moves']}: {rep['seconds']}s {rep['model']} loop ({lp['mode']}, {lp['closed_by']}), seam x{lp['encoded']['ratio']} "
            f"{'ok' if lp['seamless'] else 'VISIBLE'}, {rep['mask']['share_of_still']:.1%} of the picture moves, "
            f"outside the mask max change {rep['held']['max_change_outside_mask']}, {rep['bytes'] / 1024:.0f} KB")
