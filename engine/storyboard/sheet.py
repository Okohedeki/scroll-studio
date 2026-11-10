"""The storyboard sheet: storyboard.html (to browse) and sheet.jpg (one image an agent can read), one card per shot."""
from __future__ import annotations

import html
import time
from pathlib import Path

from ..fidelity import font, wrap
from ..plan import fmt
from ..region import outline_of as region_outline
from .cards import Card, _digest

STATUS = {"new": "#3d8bfd", "changed": "#ff8a3d", "unchanged": "#7c818c", "locked": "#a479f0", "rendered": "#2fb67c"}
LEVEL = {"final": "#2fb67c", "stills": "#3d8bfd", "sketch": "#c9a227", "placeholder": "#7c818c"}
BG, PANEL, INK, DIM, LINE = "#111214", "#1b1c20", "#eceef2", "#9aa0aa", "#2c2e34"


def thumbs(cards: list[Card], out: Path, width: int = 640) -> dict[str, list[str]]:
    """Small JPGs of every frame in out/frames/ (the sheet and the HTML use them; the folder stands alone)."""
    from PIL import Image
    d = out / "frames"
    d.mkdir(parents=True, exist_ok=True)
    keep, res = set(), {}
    for c in cards:
        names = []
        for f in c.frames:
            st = f.path.stat()
            ol = region_outline(f.path)          # an image edited inside a region: its outline is drawn on the card
            name = f"{_digest([str(f.path), st.st_size, int(st.st_mtime), width, ol.stat().st_mtime_ns if ol else 0])}.jpg"
            dst = d / name
            if not dst.exists():
                im = Image.open(f.path)
                if im.mode in ("RGBA", "LA", "P"):
                    im = im.convert("RGBA")
                    flat = Image.new("RGBA", im.size, (40, 42, 47, 255))
                    flat.alpha_composite(im)
                    im = flat
                im = im.convert("RGB")
                im.thumbnail((width, width), Image.LANCZOS)
                if ol:
                    mark = Image.open(ol).convert("RGBA").resize(im.size, Image.LANCZOS)
                    im = im.convert("RGBA")
                    im.alpha_composite(mark)
                    im = im.convert("RGB")
                im.save(dst, quality=84)
            keep.add(name)
            names.append(f"frames/{name}")
        res[c.id] = names
    for f in d.glob("*.jpg"):
        if f.name not in keep:
            f.unlink()
    return res


def _cover(im, w: int, h: int):
    from PIL import Image
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def sheet_jpg(cards: list[Card], files: dict, out: Path, head: dict) -> Path:
    from PIL import Image, ImageDraw
    W, cols, gap, pad = 2400, 3 if len(cards) > 4 else max(1, len(cards)), 28, 40
    cw = (W - 2 * pad - (cols - 1) * gap) // cols
    th = round(cw * 0.36)
    ch = th + 300
    rows = (len(cards) + cols - 1) // cols
    H = 190 + rows * (ch + gap) + pad
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    f_t, f_h, f_b, f_s, f_x = font(46, True), font(26, True), font(22), font(19), font(16, True)
    d.text((pad, 34), head["title"], fill=INK, font=f_t)
    d.text((pad, 100), head["line"], fill=DIM, font=font(25))
    d.text((pad, 138), head["line2"], fill=DIM, font=font(22))
    x0 = W - pad
    for name, col in reversed(list(STATUS.items())):
        tw = f_s.getlength(name) + 34
        x0 -= tw + 14
        d.rounded_rectangle([x0, 44, x0 + tw, 76], radius=15, fill=col)
        d.text((x0 + 17, 49), name, fill="#0b0b0c", font=f_s)
    for i, c in enumerate(cards):
        r, k = divmod(i, cols)
        x, y = pad + k * (cw + gap), 190 + r * (ch + gap)
        d.rounded_rectangle([x, y, x + cw, y + ch], radius=14, fill=PANEL,
                            outline=STATUS.get(c.status, LINE) if c.status in ("new", "changed") else LINE,
                            width=4 if c.status in ("new", "changed") else 2)
        n = max(1, min(3, len(c.frames)))
        tw = (cw - 24 - (n - 1) * 8) // n
        for j, f in enumerate(c.frames[:3]):
            try:
                t = _cover(Image.open(out / files[c.id][j]).convert("RGB"), tw, th)
            except Exception:
                continue
            tx = x + 12 + j * (tw + 8)
            im.paste(t, (tx, y + 12))
            lab = f.level.upper()
            lw = f_x.getlength(lab) + 16
            d.rounded_rectangle([tx + 8, y + 20, tx + 8 + lw, y + 44], radius=6, fill=LEVEL.get(f.level, DIM))
            d.text((tx + 16, y + 23), lab, fill="#0b0b0c", font=f_x)
        if not c.frames:
            d.text((x + 24, y + th // 2), "no frames", fill=DIM, font=f_b)
        ty = y + th + 24
        d.text((x + 16, ty), c.id, fill=INK, font=f_h)
        st = c.status
        sw = f_s.getlength(st) + 28
        d.rounded_rectangle([x + cw - 16 - sw, ty, x + cw - 16, ty + 30], radius=14, fill=STATUS.get(st, DIM))
        d.text((x + cw - 16 - sw + 14, ty + 4), st, fill="#0b0b0c", font=f_s)
        bits = [c.kind]
        if c.seconds:
            bits.append(f"{c.seconds:g} s")
        if c.scroll:
            bits.append(f"scroll {c.scroll:.1f}")
        bits.append(f"{c.level}")
        bits.append("render " + (f"~{fmt(c.estimate)}" if c.estimate else "done" if c.rendered else "0s"))
        if c.locked:
            bits.append("locked")
        if c.approval == "approved":
            bits.append("approved")
        elif c.approval in ("no", "changed"):
            bits.append("not approved" if c.approval == "no" else "changed since approval")
        d.text((x + 16, ty + 38), " · ".join(bits), fill=DIM, font=f_s)
        yy = ty + 68
        for label, text, col, maxl in (("", c.caption, "#ffb27a", 1), ("", c.prompt, INK, 3), ("motion: ", c.motion, DIM, 2),
                                    ("", c.note if c.note.startswith("reveal") else "", "#8fd3ff", 2)):
            if not text:
                continue
            for line in wrap(label + text, f_b, cw - 32)[:maxl]:
                d.text((x + 16, yy), line, fill=col, font=f_b)
                yy += 28
            if len(wrap(label + text, f_b, cw - 32)) > maxl:
                d.text((x + cw - 40, yy - 28), "…", fill=DIM, font=f_b)
            yy += 4
    path = out / "sheet.jpg"
    im.save(path, quality=86)
    return path


def sheet_html(cards: list[Card], files: dict, out: Path, head: dict, links: dict) -> Path:
    e = lambda s: html.escape(str(s or ""))
    items = []
    for c in cards:
        frames = "".join(f'<figure><img src="{files[c.id][j]}" alt="" loading="lazy"><figcaption><b class="lv lv-{f.level}">'
                         f'{e(f.level)}</b> {e(f.label)}</figcaption></figure>' for j, f in enumerate(c.frames))
        meta = [c.kind] + ([f"{c.seconds:g} s"] if c.seconds else []) + ([f"scroll {c.scroll:.1f}"] if c.scroll else []) + \
               [c.level, ("render ~" + fmt(c.estimate)) if c.estimate else ("rendered" if c.rendered else "nothing to render")]
        if c.stages:
            meta.append("stages: " + ", ".join(c.stages))
        if c.approval:
            meta.append({"approved": "approved", "changed": "changed since approval"}.get(c.approval, "not approved"))
        rows = "".join(f"<dt>{k}</dt><dd>{e(v)}</dd>" for k, v in (("caption", c.caption), ("prompt", c.prompt),
                                                                 ("motion", c.motion), ("note", c.note)) if v)
        prev = f'<video src="{e(links.get("preview_" + c.id, ""))}" muted loop autoplay playsinline></video>' if links.get("preview_" + c.id) else ""
        items.append(f'<article class="card st-{c.status}" id="{e(c.id)}"><div class="frames n{min(3, len(c.frames))}">'
                     f'{frames}</div>{prev}<header><h2>{e(c.id)}</h2><span class="pill st-{c.status}">{e(c.status)}</span></header>'
                     f'<p class="meta">{e(" · ".join(meta))}</p><dl>{rows}</dl></article>')
    css = "".join(f".st-{k}.pill{{background:{v}}} .card.st-{k}{{--st:{v}}}" for k, v in STATUS.items()) + \
        "".join(f".lv-{k}{{background:{v}}}" for k, v in LEVEL.items())
    nav = " · ".join(f'<a href="{e(v)}">{e(k)}</a>' for k, v in links.items() if not k.startswith("preview_") and v)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{e(head['title'])}</title><style>
:root {{ color-scheme: dark; }} * {{ box-sizing: border-box; margin: 0; }}
body {{ background: {BG}; color: {INK}; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; padding: 28px clamp(16px, 3vw, 44px); }}
h1 {{ font-size: clamp(26px, 3vw, 38px); letter-spacing: -.02em; }} .sum {{ color: {DIM}; margin: 6px 0 4px; }} .sum2 {{ color: {DIM}; font-size: 14px; }}
nav {{ margin: 12px 0 26px; }} a {{ color: #ffb27a; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(min(420px, 100%), 1fr)); gap: 18px; }}
.card {{ background: {PANEL}; border: 2px solid {LINE}; border-radius: 14px; padding: 12px; }}
.card.st-new, .card.st-changed {{ border-color: var(--st); }}
.frames {{ display: grid; gap: 6px; }} .frames.n2 {{ grid-template-columns: 1fr 1fr; }} .frames.n3 {{ grid-template-columns: 1fr 1fr 1fr; }}
figure img {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 8px; display: block; background: #000; }}
figcaption {{ font-size: 12px; color: {DIM}; margin-top: 3px; }} .lv {{ color: #0b0b0c; border-radius: 4px; padding: 0 5px; font-size: 11px; text-transform: uppercase; }}
video {{ width: 100%; border-radius: 8px; margin-top: 6px; }}
header {{ display: flex; justify-content: space-between; align-items: center; margin-top: 10px; gap: 8px; }} h2 {{ font-size: 18px; }}
.pill {{ color: #0b0b0c; border-radius: 99px; padding: 1px 10px; font-size: 13px; }} .meta {{ color: {DIM}; font-size: 13px; margin: 2px 0 8px; }}
dl {{ display: grid; grid-template-columns: 64px 1fr; gap: 3px 10px; font-size: 13.5px; }} dt {{ color: {DIM}; }} dd {{ overflow-wrap: anywhere; }}
{css}
</style></head><body>
<h1>{e(head['title'])}</h1><p class="sum">{e(head['line'])}</p><p class="sum2">{e(head['line2'])}</p><nav>{nav}</nav>
<main class="grid">{''.join(items)}</main>
<p class="sum2" style="margin-top:28px">Made with DesignAI (`studio storyboard`) · {time.strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""
    path = out / "storyboard.html"
    path.write_text(page, encoding="utf-8")
    return path
