"""GPU tests: they run only in the sandboxed GPU runner (ci/gpu-runner, SS_GPU=1), never in the ordinary suite.

Generated pictures are compared with golden files in tests/gpu/golden/ by structure (SSIM), not by bytes: a GPU result
is repeatable on one machine but not bit-identical across drivers. `SS_GPU_RECORD=1` writes missing goldens instead of
failing; every run leaves what it made in tests/gpu/out/ for the workflow to upload."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
GOLDEN, OUT = HERE / "golden", HERE / "out"


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SS_GPU") == "1":
        return
    skip = pytest.mark.skip(reason="GPU test: runs in the sandboxed GPU runner (ci/gpu-runner), set SS_GPU=1")
    for item in items:
        if HERE in Path(item.fspath).parents:
            item.add_marker(skip)


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    from skimage.metrics import structural_similarity
    ga, gb = (np.asarray(x, dtype=np.float32).mean(axis=2) if x.ndim == 3 else np.asarray(x, dtype=np.float32) for x in (a, b))
    return float(structural_similarity(ga, gb, data_range=255.0))


@pytest.fixture
def golden():
    """golden(name, image as uint8 array, min_ssim): save it to out/, compare it with golden/<name>.png."""
    from PIL import Image
    OUT.mkdir(exist_ok=True)

    def check(name: str, img: np.ndarray, min_ssim: float = 0.9) -> float:
        Image.fromarray(img).save(OUT / f"{name}.png")
        ref = GOLDEN / f"{name}.png"
        if not ref.exists():
            if os.environ.get("SS_GPU_RECORD") == "1":
                GOLDEN.mkdir(exist_ok=True)
                Image.fromarray(img).save(ref)
                return 1.0
            pytest.fail(f"no golden for {name}: run once with SS_GPU_RECORD=1 and commit tests/gpu/golden/{name}.png")
        want = np.asarray(Image.open(ref).convert("RGB" if img.ndim == 3 else "L"))
        assert want.shape == img.shape, f"{name}: size {img.shape} differs from the golden's {want.shape}"
        score = ssim(img, want)
        assert score >= min_ssim, f"{name}: SSIM {score:.3f} against the golden (needs {min_ssim}); see tests/gpu/out/{name}.png"
        return score

    return check
