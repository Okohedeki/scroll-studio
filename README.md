# Scroll Studio

**Scroll-driven websites from one YAML file. Runs on your own machine with no API keys, and Claude can drive it
through MCP.**

[![Lodestar Orbital: a rocket launch that plays as you scroll](docs/media/lodestar.gif)](https://okohedeki.github.io/scroll-studio-showcase/)

**[See every example site live →](https://okohedeki.github.io/scroll-studio-showcase/)** ·
**[One page, twenty-one experiences →](https://okohedeki.github.io/scroll-studio-showcase/halcyon/looks/)**

Give it a brief, a photo, a painting, a 3D model, a CSV or a film idea. It builds a static site where scrolling
plays the visuals: generated video, a painting drawn stroke by stroke, a live 3D zoom, a data story, a map flight.
The output is plain HTML, CSS and JS you can host anywhere.

**What you need:** 7 of the 10 scene types (`scene3d`, `chart`, `map`, `type`, `vector`, `splat`, and `artwork` from your own
images) need no GPU at all, just Python and a browser. `parallax` and `sequence` run on the CPU but are much
faster on a GPU. `film` generates video locally with LTX-2.3 and needs Blender, ComfyUI and a 24 GB card (RTX
4090 class). Details in [docs/INSTALL.md](docs/INSTALL.md).

```
site.yaml ──► studio build ──► dist/  (plain static files: host anywhere)
   ▲               │
   │               ├─ film      Blender blockout → Z-Image keyframes → LTX-2.3 video → scrub-ready encode
 Studio UI         ├─ artwork   any image → guides, contour strokes, graphite, underpainting, colour layers
 Claude (MCP)      ├─ scene3d   live three.js zoom journeys built from presets or your glTF models
 CLI               ├─ sequence  Blender (Cycles) renders a 3D model: turntable, explode, reassemble
                   ├─ parallax  photos + estimated depth (Depth Anything V2) → 2.5D camera moves
                   ├─ type      kinetic typography: reveal, stack, swap, scale
                   ├─ vector    SVG or vectorised artwork drawing itself stroke by stroke
                   ├─ chart     CSV data stories with D3: series, zooms, callouts read from the data
                   ├─ map       live vector maps (MapLibre): camera flights and routes per step
                   └─ splat     a Gaussian-splat scan of a real place, walked through on scroll (Spark)
```

### New in v3

- **One Take** (`film` with `take:`): one unbroken camera move through a generated world. You block the world out
  in rough shapes and camera keys; Blender renders the depth guide, LTX-2.3 paints the world along it in chained
  segments, and your real product is rendered by Cycles from its own 3D model through the identical camera and
  composited onto every frame. The product never warps, because it is never generated.
  ([Stillwater](examples/one-take/site.yaml))
- **Real places** (`splat`): a phone or drone scan as a Gaussian splat (`.ply` or a gsplat `.pt`), trimmed and
  compressed to SPZ at build time and walked through on scroll. ([Hollis House](examples/hollis-house/site.yaml))
- **Numbers you can check** (`chart` callouts, `stats` bound to data): headline figures and chart notes are read
  from the source CSV when the site is built, so the copy can't drift from the data. ([Pelorus](examples/pelorus/site.yaml))
- **Twenty-one styles that change the experience, not just the paint** (`theme: { style: … }`). Each style has its
  own scroll mechanic, layout, transitions and components, built from in-depth research
  ([docs/styles](docs/styles/)): split-flap is a departures board that updates as the clock advances, comic-book is
  read panel by panel, anime-intro cuts like an anime opening, ASCII is a terminal session, blueprint is a drawing
  that drafts itself. `studio looks` builds a site in every style. ([Halcyon](examples/halcyon/site.yaml))
- **Client work**: `studio copy export` gives the client a Markdown copy deck; `studio copy import` applies their
  edits back into site.yaml (comments kept, invalid edits refused). `studio brand --logo` draws a contrast-checked
  theme from their logo.

## Examples

**Live samples: https://okohedeki.github.io/scroll-studio-showcase/**

Make previews for any project with
`studio previews <project> ... --out <folder>` (a video and a poster each), or a single poster at a chosen
moment with `studio poster <project> --at <scene>:<progress> --out poster.jpg`. Previews stay out of git. To put several built sites online together (GitHub Pages or any static host):
`studio publish <project> ... --out <folder> --home showcase`.

The [showcase site](examples/showcase/site.yaml) puts every example on one page with its preview.

Every example is a `site.yaml` in [`examples/`](examples/) and rebuilds with `studio build examples/<name>`.

| Example | Domain | Scene type | What scrolling does |
|---|---|---|---|
| [Lodestar Orbital](examples/lodestar-orbital/site.yaml) | Aerospace | `film` | A rocket launch to orbit, generated locally with LTX-2.3, with live telemetry |
| [Meridian](examples/meridian/site.yaml) | Private aviation | `film` | A jet descends through cloud over London; the altimeter counts down |
| [Atelier Sfumato](examples/atelier-sfumato/site.yaml) | Art education | `artwork` | The Mona Lisa is drawn and painted in five lessons |
| [Cellwright Bio](examples/cellwright-bio/site.yaml) | Biotech | `scene3d` | A zoom from tissue to a molecule docking on DNA |
| [Northstar Observatory](examples/northstar-observatory/site.yaml) | Astronomy | `scene3d` | A fall from the whole galaxy to one living planet |
| [Fischer & Vale](examples/fischer-vale/site.yaml) | Luxury goods | `sequence` | A glass chess set lifts off its board and settles back |
| [FORM/26](examples/form-conference/site.yaml) | Events | `type` | A conference site told in kinetic type |
| [Wunderkammer](examples/wunderkammer/site.yaml) | Museum | `vector` | Dürer's *Rhinoceros* (1515) re-cut line by line |
| [Daybreak Institute](examples/daybreak-institute/site.yaml) | Research | `chart` | Real solar data (IRENA) told as a scrolling data story |
| [Tidewater Lines](examples/tidewater-lines/site.yaml) | Logistics | `map` | Shanghai to Rotterdam, port by port, on a live map |
| [Casa Alta](examples/casa-alta/site.yaml) | Hospitality | `parallax` | Generated photos of a cliff hotel in 2.5D (needs ComfyUI to build) |
| [Hushwell](examples/hushwell/site.yaml) | Healthcare | `stack` layout | Panels slide over each other: hero, product with phone, photo strip, orbit, FAQ |
| [Hale & Rowe](examples/hale-rowe/site.yaml) | Architecture | `artwork` | A house drawn from construction lines to finished photo (needs ComfyUI) |
| [Stillwater](examples/one-take/site.yaml) | Consumer product | `film` + `take` | One take from a mountain ridge down to a bottle on a lakeside table; the bottle is the real 3D model |
| [Hollis House](examples/hollis-house/site.yaml) | Real estate | `splat` | A walk through a scanned house, room by room |
| [Pelorus](examples/pelorus/site.yaml) | Research | `chart` (bar) | The renewables share of electricity, every figure read from Our World in Data |
| [Halcyon](examples/halcyon/site.yaml) | Software | blocks | One product page as twenty-one experiences (`studio looks`) |

## Quick start

```bash
git clone https://github.com/Okohedeki/scroll-studio && cd scroll-studio
pip install -e .
studio doctor                         # what this machine can build
studio build examples/cellwright-bio  # live 3D: needs nothing but Python
studio preview cellwright-bio         # http://localhost:5173
studio ui                             # the Studio app: http://localhost:5180
```

Full setup (GPU, Blender, ComfyUI and models) is in [docs/INSTALL.md](docs/INSTALL.md).

## Make your own

```bash
studio new harbour-hotel --example atelier-sfumato   # or start blank: studio new harbour-hotel
# edit projects/harbour-hotel/site.yaml (or use studio ui), drop files in inputs/
studio build harbour-hotel --draft
studio snapshot harbour-hotel --at top --at studio:0.5   # screenshots + contact sheet
studio build harbour-hotel && studio record harbour-hotel   # final build + an MP4 scroll-through
```

A spec is a theme, a nav and a list of sections. Scenes are the scroll-driven visuals; blocks (`hero`, `intro`,
`product`, `features`, `stats`, `timeline`, `strip`, `orbit`, `quote`, `faq`, `cta`, `gallery`) are the content between them.
Set `layout: stack` and every section becomes a full-screen panel that slides up over the one before it (see
[Hushwell](examples/hushwell/site.yaml)); `surface: dark | light | accent` recolours a single section:

```yaml
name: Harbour Hotel
theme: { preset: dusk }                  # night, brass, paper, lab, cosmos, studio, dusk, ink, blueprint
sections:
  - id: rooms
    type: parallax
    steps:
      - { intro: true, title: "A room above <em>the water.</em>" }
      - { title: Morning, image: { generate: "Hotel terrace above a harbour at sunrise, photoreal" } }
      - { title: Evening, image: inputs/terrace-dusk.jpg }
  - type: cta
    title: Stay <em>a while.</em>
    button: { label: Book, href: "https://example.com" }
```

`studio schema` prints every field. Inputs can be project files or https URLs; images can be generated locally
from a prompt (`generate:`). Builds are cached per stage, so editing copy never re-renders a film. A theme can
pin the display face's optical size (`display_optical_size: 40`): variable serifs like Fraunces grow more
expressive at huge sizes, and a pinned size keeps headlines calm.

A site can carry plain pages beside the scroll page, for the privacy policy, support or press: Markdown files set
in the site's theme, served at `/<slug>/` and linked from the footer (`nav: true` adds them to the nav too).

```yaml
pages:
  - { slug: privacy, title: Privacy, source: pages/privacy.md }
  - { slug: support, title: Support, source: pages/support.md, nav: true }
```

A `product` block's phone can play a screen recording instead of showing a screenshot: `device: { video: inputs/clips/write.mp4, image: inputs/write.jpg }` (muted, looping; the image is the poster). `pose:` picks the composition so a run of product panels doesn't repeat one: `beside` (default), `rise` (centred under centred copy, cut off by the panel's bottom edge), `close` (larger, cut off below), `lean` (tilted out of the lower corner), `pair` (with a second phone, `behind: { video: …, image: … }`, the two swapping places on a loop), `turn` (turned in perspective towards the copy). `stats: [{value, label}]` shows big figures under the body instead of tags. A `hero` takes a `device:` too, rising from the bottom edge under the copy. `theme.display_em: bold` sets `<em>` words as bold italics in the text's own colour instead of the accent colour. `scroll: { speed: 1.2 }` paces the smooth scroll, anchor scrolls and scroll-driven reveals (1 is the default; 1.2 is a fifth faster).

Any section can sit on a full-bleed `backdrop:` (in the stack layout, the panel's own), with `surface:` picking the
text colour. A backdrop can be a file, a URL, a `generate:` prompt, or a `gradient:` rendered on the spot with no
model: colour stops, glows, stars and grain, enough for colour cards, dusk skies and night seas behind type.

```yaml
  - type: hero
    surface: dark
    backdrop:
      gradient:
        colors: ["#2A1B2E", "#8A4B5A", "#D98C7A"]
        glows: [{ x: 0.5, y: 0.95, color: "#F2B48C", radius: 0.5, strength: 0.6 }]
        stars: 120
    title: Your words stay <em>on your phone.</em>
```

## Styles

`theme: { style: <name> }` changes how a site is experienced: what scrolling does, how content is laid out and
arrives, how sections hand over, what the pointer does and what the call to action is. The same `site.yaml` reads
as a departures board, a comic, a terminal session, a game level or an anime opening. `theme.colors` and
`theme.fonts` still win, so a brand's palette can wear any style.

| Style | What scrolling is |
|---|---|
| `particles` | One swarm of points re-forming into each section's subject |
| `liquid-morph` | One body that morphs; nothing cuts, everything becomes |
| `holographic` | Rotating holographic plates; the information is in the angle |
| `neon-glow` | A night street where signs ignite as you arrive |
| `wireframe-3d` | Flying a camera through a world drawn in lines |
| `glassmorphism` | Windows over a living world moving behind them |
| `kinetic-type` | An instrument made of letters, played by scroll speed |
| `isometric` | A fixed-angle drone over a model world that builds itself |
| `clay-3d` | Soft toys on a table: mass, squash and wobble |
| `ascii-art` | A terminal session that types and prints |
| `gradient-mesh` | Weather: one breathing colour field that shifts with each chapter |
| `comic-book` | Reading a comic page panel by panel |
| `split-flap` | A departures board updating as the clock advances |
| `retro-vhs` | Operating a VCR: play, search, rewind |
| `halftone` | Reading a freshly printed newspaper |
| `bauhaus` | Composing a poster from shapes that persist and change role |
| `pixel-art` | Playing a side-scrolling game |
| `blueprint` | A technical drawing that drafts itself |
| `art-deco` | An opening night: doors, sunbursts, marquees |
| `neo-brutalism` | A desk you fill up and can mess with |
| `anime-intro` | Scrubbing the playhead of an anime opening, cut by cut |

```bash
studio looks examples/halcyon            # dist/looks/<style>/ for every style, plus a gallery at dist/looks/
studio looks my-site --styles split-flap,comic-book,anime-intro
```

A style is a folder (`engine/styles/<name>/`: tokens, stylesheet, its own block markup and page chrome) plus a
runtime module (`runtime/src/styles/<name>.ts`) with its scroll controller; the contract is in
[engine/styles/README.md](engine/styles/README.md) and the research behind each one in [docs/styles](docs/styles/).

## One Take, places and data

A `film` scene with a `take:` is one continuous shot. `objects` are rough shapes (`box`, `cylinder`, `cone`, `blob`,
`plane`, `scatter` for forests or towns), `camera` is a list of `{t, at, look}` keys, and `product` is your 3D model
(`model: inputs/bottle.glb`, or `from_photo:` with TRELLIS configured) standing at a point in that world. The world is
generated; the product is rendered, lit by the take's sun, with its shadow on the surface it stands on:

```yaml
  - id: take
    type: film
    take:
      duration: 15
      objects:
        - { kind: box, name: Table, at: [0, -5, 0.75], size: [1.6, 0.9, 0.06], color: "#9a7b56" }
        - { kind: scatter, count: 60, area: [-120, 40, -30, 140], height: [6, 14], shape: cone, color: "#3f5538" }
      camera:
        - { t: 0, at: [-70, 190, 70], look: [0, 40, 6] }
        - { t: 15, at: [1.6, -3.4, 1.3], look: [0, -5, 0.95] }
      product: { model: inputs/bottle.glb, at: [0, -5, 0.78], height: 0.27 }
```

A `splat` scene takes a scan (`source: inputs/house.ply` or a gsplat checkpoint) and camera `keys` with `{t, at,
look}`; the build trims faint and oversized splats, keeps the `max_splats` most visible and writes SPZ.

A `chart` can carry `callouts` resolved from the data (`{series: Denmark, at: last, label: "Denmark {y} in {x}"}`;
`at` is `max`, `min`, `first`, `last` or an x value), and a `stats` item can take its number from a chart:
`{ unit: "%", label: World share, data: { section: share, series: World, at: last } }`.

## Client work

```bash
studio copy export my-site                 # my-site/copy.md: every visible line of text, ready to send
studio copy import my-site copy.md         # apply the client's edits (prints a diff; --dry-run to preview)
studio brand my-site --logo inputs/logo.png --mode light   # theme colours from the logo, contrast-checked
```

The copy deck is plain Markdown: one `###` key per field, the text under it. Imports keep site.yaml's comments and
layout and refuse anything that would make the spec invalid. A rebuild after an import re-renders only what the
text touches.

## With Claude

Open the repo in Claude Code and ask for a site. The `scroll-studio` MCP server (`.mcp.json`) gives Claude tools
to create projects, edit specs, build, take snapshots and look at them, and record videos; the `scroll-site` skill
gives it the workflow. Any MCP client can use `python -m engine.mcp_server`.

## How it's built

- `engine/`: Python. Spec (`spec.py`), scene builders (`scenes/`), compiler and themes (`compile/`), backends for
  ComfyUI, Blender and depth (`backends/`), CLI, server, MCP server, snapshot and record tools.
- `runtime/`: TypeScript. The scroll core (Lenis, sticky stages, step cards, HUDs) plus one lazily loaded player per
  scene type. Built into `engine/compile/static/runtime` and copied into every site.
- `ui/`: React. The Studio app.
- Every model, with its size and licence, is listed in [`engine/models.yaml`](engine/models.yaml).

## Licence

Scroll Studio is free software under the **GNU AGPL-3.0** ([LICENSE](LICENSE)) with additional terms under its
section 7 ([NOTICE.md](NOTICE.md)):

- **Derivatives stay open source.** A modified version, a port, or a tool built from Scroll Studio (including one
  offered over a network, and including code an AI agent produced from this repository) must be released under the
  AGPL with its complete source.
- **Attribution, word for word.** Derivatives keep the notice
  `Based on Scroll Studio by Edeki Okoh: https://github.com/Okohedeki/scroll-studio (GNU AGPL-3.0)` in their README,
  notice file and About / `--version` / footer, and work that uses the research in `docs/styles` credits it as
  `Style research from Scroll Studio by Edeki Okoh: https://github.com/Okohedeki/scroll-studio`.
- **No misrepresentation.** Modified versions are marked as modified, may not claim to be the original or be named
  "Scroll Studio", and nobody may present the code or the research as their own.
- **Your sites are yours.** Sites you build with Scroll Studio are covered by the Scroll Studio Output Exception: license
  them however you like, keeping the notice comment in the runtime files.

AI agents: see [AGENTS.md](AGENTS.md). Versions published before this change were MIT and stay MIT for those copies.

Model weights keep their own licences (see `engine/models.yaml`). Two are non-commercial: Depth Anything V2 Base/Large
(CC-BY-NC-4.0; the default Small model is Apache-2.0) and the optional MusicGen. LTX-2.3 and Gemma ship under their own
community terms. Check them before commercial use.
