"""Frozen moments in a project: finding the frame to freeze, running the render for a beat, `beat_frame` images, and
the stand-ins the storyboard and `build --only` use. The camera and the render itself are in engine/freeze.py.

Folder of a frozen beat (.build/<section>/beats/<id>/), each file with a `.key` beside it holding the digest of what
made it, so changing the camera re-renders in seconds and never repeats the upscale or the depth:

    frozen.png  the source frame fitted to beat_res      up.png     the upscaled frame      depth.npy  its prepared depth
    clip.mp4    the render                               first.png / last.png  its first and last frame, lossless
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import freeze as fz
from .freeze import FPS, VERSION, CameraPath, View
from .project import BuildError


class NotRendered(BuildError):
    """A frame was asked of a beat whose clip does not exist yet."""


_LENIENT = False        # build --only: a beat that is not rendered stands in with its storyboard still (set_lenient)


def digest(*parts) -> str:
    import hashlib
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def fkey(p: Path) -> Optional[dict]:
    """file_key of a file, None when it is not there."""
    if not p.exists():
        return None
    st = p.stat()
    return {"path": p.name, "size": st.st_size, "mtime": int(st.st_mtime)}


# ---------------------------------------------------------------- finding beats

def beat_dir(project, sec, b) -> Path:
    return project.build / sec.id / "beats" / b.id


def beat_clip_path(project, sec, b) -> Path:
    return beat_dir(project, sec, b) / "clip.mp4"


def beat_size(sec) -> tuple[int, int]:
    return sec.beat_res[0] // 32 * 32, sec.beat_res[1] // 32 * 32


def find_beat(project, beat_id: str, section: Optional[str] = None):
    """(film section, beat) of a beat id anywhere in the site."""
    site = project.load()
    hits = [(s, b) for s in site.sections if s.type == "film" and (section is None or s.id == section)
            for b in s.beats if b.id == beat_id]
    if not hits:
        raise BuildError(f"beat '{beat_id}' not found" + (f" in section '{section}'" if section else " in any film section"))
    if len(hits) > 1:
        raise BuildError(f"beat id '{beat_id}' is in more than one film section ({', '.join(s.id for s, _ in hits)}): "
                         "name the section")
    return hits[0]


# ---------------------------------------------------------------- reading frames

def _cached(path: Path, key, make: Callable[[Path], None]) -> Path:
    """`path`, made by make(tmp) unless a file with this key is there already (the key sits beside it)."""
    stamp = path.with_name(path.name + ".key")
    d = digest(key)
    if path.exists() and stamp.exists() and stamp.read_text() == d:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("_tmp_" + path.name)
    make(tmp)
    tmp.replace(path)
    stamp.write_text(d)
    return path


def read_rgb(p: Path) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(p).convert("RGB"))


def save_rgb(a: np.ndarray, p: Path) -> None:
    from PIL import Image
    Image.fromarray(a).save(p)


def _decode(clip: Path, before: list, after: list, size: tuple[int, int]) -> list[np.ndarray]:
    from .config import settings
    W, H = size
    r = subprocess.run([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", *before, "-i", str(clip), *after,
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    n = len(r.stdout) // (W * H * 3)
    return [np.frombuffer(r.stdout, np.uint8, W * H * 3, i * W * H * 3).reshape(H, W, 3).copy() for i in range(n)]


def _clip_info(clip: Path) -> tuple[tuple[int, int], int]:
    from .project import probe
    info = probe(clip)
    return (int(info["width"]), int(info["height"])), max(1, round(float(info.get("duration") or 0) * FPS))


def clip_frames(clip: Path, at, window: int = 1) -> list[np.ndarray]:
    """Frames of a clip: `first`, `last` (the last `window` frames, oldest first) or the frame at a time in seconds."""
    size, _ = _clip_info(clip)
    if at == "first":
        out = _decode(clip, [], ["-frames:v", "1"], size)
    elif at == "last":
        k = max(1, window)
        out = _decode(clip, ["-sseof", f"-{(k + 3) / FPS:.3f}"], [], size)[-k:]
    else:
        out = _decode(clip, ["-ss", f"{float(at):.4f}"], ["-frames:v", "1"], size)
    if not out:
        raise BuildError(f"could not read a frame of {clip}")
    return out


def beat_candidates(project, sec, b, at, window: int, log) -> list[np.ndarray]:
    """The frames a `beat_frame` / `freeze.from` chooses between, as RGB arrays (oldest first). A frozen beat is
    rendered first when it is not (it takes seconds); a generated beat must have its clip."""
    clip = beat_clip_path(project, sec, b)
    bdir = beat_dir(project, sec, b)
    if b.freeze is not None:
        from .fidelity import preview
        if preview() is None:                       # a storyboard preview reads the clip as it is, never renders
            render_beat(project, sec, b, log)       # digest-cached: instant when it is up to date
        if at in ("first", "last") and window == 1 and (bdir / f"{at}.png").exists():
            return [read_rgb(bdir / f"{at}.png")]
    elif not clip.exists():
        raise NotRendered(f"beat '{b.id}' is not rendered yet: build it first (another beat needs its frame)")
    else:
        # the lossless PNGs the clip was cut from, while they still match it: no re-encode artefacts
        frames = sorted((bdir / "frames").glob("*.png"))[round(b.trim * FPS):]
        if frames and abs(len(frames) - _clip_info(clip)[1]) <= 1 and at in ("first", "last"):
            pick = frames[:1] if at == "first" else frames[-max(1, window):]
            return [read_rgb(p) for p in pick]
    return clip_frames(clip, at, window)


def standin_image(project, sec, b, log, at: str = "last") -> Path:
    """A still for a beat that is not rendered: its storyboard still (never a new render, never stamped): a frozen beat's
    source, a generated beat's end image or start image. For the storyboard and for `build --only`."""
    from .fidelity import previewing
    from .inputs import resolve_image
    from .spec import ImageInput
    W, H = beat_size(sec)
    with previewing("sketch"):
        if b.freeze is not None:
            f = b.freeze
            if f.image is not None:
                return resolve_image(project, f.image, log)
            sb = next((x for x in sec.beats if x.id == f.from_), None)
            if sb is None:
                sec, sb = find_beat(project, f.from_)
            return standin_image(project, sec, sb, log, "last")
        if at == "last" and b.end_image is not None:
            return resolve_image(project, b.end_image, log)
        return resolve_image(project, b.image if b.image else ImageInput(generate=b.prompt, size=(W, H), seed=b.seed), log)


def _fit(im, size):
    from PIL import Image, ImageOps
    return ImageOps.fit(im.convert("RGB"), tuple(size), Image.LANCZOS)


def crop_view(im, view: View, size: tuple[int, int]):
    """A flat crop of `im` (already fitted to the output aspect) at a view, resized to `size`."""
    from PIL import Image
    W, H = im.size
    box = ((view.cx - view.w / 2) * W, (view.cy - view.w / 2) * H, (view.cx + view.w / 2) * W, (view.cy + view.w / 2) * H)
    return im.crop(tuple(round(v) for v in box)).resize(tuple(size), Image.LANCZOS)


def standin_frame(project, sec, b, at, log) -> Path:
    """The storyboard's idea of a beat's frame: a frozen beat's last view of its source (a flat crop), else the beat's
    still. Written under .build/_storyboard/, which no full build reads."""
    from PIL import Image
    img = standin_image(project, sec, b, log, "first" if at == "first" else "last")
    if b.freeze is None or at == "first":
        return img
    size = beat_size(sec)
    view = CameraPath(b.freeze.camera, b.freeze.ease).at(1.0)
    out = project.build / "_storyboard" / "freeze" / f"end_{digest(str(img), fkey(img), view.__dict__, size)}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        crop_view(_fit(Image.open(img), size), view, size).save(out)
    return out


def beat_frame_image(project, bf, log=print) -> Path:
    """The image a `beat_frame:` names, written under .build/_generated (a beat that starts on it then starts exactly
    where the other one ended)."""
    from .fidelity import is_planning, preview, would_render
    sec, b = find_beat(project, bf.beat, bf.section)
    clip = beat_clip_path(project, sec, b)

    def target() -> Path:
        return project.build / "_generated" / f"bf_{digest('bf', bf.model_dump(mode='json'), sec.id, fkey(clip))}.png"

    out = target()
    if out.exists() and clip.exists():
        return out
    if is_planning():
        would_render("beat frame", f"{bf.beat} {bf.at}")
    if preview() is not None and not clip.exists():
        return standin_frame(project, sec, b, bf.at, log)
    window = 6 if (bf.pick == "sharpest" and bf.at == "last") else 1
    try:
        cands = beat_candidates(project, sec, b, bf.at, window, log)
    except NotRendered:
        if _LENIENT:
            log(f"  beat '{b.id}' is not rendered: its storyboard still stands in for its frame")
            return standin_frame(project, sec, b, bf.at, log)
        raise
    out = target()                                   # a frozen beat may just have been rendered: its clip is new
    i = fz.sharpest(cands) if len(cands) > 1 else len(cands) - 1 if bf.at == "last" else 0
    out.parent.mkdir(parents=True, exist_ok=True)
    save_rgb(cands[i], out)
    return out


def beat_frame_deps(project, ref) -> list:
    """Cache-key parts for every `beat_frame` inside an image ref (also nested in an edit): the beat's clip as it is now,
    so a re-rendered beat re-renders whatever starts from it."""
    out: list = []
    if ref is None or isinstance(ref, str):
        return out
    bf = getattr(ref, "beat_frame", None)
    if bf is not None:
        try:
            sec, b = find_beat(project, bf.beat, bf.section)
            out.append({"beat_frame": bf.beat, "clip": fkey(beat_clip_path(project, sec, b))})
        except BuildError:
            out.append({"beat_frame": bf.beat, "clip": None})
    if getattr(ref, "edit", None) is not None:
        for r in [ref.edit.source, *ref.edit.refs]:
            out += beat_frame_deps(project, r)
    return out


# ---------------------------------------------------------------- a frozen beat

def _image_key(project, ref):
    from .inputs import stable_dump
    if isinstance(ref, str):
        if ref.startswith("http"):
            return ref
        p = project.path(ref)
        return fkey(p) or ref
    return stable_dump(ref)


def beat_key(project, sec, b) -> dict:
    """The stage key of a frozen beat: everything it renders from. The source is the clip of the beat it freezes (so a
    re-rendered walk re-freezes) or the image input; new keys only: generated beats keep theirs."""
    f = b.freeze
    W, H = beat_size(sec)
    d = f.model_dump(mode="json", by_alias=True, exclude={"image"})
    for late in ("detail", "layers"):             # fields added later: part of a key only when set, so old renders stay valid
        if d.get(late) is None:
            d.pop(late, None)
    key = {"freeze": d, "res": [W, H], "seconds": b.seconds, "v": VERSION}
    if f.from_:
        try:
            ssec, sb = find_beat(project, f.from_) if all(x.id != f.from_ for x in sec.beats) else (sec, next(x for x in sec.beats if x.id == f.from_))
            key["from"] = fkey(beat_clip_path(project, ssec, sb))
        except BuildError:
            key["from"] = None
    else:
        key["image"] = _image_key(project, f.image)
        key["deps"] = beat_frame_deps(project, f.image)
    if b.trim:
        key["trim"] = b.trim
    return key


def _source_frame(project, sec, b, log) -> Path:
    """frozen.png: the frame to freeze, fitted to beat_res (cached by what it came from)."""
    from PIL import Image
    from .inputs import resolve_image
    f = b.freeze
    size = beat_size(sec)
    bdir = beat_dir(project, sec, b)
    views = CameraPath(f.camera, f.ease).boxes()
    if f.from_:
        ssec, sb = (sec, next(x for x in sec.beats if x.id == f.from_)) if any(x.id == f.from_ for x in sec.beats) \
            else find_beat(project, f.from_)
        clip = beat_clip_path(project, ssec, sb)
        # a freeze of an unrendered generated beat is an error (or, under --only, the storyboard still stands in)
        if sb.freeze is None and not clip.exists():
            if not _LENIENT:
                raise NotRendered(f"beat '{b.id}' freezes the last frame of beat '{sb.id}', which is not rendered yet: "
                                  "build it first")
            log(f"  beat '{sb.id}' is not rendered: freezing its storyboard still instead")
            src = standin_image(project, ssec, sb, log, "last")
            key = {"standin": str(src), "k": fkey(src), "size": size}
            return _cached(bdir / "frozen.png", key, lambda tmp: _fit(Image.open(src), size).save(tmp))
        window = f.pick_window if f.pick == "sharpest" else 1
        cands = beat_candidates(project, ssec, sb, "last", window, log)
        i = fz.sharpest([_fit_np(c, size) for c in cands], views) if len(cands) > 1 else len(cands) - 1
        # keyed by the frame chosen, not by the camera: moving a box that picks the same frame keeps the upscale and depth
        key = {"from": sb.id, "clip": fkey(beat_clip_path(project, ssec, sb)), "n": len(cands), "i": i, "size": size}

        def make(tmp):
            Image.fromarray(cands[i]).convert("RGB").save(tmp)
            _fit(Image.open(tmp), size).save(tmp)
        out = _cached(bdir / "frozen.png", key, make)
        log(f"  froze beat '{sb.id}': its sharpest of the last {len(cands)} frames ({len(cands) - 1 - i} before the end)"
            if len(cands) > 1 else f"  froze the last frame of beat '{sb.id}'")
        return out
    src = resolve_image(project, f.image, log)
    key = {"image": str(src), "k": fkey(src), "size": size}
    return _cached(bdir / "frozen.png", key, lambda tmp: _fit(Image.open(src), size).save(tmp))


def _fit_np(a: np.ndarray, size) -> np.ndarray:
    from PIL import Image
    return np.asarray(_fit(Image.fromarray(a), size))


def _make_raw_depth(tmp: Path, upscaled: Path, f, size: tuple[int, int]) -> None:
    """depth_raw.npy: the frame's depth snapped to its edges but not grown (deep zoom starts every tile's depth from it)."""
    from PIL import Image
    from .backends import depth as depthmod
    from . import zoom
    img = _fit(Image.open(upscaled), size)
    d = depthmod.estimate(img, f.depth_model)
    np.save(tmp, zoom.raw_depth(d, np.asarray(img), size).astype(np.float16))


def zoom_beat_key(f, b, *, upscaled_key: str, size, depth_key: str, method: str) -> str:
    """What a deep-zoom render is made of, without making it: the settings and every tile's key (so a moved box or
    a changed detail setting re-renders, an unchanged one does not)."""
    from . import zoom, zoom_build
    from .backends import upscale as up
    d = f.detail
    base_px = up.target_size(size, f.upscale if f.upscale > 1 else 1)[0]
    tiles, sizes, ratio, tsize = zoom_build.make_plan(f, b.seconds, base_px, size)
    seed0 = f.seed if d.seed is None else d.seed
    keys = zoom_build.tile_keys(tiles, upscaled_key + depth_key, tsize, d, method, seed0)
    return digest("zoom", zoom.VERSION, zoom_build.VERSIONS, keys, d.model_dump(mode="json"))


def render_beat(project, sec, b, log=print, preview_size: Optional[tuple[int, int]] = None) -> Path:
    """Render a frozen beat into its folder (clip.mp4, first.png, last.png). Every step is cached by its own digest, so
    this is instant when nothing changed and seconds when only the camera did."""
    from PIL import Image
    f = b.freeze
    size = beat_size(sec)
    bdir = beat_dir(project, sec, b)
    bdir.mkdir(parents=True, exist_ok=True)
    clip = bdir / "clip.mp4"
    t0 = time.time()
    frozen = _source_frame(project, sec, b, log)
    # upscale
    from .backends import upscale as up
    method = up.resolve_method(f.upscale_method) if f.upscale > 1 else "none"
    upkey = {"src": frozen.with_name("frozen.png.key").read_text(), "factor": f.upscale, "method": method, "seed": f.seed}
    upscaled = _cached(bdir / "up.png", upkey, lambda tmp: up.upscale(frozen, tmp, f.upscale, method, f.seed, log))
    # depth, on the frame at beat_res (the model looks at ~518 px anyway)
    dkey = {"up": digest(upkey), "model": f.depth_model, "size": size, "v": VERSION}

    def make_depth(tmp):
        from .backends import depth as depthmod
        log(f"  depth: Depth Anything V2 ({f.depth_model})")
        img = _fit(Image.open(upscaled), size)
        d = depthmod.estimate(img, f.depth_model)
        np.save(tmp, fz.prepare_depth(d, np.asarray(img), size).astype(np.float16))
    depth = np.load(_cached(bdir / "depth.npy", dkey, make_depth)).astype(np.float32)
    # camera render
    trim_n = round(b.trim * FPS)
    rkey = {"up": digest(upkey), "depth": digest(dkey), "cam": f.model_dump(mode="json", by_alias=True,
            include={"camera", "parallax", "dolly", "ease", "blur", "grain", "seed"}), "seconds": b.seconds,
            "trim": trim_n, "size": size, "v": VERSION}
    zoomed, layered = f.detail is not None, f.layers is not None
    lkey = ""
    if layered:                                   # layered depth: the render is keyed by the planes it is made of
        lkey = digest("layers", f.layers.model_dump(mode="json"), f.seed)
        rkey["layers"] = lkey
    if zoomed:                                    # deep zoom: the render is keyed by the tiles it is made of
        rkey["zoom"] = zoom_beat_key(f, b, upscaled_key=digest(upkey) + lkey, size=size, depth_key=digest(dkey),
                                     method=up.resolve_method(f.upscale_method))
    stamp = clip.with_name(clip.name + ".key")
    if clip.exists() and stamp.exists() and stamp.read_text() == digest(rkey) and (bdir / "last.png").exists():
        log(f"  freeze: render is up to date")
        return clip
    rgb = read_rgb(upscaled)
    t1 = time.time()
    if zoomed or layered:
        from . import zoom_build, zoom_render
        raw = np.load(_cached(bdir / "depth_raw.npy", {"depth": digest(dkey), "raw": 1}, lambda tmp: _make_raw_depth(
            tmp, upscaled, f, size))).astype(np.float32)
        ls = None
        if layered:
            from . import layers as L
            ls = L.build_cached(bdir, frozen, read_rgb(frozen), raw, f.layers, f.seed if f.layers.seed is None else f.layers.seed,
                                digest(upkey) + digest(dkey), log)
        built = []
        if zoomed:
            base = zoom_build.Level0(rgb, raw, digest(upkey) + digest(dkey) + lkey, ls)
            built = zoom_build.build_pyramid(bdir, base, f, b.seconds, size, up.resolve_method(f.upscale_method), log)
        t1 = time.time()
        frames = zoom_render.render_frames(rgb, depth, [x.image() for x in built], f.camera, size=size, seconds=b.seconds,
                                           first_frame=trim_n, parallax=f.parallax, dolly=f.dolly, ease=f.ease,
                                           blur=f.blur, grain=f.grain, seed=f.seed, layers=ls)
    else:
        frames = fz.render_frames(rgb, depth, f.camera, size=size, seconds=b.seconds, first_frame=trim_n,
                                  parallax=f.parallax, dolly=f.dolly, ease=f.ease, blur=f.blur, grain=f.grain, seed=f.seed)
    tmp = bdir / "_tmp_clip.mp4"
    first, last = fz.encode_frames(frames, tmp, size, log=log)
    tmp.replace(clip)
    save_rgb(first, bdir / "first.png")
    save_rgb(last, bdir / "last.png")
    stamp.write_text(digest(rkey))
    n = max(2, round(b.seconds * FPS)) - trim_n
    log(f"  freeze: {n} frames at {size[0]}x{size[1]} in {time.time() - t1:.1f}s (prep {t1 - t0:.1f}s, "
        f"upscale {method} x{f.upscale:g})")
    return clip


def beat_clip(ctx, sec, b, only, standing: list) -> Path:
    """The frozen beat as a stage of the film: cached, lockable, rendered offline in seconds. Under `build --only` a beat
    that is not selected and not rendered stands in with a flat camera move over its storyboard still."""
    clip = beat_clip_path(ctx.project, sec, b)
    size = beat_size(sec)
    key = beat_key(ctx.project, sec, b)
    lock = b.locked or ctx.locked
    ctx.log(f"  beat {b.id} (frozen moment)")
    if only is not None and b.id not in only and ctx.status(f"beat_{b.id}", key, [clip], locked=lock) == "stale":
        from .fidelity import would_render
        would_render("stand-in", f"beat {b.id} (a flat camera move over its storyboard still, until it is rendered)")
        ctx.log(f"  beat_{b.id}: not in --only and not rendered: its storyboard still stands in")
        standing.append(b.id)
        return standin_clip(ctx.project, sec, b, beat_dir(ctx.project, sec, b) / "standin.mp4", size, ctx.log)
    ctx.stage(f"beat_{b.id}", key, [clip], lambda: render_beat(ctx.project, sec, b, ctx.log), locked=lock)
    return clip


def flat_clip(still: Path, b, out: Path, size: tuple[int, int]) -> Path:
    """The camera path over a still with no depth and no parallax (a stand-in; also the storyboard's preview)."""
    from PIL import Image
    f = b.freeze
    rgb = np.asarray(_fit(Image.open(still), size))
    depth = np.zeros((size[1], size[0]), np.float32)
    fz.encode_frames(fz.render_frames(rgb, depth, f.camera, size=size, seconds=b.seconds, first_frame=round(b.trim * FPS),
                                      parallax=0.0, ease=f.ease), out, size, crf=18)
    return out


def standin_clip(project, sec, b, out: Path, size: tuple[int, int], log) -> Path:
    """A frozen beat's stand-in clip (flat move over its storyboard still), at the beat's size; never stamped."""
    still = standin_image(project, sec, b, log, "last")
    stamp = out.with_suffix(".json")
    k = digest(str(still), fkey(still), b.freeze.model_dump(mode="json", by_alias=True, include={"camera", "ease"}),
               b.seconds, b.trim, size)
    if not (out.exists() and stamp.exists() and stamp.read_text() == k):
        out.parent.mkdir(parents=True, exist_ok=True)
        flat_clip(still, b, out, size)
        stamp.write_text(k)
    return out


def set_lenient(on: bool) -> None:
    """`build --only` sets this for a film's beats (see `lenient`); every film build sets it afresh."""
    global _LENIENT
    _LENIENT = bool(on)
