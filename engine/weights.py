"""Checksums for model files: what the engine downloads itself is verified before it is used.

`engine/models.yaml` records a `sha256` for each ComfyUI model file. A file the engine downloads (today: the GFPGAN
face-restore weights from `studio setup-comfy`) goes to a temporary name, is hashed, and only then moves into place; a
mismatch deletes it and raises. A `sha256` of `null` means "not pinned yet": the file is still used, with a warning.
"""
from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path
from typing import Callable

from .config import ENGINE

MODELS_YAML = ENGINE / "models.yaml"


class ChecksumError(RuntimeError):
    """A model file does not match the SHA-256 recorded for it."""


def sha256_file(path: Path | str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def model_entries(section: str = "comfyui") -> list[dict]:
    import yaml
    with open(MODELS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f).get(section) or []


def pinned_sha256(file: str) -> str | None:
    """The SHA-256 recorded in models.yaml for a ComfyUI model file (`folder/name`), or None when not pinned yet."""
    want = file.replace("\\", "/")
    for m in model_entries():
        if m.get("file") == want:
            return (m.get("sha256") or None) and str(m["sha256"]).lower()
    return None


def _clean(digest: str) -> str:
    d = str(digest).strip().lower()
    if d.startswith("sha256:"):
        d = d[7:]
    if len(d) != 64 or any(c not in "0123456789abcdef" for c in d):
        raise ValueError(f"not a SHA-256 (64 hex characters): {digest!r}")
    return d


def check_sha256(path: Path, expected: str, source: str) -> None:
    """Raise ChecksumError unless `path` hashes to `expected`. Never deletes: the caller decides what to do with the file."""
    want, got = _clean(expected), sha256_file(path)
    if got != want:
        raise ChecksumError(f"{Path(path).name} from {source} does not match its recorded SHA-256 "
                            f"(expected {want}, got {got}). The file was not used; the source may have changed or been tampered with.")


def download_verified(url: str, dest: Path, sha256: str | None, log: Callable[[str], None] = print,
                      fetch: Callable[[str, str], object] | None = None) -> Path:
    """Download `url` to `dest` through a temporary name and move it into place only when its SHA-256 matches.

    On a mismatch the temporary file is deleted and ChecksumError says which file, the expected and actual hash and the
    source. With `sha256` None the file is accepted with a warning (not pinned yet). `fetch(url, path)` is the downloader
    (default: urllib), replaceable in tests."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.unlink(missing_ok=True)
    try:
        (fetch or urllib.request.urlretrieve)(url, str(tmp))
        if sha256:
            check_sha256(tmp, sha256, url)
        else:
            log(f"  warning: {dest.name} has no pinned SHA-256 in engine/models.yaml, so its contents were not verified "
                f"(sha256 {sha256_file(tmp)})")
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest
