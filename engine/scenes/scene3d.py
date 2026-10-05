"""scene3d: live 3D zoom journey. Nothing to render ahead of time; glTF models are copied into the site."""
from __future__ import annotations

import shutil

from ..project import BuildContext, BuildError
from ..spec import Scene3DScene


def build(sec: Scene3DScene, ctx: BuildContext, theme: dict) -> dict:
    levels = []
    for i, lv in enumerate(sec.levels):
        params = dict(lv.params)
        if lv.preset == "gltf":
            if "file" not in params:
                raise BuildError(f"scene3d '{sec.id}' level {i}: gltf preset needs params.file")
            src = ctx.project.path(params.pop("file"))
            dst = ctx.web / f"model{i}{src.suffix}"
            shutil.copy(src, dst)
            params["url"] = ctx.url(dst)
        levels.append({"preset": lv.preset, "params": params})
    return {"style": sec.style, "levels": levels, "zoom": sec.zoom, "background": sec.background,
            "bloom": list(sec.bloom), "final": sec.final}
