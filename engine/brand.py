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
             "cue", "left", "right", "tag", "center", "status", "app", "button", "y_label", "source", "description"}
LIST_KEYS = {"tags", "words"}
SKIP_UNDER = {"prompt", "generate", "keyframes", "ltx", "take", "data", "state", "hud", "theme", "image", "video",
              "backdrop", "credit", "callouts"}


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
    from .compile.themes import _lum, _mix, contrast
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
