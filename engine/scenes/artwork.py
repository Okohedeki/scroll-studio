"""artwork: any image, drawn and painted in stages as you scroll.

Everything derives from the one source image, so every stage lines up exactly with the finished picture:
  paper.jpg    blank sheet in the spec's paper colour
  tone.jpg     graphite value study (local contrast + hatching in the darks)
  under.jpg    monochrome underpainting in the spec's underpaint colour
  final.jpg    the image itself
  mask_*.png   brush-order maps: a pixel is revealed once its stage's progress passes its value
  lines.json   contour strokes, ordered from the focus outwards
  guides.json  construction lines (axis, block-in box, composition triangle, focus ellipse)

Focus ("where the drawing starts") is detected automatically: faces first (OpenCV Haar cascade), then a
spectral-residual saliency map; or give `focus: [[x, y], ...]` in 0-1 image coordinates.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..inputs import credit, image_key, resolve_image
from ..project import BuildContext, file_key
from ..spec import ArtworkScene

VERSION = 3   # bump when the layer recipes change, so cached builds refresh


def _hex(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def smooth_noise(h, w, scale, seed):
    r = np.random.default_rng(seed).standard_normal((max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(r, (w, h), interpolation=cv2.INTER_CUBIC)


# ---------------------------------------------------------------- analysis

def saliency(img_bgr: np.ndarray) -> np.ndarray:
    """Spectral-residual saliency (Hou & Zhang 2007), 0-1, same size as the image."""
    h, w = img_bgr.shape[:2]
    g = cv2.cvtColor(cv2.resize(img_bgr, (128, max(8, round(128 * h / w)))), cv2.COLOR_BGR2GRAY).astype(np.float32)
    f = np.fft.fft2(g)
    log_amp = np.log(np.abs(f) + 1e-6)
    residual = log_amp - cv2.blur(log_amp, (3, 3))
    sal = np.abs(np.fft.ifft2(np.exp(residual + 1j * np.angle(f)))) ** 2
    sal = cv2.GaussianBlur(sal, (0, 0), 3)
    sal = (sal - sal.min()) / (np.ptp(sal) + 1e-6)
    # favour the centre a little, like a viewer does
    yy, xx = np.mgrid[0:sal.shape[0], 0:sal.shape[1]].astype(np.float32)
    centre = np.exp(-(((xx / sal.shape[1] - 0.5) / 0.45) ** 2 + ((yy / sal.shape[0] - 0.5) / 0.45) ** 2))
    return cv2.resize(sal * (0.6 + 0.4 * centre), (w, h), interpolation=cv2.INTER_CUBIC)


def detect_focus(img_bgr: np.ndarray, log) -> tuple[list[tuple[float, float, float, float]], np.ndarray]:
    """Return focus regions [(cx, cy, rx, ry)] in 0-1 coords (most important first) and the saliency map."""
    h, w = img_bgr.shape[:2]
    sal = saliency(img_bgr)
    regions: list[tuple[float, float, float, float]] = []
    gray = cv2.equalizeHist(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY))
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(max(24, w // 20), max(24, w // 20)))
    for (x, y, fw, fh) in sorted(faces, key=lambda f: -f[2] * f[3])[:3]:
        regions.append(((x + fw / 2) / w, (y + fh / 2) / h, fw / w * 0.75, fh / h * 0.9))
    if regions:
        log(f"  focus: {len(regions)} face(s)")
    # saliency peaks fill in (or provide) the rest
    s = sal.copy()
    for _ in range(3 - min(len(regions), 2)):
        y, x = np.unravel_index(np.argmax(s), s.shape)
        if s[y, x] < 0.25:
            break
        cx, cy = x / w, y / h
        if all(math.hypot(cx - r[0], cy - r[1]) > 0.15 for r in regions):
            regions.append((cx, cy, 0.12, 0.12))
        cv2.circle(s, (int(x), int(y)), int(0.18 * max(w, h)), 0, -1)
    if not regions:
        regions.append((0.5, 0.45, 0.15, 0.15))
    log("  focus: " + ", ".join(f"({r[0]:.2f}, {r[1]:.2f})" for r in regions))
    return regions, sal


def subject_box(sal: np.ndarray) -> tuple[float, float, float, float]:
    """Bounding box (x0, y0, x1, y1, 0-1) of the salient subject, for block-in guides."""
    h, w = sal.shape
    m = sal > np.quantile(sal, 0.72)
    ys, xs = np.nonzero(m)
    if len(xs) < 10:
        return 0.15, 0.1, 0.85, 0.95
    x0, x1 = np.quantile(xs, [0.03, 0.97]) / w
    y0, y1 = np.quantile(ys, [0.03, 0.97]) / h
    return float(x0), float(y0), float(x1), float(y1)


# ---------------------------------------------------------------- layers

def build_paper(h, w, colour):
    grain = smooth_noise(h, w, 2, 1) * 2.2 + smooth_noise(h, w, 9, 2) * 2.5 + smooth_noise(h, w, 60, 3) * 3.0
    paper = colour[None, None, :] + grain[..., None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    paper *= (1 - 0.10 * ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2))[..., None]
    return paper


def build_tone(lum, paper):
    h, w = lum.shape
    l8 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply((lum * 255).astype(np.uint8))
    v = cv2.GaussianBlur(l8.astype(np.float32) / 255, (0, 0), 1.1)
    v = np.clip((v - 0.08) / 0.84, 0, 1) ** 0.85
    dark = 1 - v
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    hatch = 0.5 + 0.5 * np.sin((xx * 0.70 + yy * 0.72) * 0.9 + smooth_noise(h, w, 40, 4) * 2.0)
    hatch = np.clip((hatch - 0.35) * 1.8, 0, 1)
    graphite = np.clip(dark * 0.82 + hatch * dark * 0.22, 0, 1)
    ink = np.array([46, 43, 41], np.float32)
    return paper * (1 - graphite[..., None]) + ink * graphite[..., None]


def build_under(lum, paper, colour):
    v = np.clip((cv2.GaussianBlur(lum.astype(np.float32), (0, 0), 1.6) - 0.05) / 0.9, 0, 1)
    c = colour
    stops = np.array([c * 0.42, c * 0.95, c * 0.6 + 255 * 0.4 * np.array([0.9, 0.75, 0.55]),
                      c * 0.3 + np.array([214, 180, 130]) * 0.7, np.array([236, 214, 170])], np.float32)
    pos = v * (len(stops) - 1)
    i0 = np.clip(pos.astype(int), 0, len(stops) - 2)
    t = (pos - i0)[..., None]
    col = stops[i0] * (1 - t) + stops[i0 + 1] * t
    return col * 0.93 + paper * 0.07


def priority_field(nx, ny, regions, sal_small):
    """0 = painted first: focus regions in order, then the salient subject, background last."""
    fields = []
    for k, (cx, cy, rx, ry) in enumerate(regions):
        d = np.hypot((nx - cx) / max(rx, 0.04), (ny - cy) / max(ry, 0.04))
        fields.append(0.08 * k + d * 0.28)
    subj = 0.30 + (1 - sal_small) * 0.45
    edge = 0.62 + np.abs(nx - 0.5) * 0.5 + np.abs(ny - 0.5) * 0.3
    return np.minimum.reduce(fields + [subj, edge])


def build_mask(h, w, seed, angle, streak_len, streak_amt, coarse_amt, regions, sal):
    """Reveal-order map: a smooth front spreading outward from the focus with a brushy edge, rank-equalised
    so scroll progress maps linearly to painted area and every pixel gets its turn exactly once."""
    r = np.random.default_rng(seed)
    mh, mw = h // 2, w // 2
    yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)
    field = priority_field(xx / mw, yy / mh, regions, cv2.resize(sal, (mw, mh)))
    k = np.zeros((streak_len, streak_len), np.float32)
    c = streak_len // 2
    dx, dy = math.cos(math.radians(angle)), -math.sin(math.radians(angle))
    cv2.line(k, (int(c - dx * c), int(c - dy * c)), (int(c + dx * c), int(c + dy * c)), 1.0, 1)
    k /= k.sum()
    streak = cv2.filter2D(r.standard_normal((mh, mw)).astype(np.float32), -1, k)
    streak /= streak.std() + 1e-6
    coarse = smooth_noise(mh, mw, 48, seed + 100)
    coarse /= coarse.std() + 1e-6
    m = field + streak_amt * streak + coarse_amt * coarse
    order = np.argsort(np.argsort(m.ravel())).reshape(m.shape).astype(np.float32) / (m.size - 1)
    return np.clip(cv2.GaussianBlur(order, (0, 0), 0.8) * 255, 0, 255).astype(np.uint8)


def chaikin(p, iterations=2):
    for _ in range(iterations):
        q = np.empty((len(p) * 2 - 2, 2), np.float32)
        q[0::2] = 0.75 * p[:-1] + 0.25 * p[1:]
        q[1::2] = 0.25 * p[:-1] + 0.75 * p[1:]
        p = np.vstack([p[:1], q, p[-1:]])
    return p


def build_lines(img_bgr, h, w, regions, sal, density=1.0, seed=1503):
    """Contour strokes. Edges are found on a small, smoothed copy so texture and noise vanish and only real
    forms survive; strokes are smoothed, scaled back up and ordered from the focus outwards."""
    rnd = np.random.default_rng(seed)
    ws = int(600 * math.sqrt(density))
    small = cv2.resize(img_bgr, (ws, int(ws * h / w)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    for _ in range(2):
        gray = cv2.bilateralFilter(gray, 9, 50, 9)
    gray = cv2.GaussianBlur(gray, (0, 0), 1.2)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(6, 6)).apply(gray)
    med = float(np.median(gray))
    edges = cv2.Canny(gray, max(10, 0.45 * med), max(40, 1.2 * med))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    sx = w / ws
    sal_s = cv2.resize(sal, (64, 64))
    strokes = []
    for c in contours:
        if cv2.arcLength(c, False) < 28:
            continue
        a = cv2.approxPolyDP(c, 0.7, False)[:, 0, :].astype(np.float32)
        if len(a) < 3:
            continue
        a = chaikin(a) * sx
        length = float(np.sum(np.linalg.norm(np.diff(a, axis=0), axis=1)))
        cx, cy = a[:, 0].mean() / w, a[:, 1].mean() / h
        pri = priority_field(np.array([[cx]]), np.array([[cy]]), regions,
                             np.array([[sal_s[min(63, int(cy * 64)), min(63, int(cx * 64))]]]))[0, 0]
        strokes.append({"pts": a, "len": length, "pri": float(pri) + rnd.uniform(0, 0.04)})
    strokes.sort(key=lambda s: s["pri"])
    return [{"d": "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in s["pts"]), "len": round(s["len"], 1)} for s in strokes]


def build_guides(w, h, regions, box):
    P = lambda x, y: [round(x * w, 1), round(y * h, 1)]
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = regions[0]
    g = [
        {"type": "line", "a": P(cx, 0.03), "b": P(cx, 0.97), "label": "axis"},
        {"type": "rect", "x": round(x0 * w, 1), "y": round(y0 * h, 1), "w": round((x1 - x0) * w, 1), "h": round((y1 - y0) * h, 1),
         "label": "block-in", "lx": round(x0 * w + 8, 1), "ly": round(y0 * h - 10, 1)},
        {"type": "line", "a": P(cx, max(0.02, y0 - 0.02)), "b": P(max(0.02, x0 - 0.05), min(0.98, y1)), "label": "triangle"},
        {"type": "line", "a": P(cx, max(0.02, y0 - 0.02)), "b": P(min(0.98, x1 + 0.05), min(0.98, y1)), "label": "triangle"},
        {"type": "line", "a": P(0.02, 1 / 3), "b": P(0.98, 1 / 3), "label": "thirds"},
        {"type": "line", "a": P(0.02, 2 / 3), "b": P(0.98, 2 / 3), "label": "thirds"},
    ]
    for i, (fx, fy, frx, fry) in enumerate(regions[:3]):
        g.append({"type": "ellipse", "c": P(fx, fy), "r": [round(frx * w * 1.15, 1), round(fry * h * 1.2, 1)], "rot": 0,
                  "label": "focus" if i == 0 else f"focus {i + 1}"})
    return g


# ---------------------------------------------------------------- scene builder

def build(sec: ArtworkScene, ctx: BuildContext, theme: dict) -> dict:
    src_path = resolve_image(ctx.project, sec.image, ctx.log)
    web = ctx.web
    names = ["paper.jpg", "tone.jpg", "under.jpg", "final.jpg", "mask_tone.png", "mask_under.png", "mask_color.png",
             "lines.json", "guides.json"]
    outs = [web / n for n in names]
    key = {"v": VERSION, "img": image_key(sec.image), "file": file_key(src_path), "focus": sec.focus, "w": sec.width,
           "density": sec.line_density, "under": sec.underpaint, "paper": sec.paper}
    meta = {}

    def run():
        src = Image.open(src_path).convert("RGB")
        W = sec.width
        H = round(W * src.height / src.width)
        img = np.asarray(src.resize((W, H), Image.LANCZOS), np.float32)
        bgr = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2BGR)
        regions, sal = detect_focus(bgr, ctx.log)
        if sec.focus != "auto":
            regions = [(float(x), float(y), 0.12, 0.14) for x, y in sec.focus]
        lum = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]) / 255
        paper = build_paper(H, W, _hex(sec.paper))
        layers = {"paper": paper, "tone": build_tone(lum, paper), "under": build_under(lum, paper, _hex(sec.underpaint)), "final": img}
        for k, v in layers.items():
            Image.fromarray(np.clip(v, 0, 255).astype(np.uint8)).save(web / f"{k}.jpg", quality=88, optimize=True, progressive=True)
        ctx.progress(0.4, "masks")
        for name, args in {"tone": (11, 45, 41, 0.035, 0.030), "under": (12, 20, 61, 0.045, 0.040), "color": (13, -30, 35, 0.030, 0.030)}.items():
            Image.fromarray(build_mask(H, W, *args, regions, sal)).save(web / f"mask_{name}.png", optimize=True)
        ctx.progress(0.7, "contours")
        lines = build_lines(bgr, H, W, regions, sal, sec.line_density)
        (web / "lines.json").write_text(json.dumps({"w": W, "h": H, "strokes": lines}, separators=(",", ":")))
        (web / "guides.json").write_text(json.dumps({"w": W, "h": H, "guides": build_guides(W, H, regions, subject_box(sal))}))
        ctx.log(f"  {W}x{H}, {len(lines)} strokes")

    ctx.stage("layers", key, outs, run)
    W = sec.width
    with Image.open(web / "final.jpg") as im:
        size = list(im.size)
    cfg = {
        "size": size, "stages": sec.stages, "paper": sec.paper,
        "layers": {n.split(".")[0]: ctx.url(web / n) for n in names[:7]},
        "lines": ctx.url(web / "lines.json"), "guides": ctx.url(web / "guides.json"),
        "end": ctx.url(web / "final.jpg"), "credits": [c for c in [credit(sec.image)] if c],
    }
    return cfg
