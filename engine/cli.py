"""`studio` command line.

  studio new my-site [--example lodestar-orbital]   create projects/my-site (from an example or a starter)
  studio build my-site [--section hero] [--force] [--draft]
  studio preview my-site [--port 5173]
  studio record my-site [--section hero] [--seconds 12] [--gif]
  studio ui                                         the Studio app (http://localhost:5180)
  studio doctor                                     check Python, Node, FFmpeg, Blender, GPU, ComfyUI, models
  studio schema                                     JSON Schema of site.yaml
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import typer

from .config import ROOT, settings

app = typer.Typer(add_completion=False, help="Scroll Studio: build scroll-driven sites from any inputs.")

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


def resolve(name: str) -> Path:
    from .project import Project
    for cand in (Path(name), Path(settings()["projects"]) / name, ROOT / "examples" / name):
        if (cand / "site.yaml").exists():
            return cand.resolve()
    raise typer.BadParameter(f"no project '{name}' (looked in ., {settings()['projects']}, examples/)")


@app.command()
def new(name: str, example: Optional[str] = typer.Option(None, help="Copy an example from examples/")):
    """Create a project."""
    dst = Path(settings()["projects"]) / name
    if dst.exists():
        raise typer.BadParameter(f"{dst} already exists")
    if example:
        src = ROOT / "examples" / example
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".build", "dist"))
    else:
        (dst / "inputs").mkdir(parents=True)
        (dst / "site.yaml").write_text(STARTER, encoding="utf-8")
    typer.echo(f"created {dst}\nnext: studio build {name} && studio preview {name}")


@app.command()
def build(name: str, section: Optional[str] = typer.Option(None, help="Rebuild one scene only"),
          force: bool = typer.Option(False, help="Ignore the cache"),
          draft: bool = typer.Option(False, help="Fast low-quality renders where supported")):
    """Build a project into dist/."""
    from .compile.compiler import build_site
    from .project import Project
    out = build_site(Project(resolve(name)), only=section, force=force, options={"draft": draft})
    typer.echo(f"built {out}")


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
<title>{_html.escape(site.name)}: {len(names)} looks</title>
<meta name="description" content="One site spec built in {len(names)} styles with Scroll Studio.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23f2f2f2'/%3E%3Ctext x='16' y='22.5' text-anchor='middle' font-family='system-ui' font-size='18' font-weight='700' fill='%230c0c0e'%3E20%3C/text%3E%3C/svg%3E">
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
<header><h1>One spec, {len(names)} looks.</h1>
<p>Every page below is the same <code>site.yaml</code> ({_html.escape(site.name)}), built by Scroll Studio with a different
<code>theme: {{ style: ... }}</code>. Open one, then use the arrows at the bottom (or your arrow keys) to flip through them all.</p></header>
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
def brand(name: str, logo: str = typer.Option(..., help="Logo file inside the project (png, svg rendered as png, jpg)"),
          mode: str = typer.Option("light", help="light or dark"), dry_run: bool = False):
    """Set the theme's colours from a logo (contrast-checked) and use it as the nav logo."""
    from .brand import apply_brand
    from .project import Project
    if mode not in ("light", "dark"):
        raise typer.BadParameter("mode is light or dark")
    r = apply_brand(Project(resolve(name)), logo, mode=mode, dry_run=dry_run)
    typer.echo("logo palette: " + " ".join(r["palette"]))
    for k, v in r["colors"].items():
        typer.echo(f"  {k}: {v}")
    typer.echo("written to theme.colors" + (" (dry run)" if dry_run else ""))


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
           poster_at: float = typer.Option(0.5, help="Where in the recording (0-1) to take the poster JPG")):
    """Record a scroll-through to MP4 (for README, social posts, Reddit)."""
    from .record import record as rec
    root = resolve(name)
    out = out or root / "recordings" / f"{section or 'page'}.mp4"
    rec(root / "dist", out, section=section, size=(width, height), seconds=seconds, gif=gif, out_width=out_width, poster_at=poster_at)


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


@app.command()
def schema():
    """Print the site.yaml JSON Schema."""
    from .spec import Site
    typer.echo(json.dumps(Site.model_json_schema(), indent=2))


@app.command()
def doctor():
    """Check the toolchain and report what each scene type needs."""
    from .doctor import report
    report()


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
