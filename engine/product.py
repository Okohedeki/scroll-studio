"""The site's product (`site.product`), declared once and used everywhere.

The model is resolved (project file, URL or TRELLIS photo), converted (STEP via OpenCascade, 3MF via trimesh),
normalised by Blender (axes, units, base at the origin, part materials, decimation only when absurdly heavy) and
cached as one GLB under `.build/_product/`. Stills of it are rendered by Cycles in a studio light, also cached.

Public API, for scene builders, the CLI/MCP and the trailer builder. `product` may always be omitted (or None):
it then means `site.product` of the project.

    get(project, product=None) -> Product
        The site's product spec, or BuildError if the site declares none.
    normalised_glb(project, product=None, log=print) -> Path
        `.build/_product/<digest>.glb`: Y-up, metres, base centre at the origin, front towards +Z (glTF), part
        materials applied; explodable parts carry node extras ss_part / ss_explode (offset in metres).
    product_info(project, product=None, log=print) -> dict
        The parts report written beside the GLB: size [x, y, z] m (z up), height, triangles, units, parts
        [{index, name, mesh, path, triangles, materials [{name, color}], size, centre, explode, anchor}], rules
        [{match, material, hits}].
    product_still(project, product=None, view="three-quarter", size=(1600, 1200), background="transparent",
                  log=print, **shot) -> Path
        A PNG still. view: front, three-quarter, side, top, back, hero-low, exploded. background: "transparent"
        (RGBA with a soft shadow), "theme" (the site theme's background) or a hex colour. shot: any ProductShot
        field (yaw, pitch, zoom, explode, lens, hdri, samples, shadow).
    credits(product) -> list[str]        footer credit line(s) for the model
    concept_line(product) -> str | None  "Concept page. Not affiliated with <maker>." when product.concept
    scene_still(project, product, view, size, scene, log=print, harmonise=0.3, seed=7, **shot) -> Path
        The product rendered into a generated scene (a prompt): perspective-matched Z-Image backdrop, lit by it,
        composited, harmonised by Qwen-Image-Edit and checked (needs ComfyUI). `image: {product: v, scene: "..."}`.
    take_track(project, section_id, log=print) -> Path
        `.build/<section>/product/track.json` for a film section with a take product: per frame, where the product
        is on screen (normalised 0-1, y down): {"fps", "size", "frames": [{"f", "visible", "centre", "base",
        "box": [x0, y0, x1, y1]}]}. Built with the take (stage `track`); this computes it if missing.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .config import ROOT, settings
from .project import BuildError, Project
from .fidelity import placeholder, preview, would_render
from .spec import ImageInput, Product, ProductShot

VERSION = 1           # bump when the normalisation changes, so every cached GLB is rebuilt
STILL_VERSION = 2
SCRIPTS = Path(__file__).resolve().parent / "backends" / "blender_scripts"
FORMATS = (".glb", ".gltf", ".obj", ".fbx", ".stl", ".ply", ".step", ".stp", ".3mf")
TESSELLATION = {"draft": (0.1, 0.5), "normal": (0.05, 0.3), "fine": (0.02, 0.15)}   # linear mm, angular rad
UNITS_3MF = {"millimeter": "mm", "centimeter": "cm", "meter": "m", "inch": "in", "foot": "ft"}

# view name -> camera (yaw 0 is the front; pitch is the camera's height in degrees above the horizon)
VIEWS = {
    "front": {"yaw": 0, "pitch": 6},
    "three-quarter": {"yaw": -35, "pitch": 20},
    "side": {"yaw": 90, "pitch": 6},
    "top": {"yaw": 0, "pitch": 89},
    "back": {"yaw": 180, "pitch": 12},
    "hero-low": {"yaw": -28, "pitch": -7, "lens": 32, "low": True, "zoom": 1.05},
    "exploded": {"yaw": -35, "pitch": 24, "explode": 1.0},
    "detail": {"aim": True, "lens": 85},     # a macro view of shot `part`, aimed from the side it faces out of
}


def _sha(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:14]


def _cache(project: Project) -> Path:
    d = project.build / "_product"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get(project: Project, product: Optional[Product] = None) -> Product:
    if product is not None:
        return product
    p = project.load().product
    if p is None:
        raise BuildError("this needs the site's product: add `product: {name: ..., model: ...}` at the top of site.yaml")
    return p


def _blender(script: str, args: list, log=print, what: str = "Blender") -> None:
    cmd = [settings()["blender"], "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(SCRIPTS / script), "--",
           *[str(x) for x in args]]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise BuildError(f"Blender not found at {settings()['blender']}: install Blender 4.2+ or set `blender` in studio.toml")
    tail = []
    for line in p.stdout:
        tail = (tail + [line])[-40:]
        if line.startswith(("IMPORTED", "NORMALISED", "DECIMATE", "EXPORTED")):
            log("  " + line.strip())
    if p.wait() != 0:
        raise BuildError(f"{what} failed:\n" + "".join(tail))


def _source(project: Project, product: Product, log=print) -> tuple[Path, str, Optional[str], dict]:
    """The model as a file Blender can import, its original format, units to force (or None), and a content key."""
    from .inputs import resolve_path
    if product.model:
        src = resolve_path(project, product.model, log)
        ext = src.suffix.lower()
        if ext not in FORMATS:
            raise BuildError(f"product.model {product.model}: unsupported format {ext or '(none)'} "
                             f"(use {', '.join(f.lstrip('.') for f in FORMATS)})")
        key = {"model": _sha(src), "ext": ext}
        cache = _cache(project)
        if ext in (".step", ".stp"):
            lin, ang = TESSELLATION[product.tessellation]
            key["tess"] = [lin, ang]
            out = cache / f"step_{_digest(key)}.glb"
            if not out.exists():
                would_render("product model", f"convert {src.name}")
                log(f"  converting STEP with OpenCascade ({product.tessellation}: {lin} mm, {ang} rad): {src.name}")
                _child(["step", src, out, lin, ang], out)
            if product.units != "auto":
                log("  note: STEP files carry their own units; product.units is ignored for them")
            return out, "step", "m", key
        if ext == ".3mf":
            out = cache / f"3mf_{_digest(key)}.glb"
            meta = cache / f"3mf_{_digest(key)}.json"
            if not (out.exists() and meta.exists()):
                would_render("product model", f"convert {src.name}")
                log(f"  converting 3MF: {src.name}")
                info = _child(["3mf", src, out], out)
                meta.write_text(json.dumps(info))
            units = json.loads(meta.read_text()).get("units", "millimeter")
            return out, "3mf", product.units if product.units != "auto" else UNITS_3MF.get(units, "mm"), key
        return src, ext.lstrip("."), None, key
    if product.from_photo:
        from .backends.trellis import image_to_mesh
        photo = resolve_path(project, product.from_photo, log)
        key = {"photo": _sha(photo)}
        if not (_cache(project) / f"trellis_{_digest(key)}").exists():
            would_render("product model", f"TRELLIS.2 from {photo.name}")
        mesh = image_to_mesh(photo, _cache(project) / f"trellis_{_digest(key)}", log)
        return mesh, "ply", None, key
    raise BuildError("product needs `model` (a 3D file or URL) or `from_photo`")


def _child(args: list, out: Path) -> dict:
    p = subprocess.run([sys.executable, "-m", "engine.backends.cad", *[str(a) for a in args]], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not out.exists():
        raise BuildError("model conversion failed:\n" + (p.stderr or p.stdout)[-2000:])
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {}


def _prepare(project: Project, product: Product, log=print) -> tuple[Path, Path]:
    from .inputs import resolve_path
    src, fmt, units, skey = _source(project, product, log)
    textures = {}
    for r in product.parts:
        if r.texture and r.texture not in textures:
            textures[r.texture] = str(resolve_path(project, r.texture, log))
    opts = {"up": product.up, "units": units or product.units, "rotation": list(product.rotation),
            "parts": [r.model_dump(mode="json", exclude_none=True) for r in product.parts],
            "max_triangles": product.max_triangles, "textures": textures}
    if product.exclude:
        opts["exclude"] = list(product.exclude)
    key = {"v": VERSION, "script": _sha(SCRIPTS / "product_prep.py"), "src": skey, "fmt": fmt, "opts": {**opts, "textures": {k: _sha(Path(v)) for k, v in textures.items()}}}
    cache = _cache(project)
    digest = _digest(key)
    glb, report = cache / f"{digest}.glb", cache / f"{digest}.json"
    if glb.exists() and report.exists():
        return glb, report
    would_render("product model", f"normalise {product.name}")
    log(f"  normalising product model ({fmt}) -> {glb.name}")
    optfile = cache / f"{digest}.opts.json"
    optfile.write_text(json.dumps(opts, indent=1), encoding="utf-8")
    tmp = cache / f"{digest}.tmp.glb"
    _blender("product_prep.py", ["--model", src, "--fmt", fmt, "--opts", optfile, "--out", tmp, "--report", report],
             log, "normalising the product model")
    tmp.replace(glb)
    info = json.loads(report.read_text(encoding="utf-8"))
    for r in info.get("rules", []):
        if not r["hits"]:
            log(f"  warning: product.parts rule match={r['match']!r}"
                f"{' material=' + repr(r['material']) if r['material'] else ''} matched nothing (see studio product --parts)")
    mb = glb.stat().st_size / 1e6
    if mb > 40:
        log(f"  note: the product GLB is {mb:.0f} MB; lower max_triangles or tessellation for the live showroom")
    return glb, report


def normalised_glb(project: Project, product: Optional[Product] = None, log=print) -> Path:
    return _prepare(project, get(project, product), log)[0]


def product_info(project: Project, product: Optional[Product] = None, log=print) -> dict:
    return json.loads(_prepare(project, get(project, product), log)[1].read_text(encoding="utf-8"))


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def theme_background(project: Project) -> str:
    from .compile import themes
    return themes.resolve(project.load().theme)["colors"]["bg"]


def product_still(project: Project, product: Optional[Product] = None, view: str = "three-quarter",
                  size: tuple[int, int] = (1600, 1200), background: str = "transparent", log=print, **shot) -> Path:
    product = get(project, product)
    if view not in VIEWS:
        raise BuildError(f"unknown product view {view!r} (have: {', '.join(VIEWS)})")
    glb, report = _prepare(project, product, log)
    cam = dict(VIEWS[view])
    for k in ("yaw", "pitch", "zoom", "explode", "lens", "part", "fstop"):
        if shot.get(k) is not None:
            cam[k] = shot[k]
    if shot.get("exposure"):
        cam["exposure"] = float(shot["exposure"])
    if view == "detail" and not cam.get("part"):
        raise BuildError("the detail view needs `part`: a glob on a part name (studio product <project> --parts)")
    if cam.get("explode"):
        n = len(json.loads(report.read_text(encoding="utf-8"))["parts"])
        if n < 2:
            raise BuildError(f"the exploded view needs a model with several parts; {product.name}'s model has {n}")
    samples, hdri, shadow = int(shot.get("samples") or 128), shot.get("hdri") or "studio", shot.get("shadow", True)
    w, h = int(size[0]), int(size[1])
    pv = preview()
    if pv is not None:   # a storyboard: few samples (and small at sketch); keyed by both, so never taken for a final
        samples = min(samples, pv.samples)
        w, h = max(64, round(w * pv.scale)), max(64, round(h * pv.scale))
    key = {"v": STILL_VERSION, "script": _sha(SCRIPTS / "product_still.py"), "glb": glb.name, "cam": cam, "size": [w, h], "samples": samples, "hdri": hdri, "shadow": bool(shadow)}
    stills = _cache(project) / "stills"
    stills.mkdir(exist_ok=True)
    digest = _digest(key)
    png = stills / f"{digest}.png"
    if not png.exists():
        would_render("product still", f"{product.name} {view} {w}x{h}")
        log(f"  product still: {view} {w}x{h}, {samples} samples")
        tmp = stills / f"{digest}.tmp.png"
        _blender("product_still.py", ["--glb", glb, "--out", tmp, "--size", f"{w}x{h}", "--view", json.dumps(cam),
                                      "--samples", samples, "--hdri", hdri, "--shadow", int(bool(shadow))],
                 log, "rendering the product still")
        tmp.replace(png)
    if background in (None, "", "transparent"):
        return png
    colour = theme_background(project) if background in ("theme", "auto") else background
    if not colour.startswith("#"):
        raise BuildError(f"product still background {background!r}: use transparent, theme or a hex colour")
    flat = stills / f"{digest}_{colour.lstrip('#').lower()}.png"
    if not flat.exists():
        from PIL import Image
        im = Image.open(png).convert("RGBA")
        bg = Image.new("RGBA", im.size, _hex(colour) + (255,))
        Image.alpha_composite(bg, im).convert("RGB").save(flat)
    return flat


def image_still(project: Project, ref: ImageInput, log=print, alpha: bool = False) -> Path:
    """`image: {product: <view or shot>}`: transparent where the caller can show it (alpha), else the theme bg."""
    shot = ref.product if isinstance(ref.product, ProductShot) else ProductShot(view=ref.product)
    scene = shot.scene or ref.scene
    if scene:
        opts = shot.model_dump(exclude={"view", "background", "scene", "harmonise", "seed"})
        return scene_still(project, None, shot.view, tuple(ref.size), scene, log, shot.harmonise,
                           shot.seed if "seed" in shot.model_fields_set else ref.seed, **opts)
    bg = shot.background
    if bg == "auto":
        bg = "transparent" if alpha else "theme"
    opts = shot.model_dump(exclude={"view", "background"})
    return product_still(project, None, shot.view, tuple(ref.size), bg, log, **opts)


def credits(product: Optional[Product]) -> list[str]:
    if product is None:
        return []
    line = product.credit or (f"{product.name} 3D model by {product.maker}" if product.maker else f"{product.name} 3D model")
    if product.licence and product.licence.lower() not in line.lower():
        line += f", {product.licence}"
    return [line]


def concept_line(product: Optional[Product]) -> Optional[str]:
    if product is None or not product.concept:
        return None
    return f"Concept page. Not affiliated with {product.maker}." if product.maker else "Concept page. Not an official product page."


def take_height(project: Project, layer) -> float:
    """A take product's height: as set, else the site product's real height (metres) when it uses site.product."""
    if layer.height is not None:
        return float(layer.height)
    if not (layer.model or layer.from_photo) and project.load().product is not None:
        return float(product_info(project)["height"])
    return 1.0


def take_track(project: Project, section_id: str, log=print) -> Path:
    from .project import BuildContext
    from .scenes import film
    site = project.load()
    sec = next((s for s in site.sections if getattr(s, "id", None) == section_id), None)
    if sec is None or sec.type != "film" or not sec.take or not sec.take.product:
        raise BuildError(f"section {section_id!r} is not a film with a take product")
    ctx = BuildContext(project, section_id, log=log)
    film.take_shot(sec, ctx)
    return film.track(sec, ctx)


# ---------------------------------------------------------------- the product in a generated scene

SCENE_VERSION = 3
FRAMING_VERSION = 1     # bump when product_still.py frames differently (the painted backdrop follows the framing)
HARMONISE = ("Blend the product naturally into the scene's lighting: match the light direction, colour temperature, "
             "reflections and soft contact shadow of the room. Keep the product's shape, proportions, edges, details, "
             "text and colours exactly as they are. Do not move, resize or redesign the product.")


def _floor_depth(cam: dict):
    """A depth guide of the floor the product stands on, as seen by the still's camera (white near, black sky)."""
    import numpy as np
    W, H = cam["size"]
    s = cam["sensor"] / cam["lens"]
    sx, sy = cam["shift"]
    px = (np.arange(W) + 0.5) / W - 0.5
    py = 0.5 - (np.arange(H) + 0.5) / H
    PX, PY = np.meshgrid(px, py)
    if W >= H:
        dx, dy = (PX - sx) * s, (PY * H / W - sy) * s
    else:
        dx, dy = (PX * W / H - sx) * s, (PY - sy) * s
    M = np.array(cam["matrix"], dtype=np.float64)
    R, o = M[:3, :3], M[:3, 3]
    wx = R[0, 0] * dx + R[0, 1] * dy - R[0, 2]
    wy = R[1, 0] * dx + R[1, 1] * dy - R[1, 2]
    wz = R[2, 0] * dx + R[2, 1] * dy - R[2, 2]
    norm = np.sqrt(wx ** 2 + wy ** 2 + wz ** 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (cam["floor"] - o[2]) / wz
    hit = (wz < -1e-6) & (t > 0)
    dist = np.where(hit, t * norm, np.inf)
    near = float(np.min(dist[hit])) if hit.any() else 1.0
    inv = np.where(hit, near / dist, 0.0)
    img = (np.clip(inv, 0, 1) ** 0.8 * 255).astype(np.uint8)
    return np.dstack([img] * 3)


def _edges_kept(a, b, mask) -> dict:
    """How much of the product survived an edit: edge F1 (2 px tolerance) and colour drift (Lab) inside its mask."""
    import cv2
    import numpy as np
    m = mask > 0.5
    if m.sum() < 50:
        return {"f1": 1.0, "delta_e": 0.0}
    region = cv2.dilate(m.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    ea = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), 60, 160) > 0
    eb = cv2.Canny(cv2.cvtColor(b, cv2.COLOR_RGB2GRAY), 60, 160) > 0
    ea, eb = ea & region, eb & region
    k = np.ones((5, 5), np.uint8)
    da, db = cv2.dilate(ea.astype(np.uint8), k) > 0, cv2.dilate(eb.astype(np.uint8), k) > 0
    recall = (ea & db).sum() / max(ea.sum(), 1)
    precision = (eb & da).sum() / max(eb.sum(), 1)
    f1 = 2 * recall * precision / max(recall + precision, 1e-6)
    inner = cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    la = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
    lb = cv2.cvtColor(b, cv2.COLOR_RGB2LAB).astype(np.float32)
    de = float(np.mean(np.linalg.norm((la - lb)[inner], axis=1))) if inner.any() else 0.0
    return {"f1": round(float(f1), 3), "delta_e": round(de, 2)}


def scene_still(project: Project, product: Optional[Product], view: str, size: tuple[int, int], scene: str,
                log=print, harmonise: float = 0.3, seed: int = 7, **shot) -> Path:
    """The product rendered into a generated scene: Z-Image paints the scene to the still's camera (a depth guide of
    the floor, so horizon and perspective match), the product is re-lit by an environment made from that scene
    (its brightest region as the sun, its ground under the shadow), composited with PlateMatch, then a light
    Qwen-Image-Edit pass blends it in. If that pass changed the product (edge F1 < 0.7 or colour drift > 9), the
    Cycles product is put back over the blended scene through its own matte."""
    import cv2
    import numpy as np
    from .backends import comfy
    from .scenes import film_build as fb
    product = get(project, product)
    glb, report = _prepare(project, product, log)
    w, h = (int(size[0]) // 16 * 16, int(size[1]) // 16 * 16)
    cam_v = dict(VIEWS.get(view, VIEWS["three-quarter"]))
    for k in ("yaw", "pitch", "explode", "lens", "part", "fstop"):
        if shot.get(k) is not None:
            cam_v[k] = shot[k]
    if shot.get("exposure"):
        cam_v["exposure"] = float(shot["exposure"])
    cam_v["zoom"] = float(shot.get("zoom") or 1.0) * 0.82      # leave room around it: it stands in a place
    samples, shadow = int(shot.get("samples") or 128), True
    pv = preview()
    if pv is not None:   # a storyboard: few samples and no harmonising pass (the painted scene is shared with finals)
        samples, harmonise = min(samples, pv.samples), 0.0
    key = {"v": SCENE_VERSION, "glb": glb.name, "cam": cam_v, "size": [w, h], "scene": scene, "seed": seed,
           "harmonise": harmonise, "samples": samples, "still": _sha(SCRIPTS / "product_still.py")}
    d = _cache(project) / "scenes" / _digest(key)
    final = d / "final.png"
    if final.exists():
        return final
    would_render("scene still", f"{product.name} {view} in '{scene[:60]}'")
    if pv is not None and not pv.comfy:
        # a sketch: the studio still on a card naming the scene, until the scene is painted
        from PIL import Image
        card = Image.open(placeholder(project.build / "_storyboard" / "placeholders", f"Scene: {scene}", (w, h)))
        prod = Image.open(product_still(project, product, view if view in VIEWS else "three-quarter", (w, h),
                                        "transparent", log, **{k: v for k, v in shot.items() if k in
                                                               ("yaw", "pitch", "zoom", "explode", "lens", "part")}))
        card = card.convert("RGBA")
        card.alpha_composite(prod.convert("RGBA").resize(card.size))
        out = project.build / "_storyboard" / "placeholders" / f"placeholder_scene_{d.name}_{pv.samples}.png"
        card.convert("RGB").save(out)
        return out
    if not comfy.alive():
        raise BuildError(f"`scene:` paints the product's surroundings with Z-Image, but ComfyUI is not running at "
                         f"{comfy.COMFY}. Start it (docs/INSTALL.md), or drop `scene:` for a studio still.")
    d.mkdir(parents=True, exist_ok=True)
    # the framing and the painted backdrop are kept apart from the lighting, so re-lighting never repaints the scene
    frame_v = {k: v for k, v in cam_v.items() if k != "exposure"}
    bkey = {"v": FRAMING_VERSION, "glb": glb.name, "cam": frame_v, "size": [w, h], "scene": scene, "seed": seed}
    b = _cache(project) / "scenes" / ("bg_" + _digest(bkey))
    b.mkdir(parents=True, exist_ok=True)
    # 1. the camera and a quick studio pass (framing, matte)
    cam_json, studio, mask = b / "camera.json", b / "studio.png", b / "mask.png"
    if not (cam_json.exists() and mask.exists()):
        _blender("product_still.py", ["--glb", glb, "--out", studio, "--size", f"{w}x{h}", "--view", json.dumps(cam_v),
                                      "--samples", 16, "--shadow", 1, "--camera", cam_json, "--mask", mask],
                 log, "framing the product")
    cam = json.loads(cam_json.read_text(encoding="utf-8"))
    # 2. the scene, painted to that camera
    bg = b / "scene.png"
    if not bg.exists():
        depth = b / "depth.png"
        cv2.imwrite(str(depth), _floor_depth(cam))
        prompt = (f"{scene}. The surface in the middle of the foreground is clear and empty, no objects on it. "
                  f"Photograph, natural light, realistic materials, shallow depth of field.")
        log(f"  scene: Z-Image to the product's camera: {scene[:70]}")
        kcfg = dict(comfy.ZIMAGE, control_strength=0.55)
        images = comfy.run(comfy.build_keyframe_graph(kcfg, prompt, comfy.upload(str(depth)), w, h, seed,
                                                      prefix=f"studio/scene_{d.name}"), poll=2)
        tmp = comfy.fetch(images, str(b / "_z"))
        Path(tmp, "0001.png").replace(bg)
    bg_rgb = cv2.cvtColor(cv2.imread(str(bg)), cv2.COLOR_BGR2RGB)
    bg_rgb = cv2.resize(bg_rgb, (w, h), interpolation=cv2.INTER_AREA)
    m_alpha = cv2.imread(str(mask), cv2.IMREAD_UNCHANGED)[..., 3].astype(np.float32) / 255
    # 3. light from the scene itself
    env_json = d / "env.json"
    if not env_json.exists():
        small = cv2.resize(bg_rgb, (480, round(480 * h / w)), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        lin = fb._srgb_to_linear(small).astype(np.float32)
        # no highlight lift here: a sun lamp from the brightest region carries the key light, and a lifted bright
        # window would blow out anything that reflects it (an aluminium lid facing the sky)
        env = fb.env_from_frame(lin, cam["matrix"], cam["lens"], cam["sensor"], w / h, lift=0.0)
        sun, strength = fb.env_sun(env)
        ys, xs = np.nonzero(m_alpha > 0.5)
        if len(ys):
            y0, x0, x1 = min(h - 2, int(ys.max() + h * 0.02)), int(xs.min()), int(xs.max())
            patch = bg_rgb[y0:min(h, y0 + max(4, h // 40)), x0:x1].reshape(-1, 3).astype(np.float32) / 255
            ground = fb._srgb_to_linear(patch.mean(0)).tolist() if len(patch) else [0.2, 0.2, 0.2]
        else:
            ground = [0.2, 0.2, 0.2]
        cv2.imwrite(str(d / "env.hdr"), env[..., ::-1])
        env_json.write_text(json.dumps({"file": str(d / "env.hdr"), "ground": ground, "sun": sun,
                                        "sun_strength": strength, "strength": 1.0}), encoding="utf-8")
    lit = d / "lit.png"
    if not lit.exists():
        log(f"  scene: the product lit by the scene ({samples} samples)")
        _blender("product_still.py", ["--glb", glb, "--out", lit, "--size", f"{w}x{h}", "--view", json.dumps(cam_v),
                                      "--samples", samples, "--shadow", int(shadow), "--env", env_json],
                 log, "lighting the product in the scene")
    # 4. composite, graded to the scene
    rgba = fb.read_rgba(lit, (w, h))
    plate = bg_rgb.astype(np.float32) / 255
    comp = fb.PlateMatch(True, None, 0.0).apply(plate, rgba) if rgba is not None else plate
    comp8 = (np.clip(comp, 0, 1) * 255 + 0.5).astype(np.uint8)
    cv2.imwrite(str(d / "composite.png"), cv2.cvtColor(comp8, cv2.COLOR_RGB2BGR))
    out8, info = comp8, {"harmonise": harmonise}
    # 5. a light harmonising edit, checked against the product's own edges
    if harmonise > 0:
        log(f"  scene: Qwen-Image-Edit harmonising pass (strength {harmonise})")
        g = comfy.build_qwen_edit_graph([comfy.upload(str(d / "composite.png"))], HARMONISE, seed, 30,
                                        prefix=f"studio/harm_{d.name}", megapixels=round(w * h / 1e6, 2))
        g["ks"]["inputs"]["denoise"] = float(harmonise)
        images = comfy.run(g, poll=2)
        tmp = comfy.fetch(images, str(d / "_q"))
        ed = cv2.cvtColor(cv2.imread(str(Path(tmp, "0001.png"))), cv2.COLOR_BGR2RGB)
        ed = cv2.resize(ed, (w, h), interpolation=cv2.INTER_LANCZOS4)
        cv2.imwrite(str(d / "harmonised.png"), cv2.cvtColor(ed, cv2.COLOR_RGB2BGR))
        score = _edges_kept(comp8, ed, m_alpha)
        info.update(score)
        if score["f1"] < 0.7 or score["delta_e"] > 9:
            # the edit redrew the product: keep its light and shadow around it, put the real product back
            matte = cv2.GaussianBlur(m_alpha, (0, 0), 0.8)[..., None]
            out8 = (ed.astype(np.float32) * (1 - matte) + comp8.astype(np.float32) * matte + 0.5).astype(np.uint8)
            info["product"] = "re-composited (the edit changed it)"
        else:
            out8 = ed
            info["product"] = "kept by the edit"
        log(f"  scene: edge F1 {score['f1']}, colour drift {score['delta_e']}: product {info['product']}")
    (d / "check.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    cv2.imwrite(str(final), cv2.cvtColor(out8, cv2.COLOR_RGB2BGR))
    return final
