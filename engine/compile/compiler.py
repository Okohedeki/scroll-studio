"""Site compiler: spec + built scene assets + runtime bundle -> dist/ (plain static files)."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader, select_autoescape
from markupsafe import Markup

from ..config import STATIC
from ..inputs import credit as image_credit, resolve_image
from ..project import BuildContext, BuildError, Project
from ..spec import Site, is_scene
from . import fonts, themes

TEMPLATES = Path(__file__).resolve().parent / "templates"


def _env(style_dir: Optional[Path] = None) -> Environment:
    # a style's own templates are reachable as "style/<file>" (see themes.style_dir)
    loaders = [FileSystemLoader(TEMPLATES)]
    if style_dir is not None:
        loaders.append(PrefixLoader({"style": FileSystemLoader(style_dir)}))
    env = Environment(loader=ChoiceLoader(loaders), autoescape=select_autoescape(["html", "j2"]),
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


def _knockout(im):
    """Push a light studio background to pure white so a multiply blend makes it vanish into the panel.

    The background colour is sampled from the image's edges; every channel is scaled so it maps to 255, then
    pixels that end up near-white are eased the rest of the way. Shadows and the product keep their shading.
    """
    import numpy as np
    from PIL import Image
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    b = max(4, min(h, w) // 30)
    edge = np.concatenate([a[:b].reshape(-1, 3), a[-b:].reshape(-1, 3), a[:, :b].reshape(-1, 3), a[:, -b:].reshape(-1, 3)])
    bg = np.percentile(edge, 75, axis=0)
    if bg.mean() < 170:   # not a light studio background: leave the image alone
        return im
    a = np.clip(a * (255.0 / np.maximum(bg, 1)), 0, 255)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    t = np.clip((lum - 232) / 16, 0, 1)[..., None]
    t = t * t * (3 - 2 * t)
    a = a * (1 - t) + 255 * t
    return Image.fromarray(a.astype(np.uint8))


def favicon(site: Site, theme: dict) -> str:
    """A data-URI SVG icon: the nav logo's path on the accent, or the site's initial. Browsers ask for
    /favicon.ico on every page otherwise, and hosts such as GitHub Pages answer with a 404."""
    from urllib.parse import quote
    acc, ink = theme["colors"]["accent"], theme["colors"]["accent_ink"]
    logo = site.nav.logo
    if logo and logo.startswith("M"):
        body = f'<path d="{logo}" fill="none" stroke="{ink}" stroke-width="1.8" transform="translate(4 4)"/>'
    else:
        letter = (site.name.strip()[:1] or "S").upper().replace("&", "&amp;").replace("<", "&lt;")
        body = (f'<text x="16" y="22.5" text-anchor="middle" font-family="system-ui,sans-serif" font-size="18" '
                f'font-weight="700" fill="{ink}">{letter}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="{acc}"/>{body}</svg>'
    return "data:image/svg+xml," + quote(svg)


def runtime_ready() -> bool:
    return (STATIC / "runtime" / "index.js").exists()


def nav_links(site: Site) -> list[dict]:
    if site.nav.links:
        return [l.model_dump() for l in site.nav.links]
    return [{"label": s.nav_label, "href": f"#{s.id}"} for s in site.sections if getattr(s, "nav_label", None) and s.id]


def build_site(project: Project, log: Callable[[str], None] = print,
               progress: Callable[[float, str], None] = lambda f, m="": None,
               only: Optional[str] = None, force: bool = False, options: Optional[dict] = None,
               style: Optional[str] = None, out: Optional[Path] = None, runtime_href: Optional[str] = None,
               looks: Optional[dict] = None, link_base: str = "") -> Path:
    """style: build in this look instead of the spec's; out: write the site here instead of dist/;
    runtime_href: link a runtime published elsewhere (e.g. ../../runtime/) instead of copying it in;
    looks: {"current", "items": [{name, label, href}], "home"} adds the look switcher bar.
    link_base: prefix for the page's own relative links when it is built below the site root (e.g. "../../"
    for dist/looks/<style>/), so a button to "looks/" or "privacy/" still lands on the site's page."""
    from ..scenes import builder_for

    site = project.load()
    if style is not None:
        site = site.model_copy(update={"theme": site.theme.model_copy(update={"style": style or None})})
    if not runtime_ready():
        raise BuildError("the browser runtime is not built. Run `npm install && npm run build` in the repo root "
                         "(or `studio setup`).")
    theme = themes.resolve(site.theme)
    dist = out or project.dist
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
        if not src.exists():   # e.g. a gallery preview not generated on this machine: the tile falls back to its image
            log(f"  note: {ref} not found, skipped")
            return None
        media.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, media / src.name)
        return f"assets/_media/{src.name}"
    for e in sections:
        if e["s"].type == "gallery":
            e["s"] = e["s"].model_copy(update={"items": [it.model_copy(update={"image": publish(it.image), "video": publish(it.video)})
                                                         for it in e["s"].items]})

    # Images inside blocks (hero, product, strip) can be files, URLs or generated; each is resized once to the
    # width it is shown at and written as WebP.
    def block_image(ref, width: int, knockout: bool = False) -> Optional[str]:
        if ref is None:
            return None
        src = resolve_image(project, ref, log)
        st = src.stat()
        digest = hashlib.sha1(json.dumps([str(src), st.st_size, int(st.st_mtime), width, knockout, 1]).encode()).hexdigest()[:12]
        out = media / f"{digest}.webp"
        if not out.exists():
            from PIL import Image
            media.mkdir(parents=True, exist_ok=True)
            im = Image.open(src).convert("RGB")
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            if knockout:
                im = _knockout(im)
            im.save(out, "WEBP", quality=86, method=6)
        if image_credit(ref):
            credits.append(image_credit(ref))
        return f"assets/_media/{out.name}"
    for i, e in enumerate(sections):
        s = e["s"]
        e["first"] = i == 0   # only the opening section gets the page's h1
        e["backdrop"] = block_image(getattr(s, "backdrop", None), 2400)
        if s.type == "hero":
            e["img"], e["video"] = block_image(s.image, 2400), publish(s.video)
            e["screen"] = block_image(s.device.image, 800) if s.device and s.device.image else None
            e["clip"] = publish(s.device.video) if s.device and s.device.video else None
        elif s.type == "product":
            e["img"] = block_image(s.image, 1600, knockout=s.knockout and s.surface != "dark")
            e["screen"] = block_image(s.device.image, 800) if s.device and s.device.image else None
            e["clip"] = publish(s.device.video) if s.device and s.device.video else None
            e["behind"] = block_image(s.behind.image, 800) if s.behind and s.behind.image else None
            e["behind_clip"] = publish(s.behind.video) if s.behind and s.behind.video else None
        elif s.type == "strip":
            e["imgs"] = [block_image(it.image, 900) for it in s.items]

    # Stats bound to chart data: the number comes from the same file the chart draws
    charts = {e["s"].id: e for e in sections if e["scene"] and e["s"].type == "chart"}
    for e in sections:
        if e["s"].type != "stats" or not any(st.data for st in e["s"].items):
            continue
        items = []
        for st in e["s"].items:
            if st.data:
                ch = charts.get(st.data.section)
                if not ch:
                    raise BuildError(f"stat '{st.label}': no chart section with id '{st.data.section}'")
                series = json.loads((project.build / ch["s"].id / "web" / "data.json").read_text())["series"]
                pts = series.get(st.data.series)
                if not pts:
                    raise BuildError(f"stat '{st.label}': series '{st.data.series}' is not in chart '{st.data.section}'")
                at = st.data.at
                pt = {"max": lambda: max(pts, key=lambda q: q[1]), "min": lambda: min(pts, key=lambda q: q[1]),
                      "first": lambda: pts[0], "last": lambda: pts[-1]}.get(at, lambda: next((q for q in pts if q[0] == float(at)), None))()
                if pt is None:
                    raise BuildError(f"stat '{st.label}': {st.data.series} has no point at {at}")
                v = pt[1] * st.data.scale
                st = st.model_copy(update={"value": f"{v:.{st.data.decimals}f}"})
                log(f"  stat '{st.label}' = {st.value} (from {st.data.section}/{st.data.series} {at})")
            items.append(st)
        e["s"] = e["s"].model_copy(update={"items": items})

    # CTA backgrounds can borrow a scene's final frame
    finals = {e["s"].id: (e["config"] or {}).get("end") for e in sections if e["scene"]}
    for e in sections:
        bg = getattr(e["s"], "background", None)
        if e["s"].type == "cta" and bg:
            e["bg"] = finals.get(bg[6:]) if bg.startswith("scene:") else publish(bg)

    if runtime_href is None:
        rt = dist / "runtime"
        if rt.exists():
            shutil.rmtree(rt)
        shutil.copytree(STATIC / "runtime", rt)

    # A nav logo given as an image file is copied in like any other media; SVG path data passes through.
    logo = site.nav.logo
    if logo and not logo.startswith("M"):
        logo = publish(logo)

    links = themes.font_links(theme)
    font_css = fonts.vendor(links, dist, log)
    sdir = themes.style_dir(theme["style"]) if theme["style"] else None
    env = _env(sdir)
    # theme.art: frames a style renders in its own medium (style templates see it as `art`)
    art_cfg = None
    if site.theme.art:
        from .. import art as art_mod
        art_cfg = art_mod.build(project, site.theme.art, dist, log)
    env.globals["art"] = art_cfg
    css_vars = themes.css_vars(theme, log)
    page_links = [{"label": p.title, "href": f"{p.slug}/"} for p in site.pages]
    nav = nav_links(site) + [l for l, p in zip(page_links, site.pages) if p.nav]
    html = env.get_template("site.html.j2").render(
        site=site, sections=sections, theme=theme, css_vars=css_vars, logo=logo,
        font_css=font_css, font_links=[] if font_css else links, nav_links=nav, page_links=page_links, credits=credits,
        configs={e["s"].id: e["config"] for e in sections if e["scene"]},
        style_css=themes.style_css(theme["style"]) if theme["style"] else "",
        style_blocks=bool(sdir and (sdir / "blocks.html.j2").exists()),
        style_chrome=bool(sdir and (sdir / "chrome.html.j2").exists()),
        style_scenes=bool(sdir and (sdir / "scenes.html.j2").exists()),
        runtime=runtime_href or "runtime/", looks=looks, icon=favicon(site, theme),
    )
    if link_base:
        html = re.sub(r'(<a\s[^>]*?href=")(?!#|[a-z][a-z0-9+.-]*:|/|\.\./)([^"]*")', lambda m: m.group(1) + link_base + m.group(2), html)
    (dist / "index.html").write_text(html, encoding="utf-8")

    # Plain pages (privacy policy, support): Markdown set in the site's theme at /<slug>/. They live one
    # level down, so every site-relative link gets the `base` prefix.
    if site.pages:
        import markdown
        base = "../"
        def rebase(href: str) -> str:
            return href if href.startswith(("http://", "https://", "mailto:", "tel:")) else base + href
        for p in site.pages:
            src = project.path(p.source)
            if not src.exists():
                raise BuildError(f"page '{p.slug}': {p.source} not found")
            body = markdown.markdown(src.read_text(encoding="utf-8"), extensions=["sane_lists", "smarty", "tables", "fenced_code", "toc"],
                                     extension_configs={"toc": {"permalink": False}})
            page_html = env.get_template("page.html.j2").render(
                site=site, page=p, icon=favicon(site, theme), body=Markup(body), theme=theme, css_vars=css_vars, base=base,
                logo=rebase(logo) if logo and not logo.startswith("M") else logo,
                font_css=rebase(font_css) if font_css else None, font_links=[] if font_css else links,
                nav_links=[{"label": l["label"], "href": rebase(l["href"])} for l in nav],
                page_links=[{"label": l["label"], "href": rebase(l["href"])} for l in page_links],
            )
            out = dist / p.slug
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(page_html, encoding="utf-8")
            log(f"page -> {out / 'index.html'}")

    progress(1.0, "done")
    log(f"site -> {dist / 'index.html'}")
    return dist / "index.html"
