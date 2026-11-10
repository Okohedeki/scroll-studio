---
name: scroll-engine-dev
description: Add a capability to the DesignAI engine or fix it, instead of working around it in one site - where a change goes (spec field, scene builder, runtime player, style, router backend, CLI and MCP), how to test and verify it, and the repository's rules for issues, pull requests, bundles and changelog fragments. Use when a site needs something the engine cannot do, or when changing engine code.
---

# Change the engine, not the page

When a site needs something the engine cannot do, the fix goes into the engine so every site can use it. A one-off
script, a hand-edited page in `dist/`, or a picture made outside the engine is not a fix.

## Where a change goes

| The change | Where |
|---|---|
| a new field or option | `engine/spec.py` (site) or `engine/project_spec.py` (project): Pydantic models with descriptions. The schema, the Studio forms and the MCP tools all read them |
| how a scene is built offline | `engine/scenes/<type>.py` (one builder per scene type); shared stages in `engine/inputs.py` and friends |
| how a scene plays in the browser | `runtime/src/players/<type>.ts`; the scroll core is `runtime/src/index.ts` |
| how the page is laid out | `engine/compile/` (templates and themes); blocks in `engine/compile/templates/` |
| how a whole site scrolls | a style: `engine/styles/<name>/` plus `runtime/src/styles/<name>.ts`; contract in `engine/styles/README.md` |
| a model or provider | a backend in `engine/router/builtin.py`; jobs and policy in `engine/router/core.py` |
| a command or agent tool | `engine/cli.py` and `engine/mcp_server.py` (keep them in step) |
| a commerce output | `engine/stills/`, `engine/ads.py`, `engine/listing.py`, `engine/video.py`, `engine/layouts.py` |

Design for every site: a field that only one site could use is the wrong field. Never commit machine paths, usernames
or a client's content; examples use invented brands.

## Verify it

- `python -m pytest -q` (no GPU or network needed; models are stood in) and `ruff check .`.
- After changing `runtime/src`: `npm run build:runtime` and commit the bundle in `engine/compile/static/` (CI rebuilds
  it and fails on any difference). After changing the UI: `npm run build:ui`.
- Public surface changes (CLI, MCP, schema) update the snapshots on purpose: `UPDATE_SURFACE_SNAPSHOTS=1 python -m
  pytest tests/test_public_surface.py`.
- A visual change is checked by looking: build an example that uses it, `studio snapshot`, read the sheet. Every
  example must keep building.

## Repository rules

- `main` is protected. Work on a branch; every pull request links an issue (`Part of #N`) labelled `status: accepted`,
  and changes to core paths (spec, compiler, CLI, MCP, backends, server) need `status: design-approved`. Agree the design
  in the issue before writing core code.
- Titles are Conventional Commits with a known area: `feat(scenes): ...`, `fix(runtime): ...`. Merges are squash-only.
- A user-facing change adds `changes/<issue>.<kind>.md` (added, changed, fixed ...); never edit `CHANGELOG.md`.
- Coverage floors in `tests/coverage_floors.json` never go down.
- `CONTRIBUTING.md` has the full rules; `CLAUDE.md` has the engine's layout in more detail.
