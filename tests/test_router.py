"""The model router (engine/router, issue #172): the policy picks a backend, local first by default; provider backends
are off until their key is set; every routed job is recorded. No test touches the network or a GPU."""
from __future__ import annotations

import base64
import io
import json
import sys
import types
from pathlib import Path
from typing import Optional

import pytest
from PIL import Image

from engine import router
from engine.router import builtin, core
from engine.router.core import ImageJob, NoBackend, Result, TextJob


class Fake:
    def __init__(self, name, local, kinds=("image",), ok=True):
        self.name, self.local, self.kinds, self.ok, self.calls = name, local, kinds, ok, []

    def available(self):
        return (True, "") if self.ok else (False, f"{self.name} is off")

    def model(self, kind):
        return f"{self.name}-model"

    def run(self, job, out, model=None):
        self.calls.append((job, model))
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 8), "white").save(out)
        return Result(self.name, model or self.model(job.kind), 0.0, path=out,
                      text="hello" if job.kind == "text" else None)


@pytest.fixture
def fakes(monkeypatch):
    """Only the fakes are registered while a test runs."""
    reg: dict = {}
    monkeypatch.setattr(core, "_REGISTRY", reg)
    monkeypatch.setattr(core, "backends", lambda: list(reg.values()))
    monkeypatch.setattr(core, "AVAILABLE_TTL", 0.0)
    local, provider = Fake("local:fake", True), Fake("cloud", False)
    for b in (local, provider):
        core.register(b)
    return local, provider


def test_local_comes_first(fakes):
    local, _ = fakes
    assert router.choose("image") is local


def test_prefer_provider(fakes):
    _, provider = fakes
    assert router.choose("image", {"prefer": "provider"}) is provider


def test_a_paid_provider_is_never_a_silent_fallback(fakes):
    local, provider = fakes
    local.ok = False
    with pytest.raises(NoBackend, match="not tried: cloud"):
        router.choose("image")
    assert router.choose("image", {"fallback": True}) is provider
    with pytest.raises(NoBackend, match="local:fake is off"):
        router.choose("image", {"fallback": False})


def test_a_provider_falls_back_to_local_for_free(fakes):
    local, provider = fakes
    provider.ok = False
    assert router.choose("image", {"prefer": "provider"}) is local
    with pytest.raises(NoBackend, match="cloud is off"):
        router.choose("image", {"prefer": "provider", "fallback": False})


def test_use_pins_a_backend(fakes):
    _, provider = fakes
    assert router.choose("image", {"use": {"image": "cloud"}}) is provider
    with pytest.raises(NoBackend, match="is not a image backend"):
        router.choose("image", {"use": {"image": "nowhere"}})


def test_a_pinned_backend_that_is_off_falls_back_unless_told_not_to(fakes):
    local, provider = fakes
    provider.ok = False
    assert router.choose("image", {"use": {"image": "cloud"}}) is local
    with pytest.raises(NoBackend, match="cloud is off"):
        router.choose("image", {"use": {"image": "cloud"}, "fallback": False})


def test_no_backend_says_why(fakes):
    for b in fakes:
        b.ok = False
    with pytest.raises(NoBackend, match="local:fake is off; cloud: cloud is off"):
        router.choose("image", {"fallback": True})
    with pytest.raises(NoBackend, match="none registered"):
        router.choose("text")


def test_route_passes_the_pinned_model_and_records(fakes, tmp_path):
    _, provider = fakes
    policy = {"use": {"image": "cloud"}, "model": {"image": "big"}}
    r = router.route(ImageJob("a jug", 64, 32, 3), tmp_path / "out.png", policy, build=tmp_path)
    assert r.backend == "cloud" and r.model == "big" and provider.calls[0][1] == "big"
    entry = json.loads((tmp_path / "_router" / "records.jsonl").read_text().splitlines()[-1])
    assert entry["backend"] == "cloud" and entry["job"]["seed"] == 3 and entry["model"] == "big"


def test_availability_is_remembered_briefly(fakes, monkeypatch):
    local, provider = fakes
    monkeypatch.setattr(core, "AVAILABLE_TTL", 60.0)
    core._SEEN.clear()
    assert router.choose("image") is local
    local.ok = False
    assert router.choose("image") is local          # still trusted within the TTL
    core._SEEN.clear()
    assert router.choose("image", {"fallback": True}) is provider


def test_a_spec_models_block_works_as_a_policy(fakes):
    from engine.spec import Models
    _, provider = fakes
    assert router.choose("image", Models(prefer="provider")) is provider


def test_the_builtin_backends_are_off_without_keys(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "STUDIO_TEXT_URL"):
        monkeypatch.delenv(k, raising=False)
    names = {b.name for b in router.backends()}
    assert {"local:comfy", "anthropic", "openai", "openai-compatible"} <= names
    off = {b.name: b.available()[0] for b in router.backends()}
    assert not off["anthropic"] and not off["openai"]


# ---------------------------------------------------------------- provider backends, with the network replaced

class Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def png_b64(w=40, h=20) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "red").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_openai_images_fits_the_requested_size(monkeypatch, tmp_path):
    import httpx
    sent = {}

    def post(url, **kw):
        sent.update(url=url, **kw)
        return Response({"data": [{"b64_json": png_b64()}]})
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(httpx, "post", post)
    b = builtin.OpenAIImages()
    r = b.run(ImageJob("a jug", 300, 100, 1), tmp_path / "x.png")
    assert sent["json"]["size"] == "1536x1024" and sent["url"].endswith("/images/generations")
    assert Image.open(r.path).size == (300, 100)


def test_openai_compatible_text(monkeypatch):
    import httpx
    sent = {}

    def post(url, **kw):
        sent.update(url=url, **kw)
        return Response({"model": "m", "choices": [{"message": {"content": "three directions"}}]})
    monkeypatch.setenv("STUDIO_TEXT_URL", "http://localhost:9000/")
    monkeypatch.setattr(httpx, "post", post)
    b = builtin.OpenAICompatibleText()
    assert b.local and b.available()[0]
    r = b.run(TextJob("write", system="be brief"), None)
    assert r.text == "three directions" and sent["url"] == "http://localhost:9000/v1/chat/completions"
    assert sent["json"]["messages"][0] == {"role": "system", "content": "be brief"}


def test_anthropic_text(monkeypatch):
    calls = {}

    class Messages:
        def create(self, **kw):
            calls.update(kw)
            block = types.SimpleNamespace(type="text", text="a direction")
            return types.SimpleNamespace(stop_reason="end_turn", content=[block], model=kw["model"])

    class Client:
        beta = types.SimpleNamespace(messages=Messages())

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    b = builtin.AnthropicBackend()
    assert b.available()[0]
    r = b.run(TextJob("write"), None)
    assert r.text == "a direction" and calls["model"] == "claude-opus-5-5"
    assert calls["extra_body"] == {"fallbacks": "default"}


def test_anthropic_refusal_is_an_error(monkeypatch):
    class Messages:
        def create(self, **kw):
            return types.SimpleNamespace(stop_reason="refusal", content=[], model=kw["model"])

    class Client:
        beta = types.SimpleNamespace(messages=Messages())

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    with pytest.raises(RuntimeError, match="declined"):
        builtin.AnthropicBackend().run(TextJob("write"), None)


# ---------------------------------------------------------------- generate_image goes through the router

def test_generate_image_uses_a_provider_backend_and_keeps_it_apart(fakes, tmp_path, monkeypatch):
    from engine import fidelity, inputs
    from engine.project import Project
    local, provider = fakes
    local.ok = False
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "site.yaml").write_text("name: T\nsections: []\nmodels: {fallback: true}\n", encoding="utf-8")
    monkeypatch.setattr(fidelity, "preview", lambda: None)
    p = Project(tmp_path / "p")
    out: Optional[Path] = inputs.generate_image(p, "a jug", 64, 64, 1, log=lambda m: None)
    assert out.exists() and provider.calls
    local_path = p.build / "_generated" / f"{inputs.generated_digest('a jug', 64, 64, 1)}.png"
    assert out != local_path
    assert inputs.generate_image(p, "a jug", 64, 64, 1, log=lambda m: None) == out and len(provider.calls) == 1


def test_generate_image_without_any_backend_says_what_to_do(fakes, tmp_path, monkeypatch):
    from engine import fidelity, inputs
    from engine.project import BuildError, Project
    for b in fakes:
        b.ok = False
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "site.yaml").write_text("name: T\nsections: []\n", encoding="utf-8")
    monkeypatch.setattr(fidelity, "preview", lambda: None)
    with pytest.raises(BuildError, match="ComfyUI is not running"):
        inputs.generate_image(Project(tmp_path / "p"), "a jug", 64, 64, 1, log=lambda m: None)


def test_edit_on_provider_only_when_the_policy_picks_one(fakes, tmp_path):
    local, provider = fakes
    local.kinds = provider.kinds = ("image", "edit")
    src = tmp_path / "in.png"
    Image.new("RGB", (8, 8)).save(src)
    out = tmp_path / "out.png"
    assert not router.edit_on_provider([src], "warmer", 1, 20, out)            # local preferred: the caller runs ComfyUI
    assert not provider.calls and not out.exists()
    assert router.edit_on_provider([src], "warmer", 1, 20, out, policy={"prefer": "provider"})
    assert out.exists() and provider.calls[-1][0].instruction == "warmer"
    router.use_policy({"use": {"edit": "cloud"}})
    try:
        assert router.edit_on_provider([src], "cooler", 1, 20, tmp_path / "o2.png")   # the build's policy, set once
    finally:
        router.use_policy(None)
    for b in fakes:
        b.ok = False
    assert not router.edit_on_provider([src], "x", 1, 20, tmp_path / "o3.png", policy={"fallback": True})
