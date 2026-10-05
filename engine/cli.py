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
def preview(name: str, port: int = 5173):
    """Serve a built project locally."""
    from .serve import serve
    root = resolve(name) / "dist"
    if not (root / "index.html").exists():
        raise typer.BadParameter("not built yet: run `studio build` first")
    serve(root, port)


@app.command()
def record(name: str, section: Optional[str] = None, seconds: float = 12.0, out: Optional[Path] = None,
           gif: bool = False, width: int = 1920, height: int = 1080):
    """Record a scroll-through to MP4 (for README, social posts, Reddit)."""
    from .record import record as rec
    root = resolve(name)
    out = out or root / "recordings" / f"{section or 'page'}.mp4"
    rec(root / "dist", out, section=section, size=(width, height), seconds=seconds, gif=gif)


@app.command()
def snapshot(name: str, at: list[str] = typer.Option(..., help="scene:progress, top, bottom or y:<px>; repeatable"),
             width: int = 1600, height: int = 900):
    """Screenshots at scroll positions + a contact sheet (snapshots/sheet.jpg)."""
    from .snapshot import snapshot as snap
    root = resolve(name)
    snap(root / "dist", at, root / "snapshots", size=(width, height))
    typer.echo(f"sheet: {root / 'snapshots' / 'sheet.jpg'}")


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
