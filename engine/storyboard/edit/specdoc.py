"""Editing site.yaml in place, for the storyboard's edit workspace.

The spec stays the single source of truth, and a save must leave the file the way the author wrote it. Two ways to
write, tried in this order:

  splice      the new scalar replaces the old one in the text itself (positions from ruamel's composer), and a new key
              is added to the end of its mapping. Every other byte of the file stays as it was: comments, column
              alignment, hand-wrapped flow mappings, quoting, line endings, anchors.
  round trip  ruamel's round-trip dump with the file's own indentation and wrap width guessed from it (for edits the
              splice cannot make, such as a source switched from a file to a prompt).

Either result is checked against the plain-Python meaning of the edit (`yaml.safe_load` of the new text must equal the
old data with the edit applied) and against the pydantic spec before anything is written. A rejected edit is returned
as errors for the card; the file is not touched. Each write keeps the previous text in
`<project>/storyboard/history/` (newest 30), which is also what "Undo save" restores.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from ...project import BuildError, Project
from ...spec import Site

MISSING = object()
KEEP_HISTORY = 30


class SpecError(Exception):
    """The edit would make the spec invalid (or unreadable). `errors`: [{loc, msg}]."""
    def __init__(self, errors: list[dict]):
        super().__init__("; ".join(f"{e['loc']}: {e['msg']}" for e in errors[:3]))
        self.errors = errors


class Conflict(Exception):
    """A field changed on disk since the page read it. `paths`: the dotted paths."""
    def __init__(self, paths: list[str]):
        super().__init__("site.yaml changed on disk: " + ", ".join(paths[:4]))
        self.paths = paths


@dataclass
class Op:
    path: tuple
    value: Any = None
    delete: bool = False


class _Splice(Exception):
    """This edit cannot be made as a text splice; use the round trip."""


_LOCKS: dict[str, threading.RLock] = {}
WRITTEN: list[str] = []          # revisions written by this process (the page tells its own saves from outside changes)


def lock(project: Project) -> threading.RLock:
    return _LOCKS.setdefault(str(project.root), threading.RLock())


# ---------------------------------------------------------------- reading

def read_text(project: Project) -> str:
    """The file as written: line endings kept (Path.read_text would translate CRLF)."""
    raw = project.spec_path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8")


def rev_of(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


_REV_CACHE: dict[str, tuple] = {}


def current_rev(project: Project) -> str:
    """The revision of site.yaml on disk (a content hash; re-hashed only when the file's stat changes)."""
    p = project.spec_path
    try:
        st = p.stat()
    except OSError:
        return ""
    sig = (st.st_mtime_ns, st.st_size)
    hit = _REV_CACHE.get(str(p))
    if hit and hit[0] == sig:
        return hit[1]
    rev = rev_of(read_text(project))
    _REV_CACHE[str(p)] = (sig, rev)
    return rev


def get(raw: Any, path) -> Any:
    """The value at a path in plain loaded YAML, or MISSING."""
    node = raw
    for p in path:
        try:
            if isinstance(node, dict):
                node = node[p]
            elif isinstance(node, list) and isinstance(p, int):
                node = node[p]
            else:
                return MISSING
        except (KeyError, IndexError):
            return MISSING
    return node


def dotted(path) -> str:
    return ".".join(str(p) for p in path)


def parse_dotted(s: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in s.split(".") if p != "")


def _apply_plain(data: Any, ops: list[Op]) -> Any:
    """The edit's meaning on plain data (what the text must load back as)."""
    data = copy.deepcopy(data)
    for op in ops:
        parent = get(data, op.path[:-1])
        if parent is MISSING:
            raise _Splice(f"no parent for {dotted(op.path)}")
        k = op.path[-1]
        if op.delete:
            if isinstance(parent, dict):
                parent.pop(k, None)
            elif isinstance(parent, list):
                del parent[k]
        elif isinstance(parent, list):
            parent[k] = copy.deepcopy(op.value)
        else:
            parent[k] = copy.deepcopy(op.value)
    return data


# ---------------------------------------------------------------- the splice

def _compose(text: str):
    from ruamel.yaml import YAML
    return YAML().compose(text)


def _key_text(node) -> str:
    return getattr(node, "value", None)


def _child(node, key):
    from ruamel.yaml.nodes import MappingNode, SequenceNode
    if isinstance(node, MappingNode):
        merge = False
        for k, v in node.value:
            kv = _key_text(k)
            if kv == "<<":
                merge = True
            if kv == str(key):
                return v, k
        if merge:
            raise _Splice("merge key")
        return None, None
    if isinstance(node, SequenceNode):
        if not isinstance(key, int) or key >= len(node.value):
            raise _Splice("bad index")
        return node.value[key], None
    raise _Splice("not a container")


def _leaf_end(node) -> int:
    """Index just after the last character of a node's text (block scalars and aliases are refused)."""
    from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode
    if isinstance(node, ScalarNode):
        if node.style in ("|", ">"):
            raise _Splice("block scalar")
        return node.end_mark.index
    if isinstance(node, (MappingNode, SequenceNode)):
        if node.flow_style:
            return node.end_mark.index
        if not node.value:
            raise _Splice("empty block collection")
        last = node.value[-1]
        return _leaf_end(last[1] if isinstance(node, MappingNode) else last)
    raise _Splice("unknown node")


_PLAIN_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./+-]*$")


def render_scalar(value: Any, style: Optional[str] = None, in_flow: bool = False) -> str:
    """YAML text for a scalar, quoted the way the old value was where that still fits."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        s = repr(value)
        if "e" in s and "." not in s.split("e")[0]:
            s = s.replace("e", ".0e")
        return s
    if not isinstance(value, str):
        raise _Splice("not a scalar")
    if style == '"':
        return json.dumps(value, ensure_ascii=False)
    if style == "'" and "\n" not in value and not re.search(r"[\x00-\x08\x0b-\x1f]", value):
        return "'" + value.replace("'", "''") + "'"
    if style in ("|", ">"):
        raise _Splice("block scalar")
    if "\n" in value or re.search(r"[\x00-\x08\x0b-\x1f]", value):
        return json.dumps(value, ensure_ascii=False)
    out = yaml.safe_dump(value, allow_unicode=True, width=10 ** 9, default_flow_style=True).rstrip()
    if out.endswith("\n..."):
        out = out[:-4]
    elif out.endswith("..."):
        out = out[:-3].rstrip()
    if out.startswith(("'", '"')):
        return out
    if in_flow and not _PLAIN_SAFE.match(value):
        return json.dumps(value, ensure_ascii=False)
    return out


def _splice_delete(text: str, op: Op) -> str:
    """Remove a key whose value is a single scalar: its lines in a block mapping, `key: value` and a comma in a flow one."""
    from ruamel.yaml.nodes import MappingNode, ScalarNode
    node = _compose(text)
    for key in op.path[:-1]:
        node, _k = _child(node, key)
        if node is None:
            raise _Splice("missing parent")
    if not isinstance(node, MappingNode):
        raise _Splice("not a mapping")
    target, knode = _child(node, op.path[-1])
    if target is None:
        return text                                  # nothing there: already gone
    if not isinstance(target, ScalarNode) or target.style in ("|", ">") or target.end_mark.index <= knode.end_mark.index:
        raise _Splice("not a plain scalar entry")
    if len(node.value) < 2:
        raise _Splice("only key")
    s, e = knode.start_mark.index, target.end_mark.index
    if node.flow_style:
        i = [k for k, _ in node.value].index(knode)
        if i < len(node.value) - 1:                  # up to the next key
            nxt = node.value[i + 1][0].start_mark.index
            return text[:s] + text[nxt:]
        prev_end = _leaf_end(node.value[i - 1][1])   # the last key: from the comma before it
        return text[:prev_end] + text[e:]
    ls = text.rfind("\n", 0, s) + 1
    if text[ls:s].strip():
        raise _Splice("key shares its line")
    le = text.find("\n", e)
    le = len(text) if le < 0 else le + 1
    return text[:ls] + text[le:]


def _splice_one(text: str, op: Op) -> str:
    from ruamel.yaml.nodes import MappingNode, ScalarNode
    if op.delete:
        return _splice_delete(text, op)
    root = _compose(text)
    node = root
    path = list(op.path)
    for i, key in enumerate(path[:-1]):
        node, _k = _child(node, key)
        if node is None:
            raise _Splice("missing parent")
    last = path[-1]
    if isinstance(node, MappingNode):
        target, knode = _child(node, last)
        in_flow = bool(node.flow_style)
    else:
        target, knode = _child(node, last)
        in_flow = bool(node.flow_style)
    nl = "\r\n" if "\r\n" in text else "\n"
    if target is not None:
        if not isinstance(target, ScalarNode) or isinstance(op.value, (dict, list, tuple)):
            raise _Splice("not a scalar edit")
        s, e = target.start_mark.index, target.end_mark.index
        head = text[s:s + 1]
        if head in ("&", "*", "!"):
            raise _Splice("anchor, alias or tag on the value")
        if knode is not None and e <= knode.end_mark.index:
            raise _Splice("value reached through an alias")
        new = render_scalar(op.value, target.style, in_flow)
        return text[:s] + new + text[e:]
    # a new key in an existing mapping
    if not isinstance(node, MappingNode) or isinstance(last, int):
        raise _Splice("cannot add here")
    if isinstance(op.value, (dict, list, tuple)) or not node.value:
        raise _Splice("not a scalar key")
    klast, vlast = node.value[-1]
    end = _leaf_end(vlast)
    if end <= klast.end_mark.index:
        raise _Splice("last value reached through an alias")
    key_txt = render_scalar(str(last), None, in_flow=True) if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", str(last)) else str(last)
    val = render_scalar(op.value, None, in_flow)
    if node.flow_style:
        return text[:end] + f", {key_txt}: {val}" + text[end:]
    col = node.value[0][0].start_mark.column
    eol = text.find("\n", end)
    eol = len(text) if eol < 0 else eol
    if eol > 0 and text[eol - 1] == "\r":
        eol -= 1
    return text[:eol] + nl + " " * col + f"{key_txt}: {val}" + text[eol:]


def splice(text: str, ops: list[Op]) -> str:
    for op in ops:
        text = _splice_one(text, op)
    return text


# ---------------------------------------------------------------- the round trip

def roundtrip_yaml(text: str):
    """A ruamel YAML configured to write the file back the way it is indented and wrapped: the indentation, the
    sequence offset and the wrap width that reproduce the unedited file with the fewest changed lines."""
    from ruamel.yaml import YAML

    def make(ind: int, off: int, width: int):
        y = YAML()
        y.preserve_quotes = True
        y.width = width
        y.indent(mapping=ind, sequence=off + 2, offset=off)
        return y

    def score(y) -> int:
        try:
            out = _dump(y, y.load(text), text)
        except Exception:
            return 10 ** 9
        a, b = out.splitlines(), text.splitlines()
        return sum(1 for x, z in zip(a, b) if x != z) + abs(len(a) - len(b))

    best = (10 ** 9, 2, 2)
    for ind in (2, 4, 3):
        for off in (2, 0, 1, 4):
            if off + 2 > ind + 4:
                continue
            sc = score(make(ind, off, 4096))
            if sc < best[0]:
                best = (sc, ind, off)
    _, ind, off = best
    wbest = (score(make(ind, off, 4096)), 4096)
    for width in (80, 90, 100, 110, 120, 130):
        sc = score(make(ind, off, width))
        if sc < wbest[0]:
            wbest = (sc, width)
    return make(ind, off, wbest[1])


def _dump(y, doc, original: str) -> str:
    from ...brand import _pad_braces as pad_braces
    buf = io.StringIO()
    y.dump(doc, buf)
    out = buf.getvalue()
    if "{ " in original:
        out = pad_braces(out)
    return out.replace("\n", "\r\n") if "\r\n" in original else out


def _to_commented(value: Any):
    from ruamel.yaml.comments import CommentedMap, CommentedSeq
    if isinstance(value, dict):
        m = CommentedMap()
        for k, v in value.items():
            m[k] = _to_commented(v)
        return m
    if isinstance(value, (list, tuple)):
        s = CommentedSeq(_to_commented(v) for v in value)
        return s
    return value


def roundtrip(text: str, ops: list[Op]) -> str:
    from ruamel.yaml.scalarstring import FoldedScalarString, LiteralScalarString
    y = roundtrip_yaml(text)
    doc = y.load(text)
    for op in ops:
        node = doc
        for p in op.path[:-1]:
            node = node[p]
        k = op.path[-1]
        if op.delete:
            if k in node:
                del node[k]
            continue
        value = _to_commented(op.value)
        old = node[k] if (isinstance(node, dict) and k in node) or (isinstance(node, list) and isinstance(k, int)) else None
        if isinstance(old, (LiteralScalarString, FoldedScalarString)) and isinstance(value, str):
            value = type(old)(value)
        node[k] = value
    return _dump(y, doc, text)


# ---------------------------------------------------------------- applying edits

def apply_ops(text: str, ops: list[Op]) -> str:
    """The text with the edits made: spliced if possible, else round-tripped; verified against the plain meaning."""
    if not ops:
        return text
    try:
        before = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise SpecError([{"loc": "site.yaml", "msg": f"the file is not valid YAML now: {e}"}])
    try:
        want = _apply_plain(before, ops)
    except _Splice as e:
        raise SpecError([{"loc": dotted(ops[0].path), "msg": f"cannot edit here: {e}"}])
    new = None
    try:
        new = splice(text, ops)
        if (yaml.safe_load(new) or {}) != want:
            new = None
    except (_Splice, yaml.YAMLError, Exception):
        new = None
    if new is None:
        try:
            new = roundtrip(text, ops)
            if (yaml.safe_load(new) or {}) != want:
                raise SpecError([{"loc": dotted(ops[0].path), "msg": "the edit could not be written back faithfully"}])
        except SpecError:
            raise
        except Exception as e:
            raise SpecError([{"loc": dotted(ops[0].path), "msg": f"the edit could not be written: {e}"}])
    return new


def validate(text: str) -> Site:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SpecError([{"loc": "site.yaml", "msg": str(e)}])
    from pydantic import ValidationError
    try:
        return Site.model_validate(data)
    except ValidationError as e:
        raise SpecError([{"loc": ".".join(str(x) for x in er["loc"]), "msg": er["msg"]} for er in e.errors()])


# ---------------------------------------------------------------- history and saving

def history_dir(project: Project) -> Path:
    return project.root / "storyboard" / "history"


def _write(project: Project, text: str) -> None:
    raw = text.encode("utf-8")
    tmp = project.spec_path.with_suffix(".yaml.tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, project.spec_path)
    _REV_CACHE.pop(str(project.spec_path), None)


def _remember(project: Project, old_text: str, new_text: str, label: str) -> str:
    d = history_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    name = f"site-{stamp}.yaml"
    (d / name).write_bytes(old_text.encode("utf-8"))
    (d / "last.json").write_text(json.dumps({"file": name, "wrote": rev_of(new_text), "label": label, "time": stamp}),
                                 encoding="utf-8")
    olds = sorted(d.glob("site-*.yaml"))
    for f in olds[:-KEEP_HISTORY]:
        f.unlink(missing_ok=True)
    return name


def save(project: Project, ops: list[Op], expect: Optional[dict] = None, label: str = "") -> dict:
    """Apply edits to site.yaml. `expect`: {path tuple: the raw value the caller last saw}; a mismatch on disk raises
    Conflict (nothing is written). An edit that would make the spec invalid raises SpecError (nothing is written).
    Returns {"changed": bool, "rev": new revision, "history": backup file name}."""
    with lock(project):
        text = read_text(project)
        if expect:
            cur = yaml.safe_load(text) or {}
            bad = []
            for path, old in expect.items():
                now = get(cur, path)
                now = None if now is MISSING else now
                if now != old:
                    bad.append(dotted(path))
            if bad:
                raise Conflict(bad)
        new = apply_ops(text, ops)
        validate(new)
        if new == text:
            return {"changed": False, "rev": rev_of(text), "history": None}
        hist = _remember(project, text, new, label)
        _write(project, new)
        WRITTEN.append(rev_of(new))
        del WRITTEN[:-50]
        return {"changed": True, "rev": rev_of(new), "history": hist}


def can_undo(project: Project) -> Optional[dict]:
    p = history_dir(project) / "last.json"
    if not p.exists():
        return None
    try:
        last = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if not (history_dir(project) / last["file"]).exists() or last.get("wrote") != current_rev(project):
        return None
    return last


def undo(project: Project) -> dict:
    """Put back the text before the last save made here, provided the file has not changed since."""
    with lock(project):
        last = can_undo(project)
        if not last:
            raise BuildError("nothing to undo (site.yaml has changed since the last save made here)")
        old = (history_dir(project) / last["file"]).read_bytes().decode("utf-8")
        _write(project, old)
        WRITTEN.append(rev_of(old))
        (history_dir(project) / last["file"]).unlink(missing_ok=True)
        (history_dir(project) / "last.json").unlink(missing_ok=True)
        return {"rev": rev_of(old), "label": last.get("label", "")}


def save_text(project: Project, new: str, label: str = "") -> dict:
    """Write a whole new site.yaml text that a caller composed itself (validated first, the old text kept in history like
    any save; `studio directions --pick` lays its theme out as a readable block this way)."""
    with lock(project):
        text = read_text(project)
        validate(new)
        if new == text:
            return {"changed": False, "rev": rev_of(text), "history": None}
        hist = _remember(project, text, new, label)
        _write(project, new)
        WRITTEN.append(rev_of(new))
        del WRITTEN[:-50]
        return {"changed": True, "rev": rev_of(new), "history": hist}
