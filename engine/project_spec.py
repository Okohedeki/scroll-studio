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


class Ads(Model):
    """Placement-sized ads from the picked product stills (engine/ads.py, `studio ads`)."""
    sizes: list[AdSize] = Field(default_factory=lambda: ["1x1", "4x5", "9x16"], description="Aspect ratios to make")
    headline: str = Field("", description="The line set on each ad; empty: none")
    cta: str = Field("", description="The call to action set under it, e.g. 'Shop the range'")
    shots: list[StillShot] = Field(default_factory=lambda: ["lifestyle", "packshot"],
                                   description="Which shots' stills to use (each shot's pick, else its best)")
    width: int = Field(1080, ge=320, le=4096, description="Width of every ad, pixels; the height follows the ratio")


class Listing(Model):
    """Store listing copy for the product (engine/listing.py, `studio listing`)."""
    bullets: int = Field(5, ge=0, le=10, description="How many bullet points")
    tone: str = Field("warm, plain", description="How it reads, in a few words")
    max_title: int = Field(80, ge=20, le=200, description="Longest title, characters")


class Outputs(Model):
    site: Optional[SiteOutput] = Field(None, description="A scroll-driven site, written as a site.yaml would be "
                                                         "(without the fields the project sets once)")
    stills: Optional[Stills] = Field(None, description="Product stills from one photo: pack shots, lifestyle scenes "
                                                       "and details, shortlisted (`studio stills`)")
    ads: Optional[Ads] = Field(None, description="Placement-sized ads made from the picked stills (`studio ads`)")
    listing: Optional[Listing] = Field(None, description="Store listing copy: title, bullets, description "
                                                         "(`studio listing`)")


class ProjectSpec(Model):
    name: str
    description: str = ""
    brief: str = Field("", description="What the project is for, in a sentence or two; generation steps read it")
    brand: Optional[Theme] = Field(None, description="Colours, fonts and brand source, shared by every output "
                                                     "(a site's `theme`)")
    product: Optional[Product] = Field(None, description="The product every output shows, declared once")
    imagery: Optional[Imagery] = Field(None, description="How every generated image and film is phrased")
    models: Optional[Models] = Field(None, description="Which backend does each job, for every output")
    outputs: Outputs = Field(default_factory=Outputs)


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
