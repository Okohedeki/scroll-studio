"""Ads and listing copy (engine/ads.py, engine/listing.py, issue #179): reframing keeps the whole product, the copy
stacks inside its band, and the listing parser and its draft fallback work. Laptop path: no network, no GPU."""
from __future__ import annotations

import json

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

from engine import ads, listing
from engine.project import BuildError
from engine.router import core
from engine.stills import run as stills
from test_stills import project


@pytest.fixture(autouse=True)
def no_backends(monkeypatch):
    monkeypatch.setattr(core, "backends", lambda: [])
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)


def with_outputs(p, **outputs):
    data = yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))
    data["outputs"].update(outputs)
    p.spec_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


@pytest.mark.parametrize("ratio", list(ads.RATIOS.values()))
def test_reframe_keeps_the_whole_product(ratio):
    img = Image.new("RGB", (400, 400), (200, 180, 160))
    mask = Image.new("L", (400, 400), 0)
    ImageDraw.Draw(mask).rectangle((150, 60, 250, 330), fill=255)
    out, m = ads.reframe(img, mask, ratio, 300, keep_bottom=0.3)
    assert out.size == (300, round(300 / ratio))
    area = (np.asarray(m) > 127).sum()
    x0, y0, x1, y1 = ads.mask_box(m)
    assert area > 0 and x0 > 0 and y0 > 0 and x1 < out.width
    assert y1 <= out.height * 0.72                  # above the copy band


def test_extension_has_no_seam():
    img = Image.new("RGB", (100, 100), (120, 140, 160))
    out = ads._crop_extend(img, (-50, 0, 150, 100))
    a = np.asarray(out, np.int16)
    assert np.abs(np.diff(a, axis=1)).max() <= 2


def test_copy_stacks_inside_the_band_at_every_size():
    for ratio in ads.RATIOS.values():
        img = Image.new("RGB", (540, round(540 / ratio)), "white")
        _, layout = ads.set_copy(img, "A long headline that needs to wrap onto two lines", "Shop the range now",
                                 ("#222222", "#ffffff"))
        band, cta = layout["band"], layout["cta"]["box"]
        assert layout["headline"]["bottom"] <= cta[1] and cta[3] <= band[3] and cta[2] <= band[2]


def test_ads_from_the_picked_stills(tmp_path):
    p = project(tmp_path, shots=["packshot", "lifestyle"])
    with_outputs(p, ads={"sizes": ["1x1", "9x16"], "headline": "Hello", "cta": "Shop", "width": 360,
                         "shots": ["lifestyle", "packshot"]})
    with pytest.raises(BuildError, match="studio stills"):
        ads.make(p, log=lambda m: None)
    st = stills.make(p, log=lambda m: None)
    pick = st["shortlist"]["lifestyle"][-1]
    stills.make(p, pick=pick, log=lambda m: None)
    r = ads.make(p, log=lambda m: None)
    assert len(r["ads"]) == 4 and {a["size"] for a in r["ads"]} == {"1x1", "9x16"}
    assert next(a for a in r["ads"] if a["shot"] == "lifestyle")["from"] == pick
    saved = json.loads((p.root / "ads" / "ads.json").read_text(encoding="utf-8"))
    assert Image.open(p.root / "ads" / saved["ads"][0]["file"]).width == 360


def test_listing_draft_without_a_text_backend(tmp_path):
    p = with_outputs(project(tmp_path), listing={"bullets": 4})
    r = listing.make(p, log=lambda m: None)
    assert r["draft"] and r["source"] == "template" and len(r["bullets"]) == 4
    md = (p.root / "listing" / "listing.md").read_text(encoding="utf-8")
    assert md.startswith("# A planter") and "Draft" in md


def test_listing_parse():
    d = listing.parse('ok {"title": "' + "T" * 100 + '", "bullets": ["a", "b"], "description": "d"}', 2, 80)
    assert len(d["title"]) == 80 and d["bullets"] == ["a", "b"]
    with pytest.raises(ValueError):
        listing.parse('{"title": "t", "bullets": ["a"], "description": "d"}', 2, 80)
    with pytest.raises(ValueError):
        listing.parse("nothing", 2, 80)


def test_listing_from_a_text_backend(tmp_path, monkeypatch):
    from engine.router.core import Result

    class Writer:
        name, local, kinds = "writer", False, ("text",)

        def available(self):
            return True, ""

        def model(self, kind):
            return "w"

        def run(self, job, out, model=None):
            assert "never invent" in job.prompt
            return Result("writer", "w", 0.0, text='{"title": "Planter", "bullets": ["Glazed", "Green", "Small", "Light", '
                                                  '"Gift"], "description": "A planter."}')

    monkeypatch.setattr(core, "backends", lambda: [Writer()])
    r = listing.make(with_outputs(project(tmp_path), listing={}), log=lambda m: None)
    assert r["title"] == "Planter" and r["source"] == "writer" and "draft" not in r
