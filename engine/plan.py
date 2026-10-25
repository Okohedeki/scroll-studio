"""Build plans: what `studio build` would render, and about how long that takes on this machine.

`plan_build(project)` runs every scene builder in a dry run (engine/fidelity.py `planning()`, `BuildContext` with
options["plan"]): no stage runs and nothing is generated, but each stage reports whether it is up to date, and each
image, product still or model conversion that would render says so. A stage that would run marks its outputs dirty, so
a later stage keyed on them (a join, a restore, an encode) counts as re-running too.

Estimates are seconds per unit of work for each kind of stage (frames, seconds of film, keyframes, beats...),
calibrated from the `seconds` every stage stamp records on this machine (all projects and examples), with defaults
measured on an RTX 4090 for kinds that never ran here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Callable, Iterable, Optional

from .project import BuildContext, Project, file_key
from .spec import Site, is_scene

# seconds per unit (see units()) when this machine has no stamps of that kind yet; RTX 4090 figures
DEFAULTS = {
    "film:blockout": 0.25,      # per frame (Workbench + depth)
    "film:keyframes": 90.0,     # per keyframe (Z-Image + depth ControlNet, model load included)
    "film:generate": 80.0,      # per second of film at 1024x576 (scaled by area)
    "film:generate_wan": 120.0,  # per second of film
    "film:restore": 80.0,       # per second of film (SeedVR2 / LTX upscale)
    "film:track": 5.0,
    "film:plate_env": 1.0,      # per second of film
    "film:product": 7.0,        # per frame at 64 samples, 1920x1080
    "film:composite": 1.3,      # per frame
    "film:encode": 1.2,         # per second of film
    "film:beat": 100.0,         # per second of a beat (still + edit + animation)
    "film:camera": 90.0,        # per second of a beat with a camera move (depth + people mask + guide, then the video model along it)
    "film:freeze": 1.5,         # per second of a frozen moment (depth + camera render, no upscale)
    "film:freeze_up": 10.0,     # per second of a frozen moment that upscales its frame (SeedVR2: ~2 min, then seconds)
    "film:freeze_zoom": 150.0,  # per tile of a deep zoom (SeedVR2 enlarge + Z-Image redraw + the agreement, model loads included)
    "film:freeze_layers": 150.0,  # per frozen moment with layered depth (Florence-2, SAM 2.1 per subject, Qwen background fill)
    "film:join": 0.5,           # per second of film
    "film:reveal_work": 0.8,    # per second of film (reveal: the working-size copy)
    "film:reveal_ground": 25.0,  # per region (Florence-2 on one frame, model load included)
    "film:reveal_track": 0.35,  # per frame of film per region (SAM 2.1, forward and backward)
    "film:reveal_pack": 0.12,   # per frame of film (feathered masks into videos, poster)
    "film:faces": 0.25,         # per frame of film (GFPGAN over every face)
    "film:world_depth": 0.22,   # per frame of film (type in the world: Depth Anything V2, steadied over time, snapped to edges)
    "film:world_text": 3.0,     # per in-world title (planar tracking through its shot; a prompt adds Florence-2 + SAM 2.1)
    "film:world_pack": 0.1,     # per frame of film (depth and surface masks into the atlas video)
    "sequence:render": 0.13,    # per frame at 96 samples, 1920x1080
    "sequence:encode": 1.0,     # per frame
    "inside:render": 0.55,      # per frame at 64 samples, 1600x900 (macro Cycles with a shared GPU)
    "inside:encode": 0.5,       # per frame (grade, desktop and phone WebP)
    "light:align": 2.0,         # a time that is the world itself or a picture the spec gives (measured and aligned only)
    "light:relight": 120.0,     # per time of day (Qwen-Image-Edit, measured and aligned; a drifting one is redone)
}
FLAT = 10.0                     # any other stage, per run
IMAGES = {"beat frame": 3.0, "image": 15.0, "edit": 60.0, "product still": 25.0, "scene still": 150.0, "product model": 60.0,
          "download": 5.0, "art": 240.0, "stand-in": 5.0,
          "medium": 3.0}                # a named medium's post-process (engine/medium.py), on the CPU
# what counts as heavy GPU work (a video model, SeedVR2, a Cycles pass over every frame): the build lists these first
HEAVY = ("film:generate", "film:generate_wan", "film:restore", "film:product", "film:beat", "film:camera", "film:keyframes",
         "film:freeze_up", "film:freeze_zoom", "film:freeze_layers", "sequence:render", "inside:render", "film:reveal_track", "film:faces", "light:relight")


@dataclass
class Stage:
    section: str
    name: str
    state: str                       # fresh | migrated | locked | stale
    prior: Optional[float] = None    # seconds it took last time (stamp)
    kind: str = ""
    units: float = 1.0
    estimate: float = 0.0
    inferred: bool = False           # not reached in the dry run (it follows a stage that would run)


@dataclass
class Render:
    section: str
    kind: str                        # image | edit | product still | scene still | product model | download | art
    what: str
    estimate: float = 0.0


@dataclass
class Plan:
    project: Project
    site: Site
    stages: list[Stage] = field(default_factory=list)
    renders: list[Render] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    dirty: list[dict] = field(default_factory=list)

    # ------------------------------------------------ fed by BuildContext.stage
    def record(self, section: str, name: str, state: str, prior: Optional[float], outputs: list[Path]) -> None:
        self.stages.append(Stage(section, name, state, prior))
        if state == "stale":
            for o in outputs:
                if o.exists():
                    self.dirty.append(file_key(o))

    def depends_on_dirty(self, key) -> bool:
        if not self.dirty:
            return False
        def walk(v) -> bool:
            if isinstance(v, dict):
                return v in self.dirty or any(walk(x) for x in v.values())
            if isinstance(v, (list, tuple)):
                return any(walk(x) for x in v)
            return False
        return walk(key)

    # ------------------------------------------------ queries
    def stale(self, section: Optional[str] = None) -> list[Stage]:
        return [s for s in self.stages if s.state == "stale" and (section is None or s.section == section)]

    def renders_for(self, section: Optional[str] = None) -> list[Render]:
        return [r for r in self.renders if section is None or r.section == section]

    def section_fresh(self, section: str) -> bool:
        """Every stage of the section is up to date (or locked) and nothing in it would render."""
        seen = [s for s in self.stages if s.section == section]
        return bool(seen) and not self.stale(section) and not self.renders_for(section) and section not in self.errors

    def stage_state(self, section: str, name: str) -> Optional[str]:
        return next((s.state for s in self.stages if s.section == section and s.name == name), None)

    def total(self, section: Optional[str] = None) -> float:
        return sum(s.estimate for s in self.stale(section)) + sum(r.estimate for r in self.renders_for(section))

    def heavy(self) -> list[Stage]:
        return [s for s in self.stale() if s.kind in HEAVY]

    def lines(self) -> list[str]:
        """What will render, one line each, longest first within a section, then the total."""
        out = []
        for sec in dict.fromkeys([s.section for s in self.stale()] + [r.section for r in self.renders]):
            for s in self.stale(sec):
                out.append(f"  {sec}/{s.name}: ~{fmt(s.estimate)}" + (" (follows a re-render)" if s.inferred else ""))
            for r in self.renders_for(sec):
                out.append(f"  {sec}: {r.kind} {r.what[:70]}: ~{fmt(r.estimate)}")
        for sec, err in self.errors.items():
            out.append(f"  {sec}: could not plan ({err.splitlines()[0][:120]})")
        return out

    def summary(self) -> dict:
        return {"total_seconds": round(self.total()), "total": fmt(self.total()),
                "stages": [{"section": s.section, "stage": s.name, "estimate_seconds": round(s.estimate),
                            "heavy": s.kind in HEAVY} for s in self.stale()],
                "renders": [{"section": r.section, "kind": r.kind, "what": r.what, "estimate_seconds": round(r.estimate)}
                            for r in self.renders],
                "locked": [f"{s.section}/{s.name}" for s in self.stages if s.state == "locked"],
                "errors": self.errors}


def fmt(seconds: float) -> str:
    s = int(round(seconds))
    if s < 90:
        return f"{s}s"
    m = round(s / 60)
    return f"{m} min" if m < 90 else f"{m // 60}h{m % 60:02d}"


# ---------------------------------------------------------------- what a stage costs

def _film_dims(sec) -> tuple[float, int]:
    if sec.take:
        return float(sec.take.duration), int(sec.take.fps)
    if sec.beats:
        return float(sum(b.seconds - b.trim for b in sec.beats)), 24
    return float(sec.shot.get("duration") or 10), int(sec.shot.get("fps") or 24)


def units(sec, name: str) -> tuple[str, float]:
    """(kind, units of work) of stage `name` of a scene section."""
    t = sec.type
    if t == "film":
        dur, fps = _film_dims(sec)
        frames = dur * fps
        if name.startswith("beat_") and name != "beats_join":
            b = next((b for b in sec.beats if f"beat_{b.id}" == name), None)
            if b is not None and b.freeze is not None:     # a frozen moment: offline, seconds (minutes with an upscale)
                f = b.freeze
                if f.detail is not None:                    # deep zoom: one stage per tile of the camera's pyramid
                    from .backends.upscale import target_size
                    from .freeze_beats import beat_size
                    from .zoom_build import make_plan
                    size = beat_size(sec)
                    return "film:freeze_zoom", float(max(1, len(make_plan(f, b.seconds, target_size(size, max(1.0, f.upscale))[0], size)[0])))
                if f.layers is not None:
                    return "film:freeze_layers", 1.0
                return ("film:freeze_up" if f.upscale > 1 else "film:freeze"), float(b.seconds)
            if b is not None and b.camera is not None:     # a camera move: the guide, then the video model along it
                return "film:camera", float(b.seconds)
            return "film:beat", float(b.seconds if b else 4.0)
        if name == "blockout":
            return "film:blockout", frames
        if name == "keyframes":
            kf = (sec.take.keyframes if sec.take else sec.shot.get("keyframes")) or {}
            return "film:keyframes", float(max(1, len(kf.get("frames", []))))
        if name == "generate":
            ltx = (sec.take.ltx if sec.take else sec.shot.get("ltx")) or {}
            w, h = ltx.get("res") or (1024, 576)
            return "film:generate", dur * (w * h) / (1024 * 576)
        if name == "generate_wan":
            return "film:generate_wan", dur
        if name.startswith("upscale") or name in ("restore", "beats_restore"):
            return "film:restore", dur
        if name == "beats_join":
            return "film:join", dur
        if name == "plate_env":
            return "film:plate_env", dur
        if name == "product" and sec.take and sec.take.product:
            p = sec.take.product
            w, h = p.res or ((2560, 1440) if sec.take.upscale else (1920, 1080))
            return "film:product", frames * (p.samples / 64) * (w * h) / (1920 * 1080)
        if name == "composite":
            return "film:composite", frames
        if name == "encode":
            return "film:encode", dur
        if name == "reveal_cuts":
            return "film:reveal_work", dur
        if name == "reveal_work":
            return "film:reveal_work", dur
        if name.startswith("reveal_ground_"):
            return "film:reveal_ground", 1.0
        if name.startswith("reveal_track_"):
            return "film:reveal_track", frames
        if name == "reveal_pack":
            return "film:reveal_pack", frames
        if name == "world_depth":
            return "film:world_depth", frames
        if name.startswith("world_text_"):
            return "film:world_text", 1.0
        if name == "world_pack":
            return "film:world_pack", frames
        if name.startswith("restore_"):
            b = next((b for b in sec.beats if f"restore_{b.id}" == name), None)
            return "film:restore", float(b.seconds - b.trim) if b else dur
        if name.startswith("faces_"):
            b = next((b for b in sec.beats if f"faces_{b.id}" == name), None)
            return "film:faces", float((b.seconds - b.trim) * 24 if b else frames)
        if name == "faces":
            return "film:faces", frames
        if name == "track":
            return "film:track", 1.0
    if t == "inside":
        w, h = sec.size
        stops = sec.stops or [None] * max(1, len([x for x in sec.steps if not x.intro]) or 5)
        screens = sec.length or (sum((st.hold + st.travel) if st else 2.2 for st in stops) + (2.0 if sec.establish else 0) + (1.9 if sec.outro == "wide" else 0))
        frames = max(8.0, screens * sec.density)
        if name == "render":
            return "inside:render", frames * (sec.samples / 64) * (w * h) / (1600 * 900)
        if name == "encode":
            return "inside:encode", frames
    if t == "sequence":
        w, h = sec.size
        if name == "render":
            return "sequence:render", sec.frames * (sec.samples / 96) * (w * h) / (1920 * 1080)
        if name == "encode":
            return "sequence:encode", float(sec.frames)
    if t == "light" and name.startswith("time_"):    # one relight per time of day; the world's own time and a given picture are cheap
        tm = next((x for x in sec.times if f"time_{x.id}" == name), None)
        return ("light:relight" if tm is not None and tm.image is None and tm.id != sec.world_time else "light:align"), 1.0
    return f"{t}:{re.sub(r'[0-9]+$', '', name)}", 1.0


def expected(sec, beats: Optional[set] = None) -> list[str]:
    """The stages a scene section runs, in order (films only; other builders report what they reach)."""
    if sec.type == "light":     # engine/scenes/light.py: the world, its depth and sky, one relight per time, the maps, the web files
        return (["world", "depth", "sky"] + [f"time_{t.id}" for t in sec.times if t.id != sec.world_time]
                + (["time_" + sec.world_time] if sec.world_time else []) + ["maps", "web"])
    if sec.type != "film" or sec.video:
        return ((["faces"] if sec.faces else []) + ["encode"] + expected_reveal(sec) + expected_world(sec)) if sec.type == "film" else []
    if sec.beats:
        names = [n for b in sec.beats if beats is None or b.id in beats
                 for n in [f"beat_{b.id}"] + ([f"restore_{b.id}"] if b.restore else []) + ([f"faces_{b.id}"] if b.faces else [])] + ["beats_join"]
        return names + (["beats_restore"] if sec.beat_restore else []) + (["faces"] if sec.faces else []) + ["encode"] + expected_reveal(sec) + expected_world(sec)
    from .animate import video_model
    shot = sec.take.model_dump(mode="json") if sec.take else sec.shot
    model = video_model(shot.get("video_model"))
    names = ["blockout"] + (["keyframes"] if (shot.get("keyframes") or {}).get("frames") else [])
    names.append("generate_wan" if model == "wan" else "generate")
    up = shot.get("upscale") or {}
    if up.get("method") in ("ltx", "seedvr2"):
        names.append("upscale" + ("_wan" if model == "wan" else ""))
    if sec.take and sec.take.restore and up.get("method") != "seedvr2":
        names.append("restore")
    if sec.take and sec.take.product:
        names += ["track"] + ([] if sec.take.product.hdri else ["plate_env"]) + ["product", "composite"]
    return names + (["faces"] if sec.faces else []) + ["encode"] + expected_reveal(sec) + expected_world(sec)


def expected_reveal(sec) -> list[str]:
    """The reveal stages of a film section (engine/reveal.py), after its encode."""
    if not getattr(sec, "reveal", None):
        return []
    names = ["reveal_work"] + ([] if sec.beats or sec.reveal.cuts else ["reveal_cuts"])
    for r in sec.reveal.regions:
        for k in range(len(r.seeds)):
            sfx = f"_{k}" if len(r.seeds) > 1 else ""
            names += ([f"reveal_ground_{r.id}{sfx}"] if r.prompt and not r.box else []) + [f"reveal_track_{r.id}{sfx}"]
    return names + ["reveal_pack"]


def expected_world(sec) -> list[str]:
    """The type-in-the-world stages of a film section (engine/world.py), after its encode."""
    from . import world
    steps = world.world_steps(sec)
    if not steps or getattr(sec, "reveal", None):         # (a film with `reveal` keeps its titles as captions)
        return []
    names = ["reveal_work"] + ([] if sec.beats else ["reveal_cuts"])
    if any(w.kind != "surface" or not w.quad for _, _, w in steps):
        names.append("world_depth")
    for i, _, w in steps:
        if w.kind == "surface":
            names += [f"reveal_ground_world{i}"] if w.at and not w.quad else []
            names.append(f"reveal_track_world{i}")
        names.append(f"world_text_{i}")
    return names + ["world_pack"]


_RATES: Optional[dict] = None


def rates(refresh: bool = False) -> dict[str, float]:
    """Seconds per unit for each kind of stage, the median over every stage stamp on this machine (projects folder
    and examples), else DEFAULTS."""
    global _RATES
    if _RATES is not None and not refresh:
        return _RATES
    from .config import ROOT, settings
    samples: dict[str, list[float]] = {}
    roots = [Path(settings()["projects"]), ROOT / "examples"]
    for base in roots:
        if not base.exists():
            continue
        for spec in list(base.glob("*/site.yaml")) + list(base.glob("*/*/site.yaml")):
            build = spec.parent / ".build"
            if not build.exists():
                continue
            try:
                site = Project(spec.parent).load()
            except Exception:
                continue
            secs = {s.id: s for s in site.sections if is_scene(s)}
            for stamp in build.glob("*/stamps/*.json"):
                sec = secs.get(stamp.parent.parent.name)
                if sec is None:
                    continue
                try:
                    secs_taken = float(json.loads(stamp.read_text()).get("seconds") or 0)
                    kind, u = units(sec, stamp.stem)
                except Exception:
                    continue
                if secs_taken > 0.5 and u > 0:
                    samples.setdefault(kind, []).append(secs_taken / u)
    out = dict(DEFAULTS)
    for kind, xs in samples.items():
        out[kind] = median(xs)
    _RATES = out
    return out


def estimate(plan: Plan) -> Plan:
    r = rates()
    secs = {s.id: s for s in plan.site.sections if is_scene(s)}
    for s in plan.stages:
        sec = secs.get(s.section)
        if sec is None:
            continue
        s.kind, s.units = units(sec, s.name)
        rate = r.get(s.kind)
        s.estimate = rate * s.units if rate is not None else (s.prior or FLAT)
    for x in plan.renders:
        x.estimate = IMAGES.get(x.kind, FLAT)
    return plan


# ---------------------------------------------------------------- the dry run

def selection(site: Site, only: Optional[Iterable[str]]) -> tuple[Optional[set], dict]:
    """--only ids (sections and beats) -> (scene section ids to build, {section id: beat ids or None for all}).
    None, {} when nothing is selected (build everything)."""
    if not only:
        return None, {}
    ids = {i.strip() for i in only if i and i.strip()}
    secs, beats, known = set(), {}, set()
    for s in site.sections:
        if getattr(s, "id", None):
            known.add(s.id)
        if s.type == "film":
            known.update(b.id for b in s.beats)
        if not is_scene(s):
            continue
        if s.id in ids:
            secs.add(s.id)
            beats[s.id] = None
        elif s.type == "film" and any(b.id in ids for b in s.beats):
            secs.add(s.id)
            beats[s.id] = {b.id for b in s.beats if b.id in ids}
    unknown = ids - known
    if unknown:
        from .project import BuildError
        raise BuildError(f"--only: no section or beat with id {', '.join(sorted(unknown))}")
    return secs, beats


def section_locked(sec) -> bool:
    return bool(getattr(sec, "locked", False) or (sec.type == "film" and sec.take and sec.take.locked))


def image_refs(sec) -> list[tuple[str, object, bool]]:
    """(label, image ref, alpha) for the images a block (or any section's backdrop) shows, as the compiler resolves
    them."""
    out = []
    if getattr(sec, "backdrop", None) is not None:
        out.append(("backdrop", sec.backdrop, True))
    t = sec.type
    if t == "hero":
        if sec.image is not None:
            out.append(("image", sec.image, True))
        if sec.device and sec.device.image is not None:
            out.append(("screen", sec.device.image, True))
    elif t == "product":
        if sec.image is not None:
            out.append(("image", sec.image, True))
        if sec.device and sec.device.image is not None:
            out.append(("screen", sec.device.image, True))
        if sec.behind and sec.behind.image is not None:
            out.append(("behind", sec.behind.image, True))
    elif t == "strip":
        out += [(f"item {i + 1}", it.image, True) for i, it in enumerate(sec.items)]
    return out


def plan_build(project: Project, only: Optional[Iterable[str]] = None, force: bool = False,
               options: Optional[dict] = None, blocks: bool = True) -> Plan:
    """What `build_site(project, only=..., force=...)` would render, with estimates. Nothing is rendered."""
    from .compile import themes
    from .fidelity import WouldRender, planning
    from .inputs import resolve_image
    from .scenes import builder_for
    site = project.load()
    plan = Plan(project, site)
    theme = themes.resolve(site.theme)
    secs, beat_sel = selection(site, only)
    opts = dict(options or {}, site_video_model=site.video_model, site_wan=site.wan.model_dump(mode="json"), plan=plan)
    quiet: Callable[[str], None] = lambda m: None
    with planning():
        for sec in site.sections:
            if is_scene(sec) and (secs is None or sec.id in secs):
                ctx = BuildContext(project, sec.id, log=quiet, force=force, locked=section_locked(sec),
                                   options=dict(opts, only_beats=beat_sel.get(sec.id)))
                try:
                    builder_for(sec.type)(sec.model_copy(deep=True), ctx, theme)
                except WouldRender as e:
                    plan.renders.append(Render(sec.id, e.kind, e.what))
                    _fill(plan, sec, beat_sel.get(sec.id))
                except Exception as e:   # a stage output that a stale stage would make is missing: the rest follows
                    if plan.stale(sec.id) or plan.renders_for(sec.id):
                        _fill(plan, sec, beat_sel.get(sec.id))
                    else:
                        plan.errors[sec.id] = f"{type(e).__name__}: {e}"
            if blocks:
                for label, ref, alpha in image_refs(sec):
                    if sec.type == "hero" and label == "image":     # with its calm side, as the compiler asks for it
                        from .inputs import hero_image
                        ref = hero_image(project, sec)[0]
                    try:
                        resolve_image(project, ref, quiet, alpha=alpha)
                    except WouldRender as e:
                        plan.renders.append(Render(getattr(sec, "id", None) or sec.type, e.kind, e.what))
                    except Exception as e:
                        plan.errors[f"{getattr(sec, 'id', None) or sec.type} {label}"] = str(e)
        if blocks and site.theme.art:
            from . import art as art_mod
            try:
                if not art_mod.cached(project, site.theme.art, site.video_model, site.wan.model_dump(mode="json")):
                    plan.renders.append(Render("theme.art", "art", (site.theme.art.prompt or site.theme.art.file or "")[:60]))
            except Exception:
                pass
    return estimate(plan)


def _fill(plan: Plan, sec, beats: Optional[set]) -> None:
    """The dry run stopped inside this section (an output a re-render would make is not there yet): every expected
    stage it did not reach counts as running."""
    seen = {s.name for s in plan.stages if s.section == sec.id}
    standing = any(r.kind == "stand-in" for r in plan.renders_for(sec.id))
    for name in expected(sec, beats):
        if name == "beats_restore" and standing:   # skipped while beats stand in (film.beats_film)
            continue
        if name not in seen:
            plan.stages.append(Stage(sec.id, name, "stale", inferred=True))


def announce(project: Project, only: Optional[Iterable[str]] = None, force: bool = False,
             options: Optional[dict] = None, log: Callable[[str], None] = print) -> Plan:
    """Print what a build will render and how long that takes here, before it starts (`studio build`, MCP, UI)."""
    try:
        plan = plan_build(project, only=only, force=force, options=options)
    except Exception as e:   # the plan is advice: never stop a build because it could not be made
        log(f"plan: could not estimate ({type(e).__name__}: {e})")
        return Plan(project, project.load())
    n, m = len(plan.stale()), len(plan.renders)
    locked = [f"{s.section}/{s.name}" for s in plan.stages if s.state == "locked"]
    from .storyboard.edit import approvals
    approvals.mention(project, log)      # shots the storyboard has not approved (only once approvals are in use)
    if not n and not m:
        log("plan: nothing to render, every stage is up to date" + (f" ({len(plan.errors)} section(s) not planned)" if plan.errors else ""))
        for line in plan.lines():
            log(line)
        if locked:
            log(f"  locked (kept as rendered although their settings changed): {', '.join(locked)}")
        return plan
    heavy = plan.heavy()
    log(f"plan: {n} stage(s)" + (f" and {m} image(s)" if m else "") + f" to render, about {fmt(plan.total())} on this "
        f"machine" + (f"; heavy GPU work: {', '.join(sorted({s.section + '/' + s.name for s in heavy}))}" if heavy else ""))
    for line in plan.lines():
        log(line)
    if locked:
        log(f"  locked (kept as rendered although their settings changed): {', '.join(locked)}")
    return plan
