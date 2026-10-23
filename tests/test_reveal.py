"""reveal (scroll-driven colour) and faces: the spec, the key easing (and its twin in the browser runtime), choosing what a
prompt found, the CPU compositor, the mask atlas videos (frame count, size, GOP), the build plan's stages, and the
storyboard's view. No ComfyUI, Blender or GPU is needed: the models' own outputs are replaced by synthetic masks."""
from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from engine import reveal
from engine.config import settings
from engine.spec import Beat, FilmScene, Reveal, RevealAt, RevealRegion, Site

FFMPEG = shutil.which(settings()["ffmpeg"]) or shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg is not on the PATH")

REVEAL = yaml.safe_load(textwrap.dedent('''\
    base: mono
    regions:
      - { id: her_hand, prompt: "the woman's hand", at: { beat: hands, t: 0.5 } }
      - { id: shoes, prompt: "the shoes of the woman and the man", at: { beat: feet, t: 0.5 } }
      - { id: couple, prompt: "the woman in the long coat and the man in the jacket", at: { beat: walk, t: 0 } }
    keys:
      - { at: 0.40, her_hand: 0 }
      - { at: 0.48, her_hand: 1 }
      - { at: 0.55, shoes: 0 }
      - { at: 0.62, shoes: 1 }
      - { at: 0.70, couple: 0 }
      - { at: 0.80, couple: 1 }
    feather: 6
'''))


# ---------------------------------------------------------------- the spec

def test_the_documented_example_validates():
    rv = Reveal.model_validate(REVEAL)
    assert [r.id for r in rv.regions] == ["her_hand", "shoes", "couple"]
    assert rv.regions[0].at.beat == "hands" and rv.regions[2].at.t == 0
    assert rv.base == "mono" and rv.feather == 6 and rv.ease == "smooth" and rv.tracker == "large"


def test_a_film_section_takes_reveal_and_faces():
    f = FilmScene.model_validate({"id": "s", "type": "film", "video": "inputs/a.mp4", "reveal": REVEAL, "faces": "restore"})
    assert f.reveal is not None and f.faces.mode == "restore" and f.faces.strength == 0.7
    assert FilmScene.model_validate({"id": "s", "type": "film", "video": "a.mp4"}).reveal is None
    assert FilmScene.model_validate({"id": "s", "type": "film", "video": "a.mp4", "faces": "off"}).faces is None


def test_faces_on_a_beat_and_with_options():
    b = Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "faces": {"mode": "restore", "strength": 0.4, "min_size": 64}})
    assert b.faces.strength == 0.4 and b.faces.min_size == 64
    assert Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "faces": "restore"}).faces.min_size == 96
    assert Beat.model_validate({"id": "a", "prompt": "p", "motion": "m"}).faces is None
    with pytest.raises(ValidationError):
        Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "faces": {"mode": "codeformer"}})


@pytest.mark.parametrize("patch, why", [
    ({"base": "sepia"}, "base"),
    ({"regions": [{"id": "a"}]}, "a prompt, points or a box"),
    ({"regions": [{"id": "a", "prompt": "x"}, {"id": "a", "prompt": "y"}]}, "unique"),
    ({"keys": [{"at": 0.1, "nope": 1}]}, "not a region id"),
    ({"keys": [{"at": 0.1, "her_hand": 2}]}, "between 0 and 1"),
    ({"keys": [{"her_hand": 1}]}, "needs `at`"),
])
def test_bad_reveal_specs_are_refused(patch, why):
    with pytest.raises(ValidationError, match=why):
        Reveal.model_validate({**REVEAL, **patch})


def test_base_can_be_a_tint_colour_and_a_region_can_be_pointed_at():
    rv = Reveal.model_validate({"base": "#2a4a6a", "regions": [{"id": "p", "points": [[0.4, 0.6]], "negative_points": [[0.1, 0.1]]},
                                                             {"id": "b", "box": [0.1, 0.1, 0.5, 0.5], "at": [{"frame": 3}, {"seconds": 9}]}]})
    assert rv.base == "#2a4a6a"
    assert len(rv.regions[1].seeds) == 2 and rv.regions[0].seeds[0].t == 0.5


def test_the_schema_is_exported_for_the_ui_and_mcp():
    schema = json.dumps(Site.model_json_schema())
    assert "RevealRegion" in schema and "Faces" in schema


# ---------------------------------------------------------------- keys and easing

KEYS = REVEAL["keys"]
IDS = ["her_hand", "shoes", "couple"]


def test_amounts_hold_before_ease_between_and_hold_after():
    a = lambda p, **kw: reveal.amounts_at(KEYS, IDS, p, **kw)
    assert a(0.0) == {"her_hand": 0.0, "shoes": 0.0, "couple": 0.0}
    assert a(0.44)["her_hand"] == pytest.approx(0.5)                      # smoothstep passes through the middle
    assert a(0.5)["her_hand"] == 1 and a(1.0) == {"her_hand": 1.0, "shoes": 1.0, "couple": 1.0}
    assert a(0.41, ease="linear")["her_hand"] == pytest.approx(0.125)
    assert a(0.41)["her_hand"] < a(0.41, ease="linear")["her_hand"]       # eased start is slower than linear
    assert a(0.44)["shoes"] == 0 and a(0.585)["shoes"] == pytest.approx(0.5)


def test_reduced_motion_jumps_to_the_end_of_each_change():
    a = lambda p: reveal.amounts_at(KEYS, IDS, p, reduced=True)
    assert a(0.39)["her_hand"] == 0 and a(0.40)["her_hand"] == 0 and a(0.401)["her_hand"] == 1 and a(0.45)["her_hand"] == 1
    assert all(v in (0, 1) for p in np.linspace(0, 1, 101) for v in a(p).values())


def test_without_keys_the_regions_come_in_one_after_another():
    rv = Reveal.model_validate({**REVEAL, "keys": []})
    keys = reveal.region_keys(rv)
    first, last = reveal.amounts_at(keys, IDS, 0.3), reveal.amounts_at(keys, IDS, 0.95)
    assert first["her_hand"] > 0 and first["couple"] == 0 and last == {"her_hand": 1.0, "shoes": 1.0, "couple": 1.0}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_runtime_eases_keys_exactly_as_the_engine_does(tmp_path):
    root = Path(__file__).resolve().parent.parent
    esbuild = root / "node_modules" / ".bin" / ("esbuild.cmd" if (root / "node_modules" / ".bin" / "esbuild.cmd").exists() else "esbuild")
    if not esbuild.exists():
        pytest.skip("esbuild is not installed (npm install)")
    out = tmp_path / "keys.mjs"
    subprocess.run([str(esbuild), str(root / "runtime" / "src" / "lib" / "revealKeys.ts"), "--format=esm", f"--outfile={out}"],
                   check=True, capture_output=True)
    ps = [round(x, 3) for x in np.linspace(0, 1, 61)]
    script = (f"import {{ amountsAt }} from {json.dumps(out.as_uri())};"
              f"const keys={json.dumps(KEYS)}, ids={json.dumps(IDS)}, ps={json.dumps(ps)};"
              "const r={};for(const e of ['smooth','linear'])for(const red of [false,true])"
              "r[e+red]=ps.map(p=>amountsAt(keys,ids,p,e,red));console.log(JSON.stringify(r));")
    got = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], check=True, capture_output=True, text=True).stdout)
    for e in ("smooth", "linear"):
        for red in (False, True):
            want = [reveal.amounts_at(KEYS, IDS, p, e, red) for p in ps]
            for g, w in zip(got[e + str(red).lower()], want):
                assert g == pytest.approx(w, abs=1e-9)


# ---------------------------------------------------------------- frames, shots, choosing boxes

def _beats(*names, seconds=4.0):
    return [Beat(id=n, prompt="p", motion="m", seconds=seconds) for n in names]


def test_a_moment_in_a_beat_is_a_frame_of_the_joined_film():
    sec = FilmScene(id="s", type="film", beats=_beats("hands", "feet", "walk"), beat_fade=0.25)
    spans = reveal.beat_spans(sec, [4.0, 4.0, 4.0], 0.25)
    n = 276                                          # 3 x 96 frames minus two 6-frame crossfades
    assert spans["hands"][0] == 0 and spans["walk"][1] == pytest.approx(1.0)
    at = lambda **kw: reveal.film_frame(sec, RevealAt(**kw), n, 24.0, spans)
    assert at(beat="hands", t=0) == 0 and at(beat="walk", t=1) == n - 1
    assert 40 <= at(beat="hands", t=0.5) <= 56 and 130 <= at(beat="feet", t=0.5) <= 146
    assert at(frame=10) == 10 and at(seconds=2.0) == 48 and at(t=0.5) == round(0.5 * (n - 1)) and at(frame=9999) == n - 1
    with pytest.raises(Exception, match="beat"):
        at(beat="nope")


def test_the_prompt_the_xs_y_and_the_y_of_the_x_name_an_owner():
    assert reveal.split_owner("the woman's hand") == ("hand", "the woman")
    assert reveal.split_owner("the shoes of the woman and the man") == ("shoes", "the woman and the man")
    assert reveal.split_owner("a red car") == ("a red car", None)


def test_boxes_are_chosen_inside_the_owner_then_picked():
    hand_l, hand_r, whole = [0.30, 0.60, 0.43, 0.90], [0.62, 0.25, 0.80, 0.56], [0.0, 0.0, 1.0, 1.0]
    woman = [[0.1, 0.0, 0.5, 1.0]]
    assert reveal.choose_boxes([hand_r, hand_l], "all", woman) == [hand_l]            # only hers is inside her
    assert reveal.choose_boxes([hand_r, hand_l], "all") == [hand_r, hand_l]
    assert reveal.choose_boxes([hand_r, hand_l], "left") == [hand_l]
    assert reveal.choose_boxes([hand_r, hand_l], "right") == [hand_r]
    assert reveal.choose_boxes([hand_r, hand_l], 1) == [hand_l]
    assert reveal.choose_boxes([whole, hand_l], "all") == [hand_l]                    # a box round everything is a give-up
    assert reveal.choose_boxes([whole], "all") == [whole] and reveal.choose_boxes([], "all") == []
    assert reveal.choose_boxes([hand_l, [0.3, 0.6, 0.5, 1.0]], "largest") == [[0.3, 0.6, 0.5, 1.0]]


def test_sam_prompts_carry_boxes_and_points():
    rg = RevealRegion(id="a", prompt="x", points=[(0.31, 0.7), (0.9, 0.9)], negative_points=[(0.5, 0.5)])
    items = reveal.region_prompts(rg, [[0.3, 0.6, 0.4, 0.9]])
    assert items[0]["box"] == [0.3, 0.6, 0.4, 0.9] and [0.31, 0.7] in items[0]["points"] and 0 in items[0]["labels"]
    assert items[1] == {"points": [[0.9, 0.9]], "labels": [1]}                       # a point outside every box is its own object
    assert reveal.region_prompts(RevealRegion(id="b", points=[(0.2, 0.2)]), []) == [{"points": [[0.2, 0.2]], "labels": [1]}]


# ---------------------------------------------------------------- the compositor (the shader's twin)

def _frame():
    rng = np.random.default_rng(3)
    f = rng.integers(0, 255, (36, 64, 3), dtype=np.uint8)
    f[..., 0] = np.maximum(f[..., 0], 120)           # clearly coloured
    return f


def test_base_looks():
    f = _frame().astype(np.float32) / 255
    mono = reveal.base_treatment(f, "mono")
    assert np.allclose(mono[..., 0], mono[..., 1]) and np.allclose(mono[..., 1], mono[..., 2])
    dim = reveal.base_treatment(f, "dim")
    assert dim.mean() < f.mean() * 0.7
    blur = reveal.base_treatment(f, "blur")
    assert np.abs(np.diff(blur, axis=1)).mean() < np.abs(np.diff(f, axis=1)).mean() * 0.5
    tint = reveal.base_treatment(f, "#204060")
    assert tint[..., 2].mean() > tint[..., 0].mean()                                  # bluer than red: the tint shows


def test_composite_is_base_outside_the_mask_and_colour_inside_it():
    f = _frame()
    m = np.zeros((36, 64), np.float32)
    m[:, 32:] = 1
    out = reveal.composite(f, {"r": m}, {"r": 1.0}, "mono")
    assert np.array_equal(out[:, 40:], f[:, 40:])                                      # revealed: the film's own colour
    left = out[:, :24].astype(int)
    assert np.abs(left[..., 0] - left[..., 1]).max() <= 1                              # not revealed: grey
    half = reveal.composite(f, {"r": m}, {"r": 0.5}, "mono")[:, 40:].astype(int)
    assert (np.abs(half - f[:, 40:].astype(int)) > 0).any() and np.abs(half[..., 0] - f[:, 40:, 0].astype(int)).max() < 120
    assert np.array_equal(reveal.composite(f, {"r": m}, {"r": 0.0}, "mono")[:, 40:, 0], reveal.composite(f, {}, {}, "mono")[:, 40:, 0])
    two = reveal.composite(f, {"a": m, "b": m[:, ::-1].copy()}, {"a": 1, "b": 1}, "mono")
    assert np.array_equal(two, f)                                                       # the regions together cover the frame


# ---------------------------------------------------------------- the mask videos

def _probe(path: Path) -> dict:
    out = subprocess.run([settings()["ffprobe"], "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate,nb_read_frames", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["streams"][0]


@needs_ffmpeg
def test_masks_are_packed_in_an_atlas_video_with_the_films_frame_count_rate_and_gop(tmp_path):
    n, gop = 30, 6
    base = np.zeros((n, 540, 960), np.uint8)
    for i in range(n):
        base[i, 100 + i: 300, 200: 500 + 4 * i] = 255
    regions = [reveal.tile_masks(base, 6.0, 0, reveal.TILE) for _ in range(3)]
    assert regions[0].shape == (n, 544, 960) and 0 < regions[0][5].mean() < 255       # feathered: soft values exist
    dst = tmp_path / "mask.mp4"
    cols, rows = reveal.encode_atlas(regions, 24.0, gop, dst)
    assert (cols, rows) == (2, 2)
    info = _probe(dst)
    assert (info["width"], info["height"]) == (1920, 1088) and info["nb_read_frames"] == str(n) and info["r_frame_rate"] == "24/1"
    # keyframes every `gop` frames, like the film encode
    kf = subprocess.run([settings()["ffprobe"], "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pict_type", "-of", "csv=p=0",
                         str(dst)], capture_output=True, text=True, check=True).stdout.split()
    assert [i for i, k in enumerate(kf) if k.startswith("I")] == list(range(0, n, gop))
    # the first region's tile survives the codec
    raw = subprocess.run([settings()["ffmpeg"], "-v", "error", "-i", str(dst), "-vf", "select=eq(n\\,10)", "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    tile = np.frombuffer(raw, np.uint8).reshape(1088, 1920)[:544, :960]
    assert np.abs(tile.astype(int) - regions[0][10].astype(int)).mean() < 3
    assert reveal.atlas_layout(1) == (1, 1) and reveal.atlas_layout(2) == (2, 1) and reveal.atlas_layout(4) == (2, 2)


def test_grow_and_feather_change_the_mask_as_asked():
    m = np.zeros((1, 540, 960), np.uint8)
    m[0, 200:300, 400:500] = 255
    plain = reveal.tile_masks(m, 0, 0, reveal.TILE)[0]
    grown, shrunk = reveal.tile_masks(m, 0, 20, reveal.TILE)[0], reveal.tile_masks(m, 0, -20, reveal.TILE)[0]
    soft = reveal.tile_masks(m, 24, 0, reveal.TILE)[0]
    assert grown.sum() > plain.sum() > shrunk.sum()
    assert ((soft > 0) & (soft < 255)).sum() > ((plain > 0) & (plain < 255)).sum() * 3


# ---------------------------------------------------------------- the build plan

def _site(**film):
    return Site.model_validate({"name": "t", "sections": [{"id": "story", "type": "film", **film}]})


def test_the_plan_lists_the_reveal_and_faces_stages_in_order():
    from engine.plan import expected, units
    sec = _site(beats=[{"id": "hands", "prompt": "p", "motion": "m", "faces": "restore"}, {"id": "feet", "prompt": "p", "motion": "m"}],
                reveal=REVEAL, faces="restore").sections[0]
    names = expected(sec)
    assert names[:4] == ["beat_hands", "faces_hands", "beat_feet", "beats_join"]
    assert names[names.index("faces"):names.index("faces") + 2] == ["faces", "encode"]
    assert names[-1] == "reveal_pack" and "reveal_ground_her_hand" in names and "reveal_track_couple" in names and "reveal_work" in names
    assert "reveal_cuts" not in names                                                  # a beats film knows its own cuts
    assert units(sec, "reveal_track_shoes")[0] == "film:reveal_track" and units(sec, "faces_hands")[0] == "film:faces"
    one = _site(video="a.mp4", reveal={"regions": [{"id": "a", "box": [0, 0, 1, 1], "at": [{"t": 0}, {"t": 1}]}]}).sections[0]
    assert expected(one) == ["encode", "reveal_work", "reveal_cuts", "reveal_track_a_0", "reveal_track_a_1", "reveal_pack"]


# ---------------------------------------------------------------- the storyboard

@needs_ffmpeg
def test_the_storyboard_draws_a_still_the_way_the_page_will(tmp_path):
    from PIL import Image
    from engine.project import Project
    from engine.storyboard.reveal import reveal_still
    proj = tmp_path / "p"
    (proj / "inputs").mkdir(parents=True)
    (proj / "site.yaml").write_text("name: t\nsections: []\n")
    still = proj / "inputs" / "a.png"
    Image.fromarray(np.dstack([np.full((72, 128), 200, np.uint8), np.full((72, 128), 80, np.uint8), np.full((72, 128), 40, np.uint8)])).save(still)
    sec = _site(video="a.mp4", reveal={"regions": [{"id": "a", "box": [0, 0, 1, 1]}], "keys": [{"at": 0.2, "a": 0}, {"at": 0.4, "a": 1}]}).sections[0]
    project = Project(proj)
    cache = proj / ".build" / "_storyboard"

    def px(fraction):
        return np.asarray(Image.open(reveal_still(project, sec, sec.reveal, still, fraction, cache)).convert("RGB"))[360, 640].astype(int)
    grey = px(0.0)                                                                      # no masks yet: the base look only
    assert abs(grey[0] - grey[2]) <= 2
    masks = np.zeros((10, 540, 960), np.uint8)
    masks[:, :, :480] = 255                                                             # the left half is the region
    rdir = proj / ".build" / "story" / "reveal" / "a"
    rdir.mkdir(parents=True)
    np.savez_compressed(rdir / "masks.npz", masks=masks)
    sec2 = sec.model_copy(update={"id": "story"})
    left = lambda f: np.asarray(Image.open(reveal_still(project, sec2, sec2.reveal, still, f, cache)).convert("RGB"))[360, 200].astype(int)
    assert abs(left(0.0)[0] - left(0.0)[2]) <= 2                                       # amount 0: grey
    assert left(1.0)[0] - left(1.0)[2] > 100                                           # amount 1 inside the mask: its colour
    right = np.asarray(Image.open(reveal_still(project, sec2, sec2.reveal, still, 1.0, cache)).convert("RGB"))[360, 1000].astype(int)
    assert abs(right[0] - right[2]) <= 2                                               # outside the mask: still grey
