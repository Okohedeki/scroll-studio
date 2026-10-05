"""film: an AI film generated locally and scrubbed by scroll.

Stages (each cached by its own settings):
  blockout   Blender preset or the user's .blend -> beauty frames + log-depth pass
  keyframes  Z-Image Turbo + depth ControlNet -> detailed stills at chosen times
  generate   LTX-2.3 guided by the depth video + keyframes, in segments -> gen/gen.mp4
  upscale    optional (shot.upscale.method: ltx | seedvr2)
  encode     short-GOP H.264 for scrubbing (desktop + mobile), poster and end frames

`video:` skips generation and encodes an existing film instead (remove it to regenerate from `shot:`).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..project import BuildContext, BuildError, ffmpeg, file_key, probe
from ..spec import FilmScene


def _args(ctx: BuildContext, **kw):
    o = ctx.options
    return SimpleNamespace(dry_run=False, variants=int(o.get("variants", 1)), res=o.get("res"), sampler=None,
                           seconds=None, upscale=None, only=None, segment=o.get("segment"), force=ctx.force,
                           source=None, **kw)


def generate(sec: FilmScene, ctx: BuildContext) -> Path:
    from . import film_build as fb
    shot = dict(sec.shot, id=sec.id)
    for k in ("fps", "duration", "preview_res", "ltx"):
        if k not in shot:
            raise BuildError(f"film section '{sec.id}': shot.{k} is required to generate a film (or set `video:`)")
    out = str(ctx.work)
    bl = dict(shot.get("blockout", {}))
    if bl.get("file"):
        bl["file"] = str(ctx.project.path(bl["file"]))
        shot["blockout"] = bl
    bdir, gdir = ctx.work / "blockout", ctx.work / "gen"
    bkey = {"blockout": bl, "fps": shot["fps"], "duration": shot["duration"], "res": shot["preview_res"],
            "file": file_key(Path(bl["file"])) if bl.get("file") else None}
    ctx.stage("blockout", bkey, [bdir / "depth.mp4", bdir / "first.png"], lambda: fb.stage_blockout(shot, out))
    if shot.get("keyframes", {}).get("frames"):
        names = [f["name"] for f in shot["keyframes"]["frames"]]
        ctx.stage("keyframes", {"b": bkey, "k": shot["keyframes"]}, [ctx.work / "keyframes" / f"{n}.png" for n in names],
                  lambda: fb.stage_keyframes(shot, out, _args(ctx)))
    gkey = {"b": bkey, "k": shot.get("keyframes"), "ltx": shot["ltx"], "subject": shot.get("subject")}
    ctx.stage("generate", gkey, [gdir / "gen.mp4"], lambda: fb.stage_generate(shot, out, _args(ctx)))
    film = gdir / "gen.mp4"
    up = shot.get("upscale")
    if up and up.get("method") in ("ltx", "seedvr2"):
        dst = gdir / ("gen_sr.mp4" if up["method"] == "seedvr2" else "gen_up.mp4")
        ctx.stage("upscale", {"g": gkey, "u": up}, [dst], lambda: fb.stage_upscale(shot, out, _args(ctx)))
        film = dst
    return film


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


def build(sec: FilmScene, ctx: BuildContext, theme: dict) -> dict:
    src = ctx.project.path(sec.video) if sec.video else generate(sec, ctx)
    if not src.exists():
        raise BuildError(f"film source not found: {src}")
    return encode(src, ctx, sec.gop)
