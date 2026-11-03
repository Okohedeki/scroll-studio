"""The model router: builders ask for a capability (an image, an edit, some text) and never name a provider.

    job = ImageJob(prompt="...", width=1024, height=1024, seed=7)
    result = route(job, out, policy=site.models)      # -> Result(path or text, backend, model, seconds)

Backends (engine/router/builtin.py) are local workers (ComfyUI) or provider APIs. A provider backend is available only
when its key is set, so a build with no keys runs exactly as before. The policy (`models:` in the spec) says which kind
to prefer and whether to fall back; every routed job is recorded in .build/_router/records.jsonl with its backend, model
and seed, so a candidate can be made again (docs/design/generation-engine.md).
"""
from __future__ import annotations

from .core import (Backend, EditJob, ImageJob, Job, NoBackend, Result, SpeechJob, TextJob, available, backends, choose, record,
                   register, route)

__all__ = ["Backend", "EditJob", "ImageJob", "Job", "NoBackend", "Result", "SpeechJob", "TextJob", "available", "backends", "choose",
           "record", "register", "route"]
