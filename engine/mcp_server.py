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
from typing import Any, Optional

import yaml
from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from .config import ROOT, settings
from .project import BuildError, Project, child, safe_name
from .server.jobs import JobQueue, logger
from .spec import SCENE_TYPES, Site, deprecations

mcp = MCPServer("scroll-studio")


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


# What add_input will copy into a project: media, models, data and source files. Nothing else (keys, tokens, config files)
# is a thing a scroll site needs, so a client that asks for one gets a refusal.
INPUT_SUFFIXES = frozenset(
    ".png .jpg .jpeg .webp .gif .avif .bmp .tif .tiff .svg .exr .hdr .mp4 .mov .webm .mkv .m4v .mp3 .wav .m4a .ogg .flac "
    ".glb .gltf .bin .obj .mtl .fbx .stl .ply .step .stp .3mf .blend .usdz .spz .pt .npz .csv .json .md .markdown .txt "
    ".php .py .ts .tsx .js .jsx .go .rs .rb .java .kt .swift .c .h .cpp .cs .sh .sql .html .css .yml .yaml .toml".split())


def _find(name: str) -> Project:
    try:
        for base in (PROJECTS, EXAMPLES, Path(".")):
            p = Project(child(base, name, "project name"))
            if p.exists():
                return p
    except ValueError as e:
        raise ValueError(f"{e}. Use list_projects or create_project.") from e
    raise ValueError(f"no project '{name}'. Use list_projects or create_project.")


def _readable_source(path: str, suffixes: frozenset[str], what: str) -> Path:
    """A local file a client asks us to read: it must be a real file of a kind a site uses, and not in a hidden folder
    (.ssh, .aws, .config ...). The client may be steered by text it read elsewhere, so it gets no more than the CLI would need."""
    src = Path(path).expanduser()
    if not src.is_file():
        raise ValueError(f"not a file: {src}")
    if src.suffix.lower() not in suffixes:
        raise ValueError(f"{src.name}: {what} takes {', '.join(sorted(suffixes)[:8])} ... files, not {src.suffix or 'files without an extension'}")
    real = src.resolve()
    try:
        below_home = real.relative_to(Path.home().resolve()).parts      # .ssh, .aws, .config ... live straight under it
    except ValueError:
        below_home = ()
    if any(part.startswith(".") for part in below_home):
        raise ValueError(f"{src}: files in hidden folders are not copied; move it somewhere else first")
    return src


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
    dst = child(PROJECTS, name, "project name")
    src = child(EXAMPLES, example, "example name") if example else None
    if dst.exists():
        raise ValueError(f"{dst} already exists")
    if src is not None:
        if not (src / "site.yaml").exists():
            raise ValueError(f"no example '{example}'. Use list_projects to see them.")
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".build", "dist", "snapshots", "recordings"))
    else:
        (dst / "inputs").mkdir(parents=True)
        (dst / "site.yaml").write_text(STARTER, encoding="utf-8")
    return {"name": name, "path": str(dst), "spec": str(dst / "site.yaml"), "inputs": str(dst / "inputs")}


@mcp.tool()
def spec_schema(part: Optional[str] = None) -> dict:
    """JSON Schema of site.yaml. part = a scene/block type (film, artwork, scene3d, sequence, parallax, type, inside,
    intro, features, stats, timeline, quote, cta, gallery) or 'Site'/'Theme'/'Step'/'Hud' to get just that definition."""
    sch = Site.model_json_schema()
    if not part:
        return sch
    names = {"film": "FilmScene", "artwork": "ArtworkScene", "scene3d": "Scene3DScene", "sequence": "SequenceScene",
             "parallax": "ParallaxScene", "type": "TypeScene", "code": "CodeScene", "showroom": "ShowroomScene", "diorama": "DioramaScene",
             "inside": "InsideScene", "stop": "InsideStop",
             "light": "LightScene", "time": "LightTime", "lamps": "LightLamps", "sun": "LightSun", "structure": "LightStructure",
             "product": "Product", "parts": "PartMaterial", "shot": "ProductShot", "intro": "IntroBlock", "features": "FeaturesBlock",
             "stats": "StatsBlock", "timeline": "TimelineBlock", "quote": "QuoteBlock", "cta": "CtaBlock", "gallery": "GalleryBlock"}
    key = names.get(part, part)
    return sch["$defs"].get(key) or (sch if key == "Site" else {"error": f"unknown part {part}"})


@mcp.tool()
def get_spec(project: str) -> str:
    """Read a project's site.yaml."""
    return _find(project).spec_path.read_text(encoding="utf-8")


@mcp.tool()
def set_spec(project: str, yaml_text: str) -> dict:
    """Validate and write a project's site.yaml (the whole file). Returns validation errors instead of writing if invalid.
    A spec that uses deprecated fields is written, with `deprecations` naming each one and what replaces it."""
    p = _find(project)
    try:
        site = Site.model_validate(yaml.safe_load(yaml_text))
    except ValidationError as e:
        return {"ok": False, "errors": [f"{'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors()]}
    except yaml.YAMLError as e:
        return {"ok": False, "errors": [f"YAML: {e}"]}
    p.spec_path.write_text(yaml_text, encoding="utf-8")
    return {"ok": True, "deprecations": [d.as_dict() for d in deprecations(site)]}


@mcp.tool()
def list_inputs(project: str) -> list[str]:
    """Files in the project's inputs/ folder (reference them in the spec as inputs/<name>)."""
    p = _find(project)
    return [f"inputs/{f.relative_to(p.inputs).as_posix()}" for f in sorted(p.inputs.rglob("*")) if f.is_file()] if p.inputs.exists() else []


@mcp.tool()
def add_input(project: str, source_path: str) -> str:
    """Copy a local file (image, video, 3D model, .blend) into the project's inputs/. Returns the spec path to use."""
    p = _find(project)
    src = _readable_source(source_path, INPUT_SUFFIXES, "add_input")
    p.inputs.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, child(p.inputs, src.name, "file name"))
    return f"inputs/{src.name}"


@mcp.tool()
def build(project: str, section: Optional[str] = None, draft: bool = False, force: bool = False,
          only: Optional[list[str]] = None, plan_only: bool = False) -> dict:
    """Start building the site into dist/ (in the background). Returns a job id for job_status.
    only: section and beat ids to render (the rest keep their cache or show their storyboard stand-in).
    plan_only=True returns at once what would render and the estimate on this machine, without building.
    The job log starts with the same plan. draft=True renders sequences at half size. Cached stages are skipped;
    locked scenes and beats are kept. Storyboard first (the `storyboard` tool) to check frames cheaply."""
    from .plan import announce, plan_build
    p = _find(project)
    ids = list(only or []) + ([section] if section else [])
    if plan_only:
        with contextlib.redirect_stdout(sys.stderr):
            pl = plan_build(p, only=ids or None, force=force, options={"draft": draft})
        return pl.summary() | {"lines": pl.lines()}
    from .compile.compiler import build_site

    def run(job):
        log, progress = logger(job)
        announce(p, only=ids or None, force=force, options={"draft": draft}, log=log)
        out = build_site(p, log=log, progress=progress, only=ids or None, force=force, options={"draft": draft})
        return {"index": str(out)}
    return jobs.submit("build", p.name, "build", run).public(tail=5)


@mcp.tool()
def storyboard(project: str, level: str = "stills", only: Optional[list[str]] = None, motion: bool = False,
               timeout_s: int = 900) -> dict:
    """Storyboard the site before the full render, and review it: returns `sheet` (sheet.jpg, one image with a card
    per shot: its frames, prompt, motion, caption, length, fidelity, status new/changed/unchanged/locked/rendered and
    the full render estimate; Read it), `html` (storyboard.html), `site` (the real page with stills standing in for
    unrendered films), `animatic` (animatic.mp4 at level animatic) and a JSON summary per card.
    level: sketch (no ComfyUI: blockouts, cached stills, placeholder cards; seconds), stills (the real first frames:
    keyframes, beat stills, product stills at low samples; ~10-30 s a new shot) or animatic (stills in motion and
    animatic.mp4). only: shot ids (beats, sections, blocks) to redo; the rest keep their frames. motion=True with
    animatic: a tiny LTX preview per shot. Frames reuse the full build's caches, so approved frames are the real
    first frames. Runs as a job; waits up to timeout_s, else returns the job to poll with job_status."""
    from .storyboard import storyboard as run_sb
    p = _find(project)

    def run(job):
        log, progress = logger(job)
        res = run_sb(p, level=level, only=only, motion=motion, log=log, progress=progress)
        return {k: v for k, v in res.items() if k != "plan"}
    job = jobs.submit("storyboard", p.name, f"storyboard {level}", run)
    t0 = time.time()
    while time.time() - t0 < timeout_s and job.status not in ("done", "failed"):
        time.sleep(1.0)
    if job.status == "done":
        return job.result
    return job.public(tail=20)


@mcp.tool()
def inspect_film(project: str, section: Optional[str] = None, video: Optional[str] = None, force: bool = False,
                 embed: bool = False, issues: int = 12, timeout_s: int = 900) -> dict:
    """Polish report of a built film (`studio inspect`): scores it second by second and beat by beat for pops (jumps,
    flicker, judder, crossfades between shots that should line up), softness (looks upscaled: fine detail lost),
    halos (bright rims and seams along edges: depth-warp halos, double edges), style drift (the look moving from the
    scene's start: sketchier, different grain) and morphs (shapes rebuilding instead of moving), so problems are found
    before the owner sees them. CPU only; a film that has not changed answers at once from the saved report.
    section: a film section id (default: every film section with a built film); video: any video file instead, judged as
    one shot. embed=True adds a CLIP-embedding drift check (local weights only, slow). Returns per section: `report_html`
    (open it or Read its pictures: one JPEG per worst moment, under .build/inspect/<section>/), `report_json`, a
    `summary` (verdict clean/slight/visible/bad, counts), the worst `issues` (metric, level, time span, beat, a one-line
    reason and what to try) and every beat's `scores` (0-100, 100 clean, for pops/softness/halos/drift/morphs) and worst
    issue. The storyboard editor shows each beat's worst issue as a badge that links to the report. Runs as a job; waits up
    to timeout_s, else returns the job to poll with job_status."""
    from . import polish
    p = _find(project)

    def run(job):
        log, progress = logger(job)
        if video:
            reps = [polish.inspect_video(p, video, force=force, embed=embed, log=log, progress=progress)]
        else:
            reps = polish.inspect_project(p, section, force=force, embed=embed, log=log)
        out = []
        for r in reps:
            j, h = polish.report_path(p, r["section"])
            out.append({"section": r["section"], "report_html": str(h), "report_json": str(j), "cached": r.get("cached", False),
                        "film": r["film"], "summary": r["summary"],
                        "issues": [{k: x.get(k) for k in ("metric", "level", "severity", "t0", "t1", "beat", "reason", "hint", "thumb")}
                                   for x in r["issues"][:issues]],
                        "beats": [{"id": b["id"], "start": b["start"], "end": b["end"], "scores": b["scores"],
                                   "worst": b["worst"]} for b in r["beats"]]})
        return {"reports": out, "metrics": list(polish.METRICS), "scores": "0-100, 100 = clean"}
    job = jobs.submit("inspect", p.name, "polish report", run)
    t0 = time.time()
    while time.time() - t0 < timeout_s and job.status not in ("done", "failed"):
        time.sleep(1.0)
    if job.status == "done":
        return job.result
    return job.public(tail=20)


_WORKSPACES: dict = {}


def _workspace(project: str):
    from .storyboard.edit.workspace import Workspace
    p = _find(project)
    key = str(p.root)
    if key not in _WORKSPACES:
        _WORKSPACES[key] = Workspace(p, jobs)
    return _WORKSPACES[key]


@mcp.tool()
def storyboard_shots(project: str, shot: Optional[str] = None) -> dict:
    """The storyboard as an editing workspace sees it (the same one `studio storyboard <project> --edit` opens): every
    shot with its editable fields (name, current value, type), its images (slots, each a chain of steps: generate,
    edit..., with seeds) and the variants kept for each image, plus the steps shared between shots. Use the field names
    with set_shot_field and the shot/slot names with regenerate_shot_image. shot: only that shot."""
    ws = _workspace(project)
    with contextlib.redirect_stdout(sys.stderr):
        st = ws.state()
    out = []
    for s in st["shots"]:
        if shot and s["id"] != shot:
            continue
        out.append({"id": s["id"], "kind": s["kind"], "title": s["title"], "locked": s["locked"], "approval": s["approval"],
                    "fields": {f["name"]: {"value": f["value"], "type": f["type"]} for f in s["fields"]},
                    "images": [{"slot": sl["name"], "label": sl["label"], "state": sl["nodes"][0]["image"]["state"],
                                "image": (str(_find(project).root / sl["nodes"][0]["image"]["p"]) if sl["nodes"][0]["image"].get("p") else None),
                                "variants": [{"n": v["n"], "seed": v["seed"], "current": v["current"]} for v in sl["nodes"][0]["variants"]],
                                "steps": [{"kind": n["kind"], "shared": n["shared"], "summary": n["summary"][:120],
                                           "fields": {f["name"]: f["value"] for f in n["fields"]}} for n in sl["nodes"]]}
                               for sl in s["slots"]]})
    return {"rev": st["rev"], "approved": st["approved"], "total": st["total"], "shots": out,
            "shared": [{"key": n["key"], "kind": n["kind"], "used_by": n["used_by"], "summary": n["summary"][:120],
                        "fields": {f["name"]: f["value"] for f in n["fields"]}} for n in st["shared"]]}


@mcp.tool()
def storyboard_notes(project: str, claim: bool = True, include_working: bool = False, include_done: bool = False) -> dict:
    """The inbox of plain-language notes the owner wrote in the storyboard editor ("warmer light", "she should look
    older", "tighten the pacing", ...). Each open note comes with its shot's current spec values (every editable field by
    name), its images (path to read, state, seeds, the steps of the edit chain) and the variants kept; a note for
    'general' comes with the list of all shots. Interpret each note yourself: then act with set_shot_field (text, seconds,
    seeds), regenerate_shot_image (mode rerun after changing an image's prompt or instruction, step 1 for a shared base),
    pick_shot_variant, or by editing site.yaml for page-wide changes (copy, order, pacing); LOOK at the new image
    (Read its path) before you resolve. Then call resolve_note with a short plain reply. claim=True marks the notes
    as 'working' (the page shows it, and attaches the edits you make to the note)."""
    with contextlib.redirect_stdout(sys.stderr):
        return _workspace(project).notes_for_agent(claim, include_working, include_done)


@mcp.tool()
def resolve_note(project: str, note_id: str, reply: str, changed: Optional[list[str]] = None, status: str = "done") -> dict:
    """Close a storyboard note with a short plain-language reply for the owner (what you understood and what you did, or
    why you did not: "made the light warmer (new variant 4, seed 5231); the other shots keep their look"). changed: extra
    things worth listing (edits and new variants made through the editing tools are attached automatically).
    status: done (default), or open to hand it back, or working."""
    from .storyboard.edit import notes
    return notes.resolve(_find(project), note_id, reply, changed, None, status)


@mcp.tool()
def set_shot_field(project: str, shot: str, field: str, value: Any) -> dict:
    """Set one field of a storyboard shot in site.yaml (comments and layout kept, validated first, the previous text is
    kept in storyboard/history/). field: a name from storyboard_shots, e.g. caption, prompt, motion, seconds, seed,
    trim, strength, motion_seed, duration, still.instruction, still.seed, still.region (an edit's region: what it may change),
    still.region.prompt / .pick / .grow / .feather, key.<name>.prompt, locked (true/false).
    Changing text does not render anything: follow with regenerate_shot_image (mode rerun) to redraw the image."""
    from .storyboard.edit import specdoc
    try:
        res = _workspace(project).set_fields(shot, {field: value}, label=f"mcp {shot}.{field}")
    except specdoc.SpecError as e:
        return {"ok": False, "errors": e.errors}
    return res


@mcp.tool()
def regenerate_shot_image(project: str, shot: str, slot: Optional[str] = None, mode: str = "regenerate",
                          step: int = 0, seed: Optional[int] = None, timeout_s: int = 1500) -> dict:
    """Render one image of a storyboard shot again and return the new image's path (Read it). Only that image's stage
    runs (a beat's start or end image, an edit, a take keyframe, a product still), through the build's own code and
    cache, as one background job; videos are never rendered. mode: regenerate (a new seed; written into site.yaml) or
    rerun (the same seed, after set_shot_field changed its text). slot: the image's name from storyboard_shots (default:
    the shot's first, e.g. still, end, key.<name>, image). step: 0 = the image's own step, 1 = the step under it (the
    base image of an edit chain; its shots then need a rerun). Every render is kept as a variant; pick_shot_variant
    goes back to one. Returns image (path), seed, variant, shot, slot."""
    ws = _workspace(project)
    key = ws.resolve_key(shot, slot, step)
    job = ws.start(key, mode, seed)
    t0 = time.time()
    while time.time() - t0 < timeout_s and job.status not in ("done", "failed"):
        time.sleep(1.0)
    if job.status == "done":
        return {k: v for k, v in (job.result or {}).items() if k != "key"} | {"job": job.id}
    if job.status == "failed":
        raise ValueError(job.error or "the render failed")
    return job.public(tail=10) | {"note": "still rendering: poll with job_status"}


@mcp.tool()
def pick_shot_variant(project: str, shot: str, variant: int, slot: Optional[str] = None, step: int = 0) -> dict:
    """Make a kept variant of a shot's image the one in use: its seed (and text) are written into site.yaml, and the
    build's cache holds it, so the full build reproduces that image."""
    ws = _workspace(project)
    return ws.pick(ws.resolve_key(shot, slot, step), variant)


@mcp.tool()
def approve_shot(project: str, shot: str, approved: bool = True) -> dict:
    """Mark a storyboard shot approved (kept in storyboard/state.json, not in the spec). The sheet and `build --plan`
    list shots that are not approved; editing a shot makes its approval read 'changed'."""
    return {"shot": shot, "approval": _workspace(project).approve(shot, approved)}


@mcp.tool()
def journey_plan(project: str, section: Optional[str] = None) -> list[dict]:
    """The one-take page (`journey:` on a film section): which approach it uses (a chain of camera moves between stop
    pictures, or one take through a `blockout`), every move and hold with the film seconds and scroll screens it gets, and,
    once built, where each stop's blocks sit on its picture (the calmest side), the lettering surface, the scrim and the
    contrast reached. Cheap: nothing is rendered."""
    from . import journey
    return journey.report(_find(project), section)


@mcp.tool()
def camera_guide(project: str, beat: str, section: Optional[str] = None) -> dict:
    """For a beat with `camera:` keys: make its camera guide (depth, the moving people's mask, the guide videos) without
    generating anything, and return the paths. `preview` is a pure-camera video of the keyed move over the start image (no
    video model): look at it before spending minutes on the beat. The beat itself is made by `build` (only: [beat id])."""
    from . import camera_beats
    return camera_beats.guide_only(_find(project), beat, section, lambda m: print(m, file=sys.stderr))


@mcp.tool()
def diorama_layout(project: str, section: Optional[str] = None, full: bool = False) -> dict:
    """Miniature worlds (scene type `diorama`): lay the section's world out (CPU, seconds, no GPU) and return what was
    decided: the places and where they are, which step lives at which place, where the camera dives from, how far it
    orbits, what the world is made of. Writes diorama/<id>-map.jpg (a flat map with the places numbered: look at it
    before building) and <id>-plan.json in the project."""
    from .compile import themes
    from .diorama import review
    from .spec import DioramaScene
    p = _find(project)
    site = p.load()
    secs = [s for s in site.sections if isinstance(s, DioramaScene) and (section is None or s.id == section)]
    if not secs:
        raise ValueError("no diorama section" + (f" '{section}'" if section else "") + " in this project")
    sec = secs[0]
    table = sec.look.table or themes.resolve(site.theme)["colors"]["bg"]
    info = review.write_review(sec, table, p.root / "diorama", draft=not full)
    info["map"] = str(p.root / "diorama" / f"{sec.id}-map.jpg")
    return info


@mcp.tool()
def camera_check(project: str, beat: str, section: Optional[str] = None) -> dict:
    """Measure a built beat with `camera:` keys: how far the camera is from the keyed view (zoom error in %, shift in view
    widths, per frame and rms), how far the people walked, against the floor of a perfect camera. Writes camera.json and a
    contact sheet (camera_sheet.jpg: generated, the camera alone, the guide, and the generated beat with the camera taken
    out) beside the beat; read the sheet."""
    from . import camera_beats
    return camera_beats.check(_find(project), beat, section, lambda m: print(m, file=sys.stderr))


@mcp.tool()
def cinemagraphs(project: str, only: Optional[str] = None, force: bool = False, list_only: bool = False) -> dict:
    """Build the site's cinemagraphs (any image input with `cinemagraph: {moves: "the steam above the cup", ...}`: a still where
    only that moves) and return a measured report for each: the loop's seam ratio (about 1 is seamless), how much of the
    picture moves, the largest change of any pixel held still, bytes, and the files (cine_*.mp4, its mask, report json under
    .build/_cinemagraph/). Runs in the background (a video model per cinemagraph; minutes each): returns a job id for
    job_status. only: text matched against `moves` or the spec path. list_only: just what is built and what is not."""
    from . import cinemagraph as cine
    p = _find(project)
    site = p.load()

    def run(job):
        log, _ = logger(job)
        out = []
        for where, ref in cine.collect(site):
            if only and only not in where and only not in ref.cinemagraph.moves:
                continue
            b = cine.build(p, ref, log, force=force, site_video_model=site.video_model,
                           site_wan=site.wan.model_dump(mode="json"), only_cached=list_only)
            out.append({"where": where, "moves": ref.cinemagraph.moves, "built": b is not None,
                        **({"summary": cine.summary(b["data"]), "video": str(b["video"]), "report": b["data"]} if b else {})})
        return {"cinemagraphs": out}
    return jobs.submit("cinemagraph", p.name, "cinemagraph", run).public(tail=5)


@mcp.tool()
def world_check(project: str, section: Optional[str] = None, frames: int = 6) -> dict:
    """Check the in-world type of a built film (steps with `place: {kind: behind | surface | sky}`, see the field docs of
    `place`): per title, how steady the track is (jitter in pixels of a 960-wide frame), how much of its window the type is on
    screen, the surface's slant, the depth it sits at and, where something is off, what to change (`anchor`, `follow`, `at`, `y`,
    `quad`). Writes .build/<section>/world/sheet.jpg (the title's box on the film's own frames, with the depth map beside
    them for behind and sky type): Read it. section: a film section id (default: every film with in-world type)."""
    from . import world_report
    return {"sections": world_report.check(_find(project), section, frames, lambda m: print(m, file=sys.stderr))}


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
def cuts(project: str, strip: bool = False, only: Optional[list[int]] = None, mobile: bool = False,
         reduced_motion: bool = False) -> dict:
    """The film grammar between the built site's sections (`transition:` on a section: cut, dissolve, wipe, iris, whip, match,
    carry): each cut with its length and, for a match cut, how its shapes were found (prompt, box, contour). With
    strip=True also a frame strip around each cut (headless Chrome; read the images to judge the cut): the page before,
    through the cut's stretch of scroll, and after. mobile: a 390 px phone. reduced_motion: what a visitor who asks for
    less motion gets (plain cuts)."""
    from . import cuts as cuts_mod
    p = _find(project)
    found = cuts_mod.read_cuts(p.dist)
    out: dict = {"cuts": [{k: c.get(k) for k in ("n", "label", "type", "length", "anchors") if c.get(k) is not None} for c in found]}
    if strip and found:
        with contextlib.redirect_stdout(sys.stderr):
            paths = cuts_mod.strips(p.dist, p.root / ".build" / "cuts", only=only, size=(390, 844) if mobile else (1280, 720),
                                    mobile=mobile, reduced=reduced_motion, log=lambda m: None)
        out["strips"] = [str(x) for x in paths]
    return out


@mcp.tool()
def record(project: str, section: Optional[str] = None, seconds: float = 12.0) -> dict:
    """Start recording a smooth scroll-through MP4 of the built site (background job)."""
    from .record import record as rec
    p = _find(project)
    stem = safe_name(section or "page", "section")

    def run(job):
        log, progress = logger(job)
        out = p.root / "recordings" / f"{stem}-{int(time.time())}.mp4"
        return {"video": str(rec(p.dist, out, section=section, seconds=seconds, log=log, progress=progress))}
    return jobs.submit("record", p.name, "record", run).public(tail=5)


@mcp.tool()
def trailer(project: str, formats: Optional[list[str]] = None, force: bool = False, plan_only: bool = False) -> dict:
    """Cut the launch trailer from the site's own renders (background job): dist/trailer/trailer-16x9.mp4 and
    trailer-9x16.mp4 + posters, from the spec's `trailer:` (an empty `trailer: {}` derives the cut). formats: 16x9,
    9x16. plan_only=True returns the cut (shots, timings, captions) at once without rendering."""
    from .trailer import build_trailer, plan_only as plan
    p = _find(project)
    if plan_only:
        lines: list[str] = []
        plan(p, log=lines.append)
        return {"plan": lines}

    def run(job):
        log, progress = logger(job)
        return build_trailer(p, formats=formats, force=force, log=log, progress=progress)
    return jobs.submit("trailer", p.name, "trailer", run).public(tail=5)


@mcp.tool()
def list_styles() -> list[dict]:
    """The looks a site can take with theme.style (name, label, what it looks like)."""
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
    changes = import_deck(p, _readable_source(deck_path, frozenset({".md", ".markdown", ".txt"}), "import_deck").read_text(encoding="utf-8"), dry_run=dry_run)
    return {"changed": [{"key": k, "old": o, "new": n} for k, o, n in changes], "written": bool(changes) and not dry_run}


@mcp.tool()
def brand_from_logo(project: str, logo: str, mode: str = "light", dry_run: bool = False) -> dict:
    """Set theme colours from a logo inside the project (contrast-checked) and use it as the nav logo."""
    from .brand import apply_brand
    return apply_brand(_find(project), logo, mode=mode, dry_run=dry_run)


# ---------------------------------------------------------------- inside: the product as the set

@mcp.tool()
def inside_route(project: str, section: Optional[str] = None, stills: Optional[list[str]] = None, samples: int = 24,
                 scale: float = 0.5) -> dict:
    """The route of a `type: inside` scene (the camera flying into the site's product): per stop the parts it found,
    the view, the camera side, where it rests and where its copy sits on the scroll (0-1), plus the notes (automatic
    stops). With `stills` (stop numbers as strings, 'all', 'wide', or 'strip:8' for 8 frames along the route) it renders
    quick Cycles stills and a contact sheet and returns their paths to look at. A stop that matches no part or a model
    without parts returns the error with the part names the model has."""
    from .scenes import inside as ins
    p = _find(project)
    sec = ins.find_section(p, section)
    with contextlib.redirect_stdout(sys.stderr):
        try:
            info, glb, res, plan = ins.route(sec, p, lambda m: None)
        except BuildError as e:
            return {"error": str(e)}
        out = plan.describe()
        picks: list[int] = []
        for tok in stills or []:
            if tok == "wide":
                picks.append(0 if sec.establish else plan.windows[0]["frame"])
            elif tok == "all":
                picks += [w["frame"] for w in plan.windows]
            elif tok.startswith("strip:"):
                n, k = len(plan.frames), int(tok.split(":")[1])
                picks += sorted({round(i * (n - 1) / max(k - 1, 1)) for i in range(k)})
            else:
                picks.append(plan.windows[int(tok) - 1]["frame"])
        if picks:
            sheet = p.root / f"inside_{sec.id}.jpg"
            paths = ins.preview(p, sec, picks, samples, scale, lambda m: None, sheet)
            out["stills"] = [str(x) for x in paths]
            out["sheet"] = str(sheet)
    return out


# ---------------------------------------------------------------- product (site.product)

@mcp.tool()
def product_parts(project: str) -> dict:
    """The site's product model, normalised (cached): size (m), triangles, units, and every part with its
    materials and size, so product.parts rules can target names (match/material globs, region, facing)."""
    from . import product as prod
    p = _find(project)
    with contextlib.redirect_stdout(sys.stderr):
        info = prod.product_info(p, log=lambda m: None)
        info["glb"] = str(prod.normalised_glb(p, log=lambda m: None))
    return info


@mcp.tool()
def product_still(project: str, view: str = "three-quarter", width: int = 1600, height: int = 1200,
                  background: str = "transparent", part: Optional[str] = None, scene: Optional[str] = None) -> dict:
    """Render a still of the site's product (Cycles, studio light; cached) and return its path to look at.
    view: front, three-quarter, side, top, back, hero-low, exploded, detail (with part = a name glob).
    background: transparent, theme or a hex colour. scene: a prompt to render it into a generated scene
    (needs ComfyUI)."""
    from . import product as prod
    from .spec import ImageInput, ProductShot
    p = _find(project)
    with contextlib.redirect_stdout(sys.stderr):
        if scene:
            path = prod.image_still(p, ImageInput(product=ProductShot(view=view, part=part, scene=scene, background=background),
                                                  size=(width, height)), lambda m: None, alpha=background == "transparent")
        else:
            path = prod.product_still(p, None, view, (width, height), background, lambda m: None, part=part)
    return {"image": str(path)}


def _directions_summary(state: dict) -> dict:
    return {"page": state["files"]["html"], "sheet": state["files"]["png"], "seed": state["seed"],
            "diversity": state["diversity"], "warnings": state.get("warnings", []), "picked": state.get("picked"),
            "directions": [{"id": d["id"], "name": d["name"], "stance": d["stance"], "kind": d["kind"], "concept": d["concept"],
                            "style": d["style"], "palette": d["palette"], "fonts": {k: d["fonts"][k] for k in ("display", "body", "mono")},
                            "imagery": d["imagery"], "motion": d["motion"], "voice": d["voice"], "stills": [s["image"] for s in d["stills"]]}
                           for d in state["directions"]]}


@mcp.tool()
def directions(project: str, count: Optional[int] = None, seed: Optional[int] = None, brief: Optional[str] = None,
               images: bool = True, show_only: bool = False, timeout_s: int = 1800) -> dict:
    """Art directions for a site, pitched like a studio (`studio directions`): several complete directions (a concept line, palette,
    type pairing, one of the engine's styles, an imagery treatment that phrases every generated image and film prompt, motion
    notes), each drawn as a board of storyboard stills (the hero and key sections in Z-Image Turbo), side by side on one page.
    Returns `sheet` (board.png, one image: Read it and judge: do the directions differ in kind, do the stills look like the
    palette and type, would a client pick between them?), `page` (board.html), and every direction with its stills.
    The writer is deterministic (curated design vocabularies combined by seed; no model): the same brief and seed give the
    same directions, another `seed` gives another set. The site's `directions:` block (brief, moods, keep, styles/fonts/
    palettes only/avoid/brand colours, count, seed, stills) steers it; `brief` and `count` here override it. images=False
    draws placeholder cards (no ComfyUI). show_only=True returns the saved boards without writing new ones. Then call
    direction_pick. Runs as a job; waits up to timeout_s, else returns the job to poll with job_status."""
    from .directions import run as dr
    p = _find(project)
    if show_only:
        st = dr.load(p)
        if not st:
            raise ValueError(f"no boards yet for '{project}': call directions without show_only")
        return _directions_summary(st)

    def run(job):
        log, progress = logger(job)
        return _directions_summary(dr.make(p, count, seed, brief, images=images, log=log, progress=progress))
    job = jobs.submit("directions", p.name, "direction boards", run)
    t0 = time.time()
    while time.time() - t0 < timeout_s and job.status not in ("done", "failed"):
        time.sleep(1.0)
    return job.result if job.status == "done" else job.public(tail=20)


@mcp.tool()
def direction_reroll(project: str, id: str, images: bool = True, timeout_s: int = 900) -> dict:
    """Another idea in place of one direction on the boards (by its letter), keeping the others: the best other school that
    fits the brief and differs from the rest. Returns the new boards as `directions` does."""
    from .directions import run as dr
    p = _find(project)

    def run(job):
        log, _progress = logger(job)
        return _directions_summary(dr.reroll(p, id, images=images, log=log))
    job = jobs.submit("directions", p.name, f"reroll {id}", run)
    t0 = time.time()
    while time.time() - t0 < timeout_s and job.status not in ("done", "failed"):
        time.sleep(1.0)
    return job.result if job.status == "done" else job.public(tail=20)


@mcp.tool()
def direction_pick(project: str, id: str) -> dict:
    """Write one direction (its letter, or its name) into site.yaml: theme (style, colours, fonts, weights), `imagery` (how every
    image and film prompt is phrased) and scroll pace, as the smallest readable diff, keeping the old file in
    directions/backups/. Copy is never touched. Returns the changed paths and the diff. Next: `storyboard` redraws the images in
    that direction's imagery. Ask the owner before picking unless they chose."""
    from .directions import run as dr
    p = _find(project)
    with contextlib.redirect_stdout(sys.stderr):
        res = dr.pick(p, id, lambda m: None)
    return {"direction": res["direction"]["name"], "changed": res["changed"], "backup": res["backup"], "diff": res["diff"],
            "note": res.get("note")}


@mcp.tool()
def direction_undo(project: str) -> dict:
    """Put site.yaml back as it was before the last direction_pick (only if nothing has changed it since)."""
    from .directions import run as dr
    p = _find(project)
    with contextlib.redirect_stdout(sys.stderr):
        return dr.undo(p, lambda m: None)


@mcp.tool()
def light_report(project: str, section: Optional[str] = None) -> dict:
    """What a built `type: light` scene made (one place relit from dawn to night): per time of day the drift from the world
    (how far the editor moved the place, px at 1024 across: raw, and after its global move is undone) and edge agreement, per
    neighbouring pair how far apart the light is, how far structure still differs (`glide`) and how many lamps switch. Writes
    `light/<section>/sheet.jpg` (every time with its drift: Read it) and `light.json`. Build the project first (`build`); a
    time whose drift is over the limit says so (`ok: false`): give it another `seed:` on that time. Frame strips across the
    transitions: `snapshot` with at=['<section>:0.3', ...]."""
    import json
    from . import light_report as lr
    p = _find(project)
    secs = lr.sections(p, section)
    if not secs:
        return {"error": "no light section" + (f" called '{section}'" if section else "")}
    out = []
    for sec in secs:
        rf = p.build / sec.id / "report.json"
        if not rf.exists():
            out.append({"section": sec.id, "error": "not built yet: run build first"})
            continue
        d = p.root / "light" / sec.id
        d.mkdir(parents=True, exist_ok=True)
        sheet = lr.times_sheet(p, sec, d)
        rep = json.loads(rf.read_text())
        rep.update(lr.sequence_diff(p, sec))
        (d / "light.json").write_text(json.dumps(rep, indent=1))
        out.append({"section": sec.id, "sheet": str(sheet), "report_json": str(d / "light.json"),
                    "times": [{"id": t["id"], "clock": t["clock"], "drift_raw": t["raw"]["drift"], "drift": t["aligned"]["drift"],
                               "edges": t["aligned"]["edges"], "ok": t.get("ok", True)} for t in rep["times"]],
                    "pairs": rep["pairs"]})
    return {"sections": out}


@mcp.tool()
def doctor() -> list[dict]:
    """Which tools are installed (Blender, FFmpeg, GPU, ComfyUI...) and which scene types need them."""
    from .doctor import checks
    return checks()


if __name__ == "__main__":
    mcp.run()
