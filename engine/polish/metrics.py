"""The measurements behind `studio inspect`: pure numpy / OpenCV functions on frames, no project knowledge.

Every measurement is written so it can be said in a sentence:

  edge width      how many pixels wide the sharp edges are (at 1920 px across). Clean linework or a clean photo is
                  1 to 2.5 px; a frame that was enlarged from fewer pixels has soft edges of 3 px and more.
  fine detail     the energy a frame holds at a third of its pixel resolution, against its coarse structure, measured on
                  its busiest parts in the frequency domain. A picture enlarged from fewer pixels has almost none (it
                  was never drawn that finely); sharp footage and sharp drawings keep it. Content-independent, unlike an
                  edge width, so a soft-focus photograph is not mistaken for an upscale.
  rim fraction    of the clean edges (flat on both sides) the share with a bright rim or seam beside them: the halo,
                  the double edge and the sharpening ring that a depth warp or a cut-out leaves along an edge.
  hatch share     of all the visible structure in a frame, the share that is weak texture (hatching, pencil, grain)
                  rather than strong lines: a clean ink drawing is mostly lines, a pencil sketch is mostly hatching.
  warp residual   what is left of the change between two frames after the picture is moved by its optical flow.
                  Motion (a walking person, a camera push) is explained by the flow; things that appear, dissolve or
                  rearrange are not. Low = it moved, high = it changed.

Frames are BGR uint8 (OpenCV order) unless a name says gray.
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage as ndi

REF_W = 1920          # edge widths are quoted as if the frame were this many pixels across
FLOW_W = 384          # optical flow runs at this width
STYLE_W = 640         # style statistics run at this width


# ---------------------------------------------------------------- small helpers

def gray_f32(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)


def resize_w(img: np.ndarray, w: int) -> np.ndarray:
    h = max(1, round(img.shape[0] * w / img.shape[1]))
    if w == img.shape[1]:
        return img
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA if w < img.shape[1] else cv2.INTER_LINEAR)


def _sample(img: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return ndi.map_coordinates(img, [y, x], order=1, mode="nearest")


def clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def ramp(x: float, ok: float, bad: float) -> float:
    """0 at `ok` (or below), 1 at `bad` (or above), linear between; also works when bad < ok (lower is worse)."""
    if x is None or x != x:
        return 0.0
    return clip01((x - ok) / (bad - ok))


# ---------------------------------------------------------------- edges: width and rims

K = 12                                     # profile half-length in pixels
MIN_CONTRAST = 40.0                        # an edge counts for width when its two sides differ by this many levels
RIM_CONTRAST = 70.0                        # ... for the rim test, which also needs both sides flat
MAX_EDGES = 60000                          # edge pixels profiled per frame (a fixed random subset)
_RNG = np.random.default_rng(7)


def edge_stats(gray: np.ndarray, want_points: bool = False) -> dict:
    """Edge width and rim fraction of one frame (gray float32). The frame is looked at as `REF_W` pixels across: bigger
    frames are shrunk first, smaller ones keep their pixels and their widths are scaled to REF_W.

    width        median edge width in px at REF_W: peak-gradient width of every clean step edge (contrast / steepest slope,
                 the sigma of the blur times 2.5)
    width_p25    the sharpest quarter of the edges
    n_edges      how many clean edges that was (a measure of how much there is to judge: a blank frame has few)
    rim          share of flat-sided strong edges whose bright side has a bright rim or seam (see module doc)
    n_rim        how many edges the rim share is a share of
    aniso        width across vertical edges / width across horizontal ones (1 = the same; far from 1 = smeared one way)
    """
    h, w = gray.shape
    if w > REF_W:
        gray = cv2.resize(gray, (REF_W, round(h * REF_W / w)), interpolation=cv2.INTER_AREA)
        h, w = gray.shape
    scale = REF_W / w
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    mag = np.hypot(gx, gy)
    ys, xs = np.nonzero(mag > 8.0)
    out = {"width": None, "width_p25": None, "n_edges": 0, "rim": None, "n_rim": 0, "aniso": None, "points": []}
    if len(ys) < 200:
        return out
    if len(ys) > MAX_EDGES:
        pick = _RNG.choice(len(ys), MAX_EDGES, replace=False)
        ys, xs = ys[pick], xs[pick]
    m = mag[ys, xs]
    ux, uy = gx[ys, xs] / (m + 1e-6), gy[ys, xs] / (m + 1e-6)
    # non-maximum suppression along the gradient: one pixel per edge
    keep = (m >= _sample(mag, xs + ux, ys + uy)) & (m >= _sample(mag, xs - ux, ys - uy))
    ys, xs, m, ux, uy = ys[keep], xs[keep], m[keep], ux[keep], uy[keep]
    if len(ys) < 100:
        return out
    ks = np.arange(-K, K + 1, dtype=np.float32)
    prof = np.stack([_sample(gray, xs + k * ux, ys + k * uy) for k in ks], 1)
    lo_side, hi_side = prof[:, : 4], prof[:, -4:]
    signed = hi_side.mean(1) - lo_side.mean(1)
    contrast = np.abs(signed)

    strong = contrast >= MIN_CONTRAST
    if strong.sum() >= 50:
        wd = contrast[strong] / m[strong] * scale
        out["width"] = float(np.median(wd))
        out["width_p25"] = float(np.percentile(wd, 25))
        out["n_edges"] = int(strong.sum())
        horiz = strong & (np.abs(uy) > 0.8)          # gradient points up or down: a horizontal edge
        vert = strong & (np.abs(ux) > 0.8)
        if horiz.sum() >= 30 and vert.sum() >= 30:
            wh = np.median(contrast[horiz] / m[horiz]); wv = np.median(contrast[vert] / m[vert])
            out["aniso"] = float(wv / max(wh, 1e-3))

    # rim: orient every profile so it climbs from the dark side to the light side
    flip = signed < 0
    p = np.where(flip[:, None], prof[:, ::-1], prof)
    lo_p, hi_p = p[:, :4], p[:, -4:]
    flat = (np.abs(signed) >= RIM_CONTRAST) & (lo_p.std(1) < 5.0) & (hi_p.std(1) < 5.0)
    if flat.sum() >= 50:
        light = np.median(hi_p[flat], 1)
        over = p[flat][:, K - 1: K + 9].max(1) - light
        A = np.abs(signed[flat])
        bad = over > np.maximum(16.0, 0.12 * A)
        out["rim"] = float(bad.mean())
        out["n_rim"] = int(flat.sum())
        if want_points and bad.any():
            fy, fx = ys[flat][bad], xs[flat][bad]
            out["points"] = np.stack([fx / w, fy / h], 1).astype(np.float32)   # 0-1 in the frame
    return out


# ---------------------------------------------------------------- fine detail (frequency domain)

_T = 256
_WIN = np.outer(np.hanning(_T), np.hanning(_T)).astype(np.float32)
_RAD = np.hypot(np.fft.fftfreq(_T)[:, None], np.fft.fftfreq(_T)[None, :])
_NB = 32
_BIN = np.minimum((_RAD / 0.5 * _NB).astype(int), _NB)          # radius 0-0.5 cycles/px in 32 bins (corners go to bin 32)
_COUNT = np.bincount(_BIN.ravel(), minlength=_NB + 1).astype(np.float64)
_CENT = (np.arange(_NB) + 0.5) / _NB * 0.5


def spectral_detail(gray: np.ndarray) -> dict:
    """Fine-detail index of a frame (gray float32): mean power at 0.30-0.45 cycles/pixel over mean power at 0.03-0.08,
    averaged over the busiest quarter of 256 px tiles (so a sharp subject in a blurry frame counts as sharp).

    detail   the index. Clean ink and wash 0.002-0.006, sharp photo 0.0002-0.003, a picture enlarged 3.5x or more
             0.00003-0.0001 (test page: the hands close-up, the boots, the end of the zoom)
    busy     mean gradient of those tiles (levels per pixel); tiny means there was nothing to judge
    """
    h, w = gray.shape
    if w > REF_W:
        gray = cv2.resize(gray, (REF_W, round(h * REF_W / w)), interpolation=cv2.INTER_AREA)
        h, w = gray.shape
    ny, nx = h // _T, w // _T
    out = {"detail": None, "busy": 0.0}
    if ny < 1 or nx < 1:
        return out
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    e = np.hypot(gx, gy)[: ny * _T, : nx * _T].reshape(ny, _T, nx, _T).mean((1, 3))
    order = np.argsort(e.ravel())[::-1][: max(4, min(24, ny * nx // 4))]
    acc = np.zeros(_NB + 1)
    for o in order:
        y, x = divmod(int(o), nx)
        t = gray[y * _T:(y + 1) * _T, x * _T:(x + 1) * _T]
        P = np.abs(np.fft.fft2((t - t.mean()) * _WIN)) ** 2
        acc += np.bincount(_BIN.ravel(), weights=P.ravel(), minlength=_NB + 1)
    acc = (acc / np.maximum(_COUNT, 1))[:_NB] / len(order)
    lo = acc[(_CENT > 0.03) & (_CENT < 0.08)].mean()
    hi = acc[(_CENT > 0.30) & (_CENT < 0.45)].mean()
    out["busy"] = float(e.ravel()[order].mean())
    if lo > 1e-6:
        out["detail"] = float(hi / lo)
    return out


# ---------------------------------------------------------------- style statistics

def style_stats(bgr: np.ndarray) -> dict:
    """Look statistics of one frame, at STYLE_W across.

    line    share of pixels on a strong edge (outlines)           fine   share on any visible structure
    hatch   (fine - line) / fine: how much of the structure is weak texture (hatching, pencil, grain)
    tone    luma histogram, 8 bins, sums to 1                      sat    mean saturation 0-1
    grain   noise in the flat areas (levels)                       light  mean luma 0-255
    """
    f = resize_w(bgr, STYLE_W)
    g = gray_f32(f)
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    mag = np.hypot(gx, gy)
    line = float((mag > 12).mean())
    fine = float((mag > 4).mean())
    hist = np.histogram(g, bins=8, range=(0, 256))[0] / g.size
    hp = g - cv2.GaussianBlur(g, (0, 0), 1.5)
    flat = mag < 3
    grain = float(hp[flat].std()) if flat.sum() > 1000 else float("nan")
    return {"line": line, "fine": fine, "hatch": (fine - line) / fine if fine > 0.01 else float("nan"),
            "tone": hist.astype(np.float32), "sat": float(hsv[..., 1].mean() / 255.0), "grain": grain,
            "light": float(g.mean())}


# ---------------------------------------------------------------- two frames: flow, residual, camera

_GRID: dict = {}


def _grid(h: int, w: int):
    if (h, w) not in _GRID:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        _GRID[(h, w)] = (yy, xx)
    return _GRID[(h, w)]


def step_stats(a: np.ndarray, b: np.ndarray) -> dict:
    """What happened between two gray uint8 frames (FLOW_W across).

    plain    mean absolute difference, levels
    area     the share of the picture that changed by more than 24 levels (a pop changes most of it, an event a corner)
    resid    the same after frame b is moved back by the optical flow (what motion cannot explain), levels
    local    the share of pixels that motion cannot explain by more than 25 levels
    mot      how much the picture moved: mean flow length (px at FLOW_W)
    """
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 4, 15, 3, 5, 1.2, 0)
    h, w = a.shape
    yy, xx = _grid(h, w)
    af = a.astype(np.float32)
    bf = b.astype(np.float32)
    wb = cv2.remap(bf, xx + flow[..., 0], yy + flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    r = np.abs(af - wb)[6:-6, 6:-6]
    diff = np.abs(af - bf)[6:-6, 6:-6]
    plain = float(diff.mean())
    mot = float(np.hypot(flow[..., 0], flow[..., 1]).mean())
    return {"plain": plain, "resid": float(r.mean()), "local": float((r > 25).mean()), "area": float((diff > 24).mean()),
            "mot": mot}


def luma_mean(gray_u8: np.ndarray) -> float:
    return float(gray_u8.mean())


# ---------------------------------------------------------------- two shots meeting: the join

def edge_map(bgr: np.ndarray, w: int = 480) -> np.ndarray:
    g = cv2.GaussianBlur(gray_f32(resize_w(bgr, w)), (0, 0), 1.2)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return np.hypot(gx, gy)


def misalignment(a: np.ndarray, b: np.ndarray, w: int = FLOW_W) -> dict:
    """How far out of line two frames are: the optical flow that would lay one on the other.

    disp     the 90th percentile flow length, in pixels of a 1920 px frame (what a viewer sees as the gap between the two
             images of a double exposure); mean is the average over the frame
    """
    ga = cv2.cvtColor(resize_w(a, w), cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(resize_w(b, w), cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 4, 15, 3, 5, 1.2, 0)
    mag = np.hypot(flow[..., 0], flow[..., 1])
    k = REF_W / w
    return {"disp": float(np.percentile(mag, 90) * k), "disp_mean": float(mag.mean() * k)}


def mismatch(a: np.ndarray, b: np.ndarray, w: int = 480) -> dict:
    """How two frames that are about to be dissolved into each other differ.

    edges    share of the edge energy that is not in both pictures (0 = the same drawing, 1 = nothing in common); it
             saturates after a pixel or two of misalignment, so it is reported but `misalignment` scores
    luma     mean absolute brightness difference, levels
    chroma   mean colour difference (Lab a/b), levels
    """
    a, b = resize_w(a, w), resize_w(b, w)
    ea, eb = edge_map(a, w), edge_map(b, w)
    ea[ea < 3] = 0
    eb[eb < 3] = 0
    den = float(np.maximum(ea, eb).sum())
    edges = float(np.abs(ea - eb).sum() / den) if den > 1e-3 else 0.0
    la = cv2.cvtColor(a, cv2.COLOR_BGR2LAB).astype(np.float32)
    lb = cv2.cvtColor(b, cv2.COLOR_BGR2LAB).astype(np.float32)
    return {"edges": edges, "luma": float(np.abs(la[..., 0] - lb[..., 0]).mean()),
            "chroma": float(np.hypot(la[..., 1] - lb[..., 1], la[..., 2] - lb[..., 2]).mean())}
