# Changelog

What changed in each version of Scroll Studio, newest first. Versions follow the project's milestones; each lists the
commits it spans so you can check out any earlier state (`git checkout <commit>`).

Everything so far is version 1. On 2026-10-12 the releases first published as 2.0.0 and 3.0.0 were renumbered
1.1.0 and 1.2.0 (tags `v1.1.0` and `v1.2.0`).

## Unreleased (1.5)

Planned: see the [1.5 milestone](https://github.com/Okohedeki/scroll-studio/milestone/1).

### Added
- Contribution guides: CONTRIBUTING.md (ground rules, what a complete feature includes, consistency rules for
  themes and styles), a CLA, code of conduct, security policy, issue forms and a pull request template. CI runs the
  tests on every pull request, `main` takes changes only through pull requests with the tests green, and
  `tests/test_conformance.py` checks every theme preset and style (tokens, contrast, block types, docs, and a page with
  every block type in every style).
- Layout snapshots of every example (`tests/test_layout_snapshots.py`), the 1.5 release gate.
- Inside flights take `light:` keys over the scroll (exposure, ambient, lamp, rim, lamp colour, eased between keys),
  so the light can change as the page goes: evening to lamplight to lights out. Frames are only redrawn where the
  light changes.

### Changed
- Map scenes preload their flight: while the loading screen is up the camera visits every stop (and the far point of
  each long move) and waits for its tiles, keeps them cached, and draws labels without fading, so the scroll never
  waits on the network. Measured on Tidewater Lines in Chrome on the GPU: hitches over 50 ms went from 2-3 per
  scroll (up to 150 ms) to none, for about 5 s more on the loading screen (capped at 10 s, 6 s on phones). Routes
  are added once and revealed with a gradient instead of being rebuilt every frame.

### Fixed
- Button text on the accent colour now passes WCAG AA in the `ink` preset and seven styles (anime-intro, comic-book,
  halftone, isometric, particles, pop-up-book, stop-motion), and stop-motion's accent text on its paper. These colours
  show where a style falls back to the default markup (scene captions, unstyled blocks).

## 1.4.0 · 2026-10-13 to 2026-10-20

Commits after the `v1.3.0` tag to the `v1.4.0` tag.

The headline: new ways to move through a page. The one-take page, cinemagraphs, light as the scroll, inside the
product, miniature worlds, film cuts between sections, type in the world, direction boards and six more animation
styles; plus frozen moments with deep zoom, keyed camera moves on generated video, scroll-driven colour,
storyboards, a polish report, product integration, launch trailers and Wan 2.2.

### Added
- Miniature worlds: scene type `diorama`, a tilt-shift diorama you orbit and dive into. `world` (kind `harbour`, `town`,
  `desk`, `factory` or `studio`, seed, size, base, palette, density, extra props) is laid out once by the engine
  (`engine/diorama/`: height field and water, the ground painted top-down, places with hero props, signs and dressing,
  scenery, baked contact shadows, a camera plan whose azimuths are chosen by a Viterbi pass over sight lines); `places`
  (name, kind, `where` as coordinates, a compass point or a spot of the world, `step`, `side`, `sign`, `scale`, `color`) are
  where the camera dives to and where a step's content sits; `camera` (`orbit` auto/cw/ccw, `pitch`, `dive_pitch`, `fov`,
  `dive`, `hold`, `drift`) and `look` (`tilt_shift`, `saturation`, `sun`, `table`, `grain`, `vignette`; live, never part of a
  cache key). The player (`runtime/src/players/diorama.ts`, `diorama/`) draws it in three.js: toy props merged into a few
  meshes with procedural surfaces, still water, a cut-edge base on a table, a thin-lens depth of field over a multisampled
  half-float target, a camera that rests at each place and swoops between them in one arc, pointer turn, idle motion
  (water, a lighthouse beam, a windmill, a crane, boats, steam, smoke, a conveyor, a robot arm), pins that jump to their
  step, adaptive resolution, a wider lens and lower budget on phones, one still view per place for reduced motion, a flat
  map when WebGL is missing. `studio diorama <project> [--strip] [--full]` and MCP `diorama_layout` report the layout and
  write the map (and a frame strip of the built site); the storyboard card is the map. Docs: `docs/miniature.md` (fields,
  vocabularies, method, measurements against a generated photo, 2.5D, image-to-3D and splats, limits). Example:
  `examples/little-harbour`. Tests: `tests/test_diorama.py`.
- Style `paint-on-glass` (Aleksandr Petrov, *Loving Vincent*): the page is one oil painting on a lit pane, never cut. Scroll distance is brush strokes laid toward the next picture, coarse to fine, each dragging the old colour into the new; scrolling back paints forward again (paint can't be unpainted); a slow boil keeps it alive at rest; the pointer smears wet paint. Research in `docs/styles/styles-30-31.md`.
- Style `multiplane` (Disney's multiplane camera): each section is a stack of painted glass plates at real distances; scroll trucks the camera down through the stack, plates grow and pass the lens, focus pulls to the plane carrying the words, and a foreground plate sweeps past to cover changes inside a list; the pointer trucks sideways and pulls focus.
- The product as the set (`type: inside`): the camera flies into `site.product` and the page happens inside it, one stop
  per named part with its copy arriving there (macro lens, shallow depth of field, a lamp that travels with the camera and a
  rim light behind the part). Stops are globs on part, mesh and assembly names (`part:`), or points (`point:`) for a model
  with no named parts, with `span` (mm of the real product in view), `lens`, `fstop`, `focus`, `roll`, `explode`, `aim`,
  `yaw`/`pitch`, `hold`, `travel`; with no `stops:` they are chosen from the model's most distinct parts. Parts between the
  camera and the stop dissolve (a cutaway worked out with ray casts over the whole route), the route is eased so the camera
  lands softly, the copy is placed on it, and every frame is cached on its own camera so changing one stop redraws only the
  frames near it. Phones get a 960 px set; reduced motion gets one still per stop. `studio inside <project> [--still] [--strip]`
  and the MCP tool `inside_route` print the route and render stills; storyboard cards show the wide shot and each stop. Modules:
  `engine/inside.py` (route), `engine/scenes/inside.py` (builder), `backends/blender_scripts/inside.py` (Cycles),
  `runtime/src/players/frames.ts` (shared with `sequence`). Example: `examples/inside-board` (Framework Laptop 12 mainboard,
  CC BY 4.0, concept page).
- Style `scratch-film` (Len Lye, Norman McLaren, Stan Brakhage): scroll pulls a strip of drawn film through a gate. Text steps in perforation-sized pulls and seats with a bump; the strip runs down the edge with sprockets and a drawn soundtrack; a new scratched, dyed or pressed drawing is projected every frame; sections are spliced reels with one flash frame (flashing kept within safe limits); the pointer is a needle that scratches the emulsion; optional sound. Research in `docs/styles/styles-32-33.md`.
- Style `smears` (Spider-Verse timing): the page is sampled 12 times a second; where a pose changes, headlines, numbers, buttons and pictures are drawn as smear frames with trailing colour plates, faster scrolling adds multiples, no blur anywhere; plates slip with speed while the focused element stays in register; crossing into the next sheet fast gives one impact frame (at most one per 520 ms); the pointer leaves multiples.
- Cinemagraphs: `cinemagraph: {moves, motion, seconds, loop: seamless|pingpong, strength, ...}` on any image input (hero, product,
  strip, gallery tile, section backdrop). A still where only one thing moves: Florence-2 + SAM 2.1 find `moves`, LTX-2.3 or Wan 2.2
  animate a crop around it (first = last frame for a seamless loop), SAM tracks it through the clip, the mask is grown to where the
  clip really moves, the frames are stabilised and tone-matched to the still, the loop is closed (flow-aligned crossfade) and only the
  moving part is encoded (H.264 + a lossless WebP mask). The page lays the video over the still through a CSS mask, so outside the
  mask the still's own pixels are shown; plays in view, pauses off screen, still under reduced motion / data saver
  (`runtime/src/lib/cinemagraph.ts`, wired by `data-cine` on the finished markup, so every style takes part). Stages cached per
  variant in `.build/_cinemagraph/`; plain images and the cache keys of films that use a cinemagraph image are unchanged.
  `studio cinemagraph <project> [--only] [--force] [--list] [--check [--mobile]]`, MCP `cinemagraphs`, a measured report per
  cinemagraph (loop seam, share of the picture that moves, change outside the mask, bytes) and a Chrome check of the built page.
  `gallery` tiles now take any image input. Example: `examples/tern-house`. Module: `engine/cinemagraph.py`, `engine/cinemagraph_check.py`.
- Light as the scroll: scene type `light`. One place relit from dawn to night as the page scrolls; each step is a time of day. The
  world is one picture (a file, a generated image, an edit, or `scene:<id>`); `times:` are presets (dawn, sunrise, morning, noon,
  afternoon, golden-hour, sunset, blue-hour, night, overcast, storm; `engine/light_presets.py`), free text, or `image:` pictures
  of your own; `world_time:` names the one the world already is. Build (`engine/scenes/light.py`, `engine/light.py`; stages `world`,
  `depth`, `sky`, `time_<id>`, `maps`, `web`, each cached, an unchanged spec renders nothing): every time is Qwen-Image-Edit asked to
  change only the light, then measured against the world (light-invariant structure: band-passed log luminance with local contrast
  normalisation, dense optical flow, edge F-score; drift in px at 1024 across), its global move (zoom, shear, shift: most of what
  the editor does to a place) undone with a robust affine fit so nothing is bent, and retried with another seed when still too
  far (`structure.align: affine | flow | none`, `max_drift`, `retries`); `flow` additionally pulls local structure in with
  optical flow (matches edges better, bends lines). Between neighbouring times the build writes the low-frequency light-change
  field (guided by the world's edges, log-encoded), a flow texture of the structure that remains different, and a lamp map (small
  bright features the ambient change cannot explain, optionally confined to regions named in `lamps:` with Florence-2 + SAM 2.1
  through `engine/region.py`, each light with its own delay and a halo). Play (`runtime/src/players/light.ts`): scroll moves
  continuously through the day with a hold at each step (`hold`) and the change passing between headlines; a shader applies the
  light change to both pictures, switches the rest with a front of new light spreading from the sun, glides along the flow so
  edges slide into place instead of cross-fading doubled, pops windows and lamps on one by one with a halo, draws `haze` as
  drifting mist thicker with distance, drifts the camera slowly through the depth map (`drift`), optionally travels a sun and
  moon glow over the sky (`sun`), shows a clock and sun arc, and follows the sky with the section's colours (ink, accent, shade,
  contrast-checked; each headline keeps the colours of its own time). Phones get a smaller picture set and a `focus` crop;
  reduced motion shows one still per step; without WebGL the stills are images, one per step. `studio light <project>` builds the
  section and writes `light/<id>/` (times sheet with measured drift, a frame strip across every transition, `light.json`);
  `studio light --presets` lists the named times. Example: `examples/harbour-light` (Quay House). Tests: `tests/test_light.py`.
- The one-take page: `journey:` on a film section makes the whole landing page one camera journey through one generated world.
  A journey is a `world` described once and ordered `stops` (places), each with its `blocks` (hero, intro, features, stats,
  timeline, quote, faq, product, cta, gallery), a `hold` (screens of scroll the page rests there) and a `move` (how the camera
  gets there). Two ways to make the film from the same spec: with a `blockout` (the world as rough shapes, as a take's) one
  continuous take whose camera is a real 3D path that rests at every stop (`pose`, `move.path`), a picture of each stop painted
  over the blockout's depth and the video model painting between them, cut at the middle of a hold; without one, a chain of
  keyed camera moves between stop pictures (`move.into`, `move.via`) each followed by a frozen moment of the frame it arrived at,
  so the camera flies only into what the picture before shows (measured in docs/ENGINE.md). The runtime maps scroll to the film
  with a piecewise map (a move plays as you scroll through it, a hold is the page resting at a stop; nothing is snapped or
  captured), blocks arrive as the camera slows into a stop and leave as it moves on, a rail names the places and scrolls to them,
  `#stop-id` deep links land on a stop, a portrait phone crops the wide picture around each stop's `focus`. Where the blocks sit
  is found from the stop's own picture (calmest side by gradient energy, alternating sides; light or dark lettering; a scrim
  raised only until the lettering clears WCAG AA); `side`, `form` (`type`, `rail`, `cards`, `plaque`) and `surface` override it.
  With reduced motion, without JavaScript or when the film fails the page is the stops as stills with their blocks in order and
  no film is downloaded. `studio journey <project>` and the MCP tool `journey_plan` print the plan (film seconds and scroll
  per move and hold, and where each stop's blocks were put); `studio build --plan`, `studio storyboard` and `studio inspect`
  see a journey as the take or beats film it builds. Modules: `engine/journey.py`, `runtime/src/players/journey.ts`,
  `engine/compile/templates/journey.html.j2`. Example: `examples/fenmoor`. A saved spec keeps only what was written (the derived
  `beats`/`take`, `steps`, `length` are not dumped).
- Style `stop-motion`: scrolling fires the shutter. Every 26-42 px is one exposure, poses change on twos, never faster than 12 a second, and nothing moves between exposures. Between sections the set is struck and dressed (cast lifted off, a bare set with tape crosses, the new set and cast placed). Clay letters, felt cards, masking-tape labels, a felt `theme.art`; poke a piece and it hops, an onion-skin switch shows the last exposure. Research in `docs/styles/styles-28-29.md`.
- Style `paper-cut-out`: Lotte Reiniger and Terry Gilliam. The top sheet swings off its brass brad as you scroll and uncovers the next; words on paper strips, tags and snapshots hang on hinges and sway with scroll speed; feature cards fan from one pin, a folding rule opens, a mobile of tags turns; a jointed black paper arm (two-bone IK) points at what you have reached.
- Direction boards: `studio directions <project> [--n 6] [--seed] [--brief] [--pick K] [--undo] [--reroll K] [--serve]`, MCP tools
  `directions`, `direction_reroll`, `direction_pick`, `direction_undo`, and an optional `directions:` block in the spec (brief,
  count, seed, moods, `keep`, `styles` / `fonts` / `palettes` only and avoid, brand colours, stills per board). One brief in, several
  complete art directions out (concept line, palette, type pairing, an engine style, an imagery treatment, motion notes, voice),
  each a board of storyboard stills (hero and key sections, Z-Image Turbo, the same seeds in every direction) set in its own
  palette and type, side by side on one page (`directions/board.html`, served like the storyboard editor, with a Pick button) plus a
  PNG contact sheet. The writer is deterministic (no text model exists in the engine): schools of design, palettes, pairings,
  imagery treatments and photographers' lights in `engine/directions/vocab.py`, chosen for fit and spread, then checked pairwise by
  a distance over kind, experience, colour, type and imagery; weak pairs are regenerated. A pick writes `theme`, `imagery` and
  `scroll.speed` into site.yaml as a minimal diff (backup in `directions/backups/`, `--undo`), and never touches copy.
  Modules: `engine/directions/`. Example: `examples/kiln-and-kettle`.
- `imagery:` (site-wide): medium, light, lens, mood and palette added to every generated image and film prompt
  (`engine/imagery.py`), dropping the phrases of the original prompts it replaces (`restyle`). Unset: nothing changes and no cache
  key moves. The Google Fonts families directions pair now load with their verified axis specs (`engine/directions/typefaces.py`).
- Edited like a film: `transition:` on any section (scene or block) hands over to the next in film grammar instead of a plain
  scroll: `cut` (an instant cut on a scroll position with a held beat either side), `dissolve`, `wipe`, `iris`, `whip` (a
  fast directional blur-pan), `match` (the end of one section and the start of the next share a shape; each side scales and
  moves until the shapes coincide and the picture swaps on the shape) and `carry` (an element travels from its place in one
  section to its place in the next). A join gets its own stretch of scroll in which both pictures are held (the section
  above pinned at its last screen, the one below at its first) and the scroll plays the cut on the sections' own wrappers, so
  it works for every section type; `engine/cuts.py`, `runtime/src/lib/cuts*.ts`. Match shapes come from a prompt (Florence-2 +
  SAM 2.1 through `engine/region.py`), a box, a page element, or, unnamed, from the pictures' own contours
  (`engine/cuts_shapes.py`, cached in `.build/_cuts/`). `image: {match: {section, shape, becomes, prompt, how}}` designs an
  image to match another section's last frame (Qwen-Image-Edit, or Z-Image with the shape's place written into the prompt:
  `engine/cuts_design.py`). `studio cuts <project> [--strip]` and the MCP tool `cuts` list the cuts and write frame strips
  around each. Reduced motion, no scripts and `layout: stack` keep today's plain flow; nothing changes without a `transition:`.
  Example: `examples/film-cuts`.
- Type in the world: a step's title can live inside the scene instead of floating over it. `place: { kind: behind | surface |
  sky, ... }` on a step of a film (`layout: overlay`, with an `at` window or a pinned beat) or of a parallax section; the
  caption positions (`place: left`...) work as they always did and `place: sky` is shorthand. **behind** sets the title at a
  depth, as a prompt (`at: "the spruce tree"`: found by Florence-2 + SAM 2.1, the type sits just behind it) or a number, so
  what is nearer passes in front of it as the camera moves; **surface** paints it on a wall, a sign or a floor (`at: "the
  wooden deck"`): SAM 2.1 tracks the surface through its shot (the `reveal` stages), the plane's orientation comes from the
  depth map (a plane's disparity is linear in the picture), and a per-frame homography from planar tracking carries the
  letters in perspective; the surface's light, grain and relief show through the paint, its grain ragged-edges every letter,
  it wears (`wear`, `relief`) and is laid on left to right as the step arrives; **sky** is large type in the haze at far
  depth with fog in front (`fog`, `haze`). Per film the engine makes a steady depth video (Depth Anything V2 per frame,
  aligned frame to frame by a robust scale-and-shift fit through optical flow, blended where the flow is trustworthy,
  snapped to the picture's edges by a guided filter, restarted at every cut: `engine/world_depth.py`), tracks each title
  with pyramidal LK from keyframes (similarity for a layer, homography for a surface; Savitzky-Golay smoothed:
  `engine/world_track.py`) and packs the depth and up to three surface masks into one grayscale atlas video with the
  film's own frame rate, frame count and GOP, plus a phone copy (`engine/world.py`). The page draws the film itself in
  WebGL2 (`players/world.ts`; a parallax photo in `players/parallax.ts`, with `build_photo`): the title is typeset with the
  site's fonts and `<em>` style onto an atlas texture and found per pixel through the frame's matrix, shown where the scene
  is farther than the title, lit by the light there, mixed with the air there, defocused like the footage at that depth and
  carrying the picture's grain; the film and the atlas are seeked together and drawn only when both have landed. Reduced
  motion, no WebGL, and a title that would be cropped off a narrow screen (a phone held upright) fall back to an ordinary
  caption; the title stays in the page as text either way. Everything is cached per stage (`world_depth` once per film and
  model, `world_text_<i>` per title: a headline's words matter only by their length, `world_pack`); a film without in-world
  type keeps its cache and runs none of it. `depth_model` on the film section picks the Depth Anything size. `studio world
  <project>` (and MCP `world_check`) draws each title's box on the film's own frames with the depth beside them, measures
  how steady the track is and how much of the window the type is on screen, and says what to change; `build --plan` prices
  the stages. A `sequence` section (a rendered product on a transparent backdrop, `layout: overlay`) takes in-world type
  too, with no model: its frames' alpha is the silhouette the type sits behind (`world_alpha`, `world_film`: the frames
  also become a film for the world player; the frames play as always without it). A layer with nothing to track (a plain
  backdrop, clear sky) keeps the type on the screen, and a cut nobody listed is found by the optical flow. The Studio UI's
  step form has an "On the picture / In the world" switch. Example: `examples/type-in-the-world`
  (the one-take world, all three placements) and `examples/type-in-the-world-stills` (Casa Alta photographs).
- `beat.restore`: SeedVR2 over one beat's clip at a given height, scaled back to `beat_res` (stage `restore_<beat>`), so a soft camera beat can be restored next to sharp frozen moments without restoring the whole film (`beat_restore`).
- Camera ease `smoother` (freeze and camera beats): smootherstep, speed and acceleration both zero at every stop, so the camera settles into a hold instead of landing with a jolt (`studio inspect` read the jolt as judder).
- Deep zoom for frozen moments: `freeze.detail` builds a pyramid of tiles (`engine/zoom.py`, `zoom_build.py`, `zoom_render.py`)
  so a push from the wide shot to a 20x close-up is sharp at every scale. The tiles the camera needs are found from its keys
  (set cover over a lattice, as many levels as the tightest box needs: `levels: auto`, at most `ratio` x detail per level);
  each is a crop of its parent enlarged (SeedVR2, or Lanczos), re-drawn at low `strength` (Z-Image Turbo img2img; the
  whole level in one ComfyUI job), despeckled, aligned to the parent (ECC), and given the parent's low frequencies exactly
  (`lock`), with a depth snapped to its own edges. The render takes each pixel from the finest tile that covers it and fades
  levels in by screen-space pixel density with feathered tile borders. Each tile is its own cached stage (keyed by its box and its
  parent's key). `studio freeze <project> <beat> [--plan] [--report]` prints the plan, renders one beat and measures it
  (sharpness per zoom, frame-difference plot, strip: `engine/zoom_report.py`). Qwen-Image-Edit is available as the re-draw
  (`method: qwen`), experimental: it moves things. New fields join cache keys only when set.
- Layered depth for frozen moments: `freeze.layers` (`engine/layers.py`) cuts the frame into planes: a background plate with
  the subjects painted out (Florence-2 "people" or named subjects, SAM 2.1 masks in one job, Qwen-Image-Edit fill kept only
  inside the hole) and subject planes grouped by depth, each with its own smooth depth and soft alpha, composited back to
  front with foreground colour estimation at the edge. No halo or double edge at depth jumps, and real background revealed
  behind a person. Works with `detail`: each tile carries its planes' alphas and continues the plate. `planes.jpg` shows
  what was found. `build --plan` prices both (`film:freeze_zoom` per tile, `film:freeze_layers`).
- Polish report: `studio inspect <project> [--section ID] [--json] [--embed] [--video FILE]` and the MCP tool
  `inspect_film`. A built film section (beats, a take, a `video:`) is scored on the CPU, second by second and beat by
  beat, for **pops** (flow-residual jumps over a large part of the frame, one-frame flicker, judder, and crossfades between
  beats that should line up), **softness** (fine-detail index in the frequency domain on the busiest tiles, with the edge
  width), **halos** (share of clean edges with a bright rim or seam, against the film's own baseline), **style drift**
  (hatch/pencil share of the picture's structure against the scene's first second, grain, and within a still shot tone,
  line density and saturation; optional OpenCLIP embedding distance with local weights, nothing downloaded) and **morphs**
  (the share of the change between frames that optical flow cannot explain). Beats that join like one scene (the meeting
  frames look alike) are scored as a continuation; a join between unlike frames is a scene change and is not flagged.
  Every measure is a number that reads as a sentence, calibrated on the Presence landing page (the hands close-up is soft
  and haloed, the turn beat drifts to a pencil look and rearranges the crowd, the stage changes pop) and checked against
  `examples/feel` and `examples/one-take` for false alarms. Output: `.build/inspect/<section>.json` (per-beat scores, issues
  with level, span, one-line reason and a hint, per-second timeline) and `.html` (timeline strip, the worst moments as
  pictures, scores per beat). Cached by the film's and clips' content: an unchanged build answers at once. The storyboard
  editor shows each beat's worst problem as a badge linking to the report and has a **Polish check** job button. Module
  `engine/polish/`; no new dependency (`--embed` needs `open_clip_torch` and the cached LAION ViT-H/14 weights).
- Camera moves on moving beats: a generated beat with `camera:` keys (`{t, box, hold}` and `ease`, as a frozen moment's camera)
  gets the camera it asks for instead of the one the prompt hopes for, while the crowd keeps walking. The start image gets
  a depth map (Depth Anything V2) and its moving subjects (`camera.subjects`, Florence-2 + SAM 2.1) a mask; the keyed
  path is flown through the depth with the freeze renderer into a guide video (the subjects' depth softened into blobs so
  the guide fixes the camera and the static world and leaves people free, `soften`), plus a pure-camera render of the picture
  and a static-world mask; then LTX-2.3 (the take's IC-LoRA depth control, the default) or Wan 2.2 Fun Control paints the
  beat along the guide, or Wan Uni3C (`backend: uni3c`, which names its missing 2 GB controlnet file, URL and folder).
  `camera.continues` makes beats share one camera path (position and speed carry across the cut, no ease to a stop), start
  on the previous beat's last frame (and join it as one hard, frame-exact cut instead of a crossfade) and fly their guide through the chain's base plate; `match` grades the frames toward
  the plate's tone and grain so clips do not drift. `studio camera <project> <beat> --guide` renders the pure-camera preview
  in seconds; `--check` (and MCP `camera_guide` / `camera_check`) measures the render against the keys (zoom and shift
  error per frame, how far the people walked, the measurement's floor) and writes a contact sheet. Beats without `camera`
  keep their cache; the plan prices it as `film:camera`. Modules: `engine/camera_guide.py`, `engine/camera_beats.py`.
- Region edits: `edit.region` confines an image edit to part of the picture. `region` takes a `prompt` (Florence-2
  grounding on the source, with `pick`, `within` and the "X's Y" owner rule from `reveal`), or `box` / `points` /
  `negative_points` (0-1); SAM 2.1 (image mode, through the existing `SSRevealTrack` node on a one-frame batch: no new
  ComfyUI node) cuts the mask at the source's resolution. `grow` and `feather` (pixels of the source) shape it, `invert`
  edits everything except the region, `scope: crop` (default) gives Qwen-Image-Edit a padded crop around the region
  (`context`) so a small region is drawn with the editor's full working size, `scope: image` the whole picture. The result
  is composited through the mask in integer arithmetic at source resolution: outside the mask the pixels are the source's,
  exactly, so chained region edits (shoes, hands, the whole figure) leave everything outside each region as it was and
  consecutive versions of a frame dissolve with no shimmer. `region: "the shoes"` is a prompt. The mask is saved as
  `edit_<digest>.mask.png` with an outline overlay; the storyboard sheet draws the outline on the card, the edit workspace
  shows it over the image and edits the region's prompt, `pick`, `grow` and `feather`. The region joins the cache key only
  when set (existing renders are untouched; the `examples/feel` plan still shows nothing to render). Module:
  `engine/region.py`; `reveal.find_boxes` is the grounding both features share.
- Frozen moments: a beat with `freeze:` is rendered offline instead of generated. It takes one frame (`from: <beat>`, the
  sharpest of that beat's last frames by default, or any `image:`), upscales it (`upscale: 2`; SeedVR2 image restoration
  through ComfyUI, or a local Lanczos + sharpen when its weights are not installed), estimates its depth (Depth Anything
  V2, snapped to the picture's edges) and flies a 2.5D camera through it along `camera:` keys (framing boxes in 0-1 of the
  frame, with `hold`, eased paths with no jerk at keys, `ease: flow` to keep moving through them) with a depth parallax
  that keeps the subject plane still (`parallax`, `dolly`), optional motion blur and film grain. The render (a ray marched
  through the depth map per pixel, in torch) takes seconds; the frame, upscale and depth are cached apart from the camera.
  The clip is the beat's `clip.mp4`, so it joins the film like a generated beat (`trim`, crossfade, `beat_restore`,
  `locked`, `--only`); the storyboard shows the camera's boxes as flat crops of the source and a flat preview move, the
  editor has fields for it and for each box number, and `build --plan` prices it apart from a generated beat.
- `image: { beat_frame: { beat, at: first | last | <seconds>, pick } }`: any image input can be a frame of a beat, so a
  generated beat starts exactly where a frozen moment (or another beat) ends. Beats that use it re-render when that beat's
  clip does; under `build --only` a beat that is not rendered stands in with its storyboard still.
- Scroll-driven colour reveal: `reveal:` on a film section. The film renders once in full colour; `base` (mono, dim, blur
  or a tint colour) is what un-revealed pixels look like, and each region (a `prompt`, `points` or a `box` on an `at`
  frame) comes into colour by `keys` over the section's scroll progress, eased. Masks: Florence-2 turns a prompt into
  boxes on the frame, SAM 2.1's video predictor follows them forwards and backwards inside their shot (a cut ends a
  track; beats are known cuts, other films are scene-detected or listed in `reveal.cuts`), cached per region
  (`reveal_ground_<id>`, `reveal_track_<id>`). The masks are packed up to four to a grayscale atlas video with the
  film's frame rate, frame count and GOP, plus a half-size copy for phones (`reveal_pack`: feathered, `grow`n). The
  runtime draws the film through a WebGL2 shader (`runtime/src/players/reveal.ts`): a film frame and its masks always
  from the same frame, colour film without WebGL2, jumps per region with reduced motion. The storyboard and animatic
  draw every shot as the page will show it (base look; masked colour once a build made the masks); the plan lists the
  stages with estimates; `studio doctor` checks the nodes and models. Spec: `FilmScene.reveal`, `Reveal`, `RevealRegion`,
  `RevealAt`.
- Face repair for generated video: `faces: restore` on a film or a beat (`Faces`: `strength`, `min_size`, `smooth`).
  GFPGAN v1.4 (Apache-2.0) over faces found by facexlib, blended back softly, smoothed over time in aligned space,
  in chunks of frames through ComfyUI; cached (`faces`, `faces_<beat>`); off by default.
- `studio setup-comfy` installs what these need into ComfyUI (kijai's ComfyUI-segment-anything-2 and ComfyUI-Florence2,
  Scroll Studio's own `scroll_studio_nodes`, the GFPGAN weights); `comfy_dir` in studio.toml says where ComfyUI is.
  `comfy.run_outputs` returns every output node's record, not only saved images.
- The storyboard is editable: `studio storyboard <project> --edit [--port N]` (also `/sb/<project>` in `studio ui`) serves
  one card per shot with every field editable in place (caption, prompt, motion, seconds, seed, trim, strength, motion
  seed, a take's keyframe prompts and motion segments, an edit's instruction, a product still's scene and view). Saves
  go into `site.yaml` as a text splice, so comments, alignment, quoting and line endings are untouched (ruamel's
  round trip, with the file's own indentation, for what a splice cannot do), after validating against the spec (an
  invalid value is shown on the card, nothing is written); the last 30 previous texts are kept in
  `storyboard/history/` with an Undo. Per image: Regenerate (a new seed), Re-run (same seed after editing text) and
  Revert render only that image's stage through the full build's code and cache digests (beat still, end image, edit,
  take keyframe, product still; never video, restore or product passes) as a background job with progress on the card.
  Every render is kept as a variant (`storyboard/variants/`); clicking one writes its seed (and text) back into the spec
  and restores it to the build's cache. Edit chains show each shot's own step with the shared base steps listed once at
  the top (an edit there reaches every shot using it). Lock (`locked: true`), Approve (`storyboard/state.json`, shown
  on the sheet and by `build --plan`), one job per image, and a page that notices `site.yaml` changing on disk.
  MCP: `storyboard_shots`, `set_shot_field`, `regenerate_shot_image`, `pick_shot_variant`, `approve_shot`.
- The storyboard editor takes notes instead of instructions: each card has a *What should change?* box and a **Notes**
  tab takes general notes (pacing, tone, copy, order), saved as an inbox in `storyboard/notes.json` with status (open,
  working, done), the agent's reply and what the note led to. Claude reads them through the MCP tools `storyboard_notes`
  (each open note with its shot's current spec values and image paths) and `resolve_note`, or from
  `studio storyboard <project> --notes`; edits and renders made while a note is being worked on are attached to it, and
  the page refreshes when the spec, a variant or a note changes in another process. The exact prompts, instructions,
  motion and seeds are behind an **Advanced** fold per card (closed by default, remembered per browser), and the shared
  steps fold the same way.
- A **Play** tab plays the whole storyboard in the editor: `animatic.mp4` with shot markers on the timeline (click to
  jump, the playing shot and its card highlighted), *Rebuild animatic* (a job that re-cuts from what is rendered, with
  `storyboard(generate=False)`: no ComfyUI, no Blender; marks the cut stale when shots change), and the stand-in page and
  the built page in a frame with an auto-scroll. `animatic.timeline.json` records where each shot sits in the cut.
- A take's keyframe may set its own `seed` (default: the keyframes' shared seed, so nothing existing re-renders).
- `inputs.generated_path` / `inputs.edit_path` (the cache digests of generated and edited images, unchanged) and
  `BuildContext.adopt` (record that outputs on disk are what a stage key makes).
- Storyboard first: `studio storyboard <project> [--level sketch|stills|animatic] [--only ids] [--motion] [--open]`
  and the MCP tool `storyboard`. A card per shot (beat, take, film, product still, block image) with its opening and
  end frames, prompt, motion, caption, length, fidelity, status (new / changed since the last storyboard / unchanged /
  locked / rendered) and the full render estimate on this machine, in `storyboard/sheet.jpg` and `storyboard.html`;
  the real page built into `storyboard/site/` with stills standing in for unrendered films (scrubbed by scroll, a
  corner badge); `animatic.mp4` at `animatic` (Ken Burns along the take's camera or the beat's motion verb, timed
  cuts, the page's captions and the trailer's end card); `--motion` adds a 512x288 LTX-2.3 preview per shot. Frames
  come from the full build's own stages and caches (beat stills, `blockout` + `keyframes`, image inputs, product
  stills), so approved frames are the films' first frames; low-sample previews are keyed apart. `sketch` needs no
  ComfyUI (a take's world at a few moments, placeholder cards for images not generated yet).
- `locked: true` on beats, takes and scene sections: build and storyboard keep what is rendered even when settings
  change, with a log line.
- `studio build --only id,id` renders just those sections or beats (other beats keep their clip or stand in with
  their storyboard still, never stamped); `--plan` prints what would render and the estimate (calibrated from the
  stage stamps' `seconds`, `engine/plan.py`); every build prints it first, and studio.toml `confirm_over` (minutes)
  asks before longer builds (`--yes` for unattended runs). MCP `build` takes `only` and `plan_only`.
- The `keyframes` stage repaints only the keyframes whose own settings changed (stage keys unchanged).
- Overlay captions can sit anywhere on the shot (`place: top-right`, `bottom-left`, `center`...), take their own
  colours with a soft glow behind them when the shot under them is brighter or darker than the rest (`surface:`),
  and carry a `button:`, so a film can end on its call to action. A caption pinned to the end of a film's last beat
  stays up until the scene lets go.
- A scene's `surface:` now applies to the scene itself in the flow layout (it used to colour only the stack layout's
  panel), and the nav takes the colours of the section under it, so a dark film on a light site gets a dark nav.
- `site.product`: the product declared once (name, maker, url, model, licence, credit, `concept`). Models in GLB/glTF,
  OBJ, FBX, STL, PLY, **STEP/STP** (converted locally with OpenCascade through `cascadio`, parts kept as separate meshes
  with their names) and **3MF** (trimesh), from a file or URL. `up`, `units` and `rotation` fix any file; `parts` sets
  materials by part/assembly/mesh glob, material name, a `region` of the bounds and a `facing` (so a one-piece body
  can have a screen window); `exclude` drops alternate variants; `tessellation` and `max_triangles` keep huge CAD
  files in check (only heavy meshes are thinned). Cached as one normalised GLB in `.build/_product/`
  (`engine/product.py`, `backends/blender_scripts/product_prep.py`, `backends/cad.py`).
- Product stills anywhere an image is accepted: `image: {product: <view>}` with views front, three-quarter, side, top,
  back, hero-low, exploded and detail (`part:`, a macro view with shallow depth of field). Framed on the real
  silhouette (about two thirds of the frame), Khronos PBR Neutral colour, soft contact shadow, transparent where the
  page shows it. `scene:` renders the product into a perspective-matched Z-Image backdrop, lit by it, harmonised by a
  light Qwen-Image-Edit pass and checked against the product's own edges.
- `showroom` scene: the product live in the page (three.js, the normalised GLB, environment light, soft shadow);
  scroll keys turn, explode and zoom it; a Cycles poster until it loads.
- `studio product <project> [--parts] [--still <view>]` and MCP tools `product_parts`, `product_still`.
- Footer: the product's credit and licence, and "Concept page. Not affiliated with <maker>." for `concept: true`.
- Takes: plate-matched light by default (environments made from the generated frames, the ground's colour under the
  shadow, sun from `take.light`), depth of field at the camera's look-at, motion blur, and a composite graded to the
  plate (black level, white balance, saturation, softness, grain, light wrap). `product: {}` uses the site's product;
  product passes default to 64 samples at the final film size. `track` stage writes `product/track.json`, the
  product's screen position per frame (for vertical reframing).

### Changed
- Take stage keys are portable: the generated world (blockout, keyframes, LTX) no longer depends on the product (unless
  it is in the depth guide) or on absolute paths, so moving a project or changing the product never re-renders the
  world. Stamps written by the old keys are recognised and migrated.
- Block images keep their transparency (WebP with alpha) instead of being flattened.
- `sequence` scenes take `model: product` (or no model) and the product's own explode offsets.
- ComfyUI client: time spent waiting in a shared ComfyUI's queue no longer counts towards the timeout, and a
  timed-out job is cancelled only if it is ours (it used to interrupt whatever was running).
- URL models stored with Git LFS on GitHub are fetched from media.githubusercontent.com automatically.
### Added (launch trailers)
- `trailer:` in the spec and `studio trailer <project>` (MCP tool `trailer`): a launch film cut from the site's own
  renders in 16:9 and 9:16 (`dist/trailer/trailer-16x9.mp4`, `trailer-9x16.mp4`, posters). Shots come from film takes
  and beats (by step, beat or time range), scroll recordings of other sections (at phone size for 9:16), type cards
  and product stills (`site.product`, when the product feature is present). `trailer: {}` derives the cut: hook,
  story, product reveal, feature callouts (a product block's tags, features or stats) and an end card. Cuts land on a
  `bpm` grid; `music:` is trimmed, faded and loudness-normalised; captions and the end card use the theme's fonts and
  colours, animate on the beat and keep to the TikTok/Reels safe areas. Cached per stage in `.build/_trailer`.
- 9:16 reframing: a take's product is projected through the take's camera (`take.py --pass track`) so the crop
  follows it, the reveal is cut where it is biggest in frame, and the push-in on it goes as far as the source
  resolution allows; other footage uses a saliency-guided crop (spectral residual plus faces).
- `trailer.embed`: a "Watch the launch film" button on the opening section and a modal player (the 9:16 cut on
  portrait screens).
- `take.restore`: SeedVR2 over a take's generated world before the product composite, as `beat_restore` does for beats.
- `studio record` internals take a device pixel ratio, phone emulation and a part of the scroll.
- Wan 2.2 A14B as a second local video model beside LTX-2.3: `video_model: ltx | wan` on the site (default for
  every beat, take and `theme.art`), on a beat, a take or `theme.art`, or in studio.toml (`video_model = "wan"`); LTX
  stays the default. `wan:` settings (site-wide, or per take): `quality: fast` (the lightx2v 4-step LoRAs, cfg 1) or
  `full` (~20 steps, cfg 3.5, no LoRAs), `steps`, `cfg`, `shift`, `res`, `interpolate` (mci, blend, dup), `stretch`, `guide_blur` (takes).
  LTX stays the default: in a side-by-side test Wan was not sharper after restore (see README).
  Two-stage MoE sampling (high-noise expert for the first half of the steps, low-noise for the rest) at ~1280x720,
  16 fps, retimed to 24 fps with FFmpeg's motion-compensated interpolation (RIFE isn't installed, so not used).
- Beats with Wan: `image` is the first frame and `end_image` the last (WanFirstLastFrameToVideo). A clip is at most 81
  frames; a beat up to 1.35x that is one clip played slower, longer ones chain clips from the previous last frame.
- Takes with Wan: Wan 2.2 Fun Control paints the world along the Blender depth guide, from the keyframe at each
  clip's start (and the keyframe in its range as a reference), in the segments and prompts of `ltx:`, chained clip to
  clip; the product pass and composite are unchanged. Renders live in `.build/<section>/wan/` with their own stage
  names, so switching models never discards the other model's film.
- `engine/models.yaml`: the eight Wan files with their Hugging Face URLs and VRAM notes; `studio doctor` checks each
  one through ComfyUI's own model lists (subfolders and junctions included). Names that differ from the defaults go
  in studio.toml `[wan]`; a file moved to another subfolder is found by its base name.

### Changed
- `comfy.run`: time spent waiting behind another client's job on a shared ComfyUI no longer counts toward the
  timeout, so a timeout can't cancel someone else's render.
- Cache keys: `video_model` enters a key only when it is not ltx, so every LTX beat, take and art cache stays valid.

## 1.3.0 · 2026-10-11 to 2026-10-12

Commits after `83bfbc7` to the `v1.3.0` tag.

The headline: five styles from classic animation (flipbook, pop-up book, pinscreen, sand and a zoetrope you spin),
story films told in shots, a live 3D codebase flight, and local image edits.

### Added
- Style `zoetrope`: the whole landing page is one wheel of printed cards on a giant strobe zoetrope. Every element
  (hero, each feature, each stat, each step, each question, the call to action) is a card with its own animation.
  Spin it with scroll, swipe, drag or the button; it strobes alive, slows with real friction and lands on a card;
  click a card and it flies out to be read. Research: docs/styles/styles-24-25.md.
- README: why Scroll Studio (local only, 10 to 30 times fewer tokens) with a worked token breakdown.
- Styles `pinscreen` (a dark, lamp-lit board of pins after Alexeieff and Parker: each plate is a pin picture and a wave
  of pins rolls it into the next; the pointer moves the lamp and presses pins) and `sand` (a backlit sand table after
  Caroline Leaf: one scroll sweeps a mound of grains across into the next scene; pictures are poured and cleared in
  sand, the pointer draws furrows). Research: docs/styles/styles-22-23.md.
- `type` scene `mode: weight`: words grow from thin and faint to heavy and solid in reading order, on a variable
  display face (`weights: [200, 800]`). Lines (split with ` / `) are sized at the heaviest weight so the finished
  passage fits the screen and nothing reflows on the way.
- `theme.labels: plain`: kickers, tags, timeline dates and the footer in sentence case in the body face, for brands
  that never set spaced capitals.
- `theme.display_em: heavy`: emphasis as a change of weight (upright, the text's own colour, the heaviest weight).
- `footer.links`: links in the footer to pages hosted elsewhere, such as a privacy policy.
- Styles from classic animation: `flipbook` (a pad of animation paper; one scroll notch lets go of one page, so
  pencil drawings animate; drag the dog-ear to flip) and `pop-up-book` (one book on a table; scroll is the hinge angle,
  scenes rise out of the gutter, pull-tabs raise the stats, a paper wheel turns the timeline). Research:
  docs/styles/styles-24-25.md and styles-26-27.md.
- Image edits: an image input can be an `edit:` of another (Qwen-Image-Edit, local), with up to two reference images.
  Beats take an `end_image:` so a shot lands exactly on a chosen frame, and `beat_restore:` cleans the joined film
  with SeedVR2.
- `film` with `beats:`: a story told in shots. Each beat is a generated still animated by LTX-2.3, cached on its own and
  crossfaded into the next; captions pin to beats (`state: { beat: … }`). Example: Feel.
  Beats take `strength`, `motion_seed` and `trim` for action shots that freeze on their first frame.
- `code` scene: fly through a codebase in live 3D following an agent at work. It opens on the agent's prompt box and
  dives through it; read files line a corridor, edits apply their diffs as you scroll, a run prints its output, a status
  bar ticks off the todo list, and captions pin themselves to files (`state: { file: … }`). Text stays real and readable.
- Copy fields accept `<code>` for inline commands.
- `theme.art`: a prompt (or `file:`) becomes artwork a style draws in its own medium, generated locally with Z-Image
  and, with `motion:`, animated by LTX-2.3 into a seamless loop. `ascii-art` prints it in characters in the hero and
  the render pane; `particles` turns it into a full-screen field of points.
- `theme.art` loops cut where the motion repeats: the build finds the stretch of the clip whose last frame matches its
  first while keeping most of the movement, so fast motion (a dribble) loops without a double exposure.
- `theme.art` tone mapping reads the background from the frame's border and lifts dark subjects, and a light
  background is flipped, so a subject prints as a solid figure. Tip: a dark subject reads best on a plain white
  background, a light one on black.

### Changed
- `type` scene `mode: swap`: on a narrow screen the rolling word shrinks until the longest one fits (it used to run off
  the edge on phones); the fixed words keep their size.
- `code` scene follows the scroll exactly (no trailing flight after you stop), draws lighter frames, and warms up the GPU
  behind the loader.
- `particles`: the hero is a field that fills the whole screen (the art, when there is one) and drifts apart as you
  scroll into the first formation.
- `blueprint`: next, next, next. The pen starts on the next view while the camera is still moving there, construction
  lines take less scroll, and moves between views are short, so no screen is empty paper.

### Fixed
- An animation re-rendered shorter than before no longer keeps the old render's trailing frames.
- `studio looks` refreshes the site's runtime, so rebuilding only the looks never runs a stale one.

## 1.2.0 · 2026-10-10 (first published as 3.0.0)

Commits `34dd0c5` to `83bfbc7`.

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
- Showcase: the 1.2 examples and a "New in 1.2" section.

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

## 1.1.0 · 2026-10-06 to 2026-10-08 (first published as 2.0.0)

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
