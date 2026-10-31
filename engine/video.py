"""`studio video`: a short product video from the picked stills (issue #179).

Each still (every shot's pick, then its shortlist, up to `per_shot`) is reframed to the aspect around the product and
given a slow push-in; the segments are joined with cross dissolves and end on a card with the ads' headline and call
to action. A voiceover is spoken by a speech backend (engine/router) when one can run, the music file laid under it;
with neither, the video is silent. Written to <project>/video/ with video.json saying what went in.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from .ads import RATIOS, brand_colours, reframe, set_copy
from .project import BuildError, Project, ffmpeg, probe

FPS = 30
END_CARD = 2.5
DISSOLVE = 0.5


def sources(state: dict, shots: list[str], per_shot: int) -> list[dict]:
    """The candidates to show, in order: for each shot its pick first, then its shortlist, at most per_shot each."""
    by_id = {c["id"]: c for c in state.get("candidates", [])}
    out = []
    for shot in shots:
        ids = [state.get("picked", {}).get(shot)] + list(state.get("shortlist", {}).get(shot) or [])
        seen: list[str] = []
        for i in ids:
            if i and i in by_id and i not in seen:
                seen.append(i)
        out += [by_id[i] for i in seen[:per_shot]]
    return out


def segment_seconds(total: float, n: int, end_card: bool) -> float:
    """Each still's time on screen, so the whole (dissolves overlapping) comes to `total`."""
    body = total - (END_CARD if end_card else 0)
    joins = n - 1 + (1 if end_card else 0)
    return max(1.0, (body + joins * DISSOLVE) / max(n, 1))


def _segment(still: Path, out: Path, seconds: float, w: int, h: int, log) -> None:
    frames = round(seconds * FPS)
    zoom = f"zoompan=z='1+0.10*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS}"
    ffmpeg("-loop", "1", "-i", still, "-vf", f"scale={w * 2}:{h * 2},{zoom},format=yuv420p", "-t", f"{seconds:.3f}",
           "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out, log=log)


def _join(parts: list[Path], seconds: list[float], out: Path, log) -> None:
    if len(parts) == 1:
        shutil.copy(parts[0], out)
        return
    inputs = [a for p in parts for a in ("-i", p)]
    chain, last, offset = [], "[0:v]", 0.0
    for i in range(1, len(parts)):
        offset += seconds[i - 1] - DISSOLVE
        tag = f"[v{i}]"
        chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={DISSOLVE}:offset={offset:.3f}{tag}")
        last = tag
    ffmpeg(*inputs, "-filter_complex", ";".join(chain), "-map", last, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "18", "-pix_fmt", "yuv420p", out, log=log)


def voiceover(project: Project, text: str, voice: str, policy, work: Path, log) -> tuple[Optional[Path], str]:
    """(the spoken file or None, a note on what happened)."""
    if not text.strip():
        return None, "no voiceover asked for"
    from .router import NoBackend, SpeechJob, choose, route
    try:
        choose("speech", policy)
    except NoBackend as e:
        return None, f"silent: {e}"
    out = work / "voice.mp3"
    r = route(SpeechJob(text, voice), out, policy, build=project.build, log=log)
    return out, f"voice by {r.backend} ({r.model})"


def make(project: Project, log: Callable[[str], None] = print) -> dict:
    from .stills import run as stills
    spec = project.load_project() if project.is_project_file else None
    if spec is None or spec.outputs.video is None:
        raise BuildError(f"{project.name} has no outputs.video in project.yaml (docs/stills.md#video)")
    v = spec.outputs.video
    state = stills.load(project)
    picks = sources(state or {}, list(v.shots), v.per_shot)
    if not picks:
        raise BuildError(f"{project.name} has no product stills to show: run `studio stills {project.name}` first")
    ratio = RATIOS[v.aspect]
    w = v.width - v.width % 2
    h = round(w / ratio)
    h -= h % 2
    work = project.build / "_video"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    ads = spec.outputs.ads
    end = bool(ads and (ads.headline or ads.cta))
    seg = segment_seconds(v.seconds, len(picks), end)
    parts, lengths = [], []
    for i, c in enumerate(picks):
        img = Image.open(stills.folder(project) / c["image"]).convert("RGB")
        mask = Image.open(stills.folder(project) / c["image"].replace(".png", ".mask.png")).convert("L")
        frame, _ = reframe(img, mask, ratio, w)
        still = work / f"still{i}.png"
        frame.resize((w, h)).save(still)
        part = work / f"seg{i}.mp4"
        _segment(still, part, seg, w, h, log)
        parts.append(part)
        lengths.append(seg)
    if end:
        last = picks[-1]
        img = Image.open(stills.folder(project) / last["image"]).convert("RGB")
        mask = Image.open(stills.folder(project) / last["image"].replace(".png", ".mask.png")).convert("L")
        band = 0.24 if ratio < 1 / 1.3 else 0.3 if ratio <= 1 else 0.34
        frame, _ = reframe(img, mask, ratio, w, keep_bottom=band)
        card, _ = set_copy(frame.resize((w, h)), ads.headline, ads.cta, brand_colours(project))
        still = work / "card.png"
        card.save(still)
        part = work / "card.mp4"
        _segment(still, part, END_CARD, w, h, log)
        parts.append(part)
        lengths.append(END_CARD)
    silent = work / "silent.mp4"
    _join(parts, lengths, silent, log)
    duration = float(probe(silent).get("duration") or v.seconds)

    text = v.voiceover
    if text.strip().lower() == "listing":
        lst = project.root / "listing" / "listing.json"
        text = json.loads(lst.read_text(encoding="utf-8"))["description"].split("\n\n")[0] if lst.exists() else ""
    voice, note = voiceover(project, text, v.voice, spec.models, work, log)
    music = project.path(v.music) if v.music else None
    folder = project.root / "video"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"video-{v.aspect}.mp4"
    tracks = [p for p in (voice, music) if p is not None]
    if not tracks:
        shutil.copy(silent, out)
    else:
        inputs = ["-i", silent] + [a for p in tracks for a in ("-i", p)]
        fade = f"afade=t=out:st={max(0.0, duration - 1.2):.2f}:d=1.2"
        if voice and music:
            graph = (f"[2:a]volume=0.22,atrim=0:{duration:.2f}[m];[1:a]adelay=400|400[vo];"
                     f"[vo][m]amix=inputs=2:duration=longest:dropout_transition=0,atrim=0:{duration:.2f},{fade}[a]")
        else:
            graph = f"[1:a]{'adelay=400|400,' if voice else ''}atrim=0:{duration:.2f},{fade}[a]"
        ffmpeg(*inputs, "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
               "-b:a", "160k", "-shortest", out, log=log)
    report = {"file": out.name, "seconds": round(duration, 2), "aspect": v.aspect, "size": [w, h],
              "stills": [c["id"] for c in picks], "end_card": end, "voice": note, "music": v.music}
    (folder / "video.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"  video: {out} ({duration:.1f} s; {note})")
    return report
