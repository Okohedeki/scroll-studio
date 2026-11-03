# Product stills

`studio stills my-shop` turns one product photo into a reviewed set of stills: pack shots, lifestyle scenes and
close details. It explores several art directions, makes candidates across seeds and backends, scores them, and
keeps a varied shortlist for each shot ([design](https://github.com/Okohedeki/scroll-studio/issues/175)).

```yaml
# docs: no-validate (a project file)
name: Example Shop
brief: An autumn range of glazed planters.
outputs:
  stills:
    photo: inputs/product.png        # a cut-out PNG, or a photo on a plain backdrop
    describe: a glazed green planter  # what it is, for the prompts
    shots: [packshot, lifestyle, detail]
    directions: 4                    # art directions to explore
    candidates: 2                    # seeds per direction and shot
    keep: 3                          # shortlist size per shot
    size: [1600, 1600]
```

A `site.yaml` project gets stills after `studio migrate my-shop --write` ([the project file](project-file.md)).

## How a still is made

1. **Directions.** A text backend writes divergent art directions: setting, light, palette and mood. With none
   (see `studio models`), a seeded local composer picks them, and the same seed gives the same set.
2. **Backdrop.** A pack shot stands on a seamless sweep in the direction's palette. A lifestyle scene is painted by
   an image backend; with none, it is drawn from the palette, so the flow runs on any laptop. A detail is the
   product close and cropped over a softened scene.
3. **The product** is cut out of the photo (rembg when the `ml` extra is installed, else a plain-backdrop key) and
   composited with a contact shadow. Its pixels are never redrawn.
4. **Blending.** Where an edit backend can run, one pass matches the scene's light. If it changes the product by
   more than `fidelity`, the composite is kept instead.
5. **Critics** score each candidate: fidelity (how little the product changed), framing (the right share of the
   frame, nothing cut off) and contrast (the product stands apart). A novelty check keeps near-duplicates off the
   shortlist.

## Reviewing

In the Studio app (`studio ui`), a project with `outputs.stills` has a **Stills** tab: the same view, with **More like this**, **Something different**, **Compare** (two side by side) and **Pick** on each lead still. Outside the app, open `stills/board.html`. Each shot shows its best candidate large, the rest of its shortlist beside it, and every
other candidate below, best first. Click any candidate to look at it.

| Command | What it does |
| --- | --- |
| `studio stills my-shop` | The first set, or fill in what is missing (the directions are kept) |
| `studio stills my-shop --more <id>` | More seeds in that candidate's direction and shot |
| `studio stills my-shop --different` | New directions, unlike the ones there, across every shot |
| `studio stills my-shop --pick <id>` | Mark that candidate as its shot's final |

Every candidate's record (direction, backend, model, prompt, seed and scores) is kept in `stills/stills.json`, so any
one can be made again. The MCP tool `make_stills` does the same as the command.

## Ads

`studio ads my-shop` makes placement-sized ads from the stills: each shot's pick, or its best if none is picked. The
product is kept whole in every size; where a size needs more backdrop than the still has, its edges are carried
outward and softened. The headline and call to action sit on a band in the brand's accent colour.

```yaml
# docs: no-validate (a project file)
outputs:
  ads:
    sizes: [1x1, 4x5, 9x16]          # also 16x9 and 1.91x1
    headline: Made for slow mornings
    cta: Shop the range
    shots: [lifestyle, packshot]
    width: 1080
```

Files land in `ads/`, listed in `ads/ads.json`. The MCP tool is `make_ads`.

## Listing copy

`studio listing my-shop` writes a title, bullet points and a description to `listing/listing.md` (and `.json`).
A text backend writes it from the brief and `describe`, told never to invent specifications or claims. With no text
backend, a draft is filled from what the project says, with places marked for the rest.

```yaml
# docs: no-validate (a project file)
outputs:
  listing:
    bullets: 5
    tone: warm, plain
```

The MCP tool is `write_listing`.
