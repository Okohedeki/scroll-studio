"""light: the pieces of "light as the scroll" that are not a scene builder: relighting one place into several times of
day with the geometry locked, measuring and correcting drift, and the maps the browser's light-aware transition reads.

The pipeline (engine/scenes/light.py runs it, cached per stage):

  relight     Qwen-Image-Edit gets the world picture and an instruction that changes only the light (light_presets.py).
              The editor redraws a little everywhere, so what comes back is not yet the same place.
  measure     structure, not colour: both pictures are reduced to a band-passed LOG-luminance map (a change of light is a
              multiplication, which log turns into an offset the band-pass removes), normalised by local contrast. The
              displacement between the two maps (dense optical flow, DIS) and the agreement of their edges say how far
              the place moved. `drift` below is that displacement in pixels at 1024 across. The residual after the warp is NOT the measure of
              drift (a warp can match anything, bending the place into shape): the displacement itself and the strain of
              the correction are.
  align       the flow, smoothed, is the correction: the relit picture is warped back onto the world's geometry, so a
              window is where the window was. The residual after the warp is measured again and reported.
  retry       a relight whose drift stays above the limit is redone with another seed; the best attempt is kept.
  ratio       between neighbouring times, the low-frequency lighting change (an edge-aware, guided low-pass of B over A,
              log-encoded) lets the browser carry the whole picture's light from one time to the other smoothly, so that
              only the mid-frequency detail (shadows) is switched by the sweeping front, not the brightness.
  lamps       what turned on (or off) between two times: small bright features present in one and not the other (white
              top-hat), optionally confined to regions named in the spec (engine/region.py), cut into connected
              lights each given its own delay, plus a halo. The browser switches them one by one with a glow.
  tokens      the section's ink, accent and shade colours, measured from each time's picture.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

VERSION = 5                # bump when the maps (ratio, lamps, flow, tokens) would come out differently for the same inputs
RELIGHT_VERSION = 1        # bump when a relight or its alignment would come out differently for the same inputs (re-renders every time of day)
MEASURE_W = 1024           # width at which structure is compared, so drift means the same on any picture
MAX_FLOW = 28.0            # a correction larger than this (px at MEASURE_W) is not trusted: it is a different picture
FLOW_RANGE = 24.0          # the pair flow texture covers +-this many px at MEASURE_W


# ---------------------------------------------------------------- small helpers

def load_rgb(path: Path, size: Optional[tuple[int, int]] = None) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    if size is not None and im.size != tuple(size):
        im = im.resize(tuple(size), Image.LANCZOS)
    return np.asarray(im)


def luma(rgb: np.ndarray) -> np.ndarray:
    """Rec. 709 luma of an 8-bit RGB array, 0-1."""
    return (rgb[..., :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)) / 255.0


def _small(rgb: np.ndarray, width: int = MEASURE_W) -> np.ndarray:
    h, w = rgb.shape[:2]
    if w == width:
        return rgb
    return cv2.resize(rgb, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------- structure: what does not change with the light

def structure(rgb: np.ndarray) -> np.ndarray:
    """A light-invariant picture of the place's structure at MEASURE_W across, float32, roughly -3..3. The log of
    luminance makes a change of light additive; a difference of Gaussians removes the slow part of it and keeps edges; a
    local contrast normalisation makes a dim night picture's edges as strong as a bright noon picture's."""
    s = _small(rgb)
    ln = np.log(luma(s) + 0.03)
    dog = cv2.GaussianBlur(ln, (0, 0), 1.0) - cv2.GaussianBlur(ln, (0, 0), 3.2)
    energy = cv2.GaussianBlur(np.abs(dog), (0, 0), 9.0)
    return (dog / (energy + 0.02)).astype(np.float32)


def _u8(st: np.ndarray) -> np.ndarray:
    return np.clip(st * 40 + 128, 0, 255).astype(np.uint8)


def flow(base_st: np.ndarray, cand_st: np.ndarray) -> np.ndarray:
    """Dense displacement (dx, dy) at MEASURE_W with base(x) ~ cand(x + flow(x)), from the two structure maps."""
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setFinestScale(1)
    dis.setPatchSize(12)
    dis.setPatchStride(6)
    dis.setVariationalRefinementIterations(8)
    f = dis.calc(_u8(base_st), _u8(cand_st), None)
    return np.clip(f, -MAX_FLOW, MAX_FLOW)


def _weights(base_st: np.ndarray) -> np.ndarray:
    """Where the structure is strong enough for a displacement to mean something (flat sky and water say nothing)."""
    e = cv2.GaussianBlur(np.abs(base_st), (0, 0), 2.0)
    return np.clip((e - 0.35) / 0.5, 0, 1)


def displacement(base_st: np.ndarray, f: np.ndarray) -> tuple[float, float]:
    """Mean and 90th-percentile displacement in px (at MEASURE_W) over the structured pixels."""
    mag = np.hypot(f[..., 0], f[..., 1])
    w = _weights(base_st)
    if w.sum() < 50:
        return 0.0, 0.0
    mean = float((mag * w).sum() / w.sum())
    sel = mag[w > 0.5]
    return mean, float(np.percentile(sel, 90)) if sel.size else mean


def strain(base_st: np.ndarray, f: np.ndarray, sigma: float = 5.0) -> float:
    """How much the correction stretches and shears the picture (mean of the flow's own gradient over the structured
    pixels; 0 is a pure shift, 0.1 means a tenth of a pixel of stretch per pixel): a high value is a place being bent
    into shape rather than nudged back, the melted look."""
    fs = [cv2.GaussianBlur(f[..., i], (0, 0), sigma) for i in (0, 1)]
    g = np.zeros(fs[0].shape, np.float32)
    for c in fs:
        gy, gx = np.gradient(c)
        g += gx * gx + gy * gy
    g = np.sqrt(g)
    w = _weights(base_st)
    return float((g * w).sum() / w.sum()) if w.sum() > 50 else 0.0


def edge_agreement(a_st: np.ndarray, b_st: np.ndarray, tol: int = 2, keep: float = 0.10) -> float:
    """F-score of the strongest `keep` share of structure pixels of each picture, matched within `tol` px."""
    ea, eb = np.abs(a_st), np.abs(b_st)
    ta, tb = np.quantile(ea, 1 - keep), np.quantile(eb, 1 - keep)
    A, B = ea >= ta, eb >= tb
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol + 1, 2 * tol + 1))
    Ad, Bd = cv2.dilate(A.astype(np.uint8), k) > 0, cv2.dilate(B.astype(np.uint8), k) > 0
    prec = float((B & Ad).sum() / max(1, B.sum()))
    rec = float((A & Bd).sum() / max(1, A.sum()))
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


def warp(rgb: np.ndarray, f: np.ndarray, sigma: float = 5.0) -> np.ndarray:
    """Pull `rgb` (the candidate, full size) onto the world with a flow estimated at MEASURE_W (smoothed, scaled up)."""
    h, w = rgb.shape[:2]
    fs = np.stack([cv2.GaussianBlur(f[..., i], (0, 0), sigma) for i in (0, 1)], -1)
    s = w / f.shape[1]
    fx = cv2.resize(fs[..., 0], (w, h), interpolation=cv2.INTER_CUBIC) * s
    fy = cv2.resize(fs[..., 1], (w, h), interpolation=cv2.INTER_CUBIC) * s
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(rgb, gx + fx, gy + fy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def measure(world: np.ndarray, cand: np.ndarray, base_st: Optional[np.ndarray] = None) -> dict:
    """How far `cand` is from being the same place as `world`: displacement (mean, p90, px at 1024 across) and edge
    agreement (0-1), before any correction."""
    base_st = structure(world) if base_st is None else base_st
    st = structure(cand)
    f = flow(base_st, st)
    mean, p90 = displacement(base_st, f)
    return {"drift": round(mean, 3), "drift_p90": round(p90, 3), "edges": round(edge_agreement(base_st, st), 4),
            "strain": round(strain(base_st, f), 4)}


def fit_affine(base_st: np.ndarray, cand_st: np.ndarray, f: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """The global move (scale, shear, shift) that best explains where the editor put things: an affine map at MEASURE_W
    from the world's coordinates to the candidate's, fitted robustly (RANSAC) to the dense flow at structured pixels.
    A relight that is zoomed a few percent and shifted a few pixels, as Qwen-Image-Edit's are, is mostly this, and undoing
    it bends nothing. None when too little structure agrees."""
    f = flow(base_st, cand_st) if f is None else f
    wt = _weights(base_st)
    ys, xs = np.nonzero(wt > 0.6)
    if xs.size < 400:
        return None
    sel = np.random.default_rng(0).choice(xs.size, min(20000, xs.size), replace=False)
    src = np.stack([xs[sel], ys[sel]], 1).astype(np.float32)
    dst = src + f[ys[sel], xs[sel]]
    M, inl = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0, maxIters=3000)
    if M is None or float(inl.mean()) < 0.08:
        return None
    return M.astype(np.float32)


def apply_affine(rgb: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Pull `rgb` (the candidate, full size) onto the world with a map fitted at MEASURE_W."""
    h, w = rgb.shape[:2]
    Ms = M.copy()
    Ms[:, 2] *= w / MEASURE_W
    return cv2.warpAffine(rgb, Ms, (w, h), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)


def align(world: np.ndarray, cand: np.ndarray, base_st: Optional[np.ndarray] = None, mode: str = "affine",
          passes: int = 2) -> tuple[np.ndarray, dict]:
    """Put `cand` back where the world has things. Returns the picture and a report of the drift and edge agreement before
    (raw) and after (aligned), and the global move that was undone.

    affine (the default): only the global move is undone: lines stay straight, nothing is bent. What remains is the
        editor's own redrawing, which the page's transition glides over (the flow between neighbouring times).
    flow: after the global move, a few passes of dense optical flow pull local structure onto the world as well. It matches
        edges better and bends things: windows and roof lines wobble where the editor redrew them. For small drift only.
    none: measure only."""
    base_st = structure(world) if base_st is None else base_st
    raw = measure(world, cand, base_st)
    best, report, move = cand, dict(raw), None
    if mode != "none":
        M = fit_affine(base_st, structure(cand))
        if M is not None:
            moved = apply_affine(cand, M)
            m = measure(world, moved, base_st)
            if m["drift"] < raw["drift"] - 1e-3:
                best, report = moved, dict(m)
                move = {"scale": [round(float(M[0, 0]), 4), round(float(M[1, 1]), 4)], "shear": [round(float(M[0, 1]), 4), round(float(M[1, 0]), 4)],
                        "shift": [round(float(M[0, 2]), 2), round(float(M[1, 2]), 2)]}
        if mode == "flow":
            cur = best
            for _ in range(passes):
                nxt = warp(cur, flow(base_st, structure(cur)))
                m = measure(world, nxt, base_st)
                if m["drift"] + 2 * (1 - m["edges"]) < report["drift"] + 2 * (1 - report["edges"]) - 1e-4:
                    best, report, cur = nxt, dict(m), nxt
                else:
                    break
    return best, {"raw": raw, "aligned": {k: report[k] for k in ("drift", "drift_p90", "edges", "strain")}, "move": move}


def pair_flow(a: np.ndarray, b: np.ndarray, width: int = 480) -> tuple[np.ndarray, dict]:
    """How the structure of picture `a` is displaced in picture `b` (neighbouring times of the same place), for the page to
    glide along as it changes from one to the other instead of cross-fading doubled edges. RGB uint8, `width` across:
    R, G the displacement (dx, dy in px at MEASURE_W across, +-FLOW_RANGE, 128 is none), B the confidence (where there is
    structure to measure; flat sky and water say nothing, so they are left where they are). Plus the mean glide in px."""
    sa, sb = structure(a), structure(b)
    f = flow(sa, sb)
    f = np.stack([cv2.GaussianBlur(f[..., i], (0, 0), 4.0) for i in (0, 1)], -1)
    conf = cv2.GaussianBlur(_weights(sa) * _weights(sb) ** 0.5, (0, 0), 4.0)
    conf = np.clip(conf * 1.6, 0, 1)
    f = np.clip(f, -FLOW_RANGE, FLOW_RANGE)
    h, w = sa.shape
    size = (width, max(1, round(h * width / w)))
    enc = np.dstack([np.clip(f[..., 0] / (2 * FLOW_RANGE) + 0.5, 0, 1), np.clip(f[..., 1] / (2 * FLOW_RANGE) + 0.5, 0, 1), conf])
    out = (cv2.resize(enc, size, interpolation=cv2.INTER_AREA) * 255).astype(np.uint8)
    mag = np.hypot(f[..., 0], f[..., 1])
    glide = float((mag * conf).sum() / max(float(conf.sum()), 1e-6))
    return out, {"glide": round(glide, 3), "confidence": round(float(conf.mean()), 3)}


# ---------------------------------------------------------------- relighting through ComfyUI

def relight(world_png: Path, instruction: str, seed: int, steps: int, out: Path, tag: str, log=print, denoise: float = 1.0) -> Path:
    """One Qwen-Image-Edit pass over the whole world picture; the result saved at `out` at the editor's own size."""
    import shutil
    from .backends import comfy
    from .project import BuildError
    if not comfy.alive():
        raise BuildError(f"light: relighting needs ComfyUI (Qwen-Image-Edit), which is not running at {comfy.COMFY}.")
    comfy.free()
    name = comfy.upload(str(world_png))
    images = comfy.run(comfy.build_qwen_edit_graph([name], instruction, seed, steps, prefix=f"studio/light_{tag}", denoise=denoise), poll=2)
    tmp = comfy.fetch(images, str(out.parent / f"_light_{tag}"))
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(Path(tmp) / "0001.png"), out)
    shutil.rmtree(tmp, ignore_errors=True)
    comfy.free()
    return out


def relight_locked(world: np.ndarray, world_png: Path, instruction: str, seeds: list[int], steps: int, max_drift: float,
                   align_mode: str, work: Path, tag: str, log=print, denoise: float = 1.0) -> tuple[np.ndarray, dict]:
    """Relight until the place holds still: try each seed, undo the global move, keep the first whose remaining drift is
    within `max_drift` (else the best of them). Returns the picture (at the world's size) and a report of every attempt."""
    base_st = structure(world)
    attempts, best, best_img = [], None, None
    for i, seed in enumerate(seeds):
        raw_png = work / f"_raw_{tag}_{seed}.png"
        relight(world_png, instruction, seed, steps, raw_png, f"{tag}_{seed}", log, denoise)
        cand = load_rgb(raw_png, (world.shape[1], world.shape[0]))
        raw_png.unlink(missing_ok=True)
        fixed, rep = align(world, cand, base_st, align_mode)
        rep["seed"] = seed
        attempts.append(rep)
        log(f"    seed {seed}: the editor moved the place {rep['raw']['drift']:.2f}px; after undoing its global move "
            f"{rep['aligned']['drift']:.2f}px (edges {rep['raw']['edges']:.2f} -> {rep['aligned']['edges']:.2f})")
        # score: what remains of the drift, and how well the edges agree
        score = rep["aligned"]["drift"] - 4 * rep["aligned"]["edges"]
        if best is None or score < best[0]:
            best, best_img = (score, rep), fixed
        if rep["aligned"]["drift"] <= max_drift:
            break
    report = dict(best[1])
    report["attempts"] = attempts
    report["ok"] = report["aligned"]["drift"] <= max_drift
    return best_img, report


# ---------------------------------------------------------------- the maps the browser reads

RATIO_W = 480              # the light-change field is smooth: a small texture, bilinear in the browser
LAMP_W = 960               # lamp maps: half of a 1920 picture, windows stay crisp
RATIO_RANGE = 6.0          # stops covered by the 8-bit log encoding of the ratio (+-3)


def _lin(rgb: np.ndarray) -> np.ndarray:
    return np.power(rgb.astype(np.float32) / 255.0, 2.2)


def ratio_map(world: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """How the low-frequency light changes from picture `a` to `b`: log2(lowpass(b) / lowpass(a)) per channel, linear
    light, an edge-aware low-pass guided by the world's own luminance (so the horizon, a wall's edge or the water line
    keep their own ratio instead of bleeding), encoded 0-255 over +-3 stops. RATIO_W across."""
    from .freeze import guided_filter
    h, w = a.shape[:2]
    size = (RATIO_W, max(1, round(h * RATIO_W / w)))
    guide = cv2.resize(luma(world), size, interpolation=cv2.INTER_AREA)
    out = []
    for c in range(3):
        la = cv2.resize(_lin(a)[..., c], size, interpolation=cv2.INTER_AREA)
        lb = cv2.resize(_lin(b)[..., c], size, interpolation=cv2.INTER_AREA)
        ga = guided_filter(guide, la, 10, 0.012)
        gb = guided_filter(guide, lb, 10, 0.012)
        out.append(np.log2((np.maximum(gb, 0) + 0.004) / (np.maximum(ga, 0) + 0.004)))
    r = np.stack(out, -1)
    return np.clip((r / RATIO_RANGE + 0.5) * 255, 0, 255).astype(np.uint8)


def depth_map(world: np.ndarray, model: str = "small", width: int = 960) -> np.ndarray:
    """Depth Anything V2 on the world, edge-aligned and softened for parallax (engine/freeze.prepare_depth), 8-bit,
    `width` across. 255 is near."""
    from .backends import depth as depthmod
    from .freeze import prepare_depth
    d = depthmod.estimate(Image.fromarray(world), model)
    h, w = world.shape[:2]
    size = (width, max(1, round(h * width / w)))
    return np.clip(prepare_depth(d, world, size) * 255, 0, 255).astype(np.uint8)


def sky_mask_fallback(world: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """The sky without a model: the far, smooth, upper part of the picture (0-1 float at the depth map's size)."""
    h, w = depth.shape
    small = cv2.resize(world, (w, h), interpolation=cv2.INTER_AREA)
    grad = cv2.GaussianBlur(np.hypot(*np.gradient(cv2.GaussianBlur(luma(small), (0, 0), 2.0))), (0, 0), 6.0)
    m = ((depth < 40) & (grad < 0.012)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_TOP] < h * 0.08 and stats[i, cv2.CC_STAT_AREA] > h * w * 0.03:
            keep[lab == i] = 1
    return cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 3.0)


def _top_hat(l: np.ndarray, k: int) -> np.ndarray:
    return l - cv2.morphologyEx(l, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))


def lamp_map(a: np.ndarray, b: np.ndarray, sky: Optional[np.ndarray] = None, allow: Optional[np.ndarray] = None,
             glow: float = 1.0, grow: int = 2, seed: int = 5, turns_on: Optional[bool] = None) -> Optional[dict]:
    """The lights that switch between pictures `a` and `b` (the same place at two times).

    A lamp is a small, bright, warm feature that one picture has and the other lacks (white top-hat, which keeps
    features smaller than a window and drops the sky and whole walls). Evidence in each direction is gathered; the
    direction with more of it says whether lights come on (b has them) or go off (a has them) unless `turns_on` says
    (the times' own `lit` flags), and only that direction counts, so a white sail that is brighter by day is not a lamp. `sky` (0-1, any size) keeps stars and the sun's
    glare out; `allow` (0-1, the picture's size) confines the lights to regions the spec names. Each connected light
    gets its own delay (0-1) so the browser turns them on one by one. Returns {"map": RGBA uint8, "color": "#rrggbb",
    "count": n, "turns_on": bool} or None when nothing switches. R is the cut-out (soft), G the delay, B the halo."""
    A, B = _small(a, LAMP_W), _small(b, LAMP_W)
    h, w = A.shape[:2]
    la, lb = luma(A), luma(B)
    k = max(15, (w // 40) | 1)
    ta, tb = _top_hat(la, k), _top_hat(lb, k)

    def warm(rgb):       # lit glass and bulbs are warm: red over blue
        f = rgb.astype(np.float32)
        return np.clip((f[..., 0] - f[..., 2] * 0.85) / 90.0 + 0.35, 0, 1)
    # Light that is EMITTED is what the change of ambient light cannot explain: scale each picture by the low-frequency
    # ratio between them (a window wall is darker at night; a lit window is not) and keep what is left over.
    lin_a, lin_b = np.power(la, 2.2), np.power(lb, 2.2)
    sig = w * 0.02
    ratio = (cv2.GaussianBlur(lin_b, (0, 0), sig) + 1e-4) / (cv2.GaussianBlur(lin_a, (0, 0), sig) + 1e-4)
    ratio = np.clip(ratio, 0.002, 500.0)
    on_ev = np.clip(lin_b - lin_a * ratio - 0.05, 0, None) * (tb > 0.1) * (0.4 + warm(B))
    off_ev = np.clip(lin_a - lin_b / ratio - 0.05, 0, None) * (ta > 0.1) * (0.4 + warm(A))
    if turns_on is None:
        turns_on = float(on_ev.sum()) >= float(off_ev.sum())
    ev = on_ev if turns_on else off_ev
    lit_rgb, lit_l = (B, lb) if turns_on else (A, la)
    mask = ev > 0.03
    if sky is not None:
        mask &= cv2.resize(sky.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR) < 0.5
    if allow is not None:
        al = cv2.resize(allow.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) > 0.2
        mask &= cv2.dilate(al.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    m = mask.astype(np.uint8)
    if grow:
        kk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * abs(grow) + 1, 2 * abs(grow) + 1))
        m = cv2.dilate(m, kk) if grow > 0 else cv2.erode(m, kk)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m)
    keep = np.zeros(n, bool)
    keep[1:] = (stats[1:, cv2.CC_STAT_AREA] >= 6) & (stats[1:, cv2.CC_STAT_AREA] <= w * h * 0.004)   # not a wall, not a speck
    m = keep[lab].astype(np.uint8)
    if int(m.sum()) < 30:
        return None
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m)
    rng = np.random.default_rng(seed)
    delay = np.zeros(n, np.float32)
    delay[1:] = rng.random(n - 1)
    soft = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 0.8)
    strength = cv2.dilate(ev * m, np.ones((5, 5), np.uint8))
    halo = cv2.GaussianBlur(m.astype(np.float32) * np.clip(strength * 4, 0.25, 1), (0, 0), w * 0.009)
    halo = np.clip(halo / max(float(halo.max()), 1e-6), 0, 1) ** 0.9
    lit = lit_rgb[m > 0].astype(np.float32).mean(axis=0)
    col = lit / max(float(lit.max()), 1.0)
    col = np.clip(0.55 * col + 0.45 * np.array([1.0, 0.7, 0.36]), 0, 1)
    out = np.dstack([np.clip(soft * 255, 0, 255), delay[lab] * 255, np.clip(halo * 255, 0, 255), np.full((h, w), 255)]).astype(np.uint8)
    return {"map": out, "color": "#" + "".join(f"{int(round(v * 255)):02x}" for v in col), "count": int(n - 1),
            "turns_on": bool(turns_on)}


# ---------------------------------------------------------------- the section's colours at one time of day

def tokens(rgb: np.ndarray) -> dict:
    """Ink, accent and shade colours for text set over this picture, contrast-checked like any theme surface
    (engine/compile/themes.py). Returns numbers the browser blends: bg (the shade), ink, em (the accent words), and the
    alphas of the two quieter text tiers. Also `dark`: the picture is dark, the ink light."""
    from .compile import themes as th
    h, w = rgb.shape[:2]
    zone = rgb[int(h * 0.28):int(h * 0.74), int(w * 0.03):int(w * 0.50)]
    y = float(luma(zone).mean())
    mean = rgb.reshape(-1, 3).astype(np.float32).mean(axis=0)
    meant = tuple(float(v) for v in mean)
    dark = y < 0.52
    if dark:
        bg = tuple(float(v) for v in np.clip(mean * 0.22 + np.array([4, 5, 9]), 0, 255))
        ink = th._mix((246.0, 241.0, 232.0), meant, 0.9)
    else:
        bg = th._mix((255.0, 252.0, 246.0), th._mix(meant, (255.0, 252.0, 246.0), 0.18), 0.55)
        ink = (24.0, 21.0, 19.0)
    # the accent: the colour of the light itself, from the brightest pixels, pushed to a readable saturation
    l = luma(rgb)
    top = rgb[l >= np.quantile(l, 0.985)].astype(np.float32).mean(axis=0)
    hsv = cv2.cvtColor(np.uint8([[np.clip(top, 0, 255)]]), cv2.COLOR_RGB2HSV)[0, 0].astype(np.float32)
    hsv[1] = max(hsv[1], 150)
    hsv[2] = 240 if dark else 120
    acc = tuple(float(v) for v in cv2.cvtColor(np.uint8([[hsv]]), cv2.COLOR_HSV2RGB)[0, 0])
    bg2 = th._mix(ink, bg, 0.06)
    bgs = [bg, bg2]
    a3 = th._min_alpha(ink, bgs, th.SMALL_TEXT, 0.44)
    a2 = max(th._min_alpha(ink, bgs, th.SMALL_TEXT, 0.68), min(1.0, round(a3 + 0.14, 2)))
    # accent words stay the colour of the light: move its brightness (not its hue) until it reads on the shade
    def readable(target):
        v = float(hsv[2])
        for _ in range(60):
            c = tuple(float(x) for x in cv2.cvtColor(np.uint8([[[hsv[0], hsv[1], v]]]), cv2.COLOR_HSV2RGB)[0, 0])
            if min(th.contrast(c, b) for b in bgs) >= target:
                return c
            v = v + 5 if dark else v - 5
            if not 20 <= v <= 255:
                break
        return th._readable_accent(acc, ink, bgs, target)
    em = readable(th.SMALL_TEXT)
    atext = em
    r = lambda c: [int(round(v)) for v in c]
    return {"bg": r(bg), "bg2": r(bg2), "ink": r(ink), "em": r(em), "accent": r(atext), "a2": a2, "a3": a3, "dark": bool(dark)}


def fog_color(rgb: np.ndarray, sky: Optional[np.ndarray] = None) -> list[int]:
    """The colour mist takes at this time: the sky's own average (the mist is the sky come down to the water), a little
    lifted; from the picture's top band when there is no sky mask."""
    h, w = rgb.shape[:2]
    if sky is not None and float(sky.mean()) > 0.02:
        m = cv2.resize(sky.astype(np.float32), (w // 4, h // 4), interpolation=cv2.INTER_AREA)
        small = cv2.resize(rgb, (w // 4, h // 4), interpolation=cv2.INTER_AREA).astype(np.float32)
        c = (small * m[..., None]).sum((0, 1)) / max(float(m.sum()), 1e-6)
    else:
        c = rgb[: max(1, h // 12)].reshape(-1, 3).astype(np.float32).mean(axis=0)
    c = c * 0.92 + 14
    return [int(round(float(v))) for v in np.clip(c, 0, 255)]


# ---------------------------------------------------------------- reports

def contact_sheet(times: list[dict], images: list[np.ndarray], out: Path, cols: int = 3) -> Path:
    """The times side by side with their id, clock and measured drift: what `studio light` writes for a first look."""
    from PIL import ImageDraw
    tw = 640
    th = round(tw * images[0].shape[0] / images[0].shape[1])
    rows = math.ceil(len(images) / cols)
    sheet = Image.new("RGB", (cols * tw, rows * (th + 26)), (16, 16, 18))
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(zip(times, images)):
        x, y = (i % cols) * tw, (i // cols) * (th + 26)
        sheet.paste(Image.fromarray(im).resize((tw, th), Image.LANCZOS), (x, y + 26))
        rep = t.get("report") or t
        al = rep.get("aligned") or {}
        d.text((x + 8, y + 7), f"{t['id']}  {t.get('clock', '')}  drift {al.get('drift', 0):.2f}px (raw {(rep.get('raw') or {}).get('drift', 0):.2f})  "
                               f"edges {al.get('edges', 1):.2f}", fill=(230, 230, 230))
    sheet.save(out, quality=90)
    return out
