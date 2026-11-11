"""Product page import, ad concepts, ad variations and resolution tiers, listings per language, vertical video ads
and the edit pass. Backends are stubs; no network, no GPU. ffmpeg makes the small test videos."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from PIL import Image

from engine import ads, concepts, editpass, listing, productpage, ugc
from engine.project import BuildError, Project, ffmpeg, probe
from engine.router import core
from engine.router.core import Result
from engine.stills import run as stills
from test_stills import product_photo, project

PAGE = """<html><head><title>Fern Planter | Shop</title>
<meta property="og:title" content="Fern Planter">
<meta property="og:image" content="/img/og.jpg">
<meta name="description" content="A glazed planter for small plants.">
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
  {"@type": "Organization", "name": "Shop"},
  {"@type": "Product", "name": "Fern Planter", "description": "Hand-glazed stoneware, 12 cm.",
   "brand": {"@type": "Brand", "name": "Greenhouse"}, "image": ["https://shop.test/img/1.jpg", {"url": "/img/2.jpg"}],
   "offers": [{"@type": "Offer", "price": "24.00", "priceCurrency": "EUR"}],
   "aggregateRating": {"ratingValue": "4.8", "reviewCount": "112"},}
]}</script></head>
<body><h1>Fern Planter</h1><p>Hand-glazed stoneware with a drainage hole, made for ferns and herbs.</p>
<ul><li>12 cm across</li><li>Drainage hole and saucer</li></ul></body></html>"""


@pytest.fixture(autouse=True)
def no_backends(monkeypatch):
    monkeypatch.setattr(core, "backends", lambda: [])
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)


def with_outputs(p: Project, languages=None, **outputs) -> Project:
    data = yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))
    data["outputs"].update(outputs)
    if languages:
        data["languages"] = languages
    p.spec_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


class Stub:
    """A backend that does whatever kinds it is given, without a model."""
    local = True

    def __init__(self, name, kinds, text=None):
        self.name, self.kinds, self.text, self.prompts = name, tuple(kinds), text, []

    def available(self):
        return True, ""

    def model(self, kind):
        return "stub"

    def run(self, job, out, model=None):
        if job.kind == "text":
            self.prompts.append(job.prompt)
            return Result(self.name, "stub", 0.0, text=self.text(job.prompt) if callable(self.text) else self.text)
        if job.kind == "edit":
            Image.open(job.images[0]).convert("RGB").resize((200, 300)).save(out)
            return Result(self.name, "stub", 0.0, path=out)
        if job.kind == "speech":
            ffmpeg("-f", "lavfi", "-i", "sine=frequency=330:duration=3", "-c:a", "libmp3lame", out)
            return Result(self.name, "stub", 0.0, path=out)
        raise TypeError(job.kind)


# ---------------------------------------------------------------- product page import

def test_facts_read_schema_org_and_open_graph():
    f = productpage.facts(PAGE, "https://shop.test/products/fern")
    assert f["name"] == "Fern Planter" and f["brand"] == "Greenhouse"
    assert (f["price"], f["currency"]) == ("24.00", "EUR") and (f["rating"], f["reviews"]) == ("4.8", "112")
    assert f["images"] == ["https://shop.test/img/1.jpg", "https://shop.test/img/2.jpg", "https://shop.test/img/og.jpg"]


def test_profile_parse_and_the_draft():
    with pytest.raises(ValueError):
        productpage.parse_profile('{"name": ""}')
    got = productpage.parse_profile('x {"name": "Fern", "features": ["a", 3, ""], "price": "24"} y')
    assert got["features"] == ["a", "3"] and got["objections"] == []
    d = productpage.plain_profile(productpage.facts(PAGE, "https://shop.test/p"), "")
    assert d["draft"] and d["proof"] == ["rated 4.8 from 112 reviews"] and d["price"] == "EUR 24.00"


def test_import_writes_a_project_with_pictures_and_a_profile(tmp_path, monkeypatch):
    import io

    import requests
    from engine import remake
    photo = product_photo(tmp_path / "p.png")
    big = Image.open(photo).resize((600, 720))
    buf = io.BytesIO()
    big.save(buf, "JPEG")

    class R:
        headers = {"content-type": "image/jpeg"}
        raw = None

        def __init__(self):
            self.raw = io.BytesIO(buf.getvalue())
            self.raw.read = lambda n=-1, decode_content=True, _r=self.raw: io.BytesIO.read(_r, n)

        def raise_for_status(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(remake, "read_page", lambda url, browser, log: (PAGE, url))
    monkeypatch.setattr(remake.Robots, "allowed", lambda self, url: True)
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    r = productpage.import_product("https://shop.test/products/fern", languages=["en", "es"], projects=tmp_path,
                                   log=lambda m: None)
    root = Path(r["path"])
    doc = yaml.safe_load((root / "project.yaml").read_text(encoding="utf-8"))
    assert r["name"] == "fern-planter" and doc["source"] == "https://shop.test/products/fern"
    assert doc["languages"] == ["en", "es"] and doc["outputs"]["stills"]["photo"] == "inputs/product-1.jpg"
    assert set(doc["outputs"]) >= {"stills", "ads", "listing", "concepts", "ugc"}
    assert len(r["pictures"]) == 3 and (root / "profile" / "profile.md").exists()
    assert r["profile"]["draft"] and r["profile"]["facts"]["brand"] == "Greenhouse"
    with pytest.raises(BuildError, match="already exists"):
        productpage.import_product("https://shop.test/products/fern", projects=tmp_path, log=lambda m: None)
    with pytest.raises(BuildError, match="http"):
        productpage.import_product("shop.test/fern", projects=tmp_path, log=lambda m: None)


def test_robots_refusal_writes_nothing(tmp_path, monkeypatch):
    from engine import remake
    monkeypatch.setattr(remake.Robots, "allowed", lambda self, url: False)
    with pytest.raises(remake.Refused):
        productpage.import_product("https://shop.test/products/fern", projects=tmp_path, log=lambda m: None)
    assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------- concepts

def concept_answer(prompt: str) -> str:
    lang = "es" if "Spanish" in prompt else "en"
    n = prompt.count(": ") and int(prompt.split("Write ", 1)[1].split(" ", 1)[0])
    return json.dumps({"concepts": [{"angle": "x", "hook": f"hook {lang} {i}", "headline": f"Head {lang} {i}",
                                     "cta": "Shop", "lines": ["one", "two", "three"],
                                     "script": f"say {lang} {i} " * 6} for i in range(n)]})


def test_concepts_draft_without_a_text_backend(tmp_path):
    p = with_outputs(project(tmp_path), languages=["en", "de"], concepts={"count": 3})
    r = concepts.make(p, log=lambda m: None)
    assert [c["angle"] for c in r["concepts"]] == ["benefit", "problem", "proof"]
    assert all(c["copy"]["en"]["draft"] and "de" in c["copy"] for c in r["concepts"])
    assert (p.root / "concepts" / "concepts.md").exists() and r["source"] == "draft"


def test_concepts_are_written_natively_per_language(tmp_path, monkeypatch):
    w = Stub("writer", ["text"], concept_answer)
    monkeypatch.setattr(core, "backends", lambda: [w])
    p = with_outputs(project(tmp_path), languages=["en", "es"], concepts={"count": 2, "angles": ["gift"]})
    r = concepts.make(p, log=lambda m: None)
    assert len(w.prompts) == 2 and "Do not translate" in w.prompts[1] and "Spanish" in w.prompts[1]
    assert "Never invent" in w.prompts[0]
    assert r["concepts"][1]["copy"]["es"]["headline"] == "Head es 1" and r["concepts"][0]["angle"] == "gift"
    with pytest.raises(ValueError):
        concepts.parse('{"concepts": [{"headline": "h", "script": "s"}]}', 2)


def test_languages_are_codes():
    from engine.project_spec import ProjectSpec
    with pytest.raises(ValueError):
        ProjectSpec(name="x", languages=["Spanish"])
    assert ProjectSpec(name="x", languages=["es", "es", "pt-BR"]).languages == ["es", "pt-BR"]


# ---------------------------------------------------------------- ads and listing

def made_stills(p: Project) -> Project:
    stills.make(p, log=lambda m: None)
    return p


def test_ads_make_one_variation_per_concept_and_language_at_2k(tmp_path):
    p = with_outputs(project(tmp_path, shots=["packshot"]), languages=["en", "es"], concepts={"count": 2},
                     ads={"sizes": ["1x1", "9x16"], "shots": ["packshot"], "resolution": "2k"})
    made_stills(p)
    concepts.make(p, log=lambda m: None)
    r = ads.make(p, log=lambda m: None)
    assert len(r["ads"]) == 1 * 2 * 2 * 2
    names = {a["file"] for a in r["ads"]}
    assert "packshot-1x1-c1.en.png" in names and "packshot-9x16-c2.es.png" in names
    a = r["ads"][0]
    assert a["width"] == 2048 and a["upscaled_from"] == 320 and a["concept"] == "c1"
    assert Image.open(p.root / "ads" / a["file"]).width == 2048


def test_ads_without_concepts_keep_their_names(tmp_path):
    p = with_outputs(project(tmp_path, shots=["packshot"]), ads={"sizes": ["1x1"], "shots": ["packshot"],
                                                                 "headline": "Hi", "width": 320})
    made_stills(p)
    assert [a["file"] for a in ads.make(p, log=lambda m: None)["ads"]] == ["packshot-1x1.png"]


def test_listing_in_each_language(tmp_path):
    p = with_outputs(project(tmp_path), languages=["en", "fr"], listing={"bullets": 2})
    r = listing.make(p, log=lambda m: None)
    assert set(r["languages"]) == {"en", "fr"}
    assert (p.root / "listing" / "listing.en.json").exists() and (p.root / "listing" / "listing.fr.md").exists()


# ---------------------------------------------------------------- video ads

def test_captions_chunk_and_time():
    assert ugc.chunks("one two three four five") == ["one two three", "four five"]
    jp = "これは素晴らしい商品です毎日使えます"                 # written without spaces: chunked by characters
    assert [len(c) for c in ugc.chunks(jp)] == [8, 8, 2] and "".join(ugc.chunks(jp)) == jp
    t = ugc.timings(["aa", "aaaa"], 3.0)
    assert t == [(0.0, 1.0), (1.0, 3.0)]


def test_ugc_needs_concepts_first(tmp_path):
    p = with_outputs(project(tmp_path), ugc={})
    with pytest.raises(BuildError, match="studio concepts"):
        ugc.make(p, log=lambda m: None)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_ugc_makes_a_video_per_concept_and_language(tmp_path, monkeypatch):
    p = with_outputs(project(tmp_path, shots=["packshot", "lifestyle"]), languages=["en", "es"],
                     concepts={"count": 2, "seconds": 6}, ugc={"concepts": 1, "width": 240, "presenter_seconds": 2})
    made_stills(p)
    concepts.make(p, log=lambda m: None)
    s = Stub("studio", ["edit", "speech"])
    monkeypatch.setattr(core, "backends", lambda: [s])
    r = ugc.make(p, log=lambda m: None)
    files = sorted(v["file"] for v in r["videos"])
    assert files == ["c1.en.mp4", "c1.es.mp4"]
    v = r["videos"][0]
    assert v["presenter"] == "presenter by studio" and "push-in" in v["presenter_clip"] and v["voice"].startswith("voice by")
    info = probe(p.root / "ugc" / "c1.en.mp4")
    assert (int(info["width"]), int(info["height"])) == (240, 426) and float(info["duration"]) == pytest.approx(6, abs=0.4)
    assert json.loads((p.root / "ugc" / "ugc.json").read_text(encoding="utf-8"))["videos"][1]["language"] == "es"


def test_local_comfy_takes_video_jobs():
    from engine.router.builtin import ComfyBackend
    assert "video" in ComfyBackend.kinds and ComfyBackend().model("video") == "ltx-2.3"


# ---------------------------------------------------------------- the edit pass

def test_edit_writes_next_to_the_picture_or_over_it(tmp_path, monkeypatch):
    p = project(tmp_path)
    with pytest.raises(BuildError, match="no edit backend"):
        editpass.edit(p, "inputs/product.png", "warmer", log=lambda m: None)
    monkeypatch.setattr(core, "backends", lambda: [Stub("editor", ["edit"])])
    e1 = editpass.edit(p, "inputs/product.png", "warmer", log=lambda m: None)
    assert e1["file"] == "inputs/product.edit1.png" and (p.root / e1["file"]).exists()
    e2 = editpass.edit(p, "inputs/product.png", "cooler", replace=True, log=lambda m: None)
    assert e2["file"] == "inputs/product.png" and (p.root / "inputs" / "product.orig.png").exists()
    assert Image.open(p.root / "inputs" / "product.png").size == (200, 300)
    assert [h["instruction"] for h in json.loads((p.root / "edits.json").read_text(encoding="utf-8"))] == ["warmer", "cooler"]
    (p.root / "clip.mp4").write_bytes(b"x")
    with pytest.raises(BuildError, match="is a video"):
        editpass.edit(p, "clip.mp4", "brighter", log=lambda m: None)
    with pytest.raises(BuildError, match="outside the project"):
        editpass.edit(p, "../elsewhere.png", "x", log=lambda m: None)
