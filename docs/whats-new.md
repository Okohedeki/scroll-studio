# What's new

[← README](../README.md) · [Why Scroll Studio](why.md) · [What's new](whats-new.md) · [Examples](examples.md) · [Guide: make a site](guide.md) · [Styles](styles.md) · [Scenes](scenes.md) · [Licence](licence.md)

### New in 1.5

1.5 is about making a page your own and making it look finished. Watch the
[30-second film](https://okohedeki.github.io/scroll-studio-showcase/recordings/1.5.mp4), or scroll the six new example pages in the
[showcase](https://okohedeki.github.io/scroll-studio-showcase/). Every spec from 1.4 builds the same page as before.

**Make it yours**

- **Your brand from a link, a logo or a file.** `theme: { from: ... }` reads the colours, fonts, button radius and
  logo from a web page, a logo image or a `brand.yaml`, and `studio brand --from` writes them into site.yaml for you to
  edit. ([Themes and brands](guide.md#themes-and-brands))
- **Every look is a token.** Spacing, type scale, the shade over pictures, motion, film grain and the phone width are
  theme settings now, each defaulting to how pages looked before. ([Themes and brands](guide.md#themes-and-brands))
- **Your own fonts.** Any font role can be a font file in your project instead of a Google Fonts family, served with
  the site. ([Themes and brands](guide.md#themes-and-brands))
- **One way to place and time words.** In every scene a caption says where it sits (`at`: a named spot, a box or a
  slot on a 12-column grid), when it shows (`show`) and how it arrives and leaves (`enter`, `exit`).
  ([Placing words](guide.md#placing-words), [Millrace](https://okohedeki.github.io/scroll-studio-showcase/millrace/))
- **Any block as a step.** A scene's step can be stats, a quote, features, a timeline, a call to action, a gallery, a
  product card or an FAQ, placed and timed like a caption. ([Placing words](guide.md#placing-words))
- **Styles are optional, and wear your brand.** A page needs no style; when you add one, it keeps its scroll mechanic
  and layout but takes your brand's colours and fonts, down to the parts it draws in code.
  ([Themes and brands](guide.md#themes-and-brands))

**Quality**

- **Pictures in one medium.** `imagery.medium` draws every picture on the page as risograph, toile, engraving,
  gouache, watercolour, halftone or ink, in your brand's inks, and keeps calm space where the headline sits.
  ([Art direction: a medium](guide.md#art-direction-a-medium), [Kitewell](https://okohedeki.github.io/scroll-studio-showcase/kitewell/),
  [Tidelow](https://okohedeki.github.io/scroll-studio-showcase/tidelow/))
- **Living details.** `live:` makes one small thing move in a still picture (drifting clouds, running water, rising
  dust, a glint), drawn by the page with no GPU.
  ([Living details](scenes.md#living-details-one-small-thing-alive-live), [Kitewell](https://okohedeki.github.io/scroll-studio-showcase/kitewell/))
- **The landing page kit.** Badges, buttons with icons, a ghost button, a rating line, an email signup, a logo strip,
  divided stats and a framed hero, all in your theme. ([Landing page pieces](guide.md#landing-page-pieces))
- **The pointer as a light or a lens.** `pointer:` on a photo or film turns the visitor's pointer into a lamp on a
  dark picture or a circle of colour on a black-and-white one; on a phone it follows the finger.
  ([The pointer](scenes.md#the-visitors-pointer-reveals-the-picture-pointer), [Gloamery](https://okohedeki.github.io/scroll-studio-showcase/gloamery/),
  [Tarnhollow](https://okohedeki.github.io/scroll-studio-showcase/tarnhollow/))
- **A polish report for the page.** `studio inspect my-site --page` checks the built page at desktop and phone size
  for text that is hard to read over its picture, type, blown-up pictures and layout, and names the fix in spec terms.
  ([Check a page before you ship it](guide.md#check-a-page-before-you-ship-it))

**Faster starts**

- **Remake a page you already have.** `studio remake <url>` reads a live landing page and writes a scroll site from
  its copy, pictures, sections and brand. ([Remake a landing page](guide.md#remake-a-landing-page),
  [Bramblecote](https://okohedeki.github.io/scroll-studio-showcase/bramblecote/))
- **Laptop mode.** `studio new my-site --laptop` writes a starter that builds with no GPU, ComfyUI or Blender.
  ([Try it on a laptop](laptop.md))
- **A doctor that tells you what you can build.** `studio doctor` opens with what this machine can build without a GPU,
  and the one install that unlocks each thing it cannot yet. ([Try it on a laptop](laptop.md#1-install))

**Safety and the project**

- **Deprecation warnings and a compatibility promise.** Spec fields due to change warn when you build, and a written
  policy says what stays the same between releases. ([Compatibility and deprecation](compatibility.md))
- **Checked model files.** Downloaded model weights are checked against a recorded SHA-256 before use, and
  `studio doctor --verify` checks the ones already on disk.
  ([Threat model](security/threat-model.md#model-weights-run-code-when-loaded))
- **A site.yaml is treated as untrusted.** Paths that leave the project, `javascript:` links and markup in text are
  refused or shown as plain text. ([Threat model](security/threat-model.md#a-spec-reads-or-writes-files-outside-its-project))
- **Local servers answer only this machine.** The Studio UI, preview, storyboard editor and direction boards refuse
  requests for other hosts and from other websites.
  ([Threat model](security/threat-model.md#local-servers-are-reached-by-other-web-pages))
- **A docs site.** The documentation is at [okohedeki.github.io/scroll-studio](https://okohedeki.github.io/scroll-studio/),
  with search, and its spec, command and MCP references are generated from the code.

### New in 1.4

- **The one-take page** (`journey:` on a film section): the whole landing page is one camera move through one generated world; every section is a place in it (the door, the rooms, the table, the window, the view), the page's blocks arrive at their stop set as part of the picture, and the camera rests while they are read. ([The one-take page](scenes.md#the-one-take-page-journey))
- **Cinemagraphs** (`cinemagraph:` on any image): a still where only one thing moves (steam, a curtain, smoke, water);
  everything outside the mask is held pixel for pixel and the loop is closed without a seam.
  ([Cinemagraphs](scenes.md#cinemagraphs-one-thing-moves-cinemagraph))
- **Light as the scroll** (`type: light`): one place relit from dawn to night as you scroll. Each time of day is the same
  picture relit with the geometry measured and locked; a WebGL shader carries the light between them (a front of new light,
  windows and lamps coming on one by one, mist, a slow 2.5D drift) and the page's colours follow the sky.
  ([One place, dawn to night](scenes.md#one-place-dawn-to-night-type-light))
- **Inside the product** (`type: inside`): a macro camera flies into the product's own 3D model, stopping at named
  parts, with the parts in the way cut away. ([Inside the product](scenes.md#inside-the-product-type-inside))
- **Miniature worlds** (`type: diorama`): a tilt-shift diorama you orbit and dive into, live in the browser; every
  section lives at a place on it. ([Miniature worlds](scenes.md#miniature-worlds-diorama))
- **Edited like a film** (`transition:` on any section): match cuts, irises, wipes, whips, hard cuts and carried
  headlines between sections instead of fades. ([Edited like a film](scenes.md#edited-like-a-film-transition))
- **Type in the world** (`place: { kind: behind | surface | sky }` on a step): headlines that live inside the scene:
  set behind a pine so the camera passes them, painted on a deck in perspective, written in the haze with fog in front.
  ([Type in the world](scenes.md#type-in-the-world-place))
- **Direction boards** (`studio directions`): how a design studio pitches. One brief in, several complete art directions
  out, side by side on one page, so you pick a direction in minutes before committing to a build. Pick one and it is
  written into `site.yaml`. ([Direction boards](guide.md#direction-boards-pitch-it-before-you-build-it))
- **Six more styles from classic animation:** `stop-motion`, `paper-cut-out`, `scratch-film`, `smears`
  (Spider-Verse timing), `paint-on-glass` and `multiplane`. Thirty-two styles in all.
  ([try them on Halcyon](https://okohedeki.github.io/scroll-studio-showcase/halcyon/looks/))
- **Frozen moments** (`freeze:` on a beat): when time stops, stop generating. One frame, upscaled, with a 2.5D depth
  camera moving through it, rendered offline in seconds, so a crowd stands still while the camera visits a couple's
  hands and feet and every face stays the same face. `image: { beat_frame: ... }` chains the next shot onto its last frame.
  `detail:` builds a pyramid of re-drawn tiles so a 20x push stays sharp; `layers:` cuts people out onto planes over a
  painted-out background so depth jumps have no halos.
- **Camera moves on moving shots** (`camera:` on a beat): keyed camera paths for generated video, so the crowd keeps
  walking while the camera pushes from the wide street to one girl and back out. The camera is flown through the start
  image's depth into a guide video, with the walking people softened so they stay free, and the video model paints the
  shot along it (measured: the view stays within 1% of the keys).
- **Colour that follows the camera** (`reveal:` on a film section): render the film once in full colour; the page shows
  it black and white (or dimmed, blurred, tinted) and brings colour into tracked regions as you scroll.
  ([Colour that follows the camera](scenes.md#colour-that-follows-the-camera-reveal))
- **Face repair** for generated video (`faces: restore`, GFPGAN v1.4).
- **Storyboard first** (`studio storyboard`, `--edit`): sketches, stills and an animatic before any video render, with an
  editor to redo one image at a time. ([Storyboard first](guide.md#storyboard-first))
- **Polish report** (`studio inspect`): every film scored second by second for pops, softness, halos, style drift and
  morphs. ([studio inspect](scenes.md#find-the-polish-problems-before-the-owner-does-studio-inspect))
- **Your product, declared once** (`site.product`, STEP/3MF), **launch trailers** (`studio trailer`) and **Wan 2.2** as a
  second video model.

### New in 1.3

- **Five styles from classic animation.** `zoetrope`: the landing page is one wheel of cards you spin, land on and
  open to read. `pop-up-book`: scenes fold up out of the gutter as the book opens. `flipbook`: one scroll notch, one
  pencil page. `pinscreen`: a lamp-lit wall of pins rolling from picture to picture. `sand`: a backlit sand table swept
  scene to scene. ([try them on Halcyon](https://okohedeki.github.io/scroll-studio-showcase/halcyon/looks/))
- **Story films told in shots** (`film` with `beats:`): every sentence its own generated shot, with end frames, local
  image edits and SeedVR2 clean-up. ([Feel](../examples/feel/site.yaml), the showcase's front door)
- **Fly through a codebase** (`code` scene): live 3D, real text, diffs applied as you scroll.

### New in 1.2

Full history of every version: [CHANGELOG.md](../CHANGELOG.md).


- **One Take** (`film` with `take:`): one unbroken camera move through a generated world. You block the world out
  in rough shapes and camera keys; Blender renders the depth guide, LTX-2.3 paints the world along it in chained
  segments, and your real product is rendered by Cycles from its own 3D model through the identical camera and
  composited onto every frame. The product never warps, because it is never generated.
  ([Stillwater](../examples/one-take/site.yaml))
- **Real places** (`splat`): a phone or drone scan as a Gaussian splat (`.ply` or a gsplat `.pt`), trimmed and
  compressed to SPZ at build time and walked through on scroll. ([Hollis House](../examples/hollis-house/site.yaml))
- **Numbers you can check** (`chart` callouts, `stats` bound to data): headline figures and chart notes are read
  from the source CSV when the site is built, so the copy can't drift from the data. ([Pelorus](../examples/pelorus/site.yaml))
- **Twenty-six styles that change the experience, not just the paint** (`theme: { style: … }`). Each style has its
  own scroll mechanic, layout, transitions and components, built from in-depth research
  ([docs/styles](styles/)): split-flap is a departures board that updates as the clock advances, comic-book is
  read panel by panel, anime-intro cuts like an anime opening, ASCII is a terminal session, blueprint is a drawing
  that drafts itself. `studio looks` builds a site in every style. ([Halcyon](../examples/halcyon/site.yaml))
- **Client work**: `studio copy export` gives the client a Markdown copy deck; `studio copy import` applies their
  edits back into site.yaml (comments kept, invalid edits refused). `studio brand --logo` draws a contrast-checked
  theme from their logo.
