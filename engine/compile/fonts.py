"""Self-hosted fonts: download a theme's Google Fonts once and serve them from the site itself.

Built sites make no third-party requests for type. Files are cached per URL under
~/.scroll-studio/cache/fonts, so only the first build of a theme needs the network. Without network and
without a cache, the site falls back to linking Google Fonts directly (and the build says so).
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

CACHE = Path.home() / ".scroll-studio" / "cache" / "fonts"
# Google serves woff2 with unicode-range subsets to modern browsers; this UA asks for exactly that.
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36"}
URL_RE = re.compile(r"url\((https://fonts\.gstatic\.com/[^)]+)\)")


def _key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _fetch(url: str, binary: bool):
    import requests
    path = CACHE / (_key(url) + (".woff2" if binary else ".css"))
    if path.exists():
        return path.read_bytes() if binary else path.read_text(encoding="utf-8")
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    CACHE.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(r.content)
        return r.content
    path.write_text(r.text, encoding="utf-8")
    return r.text


def vendor(links: list[str], dist: Path, log: Callable[[str], None] = print) -> Optional[str]:
    """Write dist/fonts/ (woff2 files + fonts.css) for these Google Fonts css2 links.

    Returns the stylesheet's site-relative path, or None if the fonts could not be fetched (callers then
    link Google Fonts directly).
    """
    out = dist / "fonts"
    try:
        css = "\n".join(_fetch(u, binary=False) for u in links)
        files = {}
        for url in sorted(set(URL_RE.findall(css))):
            name = _key(url) + ".woff2"
            _fetch(url, binary=True)
            files[url] = name
    except Exception as e:  # offline and not cached yet
        log(f"  note: fonts not self-hosted ({e.__class__.__name__}); linking Google Fonts instead")
        return None
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for url, name in files.items():
        shutil.copy(CACHE / name, out / name)
    css = URL_RE.sub(lambda m: f"url({files[m.group(1)]})", css)
    (out / "fonts.css").write_text(css, encoding="utf-8")
    return "fonts/fonts.css"
