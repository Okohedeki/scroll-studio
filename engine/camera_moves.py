"""camera_moves: named camera moves (`camera: dolly-in`) on generated beats.

A named move is a recipe for the keyed-camera pipeline of engine/camera_guide.py: instead of framing boxes, the move is a
rig, one camera per frame for the 2.5D renderer of engine/freeze.py (the view `cx, cy, w`, the lateral shift `sx, sy` and
the push `e` per unit of depth against the focus plane `f`, and a `roll`). The rig is flown through the start image's
depth to make the guide (the depth video LTX-2.3's IC-LoRA follows) and the pure-camera render (pinned along the way as
keyframes), exactly like keyed moves. What each recipe does, in the renderer's terms:

    static        nothing moves (a locked-off tripod shot): the guide holds the world still, the subjects stay free
    dolly-in      the view closes in on `at` (w 1 -> ~0.7) and near things grow faster than far ones (e > 0)
    dolly-out     dolly-in backwards: it starts close on `at` and pulls back to the whole picture
    crash-zoom    a lens zoom (no parallax: e = 0) that snaps from wide to ~2.6x in a fifth of the beat, then holds
    dolly-zoom    the vertigo shot: the subject at `at` keeps its size while the background swells and the foreground
                  shrinks (e from 0 to < 0 at a constant view: the push and the zoom cancel on the subject's plane)
    orbit-left    the camera arcs left around the subject (sx ramps up): near things slide right, far things left,
    orbit-right   the subject at the focus plane stays put; -right is the mirror
    crane-up      the camera rises (sy ramps up) tilting to keep the subject: near things sink, the background rises;
    crane-down    -down is the mirror
    fpv           a drone flying forward: a fast push (w 0.9 -> ~0.5, strong e) with a banking roll and a little sway
    whip-pan      a fast pan from one side of the picture to the other with motion blur in the guide
    push-through  a deep push (w -> ~0.3) aimed past the foreground: near layers blow out of frame (through a doorway,
                  between leaves); the focus plane is the far target

`amount` scales how far every move goes (1 = the tested recipe). Moves that start zoomed (dolly-out, orbit, crane, fpv,
whip-pan, dolly-zoom) begin on a crop of the start image: the beat's first frame is then the pure-camera render of the
first camera, not the start image itself (`starts_full`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

VERSION = 1           # bump when a recipe changes, so the guides of named moves are re-rendered

MOVES = ("static", "dolly-in", "dolly-out", "crash-zoom", "dolly-zoom", "orbit-left", "orbit-right", "crane-up",
         "crane-down", "fpv", "whip-pan", "push-through")


@dataclass(frozen=True)
class Recipe:
    phrase: str           # added to the video prompt (the guide does the work; the words agree with it)
    negative: str         # added to the negative prompt
    blur: float = 0.0     # motion blur of the guide, in frames (sub-frame cameras averaged)


RECIPES: dict[str, Recipe] = {
    "static": Recipe("Locked-off static camera on a tripod, the frame does not move", "camera movement, zoom, pan, dolly"),
    "dolly-in": Recipe("The camera dollies slowly forward toward the subject, smooth cinematic push in", "static camera"),
    "dolly-out": Recipe("The camera dollies slowly backward away from the subject, smooth cinematic pull back revealing the "
                        "scene", "static camera"),
    "crash-zoom": Recipe("A sudden fast crash zoom into the subject, then the frame holds", "static camera, slow zoom", 1.0),
    "dolly-zoom": Recipe("Dolly zoom vertigo effect: the subject stays the same size while the background stretches and "
                         "warps behind it", "static camera"),
    "orbit-left": Recipe("The camera orbits around the subject, arcing to the left, smooth parallax", "static camera"),
    "orbit-right": Recipe("The camera orbits around the subject, arcing to the right, smooth parallax", "static camera"),
    "crane-up": Recipe("The camera cranes up, rising smoothly while tilting down to keep the subject in frame",
                       "static camera"),
    "crane-down": Recipe("The camera cranes down, descending smoothly while tilting up to keep the subject in frame",
                         "static camera"),
    "fpv": Recipe("FPV drone shot flying fast forward through the scene, banking smoothly", "static camera", 0.6),
    "whip-pan": Recipe("A fast whip pan across the scene with motion blur", "static camera", 1.5),
    "push-through": Recipe("The camera pushes forward through the foreground into the scene beyond, smooth continuous "
                           "forward motion", "static camera"),
}


# ---------------------------------------------------------------- easing

def _sine(u: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, u)))


def _cubic(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return 4 * u ** 3 if u < 0.5 else 1 - 4 * (1 - u) ** 3


def _quart(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return 8 * u ** 4 if u < 0.5 else 1 - 8 * (1 - u) ** 4


def _window(u: float, a: float, b: float) -> float:
    return min(1.0, max(0.0, (u - a) / (b - a)))


def _lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


# ---------------------------------------------------------------- the rig

@dataclass(frozen=True)
class Cam:
    """One frame's camera for freeze.Renderer.frame (the focus plane `f` is filled in from the depth)."""
    cx: float
    cy: float
    w: float
    sx: float = 0.0
    sy: float = 0.0
    e: float = 0.0
    roll: float = 0.0

    def args(self, f: float) -> dict:
        return {"cx": self.cx, "cy": self.cy, "w": self.w, "sx": self.sx, "sy": self.sy, "e": self.e, "f": f,
                "roll": self.roll}


def _inside(cx: float, cy: float, w: float) -> tuple[float, float]:
    """The centre moved so a view of width `w` stays inside the picture."""
    return min(max(cx, w / 2), 1 - w / 2), min(max(cy, w / 2), 1 - w / 2)


def _aimed(at: tuple[float, float], w: float, k: float) -> tuple[float, float]:
    """The view centre, `k` of the way from the picture's centre to `at`, kept inside the picture."""
    return _inside(_lerp(0.5, at[0], k), _lerp(0.5, at[1], k), w)


ORBIT = 0.10          # orbit: lateral shift at the end of the arc, view widths per unit of depth (amount 1)
CRANE = 0.09          # crane: the same, vertical
SIDE_W = 0.82         # the view an orbit / crane flies (room for the shift at the picture's edges)


def cam_at(move: str, u: float, amount: float = 1.0, at: Optional[tuple[float, float]] = None) -> Cam:
    """The camera of `move` at time `u` (0-1 of the beat). `at`: the point the move is about (the subject), 0-1 of the
    picture; None: the move's own default (the centre)."""
    A = float(amount)
    tgt = tuple(at) if at is not None else (0.5, 0.5)
    if move == "static":
        return Cam(0.5, 0.5, 1.0)
    if move in ("dolly-in", "dolly-out"):
        k = _sine(u if move == "dolly-in" else 1 - u)
        w_end = 1 / (1 + 0.45 * A)
        w = math.exp(_lerp(0.0, math.log(w_end), k))
        cx, cy = _aimed(tgt, w, k)
        return Cam(cx, cy, w, e=0.32 * A * k)
    if move == "crash-zoom":
        k = _quart(_window(u, 0.12, 0.34))
        w_end = 1 / (1 + 1.6 * A)
        w = math.exp(_lerp(0.0, math.log(w_end), k))
        cx, cy = _aimed(tgt, w, k)
        return Cam(cx, cy, w)
    if move == "dolly-zoom":
        k = _sine(u)
        w = 0.76                                  # room for the foreground to shrink without running out of picture
        cx, cy = _aimed(tgt, w, 1.0)
        return Cam(cx, cy, w, e=-min(0.5 * A, 0.65) * k)     # past -0.7 the near plane folds (den clamp)
    if move in ("orbit-left", "orbit-right"):
        k = _sine(u)
        sign = 1.0 if move == "orbit-left" else -1.0
        cx, cy = _aimed(tgt, SIDE_W, 1.0)
        return Cam(cx, cy, SIDE_W, sx=sign * ORBIT * A * (2 * k - 1), e=0.05 * A * math.sin(math.pi * k))
    if move in ("crane-up", "crane-down"):
        k = _sine(u)
        sign = 1.0 if move == "crane-up" else -1.0
        cx, cy = _aimed(tgt, SIDE_W, 1.0)
        return Cam(cx, cy, SIDE_W, sy=sign * CRANE * A * (2 * k - 1))
    if move == "fpv":
        k = _lerp(u, _sine(u), 0.35)              # mostly constant speed: a drone does not ease
        w = math.exp(_lerp(math.log(0.9), math.log(0.9 / (1 + 0.9 * A)), k))
        cx, cy = _aimed(tgt, w, k)
        roll = math.radians(4.0) * A * math.sin(2 * math.pi * 0.75 * u) * min(1.0, u * 4)
        sx = 0.025 * A * math.sin(2 * math.pi * 0.5 * u)
        return Cam(cx, cy, w, sx=sx, e=0.5 * A * k, roll=roll)
    if move == "whip-pan":
        w = 0.62
        k = _quart(_window(u, 0.3, 0.62))
        x0, x1 = (w / 2, 1 - w / 2)
        if at is not None:                        # lands on `at`, starting from the far side of the picture
            x1 = min(max(tgt[0], w / 2), 1 - w / 2)
            x0 = (w / 2) if x1 > 0.5 else (1 - w / 2)
        span = (x1 - x0) * min(1.0, A)
        cx, cy = _inside(x1 - span + span * k, tgt[1], w)
        return Cam(cx, cy, w)
    if move == "push-through":
        k = _cubic(u)
        w_end = 1 / (1 + 2.4 * A)
        w = math.exp(_lerp(0.0, math.log(w_end), k))
        cx, cy = _aimed(tgt, w, k)
        return Cam(cx, cy, w, e=0.6 * A * k)
    raise ValueError(f"camera move '{move}': use one of {', '.join(MOVES)}")


def rig(move: str, n: int, amount: float = 1.0, at: Optional[tuple[float, float]] = None) -> list[Cam]:
    """The camera of every frame (frame i at u = i / (n - 1))."""
    return [cam_at(move, i / max(n - 1, 1), amount, at) for i in range(n)]


def starts_full(move: str, amount: float = 1.0, at: Optional[tuple[float, float]] = None) -> bool:
    """Whether the move's first frame is the start image itself (the whole picture, no shift, no roll)."""
    c = cam_at(move, 0.0, amount, at)
    return c.w >= 0.999 and abs(c.sx) < 1e-9 and abs(c.sy) < 1e-9 and abs(c.e) < 1e-9 and abs(c.roll) < 1e-9


def focus_depth(depth: np.ndarray, at: Optional[tuple[float, float]], radius: float = 0.06) -> float:
    """The focus plane: the median depth in a small square around `at` (the centre when None): what stays put in an
    orbit or a crane, and keeps its size in a dolly zoom."""
    H, W = depth.shape[:2]
    x, y = at if at is not None else (0.5, 0.5)
    r = max(radius, 2.0 / W)
    x0, x1 = int((x - r) * W), int(math.ceil((x + r) * W))
    y0, y1 = int((y - r) * H), int(math.ceil((y + r) * H))
    return float(np.median(depth[max(y0, 0):max(y1, y0 + 1), max(x0, 0):max(x1, x0 + 1)]))


def view_keys(move: str, amount: float = 1.0, at: Optional[tuple[float, float]] = None, n: int = 25) -> list[dict]:
    """The view part of the move (centre and width, no parallax) as freeze keys under linear easing, `n` of them: what
    the plan, the stage key and the follow measurement of camera_guide take as the camera."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        c = cam_at(move, t, amount, at)
        out.append({"t": t, "box": [c.cx - c.w / 2, c.cy - c.w / 2, c.cx + c.w / 2, c.cy + c.w / 2], "hold": 0.0})
    return out


def phrase(camera) -> str:
    """The words a named move adds to the video prompt ("" for keyed moves)."""
    name = getattr(camera, "move", None)
    return RECIPES[name].phrase if name else ""


def negative(camera, base: str) -> str:
    """The negative prompt for a named move: `base` plus the move's own words (a static shot also drops "static
    camera" from it); a keyed move keeps `base`."""
    name = getattr(camera, "move", None)
    if not name:
        return base
    extra = RECIPES[name].negative
    parts = [p.strip() for p in base.split(",") if p.strip()]
    if name == "static":                    # a tripod shot must not be told camera shake is the problem it isn't
        parts = [p for p in parts if p != "static camera"]
    return ", ".join(parts + [p.strip() for p in extra.split(",") if p.strip() and p.strip() not in parts])


# ---------------------------------------------------------------- rendering

def render(rgb: np.ndarray, depth: np.ndarray, cams: list[Cam], *, size: tuple[int, int], focus: float, blur: float = 0.0,
           device: Optional[str] = None, move: Optional[str] = None, amount: float = 1.0,
           at: Optional[tuple[float, float]] = None):
    """Yield the frames (uint8 H x W x 3) of `rgb` flown along `cams` through `depth` (freeze.Renderer). With `blur` > 0 and
    `move` given, each frame averages sub-frame cameras over `blur` frames (motion blur where the camera is fast)."""
    from . import freeze as fz
    r = fz.Renderer(rgb, depth, size, device)
    n = len(cams)
    subs = 7 if blur > 0 and move else 1
    for i, c in enumerate(cams):
        if subs == 1:
            yield r.to_u8(r.frame(**c.args(focus)))
            continue
        acc = None
        for j in range(subs):
            u = (i + (j / (subs - 1) - 0.5) * blur) / max(n - 1, 1)
            fr = r.frame(**cam_at(move, min(1.0, max(0.0, u)), amount, at).args(focus))
            acc = fr if acc is None else acc + fr
        yield r.to_u8(acc / subs)


def preset_of(camera) -> Optional[tuple[str, float, Optional[tuple[float, float]]]]:
    """(move, amount, at) of a beat's `camera` when it is a named move, else None."""
    name = getattr(camera, "move", None)
    if not name:
        return None
    at = getattr(camera, "at", None)
    return name, float(getattr(camera, "amount", 1.0)), (tuple(at) if at is not None else None)


# ---------------------------------------------------------------- measuring: does the move read?

def _flow(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    import cv2
    ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    return cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 4, 21, 3, 5, 1.1, 0)


def _small(frames: list[np.ndarray], width: int) -> list[np.ndarray]:
    import cv2
    h = max(16, round(frames[0].shape[0] * width / frames[0].shape[1]))
    return [cv2.resize(f, (width, h), interpolation=cv2.INTER_AREA) for f in frames]


def move_agreement(frames: list[np.ndarray], refs: list[np.ndarray], width: int = 320, step: int = 2,
                   mask: Optional[Callable[[int], np.ndarray]] = None) -> dict:
    """How well the generated frames move like the pure-camera render of the move, on dense optical flow (every `step`
    frames, at `width` px across). Per step:

        gain      sum(f_gen . f_ref) / sum(|f_ref|^2): 1 = the same motion, as much of it; 0 = none of it
        cosine    the direction agreement of the two flow fields (1 = the same field)
        parallax  the cosine after each field's mean is taken out: the depth structure of the move (an orbit against a
                  plain pan, a dolly zoom against a still frame). A model that only slides the picture scores ~0 here

    Steps where the render hardly moves (under 0.05 px a frame) are skipped for gain/cosine/parallax and measured as
    `drift` instead (the generated frame's own median motion, px per frame at `width`): a static camera must not drift.
    `mask(i)`: optional HxW bool (at `width`) of where to measure (the static world)."""
    n = min(len(frames), len(refs))
    g, r = _small(frames[:n], width), _small(refs[:n], width)
    gains, coss, pars, drift, ref_mag = [], [], [], [], []
    for i in range(0, n - step, step):
        fg, fr = _flow(g[i], g[i + step]), _flow(r[i], r[i + step])
        m = np.ones(fg.shape[:2], bool) if mask is None else mask(i)
        a, b = fg[m].reshape(-1, 2), fr[m].reshape(-1, 2)
        mag = float(np.sqrt((b ** 2).sum(1)).mean()) / step
        ref_mag.append(mag)
        if mag < 0.05:
            drift.append(float(np.median(np.sqrt((a ** 2).sum(1)))) / step)
            continue
        dot, bb, aa = float((a * b).sum()), float((b * b).sum()), float((a * a).sum())
        gains.append(dot / max(bb, 1e-9))
        coss.append(dot / max(math.sqrt(aa * bb), 1e-9))
        a0, b0 = a - a.mean(0), b - b.mean(0)
        d0, bb0, aa0 = float((a0 * b0).sum()), float((b0 * b0).sum()), float((a0 * a0).sum())
        pars.append(d0 / max(math.sqrt(aa0 * bb0), 1e-9) if bb0 > 1e-6 * max(bb, 1e-9) else float("nan"))
    med = lambda v: float(np.nanmedian(v)) if len(v) and np.isfinite(v).any() else float("nan")
    return {"gain": med(gains), "cosine": med(coss), "parallax": med(pars), "drift": med(drift),
            "moving_steps": len(gains), "still_steps": len(drift), "ref_px_per_frame": med(ref_mag)}


def reads(move: str, agreement: dict) -> bool:
    """Whether a generated beat reads as its move, from `move_agreement` (the thresholds were set on the contact sheets of
    the tests in docs/scenes.md: a move that reads keeps most of the render's motion in the same direction)."""
    if move == "static":
        return agreement["drift"] == agreement["drift"] and agreement["drift"] < 0.25
    ok = agreement["gain"] >= 0.5 and agreement["cosine"] >= 0.6
    if move in ("orbit-left", "orbit-right", "crane-up", "crane-down", "dolly-zoom"):
        ok = ok and agreement["parallax"] >= 0.3
    return ok
