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
from .. import layout, safety
from ..project import BuildContext, BuildError, Project
from ..spec import ImageInput, Site, is_scene
from . import fonts, themes

TEMPLATES = Path(__file__).resolve().parent / "templates"


class _SkinLoader(FileSystemLoader):
    """A style's templates in a brand's colours and fonts: the markup draws some of the style's palette itself (signage
    tubes, an SVG mascot), and a brand swaps those the way it swaps them in the stylesheet (themes.reskin)."""

    def __init__(self, path: Path, skin: dict):
        super().__init__(path)
        self.skin = skin

    def get_source(self, environment, template):
        source, filename, uptodate = super().get_source(environment, template)
        return themes.reskin(source, self.skin), filename, uptodate


def _env(style_dir: Optional[Path] = None, skin: Optional[dict] = None) -> Environment:
    # a style's own templates are reachable as "style/<file>" (see themes.style_dir)
    loaders = [FileSystemLoader(TEMPLATES)]
    if style_dir is not None:
        loaders.append(PrefixLoader({"style": _SkinLoader(style_dir, skin) if skin else FileSystemLoader(style_dir)}))
    env = Environment(loader=ChoiceLoader(loaders), autoescape=select_autoescape(["html", "j2"]),
                      trim_blocks=True, lstrip_blocks=True)
    # Copy fields allow a little inline markup (<em>, <br>, <b>, <i>, <code>); everything else is escaped.
    rich = safety.rich
    env.filters["rich"] = rich
    env.filters["vh"] = lambda v: f"{float(v) * 100:.0f}vh"
    env.filters["countable"] = lambda v: bool(re.fullmatch(r"\d+(\.\d+)?", str(v).replace(",", "")))
    # the layout model: every placement field compiled into one form (engine/layout.py)
    env.globals.update(placed=layout.scene_layout, stop_spot=layout.stop_spot)
    return env


def markdown_to_html(text: str) -> str:
    """A page's Markdown as HTML. Raw HTML in the source is shown as text, never passed through (a page's Markdown may
    come from a shared project); links are limited to safe schemes when the page is written (safety.clean_page_urls)."""
    import markdown
    md = markdown.Markdown(extensions=["sane_lists", "smarty", "tables", "fenced_code", "toc"],
                           extension_configs={"toc": {"permalink": False}})
    md.preprocessors.deregister("html_block")
    md.inlinePatterns.deregister("html")
    return md.convert(text)


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


def wire_cinemagraphs(html: str, cines: dict[str, dict], name: str = "data-cine") -> str:
    """Mark where a cinemagraph's still is shown: every <img> with that poster, and every element that has it as a CSS
    background (a section backdrop), gets `data-cine` (the video, the mask, where the video sits on the still); the runtime
    (runtime/src/lib/cinemagraph.ts) lays the video over it. Nothing else changes: without the script the still is the page.
    Works on the finished markup, so every style's own templates take part. Living details are marked the same way, with
    `data-live` (wire_live)."""
    import html as htmllib

    for poster, entry in cines.items():
        attr = ' %s="%s"' % (name, htmllib.escape(json.dumps(entry, separators=(",", ":")), quote=True))
        q = re.escape(poster)
        html = re.sub(r'(<img\b[^>]*?\bsrc="%s"[^>]*?)(\s*/?>)' % q, lambda m: m.group(1) + attr + m.group(2), html)
        html = re.sub(r'(<(?!img\b)[a-z][a-z0-9-]*\b[^>]*?url\(%s\)[^>]*?)(>)' % q, lambda m: m.group(1) + attr + m.group(2), html)
    return html


def wire_live(html: str, lives: dict[str, dict]) -> str:
    """Mark where a picture with living details is shown (`data-live`: its aspect and details, engine/live.py); the runtime
    (runtime/src/players/liveStill.ts) draws them over it."""
    return wire_cinemagraphs(html, lives, "data-live")


def runtime_ready() -> bool:
    return (STATIC / "runtime" / "index.js").exists()


def nav_links(site: Site) -> list[dict]:
    if site.nav.links:
        return [l.model_dump() for l in site.nav.links]
    return [{"label": s.nav_label, "href": f"#{s.id}"} for s in site.sections if getattr(s, "nav_label", None) and s.id]


def build_site(project: Project, log: Callable[[str], None] = print,
               progress: Callable[[float, str], None] = lambda f, m="": None,
               only=None, force: bool = False, options: Optional[dict] = None,
               style: Optional[str] = None, out: Optional[Path] = None, runtime_href: Optional[str] = None,
               looks: Optional[dict] = None, link_base: str = "", standin: Optional[Callable] = None,
               badge: Optional[str] = None) -> Path:
    """only: a section id, or ids of sections and beats (a list or "a,b"): only those are rendered (a beat alone
    renders just that beat of its film); other scenes keep their last build, and a scene never built shows its
    storyboard stand-in (engine/storyboard/standin.py, from cached frames; nothing is rendered for it).
    standin: fn(section) -> (config, web dir, section to render) or None, the storyboard's stand-in for a scene;
    badge: a small corner label marking the page (the storyboard's).
    style: build in this look instead of the spec's; out: write the site here instead of dist/;
    runtime_href: link a runtime published elsewhere (e.g. ../../runtime/) instead of copying it in;
    looks: {"current", "items": [{name, label, href}], "home"} adds the look switcher bar.
    link_base: prefix for the page's own relative links when it is built below the site root (e.g. "../../"
    for dist/looks/<style>/), so a button to "looks/" or "privacy/" still lands on the site's page."""
    from ..fidelity import preview
    from ..plan import section_locked, selection
    from ..scenes import builder_for

    site = project.load()
    if isinstance(only, str):
        only = [x for x in only.split(",") if x.strip()]
    selected, beat_sel = selection(site, only)
    if style is not None:
        site = site.model_copy(update={"theme": site.theme.model_copy(update={"style": style or None})})
    if not runtime_ready():
        raise BuildError("the browser runtime is not built. Run `npm install && npm run build` in the repo root "
                         "(or `studio setup`).")
    theme = themes.resolve(site.theme)
    dist = out or project.dist
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "assets").mkdir(exist_ok=True)

    # the site's video model and Wan settings reach every builder (film beats/takes) through the options
    options = dict(options or {}, site_video_model=site.video_model, site_wan=site.wan.model_dump(mode="json"))
    sections, credits = [], []
    # site.product: its model credit goes in the footer whatever uses it; a concept page says so
    from .. import product as product_mod
    credits += product_mod.credits(site.product)
    concept = product_mod.concept_line(site.product)
    scenes = [s for s in site.sections if is_scene(s)]
    for i, sec in enumerate(site.sections):
        entry = {"s": sec, "scene": is_scene(sec), "config": None,
                 "sdata": sec.model_dump(mode="json", include={"hud", "steps", "layout", "length"}) if is_scene(sec) else None}
        if entry["scene"]:
            stand = standin(sec) if standin is not None else None
            if stand is None and selected is not None and sec.id not in selected                     and not (project.build / sec.id / "config.json").exists():
                from ..storyboard.standin import cache_only
                log(f"[{sec.id}] never built: its storyboard stand-in is shown (build it with --only {sec.id})")
                stand = cache_only(project, sec, theme, log)
                if stand is None:
                    raise BuildError(f"section {sec.id} has never been built and has no storyboard frames; build it "
                                     f"(--only {sec.id}) or run `studio storyboard` first")
            if stand is not None:
                cfg, web_src, shown = stand
                entry.update(s=shown, config=cfg,
                             sdata=shown.model_dump(mode="json", include={"hud", "steps", "layout", "length"}))
                dst = dist / "assets" / sec.id
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(web_src, dst)
                credits += cfg.get("credits", [])
                sections.append(entry)
                continue
            if selected is not None and sec.id not in selected:
                prev = project.build / sec.id / "config.json"
                entry["config"] = json.loads(prev.read_text())
                if entry["config"].get("stepsAt"):      # a builder that placed the copy itself (inside): keep its placement
                    for st, at in zip(sec.steps, entry["config"]["stepsAt"]):
                        if layout.window(st) is None and at:
                            layout.set_window(st, *at)
                    if entry["config"].get("scrollLength") and not sec.length:
                        sec.length = entry["config"]["scrollLength"]
                    entry["sdata"] = sec.model_dump(mode="json", include={"hud", "steps", "layout", "length"})
            else:
                k = scenes.index(sec)
                log(f"[{sec.id}] {sec.type}")
                opts = dict(options or {})
                if beat_sel.get(sec.id) is not None:
                    opts["only_beats"] = beat_sel[sec.id]
                ctx = BuildContext(project, sec.id, log=log, force=force, options=opts, locked=section_locked(sec),
                                   progress=lambda f, m="", k=k: progress((k + f) / max(len(scenes), 1), m))
                if ctx.locked:
                    log(f"  locked: existing renders are kept")
                cfg = builder_for(sec.type)(sec, ctx, theme)
                (ctx.work / "config.json").write_text(json.dumps(cfg))
                entry["config"] = cfg
                # a builder may schedule the steps itself (code pins captions to files)
                entry["sdata"] = sec.model_dump(mode="json", include={"hud", "steps", "layout", "length"})
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
    # Images inside blocks (hero, product, strip) can be files, URLs or generated; each is resized once to the
    # width it is shown at and written as WebP.
    cines: dict[str, dict] = {}     # poster url -> what the page needs to play its cinemagraph (data-cine)

    def cinemagraph_of(ref, poster: str) -> None:
        """An image input with `cinemagraph:` plays: its video and mask are built (cached) and copied in beside the poster.
        A storyboard (a preview level) uses only what is already built."""
        from .. import cinemagraph as cine
        from ..fidelity import is_planning
        if not isinstance(ref, ImageInput) or ref.cinemagraph is None or is_planning():
            return
        built = cine.build(project, ref, log, force=force, options=options, site_video_model=site.video_model,
                           site_wan=site.wan.model_dump(mode="json"), only_cached=preview() is not None)
        if built is None:
            log("  note: a cinemagraph is not built yet; the still is shown (build it with `studio cinemagraph` or a full build)")
            return
        media.mkdir(parents=True, exist_ok=True)

        def url(p: Path) -> str:
            shutil.copy(p, media / p.name)
            return f"assets/_media/{p.name}"
        cines[poster] = cine.page_entry(built, url)
        log(f"  cinemagraph: {cine.summary(built['data'])}")

    lives: dict[str, dict] = {}     # poster url -> its living details (data-live)

    def live_of(ref, poster: str, src: Path, shown: Path) -> None:
        """An image input with `live:`: its details resolved for the page (regions, colours, glint points; engine/live.py)."""
        if not isinstance(ref, ImageInput) or not ref.live:
            return
        from .. import live

        def url(p: Path) -> str:
            media.mkdir(parents=True, exist_ok=True)
            shutil.copy(p, media / p.name)
            return f"assets/_media/{p.name}"
        details = live.page_details(project, ref, src, shown, theme["colors"], url, log)
        if details:
            lives[poster] = live.page_entry(details, shown)
            log(f"  live: {live.summary(details)}")

    def block_image(ref, width: int, knockout: bool = False) -> Optional[str]:
        if ref is None:
            return None
        src = resolve_image(project, ref, log, alpha=True)
        st = src.stat()
        digest = hashlib.sha1(json.dumps([str(src), st.st_size, int(st.st_mtime), width, knockout, 1]).encode()).hexdigest()[:12]
        out = media / f"{digest}.webp"
        if not out.exists():
            from PIL import Image
            media.mkdir(parents=True, exist_ok=True)
            im = Image.open(src)
            # a transparent image (a product still, a cut-out PNG) keeps its alpha, so it floats on the panel
            alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
            im = im.convert("RGBA" if alpha else "RGB")
            if alpha and im.getchannel("A").getextrema()[0] == 255:
                im, alpha = im.convert("RGB"), False
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            if knockout and not alpha:
                im = _knockout(im)
            im.save(out, "WEBP", quality=86, method=6)
        if image_credit(ref):
            credits.append(image_credit(ref))
        poster = f"assets/_media/{out.name}"
        cinemagraph_of(ref, poster)
        live_of(ref, poster, src, out)
        return poster
    for e in sections:
        if e["s"].type == "gallery":
            def tile(img):
                return block_image(img, 900) if isinstance(img, ImageInput) else publish(img)
            e["s"] = e["s"].model_copy(update={"items": [it.model_copy(update={"image": tile(it.image), "video": publish(it.video)})
                                                         for it in e["s"].items]})
    def block_media(s) -> dict:
        """The media a block shows (images resized and written as WebP, files copied in), keyed as the templates read them."""
        x = {"backdrop": block_image(getattr(s, "backdrop", None), 2400)}
        if s.type == "hero":
            from ..inputs import hero_image
            img, side = hero_image(project, s)
            x["img"], x["video"] = block_image(img, 2400), publish(s.video)
            if side and x["img"] and not s.video:      # words over a calm side: their colour from the picture
                from ..medium import tone
                from PIL import Image
                x["calm"] = {"side": side, "tone": tone(Image.open(media / Path(x["img"]).name), side)}
            x["screen"] = block_image(s.device.image, 800) if s.device and s.device.image else None
            x["clip"] = publish(s.device.video) if s.device and s.device.video else None
        elif s.type == "product":
            # a cinemagraph's video is the photograph as shot: whitening the still's studio background would put a box around it
            moving = isinstance(s.image, ImageInput) and s.image.cinemagraph is not None
            # an illustration in a named medium is a whole print, shown as a plate: no knockout, no feathered edge
            from ..inputs import art_direction
            plate = isinstance(s.image, ImageInput) and art_direction(project, s.image)[0] is not None
            x["img"] = block_image(s.image, 1600, knockout=s.knockout and s.surface != "dark" and not moving and not plate)
            x["plate"] = plate
            x["screen"] = block_image(s.device.image, 800) if s.device and s.device.image else None
            x["clip"] = publish(s.device.video) if s.device and s.device.video else None
            x["behind"] = block_image(s.behind.image, 800) if s.behind and s.behind.image else None
            x["behind_clip"] = publish(s.behind.video) if s.behind and s.behind.video else None
        elif s.type == "strip":
            x["imgs"] = [block_image(it.image, 900) for it in s.items]
        row = s if s.type == "logos" else getattr(s, "logos", None)
        if row is not None:
            x["logos"] = [logo_image(lg.image) for lg in row.items]
        return x

    def logo_image(ref: Optional[str]) -> Optional[dict]:
        """A logo for the strip: an SVG is copied in as it is, a picture resized to the height it is shown at. `mask`: it
        has transparency, so the page can show it as a silhouette in the theme's text colour."""
        if not ref:
            return None
        if ref.startswith(("http://", "https://")):
            return {"src": ref, "mask": ref.lower().split("?")[0].endswith((".svg", ".png", ".webp"))}
        if ref.lower().endswith(".svg"):
            src = publish(ref)
            return {"src": src, "mask": True} if src else None
        src = project.path(ref)
        if not src.exists():
            log(f"  note: logo {ref} not found; its name is shown instead")
            return None
        from PIL import Image
        st = src.stat()
        out = media / f"logo-{hashlib.sha1(json.dumps([str(src), st.st_size, int(st.st_mtime), 1]).encode()).hexdigest()[:12]}.webp"
        with Image.open(src) as im:
            alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
            im = im.convert("RGBA" if alpha else "RGB")
            alpha = alpha and im.getchannel("A").getextrema()[0] < 255
            if not out.exists():
                media.mkdir(parents=True, exist_ok=True)
                if im.height > 160:
                    im = im.resize((round(im.width * 160 / im.height), 160), Image.LANCZOS)
                im.save(out, "WEBP", quality=90, method=6)
        return {"src": f"assets/_media/{out.name}", "mask": alpha}
    for i, e in enumerate(sections):
        s = e["s"]
        e["first"] = i == 0   # only the opening section gets the page's h1
        e.update(block_media(s))
        if getattr(s, "journey", None) is not None:      # a one-take page: the blocks inside its stops (engine/journey.py)
            e["jx"] = {st.id: [block_media(b) for b in st.blocks] for st in s.journey.stops}

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

    # film grammar between sections (`transition:`): which joins get their own stretch of scroll (engine/cuts.py)
    from .. import cuts as cuts_mod
    style_cfg = themes.styles().get(theme["style"], {}) if theme["style"] else {}
    blocked = f"the {theme['style']} style plays its own hand-over between sections" if style_cfg.get("cuts") is False else None
    cut_cfgs = cuts_mod.plan(site, log, None if blocked else cuts_mod.find_anchors(project, site, sections, dist, log), blocked)
    for e in sections:
        e["cut_in"] = e["cut_out"] = None
    for c in cut_cfgs:
        sections[c["a"]]["cut_out"], sections[c["b"]]["cut_in"] = c["n"], c["n"]

    if runtime_href is None:
        rt = dist / "runtime"
        if rt.exists():
            shutil.rmtree(rt)
        shutil.copytree(STATIC / "runtime", rt)
        if theme["phone"]:
            (rt / "studio.css").write_text(themes.phone_css((rt / "studio.css").read_text(encoding="utf-8"), theme["phone"]),
                                           encoding="utf-8")

    # A nav logo given as an image file is copied in like any other media; SVG path data passes through.
    logo = site.nav.logo or theme["logo"]        # a brand's logo (theme.from) when the nav names none
    if logo and not logo.startswith("M"):
        logo = publish(logo)

    links = themes.font_links(theme)
    font_css = fonts.vendor(links, dist, log)
    google = [] if font_css else links         # linked from Google when they could not be self-hosted
    if theme["font_files"]:
        font_css = fonts.own(project, theme["font_files"], dist, append=font_css is not None)
    sdir = themes.style_dir(theme["style"]) if theme["style"] else None
    env = _env(sdir, theme.get("skin"))
    # theme.art: frames a style renders in its own medium (style templates see it as `art`)
    art_cfg = None
    if site.theme.art:
        from .. import art as art_mod
        art, pv = site.theme.art, preview()
        if pv is not None and art.motion:   # a storyboard: the art as a still (its own cache entry)
            art = art.model_copy(update={"motion": None})
        if pv is not None and not pv.comfy and not art_mod.cached(project, art, site.video_model,
                                                                  site.wan.model_dump(mode="json")):
            log("  note: theme.art is not generated yet; left out of the sketch")
        else:
            art_cfg = art_mod.build(project, art, dist, log, site_video_model=site.video_model,
                                    site_wan=site.wan.model_dump(mode="json"))
    env.globals["art"] = art_cfg
    css_vars = themes.css_vars(theme, log)
    # launch trailer (`trailer.embed`): a button and a modal player, once `studio trailer` has made the film
    trailer = None
    if site.trailer and site.trailer.embed:
        tdir = project.dist / "trailer"
        if (tdir / "trailer-16x9.mp4").exists():
            rel = "" if dist == project.dist else link_base
            tall = (tdir / "trailer-9x16.mp4").exists()
            trailer = {"label": site.trailer.embed_label, "wide": rel + "trailer/trailer-16x9.mp4",
                       "poster": rel + "trailer/trailer-16x9.jpg", "tall": rel + "trailer/trailer-9x16.mp4" if tall else None,
                       "tall_poster": rel + "trailer/trailer-9x16.jpg"}
        else:
            log("  note: trailer.embed is on but there is no trailer yet: run `studio trailer`, then build again")
    page_links = [{"label": p.title, "href": f"{p.slug}/"} for p in site.pages]
    nav = nav_links(site) + [l for l, p in zip(page_links, site.pages) if p.nav]
    html = env.get_template("site.html.j2").render(
        site=site, sections=sections, theme=theme, css_vars=css_vars, logo=logo,
        font_css=font_css, font_links=google, nav_links=nav, page_links=page_links, credits=credits,
        concept=concept, product=site.product,
        configs={e["s"].id: e["config"] for e in sections if e["scene"]},
        style_css=themes.style_css(theme["style"], theme) if theme["style"] else "",
        style_blocks=bool(sdir and (sdir / "blocks.html.j2").exists()),
        style_chrome=bool(sdir and (sdir / "chrome.html.j2").exists()),
        style_scenes=bool(sdir and (sdir / "scenes.html.j2").exists()),
        runtime=runtime_href or "runtime/", looks=looks, icon=favicon(site, theme), trailer=trailer, cuts=cut_cfgs,
    )
    if cines:
        html = wire_cinemagraphs(html, cines)
    if lives:
        html = wire_live(html, lives)
    if badge:   # the storyboard marks its pages: never mistaken for the finished site
        mark = (f'<div class="ss-storyboard-badge" style="position:fixed;left:14px;bottom:14px;z-index:2147483000;'
                f'font:600 12px/1 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#111;'
                f'background:#ffd25e;padding:7px 11px;border-radius:99px;box-shadow:0 2px 12px rgba(0,0,0,.35);'
                f'pointer-events:none">{Markup.escape(badge)}</div>')
        html = html.replace("</body>", mark + "\n</body>", 1).replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
    if link_base:
        html = re.sub(r'(<a\s[^>]*?href=")(?!#|[a-z][a-z0-9+.-]*:|/|\.\./)([^"]*")', lambda m: m.group(1) + link_base + m.group(2), html)
    (dist / "index.html").write_text(safety.clean_page_urls(html, log), encoding="utf-8")

    # Plain pages (privacy policy, support): Markdown set in the site's theme at /<slug>/. They live one
    # level down, so every site-relative link gets the `base` prefix.
    if site.pages:
        base = "../"
        def rebase(href: str) -> str:
            return href if href.startswith(("http://", "https://", "mailto:", "tel:")) else base + href
        for p in site.pages:
            src = project.path(p.source)
            if not src.exists():
                raise BuildError(f"page '{p.slug}': {p.source} not found")
            body = markdown_to_html(src.read_text(encoding="utf-8"))
            page_html = env.get_template("page.html.j2").render(
                site=site, page=p, icon=favicon(site, theme), body=Markup(body), theme=theme, css_vars=css_vars, base=base,
                concept=concept, product=site.product,
                logo=rebase(logo) if logo and not logo.startswith("M") else logo,
                font_css=rebase(font_css) if font_css else None, font_links=google,
                nav_links=[{"label": l["label"], "href": rebase(l["href"])} for l in nav],
                page_links=[{"label": l["label"], "href": rebase(l["href"])} for l in page_links],
            )
            out = dist / p.slug
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(safety.clean_page_urls(page_html, log), encoding="utf-8")
            log(f"page -> {out / 'index.html'}")

    progress(1.0, "done")
    log(f"site -> {dist / 'index.html'}")
    return dist / "index.html"
