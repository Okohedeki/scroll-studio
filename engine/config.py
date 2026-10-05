"""Machine configuration: where the external tools and models live.

Read from environment variables first, then `studio.toml` in the repo root (copy studio.example.toml),
then platform defaults. `studio doctor` reports what was found.
"""
from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # repo root
ENGINE = Path(__file__).resolve().parent
STATIC = ENGINE / "compile" / "static"                  # built runtime bundle lands here


def _toml() -> dict:
    path = ROOT / "studio.toml"
    if not path.exists():
        return {}
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover
        import tomli as tomllib
    with open(path, "rb") as f:
        return tomllib.load(f)


def _blender_default() -> str:
    if sys.platform == "win32":
        base = Path(r"C:\Program Files\Blender Foundation")
        found = sorted(base.glob("Blender */blender.exe"), reverse=True) if base.exists() else []
        if found:
            return str(found[0])
    elif sys.platform == "darwin":
        mac = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if mac.exists():
            return str(mac)
    return shutil.which("blender") or "blender"


@lru_cache(maxsize=1)
def settings() -> dict:
    t = _toml()
    get = lambda env, key, default: os.environ.get(env) or t.get(key) or default
    return {
        "blender": get("BLENDER", "blender", None) or _blender_default(),
        "ffmpeg": get("FFMPEG", "ffmpeg", "ffmpeg"),
        "ffprobe": get("FFPROBE", "ffprobe", "ffprobe"),
        "comfy_url": get("COMFY_URL", "comfy_url", "http://127.0.0.1:8188").rstrip("/"),
        "model_dir": get("STUDIO_MODELS", "model_dir", str(Path.home() / ".scroll-studio" / "models")),
        "chrome": get("CHROME", "chrome", None),
        "projects": get("STUDIO_PROJECTS", "projects", str(ROOT / "projects")),
    }
