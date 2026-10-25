"""The layout model (docs/design/1.5-make-it-yours.md §1-2, issue #13): `at` places a step (a named spot, a box on the
stage, a slot on the 12-column grid), `show` times it, `enter` and `exit` say how it arrives and leaves. Old fields keep
validating and compile into the same model; the layout snapshots (tests/test_layout_snapshots.py) prove the pages are
unchanged."""
from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from engine import layout
from engine.compile.layout_snapshot import page_html, parse
from engine.spec import AtBox, AtGrid, Site, Step


def scene(layout: str = "overlay", **step) -> dict:
    return {"name": "t", "sections": [{"id": "s", "type": "type", "text": "x", "layout": layout,
                                       "steps": [{"title": "One", **step}]}]}


# ---------------------------------------------------------------- the spec

def test_at_takes_a_spot_a_box_a_grid_slot_or_the_older_window():
    assert Step(title="t", at="top-right").at == "top-right"
    assert Step(title="t", at="auto").at == "auto"
    box = Step(title="t", at={"x": 0.07, "y": 0.58, "w": 0.34, "align": "right"}).at
    assert isinstance(box, AtBox) and (box.x, box.y, box.w, box.h, box.align) == (0.07, 0.58, 0.34, None, "right")
    grid = Step(title="t", at={"grid": "9 / span 4", "row": "bottom"}).at
    assert isinstance(grid, AtGrid) and grid.columns == (9, 4) and grid.row == "bottom"
    assert AtGrid(grid="1 / 7").columns == (1, 6) and AtGrid(grid=" 5 ").columns == (5, 1)
    assert Step(title="t", at=[0.2, 0.4]).at == (0.2, 0.4)          # 1.4: a window, the older way to write `show`


@pytest.mark.parametrize("at, says", [
    ("middle", "at.spot"),
    ({"x": 0.8, "y": 0.1, "w": 0.4}, "runs off the right edge"),
    ({"x": 0.1, "y": 0.8, "h": 0.3}, "runs off the bottom edge"),
    ({"x": 1.2, "y": 0}, "at.box.x"),
    ({"grid": "10 / span 4"}, "does not fit the 12 columns"),
    ({"grid": "0"}, "does not fit the 12 columns"),
    ({"grid": "left half"}, "is not a column slot"),
    ({"grid": "1 / 7", "rows": 2}, "at.grid.rows"),
    ([0.1, 0.2, 0.3], "at.window"),
])
def test_a_wrong_at_is_reported_against_the_form_it_is(at, says):
    with pytest.raises(ValidationError) as e:
        Step(title="t", at=at)
    assert says in str(e.value)


def test_show_is_a_window_inside_the_scene():
    assert Step(title="t", show=[0.3, 0.46]).show == (0.3, 0.46)
    for bad in ([0.5, 0.2], [0.2, 0.2], [-0.1, 0.4], [0.2, 1.4]):
        with pytest.raises(ValidationError, match="0 <= from < to <= 1"):
            Step(title="t", show=bad)


def test_enter_and_exit_name_a_motion():
    st = Step(title="t", enter="wipe", exit="fade")
    assert (st.enter, st.exit) == ("wipe", "fade")
    for m in ("fade", "rise", "wipe", "type-on", "scale", "none"):
        Step(title="t", enter=m, exit=m)
    with pytest.raises(ValidationError):
        Step(title="t", enter="slide")


def test_the_older_and_newer_spelling_of_one_thing_cannot_both_be_given():
    with pytest.raises(ValidationError, match="older way to write `show`"):
        Step(title="t", at=[0.1, 0.3], show=[0.1, 0.3])
    with pytest.raises(ValidationError, match="older way to write `at: top-right`"):
        Step(title="t", place="top-right", at="left")
    # type in the world sets the title in the picture; `at` still places the rest of the caption
    assert Step(title="t", place="sky", at="right").world.kind == "sky"


def test_layouts_say_what_they_can_place_and_time():
    Site.model_validate(scene("overlay", at={"grid": "9 / span 4"}, show=[0.1, 0.5], enter="wipe"))
    Site.model_validate(scene("cards", at={"x": 0.5, "y": 0.2}, enter="rise", exit="fade"))
    Site.model_validate(scene("split", at="right", enter="type-on"))
    with pytest.raises(ValidationError, match="shows while it scrolls past"):
        Site.model_validate(scene("cards", show=[0.1, 0.5]))
    with pytest.raises(ValidationError, match="split layout the copy keeps its column"):
        Site.model_validate(scene("split", at={"grid": "1 / 5"}))
    # the older window on a split or cards step was ignored in 1.4 and still validates
    Site.model_validate(scene("split", at=[0.1, 0.5]))


def test_an_old_step_dumps_exactly_as_it_did():
    """The page embeds each scene's steps (`sdata`); a spec that sets none of the new fields embeds the same keys."""
    d = Step(title="t", at=[0.1, 0.3], place="top-right").model_dump(mode="json")
    assert list(d) == ["kicker", "title", "body", "fact", "at", "length", "intro", "hint", "place", "surface", "button",
                       "image", "state"]
    d = Step(title="t", at={"grid": "9 / span 4"}, show=[0.1, 0.3], enter="wipe").model_dump(mode="json")
    assert d["at"] == {"grid": "9 / span 4", "row": "middle", "align": "left"}
    assert d["show"] == [0.1, 0.3] and d["enter"] == "wipe" and "exit" not in d
    assert Step.model_validate(d).model_dump(mode="json") == d                       # round trip


def test_the_schema_explains_every_new_field():
    props = Site.model_json_schema()["$defs"]["Step"]["properties"]
    for name in ("at", "show", "enter", "exit"):
        assert len(props[name]["description"]) > 60, name
    for model in (AtBox, AtGrid):
        for name, f in model.model_fields.items():
            assert f.description, f"{model.__name__}.{name}"


# ---------------------------------------------------------------- the old fields compile into the model (engine/layout.py)

def sec(layout_: str = "overlay", steps=(), **extra):
    raw = {"name": "t", "sections": [{"id": "s", "type": "type", "text": "x", "layout": layout_, "steps": list(steps), **extra}]}
    return Site.model_validate(raw).sections[0]


def test_a_window_is_show_or_the_older_at():
    assert layout.window(Step(title="t")) is None
    assert layout.window(Step(title="t", at=[0.1, 0.3])) == (0.1, 0.3)
    assert layout.window(Step(title="t", show=[0.2, 0.4], at="right")) == (0.2, 0.4)
    assert layout.window(Step(title="t", at="right")) is None


def test_builders_time_a_step_through_one_function_that_keeps_the_spec_s_spelling():
    old = Step(title="t")
    layout.set_window(old, 0.1, 0.3)
    assert old.at == (0.1, 0.3) and old.show is None                     # a 1.4 step: embedded exactly as 1.4 did
    placed = Step(title="t", at={"grid": "9 / span 4"})
    layout.set_window(placed, 0.1, 0.3)
    assert placed.show == (0.1, 0.3) and isinstance(placed.at, AtGrid)    # its place is kept
    layout.set_window(placed, 0.2, 0.5)
    assert placed.show == (0.2, 0.5)


def test_split_and_cards_lengths_compile_into_windows():
    steps = [Step(title="a", length=1), Step(title="b", length=3)]
    assert layout.windows_by_length(steps) == [(0.0, 0.25), (0.25, 1.0)]
    els = layout.scene_layout(sec("cards", [{"title": "a", "length": 1}, {"title": "b", "length": 3}])).elements
    assert [e.show for e in els] == [(0.0, 0.25), (0.25, 1.0)]


def test_layout_side_place_and_at_become_one_element_per_step():
    s = sec("overlay", [{"title": "a"}, {"title": "b", "place": "top-right", "at": [0.2, 0.4]}, {"title": "c", "at": "left"},
                        {"title": "d", "at": {"x": 0.1, "y": 0.6, "w": 0.3, "h": 0.2, "align": "center"}},
                        {"title": "e", "at": {"grid": "9 / span 4", "row": "top"}, "show": [0.5, 0.7], "enter": "wipe"},
                        {"title": "f", "at": "auto", "place": "sky"}], side="left")
    lay = layout.scene_layout(s)
    assert (lay.kind, lay.side) == ("overlay", "left")
    a, b, c, d, e, f = lay.elements
    assert (a.spot, a.show, a.by) == ("auto", (0, 1), None)               # 1.4: the layout's own place, the whole scene
    assert (b.spot, b.show, b.by, b.side) == ("top-right", (0.2, 0.4), "place", "right")
    assert (c.spot, c.by, c.auto) == ("left", "at", False)                 # a named left is its own spot, as `place: left` was
    assert (d.spot, d.style, d.align, d.side) == ("box", "--x: 0.1; --y: 0.6; --w: 0.3; --hh: 0.2", "center", "left")
    assert (e.spot, e.style, e.row, e.align, e.side, e.enter) == ("grid", "--col: 9 / span 4", "top", None, "right", "wipe")
    assert f.auto and f.step.world.kind == "sky"
    # the page carries the captions the layout places first, then every other in its own container (1.4's corners)
    assert [x.index for x in lay.in_order] == [0, 5, 1, 2, 3, 4]
    assert lay.runtime()["elements"][0] == {"step": 0, "show": [0, 1]}
    assert lay.runtime()["elements"][-1] == {"step": 4, "show": [0.5, 0.7], "enter": "wipe"}


def test_the_subject_takes_the_side_the_copy_leaves_free():
    inside = {"name": "t", "product": {"name": "p", "model": "m.glb"},
              "sections": [{"id": "i", "type": "inside", "steps": [{"title": "a"}, {"title": "b"}]}]}

    def side_of(**over):
        raw = {**inside, "sections": [{**inside["sections"][0], **over}]}
        return layout.subject_side(Site.model_validate(raw).sections[0])
    assert side_of() == "right"                                                       # 1.4: copy left, part right
    assert side_of(side="left") == "left"                                             # the scene's side still decides
    assert side_of(steps=[{"title": "a", "at": "right"}, {"title": "b", "at": {"grid": "8 / span 5"}}]) == "left"
    assert side_of(steps=[{"title": "a", "at": "right"}, {"title": "b", "at": "left"}]) == "right"
    assert side_of(steps=[{"title": "a", "place": "right"}]) == "right"               # a 1.4 corner keeps the 1.4 page
    assert side_of(side="right", steps=[{"title": "a", "at": "right"}]) == "right"


def test_a_journey_stop_s_side_is_its_spot():
    class Stop:
        side = "auto"
    assert layout.stop_spot(Stop()) == "left"
    assert layout.stop_spot(Stop(), {"side": "bottom"}) == "bottom"
    Stop.side = "right"
    assert layout.stop_spot(Stop()) == "right"


# ---------------------------------------------------------------- the page renders the model

def _scene_markup(spec: dict):
    html = page_html(Site.model_validate(spec))
    return html, parse(html)


def _all(node, pred):
    out = [node] if pred(node) else []
    for c in node.children:
        out += _all(c, pred)
    return out


def test_an_overlay_page_places_and_times_captions_from_the_model():
    spec = scene("overlay", at={"grid": "9 / span 4", "row": "bottom", "align": "right"}, show=[0.2, 0.6], enter="wipe",
                 exit="fade")
    spec["sections"][0]["steps"] += [{"title": "Two", "at": {"x": 0.07, "y": 0.58}}, {"title": "Three"}]
    html, tree = _scene_markup(spec)
    conts = _all(tree, lambda n: "ss-captions" in n.classes)
    assert [c.classes for c in conts] == [["ss-captions"],
                                          ["ss-captions", "ss-captions--grid", "ss-captions--row-bottom", "ss-captions--align-right"],
                                          ["ss-captions", "ss-captions--box"]]
    assert conts[1].attrs["style"] == "--col: 9 / span 4" and conts[2].attrs["style"] == "--x: 0.07; --y: 0.58; --w: 0.34"
    cap = conts[1].children[0]
    assert (cap.attrs["data-from"], cap.attrs["data-to"], cap.attrs["data-enter"], cap.attrs["data-exit"]) == ("0.2", "0.6", "wipe", "fade")
    assert "data-enter" not in conts[0].children[0].attrs                              # left to the layout: no attribute
    script = re.search(r'class="ss-layout">(.*?)</script>', html)[1]
    assert json.loads(script) == {"elements": [{"step": 2, "show": [0, 1]},
                                                       {"step": 0, "show": [0.2, 0.6], "enter": "wipe", "exit": "fade"},
                                                       {"step": 1, "show": [0, 1]}]}


def test_a_cards_page_places_a_card_and_names_its_motion():
    spec = scene("cards", at={"x": 0.55, "y": 0.2, "w": 0.35}, enter="rise")
    spec["sections"][0]["steps"] += [{"title": "Two", "at": "bottom-right", "exit": "wipe"}, {"title": "Three"}]
    _, tree = _scene_markup(spec)
    arts = _all(tree, lambda n: n.tag == "article")
    assert arts[0].classes == ["ss-step", "ss-at", "ss-at--box"] and arts[0].attrs["data-enter"] == "rise"
    assert arts[0].attrs["style"] == "--h: 120vh; --x: 0.55; --y: 0.2; --w: 0.35"
    assert arts[1].classes == ["ss-step", "ss-at", "ss-at--bottom-right"] and arts[1].attrs["data-exit"] == "wipe"
    assert arts[2].classes == ["ss-step"] and arts[2].attrs["style"] == "--h: 120vh"
