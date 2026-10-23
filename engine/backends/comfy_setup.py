"""`studio setup-comfy`: install the ComfyUI custom nodes (and the small face-restore weights) that `reveal` and `faces` use.

  ComfyUI-segment-anything-2   kijai, Apache-2.0   SAM 2.1 (its sam2 package; the weights download on first use)
  ComfyUI-Florence2            kijai, MIT          Florence-2 grounding (weights download on first use)
  scroll_studio_nodes          this repo, AGPL     engine/backends/comfy_nodes/: box/point tracking both ways, face restore

Nothing here restarts ComfyUI: custom nodes load at start, so restart it yourself when its queue is empty.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from ..config import ENGINE, settings
from ..weights import ChecksumError, check_sha256, download_verified, pinned_sha256

PACKS = {
    "ComfyUI-segment-anything-2": "https://github.com/kijai/ComfyUI-segment-anything-2",
    "ComfyUI-Florence2": "https://github.com/kijai/ComfyUI-Florence2",
}
OWN = ENGINE / "backends" / "comfy_nodes" / "scroll_studio_nodes"
GFPGAN = ("facerestore_models/GFPGANv1.4.pth",
          "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth")


def comfy_dir() -> Path | None:
    """ComfyUI's folder: `comfy_dir` in studio.toml (or COMFY_DIR), else <model_dir>/ComfyUI."""
    import os
    s = settings()
    for cand in (os.environ.get("COMFY_DIR"), s.get("comfy_dir"), Path(s["model_dir"]) / "ComfyUI"):
        if cand and (Path(cand) / "custom_nodes").is_dir():
            return Path(cand)
    return None


def install(log: Callable[[str], None] = print, weights: bool = True) -> list[str]:
    """Clone the node packs that are missing, copy this repo's nodes in (always: they update with the engine), fetch the
    GFPGAN weights. Returns what changed."""
    root = comfy_dir()
    if root is None:
        raise SystemExit("can't find ComfyUI: set `comfy_dir` in studio.toml (or COMFY_DIR) to its folder")
    nodes, changed = root / "custom_nodes", []
    for name, url in PACKS.items():
        if (nodes / name).exists():
            log(f"  {name}: already installed")
            continue
        log(f"  {name}: cloning {url}")
        subprocess.run(["git", "clone", "--depth", "1", url, str(nodes / name)], check=True)
        changed.append(name)
    dst = nodes / "scroll_studio_nodes"
    shutil.copytree(OWN, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    log(f"  scroll_studio_nodes: copied to {dst}")
    changed.append("scroll_studio_nodes")
    if weights:
        rel, url = GFPGAN
        path = root / "models" / rel
        want = pinned_sha256(rel)
        if path.exists():
            log(f"  {rel}: already there")
            if want:
                try:
                    check_sha256(path, want, url)
                except ChecksumError as e:
                    log(f"  warning: {e} Delete it and run `studio setup-comfy` again to fetch a verified copy.")
        else:
            log(f"  {rel}: downloading (~330 MB) from {url}")
            download_verified(url, path, want, log)
            changed.append(rel)
    log("  Restart ComfyUI (when its queue is empty) so it loads the nodes. SAM 2.1 and Florence-2 weights download on first use.")
    return changed
