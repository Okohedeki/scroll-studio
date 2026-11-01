"""`studio layouts`: generated page layouts (issue #179). Several pages are written from the project's own material
(the brief, the picked stills and shortlist, the listing copy, the ads' headline and call to action), each arranged
differently; picking one writes its sections into outputs.site, ready for `studio build`.

A text backend (engine/router) writes the layouts as JSON sections, naming pictures by placeholder (@lifestyle:1, the
first lifestyle still) that resolve to the stills on disk. With no text backend, or for any layout it gets wrong, a
seeded local composer arranges the same material in distinct orders. Every layout is validated as a site before it is
kept. Only blocks that build without a GPU are used: hero, intro, features, gallery, faq and cta.

    make(project)              write the layouts to <project>/layouts/ (one YAML each, layouts.json, board.html)
    make(project, pick="<id>") write that layout's sections into outputs.site (the old site kept in layouts/)
"""
from __future__ import annotations

import html
import json
import random
import re
from pathlib import Path
from typing import Callable, Optional

import yaml

from .project import BuildError, Project
from .project_spec import project_dict, site_dict
from .project_spec import validate as validate_project
from .spec import Site

BLOCKS = ("hero", "intro", "features", "gallery", "faq", "cta")
SHOTS = ("lifestyle", "packshot", "detail")
PLACEHOLDER = re.compile(r"^@(packshot|lifestyle|detail):(\d+)$")


# ---------------------------------------------------------------- the material a layout is made from

def material(project: Project) -> dict:
    """What the project gives a page: name, brief, copy and the stills by shot (paths relative to the project)."""
    from .stills import run as stills
    spec = project.load_project()
    st = stills.load(project) or {}
    by_id = {c["id"]: c for c in st.get("candidates", [])}
    images: dict[str, list[str]] = {}
    for shot in SHOTS:
        ids = [st.get("picked", {}).get(shot)] + list(st.get("shortlist", {}).get(shot) or [])
        seen = list(dict.fromkeys(i for i in ids if i in by_id))
        images[shot] = [f"stills/{by_id[i]['image']}" for i in seen]
    lst_path = project.root / "listing" / "listing.json"
    lst = json.loads(lst_path.read_text(encoding="utf-8")) if lst_path.exists() else {}
    ads = spec.outputs.ads
    describe = (spec.outputs.stills.describe if spec.outputs.stills else "") or (spec.product.name if spec.product else "")
    return {"name": spec.name, "brief": spec.brief, "describe": describe,
            "title": lst.get("title") or spec.name, "bullets": lst.get("bullets") or [],
            "description": lst.get("description") or spec.brief or describe or spec.name,
            "headline": (ads.headline if ads else "") or lst.get("title") or spec.name,
            "cta": (ads.cta if ads else "") or "Shop now", "images": images}


def pic(m: dict, shot: str, n: int = 1) -> Optional[str]:
    """The n-th still of a shot (wrapping), else any still, else None."""
    xs = m["images"].get(shot) or [x for s in SHOTS for x in m["images"].get(s) or []]
    return xs[(n - 1) % len(xs)] if xs else None


# ---------------------------------------------------------------- the local composer

def _hero(m, shot, align):
    h = {"type": "hero", "title": m["headline"], "body": m["description"].split("\n")[0][:220], "align": align,
         "buttons": [{"label": m["cta"], "href": "#buy"}]}
    if pic(m, shot):
        h["image"] = pic(m, shot)
    return h


def _intro(m, kicker):
    return {"type": "intro", "kicker": kicker, "title": m["title"], "body": m["description"]}


def _features(m, with_images):
    items = []
    for i, b in enumerate(m["bullets"][:6] or [m["describe"] or m["title"]]):
        it = {"title": b.rstrip(".")[:80]}
        if with_images and pic(m, "detail", i + 1):
            it["image"] = pic(m, "detail", i + 1)
        items.append(it)
    return {"type": "features", "kicker": "Why it works", "title": "The details", "items": items}


def _gallery(m):
    tiles = [(s, x) for s in SHOTS for x in (m["images"].get(s) or [])][:6]
    if not tiles:
        return None
    return {"type": "gallery", "kicker": "Look closer", "title": m["name"],
            "items": [{"title": s.capitalize(), "href": "#buy", "image": x} for s, x in tiles]}


def _cta(m, bg):
    c = {"type": "cta", "id": "buy", "title": m["headline"], "button": {"label": m["cta"], "href": "#buy"}}
    if bg and pic(m, "lifestyle", 2):
        c["background"] = pic(m, "lifestyle", 2)
    return c


RECIPES = {
    "Showcase": lambda m: [_hero(m, "lifestyle", "center"), _intro(m, "About"), _gallery(m), _features(m, False),
                           _cta(m, False)],
    "Editorial": lambda m: [_intro(m, (m["brief"] or "New")[:60]), _hero(m, "packshot", "left"), _features(m, True),
                            _cta(m, True)],
    "Gallery first": lambda m: [_hero(m, "packshot", "center"), _gallery(m), _intro(m, "The story"),
                                _features(m, False), _cta(m, True)],
    "Details": lambda m: [_hero(m, "packshot", "left"), _features(m, True), _intro(m, "Made to last"), _gallery(m),
                          _cta(m, False)],
    "Short": lambda m: [_hero(m, "lifestyle", "left"), _features(m, False), _cta(m, False)],
}


def compose(m: dict, n: int, seed: int, skip: tuple[str, ...] = ()) -> list[dict]:
    """n layouts from the recipes, in a seeded order, none repeated and none in `skip`."""
    names = [k for k in RECIPES if k not in skip]
    random.Random(f"layouts:{seed}").shuffle(names)
    return [{"name": name, "source": "local", "sections": [s for s in RECIPES[name](m) if s]} for name in names[:n]]


# ---------------------------------------------------------------- the text backend

PROMPT = """Design {n} different landing pages for one product. Each is a list of sections, top to bottom.
Product: {describe}
Brief: {brief}
Title: {title}
Selling points: {bullets}
Call to action: {cta}
Pictures you may use (by placeholder only): {pictures}
Section types, with their fields:
  hero      title, body, align (center|left), image (a placeholder), buttons [{{label, href}}]
  intro     kicker, title, body
  features  kicker, title, items [{{title, body, image?}}]
  gallery   kicker, title, items [{{title, href, image}}]
  faq       title, items [{{q, a}}]
  cta       id "buy", title, button {{label, href}}
Rules: 3 to 6 sections each; the pages must differ in order and emphasis; say only what the material supports.
Answer with JSON only: [{{"name": "...", "sections": [...]}}, ...]"""


def resolve(sections: list, m: dict) -> list[dict]:
    """Placeholders (@shot:n) replaced by still paths; an image that names no still is dropped; unknown blocks too."""
    def known(v) -> bool:
        mt = PLACEHOLDER.match(v) if isinstance(v, str) else None
        return bool(mt and pic(m, mt.group(1)))

    def fix(v):
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()
                    if not (k in ("image", "background") and isinstance(x, str) and x.startswith("@") and not known(x))}
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, str) and known(v):
            mt = PLACEHOLDER.match(v)
            return pic(m, mt.group(1), int(mt.group(2)))
        return v
    return [fix(s) for s in sections if isinstance(s, dict) and s.get("type") in BLOCKS]


def written(m: dict, n: int, policy, build: Path, log) -> list[dict]:
    from .router import NoBackend, TextJob, choose, route
    try:
        choose("text", policy)
    except NoBackend:
        return []
    pictures = ", ".join(f"@{s}:{i + 1}" for s in SHOTS for i in range(len(m["images"].get(s) or []))) or "none"
    job = TextJob(PROMPT.format(n=n, describe=m["describe"] or m["name"], brief=m["brief"] or "none", title=m["title"],
                                bullets="; ".join(m["bullets"]) or "none", cta=m["cta"], pictures=pictures),
                  system="You are a web designer who writes clean, honest product pages.", max_tokens=6000)
    try:
        r = route(job, None, policy, build=build, log=log)
        found = re.search(r"\[.*\]", r.text or "", re.S)
        items = json.loads(found.group(0)) if found else []
    except Exception as e:      # a provider error or unreadable answer: the local composer fills in
        log(f"  layouts: the text backend's answer was not usable ({e}); composing locally")
        return []
    return [{"name": str(it.get("name") or f"Layout {i + 1}")[:40], "source": r.backend,
             "sections": resolve(it.get("sections") or [], m)} for i, it in enumerate(items) if isinstance(it, dict)]


# ---------------------------------------------------------------- validating, writing, picking

def valid(layout: dict, m: dict) -> Optional[str]:
    """None when the layout validates as a site, else why not."""
    if not layout["sections"]:
        return "no sections"
    try:
        Site.model_validate({"name": m["name"], "sections": layout["sections"]})
    except Exception as e:
        return str(e).splitlines()[0][:160]
    return None


def folder(project: Project) -> Path:
    return project.root / "layouts"


def make(project: Project, pick: Optional[str] = None, log: Callable[[str], None] = print) -> dict:
    spec = project.load_project() if project.is_project_file else None
    if spec is None or spec.outputs.layouts is None:
        raise BuildError(f"{project.name} has no outputs.layouts in project.yaml (docs/stills.md#page-layouts)")
    if pick:
        return _pick(project, pick, log)
    lo = spec.outputs.layouts
    m = material(project)
    kept: list[dict] = []
    for layout in written(m, lo.count, spec.models, project.build, log):
        why = valid(layout, m)
        if why:
            log(f"  layouts: dropped {layout['name']!r} from the text backend ({why})")
        elif len(kept) < lo.count:
            kept.append(layout)
    if len(kept) < lo.count:
        kept += [x for x in compose(m, lo.count - len(kept), lo.seed, tuple(k["name"] for k in kept)) if not valid(x, m)]
    out = folder(project)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("l*.yaml"):
        old.unlink()
    for i, layout in enumerate(kept, 1):
        layout["id"] = f"l{i}"
        (out / f"{layout['id']}.yaml").write_text(yaml.safe_dump({"sections": layout["sections"]}, sort_keys=False,
                                                                 allow_unicode=True, width=110), encoding="utf-8")
    state = {"layouts": kept}
    (out / "layouts.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (out / "board.html").write_text(board(m["name"], kept), encoding="utf-8")
    log(f"  layouts: {len(kept)} written; board at {out / 'board.html'}")
    return state


def _pick(project: Project, pick: str, log) -> dict:
    out = folder(project)
    f = out / f"{pick}.yaml"
    if not re.fullmatch(r"l\d+", pick) or not f.exists():
        raise BuildError(f"no layout {pick!r}: run `studio layouts {project.name}` and see layouts/board.html")
    sections = yaml.safe_load(f.read_text(encoding="utf-8"))["sections"]
    data = yaml.safe_load(project.spec_path.read_text(encoding="utf-8")) or {}
    old = (data.get("outputs") or {}).get("site")
    if old:
        (out / "site-before-pick.yaml").write_text(yaml.safe_dump(old, sort_keys=False, allow_unicode=True),
                                                   encoding="utf-8")
    data.setdefault("outputs", {})["site"] = {**(old or {}), "sections": sections}
    validate_project(data)                         # the folded site must build before anything is written
    site = site_dict(data)
    project.spec_path.write_text(yaml.safe_dump(project_dict(site, keep=data), sort_keys=False, allow_unicode=True,
                                                width=110), encoding="utf-8")
    log(f"  layouts: {pick} is now outputs.site; build it with `studio build {project.name}`")
    return {"picked": pick, "sections": len(sections)}


# ---------------------------------------------------------------- the board: each layout as a wireframe page

def _e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _bg(img) -> str:
    return f"background-image:url('../{_e(img)}')" if img else ""


def _block(s: dict) -> str:
    t, title = s.get("type"), s.get("title") or ""
    if t == "hero":
        return (f"<div class='b hero {_e(s.get('align', 'center'))}' style=\"{_bg(s.get('image'))}\">"
                f"<b>{_e(title)}</b><i class=btn></i></div>")
    if t in ("gallery", "features"):
        tiles = "".join(f"<span style=\"{_bg(it.get('image'))}\"></span>" if it.get("image") else "<span class=plain></span>"
                        for it in s.get("items", [])[:6])
        return f"<div class='b {t}'><em>{_e(t)}</em><b>{_e(title)}</b><div class=tiles>{tiles}</div></div>"
    if t == "cta":
        return f"<div class='b cta' style=\"{_bg(s.get('background'))}\"><b>{_e(title)}</b><i class=btn></i></div>"
    return f"<div class='b {_e(t)}'><em>{_e(t)}</em><b>{_e(title)}</b><p></p><p class=short></p></div>"


BOARD_CSS = """
:root{--canvas:#0d0e10;--t1:#f1efe9;--t2:#a9a69e;--t3:#6d6a64;--a1:#f2b56b;
--mono:ui-monospace,"JetBrains Mono",Consolas,monospace;--sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--t1);font:14px/1.45 var(--sans)}
header{padding:36px 40px 4px}h1{margin:0;font:500 13px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--t2)}
header p{margin:6px 0 0;color:var(--t3);font:12px var(--mono)}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:36px;padding:28px 40px 60px}
.page h2{margin:0 0 12px;font-size:22px;font-weight:600}
.meta{color:var(--a1);font:600 11px var(--mono);letter-spacing:.12em;text-transform:uppercase;margin-bottom:4px}
.sheet{background:#f4f1ea;border-radius:8px;overflow:hidden;color:#24221f}
.b{padding:14px 16px;border-bottom:1px solid rgba(0,0,0,.06);background-size:cover;background-position:center}
.b em{display:block;font:600 9px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:#8a8379}
.b b{display:block;font-size:13px;margin:2px 0 6px}
.b p{height:6px;background:rgba(0,0,0,.1);border-radius:3px;margin:4px 0}.b p.short{width:60%}
.hero{min-height:150px;display:flex;flex-direction:column;justify-content:flex-end;color:#fff;background-color:#3a3631;
box-shadow:inset 0 -90px 60px -30px rgba(0,0,0,.55)}.hero.center{align-items:center;text-align:center}
.hero b{font-size:17px;text-shadow:0 1px 8px rgba(0,0,0,.4)}
.btn{display:block;width:70px;height:16px;border-radius:9px;background:var(--a1)}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:4px}
.tiles span{aspect-ratio:1;background-size:cover;background-position:center;border-radius:3px}.tiles span.plain{background:rgba(0,0,0,.08)}
.cta{min-height:90px;background-color:#24221f;color:#fff;box-shadow:inset 0 0 0 999px rgba(0,0,0,.35)}
code{color:var(--t2);font:12px var(--mono)}
.empty{padding:60px 40px;color:var(--t3);font:13px var(--mono)}
@media (max-width:700px){header,main{padding-left:16px;padding-right:16px}}
"""


def board(name: str, layouts: list[dict]) -> str:
    pages = "".join(
        f"<section class=page aria-label='{_e(x['name'])}'><div class=meta>{_e(x['id'])} · {_e(x['source'])} · "
        f"{len(x['sections'])} sections</div><h2>{_e(x['name'])}</h2><div class=sheet>"
        + "".join(_block(s) for s in x["sections"])
        + f"</div><p><code>studio layouts --pick {_e(x['id'])}</code></p></section>" for x in layouts)
    body = f"<main>{pages}</main>" if layouts else "<p class=empty>No layouts yet.</p>"
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><title>{_e(name)} · layouts</title><style>{BOARD_CSS}</style></head><body><header><h1>"
            f"{_e(name)} · page layouts</h1><p>{len(layouts)} layouts · pick one to make it the site</p></header>"
            f"{body}</body></html>")
