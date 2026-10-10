---
name: scroll-site
description: Build a scroll-driven website with the Scroll Studio engine from a brief, images, a 3D model, a film idea or nothing at all. Use when the user asks for a scroll site, landing page with scroll animation, product scroll, "Apple-style" page, artwork reveal, 3D zoom page, photo parallax page, or kinetic type page.
---

# Build a scroll site with Scroll Studio

Everything goes through the engine: write a `site.yaml`, build, look at snapshots, iterate. Never hand-write HTML.
Use the MCP tools (`scroll-studio` server) when available, otherwise the `studio` CLI (`python -m engine.cli ...`).

## 1. Pick the scene types from the subject
| The subject is... | Scene type | Inputs |
|---|---|---|
| a journey, launch, flight, place reveal (cinematic) | `film` | brief + Blender preset/.blend, or an existing video in `video:` |
| a painting, illustration, portrait, building photo, logo | `artwork` | any image (`file:` or `generate:`) |
| science, scale, space, data, networks | `scene3d` | presets: cell-field, cell, nucleus, helix · galaxy, star-system, planet · network, lattice, particles · gltf |
| a physical product with parts | `sequence` | a .glb/.obj/.fbx/.stl (file or https URL) |
| a place: hotel, home, landscape, venue | `parallax` | one photo per step (`file:` or `generate:`) |
| a manifesto, event, agency, statement | `type` | text only |
| a physical product the client owns, in a cinematic world | `film` + `take:` | the product's .glb (or a photo with TRELLIS) + rough world shapes and camera keys |
| a real place: house, venue, shop (scanned) | `splat` | a Gaussian-splat scan (.ply or gsplat .pt) + camera keys |
| a data story with figures that must be right | `chart` + `callouts`, `stats` with `data:` | a CSV (file or URL) |

Mix them: a `film` hero, then `features`/`stats`, then an `artwork` section, then a `cta`.

## 2. Write the spec
- Start from the closest example: `list_projects`, then `create_project(name, example=...)`, then edit with `get_spec`/`set_spec`.
- `spec_schema('<type>')` gives every field with descriptions. Pick a theme preset that fits the domain
  (night, brass, paper, lab, cosmos, studio, dusk, ink, blueprint) and override colours only if the brand needs it.
- An experience in one word: `theme: { style: <name> }` changes how the site scrolls and reads (split-flap board,
  comic pages, terminal session, game level, anime opening, ... the table in README.md). Pick by the brand's
  character, offer two or three, and show them with `studio looks <project> --styles a,b,c`.
- Brand: `studio brand <project> --logo inputs/logo.png` sets contrast-checked colours from the client's logo.
- Copy: short, specific, written for the reader. `<em>…</em>` marks the accent words in a title.
- Steps: the first step can be `intro: true` (the section's opening headline). For `artwork`, `scene3d`, `parallax`,
  each further step drives one stage, level or photo, in order. For `film`/`overlay`, use `at: [from, to]`.
- Quote YAML strings that contain `:` or `,` inside `{ … }` flow mappings.
- No images? Use `image: { generate: "<a photographic prompt>" }`: generated locally (needs ComfyUI running).

## 3. Build, look, fix
1. `build(project, draft=True)` then `wait_for_job`. Read the log on failure: it names the stage and the cause.
2. `snapshot(project)`, then read the sheet image. Check: text legible over the visual, the subject framed
   (not hidden behind the copy), nothing cut off, colours on brand, every stage actually visible.
3. Fix the spec (or the engine, if it's an engine limitation) and repeat. Finish with a full `build`.
4. `record(project)` for an MP4 scroll-through when the user wants something to share.
5. Client revisions: `studio copy export <project>` -> send copy.md -> `studio copy import <project> copy.md` -> build.

## 4. Hand over
Tell the user where the site is (`dist/index.html`, preview with `studio preview <name>` or in `studio ui`), what
each section shows, and anything you couldn't do (e.g. ComfyUI not running, so generated images were skipped).
