"""Looking at a miniature world without scrolling it: what the layout decided, in words, and the scroll positions worth
a frame (each place at rest, the lift, the orbit and the dive between two places)."""
from __future__ import annotations

import json
from pathlib import Path

from ..spec import DioramaScene
from .plan import build


def summary(plan: dict) -> dict:
    """The decisions in a plan, readable: where each place is, which step lives at it, how far the camera swings."""
    beats = plan["camera"]["beats"]
    steps = plan["steps"]
    places = []
    for i, p in enumerate(plan["places"]):
        step = steps.index(i) if i in steps else None
        beat = beats[step] if step is not None else None
        places.append({"n": i + 1, "name": p["name"], "kind": p["kind"], "at": [p["x"], p["z"]], "step": step,
                       "camera_yaw": beat["yaw"] if beat else None, "camera_distance": beat["dist"] if beat else None})
    yaws = [b["yaw"] for b in beats]
    counts: dict[str, int] = {}
    for pr in plan["props"]:
        counts[pr["k"]] = counts.get(pr["k"], 0) + 1
    return {"world": plan["kind"], "size": plan["size"], "base": plan["base"], "props": len(plan["props"]),
            "by_kind": dict(sorted(counts.items(), key=lambda kv: -kv[1])), "places": places,
            "beats": [{"step": i, "kind": b["kind"], "from": b["a"], "to": b["b"], "yaw": b["yaw"]} for i, b in enumerate(beats)],
            "orbit_degrees": round(abs(yaws[-1] - yaws[0])) if yaws else 0}


def strip_points(plan: dict) -> list[tuple[str, float]]:
    """(label, scene progress) for a review strip: every beat at rest, and between each pair the lift, the orbit and the dive."""
    cam = plan["camera"]
    g = (1 - cam["hold"]) / 2
    out: list[tuple[str, float]] = []
    beats = cam["beats"]
    names = {i: (plan["places"][b["place"]]["name"] if b["kind"] == "place" else "wide") for i, b in enumerate(beats)}
    for i, b in enumerate(beats):
        w = b["b"] - b["a"]
        rest0, rest1 = (b["a"] + g * w, b["b"] - g * w)
        out.append((f"{i}: {names[i]}", round((rest0 + rest1) / 2, 4)))
        if i + 1 < len(beats):
            t0, t1 = rest1, beats[i + 1]["a"] + g * (beats[i + 1]["b"] - beats[i + 1]["a"])
            for tag, u in (("lift", 0.22), ("orbit", 0.5), ("dive", 0.78)):
                out.append((f"{i}-{i + 1} {tag}", round(t0 + (t1 - t0) * u, 4)))
    return out


def write_review(sec: DioramaScene, table: str, out: Path, draft: bool = True) -> dict:
    """Lay the world out and write <out>/<id>-map.jpg and <id>-plan.json; return the summary."""
    from ..scenes.diorama import _map_image
    out.mkdir(parents=True, exist_ok=True)
    plan, tex, _ = build(sec, table, draft)
    _map_image(plan, tex, table).save(out / f"{sec.id}-map.jpg", quality=88)
    (out / f"{sec.id}-plan.json").write_text(json.dumps(summary(plan), indent=1), encoding="utf-8")
    return summary(plan)
