"""Helpers the backends share: keys from the environment, and image bytes fitted to an exact size."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional


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
