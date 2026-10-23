# Threat model

What Scroll Studio trusts, what it does not, and how each risk is handled. Keep this page current: a pull request that
adds a new input, download, server or external tool updates it. Report problems privately
([SECURITY.md](https://github.com/Okohedeki/scroll-studio/blob/main/SECURITY.md)).

## What Scroll Studio is

A local tool. A person runs the engine on their own machine; it reads a project folder (`site.yaml` and inputs),
drives local models (ComfyUI, Blender, Hugging Face weights), and writes a static site to `dist/`. That site is then
published anywhere and opened by strangers. There is no hosted service in this repository and no account system.

So there are two kinds of people to protect:

- **The builder**: the person running the engine. They may open a project, example or template written by someone
  else, or install models and nodes from the internet.
- **The visitor**: anyone who opens a built site. They trust nothing about the builder's machine and should get a
  static page that cannot do more than any other web page.

## Trust boundaries

| Input | Trusted? | Why |
|---|---|---|
| The engine's own code, templates and runtime | Yes | Reviewed and released from this repository |
| A `site.yaml` and its inputs | **No** | Projects and templates get shared; treat them like a document from the internet |
| Model weights and ComfyUI custom nodes | **Partly** | Downloaded from named sources in `engine/models.yaml`; must be verified |
| Blender and ComfyUI themselves | Yes | Installed by the builder; the engine sends them data, not code from specs |
| Requests to the local servers | **No** | Any web page the builder visits can send requests to `127.0.0.1` |
| The built site's visitors | **No** | Public |

## Risks and defences

### A spec reads or writes files outside its project

A hostile `site.yaml` names `../../.ssh/id_rsa` as an input, or an output path outside the project.

- **Defence:** project paths resolve through `Project.path()`, which refuses anything outside the project folder after
  resolving `..` and links. Specs are validated by Pydantic before anything runs.
- **Gap:** every path a spec can name must go through that check; an audit and hostile-spec tests are tracked in
  [#54](https://github.com/Okohedeki/scroll-studio/issues/54).

### A spec runs code

- **Defence:** YAML is always loaded with safe loaders (`yaml.safe_load`, ruamel's safe/round-trip mode), so no
  Python objects are created from a spec. Specs never contain Python, shell commands or Blender scripts: the engine
  writes the Blender and ComfyUI inputs from validated values.
- **Rule for contributors:** no spec field may be passed to a shell, `eval`, a Blender script as code, or a template as
  a template.

### A spec's text attacks the built page's visitors (XSS)

A caption carries `<script>` or a `javascript:` link, and every visitor of the built site runs it.

- **Defence:** the compiler's Jinja environment autoescapes HTML templates. Markdown fields are rendered by the engine
  and must not allow raw HTML or `javascript:` URLs.
- **Gap:** hostile-text tests for every block type are part of [#54](https://github.com/Okohedeki/scroll-studio/issues/54).

### Model weights run code when loaded

Pickle-based weights (`.pt`, `.pth`, `.ckpt`) can run arbitrary code when loaded, and a compromised download source can
serve a hostile file.

- **Defence:** most models are `.safetensors`, which hold data only. Downloads come from the sources named in
  `engine/models.yaml`.
- **Gap:** checksums for every file, refusing mismatches, and `weights_only=True` wherever torch files are loaded:
  [#53](https://github.com/Okohedeki/scroll-studio/issues/53).

### ComfyUI custom nodes

`studio setup-comfy` installs the engine's own nodes (from this repository) into ComfyUI. Third-party custom nodes run
with full access to the builder's machine.

- **Defence:** the engine only installs its own nodes. `docs/INSTALL.md` names each third-party node it needs, from
  its source.
- **Rule:** a feature that needs a new third-party node names it, its source and its licence in the pull request; it
  is reviewed as a dependency.

### Local servers are reached by other web pages

`studio ui` (the Studio app), `studio preview` and the storyboard and direction editors run local HTTP servers. Any
page open in the builder's browser can send requests to `127.0.0.1`, and DNS rebinding can make a remote site look
local.

- **Defence:** every server binds to `127.0.0.1` only, never to the network. Files are served only from inside the
  project (`Project.path()`, the `dist/` check in the preview route).
- **Gap:** checking the `Host` and `Origin` headers on every request, so other sites can neither read nor change
  projects: [#55](https://github.com/Okohedeki/scroll-studio/issues/55).

### The MCP server

The MCP server runs over stdio for a local AI client and can create projects, edit specs and start builds.

- **Defence:** it finds projects only in the configured projects folder, the examples and the folder it was started
  in, and writes only to projects. It has the same powers as the CLI, no more.
- **Rule:** new MCP tools must not take arbitrary paths, shell commands or URLs to fetch.

### The built site's runtime

The runtime in `engine/compile/static/runtime/` ships in every built site.

- **Defence:** it is built from `runtime/src` in this repository and checked into the engine; CI rebuilds it and fails
  if the committed bundle differs. It makes no network requests except to load the site's own files, the fonts the
  theme names (Google Fonts) and any map tiles a spec points at. No analytics, no cookies, no third-party scripts.
- **Rule:** a runtime change that adds a network request, storage or a new third-party library is a core change and
  needs a design-approved issue.

### Supply chain

- **Dependencies:** Python and npm packages are declared in `pyproject.toml` and `package.json`/`package-lock.json`.
  Dependabot alerts and updates are on; the dependency review check blocks known-vulnerable packages and incompatible
  licences on pull requests.
- **CI:** workflows run with read-only tokens by default, pin actions to commit SHAs, never run a fork's code with
  secrets or a write token, and are linted by zizmor and actionlint. First-time contributors' workflows need approval.
- **Releases:** built in CI from a protected tag, with an SBOM and build provenance attestations.
- **Secrets:** the project needs none to build or test. Secret scanning and push protection are on.

## Out of scope

- A builder who deliberately runs hostile code on their own machine (for example a custom ComfyUI node they chose to
  install).
- The security of ComfyUI, Blender, browsers and model authors' code, beyond how the engine uses them.
- The licences of model weights, which belong to their authors (recorded in `engine/models.yaml`).
