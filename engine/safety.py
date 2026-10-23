"""Text from a site.yaml is untrusted: it may come from a shared project or template. These helpers keep it from turning
into script on the built page (raw HTML, `javascript:` links, markup that escapes a CSS block or an attribute).

The built page is static and public, so the rule is simple: spec text is shown as text. The few inline tags copy fields
document (`<em>`, `<b>`, `<i>`, `<br>`, `<strong>`, `<code>`) are the only markup that survives, and only without attributes.
"""
from __future__ import annotations

import html
import re

from markupsafe import Markup

SAFE_SCHEMES = frozenset({"http", "https", "mailto", "tel"})
_SCHEME = re.compile(r"^([a-z][a-z0-9+.\-]*):", re.I)
# Browsers ignore tabs, newlines and other control characters inside a URL, so `java\tscript:` is still `javascript:`.
_INVISIBLE = re.compile(r"[\x00-\x20\x7f-\x9f­​-‏  ⁠﻿]")
_DATA_IMAGE = re.compile(r"data:image/(?:png|jpe?g|gif|webp|avif|svg\+xml)[;,]", re.I)

_INLINE = re.compile(r"&lt;(/?)(em|b|i|br|strong|code)\s*/?&gt;")
SAFE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}")


def url_scheme(url: str) -> str | None:
    """The scheme a browser would see in `url` after decoding entities and dropping invisible characters, or None for a
    relative URL, a #anchor or a path."""
    seen = _INVISIBLE.sub("", html.unescape(str(url)))
    m = _SCHEME.match(seen)
    return m.group(1).lower() if m else None


def is_safe_url(url: str, data_images: bool = False) -> bool:
    """http(s), mailto, tel, relative paths and #anchors. `data_images` also allows data:image/... (an inline picture)."""
    scheme = url_scheme(url)
    if scheme is None or scheme in SAFE_SCHEMES:
        return True
    return data_images and bool(_DATA_IMAGE.match(_INVISIBLE.sub("", html.unescape(str(url)))))


def check_url(url: str, what: str) -> str:
    """Return `url`, or raise ValueError saying which links are allowed."""
    if not is_safe_url(url):
        raise ValueError(f"{what} {url[:60]!r} is not an allowed link: use http(s), mailto:, tel:, a relative path or a #anchor")
    return url


def rich(text) -> Markup:
    """Copy text as HTML: everything escaped except bare <em>, <b>, <i>, <br>, <strong> and <code> tags."""
    if text is None:
        return Markup("")
    esc = str(Markup.escape(text))
    return Markup(_INLINE.sub(lambda m: f"<{m.group(1)}{m.group(2)}>", esc))


def angle_escaped(text: str, keep_em: bool = False) -> str:
    """`text` with < and > made harmless for a runtime that sets it with innerHTML (kinetic type, map labels). `&` is
    left alone, so an entity the author wrote still reads as written and a bare ampersand stays one."""
    t = str(text).replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"&lt;(/?)em&gt;", lambda m: f"<{m.group(1)}em>", t) if keep_em else t


_ATTR = re.compile(r"""(?P<name>\b(?:href|src|poster|action|formaction|xlink:href|data|background|ping|cite)\s*=\s*)(?P<q>["'])(?P<val>.*?)(?P=q)""",
                   re.I | re.S)
_TAG = re.compile(r"<[a-zA-Z][^<>]*>")


def clean_page_urls(page: str, log=lambda m: None) -> str:
    """Replace any link in the finished page that a browser would run as code (`javascript:`, `vbscript:`, `data:` documents,
    entity- or whitespace-obfuscated forms of them) with `#`. Pictures may stay data:image. Works on the final markup, so it
    covers every template, style and Markdown page the same way."""
    def tag(m: re.Match) -> str:
        t = m.group(0)

        def attr(a: re.Match) -> str:
            val = a.group("val")
            pictures = a.group("name").strip().lower().startswith(("src", "poster", "background")) or t[:5].lower() == "<link"
            if is_safe_url(val, data_images=pictures):
                return a.group(0)
            log(f"  note: a link to {val[:40]!r} is not allowed on the page; replaced with #")
            return f'{a.group("name")}{a.group("q")}#{a.group("q")}'
        return _ATTR.sub(attr, t)
    return _TAG.sub(tag, page)


CSS_VALUE = re.compile(r"[#\w\s(),.%/+*\-]{1,120}")      # colours, lengths, calc(); never quotes, ; { } < > \ or comments
FONT_NAME = re.compile(r"[\w .+&'\-]{1,80}")
CSS_NAME = re.compile(r"[a-z][a-z0-9\-]{0,30}")


def css_value_ok(value: str) -> bool:
    v = str(value)
    return bool(CSS_VALUE.fullmatch(v)) and not re.search(r"url\s*\(|expression\s*\(|javascript|@import|/\*|\*/", v, re.I)
