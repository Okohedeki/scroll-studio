"""Resolve spec inputs to files: project files as-is, `generate:` images through local Z-Image Turbo."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional

from .project import BuildError, Project
from .spec import ImageInput, ImageRef


def image_key(ref: ImageRef) -> dict:
    if isinstance(ref, str):
        return {"file": ref}
    return ref.model_dump(mode="json", exclude={"credit"})


def resolve_image(project: Project, ref: ImageRef, log=print) -> Path:
    if isinstance(ref, str):
        ref = ImageInput(file=ref)
    if ref.file:
        p = project.path(ref.file)
        if not p.exists():
            raise BuildError(f"input not found: {ref.file}")
        return p
    if not ref.generate:
        raise BuildError("an image input needs `file` or `generate`")
    w, h = (int(v) // 16 * 16 for v in ref.size)
    digest = hashlib.sha1(json.dumps([ref.generate, w, h, ref.seed]).encode()).hexdigest()[:12]
    out = project.build / "_generated" / f"{digest}.png"
    if out.exists():
        return out
    from .backends import comfy
    if not comfy.alive():
        raise BuildError("this image is generated locally, but ComfyUI is not running at "
                         f"{comfy.COMFY}. Start it (docs/INSTALL.md) or replace `generate:` with a `file:`.")
    log(f"  generating image ({w}x{h}, seed {ref.seed}): {ref.generate[:80]}…")
    comfy.free()
    images = comfy.run(comfy.build_txt2img_graph(ref.generate, w, h, ref.seed, prefix=f"studio/{digest}"), poll=2)
    tmp = comfy.fetch(images, str(out.parent / f"_{digest}"))
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(Path(tmp) / "0001.png"), out)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def credit(ref: Optional[ImageRef]) -> Optional[str]:
    return ref.credit if isinstance(ref, ImageInput) else None
