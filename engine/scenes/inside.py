"""inside: the product as the set. The camera flies into the site's product (engine/inside.py plans the route from the
part names; backends/blender_scripts/inside.py draws it with Cycles) and the page happens inside it: every stop is a
named part, its copy arrives with the camera.

Stages, cached: `render` (a PNG per frame, keyed by that frame's own camera and the frames around it that the dissolve
looks at, so changing one stop redraws only the frames near it) and `encode` (WebP sets for desktop and phones with the
vignette and grain, per frame; a still per stop for reduced motion).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from ..config import settings
from ..layout import subject_side, window
from ..project import BuildContext, BuildError, Project
from ..spec import InsideScene, Product

SCRIPT = Path(__file__).resolve().parent.parent / "backends" / "blender_scripts" / "inside.py"
VERSION = 1
CONTEXT_BEHIND, CONTEXT_AHEAD = 14, 18      # frames around one that its dissolve depends on


def _sha(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:14]


def product_of(sec: InsideScene, project: Project) -> Product:
    if sec.model in (None, "product"):
        p = project.load().product
        if p is None:
            raise BuildError(f"inside '{sec.id}': the scene uses the site's product, but the site has no `product:`. Add "
                             f"`product: {{name: ..., model: ...}}` at the top of site.yaml (a model with named parts: "
                             f"STEP/3MF assemblies and multi-object glTF keep them), or give the scene a `model:`")
        return p
    return Product(name=sec.id, model=sec.model, credit=sec.credit)


def route(sec: InsideScene, project: Project, log=print):
    """(product info, GLB, resolution, plan) for an inside scene. Raises BuildError with advice for a model without
    parts or a stop that matches nothing."""
    from .. import inside, product as prod
    p = product_of(sec, project)
    info = prod.product_info(project, p, log)
    glb = prod.normalised_glb(project, p, log)
    aspect = sec.size[0] / sec.size[1]
    res = inside.resolve(sec, info, aspect=aspect)
    plan = inside.make_plan(sec, res, aspect)
    return info, glb, res, plan


def look(sec: InsideScene, theme: dict) -> dict:
    return {"hdri": sec.hdri, "ambient": sec.ambient, "lamp": sec.lamp, "lamp_color": sec.lamp_color, "rim": sec.rim,
            "exposure": sec.exposure, "background": sec.background or theme["colors"]["bg"], "cutaway": sec.cutaway,
            "offset": sec.offset * (1 if subject_side(sec) == "right" else -1)}


def job_stops(res) -> list[dict]:
    return [{"match": [s.spec.part] if s.spec.part else [], "focus": [s.spec.focus] if s.spec.focus else
             ([s.spec.part] if s.spec.part else []), "box": [[float(v) for v in s.lo], [float(v) for v in s.hi]] if s.parts else None}
            for s in res.stops]


def frame_hashes(plan, glb: Path, size, samples, lk: dict, stops: list[dict]) -> list[str]:
    g = {"v": VERSION, "script": _sha(SCRIPT), "glb": glb.name, "size": list(size), "samples": samples, "look": lk,
         "stops": stops, "n": len(plan.frames)}
    fr = plan.frames
    out = []
    for k in range(len(fr)):
        lo, hi = max(0, k - CONTEXT_BEHIND), min(len(fr), k + CONTEXT_AHEAD + 1)
        out.append(_digest([g, [{x: f[x] for x in f if x not in ("k", "p")} for f in fr[lo:hi]], k - lo]))
    return out


def gpu_free_mb() -> Optional[int]:
    """Free VRAM of the first GPU (MiB), or None without nvidia-smi."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0]) if out else None
    except Exception:
        return None


def render_device(log=print) -> str:
    """cpu when STUDIO_INSIDE_DEVICE says so, or when the GPU has less than 2 GB free (other jobs: a Cycles scene that
    cannot get its memory stalls for minutes instead of failing); else gpu."""
    want = os.environ.get("STUDIO_INSIDE_DEVICE", "").lower()
    if want in ("cpu", "gpu"):
        return want
    free = gpu_free_mb()
    if free is not None and free < 2000:
        log(f"  the GPU has {free} MiB free (shared with other jobs): rendering on the CPU (STUDIO_INSIDE_DEVICE=gpu forces the GPU)")
        return "cpu"
    return "gpu"


STALL_SECONDS = float(os.environ.get("STUDIO_INSIDE_STALL", 900))     # no new frame for this long: the render is stuck


def _run_blender(cmd: list, todo: list, hashes: list, frames_dir: Path, log, progress, stall: float) -> tuple[bool, list]:
    """Run the renderer, move each finished frame into place as it is announced. Returns (finished, output tail); a render
    that makes no progress for `stall` seconds (a shared GPU out of memory stalls Cycles instead of failing) is killed."""
    import queue
    import threading
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    q: "queue.Queue" = queue.Queue()

    def pump():
        for line in p.stdout:
            q.put(line)
        q.put(None)
    threading.Thread(target=pump, daemon=True).start()
    tail, done = [], 0
    while True:
        try:
            line = q.get(timeout=stall)
        except queue.Empty:
            p.kill()
            return False, tail
        if line is None:
            break
        tail = (tail + [line])[-40:]
        if line.startswith("FRAME "):
            parts = line.split()
            k = int(parts[2])
            tmp = frames_dir / f"{hashes[k]}.tmp.png"
            if tmp.exists():
                tmp.replace(frames_dir / f"{hashes[k]}.png")
            done += 1
            progress(0.9 * done / len(todo), f"rendering frame {done}/{len(todo)}")
        elif line.startswith(("STOP ", "DISSOLVE", "RAY ", "DEVICE")):
            log("  " + line.strip())
    return p.wait() == 0, tail


def render_frames(project: Project, sec: InsideScene, glb: Path, res, plan, hashes: list[str], indices: list[int],
                  frames_dir: Path, size, samples: int, lk: dict, log=print, progress=lambda f, m="": None) -> None:
    todo = [k for k in indices if not (frames_dir / f"{hashes[k]}.png").exists()]
    if not todo:
        return
    from ..fidelity import would_render
    would_render("inside", f"{sec.id}: {len(todo)} frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    device = render_device(log)
    for attempt in (1, 2):
        todo = [k for k in indices if not (frames_dir / f"{hashes[k]}.png").exists()]
        if not todo:
            return
        job = {"glb": str(glb), "size": list(size), "samples": samples, **lk, "stops": job_stops(res), "frames": plan.frames,
               "render": [{"k": k, "out": str(frames_dir / f"{hashes[k]}.tmp.png")} for k in todo],
               "debug": int(os.environ["SS_INSIDE_DEBUG"]) if os.environ.get("SS_INSIDE_DEBUG") else None, "device": device}
        jf = frames_dir / "job.json"
        jf.write_text(json.dumps(job), encoding="utf-8")
        cmd = [settings()["blender"], "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(SCRIPT), "--", "--job", str(jf)]
        log(f"  $ blender inside.py: {len(todo)} of {len(plan.frames)} frames at {size[0]}x{size[1]}, {samples} samples ({device})")
        try:
            ok, tail = _run_blender(cmd, todo, hashes, frames_dir, log, progress, STALL_SECONDS)
        except FileNotFoundError:
            raise BuildError(f"Blender not found at {settings()['blender']}: install Blender 4.2+ or set `blender` in studio.toml")
        if ok:
            break
        if attempt == 1 and device == "gpu" and (not tail or "Traceback" not in "".join(tail)):
            log(f"  no progress for {int(STALL_SECONDS)} s on the GPU (shared with other jobs?): finishing the remaining frames on the CPU")
            device = "cpu"
            continue
        raise BuildError("Blender render failed:\n" + "".join(tail))
    missing = [k for k in indices if not (frames_dir / f"{hashes[k]}.png").exists()]
    if missing:
        raise BuildError(f"inside '{sec.id}': frame {missing[0]} was not rendered")


def _grade(im, vignette: float, grain: float, k: int):
    import numpy as np
    a = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    h, w = a.shape[:2]
    if vignette > 0:
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2) / 1.4142
        a *= (1 - vignette * np.clip(r, 0, 1) ** 2.2)[..., None]
    if grain > 0:
        rng = np.random.default_rng(1000 + k)
        a += rng.normal(0, grain, (h, w, 1)).astype(np.float32) * (0.35 + 0.65 * (1 - a.mean(axis=2, keepdims=True)))
    from PIL import Image
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def encode_frame(png: Path, k: int, desk: Path, mob: Path, size, vignette: float, grain: float) -> None:
    from PIL import Image
    im = _grade(Image.open(png), vignette, grain, k)
    n = f"{k + 1:04d}.webp"
    im.save(desk / n, quality=82, method=4)
    im.resize((960, round(960 * im.height / im.width)), Image.LANCZOS).save(mob / n, quality=78, method=4)


def build(sec: InsideScene, ctx: BuildContext, theme: dict) -> dict:
    from .. import inside
    if sec.layout != "overlay":
        raise BuildError(f"inside '{sec.id}': only the overlay layout is supported")
    info, glb, res, plan = route(sec, ctx.project, ctx.log)
    for n in plan.notes:
        ctx.log(f"  {n}")
    draft = bool(ctx.options.get("draft"))
    size = (sec.size[0] // 2 // 16 * 16, sec.size[1] // 2 // 16 * 16) if draft else tuple(sec.size)
    samples = max(8, sec.samples // 4) if draft else sec.samples
    lk = look(sec, theme)
    stops = job_stops(res)
    hashes = frame_hashes(plan, glb, size, samples, lk, stops)
    frames_dir = ctx.work / "inside" / "frames"
    pngs = [frames_dir / f"{h}.png" for h in hashes]
    n = len(pngs)

    def render():
        render_frames(ctx.project, sec, glb, res, plan, hashes, list(range(n)), frames_dir, size, samples, lk, ctx.log, ctx.progress)

    ctx.stage("render", {"frames": hashes}, pngs, render)

    desk, mob = ctx.web / "d", ctx.web / "m"
    sig_file = ctx.work / "inside" / "encoded.json"

    def encode():
        for d in (desk, mob):
            d.mkdir(exist_ok=True)
        have = json.loads(sig_file.read_text()) if sig_file.exists() else {}
        new = {}
        for k in range(n):
            sig = _digest([hashes[k], sec.vignette, sec.grain, VERSION])
            new[str(k)] = sig
            if have.get(str(k)) == sig and (desk / f"{k + 1:04d}.webp").exists() and (mob / f"{k + 1:04d}.webp").exists():
                continue
            encode_frame(pngs[k], k, desk, mob, size, sec.vignette, sec.grain)
        for extra in list(desk.glob("*.webp")) + list(mob.glob("*.webp")):
            if int(extra.stem) > n:
                extra.unlink()
        from PIL import Image
        for name, k in [("poster.jpg", 0), ("end.jpg", n - 1)] + [(f"stop{w['stop'] + 1}.jpg", w["frame"]) for w in plan.windows]:
            _grade(Image.open(pngs[k]), sec.vignette, sec.grain, k).save(ctx.web / name, quality=86)
        sig_file.write_text(json.dumps(new))

    outputs = [desk / f"{n:04d}.webp", ctx.web / "end.jpg"]
    ctx.stage("encode", {"r": hashes, "v": sec.vignette, "g": sec.grain, "e": VERSION}, outputs, encode)

    # the copy: steps without an `at` are placed on the route (and the scroll length follows it)
    placed = inside.schedule_steps(sec.steps, plan, sec.outro)
    if sec.length <= 0:
        sec.length = round(max(3.0, plan.screens), 2)
    ctx.log(f"  route: {len(res.stops)} stops, {n} frames, {sec.length} screens of scroll"
            + (f"; copy placed for {len(placed)} step(s)" if placed else ""))
    still = lambda name: ctx.url(ctx.web / name)
    return {
        "count": n, "background": lk["background"], "fit": "cover", "shift": 0,
        "desktop": {"base": ctx.url(desk) + "/", "ext": "webp"},
        "mobile": {"base": ctx.url(mob) + "/", "ext": "webp"},
        "poster": still("poster.jpg"), "end": still("end.jpg"),
        "off": [f["off"] for f in plan.frames], "offset": lk["offset"],
        "wideFill": round(min(0.86, 0.95 * (1 - inside.WIDE_OFFSET * sec.offset)), 3),
        "stops": [{"label": s.label, "frame": w["frame"], "at": w["copy"], "still": still(f"stop{s.index + 1}.jpg")}
                  for s, w in zip(res.stops, plan.windows)],
        "stepsAt": [list(window(st)) if window(st) else None for st in sec.steps], "scrollLength": sec.length,
        "credits": [sec.credit] if sec.credit and sec.model not in (None, "product") else [],
    }


# ---------------------------------------------------------------- authoring: the plan and quick stills (`studio inside`)

def find_section(project: Project, section: Optional[str]) -> InsideScene:
    secs = [s for s in project.load().sections if getattr(s, "type", None) == "inside"]
    if not secs:
        raise BuildError("the site has no `type: inside` section")
    if section:
        hit = [s for s in secs if s.id == section]
        if not hit:
            raise BuildError(f"no inside section '{section}' (have: {', '.join(s.id for s in secs)})")
        return hit[0]
    if len(secs) > 1:
        raise BuildError(f"several inside sections ({', '.join(s.id for s in secs)}): pick one with --section")
    return secs[0]


def preview(project: Project, sec: InsideScene, indices: list[int], samples: int = 24, scale: float = 0.5, log=print,
            out: Optional[Path] = None) -> list[Path]:
    """Quick stills of some frames of the route (cached), and a labelled contact sheet at `out` when given."""
    from ..compile import themes
    theme = themes.resolve(project.load().theme)
    info, glb, res, plan = route(sec, project, log)
    size = (max(16, int(sec.size[0] * scale) // 16 * 16), max(16, int(sec.size[1] * scale) // 16 * 16))
    lk = look(sec, theme)
    stops = job_stops(res)
    hashes = frame_hashes(plan, glb, size, samples, lk, stops)
    d = project.build / sec.id / "inside" / "frames"
    render_frames(project, sec, glb, res, plan, hashes, indices, d, size, samples, lk, log)
    paths = [d / f"{hashes[k]}.png" for k in indices]
    if out is not None:
        from PIL import Image, ImageDraw
        tiles = [Image.open(p).convert("RGB") for p in paths]
        cols = min(3, len(tiles))
        rows = (len(tiles) + cols - 1) // cols
        tw = tiles[0].width
        th = tiles[0].height
        sheet = Image.new("RGB", (cols * tw, rows * th), (12, 12, 14))
        dr = ImageDraw.Draw(sheet)
        for i, (k, im) in enumerate(zip(indices, tiles)):
            x, y = (i % cols) * tw, (i // cols) * th
            sheet.paste(im, (x, y))
            fr = plan.frames[k]
            lab = f"frame {k + 1}/{len(plan.frames)}  p={fr['p']:.2f}"
            if fr["stop"] >= 0:
                lab += f"  {res.stops[fr['stop']].label}"
            dr.rectangle([x, y, x + 8 + 7 * len(lab), y + 18], fill=(0, 0, 0))
            dr.text((x + 4, y + 3), lab, fill=(235, 235, 235))
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out, quality=90)
    return paths
