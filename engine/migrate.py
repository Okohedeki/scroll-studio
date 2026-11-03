"""`studio migrate`: a site.yaml rewritten as a project.yaml (engine/project_spec.py). The site it builds is the same,
which is checked before anything is written."""
from __future__ import annotations

import difflib
import os

import yaml

from .project import BuildError, Project
from .project_spec import PROJECT_FILE, SITE_FILE, project_dict, site_dict
from .spec import Site


def project_text(site: dict) -> str:
    return yaml.safe_dump(project_dict(site), sort_keys=False, allow_unicode=True, width=110)


def migrate(project: Project, write: bool = False) -> dict:
    """{diff, path, backup}: the project.yaml for `project`'s site.yaml, written only with write=True."""
    if project.is_project_file:
        raise BuildError(f"{project.name} already has a {PROJECT_FILE}")
    if not project.exists():
        raise BuildError(f"{project.name} has no {SITE_FILE}")
    old = project.spec_path.read_text(encoding="utf-8")
    site = yaml.safe_load(old) or {}
    new = project_text(site)
    if Site.model_validate(site_dict(yaml.safe_load(new))) != Site.model_validate(site):
        raise BuildError("the project file would not describe the same site; nothing written")
    diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), SITE_FILE, PROJECT_FILE))
    path, backup = project.root / PROJECT_FILE, project.root / (SITE_FILE + ".bak")
    if write:
        path.write_text(new, encoding="utf-8")
        os.replace(project.root / SITE_FILE, backup)
    return {"diff": diff, "path": str(path), "backup": str(backup)}
