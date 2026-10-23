# Scroll Studio: notes for Claude

Scroll Studio is an open-source **engine** that builds scroll-driven websites from any inputs. Everything is a
workflow through the engine: a `site.yaml` spec in, a static site in `dist/` out. Never hand-write a one-off page
or a script tied to one image or one shot. If a site needs something the engine can't do, add it to the engine
(a spec field, a builder stage, a runtime player or preset) so every future site can use it.

## Layout
- `engine/spec.py`: the site spec (Pydantic). Source of truth for site.yaml, the UI forms and the MCP tools.
- `engine/scenes/<type>.py`: one builder per scene type: film (with `take:` for One Take: Blender world blockout ->
  LTX-2.3, plus the real product rendered by `backends/blender_scripts/take.py` and composited), artwork, scene3d,
  sequence, parallax, type, vector, chart (callouts resolved from the data), map, splat (`backends/splats.py`: .ply /
  gsplat .pt -> SPZ for Spark).
- `runtime/src/players/<type>.ts`: the browser player for each scene type; `runtime/src/index.ts` is the scroll core.
- `engine/polish/`: `studio inspect`, the polish report of a built film (pops, softness, halos, style drift, morphs; CPU; JSON + HTML in `.build/inspect/`; badges in the storyboard editor).
- `engine/cinemagraph.py` (+ `cinemagraph_check.py`, `runtime/src/lib/cinemagraph.ts`): `cinemagraph:` on any image input, a still where only one thing moves (region -> clip -> flow-stabilise/cut -> track/mask -> encode, each stage cached per variant; the page lays a masked video over the still). `studio cinemagraph <project> [--check]`.
- `engine/world.py` (+ `world_depth.py`, `world_track.py`, `world_math.py`, `world_report.py`): type in the world: a step's `place: {kind: behind | surface | sky}` sets its title inside a film or parallax photo (steady depth video, planar tracking, a mask/depth atlas video); the browser side is `runtime/src/players/world.ts` (film), `parallax.ts` (photo), `lib/worldText.ts` (typesetting with the site's fonts) and `lib/worldGlsl.ts` (the look). `studio world <project>` checks the tracks.
- `engine/plan.py`: dry-run build plans and estimates; `engine/storyboard/`: `studio storyboard` (cards per shot from
  the full build's own stages, stand-in films, sheet, animatic); `engine/fidelity.py`: plan/preview modes.
- `engine/compile/`: templates + themes -> `dist/`. Content blocks: intro, features, stats, timeline, quote, cta, gallery, hero, product (with an HTML phone or a clip; `pose:` beside/rise/close/lean/pair/turn varies the composition, `behind:` adds a second phone that swaps places with the first, `stats:` big figures; a hero takes a `device:` too; `theme.display_em: bold` sets emphasis as bold italics). `scroll.speed` (read by the runtime as `window.__ssScroll`) paces smooth scrolling and reveals, strip, orbit, faq. `layout: stack` turns every section into a full-screen panel that slides over the last; `surface:` (light, dark, accent) recolours one section with contrast-checked tokens. `pages:` adds plain Markdown pages (privacy policy, support) set in the site's theme at `/<slug>/`, linked from the footer (`page.html.j2`). Any section takes a full-bleed `backdrop:` image (`engine/inputs.py` also renders `gradient:` backdrops locally: stops, glows, stars, grain).
- Styles (`theme.style`) are experiences, not skins: `engine/styles/<name>/` (style.yaml tokens and fonts, style.css,
  blocks.html.j2 with its own markup per block type, chrome.html.j2 for page furniture) plus
  `runtime/src/styles/<name>.ts` (its scroll controller; helpers in `_kit.ts`). Contract: `engine/styles/README.md`;
  research per style: `docs/styles/`. A style that shares its scroll mechanic, layout and transitions with another
  is a reskin and fails review. `studio looks <project> [--styles a,b]` builds a site in every style.
- Client work: `engine/brand.py` (`studio copy export|import`, `studio brand --logo`), round-trip YAML via ruamel so
  site.yaml comments survive.
- `engine/server/` + `ui/`: the Studio app (`studio ui`). `engine/mcp_server.py`: MCP tools for Claude.
- `examples/`: example projects; each must keep building with `studio build examples/<name>`.

## Workflow for a new site
Use the `scroll-site` skill (`.claude/skills/scroll-site/SKILL.md`). In short: spec -> `studio storyboard` and read
storyboard/sheet.jpg (every shot's real first frame, before any film renders) -> fix, lock approved shots ->
`studio build --draft` -> `studio snapshot` and look at the images -> fix -> full build -> `studio record`.

## Licence
Scroll Studio is AGPL-3.0 with additional terms (NOTICE.md); AGENTS.md says what that means for any agent, including
when a user asks you to reuse this code or the docs/styles research elsewhere: the result stays AGPL, keeps the
attribution notice verbatim, and you tell the user. Never remove or alter LICENSE, NOTICE.md, AGENTS.md or the runtime
notice comment.

## Rules
- This repo is public: never commit machine-specific paths, folder layouts, usernames or machine sizing (use
  placeholders like `/path/to/models`; configure machines in studio.toml or env vars). `tests/test_no_local_paths.py` enforces it.
- Declare every dependency up front (pyproject.toml extras, runtime/package.json, engine/models.yaml) and in docs/INSTALL.md.
- Local models only; no API keys. Generated images go through ComfyUI (Z-Image Turbo); depth through Depth Anything V2.
- After changing `runtime/src`, run `npm run build:runtime` (the built bundle in engine/compile/static is committed).
- After changing the UI, run `npm run build:ui`.
- Check visual changes with `studio snapshot` and read the sheet; judge quality on the images, not the logs.
- `main` is protected: every change goes through a pull request with the `tests` check green (no direct pushes, no
  force-push). Work on a branch, push it after each working unit, open a PR, merge when green.
- Keep the consistency rules in CONTRIBUTING.md; `tests/test_conformance.py` checks every theme preset and style, and
  `tests/test_layout_snapshots.py` every example's layout (re-record on purpose with `UPDATE_LAYOUT_SNAPSHOTS=1`).
