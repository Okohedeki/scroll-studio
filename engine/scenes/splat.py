"""splat: a scanned place (Gaussian splats) the camera flies through on scroll."""
from __future__ import annotations

import json
from pathlib import Path

from ..inputs import resolve_path
from ..project import BuildContext, BuildError, file_key
from ..spec import SplatScene

VERSION = 1


def build(sec: SplatScene, ctx: BuildContext, theme: dict) -> dict:
    from ..backends import splats
    src = resolve_path(ctx.project, sec.source, ctx.log)
    out = ctx.web / "scene.spz"
    meta = ctx.web / "scene.json"
    key = {"v": VERSION, "src": file_key(src), "max": sec.max_splats, "min": sec.min_opacity, "crop": sec.crop, "sh": sec.sh, "ms": sec.max_scale}

    def run():
        if src.suffix.lower() == ".spz" and not sec.crop and sec.max_splats >= 10_000_000:
            out.write_bytes(src.read_bytes())
            meta.write_text(json.dumps({"count": None}))
            return
        if src.suffix.lower() == ".spz":
            raise BuildError("trimming a .spz needs the original .ply or .pt; or set max_splats: 10000000 to use it as is")
        s = splats.trim(splats.read(src), max_splats=sec.max_splats, min_opacity=sec.min_opacity, crop=sec.crop, max_scale=sec.max_scale)
        if not len(s["means"]):
            raise BuildError("no splats left after trimming; raise min_opacity or widen crop")
        splats.write_spz(s, out, sh_degree=sec.sh)
        b = splats.bounds(s)
        meta.write_text(json.dumps(b))
        ctx.log(f"  {b['count']} splats -> scene.spz ({out.stat().st_size / 1048576:.1f} MB); "
                f"bounds x {b['min'][0]}..{b['max'][0]}, y {b['min'][1]}..{b['max'][1]}, z {b['min'][2]}..{b['max'][2]}")

    ctx.stage("splats", key, [out, meta], run)
    bounds = json.loads(meta.read_text()) if meta.exists() else {}
    return {
        "file": ctx.url(out), "up": list(sec.up), "fov": sec.fov, "keys": [k.model_dump() for k in sec.keys],
        "background": sec.background or theme["colors"]["bg"], "bounds": bounds,
        "credits": [sec.credit] if sec.credit else [],
    }
