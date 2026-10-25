"""Resolve spec inputs to files: project files as-is, `generate:` images through local Z-Image Turbo."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional

from .project import BuildError, Project
from .spec import ImageInput, ImageRef


def resolve_path(project: Project, ref: str, log=print) -> Path:
    """A project file, or an http(s) URL downloaded once into .build/_downloads (cached by URL)."""
    if ref.startswith(("http://", "https://")):
        import requests
        name = hashlib.sha1(ref.encode()).hexdigest()[:12] + "_" + ref.split("?")[0].rsplit("/", 1)[-1][-60:]
        out = project.build / "_downloads" / name
        if not out.exists():
            from .fidelity import would_render
            would_render("download", ref)
            out.parent.mkdir(parents=True, exist_ok=True)
            log(f"  downloading {ref}")
            ua = {"User-Agent": "ScrollStudio/0.1 (+https://github.com/Okohedeki/scroll-studio)"}
            with requests.get(ref, stream=True, timeout=60, headers=ua) as r:
                r.raise_for_status()
                tmp = out.with_suffix(out.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.replace(out)
            _lfs_check(ref, out, log)
        return out
    p = project.path(ref)
    if not p.exists():
        raise BuildError(f"input not found: {ref}")
    return p


def _lfs_check(url: str, out: Path, log=print) -> None:
    """A big file in a GitHub repo is often stored with Git LFS: raw.githubusercontent.com then serves a 130-byte
    pointer, not the file. Fetch the real content from media.githubusercontent.com instead."""
    if out.stat().st_size > 1024 or not out.read_bytes().startswith(b"version https://git-lfs"):
        return
    import re
    import requests
    m = re.match(r"https://(?:raw\.githubusercontent\.com/([^/]+)/([^/]+)/(.+)|github\.com/([^/]+)/([^/]+)/(?:raw|blob)/(.+))", url)
    if not m:
        out.unlink()
        raise BuildError(f"{url} is a Git LFS pointer, not the file; use the host's direct download link")
    owner, repo, rest = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), m.group(5), m.group(6))
    media = f"https://media.githubusercontent.com/media/{owner}/{repo}/{rest.split('?')[0]}"
    log(f"  {Path(url.split('?')[0]).name} is stored with Git LFS: downloading it from {media}")
    tmp = out.with_suffix(out.suffix + ".part")
    with requests.get(media, stream=True, timeout=120, headers={"User-Agent": "ScrollStudio/0.1"}) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(out)


# Image-input fields added after earlier builds were keyed: left out of keys while unset, so adding a field never
# re-renders finished work.
LATE_FIELDS = ("product", "scene", "beat_frame", "region", "match", "cinemagraph", "medium", "calm")


def stable_dump(model) -> dict:
    """model_dump for cache keys: late fields that are unset (None) are dropped, at any depth."""
    def strip(v):
        if isinstance(v, dict):
            return {k: strip(x) for k, x in v.items() if not (k in LATE_FIELDS and x is None)}
        if isinstance(v, list):
            return [strip(x) for x in v]
        return v
    return strip(model.model_dump(mode="json"))


def image_key(ref: ImageRef) -> dict:
    if isinstance(ref, str):
        return {"file": ref}
    d = stable_dump(ref)
    d.pop("credit", None)
    d.pop("cinemagraph", None)       # a cinemagraph moves part of the picture on the page; the picture itself is the same
    return d


def generated_path(project: Project, ref: ImageInput) -> Path:
    """Where a `generate:` image is cached: .build/_generated/<digest of prompt, size and seed>.png."""
    w, h = (int(v) // 16 * 16 for v in ref.size)
    return project.build / "_generated" / f"{generated_digest(treated_prompt(project, ref), w, h, ref.seed)}.png"


def treated_prompt(project: Project, ref: ImageInput) -> str:
    """The prompt as sent to the image model: the spec's prompt with the site's `imagery:` treatment (engine/imagery.py),
    unchanged when the site sets none (so its cache keys and files stay as they were)."""
    from . import imagery
    return imagery.treat(project, ref.generate, medium=ref.medium, calm=ref.calm)


def generated_digest(prompt: str, w: int, h: int, seed: int) -> str:
    return hashlib.sha1(json.dumps([prompt, w, h, seed]).encode()).hexdigest()[:12]


def edit_path(project: Project, ref: ImageInput, srcs: list[Path]) -> Path:
    """Where an `edit:` image is cached, given its resolved source images (the edit's source, then its refs)."""
    from .project import file_key
    e = ref.edit
    key = [[file_key(s) for s in srcs], e.instruction, e.seed, e.steps, 2]
    if e.region is not None:       # a region is part of the key only when set: edits made before it keep their images
        from .region import edit_key
        key.append(edit_key(e.region))
    digest = hashlib.sha1(json.dumps(key).encode()).hexdigest()[:12]
    return project.build / "_generated" / f"edit_{digest}.png"


def resolve_image(project: Project, ref: ImageRef, log=print, alpha: bool = False) -> Path:
    """alpha: the caller can show a transparent image (hero/product blocks), so a product still may stay RGBA."""
    if isinstance(ref, str):
        ref = ImageInput(file=ref)
    if ref.crop:
        src = resolve_image(project, ref.model_copy(update={"crop": None}), log, alpha)
        digest = hashlib.sha1(json.dumps([str(src), src.stat().st_size, list(ref.crop)]).encode()).hexdigest()[:12]
        out = project.build / "_generated" / f"crop_{digest}.png"
        if not out.exists():
            from PIL import Image
            im = Image.open(src)
            x0, y0, x1, y1 = ref.crop
            out.parent.mkdir(parents=True, exist_ok=True)
            im.crop((round(x0 * im.width), round(y0 * im.height), round(x1 * im.width), round(y1 * im.height))).save(out)
        return out
    if ref.match is not None:             # designed to match another section's last frame (engine/cuts_design.py)
        from .cuts_design import match_image
        return match_image(project, ref, log)
    if ref.beat_frame is not None:        # a frame of a beat of a film (a frozen moment's last frame, say)
        from .freeze_beats import beat_frame_image
        return beat_frame_image(project, ref.beat_frame, log)
    if ref.product is not None:
        from .product import image_still
        return image_still(project, ref, log, alpha)
    if ref.file:
        src = resolve_path(project, ref.file, log)
        if (ref.medium and ref.medium != "none") or ref.calm:     # an image's own medium works on a file too
            return _art_directed(project, ref, src, log)
        return src
    if ref.edit:
        return _edit(project, ref, log)
    if ref.gradient:
        w, h = (int(v) for v in ref.size)
        digest = hashlib.sha1(json.dumps([ref.gradient.model_dump(mode="json"), w, h, ref.seed, 1]).encode()).hexdigest()[:12]
        out = project.build / "_generated" / f"grad_{digest}.png"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            render_gradient(ref.gradient, (w, h), ref.seed).save(out)
        return out
    if not ref.generate:
        raise BuildError("an image input needs `file`, `generate`, `gradient` or `product`")
    w, h = (int(v) // 16 * 16 for v in ref.size)
    prompt = treated_prompt(project, ref)
    raw = generate_image(project, prompt, w, h, ref.seed, log)
    if raw.parent != project.build / "_generated":       # a storyboard's stand-in card: nothing to treat
        return raw
    return _art_directed(project, ref, raw, log, lambda k: generate_image(project, prompt, w, h, ref.seed + 1000 * k,
                                                                          log, free=False))


def art_direction(project: Project, ref: ImageInput) -> tuple[Optional[str], Optional[dict], Optional[float]]:
    """(named medium, its palette, grain) this image is drawn in (engine/medium.py), or Nones: its own `medium:`, else
    the site's `imagery.medium` when it is a named one (generated images only: a photo or logo you supply is left as
    it is unless it asks)."""
    from . import imagery, medium
    if ref.medium == "none" or (not ref.medium and not ref.generate):
        return None, None, None
    im, named = imagery.look(project, ref.medium)
    if not named:
        return None, None, None
    return named, medium.site_palette(project, named, im), im.grain


def hero_image(project: Project, block) -> tuple[Optional[ImageRef], Optional[str]]:
    """A hero block's picture with the composition rule (engine/medium.py): in a named medium, the side its headline is
    set on (`align`) is kept calm unless the image says `calm:` itself. (image, calm side or None)."""
    img = block.image
    if not isinstance(img, ImageInput):
        return img, None
    if img.calm is None and (img.generate or img.file) and art_direction(project, img)[0]:
        img = img.model_copy(update={"calm": "left" if block.align == "left" else "center"})
    return img, img.calm


def _art_directed(project: Project, ref: ImageInput, raw: Path, log=print, regenerate=None) -> Path:
    """The image in its named medium and with its calm side checked (engine/medium.py); `raw` when neither applies."""
    name, pal, grain = art_direction(project, ref)
    if not name and not ref.calm:
        return raw
    from . import medium
    return medium.finish(project, raw, name, pal, ref.seed, grain, ref.calm, regenerate, log=log)


def generate_image(project: Project, prompt: str, w: int, h: int, seed: int, log=print, free: bool = True) -> Path:
    """A Z-Image Turbo still for exactly this prompt, cached by prompt, size and seed in .build/_generated. The prompt is
    sent as given (an `imagery:` treatment is already in it); `studio directions` renders its boards through here too."""
    out = project.build / "_generated" / f"{generated_digest(prompt, w, h, seed)}.png"
    digest = out.stem
    if out.exists():
        return out
    from .fidelity import placeholder, preview, would_render
    would_render("image", prompt)
    pv = preview()
    if pv is not None and not pv.comfy:   # a sketch storyboard: a card for the shot to come, outside the cache
        return placeholder(project.build / "_storyboard" / "placeholders", prompt, (w, h))
    from .backends import comfy
    if not comfy.alive():
        raise BuildError("this image is generated locally, but ComfyUI is not running at "
                         f"{comfy.COMFY}. Start it (docs/INSTALL.md) or replace `generate:` with a `file:`.")
    log(f"  generating image ({w}x{h}, seed {seed}): {prompt[:80]}…")
    if free:         # a batch of stills (storyboard boards) frees the other models once, then keeps Z-Image loaded
        comfy.free()
    images = comfy.run(comfy.build_txt2img_graph(prompt, w, h, seed, prefix=f"studio/{digest}"), poll=2)
    tmp = comfy.fetch(images, str(out.parent / f"_{digest}"))
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(Path(tmp) / "0001.png"), out)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def _edit(project: Project, ref: ImageInput, log=print) -> Path:
    """An image made by editing others with Qwen-Image-Edit, cached by the sources' content and the instruction."""
    from .backends import comfy
    e = ref.edit
    srcs = [resolve_image(project, r, log) for r in [e.source, *e.refs[:2]]]
    out = edit_path(project, ref, srcs)
    digest = out.stem[len("edit_"):]
    if out.exists():
        return out
    from .fidelity import placeholder, preview, would_render
    would_render("edit", e.instruction)
    pv = preview()
    if pv is not None and not pv.comfy:
        from PIL import Image
        return placeholder(project.build / "_storyboard" / "placeholders", f"Edit: {e.instruction}",
                           Image.open(srcs[0]).size)
    if not comfy.alive():
        raise BuildError(f"this image is edited locally with Qwen-Image-Edit, but ComfyUI is not running at {comfy.COMFY}.")
    out.parent.mkdir(parents=True, exist_ok=True)

    def qwen(first: Path) -> Path:
        """Qwen-Image-Edit of `first` (the source, or a crop of it) with the edit's references; the result's path."""
        comfy.free()
        names = [comfy.upload(str(s)) for s in [first, *srcs[1:]]]
        images = comfy.run(comfy.build_qwen_edit_graph(names, e.instruction, e.seed, e.steps, prefix=f"studio/edit_{digest}"), poll=2)
        tmp = comfy.fetch(images, str(out.parent / f"_edit_{digest}"))
        res = out.parent / f"_edit_{digest}.png"
        shutil.move(str(Path(tmp) / "0001.png"), res)
        shutil.rmtree(tmp, ignore_errors=True)
        return res

    if e.region is not None:
        from . import region
        log(f"  editing image inside a region (Qwen-Image-Edit, seed {e.seed}): {e.instruction[:80]}")
        try:
            region.apply(project, srcs[0], e.region, out, qwen, log)
        finally:
            (out.parent / f"_edit_{digest}.png").unlink(missing_ok=True)
            comfy.free()
        return out
    log(f"  editing image (Qwen-Image-Edit, seed {e.seed}): {e.instruction[:80]}")
    res = qwen(srcs[0])
    shutil.move(str(res), out)
    comfy.free()
    return out


def credit(ref: Optional[ImageRef]) -> Optional[str]:
    return ref.credit if isinstance(ref, ImageInput) else None


def _rgb(hex_color: str):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def render_gradient(g, size: tuple[int, int], seed: int = 7):
    """A `gradient:` backdrop: colour stops swept along `angle`, glows blended in, stars and grain on top."""
    import math
    import numpy as np
    from PIL import Image
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(g.angle)
    dx, dy = math.sin(a), -math.cos(a)                      # 180° sweeps top to bottom, 90° left to right
    extent = abs(w / 2 * dx) + abs(h / 2 * dy) or 1.0
    t = np.clip((((xx - w / 2) * dx + (yy - h / 2) * dy) / extent + 1) / 2, 0, 1)
    stops = np.array([_rgb(c) for c in g.colors], dtype=np.float32)
    pos = t * (len(stops) - 1)
    i = np.minimum(np.floor(pos).astype(int), len(stops) - 2)
    f = (pos - i)[..., None]
    img = stops[i] * (1 - f) + stops[i + 1] * f
    for glow in g.glows:
        r = max(glow.radius * max(w, h), 1.0)
        d = np.hypot(xx - glow.x * w, yy - glow.y * h) / r
        k = (glow.strength * np.exp(-d * d))[..., None]
        img = img * (1 - k) + np.array(_rgb(glow.color), dtype=np.float32) * k
    rng = np.random.default_rng(seed)
    if g.stars:
        for _ in range(g.stars):
            sx, sy = rng.uniform(0, w), rng.uniform(0, h * 0.7)
            size_px, bright = rng.uniform(0.6, 1.8), rng.uniform(0.25, 0.9)
            x0, x1 = max(int(sx - 5), 0), min(int(sx + 6), w)
            y0, y1 = max(int(sy - 5), 0), min(int(sy + 6), h)
            if x1 <= x0 or y1 <= y0:
                continue
            d = np.hypot(xx[y0:y1, x0:x1] - sx, yy[y0:y1, x0:x1] - sy) / size_px
            k = (bright * np.exp(-d * d))[..., None]
            img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - k) + 255 * k
    if g.grain:
        img = img + rng.normal(0, g.grain * 255, (h, w, 1)).astype(np.float32)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
