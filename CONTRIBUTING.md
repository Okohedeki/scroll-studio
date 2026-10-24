# Contributing to Scroll Studio

Thank you for helping. Scroll Studio is an open-source **engine**: a `site.yaml` spec goes in and a finished static
site comes out, made with open models on the contributor's own GPU. This guide says how to contribute and the rules
every change keeps, so the engine stays consistent as more people work on it.

- [Before you start](#before-you-start)
- [No bounties](#no-bounties)
- [Ground rules](#ground-rules)
- [Rules per area: core, standard and trivial](#rules-per-area)
- [Set up](#set-up)
- [Making a change](#making-a-change)
- [What a complete feature includes](#what-a-complete-feature-includes)
- [Consistency rules: themes, styles, blocks and scenes](#consistency-rules)
- [The checks](#the-checks)
- [Pull requests](#pull-requests)
- [Licence and the CLA](#licence-and-the-cla)
- [Reporting bugs and security issues](#reporting-bugs-and-security-issues)

## Before you start

**Every pull request starts with an issue**, for everyone, maintainers included. A check on every pull request fails
until it links an issue that a maintainer has accepted, so nobody spends time on work that won't be merged:

1. **Find or open the issue.** Search the [issues](https://github.com/Okohedeki/scroll-studio/issues) and the
   [milestones](https://github.com/Okohedeki/scroll-studio/milestones) first. Questions belong in
   [Discussions](https://github.com/Okohedeki/scroll-studio/discussions) ([SUPPORT.md](SUPPORT.md)).
2. **Wait for `status: accepted`.** A maintainer triages new issues within a few days
   ([docs/maintainers/triage.md](docs/maintainers/triage.md)). Small fixes (a typo, a broken link, a clear bug) are
   accepted quickly.
3. **Core changes need the design agreed first** (`status: design-approved`): a design section in the issue, or an
   [RFC](docs/rfcs/README.md) for anything large. See [rules per area](#rules-per-area).
4. **Say you're working on it** in a comment, so two people don't build the same thing.

The current plan is in [docs/design/](docs/design/) and [docs/directions.md](docs/directions.md); how decisions are
made is in [GOVERNANCE.md](GOVERNANCE.md). Be kind and specific: the [code of conduct](CODE_OF_CONDUCT.md) applies
everywhere in the project.

<a id="no-bounties"></a>
### No bounties

Scroll Studio does not pay for contributions. There are no bounties, tips or payments for issues, pull requests,
reviews, translations or security reports, and nobody is authorised to promise any on the project's behalf. Pull
requests or issues that ask for payment (including wallet addresses or payment details) are closed. Contributors are
credited by name in the release notes, and security reporters in the advisory.

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
6. **Nothing from one machine.** No committed file carries a drive-letter path, a home folder, a username or someone's
   folder layout. Examples use placeholders (`/path/to/models`); a machine is configured in `studio.toml` (not
   committed) or environment variables. `tests/test_no_local_paths.py` checks every tracked file.
7. **Accessible by default.** Real HTML text in reading order, one `<h1>` per page, WCAG AA contrast, reduced-motion
   fallbacks, no flashing above three times a second.

<a id="rules-per-area"></a>
## Rules per area: core, standard and trivial

Not every file carries the same risk. The runtime ships inside every site anyone has ever built with Scroll Studio; a
change to it reaches all of their visitors. A typo in a guide reaches nobody. So the rules depend on what a pull request
touches. The labeler marks pull requests that touch a core path `tier: core`, and the `pr-policy` check holds them to
the core rules.

### Core

| Area | Paths | Why it is core |
|---|---|---|
| Runtime | `runtime/` (except `runtime/src/styles/`), `engine/compile/static/runtime/` | Ships in every built site |
| Spec | `engine/spec.py` | The public `site.yaml` contract; the UI and MCP tools are generated from it |
| Compiler and themes | `engine/compile/` (templates, theme derivation, page assembly), `engine/themes.yaml` | Decides what every page is made of |
| Style contract | `engine/styles/README.md` | Every style is written against it |
| Commands | `engine/cli.py`, `engine/mcp_server.py` | Public surface: scripts and AI clients depend on it |
| What runs on the builder's machine | `engine/backends/`, `engine/models.yaml`, `engine/server/`, `engine/serve.py` | Downloads, model loading and local servers ([threat model](docs/security/threat-model.md)) |
| Project infrastructure | `.github/`, `pyproject.toml`, `package.json`, `package-lock.json` | CI, security and releases |
| Licence | `LICENSE`, `NOTICE.md`, `CLA.md`, `AGENTS.md`, the runtime notice comment | Legal terms |

A core pull request needs **all** of:

1. **A design-approved issue** (`status: design-approved`): the design written down and accepted before the code
   (a design section in the issue, or an [RFC](docs/rfcs/README.md)). A pull request that arrives first is labelled
   `needs-issue` and waits; it is not reviewed as code until the design is agreed.
2. **A code owner's approval** ([CODEOWNERS](.github/CODEOWNERS), [MAINTAINERS.md](MAINTAINERS.md)).
3. **The area's extra checks**, all green:

   | Area | Extra checks |
   |---|---|
   | Runtime | The bundle rebuilt and committed (CI rebuilds it and fails on any difference); the runtime type check; the browser rendering tests for every style and preset; the size budgets; a before-and-after recording for anything visible, on desktop and on a phone, with and without reduced motion |
   | Spec | Every field has a person-readable `description`; the schema snapshot updated; the generated reference and the guides updated; old specs still validate |
   | Compiler and themes | Layout snapshots unchanged (or re-recorded and every change explained); conformance tests; the rendering tests |
   | Commands | CLI and MCP snapshots updated; docs updated |
   | Models, servers and downloads | The [threat model](docs/security/threat-model.md) updated if anything it describes changes; checksums for new downloads; servers stay on `127.0.0.1` |
   | Project infrastructure | Workflows pass zizmor and actionlint; actions pinned to commit SHAs; least-privilege permissions; [repo settings](docs/maintainers/repo-settings.md) updated |

4. **Compatibility**: if anything an existing spec, built site, command or tool does would change, the pull request is
   labelled `breaking-change` and follows the [compatibility and deprecation policy](docs/compatibility.md):
   deprecate with a warning first, and write a migration note in the changelog fragment.

A small, contained fix in a core area (a crash, a wrong value) still follows these rules, but its design can be a few
lines in the issue: what is wrong, what the fix changes, and how it is tested.

### Standard

Scene builders and planners (`engine/scenes/`, `engine/*.py` outside the core paths), styles (`engine/styles/<name>/`,
`runtime/src/styles/`, `docs/styles/`), examples, tests and docs. A standard pull request needs an issue labelled
`status: accepted`, the tests and docs for the change, and green checks. New styles also follow the
[consistency rules](#consistency-rules).

### Trivial

Typos, broken links, wording. Still linked to an issue (it keeps the history findable); a maintainer accepts these the
same day.

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
5. For anything a user would notice, add a changelog fragment: a file `changes/<issue>.<kind>.md` holding a sentence
   or two written for users ([changes/README.md](changes/README.md)). Don't edit CHANGELOG.md; fragments are
   assembled into it at release time, so pull requests never conflict over it.
6. Open a pull request against `main` with a [conventional title](#pull-requests), link the issue, and fill in the
   template.

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

Every pull request runs these without a GPU, and `main` only accepts changes that pass the required ones
([repository settings](docs/maintainers/repo-settings.md)):

- **Lint** (`lint` job): `ruff check .` (syntax errors, undefined names, unused imports, redefinitions and unused
  variables) and the repository hygiene tests (`tests/test_repo_hygiene.py`: no file over 10 MB, media only in
  `examples/*/inputs`, `examples/*/proof`, `examples/showcase`, `docs/media` and the built runtime, no `.env`, keys,
  `studio.toml` or `settings.local.json`). `pre-commit install` runs the same checks on each commit.
- **The whole suite** (`tests` job), `python -m pytest -q`: spec validation, planners, builders with stand-ins, the
  compiler, with coverage. CI fails when the total or an area in `tests/coverage_floors.json` drops below its floor;
  new code needs tests, and when a change lifts an area by 2 points or more, raise its floor in the same pull request.
  Floors only go up.
- **Platforms** (`platforms` job): the suite on Python 3.10 and 3.13, Windows and macOS.
- **Install** (`install` job): the wheel and sdist are built, installed in a clean environment, and every example
  compiles from the installed package. A new kind of data file under `engine/` must be listed in
  `[tool.setuptools.package-data]` (`tests/test_packaging.py` fails otherwise).
- **Runtime** (`runtime` job): `npm run build:runtime` must reproduce the committed `engine/compile/static/runtime/`
  exactly, so a change to `runtime/src` commits its rebuilt bundle. The runtime and the UI are type-checked.
- **Runtime unit tests** (`runtime` job), `npm run test:runtime`: Vitest in jsdom, with a v8 coverage report and floors
  (`runtime/vitest.config.ts`). They cover the runtime's scroll maths, easing, caption and window timing, frame selection,
  the players that need no GPU and the style toolkit. A change to `runtime/src` comes with tests; when it lifts a number
  by 2 points or more, raise its floor in the same pull request.
- **Size budgets** (`tests/test_performance_budgets.py`, part of the suite): the runtime entry, `studio.css`, each chunk and
  the whole runtime folder, and the weight of the page the compiler emits for each example, may not grow past
  `tests/performance_budgets.json` (each is the size when set plus about 10%). If a change makes something heavier on
  purpose, raise it and say why in the pull request:

  ```bash
  UPDATE_PERFORMANCE_BUDGETS=1 python -m pytest tests/test_performance_budgets.py
  ```
- **Conformance** (`tests/test_conformance.py`): every preset and style against the rules above.
- **Layout snapshots** (`tests/test_layout_snapshots.py`): what every example compiles to (sections, captions, windows,
  block classes). If your change moves something **on purpose**, re-record and commit the snapshots, and say why in the
  pull request; the diff is reviewed like code:

  ```bash
  UPDATE_LAYOUT_SNAPSHOTS=1 python -m pytest tests/test_layout_snapshots.py
  ```

- **Public surface** (`tests/test_public_surface.py`): the `site.yaml` schema, the CLI and the MCP tools. Re-record a
  deliberate change with `UPDATE_SURFACE_SNAPSHOTS=1`; anything removed is a breaking change
  ([compatibility](docs/compatibility.md)).
- **Old specs** (`tests/test_old_specs.py`): every example spec from every release still validates and compiles.
- **Policy, security and licences**: `pr-policy` (title, linked issue, changelog fragment), the CLA, and the security
  checks (dependency vulnerabilities and licences, secrets, workflow linting, CodeQL).

## Pull requests

- **Link the issue** in the description (`Closes #123`). The `pr-policy` check fails until the linked issue is
  accepted (design-approved for core changes); it re-runs when the pull request is edited.
- **Title it** in the [Conventional Commits](https://www.conventionalcommits.org) form, because the project merges with
  squash and the title becomes the commit on `main`: `type(area): what changed`, in the present tense, lower case
  after the colon.
  - Types: `feat` (a new capability), `fix` (a bug), `perf`, `docs`, `test`, `refactor`, `style` (a Scroll Studio
    style, not code formatting), `build`, `ci`, `chore`, `revert`.
  - Area (optional): `runtime`, `spec`, `compiler`, `scenes`, `styles`, `themes`, `models`, `cli`, `mcp`, `ui`,
    `docs`, `examples`, `tests`, `ci`.
  - A `!` after the type marks a breaking change: `feat(spec)!: ...`.
  - Example: `fix(runtime): end reveals on transform none, not the stylesheet's offset`.
- **A changelog fragment** for `feat`, `fix` and `perf` pull requests, unless a maintainer labels it `skip-changelog`.
- **Keep it focused**: one feature or fix per pull request, ideally under 400 lines changed (the labeler adds a
  `size:` label; split anything `size: xl`).
- **Fill in the template**: what changed and why, and pictures or a recording for anything visual.
- **The checks must pass.** Changes go into `main` only through pull requests, for everyone, maintainers included;
  nobody can force-push or delete `main`. The required checks are listed in
  [docs/maintainers/repo-settings.md](docs/maintainers/repo-settings.md).
- **Review.** Expect a first response within 3 days and a review within 7 of the checks passing. Expect questions about
  the ground rules, the rules for the area, and the consistency rules. Allow maintainers to edit your branch, so small
  fixes don't need a round trip.

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
