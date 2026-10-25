# Try it on a laptop

You do not need a GPU, ComfyUI or Blender to make a Scroll Studio site. Kinetic type, photo parallax, maps, data, code
flights, live 3D, every block and all 32 styles build on the CPU. This page goes from `pip install` to a built site; it
should take about five minutes, most of it the install. To see what the finished thing looks like first, open the
[live showcase](https://okohedeki.github.io/scroll-studio-showcase/).

## 1. Install

You need Python 3.10 or newer and git. Node.js, FFmpeg and Blender are not needed for anything on this page.

```bash
git clone https://github.com/Okohedeki/scroll-studio && cd scroll-studio
pip install -e .
studio doctor
```

`studio doctor` opens with two lists: **Without a GPU you can build**, each line ticked when this machine is ready for it
(or with the one `pip install` that makes it ready), and **Needs the GPU stack**. The long table below them is the whole
toolchain; a red line there only matters for the scenes that need it.

## 2. Make a site and build it

```bash
studio new my-site --laptop
studio build my-site
studio preview my-site                # http://localhost:5173
```

`studio new --laptop` writes `projects/my-site/site.yaml`: a scene of kinetic type, a second one that reveals a sentence as
you scroll, then an intro, three features, two stats and a call to action. Every scene in it is one that needs no models,
so the build finishes in seconds. Edit the YAML, build again, and only what you changed rebuilds.

Make it yours with `theme: { from: https://yoursite.com }` (or a logo, or a `brand.yaml`): your colours, fonts and logo.
A style is an optional experience on top of your brand, such as `style: bauhaus`; `studio looks` shows them all.

Try another experience by changing one word, `theme: { style: <name> }`; the [style gallery](styles.md) lists all 32, and
every one builds on a laptop.

## 3. Open on your own photo

A photo parallax gives a picture depth and a slow camera. It estimates depth with a small model
([Depth Anything V2 Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf), Apache-2.0), which runs on the
CPU and downloads once, on the first build (about 100 MB). It needs PyTorch and transformers:

```bash
pip install torch transformers
studio new my-photos --laptop --image path/to/photo.jpg
studio build my-photos
```

On Linux the default `torch` wheel is the large CUDA build; the CPU one is smaller:
`pip install torch --index-url https://download.pytorch.org/whl/cpu`.

To add a photo to a site you already have, copy it into the project's `inputs/` folder and add a scene:

```yaml
sections:
  - id: hero
    type: parallax
    layout: cards
    steps:
      - intro: true
        kicker: Welcome
        title: A picture, <em>given depth.</em>
        body: Your photo, turned into a slow camera move as you scroll.
        image: inputs/photo.jpg
```

Add more steps with more photos, and `moves: [dolly, pan, rise, orbit]` to choose the camera for each.

## 4. Then remake a page you already have

```bash
studio remake https://example.com --no-gpu
studio build example
studio preview example
```

`studio remake` reads a live landing page and writes a project from it: its main picture as the opening scene, its sections
as blocks, its calls to action with their links, its brand in `theme.from`. With `--no-gpu` the opening is a photo
parallax of that picture (it needs the `torch transformers` install above to build); a machine with no NVIDIA GPU does this by
default, and the flag makes a machine that has one do the same. It honours the site's `robots.txt`; remake pages you own or
have permission to use. The result is an ordinary `site.yaml`, so everything in step 2 applies to it.

## What else builds on a laptop

| You want | Scene | Needs besides `pip install -e .` |
|---|---|---|
| Words that move | `type` | nothing |
| A photo with depth | `parallax` | `pip install torch transformers` |
| A drawing painted in stages | `artwork` | nothing (your own image) |
| Line art that draws itself | `vector` | nothing for an SVG; `pip install -e .[vector]` to trace a raster image |
| A map journey | `map` | nothing (visitors load the tiles) |
| Charts from data | `chart` | a CSV |
| A flight through code | `code` | nothing |
| Live 3D, a miniature world, a scan | `scene3d`, `diorama`, `splat` | nothing (a scan is a `.ply` or `.spz`) |

These examples build without a GPU: [FORM/26](https://github.com/Okohedeki/scroll-studio/blob/main/examples/form-conference/site.yaml) (type),
[Cellwright Bio](https://github.com/Okohedeki/scroll-studio/blob/main/examples/cellwright-bio/site.yaml) (live 3D),
[Northstar Observatory](https://github.com/Okohedeki/scroll-studio/blob/main/examples/northstar-observatory/site.yaml) (live 3D),
[Tidewater Lines](https://github.com/Okohedeki/scroll-studio/blob/main/examples/tidewater-lines/site.yaml) (a map),
[Harbourlight](https://github.com/Okohedeki/scroll-studio/blob/main/examples/little-harbour/site.yaml) (a miniature world),
[Wunderkammer](https://github.com/Okohedeki/scroll-studio/blob/main/examples/wunderkammer/site.yaml) (vector line art) and
[Atelier Sfumato](https://github.com/Okohedeki/scroll-studio/blob/main/examples/atelier-sfumato/site.yaml) (artwork). Build one with
`studio build examples/<name>`.

## What needs the GPU stack

Generated film, the one-take page, cinemagraphs, light as the scroll and any `generate:` picture need ComfyUI and a 24 GB
GPU. Product sequences and the inside-the-product flight need Blender (slow without a GPU, but it runs). A style's own
`art:` made from a prompt needs ComfyUI too; made from a file it does not. [Install](INSTALL.md) has the full setup, and
`studio doctor` says which of these this machine can do.

## Where next

- [Make a site](guide.md): direction boards, storyboards, publishing.
- [Scenes](scenes.md) and [styles](styles.md): everything you can build.
- [site.yaml reference](reference/spec/index.md): every field.
