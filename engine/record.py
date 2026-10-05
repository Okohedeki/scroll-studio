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
import sys
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


def record(dist: Path, out: Path, section: Optional[str] = None, size=(1920, 1080), seconds: float = 12.0,
           fps: int = 24, settle: float = 0.2, gif: bool = False, out_width: Optional[int] = None,
           log: Callable[[str], None] = print, progress: Callable[[float, str], None] = lambda f, m="": None) -> Path:
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
        cdp.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        cdp.call("Page.enable")
        cdp.call("Page.navigate", url=f"http://127.0.0.1:{port}/index.html")
        for _ in range(120):
            if cdp.js("document.readyState") == "complete":
                break
            time.sleep(0.25)
        time.sleep(4)
        sel = json.dumps(f"#{section}") if section else "null"
        start, end = cdp.js(f"""(() => {{ const s = {sel} ? document.querySelector({sel}) : null;
            if (!s) return [0, document.documentElement.scrollHeight - innerHeight];
            const top = s.getBoundingClientRect().top + scrollY;
            return [top, top + s.offsetHeight - innerHeight]; }})()""")
        log(f"recording {section or 'page'}: {start:.0f} -> {end:.0f}px, {n} frames at {W}x{H}")
        for i in range(n + hold):
            t = min(1.0, i / max(n - 1, 1))
            e = t * t * (3 - 2 * t)
            cdp.js(f"window.scrollTo(0, {start + (end - start) * e:.1f})")
            time.sleep(settle)
            png = cdp.call("Page.captureScreenshot", format="png")["data"]
            (frames_dir / f"{i:05d}.png").write_bytes(base64.b64decode(png))
            progress(i / (n + hold), f"frame {i + 1}/{n + hold}")
        cdp.ws.close()
    finally:
        proc.terminate()
        httpd.shutdown()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    src = str(frames_dir / "%05d.png")
    ow = out_width or W
    ffmpeg("-framerate", str(fps), "-i", src, "-vf", f"scale={ow}:-2:flags=lanczos", "-c:v", "libx264",
           "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out.with_suffix(".mp4"))
    if gif:
        ffmpeg("-framerate", str(fps), "-i", src, "-vf", "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:"
               "stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle", out.with_suffix(".gif"))
    shutil.copy(frames_dir / f"{n // 2:05d}.png", out.with_name(out.stem + "-mid.png"))
    shutil.rmtree(frames_dir, ignore_errors=True)
    shutil.rmtree(prof, ignore_errors=True)
    log(f"-> {out.with_suffix('.mp4')}")
    return out.with_suffix(".mp4")
