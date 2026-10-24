"""The MCP server starts and answers (#83: the suite never imported it, so a new `mcp` major release broke it unseen).

Two checks with the SDK's own client: in memory (the server object, no process) and over stdio against the same
command that .mcp.json and the docs give MCP clients (`python -m engine.mcp_server`).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from engine import mcp_server
from engine.compile import themes

ROOT = Path(__file__).resolve().parent.parent


def _styles(result) -> list[dict]:
    assert not result.is_error
    data = result.structured_content
    return data["result"] if "result" in data else data


async def _exercise(client) -> tuple[set[str], list[dict]]:
    tools = {t.name for t in (await client.list_tools()).tools}
    styles = _styles(await client.call_tool("list_styles", {}))
    return tools, styles


def _check(tools: set[str], styles: list[dict]):
    assert {"list_projects", "build", "doctor", "list_styles", "world_check"} <= tools
    assert [s["name"] for s in styles] == list(themes.styles())
    assert len(styles) > 21 and all(s["label"] for s in styles)


def test_server_answers_in_memory():
    async def run():
        async with Client(mcp_server.mcp) as client:
            return await _exercise(client)
    _check(*asyncio.run(run()))


def test_server_answers_over_stdio():
    """Start `python -m engine.mcp_server` as a client would, list the tools and call one."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "engine.mcp_server"], cwd=ROOT)

    async def run():
        async with Client(params) as client:
            return await _exercise(client)
    _check(*asyncio.run(asyncio.wait_for(run(), timeout=120)))

