"""theme.from (issue #117): a brand read from a web page, a logo or a brand.yaml, cached under .build/brand/, laid over
the preset and style, and written into site.yaml by `studio brand --from`. No network: the web page is
tests/fixtures/brand/page.html, served to the reader by a stand-in for the one function that fetches."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from engine import brand
from engine.compile import compiler, fonts, themes
from engine.project import BuildError, Project
from engine.spec import Site, Theme

FIXTURES = Path(__file__).parent / "fixtures" / "brand"
URL = "https://fernwick.example/"


def project(tmp_path: Path, theme: dict) -> Project:
    shutil.copytree(FIXTURES, tmp_path / "brand")
    (tmp_path / "site.yaml").write_text(yaml.safe_dump({"name": "Fernwick", "theme": theme, "sections": [
        {"type": "hero", "id": "hero", "title": "Coffee"}, {"type": "cta", "id": "cta", "title": "Order"}]}), encoding="utf-8")
    return Project(tmp_path)


@pytest.fixture
def web(monkeypatch):
    """The fixture page as if it were on the web; every URL fetched is recorded, anything else fails."""
    files = {URL: "page.html", URL + "site.css": "site.css", URL + "logo.svg": "logo.svg"}
    asked: list[str] = []

    def fetch(url, binary=False):
        asked.append(url)
        data = (FIXTURES / files[url]).read_bytes()
        return data if binary else data.decode("utf-8")
    monkeypatch.setattr(brand, "_fetch", fetch)
    return asked


def no_network(monkeypatch):
    monkeypatch.setattr(fonts, "vendor", lambda links, dist, log=print: None)
    monkeypatch.setattr(brand, "_fetch", lambda *a, **k: pytest.fail("the network was used"))


def test_a_saved_page_gives_colours_fonts_radius_and_logo(tmp_path, monkeypatch):
    no_network(monkeypatch)
    p = project(tmp_path, {"from": "brand/page.html"})
    t = p.load().theme._brand
    assert t["colors"] == {"bg": "#fbf7ef", "ink": "#1d2a24", "accent": "#0b6e4f", "accent2": "#f2a541"}
    assert t["fonts"] == {"display": "Fraunces", "body": "Inter"}          # "Fernwick Mono" is not on Google Fonts
    assert t["radius"] == "10px" and t["logo"] == "brand/logo.svg" and t["source"] == "brand/page.html"
    assert list((tmp_path / ".build" / "brand").glob("*.json"))             # kept for the next load


def test_the_brand_is_laid_over_the_preset_and_under_theme_overrides(tmp_path, monkeypatch):
    no_network(monkeypatch)
    p = project(tmp_path, {"preset": "night", "from": "brand/page.html", "fonts": {"body": "Figtree"}})
    theme = p.load().theme
    assert [n for n, _ in themes.layers(theme)] == ["defaults", "preset night", "brand", "site.yaml"]
    t = themes.resolve(theme)
    assert t["mode"] == "light" and t["colors"]["bg"] == "#fbf7ef" and t["colors"]["accent"] == "#0b6e4f"
    assert t["fonts"] == {"display": "Fraunces", "body": "Figtree", "mono": "IBM Plex Mono"}   # site.yaml still wins
    assert t["radius"] == "10px" and t["logo"] == "brand/logo.svg"
    html = compiler.build_site(p, log=lambda m: None).read_text(encoding="utf-8")
    assert "assets/_media/logo.svg" in html                                 # the brand's logo in the nav
    assert (tmp_path / "dist" / "assets" / "_media" / "logo.svg").exists()


def test_a_web_page_is_read_once_and_its_logo_kept_locally(tmp_path, monkeypatch, web):
    p = project(tmp_path, {"from": URL})
    t = p.load().theme._brand
    assert web == [URL, URL + "site.css", URL + "logo.svg"]
    assert t["colors"]["accent"] == "#0b6e4f" and t["fonts"]["display"] == "Fraunces" and t["radius"] == "10px"
    assert t["logo"].startswith(".build/brand/logo-") and (tmp_path / t["logo"]).exists()
    p.load()
    assert len(web) == 3                                                     # cached: no second request


def test_a_logo_image_gives_the_brand_colours(tmp_path, monkeypatch):
    no_network(monkeypatch)
    from PIL import Image
    p = project(tmp_path, {"from": "brand/logo.svg"})
    t = p.load().theme._brand
    assert {t["colors"]["accent"], t["colors"]["accent2"]} == {"#0b6e4f", "#f2a541"} and t["logo"] == "brand/logo.svg"
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    im.paste((200, 30, 60, 255), (0, 0, 40, 26))
    im.paste((20, 90, 200, 255), (0, 26, 40, 40))
    im.save(tmp_path / "brand" / "mark.png")
    colors = brand.logo_colors(tmp_path / "brand" / "mark.png")
    assert colors["accent"].startswith("#") and "accent2" in colors
    t = themes.resolve(Theme.model_validate({"from": {"colors": colors}}))
    assert themes.contrast(themes._rgb(t["colors"]["ink"]), themes._rgb(t["colors"]["bg"])) >= 7


def test_a_brand_yaml_is_read_and_checked(tmp_path, monkeypatch):
    no_network(monkeypatch)
    p = project(tmp_path, {"from": "brand/brand.yaml", "style": "particles"})
    t = themes.resolve(p.load().theme)
    assert t["mode"] == "dark" and t["colors"]["bg"] == "#101418" and t["fonts"]["display"] == "Sora" and t["radius"] == "2px"
    (tmp_path / "brand" / "brand.yaml").write_text("colors: { accent: 'red;}</style>' }\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hex"):
        p.load()


def test_studio_brand_from_writes_editable_tokens(tmp_path, monkeypatch, web):
    from typer.testing import CliRunner

    from engine import cli
    p = project(tmp_path, {"style": "bauhaus"})
    monkeypatch.setattr(cli, "resolve", lambda name: tmp_path)
    r = CliRunner().invoke(cli.app, ["brand", "fernwick", "--from", URL])
    assert r.exit_code == 0, r.output
    assert "written to theme.from" in r.output
    written = yaml.safe_load((tmp_path / "site.yaml").read_text(encoding="utf-8"))["theme"]["from"]
    assert set(written["colors"]) == {"bg", "bg2", "ink", "accent", "accent2", "accent_ink"} and written["mode"] == "light"
    assert written["source"] == URL and written["fonts"]["display"] == "Fraunces"
    no_network(monkeypatch)                                       # the spec now carries the brand: no reading needed
    site = p.load()
    t = themes.resolve(site.theme)
    assert t["fonts"]["display"] == "Fraunces" and t["skin"]["colors"]["#be1e2d"] == t["colors"]["accent"]
    assert "#be1e2d" not in themes.style_css("bauhaus", t)       # the style's own red is the brand's accent now
    assert CliRunner().invoke(cli.app, ["brand", "fernwick"]).exit_code != 0       # --logo or --from


def test_theme_from_is_checked_and_needs_the_project(tmp_path):
    for bad in ("javascript:alert(1)", "brand/notes.txt", {"colors": {"accent": "red"}}, {"colors": {"glow": "#ffffff"}},
                {"fonts": {"script": "Inter"}}, {"fonts": {"display": "x;}"}}, {"radius": "1px;}"}):
        with pytest.raises(ValueError):
            Theme.model_validate({"from": bad})
    with pytest.raises(ValueError, match="project is loaded"):
        themes.resolve(Theme.model_validate({"from": "brand/page.html"}))
    with pytest.raises(BuildError, match="not found"):
        brand.brand_from(Project(tmp_path), "brand/missing.yaml")
    assert Site.model_validate({"name": "x", "theme": {"from": {"colors": {"accent": "#123456"}}}, "sections": []})
