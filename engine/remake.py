"""`studio remake <url>`: a live landing page read and told again as a scroll site, in a new project.

  studio remake https://example.com/ [--name my-remake] [--style bauhaus] [--no-gpu]

Reading (read_page). robots.txt is asked first, for the page and for every host a picture comes from, under the plain
user agent below; a page it disallows is refused. The page is opened in headless Chromium (Playwright), scrolled once
so lazy content loads, and every element is marked with what the browser knows (hidden, fixed banners, an image's real
size, a CSS background picture). Without Playwright's Chromium the page is read with a plain request instead. Only
the page, its stylesheets and its pictures are fetched; nothing is sent anywhere.

Mapping (parse_page, then story). The markup becomes a flat list of events (headings, paragraphs, links, pictures,
list items, quotes, questions) with the page's chrome left out (nav, the page footer, a header without the headline,
dialogs, cookie banners, hidden and screen-reader-only text). The list is cut into segments at the page's outermost
`<section>`s, or, without them, at its section headings (the highest level after the h1). The segment holding the h1
is the hero: eyebrow, headline, subhead, buttons and its largest picture. Every other segment becomes blocks by its
shape: questions -> faq; quotes -> quote; two or more figures -> stats; numbered steps -> timeline; cards or a list ->
features; three or more photos -> strip; a heading with one photo -> product; a short heading with a button -> cta;
a heading with copy -> intro. A row of small logos is left out. The page's own words and links are kept as they are.

The story. An opening scene from the hero picture: a photo parallax (laptop-friendly, depth only), or with a GPU a
film whose one shot starts from that picture; a kinetic type headline when the page has no hero picture. Then the
page's own statement (its description) as kinetic type when it says something the hero does not, the sections in page
order, and a closing call to action with the hero's button. The brand comes from `theme.from` (engine/brand.py
page_brand), written in as editable tokens; the pictures are saved in the project's inputs/.
"""
from __future__ import annotations

import io
import re
import shutil
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterator, Optional
from urllib.parse import urljoin, urlparse

from .project import BuildError, Project, child

AGENT = "ScrollStudio"                      # the token robots.txt rules are matched against
UA = {"User-Agent": "ScrollStudio-remake (+https://github.com/Okohedeki/scroll-studio)"}
MAX_PAGE = 8_000_000                        # bytes of markup read
MAX_IMAGES = 12                             # pictures saved into inputs/
MAX_IMAGE_BYTES = 12_000_000                # one picture larger than this is skipped
MAX_TOTAL_BYTES = 80_000_000                # all pictures together
MAX_SIDE = 2560                             # pictures are scaled down to this width
PHOTO = (480, 270)                          # a picture smaller than this (long side, short side) is not a photo
NOTICE = ("The words, pictures and brand come from {host} and belong to its owner. Use this remake for yourself, or "
          "with the owner's permission. Nothing was uploaded anywhere.")


class Refused(BuildError):
    """The site's robots.txt does not allow this page to be read."""


# ---------------------------------------------------------------- reading the page

class Robots:
    """robots.txt per origin, read once (RFC 9309: a missing file allows everything; a server error, an unreachable
    host, 401 or 403 is read as 'no')."""

    def __init__(self):
        self._by_origin: dict = {}

    def allowed(self, url: str) -> bool:
        from urllib.robotparser import RobotFileParser

        import requests
        u = urlparse(url)
        origin = f"{u.scheme}://{u.netloc}"
        rp = self._by_origin.get(origin)
        if rp is None:
            rp = RobotFileParser()
            try:
                r = requests.get(origin + "/robots.txt", headers=UA, timeout=15)
                status = r.status_code
            except requests.RequestException:
                status = 503
            if status in (401, 403) or status >= 500:
                rp.disallow_all = True
            elif status >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
            self._by_origin[origin] = rp
        return rp.can_fetch(AGENT, url)


class _NoBrowser(Exception):
    pass


_SCROLL_JS = """async () => {
  const h = () => (document.scrollingElement || document.body).scrollHeight;
  for (let y = 0, i = 0; y < h() && i < 40; y += innerHeight * 0.8, i++) {
    scrollTo(0, y); await new Promise(r => setTimeout(r, 120));
  }
  scrollTo(0, 0); await new Promise(r => setTimeout(r, 200));
}"""

# What only the browser knows, written onto the elements so the one parser reads it: hidden elements (and fixed bars
# such as cookie banners), an image's real size and source, and CSS background pictures of large elements.
_MARK_JS = """() => {
  let n = 0;
  for (const el of (document.body ? document.body.querySelectorAll('*') : [])) {
    if (++n > 30000) break;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') { el.setAttribute('data-ss-hidden', ''); continue; }
    const r = el.getBoundingClientRect();
    if (cs.position === 'fixed' && r.height < innerHeight * 0.5) { el.setAttribute('data-ss-hidden', ''); continue; }
    if (el.tagName === 'IMG') {
      if (el.currentSrc) el.setAttribute('data-ss-src', el.currentSrc);
      el.setAttribute('data-ss-w', el.naturalWidth); el.setAttribute('data-ss-h', el.naturalHeight);
      continue;
    }
    const m = (cs.backgroundImage || '').match(/url\\(["']?([^"')]+)["']?\\)/);
    if (m && r.width >= 320 && r.height >= 200) {
      el.setAttribute('data-ss-bg', m[1]);
      el.setAttribute('data-ss-w', Math.round(r.width)); el.setAttribute('data-ss-h', Math.round(r.height));
    }
  }
}"""


def _browser_read(url: str) -> tuple[str, str]:
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as e:
        raise _NoBrowser("Playwright is not installed") from e
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Error as e:
            raise _NoBrowser("Playwright's Chromium is not installed (playwright install chromium)") from e
        try:
            ctx = browser.new_context(user_agent=UA["User-Agent"], viewport={"width": 1440, "height": 900},
                                      service_workers="block", accept_downloads=False)
            page = ctx.new_page()
            try:
                resp = page.goto(url, wait_until="load", timeout=45_000)
            except Error as e:
                raise BuildError(f"{url} did not load: {str(e).splitlines()[0][:160]}") from None
            if resp is not None and resp.status >= 400:
                raise BuildError(f"{url} answered {resp.status}")
            for js in (_SCROLL_JS, None):
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Error:
                    pass
                if js:
                    page.evaluate(js)
            page.evaluate(_MARK_JS)
            return page.content(), page.url
        finally:
            browser.close()


def read_page(url: str, browser: bool = True, log: Callable = print) -> tuple[str, str]:
    """The page's markup (as the browser drew it, when it can) and its final URL after redirects."""
    if browser:
        from concurrent.futures import ThreadPoolExecutor
        try:
            with ThreadPoolExecutor(1) as pool:       # its own thread: the sync API refuses to run inside an event loop
                return pool.submit(_browser_read, url).result()
        except _NoBrowser as e:
            log(f"  note: {e}; reading the page without a browser, so a page drawn by JavaScript may come out thin")
    import requests
    r = requests.get(url, headers=UA, timeout=30, stream=True)
    if r.status_code >= 400:
        raise BuildError(f"{url} answered {r.status_code}")
    if "html" not in r.headers.get("content-type", "text/html"):
        raise BuildError(f"{url} is not a web page ({r.headers.get('content-type')})")
    data = r.raw.read(MAX_PAGE + 1, decode_content=True)
    if len(data) > MAX_PAGE:
        raise BuildError(f"{url} is larger than {MAX_PAGE // 1_000_000} MB; not read")
    enc = r.encoding if "charset" in r.headers.get("content-type", "") else "utf-8"
    return data.decode(enc or "utf-8", errors="replace"), r.url


# ---------------------------------------------------------------- a forgiving DOM

VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
BLOCK = frozenset("address article aside blockquote details dialog dd div dl dt fieldset figcaption figure footer form "
                  "h1 h2 h3 h4 h5 h6 header hr li main menu nav ol p pre section summary table tbody tfoot thead td "
                  "th tr ul".split())
HEADINGS = frozenset("h1 h2 h3 h4 h5 h6".split())
SKIP = frozenset("script style noscript template iframe svg canvas object embed select textarea input form nav dialog "
                 "head title meta link audio map button".split())
_CLOSES = {"p": BLOCK, "li": {"li"}, "dt": {"dt", "dd"}, "dd": {"dt", "dd"}, "tr": {"tr"}, "td": {"td", "th", "tr"},
           "th": {"td", "th", "tr"}, "option": {"option"}}
_HIDE = re.compile(r"cookie|consent|gdpr|modal|popup|pop-up|sr-only|visually-hidden|screen-reader|skip-link|offcanvas",
                   re.I)


class El:
    __slots__ = ("tag", "attrs", "kids", "parent")

    def __init__(self, tag: str, attrs: dict, parent: Optional["El"]):
        self.tag, self.attrs, self.kids, self.parent = tag, attrs, [], parent

    def get(self, k: str) -> str:
        return self.attrs.get(k) or ""

    @property
    def words(self) -> str:
        return f"{self.get('class')} {self.get('id')} {self.get('role')}".lower()

    def iter(self) -> Iterator["El"]:
        stack = [self]
        while stack:
            el = stack.pop()
            yield el
            stack.extend(k for k in reversed(el.kids) if isinstance(k, El))

    def first(self, *tags: str) -> Optional["El"]:
        return next((e for e in self.iter() if e.tag in tags and e is not self), None)

    def inside(self, *tags: str) -> bool:
        p = self.parent
        while p is not None:
            if p.tag in tags:
                return True
            p = p.parent
        return False


class _Builder(HTMLParser):
    """Builds a tree from any markup: unclosed paragraphs and list items close themselves, stray end tags are ignored."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = El("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        while self.cur.tag in _CLOSES and tag in _CLOSES[self.cur.tag]:
            self.cur = self.cur.parent
        el = El(tag, {k.lower(): (v or "") for k, v in attrs}, self.cur)
        self.cur.kids.append(el)
        if tag not in VOID:
            self.cur = el

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.cur.tag == tag:
            self.cur = self.cur.parent

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if data:
            self.cur.kids.append(data)


def parse_html(html: str) -> El:
    b = _Builder()
    b.feed(html)
    b.close()
    return b.root


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub("[\u200b-\u200d\ufeff\u00ad]", "", t)).strip()


def _hidden(el: El) -> bool:
    a = el.attrs
    if "hidden" in a or "data-ss-hidden" in a or a.get("aria-modal") == "true":
        return True
    if a.get("role") in ("dialog", "alertdialog", "navigation", "contentinfo", "search"):
        return True
    style = a.get("style", "").replace(" ", "").lower()
    return "display:none" in style or "visibility:hidden" in style or bool(_HIDE.search(f"{el.get('class')} {el.get('id')}"))


def _chrome(el: El) -> bool:
    """Page furniture: the page footer, and a header that does not hold the headline."""
    if el.tag == "footer" or el.get("role") == "contentinfo":
        return not el.inside("blockquote", "figure", "li", "article")
    if el.tag == "header" or el.get("role") == "banner":
        return el.first("h1") is None
    return False


def _skip(el: El) -> bool:
    return (el.tag in SKIP and not (el.tag == "button" and el.inside("a"))) or _hidden(el)


def _mute(el: El) -> bool:
    """Decoration hidden from screen readers: its pictures count, its words do not."""
    return el.attrs.get("aria-hidden") == "true"


def _text(el: El, em: bool = False, leave: tuple = ()) -> str:
    """Visible text under `el`. With `em`, emphasised words (em, i, mark, a highlight span) are kept as <em>."""
    out = []
    for k in el.kids:
        if isinstance(k, str):
            out.append(k)
        elif _skip(k) or _mute(k) or k in leave:
            continue
        elif k.tag == "br":
            out.append(" ")
        else:
            t = _text(k, em, leave)
            if k.tag in BLOCK:
                out.append(f" {t} ")
            elif em and t and (k.tag in ("em", "i", "mark") or re.search(r"highlight|accent|gradient|emph", k.get("class"), re.I)):
                out.append(f" <em>{t.replace('<em>', '').replace('</em>', '')}</em> ")
            else:
                out.append(t)
    t = _clean("".join(out))
    return re.sub(r"\s+([,.;:!?])", r"\1", t.replace("<em> ", "<em>").replace(" </em>", "</em>"))


def _inline_only(el: El) -> bool:
    return not any(e.tag in BLOCK for e in el.iter() if e is not el and not _skip(e))


def _plain(t: str) -> str:
    return re.sub(r"</?em>", "", t)


# ---------------------------------------------------------------- what the page holds

@dataclass
class Img:
    url: str
    alt: str = ""
    w: int = 0
    h: int = 0
    hint: str = ""
    file: Optional[str] = None           # inputs/... once saved

    @property
    def junk(self) -> bool:
        """Pixels, icons, avatars, logos and vector art: never a photo for a scene."""
        u = self.url.lower().split("?")[0]
        if u.startswith("data:") or u.endswith((".svg", ".ico")) or (self.w and self.h and (self.w < 120 or self.h < 80)):
            return True
        return bool(re.search(r"pixel|track|beacon|analytics|doubleclick|spacer|blank\.gif|1x1|favicon|sprite", u)
                    or re.search(r"\b(logo|icon|avatar|emoji|badge|spinner|loader|flag)", self.hint))

    @property
    def logo(self) -> bool:
        return bool(re.search(r"(?<![a-z])logo", f"{self.hint} {self.url.lower()}"))

    @property
    def photo(self) -> bool:
        return bool(self.file) and max(self.w, self.h) >= PHOTO[0] and min(self.w, self.h) >= PHOTO[1]


@dataclass
class Ev:
    kind: str                            # h text link img li pair qa quote break
    text: str = ""
    level: int = 0
    href: str = ""
    button: bool = False
    title: str = ""
    hint: str = ""
    anchor: str = ""
    img: Optional[Img] = None
    home: int = 0                        # the element holding it (for a background picture: its own element)
    path: frozenset = frozenset()        # headings: every element they sit in


def _num(v: str) -> int:
    m = re.match(r"\s*(\d+)", v or "")
    return int(m.group(1)) if m else 0


def _srcset(v: str) -> str:
    best, score = "", -1.0
    for part in v.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        d = bits[1] if len(bits) > 1 else "1x"
        s = float(re.sub(r"[^\d.]", "", d) or 1) * (1 if d.endswith("w") else 1000)
        if d.endswith("w") and s > 2600:
            s = 1 / s                          # the largest that is not absurdly large; a huge one only if alone
        if s > score:
            best, score = bits[0], s
    return best


def _img(el: El, base: str) -> Optional[Img]:
    src = (el.get("data-ss-src") or _srcset(el.get("srcset") or el.get("data-srcset"))
           or next((el.get(k) for k in ("src", "data-src", "data-lazy-src", "data-original")
                    if el.get(k) and not el.get(k).startswith("data:")), ""))
    if not src and el.parent is not None and el.parent.tag == "picture":
        src = next((_srcset(s.get("srcset")) for s in el.parent.kids if isinstance(s, El) and s.tag == "source"), "")
    if not src:
        return None
    near = el.parent.words if el.parent is not None else ""
    return Img(urljoin(base, src), _clean(el.get("alt")), _num(el.get("data-ss-w") or el.get("width")),
               _num(el.get("data-ss-h") or el.get("height")), f"{near} {el.words} {_clean(el.get('alt'))}".lower())


def _background(el: El, base: str) -> Optional[Img]:
    url = el.get("data-ss-bg")
    if not url:
        m = re.search(r"background(?:-image)?\s*:[^;]*url\(\s*['\"]?([^'\")]+)", el.get("style"), re.I)
        url = m.group(1) if m else ""
    if not url or url.startswith("data:"):
        return None
    return Img(urljoin(base, url), _clean(el.get("aria-label")), _num(el.get("data-ss-w")), _num(el.get("data-ss-h")),
               el.words)


def _buttonish(el: El) -> bool:
    return bool(re.search(r"btn|button|cta|primary", el.words)) or el.first("button") is not None


class _Walk:
    """The page as a flat list of events, in reading order."""

    def __init__(self, base: str, tops: set):
        self.base, self.tops, self.out = base, tops, []
        self.anchor = ""                 # the id of the element entered last, for the next heading to take

    def add(self, kind: str, home: int, **kw):
        self.out.append(Ev(kind, home=home, **kw))

    def run(self, el: El, hint: str = "", path: tuple = ()) -> None:
        if len(path) > 300:
            return
        path = path + (id(el),)
        for k in el.kids:
            if isinstance(k, str):
                t = _clean(k)
                if len(t) > 1:
                    self.add("text", id(el), text=t, hint=hint)
                continue
            if _skip(k) or _chrome(k):
                continue
            tag, h, home = k.tag, f"{hint} {k.words}"[-240:], id(el)
            if id(k) in self.tops:
                self.add("break", home, anchor=k.get("id"), level=1)
            if k.get("id"):
                self.anchor = k.get("id")
            if _mute(k):
                self.pictures(k, home, h, own=True)
            else:
                bg = _background(k, self.base)
                if bg:
                    self.add("img", id(k), img=bg, hint=h)
                self.one(k, tag, h, home, path)
            if id(k) in self.tops:
                self.add("break", home)

    def pictures(self, el: El, home: int, h: str, own: bool = False) -> None:
        """The pictures in `el` (with `own`, its own background too)."""
        for e in el.iter():
            if e is el and not own and e.tag != "img":
                continue
            im = None if _skip(e) else _img(e, self.base) if e.tag == "img" else _background(e, self.base)
            if im:
                self.add("img", id(e) if e.tag != "img" else home, img=im, hint=h)

    def one(self, k: El, tag: str, h: str, home: int, path: tuple) -> None:
        if tag in HEADINGS:
            t = _text(k, em=True)
            if t:
                self.add("h", home, text=t, level=int(tag[1]), hint=h, anchor=self.anchor, path=frozenset(path))
                self.anchor = ""
        elif tag == "img":
            self.pictures(k, home, h)
        elif tag == "video" and k.get("poster"):
            self.add("img", home, img=Img(urljoin(self.base, k.get("poster")), hint=k.words), hint=h)
        elif tag in ("blockquote", "q") or (tag == "figure" and k.first("blockquote")):
            quote = k.first("blockquote") if tag == "figure" else k
            cites = [e for e in k.iter() if e.tag in ("cite", "figcaption", "footer") and e is not k]
            text = _text(quote, leave=tuple(cites)).strip("“”\"'«» ")
            if text:
                self.add("quote", home, text=text, title=_clean(" ".join(_text(c) for c in cites)).lstrip("—–- "), hint=h)
        elif tag == "details":
            summary = k.first("summary")
            if summary is not None:
                self.add("qa", home, text=_text(k, leave=(summary,)), title=_text(summary), hint=h)
        elif tag == "dl":
            term = None
            for d in (e for e in k.kids if isinstance(e, El) and not _skip(e)):
                if d.tag == "dt":
                    term = _text(d)
                elif d.tag == "dd" and term:
                    self.add("pair", home, text=_text(d), title=term, hint=h)
        elif _inline_only(k) and (tag in ("p", "li", "a") or _one_run(k)):
            self.pictures(k, home, h)
            t = _text(k)
            if not t:
                return
            links = [e for e in k.iter() if e.tag == "a" and e.get("href") and not _skip(e)]
            if links and re.sub(r"\s", "", "".join(_text(a) for a in links)) == re.sub(r"\s", "", t):
                for a in links:            # a run of buttons
                    if _text(a):
                        self.add("link", home, text=_text(a), href=a.get("href"), button=_buttonish(a) or _buttonish(k), hint=h)
            elif tag == "li":
                lead = next((e for e in k.kids if isinstance(e, El) and e.tag in ("strong", "b")), None)
                title = _text(lead) if lead is not None and t.startswith(_text(lead)[:8]) else ""
                body = t[len(title):].lstrip(" :.—–-") if title else t
                self.add("li", home, text=body if title else "", title=title or t, hint=h)
            else:
                self.add("text", home, text=t, hint=h)
        else:
            self.run(k, h, path)


def _one_run(el: El) -> bool:
    """Text that reads as one run: it has words of its own, or a single part that has. A box of separately set parts
    (a figure over its label) is walked part by part instead."""
    if any(isinstance(k, str) and k.strip() for k in el.kids):
        return True
    return sum(1 for k in el.kids if isinstance(k, El) and not _skip(k) and _text(k)) <= 1


def _top_sections(body: El) -> list[El]:
    """The page's outermost <section>s (or the ones inside a single wrapping section)."""
    tops = [e for e in body.iter() if e.tag == "section" and not e.inside("section") and not _skip(e)]
    while len(tops) == 1:
        inner = [e for e in tops[0].iter() if e.tag == "section" and e is not tops[0]
                 and next((p for p in _ancestors(e) if p.tag == "section"), None) is tops[0]]
        if len(inner) < 2:
            break
        tops = inner
    return tops if len(tops) >= 2 else []


def _ancestors(el: El) -> Iterator[El]:
    p = el.parent
    while p is not None:
        yield p
        p = p.parent


def _kickerish(t: str) -> bool:
    return 0 < len(t) <= 40 and len(t.split()) <= 5 and not t.rstrip().endswith((".", "!", "?", ","))


@dataclass
class Page:
    url: str
    title: str = ""
    site_name: str = ""
    description: str = ""
    lang: str = "en"
    kicker: str = ""
    headline: str = ""
    subhead: str = ""
    buttons: list[Ev] = field(default_factory=list)
    hero_images: list[Img] = field(default_factory=list)
    share_image: Optional[Img] = None
    nav_cta: Optional[Ev] = None
    nav_labels: dict[str, str] = field(default_factory=dict)
    segments: list[list[Ev]] = field(default_factory=list)
    anchors: list[str] = field(default_factory=list)

    @property
    def host(self) -> str:
        return urlparse(self.url).netloc

    def images(self) -> Iterator[tuple[str, Img]]:
        """Every picture with a file stem for it, the hero's first."""
        for im in sorted(self.hero_images, key=lambda i: -(i.w * i.h)):
            yield "hero", im
        if self.share_image:
            yield "share", self.share_image
        for k, seg in enumerate(self.segments):
            head = next((e.text for e in seg if e.kind == "h"), "")
            stem = _slug(" ".join(_plain(head).split()[:4]))[:32].strip("-") or f"section-{k + 1}"
            for e in seg:
                if e.kind == "img":
                    yield stem, e.img


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def parse_page(html: str, url: str) -> Page:
    """Everything the remake uses from a page's markup (no network)."""
    root = parse_html(html)
    page = Page(url=url)
    head = root.first("head") or root
    metas = {(m.get("name") or m.get("property")).lower(): _clean(m.get("content")) for m in head.iter() if m.tag == "meta"}
    title = root.first("title")
    page.title = _clean(_text(title)) if title is not None else ""
    page.description = metas.get("description") or metas.get("og:description") or ""
    html_el = root.first("html")
    lang = html_el.get("lang") if html_el is not None else ""
    page.lang = lang if re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", lang or "") else "en"
    if metas.get("og:image"):
        page.share_image = Img(urljoin(url, metas["og:image"]), hint="share")
    page.site_name = metas.get("og:site_name") or _site_name(page.title, page.host)

    body = root.first("body") or root
    for bar in (e for e in body.iter() if e.tag in ("nav", "header") or e.get("role") in ("navigation", "banner")):
        for a in (e for e in bar.iter() if e.tag == "a" and e.get("href")):
            label = _text(a)
            if a.get("href").startswith("#") and len(a.get("href")) > 1 and label:
                page.nav_labels.setdefault(a.get("href")[1:], label)
            elif page.nav_cta is None and label and _buttonish(a) and len(label.split()) <= 4:
                page.nav_cta = Ev("link", label, href=a.get("href"), button=True)

    tops = _top_sections(body)
    walk = _Walk(url, {id(t) for t in tops})
    walk.run(body)
    events = walk.out
    name = page.site_name.lower()
    for e in events:                     # a logo set as the h1 (older themes do) is not the headline
        if e.kind == "h" and e.level == 1 and _plain(e.text).lower() == name and sum(x.kind == "h" for x in events) > 1:
            e.kind, e.level = "text", 0
    levels =[e.level for e in events if e.kind == "h" and e.level > 1]
    split = min(levels) if levels else 2
    segs: list[list[Ev]] = [[]]
    anchors = [""]

    def start(anchor: str = "", within: frozenset = frozenset()):
        cur, moved = segs[-1], []
        while cur and cur[-1].home in within:      # an eyebrow or a background in the heading's own boxes goes with it
            moved.insert(0, cur.pop())
        if cur:
            segs.append([])
            anchors.append(anchor)
        else:
            anchors[-1] = anchor or anchors[-1]
        segs[-1].extend(moved)

    for e in events:
        if e.kind == "break":
            start(e.anchor)
        elif e.kind == "h" and (e.level == 1 or (not tops and e.level <= split)):
            if not tops or any(x.kind == "h" for x in segs[-1]):
                start(e.anchor, e.path)
            segs[-1].append(e)
        else:
            segs[-1].append(e)
    pairs = [(s, a) for s, a in zip(segs, anchors) if s]
    hero_at = next((i for i, (s, _) in enumerate(pairs) if any(e.kind == "h" and e.level == 1 for e in s)),
                   next((i for i, (s, _) in enumerate(pairs) if any(e.kind == "h" for e in s)), None))
    if hero_at is None:
        page.headline = page.site_name or page.host
        page.segments, page.anchors = [s for s, _ in pairs], [a for _, a in pairs]
        return page
    hero = pairs[hero_at][0]
    i = next(j for j, e in enumerate(hero) if e.kind == "h" and (e.level == 1 or not any(x.level == 1 for x in hero if x.kind == "h")))
    nxt = next((j for j in range(i + 1, len(hero)) if hero[j].kind == "h"), len(hero))
    rest = hero[nxt:]                    # a hero section that runs on into the next part of the page
    hero = hero[:nxt]
    if i and hero[i - 1].kind == "text" and _kickerish(hero[i - 1].text):
        page.kicker = hero[i - 1].text
    page.headline = hero[i].text
    page.subhead = next((e.text for e in hero[i + 1:] if e.kind == "text" and len(e.text) >= 20), "")
    links = [e for e in hero if e.kind == "link" and _link_ok(e.href)]
    page.buttons = sorted(links, key=lambda e: not e.button)[:2]
    page.hero_images = [e.img for e in hero if e.kind == "img"]
    after = pairs[hero_at + 1:]
    if rest:
        after.insert(0, (rest, rest[0].anchor))
    page.segments, page.anchors = [s for s, _ in after], [a for _, a in after]
    return page


def _site_name(title: str, host: str) -> str:
    label = host.split(":")[0].removeprefix("www.").split(".")[0]
    parts = [p.strip() for p in re.split(r"\s[|–—·-]\s|:\s", title) if p.strip()]
    for p in parts:
        if _slug(p).replace("-", "") == label.replace("-", ""):
            return p
    return min(parts, key=len) if parts else label.replace("-", " ").title()


def _link_ok(href: str) -> bool:
    return bool(href) and href != "#" and not re.match(r"\s*(javascript|data|vbscript):", href, re.I)


# ---------------------------------------------------------------- pictures into inputs/

def fetch_images(page: Page, project: Project, robots: Robots, warnings: list, log: Callable = print) -> list[str]:
    """Download the page's pictures (photos only, capped in number and size) into inputs/; returns the files."""
    import requests
    from PIL import Image
    files: dict[str, tuple[str, int, int]] = {}
    used: set[str] = set()
    total, tried = 0, 0
    for stem, im in page.images():
        if im.url in files or im.junk or (stem == "share" and "hero" in used):   # the share card: only without a hero
            continue
        if len(files) >= MAX_IMAGES or tried >= MAX_IMAGES * 3:
            warnings.append(f"kept the first {MAX_IMAGES} pictures; the rest of the page's pictures were not downloaded")
            break
        if not im.url.startswith(("http://", "https://")):
            continue
        tried += 1
        if not robots.allowed(im.url):
            warnings.append(f"robots.txt does not allow {im.url[:80]}; left out")
            continue
        try:
            with requests.get(im.url, headers=UA, timeout=20, stream=True) as r:
                r.raise_for_status()
                if not r.headers.get("content-type", "image/").startswith("image/"):
                    continue
                data = r.raw.read(MAX_IMAGE_BYTES + 1, decode_content=True)
            if len(data) > MAX_IMAGE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
                warnings.append(f"{im.url[:80]} is too large; left out")
                continue
            pic = Image.open(io.BytesIO(data))
            w, h = pic.size
            if w * h > 60_000_000 or max(w, h) < PHOTO[0] or min(w, h) < PHOTO[1]:
                continue
            ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(pic.format or "")
            if ext is None or w > MAX_SIDE or getattr(pic, "is_animated", False):
                pic.seek(0)
                pic = pic.convert("RGBA" if "A" in pic.getbands() else "RGB")
                if pic.width > MAX_SIDE:
                    pic = pic.resize((MAX_SIDE, round(MAX_SIDE * pic.height / pic.width)), Image.LANCZOS)
                ext = ".png" if pic.mode == "RGBA" else ".jpg"
                buf = io.BytesIO()
                pic.save(buf, "PNG" if ext == ".png" else "JPEG", quality=90)
                data, (w, h) = buf.getvalue(), pic.size
        except Exception as e:      # an unreachable, broken or odd picture is skipped, never fatal
            log(f"  note: picture {im.url[:70]} not used ({e.__class__.__name__})")
            continue
        name, n = stem, 2
        while name in used:
            name, n = f"{stem}-{n}", n + 1
        used.add(name)
        (project.inputs / (name + ext)).write_bytes(data)
        total += len(data)
        files[im.url] = (f"inputs/{name}{ext}", w, h)
        log(f"  picture inputs/{name}{ext} ({w}x{h})")
    for _, im in list(page.images()):
        if im.url in files:
            im.file, im.w, im.h = files[im.url]
    return [f for f, _, _ in files.values()]


# ---------------------------------------------------------------- the brand (theme.from)

def read_brand(project: Project, html: str, url: str, warnings: list, log: Callable = print) -> Optional[dict]:
    """The page's brand as theme.from tokens (engine/brand.py page_brand), its logo saved into inputs/."""
    from . import brand
    from .spec import Brand
    try:
        tokens = brand.page_brand(project, html, url, log)
    except Exception as e:
        warnings.append(f"the brand was not read ({e.__class__.__name__}); the preset's colours are used")
        return None
    logo = tokens.get("logo")
    if logo and logo.startswith(".build/"):
        dst = project.inputs / ("logo" + Path(logo).suffix)
        shutil.copyfile(project.root / logo, dst)
        tokens["logo"] = dst.relative_to(project.root).as_posix()
    tokens["source"] = url
    tokens = brand.theme_tokens(Brand.model_validate(tokens).model_dump(mode="json", exclude_none=True))
    if not tokens.get("colors") and not tokens.get("fonts"):
        warnings.append("found no brand colours or fonts on the page; the preset's are used")
        return None
    return tokens


# ---------------------------------------------------------------- the story

# A figure such as "12k+", "4.8M", "99.9%", "3 days". The unit part repeats at most twice: its alternatives overlap
# ("m", "s", "ms"), and an unbounded repeat would backtrack exponentially on hostile page text.
_STAT = re.compile(r"^[~≈<>+]?\s?[$€£¥]?\d[\d,.]*\s?(?:%|×|x|k|K|M|B|bn|m|h|hrs?|ms|s|min|"
                   r"yrs?|years?|days?|/\d+|★|stars?|\+){0,2}\+?$")


class _Stat:
    """`STAT.match(text)`, refusing anything longer than a figure could be before the pattern runs."""

    @staticmethod
    def match(text: str):
        return _STAT.match(text) if len(text) <= 32 else None


STAT = _Stat()
STEP = re.compile(r"^(?:(?:step|phase|stage)\s*)?0?(\d{1,2})[.):]?$|^((?:19|20)\d{2})$", re.I)
FAQ = re.compile(r"\bfaqs?\b|frequently asked|questions", re.I)
QUOTE = re.compile(r"testimonial|quote|review|praise|customer-story", re.I)


@dataclass
class _Item:
    title: str
    body: list[str] = field(default_factory=list)
    tag: str = ""

    @property
    def text(self) -> str:
        return " ".join(self.body)


@dataclass
class _Shape:
    head: str = ""
    kicker: str = ""
    lead: list[str] = field(default_factory=list)
    items: list[_Item] = field(default_factory=list)
    quotes: list[list[str]] = field(default_factory=list)
    qas: list[tuple[str, str]] = field(default_factory=list)
    imgs: list[Img] = field(default_factory=list)
    links: list[Ev] = field(default_factory=list)


def _shape(seg: list[Ev]) -> _Shape:
    s = _Shape()
    hi = next((i for i, e in enumerate(seg) if e.kind == "h"), None)
    if hi is not None:
        s.head = seg[hi].text
        if hi and seg[hi - 1].kind == "text" and _kickerish(seg[hi - 1].text):
            s.kicker = seg[hi - 1].text
    cur: Optional[_Item] = None
    who_next = False
    for j, e in enumerate(seg):
        if j == hi or (s.kicker and hi is not None and j == hi - 1):
            continue
        if e.kind == "h":
            tag = ""
            pool = cur.body if cur else (s.lead if not s.items else [])
            if pool and _kickerish(pool[-1]) and len(pool[-1]) <= 24:
                tag = pool.pop()
            cur = _Item(e.text, tag=tag)
            s.items.append(cur)
        elif e.kind == "text":
            if len(e.text) >= 40 and (QUOTE.search(e.hint) or e.text[:1] in "“\"«"):
                s.quotes.append([e.text.strip("“”\"'«» "), ""])
                who_next = True
                continue
            if who_next and len(e.text) <= 80:
                s.quotes[-1][1] = e.text.lstrip("—–- ")
            elif cur:
                cur.body.append(e.text)
            else:
                s.lead.append(e.text)
            who_next = False
        elif e.kind in ("li", "pair"):
            s.items.append(_Item(e.title, [e.text] if e.text else []))
            cur = None
        elif e.kind == "qa":
            s.qas.append((e.title, e.text))
        elif e.kind == "quote":
            s.quotes.append([e.text, e.title])
        elif e.kind == "img":
            s.imgs.append(e.img)
        elif e.kind == "link" and _link_ok(e.href):
            s.links.append(e)
    return s


def _clip(t: str, n: int) -> str:
    t = _clean(t)
    if len(t) <= n:
        return t
    cut = t[:n]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end > n * 0.5:
        return cut[:end + 1]
    return cut[:cut.rfind(" ")].rstrip(",;:") + "…" if " " in cut else cut


def _stat(value: str, label: str) -> dict:
    """A figure as the stats block shows it: a plain number counts up, with what follows it as the unit."""
    value = value.strip()
    m = re.match(r"^(\d[\d,.]*\d|\d)\s*([^\d,.].*)$", value)
    return {**({"value": m.group(1), "unit": m.group(2).strip()} if m else {"value": value}), "label": _clip(label, 48)}


def _stats(s: _Shape) -> tuple[list[dict], set]:
    """Figures with their labels (cards, a figure over its label, '40% faster' lines), and the lead lines they use."""
    out, used = [], set()
    for it in s.items:
        t = _plain(it.title)
        if STAT.match(t) and (it.text or it.tag):
            out.append(_stat(t, it.text or it.tag))
        elif it.body and STAT.match(it.body[0]) and len(t) <= 48:
            out.append(_stat(it.body[0], t))
    texts = s.lead
    j = 0
    while j < len(texts) - 1:
        if STAT.match(texts[j]) and not STAT.match(texts[j + 1]) and len(texts[j + 1]) <= 60:
            out.append(_stat(texts[j], texts[j + 1]))
            used |= {j, j + 1}
            j += 2
        else:
            j += 1
    if len(out) < 2:
        lines = [(j, re.match(r"^(\S+)\s+(.{2,48})$", t)) for j, t in enumerate(texts)]
        lines = [(j, m) for j, m in lines if m and STAT.match(m.group(1))]
        if len(lines) >= 2:
            out += [_stat(m.group(1), m.group(2)) for _, m in lines]
            used |= {j for j, _ in lines}
    return out[:4], used


class _Story:
    def __init__(self, page: Page, gpu: bool):
        self.page, self.gpu = page, gpu
        self.notes: list[str] = []
        self.ids: set[str] = {"open", "statement"}
        self.anchor_ids: dict[str, str] = {}
        self.side = "right"                # product panels alternate, the first with its picture on the left

    def link(self, e: Optional[Ev]) -> Optional[dict]:
        if e is None or not _link_ok(e.href) or not _plain(e.text):
            return None
        href = e.href.strip()
        if not href.startswith("#"):
            href = urljoin(self.page.url, href)
            if urlparse(href).scheme not in ("http", "https", "mailto", "tel"):
                return None
        return {"label": _clip(_plain(e.text), 32), "href": href}

    def ident(self, anchor: str, head: str) -> Optional[str]:
        base = _slug(anchor) or _slug(_plain(head))[:32].strip("-")
        if not base:
            return None
        name, n = base[:48], 2
        while name in self.ids:
            name, n = f"{base[:44]}-{n}", n + 1
        self.ids.add(name)
        if anchor:
            self.anchor_ids[anchor] = name
        return name

    # ---- the opening
    def opener(self) -> list[dict]:
        """The hero as the opening scene: its picture in depth (or, with a GPU, a film shot from it) under the eyebrow,
        headline, subhead and first button; kinetic type when the page has no hero picture."""
        p = self.page
        hero = next((i for i in sorted(p.hero_images, key=lambda i: -(i.w * i.h)) if i.photo), None)
        if hero is None and p.share_image is not None and p.share_image.photo:
            hero = p.share_image
        title, kicker = _clip(p.headline, 120), _clip(p.kicker, 40)
        button = self.link(p.buttons[0]) if p.buttons else None
        if hero is None:
            self.notes.append("the page has no hero picture: the headline opens as kinetic type")
            out = [{"id": "open", "type": "type", "mode": "scale", "size": "display", "text": title, "length": 2.5}]
            if p.subhead or button:
                out.append({"type": "intro", **({"kicker": kicker} if kicker else {}),
                            "title": _clip(p.subhead, 160) if p.subhead else title, **({"button": button} if button else {})})
            return out
        step = {"intro": True, **({"kicker": kicker} if kicker else {}), "title": title,
                **({"body": _clip(p.subhead, 260)} if p.subhead else {}), **({"button": button} if button else {}),
                "at": [0.0, 0.7]}
        if self.gpu:
            return [{"id": "open", "type": "film", "length": 3.0, "cue": "Scroll",
                     "beats": [{"id": "open", "image": hero.file, "seconds": 6,
                                "prompt": _clip(hero.alt or _plain(p.headline), 200),
                                "motion": "a slow cinematic push-in, gentle natural movement, the light shifting softly"}],
                     "steps": [step]}]
        return [{"id": "open", "type": "parallax", "layout": "overlay", "length": 2.5, "move": "dolly", "cue": "Scroll",
                 "steps": [{**step, "image": hero.file}]}]

    def statement(self) -> list[dict]:
        """The page's description as kinetic type, when it says something the hero does not."""
        import difflib
        d = _clean(self.page.description)
        seen = _plain(f"{self.page.headline} {self.page.subhead}").lower()
        if len(d) < 60 or d.lower() in seen or difflib.SequenceMatcher(None, d.lower(), seen).ratio() > 0.6:
            return []
        return [{"id": "statement", "type": "type", "mode": "reveal", "text": _clip(d, 280), "length": 2.5}]

    # ---- one segment of the page
    def blocks(self, seg: list[Ev], anchor: str) -> list[dict]:
        s = _shape(seg)
        head, kick = _clip(s.head, 120), _clip(s.kicker, 40)
        lead = _clip(" ".join(s.lead), 480)
        links = [x for x in (self.link(e) for e in sorted(s.links, key=lambda e: not e.button)) if x]
        photos = [i for i in s.imgs if i.photo]
        named = {k: v for k, v in (("kicker", kick), ("title", head)) if v}
        out: list[dict] = []

        def intro(body: str) -> dict:
            """An intro for the heading and its copy, when there is copy; the block after it then goes untitled."""
            if head and len(body) >= 60:
                out.append({"type": "intro", **named, "body": body})
                return {}
            return named

        qas = s.qas + [(it.title, it.text) for it in s.items
                       if it.title.rstrip().endswith("?") and it.text and (FAQ.search(head) or len(s.items) >= 2)]
        stats, used = _stats(s)
        steps = [it for it in s.items if STEP.match(it.tag) or re.match(r"^(?:step\s*)?\d{1,2}[.)]\s+\S", _plain(it.title), re.I)]
        if len(qas) >= 2 or (qas and FAQ.search(head)):
            out.append({"type": "faq", **({"kicker": kick} if kick else {}), "title": head or "Questions",
                        "items": [{"q": _clip(_plain(q), 160), "a": _clip(a, 600)} for q, a in qas[:8]]})
        elif s.quotes and len(s.items) < 2:
            for text, who in s.quotes[:2]:
                out.append({"type": "quote", "text": _clip(text, 400), **({"who": _clip(who, 80)} if who else {})})
        elif len(stats) >= 2:
            intro(_clip(" ".join(t for j, t in enumerate(s.lead) if j not in used), 480))
            out.append({"type": "stats", "items": stats})
        elif len(photos) >= 3:
            out.append({"type": "strip", **named, **({"body": lead} if lead else {}),
                        "items": [{"image": i.file, **({"caption": _clip(i.alt, 80)} if i.alt else {})} for i in photos[:8]]})
        elif photos and head:
            self.side = "right" if self.side == "left" else "left"
            short = [_plain(it.title) for it in s.items if not it.text and len(_plain(it.title).split()) <= 4]
            block = {"type": "product", **named, "side": self.side, "image": photos[0].file, "knockout": False}
            if lead or (s.items and not short):
                block["body"] = lead or _clip(" ".join(f"{_plain(it.title)}. {it.text}" for it in s.items), 480)
            if short:
                block["tags"] = short[:6]
            if links:
                block["buttons"] = links[:2]
            out.append(block)
            long = [it for it in s.items if it.text]
            if len(long) >= 2:
                out.append(self.features(long, {}))
        elif len(steps) >= 2 and len(steps) >= len(s.items) - 1:
            out.append({"type": "timeline", **intro(lead), "items": [self.step(it) for it in steps[:6]]})
        elif len(s.items) >= 2:
            out.append(self.features(s.items, intro(lead)))
        elif head and links and len(lead) <= 220 and not s.items:
            out.append({"type": "cta", **named, "button": links[0]})
        elif head and (lead or links or s.items):
            body = lead or _clip(" ".join(f"{_plain(it.title)}. {it.text}" for it in s.items), 480)
            out.append({"type": "intro", **named, **({"body": body} if body else {}),
                        **({"button": links[0]} if links else {})})
        elif not head and len(lead) >= 80:
            first = re.split(r"(?<=[.!?])\s", lead, maxsplit=1)
            out.append({"type": "intro", "title": _clip(first[0], 120), **({"body": first[1]} if len(first) > 1 else {})})
        if not out:
            if s.imgs and all(i.logo or i.junk for i in s.imgs) and len(s.imgs) >= 3:
                self.notes.append(f"left out a row of logos{f' ({_plain(head)})' if head else ''}")
            elif head or lead:
                self.notes.append(f"left out a part with too little to show: {_clip(_plain(head or lead), 60)!r}")
            return []
        ident = self.ident(anchor, s.head)
        if ident:
            out[0]["id"] = ident
            label = self.page.nav_labels.get(anchor)
            if label:
                out[0]["nav_label"] = _clip(label, 24)
        return out

    @staticmethod
    def features(items: list[_Item], named: dict) -> dict:
        return {"type": "features", **named, "items": [
            {k: v for k, v in (("tag", _clip(it.tag, 32)), ("title", _clip(_plain(it.title), 80)),
                               ("body", _clip(it.text, 220))) if v} for it in items[:6]]}

    @staticmethod
    def step(it: _Item) -> dict:
        m = re.match(r"^(?:step\s*)?(\d{1,2})[.)]\s+(.+)$", _plain(it.title), re.I)
        when, title = (m.group(1), m.group(2)) if m and not it.tag else (it.tag, _plain(it.title))
        return {"when": _clip(when, 24), "title": _clip(title, 80), **({"body": _clip(it.text, 220)} if it.text else {})}


def story(page: Page, style: Optional[str] = None, gpu: bool = False, brand: Optional[dict] = None) -> tuple[dict, list[str]]:
    """The site.yaml (as a dict) a page tells, and notes on what was left out."""
    st = _Story(page, gpu)
    sections = st.opener() + st.statement()
    for seg, anchor in zip(page.segments, page.anchors):
        sections += st.blocks(seg, anchor)
    primary = st.link(page.buttons[0] if page.buttons else page.nav_cta)
    nav_cta = st.link(page.nav_cta) or primary
    if primary and not any(s["type"] == "cta" for s in sections):
        cta = {"type": "cta", "id": st.ident("", "start") or "start", "kicker": _clip(page.site_name, 40),
               "title": _clip(page.headline, 120), "button": dict(primary)}
        if sections[0]["type"] in ("parallax", "film"):
            cta["background"] = "scene:open"
        sections.append(cta)
    sections = [{"id": s.get("id") or st.ident("", s["type"]), "type": s["type"],      # every section has an id
                 **{k: v for k, v in s.items() if k not in ("id", "type")}} for s in sections]

    def anchors(node):                   # a link to a part of the page goes to that part here, or back to the page
        if isinstance(node, dict):
            href = node.get("href")
            if isinstance(href, str) and href.startswith("#"):
                target = href[1:]
                node["href"] = (f"#{st.anchor_ids[target]}" if target in st.anchor_ids
                                else f"#{target}" if target in st.ids else page.url + (href if target else ""))
            for v in node.values():
                anchors(v)
        elif isinstance(node, list):
            for v in node:
                anchors(v)
    anchors(sections)
    if nav_cta:
        anchors(nav_cta)

    mode = (brand or {}).get("mode", "light")
    theme: dict = {"preset": "night" if mode == "dark" else "studio"}
    if style:
        theme["style"] = style
    if brand:
        theme["from"] = brand
    spec = {"name": _clip(page.site_name, 60) or page.host, "description": _clip(page.description, 300),
            "lang": page.lang, "theme": theme, "nav": {"cta": nav_cta} if nav_cta else {}, "sections": sections,
            "footer": {"left": f"Remade from {page.host} with Scroll Studio. The words and pictures belong to "
                               f"{_clip(page.site_name, 60) or page.host}."}}
    if not spec["description"]:
        del spec["description"]
    return spec, st.notes


# ---------------------------------------------------------------- the command

def has_gpu() -> bool:
    return shutil.which("nvidia-smi") is not None


def project_name(page: Page) -> str:
    return _slug(page.host.split(":")[0].removeprefix("www.").split(".")[0]) or "remake"


def _dump(spec: dict, page: Page) -> str:
    import yaml
    import textwrap
    head = (f"# Remade by `studio remake` from {page.url}\n"
            + "".join(f"# {line}\n" for line in textwrap.wrap(NOTICE.format(host=page.host), 110))
            + "# This is an ordinary site.yaml: edit any line, swap a picture in inputs/, or try another look with\n"
            "# theme.style. theme.from holds the brand read from the page, as editable tokens.\n")

    class Plain(yaml.SafeDumper):
        def ignore_aliases(self, data):           # a repeated link is written out again, never as &anchor / *alias
            return True
    return head + yaml.dump(spec, Dumper=Plain, sort_keys=False, allow_unicode=True, width=110)


def remake(url: str, name: Optional[str] = None, style: Optional[str] = None, gpu: Optional[bool] = None,
           projects: Optional[Path] = None, browser: bool = True, log: Callable = print) -> dict:
    """Read `url` and write a new project telling its story. Returns what was made, with warnings and notes."""
    import yaml

    from .compile import themes
    from .config import settings
    from .spec import Site
    if not re.match(r"^https?://[^/\s]+", url or ""):
        raise BuildError("give the page as an http(s) address, e.g. https://example.com/")
    if style and style not in themes.styles():
        raise BuildError(f"no style {style!r}; styles: {', '.join(sorted(themes.styles()))}")
    robots = Robots()
    if not robots.allowed(url):
        raise Refused(f"{urlparse(url).netloc}'s robots.txt does not allow {url} to be read, so it is not remade")
    log(f"reading {url}")
    html, final = read_page(url, browser, log)
    if final != url and not robots.allowed(final):
        raise Refused(f"the page moved to {final}, which its robots.txt does not allow to be read")
    page = parse_page(html, final)
    name = name or project_name(page)
    root = child(projects or Path(settings()["projects"]), name, "project name")
    if root.exists():
        raise BuildError(f"{root} already exists; pick another name with --name")
    gpu = has_gpu() if gpu is None else gpu
    warnings: list[str] = []
    (root / "inputs").mkdir(parents=True)
    try:
        project = Project(root)
        files = fetch_images(page, project, robots, warnings, log)
        tokens = read_brand(project, html, final, warnings, log)
        spec, notes = story(page, style=style, gpu=gpu, brand=tokens)
        text = _dump(spec, page)
        Site.model_validate(yaml.safe_load(text))           # never write an invalid spec
        project.spec_path.write_text(text, encoding="utf-8")
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    if not page.subhead and not page.segments:
        warnings.append("the page gave little to work with (a page drawn by JavaScript reads best with Playwright's "
                        "Chromium installed)")
    return {"name": name, "path": str(root), "url": final, "spec": str(project.spec_path),
            "sections": [{"id": s.get("id"), "type": s["type"]} for s in spec["sections"]], "images": files,
            "brand": tokens, "gpu": gpu, "warnings": warnings, "notes": notes, "notice": NOTICE.format(host=page.host),
            "next": [f"studio storyboard {name}", f"studio build {name}", f"studio preview {name}"]}
