"""The frontier provider backends (engine/router/providers.py), the cloud account backend (engine/cloud.py) and video
jobs routed out of `animate`. Every HTTP call is answered by a stand-in: no test touches the network."""
from __future__ import annotations

import base64
import io
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from engine import cloud, router
from engine.router import core, providers
from engine.router.core import EditJob, ImageJob, TextJob, VideoJob


def png_bytes(w=40, h=30, colour="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, "PNG")
    return buf.getvalue()


class R:
    def __init__(self, data=None, content=b"", status=200):
        self._data, self.content, self.status_code = data, content or (json.dumps(data).encode() if data else b""), status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def web(monkeypatch):
    """Records every httpx.get/post and answers from `routes` (url substring -> response or callable)."""
    import httpx
    calls, routes = [], {}

    def answer(method):
        def f(url, **kw):
            calls.append((method, url, kw))
            for key, resp in routes.items():
                if key in url:
                    return resp(url, kw) if callable(resp) else resp
            raise AssertionError(f"unexpected {method} {url}")
        return f
    monkeypatch.setattr(httpx, "post", answer("post"))
    monkeypatch.setattr(httpx, "get", answer("get"))
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    return calls, routes


def test_gemini_draws_an_image_at_the_asked_size(web, monkeypatch, tmp_path):
    calls, routes = web
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    b64 = base64.b64encode(png_bytes(64, 36)).decode()
    routes[":generateContent"] = R({"candidates": [{"content": {"parts": [{"inlineData": {"data": b64}}]}}]})
    out = tmp_path / "a.png"
    res = providers.GeminiBackend().run(ImageJob("a kettle", 1600, 900, 3), out)
    assert Image.open(out).size == (1600, 900) and res.model == "gemini-3.1-flash-image"
    body = calls[0][2]["json"]
    assert body["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"
    assert calls[0][2]["headers"]["x-goog-api-key"] == "k"


def test_gemini_text_skips_thoughts_and_asks_for_json(web, monkeypatch):
    calls, routes = web
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    routes[":generateContent"] = R({"candidates": [{"content": {"parts": [{"text": "plan", "thought": True},
                                                                          {"text": '{"a": 1}'}]}}]})
    res = providers.GeminiBackend().run(TextJob("x", system="be brief", json=True), None)
    assert res.text == '{"a": 1}'
    gen = calls[0][2]["json"]
    assert gen["generationConfig"]["responseMimeType"] == "application/json"
    assert gen["systemInstruction"]["parts"][0]["text"] == "be brief"


def test_gemini_video_waits_for_the_file_then_downloads_it(web, monkeypatch, tmp_path):
    calls, routes = web
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    still = tmp_path / "s.png"
    still.write_bytes(png_bytes())
    routes["/interactions"] = R({"steps": [{"type": "model_output", "content": [{"type": "video", "uri": "files/abc"}]}]})
    states = iter(["PROCESSING", "ACTIVE"])
    routes[":download"] = R(content=b"MP4")
    routes["/files/abc"] = lambda url, kw: R({"state": next(states)})
    out = tmp_path / "v.mp4"
    providers.GeminiBackend().run(VideoJob(str(still), "steam rises", 4.4, 1280, 720, 1), out)
    assert out.read_bytes() == b"MP4"
    fmt = calls[0][2]["json"]["response_format"]
    assert fmt["duration"] == "4s" and fmt["aspect_ratio"] == "16:9"


def test_flux_polls_until_ready_and_sends_edit_sources(web, monkeypatch, tmp_path):
    calls, routes = web
    monkeypatch.setenv("BFL_API_KEY", "k")
    src = tmp_path / "src.png"
    src.write_bytes(png_bytes(300, 200))
    routes["/flux-2-pro"] = R({"id": "1", "polling_url": "https://poll.example/1"})
    ticks = iter([{"status": "Pending"}, {"status": "Ready", "result": {"sample": "https://cdn.example/x.png"}}])
    routes["poll.example"] = lambda url, kw: R(next(ticks))
    routes["cdn.example"] = R(content=png_bytes(320, 208))
    out = tmp_path / "e.png"
    providers.FluxBackend().run(EditJob((str(src), str(src)), "warmer light", 7), out)
    body = calls[0][2]["json"]
    assert "input_image" in body and "input_image_2" in body and body["width"] % 16 == 0
    assert Image.open(out).size == (300, 200)


def test_flux_reports_moderation(web, monkeypatch, tmp_path):
    _, routes = web
    monkeypatch.setenv("BFL_API_KEY", "k")
    routes["/flux-2-pro"] = R({"id": "1", "polling_url": "https://poll.example/1"})
    routes["poll.example"] = R({"status": "Content Moderated"})
    with pytest.raises(RuntimeError, match="Moderated"):
        providers.FluxBackend().run(ImageJob("x", 512, 512, 1), tmp_path / "x.png")


def test_runway_picks_its_nearest_ratio_and_clamps_the_length(web, monkeypatch, tmp_path):
    calls, routes = web
    monkeypatch.setenv("RUNWAYML_API_SECRET", "k")
    still = tmp_path / "s.png"
    still.write_bytes(png_bytes())
    routes["/image_to_video"] = R({"id": "t1"})
    routes["/tasks/t1"] = R({"status": "SUCCEEDED", "output": ["https://cdn.example/v.mp4"]})
    routes["cdn.example"] = R(content=b"MP4")
    providers.RunwayBackend().run(VideoJob(str(still), "pan left", 14, 1080, 1920, 2), tmp_path / "v.mp4")
    body = calls[0][2]["json"]
    assert body["ratio"] == "720:1280" and body["duration"] == 10 and body["promptImage"].startswith("data:image/png;base64,")
    assert calls[0][2]["headers"]["X-Runway-Version"] == "2024-11-06"


def test_every_provider_is_off_without_its_key(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "BFL_API_KEY", "RUNWAYML_API_SECRET", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for b in (providers.GeminiBackend(), providers.FluxBackend(), providers.RunwayBackend(), providers.OpenAIText()):
        ok, why = b.available()
        assert not ok and "not set" in why


def test_local_first_never_routes_video_to_a_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNWAYML_API_SECRET", "k")
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)
    assert router.video_on_provider(tmp_path / "s.png", "x", 3, 1, tmp_path / "v.mp4", (64, 64), policy=None) is False
    assert router.choose("video", {"prefer": "provider"}).name == "runway"


# ---------------------------------------------------------------- the cloud account

class FakeClient:
    """Stands in for httpx.Client against the cloud API."""
    def __init__(self, script):
        self.script, self.calls = script, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _do(self, method, path, **kw):
        self.calls.append((method, path, kw))
        exact = self.script.get((method, path))
        hits = [exact] if exact is not None else             [r for k, r in sorted(self.script.items(), key=lambda kv: -len(kv[0][1]))
             if k[0] == method and path.startswith(k[1])]
        for resp in hits:
            return resp() if callable(resp) else resp
        raise AssertionError(f"unexpected {method} {path}")

    def post(self, path, **kw):
        return self._do("post", path, **kw)

    def get(self, path, **kw):
        return self._do("get", path, **kw)


@pytest.fixture
def account(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDIO_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("STUDIO_CLOUD_TOKEN", raising=False)
    monkeypatch.delenv("STUDIO_CLOUD_URL", raising=False)
    monkeypatch.setattr(cloud.time, "sleep", lambda s: None)
    return tmp_path


def test_login_waits_for_the_link_then_keeps_the_token(account, monkeypatch):
    polls = iter([R(status=428), R({"token": "tok", "email": "a@example.com", "balance": 50})])
    fc = FakeClient({("post", "/v1/login"): R({"device_code": "d", "interval": 1, "expires_in": 900}),
                     ("post", "/v1/login/poll"): lambda: next(polls)})
    monkeypatch.setattr(cloud, "_client", lambda url=None, token=None: fc)
    got = cloud.login("a@example.com", "http://127.0.0.1:8790/", log=lambda m: None)
    assert got == {"email": "a@example.com", "balance": 50}
    assert cloud.credentials() == {"url": "http://127.0.0.1:8790", "token": "tok", "email": "a@example.com"}
    assert cloud.CloudBackend().available() == (True, "")
    assert cloud.forget() and not cloud.CloudBackend().available()[0]


def test_a_cloud_edit_sends_its_images_and_writes_the_result(account, monkeypatch, tmp_path):
    cloud.save("http://svc", "tok", "a@example.com")
    src = tmp_path / "src.png"
    src.write_bytes(png_bytes(50, 40, "blue"))
    states = iter([R({"status": "running"}), R({"status": "done", "has_output": True, "backend": "gemini",
                                                "model": "m", "credits": 8, "balance": 42})])
    fc = FakeClient({("post", "/v1/jobs"): R({"id": "j1", "credits": 8, "balance": 42}),
                     ("get", "/v1/jobs/j1/output"): R(content=png_bytes(100, 80)),
                     ("get", "/v1/jobs/j1"): lambda: next(states)})
    monkeypatch.setattr(cloud, "_client", lambda url=None, token=None: fc)
    out = tmp_path / "out.png"
    res = cloud.CloudBackend().run(EditJob((str(src),), "frame it", 3), out)
    sent = fc.calls[0][2]["json"]
    assert sent["job"]["images"] == ["@0"] and base64.b64decode(sent["inputs"]["0"]) == src.read_bytes()
    assert Image.open(out).size == (50, 40) and res.meta == {"credits": 8, "balance": 42}


def test_out_of_credits_names_the_top_up(account, monkeypatch):
    cloud.save("http://svc", "tok", "a@example.com")
    fc = FakeClient({("post", "/v1/jobs"): R({"detail": "This job needs 9 credits."}, status=402)})
    monkeypatch.setattr(cloud, "_client", lambda url=None, token=None: fc)
    with pytest.raises(cloud.CloudError, match="studio cloud buy"):
        cloud.run_job(TextJob("x"), None)


def test_the_cloud_is_the_last_provider_tried():
    names = [b.name for b in router.backends() if not b.local]
    assert names[-1] == "cloud"


# ---------------------------------------------------------------- video routed out of animate

@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_a_provider_clip_becomes_frames_at_the_asked_length_and_size(tmp_path, monkeypatch):
    import subprocess
    from engine import animate
    clip = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=320x180:rate=30:duration=4", "-pix_fmt", "yuv420p", str(clip)], check=True)
    frames = animate.clip_frames(clip, tmp_path / "frames", 2.5, (200, 200), log=lambda m: None)
    assert len(frames) == round(2.5 * animate.FPS) + 1
    assert Image.open(frames[0]).size == (200, 200)


def test_animate_hands_the_clip_to_a_provider_when_the_policy_says_so(tmp_path, monkeypatch):
    from engine import animate
    still = tmp_path / "s.png"
    still.write_bytes(png_bytes(64, 64))
    seen = {}

    def provider(st, prompt, seconds, seed, out, size, end_image=None, **kw):
        seen.update(prompt=prompt, seconds=seconds, size=size)
        return True
    monkeypatch.setattr(router, "video_on_provider", provider)
    monkeypatch.setattr(animate, "clip_frames", lambda clip, d, s, size, log: [Path("f1.png")])
    frames = animate.animate(still, "a cup", "steam rises", 3.0, 1, tmp_path / "w", log=lambda m: None)
    assert frames == [Path("f1.png")] and seen["size"] == (64, 64) and "steam rises" in seen["prompt"]
