"""Record a scroll-through of a page as a README demo (GIF + MP4), using installed Chrome over CDP.

  python tools/capture_demo.py orbital.html "#film"     docs/demos/rocket
  python tools/capture_demo.py art.html     "#studio"   docs/demos/mona-lisa
  python tools/capture_demo.py bio.html     "#journey"  docs/demos/biomedical

The page is served by serve.py (http://localhost:5173). The section selector is the scroll-driven part;
the recording scrolls from its top to its bottom with an ease-in-out, then holds on the last frame.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import requests
import websocket

CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
BASE = os.environ.get("DEMO_BASE", "http://localhost:5173/")
W, H = 1440, 810
FRAMES, HOLD, FPS = 150, 18, 24      # ~6 s of scrolling plus a short hold
SETTLE = 0.22                        # seconds per frame for the page's own easing to catch up
PORT = 9333


class CDP:
    def __init__(self, ws_url):
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


def main(page, selector, out_prefix):
    frames_dir = tempfile.mkdtemp(prefix="demo_")
    prof = tempfile.mkdtemp(prefix="cdp_prof_")
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={prof}",
                             f"--window-size={W},{H}", "--hide-scrollbars", "--autoplay-policy=no-user-gesture-required",
                             "--enable-gpu", "--ignore-gpu-blocklist", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = requests.get(f"http://127.0.0.1:{PORT}/json", timeout=1).json()
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        cdp = CDP(ws_url)
        cdp.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        cdp.call("Page.enable")
        cdp.call("Page.navigate", url=BASE + page)
        for _ in range(100):   # wait for load + textures / video metadata
            if cdp.js("document.readyState") == "complete":
                break
            time.sleep(0.2)
        time.sleep(5)
        rng = cdp.js(f"""(() => {{ const s = document.querySelector('{selector}');
            const top = s.getBoundingClientRect().top + scrollY;
            return [top, top + s.offsetHeight - innerHeight]; }})()""")
        start, end = rng
        print(f"{page}: scrolling {start:.0f} -> {end:.0f}px over {FRAMES} frames")
        for i in range(FRAMES + HOLD):
            t = min(1.0, i / (FRAMES - 1))
            e = t * t * (3 - 2 * t)                      # ease in-out
            cdp.js(f"window.scrollTo(0, {start + (end - start) * e:.1f})")
            time.sleep(SETTLE)
            png = cdp.call("Page.captureScreenshot", format="png")["data"]
            with open(os.path.join(frames_dir, f"{i:04d}.png"), "wb") as f:
                f.write(base64.b64decode(png))
        cdp.ws.close()
    finally:
        proc.terminate()

    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    src = os.path.join(frames_dir, "%04d.png")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", src,
                    "-vf", "scale=1280:-2:flags=lanczos", "-c:v", "libx264", "-crf", "22", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_prefix + ".mp4"], check=True)
    # GIF: 720 px, 10 fps, per-demo palette with light dithering, kept small for the README
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", src,
                    "-vf", "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];"
                           "[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle", out_prefix + ".gif"], check=True)
    shutil.copy(os.path.join(frames_dir, f"{FRAMES // 2:04d}.png"), out_prefix + "-mid.png")
    shutil.rmtree(frames_dir, ignore_errors=True)
    shutil.rmtree(prof, ignore_errors=True)
    for ext in (".gif", ".mp4"):
        print(f"  {out_prefix}{ext}: {os.path.getsize(out_prefix + ext) / 1e6:.1f} MB")


if __name__ == "__main__":
    main(*sys.argv[1:4])
