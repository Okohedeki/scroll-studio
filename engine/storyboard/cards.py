"""The storyboard's cards: one per shot of the page (a beat, a take, a film, a product still, an image a block shows),
each with the frames it opens (and ends) on.

Frames come from the very stages and caches the full build uses: a beat's still is `resolve_image` of the same image
input `beats_film` animates (same digest in .build/_generated), a take's keyframes are the `keyframes` stage over the
`blockout` stage (film.world), product stills are `product_still` (at low samples while previewing, which is its own
cache entry). So an approved frame is the real first frame, and the full build only adds motion. What only the
storyboard makes (a take's sketch frames, its low-sample product overlay, motion previews, placeholders) lives in
.build/_storyboard/, where no full build looks.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..config import settings
from ..fidelity import PRESETS, WouldRender, planning, previewing
from ..inputs import image_key, resolve_image
from ..layout import window
from ..plan import IMAGES, Plan, image_refs, section_locked
from ..project import BuildContext, BuildError, Project, file_key
from ..spec import FilmScene, ImageInput, Site, is_scene
from .motion import Move, Piece, from_camera, from_text

PREVIEW_SIZE = (512, 288)      # --motion: the tiny LTX preview per shot
PREVIEW_SECONDS = 2.0
PREVIEW_TIMEOUT = 12 * 60     # a preview stuck in a busy ComfyUI is dropped (the shot keeps its still move)


@dataclass
class Frame:
    path: Path
    label: str
    level: str                   # final | stills | sketch | placeholder
    t: float = 0.0               # seconds into the shot


@dataclass
class Card:
    id: str
    section: str
    kind: str                    # beat | take | shot | video | sequence | showroom | diorama | image | art
    title: str
    frames: list[Frame] = field(default_factory=list)
    prompt: str = ""
    motion: str = ""
    caption: str = ""
    seconds: float = 0.0         # length of the shot in the film (0 for a still)
    scroll: float = 0.0          # screen heights of scroll it spans
    locked: bool = False
    fingerprint: str = ""
    status: str = ""             # new | changed | unchanged | locked | rendered
    rendered: bool = False
    estimate: float = 0.0        # seconds to render it fully on this machine
    stages: list[str] = field(default_factory=list)
    pieces: list[Piece] = field(default_factory=list)
    preview: Optional[Path] = None   # --motion clip
    note: str = ""
    seconds_taken: float = 0.0
    redrawn: bool = False
    captions: list = field(default_factory=list)   # (from, to) as 0-1 of the shot, title (HTML), kicker: the animatic's type
    approval: str = ""           # approved | changed | no | "" (the project has not used approvals: `studio storyboard --edit`)

    @property
    def level(self) -> str:
        order = ["placeholder", "sketch", "stills", "final"]
        levels = [f.level for f in self.frames] or ["placeholder"]
        return min(levels, key=order.index)

    def public(self) -> dict:
        return {"id": self.id, "section": self.section, "kind": self.kind, "title": self.title,
                "frames": [{"path": str(f.path), "label": f.label, "level": f.level, "t": round(f.t, 2)} for f in self.frames],
                "prompt": self.prompt, "motion": self.motion, "caption": self.caption, "seconds": round(self.seconds, 2),
                "scroll": round(self.scroll, 2), "level": self.level, "status": self.status, "locked": self.locked,
                "estimate_seconds": round(self.estimate), "stages": self.stages, "fingerprint": self.fingerprint,
                "preview": str(self.preview) if self.preview else None, "note": self.note,
                "redrawn": self.redrawn, "seconds_taken": round(self.seconds_taken, 1), "approval": self.approval}


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:14]


def plain(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def step_captions(steps, beat: Optional[str] = None) -> list:
    """The captions over a shot as (from, to, title, kicker), 0-1 of the shot: steps pinned to `beat` (their `part`, or
    an even share), or a section's steps (their `at`, or an even share)."""
    if beat is not None:
        steps = [st for st in steps if (st.state or {}).get("beat") == beat]
    steps = [st for st in steps if st.title]
    out = []
    for i, st in enumerate(steps):
        part = (st.state or {}).get("part") if beat is not None else window(st)
        a, b = (float(part[0]), float(part[1])) if part else (i / len(steps), (i + 1) / len(steps))
        out.append((a, b, st.title, st.kicker or ""))
    return out


def span_captions(steps, s0: float, s1: float) -> list:
    """Captions over one beat from the section's own steps that are not pinned to a beat: a step laid over the film by
    `at` (0-1 of the section; or an even share when it has neither `at` nor a beat), clipped to the beat's span
    [s0, s1] of the section and given as (from, to, title, kicker) in 0-1 of the beat."""
    free = [st for st in steps if st.title and not (st.state or {}).get("beat")]
    out, n = [], len(free)
    for i, st in enumerate(free):
        w = window(st)
        a, b = (float(w[0]), float(w[1])) if w else (i / n, (i + 1) / n)
        lo, hi = max(a, s0), min(b, s1)
        if hi - lo > 1e-6 and s1 > s0:
            out.append(((lo - s0) / (s1 - s0), (hi - s0) / (s1 - s0), st.title, st.kicker or ""))
    return out


def describe(ref) -> str:
    """A short text for an image input: its prompt, its edit, its product view, or its file."""
    if ref is None:
        return ""
    if isinstance(ref, str):
        return ref
    if ref.generate:
        return ref.generate
    if ref.edit:                      # this shot's own step first; the chain's base after it, short
        base, src = "", ref.edit.source
        while not isinstance(src, str) and src.edit and not src.generate and not src.file and src.product is None:
            src = src.edit.source
        base = describe(src)
        rg = ref.edit.region
        where = ""
        if rg is not None:
            what = rg.prompt or ("box" if rg.box else "points")
            where = f" [{'outside' if rg.invert else 'only in'}: {what}]"
        return f"edit{where}: {ref.edit.instruction}" + (f"  (from: {base[:70]}{'...' if len(base) > 70 else ''})" if base else "")
    if ref.product is not None:
        view = ref.product if isinstance(ref.product, str) else ref.product.view
        scene = ref.scene or (getattr(ref.product, "scene", None) if not isinstance(ref.product, str) else None)
        return f"product still, {view}" + (f", in: {scene}" if scene else "")
    if ref.gradient:
        return "gradient " + " > ".join(ref.gradient.colors)
    return ref.file or ""


class Maker:
    """Builds the cards of one storyboard run."""

    def __init__(self, project: Project, site: Site, plan: Plan, level: str, prev: dict, only: Optional[set],
                 motion: bool, log: Callable[[str], None], generate: bool = True):
        # generate=False: nothing is rendered for the cards (no ComfyUI, no Blender): what is cached is shown, what is
        # not becomes a placeholder card. The edit workspace's "Rebuild animatic" cuts from what exists this way.
        self.nogen = not generate
        self.project, self.site, self.plan, self.level = project, site, plan, level
        self.prev, self.only, self.motion, self.log = prev, only, motion, log
        self.cache = project.build / "_storyboard"
        self.quiet = lambda m: None

    # ------------------------------------------------------------ helpers
    def selected(self, card_id: str, section: str) -> bool:
        return self.only is None or card_id in self.only or section in self.only

    def reuse(self, card: Card) -> bool:
        """Keep the frames of the last storyboard (a locked card, or one outside --only)."""
        old = (self.prev.get("cards") or {}).get(card.id)
        if not old:
            return False
        frames = [Frame(Path(f["path"]), f["label"], f["level"], f.get("t", 0.0)) for f in old.get("frames", [])]
        if not frames or not all(f.path.exists() for f in frames):
            return False
        card.frames = frames
        card.note = card.note or ("locked: kept" if card.locked else "not in --only: kept")
        return True

    def image(self, ref, alpha: bool = False, cache_only: bool = False) -> tuple[Path, str]:
        """(path, level) of an image input: the full build's own file when it exists, else the preview's."""
        try:
            with planning():
                return resolve_image(self.project, ref, self.quiet, alpha=alpha), "final"
        except WouldRender:
            pass
        if self.nogen:
            from ..fidelity import placeholder
            size = tuple(ref.size) if not isinstance(ref, str) else (1280, 720)
            return placeholder(self.cache / "placeholders", describe(ref), size), "placeholder"
        lvl = "sketch" if cache_only or self.level == "sketch" else "stills"
        try:
            with previewing(lvl):
                p = resolve_image(self.project, ref, self.log, alpha=alpha)
        except (BuildError, SystemExit, OSError) as e:   # ComfyUI down or failing: a card now, the still next run
            if lvl == "sketch":
                raise
            self.log(f"  could not render a still ({str(e).splitlines()[0][:120]}); a placeholder stands in")
            lvl = "sketch"
            with previewing(lvl):
                p = resolve_image(self.project, ref, self.log, alpha=alpha)
        return p, ("placeholder" if "placeholder" in p.name else lvl)

    def would(self, refs: list, alpha: bool = True) -> tuple[float, list[str]]:
        """Seconds the full build needs to render these image inputs, and what."""
        secs, what = 0.0, []
        for r in refs:
            try:
                with planning():
                    resolve_image(self.project, r, self.quiet, alpha=alpha)
            except WouldRender as e:
                secs += IMAGES.get(e.kind, 10.0)
                what.append(e.kind)
            except Exception:
                pass
        return secs, what

    def grab(self, video: Path, t: float, tag: str) -> Path:
        """One frame of a video (cached by the video's content and the time)."""
        out = self.cache / "grabs" / f"{tag}_{_digest([file_key(video), round(t, 3)])}.jpg"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            args = ["-sseof", "-0.08"] if t < 0 else ["-ss", f"{t:.3f}"]
            subprocess.run([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", *args, "-i", str(video),
                            "-frames:v", "1", "-q:v", "3", "-update", "1", str(out)], check=False)
            if not out.exists():
                raise BuildError(f"storyboard: could not read a frame of {video}")
        return out

    def estimate_section(self, card: Card, stage_filter: Callable[[str], bool] = lambda n: True) -> None:
        st = [s for s in self.plan.stale(card.section) if stage_filter(s.name)]
        card.stages = [s.name for s in st] + [r.kind for r in self.plan.renders_for(card.section)]
        card.estimate = sum(s.estimate for s in st) + sum(r.estimate for r in self.plan.renders_for(card.section))

    # ------------------------------------------------------------ all cards, page order
    def cards(self) -> list[Card]:
        out: list[Card] = []
        for sec in self.site.sections:
            t0 = time.time()
            made: list[Card] = []
            try:
                if is_scene(sec):
                    fn = getattr(self, f"scene_{sec.type}", None)
                    if fn is not None:
                        made = fn(sec)
                if not is_scene(sec) or sec.type in ("type", "chart", "code", "map", "scene3d", "splat", "diorama"):
                    made += self.block(sec)
            except Exception as e:   # one broken shot never stops the storyboard: it shows as a card with the error
                sid = getattr(sec, "id", None) or sec.type
                msg = f"{type(e).__name__}: {e}"
                self.log(f"  {sid}: failed, {msg.splitlines()[0][:200]}")
                made = [Card(sid, sid, sec.type, sid, note=f"failed: {msg}"[:400])]
            dt = (time.time() - t0) / max(1, len(made))
            for c in made:
                c.seconds_taken = c.seconds_taken or dt
            out += made
        if self.site.theme.art:
            out.append(self.art())
        return out

    # ------------------------------------------------------------ film: beats
    def scene_film(self, sec: FilmScene) -> list[Card]:
        if sec.video:
            cards = [self.film_video(sec)]
        elif sec.beats:
            cards = self.film_beats(sec)
        else:
            cards = [self.film_take(sec)]
        if sec.reveal:      # reveal: every frame drawn as the page shows it (base look, masked colour): storyboard/reveal.py
            from . import reveal
            reveal.apply(self, sec, cards)
        return cards

    def film_beats(self, sec: FilmScene) -> list[Card]:
        W, H = sec.beat_res[0] // 32 * 32, sec.beat_res[1] // 32 * 32
        total = sum(b.seconds - b.trim for b in sec.beats) or 1.0
        cards = []
        done = 0.0
        for b in sec.beats:
            t0 = time.time()
            s0, s1 = done / total, (done + b.seconds - b.trim) / total
            done += b.seconds - b.trim
            spans = span_captions(sec.steps, s0, s1)
            caption = " / ".join([plain(st.title) for st in sec.steps if (st.state or {}).get("beat") == b.id] +
                                 [plain(t) for _, _, t, _ in spans])
            if b.freeze is not None:      # a frozen moment: its source frame and camera path (cards_freeze below)
                c = self.freeze_card(sec, b, caption, spans, sec.length * (b.seconds - b.trim) / total, cards)
                c.seconds_taken = time.time() - t0
                cards.append(c)
                continue
            from ..camera_beats import start_ref
            ref = start_ref(sec, sec.beats.index(b), (W, H))
            fp = _digest({"prompt": b.prompt, "motion": b.motion, "seconds": b.seconds, "seed": b.seed, "trim": b.trim,
                          "strength": b.strength, "res": [W, H], "image": image_key(b.image) if b.image else None,
                          "end": image_key(b.end_image) if b.end_image else None, "model": b.video_model,
                          "motion_seed": b.motion_seed,
                          **({"camera": b.camera.model_dump(mode="json")} if b.camera is not None else {}),
                          **({"subject": sec.subject.model_dump(mode="json")} if sec.subject is not None and not b.image else {})})
            c = Card(b.id, sec.id, "beat", f"{sec.id} / {b.id}", prompt=describe(ref) if b.image else b.prompt,
                     motion=b.motion, caption=caption, seconds=b.seconds - b.trim,
                     scroll=sec.length * (b.seconds - b.trim) / total, locked=b.locked or sec.locked, fingerprint=fp,
                     captions=sorted(step_captions(sec.steps, b.id) + spans))
            name = f"beat_{b.id}"
            state = self.plan.stage_state(sec.id, name)
            clip = self.project.build / sec.id / "beats" / b.id / "clip.mp4"
            c.rendered = state in ("fresh", "migrated", "locked") and clip.exists()
            st = [s for s in self.plan.stale(sec.id) if s.name == name]
            c.stages, c.estimate = [s.name for s in st], sum(s.estimate for s in st)
            if c.rendered:
                c.frames = [Frame(self.grab(clip, 0.0, f"{b.id}_a"), "start (rendered)", "final", 0.0),
                            Frame(self.grab(clip, -1, f"{b.id}_z"), "end (rendered)", "final", c.seconds)]
                c.pieces = [Piece(c.seconds, video=clip, label=b.id)]
            else:
                keep = (c.locked or not self.selected(b.id, sec.id)) and self.reuse(c)
                if not keep:
                    cache_only = not self.selected(b.id, sec.id)
                    p, lvl = self.image(ref, cache_only=cache_only)
                    c.frames = [Frame(p, "start", lvl, 0.0)]
                    if b.end_image:
                        q, lvl2 = self.image(b.end_image, cache_only=cache_only)
                        c.frames.append(Frame(q, "end", lvl2, c.seconds))
                start = c.frames[0].path
                end = c.frames[1].path if len(c.frames) > 1 else None
                c.pieces = [Piece(c.seconds, start, end, from_text(b.motion), label=b.id)]
                if self.motion and self.selected(b.id, sec.id) and c.frames[0].level != "placeholder":
                    c.preview = self.preview(sec.id, b.id, start, b.prompt, b.motion, b.seed, end)
                    c.pieces[0].video = c.preview
            c.seconds_taken = time.time() - t0
            cards.append(c)
        return cards

    # ------------------------------------------------------------ film: frozen moment
    def freeze_card(self, sec: FilmScene, b, caption: str, spans: list, scroll: float, earlier: list[Card]) -> Card:
        """A frozen-moment beat: the frame it freezes and the camera's boxes. Rendered: frames of the clip at each key.
        Not rendered: flat crops of the source at each key (the boxes the camera will visit), from the full build's own
        image when it is cached, else the storyboard still; the clip itself is a flat preview of the camera path."""
        from PIL import Image
        from .. import freeze_beats as fbm
        from ..freeze import CameraPath
        f = b.freeze
        W, H = fbm.beat_size(sec)
        secs = b.seconds - b.trim
        path = CameraPath(f.camera, f.ease)
        src_text = f"the last frame of beat '{f.from_}'" if f.from_ else describe(f.image)
        fp = _digest({"freeze": f.model_dump(mode="json", by_alias=True, exclude={"image"}), "seconds": b.seconds,
                      "trim": b.trim, "res": [W, H], "image": image_key(f.image) if f.image is not None else None})
        boxes = "; ".join(f"{k.t:g}: {', '.join(f'{v:g}' for v in k.box)}" + (f" (hold {k.hold:g})" if k.hold else "")
                          for k in f.camera) or "the whole frame"
        c = Card(b.id, sec.id, "freeze", f"{sec.id} / {b.id}", prompt=f"frozen moment: {src_text}"
                 + (f", upscaled x{f.upscale:g}" if f.upscale > 1 else ""),
                 motion=f"camera {boxes}; parallax {f.parallax:g}, {f.ease}", caption=caption, seconds=secs, scroll=scroll,
                 locked=b.locked or sec.locked, fingerprint=fp, captions=sorted(step_captions(sec.steps, b.id) + spans))
        name = f"beat_{b.id}"
        state = self.plan.stage_state(sec.id, name)
        clip = self.project.build / sec.id / "beats" / b.id / "clip.mp4"
        c.rendered = state in ("fresh", "migrated", "locked") and clip.exists()
        st = [s for s in self.plan.stale(sec.id) if s.name == name]
        c.stages, c.estimate = [s.name for s in st], sum(s.estimate for s in st)
        times = sorted({0.0, 1.0} | {k.t for k in f.camera} | {min(1.0, k.t + k.hold) for k in f.camera if k.hold})
        total = secs + b.trim
        if c.rendered:
            c.frames = [Frame(self.grab(clip, max(0.0, min(t * total - b.trim, secs - 0.05)) if t < 1 else -1, f"{b.id}_{t:.2f}"),
                              f"t={t:g} (rendered)", "final", t * secs) for t in times]
            c.pieces = [Piece(secs, video=clip, label=b.id)]
            return c
        # the frame being frozen: an earlier card's last frame, a cached render of the source, or the storyboard still
        src, level = None, "stills"
        if f.from_:
            prior = next((x for x in earlier if x.id == f.from_ and x.frames), None)
            if prior is not None:
                src, level = prior.frames[-1].path, prior.frames[-1].level
            else:
                try:
                    src = fbm.standin_image(self.project, sec, b, self.quiet, "last")
                    level = "sketch"
                except (BuildError, OSError):
                    pass
        else:
            src, level = self.image(f.image, cache_only=not self.selected(b.id, sec.id))
        if src is None:
            c.frames = []
            c.note = "the frame to freeze is not available yet"
            return c
        out = self.cache / "freeze"
        out.mkdir(parents=True, exist_ok=True)
        im = fbm._fit(Image.open(src), (W, H))
        c.frames = []
        for t in times:
            p = out / f"{b.id}_{_digest([file_key(src), t, [k.box for k in f.camera], f.ease, W, H])}.jpg"
            if not p.exists():
                fbm.crop_view(im, path.at(t), (640, round(640 * H / W))).save(p, quality=88)
            c.frames.append(Frame(p, f"t={t:g}", level, t * secs))
        try:      # the clip as a flat camera move over the frame (no depth, no parallax), kept in the storyboard folder
            pv = out / f"{b.id}_{_digest([file_key(src), [k.box for k in f.camera], f.ease, secs, b.trim])}.mp4"
            if not pv.exists():
                fbm.flat_clip(src, b, pv, (640, round(640 * H / W) // 2 * 2))
            c.pieces = [Piece(secs, video=pv, label=b.id)]
        except Exception as e:    # no torch/ffmpeg here: the animatic then holds the first frame
            self.log(f"  {b.id}: no flat preview ({str(e).splitlines()[0][:100]})")
            c.pieces = [Piece(secs, c.frames[0].path, None, from_text(""), label=b.id)]
        return c

    # ------------------------------------------------------------ film: take / shot
    def film_take(self, sec: FilmScene) -> Card:
        from ..scenes import film
        from ..trailer.plan import film_source
        take = sec.take
        t0 = time.time()
        shotspec = take.model_dump(mode="json", exclude={"locked"}) if take else dict(sec.shot)
        kf = (shotspec.get("keyframes") or {}).get("frames", [])
        dur, fps = float(shotspec.get("duration") or 10), int(shotspec.get("fps") or 24)
        segs = (shotspec.get("ltx") or {}).get("segments") or []
        prompt = " | ".join(f"{k['name']} @{k['t']}{'' if k['t'] == 'end' else 's'}: {k['prompt']}" for k in kf) \
            or (segs[0].get("prompt", "") if segs else "")
        motion = " | ".join(f"{s.get('id')} {s['range'][0]:g}-{s['range'][1]:g}s: {s.get('prompt', '')}" for s in segs)
        caption = " / ".join(plain(st.title) for st in sec.steps)
        fpd = {"take": shotspec, "product": self.site.product.model_dump(mode="json") if (take and take.product and
                                                                                       self.site.product) else None}
        c = Card(sec.id, sec.id, "take" if take else "shot", f"{sec.id} (one take)" if take else sec.id, prompt=prompt,
                 motion=motion, caption=caption, seconds=dur, scroll=sec.length, locked=section_locked(sec),
                 fingerprint=_digest(fpd), captions=step_captions(sec.steps))
        self.estimate_section(c)
        src = film_source(self.project, sec)
        c.rendered = self.plan.section_fresh(sec.id) and src is not None
        times = sorted({0.0, dur} | {dur if k["t"] == "end" else float(k["t"]) for k in kf})
        if c.rendered:
            c.frames = [Frame(self.grab(src, min(t, dur - 0.05) if t < dur else -1, f"{sec.id}_{t:g}"),
                              f"{t:g}s (rendered)", "final", t) for t in times]
            c.pieces = [Piece(dur, video=src, label=sec.id)]
            c.seconds_taken = time.time() - t0
            return c
        keys = [k.model_dump(mode="json") for k in take.camera] if take else None
        if not ((c.locked or not self.selected(c.id, sec.id)) and self.reuse(c)):
            ctx = BuildContext(self.project, sec.id, log=self.log, locked=c.locked,
                               options={"site_video_model": self.site.video_model})
            sketch = self.level == "sketch" or not self.selected(c.id, sec.id) or self.nogen
            if sketch:
                shot, bkey, legacy = film.blockout_key(sec, ctx)
                bdir = ctx.work / "blockout"
                world_ok = ctx.status("blockout", bkey, [bdir / "depth.mp4", bdir / "first.png"], legacy) != "stale"
            else:
                try:
                    shot, bkey, legacy = film.world(sec, ctx)   # the full build's own blockout + keyframes stages
                    world_ok = True
                except (BuildError, SystemExit, RuntimeError, OSError) as e:   # e.g. ComfyUI down: sketch instead
                    self.log(f"  {sec.id}: keyframes not painted ({str(e).splitlines()[0][:120]}); sketching instead")
                    sketch = True
                    shot, bkey, legacy = film.blockout_key(sec, ctx)
                    bdir = ctx.work / "blockout"
                    world_ok = ctx.status("blockout", bkey, [bdir / "depth.mp4", bdir / "first.png"], legacy) != "stale"
            kpaths = {}
            if kf:
                outs = [ctx.work / "keyframes" / f"{k['name']}.png" for k in kf]
                kstate = ctx.status("keyframes", {"b": bkey, "k": shot["keyframes"]}, outs,
                                    legacy and {"b": legacy, "k": shot["keyframes"]})
                if kstate != "stale" or not sketch:
                    kpaths = {(dur if k["t"] == "end" else float(k["t"])): (k["name"], o) for k, o in zip(kf, outs) if o.exists()}
            n = int(round(dur * fps))
            frames = []
            if world_ok:
                at = lambda t: ctx.work / "blockout" / "frames" / f"{min(n, 1 + int(round(t * fps))):04d}.png"
            elif self.nogen:
                from ..fidelity import placeholder
                at = lambda t: placeholder(self.cache / "placeholders", f"{sec.id} at {t:g}s: {prompt}", (1280, 720),
                                           "blockout not rendered yet")
            else:
                try:
                    at = self.world_stills(sec, ctx, times)
                except BuildError as e:
                    self.log(f"  {sec.id}: {e}")
                    from ..fidelity import placeholder
                    at = lambda t: placeholder(self.cache / "placeholders", f"{sec.id} at {t:g}s: {prompt}", (1280, 720),
                                               "blockout not rendered yet")
            for t in times:
                if t in kpaths:
                    frames.append(Frame(kpaths[t][1], f"keyframe {kpaths[t][0]} @{t:g}s", "stills", t))
                else:
                    p = at(t)
                    frames.append(Frame(p, f"blockout @{t:g}s", "placeholder" if "placeholder" in p.name else "sketch", t))
            if take and take.product and not self.nogen:
                frames = self.with_product(sec, ctx, frames, n, fps)
            c.frames = frames
        if keys:
            c.pieces = [Piece(b.t - a.t, a.path, None, from_camera(keys, a.t, b.t), label=f"{sec.id} {a.t:g}s")
                        for a, b in zip(c.frames, c.frames[1:]) if b.t > a.t]
        else:
            c.pieces = [Piece(b.t - a.t, a.path, None, Move(1.0, 1.08), label=sec.id)
                        for a, b in zip(c.frames, c.frames[1:]) if b.t > a.t]
        if self.motion and self.selected(c.id, sec.id) and c.frames:
            seg = segs[0] if segs else {}
            c.preview = self.preview(sec.id, "take", c.frames[0].path, seg.get("prompt", prompt), seg.get("prompt", ""),
                                     int((shotspec.get("ltx") or {}).get("seed", 7)))
            if c.pieces:
                c.pieces[0].video = c.preview
        c.seconds_taken = time.time() - t0
        return c

    def world_stills(self, sec: FilmScene, ctx: BuildContext, times: list[float]) -> Callable[[float], Path]:
        """A few frames of a take's world (its sketch) when the blockout is not rendered yet: take.py's own world pass
        told to render only these moments (backends/blender_scripts/take_stills.py)."""
        import os
        from ..scenes import film_build as fb
        t = json.loads((ctx.work / "take.json").read_text(encoding="utf-8")) if sec.take else None
        res = list(sec.take.preview_res) if sec.take else list(sec.shot.get("preview_res", [1280, 720]))
        key = {"world": {k: v for k, v in (t or sec.shot).items() if k not in ("ltx", "keyframes", "upscale", "restore",
                                                                                   "video_model", "wan", "product_file")},
               "times": times, "res": res, "script": file_key(Path(fb.SCRIPTS) / "take.py")}
        d = self.cache / sec.id / f"world_{_digest(key)}"
        name = lambda x: d / "stills" / f"t{x:05.2f}.png"
        if not all(name(x).exists() for x in times):
            if not sec.take:
                raise BuildError(f"storyboard: '{sec.id}' has no blockout yet; build it with `studio storyboard "
                                 f"--level stills`")
            self.log(f"  {sec.id}: sketching the world at {', '.join(f'{x:g}s' for x in times)}")
            env = dict(os.environ, SS_STILLS=",".join(f"{x:.3f}" for x in times))
            cmd = [settings()["blender"], "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                   str(Path(fb.SCRIPTS) / "take_stills.py"), "--", "--take", str(ctx.work / "take.json"), "--pass", "world",
                   "--out", str(d), "--res", f"{res[0]}x{res[1]}"]
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            if p.returncode != 0 or not all(name(x).exists() for x in times):
                raise BuildError("storyboard: sketching the world failed:\n" + (p.stderr or p.stdout)[-1500:])
        return name

    def with_product(self, sec: FilmScene, ctx: BuildContext, frames: list[Frame], n: int, fps: int) -> list[Frame]:
        """The take's real product over its frames: take.py's product pass, only at these frames and at a few samples
        (studio light until the plate exists), composited without the plate grade."""
        from PIL import Image
        from ..scenes import film, film_build as fb
        samples = PRESETS[self.level].samples if self.level in PRESETS else 8
        if self.level == "sketch":
            samples = PRESETS["sketch"].samples
        idx = sorted({min(n, 1 + int(round(f.t * fps))) for f in frames})
        res = list(sec.take.preview_res)
        key = {"p": film._product_keys(ctx), "f": idx, "s": samples, "r": res}
        d = self.cache / sec.id / f"product_{_digest(key)}"
        if not all((d / "frames" / f"{i:04d}.png").exists() for i in idx):
            self.log(f"  {sec.id}: product pass at {len(idx)} frame(s), {samples} samples")
            cmd = [settings()["blender"], "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                   str(Path(fb.SCRIPTS) / "take.py"), "--", "--take", str(ctx.work / "take.json"), "--pass", "product",
                   "--out", str(d), "--res", f"{res[0]}x{res[1]}", "--samples", str(samples), "--only", *[str(i) for i in idx]]
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if p.returncode != 0:
                raise BuildError("storyboard: the product pass failed:\n" + (p.stderr or p.stdout)[-1500:])
        out = []
        for f in frames:
            layer = d / "frames" / f"{min(n, 1 + int(round(f.t * fps))):04d}.png"
            if not layer.exists():
                out.append(f)
                continue
            comp = self.cache / sec.id / "comp" / f"{_digest([file_key(f.path), file_key(layer)])}.jpg"
            if not comp.exists():
                comp.parent.mkdir(parents=True, exist_ok=True)
                base = Image.open(f.path).convert("RGBA")
                over = Image.open(layer).convert("RGBA").resize(base.size, Image.LANCZOS)
                base.alpha_composite(over)
                base.convert("RGB").save(comp, quality=90)
            out.append(Frame(comp, f.label + " + product", f.level, f.t))
        return out

    def film_video(self, sec: FilmScene) -> Card:
        from ..project import probe
        src = self.project.path(sec.video)
        dur = float(probe(src).get("duration") or 1) if src.exists() else 1.0
        c = Card(sec.id, sec.id, "video", sec.id, prompt=f"film: {sec.video}", seconds=dur, scroll=sec.length,
                 caption=" / ".join(plain(st.title) for st in sec.steps), locked=sec.locked,
                 fingerprint=_digest({"video": file_key(src) if src.exists() else sec.video}), rendered=src.exists(),
                 captions=step_captions(sec.steps))
        self.estimate_section(c)
        if src.exists():
            c.frames = [Frame(self.grab(src, t, f"{sec.id}_{i}"), lab, "final", max(t, 0) if t >= 0 else dur)
                        for i, (t, lab) in enumerate([(0.0, "start"), (dur / 2, "middle"), (-1, "end")])]
            c.pieces = [Piece(dur, video=src, label=sec.id)]
        return c

    # ------------------------------------------------------------ other scenes
    def scene_sequence(self, sec) -> list[Card]:
        from .. import product as prod
        from ..spec import Product
        c = Card(sec.id, sec.id, "sequence", f"{sec.id} (product turn)", prompt=f"{sec.frames} frames: " + ", ".join(
            f"yaw {k.get('yaw', 0)} pitch {k.get('pitch', 0)}" + (f" explode {k['explode']}" if k.get("explode") else "")
            for k in sec.keys), caption=" / ".join(plain(st.title) for st in sec.steps), scroll=sec.length,
            locked=sec.locked, fingerprint=_digest(sec.model_dump(mode="json", include={"model", "frames", "size",
                                                                                    "samples", "keys", "hdri"})))
        self.estimate_section(c)
        c.rendered = self.plan.section_fresh(sec.id)
        d = self.project.build / sec.id / "render" / "frames"
        if c.rendered and d.exists():
            picks = [1, max(1, sec.frames // 2), sec.frames]
            c.frames = [Frame(d / f"{i:04d}.png", f"frame {i}", "final", 0) for i in picks if (d / f"{i:04d}.png").exists()]
        elif self.nogen:
            self.reuse(c)
        elif not ((c.locked or not self.selected(c.id, sec.id)) and self.reuse(c)):
            p = None if sec.model in (None, "product") else Product(name=sec.id, model=sec.model)
            lvl = "sketch" if self.level == "sketch" or not self.selected(c.id, sec.id) else "stills"
            with previewing(lvl):
                for k in sorted(sec.keys, key=lambda k: k.get("t", 0))[:3]:
                    path = prod.product_still(self.project, p, "three-quarter", (960, 540), "transparent", self.log,
                                              yaw=k.get("yaw"), pitch=k.get("pitch"), zoom=k.get("zoom"),
                                              explode=k.get("explode") or None, samples=sec.samples, hdri=sec.hdri)
                    c.frames.append(Frame(path, f"t={k.get('t', 0)}", lvl, 0))
        c.pieces = [Piece(2.0, f.path, None, Move(1.0, 1.05)) for f in c.frames]
        c.captions = step_captions(sec.steps)
        return [c]

    def scene_inside(self, sec) -> list[Card]:
        """The product as the set: the opening wide shot and a still of every stop (Cycles, low samples), each a held piece
        with the stop's copy over it."""
        from ..fidelity import previewing
        from ..scenes import inside as ins
        c = Card(sec.id, sec.id, "sequence", f"{sec.id} (inside the product)",
                 prompt="the camera flies into the product, one stop per part: "
                        + ", ".join(st.part or "a point" for st in (sec.stops or [])) if sec.stops else "the camera flies into the product, stops chosen from its parts",
                 caption=" / ".join(plain(st.title) for st in sec.steps), scroll=sec.length or 0.0, locked=sec.locked,
                 fingerprint=_digest({"inside": sec.model_dump(mode="json", exclude={"steps", "hud", "transition", "backdrop"}),
                                      "product": self.site.product.model_dump(mode="json") if self.site.product else None}))
        self.estimate_section(c)
        c.rendered = self.plan.section_fresh(sec.id)
        if self.nogen:
            self.reuse(c)
        elif not ((c.locked or not self.selected(c.id, sec.id)) and self.reuse(c)):
            lvl = "sketch" if self.level == "sketch" or not self.selected(c.id, sec.id) else "stills"
            with previewing(lvl):
                info, glb, res, plan = ins.route(sec, self.project, self.log)
                picks = ([0] if sec.establish else []) + [w["frame"] for w in plan.windows]
                labels = (["wide"] if sec.establish else []) + [s.label for s in res.stops]
                if not sec.length:
                    sec.length = round(max(3.0, plan.screens), 2)
                paths = ins.preview(self.project, sec, picks, 8 if lvl == "sketch" else 24, 0.5, self.log)
            c.frames = [Frame(p, lab, lvl, 0) for p, lab in zip(paths, labels)]
        c.pieces = [Piece(2.0, f.path, None, Move(1.0, 1.05)) for f in c.frames]
        c.captions = step_captions(sec.steps)
        return [c]

    def scene_showroom(self, sec) -> list[Card]:
        from .. import product as prod
        k0 = sorted(sec.keys, key=lambda k: k.get("t", 0))[0] if sec.keys else {}
        c = Card(sec.id, sec.id, "showroom", f"{sec.id} (live 3D)", prompt="the product live in the page (three.js)",
                 caption=" / ".join(plain(st.title) for st in sec.steps), scroll=sec.length, locked=sec.locked,
                 fingerprint=_digest(sec.model_dump(mode="json", include={"model", "keys", "lighting", "background"})))
        self.estimate_section(c)
        if self.nogen:
            self.reuse(c)
        elif not ((c.locked or not self.selected(c.id, sec.id)) and self.reuse(c)):
            lvl = "sketch" if self.level == "sketch" else "stills"
            with previewing(lvl):
                path = prod.product_still(self.project, None, "three-quarter", (960, 600), "transparent", self.log,
                                          yaw=k0.get("yaw", -35), pitch=k0.get("pitch", 18), explode=k0.get("explode") or None)
            c.frames = [Frame(path, "first key", lvl, 0)]
        c.rendered = self.plan.section_fresh(sec.id)
        c.pieces = [Piece(3.0, c.frames[0].path, None, Move(1.0, 1.06))] if c.frames else []
        c.captions = step_captions(sec.steps)
        return [c]

    def _images_card(self, sec, kind: str, refs: list[tuple[str, object, bool]], title: str, caption: str) -> Card:
        """One card for the images a section shows (a block's photo or product still, strip items, a backdrop)."""
        card_id = getattr(sec, "id", None) or f"{sec.type}-{self.site.sections.index(sec) + 1}"
        fp = _digest({"refs": [image_key(r) for _, r, _ in refs],
                      "product": self.site.product.model_dump(mode="json") if self.site.product else None})
        c = Card(card_id, card_id, kind, title, prompt=" | ".join(f"{lab}: {describe(r)}" for lab, r, _ in refs),
                 caption=caption, locked=bool(getattr(sec, "locked", False)), fingerprint=fp)
        c.estimate, c.stages = self.would([r for _, r, _ in refs])
        c.rendered = not c.stages
        if not ((c.locked or not self.selected(c.id, c.section)) and self.reuse(c)):
            for lab, r, alpha in refs:
                p, lvl = self.image(r, alpha=alpha, cache_only=not self.selected(c.id, c.section))
                c.frames.append(Frame(p, lab, lvl, 0))
        c.pieces = [Piece(3.0, f.path, None, Move(1.0, 1.06)) for f in c.frames]
        steps = getattr(sec, "steps", None)
        c.captions = step_captions(steps) if steps else ([(0.0, 1.0, getattr(sec, "title", None) or "",
                                                           getattr(sec, "kicker", None) or "")]
                                                         if getattr(sec, "title", None) else [])
        return c

    def scene_diorama(self, sec) -> list[Card]:
        """A miniature world: its flat map (the same picture the page shows before WebGL is up), laid out on the CPU in a
        couple of seconds, with the places numbered. The live scene itself is drawn in the browser, so nothing renders."""
        from .. import diorama as dio
        from ..compile import themes
        from ..scenes.diorama import _map_image, stage_key
        table = sec.look.table or themes.resolve(self.site.theme)["colors"]["bg"]
        key = _digest(stage_key(sec, table, True))
        path = self.cache / sec.id / f"diorama_{key}.jpg"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            plan, tex, _ = dio.build(sec, table, True)
            _map_image(plan, tex, table).save(path, quality=86)
        c = Card(sec.id, sec.id, "diorama", f"{sec.id} (miniature world, live in the page)",
                 prompt=f"a {sec.world.kind} diorama with {len(sec.places)} places: " + ", ".join(p.name for p in sec.places),
                 caption=" / ".join(plain(st.title) for st in sec.steps), scroll=sec.length, locked=sec.locked, fingerprint=key)
        c.frames = [Frame(path, "map", "final", 0)]
        c.pieces = [Piece(3.0, path, None, Move(1.0, 1.04))]
        c.captions = step_captions(sec.steps)
        c.rendered = True
        return [c]

    def scene_artwork(self, sec) -> list[Card]:
        return [self._images_card(sec, "image", [("image", sec.image, False)], f"{sec.id} (artwork)",
                                  " / ".join(plain(st.title) for st in sec.steps))]

    def scene_vector(self, sec) -> list[Card]:
        if not sec.image:
            return []
        return [self._images_card(sec, "image", [("image", sec.image, False)], f"{sec.id} (vector)",
                                  " / ".join(plain(st.title) for st in sec.steps))]

    def scene_parallax(self, sec) -> list[Card]:
        refs = [(f"photo {i + 1}", st.image, False) for i, st in enumerate(sec.steps) if st.image is not None]
        return [self._images_card(sec, "image", refs, f"{sec.id} (parallax)",
                                  " / ".join(plain(st.title) for st in sec.steps))] if refs else []

    def scene_light(self, sec) -> list[Card]:
        """The world: the one picture every time of day is a relighting of (a `scene:<id>` world is another card's)."""
        if isinstance(sec.world, str) and sec.world.startswith("scene:"):
            return []
        return [self._images_card(sec, "image", [("world", sec.world, False)],
                                  f"{sec.id} (light: {', '.join(t.id for t in sec.times)})",
                                  " / ".join(plain(st.title) for st in sec.steps))]

    def block(self, sec) -> list[Card]:
        refs = image_refs(sec)
        if not refs:
            return []
        title = plain(getattr(sec, "title", None) or getattr(sec, "kicker", None) or sec.type)
        kind = "product" if any(not isinstance(r, str) and getattr(r, "product", None) is not None for _, r, _ in refs) \
            else "image"
        return [self._images_card(sec, kind, refs, f"{getattr(sec, 'id', None) or sec.type} ({sec.type})", title)]

    def art(self) -> Card:
        art = self.site.theme.art
        ref = art.file or ImageInput(generate=art.prompt, size=art.size, seed=art.seed)
        c = Card("theme-art", "theme.art", "art", "theme.art", prompt=describe(ref), motion=art.motion or "",
                 seconds=art.seconds if art.motion else 0, fingerprint=_digest(art.model_dump(mode="json")))
        c.estimate, c.stages = self.would([ref])
        if art.motion:
            from .. import art as art_mod
            if not art_mod.cached(self.project, art, self.site.video_model, self.site.wan.model_dump(mode="json")):
                c.estimate += IMAGES["art"]
                c.stages.append("art")
        c.rendered = not c.stages
        if not (not self.selected(c.id, c.section) and self.reuse(c)):
            p, lvl = self.image(ref, cache_only=not self.selected(c.id, c.section))
            c.frames = [Frame(p, "still", lvl, 0)]
        c.pieces = [Piece(3.0, c.frames[0].path, None, from_text(art.motion))] if c.frames else []
        return c

    # ------------------------------------------------------------ --motion: a tiny LTX preview
    def preview(self, section: str, name: str, still: Path, prompt: str, motion: str, seed: int,
                end: Optional[Path] = None) -> Optional[Path]:
        """A 512x288, two-second LTX-2.3 clip of the shot (cached), to check the motion before the full render."""
        from ..animate import animate
        from ..project import ffmpeg
        key = {"still": file_key(still), "end": file_key(end) if end else None, "prompt": prompt, "motion": motion,
               "seed": seed, "size": PREVIEW_SIZE, "s": PREVIEW_SECONDS}
        d = self.cache / section / f"motion_{name}_{_digest(key)}"
        clip = d / "preview.mp4"
        if clip.exists():
            return clip
        d.mkdir(parents=True, exist_ok=True)
        try:
            frames = animate(still, prompt, motion, PREVIEW_SECONDS, seed, d, self.log, size=PREVIEW_SIZE, end_image=end,
                             timeout=PREVIEW_TIMEOUT)
        except (BuildError, SystemExit) as e:
            self.log(f"  {name}: no motion preview ({e})")
            return None
        seq = d / "seq"
        seq.mkdir(exist_ok=True)
        for i, f in enumerate(frames):
            shutil.copy(f, seq / f"{i:04d}.png")
        ffmpeg("-framerate", "24", "-i", seq / "%04d.png", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", clip)
        shutil.rmtree(seq, ignore_errors=True)
        return clip
