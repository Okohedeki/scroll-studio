---
title: Documentation
hide:
  - navigation
  - toc
---

<div align="center" markdown>

![Scroll Studio](media/logo.svg){ width="88" }

# Scroll Studio

**An open-source design studio for scroll-driven landing pages. One YAML file in, a finished site out, made on your own GPU with no API keys.**

[Get started](INSTALL.md){ .md-button .md-button--primary }
[See the examples](examples.md){ .md-button }
[Showcase](https://okohedeki.github.io/scroll-studio-showcase/){ .md-button }

</div>

Every image and video is made with open models on your machine (Z-Image, Qwen-Image-Edit, LTX-2.3, Wan 2.2, SeedVR2,
Blender). The output is plain HTML, CSS and JS you can host anywhere. Bring your own photos, footage, 3D models, logo
and copy, or a brief. The [examples](examples.md) show what each scene does; they are not templates.

## What it makes

<div class="grid cards" markdown>

-   **Scenes**

    One camera take through a whole page, cinemagraphs, light from dawn to night, a fly-through of your product's 3D
    model, miniature worlds, maps, charts, live 3D.

    [Scenes](scenes.md)

-   **Styles**

    32 page experiences, one word to switch: zoetrope, stop-motion, paint on glass, pop-up book, Spider-Verse smears,
    and film cuts between any two sections.

    [Style gallery](styles.md) · [Style research](styles/index.md)

-   **Workflow**

    Six art directions from one brief, a storyboard before any render, a polish report on every film, and Claude
    driving it all through MCP.

    [Make a site](guide.md)

-   **Reference**

    Every `site.yaml` field, every `studio` command and every MCP tool, generated from the engine so it cannot drift.

    [Reference](reference/index.md)

</div>

| | |
| :--- | :--- |
| ![The one-take page: a farmhouse hearth room](media/readme/journey.jpg) | ![Cinemagraphs: a hotel where only one thing moves](media/readme/cinemagraphs.jpg) |
| **The one-take page** | **Cinemagraphs** |
| ![Light as the scroll: a harbour at blue hour](media/readme/light.jpg) | ![Inside the product: the Framework mainboard fan](media/readme/inside.jpg) |
| **Light as the scroll** | **Inside the product** |
| ![Miniature worlds: a tilt-shift harbour](media/readme/diorama.jpg) | ![Film cuts: a ring logo becomes the sun](media/readme/film-cuts.jpg) |
| **Miniature worlds** | **Film cuts** |

## Find your way

| Need | Start here |
| --- | --- |
| Set up | [Install](INSTALL.md) · [Quick start](quickstart.md) |
| Make a site | [Guide](guide.md): direction boards, storyboards, client copy decks, trailers, Claude |
| What it can make | [Scenes](scenes.md) · [Styles](styles.md) · [Examples](examples.md) |
| Look something up | [site.yaml](reference/spec/index.md) · [Command line](reference/cli.md) · [MCP tools](reference/mcp.md) |
| How it works | [Architecture](ENGINE.md) · [Roadmap](directions.md) |
| Contribute | [How to contribute](contributing/guide.md) · [Build the docs](contributing/building-the-docs.md) |
| Releases | [What's new](whats-new.md) · [Changelog](project/changelog.md) |

## Licence

Free software under the **GNU AGPL-3.0** with additional terms ([notice](project/notice.md)): derivatives stay open
source and keep the attribution word for word, and **sites you build are yours** to license however you like. Model
weights keep their own licences. Details in the [licence page](licence.md).
