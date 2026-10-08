"""The site spec: one YAML file describes a whole site. The UI, Claude and the CLI all edit this.

A site is a nav, a list of sections and a footer. A section is either a *scene* (a scroll-driven visual
built by a scene module: film, artwork, scene3d, sequence, parallax, type) or a *block* (static content:
intro, features, stats, timeline, quote, cta, gallery).

`Site.model_json_schema()` is the contract for the UI forms and the MCP tools.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- shared pieces

class Link(Model):
    label: str
    href: str = "#"


class ImageInput(Model):
    """An image the engine uses as input: a file in the project's inputs/, or one generated locally."""
    file: Optional[str] = Field(None, description="Path relative to the project folder (inputs/photo.jpg) or an https URL")
    generate: Optional[str] = Field(None, description="Prompt for a local text-to-image model (Z-Image Turbo)")
    size: tuple[int, int] = Field((1920, 1088), description="Generated size (multiples of 16)")
    seed: int = 7
    crop: Optional[tuple[float, float, float, float]] = Field(None, description="Crop [x0, y0, x1, y1] in 0-1 image coordinates")
    credit: Optional[str] = Field(None, description="Attribution shown in the footer")


ImageRef = Union[str, ImageInput]   # a bare string is a file path


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


# ---------------------------------------------------------------- scene types

class FilmScene(SceneBase):
    """AI film scrubbed by scroll. Blender blockout -> Z-Image keyframes -> LTX-2.3 -> encode."""
    type: Literal["film"] = "film"
    video: Optional[str] = Field(None, description="Use an existing film instead of generating one")
    shot: dict[str, Any] = Field(default_factory=dict,
        description="Generation settings: fps, duration, preview_res, blockout {preset|file}, keyframes, ltx, upscale")
    gop: int = 6


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
    model: str = Field(..., description="glTF/GLB, OBJ, FBX or STL: a project file or an https URL (downloaded once)")
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
    kind: Literal["line", "area"] = "line"
    y_scale: Literal["linear", "log"] = "linear"
    y_label: Optional[str] = None
    unit: str = Field("", description="Unit after values, e.g. ' GW'")
    source: Optional[str] = Field(None, description="Data credit shown under the chart and in the footer")
    colors: list[str] = Field(default_factory=list, description="Series colours in `include` order (defaults to the theme)")


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


class TypeScene(SceneBase):
    """Kinetic typography driven by scroll."""
    type: Literal["type"] = "type"
    mode: Literal["reveal", "stack", "swap", "scale"] = "reveal"
    text: str = Field("", description="reveal/scale: the passage; swap: the fixed part")
    words: list[str] = Field(default_factory=list, description="swap: the words that cycle")
    length: float = 3.0


# ---------------------------------------------------------------- content blocks

class BlockBase(Model):
    id: Optional[str] = None
    nav_label: Optional[str] = None
    band: bool = Field(False, description="Alternate background band")
    surface: Optional[Literal["light", "dark", "accent"]] = Field(
        None, description="Colour scheme for this section: dark inverts the theme, accent uses its soft accent colour. "
                          "In the stack layout each section is a panel, so this sets the panel's colour.")


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


class Stat(Model):
    value: str = Field(..., description="Shown as-is; a plain number counts up")
    unit: Optional[str] = None
    label: str


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
    image: Optional[str] = None
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


Section = Annotated[Union[
    FilmScene, ArtworkScene, Scene3DScene, SequenceScene, ParallaxScene, TypeScene, VectorScene, ChartScene, MapScene,
    IntroBlock, FeaturesBlock, StatsBlock, TimelineBlock, QuoteBlock, CtaBlock, GalleryBlock,
    HeroBlock, ProductBlock, StripBlock, OrbitBlock, FaqBlock,
], Field(discriminator="type")]

SCENE_TYPES = ("film", "artwork", "scene3d", "sequence", "parallax", "type", "vector", "chart", "map")


# ---------------------------------------------------------------- site

class Theme(Model):
    preset: str = Field("night", description="night, brass, paper, lab, cosmos, studio, dusk, ink, blueprint, clinic (see engine/themes.yaml)")
    colors: dict[str, str] = Field(default_factory=dict, description="Override tokens: bg, bg2, ink, accent, accent2")
    fonts: dict[str, str] = Field(default_factory=dict, description="Google Fonts families: display, body, mono")
    display_weight: Optional[int] = None
    display_italic_em: Optional[bool] = Field(None, description="Render <em> accent words in italic")
    radius: Optional[str] = None


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


class Page(Model):
    """A plain page beside the site (privacy policy, support, press): Markdown set in the site's theme, served
    at /<slug>/ and linked from the footer."""
    slug: str = Field(..., description="URL path: 'privacy' is served at /privacy/")
    title: str
    source: str = Field(..., description="Markdown file relative to the project folder (pages/privacy.md)")
    summary: Optional[str] = Field(None, description="Meta description for the page")
    nav: bool = Field(False, description="Also link it from the nav, after the section links")


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
    sections: list[Section]
    footer: Footer = Field(default_factory=Footer)
    pages: list[Page] = Field(default_factory=list, description="Plain Markdown pages beside the site (privacy, support)")


def is_scene(section) -> bool:
    return getattr(section, "type", None) in SCENE_TYPES
