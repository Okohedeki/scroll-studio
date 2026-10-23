"""The local servers answer only the machine they run on: Host must be 127.0.0.1, localhost or [::1] with the server's own
port (400), and a request that changes something must not come from another site (403). The same servers never serve
files from outside the project. No network, no GPU: FastAPI's TestClient, plus the preview server on an ephemeral port."""
from __future__ import annotations

import ast
import http.client
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.server import local_only
from engine.server.local_only import host_allowed, origin_allowed

ROOT = Path(__file__).resolve().parent.parent
PORT = 5180
LOCAL = f"http://127.0.0.1:{PORT}"
EVIL_HOST = {"Host": f"evil.example:{PORT}"}


# ---------------------------------------------------------------- the checks themselves

@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"[::1]:{PORT}", f"LOCALHOST:{PORT}"])
def test_local_hosts_are_allowed(host):
    assert host_allowed(host, PORT)


@pytest.mark.parametrize("host", [None, "", f"evil.example:{PORT}", f"127.0.0.1.evil.example:{PORT}", f"localhost.evil.example:{PORT}",
                                  "127.0.0.1:9999", "localhost", "127.0.0.1:", "127.0.0.1:abc", f"0.0.0.0:{PORT}", f"[::1]x:{PORT}",
                                  f"user@127.0.0.1:{PORT}", f"127.0.0.1:{PORT} evil.example", f"192.168.1.5:{PORT}"])
def test_other_hosts_are_refused(host):
    assert not host_allowed(host, PORT)


def test_the_port_is_the_servers_own_unless_a_dev_port_is_named():
    assert not host_allowed("localhost:5181", PORT)
    assert host_allowed("localhost:5181", PORT, extra_ports=(5181,))
    assert not host_allowed("evil.example:5181", PORT, extra_ports=(5181,))
    assert host_allowed("localhost", 80) and host_allowed("127.0.0.1:80", 80)


def test_origins_for_requests_that_change_things():
    ok = lambda o=None, r=None, extra=(): origin_allowed(o, r, PORT, extra)
    assert ok() and ok(LOCAL) and ok(f"http://localhost:{PORT}") and ok(f"http://[::1]:{PORT}")
    assert ok(r=f"{LOCAL}/sb/mine?x=1") and ok(LOCAL, r="https://evil.example/x")      # Origin wins over Referer
    for bad in ("https://evil.example", f"http://evil.example:{PORT}", "null", f"http://127.0.0.1:{PORT + 1}", f"https://127.0.0.1:{PORT}",
                f"http://127.0.0.1.evil.example:{PORT}", "http://localhost", ""):
        assert not ok(bad), bad
    assert not ok(r="https://evil.example/page") and not ok(r="not a url") and not ok(r="")
    assert not ok("http://localhost:5181") and ok("http://localhost:5181", extra=(5181,))


# ---------------------------------------------------------------- the Studio app

@pytest.fixture()
def studio(tmp_path, monkeypatch):
    from engine.server import app as server
    (tmp_path / "projects").mkdir()
    (tmp_path / "examples").mkdir()
    monkeypatch.setattr(server, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(server, "EXAMPLES", tmp_path / "examples")
    return TestClient(server.app, base_url=LOCAL), tmp_path


def test_a_request_to_the_right_host_passes(studio):
    c, _ = studio
    assert c.get("/api/info").status_code == 200
    for host in (f"localhost:{PORT}", f"[::1]:{PORT}"):
        assert c.get("/api/info", headers={"Host": host}).status_code == 200


def test_a_request_with_another_host_is_refused_whatever_the_method(studio):
    c, tmp = studio
    for method, url, kw in (("GET", "/api/info", {}), ("GET", "/api/projects", {}), ("GET", "/files/x/y", {}),
                            ("POST", "/api/projects", {"json": {"name": "p"}}), ("PUT", "/api/projects/p/spec", {"json": {"yaml": "x"}}),
                            ("DELETE", "/api/projects/p", {})):
        r = c.request(method, url, headers=EVIL_HOST, **kw)
        assert r.status_code == 400, (method, url)
        assert "Host" in r.text
    assert not list((tmp / "projects").iterdir())            # nothing was created


def test_a_cross_origin_post_is_refused_and_creates_nothing(studio):
    c, tmp = studio
    for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Origin": f"http://evil.example:{PORT}"},
                    {"Referer": "https://evil.example/page"}):
        r = c.post("/api/projects", json={"name": "stolen"}, headers=headers)
        assert r.status_code == 403, headers
    assert not (tmp / "projects" / "stolen").exists()
    c.post("/api/projects", json={"name": "mine"})
    for method in ("PUT", "PATCH", "DELETE"):
        assert c.request(method, "/api/projects/mine/spec", headers={"Origin": "https://evil.example"}, json={"yaml": "name: x\n"}).status_code == 403
    assert c.post("/api/projects/mine/build", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/projects/mine/inputs", files=[("files", ("a.txt", b"x"))], headers={"Origin": "https://evil.example"}).status_code == 403


def test_a_same_origin_post_passes(studio):
    c, tmp = studio
    assert c.post("/api/projects", json={"name": "a"}, headers={"Origin": LOCAL}).status_code == 200
    assert c.post("/api/projects", json={"name": "b"}, headers={"Origin": f"http://localhost:{PORT}"}).status_code == 200
    assert c.post("/api/projects", json={"name": "c"}, headers={"Referer": f"{LOCAL}/projects/c"}).status_code == 200
    assert c.post("/api/projects", json={"name": "d"}).status_code == 200                       # curl, scripts: no Origin
    assert sorted(p.name for p in (tmp / "projects").iterdir()) == ["a", "b", "c", "d"]


def test_the_vite_dev_server_keeps_working_for_the_studio_ui(studio):
    """`npm run dev:ui` serves the UI on 5181 and proxies /api here: its Host and Origin carry that port."""
    c, _ = studio
    dev = {"Host": "localhost:5181", "Origin": "http://localhost:5181"}
    assert c.get("/api/info", headers=dev).status_code == 200
    assert c.post("/api/projects", json={"name": "from-dev-ui"}, headers=dev).status_code == 200
    assert c.post("/api/projects", json={"name": "x"}, headers={"Host": "evil.example:5181", "Origin": "http://evil.example:5181"}).status_code == 400


def test_a_foreign_site_can_neither_read_nor_change_through_the_browser(studio):
    """No CORS headers are sent, so a page on another site cannot read a response, and the preflight-free ways of changing
    something (simple form POSTs) carry an Origin that is refused."""
    c, _ = studio
    r = c.get("/api/info", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    r = c.options("/api/projects", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_the_studio_file_routes_stay_inside_the_project(studio):
    c, tmp = studio
    c.post("/api/projects", json={"name": "mine"})
    (tmp / "projects" / "secret.txt").write_text("secret")
    for url in ("/files/mine/..%2Fsecret.txt", "/files/mine/%2e%2e/secret.txt", "/files/mine/inputs/..%2F..%2Fsecret.txt",
                "/preview/mine/..%2Fsite.yaml", "/preview/mine/%2e%2e%2fsecret.txt", "/files/mine//etc/passwd"):
        r = c.get(url)
        assert r.status_code in (403, 404) and "secret" not in r.text, url


# ---------------------------------------------------------------- the storyboard editor and direction boards

@pytest.fixture()
def one_project(tmp_path):
    from engine.project import Project
    root = tmp_path / "demo"
    (root / "inputs").mkdir(parents=True)
    (root / "storyboard").mkdir()
    (root / "storyboard" / "storyboard.html").write_text("<p>board</p>")
    (root / "site.yaml").write_text("name: demo\nsections:\n  - { id: a, type: type, text: hi }\n", encoding="utf-8")
    (tmp_path / "secret.png").write_bytes(b"\x89PNG secret")
    (tmp_path / "secret.txt").write_text("secret")
    return Project(root)


def test_the_storyboard_editor_checks_host_and_origin_and_stays_in_its_folders(one_project):
    from engine.storyboard.edit.api import make_app
    c = TestClient(make_app(one_project), base_url="http://127.0.0.1:8971")
    assert c.get("/sb/demo/files/storyboard.html").status_code == 200
    assert c.get("/sb/demo/files/storyboard.html", headers={"Host": "evil.example:8971"}).status_code == 400
    assert c.post("/api/sb/demo/lock", json={"shot": "a", "locked": True}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/sb/demo/lock", json={"shot": "a", "locked": True}, headers={"Origin": "http://127.0.0.1:8971"}).status_code != 403
    assert c.post("/api/sb/demo/lock", json={"shot": "a", "locked": True}, headers={"Origin": "http://localhost:5181"}).status_code == 403   # the Vite port is the Studio app's only
    for url in ("/sb/demo/files/..%2Fsite.yaml", "/sb/demo/files/%2e%2e/%2e%2e/secret.txt", "/sb/demo/dist/..%2Fsite.yaml",
                "/sb/demo/inspect/..%2F..%2Fsite.yaml", "/api/sb/demo/img?p=../secret.png", "/api/sb/demo/img?p=../../secret.png",
                "/api/sb/demo/img?p=secret.png"):
        r = c.get(url)
        assert r.status_code in (403, 404) and "secret" not in r.text and "PNG" not in r.text, url


def test_the_direction_boards_check_host_and_origin_and_stay_in_their_folder(one_project):
    from engine.directions.api import make_app
    (one_project.root / "directions").mkdir()
    (one_project.root / "directions" / "board.html").write_text("<html><head></head><body>b</body></html>")
    c = TestClient(make_app(one_project), base_url="http://127.0.0.1:8981")
    assert c.get("/dir/demo").status_code == 200
    assert c.get("/dir/demo", headers={"Host": "evil.example:8981"}).status_code == 400
    assert c.post("/api/dir/demo/undo", headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/dir/demo/pick", json={"id": "a"}, headers={"Referer": "https://evil.example/"}).status_code == 403
    for url in ("/dir/demo/files/..%2Fsite.yaml", "/dir/demo/files/%2e%2e/secret.txt", "/dir/demo/files//etc/passwd"):
        assert c.get(url).status_code in (403, 404), url


# ---------------------------------------------------------------- the preview server

def _request(port: int, host: str | None, path: str = "/index.html", method: str = "GET") -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest(method, path, skip_host=True)
    if host is not None:
        conn.putheader("Host", host)
    conn.endheaders()
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, body


def test_the_preview_server_binds_to_localhost_and_checks_the_host(tmp_path):
    from engine.serve import serve
    (tmp_path / "index.html").write_text("<p>site</p>")
    (tmp_path.parent / "outside.txt").write_text("outside")
    httpd = serve(tmp_path, 0, background=True)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
        port = httpd.server_address[1]
        assert _request(port, f"127.0.0.1:{port}") == (200, b"<p>site</p>")
        assert _request(port, f"localhost:{port}")[0] == 200
        assert _request(port, f"[::1]:{port}")[0] == 200
        for bad in (f"evil.example:{port}", "localhost", f"localhost:{port + 1}", None):
            assert _request(port, bad)[0] == 400, bad
        assert _request(port, f"evil.example:{port}", method="HEAD")[0] == 400
        status, body = _request(port, f"127.0.0.1:{port}", "/../outside.txt")
        assert b"outside" not in body
        status, body = _request(port, f"127.0.0.1:{port}", "/%2e%2e/outside.txt")
        assert b"outside" not in body
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---------------------------------------------------------------- every server in the engine binds to 127.0.0.1

def _calls(name_ends: tuple[str, ...]):
    for f in (ROOT / "engine").rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and ast.unparse(node.func).endswith(name_ends):
                yield f, node


def test_every_uvicorn_run_binds_to_127_0_0_1():
    seen = list(_calls(("uvicorn.run",)))
    assert len(seen) >= 3          # studio ui, the storyboard editor, the direction boards
    for f, node in seen:
        host = next((k.value for k in node.keywords if k.arg == "host"), None)
        assert isinstance(host, ast.Constant) and host.value == "127.0.0.1", f"{f.name}:{node.lineno} must bind host='127.0.0.1'"


def test_every_http_server_binds_to_127_0_0_1():
    seen = list(_calls(("HTTPServer", "ThreadingHTTPServer", "TCPServer", "ThreadingTCPServer")))
    assert seen
    for f, node in seen:
        addr = node.args[0] if node.args else None
        assert isinstance(addr, ast.Tuple) and isinstance(addr.elts[0], ast.Constant) and addr.elts[0].value == "127.0.0.1", \
            f"{f.name}:{node.lineno} must bind ('127.0.0.1', port)"


def test_every_fastapi_app_has_the_local_only_middleware():
    """A FastAPI() created anywhere in the engine must add LocalOnly (so a new server can't forget it)."""
    for f in (ROOT / "engine").rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        if "FastAPI(" in text and "import FastAPI" in text or "FastAPI(title" in text:
            assert "LocalOnly" in text, f"{f.name} creates a FastAPI app without the LocalOnly middleware"
    assert local_only.LOCAL_NAMES == ("127.0.0.1", "localhost", "[::1]")


# ---------------------------------------------------------------- over a real socket

def test_the_studio_app_over_a_real_uvicorn_socket(tmp_path, monkeypatch):
    """TestClient fakes the connection; this checks the Host/port logic against what uvicorn really reports."""
    import time
    import httpx
    import uvicorn
    from engine.server import app as server
    monkeypatch.setattr(server, "PROJECTS", tmp_path / "projects")
    (tmp_path / "projects").mkdir()
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=0, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    try:
        for _ in range(100):
            if srv.started:
                break
            time.sleep(0.05)
        assert srv.started
        port = srv.servers[0].sockets[0].getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        assert httpx.get(f"{base}/api/info").status_code == 200
        assert httpx.get(f"http://localhost:{port}/api/info").status_code in (200, 400)    # localhost may resolve to ::1 only
        assert httpx.get(f"{base}/api/info", headers={"Host": f"evil.example:{port}"}).status_code == 400
        assert httpx.post(f"{base}/api/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert httpx.post(f"{base}/api/projects", json={"name": "x"}, headers={"Origin": base}).status_code == 200
        assert not (tmp_path / "projects" / "stolen").exists()
    finally:
        srv.should_exit = True
        t.join(timeout=10)
