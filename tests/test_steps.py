"""One caption template for every layout, and any block as a step (issue #14, docs/design/1.5-make-it-yours.md §3)."""
from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from engine.compile.layout_snapshot import page_html
from engine.spec import STEP_BLOCKS, Site, StatsBlock, Step

BTN = {"label": "Go", "href": "#go"}
FULL = {"kicker": "Kick", "title": "Title", "body": "Body words", "fact": "Fact line", "hint": "Hint line",
        "button": BTN, "surface": "light"}


def page(layout: str, steps: list[dict]) -> str:
    return page_html(Site.model_validate({"name": "t", "sections": [
        {"id": "s", "type": "type", "text": "x", "layout": layout, "steps": steps}]}))


def scene_part(html: str) -> str:
    """The scene's markup, up to its layout data (blocks shown as steps are sections inside it)."""
    a = html.index('<section class="ss-scene')
    return html[a:html.index("</script>", html.index('class="ss-layout"', a))]


# ---------------------------------------------------------------- one caption

@pytest.mark.parametrize("layout", ["overlay", "split", "cards"])
def test_every_layout_renders_every_caption_field(layout):
    html = scene_part(page(layout, [FULL]))
    for cls, words in (("ss-body", "Body words"), ("ss-fact", "Fact line"), ("ss-hint", "Hint line")):
        assert re.search(rf'class="{cls}">{words}<', html), f"{layout}: {cls} missing"
    assert 'class="ss-btn ss-btn--hot" href="#go">Go' in html
    assert "ss-surface-light" in html
    assert ("ss-eyebrow" in html) == (layout == "overlay") and ("ss-num" in html) == (layout != "overlay")


def test_the_caption_keeps_its_order_kicker_title_body_fact_button_hint():
    html = scene_part(page("cards", [FULL]))
    order = [html.index(s) for s in ("Kick", "Title", "Body words", "Fact line", ">Go", "Hint line")]
    assert order == sorted(order)


# ---------------------------------------------------------------- any block as a step

STATS = {"block": "stats", "items": [{"value": "12", "label": "Twelve"}, {"value": "3", "unit": "%", "label": "Three"}]}
QUOTE = {"block": "quote", "text": "A quoted line.", "who": "Someone"}


def test_a_step_is_a_caption_unless_it_names_a_block():
    st = Step(title="t")
    assert st.block == "caption" and st.content is None
    assert "block" not in st.model_dump(mode="json")        # an old step dumps (and is embedded in the page) as it did
    stats = Step.model_validate({**STATS, "at": "right", "show": [0.2, 0.4]})
    assert isinstance(stats.content, StatsBlock) and stats.content.items[1].unit == "%"
    assert stats.title == "" and stats.label == "(stats)"
    cta = Step.model_validate({"block": "cta", "kicker": "Last", "title": "Go", "button": BTN})
    assert (cta.kicker, cta.title, cta.content.button.label) == ("Last", "Go", "Go")   # its words reach storyboards too


def test_a_block_step_dumps_as_it_is_written_and_reads_back():
    st = Step.model_validate({**QUOTE, "at": {"x": 0.55, "y": 0.2, "w": 0.4}, "show": [0.5, 0.8], "enter": "fade"})
    d = st.model_dump(mode="json")
    assert d["block"] == "quote" and d["text"] == "A quoted line." and d["show"] == [0.5, 0.8]
    assert "type" not in d and "content" not in d and "fact" not in d
    assert Step.model_validate(d) == st


@pytest.mark.parametrize("bad,says", [
    ({"block": "stats", "items": [{"value": "1"}]}, "a stats step: items.0.label: Field required"),
    ({**STATS, "title": "x"}, "a stats step: title: Extra inputs are not permitted"),
    ({**QUOTE, "fact": "x"}, "a quote step: fact: Extra inputs"),
    ({**QUOTE, "transition": "cut"}, "`transition` belongs to a section of its own"),
    ({"block": "hero", "title": "x"}, "Input should be 'caption'"),
    ({"body": "no title"}, "a caption step needs a `title`"),
    ({"title": "x", "content": {}}, "Extra inputs are not permitted"),
])
def test_a_wrong_block_step_says_which_field(bad, says):
    with pytest.raises(ValidationError, match=re.escape(says)):
        Step.model_validate(bad)


def test_a_block_step_is_placed_and_timed_like_any_step():
    html = scene_part(page("overlay", [{"title": "First"}, {**STATS, "at": "top-right", "show": [0.3, 0.6], "enter": "fade"}]))
    m = re.search(r'<div class="ss-captions ss-captions--top-right"><div class="ss-caption ss-caption--block ss-caption--stats" '
                  r'data-from="0.3" data-to="0.6" data-enter="fade">\s*<section class="ss-block ss-band', html)
    assert m, html
    assert "Twelve" in html and "Three" in html
    assert '{"enter": "fade", "show": [0.3, 0.6], "step": 1}' in html          # the element engine times it
    with pytest.raises(ValidationError, match="split layout the copy keeps its column"):
        page("split", [{**QUOTE, "at": {"x": 0.1, "y": 0.1}}])


@pytest.mark.parametrize("layout", ["split", "cards"])
def test_a_block_step_is_a_card_in_split_and_cards(layout):
    html = scene_part(page(layout, [{"title": "First"}, {**QUOTE, "length": 0.8}]))
    assert re.search(r'<article class="ss-step" style="--h: 80vh"><div class="ss-card ss-card--block ss-card--quote">\s*'
                     r'<section class="ss-block"><div class="ss-wrap ss-quote ss-reveal">', html), html
    assert "A quoted line." in html and "Someone" in html


def test_every_block_a_step_can_be_renders_in_a_scene():
    steps = [{"block": "features", "items": [{"title": "Feat"}]}, STATS, {"block": "timeline", "items": [{"when": "2026", "title": "Now"}]},
             QUOTE, {"block": "cta", "title": "Ready", "button": BTN}, {"block": "gallery", "items": [{"title": "Tile", "href": "#"}]},
             {"block": "product", "title": "Prod", "buttons": [BTN]}, {"block": "faq", "items": [{"q": "Why?", "a": "Because."}]}]
    assert sorted(s["block"] for s in steps) == sorted(STEP_BLOCKS[1:])
    html = scene_part(page("overlay", [{"title": "First"}] + [{**s, "show": [0.1 * i, 0.1 * i + 0.1]} for i, s in enumerate(steps)]))
    for word in ("Feat", "Twelve", "Now", "A quoted line.", "Ready", "Tile", "Prod", "Because."):
        assert word in html, word
    assert html.count("<h1") == 0                              # a block in a step never takes the page's h1


def test_a_style_draws_a_block_step_with_its_own_markup():
    site = Site.model_validate({"name": "t", "theme": {"style": "neo-brutalism"}, "sections": [
        {"id": "s", "type": "type", "text": "x", "steps": [{"title": "First"}, {**STATS, "show": [0.3, 0.6]}]}]})
    html = scene_part(page_html(site))
    assert re.search(r'class="ss-caption ss-caption--block ss-caption--stats"[^>]*>\s*<section class="nb-sec nb-c-pink nb-stats"', html), html
    assert "ss-reveal" not in html and "Twelve" in html


def test_a_build_writes_a_block_step_s_media_as_a_block_section_s(tmp_path, monkeypatch):
    from PIL import Image

    from engine.compile import compiler, fonts
    from engine.project import Project
    (tmp_path / "inputs").mkdir()
    Image.new("RGB", (64, 40), (200, 90, 40)).save(tmp_path / "inputs" / "tile.png")
    (tmp_path / "site.yaml").write_text(
        "name: t\nsections:\n"
        "  - {id: s, type: type, text: x, steps: [{title: First},\n"
        "      {block: gallery, show: [0.2, 0.5], items: [{title: Tile, href: '#', image: inputs/tile.png}]},\n"
        "      {block: product, show: [0.5, 0.8], title: Prod, image: inputs/tile.png},\n"
        "      {block: cta, show: [0.8, 1], title: Done, background: inputs/tile.png}]}\n", encoding="utf-8")
    monkeypatch.setattr(fonts, "vendor", lambda links, dist, log=print: None)     # no network in tests
    html = compiler.build_site(Project(tmp_path), log=lambda m: None).read_text(encoding="utf-8")
    tile = re.search(r'<a class="ss-tile ss-reveal" href="#">\s*<div class="ss-tile__media"><img src="(assets/_media/tile\.png)"', html)
    prod = re.search(r'<img class="ss-product__img" src="(assets/_media/\w+\.webp)"', html)
    assert tile and prod and (tmp_path / "dist" / tile[1]).exists() and (tmp_path / "dist" / prod[1]).exists()
    assert "background-image: url('assets/_media/tile.png')" in html


def test_a_style_draws_in_a_scene_only_the_blocks_it_says_it_can(monkeypatch):
    """style.yaml `scene_blocks`: the types whose own markup works inside a scene; the rest use the default markup there."""
    from engine.compile import themes
    real = themes.styles()
    monkeypatch.setattr(themes, "styles", lambda: {**real, "bauhaus": {**real["bauhaus"], "scene_blocks": ["quote"]}})
    site = Site.model_validate({"name": "t", "theme": {"style": "bauhaus"}, "sections": [
        {"id": "s", "type": "type", "text": "x", "steps": [{"title": "First"}, {**STATS, "show": [0.3, 0.6]},
                                                           {**QUOTE, "show": [0.6, 0.9]}]}]})
    html = scene_part(page_html(site))
    assert re.search(r'ss-caption--stats"[^>]*>\s*<section class="ss-block ss-band', html)
    assert re.search(r'ss-caption--quote"[^>]*>\s*<section class="bh bh--quote', html)
