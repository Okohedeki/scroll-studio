"""One candidate still: a backdrop for the shot and direction, the product cut-out composited onto it with a contact
shadow, and (where an edit backend can run) a light-blending pass whose change to the product is measured.

Backdrops: a packshot's is drawn locally (a seamless sweep in the direction's palette). A lifestyle scene is painted
by an image backend through the router; when none can run here, it is drawn locally from the palette, so the flow still
works on a laptop. A detail is the product close and cropped over a softened version of the scene.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageFilter

from .directions import Direction

# product height as a share of the frame, and where its base sits (share of the height from the top)
PLACE = {"packshot": (0.52, 0.84), "lifestyle": (0.40, 0.80), "detail": (0.95, 1.12)}

HARMONISE = ("Blend the product into the scene's light: match the light direction, colour temperature and shadows. "
             "Do not change the product's shape, colours, text, logo or proportions.")


@dataclass
class Made:
    image: Path
    mask: Path                     # the product's mask in the frame (L)
    composite: Path                # before any blending
    backend: str = "local"
    model: str = "drawn"
    prompt: str = ""
    harmonised: bool = False
    notes: list[str] = field(default_factory=list)


def _hex(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def sweep(size: tuple[int, int], palette: tuple[str, str, str], seed: int) -> Image.Image:
    """A seamless studio sweep: the backdrop colour falling into the surface colour, a soft light pool, fine grain."""
    w, h = size
    top, floor = np.array(_hex(palette[0]), np.float32), np.array(_hex(palette[1]), np.float32)
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    t = np.clip((y - 0.55) / 0.35, 0, 1) ** 1.6 * 0.55
    img = top * (1 - t) + floor * t
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    pool = np.exp(-(((xx - w * 0.5) / (w * 0.42)) ** 2 + ((yy - h * 0.62) / (h * 0.45)) ** 2))
    img = img * (0.86 + 0.18 * pool[..., None])
    rng = np.random.default_rng(seed)
    img += rng.normal(0, 2.2, img.shape).astype(np.float32)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def scene_prompt(d: Direction, describe: str) -> str:
    return (f"{d.setting}, {d.light}, {d.mood} mood, colours {', '.join(d.palette)}; an empty clear surface in the "
            f"foreground centre where a product will stand ({describe or 'a product'} not shown), no objects in the "
            "centre, professional product photograph, sharp, realistic")


def drawn_scene(size: tuple[int, int], d: Direction, seed: int) -> Image.Image:
    """A scene drawn with no model: a wall in the palette with a glow where the light comes from, and a surface in the
    surface colour meeting it at a soft horizon, shaded towards the front, so the product has somewhere to stand."""
    from ..inputs import render_gradient
    from ..spec import Glow, Gradient
    w, h = size
    rng = np.random.default_rng(seed)
    wall = Gradient(colors=[d.palette[0], d.palette[0], d.palette[2]], angle=180 + float(rng.uniform(-10, 10)),
                    glows=[Glow(x=float(rng.uniform(0.15, 0.85)), y=0.2, radius=0.55, color="#ffffff", strength=0.35)],
                    grain=0.025)
    img = np.asarray(render_gradient(wall, size, seed=seed).convert("RGB"), np.float32)
    horizon = h * float(rng.uniform(0.56, 0.66))
    y = np.arange(h, dtype=np.float32)[:, None, None]
    surf = np.array(_hex(d.palette[1]), np.float32) * (1.06 - 0.22 * np.clip((y - horizon) / (h - horizon), 0, 1))
    blend = np.clip((y - horizon) / (h * 0.012) + 0.5, 0, 1)
    img = img * (1 - blend) + surf * blend
    img += np.random.default_rng(seed + 1).normal(0, 2.0, img.shape).astype(np.float32)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def backdrop(shot: str, d: Direction, size: tuple[int, int], seed: int, describe: str, work: Path, policy=None,
             build: Optional[Path] = None, log: Callable[[str], None] = print) -> tuple[Image.Image, str, str, str]:
    """(image, backend, model, prompt) for the shot's backdrop."""
    if shot == "packshot":
        return sweep(size, d.palette, seed), "local", "sweep", ""
    from ..router import ImageJob, NoBackend, choose, route
    prompt = scene_prompt(d, describe)
    try:
        choose("image", policy)
    except NoBackend:
        return drawn_scene(size, d, seed), "local", "drawn", prompt
    digest = hashlib.sha1(f"{prompt}|{size}|{seed}".encode()).hexdigest()[:16]
    out = work / "scenes" / f"{digest}.png"
    made_by = out.with_suffix(".json")          # who painted a cached scene, so a candidate's record still names it
    if not out.exists():
        r = route(ImageJob(prompt, size[0], size[1], seed), out, policy, build=build, log=log)
        backend, model = r.backend, r.model
        made_by.write_text(json.dumps({"backend": backend, "model": model}), encoding="utf-8")
    else:
        try:
            rec = json.loads(made_by.read_text(encoding="utf-8"))
            backend, model = rec["backend"], rec["model"]
        except (OSError, ValueError, KeyError):
            backend, model = "cache", "cache"
    return Image.open(out).convert("RGB").resize(size, Image.LANCZOS), backend, model, prompt


def place(product: Image.Image, shot: str, size: tuple[int, int], seed: int) -> tuple[Image.Image, tuple[int, int]]:
    """The product scaled for the shot and the top-left where it goes."""
    w, h = size
    share, base = PLACE[shot]
    scale = share * h / product.height
    if shot != "detail":
        scale = min(scale, 0.86 * w / product.width)
    p = product.resize((max(1, round(product.width * scale)), max(1, round(product.height * scale))), Image.LANCZOS)
    rng = np.random.default_rng(seed)
    cx = w * (0.5 if shot != "lifestyle" else float(rng.choice([0.38, 0.5, 0.62])))
    return p, (round(cx - p.width / 2), round(base * h - p.height))


def shadow(size: tuple[int, int], box: tuple[int, int, int, int], strength: float = 0.58) -> Image.Image:
    """A soft contact shadow (L, 255 = no shadow) under the product's base."""
    w, h = size
    x0, y0, x1, y1 = box
    m = Image.new("L", size, 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(m)
    bw = (x1 - x0)
    d.ellipse((x0 - bw * 0.04, y1 - bw * 0.07, x1 + bw * 0.04, y1 + bw * 0.08), fill=150)
    d.ellipse((x0 + bw * 0.1, y1 - bw * 0.04, x1 - bw * 0.1, y1 + bw * 0.035), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(max(2, bw * 0.05)))
    a = np.asarray(m, np.float32) / 255 * strength
    return Image.fromarray((255 * (1 - a)).astype(np.uint8))


def composite(bg: Image.Image, product: Image.Image, shot: str, seed: int) -> tuple[Image.Image, Image.Image]:
    """(composite RGB, product mask L) with the product's pixels exactly as cut out."""
    size = bg.size
    p, (x, y) = place(product, shot, size, seed)
    if shot == "detail":
        bg = bg.filter(ImageFilter.GaussianBlur(size[0] * 0.012))
    box = (x, y, x + p.width, y + p.height)
    out = Image.fromarray((np.asarray(bg, np.float32) * (np.asarray(shadow(size, box), np.float32)[..., None] / 255))
                          .astype(np.uint8))
    out.paste(p.convert("RGB"), (x, y), p.getchannel("A"))
    mask = Image.new("L", size, 0)
    mask.paste(p.getchannel("A"), (x, y))
    return out, mask


def make(product: Image.Image, shot: str, d: Direction, seed: int, size: tuple[int, int], describe: str, work: Path,
         name: str, harmonise: bool = True, fidelity: float = 0.06, policy=None, build: Optional[Path] = None,
         log: Callable[[str], None] = print) -> Made:
    """The candidate `name`: written to work/<name>.png with its mask and its unblended composite."""
    from . import critics
    work.mkdir(parents=True, exist_ok=True)
    bg, backend, model, prompt = backdrop(shot, d, size, seed, describe, work, policy, build, log)
    comp, mask = composite(bg, product, shot, seed)
    paths = Made(work / f"{name}.png", work / f"{name}.mask.png", work / f"{name}.composite.png", backend, model, prompt)
    comp.save(paths.composite)
    mask.save(paths.mask)
    final = comp
    if harmonise and shot != "packshot":
        from ..router import EditJob, NoBackend, choose, route
        try:
            choose("edit", policy)
        except NoBackend:
            paths.notes.append("no edit backend here: composite kept unblended")
        else:
            blended = work / f"{name}.blend.png"
            try:
                route(EditJob((str(paths.composite),), HARMONISE, seed), blended, policy, build=build, log=log)
                b = Image.open(blended).convert("RGB").resize(size, Image.LANCZOS)
                change = critics.product_change(comp, b, mask)
                if change <= fidelity:
                    final, paths.harmonised = b, True
                else:
                    paths.notes.append(f"blending changed the product by {change:.3f} (over {fidelity}): kept the composite")
            except Exception as e:     # a provider failure leaves the composite, which is already a valid candidate
                paths.notes.append(f"blending failed ({e}): kept the composite")
    final.save(paths.image)
    return paths
