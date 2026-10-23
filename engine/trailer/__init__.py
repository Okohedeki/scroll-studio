"""Launch trailers: `studio trailer <project>` cuts a 16:9 and a 9:16 launch film from what the site already rendered.

  plan     the cut (plan.py): explicit `trailer.shots`, or derived for `trailer: {}`: hook, story, product reveal,
           feature callouts, end card, every cut on the beat grid (`bpm`)
  track    a take's product screen position per frame (take.py --pass track), for the 9:16 reframe
  record   scroll recordings of non-film sections (engine/record.py; at phone size for 9:16)
  type     captions, callouts and the end card in the theme's fonts (type.py, headless Chrome, transparent PNGs)
  render   footage reframed per format (frame.py) with the type over it, encoded once per format
  final    music (trimmed, faded, loudness-normalised) muxed in; H.264 yuv420p CRF 18 +faststart; posters

Every stage is cached by its inputs in .build/_trailer, so re-running costs nothing until something changes.
Output: dist/trailer/trailer-16x9.mp4, trailer-9x16.mp4 and a poster JPG beside each.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from ..config import settings
from ..project import BuildContext, BuildError, Project, ffmpeg, file_key
from ..spec import Trailer
from . import frame as fr
from .plan import Planner, Shot, end_card, film_source, product_still
from .type import LAYOUT, render as render_type

HERE = Path(__file__).resolve().parent
FORMATS = ("16x9", "9x16")


def _hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * np.cos(np.pi * x)


def cut_frames(shots: list[Shot], bpm: float, fps: int) -> list[tuple[int, int]]:
    """Frame span of each shot: cuts at whole beats, rounded to frames from the running time (no drift)."""
    beat, t, out = 60.0 / bpm, 0.0, []
    for s in shots:
        a = round(t * fps)
        t += s.beats * beat
        out.append((a, round(t * fps)))
    return out


def timeline(shots: list[Shot], cuts: list[tuple[int, int]], fps: int, bpm: float, card: dict) -> dict:
    """What the type layer draws, in seconds."""
    beat = 60.0 / bpm
    items, texty = [], []
    for s, (a, b) in zip(shots, cuts):
        t0, t1 = a / fps, b / fps
        if s.kind == "end":
            items.append({"kind": "end", "t0": t0, "t1": t1 + 10, "fade_out": 0.01, "beat": beat, "delay": 0.25, **card})
            continue
        if s.kind == "card":
            items.append({"kind": "card", "t0": t0, "t1": t1 - 0.04, "title": s.text, "kicker": s.kicker,
                          "fade_out": 0.25})
        if s.callouts:
            k = len(s.callouts)
            per = (t1 - t0) / k
            for j, line in enumerate(s.callouts):
                c0 = t0 + j * per
                items.append({"kind": "callout", "t0": c0, "t1": c0 + per - 0.02, "title": line, "kicker": s.kicker,
                              "kstatic": j > 0, "count": f"{j + 1:02d} / {k:02d}" if k > 1 else "",
                              "fade_out": 0.1, "delay": 0.02})
            texty.append((t0, t1))
        elif s.kind != "card" and (s.caption or s.kicker):
            items.append({"kind": "caption", "t0": t0, "t1": t1 - 0.06, "title": s.caption, "kicker": s.kicker,
                          "fade_out": 0.34})
            texty.append((t0, t1))
    merged: list[list[float]] = []
    for a, b in texty:   # one scrim under a run of captioned shots, so it never flickers at the cuts
        if merged and a - merged[-1][1] < 1e-6:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    scrims = [{"kind": "scrim", "t0": a, "t1": b, "fade_in": 0.35, "fade_out": 0.4} for a, b in merged]
    total = cuts[-1][1] if cuts else 0
    return {"fps": fps, "frames": total, "items": scrims + items}


# ---------------------------------------------------------------- the take's product track

def product_track(project: Project, ctx: BuildContext, sec_id: str) -> Optional[Path]:
    """Screen position of the take's product per frame, from the take's own camera: the take's `track` stage
    (engine.product.take_track, `.build/<section>/product/track.json`), built here if the take hasn't made it yet."""
    from ..product import take_track
    try:
        return take_track(project, sec_id, log=ctx.log)
    except Exception as e:   # no product model on disk, no Blender...: fall back to the saliency crop
        ctx.log(f"  note: no product track for '{sec_id}' ({e}); the 9:16 crop follows saliency instead")
        return None


# ---------------------------------------------------------------- scroll recordings of other sections

def recording(project: Project, ctx: BuildContext, shot: Shot, fmt: str, fps: int, seconds: float) -> Path:
    from ..record import record
    if not (project.dist / "index.html").exists():
        raise BuildError(f"trailer: recording '{shot.section}' needs the built site; run `studio build` first")
    phone = fmt == "9x16"
    size, dpr = ((540, 960), 2.0) if phone else ((1920, 1080), 1.0)
    key = {"section": shot.section, "span": list(shot.span), "fmt": fmt, "fps": fps, "s": round(seconds, 3),
           "site": file_key(project.dist / "index.html")}
    out = ctx.work / "rec" / f"{shot.section}-{fmt}-{_hash(key)}.mp4"
    ctx.stage(f"rec_{shot.section}_{fmt}", key, [out],
              lambda: record(project.dist, out, section=shot.section, size=size, dpr=dpr, mobile=phone,
                             seconds=seconds, fps=fps, span=shot.span, log=lambda m: None))
    return out


# ---------------------------------------------------------------- render one format

def _blend(img: np.ndarray, over: Optional[np.ndarray]) -> np.ndarray:
    if over is None:
        return img
    a = over[:, :, 3:4].astype(np.float32) * (1 / 255)
    return (img.astype(np.float32) * (1 - a) + over[:, :, :3].astype(np.float32) * a).astype(np.uint8)


def _hex_bgr(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)


def render_format(shots: list[Shot], cuts, fmt: str, fps: int, sources: dict, tracks: dict, type_dir: Path,
                  theme: dict, end_bg: str, out: Path, log, progress) -> None:
    import cv2
    L = LAYOUT[fmt]
    W, H = L["W"], L["H"]
    total = cuts[-1][1]
    index = json.loads((type_dir / "index.json").read_text())
    cache: dict[str, np.ndarray] = {}

    def overlay(i):
        name = index[i] if i < len(index) else None
        if not name:
            return None
        if name not in cache:
            if len(cache) > 6:
                cache.pop(next(iter(cache)))
            cache[name] = cv2.imread(str(type_dir / name), cv2.IMREAD_UNCHANGED)
        return cache[name]

    bg = np.zeros((H, W, 3), np.uint8)
    bg[:] = _hex_bgr(theme["colors"]["bg"])
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                            "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264",
                            "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", str(out)],
                           stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    last = bg.copy()
    prev_z = None     # (source, end zoom) of the shot before, so a freeze after it carries its push on
    fi = 0
    try:
        for k, (s, (a, b)) in enumerate(zip(shots, cuts)):
            n = b - a
            z0, z1 = s.zoom or (1.0, 1.0)
            if s.kind == "film" and s.zoom is None and s.track and tracks.get(s.track):
                # a take's product: push in until it reads large, as far as the source's resolution allows
                zmax = fr.max_zoom(s.src, W, H, fmt)
                times = [s.t0 + (0 if s.hold else i * s.speed / fps) for i in range(n)]
                zp = fr.product_push(fr.load_track(tracks[s.track]), times, fmt, zmax)
                if zp is not None:
                    if s.hold and prev_z and prev_z[0] == s.src:
                        z0, z1 = prev_z[1], max(prev_z[1], min(zmax, prev_z[1] + (zmax - 1) * 0.2))
                    elif s.role in ("reveal", "hook"):
                        z0, z1 = 1 + (zp - 1) * 0.25, 1 + (zp - 1) * 0.85
                    else:
                        z0, z1 = 1 + (zp - 1) * 0.6, 1 + (zp - 1) * 0.85
            prev_z = (s.src, z1) if s.kind == "film" else None
            zooms = [z0 + (z1 - z0) * _ease(i / max(n - 1, 1)) for i in range(n)]
            if s.kind == "film":
                need_focus = fmt != "16x9" or z0 > 1.001 or z1 > 1.001 or s.focus is not None
                path = (fr.focus_path(s.src, s.t0, n, fps, s.speed, s.hold, W, H, fr.load_track(tracks.get(s.track)), s.focus)
                        if need_focus else np.full((n, 2), 0.5))
                src_iter = fr.frames(s.src, s.t0, n, fps, s.speed, s.hold)
                gen = (fr.warp(f, W, H, path[i][0], path[i][1], zooms[i]) for i, f in enumerate(src_iter))
            elif s.kind == "record":   # recorded at this size; a slow push keeps a short section alive
                if s.zoom is None:
                    zooms = [1.0 + 0.05 * _ease(i / max(n - 1, 1)) for i in range(n)]
                fx, fy = s.focus or (0.5, 0.45)
                gen = (fr.warp(f, W, H, fx, fy, zooms[i]) for i, f in enumerate(fr.frames(sources[k], 0.0, n, fps)))
            elif s.kind == "still":
                still = sources[k]   # laid out by _still: the product large, above the type when there is some
                fx, fy = s.focus or (0.5, 0.5)
                if s.zoom is None:   # a slow push and drift, so a still moves like a shot
                    zooms = [1.0 + 0.08 * _ease(i / max(n - 1, 1)) for i in range(n)]
                gen = (fr.warp(still, W, H, fx - 0.015 + 0.03 * _ease(i / max(n - 1, 1)), fy, zooms[i]) for i in range(n))
            elif s.kind == "card":
                gen = (bg for _ in range(n))
            else:   # end card: the last frame, blurred under the theme's background colour
                tint = 0.8 if end_bg == "blur" else 1.0
                small = cv2.resize(last, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
                blur = cv2.resize(cv2.GaussianBlur(small, (0, 0), 6), (W, H), interpolation=cv2.INTER_CUBIC)
                card = (blur.astype(np.float32) * (1 - tint) + bg.astype(np.float32) * tint).astype(np.uint8)
                ramp = max(1, round(fps * 0.45))
                gen = (cv2.addWeighted(last, 1 - _ease(i / ramp), card, _ease(i / ramp), 0) if i < ramp else card
                       for i in range(n))
            for i, img in enumerate(gen):
                if fi < 5:   # a breath of black before the first frame
                    img = (img.astype(np.float32) * (fi / 5)).astype(np.uint8)
                if s.kind != "end":
                    last = img
                enc.stdin.write(np.ascontiguousarray(_blend(img, overlay(fi))).tobytes())
                fi += 1
                if fi % 24 == 0:
                    progress(fi / total, f"{fmt} frame {fi}/{total}")
        enc.stdin.close()
        if enc.wait() != 0:
            raise BuildError("trailer encode failed: " + enc.stderr.read().decode(errors="replace")[-800:])
    finally:
        if enc.poll() is None:
            enc.kill()
    log(f"  {fmt}: {fi} frames at {W}x{H}")


def finish(video: Path, out: Path, music: Optional[Path], t: Trailer, seconds: float, poster_t: float, log) -> None:
    """Mux music (trimmed from music_start, faded out over the end card, loudness-normalised), encode for social
    (H.264 high, yuv420p, CRF 18, +faststart) and write a poster."""
    out.parent.mkdir(parents=True, exist_ok=True)
    vargs = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart"]
    if music:
        fade = min(2.0, seconds / 6)
        pre = f"afade=t=in:d=0.05,afade=t=out:st={seconds - fade:.3f}:d={fade:.3f}"
        meas = subprocess.run([settings()["ffmpeg"], "-hide_banner", "-ss", f"{t.music_start:.3f}", "-t", f"{seconds:.3f}",
                               "-i", str(music), "-af", f"{pre},loudnorm=I={t.loudness}:TP=-1.5:LRA=11:print_format=json",
                               "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        txt = meas.stderr
        try:
            m = json.loads(txt[txt.rindex("{"):txt.rindex("}") + 1])
            ln = (f"loudnorm=I={t.loudness}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                  f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
        except (ValueError, KeyError):
            ln = f"loudnorm=I={t.loudness}:TP=-1.5:LRA=11"
        ffmpeg("-i", video, "-ss", f"{t.music_start:.3f}", "-t", f"{seconds:.3f}", "-i", music, "-map", "0:v", "-map", "1:a",
               "-af", f"{pre},{ln},aresample=48000", *vargs, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
               "-shortest", out, log=log)
    else:
        ffmpeg("-i", video, *vargs, "-an", out, log=log)
    ffmpeg("-ss", f"{poster_t:.3f}", "-i", out, "-frames:v", "1", "-q:v", "2", out.with_suffix(".jpg"))


# ---------------------------------------------------------------- entry point

def take_tracks(project: Project, site, ctx: BuildContext) -> dict[str, Path]:
    """The product's screen position in each built take, from the take's own camera: where to cut, push and crop."""
    tracks: dict[str, Path] = {}
    for s in site.sections:
        if s.type == "film" and s.take and s.take.product and film_source(project, s) is not None:
            p = product_track(project, ctx, s.id)
            if p:
                tracks[s.id] = p
    return tracks


def plan_only(project: Project, log: Callable[[str], None] = print) -> list[Shot]:
    """The cut, logged, without rendering anything (`studio trailer --plan`)."""
    site = project.load()
    t = site.trailer or Trailer()
    tracks = take_tracks(project, site, BuildContext(project, "_trailer", log=lambda m: None))
    shots = Planner(project, site, t, log, tracks={k: fr.load_track(v) for k, v in tracks.items()}).plan()
    _log_cut(shots, cut_frames(shots, t.bpm, t.fps), t, log)
    return shots


def _log_cut(shots, cuts, t, log):
    fps = t.fps
    log(f"trailer: {len(shots)} shots, {cuts[-1][1] / fps:.1f}s at {t.bpm:g} bpm, {fps} fps")
    for s, (a, b) in zip(shots, cuts):
        what = (f"{s.src.name} @{s.t0:.2f}s" + (" hold" if s.hold else "")) if s.kind == "film" else s.kind
        words = s.caption or " / ".join(s.callouts) or s.text
        log(f"  {a / fps:5.1f}s  {s.beats:2d} beats  {s.role:8s} {what:24s} {re.sub('<[^>]+>', '', words)[:60]}")


def build_trailer(project: Project, formats: Optional[list[str]] = None, force: bool = False,
                  log: Callable[[str], None] = print,
                  progress: Callable[[float, str], None] = lambda f, m="": None) -> dict:
    from ..compile import themes
    site = project.load()
    t = site.trailer
    if t is None:
        log("no `trailer:` in site.yaml; using the default cut (add `trailer: {}` to keep it, or list shots)")
        t = Trailer()
    fmts = formats or list(t.formats)
    for f in fmts:
        if f not in FORMATS:
            raise BuildError(f"unknown trailer format {f} (16x9, 9x16)")
    theme = themes.resolve(site.theme)
    ctx = BuildContext(project, "_trailer", log=log, force=force, progress=progress)
    tracks = take_tracks(project, site, ctx)
    planner = Planner(project, site, t, log, tracks={k: fr.load_track(v) for k, v in tracks.items()})
    shots = planner.plan()
    fps = t.fps
    cuts = cut_frames(shots, t.bpm, fps)
    seconds = cuts[-1][1] / fps
    _log_cut(shots, cuts, t, log)
    if not (5 <= seconds <= 90):
        log(f"  note: the cut runs {seconds:.1f}s")

    music = None
    if t.music:
        from ..inputs import resolve_path
        music = resolve_path(project, t.music, log)


    card = end_card(site, t)
    dist = project.dist / "trailer"
    outs = {}
    reveal = next((k for k, s in enumerate(shots) if s.role == "reveal"), None)
    if reveal is None:
        reveal = max(0, len(shots) - 2)
    pa, pb = cuts[reveal]
    poster_t = (pa + (pb - pa) * 0.72) / fps
    for fmt in fmts:
        sources: dict = {}
        for k, (s, (a, b)) in enumerate(zip(shots, cuts)):
            if s.kind == "record":
                sources[k] = recording(project, ctx, s, fmt, fps, (b - a) / fps * s.speed + 0.1)
            elif s.kind == "still":
                sources[k] = _still(project, site, s, fmt, theme, log)
        tl = timeline(shots, cuts, fps, t.bpm, card)
        tdir = ctx.work / "type" / fmt
        tkey = {"tl": tl, "theme": theme, "layout": LAYOUT[fmt], "html": file_key(HERE / "type.html"),
                "css": file_key(HERE / "type.py")}
        ctx.stage(f"type_{fmt}", tkey, [tdir / "index.json"], lambda: render_type(tl, theme, fmt, tdir, log, progress))
        raw = ctx.work / "render" / f"{fmt}.mp4"
        src_keys = sorted({str(s.src) for s in shots if s.src}) + [str(p) for p in tracks.values()]
        rkey = {"shots": [s.key() for s in shots], "cuts": cuts, "fps": fps, "type": tkey,
                "src": [file_key(Path(p)) for p in src_keys],
                "media": {str(k): file_key(v) for k, v in sources.items()},
                "code": [file_key(HERE / "frame.py"), file_key(HERE / "__init__.py")], "end": t.end_background}
        ctx.stage(f"render_{fmt}", rkey, [raw], lambda: render_format(
            shots, cuts, fmt, fps, {k: _load(v) for k, v in sources.items()}, tracks, tdir, theme, t.end_background,
            raw, log, progress))
        final = dist / f"trailer-{fmt}.mp4"
        fkey = {"raw": file_key(raw), "music": file_key(music) if music else None, "start": t.music_start,
                "lufs": t.loudness, "poster": poster_t}
        ctx.stage(f"final_{fmt}", fkey, [final, final.with_suffix(".jpg")],
                  lambda: finish(raw, final, music, t, seconds, poster_t, log))
        outs[fmt] = final
        log(f"-> {final}")
    return {"videos": {k: str(v) for k, v in outs.items()}, "seconds": round(seconds, 2),
            "posters": {k: str(v.with_suffix(".jpg")) for k, v in outs.items()}}


def _load(v):
    """Stills are passed to the renderer as images; recordings as paths."""
    if isinstance(v, Path) and v.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        import cv2
        return cv2.imread(str(v), cv2.IMREAD_COLOR)
    return v


def _still(project: Project, site, s: Shot, fmt: str, theme: dict, log) -> Path:
    """A product still from the product feature, laid out for this format: the product (cut out by its alpha, or
    by what differs from a flat background) scaled to fill most of the frame, raised above the type when the shot
    has words, on the theme background. Never scaled up more than 1.3x its own pixels."""
    import numpy as np
    from PIL import Image
    L = LAYOUT[fmt]
    W, H = L["W"], L["H"]
    p = product_still(project, site, s.text, (W, H), None, log)    # None: a transparent PNG when it can
    im = Image.open(p)
    bgc = theme["colors"]["bg"]
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        box = im.split()[3].point(lambda v: 255 if v > 8 else 0).getbbox()
    else:
        im = im.convert("RGB")
        a = np.asarray(im).astype(np.int16)
        edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
        diff = np.abs(a - np.median(edge, axis=0)).sum(axis=2) > 36
        ys, xs = np.nonzero(diff)
        box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if len(xs) > 20 else None
        im = im.convert("RGBA")
    words = bool(s.caption or s.callouts)
    share, cy = (0.44, 0.33) if words else (0.78, 0.5)
    canvas = Image.new("RGBA", (W, H), bgc)
    if box:
        prod = im.crop(box)
        k = min(share * H / prod.height, 0.86 * W / prod.width, 1.3 * max(W / im.width, H / im.height, 1.0))
        prod = prod.resize((max(1, round(prod.width * k)), max(1, round(prod.height * k))), Image.LANCZOS)
        canvas.alpha_composite(prod, ((W - prod.width) // 2, max(0, min(H - prod.height, round(cy * H - prod.height / 2)))))
    else:
        canvas.alpha_composite(im.resize((W, H), Image.LANCZOS))
    out = project.build / "_trailer" / "stills" / f"{p.stem}-{fmt}-{'t' if words else 'f'}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out)
    s.focus = s.focus or (0.5, cy)
    return out

