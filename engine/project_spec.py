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
from typing import Any, Optional

from pydantic import Field

from .spec import Imagery, Model, Models, Product, Site, Theme

PROJECT_FILE = "project.yaml"
SITE_FILE = "site.yaml"

# site key -> project key, for the fields that belong to the whole project rather than to one output
HOISTED = {"name": "name", "description": "description", "theme": "brand", "product": "product", "imagery": "imagery",
           "models": "models"}


class SiteOutput(Site):
    """A site output: today's site spec. Its name, theme, product and imagery default to the project's."""
    name: str = ""


class Outputs(Model):
    site: Optional[SiteOutput] = Field(None, description="A scroll-driven site, written as a site.yaml would be "
                                                         "(without the fields the project sets once)")


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
