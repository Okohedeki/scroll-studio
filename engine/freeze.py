"""freeze: a frozen moment, rendered offline instead of generated.

A video model cannot freeze a crowd while the camera moves (the people melt and drift), and redrawing close-ups
with an image editor changes the faces every time. So when time stops, stop generating: take one frame, upscale it,
estimate its depth (Depth Anything V2) and fly a 2.5D camera through it. Everything in the clip is a pixel of the one
frame, so faces, hands and shoes stay what they are. The clip is the beat's `clip.mp4` (frames at `beat_res`, 24 fps),
so it joins the film exactly like a generated beat: same stage, cache, trim, crossfade, restore, `locked`, `--only`.

Pipeline (each step cached by its own digest inside the beat's folder, so changing the camera re-renders in seconds
and never repeats the upscale or the depth):

    frozen.png   the source frame, fitted to beat_res (a beat's last/sharpest frame, or any image input)
    up.png       the frame upscaled `freeze.upscale` times (SeedVR2 through ComfyUI, or a local Lanczos + sharpen)
    depth.npy    Depth Anything V2 depth, snapped to the frame's edges (guided filter), near edges grown a few pixels
    clip.mp4     the camera render (+ first.png / last.png, lossless, for `beat_frame` and the storyboard)

The render is an inverse parallax warp done with torch `grid_sample` (GPU when there is one, else CPU): for every
output pixel, a few fixed-point steps find the source pixel whose depth-shifted position lands there, sampled with
bicubic filtering from a mip chain of the upscaled frame. It runs about 150 frames a second at 1920x1088 on a 4090 and
needs no Blender session (a mesh displacement would open the same holes behind foreground edges and cost seconds a
frame), and it is deterministic, so a re-render is byte-for-byte what the stage key promises.
"""
from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

import numpy as np

from .project import BuildError

VERSION = 1          # bump when the render changes, so frozen clips are re-rendered
FPS = 24


# ---------------------------------------------------------------- the camera path

EASES: dict[str, Callable[[float], float]] = {
    "linear": lambda u: u,
    "inOutSine": lambda u: 0.5 - 0.5 * math.cos(math.pi * u),
    "inOutQuad": lambda u: 2 * u * u if u < 0.5 else 1 - 2 * (1 - u) ** 2,
    "inOutCubic": lambda u: 4 * u ** 3 if u < 0.5 else 1 - 4 * (1 - u) ** 3,
    "inOutQuart": lambda u: 8 * u ** 4 if u < 0.5 else 1 - 8 * (1 - u) ** 4,
    "smoother": lambda u: u * u * u * (u * (6 * u - 15) + 10),     # smootherstep: speed and acceleration are 0 at the stops
}


@dataclass(frozen=True)
class View:
    """Where the camera looks: the centre and the width of the view in 0-1 of the frozen frame. The frame has the
    output's aspect, so the view is a square in these units (its height is `w` too)."""
    cx: float
    cy: float
    w: float


def box_view(box) -> View:
    """A framing box [x0, y0, x1, y1] as a view: centred on the box and wide enough to hold all of it (a box of
    another shape than the frame is widened, never cropped), moved inside the frame when it sticks out."""
    x0, y0, x1, y1 = (float(v) for v in box)
    w = min(1.0, max(x1 - x0, y1 - y0, 0.02))
    cx = min(max((x0 + x1) / 2, w / 2), 1 - w / 2)
    cy = min(max((y0 + y1) / 2, w / 2), 1 - w / 2)
    return View(cx, cy, w)


def _key(k) -> tuple[float, tuple, float]:
    if isinstance(k, dict):
        return float(k["t"]), tuple(k["box"]), float(k.get("hold", 0) or 0)
    return float(k.t), tuple(k.box), float(k.hold)


class CameraPath:
    """The camera over a beat: keys (t 0-1, box, hold) -> a View at any t.

    It arrives at each box at its `t`, rests there for its `hold`, and travels to the next box so as to arrive at that
    key's `t`; before the first key and after the last it rests on that key's box. `ease` shapes each leg
    (inOut*: the camera is at rest at every key, so a leg is a clean move from one stop to the next) or, for `flow`,
    the whole path is one smooth curve that keeps its speed through keys and rests only at the ends and on holds."""

    def __init__(self, keys, ease: str = "inOutSine"):
        ks = sorted((_key(k) for k in keys), key=lambda k: k[0]) or [(0.0, (0, 0, 1, 1), 0.0)]
        if ease != "flow" and ease not in EASES:
            raise BuildError(f"freeze ease '{ease}': use one of {', '.join([*EASES, 'flow'])}")
        self.ease = ease
        self.stops = []                       # (arrive, depart, params)
        for t, box, hold in ks:
            v = box_view(box)
            self.stops.append((t, min(1.0, t + hold), np.array([v.cx, v.cy, math.log(v.w)])))
        self._spline = self._flow() if ease == "flow" and len(self.stops) > 1 else None

    def _flow(self):
        from scipy.interpolate import CubicHermiteSpline, PchipInterpolator
        xs, ys, rest = [], [], []
        st = self.stops
        if st[0][0] > 1e-9:
            xs.append(0.0); ys.append(st[0][2]); rest.append(True)
        for a, d, p in st:
            held = d > a + 1e-9
            xs.append(a); ys.append(p); rest.append(held)       # a held key is a stop; a key without hold is passed through
            if held:
                xs.append(d); ys.append(p); rest.append(True)
        if st[-1][1] < 1 - 1e-9:
            xs.append(1.0); ys.append(st[-1][2]); rest.append(True)
        xs, ys = np.array(xs), np.array(ys)
        rest[0] = rest[-1] = True
        d = np.stack([PchipInterpolator(xs, ys[:, j])(xs, 1) for j in range(3)], axis=1)
        d[np.array(rest)] = 0.0              # at rest on holds and at both ends
        return [CubicHermiteSpline(xs, ys[:, j], d[:, j]) for j in range(3)]

    def params(self, t: float) -> np.ndarray:
        t = min(1.0, max(0.0, float(t)))
        s = self.stops
        if t <= s[0][0]:
            return s[0][2]
        if self._spline is not None:
            return np.array([float(sp(t)) for sp in self._spline])
        for (a0, d0, p0), (a1, d1, p1) in zip(s, s[1:]):
            if t <= d0:
                return p0
            if t < a1:
                u = (t - d0) / max(a1 - d0, 1e-9)
                return p0 + (p1 - p0) * EASES[self.ease](u)
        return s[-1][2]

    def at(self, t: float) -> View:
        cx, cy, lw = self.params(t)
        w = float(min(1.0, math.exp(lw)))
        return View(float(min(max(cx, w / 2), 1 - w / 2)), float(min(max(cy, w / 2), 1 - w / 2)), w)

    def boxes(self) -> list[View]:
        return [View(float(p[0]), float(p[1]), float(math.exp(p[2]))) for _, _, p in self.stops]


# ---------------------------------------------------------------- the camera timeline (parallax, dolly, focus)

def _smooth(a: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0 or len(a) < 3:
        return a
    from scipy.ndimage import gaussian_filter1d
    return gaussian_filter1d(a, sigma, mode="nearest")


class Timeline:
    """Everything the render needs per moment, computed once on a dense time grid and interpolated: the view, the
    lateral sway of the camera (the parallax), the push-in of near things (the dolly), and the focus plane that stays
    put (the depth at the middle of the view, smoothed, so the subject holds still while the rest of the world shifts).

    The sway is scaled down wherever the view is too close to the frame's edge to move (a full-frame view cannot sway at
    all: the first frame of the beat is the frozen frame itself)."""
    AMP = 0.05           # sway, in view widths per unit of depth, at parallax 1
    DOLLY = 0.25         # push-in of near things per unit of log zoom and unit of depth, at parallax 1
    STEPS_PER_FRAME = 4

    def __init__(self, path: CameraPath, seconds: float, depth_small: np.ndarray, parallax: float,
                 dolly: Optional[float] = None, fps: int = FPS):
        n = max(2, int(round(seconds * fps * self.STEPS_PER_FRAME)) + 1)
        self.t = np.linspace(0, 1, n)
        views = [path.at(t) for t in self.t]
        self.cx = np.array([v.cx for v in views])
        self.cy = np.array([v.cy for v in views])
        self.w = np.array([v.w for v in views])
        dolly = parallax * self.DOLLY if dolly is None else dolly * self.DOLLY
        # focus: the depth in the middle of the view
        H, W = depth_small.shape
        f = np.empty(n)
        for i in range(n):
            r = max(self.w[i] * 0.18, 1.5 / W)
            x0, x1 = int((self.cx[i] - r) * W), int(math.ceil((self.cx[i] + r) * W))
            y0, y1 = int((self.cy[i] - r) * H), int(math.ceil((self.cy[i] + r) * H))
            f[i] = float(np.median(depth_small[max(y0, 0):max(y1, y0 + 1), max(x0, 0):max(x1, x0 + 1)]))
        self.f = _smooth(f, fps * self.STEPS_PER_FRAME * 0.6)
        # the camera's lateral drift: one slow lissajous that starts and ends at rest in the middle
        cycles = max(1, round(seconds / 9.0))
        amp = self.AMP * parallax
        sx = amp * np.sin(2 * np.pi * cycles * self.t)
        sy = amp * 0.3 * np.sin(2 * np.pi * (2 * cycles) * self.t + 0.6) * np.sin(np.pi * self.t)
        e = dolly * np.log(1.0 / self.w)
        # room to move: how far the view is from the frame's edge against how far the shift would pull in
        room = np.minimum.reduce([self.cx - self.w / 2, 1 - self.cx - self.w / 2, self.cy - self.w / 2, 1 - self.cy - self.w / 2])
        span = np.maximum(self.f, 1 - self.f)
        need = self.w * (np.maximum(np.abs(sx), np.abs(sy)) * span + 0.5 * np.abs(e) * span / np.maximum(1 - np.abs(e) * span, 0.3))
        k = np.clip(room / np.maximum(need, 1e-9), 0, 1)
        from scipy.ndimage import minimum_filter1d
        win = int(fps * self.STEPS_PER_FRAME * 0.6) | 1
        k = _smooth(minimum_filter1d(k, win, mode="nearest"), win / 6)          # never above what the edge allows
        self.sx, self.sy, self.e = sx * k, sy * k, e * k

    def at(self, t: float) -> dict:
        t = min(1.0, max(0.0, t))
        g = lambda a: float(np.interp(t, self.t, a))
        return {"cx": g(self.cx), "cy": g(self.cy), "w": g(self.w), "sx": g(self.sx), "sy": g(self.sy), "e": g(self.e),
                "f": g(self.f)}


# ---------------------------------------------------------------- depth: edges and focus

def guided_filter(guide: np.ndarray, src: np.ndarray, r: int, eps: float) -> np.ndarray:
    """He et al.'s guided filter (box filters): `src` smoothed but snapped to the edges of `guide` (both float 0-1).
    The depth map then changes where the picture does, so a person's outline moves with the person."""
    import cv2
    box = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1), borderType=cv2.BORDER_REPLICATE)
    mI, mp = box(guide), box(src)
    cov = box(guide * src) - mI * mp
    var = box(guide * guide) - mI * mI
    a = cov / (var + eps)
    b = mp - a * mI
    return box(a) * guide + box(b)


def prepare_depth(depth: np.ndarray, rgb: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Depth (0 far .. 1 near, any size) -> float32 at `size`, edge-aligned to `rgb`, near regions grown a few pixels
    (so a foreground edge carries its own colour when it moves instead of smearing the background into it), softened."""
    import cv2
    W, H = size
    d = cv2.resize(depth.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    d = np.clip(guided_filter(g, np.clip(d, 0, 1), max(3, W // 240), 2e-3), 0, 1)
    r = max(2, W // 400)
    d8 = cv2.dilate((d * 255).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    d8 = cv2.GaussianBlur(d8, (0, 0), r * 0.8)
    return d8.astype(np.float32) / 255


# ---------------------------------------------------------------- the render

class Renderer:
    """Inverse parallax warp of one upscaled frame with a depth map, on torch (cuda when present).

    For every output pixel a ray is marched through the depth map, from the nearest depth to the farthest, to find
    the nearest surface that lands on that pixel (parallax occlusion mapping). That keeps visibility right at an
    edge: behind a foreground person the pixels show the background that was really there instead of a smear of the
    person, and the march is stable where a few fixed-point steps flicker between near and far. The march runs at
    half the output size (depth is smooth); the colour is then sampled at full size with bicubic filtering from a mip
    chain of the upscaled frame."""
    STEPS = 24

    def __init__(self, rgb: np.ndarray, depth: np.ndarray, size: tuple[int, int], device: Optional[str] = None,
                 edge: str = "clamp"):
        """`edge`: what a ray that leaves the picture sees: "clamp" (the edge pixel, stretched into streaks; a frozen
        moment's camera never leaves the picture) or "mirror" (the picture reflected at its edge, which reads as more of
        the scene; named camera moves, whose parallax can reach past the edge)."""
        import torch
        self.torch = torch
        self.edge = edge
        self.dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.W, self.H = size
        t = torch.from_numpy(np.array(rgb, dtype=np.uint8)).to(self.dev).permute(2, 0, 1)[None].float()
        self.src_w = t.shape[-1]
        self.levels = [t]
        while self.levels[-1].shape[-1] > self.W // 2 and len(self.levels) < 4:
            self.levels.append(torch.nn.functional.avg_pool2d(self.levels[-1], 2))
        self.depth = torch.from_numpy(np.array(depth, dtype=np.float32)).to(self.dev)[None, None]
        self.o = self._grid_of(self.W, self.H)
        sw, sh = self.W, self.H
        self.o_solve = self._grid_of(sw, sh)

    def _grid_of(self, w: int, h: int):
        torch = self.torch
        xs = (torch.arange(w, device=self.dev, dtype=torch.float32) + 0.5) / w - 0.5
        ys = (torch.arange(h, device=self.dev, dtype=torch.float32) + 0.5) / h - 0.5
        return torch.stack(torch.meshgrid(xs, ys, indexing="xy"), dim=-1)      # (h, w, 2): x, y

    @staticmethod
    def _grid(u):
        return (u * 2 - 1)[None]

    def _source_at(self, c, s, w, e, f, d, o):
        """Source position (0-1) seen at view position `o` when the surface there has depth `d` (a scalar or a map)."""
        dd = d - f
        den = (1 + e * dd).clamp(min=0.3) if hasattr(dd, "clamp") else max(1 + e * dd, 0.3)
        sd = s * dd[..., None] if hasattr(dd, "clamp") else s * dd
        return c + w * (o - sd) / (den[..., None] if hasattr(den, "clamp") else den)

    def _march(self, c, s, w, e, f):
        """The depth of the nearest surface that lands on each pixel of the solve grid."""
        torch = self.torch
        F = torch.nn.functional
        o = self.o_solve
        n = self.STEPS
        hit = star = prev_gap = prev_d = None
        for k in range(n + 1):
            d = 1.0 - k / n
            u = self._wrap(self._source_at(c, s, w, e, f, d, o))
            gap = F.grid_sample(self.depth, self._grid(u), mode="bilinear", padding_mode="border", align_corners=False)[0, 0] - d
            if k == 0:
                hit = gap >= 0
                star = torch.where(hit, torch.ones_like(gap), torch.zeros_like(gap))
            else:
                new = (~hit) & (gap >= 0)
                frac = (-prev_gap) / (gap - prev_gap).clamp(min=1e-6)           # where the ray crossed, between the two steps
                star = torch.where(new, prev_d + (d - prev_d) * frac, star)
                hit = hit | new
            prev_gap, prev_d = gap, d
        return star

    def _wrap(self, u):
        """Source positions brought into the picture (0-1): clamped to its edge, or reflected at it (`edge`)."""
        return u.clamp(0, 1) if self.edge == "clamp" else 1 - (1 - u.abs().remainder(2)).abs()

    def _rolled(self, o, roll: float):
        """The view grid `o` turned by `roll` radians about the view's centre (in pixels, so the turn is not skewed by the
        frame's aspect): a camera banking. The grid is in square units (x in widths, y in heights)."""
        c, s = math.cos(roll), math.sin(roll)
        a = self.W / self.H
        x, y = o[..., 0], o[..., 1]
        return self.torch.stack([c * x - s * y / a, s * x * a + c * y], dim=-1)

    def frame(self, cx: float, cy: float, w: float, sx: float, sy: float, e: float, f: float, roll: float = 0.0):
        """One frame (3, H, W) float 0-255. The camera views the square (cx, cy, w), is shifted (sx, sy) view-widths per
        unit of depth against the focus plane `f`, and pushes near things in by `e` per unit of depth. `roll` banks the
        camera clockwise by that many radians (the picture turns the other way); 0 is the unchanged render."""
        torch = self.torch
        F = torch.nn.functional
        c = torch.tensor([cx, cy], device=self.dev)
        o_full, o_solve = (self.o, self.o_solve) if not roll else (self._rolled(self.o, roll), self._rolled(self.o_solve, roll))
        if sx or sy or e:
            s = torch.tensor([sx, sy], device=self.dev)
            keep = self.o_solve
            self.o_solve = o_solve
            try:
                star = self._march(c, s, w, e, f)[None, None]
            finally:
                self.o_solve = keep
            star = F.interpolate(star, size=(self.H, self.W), mode="bilinear", align_corners=False)[0, 0]
            u = self._source_at(c, s, w, e, f, star, o_full)
        else:
            u = c + w * o_full
        grid = self._grid(self._wrap(u))
        ratio = max(w * self.src_w / self.W, 1e-6)          # source pixels per output pixel
        lod = min(max(math.log2(ratio), 0.0), len(self.levels) - 1)
        lo, fr = int(lod), lod - int(lod)
        out = F.grid_sample(self.levels[lo], grid, mode="bicubic", padding_mode="border", align_corners=False)
        if fr > 0.02 and lo + 1 < len(self.levels):
            out = out * (1 - fr) + F.grid_sample(self.levels[lo + 1], grid, mode="bicubic", padding_mode="border",
                                                 align_corners=False) * fr
        return out[0]

    def grain(self, frame, sigma: float, seed: int):
        """Film grain: luminance noise, a touch softer than pixel noise, the same on all three channels."""
        torch = self.torch
        g = torch.Generator(device=self.dev).manual_seed(int(seed))
        n = torch.randn((1, 1, self.H, self.W), device=self.dev, generator=g)
        n = torch.nn.functional.avg_pool2d(torch.nn.functional.pad(n, (0, 1, 0, 1), mode="replicate"), 2, 1) * 1.6
        return frame + n[0] * (sigma * 255)

    def to_u8(self, frame) -> np.ndarray:
        return frame.clamp(0, 255).round().byte().permute(1, 2, 0).cpu().numpy()


def render_frames(rgb: np.ndarray, depth: np.ndarray, camera, *, size: tuple[int, int], seconds: float,
                  first_frame: int = 0, parallax: float = 0.6, dolly: Optional[float] = None, ease: str = "inOutSine",
                  blur: float = 0.0, grain: float = 0.0, seed: int = 7, fps: int = FPS,
                  device: Optional[str] = None) -> "Iterator[np.ndarray]":
    """Yield the beat's frames (uint8 H x W x 3) from frame `first_frame` on. `rgb` is the (upscaled) frozen frame,
    `depth` its prepared depth map. n = round(seconds * fps) frames, the camera at t = i / (n - 1)."""
    n = max(2, int(round(seconds * fps)))
    path = CameraPath(camera, ease)
    small = depth if depth.shape[1] <= 480 else None
    if small is None:
        import cv2
        small = cv2.resize(depth, (480, max(1, round(480 * depth.shape[0] / depth.shape[1]))), interpolation=cv2.INTER_AREA)
    tl = Timeline(path, seconds, small, parallax, dolly, fps)
    r = Renderer(rgb, depth, size, device)
    subs = 5 if blur > 0 else 1
    for i in range(first_frame, n):
        acc = None
        for j in range(subs):
            off = (j / (subs - 1) - 0.5) * blur if subs > 1 else 0.0       # in frames
            p = tl.at((i + off) / (n - 1))
            fr = r.frame(**p)
            acc = fr if acc is None else acc + fr
        fr = acc / subs
        if grain > 0:
            fr = r.grain(fr, grain, seed * 100003 + i)
        yield r.to_u8(fr)


def render_move_frames(rgb: np.ndarray, depth: np.ndarray, move: str, *, size: tuple[int, int], seconds: float,
                       amount: float = 1.0, at: Optional[tuple[float, float]] = None, first_frame: int = 0,
                       blur: float = 0.0, grain: float = 0.0, seed: int = 7, fps: int = FPS,
                       device: Optional[str] = None) -> "Iterator[np.ndarray]":
    """Yield a frozen beat's frames along a named camera move (engine/camera_moves.py) instead of keys: the rig a
    generated beat's guide is flown along, here rendered as the beat itself. The focus plane is the subject's depth at
    `at` (else the nearer things in the middle of the picture), so an orbit pivots on the subject and a dolly zoom keeps
    it the same size. Rays that leave the picture see it mirrored (a move's parallax can reach past the edge). `blur`
    (frames of shutter) is at least the move's own (a whip pan or a crash zoom is blurred by its recipe)."""
    from . import camera_moves as cm
    n = max(2, int(round(seconds * fps)))
    focus = cm.focus_depth(depth, at)
    r = Renderer(rgb, depth, size, device, edge="mirror")
    blur = max(float(blur), cm.RECIPES[move].blur)
    subs = 5 if blur > 0 else 1
    for i in range(first_frame, n):
        acc = None
        for j in range(subs):
            off = (j / (subs - 1) - 0.5) * blur if subs > 1 else 0.0       # in frames
            u = min(1.0, max(0.0, (i + off) / (n - 1)))
            fr = r.frame(**cm.cam_at(move, u, amount, at).args(focus))
            acc = fr if acc is None else acc + fr
        fr = acc / subs
        if grain > 0:
            fr = r.grain(fr, grain, seed * 100003 + i)
        yield r.to_u8(fr)


def encode_frames(frames, out: Path, size: tuple[int, int], fps: int = FPS, crf: int = 13, log: Callable = print) -> tuple:
    """Pipe frames into FFmpeg (libx264, the same encode as a generated beat). Returns (first frame, last frame)."""
    from .config import settings
    out.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt",
                          "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", str(crf),
                          "-preset", "slow", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    first = last = None
    try:
        for fr in frames:
            if first is None:
                first = fr
            last = fr
            p.stdin.write(fr.tobytes())
    finally:
        p.stdin.close()
        rc = p.wait()
    if rc != 0:
        raise BuildError(f"ffmpeg failed encoding {out.name} (exit {rc})")
    return first, last


# ---------------------------------------------------------------- sharpness (which frame to freeze)

def sharpness(rgb: np.ndarray, views: Optional[list[View]] = None) -> float:
    """How sharp a frame is where the camera will look: the variance of the Laplacian of the lightly blurred luminance,
    averaged over the tightest framing boxes (the whole frame when there are none). Grain alone cannot win: the blur
    takes the pixel noise out, and every candidate has the same grain."""
    import cv2
    g = cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.0)
    lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
    H, W = g.shape
    tight = [v for v in (views or []) if v.w < 0.7] or [View(0.5, 0.5, 1.0)]
    scores = []
    for v in tight:
        x0, x1 = int((v.cx - v.w / 2) * W), int(math.ceil((v.cx + v.w / 2) * W))
        y0, y1 = int((v.cy - v.w / 2) * H), int(math.ceil((v.cy + v.w / 2) * H))
        scores.append(float(lap[max(y0, 0):y1, max(x0, 0):x1].var()))
    return float(np.mean(scores))


def sharpest(frames: list[np.ndarray], views: Optional[list[View]] = None) -> int:
    """Index of the sharpest frame; a later frame wins a tie (and anything within 3% of the best), to stay close to the
    moment the shot ended on."""
    scores = [sharpness(f, views) for f in frames]
    best = max(scores)
    return max(i for i, s in enumerate(scores) if s >= best * 0.97)
