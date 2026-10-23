"""Light as the scroll: the spec (presets, free-text times, ids, pinned steps), the schedule (where the light holds, how it
travels), the geometry lock (measuring and correcting drift on a synthetic place that is warped and relit), the maps the
browser reads (the log-encoded light-change field, the lamp map), the section's colours and the whole build with
ComfyUI replaced by a fake editor. No ComfyUI, Blender or GPU is needed."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from engine import light, light_presets
from engine.scenes import light as scene
from engine.spec import Site


def site(**over) -> Site:
    sec = {"id": "day", "type": "light", "world": {"generate": "a harbour"},
           "steps": [{"title": "a"}, {"title": "b"}, {"title": "c"}], **over}
    return Site.model_validate({"name": "x", "sections": [sec]})


# ---------------------------------------------------------------- the spec

def test_the_documented_example_validates():
    s = Site.model_validate(yaml.safe_load(textwrap.dedent('''\
        name: Quay
        sections:
          - id: day
            type: light
            world: { generate: "a harbour town, even daylight", size: [1920, 1088], seed: 3 }
            world_time: noon
            times: [dawn, morning, noon, golden-hour, blue-hour, night]
            lamps: [{ prompt: the street lamps and the lit windows }]
            steps:
              - { title: "The harbour <em>wakes first.</em>", intro: true }
              - { title: "Noon", state: { time: noon } }
        ''')))
    sec = s.sections[0]
    assert [t.id for t in sec.times] == ["dawn", "morning", "noon", "golden-hour", "blue-hour", "night"]
    assert sec.layout == "overlay" and sec.blend == "light" and sec.hold == 0.3 and sec.lamps[0].glow == 1.0


def test_bare_strings_are_presets_or_free_text_and_ids_are_unique():
    sec = site(times=["dawn", "Golden Hour", "low green storm light over the water", "dawn"]).sections[0]
    assert [t.preset for t in sec.times] == ["dawn", "golden-hour", None, "dawn"]
    assert sec.times[2].prompt.startswith("low green")
    assert [t.id for t in sec.times] == ["dawn", "golden-hour", "low-green-storm", "dawn-2"]


def test_day_is_the_usual_six():
    sec = site(times="day").sections[0]
    assert [t.id for t in sec.times] == ["dawn", "morning", "noon", "golden-hour", "blue-hour", "night"]
    assert site().sections[0].times[0].preset == "dawn"        # the default


@pytest.mark.parametrize("over", [
    {"times": ["dawn"]},                                       # a day needs two times
    {"times": ["dawn", "noon"], "world_time": "night"},        # world_time must be one of the times
    {"times": [{"id": "x", "preset": "teatime"}]},             # unknown preset
    {"times": [{"id": "x"}]},                                  # nothing to relight with
    {"times": [{"preset": "dawn", "id": "a"}, {"preset": "noon", "id": "a"}]},
    {"times": ["dawn", "noon"], "steps": [{"title": "a", "state": {"time": "midnight"}}]},   # a step pinned to nothing
])
def test_bad_specs_are_refused(over):
    with pytest.raises(ValidationError):
        site(**over)


def test_every_preset_has_the_parts_the_builder_reads():
    for name, p in light_presets.PRESETS.items():
        assert {"label", "clock", "hours", "haze", "lit", "sun", "prompt"} <= set(p), name
        assert 0 <= p["haze"] <= 1 and 0 <= p["hours"] < 24
        assert light_presets.preset(name.replace("-", " ")) is p
    ins = light_presets.instruction("golden-hour", "wet cobbles")
    assert "golden hour" in ins and ins.rstrip(".").endswith("No people") and "wet cobbles" in ins
    assert "Keep the scene identical" in ins


def test_schema_documents_the_scene():
    schema = Site.model_json_schema()
    defs = schema["$defs"]
    assert "LightScene" in defs and "LightTime" in defs
    for name in ("world", "times", "hold", "lamps", "sun", "drift", "structure", "blend"):
        assert defs["LightScene"]["properties"][name].get("description"), name


# ---------------------------------------------------------------- the schedule

def test_schedule_maps_steps_to_times_and_holds():
    sec = site(times="day", steps=[{"title": str(i)} for i in range(6)]).sections[0]
    tt, holds = scene.schedule(sec)
    assert tt == [0, 1, 2, 3, 4, 5]
    assert sec.length == pytest.approx(2.6 * 6)
    assert sec.steps[0].at[0] == 0.0 and sec.steps[-1].at[1] == 1.0
    for i, (h, st) in enumerate(zip(holds, sec.steps)):
        a, b = i / 6, (i + 1) / 6
        assert a < (h["a"] + h["b"]) / 2 < b and h["b"] - h["a"] == pytest.approx(0.3 / 6, abs=1e-3)
        # the headline is on screen over its hold (and a little either side), never over the middle of a change
        assert st.at[0] <= h["a"] and st.at[1] >= h["b"]
        if i < 5:
            nxt = sec.steps[i + 1].at[0]
            assert st.at[1] < nxt + 1e-9 and (h["b"] + holds[i + 1]["a"]) / 2 > st.at[1]


def test_schedule_with_fewer_steps_than_times_and_pins():
    sec = site(times="day", steps=[{"title": "a"}, {"title": "b"}, {"title": "c"}]).sections[0]
    assert scene.schedule(sec)[0] == [0, 2, 5]                  # spread over the day
    sec = site(times="day", steps=[{"title": "a"}, {"title": "b", "state": {"time": "night"}}, {"title": "c"}]).sections[0]
    assert scene.schedule(sec)[0] == [0, 5, 5]                  # an unpinned step keeps the last time


def test_time_at_holds_then_eases_and_is_monotonic():
    sec = site(times="day", steps=[{"title": str(i)} for i in range(6)]).sections[0]
    _, holds = scene.schedule(sec)
    assert scene.time_at(0.0, holds) == 0 and scene.time_at(1.0, holds) == 5
    h0, h1 = holds[0], holds[1]
    assert scene.time_at((h0["a"] + h0["b"]) / 2, holds) == 0            # held while the headline is read
    mid = scene.time_at((h0["b"] + h1["a"]) / 2, holds)
    assert 0.45 < mid < 0.55                                              # half-way through the change
    xs = [scene.time_at(p, holds) for p in np.linspace(0, 1, 400)]
    assert all(b >= a - 1e-9 for a, b in zip(xs, xs[1:]))


# ---------------------------------------------------------------- geometry lock: a synthetic place, warped and relit

def place(w=640, h=360, seed=1) -> np.ndarray:
    """Houses with windows under a sky, on water: structure that survives a change of light."""
    rng = np.random.default_rng(seed)
    im = np.zeros((h, w, 3), np.float32)
    im[: h // 2] = (0.55, 0.70, 0.95)
    im[h // 2:] = (0.25, 0.40, 0.55)
    for x0 in range(20, w - 60, 90):
        top = int(h * 0.18 + rng.random() * h * 0.2)
        cv2.rectangle(im, (x0, top), (x0 + 70, h // 2 + 10), (0.85, 0.78, 0.65), -1)
        cv2.rectangle(im, (x0, top), (x0 + 70, top + 12), (0.7, 0.3, 0.2), -1)
        for wx in range(x0 + 10, x0 + 60, 22):
            for wy in range(top + 24, h // 2, 30):
                cv2.rectangle(im, (wx, wy), (wx + 10, wy + 16), (0.25, 0.3, 0.38), -1)
    im += rng.normal(0, 0.01, im.shape)
    return np.clip(im * 255, 0, 255).astype(np.uint8)


def relit(rgb: np.ndarray, gain=(0.35, 0.4, 0.7), shift=(0.0, 0.0), warp=0.0) -> np.ndarray:
    """The same place under another light (a colour gain and a slope of exposure) and, optionally, moved a little."""
    h, w = rgb.shape[:2]
    f = rgb.astype(np.float32) / 255
    ramp = np.linspace(1.3, 0.7, w, dtype=np.float32)[None, :, None]
    out = np.clip(f * np.array(gain, np.float32) * ramp, 0, 1)
    if warp or shift != (0.0, 0.0):
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        gx = gx + shift[0] + warp * np.sin(gy / 37.0)
        gy = gy + shift[1] + warp * np.cos(gx / 53.0)
        out = cv2.remap(out, gx, gy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return (out * 255).astype(np.uint8)


def test_structure_ignores_the_light_and_sees_a_move():
    world = place()
    base = light.structure(world)
    dark = light.measure(world, relit(world), base)
    assert dark["drift"] < 0.6 and dark["edges"] > 0.85            # a different light is not a different place
    moved = light.measure(world, relit(world, shift=(7, 4)), base)
    assert moved["drift"] > 3.0                                     # a place that moved is
    assert moved["drift"] > 4 * dark["drift"]


def test_align_undoes_a_global_move_and_bends_nothing():
    """The editor zooms a few percent and shifts a few pixels: undone exactly, lines stay straight."""
    world = place()
    h, w = world.shape[:2]
    M = np.array([[0.97, 0.01, 9.0], [-0.004, 0.96, 7.0]], np.float32)            # the candidate's coordinates of world points
    cand = cv2.warpAffine(relit(world), M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    fixed, rep = light.align(world, cand)
    assert rep["raw"]["drift"] > 5
    assert rep["aligned"]["drift"] < 0.35 * rep["raw"]["drift"] and rep["aligned"]["edges"] > rep["raw"]["edges"]
    mv = rep["move"]
    assert mv is not None and abs(mv["scale"][0] - 0.97) < 0.01 and abs(mv["scale"][1] - 0.96) < 0.01
    assert abs(float(light.luma(fixed).mean()) - float(light.luma(cand).mean())) < 0.03       # the light survives the warp


def test_align_flow_pulls_local_drift_in_and_affine_leaves_it():
    world = place()
    cand = relit(world, shift=(6, -3), warp=3.0)
    _, aff = light.align(world, cand, mode="affine")
    fixed, flo = light.align(world, cand, mode="flow")
    _, none = light.align(world, cand, mode="none")
    assert none["aligned"]["drift"] == none["raw"]["drift"] and none["move"] is None
    assert flo["aligned"]["drift"] < 0.5 * flo["raw"]["drift"]
    assert flo["aligned"]["drift"] <= aff["aligned"]["drift"] + 1e-6
    assert fixed.shape == world.shape and fixed.dtype == np.uint8


def test_align_leaves_a_clean_relight_alone():
    world = place()
    cand = relit(world)
    fixed, rep = light.align(world, cand)
    assert rep["aligned"]["drift"] <= rep["raw"]["drift"] + 1e-6
    assert float(np.abs(fixed.astype(int) - cand.astype(int)).mean()) < 2.0


def test_pair_flow_encodes_how_neighbours_differ():
    world = place()
    a, b = relit(world), relit(world, gain=(0.9, 0.8, 0.7), shift=(-6, 3))        # b: the structure sits 6px left, 3 up
    enc, stats = light.pair_flow(a, b)
    assert enc.shape[1] == 480 and enc.shape[2] == 3 and enc.dtype == np.uint8
    conf = enc[..., 2].astype(np.float32) / 255
    dx = (enc[..., 0].astype(np.float32) / 255 - 0.5) * 2 * light.FLOW_RANGE
    # where there is structure the flow says so (px at 1024 across; the picture is 640 wide, so x1.6)
    assert stats["glide"] > 3 and float((dx * conf).sum() / conf.sum()) > 3.0
    same, st0 = light.pair_flow(a, a)
    assert st0["glide"] < 0.3


def test_relight_locked_retries_until_the_place_holds_still(tmp_path, monkeypatch):
    world = place()
    wp = tmp_path / "world.png"
    Image.fromarray(world).save(wp)
    tries = []

    def fake(world_png, instruction, seed, steps, out, tag, log=print, denoise=1.0):
        tries.append(seed)
        # the first seed drifts far, the second is clean
        # the first seed redraws the place (other houses), the second keeps it
        Image.fromarray(relit(place(seed=9) if len(tries) == 1 else world)).save(out)
        return out
    monkeypatch.setattr(light, "relight", fake)
    img, rep = light.relight_locked(world, wp, "night", [7, 1007, 2007], 8, 4.0, "affine", tmp_path, "night", lambda m: None)
    assert tries == [7, 1007] and rep["ok"] and len(rep["attempts"]) == 2
    assert rep["attempts"][0]["aligned"]["drift"] > rep["attempts"][1]["aligned"]["drift"]
    # and when no seed is good enough, the best of them is kept and reported not ok
    tries.clear()
    monkeypatch.setattr(light, "relight", lambda *a, **k: (Image.fromarray(relit(place(seed=9))).save(a[4]), a[4])[1])
    img, rep = light.relight_locked(world, wp, "night", [1, 2], 8, 0.01, "affine", tmp_path, "n2", lambda m: None)
    assert not rep["ok"] and len(rep["attempts"]) == 2


# ---------------------------------------------------------------- the maps

def test_ratio_map_carries_the_light_change_and_decodes():
    world = place()
    night = relit(world, gain=(0.25, 0.25, 0.25))          # two stops darker everywhere
    r = light.ratio_map(world, world, night)
    assert r.shape[1] == light.RATIO_W and r.dtype == np.uint8
    stops = (r.astype(np.float32) / 255 - 0.5) * light.RATIO_RANGE
    assert float(np.median(stops)) < -1.2                    # darker, in the log encoding the shader decodes
    same = light.ratio_map(world, world, world)
    assert abs(float((same.astype(np.float32) / 255 - 0.5).mean())) < 0.01   # no change, no ratio


def dots(w=640, h=360, on=True, seed=3):
    rng = np.random.default_rng(seed)
    im = np.full((h, w, 3), 30, np.uint8)
    cv2.rectangle(im, (0, 0), (w, 100), (60, 80, 120), -1)
    pts = [(int(x), int(y)) for x, y in zip(rng.integers(30, w - 30, 14), rng.integers(140, h - 20, 14))]
    if on:
        for x, y in pts:
            cv2.rectangle(im, (x, y), (x + 9, y + 13), (255, 190, 90), -1)
    return im


def test_lamp_map_finds_what_turned_on_and_gives_each_its_own_delay():
    off, on = dots(on=False), dots(on=True)
    lamp = light.lamp_map(off, on)
    assert lamp is not None and lamp["turns_on"] and lamp["count"] >= 10
    m = lamp["map"]
    assert m.shape[2] == 4 and m[..., 0].max() > 200 and m[..., 2].max() > 100            # cut-out and halo
    delays = m[..., 1][m[..., 0] > 200]
    assert len(np.unique(delays)) >= 8                                                     # windows pop at different moments
    assert lamp["color"].startswith("#") and int(lamp["color"][1:3], 16) > 150             # a warm glow
    # nothing switches: no map; and a sky mask keeps stars out
    assert light.lamp_map(off, off) is None
    sky = np.zeros((90, 160), np.float32); sky[:] = 1.0
    assert light.lamp_map(off, on, sky=sky) is None
    # turning off is the same map the other way round
    assert light.lamp_map(on, off)["turns_on"] is False


def test_lamp_map_is_confined_to_named_regions():
    off, on = dots(on=False), dots(on=True)
    allow = np.zeros((360, 640), np.float32); allow[:, :320] = 1
    lamp = light.lamp_map(off, on, allow=allow)
    xs = np.nonzero(lamp["map"][..., 0] > 128)[1]
    assert xs.size and xs.max() < 340 / 2 * 1.0 * 2 / 2 + 340                              # nothing from the right half
    assert xs.max() <= 330 * lamp["map"].shape[1] / 640


def test_tokens_are_readable_in_the_dark_and_the_light():
    from engine.compile import themes as th
    for rgb in (np.full((90, 160, 3), (12, 16, 40), np.uint8), np.full((90, 160, 3), (190, 215, 245), np.uint8)):
        t = light.tokens(rgb)
        assert th.contrast(t["ink"], t["bg"]) >= 7
        assert th.contrast(t["accent"], t["bg"]) >= th.SMALL_TEXT - 1e-6
    assert light.tokens(np.full((90, 160, 3), (12, 16, 40), np.uint8))["dark"] is True
    assert light.tokens(np.full((90, 160, 3), (190, 215, 245), np.uint8))["dark"] is False


def test_fog_colour_is_the_skys():
    world = place()
    sky = np.zeros((360, 640), np.float32); sky[:180] = 1
    f = light.fog_color(world, sky)
    assert f[2] > f[0]                                       # blue sky, bluish mist


# ---------------------------------------------------------------- the whole build, with a fake editor

def make_project(tmp_path: Path, extra: str = "") -> Path:
    root = tmp_path / "harbour"
    (root / "inputs").mkdir(parents=True)
    Image.fromarray(place(1280, 720)).save(root / "inputs" / "world.png")
    (root / "site.yaml").write_text(textwrap.dedent(f'''\
        name: Quay
        sections:
          - id: day
            type: light
            width: 1280
            world: inputs/world.png
            world_time: noon
            times: [dawn, noon, night]
            sun: false
            steps: [{{ title: One }}, {{ title: Two }}, {{ title: Three }}]
            {extra}
        '''), encoding="utf-8")
    return root


def test_build_runs_every_stage_caches_and_reports(tmp_path, monkeypatch):
    from engine.project import BuildContext, Project
    root = make_project(tmp_path)
    world = place(1280, 720)
    calls = []

    def fake(world_png, instruction, seed, steps, out, tag, log=print, denoise=1.0):
        calls.append(tag)
        night = "night" in tag
        im = relit(world, gain=(0.18, 0.2, 0.4) if night else (0.9, 0.7, 0.8), shift=(2, 1))
        if night:                      # lit windows
            for x, y in [(100, 400), (260, 420), (500, 380), (900, 430), (1100, 410)]:
                cv2.rectangle(im, (x, y), (x + 16, y + 24), (255, 200, 110), -1)
        Image.fromarray(im).save(out)
        return out
    monkeypatch.setattr(light, "relight", fake)
    monkeypatch.setattr("engine.backends.depth.estimate", lambda im, size="small": np.linspace(0, 1, im.height)[:, None].repeat(im.width, 1).astype(np.float32))
    import engine.region as regionmod
    monkeypatch.setattr(regionmod, "find", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no nodes")))
    p = Project(root)
    sec = p.load().sections[0]
    ctx = BuildContext(p, "day", log=lambda m: None)
    cfg = scene.build(sec, ctx, {})
    assert sorted(calls) == ["dawn_7", "night_33"] or len(calls) == 2          # noon is the world: not relit
    assert [t["id"] for t in cfg["times"]] == ["dawn", "noon", "night"]
    assert len(cfg["pairs"]) == 2 and cfg["pairs"][1]["lamp"] and cfg["pairs"][1]["count"] >= 3     # the windows that lit
    assert cfg["holds"] and cfg["stepTimes"] == [0, 1, 2] and cfg["layout"] == "overlay"
    assert cfg["times"][1]["drift"] == 0 and cfg["times"][2]["tokens"]["dark"] is True
    rep = json.loads((root / ".build" / "day" / "report.json").read_text())
    assert [t["id"] for t in rep["times"]] == ["dawn", "noon", "night"] and rep["times"][0]["aligned"]["drift"] < rep["times"][0]["raw"]["drift"] + 1e-6
    for rel in [cfg["depth"], cfg["sky"], cfg["poster"], cfg["times"][0]["img"], cfg["times"][0]["imgS"], cfg["pairs"][0]["ratio"], cfg["pairs"][0]["flow"], cfg["pairs"][1]["lamp"]]:
        assert (root / ".build" / "day" / "web" / Path(rel).relative_to("assets/day")).exists(), rel
    # an unchanged spec renders nothing: no relight, no stage rerun
    calls.clear()
    scene.build(p.load().sections[0], BuildContext(p, "day", log=lambda m: None), {})
    assert calls == []
    # changing one time's words re-renders that time only
    (root / "site.yaml").write_text((root / "site.yaml").read_text().replace("times: [dawn, noon, night]",
                                                                             "times: [{preset: dawn, prompt: with mist}, noon, night]"))
    scene.build(p.load().sections[0], BuildContext(p, "day", log=lambda m: None), {})
    assert [c.split("_")[0] for c in calls] == ["dawn"]


def test_the_page_builds_with_the_scene(tmp_path, monkeypatch):
    from engine.project import Project
    from engine.compile.compiler import build_site
    root = make_project(tmp_path)
    world = place(1280, 720)
    monkeypatch.setattr(light, "relight", lambda wp, ins, seed, steps, out, tag, log=print, denoise=1.0: (Image.fromarray(relit(world)).save(out), out)[1])
    monkeypatch.setattr("engine.backends.depth.estimate", lambda im, size="small": np.zeros((im.height, im.width), np.float32))
    import engine.region as regionmod
    monkeypatch.setattr(regionmod, "find", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no nodes")))
    out = build_site(Project(root), log=lambda m: None)
    html = out.read_text(encoding="utf-8")
    assert 'data-scene="light"' in html and "ss-type-light" in html
    cfg = json.loads(html.split('class="ss-config">')[1].split("</script>")[0])
    assert cfg["times"][0]["img"].startswith("assets/day/") and (root / "dist" / cfg["times"][0]["img"]).exists()
    assert 'data-from="0.0"' in html                                  # the first caption is scheduled
    assert (root / "dist" / "runtime").exists()


def test_named_lamps_are_cut_out_with_region_and_confine_the_lights(tmp_path, monkeypatch):
    """`lamps: [{prompt}]`: the lit picture is searched with engine/region.py; only lights inside the cut-out switch."""
    from engine.project import BuildContext, Project
    root = make_project(tmp_path, "lamps: [{ prompt: the windows on the left, glow: 1.5 }]")
    world = place(1280, 720)
    seen = []

    def fake(world_png, instruction, seed, steps, out, tag, log=print, denoise=1.0):
        im = relit(world, gain=(0.18, 0.2, 0.4)) if "night" in tag else relit(world, gain=(0.9, 0.7, 0.8))
        if "night" in tag:
            for x, y in [(100, 400), (260, 420), (500, 380), (900, 430), (1100, 410)]:
                cv2.rectangle(im, (x, y), (x + 16, y + 24), (255, 200, 110), -1)
        Image.fromarray(im).save(out)
        return out
    monkeypatch.setattr(light, "relight", fake)
    monkeypatch.setattr("engine.backends.depth.estimate", lambda im, size="small": np.zeros((im.height, im.width), np.float32))
    import engine.region as regionmod

    def find(project, src, region, log=print):
        seen.append((Path(src).name, region.prompt))
        if region.prompt == "the sky":
            raise RuntimeError("no nodes")
        m = np.zeros((720, 1280), np.uint8); m[:, :640] = 255      # "the windows on the left"
        out = Path(project.build / "_generated" / "m.png"); out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(m, "L").save(out)
        return out
    monkeypatch.setattr(regionmod, "find", find)
    p = Project(root)
    cfg = scene.build(p.load().sections[0], BuildContext(p, "day", log=lambda m: None), {})
    assert ("night.png", "the windows on the left") in seen            # searched on the picture where the lights are lit
    pair = cfg["pairs"][1]
    assert pair["lamp"] and pair["glow"] == 1.5
    lamp = np.asarray(Image.open(root / ".build" / "day" / "web" / Path(pair["lamp"]).relative_to("assets/day")))
    xs = np.nonzero(lamp[..., 0] > 128)[1]
    assert xs.size and xs.max() < lamp.shape[1] * 0.55                   # nothing from the right half


def test_chain_relights_each_time_from_its_neighbour_nearer_the_world(tmp_path, monkeypatch):
    from engine.project import BuildContext, Project
    root = make_project(tmp_path, "structure: { chain: true, strength: 0.8 }")
    (root / "site.yaml").write_text((root / "site.yaml").read_text().replace("times: [dawn, noon, night]", "times: [dawn, morning, noon, golden-hour, night]")
                                    .replace("steps: [{ title: One }, { title: Two }, { title: Three }]", "steps: [{ title: One }, { title: Two }, { title: Three }]"))
    world = place(1280, 720)
    seen = []

    def fake(world_png, instruction, seed, steps, out, tag, log=print, denoise=1.0):
        seen.append((tag.split("_")[0], Path(world_png).name, denoise))
        Image.fromarray(relit(world, gain=(0.9, 0.8, 0.7) if "night" not in tag else (0.2, 0.2, 0.4))).save(out)
        return out
    monkeypatch.setattr(light, "relight", fake)
    monkeypatch.setattr("engine.backends.depth.estimate", lambda im, size="small": np.zeros((im.height, im.width), np.float32))
    import engine.region as regionmod
    monkeypatch.setattr(regionmod, "find", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no nodes")))
    p = Project(root)
    cfg = scene.build(p.load().sections[0], BuildContext(p, "day", log=lambda m: None), {})
    by = {t: (src, d) for t, src, d in seen}
    assert by["morning"] == ("noon.png", 0.8) and by["dawn"] == ("morning.png", 0.8)       # backwards from the world's time
    assert by["golden-hour"] == ("noon.png", 0.8) and by["night"] == ("golden-hour.png", 0.8)    # forwards
    assert [t["id"] for t in cfg["times"]] == ["dawn", "morning", "noon", "golden-hour", "night"]
    rep = json.loads((root / ".build" / "day" / "times" / "night.json").read_text())
    assert rep["source"] == "golden-hour" and "to_world" in rep
    # change the world's own time and everything made from it is made again; change the last link and only it is
    seen.clear()
    (root / "site.yaml").write_text((root / "site.yaml").read_text().replace("times: [dawn, morning, noon, golden-hour, night]",
                                                                             "times: [dawn, morning, noon, golden-hour, {preset: night, prompt: with fog}]"))
    scene.build(p.load().sections[0], BuildContext(p, "day", log=lambda m: None), {})
    assert [t for t, *_ in seen] == ["night"]
