"""Movers on a diorama: routes, scroll movers with stops, grid traffic that never collides, the plain world and the
glide camera (engine/diorama/movers.py, engine/diorama/plan.py)."""
from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from engine.diorama import movers as mv
from engine.spec import DioramaScene, DioramaStop


def scene(**over) -> dict:
    sec = {
        "id": "floor", "type": "diorama", "layout": "cards",
        "world": {"kind": "plain", "size": 26, "props": [{"kind": "tiles", "at": [0, 0], "size": [16, 8]}]},
        "places": [{"name": "First", "kind": "printer", "where": [-6, 6], "turn": 0, "sign": ""},
                   {"name": "Second", "kind": "oven", "where": [3, 6], "turn": 0}],
        "movers": [{"id": "hero", "drive": "scroll", "hover": 0.1, "route": [[-12, 6.4], [12, 6.4]],
                    "stops": [{"place": "First", "carry": "inputs/a.png"}, {"place": "Second"}]}],
        "traffic": [{"area": [-8, -4, 8, 8], "cell": 1.0, "count": 12, "seed": 3}],
        "camera": {"travel": "glide", "yaw": 10},
        "steps": [{"title": "Whole", "intro": True}, {"title": "One"}, {"title": "Two"}, {"title": "End", "state": {"wide": True}}],
    }
    sec.update(over)
    return sec


# ---------------------------------------------------------------- routes

def test_a_route_rounds_its_corners_and_measures_its_length():
    path, total = mv.route_path([(0, 0), (4, 0), (4, 3)], radius=0.6)
    assert total < 7.0 and total > 6.5                    # shorter than the two legs (7): the corner is cut
    xs, zs = zip(*path)
    assert min(xs) == 0 and max(zs) == 3
    gaps = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    assert max(gaps) < 0.2                                 # dense enough to follow smoothly
    assert mv.route_path([(1, 2)]) == ([[1.0, 2.0]], 0.0)


def test_stops_sit_on_the_route_in_order():
    r = mv.scroll_mover([(0, 0), (10, 0)], [{"x": 2, "z": 0.3, "step": 1, "carry": "a"}, {"x": 7, "z": -0.2, "step": 2, "carry": None}])
    assert [round(s["s"], 3) for s in r["stops"]] == [2.0, 7.0]
    assert r["stops"][0]["off"] == pytest.approx(0.3)
    # a stop behind the one before it waits there instead of driving backwards
    r = mv.scroll_mover([(0, 0), (10, 0)], [{"x": 6, "z": 0, "step": 1}, {"x": 3, "z": 0, "step": 2}])
    assert r["stops"][1]["s"] == r["stops"][0]["s"]
    # no route: stop to stop
    r = mv.scroll_mover([], [{"x": 0, "z": 0, "step": 1}, {"x": 3, "z": 4, "step": 2}])
    assert r["len"] == pytest.approx(5.0)
    assert mv.path_at(r["path"], r["len"], 2.5) == pytest.approx((1.5, 2.0), abs=1e-6)


# ---------------------------------------------------------------- traffic

def test_traffic_never_shares_a_cell_and_keeps_off_what_is_blocked():
    blocked = lambda x, z: -1.6 < x < 1.6 and -1.6 < z < 1.6     # something standing in the middle of the grid
    sim = mv.simulate_traffic((-6, -4, 6, 4), 1.0, 16, 1.6, 0.25, blocked, seed=5, duration=60)
    keys = sim["keys"]
    assert len(keys) == 16
    moves = sum(len(k) // 3 for k in keys)
    assert moves > 16 * 20                                 # they really move
    for t in np.linspace(0, 60, 241):
        pts = np.array([mv.position(k, float(t)) for k in keys])
        d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1]) + np.eye(len(pts)) * 9
        assert d.min() >= 0.7, f"two movers within {d.min():.2f} at t={t:.2f}"
        for x, z in pts:
            assert not blocked(x, z)
            assert -6 <= x <= 6 and -4 <= z <= 4


def test_traffic_is_deterministic():
    a = mv.simulate_traffic((-5, -3, 5, 3), 1.0, 8, 1.4, 0.3, lambda x, z: False, seed=9, duration=20)
    b = mv.simulate_traffic((-5, -3, 5, 3), 1.0, 8, 1.4, 0.3, lambda x, z: False, seed=9, duration=20)
    assert a == b


# ---------------------------------------------------------------- the spec

def test_what_the_spec_refuses():
    with pytest.raises(ValidationError, match="not one of the places"):
        DioramaScene.model_validate(scene(movers=[{"id": "m", "stops": [{"place": "Nowhere"}]}]))
    with pytest.raises(ValidationError, match="one mover can be driven by the scroll"):
        DioramaScene.model_validate(scene(movers=[{"id": "a", "stops": [{"place": "First"}]}, {"id": "b", "stops": [{"place": "Second"}]}]))
    with pytest.raises(ValidationError, match="needs `stops`"):
        DioramaScene.model_validate(scene(movers=[{"id": "a"}]))
    with pytest.raises(ValidationError, match="route` of at least two"):
        DioramaScene.model_validate(scene(movers=[{"id": "a", "drive": "time", "route": [[0, 0]]}]))
    with pytest.raises(ValidationError, match="names a `place` or gives `at`"):
        DioramaStop.model_validate({"place": "First", "at": [0, 0]})
    with pytest.raises(ValidationError, match="needs the `step`"):
        DioramaStop.model_validate({"at": [0, 0]})
    with pytest.raises(ValidationError, match="at least two cells"):
        DioramaScene.model_validate(scene(traffic=[{"area": [0, 0, 1, 1]}]))


# ---------------------------------------------------------------- the plan

def test_the_plan_carries_the_movers_the_traffic_and_a_glide_camera():
    from engine.diorama import plan
    sec = DioramaScene.model_validate(scene())
    urls = {}
    pl, tex, w = plan.build(sec, "#eceef0", draft=True, carry_url=lambda ref: urls.setdefault(str(ref), f"u{len(urls)}") if ref else None)
    assert pl["kind"] == "plain" and pl["camera"]["travel"] == "glide"
    hero = pl["movers"][0]
    assert hero["drive"] == "scroll" and hero["carry"] is None
    assert [s["step"] for s in hero["stops"]] == [1, 2]
    assert hero["stops"][0]["carry"] == "u0" and hero["stops"][1]["carry"] is None
    # at a stop, the camera looks at the mover (on the route, at deck height), not at the middle of the place's hero
    b1 = pl["camera"]["beats"][1]
    assert b1["kind"] == "place" and b1["target"][2] == pytest.approx(6.4, abs=0.01) and b1["target"][1] < 1.0
    # wide beats look from the yaw the spec gives
    assert pl["camera"]["beats"][0]["yaw"] % 360 == pytest.approx(10)
    # no sign at a place whose sign is empty, one at the other
    signs = [p for p in pl["props"] if p["k"] == "sign"]
    assert [s["text"] for s in signs] == ["Second"]
    # the traffic stays off the hero's route and off the machines
    tr = pl["traffic"][0]
    for k in tr["keys"]:
        for i in range(0, len(k), 3):
            assert abs(k[i + 2] - 6.4) > 0.79
    tiles = next(p for p in pl["props"] if p["k"] == "tiles")
    assert tiles["size"] == [16, 8]


def test_a_world_without_movers_is_laid_out_as_before():
    from engine.diorama import plan
    sec = DioramaScene.model_validate(scene(movers=[], traffic=[]))
    pl, *_ = plan.build(sec, "#eceef0", draft=True)
    assert "movers" not in pl and "traffic" not in pl
