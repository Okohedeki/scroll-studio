"""A story film on a phone and with reduced motion: each beat's `focus` (where a portrait crop looks), the moment of each
beat that stands for it as a still (`beat_moments`), and the per-beat stills and spans the build hands the page."""
from __future__ import annotations

import shutil

import pytest
from pydantic import ValidationError

from engine.scenes.film import beat_moments, beat_spans, beat_stills, join_fades
from engine.spec import Beat, FilmScene

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def film(*focus, fades=None, seconds=3):
    beats = []
    for i, f in enumerate(focus):
        b = {"id": f"b{i}", "prompt": "p", "motion": "m", "seconds": seconds}
        if f is not None:
            b["focus"] = f
        if fades and i and fades[i - 1] is not None:
            b["fade"] = fades[i - 1]
        beats.append(b)
    return FilmScene.model_validate({"id": "s", "beats": beats})


def test_focus_is_optional_and_a_point_of_the_frame():
    assert Beat.model_validate({"id": "a", "prompt": "p", "motion": "m"}).focus is None
    assert Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "focus": [0.7, 0.4]}).focus == (0.7, 0.4)
    with pytest.raises(ValidationError):
        Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "focus": [1.2, 0.5]})
    with pytest.raises(ValidationError):
        Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "focus": [0.5]})


def test_a_beats_still_is_taken_clear_of_the_dissolves_either_side():
    sec = film(None, None, None, fades=[1.0, 0])
    durs = [3.0, 3.0, 3.0]
    spans = beat_spans(sec, durs, join_fades(sec, durs))
    m = beat_moments(spans)
    total = 9.0 - 1.0
    # the first beat's clear part ends where the second starts dissolving in (2 s), the second's runs from the end of
    # that dissolve (3 s) to the hard cut (5 s), the third's from the cut to the end
    assert m["b0"] == pytest.approx(1.0 / total)
    assert m["b1"] == pytest.approx(4.0 / total)
    assert m["b2"] == pytest.approx(6.5 / total)
    for b in m:
        assert spans[b][0] <= m[b] <= spans[b][1]


def test_a_beat_entirely_inside_dissolves_falls_back_to_its_middle():
    spans = {"a": (0.0, 0.5), "b": (0.3, 0.6), "c": (0.45, 1.0)}
    assert beat_moments(spans)["b"] == pytest.approx(0.45)


@needs_ffmpeg
def test_the_page_gets_each_beats_span_focus_and_still(tmp_path):
    from engine.project import BuildContext, Project, ffmpeg
    (tmp_path / "p").mkdir()
    ctx = BuildContext(Project(tmp_path / "p"), "s", log=lambda *a: None)
    src = tmp_path / "film.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=192x108:rate=24:duration=2", "-pix_fmt", "yuv420p", src)
    sec = film([0.8, 0.3], None, seconds=1)
    spans = {"b0": (0.0, 0.55), "b1": (0.45, 1.0)}
    out = beat_stills(sec, ctx, src, spans)
    assert [b["id"] for b in out] == ["b0", "b1"]
    assert out[0]["focus"] == [0.8, 0.3] and out[1]["focus"] is None
    assert (out[0]["p0"], out[0]["p1"]) == (0.0, 0.55)
    for b in out:
        assert b["still"].startswith("assets/s/") and (ctx.web / b["still"].rsplit("/", 1)[1]).stat().st_size > 0
    stamp = {p.name: p.stat().st_mtime_ns for p in ctx.web.glob("beat-*.jpg")}
    beat_stills(sec, ctx, src, spans)                     # cached by the film and the moments: nothing is taken again
    assert {p.name: p.stat().st_mtime_ns for p in ctx.web.glob("beat-*.jpg")} == stamp
