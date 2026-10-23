"""Rendering one image of the storyboard, and choosing between the renders kept for it.

Only the image's own stage runs, through the code the full build uses, so the result lands in the build's cache under
the digest the build looks for:

  generated image / edit / gradient / product still    `inputs.resolve_image` on the image input (the same call
                                                        `beats_film`, the compiler and the storyboard make)
  take keyframe                                         the take's `keyframes` stage (`film.world`): only keyframes
                                                        whose own recipe changed are repainted

Nothing here ever starts a video, restore or product-pass render.
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path
from typing import Callable, Optional

from ...inputs import edit_path, generated_path, resolve_image
from ...fidelity import planning
from ...project import BuildContext, BuildError, Project
from . import images, shots, specdoc, variants
from .shots import Board, Node, Shot, Slot

Log = Callable[[str], None]

# rough seconds on an RTX 4090, to move a progress bar (plan.IMAGES has the build's own figures)
ESTIMATE = {"generate": 18, "edit": 70, "gradient": 1, "keyframe": 90, "product": 30, "product-scene": 150}


def estimate(node: Node) -> float:
    if node.kind == "product":
        return ESTIMATE["product-scene"] if node.regen else ESTIMATE["product"]
    return ESTIMATE.get(node.kind, 20)


def fresh_seed(avoid: set) -> int:
    rng = random.SystemRandom()
    while True:
        s = rng.randrange(100, 1_000_000)
        if s not in avoid:
            return s


def with_recipe(node: Node, recipe: dict):
    """The node's image input with a recipe applied in memory (the spec is untouched)."""
    ref = node.ref.model_copy(deep=True)
    for f in node.fields:
        if not f.recipe or f.attr is None:
            continue
        k = f.name.split(".")[-1]
        if k not in recipe:
            continue
        obj = ref
        for a in f.attr[:-1]:
            obj = getattr(obj, a)
        setattr(obj, f.attr[-1], recipe[k])
    return ref


def _find(board: Board, key: str) -> tuple[Node, Shot, Slot]:
    hit = board.node(key)
    if hit is None:
        raise BuildError(f"no image '{key}' in this spec any more (was the shot renamed?)")
    return hit


def _guard(node: Node, shot: Shot) -> None:
    if shot.locked:
        raise BuildError(f"{shot.id} is locked; unlock it to render its images")
    if node.kind == "file":
        raise BuildError("this image is a file in the project, not something the engine renders")


def register_current(project: Project, board: Board, node: Node, origin: str = "original") -> Optional[dict]:
    """Keep the image the spec describes now (when it exists) as a variant, so it can always be gone back to."""
    pr = images.probe(project, board.site, node)
    if pr.state != "current" or pr.path is None:
        return None
    v = variants.register(project, node.key, pr.path, pr.cache, node.recipe(), origin, seed=node.recipe().get("seed"))
    if not variants.load(project, node.key)["history"]:      # the first image is where Revert can always go back to
        variants.push_history(project, node.key, v["n"])
    return v


def run_image(project: Project, key: str, mode: str, seed: Optional[int] = None, log: Log = print,
              progress: Callable[[float, str], None] = lambda f, m="": None) -> dict:
    """Render one image: mode 'regenerate' (a new seed) or 'rerun' (the same recipe, after the text was edited).
    The caller holds the image's lock (variants.claim). Returns what happened."""
    if mode not in ("regenerate", "rerun"):
        raise BuildError(f"mode must be regenerate or rerun, not {mode!r}")
    board = shots.build(project)
    node, shot, slot = _find(board, key)
    _guard(node, shot)
    recipe0 = node.recipe()
    recipe = dict(recipe0)
    if mode == "regenerate":
        if not node.regen or node.seed_field is None:
            raise BuildError("this image has no seed to change; edit its text and use Re-run")
        recipe["seed"] = seed if seed is not None else fresh_seed(variants.used_seeds(project, key) | {recipe0.get("seed")})
    progress(0.02, "looking up the current image")
    register_current(project, board, node)
    if node.kind == "keyframe":
        path, cache = _keyframe(project, board, node, recipe, recipe0, mode, log, progress)
    else:
        ref = with_recipe(node, recipe)
        progress(0.05, "rendering")
        path = resolve_image(project, ref, log, alpha=node.alpha)
        cache = images.rel(project, path)
    seen = variants.find(variants.load(project, key), cache) is not None
    variant = variants.register(project, key, path, cache, recipe, mode, seed=recipe.get("seed"), make_current=True)
    applied, why = True, ""
    if node.kind != "keyframe" and mode == "regenerate":
        applied, why = _write_recipe(project, node, {"seed": recipe["seed"]}, recipe0, f"regenerate {key}")
    elif node.kind == "keyframe":
        applied = True
    progress(1.0, "done")
    from . import notes
    notes.record(project, shot.id, f"{slot.label}: new variant {variant['n']}" + (f" (seed {recipe['seed']})" if recipe.get("seed") is not None else ""),
                 {"shot": shot.id, "slot": slot.name, "key": key, "n": variant["n"]})
    return {"key": key, "shot": shot.id, "slot": slot.name, "variant": variant["n"], "seed": recipe.get("seed"),
            "mode": mode, "image": str(variants.file_of(project, key, variant)), "applied": applied, "note": why,
            "unchanged": seen}


def _write_recipe(project: Project, node: Node, changes: dict, current: dict, label: str) -> tuple[bool, str]:
    """Write recipe fields into site.yaml (every place the node appears); False and why when the file moved on."""
    paths = node.recipe_paths()
    ops, expect = [], {}
    cur_raw = {f.name.split(".")[-1]: f for f in node.fields if f.recipe}
    for name, value in changes.items():
        for p in paths.get(name, []):
            ops.append(specdoc.Op(p, value))
            expect[p] = cur_raw[name].raw
    if not ops:
        return True, ""
    try:
        specdoc.save(project, ops, expect=expect, label=label)
        return True, ""
    except specdoc.Conflict:
        return False, "site.yaml changed while this rendered; the new image is in the strip but was not applied"
    except specdoc.SpecError as e:
        return False, f"not applied: {e}"


def _keyframe(project: Project, board: Board, node: Node, recipe: dict, recipe0: dict, mode: str, log: Log,
              progress: Callable[[float, str], None]) -> tuple[Path, str]:
    from ...scenes import film
    seed_changed = recipe.get("seed") != recipe0.get("seed")
    if seed_changed:
        ok, why = _write_recipe(project, node, {"seed": recipe["seed"]}, recipe0, f"regenerate {node.key}")
        if not ok:
            raise BuildError(why)
    try:
        site = project.load()
        sec = site.sections[node.extra["section_index"]]
        ctx = BuildContext(project, sec.id, log=log, options={"site_video_model": site.video_model})
        progress(0.05, "keyframes stage")
        shot, bkey, _legacy = film.world(sec, ctx)
        ident = images.keyframe_ident(shot, bkey, node.extra["frame"])
    except Exception:
        if seed_changed:                                         # put the seed back: nothing came of it
            try:
                paths = node.recipe_paths()["seed"]
                specdoc.save(project, [specdoc.Op(p, recipe0.get("seed")) for p in paths],
                             expect={p: recipe["seed"] for p in paths}, label="undo failed regenerate")
            except Exception:
                pass
        raise
    png = ctx.work / "keyframes" / f"{node.extra['frame']}.png"
    return png, f"kf:{ident}"


# ---------------------------------------------------------------- choosing a variant

def cache_target(project: Project, node: Node) -> Optional[Path]:
    """Where the build caches this node's image, computed without rendering (generate and edit only)."""
    ref = node.ref
    if isinstance(ref, str) or ref is None or ref.product is not None or ref.file or ref.gradient:
        return None
    if ref.edit:
        e = ref.edit
        try:
            with planning():
                srcs = [resolve_image(project, r, lambda m: None) for r in [e.source, *e.refs[:2]]]
        except Exception:
            return None
        return edit_path(project, ref, srcs)
    if ref.generate:
        return generated_path(project, ref)
    return None


def pick(project: Project, key: str, n: int, log: Log = print, push: bool = True) -> dict:
    """Make variant `n` the image: write its recipe into site.yaml and make sure the build's cache holds it."""
    board = shots.build(project)
    node, shot, slot = _find(board, key)
    _guard(node, shot)
    data = variants.load(project, key)
    v = variants.get(data, n)
    if v is None:
        raise BuildError(f"{key} has no variant {n}")
    register_current(project, board, node)           # keep what is current before it is replaced
    current = node.recipe()
    want = {k: val for k, val in (v.get("recipe") or {}).items() if k in current and not _is_readonly(node, k)}
    changes = {k: val for k, val in want.items() if current.get(k) != val}
    ok, why = (True, "")
    if changes:
        ok, why = _write_recipe(project, node, changes, current, f"pick {key} variant {n}")
        if not ok:
            raise BuildError(why)
    board2 = shots.build(project)
    node2, _, _ = _find(board2, key)
    restored = False
    src = variants.file_of(project, key, v)
    if node2.kind == "keyframe":
        restored = _restore_keyframe(project, board2, node2, src, log)
    else:
        pr = images.probe(project, board2.site, node2)
        if pr.state != "current":
            target = cache_target(project, node2)
            if target is not None and src.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                from ...region import copy_sidecars
                copy_sidecars(src, target)
                restored = True
    pr = images.probe(project, board2.site, node2)
    if push:
        variants.push_history(project, key, n)
        from . import notes
        notes.record(project, shot.id, f"{slot.label}: went back to variant {n}", {"shot": shot.id, "slot": slot.name, "key": key, "n": n})
    return {"key": key, "variant": n, "wrote": sorted(changes), "restored_cache": restored,
            "in_cache": pr.state == "current", "note": "" if pr.state == "current" else
            "the cached render is gone and cannot be rebuilt from here: use Re-run"}


def _is_readonly(node: Node, name: str) -> bool:
    f = next((f for f in node.fields if f.recipe and f.name.split(".")[-1] == name), None)
    return f is None or f.readonly


def _restore_keyframe(project: Project, board: Board, node: Node, src: Path, log: Log) -> bool:
    """Put a kept keyframe back where the stage reads it, and record it as painted from the recipe now in the spec."""
    import json
    from ...scenes import film
    site = board.site
    sec = site.sections[node.extra["section_index"]]
    ctx = BuildContext(project, sec.id, log=log, options={"site_video_model": site.video_model})
    try:
        with planning():
            shot, bkey, legacy = film.blockout_key(sec, ctx)
    except Exception:
        return False
    digests = film.keyframe_digests(shot, bkey, 1, ctx.work)
    name = node.extra["frame"]
    kdir = ctx.work / "keyframes"
    kdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, kdir / f"{name}.png")
    rec = kdir / "_frames.json"
    try:
        recorded = json.loads(rec.read_text()) if rec.exists() else {}
    except ValueError:
        recorded = {}
    others_ok = all(recorded.get(k) == d for k, d in digests.items() if k != name and (kdir / f"{k}.png").exists()) \
        and all((kdir / f"{k}.png").exists() for k in digests)
    recorded[name] = digests[name]
    rec.write_text(json.dumps(recorded, indent=1))
    if others_ok:                                    # the whole stage is now what the spec asks for
        ctx.adopt("keyframes", {"b": bkey, "k": shot["keyframes"]})
    return True


def revert(project: Project, key: str, log: Log = print) -> dict:
    target = variants.revert_target(project, key)
    if target is None:
        raise BuildError("there is no earlier image to go back to")
    res = pick(project, key, target["n"], log, push=False)
    variants.pop_history(project, key)
    return res | {"reverted_to": target["n"]}
