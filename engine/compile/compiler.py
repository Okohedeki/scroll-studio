"""Site compiler: spec + built scene assets + runtime bundle -> dist/ (plain static files)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from ..config import STATIC
from ..project import BuildContext, BuildError, Project
from ..spec import Site, is_scene
from . import themes

TEMPLATES = Path(__file__).resolve().parent / "templates"


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]),
                      trim_blocks=True, lstrip_blocks=True)
    # Copy fields allow a little inline markup (<em>, <br>, <b>, <i>); everything else is escaped.
    allowed = re.compile(r"&lt;(/?)(em|b|i|br|strong)\s*/?&gt;")
    def rich(text):
        if text is None:
            return ""
        esc = str(Markup.escape(text))
        return Markup(allowed.sub(lambda m: f"<{m.group(1)}{m.group(2)}>", esc))
    env.filters["rich"] = rich
    env.filters["vh"] = lambda v: f"{float(v) * 100:.0f}vh"
    env.filters["countable"] = lambda v: bool(re.fullmatch(r"\d+(\.\d+)?", str(v).replace(",", "")))
    return env


def runtime_ready() -> bool:
    return (STATIC / "runtime" / "index.js").exists()


def nav_links(site: Site) -> list[dict]:
    if site.nav.links:
        return [l.model_dump() for l in site.nav.links]
    return [{"label": s.nav_label, "href": f"#{s.id}"} for s in site.sections if getattr(s, "nav_label", None) and s.id]


def build_site(project: Project, log: Callable[[str], None] = print,
               progress: Callable[[float, str], None] = lambda f, m="": None,
               only: Optional[str] = None, force: bool = False, options: Optional[dict] = None) -> Path:
    from ..scenes import builder_for

    site = project.load()
    if not runtime_ready():
        raise BuildError("the browser runtime is not built. Run `npm install && npm run build` in the repo root "
                         "(or `studio setup`).")
    theme = themes.resolve(site.theme)
    dist = project.dist
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "assets").mkdir(exist_ok=True)

    sections, credits = [], []
    scenes = [s for s in site.sections if is_scene(s)]
    for i, sec in enumerate(site.sections):
        entry = {"s": sec, "scene": is_scene(sec), "config": None,
                 "sdata": sec.model_dump(mode="json", include={"hud", "steps", "layout", "length"}) if is_scene(sec) else None}
        if entry["scene"]:
            if only and sec.id != only:
                prev = project.build / sec.id / "config.json"
                if not prev.exists():
                    raise BuildError(f"section {sec.id} has never been built; build it first")
                entry["config"] = json.loads(prev.read_text())
            else:
                k = scenes.index(sec)
                log(f"[{sec.id}] {sec.type}")
                ctx = BuildContext(project, sec.id, log=log, force=force, options=options or {},
                                   progress=lambda f, m="", k=k: progress((k + f) / max(len(scenes), 1), m))
                cfg = builder_for(sec.type)(sec, ctx, theme)
                (ctx.work / "config.json").write_text(json.dumps(cfg))
                entry["config"] = cfg
            web = project.build / sec.id / "web"
            if web.exists():
                dst = dist / "assets" / sec.id
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(web, dst)
            credits += entry["config"].get("credits", [])
        sections.append(entry)

    # Block media given as project files are copied into the site; URLs pass through untouched.
    media = dist / "assets" / "_media"
    def publish(ref):
        if not ref or ref.startswith(("http://", "https://", "/", "assets/", "../")):
            return ref
        src = project.path(ref)
        if not src.exists():
            raise BuildError(f"block media not found: {ref}")
        media.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, media / src.name)
        return f"assets/_media/{src.name}"
    for e in sections:
        if e["s"].type == "gallery":
            e["s"] = e["s"].model_copy(update={"items": [it.model_copy(update={"image": publish(it.image), "video": publish(it.video)})
                                                         for it in e["s"].items]})

    # CTA backgrounds can borrow a scene's final frame
    finals = {e["s"].id: (e["config"] or {}).get("end") for e in sections if e["scene"]}
    for e in sections:
        bg = getattr(e["s"], "background", None)
        if e["s"].type == "cta" and bg:
            e["bg"] = finals.get(bg[6:]) if bg.startswith("scene:") else publish(bg)

    rt = dist / "runtime"
    if rt.exists():
        shutil.rmtree(rt)
    shutil.copytree(STATIC / "runtime", rt)

    html = _env().get_template("site.html.j2").render(
        site=site, sections=sections, theme=theme, css_vars=themes.css_vars(theme),
        font_links=themes.font_links(theme), nav_links=nav_links(site), credits=credits,
        configs={e["s"].id: e["config"] for e in sections if e["scene"]},
    )
    (dist / "index.html").write_text(html, encoding="utf-8")
    progress(1.0, "done")
    log(f"site -> {dist / 'index.html'}")
    return dist / "index.html"
