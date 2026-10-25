"""The landing page kit (#138): badge, button icons and the ghost, rating, signup, figures, logos and the framed card.
Old specs must build the same page (the layout snapshots and the byte-identical markup below), the new pieces render
from the spec in the theme's tokens, and the compiler turns logo files into what the strip shows. No GPU, no browser."""
from __future__ import annotations

import re

import pytest
import yaml
from PIL import Image

from engine import spec
from engine.compile.compiler import _env
from engine.compile.layout_snapshot import page_html


def site(*sections, **extra) -> spec.Site:
    return spec.Site.model_validate({"name": "Kit", "sections": list(sections), **extra})


def macros():
    return _env().get_template("blocks.html.j2").module


# ---------------------------------------------------------------- old specs dump and render as they did

def test_unset_kit_fields_stay_out_of_every_dump():
    link = spec.Link(label="Go")
    assert link.model_dump() == {"label": "Go", "href": "#"}
    step = spec.Step(title="T", button={"label": "Go"})
    d = step.model_dump(mode="json")
    assert "badge" not in d and d["button"] == {"label": "Go", "href": "#"}
    scene = spec.TypeScene.model_validate({"id": "t", "type": "type", "steps": [{"title": "T"}]})
    assert "frame" not in scene.model_dump(mode="json")
    hero = spec.HeroBlock(title="T").model_dump(mode="json")
    assert not {"rating", "signup", "stats", "logos", "frame"} & set(hero)
    assert "look" not in spec.StatsBlock(items=[{"value": "1", "label": "x"}]).model_dump()


def test_a_button_without_icon_or_look_is_the_one_drawn_before():
    m = macros()
    assert str(m.btn(spec.Link(label="Go", href="#a"), True)) == '<a class="ss-btn ss-btn--hot" href="#a">Go <span class="ss-arrow">→</span></a>'
    assert str(m.btn(spec.Link(label="More", href="#b"))) == '<a class="ss-btn" href="#b">More</a>'
    assert str(m.badge("Now open")) == '<span class="ss-badge">Now open</span>'


def test_a_hero_without_the_kit_has_no_kit_classes():
    html = page_html(site({"type": "hero", "id": "h", "title": "Hi", "badge": "Words", "buttons": [{"label": "Go"}]}))
    assert "ss-hero--kit" not in html and "ss-frame-card" not in html and "hero-frame" not in html and "ss-kit" not in html


# ---------------------------------------------------------------- the pieces

def test_button_icons_and_the_ghost():
    m = macros()
    play = str(m.btn(spec.Link(label="Watch", icon="play", look="ghost")))
    assert "ss-btn--ghost" in play and "ss-btn--hot" not in play and play.index("ss-icon--play") < play.index("Watch")
    ext = str(m.btn(spec.Link(label="Docs", href="https://example.com", icon="external"), True))
    assert 'target="_blank" rel="noopener"' in ext and "opens in a new tab" in ext and "ss-btn--hot" in ext
    none = str(m.btn(spec.Link(label="Plain", icon="none"), True))
    assert "ss-icon" not in none and "ss-arrow" not in none


def test_a_badge_as_a_link_with_a_tag_or_a_dot():
    b = spec.Badge(text="Field notes", href="#n", tag="New")
    assert str(b) == "New · Field notes"            # what a style's own markup prints
    html = str(macros().badge(b))
    assert html.startswith('<a class="ss-badge ss-badge--kit" href="#n">') and '<b class="ss-badge__tag">New</b>' in html
    dot = str(macros().badge(spec.Badge(text="Live", icon="dot")))
    assert dot.startswith("<span") and "ss-badge__dot" in dot and "ss-arrow" not in dot


def test_a_rating_fills_its_stars_to_the_score_and_reads_as_text():
    html = str(macros().rating(spec.Rating(score=4.5, text="from 300 reviews")))
    assert 'style="width: 90.0%"' in html and html.count("ss-icon--star") == 10
    assert "4.5<span class=\"ss-sr\"> out of 5</span>" in html and "from 300 reviews" in html
    assert 'aria-hidden="true"' in html                                   # the stars are decoration; the words say it
    with pytest.raises(ValueError, match="more than out_of"):
        spec.Rating(score=6)


def test_a_signup_is_a_plain_labelled_form():
    m = macros()
    mail = str(m.signup(spec.SignupForm(action="mailto:hi@example.com", button="Join")))
    assert 'method="post" enctype="text/plain"' in mail and 'type="email"' in mail and "required" in mail
    assert re.search(r'<label class="ss-signup__field"><span class="ss-sr">Email address</span><input', mail)
    post = str(m.signup(spec.SignupForm(action="https://forms.example.com/x", method="get", name="EMAIL",
                                        hidden={"list": "a1"}, placeholder=None, note="No <em>spam</em>.")))
    assert 'method="get"' in post and "enctype" not in post and 'name="EMAIL"' in post
    assert '<input type="hidden" name="list" value="a1">' in post and 'placeholder="Email address"' in post
    assert "No <em>spam</em>." in post
    with pytest.raises(ValueError, match="not an allowed link"):
        spec.SignupForm(action="javascript:alert(1)")
    with pytest.raises(ValueError):
        spec.SignupForm(action="#", hidden={"bad name": "x"})


def test_a_logo_image_must_be_a_plain_reference():
    spec.Logo(name="A", image="inputs/logos/a.svg")
    for bad in ("x.svg') ; background: red", "javascript:alert(1)", 'a"b.png'):
        with pytest.raises(ValueError):
            spec.Logo(name="A", image=bad)


def test_the_hero_kit_renders_every_piece_and_the_frame():
    s = site({"type": "hero", "id": "h", "title": "Hi", "align": "left", "frame": "card",
              "badge": {"text": "News", "href": "#n"}, "buttons": [{"label": "Go", "icon": "arrow"}],
              "rating": {"score": 4.2, "text": "from 51 shops"}, "signup": {"action": "mailto:a@example.com"},
              "stats": [{"value": "61%", "label": "kept"}, {"value": "9", "unit": "d", "label": "days"}],
              "logos": {"title": "With", "items": [{"name": "Halden"}, {"name": "Quanta", "image": "q.svg", "href": "#q"}]}},
             {"type": "type", "id": "t", "frame": "card", "steps": [{"title": "Scene", "badge": "Pill"}]})
    html = page_html(s)
    assert 'class="mode-dark layout-flow hero-frame"' in html
    assert "ss-hero ss-hero--left" in html and "ss-hero--kit ss-frame-card" in html
    for piece in ("ss-badge--kit", "ss-rating", "ss-signup", "ss-figures", "ss-hero__logos", "from 51 shops", "61%", "days"):
        assert piece in html, piece
    assert '<span class="ss-logo ss-logo--word">Halden</span>' in html
    assert "ss-logo--mono" in html and "mask-image: url('standin')" in html and 'alt="Quanta"' in html
    assert re.search(r'<section class="ss-scene ss-overlay[^"]*ss-frame-card"', html)
    assert '<span class="ss-badge">Pill</span>' in html


def test_the_logos_and_signup_blocks_and_divided_stats():
    html = page_html(site({"type": "logos", "id": "l", "title": "Partners", "tint": "original",
                           "items": [{"name": "Orbitly", "image": "o.png"}]},
                          {"type": "signup", "id": "s", "title": "Letters", "action": "https://example.com/s",
                           "rating": {"score": 5, "text": "from readers"}},
                          {"type": "stats", "id": "f", "look": "divided", "items": [{"value": "3", "label": "x"}]}))
    assert "ss-logos-block" in html and "ss-logo--own" in html and "mask-image" not in html
    assert "ss-signup-block" in html and 'action="https://example.com/s"' in html and "from readers" in html
    assert "ss-stats--divided" in html


# ---------------------------------------------------------------- logo files

def test_the_compiler_turns_logo_files_into_silhouettes_or_greys(tmp_path, monkeypatch):
    from engine.compile import compiler, fonts
    from engine.project import Project
    logos = tmp_path / "inputs"
    logos.mkdir()
    (logos / "mark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>')
    Image.new("RGBA", (400, 200), (0, 0, 0, 0)).save(logos / "clear.png")
    Image.new("RGB", (400, 200), (240, 240, 240)).save(logos / "box.jpg")
    items = [{"name": "Svg", "image": "inputs/mark.svg"}, {"name": "Clear", "image": "inputs/clear.png"},
             {"name": "Box", "image": "inputs/box.jpg"}, {"name": "Gone", "image": "inputs/missing.png"}]
    (tmp_path / "site.yaml").write_text(yaml.safe_dump({"name": "L", "sections": [
        {"type": "hero", "id": "h", "title": "Hi", "logos": {"items": items}}]}), encoding="utf-8")
    monkeypatch.setattr(fonts, "vendor", lambda links, dist, log=print: None)      # no network in tests
    notes: list[str] = []
    compiler.build_site(Project(tmp_path), log=notes.append)
    html = (tmp_path / "dist" / "index.html").read_text(encoding="utf-8")
    assert "mask-image: url('assets/_media/mark.svg')" in html and (tmp_path / "dist/assets/_media/mark.svg").exists()
    clear = re.search(r'<span class="ss-logo ss-logo--mono" style="[^"]*url\(\'(assets/_media/logo-[0-9a-f]+\.webp)\'\)', html)
    assert clear and Image.open(tmp_path / "dist" / clear.group(1)).height == 160           # resized to the strip's height
    assert re.search(r'<span class="ss-logo ss-logo--grey"><img src="assets/_media/logo-[0-9a-f]+\.webp" alt="Box"', html)
    assert '<span class="ss-logo ss-logo--word">Gone</span>' in html and any("missing.png" in n for n in notes)
