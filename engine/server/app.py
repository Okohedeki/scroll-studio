"""Studio server: the API behind the UI (and the MCP server). Run with `studio ui`.

Projects live in the projects folder (studio.toml `projects`, default ./projects); the bundled examples
are listed too and can be built and previewed in place.
"""
from __future__ import annotations

import mimetypes
import shutil
import time
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from ..config import ROOT, settings
from ..project import BuildError, Project, child, safe_name
from ..spec import SCENE_TYPES, Site, deprecations
from .jobs import JobQueue, logger
from .local_only import UI_DEV_PORTS, LocalOnly

# Windows can map .js to text/plain from the registry, which breaks module scripts in the preview.
for ext, typ in ((".js", "text/javascript"), (".mjs", "text/javascript"), (".css", "text/css"), (".webp", "image/webp"),
                 (".glb", "model/gltf-binary"), (".json", "application/json"), (".mp4", "video/mp4")):
    mimetypes.add_type(typ, ext)

app = FastAPI(title="Scroll Studio")
app.add_middleware(LocalOnly, extra_ports=UI_DEV_PORTS)    # Host and Origin checks: see local_only.py
jobs = JobQueue()
PROJECTS = Path(settings()["projects"])
EXAMPLES = ROOT / "examples"
UI_DIST = ROOT / "ui" / "dist"

SCENE_INFO = {
    "film": "AI film generated locally (Blender blockout → Z-Image keyframes → LTX-2.3), scrubbed by scroll.",
    "artwork": "Any image drawn and painted in stages: guides, contour lines, graphite, underpainting, colour.",
    "scene3d": "Live 3D zoom journey through levels: cells → DNA, galaxy → planet, networks, lattices, your glTF.",
    "sequence": "A 3D model rendered by Blender into frames: turntable, explode and reassemble.",
    "showroom": "The site's product live in the page (three.js): scroll turns, explodes and zooms the real model.",
    "diorama": "A miniature world (tilt-shift diorama, live 3D): scroll orbits it, dives to a place for each step, lifts out and travels on.",
    "parallax": "Photos turned into 2.5D camera moves with estimated depth, one per step.",
    "type": "Kinetic typography: reveal, stack, swap or scale.",
    "light": "One place relit from dawn to night as you scroll: each step a time of day, windows and lamps coming on.",
}
BLOCK_TYPES = ["intro", "features", "stats", "timeline", "quote", "cta", "gallery"]
PRESETS_3D = ["cell-field", "cell", "nucleus", "helix", "galaxy", "star-system", "planet", "network", "lattice", "particles", "gltf"]


MAX_UPLOAD = 4 * 2**30       # bytes per file: a long film or a big scan fits, a runaway upload does not


def find(name: str) -> Project:
    for base in (PROJECTS, EXAMPLES):
        try:
            p = Project(child(base, name, "project name"))
        except ValueError:
            break
        if p.exists():
            return p
    raise HTTPException(404, f"no project '{name}'")


def file_stem(text: Optional[str], default: str) -> str:
    """A name from a request made safe to use inside a file name (a section id, say)."""
    try:
        return safe_name(text or default)
    except ValueError:
        raise HTTPException(400, f"{text!r} can't be used in a file name: use letters, digits, '-' and '_'")


def summary(p: Project, kind: str) -> dict:
    try:
        raw = p.raw()
    except Exception:
        raw = {}
    poster = None
    for sec in raw.get("sections", []):
        if sec.get("type") in SCENE_TYPES and sec.get("id"):
            for cand in ("poster.jpg", "end.jpg", "photo0.jpg", "final.jpg"):
                if (p.dist / "assets" / sec["id"] / cand).exists():
                    poster = f"/preview/{p.name}/assets/{sec['id']}/{cand}"
                    break
        if poster:
            break
    return {"name": p.name, "kind": kind, "title": raw.get("name", p.name), "description": raw.get("description", ""),
            "theme": (raw.get("theme") or {}).get("preset", "night"),
            "scenes": list(dict.fromkeys(s.get("type") for s in raw.get("sections", []) if s.get("type") in SCENE_TYPES)),
            "built": (p.dist / "index.html").exists(), "poster": poster,
            "modified": p.spec_path.stat().st_mtime if p.exists() else 0}


# ---------------------------------------------------------------- catalogue

@app.get("/api/info")
def info():
    from ..compile.themes import presets
    return {"scene_types": SCENE_INFO, "block_types": BLOCK_TYPES, "themes": presets(), "presets3d": PRESETS_3D,
            "projects_dir": str(PROJECTS)}


@app.get("/api/schema")
def schema():
    return Site.model_json_schema()


@app.get("/api/doctor")
def doctor():
    from ..doctor import checks
    return checks()


# ---------------------------------------------------------------- projects

@app.get("/api/projects")
def projects():
    out = []
    PROJECTS.mkdir(parents=True, exist_ok=True)
    for base, kind in ((PROJECTS, "project"), (EXAMPLES, "example")):
        for d in sorted(base.iterdir()) if base.exists() else []:
            if (d / "site.yaml").exists():
                out.append(summary(Project(d), kind))
    return out


class NewProject(BaseModel):
    name: str
    example: Optional[str] = None


@app.post("/api/projects")
def create(req: NewProject):
    from ..cli import STARTER
    name = "".join(c for c in req.name.lower().replace(" ", "-") if c.isalnum() or c in "-_")
    if not name:
        raise HTTPException(400, "name is empty")
    try:
        dst = child(PROJECTS, name, "project name")
        src = child(EXAMPLES, req.example, "example name") if req.example else None
    except ValueError as e:
        raise HTTPException(400, str(e))
    if dst.exists():
        raise HTTPException(409, f"{name} already exists")
    if src is not None:
        if not (src / "site.yaml").exists():
            raise HTTPException(404, f"no example '{req.example}'")
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".build", "dist", "snapshots", "recordings"))
    else:
        (dst / "inputs").mkdir(parents=True)
        (dst / "site.yaml").write_text(STARTER, encoding="utf-8")
    return summary(Project(dst), "project")


@app.get("/api/projects/{name}/spec")
def get_spec(name: str):
    p = find(name)
    text = p.spec_path.read_text(encoding="utf-8")
    return {"yaml": text, "data": yaml.safe_load(text), "modified": p.spec_path.stat().st_mtime}


class SpecUpdate(BaseModel):
    data: Optional[dict] = None
    yaml: Optional[str] = None


@app.put("/api/projects/{name}/spec")
def put_spec(name: str, req: SpecUpdate):
    p = find(name)
    try:
        data = yaml.safe_load(req.yaml) if req.yaml is not None else req.data
        site = Site.model_validate(data)
    except ValidationError as e:
        return JSONResponse({"ok": False, "errors": [{"loc": ".".join(map(str, er["loc"])), "msg": er["msg"]} for er in e.errors()]}, 422)
    except yaml.YAMLError as e:
        return JSONResponse({"ok": False, "errors": [{"loc": "yaml", "msg": str(e)}]}, 422)
    if req.yaml is not None:
        p.spec_path.write_text(req.yaml, encoding="utf-8")
    else:
        p.save(data)
    return {"ok": True, "modified": p.spec_path.stat().st_mtime, "deprecations": [d.as_dict() for d in deprecations(site)]}


@app.get("/api/projects/{name}/inputs")
def inputs(name: str):
    p = find(name)
    if not p.inputs.exists():
        return []
    return [{"path": f"inputs/{f.relative_to(p.inputs).as_posix()}", "size": f.stat().st_size,
             "url": f"/files/{name}/inputs/{f.relative_to(p.inputs).as_posix()}"} for f in sorted(p.inputs.rglob("*")) if f.is_file()]


@app.post("/api/projects/{name}/inputs")
async def upload(name: str, files: list[UploadFile] = File(...)):
    p = find(name)
    p.inputs.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        try:
            name = child(p.inputs, Path(f.filename or "").name, "file name").name
            dst = p.path(f"inputs/{name}")       # follows links: an input that is a link out of the project is refused
        except (ValueError, BuildError) as e:
            raise HTTPException(400, str(e))
        written = 0
        with open(dst, "wb") as out:
            while chunk := f.file.read(1 << 20):
                written += len(chunk)
                if written > MAX_UPLOAD:
                    out.close()
                    dst.unlink(missing_ok=True)
                    raise HTTPException(413, f"{name} is larger than {MAX_UPLOAD // 2**30} GB: put it in the project's inputs/ folder yourself")
                out.write(chunk)
        saved.append(f"inputs/{dst.name}")
    return {"saved": saved}


@app.get("/files/{name}/{path:path}")
def project_file(name: str, path: str):
    p = find(name)
    try:
        f = p.path(path)
    except BuildError:
        raise HTTPException(403, "outside the project folder")
    if not f.is_file():
        raise HTTPException(404)
    return FileResponse(f)


@app.get("/preview/{name}/{path:path}")
def preview(name: str, path: str):
    p = find(name)
    f = (p.dist / (path or "index.html")).resolve()
    if p.dist.resolve() not in f.parents and f != p.dist.resolve():
        raise HTTPException(403)
    if f.is_dir():
        f = f / "index.html"
    if not f.is_file():
        raise HTTPException(404, "not built yet")
    return FileResponse(f, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- jobs

class BuildReq(BaseModel):
    section: Optional[str] = None
    force: bool = False
    draft: bool = False


@app.post("/api/projects/{name}/build")
def build(name: str, req: BuildReq):
    p = find(name)
    from ..compile.compiler import build_site

    def run(job):
        from ..plan import announce
        log, progress = logger(job)
        announce(p, only=[req.section] if req.section else None, force=req.force, options={"draft": req.draft}, log=log)
        build_site(p, log=log, progress=progress, only=req.section, force=req.force, options={"draft": req.draft})
        return {"preview": f"/preview/{name}/index.html?t={int(time.time())}"}
    return jobs.submit("build", name, f"Build {req.section or 'site'}" + (" (draft)" if req.draft else ""), run).public()


class StoryboardReq(BaseModel):
    level: str = "stills"
    only: list[str] = []
    motion: bool = False


@app.post("/api/projects/{name}/storyboard")
def storyboard(name: str, req: StoryboardReq):
    """`studio storyboard` as a job: the result has the sheet, the storyboard page and the stand-in site."""
    p = find(name)

    def run(job):
        from ..storyboard import storyboard as run_sb
        log, progress = logger(job)
        res = run_sb(p, level=req.level, only=req.only or None, motion=req.motion, log=log, progress=progress)
        return {k: v for k, v in res.items() if k in ("sheet", "html", "site", "animatic", "shots", "changed",
                                                       "render_estimate", "seconds")}
    return jobs.submit("storyboard", name, f"Storyboard ({req.level})", run).public()


class SnapReq(BaseModel):
    at: list[str] = []


@app.post("/api/projects/{name}/snapshot")
def snapshot(name: str, req: SnapReq):
    p = find(name)
    at = req.at
    if not at:
        site = p.load()
        at = ["top"] + [f"{s.id}:{v}" for s in site.sections if s.type in SCENE_TYPES for v in (0.15, 0.5, 0.85)] + ["bottom"]
    from ..snapshot import snapshot as snap

    def run(job):
        log, _ = logger(job)
        out = p.root / "snapshots"
        shutil.rmtree(out, ignore_errors=True)
        paths = snap(p.dist, at, out, log=log)
        stamp = int(time.time())
        return {"images": [f"/files/{name}/snapshots/{q.name}?t={stamp}" for q in paths], "sheet": f"/files/{name}/snapshots/sheet.jpg?t={stamp}"}
    return jobs.submit("snapshot", name, "Snapshots", run).public()


class RecordReq(BaseModel):
    section: Optional[str] = None
    seconds: float = 12.0
    width: int = 1920
    height: int = 1080


@app.post("/api/projects/{name}/record")
def record(name: str, req: RecordReq):
    p = find(name)
    stem = file_stem(req.section, "page")
    from ..record import record as rec

    def run(job):
        log, progress = logger(job)
        out = p.root / "recordings" / f"{stem}-{int(time.time())}.mp4"
        mp4 = rec(p.dist, out, section=req.section, size=(req.width, req.height), seconds=req.seconds, log=log, progress=progress)
        return {"video": f"/files/{name}/recordings/{mp4.name}"}
    return jobs.submit("record", name, f"Record {req.section or 'page'}", run).public()


@app.get("/api/projects/{name}/recordings")
def recordings(name: str):
    p = find(name)
    d = p.root / "recordings"
    return [{"name": f.name, "url": f"/files/{name}/recordings/{f.name}", "size": f.stat().st_size}
            for f in sorted(d.glob("*.mp4"), key=lambda f: -f.stat().st_mtime)] if d.exists() else []


@app.get("/api/jobs")
def list_jobs(project: Optional[str] = None):
    return jobs.list(project)


@app.get("/api/jobs/{jid}")
def job(jid: str):
    if jid not in jobs.jobs:
        raise HTTPException(404)
    return jobs.jobs[jid].public()


# ---------------------------------------------------------------- storyboard editor

from ..storyboard.edit.api import make_router as _sb_router   # noqa: E402  /sb/<project> and /api/sb/<project>/...
app.include_router(_sb_router(find, jobs))

from ..directions.api import make_router as _dir_router   # noqa: E402  /dir/<project> and /api/dir/<project>/... (direction boards)
app.include_router(_dir_router(find))


# ---------------------------------------------------------------- UI

if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
else:
    @app.get("/")
    def no_ui():
        return PlainTextResponse("The UI is not built. Run `npm install && npm run build` in the repo root, then restart `studio ui`.")
