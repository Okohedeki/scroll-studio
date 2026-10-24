# Render tests

Every style and theme preset, built into a real page and loaded in Chromium: **32 styles + 10 presets = 42 looks**, each
at a desktop (1280x800) and a phone (390x844) size. No GPU and no models: the page is a "kitchen sink" spec
([kitchen.py](kitchen.py)) with every block type and a `type` scene in each layout, built by the engine's own compiler
and served by its own server. Per look and viewport:

- **Runs clean:** no console errors, page errors or failed requests, `data-ss-ready` set, exactly one `<h1>` after the
  JavaScript ran, every word of the spec on the page as text, no horizontal overflow. Checked scrolling through the page
  with motion, and again with reduced motion.
- **Accessibility:** axe-core, `serious` and `critical` violations fail, at the top, middle and bottom of the page with
  reduced motion. Violations that are known and accepted go in [axe-allow.yaml](axe-allow.yaml) (rule, look, reason).

Screenshot comparison against recorded baselines is not part of this yet (the images would add tens of megabytes to
the repository); these checks catch pages that break, not pages that merely moved.

## Running them

They only run inside the pinned Playwright image, so fonts and browser are the same on every machine. Anywhere else they are skipped (`SS_RENDER` unset), so `python -m pytest` stays fast.

```bash
# Linux / macOS / Git Bash on Windows (Git Bash: put MSYS_NO_PATHCONV=1 in front of `docker`)
docker run --rm -v "$PWD":/repo -v render-node-modules:/repo/node_modules -w /repo \
  mcr.microsoft.com/playwright/python:v1.58.0-noble bash tests/render/run.sh

# one look: extra arguments go to pytest
docker run --rm -v "$PWD":/repo -v render-node-modules:/repo/node_modules -w /repo \
  mcr.microsoft.com/playwright/python:v1.58.0-noble bash tests/render/run.sh -k "style-bauhaus"
```

```powershell
# Windows PowerShell
docker run --rm -v "${PWD}:/repo" -v render-node-modules:/repo/node_modules -w /repo `
  mcr.microsoft.com/playwright/python:v1.58.0-noble bash tests/render/run.sh
```

`run.sh` installs what the image lacks (the `playwright` package at the image's version, Node, the Python dev extra,
`npm ci` for axe-core) and runs `pytest tests/render` on `RENDER_WORKERS` workers (default: one per CPU), one look per worker.
The `render-node-modules` volume keeps the container's Linux `node_modules` apart from yours. The first build of a look
downloads its Google Fonts (they are then self-hosted in the page), so the network must be up.
CI does the same in [render.yml](../../.github/workflows/render.yml).

A new style or preset needs no test code: it is picked up from `engine/styles/` and `engine/themes.yaml`. Nothing is
allowlisted for a new look: fix the accessibility finding rather than record it.

## Known problems

The first run found real bugs in styles and presets. They are recorded, each with its reason, so CI starts green and goes
red for anything new: [known-issues.yaml](known-issues.yaml) (console errors, missing text, overflow; the test is marked
xfail while the bug is there) and [axe-allow.yaml](axe-allow.yaml) (accessibility findings, by rule, look and a selector).
Fixing a bug means deleting its entry; do not add one for a new look or a change you made.
