"""Self-hosted fonts: download a theme's Google Fonts once and serve them from the site itself, beside any font
files of the project's own (`fonts: {display: {file: fonts/Brand.woff2}}`).

Built sites make no third-party requests for type. Files are cached per URL under
~/.scroll-studio/cache/fonts, so only the first build of a theme needs the network. Without network and
without a cache, the site falls back to linking Google Fonts directly (and the build says so).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
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
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")        # written whole, then moved: a build running beside this one never reads half a file
    tmp.write_bytes(r.content if binary else r.text.encode("utf-8"))
    os.replace(tmp, path)
    return r.content if binary else r.text


def vendor(links: list[str], dist: Path, log: Callable[[str], None] = print) -> Optional[str]:
    """Write dist/fonts/ (woff2 files + fonts.css) for these Google Fonts css2 links.

    Returns the stylesheet's site-relative path, or None if the fonts could not be fetched (callers then
    link Google Fonts directly).
    """
    out = dist / "fonts"
    try:
        css = "\n".join(_fetch(u, binary=False) for u in links)
        urls = sorted(set(URL_RE.findall(css)))
        with ThreadPoolExecutor(16) as pool:        # a CJK face is a hundred unicode-range files: fetched side by side
            list(pool.map(lambda u: _fetch(u, binary=True), urls))
        files = {url: _key(url) + ".woff2" for url in urls}
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


FORMATS = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}


def own(project, faces: list[dict], dist: Path, append: bool) -> str:
    """Copy the project's own font files into dist/fonts/ and declare them in fonts.css (after the Google faces when
    `append`, else on their own). Returns the stylesheet's site-relative path."""
    from ..project import BuildError
    out = dist / "fonts"
    out.mkdir(parents=True, exist_ok=True)
    rules = []
    for f in faces:
        src = project.path(f["file"])
        if not src.is_file():
            raise BuildError(f"theme font {f['file']} not found in the project folder")
        data = src.read_bytes()
        name = hashlib.sha1(data).hexdigest()[:16] + src.suffix.lower()     # a plain name: nothing from the spec in the CSS
        (out / name).write_bytes(data)
        rules.append(f'@font-face {{ font-family: "{f["family"]}"; src: url({name}) format("{FORMATS[src.suffix.lower()]}"); '
                     f'font-weight: {f["weight"]}; font-style: {f["style"]}; font-display: swap; }}')
    css = out / "fonts.css"
    before = css.read_text(encoding="utf-8") + "\n" if append and css.exists() else ""
    css.write_text(before + "\n".join(rules) + "\n", encoding="utf-8")
    return "fonts/fonts.css"
