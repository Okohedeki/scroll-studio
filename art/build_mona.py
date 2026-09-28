"""Build the layers for the scroll-drawn Mona Lisa from the real (public-domain) painting.

Everything derives from one source image, so every stage lines up exactly with the finished painting
and nothing can drift or mutate the way generated video does.

  python art/build_mona.py            -> web/media/mona/*  (+ art/out/preview_*.jpg stage previews)

Layers (all W x H, same framing):
  paper.jpg   blank primed paper
  tone.jpg    graphite value study (shading + light hatching on the paper)
  under.jpg   umber underpainting (monochrome brown, softened)
  final.jpg   the painting
  mask_*.png  brush-order maps: a pixel is revealed once scroll progress passes its value
  lines.json  charcoal contour strokes, ordered face -> hands -> figure -> landscape
  guides.json proportion / composition construction lines
"""
import json
import math
import os

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src", "mona_lisa.jpg")
OUT = os.path.join(HERE, "..", "web", "media", "mona")
PREVIEW = os.path.join(HERE, "out")
W = 1800
rng = np.random.default_rng(1503)  # the year Leonardo started it

# Landmarks in normalised (x, y) image coordinates, measured on the painting.
FACE = (0.46, 0.225)
HANDS = (0.43, 0.82)


def save_jpg(arr, name, q=90, folder=None):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(folder or OUT, name), quality=q,
                                                                  optimize=True, progressive=True)


def smooth_noise(h, w, scale, seed):
    r = np.random.default_rng(seed).standard_normal((max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(r, (w, h), interpolation=cv2.INTER_CUBIC)


def build_paper(h, w):
    base = np.array([241, 235, 223], np.float32)
    grain = smooth_noise(h, w, 2, 1) * 2.2 + smooth_noise(h, w, 9, 2) * 2.5 + smooth_noise(h, w, 60, 3) * 3.0
    paper = base[None, None, :] + grain[..., None]
    # faint vignette, like a sheet under a studio lamp
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2)
    paper *= (1 - 0.10 * v)[..., None]
    return paper


def build_tone(lum, paper):
    h, w = lum.shape
    # Local-contrast value study: lift the sfumato so the drawing reads like graphite, not a photo.
    l8 = (lum * 255).astype(np.uint8)
    l8 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l8)
    v = cv2.GaussianBlur(l8.astype(np.float32) / 255, (0, 0), 1.1)
    v = np.clip((v - 0.08) / 0.84, 0, 1) ** 0.85
    dark = 1 - v
    # Directional hatching that only shows in the darker passages.
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    hatch = 0.5 + 0.5 * np.sin((xx * 0.70 + yy * 0.72) * 0.9 + smooth_noise(h, w, 40, 4) * 2.0)
    hatch = np.clip((hatch - 0.35) * 1.8, 0, 1)
    graphite = np.clip(dark * 0.82 + hatch * dark * 0.22, 0, 1)
    ink = np.array([46, 43, 41], np.float32)
    out = paper * (1 - graphite[..., None]) + ink * graphite[..., None]
    return out


def build_under(lum, paper):
    # Monochrome umber: dark umber -> burnt sienna -> warm ochre, softened like a first lay-in.
    v = cv2.GaussianBlur(lum.astype(np.float32), (0, 0), 1.6)
    v = np.clip((v - 0.05) / 0.9, 0, 1)
    stops = np.array([[38, 24, 16], [96, 56, 30], [158, 98, 52], [214, 172, 112], [236, 212, 164]], np.float32)
    pos = v * (len(stops) - 1)
    i0 = np.clip(pos.astype(int), 0, len(stops) - 2)
    t = (pos - i0)[..., None]
    col = stops[i0] * (1 - t) + stops[i0 + 1] * t
    # let the paper tooth show through the thin paint
    col = col * 0.93 + paper * 0.07
    return col


def region_priority(nx, ny):
    """0 = drawn first. Face, then hands, then the figure, landscape last."""
    d_face = math.hypot((nx - FACE[0]) / 0.12, (ny - FACE[1]) / 0.16)
    d_hand = math.hypot((nx - HANDS[0]) / 0.22, (ny - HANDS[1]) / 0.10)
    in_figure = 0.18 < nx < 0.85 and ny > 0.08 and not (ny < 0.45 and (nx < 0.30 or nx > 0.68))
    if d_face < 1.0:
        return 0.00 + 0.10 * d_face
    if d_hand < 1.0:
        return 0.15 + 0.10 * d_hand
    if in_figure:
        return 0.30 + 0.30 * ny
    return 0.70 + 0.25 * abs(nx - 0.5)


def chaikin(p, iterations=2):
    """Corner-cutting smoothing: turns stair-stepped edge polylines into flowing strokes."""
    for _ in range(iterations):
        q = np.empty((len(p) * 2 - 2, 2), np.float32)
        q[0::2] = 0.75 * p[:-1] + 0.25 * p[1:]
        q[1::2] = 0.25 * p[:-1] + 0.75 * p[1:]
        p = np.vstack([p[:1], q, p[-1:]])
    return p


def build_lines(img_bgr, h, w):
    """Charcoal contours. Edges are found on a small, smoothed copy so the varnish crackle and fabric
    texture vanish and only real forms (hair, eyes, mouth, hands, neckline) survive; strokes are then
    smoothed and scaled back up."""
    ws = 600
    small = cv2.resize(img_bgr, (ws, int(ws * h / w)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    for _ in range(2):
        gray = cv2.bilateralFilter(gray, 9, 50, 9)
    gray = cv2.GaussianBlur(gray, (0, 0), 1.2)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(6, 6)).apply(gray)
    edges = cv2.Canny(gray, 30, 80)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    sx = w / ws
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
        strokes.append({"pts": a, "len": length, "pri": region_priority(cx, cy) + rng.uniform(0, 0.04)})
    strokes.sort(key=lambda s: s["pri"])
    out = []
    for s in strokes:
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in s["pts"])
        out.append({"d": d, "len": round(s["len"], 1)})
    return out


def build_guides(w, h):
    """Construction lines an instructor would lay in first (normalised landmarks -> pixels)."""
    P = lambda x, y: [round(x * w, 1), round(y * h, 1)]
    return [
        {"type": "line", "a": P(0.50, 0.03), "b": P(0.50, 0.97), "label": "vertical axis"},
        {"type": "line", "a": P(0.52, 0.09), "b": P(0.06, 0.97), "label": "pyramid"},
        {"type": "line", "a": P(0.52, 0.09), "b": P(0.95, 0.97), "label": "pyramid"},
        {"type": "ellipse", "c": P(0.465, 0.232), "r": [round(0.095 * w, 1), round(0.118 * h, 1)], "rot": -8,
         "label": "head"},
        {"type": "line", "a": P(0.33, 0.224), "b": P(0.60, 0.224), "label": "eye line"},
        {"type": "line", "a": P(0.35, 0.305), "b": P(0.56, 0.305), "label": "mouth"},
        {"type": "line", "a": P(0.02, 0.40), "b": P(0.30, 0.40), "label": "horizon (left)"},
        {"type": "line", "a": P(0.70, 0.33), "b": P(0.98, 0.33), "label": "horizon (right)"},
        {"type": "line", "a": P(0.18, 0.56), "b": P(0.84, 0.50), "label": "shoulders"},
        {"type": "ellipse", "c": P(0.44, 0.82), "r": [round(0.19 * w, 1), round(0.055 * h, 1)], "rot": 4,
         "label": "hands"},
    ]


def build_mask(h, w, seed, angle, streak_len, streak_amt, coarse_amt):
    """Reveal-order map: a smooth front spreading face -> hands -> figure -> landscape, with a brushy edge.

    order = rank(priority field + directional streak noise). Ranking (histogram equalisation) makes
    scroll progress map linearly to painted area, and there are no holes: every pixel's turn comes
    exactly once as the front sweeps past.
    """
    r = np.random.default_rng(seed)
    mh, mw = h // 2, w // 2
    yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)
    nx, ny = xx / mw, yy / mh
    d_face = np.hypot((nx - FACE[0]) / 0.12, (ny - FACE[1]) / 0.16)
    d_hand = np.hypot((nx - HANDS[0]) / 0.22, (ny - HANDS[1]) / 0.10)
    figure = np.hypot((nx - 0.5) / 0.36, (ny - 0.62) / 0.55)
    field = np.minimum.reduce([d_face * 0.30, 0.22 + d_hand * 0.25, 0.30 + figure * 0.35,
                               0.62 + np.abs(nx - 0.5) * 0.5 + (1 - ny) * 0.15])
    # directional streaks: white noise smeared along the brush angle
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
    order = cv2.GaussianBlur(order, (0, 0), 0.8)
    return np.clip(order * 255, 0, 255).astype(np.uint8)


def composite(layers, masks, p_tone, p_under, p_color, soft=0.06):
    """Python mirror of the page's WebGL shader, used for previews."""
    def reveal(mask, p):
        m = cv2.resize(mask, (layers["final"].shape[1], layers["final"].shape[0])).astype(np.float32) / 255
        return np.clip((p * (1 + soft) - m) / soft, 0, 1)[..., None]
    c = layers["paper"]
    c = c * (1 - reveal(masks["tone"], p_tone)) + layers["tone"] * reveal(masks["tone"], p_tone)
    c = c * (1 - reveal(masks["under"], p_under)) + layers["under"] * reveal(masks["under"], p_under)
    c = c * (1 - reveal(masks["color"], p_color)) + layers["final"] * reveal(masks["color"], p_color)
    return c


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    src = Image.open(SRC).convert("RGB")
    H = round(W * src.height / src.width)
    img = np.asarray(src.resize((W, H), Image.LANCZOS), np.float32)
    lum = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]) / 255

    paper = build_paper(H, W)
    tone = build_tone(lum, paper)
    under = build_under(lum, paper)
    layers = {"paper": paper, "tone": tone, "under": under, "final": img}
    for k, v in layers.items():
        save_jpg(v, f"{k}.jpg", q=88)

    masks = {
        "tone": build_mask(H, W, 11, 45, 41, 0.035, 0.030),
        "under": build_mask(H, W, 12, 20, 61, 0.045, 0.040),
        "color": build_mask(H, W, 13, -30, 35, 0.030, 0.030),
    }
    for k, v in masks.items():
        Image.fromarray(v).save(os.path.join(OUT, f"mask_{k}.png"), optimize=True)

    lines = build_lines(cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2BGR), H, W)
    guides = build_guides(W, H)
    with open(os.path.join(OUT, "lines.json"), "w") as f:
        json.dump({"w": W, "h": H, "strokes": lines}, f, separators=(",", ":"))
    with open(os.path.join(OUT, "guides.json"), "w") as f:
        json.dump({"w": W, "h": H, "guides": guides}, f)

    # Stage previews (lines are drawn by the browser, so previews show paint layers only)
    for name, pt, pu, pc in [("tone50", 0.5, 0, 0), ("tone100", 1, 0, 0), ("under60", 1, 0.6, 0),
                             ("color40", 1, 1, 0.4), ("color100", 1, 1, 1)]:
        save_jpg(cv2.resize(composite(layers, masks, pt, pu, pc), (600, round(600 * H / W))), f"preview_{name}.jpg", folder=PREVIEW)
    total = sum(s["len"] for s in lines)
    sizes = {f: os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)}
    print(f"{W}x{H} | {len(lines)} strokes, {total:.0f} px of line | {len(guides)} guides")
    print({k: f"{v / 1e6:.2f} MB" for k, v in sorted(sizes.items())}, f"total {sum(sizes.values()) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
