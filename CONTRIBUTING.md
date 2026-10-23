# Contributing to Scroll Studio

Thank you for helping. Scroll Studio is an open-source **engine**: a `site.yaml` spec goes in and a finished static
site comes out, made with open models on the contributor's own GPU. This guide says how to contribute and the rules
every change keeps, so the engine stays consistent as more people work on it.

- [Before you start](#before-you-start)
- [Ground rules](#ground-rules)
- [Set up](#set-up)
- [Making a change](#making-a-change)
- [What a complete feature includes](#what-a-complete-feature-includes)
- [Consistency rules: themes, styles, blocks and scenes](#consistency-rules)
- [The checks](#the-checks)
- [Pull requests](#pull-requests)
- [Licence and the CLA](#licence-and-the-cla)
- [Reporting bugs and security issues](#reporting-bugs-and-security-issues)

## Before you start

- **Small fixes** (a typo, a broken link, a clear bug with an obvious fix): open a pull request directly.
- **Anything bigger** (a new scene type, a new style, a new spec field, a change to how layouts or themes work): open
  an issue first, or comment on the one in the [milestones](https://github.com/Okohedeki/scroll-studio/milestones),
  and agree the design before writing code. The current plan is in [docs/design/](docs/design/) and
  [docs/directions.md](docs/directions.md).
- Be kind and specific. The [code of conduct](CODE_OF_CONDUCT.md) applies everywhere in the project.

## Ground rules

These are what make Scroll Studio what it is. A change that breaks one is not merged, however good it is otherwise.

1. **Engine features, never one-off pages.** If a site needs something the engine can't do, add it to the engine (a
   spec field, a builder stage, a runtime player or preset) so every site can use it. No hand-written pages, no
   scripts tied to one image or one shot, nothing hard-coded for one example.
2. **Local models only, no API keys.** Every model runs on the user's machine (ComfyUI, Blender, local weights). A
   feature that needs a hosted API or a key will not be merged.
3. **The spec is the source of truth.** `engine/spec.py` (Pydantic) defines `site.yaml`, and the Studio UI forms and the
   MCP tools are generated from it. Every field has a `description` written for a person.
4. **Old sites keep building the same page.** A change may add, never silently change, what an existing spec produces.
   The layout snapshots of every example (below) are the proof.
5. **Declare every dependency up front**, in `pyproject.toml` (an extra for heavy or optional ones),
   `runtime/package.json` or `engine/models.yaml`, and in [docs/INSTALL.md](docs/INSTALL.md).
6. **Accessible by default.** Real HTML text in reading order, one `<h1>` per page, WCAG AA contrast, reduced-motion
   fallbacks, no flashing above three times a second.

## Set up

```bash
git clone https://github.com/<you>/scroll-studio && cd scroll-studio
pip install -e ".[dev]"            # add extras you need: .[ml,mesh,cad,...] (see pyproject.toml)
npm ci                             # the runtime and the Studio UI
python -m pytest -q                # the whole suite, no GPU needed (about 5 minutes)
studio doctor                      # what your machine can build
```

GPU stages need ComfyUI, Blender and the models: [docs/INSTALL.md](docs/INSTALL.md). You do not need them to work on
the spec, the compiler, the runtime, styles or docs.

How the code is laid out: [CLAUDE.md](CLAUDE.md) (it is written for AI assistants but is the best map of the repo) and
[docs/ENGINE.md](docs/ENGINE.md).

## Making a change

1. Fork, then branch from `main`: `fix/<what>`, `feat/<what>`, `style/<name>` or `docs/<what>`.
2. Write the change with its tests and docs (see the next section).
3. If you changed `runtime/src`, rebuild the bundle that ships in the engine: `npm run build:runtime`, and commit
   `engine/compile/static/runtime/`. If you changed the UI: `npm run build:ui`.
4. Run `python -m pytest -q`. For anything visual, build an example and look at it: `studio build examples/<name>` and
   `studio snapshot` (judge the images, not the logs).
5. Add a line under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md) for anything a user would notice.
6. Open a pull request against `main` and fill in the template.

**Code style.** Match the code around you: its naming, its density and its comments. Docstrings and comments say
*why*, briefly. Python 3.10+, type hints on public functions. Text files use LF line endings. User-facing words (docs,
errors, descriptions) are plain and specific: say what happened and what to do about it.

**Commits.** One logical change per commit, a short summary line in the imperative or as a statement of what changed,
and a body when the why is not obvious.

## What a complete feature includes

A feature is done when every layer that should know about it does:

| Layer | Where |
|---|---|
| Spec field(s) with descriptions and validation | `engine/spec.py` |
| Builder stage, cached by its inputs | `engine/scenes/<type>.py`, `engine/*.py` |
| Runtime player or behaviour, and the rebuilt bundle | `runtime/src/`, `engine/compile/static/runtime/` |
| CLI command or option | `engine/cli.py` |
| MCP tool, when Claude should be able to drive it | `engine/mcp_server.py` |
| Tests (no GPU: replace renders with stand-ins) | `tests/test_<feature>.py` |
| Docs | `docs/scenes.md`, `docs/guide.md`, `docs/styles.md` as fits |
| An example or a showcase spec that uses it | `examples/<name>/site.yaml` |
| Changelog line | `CHANGELOG.md` |

<a id="consistency-rules"></a>
## Consistency rules: themes, styles, blocks and scenes

These are checked by `tests/test_conformance.py` on every pull request, so a change that breaks one fails with a
message naming the file and the rule.

### Theme presets (`engine/themes.yaml`)

- Every preset sets `mode`, the colours `bg, bg2, ink, accent, accent2, accent_ink` (`#rrggbb`), and the fonts
  `display, body, mono` (Google Fonts families). Nothing else but the known keys (`display_weight, em_italic, radius,
  display_em, labels, display_optical_size`).
- `mode` matches the colours: `dark` means the background is darker than the ink.
- Contrast: ink on `bg` at least **7:1**, ink on `bg2` at least 4.5:1, button text (`accent_ink` on `accent`) at least
  **4.5:1**.
- Secondary text tiers, accent text and section surfaces are derived by `engine/compile/themes.py` and checked for
  contrast there: change the derivation, not the output.

### Styles (`theme.style`, `engine/styles/<name>/`)

A style is an **experience**: its own scroll mechanic, layout, transitions and pointer behaviour. A style that shares
those with an existing one is a reskin and is not merged. The full contract is
[engine/styles/README.md](engine/styles/README.md); in short:

- **A complete folder:** `style.yaml` (label, about, mode, colours, fonts, `font_axes`, radius, optional `cuts`),
  `style.css`, `blocks.html.j2` (declaring the block types it renders), optional `chrome.html.j2`, and its runtime
  `runtime/src/styles/<name>.ts`. The folder name is lowercase words joined by hyphens.
- **Tokens, checked like a preset's:** the same colour roles, mode and contrast rules; `font_axes` only for fonts it uses.
- **Its own markup and motion:** templates render only real block types and never use the default motion
  (`ss-reveal`, `data-count`). Class names use the style's own prefix (`bh-` for bauhaus) so they never collide with
  the engine's `ss-` classes.
- **Works with any spec:** every style must render a page holding every block type, with exactly one `<h1>` and all the
  spec's words as real text. Content, order and counts come from the spec; nothing is hard-coded for a demo.
- **Researched and listed:** a research brief in [docs/styles/](docs/styles/) (origin, layout, scroll and pointer
  behaviour, components, type, implementation, anti-patterns, reduced-motion fallback), the name in the `Theme.style`
  description in `engine/spec.py` (the UI and MCP read it), an entry in [docs/styles.md](docs/styles.md), and the style
  count in the README kept true.
- **Phones and motion:** works at 390 px wide; recognisable with reduced motion; animate `transform` and `opacity`;
  pause loops off screen.

### Blocks and templates (`engine/compile/templates/`)

- A new block type is a model in `engine/spec.py` (subclass `BlockBase`), markup in `blocks.html.j2`, CSS in
  `runtime/src/styles.css`, and a decision for every style: styled by the default markup, or given its own.
- Templates take every value from the spec and the theme tokens (`var(--ink)`, `var(--accent)` ...), never a
  hard-coded colour, size or string.

### Scenes and layout

- Where words go and when they show belongs to the layout model, not to one scene: in 1.5 every scene uses the same
  `at`, `show`, `enter` and `exit` ([docs/design/1.5-make-it-yours.md](docs/design/1.5-make-it-yours.md)). Do not add a
  scene-specific placement field.
- Builders cache every stage by its inputs, so changing one field re-renders only what depends on it.
- A scene that renders must also have a storyboard path (`studio storyboard`) and a reduced-motion fallback.

## The checks

Every pull request runs the [tests workflow](.github/workflows/tests.yml) on Linux without a GPU, and `main` only
accepts changes that pass it:

- **The whole suite**, `python -m pytest -q`: spec validation, planners, builders with stand-ins, the compiler.
- **Conformance** (`tests/test_conformance.py`): every preset and style against the rules above.
- **Layout snapshots** (`tests/test_layout_snapshots.py`): what every example compiles to (sections, captions, windows,
  block classes). If your change moves something **on purpose**, re-record and commit the snapshots, and say why in the
  pull request; the diff is reviewed like code:

  ```bash
  UPDATE_LAYOUT_SNAPSHOTS=1 python -m pytest tests/test_layout_snapshots.py
  ```

## Pull requests

- Fill in the template: what changed, why, how you checked it (and pictures for anything visual).
- Keep it focused: one feature or fix per pull request.
- The `tests` check must pass. Changes go into `main` only through pull requests, for everyone, maintainers included;
  nobody can force-push or delete `main`.
- The maintainer reviews and merges. Expect questions about the ground rules and the consistency rules above.

## Licence and the CLA

Scroll Studio is licensed under the **GNU AGPL-3.0 with additional terms** ([LICENSE](LICENSE),
[NOTICE.md](NOTICE.md)). Never remove or alter `LICENSE`, `NOTICE.md`, `AGENTS.md` or the notice comment at the top of
the runtime files.

Before your first pull request can be merged, you sign the [Contributor Licence Agreement](CLA.md): a bot comments on
your pull request and you reply with the sentence it gives. You keep the copyright in your work; the CLA lets the
project be published under the AGPL and also offered in other forms, such as a hosted service. You sign once.

Contributions that include someone else's work (a library, an image, a model, text) must say so in the pull request,
with its source and licence, and the licence must be compatible with the AGPL-3.0. Model weights keep their own
licences; record them in `engine/models.yaml`.

AI assistants contributing on someone's behalf follow [AGENTS.md](AGENTS.md); the person submitting is responsible
for the contribution and signs the CLA.

## Reporting bugs and security issues

- **Bugs and ideas:** [open an issue](https://github.com/Okohedeki/scroll-studio/issues/new/choose) with the template.
- **Security problems:** do not open a public issue; follow [SECURITY.md](SECURITY.md).
