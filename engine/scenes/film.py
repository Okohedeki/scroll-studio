"""film: an AI film generated locally and scrubbed by scroll.

Stages (each cached by its own settings):
  blockout   Blender preset or the user's .blend -> beauty frames + log-depth pass
  keyframes  Z-Image Turbo + depth ControlNet -> detailed stills at chosen times
  generate   LTX-2.3 guided by the depth video + keyframes, in segments -> gen/gen.mp4; or, with
             video_model: wan, Wan 2.2 Fun Control along the same depth video -> wan/gen/gen.mp4
  upscale    optional (shot.upscale.method: ltx | seedvr2)
  restore    take.restore: SeedVR2 over the generated world, before the product composite
  encode     short-GOP H.264 for scrubbing (desktop + mobile), poster and end frames

`video:` skips generation and encodes an existing film instead (remove it to regenerate from `shot:`).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from .. import world as typeworld
from ..layout import set_window, window
from ..project import BuildContext, BuildError, ffmpeg, file_key, probe
from ..spec import FilmScene


def _args(ctx: BuildContext, **kw):
    o = ctx.options
    return SimpleNamespace(dry_run=False, variants=int(o.get("variants", 1)), res=o.get("res"), sampler=None,
                           seconds=None, upscale=None, only=None, segment=o.get("segment"), force=ctx.force,
                           source=None, **kw)


def _restore_args(ctx: BuildContext, source: Path):
    a = _args(ctx)
    a.source = str(source)
    return a


def _legacy_path(path: Path) -> str:
    """How take.json named the product file before keys were made portable (absolute path); tests patch this."""
    return str(path)


def take_product(sec: FilmScene, ctx: BuildContext) -> tuple[Path, Optional[Path], dict]:
    """The take product's model file (site.product's normalised GLB when the layer names no model), the raw source
    file (for keys written before site.product existed), and the layer as take.py reads it (height and res resolved)."""
    from ..inputs import resolve_path
    layer = sec.take.product
    p = layer.model_dump(mode="json")
    site_product = ctx.project.load().product
    raw = None
    if layer.model:
        path = raw = resolve_path(ctx.project, layer.model, ctx.log)
    elif layer.from_photo:
        from ..backends.trellis import image_to_mesh
        photo = resolve_path(ctx.project, layer.from_photo, ctx.log)
        path = image_to_mesh(photo, ctx.work / "trellis", ctx.log)
    elif site_product is not None:
        from ..product import normalised_glb
        path = normalised_glb(ctx.project, log=ctx.log)
        if site_product.model:
            raw = resolve_path(ctx.project, site_product.model, ctx.log)
    else:
        raise BuildError(f"film section '{sec.id}': take.product needs `model` or `from_photo`, or a site `product:`")
    from ..product import take_height
    p["height"] = take_height(ctx.project, layer)
    if not p.get("res"):
        p["res"] = [2560, 1440] if sec.take.upscale else [1920, 1080]
    return path, raw, p


def take_shot(sec: FilmScene, ctx: BuildContext) -> dict:
    """Turn a spec `take` into the `shot` mapping the film stages run on, writing take.json for Blender.

    Keys are portable: the world (blockout, keyframes, LTX) is keyed without the product unless the product is in
    the depth guide, and never by an absolute path, so a moved project or a new product keeps its generated world.
    `legacy_world_key` is the key of the older formula, so stamps written by it still count."""
    import json
    t = sec.take.model_dump(mode="json", exclude={"locked"})   # locking never changes what is rendered
    legacy = None
    if sec.take.product:
        path, raw, p = take_product(sec, ctx)
        t["product"] = p
        t["product_file"] = str(path)
        pw, ph = p["res"]
        bw, bh = t["preview_res"]
        if abs(pw / ph - bw / bh) > 0.01:
            raise BuildError(f"take.product.res {pw}x{ph} and take.preview_res {bw}x{bh} must have the same aspect ratio")
        layer = sec.take.product
        old = {k: v for k, v in layer.model_dump(mode="json").items()
               if k in ("model", "from_photo", "credit", "at", "height", "rotation", "spin", "hdri", "sun_strength",
                        "samples", "shadow", "shadow_size", "res")}
        site_product = ctx.project.load().product
        if not old["model"] and not old["from_photo"] and site_product is not None:
            old["model"] = site_product.model
            old["credit"] = old["credit"] or site_product.credit
        old["height"] = old["height"] if old["height"] is not None else 1.0
        old["hdri"] = old["hdri"] or "sunrise"
        old["samples"] = old["samples"] if "samples" in layer.model_fields_set else 32
        old["res"] = old["res"] or [1920, 1080]
        src = raw or path
        lw = {**{k: v for k, v in t.items() if k not in ("ltx", "keyframes", "upscale", "product", "product_file", "restore", "video_model", "wan")},
              "product": old, "product_file": _legacy_path(src)}
        legacy = {"world_key": lw, "model": file_key(src)}
    ctx.work.mkdir(parents=True, exist_ok=True)
    (ctx.work / "take.json").write_text(json.dumps(t, indent=1), encoding="utf-8")
    world = {k: v for k, v in t.items() if k not in ("ltx", "keyframes", "upscale", "product", "product_file", "restore", "video_model", "wan")}
    if sec.take.product and sec.take.product_in_guide:
        world["product"] = {k: t["product"][k] for k in ("at", "height", "rotation", "spin")}
        world["product_model"] = file_key(Path(t["product_file"]))
    shot = {"fps": t["fps"], "duration": t["duration"], "preview_res": t["preview_res"], "ltx": t["ltx"],
            "blockout": {"world": str(ctx.work / "take.json")}, "world_key": world, "legacy_world_key": legacy}
    if t.get("video_model"):
        shot["video_model"] = t["video_model"]
    if sec.take.wan:   # only what the take sets, so the site's `wan:` fills the rest
        shot["wan"] = sec.take.wan.model_dump(mode="json", exclude_unset=True)
    if t.get("keyframes"):
        shot["keyframes"] = t["keyframes"]
    if t.get("upscale"):
        shot["upscale"] = t["upscale"]
    return shot


def world(sec: FilmScene, ctx: BuildContext, keyframes_too: bool = True) -> tuple[dict, dict, Optional[dict]]:
    """The world stages of a take or shot, as the full build runs them: `blockout` (Blender: the grey world, the
    camera and its depth guide) and `keyframes` (Z-Image stills on that depth). Returns (shot, blockout key, legacy
    key). The storyboard calls this too, so an approved keyframe is the one the film is generated from."""
    from . import film_build as fb
    shot, bkey, legacy = blockout_key(sec, ctx)
    bdir = ctx.work / "blockout"
    ctx.stage("blockout", bkey, [bdir / "depth.mp4", bdir / "first.png"], lambda: fb.stage_blockout(shot, str(ctx.work)),
              legacy=legacy)
    if keyframes_too and shot.get("keyframes", {}).get("frames"):
        keyframes(shot, bkey, legacy, ctx)
    return shot, bkey, legacy


def blockout_key(sec: FilmScene, ctx: BuildContext) -> tuple[dict, dict, Optional[dict]]:
    """(shot, blockout key, legacy key) without running anything (the storyboard's sketch reads the cache with it)."""
    from .. import imagery
    shot = dict(take_shot(sec, ctx) if sec.take else sec.shot, id=sec.id)
    shot = imagery.treat_shot(ctx.project, shot)      # the site's `imagery:` in the keyframe and segment prompts (if set)
    for k in ("fps", "duration", "preview_res", "ltx"):
        if k not in shot:
            raise BuildError(f"film section '{sec.id}': shot.{k} is required to generate a film (or set `video:`)")
    bl = dict(shot.get("blockout", {}))
    if bl.get("file"):
        bl["file"] = str(ctx.project.path(bl["file"]))
        shot["blockout"] = bl
    legacy = None
    if sec.take:
        bkey = {"take": shot["world_key"], "fps": shot["fps"], "duration": shot["duration"], "res": shot["preview_res"]}
        lw = shot.get("legacy_world_key")
        legacy = {"blockout": {"world_key": (lw or {}).get("world_key", shot["world_key"])}, "fps": shot["fps"],
                  "duration": shot["duration"], "res": shot["preview_res"], "file": None,
                  "model": lw["model"] if lw else None}
    else:
        bkey = {"blockout": {k: v for k, v in bl.items() if k != "world"}, "fps": shot["fps"], "duration": shot["duration"],
                "res": shot["preview_res"], "file": file_key(Path(bl["file"])) if bl.get("file") else None, "model": None}
    return shot, bkey, legacy


def generate(sec: FilmScene, ctx: BuildContext) -> Path:
    from . import film_build as fb
    shot, bkey, legacy = world(sec, ctx)
    out = str(ctx.work)
    gkey = {"b": bkey, "k": shot.get("keyframes"), "ltx": shot["ltx"], "subject": shot.get("subject")}
    glegacy = legacy and {"b": legacy, "k": shot.get("keyframes"), "ltx": shot["ltx"], "subject": shot.get("subject")}
    from ..animate import video_model, wan_settings
    model = video_model(shot.get("video_model"), ctx.options.get("site_video_model"))
    # Wan's renders live under wan/ with their own stage names, so switching models back and forth never
    # throws away the other model's cached film (and LTX keys are unchanged).
    sfx, mout = ("", out) if model == "ltx" else ("_wan", str(ctx.work / "wan"))
    gdir = Path(mout) / "gen"
    if model == "wan":
        shot["wan"] = wan_settings(ctx.options.get("site_wan"), shot.get("wan"))
        gkey = dict(gkey, video_model=model, wan=shot["wan"])
        ctx.stage("generate_wan", gkey, [gdir / "gen.mp4"],
                  lambda: fb.stage_generate_wan(shot, out, mout, _args(ctx), ctx.log))
    else:
        ctx.stage("generate", gkey, [gdir / "gen.mp4"], lambda: fb.stage_generate(shot, out, _args(ctx)),
                  legacy=glegacy)
    film = gdir / "gen.mp4"
    up = shot.get("upscale")
    if up and up.get("method") in ("ltx", "seedvr2"):
        dst = gdir / ("gen_sr.mp4" if up["method"] == "seedvr2" else "gen_up.mp4")
        ctx.stage("upscale" + sfx, {"g": gkey, "u": up}, [dst], lambda: fb.stage_upscale(shot, mout, _args(ctx)),
                  legacy=(glegacy and not sfx) and {"g": glegacy, "u": up})
        film = dst
    if sec.take and sec.take.restore:
        film = restore_take(sec, ctx, shot, film, up)
    if sec.take and sec.take.product:
        film = product_layer(sec, ctx, shot, film)
    return film


def _depth_digest(shot: dict, work: Path, f: dict) -> Optional[str]:
    """Digest of the depth frame a keyframe is painted over (None before the blockout is rendered)."""
    import glob
    import hashlib
    from . import film_build as fb
    frames = sorted(glob.glob(str(work / "blockout" / "depth" / "*.png")))
    if not frames:
        return None
    idx = fb.keyframe_index(f["t"], shot["fps"])
    return hashlib.sha1(Path(frames[idx if idx < 0 else min(idx, len(frames) - 1)]).read_bytes()).hexdigest()[:16]


def keyframe_digests(shot: dict, bkey: dict, variants: int = 1, work: Optional[Path] = None) -> dict[str, str]:
    """One digest per keyframe: the world it is painted over, the shared settings (model, res, seed...) and its own
    entry. The stage key covers every keyframe; these let a re-run redo only the keyframes that changed."""
    import hashlib
    import json
    common = {k: v for k, v in shot["keyframes"].items() if k != "frames"}

    def world_of(f):
        # `by_depth` (a journey's take): the world a keyframe depends on is the depth frame under it, so moving the camera at
        # one stop repaints that stop's picture and no other
        if common.get("by_depth") and work is not None:
            d = _depth_digest(shot, work, f)
            if d:
                return {"depth": d}
        return bkey
    def entry(f):      # by_depth: when the keyframe falls in the film does not change what it is painted over
        return {k: v for k, v in f.items() if k != "t"} if common.get("by_depth") else f
    return {f["name"]: hashlib.sha1(json.dumps({"b": world_of(f), "c": common, "f": entry(f), "v": variants}, sort_keys=True,
                                               default=str).encode()).hexdigest()[:16]
            for f in shot["keyframes"]["frames"]}


def keyframes(shot: dict, bkey: dict, legacy: Optional[dict], ctx: BuildContext) -> list[Path]:
    """Stage `keyframes`: Z-Image stills locked to the blockout's depth. When it re-runs, keyframes whose own digest
    (keyframe_digests) is unchanged and whose PNG exists are kept, so editing one keyframe's prompt repaints only it."""
    import json
    from . import film_build as fb
    kdir = ctx.work / "keyframes"
    names = [f["name"] for f in shot["keyframes"]["frames"]]
    outs = [kdir / f"{n}.png" for n in names]
    args = _args(ctx)
    digests = keyframe_digests(shot, bkey, args.variants, ctx.work)
    record = kdir / "_frames.json"

    def run():
        old = json.loads(record.read_text()) if record.exists() and not ctx.force else {}
        keep = {n for n in names if old.get(n) == digests[n] and (kdir / f"{n}.png").exists()}
        if keep:
            ctx.log(f"  keyframes: kept {', '.join(sorted(keep))} (unchanged)")
        a = _args(ctx, skip=keep)
        fb.stage_keyframes(shot, str(ctx.work), a)
        record.write_text(json.dumps(digests, indent=1))
    key, lkey = {"b": bkey, "k": shot["keyframes"]}, legacy and {"b": legacy, "k": shot["keyframes"]}
    state = ctx.status("keyframes", key, outs, lkey)
    ctx.stage("keyframes", key, outs, run, legacy=lkey)
    if state in ("fresh", "migrated") and not record.exists() and ctx.options.get("plan") is None:
        record.write_text(json.dumps(digests, indent=1))   # a cache from before per-keyframe digests: adopt it
    return outs


def restore_take(sec: FilmScene, ctx: BuildContext, shot: dict, film: Path, up: Optional[dict]) -> Path:
    """take.restore: SeedVR2 over the generated world (as beat_restore does for beats), before the product composite,
    so the real product is never touched by restoration. Skipped when the take already upscales with SeedVR2."""
    from . import film_build as fb
    if up and up.get("method") == "seedvr2":
        ctx.log("  restore: skipped, take.upscale already runs SeedVR2")
        return film
    restored = ctx.work / "gen" / "gen_sr.mp4"
    rshot = {"id": sec.id, "fps": shot["fps"], "duration": shot["duration"], "ltx": {},
             "upscale": {"method": "seedvr2", "resolution": int(sec.take.restore), **ctx.options.get("restore", {})}}
    ctx.stage("restore", {"src": file_key(film), "res": sec.take.restore}, [restored],
              lambda: fb.stage_upscale(rshot, str(ctx.work), _restore_args(ctx, film)))
    return restored


def _take_json(ctx: BuildContext) -> dict:
    import json
    return json.loads((ctx.work / "take.json").read_text(encoding="utf-8"))


def json_product_file(ctx: BuildContext) -> str:
    return _take_json(ctx)["product_file"]


def _model_key(path: Path) -> dict:
    """The product model in a cache key: a normalised GLB is named by the digest of what made it, so its name and size
    identify it on any machine (no mtime, which would re-render a product pass after a fresh checkout or copy)."""
    if path.parent.name == "_product":
        return {"glb": path.name, "size": path.stat().st_size}
    return file_key(path)


def _product_keys(ctx: BuildContext) -> dict:
    """What the product pass depends on: the camera and world timing, the product layer and model, and take.py."""
    from ..product import _sha
    from . import film_build as fb
    t = _take_json(ctx)
    return {"camera": {k: t.get(k) for k in ("camera", "lens", "fps", "duration", "light")},
            "product": t["product"], "model": _model_key(Path(t["product_file"])),
            "script": _sha(Path(fb.SCRIPTS) / "take.py")}


def track(sec: FilmScene, ctx: BuildContext) -> Path:
    """product/track.json: per frame, the camera and where the product is on screen (stage `track`, seconds)."""
    from . import film_build as fb
    out = ctx.work / "product" / "track.json"
    ctx.stage("track", {"p": _product_keys(ctx)}, [out],
              lambda: fb.stage_track(str(ctx.work), _take_json(ctx)["product"]["res"]))
    return out


def product_layer(sec: FilmScene, ctx: BuildContext, shot: dict, film: Path) -> Path:
    """The real product, rendered through the identical camera, lit by the plate and graded to it, over the world."""
    from . import film_build as fb
    p = _take_json(ctx)["product"]
    pdir = ctx.work / "product"
    n = int(round(shot["fps"] * shot["duration"]))
    base = _product_keys(ctx)
    trk = track(sec, ctx)
    env = None
    if not p.get("hdri"):        # plate-matched light: environments built from the generated frames themselves
        env = pdir / "env" / "env.json"
        ctx.stage("plate_env", {"p": base, "film": file_key(film), "v": fb.PLATE_ENV_VERSION}, [env],
                  lambda: fb.stage_plate_env(film, trk, env, shot["fps"], ctx.log))
    pkey = {"p": base, "env": file_key(env) if env else None}
    ctx.stage("product", pkey, [pdir / "frames" / f"{n:04d}.png"],
              lambda: fb.stage_product(shot, str(ctx.work), p["res"], p["samples"], ctx, env=env))
    comp = ctx.work / "gen" / "take.mp4"
    ckey = {"film": file_key(film), "p": pkey, "grade": p.get("grade", True), "grain": p.get("grain"),
            "v": fb.COMPOSITE_VERSION}
    ctx.stage("composite", ckey, [comp], lambda: fb.stage_composite(film, pdir, comp, shot["fps"], p["res"],
                                                                     grade=p.get("grade", True), grain=p.get("grain"),
                                                                     track=trk, log=ctx.log))
    return comp


def encode(src: Path, ctx: BuildContext, gop: int) -> dict:
    web = ctx.web
    common = ["-an", "-c:v", "libx264", "-preset", "slow", "-pix_fmt", "yuv420p", "-g", str(gop), "-keyint_min", str(gop),
              "-sc_threshold", "0", "-movflags", "+faststart"]
    crop169 = "crop='min(iw,ih*16/9)':'min(ih,iw*9/16)',"

    def run():
        h = int(probe(src).get("height") or 0)
        desk_w, crf = (2560, 19) if h >= 1440 else (1920, 20)
        mob_w = 1280 if h >= 1080 else 960
        ffmpeg("-i", src, "-vf", f"{crop169}scale={desk_w}:-2:flags=lanczos", *common, "-crf", str(crf), web / "film.mp4", log=ctx.log)
        ffmpeg("-i", src, "-vf", f"{crop169}scale={mob_w}:-2:flags=lanczos", *common, "-crf", "24", web / "film-mobile.mp4", log=ctx.log)
        ffmpeg("-i", src, "-vf", f"{crop169}scale={desk_w}:-2", "-frames:v", "1", "-q:v", "2", web / "poster.jpg")
        ffmpeg("-sseof", "-0.1", "-i", src, "-vf", f"{crop169}scale={desk_w}:-2", "-frames:v", "1", "-q:v", "2", "-update", "1", web / "end.jpg")
    outs = [web / n for n in ("film.mp4", "film-mobile.mp4", "poster.jpg", "end.jpg")]
    ctx.stage("encode", {"src": file_key(src), "gop": gop}, outs, run)
    return {"video": ctx.url(outs[0]), "videoMobile": ctx.url(outs[1]), "poster": ctx.url(outs[2]), "end": ctx.url(outs[3])}


def beats_film(sec: FilmScene, ctx: BuildContext) -> Path:
    """A story in shots: each beat's still (generated, or a file) animated by the video model (LTX-2.3 or Wan 2.2,
    `video_model`), cached per beat, then joined with crossfades. Steps pinned with state: {beat: <id>} are timed to their beat."""
    import shutil
    from PIL import Image, ImageOps
    from ..animate import FPS, animate, video_model, wan_settings
    from ..inputs import resolve_image
    from ..camera_beats import start_ref
    from .. import imagery
    W, H = sec.beat_res[0] // 32 * 32, sec.beat_res[1] // 32 * 32
    clips, standing = [], []
    only = ctx.options.get("only_beats")      # build --only: the beats to render (None: all)
    from ..freeze_beats import set_lenient    # frozen moments: under --only a beat that is not rendered stands in
    set_lenient(only is not None)
    for bi, b in enumerate(sec.beats):
        if b.freeze is not None:              # a frozen moment: rendered offline in seconds (engine/freeze_beats.py)
            from ..freeze_beats import beat_clip as freeze_clip
            clips.append(freeze_clip(ctx, sec, b, only, standing))
            continue
        bdir = ctx.work / "beats" / b.id
        clip = bdir / "clip.mp4"

        def run(b=b, bdir=bdir, clip=clip, bi=bi):
            bdir.mkdir(parents=True, exist_ok=True)
            ref = start_ref(sec, bi, (W, H))
            src = resolve_image(ctx.project, ref, ctx.log)
            still = bdir / "still.png"
            ImageOps.fit(Image.open(src).convert("RGB"), (W, H), Image.LANCZOS).save(still)
            end = None
            if b.end_image:
                end = bdir / "end.png"
                ImageOps.fit(Image.open(resolve_image(ctx.project, b.end_image, ctx.log)).convert("RGB"), (W, H),
                             Image.LANCZOS).save(end)
            import json
            akey = json.dumps({k: v for k, v in key.items() if k != "trim"}, sort_keys=True)
            stamp = bdir / "anim.json"
            frames = sorted((bdir / "frames").glob("*.png"))
            if not (frames and stamp.exists() and stamp.read_text() == akey):
                if b.camera is not None:     # a keyed camera move (engine/camera_beats.py): the model generates along a guide
                    from ..camera_beats import make_frames as camera_frames
                    from ..animate import NEGATIVE
                    seed = b.camera.seed if b.camera.seed is not None else b.seed if b.motion_seed is None else b.motion_seed
                    from ..camera_moves import negative as move_negative, phrase as move_phrase
                    said = move_phrase(b.camera)
                    frames = camera_frames(ctx.project, sec, bi, still, bdir,
                                           f"{imagery.treat(ctx.project, b.prompt, video=True) or 'The subject of the image'}. {b.motion}. "
                                           + (f"{said}. " if said else "") + "Smooth natural motion.",
                                           move_negative(b.camera, NEGATIVE), seed, wan_settings(ctx.options.get("site_wan")), ctx.log)
                else:
                    frames = animate(still, imagery.treat(ctx.project, b.prompt, video=True), b.motion, b.seconds, b.seed if b.motion_seed is None else b.motion_seed,
                                     bdir, ctx.log, size=(W, H), strength=b.strength, end_image=end, model=model, wan=wan)
                stamp.write_text(akey)
            frames = frames[round(b.trim * FPS):]
            seq = bdir / "seq"
            if seq.exists():
                shutil.rmtree(seq)
            seq.mkdir()
            for i, f in enumerate(frames):
                shutil.copy(f, seq / f"{i:04d}.png")
            ffmpeg("-framerate", str(FPS), "-i", seq / "%04d.png", "-c:v", "libx264", "-crf", "13", "-preset", "slow",
                   "-pix_fmt", "yuv420p", clip, log=ctx.log)
        def ref_key(r):
            if r is None or (isinstance(r, str) and r.startswith("http")):
                return r
            if isinstance(r, str):
                return file_key(ctx.project.path(r))
            from ..freeze_beats import beat_frame_deps
            from ..inputs import stable_dump
            deps = beat_frame_deps(ctx.project, r)      # an image that is a beat's frame depends on that beat's clip
            return {**stable_dump(r), "beat_frame_deps": deps} if deps else stable_dump(r)
        key = {"prompt": b.prompt, "motion": b.motion, "seconds": b.seconds, "seed": b.seed, "res": [W, H],
               "image": ref_key(b.image)}
        if b.camera is not None:   # only for a camera beat, so every other beat keeps its cache
            from ..camera_beats import key_of as camera_key
            key["camera"] = camera_key(sec, bi)
            if not b.image and b.camera.continues and bi > 0:
                key["image"] = ref_key(start_ref(sec, bi, (W, H)))
        look = imagery.of(ctx.project)
        if look is not None:     # the site's `imagery:` treatment is part of the beat (only when set: other beats keep their cache)
            key["imagery"] = look.model_dump(mode="json")
        model = video_model(b.video_model, ctx.options.get("site_video_model"))
        wan = wan_settings(ctx.options.get("site_wan")) if model == "wan" else None
        if model != "ltx":   # only when not the default, so LTX beats rendered before video_model existed stay cached
            key["video_model"] = model
            key["wan"] = {k: v for k, v in wan.items() if k != "seed"}
        if b.end_image:
            key["end_image"] = ref_key(b.end_image)
        # only when set, so beats rendered before these existed stay cached
        if b.strength != 1.0:
            key["strength"] = b.strength
        if b.motion_seed is not None:
            key["motion_seed"] = b.motion_seed
        if b.trim:
            key["trim"] = b.trim
        ctx.log(f"  beat {b.id}")
        lock = b.locked or ctx.locked
        if only is not None and b.id not in only and ctx.status(f"beat_{b.id}", key, [clip], locked=lock) == "stale":
            # not selected and not rendered yet: its storyboard still stands in (never stamped as the beat)
            from ..fidelity import would_render
            would_render("stand-in", f"beat {b.id} (its storyboard still, until it is rendered)")
            from ..storyboard.standin import beat_clip
            ctx.log(f"  beat_{b.id}: not in --only and not rendered: its storyboard still stands in")
            clips.append(beat_clip(ctx.project, sec, b, bdir / "standin.mp4", (W, H), ctx.log))
            standing.append(b.id)
            continue
        ctx.stage(f"beat_{b.id}", key, [clip], run, locked=lock)
        # ---- restore: SeedVR2 over this beat's clip only (beat_restore does the whole film), back at beat_res
        if b.restore:
            clip = restore_beat(ctx, b, clip, bdir, (W, H))
        # ---- faces (engine/faces.py): this beat's clip with its faces repaired, before the join
        if b.faces:
            from .. import faces
            clip = faces.restore_beat(ctx, b.id, clip, b.faces)
        clips.append(clip)

    # join: each clip crossfades into the next, except a camera beat that continues the one before it: its first frame is
    # that beat's last frame and the camera keeps its speed through the cut, so the two are one shot (a hard, frame-exact join)
    durs = [float(probe(c)["duration"]) for c in clips]
    fades = join_fades(sec, durs)
    fade = min(sec.beat_fade, *(d / 3 for d in durs)) if len(clips) > 1 else 0
    cont = [i > 0 and b.camera is not None and b.camera.continues for i, b in enumerate(sec.beats)]
    out = ctx.work / "gen" / "beats.mp4"

    def join():
        out.parent.mkdir(parents=True, exist_ok=True)
        if len(clips) == 1:
            shutil.copy(clips[0], out)
            return
        groups: list = []                       # (file, seconds): continued beats merged into one clip
        for i, c in enumerate(clips):
            if cont[i] and groups:
                prev, pd = groups[-1]
                merged = ctx.work / "gen" / f"chain_{sec.beats[i].id}.mp4"
                ffmpeg("-i", prev, "-i", c, "-filter_complex",
                       "[1:v]trim=start_frame=1,setpts=PTS-STARTPTS[b];[0:v][b]concat=n=2:v=1:a=0[v]", "-map", "[v]",
                       "-c:v", "libx264", "-crf", "13", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS), merged,
                       log=ctx.log)
                groups[-1] = (merged, pd + durs[i] - 1 / FPS)
            else:
                groups.append((c, durs[i]))
        if len(groups) == 1:
            shutil.copy(groups[0][0], out)
            return
        args, graph, last, t = [], [], "[0:v]", 0.0
        for c, _ in groups:
            args += ["-i", c]
        gfade = min(sec.beat_fade, *(d / 3 for _, d in groups))
        for i in range(1, len(groups)):
            t += groups[i - 1][1] - gfade
            tag = f"[v{i}]"
            graph.append(f"{last}[{i}:v]xfade=transition=fade:duration={gfade:.3f}:offset={t:.3f}{tag}")
            last = tag
        ffmpeg(*args, "-filter_complex", ";".join(graph), "-map", last, "-c:v", "libx264", "-crf", "14", "-preset", "slow",
               "-pix_fmt", "yuv420p", "-r", str(FPS), out, log=ctx.log)
    jkey = {"clips": [file_key(c) for c in clips], "fade": fade}
    if any(cont):
        jkey["continued"] = cont                # only when there is one, so every other film keeps its cache
    ctx.stage("beats_join", jkey, [out], join)
    if sec.beat_restore and standing:
        ctx.log(f"  beats_restore: skipped while {', '.join(standing)} stand in; a full build restores the film")
    elif sec.beat_restore:
        from . import film_build as fb
        shot = {"id": sec.id, "fps": FPS, "duration": float(probe(out)["duration"]), "ltx": {},
                "upscale": {"method": "seedvr2", "resolution": int(sec.beat_restore)}}
        restored = ctx.work / "gen" / "gen_sr.mp4"
        ctx.stage("beats_restore", {"src": file_key(out), "res": sec.beat_restore}, [restored],
                  lambda: fb.stage_upscale(shot, str(ctx.work), _restore_args(ctx, out)))
        out = restored

    set_lenient(False)
    pin_steps(sec, durs, fades)
    return out


def restore_beat(ctx: BuildContext, b, clip: Path, bdir: Path, size: tuple[int, int]) -> Path:
    """`beat.restore`: SeedVR2 over one beat's clip at that height (it cleans grain and redraws fine detail, e.g. on a
    camera beat, which the video model renders near 1024 px), scaled back to the film's size so the join still lines up."""
    from ..animate import FPS
    from . import film_build as fb
    rdir = bdir / "restore"
    out = rdir / "clip.mp4"

    def run():
        shot = {"id": f"beat-{b.id}", "fps": FPS, "duration": float(probe(clip)["duration"]), "ltx": {},
                "upscale": {"method": "seedvr2", "resolution": int(b.restore)}}
        rdir.mkdir(parents=True, exist_ok=True)
        fb.stage_upscale(shot, str(rdir), _restore_args(ctx, clip))
        W, H = size
        ffmpeg("-i", rdir / "gen" / "gen_sr.mp4", "-vf", f"scale={W}:{H}:flags=lanczos", "-c:v", "libx264", "-crf", "13",
               "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS), out, log=ctx.log)
    ctx.stage(f"restore_{b.id}", {"src": file_key(clip), "res": int(b.restore), "size": list(size)}, [out], run)
    return out


def join_fades(sec: FilmScene, durs: list[float]) -> list[float]:
    """The overlap at each join of a beats film, in seconds (one per join): the crossfade, or, for a camera beat that
    `continues` the one before it, one frame (the duplicate first frame of the continued beat, which is dropped: a hard cut)."""
    from ..animate import FPS
    n = len(durs)
    fade = min(sec.beat_fade, *(d / 3 for d in durs)) if n > 1 else 0
    return [1 / FPS if (sec.beats[i].camera is not None and sec.beats[i].camera.continues) else fade for i in range(1, n)]


def beat_spans(sec: FilmScene, durs: list[float], fade) -> dict[str, tuple[float, float]]:
    """Each beat's span over the joined film, as fractions 0-1 of its length (steps and reveal regions are timed by it).
    `fade`: the crossfade, or one overlap per join (`join_fades`)."""
    fades = list(fade) if isinstance(fade, (list, tuple)) else [fade] * (len(durs) - 1)
    total = sum(durs) - sum(fades)
    spans, t = {}, 0.0
    for i, (b, d) in enumerate(zip(sec.beats, durs)):
        spans[b.id] = (t / total, (t + d) / total)
        t += d - (fades[i] if i < len(fades) else 0)
    return spans


def pin_steps(sec: FilmScene, durs: list[float], fade) -> None:
    """Time steps pinned with state: {beat: id} to their beat's span over the joined film (sets the step's window)."""
    spans = beat_spans(sec, durs, fade)
    for st in sec.steps:
        pin = (st.state or {}).get("beat")
        if pin is None or window(st) is not None:
            continue
        if pin not in spans:
            raise BuildError(f"film section '{sec.id}': step '{st.title}' is pinned to beat {pin}, which is not in beats")
        a, b2 = spans[pin]
        part = (st.state or {}).get("part")
        if part:
            a, b2 = a + (b2 - a) * float(part[0]), a + (b2 - a) * float(part[1])
        pad = (b2 - a) * 0.1
        # a caption on the film's last moment stays up until the scene lets go (a closing line, a button)
        set_window(st, round(a + pad, 4), 1.0 if b2 >= 0.999 else round(b2 - pad * 0.6, 4))


def build(sec: FilmScene, ctx: BuildContext, theme: dict) -> dict:
    if sec.reveal:      # reveal: fail now, before a film renders, if ComfyUI lacks the nodes that mask it
        from .. import reveal
        reveal.preflight(ctx)
    in_world = typeworld.active(sec) and not sec.reveal and sec.pointer is None
    if typeworld.active(sec) and not in_world:
        ctx.log("  note: type in the world is not drawn through `reveal`'s shader yet (`reveal` and `pointer` use it): the "
                "titles stay ordinary captions on this film")
    if in_world:           # type in the world: fail now, before a film renders, if a placement can't work
        typeworld.preflight(sec, ctx)
    src = ctx.project.path(sec.video) if sec.video else beats_film(sec, ctx) if sec.beats else generate(sec, ctx)
    if not src.exists():
        raise BuildError(f"film source not found: {src}")
    # ---- faces (engine/faces.py): repair the faces of the whole film before it is encoded
    if sec.faces:
        from .. import faces
        faces.preflight(ctx)
        src = faces.restore_film(sec, ctx, src)
    # ---- finish (engine/finish.py): SeedVR2 restore, deflicker, temporal denoise, interpolation, before the encode
    if sec.finish is not None:
        from .. import finish
        src = finish.run(sec, ctx, src)
    cfg = encode(src, ctx, sec.gop)
    # ---- reveal (engine/reveal.py): tracked masks and the scroll-driven colour config, from the same film file
    if sec.reveal:
        from .. import reveal
        cfg["reveal"] = reveal.build(sec, ctx, src, cfg)
    elif sec.pointer is not None:   # the pointer lens or light is drawn by the reveal shader, frame by frame: it needs the rate
        num, _, den = str(probe(src).get("r_frame_rate") or "24/1").partition("/")
        cfg["fps"] = round(float(num) / float(den or 1), 3)
    # ---- type in the world (engine/world.py): depth, tracks and masks for the titles set inside the film
    if in_world:
        cfg["world"] = typeworld.build(sec, ctx, src, cfg)
    if sec.journey is not None:    # the one-take page (engine/journey.py): stop stills, scroll-to-film map, block placement
        from .. import journey
        journey.build(sec, ctx, src, cfg, theme)
    if sec.take and sec.take.product and sec.take.product.credit:   # site.product's own credit is added site-wide
        cfg["credits"] = [sec.take.product.credit]
    return cfg
