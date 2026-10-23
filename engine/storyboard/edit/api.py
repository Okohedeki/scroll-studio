"""HTTP side of the edit workspace: one router, used by `studio storyboard <project> --edit` (its own small server) and
mounted in `studio ui`'s server too.

  GET  /sb/{name}                         the page
  GET  /api/sb/{name}/state | poll        everything shown / what changed since (spec revision, running jobs)
  POST /api/sb/{name}/save                field edits -> site.yaml (422 {errors} when invalid, 409 {conflict} when the
                                          file moved on under the fields being saved)
  POST /api/sb/{name}/lock | approve | undo | sheet
  POST /api/sb/{name}/image               {key, mode: regenerate|rerun}   one image job (409 if it is already running)
  POST /api/sb/{name}/pick | revert       make a kept variant current
  GET  /api/sb/{name}/img?p=&w=           an image of the project, as a thumbnail (w) or whole
  GET  /sb/{name}/files/...               the storyboard folder (sheet, stand-in page)
  POST /api/sb/{name}/inspect             run the polish check (`studio inspect`) as a job
  GET  /sb/{name}/inspect/...             the polish reports (.build/inspect: <section>.html, .json, pictures)
"""
from __future__ import annotations

import mimetypes
import socket
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from ...project import BuildError, Project
from ...server.jobs import JobQueue
from ...server.local_only import LocalOnly
from . import images, specdoc, variants
from .workspace import Workspace

# Windows can map .js to text/plain from the registry, which stops module scripts of the pages played in the editor
for _ext, _typ in ((".js", "text/javascript"), (".mjs", "text/javascript"), (".css", "text/css"), (".webp", "image/webp"),
                   (".glb", "model/gltf-binary"), (".json", "application/json"), (".mp4", "video/mp4"),
                   (".woff2", "font/woff2")):
    mimetypes.add_type(_typ, _ext)

PAGE = Path(__file__).with_name("page.html")
PORTS = range(8971, 8980)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


class SaveReq(BaseModel):
    edits: list[dict]
    rev: Optional[str] = None


class LockReq(BaseModel):
    shot: str
    locked: bool


class ApproveReq(BaseModel):
    shot: str
    approved: bool


class ImageReq(BaseModel):
    key: str
    mode: str = "regenerate"
    seed: Optional[int] = None


class PickReq(BaseModel):
    key: str
    n: int


class KeyReq(BaseModel):
    key: str


class NoteReq(BaseModel):
    shot: str = "general"
    text: str


class NoteIdReq(BaseModel):
    id: str
    more: str = ""


def make_router(resolve: Callable[[str], Project], jobs: JobQueue) -> APIRouter:
    r = APIRouter()
    spaces: dict[str, Workspace] = {}

    def ws(name: str) -> Workspace:
        project = resolve(name)
        key = str(project.root)
        if key not in spaces:
            spaces[key] = Workspace(project, jobs)
        return spaces[key]

    def guarded(fn):
        try:
            return fn()
        except specdoc.SpecError as e:
            return JSONResponse({"ok": False, "errors": e.errors}, 422)
        except specdoc.Conflict as e:
            return JSONResponse({"ok": False, "conflict": e.paths,
                                 "error": "site.yaml changed on disk under these fields; they were reloaded"}, 409)
        except variants.Busy as e:
            return JSONResponse({"ok": False, "error": str(e)}, 409)
        except BuildError as e:
            return JSONResponse({"ok": False, "error": str(e)}, 400)

    @r.get("/sb/{name}", response_class=HTMLResponse)
    def page(name: str):
        ws(name)
        return HTMLResponse(PAGE.read_text(encoding="utf-8").replace("__NAME__", name),
                            headers={"Cache-Control": "no-store"})

    @r.get("/api/sb/{name}/state")
    def state(name: str):
        return guarded(lambda: ws(name).state())

    @r.get("/api/sb/{name}/poll")
    def poll(name: str):
        return ws(name).poll()

    @r.post("/api/sb/{name}/save")
    def save(name: str, req: SaveReq):
        return guarded(lambda: ws(name).save(req.edits, req.rev))

    @r.post("/api/sb/{name}/lock")
    def lock(name: str, req: LockReq):
        return guarded(lambda: ws(name).set_lock(req.shot, req.locked))

    @r.post("/api/sb/{name}/approve")
    def approve(name: str, req: ApproveReq):
        return guarded(lambda: {"ok": True, "approval": ws(name).approve(req.shot, req.approved)})

    @r.post("/api/sb/{name}/undo")
    def undo(name: str):
        return guarded(lambda: {"ok": True, **ws(name).undo()})

    @r.post("/api/sb/{name}/image")
    def image(name: str, req: ImageReq):
        return guarded(lambda: {"ok": True, "job": ws(name).start(req.key, req.mode, req.seed).public(tail=3)})

    @r.post("/api/sb/{name}/pick")
    def pick(name: str, req: PickReq):
        return guarded(lambda: {"ok": True, **ws(name).pick(req.key, req.n)})

    @r.post("/api/sb/{name}/revert")
    def revert(name: str, req: KeyReq):
        return guarded(lambda: {"ok": True, **ws(name).revert(req.key)})

    @r.post("/api/sb/{name}/notes")
    def add_note(name: str, req: NoteReq):
        return guarded(lambda: {"ok": True, "note": ws(name).add_note(req.shot, req.text)})

    @r.post("/api/sb/{name}/notes/reopen")
    def reopen_note(name: str, req: NoteIdReq):
        return guarded(lambda: {"ok": True, "note": ws(name).reopen_note(req.id, req.more)})

    @r.post("/api/sb/{name}/notes/delete")
    def delete_note(name: str, req: NoteIdReq):
        return guarded(lambda: (ws(name).delete_note(req.id), {"ok": True})[1])

    @r.post("/api/sb/{name}/animatic")
    def animatic(name: str):
        return guarded(lambda: {"ok": True, "job": ws(name).animatic().public(tail=3)})

    @r.get("/api/sb/{name}/play")
    def play(name: str):
        return guarded(lambda: ws(name).play_info())

    @r.post("/api/sb/{name}/sheet")
    def sheet(name: str):
        return guarded(lambda: {"ok": True, "job": ws(name).sheet().public(tail=3)})

    @r.get("/api/sb/{name}/img")
    def img(name: str, p: str, w: int = 0):
        project = resolve(name)
        f = (project.root / p).resolve()
        if project.root not in f.parents or f.suffix.lower() not in IMAGE_EXT or not f.is_file():
            raise HTTPException(404)
        if w and w < 2000:
            t = images.thumb(project, f, w)
            if t is not None:
                f = t
        return FileResponse(f, headers={"Cache-Control": "private, max-age=86400"})

    @r.post("/api/sb/{name}/inspect")
    def inspect_run(name: str):
        return guarded(lambda: {"ok": True, "job": ws(name).inspect().public(tail=3)})

    @r.get("/sb/{name}/inspect/{path:path}")
    def inspect_files(name: str, path: str):
        project = resolve(name)
        base = (project.build / "inspect").resolve()
        f = (base / path).resolve()
        if base not in f.parents or f.suffix.lower() not in (".html", ".json", ".jpg", ".png"):
            raise HTTPException(403)
        if not f.is_file():
            raise HTTPException(404, "no polish report yet: use Polish check")
        return FileResponse(f, headers={"Cache-Control": "no-store"})

    @r.get("/sb/{name}/files/{path:path}")
    def files(name: str, path: str):
        project = resolve(name)
        base = (project.root / "storyboard").resolve()
        f = (base / (path or "storyboard.html")).resolve()
        if base not in f.parents and f != base:
            raise HTTPException(403)
        if f.is_dir():
            f = f / "index.html"
        if not f.is_file():
            raise HTTPException(404, "not made yet: use Update sheet")
        return FileResponse(f, headers={"Cache-Control": "no-store"})

    @r.get("/sb/{name}/dist/{path:path}")
    def dist(name: str, path: str):
        """The built page (dist/), so the editor can play it in a frame."""
        project = resolve(name)
        base = project.dist.resolve()
        f = (base / (path or "index.html")).resolve()
        if base not in f.parents and f != base:
            raise HTTPException(403)
        if f.is_dir():
            f = f / "index.html"
        if not f.is_file():
            raise HTTPException(404, "not built yet: run studio build")
        return FileResponse(f, headers={"Cache-Control": "no-store"})

    return r


def free_port(preferred: Optional[int] = None) -> int:
    def free(p: int) -> bool:
        with socket.socket() as s:
            return s.connect_ex(("127.0.0.1", p)) != 0
    if preferred:
        if not free(preferred):
            raise BuildError(f"port {preferred} is in use")
        return preferred
    for p in PORTS:
        if free(p):
            return p
    raise BuildError("ports 8971-8979 are all in use; pass --port")


def make_app(project: Project) -> FastAPI:
    app = FastAPI(title="Scroll Studio: storyboard editor")
    app.add_middleware(LocalOnly)
    jobs = JobQueue()

    def resolve(name: str) -> Project:
        if name != project.name:
            raise HTTPException(404, f"this editor serves '{project.name}'")
        return project
    app.include_router(make_router(resolve, jobs))

    @app.get("/")
    def home():
        return RedirectResponse(f"/sb/{project.name}")
    return app


def serve(project: Project, port: Optional[int] = None, open_browser: bool = True, log: Callable[[str], None] = print) -> None:
    """Serve the edit workspace for one project (blocks until Ctrl-C)."""
    import uvicorn
    port = free_port(port)
    url = f"http://127.0.0.1:{port}/sb/{project.name}"
    app = make_app(project)
    log(f"storyboard editor for {project.name}: {url}  (Ctrl-C to stop)")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
