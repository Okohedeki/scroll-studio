# Guide: make a site

[← README](../README.md) · [Why Scroll Studio](why.md) · [What's new](whats-new.md) · [Examples](examples.md) · [Guide: make a site](guide.md) · [Styles](styles.md) · [Scenes](scenes.md) · [Licence](licence.md)

## Make your own

```bash
studio new harbour-hotel --example atelier-sfumato   # or start blank: studio new harbour-hotel
# edit projects/harbour-hotel/site.yaml (or use studio ui), drop files in inputs/
studio storyboard harbour-hotel                      # every shot's real first frame, before any film renders
studio build harbour-hotel --draft
studio snapshot harbour-hotel --at top --at studio:0.5   # screenshots + contact sheet
studio build harbour-hotel && studio record harbour-hotel   # final build + an MP4 scroll-through
```

A spec is a theme, a nav and a list of sections. Scenes are the scroll-driven visuals; blocks (`hero`, `intro`,
`product`, `features`, `stats`, `timeline`, `strip`, `orbit`, `quote`, `faq`, `cta`, `gallery`) are the content between them.
Set `layout: stack` and every section becomes a full-screen panel that slides up over the one before it (see
[Hushwell](../examples/hushwell/site.yaml)); `surface: dark | light | accent` recolours a single section:

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
in the site's theme, served at `/<slug>/` and linked from the footer (`nav: true` adds them to the nav too). Raw HTML in a page's Markdown is shown as text rather than run, and links must be `http(s)`, `mailto:`, `tel:`, a relative path or a `#anchor`.

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

## Direction boards: pitch it before you build it

A studio does not start with the build. It shows the client three or six different ideas of what the site could be, side
by side, and the client points at one. `studio directions` does that from the site's own spec:

```bash
studio directions my-site                      # six directions: board.html + board.png in my-site/directions/
studio directions my-site --n 4 --seed 7       # another seed, another set
studio directions my-site --brief "calmer, more editorial, for people who travel slowly"
studio directions my-site --serve              # the boards in the browser, a Pick button on each
studio directions my-site --pick c             # write direction C into site.yaml (a minimal diff; backup kept)
studio directions my-site --undo               # put the file back as it was before the last pick
studio directions my-site --reroll d           # another idea in place of one direction
studio storyboard my-site                      # now every image redraws in the picked direction's imagery
```

Each **direction** is a complete art direction, not a colourway: a **concept** line; a **palette**; a **type pairing**
(Google Fonts the engine loads and self-hosts); one of the engine's **styles** (the experience: what scrolling does, how
sections hand over; or the default editorial layout); an **imagery treatment**, which is how every generated image and film
prompt is phrased (medium, light, lens, mood, colour in words) so the whole page looks like one shoot; **motion notes**
(page, camera, type) and the pace; and the **voice** that suits it. Its board shows the hero and two or three key sections
as storyboard stills (Z-Image Turbo, the same generator and seeds in every direction, so what differs is the direction),
set in that direction's palette and type, with the palette, faces, style and imagery written out under them. The page is
`directions/board.html` (open it, or `--serve` it like the storyboard editor), and `directions/board.png` is the same page
as one contact sheet.

**They differ in kind.** The set is built from schools of design (a naturalist's plate book, the Swiss grid, golden-hour
film photography, neon noir, drafting-table blueprint, a risograph zine, a picture book, soft clay, silver noir, art deco,
cut paper, a travel poster, a Dutch still life, Y2K chrome, an arcade, a terminal, a quiet product studio, reportage,
wabi-sabi, an old atlas, cel animation, Memphis pop), picked greedily so each next one fits the subject and is far from
those already chosen. A distance measure (kind of picture, experience, colour, type, what the pictures are made of) then
checks every pair; a pair closer than 0.5 is one idea twice, and the weaker of the two is replaced. The board header shows
the closest pair, how many kinds and experiences the set spans, and what was regenerated. Directions are listed from closest
to today's site to a different site.

**There is no text model, so the writer is deterministic.** The engine has no local language model (ComfyUI's `models/LLM`
holds Florence-2, a captioner, and Gemma is only LTX's text encoder), so ideas are not generated: they are composed from a
curated, combinable vocabulary (`engine/directions/vocab.py`: schools, palettes, type pairings, imagery treatments,
photographers' lighting such as Rembrandt, Vermeer window light or Penn's north light, and which engine styles give each
school the right experience), chosen to fit the subject and mood words found in the site's copy and the brief, and combined
by a seed. The same brief and seed give the same boards. Add a school by adding data; tests check every palette's contrast,
that every font loads and every style exists. Nothing is sent anywhere and there are no API keys.

The optional **`directions:`** block in the spec is the brief and the constraints:

```yaml
directions:
  brief: "Quiet and handmade, never precious; a working studio, not a gallery."
  count: 6
  seed: 4
  moods: [handmade, warm, calm]            # also read from the brief: calm, warm, bold, playful, technical, raw, nostalgic ...
  keep: [colors]                           # parts of today's look every direction keeps: style, colors, fonts, imagery
  styles:   { avoid: [pixel-art, ascii-art] }              # or only: [none, halftone, sand]; none = the default layout
  fonts:    { avoid: [Press Start 2P] }                    # or only: [Fraunces, Karla ...]
  palettes: { avoid: [pink], brand: ["#c2612a"] }          # brand colours become every direction's accent
  stills: 4                                # stills per board: the hero, then key sections
```

**A pick** writes the direction into `site.yaml` and nothing else: `theme` (style, mode, colours, fonts, display weight and
emphasis, radius), `imagery` and `scroll.speed`. Only what differs from what the site already resolves to is written, comments
and layout stay, the old file is kept in `directions/backups/`, and an edit that would make the spec invalid is refused.
**Copy is never touched** (a direction has a voice note, but the writer cannot write copy, so there is nothing to apply).

`imagery:` is a spec field on its own, so you can write it by hand:

```yaml
imagery:
  medium: 35mm film photograph, Kodak Portra 400, fine grain
  light: low golden-hour sun, long soft shadows
  lens: 35mm, eye level, shallow depth of field
  mood: unhurried, sun-warmed, quietly luxurious
  palette: honey, terracotta and sea blue
```

It is added to every prompt the engine sends to the image and video models (a `generate:` image, a beat's frame and clip, a
take's keyframes and segments), and with `restyle` on (the default) the phrases it replaces in the original prompts
(`photorealistic`, `shot on a medium format camera`, `golden hour`) are dropped first. Unset, nothing is added and no cache
key changes. Example: [Kiln & Kettle](../examples/kiln-and-kettle/site.yaml). MCP tools: `directions`, `direction_reroll`,
`direction_pick`, `direction_undo`.

## Storyboard first

A film costs an hour or more to render (LTX-2.3 or Wan 2.2, SeedVR2, a Cycles product pass over every frame), so
look at it before you pay for it. `studio storyboard` shows every shot of the page at a fraction of the cost, through
the same stages and caches the full build uses:

```bash
studio storyboard my-site --level sketch     # seconds, no ComfyUI: a take's grey world, cached stills, prompt cards
studio storyboard my-site                    # stills (default): the real first (and end) frame of every shot
studio storyboard my-site --level animatic   # the stills in motion, timed cuts and captions -> animatic.mp4
studio storyboard my-site --level animatic --motion --only door   # plus a tiny LTX preview of one shot's motion
studio build my-site --plan                  # what a build would render, and about how long it takes here
studio build my-site --only door,enter       # render just those beats (or sections); the rest keep their cache
studio storyboard my-site --edit             # edit every shot in the browser, regenerate one image at a time
```

It writes `<project>/storyboard/` (not committed, like `dist/`):

- `site/`: the real page, built with the storyboard's frames standing in for every film that isn't rendered yet
  (stills that dissolve into one another as you scroll; with a slow camera move at `animatic`), with the real copy,
  layout and style, and a corner badge so it is never mistaken for the finished site.
- `sheet.jpg` (one image an agent can read) and `storyboard.html`: a card per shot (a beat, a take, a product still,
  a block's image) with its frames, prompt, motion, caption, length, the fidelity of its frames (final, stills,
  sketch, placeholder), its status (new, changed since the last storyboard, unchanged, locked, rendered) and the full
  render estimate on this machine, calibrated from the seconds every stage records; the total is at the top.
- `animatic.mp4` at `animatic`: a rough cut with the page's captions in its own fonts and the trailer's end card.

Nothing is thrown away. A beat's still is the very image the beat is animated from (same input, same cache); a
take's frames are its `blockout` and `keyframes` stages, painted over the depth of the blockout the film is
generated along. So an approved frame is the film's first frame and the full build only adds motion. What only the
storyboard makes (a take's sketch, low-sample product stills and the product over its keyframes, motion previews,
placeholder cards) is cached apart, keyed by its samples, and never read by a full build.

Edit one beat and storyboard again: only that shot is redone, in seconds, and the sheet marks it. Editing one of a
take's keyframe prompts repaints only that keyframe. When a shot is right, lock it:

```yaml
beats:
  - id: door
    prompt: ...
    motion: ...
    locked: true      # never re-rendered by storyboard or build, even if its prompt or settings change
```

`locked: true` works on a beat, a take and any scene section; the build logs `locked, kept the existing render` for
each stage it keeps (a locked shot that was never rendered is rendered once). `studio build` prints its plan and
estimate before any heavy GPU work; with `confirm_over = 30` in studio.toml it asks first when a build would run
longer than that many minutes (`--yes` skips the question; without a terminal it stops instead of waiting).

### Edit it, one image at a time

`studio storyboard my-site --edit [--port 8971]` opens the storyboard as an editing workspace (a local server; the same
page is `/sb/<project>` in `studio ui`). Three tabs: **Shots**, **Notes** and **Play**. A card shows what you judge by:
the image or images with their variants, the caption, a *What should change?* box, Regenerate / Re-run / Revert and
Lock / Approve. The exact prompts, edit instructions, motion, seeds and strengths are behind **Advanced** on each card
(and the shared steps behind their own fold), closed until you open them; each browser remembers what it opened.

- **Say what should change.** Type a note in plain words on a card ("warmer light", "she should look older", "less
  grain"), or on the **Notes** tab for the whole storyboard (pacing, tone, copy, order, anything). Notes are an inbox
  in `<project>/storyboard/notes.json`; the page only collects them and shows each one's status (waiting for Claude,
  Claude is on it, done), Claude's reply, and what it led to (the fields edited, the variants added). An agent does the
  interpreting: the MCP tool `storyboard_notes` lists the open notes with each shot's current values and image paths
  (`studio storyboard my-site --notes` prints the same for an agent without MCP); it acts with `set_shot_field`,
  `regenerate_shot_image`, `pick_shot_variant` or by editing `site.yaml`, looks at the result, and calls `resolve_note`
  with a short reply. The page refreshes by itself when the spec, a variant or a note changes, wherever the change came
  from, and **Not quite** sends a note back with a follow-up.
- **Edit any field** (under Advanced). Caption, prompt, motion, seconds, seed, trim, strength, a take's keyframe prompts and motion
  segments, an edit's instruction, a product still's scene and view. Save writes the change into `site.yaml` *in
  place*: only the edited text changes, so comments, column alignment, quoting and line endings stay as you wrote them
  (a change a text splice cannot make, such as switching a source, falls back to ruamel's round-trip dump with the
  file's own indentation). The spec is validated first: an invalid value is shown on the card and nothing is written.
  The previous text of every save is kept in `<project>/storyboard/history/` (the last 30; **Undo last save**
  restores it).
- **Regenerate, Re-run, Revert, per image.** *Regenerate* renders one more variant of just that image with a new seed;
  *Re-run* renders it with the same seed after you edited its text; *Revert* goes back to the image that was in use
  before. Only that image's stage runs (a beat's start or end image, an edit, a take keyframe, a product still), through
  the code and cache digests the full build uses, as a background job with its progress on the card. Videos, restores and
  product passes are never started from here. Locked shots refuse, and one job runs per image at a time; jobs share
  ComfyUI with whatever else is queued on it.
- **Variants.** Every render is kept under `<project>/storyboard/variants/<shot>/<image>/` and shown as a strip of
  thumbnails on the card. Click one to make it current: its seed (and text) are written into `site.yaml`, and it is put
  back in the build's cache if that was cleaned, so `studio build` reproduces exactly that image.
- **Shared steps.** A chain of edits (a generated base image, a relight edit, a crop edit per shot) is shown the readable
  way: each card holds only what is its own, with the full chain behind an expander, and the steps several shots share
  are listed once at the top, where one edit reaches every shot that uses them ("Re-run its shots" redraws them).
- **Lock and Approve.** *Lock* sets `locked: true` in the spec. *Approve* is storyboard-only state in
  `<project>/storyboard/state.json`: a badge on the card, listed as "not approved" on the sheet and by
  `studio build --plan`, and read as "changed since approval" once the shot is edited again.
- **Safe beside other editors.** If `site.yaml` changes on disk while the page is open (you, an agent, git), the page
  notices, reloads the values and says which; a save whose fields changed under it is refused instead of overwriting.

- **Play the whole thing.** The **Play** tab plays `animatic.mp4` (every shot at its length, with the page's captions)
  with a timeline of shot markers: click one to jump to that shot; the shot on screen is named and its card is
  highlighted. *Rebuild animatic* cuts it again as a background job from the stills and clips that exist now (it
  renders nothing new: no ComfyUI, no Blender; an image not drawn yet is a placeholder card) and the player says when
  the cut is out of date and which shots changed since. The stand-in page (stills scrolling like the real one) and, once
  `studio build` has run, the real built page play in a frame with an auto-scroll that runs top to bottom (speed, pause,
  scrub; it waits out the page's loader).

Agents drive the same loop through the MCP tools `storyboard_notes`, `resolve_note`, `storyboard_shots`,
`set_shot_field`, `regenerate_shot_image` (returns the new image's path), `pick_shot_variant` and `approve_shot`. *Update sheet* in the page rebuilds `sheet.jpg` and the stand-in
page from the edited spec and what is rendered so far (a sketch-level storyboard: no ComfyUI, images not drawn yet show as
cards); `studio storyboard my-site` does the same at stills or animatic level.

## Launch trailers

`studio trailer my-site` cuts a launch film from what the site already rendered, in 16:9 and 9:16, with no extra
generation: `dist/trailer/trailer-16x9.mp4`, `trailer-9x16.mp4` and a poster beside each (H.264, yuv420p, CRF 18,
faststart; ready for X, TikTok, Reels and Shorts). `trailer: {}` derives the cut: a hook shot, the middle of the
story, the product reveal, feature callouts and an end card, each captioned with the site's own headlines.

```yaml
trailer:
  bpm: 100                       # every cut lands on the beat grid
  music: inputs/track.mp3        # optional, local; trimmed, faded and loudness-normalised (-14 LUFS)
  url: stillwater.example        # end card: name, tagline, call to action, address, disclaimer
  embed: true                    # a "Watch the launch film" button on the opening section
  shots:                         # optional; leave out for the derived cut
    - { section: take, step: 0 }                            # the footage under a step, captioned with it
    - { beat: laugh }                                       # a beat of a story film
    - { card: "One take. <em>No cuts.</em>", beats: 4 }     # type on the theme background
    - { section: order, beats: 6 }                          # any other section, recorded scrolling
    - { product: three-quarter, callouts: [750 ml, 24 h cold] }   # a product still (needs site.product)
```

The 9:16 cut is reframed, never letterboxed: in a take the crop follows the product through the take's own camera
(`take.py --pass track`), cuts the reveal where the product is biggest in frame and pushes in on it as far as the
source resolution allows; other footage follows a saliency-guided crop; recorded sections are recorded at phone size.
Captions, callouts and the end card are set in the theme's own fonts and colours (HTML in headless Chrome, so `<em>`
reads as it does on the site), animate on the beat, and keep inside the TikTok/Reels safe areas. Every stage is
cached, so a re-run costs nothing until something changes; `studio trailer my-site --plan` prints the cut.

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
to create projects, edit specs, build, take snapshots and look at them, record videos and cut launch trailers; the `scroll-site` skill
gives it the workflow. Any MCP client can use `python -m engine.mcp_server`.

## How it's built

- `engine/`: Python. Spec (`spec.py`), scene builders (`scenes/`), compiler and themes (`compile/`), backends for
  ComfyUI, Blender and depth (`backends/`), CLI, server, MCP server, snapshot and record tools.
- `runtime/`: TypeScript. The scroll core (Lenis, sticky stages, step cards, HUDs) plus one lazily loaded player per
  scene type. Built into `engine/compile/static/runtime` and copied into every site.
- `ui/`: React. The Studio app.
- Every model, with its size and licence, is listed in [`engine/models.yaml`](../engine/models.yaml).
