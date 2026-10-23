"""The storyboard's view of `reveal`: a film that brings colour in by scroll must not be judged in full colour.

Every frame of a film section with `reveal:` is drawn the way the page will show it at that moment of the film: the base
look everywhere (black and white, dimmed, blurred or tinted), and, when the masks exist (a full build made them: they sit in
.build/<section>/reveal/), colour inside each region's mask at the film frame that moment falls on, by the amount the section's
keys give at that fraction of the scroll. Without masks the frames show the base look only and the card says so: "reveal: ...
masks come with the full build". The stand-in film and the animatic are cut from these frames, so they show it too, and the page
built from them plays without the shader (the reveal is already in the frames).

Frames from a clip that is already rendered are treated alike (a still of it, not the clip: the real page plays the clip with the
shader once the section is built).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

from ..project import Project, file_key
from ..reveal import amounts_at, composite, region_keys


def mask_files(project: Project, sec_id: str, rv) -> Optional[dict]:
    """{region id: [masks .npz files]} when the section's masks are all on disk, else None."""
    out = {}
    for r in rv.regions:
        n = len(r.seeds)
        names = [f"masks_{k}.npz" if n > 1 else "masks.npz" for k in range(n)]
        files = [project.build / sec_id / "reveal" / r.id / x for x in names]
        if not all(f.exists() for f in files):
            return None
        out[r.id] = files
    return out


_LOADED: dict = {}


def _frame_mask(files: list[Path], fi: int) -> np.ndarray:
    m = None
    for f in files:
        key = str(f)
        if key not in _LOADED or _LOADED[key][0] != f.stat().st_mtime:
            if len(_LOADED) >= 8:
                _LOADED.pop(next(iter(_LOADED)))
            _LOADED[key] = (f.stat().st_mtime, np.load(f)["masks"])
        a = _LOADED[key][1]
        x = a[min(fi, len(a) - 1)]
        m = x if m is None else np.maximum(m, x)
    return m


def reveal_still(project: Project, sec, rv, src: Path, fraction: float, cache: Path) -> Path:
    """One still as the page shows the film at `fraction` (0-1) of the section: base look + masked colour."""
    from PIL import Image, ImageOps
    files = mask_files(project, sec.id, rv)
    ids = [r.id for r in rv.regions]
    amounts = amounts_at(region_keys(rv), ids, fraction, rv.ease)
    key = {"src": file_key(src), "base": rv.base, "strength": rv.strength, "f": round(fraction, 3), "a": amounts,
           "m": {k: [file_key(f) for f in v] for k, v in (files or {}).items()}, "v": 1}
    import hashlib
    out = cache / f"reveal_{hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:14]}.jpg"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    im = ImageOps.fit(Image.open(src).convert("RGB"), (1280, 720), Image.LANCZOS)     # the page crops the film to 16:9 too
    masks = {}
    if files:
        n = None
        for rid, fs in files.items():
            if n is None:
                n = len(np.load(fs[0])["masks"])
            fi = int(round(fraction * (n - 1)))
            m = _frame_mask(fs, fi)
            masks[rid] = np.asarray(Image.fromarray(m).resize((1280, 720), Image.BILINEAR)).astype(np.float32) / 255
    comp = composite(np.asarray(im), masks, amounts, rv.base, rv.strength)
    Image.fromarray(comp).save(out, quality=92)
    return out


def apply(mk, sec, cards: list) -> None:
    """Replace the frames of this section's cards (and the pieces the animatic and stand-in are cut from) with their reveal
    state, and say so on each card. `mk` is the cards.Maker."""
    from .cards import _digest
    rv = sec.reveal
    if rv is None:
        return
    have = mask_files(mk.project, sec.id, rv) is not None
    note = f"reveal: {', '.join(r.id for r in rv.regions)} over {rv.base}" + ("" if have else " (masks come with the full build: base look only)")
    total = (sum(b.seconds - b.trim for b in sec.beats) or 1.0) if sec.beats else 0.0
    done = 0.0
    cache = mk.cache / "reveal"
    for c in cards:
        if c.section != sec.id:
            continue
        if sec.beats and c.kind == "beat":
            b = next((x for x in sec.beats if x.id == c.id), None)
            span = (done / total, (done + (b.seconds - b.trim)) / total) if b else (0.0, 1.0)
            done += (b.seconds - b.trim) if b else 0.0
        else:
            span = (0.0, 1.0)
        for j, f in enumerate(c.frames):
            # a beat's start and end frames sit at the ends of its span; other cards' frames at their time in the film
            fr = (span[0] if j == 0 else span[1]) if (sec.beats and c.kind == "beat") else (min(1.0, f.t / c.seconds) if c.seconds else 0.0)
            new = reveal_still(mk.project, sec, rv, f.path, fr, cache)
            for p in c.pieces:
                if p.start == f.path:
                    p.start = new
                if p.end == f.path:
                    p.end = new
            f.path, f.label = new, f.label + " · reveal"
        for p in c.pieces:       # a clip that is already rendered: its frames drawn the same way
            if p.video is not None and p.video.exists():
                p.video = reveal_clip(mk.project, sec, rv, p.video, span, cache)
        c.note = (c.note + " · " if c.note else "") + note
        c.fingerprint = _digest([c.fingerprint, rv.model_dump(mode="json")])


def reveal_clip(project: Project, sec, rv, clip: Path, span: tuple[float, float], cache: Path) -> Path:
    """A rendered clip (colour) as the page shows it: the base look with each region's masked colour, frame by frame,
    over `span` (0-1) of the section. 1280x720, for the animatic."""
    import hashlib
    from PIL import Image
    from ..config import settings
    files = mask_files(project, sec.id, rv)
    ids = [r.id for r in rv.regions]
    keys = region_keys(rv)
    key = {"clip": file_key(clip), "span": [round(x, 4) for x in span], "base": rv.base, "strength": rv.strength, "keys": keys,
           "m": {k: [file_key(f) for f in v] for k, v in (files or {}).items()}, "v": 1}
    out = cache / f"reveal_clip_{hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:14]}.mp4"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    W, H = 1280, 720
    ff = settings()["ffmpeg"]
    rd = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", "-i", str(clip), "-vf",
                           f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    wr = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
                           "24", "-i", "-", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    frames = [rd.stdout.read(W * H * 3)]
    while len(frames[-1]) == W * H * 3:
        frames.append(rd.stdout.read(W * H * 3))
    frames.pop()
    n = len(frames)
    mn = None
    for i, raw in enumerate(frames):
        fr = span[0] + (span[1] - span[0]) * (i / max(n - 1, 1))
        masks = {}
        if files:
            for rid, fs in files.items():
                if mn is None:
                    mn = len(np.load(fs[0])["masks"])
                m = _frame_mask(fs, int(round(fr * (mn - 1))))
                masks[rid] = np.asarray(Image.fromarray(m).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
        comp = composite(np.frombuffer(raw, np.uint8).reshape(H, W, 3), masks, amounts_at(keys, ids, fr, rv.ease), rv.base, rv.strength)
        wr.stdin.write(comp.tobytes())
    wr.stdin.close()
    wr.wait()
    rd.wait()
    return out
