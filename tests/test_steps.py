"""One caption template for every layout, and any block as a step (issue #14, docs/design/1.5-make-it-yours.md §3)."""
from __future__ import annotations

import re

import pytest

from engine.compile.layout_snapshot import page_html
from engine.spec import Site

BTN = {"label": "Go", "href": "#go"}
FULL = {"kicker": "Kick", "title": "Title", "body": "Body words", "fact": "Fact line", "hint": "Hint line",
        "button": BTN, "surface": "light"}


def page(layout: str, steps: list[dict]) -> str:
    return page_html(Site.model_validate({"name": "t", "sections": [
        {"id": "s", "type": "type", "text": "x", "layout": layout, "steps": steps}]}))


def scene_part(html: str) -> str:
    return html[html.index('<section class="ss-scene'):html.index("</section>", html.index('<section class="ss-scene'))]


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
