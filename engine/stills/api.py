"""HTTP side of product stills, mounted by `studio ui`'s server (issue #177).

  GET  /api/projects/{name}/stills                 the state: directions, candidates (with file URLs), shortlist, picks
  GET  /api/projects/{name}/stills/files/{path}    a file inside stills/
  POST /api/projects/{name}/stills                 {pick} at once, or {more | different} (or nothing: fill in) as a job
"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..project import BuildError, Project, within
from ..server.jobs import JobQueue, logger
from . import run


NO_STILLS = "this project has no outputs.stills in a project.yaml (docs/stills.md)"
MIGRATE_FIRST = "this project is a site.yaml: run `studio migrate <project> --write`, then add outputs.stills (docs/stills.md)"


class StillsReq(BaseModel):
    more: Optional[str] = None
    different: bool = False
    pick: Optional[str] = None


def view(project: Project, state: Optional[dict]) -> dict:
    """The state with a URL for every candidate's image; `enabled` says whether the project has outputs.stills."""
    try:
        _, st = run.spec_of(project)
        enabled, why = True, ""
        shots = list(st.shots)
    except BuildError:
        # fixed messages: exception text never reaches the client
        enabled, shots = False, []
        why = NO_STILLS if project.is_project_file else MIGRATE_FIRST
    state = state or {"directions": [], "candidates": [], "shortlist": {}, "picked": {}}
    base = f"/api/projects/{project.name}/stills/files/"
    cands = [{**c, "url": base + c["image"]} for c in state["candidates"]]
    return {**state, "candidates": cands, "enabled": enabled, "why": why, "shots": shots}


def make_router(find: Callable[[str], Project], jobs: JobQueue) -> APIRouter:
    r = APIRouter()

    @r.get("/api/projects/{name}/stills")
    def get_state(name: str):
        p = find(name)
        return view(p, run.load(p))

    @r.get("/api/projects/{name}/stills/files/{path:path}")
    def get_file(name: str, path: str):
        p = find(name)
        try:
            f = within(run.folder(p), path)
        except ValueError:
            raise HTTPException(404) from None
        if not f.is_file():
            raise HTTPException(404)
        return FileResponse(f)

    @r.post("/api/projects/{name}/stills")
    def post(name: str, req: StillsReq):
        p = find(name)
        if req.pick:
            try:
                return {"ok": True, "state": view(p, run.make(p, pick=req.pick, log=lambda m: None))}
            except BuildError:
                raise HTTPException(400, "no such candidate: pick one of the ids the stills view lists") from None
        try:
            run.spec_of(p)
        except BuildError:
            raise HTTPException(400, NO_STILLS) from None

        def work(job):
            log, _ = logger(job)
            st = run.make(p, more=req.more, different=req.different, log=log)
            return {"shortlist": st["shortlist"]}
        label = f"more like {req.more}" if req.more else "different directions" if req.different else "product stills"
        return jobs.submit("stills", p.name, label, work).public(tail=5)

    return r
