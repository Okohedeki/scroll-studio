"""vector: an SVG (or a raster image vectorised with vtracer) whose strokes draw themselves, then fill.

The builder normalises the drawing into one clean SVG: scripts and external references stripped, every shape a
<path> with its fill kept as data-fill, and paths sorted into drawing order (centre-out, left-right, top-down).
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

from ..inputs import credit, image_key, resolve_image, resolve_path
from ..project import BuildContext, BuildError, file_key
from ..spec import VectorScene

VERSION = 2
NS = "http://www.w3.org/2000/svg"
NUM = re.compile(r"-?\d*\.?\d+(?:e-?\d+)?")


def _vectorise(src: Path, out: Path, sec: VectorScene, log) -> None:
    import vtracer
    im = Image.open(src).convert("L")
    if im.width > sec.max_width:
        im = im.resize((sec.max_width, round(sec.max_width * im.height / im.width)), Image.LANCZOS)
    ink = np.asarray(im) < sec.threshold
    bw = Image.fromarray(np.where(ink, 0, 255).astype(np.uint8)).convert("RGB")
    tmp = out.with_suffix(".bw.png")
    bw.save(tmp)
    speckle = max(2, int(round(10 / max(sec.detail, 0.1))))
    vtracer.convert_image_to_svg_py(str(tmp), str(out), colormode="binary", hierarchical="cutout", mode="spline",
                                    filter_speckle=speckle, corner_threshold=60, length_threshold=4.0,
                                    splice_threshold=45, path_precision=2)
    tmp.unlink(missing_ok=True)
    log(f"  vectorised {src.name} at {im.width}x{im.height}")


def _translate(el) -> tuple[float, float]:
    m = re.search(r"translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)", el.get("transform", ""))
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)


def _normalise(svg_path: Path, out: Path, sec: VectorScene) -> dict:
    ET.register_namespace("", NS)
    root = ET.parse(svg_path).getroot()
    vb = root.get("viewBox")
    if vb:
        x0, y0, w, h = (float(v) for v in vb.replace(",", " ").split())
    else:
        w, h = float(re.sub(r"[^\d.]", "", root.get("width", "1000"))), float(re.sub(r"[^\d.]", "", root.get("height", "1000")))
        x0 = y0 = 0.0
    paths = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("script", "foreignObject"):
            continue
        if tag != "path" or not el.get("d"):
            continue
        nums = [float(n) for n in NUM.findall(el.get("d"))[:40]]
        tx, ty = _translate(el)
        xs, ys = nums[0::2], nums[1::2]
        cx = (sum(xs) / max(len(xs), 1)) + tx
        cy = (sum(ys) / max(len(ys), 1)) + ty
        fill = el.get("fill") or (re.search(r"fill:\s*([^;]+)", el.get("style", "")) or [None, "#000"])[1]
        paths.append({"d": el.get("d"), "t": el.get("transform", ""), "fill": fill, "cx": cx, "cy": cy,
                      "size": len(el.get("d"))})
    if not paths:
        raise BuildError("the SVG has no <path> elements (convert shapes to paths first)")
    # vtracer's binary mode emits a white background/hole fills: keep only ink-coloured paths
    def dark(c):
        c = (c or "#000").strip().lower()
        if c in ("none", "transparent"):
            return False
        m = re.fullmatch(r"#([0-9a-f]{6})", c)
        return not m or sum(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) < 600
    ink = [p for p in paths if dark(p["fill"])] if sec.image is not None and sec.svg is None else paths
    mx, my = x0 + w / 2, y0 + h / 2
    key = {"center": lambda p: math.hypot((p["cx"] - mx) / w, (p["cy"] - my) / h),
           "left": lambda p: p["cx"], "top": lambda p: p["cy"], "document": lambda p: 0}[sec.order]
    ink.sort(key=key)
    body = []
    for p in ink:
        t = f' transform="{p["t"]}"' if p["t"] else ""
        body.append(f'<path d="{p["d"]}"{t} data-fill="{p["fill"]}"/>')
    out.write_text(f'<svg xmlns="{NS}" viewBox="{x0:g} {y0:g} {w:g} {h:g}">' + "".join(body) + "</svg>", encoding="utf-8")
    return {"paths": len(ink), "size": [w, h]}


def build(sec: VectorScene, ctx: BuildContext, theme: dict) -> dict:
    if not sec.svg and sec.image is None:
        raise BuildError(f"vector section '{sec.id}' needs `svg` or `image`")
    src = resolve_path(ctx.project, sec.svg, ctx.log) if sec.svg else resolve_image(ctx.project, sec.image, ctx.log)
    out = ctx.web / "drawing.svg"
    traced = ctx.work / "traced.svg"
    meta: dict = {}

    def run():
        svg_in = src
        if not sec.svg:
            _vectorise(src, traced, sec, ctx.log)
            svg_in = traced
        meta.update(_normalise(svg_in, out, sec))
        (ctx.work / "vector.json").write_text(str(meta))
        ctx.log(f"  {meta['paths']} paths")
    key = {"v": VERSION, "src": file_key(src), "svg": sec.svg, "img": image_key(sec.image) if sec.image else None,
           "order": sec.order, "detail": sec.detail, "threshold": sec.threshold, "w": sec.max_width}
    ctx.stage("vector", key, [out], run)
    vb = re.search(r'viewBox="([^"]+)"', out.read_text(encoding="utf-8")[:300]).group(1).split()
    return {"svg": ctx.url(out), "size": [float(vb[2]), float(vb[3])], "colors": sec.colors,
            "background": sec.background, "credits": [c for c in [credit(sec.image) if sec.image else None] if c]}
