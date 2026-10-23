"""Film grammar between sections: `transition:` on a section (engine/cuts.py, cuts_shapes.py, cuts_design.py).

The spec and its schema, the plan a site compiles to (which sections hand over, what the page carries, what is dropped),
the markup of a join (two pins and a gap, only where a transition is set), the shapes a match cut finds (synthetic
pictures, with Florence-2 and SAM 2.1 replaced by a fake mask), the images designed to match another section's frame
(with the editor replaced), and cache keys. No ComfyUI, Blender, GPU or browser is needed."""
from __future__ import annotations

import json
import re
import textwrap

import numpy as np
import pytest
import yaml
from PIL import Image
from pydantic import ValidationError

from engine import cuts, cuts_design, cuts_shapes
from engine.compile import compiler, fonts
from engine.inputs import image_key, stable_dump
from engine.project import Project
from engine.spec import CutAnchor, FrameMatch, ImageInput, Site, Transition


def site(*sections, **kw) -> Site:
    return Site.model_validate({"name": "T", "sections": list(sections), **kw})


def block(i, **kw):
    return {"type": "intro", "id": f"s{i}", "title": f"Section {i}", **kw}


# ---------------------------------------------------------------- the spec

def test_a_bare_name_is_a_transition_and_defaults_leave_everything_off():
    s = site(block(0, transition="whip"), block(1))
    t = s.sections[0].transition
    assert t.type == "whip" and t.length is None and t.direction is None and t.carry is None
    assert s.sections[1].transition is None                    # today's behaviour is the default
    assert cuts.length_of(t) == 1.1
    assert cuts.length_of(Transition(type="match")) == 1.5
    assert cuts.length_of(Transition(type="iris", length=2)) == 2.0


def test_every_type_has_a_default_length():
    assert set(cuts.DEFAULT_LENGTH) == set(cuts.CUT_TYPES)


def test_the_documented_examples_validate():
    t = Transition.model_validate(yaml.safe_load(textwrap.dedent('''\
        type: match
        shape: the round logo
        becomes: { selector: ".ss-phone__screen" }
        zoom: 2.5
        blend: 0.05
        ''')))
    assert t.shape.prompt == "the round logo" and t.becomes.selector == ".ss-phone__screen" and t.zoom == 2.5
    c = Transition.model_validate({"type": "carry", "carry": {"from": ".ss-h1", "to": ".ss-num", "via": "wipe"}})
    assert c.carry.from_ == ".ss-h1" and c.carry.to == ".ss-num" and c.carry.via == "wipe"
    assert Transition(type="carry", carry={}).carry.from_ == "h1, h2"
    i = Transition.model_validate({"type": "iris", "origin": [0.3, 0.7], "closing": True, "soft": 0.2})
    assert i.origin == (0.3, 0.7) and i.closing


def test_bad_transitions_are_refused():
    with pytest.raises(ValidationError):
        Transition(type="spin")
    with pytest.raises(ValidationError):
        Transition(type="whip", shape="the sun")                # shape belongs to match
    with pytest.raises(ValidationError):
        Transition(type="match", carry={})                       # carry belongs to carry
    with pytest.raises(ValidationError):
        Transition(type="cut", length=0.01)
    with pytest.raises(ValidationError):
        Transition(type="wipe", direction="sideways")
    with pytest.raises(ValidationError):
        Transition(type="cut", nonsense=1)
    with pytest.raises(ValidationError):
        CutAnchor(prompt="a", selector=".b")                     # exactly one of prompt / box / selector
    with pytest.raises(ValidationError):
        CutAnchor()
    assert CutAnchor(box=(0.1, 0.1, 0.3, 0.3)).prompt is None


def test_scenes_and_blocks_both_take_a_transition_and_the_schema_says_so():
    schema = json.dumps(Site.model_json_schema())
    assert '"Transition"' in schema and '"CutAnchor"' in schema and '"FrameMatch"' in schema
    s = site({"type": "parallax", "id": "p", "steps": [], "transition": "iris"}, {"type": "hero", "title": "x", "transition": {"type": "cut"}})
    assert s.sections[0].transition.type == "iris" and s.sections[1].transition.type == "cut"


def test_a_transition_never_enters_a_scene_or_image_cache_key():
    a = ImageInput(generate="a ring")
    assert "match" not in json.dumps(stable_dump(a)) and "match" not in json.dumps(image_key(a))
    b = ImageInput(generate="a ring", match=FrameMatch(section="x", shape="the ring"))
    assert image_key(a) != image_key(b)                          # but a designed image is its own thing


# ---------------------------------------------------------------- the plan

def test_plan_lists_each_handover_and_numbers_them():
    s = site(block(0, transition="cut"), block(1), block(2, transition={"type": "iris", "length": 2}), block(3))
    pairs = cuts.cut_pairs(s)
    assert [(a, b, t.type) for a, b, t in pairs] == [(0, 1, "cut"), (2, 3, "iris")]
    p = cuts.plan(s, lambda m: None)
    assert [(c["n"], c["a"], c["b"], c["type"], c["length"]) for c in p] == [(0, 0, 1, "cut", 0.8), (1, 2, 3, "iris", 2.0)]
    assert p[0]["label"] == "s0 -> s1"
    assert "carry" not in p[0] and "anchors" not in p[0]


def test_the_last_section_and_the_stack_layout_have_nothing_to_hand_over():
    notes: list[str] = []
    p = cuts.plan(site(block(0), block(1, transition="cut")), notes.append)
    assert p == [] and "last section" in notes[0]
    notes.clear()
    p = cuts.plan(site(block(0, transition="cut"), block(1), layout="stack"), notes.append)
    assert p == [] and "stack" in notes[0]


def test_a_carry_always_carries_its_selectors_and_a_match_its_anchors():
    s = site(block(0, transition="carry"), block(1, transition="match"), block(2))
    p = cuts.plan(s, lambda m: None, {1: {"a": {"sel": ".x"}, "b": {"sel": ".y"}}})
    assert p[0]["carry"] == {"from": "h1, h2", "to": "h1, h2", "via": "dissolve"}
    assert p[1]["anchors"]["b"] == {"sel": ".y"} and "anchors" not in p[0]


# ---------------------------------------------------------------- the markup of a join

@pytest.fixture
def built(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "vendor", lambda *a, **k: None)

    def go(**site_kw):
        root = tmp_path / "p"
        (root / "inputs").mkdir(parents=True, exist_ok=True)
        proj = Project(root)
        proj.spec_path.write_text(yaml.safe_dump(site_kw), encoding="utf-8")
        compiler.build_site(proj, log=lambda m: None)
        return (proj.dist / "index.html").read_text(encoding="utf-8")
    return go


def test_a_site_without_transitions_has_no_cut_markup(built):
    html = built(name="T", sections=[block(0), block(1)])
    assert "ss-cut" not in html.replace("ss-cuts-on", "") and "ss-cuts" not in html


def test_a_join_is_two_pins_and_a_gap_and_the_page_carries_the_cut(built):
    html = built(name="T", sections=[block(0, transition={"type": "wipe", "direction": "right"}), block(1), block(2)])
    assert html.count('class="ss-cutw ss-cutw--out"') == 1 and html.count('class="ss-cutw ss-cutw--in"') == 1
    assert html.count('class="ss-cutpin ss-cutpin--') == 2 and html.count('class="ss-cutgap"') == 2
    assert 'style="--cut-l: 1.3"' in html
    m = re.search(r'id="ss-cuts">(.*?)</script>', html, re.S)
    c = json.loads(m.group(1))
    assert len(c) == 1 and c[0]["type"] == "wipe" and c[0]["direction"] == "right" and (c[0]["a"], c[0]["b"]) == (0, 1)
    # the section between two cuts is the lower pin of one and the upper pin of the other: the pins nest
    html = built(name="T", sections=[block(0, transition="cut"), block(1, transition="dissolve"), block(2)])
    assert html.count("ss-cutpin--in") == 2 and html.count("ss-cutpin--out") == 2
    assert html.index('data-cut-in="0"') < html.index('data-cut-out="1"') < html.index('data-cut-in="1"') or \
        html.index('data-cut-in="1"') > html.index('data-cut-out="1"')


def test_a_style_that_plays_its_own_handover_drops_the_cuts(built):
    from engine.compile import themes
    flagged = {n for n, v in themes.styles().items() if v.get("cuts") is False}
    assert {"flipbook", "zoetrope", "pop-up-book"} <= flagged and "halftone" not in flagged and "neo-brutalism" not in flagged
    html = built(name="T", theme={"style": "flipbook"}, sections=[block(0, transition="cut"), block(1)])
    assert "ss-cut" not in html.replace("ss-cuts-on", "")
    html = built(name="T", theme={"style": "halftone"}, sections=[block(0, transition="cut"), block(1)])
    assert 'id="ss-cuts"' in html


# ---------------------------------------------------------------- finding shapes

def disc_image(w=640, h=360, cx=200, cy=180, r=70, bg=(20, 40, 90), fg=(250, 250, 250)) -> Image.Image:
    yy, xx = np.mgrid[:h, :w]
    a = np.zeros((h, w, 3), np.uint8)
    a[:] = bg
    a[((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r] = fg
    return Image.fromarray(a)


def rect_image(w=640, h=360, box=(400, 100, 560, 300), bg=(240, 190, 90), fg=(30, 30, 40)) -> Image.Image:
    a = np.zeros((h, w, 3), np.uint8)
    a[:] = bg
    a[box[1]:box[3], box[0]:box[2]] = fg
    return Image.fromarray(a)


def test_a_mask_becomes_a_shape_with_a_box_and_a_kind():
    m = np.asarray(disc_image().convert("L")) > 128
    sh = cuts_shapes.mask_shape(m.astype(np.uint8) * 255)
    x0, y0, x1, y1 = sh["box"]
    assert sh["kind"] == "round" and abs((x0 + x1) / 2 - 200 / 640) < 0.01 and abs((y1 - y0) - 140 / 360) < 0.02
    r = np.asarray(rect_image().convert("L")) < 100
    assert cuts_shapes.mask_shape(r.astype(np.uint8) * 255)["kind"] == "rect"
    assert cuts_shapes.mask_shape(np.zeros((10, 10), np.uint8)) is None


def test_the_best_pair_is_found_without_any_model_round_to_round_and_rect_to_rect():
    a = disc_image(cx=200, cy=180, r=70)
    b = disc_image(cx=400, cy=190, r=110, bg=(240, 170, 80), fg=(255, 250, 235))
    ca, cb = cuts_shapes.candidates(a), cuts_shapes.candidates(b)
    assert ca and cb
    sa, sb, conf = cuts_shapes.pair_shapes(ca, cb)
    assert sa["kind"] == sb["kind"] == "round" and 0 < conf <= 1
    assert abs((sb["box"][0] + sb["box"][2]) / 2 - 400 / 640) < 0.02 and (sb["box"][2] - sb["box"][0]) > (sa["box"][2] - sa["box"][0])
    # a door frame and a phone screen: tall rectangles
    d = rect_image(box=(100, 60, 260, 320), bg=(150, 120, 80), fg=(20, 20, 20))
    p = rect_image(box=(300, 40, 420, 330), bg=(235, 235, 240), fg=(15, 15, 25))
    sd, sp, _ = cuts_shapes.pair_shapes(cuts_shapes.candidates(d), cuts_shapes.candidates(p))
    assert sd["kind"] == sp["kind"] == "rect"


def test_a_plain_picture_has_no_shapes_to_offer():
    assert cuts_shapes.candidates(Image.fromarray(np.full((200, 300, 3), 128, np.uint8))) == []
    assert cuts_shapes.pair_shapes([], cuts_shapes.candidates(disc_image())) is None


def test_the_anchor_carries_how_the_page_fits_the_picture():
    sh = {"box": [0.1, 0.2, 0.3, 0.4], "kind": "round"}
    a = cuts_shapes.anchor(sh, {"of": ".ss-hero__media img", "fit": "cover", "scale": 1.0}, (1920, 1080), "prompt")
    assert a == {"box": [0.1, 0.2, 0.3, 0.4], "aspect": 1.7778, "how": "prompt", "kind": "round", "of": ".ss-hero__media img"}
    b = cuts_shapes.anchor(sh, {"of": None, "fit": "contain", "scale": 1.14}, (100, 100), "contour")
    assert b["fit"] == "contain" and b["scale"] == 1.14 and "of" not in b


def project_with_heroes(tmp_path, a_img: Image.Image, b_img: Image.Image) -> tuple[Project, list[dict], Site]:
    """Two hero blocks with real pictures, compiled far enough to know their published images."""
    root = tmp_path / "p"
    (root / "inputs").mkdir(parents=True)
    a_img.save(root / "inputs" / "a.png")
    b_img.save(root / "inputs" / "b.png")
    proj = Project(root)
    spec = {"name": "T", "sections": [
        {"type": "hero", "id": "a", "title": "A", "image": "inputs/a.png", "transition": {"type": "match", "shape": "the ring"}},
        {"type": "hero", "id": "b", "title": "B", "image": "inputs/b.png"}]}
    proj.spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return proj, proj.load().sections, proj.load()


def entries_of(proj: Project, st: Site) -> list[dict]:
    """The compiler's entries for two heroes: the published image of each (what `picture` reads)."""
    from engine.compile.compiler import _env  # noqa: F401  (the compiler is exercised in the markup tests)
    out = []
    media = proj.dist / "assets" / "_media"
    media.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(st.sections):
        src = proj.path(s.image)
        dst = media / f"img{i}.webp"
        Image.open(src).save(dst, "WEBP")
        out.append({"s": s, "scene": False, "config": None, "img": f"assets/_media/{dst.name}", "video": None, "backdrop": None})
    return out


def test_a_prompt_finds_its_shape_through_the_model_once_and_caches_it(tmp_path, monkeypatch):
    from engine import region
    proj, _, st = project_with_heroes(tmp_path, disc_image(), disc_image(cx=420, cy=170, r=110, bg=(240, 170, 80)))
    entries = entries_of(proj, st)
    calls = []

    def fake_find(project, src, rg, log=print):
        calls.append(rg.prompt)
        im = Image.open(src).convert("RGB")
        a = np.asarray(im).astype(int)
        mask = (a.sum(axis=2) > 650).astype(np.uint8) * 255          # the bright disc
        out = project.build / "_generated" / f"fake_{len(calls)}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(mask).save(out)
        return out
    monkeypatch.setattr(region, "find", fake_find)
    pairs = cuts.cut_pairs(st)
    got = cuts_shapes.analyse(proj, pairs, ["a -> b"], entries, proj.dist, lambda m: None)
    assert calls == ["the ring", "the ring"]                           # `becomes` defaults to the same prompt, on the next picture
    a, b = got[0]["a"], got[0]["b"]
    assert a["how"] == b["how"] == "prompt" and a["of"] == ".ss-hero__media img"
    assert abs((a["box"][0] + a["box"][2]) / 2 - 200 / 640) < 0.02 and abs((b["box"][0] + b["box"][2]) / 2 - 420 / 640) < 0.02
    again = cuts_shapes.analyse(proj, pairs, ["a -> b"], entries, proj.dist, lambda m: None)
    assert again == got and len(calls) == 2                            # from the cache: no model the second time


def test_a_selector_and_a_box_need_no_model_and_a_nothing_found_softens_the_cut(tmp_path, monkeypatch):
    from engine import region
    from engine.project import BuildError
    proj, _, st = project_with_heroes(tmp_path, disc_image(), disc_image())
    st.sections[0].transition = Transition(type="match", shape=CutAnchor(box=(0.2, 0.2, 0.5, 0.8)),
                                           becomes=CutAnchor(selector=".ss-phone__screen"))
    entries = entries_of(proj, st)
    monkeypatch.setattr(region, "find", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model needed")))
    got = cuts_shapes.analyse(proj, cuts.cut_pairs(st), ["a -> b"], entries, proj.dist, lambda m: None)
    assert got[0]["b"] == {"sel": ".ss-phone__screen"} and got[0]["a"]["box"] == [0.2, 0.2, 0.5, 0.8] and got[0]["a"]["how"] == "box"
    # a prompt the model cannot find: no anchors, so the page dissolves
    st.sections[0].transition = Transition(type="match", shape="a unicorn")
    monkeypatch.setattr(region, "find", lambda *a, **k: (_ for _ in ()).throw(BuildError("nothing matching")))
    notes: list[str] = []
    assert cuts_shapes.analyse(proj, cuts.cut_pairs(st), ["a -> b"], entries, proj.dist, notes.append) == {}
    assert any("no shapes to meet on" in n for n in notes)


def test_without_names_the_engine_looks_for_the_shapes_itself(tmp_path):
    proj, _, st = project_with_heroes(tmp_path, disc_image(), disc_image(cx=430, cy=170, r=100, bg=(240, 170, 80), fg=(255, 250, 235)))
    st.sections[0].transition = Transition(type="match")
    got = cuts_shapes.analyse(proj, cuts.cut_pairs(st), ["a -> b"], entries_of(proj, st), proj.dist, lambda m: None)
    assert got[0]["a"]["how"] == "contour" and got[0]["a"]["kind"] == "round" and got[0]["score"] > 0.4


# ---------------------------------------------------------------- designing the second picture

def test_the_edit_instruction_says_what_stays_and_what_changes():
    m = FrameMatch(section="mark", shape="the white ring", becomes="the sun", prompt="a calm sea at dawn")
    text = cuts_design.instruction(m)
    assert "the white ring" in text and "the sun" in text and "a calm sea at dawn" in text and "same size" in text
    assert text.startswith("Replace the white ring with the sun. The sun fills exactly the area")
    assert "new scene" in cuts_design.instruction(FrameMatch(section="m", shape="the ring"))
    assert cuts_design.placement([0.05, 0.4, 0.2, 0.6]) == "in the middle left, about a fifth of the width"
    assert cuts_design.placement([0.4, 0.4, 0.6, 0.6]).startswith("in the centre of the frame")
    assert cuts_design.placement([0.75, 0.05, 0.85, 0.15]).startswith("in the upper right, small")


def design_project(tmp_path) -> Project:
    root = tmp_path / "d"
    (root / "inputs").mkdir(parents=True)
    disc_image().save(root / "inputs" / "mark.png")
    proj = Project(root)
    spec = {"name": "T", "sections": [
        {"type": "hero", "id": "mark", "title": "A", "image": "inputs/mark.png"},
        {"type": "hero", "id": "sun", "title": "B", "image": {"match": {"section": "mark", "shape": "the ring", "becomes": "the sun",
                                                                          "prompt": "a calm sea at dawn", "how": "edit"}}}]}
    proj.spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return proj


def test_an_edit_match_hands_the_other_frame_to_the_editor(tmp_path, monkeypatch):
    from engine import inputs
    proj = design_project(tmp_path)
    seen = {}

    def fake_edit(project, ref, log=print):
        seen["ref"] = ref
        out = project.build / "_generated" / "edited.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(project.path(ref.edit.source.file)).save(out)
        return out
    monkeypatch.setattr(inputs, "_edit", fake_edit)
    out = inputs.resolve_image(proj, proj.load().sections[1].image)
    e = seen["ref"].edit
    assert out.name == "edited.png" and e.source.file == "inputs/mark.png" and "the sun" in e.instruction and e.seed == 7


def test_a_hint_match_writes_the_shapes_place_into_the_prompt(tmp_path, monkeypatch):
    from engine import inputs
    proj = design_project(tmp_path)
    ref = proj.load().sections[1].image.model_copy(update={"match": FrameMatch(
        section="mark", shape="the ring", becomes="the sun", prompt="a calm sea at dawn", how="hint")})
    monkeypatch.setattr(cuts_shapes, "find_by_prompt", lambda project, path, prompt, log=print: {"box": [0.05, 0.4, 0.2, 0.6]})
    got = {}

    def fake_generate(project, r, log=print, alpha=False):
        got["prompt"] = r.generate
        return project.root / "inputs" / "mark.png"
    real = inputs.resolve_image
    monkeypatch.setattr(inputs, "resolve_image", lambda project, r, log=print, alpha=False: fake_generate(project, r, log) if getattr(r, "generate", None) else real(project, r, log, alpha))
    cuts_design.match_image(proj, ref)
    assert got["prompt"].startswith("a calm sea at dawn.") and "the sun is in the middle left" in got["prompt"]


def test_a_match_needs_its_section_built_first(tmp_path):
    from engine.project import BuildError
    proj = design_project(tmp_path)
    scene = {"type": "parallax", "id": "p", "steps": []}
    spec = proj.raw()
    spec["sections"].insert(0, scene)
    spec["sections"][2]["image"]["match"]["section"] = "p"
    proj.spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    with pytest.raises(BuildError, match="not built yet"):
        cuts_design.section_frame(proj, proj.load(), "p")
    with pytest.raises(BuildError, match="no section with id"):
        cuts_design.section_frame(proj, proj.load(), "nope")
    assert cuts_design.section_frame(proj, proj.load(), "mark").name == "mark.png"
