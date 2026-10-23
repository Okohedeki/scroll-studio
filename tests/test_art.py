"""theme.art from a file: the sprite sheet a style prints in characters or points. A prompt needs a local image model; a
file does not, so this builds on any machine."""
from __future__ import annotations

import numpy as np
from PIL import Image

from engine import art
from engine.project import Project
from engine.spec import Art


def test_art_taken_from_a_file_builds_its_sheet(tmp_path):
    root = tmp_path / "p"
    (root / "inputs").mkdir(parents=True)
    yy, xx = np.mgrid[0:96, 0:128]
    disc = (((xx - 64) ** 2 + (yy - 48) ** 2) < 30 ** 2) * 200 + 20       # a light disc on a dark ground
    Image.fromarray(disc.astype(np.uint8)).convert("RGB").save(root / "inputs" / "disc.png")
    dist = tmp_path / "dist"
    meta = art.build(Project(root), Art(file="inputs/disc.png", width=64, frames=1), dist, log=lambda m: None)
    assert meta["frames"] == 1 and meta["w"] == 64 and meta["label"] == "disc"
    sheet = Image.open(dist / meta["sheet"])
    assert sheet.mode == "L" and sheet.width == 64 and sheet.getpixel((32, sheet.height // 2)) > 100   # the disc is bright
    assert sheet.getpixel((1, 1)) == 0                                                                 # the ground is black
