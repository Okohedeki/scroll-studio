"""A beat's own join (`fade:` on a beat): a crossfade of its own length into it, or 0 for a hard cut. The spec, the
overlaps every timing reads (`join_fades`, `beat_spans`), the ffmpeg join itself, and the polish report's spans."""
from __future__ import annotations

import shutil

import numpy as np
import pytest
from pydantic import ValidationError

from engine.scenes.film import beat_spans, join_beats, join_fades
from engine.spec import Beat, FilmScene

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def film(*fades, beat_fade=0.4, seconds=3):
    beats = [{"id": f"b{i}", "prompt": "p", "motion": "m", "seconds": seconds, **({} if f is None else {"fade": f})}
             for i, f in enumerate(fades)]
    return FilmScene.model_validate({"id": "s", "beat_fade": beat_fade, "beats": beats})


def test_fade_is_optional_and_bounded():
    assert Beat.model_validate({"id": "a", "prompt": "p", "motion": "m"}).fade is None
    assert Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "fade": 0}).fade == 0
    assert Beat.model_validate({"id": "a", "seconds": 3, "freeze": {"image": "x.png"}, "fade": 1.2}).fade == 1.2
    with pytest.raises(ValidationError):
        Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "fade": 3})
    with pytest.raises(ValidationError):
        Beat.model_validate({"id": "a", "prompt": "p", "motion": "m", "fade": -0.1})


def test_join_fades_take_each_beats_own_or_the_films():
    sec = film(None, 0, None, 0.9)
    assert join_fades(sec, [3.0, 3.0, 3.0, 3.0]) == pytest.approx([0.0, 0.4, 0.9])
    # a beat's own crossfade is still at most a third of either clip it joins
    assert join_fades(film(None, 2.0), [3.0, 1.5]) == pytest.approx([0.5])
    # a film without any keeps the one crossfade for every join
    assert join_fades(film(None, None, None), [3.0, 3.0, 3.0]) == pytest.approx([0.4, 0.4])


def test_a_continued_camera_beat_keeps_its_frame_exact_join():
    keys = [{"t": 0, "box": [0, 0, 1, 1]}, {"t": 1, "box": [0.2, 0.2, 0.8, 0.8]}]
    sec = FilmScene.model_validate({"id": "s", "beats": [
        {"id": "a", "prompt": "p", "motion": "m", "seconds": 3, "camera": keys},
        {"id": "b", "prompt": "p", "motion": "m", "seconds": 3, "fade": 1.0,
         "camera": {"keys": keys[1:], "continues": True}}]})
    assert join_fades(sec, [3.0, 3.0]) == pytest.approx([1 / 24])


def test_a_hard_cut_puts_the_next_beat_right_after_the_one_before():
    sec = film(None, 0, None)
    durs = [3.0, 3.0, 3.0]
    spans = beat_spans(sec, durs, join_fades(sec, durs))
    total = 9.0 - 0.4
    assert spans["b1"] == pytest.approx((3.0 / total, 6.0 / total))
    assert spans["b2"] == pytest.approx(((6.0 - 0.4) / total, 1.0))


def _clip(path, color, seconds, size=(64, 48)):
    from engine.project import ffmpeg
    w, h = size
    ffmpeg("-f", "lavfi", "-i", f"color=c=0x{color}:s={w}x{h}:r=24:d={seconds}", "-c:v", "libx264", "-crf", "10",
           "-pix_fmt", "yuv420p", path)
    return path


def _frames(path):
    import subprocess
    w, h = 64, 48
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


@needs_ffmpeg
def test_a_hard_cut_and_a_crossfade_in_one_film(tmp_path):
    a = _clip(tmp_path / "a.mp4", "ff0000", 2.0)
    b = _clip(tmp_path / "b.mp4", "0000ff", 2.0)
    c = _clip(tmp_path / "c.mp4", "00ff00", 2.0)
    out = tmp_path / "out.mp4"
    sec = film(None, 0, 0.5, seconds=2)
    join_beats(sec, [a, b, c], [2.0, 2.0, 2.0], out, tmp_path)
    fr = _frames(out)
    assert len(fr) == 3 * 48 - 12                          # the cut overlaps nothing, the crossfade half a second
    red, blue = fr[47].astype(int), fr[48].astype(int)
    assert red[..., 0].mean() > 200 and red[..., 2].mean() < 40      # the last frame of a is all a
    assert blue[..., 2].mean() > 200 and blue[..., 0].mean() < 40    # the first frame after the cut is all b
    mid = fr[96 - 12 + 6].astype(int)                                # inside the crossfade from b to c: a blend
    assert 40 < mid[..., 2].mean() < 215 and 40 < mid[..., 1].mean() < 215


@needs_ffmpeg
def test_a_film_without_its_own_joins_crossfades_every_join(tmp_path):
    a = _clip(tmp_path / "a.mp4", "ff0000", 1.0)
    b = _clip(tmp_path / "b.mp4", "0000ff", 1.0)
    out = tmp_path / "out.mp4"
    join_beats(film(None, None, beat_fade=0.25, seconds=1), [a, b], [1.0, 1.0], out, tmp_path)
    fr = _frames(out)
    assert len(fr) == 48 - 6
    assert 40 < fr[21].astype(int)[..., 0].mean() < 215                # mid-crossfade


def test_polish_spans_follow_a_beats_own_join(tmp_path):
    from engine.polish.run import plan_spans
    from engine.project import Project
    (tmp_path / "site.yaml").write_text("name: T\nsections: []\n", encoding="utf-8")
    sec = film(None, 0, None, beat_fade=1.0)
    spans, fade = plan_spans(Project(tmp_path), sec, 3 * 3.0 - 1.0)
    assert [round(s.start, 2) for s in spans] == [0.0, 3.0, 5.0]
    assert [round(s.end, 2) for s in spans] == [3.0, 6.0, 8.0]
