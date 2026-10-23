"""cuts_design: an image designed to match another section's last frame (`image: {match: {...}}`).

A match cut found by luck needs two pictures that happen to share a shape. This makes the second one on purpose:

  edit   Qwen-Image-Edit gets the other section's last frame and an instruction built from the spec ("the round logo
         becomes the sun; keep it where it is, the same size and outline; everything else is a morning seascape"). The
         result is cached like any edit, keyed by the frame's content, so it is redone when that frame is.
  hint   the picture is generated (Z-Image) from `prompt`, with the shape's place and size, found on the other frame
         (Florence-2 + SAM 2.1), written into the prompt ("... the sun in the middle left, about a fifth of the width").
"""
from __future__ import annotations

from pathlib import Path

from .project import BuildError, Project
from .spec import FrameMatch, ImageEdit, ImageInput


def section_frame(project: Project, site, section_id: str, at: str = "last", log=print) -> Path:
    """The picture a section shows at its last (or first) moment, from what is built or the image it is made of."""
    import json
    from .inputs import resolve_image
    sec = next((s for s in site.sections if getattr(s, "id", None) == section_id), None)
    if sec is None:
        raise BuildError(f"match: there is no section with id '{section_id}'")
    from .spec import is_scene
    if is_scene(sec):
        cfg_path = project.build / sec.id / "config.json"
        if not cfg_path.exists():
            raise BuildError(f"match: section '{section_id}' is not built yet. It has to come before the picture that matches it "
                             "in the page (build it first, or `studio build --only " + section_id + "`)")
        cfg = json.loads(cfg_path.read_text())
        url = cfg.get("end" if at == "last" else "poster")
        path = project.build / sec.id / "web" / url.split(f"assets/{sec.id}/", 1)[-1] if url else None
        if path is None or not path.exists():
            raise BuildError(f"match: section '{section_id}' has no {at} frame to match")
        return path
    img = getattr(sec, "image", None) or getattr(sec, "backdrop", None)
    if img is None:
        raise BuildError(f"match: section '{section_id}' ({sec.type}) has no picture to match; it can only be matched "
                         "on a page element (transition.shape.selector)")
    return resolve_image(project, img, log)


def instruction(m: FrameMatch) -> str:
    """The editor's instruction for an `edit` match."""
    if m.becomes:
        parts = [f"Replace {m.shape} with {m.becomes}. {m.becomes[:1].upper() + m.becomes[1:]} fills exactly the area that "
                 f"{m.shape} filled: the same position, the same size and the same outline. {m.shape[:1].upper() + m.shape[1:]} "
                 "itself is no longer visible."]
    else:
        parts = [f"Keep {m.shape} exactly where it is, with the same size and the same outline."]
    if m.prompt:
        parts.append(f"Redraw everything else as: {m.prompt}.")
    else:
        parts.append("Redraw everything around it as a new scene that suits it.")
    return " ".join(parts)


def placement(box: list[float]) -> str:
    """A shape's place and size in words a text-to-image model reads: 'in the middle left, about a fifth of the width'."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    h = "left" if cx < 0.38 else "right" if cx > 0.62 else "centre"
    v = "upper" if cy < 0.38 else "lower" if cy > 0.62 else "middle"
    if (h, v) == ("centre", "middle"):
        where = "in the centre of the frame"
    elif v == "middle":
        where = f"in the middle {h}"
    elif h == "centre":
        where = f"in the {v} centre"
    else:
        where = f"in the {v} {h}"
    w = box[2] - box[0]
    size = ("tiny, about a twentieth of the width" if w < 0.08 else "small, about a tenth of the width" if w < 0.14
            else "about a fifth of the width" if w < 0.26 else "about a third of the width" if w < 0.42
            else "about half the width" if w < 0.62 else "filling most of the frame")
    return f"{where}, {size}"


def match_image(project: Project, ref: ImageInput, log=print) -> Path:
    """Resolve an `image: {match: ...}`: an edit of the other section's frame, or a generated picture with a composition hint."""
    from .fidelity import preview
    from .inputs import _edit, resolve_image
    m = ref.match
    site = project.load()
    try:
        frame = section_frame(project, site, m.section, m.at, log)
    except BuildError:
        # the other section is not built: a plan prices the render, a storyboard shows a card for it, a build stops
        from .fidelity import placeholder, would_render
        would_render("edit" if m.how == "edit" else "image", m.prompt or instruction(m))
        if preview() is not None:
            return placeholder(project.build / "_storyboard" / "placeholders", f"Match {m.section}: {m.becomes or m.shape}", ref.size)
        raise
    if m.how == "edit":
        rel = frame.relative_to(project.root).as_posix() if project.root in frame.parents else str(frame)
        edit = ImageInput(edit=ImageEdit(source=ImageInput(file=rel), instruction=instruction(m), seed=m.seed, steps=m.steps),
                          size=ref.size, seed=ref.seed)
        return _edit(project, edit, log)
    if not m.prompt:
        raise BuildError("match: how: hint needs `prompt` (the whole picture, with the shape in it)")
    hint = ""
    pv = preview()
    if not (pv is not None and not pv.comfy):
        from .cuts_shapes import find_by_prompt
        sh = find_by_prompt(project, frame, m.shape, log)
        if sh is not None:
            what = m.becomes or m.shape
            hint = f" Composition: {what} is {placement(sh['box'])}."
        else:
            log(f"    note: match: '{m.shape}' was not found on {m.section}'s frame; generating without a composition hint")
    return resolve_image(project, ImageInput(generate=m.prompt.rstrip(". ") + "." + hint, size=ref.size, seed=m.seed), log)
