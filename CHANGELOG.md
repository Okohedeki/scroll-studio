# Changelog

What changed in each version of Scroll Studio, newest first. Versions follow the project's milestones; each lists the
commits it spans so you can check out any earlier state (`git checkout <commit>`).

## Unreleased

### Added
- `theme.art`: a prompt (or `file:`) becomes artwork a style draws in its own medium, generated locally with Z-Image
  and, with `motion:`, animated by LTX-2.3 into a seamless loop. `ascii-art` prints it in characters in the hero and
  the render pane; `particles` turns it into a full-screen field of points.

### Changed
- `particles`: the hero is a field that fills the whole screen (the art, when there is one) and drifts apart as you
  scroll into the first formation.
- `blueprint`: next, next, next. The pen starts on the next view while the camera is still moving there, construction
  lines take less scroll, and moves between views are short, so no screen is empty paper.

### Fixed
- `studio looks` refreshes the site's runtime, so rebuilding only the looks never runs a stale one.

## 3.0.0 · 2026-10-10

Commits `34dd0c5` to the latest commit on `main`.

The headline: your real product in a generated world, real places, numbers read from the data, twenty-one styles that
change how a site is experienced, tools for client work, and a new licence.

### Licence (breaking)
- Scroll Studio is now **GNU AGPL-3.0** with additional terms ([NOTICE.md](NOTICE.md)): derivatives stay open source
  (including tools offered over a network and code AI agents produce from this repository), the attribution notice is
  kept word for word, modified versions are marked and may not use the name, and the research in `docs/styles` is
  credited wherever it is used. Sites you build are yours under the Scroll Studio Output Exception.
- [AGENTS.md](AGENTS.md) tells AI agents what the licence requires of them.
- Earlier versions were MIT and stay MIT for those copies.

### Added
- **One Take** (`film` with `take:`): one continuous camera move through a generated world. Rough shapes and camera
  keys become a Blender depth guide, LTX-2.3 paints the world in chained segments, and the real product is rendered by
  Cycles from its own 3D model through the same camera and composited, so it never warps. `from_photo:` builds the
  model with TRELLIS. Example: Stillwater (`examples/one-take`).
- **Real places** (`splat` scene): Gaussian-splat scans (`.ply` or gsplat `.pt`) trimmed and compressed to SPZ at build
  time and walked through on scroll with Spark. Example: Hollis House.
- **Numbers you can check**: chart `callouts` resolved from the data at build time, bar and scatter charts, number
  formats, and `stats` items that read their value from a chart. Example: Pelorus (renewables data from Our World in
  Data).
- **Twenty-one styles as experiences** (`theme.style`): particles, liquid-morph, holographic, neon-glow, wireframe-3d,
  glassmorphism, kinetic-type, isometric, clay-3d, ascii-art, gradient-mesh, comic-book, split-flap, retro-vhs, halftone,
  bauhaus, pixel-art, blueprint, art-deco, neo-brutalism and anime-intro. Each has its own scroll mechanic, layout,
  transitions, components and call to action (a departures board, comic pages, a terminal session, a game level, an
  anime opening...), built from research in [docs/styles](docs/styles/). A style is a folder (`engine/styles/<name>/`)
  plus a runtime controller (`runtime/src/styles/<name>.ts`); the contract is in `engine/styles/README.md`.
- `studio looks`: build one site in every style, with a switcher bar and a gallery. Example: Halcyon.
- **Client work**: `studio copy export|import` (a Markdown copy deck for clients, applied back into site.yaml with
  comments kept and invalid edits refused) and `studio brand --logo` (theme colours from a logo, contrast-checked).
- MCP tools: `list_styles`, `looks`, `copy_deck`, `apply_copy_deck`, `brand_from_logo`.
- `theme.mode` override; extra font roles in a style (`--font-<role>` CSS variables).
- An SVG favicon on every page.
- Showcase: the v3 examples and a "New in v3" section.

### Changed
- One Take product pass renders only the product's screen region (about 9 times faster), its shadow ends at the surface
  it stands on, and the HDRI's own sun is turned to match the scene's light.
- Snapshots and recordings wait for a style's experience to start.
- The Halcyon demo no longer shares one type scene across styles.

### Fixed
- Runtime chunk preloads resolve next to `index.js` (they requested `/chunks/...` from the server root and 404ed on
  GitHub Pages).
- Look pages rebase their own relative links.
- Map styles that name a missing icon no longer log warnings.
- Chart end labels give way to callouts; label halos; a `0%` tick instead of `0.0%`.
- The rolling word in a type `swap` scene is measured after the web fonts load (it was cut off).
- Blockout `scatter` can be cones (pines), so forests no longer read as boxes to the video model.

### Removed
- The first, CSS-only version of the styles and its shared effects layer (`runtime/src/fx`), replaced by the
  per-style experiences.

## 2.0.0 · 2026-10-06 to 2026-10-08

Commits `387962c` to `c566ea5`.

The polish release: rendering fixes found on real hardware, typography and contrast, new layouts and blocks, and
phones that play clips.

### Added
- **Stack layout** (`layout: stack`): every section is a full-screen panel that slides over the last; panel blocks and
  `surface:` (light, dark, accent) recolour one section with contrast-checked tokens. Example: Hushwell.
- **Plain pages** beside a site (privacy, support, press) from Markdown, with fenced code blocks and heading anchors.
- **Backdrops** for any section, including `gradient:` backdrops rendered locally (stops, glows, stars, grain), and
  display-size type.
- **Phones**: a product or hero phone can play a screen recording; poses `rise`, `close`, `lean`, `pair` (two phones that
  swap) and `turn`; big figures under the copy; bold-italic emphasis (`theme.display_em: bold`).
- `scroll.speed` paces the smooth scroll, anchor scrolls and reveals.
- `theme.display_optical_size` pins a variable display face's optical size.
- Self-hosted Google Fonts (no third-party requests for type), with axis specs for more families.
- Casa Alta in the showcase; README GIF and launch copy.

### Changed
- Typography and contrast: secondary text tiers and accent text are derived per theme so small text clears WCAG AA.
- Depth Anything V2 Small (Apache-2.0) is the default depth model; GSAP dropped (unused).
- Clips in phones play only while on screen and pause while the page is hidden.
- `studio publish` rewrites links to every sibling site and warns about missing ones.

### Fixed
- A black rectangle flashing over WebGL scenes (a NaN in the glow shader), and black squares over `scene3d` views.
- Caption text tracks the scroll position, so fast scrolling never leaves text behind.
- GitHub detects the licence file.

## 1.0.0 · 2026-09-28 to 2026-10-05

Commits `51f56a6` to `6353886`.

The first release of the engine: one `site.yaml` in, a static scroll-driven site out.

### Added
- **The engine**: a Pydantic site spec, cached scene builders, a Jinja compiler with themes, and a TypeScript browser
  runtime (Lenis smooth scroll, sticky stages, step cards, HUDs, one lazily loaded player per scene type).
- **Nine scene types**: `film` (Blender blockout, Z-Image keyframes, LTX-2.3 video), `artwork` (any image drawn and
  painted in stages), `scene3d` (three.js zoom journeys), `sequence` (Blender renders of a 3D model), `parallax` (photos
  with estimated depth), `type` (kinetic typography), `vector` (SVG line drawings), `chart` (D3 data stories) and `map`
  (MapLibre camera flights and routes).
- **Content blocks**: hero, intro, features, stats, timeline, quote, cta, gallery, product, strip, orbit, faq.
- **Tools**: the Studio UI and server, a CLI (`build`, `preview`, `snapshot`, `record`, `previews`, `poster`, `publish`,
  `combine`, `doctor`), an MCP server and Claude skill, a model registry, and an install guide.
- URL inputs and locally generated images (`generate:`).
- A loading screen that holds scrolling until every scene's media is ready.
- **Examples**: Lodestar Orbital, Meridian, Atelier Sfumato, Cellwright Bio, Northstar Observatory, Fischer & Vale,
  FORM/26, Wunderkammer, Daybreak Institute, Tidewater Lines, Casa Alta, Hale & Rowe, and the showcase gallery with
  preview videos.
- Licensed MIT.
