"""MCP server: lets Claude (Claude Code, Claude Desktop, any MCP client) build scroll sites with the engine.

  python -m engine.mcp_server          (registered for Claude Code in .mcp.json at the repo root)

Long jobs (renders, recordings) run in the background: start them, then poll `job_status`.
`snapshot` returns screenshot paths so Claude can look at its own work and iterate.
"""

import contextlib
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from .config import ROOT, settings
from .project import Project
from .server.jobs import JobQueue, logger
from .spec import SCENE_TYPES, Site

mcp = FastMCP("scroll-studio")


class _Jobs(JobQueue):
    """stdout is the MCP channel: anything a job prints goes to stderr instead."""
    def submit(self, kind, project, label, fn):
        def quiet(job):
            with contextlib.redirect_stdout(sys.stderr):
                return fn(job)
        return super().submit(kind, project, label, quiet)


jobs = _Jobs()
PROJECTS = Path(settings()["projects"])
EXAMPLES = ROOT / "examples"


def _find(name: str) -> Project:
    for base in (PROJECTS, EXAMPLES, Path(".")):
        p = Project(base / name)
        if p.exists():
            return p
    raise ValueError(f"no project '{name}'. Use list_projects or create_project.")


@mcp.tool()
def list_projects() -> list[dict]:
    """List user projects and bundled examples (good starting points: copy one with create_project)."""
    out = []
    for base, kind in ((PROJECTS, "project"), (EXAMPLES, "example")):
        for d in sorted(base.iterdir()) if base.exists() else []:
            if (d / "site.yaml").exists():
                raw = yaml.safe_load((d / "site.yaml").read_text(encoding="utf-8")) or {}
                out.append({"name": d.name, "kind": kind, "title": raw.get("name"), "path": str(d),
                            "scenes": [s.get("type") for s in raw.get("sections", []) if s.get("type") in SCENE_TYPES],
                            "built": (d / "dist" / "index.html").exists()})
    return out


@mcp.tool()
def create_project(name: str, example: Optional[str] = None) -> dict:
    """Create a project in the projects folder, empty or copied from an example. Returns its path."""
    from .cli import STARTER
    dst = PROJECTS / name
    if dst.exists():
        raise ValueError(f"{dst} already exists")
    if example:
        shutil.copytree(EXAMPLES / example, dst, ignore=shutil.ignore_patterns(".build", "dist", "snapshots", "recordings"))
    else:
        (dst / "inputs").mkdir(parents=True)
        (dst / "site.yaml").write_text(STARTER, encoding="utf-8")
    return {"name": name, "path": str(dst), "spec": str(dst / "site.yaml"), "inputs": str(dst / "inputs")}


@mcp.tool()
def spec_schema(part: Optional[str] = None) -> dict:
    """JSON Schema of site.yaml. part = a scene/block type (film, artwork, scene3d, sequence, parallax, type,
    intro, features, stats, timeline, quote, cta, gallery) or 'Site'/'Theme'/'Step'/'Hud' to get just that definition."""
    sch = Site.model_json_schema()
    if not part:
        return sch
    names = {"film": "FilmScene", "artwork": "ArtworkScene", "scene3d": "Scene3DScene", "sequence": "SequenceScene",
             "parallax": "ParallaxScene", "type": "TypeScene", "intro": "IntroBlock", "features": "FeaturesBlock",
             "stats": "StatsBlock", "timeline": "TimelineBlock", "quote": "QuoteBlock", "cta": "CtaBlock", "gallery": "GalleryBlock"}
    key = names.get(part, part)
    return sch["$defs"].get(key) or (sch if key == "Site" else {"error": f"unknown part {part}"})


@mcp.tool()
def get_spec(project: str) -> str:
    """Read a project's site.yaml."""
    return _find(project).spec_path.read_text(encoding="utf-8")


@mcp.tool()
def set_spec(project: str, yaml_text: str) -> dict:
    """Validate and write a project's site.yaml (the whole file). Returns validation errors instead of writing if invalid."""
    p = _find(project)
    try:
        Site.model_validate(yaml.safe_load(yaml_text))
    except ValidationError as e:
        return {"ok": False, "errors": [f"{'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors()]}
    except yaml.YAMLError as e:
        return {"ok": False, "errors": [f"YAML: {e}"]}
    p.spec_path.write_text(yaml_text, encoding="utf-8")
    return {"ok": True}


@mcp.tool()
def list_inputs(project: str) -> list[str]:
    """Files in the project's inputs/ folder (reference them in the spec as inputs/<name>)."""
    p = _find(project)
    return [f"inputs/{f.relative_to(p.inputs).as_posix()}" for f in sorted(p.inputs.rglob("*")) if f.is_file()] if p.inputs.exists() else []


@mcp.tool()
def add_input(project: str, source_path: str) -> str:
    """Copy a local file (image, video, 3D model, .blend) into the project's inputs/. Returns the spec path to use."""
    p = _find(project)
    src = Path(source_path).expanduser()
    if not src.is_file():
        raise ValueError(f"not a file: {src}")
    p.inputs.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, p.inputs / src.name)
    return f"inputs/{src.name}"


@mcp.tool()
def build(project: str, section: Optional[str] = None, draft: bool = False, force: bool = False) -> dict:
    """Start building the site into dist/ (in the background). Returns a job id for job_status.
    draft=True renders sequences at half size for quick checks. Cached stages are skipped."""
    p = _find(project)
    from .compile.compiler import build_site

    def run(job):
        log, progress = logger(job)
        out = build_site(p, log=log, progress=progress, only=section, force=force, options={"draft": draft})
        return {"index": str(out)}
    return jobs.submit("build", p.name, "build", run).public(tail=5)


@mcp.tool()
def job_status(job_id: str, log_lines: int = 40) -> dict:
    """Progress, status and log tail of a background job."""
    j = jobs.jobs.get(job_id)
    if not j:
        raise ValueError("unknown job id")
    return j.public(tail=log_lines)


@mcp.tool()
def wait_for_job(job_id: str, timeout_s: int = 240) -> dict:
    """Block until a job finishes (or the timeout passes) and return its status."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = jobs.jobs.get(job_id)
        if j and j.status in ("done", "failed"):
            return j.public(tail=60)
        time.sleep(1.5)
    return jobs.jobs[job_id].public(tail=20)


@mcp.tool()
def snapshot(project: str, at: Optional[list[str]] = None) -> dict:
    """Screenshot the built site at scroll positions and return the image paths (read them to review the page).
    at: 'scene_id:progress' (e.g. 'hero:0.5'), 'top', 'bottom' or 'y:<px>'. Default: every scene at 15/50/85%."""
    from .snapshot import snapshot as snap
    p = _find(project)
    if not at:
        site = p.load()
        at = ["top"] + [f"{s.id}:{v}" for s in site.sections if s.type in SCENE_TYPES for v in (0.15, 0.5, 0.85)] + ["bottom"]
    out = p.root / "snapshots"
    shutil.rmtree(out, ignore_errors=True)
    with contextlib.redirect_stdout(sys.stderr):
        paths = snap(p.dist, at, out, log=lambda m: None)
    return {"sheet": str(out / "sheet.jpg"), "images": [str(x) for x in paths]}


@mcp.tool()
def record(project: str, section: Optional[str] = None, seconds: float = 12.0) -> dict:
    """Start recording a smooth scroll-through MP4 of the built site (background job)."""
    from .record import record as rec
    p = _find(project)

    def run(job):
        log, progress = logger(job)
        out = p.root / "recordings" / f"{section or 'page'}-{int(time.time())}.mp4"
        return {"video": str(rec(p.dist, out, section=section, seconds=seconds, log=log, progress=progress))}
    return jobs.submit("record", p.name, "record", run).public(tail=5)


@mcp.tool()
def list_styles() -> list[dict]:
    """The twenty-one looks a site can take with theme.style (name, label, what it looks like)."""
    from .compile import themes
    return [{"name": k, "label": v["label"], "about": v.get("about", "")} for k, v in themes.styles().items()]


@mcp.tool()
def looks(project: str, styles: Optional[list[str]] = None) -> dict:
    """Build the (already built) site once per style into dist/looks/<style>/ with a gallery at dist/looks/index.html,
    so the user can compare looks. styles: names from list_styles (default: all)."""
    from .cli import looks as run_looks
    p = _find(project)
    with contextlib.redirect_stdout(sys.stderr):
        run_looks(str(p.root), styles=",".join(styles) if styles else None, thumbs=True)
    return {"gallery": str(p.dist / "looks" / "index.html")}


@mcp.tool()
def copy_deck(project: str) -> dict:
    """Write the site's visible text to <project>/copy.md: a Markdown deck the client can edit and send back."""
    from .brand import export_deck
    p = _find(project)
    out = p.root / "copy.md"
    out.write_text(export_deck(p), encoding="utf-8")
    return {"deck": str(out)}


@mcp.tool()
def apply_copy_deck(project: str, deck_path: str, dry_run: bool = False) -> dict:
    """Apply an edited copy deck to site.yaml (comments kept, invalid edits refused). Returns the changed fields."""
    from .brand import import_deck
    p = _find(project)
    changes = import_deck(p, Path(deck_path).read_text(encoding="utf-8"), dry_run=dry_run)
    return {"changed": [{"key": k, "old": o, "new": n} for k, o, n in changes], "written": bool(changes) and not dry_run}


@mcp.tool()
def brand_from_logo(project: str, logo: str, mode: str = "light", dry_run: bool = False) -> dict:
    """Set theme colours from a logo inside the project (contrast-checked) and use it as the nav logo."""
    from .brand import apply_brand
    return apply_brand(_find(project), logo, mode=mode, dry_run=dry_run)


@mcp.tool()
def doctor() -> list[dict]:
    """Which tools are installed (Blender, FFmpeg, GPU, ComfyUI...) and which scene types need them."""
    from .doctor import checks
    return checks()


if __name__ == "__main__":
    mcp.run()
