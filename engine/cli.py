"""`studio` command line.

  studio new my-site [--example lodestar-orbital]   create projects/my-site (from an example or a starter)
  studio new my-site --laptop [--image photo.jpg]   a starter that builds on any laptop: no GPU, ComfyUI or Blender
  studio remake https://example.com/ [--name x] [--style bauhaus] [--no-gpu]   a live landing page told as a scroll site
  studio build my-site [--only hero,door] [--force] [--draft] [--yes] [--plan]
  studio storyboard my-site [--level sketch|stills|animatic] [--only id,id] [--motion] [--open]
  studio storyboard my-site --edit [--port 8971]    edit every shot in the browser: notes, captions, regenerate one image, play it
  studio storyboard my-site --notes                 the open notes written there, with each shot's current values
  studio camera my-site beat [--guide | --check]    a beat with `camera:` keys: preview its guide (pure camera), or measure how well it follows
  studio directions my-site [--n 6] [--seed 1] [--pick a]   art directions as side-by-side boards; pick one into site.yaml
  studio world my-site [--section story]            check the in-world type of a built film: its track on the frames, the depth, what to change
  studio preview my-site [--port 5173]
  studio record my-site [--section hero] [--seconds 12] [--gif]
  studio cuts my-site [--strip] [--only 0,2] [--mobile]   the film grammar between sections: each cut, the shapes a match found, frame strips
  studio cinemagraph my-site [--only steam] [--force]   build (or list) every `cinemagraph:` image: video + mask + a measured report
  studio inspect my-site [--section story] [--json]   polish report of a built film: pops, softness, halos, style drift, morphs
  studio inspect my-site --page [--section hero]      polish report of the built page: text over pictures, type, pictures, layout; exit 1 on a fail
  studio trailer my-site [--format 9x16] [--plan]      launch trailer from the site's renders -> dist/trailer/
  studio ui                                         the Studio app (http://localhost:5180)
  studio doctor                                     check Python, Node, FFmpeg, Blender, GPU, ComfyUI, models
  studio setup-comfy                                install the ComfyUI nodes for `reveal` and `faces` (restart ComfyUI after)
  studio schema                                     JSON Schema of site.yaml
  studio product my-site [--parts] [--still three-quarter]   the site's product: parts, stills
  studio light my-site [--section day] [--presets]   a `light` scene (one place, dawn to night): build it, the times with their measured drift, frame strips across each transition
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Optional

import typer

from .config import ROOT, settings

app = typer.Typer(add_completion=False, help="Scroll Studio: build scroll-driven sites from any inputs.\n\nScroll Studio by Edeki Okoh: https://github.com/Okohedeki/scroll-studio (GNU AGPL-3.0, see NOTICE.md). Sites you build are yours under the Scroll Studio Output Exception.")

STARTER = """name: My Site
description: A scroll-driven site built with Scroll Studio.
theme: { preset: night }
nav: { cta: { label: Get in touch, href: "#contact" } }
sections:
  - id: hero
    type: type
    mode: scale
    text: "Hello"
    length: 2.5
  - type: intro
    kicker: About
    title: Say what you do in <em>one line.</em>
    body: Replace this with a paragraph about the product, the place or the idea.
  - type: cta
    id: contact
    title: Ready when <em>you are.</em>
    button: { label: Get in touch, href: "mailto:hello@example.com" }
"""


# `studio new --laptop`: every scene in it is one that needs no GPU (engine/doctor.py LAPTOP_SCENES). It opens on kinetic type
# (nothing to install), or on a photo parallax when the user brings a picture (`--image`).
LAPTOP_STARTER = """# A site that builds on any laptop: no GPU, no ComfyUI, no Blender (docs/laptop.md).
name: @TITLE@
description: A scroll-driven site built with Scroll Studio.
# Your brand: `theme: { from: https://yoursite.com }` (or a logo, or brand.yaml). A style is an optional experience on top,
# e.g. `style: bauhaus` (studio looks lists them).
theme: { preset: night }
nav: { cta: { label: Get in touch, href: "#contact" } }
sections:
@OPENING@
  - id: idea
    type: type
    mode: reveal
    text: "Say what you do in a few plain words, and let the page <em>move</em> while they read it."
    length: 3
  - type: intro
    kicker: About
    title: Say what you do in <em>one line.</em>
    body: Replace this with a paragraph about the product, the place or the idea.
  - type: features
    kicker: What you get
    title: Three things, <em>made clear.</em>
    items:
      - { tag: One, title: The first thing, body: One sentence about it. }
      - { tag: Two, title: The second thing, body: One sentence about it. }
      - { tag: Three, title: The third thing, body: One sentence about it. }
  - type: stats
    items:
      - { value: "3", label: Things to know }
      - { value: "1", label: Page }
  - type: cta
    id: contact
    title: Ready when <em>you are.</em>
    button: { label: Get in touch, href: "mailto:hello@example.com" }
"""

LAPTOP_TYPE_OPENING = """  # Open on your own photo instead: copy a picture into inputs/ and replace this scene with the parallax one in docs/laptop.md.
  - id: hero
    type: type
    mode: scale
    text: @TITLE@
    length: 2.5"""

LAPTOP_PHOTO_OPENING = """  - id: hero
    type: parallax
    layout: cards
    steps:
      - intro: true
        kicker: Welcome
        title: A picture, <em>given depth.</em>
        body: Your photo, turned into a slow camera move as you scroll.
        hint: Scroll to look around
        image: @IMAGE@"""


def laptop_starter(title: str, image: Optional[str] = None) -> str:
    """The starter site.yaml of `studio new --laptop`: kinetic type up front, or a photo parallax of `image` (a path inside inputs/)."""
    quoted = json.dumps(title)                       # a YAML double-quoted string: any name is safe
    opening = LAPTOP_PHOTO_OPENING.replace("@IMAGE@", json.dumps(image)) if image else LAPTOP_TYPE_OPENING
    return LAPTOP_STARTER.replace("@OPENING@", opening).replace("@TITLE@", quoted)


def resolve(name: str) -> Path:
    for cand in (Path(name), Path(settings()["projects"]) / name, ROOT / "examples" / name):
        if (cand / "site.yaml").exists():
            return cand.resolve()
    raise typer.BadParameter(f"no project '{name}' (looked in ., {settings()['projects']}, examples/)")


@app.command()
def new(name: str, example: Optional[str] = typer.Option(None, help="Copy an example from examples/"),
        laptop: bool = typer.Option(False, "--laptop", help="A starter that builds on any laptop, with no GPU, ComfyUI or Blender"),
        image: Optional[Path] = typer.Option(None, "--image", help="With --laptop: your photo, opened as a photo parallax "
                                                                   "(default: the page opens on kinetic type)")):
    """Create a project."""
    dst = Path(settings()["projects"]) / name
    if dst.exists():
        raise typer.BadParameter(f"{dst} already exists")
    if (laptop or image) and example:
        raise typer.BadParameter("--laptop and --image make a starter; --example copies an example: use one or the other")
    if image and not laptop:
        raise typer.BadParameter("--image goes with --laptop (studio new my-site --laptop --image photo.jpg)")
    if image and not image.is_file():
        raise typer.BadParameter(f"{image} is not a file")
    if example:
        src = ROOT / "examples" / example
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".build", "dist"))
    elif laptop:
        from PIL import Image, UnidentifiedImageError
        if image:
            try:
                with Image.open(image) as im:
                    im.verify()
            except (UnidentifiedImageError, OSError):
                raise typer.BadParameter(f"{image} is not a picture Scroll Studio can read (jpg, png, webp)") from None
        (dst / "inputs").mkdir(parents=True)
        inside = None
        if image:
            inside = "inputs/" + re.sub(r"[^A-Za-z0-9._-]+", "-", image.name)
            shutil.copyfile(image, dst / inside)
        (dst / "site.yaml").write_text(laptop_starter(re.sub(r"[-_]+", " ", name).strip().title() or "My Site", inside), encoding="utf-8")
    else:
        (dst / "inputs").mkdir(parents=True)
        (dst / "site.yaml").write_text(STARTER, encoding="utf-8")
    typer.echo(f"created {dst}\nnext: studio build {name} && studio preview {name}")
    if laptop:
        typer.echo("this one builds on any laptop: it needs no GPU, ComfyUI or Blender"
                   + (f"; it opens on {inside.split('/')[-1]} as a photo parallax (the first build downloads a small depth model)" if image else
                      "; to open on your own photo, see docs/laptop.md"))


@app.command()
def remake(url: str, name: Optional[str] = typer.Option(None, help="Project name (default: from the site's address)"),
           style: Optional[str] = typer.Option(None, help="Wear one of the styles (engine/styles/) over the brand"),
           no_gpu: bool = typer.Option(False, "--no-gpu", help="Open with a laptop scene (photo parallax) even when "
                                                               "a GPU is here")):
    """Read a live landing page and write a new project that tells it as a scroll site: its hero picture as the
    opening scene, its sections as blocks, its calls to action with their links, its brand in theme.from."""
    from .project import BuildError
    from .remake import remake as run
    try:
        r = run(url, name=name, style=style, gpu=False if no_gpu else None, log=typer.echo)
    except (BuildError, ValueError) as e:
        raise typer.BadParameter(str(e)) from None
    typer.echo("sections: " + ", ".join(f"{s['id'] or '-'} ({s['type']})" for s in r["sections"]))
    typer.echo(f"pictures: {len(r['images'])} saved in inputs/")
    if r["brand"]:
        b = r["brand"]
        typer.echo("brand: " + " ".join(f"{k} {v}" for k, v in b.get("colors", {}).items() if k in ("accent", "bg", "ink"))
                   + "".join(f", {k} font {v}" for k, v in b.get("fonts", {}).items()))
    for n in r["notes"]:
        typer.echo(f"note: {n}")
    for w in r["warnings"]:
        typer.echo(f"warning: {w}")
    typer.echo(f"\n{r['notice']}\ncreated {r['path']}\nnext: " + "  then  ".join(r["next"]))


@app.command()
def build(name: str, only: Optional[str] = typer.Option(None, help="Render only these sections and beats (ids, comma "
                                                                   "separated); the rest keep their cache or show "
                                                                   "their storyboard stand-in"),
          section: Optional[str] = typer.Option(None, help="Rebuild one scene only (same as --only <id>)"),
          force: bool = typer.Option(False, help="Ignore the cache (locked scenes and beats are still kept)"),
          draft: bool = typer.Option(False, help="Fast low-quality renders where supported"),
          yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask, even over studio.toml's confirm_over"),
          plan: bool = typer.Option(False, "--plan", help="Print what would render and the estimate, then stop")):
    """Build a project into dist/. Prints what will render and about how long it takes here before starting."""
    import sys
    from .compile.compiler import build_site
    from .plan import announce, fmt
    from .project import Project
    from .spec import deprecations
    project = Project(resolve(name))
    ids = ",".join(x for x in (only, section) if x) or None
    est = announce(project, only=ids.split(",") if ids else None, force=force, options={"draft": draft}, log=typer.echo)
    for d in deprecations(project.load()):
        typer.echo(f"warning: {d}")
    if plan:
        return
    limit = settings().get("confirm_over")
    if limit and est.total() > limit * 60 and not yes:
        if sys.stdin.isatty():
            if not typer.confirm(f"about {fmt(est.total())} of rendering (over confirm_over = {limit:g} min). Start?"):
                raise typer.Exit(1)
        else:
            typer.echo(f"stopping: about {fmt(est.total())} of rendering is over confirm_over = {limit:g} min; "
                       f"run with --yes for unattended builds")
            raise typer.Exit(2)
    out = build_site(project, only=ids, force=force, options={"draft": draft})
    typer.echo(f"built {out}")


@app.command()
def storyboard(name: str, level: str = typer.Option("stills", help="sketch (no ComfyUI: blockouts, cached stills, "
                                                                   "cards), stills (the real first frames) or animatic "
                                                                   "(stills in motion + animatic.mp4)"),
               only: Optional[str] = typer.Option(None, help="Redo only these shots (beat, section or block ids); "
                                                             "the rest keep their last storyboard frames"),
               motion: bool = typer.Option(False, "--motion", help="animatic: a tiny LTX-2.3 preview per shot "
                                                                    "(512x288, 2 s) to check motion"),
               open_: bool = typer.Option(False, "--open", help="Open storyboard.html when done"),
               edit: bool = typer.Option(False, "--edit", help="Serve the storyboard as an editing workspace instead: "
                                                               "change any shot's text, seed, motion or length (written into "
                                                               "site.yaml), regenerate one image at a time, keep every "
                                                               "variant, lock and approve shots"),
               port: Optional[int] = typer.Option(None, help="--edit: port (default: the first free one of 8971-8979)"),
               browser: bool = typer.Option(True, "--browser/--no-browser", help="--edit: open the browser"),
               notes: bool = typer.Option(False, "--notes", help="Print the open notes written in the editor, each with "
                                                                 "its shot's current values and image paths (for an "
                                                                 "agent without MCP), and stop"),
               all_notes: bool = typer.Option(False, "--all", help="--notes: include working and done notes")):
    """Storyboard the site before the full render: <project>/storyboard/ (the page with stills standing in for films,
    storyboard.html + sheet.jpg with a card per shot and the render estimate, animatic.mp4). With --edit: the same
    shots as an editing workspace on a local server."""
    from .project import Project
    if notes:
        from .storyboard.edit.workspace import Workspace
        ws = Workspace(Project(resolve(name)))
        data = ws.notes_for_agent(claim=False, include_working=all_notes, include_done=all_notes)
        if not data["notes"]:
            typer.echo("no open notes")
        for n in data["notes"]:
            typer.echo(f"{n['id']} [{n['shot']}] {n['status']} {n['time']}: {n['text']}")
            if n.get("reply"):
                typer.echo(f"    reply: {n['reply']}")
            ss = n.get("shot_state")
            if ss:
                typer.echo(f"    shot {ss['id']} ({ss['kind']}){' LOCKED' if ss['locked'] else ''}: " +
                           "; ".join(f"{k}={str(v)[:90]!r}" for k, v in ss["fields"].items() if v not in (None, "")))
                for im in ss["images"]:
                    typer.echo(f"    image {im['slot']} ({im['state']}): {im['image']}")
                    for st in im["steps"]:
                        typer.echo(f"      step {st['kind']}{' (shared)' if st['shared'] else ''}: " +
                                   "; ".join(f"{k}={str(v)[:70]!r}" for k, v in st["fields"].items()))
            for b in n.get("storyboard") or []:
                typer.echo(f"    shot {b['id']} ({b['kind']}, {b['seconds'] or '-'} s): {b['caption'] or b['title']}")
        if data["notes"]:
            typer.echo("\nact with the MCP tools (set_shot_field, regenerate_shot_image, resolve_note) or edit site.yaml; "
                       "see the scroll-site skill")
        return
    if edit:
        from .storyboard.edit.api import serve
        serve(Project(resolve(name)), port=port, open_browser=browser, log=typer.echo)
        return
    from .storyboard import storyboard as run
    res = run(Project(resolve(name)), level=level, only=only.split(",") if only else None, motion=motion,
              log=typer.echo)
    typer.echo(f"sheet: {res['sheet']}")
    typer.echo(f"page: {res['site']}")
    if res["animatic"]:
        typer.echo(f"animatic: {res['animatic']}")
    if open_:
        import webbrowser
        webbrowser.open(Path(res["html"]).as_uri())


@app.command()
def directions(name: str,
               n: Optional[int] = typer.Option(None, "--n", "--count", help="How many directions (default: the spec's `directions.count`, 6)"),
               seed: Optional[int] = typer.Option(None, help="Another seed, another set of directions (default: the spec's, 1)"),
               brief: Optional[str] = typer.Option(None, help="What to pitch, in your words (default: the spec's `directions.brief`)"),
               pick: Optional[str] = typer.Option(None, "--pick", help="Write this direction (its letter, or its name) into site.yaml: "
                                                                       "theme, style, fonts, imagery, pace; copy is never touched. The old file is kept"),
               undo: bool = typer.Option(False, "--undo", help="Put site.yaml back as it was before the last pick"),
               reroll: Optional[str] = typer.Option(None, "--reroll", help="Another idea in place of this direction (its letter)"),
               stills: bool = typer.Option(False, "--stills", help="Draw the stills of the saved directions again (ComfyUI was down)"),
               images: bool = typer.Option(True, "--images/--no-images", help="--no-images: placeholder cards instead of Z-Image stills"),
               sheet: bool = typer.Option(True, "--sheet/--no-sheet", help="Make board.png (headless Chrome)"),
               serve: bool = typer.Option(False, "--serve", help="Serve the boards in the browser, with a Pick button on each"),
               port: Optional[int] = typer.Option(None, help="--serve: port (default: the first free one of 8981-8989)"),
               browser: bool = typer.Option(True, "--browser/--no-browser", help="--serve: open the browser"),
               show: bool = typer.Option(False, "--show", help="Print the saved directions and stop")):
    """Art directions for the site, pitched like a studio: one brief in, several complete directions out (concept, palette,
    type, style, imagery, motion), each a board of storyboard stills, side by side on one page. Pick one and it is written
    into site.yaml. Outputs in <project>/directions/: board.html, board.png (contact sheet), directions.json."""
    from .directions import run as dr
    from .project import Project
    project = Project(resolve(name))

    def listing(state):
        for d in state["directions"]:
            p = d["palette"]
            typer.echo(f"  {d['id'].upper()}  {d['name']:<16} {d['stance']:<17} style {d['style'] or 'none':<14} {p['name']} ({p['mode']})  "
                       f"{d['fonts']['display']} / {d['fonts']['body']}")
            typer.echo(f"       {d['concept']}")
        dv = state["diversity"]
        typer.echo(f"closest pair {dv['min']:.2f} apart; {dv['kinds']} kinds, {dv['styles']} experiences")
    if undo:
        dr.undo(project, typer.echo)
        return
    if show:
        st = dr.load(project)
        if not st:
            raise typer.BadParameter(f"no boards yet: run studio directions {name}")
        listing(st)
        typer.echo(f"page: {st['files']['html']}\nsheet: {st['files']['png']}")
        return
    if pick and not (n or seed or brief):
        res = dr.pick(project, pick, typer.echo, sheet=sheet)
        if res.get("note"):
            typer.echo(res["note"])
        else:
            typer.echo(res["diff"] or "(no change)")
            typer.echo(f"backup: {res['backup']}\nnext: studio storyboard {name}   (the images redraw in this direction's imagery)")
        return
    if reroll:
        st = dr.reroll(project, reroll, images=images, sheet=sheet, log=typer.echo)
    elif stills:
        st = dr.redraw(project, images=images, sheet=sheet, log=typer.echo)
    elif serve and dr.load(project) and not (n or seed or brief):
        st = dr.load(project)
    else:
        st = dr.make(project, n, seed, brief, images=images, sheet=sheet, log=typer.echo)
    listing(st)
    typer.echo(f"page: {st['files']['html']}\nsheet: {st['files']['png']}")
    if pick:
        res = dr.pick(project, pick, typer.echo)
        typer.echo(res["diff"] or "(no change)")
    if serve:
        from .directions.api import serve as run_server
        run_server(project, port=port, open_browser=browser, log=typer.echo)


@app.command()
def looks(name: str, styles: Optional[str] = typer.Option(None, help="Comma-separated styles (default: all of engine/styles.yaml)"),
          thumbs: bool = typer.Option(True, help="Screenshot each look for the gallery page")):
    """Build the site once in every style: dist/looks/<style>/ with a look switcher, and a gallery at dist/looks/."""
    import html as _html
    import tempfile
    from .compile import themes
    from .compile.compiler import build_site
    from .project import Project, ffmpeg
    project = Project(resolve(name))
    if not (project.dist / "runtime" / "index.js").exists():
        build_site(project)   # the looks share the main build's runtime
    else:
        # ...kept current with the engine's, so a looks-only rebuild never runs a stale runtime
        import shutil
        from .config import STATIC
        rt = project.dist / "runtime"
        shutil.rmtree(rt)
        shutil.copytree(STATIC / "runtime", rt)
    all_styles = themes.styles()
    names = [s.strip() for s in styles.split(",")] if styles else list(all_styles)
    for n in names:
        if n not in all_styles:
            raise typer.BadParameter(f"unknown style {n} (have: {', '.join(all_styles)})")
    root = project.dist / "looks"
    items = [{"name": n, "label": all_styles[n]["label"], "href": f"../{n}/"} for n in names]
    for i, n in enumerate(names):
        typer.echo(f"look {i + 1}/{len(names)}: {n}")
        build_site(project, style=n, out=root / n, runtime_href="../../runtime/", link_base="../../",
                   looks={"index": i, "items": items, "home": "../"}, log=lambda m: None)
    if thumbs:
        from .snapshot import snapshot as snap
        with tempfile.TemporaryDirectory() as tmp:
            for n in names:
                shot = snap(project.dist, ["top"], Path(tmp) / n, size=(1440, 900), log=lambda m: None, page=f"looks/{n}/index.html")[0]
                ffmpeg("-i", shot, "-vf", "scale=720:-2:flags=lanczos", "-q:v", "4", root / n / "thumb.jpg")
    site = project.load()
    cards = "\n".join(
        f'<a class="card" href="{n}/"><img src="{n}/thumb.jpg" alt="" loading="lazy" width="720" height="450">'
        f'<span class="t"><b>{_html.escape(all_styles[n]["label"])}</b><small>theme: {{ style: {n} }}</small></span>'
        f'<span class="d">{_html.escape(all_styles[n].get("about", ""))}</span></a>' for n in names)
    (root / "index.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(site.name)}: {len(names)} experiences</title>
<meta name="description" content="One site spec built as {len(names)} different experiences with Scroll Studio.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23f2f2f2'/%3E%3Ctext x='16' y='22.5' text-anchor='middle' font-family='system-ui' font-size='18' font-weight='700' fill='%230c0c0e'%3E21%3C/text%3E%3C/svg%3E">
<style>
  :root {{ color-scheme: dark; --bg: #0c0c0e; --ink: #f2f2f2; --dim: rgba(242, 242, 242, .68); --line: rgba(242, 242, 242, .14); }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ background: var(--bg); color: var(--ink); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; padding: clamp(28px, 5vw, 72px) clamp(16px, 4vw, 64px); }}
  header {{ max-width: 1500px; margin: 0 auto 44px; }}
  h1 {{ font-size: clamp(34px, 5vw, 64px); line-height: 1.02; letter-spacing: -.03em; font-weight: 650; }}
  header p {{ color: var(--dim); max-width: 62ch; margin-top: 14px; font-size: 18px; }}
  code {{ font: 14px ui-monospace, monospace; background: rgba(255, 255, 255, .08); padding: 2px 6px; border-radius: 5px; }}
  .grid {{ max-width: 1500px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(330px, 100%), 1fr)); gap: 22px; }}
  .card {{ display: flex; flex-direction: column; color: inherit; text-decoration: none; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; background: #141417; transition: transform .3s, border-color .3s; }}
  .card:hover {{ transform: translateY(-4px); border-color: rgba(242, 242, 242, .4); }}
  .card img {{ width: 100%; height: auto; aspect-ratio: 16 / 10; object-fit: cover; display: block; background: #000; }}
  .t {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 16px 18px 4px; }}
  .t b {{ font-size: 19px; font-weight: 600; }}
  .t small {{ font: 12px ui-monospace, monospace; color: var(--dim); white-space: nowrap; }}
  .d {{ padding: 0 18px 18px; color: var(--dim); font-size: 14.5px; }}
  footer {{ max-width: 1500px; margin: 48px auto 0; color: var(--dim); font-size: 14px; }}
  a {{ color: inherit; }}
</style></head><body>
<header><h1>One spec, {len(names)} experiences.</h1>
<p>Every page below is the same <code>site.yaml</code> ({_html.escape(site.name)}), built by Scroll Studio with a different
<code>theme: {{ style: ... }}</code>. Each style is its own experience: a different scroll mechanic, layout and set of transitions, not a recolour. Open one, then use the arrows at the bottom (or your arrow keys) to flip through them all.</p></header>
<main class="grid">
{cards}
</main>
<footer><a href="../">Back to {_html.escape(site.name)}</a> · Made with <a href="https://github.com/Okohedeki/scroll-studio">Scroll Studio</a></footer>
</body></html>
""", encoding="utf-8")
    typer.echo(f"looks -> {root / 'index.html'}")


copy_app = typer.Typer(help="A copy deck for clients: export every piece of text to Markdown, import their edits.")
app.add_typer(copy_app, name="copy")


@copy_app.command("export")
def copy_export(name: str, out: Optional[Path] = typer.Option(None, help="Default: <project>/copy.md")):
    """Write the site's text to a Markdown copy deck."""
    from .brand import export_deck
    from .project import Project
    project = Project(resolve(name))
    out = out or project.root / "copy.md"
    out.write_text(export_deck(project), encoding="utf-8")
    typer.echo(f"copy deck -> {out}")


@copy_app.command("import")
def copy_import(name: str, deck: Path, dry_run: bool = typer.Option(False, help="Show the changes without writing")):
    """Apply an edited copy deck to site.yaml (comments kept; an invalid result is refused)."""
    from .brand import import_deck
    from .project import Project
    changes = import_deck(Project(resolve(name)), deck.read_text(encoding="utf-8"), dry_run=dry_run)
    for k, old, new in changes:
        typer.echo(f"  {k}\n    - {old}\n    + {new}")
    typer.echo(f"{len(changes)} field(s) changed" + (" (dry run, nothing written)" if dry_run else "; run studio build to update the site"))


@app.command()
def brand(name: str, logo: Optional[str] = typer.Option(None, help="Logo file inside the project (png, svg rendered as png, jpg)"),
          mode: str = typer.Option("light", help="light or dark"), dry_run: bool = False,
          from_: Optional[str] = typer.Option(None, "--from", help="Read a brand from a web page URL, a saved .html page, "
                                                                   "a logo image or a brand.yaml, and write its tokens "
                                                                   "into site.yaml as theme.from")):
    """Set the theme's colours from a logo (contrast-checked) and use it as the nav logo, or (--from) write a brand's
    colours, fonts, radius and logo into theme.from, where they can be edited."""
    from .brand import apply_brand, write_brand
    from .project import BuildError, Project
    if (logo is None) == (from_ is None):
        raise typer.BadParameter("give --logo or --from")
    if from_ is not None:
        try:
            t = write_brand(Project(resolve(name)), from_, dry_run=dry_run, log=typer.echo)
        except BuildError as e:
            raise typer.BadParameter(str(e)) from None
        for group in ("colors", "fonts"):
            for k, v in t.get(group, {}).items():
                typer.echo(f"  {group}.{k}: {v}")
        for k in ("mode", "radius", "logo"):
            if t.get(k):
                typer.echo(f"  {k}: {t[k]}")
        typer.echo("written to theme.from" + (" (dry run)" if dry_run else ""))
        return
    if mode not in ("light", "dark"):
        raise typer.BadParameter("mode is light or dark")
    r = apply_brand(Project(resolve(name)), logo, mode=mode, dry_run=dry_run)
    typer.echo("logo palette: " + " ".join(r["palette"]))
    for k, v in r["colors"].items():
        typer.echo(f"  {k}: {v}")
    typer.echo("written to theme.colors" + (" (dry run)" if dry_run else ""))


# ---- frozen beats: deep zoom + layered depth (engine/zoom.py, engine/layers.py, engine/zoom_report.py) ---------------

@app.command("freeze")
def freeze_cmd(name: str, beat: str,
               plan: bool = typer.Option(False, "--plan", help="Print the deep-zoom tile plan (levels, tiles, boxes) and stop: "
                                                               "no ComfyUI, no GPU"),
               report: bool = typer.Option(False, "--report", help="After rendering, measure the clip: sharpness at each zoom "
                                                                   "the camera reaches, a frame-difference plot (pops), a "
                                                                   "frame strip; written beside the clip"),
               against: Optional[str] = typer.Option(None, help="--report: another frozen beat to measure alongside (the "
                                                                "same camera without detail, say)")):
    """Render one frozen-moment beat (deep zoom and layers included), or print its tile plan, or measure its clip."""
    from . import freeze_beats as fb
    from .project import Project
    project = Project(resolve(name))
    sec, b = fb.find_beat(project, beat)
    if b.freeze is None:
        raise typer.BadParameter(f"beat '{beat}' is not a frozen moment")
    f = b.freeze
    if plan:
        from .backends import upscale as up
        from . import zoom_build
        if f.detail is None:
            raise typer.BadParameter("this beat has no `detail:`: there is no tile plan")
        size = fb.beat_size(sec)
        tiles, sizes, ratio, tsize = zoom_build.make_plan(f, b.seconds, up.target_size(size, max(1.0, f.upscale))[0], size)
        typer.echo(f"{len(tiles)} tiles in {len(sizes)} levels, x{ratio:.2f} detail per level, tiles {tsize[0]}x{tsize[1]}")
        for k, w in enumerate(sizes, start=1):
            mine = [t for t in tiles if t.level == k]
            typer.echo(f"  level {k}: tiles {w:.3f} of the frame wide ({w * size[0] * max(1.0, f.upscale):.0f} frame px), {len(mine)} tile(s)")
            for t in mine:
                typer.echo("    [" + ", ".join(f"{v:.3f}" for v in t.box) + "]")
        return
    clip = fb.render_beat(project, sec, b, typer.echo)
    typer.echo(f"clip: {clip}")
    if report:
        from . import zoom_report
        others = {}
        if against:
            osec, ob = fb.find_beat(project, against)
            others[against] = fb.beat_clip_path(project, osec, ob)
        zoom_report.report(clip, fb.camera_keys(f), "linear" if f.move is not None else f.ease, clip.parent / "report",
                           name=beat, others=others, log=typer.echo)
        typer.echo(f"report: {clip.parent / 'report'}")


@app.command()
def preview(name: str, port: int = 5173):
    """Serve a built project locally."""
    from .serve import serve
    root = resolve(name) / "dist"
    if not (root / "index.html").exists():
        raise typer.BadParameter("not built yet: run `studio build` first")
    serve(root, port)


@app.command()
def record(name: str, section: Optional[str] = None, seconds: float = 12.0, out: Optional[Path] = None,
           gif: bool = False, width: int = 1920, height: int = 1080, out_width: Optional[int] = None,
           poster_at: float = typer.Option(0.5, help="Where in the recording (0-1) to take the poster JPG"),
           pointer: Optional[str] = typer.Option(None, "--pointer", help="Move the mouse while recording, for pictures "
                                                 "that follow it (`pointer:` lenses and lights): 'wander' for a slow tour "
                                                 "of the frame, or waypoints 'x,y x,y ...' in 0-1 of the viewport"),
           cursor: bool = typer.Option(True, "--cursor/--no-cursor", help="With --pointer: draw a small ring where the "
                                                                         "pointer is (headless frames have no cursor)")):
    """Record a scroll-through to MP4 (for README, social posts, Reddit)."""
    from .project import BuildError
    from .record import parse_pointer, record as rec
    root = resolve(name)
    out = out or root / "recordings" / f"{section or 'page'}.mp4"
    try:
        path = parse_pointer(pointer)
    except BuildError as e:
        raise typer.BadParameter(str(e))
    rec(root / "dist", out, section=section, size=(width, height), seconds=seconds, gif=gif, out_width=out_width,
        poster_at=poster_at, pointer=path, cursor=cursor)


@app.command()
def inspect(name: str, section: Optional[str] = typer.Option(None, help="Film section to inspect (default: every film section "
                                                                        "that has a built film)"),
            video: Optional[Path] = typer.Option(None, "--video", help="Inspect any video file as one shot instead (a screen "
                                                                     "recording, a clip)"),
            as_json: bool = typer.Option(False, "--json", help="Print the report as JSON and nothing else"),
            force: bool = typer.Option(False, "--force", help="Measure again even if the film has not changed"),
            embed: bool = typer.Option(False, "--embed", help="Also measure style drift with a local CLIP embedding "
                                                              "(OpenCLIP ViT-H/14 from the Hugging Face cache, CPU, slow; "
                                                              "nothing is downloaded)"),
            open_: bool = typer.Option(False, "--open", help="Open the HTML report when done"),
            page: bool = typer.Option(False, "--page", help="Check the built page instead of its films: screenshots at "
                                                           "desktop and phone size (headless Chromium, reduced motion), "
                                                           "text over pictures, type, pictures and layout, per section; "
                                                           "exits 1 when anything fails. --section limits it to one section")):
    """Polish report for a built film (beats, a take or a video): scores it second by second and beat by beat for pops
    (jumps, flicker, judder and crossfades that do not line up), softness (looks upscaled), halos (rims and double edges),
    style drift (the look moving away from the section's start) and morphs (shapes rebuilding instead of moving). Writes
    <project>/.build/inspect/<section>.json and .html (the worst moments with pictures and a line saying what is wrong);
    the storyboard editor shows each beat's worst problem. CPU only; unchanged films are answered from the saved report.

    With --page it checks the built page instead (see the guide, "Check a page before you ship it"): the report is
    <project>/.build/inspect/page/report.json with a contact sheet per screen size, and the exit code is 1 when a check
    fails, so a showcase page can be gated on it."""
    import json as _json
    import sys
    from . import polish
    from .project import Project
    project = Project(resolve(name))
    log = (lambda m: typer.echo(m, err=True)) if as_json else typer.echo
    if page:
        from .polish import page as page_check
        try:
            r = page_check.inspect_page(project, only=section, log=log)
        except polish.Nothing as e:
            raise typer.BadParameter(str(e))
        out = _json.dumps(r, indent=1, default=float) if as_json else page_check.table(r)
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"          # page text may hold characters a console cannot show
        typer.echo(out.encode(enc, "replace").decode(enc))
        if open_:
            import webbrowser
            webbrowser.open((Path(r["folder"]) / next(iter(r["sheets"].values()))).as_uri())
        raise typer.Exit(1 if r["summary"]["fails"] else 0)
    try:
        reports = ([polish.inspect_video(project, str(video), force=force, embed=embed, log=log)] if video
                   else polish.inspect_project(project, section, force=force, embed=embed, log=log))
    except polish.Nothing as e:
        raise typer.BadParameter(str(e))
    if not reports:
        raise typer.BadParameter("nothing to inspect: no film section with a built film (run `studio build` first)")
    if as_json:
        sys.stdout.write(_json.dumps(reports[0] if len(reports) == 1 else reports, indent=1, default=float) + "\n")
        return
    for r in reports:
        _, html = polish.report_path(project, r["section"])
        s = r["summary"]
        typer.echo(f"\n{r['section']}: {s['verdict']}: {s['issues']} problem(s)"
                   + (f" ({s['counts']['bad']} bad, {s['counts']['visible']} visible, {s['counts']['slight']} slight)" if s["issues"] else "")
                   + ("  [saved report, film unchanged]" if r.get("cached") else ""))
        for x in r["issues"][:8]:
            typer.echo(f"  {x['level']:8} {x['metric']:8} {x['t0']:6.1f}-{x['t1']:.1f}s  {x['beat']}: {x['reason']}")
        if len(r["issues"]) > 8:
            typer.echo(f"  ... {len(r['issues']) - 8} more in the report")
        typer.echo("  beat scores (100 = clean): " + "  ".join(
            f"{b['id']}[{' '.join(str(b['scores'][m]) for m in polish.METRICS)}]" for b in r["beats"]) + f"   order: {' '.join(polish.METRICS)}")
        typer.echo(f"  report: {html}")
    if open_:
        import webbrowser
        webbrowser.open(polish.report_path(project, reports[0]["section"])[1].as_uri())


@app.command()
def previews(names: list[str], out: Path = typer.Option(..., help="Folder for <project>.mp4 + <project>.jpg"),
             seconds: float = 10.0, out_width: int = 1280, poster_at: float = 0.5, skip_existing: bool = True):
    """Preview video + poster for each project's first scene (for galleries and READMEs)."""
    from .project import Project
    from .record import record as rec
    from .spec import is_scene
    out.mkdir(parents=True, exist_ok=True)
    for name in names:
        root = resolve(name)
        dst = out / f"{root.name}.mp4"
        if skip_existing and dst.exists():
            typer.echo(f"skip {root.name} (exists)")
            continue
        site = Project(root).load()
        first = next((s for s in site.sections if is_scene(s)), None)
        # kinetic-type scenes are short; for type-led sites record the whole page instead
        section = first.id if first is not None and first.type != "type" else None
        rec(root / "dist", dst, section=section, seconds=seconds, out_width=out_width, poster_at=poster_at)


@app.command()
def snapshot(name: str, at: list[str] = typer.Option(..., help="scene:progress, top, bottom or y:<px>; repeatable"),
             width: int = 1600, height: int = 900):
    """Screenshots at scroll positions + a contact sheet (snapshots/sheet.jpg)."""
    from .snapshot import snapshot as snap
    root = resolve(name)
    snap(root / "dist", at, root / "snapshots", size=(width, height))
    typer.echo(f"sheet: {root / 'snapshots' / 'sheet.jpg'}")


@app.command()
def cuts(name: str, strip: bool = typer.Option(False, "--strip", help="Frame strips around each cut of the built site "
                                                                      "(<project>/.build/cuts/cut_<n>.jpg)"),
         only: Optional[str] = typer.Option(None, help="Comma-separated cut numbers (default: all)"),
         mobile: bool = typer.Option(False, "--mobile", help="Strips at a phone's size (390x844)"),
         reduced: bool = typer.Option(False, "--reduced-motion", help="Strips with prefers-reduced-motion on (the cuts "
                                                                      "fall back to plain cuts)"),
         frames: int = typer.Option(9, help="Frames in each strip"),
         clip: bool = typer.Option(False, "--clip", help="With --strip: also a short video of each cut (cut_<n>.mp4)")):
    """The film grammar between a built site's sections (`transition:`): each cut, how long it is, the shapes a match
    cut found; with --strip, a frame strip around each one to look at."""
    from . import cuts as cuts_mod
    root = resolve(name)
    found = cuts_mod.read_cuts(root / "dist")
    if not found:
        typer.echo("no cuts in the built page (add `transition:` to a section and build)")
        raise typer.Exit()
    for c in found:
        line = f"  {c['n']}: {c['label']}  {c['type']}, {c['length']} screens"
        if c["type"] == "match":
            a = (c.get("anchors") or {})
            line += "  shapes: " + (", ".join(f"{k}={v.get('how') or 'selector'}" for k, v in a.items() if isinstance(v, dict)) or "none found (dissolves)")
        typer.echo(line)
    if strip:
        ids = [int(x) for x in only.split(",")] if only else None
        size = (390, 844) if mobile else (1280, 720)
        cuts_mod.strips(root / "dist", root / ".build" / "cuts", only=ids, size=size, mobile=mobile, frames=frames,
                        reduced=reduced, clip=clip, log=typer.echo)
        typer.echo(f"strips: {root / '.build' / 'cuts'}")


@app.command()
def poster(name: str, at: str = typer.Option(..., help="scene:progress (e.g. studio:0.88), top, bottom or y:<px>"),
           out: Path = typer.Option(..., help="JPG to write"), width: int = 1280):
    """A poster JPG of a built site at one scroll position (screenshot -> FFmpeg -> JPG)."""
    import tempfile
    from .project import ffmpeg
    from .snapshot import snapshot as snap
    root = resolve(name)
    with tempfile.TemporaryDirectory() as tmp:
        shot = snap(root / "dist", [at], Path(tmp), log=lambda m: None)[0]
        out.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-i", shot, "-vf", f"scale={width}:-2:flags=lanczos", "-q:v", "3", out)
    typer.echo(f"poster -> {out}")


@app.command()
def publish(names: list[str], out: Path = typer.Option(..., help="Folder to deploy (e.g. a GitHub Pages repo)"),
            home: Optional[str] = typer.Option(None, help="Project whose page becomes the folder's index.html")):
    """Assemble built projects into one static folder: out/<project>/... ready for GitHub Pages or any host.

    Cross-links between projects written as ../<project>/dist/ (how the showcase gallery links locally) are
    rewritten to ../<project>/. A .nojekyll file keeps GitHub Pages from dropping folders that start with _.
    """
    import re as _re
    roots = [resolve(n) for n in names]
    for r in roots:
        if not (r / "dist" / "index.html").exists():
            raise typer.BadParameter(f"{r.name} is not built: run studio build first")
    out.mkdir(parents=True, exist_ok=True)
    # Any sibling project, not just the ones in this call: republishing one site must not break its links
    # to sites published earlier.
    pattern = _re.compile(r"\.\./([A-Za-z0-9_.-]+)/dist/")
    linked: set[str] = set()
    for r in roots:
        dst = out / r.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(r / "dist", dst)
        for html in dst.rglob("*.html"):
            text = html.read_text(encoding="utf-8")
            linked.update(m.group(1) for m in pattern.finditer(text))
            new = pattern.sub(lambda m: f"../{m.group(1)}/", text)
            if new != text:
                html.write_text(new, encoding="utf-8")
        typer.echo(f"  {r.name}/")
    for name in sorted(linked):
        if not (out / name / "index.html").exists():
            typer.echo(f"  warning: pages link to {name}/, which is not in {out}: publish it too")
    (out / ".nojekyll").write_text("")
    if home:
        # The folder's root serves the home page itself (not a redirect), so visitors, link previews and
        # text-only readers all get the real content. <base> makes its relative links and assets resolve
        # inside the home project's folder.
        if not (out / home / "index.html").exists():
            raise typer.BadParameter(f"--home {home} is not in {out}: publish it too")
        page = (out / home / "index.html").read_text(encoding="utf-8")
        page = _re.sub(r"<head>", f'<head>\n<base href="{home}/">', page, count=1)
        (out / "index.html").write_text(page, encoding="utf-8")
    typer.echo(f"published {len(roots)} site(s) to {out}")


@app.command()
def combine(videos: list[Path], out: Path = typer.Option(..., help="MP4 to write"),
            fade: float = typer.Option(0.6, help="Crossfade between clips, seconds")):
    """Join recordings into one video with crossfades (e.g. a reel of several sites)."""
    from .project import ffmpeg, probe
    if len(videos) < 2:
        raise typer.BadParameter("give at least two videos")
    durs = [float(probe(v)["duration"]) for v in videos]
    w, h = int(probe(videos[0])["width"]), int(probe(videos[0])["height"])
    inputs, chains, last, offset = [], [], "[v0]", 0.0
    for i, v in enumerate(videos):
        inputs += ["-i", str(v)]
        chains.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,format=yuv420p[v{i}]")
    for i in range(1, len(videos)):
        offset += durs[i - 1] - fade
        chains.append(f"{last}[v{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[x{i}]")
        last = f"[x{i}]"
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg(*inputs, "-filter_complex", ";".join(chains), "-map", last, "-c:v", "libx264", "-crf", "18", "-preset", "slow",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out))
    typer.echo(f"-> {out} ({sum(durs) - fade * (len(videos) - 1):.1f}s)")


# ---------------------------------------------------------------- product (site.product)

@app.command()
def product(name: str, parts: bool = typer.Option(False, "--parts", help="List the model's parts and materials (names to target in product.parts)"),
            still: Optional[str] = typer.Option(None, help="Render a still: front, three-quarter, side, top, back, hero-low, exploded, detail"),
            part: Optional[str] = typer.Option(None, help="detail (or any view): glob on the part to frame"),
            size: str = typer.Option("1600x1200", help="Still size WxH"),
            background: str = typer.Option("transparent", help="transparent, theme or a hex colour"),
            scene: Optional[str] = typer.Option(None, help="Render the still into a generated scene (prompt; needs ComfyUI)"),
            out: Optional[Path] = typer.Option(None, help="Copy the still here"),
            exposure: float = typer.Option(0.0, help="Exposure in stops"),
            all_parts: bool = typer.Option(False, "--all", help="With --parts: every part, not grouped by name")):
    """The site's product: normalise its model (cached), list its parts, render stills."""
    import re as _re
    from . import product as prod
    from .project import Project
    project = Project(resolve(name))
    info = prod.product_info(project, log=typer.echo)
    sx, sy, sz = info["size"]
    typer.echo(f"{project.load().product.name}: {sx * 1000:.1f} x {sy * 1000:.1f} x {sz * 1000:.1f} mm (w x d x h), "
               f"{info['triangles']:,} triangles{' (decimated from ' + format(info['source_triangles'], ',') + ')' if info['decimated'] else ''}, "
               f"{len(info['parts'])} parts, units {info['units']}, up {info['up']}")
    typer.echo(f"  GLB: {prod.normalised_glb(project)}")
    if parts:
        groups: dict = {}
        for p in info["parts"]:
            key = p["name"] if all_parts else _re.sub(r"(\.\d{3}|:\d+)+$", "", p["name"])
            g = groups.setdefault(key, {"n": 0, "tris": 0, "mats": [], "size": p["size"], "path": p["path"]})
            g["n"] += 1
            g["tris"] += p["triangles"]
            for m in p["materials"]:
                if m not in g["mats"]:
                    g["mats"].append(m)
        typer.echo("")
        typer.echo(f"  {'part':<38} {'count':>5} {'triangles':>10}  {'size mm':<20} materials")
        for k, g in sorted(groups.items(), key=lambda kv: -max(kv[1]["size"])):
            dims = "x".join(f"{v * 1000:.0f}" for v in g["size"])
            mats = ", ".join(f"{m['name']} {m['color'] or ''}".strip() for m in g["mats"][:4]) + (" ..." if len(g["mats"]) > 4 else "")
            typer.echo(f"  {k[:38]:<38} {g['n']:>5} {g['tris']:>10,}  {dims:<20} {mats}")
        parents = sorted({p["path"].rsplit("/", 1)[0] for p in info["parts"] if "/" in p["path"]})
        if parents:
            typer.echo("")
            typer.echo(f"  assemblies (a match on one covers its parts): {', '.join(parents[:25])}{' ...' if len(parents) > 25 else ''}")
        for r in info.get("rules", []):
            typer.echo(f"  rule match={r['match']!r}{' material=' + repr(r['material']) if r['material'] else ''}: {r['hits']} mesh(es)")
    if still:
        w, h = (int(v) for v in size.lower().split("x"))
        if scene:
            from .spec import ImageInput, ProductShot
            path = prod.image_still(project, ImageInput(product=ProductShot(view=still, part=part, scene=scene, exposure=exposure,
                                    background=background), size=(w, h)), typer.echo, alpha=background == "transparent")
        else:
            path = prod.product_still(project, None, still, (w, h), background, typer.echo, part=part, exposure=exposure)
        if out:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, out)
            path = out
        typer.echo(f"still -> {path}")


@app.command()
def inside(name: str, section: Optional[str] = typer.Option(None, help="The `type: inside` section (when the site has several)"),
           still: Optional[str] = typer.Option(None, help="Render stills: stop numbers (1,3), `all` for every stop, `wide` for the opening shot"),
           strip: int = typer.Option(0, help="Render this many frames spaced evenly along the whole route"),
           samples: int = typer.Option(24, help="Cycles samples for the stills"),
           scale: float = typer.Option(0.5, help="Still size as a fraction of the scene's frame size"),
           out: Optional[Path] = typer.Option(None, help="Contact sheet of the stills (default: <project>/inside_<section>.jpg)")):
    """The product as the set: print the route (which parts each stop found, how the camera comes in, where the copy
    sits on the scroll) and render quick stills of stops or a strip along the route, with a contact sheet."""
    from .project import BuildError, Project
    from .scenes import inside as ins
    project = Project(resolve(name))
    sec = ins.find_section(project, section)
    try:
        info, glb, res, plan = ins.route(sec, project, typer.echo)
    except BuildError as e:
        typer.echo(str(e))
        raise typer.Exit(1)
    typer.echo(f"{sec.id}: {len(res.stops)} stops, {plan.screens:.1f} screens of scroll, {len(plan.frames)} frames")
    for n in plan.notes:
        typer.echo(f"  {n}")
    for s, w in zip(res.stops, plan.windows):
        d = s.describe()
        parts = ", ".join(d["parts"][:4]) + (f" +{d['matched'] - 4} more" if d["matched"] > 4 else "")
        typer.echo(f"  {s.index + 1}. {s.label}  [{d['pattern']}]  {d['matched']} part(s): {parts}")
        typer.echo(f"       view {d['span_mm']} mm wide, {s.lens:g} mm f/{s.fstop:g}, from yaw {d['from']['yaw']} pitch {d['from']['pitch']}, "
                   f"{d['distance_mm']} mm away; rests p {w['arrive']:.3f}-{w['leave']:.3f}, copy p {w['copy'][0]:.3f}-{w['copy'][1]:.3f}")
    shown = [st for st in sec.steps]
    if shown:
        typer.echo(f"  copy: {len(shown)} step(s), {len([x for x in shown if x.intro])} intro; steps without `at` are placed on the route")
    picks: list[int] = []
    if still:
        for tok in [t.strip() for t in still.split(",") if t.strip()]:
            if tok == "wide":
                picks.append(0 if sec.establish else plan.windows[0]["frame"])
            elif tok == "all":
                picks += [w["frame"] for w in plan.windows]
            else:
                i = int(tok)
                if not 1 <= i <= len(plan.windows):
                    raise typer.BadParameter(f"stop {i}: the route has {len(plan.windows)} stops")
                picks.append(plan.windows[i - 1]["frame"])
    if strip:
        n = len(plan.frames)
        picks += sorted({round(i * (n - 1) / max(strip - 1, 1)) for i in range(strip)})
    if picks:
        sheet = out or (project.root / f"inside_{sec.id}.jpg")
        try:
            paths = ins.preview(project, sec, picks, samples, scale, typer.echo, sheet)
        except BuildError as e:
            typer.echo(str(e))
            raise typer.Exit(1)
        for k, p in zip(picks, paths):
            typer.echo(f"  frame {k + 1}: {p}")
        typer.echo(f"contact sheet -> {sheet}")


@app.command()
def trailer(name: str, format: Optional[str] = typer.Option(None, help="16x9 or 9x16 (default: trailer.formats)"),
            force: bool = typer.Option(False, help="Ignore the cache"),
            plan: bool = typer.Option(False, help="Print the cut and stop")):
    """Cut a launch trailer from the site's own renders: dist/trailer/trailer-16x9.mp4 and trailer-9x16.mp4."""
    from .project import Project
    from .trailer import build_trailer, plan_only
    project = Project(resolve(name))
    if plan:
        plan_only(project)
        return
    res = build_trailer(project, formats=[format] if format else None, force=force)
    for fmt, v in res["videos"].items():
        typer.echo(f"{fmt}: {v}")


@app.command()
def camera(name: str, beat: str,
           guide: bool = typer.Option(False, "--guide", help="Only make the camera guide (depth, people mask, the guide videos) and print "
                                                             "where it is: guide_rgb.mp4 is a pure-camera preview of the keyed move"),
           check: bool = typer.Option(False, "--check", help="Measure the beat's rendered frames: does the camera follow its keys, do the "
                                                             "people still move? Writes camera.json beside the beat's frames"),
           section: Optional[str] = typer.Option(None, help="The film section, when the beat id is in more than one")):
    """Keyed camera moves on a moving beat (`camera:` on a beat): preview the guide, or measure how well the render follows the keys."""
    from . import camera_beats as cb
    from .project import Project
    project = Project(resolve(name))
    if not (guide or check):
        raise typer.BadParameter("use --guide or --check (the beat itself is made by `studio build --only <beat>`)")
    if guide:
        r = cb.guide_only(project, beat, section, typer.echo)
        typer.echo(json.dumps(r, indent=1))
    if check:
        r = cb.check(project, beat, section, typer.echo)
        c, f = r["camera"], r["floor"]
        typer.echo(f"{r['beat']} ({r['backend']}, {r['frames']} frames): camera zoom error rms {c['zoom_rms']:.1f}% (max {c['zoom_max']:.1f}%), "
                   f"shift rms {c['shift_rms']:.3f} view widths (max {c['shift_max']:.3f}), {c['lost']} frames not registered; "
                   f"measurement floor {f['zoom_rms']:.2f}% / {f['shift_rms']:.3f}")
        if "people" in r:
            p, pf = r["people"], r["people_floor"]
            typer.echo(f"  people: {p['people_end_px']:.1f} px from where they stood at the start by the end of the beat "
                       f"(static world {p['static_end_px']:.1f} px; a frozen picture under the same camera {pf['people_end_px']:.1f} px; "
                       f"frame is {p['width']} px wide)")
        typer.echo(f"  sheet: {r.get('sheet')}")


@app.command("diorama")
def diorama_cmd(name: str, section: Optional[str] = typer.Option(None, help="The diorama section (default: the first)"),
                strip: bool = typer.Option(False, "--strip", help="Also take a frame strip of the built site: every place at rest, "
                                                                  "and the lift, orbit and dive between places (dioramas/<id>-strip.jpg)"),
                full: bool = typer.Option(False, "--full", help="Lay the ground out at full resolution (default: draft)")):
    """Miniature worlds: lay a `diorama` section out and say what was decided: the map with the places numbered
    (diorama/<id>-map.jpg), which step lives at which place, where the camera dives from, how far it orbits. Takes a
    couple of seconds and needs no GPU; with --strip it also photographs the built site along the whole scroll."""
    from .compile import themes
    from .diorama import review
    from .project import Project
    from .spec import DioramaScene
    project = Project(resolve(name))
    site = project.load()
    secs = [s for s in site.sections if isinstance(s, DioramaScene) and (section is None or s.id == section)]
    if not secs:
        raise typer.BadParameter("no diorama section" + (f" '{section}'" if section else "") + " in this project")
    sec = secs[0]
    table = sec.look.table or themes.resolve(site.theme)["colors"]["bg"]
    out = project.root / "diorama"
    info = review.write_review(sec, table, out, draft=not full)
    typer.echo(f"{info['world']} world, {info['size']:g} units, {info['props']} props ({', '.join(f'{k} {v}' for k, v in list(info['by_kind'].items())[:6])})")
    for p in info["places"]:
        typer.echo(f"  {p['n']}. {p['name']} ({p['kind']}) at {p['at']}: step {p['step']}, camera azimuth {p['camera_yaw']}, distance {p['camera_distance']}")
    typer.echo(f"  the camera orbits {info['orbit_degrees']} degrees in all; map: {out / (sec.id + '-map.jpg')}")
    if strip:
        from PIL import Image, ImageDraw
        from .diorama.plan import build as layout
        from .snapshot import snapshot as snap
        import tempfile
        if not (project.dist / "index.html").exists():
            raise typer.BadParameter("build the site first (studio build)")
        plan = layout(sec, table, True)[0]
        pts = review.strip_points(plan)
        with tempfile.TemporaryDirectory() as tmp:
            shots = snap(project.dist, [f"{sec.id}:{p}" for _, p in pts], Path(tmp), size=(960, 540), log=lambda m: None)
            cols, tw = 4, 480
            th = round(tw * 540 / 960)
            rows = (len(shots) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
            d = ImageDraw.Draw(sheet)
            for i, ((label, p), f) in enumerate(zip(pts, shots)):
                im = Image.open(f).convert("RGB").resize((tw, th), Image.LANCZOS)
                sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
                d.rectangle(((i % cols) * tw, (i // cols) * th, (i % cols) * tw + 8 + 7 * len(label), (i // cols) * th + 18), fill=(0, 0, 0))
                d.text(((i % cols) * tw + 4, (i // cols) * th + 3), f"{label}  p={p}", fill=(255, 255, 255))
        dest = out / f"{sec.id}-strip.jpg"
        sheet.save(dest, quality=88)
        typer.echo(f"  strip: {dest}")


@app.command("cinemagraph")
def cinemagraph_cmd(name: str,
                    only: Optional[str] = typer.Option(None, help="Only the cinemagraphs whose `moves` or spec path contains this text"),
                    force: bool = typer.Option(False, help="Ignore the cache"),
                    list_only: bool = typer.Option(False, "--list", help="List the cinemagraphs in the spec and their cache state, build nothing"),
                    check: bool = typer.Option(False, "--check", help="Instead of building, measure the BUILT page (dist/) in Chrome: is everything "
                                                                     "but the moving part truly still, does the loop hitch, does reduced motion show the still"),
                    mobile: bool = typer.Option(False, "--mobile", help="With --check: a 390 px phone viewport")):
    """Build the site's cinemagraphs (an image input with `cinemagraph:`: a still where only one thing moves) and report on each:
    the loop's seam, how much of the picture moves, what the page holds still, bytes. Files are in <project>/.build/_cinemagraph/.
    `studio build` makes them too, as part of the page."""
    from . import cinemagraph as cine
    from .project import Project
    project = Project(resolve(name))
    if check:
        from . import cinemagraph_check as chk
        work = project.build / "_cinemagraph" / "page-check"
        res = chk.check_page(project.dist, work, size=(390, 844) if mobile else (1440, 900), mobile=mobile, dpr=1.0, log=typer.echo)
        res["reduced_motion"] = chk.check_reduced(project.dist, log=typer.echo)
        (work / ("mobile.json" if mobile else "desktop.json")).write_text(json.dumps(res, indent=1))
        typer.echo(f"report: {work}")
        return
    site = project.load()
    found = [(w, r) for w, r in cine.collect(site) if not only or only in w or only in r.cinemagraph.moves]
    if not found:
        typer.echo("no image input with `cinemagraph:` in this spec" + (f" matching '{only}'" if only else ""))
        raise typer.Exit(1)
    for where, ref in found:
        typer.echo(f"{where}: {ref.cinemagraph.moves}")
        built = cine.build(project, ref, typer.echo, force=force, site_video_model=site.video_model,
                           site_wan=site.wan.model_dump(mode="json"), only_cached=list_only)
        if built is None:
            typer.echo("  not built yet")
            continue
        typer.echo("  " + cine.summary(built["data"]))
        typer.echo(f"  {built['video']}")


@app.command("world")
def world_cmd(name: str, section: Optional[str] = typer.Option(None, help="The film section (default: every film with in-world type)"),
              frames: int = typer.Option(6, help="Frames drawn on the sheet per title")):
    """Check the in-world type of a built film (steps with `place: {kind: behind | surface | sky}`): draws each title's box
    through the per-frame matrices the page will use on the film's own frames (with the depth map beside them for behind and
    sky type), measures how steady the track is and how much of the time the type is on screen, and says what to change.
    Writes .build/<section>/world/sheet.jpg and report.json: read the sheet."""
    from . import world_report
    from .project import Project
    for r in world_report.check(Project(resolve(name)), section, frames, typer.echo):
        typer.echo(f"  sheet: {r['sheet']}")


@app.command()
def light(name: str, section: Optional[str] = typer.Option(None, help="The light section (default: every one)"),
         build_: bool = typer.Option(True, "--build/--no-build", help="Build the section first (cached stages are skipped)"),
         strips: bool = typer.Option(True, "--strips/--no-strips", help="Screenshot the built page across every transition"),
         frames: int = typer.Option(7, help="Frames per transition strip"),
         presets: bool = typer.Option(False, "--presets", help="List the named times of day and exit")):
    """Light as the scroll (`type: light`): build the section, then write what it made to look at, in
    <project>/light/<section>/: sheet.jpg (every time of day with its drift from the world, raw and aligned), strip_*.jpg (the page
    across each transition, the same scroll positions a viewer passes through) and light.json (drift, edge agreement and
    how far apart neighbouring times are). The drift is how far the editor moved the place, in pixels at 1024 across."""
    from . import light_presets, light_report
    from .project import Project
    if presets:
        for k, p in light_presets.PRESETS.items():
            typer.echo(f"{k:12s} {p['clock']}  haze {p['haze']:.2f}  {'lamps on' if p['lit'] else 'lamps off':9s} {p['prompt'][:70]}")
        return
    project = Project(resolve(name))
    secs = light_report.sections(project, section)
    if not secs:
        raise typer.BadParameter("no light section in this project" + (f" called '{section}'" if section else ""))
    if build_:
        from .compile.compiler import build_site
        build_site(project, log=typer.echo, only=[s.id for s in secs])
    for sec in secs:
        out = project.root / "light" / sec.id
        out.mkdir(parents=True, exist_ok=True)
        sheet = light_report.times_sheet(project, sec, out)
        rep = json.loads((project.build / sec.id / "report.json").read_text())
        rep.update(light_report.sequence_diff(project, sec))
        (out / "light.json").write_text(json.dumps(rep, indent=1))
        typer.echo(f"[{sec.id}] times: {sheet}")
        for t in rep["times"]:
            al, raw = t["aligned"], t["raw"]
            typer.echo(f"  {t['id']:12s} {t['clock']}  drift {raw['drift']:5.2f}px raw -> {al['drift']:4.2f} aligned   edges {raw['edges']:.2f} -> {al['edges']:.2f}"
                       + ("" if t.get("ok", True) else "   (still drifting)"))
        for p in rep["pairs"]:
            typer.echo(f"  {p['from']} > {p['to']}: light step {p['luma_step']:.3f}, structure agreement {p['edges']:.2f}")
        if strips:
            light_report.strips(project, sec, out, frames=frames, log=typer.echo)
        typer.echo(f"[{sec.id}] report: {out / 'light.json'}")


@app.command("journey")
def journey_cmd(name: str, section: Optional[str] = typer.Option(None, help="The film section, when there is more than one journey"),
                as_json: bool = typer.Option(False, "--json", help="Print the report as JSON")):
    """The one-take page (`journey:` on a film): its approach, every move and hold with the film seconds and scroll they get,
    and, once built, where each stop's blocks sit on its picture and the contrast they reach."""
    from . import journey as jy
    from .project import Project
    rep = jy.report(Project(resolve(name)), section)
    if as_json:
        typer.echo(json.dumps(rep, indent=1))
        return
    for r in rep:
        typer.echo(f"{r['section']}: {r['approach']}, {r['film_seconds']} s of film, {r['scroll_screens']} screens of scroll")
        for g in r["segments"]:
            where = r["placed"].get(g["stop"]) if g["kind"] == "hold" else None
            extra = f"  blocks: {', '.join(g['blocks']) or 'none'}" + (f"; on the {where['side']}, {where['surface']} surface, "
                                                                        f"scrim {where['scrim']}, contrast {where['contrast']}" if where else "") if g["kind"] == "hold" else ""
            typer.echo(f"  {g['segment']:<22} {g['kind']:<5} {g['film_seconds']:>5.1f} s  {g['scroll_screens']:>5.2f} screens{extra}")


@app.command()
def schema():
    """Print the site.yaml JSON Schema."""
    from .spec import Site
    typer.echo(json.dumps(Site.model_json_schema(), indent=2))


@app.command()
def doctor(verify: bool = typer.Option(False, help="Also hash the model files in ComfyUI's folder against engine/models.yaml (slow)")):
    """Check the toolchain and report what each scene type needs."""
    from .doctor import report
    report(verify=verify)


@app.command("setup-comfy")
def setup_comfy(no_weights: bool = typer.Option(False, help="Skip the GFPGAN face-restore weights (~330 MB)")):
    """Install the ComfyUI custom nodes that `reveal` (scroll-driven colour) and `faces: restore` use."""
    from .backends.comfy_setup import install
    install(typer.echo, weights=not no_weights)


@app.command()
def ui(port: int = 5180, no_open: bool = typer.Option(False, help="Don't open a browser")):
    """Start the Studio app."""
    import uvicorn
    if not no_open:
        import threading, webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run("engine.server.app:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    app()
