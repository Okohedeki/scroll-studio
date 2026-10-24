"""The MCP tools take names and file paths from an AI client: names stay single folder names, and only files a site
can use are read (the client may be steered by text it read elsewhere)."""
from __future__ import annotations

from pathlib import Path

import pytest

from engine import mcp_server


@pytest.fixture
def projects(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    (root / "demo" / "inputs").mkdir(parents=True)
    (root / "demo" / "site.yaml").write_text("name: Demo\nsections: []\n", encoding="utf-8")
    monkeypatch.setattr(mcp_server, "PROJECTS", root)
    return root


@pytest.mark.parametrize("name", ["../demo", "..", ".hidden", "a/b", "a\\b", ""])
def test_project_names_are_one_plain_folder(projects, name):
    with pytest.raises(ValueError):
        mcp_server._find(name)


def test_a_project_is_found_by_name(projects):
    assert mcp_server._find("demo").root == (projects / "demo").resolve()


@pytest.mark.parametrize("name", ["../escape", ".hidden", "a/b"])
def test_create_project_refuses_names_that_leave_the_folder(projects, name):
    with pytest.raises(ValueError):
        mcp_server.create_project(name)
    assert not (projects.parent / "escape").exists()


def test_create_project_refuses_an_unknown_example(projects):
    with pytest.raises(ValueError, match="no example"):
        mcp_server.create_project("fresh", example="no-such-example")


def test_add_input_copies_media(projects, tmp_path):
    src = tmp_path / "photo.jpg"
    src.write_bytes(b"\xff\xd8\xff")
    mcp_server.add_input("demo", str(src))
    assert (projects / "demo" / "inputs" / "photo.jpg").read_bytes() == b"\xff\xd8\xff"


@pytest.mark.parametrize("filename", ["id_rsa", "secrets.env", "key.pem", "credentials"])
def test_add_input_refuses_files_a_site_does_not_use(projects, tmp_path, filename):
    src = tmp_path / filename
    src.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError):
        mcp_server.add_input("demo", str(src))
    assert not (projects / "demo" / "inputs" / filename).exists()


def test_add_input_refuses_files_in_hidden_folders_under_home(projects, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".aws").mkdir(parents=True)
    src = home / ".aws" / "notes.txt"
    src.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    with pytest.raises(ValueError, match="hidden"):
        mcp_server.add_input("demo", str(src))


def test_add_input_refuses_a_missing_file(projects, tmp_path):
    with pytest.raises(ValueError, match="not a file"):
        mcp_server.add_input("demo", str(tmp_path / "nothing.jpg"))
