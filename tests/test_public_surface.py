"""Snapshots of the public surface (docs/compatibility.md): the site.yaml JSON Schema, every CLI command and option, and
every MCP tool with its inputs.

A change shows up as a diff that is reviewed like code. Adding is fine; removing or renaming something users rely on
is a breaking change and goes through a deprecation first. Re-record on purpose:

    UPDATE_SURFACE_SNAPSHOTS=1 python -m pytest tests/test_public_surface.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

SNAPS = Path(__file__).parent / "snapshots" / "surface"
UPDATE = os.environ.get("UPDATE_SURFACE_SNAPSHOTS") == "1"


def _default(value):
    """Defaults worth recording: literals. Anything that could come from a machine's config (paths, URLs) is not."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str) and not any(c in value for c in "/\\:") and len(value) < 60:
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(v, (bool, int, float, str)) for v in value):
        return [_default(v) for v in value]
    return "<computed>"


def cli_surface() -> dict:
    import typer
    from engine.cli import app

    # typer may ship its own copy of click, so commands and parameters are recognised by shape, not by class
    def walk(cmd) -> dict:
        out = {"help": (cmd.help or "").strip().split("\n")[0], "params": {}}
        for p in cmd.params:
            out["params"][p.name] = {
                "kind": "argument" if "Argument" in type(p).__name__ else "option",
                "opts": sorted(p.opts + list(getattr(p, "secondary_opts", []))),
                "type": str(getattr(p.type, "name", None) or type(p.type).__name__),
                "required": bool(p.required),
                "multiple": bool(getattr(p, "multiple", False)),
                "default": _default(p.default),
            }
        if hasattr(cmd, "commands"):
            out["commands"] = {name: walk(sub) for name, sub in sorted(cmd.commands.items())}
        return out

    return walk(typer.main.get_command(app))


def mcp_surface() -> dict:
    from engine import mcp_server

    def clean(schema):
        if isinstance(schema, dict):
            return {k: (_default(v) if k == "default" else clean(v)) for k, v in sorted(schema.items())}
        if isinstance(schema, list):
            return [clean(v) for v in schema]
        return schema

    tools = asyncio.run(mcp_server.mcp.list_tools())
    return {t.name: {"description": (t.description or "").strip().split("\n")[0], "input": clean(t.inputSchema)}
            for t in sorted(tools, key=lambda t: t.name)}


def schema_surface() -> dict:
    from engine.spec import Site
    return Site.model_json_schema()


def _removed(old, new, path="") -> list[str]:
    """Keys present in the old snapshot and gone from the new one: what a user may rely on."""
    out = []
    if isinstance(old, dict) and isinstance(new, dict):
        for k, v in old.items():
            if k not in new:
                out.append(f"{path}/{k}")
            else:
                out += _removed(v, new[k], f"{path}/{k}")
    return out


@pytest.mark.parametrize("name,make", [("schema", schema_surface), ("cli", cli_surface), ("mcp", mcp_surface)])
def test_public_surface(name, make):
    file = SNAPS / f"{name}.json"
    now = json.loads(json.dumps(make()))
    if UPDATE or not file.exists():
        SNAPS.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(now, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8",
                        newline="\n")
        return
    was = json.loads(file.read_text(encoding="utf-8"))
    if now == was:
        return
    removed = [p for p in _removed(was, now) if "/description" not in p and "/help" not in p]
    message = [f"The public {name} surface changed (tests/snapshots/surface/{name}.json)."]
    if removed:
        message.append("Removed or renamed, which breaks users (docs/compatibility.md: deprecate first, label the pull "
                       "request `breaking-change`):\n  " + "\n  ".join(removed[:30]))
    message.append("If the change is intended, re-record: UPDATE_SURFACE_SNAPSHOTS=1 python -m pytest "
                   "tests/test_public_surface.py, and commit the snapshot with the change.")
    pytest.fail("\n".join(message))


def test_removal_detection():
    old = {"a": {"b": 1, "c": {"d": 2}}, "e": 3}
    assert _removed(old, {"a": {"b": 1, "c": {}}, "e": 3, "f": 4}) == ["/a/c/d"]
    assert _removed(old, old) == []
