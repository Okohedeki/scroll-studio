"""The chunked restore pass (film_build.stage_upscale) keeps each chunk by the frames it is made of: a film re-joined
after one shot changed restores only the chunks whose frames changed. ComfyUI is faked; ffmpeg is real."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from engine.scenes import film_build as fb

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def _film(path: Path, colors: list[int], size=(64, 48)):
    """A film with one flat grey level per frame."""
    frames = path.parent / (path.stem + "_frames")
    frames.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(colors):
        Image.fromarray(np.full((size[1], size[0], 3), c, np.uint8)).save(frames / f"{i + 1:04d}.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "24", "-i", str(frames / "%04d.png"), "-c:v", "libx264",
                    "-crf", "0", "-pix_fmt", "yuv444p", str(path)], check=True)
    shutil.rmtree(frames)
    return path


@pytest.fixture
def fake_comfy(monkeypatch):
    calls = []

    def run(graph, *a, **k):
        calls.append(graph["clip"])
        return [graph["clip"]] * 20

    def fetch(images, out):
        Path(out).mkdir(parents=True, exist_ok=True)
        for i, _ in enumerate(images):
            Image.fromarray(np.full((48, 64, 3), 128, np.uint8)).save(Path(out) / f"{i + 1:04d}.png")
        return out

    monkeypatch.setattr(fb.ltx_comfy, "free", lambda: None)
    monkeypatch.setattr(fb.ltx_comfy, "upload", lambda p: Path(p).name)
    monkeypatch.setattr(fb.ltx_comfy, "build_seedvr2_graph", lambda cfg, name, prefix="": {"clip": name})
    monkeypatch.setattr(fb.ltx_comfy, "run", run)
    monkeypatch.setattr(fb.ltx_comfy, "fetch", fetch)
    return calls


def _pass(out: Path, src: Path):
    shot = {"id": "t", "fps": 24, "duration": 60 / 24, "ltx": {},
            "upscale": {"method": "seedvr2", "resolution": 48, "chunk": 20, "overlap": 4}}
    fb.stage_upscale(shot, str(out), SimpleNamespace(source=str(src), dry_run=False, force=False, seconds=None))
    return out / "gen" / "gen_sr.mp4"


def test_a_rejoined_film_restores_only_the_chunks_that_changed(tmp_path, fake_comfy):
    colors = [10 + 3 * i for i in range(60)]
    work = tmp_path / "w"
    first = _pass(work, _film(tmp_path / "a.mp4", colors))
    assert first.exists()
    n = len(fake_comfy)
    assert n == 4                                           # 60 frames in chunks of 20 overlapping by 4
    # the same frames in a new file (a re-join): nothing is restored again
    fake_comfy.clear()
    _pass(work, _film(tmp_path / "b.mp4", colors))
    assert fake_comfy == []
    # the last shot changed: only the chunk that holds those frames is restored again
    changed = colors[:55] + [200] * 5             # frames 55-59: only in the last chunk (40-59)
    fake_comfy.clear()
    _pass(work, _film(tmp_path / "c.mp4", changed))
    assert len(fake_comfy) == 1


def test_chunk_key_follows_the_frames_and_the_settings(tmp_path):
    a = _film(tmp_path / "a.mp4", [10 + i for i in range(30)])
    k = fb.chunk_key(a, 0, 20, 24, {"resolution": 1088}, "seedvr2")
    assert k == fb.chunk_key(a, 0, 20, 24, {"resolution": 1088}, "seedvr2")
    assert k != fb.chunk_key(a, 4, 20, 24, {"resolution": 1088}, "seedvr2")       # other frames
    assert k != fb.chunk_key(a, 0, 20, 24, {"resolution": 2160}, "seedvr2")       # another target
    assert k != fb.chunk_key(a, 0, 20, 24, {"resolution": 1088}, "ltx", "a prompt")
