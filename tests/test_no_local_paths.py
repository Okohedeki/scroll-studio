"""No committed file may carry one machine's paths: a drive-letter path, a home folder, someone's folder layout. This is
a public repository; examples use placeholders (`/path/to/models`) and machines are configured in studio.toml
(gitignored) or environment variables. Standard install locations every Windows machine has are allowed."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DRIVE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]):[\\/]+([A-Za-z][^\s\"'`)]*)")
HOME = re.compile(r"/Users/[A-Za-z]|/home/(?!runner\b)[a-z]|\\Users\\[A-Za-z]")
ALLOWED = re.compile(r"^C:[\\/]+(Program|Windows)\b", re.I)   # where Blender, Chrome and fonts are installed
SKIP = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".glb", ".ply", ".spz", ".woff", ".woff2", ".ttf",
        ".otf", ".ico", ".pdf", ".zip", ".exr", ".npz", ".bin"}


def tracked() -> list[Path]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout")
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode()
    return [ROOT / p for p in out.split("\0") if p and Path(p).suffix.lower() not in SKIP and (ROOT / p).is_file()
            and not p.startswith("engine/compile/static/")]      # minified bundles, built from runtime/src (scanned)


def leaks(text: str) -> list[str]:
    found = []
    for m in DRIVE.finditer(text):
        if not ALLOWED.match(m.group(0)):
            found.append(m.group(0)[:60])
    found += [m.group(0) for m in HOME.finditer(text)]
    return found


def test_the_detector_finds_local_paths_and_allows_install_locations():
    assert leaks("model_dir = '" + "Q" + ":/models/x'") and leaks("cd " + "Q" + ":\\work\\site")
    assert leaks("/" + "Users/someone/site") and leaks("/" + "home/someone/site")
    assert not leaks(r"C:\Program Files\Blender Foundation") and not leaks("C:/Windows/Fonts/arial.ttf")
    assert not leaks("https://example.com/a:b and /home/runner/work and Notes:/x")


def test_no_committed_file_has_machine_specific_paths():
    bad = []
    for f in tracked():
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for hit in leaks(text):
            bad.append(f"{f.relative_to(ROOT).as_posix()}: {hit}")
    assert not bad, ("machine-specific paths in committed files (use a placeholder like /path/to/..., or studio.toml / "
                     "an environment variable):\n  " + "\n  ".join(bad[:40]))
