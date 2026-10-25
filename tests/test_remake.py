"""`studio remake <url>` (issue #118): a live landing page read and told again as a scroll site.

No network: the fixture pages (tests/fixtures/remake/, invented brands) are parsed straight from their files, or served
from a local HTTP server on 127.0.0.1; any request to another host fails the test. Their pictures are drawn when a site
is served (the repository keeps no media under tests/). Playwright is used only by the one test that reads a page in
Chromium, which is skipped when the browser is not installed."""
from __future__ import annotations

import functools
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
import yaml

from engine import remake as rm
from engine.compile.layout_snapshot import page_html
from engine.project import BuildError, Project

FIXTURES = Path(__file__).parent / "fixtures" / "remake"
# The pictures each fixture page links to, by size: photos, a share card, logos, an avatar and tracking pixels.
PICTURES = {
    "quillfern": {"img/hero.jpg": (1600, 900), "img/share.jpg": (1200, 630), "img/map-view.png": (1200, 800),
                  **{f"img/client-logo-{i}.png": (120, 40) for i in range(1, 5)}, "img/track.gif": (1, 1)},
    "driftmoss": {"media/coast-dawn.jpg": (1920, 1080), **{f"media/trip-{i}.jpg": (900, 600) for i in range(1, 5)},
                  **{f"media/press-logo-{i}.png": (100, 36) for i in range(1, 4)}, "media/avatar-1.jpg": (64, 64),
                  "media/pixel.gif": (1, 1)},
}


def draw(path: Path, size: tuple[int, int], seed: int) -> None:
    """A small picture: a two-colour gradient with a disc on it."""
    from PIL import Image, ImageDraw
    w, h = size
    a, b = (40 + seed * 37 % 180, 60 + seed * 53 % 160, 90 + seed * 71 % 140), (230, 220 - seed * 13 % 90, 200)
    im = Image.linear_gradient("L").resize((w, h))
    im = Image.composite(Image.new("RGB", (w, h), a), Image.new("RGB", (w, h), b), im)
    ImageDraw.Draw(im).ellipse((w * .3, h * .3, w * .7, h * .8), fill=b[::-1])
    im.save(path)


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def serve(monkeypatch, tmp_path_factory):
    """serve('quillfern') -> the fixture site's base URL on a local server. Requests anywhere else fail."""
    servers = []
    real_get = requests.get

    def local_only(url, *a, **k):
        assert urlparse(url).hostname == "127.0.0.1", f"the network was used: {url}"
        return real_get(url, *a, **k)
    monkeypatch.setattr(requests, "get", local_only)

    def start(name: str) -> str:
        root = tmp_path_factory.mktemp("web") / name
        shutil.copytree(FIXTURES / name, root)
        for k, (rel, size) in enumerate(PICTURES.get(name, {}).items()):
            draw(root / rel, size, k)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(root)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}/"
    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def remake(url: str, tmp_path: Path, **kw) -> tuple[dict, dict, Project]:
    kw.setdefault("gpu", False)
    r = rm.remake(url, name=kw.pop("name", "site"), projects=tmp_path, browser=kw.pop("browser", False),
                  log=lambda m: None, **kw)
    p = Project(r["path"])
    return r, yaml.safe_load(p.spec_path.read_text(encoding="utf-8")), p


def types(spec: dict) -> list[str]:
    return [s["type"] for s in spec["sections"]]


def by_type(spec: dict, kind: str) -> list[dict]:
    return [s for s in spec["sections"] if s["type"] == kind]


# ---------------------------------------------------------------- reading markup (no network, no browser)

def test_a_semantic_page_is_read_into_hero_and_segments():
    page = rm.parse_page((FIXTURES / "quillfern" / "index.html").read_text(encoding="utf-8"), "https://quillfern.test/")
    assert page.site_name == "Quillfern" and page.lang == "en"
    assert page.kicker == "Research notebook" and page.headline == "Notes that <em>link themselves</em>"
    assert page.subhead.startswith("Write as you read.")
    assert [(b.text, b.href) for b in page.buttons] == [("Start free", "/signup"), ("See how it works", "#how")]
    assert page.nav_cta.text == "Start free" and page.nav_labels["faq"] == "FAQ"
    assert [i.url for i in page.hero_images] == ["https://quillfern.test/img/hero.jpg"]
    text = " ".join(e.text + e.title for seg in page.segments for e in seg)
    assert "cookies" not in text and "Skip to content" not in text and "Privacy" not in text   # banner, skip link, footer
    imgs = [im for _, im in page.images()]
    assert any(im.junk for im in imgs if "track.gif" in im.url)                           # the tracking pixel
    assert all(im.junk for im in imgs if "client-logo" in im.url)                         # the logo row


def test_a_page_without_sections_is_cut_at_its_headings():
    page = rm.parse_page((FIXTURES / "driftmoss" / "index.html").read_text(encoding="utf-8"), "https://driftmoss.test/")
    assert page.site_name == "Driftmoss Outfitters" and page.kicker == "Guided sea kayaking"
    assert page.headline == "Paddle the <em>quiet coast</em>"
    assert page.hero_images[0].url == "https://driftmoss.test/media/coast-dawn.jpg"       # an inline CSS background
    heads = [next(e.text for e in seg if e.kind == "h") for seg in page.segments]
    assert heads == ["Routes for every paddler", "Out on the water", "By the numbers", "What paddlers say",
                     "Good to know", "Ready for the water?"]
    assert "10% off" not in str(page.segments)                                             # the popup is left out
    lazy = [e.img.url for e in page.segments[1] if e.kind == "img"]
    assert "https://driftmoss.test/media/trip-3.jpg" in lazy                               # data-src behind a placeholder


def test_decoration_pictures_count_and_buttons_inside_links_keep_their_words():
    page = rm.parse_page('<body><section><div aria-hidden="true" style="background-image: url(/bg.jpg)"><span>decor'
                         '</span></div><h1>Hello there</h1><p>A subhead long enough to read.</p><a href="/go"><button>'
                         'Go now</button></a></section><section><h2>Next</h2><p>More.</p></section></body>',
                         "https://deco.test/")
    assert [i.url for i in page.hero_images] == ["https://deco.test/bg.jpg"]
    assert [(b.text, b.href, b.button) for b in page.buttons] == [("Go now", "/go", True)]
    assert "decor" not in str(page.segments)
    logo_h1 = rm.parse_page('<title>Oddhill | Bread</title><header><h1>Oddhill</h1></header><div><h2>Bread, slowly</h2>'
                            '<p>Baked overnight in a wood oven.</p></div>', "https://oddhill.test/")
    assert logo_h1.headline == "Bread, slowly"                                         # the logo h1 is not the headline


def test_odd_markup_never_crashes():
    for html in ("", "<p>just text", "<html><body><div><h2>Only a heading", "<<<>>><h1>Hi</h2></p></li><section>",
                 "<body>" + "<div>" * 500 + "<h1>Deep</h1>" + "</div>" * 10, "<h1></h1><img><a href='javascript:x'>x</a>"):
        page = rm.parse_page(html, "https://odd.test/")
        spec, _ = rm.story(page)
        assert spec["sections"]


# ---------------------------------------------------------------- the whole command, served locally

def test_a_landing_page_becomes_a_project_with_its_story(tmp_path, serve):
    base = serve("quillfern")
    r, spec, p = remake(base, tmp_path)
    assert types(spec) == ["parallax", "type", "features", "product", "stats", "timeline", "quote", "features", "faq",
                           "cta"]
    site = p.load()                                                         # the spec validates and loads
    opener = spec["sections"][0]
    step = opener["steps"][0]
    assert step["image"] == "inputs/hero.jpg" and step["intro"] is True
    assert step["title"] == "Notes that <em>link themselves</em>" and step["kicker"] == "Research notebook"
    assert step["button"] == {"label": "Start free", "href": base + "signup"}            # the CTA with its link
    assert spec["nav"]["cta"]["href"] == base + "signup"
    feats = by_type(spec, "features")[0]
    assert feats["id"] == "features" and feats["nav_label"] == "Features" and feats["kicker"] == "Features"
    assert [i["title"] for i in feats["items"]] == ["Linked by meaning", "Sources kept", "Shared shelves", "Works offline"]
    product = by_type(spec, "product")[0]
    assert product["tags"] == ["Clusters", "Timelines", "Citations"] and product["buttons"][0]["href"] == base + "tour"
    assert (p.root / product["image"]).exists()
    assert by_type(spec, "stats")[0]["items"][0] == {"value": "12", "unit": "k+", "label": "research teams"}
    assert [i["when"] for i in by_type(spec, "timeline")[0]["items"]] == ["01", "02", "03"]
    assert by_type(spec, "quote")[0]["who"] == "Mara Ellison, lead researcher at Northfold Lab"
    assert by_type(spec, "features")[1]["items"][1]["tag"] == "$8 a seat"
    assert by_type(spec, "faq")[0]["items"][0]["q"] == "Can I import from other apps?"
    assert by_type(spec, "cta")[0]["button"]["href"] == base + "signup"
    # pictures: the hero and the product shot, never the logos, the pixel or the unused share card
    assert sorted(f.name for f in (p.root / "inputs").iterdir()) == ["hero.jpg", "logo.svg", "see-the-shape-of.png"]
    # the brand, written in as editable tokens
    brand = spec["theme"]["from"]
    assert brand["colors"]["accent"] == "#5b3cc4" and brand["mode"] == "light"
    assert brand["fonts"] == {"display": "Fraunces", "body": "Inter"} and brand["radius"] == "999px"
    assert brand["logo"] == "inputs/logo.svg" and brand["source"] == base
    # a stand-in compile renders every section
    html = page_html(site)
    for s in site.sections:
        assert f'id="{s.id}"' in html
    for words in ("Linked by meaning", "Where are my notes stored?", "Start your reading map today", "Northfold Lab"):
        assert words in html
    assert "belong to its owner" in p.spec_path.read_text(encoding="utf-8") and "belong to its owner" in r["notice"]
    assert any("logos" in n for n in r["notes"])


def test_a_page_of_plain_divs_maps_by_shape(tmp_path, serve):
    base = serve("driftmoss")
    r, spec, p = remake(base, tmp_path)
    assert types(spec) == ["parallax", "type", "features", "strip", "stats", "quote", "faq", "cta"]
    assert spec["sections"][0]["steps"][0]["image"] == "inputs/hero.jpg"               # from the CSS background
    assert spec["sections"][0]["steps"][0]["button"]["href"] == base + "book"
    strip = by_type(spec, "strip")[0]
    assert len(strip["items"]) == 4 and strip["items"][2]["caption"] == "Tents on a beach at dusk"
    assert all((p.root / i["image"]).exists() for i in strip["items"])
    assert [s.get("unit") for s in by_type(spec, "stats")[0]["items"]] == [None, None, None]
    assert by_type(spec, "stats")[0]["items"][2]["value"] == "2,300"
    assert by_type(spec, "quote")[0] == {"type": "quote", "id": "what-paddlers-say", "who": "Ines, first-timer",
                                         "text": "I had never been in a kayak. By the end of the morning I was paddling "
                                                 "into a cave with seals watching us."}
    assert len(by_type(spec, "faq")[0]["items"]) == 3
    assert by_type(spec, "features")[0]["id"] == "routes"                                # the page's own anchor
    files = sorted(f.name for f in (p.root / "inputs").iterdir())
    assert not any("logo-" in f or "pixel" in f or "avatar" in f for f in files)
    brand = spec["theme"]["from"]
    assert brand["mode"] == "dark" and brand["colors"]["accent"] == "#e8783a" and spec["theme"]["preset"] == "night"
    html = page_html(p.load())
    assert all(f'id="{s.id}"' in html for s in p.load().sections)


def test_a_style_wears_the_brand(tmp_path, serve):
    base = serve("quillfern")
    _, spec, p = remake(base, tmp_path, style="bauhaus")
    assert spec["theme"]["style"] == "bauhaus" and spec["theme"]["from"]["colors"]["accent"] == "#5b3cc4"
    html = page_html(p.load())
    assert 'data-style="bauhaus"' in html and "Linked by meaning" in html
    with pytest.raises(BuildError, match="no style"):
        remake(base, tmp_path, name="other", style="no-such-style")
    assert not (tmp_path / "other").exists()


def test_with_a_gpu_the_hero_picture_opens_a_film(tmp_path, serve):
    _, spec, p = remake(serve("quillfern"), tmp_path, gpu=True)
    film = spec["sections"][0]
    assert film["type"] == "film" and film["beats"][0]["image"] == "inputs/hero.jpg"
    assert film["steps"][0]["intro"] is True
    assert 'id="open"' in page_html(p.load())                                          # it builds with stand-ins


def test_robots_txt_is_honoured(tmp_path, serve):
    with pytest.raises(rm.Refused, match="robots.txt"):
        remake(serve("closed"), tmp_path)                    # the remake's own agent is shut out; others are not
    with pytest.raises(rm.Refused):
        remake(serve("quillfern") + "drafts/next.html", tmp_path)
    assert not (tmp_path / "site").exists()


def test_an_existing_project_is_never_overwritten(tmp_path, serve):
    (tmp_path / "site").mkdir()
    with pytest.raises(BuildError, match="already exists"):
        remake(serve("quillfern"), tmp_path)
    assert rm.project_name(rm.Page(url="https://www.quill-fern.test/")) == "quill-fern"


def test_the_cli_and_the_mcp_tool(tmp_path, serve, monkeypatch):
    from typer.testing import CliRunner

    from engine import cli, config, mcp_server
    base = serve("quillfern")
    monkeypatch.setattr(config, "settings", lambda: {"projects": str(tmp_path)})
    monkeypatch.setattr(rm, "_browser_read", lambda url: (_ for _ in ()).throw(rm._NoBrowser("no browser here")))
    res = CliRunner().invoke(cli.app, ["remake", base, "--name", "qf", "--no-gpu"])
    assert res.exit_code == 0, res.output
    assert "next: studio storyboard qf" in res.output and "belong to its owner" in res.output
    assert "reading the page without a browser" in res.output
    assert CliRunner().invoke(cli.app, ["remake", base, "--name", "qf"]).exit_code != 0     # exists
    monkeypatch.setattr(mcp_server, "PROJECTS", tmp_path)
    out = mcp_server.remake_site(base, name="qf2", style="halftone", no_gpu=True)
    assert out["sections"][0]["type"] == "parallax" and (tmp_path / "qf2" / "site.yaml").exists()
    with pytest.raises(ValueError, match="robots"):
        mcp_server.remake_site(serve("closed"), name="qf3")


def _chromium() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_a_page_read_in_chromium(tmp_path, serve):
    base = serve("driftmoss")
    r, spec, p = remake(base, tmp_path, browser=True)
    assert types(spec)[:3] == ["parallax", "type", "features"] and "cta" in types(spec)
    assert spec["sections"][0]["steps"][0]["image"] == "inputs/hero.jpg"
    assert "10% off" not in p.spec_path.read_text(encoding="utf-8")
