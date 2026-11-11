"""The built-in backends. Local: ComfyUI (Z-Image Turbo stills, Qwen-Image-Edit edits). Providers, each used only when
its key is set: Anthropic (text), OpenAI (images and edits), ElevenLabs (speech) and any OpenAI-compatible text server (`text_url` in
studio.toml, for example a model served on this machine). Licences and terms belong to each provider."""
from __future__ import annotations

import base64
import io
import os
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from ..config import settings
from .core import EditJob, ImageJob, Job, Kind, Result, SpeechJob, TextJob, register


def _key(*names: str) -> Optional[str]:
    return next((os.environ[n] for n in names if os.environ.get(n)), None)


def _fit(data: bytes, out: Path, width: int, height: int) -> Path:
    """Write image bytes to `out` at exactly width x height (scaled to cover, centre-cropped)."""
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    s = max(width / im.width, height / im.height)
    im = im.resize((max(width, round(im.width * s)), max(height, round(im.height * s))), Image.LANCZOS)
    left, top = (im.width - width) // 2, (im.height - height) // 2
    out.parent.mkdir(parents=True, exist_ok=True)
    im.crop((left, top, left + width, top + height)).save(out)
    return out


# ---------------------------------------------------------------- local

class ComfyBackend:
    name = "local:comfy"
    local = True
    kinds: tuple[Kind, ...] = ("image", "edit")

    def available(self) -> tuple[bool, str]:
        from ..backends import comfy
        return (True, "") if comfy.alive() else (False, f"ComfyUI is not running at {comfy.COMFY}")

    def model(self, kind: Kind) -> str:
        return "z-image-turbo" if kind == "image" else "qwen-image-edit"

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        from ..backends import comfy
        assert out is not None
        tag = out.stem[:40]
        if isinstance(job, ImageJob):
            graph = comfy.build_txt2img_graph(job.prompt, job.width, job.height, job.seed, prefix=f"studio/{tag}")
        elif isinstance(job, EditJob):
            names = [comfy.upload(p) for p in job.images]
            graph = comfy.build_qwen_edit_graph(names, job.instruction, job.seed, job.steps, prefix=f"studio/edit_{tag}")
        else:
            raise TypeError(f"{self.name} does not do {job.kind} jobs")
        images = comfy.run(graph, poll=2)
        tmp = Path(comfy.fetch(images, str(out.parent / f"_{tag}")))
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp / "0001.png"), out)
        shutil.rmtree(tmp, ignore_errors=True)
        return Result(self.name, self.model(job.kind), 0.0, path=out)


# ---------------------------------------------------------------- providers

class AnthropicBackend:
    """Text through the Claude API (the `anthropic` package). Key: ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN)."""
    name = "anthropic"
    local = False
    kinds: tuple[Kind, ...] = ("text",)
    default_model = "claude-opus-5-5"

    def available(self) -> tuple[bool, str]:
        if not _key("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            return False, "ANTHROPIC_API_KEY is not set"
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, "the anthropic package is not installed (pip install anthropic)"
        return True, ""

    def model(self, kind: Kind) -> str:
        return settings().get("anthropic_model") or self.default_model

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import anthropic
        assert isinstance(job, TextJob)
        model = model or self.model("text")
        client = anthropic.Anthropic()
        kwargs = {"system": job.system} if job.system else {}
        if job.temperature is not None:
            kwargs["temperature"] = job.temperature
        # a declined request is re-run on a fallback model the API picks ("default" routing)
        response = client.beta.messages.create(
            model=model, max_tokens=job.max_tokens, messages=[{"role": "user", "content": job.prompt}],
            betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"}, **kwargs)
        if response.stop_reason == "refusal":
            raise RuntimeError(f"{model} declined this text job")
        text = "".join(b.text for b in response.content if b.type == "text")
        return Result(self.name, getattr(response, "model", None) or model, 0.0, text=text)


class OpenAICompatibleText:
    """Text from any server with an OpenAI-style /v1/chat/completions endpoint: `text_url` in studio.toml (or
    STUDIO_TEXT_URL), with STUDIO_TEXT_KEY when the server needs a key. A server on localhost counts as local."""
    name = "openai-compatible"
    kinds: tuple[Kind, ...] = ("text",)

    @property
    def url(self) -> Optional[str]:
        return os.environ.get("STUDIO_TEXT_URL") or settings().get("text_url")

    @property
    def local(self) -> bool:
        return (urlparse(self.url or "").hostname or "") in ("localhost", "127.0.0.1", "::1")

    def available(self) -> tuple[bool, str]:
        return (True, "") if self.url else (False, "text_url is not set in studio.toml")

    def model(self, kind: Kind) -> str:
        return os.environ.get("STUDIO_TEXT_MODEL") or settings().get("text_model") or "default"

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import httpx
        assert isinstance(job, TextJob)
        model = model or self.model("text")
        messages = [{"role": "system", "content": job.system}] if job.system else []
        messages.append({"role": "user", "content": job.prompt})
        key = _key("STUDIO_TEXT_KEY")
        body = {"model": model, "messages": messages, "max_tokens": job.max_tokens}
        if job.temperature is not None:
            body["temperature"] = job.temperature
        if job.seed is not None:
            body["seed"] = job.seed
        if job.json:
            body["response_format"] = {"type": "json_object"}
        r = httpx.post(self.url.rstrip("/") + "/v1/chat/completions", timeout=600,
                       headers={"Authorization": f"Bearer {key}"} if key else {}, json=body)
        r.raise_for_status()
        data = r.json()
        return Result(self.name, data.get("model") or model, 0.0, text=data["choices"][0]["message"]["content"])

    def release(self, model: Optional[str] = None) -> bool:
        """Free the GPU memory the text model holds, so ComfyUI can render next. Servers that hold a model until told
        otherwise (Ollama) are told; any other server is left as it is. True when a model was unloaded."""
        import httpx
        if not (self.url and self.local):
            return False
        base = self.url.rstrip("/").removesuffix("/v1")
        try:
            if httpx.get(base + "/api/version", timeout=3).status_code != 200:      # not an Ollama server
                return False
            r = httpx.post(base + "/api/generate", timeout=30, json={"model": model or self.model("text"), "keep_alive": 0})
            return r.status_code == 200
        except httpx.HTTPError:
            return False


class OpenAIImages:
    """Images and edits through OpenAI's Images API. Key: OPENAI_API_KEY. The image is scaled and cropped to the size
    the job asks for."""
    name = "openai"
    local = False
    kinds: tuple[Kind, ...] = ("image", "edit")
    base = "https://api.openai.com/v1"

    def available(self) -> tuple[bool, str]:
        return (True, "") if _key("OPENAI_API_KEY") else (False, "OPENAI_API_KEY is not set")

    def model(self, kind: Kind) -> str:
        return settings().get("openai_image_model") or "gpt-image-1"

    @staticmethod
    def size(width: int, height: int) -> str:
        r = width / height
        return "1536x1024" if r > 1.2 else "1024x1536" if r < 1 / 1.2 else "1024x1024"

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import httpx
        assert out is not None
        model = model or self.model(job.kind)
        headers = {"Authorization": f"Bearer {_key('OPENAI_API_KEY')}"}
        if isinstance(job, ImageJob):
            w, h = job.width, job.height
            r = httpx.post(f"{self.base}/images/generations", headers=headers, timeout=600,
                           json={"model": model, "prompt": job.prompt, "n": 1, "size": self.size(w, h)})
        elif isinstance(job, EditJob):
            from PIL import Image
            with Image.open(job.images[0]) as im:
                w, h = im.size
            files = [("image[]", (Path(p).name, Path(p).read_bytes(), "image/png")) for p in job.images]
            r = httpx.post(f"{self.base}/images/edits", headers=headers, timeout=600, files=files,
                           data={"model": model, "prompt": job.instruction, "n": "1", "size": self.size(w, h)})
        else:
            raise TypeError(f"{self.name} does not do {job.kind} jobs")
        r.raise_for_status()
        _fit(base64.b64decode(r.json()["data"][0]["b64_json"]), out, w, h)
        return Result(self.name, model, 0.0, path=out)


class ElevenLabsSpeech:
    """Voiceover through ElevenLabs' text-to-speech API. Key: ELEVENLABS_API_KEY; voice and model from studio.toml
    (elevenlabs_voice, elevenlabs_model) or the job. Writes an MP3."""
    name = "elevenlabs"
    local = False
    kinds: tuple[Kind, ...] = ("speech",)
    base = "https://api.elevenlabs.io/v1"
    default_voice = "21m00Tcm4TlvDq8ikWAM"

    def available(self) -> tuple[bool, str]:
        return (True, "") if _key("ELEVENLABS_API_KEY") else (False, "ELEVENLABS_API_KEY is not set")

    def model(self, kind: Kind) -> str:
        return settings().get("elevenlabs_model") or "eleven_multilingual_v2"

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import httpx
        assert isinstance(job, SpeechJob) and out is not None
        model = model or self.model("speech")
        voice = job.voice or settings().get("elevenlabs_voice") or self.default_voice
        r = httpx.post(f"{self.base}/text-to-speech/{voice}", timeout=300,
                       headers={"xi-api-key": _key("ELEVENLABS_API_KEY"), "accept": "audio/mpeg"},
                       json={"text": job.text, "model_id": model})
        r.raise_for_status()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
        return Result(self.name, model, 0.0, path=out, meta={"voice": voice})


for _b in (ComfyBackend(), OpenAICompatibleText(), AnthropicBackend(), OpenAIImages(), ElevenLabsSpeech()):
    register(_b)
