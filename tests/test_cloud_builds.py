"""`studio build --cloud`: the upload leaves build output at home, the log streams, dist/ comes back, and names that
would leave the project are refused. The service is a stub; nothing goes over the network."""
from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from engine import cloud


def _dist_tar(files: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class Resp:
    def __init__(self, status=200, body=None, content=None):
        self.status_code, self._body = status, body
        self.content = content if content is not None else json.dumps(body or {}).encode()
        self.text = self.content.decode(errors="replace")

    def json(self):
        return self._body


class Service:
    """Accepts one build, reports it running with two log lines, then done, then serves dist/."""
    def __init__(self, dist: bytes, final="done"):
        self.dist, self.final, self.polls, self.upload, self.form = dist, final, 0, None, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, path, data=None, files=None, timeout=None, json=None):
        if path == "/v1/builds":
            self.form = data
            self.upload = files["bundle"][1].read()
            return Resp(202, {"id": "b1", "hold": 60, "rate": 6, "max_minutes": 10, "gpu": "L40S", "balance": 940})
        return Resp(200, {})

    def get(self, path, params=None, timeout=None):
        if path == "/v1/builds/b1":
            self.polls += 1
            if self.polls == 1:
                return Resp(200, {"status": "running", "lines": ["  render: running", "  render: done"], "next": 2})
            return Resp(200, {"status": self.final, "lines": [], "next": 2, "charged": 12, "minutes": 1.5,
                              "balance": 988, "error": "the build stopped with exit code 1"})
        if path == "/v1/builds/b1/output":
            return Resp(200, content=self.dist)
        return Resp(404, {"detail": "no"})


def _project(tmp_path: Path) -> Path:
    p = tmp_path / "shop"
    (p / "inputs").mkdir(parents=True)
    (p / "site.yaml").write_text("title: Shop\n", encoding="utf-8")
    (p / "inputs" / "photo.jpg").write_bytes(b"jpg")
    (p / ".build").mkdir()
    (p / ".build" / "cache.bin").write_bytes(b"x" * 100)
    (p / "dist").mkdir()
    (p / "dist" / "old.html").write_text("old", encoding="utf-8")
    return p


def test_a_hosted_build_uploads_the_project_and_brings_dist_back(tmp_path, monkeypatch):
    p = _project(tmp_path)
    svc = Service(_dist_tar({"index.html": b"<h1>new</h1>", "media/a.mp4": b"v"}))
    monkeypatch.setattr(cloud, "_client", lambda *a, **k: svc)
    seen = []
    st = cloud.build(p, {"draft": True}, 10, log=seen.append, poll=0)
    with tarfile.open(fileobj=io.BytesIO(svc.upload), mode="r:gz") as tar:
        names = set(tar.getnames())
    assert names == {"site.yaml", "inputs/photo.jpg"}              # .build and dist stay home
    assert json.loads(svc.form["options"]) == {"draft": True} and svc.form["max_minutes"] == "10"
    assert "  render: done" in seen and any("12 credits" in s for s in seen)
    assert (p / "dist" / "index.html").read_bytes() == b"<h1>new</h1>" and not (p / "dist" / "old.html").exists()
    assert st["charged"] == 12


def test_a_failed_hosted_build_says_why_and_keeps_the_old_dist(tmp_path, monkeypatch):
    p = _project(tmp_path)
    svc = Service(b"", final="failed")
    monkeypatch.setattr(cloud, "_client", lambda *a, **k: svc)
    with pytest.raises(cloud.CloudError, match="exit code 1"):
        cloud.build(p, {}, None, log=lambda m: None, poll=0)
    assert (p / "dist" / "old.html").exists()


def test_dist_from_the_service_cannot_write_outside_the_project(tmp_path):
    with pytest.raises(cloud.CloudError):
        cloud.unpack_dist(_dist_tar({"../escape.html": b"x"}), tmp_path / "dist")
    assert not (tmp_path / "escape.html").exists()


def test_the_build_machine_turns_the_account_off(monkeypatch):
    monkeypatch.setenv("STUDIO_CLOUD_TOKEN", "t")
    monkeypatch.setenv("STUDIO_CLOUD_URL", "http://service.test")
    assert cloud.CloudBackend().available()[0]
    monkeypatch.setenv("STUDIO_CLOUD_DISABLED", "1")
    assert not cloud.CloudBackend().available()[0]


def test_max_minutes_needs_cloud(tmp_path):
    from typer.testing import CliRunner

    from engine.cli import app
    p = _project(tmp_path)
    r = CliRunner().invoke(app, ["build", str(p), "--max-minutes", "5"])
    assert r.exit_code != 0 and "--cloud" in r.output
