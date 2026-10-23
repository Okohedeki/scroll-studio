"""Stand-ins: what the page shows for a scene that is not rendered yet.

A film (or a product turn, or an image scene at sketch level) becomes a short film of its storyboard frames, scrubbed
by scroll like the real one: held stills that dissolve into one another (stills), or the same with a slow camera move
per shot (animatic). The page keeps the section's own steps, captions, layout and length, so the storyboard site is
the real page with stills standing in for the films. `beat_clip` gives `studio build --only` a clip for a beat that is
not selected and not rendered yet.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Optional

from ..project import Project, ffmpeg, file_key
from ..spec import FilmScene
from .cards import Card, _digest
from .motion import Piece, from_text, render, timings

SIZE = (1280, 720)


def section(project: Project, sec, cards: list[Card], level: str, log: Callable[[str], None]) -> Optional[tuple]:
    """(config, web dir, section to render) for a scene shown by its storyboard frames, or None when it has none."""
    pieces = [p for c in cards for p in c.pieces if p.start is not None or p.video is not None]
    if not pieces:
        return None
    moves = level == "animatic"
    fade = sec.beat_fade if getattr(sec, "beats", None) else 0.5
    fps = 24 if moves or any(p.video for p in pieces) else 12
    work = project.build / "_storyboard" / sec.id
    web = work / "web"
    key = {"p": [p.key() for p in pieces], "fade": fade, "fps": fps, "moves": moves, "size": SIZE, "v": 1}
    stamp = work / "standin.json"
    film = web / "film.mp4"
    if not (film.exists() and stamp.exists() and json.loads(stamp.read_text()).get("key") == _digest(key)):
        log(f"  {sec.id}: stand-in film from {len(pieces)} shot(s)")
        if web.exists():
            shutil.rmtree(web)
        web.mkdir(parents=True)
        render(pieces, film, SIZE, fps=fps, fade=fade, gop=6, moves=moves, log=log)
        ffmpeg("-i", film, "-frames:v", "1", "-q:v", "3", web / "poster.jpg")
        ffmpeg("-sseof", "-0.1", "-i", film, "-frames:v", "1", "-q:v", "3", "-update", "1", web / "end.jpg")
        stamp.write_text(json.dumps({"key": _digest(key)}))
    base = f"assets/{sec.id}/"
    cfg = {"video": base + "film.mp4", "videoMobile": base + "film.mp4", "poster": base + "poster.jpg",
           "end": base + "end.jpg", "storyboard": level}
    shown = as_film(sec)
    if getattr(sec, "beats", None):
        from ..scenes.film import pin_steps
        _, _, used = timings(pieces, fade)
        pin_steps(shown, [p.seconds for p in pieces], used)
    return cfg, web, shown


def as_film(sec):
    """The section as a film scene with the same id, copy and layout (the page then plays the stand-in film)."""
    if sec.type == "film":
        return sec.model_copy(deep=True)
    keep = {k: getattr(sec, k) for k in ("id", "nav_label", "layout", "side", "length", "steps", "hud", "cue", "shade",
                                         "surface", "backdrop") if hasattr(sec, k)}
    return FilmScene(**{k: (v.model_copy(deep=True) if hasattr(v, "model_copy") else
                            [x.model_copy(deep=True) for x in v] if isinstance(v, list) else v) for k, v in keep.items()},
                     video="storyboard")


def beat_clip(project: Project, sec: FilmScene, b, out: Path, size: tuple[int, int], log: Callable[[str], None]) -> Path:
    """A beat's stand-in clip for `build --only`: its storyboard still (or a card, never a new render) at the beat's
    size and frame rate, with the slow move its motion text suggests. Not stamped: the full build renders the beat."""
    from ..fidelity import previewing
    from ..inputs import resolve_image
    W, H = size
    from ..camera_beats import start_ref
    ref = start_ref(sec, sec.beats.index(b), (W, H))
    with previewing("sketch"):
        still = resolve_image(project, ref, log)
        end = resolve_image(project, b.end_image, log) if b.end_image else None
    key = {"still": file_key(still), "end": file_key(end) if end else None, "s": b.seconds - b.trim, "size": [W, H],
           "m": b.motion}
    stamp = out.with_suffix(".json")
    if not (out.exists() and stamp.exists() and stamp.read_text() == _digest(key)):
        render([Piece(b.seconds - b.trim, still, end, from_text(b.motion))], out, (W, H), fps=24, fade=0, gop=None,
               crf=16, log=log)
        stamp.write_text(_digest(key))
    return out


def cache_only(project: Project, sec, theme: dict, log: Callable[[str], None]) -> Optional[tuple]:
    """A never-built scene in `build --only`: its stand-in from what is cached (the last storyboard's frames, cached
    stills, else cards). Nothing is rendered for it."""
    from ..plan import plan_build
    from .cards import Maker
    from .record import load
    plan = plan_build(project, only=[sec.id], blocks=False)
    prev = load(project)
    mk = Maker(project, project.load(), plan, "sketch", prev, only=set(), motion=False, log=log)
    fn = getattr(mk, f"scene_{sec.type}", None)
    cards = fn(sec) if fn else []
    return section(project, sec, cards, "sketch", log)
