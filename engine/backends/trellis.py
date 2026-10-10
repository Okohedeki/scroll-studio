"""Image to 3D with TRELLIS.2 (Microsoft, MIT), run in its own environment.

TRELLIS.2 needs its own Python environment (CUDA extensions, xformers). Point studio.toml at it:

    trellis_python = "D:/tools/trellis/.venv/Scripts/python.exe"
    trellis_script = "D:/tools/trellis/image_to_mesh.py"

The script is called as `<python> <script> --dir <work dir>` with `<work dir>/object.png` (the cut-out product on a
transparent background) and must write `<work dir>/mesh.ply`, a vertex-coloured mesh with +z up. Any script with
that contract works; docs/INSTALL.md shows a minimal one.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..config import settings
from ..project import BuildError


def image_to_mesh(photo: Path, work: Path, log=print) -> Path:
    cfg = settings()
    py, script = cfg.get("trellis_python"), cfg.get("trellis_script")
    out = work / "mesh.ply"
    if out.exists():
        return out
    if not (py and script):
        raise BuildError("product.from_photo needs TRELLIS.2: set trellis_python and trellis_script in studio.toml "
                         "(docs/INSTALL.md), or give the product as a 3D model with `model:`.")
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy(photo, work / "object.png")
    log(f"  TRELLIS.2: {photo.name} -> mesh.ply (a few minutes on the GPU)")
    p = subprocess.run([py, script, "--dir", str(work)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not out.exists():
        raise BuildError("TRELLIS.2 failed:\n" + (p.stderr or p.stdout)[-3000:])
    return out
