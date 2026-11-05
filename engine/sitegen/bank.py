"""Patterns for the site writer: one real section of each type, taken from the examples that ship with the engine.

A local text model cannot hold the spec's JSON schema (a film scene's alone is longer than its context), but it copies
the shape of a real section well. Only sections that need no files are used, since a generated project has none: every
picture it shows is made from a prompt. The pattern's copy is never kept; the writer rewrites all of it.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
SKIP_PROJECTS = {"showcase"}              # a gallery of the other examples, not a site about something
FILE_RE = re.compile(r"^(?:\.\./|inputs/|data/|models?/|previews/|recordings/)|\.(?:png|jpe?g|webp|gif|mp4|webm|glb|"
                     r"gltf|spz|ply|splat|csv|json|svg|pdb|cif|step|stp|3mf|obj|stl)$", re.I)


def files_in(node: Any) -> list[str]:
    """Every string in `node` that names a file (an input, a data table, a model) rather than a link or copy."""
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "href":
                continue
            out += files_in(v)
    elif isinstance(node, list):
        for v in node:
            out += files_in(v)
    elif isinstance(node, str) and FILE_RE.search(node.strip()):
        out.append(node)
    return out


def _sections(path: Path) -> list[dict]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    site = data.get("outputs", {}).get("site") if path.name == "project.yaml" else data
    return [s for s in (site or {}).get("sections") or [] if isinstance(s, dict) and s.get("type")]


@lru_cache(maxsize=1)
def load(root: Path = EXAMPLES) -> dict[str, list[dict]]:
    """{section type: [sections that need no files, shortest first]} from every example, each valid on its own."""
    from pydantic import TypeAdapter, ValidationError

    from ..spec import Section
    check = TypeAdapter(Section)
    out: dict[str, list[tuple[int, dict]]] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in SKIP_PROJECTS):
        for name in ("project.yaml", "site.yaml"):
            if (folder / name).exists():
                for s in _sections(folder / name):
                    if files_in(s):
                        continue
                    try:
                        check.validate_python(s)
                    except ValidationError:
                        continue
                    out.setdefault(s["type"], []).append((len(yaml.safe_dump(s)), s))
                break
    return {t: [s for _, s in sorted(v, key=lambda x: x[0])] for t, v in out.items()}


def pattern(kind: str, bank: dict[str, list[dict]]) -> dict | None:
    """The pattern for one section type: the example nearest the middle in length (the shortest are often stubs)."""
    found = bank.get(kind) or []
    return found[len(found) // 2] if found else None
