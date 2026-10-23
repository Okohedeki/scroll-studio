"""What a pip install carries. The engine reads data files next to its code (templates, styles, the runtime bundle,
themes.yaml, models.yaml, Blender scripts); a file the wheel leaves out works from a checkout and fails for a user.
Builds the wheel from a copy of the tracked files, so nothing is written to the checkout, and checks it holds every
tracked file under engine/ (the `install` CI job runs the built wheel from a clean virtualenv as well)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NOT_SHIPPED: set[str] = set()      # tracked files under engine/ that are deliberately not part of the package


def tracked(*paths: str) -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout")
    out = subprocess.run(["git", "ls-files", "-z", "--", *paths], cwd=ROOT, capture_output=True, check=True).stdout.decode()
    return [p for p in out.split("\0") if p and (ROOT / p).is_file()]


@pytest.fixture(scope="module")
def wheel(tmp_path_factory) -> zipfile.ZipFile:
    pytest.importorskip("setuptools", minversion="68")
    src = tmp_path_factory.mktemp("src")
    out = tmp_path_factory.mktemp("wheel")
    for p in tracked("engine", "pyproject.toml", "README.md", "LICENSE"):
        (src / p).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / p, src / p)
    code = "import sys; from setuptools import build_meta; build_meta.build_wheel(sys.argv[1])"
    # without pytest-cov's variables: a measured subprocess would count the copy of engine/ it runs in as unexecuted source
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE", "COVERAGE"))}
    done = subprocess.run([sys.executable, "-c", code, str(out)], cwd=src, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    (whl,) = out.glob("*.whl")
    return zipfile.ZipFile(whl)


def test_the_wheel_has_every_tracked_file_under_engine(wheel):
    have = set(wheel.namelist())
    missing = [p for p in tracked("engine") if p not in have and p not in NOT_SHIPPED]
    assert not missing, ("not in the wheel: add them to [tool.setuptools.package-data] in pyproject.toml\n  "
                         + "\n  ".join(missing[:40]) + (f"\n  ... and {len(missing) - 40} more" if len(missing) > 40 else ""))


def test_the_wheel_carries_what_the_compiler_and_the_cli_open(wheel):
    have = set(wheel.namelist())
    for needed in ("engine/compile/templates/site.html.j2", "engine/compile/static/runtime/index.js",
                   "engine/compile/static/runtime/studio.css", "engine/themes.yaml", "engine/models.yaml",
                   "engine/backends/blender_scripts/take.py", "engine/styles/particles/style.yaml",
                   "engine/trailer/type.html"):
        assert needed in have, needed
    assert any(n.startswith("engine/compile/static/runtime/chunks/") for n in have)


def test_the_wheel_installs_the_studio_command_and_requires_python_3_10(wheel):
    entry = next(n for n in wheel.namelist() if n.endswith("entry_points.txt"))
    assert "studio = engine.cli:app" in wheel.read(entry).decode()
    meta = wheel.read(next(n for n in wheel.namelist() if n.endswith("/METADATA"))).decode()
    assert "Requires-Python: >=3.10" in meta
