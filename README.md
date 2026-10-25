<div align="center">
  <img src="docs/media/logo.svg" alt="Scroll Studio" width="88" />
  <h1>Scroll Studio</h1>
  <p><strong>An open-source design studio for scroll-driven landing pages. One YAML file in, a finished site out, made on your own machine with no API keys.</strong></p>
  <table>
    <tr>
      <td align="center" width="50%">
        <a href="https://okohedeki.github.io/scroll-studio-showcase/"><strong>See it live &rarr;</strong></a><br />
        Every example, built by this engine, on one page. Scroll it.
      </td>
      <td align="center" width="50%">
        <a href="docs/laptop.md"><strong>Try it on a laptop &rarr;</strong></a><br />
        No GPU needed: <code>pip install -e .</code>, then <code>studio new my-site --laptop</code>.
      </td>
    </tr>
  </table>
  <p>
    <a href="https://okohedeki.github.io/scroll-studio-showcase/">Showcase</a> ·
    <a href="#get-started">Get started</a> ·
    <a href="https://okohedeki.github.io/scroll-studio/">Docs</a> ·
    <a href="docs/examples.md">Examples</a> ·
    <a href="https://github.com/Okohedeki/scroll-studio/releases/latest">Releases</a> ·
    <a href="CHANGELOG.md">Changelog</a>
  </p>
  <p>
    <a href="https://github.com/Okohedeki/scroll-studio/releases/latest"><img src="https://img.shields.io/github/v/release/Okohedeki/scroll-studio" alt="Latest release" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="AGPL-3.0" /></a>
    <a href="https://github.com/Okohedeki/scroll-studio/actions/workflows/tests.yml"><img src="https://github.com/Okohedeki/scroll-studio/actions/workflows/tests.yml/badge.svg" alt="Tests" /></a>
    <a href="https://scorecard.dev/viewer/?uri=github.com/Okohedeki/scroll-studio"><img src="https://api.scorecard.dev/projects/github.com/Okohedeki/scroll-studio/badge" alt="OpenSSF Scorecard" /></a>
    <img src="https://img.shields.io/badge/models-local%20only-ff7a3d" alt="Local models only" />
    <img src="https://img.shields.io/badge/MCP-ready-8a5cff" alt="MCP ready" />
  </p>
</div>

## Your brand. Your scroll.

| Scenes | Styles | Workflow |
| :--- | :--- | :--- |
| One camera take through a whole page | 32 page experiences, one word to switch | Six art directions from one brief |
| Cinemagraphs, light from dawn to night | Zoetrope, stop-motion, paint on glass | Storyboard before you render |
| Fly inside your product's 3D model | Pop-up book, multiplane, Spider-Verse smears | A polish report on every film |
| Miniature worlds, maps, charts, live 3D | Film cuts between any two sections | Claude drives it all through MCP |
| Photo parallax from your own pictures | Any brand, from a page, a logo or a brand.yaml | Remake a live landing page: `studio remake <url>` |

The heavy scenes (generated film and images) are made with open models on your own GPU (Z-Image, Qwen-Image-Edit, LTX-2.3,
Wan 2.2, SeedVR2, Blender); photo parallax, kinetic type, maps, data, code, live 3D and every style need no GPU. The output is plain HTML, CSS and JS you can host anywhere. The [examples](docs/examples.md) show what each
scene does; they are not templates. Bring your own photos, footage, 3D models, logo and copy, or a brief.

<details>
<summary><strong>See the scenes</strong> · one take, cinemagraphs, light, inside the product, miniature worlds, film cuts</summary>

<table>
  <tr>
    <td><img src="docs/media/readme/journey.jpg" alt="The one-take page: a farmhouse hearth room" width="100%" /></td>
    <td><img src="docs/media/readme/cinemagraphs.jpg" alt="Cinemagraphs: a hotel where only one thing moves" width="100%" /></td>
  </tr>
  <tr><td align="center">The one-take page</td><td align="center">Cinemagraphs</td></tr>
  <tr>
    <td><img src="docs/media/readme/light.jpg" alt="Light as the scroll: a harbour at blue hour" width="100%" /></td>
    <td><img src="docs/media/readme/inside.jpg" alt="Inside the product: the Framework mainboard fan" width="100%" /></td>
  </tr>
  <tr><td align="center">Light as the scroll</td><td align="center">Inside the product</td></tr>
  <tr>
    <td><img src="docs/media/readme/diorama.jpg" alt="Miniature worlds: a tilt-shift harbour" width="100%" /></td>
    <td><img src="docs/media/readme/film-cuts.jpg" alt="Film cuts: a ring logo becomes the sun" width="100%" /></td>
  </tr>
  <tr><td align="center">Miniature worlds</td><td align="center">Film cuts</td></tr>
  <tr>
    <td><img src="docs/media/readme/type-world.jpg" alt="Type in the world: a headline behind a tree" width="100%" /></td>
    <td><img src="docs/media/readme/directions.jpg" alt="Direction boards: six art directions side by side" width="100%" /></td>
  </tr>
  <tr><td align="center">Type in the world</td><td align="center">Direction boards</td></tr>
</table>

</details>

## Get started

```bash
git clone https://github.com/Okohedeki/scroll-studio && cd scroll-studio
pip install -e .
studio doctor                         # what this machine can build
studio build examples/cellwright-bio  # live 3D: needs nothing but Python
studio preview cellwright-bio         # http://localhost:5173
studio ui                             # the Studio app: http://localhost:5180
```

No GPU? [Try it on a laptop](docs/laptop.md): `studio new my-site --laptop` makes a site that builds without ComfyUI or
Blender, and `studio remake <url> --no-gpu` turns a live page into one.

| What you build | What it needs |
|---|---|
| Live 3D, charts, maps, type, vector art, splat scans, miniature worlds, code flights, all 32 styles | Python and a browser |
| Photo parallax, product sequences, inside the product | Runs on the CPU; Blender and a GPU make it fast |
| Generated film, the one-take page, cinemagraphs, light as the scroll, generated images | ComfyUI and a 24 GB GPU (RTX 4090 class) |

Full setup (GPU, Blender, ComfyUI and the models) is in [docs/INSTALL.md](docs/INSTALL.md).

### Build with Claude

Open the repo in Claude Code and ask for a site. The `scroll-studio` MCP server (`.mcp.json`) gives Claude every
engine tool, and the `scroll-site` skill gives it the workflow. Or paste this into any coding agent:

```text
Install Scroll Studio on this machine and build one of its examples, following
https://github.com/Okohedeki/scroll-studio/blob/main/docs/INSTALL.md
```

<details>
<summary><strong>Make your own site</strong></summary>

```bash
studio new my-site                 # a starter site.yaml
studio remake https://example.com/ # or start from a live landing page, told as a scroll site
studio directions my-site          # six art directions; --pick one
studio storyboard my-site --edit   # sketches, stills and an animatic before any video render
studio build my-site               # cached stage by stage: change one thing, rebuild one thing
studio inspect my-site             # pops, softness, halos and drift in every film
studio publish my-site --out site  # one static folder for GitHub Pages or any host
```

The whole workflow is in the [guide](docs/guide.md).

</details>

## Documentation

| Need | Start here |
|---|---|
| Setup | [Install](docs/INSTALL.md) · [What each machine can build](docs/INSTALL.md) |
| What it can make | [Scenes](docs/scenes.md) · [Styles](docs/styles.md) · [Examples](docs/examples.md) · [Showcase](https://okohedeki.github.io/scroll-studio-showcase/) |
| Reference | [site.yaml, CLI and MCP reference](https://okohedeki.github.io/scroll-studio/reference/), generated from the engine |
| Making a site | [Guide](docs/guide.md): direction boards, storyboards, client copy decks, trailers, Claude |
| Why it exists | [Local only, 10 to 30 times fewer tokens](docs/why.md) |
| How it works | [Engine](docs/ENGINE.md) · [Style research](docs/styles/) · [Roadmap](docs/directions.md) |
| Contributing | [How to contribute](CONTRIBUTING.md) · [Rules per area](CONTRIBUTING.md#rules-per-area) · [Code of conduct](CODE_OF_CONDUCT.md) · [Getting help](SUPPORT.md) |
| The project | [Governance](GOVERNANCE.md) · [Maintainers](MAINTAINERS.md) · [Compatibility](docs/compatibility.md) · [Design proposals](docs/rfcs/README.md) · [Security](SECURITY.md) · [Threat model](docs/security/threat-model.md) |
| Releases | [What's new](docs/whats-new.md) · [Changelog](CHANGELOG.md) · [1.5 milestone](https://github.com/Okohedeki/scroll-studio/milestone/1) |

## Licence

Free software under the **GNU AGPL-3.0** with additional terms ([NOTICE.md](NOTICE.md)): derivatives stay open source
and keep the attribution word for word, and **sites you build are yours** to license however you like. Model weights
keep their own licences. Details in [docs/licence.md](docs/licence.md); AI agents, see [AGENTS.md](AGENTS.md).
