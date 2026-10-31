"""`studio ads`: placement-sized ads from the picked product stills (issue #179).

For each shot in `outputs.ads.shots`, the still is the shot's pick (else the top of its shortlist). It is reframed to
each size around the product's mask, so the product stays whole: the crop is centred on the product and, where the
size needs more backdrop than the still has, the still's edges are stretched and softened to fill. The headline and
call to action are set on a band in the brand's colours. Files land in <project>/ads/, with ads.json listing them.
"""
from __future__ import annotations

import json
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .project import BuildError, Project

RATIOS = {"1x1": 1.0, "4x5": 4 / 5, "9x16": 9 / 16, "16x9": 16 / 9, "1.91x1": 1.91}


def mask_box(mask: Image.Image) -> tuple[int, int, int, int]:
    a = np.asarray(mask) > 127
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return 0, 0, mask.width, mask.height
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def reframe(img: Image.Image, mask: Image.Image, ratio: float, width: int, keep_bottom: float = 0.0) -> tuple[Image.Image, Image.Image]:
    """(image, mask) at width x width/ratio, the product whole and as large as the still allows. `keep_bottom` is the
    share of the height kept clear for the copy band (the product sits above it)."""
    w, h = img.size
    x0, y0, x1, y1 = mask_box(mask)
    target_h = round(width / ratio)
    # the largest crop of this ratio inside the still that holds the product
    cw = min(w, h * ratio)
    ch = cw / ratio
    if cw < (x1 - x0) or ch * (1 - keep_bottom) < (y1 - y0):       # too tight: pad the still instead of cutting it
        need = max((x1 - x0) * 1.15 / cw, (y1 - y0) * 1.15 / (ch * (1 - keep_bottom)))
        cw, ch = cw * need, ch * need
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2 + ch * keep_bottom / 2
    left, top = cx - cw / 2, cy - ch / 2
    box = (round(left), round(top), round(left + cw), round(top + ch))
    out = _crop_extend(img, box).resize((width, target_h), Image.LANCZOS)
    m = _crop_extend(mask, box, fill=0).resize((width, target_h), Image.LANCZOS)
    return out, m


def _crop_extend(img: Image.Image, box: tuple[int, int, int, int], fill: Optional[int] = None) -> Image.Image:
    """img.crop(box). Whatever falls outside the still is `fill`, or (by default) the still's edge pixels carried
    outward and softened more the further they reach, so the backdrop continues without a seam."""
    x0, y0, x1, y1 = box
    if x0 >= 0 and y0 >= 0 and x1 <= img.width and y1 <= img.height:
        return img.crop(box)
    W, H = x1 - x0, y1 - y0
    if fill is not None:
        canvas = Image.new(img.mode, (W, H), fill)
        canvas.paste(img, (-x0, -y0))
        return canvas
    a = np.asarray(img)
    pads = ((max(0, -y0), max(0, y1 - img.height)), (max(0, -x0), max(0, x1 - img.width)))
    if a.ndim == 3:
        pads += ((0, 0),)
    padded = np.pad(a, pads, mode="edge")
    ox, oy = max(0, x0), max(0, y0)
    out = Image.fromarray(padded[oy:oy + H, ox:ox + W])
    soft = out.filter(ImageFilter.GaussianBlur(max(W, H) / 60))
    # weight: 0 inside the still, rising to 1 a little way into the extension
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ix0, iy0 = -x0, -y0
    dx = np.maximum(np.maximum(ix0 - xx, xx - (ix0 + img.width - 1)), 0)
    dy = np.maximum(np.maximum(iy0 - yy, yy - (iy0 + img.height - 1)), 0)
    wgt = np.clip(np.maximum(dx, dy) / (max(W, H) * 0.03), 0, 1)
    if a.ndim == 3:
        wgt = wgt[..., None]
    mixed = np.asarray(out, np.float32) * (1 - wgt) + np.asarray(soft, np.float32) * wgt
    return Image.fromarray(mixed.astype(np.uint8))


def _font(size: int, bold: bool = False):
    for name in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), ("arialbd.ttf" if bold else "arial.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_w: int, size: int, bold: bool, min_size: int = 12):
    """(font, lines): the largest font from `size` down whose words wrap into at most two lines of max_w."""
    while True:
        font = _font(size, bold)
        lines, cur = [], ""
        for word in text.split():
            trial = f"{cur} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        if (len(lines) <= 2 and all(draw.textlength(ln, font=font) <= max_w for ln in lines)) or size <= min_size:
            return font, lines
        size -= 2


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def set_copy(img: Image.Image, headline: str, cta: str, colours: tuple[str, str]) -> tuple[Image.Image, dict]:
    """The ad with a copy band at the bottom: headline, then the call to action as a pill. Returns the layout boxes."""
    if not headline and not cta:
        return img, {}
    w, h = img.size
    band_h = round(h * (0.24 if h > w * 1.3 else 0.3 if h >= w else 0.34))
    out = img.convert("RGB").copy()
    d = ImageDraw.Draw(out)
    bg, fg = _hex(colours[0]), _hex(colours[1])
    d.rectangle((0, h - band_h, w, h), fill=bg)
    pad = round(w * 0.07)
    layout: dict = {"band": [0, h - band_h, w, h]}
    top, bottom = h - band_h + round(band_h * 0.15), h - round(band_h * 0.13)
    cta_size = round(band_h * 0.13)
    head_size = round(band_h * 0.24)
    while True:      # shrink the headline until it, a gap and the call to action stack inside the band
        font, lines = fit_text(d, headline, w - 2 * pad, head_size, True) if headline else (None, [])
        cfont, clines = fit_text(d, cta, w - 2 * pad - 2 * cta_size, cta_size, True) if cta else (None, [])
        text_h = round(font.size * 1.15) * len(lines) if font else 0
        pill_h = round(cfont.size * 2.0) if cfont else 0
        gap = round(band_h * 0.07) if font and cfont else 0
        if text_h + gap + pill_h <= bottom - top or head_size <= 12:
            break
        head_size -= 2
        cta_size = max(12, min(cta_size, head_size - 2))
    y = top + max(0, (bottom - top - text_h - gap - pill_h) // 2)
    if font:
        for ln in lines:
            d.text((pad, y), ln, font=font, fill=fg)
            y += round(font.size * 1.15)
        layout["headline"] = {"lines": lines, "size": font.size, "bottom": y}
        y += gap
    if cfont:
        line = clines[0]
        tw = d.textlength(line, font=cfont)
        box = (pad, y, round(pad + tw + cfont.size * 2), y + pill_h)
        d.rounded_rectangle(box, radius=pill_h // 2, fill=fg)
        d.text((pad + cfont.size, y + (pill_h - cfont.size) / 2 - cfont.size * 0.1), line, font=cfont, fill=bg)
        layout["cta"] = {"text": line, "size": cfont.size, "box": list(box)}
    return out, layout


def brand_colours(project: Project) -> tuple[str, str]:
    """(band colour, text colour) from the project's brand, or a quiet default."""
    try:
        from .compile import themes
        spec = project.load_project()
        if spec.brand is not None:
            c = themes.resolve(spec.brand)["colors"]
            band, text = c.get("accent"), c.get("accent_ink") or c.get("bg")
            if all(isinstance(x, str) and len(x) == 7 and x.startswith("#") for x in (band, text)):
                return band, text
    except Exception:       # a brand that can't be read leaves the default band
        pass
    return "#1d1f24", "#f4f1ea"


def make(project: Project, log: Callable[[str], None] = print) -> dict:
    from .stills import run as stills
    spec = project.load_project() if project.is_project_file else None
    if spec is None or spec.outputs.ads is None:
        raise BuildError(f"{project.name} has no outputs.ads in project.yaml (docs/stills.md#ads)")
    ads = spec.outputs.ads
    state = stills.load(project)
    if not state or not state.get("candidates"):
        raise BuildError(f"{project.name} has no product stills yet: run `studio stills {project.name}` first")
    by_id = {c["id"]: c for c in state["candidates"]}
    colours = brand_colours(project)
    out_dir = project.root / "ads"
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for shot in ads.shots:
        cid = state.get("picked", {}).get(shot) or next(iter(state.get("shortlist", {}).get(shot) or []), None)
        if cid is None or cid not in by_id:
            log(f"  ads: no {shot} still to use, skipped")
            continue
        c = by_id[cid]
        img = Image.open(stills.folder(project) / c["image"]).convert("RGB")
        mask = Image.open(stills.folder(project) / c["image"].replace(".png", ".mask.png")).convert("L")
        for size in ads.sizes:
            ratio = RATIOS[size]
            band = 0.0 if not (ads.headline or ads.cta) else (0.24 if ratio < 1 / 1.3 else 0.3 if ratio <= 1 else 0.34)
            frame, fmask = reframe(img, mask, ratio, ads.width, keep_bottom=band)
            final, layout = set_copy(frame, ads.headline, ads.cta, colours)
            path = out_dir / f"{shot}-{size}.png"
            final.save(path)
            made.append({"file": path.name, "shot": shot, "size": size, "from": cid, "width": final.width,
                         "height": final.height, "product_box": list(mask_box(fmask)), **layout})
            log(f"  ads: {path.name}")
    (out_dir / "ads.json").write_text(json.dumps({"ads": made, "colours": colours}, indent=2), encoding="utf-8")
    return {"ads": made, "folder": str(out_dir)}
