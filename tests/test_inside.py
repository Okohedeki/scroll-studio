"""The product as the set (`type: inside`): the spec, finding parts by name, automatic stops, the camera route (where it
lands, how it flies, where the copy sits on the scroll), the per-frame cache keys and the scene builder (with Blender
replaced by a writer of tiny PNGs). No Blender, GPU or browser is needed."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from engine import inside
from engine.project import BuildContext, BuildError, Project
from engine.scenes import inside as scene
from engine.spec import InsideScene, InsideStop, Site, Step


def part(i, name, centre, size, tris=500, path=None, mesh=None, explode=(0, 0, 0)):
    return {"index": i, "name": name, "mesh": mesh or name + "_m", "path": path or f"Speaker/{name}", "triangles": tris,
            "materials": [], "size": list(size), "centre": list(centre), "explode": list(explode), "anchor": False}


def speaker() -> dict:
    """A speaker, in metres, z up: a cabinet shell around a driver (cone, surround, dust cap, magnet, voice coil), a
    port tube and a binding post, plus a grille of eight identical pins."""
    parts = [
        part(0, "Cabinet", (0, 0, 0.14), (0.20, 0.24, 0.28), 20000, "Speaker/Housing/Cabinet"),
        part(1, "Cone", (0, -0.10, 0.18), (0.14, 0.03, 0.14), 4000, "Speaker/Driver/Cone", explode=(0, -0.05, 0)),
        part(2, "Surround", (0, -0.10, 0.18), (0.16, 0.01, 0.16), 3000, "Speaker/Driver/Surround"),
        part(3, "DustCap", (0, -0.115, 0.18), (0.04, 0.02, 0.04), 800, "Speaker/Driver/DustCap"),
        part(4, "Magnet", (0, -0.05, 0.18), (0.10, 0.04, 0.10), 2500, "Speaker/Driver/Magnet", explode=(0, 0.05, 0)),
        part(5, "VoiceCoil", (0, -0.08, 0.18), (0.03, 0.03, 0.03), 900, "Speaker/Driver/VoiceCoil"),
        part(6, "PortTube", (0, 0.11, 0.06), (0.05, 0.10, 0.05), 1200, "Speaker/Housing/PortTube"),
        part(7, "BindingPost", (0.05, 0.12, 0.25), (0.02, 0.02, 0.02), 600, "Speaker/Terminals/BindingPost"),
    ]
    for k in range(8):
        parts.append(part(8 + k, f"GrillePin.{k:03d}" if k else "GrillePin", (-0.08 + 0.023 * k, -0.125, 0.03),
                          (0.004, 0.004, 0.02), 100, "Speaker/Grille/GrillePin"))
    return {"size": [0.2, 0.24, 0.28], "height": 0.28, "units": "m", "triangles": 40000, "parts": parts}


def scene_of(**kw) -> InsideScene:
    return InsideScene.model_validate({"id": "in", "type": "inside", **kw})


# ---------------------------------------------------------------- the spec

def test_a_stop_names_a_part_or_a_point_not_both_or_neither():
    scene_of(stops=[{"part": "Cone"}, {"point": [0.5, 0.5, 0.5]}])
    with pytest.raises(ValidationError, match="exactly one of"):
        scene_of(stops=[{"part": "Cone", "point": [0.5, 0.5, 0.5]}])
    with pytest.raises(ValidationError, match="exactly one of"):
        scene_of(stops=[{}])


def test_the_defaults_are_a_macro_flight_and_the_scene_is_part_of_the_site():
    s = scene_of()
    assert s.stops is None and s.establish and s.outro == "wide" and s.cutaway and s.layout == "overlay" and s.length == 0
    assert s.lens == 60 and s.fstop == 11 and s.density == 18
    with pytest.raises(ValidationError):
        scene_of(layout="cards")
    site = Site.model_validate({"name": "T", "sections": [{"type": "inside", "id": "a", "stops": [{"part": "x*"}]}]})
    assert site.sections[0].type == "inside"
    from engine.spec import is_scene
    assert is_scene(site.sections[0])


def test_every_field_is_described_for_the_ui_and_the_mcp_schema():
    schema = InsideScene.model_json_schema()
    from engine.spec import SceneBase
    own = (set(InsideScene.model_fields) - set(SceneBase.model_fields)) | {"layout", "length"}
    missing = [k for k in own if k != "type" and not schema["properties"][k].get("description")]
    assert not missing, missing
    stop = InsideStop.model_json_schema()
    assert all(v.get("description") for v in stop["properties"].values())


# ---------------------------------------------------------------- finding parts

def test_a_glob_finds_parts_by_name_and_assemblies_by_path_case_insensitively():
    parts = inside.parts_of(speaker())
    assert [p.name for p in inside.find(parts, "cone")] == ["Cone"]
    assert {p.name for p in inside.find(parts, "Driver/*")} == {"Cone", "Surround", "DustCap", "Magnet", "VoiceCoil"}
    assert {p.name for p in inside.find(parts, "*magnet*")} == {"Magnet"}
    assert len(inside.find(parts, "grillepin*")) == 8


def test_a_name_match_wins_over_the_mesh_names_of_neighbours():
    parts = inside.parts_of(speaker())
    parts[1].mesh = "DustCap"             # a mesh named like another part (importers do this) must not drag it in
    assert [p.name for p in inside.find(parts, "DustCap")] == ["DustCap"]


def test_a_stop_that_matches_nothing_says_what_the_model_has():
    parts = inside.parts_of(speaker())
    with pytest.raises(BuildError) as e:
        inside.find(parts, "Cones", "inside 'in' stop 2")
    msg = str(e.value)
    assert "stop 2" in msg and "no part matches 'Cones'" in msg and "Cone" in msg and "--parts" in msg


# ---------------------------------------------------------------- stops

def test_a_model_without_parts_gets_a_clear_error_for_automatic_stops_and_still_takes_points():
    one = {"size": [0.1, 0.1, 0.1], "parts": [part(0, "Body", (0, 0, 0.05), (0.1, 0.1, 0.1), 1000)]}
    with pytest.raises(BuildError) as e:
        inside.resolve(scene_of(), one)
    assert "single mesh" in str(e.value) and "point" in str(e.value)
    res = inside.resolve(scene_of(stops=[{"point": [0.5, 0.2, 0.9]}, {"point": [0.2, 0.8, 0.3]}]), one)
    assert len(res.stops) == 2 and res.stops[0].parts == []
    assert res.stops[0].aim == pytest.approx([0.0, -0.03, 0.09], abs=0.01) or res.stops[0].aim[2] > 0.08
    with pytest.raises(BuildError, match="no parts"):
        inside.resolve(scene_of(), {"size": [1, 1, 1], "parts": []})


def test_automatic_stops_are_the_distinct_parts_in_a_tour_and_repeated_parts_are_one_stop():
    parts = inside.parts_of(speaker())
    stops = inside.auto_stops(parts, 4)
    assert len(stops) == 4 and len({s.part for s in stops}) == 4
    assert all(s.label for s in stops)
    grille = inside.auto_stops(parts, 8)
    assert sum(1 for s in grille if s.part.lower().startswith("grillepin")) <= 1     # eight pins: one place
    centres = [np.mean([p.centre for p in inside.find(parts, s.part)], axis=0) for s in stops]
    assert centres[0][0] <= min(c[0] for c in centres) + 1e-9               # the tour starts at the left
    n = len([1 for _ in inside.auto_stops(parts, 99)])
    assert n <= len({inside._stem(p.name) for p in parts})


def test_a_scene_without_stops_makes_as_many_as_it_has_copy_for():
    s = scene_of(steps=[Step(title="a", intro=True), Step(title="b"), Step(title="c"), Step(title="d")])
    res = inside.resolve(s, speaker())
    assert len(res.stops) == 3 and res.notes and "no stops" in res.notes[0]
    assert len(inside.resolve(scene_of(), speaker()).stops) == 5


def test_a_stop_is_framed_by_its_span_and_lens():
    s = scene_of(stops=[{"part": "Magnet", "span": 40, "lens": 60, "yaw": 20, "pitch": 25}])
    r = inside.resolve(s, speaker()).stops[0]
    assert r.span == pytest.approx(0.040) and r.lens == 60 and r.yaw == 20 and r.pitch == 25
    # the width of the view at the focal plane is the span: 36 mm sensor, 60 mm lens
    d = float(np.linalg.norm(r.cam - r.aim))
    assert d >= 0.040 * 60 / 36 - 1e-9
    longer = inside.resolve(scene_of(stops=[{"part": "Magnet", "span": 40, "lens": 120, "yaw": 20, "pitch": 25}]), speaker()).stops[0]
    assert float(np.linalg.norm(longer.cam - longer.aim)) > d * 1.5              # same view, longer lens: further away


def test_explode_moves_where_the_stop_looks():
    flat = inside.resolve(scene_of(stops=[{"part": "Magnet"}]), speaker()).stops[0]
    open_ = inside.resolve(scene_of(stops=[{"part": "Magnet", "explode": 1.0}]), speaker()).stops[0]
    assert open_.aim[1] == pytest.approx(flat.aim[1] + 0.05) and open_.explode == 1.0


def test_the_camera_comes_in_from_a_side_close_to_the_previous_one_unless_told():
    s = scene_of(stops=[{"part": "Cone", "yaw": 40}, {"part": "Magnet"}, {"part": "PortTube", "yaw": -120, "pitch": 10}])
    r = inside.resolve(s, speaker()).stops
    assert r[0].yaw == 40
    assert abs(inside._wrap(r[1].yaw - 40)) <= 90 and 10 <= r[1].pitch <= 70
    assert r[2].yaw == -120 and r[2].pitch == 10


# ---------------------------------------------------------------- the route

def route(**kw):
    s = scene_of(**{"stops": [{"part": "Cone", "yaw": -20, "pitch": 20}, {"part": "Magnet", "yaw": 30, "pitch": 25},
                              {"part": "PortTube", "yaw": 150, "pitch": 15}], "density": 10, **kw})
    res = inside.resolve(s, speaker())
    return s, res, inside.make_plan(s, res)


def test_the_route_opens_wide_dives_to_each_stop_rests_there_and_pulls_back():
    s, res, plan = route()
    fr = plan.frames
    assert len(fr) == round(plan.screens * 10) and fr[0]["p"] == 0 and fr[-1]["p"] == 1
    assert fr[0]["stop"] == -1 and fr[0]["lens"] == inside.WIDE_LENS and fr[-1]["lens"] == inside.WIDE_LENS
    for w, r in zip(plan.windows, res.stops):
        k = w["frame"]
        assert fr[k]["rest"] and fr[k]["stop"] == r.index
        cam, tgt = np.array(fr[k]["cam"]), np.array(fr[k]["target"])
        assert np.linalg.norm(tgt - r.aim) < 1e-3                                   # looking at the stop's aim point
        assert np.linalg.norm(cam - r.cam) < 0.06 * r.distance + 1e-6               # the small creep, nothing more
        assert fr[k]["lens"] == r.lens
    assert [w["arrive"] for w in plan.windows] == sorted(w["arrive"] for w in plan.windows)
    for a, b in zip(plan.windows, plan.windows[1:]):
        assert a["leave"] < b["arrive"] and a["copy"][1] < b["copy"][0] + 1e-9       # copy windows never overlap


def test_the_camera_lands_softly_slow_at_each_stop_fast_between():
    s, res, plan = route(density=30)
    pos = np.array([f["cam"] for f in plan.frames])
    speed = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    for w in plan.windows:
        i = int(round(w["arrive"] * (len(plan.frames) - 1)))
        assert speed[max(i - 2, 0):i + 1].max() < 0.25 * speed.max()                 # decelerated into the stop
    assert speed.max() > 5 * speed[plan.windows[0]["frame"]]


def test_the_route_flies_out_over_the_surfaces_between_stops():
    s, res, plan = route(density=30)
    a, b = res.stops[0], res.stops[1]
    seg = next(g for g in plan.segments if g.kind == "travel" and g.stop == 1)
    n = len(plan.frames)
    ks = [i for i, f in enumerate(plan.frames) if seg.t0 / plan.screens * (n - 1) <= i <= seg.t1 / plan.screens * (n - 1)]
    mid = np.array(plan.frames[ks[len(ks) // 2]]["cam"])
    chord = (np.array(a.cam) + np.array(b.cam)) / 2
    assert np.linalg.norm(mid - chord) > 0.05 * np.linalg.norm(np.array(b.cam) - np.array(a.cam))   # bowed, not a straight line


def test_a_route_without_the_wide_shots_starts_and_ends_at_the_stops():
    s, res, plan = route(establish=False, outro="stay")
    assert plan.frames[0]["stop"] == 0 and plan.frames[-1]["stop"] == 2
    assert plan.intro_window is None and plan.outro_window is None
    assert plan.frames[0]["lens"] == res.stops[0].lens


def test_scroll_length_is_the_sum_of_the_holds_and_flights():
    s, res, plan = route()
    st = res.stops
    expect = 0.7 + sum(r.travel + r.hold for r in st) + 1.3 + 0.6
    assert plan.screens == pytest.approx(expect)
    short = scene_of(stops=[{"part": "Cone", "hold": 0.4, "travel": 0.8}, {"part": "Magnet", "hold": 0.4, "travel": 0.8}], density=10)
    p2 = inside.make_plan(short, inside.resolve(short, speaker()))
    assert p2.screens == pytest.approx(0.7 + 2 * 1.2 + 1.9)


# ---------------------------------------------------------------- the copy

def test_steps_without_an_at_are_placed_intro_then_stops_then_closing():
    steps = [Step(title="open", intro=True), Step(title="one"), Step(title="two"), Step(title="three"), Step(title="close")]
    s, res, plan = route(steps=steps)
    placed = inside.schedule_steps(s.steps, plan, s.outro)
    assert len(placed) == 5 and all(st.at is not None for st in s.steps)
    spans = [st.at for st in s.steps]
    assert spans[0][0] == 0 and spans[-1][1] == 1
    assert all(a[1] <= b[0] + 1e-9 for a, b in zip(spans, spans[1:]))                # one caption at a time
    for st, w in zip(s.steps[1:4], plan.windows):
        assert st.at[0] <= w["arrive"] and st.at[1] >= w["leave"]                    # each is on screen while its stop rests
    assert spans[0][1] < plan.windows[0]["arrive"] and spans[4][0] > plan.windows[-1]["leave"]


def test_an_at_the_author_set_is_kept_and_fewer_steps_than_stops_leave_silent_stops():
    steps = [Step(title="one", at=(0.1, 0.2)), Step(title="two")]
    s, res, plan = route(steps=steps)
    inside.schedule_steps(s.steps, plan, s.outro)
    assert s.steps[0].at == (0.1, 0.2) and s.steps[1].at is not None and s.steps[1].at[0] >= plan.windows[1]["copy"][0] - 1e-6


def test_extra_steps_end_on_the_last_stop_when_the_route_stays():
    steps = [Step(title="one"), Step(title="two"), Step(title="three"), Step(title="four")]
    s, res, plan = route(steps=steps, outro="stay")
    inside.schedule_steps(s.steps, plan, s.outro)
    assert s.steps[3].at[1] == 1 and s.steps[3].at[0] > plan.windows[-1]["arrive"]


# ---------------------------------------------------------------- the cache

def hashes(sec, plan, size=(960, 544), samples=24):
    res = inside.resolve(sec, speaker())
    return scene.frame_hashes(plan, Path("p.glb"), size, samples, {"a": 1}, scene.job_stops(res))


def test_changing_one_stop_redraws_only_the_frames_near_it():
    s = scene_of(stops=[{"part": "Cone", "yaw": -20, "pitch": 20}, {"part": "Magnet", "yaw": 30, "pitch": 25},
                        {"part": "PortTube", "yaw": 150, "pitch": 15}, {"part": "BindingPost", "yaw": 100, "pitch": 30}], density=14)
    a = inside.make_plan(s, inside.resolve(s, speaker()))
    s2 = scene_of(stops=[{"part": "Cone", "yaw": -20, "pitch": 20}, {"part": "Magnet", "yaw": 30, "pitch": 25},
                         {"part": "PortTube", "yaw": 150, "pitch": 15}, {"part": "BindingPost", "yaw": 100, "pitch": 30, "lens": 100}], density=14)
    b = inside.make_plan(s2, inside.resolve(s2, speaker()))
    ha, hb = hashes(s, a), hashes(s2, b)
    changed = [k for k in range(len(ha)) if ha[k] != hb[k]]
    assert changed and len(changed) < 0.6 * len(ha)
    assert min(changed) > 0.45 * len(ha)                                               # the early frames kept their renders


def test_samples_and_size_are_part_of_every_frames_key_and_copy_is_not():
    s = scene_of(stops=[{"part": "Cone"}, {"part": "Magnet"}], density=8)
    plan = inside.make_plan(s, inside.resolve(s, speaker()))
    base = hashes(s, plan)
    assert hashes(s, plan, samples=48)[0] != base[0] and hashes(s, plan, size=(1920, 1088))[0] != base[0]
    s2 = scene_of(stops=[{"part": "Cone"}, {"part": "Magnet"}], density=8, steps=[Step(title="x")], vignette=0.6)
    assert hashes(s2, inside.make_plan(s2, inside.resolve(s2, speaker()))) == base      # copy and grade do not redraw


def test_light_keys_ease_along_the_flight_and_leave_unset_values_to_the_scene():
    s = scene_of(stops=[{"part": "Cone"}, {"part": "Magnet"}], density=10, exposure=0.5, rim=2.0,
                 light=[{"at": 0.2, "exposure": 0.5, "lamp_color": "#ffffff"}, {"at": 0.8, "exposure": -2.5, "lamp_color": "#ff0000"}])
    assert inside.light_at(s, 0.0) == {"exposure": 0.5, "ambient": 0.25, "lamp": 1.0, "rim": 2.0, "lamp_color": "#ffffff"}
    assert inside.light_at(s, 1.0)["exposure"] == -2.5 and inside.light_at(s, 1.0)["lamp_color"] == "#ff0000"
    mid = inside.light_at(s, 0.5)
    assert mid["exposure"] == pytest.approx(-1.0, abs=1e-3) and mid["rim"] == 2.0
    ex = [inside.light_at(s, p / 50)["exposure"] for p in range(51)]
    assert all(b <= a + 1e-9 for a, b in zip(ex, ex[1:]))                                # eased, never back up
    plan = inside.make_plan(s, inside.resolve(s, speaker()))
    assert plan.frames[0]["light"]["exposure"] == 0.5 and plan.frames[-1]["light"]["exposure"] == -2.5


def test_light_keys_must_go_forward_and_take_a_hex_colour():
    with pytest.raises(ValidationError):
        scene_of(light=[{"at": 0.6, "lamp": 1}, {"at": 0.2, "lamp": 2}])
    with pytest.raises(ValidationError):
        scene_of(light=[{"at": 0.5, "lamp_color": "warm"}])


def test_a_flight_without_light_keys_keeps_its_frame_keys_and_light_redraws_them():
    s = scene_of(stops=[{"part": "Cone"}, {"part": "Magnet"}], density=8)
    plan = inside.make_plan(s, inside.resolve(s, speaker()))
    assert "light" not in plan.frames[0]                                                 # old caches stay valid
    s2 = scene_of(stops=[{"part": "Cone"}, {"part": "Magnet"}], density=8, light=[{"at": 1, "exposure": -2}])
    lit = hashes(s2, inside.make_plan(s2, inside.resolve(s2, speaker())))
    assert lit[-1] != hashes(s, plan)[-1]


# ---------------------------------------------------------------- the builder (Blender replaced)

@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "p"
    (root / "inputs").mkdir(parents=True)
    spec = {"name": "T", "product": {"name": "Speaker", "model": "inputs/speaker.glb"},
            "sections": [{"type": "inside", "id": "in", "size": [320, 192], "density": 4, "samples": 8,
                          "stops": [{"part": "Cone"}, {"part": "Magnet"}],
                          "steps": [{"title": "Open", "intro": True}, {"title": "Cone"}, {"title": "Magnet"}]}]}
    (root / "site.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    proj = Project(root)
    from engine import product as prod
    glb = root / "speaker.glb"
    glb.write_bytes(b"glb")
    monkeypatch.setattr(prod, "product_info", lambda project, p=None, log=print: speaker())
    monkeypatch.setattr(prod, "normalised_glb", lambda project, p=None, log=print: glb)
    return proj


def test_the_builder_renders_once_encodes_both_sets_and_describes_the_stops(project, monkeypatch):
    calls = []

    def fake(project_, sec, glb, res, plan, hashes, indices, frames_dir, size, samples, lk, log=print, progress=lambda f, m="": None):
        todo = [k for k in indices if not (frames_dir / f"{hashes[k]}.png").exists()]
        calls.append(len(todo))
        frames_dir.mkdir(parents=True, exist_ok=True)
        for k in todo:
            Image.new("RGB", size, (k * 7 % 255, 40, 60)).save(frames_dir / f"{hashes[k]}.png")
    monkeypatch.setattr(scene, "render_frames", fake)
    sec = project.load().sections[0]
    ctx = BuildContext(project, "in", log=lambda m: None)
    theme = {"colors": {"bg": "#050608"}}
    cfg = scene.build(sec, ctx, theme)
    n = cfg["count"]
    assert n > 8 and calls == [n]
    assert len(list((ctx.web / "d").glob("*.webp"))) == n and len(list((ctx.web / "m").glob("*.webp"))) == n
    assert Image.open(ctx.web / "m" / "0001.webp").width == 960 or Image.open(ctx.web / "m" / "0001.webp").width <= 960
    assert cfg["fit"] == "cover" and cfg["background"] == "#050608"
    assert [s["label"] for s in cfg["stops"]] == ["Cone", "Magnet"]
    for st in cfg["stops"]:
        assert 0 <= st["frame"] < n and st["at"][0] < st["at"][1] and (ctx.web / Path(st["still"]).name).exists()
    # the copy was placed, the scroll length followed the route, and both are in the config for a partial rebuild
    assert all(st.at is not None for st in sec.steps) and sec.length > 3
    assert cfg["stepsAt"] == [list(st.at) for st in sec.steps] and cfg["scrollLength"] == sec.length
    # a second build rebuilds nothing
    ctx2 = BuildContext(project, "in", log=lambda m: None)
    project.load().sections[0]
    scene.build(project.load().sections[0], ctx2, theme)
    assert calls == [n]


def test_a_missing_product_or_stop_part_fails_with_advice(project, monkeypatch):
    sec = project.load().sections[0]
    sec.stops[1].part = "Magnets"
    ctx = BuildContext(project, "in", log=lambda m: None)
    with pytest.raises(BuildError, match="no part matches 'Magnets'"):
        scene.build(sec, ctx, {"colors": {"bg": "#000000"}})
    bare = Project(project.root)
    bare.spec_path.write_text(yaml.safe_dump({"name": "T", "sections": [{"type": "inside", "id": "in"}]}), encoding="utf-8")
    with pytest.raises(BuildError, match="the site has no `product:`"):
        scene.build(bare.load().sections[0], BuildContext(bare, "in", log=lambda m: None), {"colors": {"bg": "#000000"}})


def test_the_plan_estimates_the_render(project):
    from engine import plan as plan_mod
    sec = project.load().sections[0]
    unit, amount = plan_mod.units(sec, "render")
    assert unit == "inside:render" and amount > 0


# ---------------------------------------------------------------- the renderer process

FAKE = """
import sys, time, pathlib
d = pathlib.Path(sys.argv[1]); stall = sys.argv[2] == "stall"
print("DEVICE GPU", flush=True)
for n, k in enumerate([0, 1, 2], 1):
    if stall and n == 3:
        time.sleep(30)
    (d / f"h{k}.tmp.png").write_bytes(b"png")
    print(f"FRAME {n}/3 {k}", flush=True)
"""


def test_finished_frames_are_put_in_place_as_they_are_announced(tmp_path):
    import sys
    seen = []
    ok, tail = scene._run_blender([sys.executable, "-c", FAKE, str(tmp_path), "ok"], [0, 1, 2], ["h0", "h1", "h2"], tmp_path,
                                  lambda m: None, lambda f, m="": seen.append(m), 20)
    assert ok and (tmp_path / "h0.png").exists() and (tmp_path / "h2.png").exists() and not list(tmp_path.glob("*.tmp.png"))
    assert seen[-1] == "rendering frame 3/3"


def test_a_render_that_stalls_is_killed_and_keeps_the_frames_it_finished(tmp_path):
    import sys
    ok, tail = scene._run_blender([sys.executable, "-c", FAKE, str(tmp_path), "stall"], [0, 1, 2], ["h0", "h1", "h2"], tmp_path,
                                  lambda m: None, lambda f, m="": None, 2)
    assert not ok and (tmp_path / "h0.png").exists() and (tmp_path / "h1.png").exists() and not (tmp_path / "h2.png").exists()


def test_the_device_is_the_cpu_when_the_gpu_is_nearly_full_or_when_asked(monkeypatch):
    monkeypatch.delenv("STUDIO_INSIDE_DEVICE", raising=False)
    monkeypatch.setattr(scene, "gpu_free_mb", lambda: 800)
    assert scene.render_device(lambda m: None) == "cpu"
    monkeypatch.setattr(scene, "gpu_free_mb", lambda: 9000)
    assert scene.render_device(lambda m: None) == "gpu"
    monkeypatch.setattr(scene, "gpu_free_mb", lambda: None)
    assert scene.render_device(lambda m: None) == "gpu"
    monkeypatch.setenv("STUDIO_INSIDE_DEVICE", "cpu")
    assert scene.render_device(lambda m: None) == "cpu"
