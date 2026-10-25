# Quick start

From a fresh clone to a built site in a few minutes. Live 3D, charts, maps, type, vector art and miniature worlds need
nothing but Python and a browser; generated film and images need ComfyUI and a 24 GB GPU (see [Install](INSTALL.md)
for what each scene type needs). No GPU? [Try it on a laptop](laptop.md) is this path for a machine without a GPU.

## Install and look around

```bash
git clone https://github.com/Okohedeki/scroll-studio && cd scroll-studio
pip install -e .
studio doctor                         # what this machine can build
```

## Build an example

```bash
studio build examples/cellwright-bio  # live 3D: needs nothing but Python
studio preview cellwright-bio         # http://localhost:5173
studio ui                             # the Studio app: http://localhost:5180
```

The [examples](examples.md) list what every one shows and what it needs.

## Make your own site

```bash
studio new my-site                 # a starter site.yaml
studio directions my-site          # six art directions; --pick one
studio storyboard my-site --edit   # sketches, stills and an animatic before any video render
studio build my-site               # cached stage by stage: change one thing, rebuild one thing
studio inspect my-site             # pops, softness, halos and drift in every film
studio publish my-site --out site  # one static folder for GitHub Pages or any host
```

A site is one `site.yaml`. This one is a complete page:

```yaml
name: Harbour Hotel
theme: { preset: dusk }
sections:
  - type: hero
    title: A room above <em>the water.</em>
    image: { generate: "Hotel terrace above a harbour at sunrise, photoreal" }
  - type: cta
    title: Stay <em>a while.</em>
    button: { label: Book, href: "https://example.com" }
```

## Build with Claude

Open the repository in Claude Code and ask for a site. The `scroll-studio` MCP server (`.mcp.json`) gives Claude every
engine tool, and the `scroll-site` skill gives it the workflow. The tools are listed in the
[MCP reference](reference/mcp.md).

## Where next

- [Make a site](guide.md): the whole workflow, from direction boards to trailers.
- [Scenes](scenes.md) and [styles](styles.md): what you can build.
- [site.yaml reference](reference/spec/index.md): every field.
