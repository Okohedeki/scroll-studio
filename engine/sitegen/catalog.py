"""What the site writer may choose from: every section type the engine has, described from the spec models themselves.

A type is offered only when the bank has a pattern for it (engine/sitegen/bank.py), so a new scene joins the catalog as
soon as an example uses it without files.
"""
from __future__ import annotations

from typing import get_args

THREE_D = {"diorama", "scene3d", "showroom", "inside", "splat"}
NEEDS_PRODUCT = {"inside", "showroom"}     # they stage the site's declared product (a 3D model): not from a brief alone
INTERACTIVE = ("pointer", "3d", "code", "film")


def section_classes() -> dict[str, type]:
    from ..spec import Section
    union = get_args(Section)[0]
    out = {}
    for cls in get_args(union):
        literal = cls.model_fields["type"].annotation
        out[get_args(literal)[0]] = cls
    return out


def kinds_of(kind: str, cls: type) -> list[str]:
    """The interactive kinds a section type can show."""
    out = []
    if "pointer" in cls.model_fields:
        out.append("pointer")
    if kind in THREE_D:
        out.append("3d")
    if kind == "code":
        out.append("code")
    if kind == "film":
        out.append("film")
    return out


def about(cls: type) -> str:
    doc = " ".join((cls.__doc__ or "").split())
    first = doc.split(". ")[0].rstrip(".")
    return first[:220]


def entries(bank: dict[str, list[dict]]) -> list[dict]:
    """[{type, scene, about, interactive}] for every type with a pattern."""
    from ..spec import SCENE_TYPES
    out = []
    for kind, cls in section_classes().items():
        if kind not in bank or kind in NEEDS_PRODUCT:
            continue
        out.append({"type": kind, "scene": kind in SCENE_TYPES, "about": about(cls), "interactive": kinds_of(kind, cls)})
    return out


def offering(want: tuple[str, ...], entries_: list[dict]) -> dict[str, list[str]]:
    """{interactive kind: the types that can show it}, for the kinds asked for."""
    return {k: [e["type"] for e in entries_ if k in e["interactive"]] for k in want}
