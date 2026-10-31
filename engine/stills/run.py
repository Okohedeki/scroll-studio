"""`studio stills`, start to finish: directions -> candidates -> critics -> shortlist -> board.

    make(project)                      the first set, or fill in what is missing (the directions are kept)
    make(project, more="<id>")         more seeds in that candidate's direction and shot
    make(project, different=True)      new directions, unlike the ones there, across every shot
    make(project, pick="<id>")         mark a final for its shot

Everything lands in <project>/stills/: candidates/ (each still, its mask and its unblended composite), stills.json (the
directions, every candidate's record and scores, the shortlist, the picks) and board.html.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from ..project import BuildError, Project
from . import board, compose, critics, directions as dirs, shortlist
from .cutout import CutoutError, cutout
from .directions import Direction

Log = Callable[[str], None]


def folder(project: Project) -> Path:
    return project.root / "stills"


def state_path(project: Project) -> Path:
    return folder(project) / "stills.json"


def load(project: Project) -> Optional[dict]:
    p = state_path(project)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except ValueError:
        return None


def save(project: Project, state: dict) -> None:
    folder(project).mkdir(parents=True, exist_ok=True)
    state_path(project).write_text(json.dumps(state, indent=2), encoding="utf-8")


def spec_of(project: Project):
    """(project spec, its outputs.stills); BuildError saying how to add one."""
    if not project.is_project_file:
        raise BuildError(f"{project.name} has no project.yaml: run `studio migrate {project.name} --write`, then add "
                         "outputs.stills (docs/stills.md)")
    spec = project.load_project()
    if spec.outputs.stills is None:
        raise BuildError(f"{project.name}'s project.yaml has no outputs.stills (docs/stills.md)")
    return spec, spec.outputs.stills


def candidate_id(shot: str, d: Direction, seed: int) -> str:
    return f"{shot}-{d.id}-s{seed}"


def _score(made: compose.Made, shot: str, limit: float) -> dict:
    img, mask = Image.open(made.image), Image.open(made.mask)
    change = critics.product_change(Image.open(made.composite), img, mask) if made.harmonised else 0.0
    fid, fra, con = critics.fidelity(change, limit), critics.framing(mask, shot), critics.contrast(img, mask)
    return {"fidelity": round(fid, 3), "framing": fra, "contrast": con, "change": round(change, 4),
            "score": critics.score(fid, fra, con)}


def make(project: Project, more: Optional[str] = None, different: bool = False, pick: Optional[str] = None,
         log: Log = print) -> dict:
    spec, st = spec_of(project)
    state = load(project) or {"directions": [], "candidates": [], "shortlist": {}, "picked": {}, "next_seed": st.seed}
    by_id = {c["id"]: c for c in state["candidates"]}
    if pick:
        c = by_id.get(pick)
        if c is None:
            raise BuildError(f"no candidate {pick!r}: see stills/board.html for the ids")
        state["picked"][c["shot"]] = pick
        save(project, state)
        board.write(project, state)
        return state

    try:
        product = cutout(project.path(st.photo))
    except (CutoutError, OSError) as e:
        raise BuildError(f"outputs.stills.photo: {e}") from None
    describe = st.describe or (spec.product.name if spec.product else "")
    policy = spec.models
    existing = [Direction.from_dict(d) for d in state["directions"]]
    jobs: list[tuple[str, Direction, int]] = []
    if more:
        c = by_id.get(more)
        if c is None:
            raise BuildError(f"no candidate {more!r}: see stills/board.html for the ids")
        d = dirs.by_id(existing, c["direction"])
        start = max(x["seed"] for x in state["candidates"] if x["shot"] == c["shot"] and x["direction"] == d.id) + 1
        jobs = [(c["shot"], d, s) for s in range(start, start + st.candidates)]
    else:
        if different or not existing:
            seed = state["next_seed"]
            new = dirs.write(st.directions, seed, describe, spec.brief, policy, project.build,
                             avoid=dirs.named(existing), log=log)
            state["next_seed"] = seed + 1
            existing += new
            state["directions"] = [d.as_dict() for d in existing]
            targets = new
        else:
            targets = existing
        jobs = [(shot, d, s) for shot in st.shots for d in targets for s in range(st.seed, st.seed + st.candidates)]

    work = folder(project) / "candidates"
    todo = [(shot, d, s) for shot, d, s in jobs if candidate_id(shot, d, s) not in by_id]
    log(f"stills: {len(todo)} candidates to make ({len(existing)} directions, shots: {', '.join(st.shots)})")
    for i, (shot, d, s) in enumerate(todo, 1):
        cid = candidate_id(shot, d, s)
        log(f"  [{i}/{len(todo)}] {cid}: {d.name}")
        made = compose.make(product, shot, d, s, tuple(st.size), describe, work, cid, harmonise=st.harmonise,
                            fidelity=st.fidelity, policy=policy, build=project.build, log=log)
        rec = {"id": cid, "shot": shot, "direction": d.id, "seed": s, "backend": made.backend, "model": made.model,
               "prompt": made.prompt, "harmonised": made.harmonised, "notes": made.notes,
               "image": made.image.relative_to(folder(project)).as_posix(),
               "scores": _score(made, shot, st.fidelity)}
        state["candidates"].append(rec)
        by_id[cid] = rec
        save(project, state)            # a long run can stop anywhere and pick up here

    vectors = {c["id"]: critics.descriptor(Image.open(folder(project) / c["image"])) for c in state["candidates"]}
    for shot in st.shots:
        pool = [{"id": c["id"], "score": c["scores"]["score"]} for c in state["candidates"] if c["shot"] == shot]
        state["shortlist"][shot] = shortlist.pick(pool, vectors, st.keep)
    save(project, state)
    board.write(project, state)
    log(f"stills: board at {folder(project) / 'board.html'}")
    return state
