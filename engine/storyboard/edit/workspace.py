"""The edit workspace of one project: what the page and the MCP tools drive.

  state()      everything the page shows (shots, fields, images, variants, shared steps, jobs)
  save()       field edits -> site.yaml (spliced in place, validated first, previous text kept)
  start()      an image job: Regenerate (a new seed) or Re-run (same seed, after editing text), in the background
  pick() / revert()   make a kept variant current
  approve()    the storyboard-only approval (state.json)

Rendering shares ComfyUI (127.0.0.1:8188) with whatever else is queued on it: nothing here stops, restarts or
interrupts it, and an image's job is the only thing this module ever queues for it.
"""
from __future__ import annotations

import contextlib
import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Optional

from ...project import BuildError, Project
from ...region import outline_of
from ...server.jobs import Job, JobQueue, logger
from . import approvals, images, notes, render, shots, specdoc, variants
from .shots import Board, Fld, Node

PAGE_LEVEL = "sketch"      # the sheet is rebuilt from what is cached: renders happen per image, on their own buttons


class _ToLog:
    """Stand-in for stdout while a job runs, so what comfy.run prints ("done in 14s") lands in the job's log."""
    def __init__(self, log):
        self.log, self.buf = log, ""

    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip():
                self.log(line)
        return len(s)

    def flush(self):
        pass


def coerce(f: Fld, value: Any) -> Any:
    """A value from the page or an agent, as the field's YAML type. Raises ValueError with a sentence for the card."""
    t = f.type
    if t == "bool":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if t in ("int", "float"):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        try:
            x = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{f.label}: '{value}' is not a number")
        if t == "int":
            if x != int(x):
                raise ValueError(f"{f.label}: must be a whole number")
            return int(x)
        return int(x) if x == int(x) and abs(x) < 1e9 else x
    if value is None:
        return "" if f.raw is None else None
    v = str(value)
    if "\n" not in str(f.raw or ""):
        import re
        v = re.sub(r"\s*\n\s*", " ", v).strip()
    return v


class Workspace:
    def __init__(self, project: Project, jobs: Optional[JobQueue] = None):
        self.project = project
        self.jobs = jobs
        self.active: dict[str, Job] = {}
        self.last: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._busy_cache: set = set()
        self._comfy: tuple[float, bool] = (0.0, False)

    # ------------------------------------------------------------ reading
    def comfy_alive(self) -> bool:
        """Whether ComfyUI answers (checked in the background with a short timeout: a ComfyUI busy loading a model must
        not make the page wait)."""
        t, v = self._comfy
        if time.time() - t >= 5 and not getattr(self, "_checking", False):
            self._checking = True

            def check():
                import urllib.request
                ok = False
                try:
                    from ...config import settings
                    with urllib.request.urlopen(settings()["comfy_url"] + "/system_stats", timeout=2.5) as r:
                        ok = r.status == 200
                except Exception:
                    ok = False
                self._comfy = (time.time(), ok)
                self._checking = False
            threading.Thread(target=check, daemon=True).start()
            if t == 0.0:
                time.sleep(0.4)
                return self._comfy[1]
        return v

    @staticmethod
    def _comfy_url() -> str:
        from ...config import settings
        return settings()["comfy_url"]

    def _comfy_now(self) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(self._comfy_url() + "/system_stats", timeout=6) as r:
                return r.status == 200
        except Exception:
            return False

    def job_json(self, key: str) -> Optional[dict]:
        j = self.active.get(key)
        if j is not None:
            d = j.public(tail=3)
            d["elapsed"] = round(time.time() - j.created, 1)
            return d
        return self.last.get(key)

    def poll(self) -> dict:
        """Cheap: what changed since the page last looked (the spec's revision, running jobs, ComfyUI)."""
        jobs = {k: self.job_json(k) for k in list(self.active)}
        rev = specdoc.current_rev(self.project)
        for key in self.busy_elsewhere():
            jobs.setdefault(key, {"status": "running", "progress": 0.1, "message": "being rendered by another session "
                                  "(an agent or a second editor)", "external": True, "log": []})
        return {"rev": rev, "vrev": self.vrev(), "own": rev in specdoc.WRITTEN, "jobs": jobs, "comfy": self.comfy_alive(),
                "last": {k: v for k, v in self.last.items() if k not in self.active and time.time() - v.get("finished", 0) < 900},
                "undo": bool(specdoc.can_undo(self.project))}

    def vrev(self) -> str:
        """Changes when a variant is added or picked, a note is written or an approval is made, by anyone (another
        process included): the page then reloads its cards."""
        vs = self.project.root / "storyboard" / "variants"
        m = 0.0
        try:
            for f in vs.glob("*/*/index.json"):
                m = max(m, f.stat().st_mtime)
        except OSError:
            pass
        sp = approvals.path(self.project)
        m = max(m, notes.mtime(self.project), sp.stat().st_mtime if sp.exists() else 0.0)
        try:                                           # a polish report written by `studio inspect` elsewhere
            for f in (self.project.build / "inspect").glob("*.json"):
                m = max(m, f.stat().st_mtime)
        except OSError:
            pass
        return f"{m:.3f}"

    def busy_elsewhere(self) -> list[str]:
        out = []
        vs = self.project.root / "storyboard" / "variants"
        try:
            for f in vs.glob("*/*/.busy"):
                key = f.parent.relative_to(vs).as_posix()
                if key not in self.active and variants.busy(self.project, key):
                    out.append(key)
        except OSError:
            pass
        return out

    def _img(self, p: Path) -> dict:
        try:
            v = int(p.stat().st_mtime)
        except OSError:
            v = 0
        return {"p": images.rel(self.project, p), "v": v}

    def node_json(self, board: Board, node: Node, probes: dict, outer: bool) -> dict:
        project = self.project
        pr = probes.get(node.key + "|" + node.sig)
        if pr is None:
            pr = probes[node.key + "|" + node.sig] = images.probe(project, board.site, node)
        data: dict = {"variants": [], "history": []}
        regenerable = node.kind != "file"
        if regenerable:
            if pr.state == "current" and pr.path is not None:
                with contextlib.suppress(Exception):
                    variants.register(project, node.key, pr.path, pr.cache, node.recipe(), "original",
                                      seed=node.recipe().get("seed"))
            data = variants.load(project, node.key)
        img: dict = {"state": pr.state, "error": pr.error}
        if pr.path is not None and pr.state in ("current", "file"):
            img |= self._img(pr.path)
            ol = outline_of(pr.path) if node.kind == "edit" else None     # an edit inside a region: its outline
            if ol is not None:
                img["region"] = self._img(ol)
        elif data["variants"]:
            last = data["variants"][-1]
            img |= {"state": "stale"} | self._img(variants.file_of(project, node.key, last))
        vs = []
        for v in reversed(data["variants"]):
            f = variants.file_of(project, node.key, v)
            vs.append({"n": v["n"], "seed": v.get("seed"), "origin": v.get("origin"), "time": v.get("time"),
                       "current": bool(pr.cache) and v.get("cache") == pr.cache, **self._img(f),
                       "recipe": {k: val for k, val in (v.get("recipe") or {}).items() if k != "seed"}})
        job = self.job_json(node.key)
        if job is None and node.key in self._busy_cache:
            job = {"status": "running", "progress": 0.1, "message": "being rendered by another session", "external": True}
        return {"key": node.key, "kind": node.kind, "label": node.label, "depth": node.depth, "summary": node.summary,
                "shared": node.shared, "used_by": node.used_by, "regen": node.regen and node.kind != "file",
                "render": regenerable, "image": img, "variants": vs,
                "can_revert": variants.revert_target(project, node.key) is not None if regenerable else False,
                "fields": [f.public() for f in node.fields if not f.hidden], "job": job,
                "est": render.estimate(node)}

    def state(self) -> dict:
        project = self.project
        board = shots.build(project)
        ap = approvals.status(project, board)
        self._busy_cache = set(self.busy_elsewhere())
        probes: dict = {}
        out_shots = []
        from ... import polish
        badges = polish.beat_badges(project)
        for s in board.shots:
            slots = []
            for sl in s.slots:
                nodes = [self.node_json(board, n, probes, i == 0) for i, n in enumerate(sl.nodes)]
                slots.append({"id": sl.id, "name": sl.name, "label": sl.label, "key": sl.key, "nodes": nodes})
            out_shots.append({"id": s.id, "section": s.section, "kind": s.kind, "title": s.title, "seconds": s.seconds,
                              "locked": s.locked, "can_lock": bool(s.lock_paths), "note": s.note, "approval": ap.get(s.id, "no"),
                              "fields": [f.public() for f in s.fields], "slots": slots,
                              "polish": (badges.get(s.id) if (badges.get(s.id) or {}).get("section") == s.section else None)})
        shared = []
        for n in board.shared:
            nj = self.node_json(board, n, probes, False)
            shared.append(nj)
        sb = project.root / "storyboard"
        approved = sum(1 for v in ap.values() if v == "approved")
        return {"project": project.name, "name": board.site.name, "rev": board.rev, "shots": out_shots, "shared": shared,
                "approved": approved, "total": len(ap), "comfy": self.comfy_alive(),
                "undo": bool(specdoc.can_undo(project)), "has_sheet": (sb / "storyboard.html").exists(),
                "notes": list(reversed(notes.all_notes(project))), "vrev": self.vrev(),
                "play": self.play_info(board),
                "has_page": (sb / "site" / "index.html").exists(), "time": time.time()}

    # ------------------------------------------------------------ editing
    def _edits_to_ops(self, board: Board, edits: list[dict]) -> tuple[list[specdoc.Op], dict, list[str], list[dict]]:
        allowed = {}
        for s in board.shots:
            for f in s.all_fields():
                for p in f.paths:
                    allowed[specdoc.dotted(p)] = (s.id, f)
        ops, expect, changed, errors = [], {}, [], []
        self._touched = {}
        for e in edits:
            ds = e.get("path") or ""
            sid, f = allowed.get(ds, (None, None))
            if f is None:
                errors.append({"loc": ds, "msg": "not an editable field of this spec (it changed? reload the page)"})
                continue
            if f.readonly:
                errors.append({"loc": ds, "msg": f"{f.label} cannot be edited here"})
                continue
            try:
                value = coerce(f, e.get("value"))
            except ValueError as ex:
                errors.append({"loc": ds, "msg": str(ex)})
                continue
            for p in f.paths:
                same = f.raw == value or (f.raw is None and value in ("", None) and f.type in ("text", "area"))
                if same:
                    continue
                ops.append(specdoc.Op(p, value, delete=value is None and f.type in ("int", "float")))
                if "old" in e:
                    expect[p] = e["old"] if p == f.paths[0] else specdoc.get(board.raw, p)
                    if expect[p] is specdoc.MISSING:
                        expect[p] = None
                changed.append(specdoc.dotted(p))
            if f.paths and any(specdoc.dotted(p) in changed for p in f.paths):
                self._touched.setdefault(sid, []).append(f.label)
        return ops, expect, changed, errors

    def save(self, edits: list[dict], base_rev: Optional[str] = None, label: str = "edit") -> dict:
        """Field edits [{path, value, old?}]. Raises specdoc.SpecError (invalid: nothing written) or specdoc.Conflict."""
        with specdoc.lock(self.project):
            board = shots.build(self.project)
            ops, expect, changed, errors = self._edits_to_ops(board, edits)
            if errors:
                raise specdoc.SpecError(errors)
            if not ops:
                return {"ok": True, "changed": [], "rev": board.rev}
            res = specdoc.save(self.project, ops, expect=expect or None, label=label)
            for sid, labels in self._touched.items():
                notes.record(self.project, sid, "edited " + ", ".join(dict.fromkeys(labels)))
            return {"ok": True, "changed": changed, "rev": res["rev"]}

    def set_fields(self, shot_id: str, values: dict[str, Any], label: str = "edit") -> dict:
        """Edit fields of one shot by name (what an agent does): {name: value}."""
        board = shots.build(self.project)
        s = board.shot(shot_id)
        if s is None:
            raise BuildError(f"no shot '{shot_id}' (shots: {', '.join(x.id for x in board.shots)})")
        edits, lock = [], None
        for name, value in values.items():
            if name == "locked":
                lock = bool(value)
                continue
            f = s.field(name)
            if f is None:
                names = sorted({g.name for g in s.all_fields()})
                raise BuildError(f"shot '{shot_id}' has no field '{name}' (fields: {', '.join(names)}, locked)")
            edits.append({"path": specdoc.dotted(f.path), "value": value})
        with specdoc.lock(self.project):
            res = self.save(edits, label=label) if edits else {"ok": True, "changed": [], "rev": board.rev}
            if lock is not None:
                if lock and not s.lock_paths:
                    raise BuildError(f"'{shot_id}' cannot be locked (only scenes, beats and takes can)")
                ops = board.lock_ops(s, lock)
                if ops:
                    r2 = specdoc.save(self.project, ops, label=f"{'lock' if lock else 'unlock'} {shot_id}")
                    notes.record(self.project, shot_id, "locked" if lock else "unlocked")
                    res = {"ok": True, "changed": res["changed"] + [specdoc.dotted(o.path) for o in ops], "rev": r2["rev"]}
        return res

    def set_lock(self, shot_id: str, locked: bool) -> dict:
        return self.set_fields(shot_id, {"locked": locked})

    def undo(self) -> dict:
        return specdoc.undo(self.project)

    def approve(self, shot_id: str, approved: bool) -> str:
        board = shots.build(self.project)
        return approvals.set_approved(self.project, board, shot_id, approved)

    # ------------------------------------------------------------ images
    def resolve_key(self, shot_id: str, slot: Optional[str] = None, node: Optional[int] = None) -> str:
        """The variant key of a shot's image: its first slot (or the named one), or the n-th node of its chain."""
        board = shots.build(self.project)
        s = board.shot(shot_id)
        if s is None:
            raise BuildError(f"no shot '{shot_id}' (shots: {', '.join(x.id for x in board.shots)})")
        if not s.slots:
            raise BuildError(f"'{shot_id}' shows no generated image ({s.note or s.kind})")
        sl = next((x for x in s.slots if x.name == slot), None) if slot else s.slots[0]
        if sl is None:
            raise BuildError(f"shot '{shot_id}' has no image '{slot}' (images: {', '.join(x.name for x in s.slots)})")
        return sl.nodes[min(node or 0, len(sl.nodes) - 1)].key

    def start(self, key: str, mode: str, seed: Optional[int] = None) -> Job:
        """Queue an image job (a worker thread; ComfyUI is shared, so jobs run one at a time)."""
        if self.jobs is None:
            raise BuildError("this workspace has no job queue")
        with self._lock:
            if key in self.active:
                raise variants.Busy(f"{key} is already being rendered")
            board = shots.build(self.project)
            hit = board.node(key)
            if hit is None:
                raise BuildError(f"no image '{key}' in this spec")
            node, shot, _ = hit
            render._guard(node, shot)
            if mode == "regenerate" and not node.regen:
                raise BuildError("this image has no seed to change; edit its text and use Re-run")
            if node.kind in ("generate", "edit", "keyframe") or (node.kind == "product" and node.regen):
                if not self._comfy_now():
                    raise BuildError("ComfyUI is not answering at " + self._comfy_url() + " (not running, or busy loading a "
                                     "model). Nothing was started; try again in a moment.")
            lock = variants.claim(self.project, key, mode)
            label = f"{'Regenerate' if mode == 'regenerate' else 'Re-run'} {key}"
            est = render.estimate(node)

            def run(job: Job):
                log, progress = logger(job)

                def say(m):
                    log(m)
                    job.message = str(m).strip()[:140] or job.message
                stop = threading.Event()

                def tick():
                    t0 = time.time()
                    while not stop.wait(0.5):
                        job.progress = max(job.progress, min(0.93, 0.05 + 0.88 * (1 - math.exp(-(time.time() - t0) / est))))
                threading.Thread(target=tick, daemon=True).start()
                try:
                    with contextlib.redirect_stdout(_ToLog(say)):
                        res = render.run_image(self.project, key, mode, seed, say, progress)
                    self.last[key] = {"status": "done", "message": "unchanged: already rendered" if res["unchanged"] else
                                      (f"new image, seed {res['seed']}" if res.get("seed") is not None else "new image"),
                                      "note": res["note"], "finished": time.time()}
                    return res
                except Exception as e:
                    self.last[key] = {"status": "failed", "error": str(e).splitlines()[0][:300] if str(e) else type(e).__name__,
                                      "finished": time.time()}
                    raise
                finally:
                    stop.set()
                    variants.release(lock)
                    self.active.pop(key, None)
            try:
                job = self.jobs.submit("image", self.project.name, label, run)
            except Exception:
                variants.release(lock)
                raise
            self.active[key] = job
            self.last.pop(key, None)
            return job

    def run_blocking(self, key: str, mode: str, seed: Optional[int] = None, log=print) -> dict:
        """Render one image in the calling thread (the MCP tool inside its own job)."""
        lock = variants.claim(self.project, key, mode)
        try:
            return render.run_image(self.project, key, mode, seed, log)
        finally:
            variants.release(lock)

    def pick(self, key: str, n: int) -> dict:
        lock = variants.claim(self.project, key, "pick")
        try:
            return render.pick(self.project, key, n)
        finally:
            variants.release(lock)

    def revert(self, key: str) -> dict:
        lock = variants.claim(self.project, key, "revert")
        try:
            return render.revert(self.project, key)
        finally:
            variants.release(lock)

    def sheet(self) -> Job:
        """Rebuild the storyboard sheet and stand-in page from the (now edited) spec: `studio storyboard` as a job."""
        if self.jobs is None:
            raise BuildError("this workspace has no job queue")
        key = "__sheet__"
        with self._lock:
            if key in self.active:
                raise variants.Busy("the sheet is already being rebuilt")

            def run(job: Job):
                from .. import storyboard as run_sb
                log, progress = logger(job)
                try:
                    with contextlib.redirect_stdout(_ToLog(log)):
                        res = run_sb(self.project, level=PAGE_LEVEL, log=log, progress=progress)
                    self.last[key] = {"status": "done", "message": f"sheet updated: {res['shots']} shots", "finished": time.time()}
                    return {k: res[k] for k in ("sheet", "html", "site", "shots", "render_estimate")}
                except Exception as e:
                    self.last[key] = {"status": "failed", "error": str(e).splitlines()[0][:300], "finished": time.time()}
                    raise
                finally:
                    self.active.pop(key, None)
            job = self.jobs.submit("storyboard", self.project.name, "Update the sheet", run)
            self.active[key] = job
            self.last.pop(key, None)
            return job

    def inspect(self) -> Job:
        """Polish report of every built film section (`studio inspect`) as a job: the beat badges follow."""
        if self.jobs is None:
            raise BuildError("this workspace has no job queue")
        key = "__inspect__"
        with self._lock:
            if key in self.active:
                raise variants.Busy("the polish check is already running")

            def run(job: Job):
                from ... import polish
                log, progress = logger(job)
                try:
                    reps = polish.inspect_project(self.project, log=log)
                    worst = max((r["summary"]["worst"]["severity"] for r in reps if r["summary"]["worst"]), default=0.0)
                    msg = (f"polish check done: {sum(r['summary']['issues'] for r in reps)} problem(s) in "
                           f"{len(reps)} film section(s)" if reps else "nothing to check: no film has been built yet")
                    self.last[key] = {"status": "done", "finished": time.time(), "message": msg}
                    return {"sections": [r["section"] for r in reps], "worst": worst}
                except Exception as e:
                    self.last[key] = {"status": "failed", "error": str(e).splitlines()[0][:300], "finished": time.time()}
                    raise
                finally:
                    self.active.pop(key, None)
            job = self.jobs.submit("inspect", self.project.name, "Polish check", run)
            self.active[key] = job
            self.last.pop(key, None)
            return job

    # ------------------------------------------------------------ notes
    def add_note(self, shot: str, text: str) -> dict:
        board = shots.build(self.project)
        if shot != notes.GENERAL and board.shot(shot) is None:
            raise BuildError(f"no shot '{shot}'")
        return notes.add(self.project, shot, text)

    def reopen_note(self, nid: str, more: str = "") -> dict:
        return notes.reopen(self.project, nid, more)

    def delete_note(self, nid: str) -> None:
        notes.delete(self.project, nid)

    # ------------------------------------------------------------ playing the whole thing
    def play_info(self, board: Optional[Board] = None) -> dict:
        """What there is to play: the animatic (with its shot markers and whether it is out of date), the stand-in page of
        stills, the real built page. Paths are relative to /sb/<project>/."""
        project = self.project
        sb = project.root / "storyboard"
        mp4 = sb / "animatic.mp4"
        spec_m = project.spec_path.stat().st_mtime if project.spec_path.exists() else 0.0
        out: dict = {"animatic": None, "standin": None, "dist": None}
        if mp4.exists():
            tl = {}
            try:
                tl = json.loads((sb / "animatic.timeline.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            a = {"url": "files/animatic.mp4", "v": int(mp4.stat().st_mtime), "duration": tl.get("duration"),
                 "shots": tl.get("shots") or [], "cut_at": tl.get("cut_at") or mp4.stat().st_mtime, "changed": [],
                 "stale": False, "reason": ""}
            try:
                board = board or shots.build(project)
            except specdoc.SpecError:
                board = None
            if board is not None:
                sigs = tl.get("sigs") or {}
                vs = sb / "variants"
                for s in board.shots:
                    newer = False       # a render made since the cut (not the original image being kept as variant 1)
                    for f in (vs / s.id).glob("*/index.json") if (vs / s.id).exists() else []:
                        if f.stat().st_mtime <= a["cut_at"] + 1:
                            continue
                        try:
                            for v in json.loads(f.read_text(encoding="utf-8")).get("variants", []):
                                if v.get("origin") != "original" and time.mktime(time.strptime(v["time"], "%Y-%m-%d %H:%M:%S")) > a["cut_at"] - 1:
                                    newer = True
                        except (OSError, ValueError, KeyError):
                            pass
                    if sigs and (sigs.get(s.id) != s.sig() or newer):
                        a["changed"].append(s.id)
                    elif not sigs and newer:
                        a["changed"].append(s.id)
                gone = [i for i in sigs if board.shot(i) is None]
                a["changed"] += gone
                if a["changed"]:
                    a["stale"], a["reason"] = True, "changed since it was cut: " + ", ".join(a["changed"][:8])
                elif tl.get("rev") and tl["rev"] != board.rev:
                    a["stale"], a["reason"] = True, "site.yaml changed since it was cut"
                elif not tl and spec_m > mp4.stat().st_mtime:
                    a["stale"], a["reason"] = True, "site.yaml changed since it was cut"
                if not a["shots"]:
                    a["reason"] = (a["reason"] + "; " if a["reason"] else "") + "rebuild it once to get the shot markers"
            out["animatic"] = a
        si = sb / "site" / "index.html"
        if si.exists():
            out["standin"] = {"url": "files/site/index.html", "stale": spec_m > si.stat().st_mtime}
        if (project.dist / "index.html").exists():
            out["dist"] = {"url": "dist/index.html", "built": time.strftime("%Y-%m-%d %H:%M", time.localtime((project.dist / "index.html").stat().st_mtime))}
        out["rebuilding"] = "__animatic__" in self.active
        return out

    def animatic(self) -> Job:
        """Cut the animatic again from what is rendered now (stills, clips): a storyboard at animatic level that renders
        nothing new (no ComfyUI, no Blender product pass). Also refreshes the sheet and the stand-in page."""
        if self.jobs is None:
            raise BuildError("this workspace has no job queue")
        key = "__animatic__"
        with self._lock:
            if key in self.active:
                raise variants.Busy("the animatic is already being rebuilt")

            def run(job: Job):
                from .. import storyboard as run_sb
                log, progress = logger(job)
                try:
                    with contextlib.redirect_stdout(_ToLog(log)):
                        res = run_sb(self.project, level="animatic", log=log, progress=progress, generate=False)
                    self.last[key] = {"status": "done", "message": f"animatic cut: {res['shots']} shots", "finished": time.time()}
                    return {k: res[k] for k in ("sheet", "animatic", "shots")}
                except Exception as e:
                    self.last[key] = {"status": "failed", "error": str(e).splitlines()[0][:300] if str(e) else type(e).__name__,
                                      "finished": time.time()}
                    raise
                finally:
                    self.active.pop(key, None)
            job = self.jobs.submit("animatic", self.project.name, "Rebuild the animatic", run)
            self.active[key] = job
            self.last.pop(key, None)
            return job

    # ------------------------------------------------------------ what an agent sees of a note
    def shot_summary(self, st: dict, shot_id: str) -> Optional[dict]:
        """A shot as an agent needs it to interpret a note: current field values, its images (path, state, seeds, steps)
        and the variants kept for each. `st` is state()."""
        s = next((x for x in st["shots"] if x["id"] == shot_id), None)
        if s is None:
            return None
        root = self.project.root
        return {"id": s["id"], "kind": s["kind"], "title": s["title"], "locked": s["locked"], "approval": s["approval"],
                "fields": {f["name"]: f["value"] for f in s["fields"]},
                "images": [{"slot": sl["name"], "label": sl["label"], "state": sl["nodes"][0]["image"]["state"],
                            "image": str(root / sl["nodes"][0]["image"]["p"]) if sl["nodes"][0]["image"].get("p") else None,
                            "variants": [{"n": v["n"], "seed": v["seed"], "current": v["current"]} for v in sl["nodes"][0]["variants"]],
                            "steps": [{"kind": n["kind"], "shared": n["shared"], "summary": n["summary"][:140],
                                       "fields": {f["name"]: f["value"] for f in n["fields"]}} for n in sl["nodes"]]}
                           for sl in s["slots"]]}

    def notes_for_agent(self, claim: bool = True, include_working: bool = False, include_done: bool = False) -> dict:
        """The notes an agent should act on, each with its shot's current spec values and image paths; a general note comes
        with the list of all shots. `claim` marks the open ones as working (the page shows that)."""
        todo = [n for n in notes.all_notes(self.project)
                if n["status"] == "open" or (include_working and n["status"] == "working") or (include_done and n["status"] == "done")]
        if claim:
            notes.claim(self.project, [n["id"] for n in todo if n["status"] == "open"])
            todo = [notes.get(self.project, n["id"]) for n in todo]
        st = self.state() if todo else None
        out = []
        for n in todo:
            item = dict(n)
            if st and n["shot"] != notes.GENERAL:
                item["shot_state"] = self.shot_summary(st, n["shot"])
            elif st:
                item["storyboard"] = [{"id": s["id"], "kind": s["kind"], "title": s["title"], "locked": s["locked"],
                                       "caption": next((f["value"] for f in s["fields"] if f["name"] == "caption"), None),
                                       "seconds": s["seconds"]} for s in st["shots"]]
            out.append(item)
        return {"project": self.project.name, "notes": out}
