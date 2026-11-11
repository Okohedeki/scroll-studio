"""`studio concepts`: ad concepts from the product profile, in every language the project sells in.

A concept is an angle on the product (a problem it solves, a benefit, proof, a comparison, a routine, a gift...) with
a hook for the first seconds, a headline and call to action for static ads, a few on-screen lines and a short spoken
script for video ads. The first language's concepts fix the angles; each other language gets the same concepts
written natively for its market (engine/languages.py), not translated. Ads and video ads make one variation per
concept. With no text backend, plain drafts are filled from the profile so there is always something to edit.

Written to <project>/concepts/concepts.json and concepts.md."""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

from .languages import instruction
from .project import BuildError, Project

DEFAULT_ANGLES = ["benefit", "problem", "proof", "routine", "comparison", "gift", "objection", "story", "unboxing",
                  "offer"]
ANGLE_HINTS = {
    "problem": "open on the problem the buyer has, then the product as the way out",
    "benefit": "lead with the single biggest benefit, made concrete",
    "proof": "lead with proof the page gives: ratings, numbers, what buyers say",
    "comparison": "the product against the usual way of doing it (no named competitors)",
    "routine": "the product in a moment of the buyer's day",
    "gift": "the product as a gift, and who it is for",
    "unboxing": "first look: opening it, what is inside, first use",
    "story": "a short story of a buyer before and after",
    "offer": "the price or offer the page gives, and why now",
    "objection": "answer a doubt a buyer may have",
}

PROMPT = """Write {count} ad concepts for this product, one per angle below, in this order.

Product profile:
{profile}

Angles:
{angles}

Tone: {tone}
{language}
Answer with JSON only: {{"concepts": [{{"angle": "...", "hook": "...", "headline": "...", "cta": "...",
  "lines": ["...", "..."], "script": "..."}}, ...]}}
- hook: what is said or shown in the first two seconds, under 12 words
- headline: under 40 characters, for a static ad
- cta: under 20 characters
- lines: 3 to 5 on-screen lines, each under 8 words
- script: what a presenter says, about {words} words ({seconds:g} seconds), spoken and natural
{claims}"""

CLAIMS = {
    "page": "Every claim must be one the product page itself makes. Never invent numbers, ratings or specifications.",
    "profile": "Only claim what the profile supports. Never invent numbers, ratings or specifications.",
}


def folder(project: Project):
    return project.root / "concepts"


def load(project: Project) -> dict:
    try:
        return json.loads((folder(project) / "concepts.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def angles_for(asked: list[str], count: int) -> list[str]:
    base = list(dict.fromkeys(asked)) or DEFAULT_ANGLES
    return [base[i % len(base)] for i in range(count)]


def describe(project: Project, spec) -> dict:
    """The profile the concepts are written from: the imported one, else what project.yaml says."""
    from . import productpage
    got = productpage.load(project)
    if got:
        return {k: v for k, v in got.items() if k not in ("facts", "source", "draft") and v}
    what = (spec.outputs.stills.describe if spec.outputs.stills else "") or (spec.product.name if spec.product else "")
    return {"name": spec.description or spec.name, "what": what, "main_benefit": spec.brief}


def parse(text: str, count: int) -> list[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in the answer")
    items = json.loads(m.group(0)).get("concepts")
    if not isinstance(items, list) or len(items) < count:
        raise ValueError(f"asked for {count} concepts, got {len(items) if isinstance(items, list) else 0}")
    out = []
    for c in items[:count]:
        lines = [str(x).strip() for x in (c.get("lines") or []) if str(x).strip()][:5]
        got = {"hook": str(c.get("hook") or "").strip(), "headline": str(c.get("headline") or "").strip()[:60],
               "cta": str(c.get("cta") or "").strip()[:30], "lines": lines, "script": str(c.get("script") or "").strip()}
        if not (got["headline"] and got["script"]):
            raise ValueError("a concept has no headline or script")
        out.append(got)
    return out


def draft(prof: dict, angle: str) -> dict:
    """A plain concept from the profile, marked as a draft."""
    name = prof.get("name") or prof.get("what") or "This product"
    benefit = (prof.get("main_benefit") or "").rstrip(".")
    proof = (prof.get("proof") or [""])[0]
    lead = {"proof": proof or benefit, "problem": f"Tired of the usual way? {benefit}".strip(), "gift": f"A gift: {name}",
            }.get(angle, benefit or name)
    return {"hook": lead[:80], "headline": (benefit or name)[:40], "cta": "Shop now",
            "lines": [x for x in (name, benefit, proof) if x][:3],
            "script": f"{lead}. {name}. {benefit}. Have a look today.".replace("..", "."), "draft": True}


def make(project: Project, log: Callable[[str], None] = print) -> dict:
    spec = project.load_project() if project.is_project_file else None
    if spec is None or spec.outputs.concepts is None:
        raise BuildError(f"{project.name} has no outputs.concepts in project.yaml (docs/stills.md#ad-concepts)")
    cfg = spec.outputs.concepts
    prof = describe(project, spec)
    angles = angles_for(cfg.angles, cfg.count)
    from .router import NoBackend, TextJob, choose, route
    can_write = True
    try:
        choose("text", spec.models)
    except NoBackend:
        can_write = False
        log("  concepts: no text backend can run here, so the concepts are drafts from the profile")
    concepts = [{"id": f"c{i + 1}", "angle": a, "copy": {}} for i, a in enumerate(angles)]
    sources = set()
    for lang in spec.languages:
        got: Optional[list[dict]] = None
        if can_write:
            prompt = PROMPT.format(count=cfg.count, profile=json.dumps(prof, ensure_ascii=False, indent=1),
                                   angles="\n".join(f"{i + 1}. {a}: {ANGLE_HINTS[a]}" for i, a in enumerate(angles)),
                                   tone=cfg.tone, language=instruction(lang), words=round(cfg.seconds * 2.4),
                                   seconds=cfg.seconds, claims=CLAIMS[cfg.claims])
            try:
                r = route(TextJob(prompt, system="You write honest, specific e-commerce ads that sound like people.",
                                  max_tokens=600 + 450 * cfg.count, json=True), None, spec.models,
                          build=project.build, log=log)
                got = parse(r.text or "", cfg.count)
                sources.add(r.backend)
            except Exception as e:      # an unusable answer: drafts keep the step going
                log(f"  concepts ({lang}): the text backend's answer was not usable ({e}); writing drafts")
        if got is None:
            got = [draft(prof, a) for a in angles]
            sources.add("draft")
        for c, copy in zip(concepts, got):
            c["copy"][lang] = copy
        log(f"  concepts ({lang}): {len(got)}")
    result = {"languages": spec.languages, "concepts": concepts, "source": ", ".join(sorted(sources))}
    out = folder(project)
    out.mkdir(parents=True, exist_ok=True)
    (out / "concepts.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "concepts.md").write_text(to_markdown(result), encoding="utf-8")
    log(f"  concepts: {out / 'concepts.md'}")
    return result


def to_markdown(r: dict) -> str:
    out = ["# Ad concepts", ""]
    for c in r["concepts"]:
        out += [f"## {c['id']}: {c['angle']}", ""]
        for lang, cp in c["copy"].items():
            mark = " (draft)" if cp.get("draft") else ""
            out += [f"**{lang}**{mark}", "", f"- Hook: {cp['hook']}", f"- Headline: {cp['headline']}",
                    f"- Call to action: {cp['cta']}", "- On screen: " + " / ".join(cp["lines"]), "",
                    f"> {cp['script']}", ""]
    return "\n".join(out)


def pick(project: Project, count: Optional[int] = None) -> list[dict]:
    """The concepts to make variations of (all, or the first `count`)."""
    got = load(project).get("concepts") or []
    return got[:count] if count else got
