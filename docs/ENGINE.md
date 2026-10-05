# Scroll Studio engine: design

Scroll Studio is an open-source engine for scroll-driven sites. You clone it, give it inputs (a brief, images,
a 3D model, a CSV, a URL), and it builds a finished static site where scrolling plays the visuals. It runs
locally, with no API keys, and Claude can drive it through the UI's chat, Claude Code, or an MCP server.

Everything in this repo goes through the engine. The current demos (Lodestar Orbital, Atelier Sfumato,
Cellwright Bio, Meridian) become example projects that the engine rebuilds from their spec. One-off scripts
and hand-written pages are not part of the design.

---

## 1. The idea all these sites share

Every site in this realm works the same way: visuals are built ahead of time, and the scroll position plays
them back. That gives the engine two halves:

1. **Build (offline, Python, GPU).** Turn inputs into scroll-ready assets: a film, a frame sequence, image
   layers with reveal masks, a 3D scene, a depth map, a chart dataset.
2. **Play (browser, TypeScript).** One shared runtime maps scroll position to progress per section, and
   a "player" for each scene type renders that progress. Text cards scroll beside the visual.

A site is a list of **sections**. Each section has a **scene type**, its **inputs**, and its **steps** (the
copy cards that scroll past). A site can mix types: a film hero, then an artwork section, then a chart.

---

## 2. Scene types

Each scene type is one engine module: a schema, a builder (inputs → assets), and a runtime player
(assets + progress → pixels). Adding a new kind of site means adding a module, never a one-off page.

| # | Scene type | What the viewer sees | Inputs it accepts | Build | Player |
|---|---|---|---|---|---|
| 1 | `film` | A cinematic shot scrubbed by scroll (rocket launch, fly-over, product reveal) | brief text; optional blockout (`.blend`, `.glb`, or a generated preset rig), reference/brand images, keyframe images | Blender blockout + depth → Z-Image keyframes → LTX-2.3 video (segments) → upscale → short-GOP encode | `video-scrub` (H.264/AV1, seek per frame) or `frame-seq` |
| 2 | `sequence` | Apple-style object turntable / exploded view / assembly | `.glb`/`.obj`/`.step` model, or product photos (→ image-to-3D) | Blender renders a camera path or explode animation to frames (transparent PNG → WebP/AVIF) | `frame-seq` (canvas, preloaded frames) |
| 3 | `artwork` | An image drawn and painted on scroll (sketch → value → underpaint → colour) | any image (painting, illustration, photo, logo), optional focus points | Segmentation + saliency → reveal order; edge trace → SVG strokes; tonal/monochrome layers; brush-front masks | `layers-gl` (WebGL2 compositing) + `svg-draw` |
| 4 | `vector` | A logo or line illustration that draws and fills itself | SVG, or a raster logo (vectorised) | Vectorise, order paths, compute lengths | `svg-draw` |
| 5 | `parallax` | A still photo turned into a 2.5D camera move | one image (or several) | Depth Anything V2 → depth map; optional inpainted background layer | `depth-gl` (displacement / layered parallax) |
| 6 | `morph` | A → B → C transformation (before/after, renovation, product generations) | 2+ images, optional prompt | LTX keyframe interpolation or RIFE/FILM frame interpolation; or masked dissolve | `video-scrub` / `layers-gl` |
| 7 | `scene3d` | Live 3D world: zoom across scales, configurator, space, molecules | `.glb` assets and/or procedural generator presets (cells, helix, particles, terrain, orbit) | glTF optimise (Draco/Meshopt, KTX2), bake preset params, camera path | `three-scene` (three.js + postprocessing) |
| 8 | `splat` | Photoreal fly-through of a real place or object | a phone video or photo set | Gaussian-splat training (gsplat/nerfstudio), compress | `splat` (Spark / gaussian-splats-3d) |
| 9 | `chart` | Data story: charts that build, highlight and re-shape | CSV/JSON + narrative | Clean, aggregate, pre-compute states | `chart` (D3) |
| 10 | `map` | Geographic journey: fly between places, draw routes | places/GeoJSON | Fetch/clip tiles to PMTiles (offline), route geometry | `map` (MapLibre GL) |
| 11 | `type` | Kinetic typography: headlines that assemble, swap, scale with scroll | text only | none | `type` (GSAP) |

Mapping the current demos: Lodestar Orbital and Meridian = `film`; Atelier Sfumato = `artwork`;
Cellwright Bio = `scene3d` with generator presets (cells, chromatin, helix, molecule).

**Proposed v1:** `film`, `artwork`, `scene3d`, `sequence`, `parallax`, `type`, because they cover the existing
demos plus the two most-requested looks (product turntable, photo parallax). **v2:** `morph`, `vector`, `chart`,
`splat`, `map`. All dependencies for v1 and v2 are declared now (section 6) so nothing is missing later.

---

## 3. The site spec

One file describes a site. The UI edits it, Claude edits it, the CLI builds it.

```yaml
# projects/lodestar/site.yaml
site:
  name: Lodestar Orbital
  theme: { preset: night-mission, accent: "#e8742c", fonts: { display: "Sora", body: "Inter", mono: "IBM Plex Mono" } }
  brand: { logo: inputs/logo.svg, capture_url: null }    # or a URL to pull colours, fonts, logo
  nav: { links: [Mission, Services, Record], cta: "Talk to mission ops" }

sections:
  - id: launch
    type: film
    length: 9 screens                    # scroll distance
    inputs:
      brief: "A slender white two-stage rocket launches at dawn, climbs through clouds, separates, deploys a satellite."
      subject: "slender white two-stage rocket, plain white body, two thin black bands ..."
      blockout: { preset: rocket-launch }          # or file: inputs/scene.blend / inputs/scene.glb
      keyframes: auto                              # or a list of images/prompts at times
    render: { res: 1920x1088, seconds: 18, segments: 3s, upscale: none }
    hud: { kind: telemetry, fields: [altitude, velocity], events: [Lift-off, Max-Q, Stage separation] }
    steps:
      - { at: 0.00, kicker: Lodestar Orbital, title: "Every mission starts on the ground." }
      - { at: 0.30, title: "Through the weather. Past the noise." }
      - { at: 0.80, title: "Your satellite, exactly where it belongs." }

  - id: studio
    type: artwork
    inputs: { image: inputs/mona_lisa.jpg, focus: auto }          # auto = face/saliency detection
    stages: [guides, lines, value, underpaint, colour]
    steps: [...]
```

The schema is defined once (Pydantic) and exported as JSON Schema, which drives the UI forms, validation, and
the MCP tools.

---

## 4. Architecture

```
inputs ─► ingest ─► builders (per scene type) ─► asset cache ─► site compiler ─► dist/ (static site)
                         │                                        ▲
                         └─ backends: ComfyUI · Blender · ML models · FFmpeg
UI (React) ◄─► engine server (FastAPI + job queue + websocket events) ◄─► MCP server / CLI / Claude Code
```

- **Ingest** normalises inputs: images (EXIF, colour space, size), video (probe, proxy), 3D (glTF convert),
  URL capture (Playwright: brand colours, fonts, logo, copy), CSV, brief text.
- **Builders** are stage graphs with a content-addressed cache (inputs + params hash → outputs), so changing
  one step only reruns what depends on it. Long GPU stages are resumable and report progress.
- **Backends**: ComfyUI workflows are stored as JSON templates, never built in ad-hoc code. Blender runs
  headless with a library of rigs and presets. ML models load through one model registry.
- **Model manager**: one registry of every model (name, size, VRAM, licence, source). It downloads to a
  configurable model directory, verifies checksums, and checks the GPU before a job starts.
- **Site compiler** renders templates + the runtime bundle + assets into `dist/`: plain static files that
  deploy to any host (GitHub Pages, Netlify, S3). It emits poster images, mobile encodes, and reduced-motion
  fallbacks for every section.
- **Runtime** (`@scroll-studio/runtime`, TypeScript): scroll controller (Lenis + per-section progress),
  sticky stage + scrolling step cards, the players, shared HUD/caption/progress components, theme tokens,
  asset preloading by priority, and mobile and `prefers-reduced-motion` behaviour.
- **`doctor`** checks the whole stack: Python, Node, FFmpeg, Blender, CUDA/VRAM, ComfyUI, disk space, models.

### Repository layout

```
scroll-studio/
  engine/                      Python package
    spec/                      Pydantic schema → JSON Schema
    ingest/                    images, video, 3D, URL capture, data
    scenes/<type>/             schema.py · builder.py · presets/   (one folder per scene type)
    backends/comfy/            client + workflows/*.json
    backends/blender/          headless runner, blockout_lib, rigs/
    backends/models/           registry.yaml, downloader, VRAM checks
    compile/                   site compiler, templates/, themes/
    jobs/                      stage graph, cache, events
    server/                    FastAPI app (REST + websocket) used by the UI and MCP
    cli.py                     `studio new | build | preview | export | doctor | models`
  runtime/                     TypeScript runtime (Vite) → runtime.js
    core/ players/ components/
  ui/                          React + Vite app: the Studio
  mcp/                         MCP server so Claude can create projects, edit specs, run builds, read previews
  .claude/skills/              Claude Code skills: new-site, add-section, render, publish
  examples/                    lodestar-orbital/, meridian/, atelier-sfumato/, cellwright-bio/ (spec + inputs)
  docs/
  requirements.txt  pyproject.toml  package.json  install.ps1 / install.sh
```

---

## 5. The UI (Studio)

A local web app (`studio ui` → http://localhost:5180):

1. **Projects**: create from a template or an example, or from a URL (brand capture).
2. **Site editor**: section list (add, reorder, delete), each section's inputs (upload/drag-drop), copy steps,
   theme. Forms are generated from the JSON Schema.
3. **Build panel**: per-section stages with status, progress, logs, ETA, VRAM, cancel/resume.
4. **Review**: contact sheets for keyframes and variants (pick one), frame scrubber for films, before/after
   for upscales, the 100% crop check.
5. **Live preview**: the real site in an iframe at desktop and phone width, with a scroll-position slider.
6. **Export**: static `dist/` zip, a scroll-through recording (MP4/GIF for README or social), deploy guide.
7. **Claude panel**: chat that edits the spec and triggers builds through the same API the UI uses.

---

## 6. Required technology (declared now)

### System
| Tool | Version | Used by |
|---|---|---|
| Python | 3.11 | engine |
| Node.js | 20 LTS+ | runtime, UI, site build |
| FFmpeg | 6+ (with libx264, libsvtav1, libvpx) | encodes, probes, frame extraction |
| Blender | 4.2 LTS+ (headless) | blockouts, depth passes, turntables |
| Git + Git LFS | any | examples' inputs |
| NVIDIA GPU + driver | CUDA 12.4+; 24 GB VRAM for full-quality film, 12 GB for the lighter profile | ComfyUI, ML models |
| ComfyUI | pinned commit + custom nodes (ComfyUI-LTXVideo, KJNodes, VideoHelperSuite) | film, morph, keyframes |
| Chrome / Playwright Chromium | current | URL capture, previews, scroll recordings |
| COLMAP | 3.9+ (only for `splat`) | camera poses for splat training |

### Python (`requirements.txt`)
`torch` (CUDA build), `numpy`, `opencv-python`, `scikit-image`, `scipy`, `pillow`, `pillow-avif-plugin`,
`imageio`, `av` (PyAV), `pydantic`, `pyyaml`, `jinja2`, `fastapi`, `uvicorn`, `websockets`, `httpx`,
`huggingface_hub`, `transformers`, `accelerate`, `safetensors`, `onnxruntime-gpu`, `rembg`, `vtracer`,
`trimesh`, `pygltflib`, `playwright`, `pandas`, `soundfile`, `rich`, `typer`, `mcp`, `pytest`.
Optional extras: `[splat]` gsplat, nerfstudio; `[audio]` audiocraft or transformers MusicGen.

### Node (`package.json`)
Runtime: `lenis`, `gsap` (ScrollTrigger), `three`, `postprocessing`, `@sparkjsdev/spark` (splats), `d3`,
`maplibre-gl`, `pmtiles`. Build/UI: `vite`, `typescript`, `react`, `react-dom`, `@gltf-transform/cli`,
`sharp`, `zod` (schema mirror), `playwright`.

### Models (downloaded by the model manager)
| Model | For | Size | Licence (check before commercial use) |
|---|---|---|---|
| LTX-2.3 22B distilled fp8 + Gemma 3 12B text encoder + IC-LoRA Union Control + spatial upscaler | `film`, `morph` | ~35 GB | LTX-2 Community Licence |
| Z-Image Turbo + Fun ControlNet Union 2.1 + Qwen3 4B encoder | keyframes, stills | ~20 GB | Apache 2.0 |
| Depth Anything V2 (Large) | `parallax`, depth from photos | 1.3 GB | CC-BY-NC (Large) / Apache (Small) |
| BiRefNet or SAM 2 | segmentation for `artwork`, `sequence`, cutouts | 0.2–0.9 GB | MIT / Apache 2.0 |
| RIFE 4.x | `morph`, frame interpolation | <0.1 GB | MIT |
| Hunyuan3D-2 or TRELLIS | image → 3D for `sequence` from photos | 5–10 GB | Tencent community (region limits) / MIT |
| Real-ESRGAN (or LTX upscaler) | stills and frame upscaling | <0.1 GB | BSD-3 |
| MusicGen (optional) | music beds for recordings | 3–13 GB | CC-BY-NC |

The open-source project itself is MIT or Apache 2.0; model licences are listed in the model registry and shown
in the UI when a model is first downloaded.

---

## 7. Build order

1. **Engine skeleton**: spec schema, job graph and cache, CLI, `doctor`, model registry.
2. **Runtime**: scroll core, step cards, `video-scrub`, `frame-seq`, `layers-gl`, `svg-draw`, `three-scene`.
3. **Port the demos into scene modules** and rebuild them from `examples/` as the acceptance test:
   `film` (from run.py + ltx_comfy.py + blockout_lib), `artwork` (from build_mona.py, with auto focus
   instead of hard-coded landmarks), `scene3d` (from bio.html, split into generator presets).
4. **UI + server**, then the **MCP server and Claude skills**.
5. New scene types: `sequence`, `parallax`, `type`, then v2.
6. Installers, docs, CI (build every example at low resolution on each change).
