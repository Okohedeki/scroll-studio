"""animatic.mp4: the storyboard as a rough cut. Every shot of the page in order at its own length (a film's beats and
takes at their film timing, stills for a few seconds each), with a slow camera move per shot (or its --motion preview),
the page's captions set by the trailer's type layer (engine/trailer/type.py: the site's fonts and colours) and the
trailer's end card. 1920x1080, 24 fps."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..project import Project
from .cards import Card, _digest
from .motion import Piece, render, timings

FADE = 0.4


def write_timeline(project: Project, out: Path, total: float, shots: list[dict]) -> None:
    """animatic.timeline.json beside the mp4: where each shot sits in the cut, and what the spec and each shot looked like
    when it was cut (the edit workspace marks the cut stale when they change). `cut_at` is when it was last checked."""
    import time
    sigs, rev = {}, None
    try:
        from .edit import shots as shots_mod
        board = shots_mod.build(project)
        sigs, rev = {s.id: s.sig() for s in board.shots}, board.rev
    except Exception:
        pass
    (out.parent / "animatic.timeline.json").write_text(json.dumps(
        {"cut_at": time.time(), "duration": round(total, 3), "shots": shots, "sigs": sigs, "rev": rev}, indent=1), encoding="utf-8")


def build(project: Project, site, cards: list[Card], out: Path, log: Callable[[str], None] = print,
          progress: Callable[[float, str], None] = lambda f, m="": None) -> Path:
    import cv2
    from PIL import Image
    from ..compile import themes
    from ..spec import Trailer
    from ..trailer.plan import end_card, rich
    from ..trailer.type import LAYOUT, render as render_type
    theme = themes.resolve(site.theme)
    L = LAYOUT["16x9"]
    W, H, fps = L["W"], L["H"], 24
    pieces: list[Piece] = []
    spans = []     # (card, first piece, last piece)
    for c in cards:
        ps = [p for p in c.pieces if p.start is not None or p.video is not None]
        if ps:
            spans.append((c, len(pieces), len(pieces) + len(ps) - 1))
            pieces += ps
    if not pieces:
        return out
    work = project.build / "_storyboard" / "_animatic"
    work.mkdir(parents=True, exist_ok=True)
    bg = work / f"end_{theme['colors']['bg'].lstrip('#')}.png"
    if not bg.exists():
        Image.new("RGB", (W, H), theme["colors"]["bg"]).save(bg)
    pieces.append(Piece(3.5, bg, None, label="end"))
    starts, total, fade = timings(pieces, FADE)
    items, texty = [], []
    for c, a, b in spans:
        t0, t1 = starts[a], starts[b] + pieces[b].seconds
        for u0, u1, title, kicker in c.captions:
            c0, c1 = t0 + (t1 - t0) * u0 + (fade * 0.6 if u0 <= 0 else 0), t0 + (t1 - t0) * u1 - (fade if u1 >= 1 else 0)
            if c1 - c0 < 0.4:
                continue
            prev = items[-1] if items and items[-1]["kind"] == "caption" else None
            if prev and prev["title"] == rich(title) and c0 - prev["t1"] < 1.2:
                prev["t1"] = c1 - 0.06       # one caption held across shots: it stays up through the cut
                texty[-1][1] = c1
                continue
            items.append({"kind": "caption", "t0": c0, "t1": c1 - 0.06, "title": rich(title), "kicker": rich(kicker),
                          "fade_out": 0.3})
            texty.append([c0, c1])
    merged: list[list[float]] = []
    for a, b in sorted(texty):
        if merged and a - merged[-1][1] < 0.3:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    scrims = [{"kind": "scrim", "t0": a, "t1": b, "fade_in": 0.35, "fade_out": 0.4} for a, b in merged]
    end = starts[-1]
    items.append({"kind": "end", "t0": end, "t1": total + 10, "fade_out": 0.01, "beat": 0.6, "delay": 0.2,
                  **end_card(site, site.trailer or Trailer())})
    n = int(round(total * fps))
    tl = {"fps": fps, "frames": n, "items": scrims + items}
    tdir = work / ("type_" + _digest({"tl": tl, "theme": theme}))
    if not (tdir / "index.json").exists():
        log(f"  animatic: setting {len(items) - 1} caption(s) in the site's type")
        render_type(tl, theme, "16x9", tdir, log=lambda m: None)
    index = json.loads((tdir / "index.json").read_text())
    cache: dict = {}

    def overlay(i: int):
        name = index[i] if i < len(index) else None
        if not name:
            return None
        if name not in cache:
            if len(cache) > 6:
                cache.pop(next(iter(cache)))
            cache[name] = cv2.imread(str(tdir / name), cv2.IMREAD_UNCHANGED)
        return cache[name]

    timeline = [{"id": c.id, "t0": round(starts[a], 3), "t1": round(starts[b] + pieces[b].seconds, 3)} for c, a, b in spans]
    key = {"p": [p.key() for p in pieces], "type": tdir.name, "size": [W, H], "v": 1}
    stamp = work / "animatic.json"
    if out.exists() and stamp.exists() and json.loads(stamp.read_text()).get("key") == _digest(key) and \
            json.loads(stamp.read_text()).get("out") == str(out):
        log("  animatic: up to date")
        write_timeline(project, out, total, timeline)
        return out
    log(f"  animatic: {len(pieces) - 1} shot(s), {total:.1f}s")
    render(pieces, out, (W, H), fps=fps, fade=FADE, gop=None, crf=20, moves=True, overlay=overlay, log=log,
           progress=progress)
    stamp.write_text(json.dumps({"key": _digest(key), "out": str(out)}))
    write_timeline(project, out, total, timeline)
    return out
