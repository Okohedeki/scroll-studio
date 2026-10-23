"""Check a built page's cinemagraphs in a real browser: is everything but the moving part truly still, does the part that moves
move, does the loop hitch at its seam, and does the page stay a still when it should (reduced motion).

Headless Chrome with the GPU on (`--headless=new` uses the real GPU, so the video decodes and the CSS mask composites as on a
visitor's machine). For each `data-cine` element the page is scrolled to it and settled, then screenshots of its box are taken
over the loop; the mask the page composites through is placed where the video sits (read from the page), and

  held     the largest change from the first screenshot of any pixel where the mask is zero (must be 0: the still's own
           pixels), and how many pixels changed at all
  moving   how much the pixels under the mask change over time (temporal standard deviation)
  hitch    video frame callbacks across the loop's wrap: the longest gap between two presented frames, against the usual one

and the same page with `prefers-reduced-motion: reduce`: no video is loaded, and the box is the still.
"""
from __future__ import annotations

import base64
import io
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

import numpy as np

from .project import BuildError
from .record import CDP, _chrome, _free_port
from .serve import serve


def _open(dist: Path, size, mobile: bool, dpr: float, reduced: bool, log):
    import requests
    port, dbg = _free_port(), _free_port()
    httpd = serve(dist, port, background=True)
    prof = tempfile.mkdtemp(prefix="cinechk_")
    proc = subprocess.Popen([_chrome(), "--headless=new", f"--remote-debugging-port={dbg}", f"--user-data-dir={prof}",
                             f"--window-size={size[0]},{size[1]}", "--hide-scrollbars", "--autoplay-policy=no-user-gesture-required",
                             "--enable-gpu", "--ignore-gpu-blocklist", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(60):
        try:
            ws = next(t["webSocketDebuggerUrl"] for t in requests.get(f"http://127.0.0.1:{dbg}/json", timeout=1).json() if t["type"] == "page")
            break
        except Exception:
            time.sleep(0.25)
    if not ws:
        raise BuildError("could not connect to headless Chrome")
    cdp = CDP(ws)
    cdp.call("Emulation.setDeviceMetricsOverride", width=size[0], height=size[1], deviceScaleFactor=dpr, mobile=mobile)
    if reduced:
        cdp.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
    cdp.call("Page.enable")
    cdp.call("Page.navigate", url=f"http://127.0.0.1:{port}/index.html")
    for _ in range(120):
        if cdp.js("document.readyState") == "complete":
            break
        time.sleep(0.25)
    for _ in range(240):
        if cdp.js("(document.documentElement.dataset.ssReady === '1' || !document.getElementById('ss-loader')) && (!document.documentElement.dataset.style || document.documentElement.dataset.ssStyle === 'ready')"):
            break
        time.sleep(0.25)

    def close():
        try:
            cdp.ws.close()
        finally:
            proc.terminate()
            httpd.shutdown()
            shutil.rmtree(prof, ignore_errors=True)
    return cdp, close


def _shot(cdp, rect: dict) -> np.ndarray:
    from PIL import Image
    # the clip is in page coordinates; `rect` is in the viewport's
    sx, sy = cdp.js("[scrollX, scrollY]")
    clip = {"x": rect["x"] + sx, "y": rect["y"] + sy, "width": rect["w"], "height": rect["h"], "scale": 1}
    b = base64.b64decode(cdp.call("Page.captureScreenshot", format="png", clip=clip, captureBeyondViewport=False)["data"])
    return np.asarray(Image.open(io.BytesIO(b)).convert("RGB"))


PROBE = """(i) => { const it = window.__ssCine && window.__ssCine[i]; if (!it) return null;
  const h = it.host.getBoundingClientRect(); const v = it.video && it.video.getBoundingClientRect();
  return { host: [h.left, h.top, h.width, h.height], video: v ? [v.left, v.top, v.width, v.height] : null,
           state: it.state, mask: it.e.m, src: it.e.v, hasVideo: !!it.video, paused: it.video ? it.video.paused : null,
           t: it.video ? it.video.currentTime : null, dur: it.video ? it.video.duration : null,
           opacity: it.video ? getComputedStyle(it.video).opacity : null }; }"""

HITCH = """(i, seconds) => new Promise((res) => { const it = window.__ssCine[i]; const v = it.video; const log = [];
  if (!v || !('requestVideoFrameCallback' in v)) return res(null);
  const end = performance.now() + seconds * 1000; let last = null;
  const cb = (now, md) => { log.push([now, md.mediaTime, md.presentedFrames]); if (performance.now() < end) v.requestVideoFrameCallback(cb); else res(log); };
  v.requestVideoFrameCallback(cb); }) """


def _mask_in(rect_video: list, rect_clip: dict, mask_path: Path) -> np.ndarray:
    """The page's mask as an array over the clip's pixels: the mask resized to where the video sits, zero elsewhere."""
    from PIL import Image
    a = np.asarray(Image.open(mask_path).convert("RGBA"))[..., 3]
    vx, vy, vw, vh = rect_video
    x0, y0 = int(round(vx - rect_clip["x"])), int(round(vy - rect_clip["y"]))
    w, h = int(round(vw)), int(round(vh))
    m = np.asarray(Image.fromarray(a).resize((max(w, 1), max(h, 1)), Image.BILINEAR))
    out = np.zeros((rect_clip["h"], rect_clip["w"]), np.uint8)
    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(rect_clip["w"], x0 + w), min(rect_clip["h"], y0 + h)
    if xb > xa and yb > ya:
        out[ya:yb, xa:xb] = m[ya - y0:yb - y0, xa - x0:xb - x0]
    return out


def check_page(dist: Path, work: Path, size=(1440, 900), mobile: bool = False, dpr: float = 1.0, shots: int = 20,
               log: Callable[[str], None] = print) -> dict:
    """Measure every cinemagraph on the built page (dist/index.html). Writes per-cinemagraph sheets into `work`."""
    from PIL import Image
    work.mkdir(parents=True, exist_ok=True)
    out: dict = {"viewport": list(size), "mobile": mobile, "items": []}
    cdp, close = _open(dist, size, mobile, dpr, False, log)
    try:
        n = cdp.js("(window.__ssCine || []).length") or 0
        if not n:
            raise BuildError("the page has no running cinemagraphs (window.__ssCine is empty): is the runtime built, and are there any?")
        for i in range(n):
            cdp.js(f"(() => {{ const it = window.__ssCine[{i}]; it.host.scrollIntoView({{block: 'center'}}); }})()")
            probe = None
            for _ in range(80):                         # the video loads when it is near and plays when in view
                time.sleep(0.25)
                probe = cdp.js(f"({PROBE})({i})")
                if probe and probe["hasVideo"] and probe["state"] == "playing" and (probe["t"] or 0) > 0.2 and float(probe["opacity"]) > 0.99:
                    break
            if not probe or probe["state"] != "playing":
                out["items"].append({"index": i, "playing": False, "state": probe and probe["state"]})
                log(f"  cinemagraph {i}: did not start playing ({probe and probe['state']})")
                continue
            time.sleep(0.5)
            probe = cdp.js(f"({PROBE})({i})")
            hx, hy, hw, hh = probe["host"]
            vx, vy, vw, vh = probe["video"]
            # the clip: the host's visible box, but at least the video's box, inside the viewport
            x0, y0 = max(0, int(min(hx, vx))), max(0, int(min(hy, vy)))
            x1, y1 = min(size[0], int(max(hx + hw, vx + vw)) + 1), min(size[1], int(max(hy + hh, vy + vh)) + 1)
            rect = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
            mask = _mask_in(probe["video"], rect, dist / probe["mask"])
            dur = float(probe["dur"])
            # screenshots over a loop and a half, then a frame callback log over two loops
            frames, t0 = [], time.time()
            for k in range(shots):
                frames.append(_shot(cdp, rect))
                time.sleep(max(0.0, (k + 1) * dur * 1.5 / shots - (time.time() - t0)))
            fr = np.stack(frames).astype(np.int16)
            import cv2
            z = mask == 0
            d_out = np.abs(fr[:, z] - fr[0:1, z])
            changed = float((d_out.max(axis=(0, 2)) > 0).mean()) if z.any() else 0.0
            # pixels within 3 px of the mask's edge are resampled differently by the browser than by this check: report them apart
            deep = cv2.dilate((mask > 0).astype(np.uint8), np.ones((7, 7), np.uint8)) == 0
            d_deep = np.abs(fr[:, deep] - fr[0:1, deep])
            live = mask > 200
            std_in = float(np.std(fr[:, live].astype(np.float32), axis=0).mean()) if live.any() else 0.0
            log_ = cdp.js(f"({HITCH})({i}, {dur * 2.2:.2f})")
            hitch = None
            if log_ and len(log_) > 8:
                a = np.array(log_, dtype=np.float64)
                dt = np.diff(a[:, 0])
                wr = np.where(np.diff(a[:, 1]) < -0.2 * dur)[0]
                others = np.delete(dt, wr) if len(wr) else dt
                at_wrap = [float(dt[w]) for w in wr if w < len(dt)]
                # a 24 fps video on a 60 Hz display presents frames 33 and 50 (sometimes 67) ms apart; the wrap is a hitch only if
                # it takes longer than the longest gap anywhere else
                hitch = {"usual_ms": round(float(np.median(dt)), 1), "worst_elsewhere_ms": round(float(others.max()), 1),
                         "wraps": int(len(wr)), "wrap_gap_ms": round(max(at_wrap), 1) if at_wrap else None,
                         "hitch": bool(at_wrap and max(at_wrap) > float(others.max()) + 20)}
            sheet = work / f"page_{i}.png"
            tiles = [fr[j].astype(np.uint8) for j in np.linspace(0, len(fr) - 1, 6).astype(int)]
            Image.fromarray(np.concatenate([np.concatenate(tiles[:3], axis=1), np.concatenate(tiles[3:], axis=1)], axis=0)).save(sheet)
            res = {"index": i, "playing": True, "box": rect, "mask_zero_share": round(float(z.mean()), 3),
                   "held": {"max_change_outside_mask": int(d_out.max()) if z.any() else 0, "share_of_pixels_changed": round(changed, 5),
                            "max_change_beyond_3px_of_the_mask": int(d_deep.max()) if deep.any() else 0},
                   "moving": {"temporal_std_under_mask": round(std_in, 2)}, "loop_hitch": hitch, "sheet": str(sheet)}
            out["items"].append(res)
            log(f"  cinemagraph {i}: outside the mask max change {res['held']['max_change_outside_mask']} "
                f"({changed:.4%} of pixels), {res['held']['max_change_beyond_3px_of_the_mask']} beyond 3 px of it; under it std {std_in:.1f}; "
                f"loop wrap gap {hitch and hitch['wrap_gap_ms']} ms (longest elsewhere {hitch and hitch['worst_elsewhere_ms']} ms)")
    finally:
        close()
    return out


def check_reduced(dist: Path, size=(1440, 900), log: Callable[[str], None] = print) -> dict:
    """The same page with prefers-reduced-motion: nothing is loaded, nothing plays, the box is the still."""
    cdp, close = _open(dist, size, False, 1.0, True, log)
    try:
        time.sleep(2.0)
        n = cdp.js("document.querySelectorAll('[data-cine]').length")
        started = cdp.js("(window.__ssCine || []).length")
        videos = cdp.js("document.querySelectorAll('.ss-cine video').length")
        res = {"cinemagraph_elements": n, "started": started, "videos_loaded": videos, "still_only": started == 0 and videos == 0}
        log(f"  reduced motion: {n} cinemagraph(s) on the page, {videos} video(s) loaded -> {'the still' if res['still_only'] else 'PLAYS'}")
        return res
    finally:
        close()
