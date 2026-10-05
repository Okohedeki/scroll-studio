"""Resolve spec inputs to files: project files as-is, `generate:` images through local Z-Image Turbo."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional

from .project import BuildError, Project
from .spec import ImageInput, ImageRef


def resolve_path(project: Project, ref: str, log=print) -> Path:
    """A project file, or an http(s) URL downloaded once into .build/_downloads (cached by URL)."""
    if ref.startswith(("http://", "https://")):
        import requests
        name = hashlib.sha1(ref.encode()).hexdigest()[:12] + "_" + ref.split("?")[0].rsplit("/", 1)[-1][-60:]
        out = project.build / "_downloads" / name
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            log(f"  downloading {ref}")
            ua = {"User-Agent": "ScrollStudio/0.1 (+https://github.com/Okohedeki/scroll-studio)"}
            with requests.get(ref, stream=True, timeout=60, headers=ua) as r:
                r.raise_for_status()
                tmp = out.with_suffix(out.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.replace(out)
        return out
    p = project.path(ref)
    if not p.exists():
        raise BuildError(f"input not found: {ref}")
    return p


def image_key(ref: ImageRef) -> dict:
    if isinstance(ref, str):
        return {"file": ref}
    return ref.model_dump(mode="json", exclude={"credit"})


def resolve_image(project: Project, ref: ImageRef, log=print) -> Path:
    if isinstance(ref, str):
        ref = ImageInput(file=ref)
    if ref.crop:
        src = resolve_image(project, ref.model_copy(update={"crop": None}), log)
        digest = hashlib.sha1(json.dumps([str(src), src.stat().st_size, list(ref.crop)]).encode()).hexdigest()[:12]
        out = project.build / "_generated" / f"crop_{digest}.png"
        if not out.exists():
            from PIL import Image
            im = Image.open(src)
            x0, y0, x1, y1 = ref.crop
            out.parent.mkdir(parents=True, exist_ok=True)
            im.crop((round(x0 * im.width), round(y0 * im.height), round(x1 * im.width), round(y1 * im.height))).save(out)
        return out
    if ref.file:
        return resolve_path(project, ref.file, log)
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
