"""The frontier provider backends beside the first ones in builtin.py: OpenAI text, Google Gemini (images, edits, text
and image-to-video), Black Forest Labs FLUX (images and edits) and Runway (image-to-video). Each is used only when its
key is set, and never in place of local models unless the spec's `models:` asks for providers. The models each one
runs by default are settings in studio.toml, so a newer model is a one-line change."""
from __future__ import annotations

import base64
import io
import math
import time
from pathlib import Path
from typing import Callable, Optional

from ..config import settings
from .util import _fit, _key
from .core import EditJob, ImageJob, Job, Kind, Result, TextJob, VideoJob


def poll(check: Callable[[], object], every: float = 2.0, timeout: float = 30 * 60, what: str = "job"):
    """Call `check()` until it returns something other than None, every `every` seconds, for at most `timeout`."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        got = check()
        if got is not None:
            return got
        time.sleep(every)
    raise TimeoutError(f"the provider's {what} did not finish within {timeout / 60:.0f} minutes")


def image_b64(path: str, longest: int = 1536) -> tuple[str, str]:
    """A source image as base64 PNG, scaled down so its longest side is at most `longest` (uploads stay small)."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if max(im.size) > longest:
        s = longest / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode(), "image/png"


def nearest(width: int, height: int, ratios: dict) -> str:
    """The key of `ratios` (name -> width/height) closest to width/height, compared in log space."""
    r = math.log(width / height)
    return min(ratios, key=lambda k: abs(math.log(ratios[k]) - r))


def download(url: str, out: Path, headers: Optional[dict] = None) -> Path:
    import httpx
    r = httpx.get(url, headers=headers or {}, timeout=600, follow_redirects=True)
    r.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return out


def source_size(path: str) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


class OpenAIText:
    """Text through OpenAI's Chat Completions API. Key: OPENAI_API_KEY; model `openai_text_model` in studio.toml."""
    name = "openai-text"
    local = False
    kinds: tuple[Kind, ...] = ("text",)
    base = "https://api.openai.com/v1"
    default_model = "gpt-5"

    def available(self) -> tuple[bool, str]:
        return (True, "") if _key("OPENAI_API_KEY") else (False, "OPENAI_API_KEY is not set")

    def model(self, kind: Kind) -> str:
        return settings().get("openai_text_model") or self.default_model

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import httpx
        assert isinstance(job, TextJob)
        model = model or self.model("text")
        messages = ([{"role": "developer", "content": job.system}] if job.system else []) + \
            [{"role": "user", "content": job.prompt}]
        body: dict = {"model": model, "messages": messages, "max_completion_tokens": job.max_tokens}
        if job.json:
            body["response_format"] = {"type": "json_object"}
        if job.seed is not None:
            body["seed"] = job.seed
        r = httpx.post(f"{self.base}/chat/completions", timeout=600, json=body,
                       headers={"Authorization": f"Bearer {_key('OPENAI_API_KEY')}"})
        r.raise_for_status()
        data = r.json()
        return Result(self.name, data.get("model") or model, 0.0, text=data["choices"][0]["message"]["content"])


class GeminiBackend:
    """Google's Gemini API: images and edits (Nano Banana), text, and image-to-video (Gemini Omni Flash). Key:
    GEMINI_API_KEY (or GOOGLE_API_KEY); models `gemini_image_model`, `gemini_text_model` and `gemini_video_model`."""
    name = "gemini"
    local = False
    kinds: tuple[Kind, ...] = ("image", "edit", "text", "video")
    base = "https://generativelanguage.googleapis.com/v1beta"
    defaults = {"image": "gemini-3.1-flash-image", "edit": "gemini-3.1-flash-image", "text": "gemini-flash-latest",
                "video": "gemini-omni-1.2-flash"}
    settings_keys = {"image": "gemini_image_model", "edit": "gemini_image_model", "text": "gemini_text_model",
                     "video": "gemini_video_model"}
    ratios = {"1:1": 1, "2:3": 2 / 3, "3:2": 1.5, "3:4": 0.75, "4:3": 4 / 3, "4:5": 0.8, "5:4": 1.25, "9:16": 9 / 16,
              "16:9": 16 / 9, "21:9": 21 / 9}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _key("GEMINI_API_KEY", "GOOGLE_API_KEY") else (False, "GEMINI_API_KEY is not set")

    def model(self, kind: Kind) -> str:
        return settings().get(self.settings_keys[kind]) or self.defaults[kind]

    @property
    def headers(self) -> dict:
        return {"x-goog-api-key": _key("GEMINI_API_KEY", "GOOGLE_API_KEY") or ""}

    @staticmethod
    def parts(data: dict) -> list:
        cands = data.get("candidates") or []
        if not cands:
            why = (data.get("promptFeedback") or {}).get("blockReason") or "no answer"
            raise RuntimeError(f"Gemini returned nothing ({why})")
        return (cands[0].get("content") or {}).get("parts") or []

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import httpx
        model = model or self.model(job.kind)
        if isinstance(job, VideoJob):
            return self._video(job, out, model)
        url = f"{self.base}/models/{model}:generateContent"
        if isinstance(job, TextJob):
            gen: dict = {"maxOutputTokens": job.max_tokens}
            if job.temperature is not None:
                gen["temperature"] = job.temperature
            if job.seed is not None:
                gen["seed"] = job.seed
            if job.json:
                gen["responseMimeType"] = "application/json"
            body: dict = {"contents": [{"role": "user", "parts": [{"text": job.prompt}]}], "generationConfig": gen}
            if job.system:
                body["systemInstruction"] = {"parts": [{"text": job.system}]}
            r = httpx.post(url, headers=self.headers, json=body, timeout=600)
            r.raise_for_status()
            text = "".join(p.get("text", "") for p in self.parts(r.json()) if not p.get("thought"))
            return Result(self.name, model, 0.0, text=text)
        assert out is not None
        if isinstance(job, ImageJob):
            w, h = job.width, job.height
            parts: list = [{"text": job.prompt}]
        elif isinstance(job, EditJob):
            w, h = source_size(job.images[0])
            parts = []
            for p in job.images:
                data, mime = image_b64(p)
                parts.append({"inlineData": {"mimeType": mime, "data": data}})
            parts.append({"text": job.instruction})
        else:
            raise TypeError(f"{self.name} does not do {job.kind} jobs")
        body = {"contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"responseModalities": ["IMAGE"],
                                     "imageConfig": {"aspectRatio": nearest(w, h, self.ratios)}}}
        r = httpx.post(url, headers=self.headers, json=body, timeout=600)
        r.raise_for_status()
        blob = next((p.get("inlineData") or p.get("inline_data") for p in self.parts(r.json())
                     if p.get("inlineData") or p.get("inline_data")), None)
        if not blob:
            raise RuntimeError(f"{model} answered without an image")
        _fit(base64.b64decode(blob["data"]), out, w, h)
        return Result(self.name, model, 0.0, path=out)

    def _video(self, job: VideoJob, out: Optional[Path], model: str) -> Result:
        import httpx
        assert out is not None
        data, mime = image_b64(job.image, 1280)
        inputs: list = [{"type": "image", "data": data, "mime_type": mime}]
        prompt = job.prompt
        if job.end_image:               # two frames: the clip interpolates from the first to the second
            end, end_mime = image_b64(job.end_image, 1280)
            inputs.append({"type": "image", "data": end, "mime_type": end_mime})
            prompt += " The clip starts on the first image and ends on the second."
        inputs.append({"type": "text", "text": prompt})
        seconds = min(10 if job.end_image else 15, max(3, round(job.seconds)))
        body = {"model": model, "input": inputs,
                "response_format": {"type": "video", "aspect_ratio": "16:9" if job.width >= job.height else "9:16",
                                    "resolution": "720p", "duration": f"{seconds}s", "delivery": "uri"}}
        r = httpx.post(f"{self.base}/interactions", headers=self.headers, json=body, timeout=1800)
        r.raise_for_status()
        clip = next((c for step in r.json().get("steps", []) if step.get("type") == "model_output"
                     for c in step.get("content", []) if c.get("type") == "video"), None)
        if clip is None:
            raise RuntimeError(f"{model} answered without a video")
        out.parent.mkdir(parents=True, exist_ok=True)
        if clip.get("data"):
            out.write_bytes(base64.b64decode(clip["data"]))
            return Result(self.name, model, 0.0, path=out, meta={"seconds_made": seconds})
        fid = "files/" + clip["uri"].rstrip("/").split("files/")[-1]

        def active():
            f = httpx.get(f"{self.base}/{fid}", headers=self.headers, timeout=60)
            f.raise_for_status()
            state = f.json().get("state")
            if state == "FAILED":
                raise RuntimeError(f"{model}: the video file failed")
            return True if state == "ACTIVE" else None
        poll(active, 3, 20 * 60, "video file")
        download(f"{self.base}/{fid}:download?alt=media", out, self.headers)
        return Result(self.name, model, 0.0, path=out, meta={"seconds_made": seconds})


class FluxBackend:
    """Images and edits through Black Forest Labs' API (FLUX.2). Key: BFL_API_KEY; model `flux_model` (default
    flux-2-pro) and host `bfl_url` (default the global https://api.bfl.ai/v1) in studio.toml."""
    name = "flux"
    local = False
    kinds: tuple[Kind, ...] = ("image", "edit")
    default_model = "flux-2-pro"
    failed = ("Error", "Failed", "Content Moderated", "Request Moderated", "Task not found")

    def available(self) -> tuple[bool, str]:
        return (True, "") if _key("BFL_API_KEY") else (False, "BFL_API_KEY is not set")

    def model(self, kind: Kind) -> str:
        return settings().get("flux_model") or self.default_model

    @staticmethod
    def size(width: int, height: int, mp: float = 2.0) -> tuple[int, int]:
        """At most `mp` megapixels at the asked aspect, both sides multiples of 16."""
        s = min(1.0, (mp * 1_000_000 / (width * height)) ** 0.5)
        return max(256, round(width * s / 16) * 16), max(256, round(height * s / 16) * 16)

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import httpx
        assert out is not None
        model = model or self.model(job.kind)
        headers = {"x-key": _key("BFL_API_KEY") or "", "accept": "application/json"}
        if isinstance(job, ImageJob):
            w, h = job.width, job.height
            body: dict = {"prompt": job.prompt}
        elif isinstance(job, EditJob):
            w, h = source_size(job.images[0])
            body = {"prompt": job.instruction}
            for i, p in enumerate(job.images[:8]):
                body["input_image" if i == 0 else f"input_image_{i + 1}"] = image_b64(p)[0]
        else:
            raise TypeError(f"{self.name} does not do {job.kind} jobs")
        rw, rh = self.size(w, h)
        body.update(width=rw, height=rh, seed=job.seed % 2**32, output_format="png")
        base = (settings().get("bfl_url") or "https://api.bfl.ai/v1").rstrip("/")
        r = httpx.post(f"{base}/{model}", headers=headers, json=body, timeout=120)
        r.raise_for_status()
        polling = r.json()["polling_url"]

        def ready():
            p = httpx.get(polling, headers=headers, timeout=60)
            p.raise_for_status()
            d = p.json()
            if d.get("status") == "Ready":
                return d["result"]["sample"]
            if d.get("status") in self.failed:
                raise RuntimeError(f"{model}: {d.get('status')}")
            return None
        sample = poll(ready, 1.5, 10 * 60, "image")
        got = httpx.get(sample, timeout=300, follow_redirects=True)    # a signed URL, valid for minutes
        got.raise_for_status()
        _fit(got.content, out, w, h)
        return Result(self.name, model, 0.0, path=out)


class RunwayBackend:
    """Image-to-video through Runway's API. Key: RUNWAYML_API_SECRET; model `runway_model` (default gen4.5). Clips are
    2 to 10 seconds at Runway's nearest ratio; the engine scales the frames to the size it wants."""
    name = "runway"
    local = False
    kinds: tuple[Kind, ...] = ("video",)
    base = "https://api.dev.runwayml.com/v1"
    default_model = "gen4.5"
    ratios = {"1280:720": 1280 / 720, "720:1280": 720 / 1280, "1104:832": 1104 / 832, "960:960": 1.0,
              "832:1104": 832 / 1104, "1584:672": 1584 / 672}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _key("RUNWAYML_API_SECRET") else (False, "RUNWAYML_API_SECRET is not set")

    def model(self, kind: Kind) -> str:
        return settings().get("runway_model") or self.default_model

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        import httpx
        assert isinstance(job, VideoJob) and out is not None
        model = model or self.model("video")
        headers = {"Authorization": f"Bearer {_key('RUNWAYML_API_SECRET')}", "X-Runway-Version": "2024-11-06"}
        data, mime = image_b64(job.image, 1280)
        seconds = min(10, max(2, round(job.seconds)))
        body = {"model": model, "promptImage": f"data:{mime};base64,{data}", "promptText": job.prompt[:1000],
                "ratio": nearest(job.width, job.height, self.ratios), "duration": seconds,
                "seed": job.seed % 4294967295}
        r = httpx.post(f"{self.base}/image_to_video", headers=headers, json=body, timeout=120)
        r.raise_for_status()
        task = r.json()["id"]

        def ready():
            t = httpx.get(f"{self.base}/tasks/{task}", headers=headers, timeout=60)
            t.raise_for_status()
            d = t.json()
            if d.get("status") == "SUCCEEDED":
                return d["output"][0]
            if d.get("status") in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"{model}: {d.get('failure') or d.get('status')}")
            return None
        download(poll(ready, 5, 30 * 60, "video"), out)
        return Result(self.name, model, 0.0, path=out, meta={"seconds_made": seconds})
