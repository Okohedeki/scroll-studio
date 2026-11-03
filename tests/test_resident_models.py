"""Keeping models warm on the local GPU (issue #4): freeing ComfyUI's VRAM keeps its weight cache, every ComfyUI job's
timings reach `build --profile`, and stills make every scene before any blending pass. No ComfyUI, no GPU."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from PIL import Image, ImageDraw

from engine import profile
from engine.backends import comfy
from engine.project import Project
from engine.router import core
from engine.router.core import Result
from engine.stills import run


class FakeComfy:
    """Answers ComfyUI's /free, /prompt, /history and /queue like a server whose jobs finish at once."""

    def __init__(self):
        self.calls, self.n = [], 0

    def __call__(self, path, data=None, headers=None):
        body = json.loads(data) if data else None
        self.calls.append((path, body))
        if path == "/free":
            return b"{}"
        if path == "/prompt":
            self.n += 1
            return json.dumps({"prompt_id": f"p{self.n}"}).encode()
        if path.startswith("/history/"):
            pid = path.rsplit("/", 1)[1]
            status = {"completed": True, "messages": [["execution_start", {"timestamp": 1000}],
                                                      ["execution_success", {"timestamp": 3500}]]}
            return json.dumps({pid: {"status": status, "outputs": {"save": {"images": []}}}}).encode()
        if path == "/queue":
            return json.dumps({"queue_running": [], "queue_pending": []}).encode()
        raise AssertionError(path)


@pytest.fixture
def server(monkeypatch):
    fake = FakeComfy()
    monkeypatch.setattr(comfy, "_req", fake)
    monkeypatch.setattr(comfy, "_RESIDENT", None)
    monkeypatch.setattr(comfy, "JOBS", [])
    return fake


def graph(*files):
    nodes = {f"n{i}": {"class_type": "Loader", "inputs": {"unet_name": f}} for i, f in enumerate(files)}
    nodes["save"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "x", "steps": 8}}
    return nodes


def test_free_releases_vram_but_keeps_the_weight_cache(server):
    comfy.free()
    comfy.free(deep=True)
    frees = [body for path, body in server.calls if path == "/free"]
    assert frees == [{"unload_models": True, "free_memory": False}, {"unload_models": True, "free_memory": True}]


def test_models_of_reads_every_weights_file_in_a_graph():
    g = graph("z_image_turbo_bf16.safetensors", "sub\\qwen_3_4b_fp8_mixed.safetensors")
    g["n9"] = {"class_type": "Text", "inputs": {"text": "a vase.png on a table"}}
    assert comfy.models_of(g) == {"z_image_turbo_bf16.safetensors", "sub/qwen_3_4b_fp8_mixed.safetensors"}
    assert comfy.model_label(comfy.models_of(g)) == "z_image_turbo_bf16"
    assert comfy.model_label(frozenset()) == "no model"


def test_each_job_is_timed_and_says_whether_it_loaded_its_models(server, monkeypatch):
    monkeypatch.setattr(comfy.time, "sleep", lambda s: None)
    zimage, qwen = graph("z_image_turbo_bf16.safetensors"), graph("qwen_image_edit_2509_fp8.safetensors")
    for g in (zimage, zimage, qwen, zimage):
        comfy.run(g, poll=0)
    comfy.free()
    comfy.run(zimage, poll=0)
    assert [j["loads"] for j in comfy.JOBS] == [True, False, True, True, True]   # a free puts the next one back
    assert all(j["ran"] == 2.5 for j in comfy.JOBS)
    assert comfy.jobs_since(0) == comfy.JOBS


def test_the_profile_reports_comfy_time_per_model():
    jobs = [{"at": 1.0, "model": "z_image", "loads": True, "seconds": 9.0, "queued": 0.5, "ran": 8.0},
            {"at": 2.0, "model": "z_image", "loads": False, "seconds": 3.0, "queued": 0.0, "ran": 3.0},
            {"at": 3.0, "model": "qwen_edit", "loads": True, "seconds": 20.0, "queued": 1.0, "ran": 18.0}]
    rep = profile.report([], [], 40.0, comfy_jobs=jobs)
    assert list(rep["comfy"]) == ["qwen_edit", "z_image"]                         # slowest first
    assert rep["comfy"]["z_image"] == {"jobs": 2, "loads": 1, "seconds": 12.0, "queued": 0.5, "ran": 11.0}
    assert "comfy z_image" in profile.table(rep) and "1 loads" in profile.table(rep)


def test_stills_paint_every_scene_before_any_blending(tmp_path, monkeypatch):
    order = []

    class Studio:
        name, local, kinds = "studio", True, ("image", "edit")

        def available(self):
            return True, ""

        def model(self, kind):
            return f"{kind}-model"

        def run(self, job, out, model=None):
            order.append(job.kind)
            out.parent.mkdir(parents=True, exist_ok=True)
            src = Image.open(job.images[0]).convert("RGB") if job.kind == "edit" else Image.new(
                "RGB", (job.width, job.height), (90, 120, 160))
            src.save(out)
            return Result(self.name, f"{job.kind}-model", 0.0, path=out)

    monkeypatch.setattr(core, "backends", lambda: [Studio()])
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)
    root = tmp_path / "shop"
    im = Image.new("RGB", (300, 360), (246, 246, 244))
    ImageDraw.Draw(im).rounded_rectangle((90, 110, 210, 320), radius=20, fill=(60, 110, 90))
    (root / "inputs").mkdir(parents=True)
    im.save(root / "inputs" / "product.png")
    (root / "project.yaml").write_text(yaml.safe_dump({"name": "Shop", "outputs": {"stills": {
        "photo": "inputs/product.png", "describe": "a planter", "shots": ["lifestyle", "detail"], "directions": 2,
        "candidates": 1, "size": [256, 256]}}}), encoding="utf-8")
    st = run.make(Project(root), log=lambda m: None)
    assert order.count("image") == 2 and order.count("edit") == 4             # a direction's scene serves both shots
    assert order == sorted(order, key=lambda k: k != "image")                  # every scene, then every blend
    assert {c["backend"] for c in st["candidates"]} == {"studio"}              # the painter, not "cache"
