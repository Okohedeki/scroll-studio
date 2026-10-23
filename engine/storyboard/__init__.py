"""Storyboard: prototype a site before the full render (`studio storyboard <project>`, MCP tool `storyboard`).

Levels:
  sketch    no ComfyUI: a take's grey world from Blender at a few moments, cached stills, placeholder cards for
            images not generated yet (prompt on a card), product stills at a few samples.
  stills    (default) the real opening (and end) frame of every shot: take keyframes over the blockout (the full
            build's own `blockout` and `keyframes` stages), beat stills and end images (the same image inputs the
            beats animate), image inputs, product and in-scene stills at low samples. About 10-30 s a shot.
  animatic  the stills with a slow camera move per shot (along a take's camera path, or a beat's motion verb) and
            timed cuts, plus animatic.mp4 (a rough cut with the page's captions, the trailer's type and end card).
            --motion adds a tiny LTX-2.3 preview per shot (512x288, 2 s) to check motion before the full render.

Outputs in <project>/storyboard/: site/ (the real page with storyboard frames standing in for unrendered films,
marked with a corner badge), storyboard.html and sheet.jpg (a card per shot: frames, prompt, motion, caption, length,
fidelity, status new/changed/unchanged/locked/rendered, and the full render estimate on this machine), animatic.mp4,
storyboard.json (what the next run compares against).

Everything it renders goes through the stages and caches the full build uses (see cards.py), so approving a frame
means the full build starts from it. Re-running after an edit redoes only the shots whose inputs changed.
"""
from __future__ import annotations

import time
from typing import Callable, Iterable, Optional

from ..fidelity import LEVELS, previewing
from ..plan import fmt, plan_build
from ..project import BuildError, Project
from ..spec import is_scene
from . import record
from .cards import Maker

STAND_IN = ("film", "sequence", "inside")                       # scenes that render heavily: shown by their frames until rendered
STAND_IN_SKETCH = ("artwork", "parallax", "vector")   # image scenes: at sketch their images may not exist yet


def storyboard(project: Project, level: str = "stills", only: Optional[Iterable[str]] = None, motion: bool = False,
               site_too: bool = True, log: Callable[[str], None] = print,
               progress: Callable[[float, str], None] = lambda f, m="": None, generate: bool = True) -> dict:
    """generate=False cuts everything from what is already rendered (cached stills, rendered clips) and renders nothing
    new: no ComfyUI, no Blender; an image not drawn yet is a placeholder card."""
    from ..compile.compiler import build_site
    from . import animatic, sheet, standin
    if level not in LEVELS:
        raise BuildError(f"storyboard level {level!r}: use {', '.join(LEVELS)}")
    t0 = time.time()
    site = project.load()
    out = project.root / "storyboard"
    out.mkdir(parents=True, exist_ok=True)
    prev = record.load(project)
    only_set = {x.strip() for x in only if x and x.strip()} if only else None
    log(f"storyboard {project.name}: {level}" + (f", only {', '.join(sorted(only_set))}" if only_set else ""))
    plan = plan_build(project)            # what the full build would still render: statuses and estimates
    progress(0.05, "frames")
    mk = Maker(project, site, plan, level, prev, only_set, motion and level == "animatic" and generate, log, generate)
    cards = mk.cards()
    if only_set:
        known = {c.id for c in cards} | {c.section for c in cards}
        missing = only_set - known
        if missing:
            log(f"  note: --only {', '.join(sorted(missing))} matched no shot")
    old = prev.get("cards") or {}
    for c in cards:
        if c.locked:
            c.status = "locked"
        elif c.rendered:
            c.status = "rendered"
        elif c.id not in old:
            c.status = "new"
        elif old[c.id].get("fingerprint") != c.fingerprint:
            c.status = "changed"
        else:
            c.status = "unchanged"
        c.redrawn = old.get(c.id, {}).get("frame_keys") != record.frame_keys(c)
        made = "made" if c.id not in old else "redrawn"
        log(f"  {c.id}: {c.status}, {c.level}" + (f", frames {made} in {c.seconds_taken:.1f}s" if c.redrawn else
                                                  ", frames unchanged") + (f" ({c.note})" if c.note else ""))
    progress(0.6, "page")
    site_index = None
    if site_too:
        standins = {}
        for sec in site.sections:
            if not is_scene(sec):
                continue
            mine = [c for c in cards if c.section == sec.id]
            if (sec.type in STAND_IN and not plan.section_fresh(sec.id)) or (level == "sketch" and sec.type in STAND_IN_SKETCH):
                si = standin.section(project, sec, mine, level, log)
                if si:
                    standins[sec.id] = si
        with previewing(level if generate else "sketch"):
            site_index = build_site(project, log=lambda m: None, out=out / "site", options={"draft": True},
                                    standin=lambda s: standins.get(s.id), badge=f"Storyboard · {level}")
        log(f"  page: {site_index}" + (f" ({len(standins)} scene(s) standing in)" if standins else ""))
    anim = None
    if level == "animatic":
        progress(0.75, "animatic")
        anim = animatic.build(project, site, cards, out / "animatic.mp4", log, lambda f, m="": progress(0.75 + 0.15 * f, m))
    progress(0.9, "sheet")
    from .edit import approvals
    appr = approvals.summary(project)       # None until the project has used approvals in the edit workspace
    if appr:
        for c in cards:
            c.approval = appr["status"].get(c.id, "no")
    files = sheet.thumbs(cards, out)
    shots = [c for c in cards]
    changed = [c.id for c in cards if c.status in ("new", "changed")]
    finishing = sum(s.estimate for s in plan.stale() if not any(s.name in c.stages for c in cards if c.section == s.section))
    total = plan.total()
    heavy = sorted({s.kind.split(":")[1] for s in plan.heavy()})
    head = {"title": f"Storyboard: {site.name} ({level})",
            "line": f"{len(shots)} shots · {len(changed)} new or changed · "
                    f"{sum(c.status == 'rendered' for c in cards)} rendered · {sum(c.locked for c in cards)} locked · "
                    + (f"{appr['approved']} of {appr['total']} approved · " if appr else "")
                    + f"full render on this machine ~{fmt(total)}" + (f" (heavy: {', '.join(heavy)})" if heavy else ""),
            "line2": f"made in {time.time() - t0:.0f}s · {time.strftime('%Y-%m-%d %H:%M')} · frames: FINAL rendered, "
                     f"STILLS real first frames, SKETCH blockout/low samples, PLACEHOLDER not generated yet"
                     + (f" · not approved: {', '.join(appr['pending'][:10])}" + (" ..." if len(appr['pending']) > 10 else "")
                        if appr and appr["pending"] else "")
                     + (f" · joins/restores/encodes ~{fmt(finishing)}" if finishing else "")}
    links = {"page": "site/index.html" if site_index else "", "animatic": "animatic.mp4" if anim else "",
             "sheet": "sheet.jpg"}
    for c in cards:
        if c.preview:
            dst = out / "previews" / f"{c.id}.mp4"
            dst.parent.mkdir(exist_ok=True)
            import shutil
            shutil.copy(c.preview, dst)
            links["preview_" + c.id] = f"previews/{c.id}.mp4"
    jpg = sheet.sheet_jpg(cards, files, out, head)
    html = sheet.sheet_html(cards, files, out, head, links)
    summary = {"level": level, "seconds": round(time.time() - t0, 1), "shots": len(cards), "changed": changed,
               "redrawn": [c.id for c in cards if c.redrawn], "render_estimate_seconds": round(total),
               "render_estimate": fmt(total), "plan": plan.summary()}
    record.save(project, level, cards, summary)
    progress(1.0, "done")
    log(f"storyboard: {len(cards)} shots in {time.time() - t0:.1f}s; full render ~{fmt(total)}")
    log(f"  sheet: {jpg}")
    return {"sheet": str(jpg), "html": str(html), "site": str(site_index) if site_index else None,
            "animatic": str(anim) if anim else None, **summary, "cards": [c.public() for c in cards]}
