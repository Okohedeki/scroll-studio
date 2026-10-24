"""A site.yaml is a document that may come from anyone. Hostile specs: paths that leave the project, names that would
escape a folder, text that would turn into script on the built page. No GPU, no ComfyUI, no network."""
from __future__ import annotations

import json
import os
import re
import textwrap
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from engine import inputs, safety
from engine.compile import compiler, fonts
from engine.project import BuildError, Project, child, safe_name
from engine.spec import ImageInput, Site

OUTSIDE = "outside-secret"


# ---------------------------------------------------------------- helpers

def make_project(tmp_path: Path, spec: str, files: dict[str, str] | None = None) -> Project:
    root = tmp_path / "proj"
    (root / "inputs").mkdir(parents=True)
    (tmp_path / OUTSIDE).mkdir(exist_ok=True)
    (tmp_path / OUTSIDE / "secret.txt").write_text("top secret", encoding="utf-8")
    (tmp_path / OUTSIDE / "secret.csv").write_text("series,x,y\na,1,2\n", encoding="utf-8")
    (tmp_path / OUTSIDE / "secret.md").write_text("# secret", encoding="utf-8")
    (tmp_path / OUTSIDE / "secret.mp4").write_bytes(b"not a video")
    for name, text in (files or {}).items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    (root / "site.yaml").write_text(textwrap.dedent(spec), encoding="utf-8")
    return Project(root)


def symlink_or_skip(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("this account can't create symlinks here")


def build(project: Project, monkeypatch) -> str:
    monkeypatch.setattr(fonts, "vendor", lambda links, dist, log=print: None)     # no network in tests
    return compiler.build_site(project, log=lambda m: None).read_text(encoding="utf-8")


class Hostile(HTMLParser):
    """Collects what would run in a browser: script elements, event-handler attributes, javascript:/data: links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []
        self._in_script = False
        self._script_type = ""

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k.lower().startswith("on"):
                self.found.append(f"<{tag} {k}>")
            if k.lower() in ("href", "src", "action", "formaction", "poster", "xlink:href") and v:
                if not safety.is_safe_url(v, data_images=k.lower() in ("src", "poster") or tag == "link"):
                    self.found.append(f"<{tag} {k}={v[:30]}>")
        if tag == "script":
            self._in_script = True
            self._script_type = dict(attrs).get("type", "")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script and self._script_type == "" and "alert(" in data:
            self.found.append("inline script with alert")


def hostile_findings(html: str) -> list[str]:
    h = Hostile()
    h.feed(html)
    return h.found


# ---------------------------------------------------------------- paths stay inside the project

# drive and root-relative Windows paths only leave the project on Windows; elsewhere they are plain file names
WINDOWS_ONLY = pytest.mark.skipif(os.name != "nt", reason="a Windows path is a plain file name on other systems")


@pytest.mark.parametrize("ref", [
    f"../{OUTSIDE}/secret.txt", "inputs/../../" + OUTSIDE + "/secret.txt", "inputs/./../../" + OUTSIDE + "/secret.txt",
    "/etc/passwd", "inputs/\x00evil",
    *[pytest.param(w, marks=WINDOWS_ONLY) for w in ("\\Windows\\win.ini", "C:\\Windows\\win.ini", "C:/Windows/win.ini")],
])
def test_project_path_refuses_names_that_leave_the_project(tmp_path, ref):
    p = make_project(tmp_path, "name: x\nsections: []\n")
    with pytest.raises(BuildError):
        p.path(ref)


def test_project_path_resolves_inside_names(tmp_path):
    p = make_project(tmp_path, "name: x\nsections: []\n", {"inputs/a.txt": "a"})
    assert p.path("inputs/a.txt") == p.root / "inputs" / "a.txt"
    assert p.path("inputs/../inputs/a.txt") == p.root / "inputs" / "a.txt"
    assert p.path(".") == p.root


def test_project_root_is_resolved_so_links_in_the_root_do_not_confuse_the_check(tmp_path):
    real = tmp_path / "real"
    (real / "inputs").mkdir(parents=True)
    (real / "inputs" / "a.txt").write_text("a")
    link = tmp_path / "link"
    symlink_or_skip(link, real)
    p = Project(link)
    assert p.root == real.resolve()
    assert p.path("inputs/a.txt").read_text() == "a"
    with pytest.raises(BuildError):
        p.path("../real2")


def test_a_symlink_inside_the_project_that_points_out_is_refused(tmp_path):
    p = make_project(tmp_path, "name: x\nsections: []\n")
    symlink_or_skip(p.inputs / "link.txt", tmp_path / OUTSIDE / "secret.txt")
    with pytest.raises(BuildError):
        p.path("inputs/link.txt")
    with pytest.raises(BuildError):
        inputs.resolve_path(p, "inputs/link.txt")
    symlink_or_skip(p.root / "linked-dir", tmp_path / OUTSIDE)
    with pytest.raises(BuildError):
        p.path("linked-dir/secret.txt")


@pytest.mark.parametrize("ref", [f"../{OUTSIDE}/secret.txt", "/etc/passwd", "C:\\Windows\\win.ini"])
def test_image_and_file_inputs_go_through_the_project_check(tmp_path, ref):
    p = make_project(tmp_path, "name: x\nsections: []\n")
    with pytest.raises(BuildError):
        inputs.resolve_path(p, ref)
    with pytest.raises(BuildError):
        inputs.resolve_image(p, ImageInput(file=ref))
    with pytest.raises(BuildError):
        inputs.resolve_image(p, ref)


def test_a_build_refuses_a_page_source_outside_the_project(tmp_path, monkeypatch):
    p = make_project(tmp_path, f"""
        name: x
        pages: [ {{ slug: privacy, title: Privacy, source: "../{OUTSIDE}/secret.md" }} ]
        sections: [ {{ type: intro, title: Hi }} ]
    """)
    with pytest.raises(BuildError, match="outside the project"):
        build(p, monkeypatch)
    assert not (p.dist / "privacy").exists()


def test_a_build_refuses_a_hero_video_that_leaves_through_dots_or_a_link(tmp_path, monkeypatch):
    p = make_project(tmp_path, f"""
        name: x
        sections: [ {{ type: hero, title: Hi, video: "inputs/../../{OUTSIDE}/secret.mp4" }} ]
    """)
    with pytest.raises(BuildError, match="outside the project"):
        build(p, monkeypatch)
    symlink_or_skip(p.inputs / "clip.mp4", tmp_path / OUTSIDE / "secret.mp4")
    p.spec_path.write_text("name: x\nsections: [ { type: hero, title: Hi, video: inputs/clip.mp4 } ]\n", encoding="utf-8")
    with pytest.raises(BuildError, match="outside the project"):
        build(p, monkeypatch)
    assert not list((p.dist / "assets").rglob("clip.mp4")) and not list((p.dist / "assets").rglob("secret.mp4"))


def test_a_code_scene_will_not_read_a_file_outside_the_project(tmp_path, monkeypatch):
    p = make_project(tmp_path, f"""
        name: x
        sections:
          - id: tour
            type: code
            files: [ {{ path: a.txt, file: "../{OUTSIDE}/secret.txt" }} ]
    """)
    with pytest.raises(BuildError, match="outside the project"):
        build(p, monkeypatch)


def test_a_chart_will_not_read_data_outside_the_project(tmp_path, monkeypatch):
    p = make_project(tmp_path, f"""
        name: x
        sections: [ {{ id: c, type: chart, data: "../{OUTSIDE}/secret.csv", x: x, y: y, series: series }} ]
    """)
    with pytest.raises(BuildError, match="outside the project"):
        build(p, monkeypatch)


# ---------------------------------------------------------------- names that become folders and links

@pytest.mark.parametrize("bad", ["../x", "a/b", "a\\b", "..", ".", "", ".hidden", "C:x", "a\x00b", " a", "a|b"])
def test_child_refuses_anything_but_one_plain_name(tmp_path, bad):
    with pytest.raises(ValueError):
        child(tmp_path, bad)


def test_child_allows_folders_people_already_have(tmp_path):
    assert child(tmp_path, "My Site 2") == tmp_path / "My Site 2"
    assert child(tmp_path, "tern-house_v2") == tmp_path / "tern-house_v2"


@pytest.mark.parametrize("bad", ["a b", "a/b", "../x", "x..y", "-x", "", "a" * 101])
def test_safe_name_is_strict(bad):
    with pytest.raises(ValueError):
        safe_name(bad)


@pytest.mark.parametrize("bad_id", ["../../x", "..", "a/b", "a\\b", "a b", "<x>", "", "x" * 65, ".hidden"])
def test_section_ids_that_would_be_folders_are_refused(bad_id):
    with pytest.raises(ValidationError, match="id"):
        Site.model_validate({"name": "x", "sections": [{"id": bad_id, "type": "type", "text": "hi"}]})


def test_a_page_slug_cannot_leave_dist():
    for bad in ("../x", "a/../b", "..", "a b", "/", ""):
        with pytest.raises(ValidationError, match="slug"):
            Site.model_validate({"name": "x", "pages": [{"slug": bad, "title": "t", "source": "p.md"}], "sections": []})
    site = Site.model_validate({"name": "x", "pages": [{"slug": "/legal/privacy/", "title": "t", "source": "p.md"}], "sections": []})
    assert site.pages[0].slug == "legal/privacy"


def test_a_studio_light_is_a_name_not_a_path():
    spec = {"name": "x", "sections": [{"id": "s", "type": "inside", "model": "product", "hdri": "../../../etc/passwd", "stops": []}]}
    with pytest.raises(ValidationError, match="hdri"):
        Site.model_validate(spec)


# ---------------------------------------------------------------- yaml

def test_yaml_with_python_objects_is_refused(tmp_path):
    p = make_project(tmp_path, "name: !!python/object/apply:os.getcwd []\nsections: []\n")
    with pytest.raises(yaml.YAMLError):
        p.raw()


def test_no_unsafe_yaml_loader_anywhere_in_the_engine():
    bad = []
    for f in (Path(__file__).resolve().parent.parent / "engine").rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"yaml\.(load|load_all|unsafe_load|full_load)\(|Loader=(yaml\.)?(Loader|UnsafeLoader|FullLoader)|typ\s*=\s*['\"]unsafe", text):
            bad.append(f"{f.name}: {m.group(0)}")
    assert not bad, bad


# ---------------------------------------------------------------- text becomes text

def test_links_must_be_safe_schemes():
    for ok in ("#hero", "https://example.com/a?b=c", "mailto:a@b.c", "tel:+123", "pricing/", "/pricing", "../x", "inputs/a b.png"):
        assert safety.is_safe_url(ok), ok
    for bad in ("javascript:alert(1)", " JaVaScRiPt:alert(1)", "java\tscript:alert(1)", "java&#115;cript:alert(1)",
                "&#x6A;avascript:alert(1)", "data:text/html,<script>alert(1)</script>", "vbscript:x", "file:///etc/passwd"):
        assert not safety.is_safe_url(bad), bad
    assert safety.is_safe_url("data:image/png;base64,AAAA", data_images=True)
    assert not safety.is_safe_url("data:text/html;base64,AAAA", data_images=True)


@pytest.mark.parametrize("href", ["javascript:alert(1)", "  javascript:alert(1)", "data:text/html,x", "jav\nascript:alert(1)"])
def test_a_button_or_link_cannot_carry_a_script_url(href):
    for section in ({"type": "intro", "title": "t", "button": {"label": "go", "href": href}},
                    {"type": "cta", "title": "t", "button": {"label": "go", "href": href}}):
        with pytest.raises(ValidationError, match="allowed link"):
            Site.model_validate({"name": "x", "sections": [section]})
    with pytest.raises(ValidationError, match="allowed link"):
        Site.model_validate({"name": "x", "nav": {"links": [{"label": "l", "href": href}]}, "sections": []})
    with pytest.raises(ValidationError, match="allowed link"):
        Site.model_validate({"name": "x", "footer": {"links": [{"label": "l", "href": href}]}, "sections": []})
    with pytest.raises(ValidationError, match="allowed link"):
        Site.model_validate({"name": "x", "sections": [{"type": "gallery", "items": [{"title": "t", "href": href}]}]})


def test_the_finished_page_drops_any_link_a_browser_would_run():
    page = ('<a href="javascript:alert(1)">a</a> <a href=" jav&#x09;ascript:alert(1)">b</a> <a href="https://ok.example">c</a> '
            '<img src="data:image/png;base64,AAAA"> <iframe src="data:text/html,x"></iframe> <link rel="icon" href="data:image/svg+xml,%3Csvg%3E">'
            '<form action="javascript:x()"></form> <a href="#top">d</a>')
    out = safety.clean_page_urls(page)
    assert not hostile_findings(out)
    assert 'href="https://ok.example"' in out and 'href="#top"' in out and "data:image/png" in out and "data:image/svg+xml" in out


def test_css_values_cannot_close_the_style_block():
    for bad in ("red;} </style><script>alert(1)</script>", "url(javascript:alert(1))", "red /* x */", "a{b}", "x\\ny", "expression(alert(1))"):
        assert not safety.css_value_ok(bad), bad
    for ok in ("#fff", "#ffffff", "rgba(10, 20, 30, .5)", "0.5rem", "calc(2px + 1em)", "tomato"):
        assert safety.css_value_ok(ok), ok


def test_hostile_theme_values_are_refused():
    base = {"name": "x", "sections": []}
    for theme in ({"colors": {"bg": "red;}</style><script>alert(1)</script>"}}, {"fonts": {"display": 'A"; } </style><script>x</script>'}},
                  {"fonts": {"x}</style><script>alert(1)</script>": "Inter"}}, {"radius": "4px;}</style><script>alert(1)</script>"}):
        with pytest.raises(ValidationError):
            Site.model_validate({**base, "theme": theme})


def test_hostile_text_in_every_copy_field_is_escaped_on_the_built_page(tmp_path, monkeypatch):
    bad_tag, bad_attr = "<script>alert(1)</script>", "<img src=x onerror=alert(2)>"
    p = make_project(tmp_path, f"""
        name: "{bad_tag}"
        description: "{bad_attr}"
        nav: {{ cta: {{ label: "{bad_tag}", href: "#x" }} }}
        footer: {{ left: "{bad_tag}", right: "{bad_attr}" }}
        sections:
          - {{ id: hero, type: type, mode: reveal, text: "{bad_attr} <em>fine</em> {bad_tag}" }}
          - {{ id: tape, type: type, mode: swap, text: "{bad_tag}", words: ["{bad_attr}", "<em>ok</em>"] }}
          - {{ id: where, type: map, style: "https://tiles.example/style.json", markers: [ {{ lng: 1, lat: 2, label: "{bad_attr}" }} ],
              routes: [] }}
          - type: intro
            kicker: "{bad_attr}"
            title: "Say {bad_tag} <em>it</em>"
            body: "{bad_attr} <script>alert(3)</script>"
            button: {{ label: "{bad_attr}", href: "#x" }}
          - type: features
            title: "{bad_tag}"
            items: [ {{ tag: "{bad_attr}", title: "{bad_tag}", body: "{bad_attr}" }} ]
          - {{ type: quote, text: "{bad_tag}", who: "{bad_attr}" }}
          - {{ type: cta, title: "{bad_tag}", button: {{ label: "{bad_attr}", href: "mailto:a@b.c" }} }}
    """)
    html = build(p, monkeypatch)
    assert not hostile_findings(html), hostile_findings(html)
    assert "<script>alert" not in html and "<img src=x" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html          # shown as text, not dropped
    assert "<em>it</em>" in html                                        # the documented inline markup still works
    # kinetic type and map labels are set with innerHTML by the runtime: their text must arrive without raw tags
    configs = [json.loads(m) for m in re.findall(r'<script type="application/json" class="ss-config">(.*?)</script>', html, re.S)]
    flat = json.dumps(configs)
    assert "<img" not in flat and "<script" not in flat
    assert "<em>fine</em>" in flat and "<em>ok</em>" in flat and "&lt;img" in flat


def test_markdown_pages_show_raw_html_as_text_and_drop_script_links(tmp_path, monkeypatch):
    md = textwrap.dedent("""\
        # Privacy

        <script>alert(1)</script>

        <img src=x onerror=alert(2)>

        <div onclick="alert(3)">raw</div>

        [click](javascript:alert(4)) [also](java&#115;cript:alert(5)) ![x](javascript:alert(6))
        [fine](https://example.com) [mail](mailto:a@b.c) [anchor](#top) <https://auto.example>

        **bold**, *emphasis*, `code`, a list:

        - one
        - two

        | a | b |
        |---|---|
        | 1 | 2 |

        ```
        <script>in a code block</script>
        ```
    """)
    p = make_project(tmp_path, """
        name: x
        pages: [ { slug: privacy, title: Privacy, source: pages/privacy.md } ]
        sections: [ { type: intro, title: Hi } ]
    """, {"pages/privacy.md": md})
    build(p, monkeypatch)
    page = (p.dist / "privacy" / "index.html").read_text(encoding="utf-8")
    assert not hostile_findings(page), hostile_findings(page)
    assert "<script>alert" not in page and "<img src=x" not in page and "<div onclick" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    for kept in ("<strong>bold</strong>", "<em>emphasis</em>", "<code>code</code>", "<li>one</li>", "<table>", 'href="https://example.com"',
                 'href="mailto:a@b.c"', 'href="#top"', 'href="https://auto.example"', "<h1"):
        assert kept in page, kept


def test_the_vector_scene_does_not_pass_attribute_markup_through(tmp_path):
    from engine.scenes import vector
    from engine.spec import VectorScene
    sec = VectorScene.model_validate({"id": "v", "type": "vector", "svg": "inputs/a.svg"})
    ok = tmp_path / "ok.svg"
    ok.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M1 1 L5 5 Z" fill="#c40" transform="translate(1,2)"/></svg>',
                  encoding="utf-8")
    out = tmp_path / "out.svg"
    assert vector._normalise(ok, out, sec)["paths"] == 1
    for evil in ("M0 0&quot; onmouseover=&quot;alert(1)", "M0 0 L1 1&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"):   # XML-escaped, so they parse
        bad = tmp_path / "bad.svg"
        bad.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="{evil}"/></svg>', encoding="utf-8")
        with pytest.raises(BuildError, match="path data"):
            vector._normalise(bad, tmp_path / "bad-out.svg", sec)
    fill = tmp_path / "fill.svg"
    fill.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M1 1 L5 5 Z" fill="red&quot; onload=&quot;alert(1)"/></svg>',
                    encoding="utf-8")
    vector._normalise(fill, out, sec)
    assert "onload" not in out.read_text(encoding="utf-8")


def test_the_examples_still_validate_and_keep_their_ids():
    root = Path(__file__).resolve().parent.parent / "examples"
    specs = sorted(root.glob("*/site.yaml"))
    assert specs
    for f in specs:
        Site.model_validate(yaml.safe_load(f.read_text(encoding="utf-8")))


# ---------------------------------------------------------------- the Studio server's names and uploads

@pytest.fixture()
def studio(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from engine.server import app as server
    (tmp_path / "projects").mkdir()
    (tmp_path / "examples" / "demo").mkdir(parents=True)
    (tmp_path / "examples" / "demo" / "site.yaml").write_text("name: demo\nsections: []\n", encoding="utf-8")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "site.yaml").write_text("name: private\nsections: []\n", encoding="utf-8")
    monkeypatch.setattr(server, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(server, "EXAMPLES", tmp_path / "examples")
    client = TestClient(server.app, base_url="http://127.0.0.1:5180")
    assert client.post("/api/projects", json={"name": "mine"}).status_code == 200
    return client, tmp_path


def test_studio_refuses_project_names_that_climb_out_of_the_projects_folder(studio):
    client, tmp = studio
    for name in ("..%2Fprivate", "%2e%2e", "..%5Cprivate", ".hidden"):
        assert client.get(f"/api/projects/{name}/spec").status_code == 404, name
    assert client.get("/api/projects/mine/spec").status_code == 200


def test_studio_refuses_a_new_project_copied_from_outside_the_examples(studio):
    client, tmp = studio
    assert client.post("/api/projects", json={"name": "copy", "example": "../private"}).status_code == 400
    assert client.post("/api/projects", json={"name": "copy", "example": "nope"}).status_code == 404
    assert not (tmp / "projects" / "copy").exists()
    assert client.post("/api/projects", json={"name": "from-demo", "example": "demo"}).status_code == 200


def test_studio_uploads_keep_to_the_inputs_folder(studio):
    client, tmp = studio
    ok = client.post("/api/projects/mine/inputs", files=[("files", ("../../escape.txt", b"x"))])
    assert ok.status_code == 200 and ok.json()["saved"] == ["inputs/escape.txt"]
    assert not (tmp / "escape.txt").exists() and (tmp / "projects" / "mine" / "inputs" / "escape.txt").exists()
    for bad in ("", ".", "..", ".hidden"):
        r = client.post("/api/projects/mine/inputs", files=[("files", (bad, b"x"))])
        assert r.status_code in (400, 422), bad


def test_studio_upload_will_not_write_through_a_link_that_leaves_the_project(studio):
    client, tmp = studio
    target = tmp / "private" / "target.txt"
    target.write_text("keep me")
    symlink_or_skip(tmp / "projects" / "mine" / "inputs" / "link.txt", target)
    r = client.post("/api/projects/mine/inputs", files=[("files", ("link.txt", b"overwritten"))])
    assert r.status_code == 400 and target.read_text() == "keep me"


def test_studio_upload_has_a_size_limit(studio, monkeypatch):
    from engine.server import app as server
    client, tmp = studio
    monkeypatch.setattr(server, "MAX_UPLOAD", 1024)
    r = client.post("/api/projects/mine/inputs", files=[("files", ("big.bin", b"x" * 4096))])
    assert r.status_code == 413
    assert not (tmp / "projects" / "mine" / "inputs" / "big.bin").exists()


def test_studio_file_routes_refuse_paths_outside_the_project(studio):
    client, tmp = studio
    (tmp / "private" / "secret.txt").write_text("secret")
    (tmp / "projects" / "mine" / "inputs" / "a.txt").write_text("a")
    assert client.get("/files/mine/inputs/a.txt").status_code == 200
    for path in ("..%2F..%2Fprivate%2Fsecret.txt", "%2e%2e/%2e%2e/private/secret.txt", "inputs%2F..%2F..%2F..%2Fprivate%2Fsecret.txt"):
        assert client.get(f"/files/mine/{path}").status_code in (403, 404), path
    symlink_or_skip(tmp / "projects" / "mine" / "inputs" / "out.txt", tmp / "private" / "secret.txt")
    assert client.get("/files/mine/inputs/out.txt").status_code == 403
    assert client.get("/preview/mine/..%2Fsite.yaml").status_code in (403, 404)


def test_studio_recordings_get_a_safe_file_name(studio):
    client, tmp = studio
    r = client.post("/api/projects/mine/record", json={"section": "../../evil"})
    assert r.status_code == 400
