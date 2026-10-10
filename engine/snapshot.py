"""Screenshots of a built site at chosen scene progress values, plus a contact sheet. Used by `studio snapshot`,
the UI's review panel, and CI to eyeball every example after a change.

  studio snapshot lodestar-orbital --at launch:0.1 launch:0.5 launch:0.9 --at top --at bottom
"""
from __future__ import annotations

import base64
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

from PIL import Image

from .record import CDP, _chrome, _free_port
from .serve import serve


def snapshot(dist: Path, shots: list[str], out_dir: Path, size=(1600, 900), wait: float = 2.0,
             log: Callable[[str], None] = print, page: str = "index.html") -> list[Path]:
    """shots: 'scene:progress' (e.g. 'hero:0.4'), 'top', 'bottom', or 'y:<pixels>'. page: which page under dist."""
    import requests
    W, H = size
    port, dbg = _free_port(), _free_port()
    httpd = serve(dist, port, background=True)
    prof = tempfile.mkdtemp(prefix="snap_")
    proc = subprocess.Popen([_chrome(), "--headless=new", f"--remote-debugging-port={dbg}", f"--user-data-dir={prof}",
                             f"--window-size={W},{H}", "--hide-scrollbars", "--enable-gpu", "--ignore-gpu-blocklist",
                             "--enable-unsafe-swiftshader", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):   # a fresh set each time, so the sheet never mixes runs
        old.unlink()
    paths = []
    try:
        ws = None
        for _ in range(60):
            try:
                ws = next(t["webSocketDebuggerUrl"] for t in requests.get(f"http://127.0.0.1:{dbg}/json", timeout=1).json() if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        cdp = CDP(ws)
        cdp.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        cdp.call("Page.enable")
        for i, shot in enumerate(shots):
            base = f"http://127.0.0.1:{port}/{page}"
            if ":" in shot and not shot.startswith("y:"):
                sid, p = shot.split(":", 1)
                url = f"{base}?p={float(p)}&s={sid}"
            else:
                url = base
            cdp.call("Page.navigate", url=url)
            for _ in range(80):
                if cdp.js("document.readyState") == "complete":
                    break
                time.sleep(0.25)
            for _ in range(240):   # the loading screen holds scrolling until every scene's media is in
                if cdp.js("(document.documentElement.dataset.ssReady === '1' || !document.getElementById('ss-loader')) && (!document.documentElement.dataset.style || document.documentElement.dataset.ssStyle === 'ready')"):
                    break
                time.sleep(0.25)
            if shot == "bottom":
                cdp.js("scrollTo(0, document.documentElement.scrollHeight)")
            elif shot.startswith("y:"):
                cdp.js(f"scrollTo(0, {float(shot[2:])})")
            time.sleep(wait)
            png = base64.b64decode(cdp.call("Page.captureScreenshot", format="png")["data"])
            path = out_dir / f"{i:02d}_{shot.replace(':', '_')}.png"
            path.write_bytes(png)
            paths.append(path)
            log(f"  {shot} -> {path.name}")
        cdp.ws.close()
    finally:
        proc.terminate()
        httpd.shutdown()
    # contact sheet
    cols = min(3, len(paths))
    tw = 640
    th = round(tw * H / W)
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), "black")
    for i, p in enumerate(paths):
        sheet.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
    sheet.save(out_dir / "sheet.jpg", quality=88)
    return paths
