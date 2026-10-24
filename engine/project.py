"""A project is a folder: site.yaml + inputs/ + .build/ (cache) + dist/ (the finished static site).

Builders run as named stages. A stage is skipped when its key (inputs + params) is unchanged and its
outputs exist, so editing one section's copy never re-renders another section's film.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from .config import settings
from .spec import Site


class BuildError(RuntimeError):
    pass


_BAD_NAME_CHARS = frozenset("/\\:*?\"<>|\x00")
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}")


def safe_name(name: str, what: str = "name") -> str:
    """A single file or folder name that can be joined onto a folder without leaving it: letters, digits, `_`, `-` and
    inner dots; no separators, no leading dot, no `..`. Raises ValueError saying what to change."""
    if not isinstance(name, str) or not _NAME.fullmatch(name) or ".." in name:
        raise ValueError(f"{what} {name!r} is not allowed: use letters, digits, '-' and '_' only (at most 100 characters)")
    return name


def child(base: str | Path, name: str, what: str = "name") -> Path:
    """`base/name` for a name that comes from a request, a spec or an AI client: exactly one path component. Folders
    people already made (spaces and all) still work; separators, `..`, drive letters and hidden names do not."""
    if (not isinstance(name, str) or not name or name in (".", "..") or name.startswith(".") or name != name.strip()
            or any(c in _BAD_NAME_CHARS for c in name)):
        raise ValueError(f"{what} {name!r} is not allowed: it must be a plain folder or file name, with no slashes, '..' "
                         "or leading dot")
    return within(base, name)


def within(base: str | Path, rel: str) -> Path:
    """`base/rel` normalised, refused with ValueError unless it stays inside `base`. Lexical only: a caller that must
    follow links resolves the result and checks again. Written as normpath plus a prefix test, the guard static
    analysis (CodeQL) recognises."""
    root = os.path.normpath(os.fspath(base))
    full = os.path.normpath(os.path.join(root, rel))
    if full == root:
        return Path(full)
    if not full.startswith(root.rstrip(os.sep) + os.sep):
        raise ValueError(f"{rel!r} is outside {root}")
    return Path(full)


def file_key(path: Path) -> dict:
    """Cheap content key for an input file (size + mtime); stages hash this with their params."""
    st = path.stat()
    return {"path": path.name, "size": st.st_size, "mtime": int(st.st_mtime)}


def _hash(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


class Project:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.spec_path = self.root / "site.yaml"
        self.inputs = self.root / "inputs"
        self.build = self.root / ".build"
        self.dist = self.root / "dist"

    @property
    def name(self) -> str:
        return self.root.name

    def exists(self) -> bool:
        return self.spec_path.exists()

    def raw(self) -> dict:
        with open(self.spec_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def load(self) -> Site:
        return Site.model_validate(self.raw())

    def save(self, data: dict | Site) -> None:
        if isinstance(data, Site):
            data = data.model_dump(mode="json", exclude_defaults=True)
        Site.model_validate(data)      # never write an invalid spec
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.spec_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=110)

    def path(self, rel: str) -> Path:
        """A path named in the spec, resolved (links followed) and required to stay inside the project folder. An
        absolute path, `..` or a symlink pointing out is refused: a spec is a document that may come from anyone."""
        outside = BuildError(f"{rel} is outside the project folder: use a file inside it (e.g. inputs/photo.jpg), "
                             "not an absolute path, `..` or a link that leads out")
        if "\x00" in str(rel):
            raise BuildError(f"{rel!r} is not a usable path (embedded null character); use a file inside the project "
                             "folder, e.g. inputs/photo.jpg")
        try:
            lexical = within(self.root, str(rel))          # `..` and absolute paths, before touching the disk
        except ValueError:
            raise outside from None
        try:
            p = lexical.resolve()                          # then links: one pointing out is refused below
        except (OSError, ValueError, RuntimeError) as e:     # loops, names the OS refuses
            raise BuildError(f"{rel!r} is not a usable path ({e.__class__.__name__}); use a file inside the project folder, "
                             "e.g. inputs/photo.jpg") from e
        if p != self.root and not p.is_relative_to(self.root):
            raise BuildError(f"{rel} is outside the project folder: use a file inside it (e.g. inputs/photo.jpg), "
                             "not an absolute path, `..` or a link that leads out")
        return p


Log = Callable[[str], None]
Progress = Callable[[float, str], None]


@dataclass
class BuildContext:
    project: Project
    section_id: str
    log: Log = print
    progress: Progress = lambda f, msg="": None
    force: bool = False
    options: dict = field(default_factory=dict)      # CLI/UI knobs: draft quality, only=stage, plan=Plan, ...
    locked: bool = False                              # the section (or its take) is locked: keep what is rendered

    @property
    def work(self) -> Path:
        d = self.project.build / self.section_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def web(self) -> Path:
        """Web-ready files for this section; copied to dist/assets/<section>/."""
        d = self.work / "web"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def url(self, path: Path) -> str:
        return f"assets/{self.section_id}/{path.relative_to(self.web).as_posix()}"

    def status(self, name: str, key: Any, outputs: list[Path], legacy: Any = None, locked: Optional[bool] = None) -> str:
        """What stage() would do: 'fresh' (stamp matches), 'migrated' (stamp of the legacy key), 'locked' (outputs
        kept although the key changed) or 'stale' (it would run). Nothing is written."""
        locked = self.locked if locked is None else locked
        have = all(p.exists() for p in outputs)
        stamp = self.work / "stamps" / f"{name}.json"
        old = json.loads(stamp.read_text()) if stamp.exists() else None
        if not self.force and old and have:
            if old.get("key") == _hash(key):
                plan = self.options.get("plan")
                return "stale" if plan is not None and plan.depends_on_dirty(key) else "fresh"
            if legacy is not None and old.get("key") == _hash(legacy):
                return "migrated"
        if locked and have:
            return "locked"
        return "stale"

    def adopt(self, name: str, key: Any) -> None:
        """Record that the outputs on disk are what `key` makes, without running the stage (the storyboard's edit
        workspace puts a chosen variant in place, so the build keeps it)."""
        stamp = self.work / "stamps" / f"{name}.json"
        prior = json.loads(stamp.read_text()) if stamp.exists() else {}
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(json.dumps({**prior, "key": _hash(key)}))

    def stage(self, name: str, key: Any, outputs: list[Path], fn: Callable[[], Any], legacy: Any = None,
              locked: Optional[bool] = None) -> bool:
        """Run fn unless the stamp matches key and every output exists. Returns True if it ran.

        legacy: the key this stage had under an older formula. A stamp written with it still counts (and is
        rewritten with the new key), so changing how a key is computed never re-renders finished work.
        locked: keep existing outputs even when the key changed (default: the context's `locked`, set from the
        section's or take's `locked: true`). With options["plan"] (engine/plan.py) nothing runs: a stage that would
        run is recorded instead."""
        stamp = self.work / "stamps" / f"{name}.json"
        digest = _hash(key)
        plan = self.options.get("plan")
        state = self.status(name, key, outputs, legacy, locked)
        prior = json.loads(stamp.read_text()) if stamp.exists() else {}
        if plan is not None:
            plan.record(self.section_id, name, state, prior.get("seconds"), outputs)
        if state == "fresh":
            self.log(f"  {name}: up to date")
            return False
        if state == "migrated":
            if plan is None:
                stamp.write_text(json.dumps({**prior, "key": digest}))
            self.log(f"  {name}: up to date (cache key migrated)")
            return False
        if state == "locked":
            self.log(f"  {name}: locked, kept the existing render (its settings changed; set locked: false to redo it)")
            return False
        if plan is not None:
            self.log(f"  {name}: would run")
            return True
        self.log(f"  {name}: running")
        t0 = time.time()
        fn()
        missing = [str(p) for p in outputs if not p.exists()]
        if missing:
            raise BuildError(f"stage {name} did not produce {missing}")
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(json.dumps({"key": digest, "seconds": round(time.time() - t0, 1)}))
        self.log(f"  {name}: done in {time.time() - t0:.1f}s")
        return True


# ---------------------------------------------------------------- shared tool helpers

def run(cmd: list, log: Optional[Log] = None, cwd: Optional[Path] = None) -> str:
    cmd = [str(c) for c in cmd]
    if log:
        log("  $ " + " ".join(cmd)[:300])
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        tail = (p.stderr or p.stdout)[-2000:]
        raise BuildError(f"{Path(cmd[0]).name} failed ({p.returncode}):\n{tail}")
    return p.stdout


def ffmpeg(*args, log: Optional[Log] = None) -> None:
    run([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", *args], log)


def probe(path: Path, entries: str = "stream=width,height,r_frame_rate:format=duration") -> dict:
    out = run([settings()["ffprobe"], "-v", "error", "-select_streams", "v:0", "-show_entries", entries,
               "-of", "json", path])
    data = json.loads(out)
    s = (data.get("streams") or [{}])[0]
    return {**s, **data.get("format", {})}


def copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
