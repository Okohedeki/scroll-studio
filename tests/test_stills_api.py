"""The Studio server's stills API (engine/stills/api.py, issue #177): state with file URLs, files kept inside stills/,
pick at once and the rest as jobs. Laptop path: no network, no GPU."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from engine.router import core
from test_stills import project


@pytest.fixture
def client(tmp_path, monkeypatch):
    from engine.server import app as server
    monkeypatch.setattr(core, "backends", lambda: [])
    project(tmp_path)
    monkeypatch.setattr(server, "PROJECTS", tmp_path)
    return TestClient(server.app, base_url="http://127.0.0.1:8970")


def wait(c, job):
    for _ in range(200):
        j = c.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_state_files_and_actions(client):
    s = client.get("/api/projects/shop/stills").json()
    assert s["enabled"] and s["candidates"] == [] and s["shots"] == ["packshot", "lifestyle", "detail"]
    j = wait(client, client.post("/api/projects/shop/stills", json={}).json())
    assert j["status"] == "done"
    s = client.get("/api/projects/shop/stills").json()
    c = s["candidates"][0]
    assert c["url"].startswith("/api/projects/shop/stills/files/candidates/")
    r = client.get(c["url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    r = client.post("/api/projects/shop/stills", json={"pick": c["id"]}).json()
    assert r["state"]["picked"][c["shot"]] == c["id"]
    j = wait(client, client.post("/api/projects/shop/stills", json={"more": c["id"]}).json())
    assert j["status"] == "done" and len(client.get("/api/projects/shop/stills").json()["candidates"]) == 7


def test_files_stay_inside_stills(client):
    assert client.get("/api/projects/shop/stills/files/../project.yaml").status_code == 404
    assert client.get("/api/projects/shop/stills/files/nothing.png").status_code == 404


def test_a_bad_pick_and_a_project_without_stills(client, tmp_path):
    assert client.post("/api/projects/shop/stills", json={"pick": "nope"}).status_code == 400
    (tmp_path / "plain").mkdir()
    (tmp_path / "plain" / "site.yaml").write_text("name: T\nsections: []\n", encoding="utf-8")
    s = client.get("/api/projects/plain/stills").json()
    assert not s["enabled"] and "studio migrate" in s["why"]
    assert client.post("/api/projects/plain/stills", json={}).status_code == 400
