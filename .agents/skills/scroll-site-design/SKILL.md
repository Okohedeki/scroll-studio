---
name: scroll-site-design
description: Design a new Scroll Studio site from a brief, from nothing, instead of adapting an example. Covers finding the story and the one idea, choosing scenes for what each moment must do (with at least one thing the visitor plays with), setting a look with art directions, writing specific copy and picture prompts, and checking the result is not a copy of an example. Use before writing or rewriting any site spec.
---

# Design a site from the brief

The engine can make almost any page; the risk is that every page comes out the same. That happens when an agent opens
the nearest example, keeps its sections and changes the words. Work the other way round: from the subject to the page.

**Examples are a dictionary, not a template.** Look inside `examples/` only to see how a field is written (grep for
`type: diorama` to see a diorama's fields). Never copy an example's section order, copy, prompts, or its pairing of
theme preset and style. Do not run `studio new --example` or `create_project(example=...)` for a new site.

## 1. Find the story (before any YAML)

Write these down for yourself first, in a sentence each:

- **Who** the page is for, and what they already know.
- **The promise:** the one thing the page must prove. Everything else serves it.
- **The image:** a concrete picture or metaphor that belongs to this subject and no other (a mill race feeding a wheel
  for a job queue; a harbour that wakes up for a ferry company; a cell zooming down to its proteins for a biotech lab).
  If the image would fit any company, it is not the image.
- **The arc:** five to nine moments, in order, from the first impression to the call to action. Each moment has one job:
  show, prove, explain, reassure, or ask.
- **What the visitor plays with:** at least one moment where the page answers the visitor (the pointer, live 3D, the
  scroll scrubbing a film). Interactivity is what a scroll site has that a slide deck does not.

## 2. Choose a scene for each moment

Pick by what the moment must do, not by what an example used. Each row is a real scene type (`scroll-scenes` has the
details and costs).

| The moment must... | Scenes that do it |
|---|---|
| open on a feeling, a place, a journey | `film` (generated video scrubbed by scroll; `journey:` makes the whole page one camera take), `parallax` (depth from one picture), `type` (kinetic words) |
| let the visitor explore | `pointer:` on a `parallax`, `film` or `stages` (a torch or a lens that follows the pointer); `diorama` (a miniature world to orbit and dive into); `scene3d` (a zoom through nested live 3D levels) |
| show how something works | `stages` (one subject changing state), `code` (a fly-through of real code), `chart` (figures that draw themselves), `map` (a route on a live map) |
| show change over time | `light` (one place relit from dawn to night), `stages`, `timeline` |
| show a product | `product` or `hero` blocks with generated or product stills, `strip`, `gallery`; with a 3D model: `sequence`, `showroom`, `inside` |
| prove it | `stats` (only real figures), `quote`, `logos`, `features` |
| ask | `cta`, `signup` |

Rules of thumb:

- Open on a scene, never on a plain block. End on a `cta`.
- One hero scene done well beats four half-done. A page of seven scenes is tiring; alternate scenes with blocks.
- Never two blocks of the same type in a row. Use a type at most twice.
- Join the important moments like a film (`transition:` match, carry, iris, whip) rather than a plain scroll, once or
  twice per page, where the two pictures share a shape or a motion.
- Check the machine: `studio doctor`. Films, generated pictures (`generate:`) and `light` (it relights with an image
  editor) need a GPU with ComfyUI. With no GPU, `type`, `scene3d`, `diorama`, `code`, `chart` and `map` still render live
  in the page, `parallax` and `stages` work from the user's own photos, and every block works.

## 3. Set the look

Do not default to the `night` preset with an orange accent; most pages that look alike share that choice.

- **No brand yet:** put the brief in `directions:` and run `studio directions <project>` (MCP: `directions`). It pitches
  several complete art directions (concept, palette, type, a style, an imagery treatment, motion), each a board of stills.
  Look at the board, pick one with `--pick <letter>`. It writes the theme and `imagery:` and never touches the copy.
- **A brand exists:** `studio brand <project> --from <url>` or `--logo inputs/logo.png` (contrast-checked colours).
- **A style** (`theme.style`) changes how the whole page scrolls (split-flap board, comic pages, paper theatre...;
  `docs/styles.md`). Choose it for the brand's character; show two or three with `studio looks <project> --styles a,b`.
- `imagery:` (medium, light, lens, mood, palette) phrases every generated picture and film the same way. It is how a
  page looks like one piece. Set it once instead of styling each prompt.

## 4. Write the copy

- Specific to this subject: name the real thing, how it works, who it is for, with the brief's own facts.
- Headlines of eight words or fewer; wrap the accent phrase in `<em>...</em>`. Short sentences in the body.
- No stock phrases (unlock, seamless, elevate, revolutionize, cutting-edge, game-changer, empower, robust, leverage,
  supercharge, world-class, effortless) and no exclamation marks.
- Numbers only from the brief or plainly countable facts. Never invent customer counts, uptime or awards; never name
  real companies or people as customers or quotes.

## 5. Write the picture prompts

- Describe what is in the picture: subject, setting, composition, light, time of day. Leave the medium, style and lens
  out (photoreal, illustration, 3D render, 50mm): `imagery:` adds those, so every picture matches.
- No text, logos or screens with writing in a picture: generated lettering is garbled. Put words in the copy.
- A film is one continuous place. Each beat continues where the last ended (chain them with
  `image: { beat_frame: { beat: <id>, at: last } }`); a cut to an unrelated scene shows as a jump.
- Leave room for the words: say where the subject sits ("the wheel on the right third, open sky on the left").

## 6. Check it is new

Before building, compare the spec with the examples:

- Is the section order the same as any example's? Is the opening scene the same type and composition?
- Is the theme preset and style pairing the same as an example's?
- Does any sentence or prompt come from an example?

If yes to any, go back to step 1. Then validate the fields (`studio build <project> --plan` names every section it
cannot plan, with the reason) and continue with `scroll-site-build`.
