"""The layout model (docs/design/1.5-make-it-yours.md §1-2, issue #13): `at` places a step (a named spot, a box on the
stage, a slot on the 12-column grid), `show` times it, `enter` and `exit` say how it arrives and leaves. Old fields keep
validating and compile into the same model; the layout snapshots (tests/test_layout_snapshots.py) prove the pages are
unchanged."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

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
