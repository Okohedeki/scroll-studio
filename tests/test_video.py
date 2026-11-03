"""Product video (engine/video.py, issue #179) and the speech backend: which stills go in and for how long, the silent
laptop path, a voiceover from a stand-in speech backend, and ElevenLabs with the network replaced."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
import yaml

from engine import video
from engine.project import BuildError, probe
from engine.router import builtin, core
from engine.router.core import Result, SpeechJob
from engine.stills import run as stills
from test_stills import project

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


@pytest.fixture(autouse=True)
def no_backends(monkeypatch):
    monkeypatch.setattr(core, "backends", lambda: [])
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)


def with_outputs(p, **outputs):
    data = yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))
    data["outputs"].update(outputs)
    p.spec_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def test_sources_take_the_pick_first_then_the_shortlist():
    state = {"candidates": [{"id": i} for i in "abcde"], "picked": {"x": "c"},
             "shortlist": {"x": ["a", "c", "b"], "y": ["d", "e"]}}
    assert [c["id"] for c in video.sources(state, ["x", "y"], 2)] == ["c", "a", "d", "e"]


def test_segments_fill_the_length_with_dissolves():
    seg = video.segment_seconds(15, 4, True)
    total = 4 * seg + video.END_CARD - 4 * video.DISSOLVE
    assert total == pytest.approx(15)


def test_video_needs_stills(tmp_path):
    p = with_outputs(project(tmp_path), video={"seconds": 6, "width": 320})
    with pytest.raises(BuildError, match="studio stills"):
        video.make(p, log=lambda m: None)


@needs_ffmpeg
def test_a_silent_video_on_a_laptop(tmp_path):
    p = with_outputs(project(tmp_path, shots=["lifestyle", "packshot"]),
                     video={"seconds": 6, "width": 320, "shots": ["lifestyle", "packshot"], "per_shot": 1,
                            "voiceover": "Hello"},
                     ads={"headline": "Hi", "cta": "Shop"})
    stills.make(p, log=lambda m: None)
    r = video.make(p, log=lambda m: None)
    out = p.root / "video" / r["file"]
    assert r["end_card"] and r["voice"].startswith("silent") and len(r["stills"]) == 2
    assert float(probe(out)["duration"]) == pytest.approx(6, abs=0.2)
    assert json.loads((p.root / "video" / "video.json").read_text(encoding="utf-8"))["size"] == [320, 568]


@needs_ffmpeg
def test_a_voiceover_from_a_speech_backend(tmp_path, monkeypatch):
    class Voice:
        name, local, kinds = "voice", False, ("speech",)

        def available(self):
            return True, ""

        def model(self, kind):
            return "v1"

        def run(self, job, out, model=None):
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
                            str(out)], check=True)
            return Result("voice", "v1", 0.0, path=out)

    p = with_outputs(project(tmp_path, shots=["packshot"]),
                     video={"seconds": 5, "width": 320, "shots": ["packshot"], "per_shot": 1, "voiceover": "Hello"})
    stills.make(p, log=lambda m: None)
    monkeypatch.setattr(core, "backends", lambda: [Voice()])
    r = video.make(p, log=lambda m: None)
    assert r["voice"] == "voice by voice (v1)"
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                              str(p.root / "video" / r["file"])], capture_output=True, text=True).stdout.split()
    assert "audio" in streams


def test_elevenlabs_backend(monkeypatch, tmp_path):
    import httpx
    sent = {}

    class R:
        content = b"ID3fake"

        def raise_for_status(self):
            pass

    def post(url, **kw):
        sent.update(url=url, **kw)
        return R()
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    monkeypatch.setattr(httpx, "post", post)
    b = builtin.ElevenLabsSpeech()
    assert b.available()[0]
    r = b.run(SpeechJob("Hello there", voice="abc"), tmp_path / "v.mp3")
    assert sent["url"].endswith("/text-to-speech/abc") and sent["headers"]["xi-api-key"] == "test"
    assert sent["json"]["text"] == "Hello there" and (tmp_path / "v.mp3").read_bytes() == b"ID3fake"
    assert r.meta["voice"] == "abc"
