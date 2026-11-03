"""`studio listing`: store listing copy for the product: a title, bullet points and a description (issue #179).

A text backend (engine/router) writes it from the brief, the product description and the picked stills' directions,
in the asked tone. With none, a plain template is filled from what the project says and marked as a draft, so there is
always something to edit. Written to <project>/listing/listing.json and listing.md.
"""
from __future__ import annotations

import json
import re
from typing import Callable

from .project import BuildError, Project

PROMPT = """Write store listing copy for this product.
Product: {describe}
Brief: {brief}
Tone: {tone}
Answer with JSON only: {{"title": "...", "bullets": ["...", ...], "description": "..."}}
- title: at most {max_title} characters, the product first, no hype words
- bullets: exactly {bullets}, each one concrete benefit or fact in under 15 words
- description: two short paragraphs, plain words
Only say what the product description and brief support; never invent specifications, materials or claims."""


def parse(text: str, bullets: int, max_title: int) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in the answer")
    d = json.loads(m.group(0))
    title, bl, desc = d.get("title"), d.get("bullets"), d.get("description")
    if not isinstance(title, str) or not title.strip() or not isinstance(desc, str) or not isinstance(bl, list):
        raise ValueError("title, bullets and description are required")
    bl = [str(b).strip() for b in bl if str(b).strip()][:bullets]
    if len(bl) < bullets:
        raise ValueError(f"only {len(bl)} of {bullets} bullets")
    return {"title": title.strip()[:max_title], "bullets": bl, "description": desc.strip()}


def template(describe: str, brief: str, bullets: int, max_title: int) -> dict:
    """A draft from what the project says, with places marked for what it doesn't."""
    what = (describe or "This product").strip().rstrip(".")
    name = what[:1].upper() + what[1:]
    lines = [f"{name}.", brief.strip().rstrip(".") + "." if brief.strip() else "What it is for: say it in one line.",
             "Size and materials: add them here.", "Care: how to look after it.", "What's in the box: list it.",
             "Delivery and returns: your terms."]
    return {"title": name[:max_title], "bullets": lines[:bullets],
            "description": f"{name}. {brief.strip()}".strip() + "\n\nAdd the details a buyer needs: size, materials, care.",
            "draft": True}


def to_markdown(d: dict) -> str:
    out = [f"# {d['title']}", ""]
    if d.get("draft"):
        out += ["> Draft from the project's own description: no text backend could run. Edit before using.", ""]
    out += [f"- {b}" for b in d["bullets"]] + ["", d["description"], ""]
    return "\n".join(out)


def make(project: Project, log: Callable[[str], None] = print) -> dict:
    spec = project.load_project() if project.is_project_file else None
    if spec is None or spec.outputs.listing is None:
        raise BuildError(f"{project.name} has no outputs.listing in project.yaml (docs/stills.md#listing-copy)")
    ls = spec.outputs.listing
    describe = (spec.outputs.stills.describe if spec.outputs.stills else "") or (spec.product.name if spec.product else "")
    from .router import NoBackend, TextJob, choose, route
    result, source = None, "template"
    try:
        choose("text", spec.models)
        job = TextJob(PROMPT.format(describe=describe or "a product", brief=spec.brief or "none given", tone=ls.tone,
                                    max_title=ls.max_title, bullets=ls.bullets),
                      system="You write clear, honest e-commerce copy.", max_tokens=1500)
        r = route(job, None, spec.models, build=project.build, log=log)
        result, source = parse(r.text or "", ls.bullets, ls.max_title), r.backend
    except NoBackend:
        pass
    except Exception as e:      # an unreadable answer or a provider error: the draft template still gives a start
        log(f"  listing: the text backend's answer was not usable ({e}); writing a draft from the project instead")
    if result is None:
        result = template(describe, spec.brief, ls.bullets, ls.max_title)
    result["source"] = source
    folder = project.root / "listing"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "listing.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (folder / "listing.md").write_text(to_markdown(result), encoding="utf-8")
    log(f"  listing: {folder / 'listing.md'} ({source})")
    return result
