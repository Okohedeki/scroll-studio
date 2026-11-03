"""The project root (engine/project_spec.py, issue #172): project.yaml folds into the same site a site.yaml describes,
site.yaml folders keep working, and `studio migrate` changes the file, never the site."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from engine.migrate import migrate, project_text
from engine.project import BuildError, Project, has_spec
from engine.project_spec import ProjectFileError, ProjectSpec, is_site_shaped, project_dict, site_dict, validate
from engine.spec import Site

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted(p.parent for p in (ROOT / "examples").glob("*/site.yaml"))

SITE = {
    "name": "Example Shop",
    "description": "A small shop.",
    "theme": {"preset": "paper"},
    "imagery": {"medium": "photo"},
    "sections": [{"type": "intro", "title": "Hello"}],
}


def write_project(folder: Path, data: dict, file: str = "project.yaml") -> Project:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / file).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return Project(folder)


# ---------------------------------------------------------------- every example, both ways

@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_every_example_is_the_same_site_as_a_project(example):
    site = yaml.safe_load((example / "site.yaml").read_text(encoding="utf-8"))
    as_project = yaml.safe_load(project_text(site))
    assert not is_site_shaped(as_project)
    assert Site.model_validate(site_dict(as_project)) == Site.model_validate(site)
    validate(as_project)


def test_examples_are_found():
    assert len(EXAMPLES) > 10


# ---------------------------------------------------------------- folding

def test_shared_fields_move_up_and_fold_back():
    data = project_dict(SITE)
    assert data["brand"] == {"preset": "paper"} and data["imagery"] == {"medium": "photo"}
    assert "theme" not in data["outputs"]["site"] and "name" not in data["outputs"]["site"]
    assert site_dict(data) == SITE


def test_a_field_left_inside_the_site_still_counts():
    data = {"name": "Example Shop", "outputs": {"site": {"theme": {"preset": "night"}, "sections": SITE["sections"]}}}
    assert site_dict(data)["theme"] == {"preset": "night"}


def test_the_same_field_set_twice_differently_is_refused():
    data = {"name": "A", "brand": {"preset": "paper"},
            "outputs": {"site": {"theme": {"preset": "night"}, "sections": SITE["sections"]}}}
    with pytest.raises(ProjectFileError, match="brand"):
        site_dict(data)


def test_a_project_without_a_site_output_does_not_build():
    with pytest.raises(ProjectFileError, match="outputs.site"):
        site_dict({"name": "A", "outputs": {}})
    assert validate({"name": "A"}).outputs.site is None


def test_project_only_fields_are_kept_when_the_site_is_rewritten():
    keep = {"name": "A", "brief": "Launch set", "outputs": {"site": {"sections": []}}}
    out = project_dict({**SITE, "name": "B"}, keep=keep)
    assert out["brief"] == "Launch set" and out["name"] == "B"


def test_unknown_project_fields_are_refused():
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate({"name": "A", "colour": "red"})


# ---------------------------------------------------------------- the Project folder

def test_a_project_folder_loads_the_folded_site(tmp_path):
    p = write_project(tmp_path / "shop", {**project_dict(SITE), "brief": "Autumn range"})
    assert p.is_project_file and has_spec(p.root)
    assert p.load().theme.preset == "paper"
    assert p.load_project().brief == "Autumn range"
    assert p.raw() == SITE


def test_project_yaml_wins_over_site_yaml(tmp_path):
    write_project(tmp_path / "shop", {**SITE, "name": "Old"}, file="site.yaml")
    p = write_project(tmp_path / "shop", project_dict(SITE))
    assert p.load().name == "Example Shop"


def test_a_site_yaml_folder_reads_as_a_project(tmp_path):
    p = write_project(tmp_path / "shop", SITE, file="site.yaml")
    assert not p.is_project_file
    assert p.load_project().brand.preset == "paper"


def test_a_bad_project_file_is_a_build_error(tmp_path):
    p = write_project(tmp_path / "shop", {"name": "A", "outputs": {}})
    with pytest.raises(BuildError, match="outputs.site"):
        p.load()


def test_site_text_round_trips_through_a_project_file(tmp_path):
    p = write_project(tmp_path / "shop", {**project_dict(SITE), "brief": "Autumn range"})
    text = p.site_text()
    assert yaml.safe_load(text) == SITE
    p.write_site_text(text.replace("Hello", "Welcome"))
    data = yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))
    assert data["brief"] == "Autumn range"
    assert data["outputs"]["site"]["sections"][0]["title"] == "Welcome"


def test_save_writes_the_project_file(tmp_path):
    p = write_project(tmp_path / "shop", project_dict(SITE))
    p.save({**SITE, "description": "Changed"})
    assert yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))["description"] == "Changed"
    assert not (tmp_path / "shop" / "site.yaml").exists()


def test_put_text_takes_either_shape(tmp_path):
    p = write_project(tmp_path / "shop", SITE, file="site.yaml")
    p.put_text(yaml.safe_dump({**SITE, "description": "Edited"}))
    assert not p.is_project_file and p.load().description == "Edited"
    p.put_text(project_text(SITE))
    assert p.is_project_file and (tmp_path / "shop" / "site.yaml.bak").exists()
    p.put_text(yaml.safe_dump({**SITE, "description": "Again"}))
    assert p.is_project_file and p.load().description == "Again"


def test_put_text_refuses_an_invalid_project(tmp_path):
    p = write_project(tmp_path / "shop", SITE, file="site.yaml")
    with pytest.raises(BuildError):
        p.put_text(yaml.safe_dump({"name": "A", "outputs": {}}))
    with pytest.raises(ValidationError):
        p.put_text(yaml.safe_dump({"name": "A", "outputs": {"site": {"sections": [{"type": "nope"}]}}}))
    assert not p.is_project_file


# ---------------------------------------------------------------- migrate

def test_migrate_shows_then_writes(tmp_path):
    p = write_project(tmp_path / "shop", SITE, file="site.yaml")
    r = migrate(p)
    assert "+++ project.yaml" in r["diff"] and not p.is_project_file
    migrate(p, write=True)
    assert p.is_project_file and (tmp_path / "shop" / "site.yaml.bak").exists()
    assert p.raw() == SITE
    with pytest.raises(BuildError, match="already"):
        migrate(p)


def test_migrate_needs_a_site_yaml(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(BuildError, match="no site.yaml"):
        migrate(Project(tmp_path / "empty"))


def test_storyboard_edits_reach_a_project_file(tmp_path):
    from engine.storyboard.edit import specdoc
    p = write_project(tmp_path / "shop", {**project_dict(SITE), "brief": "Autumn range"})
    text = specdoc.read_text(p)
    specdoc._write(p, text.replace("Hello", "Welcome"))
    data = yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))
    assert data["brief"] == "Autumn range" and data["outputs"]["site"]["sections"][0]["title"] == "Welcome"


def test_the_studio_server_edits_a_project_file_as_a_site(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from engine.server import app as server
    write_project(tmp_path / "demo", {**project_dict(SITE), "brief": "Autumn range"})
    monkeypatch.setattr(server, "PROJECTS", tmp_path)
    c = TestClient(server.app, base_url="http://127.0.0.1:8970")
    r = c.get("/api/projects/demo/spec").json()
    assert r["file"] == "project.yaml" and r["data"] == SITE and "outputs:" in r["yaml"]
    r = c.put("/api/projects/demo/spec", json={"data": {**SITE, "description": "From the form"}})
    assert r.status_code == 200
    data = yaml.safe_load((tmp_path / "demo" / "project.yaml").read_text(encoding="utf-8"))
    assert data["description"] == "From the form" and data["brief"] == "Autumn range"
