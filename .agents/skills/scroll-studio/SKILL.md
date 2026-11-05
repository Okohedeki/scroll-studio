---
name: scroll-studio
description: Start here for any work with Scroll Studio, the engine that builds scroll-driven websites and commerce creative from a spec. Covers what the engine is, the rules every agent follows (design each site new, never copy an example, never hand-write HTML, fix the engine instead of working around it) and which skill to read next. Use when asked to make a scroll site, landing page, product page, scroll animation, interactive page, product stills, ads, or to change the engine itself.
---

# Scroll Studio

Scroll Studio is an engine. A project file goes in (`project.yaml`, or the older `site.yaml`); the engine renders every
picture, film and 3D scene, and compiles a static site into `dist/`. Each section of a page is either a **scene** the
visitor scrolls through (a film, a live 3D world, a photo lit by the pointer, a fly-through of code, a place relit from
dawn to night) or a **block** (features, stats, a quote, a call to action).

You drive it through the `studio` CLI or the `scroll-studio` MCP server (the same operations under both).

## The rules

1. **Design every site new.** The examples in `examples/` show what the engine can do and what each field looks like.
   They are not templates. Never start a new site by copying one (`studio new --example`, `create_project(example=...)`)
   and swapping the words. A site copied from an example looks like that example, and the point of the engine is that
   every site looks like its own subject. Read `scroll-site-design` before writing any spec.
2. **Everything goes through the engine.** Never hand-write HTML, CSS or a one-off script for one page. If a site needs
   something the engine cannot do, add it to the engine (a spec field, a builder stage, a runtime player) so every site
   can use it. Read `scroll-engine-dev`.
3. **Look at the result.** Judge a page by its storyboard sheet, snapshots and recordings, not by the build log. A build
   that succeeds can still be ugly, unreadable or broken on a phone.
4. **Storyboard before rendering.** Films and generated images cost minutes to hours of GPU time. The storyboard shows
   every shot's real first frame in seconds.
5. **Local first.** Every build works with local models and no API keys. Provider APIs are optional and run only when a
   project's `models:` asks for them and their key is set. Never turn on a paid provider without the user's say-so.

## Which skill next

| You are asked to... | Read |
|---|---|
| make a new site or landing page, or redesign one | `scroll-site-design`, then `scroll-site-build` |
| choose or configure a scene (film, 3D, pointer, code, light ...) | `scroll-scenes` |
| storyboard, build, check, fix and hand over a site | `scroll-site-build` |
| make product stills, ads, listing copy, a product video or product pages | `scroll-commerce` |
| add a capability the engine lacks, or fix the engine | `scroll-engine-dev` |

## Where things are

- Spec models (the source of truth for every field): `engine/spec.py` (site) and `engine/project_spec.py` (project).
  Print a schema with `studio schema` (or `studio schema --project`), or the MCP tool `spec_schema('<type>')`.
- Scene guide with worked examples: `docs/scenes.md`. Styles (how a whole site scrolls): `docs/styles.md`.
  The project file: `docs/project-file.md`. Commerce outputs: `docs/stills.md`.
- `studio doctor` says what this machine can render (no GPU, a GPU without ComfyUI, the full stack).

## Licence

Scroll Studio is AGPL-3.0 with additional terms. Sites a user builds with it are theirs (the Output Exception in
NOTICE.md). Code, templates or research reused elsewhere stay AGPL and keep the attribution notice: see `AGENTS.md`.
