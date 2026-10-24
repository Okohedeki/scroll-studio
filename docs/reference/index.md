# Reference

Three references are generated from the engine itself every time the site is built, so they match the code that
runs. Nothing in them is written by hand: a change to `engine/spec.py`, `engine/cli.py` or `engine/mcp_server.py`
changes these pages.

| Reference | Read from | What it lists |
| --- | --- | --- |
| [site.yaml](spec/index.md) | `engine/spec.py` (Pydantic) | Every model and field: type, default, allowed values, limits and what it does |
| [Command line](cli.md) | `engine/cli.py` (typer) | Every `studio` command, its arguments and options |
| [MCP tools](mcp.md) | `engine/mcp_server.py` (FastMCP) | Every tool Claude can call, and its inputs |

Hand-written pages explain how to use these: the [guide](../guide.md) for the workflow, [scenes](../scenes.md) and
[styles](../styles.md) for what each does, [architecture](../ENGINE.md) for how the engine is put together.

The same schema is available offline: `studio schema` prints the JSON Schema of `site.yaml`, and the MCP tool
`spec_schema` returns it, or one model of it.
