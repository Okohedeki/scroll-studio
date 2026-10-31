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
        # ComfyUI's folder, for `studio setup-comfy` and `studio doctor` (default: <model_dir>/ComfyUI)
        "comfy_dir": get("COMFY_DIR", "comfy_dir", None),
        "chrome": get("CHROME", "chrome", None),
        "projects": get("STUDIO_PROJECTS", "projects", str(ROOT / "projects")),
        # image -> 3D for product takes (engine/backends/trellis.py); optional
        "trellis_python": get("TRELLIS_PYTHON", "trellis_python", None),
        "trellis_script": get("TRELLIS_SCRIPT", "trellis_script", None),
        # video model for film beats, takes and theme.art when the spec doesn't choose one: ltx | wan
        "video_model": get("STUDIO_VIDEO_MODEL", "video_model", "ltx"),
        # Wan 2.2 file names as ComfyUI lists them, when they differ from engine/backends/comfy.py WAN ([wan] table)
        "wan": t.get("wan") or {},
        # `studio build` asks before starting when its estimate is over this many minutes (unset: just print it);
        # --yes skips the question, and without a terminal the build stops instead of waiting
        "confirm_over": float(get("STUDIO_CONFIRM_OVER", "confirm_over", 0) or 0) or None,
        # model router (engine/router): an OpenAI-style text server, and the models provider backends use
        "text_url": get("STUDIO_TEXT_URL", "text_url", None),
        "text_model": get("STUDIO_TEXT_MODEL", "text_model", None),
        "anthropic_model": get("STUDIO_ANTHROPIC_MODEL", "anthropic_model", None),
        "openai_image_model": get("STUDIO_OPENAI_IMAGE_MODEL", "openai_image_model", None),
    }
