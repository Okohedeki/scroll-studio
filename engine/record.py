"""Record a scroll-through of a built site to MP4 (and optionally GIF) with headless Chrome over CDP.

Frames are captured one scroll position at a time (with time for the page's own easing to settle), so the
recording is smooth regardless of machine speed. Used by `studio record` and the UI's export panel.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from .config import settings
from .project import BuildError, ffmpeg
from .serve import serve


def _chrome() -> str:
    if settings()["chrome"]:
        return settings()["chrome"]
    cands = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] + [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser")]
    for c in cands:
        if c and os.path.exists(c):
            return c
    try:   # Playwright's bundled Chromium
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return p.chromium.executable_path
    except Exception:
        raise BuildError("Chrome not found. Install Chrome or run `playwright install chromium`, or set CHROME.")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CDP:
    def __init__(self, ws_url):
        import websocket
        self.ws = websocket.create_connection(ws_url, max_size=None, suppress_origin=True)
        self.i = 0

    def call(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.i:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")


# A slow tour of the frame for `--pointer wander`: through the middle, out to either side and back, in 0-1 of the viewport
WANDER = [(0.5, 0.55), (0.34, 0.5), (0.42, 0.36), (0.62, 0.42), (0.7, 0.6), (0.52, 0.66), (0.4, 0.56), (0.5, 0.48)]


def parse_pointer(text: Optional[str]) -> Optional[list[tuple[float, float]]]:
    """`--pointer` as written: None (no pointer), "wander" (WANDER), or waypoints "x,y x,y ..." in 0-1 of the viewport."""
    if not text:
        return None
    if text.strip() == "wander":
        return list(WANDER)
    pts = []
    for tok in text.replace(";", " ").split():
        try:
            x, y = (float(v) for v in tok.split(","))
        except ValueError:
            raise BuildError(f"--pointer: '{tok}' is not x,y (two numbers in 0-1 of the viewport, e.g. 0.3,0.5)")
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise BuildError(f"--pointer: {tok} is outside the viewport (x and y are 0-1)")
        pts.append((x, y))
    if not pts:
        raise BuildError("--pointer: give 'wander' or waypoints such as '0.3,0.5 0.7,0.4'")
    return pts


def pointer_path(points: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    """The pointer at each of `n` frames: a smooth curve through the waypoints (Catmull-Rom, the ends held), reaching
    the first at frame 0 and the last at frame n - 1, at an even pace between waypoints."""
    if n <= 0:
        return []
    if len(points) == 1:
        return [tuple(points[0])] * n
    p = [points[0], *points, points[-1]]
    segs = len(points) - 1
    out = []
    for i in range(n):
        u = segs * i / max(n - 1, 1)
        k = min(int(u), segs - 1)
        t = u - k
        p0, p1, p2, p3 = p[k], p[k + 1], p[k + 2], p[k + 3]
        t2, t3 = t * t, t * t * t
        xy = tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                          + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2))
        out.append((min(1.0, max(0.0, xy[0])), min(1.0, max(0.0, xy[1]))))
    return out


def draw_cursor(jpg: bytes, xy: tuple[float, float], scale: float = 1.0) -> bytes:
    """A small soft ring where the pointer is (headless screenshots have no cursor), so a recording shows what the
    pointer is doing. `xy` in pixels of the captured frame; `scale` is the device pixel ratio."""
    import io
    from PIL import Image, ImageDraw
    im = Image.open(io.BytesIO(jpg)).convert("RGB")
    x, y = xy
    r = 9 * scale
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse((x - r - 1.5 * scale, y - r - 1.5 * scale, x + r + 1.5 * scale, y + r + 1.5 * scale),
              outline=(0, 0, 0, 90), width=max(1, round(3 * scale)))
    d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 235), width=max(1, round(2 * scale)))
    d.ellipse((x - 1.5 * scale, y - 1.5 * scale, x + 1.5 * scale, y + 1.5 * scale), fill=(255, 255, 255, 235))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=94)
    return buf.getvalue()


def record(dist: Path, out: Path, section: Optional[str] = None, size=(1920, 1080), seconds: float = 12.0,
           fps: int = 24, settle: float = 0.2, gif: bool = False, out_width: Optional[int] = None, poster_at: float = 0.5,
           log: Callable[[str], None] = print, progress: Callable[[float, str], None] = lambda f, m="": None,
           dpr: float = 1.0, mobile: bool = False, span: tuple[float, float] = (0.0, 1.0),
           pointer: Optional[list[tuple[float, float]]] = None, cursor: bool = True) -> Path:
    """size is the CSS viewport; dpr scales the captured pixels (a phone: size=(540, 960), dpr=2, mobile=True).
    span records only that part (0-1) of the section's (or page's) scroll. `pointer`: waypoints (0-1 of the viewport)
    the mouse moves through over the recording, for pages whose pictures follow it (a `pointer:` lens or light); with
    `cursor` a small ring marks it in the frames."""
    import requests
    W, H = size
    port, dbg = _free_port(), _free_port()
    httpd = serve(dist, port, background=True)
    frames_dir, prof = Path(tempfile.mkdtemp(prefix="rec_")), tempfile.mkdtemp(prefix="cdp_")
    proc = subprocess.Popen([_chrome(), "--headless=new", f"--remote-debugging-port={dbg}", f"--user-data-dir={prof}",
                             f"--window-size={W},{H}", "--hide-scrollbars", "--autoplay-policy=no-user-gesture-required",
                             "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n = int(seconds * fps)
    hold = int(fps * 0.75)
    try:
        ws_url = None
        for _ in range(60):
            try:
                tabs = requests.get(f"http://127.0.0.1:{dbg}/json", timeout=1).json()
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        if not ws_url:
            raise BuildError("could not connect to headless Chrome")
        cdp = CDP(ws_url)
        cdp.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=dpr, mobile=mobile)
        cdp.call("Page.enable")
        cdp.call("Page.navigate", url=f"http://127.0.0.1:{port}/index.html")
        for _ in range(120):
            if cdp.js("document.readyState") == "complete":
                break
            time.sleep(0.25)
        for _ in range(240):   # the loading screen holds scrolling until every scene's media is in
            if cdp.js("(document.documentElement.dataset.ssReady === '1' || !document.getElementById('ss-loader')) && (!document.documentElement.dataset.style || document.documentElement.dataset.ssStyle === 'ready')"):
                break
            time.sleep(0.25)
        time.sleep(1.5)
        sel = json.dumps(f"#{section}") if section else "null"
        start, end = cdp.js(f"""(() => {{ const s = {sel} ? document.querySelector({sel}) : null;
            if (!s) return [0, document.documentElement.scrollHeight - innerHeight];
            const top = s.getBoundingClientRect().top + scrollY;
            return [top, top + s.offsetHeight - innerHeight]; }})()""")
        start, end = start + (end - start) * span[0], start + (end - start) * span[1]
        log(f"recording {section or 'page'}: {start:.0f} -> {end:.0f}px, {n} frames at {W}x{H}"
            + (f", the pointer through {len(pointer)} point(s)" if pointer else ""))
        path = pointer_path(pointer, n + hold) if pointer else []
        for i in range(n + hold):
            t = min(1.0, i / max(n - 1, 1))
            e = t * t * (3 - 2 * t)
            if path:      # a real mouse move, so the page's pointermove listeners follow it
                px, py = path[i][0] * W, path[i][1] * H
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=px, y=py, button="none")
            cdp.js(f"window.scrollTo(0, {start + (end - start) * e:.1f})")
            time.sleep(settle)
            # JPEG at high quality is several times faster to capture than PNG and indistinguishable after H.264
            jpg = base64.b64decode(cdp.call("Page.captureScreenshot", format="jpeg", quality=94)["data"])
            if path and cursor:
                jpg = draw_cursor(jpg, (px * dpr, py * dpr), dpr)
            (frames_dir / f"{i:05d}.jpg").write_bytes(jpg)
            progress(i / (n + hold), f"frame {i + 1}/{n + hold}")
        cdp.ws.close()
    finally:
        proc.terminate()
        httpd.shutdown()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    src = str(frames_dir / "%05d.jpg")
    ow = out_width or round(W * dpr)
    ffmpeg("-framerate", str(fps), "-i", src, "-vf", f"scale={ow}:-2:flags=lanczos", "-c:v", "libx264",
           "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out.with_suffix(".mp4"))
    if gif:
        ffmpeg("-framerate", str(fps), "-i", src, "-vf", "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:"
               "stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle", out.with_suffix(".gif"))
    # poster: one frame of the recording, at the recording's own width
    pf = frames_dir / f"{min(n - 1, max(0, int(poster_at * (n - 1)))):05d}.jpg"
    ffmpeg("-i", pf, "-vf", f"scale={ow}:-2:flags=lanczos", "-q:v", "3", out.with_suffix(".jpg"))
    shutil.rmtree(frames_dir, ignore_errors=True)
    shutil.rmtree(prof, ignore_errors=True)
    log(f"-> {out.with_suffix('.mp4')}")
    return out.with_suffix(".mp4")
