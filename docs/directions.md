# Directions: the next level of landing pages

DesignAI is a design studio for landing pages. These are the directions it grows in next, chosen for what the
engine does well (generated worlds and camera moves, depth and masks, type, real products, browser-side mechanics) and
away from what it does badly (people acting, choreography, consistent characters). Each one is an engine feature: a
spec field, a cached builder, a runtime player where needed, CLI and MCP, docs and a showcase spec.

## 1.5 · Make it yours (building)

One layout system for every scene: where things go (`at`), when they show (`show`, `enter`, `exit`), any block
as a step, theme tokens for space, type, shade and motion, style options, your own CSS, blocks and styles, phone
rules, placement measured from the picture, and `studio layout` to check it. Design:
[design/1.5-make-it-yours.md](design/1.5-make-it-yours.md).

## Wave 1

- [x] **Direction boards** (`studio directions`): one brief in, six complete art directions out, side by side as
  storyboards (palette, type, imagery, motion, style). Pick one and it becomes the spec. How a studio pitches.
- [x] **Type in the world**: headlines placed inside the scene, painted on a wall, written in the sky, set behind a
  building so the camera passes them and things pass in front (depth-aware, tracked to surfaces).
- [x] **Edited like a film**: sections join with film grammar instead of fades: match cuts (a round logo becomes the
  sun becomes a cup), whip pans, type carried from one section into the next, hard cuts on the beat.
- [x] **Styles 28-29**: `stop-motion` and `paper-cut-out` (see `docs/styles/todo.md`).

## Wave 2

- [x] **The one-take page** (`journey:`, `studio journey`, example `examples/fenmoor`): the whole page is one camera journey through one generated world; each section is a place
  in it (hero at the door, features as rooms, pricing at the window, the CTA at the view).
- [x] **Cinemagraph pages**: stills where only one thing moves (steam, a curtain, light on water); a mask picks what
  moves and the rest is held perfectly still.
- [x] **Light as the scroll** (`type: light`, `studio light`): one world from dawn to night; each section is a time of day, the same place relit.
- [x] **The product as the set** (`type: inside`): fly into the product (inside a speaker, between the layers of a board, macro around a
  bottle); each feature is a stop inside it.
- [x] **Miniature worlds** (`diorama`, [docs/miniature.md](miniature.md)): a tilt-shift diorama you orbit and dive into; sections are places on it.
- [x] **Styles 30-33**: `paint-on-glass`, `multiplane`, `scratch-film`, `smears`.
