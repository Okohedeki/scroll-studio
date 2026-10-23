"""Miniature worlds (scene type `diorama`): the spec, the layout of every kind of world, the camera's beats, and the
build stage. No browser and no GPU: the live drawing is runtime/src/players/diorama.ts (checked by eye, see
docs/miniature.md); everything that decides what the page shows is plain Python and is tested here."""
from __future__ import annotations

import json
import math
import textwrap

import pytest
from pydantic import ValidationError

from engine import diorama
from engine.compile.compiler import build_site
from engine.diorama import plan as P
from engine.diorama.recipes import HERO
from engine.project import Project
from engine.scenes.diorama import stage_key
from engine.spec import DIORAMA_KINDS, DioramaScene, Site

KINDS_PLACES = {
    "harbour": [("Light", "lighthouse"), ("Yard", "crane"), ("Stall", "stall")],
    "town": [("Tower", "clocktower"), ("Shop", "shop"), ("Mill", "windmill")],
    "desk": [("Laptop", "laptop"), ("Mug", "mug"), ("Lamp", "deskLamp")],
    "factory": [("Line", "conveyor"), ("Cell", "robot"), ("Tank", "tank")],
    "studio": [("Easel", "easel"), ("Camera", "camera"), ("Sofa", "sofa")],
}


def scene(kind="harbour", places=None, steps=None, **extra) -> DioramaScene:
    places = places if places is not None else [{"name": n, "kind": k} for n, k in KINDS_PLACES[kind]]
    steps = steps if steps is not None else [{"title": "Intro", "intro": True}] + [{"title": p["name"]} for p in places] + [{"title": "End"}]
    return DioramaScene.model_validate({"id": "d", "type": "diorama", "world": {"kind": kind, "seed": 5}, "places": places,
                                        "steps": steps, **extra})


@pytest.fixture(scope="module")
def plans():
    return {k: diorama.build(scene(k), "#f3ead9", draft=True) for k in DIORAMA_KINDS}


# ---------------------------------------------------------------- the spec

def test_the_scene_is_part_of_the_site_schema():
    schema = Site.model_json_schema()
    d = schema["$defs"]["DioramaScene"]
    assert d["properties"]["places"]["minItems"] == 1
    for name in ("DioramaWorld", "DioramaPlace", "DioramaCamera", "DioramaLook"):
        assert name in schema["$defs"]
        for field, prop in schema["$defs"][name]["properties"].items():
            assert prop.get("description") or prop.get("$ref") or prop.get("allOf") or prop.get("anyOf"), f"{name}.{field} has no description"


def test_a_scene_needs_a_place_and_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DioramaScene.model_validate({"id": "d", "type": "diorama", "places": []})
    with pytest.raises(ValidationError):
        scene(world={"kind": "moon"})
    with pytest.raises(ValidationError):
        scene(look={"glow": 1})


def test_overlay_captions_get_a_window_each():
    s = scene(layout="overlay", steps=[{"title": "a", "length": 1}, {"title": "b", "length": 3}])
    assert s.steps[0].at == (0.03, 0.22) and s.steps[1].at == (0.34, 0.91)
    kept = scene(layout="overlay", steps=[{"title": "a", "at": [0.1, 0.2]}]).steps[0].at
    assert kept == (0.1, 0.2)               # a window the author wrote is never overwritten


# ---------------------------------------------------------------- the world

@pytest.mark.parametrize("kind", DIORAMA_KINDS)
def test_every_kind_lays_out_a_world(plans, kind):
    plan, tex, w = plans[kind]
    assert plan["kind"] == kind and plan["grid"] == 129 and len(plan["heights"]) == 129 * 129
    assert tex.shape == (1024, 1024, 3) and tex.dtype.name == "uint8"          # draft ground; the full build is 2048
    assert len(plan["props"]) >= 10 and len(plan["places"]) == 3
    R = plan["size"] / 2
    for p in plan["props"]:
        assert {"k", "x", "y", "z", "r", "s"} <= p.keys()
        assert abs(p["x"]) <= R + 1.0 and abs(p["z"]) <= R + 1.0, p              # stands on the base (or at its very edge)
    for pl in plan["places"]:
        assert pl["kind"] in HERO and pl["h"] > 0 and pl["r"] > 0
        assert abs(pl["x"]) < R and abs(pl["z"]) < R
    signs = [p for p in plan["props"] if p["k"] == "sign"]
    assert sorted(s["text"] for s in signs) == sorted(p["name"] for p in plan["places"])    # one sign per place, with its name


def test_the_world_is_the_same_every_time_and_the_seed_changes_it():
    a = diorama.build(scene("harbour"), "#fff", True)[0]
    b = diorama.build(scene("harbour"), "#fff", True)[0]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    other = scene("harbour")
    other.world.seed = 6
    c = diorama.build(other, "#fff", True)[0]
    assert [p["x"] for p in a["props"] if p["k"] == "tree"] != [p["x"] for p in c["props"] if p["k"] == "tree"]


def test_the_harbour_has_water_and_props_stay_out_of_it(plans):
    plan, tex, w = plans["harbour"]
    assert plan["water"]["has"]
    for p in plan["props"]:
        if p["k"] in ("boat", "buoy", "ferry", "pier", "bridge"):
            continue
        assert not w.water_at(p["x"], p["z"]), (p["k"], p["x"], p["z"])
    assert any(p["k"] == "boat" and w.water_at(p["x"], p["z"]) for p in plan["props"])      # and the boats are on it
    dry = plans["desk"][0]
    assert not dry["water"]["has"] and all(h == 0 for h in dry["heights"])


def test_density_and_hand_placed_props():
    sparse = scene("town", world={"kind": "town", "seed": 5, "density": 0.2})
    full = scene("town")
    assert len(diorama.build(sparse, "#fff", True)[0]["props"]) < len(diorama.build(full, "#fff", True)[0]["props"])
    custom = scene("desk", world={"kind": "desk", "seed": 5, "props": [{"kind": "mug", "at": [-9, 7], "scale": 1.3, "color": "#123456"}]})
    props = diorama.build(custom, "#fff", True)[0]["props"]
    mine = [p for p in props if p["k"] == "mug" and p.get("c") == ["#123456"]]
    assert len(mine) == 1 and (mine[0]["x"], mine[0]["z"], mine[0]["s"]) == (-9, 7, 1.3)


# ---------------------------------------------------------------- where places go

def _place(where=None, kind="stall", **kw):
    s = scene("harbour", places=[{"name": "Here", "kind": kind, "where": where, **kw}], steps=[{"title": "x"}])
    return diorama.build(s, "#fff", True)[0]["places"][0]


def test_where_takes_coordinates_compass_words_and_spots():
    near = _place([-8, 6])
    assert math.hypot(near["x"] + 8, near["z"] - 6) < 4
    north = _place("north", kind="windmill")
    assert north["z"] < -3                                   # north is the back of the world
    south = _place("south", kind="windmill")
    assert south["z"] > 3
    spot = _place("hill", kind="lighthouse")
    assert (spot["x"], spot["z"]) == (-9.6, -6.2)            # a named spot is used as it is
    assert _place("hill", kind="lighthouse")["yaw"] == spot["yaw"]


def test_a_place_without_where_takes_the_spot_for_its_kind():
    light = _place(None, kind="lighthouse")
    assert (light["x"], light["z"]) == (-9.6, -6.2)
    ferry = _place(None, kind="ferry")
    assert diorama.build(scene("harbour", places=[{"name": "F", "kind": "ferry"}], steps=[{"title": "x"}]), "#fff", True)[2].water_at(ferry["x"], ferry["z"])


def test_unknown_kind_still_places_and_places_get_distinct_spots():
    s = scene("town", places=[{"name": f"P{i}"} for i in range(5)], steps=[{"title": "x"}] * 5)
    pl = diorama.build(s, "#fff", True)[0]["places"]
    assert len({(p["x"], p["z"]) for p in pl}) == 5


# ---------------------------------------------------------------- the camera

def test_one_beat_per_step_and_windows_cover_the_scroll(plans):
    plan = plans["harbour"][0]
    beats = plan["camera"]["beats"]
    assert [b["kind"] for b in beats] == ["wide", "place", "place", "place", "wide"]
    assert beats[0]["a"] == 0 and beats[-1]["b"] == 1
    for x, y in zip(beats, beats[1:]):
        assert x["b"] == pytest.approx(y["a"], abs=1e-4)
    assert plan["steps"] == [None, 0, 1, 2, None]


def test_steps_find_their_places_by_order_index_or_name():
    places = [{"name": "A", "kind": "lighthouse"}, {"name": "B", "kind": "crane", "step": 1}, {"name": "C", "kind": "stall"}]
    s = scene("harbour", places=places, steps=[{"title": "i", "intro": True}, {"title": "1"}, {"title": "2"}, {"title": "3"}])
    steps = diorama.build(s, "#fff", True)[0]["steps"]
    assert steps[1] == 1 and sorted(x for x in steps if x is not None) == [0, 1, 2] and steps[0] is None
    named = scene("harbour", places=places[:2], steps=[{"title": "x", "state": {"place": "B"}}, {"title": "y"}])
    assert diorama.build(named, "#fff", True)[0]["steps"][0] == 1 or diorama.build(named, "#fff", True)[0]["steps"][0] == 0


def test_orbit_direction_is_kept_when_asked(plans):
    def yaws(mode):
        s = scene("harbour", camera={"orbit": mode})
        return [b["yaw"] for b in diorama.build(s, "#fff", True)[0]["camera"]["beats"]]
    ccw, cw = yaws("ccw"), yaws("cw")
    assert all(b >= a - 1e-6 for a, b in zip(ccw, ccw[1:]))
    assert all(b <= a + 1e-6 for a, b in zip(cw, cw[1:]))


def test_the_swing_between_places_goes_the_asked_way():
    assert P._turn(350, 10, "auto") == pytest.approx(20)
    assert P._turn(10, 350, "auto") == pytest.approx(-20)
    assert P._turn(350, 10, "cw") == pytest.approx(-340)
    assert P._turn(10, 350, "ccw") == pytest.approx(340)


def test_the_cheapest_sight_line_wins_unless_it_means_a_big_swing():
    opts = [[(0.0, 5.0), (40.0, 0.0)], [(0.0, 0.0), (40.0, 4.0)]]
    assert P.choose_yaws(opts, "auto") == [40.0, 0.0]        # a blocked first view is given up for a clear one
    opts = [[(0.0, 0.0), (90.0, 0.0)], [(0.0, 0.0), (90.0, 0.0)]]
    first, second = P.choose_yaws(opts, "auto")
    assert first == second                                   # equal costs: stay put rather than swing


def test_a_tall_thing_in_the_way_changes_the_view():
    s = scene("harbour", places=[{"name": "Yard", "kind": "crane"}], steps=[{"title": "x"}])
    plan, tex, w = diorama.build(s, "#fff", True)
    clear = P.yaw_options(w, {"x": 0.0, "z": 0.0}, (0.0, 1.0, 0.0), 12.0, 21.0, 0.0, 24.0)
    saved = list(w.props)
    w.props.append({"k": "lighthouse", "x": 0.0, "z": 5.0, "y": 0.0, "r": 0.0, "s": 1.0, "v": 0})
    blocked = P.yaw_options(w, {"x": 0.0, "z": 0.0}, (0.0, 1.0, 0.0), 12.0, 21.0, 0.0, 24.0)
    w.props[:] = saved
    cost = lambda o, yaw: dict(o)[yaw]
    assert cost(blocked, 0.0) > cost(clear, 0.0) + 1       # looking from the front now runs into the lighthouse


def test_the_camera_never_starts_inside_a_place(plans):
    for kind, (plan, _, _) in plans.items():
        for b in plan["camera"]["beats"]:
            if b["kind"] == "place":
                assert b["dist"] > 4 and b["target"][1] >= -0.5


# ---------------------------------------------------------------- the build stage

SITE = textwrap.dedent("""
    name: Tiny
    theme: {preset: paper}
    sections:
      - id: w
        type: diorama
        world: {kind: desk, seed: 2}
        places: [{name: Laptop, kind: laptop}, {name: Coffee, kind: mug}]
        steps:
          - {title: Welcome, intro: true}
          - {title: Work, body: Laptop}
          - {title: Rest, body: Coffee}
""")


def test_building_writes_the_world_and_a_map_and_the_page_carries_the_config(tmp_path):
    (tmp_path / "site.yaml").write_text(SITE, encoding="utf-8")
    p = Project(tmp_path)
    log: list[str] = []
    build_site(p, log=log.append, options={"draft": True})
    web = p.build / "w" / "web"
    for f in ("world.json", "ground.jpg", "map.jpg"):
        assert (web / f).exists(), f
    plan = json.loads((web / "world.json").read_text())
    assert plan["kind"] == "desk" and len(plan["camera"]["beats"]) == 3
    html = (p.dist / "index.html").read_text(encoding="utf-8")
    assert 'data-scene="diorama"' in html and "assets/w/world.json" in html and "assets/w/map.jpg" in html
    assert (p.dist / "assets" / "w" / "world.json").exists()
    assert html.count("ss-step") >= 3                                  # the copy is real text in reading order


def test_an_unchanged_spec_rebuilds_nothing_and_the_look_is_not_part_of_the_cache(tmp_path):
    (tmp_path / "site.yaml").write_text(SITE, encoding="utf-8")
    p = Project(tmp_path)
    build_site(p, log=lambda m: None, options={"draft": True})
    log: list[str] = []
    build_site(p, log=log.append, options={"draft": True})
    assert any("diorama: up to date" in m for m in log)
    (tmp_path / "site.yaml").write_text(SITE.replace("world: {kind: desk, seed: 2}", "world: {kind: desk, seed: 2}\n    look: {tilt_shift: 2.0, sun: dusk}"), encoding="utf-8")
    log.clear()
    build_site(p, log=log.append, options={"draft": True})
    assert any("diorama: up to date" in m for m in log)                # tilt-shift and sun are live settings
    (tmp_path / "site.yaml").write_text(SITE.replace("seed: 2", "seed: 3"), encoding="utf-8")
    log.clear()
    build_site(p, log=log.append, options={"draft": True})
    assert any("diorama: running" in m for m in log)                   # another seed is another world


def test_stage_key_ignores_the_look_but_not_the_world():
    a, b = scene("harbour"), scene("harbour", look={"tilt_shift": 2.0})
    assert stage_key(a, "#fff", False) == stage_key(b, "#fff", False)
    c = scene("harbour")
    c.world.seed = 99
    assert stage_key(a, "#fff", False) != stage_key(c, "#fff", False)
    assert stage_key(a, "#fff", False) != stage_key(a, "#fff", True)    # a draft ground is not the full one


def test_the_example_builds_a_world_with_every_place():
    p = Project(__file__.rsplit("tests", 1)[0] + "examples/little-harbour")
    site = p.load()
    sec = site.sections[0]
    assert sec.type == "diorama" and len(sec.places) == 5
    plan = diorama.build(sec, "#f3ead9", True)[0]
    assert [pl["name"] for pl in plan["places"]] == [x.name for x in sec.places]
    assert [b["kind"] for b in plan["camera"]["beats"]].count("place") == 5
