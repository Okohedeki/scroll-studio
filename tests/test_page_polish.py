"""`studio inspect --page` (issue #139): the polish report of a built page. The measurements are checked on pictures drawn
with PIL and on made-up facts, with no browser; the whole check runs on a tiny site built by the real compiler (pictures
drawn on the spot, no fonts downloaded) in headless Chromium, and is skipped where Playwright's Chromium is not installed.
No GPU, no network."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner

from engine import cli
from engine.polish import page as P
from engine.polish import page_metrics as M
from engine.project import Project


def solid(rgb, w=60, h=30) -> np.ndarray:
    return np.full((h, w, 3), rgb, np.uint8)


def noise(w=120, h=60, seed=1) -> np.ndarray:
    return (np.random.default_rng(seed).random((h, w, 3)) * 255).astype(np.uint8)


def ramp(w=120, h=60) -> np.ndarray:
    return np.tile(np.linspace(30, 200, w, dtype=np.float32)[None, :, None], (h, 1, 3)).astype(np.uint8)


# ---------------------------------------------------------------- the measurements

def test_busyness_tells_flat_from_graded_from_noisy():
    flat, graded, busy = M.busyness(solid((90, 90, 90))), M.busyness(ramp()), M.busyness(noise())
    assert flat["score"] == 0 and graded["score"] <= 10, (flat, graded)    # a sky's gradient is not busy
    assert busy["score"] >= 90, busy
    assert flat["score"] < M.BUSY_WARN < busy["score"]


def test_busyness_of_a_picture_with_one_object_sits_between():
    img = solid((60, 60, 60), 160, 80)
    img[20:60, 60:100] = noise(40, 40)
    score = M.busyness(img)["score"]
    assert 10 < score < 90
    assert M.busyness(np.zeros((2, 2, 3), np.uint8))["score"] == 0         # too small to measure


def test_contrast_matches_wcag_reference_values():
    assert M.text_contrast(solid((0, 0, 0)), (255, 255, 255))["typical"] == 21.0
    assert M.text_contrast(solid((255, 255, 255)), (119, 119, 119))["typical"] == pytest.approx(4.48, abs=0.02)   # #777 on white
    assert M.text_contrast(solid((255, 255, 255)), (255, 255, 255))["typical"] == 1.0
    half = M.text_contrast(solid((0, 0, 0)), (255, 255, 255), alpha=0.5)["typical"]     # 50% white over black: grey on black
    assert 5 < half < 9


def test_worst_contrast_finds_the_bright_patch_that_the_typical_value_hides():
    back = solid((10, 10, 10), 100, 20)
    back[:, 70:] = (235, 235, 235)                                         # a tenth-plus of the box is nearly white
    c = M.text_contrast(back, (255, 255, 255))
    assert c["typical"] > 12 and c["worst"] < 1.5


def test_needed_contrast_is_lower_for_large_text():
    assert M.needed_contrast(16) == 4.5 and M.needed_contrast(24) == 3.0
    assert M.needed_contrast(19, 700) == 3.0 and M.needed_contrast(19, 400) == 4.5


def test_the_calmest_side_is_the_side_without_detail():
    img = solid((40, 40, 40), 300, 90)
    img[:, :100] = noise(100, 90)
    sides = M.calmest_side(img, (10, 60))
    assert sides["left"] > M.BUSY_WARN and sides["right"] == 0 and sides["center"] == 0


def test_line_length_is_the_mean_of_the_full_lines():
    assert M.line_length([82, 80, 79, 20]) == 80
    assert M.line_length([40]) is None and M.line_length([]) is None
    assert M.line_length([40, 12]) == 40


def test_upscale_uses_the_fit_and_the_pixel_ratio():
    assert M.upscale((1920, 1080), (1440, 810), 1, "cover") == 0.75
    assert M.upscale((1920, 1080), (390, 844), 2, "cover") == pytest.approx(1.56, abs=0.01)    # a phone crops a wide picture
    assert M.upscale((1920, 1080), (390, 844), 2, "contain") == pytest.approx(0.41, abs=0.01)
    assert M.upscale((100, 100), (300, 300), 1, "fill") == 3.0
    assert M.upscale((100, 100), (300, 300), 2, "none") == 1.0


def test_the_crop_window_follows_cover_and_object_position():
    x0, y0, x1, y1 = M.crop_window((1920, 1080), (390, 844), "cover", (0.5, 0.5))
    assert (y0, y1) == (0.0, 1.0) and x1 - x0 == pytest.approx(390 / 844 * 1080 / 1920, abs=0.01)
    assert (x0 + x1) / 2 == pytest.approx(0.5, abs=0.001)
    left = M.crop_window((1920, 1080), (390, 844), "cover", (0.0, 0.5))
    assert left[0] == 0.0
    assert M.crop_window((1920, 1080), (390, 844), "contain", (0.5, 0.5)) == (0.0, 0.0, 1.0, 1.0)


def test_a_face_cut_by_the_frame_is_partly_inside_it():
    window = (0.3, 0.0, 0.7, 1.0)
    assert M.face_in_frame((0.4, 0.2, 0.5, 0.4), window) == 1.0
    assert M.face_in_frame((0.25, 0.2, 0.35, 0.4), window) == pytest.approx(0.5)
    assert M.face_in_frame((0.0, 0.2, 0.1, 0.4), window) == 0.0
    assert M.face_overlap((10, 10, 20, 20), (15, 0, 40, 40)) == 0.5 and M.face_overlap((10, 10, 20, 20), (30, 0, 40, 40)) == 0.0


def test_a_face_is_placed_on_the_screen_through_the_crop():
    window, rect = (0.25, 0.0, 0.75, 1.0), (0.0, 0.0, 400.0, 800.0)               # the middle half of the picture fills the box
    assert M.face_on_screen((0.4, 0.2, 0.5, 0.3), window, rect) == pytest.approx([120.0, 160.0, 200.0, 240.0])
    assert M.face_on_screen((0.1, 0.2, 0.2, 0.3), window, rect) is None              # outside the frame
    cut = M.face_on_screen((0.2, 0.2, 0.3, 0.3), window, rect)                      # half of it is in
    assert cut[0] == 0.0 and cut[2] == pytest.approx(40.0)


def test_overlap_is_a_share_of_the_smaller_box():
    assert M.overlap((0, 0, 100, 20), (0, 10, 100, 30)) == 0.5
    assert M.overlap((0, 0, 100, 20), (0, 20, 100, 40)) == 0.0
    assert M.overlap((0, 0, 100, 20), (200, 0, 300, 20)) == 0.0


# ---------------------------------------------------------------- the rules

def text(**kw) -> dict:
    t = {"text": "Sleep care built around you", "role": "headline", "size": 64, "weight": 600, "caption": False, "hero": True,
         "section": "hero", "viewport": "desktop", "shot": 0, "box": [10, 10, 300, 80], "busy": 10,
         "contrast": {"typical": 9.0, "worst": 7.0, "backdrop_lum": 0.05}, "raw": None, "calm": {"left": 5, "center": 5, "right": 5},
         "side": "left"}
    t.update(kw)
    return t


def checks(findings):
    return sorted((f["severity"], f["check"]) for f in findings)


def test_text_that_reads_clean_has_no_findings():
    assert M.text_findings(text()) == []


def test_text_that_fails_contrast_says_the_ratio_and_the_need():
    f, = M.text_findings(text(size=17, role="body", contrast={"typical": 2.4, "worst": 2.0, "backdrop_lum": 0.4}))
    assert (f["severity"], f["check"]) == ("fail", "contrast") and "2.4:1" in f["what"] and "4.5:1" in f["what"]
    assert f["section"] == "hero" and f["viewport"] == "desktop" and f["box"] == [10, 10, 300, 80]


def test_large_text_is_held_to_three_and_just_under_is_a_warning():
    assert M.text_findings(text(size=64, contrast={"typical": 3.4, "worst": 3.0, "backdrop_lum": 0.1})) == []
    f, = M.text_findings(text(size=17, role="body", contrast={"typical": 4.2, "worst": 4.0, "backdrop_lum": 0.1}))
    assert (f["severity"], f["check"]) == ("warn", "contrast") and "just under" in f["what"]
    f, = M.text_findings(text(size=17, role="body", contrast={"typical": 6.0, "worst": 2.2, "backdrop_lum": 0.1}))
    assert f["severity"] == "warn" and "brightest or darkest tenth" in f["what"]


def test_a_scrim_that_does_the_work_is_named():
    raw = {"typical": 1.9, "worst": 1.5, "backdrop_lum": 0.7, "shift": 0.4}
    fs = M.text_findings(text(size=17, role="body", contrast={"typical": 5.2, "worst": 4.9, "backdrop_lum": 0.1}, raw=raw))
    assert checks(fs) == [("warn", "scrim")] and "5.2:1 with it" in fs[0]["what"] and "1.9:1" in fs[0]["what"]
    weak = dict(raw, shift=0.02)
    assert M.text_findings(text(size=17, role="body", contrast={"typical": 5.2, "worst": 4.9, "backdrop_lum": 0.1}, raw=weak)) == []


def test_busy_pictures_are_flagged_but_buttons_are_not():
    assert checks(M.text_findings(text(busy=72))) == [("warn", "busy")]
    assert M.text_findings(text(busy=72, role="cta")) == []


def test_the_fix_for_a_caption_names_the_calmer_side_in_the_engines_terms():
    bad = {"typical": 2.0, "worst": 1.5, "backdrop_lum": 0.5}
    fs = M.text_findings(text(caption=True, hero=False, busy=70, side="left", calm={"left": 70, "center": 40, "right": 8}, contrast=bad))
    fix = next(f for f in fs if f["check"] == "contrast")["fix"]
    assert "`place: right`" in fix and "`surface:" in fix and "`shade: strong`" in fix
    same = M.text_findings(text(caption=True, hero=False, busy=70, side="left", calm={"left": 30, "center": 40, "right": 60}, contrast=bad))
    assert "place:" not in next(f for f in same if f["check"] == "contrast")["fix"]       # no calmer side: no false advice


def test_the_fix_for_a_hero_and_for_the_nav_speak_of_the_picture():
    bad = {"typical": 2.0, "worst": 1.5, "backdrop_lum": 0.5}
    hero = M.text_findings(text(busy=70, side="center", calm={"left": 5, "center": 60, "right": 70}, contrast=bad))[0]["fix"]
    assert "calm space" in hero and "`align: left`" in hero and "`surface: dark`" in hero
    right = M.text_findings(text(busy=70, side="center", calm={"left": 60, "center": 60, "right": 5}, contrast=bad))[0]["fix"]
    assert "right third is calmer" in right and "align" not in right
    nav = M.text_findings(text(section="nav", hero=False, contrast=bad))[0]["fix"]
    assert "top of the page" in nav


def test_type_rules():
    body = {"text": "x" * 50, "lines": [95, 96, 40], "nlines": 3, "shot": 1, "box": [0, 0, 5, 5]}
    narrow = {"text": "y" * 50, "lines": [22, 24, 23, 20, 9], "nlines": 5, "shot": 2, "box": [0, 0, 5, 5]}
    short = {"text": "z", "lines": [22, 24, 9], "nlines": 3}
    fs = M.type_findings("intro", "desktop", 20, 17, [body, narrow, short], [])
    assert checks(fs) == [("warn", "hierarchy"), ("warn", "line-length"), ("warn", "line-length")]
    assert sorted(f["what"].split(" runs ")[1].split(" ")[0] for f in fs if f["check"] == "line-length") == ["22", "96"]
    assert M.type_findings("intro", "desktop", 60, 17, [], []) == []

    def head(n):
        return [{"text": "A long headline", "nlines": n, "lines": [10] * n}]
    assert M.type_findings("hero", "phone", 60, 17, [], head(5)) == []
    assert checks(M.type_findings("hero", "phone", 60, 17, [], head(6))) == [("warn", "headline-lines")]
    assert checks(M.type_findings("hero", "phone", 60, 17, [], head(8))) == [("fail", "headline-lines")]
    assert M.type_findings("hero", "desktop", 60, 17, [], head(8)) == []          # lines on a phone only


def test_image_rules():
    im = {"src": "hero.webp", "section": "hero", "viewport": "phone", "natural": [1920, 1088], "box": [406, 878], "dpr": 2.0,
          "fit": "cover", "shot": 0, "rect": [0, 0, 406, 878], "face": None}
    f, = M.image_findings(im)
    assert (f["severity"], f["check"]) == ("warn", "upscaled") and "1.61x" in f["what"] and "`size:" in f["fix"]
    assert "shows only 26% of the picture's width" in f["fix"]
    assert M.image_findings(dict(im, viewport="desktop", box=[1440, 900], dpr=1.0)) == []
    f, = M.image_findings(dict(im, natural=[160, 90], box=[1440, 900], dpr=1.0))
    assert f["severity"] == "fail"
    f, = M.image_findings(dict(im, box=[1440, 900], dpr=1.0, face=0.6))
    assert (f["check"], f["severity"]) == ("face-cut", "warn") and "60%" in f["what"] and "`crop:" in f["fix"]
    assert M.image_findings(dict(im, box=[1440, 900], dpr=1.0, face=1.0)) == []
    assert M.image_findings(dict(im, box=[1440, 900], dpr=1.0, face=0.0)) == []        # a face the frame never shows is not cut


def test_layout_rules():
    over = {"px": 120, "culprits": ["#wide in one (reaches 510 px)"]}
    cta = {"label": "Start your plan", "top": 700.0, "bottom": 760.0, "fold": 844.0, "box": [1, 2, 3, 4]}
    assert M.layout_findings("hero", "phone", 0, None, cta, []) == []
    cut = M.layout_findings("hero", "phone", 0, None, dict(cta, bottom=880.0), [])[0]
    assert (cut["severity"], cut["check"]) == ("warn", "cta-fold") and "cut by the fold" in cut["what"]
    gone = M.layout_findings("hero", "phone", 0, None, dict(cta, top=900.0, bottom=950.0), [])[0]
    assert gone["severity"] == "fail" and "below the fold" in gone["what"]
    fs = M.layout_findings("one", "phone", 3, over, None, [{"a": "Headline", "b": "Paragraph", "share": 0.6, "box": [0, 0, 9, 9]}])
    assert checks(fs) == [("fail", "overflow"), ("fail", "overlap")]
    assert "120 px wider" in fs[0]["what"] and "#wide" in fs[0]["what"] and "60%" in fs[1]["what"]


def test_the_verdict_is_the_worst_finding():
    assert M.verdict([]) == "clean"
    assert M.verdict([{"severity": "warn"}]) == "warn"
    assert M.verdict([{"severity": "warn"}, {"severity": "fail"}]) == "fail"


# ---------------------------------------------------------------- the report's plumbing

def test_stops_are_one_per_position_in_page_order_and_capped():
    plan = {"sections": [
        {"label": "a", "scene": False, "ys": [0, 900, 1800]},
        {"label": "b", "scene": False, "ys": [900]},                     # the same position as a's second: one photograph
        {"label": "c", "scene": False, "ys": [2700, 3600, 4500, 5400, 6300, 7200]},
        {"label": "s", "scene": True, "ys": list(range(9000, 9000 + 12 * 400, 400))}]}
    stops = P._stops(plan, None)
    ys = [s["y"] for s in stops]
    assert ys == sorted(ys) and len(ys) == len(set(ys))
    assert sum("c" in s["sections"] for s in stops) == 4 and sum("s" in s["sections"] for s in stops) == 8
    assert next(s for s in stops if s["y"] == 900)["sections"] == ["a", "b"]
    assert [s["y"] for s in P._stops(plan, "b")] == [900]


def test_line_boxes_are_trimmed_to_the_ink_before_text_is_compared():
    tight = [0, 0, 100, 20], [0, 14, 100, 34]                            # line boxes that touch because the leading is tight
    assert M.overlap(tight[0], tight[1]) > M.OVERLAP_MIN and M.overlap(P._ink(tight[0]), P._ink(tight[1])) == 0.0


def test_dedupe_keeps_one_finding_per_thing_and_the_failing_one():
    a = M.finding("warn", "contrast", "hero", "phone", "x", "y", subject="headline A")
    b = M.finding("fail", "contrast", "hero", "phone", "x2", "y", subject="headline A")
    c = M.finding("warn", "contrast", "hero", "phone", "z", "y", subject="headline B")
    out = P._dedupe([a, b, c])
    assert len(out) == 2 and next(f for f in out if f["subject"] == "headline A")["severity"] == "fail"


def test_the_contact_sheet_frames_each_shot_by_its_worst_finding_and_marks_the_box(tmp_path):
    for n in range(2):
        Image.new("RGB", (1440, 900), (60, 60, 60)).save(tmp_path / f"desktop-0{n}.jpg")
    stops = [{"y": 0, "sections": ["hero"], "path": "desktop-00.jpg"}, {"y": 900, "sections": ["faq"], "path": "desktop-01.jpg"}]
    fs = [M.finding("fail", "contrast", "hero", "desktop", "w", "f", shot=0, box=[100, 100, 600, 300])]
    sheet = Image.open(P._sheet(tmp_path, "desktop", stops, fs)).convert("RGB")
    assert sheet.width > 3 * 500 and sheet.height > 300

    def near(px, rgb):
        return all(abs(a - b) < 40 for a, b in zip(px, rgb))
    assert near(sheet.getpixel((8 - 1, 8 + 100)), P.COLORS["fail"])                       # the first frame is red
    assert near(sheet.getpixel((8 + 520 + 8 - 1, 8 + 100)), P.COLORS["clean"])           # the second is green
    assert P._sheet(tmp_path, "phone", [], []) is None


def test_the_table_lists_sections_findings_and_fixes():
    f = M.finding("fail", "contrast", "hero", "phone", "headline \"x\" has 2:1", "move it with `place: left`", shot=0)
    r = {"project": "demo", "summary": {"verdict": "fail", "fails": 1, "warns": 0, "sections": 2}, "seconds": 3.0,
         "sections": [{"id": "hero"}, {"id": "faq"}], "findings": [f, M.finding("warn", "busy", "nav", "desktop", "w", "f")],
         "folder": "out", "sheets": {"desktop": "sheet-desktop.jpg"}, "skipped": ["faces: none"]}
    out = P.table(r)
    assert "fail: 1 fail, 0 warn" in out and "hero" in out and "1 fail 0 warn" in out and "clean" in out
    assert "FAIL  hero | phone | contrast" in out and "fix: move it with `place: left`" in out
    assert "sheet-desktop.jpg" in out and "not checked: faces: none" in out


# ---------------------------------------------------------------- the whole check against a browser made of stand-ins

class FakeTag:
    def __init__(self, page, css):
        self.page, self.css = page, css

    def evaluate(self, js):
        if "remove" in js and self.css in self.page.styles:
            self.page.styles.remove(self.css)


class FakePage:
    """What `inspect_page` asks of a Playwright page, answered from made-up facts: a plan of sections, the text blocks seen at
    each scroll position, the pictures, and a screenshot that is noisy without the page's words, flat with them, and brighter
    again with the scrims hidden. A browser-free test of the glue: stops, hiding words, measuring, findings, sheets, report."""

    def __init__(self, viewport):
        self.vp, self.y, self.styles = viewport, 0, []
        w, h, dpr, _ = P.VIEWPORTS[viewport]
        self.size = (int(w * dpr), int(h * dpr))
        self.dpr, self.h = dpr, h

    def item(self, text, role, section, y, **kw):
        w = P.VIEWPORTS[self.vp][0]
        box = [w * 0.2, y, w * 0.8, y + 40]
        it = {"text": text, "sel": "p", "role": role, "size": 17 if role == "body" else 60, "weight": 400,
              "color": [255, 255, 255, 1.0], "section": section, "caption": False, "hero": section == "hero", "side": "center",
              "rect": box, "seen": [box], "nlines": 2, "chars": [90, 30], "over": ["img"], "veils": 1, "device": False}
        it.update(kw)
        return it

    def evaluate(self, js, *a):
        if js == P.PLAN_JS:
            return {"docH": 3000, "sections": [{"label": "hero", "kind": "hero", "scene": False, "top": 0, "height": 900, "ys": [0]},
                                               {"label": "story", "kind": "scene", "scene": True, "top": 900, "height": 900, "ys": [900]}]}
        if js == P.IMAGES_JS:
            return [{"path": "/hero.png", "natural": [320, 180], "box": [1440, 900], "fit": "cover", "at": [0.5, 0.5], "doc": [0, 0],
                     "section": "hero"}]
        if js == P.COLLECT_JS:
            if self.y == 0:
                items = [self.item("Sleep care built around you", "headline", "hero", 300),
                         self.item("A paragraph that is far too wide for comfortable reading " * 3, "body", "hero", 380),
                         self.item("Start", "cta", "hero", 800),
                         self.item("Overlapping", "label", "hero", 392),
                         self.item("Menu", "label", "nav", 10)]
                over = {"px": 60, "culprits": ["#wide in hero (reaches 500 px)"], "section": "hero"}
                cta = {"label": "Start", "top": self.h + 10.0, "bottom": self.h + 50.0, "fold": float(self.h), "box": [1, 2, 3, 4],
                       "section": "hero"}
                return {"items": items, "overflow": over, "ctas": [cta], "veils": 1}
            return {"items": [self.item("A caption", "body", "story", 300, caption=True, over=[], chars=[50, 30]),
                              self.item("A phone line", "body", "story", 500, device=True, over=[])],
                    "overflow": None, "ctas": [], "veils": 0}
        if isinstance(js, str) and js.startswith("scrollTo(0, "):
            self.y = int(js[len("scrollTo(0, "):-1])
        elif "pp-hit" in str(js) and "remove" in str(js):
            self.styles.remove(P.HIT)
        return None

    def wait_for_timeout(self, ms):
        pass

    def add_style_tag(self, content):
        self.styles.append(content)
        return FakeTag(self, content)

    def screenshot(self):
        import io
        w, h = self.size
        if P.NO_SCRIM in self.styles:
            img = np.full((h, w, 3), 235, np.uint8)               # the picture without its scrims: bright, flat
        elif P.NO_TEXT in self.styles:
            img = np.where(np.arange(w)[None, :, None] % 4 < 2, 40, 150).astype(np.uint8) * np.ones((h, 1, 3), np.uint8)
        else:
            img = np.full((h, w, 3), 90, np.uint8)
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, "PNG")
        return buf.getvalue()


class FakeContext:
    def close(self):
        pass


class FakeBrowser:
    def close(self):
        pass


def fake_browser(monkeypatch):
    import playwright.sync_api as pw

    class FakePlaywright:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(pw, "sync_playwright", lambda: FakePlaywright())
    monkeypatch.setattr(P, "_chromium", lambda p: FakeBrowser())
    monkeypatch.setattr(P, "_open", lambda browser, base, viewport: (FakeContext(), FakePage(viewport)))


def test_the_report_is_assembled_from_what_the_browser_reads(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    Image.new("RGB", (320, 180), (20, 20, 20)).save(dist / "hero.png")
    fake_browser(monkeypatch)
    monkeypatch.setattr(P, "detect_faces", lambda rgb: [(0.3, 0.3, 0.5, 0.5)])          # a face behind the headline
    log: list[str] = []
    r = P.inspect_page(Project(tmp_path), log=log.append)
    assert r["summary"]["verdict"] == "fail" and r["summary"]["sections"] == 2 and len(log) == 4
    got = {(f["section"], f["viewport"], f["check"]) for f in r["findings"]}
    assert {("hero", "desktop", "contrast"), ("hero", "desktop", "busy"), ("hero", "desktop", "line-length"),
            ("hero", "desktop", "overflow"), ("hero", "desktop", "cta-fold"), ("hero", "desktop", "overlap"),
            ("hero", "desktop", "upscaled"), ("hero", "desktop", "scrim"), ("hero", "desktop", "text-over-face")} <= got
    assert not [f for f in r["findings"] if f["section"] == "story"]            # a phone mock's text is not the page's type
    assert any(f["section"] == "nav" for f in r["findings"]) and not any(f["check"] == "overlap" and f["section"] == "nav" for f in r["findings"])
    folder = tmp_path / ".build" / "inspect" / "page"
    saved = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert saved["summary"] == r["summary"] and saved["text_over_pictures"] and saved["pictures"][0]["upscale"] > 4
    assert {p.name for p in folder.glob("*.jpg")} >= {"sheet-desktop.jpg", "sheet-phone.jpg", "desktop-00.jpg", "phone-01.jpg"}
    rows = [t for t in saved["text_over_pictures"] if t["viewport"] == "desktop" and t["role"] == "headline"]
    assert rows[0]["busy"] >= 90 and rows[0]["without_scrim"]["shift"] > 0.1
    only = P.inspect_page(Project(tmp_path), only="story", log=log.append)
    assert only["summary"]["stops"]["desktop"] == 1 and not only["findings"]
    with pytest.raises(P.Nothing, match="no section 'nope'"):
        P.inspect_page(Project(tmp_path), only="nope", log=log.append)


def test_a_missing_build_or_chromium_is_said_plainly(tmp_path):
    with pytest.raises(P.Nothing, match="studio build"):
        P.inspect_page(Project(tmp_path), log=print)

    class Chromium:
        def launch(self, **kw):
            raise RuntimeError("Executable doesn't exist at /nowhere\nrun playwright install")

    class Playwright:
        chromium = Chromium()
    with pytest.raises(P.Nothing, match="playwright install chromium"):
        P._chromium(Playwright())


def test_no_faces_are_found_in_a_flat_picture():
    faces = P.detect_faces(solid((90, 90, 90), 400, 300))
    if faces is None:       # an OpenCV build without the bundled cascade files: the report lists faces as not checked
        pytest.skip("this OpenCV has no face cascade files")
    assert faces == []


# ---------------------------------------------------------------- the command

def test_the_page_check_needs_a_built_page(tmp_path):
    (tmp_path / "site.yaml").write_text("name: x\nsections: []\n", encoding="utf-8")
    r = CliRunner().invoke(cli.app, ["inspect", str(tmp_path), "--page"])
    assert r.exit_code != 0 and "studio build" in r.output


def test_the_exit_code_gates_on_fails_and_json_is_clean(tmp_path, monkeypatch):
    (tmp_path / "site.yaml").write_text("name: x\nsections: []\n", encoding="utf-8")
    report = {"project": "x", "summary": {"verdict": "fail", "fails": 1, "warns": 0, "sections": 1}, "seconds": 1.0,
              "sections": [{"id": "hero"}], "findings": [M.finding("fail", "overflow", "hero", "phone", "w → x", "f")],
              "folder": str(tmp_path), "sheets": {}, "skipped": []}
    monkeypatch.setattr(P, "inspect_page", lambda project, only=None, log=print: report)
    r = CliRunner().invoke(cli.app, ["inspect", str(tmp_path), "--page", "--json"])
    assert r.exit_code == 1 and json.loads(r.output)["summary"]["fails"] == 1
    r = CliRunner().invoke(cli.app, ["inspect", str(tmp_path), "--page"])
    assert r.exit_code == 1 and "FAIL  hero | phone | overflow" in r.output
    report["summary"]["fails"], report["findings"] = 0, []
    assert CliRunner().invoke(cli.app, ["inspect", str(tmp_path), "--page"]).exit_code == 0


def test_the_surface_snapshot_knows_the_option():
    snap = json.loads((Path(__file__).parent / "snapshots" / "surface" / "cli.json").read_text(encoding="utf-8"))
    assert "--page" in snap["commands"]["inspect"]["params"]["page"]["opts"]


# ---------------------------------------------------------------- a real page in headless Chromium

LONG = " ".join(["Every plan is written by a clinician who has read your answers and adjusts it each week as you sleep."] * 3)


def build_site(root: Path) -> Project:
    """Six blocks, built by the real compiler: a hero over a deliberately busy picture, one over a small calm picture (blown
    up), one over a large calm picture, an FAQ whose answer runs far too wide, a hero too tall for a phone."""
    from engine.compile import compiler, fonts
    (root / "inputs").mkdir(parents=True)
    Image.fromarray(noise(960, 540, 7)).resize((1920, 1080), Image.NEAREST).save(root / "inputs" / "busy.png")
    small = np.tile(np.linspace(18, 60, 90, dtype=np.float32)[:, None, None], (1, 160, 3)).astype(np.uint8)
    Image.fromarray(small).save(root / "inputs" / "small.png")
    calm = np.tile(np.linspace(18, 60, 1080, dtype=np.float32)[:, None, None], (1, 1920, 3)).astype(np.uint8)
    Image.fromarray(calm).save(root / "inputs" / "calm.png")

    def hero(id_, title, body, image):
        return {"id": id_, "type": "hero", "title": title, "body": body, "buttons": [{"label": "Start", "href": "#end"}],
                "image": {"file": f"inputs/{image}.png"}}
    spec = {"name": "Page fixture", "theme": {"preset": "night", "type": {"body": "11px"}}, "sections": [
        hero("busy", "Sleep care built around you", "A clinician, a plan and support that changes as you do.", "busy"),
        hero("small", "Calm but small", "Short body.", "small"),
        hero("good", "Calm and large", "Short body.", "calm"),
        {"id": "faq", "type": "faq", "title": "Questions", "items": [{"q": "Who builds my plan?", "a": LONG}]},
        hero("tall", "A hero that is too tall for a phone", " ".join([LONG] * 3), "calm"),
        {"id": "end", "type": "cta", "title": "Done", "button": {"label": "Go", "href": "#"}}]}
    (root / "site.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    saved = fonts.vendor
    fonts.vendor = lambda links, dist, log=print: None                  # no network: the page uses the machine's fonts
    try:
        compiler.build_site(Project(root), log=lambda m: None)
    finally:
        fonts.vendor = saved
    return Project(root)


@pytest.fixture(scope="module")
def chromium():
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as e:
        pytest.skip(f"Playwright's Chromium is not installed ({str(e).strip().splitlines()[0][:80]})")


@pytest.fixture(scope="module")
def fixture_page(chromium, tmp_path_factory):
    project = build_site(tmp_path_factory.mktemp("page-fixture") / "site")
    return project, P.inspect_page(project, log=lambda m: None)


def where(report, section, check, viewport=None):
    return [f for f in report["findings"] if f["section"] == section and f["check"] == check and viewport in (None, f["viewport"])]


def test_a_busy_picture_under_text_fails_and_a_calm_one_does_not(fixture_page):
    _, r = fixture_page
    busy = [f for f in where(r, "busy", "contrast") if f["severity"] == "fail"]
    assert {f["viewport"] for f in busy} == {"desktop", "phone"}
    assert where(r, "busy", "busy", "desktop")
    assert not [f for f in r["findings"] if f["section"] == "good" and f["check"] in ("contrast", "busy", "scrim")]
    rows = {(t["section"], t["role"]): t for t in r["text_over_pictures"] if t["viewport"] == "desktop"}
    assert rows[("busy", "headline")]["busy"] >= 90 and rows[("good", "headline")]["busy"] <= 15
    assert rows[("good", "headline")]["contrast"]["typical"] > 8


def test_a_picture_blown_up_is_found_with_the_numbers(fixture_page):
    _, r = fixture_page
    f, = where(r, "small", "upscaled", "desktop")
    assert f["severity"] == "fail" and "160x90" in f["what"] and "`size:" in f["fix"]
    assert where(r, "good", "upscaled", "desktop") == []
    phone = where(r, "good", "upscaled", "phone")[0]                       # a wide picture cropped for a phone at 2x
    assert phone["severity"] == "warn" and "1.6" in phone["what"]


def test_a_line_that_is_too_long_and_a_button_below_the_fold_are_found(fixture_page):
    _, r = fixture_page
    f, = where(r, "faq", "line-length", "desktop")
    assert f["severity"] == "warn" and "over 80" in f["what"]
    cta = where(r, "tall", "cta-fold", "phone")
    assert cta and cta[0]["severity"] == "fail" and "below the fold" in cta[0]["what"]
    assert not where(r, "busy", "cta-fold")


def test_the_report_and_the_sheets_are_written(fixture_page):
    project, r = fixture_page
    folder = project.build / "inspect" / "page"
    assert json.loads((folder / "report.json").read_text(encoding="utf-8"))["summary"] == r["summary"]
    assert r["summary"]["verdict"] == "fail" and r["summary"]["fails"] >= 3
    for vp in ("desktop", "phone"):
        sheet = Image.open(folder / r["sheets"][vp])
        assert sheet.width > 600 and r["summary"]["stops"][vp] >= 6
    names = {s["id"] for s in r["sections"]}
    assert {"busy", "small", "good", "faq", "tall", "end"} <= names
    assert any("faces" in x for x in r["skipped"])


def test_the_command_exits_non_zero_when_something_fails(fixture_page):
    project, _ = fixture_page
    run = CliRunner().invoke(cli.app, ["inspect", str(project.root), "--page", "--section", "busy"])
    assert run.exit_code == 1 and "FAIL  busy" in run.output
    run = CliRunner().invoke(cli.app, ["inspect", str(project.root), "--page", "--section", "end", "--json"])
    assert run.exit_code == 0 and json.loads(run.stdout)["summary"]["fails"] == 0
    assert CliRunner().invoke(cli.app, ["inspect", str(project.root), "--page", "--section", "nope"]).exit_code != 0


def test_overflow_and_overlapping_text_are_found_in_markup_the_compiler_did_not_make(chromium, tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:#222;color:#eee;font:16px sans-serif}.ss-block{position:relative;min-height:100vh}
h2{margin:0;font-size:40px;position:absolute;top:100px;left:20px}p{position:absolute;top:110px;left:30px;margin:0}
#wide{position:absolute;top:400px;left:0;width:2000px;height:20px;background:#c33}</style></head><body>
<section class="ss-block" id="one"><h2>Overlapping headline text</h2><p>Overlapping paragraph of copy</p><div id="wide"></div></section>
<script>document.documentElement.dataset.ssReady = '1'</script></body></html>""", encoding="utf-8")
    r = P.inspect_page(Project(tmp_path), log=lambda m: None)
    over = where(r, "one", "overflow", "phone")
    assert over and over[0]["severity"] == "fail" and "#wide" in over[0]["what"]
    assert where(r, "one", "overlap", "desktop") and where(r, "one", "overlap", "phone")


def test_a_page_that_never_gets_ready_says_so(chromium, tmp_path, monkeypatch):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<!doctype html><title>x</title><p>no runtime</p>", encoding="utf-8")
    import playwright.sync_api as pw
    orig = pw.Page.wait_for_function
    monkeypatch.setattr(pw.Page, "wait_for_function", lambda self, expr, timeout=None, **k: orig(self, expr, timeout=500, **k))
    with pytest.raises(P.Nothing, match="never became ready"):
        P.inspect_page(Project(tmp_path), log=lambda m: None)


def test_a_tall_overlay_caption_on_a_phone_stops_below_the_nav(chromium, tmp_path):
    """An overlay caption is centred a quarter of the way down a phone; a tall one used to grow up under the nav."""
    from playwright.sync_api import sync_playwright

    from engine.compile import compiler, fonts
    from engine.serve import serve
    root = tmp_path / "site"
    root.mkdir()
    spec = {"name": "Tall", "theme": {"preset": "paper"}, "sections": [
        {"id": "desk", "type": "diorama", "layout": "overlay", "world": {"kind": "desk", "seed": 4},
         "places": [{"name": "Notebook", "kind": "notebook"}],
         "steps": [{"intro": True, "at": "left", "kicker": "Kicker", "title": "A headline long enough to take three lines",
                    "body": LONG, "button": {"label": "Go", "href": "#"}}]},
        {"type": "cta", "title": "End"}]}
    (root / "site.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    saved = fonts.vendor
    fonts.vendor = lambda links, dist, log=print: None
    try:
        compiler.build_site(Project(root), log=lambda m: None)
    finally:
        fonts.vendor = saved
    httpd = serve(root / "dist", 0, background=True)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/", wait_until="load")
            page.wait_for_timeout(800)
            nav = page.eval_on_selector(".ss-nav", "e => e.getBoundingClientRect().bottom")
            top = page.eval_on_selector("#desk .ss-caption", "e => e.getBoundingClientRect().top")
            b.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert top >= nav, f"the caption starts at {top:.0f}px, under the nav that ends at {nav:.0f}px"


def test_a_headline_in_a_narrow_grid_slot_fits_the_slot(chromium, tmp_path):
    """A third of the grid is about 440 px on a laptop: a caption there sets its headline to the slot, not the screen."""
    from playwright.sync_api import sync_playwright

    from engine.compile import compiler, fonts
    from engine.serve import serve
    root = tmp_path / "site"
    root.mkdir()
    steps = [{"title": "Back-pressure at the door", "body": "Short.", "at": {"grid": f"{c} / span 4", "row": "top"},
              "show": [0.05, 0.95]} for c in (1, 5, 9)]
    spec = {"name": "Slots", "theme": {"preset": "paper"}, "sections": [
        {"id": "desk", "type": "diorama", "layout": "overlay", "world": {"kind": "desk", "seed": 4},
         "places": [{"name": "Notebook", "kind": "notebook"}], "steps": steps}, {"type": "cta", "title": "End"}]}
    (root / "site.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    saved = fonts.vendor
    fonts.vendor = lambda links, dist, log=print: None
    try:
        compiler.build_site(Project(root), log=lambda m: None)
    finally:
        fonts.vendor = saved
    httpd = serve(root / "dist", 0, background=True)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
            page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/", wait_until="load")
            page.wait_for_timeout(500)
            boxes = page.eval_on_selector_all("#desk .ss-captions--grid .ss-caption", """els => els.map(e => {
                const h = e.querySelector('.ss-display');
                return {slot: e.getBoundingClientRect().width, size: parseFloat(getComputedStyle(h).fontSize),
                        right: h.getBoundingClientRect().right, edge: e.getBoundingClientRect().right};
            })""")
            b.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert len(boxes) == 3
    for x in boxes:
        assert x["size"] <= x["slot"] * 0.12 + 0.5, x            # the type follows the slot
        assert x["right"] <= x["edge"] + 1, x                     # and the headline stays inside it


def test_a_split_scene_with_its_picture_on_the_left_stacks_on_a_phone(chromium, tmp_path):
    """`side: left` set two columns with a stronger rule than the phone's one column, so the picture and the copy were
    squeezed side by side on a phone."""
    from playwright.sync_api import sync_playwright

    from engine.compile import compiler, fonts
    from engine.serve import serve
    root = tmp_path / "site"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs" / "d.csv").write_text("year,value\n2020,1\n2021,3\n2022,2\n", encoding="utf-8")
    spec = {"name": "Split", "theme": {"preset": "paper"}, "sections": [
        {"id": "data", "type": "chart", "layout": "split", "side": "left", "data": "inputs/d.csv", "x": "year", "y": "value",
         "steps": [{"title": "A line", "body": "It goes up and down."}]}, {"type": "cta", "title": "End"}]}
    (root / "site.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    saved = fonts.vendor
    fonts.vendor = lambda links, dist, log=print: None
    try:
        compiler.build_site(Project(root), log=lambda m: None)
    finally:
        fonts.vendor = saved
    httpd = serve(root / "dist", 0, background=True)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": 390, "height": 844})
            page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/", wait_until="load")
            tracks = page.eval_on_selector("#data .ss-split-grid", "e => getComputedStyle(e).gridTemplateColumns")
            b.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert len(tracks.split()) == 1, tracks
