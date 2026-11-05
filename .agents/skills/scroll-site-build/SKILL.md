---
name: scroll-site-build
description: Take a designed Scroll Studio spec to a finished site - storyboard every shot before rendering, edit shots in place, build in draft then full, check snapshots and the film and page reports, fix, and hand over. Use after the spec is designed (scroll-site-design), whenever building, rebuilding, reviewing or fixing a Scroll Studio site.
---

# Storyboard, build, look, fix

Every command below has an MCP tool of the same name (`storyboard`, `build`, `snapshot`, `inspect_film`, `record`...),
and long jobs return a job id to pass to `wait_for_job`.

## 1. Storyboard before rendering

A film costs an hour or more; a storyboard costs seconds to minutes, and its frames are the real first frames (the
same stages and caches as the build), so approving them is never wasted work.

1. `studio storyboard <project> --level sketch` for layout and pacing with no GPU, then `studio storyboard <project>`
   for stills. Read `storyboard/sheet.jpg`: does each shot open (and end) on the right frame, is the subject placed where
   the words leave room, is anything a placeholder? The summary lists every card and the full render estimate.
2. Fix and storyboard again; only changed shots are redone (`--only <ids>`). `--level animatic` checks pacing and motion.
3. Edit shots in place instead of rewriting the spec: `storyboard_shots` lists every shot's fields and images,
   `set_shot_field` changes one field (comments kept, validated), `regenerate_shot_image` re-renders one image with a new
   seed (read it, then keep it or `pick_shot_variant` an earlier one). People can do the same in the browser with
   `studio storyboard <project> --edit`, and leave notes: `storyboard_notes` lists them, `resolve_note` answers each.
4. Lock what is approved (`locked: true`, or `approve_shot`): later edits never re-render it.
5. `studio build <project> --plan` says what will render and how long. Tell the user before a long render.

## 2. Build

- `studio build <project> --draft` (or `--only <ids>`) for fast low-quality renders; read the log on failure: it names
  the stage and the cause.
- The full `studio build <project>` when the draft looks right. `--profile` shows where the time went.
- Close games and other GPU apps before a film render; a local text model and ComfyUI share the GPU.

## 3. Look

Judge the images, never the log.

- `studio snapshot <project>` and read `snapshots/sheet.jpg`: text legible over every picture, the subject framed and
  not under the copy, nothing cut off, colours on brand, every stage of every scene actually visible.
- `studio inspect <project> --page` checks the built page at desktop and phone size (text over pictures, type, layout)
  and names the spec fix for each finding.
- After a film: `studio inspect <project>` scores it second by second for pops, softness, halos, style drift and
  morphs; read the worst-moment pictures in `.build/inspect/` and fix what it names.
- Transitions: `studio cuts <project> --strip` writes frame strips around each cut.
- Interactivity: open the page (`studio preview <project>`) and use it. Move the pointer over pointer scenes, orbit the
  3D, scroll back and forth through films, try a phone width and reduced motion.

Fix the spec (or the engine, when it is an engine limit: `scroll-engine-dev`) and repeat.

## 4. Share and hand over

- `studio record <project>` makes an MP4 scroll-through; `trailer: {}` in the spec and `studio trailer <project>` cut
  launch films (16:9 and 9:16) from the site's own renders.
- `studio publish <project> [<project>...]` gathers built projects into one static folder (`out/`) for any host.
- Client copy rounds: `studio copy export <project>`, edit `copy.md`, `studio copy import <project> copy.md`, build.
- Tell the user where the site is (`dist/index.html`, `studio preview <project>`), what each section shows, and what
  you could not do and why (no GPU, ComfyUI not running, a section left out).
