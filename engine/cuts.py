"""cuts: film grammar between sections (`transition:` on a section, into the next).

A site's sections normally follow one another. A transition gives the join its own stretch of scroll in which both
pictures are held on screen (the section above pinned at its last screen, the one below pinned at its first) and the
scroll drives a cut between them: a hard cut with a beat of hold, a dissolve, a wipe, an iris, a whip pan, a match cut
on a shared shape, or an element carried from one to the other. The browser does all of it (runtime/src/lib/cuts.ts,
layers are the pinned sections themselves, so it works for every section type). This module is the engine's half:

  plan      which sections hand over to which, validated, and the config the page carries (`#ss-cuts`).
  find      for a match cut: the shape on the last picture of one section and the first of the next (a prompt, found by
            Florence-2 + SAM 2.1 through engine/region.py, or contours when nothing is named), saved as anchors in the
            picture's own coordinates; the page maps them to the screen exactly as the picture is fitted. Cached by the
            two pictures' content and what names the shapes (`.build/_cuts/`).
  frames    the first and last picture of any section (its poster and end frame, or a block's image).
  design    (ImageInput.match) an image generated to match another section's last frame: an edit of that frame
            (Qwen-Image-Edit) or a composition hint added to the prompt.
  strips    a frame strip around each cut from the built page (headless Chrome), to look at it.
"""
from __future__ import annotations

from typing import Callable, Optional

from .spec import CUT_TYPES, Site, Transition, is_scene  # noqa: F401  (CUT_TYPES is read as cuts.CUT_TYPES)

# screens of scroll each kind of cut takes when `length` is not set
DEFAULT_LENGTH = {"cut": 0.8, "dissolve": 1.2, "wipe": 1.3, "iris": 1.4, "whip": 1.1, "match": 1.5, "carry": 1.5}


def length_of(t: Transition) -> float:
    return float(t.length if t.length is not None else DEFAULT_LENGTH[t.type])


def cut_pairs(site: Site) -> list[tuple[int, int, Transition]]:
    """(index of the section, index of the next, its transition) for every section that hands over with a transition."""
    out = []
    for i, s in enumerate(site.sections[:-1]):
        t = getattr(s, "transition", None)
        if t is not None:
            out.append((i, i + 1, t))
    return out


def section_label(site: Site, i: int) -> str:
    s = site.sections[i]
    return getattr(s, "id", None) or f"{s.type}-{i}"


def plan(site: Site, log: Callable[[str], None] = print, anchors: Optional[dict] = None,
         blocked: Optional[str] = None) -> list[dict]:
    """The cuts the page carries, one dict per transition: `{n, a, b, type, length, ...}` where a and b are the indices
    of the two sections. Transitions that cannot work are dropped with a note (the last section has nothing to hand
    over to; the stack layout already hands over by sliding a panel over the last; a style that runs its own hand-over
    between sections says so with `blocked`)."""
    cfgs: list[dict] = []
    if site.sections and getattr(site.sections[-1], "transition", None) is not None:
        log(f"  note: [{section_label(site, len(site.sections) - 1)}] is the last section: its transition has nothing to hand over to")
    if site.layout == "stack":
        if cut_pairs(site):
            log("  note: transitions are not used with layout: stack (its panels already slide over one another); ignored")
        return []
    if blocked:
        if cut_pairs(site):
            log(f"  note: transitions are ignored: {blocked}")
        return []
    for n, (a, b, t) in enumerate(cut_pairs(site)):
        d = t.model_dump(mode="json", exclude_none=True, by_alias=True)
        d.update(n=n, a=a, b=b, length=length_of(t), label=f"{section_label(site, a)} -> {section_label(site, b)}")
        if t.type == "carry":
            d["carry"] = (t.carry.model_dump(mode="json", by_alias=True) if t.carry else {"from": "h1, h2",
                                                                                          "to": "h1, h2", "via": "dissolve"})
        if anchors and n in anchors:
            d["anchors"] = anchors[n]
        cfgs.append(d)
    return cfgs


# ---------------------------------------------------------------- frame strips

def strips(dist, out_dir, only: Optional[list[int]] = None, size=(1280, 720), frames: int = 9, pad: float = 0.2,
           mobile: bool = False, dpr: float = 1.0, wait: float = 0.45, log: Callable[[str], None] = print,
           page: str = "index.html", reduced: bool = False, clip: bool = False, clip_frames: int = 60):
    """A frame strip around each cut of a built site (headless Chrome): `frames` screenshots from `pad` screens before
    the cut's stretch of scroll to `pad` screens after it, laid out in a grid with the cut's progress under each.
    Writes <out_dir>/cut_<n>.jpg and returns the paths. The picture the visitor sees, not a mock-up. clip: also a short
    video of each cut (`cut_<n>.mp4`, `clip_frames` frames from the same stretch of scroll at 24 fps)."""
    import base64
    import subprocess
    import tempfile
    import time
    from pathlib import Path

    import requests
    from PIL import Image, ImageDraw

    from .record import CDP, _chrome, _free_port
    from .serve import serve

    W, H = size
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    port, dbg = _free_port(), _free_port()
    httpd = serve(Path(dist), port, background=True)
    prof = tempfile.mkdtemp(prefix="cuts_")
    args = [_chrome(), "--headless=new", f"--remote-debugging-port={dbg}", f"--user-data-dir={prof}", f"--window-size={W},{H}",
            "--hide-scrollbars", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader",
            "--autoplay-policy=no-user-gesture-required", "about:blank"]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    paths: list[Path] = []
    try:
        ws = None
        for _ in range(60):
            try:
                ws = next(t["webSocketDebuggerUrl"] for t in requests.get(f"http://127.0.0.1:{dbg}/json", timeout=1).json()
                          if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        cdp = CDP(ws)
        cdp.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=dpr, mobile=mobile)
        if reduced:
            cdp.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
        cdp.call("Page.enable")
        cdp.call("Page.navigate", url=f"http://127.0.0.1:{port}/{page}")
        for _ in range(80):
            if cdp.js("document.readyState") == "complete":
                break
            time.sleep(0.25)
        for _ in range(240):
            if cdp.js("(document.documentElement.dataset.ssReady === '1' || !document.getElementById('ss-loader')) && "
                      "(!document.documentElement.dataset.style || document.documentElement.dataset.ssStyle === 'ready')"):
                break
            time.sleep(0.25)
        time.sleep(1.2)
        pos = cdp.js("window.__ssCuts ? window.__ssCuts.positions() : []") or []
        if not pos:
            log("  the page has no cuts" + (" (reduced motion: sections just follow one another)" if reduced else ""))
        for p in pos:
            if only is not None and p["n"] not in only:
                continue
            y0, L = p["from"], p["length"]
            total = max(frames, clip_frames) if clip else frames
            ys_all = [y0 - pad * H + (L + 2 * pad * H) * i / (total - 1) for i in range(total)]
            keep = sorted({round(i * (total - 1) / (frames - 1)) for i in range(frames)})
            ys = [ys_all[i] for i in keep]
            all_shots = []
            for y in ys_all:
                cdp.js(f"window.scrollTo(0, {max(0.0, y):.1f})")
                time.sleep(wait)
                all_shots.append(Image.open(__import__("io").BytesIO(base64.b64decode(cdp.call("Page.captureScreenshot", format="jpeg", quality=90)["data"]))).convert("RGB"))
            shots = [all_shots[i] for i in keep]
            cols = min(frames, 5 if W >= H else 9)
            rows = (frames + cols - 1) // cols
            tw = 400 if W >= H else 190
            th = round(tw * shots[0].height / shots[0].width)
            sheet = Image.new("RGB", (cols * tw, rows * (th + 18)), (14, 14, 14))
            d = ImageDraw.Draw(sheet)
            for i, im in enumerate(shots):
                x, yy = (i % cols) * tw, (i // cols) * (th + 18)
                sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, yy + 18))
                k = (ys[i] - y0) / L if L else 0
                d.text((x + 4, yy + 3), f"{p['type']}  k={k:.2f}", fill=(235, 235, 235))
            path = out_dir / f"cut_{p['n']}.jpg"
            sheet.save(path, quality=88)
            paths.append(path)
            if clip:
                from .project import ffmpeg
                tmp = Path(tempfile.mkdtemp(prefix="cutclip_"))
                for i, im in enumerate(all_shots):
                    im.save(tmp / f"{i:04d}.jpg", quality=92)
                mp4 = out_dir / f"cut_{p['n']}.mp4"
                ffmpeg("-framerate", "24", "-i", str(tmp / "%04d.jpg"), "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-crf", "20",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4)
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)
                paths.append(mp4)
            log(f"  [{p['label']}] {p['type']} -> {path.name}")
        cdp.ws.close()
    finally:
        proc.terminate()
        httpd.shutdown()
    return paths


def find_anchors(project, site: Site, entries: list[dict], dist=None, log: Callable[[str], None] = print) -> dict:
    """Where the shapes of every match cut sit (engine/cuts_shapes.py); {} when there are none."""
    pairs = cut_pairs(site)
    if site.layout == "stack" or not any(t.type == "match" for _, _, t in pairs):
        return {}
    from .cuts_shapes import analyse
    labels = [f"{section_label(site, a)} -> {section_label(site, b)}" for a, b, _ in pairs]
    return analyse(project, pairs, labels, entries, dist, log)


def read_cuts(dist) -> list[dict]:
    """The cuts a built page carries (its `#ss-cuts` block): n, label, type, length, anchors."""
    import json
    import re
    from pathlib import Path
    f = Path(dist) / "index.html"
    if not f.exists():
        return []
    m = re.search(r'<script type="application/json" id="ss-cuts">(.*?)</script>', f.read_text(encoding="utf-8"), re.S)
    if not m:
        return []
    import html
    return json.loads(html.unescape(m.group(1)))
