"""`studio ugc`: vertical creator-style video ads, one per concept and language.

For each of the first `outputs.ugc.concepts` concepts (engine/concepts.py):

1. a presenter still: an edit job puts a generated presenter (outputs.ugc.presenter) with the product still, the
   product kept as it is. The presenter is a made-up person, never a real one's likeness.
2. a presenter clip: a video job brings that still to life (local LTX-2.3 through ComfyUI, or a provider, as
   `models:` allows); with no video backend the still is shown with a slow push-in.
3. product shots: the picked stills with a push-in, cut to fill the script.
4. in each language: the concept's script spoken by a speech backend, its hook on screen at the start, and the
   script as captions a few words at a time.

The voice is a voiceover: lip sync is not attempted. Captions use DejaVu Sans or Arial; a language in another
script (Japanese, Arabic...) needs a font with those letters installed. Written to <project>/ugc/ with ugc.json
saying what went into each video."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw

from .ads import RATIOS, _font, reframe
from .project import BuildError, Project, ffmpeg, probe

FPS = 30
PRESENTER_EDIT = ("Make this a frame of a vertical phone video: {presenter} holding this exact product up toward the "
                  "camera, looking into the lens, natural window light, handheld selfie framing, real home setting. "
                  "The person is made up, not any real or famous person. Keep the product exactly as it is: its "
                  "shape, colours, label and size in the hand.")
PRESENTER_MOTION = ("{presenter} talks to the camera and shows the product, natural handheld phone video, small "
                    "head and hand movements, the product stays the same")


def size_of(aspect: str, width: int) -> tuple[int, int]:
    w = width - width % 2
    h = round(w / RATIOS[aspect])
    return w, h - h % 2


def chunks(script: str, words: int = 3) -> list[str]:
    """The script as caption chunks: a few words each, or a few characters for scripts written without spaces."""
    text = " ".join(script.split())
    if not text:
        return []
    if " " not in text and len(text) > 12:              # Japanese, Chinese, Thai...: by characters
        return [text[i:i + 8] for i in range(0, len(text), 8)]
    ws = text.split(" ")
    return [" ".join(ws[i:i + words]) for i in range(0, len(ws), words)]


def timings(parts: list[str], total: float, start: float = 0.0) -> list[tuple[float, float]]:
    """(from, to) for each chunk, in proportion to its length, over `total` seconds."""
    weights = [max(len(p), 1) for p in parts]
    whole = sum(weights) or 1
    out, t = [], start
    for wgt in weights:
        d = total * wgt / whole
        out.append((round(t, 3), round(t + d, 3)))
        t += d
    return out


def caption_png(text: str, w: int, h: int, out: Path, top: bool = False) -> Path:
    """A full-frame transparent PNG with `text` on a rounded dark plate: bottom third, or near the top for a hook."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = round(w * (0.075 if top else 0.062))
    font = _font(size, bold=True)
    lines, cur = [], ""
    for word in text.split(" "):
        test = f"{cur} {word}".strip()
        if d.textlength(test, font=font) > w * 0.82 and cur:
            lines.append(cur)
            cur = word
        else:
            cur = test
    lines.append(cur)
    lh = round(size * 1.2)
    block = lh * len(lines)
    y = round(h * 0.12) if top else round(h * 0.70) - block // 2
    for ln in lines:
        tw = d.textlength(ln, font=font)
        x = (w - tw) / 2
        pad = size * 0.35
        d.rounded_rectangle((x - pad, y - pad * 0.5, x + tw + pad, y + lh), radius=round(size * 0.3),
                            fill=(16, 16, 18, 215))
        d.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += lh
    img.save(out)
    return out


def push_in(still: Path, out: Path, seconds: float, w: int, h: int, log) -> Path:
    frames = max(1, round(seconds * FPS))
    zoom = f"zoompan=z='1+0.08*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS}"
    ffmpeg("-loop", "1", "-i", still, "-vf", f"scale={w * 2}:{h * 2},{zoom},format=yuv420p", "-t", f"{seconds:.3f}",
           "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out, log=log)
    return out


def fit_clip(src: Path, out: Path, seconds: float, w: int, h: int, log) -> Path:
    """A clip cropped to fill w x h at FPS, cut (or its last frame held) to `seconds`."""
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},"
          f"tpad=stop_mode=clone:stop_duration={seconds:.3f},format=yuv420p")
    ffmpeg("-i", src, "-vf", vf, "-t", f"{seconds:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           out, log=log)
    return out


def cut_join(parts: list[Path], out: Path, log) -> Path:
    """Hard cuts, the way creator videos are edited."""
    if len(parts) == 1:
        shutil.copy(parts[0], out)
        return out
    inputs = [a for p in parts for a in ("-i", p)]
    graph = "".join(f"[{i}:v]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]"
    ffmpeg(*inputs, "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", out, log=log)
    return out


def overlay(video: Path, plates: list[tuple[Path, float, float]], out: Path, log) -> Path:
    if not plates:
        shutil.copy(video, out)
        return out
    inputs = ["-i", video] + [a for p, _, _ in plates for a in ("-i", p)]
    chain, last = [], "[0:v]"
    for i, (_, a, b) in enumerate(plates, start=1):
        tag = f"[o{i}]"
        chain.append(f"{last}[{i}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'{tag}")
        last = tag
    ffmpeg(*inputs, "-filter_complex", ";".join(chain), "-map", last, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "18", "-pix_fmt", "yuv420p", out, log=log)
    return out


def presenter_still(project: Project, spec, product: Path, cfg, seed: int, work: Path, log) -> tuple[Optional[Path], str]:
    from .router import EditJob, NoBackend, choose, route
    try:
        choose("edit", spec.models)
    except NoBackend as e:
        return None, f"no presenter ({e})"
    out = work / f"presenter-{seed}.png"
    r = route(EditJob((str(product),), PRESENTER_EDIT.format(presenter=cfg.presenter), seed, 24), out, spec.models,
              build=project.build, log=log)
    return out, f"presenter by {r.backend}"


def presenter_clip(project: Project, spec, still: Path, cfg, seed: int, w: int, h: int, work: Path,
                   log) -> tuple[Path, str]:
    from .router import NoBackend, VideoJob, choose, route
    raw = work / f"presenter-{seed}.raw.mp4"
    fitted = work / f"presenter-{seed}.mp4"
    try:
        choose("video", spec.models)
        r = route(VideoJob(str(still), PRESENTER_MOTION.format(presenter=cfg.presenter), cfg.presenter_seconds, w, h,
                           seed), raw, spec.models, build=project.build, log=log)
        return fit_clip(r.path or raw, fitted, cfg.presenter_seconds, w, h, log), f"moving, by {r.backend}"
    except NoBackend:
        framed = work / f"presenter-{seed}.framed.png"
        Image.open(still).convert("RGB").resize((w, h)).save(framed)
        return push_in(framed, fitted, cfg.presenter_seconds, w, h, log), "a still with a push-in (no video backend)"


def make(project: Project, log: Callable[[str], None] = print) -> dict:
    from . import concepts as concept_mod
    from .languages import suffix
    from .stills import run as stills
    from .video import sources, voiceover
    spec = project.load_project() if project.is_project_file else None
    if spec is None or spec.outputs.ugc is None:
        raise BuildError(f"{project.name} has no outputs.ugc in project.yaml (docs/stills.md#video-ads)")
    cfg = spec.outputs.ugc
    chosen = concept_mod.pick(project, cfg.concepts)
    if not chosen:
        raise BuildError(f"{project.name} has no ad concepts yet: add outputs.concepts and run "
                         f"`studio concepts {project.name}` first")
    state = stills.load(project) or {}
    picks = sources(state, ["lifestyle", "detail", "packshot"], 2)
    if not picks:
        raise BuildError(f"{project.name} has no product stills to show: run `studio stills {project.name}` first")
    w, h = size_of(cfg.aspect, cfg.width)
    work = project.build / "_ugc"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    ratio = RATIOS[cfg.aspect]
    broll_stills = []
    for i, c in enumerate(picks):
        img = Image.open(stills.folder(project) / c["image"]).convert("RGB")
        mask = Image.open(stills.folder(project) / c["image"].replace(".png", ".mask.png")).convert("L")
        frame, _ = reframe(img, mask, ratio, w)
        p = work / f"broll{i}.png"
        frame.resize((w, h)).save(p)
        broll_stills.append(p)
    product = stills.folder(project) / picks[-1]["image"]
    out_dir = project.root / "ugc"
    out_dir.mkdir(parents=True, exist_ok=True)
    langs = spec.languages
    report = []
    for n, concept in enumerate(chosen):
        seed = 101 + n
        still, p_note = presenter_still(project, spec, product, cfg, seed, work, log)
        clip, c_note = presenter_clip(project, spec, still, cfg, seed, w, h, work, log) if still else (None, "")
        for lang in langs:
            copy = concept["copy"].get(lang)
            if not copy:
                continue
            lw = work / f"{concept['id']}-{lang}"
            lw.mkdir()
            voice, v_note = voiceover(project, copy["script"], cfg.voice, spec.models, lw, log)
            spoken = float(probe(voice, "format=duration").get("duration") or 0) if voice else 0.0
            total = max(spoken + 0.6, spec.outputs.concepts.seconds if spec.outputs.concepts else 15.0)
            parts, used = [], 0.0
            if clip is not None:
                parts.append(clip)
                used = cfg.presenter_seconds
            k = 0
            while used < total - 0.05:
                d = min(3.0, total - used)
                parts.append(push_in(broll_stills[k % len(broll_stills)], lw / f"b{k}.mp4", d, w, h, log))
                used += d
                k += 1
            body = cut_join(parts, lw / "body.mp4", log)
            plates = []
            if copy.get("hook"):
                plates.append((caption_png(copy["hook"], w, h, lw / "hook.png", top=True), 0.0,
                               min(2.6, total)))
            if cfg.captions:
                said = chunks(copy["script"])
                for i, (text, (a, b)) in enumerate(zip(said, timings(said, spoken or total * 0.95, 0.2))):
                    plates.append((caption_png(text, w, h, lw / f"cap{i}.png"), a, b))
            framed = overlay(body, plates, lw / "framed.mp4", log)
            out = out_dir / f"{concept['id']}{suffix(lang, langs)}.mp4"
            music = project.path(cfg.music) if cfg.music else None
            tracks = [p for p in (voice, music) if p is not None]
            if not tracks:
                shutil.copy(framed, out)
            elif voice and music:
                ffmpeg("-i", framed, "-i", voice, "-i", music, "-filter_complex",
                       f"[2:a]volume=0.18,atrim=0:{total:.2f}[m];[1:a]adelay=200|200[vo];"
                       f"[vo][m]amix=inputs=2:duration=longest:dropout_transition=0,atrim=0:{total:.2f}[a]",
                       "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", out, log=log)
            else:
                ffmpeg("-i", framed, "-i", tracks[0], "-filter_complex",
                       f"[1:a]adelay=200|200,atrim=0:{total:.2f}[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                       "-c:a", "aac", "-b:a", "160k", out, log=log)
            report.append({"file": out.name, "concept": concept["id"], "angle": concept["angle"], "language": lang,
                           "seconds": round(total, 2), "size": [w, h], "presenter": p_note, "presenter_clip": c_note,
                           "voice": v_note, "captions": cfg.captions, "hook": copy.get("hook")})
            log(f"  ugc: {out.name} ({total:.1f} s; {v_note})")
    (out_dir / "ugc.json").write_text(json.dumps({"videos": report}, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"videos": report, "folder": str(out_dir)}

