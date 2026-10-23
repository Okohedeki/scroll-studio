"""HTTP side of the direction boards, served like the storyboard editor: `studio directions <project> --serve` runs its
own small server, and `studio ui`'s server mounts the same router.

  GET  /dir/{name}                      the board page (the buttons appear when it is served)
  GET  /dir/{name}/files/...            directions/ (stills, fonts, the contact sheet)
  GET  /api/dir/{name}/state            the saved directions
  POST /api/dir/{name}/pick             {id}        write that direction into site.yaml (backup kept)
  POST /api/dir/{name}/undo                         put site.yaml back as before the last pick
  POST /api/dir/{name}/reroll           {id}        another idea in place of one direction
  POST /api/dir/{name}/generate         {seed?, count?, brief?}   write a new set
  POST /api/dir/{name}/stills                       draw the stills again
"""
from __future__ import annotations

import socket
import threading
import webbrowser
from typing import Callable, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from ..project import BuildError, Project
from ..server.local_only import LocalOnly
from . import board, run

PORTS = range(8981, 8990)


class IdReq(BaseModel):
    id: str


class GenReq(BaseModel):
    seed: Optional[int] = None
    count: Optional[int] = None
    brief: Optional[str] = None


def make_router(resolve: Callable[[str], Project]) -> APIRouter:
    r = APIRouter()
    busy: set[str] = set()

    def guarded(name: str, fn, exclusive: bool = False):
        try:
            if exclusive:
                if name in busy:
                    return JSONResponse({"ok": False, "error": "the boards are being drawn: wait for it to finish"}, 409)
                busy.add(name)
            try:
                return fn()
            finally:
                busy.discard(name)
        except BuildError as e:
            return JSONResponse({"ok": False, "error": str(e)}, 400)
        except Exception as e:      # a validation error from the spec writer, ComfyUI down...
            return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, 400)

    @r.get("/dir/{name}", response_class=HTMLResponse)
    def page(name: str):
        project = resolve(name)
        f = board.folder(project) / "board.html"
        if not f.exists():
            raise HTTPException(404, f"no boards yet: run `studio directions {name}`")
        text = f.read_text(encoding="utf-8").replace("<head>", f'<head><base href="/dir/{name}/files/">', 1)
        return HTMLResponse(text, headers={"Cache-Control": "no-store"})

    @r.get("/dir/{name}/files/{path:path}")
    def files(name: str, path: str):
        project = resolve(name)
        base = board.folder(project).resolve()
        f = (base / (path or "board.html")).resolve()
        if base not in f.parents and f != base:
            raise HTTPException(403)
        if not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, headers={"Cache-Control": "no-store"})

    @r.get("/api/dir/{name}/state")
    def state(name: str):
        s = run.load(resolve(name))
        if not s:
            raise HTTPException(404, "no boards yet")
        return s

    @r.post("/api/dir/{name}/pick")
    def pick(name: str, req: IdReq):
        def go():
            res = run.pick(resolve(name), req.id)
            return {"ok": True, "changed": res["changed"], "backup": res["backup"] or "(nothing to change)",
                    "diff": res["diff"]}
        return guarded(name, go)

    @r.post("/api/dir/{name}/undo")
    def undo(name: str):
        return guarded(name, lambda: {"ok": True, **run.undo(resolve(name), log=lambda m: None)})

    @r.post("/api/dir/{name}/reroll")
    def reroll(name: str, req: IdReq):
        return guarded(name, lambda: {"ok": True, "state": run.reroll(resolve(name), req.id, log=lambda m: None)["seed"]}, True)

    @r.post("/api/dir/{name}/generate")
    def generate(name: str, req: GenReq):
        return guarded(name, lambda: {"ok": True, "seed": run.make(resolve(name), req.count, req.seed, req.brief,
                                                                  log=lambda m: None)["seed"]}, True)

    @r.post("/api/dir/{name}/stills")
    def stills(name: str):
        return guarded(name, lambda: {"ok": True, "seed": run.redraw(resolve(name), log=lambda m: None)["seed"]}, True)

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
    raise BuildError("ports 8981-8989 are all in use; pass --port")


def make_app(project: Project) -> FastAPI:
    app = FastAPI(title="Scroll Studio: direction boards")
    app.add_middleware(LocalOnly)

    def resolve(name: str) -> Project:
        if name != project.name:
            raise HTTPException(404, f"this server shows '{project.name}'")
        return project
    app.include_router(make_router(resolve))

    @app.get("/")
    def home():
        return RedirectResponse(f"/dir/{project.name}")
    return app


def serve(project: Project, port: Optional[int] = None, open_browser: bool = True, log: Callable[[str], None] = print) -> None:
    """Serve the boards of one project (blocks until Ctrl-C)."""
    import uvicorn
    port = free_port(port)
    url = f"http://127.0.0.1:{port}/dir/{project.name}"
    log(f"direction boards for {project.name}: {url}  (Ctrl-C to stop)")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(make_app(project), host="127.0.0.1", port=port, log_level="warning")
