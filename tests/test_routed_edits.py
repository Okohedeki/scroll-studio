"""Builders' image edits through the model router (issue #172): a provider edit backend does the edit only when the
spec's `models:` picks it; otherwise the local ComfyUI path runs exactly as before. No network, no GPU."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from engine import fidelity, inputs, layers, light
from engine.backends import comfy, detail
from engine.project import BuildError, Project
from engine.router import core, use_policy
from engine.router.core import Result
from engine.spec import ImageInput


class Editor:
    name, local, kinds = "editor", False, ("edit",)

    def __init__(self):
        self.calls = []

    def available(self):
        return True, ""

    def model(self, kind):
        return "e1"

    def run(self, job, out, model=None):
        self.calls.append(job)
        with Image.open(job.images[0]) as im:
            Image.new("RGB", im.size, (10, 200, 10)).save(out)
        return Result(self.name, "e1", 0.0, path=out)


@pytest.fixture
def editor(monkeypatch):
    e = Editor()
    monkeypatch.setattr(core, "backends", lambda: [e])
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)
    monkeypatch.setattr(comfy, "alive", lambda: False)
    monkeypatch.setattr(comfy, "free", lambda: (_ for _ in ()).throw(AssertionError("ComfyUI touched")))
    monkeypatch.setattr(fidelity, "preview", lambda: None)
    yield e
    use_policy(None)


def site_project(tmp_path: Path, models: str = "") -> Project:
    root = tmp_path / "p"
    (root / "inputs").mkdir(parents=True)
    Image.new("RGB", (64, 48), (120, 120, 120)).save(root / "inputs" / "room.png")
    (root / "site.yaml").write_text(f"name: T\nsections: []\n{models}", encoding="utf-8")
    return Project(root)


def edit_ref(**kw) -> ImageInput:
    return ImageInput.model_validate({"edit": {"source": "inputs/room.png", "instruction": "paint it green", **kw}})


def test_an_edit_input_runs_on_the_provider_the_spec_picks(editor, tmp_path):
    p = site_project(tmp_path, "models: {prefer: provider}\n")
    out = inputs.resolve_image(p, edit_ref(), log=lambda m: None)
    assert editor.calls and editor.calls[0].instruction == "paint it green"
    assert out.name.endswith("-editor.png") and np.asarray(Image.open(out))[0, 0, 1] == 200
    assert inputs.resolve_image(p, edit_ref(), log=lambda m: None) == out and len(editor.calls) == 1


def test_without_a_choice_the_local_path_and_its_error_are_unchanged(editor, tmp_path):
    p = site_project(tmp_path)                    # local preferred, ComfyUI down: no paid fallback
    with pytest.raises(BuildError, match="ComfyUI is not running"):
        inputs.resolve_image(p, edit_ref(), log=lambda m: None)
    assert not editor.calls


def test_relight_and_the_zoom_detail_pass_follow_the_builds_policy(editor, tmp_path):
    src = tmp_path / "world.png"
    Image.new("RGB", (40, 30), (50, 50, 50)).save(src)
    with pytest.raises(BuildError, match="relighting needs ComfyUI"):
        light.relight(src, "night", 1, 20, tmp_path / "lit.png", "t", log=lambda m: None)
    use_policy({"prefer": "provider"})
    assert light.relight(src, "night", 1, 20, tmp_path / "lit.png", "t", log=lambda m: None).exists()
    out = detail.qwen_detail(src, tmp_path / "zoom.png", "more detail", 1, log=lambda m: None)
    assert Image.open(out).size == (40, 30) and len(editor.calls) == 2


def test_the_layers_plate_follows_the_builds_policy(editor, tmp_path):
    frozen = np.full((30, 40, 3), 90, np.uint8)
    assert layers.paint_out(frozen, "remove the people", 1, tmp_path, lambda m: None) is None   # local, ComfyUI down
    use_policy({"prefer": "provider"})
    cache = (tmp_path / "plate.png", "k1")
    got = layers.paint_out(frozen, "remove the people", 1, tmp_path, lambda m: None, cache=cache)
    assert got.shape == frozen.shape and got[0, 0, 1] == 200 and cache[0].exists()
