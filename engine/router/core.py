"""Jobs, the backend protocol, the registry and the policy that picks a backend (engine/router/__init__.py)."""
from __future__ import annotations

import json
import time
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional, Protocol, Union

Kind = Literal["image", "edit", "text", "speech", "video"]


@dataclass(frozen=True)
class ImageJob:
    prompt: str
    width: int
    height: int
    seed: int
    kind: Kind = "image"


@dataclass(frozen=True)
class EditJob:
    images: tuple[str, ...]          # paths of the source images, the first is the one edited
    instruction: str
    seed: int
    steps: int = 20
    kind: Kind = "edit"


@dataclass(frozen=True)
class TextJob:
    prompt: str
    system: str = ""
    max_tokens: int = 4000
    temperature: Optional[float] = None    # the backend's default when unset
    seed: Optional[int] = None             # for backends that sample reproducibly with one (local servers)
    json: bool = False                     # ask for a JSON object where the backend supports it
    kind: Kind = "text"


@dataclass(frozen=True)
class SpeechJob:
    text: str
    voice: str = ""                  # the backend's voice id; empty: its default
    kind: Kind = "speech"


@dataclass(frozen=True)
class VideoJob:
    image: str                       # path of the still the clip starts on
    prompt: str                      # what moves, and how
    seconds: float
    width: int                       # the size the frames are wanted at (a provider renders at its nearest size)
    height: int
    seed: int
    end_image: Optional[str] = None  # a still the clip should land on, where the backend can
    kind: Kind = "video"


Job = Union[ImageJob, EditJob, TextJob, SpeechJob, VideoJob]


@dataclass
class Result:
    backend: str
    model: str
    seconds: float
    path: Optional[Path] = None      # image, edit and speech jobs; an MP4 for video jobs
    text: Optional[str] = None       # text jobs
    meta: dict = field(default_factory=dict)


class Backend(Protocol):
    name: str                        # "local:comfy", "anthropic", ...
    local: bool                      # runs on this machine (no key, no network beyond localhost)
    kinds: tuple[Kind, ...]

    def available(self) -> tuple[bool, str]:
        """(usable now, why not)."""

    def model(self, kind: Kind) -> str:
        """The model this backend would use for a job of `kind`."""

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        """Do the job (on `model`, else the backend's default). Image and edit jobs write `out`; text jobs return
        the text."""


class NoBackend(RuntimeError):
    pass


_REGISTRY: dict[str, Backend] = {}


def register(backend: Backend) -> Backend:
    _REGISTRY[backend.name] = backend
    return backend


def backends() -> list[Backend]:
    from . import builtin  # noqa: F401  (registers the built-in backends)
    return list(_REGISTRY.values())


_SEEN: dict[int, tuple[float, tuple[bool, str]]] = {}
AVAILABLE_TTL = 15.0      # seconds a backend's answer is trusted: a stopped ComfyUI costs seconds to ask, every job


def check(b: Backend) -> tuple[bool, str]:
    """b.available(), remembered for AVAILABLE_TTL seconds."""
    hit = _SEEN.get(id(b))
    if hit and time.time() - hit[0] < AVAILABLE_TTL:
        return hit[1]
    res = b.available()
    _SEEN[id(b)] = (time.time(), res)
    return res


def available(kind: Kind) -> list[Backend]:
    return [b for b in backends() if kind in b.kinds and check(b)[0]]


def _policy(policy: Any) -> dict:
    if policy is None:
        return {}
    if hasattr(policy, "model_dump"):
        return policy.model_dump(exclude_none=True)
    return dict(policy)


def choose(kind: Kind, policy: Any = None) -> Backend:
    """The backend for a job of `kind`: the one the policy pins, else the first available of the preferred kind (local
    by default). A paid provider is never a silent fallback: when local is preferred, providers are tried only with an
    explicit `fallback: true` (or a pin). Falling back from a provider to local models is free, so it is the default;
    `fallback: false` keeps to the preferred kind alone. Raises NoBackend saying what to set up."""
    p = _policy(policy)
    fb = p.get("fallback")
    name = (p.get("use") or {}).get(kind)
    candidates = [b for b in backends() if kind in b.kinds]
    if name:
        b = next((b for b in candidates if b.name == name), None)
        if b is None:
            raise NoBackend(f"models.use.{kind} names {name!r}, which is not a {kind} backend: "
                            f"use one of {', '.join(c.name for c in candidates) or 'none'}")
        ok, why = check(b)
        if ok:
            return b
        if fb is False:
            raise NoBackend(f"models.use.{kind} is {name}, which is not available: {why}")
    prefer_local = p.get("prefer", "local") == "local"

    def allowed(b: Backend) -> bool:
        return (prefer_local or fb is not False) if b.local else (not prefer_local or fb is True)
    ordered = sorted((b for b in candidates if allowed(b)), key=lambda b: (b.local != prefer_local, candidates.index(b)))
    reasons = []
    for b in ordered:
        ok, why = check(b)
        if ok:
            return b
        reasons.append(f"{b.name}: {why}")
    skipped = [b.name for b in candidates if not allowed(b)]
    extra = f"; not tried: {', '.join(skipped)} (set models.prefer: provider or fallback: true)" if skipped else ""
    raise NoBackend(f"no {kind} backend can run here ({'; '.join(reasons) or 'none registered'}{extra})")


CURRENT: ContextVar = ContextVar("router_policy", default=None)


def use_policy(policy: Any) -> None:
    """The `models:` policy for jobs started from here on in this build (builders deep inside it read it)."""
    CURRENT.set(policy)


def edit_on_provider(images: list, instruction: str, seed: int, steps: int, out: Path, policy: Any = None,
                     build: Optional[Path] = None, log=lambda m: None) -> bool:
    """Run an image edit on a provider backend when the policy picks one, writing `out`. False means the local
    ComfyUI path should run as before (its graph, steps and strength unchanged), including when nothing can run."""
    policy = CURRENT.get() if policy is None else policy
    try:
        b = choose("edit", policy)
    except NoBackend:
        return False
    if b.local:
        return False
    route(EditJob(tuple(str(i) for i in images), instruction, seed, steps), out, policy, build=build, log=log)
    return True


def video_on_provider(still: Path, prompt: str, seconds: float, seed: int, out: Path, size: tuple[int, int],
                      end_image: Optional[Path] = None, policy: Any = None, build: Optional[Path] = None,
                      log=lambda m: None) -> bool:
    """Animate `still` on a provider backend when the policy picks one, writing the MP4 `out`. False means the local
    ComfyUI path (LTX-2.3 or Wan 2.2) should run as before, including when no video backend can run."""
    policy = CURRENT.get() if policy is None else policy
    try:
        b = choose("video", policy)
    except NoBackend:
        return False
    if b.local:
        return False
    route(VideoJob(str(still), prompt, seconds, size[0], size[1], seed, str(end_image) if end_image else None), out,
          policy, build=build, log=log)
    return True


def record(build: Path, job: Job, result: Result) -> None:
    """Append what made this result to .build/_router/records.jsonl (the job, the backend, its model, the time)."""
    path = build / "_router" / "records.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"at": round(time.time(), 1), "job": asdict(job), "backend": result.backend, "model": result.model,
             "seconds": result.seconds, "out": str(result.path) if result.path else None, **result.meta}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def route(job: Job, out: Optional[Path] = None, policy: Any = None, build: Optional[Path] = None,
          log=lambda m: None) -> Result:
    """Run `job` on the backend `choose` picks; record it under `build` when given."""
    b = choose(job.kind, policy)
    p = _policy(policy)
    model = (p.get("model") or {}).get(job.kind) if (p.get("use") or {}).get(job.kind) == b.name else None
    if not b.local:
        log(f"  {job.kind} job on {b.name} ({model or b.model(job.kind)})")
    t0 = time.time()
    result = b.run(job, out, model)
    result.seconds = round(time.time() - t0, 2)
    if build is not None:
        record(build, job, result)
    return result
