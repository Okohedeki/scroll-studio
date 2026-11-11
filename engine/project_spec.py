"""The project root: `project.yaml` holds the brief, brand, product and imagery once, and every output under `outputs:`.

A site is one output (`outputs.site`). The engine still builds from a `Site`, so a project file is folded into one on
load, and a site written back is split again. A folder with only `site.yaml` keeps working: it is read as a project
whose single output is that site (docs/design/generation-engine.md, issue #172).

    project.yaml              site the engine builds
    ------------              ----------------------
    name, description         name, description
    brand                     theme
    product, imagery, models  product, imagery, models
    outputs.site.*            everything else
"""
from __future__ import annotations

import copy
from typing import Any, Literal, Optional

from pydantic import Field, field_validator

from .spec import Imagery, Model, Models, Product, Site, Theme

PROJECT_FILE = "project.yaml"
SITE_FILE = "site.yaml"

# site key -> project key, for the fields that belong to the whole project rather than to one output
HOISTED = {"name": "name", "description": "description", "theme": "brand", "product": "product", "imagery": "imagery",
           "models": "models"}


class SiteOutput(Site):
    """A site output: today's site spec. Its name, theme, product and imagery default to the project's."""
    name: str = ""


StillShot = Literal["packshot", "lifestyle", "detail"]


class Stills(Model):
    """Product stills from one photo (engine/stills, `studio stills`): several art directions, candidates across seeds
    and backends, critics, and a varied shortlist per shot. The product's pixels come from the photo, never redrawn."""
    photo: str = Field(..., description="The product photo, inside the project (e.g. inputs/product.png): a cut-out "
                                        "PNG, or a photo on a plain background (cut out automatically)")
    describe: str = Field("", description="What the product is, for the prompts: 'a matte glazed planter'")
    shots: list[StillShot] = Field(default_factory=lambda: ["packshot", "lifestyle", "detail"],
                                   description="packshot: on a clean backdrop. lifestyle: in a scene. detail: close "
                                               "and cropped")
    directions: int = Field(4, ge=1, le=12, description="How many art directions to explore")
    candidates: int = Field(2, ge=1, le=8, description="Seeds per direction and shot")
    keep: int = Field(3, ge=1, le=12, description="Shortlist size per shot")
    size: tuple[int, int] = Field((1600, 1600), description="Width and height of every still, pixels")
    seed: int = Field(1, description="The seed the directions and candidates start from")
    harmonise: bool = Field(True, description="Blend the light with an edit job where one can run; skipped, and the "
                                              "composite kept, when it changes the product too much")
    fidelity: float = Field(0.06, gt=0, le=1, description="Most the product may change when blended (mean change "
                                                          "inside its mask, 0-1)")

    @field_validator("size")
    @classmethod
    def _size(cls, v):
        if not all(256 <= x <= 4096 for x in v):
            raise ValueError("size must be between 256 and 4096 pixels each way")
        return v


AdSize = Literal["1x1", "4x5", "9x16", "16x9", "1.91x1"]


AdResolution = Literal["1k", "2k", "4k"]
RESOLUTION_WIDTH = {"1k": 1080, "2k": 2048, "4k": 4096}


class Ads(Model):
    """Placement-sized ads from the picked product stills (engine/ads.py, `studio ads`). With outputs.concepts, one
    variation per concept and language: each concept's headline and call to action on every size."""
    sizes: list[AdSize] = Field(default_factory=lambda: ["1x1", "4x5", "9x16"], description="Aspect ratios to make")
    headline: str = Field("", description="The line set on each ad; empty: none")
    cta: str = Field("", description="The call to action set under it, e.g. 'Shop the range'")
    shots: list[StillShot] = Field(default_factory=lambda: ["lifestyle", "packshot"],
                                   description="Which shots' stills to use (each shot's pick, else its best)")
    width: int = Field(1080, ge=320, le=4096, description="Width of every ad, pixels; the height follows the ratio")
    resolution: Optional[AdResolution] = Field(None, description="1k (1080 px wide), 2k (2048) or 4k (4096): sets "
                                                                 "the width; a still smaller than that is upscaled, "
                                                                 "and ads.json says so")
    concepts: bool = Field(True, description="With outputs.concepts: one variation per concept (its headline and "
                                             "call to action); headline and cta here are then the fallback")


class Listing(Model):
    """Store listing copy for the product (engine/listing.py, `studio listing`)."""
    bullets: int = Field(5, ge=0, le=10, description="How many bullet points")
    tone: str = Field("warm, plain", description="How it reads, in a few words")
    max_title: int = Field(80, ge=20, le=200, description="Longest title, characters")


class Video(Model):
    """A short product video from the picked stills (engine/video.py, `studio video`): a slow push-in on each, cross
    dissolves, an end card with the ads' headline and call to action, and a voiceover where a speech backend can run."""
    seconds: float = Field(15, ge=4, le=60, description="Length of the video")
    aspect: AdSize = Field("9x16", description="Aspect ratio")
    width: int = Field(1080, ge=320, le=2160, description="Width in pixels; the height follows the ratio")
    shots: list[StillShot] = Field(default_factory=lambda: ["lifestyle", "detail", "packshot"],
                                   description="Which shots' stills to show, in order (each shot's pick and shortlist)")
    per_shot: int = Field(2, ge=1, le=6, description="Most stills taken from each shot")
    voiceover: str = Field("", description="What the voice says. 'listing': the listing's description. Empty: no voice")
    voice: str = Field("", description="The speech backend's voice id; empty: its default")
    music: Optional[str] = Field(None, description="A music file inside the project, laid under the voice "
                                                   "(you need the right to use it)")


ConceptAngle = Literal["problem", "benefit", "proof", "comparison", "routine", "gift", "unboxing", "story", "offer",
                       "objection"]


class Concepts(Model):
    """Ad concepts (engine/concepts.py, `studio concepts`): angles on the product, each with a hook, a headline, a
    call to action, on-screen lines and a short spoken script, written from the product profile in every language
    the project sells in. Ads and video ads make one variation per concept."""
    count: int = Field(6, ge=1, le=30, description="How many concepts to write")
    angles: list[ConceptAngle] = Field(default_factory=list, description="Angles to use, in order; empty: the "
                                                                         "engine picks the ones the product supports")
    seconds: float = Field(20, ge=6, le=60, description="Length of each spoken script, for video ads")
    tone: str = Field("warm, plain, direct", description="How the copy reads, in a few words")
    claims: Literal["page", "profile"] = Field("profile", description="What a claim may rest on: the product page's "
                                                                      "own words only, or the profile drawn from it")


class Ugc(Model):
    """Vertical creator-style video ads (engine/ugc.py, `studio ugc`): for each concept and language, a synthetic
    presenter with the product, product shots, the concept's script as a voiceover and its lines as captions. The
    presenter is generated, never a real person's likeness; lip sync is not attempted (the voice is a voiceover)."""
    concepts: int = Field(3, ge=1, le=30, description="How many concepts get a video ad (the first ones)")
    presenter: str = Field("a friendly person in their thirties, casual clothes, at home", description="Who presents "
                           "the product, described (a generated person; never name or describe a real one)")
    aspect: Literal["9x16", "4x5", "1x1"] = Field("9x16", description="Aspect ratio")
    width: int = Field(1080, ge=240, le=2160, description="Width in pixels; the height follows the ratio")
    captions: bool = Field(True, description="Burn the script in as captions, a few words at a time")
    voice: str = Field("", description="The speech backend's voice id; empty: its default")
    music: Optional[str] = Field(None, description="A music file inside the project, laid under the voice "
                                                   "(you need the right to use it)")
    presenter_seconds: float = Field(4, ge=2, le=10, description="Length of each presenter clip")


class Layouts(Model):
    """Generated page layouts (engine/layouts.py, `studio layouts`): several pages written from the brief, the stills
    and the listing, each a different arrangement; picking one writes its sections into outputs.site."""
    count: int = Field(3, ge=1, le=8, description="How many layouts to write")
    seed: int = Field(1, description="Which arrangements the local composer starts from")


class Outputs(Model):
    site: Optional[SiteOutput] = Field(None, description="A scroll-driven site, written as a site.yaml would be "
                                                         "(without the fields the project sets once)")
    stills: Optional[Stills] = Field(None, description="Product stills from one photo: pack shots, lifestyle scenes "
                                                       "and details, shortlisted (`studio stills`)")
    ads: Optional[Ads] = Field(None, description="Placement-sized ads made from the picked stills (`studio ads`)")
    listing: Optional[Listing] = Field(None, description="Store listing copy: title, bullets, description "
                                                         "(`studio listing`)")
    video: Optional[Video] = Field(None, description="A short product video from the picked stills, with a voiceover "
                                                     "where a speech backend can run (`studio video`)")
    layouts: Optional[Layouts] = Field(None, description="Generated page layouts to pick from; the pick becomes "
                                                         "outputs.site (`studio layouts`)")
    concepts: Optional[Concepts] = Field(None, description="Ad concepts: angles, hooks, headlines, scripts, in every "
                                                           "language (`studio concepts`)")
    ugc: Optional[Ugc] = Field(None, description="Vertical creator-style video ads, one per concept and language "
                                                 "(`studio ugc`)")


class ProjectSpec(Model):
    name: str
    description: str = ""
    brief: str = Field("", description="What the project is for, in a sentence or two; generation steps read it")
    source: Optional[str] = Field(None, description="The product page this project was imported from (`studio "
                                                    "import`); its profile is in profile/profile.json")
    languages: list[str] = Field(default_factory=lambda: ["en"], description="The languages the copy, captions and "
                                 "voice are written in, as codes (en, es, de, pt-BR, ja...): each is written for its "
                                 "market, not translated word for word")
    brand: Optional[Theme] = Field(None, description="Colours, fonts and brand source, shared by every output "
                                                     "(a site's `theme`)")
    product: Optional[Product] = Field(None, description="The product every output shows, declared once")
    imagery: Optional[Imagery] = Field(None, description="How every generated image and film is phrased")
    models: Optional[Models] = Field(None, description="Which backend does each job, for every output")
    outputs: Outputs = Field(default_factory=Outputs)

    @field_validator("languages")
    @classmethod
    def _languages(cls, v):
        import re
        bad = [x for x in v if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})?", x)]
        if bad or not v:
            raise ValueError(f"languages are codes such as en, es, pt-BR (got {bad or 'none'})")
        return list(dict.fromkeys(v))


class ProjectFileError(ValueError):
    pass


def is_site_shaped(data: Any) -> bool:
    """A site.yaml document (top-level `sections`), not a project file."""
    return isinstance(data, dict) and "sections" in data and "outputs" not in data


def site_dict(data: dict) -> dict:
    """The site a project file describes, as a site.yaml document: the project's shared fields folded into
    `outputs.site`. The same field set in both places with different values is refused."""
    site = (data.get("outputs") or {}).get("site")
    if not isinstance(site, dict):
        raise ProjectFileError(f"{PROJECT_FILE} has no outputs.site: a site is the only output that builds so far")
    site = copy.deepcopy(site)
    out: dict = {}
    for site_key, key in HOISTED.items():
        if key in data:
            if site_key in site and site[site_key] != data[key]:
                raise ProjectFileError(f"{key} is set on the project and as outputs.site.{site_key}, with different "
                                       f"values: keep one")
            out[site_key] = copy.deepcopy(data[key])
        elif site_key in site:
            out[site_key] = site.pop(site_key)
        site.pop(site_key, None)
    out.update(site)
    return out


def project_dict(site: dict, keep: Optional[dict] = None) -> dict:
    """A site.yaml document as a project file. `keep` is the project file being rewritten: what only a project has
    (its brief, other outputs) is carried over."""
    keep = keep or {}
    out: dict = {}
    for site_key, key in HOISTED.items():
        if site_key in site:
            out[key] = copy.deepcopy(site[site_key])
        if key == "description" and "brief" in keep:
            out["brief"] = keep["brief"]
    for key, value in keep.items():
        if key not in out and key not in HOISTED.values() and key != "outputs":
            out[key] = copy.deepcopy(value)
    outputs = {k: copy.deepcopy(v) for k, v in (keep.get("outputs") or {}).items() if k != "site"}
    outputs["site"] = {k: copy.deepcopy(v) for k, v in site.items() if k not in HOISTED}
    out["outputs"] = outputs
    return out


def validate(data: Any) -> ProjectSpec:
    """A project file or a site.yaml document, validated as a project."""
    if is_site_shaped(data):
        data = project_dict(data)
    spec = ProjectSpec.model_validate(data)
    if spec.outputs.site is not None:
        Site.model_validate(site_dict(data))       # the folded site, with the project's fields, must be valid too
    return spec
