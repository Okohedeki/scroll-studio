"""The GPU paths the engine generates with, each run small and seeded: torch on CUDA, the frozen-moment warp, depth,
Cycles on the GPU and a Z-Image still through ComfyUI. Skipped outside the GPU runner (see conftest.py)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest

from engine import freeze as fz
from engine.config import settings

PHOTO = Path(__file__).resolve().parents[2] / "examples" / "atelier-sfumato" / "inputs" / "mona_lisa.jpg"


def test_torch_sees_the_gpu():
    import torch
    assert torch.cuda.is_available(), "no CUDA device in the runner"
    a = torch.randn(1024, 1024, device="cuda")
    assert torch.allclose((a @ a.T).cpu(), (a.cpu() @ a.cpu().T), atol=1e-2)


def _scene(w=192, h=128):
    yy, xx = np.mgrid[0:h, 0:w]
    rgb = np.stack([(xx * 255 // w), (yy * 255 // h), ((xx + yy) % 64) * 4], axis=-1).astype(np.uint8)
    depth = np.clip(((xx - w / 2) ** 2 + (yy - h / 2) ** 2) ** 0.5 / (w / 2), 0, 1).astype(np.float32)
    return rgb, 1 - depth


def test_the_frozen_moment_warp_on_the_gpu_matches_the_cpu():
    rgb, depth = _scene()
    cam = [{"t": 0, "box": [0, 0, 1, 1]}, {"t": 1, "box": [0.25, 0.25, 0.75, 0.75]}]
    kw = dict(size=(192, 128), seconds=1.0, parallax=0.6)
    gpu = list(fz.render_frames(rgb, depth, cam, device="cuda", **kw))
    cpu = list(fz.render_frames(rgb, depth, cam, device="cpu", **kw))
    diff = max(np.abs(g.astype(int) - c.astype(int)).mean() for g, c in zip(gpu, cpu))
    assert diff < 1.5, f"the CUDA warp drifts from the CPU one by {diff:.2f} levels on average"


def test_depth_anything_on_the_gpu(golden):
    from PIL import Image
    from engine.backends import depth
    d = depth.estimate(Image.open(PHOTO).convert("RGB").resize((384, 576)), "small")
    assert d.shape == (576, 384) and 0 <= d.min() and d.max() <= 1
    golden("depth_small", (d * 255).astype(np.uint8), min_ssim=0.95)


CYCLES = """
import bpy, sys
bpy.ops.wm.read_factory_settings(use_empty=True)
s = bpy.context.scene
s.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
kind = None
for k in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = k
        prefs.get_devices()
        if any(d.type == k for d in prefs.devices):
            kind = k
            break
    except TypeError:
        pass
for d in prefs.devices:
    d.use = d.type == kind
s.cycles.device = "GPU"
s.cycles.samples = 16
s.cycles.seed = 7
s.render.resolution_x, s.render.resolution_y = 160, 96
bpy.ops.mesh.primitive_uv_sphere_add(radius=1)
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, -1))
bpy.ops.object.light_add(type="AREA", location=(2, -2, 3))
bpy.context.object.data.energy = 500
bpy.ops.object.camera_add(location=(0, -6, 1.5), rotation=(1.35, 0, 0))
s.camera = bpy.context.object
s.render.filepath = sys.argv[-1]
bpy.ops.render.render(write_still=True)
print("DEVICE", kind)
"""


def test_cycles_renders_on_the_gpu(golden, tmp_path):
    from PIL import Image
    script = tmp_path / "cycles.py"
    script.write_text(CYCLES)
    out = tmp_path / "sphere.png"
    r = subprocess.run([settings()["blender"], "-b", "--factory-startup", "-P", str(script), "--", str(out)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    kind = next((line.split()[1] for line in r.stdout.splitlines() if line.startswith("DEVICE")), "None")
    assert kind in ("OPTIX", "CUDA"), f"Cycles found no GPU device:\n{r.stdout[-1500:]}"
    golden("cycles_sphere", np.asarray(Image.open(out).convert("RGB")), min_ssim=0.85)


def test_zimage_still_through_comfyui(golden, tmp_path):
    from PIL import Image
    from engine.backends import comfy
    assert comfy.alive(), "ComfyUI is not running in the runner (the workflow starts it)"
    graph = comfy.build_txt2img_graph("a white ceramic mug on a walnut table, soft window light, product photo",
                                      512, 512, 7, "ss_gpu_test")
    images = comfy.run(graph, poll=1, timeout=600)
    path = Path(comfy.fetch(images, str(tmp_path)))
    path = path if path.is_file() else next(path.glob("*.png"))
    img = np.asarray(Image.open(path).convert("RGB"))
    assert img.shape == (512, 512, 3) and img.std() > 10, "the still is blank"
    golden("zimage_mug", img, min_ssim=0.8)
