"""`studio edit`: change a finished picture with an instruction ("make the backdrop warmer", "remove the cup").

Any image inside the project (a still, an ad, a presenter frame) goes through an edit job on the model router. The
result is written next to it as <name>.edit<n>.png, or, with --replace, over it (the original kept once as
<name>.orig.<ext>), so the steps that use it (ads, video) pick the edit up when they run again. Every edit is listed
in <project>/edits.json.

Videos are edited through what they are made from: edit the still they show, or the concept's script in
concepts/concepts.json, and run `studio video` or `studio ugc` again."""
from __future__ import annotations

import json
import shutil
import time
from typing import Callable

from .project import BuildError, Project

IMAGES = (".png", ".jpg", ".jpeg", ".webp")
VIDEOS = (".mp4", ".mov", ".webm")


def edit(project: Project, ref: str, instruction: str, seed: int = 1, replace: bool = False,
         log: Callable[[str], None] = print) -> dict:
    if not instruction.strip():
        raise BuildError("say what to change, e.g. \"make the backdrop warmer\"")
    src = project.path(ref)
    if not src.is_file():
        raise BuildError(f"{ref} is not a file in {project.name}")
    ext = src.suffix.lower()
    if ext in VIDEOS:
        raise BuildError(f"{ref} is a video: edit the still it shows (studio edit {project.name} <still> \"...\") or "
                         "the concept's script in concepts/concepts.json, then run studio video or studio ugc again")
    if ext not in IMAGES:
        raise BuildError(f"{ref} is not a picture ({', '.join(IMAGES)})")
    from .router import EditJob, NoBackend, choose, route
    spec = project.load_project() if project.is_project_file else None
    policy = spec.models if spec else None
    try:
        choose("edit", policy)
    except NoBackend as e:
        raise BuildError(f"no edit backend can run here: {e}") from None
    n = 1
    while (src.parent / f"{src.stem}.edit{n}.png").exists():
        n += 1
    out = src.parent / f"{src.stem}.edit{n}.png"
    r = route(EditJob((str(src),), instruction.strip(), seed, 24), out, policy, build=project.build, log=log)
    written = out
    if replace:
        keep = src.with_name(f"{src.stem}.orig{src.suffix}")
        if not keep.exists():
            shutil.copy(src, keep)
        from PIL import Image
        img = Image.open(out)
        if ext in (".jpg", ".jpeg"):
            img = img.convert("RGB")
        img.save(src)
        out.unlink()
        written = src
    entry = {"file": written.relative_to(project.root).as_posix(), "from": ref, "instruction": instruction.strip(),
             "backend": r.backend, "model": r.model, "replaced": replace, "at": round(time.time())}
    log_path = project.root / "edits.json"
    try:
        history = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        history = []
    history.append(entry)
    log_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"  edit: {entry['file']} ({r.backend})")
    return entry
