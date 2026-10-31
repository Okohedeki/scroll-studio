"""A project is a folder: project.yaml (or the older site.yaml) + inputs/ + .build/ (cache) + dist/ (the finished site).

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
from .project_spec import (PROJECT_FILE, SITE_FILE, ProjectFileError, ProjectSpec, is_site_shaped, project_dict,
                           site_dict)
from .project_spec import validate as validate_project
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


def has_spec(folder: str | Path) -> bool:
    """A project folder: it holds a project.yaml or a site.yaml."""
    return (Path(folder) / PROJECT_FILE).exists() or (Path(folder) / SITE_FILE).exists()


class Project:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.inputs = self.root / "inputs"
        self.build = self.root / ".build"
        self.dist = self.root / "dist"

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def spec_path(self) -> Path:
        """project.yaml when there is one, else site.yaml (engine/project_spec.py)."""
        p = self.root / PROJECT_FILE
        return p if p.exists() else self.root / SITE_FILE

    @property
    def is_project_file(self) -> bool:
        return self.spec_path.name == PROJECT_FILE

    def exists(self) -> bool:
        return self.spec_path.exists()

    def _file(self) -> dict:
        with open(self.spec_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def raw(self) -> dict:
        """The site the project builds, as a site.yaml document (a project file's shared fields folded in)."""
        data = self._file()
        if not self.is_project_file:
            return data
        try:
            return site_dict(data)
        except ProjectFileError as e:
            raise BuildError(str(e)) from None

    def load(self) -> Site:
        if self.is_project_file:
            ProjectSpec.model_validate(self._file())     # what only a project has (its brief) is checked too
        site = Site.model_validate(self.raw())
        if isinstance(site.theme.from_, str):      # a brand source: its tokens, read once and kept in .build/brand/
            from .brand import brand_from
            site.theme._brand = brand_from(self, site.theme.from_)
        return site

    def load_project(self) -> ProjectSpec:
        """The whole project: a site.yaml is read as a project whose one output is that site."""
        return validate_project(self._file())

    def save(self, data: dict | Site) -> None:
        if isinstance(data, Site):
            data = data.model_dump(mode="json", exclude_defaults=True)
        Site.model_validate(data)      # never write an invalid spec
        self.root.mkdir(parents=True, exist_ok=True)
        if self.is_project_file:
            data = project_dict(data, keep=self._file())
        with open(self.spec_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=110)

    def site_text(self) -> str:
        """The site as site.yaml text, for the tools that edit it as text. A site.yaml is returned as written; a
        project file's site is laid out afresh (its comments are not kept)."""
        if not self.is_project_file:
            return self.spec_path.read_text(encoding="utf-8")
        return yaml.safe_dump(self.raw(), sort_keys=False, allow_unicode=True, width=110)

    def put_text(self, text: str) -> Site:
        """Validate and write a whole spec given as text: a project file, or a site.yaml document. A site.yaml folder
        that receives a project file becomes a project (its site.yaml is kept as site.yaml.bak). Returns the site;
        raises yaml.YAMLError, pydantic's ValidationError or BuildError."""
        data = yaml.safe_load(text) or {}
        if is_site_shaped(data):
            site = Site.model_validate(data)
            self.write_site_text(text)
            return site
        try:
            validate_project(data)
            site = Site.model_validate(site_dict(data))
        except ProjectFileError as e:
            raise BuildError(str(e)) from None
        old = self.root / SITE_FILE
        (self.root / PROJECT_FILE).write_text(text, encoding="utf-8")
        if old.exists():
            os.replace(old, old.with_name(SITE_FILE + ".bak"))
        return site

    def write_site_text(self, text: str) -> None:
        """Write site.yaml text back: as is to a site.yaml, or split into the project file (what only the project
        has is kept). The caller has validated it."""
        if not self.is_project_file:
            self.spec_path.write_text(text, encoding="utf-8")
            return
        data = project_dict(yaml.safe_load(text) or {}, keep=self._file())
        tmp = self.spec_path.with_suffix(".yaml.tmp")
        tmp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
        os.replace(tmp, self.spec_path)

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
        run is recorded instead. With options["profile"] (a list, engine/profile.py) each stage appends what it did
        and how long it took."""
        stamp = self.work / "stamps" / f"{name}.json"
        digest = _hash(key)
        plan = self.options.get("plan")
        state = self.status(name, key, outputs, legacy, locked)
        prior = json.loads(stamp.read_text()) if stamp.exists() else {}
        if plan is not None:
            plan.record(self.section_id, name, state, prior.get("seconds"), outputs)
        prof = self.options.get("profile")
        if prof is not None and (plan is not None or state != "stale"):
            prof.append({"section": self.section_id, "stage": name, "state": state, "seconds": 0.0})
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
        seconds = round(time.time() - t0, 1)
        stamp.write_text(json.dumps({"key": digest, "seconds": seconds}))
        if prof is not None:
            prof.append({"section": self.section_id, "stage": name, "state": "ran", "seconds": seconds})
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
