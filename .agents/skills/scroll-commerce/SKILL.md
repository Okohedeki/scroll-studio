---
name: scroll-commerce
description: Make commerce creative with Scroll Studio's project file - product stills from one photo (pack shots, lifestyle scenes, details, scored and shortlisted), placement-sized ads, listing copy, a short product video, and generated product page layouts, all from one project.yaml. Use when asked for product photos, e-commerce images, ads in several sizes, store listing copy, a product video or a product page.
---

# Commerce outputs from one project file

A `project.yaml` holds the brief, brand, product and imagery once, and every output under `outputs:` reads them. A site
is one output (`outputs.site`); the rest are below. Old `site.yaml` projects convert with `studio migrate <project>
--write`. Reference: `docs/project-file.md` and `docs/stills.md`.

```yaml
name: Example Goods
brief: A small studio's stoneware mugs, glazed by hand.
brand: { preset: paper }
outputs:
  stills: { photo: inputs/product.png, describe: a speckled stoneware mug, directions: 3, candidates: 2 }
  ads: { sizes: [1x1, 4x5, 9x16], headline: Made for the first cup, cta: Shop the mugs }
  listing: {}
  video: { seconds: 12, aspect: 9x16 }
  layouts: { count: 3 }
```

## The order of work

1. **Stills first** (`studio stills <project>`, MCP `make_stills`). One product photo becomes pack shots, lifestyle
   scenes and close details, across several art directions and seeds. The product is cut out and composited, never
   redrawn; critics score fidelity, framing and contrast, and a varied shortlist goes on `stills/board.html` (also the
   Stills tab in `studio ui`). Look at the board, then `--more <id>`, `--different` or `--pick <id>`.
2. **Ads** (`studio ads`, `make_ads`) from each shot's pick: every placement size with the product kept whole and the
   headline and call to action on a band in the brand's accent.
3. **Listing copy** (`studio listing`, `write_listing`): title, bullets, description, from the brief. With no text model
   it writes a marked draft; never present that as finished copy.
4. **Video** (`studio video`, `make_video`): push-ins on the stills, dissolves, an end card; a voiceover only when a
   speech backend is set up.
5. **Page layouts** (`studio layouts`, `make_layouts`): several product pages made from the stills and copy, each
   arranged differently; `--pick <id>` makes one the site, then `studio build`.

## Rules

- A good product photo matters most: a plain backdrop, the whole product in frame, even light. The cut-out keeps a soft
  shadow unless the `ml` extra (rembg) is installed.
- Look at every board before moving on. A lifestyle scene can come back with a second product painted into it, or a
  backdrop that fights the product; reject it with `--different` or pick another.
- `studio models` shows which image, edit, text and speech backends can run. Local models are the default; providers
  run only when `models:` asks for them and their key is set.
