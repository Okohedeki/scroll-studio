"""Laptop mode (issue #119): `studio new --laptop` makes a project that builds with no GPU, ComfyUI, Blender or FFmpeg, and
`studio doctor` says what a machine without a GPU can build. The build runs for real, with stand-ins for the two things
a test machine should not do: download a depth model (the photo parallax's depth map is a gradient) and fetch fonts."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner

from engine import cli, doctor, spec
from engine.backends import comfy, depth
from engine.compile import compiler, fonts, themes
from engine.project import BuildError, Project

ROOT = Path(__file__).resolve().parent.parent
LAPTOP_TYPES = {"parallax", "type", "artwork", "vector", "chart", "map", "code", "scene3d", "diorama", "splat"}


@pytest.fixture
def laptop(tmp_path, monkeypatch):
    """A machine with no GPU stack: ComfyUI is down, and a build that starts Blender or FFmpeg fails the test."""
    import numpy as np
    monkeypatch.setattr(cli, "settings", lambda: {"projects": str(tmp_path / "projects")})
    monkeypatch.setattr(fonts, "vendor", lambda links, dist, log=print: None)
    monkeypatch.setattr(comfy, "alive", lambda *a, **k: False)

    def gradient(img, size="small"):
        return np.tile(np.linspace(0, 1, img.width, dtype=np.float32), (img.height, 1))
    monkeypatch.setattr(depth, "estimate", gradient)

    real_run, real_popen = subprocess.run, subprocess.Popen

    def guard(cmd):
        exe = Path(str(cmd[0] if isinstance(cmd, (list, tuple)) else cmd)).stem.lower()
        assert not re.match(r"blender|ffmpeg|ffprobe", exe), f"a laptop build started {exe}"

    def run(cmd, *a, **k):
        guard(cmd)
        return real_run(cmd, *a, **k)

    class Popen(real_popen):
        def __init__(self, cmd, *a, **k):
            guard(cmd)
            super().__init__(cmd, *a, **k)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", Popen)
    return tmp_path / "projects"


def photo(path: Path) -> Path:
    Image.new("RGB", (640, 360), (40, 90, 140)).save(path)
    return path


def new(*args: str):
    return CliRunner().invoke(cli.app, ["new", *args])


# ---------------------------------------------------------------- studio new --laptop

def test_the_laptop_starter_builds_with_no_gpu_stack(laptop):
    r = new("my-site", "--laptop")
    assert r.exit_code == 0, r.output
    root = laptop / "my-site"
    site = Project(root).load()
    assert site.theme.style is None, "brand first: the starter wears no style until the user picks one"
    types = [s.type for s in site.sections]
    assert {"type", "intro", "features", "stats", "cta"} <= set(types) and not set(types) & {"film", "sequence", "inside", "light"}
    out = compiler.build_site(Project(root), log=lambda m: None)
    assert "My Site" in out.read_text(encoding="utf-8")


def test_a_photo_opens_the_laptop_starter_as_a_parallax(laptop, tmp_path):
    r = new("my-photos", "--laptop", "--image", str(photo(tmp_path / "my photo.png")))
    assert r.exit_code == 0, r.output
    root = laptop / "my-photos"
    assert (root / "inputs" / "my-photo.png").exists()
    site = Project(root).load()
    assert site.sections[0].type == "parallax" and site.sections[0].steps[0].image == "inputs/my-photo.png"
    compiler.build_site(Project(root), log=lambda m: None)
    assert (root / "dist" / "index.html").exists() and list((root / "dist").rglob("photo0-depth.png"))


def test_a_name_with_yaml_in_it_stays_a_name():
    for title in ("A: b #c", "Quote \" and 'tick'", "Café"):
        assert yaml.safe_load(cli.laptop_starter(title))["name"] == title
        assert yaml.safe_load(cli.laptop_starter(title, "inputs/a b.jpg"))["sections"][0]["steps"][0]["image"] == "inputs/a b.jpg"


def test_the_laptop_options_say_what_is_wrong(laptop, tmp_path):
    assert new("x", "--image", str(photo(tmp_path / "p.png"))).exit_code != 0           # --image needs --laptop
    assert new("x", "--laptop", "--example", "halcyon").exit_code != 0
    assert new("x", "--laptop", "--image", str(tmp_path / "missing.png")).exit_code != 0
    junk = tmp_path / "junk.png"
    junk.write_text("not a picture")
    assert new("x", "--laptop", "--image", str(junk)).exit_code != 0
    assert not (laptop / "x").exists()                                                  # nothing half made


def test_the_plain_starter_is_unchanged(laptop):
    assert new("plain").exit_code == 0
    assert (laptop / "plain" / "site.yaml").read_text(encoding="utf-8") == cli.STARTER


def test_photo_parallax_without_pytorch_says_how_to_get_it(monkeypatch):
    import builtins
    real = builtins.__import__

    def no_torch(name, *a, **k):
        if name in ("torch", "transformers"):
            raise ImportError(f"No module named {name!r}", name=name)
        return real(name, *a, **k)
    depth._load.cache_clear()
    monkeypatch.setattr(builtins, "__import__", no_torch)
    with pytest.raises(BuildError, match="pip install torch transformers"):
        depth._load("small")


# ---------------------------------------------------------------- the claims, checked against the code

def test_every_laptop_scene_is_a_real_scene_type_and_the_gpu_ones_are_not_listed():
    listed = {t.strip() for item in doctor.LAPTOP_SCENES for t in item["uses"].removeprefix("type: ").split(",")}
    assert listed == LAPTOP_TYPES
    assert listed <= set(spec.SCENE_TYPES)
    assert not listed & {"film", "sequence", "inside", "light", "showroom"}


@pytest.mark.parametrize("scene", sorted(LAPTOP_TYPES))
def test_a_laptop_scene_never_reaches_for_comfyui_blender_or_ffmpeg(scene):
    src = (ROOT / "engine" / "scenes" / f"{scene}.py").read_text(encoding="utf-8").lower()
    assert not re.search(r"comfy|blender|ffmpeg|ffprobe|film_build", src), f"engine/scenes/{scene}.py"


def test_every_style_builds_without_a_gpu(laptop, tmp_path):
    """The starter's blocks and type scene, in every style."""
    root = tmp_path / "styles"
    root.mkdir()
    base = yaml.safe_load(cli.laptop_starter("Styles"))
    for style in themes.styles():
        base["theme"]["style"] = style
        (root / "site.yaml").write_text(yaml.safe_dump(base), encoding="utf-8")
        assert compiler.build_site(Project(root), log=lambda m: None).exists(), style


# ---------------------------------------------------------------- studio doctor

def test_doctor_lists_the_laptop_scenes_and_the_gpu_stack():
    s = doctor.laptop_summary()
    labels = [r["label"] for r in s["no_gpu"]]
    assert {"Photo parallax", "Kinetic type", "Maps", "Data", "Code", "Blocks"} <= set(labels)
    assert any(label.startswith("Every style (") for label in labels)
    blocks = next(r for r in s["no_gpu"] if r["label"] == "Blocks")
    assert all(b in blocks["uses"] for b in ("intro", "features", "stats", "cta", "faq"))
    assert len(s["gpu_stack"]) == 2 and all("ComfyUI" in r["detail"] or "Blender" in r["detail"] for r in s["gpu_stack"])


def test_doctor_gives_the_one_line_that_makes_photo_parallax_ready(monkeypatch):
    import importlib.util
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "torch" else real(name, *a))
    row = next(r for r in doctor.laptop_summary()["no_gpu"] if r["label"] == "Photo parallax")
    assert not row["ok"] and row["fix"] == "pip install torch transformers"


def test_doctor_names_remake_only_where_it_exists():
    has = (ROOT / "engine" / "remake.py").exists()
    assert any(r["label"].startswith("Remake") for r in doctor.laptop_summary()["no_gpu"]) == has


def test_doctor_prints_both_lists(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "checks", lambda: [{"name": "x", "ok": True, "detail": "d", "needed_by": "n"}])
    monkeypatch.setenv("COLUMNS", "200")
    doctor.report()
    out = capsys.readouterr().out
    assert "Without a GPU you can build:" in out and "Needs the GPU stack" in out and "studio new my-site --laptop" in out
    assert ".[vector]" in out                                           # square brackets are not swallowed as markup


def test_doctor_marks_fall_back_where_the_console_cannot_show_them():
    from engine.doctor import marks
    assert marks("utf-8") == ("✓", "✗")
    assert marks("cp1252") == ("ok", "no")
    assert marks("no-such-codec") == ("ok", "no")
