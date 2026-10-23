"""What image a node shows now: its cached render (looked up the way the build looks it up), a keyframe's file, a project
file; and small JPEG thumbnails of any of them for the page."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...fidelity import WouldRender, planning
from ...project import BuildContext, BuildError, Project
from .shots import Node

_QUIET = lambda m: None
_LOCK = threading.Lock()


@dataclass
class Probe:
    state: str                       # current | missing | file | error
    path: Optional[Path] = None
    cache: str = ""                  # identifies the image: its path relative to the project, or kf:<digest>
    error: str = ""


def rel(project: Project, p: Path) -> str:
    try:
        return p.resolve().relative_to(project.root).as_posix()
    except ValueError:
        return str(p)


def keyframe_ident(shot: dict, bkey: dict, name: str) -> str:
    """Identifies a keyframe's image for the variant store: the world it is painted over and its *effective* recipe, so
    a seed written explicitly (equal to the shared default) is still the same image."""
    kf = shot["keyframes"]
    fr = next(f for f in kf["frames"] if f["name"] == name)
    eff = dict(fr, seed=fr.get("seed", kf.get("seed", 7)), control_strength=fr.get("control_strength", kf.get("control_strength", 0.8)))
    common = {k: v for k, v in kf.items() if k not in ("frames", "seed", "control_strength")}
    return hashlib.sha1(json.dumps({"b": bkey, "c": common, "f": eff}, sort_keys=True, default=str).encode()).hexdigest()[:16]


def keyframe_info(project: Project, site, node: Node) -> tuple[Optional[str], Path, bool]:
    """(identity of the keyframe's recipe now, its file, whether the stage has painted exactly that). The identity is
    None when the world it is painted over cannot be keyed without rendering something."""
    from ...scenes import film
    sec = site.sections[node.extra["section_index"]]
    name = node.extra["frame"]
    ctx = BuildContext(project, sec.id, log=_QUIET, options={"site_video_model": site.video_model})
    png = ctx.work / "keyframes" / f"{name}.png"
    try:
        with planning():
            shot, bkey, _legacy = film.blockout_key(sec, ctx)
    except (WouldRender, BuildError, KeyError, OSError):
        return None, png, False
    digest = film.keyframe_digests(shot, bkey, 1, ctx.work).get(name)
    ident = keyframe_ident(shot, bkey, name) if digest else None
    rec = ctx.work / "keyframes" / "_frames.json"
    try:
        recorded = json.loads(rec.read_text()) if rec.exists() else {}
    except ValueError:
        recorded = {}
    return ident, png, bool(digest and png.exists() and recorded.get(name) == digest)


def probe(project: Project, site, node: Node) -> Probe:
    if node.kind == "keyframe":
        digest, png, fresh = keyframe_info(project, site, node)
        if fresh:
            return Probe("current", png, f"kf:{digest}")
        return Probe("missing")
    from ...inputs import resolve_image
    try:
        with planning():
            p = resolve_image(project, node.ref, _QUIET, alpha=node.alpha)
    except WouldRender:
        return Probe("missing")
    except (BuildError, OSError) as e:
        return Probe("error", error=str(e).splitlines()[0][:200])
    except Exception as e:          # a ref that cannot be keyed (e.g. a section the planner cannot read)
        return Probe("error", error=f"{type(e).__name__}: {str(e)[:160]}")
    if node.kind == "file":
        return Probe("file", p, rel(project, p))
    return Probe("current", p, rel(project, p))


def thumb(project: Project, path: Path, width: int = 640) -> Optional[Path]:
    """A JPEG of an image under storyboard/variants/_thumbs/ (made once per file version); alpha sits on a dark panel."""
    try:
        st = path.stat()
    except OSError:
        return None
    key = hashlib.sha1(json.dumps([str(path), st.st_size, int(st.st_mtime), width]).encode()).hexdigest()[:16]
    out = project.root / "storyboard" / "variants" / "_thumbs" / f"{key}.jpg"
    if out.exists():
        return out
    with _LOCK:
        if out.exists():
            return out
        from PIL import Image
        out.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(path)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            flat = Image.new("RGBA", im.size, (40, 42, 47, 255))
            flat.alpha_composite(im)
            im = flat
        im = im.convert("RGB")
        size = im.size
        im.thumbnail((width, width), Image.LANCZOS)
        tmp = out.with_suffix(".tmp.jpg")
        im.save(tmp, quality=84)
        tmp.replace(out)
        (out.with_suffix(".json")).write_text(json.dumps({"w": size[0], "h": size[1]}))
    return out


def size_of(project: Project, path: Path) -> Optional[tuple[int, int]]:
    t = thumb(project, path)
    if t is None:
        return None
    try:
        d = json.loads(t.with_suffix(".json").read_text())
        return d["w"], d["h"]
    except (OSError, ValueError, KeyError):
        return None
