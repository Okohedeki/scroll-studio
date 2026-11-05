"""The whole site from a brief (issue #191): `studio new <name> --brief "..."`.

    report = generate(project_root, brief, want=("pointer", "3d"), count=8, seed=1)

An outline first, then every section written against a real pattern of its type (engine/sitegen/bank.py) and checked
by the spec's own models, then the look from `studio directions`. The result is an ordinary project.yaml, and
<project>/generate.json records the brief, the model, the seed and what each step decided, so it can be made again.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from . import bank as bank_mod, catalog, write
from .write import WriteError as WriteError

Log = Callable[[str], None]
DEFAULT_WANT = ("pointer", "3d")


def text_backend(policy=None):
    """The text backend generation would use, or a BuildError saying how to set one up."""
    from ..project import BuildError
    from ..router import NoBackend, choose
    try:
        return choose("text", policy)
    except NoBackend as e:
        raise BuildError("generating a site needs a text model. Run one locally behind an OpenAI-style endpoint (for "
                         "example Ollama) and set text_url and text_model in studio.toml, or set a provider key and "
                         f"`models: {{prefer: provider}}` (docs/generate.md). The router said: {e}") from None


def _make_room(log: Log) -> None:
    """A local text model shares the GPU with ComfyUI: release ComfyUI's VRAM first (its weights stay cached in RAM)."""
    from ..backends import comfy
    try:
        if comfy.alive():
            comfy.free()
            log("  released ComfyUI's GPU memory for the text model")
    except Exception:
        pass


def generate(root: Path, brief: str, want: tuple[str, ...] = DEFAULT_WANT, count: int = 8, seed: int = 1,
             direction: Optional[str] = "best", looks: bool = True, images: bool = False, policy=None,
             log: Log = print, only: Optional[str] = None) -> dict:
    """Write <root>/project.yaml from `brief` (or, with `only`, rewrite that one section of an existing one)."""
    from ..project import BuildError, Project
    from ..project_spec import validate
    backend = text_backend(policy)
    if backend.local:
        _make_room(log)
    root.mkdir(parents=True, exist_ok=True)
    project = Project(root)
    build = project.build
    bank = bank_mod.load()
    entries = catalog.entries(bank)
    if not write.NUMBER.search(brief):           # no figures in the brief: a stats block could only invent them
        entries = [e for e in entries if e["type"] != "stats"]
    unknown = [k for k in want if k not in catalog.INTERACTIVE]
    if unknown:
        raise BuildError(f"unknown interactive kind {', '.join(unknown)}: use {', '.join(catalog.INTERACTIVE)}")
    t0 = time.time()
    log(f"generate: {root.name} with {backend.name} ({backend.model('text')}), seed {seed}")
    record_path = root / "generate.json"

    if only:
        record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else None
        if not record or not project.is_project_file:
            raise BuildError("`--only` rewrites one section of a generated project; this one has no generate.json")
        plan = record["outline"]
        item = next((s for s in plan["sections"] if s.get("id") == only), None)
        if item is None:
            raise BuildError(f"no section {only!r} in the outline: " + ", ".join(s.get("id", "?") for s in plan["sections"]))
        sec, left = write.section(record["brief"], plan, item, bank_mod.pattern(item["type"], bank), seed + 101,
                                  policy, build, log)
        if sec is None:
            raise BuildError(f"{only}: still invalid after retries: " + "; ".join(left[:3]))
        data = project.load_project().model_dump(exclude_none=True, exclude_defaults=True)
        data.setdefault("outputs", {}).setdefault("site", {})
        secs = data["outputs"]["site"].get("sections", [])
        data["outputs"]["site"]["sections"] = [sec if s.get("id") == only else s for s in secs]
        validate(data)
        project.put_text(write.dump(data))
        log(f"generate: rewrote {only}")
        return {"only": only}

    log("  outline")
    plan = write.outline(brief, entries, want, count, seed, policy, build, log)
    log(f"  {plan.get('name')}: " + ", ".join(f"{s['id']} ({s['type']})" for s in plan["sections"]))
    sections, dropped = [], []
    for i, item in enumerate(plan["sections"]):
        pattern = bank_mod.pattern(item["type"], bank)
        log(f"  [{i + 1}/{len(plan['sections'])}] {item['id']}: {item['type']}")
        sec, left = write.section(brief, plan, item, pattern, seed + 10 * (i + 1), policy, build, log)
        if sec is None:
            dropped.append({"id": item["id"], "type": item["type"], "problems": left})
            log(f"  {item['id']}: left out ({'; '.join(left[:2])})")
            continue
        sections.append(sec)
    if not sections or sections[-1].get("type") != "cta":
        raise BuildError("generation lost the page's call to action; run it again with another --seed")
    site = write.assemble(plan, sections)
    data = {"name": site.pop("name"), "description": site.pop("description"), "brief": brief,
            "outputs": {"site": site}}
    validate(data)
    project.put_text(write.dump(data))

    # The page as a whole: references between sections, then the build planner's own checks (nothing rendered).
    items = {s["id"]: s for s in plan["sections"]}
    for round_ in range(2):
        found = write.page_problems(sections)
        for sid, msgs in write.plan_problems(project).items():
            found.setdefault(sid, []).extend(msgs)
        if not found:
            break
        if "" in found:
            raise BuildError("the generated page cannot be planned: " + "; ".join(found[""]))
        for sid, msgs in found.items():
            log(f"  {sid}: the build would fail ({'; '.join(msgs)[:160]}); writing it again")
            item = items.get(sid) or {"id": sid, "type": next(s["type"] for s in sections if s["id"] == sid)}
            sec, left = write.section(brief, plan, item, bank_mod.pattern(item["type"], bank), seed + 500 + round_,
                                      policy, build, log, known=msgs)
            if sec is not None:
                sections = [sec if s["id"] == sid else s for s in sections]
            elif item["type"] != "cta":
                sections = [s for s in sections if s["id"] != sid]
                dropped.append({"id": sid, "type": item["type"], "problems": msgs + left})
        site = write.assemble(plan, sections)
        site.pop("name"), site.pop("description")
        data["outputs"]["site"] = site
        validate(data)
        project.put_text(write.dump(data))
    else:
        left_over = {**write.page_problems(sections), **write.plan_problems(project)}
        for sid, msgs in left_over.items():
            if sid and next((s["type"] for s in sections if s["id"] == sid), "cta") != "cta":
                sections = [s for s in sections if s["id"] != sid]
                dropped.append({"id": sid, "problems": msgs})
                log(f"  {sid}: left out ({'; '.join(msgs)[:160]})")
        site = write.assemble(plan, sections)
        site.pop("name"), site.pop("description")
        data["outputs"]["site"] = site
        validate(data)
        project.put_text(write.dump(data))
    log(f"  wrote {project.spec_path.name}: {len(sections)} sections"
        + (f", left out {', '.join(d['id'] for d in dropped)}" if dropped else ""))

    kept = {s["id"] for s in sections}
    shown = {item.get("interactive") for item in plan["sections"] if item.get("id") in kept}
    missing = [k for k in want if k not in shown]

    picked = None
    if looks and direction:
        from ..directions import run as directions
        log("  look: art directions")
        state = directions.make(project, brief=brief, images=images, sheet=False, log=lambda m: log("    " + m))
        if direction == "best":                  # the direction that fits the brief best, not whichever came first
            direction = max(state["directions"], key=lambda d: d.get("fit") or 0)["id"]
        picked = directions.pick(project, direction, log=lambda m: log("    " + m))["direction"]["name"]
        log(f"  look: picked {picked}")
    record = {"brief": brief, "seed": seed, "want": list(want), "count": count, "backend": backend.name,
              "model": backend.model("text"), "outline": plan, "dropped": dropped, "interactive_missing": missing,
              "direction": picked, "seconds": round(time.time() - t0, 1)}
    record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"generate: done in {record['seconds']:.0f}s -> {project.spec_path}"
        + (f" (missing interactive: {', '.join(missing)})" if missing else ""))
    return record
