# Miniature worlds: a diorama you orbit and dive into

A `diorama` section is a tilt-shift model of a tiny world (a harbour town, a market town, a desk, a factory floor, a
studio) drawn live in the page. Scrolling orbits the camera round the whole thing, dives to a place where one step's
content sits (a lighthouse, a crane, a market stall, a laptop), lifts back out and travels to the next. The look is a
macro photograph of a model: shallow depth of field that blurs the near and far edges, a high soft sun, toy proportions
and saturation, a base with a cut edge standing on a table. No people, no video, nothing to render: the world is laid
out by the engine in a couple of seconds and drawn by three.js in the browser, so the pointer can turn the view, the
text stays real text and the scene's own data (a ground picture, the plan, a flat map) is a few hundred KB.

The showcase is [`examples/little-harbour`](../examples/little-harbour/site.yaml): Harbourlight, port software told
as the port itself.

```yaml
- id: harbour
  type: diorama
  world: { kind: harbour, seed: 7 }
  camera: { orbit: ccw }
  look: { sun: golden, tilt_shift: 1.0 }
  places:
    - { name: Lighthouse, kind: lighthouse }
    - { name: Wind farm, kind: windmill }
    - { name: Container yard, kind: crane }
    - { name: Customs house, kind: office }
    - { name: Fish market, kind: stall }
  steps:
    - { intro: true, kicker: Harbourlight, title: "Run a whole <em>port</em> from one screen." }
    - { kicker: "01 · Visibility", title: "See every ship, <em>from the horizon in.</em>", body: "..." }
    # one step per place, in order
```

## What each part decides

**`world`** is described once. `kind` picks the ground plan, the scenery and the vocabulary; `seed` picks the
arrangement (the same spec always gives the same world); `size` is the width in world units (a house is about 2; unset:
30 for a harbour or town, 26 for a factory, 22 for a desk or studio); `base` is `round` or `square`; `palette` replaces
the roof, hull and container colours; `density` scales trees, houses, boats and lamps; `props` sets extra things by hand
(`{kind, at: [x, z], turn, scale, color}`).

**`places`** are where the camera goes. Each has a `name` (the sign, the pin), a `kind` (the hero prop), a `where` and
optionally `step`, `side`, `sign`, `scale` and `color`. `where` is coordinates `[x, z]` from the middle (x to the right, z
towards the viewer), or words: a compass point (`north-east`; north is the back), `centre`, `edge`, or one of the
world's own spots. Unset, a place takes the spot that belongs to its kind. A place gets its hero prop, a little set
dressing around it, a sign with its name, and a pin over the orbit view (a button: it scrolls to that step).

**`steps`** are the content. The first may be `intro: true`: the world seen whole. The rest take the places in order; a
place can claim a step with `step: n`, or a step can name its place with `state: { place: "Lighthouse" }`. A step with no
place (a closing step) is another view of the whole world. `layout` is `cards` (the default, copy scrolling beside the
world; `side` says which side the world takes), `split` or `overlay` (captions over the scene; each caption's `at`
window is filled in from the steps' lengths).

**`camera`**: `orbit` (`auto` swings the short way between places; `cw` / `ccw` always the same way round), `pitch` (the
orbit view's height, degrees), `dive_pitch`, `fov` (narrow flattens the world into a macro photograph), `dive` (closer
above 1), `hold` (how much of each step's scroll the camera rests at its place) and `drift` (idle breathing and how far
the pointer can turn the view).

**`look`** is live and never rebuilds anything: `tilt_shift` (0 is sharp everywhere, 1 a macro lens on a model, above 1
extreme), `saturation`, `sun` (`morning`, `noon`, `golden`, `dusk`), `table` (the surface it stands on; default the
theme background), `grain`, `vignette`.

## Worlds and their vocabulary

| world | base | what is on it | hero kinds (`places[].kind`) | spots (`where`) |
|---|---|---|---|---|
| `harbour` | round | a bay with a channel to the front edge, a ring road, a headland hill, a container yard, a plaza, meadows | lighthouse, crane, warehouse, stall, office, ferry, windmill, shop, cafe | hill, yard, plaza, quay, meadow, village, bay, pier |
| `town` | round | a river with a bridge, a main street and a cross street, a cobbled square, houses facing the streets, a hill | clocktower, fountain, shop, cafe, windmill, stall, office | square, tower, street, market, mill, hall, river, park |
| `desk` | square | a wood desk with a mat | laptop, monitor, mug, books, plant, deskLamp, notebook | centre, back, right, left, corner, lamp, front, front-right |
| `factory` | square | a concrete floor with safety lines, cells and aisles | conveyor, robot, tank, silo, chimney, warehouse, office | line, cell, tanks, silo, stack, dock, office, yard |
| `studio` | square | a wood floor with a rug and a paper sweep | easel, softbox, camera, monitor, speaker, sofa, shelf, plant | sweep, easel, lights, desk, lounge, shelf, speaker, corner |

The kit also draws, as scenery or for `world.props`: tree, pine, bush, rock, lamp, bench, fence, crate, barrel, flag, sign,
house, container, boat, buoy, bollard, pier, bridge, forklift, pencils, rug. Things move: water, a lighthouse beam, a
windmill, a crane's trolley and its load, boats bobbing, flags, steam over a mug, smoke from a chimney, a conveyor, a
robot arm. A prop kind the kit does not know is drawn as a plain block and logged.

## How it is built

`engine/diorama/` lays the world out on the CPU, with numpy and no GPU, deterministically from the spec:

1. **Terrain** (`recipes.py`, `recipes2.py`): a height field (hills, a bay or a river), the water, and the ground painted
   top-down into a 2048 px texture (grass with flowers, water depth, kerbs, asphalt with dashed lines, cobbles, fields,
   wood grain, concrete joints). The same picture, with the props drawn as footprints and the places numbered, is the flat
   map shown until WebGL is up and in place of the scene when it is missing.
2. **Places** (`plan.py`): a place's `where` becomes a position and a facing; the hero, its dressing and its sign are
   placed; a view cone in front of it is kept clear of scenery.
3. **Scenery** fills what is left: houses facing the water or the street, clustered trees, a fringe round the rim, lamps,
   boats on the water, containers in the yard. A soft contact shadow under every prop is baked into the ground.
4. **Camera** (`plan.py`): one beat per step. A place's azimuth is chosen from a dozen candidates round the hero's
   front: each is scored by how much of the sight line (and of a cone round it) tall things block, and by tall things
   close to the lens that would become big blurred shapes in the corner; a Viterbi pass then picks the azimuths that are
   cheapest overall with the least swinging between places, in the direction `orbit` asks. The sign is seated beside the
   place as that camera sees it, so it is in the focal plane when the camera has dived in.

The stage is cached by the world, the places, the camera and the steps' timing (`.build/<id>/stamps/diorama.json`). The
look is not part of the key: change the sun or the tilt-shift and nothing rebuilds.

`runtime/src/players/diorama.ts` (with `diorama/`) draws it:

- **Props** (`kit.ts`, `kit2.ts`) are drawn from boxes, cylinders, spheres and roofs with toy proportions into a few big
  merged meshes: positions baked to world space, paint in vertex colours with a cheap baked ambient occlusion, and a
  procedural surface (roof tiles, planks, brick, foliage, container ribs, deck boards) drawn in the shader from world
  position, so there are no textures to load. Some 120 props become a few dozen draw calls.
- **Terrain, water and the base** (`terrain.ts`): a polar mesh wearing the painted ground, still water with ripples and
  foam where it meets the shore, and the cut edge of the diorama: grass lip, soil, clay and stone, the sea in section where
  the bay reaches the edge, a wooden plinth, all on a table with a soft contact shadow.
- **The miniature look** (`post.ts`): the scene is drawn into a multisampled half-float target with a depth texture, then
  one pass does a thin-lens depth of field (the blur grows with a pixel's distance from the focus plane, so a high view
  across a model blurs its near and far edges like a tilt-shift lens; sharp things never bleed into blurred ones), tone
  mapping, a saturation lift, a vignette and grain. The focus is always the camera's target, so the place the camera has
  dived to is sharp and the rest of the world melts away behind it.
- **Camera** (`camera.ts`): while a beat's content is on screen the camera rests at its place; between two beats it
  lifts out, sweeps round the world at a distance, and dives in, as one swooping arc (the three motions overlap). The
  pointer turns the view a few degrees; the camera breathes a little at rest.

## Phones, reduced motion, scrolling

- Phones (under 760 px): a wider lens so the world fits a portrait frame, the subject pushed up above the copy, less blur,
  2048 px shadows, 2x MSAA, a lower pixel budget (1.1 M pixels), pin labels as numbers.
- `prefers-reduced-motion`: the camera shows one still view per place and cuts between them (no travel, no idle motion, no
  water ripple, no pointer turn). The copy is the same.
- The scene is never a scroll trap: it is a pinned canvas under ordinary scrolling, pins are real buttons that jump to
  their step (`aria-label` "Go to ..."), they leave the tab order when the camera dives, and the copy is live text.
- Without WebGL the flat map of the world stays, with the places numbered, and the copy reads as usual.
- Resolution adapts by itself: the scene is drawn at the screen's pixels up to a budget (2.3 M pixels; the depth of field
  hides the rest), and a stretch of frames over 34 ms lowers the budget by a fifth, down to half; a long fast stretch
  raises it again.

## Looking at it

`studio diorama <project> [--section id] [--strip] [--full]` lays the section out and says what it decided (the places
and where they are, which step lives at which, the camera's azimuth and distance at each, how far it orbits in all) and
writes `diorama/<id>-map.jpg`, the flat map with the places numbered. It takes a couple of seconds and needs no GPU. With
`--strip`, it also photographs the built site (headless Chrome) at every place at rest and at the lift, the orbit and the
dive between places, as one contact sheet, `diorama/<id>-strip.jpg`. The MCP tool `diorama_layout` returns the same
summary. `studio storyboard` shows the map as the section's card. Try the sun and the lens in the browser console:
`__dio.post.o.tilt = 1.6` (the live scene is `window.__dio`).

## Why live 3D, and what was measured instead

The brief was to find the best way to get a 3D-feeling diorama on this machine, and to pick by measured result.

| approach | measured | verdict |
|---|---|---|
| **A generated diorama photo** (Z-Image Turbo, 1344x768, "tilt-shift photograph of a miniature harbour on a wooden base") | The look is exactly right: sculpted toy houses, a striped lighthouse, boats, a real tilt-shift blur. One image, though. | The art direction target for the live render, not a world to travel in. |
| **That photo as 2.5D** (Depth Anything V2 large, the engine's `freeze` renderer) | Sway of 0.1 view-widths per unit of depth (about a 10 degree orbit) holds; at 0.2 the lighthouse and the crane streak and the houses tear. Zooming to the lighthouse is soft: a 1344 px source gives about 2x before it blurs. | Cannot orbit (a quarter turn is impossible) and cannot dive. Fine for a nudge, not a journey. |
| **Image to 3D** (TRELLIS.2 through `engine/backends/trellis.py`, or ComfyUI's Hunyuan3D / Trellis2 nodes) | Not installed: no TRELLIS environment (`trellis_python` unset), no Trellis2 or Hunyuan3D weights in the ComfyUI models folder. Not downloaded (the brief forbids new weights). | Unmeasured. Even installed, a whole diorama as one baked mesh has a hallucinated back and a texture too coarse for a dive. |
| **A splat** (`splat` scene, `engine/backends/splats.py`) | There is no scan of a diorama and nothing local makes one from a prompt. | Nothing to measure. |
| **Live three.js, laid out by the engine** (this) | A flagship world of about 120 props, 5 places: 60 fps locked at 1600x900 on the RTX 4090 (D3D11), about 4 ms a frame (4.6 ms at 1920x1080); the scene's data is under 0.4 MB (three.js is shared with the other 3D scenes). Free orbit, any dive, a pointer-driven view, real depth of field, and everything stays vector sharp at any zoom. | Chosen. |

What the live approach gives up is the photograph's sculpted surface detail; it makes up for it with true depth of field
on real geometry, soft shadows, baked contact shadows and animation.

## Limits, honestly

- The props are drawn from primitives: charming, toy-proportioned, but not sculpted. Up close a house is a box with a
  roof, windows and a door. The photograph a generative model makes has more surface than any of this.
- The worlds are one layout recipe each, varied by seed. Harbour and town are the richest; the desk, factory and studio
  have fewer props and fewer spots.
- The camera avoids tall things in the way by choosing an azimuth; it does not path-find, so a very crowded world (`density` 2)
  can still put a prop near the lens during the dive.
- Water is a still surface with ripples and foam, not a simulation, and nothing reflects the props.
