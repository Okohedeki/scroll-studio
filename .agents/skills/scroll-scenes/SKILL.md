---
name: scroll-scenes
description: Reference for DesignAI's scene types and interactive features - what each scene is for, what it needs (GPU, files, nothing), how the visitor interacts with it, and the techniques for films (continuous beats, frozen moments, camera moves, colour reveals, region edits, transitions). Use when choosing or configuring a scene, or when a scene does not look or behave right.
---

# Scenes and how visitors play with them

Field-by-field details live in the spec: `studio schema` or the MCP tool `spec_schema('<type>')`. Worked examples are in
`docs/scenes.md`. This page is for choosing well.

## The scene types

| Type | What the visitor gets | Needs |
|---|---|---|
| `film` | Generated video scrubbed by the scroll; captions over it. `journey:` makes the page one camera take through one world | GPU + ComfyUI (LTX-2.3 or Wan 2.2) |
| `parallax` | A photo turned into a 2.5D camera move from its depth map, one photo per step | CPU (PyTorch); `generate:` pictures need ComfyUI |
| `type` | Kinetic typography driven by the scroll (`mode`: reveal, stack, swap, scale, weight) | nothing |
| `stages` | One subject changing state step by step (drawn, cut, assembled, finished) with wipes and a band of light on the change | aligned pictures of one view |
| `light` | One place relit from dawn to night as the page scrolls; windows light up at dusk | one picture + ComfyUI (relighting) |
| `scene3d` | A live 3D zoom through nested levels: cell-field, cell, nucleus, helix, galaxy, star-system, planet, network, lattice, particles, or a glTF model | nothing (renders in the page) |
| `diorama` | A tilt-shift miniature world (harbour, town, desk, factory, studio) the camera orbits and dives into, a place per step; movers and traffic | nothing (laid out on the CPU) |
| `code` | A flight through a codebase in live 3D: an opening window where the task types itself, files read, edits applying as diffs, a run printing its output | nothing |
| `chart` | A data story: a chart that draws, zooms, highlights and annotates itself | a CSV or inline data |
| `map` | A route on a live vector map | nothing |
| `artwork` | Any picture drawn and painted in stages as you scroll | a picture |
| `vector` | A logo or line drawing whose strokes draw themselves, then fill | an SVG, or a raster to trace (`vector` extra) |
| `sequence` | A 3D model rendered to frames (turntable, explode, assemble) and scrubbed by the scroll | a 3D model + Blender |
| `showroom`, `inside` | The real product live in the page (turned, exploded, zoomed; the pointer turns it), or the camera flying into it | `product:` with a 3D model |
| `splat` | A walk through a real place from a Gaussian-splat scan | a scan file |

Blocks (`hero`, `intro`, `features`, `stats`, `timeline`, `quote`, `product`, `strip`, `gallery`, `orbit`, `faq`, `logos`,
`signup`, `cta`) carry the facts between scenes.

## Interactive features

- **The pointer** (`pointer:` on `parallax`, `film`, `stages`): `mode: light` is a torch over a dark picture that falls
  off with depth; `mode: lens` is a circle showing a second layer (the picture's colour through a black-and-white page, a
  before/after, the inside of a product). On a phone it follows the finger. Choose it when exploring is the point.
- **Live 3D** (`scene3d`, `diorama`): the visitor turns and dives; each step is a level or a place.
- **Scroll as a scrubber** (`film`, `light`, `stages`): scrolling back plays time backwards; the visitor controls pace.
- **Living pictures:** `cinemagraph:` on any image (only one thing moves, everything else held still) and `live:` (one
  small detail alive) make blocks feel present without a film.
- **Type in the world** (`place:` on a step of a `film` or `parallax`): the headline sits inside the scene, behind a
  tree, painted on a wall, set in the haze.
- **Transitions** (`transition:` on a section): `match` (a shared shape carries the cut), `carry` (an element travels to
  the next section), `iris`, `wipe`, `whip`, `dissolve`, `cut`. One or two per page, where they mean something.
- **Styles** (`theme.style`): a style changes how the whole site scrolls and reads (split-flap, comic pages, zoetrope,
  paper theatre ...). `docs/styles.md` lists them; `studio looks` builds the site in several.

## Films: techniques

- **Continuity.** Beats meant to look like one scene start on the previous beat's last frame:
  `image: { beat_frame: { beat: <id>, at: last } }`. A crossfade between pictures that do not line up shows as a pop.
- **Time stops: freeze, don't generate.** A video model cannot hold a crowd still while the camera moves. Make that beat a
  frozen moment: `freeze: { from: <beat id>, upscale: 2, camera: [{ t, box: [x0, y0, x1, y1], hold? }], parallax: 0.6 }`.
  It renders offline in seconds from one upscaled frame and a depth camera, so faces never change. Keep `parallax`
  0.3-0.8 and the boxes near the aspect of `beat_res`.
- **A camera move on a moving shot:** `camera: { keys: [{ t, box }], subjects: "the people" }` on a beat flies a path
  through the start image's depth into a guide the video model follows. Preview with `studio camera <project> <beat>
  --guide`, check with `--check`.
- **Colour that follows the camera:** render in full colour, then add `reveal:` (`base: mono`, `regions` with a `prompt`
  and an `at: {beat, t}` frame where the thing is plainly in view, `keys` mapping scroll to 0-1). Never ask the video
  model to colour only part of a picture.
- **Edit only a region:** `image: { edit: { source, instruction, region: { prompt, pick, grow, feather } } }` keeps
  everything outside the mask pixel for pixel. Fix a wrong mask with `pick`, `within`, `points`, `grow`, not by
  rewording the instruction.
- **Faces:** `faces: restore` on a beat or the film repairs faces in generated video (needs `studio setup-comfy`).
- **Two video models:** LTX-2.3 (default) or Wan 2.2 (`video_model: wan`) per site or beat.
- **After building:** `studio inspect <project>` scores pops, softness, halos, style drift and morphs; fix what it names.
