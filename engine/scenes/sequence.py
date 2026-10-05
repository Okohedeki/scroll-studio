"""sequence: a 3D model rendered by Blender (Cycles, GPU) into frames, scrubbed on a canvas by scroll."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from ..config import settings
from ..project import BuildContext, BuildError, file_key
from ..spec import SequenceScene

SCRIPT = Path(__file__).resolve().parent.parent / "backends" / "blender_scripts" / "turntable.py"
VERSION = 2


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def build(sec: SequenceScene, ctx: BuildContext, theme: dict) -> dict:
    model = ctx.project.path(sec.model)
    if not model.exists():
        raise BuildError(f"sequence '{sec.id}': model not found: {sec.model}")
    raw = ctx.work / "render"
    frames = [raw / "frames" / f"{i:04d}.png" for i in range(1, sec.frames + 1)]
    draft = bool(ctx.options.get("draft"))
    size = (sec.size[0] // 2, sec.size[1] // 2) if draft else sec.size
    samples = max(8, sec.samples // 4) if draft else sec.samples
    key = {"v": VERSION, "model": file_key(model), "frames": sec.frames, "size": size, "samples": samples,
           "keys": sec.keys, "hdri": sec.hdri}

    def render():
        cmd = [settings()["blender"], "-b", "--factory-startup", "-P", str(SCRIPT), "--", "--model", str(model),
               "--out", str(raw), "--frames", str(sec.frames), "--size", f"{size[0]}x{size[1]}", "--samples", str(samples),
               "--keys", json.dumps(sec.keys), "--hdri", sec.hdri]
        ctx.log("  $ blender turntable.py " + sec.model)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        tail = []
        for line in p.stdout:
            tail = (tail + [line])[-40:]
            if line.startswith("FRAME "):
                n, total = line.split()[1].split("/")
                ctx.progress(int(n) / int(total) * 0.9, f"rendering frame {n}/{total}")
        if p.wait() != 0:
            raise BuildError("Blender render failed:\n" + "".join(tail))

    ctx.stage("render", key, frames, render)

    bg = sec.background or theme["colors"]["bg"]
    desk, mob = ctx.web / "d", ctx.web / "m"

    def encode():
        for d in (desk, mob):
            d.mkdir(exist_ok=True)
        for i, f in enumerate(frames, 1):
            im = Image.open(f).convert("RGBA")
            im.save(desk / f"{i:04d}.webp", quality=84, method=5)
            im.resize((960, round(960 * im.height / im.width)), Image.LANCZOS).save(mob / f"{i:04d}.webp", quality=80, method=5)
        for name, f in (("poster.jpg", frames[0]), ("end.jpg", frames[-1])):
            im = Image.open(f).convert("RGBA")
            flat = Image.new("RGB", im.size, _hex(bg))
            flat.paste(im, mask=im.split()[3])
            flat.save(ctx.web / name, quality=88)
    ctx.stage("encode", {"r": key, "bg": bg}, [desk / f"{sec.frames:04d}.webp", ctx.web / "end.jpg"], encode)
    return {
        "count": sec.frames, "background": bg, "fit": "contain",
        "desktop": {"base": ctx.url(desk) + "/", "ext": "webp"},
        "mobile": {"base": ctx.url(mob) + "/", "ext": "webp"},
        "poster": ctx.url(ctx.web / "poster.jpg"), "end": ctx.url(ctx.web / "end.jpg"),
    }
