"""The site spec: one YAML file describes a whole site. The UI, Claude and the CLI all edit this.

A site is a nav, a list of sections and a footer. A section is either a *scene* (a scroll-driven visual
built by a scene module: film, artwork, scene3d, sequence, parallax, type) or a *block* (static content:
intro, features, stats, timeline, quote, cta, gallery).

`Site.model_json_schema()` is the contract for the UI forms and the MCP tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

from .safety import CSS_NAME, FONT_NAME, SAFE_ID, check_url, css_value_ok


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def _untrusted_text(cls, v: Any, info) -> Any:
        """A spec may come from anyone, so the few fields that end up in a file name, a link or a light name are
        checked wherever they appear (see engine/safety.py)."""
        name = info.field_name
        if v is None or not isinstance(v, str):
            return v
        if name == "id" and not SAFE_ID.fullmatch(v):
            raise ValueError(f"id {v[:40]!r} is not allowed: ids name folders and page anchors, so use letters, digits, '-', '_' "
                             "and '.', starting with a letter or digit (at most 64 characters)")
        if name in ("href", "url"):
            check_url(v, name)
        if name == "hdri" and not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", v):
            raise ValueError(f"hdri {v[:40]!r} is not a studio light name: use one of Blender's studio lights, e.g. studio, city, forest")
        return v


# ---------------------------------------------------------------- deprecation (docs/compatibility.md)
#
# A deprecated field (or value of a field) keeps working and warns. Mark it where it is declared:
#
#     Field(None, json_schema_extra=deprecated("2.0.0", replacement="`headline`"))                  # the field
#     Field("a", json_schema_extra=deprecated("2.0.0", replacement="`layout: stack`", value="b"))   # one value of it
#
# The mark goes into the JSON Schema (`deprecated: true` and `x-deprecated`), so the generated reference shows it.
# `deprecations(spec)` lists every use in a spec; the spec still validates.

_ANY = object()


def deprecated(removed_in: str, replacement: Optional[str] = None, *, note: str = "", value: Any = _ANY) -> dict:
    """`json_schema_extra` for a deprecated field, or with `value=` for one deprecated value of the field.
    `removed_in` is the major version that removes it, `replacement` what to write instead, `note` anything else."""
    rule: dict[str, Any] = {"removed_in": removed_in}
    if replacement:
        rule["replacement"] = replacement
    if note:
        rule["note"] = note
    if value is _ANY:
        return {"deprecated": True, "x-deprecated": [rule]}
    return {"x-deprecated": [rule | {"value": value}]}


def deprecated_all(*marks: dict) -> dict:
    """Several marks on one field (a few deprecated values): `deprecated_all(deprecated(..., value="a"), deprecated(..., value="b"))`."""
    out: dict[str, Any] = {"x-deprecated": [r for m in marks for r in m["x-deprecated"]]}
    if any(m.get("deprecated") for m in marks):
        out["deprecated"] = True
    return out


def deprecation_tail(rule: dict) -> str:
    """'will be removed in 2.0.0. Use `x` instead.' for a rule from `deprecated()`, as the warnings and the reference say it."""
    out = f"will be removed in {rule['removed_in']}."
    if rule.get("replacement"):
        out += f" Use {rule['replacement']} instead."
    if rule.get("note"):
        out += f" {rule['note']}"
    return out


@dataclass(frozen=True)
class Deprecation:
    """One deprecated use in a spec: where it is (`path`, inside section `section`), what to do about it."""
    path: str                       # e.g. sections[2].steps[0].old_field
    section: Optional[str]          # id of the section it is in
    removed_in: str
    replacement: Optional[str] = None
    note: str = ""
    value: Any = _ANY               # set when only this value of the field is deprecated

    @property
    def text(self) -> str:
        where = f"{self.path} (section {self.section!r})" if self.section else self.path
        what = "deprecated" if self.value is _ANY else f"the value {self.value!r} is deprecated"
        return f"{where}: {what} and {deprecation_tail(self.__dict__)}"

    def as_dict(self) -> dict:
        """For JSON replies: the parts and the sentence."""
        return {"path": self.path, "section": self.section, "removed_in": self.removed_in,
                "replacement": self.replacement, "text": self.text}

    def __str__(self) -> str:
        return self.text


def deprecations(spec: Any) -> list[Deprecation]:
    """Every deprecated field or value a spec sets, in file order. `spec` is a validated model or the raw dict (validated
    here, so an invalid spec raises as it does anywhere else). A field left at its default is not a use."""
    found: list[Deprecation] = []
    _walk(spec if isinstance(spec, Model) else Site.model_validate(spec), "", None, found)
    return found


def _walk(node: Any, path: str, section: Optional[str], found: list[Deprecation]) -> None:
    if isinstance(node, Model):
        if section is None and isinstance(getattr(node, "id", None), str):
            section = node.id
        for name, info in type(node).model_fields.items():
            if name not in node.model_fields_set:
                continue
            value, here = getattr(node, name), f"{path}.{name}" if path else name
            extra = info.json_schema_extra
            for rule in extra.get("x-deprecated", ()) if isinstance(extra, dict) else ():
                if "value" not in rule or value == rule["value"]:
                    found.append(Deprecation(here, section, rule["removed_in"], rule.get("replacement"),
                                             rule.get("note", ""), rule.get("value", _ANY)))
            _walk(value, here, section, found)
    elif isinstance(node, (list, tuple)):
        for i, item in enumerate(node):
            _walk(item, f"{path}[{i}]", section, found)
    elif isinstance(node, dict):
        for key, item in node.items():
            _walk(item, f"{path}.{key}", section, found)


# ---------------------------------------------------------------- shared pieces

class Link(Model):
    label: str
    href: str = "#"


class Glow(Model):
    """A soft radial light laid over a gradient."""
    x: float = Field(0.5, description="Centre, 0-1 across the image")
    y: float = Field(0.5, description="Centre, 0-1 down the image")
    color: str = Field(..., description="Hex colour")
    radius: float = Field(0.4, description="Softness, as a fraction of the longer side")
    strength: float = Field(0.8, description="0-1: how far the centre goes to the glow's colour")


class Gradient(Model):
    """A backdrop rendered locally with no model at all: a colour sweep, optional glows, stars and film grain.
    For colour cards, dusk skies and night seas behind type."""
    colors: list[str] = Field(..., min_length=2, description="Hex colours along the sweep, first to last")
    angle: float = Field(180, description="Sweep direction in degrees, as in CSS: 180 is top to bottom, 90 left to right")
    glows: list[Glow] = Field(default_factory=list)
    grain: float = Field(0.035, description="Film grain, 0 to 0.2")
    stars: int = Field(0, description="Faint stars scattered over the upper part, for night skies")


# ---------------------------------------------------------------- the product (feature: product integration)

ProductView = Literal["front", "three-quarter", "side", "top", "back", "hero-low", "exploded", "detail"]


class PartMaterial(Model):
    """A material override for the product's parts whose names match. `studio product <project> --parts` lists the
    part, mesh and material names. Rules apply in order, so a later rule wins where two match."""
    match: str = Field("*", description="Glob on the part, mesh or assembly name, case-insensitive: 'Case*', '*knob*', "
                                        "'Housing/*' (an assembly name matches every part inside it)")
    material: Optional[str] = Field(None, description="Only the faces using a material whose name matches this glob "
                                                      "(as listed by --parts), e.g. 'mat_2' or '*Rubber*'")
    color: Optional[str] = Field(None, description="Base colour, hex (sRGB)")
    metallic: Optional[float] = Field(None, ge=0, le=1, description="0 plastic/paint, 1 bare metal")
    roughness: Optional[float] = Field(None, ge=0, le=1, description="0 mirror, 0.3 satin, 0.6 bead-blasted, 0.9 matte")
    emission: Optional[str] = Field(None, description="Glow colour, hex (screens, LEDs)")
    emission_strength: float = Field(1.0, ge=0, description="Glow brightness when `emission` is set")
    transmission: Optional[float] = Field(None, ge=0, le=1, description="See-through amount: 1 glass or clear acrylic")
    texture: Optional[str] = Field(None, description="Base-colour image (project file or URL). Meshes without UVs get a box projection")
    texture_scale: float = Field(0.05, gt=0, description="Box projection: metres per repeat of the texture")
    region: Optional[tuple[float, float, float, float, float, float]] = Field(
        None, description="Only faces whose centre lies in this box, x0 y0 z0 x1 y1 z1 in 0-1 of the product's bounds "
                          "(x left to right seen from the front, y front to back, z bottom to top): paint a screen "
                          "window or a button on a one-piece body")
    facing: Optional[Literal["front", "back", "left", "right", "top", "bottom"]] = Field(
        None, description="Only faces pointing this way (seen from the front view)")


class Product(Model):
    """The product the site is about, declared once. The model is converted, fixed (axes, units), centred on its
    base, given its part materials and cached as one GLB; then takes (`product: {}`), sequences (`model: product`),
    showroom scenes and product stills (`image: {product: three-quarter}`) all use it, and its credit and licence go
    in the footer. One of `model` or `from_photo`."""
    name: str = Field(..., description="Product name, e.g. 'Flipper Zero'")
    maker: Optional[str] = Field(None, description="Who makes it, e.g. 'Flipper Devices'")
    url: Optional[str] = Field(None, description="The maker's page for the product")
    model: Optional[str] = Field(None, description="3D model: GLB/glTF, OBJ, FBX, STL, PLY, STEP/STP (converted locally "
                                                   "with OpenCascade, parts kept with their names) or 3MF; a project "
                                                   "file or an https URL (downloaded once)")
    from_photo: Optional[str] = Field(None, description="A cut-out PNG turned into a 3D model with TRELLIS.2 (see ProductLayer)")
    up: Literal["auto", "z", "y", "x", "-z", "-y", "-x"] = Field(
        "auto", description="Which axis of the file points up. auto: the format's convention (glTF, FBX and OBJ: y; "
                            "STL, PLY, STEP and 3MF: z)")
    units: Literal["auto", "m", "cm", "mm", "in", "ft"] = Field(
        "auto", description="Units the file is in. auto: metres for glTF/FBX/OBJ/PLY, millimetres for STL; STEP and 3MF "
                            "carry their own; anything over 20 m is taken as millimetres")
    rotation: tuple[float, float, float] = Field((0, 0, 0), description="Euler degrees applied after the up fix: turn "
                                                                        "the product so its front faces -y (the front view)")
    parts: list[PartMaterial] = Field(default_factory=list, description="Material overrides by part name")
    exclude: list[str] = Field(default_factory=list, description="Globs on part or assembly names to leave out: "
                                                                 "alternate variants stacked in one CAD file, internal "
                                                                 "parts, packaging")
    tessellation: Literal["draft", "normal", "fine"] = Field(
        "normal", description="STEP: how finely curved surfaces are meshed (fine is smoother and heavier)")
    max_triangles: int = Field(1_500_000, ge=10_000, description="Decimate only above this many triangles")
    licence: Optional[str] = Field(None, description="The model's licence, e.g. 'CC BY 4.0'; shown with the credit")
    credit: Optional[str] = Field(None, description="Attribution for the model, e.g. '3D model by Framework Computer Inc' "
                                                    "(default: '<name> 3D model by <maker>')")
    concept: bool = Field(False, description="Mark the page as a concept: the footer (and the trailer's end card) say "
                                             "'Concept page. Not affiliated with <maker>.'")


class ProductShot(Model):
    """A still of the site's product, rendered by Cycles in a studio light and cached."""
    view: ProductView = Field("three-quarter", description="front, three-quarter, side, top, back, hero-low (a low "
                                                           "camera looking up), exploded (parts pulled apart) or "
                                                           "detail (a close macro view of `part`)")
    part: Optional[str] = Field(None, description="detail: glob on the part/mesh name to frame, e.g. '*port*' "
                                                  "(see studio product --parts); also aims any other view at that part")
    yaw: Optional[float] = Field(None, description="Override the view's turn, degrees (0 front, 90 right side)")
    pitch: Optional[float] = Field(None, description="Override the view's camera height, degrees above the horizon")
    zoom: float = Field(1.0, gt=0, description="1 fits the product in the frame with a margin; 1.3 is closer")
    explode: Optional[float] = Field(None, ge=0, le=1.5, description="How far parts pull apart (exploded view: 1)")
    lens: Optional[float] = Field(None, description="Focal length in mm (default 50; hero-low 32)")
    background: str = Field("auto", description="auto (transparent where the page shows it, such as hero and product "
                                                "blocks, else the theme background), transparent, theme, or a hex colour")
    hdri: str = Field("studio", description="Blender studio light: studio, city, courtyard, forest, interior, night, sunrise, sunset")
    samples: int = Field(128, ge=4, le=4096, description="Cycles samples (denoised)")
    shadow: bool = Field(True, description="A soft contact shadow under the product")
    exposure: float = Field(0.0, ge=-4, le=4, description="Exposure in stops (-0.7 tames a pale metal lid in a bright scene)")
    fstop: Optional[float] = Field(None, gt=0, description="Depth of field, focused on the product (or `part`); "
                                                          "detail views default to f/8, a macro look")
    scene: Optional[str] = Field(None, description="Render the product into a generated scene instead of the studio: "
                                                   "a prompt for the place it stands ('a walnut desk by a window, "
                                                   "morning light'). Z-Image paints the scene to the product's camera "
                                                   "(perspective-matched), the product is lit by it, and a light "
                                                   "Qwen-Image-Edit pass blends it in (needs ComfyUI)")
    harmonise: float = Field(0.3, ge=0, le=1, description="scene: strength of the blending pass (0 skips it); the "
                                                          "product's own pixels are put back if the pass changes them")
    seed: int = Field(7, description="scene: seed for the generated scene")


# ---- freeze (frozen-moment beats): a frame of a beat as an image input ----
class BeatFrame(Model):
    """A frame of a beat of a film: the first or last frame of what that beat renders (after its trim), or the frame
    at a time. Chain beats with it: a beat whose `image` is the last frame of the frozen moment before it starts exactly
    where that moment ends. The beat must come first in the film (or be rendered); `build --only` renders a frozen
    moment on the way, a generated beat that is not rendered yet stands in with its start image."""
    beat: str = Field(..., description="The id of the beat")
    at: Union[Literal["first", "last"], float] = Field("last", description="`first`, `last`, or seconds into the "
                                                                          "beat's clip (after its trim)")
    pick: Literal["last", "sharpest"] = Field("last", description="With at: last, `sharpest` takes the sharpest of the "
                                                                  "last few frames instead of the very last one")
    section: Optional[str] = Field(None, description="The film section holding the beat (found by the beat id when "
                                                     "omitted)")


class FrameMatch(Model):
    """An image designed to match another section's last frame, so a match cut can be built rather than found: the shape
    that ends that section becomes something else in this picture, in the same place at the same size. `edit` hands the
    frame to Qwen-Image-Edit with an instruction made from these fields; `hint` generates this picture from `prompt` with
    the shape's place and size written into it. The section must come before this picture's in the page (it is built
    first); pair it with `transition: {type: match}` on that section."""
    section: str = Field(..., description="The id of the section whose last frame to match")
    shape: str = Field(..., description="What to match in that frame, as you would say it to a person: \"the round logo\"")
    becomes: Optional[str] = Field(None, description="What that shape is in this picture: \"the sun\", \"the rim of a coffee cup\"")
    prompt: Optional[str] = Field(None, description="The rest of this picture (the scene around the shape); with how: hint "
                                                    "this is the whole prompt")
    how: Literal["edit", "hint"] = Field("edit", description="edit: redraw that frame (Qwen-Image-Edit) keeping the shape's "
                                                             "place, size and outline. hint: generate this picture "
                                                             "(Z-Image) from `prompt` with the shape's place and size in it")
    at: Literal["last", "first"] = Field("last", description="Match the section's last frame (or its first)")
    seed: int = 7
    steps: int = Field(30, ge=4, le=60, description="how: edit, the editor's steps")


class Cinemagraph(Model):
    """Make a picture a cinemagraph: a still where only one thing moves (steam from a cup, a curtain in a breeze, light
    on water, a candle flame), and everything else is held perfectly still. Put it on any image input (`hero.image`,
    a product or strip image, a gallery tile, a section `backdrop`):

        image: { generate: "a cup of coffee, steam rising ...", cinemagraph: { moves: "the steam above the cup" } }

    The still stays the picture. The engine finds what moves (Florence-2 + SAM 2.1 from `moves`), has a local video
    model (LTX-2.3 or Wan 2.2) bring a crop around it to life, keeps only the moving part, closes the loop and encodes
    a small video of that part; the page lays it over the still through a soft mask, so outside the mask the pixels are
    the still's and never change. Plain images (no `cinemagraph`) are untouched and keep their cache."""
    moves: str = Field(..., description="What moves, as you would say it to a person: \"the steam above the cup\", "
                                        "\"the sheer curtains\", \"the light on the water\", \"the candle flame\". Found on "
                                        "the still by Florence-2 grounding; it must be visible in the picture")
    motion: Optional[str] = Field(None, description="How it moves, for the video model: \"slow, curling upward\", "
                                                    "\"swaying a little in a soft breeze\". Default: gentle motion of `moves`")
    seconds: float = Field(4.0, ge=1.0, le=8.0, description="Length of the loop in seconds (a pingpong loop is "
                                                            "generated at half this and played forward then back)")
    loop: Literal["seamless", "pingpong"] = Field(
        "seamless", description="seamless: the clip is made to end where it began (first = last frame generation) and any "
                                "seam left is closed by a flow-aligned crossfade; the motion keeps one direction (steam "
                                "keeps rising). pingpong: forward then backward, a seam by construction; for sways and "
                                "shimmer that read the same both ways")
    strength: float = Field(1.0, ge=0.2, le=1.5, description="How far it moves: 1 is the motion as generated, lower "
                                                             "damps it toward its resting look, higher exaggerates it")
    seed: int = 7
    model: Optional[Literal["ltx", "wan"]] = Field(None, description="Video model: ltx (LTX-2.3) or wan (Wan 2.2). "
                                                                      "Default: the site's video_model, then ltx")
    box: Optional[tuple[float, float, float, float]] = Field(None, description="x0, y0, x1, y1 around what moves, 0-1 of "
                                                                              "the still (skips the search by name)")
    points: list[tuple[float, float]] = Field(default_factory=list, description="Points ON what moves, 0-1 across and "
                                                                              "down the still")
    negative_points: list[tuple[float, float]] = Field(default_factory=list, description="Points on what must NOT move")
    pick: Union[Literal["all", "first", "largest", "smallest", "left", "right", "top", "bottom", "center"], int] = Field(
        "all", description="When `moves` matches several things: all of them, or one by rank or index")
    grow: int = Field(10, ge=-60, le=200, description="Widen (+) or shrink (-) the moving region by this many pixels of "
                                                      "the still (the video is free to move this much beyond it)")
    feather: int = Field(28, ge=0, le=120, description="Softness of the region's edge in pixels of the still: the motion "
                                                       "fades into the held-still picture over about this distance")
    track: bool = Field(True, description="Follow the moving thing through the clip (SAM 2.1 video tracking) and keep "
                                          "the whole path it sweeps, so a flame or a curtain that leaves its first "
                                          "outline is not cut off at the edge of the region")


class ImageInput(Model):
    """An image the engine uses as input: a file in the project's inputs/, one generated locally, a gradient, or a
    still of the site's product."""
    file: Optional[str] = Field(None, description="Path relative to the project folder (inputs/photo.jpg) or an https URL")
    generate: Optional[str] = Field(None, description="Prompt for a local text-to-image model (Z-Image Turbo)")
    gradient: Optional[Gradient] = Field(None, description="Render a gradient backdrop (no model needed) at `size`")
    product: Optional[Union[ProductView, ProductShot]] = Field(
        None, description="A still of `site.product` at `size`: a view name (three-quarter, front, side, top, back, "
                          "hero-low, exploded, detail) or a shot {view, part, yaw, pitch, zoom, explode, background, "
                          "scene ...}")
    scene: Optional[str] = Field(None, description="With `product`: render it into a generated scene described by this "
                                                   "prompt (see ProductShot.scene)")
    size: tuple[int, int] = Field((1920, 1088), description="Generated size (multiples of 16)")
    seed: int = 7
    crop: Optional[tuple[float, float, float, float]] = Field(None, description="Crop [x0, y0, x1, y1] in 0-1 image coordinates")
    edit: Optional["ImageEdit"] = Field(None, description="Make this image by editing another one locally (Qwen-Image-Edit)")
    beat_frame: Optional[BeatFrame] = Field(None, description="A frame of a beat of a film (its first or last frame, "
                                                              "or the frame at a time): chain one beat onto the "
                                                              "end of another")
    match: Optional[FrameMatch] = Field(None, description="Design this image to match another section's last frame, for a "
                                                         "match cut (see FrameMatch)")
    credit: Optional[str] = Field(None, description="Attribution shown in the footer")
    cinemagraph: Optional[Cinemagraph] = Field(
        None, description="Make this picture a cinemagraph: only the thing named by `moves` moves (a video laid over the "
                          "still through a soft mask), everything else is held perfectly still. Works wherever the page "
                          "shows the image (hero, product, strip, gallery, a section backdrop)")


ImageRef = Union[str, ImageInput]   # a bare string is a file path


class EditRegion(Model):
    """Where an image edit is allowed to change the picture; everywhere else the result is the source, pixel for pixel.

    Name the region (`prompt`, found on the source image by Florence-2 grounding), or point at it (`box`, `points`;
    0-1 picture coordinates). SAM 2.1 then cuts a precise mask around it. A bare string is a prompt:
    `region: "the girl's shoes"`. The editor works on a padded crop around the region (see `scope`), and the result is
    composited back through the feathered mask at the source's own resolution."""
    prompt: Optional[str] = Field(None, description="What the edit may change, as you would say it to a person: \"the girl's "
                                                    "shoes\", \"the shoes of the woman and the man\"")
    points: list[tuple[float, float]] = Field(default_factory=list, description="Points ON the thing, 0-1 across and down the "
                                                                              "source image (with or without a prompt or box)")
    negative_points: list[tuple[float, float]] = Field(default_factory=list, description="Points on what the mask must NOT take")
    box: Optional[tuple[float, float, float, float]] = Field(None, description="x0, y0, x1, y1 around it, 0-1 of the source "
                                                                              "(skips the prompt's search)")
    pick: Union[Literal["all", "first", "largest", "smallest", "left", "right", "top", "bottom", "center"], int] = Field(
        "all", description="When the prompt matches several things: all of them, one by rank (largest, left, center ...) or "
                           "by index (0 is the first the search lists)")
    within: Optional[str] = Field(None, description="Keep only the matches inside the thing this names, e.g. prompt \"hands\" "
                                                    "within \"the girl in the red coat\". A prompt shaped \"the X's Y\" or "
                                                    "\"the Y of the X\" does this by itself")
    grow: int = Field(0, ge=-80, le=200, description="Widen (+) or shrink (-) the mask by this many pixels of the source image "
                                                      "(the edit is free to redraw this much beyond the thing itself)")
    feather: int = Field(8, ge=0, le=100, description="Softness of the mask's edge in pixels of the source image: the edit "
                                                       "fades into the untouched picture over about this distance")
    invert: bool = Field(False, description="Edit everything EXCEPT the region (the region stays the source, pixel for pixel)")
    scope: Literal["crop", "image"] = Field(
        "crop", description="crop: the editor sees only a padded crop around the region, upscaled to its working size, so a "
                            "small region gets full detail; image: the editor sees the whole picture (always used with "
                            "`invert`)")
    context: float = Field(0.6, ge=0, le=4, description="scope crop: how much of the surroundings the editor sees, as a share "
                                                         "of the region's size added on every side")

    @model_validator(mode="before")
    @classmethod
    def _bare_prompt(cls, v):
        return {"prompt": v} if isinstance(v, str) else v

    @model_validator(mode="after")
    def _has_target(self):
        if not (self.prompt or self.points or self.box):
            raise ValueError("an edit region needs a prompt, points or a box")
        return self


class ImageEdit(Model):
    """Derive an image from another with a local image editor (Qwen-Image-Edit): change one thing, keep the rest."""
    source: ImageRef = Field(..., description="The image to edit (a file, or another generated image)")
    instruction: str = Field(..., description="What to change, e.g. 'close the door completely, keep everything else'")
    refs: list[ImageRef] = Field(default_factory=list, description="Up to two more images the instruction can refer to "
                                                                   "('put the second image on the laptop screen')")
    seed: int = 7
    steps: int = Field(30, ge=4, le=60)
    region: Optional[EditRegion] = Field(
        None, description="Edit only inside this region of the source image (or, with `invert`, everywhere but inside it): "
                          "the rest of the result is the source, pixel for pixel, so consecutive versions of a frame "
                          "differ only where the edit is")


ImageInput.model_rebuild()


class RevealAt(Model):
    """The frame a region is first found on (before it is tracked through the whole film): a moment in a beat
    (`beat` + `t`, 0 = its first frame, 1 = its last), or in the whole film (`t` alone, 0-1), or an exact `frame` /
    `seconds` of the joined film. Pick a frame where the thing is plainly in view."""
    beat: Optional[str] = Field(None, description="beats film: the beat's id")
    t: float = Field(0.5, ge=0, le=1, description="0-1 through the beat (or through the film without `beat`)")
    frame: Optional[int] = Field(None, ge=0, description="An exact frame of the film (overrides beat/t)")
    seconds: Optional[float] = Field(None, ge=0, description="An exact time in the film, seconds (overrides beat/t)")


# ---- type in the world (engine/world.py): a headline placed inside the scene instead of floating over it ------------

class WorldPlace(Model):
    """A headline that lives inside the scene. The camera moves and the type goes with the world: it is occluded by what
    is nearer, it sits on a surface in perspective, it hangs in the haze. The step's title is the text (its `<em>` words
    take the theme's accent as everywhere); `kicker`, `body` and the button stay an ordinary caption beside it. Works on a
    film or a sequence with `layout: overlay` and an `at` window on the step (a sequence: the product's own alpha is the
    silhouette, so type set behind it is cut exactly), and on a parallax section's step with a photo.
    Without WebGL, with reduced motion, and where the headline would be cropped off a narrow screen (a phone held upright),
    the title falls back to a clean overlay caption."""
    kind: Literal["behind", "surface", "sky"] = Field(
        ..., description="behind: set at a depth in the scene, so what is nearer (a pine, a railing, a building, a person) "
                         "passes in front of it as the camera moves; surface: painted on a wall, a sign or a floor, tracked "
                         "to it in perspective, with the surface's light and texture showing through; sky: large type in "
                         "the haze at far depth, with fog in front")
    at: Optional[Union[float, str]] = Field(
        None, description="behind: what the type sits just behind, as a prompt (\"the spruce\", \"the railing\"; found on the "
                          "anchor frame by Florence-2 + SAM 2.1, so it needs ComfyUI the first time) or a depth, 0 far to 1 "
                          "near, in the shot's own range (default: behind the nearest third of what is in its box). "
                          "surface: what it is painted on, as a prompt (\"the wooden deck\", \"the white wall\"; required "
                          "unless `quad` is given). sky: a depth (default 0.07, just in front of the farthest thing)")
    x: Optional[float] = Field(None, description="Centre across, 0-1 of the frame (behind, sky) or of the surface (surface). "
                                                 "Default 0.5")
    y: Optional[float] = Field(None, description="Centre down, 0-1 of the frame or of the surface. Default 0.5 (sky: 0.3)")
    size: Optional[float] = Field(None, gt=0.05, le=1.5, description="Width of the type, as a fraction of the frame (behind, "
                                                                     "sky) or of the surface (surface). Default 0.5 behind, "
                                                                     "0.72 sky, 0.8 surface")
    lines: Optional[int] = Field(None, ge=1, le=5, description="Break the title into this many lines (default: the layout "
                                                               "that fills the width best)")
    align: Literal["left", "center", "right"] = Field("center", description="Alignment of a title of several lines")
    caps: bool = Field(False, description="Set the title in capitals")
    track: Optional[float] = Field(None, ge=-0.1, le=0.6, description="Letter-spacing in em (default: 0 behind, 0.05 on a "
                                                                      "surface, 0.1 in the sky)")
    weight: Optional[int] = Field(None, ge=100, le=900, description="Font weight (default: the theme's display weight)")
    color: str = Field("auto", description="auto (light or dark ink, whichever reads on the footage under it), ink, paper, "
                                           "accent, or a hex colour")
    anchor: Optional[RevealAt] = Field(None, description="The frame the thing is found on and the type is laid out on "
                                                           "(default: the middle of the step's `at` window). Pick a frame "
                                                           "where it is plainly in view")
    gap: float = Field(0.05, ge=0, le=0.5, description="behind (named thing): how far behind it the type sits, in depth units")
    follow: Optional[float] = Field(None, ge=0, le=1.5, description="How much of the camera's motion the type follows "
                                                                   "(behind, sky): 1 moves with the layer it sits in, 0 stays "
                                                                   "on the screen. Default: what its depth says")
    haze: Optional[float] = Field(None, ge=0, le=1, description="How much of the scene's air is mixed into the type (behind: "
                                                                "0.12, sky: 0.5): colour and contrast of distance")
    fog: float = Field(0.55, ge=0, le=1, description="sky: fog in front of the type, thicker low in the picture and where "
                                                     "something far passes in front of it")
    blur: Optional[float] = Field(None, ge=0, le=30, description="Softness of the type in pixels of a 1920-wide frame "
                                                                 "(behind, sky: default matches how sharp the footage is at "
                                                                 "that depth)")
    wear: float = Field(0.35, ge=0, le=1, description="surface: how much of the paint has worn off (the surface's own texture "
                                                      "breaks the letters up)")
    relief: float = Field(0.8, ge=0, le=1, description="surface: how much of the surface's grain and light shows through the paint")
    quad: Optional[list[tuple[float, float]]] = Field(
        None, min_length=4, max_length=4, description="surface: the four corners of the surface on the anchor frame, 0-1, "
                                                      "clockwise from the top left, instead of finding it by prompt (the "
                                                      "type is then tracked from these corners)")
    angle: float = Field(0.0, ge=-180, le=180, description="surface: turn the type on the surface, degrees")
    slant: float = Field(1.0, ge=0, le=1.5, description="surface: how much of the slant the depth map gives the surface is used "
                                                        "(1: as estimated, 0: the type lies flat to the screen). The estimate "
                                                        "is a guess from relative depth; lower it when the letters look "
                                                        "over-foreshortened")
    track_model: Optional[Literal["homography", "similarity"]] = Field(
        None, description="How the footage is followed: a surface is tracked as a plane seen in perspective (homography); "
                          "behind and sky as a layer that shifts, turns and zooms (similarity)")


def _place(v):
    """`place: sky` is shorthand for `place: {kind: sky}`; the caption positions keep working as they were."""
    if isinstance(v, str) and v in ("behind", "surface", "sky"):
        return {"kind": v}
    return v


class Step(Model):
    """One beat of copy that scrolls past the scene."""
    kicker: Optional[str] = None
    title: str = Field(..., description="Headline; <em>…</em> marks the accent words")
    body: Optional[str] = None
    fact: Optional[str] = Field(None, description="Small print under the body (mono)")
    at: Optional[tuple[float, float]] = Field(None, description="overlay layout: visible between these scene progress values (0-1)")
    length: float = Field(1.2, description="split/cards layouts: scroll distance of this step, in screen heights")
    intro: bool = Field(False, description="Render as the section's opening headline (h1)")
    hint: Optional[str] = Field(None, description="Small 'scroll to begin' line under an intro step")
    place: Optional[Union[Literal["left", "right", "center", "top-left", "top-right", "bottom-left", "bottom-right"], WorldPlace]] = Field(
        None, description="overlay layout: where this caption sits on the shot (default: left, centred vertically). Or an "
                          "object, `{kind: behind | surface | sky, ...}`: the title is set inside the scene instead of over "
                          "it (type in the world; see WorldPlace). `place: sky` is shorthand")

    @field_validator("place", mode="before")
    @classmethod
    def _place_in(cls, v):
        return _place(v)

    @property
    def world(self) -> Optional[WorldPlace]:
        """The in-world placement of the title, if it has one."""
        return self.place if isinstance(self.place, WorldPlace) else None

    @property
    def corner(self) -> Optional[str]:
        """Where the caption sits when it is an ordinary overlay (`place: left`...)."""
        return self.place if isinstance(self.place, str) else None
    surface: Optional[Literal["light", "dark"]] = Field(
        None, description="overlay layout: this caption's colours, when the shot under it is lighter or darker than the "
                          "rest of the scene (dark words on a bright sky: light), with a soft glow behind them")
    button: Optional[Link] = Field(None, description="overlay layout: a button under the caption, e.g. the call to "
                                                     "action on a film's last shot")
    image: Optional[ImageRef] = Field(None, description="parallax: this step's photo")
    state: dict[str, Any] = Field(default_factory=dict,
        description="Scene-specific state for this step. chart: {show, focus, x, y, reveal, marks}; map: {center, zoom, pitch, bearing, route, marker}")


class Hud(Model):
    """Overlay instruments tied to scroll progress."""
    kind: Literal["telemetry", "scale", "progress", "legend", "none"] = "none"
    fields: list[dict[str, Any]] = Field(default_factory=list,
        description="telemetry: [{label, unit, from, to, curve, decimals, grouping}] values go from `from` (default 0) to `to` with progress^curve")
    events: list[dict[str, Any]] = Field(default_factory=list, description="telemetry: [{at, label}] lit when progress >= at")
    clock: Optional[dict[str, Any]] = Field(None, description="telemetry: {prefix, start, end, zero} seconds; zero = progress where T=0")
    scales: list[str] = Field(default_factory=list, description="scale: one label per level, e.g. ['100 µm','10 µm']")
    legend: list[dict[str, str]] = Field(default_factory=list, description="legend: [{label, color}]")


# ---------------------------------------------------------------- film grammar between sections (transition:, engine/cuts.py)

CUT_TYPES = ("cut", "dissolve", "wipe", "iris", "whip", "match", "carry")


class CutAnchor(Model):
    """Where a shape sits on one side of a match cut: named (found on that side's picture by Florence-2 and SAM 2.1),
    boxed, or a page element. A bare string is a prompt: `shape: "the round logo"`."""
    prompt: Optional[str] = Field(None, description="What to find on the picture, as you would say it to a person: "
                                                    "\"the sun\", \"the round logo\", \"the cup\"")
    box: Optional[tuple[float, float, float, float]] = Field(None, description="x0, y0, x1, y1 around the shape, 0-1 of "
                                                                               "the section's picture")
    selector: Optional[str] = Field(None, description="A CSS selector for a page element inside the section (the phone "
                                                      "screen: `.ss-phone__screen`, a logo: `.ss-wordmark svg`); "
                                                      "measured in the browser, so it works on any block")

    @model_validator(mode="before")
    @classmethod
    def _bare_prompt(cls, v):
        return {"prompt": v} if isinstance(v, str) else v

    @model_validator(mode="after")
    def _one(self):
        if sum(x is not None for x in (self.prompt, self.box, self.selector)) != 1:
            raise ValueError("a cut anchor is exactly one of prompt, box or selector")
        return self


class Carry(Model):
    """An element that travels across the cut: it leaves its place in this section and settles in its place in the
    next (FLIP: the browser measures both), so the eye is led over the join."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: str = Field("h1, h2", alias="from", description="CSS selector of the element in this section "
                                                                       "(the last match on its final screen)")
    to: str = Field("h1, h2", description="CSS selector of the element in the next section (the first match "
                                                         "on its first screen)")
    via: Literal["dissolve", "cut", "wipe", "iris"] = Field("dissolve", description="What the rest of the picture does "
                                                                                     "while the element travels")


class Transition(Model):
    """How a section hands over to the next, in the language of film. Without it sections simply follow one another
    (today's behaviour). The cut takes its own stretch of scroll (`length`): both pictures are held on screen while the
    scroll drives the cut, then the page carries on. Reduced motion, and pages without scripts, get a plain cut.

    cut: an instant cut at a scroll position with a held beat either side. dissolve: a held cross-dissolve.
    wipe: the next picture is revealed along a line (`direction`, `angle`, `soft`). iris: it opens from a point as a
    circle (`origin`, or `closing` for the iris that closes on this one). whip: a fast directional blur-pan into the
    next (`direction`, `blur`). match: the end of this section and the start of the next share a shape; the frames scale
    and move until the two shapes coincide and the picture swaps on the shape (`shape`, `becomes`). carry: an element
    travels from its place here to its place there (`carry`)."""
    type: Literal["cut", "dissolve", "wipe", "iris", "whip", "match", "carry"] = Field(
        ..., description="cut, dissolve, wipe, iris, whip, match or carry")
    length: Optional[float] = Field(None, ge=0.1, le=4, description="Scroll distance the cut takes, in screen heights "
                                    "(defaults: cut 0.8, dissolve 1.2, wipe 1.3, iris 1.4, whip 1.1, match 1.5, carry 1.5)")
    hold: float = Field(0.15, ge=0, le=0.4, description="The share of the stretch held still at each end, so each picture "
                                                         "is on screen a moment before and after the cut")
    at: float = Field(0.5, ge=0.1, le=0.9, description="cut and match: where in the cut (between the two holds) the picture swaps, 0-1")
    direction: Optional[Literal["left", "right", "up", "down"]] = Field(
        None, description="wipe and whip: the way things travel (left: the next picture arrives from the right). "
                          "Default left")
    angle: Optional[float] = Field(None, description="wipe: the edge's direction in degrees (0 right, 90 down); overrides direction")
    soft: float = Field(0.0, ge=0, le=1, description="wipe and iris: how soft the edge is (0 hard)")
    origin: Optional[tuple[float, float]] = Field(None, description="iris: where it opens from, 0-1 across and down the "
                                                                    "screen (default the middle; with a match, the shape)")
    closing: bool = Field(False, description="iris: close on this section (the next shows behind it) instead of opening the next")
    blur: float = Field(1.0, ge=0, le=3, description="whip: blur strength, 1 is natural")
    shape: Optional[CutAnchor] = Field(None, description="match: the shape on this section's last picture. Leave out "
                                                         "both `shape` and `becomes` to let the engine look for the "
                                                         "best-matching pair of shapes (contours)")
    becomes: Optional[CutAnchor] = Field(None, description="match: the shape on the next section's first picture "
                                                            "(default: the same prompt as `shape`)")
    zoom: float = Field(3.0, ge=1, le=8, description="match: the most each side may be scaled to bring the shapes to the "
                                                      "same size (more than this and they only nearly coincide)")
    blend: float = Field(0.0, ge=0, le=0.3, description="match: a quick cross-dissolve over the swap, as a share of the "
                                                         "stretch (0: a hard swap on the shape)")
    carry: Optional[Carry] = Field(None, description="carry: the element that travels (the section's heading to the next one's by default)")

    @model_validator(mode="before")
    @classmethod
    def _bare_type(cls, v):
        return {"type": v} if isinstance(v, str) else v

    @model_validator(mode="after")
    def _fit(self):
        if self.type != "carry" and self.carry is not None:
            raise ValueError("`carry` belongs to a transition of type carry")
        if self.type != "match" and (self.shape is not None or self.becomes is not None):
            raise ValueError("`shape` and `becomes` belong to a transition of type match")
        return self


TRANSITION_DOC = ("How this section hands over to the next one, in film grammar: cut, dissolve, wipe, iris, whip, match "
                  "(a shared shape) or carry (an element travels over). Unset: the sections just follow one another. "
                  "A bare name works: `transition: whip`. See Transition")


class SceneBase(Model):
    id: str
    nav_label: Optional[str] = None
    layout: Literal["overlay", "split", "cards"] = Field(
        "overlay", description="overlay: captions over a full-bleed stage; split: pinned visual beside scrolling "
                               "cards; cards: full-bleed stage with cards scrolling over it")
    side: Literal["left", "right"] = Field("right", description="split/cards: which side the visual sits on")
    length: float = Field(4.0, description="overlay layout: scroll distance in screen heights")
    steps: list[Step] = Field(default_factory=list)
    hud: Hud = Field(default_factory=Hud)
    cue: Optional[str] = Field(None, description="'Scroll to …' hint shown at the start")
    shade: Literal["auto", "none", "strong"] = "auto"
    surface: Optional[Literal["light", "dark", "accent"]] = Field(
        None, description="Colour scheme for the scene's panel in the stack layout (see blocks); sets the text colour over a backdrop")
    backdrop: Optional[ImageRef] = Field(
        None, description="Full-bleed image behind the whole section: a file, URL, generate: or gradient:. In the stack "
                          "layout it is the panel's own backdrop. Pair with `surface` for legible text.")
    locked: bool = Field(False, description="Keep this scene's renders as they are: `studio build` and `studio "
                                            "storyboard` never re-render it, even when its settings change (a log line "
                                            "says so). A locked scene that was never rendered is rendered once. Unlock "
                                            "(or delete the render) to redo it")
    transition: Optional[Transition] = Field(None, description=TRANSITION_DOC)


# ---------------------------------------------------------------- scene types

class WorldObject(Model):
    """One rough shape in a take's world. Only layout, scale and depth matter: the video model paints the detail."""
    kind: Literal["box", "cylinder", "cone", "blob", "plane", "scatter"]
    name: Optional[str] = None
    at: tuple[float, float, float] = Field((0, 0, 0), description="Centre (x, y, z); z is up")
    size: tuple[float, float, float] = Field((1, 1, 1), description="box/plane: full width, depth, height; blob: radii")
    radius: float = Field(1.0, description="cylinder/cone radius")
    depth: float = Field(1.0, description="cylinder/cone height")
    rotation: tuple[float, float, float] = Field((0, 0, 0), description="Euler degrees")
    color: str = "#9a9a9a"
    soft: bool = Field(False, description="blob: visible in the preview but left out of the depth guide (clouds, haze)")
    count: int = Field(40, description="scatter: how many boxes")
    seed: int = Field(1, description="scatter: random seed")
    area: tuple[float, float, float, float] = Field((-50, -50, 50, 50), description="scatter: x0, y0, x1, y1")
    height: tuple[float, float] = Field((2, 10), description="scatter: min and max box height")
    footprint: tuple[float, float] = Field((3, 6), description="scatter: min and max box width/depth")
    shape: Literal["box", "cone"] = Field("box", description="scatter: box (buildings, rocks) or cone (pines)")
    clear: Optional[tuple[float, float, float]] = Field(None, description="scatter: keep (x, y, radius) empty")


# ---------------------------------------------------------------- video model (LTX-2.3 or Wan 2.2)

VideoModel = Literal["ltx", "wan"]
VIDEO_MODEL_DOC = ("Video model: ltx (LTX-2.3, the default) or wan (Wan 2.2 A14B: renders at ~1280x720 and 16 fps, "
                   "retimed to 24; clean, physical motion and first/last-frame control, but no finer detail than LTX "
                   "after restore, and slower). Unset = the site's `video_model`, then studio.toml's, then ltx")


class Wan(Model):
    """Wan 2.2 A14B settings (`video_model: wan`). Two 14B experts sample in turn (high-noise for the first half of
    the steps, low-noise for the rest). Renders at ~1280x720, 16 fps, up to 81 frames (~5 s) per clip; longer shots
    chain clips from the previous last frame; frames are retimed to 24 fps and restored/upscaled as usual."""
    quality: Literal["fast", "full"] = Field("fast", description="fast: the lightx2v 4-step LoRAs, cfg 1 (an 81-frame "
                                             "720p clip samples in ~2.5 min on an RTX 4090, plus loading the two "
                                             "experts). full: no LoRAs, 20 steps at cfg 3.5 (~25 min a clip; uses the "
                                             "negative prompt; in tests no sharper than fast)")
    steps: Optional[int] = Field(None, ge=2, le=60, description="Total steps (default 4 fast, 20 full); the high-noise "
                                                                "expert takes the first half")
    cfg: Optional[float] = Field(None, ge=1, le=10, description="Guidance (default 1 fast, 3.5 full)")
    shift: Optional[float] = Field(None, ge=1, le=20, description="ModelSamplingSD3 shift (default 5 fast, 8 full)")
    res: Optional[tuple[int, int]] = Field(None, description="Render size, multiples of 16 (default 1280x720's "
                                                             "pixel count at the shot's aspect; 720x1280 for portrait)")
    interpolate: Literal["mci", "blend", "dup"] = Field(
        "mci", description="16 -> 24 fps: mci (FFmpeg motion-compensated in-betweens), blend (cross-fades) or dup "
                           "(repeated frames, exact pixels, slight judder)")
    stretch: float = Field(1.35, ge=1, le=2, description="beats/art: a shot up to this many times one clip's length "
                                                     "(81 frames, ~5 s) is one clip played slower instead of two "
                                                     "chained clips (a chained clip restarts the motion)")
    seed: Optional[int] = Field(None, description="takes: seed for Wan (default: the take's ltx.seed)")
    guide_blur: Optional[float] = Field(None, ge=0, le=12, description="takes: blur of the depth guide in pixels "
                                        "(default: ltx.guide_blur). Fun Control follows the guide's shapes closely, so "
                                        "a blockout box tends to stay a box: blur more (3-6) to let it paint a real "
                                        "table or rock, less to hold exact edges")
    negative_prompt: Optional[str] = Field(None, description="Used only when cfg > 1 (quality: full)")


class CameraKey(Model):
    t: float = Field(..., description="Seconds")
    at: tuple[float, float, float] = Field(..., description="Camera position")
    look: tuple[float, float, float] = Field(..., description="Point the camera looks at")


class ProductLayer(Model):
    """The real thing in a take: rendered from its own 3D model through the take's camera and composited over the
    generated world, so it never warps. One of `model` or `from_photo`, or neither (`product: {}`) to use the site's
    `product:` (its normalised model, materials and credit)."""
    model: Optional[str] = Field(None, description="GLB/glTF, OBJ, FBX, STL or PLY: a project file or an https URL. "
                                                   "Omit to use site.product")
    from_photo: Optional[str] = Field(None, description="A cut-out PNG (transparent background) turned into a 3D model "
                                                         "with TRELLIS.2 (needs `trellis_python`/`trellis_script` in studio.toml)")
    credit: Optional[str] = Field(None, description="Attribution shown in the footer")
    at: tuple[float, float, float] = Field((0, 0, 0), description="Where the base centre of the product sits in the world")
    height: Optional[float] = Field(None, description="Height of the product in world units (default: site.product's "
                                                      "real height in metres, else 1)")
    rotation: tuple[float, float, float] = Field((0, 0, 0), description="Euler degrees")
    spin: float = Field(0.0, description="Extra yaw, in degrees, turned evenly over the whole take")
    hdri: Optional[str] = Field(None, description="Light for the product. Default: the plate itself (an environment "
                                                  "built from the generated frames around each moment, so the product "
                                                  "takes the scene's light and reflections). Or a Blender studio light: "
                                                  "studio, forest, city, courtyard, night, interior, sunrise, sunset")
    sun_strength: float = Field(3.0, description="A sun lamp along the take's light direction; 0 to turn it off")
    samples: int = Field(64, description="Cycles samples per frame (denoised)")
    shadow: bool = Field(True, description="Cast the product's shadow onto the generated ground")
    shadow_size: Optional[float] = Field(None, description="Side of the square the shadow falls on, in metres (the table or floor patch); default 3x the height")
    res: Optional[tuple[int, int]] = Field(None, description="Render size of the product pass, which is also the final "
                                                             "film size (default 1920x1080; 2560x1440 when the take "
                                                             "is upscaled)")
    fstop: Optional[float] = Field(2.8, description="Depth of field: focused where the camera looks, at this f-stop "
                                                    "(real scale); none for everything sharp")
    motion_blur: float = Field(0.5, ge=0, le=1, description="Shutter as a fraction of a frame (0: off)")
    grade: bool = Field(True, description="Match the product pass to the plate: black level, white balance, saturation, "
                                          "softness, and a light wrap at the edges")
    grain: Optional[float] = Field(None, ge=0, description="Film grain on the product (0-255 sigma); default: measured "
                                                          "from the plate")


class Take(Model):
    """One continuous camera move through a generated world, with a real product locked to the same camera.

    The world is a rough blockout (shapes + camera keys) rendered by Blender into a depth guide; LTX-2.3 paints the
    world along that guide in chained segments; the product is rendered by Cycles through the identical camera and
    composited over every frame; the result is encoded for scrubbing."""
    duration: float = Field(..., description="Seconds")
    fps: int = 24
    sky: str = "#8fb4d8"
    light: tuple[float, float, float] = Field((0.4, -0.3, 0.85), description="Light direction for the preview and the product's sun")
    ground: Optional[WorldObject] = Field(None, description="A plane under everything (defaults to a 400 x 400 plane at z = 0)")
    objects: list[WorldObject] = Field(default_factory=list)
    camera: list[CameraKey] = Field(..., min_length=2)
    lens: float = Field(32.0, description="Focal length in mm")
    product: Optional[ProductLayer] = None
    product_in_guide: bool = Field(False, description="Put the product's shape in the depth guide. Off by default: the video model then paints its own version of the product, which shows around the edges of the real one. Leave the product out of the prompts too and describe the empty spot ('an empty table').")
    preview_res: tuple[int, int] = Field((1280, 720), description="Blockout render size; same aspect as product.res")
    depth_far: float = Field(400.0, description="Depth guide far plane")
    keyframes: Optional[dict[str, Any]] = Field(None, description="Z-Image stills pinned at times, as in shot.keyframes")
    ltx: dict[str, Any] = Field(..., description="LTX-2.3 settings, as in shot.ltx: res, segments [{id, range, prompt}], "
                                                 "seed, guide_strength ... Render at res [1920, 1088] (multiples of "
                                                 "32) for a detailed world; [1024, 576] is a quick draft")
    upscale: Optional[dict[str, Any]] = Field(None, description="Optional upscale stage, as in shot.upscale")
    restore: Optional[int] = Field(None, ge=360, le=2160, description="Run SeedVR2 over the generated world at this "
                                                                      "height (e.g. 1080) to clean the video model's "
                                                                      "softness and redraw fine detail, before the "
                                                                      "product is composited (the real product is "
                                                                      "never restored); slow")
    video_model: Optional[VideoModel] = Field(None, description=VIDEO_MODEL_DOC + ". With wan the world is painted by "
                                              "Wan 2.2 Fun Control along the same depth guide, from the first "
                                              "keyframe, in the segments and prompts of `ltx:`")
    wan: Optional[Wan] = Field(None, description="Wan settings for this take (over the site's `wan:`)")
    locked: bool = Field(False, description="Keep the take's renders (world, product pass, composite) as they are, even "
                                            "when its settings change: build and storyboard log it and move on")


# ---- freeze (frozen-moment beats) ----
FreezeEase = Literal["linear", "inOutSine", "inOutQuad", "inOutCubic", "inOutQuart", "smoother", "flow"]


class FreezeKey(Model):
    """One stop of a frozen moment's camera: the framing box the camera has reached at time `t` of the beat."""
    t: float = Field(..., ge=0, le=1, description="When the camera reaches the box, 0-1 of the beat")
    box: tuple[float, float, float, float] = Field(
        ..., description="Framing box [x0, y0, x1, y1] in 0-1 of the frozen frame. The aspect comes from beat_res: a "
                         "box of another shape is widened (never cropped) to it, so everything in the box stays in frame")
    hold: float = Field(0.0, ge=0, le=1, description="The camera rests on the box for this much of the beat after "
                                                     "reaching it (the frozen moment still breathes with the parallax)")


# ---- deep zoom + layered depth for frozen moments (engine/zoom.py, engine/layers.py) ------------------------------

class FreezeDetail(Model):
    """Deep zoom: the camera may push from the wide shot to a 10-20x close-up and every scale stays sharp. The frame is
    not enlarged, it is built into a pyramid of tiles (about `ratio` times the detail per level, as many levels as the
    tightest camera box needs): each tile is a crop of its parent, enlarged (SeedVR2), re-drawn at low `strength` so it
    gains fine detail in the same style, aligned to its parent, and given the parent's low frequencies exactly, so colours
    and shapes agree at every level and only fine detail is new. The render takes each pixel from the finest tile that
    covers it and fades levels in by screen-space pixel density, so detail arrives as the camera does and nothing pops.
    Every tile is its own cached stage. Needs ComfyUI (SeedVR2, Z-Image Turbo)."""
    levels: Union[Literal["auto"], int] = Field("auto", description="Levels of tiles below the frame: auto stops when the "
                                                                    "tightest camera box has a tile pixel for every output "
                                                                    "pixel; or a number (1-8)")
    ratio: float = Field(2.0, ge=1.3, le=4.0, description="The most detail one level adds to the one above (pixels per unit "
                                                          "of the frame). auto levels lower it so the levels share the gain "
                                                          "evenly; a smaller ratio means more levels and tiles, and no "
                                                          "moment where the picture is much softer than the screen")
    strength: float = Field(0.35, ge=0, le=0.9, description="How much each tile is re-drawn (img2img denoise): 0 keeps the "
                                                            "enlargement as it is, 0.3-0.5 invents fine detail (stitching, "
                                                            "creases, paper grain) without moving a shape")
    prompt: str = Field("", description="What the re-draw should add, in the picture's own words, e.g. 'hand-drawn ink, "
                                        "fine cross-hatching, stitched leather'. Added to a generic 'same style, fine "
                                        "detail' line")
    tile: float = Field(1.25, ge=1.0, le=2.0, description="A tile's resolution as a multiple of the beat's (1.25 = 2400 px "
                                                          "across for a 1920 beat): more means fewer, sharper tiles and a "
                                                          "slower build")
    lock: float = Field(2.5, ge=0.2, le=8.0, description="How firmly a tile agrees with its parent: the tile is made to match "
                                                          "the parent at every scale coarser than this many parent pixels "
                                                          "(colour, tone, where shapes are); finer than that it is its own. "
                                                          "Lower holds the parent's soft edges and detail too, so a tile "
                                                          "stays as soft as its parent; higher lets the tile move "
                                                          "mid-sized shapes")
    method: Literal["zimage", "qwen"] = Field("zimage", description="The re-draw: zimage (Z-Image Turbo img2img: keeps "
                                                                    "every shape where it is, fast; adds texture and "
                                                                    "creases, and draws what the prompt names where the "
                                                                    "picture already has the shape) or qwen "
                                                                    "(Qwen-Image-Edit asked to add fine detail: it "
                                                                    "understands the picture and draws laces and "
                                                                    "stitching, but also moves and reshapes things by "
                                                                    "several percent, which a tile cannot be made to agree "
                                                                    "with: ghosting. Experimental)")
    seed: Optional[int] = Field(None, description="Seed of the re-draw (default: the freeze's seed)")


class FreezeLayer(Model):
    """A subject that gets its own plane."""
    id: Optional[str] = None
    prompt: Optional[str] = Field(None, description="The subject as you would say it: 'the woman in the black coat', "
                                                    "'the people'. Every match is cut out (Florence-2 finds it, SAM 2.1 "
                                                    "cuts it out)")
    box: Optional[tuple[float, float, float, float]] = Field(None, description="Or a box [x0, y0, x1, y1] around it, 0-1 of "
                                                                                "the frozen frame (skips the search)")
    points: list[tuple[float, float]] = Field(default_factory=list, description="Points ON the subject, 0-1")

    @model_validator(mode="after")
    def _has_target(self):
        if not (self.prompt or self.box or self.points):
            raise ValueError("a layer needs a prompt, a box or points")
        return self


class FreezeLayers(Model):
    """Layered depth: the picture is cut into planes, back to front: a background plate with the subjects painted out
    (what was really behind them), and a plane per subject (or group of subjects at a similar depth) with its own
    smooth depth and a soft alpha edge. The camera then reveals true background behind a person instead of smearing
    the person, and a depth jump no longer leaves a halo or a double edge. The planes are cut from the same picture
    (and, with `detail`, the same tiles) at render time, so every level of a deep zoom is layered too."""
    subjects: Union[Literal["auto"], list[FreezeLayer]] = Field(
        "auto", description="auto: every person found on the frame (Florence-2 'people'); or the subjects to cut out")
    planes: int = Field(3, ge=1, le=8, description="At most this many subject planes: subjects at a similar depth share one")
    plate: str = Field("", description="What the empty background should look like where the subjects stood (added to "
                                       "'remove the people, continue the background in the same style'), e.g. 'the empty "
                                       "foggy street'")
    grow: int = Field(3, ge=0, le=60, description="How far (pixels of the frame at beat resolution) the hole in the "
                                                   "background plate extends past a subject's edge")
    feather: float = Field(1.5, ge=0, le=12, description="Softness of a subject's alpha edge (pixels at beat resolution)")
    seed: Optional[int] = Field(None, description="Seed of the background fill (default: the freeze's seed)")

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, v):
        if v is True or v == "auto":
            return {}
        if isinstance(v, list):
            return {"subjects": v}
        return v


class Freeze(Model):
    """A frozen moment: the beat is not generated but rendered from one frame, offline, in seconds. The frame is
    upscaled, given a depth map (Depth Anything V2) and the camera moves through it as a 2.5D parallax move along
    `camera` keys, so a crowd can stand still while the camera visits a couple's hands and feet, and the faces stay
    the faces of the frame. The clip joins the film like any generated beat (trim, crossfade, restore, locked, --only)."""
    from_: Optional[str] = Field(None, alias="from", description="Freeze the last frame of this beat (an earlier beat of "
                                                                 "the film, after its trim); or give `image:`")
    image: Optional[ImageRef] = Field(None, description="Freeze this image instead (a file, or any image input; "
                                                        "`beat_frame:` takes a frame of a beat)")
    pick: Literal["sharpest", "last"] = Field("sharpest", description="With `from`: `sharpest` takes the sharpest of the "
                                                                      "last `pick_window` frames (the very last of a "
                                                                      "moving shot is often motion-blurred, bad for "
                                                                      "close-ups), `last` the very last one. Sharpness is "
                                                                      "measured in the camera's tightest boxes")
    pick_window: int = Field(6, ge=1, le=48, description="How many of the last frames `pick: sharpest` looks at")
    upscale: float = Field(1.0, ge=1, le=4, description="Upscale the frame this many times before moving through it, "
                                                        "so crops stay sharp (a 3x crop of a 1920 frame needs 2). "
                                                        "1 = off")
    upscale_method: Literal["auto", "seedvr2", "lanczos"] = Field(
        "auto", description="seedvr2: SeedVR2 image restoration through ComfyUI (redraws fine detail; the model "
                            "downloads on first use). lanczos: a local detail-preserving resample, no model. auto: "
                            "seedvr2 when its weights are installed, else lanczos")
    camera: list[FreezeKey] = Field(default_factory=list, description="Camera keys over the beat. The camera rests on "
                                                                      "the first box until its t and on the last after "
                                                                      "its t; none: the whole frame, with the parallax")
    parallax: float = Field(0.6, ge=0, le=2, description="Strength of the 2.5D depth effect (0 = flat Ken Burns; the "
                                                         "subject plane stays put while nearer and farther things shift)")
    dolly: Optional[float] = Field(None, ge=0, le=3, description="Extra push-in of near things as the camera closes in "
                                                                 "(default follows `parallax`)")
    ease: FreezeEase = Field("inOutSine", description="How the camera travels between boxes. inOutSine/Quad/Cubic/Quart: "
                                                      "eased, resting at every key. smoother: eased with no jolt "
                                                      "at the stops (it settles into each hold and leaves it gently; "
                                                      "best with holds). flow: keeps moving through keys "
                                                      "(it rests only at keys with a hold)")
    depth_model: Literal["small", "base", "large"] = Field("small", description="Depth Anything V2 size (small is "
                                                                                  "Apache-2.0; base and large are CC-BY-NC)")
    blur: float = Field(0.0, ge=0, le=1, description="Motion blur: the shutter, as a fraction of a frame (0 = off, 0.5 = "
                                                     "180 degrees). Sub-frames are averaged")
    grain: float = Field(0.0, ge=0, le=0.2, description="Film grain laid over the render (0.01-0.03 is faint) so it "
                                                        "matches generated shots")
    seed: int = 7
    detail: Optional[FreezeDetail] = Field(None, description="Deep zoom: a pyramid of re-drawn tiles so a push to a 10-20x "
                                                              "close-up stays sharp at every scale (see FreezeDetail). "
                                                              "`detail: {}` for the defaults")
    layers: Optional[FreezeLayers] = Field(None, description="Experimental. Layered depth: background plate + a plane per subject, so "
                                                              "depth jumps have no halos and the camera reveals real "
                                                              "background behind people (see FreezeLayers). `layers: auto` "
                                                              "or a list of subjects")

    @field_validator("detail", mode="before")
    @classmethod
    def _detail_shorthand(cls, v):
        return {} if v is True or v == "auto" else v

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---- reveal + faces (engine/reveal.py, engine/faces.py): kept together so they merge cleanly ----------------------

class RevealRegion(Model):
    """One part of the picture that comes into colour. Describe it (`prompt`: found on the `at` frame by Florence-2),
    or point at it (`points` / `box` in 0-1 picture coordinates on the `at` frame); SAM 2.1 then follows it through
    the whole film, forwards and backwards."""
    id: str
    prompt: Optional[str] = Field(None, description="What to colour, as you would say it to a person: \"the woman's hand\", "
                                                    "\"the shoes of the woman and the man\". Every match on the `at` frame "
                                                    "is revealed (see `pick`, `within`)")
    points: list[tuple[float, float]] = Field(default_factory=list, description="Points ON the thing, 0-1 across and down the "
                                                                              "`at` frame (with or without a prompt or box)")
    negative_points: list[tuple[float, float]] = Field(default_factory=list, description="Points on what the mask must NOT take")
    box: Optional[tuple[float, float, float, float]] = Field(None, description="x0, y0, x1, y1 around it, 0-1 on the `at` "
                                                                              "frame (skips the prompt's search)")
    at: Union[RevealAt, list[RevealAt]] = Field(default_factory=RevealAt, description="The frame to find it on. A film of several "
                                                                                       "shots tracks a region only inside a shot it is found in "
                                                                                       "(a cut ends it): give one `at` per shot it must show in")
    pick: Union[Literal["all", "first", "largest", "smallest", "left", "right", "top", "bottom"], int] = Field(
        "all", description="When the prompt matches several things: all of them, one by rank (largest, left, ...) or by "
                           "index (0 is the first the search lists)")
    within: Optional[str] = Field(None, description="Keep only the matches inside the thing this names, e.g. prompt "
                                                    "\"hand\" within \"the woman in the long coat\". A prompt shaped \"the X's Y\" "
                                                    "or \"the Y of the X\" does this by itself")
    grow: int = Field(0, ge=-40, le=80, description="Widen (+) or shrink (-) the finished mask by this many pixels at film size")

    @property
    def seeds(self) -> list[RevealAt]:
        return self.at if isinstance(self.at, list) else [self.at]

    @model_validator(mode="after")
    def _has_target(self):
        if not (self.prompt or self.points or self.box):
            raise ValueError(f"reveal region '{self.id}': give a prompt, points or a box")
        return self


class Reveal(Model):
    """Colour that comes in where the camera looks, driven by scroll. The film is rendered once in full colour; the page
    shows everything in the `base` look, and each region's colour is brought in through a tracked mask, in the browser
    (a WebGL shader draws each frame of the film with its masks from the same frame). Without WebGL the colour film
    plays as it is; with reduced motion each region jumps to colour as its moment arrives."""
    base: str = Field("mono", description="What pixels that are not revealed look like: mono (black and white), dim (darker "
                                          "and muted), blur (soft focus in colour), or a hex colour such as \"#2a4a6a\" "
                                          "(a duotone from black through that colour to white)")
    regions: list[RevealRegion] = Field(..., min_length=1)
    keys: list[dict[str, float]] = Field(default_factory=list, description="Scroll progress of the section -> how revealed "
                                                                          "each region is (0-1), eased between keys: "
                                                                          "[{at: 0.4, her_hand: 0}, {at: 0.48, her_hand: 1}]. A region keeps "
                                                                          "its last value. Default: one region after another")
    cuts: list[float] = Field(default_factory=list, description="Times of the film's cuts, in seconds, when they can't be known "
                                                                "(a beats film knows its own; other films are searched for them)")
    feather: float = Field(6.0, ge=0, le=64, description="Softness of every mask's edge, in pixels at film size")
    ease: Literal["smooth", "linear"] = Field("smooth", description="How a region eases between two keys")
    tracker: Literal["large", "base_plus"] = Field("large", description="SAM 2.1 size: large (sharper, ~450 MB) or base_plus")
    strength: float = Field(1.0, ge=0, le=1, description="1: revealed pixels show the film's own colour; lower mixes the base "
                                                         "look back in")

    @field_validator("base")
    @classmethod
    def _base(cls, v):
        import re
        if v not in ("mono", "dim", "blur") and not re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v):
            raise ValueError("base is mono, dim, blur or a hex colour like #2a4a6a")
        return v

    @model_validator(mode="after")
    def _keys(self):
        ids = [r.id for r in self.regions]
        if len(set(ids)) != len(ids):
            raise ValueError("reveal: region ids must be unique")
        for k in self.keys:
            if "at" not in k:
                raise ValueError("reveal.keys: every key needs `at`")
            for name, v in k.items():
                if name != "at" and name not in ids:
                    raise ValueError(f"reveal.keys: '{name}' is not a region id ({', '.join(ids)})")
                if not 0 <= v <= 1:
                    raise ValueError(f"reveal.keys: {name} must be between 0 and 1")
        return self


class Faces(Model):
    """Face repair for generated video: faces above `min_size` are found in every frame, restored with GFPGAN v1.4, and
    blended back softly (and smoothed over time so nothing flickers)."""
    mode: Literal["restore"] = "restore"
    strength: float = Field(0.7, ge=0, le=1, description="How much of the restored face is blended in")
    min_size: int = Field(96, ge=16, le=2048, description="Faces smaller than this many pixels across are left alone")
    smooth: float = Field(0.6, ge=0, le=0.95, description="Temporal smoothing of the blend (higher: steadier, slower to follow)")


def _faces(v):
    if v in (None, False, "off", "none"):
        return None
    if v is True or v == "restore":
        return {"mode": "restore"}
    return v


# ---------------------------------------------------------------------------------------------------------------


# ---- camera moves on moving beats (engine/camera_guide.py): kept together so they merge cleanly --------------------

CameraBackend = Literal["auto", "ltx", "wan", "uni3c"]


class CameraMove(Model):
    """A keyed camera move on a generated (moving) beat: the same keys as a frozen moment's camera, but the people keep
    walking. The start image is given a depth map, the camera path is flown through it to make a guide video (the
    moving subjects softened so they stay free), and the video model generates the beat along that guide, so the camera
    does what the keys say instead of what the prompt hopes."""
    keys: list[FreezeKey] = Field(..., min_length=1, description="Camera keys over the beat: {t, box, hold} exactly as in a "
                                  "frozen moment (`freeze.camera`). The camera rests on the first box until its t and on "
                                  "the last after its t")
    ease: FreezeEase = Field("inOutSine", description="How the camera travels between boxes (as `freeze.ease`; `flow` keeps "
                                                     "moving through keys)")
    backend: CameraBackend = Field("auto", description="What generates the beat along the guide: ltx (LTX-2.3 IC-LoRA depth "
                                   "control, the depth guide a take uses), wan (Wan 2.2 Fun Control, the guide as the control "
                                   "video) or uni3c (Wan Uni3C camera controlnet; needs a model file that is not installed "
                                   "by default). auto: the one measured to follow the keys best (see docs/ENGINE.md)")
    subjects: str = Field("the people", description="Who is free to move, as you would say it to a person (found by "
                          "Florence-2, cut out by SAM 2.1). The guide fixes the camera and the static world and only "
                          "hints at where these are. Empty: nothing is freed (the guide pins everything, people included)")
    soften: float = Field(0.045, ge=0, le=0.3, description="How far the subjects are softened in the guide, as a share of the "
                          "frame width (a Gaussian blur of their own depth). 0 keeps their exact depth, which pins their "
                          "silhouettes too (they only slide with the camera); larger frees them more but tells the model "
                          "less about where they are")
    guide_strength: float = Field(1.0, ge=0, le=2, description="How strongly the guide steers the model (LTX: the IC-LoRA "
                                  "guide strength; Wan: Fun Control has no scale, so this is the Uni3C strength)")
    parallax: float = Field(0.5, ge=0, le=2, description="Depth effect of the guide's camera (as `freeze.parallax`): near "
                            "things shift against far ones as the camera moves, so the model sees a real camera move")
    dolly: Optional[float] = Field(None, ge=0, le=3, description="Extra push-in of near things (default follows parallax)")
    continues: bool = Field(False, description="Carry the previous beat's camera across the cut: this beat's camera starts "
                            "where the previous camera beat ended, with the speed it ended at (no ease to a stop at the "
                            "boundary), and it starts on that beat's last frame, graded to match")
    res: Optional[tuple[int, int]] = Field(None, description="Size the video model runs at (the frames are scaled to beat_res; "
                                           "ltx: multiples of 64, wan/uni3c: multiples of 16). Default: ltx about 1024x576 (more "
                                           "pixels let the subjects drift in tests; `beat_restore` adds the detail back), wan "
                                           "~1280x720")
    anchor: float = Field(0.6, ge=0, le=1, description="ltx: how firmly the pure-camera render of the start image (the picture "
                          "flown along the keys) is pinned as keyframes along the way, once a second and at the end. It keeps "
                          "what things look like and sharpens close-ups (in tests: Laplacian variance 48-63 against 29-48 "
                          "without, 66 in the pure render) and tightens the camera (0.8% against 1.3% zoom error). 0 = only "
                          "the first frame is pinned")
    match: Optional[float] = Field(None, ge=0, le=1, description="How far the generated frames are pulled back toward the base "
                                   "plate's tone and grain (the start image of the first beat of the chain, flown along the "
                                   "same camera): a video model drifts in contrast, haze and grain from clip to clip, and a "
                                   "cut shows it. 0 = off. Default: 0.7 for a beat in a chain of `continues` beats, else off")
    seed: Optional[int] = Field(None, description="Seed for the generation (default: the beat's motion_seed, then seed)")

    @model_validator(mode="before")
    @classmethod
    def _bare_keys(cls, v):
        return {"keys": v} if isinstance(v, list) else v


# ---------------------------------------------------------------------------------------------------------------


def _check_camera(b) -> None:
    """Validate a generated beat's `camera:` (keys inside the frame, going forward in time)."""
    c = b.camera
    ks = c.keys
    for i, k in enumerate(ks):
        x0, y0, x1, y1 = k.box
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError(f"beat '{b.id}': camera box {i} {list(k.box)} must be [x0, y0, x1, y1] inside 0-1 "
                             "with x0 < x1 and y0 < y1")
        if i and k.t <= ks[i - 1].t + ks[i - 1].hold - 1e-9:
            raise ValueError(f"beat '{b.id}': camera keys must go forward in time (key {i} at t={k.t} comes before "
                             f"the previous key's hold ends at {ks[i - 1].t + ks[i - 1].hold:g})")
    if ks[-1].t + ks[-1].hold > 1 + 1e-9:
        raise ValueError(f"beat '{b.id}': the last camera key's hold runs past the end of the beat")
    if c.continues and ks[0].t <= 0:
        raise ValueError(f"beat '{b.id}': with `continues` the camera starts where the previous beat's ended, so the first "
                         "key must come after t = 0")
    if b.trim:
        raise ValueError(f"beat '{b.id}': `trim` cannot be combined with `camera` (the keys are timed over the whole clip)")
    if b.end_image is not None:
        raise ValueError(f"beat '{b.id}': `end_image` cannot be combined with `camera` (the camera path decides the last frame)")


class Beat(Model):
    """One shot of a story film: a still generated from `prompt` (or taken from `image`), brought to life by `motion`."""
    id: str
    prompt: str = Field("", description="The opening frame, described like a photograph: subject, place, light, lens "
                                        "(not used by a frozen moment)")
    motion: str = Field("", description="What moves and how the camera moves, e.g. 'the door swings open, the camera pushes in'"
                                        " (not used by a frozen moment)")
    seconds: float = Field(4.0, ge=1, le=60, description="Length of the shot (1 to 10 generated; a frozen moment may run longer)")
    seed: int = 7
    image: Optional[ImageRef] = Field(None, description="Start from this image instead of generating it from `prompt`: "
                                                        "a file, or an image input (generate:, edit: ...)")
    end_image: Optional[ImageRef] = Field(None, description="The clip's last frame (same forms as `image`): the motion is "
                                                            "steered to land on it, e.g. a closed door ending open")
    strength: float = Field(1.0, ge=0.3, le=1.0, description="How tightly the clip holds the start image. Lower it "
                                                           "(0.7-0.85) when an action shot freezes on its first frame")
    motion_seed: Optional[int] = Field(None, description="Seed for the motion only, to re-roll a clip and keep its still")
    trim: float = Field(0.0, ge=0, description="Seconds cut from the start of the clip (an action shot that holds its "
                                               "first frame before moving). Re-uses the render: nothing is re-animated")
    video_model: Optional[VideoModel] = Field(None, description=VIDEO_MODEL_DOC + ". `strength` applies to ltx only")
    locked: bool = Field(False, description="Keep this beat's clip (and its storyboard still) as rendered, even when "
                                            "its prompt or motion changes; the rest of the film still builds around it")
    freeze: Optional[Freeze] = Field(None, description="A frozen moment instead of a generated clip: one frame, upscaled, "
                                                       "with a 2.5D camera moving through it, rendered offline in seconds "
                                                       "(see Freeze). prompt, motion, image and end_image are not used")
    camera: Optional[CameraMove] = Field(None, description="A keyed camera move on this moving beat (see CameraMove): "
                                                         "`camera: {keys: [{t: 0, box: [0,0,1,1]}, {t: 0.5, box: [...]}, ...]}`. "
                                                         "The crowd keeps moving, the camera does what the keys say. Needs an "
                                                         "`image` (or a `prompt` to make one); not for a frozen moment")

    @model_validator(mode="after")
    def _generated_or_frozen(self):
        if self.freeze is None:
            if not self.prompt or not self.motion:
                raise ValueError(f"beat '{self.id}': `prompt` and `motion` are required (or make it a frozen moment with `freeze:`)")
            if self.seconds > 10:
                raise ValueError(f"beat '{self.id}': a generated beat is 1 to 10 seconds (a `freeze:` beat may be longer)")
            if self.camera is not None:
                _check_camera(self)
            return self
        if self.camera is not None:
            raise ValueError(f"beat '{self.id}': `camera` moves a generated beat; a frozen moment has `freeze.camera`")
        f = self.freeze
        if bool(f.from_) == (f.image is not None):
            raise ValueError(f"beat '{self.id}': freeze needs exactly one of `from` (a beat id) and `image`")
        if f.from_ == self.id:
            raise ValueError(f"beat '{self.id}': freeze cannot take its own frame")
        for name in ("image", "end_image", "video_model", "motion_seed"):
            if getattr(self, name) is not None:
                raise ValueError(f"beat '{self.id}': `{name}` does not apply to a frozen moment (use freeze.image / freeze.from)")
        if self.strength != 1.0:
            raise ValueError(f"beat '{self.id}': `strength` does not apply to a frozen moment")
        ks = f.camera
        for i, k in enumerate(ks):
            x0, y0, x1, y1 = k.box
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                raise ValueError(f"beat '{self.id}': camera box {i} {list(k.box)} must be [x0, y0, x1, y1] inside 0-1 "
                                 "with x0 < x1 and y0 < y1")
            if i and k.t <= ks[i - 1].t + ks[i - 1].hold - 1e-9:
                raise ValueError(f"beat '{self.id}': camera keys must go forward in time (key {i} at t={k.t} comes before "
                                 f"the previous key's hold ends at {ks[i - 1].t + ks[i - 1].hold:g})")
        if ks and ks[-1].t + ks[-1].hold > 1 + 1e-9:
            raise ValueError(f"beat '{self.id}': the last camera key's hold runs past the end of the beat")
        return self


    # ---- faces
    restore: Optional[int] = Field(None, ge=480, le=2160, description="Run SeedVR2 over this beat's clip at this height "
                                   "(e.g. 1088) to clean grain and redraw fine detail, then scale it back to beat_res. "
                                   "Like the section's beat_restore but for one beat, e.g. a camera beat (rendered near "
                                   "1024 px) next to sharp frozen moments; slow (minutes per second of film)")
    faces: Optional[Faces] = Field(None, description="`restore`: repair the faces in this beat's clip (GFPGAN), after it is "
                                                     "generated. Off by default; or a mapping with strength, min_size, smooth")

    @field_validator("faces", mode="before")
    @classmethod
    def _faces_in(cls, v):
        return _faces(v)


class FilmScene(SceneBase):
    """AI film scrubbed by scroll. Blender blockout -> Z-Image keyframes -> LTX-2.3 -> encode. Or `beats`: a story told
    in separate shots, each a generated still animated by LTX-2.3, joined with short crossfades; steps can pin
    themselves to a beat with state: {beat: <id>}."""
    type: Literal["film"] = "film"
    video: Optional[str] = Field(None, description="Use an existing film instead of generating one")
    shot: dict[str, Any] = Field(default_factory=dict,
        description="Generation settings: fps, duration, preview_res, blockout {preset|file}, keyframes, ltx, upscale")
    take: Optional[Take] = Field(None, description="A one-take film described in the spec (world, camera, product) instead of `shot`")
    beats: list[Beat] = Field(default_factory=list, description="A story film shot by shot (instead of `shot` / `take`)")
    beat_res: tuple[int, int] = Field((1920, 1088), description="beats: render size (multiples of 32)")
    beat_fade: float = Field(0.4, ge=0, le=2, description="beats: crossfade between shots, in seconds")
    beat_restore: Optional[int] = Field(None, description="beats: run SeedVR2 over the finished film at this height "
                                                          "(e.g. 1088) to clean grain and redraw fine detail; slow")
    gop: int = 6
    # ---- the one-take page (engine/journey.py)
    journey: Optional["Journey"] = Field(None, description="The page as one camera journey (see Journey): the world "
                                         "described once and an ordered list of stops, each a place in it that shows "
                                         "its blocks (hero, features, stats, quote, faq, cta ...) laid out to sit with the "
                                         "picture. The engine makes the `beats` (a frozen moment at every stop, a camera "
                                         "move between stops), the scroll timing and the page markup from it; do not "
                                         "write `beats`, `steps` or `length` yourself")
    # ---- reveal + faces
    reveal: Optional[Reveal] = Field(None, description="Scroll-driven colour: the film is full colour, the page shows the "
                                                       "`base` look and brings colour into tracked regions as you scroll")
    faces: Optional[Faces] = Field(None, description="`restore`: repair the faces in the whole film (GFPGAN) before it is "
                                                     "encoded; beats can set it per beat. Off by default")
    # ---- type in the world (steps with `place: {kind: behind | surface | sky}`)
    depth_model: Optional[Literal["small", "base", "large"]] = Field(
        None, description="Steps with in-world type (`place: {kind: ...}`): the Depth Anything V2 size that measures the film's "
                          "depth per frame. small is Apache-2.0 (default); base/large are sharper but CC-BY-NC (non-commercial)")

    @field_validator("faces", mode="before")
    @classmethod
    def _faces_in(cls, v):
        return _faces(v)

    @model_validator(mode="after")
    def _journey_beats(self):
        """A journey is written as stops; the film it plays is made of beats the engine derives from them (kept apart
        from the spec as written: `model_dump` leaves them out, so saving a spec never freezes them into it)."""
        if self.journey is not None:
            from .journey import expand
            expand(self)
        return self

    @model_serializer(mode="wrap")
    def _journey_dump(self, handler, info):
        d = handler(self)
        if self.journey is not None and isinstance(d, dict) and info.include is None:   # a field list (the compiler's) keeps them
            for k in ("beats", "steps", "length", "beat_fade", "beat_restore", "take"):
                d.pop(k, None)
        return d


class ArtworkScene(SceneBase):
    """Any image, drawn and painted in stages as you scroll."""
    type: Literal["artwork"] = "artwork"
    layout: Literal["overlay", "split", "cards"] = "split"
    image: ImageRef
    focus: Union[Literal["auto"], list[tuple[float, float]]] = Field(
        "auto", description="Where drawing starts: 'auto' (faces, then saliency) or [(x, y)] in 0-1 image coords")
    stages: list[Literal["guides", "lines", "value", "underpaint", "colour"]] = Field(
        default_factory=lambda: ["guides", "lines", "value", "underpaint", "colour"],
        description="One stage per step after the intro step, in order")
    width: int = Field(1800, description="Working width of the layers in pixels")
    line_density: float = Field(1.0, description="More (>1) or fewer (<1) contour strokes")
    underpaint: str = Field("#5a3a22", description="Monochrome underpainting colour")
    paper: str = Field("#efe8da", description="Paper colour")
    caption: Optional[str] = Field(None, description="Label under the canvas")


class Level(Model):
    preset: str = Field(..., description="Level generator, see engine/scenes/scene3d.py PRESETS")
    params: dict[str, Any] = Field(default_factory=dict)


class Scene3DScene(SceneBase):
    """Live 3D: a zoom journey through nested levels built from generator presets (or glTF models)."""
    type: Literal["scene3d"] = "scene3d"
    layout: Literal["overlay", "split", "cards"] = "cards"
    style: Literal["glow", "solid"] = Field("glow", description="glow: additive fluorescence; solid: lit PBR")
    levels: list[Level]
    zoom: float = Field(14.0, description="Scale factor between levels")
    background: Optional[str] = None
    bloom: tuple[float, float, float] = (0.5, 0.45, 0.12)
    final: Optional[str] = Field(None, description="Extra beat on the last level, e.g. 'dock' for molecule docking")
    dust: str = Field("#8fb8d8", description="Colour of the background dust particles")
    seed: int = Field(7, description="Seed for the procedural presets")


class SequenceScene(SceneBase):
    """A 3D model rendered to an image sequence (turntable, explode, assemble) and scrubbed by scroll."""
    type: Literal["sequence"] = "sequence"
    model: Optional[str] = Field(None, description="glTF/GLB, OBJ, FBX or STL: a project file or an https URL (downloaded "
                                                   "once). Omit, or write 'product', to use site.product")
    credit: Optional[str] = Field(None, description="Attribution shown in the footer (e.g. for CC-BY models)")
    frames: int = 120
    size: tuple[int, int] = (1920, 1080)
    samples: int = 96
    keys: list[dict[str, Any]] = Field(default_factory=lambda: [
        {"t": 0, "yaw": -35, "pitch": 18, "explode": 0, "zoom": 1.0},
        {"t": 0.5, "yaw": 60, "pitch": 28, "explode": 1, "zoom": 1.1},
        {"t": 1, "yaw": 160, "pitch": 14, "explode": 0, "zoom": 0.95}],
        description="Camera/explode keys over progress: yaw/pitch degrees, explode 0-1, zoom")
    background: Optional[str] = Field(None, description="Backdrop colour (defaults to the theme background)")
    hdri: str = Field("studio", description="Blender studio light: studio, forest, city, courtyard, night, interior, sunrise, sunset")


# ---------------------------------------------------------------- inside: the product as the set (engine/inside.py)

class InsideStop(Model):
    """One stop of the camera inside the product: it flies to a named part (or a point), lands there at macro scale
    with a shallow depth of field, and the stop's copy (the step in the same position) arrives with it. Only `part`
    (or `point`) is needed; everything else has a default that suits any model with named parts."""
    part: Optional[str] = Field(None, description="Glob on the part, mesh or assembly name, case-insensitive: 'driver*', "
                                                  "'*magnet*', 'Housing/*' (see `studio product <project> --parts`). Several "
                                                  "parts are framed together. Use `point` for a model with no named parts")
    point: Optional[tuple[float, float, float]] = Field(
        None, description="Instead of a part: a point inside the product, x y z in 0-1 of its bounds (x left to right, y "
                          "front to back, z bottom to top)")
    aim: tuple[float, float, float] = Field(
        (0.5, 0.5, 0.5), description="Where in the part's own bounds the camera looks, x y z in 0-1 (z 1 = its top "
                                     "surface): look at one end of a long part, or its top")
    label: Optional[str] = Field(None, description="Name for this stop in `studio inside` and in alt text "
                                                   "(default: the part's name)")
    span: Optional[float] = Field(None, gt=0, description="How much fills the frame at the stop: the width of the view at "
                                                          "the focal plane, in millimetres of the real product (macro: "
                                                          "8-40). Default: the part with a margin, never wider than 40% "
                                                          "of the product")
    lens: Optional[float] = Field(None, gt=4, description="Focal length in mm (default: the scene's `lens`). Longer "
                                                          "flattens and blurs more")
    fstop: Optional[float] = Field(None, gt=0.5, description="Aperture (default: the scene's `fstop`). 1.8 is a razor "
                                                             "thin plane in focus, 8 keeps most of the part sharp")
    focus: Optional[str] = Field(None, description="Glob on the part the focus is held on (default: the stop's part). "
                                                   "Rack focus by naming a part in front of or behind it")
    yaw: Optional[float] = Field(None, description="Which side the camera comes from, degrees (0 the front, 90 the right "
                                                   "side). Default: chosen per stop, the clearest way in, close to the "
                                                   "previous stop's side")
    pitch: Optional[float] = Field(None, ge=-85, le=89, description="Camera height above the horizon, degrees (default: "
                                                                    "chosen, 15-40)")
    roll: float = Field(0.0, description="Tilt of the horizon at the stop, degrees (a few degrees reads as handheld/"
                                         "cinematic)")
    explode: Optional[float] = Field(None, ge=0, le=1.5, description="How far the parts are pulled apart at this stop "
                                                                     "(default: the scene's `explode`); opens a closed "
                                                                     "assembly so the camera can enter")
    hold: float = Field(0.8, gt=0, description="Scroll distance, in screens, the camera rests here while the copy is read")
    travel: float = Field(1.4, gt=0, description="Scroll distance, in screens, of the flight that arrives at this stop")


class InsideScene(SceneBase):
    """The product as the set: the camera flies into the product and the page happens inside it (between the layers of
    a board, past the cone and magnet of a speaker, along a keyboard's switches). Each feature is a stop: the camera
    lands at a named part with a macro lens and a shallow depth of field, and the copy (the steps, in order) arrives
    with it. Rendered offline by Cycles from the site's product (`site.product`: any model with named parts), a frame
    per slice of the flight, and scrubbed by scroll like a sequence. Parts between the camera and the stop's part
    dissolve (a cutaway) so the camera can see and travel through the assembly.

    Copy: leading steps with `intro: true` are shown over the opening wide shot; the next steps are matched to the
    stops in order; steps after those are shown over the pull-back. `studio inside <project>` prints the plan (which
    parts each stop found, where the copy sits) and renders a still of any stop."""
    type: Literal["inside"] = "inside"
    layout: Literal["overlay"] = Field("overlay", description="overlay only: the camera is pinned and the copy arrives "
                                                              "over it")
    length: float = Field(0.0, description="Scroll distance in screens (0: the sum of the stops' travel and hold, plus "
                                           "the opening and closing shots)")
    model: Optional[str] = Field(None, description="Model file or https URL; omit, or write 'product', to use site.product")
    credit: Optional[str] = Field(None, description="Attribution shown in the footer (for a model that is not site.product)")
    stops: Optional[list[InsideStop]] = Field(
        None, description="The camera's stops, in order. Omit for automatic stops: as many as there are copy steps (5 "
                          "without any), the model's most distinct named parts in a tour order")
    establish: bool = Field(True, description="Open on a wide shot of the whole product, then dive in")
    outro: Literal["wide", "stay"] = Field("wide", description="wide: pull back to the whole product after the last stop "
                                                               "(room for a closing step); stay: end at the last stop")
    lens: float = Field(60.0, gt=4, description="Focal length in mm at the stops (the opening shot uses a wider lens)")
    fstop: float = Field(11.0, gt=0.5, description="Aperture at the stops, for the real product: this is macro, where f/2.8 leaves only a sliver in focus and f/11 keeps a part sharp with the rest falling softly away; f/16 keeps most in focus")
    explode: float = Field(0.0, ge=0, le=1.5, description="Spread of the parts at every stop unless it sets its own")
    cutaway: bool = Field(True, description="Parts between the camera and the stop's part dissolve while the camera is "
                                            "behind them, so it can see (and fly) inside a closed product")
    density: float = Field(18.0, gt=1, description="Rendered frames per screen of scroll. 18 is smooth on desktop; "
                                                   "lower renders faster and steps more")
    size: tuple[int, int] = Field((1600, 900), description="Frame size (a second set at 960 px wide is made for phones)")
    samples: int = Field(64, ge=4, le=4096, description="Cycles samples per frame (denoised)")
    offset: float = Field(0.2, ge=0, le=0.4, description="How far the stop's part sits off the centre of the frame, as a "
                                                          "share of its width, towards `side` (the copy has the other "
                                                          "side). 0 centres it")
    hdri: str = Field("studio", description="Blender studio light the interior reflects: studio, city, courtyard, forest, "
                                            "interior, night, sunrise, sunset")
    ambient: float = Field(0.25, ge=0, le=4, description="Strength of that light on the scene (low: the camera's own lamp "
                                                         "lights the macro shot)")
    lamp: float = Field(1.0, ge=0, le=10, description="Strength of the lamp that travels with the camera")
    lamp_color: str = Field("#ffe8d0", description="Colour of the camera lamp, hex")
    rim: float = Field(1.0, ge=0, le=10, description="Strength of the light behind the stop's part (edges, translucent "
                                                     "materials glow)")
    exposure: float = Field(0.0, ge=-4, le=4, description="Exposure in stops")
    background: Optional[str] = Field(None, description="Colour of the void beyond the product (hex; default: the "
                                                        "theme background)")
    vignette: float = Field(0.35, ge=0, le=1, description="Darkening towards the corners")
    grain: float = Field(0.02, ge=0, le=0.2, description="Film grain")
    light: list["InsideLight"] = Field(default_factory=list, description="The light changing along the flight: keys over "
                                       "the scene's progress (0-1, as `studio inside` prints the stops' rests), eased "
                                       "between keys: evening to lamplight to lights out. A key sets any of exposure, "
                                       "ambient, lamp, rim, lamp_color; what it leaves out stays the scene's. Empty: "
                                       "one light for the whole flight")

    @model_validator(mode="after")
    def _stops(self):
        for i, st in enumerate(self.stops or []):
            if (st.part is None) == (st.point is None):
                raise ValueError(f"inside '{self.id}': stop {i + 1} needs exactly one of `part` and `point`")
        ats = [k.at for k in self.light]
        if ats != sorted(ats):
            raise ValueError(f"inside '{self.id}': light keys must go forward (`at` in increasing order)")
        return self


class InsideLight(Model):
    """One key of an inside flight's light, at a point of the scene's progress. Unset fields follow the scene's own."""
    at: float = Field(..., ge=0, le=1, description="Scene progress, 0-1")
    exposure: Optional[float] = Field(None, ge=-6, le=4, description="Exposure in stops")
    ambient: Optional[float] = Field(None, ge=0, le=4, description="Strength of the studio light")
    lamp: Optional[float] = Field(None, ge=0, le=10, description="Strength of the lamp that travels with the camera")
    rim: Optional[float] = Field(None, ge=0, le=10, description="Strength of the light behind the stop's part")
    lamp_color: Optional[str] = Field(None, description="Colour of the camera lamp, hex")

    @field_validator("lamp_color")
    @classmethod
    def _hex(cls, v):
        if v is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise ValueError("lamp_color is a hex colour like #ffe2c0")
        return v


class ShowroomScene(SceneBase):
    """The real product, live in the page: three.js renders the product's normalised GLB with studio environment
    lighting and a soft shadow; scroll turns, explodes and zooms it along `keys`, and the pointer nudges the view."""
    type: Literal["showroom"] = "showroom"
    layout: Literal["overlay", "split", "cards"] = "cards"
    model: str = Field("product", description="'product' (site.product) or a model file/URL in any product format")
    keys: list[dict[str, Any]] = Field(default_factory=lambda: [
        {"t": 0, "yaw": -35, "pitch": 18, "explode": 0, "zoom": 1.0},
        {"t": 0.5, "yaw": 50, "pitch": 26, "explode": 1, "zoom": 0.9},
        {"t": 1, "yaw": 160, "pitch": 12, "explode": 0, "zoom": 1.05}],
        description="Over scene progress: yaw/pitch degrees (yaw 0 is the front), explode 0-1, zoom")
    background: Optional[str] = Field(None, description="Colour behind the product (default: the theme background); "
                                                        "'transparent' shows the section's backdrop")
    lighting: Literal["studio", "soft", "contrast"] = Field(
        "studio", description="studio: environment light plus a key; soft: even, low-contrast; contrast: a hard key and rim")
    exposure: float = Field(1.0, gt=0, description="Tone-mapping exposure")
    shadow: bool = Field(True, description="Soft shadow on an invisible floor")
    spin: float = Field(0.0, description="Idle turn in degrees per second on top of the keys (0: scroll only)")
    poster: bool = Field(True, description="Render a Cycles still shown until the live model has loaded (and without WebGL)")


class ParallaxScene(SceneBase):
    """Photos turned into 2.5D camera moves with an estimated depth map; one photo per step."""
    type: Literal["parallax"] = "parallax"
    layout: Literal["overlay", "split", "cards"] = "cards"
    move: Literal["dolly", "pan", "orbit", "rise"] = Field("dolly", description="Default camera move for each photo")
    moves: list[Literal["dolly", "pan", "orbit", "rise"]] = Field(default_factory=list, description="Per-photo moves, in step order")
    strength: float = Field(1.0, description="Depth effect amount")
    depth_model: Literal["small", "base", "large"] = Field(
        "small", description="Depth Anything V2 size. small is Apache-2.0; base/large are sharper but CC-BY-NC (non-commercial)")
    width: int = Field(2560, description="Max photo width served to desktop browsers")


class VectorScene(SceneBase):
    """A logo or line drawing whose strokes draw themselves, then fill. From an SVG, or a raster image vectorised
    with vtracer (engravings, illustrations, logos)."""
    type: Literal["vector"] = "vector"
    layout: Literal["overlay", "split", "cards"] = "split"
    svg: Optional[str] = Field(None, description="SVG file (project path or https URL)")
    image: Optional[ImageRef] = Field(None, description="Raster image to vectorise when there is no SVG")
    order: Literal["center", "left", "top", "document"] = Field("center", description="Which strokes draw first")
    colors: Literal["original", "ink", "accent"] = Field("original", description="Fill colours: as traced, theme ink, or theme accent")
    detail: float = Field(1.0, description="Vectorising detail: higher keeps smaller specks (more paths, heavier page)")
    threshold: int = Field(140, description="Raster images: grey level below which a pixel counts as ink (0-255)")
    max_width: int = Field(2000, description="Raster images are traced at this width")
    background: Optional[str] = Field(None, description="Canvas colour behind the drawing (defaults to the theme)")


class ChartScene(SceneBase):
    """A data story: a chart that draws, zooms, highlights and annotates itself as the steps scroll past.
    Each step's `state` says what to show: {show: [series], focus: [series], x: [x0, x1], y: [y0, y1],
    reveal: true (draw the lines across this step), marks: [{series, x, label}]}."""
    type: Literal["chart"] = "chart"
    layout: Literal["overlay", "split", "cards"] = "split"
    data: str = Field(..., description="CSV file (project path or https URL), long format: one row per (series, x, y)")
    x: str = Field(..., description="Column for the x axis (numbers or years)")
    y: str = Field(..., description="Column for the y axis")
    series: Optional[str] = Field(None, description="Column that names each line")
    include: list[str] = Field(default_factory=list, description="Series to load (empty = all, capped at 12)")
    kind: Literal["line", "area", "bar", "scatter"] = Field("line", description="bar: grouped bars per x; scatter: dots")
    y_scale: Literal["linear", "log"] = "linear"
    y_label: Optional[str] = None
    unit: str = Field("", description="Unit after values, e.g. ' GW' or '%'")
    format: Literal["auto", "compact", "percent", "integer"] = Field(
        "auto", description="Number style: compact (1.2k, 3.4M), percent (adds %), integer, or auto")
    source: Optional[str] = Field(None, description="Data credit shown under the chart and in the footer")
    colors: list[str] = Field(default_factory=list, description="Series colours in `include` order (defaults to the theme)")
    callouts: list[dict[str, Any]] = Field(default_factory=list,
        description="Marks computed from the data at build time, so numbers in the story are the data's: "
                    "[{series, at: max | min | first | last | <x value>, label: 'text with {y} and {x}', step: <index>}]. "
                    "Each becomes a mark on that step (default: the last step).")


class Route(Model):
    id: str
    points: list[tuple[float, float]] = Field(..., description="[lng, lat] waypoints")
    color: Optional[str] = None
    geodesic: bool = Field(False, description="Bend each leg along the great circle (flights)")


class Marker(Model):
    lng: float
    lat: float
    label: str


class MapScene(SceneBase):
    """A geographic journey on a live vector map. Each step's `state` moves the camera and draws routes:
    {center: [lng, lat], zoom, pitch, bearing, routes: {route_id: 0-1}}. Tiles come from OpenFreeMap (no key)."""
    type: Literal["map"] = "map"
    layout: Literal["overlay", "split", "cards"] = "cards"
    style: str = Field("https://tiles.openfreemap.org/styles/liberty", description="MapLibre style URL")
    dark: bool = Field(False, description="Darken and desaturate the base map to sit under a dark theme")
    routes: list[Route] = Field(default_factory=list)
    markers: list[Marker] = Field(default_factory=list)


class SplatKey(Model):
    t: float = Field(..., description="Scene progress 0-1")
    at: tuple[float, float, float] = Field(..., description="Camera position, in the scan's own coordinates")
    look: tuple[float, float, float] = Field(..., description="Point the camera looks at")


class SplatScene(SceneBase):
    """A real place, scanned: a Gaussian splat the camera flies through as you scroll. Bring a scan from any
    phone app or trainer as .ply (3D Gaussian Splatting layout), .spz, or a gsplat .pt checkpoint; the build trims
    it and writes a small .spz the page streams. `studio build` logs the scan's bounds to place the camera keys."""
    type: Literal["splat"] = "splat"
    source: str = Field(..., description="Scan file: project path or https URL (.ply, .spz, .pt)")
    credit: Optional[str] = Field(None, description="Attribution shown in the footer")
    max_splats: int = Field(600_000, description="Keep the N most opaque splats (page weight ~16 bytes each)")
    min_opacity: float = Field(0.04, description="Drop splats fainter than this")
    max_scale: float = Field(0.0, description="Drop splats longer than this (scene units) on any axis: the smears scans leave in the air; 0 keeps all")
    crop: Optional[tuple[float, float, float, float, float, float]] = Field(None, description="Keep only x0 y0 z0 x1 y1 z1")
    sh: int = Field(1, ge=0, le=3, description="Spherical-harmonic degree to keep (view-dependent colour); 0 is smallest")
    up: tuple[float, float, float] = Field((0, 0, 1), description="Which way is up in the scan")
    fov: float = Field(60.0, description="Vertical field of view in degrees")
    keys: list[SplatKey] = Field(..., min_length=2, description="Camera path over scene progress")
    background: Optional[str] = Field(None, description="Colour behind the splats (defaults to the theme background)")


class TypeScene(SceneBase):
    """Kinetic typography driven by scroll."""
    type: Literal["type"] = "type"
    mode: Literal["reveal", "stack", "swap", "scale", "weight"] = Field(
        "reveal", description="reveal: words light up in reading order; stack: lines slam in; swap: one word rolls "
                              "through `words`; scale: one phrase settles then bursts; weight: words grow from thin and "
                              "faint to heavy and solid in reading order (a variable display face; ' / ' breaks lines)")
    text: str = Field("", description="reveal/scale/weight: the passage; swap: the fixed part")
    words: list[str] = Field(default_factory=list, description="swap: the words that cycle")
    weights: list[int] = Field(default_factory=lambda: [200, 800], min_length=2, max_length=2,
                               description="weight: the display face's weight at the start and at the end")
    length: float = 3.0
    size: Literal["passage", "display"] = Field(
        "passage", description="passage: reading size, left-aligned. display: a headline, bigger and centred")



class CodeFile(Model):
    """One file on the route through the codebase."""
    path: str = Field(..., description="Shown as the file's title, e.g. app/Models/User.php")
    code: Optional[str] = Field(None, description="The source. For kind: edit, start each line with '+' (added), "
                                                  "'-' (removed) or ' ' (unchanged), like a diff")
    file: Optional[str] = Field(None, description="Read the source from this project file instead of `code`")
    kind: Literal["read", "edit", "run"] = Field(
        "read", description="read: flies past as the agent reads it; edit: a stop where the diff applies itself as you "
                            "scroll; run: a terminal stop whose output prints line by line")
    label: Optional[str] = Field(None, description="Tag over the file (default: Read / Edit / the command for run)")
    lang: Optional[str] = Field(None, description="Highlighting: php, ts, tsx, js, py, go, rust, sh... (default: from the extension)")
    weight: float = Field(1.0, description="Share of the scroll this file gets, relative to the others of its kind")
    todo: Optional[str] = Field(None, description="An item on the agent's todo list, ticked when this file is done")


class CodeTerminal(Model):
    """The agent's prompt box the scene opens on; the camera dives through it into the code."""
    logo: str = Field("", description="Wordmark over the prompt, e.g. 'opencode'; split as dim|bright with '|', e.g. 'open|code'")
    prompt: str
    agent: str = "Build"
    model: str = ""
    provider: str = ""
    hints: list[str] = Field(default_factory=lambda: ["tab switch agent", "ctrl+p commands"])


class CodeScene(SceneBase):
    """Fly through a codebase in live 3D, following an agent at work: the scene opens on its prompt, dives into the
    files it reads, stops at each edit while the diff applies itself, and ends on the test run. Steps can pin
    themselves to the route with state: {file: <path>} (or 'terminal' / 'outro') instead of `at`."""
    type: Literal["code"] = "code"
    terminal: Optional[CodeTerminal] = None
    files: list[CodeFile] = Field(..., min_length=1, description="The route, in order")
    tree: list[str] = Field(default_factory=list, description="More paths in the project, drawn around the route so "
                                                              "it reads as a whole codebase")
    length: float = 14.0


# ---------------------------------------------------------------- miniature worlds (scene type `diorama`, engine/diorama/)

DIORAMA_KINDS = ("harbour", "town", "desk", "factory", "studio")


class DioramaProp(Model):
    """One extra thing set on the diorama by hand, beside what the world generates."""
    kind: str = Field(..., description="A prop of the kit: tree, pine, bush, rock, house, shop, cafe, warehouse, "
                                       "lamp, bench, fence, crate, barrel, flag, container, boat, windmill ... (the "
                                       "full vocabulary is in docs/miniature.md)")
    at: tuple[float, float] = Field(..., description="Where, in world units from the middle (x to the right, z towards the viewer)")
    turn: float = Field(0.0, description="Degrees the front is turned (0 faces the viewer)")
    scale: float = 1.0
    color: Optional[str] = Field(None, description="Main colour (roof, hull, body), hex")


class DioramaPlace(Model):
    """A place on the diorama: where the camera dives to and where one step's content sits. The place gets a hero
    prop, a sign with its name, a little set dressing around it and a pin in the orbit view."""
    name: str = Field(..., description="The name on the sign and the pin")
    kind: Optional[str] = Field(None, description="The hero prop. harbour: lighthouse, crane, warehouse, stall, office, "
                                "ferry, windmill, shop, cafe. town: clocktower, shop, cafe, windmill, stall, office, "
                                "fountain. desk: laptop, mug, books, plant, lamp, monitor, notebook. factory: tank, "
                                "chimney, conveyor, robot, warehouse, office, silo. studio: easel, softbox, camera, "
                                "monitor, speaker, sofa, shelf, plant. Unset: the next one the world suggests")
    where: Optional[Union[str, tuple[float, float]]] = Field(
        None, description="Where on the world: coordinates [x, z] in world units from the middle, or words: a compass "
                          "point (north is the back, south the front: 'north-east', 'south'), 'centre', 'edge', or one "
                          "of the world's own spots (harbour: hill, yard, plaza, pier, bay, village, quay; the "
                          "others in docs/miniature.md). Unset: the world's own spot for this kind")
    step: Optional[int] = Field(None, ge=0, description="Which of the scene's steps (0-based) lives here. Unset: the "
                                "places take the steps in order, skipping a leading intro step")
    side: Optional[Literal["left", "right"]] = Field(None, description="Which side of the screen the place sits on once "
                                                     "the camera has dived to it (the copy takes the other). Unset: opposite the card column")
    sign: Optional[str] = Field(None, description="Text on the little sign at the place (default: the name)")
    scale: float = Field(1.0, gt=0, description="Size of the hero prop")
    color: Optional[str] = Field(None, description="Main colour of the hero prop, hex")


class DioramaWorld(Model):
    """The world, described once. The engine lays out the ground (water, roads, hills, paving), the scenery and the
    places' dressing from this and the seed; the same spec always gives the same world."""
    kind: Literal["harbour", "town", "desk", "factory", "studio"] = Field(
        "harbour", description="The kind of world: sets the ground plan, the scenery and the prop vocabulary")
    seed: int = Field(7, description="Seed for the layout: another seed is another arrangement of the same kind of world")
    size: Optional[float] = Field(None, ge=16, le=60, description="Width of the diorama in world units (a house is about 2). Unset: 30 for a harbour or town, 22 for a desk or studio, 26 for a factory")
    base: Optional[Literal["round", "square"]] = Field(
        None, description="The shape of the base it stands on (default: round for harbour and town, square for the rest)")
    palette: list[str] = Field(default_factory=list, description="Hex colours for roofs, hulls and containers, replacing the world's own (2-8)")
    density: float = Field(1.0, ge=0, le=2.0, description="How much scenery fills the world: trees, houses, boats, lamps")
    props: list[DioramaProp] = Field(default_factory=list, description="Extra props set by hand")


class DioramaCamera(Model):
    """How the camera moves: it orbits the whole diorama, dives to each place, and lifts back out."""
    orbit: Literal["auto", "cw", "ccw"] = Field(
        "auto", description="Which way it travels round the world between places: the short way, or always "
                            "clockwise / counter-clockwise (seen from above)")
    pitch: float = Field(36.0, ge=10, le=80, description="Degrees above the horizon in the orbit view")
    dive_pitch: float = Field(21.0, ge=6, le=60, description="Degrees above the horizon once it has dived to a place")
    fov: float = Field(30.0, ge=14, le=60, description="Lens in degrees: narrow flattens the world into a macro photograph")
    dive: float = Field(1.0, ge=0.4, le=2.0, description="How close the dive lands (above 1 is closer)")
    hold: float = Field(0.5, ge=0.1, le=0.9, description="Share of each step's scroll the camera rests at its place; the rest is travel")
    drift: float = Field(1.0, ge=0, le=3, description="The camera's idle breathing, and how far the pointer can turn it (0: still)")


class DioramaLook(Model):
    """The miniature look: shallow tilt-shift depth of field, high soft sun, toy saturation."""
    tilt_shift: float = Field(1.0, ge=0, le=2.5, description="Depth-of-field strength: 0 is sharp everywhere; 1 reads "
                                                             "as a macro lens on a model; above 1 is extreme")
    saturation: float = Field(1.15, ge=0.5, le=2.0, description="Colour boost (toys are a little too colourful)")
    sun: Literal["morning", "noon", "golden", "dusk"] = Field(
        "golden", description="Time of day: the sun's height and warmth, the length of the shadows")
    table: Optional[str] = Field(None, description="Colour of the surface the diorama stands on (default: the theme background)")
    grain: float = Field(0.03, ge=0, le=0.2, description="Film grain")
    vignette: float = Field(0.25, ge=0, le=1.0, description="Darkening towards the corners")


class DioramaScene(SceneBase):
    """A miniature world: a tilt-shift diorama (a tiny harbour town, a desk, a factory floor, a studio) rendered live in
    the page. Scrolling orbits the camera round the whole thing, dives to a place where that step's content sits,
    lifts back out and travels to the next. Steps are the places' content: the first step may be an `intro` (the
    world seen whole), the rest take the places in order (or a place names its own with `step`)."""
    type: Literal["diorama"] = "diorama"
    layout: Literal["overlay", "split", "cards"] = "cards"
    world: DioramaWorld = Field(default_factory=DioramaWorld)
    places: list[DioramaPlace] = Field(..., min_length=1)
    camera: DioramaCamera = Field(default_factory=DioramaCamera)
    look: DioramaLook = Field(default_factory=DioramaLook)
    length: float = 10.0

    @model_validator(mode="after")
    def _windows(self):
        # overlay layout: a step's caption is on screen while the camera rests at its place (and a little around it)
        if self.layout == "overlay" and self.steps and any(s.at is None for s in self.steps):
            total = sum(s.length for s in self.steps) or 1.0
            acc = 0.0
            for s in self.steps:
                a, b = acc / total, (acc + s.length) / total
                acc += s.length
                if s.at is None:
                    w = b - a
                    s.at = (round(a + w * 0.12, 4), round(b - w * 0.12, 4))
        return self


# ---- light as the scroll (engine/scenes/light.py, engine/light.py, runtime/src/players/light.ts): kept together ------

class LightTime(Model):
    """One time of day of a `light` scene. A bare string is a named preset (`dawn`, `morning`, `noon`, `afternoon`,
    `golden-hour`, `sunset`, `blue-hour`, `night`, `overcast`, `storm`; `engine/light_presets.py`) or, when it is not
    one, free text describing the light."""
    id: Optional[str] = Field(None, description="Name to pin steps to (`state: {time: <id>}`); default: the preset's "
                                                "name, else the first words of the prompt")
    preset: Optional[str] = Field(None, description="A named time of day: dawn, sunrise, morning, noon, afternoon, "
                                                    "golden-hour, sunset, blue-hour, night, overcast, storm. It supplies the "
                                                    "light's wording, the clock, the mist and whether lamps are on")
    prompt: Optional[str] = Field(None, description="Free text describing this light ('low green storm light, the sun "
                                                    "breaking through on the left, wet stone'). With a preset it is added "
                                                    "to the preset's wording")
    clock: Optional[str] = Field(None, description="The hour shown beside the picture, e.g. '18:40' (default: the preset's)")
    haze: Optional[float] = Field(None, ge=0, le=1, description="Mist lying in the distance at this time, 0-1; the page "
                                                                "draws it with the depth map and lets it drift "
                                                                "(default: the preset's)")
    lit: Optional[bool] = Field(None, description="Lamps and windows are lit at this time (default: the preset's). The "
                                                  "build finds what turned on or off between neighbouring times")
    seed: Optional[int] = Field(None, description="Seed for this time's relight (default: the scene's); try another when "
                                                  "one drifts or looks wrong")
    strength: Optional[float] = Field(None, ge=0.4, le=1.0, description="This time's own denoise strength (default: the scene's "
                                                                       "`structure.strength`): a time far from the world's light, "
                                                                       "such as night, needs more freedom (0.95) than one near it")
    image: Optional[ImageRef] = Field(None, description="This time's own picture of the same place, instead of relighting "
                                                        "the world (a real photograph, a hand-fixed render). It is aligned "
                                                        "to the world like any relight")

    @model_validator(mode="before")
    @classmethod
    def _bare(cls, v):
        if isinstance(v, str):
            from .light_presets import PRESETS
            key = v.strip().lower().replace(" ", "-").replace("_", "-")
            return {"preset": key} if key in PRESETS else {"prompt": v}
        return v

    @model_validator(mode="after")
    def _known(self):
        from .light_presets import PRESETS
        if self.preset is not None:
            self.preset = self.preset.strip().lower().replace(" ", "-").replace("_", "-")
            if self.preset not in PRESETS:
                raise ValueError(f"unknown time of day '{self.preset}' (known: {', '.join(PRESETS)})")
        if not (self.preset or self.prompt or self.image):
            raise ValueError("a time needs a preset, a prompt or an image")
        return self


class LightLamps(Model):
    """Lights that switch on (or off) between two times: windows, street lamps, a lit cabin. Name them and the build cuts
    them out of the lit picture (Florence-2 + SAM 2.1, `engine/region.py`); the page then turns each one on at its own
    moment as the light changes, with a glow, instead of fading the whole picture."""
    prompt: str = Field(..., description="What turns on, as you would say it to a person: 'the street lamps and the lit "
                                         "windows'. Found on the picture where it is lit")
    color: Optional[str] = Field(None, description="Glow colour, hex (default: measured from the lit pixels)")
    glow: float = Field(1.0, ge=0, le=3, description="Strength of the halo around a light as it comes on")
    grow: int = Field(2, ge=-20, le=60, description="Widen (+) or shrink (-) each cut-out by this many pixels")


class LightSun(Model):
    """A sun (by day) and a moon (by night) that travel over the sky as the scroll goes through the day: a soft glow
    drawn in the browser over the sky only, behind the buildings. The relit pictures are asked for a sky without a
    sun disc so the two never double up."""
    rise: tuple[float, float] = Field((0.1, 0.5), description="Where it comes up, 0-1 across and down the picture")
    noon: tuple[float, float] = Field((0.5, 0.06), description="Where it is highest")
    set: tuple[float, float] = Field((0.92, 0.5), description="Where it goes down")
    size: float = Field(1.0, ge=0.1, le=4, description="Size of the glow")
    strength: float = Field(1.0, ge=0, le=3, description="Brightness of the glow")
    moon: bool = Field(True, description="A cool glow takes its place after dark, crossing the same way")
    sky: Optional[str] = Field(None, description="What the sky is called for the cut-out (default: 'the sky')")


class LightStructure(Model):
    """Geometry lock. The place must not move between times, only the light. Every relight is measured against the world
    (how far the editor displaced structure, and how well edges agree); its global move is undone; a relight that is still
    too far off is redone with another seed, and the best attempt is kept. What drift is left between neighbouring times
    is measured too and the page glides along it (a flow texture) instead of cross-fading doubled edges."""
    align: Literal["affine", "flow", "none"] = Field(
        "affine", description="affine: undo the editor's global move (a few percent of zoom and a few pixels of shift, which "
                              "is most of what it does to the place) and bend nothing; flow: also pull local structure onto "
                              "the world with dense optical flow (edges agree better, lines wobble where the editor redrew "
                              "things; for small drift); none: measure only. What drift remains is glided over in the page")
    max_drift: float = Field(8.0, ge=0, le=40, description="How far the place may still be from the world after the global "
                                                           "move is undone, mean displacement in pixels at 1024 across; above "
                                                           "it the relight is retried with another seed")
    retries: int = Field(1, ge=0, le=8, description="How many more seeds to try when a relight drifts too far")
    strength: float = Field(0.88, ge=0.4, le=1.0, description="How far the editor may depart from the picture it relights (the "
                                                              "denoise strength of the edit): 1 starts from noise and relights "
                                                              "fully but redraws and moves things; lower starts from the picture's own "
                                                              "layout and holds it (0.75 moves things about 1 px, 0.88 a few) while "
                                                              "relighting less. The prompts are written for 0.85-0.9")
    chain: bool = Field(False, description="Relight each time from its neighbour nearer the world's time instead of from the "
                                           "world: smaller steps of light hold the layout and make neighbouring times agree "
                                           "better, at the price of a little sharpness per step")


class LightScene(SceneBase):
    """Light as the scroll: one place, relit from dawn to night as the page scrolls. The world is one picture (a file, a
    generated image, or another scene's still); each time of day is that same picture relit with the geometry locked
    (Qwen-Image-Edit, measured and aligned to the world), cached per time. In the browser the scroll moves continuously
    through the day: a WebGL shader blends neighbouring times with the light itself (a front of new light spreads from
    the sun, shadows sweep, windows and lamps come on one by one with a glow), a slow 2.5D drift lets the place
    breathe, and the section's colours (captions, shade) follow the sky. Steps are the sections of the day: each sits at
    a time (`state: {time: <id>}`, or in order). Reduced motion shows one still per step."""
    type: Literal["light"] = "light"
    layout: Literal["overlay", "split", "cards"] = "overlay"
    length: float = Field(0.0, description="overlay layout: scroll distance in screen heights (0: 2.6 per time of day)")
    world: ImageRef = Field(..., description="The place: a file, a generated image, an edit, or `scene:<id>` for the "
                                             "first frame of another scene (built first). Neutral daylight with the lamps "
                                             "off relights best; everything in it stays where it is")
    world_time: Optional[str] = Field(None, description="The id of the time the world picture already shows (it is used as "
                                                        "it is, not relit): the cleanest anchor, e.g. `noon`")
    times: Union[Literal["day"], list[LightTime]] = Field(
        "day", description="The times of day in order, as presets or free text: [dawn, morning, noon, golden-hour, "
                           "blue-hour, night]. `day` is that list. At least two")
    hold: float = Field(0.3, ge=0, le=0.9, description="Share of each step the light holds still at its time (so a "
                                                        "headline reads in its own light) before the next change begins")
    lamps: list[LightLamps] = Field(default_factory=list, description="Lights that come on and go off (windows, lamps); "
                                                                      "found with Florence-2 + SAM 2.1 and switched one by "
                                                                      "one in the browser. Without it the build finds what "
                                                                      "changed from the pictures themselves")
    sun: Union[bool, LightSun] = Field(False, description="A sun (and moon) glow that travels over the sky, clipped to it; "
                                                           "`true` or a LightSun. Off by default: the relit pictures already paint "
                                                           "a sun or a moon, so use it with prompts that leave the sky bare")
    mist: bool = Field(True, description="Draw the times' `haze` as drifting mist, thicker with distance (needs depth)")
    drift: float = Field(0.5, ge=0, le=2, description="A slow 2.5D camera drift through the depth map so the place "
                                                      "breathes (0 off; reduced motion always off)")
    follow: bool = Field(True, description="The section's colours follow the sky: caption ink, accent and the shade "
                                           "behind the text are measured from each time's picture and blended with the light")
    clock: bool = Field(True, description="Show the time of day (a clock and a sun arc) in a corner")
    focus: tuple[float, float] = Field((0.5, 0.5), description="Where a narrow screen (a phone, in portrait) looks: the point of "
                                                              "the picture, 0-1 across and down, kept in view when it is cropped")
    blend: Literal["light", "fade"] = Field("light", description="light: the light-aware transition; fade: a plain "
                                                                 "crossfade (for comparison, or a quieter page)")
    structure: LightStructure = Field(default_factory=LightStructure, description="Geometry lock: measure each relight against the world, warp small drift away, retry a relight that still drifts")
    depth_model: Literal["small", "base", "large"] = Field("small", description="Depth Anything V2 size for the drift and "
                                                                                 "the mist (small is Apache-2.0)")
    seed: int = Field(7, description="Seed for the relights")
    edit_steps: int = Field(24, ge=4, le=60, description="Qwen-Image-Edit sampling steps per relight")
    width: int = Field(1920, ge=640, le=3840, description="Width of the pictures served to desktop browsers (phones get "
                                                          "two thirds)")

    @model_validator(mode="after")
    def _times(self):
        from .light_presets import SEQUENCES
        if self.times == "day":
            self.times = [LightTime(preset=p) for p in SEQUENCES["day"]]
        used: set[str] = set()
        for i, t in enumerate(self.times):
            if not t.id:
                base = t.preset or "-".join(re.findall(r"[a-z0-9]+", (t.prompt or "").lower())[:3]) or f"t{i}"
                t.id = base
                n = 2
                while t.id in used:
                    t.id, n = f"{base}-{n}", n + 1
            elif t.id in used:
                raise ValueError(f"light '{self.id}': two times are called '{t.id}'")
            used.add(t.id)
        if len(self.times) < 2:
            raise ValueError(f"light '{self.id}': a day needs at least two times")
        if self.world_time is not None and self.world_time not in used:
            raise ValueError(f"light '{self.id}': world_time '{self.world_time}' is not one of the times ({', '.join(sorted(used))})")
        for st in self.steps:
            tid = (st.state or {}).get("time")
            if tid is not None and tid not in used:
                raise ValueError(f"light '{self.id}': step '{st.title}' sits at time '{tid}', which is not one of the times "
                                 f"({', '.join(sorted(used))})")
        return self


# ---------------------------------------------------------------- content blocks

class BlockBase(Model):
    id: Optional[str] = None
    nav_label: Optional[str] = None
    band: bool = Field(False, description="Alternate background band")
    surface: Optional[Literal["light", "dark", "accent"]] = Field(
        None, description="Colour scheme for this section: dark inverts the theme, accent uses its soft accent colour. "
                          "In the stack layout each section is a panel, so this sets the panel's colour.")
    backdrop: Optional[ImageRef] = Field(
        None, description="Full-bleed image behind the whole section: a file, URL, generate: or gradient:. In the stack "
                          "layout it is the panel's own backdrop. Pair with `surface` for legible text.")
    transition: Optional[Transition] = Field(None, description=TRANSITION_DOC)


class IntroBlock(BlockBase):
    type: Literal["intro"] = "intro"
    kicker: Optional[str] = None
    title: str
    body: Optional[str] = None
    button: Optional[Link] = None


class Feature(Model):
    tag: Optional[str] = None
    title: str
    body: Optional[str] = None
    meter: Optional[float] = Field(None, description="0-1 progress bar under the card")


class FeaturesBlock(BlockBase):
    type: Literal["features"] = "features"
    kicker: Optional[str] = None
    title: Optional[str] = None
    items: list[Feature]


class StatData(Model):
    section: str = Field(..., description="id of a chart section on this page")
    series: str
    at: Union[Literal["max", "min", "first", "last"], float] = "last"
    decimals: int = 0
    scale: float = Field(1.0, description="Multiply the value (e.g. 0.001 to show thousands)")


class Stat(Model):
    value: str = Field("", description="Shown as-is; a plain number counts up. Leave empty when `data` fills it")
    unit: Optional[str] = None
    label: str
    data: Optional[StatData] = Field(None, description="Read the value from a chart's data at build time, so headline "
                                                       "numbers can never drift from the source")


class StatsBlock(BlockBase):
    type: Literal["stats"] = "stats"
    items: list[Stat]


class TimelineItem(Model):
    when: str
    title: str
    body: Optional[str] = None


class TimelineBlock(BlockBase):
    type: Literal["timeline"] = "timeline"
    kicker: Optional[str] = None
    title: Optional[str] = None
    items: list[TimelineItem]


class QuoteBlock(BlockBase):
    type: Literal["quote"] = "quote"
    text: str
    who: Optional[str] = None


class CtaBlock(BlockBase):
    type: Literal["cta"] = "cta"
    kicker: Optional[str] = None
    title: str
    button: Optional[Link] = None
    background: Optional[str] = Field(None, description="'scene:<id>' uses that scene's last frame, or an image path")


class GalleryItem(Model):
    title: str
    href: str
    kicker: Optional[str] = None
    body: Optional[str] = None
    image: Optional[ImageRef] = Field(None, description="The tile's picture: a file or URL, or an image input (generate:, "
                                                        "edit:, cinemagraph: ...)")
    video: Optional[str] = None


class GalleryBlock(BlockBase):
    type: Literal["gallery"] = "gallery"
    kicker: Optional[str] = None
    title: Optional[str] = None
    items: list[GalleryItem]


class HeroBlock(BlockBase):
    """A full-screen opening: headline over a photo or looping video, with an optional badge and buttons."""
    type: Literal["hero"] = "hero"
    badge: Optional[str] = Field(None, description="Small pill above the headline (e.g. 'Now open in Lisbon')")
    title: str
    body: Optional[str] = None
    buttons: list[Link] = Field(default_factory=list, description="The first is the primary button")
    image: Optional[ImageRef] = Field(None, description="Background photo (file, URL or generate:)")
    video: Optional[str] = Field(None, description="Background video file (muted, looping); image is its poster")
    align: Literal["center", "left"] = "center"
    device: Optional["Device"] = Field(None, description="A phone rising from the bottom edge under the copy")


class DeviceOption(Model):
    title: str
    body: Optional[str] = None
    selected: bool = Field(False, description="Shown as the chosen option")


class Device(Model):
    """A phone showing a simple app screen, drawn in HTML so the text stays sharp at any size."""
    app: Optional[str] = Field(None, description="App name in the screen's header")
    title: Optional[str] = Field(None, description="Screen title")
    label: Optional[str] = Field(None, description="Small label above the options")
    note: Optional[str] = Field(None, description="Paragraph under the label")
    options: list[DeviceOption] = Field(default_factory=list)
    button: Optional[str] = Field(None, description="Button at the bottom of the screen")
    image: Optional[ImageRef] = Field(None, description="Use a screenshot instead of the drawn screen")
    video: Optional[str] = Field(None, description="Play a screen recording (a project file or URL; muted, looping) "
                                                  "instead of the drawn screen; `image` is then its poster")
    time: str = "9:41"


class ProductBlock(BlockBase):
    """Product or service panel: a large image and/or a phone on one side, copy, tags and buttons on the other."""
    type: Literal["product"] = "product"
    kicker: Optional[str] = None
    title: str
    body: Optional[str] = None
    tags: list[str] = Field(default_factory=list, description="Small pills under the body")
    buttons: list[Link] = Field(default_factory=list, description="The first is the primary button")
    note: Optional[str] = Field(None, description="Small print under the buttons (e.g. a price)")
    image: Optional[ImageRef] = Field(None, description="Product shot. On light surfaces a white background disappears "
                                                        "(multiply blend), so generate it 'on a plain white background'")
    knockout: bool = Field(True, description="Whiten the shot's light studio background (sampled from its edges) so "
                                             "the product floats on the panel instead of sitting in a grey box")
    device: Optional[Device] = None
    side: Literal["left", "right"] = Field("left", description="Which side the image goes on")
    pose: Literal["beside", "rise", "close", "lean", "pair", "turn"] = Field("beside", description=(
        "How the phone sits, so a run of product panels doesn't repeat one composition. beside: next to the copy. "
        "rise: centred under centred copy, cut off by the panel's bottom edge. close: larger, top-aligned beside the "
        "copy and cut off below. lean: tilted out of the lower corner on `side`, running off the edges. "
        "pair: with a second phone (`behind`), the two swapping places on a loop. turn: turned in perspective "
        "towards the copy"))
    behind: Optional[Device] = Field(None, description="pair: the second phone (its own image or video)")
    stats: list[Stat] = Field(default_factory=list, description="Big figures under the body, shown instead of the tags")


class StripItem(Model):
    image: ImageRef
    caption: Optional[str] = None


class StripBlock(BlockBase):
    """A row of photos that slides sideways as you scroll."""
    type: Literal["strip"] = "strip"
    kicker: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    items: list[StripItem]


class OrbitItem(Model):
    label: str
    status: Optional[str] = Field(None, description="e.g. Live, Developing, Roadmap; the first status used is highlighted")


class OrbitBlock(BlockBase):
    """Services arranged around a centre on rings that turn as you scroll, each with a status."""
    type: Literal["orbit"] = "orbit"
    kicker: Optional[str] = None
    title: str
    body: Optional[str] = None
    center: str = Field(..., description="Label in the middle (usually the brand)")
    items: list[OrbitItem]


class FaqItem(Model):
    q: str
    a: str


class FaqBlock(BlockBase):
    """Questions and answers as an accordion (works without JavaScript)."""
    type: Literal["faq"] = "faq"
    kicker: Optional[str] = None
    title: str = "Questions"
    items: list[FaqItem]


# ---- the one-take page (engine/journey.py): kept together so it merges cleanly -----------------------------------

JourneyBlock = Annotated[Union[IntroBlock, FeaturesBlock, StatsBlock, TimelineBlock, QuoteBlock, CtaBlock, GalleryBlock,
                               HeroBlock, ProductBlock, FaqBlock], Field(discriminator="type")]
JourneyBox = tuple[float, float, float, float]


class JourneyPose(Model):
    """Where the camera is and what it looks at, in the blockout's world units (metres, z up, y forward)."""
    at: tuple[float, float, float] = Field(..., description="Camera position")
    look: tuple[float, float, float] = Field(..., description="The point the camera looks at")


class JourneyBlockout(Model):
    """The world as rough shapes, as a take's: Blender renders their depth along the camera path, a still of every stop
    is painted over that depth (Z-Image Turbo + depth ControlNet) and the video model paints the world between the stops
    along the same depth (LTX-2.3). The camera is a real 3D path, so it can go through a door into a room the first
    picture never showed; the price is describing the world's layout once, in shapes."""
    objects: list[WorldObject] = Field(default_factory=list, description="Boxes, cylinders, blobs, planes, scatter: only "
                                       "layout, scale and depth matter, the models paint the detail. Leave a gap in a wall "
                                       "for a doorway (two boxes and a lintel)")
    ground: Optional[WorldObject] = Field(None, description="A plane under everything (default: 400 x 400 at z = 0)")
    sky: str = Field("#b9cde0", description="Colour of the sky in the blockout")
    light: tuple[float, float, float] = Field((0.0, -0.4, 0.9), description="Light direction of the blockout preview")
    lens: float = Field(28.0, description="Focal length in mm")
    depth_far: float = Field(400.0, description="Depth guide far plane")
    control_strength: float = Field(0.75, ge=0, le=1, description="How tightly each stop's picture follows the blockout's "
                                    "depth (Z-Image depth ControlNet)")
    keyframe_res: tuple[int, int] = Field((1536, 864), description="Size of each stop's picture")
    ltx_res: tuple[int, int] = Field((1024, 576), description="Size the video model runs at (multiples of 64); the "
                                     "film is scaled to the page. 1024x576 is the size it holds its look at")
    guide_strength: float = Field(1.0, ge=0, le=2, description="How strongly the depth guide steers the video model")
    guide_blur: float = Field(1.5, ge=0, le=12, description="Blur of the depth guide in pixels: keeps the camera and the "
                              "big shapes, drops the blockout's hard edges so a box does not stay a box")
    segment: float = Field(8.0, ge=3, le=10, description="Longest stretch the video model paints in one go, in seconds. "
                           "The film is cut into stretches at the middle of each hold (the camera is at rest there, so "
                           "the seam cannot show) and a longer one is split evenly")
    keyframe_strength: float = Field(0.6, ge=0, le=1, description="How firmly each stop's picture is pinned in the film. Too firm (0.9 was measured) and the model, holding the picture before and the picture after, dissolves between them instead of travelling; about 0.5-0.6 lets the depth guide move the camera and still lands on the picture")
    negative: Optional[str] = Field(None, description="What the video model must avoid (default: cuts, flicker, warped "
                                                      "shapes, text, watermark, blur)")


class JourneyMove(Model):
    """How the camera gets from the stop before to this one: a keyed camera move on a moving shot (`camera:` of a beat),
    flown through the picture the last stop left and painted by the video model, so the place it arrives at is the one
    this stop's `place` describes, found inside the last picture and not cut to."""
    into: Optional[JourneyBox] = Field(None, description="Chain (no `blockout`): the part of the previous stop's picture the camera travels "
                                       "into: [x0, y0, x1, y1] in 0-1 of that picture, the doorway, the window, the "
                                       "table. The camera arrives with this box filling the frame. Default: the middle "
                                       "third")
    via: list[JourneyBox] = Field(default_factory=list, description="Chain: boxes the camera passes on the way (a bend in the "
                                  "path: past the fire and on to the stairs), evenly spaced in time")
    path: list[JourneyPose] = Field(default_factory=list, description="With a `blockout`: poses the camera passes on the "
                                    "way (evenly spaced in time), a bend in its path: round the table, through the arch")
    seconds: float = Field(4.0, ge=1, le=20, description="Length of the move in the film (a chain: at most 10)")
    scroll: Optional[float] = Field(None, ge=0.3, le=12, description="Scroll distance of the move, in screen heights "
                                    "(default: half the seconds of film). The page lands on the stop at the end of it")
    motion: Optional[str] = Field(None, description="What the move looks like, in words, for the video model: 'the "
                                  "camera glides through the open door into the hall, firelight ahead'")
    ease: FreezeEase = Field("inOutSine", description="How the camera travels (as `freeze.ease`); the default starts and "
                             "ends at rest, so the page lands softly at the stop")
    parallax: float = Field(0.5, ge=0, le=2, description="Depth effect of the guide (as `camera.parallax`)")
    anchor: float = Field(0.6, ge=0, le=1, description="How firmly the pure-camera render of the picture is pinned along "
                          "the way (as `camera.anchor`): more keeps the world the picture shows, less lets the model "
                          "paint more of the place it arrives at")
    guide_strength: float = Field(1.0, ge=0, le=2, description="How strongly the depth guide steers the model")
    res: Optional[tuple[int, int]] = Field(None, description="Size the video model runs at (as `camera.res`)")
    seed: Optional[int] = Field(None, description="Seed of the move (default: the stop's). With a `blockout` it re-rolls the "
                                "stretch of the take that ends at this stop (and so the stretches after it, which continue from it)")


class JourneyStop(Model):
    """One place on the journey. The camera arrives (`move`), rests while the page holds (`hold`), shows its `blocks`
    laid out to sit with the picture, and moves on."""
    id: str = Field(..., description="Short name; the beats are called <id>-travel and <id>-hold")
    label: Optional[str] = Field(None, description="Name of the place in the page's places rail (default: the id)")
    world: Optional[str] = Field(None, description="Replaces `journey.world` in this stop's prompts: for a place the shared "
                                 "world would mislead, such as the view out of a window in a journey described from inside")
    place: str = Field(..., description="The place as a photograph: what the camera sees at rest here, in the world "
                                        "described once at `journey.world`. The first stop's picture is made from it; "
                                        "later stops arrive at it through `move` (it steers the video model toward the "
                                        "place) and it names the picture for the reduced-motion page")
    still: Optional[ImageRef] = Field(None, description="Use this picture for the stop instead (a file, or an image "
                                      "input: generate:, edit:, beat_frame ...). For the first stop it replaces the "
                                      "picture made from `place`; for a later one the hold freezes it instead of the "
                                      "frame the camera arrived at")
    edit: Optional[str] = Field(None, description="Make the stop's picture by editing the frame the camera arrived at "
                                "(Qwen-Image-Edit): 'a wooden crate of jars stands on the table'. With `region` the "
                                "rest of the frame is that frame, pixel for pixel, so the join stays invisible")
    region: Optional[EditRegion] = Field(None, description="`edit`: where it may change the picture")
    pose: Optional[JourneyPose] = Field(None, description="With a `blockout`: where the camera rests at this stop")
    move: JourneyMove = Field(default_factory=JourneyMove, description="How the camera gets here (not used by the first stop)")
    frame: Optional[JourneyBox] = Field(None, description="The framing the hold settles on, a box in 0-1 of the stop's "
                                        "picture (default: a slow push-in of `breathe`). The hold starts and ends on the "
                                        "whole picture, so it joins the moves before and after exactly")
    breathe: float = Field(0.05, ge=0, le=0.3, description="How far the camera pushes in during the hold when `frame` is "
                           "not set, as a share of the picture. The frozen moment keeps its parallax, so it lives")
    seconds: float = Field(3.0, ge=1, le=20, description="Length of the hold in the film (chain: a frozen moment, no model, "
                                                          "rendered offline in seconds; blockout: the camera at rest)")
    hold: float = Field(1.4, ge=0.3, le=12, description="Scroll distance of the hold, in screen heights: how long the "
                        "page stays at this place while its blocks are read")
    parallax: float = Field(0.6, ge=0, le=2, description="Depth effect of the hold (as `freeze.parallax`)")
    focus: Optional[tuple[float, float]] = Field(None, description="The point of the picture (0-1 across, 0-1 down) a "
                                                  "portrait phone keeps in view when it crops the wide picture "
                                                  "(default: the middle)")
    blocks: list[JourneyBlock] = Field(default_factory=list, description="Content shown at this stop (hero, intro, "
                                       "features, stats, quote, faq, product, cta ...): the same blocks as a section, "
                                       "set as part of the place instead of over it")
    side: Literal["auto", "left", "right", "center", "top", "bottom"] = Field(
        "auto", description="Where the blocks sit on the picture. auto: the calmest part of the picture, found from "
                            "the picture itself (least detail, so nothing important is covered), alternating sides")
    form: Literal["auto", "type", "rail", "cards", "plaque"] = Field(
        "auto", description="How the blocks are set. type: bare lettering with a soft scrim, as if written in the scene. "
                            "rail: items in a column divided by hairlines, like a plan beside the place. cards: panels "
                            "of glass. plaque: one framed plate with a rule inside, like an engraved sign. auto: each "
                            "block type picks the one that suits it")
    surface: Literal["auto", "light", "dark"] = Field(
        "auto", description="light/dark: the picture under the blocks is light (dark lettering) or dark (light "
                            "lettering). auto: measured from the picture where the blocks sit")
    seed: Optional[int] = Field(None, description="Seed of this stop's picture and move (default: the journey's, plus the "
                                                  "stop's position)")

    @model_validator(mode="after")
    def _edit_needs_source(self):
        if self.region is not None and not self.edit:
            raise ValueError(f"stop '{self.id}': `region` limits an `edit`; give the edit too")
        if self.edit and self.still is not None:
            raise ValueError(f"stop '{self.id}': `edit` and `still` both make the picture; use one")
        return self


class Journey(Model):
    """The whole page as one camera journey through one generated world: each stop is a place in it, the camera
    travels between them in one unbroken move and the page's content arrives at its stop.

    The engine builds it from what it already does best: the first picture is generated from the world and the first
    place; every later place is arrived at by a keyed camera move on a moving shot (flown through the picture before,
    painted by the video model), then frozen as a moment with a slow parallax while the page holds. Every join is on
    the same frame, so there is no cut, and every picture comes out of the one before, so there is no change of style.
    The runtime maps scroll to the film: a move plays as you scroll through it, a stop holds while its blocks are read,
    and the camera is at rest whenever the page is. On a phone the wide picture is cropped around `focus`; with reduced
    motion (or no JavaScript) the page is the stops as stills with their blocks, in order."""
    world: str = Field(..., description="The world, described once: the place, its materials, the light and the hour "
                                        "('a stone farmhouse on a northern moor at dawn, blue mist, oak and slate, "
                                        "firelight inside'). Added to the prompt of every picture and move, so the stops "
                                        "are one place. Say nothing about people")
    stops: list[JourneyStop] = Field(..., min_length=2, description="The places, in order")
    pace: float = Field(1.0, gt=0.2, le=4, description="Scales every scroll distance (holds and moves): 0.8 is brisker")
    rail: bool = Field(True, description="A rail of the places down the right edge: a mark per stop, the current one "
                                         "named, each a link that scrolls to it")
    seed: int = Field(11, description="Seed of the pictures and moves (each stop adds its position)")
    fade: float = Field(0.25, ge=0, le=1, description="Seconds of cross-dissolve between the move and the hold on the "
                        "same frame (invisible; it only hides the one-frame seam of two encodes)")
    grain: float = Field(0.012, ge=0, le=0.2, description="Chain: film grain laid over the frozen holds so they match the "
                         "generated moves on either side (as `freeze.grain`)")
    blockout: Optional[JourneyBlockout] = Field(None, description="The generation approach. Unset: a chain of camera moves "
                                                "between stop pictures (the camera flies through the picture the last stop "
                                                "left, so every stop must be visible in the one before: a facade, a street, "
                                                "a landscape). Set: one continuous take through a blockout of the world "
                                                "(real 3D, so doors and rooms work); every stop then needs a `pose`")
    restore: Optional[int] = Field(None, ge=360, le=2160, description="Run SeedVR2 over the finished film at this height "
                                   "(e.g. 1080) to clean the video model's softness and redraw fine detail; slow")

    @model_validator(mode="after")
    def _unique_stops(self):
        ids = [s.id for s in self.stops]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"journey stop ids must be unique: {', '.join(dup)}")
        for i, st in enumerate(self.stops):
            if self.blockout is not None and st.pose is None:
                raise ValueError(f"stop '{st.id}': with a `blockout` every stop needs a `pose` (where the camera rests)")
            if self.blockout is None and (st.pose is not None or st.move.path):
                raise ValueError(f"stop '{st.id}': `pose` and `move.path` place the camera in a `blockout`; without one the "
                                 "camera flies through the pictures (`move.into`, `move.via`)")
            if self.blockout is not None and i and (st.move.into or st.move.via):
                raise ValueError(f"stop '{st.id}': `move.into` and `move.via` fly through a picture; with a `blockout` use `move.path`")
            if self.blockout is None and i and st.move.seconds > 10:
                raise ValueError(f"stop '{st.id}': a move in a chain is at most 10 seconds (one generated shot)")
        return self


FilmScene.model_rebuild()
InsideScene.model_rebuild()


Section = Annotated[Union[
    FilmScene, ArtworkScene, Scene3DScene, SequenceScene, ParallaxScene, TypeScene, VectorScene, ChartScene, MapScene,
    SplatScene, CodeScene, ShowroomScene, DioramaScene, InsideScene, LightScene,
    IntroBlock, FeaturesBlock, StatsBlock, TimelineBlock, QuoteBlock, CtaBlock, GalleryBlock,
    HeroBlock, ProductBlock, StripBlock, OrbitBlock, FaqBlock,
], Field(discriminator="type")]

SCENE_TYPES = ("film", "artwork", "scene3d", "sequence", "parallax", "type", "vector", "chart", "map", "splat", "code",
               "showroom", "diorama", "inside", "light")


# ---------------------------------------------------------------- site

class Art(Model):
    """Artwork a style renders in its own medium: ascii-art prints it in characters, particles fills the screen with
    it in points. Generated locally from a prompt (or taken from a file), optionally animated into a short loop."""
    prompt: Optional[str] = Field(None, description="Generate the image locally (Z-Image), e.g. 'a basketball player "
                                                    "dribbling, black background'. Plain backgrounds and strong "
                                                    "silhouettes read best in characters and points")
    file: Optional[str] = Field(None, description="Use this image (project file or URL) instead of a prompt")
    motion: Optional[str] = Field(None, description="Animate it with the video model (needs ComfyUI), e.g. 'dribbles the "
                                                    "ball between his legs'. Omit for a still")
    seconds: float = Field(3.0, ge=1, le=8, description="Length of the animated loop")
    size: tuple[int, int] = Field((1024, 768), description="Generated image size (the loop keeps its aspect)")
    seed: int = 7
    frames: int = Field(36, ge=1, le=96, description="Frames shipped to the page (sampled evenly from the loop)")
    width: int = Field(220, ge=40, le=480, description="Sampling width in pixels of the shipped frames: characters "
                                                       "and points are drawn from these")
    label: Optional[str] = Field(None, description="Short name shown with the art (defaults to the prompt)")
    video_model: Optional[VideoModel] = Field(None, description=VIDEO_MODEL_DOC)


def _css_values(model: BaseModel) -> BaseModel:
    """Theme token values end up inside the page's <style> block, so a string may only be a plain CSS value."""
    for k, v in model:
        if isinstance(v, str) and not css_value_ok(v):
            raise ValueError(f"{k}: {v[:40]!r} is not a plain CSS value (a length such as 24px, or clamp(...), min(...))")
    return model


class SpaceTokens(Model):
    """Page spacing. Each value defaults to what the stylesheet has always used."""
    gutter: Optional[str] = Field(None, description="Margin at the page's sides (default clamp(20px, 4vw, 64px))")
    max: Optional[str] = Field(None, description="Widest the content runs (default 1600px)")
    caption: Optional[str] = Field(None, description="Width of the captions over a scene (default min(680px, 82vw))")

    _plain = model_validator(mode="after")(_css_values)


class TypeTokens(Model):
    """Type sizes. Each value defaults to what the stylesheet has always used."""
    scale: Optional[float] = Field(None, gt=0, le=4, description="Multiplies every headline size, on phones too "
                                                                 "(default 1: 1.15 is a seventh larger)")
    body: Optional[str] = Field(None, description="Size of running text (default 17px)")

    _plain = model_validator(mode="after")(_css_values)


class ShadeTokens(Model):
    """The shade laid over a scene's picture so its captions stay readable."""
    strength: Optional[float] = Field(None, ge=0, le=1, description="How strongly the shade fades the picture toward "
                                                                    "the background: 1 as designed (the default), 0 none")


class MotionTokens(Model):
    """How the page moves. Each value defaults to what the runtime has always used; `scroll.speed` still paces it."""
    ease: Optional[str] = Field(None, description="Easing of transitions (default cubic-bezier(.22, .8, .2, 1))")
    enter: Optional[float] = Field(None, gt=0, le=1, description="Share of the screen height a block scrolls through "
                                                                 "while it arrives (default 0.2)")
    follow: Optional[float] = Field(None, gt=0, le=0.5, description="How quickly smooth scrolling catches up with the "
                                                                    "wheel (default 0.1; 0.5 is nearly immediate)")

    _plain = model_validator(mode="after")(_css_values)


FONT_FILE_TYPES = (".woff2", ".woff", ".ttf", ".otf")


class FontFile(Model):
    """A font file of the project's own (a brand face that is not on Google Fonts), served from the site itself."""
    file: str = Field(..., description="The font file inside the project folder: .woff2 (best), .woff, .ttf or .otf")
    family: Optional[str] = Field(None, description="The family name it is set in (default: from the file name, "
                                                    "fonts/Brand-Sans.woff2 is 'Brand Sans')")
    weight: Optional[str] = Field(None, description="The weight the file holds, e.g. 400 or 700, or a range such as "
                                                    "'100 900' for a variable font (default: every weight)")
    style: Literal["normal", "italic"] = Field("normal", description="normal, or italic for an italic file")

    @field_validator("file")
    @classmethod
    def _a_font_file(cls, v: str) -> str:
        if not v.lower().endswith(FONT_FILE_TYPES):
            raise ValueError(f"file {v[:40]!r} is not a font file ({', '.join(FONT_FILE_TYPES)})")
        return v

    @field_validator("family")
    @classmethod
    def _a_family_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not FONT_NAME.fullmatch(v):
            raise ValueError(f"family {v[:40]!r} is not a font family name (letters, digits, spaces and . + & ' -)")
        return v

    @field_validator("weight", mode="before")
    @classmethod
    def _a_weight(cls, v: Any) -> Optional[str]:      # `weight: 700` in YAML is a number
        if v is not None and not re.fullmatch(r"[1-9]00( [1-9]00)?", str(v).strip()):
            raise ValueError(f"weight {v[:20]!r} is a weight such as 400, or a range such as '100 900'")
        return v if v is None else str(v).strip()


def _fonts_schema(schema: dict) -> None:
    """A role is a family name or a FontFile. `type` stays in the schema beside the union, widened rather than
    dropped, so whatever read `type: string` here before still finds it."""
    schema["additionalProperties"]["type"] = ["string", "object"]


class Theme(Model):
    preset: str = Field("night", description="night, brass, paper, lab, cosmos, studio, dusk, ink, blueprint, clinic (see engine/themes.yaml)")
    style: Optional[str] = Field(
        None, description="An experience in one word: its own scroll mechanic, layout, transitions and look. particles, "
                          "liquid-morph, holographic, neon-glow, wireframe-3d, glassmorphism, kinetic-type, isometric, clay-3d, "
                          "ascii-art, gradient-mesh, comic-book, split-flap, retro-vhs, halftone, bauhaus, pixel-art, blueprint, "
                          "art-deco, neo-brutalism, anime-intro, flipbook, pop-up-book, pinscreen, sand, zoetrope, stop-motion, paper-cut-out, scratch-film, smears, paint-on-glass, multiplane (see engine/styles/). Colours/fonts set here still win")
    mode: Optional[Literal["light", "dark"]] = Field(None, description="Override the preset's light/dark mode (set it when colors flip it)")
    colors: dict[str, str] = Field(default_factory=dict, description="Override tokens: bg, bg2, ink, accent, accent2")
    fonts: dict[str, Union[str, FontFile]] = Field(
        default_factory=dict, json_schema_extra=_fonts_schema,
        description="Fonts by role (display, body, mono): a Google Fonts family, or a file of the project's own "
                    "({file: fonts/Brand.woff2}), served from the site either way")
    display_weight: Optional[int] = None
    display_italic_em: Optional[bool] = Field(None, description="Render <em> accent words in italic")
    display_em: Optional[Literal["accent", "bold", "heavy"]] = Field(
        None, description="How <em> words are set: accent (the accent colour, italic when display_italic_em), "
                          "bold (bold italics in the text's own colour, so a headline reads as one face) or heavy "
                          "(upright, the text's own colour, at the face's heaviest weight: pair with a light "
                          "display_weight so emphasis is a change of weight)")
    labels: Optional[Literal["caps", "plain"]] = Field(
        None, description="Small labels (kickers, tags, timeline dates): caps (spaced capitals in the mono face, the "
                          "default) or plain (sentence case in the body face, for brands that never set all-caps)")
    display_optical_size: Optional[int] = Field(
        None, description="Pin the display face's optical size (variable fonts such as Fraunces or Newsreader grow "
                          "more expressive at large sizes; 36-48 keeps headlines calm)")
    radius: Optional[str] = None
    art: Optional[Art] = Field(None, description="Artwork the style renders in its own medium (ascii-art: characters, "
                                                  "particles: points). A prompt or a file, optionally animated")
    space: Optional[SpaceTokens] = Field(None, description="Page spacing: gutter, max width, caption width")
    type: Optional[TypeTokens] = Field(None, description="Type sizes: headline scale and running-text size")
    shade: Optional[ShadeTokens] = Field(None, description="Strength of the shade over scene pictures")
    motion: Optional[MotionTokens] = Field(None, description="Easing, how blocks arrive and how smooth scrolling follows")
    grain: Optional[float] = Field(None, ge=0, le=1, description="Film grain over the whole page: 0 none (the default) "
                                                                  "to 1; 0.15-0.3 reads as print or film")
    phone: Optional[int] = Field(None, ge=320, le=1600, description="Width in px below which the page takes its phone "
                                                                     "layout, for the stylesheet and the runtime alike. "
                                                                     "Unset keeps the built-in widths (900 for the "
                                                                     "layout, 760 for scenes, 700 for one-take pages)")

    @field_validator("colors")
    @classmethod
    def _colors_are_colors(cls, v: dict[str, str]) -> dict[str, str]:
        for k, c in v.items():
            if not CSS_NAME.fullmatch(k.replace("_", "-")) or not css_value_ok(c):
                raise ValueError(f"colors.{k}: {c[:40]!r} is not a plain CSS colour (use #hex, rgb(...) or a colour name)")
        return v

    @field_validator("fonts")
    @classmethod
    def _fonts_are_families(cls, v: dict[str, Union[str, FontFile]]) -> dict[str, Union[str, FontFile]]:
        for k, f in v.items():
            if not CSS_NAME.fullmatch(k) or not (isinstance(f, FontFile) or FONT_NAME.fullmatch(f)):
                raise ValueError(f"fonts.{k}: {f[:40]!r} is not a Google Fonts family name (letters, digits, spaces and . + & ' -)")
        return v

    @field_validator("radius")
    @classmethod
    def _radius_is_a_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not css_value_ok(v):
            raise ValueError(f"radius {v[:40]!r} is not a CSS length such as 4px or 0.5rem")
        return v


class Nav(Model):
    logo: Optional[str] = Field(None, description="Inline SVG path data (24x24) or an image file")
    links: list[Link] = Field(default_factory=list, description="Empty = generated from sections with nav_label")
    cta: Optional[Link] = None


class Loader(Model):
    """Loading screen: scrolling stays locked until every scene's media has loaded (videos fully downloaded,
    frames decoded, map tiles drawn), with a progress bar."""
    enabled: bool = True
    label: Optional[str] = Field(None, description="Text under the bar (defaults to the site name)")
    max_wait: float = Field(45.0, description="Seconds after which the site opens anyway")
    min_time: float = Field(0.6, description="Minimum seconds on screen, so it never flashes")


class Footer(Model):
    left: Optional[str] = None
    right: Optional[str] = None
    links: list[Link] = Field(default_factory=list, description="Links shown before `right`, e.g. a privacy policy "
                                                                 "or terms hosted elsewhere (`pages:` adds its own)")


class Scroll(Model):
    speed: float = Field(1.0, description="Pace of the smooth scroll, anchor scrolls and scroll-driven reveals: "
                                          "1.2 is a fifth faster, 0.8 a fifth slower")


class Page(Model):
    """A plain page beside the site (privacy policy, support, press): Markdown set in the site's theme, served
    at /<slug>/ and linked from the footer."""
    slug: str = Field(..., description="URL path: 'privacy' is served at /privacy/")
    title: str
    source: str = Field(..., description="Markdown file relative to the project folder (pages/privacy.md)")
    summary: Optional[str] = Field(None, description="Meta description for the page")
    nav: bool = Field(False, description="Also link it from the nav, after the section links")

    @field_validator("slug")
    @classmethod
    def _slug_is_a_url_path(cls, v: str) -> str:
        parts = v.strip("/").split("/")
        if not all(SAFE_ID.fullmatch(p) and not p.startswith(".") for p in parts):
            raise ValueError(f"slug {v[:40]!r} is not allowed: use letters, digits, '-' and '_', with '/' between folders "
                             "(no '..', no spaces)")
        return "/".join(parts)


# ---------------------------------------------------------------- launch trailer (`studio trailer`, engine/trailer/)

class TrailerShot(Model):
    """One shot of the launch trailer, cut from something the site already rendered. Give one source: `section`
    (with `step` or `range`), `beat`, `product` or `card`."""
    section: Optional[str] = Field(None, description="id of a section. A film plays its own footage (take, beats or "
                                                      "video); any other section is recorded scrolling through the "
                                                      "built site (at phone size for 9:16)")
    step: Optional[int] = Field(None, description="film: the footage under this step (its index in the section's "
                                                  "steps), captioned with its headline")
    beat: Optional[str] = Field(None, description="id of a beat of a beats film (the section is found for you)")
    range: Optional[tuple[float, float]] = Field(None, description="Part of the source: seconds of a film, or 0-1 "
                                                                   "scroll progress of a recorded section")
    product: Optional[str] = Field(None, description="A still of `site.product` from this view (front, three-quarter, "
                                                     "side, top, back, hero-low, exploded) with a slow push-in. Needs "
                                                     "the product feature; skipped with a note when it is missing")
    card: Optional[str] = Field(None, description="A type card on the theme background with this headline "
                                                  "(<em>…</em> marks accent words)")
    caption: Optional[str] = Field(None, description="Headline over the shot (<em>…</em> marks accent words). "
                                                     "Default: the matching step or section headline; '' for none")
    kicker: Optional[str] = Field(None, description="Small label above the caption")
    callouts: list[str] = Field(default_factory=list, description="Short feature lines ('24 h cold') set big, one "
                                                                  "after another on the beat, over this shot")
    beats: Optional[int] = Field(None, ge=1, le=64, description="Length on the trailer's beat grid (default: long "
                                                                "enough to read the caption, at least a bar)")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Playback speed of the footage")
    hold: bool = Field(False, description="Freeze the first frame of `range` instead of playing it")
    zoom: Optional[tuple[float, float]] = Field(None, description="Push-in: scale at the start and the end of the "
                                                                  "shot (1 = the whole frame). Default: a slow push on "
                                                                  "the product reveal and on stills")
    focus: Optional[tuple[float, float]] = Field(None, description="Point (0-1 x, y of the source) that the 9:16 crop "
                                                                   "and the push-in keep in frame. Default: the "
                                                                   "product in a take, else the most salient area")


class Trailer(Model):
    """A launch film cut by the engine from the site's own renders (`studio trailer`): dist/trailer/trailer-16x9.mp4,
    trailer-9x16.mp4 (reframed, never letterboxed) and their posters. Cuts land on a beat grid; captions and the end
    card are set in the theme's fonts and colours. `trailer: {}` derives the cut: a hook shot, the middle of the
    story, the product reveal, 2-4 feature callouts and an end card."""
    shots: list[TrailerShot] = Field(default_factory=list, description="The cut, in order. Empty: derived from the site")
    formats: list[Literal["16x9", "9x16"]] = Field(default_factory=lambda: ["16x9", "9x16"],
                                                   description="16x9: 1920x1080; 9x16: 1080x1920 for TikTok/Reels/Shorts")
    seconds: float = Field(24.0, ge=8, le=90, description="Target length of a derived cut (15-30 s suits social)")
    bpm: float = Field(100.0, ge=40, le=220, description="Tempo of the beat grid the cuts land on")
    music: Optional[str] = Field(None, description="A local audio file (project path); none is generated. Without "
                                                   "it the trailer is silent and the captions carry it")
    music_start: float = Field(0.0, ge=0, description="Seconds into the music where the first cut lands (a downbeat)")
    loudness: float = Field(-14.0, ge=-30, le=-8, description="Music loudness target, integrated LUFS")
    fps: Literal[24, 30] = 24
    captions: bool = Field(True, description="Set captions over the shots")
    title: Optional[str] = Field(None, description="End card name (default: the site name)")
    tagline: Optional[str] = Field(None, description="End card line (default: the site description)")
    cta: Optional[str] = Field(None, description="End card call to action (default: the nav button's label)")
    url: Optional[str] = Field(None, description="End card address, e.g. stillwater.example (default: the nav "
                                                 "button's link when it is a full URL)")
    disclaimer: Optional[str] = Field(None, description="Small print on the end card (default: the product's concept "
                                                        "line, 'Concept page. Not affiliated with <maker>.')")
    end_beats: int = Field(8, ge=2, le=32, description="Length of the end card on the beat grid")
    end_background: Literal["blur", "theme"] = Field("blur", description="blur: the last shot, blurred under the "
                                                                         "theme colour; theme: the plain background")
    embed: bool = Field(False, description="Add a 'Watch the launch film' button to the first section that opens the "
                                           "trailer in a modal (built by `studio trailer`, picked up by the next build)")
    embed_label: str = Field("Watch the launch film", description="Label of the embed button")


# ---------------------------------------------------------------- imagery + directions (engine/imagery.py, engine/directions/)

class Imagery(Model):
    """How every image and film this site generates is phrased, so the whole page looks like one shoot. Each part is
    added to every prompt the engine sends to the image and video models (a `generate:` image, a beat's frame and clip,
    a take's keyframes and segments); the prompt itself stays about the subject. Unset, nothing is added. A direction
    from `studio directions` writes this block when you pick it."""
    medium: str = Field(..., description="What the picture is made of, said first: '35mm film photograph, Kodak Portra "
                                         "400, fine grain', 'gouache illustration on textured paper, flat shapes'")
    light: Optional[str] = Field(None, description="The light: 'low golden-hour sun, long soft shadows', 'single window "
                                                   "light from the left, Vermeer'")
    lens: Optional[str] = Field(None, description="Lens and framing: '35mm, eye level, shallow depth of field'")
    mood: Optional[str] = Field(None, description="The feeling in a few words: 'unhurried, sun-warmed, quiet'")
    palette: Optional[str] = Field(None, description="Colour in words: 'muted terracotta, bone and sage'")
    restyle: bool = Field(True, description="Drop the medium, lens and light phrases already in a prompt ('photorealistic', "
                                            "'shot on 35mm', 'golden hour') for the parts set here, so the prompt does not "
                                            "contradict the shoot. Off: the parts are only added")


class Pool(Model):
    """What a direction may draw on: only these (empty: everything), never these."""
    only: list[str] = Field(default_factory=list, description="Consider only these (empty: all)")
    avoid: list[str] = Field(default_factory=list, description="Never use these")


class PalettePool(Pool):
    """only/avoid take palette names (`studio directions --list palettes`) or colour words (avoid: [red, green])."""
    brand: list[str] = Field(default_factory=list, description="Hex colours every direction must carry as its accent: "
                                                               "the palettes keep their grounds and take these")


class Directions(Model):
    """Art directions for this site (`studio directions <project>`): the studio's pitch. One brief in, several complete
    directions out (concept, palette, type, style, imagery, motion), each a board of storyboard stills side by side; pick
    one and it is written into this file. The writer is deterministic (curated design vocabularies combined by seed), so
    the same brief and seed give the same boards. Copy is never changed."""
    brief: Optional[str] = Field(None, description="What to pitch, in your words: 'calmer, more editorial; for people who "
                                                   "travel slowly'. Mood words in it steer the directions")
    count: int = Field(6, ge=2, le=12, description="How many directions")
    seed: int = Field(1, description="Another seed, another set of directions")
    moods: list[str] = Field(default_factory=list, description="Mood words to lean toward (calm, warm, bold, playful, "
                                                               "technical, raw, nostalgic, futuristic, handmade, luxurious...)")
    keep: list[Literal["style", "colors", "fonts", "imagery"]] = Field(
        default_factory=list, description="Parts of the site's current look every direction must keep, varying the rest. "
                                          "The name and copy are always kept")
    styles: Pool = Field(default_factory=Pool, description="Which styles (engine/styles/) to consider or avoid; "
                                                             "'none' is the default editorial layout")
    fonts: Pool = Field(default_factory=Pool, description="Google Fonts families to consider or avoid")
    palettes: PalettePool = Field(default_factory=PalettePool, description="Palettes to consider or avoid, and brand "
                                                                           "colours to carry")
    stills: int = Field(4, ge=1, le=6, description="Storyboard stills per board: the hero, then key sections")


class Site(Model):
    name: str
    description: str = ""
    lang: str = "en"
    theme: Theme = Field(default_factory=Theme)
    layout: Literal["flow", "stack"] = Field(
        "flow", description="flow: sections follow one another. stack: every section is a full-screen panel with "
                            "rounded top corners that slides up over the one before it.")
    nav: Nav = Field(default_factory=Nav)
    loader: Loader = Field(default_factory=Loader)
    scroll: Scroll = Field(default_factory=Scroll)
    sections: list[Section]
    footer: Footer = Field(default_factory=Footer)
    pages: list[Page] = Field(default_factory=list, description="Plain Markdown pages beside the site (privacy, support)")
    product: Optional[Product] = Field(None, description="The product the site is about, declared once: takes, sequences, "
                                                         "showroom scenes and `image: {product: <view>}` stills use it")
    # launch trailer
    trailer: Optional[Trailer] = Field(None, description="A launch film built from the site's renders by "
                                                         "`studio trailer` (16:9 and 9:16); `{}` derives the cut")
    video_model: Optional[VideoModel] = Field(None, description="Default video model for film beats, takes and "
                                              "theme.art: ltx (LTX-2.3) or wan (Wan 2.2). Unset = studio.toml's, then ltx")
    wan: Wan = Field(default_factory=Wan, description="Wan 2.2 settings used wherever video_model is wan")
    imagery: Optional[Imagery] = Field(None, description="How every generated image and film is phrased (medium, light, "
                                                         "lens, mood, palette), so the page looks like one shoot; "
                                                         "written by picking a direction (`studio directions`)")
    directions: Optional[Directions] = Field(None, description="Brief and constraints for `studio directions`: several "
                                                               "complete art directions as side-by-side boards")


def is_scene(section) -> bool:
    return getattr(section, "type", None) in SCENE_TYPES
