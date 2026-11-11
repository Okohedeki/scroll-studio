# Product stills

`studio stills my-shop` turns one product photo into a reviewed set of stills: pack shots, lifestyle scenes and
close details. It explores several art directions, makes candidates across seeds and backends, scores them, and
keeps a varied shortlist for each shot ([design](https://github.com/Okohedeki/designai/issues/175)).

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

## From a product page

`studio import https://shop.example/products/mug` starts a project from a product page. It reads the page's
schema.org product data, its Open Graph tags and its text, saves the product pictures into `inputs/`, and writes a
product profile to `profile/profile.md`: what the product is, the main benefit, what the buyer wants, how it looks,
who it is for, proof points and objections. Every output below starts from that profile. The page's robots.txt is
obeyed. Import your own products, or ones you have permission to use.

```bash
studio import https://shop.example/products/mug --languages en,es,de
```

`--languages` sets the project's `languages`. Copy, captions and voice are written in each one for its market, not
translated word for word. The MCP tool is `import_product`.

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

`resolution: 1k | 2k | 4k` sets the width to 1080, 2048 or 4096 pixels. A still smaller than that is scaled up, and
`ads.json` says so (`upscaled_from`); for sharp 4k ads, make the stills at `size: [4096, 4096]`.

With [ad concepts](#ad-concepts), every ad is made once per concept and language, with that concept's headline and
call to action: `lifestyle-9x16-c2.es.png`. Set `concepts: false` to keep one ad per size.

Files land in `ads/`, listed in `ads/ads.json`. The MCP tool is `make_ads`.

## Ad concepts

`studio concepts my-shop` writes ad concepts from the product profile. Each concept is an angle on the product, with
a hook for the first two seconds, a headline and call to action, a few on-screen lines and a short spoken script.
The angles are problem, benefit, proof, comparison, routine, gift, unboxing, story, offer and objection. The first
language fixes them, and each other language gets the same concepts written for its market. The text backend is told
never to invent numbers, ratings or specifications. With no text backend, plain drafts come from the profile.

```yaml
# docs: no-validate (a project file)
languages: [en, es]
outputs:
  concepts:
    count: 6                  # how many concepts
    angles: []                # or a list, in order; empty: the engine picks
    seconds: 20               # length of each spoken script
    tone: warm, plain, direct
    claims: profile           # or page: only what the product page itself says
```

Written to `concepts/concepts.md` and `.json`. Ads and video ads make one variation per concept. The MCP tool is
`make_concepts`.

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

## Video

`studio video my-shop` makes a short product video from the stills: each shot's pick and shortlist, a slow push-in
on each, cross dissolves, and an end card with the ads' headline and call to action. A speech backend reads the
voiceover (ElevenLabs, with `ELEVENLABS_API_KEY` set); with none, the video is silent. A music file can sit under it.

```yaml
# docs: no-validate (a project file)
outputs:
  video:
    seconds: 15
    aspect: 9x16
    shots: [lifestyle, detail, packshot]
    voiceover: listing        # the listing's description; or the words themselves; empty for none
    music: inputs/bed.mp3     # optional; you need the right to use it
```

Written to `video/video-<aspect>.mp4` with `video/video.json`. The MCP tool is `make_video`.

## Video ads

`studio ugc my-shop` makes vertical, creator-style video ads, one for each of the first concepts in each language:

1. A presenter still: an edit job puts a generated presenter with the product still, and the product is kept as it
   is. The presenter is a made-up person. Never describe a real or famous one.
2. A presenter clip: a video job brings it to life, through local LTX-2.3 in ComfyUI or a provider, as `models:`
   allows. With no video backend, the still is shown with a slow push-in.
3. Product shots from the picked stills, cut to the length of the script.
4. The concept's hook on screen at the start, its script read as a voiceover, and the script burned in as captions
   a few words at a time.

The voice is a voiceover; lip sync is not attempted. Captions use DejaVu Sans or Arial, so a language written in
another script (Japanese, Arabic...) needs a font with those letters installed.

```yaml
# docs: no-validate (a project file)
outputs:
  ugc:
    concepts: 3                       # the first three concepts each get a video ad
    presenter: a friendly person in their thirties, casual clothes, at home
    aspect: 9x16
    captions: true
    presenter_seconds: 4
    music: inputs/bed.mp3             # optional; you need the right to use it
```

Written to `ugc/<concept>.<language>.mp4` (or `ugc/<concept>.mp4` with one language), with `ugc/ugc.json`. The MCP
tool is `make_video_ads`.

## Editing a picture

`studio edit my-shop ads/lifestyle-1x1.png "make the backdrop warmer"` changes a finished picture through an edit
job. The result goes next to it as `lifestyle-1x1.edit1.png`. With `--replace`, it goes over the picture instead,
and the original is kept once as `.orig`, so the steps that use the picture pick up the edit when they run again.
Every edit is listed in `edits.json`. Videos are edited through what they are made from: edit the still, or a
concept's script in `concepts/concepts.json`, then run `studio video` or `studio ugc` again. The MCP tool is
`edit_picture`.

## Page layouts

`studio layouts my-shop` writes several product pages from the project's own material: the picked stills and
shortlist, the listing copy, and the ads' headline and call to action. Each layout is arranged differently. A text
backend writes them when one can run; otherwise a local composer arranges the same material in distinct orders.
Every layout is checked against the site spec, and only blocks that build without a GPU are used (hero, intro,
features, gallery, faq, cta).

```yaml
# docs: no-validate (a project file)
outputs:
  layouts:
    count: 3
```

`layouts/board.html` shows each layout as a wireframe page with its stills. `studio layouts my-shop --pick l2` writes
that layout's sections into `outputs.site`, keeping the site's other settings and saving the old sections in
`layouts/site-before-pick.yaml`; then `studio build my-shop`. The MCP tool is `make_layouts`.
