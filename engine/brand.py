"""Client work: a copy deck the client edits, and a theme drawn from a brand's logo.

Copy deck
  studio copy export my-site            -> my-site/copy.md: every piece of visible text, one block per field
  studio copy import my-site copy.md    -> applies the edits to site.yaml (comments and layout kept), shows what
                                           changed, and refuses edits that would make the spec invalid
  The deck is plain Markdown, so it goes by email or into a shared doc. Keys (the ### lines) stay as they are;
  everything under a key, up to the next key, is that field's new text. Lists (tags, words) are one item per line.
  A rebuild after an import only re-renders what the text touches: blocks are instant, scenes keep their caches
  unless their own inputs changed.

Brand
  studio brand my-site --logo inputs/logo.png [--mode light|dark]
  samples the logo's colours, picks the most characterful one as the accent, builds background, ink and a second
  accent around it with the same contrast rules as the presets, and writes them to theme.colors (plus nav.logo).
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from .project import BuildError, Project
from .spec import Site

# Fields that hold visible text (prompts, ids, paths and urls are left alone)
TEXT_KEYS = {"title", "body", "kicker", "badge", "label", "text", "who", "note", "q", "a", "when", "hint", "caption",
             "cue", "left", "right", "tag", "center", "status", "app", "button", "y_label", "source", "description",
             "placeholder"}
LIST_KEYS = {"tags", "words"}
SKIP_UNDER = {"prompt", "generate", "keyframes", "ltx", "take", "data", "state", "hud", "theme", "image", "video",
              "backdrop", "credit", "callouts", "imagery", "directions"}


def _yaml():
    from ruamel.yaml import YAML
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)   # "  - item", as the examples are written
    return y


def _walk(node: Any, path: list, out: list) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k in SKIP_UNDER:
                continue
            if k in TEXT_KEYS and isinstance(v, str):
                out.append((path + [k], v))
            elif k in LIST_KEYS and isinstance(v, list) and all(isinstance(x, str) for x in v):
                out.append((path + [k], v))
            elif isinstance(v, (dict, list)):
                _walk(v, path + [k], out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, path + [i], out)


def fields(raw: dict) -> list[tuple[list, Any]]:
    out: list = []
    if isinstance(raw.get("name"), str):
        out.append((["name"], raw["name"]))
    _walk(raw, [], out)
    return out


def key(path: list) -> str:
    return ".".join(str(p) for p in path)


def _section_label(raw: dict, i: int) -> str:
    s = raw["sections"][i]
    return f"{i + 1}. {s.get('type', 'section')}" + (f" #{s['id']}" if s.get("id") else "")


def export_deck(project: Project) -> str:
    raw = project.raw()
    lines = [f"# Copy deck: {raw.get('name', project.name)}", "",
             "Edit the text under each ### line and send this file back. Keep the ### lines exactly as they are.",
             "Inline emphasis is written <em>like this</em>. Lists (tags, words) are one item per line.", ""]
    group = None
    for path, v in fields(raw):
        g = _section_label(raw, path[1]) if path[0] == "sections" and len(path) > 1 else ("Site" if path[0] in ("name", "description", "nav") else "Footer")
        if g != group:
            lines += [f"## {g}", ""]
            group = g
        lines += [f"### {key(path)}", "\n".join(v) if isinstance(v, list) else str(v), ""]
    return "\n".join(lines)


def parse_deck(text: str) -> dict[str, str]:
    out, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^### (\S+)\s*$", line)
        if m or re.match(r"^#{1,2} ", line):
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = (m.group(1) if m else None), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def _pad_braces(text: str) -> str:
    """ruamel writes flow mappings as {a: b}; the examples write { a: b }. Pad braces outside quoted strings."""
    out = []
    for line in text.splitlines(keepends=True):
        res, q = [], None
        for i, ch in enumerate(line):
            if q:
                if ch == q and line[i - 1] != "\\":
                    q = None
            elif ch in "\"'":
                q = ch
            elif ch == "{" and i + 1 < len(line) and line[i + 1] not in " }\r\n":
                res.append("{ ")
                continue
            elif ch == "}" and i and line[i - 1] not in " {":
                res.append(" }")
                continue
            res.append(ch)
        out.append("".join(res))
    return "".join(out)


def _dump(y, doc, original: str) -> str:
    buf = io.StringIO()
    y.dump(doc, buf)
    text = buf.getvalue()
    text = _pad_braces(text) if "{ " in original else text
    return text.replace("\n", "\r\n") if "\r\n" in original else text   # keep the file's line endings


def _get(node, path):
    for p in path:
        node = node[p]
    return node


def import_deck(project: Project, text: str, dry_run: bool = False) -> list[tuple[str, Any, Any]]:
    """Apply a copy deck. Returns [(key, old, new)] for every field that changed."""
    y = _yaml()
    original = project.spec_path.read_text(encoding="utf-8")
    doc = y.load(original)
    known = {key(p): (p, v) for p, v in fields(doc)}
    edits = parse_deck(text)
    unknown = [k for k in edits if k not in known]
    if unknown:
        raise BuildError(f"the deck has keys this site doesn't: {', '.join(unknown[:5])} (was it exported from another version?)")
    changes = []
    for k, new in edits.items():
        path, old = known[k]
        if isinstance(old, list):
            new_v = [ln.strip() for ln in new.splitlines() if ln.strip()]
            if new_v != list(old):
                changes.append((k, list(old), new_v))
                from ruamel.yaml.comments import CommentedSeq
                seq = CommentedSeq(new_v)
                if getattr(old, "fa", None) is not None and old.fa.flow_style():
                    seq.fa.set_flow_style()   # [a, b, c] stays on one line
                _get(doc, path[:-1])[path[-1]] = seq
        else:
            new_v = " ".join(ln.strip() for ln in new.splitlines() if ln.strip())   # one paragraph per field
            if not new_v:
                raise BuildError(f"{k} is empty in the deck; leave the old text if it shouldn't change")
            if new_v != old:
                changes.append((k, old, new_v))
                _get(doc, path[:-1])[path[-1]] = new_v
    text_out = _dump(y, doc, original)
    import yaml as _pyyaml
    Site.model_validate(_pyyaml.safe_load(text_out))   # never write an invalid spec
    if changes and not dry_run:
        project.spec_path.write_text(text_out, encoding="utf-8")
    return changes


# ---------------------------------------------------------------- brand colours from a logo
def _palette(img_path: Path, k: int = 6) -> list[tuple[tuple[int, int, int], float]]:
    """Main colours of an image (ignoring transparent and near-white/near-black background), most common first."""
    import numpy as np
    from PIL import Image
    im = Image.open(img_path).convert("RGBA")
    im.thumbnail((200, 200))
    a = np.asarray(im).reshape(-1, 4).astype(np.float32)
    a = a[a[:, 3] > 128][:, :3]
    if len(a) == 0:
        raise BuildError(f"{img_path} has no visible pixels")
    q = (a // 24).astype(np.int32)
    keys, inv, counts = np.unique(q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2], return_inverse=True, return_counts=True)
    order = np.argsort(-counts)
    out = []
    for idx in order[:40]:
        col = a[inv == idx].mean(axis=0)
        share = counts[idx] / len(a)
        if all(sum(abs(col - np.array(c)) ) > 60 for c, _ in out):
            out.append((tuple(int(v) for v in col), float(share)))
        if len(out) >= k:
            break
    return out


def _hex(c) -> str:
    return "#" + "".join(f"{int(round(v)):02x}" for v in c)


def brand_colors(logo: Path, mode: str = "light") -> dict:
    import colorsys
    from .compile.themes import contrast
    pal = _palette(logo)

    def chroma(c):
        h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
        return s * (1 - abs(2 * l - 1))
    # the accent: the most colourful colour that covers a fair part of the mark
    ranked = sorted(pal, key=lambda cs: chroma(cs[0]) * (0.35 + cs[1]), reverse=True)
    accent = ranked[0][0]
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in accent))
    if mode == "light":
        bg = tuple(v * 255 for v in colorsys.hls_to_rgb(h, 0.965, min(s, 0.35)))
        bg2 = tuple(v * 255 for v in colorsys.hls_to_rgb(h, 0.925, min(s, 0.3)))
        ink = tuple(v * 255 for v in colorsys.hls_to_rgb(h, 0.11, min(s, 0.3)))
    else:
        bg = tuple(v * 255 for v in colorsys.hls_to_rgb(h, 0.045, min(s, 0.4)))
        bg2 = tuple(v * 255 for v in colorsys.hls_to_rgb(h, 0.08, min(s, 0.35)))
        ink = tuple(v * 255 for v in colorsys.hls_to_rgb(h, 0.95, min(s, 0.25)))
    # accent2: a second brand colour if the logo has one, else a lighter accent
    other = next((c for c, _ in ranked[1:] if chroma(c) > 0.25 and abs(colorsys.rgb_to_hls(*(v / 255 for v in c))[0] - h) > 0.08), None)
    accent2 = other or tuple(v * 255 for v in colorsys.hls_to_rgb(h, min(0.8, l + 0.18), s))
    accent_ink = max(((255, 255, 255), (0, 0, 0), ink, bg), key=lambda c: contrast(c, accent))
    return {"bg": _hex(bg), "bg2": _hex(bg2), "ink": _hex(ink), "accent": _hex(accent), "accent2": _hex(accent2),
            "accent_ink": _hex(accent_ink), "_palette": [_hex(c) for c, _ in pal]}


def apply_brand(project: Project, logo_rel: str, mode: str = "light", dry_run: bool = False) -> dict:
    logo = project.path(logo_rel)
    if not logo.exists():
        raise BuildError(f"{logo_rel} not found")
    cols = brand_colors(logo, mode)
    palette = cols.pop("_palette")
    y = _yaml()
    original = project.spec_path.read_text(encoding="utf-8")
    doc = y.load(original)
    from ruamel.yaml.comments import CommentedMap
    theme = doc.get("theme")
    if theme is None:
        theme = doc["theme"] = CommentedMap()
    theme.setdefault("colors", CommentedMap()).update(cols)
    theme["mode"] = mode
    if logo.suffix.lower() in (".svg", ".png", ".webp", ".jpg", ".jpeg"):
        nav = doc.get("nav")
        if nav is None:
            nav = doc["nav"] = CommentedMap()
        nav["logo"] = logo_rel
    text_out = _dump(y, doc, original)
    import yaml as _pyyaml
    Site.model_validate(_pyyaml.safe_load(text_out))
    if not dry_run:
        project.spec_path.write_text(text_out, encoding="utf-8")
    return {"colors": cols, "palette": palette}


# ---------------------------------------------------------------- a brand from a page, a logo or a brand.yaml (theme.from)
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp", ".svg")
UA = {"User-Agent": "Mozilla/5.0 (compatible; ScrollStudio brand reader)"}
MAX_FETCH = 4_000_000            # bytes: a page, a stylesheet or a logo larger than this is not read


def _kind(ref: str) -> str:
    if ref.startswith(("http://", "https://")):
        return "url"
    suffix = Path(ref).suffix.lower()
    if suffix in (".yaml", ".yml"):
        return "yaml"
    if suffix in (".html", ".htm"):
        return "html"
    if suffix in IMAGE_TYPES:
        return "image"
    raise BuildError(f"theme.from {ref[:60]!r}: give a web page (https://...), a page saved as .html, a logo image "
                     f"({', '.join(IMAGE_TYPES)}) or a brand.yaml")


def _fetch(url: str, binary: bool = False):
    """One request, only ever for a URL the spec or the command names (theme.from, studio brand --from)."""
    import requests
    from .safety import check_url
    check_url(url, "theme.from")
    r = requests.get(url, headers=UA, timeout=20, stream=True)
    r.raise_for_status()
    data = r.raw.read(MAX_FETCH + 1, decode_content=True)
    if len(data) > MAX_FETCH:
        raise BuildError(f"{url[:80]} is larger than {MAX_FETCH // 1_000_000} MB; not read")
    return data if binary else data.decode(r.encoding or "utf-8", errors="replace")


def brand_from(project: Project, ref: str, refresh: bool = False, log=print) -> dict:
    """The brand tokens `theme.from` names, as a Brand token set (engine/spec.py). Read once and kept in
    .build/brand/: a file is read again when it changes, a web page only when `refresh` (studio brand --from)."""
    import hashlib
    import json

    from .spec import Brand
    kind = _kind(ref)
    stamp = ref
    if kind != "url":
        src = project.path(ref)
        if not src.is_file():
            raise BuildError(f"theme.from: {ref} not found in the project folder")
        stamp += hashlib.sha1(src.read_bytes()).hexdigest()
    cache = project.build / "brand" / (hashlib.sha1(stamp.encode()).hexdigest()[:16] + ".json")
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    if kind == "yaml":
        import yaml
        raw = yaml.safe_load(project.path(ref).read_text(encoding="utf-8")) or {}
        tokens = Brand.model_validate(raw).model_dump(mode="json", exclude_none=True)
    elif kind == "image":
        tokens = {"colors": logo_colors(project.path(ref)), "logo": ref}
    else:
        if kind == "url":
            log(f"theme.from: reading {ref}")
            page, base = _fetch(ref), ref
        else:
            page, base = project.path(ref).read_text(encoding="utf-8", errors="replace"), ref
        tokens = page_brand(project, page, base, log)
    tokens["source"] = ref
    tokens = Brand.model_validate(tokens).model_dump(mode="json", exclude_none=True)     # what a page says is data
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(tokens, indent=1), encoding="utf-8")
    return tokens


def _chroma(c) -> float:
    import colorsys
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
    return s * (1 - abs(2 * l - 1))


def _brand_accents(pal: list[tuple[tuple, float]], named: tuple = ()) -> dict:
    """The accent (a colour the source names as its brand colour, else the most colourful one with a fair share) and,
    if there is one, a second brand colour of another hue."""
    import colorsys
    ranked = [(c, 1.0) for c in named] + sorted(pal, key=lambda cs: _chroma(cs[0]) * (0.35 + cs[1]), reverse=True)
    if not ranked:
        return {}
    accent = ranked[0][0]
    hue = colorsys.rgb_to_hls(*(v / 255 for v in accent))[0]
    other = next((c for c, _ in ranked[1:] if _chroma(c) > 0.25
                  and abs(colorsys.rgb_to_hls(*(v / 255 for v in c))[0] - hue) > 0.08), None)
    return {"accent": _hex(accent), **({"accent2": _hex(other)} if other else {})}


def _hexes(text: str) -> list[tuple]:
    out = []
    for h in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", text):
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        out.append(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
    return out


def _shares(cols: list[tuple]) -> list[tuple[tuple, float]]:
    from collections import Counter
    n = Counter(cols)
    return [(c, k / max(len(cols), 1)) for c, k in n.most_common(40)]


def logo_colors(path: Path) -> dict:
    """A logo's brand colours: an SVG's own fills and strokes, or a raster's main colours (_palette)."""
    if path.suffix.lower() == ".svg":
        text = path.read_text(encoding="utf-8", errors="replace")
        pal = [(c, s) for c, s in _shares(_hexes(text)) if 30 < sum(c) / 3 < 235 or _chroma(c) > 0.2]
    else:
        pal = _palette(path)
    cols = _brand_accents(pal)
    if not cols:
        raise BuildError(f"{path.name}: found no brand colour in it")
    return cols


def _css_blocks(css: str, selector: str) -> str:
    """The declarations of every rule whose selector list names `selector` (body, h1, button...)."""
    out = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if any(re.fullmatch(selector, s.strip(), re.I) for s in sel.split(",")):
            out.append(body)
    return ";".join(out)


def _decl(body: str, prop: str) -> list[str]:
    return [v.strip() for v in re.findall(rf"(?<![\w-]){prop}\s*:\s*([^;]+)", body, re.I)]


def page_brand(project: Project, page: str, base: str, log=print) -> dict:
    """Colours, fonts, radius and logo of a web page, from its markup and styles. Fonts are kept only when they are
    Google Fonts families (the page links them, or the engine knows them); a brand's own face is added as a file."""
    from html.parser import HTMLParser
    from urllib.parse import urljoin, urlparse

    def google_fonts(href: str) -> bool:
        return (urlparse(urljoin("https://x/", href)).hostname or "") == "fonts.googleapis.com"

    from .compile.themes import FONT_AXES

    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags, self.styles, self._in_style = [], [], False

        def handle_starttag(self, tag, attrs):
            a = {k: (v or "") for k, v in attrs}
            self.tags.append((tag, a))
            self._in_style = tag == "style"
            if a.get("style"):
                self.styles.append("[style] {" + a["style"].replace("{", "").replace("}", "") + "}")   # a rule of its own

        def handle_endtag(self, tag):
            self._in_style = False if tag == "style" else self._in_style

        def handle_data(self, data):
            if self._in_style:
                self.styles.append(data)

    p = Tags()
    p.feed(page)
    css = "\n".join(p.styles)
    remote = base.startswith(("http://", "https://"))
    sheets = [a["href"] for t, a in p.tags if t == "link" and "stylesheet" in a.get("rel", "").lower() and a.get("href")]
    for href in sheets[:4]:          # the page's own stylesheets carry most of its look
        if google_fonts(href):
            continue
        try:
            css += "\n" + (_fetch(urljoin(base, href)) if remote else _local(project, base, href).read_text(encoding="utf-8"))
        except Exception as e:      # a missing or unreachable stylesheet: the page's inline styles still count
            log(f"  note: stylesheet {href[:60]} not read ({e.__class__.__name__})")

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)      # a comment before a rule would hide its selector
    colors: dict = {}
    root = _css_blocks(css, r"html|body|:root")
    for prop, role in (("background-color", "bg"), ("background", "bg"), ("color", "ink")):
        for v in _decl(root, prop):
            h = _hexes(v)
            if h and role not in colors:
                colors[role] = _hex(h[0])
    named = [_hexes(v) for k, v in re.findall(r"--([\w-]*(?:brand|primary|accent)[\w-]*)\s*:\s*([^;]+)", css, re.I)]
    meta = [_hexes(a.get("content", "")) for t, a in p.tags if t == "meta" and a.get("name", "").lower() == "theme-color"]
    picked = tuple(c[0] for c in meta + named if c)       # what the page itself calls its brand colour comes first
    acc = _brand_accents(_shares(_hexes(css)), picked)
    colors.update({k: v for k, v in acc.items() if k not in colors})

    google = {re.sub(r"\+", " ", f.split(":")[0]) for t, a in p.tags if t == "link"
              for f in re.findall(r"family=([^&]+)", a.get("href", "")) if google_fonts(a.get("href", ""))}

    def family(selector: str):
        for v in _decl(_css_blocks(css, selector), "font-family"):
            first = v.split(",")[0].strip().strip("\"'")
            if first in google or first in FONT_AXES:
                return first
        return None
    fonts = {k: f for k, f in (("display", family(r"h1|h2|h1 *\.?[\w-]*|\.?[\w-]*title|\.?[\w-]*heading")),
                               ("body", family(r"html|body|:root|p")), ("mono", family(r"code|pre|kbd"))) if f}

    radius = None
    rads = [r for v in _decl(_css_blocks(css, r"button|\.btn[\w-]*|\.button[\w-]*|a\.btn[\w-]*"), "border-radius")
            for r in re.findall(r"^\d+(?:\.\d+)?(?:px|rem|em)$", v.split()[0])]
    if rads:
        radius = "999px" if rads[0].endswith("px") and float(rads[0][:-2]) >= 99 else rads[0]

    logo = None
    cands = [a.get("src") for t, a in p.tags if t == "img" and a.get("src")
             and re.search(r"logo", " ".join((a.get("src"), a.get("alt", ""), a.get("class", ""), a.get("id", ""))), re.I)]
    cands += [a.get("href") for t, a in p.tags if t == "link" and re.search(r"\bicon\b", a.get("rel", ""), re.I)
              and a.get("href", "").lower().endswith(".svg")]
    for src in cands:
        if src.startswith("data:"):
            continue
        try:
            logo = _save_logo(project, urljoin(base, src)) if remote else str(_local(project, base, src).relative_to(project.root.resolve()).as_posix())
            break
        except Exception as e:
            log(f"  note: logo {src[:60]} not used ({e.__class__.__name__})")
    out = {"colors": colors, "fonts": fonts}
    if radius:
        out["radius"] = radius
    if logo:
        out["logo"] = logo
    return out


def _local(project: Project, page_ref: str, href: str) -> Path:
    """A file a saved page links to, relative to the page and inside the project."""
    if href.startswith(("http://", "https://", "//", "data:")):
        raise BuildError(f"{href[:60]} is not a file beside the page")
    return project.path(str(Path(page_ref).parent / href.split("?")[0].split("#")[0]))


def _save_logo(project: Project, url: str) -> str:
    """A web page's logo, kept in .build/brand/ so the built site serves it itself."""
    import hashlib
    suffix = Path(url.split("?")[0]).suffix.lower()
    if suffix not in IMAGE_TYPES:
        raise BuildError(f"{url[:60]} is not an image ({', '.join(IMAGE_TYPES)})")
    data = _fetch(url, binary=True)
    out = project.build / "brand" / ("logo-" + hashlib.sha1(data).hexdigest()[:12] + suffix)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out.relative_to(project.root).as_posix()


def theme_tokens(tokens: dict) -> dict:
    """A brand's tokens as theme.from writes them out: a complete, contrast-checked palette (with the mode it implies),
    then fonts, radius, logo and source, in that order."""
    from .compile.themes import brand_palette
    tokens = dict(tokens)
    if tokens.get("colors"):
        tokens["colors"], tokens["mode"] = brand_palette(tokens["colors"], tokens.get("mode"))
    return {k: tokens[k] for k in ("mode", "colors", "fonts", "radius", "logo", "source") if tokens.get(k)}


def write_brand(project: Project, ref: str, dry_run: bool = False, log=print) -> dict:
    """`studio brand --from`: read the brand afresh and write its tokens into site.yaml as theme.from (a complete,
    contrast-checked palette, its fonts, radius and logo), so they can be edited; the source is kept as `source`."""
    from ruamel.yaml.comments import CommentedMap

    tokens = theme_tokens(brand_from(project, ref, refresh=True, log=log))
    y = _yaml()
    original = project.spec_path.read_text(encoding="utf-8")
    doc = y.load(original)
    theme = doc.get("theme")
    if theme is None:
        theme = doc["theme"] = CommentedMap()
    theme["from"] = CommentedMap(tokens.items())
    text_out = _dump(y, doc, original)
    import yaml as _pyyaml
    Site.model_validate(_pyyaml.safe_load(text_out))     # never write an invalid spec
    if not dry_run:
        project.spec_path.write_text(text_out, encoding="utf-8")
    return tokens
