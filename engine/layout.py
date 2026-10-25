"""The layout model (docs/design/1.5-make-it-yours.md §1-2): where a scene's words sit and when they show.

Every scene's copy goes through here. The spec's fields, the 1.4 ones and the new ones, compile into one normalised
form that the templates render and the runtime reads (`.ss-layout`, runtime/src/lib/elements.ts):

    scene_layout(sec) -> SceneLayout   the arrangement (layout preset and the picture's side) and every step's Element
    window(step)                       the step's window: `show`, or the older `at: [from, to]`; None when unset
    set_window(step, a, b)             the one way a scene builder times a step (inside, light, code, film beats, diorama)
    windows_by_length(steps)           each step's share of the scroll by its `length` (split/cards, the diorama)
    subject_side(sec)                  the side a scene's subject takes so the copy has the other (inside's `offset`)
    stop_spot(stop, measured)          where a journey stop's blocks sit

How the 1.4 fields map:

    layout + side          -> Arrangement(kind, side): named arrangements of the stage and the copy column
    place: <corner>        -> at: <corner>
    at: [from, to]         -> show: [from, to]
    length (split/cards)   -> show: the step's share of the scene's scroll (the runtime still measures the cards)
    InsideScene side       -> subject side; when it is not set, the copy's `at` decides (the copy keeps its side)
    JourneyStop side       -> the stop's spot (auto: measured from the picture, else left)

A step left to the layout (`at` unset or `auto`) sits where 1.4 put it, so an old spec builds the same page
(tests/test_layout_snapshots.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .spec import AtBox, AtGrid, Step

AUTO = "auto"
RIGHT_SPOTS = ("right", "top-right", "bottom-right")
LEFT_SPOTS = ("left", "top-left", "bottom-left")


# ---------------------------------------------------------------- timing

def window(step: Step) -> Optional[tuple[float, float]]:
    """When the step shows, 0-1 of its scene's progress: `show`, or the older `at: [from, to]`. None when unset."""
    if step.show is not None:
        return tuple(step.show)
    if isinstance(step.at, tuple):
        return step.at
    return None


def set_window(step: Step, a: float, b: float) -> None:
    """Time a step: the one function every builder that places copy writes windows through. A step whose `at` is free
    keeps the older spelling (`at: [a, b]`), so a page compiled from a 1.4 spec embeds the same section data; a step
    placed with `at` gets `show`."""
    if step.at is None and step.show is None:
        step.at = (a, b)
    else:
        step.show = (a, b)


def windows_by_length(steps: list[Step]) -> list[tuple[float, float]]:
    """Each step's share of the scene's scroll, in order, by its `length` (how split and cards lay steps out)."""
    total = sum(st.length for st in steps) or 1.0
    out, acc = [], 0.0
    for st in steps:
        out.append((acc / total, (acc + st.length) / total))
        acc += st.length
    return out


# ---------------------------------------------------------------- placement

@dataclass(frozen=True)
class Arrangement:
    """A layout preset: overlay (captions over a full-bleed stage), split (a pinned picture beside scrolling cards) or
    cards (a full-bleed stage with cards scrolling over it), and the side the picture takes in split and cards."""
    kind: str
    side: str


@dataclass(frozen=True)
class Element:
    """One step in the layout model."""
    index: int                          # the step's position in its scene
    step: Step
    spot: str                           # a named spot, "box" or "grid"; "auto" when the layout decides
    box: Optional[AtBox]
    grid: Optional[AtGrid]
    show: tuple                         # its window (overlay: as given, else the whole scene; split/cards: by length)
    enter: Optional[str]
    exit: Optional[str]
    by: Optional[str]                   # which field placed it: "at", "place" (1.4) or None

    @property
    def auto(self) -> bool:
        return self.spot == AUTO

    @property
    def align(self) -> Optional[str]:
        """How the words line up in a box or a grid slot (left is the default and adds nothing)."""
        a = (self.box or self.grid).align if (self.box or self.grid) else "left"
        return None if a == "left" else a

    @property
    def row(self) -> Optional[str]:
        return self.grid.row if self.grid else None

    @property
    def style(self) -> str:
        """The custom properties a box or a grid slot is laid out with (runtime/src/styles.css)."""
        if self.box:
            b = self.box
            return f"--x: {b.x}; --y: {b.y}; --w: {b.w}" + (f"; --hh: {b.h}" if b.h is not None else "")
        if self.grid:
            start, span = self.grid.columns
            return f"--col: {start} / span {span}"
        return ""

    @property
    def side(self) -> str:
        """left, right or center: which half of the stage the words are in (a box or slot by its middle)."""
        if self.box or self.grid:
            if self.box:
                mid = self.box.x + self.box.w / 2
            else:
                start, span = self.grid.columns
                mid = (start - 1 + span / 2) / 12
            return "left" if mid < 0.45 else "right" if mid > 0.55 else "center"
        if self.spot in RIGHT_SPOTS:
            return "right"
        if self.spot in LEFT_SPOTS or self.auto:
            return "left"
        return "center"

    def runtime(self) -> dict:
        """What the page's element engine needs (runtime/src/lib/elements.ts)."""
        out: dict[str, Any] = {"step": self.index, "show": list(self.show)}
        if self.enter:
            out["enter"] = self.enter
        if self.exit:
            out["exit"] = self.exit
        return out


@dataclass(frozen=True)
class SceneLayout:
    arrangement: Arrangement
    elements: list[Element]

    @property
    def kind(self) -> str:
        return self.arrangement.kind

    @property
    def side(self) -> str:
        return self.arrangement.side

    @property
    def in_order(self) -> list[Element]:
        """The elements in the order the page carries them: an overlay keeps the captions the layout places in one
        container and gives every other its own after it (as 1.4 did for corners); split and cards keep step order."""
        if self.kind != "overlay":
            return list(self.elements)
        return [e for e in self.elements if e.auto] + [e for e in self.elements if not e.auto]

    def runtime(self) -> dict:
        return {"elements": [e.runtime() for e in self.in_order]}


def _element(i: int, st: Step, shown: tuple) -> Element:
    at = None if isinstance(st.at, tuple) else st.at
    by = "at" if at is not None else ("place" if st.corner else None)
    if isinstance(at, AtBox):
        spot, box, grid = "box", at, None
    elif isinstance(at, AtGrid):
        spot, box, grid = "grid", None, at
    else:
        spot, box, grid = (at or st.corner or AUTO), None, None
    return Element(i, st, spot, box, grid, shown, st.enter, st.exit, by)


def scene_layout(sec) -> SceneLayout:
    """A scene's arrangement and every step's place and window, from whichever fields the spec uses."""
    steps = list(getattr(sec, "steps", None) or [])
    arr = Arrangement(sec.layout, sec.side)
    if arr.kind == "overlay":
        shows = [window(st) or (0, 1) for st in steps]
    else:
        shows = [tuple(round(v, 4) for v in w) for w in windows_by_length(steps)]
    return SceneLayout(arr, [_element(i, st, w) for i, (st, w) in enumerate(zip(steps, shows))])


def subject_side(sec) -> str:
    """Where a scene's subject sits (inside: the stop's part, off-centre by `offset`) so the copy has the other side.
    The scene's `side` decides when it is set, as in 1.4. Otherwise the copy does: steps placed with `at`, all on the
    right, put the subject on the left. Steps left to the layout sit on the left, so the subject is on the right."""
    if "side" in sec.model_fields_set:
        return sec.side
    placed = [e.side for e in scene_layout(sec).elements if e.by == "at"]
    return "left" if placed and all(s == "right" for s in placed) else "right"


def stop_spot(stop, measured: Optional[dict] = None) -> str:
    """Where a journey stop's blocks sit: measured from its picture once the film is built (engine/journey.py), else the
    stop's own `side`, with auto falling back to the left."""
    if measured:
        return measured["side"]
    return stop.side if stop.side != AUTO else "left"
