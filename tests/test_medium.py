"""Art direction in one medium (engine/medium.py, issue #131): the spec fields, the prompt words, the inks taken from
the brand, the post-process of every medium on a fixture drawn here with PIL (deterministic, with the properties each
medium promises), the composition check on calm and busy pictures, and the example built on the CPU. No GPU."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw
from pydantic import ValidationError

from engine import imagery, medium
from engine.compile import compiler
from engine.inputs import art_direction, hero_image, resolve_image, treated_prompt
from engine.project import Project
from engine.spec import MEDIUM_NAMES, HeroBlock, ImageInput, Imagery, Site

ROOT = Path(__file__).resolve().parent.parent
BRAND = {"bg": "#f6f1e7", "bg2": "#ece4d3", "ink": "#16203a", "accent": "#2f4fd8", "accent2": "#ff6c8f"}


def fixture(w: int = 480, h: int = 272, seed: int = 1) -> Image.Image:
    """A small illustration: a blue sky graded to pink, a sun, hills, a dark house; enough tone and colour for every
    medium to have something to print."""
    im = Image.new("RGB", (w, h))
    px = np.zeros((h, w, 3), np.uint8)
    t = np.linspace(0, 1, h)[:, None]
    px[..., 0] = (60 + 180 * t).astype(np.uint8)
    px[..., 1] = (90 + 60 * t).astype(np.uint8)
    px[..., 2] = (200 - 40 * t).astype(np.uint8)
    im = Image.fromarray(px)
    d = ImageDraw.Draw(im)
    d.ellipse((w * 0.68, h * 0.12, w * 0.82, h * 0.36), fill=(250, 210, 90))
    d.polygon([(0, h * 0.75), (w * 0.4, h * 0.55), (w, h * 0.8), (w, h), (0, h)], fill=(60, 130, 70))
    d.rectangle((w * 0.6, h * 0.62, w * 0.72, h * 0.85), fill=(30, 30, 50))
    rng = np.random.default_rng(seed)
    for _ in range(40):
        x, y = rng.integers(0, w), rng.integers(int(h * 0.8), h)
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(20, 60, 30))
    return im


def project(tmp_path: Path, spec: dict) -> Project:
    root = tmp_path / "site"
    root.mkdir(parents=True, exist_ok=True)
    (root / "site.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    return Project(root)


def spec(**extra) -> dict:
    return {"name": "Test", "theme": {"preset": "paper", "from": {"mode": "light", "colors": BRAND}},
            "sections": [{"type": "intro", "title": "Hello"}], **extra}


# ---------------------------------------------------------------- the spec

def test_the_spec_takes_named_media_and_keeps_words():
    assert Imagery(medium="risograph").medium == "risograph"
    assert Imagery(medium="35mm film photograph, Kodak Portra 400").medium.startswith("35mm")      # words as before
    assert ImageInput(generate="x", medium="Watercolor").medium == "watercolour"                 # alias, any case
    assert ImageInput(generate="x", medium="riso").medium == "risograph"
    assert ImageInput(generate="x", medium="None").medium == "none"
    assert ImageInput(generate="x", calm="left").calm == "left"
    with pytest.raises(ValidationError, match="not a named medium"):
        ImageInput(generate="x", medium="oil on canvas")
    with pytest.raises(ValidationError):
        ImageInput(generate="x", calm="middle")
    assert Imagery(medium="toile", inks=["accent", "#123"], paper="bg", grain=0.2).inks == ["accent", "#123"]
    for bad in (dict(inks=["red; x"]), dict(inks=["#12345"]), dict(paper="url(x)"), dict(grain=2),
                dict(inks=["accent"] * 5)):
        with pytest.raises(ValidationError):
            Imagery(medium="toile", **bad)
    assert set(MEDIUM_NAMES) == set(medium.RECIPES)


def test_unset_fields_stay_out_of_dumps_so_old_pages_and_caches_are_unchanged():
    d = ImageInput(generate="x").model_dump(mode="json")
    assert "medium" not in d and "calm" not in d
    assert ImageInput(generate="x", medium="ink", calm="right").model_dump(mode="json")["calm"] == "right"
    site = Site.model_validate({"name": "a", "sections": [{"type": "hero", "title": "t", "image": {"generate": "x"}}]})
    assert "medium" not in site.model_dump_json()


# ---------------------------------------------------------------- inks from the brand

def test_inks_come_from_the_brand():
    riso = medium.palette("risograph", BRAND)
    assert riso["inks"] == [medium.rgb(BRAND["accent"]), medium.rgb(BRAND["accent2"])]
    assert riso["paper"] == medium.rgb(BRAND["bg"])                                      # a pale background is the paper
    toile = medium.palette("toile", BRAND)
    assert toile["inks"] == [medium.rgb(BRAND["accent"])]                                 # a blue toile for a blue brand
    assert medium.palette("engraving", BRAND)["inks"] == [medium.rgb(BRAND["ink"])]
    assert medium.palette("halftone", BRAND)["inks"] == [medium.rgb(BRAND["ink"]), medium.rgb(BRAND["accent"])]


def test_a_second_ink_too_close_to_the_first_is_a_riso_ink_far_from_it():
    pal = medium.palette("risograph", dict(BRAND, accent2="#3355dd"))
    assert pal["inks"][1] in medium.RISO_INKS.values()
    assert medium._hue_gap(pal["inks"][1], pal["inks"][0]) >= 90
    assert medium.palette("risograph", {k: v for k, v in BRAND.items() if k != "accent2"})["inks"][1] in medium.RISO_INKS.values()


def test_a_pale_ink_is_darkened_until_line_work_shows_and_a_dark_site_prints_on_paper():
    pale = medium.palette("toile", dict(BRAND, accent="#a8c4ff"))
    assert medium.contrast(pale["inks"][0], pale["paper"]) >= 3.0
    dark = medium.palette("engraving", {"bg": "#101418", "ink": "#eef0f2", "accent": "#7fd"})
    assert dark["paper"] == medium.rgb("#eef0f2") and dark["inks"] == [medium.rgb("#101418")]   # light text is the paper
    murky = medium.palette("toile", {"bg": "#3a3a3a", "ink": "#777777", "accent": "#2f4fd8"})
    assert murky["paper"] == medium.PAPER                                                # neither is a paper: off-white


def test_inks_and_paper_can_be_set_by_role_or_hex():
    pal = medium.palette("risograph", BRAND, inks=["ink", "#ff8800"], paper="bg2")
    assert pal["inks"] == [medium.rgb(BRAND["ink"]), (255, 136, 0)] and pal["paper"] == medium.rgb(BRAND["bg2"])


def test_the_palette_is_the_resolved_theme_with_imagery_over_it(tmp_path):
    p = project(tmp_path, spec(imagery={"medium": "risograph", "inks": ["accent2", "accent"]}))
    im, named = imagery.look(p)
    assert named == "risograph"
    pal = medium.site_palette(p, named, im)
    assert pal["inks"] == [medium.rgb(BRAND["accent2"]), medium.rgb(BRAND["accent"])]


# ---------------------------------------------------------------- the prompt

def test_every_medium_says_its_recipe_with_the_inks_in_words():
    for name in MEDIUM_NAMES:
        pal = medium.palette(name, BRAND)
        head = medium.prompt_head(name, pal)
        assert "{" not in head and "no text" in head, name
        assert medium.colour_word(pal["inks"][0]) in head, name
    assert "cobalt blue and fluorescent pink" in medium.prompt_head("risograph", medium.palette("risograph", BRAND))
    assert "printed in cobalt blue on warm cream cotton" in medium.prompt_head("toile", medium.palette("toile", BRAND))


def test_colour_words():
    assert medium.colour_word("#16203a") == "navy"
    assert medium.colour_word("#2f4fd8") == "cobalt blue"
    assert medium.colour_word("#f6f1e7") == "warm cream"
    assert medium.colour_word("#ff48b0") == "fluorescent pink"
    assert medium.colour_word("#111111") == "black"


def test_treated_prompts(tmp_path):
    p = project(tmp_path, spec(imagery={"medium": "risograph", "mood": "breezy"}))
    ref = ImageInput(generate="A kite over rooftops, photorealistic, golden hour", calm="left")
    out = treated_prompt(p, ref)
    assert out.startswith("Risograph print illustration, two-colour riso print in cobalt blue and fluorescent pink")
    assert "A kite over rooftops" in out and "photorealistic" not in out
    assert medium.CALM_WORDS["left"] in out and out.rstrip(".").endswith("breezy")
    toile = treated_prompt(p, ImageInput(generate="A bridge", medium="toile"))
    assert toile.startswith("Toile de Jouy") and "breezy" in toile                      # the image's medium wins
    plain = treated_prompt(p, ImageInput(generate="A bridge", medium="none"))
    assert plain == "A bridge. breezy."                                                # out of the named medium
    clip = imagery.treat(p, "A kite", video=True, calm="left")
    assert medium.CALM_WORDS["left"] not in clip                                       # a clip has no headline side


def test_old_specs_send_the_same_prompts(tmp_path):
    words = {"medium": "35mm film photograph, fine grain", "light": "low sun", "palette": "honey and sea blue"}
    p = project(tmp_path, spec(imagery=words))
    assert treated_prompt(p, ImageInput(generate="A cup")) == \
        "35mm film photograph, fine grain. A cup. low sun. honey and sea blue."
    q = project(tmp_path / "b", spec())
    assert treated_prompt(q, ImageInput(generate="A cup, golden hour")) == "A cup, golden hour"
    assert imagery.treat_shot(q, {"keyframes": {"frames": [{"prompt": "x"}]}}) == {"keyframes": {"frames": [{"prompt": "x"}]}}


def test_a_take_is_phrased_in_the_named_medium(tmp_path):
    p = project(tmp_path, spec(imagery={"medium": "ink"}))
    shot = imagery.treat_shot(p, {"keyframes": {"frames": [{"prompt": "A heron"}]}, "ltx": {"prompt": "it flies"}})
    assert shot["keyframes"]["frames"][0]["prompt"].startswith("Brush and ink drawing")
    assert shot["ltx"]["prompt"].startswith("Brush and ink drawing")


def test_which_images_a_medium_reaches(tmp_path):
    p = project(tmp_path, spec(imagery={"medium": "gouache"}))
    assert art_direction(p, ImageInput(generate="x"))[0] == "gouache"
    assert art_direction(p, ImageInput(file="inputs/photo.jpg"))[0] is None              # your photo is left alone
    assert art_direction(p, ImageInput(file="inputs/photo.jpg", medium="ink"))[0] == "ink"   # unless it asks
    assert art_direction(p, ImageInput(generate="x", medium="none"))[0] is None
    q = project(tmp_path / "b", spec(imagery={"medium": "a watercolour sketch, loose"}))   # words: no recipe
    assert art_direction(q, ImageInput(generate="x"))[0] is None


def test_a_hero_in_a_named_medium_keeps_its_headline_side_calm(tmp_path):
    p = project(tmp_path, spec(imagery={"medium": "risograph"}))
    left = HeroBlock(title="t", align="left", image={"generate": "x"})
    assert hero_image(p, left)[1] == "left"
    assert hero_image(p, HeroBlock(title="t", image={"generate": "x"}))[1] == "center"
    assert hero_image(p, HeroBlock(title="t", align="left", image={"generate": "x", "calm": "right"}))[1] == "right"
    assert hero_image(p, HeroBlock(title="t", align="left", image="inputs/a.jpg"))[1] is None
    q = project(tmp_path / "b", spec())
    assert hero_image(q, left) == (left.image, None)                                     # no medium: as before


# ---------------------------------------------------------------- the post-processes

@pytest.mark.parametrize("name", MEDIUM_NAMES)
def test_every_medium_is_deterministic_and_keeps_the_size(name):
    pal = medium.palette(name, BRAND)
    a = medium.apply(fixture(), name, pal, seed=4)
    b = medium.apply(fixture(), name, pal, seed=4)
    assert a.size == fixture().size and a.mode == "RGB"
    assert a.tobytes() == b.tobytes()
    assert a.tobytes() != medium.apply(fixture(), name, pal, seed=5).tobytes() or name in ("gouache", "watercolour") \
        and medium.RECIPES[name].grain == 0


def test_risograph_prints_two_inks_and_their_overprint_only():
    pal = medium.palette("risograph", BRAND)
    out = np.asarray(medium.apply(fixture(), "risograph", pal, grain=0)).reshape(-1, 3)
    colours = {tuple(c) for c in np.unique(out, axis=0)}
    assert len(colours) <= 4                                         # paper, ink A, ink B, A over B
    p, a, b = (np.array(c, float) / 255 for c in (pal["paper"], *pal["inks"]))
    states = {tuple(np.round(255 * v).astype(int)) for v in (p, p * a, p * b, p * a * b)}
    assert all(min(np.abs(np.array(c) - np.array(s)).max() for s in states) <= 1 for c in colours)
    assert len(colours) >= 3                                         # both inks are used on this picture


def test_risograph_grain_and_misregistration():
    pal = medium.palette("risograph", BRAND)
    flat = Image.new("RGB", (400, 240), medium.hexc(BRAND["accent"]))
    ImageDraw.Draw(flat).rectangle((150, 80, 250, 160), fill=medium.hexc(BRAND["accent2"]))
    out = np.asarray(medium.apply(flat, "risograph", pal), np.float32) / 255
    blue = out[20:60, 20:120].reshape(-1, 3)
    assert np.abs(blue.mean(0) - np.array(pal["inks"][0]) / 255 * np.array(pal["paper"]) / 255).max() < 0.08
    assert blue.std(0).max() > 0.004                                  # grain and paper, not a flat fill
    # the pink drum is off register: its square is shifted against where it was drawn
    pink = (out[..., 0] > 0.8) & (out[..., 2] < 0.75)
    ys, xs = np.nonzero(pink)
    assert abs(xs.mean() - 200) + abs(ys.mean() - 120) > 0.3


def test_toile_and_engraving_print_one_ink_on_paper():
    for name in ("toile", "engraving"):
        pal = medium.palette(name, BRAND)
        out = np.asarray(medium.apply(fixture(), name, pal, grain=0), np.float32).reshape(-1, 3)
        paper, ink = np.array(pal["paper"], float), np.array(pal["paper"], float) * np.array(pal["inks"][0]) / 255
        seg = ink - paper
        t = np.clip(((out - paper) @ seg) / (seg @ seg), 0, 1)
        off = np.linalg.norm(out - (paper + t[:, None] * seg), axis=1)
        assert off.max() <= 2.5, name                                 # every pixel is paper, ink, or between
        assert t.min() < 0.05 and t.max() > 0.9, name                 # with real paper and real ink in it


def test_halftone_is_a_dot_screen_of_the_set_period():
    pal = {"paper": (255, 255, 255), "inks": [(0, 0, 0)]}
    grey = np.full((256, 256), 0.35, np.float32)
    dots = medium.screen(grey, 8.0, 0.0)
    spec_ = np.abs(np.fft.rfft(dots.mean(0) - dots.mean()))
    assert round(256 / int(np.argmax(spec_))) == 8                    # one dot every 8 px
    assert abs(dots.mean() - 0.35) < 0.08                            # dot area is the tone
    img = np.full((240, 420, 3), 110 / 255, np.float32)
    out = medium.halftone(img, dict(pal, inks=[(0, 0, 0), (255, 0, 0)]), grain=0, period=8) * 255
    assert ((out < 40).all(-1).mean() > 0.1) and ((out > 215).all(-1).mean() > 0.1)   # ink dots on bare paper
    assert medium.screen(np.zeros((32, 32), np.float32), 8, 45).max() < 0.5          # no tone, no dots


def test_ink_is_black_line_work_with_washes_in_the_accent():
    pal = medium.palette("ink", BRAND)
    out = np.asarray(medium.apply(fixture(), "ink", pal, grain=0), np.float32) / 255
    assert out.min() < 0.25                                            # the dark ink
    acc = np.array(pal["inks"][1]) / 255
    hue = out[..., 2] - out[..., 0]                                    # the cobalt wash is bluer than the paper
    assert hue.max() > 0.15 and acc[2] > acc[0]


DEEP = {"bg": "#16142b", "ink": "#efe7da", "accent": "#ff7a59", "accent2": "#8fb8ff"}


@pytest.mark.parametrize("name", ["halftone", "engraving", "toile", "ink", "risograph"])
def test_light_inks_on_a_dark_paper_print_a_negative(name):
    """`imagery.paper: bg` on a dark site with light inks: the inks cover the paper where the picture is light (opaque,
    as a screen print on dark stock), instead of multiplying into it and vanishing."""
    pal = medium.palette(name, DEEP, inks=["ink", "accent"], paper="bg")
    assert medium.negative(pal) and pal["paper"] == medium.rgb(DEEP["bg"])
    img = Image.new("RGB", (480, 272), (8, 8, 12))
    ImageDraw.Draw(img).ellipse((300, 40, 420, 160), fill=(250, 248, 240))         # a white moon on a black sky
    out = np.asarray(medium.apply(img, name, pal, grain=0), np.float32)
    sky, moon = out[200:260, 20:200].reshape(-1, 3).mean(0), out[80:120, 340:380].reshape(-1, 3).mean(0)
    paper = np.array(pal["paper"], np.float32)
    assert np.abs(sky - paper).max() < 12, name                      # the dark of the picture is the bare paper
    assert medium._lum(tuple(moon)) > medium._lum(tuple(paper)) * 8 and moon.min() > 150, name   # its light is the light ink


def test_a_light_paper_prints_as_it_always_did():
    pal = medium.palette("halftone", BRAND)
    assert not medium.negative(pal)
    layers = [(np.full((4, 4), 0.5, np.float32), pal["inks"][0])]
    want = np.array(pal["paper"], np.float32) / 255 * (1 - 0.5 * (1 - np.array(pal["inks"][0], np.float32) / 255))
    assert np.allclose(medium._print(pal["paper"], layers)[0, 0], want)


def test_gouache_and_watercolour_lean_toward_the_brand():
    from skimage.color import rgb2lab
    for name in ("gouache", "watercolour"):
        pal = medium.palette(name, BRAND)
        src = np.asarray(fixture(), np.float32) / 255
        out = np.asarray(medium.apply(fixture(), name, pal, grain=0), np.float32) / 255
        targets = rgb2lab(np.array([[c for c in [*pal["inks"], pal["paper"]]]], np.float32) / 255)[0]

        def near(img):
            lab = rgb2lab(img).reshape(-1, 3)
            return np.sqrt(((lab[:, None] - targets[None]) ** 2).sum(-1)).min(1).mean()
        assert near(out) < near(src), name


def test_watercolour_paper_shows_through():
    pal = medium.palette("watercolour", BRAND)
    img = Image.new("RGB", (1200, 800), "white")
    ImageDraw.Draw(img).ellipse((400, 200, 800, 600), fill=(80, 120, 200))
    out = np.asarray(medium.apply(img, "watercolour", pal, grain=0))
    assert tuple(out[10, 10]) == pal["paper"]                          # white is the paper
    ring = out[400, 405].astype(int).sum(), out[400, 600].astype(int).sum()
    assert ring[0] < ring[1]                                           # pigment pools at the edge of a wash


def test_a_drawn_paper_margin_is_cut_away_but_a_pale_sky_is_kept():
    framed = Image.new("RGB", (400, 240), (240, 236, 228))
    ImageDraw.Draw(framed).rectangle((20, 16, 380, 224), fill=(40, 80, 200))
    out = medium.trim_margin(np.asarray(framed, np.float32) / 255)
    assert out.shape == (240, 400, 3) and out[0, 0, 2] > 0.7 and out[0, 0, 0] < 0.3       # blue to the edge now
    sky = Image.new("RGB", (400, 240), (235, 240, 250))
    ImageDraw.Draw(sky).rectangle((0, 180, 400, 240), fill=(60, 120, 60))
    arr = np.asarray(sky, np.float32) / 255
    assert np.array_equal(medium.trim_margin(arr), arr)


# ---------------------------------------------------------------- composition

def calm_left(w=640, h=360) -> Image.Image:
    im = Image.new("RGB", (w, h), (46, 80, 200))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(3)
    for _ in range(160):                                               # a town on the right
        x, y = rng.integers(w // 2 + 20, w), rng.integers(0, h)
        d.rectangle((x, y, x + rng.integers(6, 30), y + rng.integers(6, 30)), fill=tuple(int(v) for v in rng.integers(0, 255, 3)))
    return im


def test_calm_and_busy():
    im = calm_left()
    ok, score = medium.calm(im, "left")
    assert ok and score < 0.02
    ok, score = medium.calm(im, "right")
    assert not ok and score > 0.2
    band = Image.new("RGB", (640, 360), (46, 80, 200))
    ImageDraw.Draw(band).rectangle((0, 180, 640, 360), fill=(255, 140, 170))       # one hard band under the words
    assert not medium.calm(band, "left")[0]
    grain = np.clip(np.asarray(Image.new("RGB", (1920, 1088), (46, 80, 200)), np.float32) / 255
                    + np.random.default_rng(1).normal(0, 0.08, (1088, 1920, 3)), 0, 1)
    assert medium.calm(grain, "left")[0]                               # paper grain is a tone, not detail
    assert medium.tone(im, "left") == "dark" and medium.tone(Image.new("RGB", (64, 64), "#f6f1e7"), "left") == "light"


def test_finish_mirrors_or_regenerates_until_the_side_is_calm(tmp_path):
    p = project(tmp_path, spec())
    busy_left = calm_left().transpose(Image.FLIP_LEFT_RIGHT)
    src = p.root / "busy.png"
    busy_left.save(src)
    logs = []
    out = medium.finish(p, src, None, None, 7, None, "left", regenerate=lambda k: src, log=logs.append)
    assert medium.calm(Image.open(out), "left")[0]
    assert (out.with_suffix(".json")).read_text().count('"mirrored": true') == 1
    # top/bottom cannot be mirrored: the next seeds are asked for, the calm one wins
    noisy = calm_left()
    noisy.paste(noisy.crop((320, 0, 640, 360)), (0, 0))                # busy everywhere
    assert not medium.calm(noisy, "top")[0]
    noisy.save(p.root / "noisy.png")
    flat = p.root / "flat.png"
    Image.new("RGB", (640, 360), (40, 60, 180)).save(flat)
    asked = []
    out = medium.finish(p, p.root / "noisy.png", None, None, 7, None, "top",
                        regenerate=lambda k: asked.append(k) or flat, log=logs.append)
    assert asked == [1] and np.asarray(Image.open(out)).reshape(-1, 3).std(0).max() < 1
    # a file is only checked: it stays as it is and the build says so
    logs.clear()
    out = medium.finish(p, src, None, None, 7, None, "left", log=logs.append)
    assert Image.open(out).tobytes() == busy_left.tobytes() and "busy" in logs[0]
    # and the result is cached: asked again, nothing is regenerated
    assert medium.finish(p, p.root / "noisy.png", None, None, 7, None, "top",
                         regenerate=lambda k: pytest.fail("regenerated"), log=logs.append).exists()


def test_a_file_in_a_medium_resolves_through_the_recipe(tmp_path):
    p = project(tmp_path, spec())
    (p.root / "inputs").mkdir()
    fixture().save(p.root / "inputs" / "a.png")
    out = resolve_image(p, ImageInput(file="inputs/a.png", medium="toile"), log=lambda m: None)
    assert out.name.startswith("med_") and out.parent == p.build / "_generated"
    assert resolve_image(p, ImageInput(file="inputs/a.png"), log=lambda m: None).name == "a.png"


# ---------------------------------------------------------------- illustrated feature cards

def test_feature_cards_take_an_illustration_in_the_medium(tmp_path):
    from engine.plan import image_refs
    from engine.spec import Feature
    assert "image" not in Feature(title="Plain").model_dump()          # old pages dump as they did
    p = project(tmp_path, spec(sections=[{"type": "features", "title": "Three things", "items": [
        {"title": "One", "body": "First.", "image": {"file": "inputs/a.png", "medium": "risograph"}},
        {"title": "Two", "body": "Second.", "image": {"file": "inputs/a.png", "medium": "risograph"}},
        {"title": "Three", "body": "Third."}]}]))
    (p.root / "inputs").mkdir()
    fixture().save(p.root / "inputs" / "a.png")
    sec = p.load().sections[0]
    assert [r[0] for r in image_refs(sec)] == ["card 1", "card 2"]
    logs = []
    html = compiler.build_site(p, log=logs.append).read_text(encoding="utf-8")
    assert html.count('class="ss-feature__art"') == 2 and html.count("ss-feature--art") == 3
    assert sum("medium: risograph" in m for m in logs) == 1             # the same file is printed once, then cached
    plain = project(tmp_path / "plain", spec(sections=[{"type": "features", "items": [{"title": "One"}]}]))
    assert "ss-feature__art" not in compiler.build_site(plain, log=lambda m: None).read_text(encoding="utf-8")


# ---------------------------------------------------------------- the example

def test_the_example_builds_on_the_cpu_in_its_media(tmp_path):
    root = tmp_path / "kitewell"
    shutil.copytree(ROOT / "examples" / "kitewell", root, ignore=shutil.ignore_patterns(".build", "dist", "snapshots"))
    p = Project(root)
    site = p.load()
    assert site.imagery.medium == "risograph" and site.theme.from_.colors["accent"] == "#2f4fd8"
    logs = []
    html = compiler.build_site(p, log=logs.append).read_text(encoding="utf-8")
    assert "ss-hero--calm ss-hero--calm-left" in html and "ss-surface-dark ss-hero--media" in html
    assert "ss-product__img--plate" in html
    assert any("composition: left side calm" in m for m in logs)
    assert any("medium: toile in #2f4fd8 on #f6f1e7" in m for m in logs)
    assert sum("medium: risograph" in m for m in logs) == 2
    for name in ("hero.jpg", "product.jpg", "band.jpg"):
        assert (root / "inputs" / name).stat().st_size < 1_500_000
