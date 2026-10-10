# Scroll Studio style research: styles 16 to 21

**Bauhaus, Pixel art, Blueprint, Art deco, Neo-brutalism, 2D anime intro (OP)**

Prepared 2026-10-10 for the Scroll Studio engine. The aim: each style has to be a different *interaction model*, not a reskin. So every brief below starts from one question: **what does one notch of the scroll wheel mean in this style?** Fonts and colours come after that.

> **How to read the citations.** URLs are inline. Where a claim comes from general design or animation knowledge and not from a source I retrieved, I say "(general knowledge)". Treat named live sites as references to check, because sites get redesigned. One example: one source says gumroad.com's live homepage no longer serves its famous hard shadows.

---

## Cross-cutting principle: six different scroll models

The last attempt failed because all 20 styles shared one scroll model: a vertical stack of sections that fade or slide up as they enter the viewport. The table below sets the scroll model for each of these six styles. The engine should treat it as a separate layer (a "scroll grammar") from the skin.

| Style | What scroll *is* | Time quantisation | Motion curve | Spatial axis | Primary renderer |
|---|---|---|---|---|---|
| Bauhaus | Composing a poster: shapes move to new positions in one fixed frame | Continuous scrub between composed "states" that you can snap to | Mechanical ease-in-out, strong overshoot on primitives | Diagonals and rotation inside a pinned poster | SVG / CSS transforms |
| Pixel art | Playing a game: scroll input becomes *turns*, steps and dialog advances | Discrete. Positions snap to an integer pixel grid and sprites animate at 8 to 12 fps | `steps()`, no easing | Horizontal side-scroll or overworld map, camera follows the player | Canvas 2D (nearest-neighbour) |
| Blueprint | A pen drafting: the drawing completes as you scroll | Continuous and *linear*. Scroll position equals pen position | Linear (constant pen speed), with a short settle when a dimension label appears | Camera pans and zooms across one large sheet | SVG strokes plus a CSS grid background |
| Art deco | A stage show: curtains, marquees and symmetric reveals that open from a central axis | Continuous but slow, with *scenes* | Ease-in-out-sine, long durations, never bouncy | Mirror symmetry about the vertical centre line | CSS clip-path / masks plus SVG sunbursts |
| Neo-brutalism | A pinboard or desk: objects get slapped down and you can grab them | Threshold-triggered *events*, not scrubbed | Springs with overshoot. Hard offsets and no blur | Free 2D placement, rotation, overlap | DOM plus a little physics |
| Anime OP | A 90-second edit: scroll is the playhead and every section is a *cut* | Discrete cuts on a beat grid, with holds (freeze frames) | Hard cuts between shots. Smears and ease-out *within* a shot | Camera moves inside shots (pans, zooms, shakes) | Canvas/WebGL compositing plus DOM type |

If two of these styles feel alike, check this table first. If they share a scroll model, it doesn't matter that their fonts differ.

---

## 1. Bauhaus

### 1.1 Origin and defining aesthetic

The Bauhaus (Weimar 1919, Dessau 1925, Berlin 1932 to 1933) did not originally treat typography as central. That changed in 1923 when László Moholy-Nagy took over the preliminary course and an advertising workshop was set up for the 1923 Weimar exhibition ([Goethe-Institut teaching module](https://www.goethe.de/ins/ca/en/m/kul/kue/bau/ver/m09.html)). Moholy-Nagy defined the "new typography" in that exhibition's catalogue, and in 1925 he introduced "typophoto", the fusion of type and photography. He designed most of the 14 *Bauhausbücher* (1925 to 1930) ([Letterform Archive: Bauhaus publications](https://exhibitions.letterformarchive.org/bauhaus/exhibit/bauhaus-publications)). Herbert Bayer's 1926 Hans Poelzig lecture poster is the textbook example. MoMA describes it as strict sans-serif type, a single type treatment, an underlying grid and an asymmetrical composition, with type size and weight running from most to least important ([MoMA](https://www.moma.org/collection/works/5101)). Bayer's lowercase-only "universal" alphabet was built from arcs, angles and straight lines ([Wikipedia: Herbert Bayer](https://en.wikipedia.org/wiki/Herbert_Bayer)). Kandinsky's 1923 questionnaire asked students to pair yellow, red and blue with triangle, square and circle. The expected answer was a yellow triangle, a red square and a blue circle ([Immelmann et al. via PhilArchive](https://dc2.philarchive.org/rec/IMMKBQ); [Google Arts & Culture: The importance of shapes](https://artsandculture.google.com/story/OwURAJwcVUkTow)).

**Visual signatures:**
1. **Primitives as protagonists.** Circle, square and triangle in flat red, yellow, blue and black on off-white. These shapes do structural work in the composition and are not ornament.
2. **Asymmetric grids with heavy bars and rules.** Thick black bars and rules divide the field and stress key words (MoMA, above).
3. **Diagonal type.** Headlines run at about 15° to 45°, stacked or rotated 90° up a margin. This comes from Constructivist influence (El Lissitzky) and appears in Joost Schmidt's 1923 exhibition poster (Goethe module, above).
4. **Scale contrast.** One huge word or numeral against tiny captions, with nothing in between.
5. **Typophoto.** High-contrast black-and-white photography cut into geometric masks (circles, half-circles) and overlapped by type.
6. **Lowercase and sans-serif.** Bayer's lowercase manifesto and the use of grotesque/geometric sans.

### 1.2 Layout and information architecture

- **The poster is the unit.** Each section is one full-viewport, *pinned* poster, not a stack of cards. The page reads as a portfolio of posters, or one poster that keeps recomposing.
- **A visible but irregular grid.** For example, one wide column plus five narrow ones, a structure that has been used to recreate a Moholy-Nagy page with CSS `grid-template-columns` (seen in a search summary; I couldn't confirm the original article). daisyUI's trend page suggests treating red, yellow and blue as deliberate signals and not decoration ([daisyUI trends: Bauhaus](https://trends.daisyui.com/trend/bauhaus/)). Content sits off-centre, and you balance it with a counterweight shape and not by centring it.
- **Information hierarchy through scale.** H1 is 3 to 6 times body size, and H2 barely exists. Numbered sections ("1", "2", "3") are set as huge numerals that double as compositional shapes.
- **Reading path as a diagonal.** The eye moves from top-left to bottom-right along a dominant diagonal bar. Put the CTA at the end of that diagonal.

### 1.3 Signature interactions and scroll behaviour

**How scroll feels:** mechanical and *constructive*, like a kinetic sculpture or Moholy-Nagy's *Light-Space Modulator*. Scrolling moves the parts of one composition to new positions. The page does not travel. The poster rearranges inside a fixed frame.

**What scroll drives:**
- **Poster recomposition.** Each section is a pinned stage holding about 6 to 12 primitives (circle, half-disc, square, bar, triangle, rule) plus headline words. Every primitive has a keyframe for each "state". Scroll interpolates between states. State A might be "headline", state B "feature 1" and state C "feature 2". The *same* red circle can be a sun behind the headline, then a pie-segment diagram, then a button. This persistence is what sets it apart from other styles. **Objects survive between sections and change role.**
- **Rotation as a verb.** Text blocks rotate between 0° and -90°/45°, and the grid itself can rotate 15° to set up a diagonal composition. Rotate around shape centres or corners. Use rigid moves and never skew.
- **Snap to composed states.** Scroll scrubs continuously, but with `scroll-snap` or a programmatic settle the composition always rests on a *designed* state. A half-way state should not look like a finished poster.

**Headline arrival:** letters arrive as *blocks*. Each word slides in along the grid axis, from the edge it is aligned to, and locks against a bar. Alternatively the headline is built from geometric letterforms that assemble from circles and bars (a nod to Bayer and Albers' stencil type). Do not fade letters in.

**Stats:** a number is a *shape*. Show 72% as a circle with a 72% wedge cut out, rendered in flat red, or as a bar whose length is the value against a ruled scale. Let the big numeral overlap the shape. Scrubbing grows the wedge or bar. This is a geometric diagram and not a counter ticking up.

**Feature list:** each feature gets one primitive and one primary colour (triangle, square, circle), and its copy sits in a strict narrow column. As you scroll, the active feature's shape grows to dominate the composition and the others shrink into a "legend" strip. This is a structured index and not a card carousel.

**Section transitions:** a giant primitive *wipes* the frame. A black bar sweeps diagonally, or a circle scales up from a corner to fill the viewport and becomes the next poster's background colour. Use transform and clip-path only.

**Hover / pointer:** shapes respond with *rigid* motion: a 90° rotation step, a slide of one grid unit, or a colour swap among red, yellow and blue. Pointer parallax is allowed only as whole-shape translation in grid units, never smooth floaty parallax. Buttons can be a square that rotates into a diamond on hover.

**CTA:** the poster's composition resolves *into* the CTA. At the end of the page, every primitive migrates into one formation (an arrow made of a triangle and a bar, for example) and the CTA label sits in its block. This is the payoff for recomposition: the last state of the poster points at the button.

**Real-world references:**
- The Bauhaus-Universität Weimar centenary site (Happy Little Accidents with TRITUM) won a 2019 TYPO Award for interpreting historical Bauhaus references in a new way ([uni-weimar](https://bauhaus100.uni-weimar.de/en/news/news-post/titel/the-anniversary-website-of-the-bauhaus-universitaet-weimar-wins-the-typo-award/)).
- The Taiwan "Bauhaus 100: Manifest of Practice" identity used a horizontal-line grid that visitors helped compose ([Red Dot](https://red-dot.org/project/bauhaus-100-manifest-of-practice-in-taiwan-48619)). That participatory idea suits a scroll-recomposed poster.
- Google Arts & Culture's Bauhaus stories use the shape vocabulary in a scroll-story format ([example](https://artsandculture.google.com/story/OwURAJwcVUkTow)).

### 1.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | A vertical strip on the left with rotated (-90°) lowercase labels, or a single black bar with a numbered index ("1 work 2 about"). The active item is marked by a small red square, not an underline. |
| Buttons | Rectangular, flat fill (red/blue/yellow/black), no radius, no shadow. Hover: a rigid 90° rotation of an arrow glyph or a one-grid-unit slide. A circle button is allowed for the single primary CTA. |
| Cards / features | Not "cards". Features are *zones* of the poster, each tied to a primitive. If you must have boxes, use black rules between them and not borders around them. |
| Stats | Geometric diagrams: wedge-cut circles, ruled bars, stacked squares. Huge numerals in a heavy grotesque. |
| Timeline / steps | A thick diagonal bar with numbered circles along it. Scroll travels along the diagonal. |
| Quote | Set as a typographic poster: the quote at 60 to 120 px in lowercase, rotated or stepped, with a large red quotation mark built from two squares. |
| FAQ | Questions as a numbered list with heavy numerals. Expanding rotates a "+" built from two bars into "×" (a rigid 45° turn). |
| Footer | The poster's colophon: small type in a strict column, plus one large primitive as a sign-off. |
| Images | Typophoto. Black-and-white, high contrast, cropped into circles, half-discs or rectangles, overlapped by colour planes in `mix-blend-mode: multiply`. |

### 1.5 Typography and colour

- **Display:** **Jost** 600 to 800 (a Futura-like geometric revival) or **Josefin Sans** 700. For heavy grotesque poster headlines, use **Archivo Black** or **Archivo** 800 to 900. For a lowercase Bayer homage, set display type in lowercase with tight tracking (-0.02em).
- **Captions / numerals:** **Jost** 400 or **DM Mono** 400, caps with tracking +0.08em for labels.
- **Case:** lowercase manifesto headlines (Bayer), or all-caps stacked blocks (Poelzig poster). Never title case.
- **Palette (flat, no tints):**
  - Bauhaus red `#BE1E2D`
  - Yellow `#F2C230`
  - Blue `#1F4E9C`
  - Black `#111111`
  - Paper `#EFE8DA`, alternative white `#FAF7F0`
  - Optional grey `#8C8C8C` for typophoto duotone
- A design-system kit for the style specifies flat colour, pure geometric forms, a strict grid and asymmetric balance, with diagonal energy allowed ([wrongstack Bauhaus kit](https://cdn.jsdelivr.net/npm/@wrongstack/core@0.295.1/design-kits/bauhaus/KIT.md)).

### 1.6 Implementation

- **SVG scene graph per pinned section.** Each primitive is an SVG element with per-state `{x, y, rotate, scale, fill}`. Interpolate with GSAP ScrollTrigger (`scrub: true`, `pin: true`) or CSS scroll-driven animations (`animation-timeline: view()`, [MDN](https://developer.mozilla.org/docs/Web/CSS/animation-timeline); [WebKit guide](https://webkit.org/blog/17101/a-guide-to-scroll-driven-animations-with-just-css/)) with `@supports` fallbacks.
- **Shape persistence across sections:** use a single fixed SVG layer behind the content flow (`position: fixed`) whose primitives are driven by one global timeline. This is better than one SVG per section, because it lets shapes survive between sections.
- **Masks for typophoto:** `clip-path: circle()` or `polygon()` on `<img>`, plus `filter: grayscale(1) contrast(1.4)`.
- **Performance:** animate `transform` and `opacity` only. Keep under about 40 animated nodes per frame. Avoid animating SVG `d`. Use transform for everything.
- **Accessibility:** rotated text must also exist unrotated in reading order, or use `writing-mode` and not transforms for rotated nav. Red `#BE1E2D` on paper is about 5.9:1 (fine), but **yellow fails as text colour on paper**: use yellow only as fills behind black text. Under `prefers-reduced-motion`, render each state as a static poster and step between them with crossfades. The poster composition still reads.

### 1.7 Anti-patterns

- **Cheap version:** three coloured shapes floating with smooth parallax over a normal SaaS layout. Circles with soft drop shadows. Rounded corners. Primary colours as tinted pastels.
- **"Mondrian confusion":** black-ruled grids with primary rectangles belong to De Stijl, not Bauhaus. They can be a sub-motif but should not be the whole identity.
- **Using Bauhaus 93** or similar novelty fonts. These are a 1970s pastiche.
- **Same-as-Neo-brutalism trap:** both use flat primary colours and black. The differences: neo-brutalism has *hard offset shadows, borders around everything, stickers and chaos*. Bauhaus has *no shadows, no borders around boxes, objects that persist and recompose, rigid geometric motion and a quiet paper ground*. If you add a box-shadow, it stops being Bauhaus.
- **Same-as-Art-deco trap:** both are geometric. Deco is *symmetrical, ornamental and metallic*. Bauhaus is *asymmetric, functional and flat*.

### 1.8 UX signature

**You don't scroll down the page. You compose a poster.** One stage stays pinned while a red circle, a black bar and a yellow triangle slide, rotate and re-dock along a diagonal grid. Each designed resting point reads as a finished 1926-style poster that says something new: headline, then feature, then stat. The same circle that was the sun behind the headline becomes the pie chart and finally the CTA button. The visitor should feel they are watching the layout *being designed*. Objects persist and change role. No other style keeps the same physical shapes on screen across the whole site.

---

## 2. Pixel art (8/16-bit game)

### 2.1 Origin and defining aesthetic

Pixel art comes from the hardware limits of 8-bit (NES, 1983 to 1990s, 54-colour master palette, 8×8 tiles, 3 colours plus transparency per sprite) and 16-bit consoles (SNES / Mega Drive, larger palettes, parallax layers, Mode 7) (general knowledge). The aesthetic is built from game *grammar* as much as pixels:

1. **Title screen.** A logo, a blinking "PRESS START", a copyright line and an attract-mode loop.
2. **HUD.** Score, lives, coins, timer, health/MP bars, minimap, all on a fixed layer over the playfield.
3. **Dialog boxes.** Bordered windows (JRPG style: a blue gradient with a white border, or a black box with a white frame), typewriter text with a per-character blip sound, a portrait, and a bouncing "▼" advance arrow.
4. **Level select / overworld map.** Nodes connected by dotted paths (Super Mario World), with locked and cleared states.
5. **Sprite animation.** 2 to 8 frame loops at about 8 to 12 fps, no tweening, plus squash on landing.
6. **Screen transitions.** Mosaic/pixelate dissolves, iris wipes (circle closing on the player), Zelda-style screen flip-scrolls, battle-swirl transitions, fade to black in palette steps.

### 2.2 Layout and information architecture

- **The site is a game.** Map the IA onto game structure:
  - Hero → title screen
  - Sections → levels / worlds (World 1-1: "The Problem", 1-2: "How it works")
  - Features → items / power-ups / party members
  - Stats → character stat sheet
  - Testimonials → NPC dialogue
  - Pricing → shop
  - CTA → "CONTINUE?" or "PRESS START"
- **Two layout models** (choose per site):
  - **Side-scroller:** vertical scroll input drives horizontal camera travel through one long level. This is the Robby Leonardi interactive resume model, generally cited as the first publicly available "game resume" ([Play My Resume, Press Start journal](https://press-start.gla.ac.uk/press-start/article/view/317); [Kotaku](https://kotaku.com/a-resume-thatll-get-you-any-job-in-the-mushroom-kingdo-1453403102); live at rleonardi.com/interactive-resume, which had an expired TLS certificate when checked).
  - **Overworld map:** a top-down map where each section is a node. Scroll moves the player sprite along the path, and arriving at a node opens that "level" (an overlay or zoom-in).
- **Fixed HUD layer** carries persistent nav (world number, progress, CTA as a "coin counter").
- **Grid:** everything aligns to a base pixel unit (for example 4 CSS px = 1 art pixel), including text box padding and borders.

### 2.3 Signature interactions and scroll behaviour

**How scroll feels:** *quantised* and *responsive*, like a controller. One wheel notch is one step or one dialog advance. The camera moves in whole art-pixels, so you never see sub-pixel smoothness. Momentum does not carry: when you stop scrolling, the player stops (with an idle animation).

**What scroll drives:**
- **The player sprite walks** while scroll is active (walk cycle plays). It stops and idles when scroll stops, and walks backward (flipped sprite) when scrolling up. This one-to-one avatar mapping is the core feel.
- **Parallax** in 3 to 5 integer-speed layers (sky 0.1, mountains 0.25, hills 0.5, ground 1.0), snapped to whole pixels.
- **Dialog advancement:** at an NPC or sign, horizontal travel *locks* and further scroll notches advance the dialog page by page. Each page types out (about 30 to 50 chars/second) and a notch mid-typing completes the page instantly, which is standard game UX. When the dialog finishes, travel unlocks.
- **Item pickups = features.** Walking into a "?" block bumps it. The item pops out with an arc, lands, and the feature card appears as an "ITEM GET!" box with icon, name and description. The HUD counter increments.
- **Stats as HUD bars:** at a "stat sheet" checkpoint, bars fill in discrete segments (8 to 20 cells) with a tick sound and numbers counting in steps, like an RPG level-up screen ("SPEED ▮▮▮▮▮▮▯▯ 75").
- **Boss / level end = CTA.** A flagpole or a boss door. Reaching it shows "COURSE CLEAR!" with a score tally, then a "CONTINUE?" menu whose options are the CTAs, with a blinking cursor "▶".

**Headline arrival:** letter by letter, typed into a box. Alternatively the title logo drops from the top and bounces in 2 to 3 stepped frames, with "PRESS START" blinking at 1 Hz underneath. Never smooth fades.

**Section transitions:** mosaic pixelation (the screen down-samples to big blocks, the scene swaps, then it re-sharpens), iris wipe onto the player, or a Zelda-style full-screen pan. Codrops' grid-cell "pixel page transitions" (cells appearing and disappearing in patterns, inspired by Niccolò Miranda) are directly reusable ([Codrops: Ideas for Pixel Page Transitions](https://tympanus.net/codrops/2023/04/05/ideas-for-pixel-page-transitions/)).

**Hover / pointer:** menu items get a blinking "▶" cursor, the selected item inverts colours, and there is an 8-bit blip on focus. The pointer can be replaced by a pixel glove or sword cursor (keep the system cursor available). Keyboard is first-class: arrows move, Enter or Space advances dialog, and an on-screen "A" button prompt appears.

**CTA:** a game menu ("▶ START FREE TRIAL / VIEW PRICING / QUIT"), or a coin-insert gag ("INSERT COIN" counts credits). Pressing it plays a short "power-up" flash (palette cycling, not white flashes).

**Real-world references:**
- Robby Leonardi's interactive resume: the scroll-driven platformer (above). Its critics note a weaker second level and no link to an actual portfolio ([Kotaku](https://kotaku.com/a-resume-thatll-get-you-any-job-in-the-mushroom-kingdo-1453403102)). The lesson: game structure must still deliver the content.
- Awwwards elements: "Pixel walkers side-scroll navigation" for 5051 punk band ([Awwwards](https://www.awwwards.com/inspiration/pixel-walkers-side-scroll-navigation-5051-punk-band)), "Scroll gamification" for Escape the Kim ([Awwwards](https://www.awwwards.com/inspiration/poster-style-hero-section-escape-the-kim)), Stink Studios' Miu Miu pixel game ([Awwwards](https://www.awwwards.com/inspiration/pixel-art-game-miu-miu-fragrance)), and Akufen's Curious Critters game map ([Awwwards](https://www.awwwards.com/inspiration/curious-critters-maps)).
- NES.css, a pure-CSS 8-bit component framework covering buttons, dialogs, progress bars and icons ([nostalgic-css/NES.css](https://best-of-web.builder.io/library/nostalgic-css/NES.css)). It is a good component reference, but a cliché if used as-is.

### 2.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | A HUD strip: "WORLD 1-2 ★×3 ◉ 00450". Section links are level numbers. On mobile, a "START" pause menu overlay with a cursor list. |
| Buttons | Stepped-corner pixel borders (made with `box-shadow` stacks or `border-image`), a 2 art-px bottom-right shadow, and a pressed state that shifts 1 art-px down-right. A blip sound is optional, off by default. |
| Cards / features | "ITEM GET!" windows or inventory slots: icon sprite (16×16 or 32×32 scaled ×4), name in caps, flavour text. Unowned items appear as dark silhouettes until reached. |
| Stats | RPG stat sheet: segmented bars, numerals in a pixel font, "LV UP!" popups. |
| Timeline / steps | The overworld map path with level nodes; completed nodes get a flag. |
| Quote | NPC dialog box with portrait (customer avatar pixelated to 32×32), name tag, typewriter text and a ▼ advance arrow. |
| FAQ | An "?" NPC or menu: "ASK ABOUT... ▶ PRICING / ▶ PRIVACY". Selecting one opens a dialog box. |
| Footer | End credits roll (staff-roll style) plus "THANK YOU FOR PLAYING" and a high-score table (could be changelog or social proof). |
| Images | Product screenshots shown inside an in-world monitor or "TV" sprite, or pixelated with a hover/scroll "depixelate" to sharp. Real photos are dithered to the palette. |

### 2.5 Typography and colour

- **Fonts (Google):**
  - **Press Start 2P**: Namco-arcade bitmap, crisp at multiples of 8 px ([Google Fonts](https://fonts.google.com/specimen/Press+Start+2P/about)). Use only for headings and labels, all caps.
  - **Pixelify Sans**: 4 weights, readable smaller.
  - **Silkscreen**: tiny caps labels.
  - **VT323**: DEC terminal-derived mono, good for body text.
  - **DotGothic16**: Japanese-capable pixel gothic, for JRPG flavour.
  - **Jersey 10** or **Tiny5**: chunky HUD numerals.
  - Body copy longer than 2 lines should use VT323 or Pixelify Sans at 20 px or more, never Press Start 2P.
- **Palettes** (pick one *system* and stick to it):
  - **NES-ish:** `#000000`, `#FCFCFC`, `#F83800` (red), `#FCA044` (orange), `#00A800` (green), `#0058F8` (blue), `#3CBCFC` (sky), `#6844FC` (violet).
  - **PICO-8 (16):** `#000000 #1D2B53 #7E2553 #008751 #AB5236 #5F574F #C2C3C7 #FFF1E8 #FF004D #FFA300 #FFEC27 #00E436 #29ADFF #83769C #FF77A8 #FFCCAA`.
  - **Game Boy DMG (4):** `#0F380F #306230 #8BAC0F #9BBC0F`. This makes a strong one-colour brand mode.
  - JRPG window: gradient `#2038A8 → #081860` with a `#F8F8F8` 2-px border.

### 2.6 Implementation

- **Render at native resolution, scale by integers.** Use a 320×180 or 384×216 canvas scaled ×4/×5 with `image-rendering: pixelated` and `ctx.imageSmoothingEnabled = false` (reapply after resize). Snap camera and sprites to integers ([pixel-art rendering guide](https://app.cinevva.com/tutorials/pixel-art-rendering)).
- **Sprites in CSS:** `background-position` plus `animation: steps(N)` ([Treehouse: CSS sprite sheet animations with steps()](https://blog.teamtreehouse.com/css-Sprite-sheet-animations-steps?amp=1)).
- **Scroll mapping:** read `wheel`, `touchmove` and `scroll` deltas into an *accumulator*. Every N px of accumulation issues one "step" or "advance". Keep a real document height (for scrollbar, anchors and SEO) but drive the canvas from a quantised progress value. Throttle the visual update to the sprite frame rate (12 fps) while the camera updates at 60 fps in integer pixels.
- **Mosaic transition:** draw the scene to a tiny offscreen canvas (w/16), then upscale with smoothing off, and step the factor 16 → 8 → 4 → 2 → 1. Alternatively use the Codrops DOM grid of cells.
- **Text stays DOM.** Dialog boxes are real HTML laid over the canvas, so text is selectable, translatable and indexable.
- **Accessibility:**
  - Typewriter text: put the full line in a visually-hidden element or label, and set `aria-hidden` on the animated characters. Avoid streaming into `aria-live` regions, which announce fragments. Reserve the box height so the layout doesn't jump. Honour `prefers-reduced-motion` by showing the full text at once ([dev.to: the problem with the typewriter effect](https://dev.to/savvasstephnds/the-problem-with-the-typewriter-effect-and-how-to-fix-it-2731); [GitHub typing-effect element](https://github.com/github/typing-effect-element)).
  - Provide a "SKIP / READ AS PAGE" toggle that renders all levels as a plain, linear document.
  - Sound off by default, with a visible mute.
  - Blinking "PRESS START" at 1 to 2 Hz is fine (under 3 flashes/s). Pause it on reduced motion.
  - Press Start 2P at small sizes hurts readability. Enforce a minimum of 16 px and real body fonts.
  - Hijacking scroll is risky: don't block native scroll. Map it, and keep page-down, anchor links and keyboard working.

### 2.7 Anti-patterns

- **Cheap version:** a normal SaaS layout in Press Start 2P with pixel borders on cards. This is exactly the "CSS skin" failure.
- Mixed pixel scales (a 4× sprite next to a 3× sprite), sub-pixel blurry scaling, smooth easing on sprites, anti-aliased rotation of pixel art, gradient-heavy "pixel" art with 200 colours.
- Making visitors actually *play* (jump timing, fail states) to reach the content. The game metaphor should never gate information.
- **Same-as-Anime trap:** both can have dialog boxes and Japanese text. Pixel art is *quantised and turn-based* (steps, menus, cursor). Anime OP is *cinematic and continuous within cuts* (camera moves, smears, music-timed cuts). If the pixel site has cinematic camera zooms, or the anime site has menu cursors, they blur together.
- **Same-as-Neo-brutalism trap:** hard 2-px offset shadows on pixel buttons look neo-brutal. Keep pixel shadows *stepped* (staircase corners) and scale-locked to the art-pixel unit.

### 2.8 UX signature

**Scrolling is pressing the controller.** The site opens on a title screen with a blinking PRESS START. The first scroll notch walks a little sprite into World 1-1. Scroll down and it walks right, scroll up and it turns around, stop and it idles and taps its foot. Features pop out of "?" blocks as ITEM GET! cards. Testimonials are NPCs whose dialog boxes advance one scroll notch at a time. The stat sheet levels up in segmented bars. The CTA is a COURSE CLEAR tally ending in a CONTINUE? menu with a blinking cursor. Everything moves in whole pixels and stepped frames, and the visitor is *playing through* the product, not reading about it.

---

## 3. Blueprint (technical drawing)

### 3.1 Origin and defining aesthetic

Blueprints are cyanotype reproductions of engineering drawings: white lines on Prussian-blue paper, later replaced by diazo "whiteprints" (blue lines on white) ([Kittl: blueprint design](https://www.kittl.com/blogs/?p=14042)). The visual language comes from drafting standards (ISO 128 general presentation, ASME Y14.5 dimensioning, AS 1100) ([AS 1100.101](https://store.standards.org.au/product/as-1100-101-1992)):

1. **Title block** in the bottom-right corner: drawing title, drawing number (most emphasis), scale, sheet, drafter, date, plus a **revision block** that logs revision letter, change, date and approval ([Machine MFG: dimensioning best practices](https://shop.machinemfg.com/best-practices-for-dimensioning-and-engineering-drawings)).
2. **Dimension lines:** thin lines with arrowheads touching extension lines. Extension lines start with a small gap off the object and run about 3 mm past the arrow. Text reads from the bottom ([Pressbooks: welding drawing conventions](https://openwa.pressbooks.pub/welding1/?p=1572)).
3. **Leaders and callouts:** thin continuous leader lines ending in an *arrow* (pointing at an edge) or a *dot* (pointing at a face), plus balloon callouts with item numbers (same source).
4. **Section views:** a cutting plane A-A shown with a chain line and view arrows, ([Engineering drawing reference](https://www.scribd.com/document/49299652/Engineering-Drawing)), with the cut surface hatched at 45° (general knowledge).
5. **Line hierarchy:** thick visible edges, thin dimensions, dashed hidden lines, chain centre lines.
6. **Exploded views** and **bills of materials** (numbered balloons keyed to a parts table), plus **grid reference zones** (A to F / 1 to 8 around the border), crosshair registration marks and scale bars.

There is also a contemporary web cousin, the "Vercel aesthetic": a faint line or dot grid behind sections, sharp corners, shared borders, monospace labels and measurement annotations ([Setproduct: Blueprint grid design](https://www.setproduct.com/blog/complete-guide-to-blueprint-grid-design); [skills.sh blueprint-ui](https://www.skills.sh/superhq-ai/shuru/blueprint-ui)). That is *blueprint flavour*, not the full style.

### 3.2 Layout and information architecture

- **The site is one large drawing sheet** with a border, grid-reference zones and a title block. The visitor pans and zooms around it. Sections are *views on the sheet* (front elevation, section A-A, detail B at 4:1, exploded assembly, BOM) and not stacked bands.
- **Sheet border zones as nav:** the coordinates (A1, B3...) become anchor links ("see Detail C, zone D4").
- **The title block is the persistent footer/HUD.** It shows company name (drawing title), product (part number), "REV C" (version/changelog), "SCALE 1:1", "SHEET 2 OF 6" (scroll progress).
- **Hierarchy:** the object (product) is drawn in heavy lines. Annotations (copy) sit in thin lines at the periphery, connected by leaders. Copy lives *around* the drawing and points into it. It is not stacked under images.

### 3.3 Signature interactions and scroll behaviour

**How scroll feels:** precise, calm and linear, like a plotter pen. No bounce, no overshoot. The drawing progresses at constant speed proportional to scroll. Holding still leaves a half-drawn line exactly where it is, as if you could lift the pen.

**What scroll drives:**
- **The drawing draws itself.** The order follows drafting practice: construction lines (faint) → visible outline (heavy) → hidden lines (dashed) → centre lines → dimensions → leaders and notes → hatching → title block fields. This uses `stroke-dashoffset` scrubbing, the classic technique (Jake Archibald's method, used in [Codrops' SVG Drawing Animation](https://tympanus.net/codrops/2013/12/30/svg-drawing-animation/comment-page-1)). The *order* is the authenticity: real drafters lay out light construction lines first.
- **Dimensions measure the product's claims.** A dimension line extends between two extension lines, and its label counts to the value: "↔ 2.4 s faster", "⌀ 99.9% uptime", "R 12 integrations". **Stats are dimensions.** The number appears in the gap of the dimension line after both arrowheads land.
- **Callouts appear as leaders.** A leader shoots from a feature on the drawing to a margin note (dot terminator for surfaces, arrow for edges). The note types in mono caps. Features are a numbered balloon list (①②③) keyed to parts, which is exactly a BOM. Scrolling activates balloons in sequence, highlights the referenced part in accent colour and pans the camera to it.
- **Exploded view.** Pinned section: the assembled product (or UI stack) separates along its assembly axis with scroll, with dashed alignment/centre lines showing how the parts fit, and balloons attached to each part. Scrolling back reassembles it. This is the blueprint equivalent of the Apple AirPods Pro scroll-scrubbed sequence ([CSS-Tricks on the Apple scroll sequence technique](https://css-tricks.com/?p=308477)), done in vector line art.
- **Section cut.** A cutting-plane line A-A sweeps across the object, and the view rotates/reveals the hatched section to show "what's inside" (architecture, internals, how it works).
- **Camera:** the viewport is a camera on a large sheet. Scroll pans between views, with a zoom-in for "DETAIL B (4:1)", marked by a detail circle on the main view.

**Headline arrival:** lettered in. Characters stroke in as single-line (Hershey/engraving-style) vector text, as if lettered by a plotter or a drafter with a Leroy guide. Alternatively the headline is the drawing title in the title block, typed field by field. A faint guideline (lettering baseline) can be ruled first.

**Section transitions:** the camera pans across the sheet along grid lines. Or the sheet is "revised": a red revision cloud draws around the changed area, a revision triangle "△C" appears, and the revision table gains a row. That is a good way to present a changelog or "what's new".

**Hover / pointer:** a full-viewport crosshair cursor with live X/Y coordinate readouts on the rulers (as in CAD). Hovering a part highlights its outline, shows its dimensions and lights the matching BOM row, and vice versa. Measurement-on-hover between elements ("↔ 24 px") is a strong developer-tool trope.

**CTA:** "APPROVED FOR PRODUCTION". The CTA is the approval/signature field of the title block. Clicking stamps it (a red "APPROVED" stamp, the one non-blue colour) and/or downloads the "spec" (docs). A secondary CTA can be "REQUEST REVISION" (contact).

**References:**
- Awwwards "BLUEPRINT" scroll elements by EMME & CO (intro, timeline, horizontal scroll, parallax) ([Awwwards approach scroll](https://www.awwwards.com/inspiration/approach-scroll-blueprint-1); [scroll](https://www.awwwards.com/inspiration/scroll-blueprint-1)).
- Framer's DrawOnScroll component for per-path scroll drawing ([Framer marketplace](https://www.framer.com/marketplace/components/drawonscroll/)).
- Blueprint landing-page and design kits with navy grid, monospace labels and node diagrams with dashed connectors ([Kombai Meridian Blueprint](https://kombai.com/gallery/inspirations/meridian-blueprint/); [wrongstack tech-blueprint kit](https://cdn.jsdelivr.net/npm/@wrongstack/core@0.295.1/design-kits/tech-blueprint/KIT.md)).

### 3.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Sheet-zone index along the border (A to F, 1 to 8) plus a "SHEET n OF N" pager in the title block. Mobile: a drawing-list table (DWG NO / TITLE / REV). |
| Buttons | Rectangles with a 1-px line, corner tick marks (registration crop marks) and mono caps labels. Hover: dimension ticks extend out from the button to show its width, and the fill becomes a 45° hatch. No shadows. |
| Cards / features | BOM rows and balloon callouts. No floating cards. Panels share borders like a drawing's view frames. |
| Stats | Dimension lines with the value in the gap, tolerances as a subtitle ("±0.1 s", "p95"). |
| Timeline / steps | Revision table (REV / DESCRIPTION / DATE / BY) or assembly sequence ("STEP 1: INSERT A INTO B" with exploded sub-views). |
| Quote | A "NOTES:" block: "1. ALL CUSTOMERS REPORT ...", or a reviewer's markup in redline handwriting. |
| FAQ | "GENERAL NOTES" numbered list. Expanding draws a leader to the answer. |
| Footer | Full title block: company, address, "DO NOT SCALE DRAWING", copyright as "PROPRIETARY AND CONFIDENTIAL", a scale bar, a north arrow / projection symbol (first/third angle). |
| Images | Line-art renders (toon/edge-detected 3D renders), orthographic views, isometric. Photos only inside a "PHOTO REF" frame, duotone blue. |

### 3.5 Typography and colour

- **Lettering:**
  - **Mono and technical:** **IBM Plex Mono** 400/500, **JetBrains Mono**, **Space Mono**, **Share Tech Mono**, always caps with +0.05 to 0.1em tracking for labels.
  - **Condensed technical sans for titles:** **Barlow Condensed** 500/600, **Saira Condensed**.
  - **Hand-lettered drafting (accent only):** **Architects Daughter**.
  - SuperDesign's architectural system pairs Space Grotesk headings with JetBrains Mono labels ([SuperDesign](https://superdesign.dev/library/mosaic-grid-architecture-style)).
  - For self-drawing headlines, use single-stroke (Hershey) SVG fonts, because outline fonts draw as double lines.
- **Palettes:**
  - **Cyanotype:** paper `#1B4F8A` (or deeper Prussian `#0E3A6B`), lines `#E8F1FF`, construction lines `rgba(232,241,255,0.25)`, grid minor `rgba(255,255,255,0.06)`, major `rgba(255,255,255,0.14)`.
  - **Whiteprint/diazo:** paper `#F4F1E8`, ink `#1E3F73`, grid `#D6DDE8`.
  - **Redline accent** (revisions, approvals, CTA): `#E4572E`. Highlight cyan for the active part: `#7FE3FF`.
  - **Dark CAD mode:** `#0D1117` ground, `#58A6FF` lines, `#F0B429` dimensions.

### 3.6 Implementation

- **SVG is the native medium.** Normalise every stroke with `pathLength="1"` and scrub `stroke-dashoffset` from 1 to 0. This works with CSS scroll-driven animations (`animation-timeline: view()`) or GSAP ScrollTrigger (`scrub: true`, linear ease). Dashed hidden/centre lines can't use dasharray for both pattern and reveal at once: reveal them with a mask (a solid stroke drawn in a `<mask>`) over the dashed path ([GSAP forum on dashed paths](https://greensock.com/forums/topic/35819-gsap-drawsvg-on-scrolltrigger-with-stroke-dasharray/)).
- **Grid:** two `linear-gradient` background layers (minor and major), or an SVG `<pattern>`. Make the grid zoom with the camera.
- **Camera:** one big SVG sheet. Animate the `viewBox` or a wrapping `<g transform>` with scroll for pan/zoom between views. Vector stays crisp at any zoom.
- **Exploded view:** SVG groups translated along an axis. For 3D products, render line-art from Three.js with an edge/outline pass (`EdgesGeometry` or a Sobel post-process) on a blue background, and scrub camera and part offsets.
- **Performance:** hundreds of paths drawing at once is fine in SVG if you animate only `stroke-dashoffset` and `opacity`. Avoid filters on large SVGs. Pre-compute lengths at build time.
- **Accessibility:** thin 1-px lines in low-contrast blue fail as *information carriers*. Every dimension value and note must be real text with at least 4.5:1 contrast (`#E8F1FF` on `#1B4F8A` is about 7:1). Leaders are decorative (`aria-hidden`). Callout content is a real ordered list. Under reduced motion, render the completed drawing and fade annotation layers in. The crosshair cursor must not hide the system cursor for touch/keyboard users.

### 3.7 Anti-patterns

- **Cheap version:** a blue background with a CSS grid and a mono font, with normal fade-up sections. That is the "Vercel aesthetic" skin and not a drawing. Also: random measurement lines that don't measure anything, fake "schematic" circuit-board clip art, and graph-paper stock images.
- Drawing lines with easing (ease-out pens look like rubber bands), drawing everything at once, and outline fonts drawn as strokes (double-line letters).
- **Same-as-Bauhaus trap:** both are diagrammatic and geometric. Blueprint is *monochrome, line-only, orthographic and annotated*. Bauhaus is *flat colour fills and asymmetric composition*. No colour fills in blueprint except the hatch.
- **Same-as-Pixel trap:** grid plus mono plus HUD-like title block can feel like a game HUD. Keep blueprint *vector-crisp and linear* (no steps, no sprites) and use drafting vocabulary, not game vocabulary.

### 3.8 UX signature

**You watch the product being engineered on one living drawing sheet.** As you scroll, a plotter pen at constant speed lays down faint construction lines, then heavy outlines, then dimensions whose numbers are the product's claims ("↔ 2.4 s faster"). Leaders shoot out to numbered callouts that form the feature list. Then the assembly separates into an exploded view, parts balloon-numbered against a bill of materials. The title block in the corner keeps count ("SHEET 3 OF 6, REV C"). The finale is an "APPROVED" stamp on the signature field. The feeling is *precision and proof*: the product is not shown, it is specified, and the drawing completes itself in exact step with your scroll.

---

## 4. Art deco

### 4.1 Origin and defining aesthetic

Art deco (roughly 1920 to 1940, named after the 1925 Paris *Exposition internationale des arts décoratifs*) fused machine-age geometry with luxury. It is visible in the Chrysler Building's stepped, sunburst crown, in cinema palaces and ocean liners, and in A. M. Cassandre's posters (*Étoile du Nord*, *Nord Express*, *Normandie*). Cassandre made stylised airbrushed imagery and the type designs Bifur (1929, extreme thick/thin), Acier Noir (1935) and Peignot (1937) ([Artyfactory: Cassandre](https://artyfactory.com/graphic_design/graphic_designers/cassandre.htm); [Sessions College: Cassandre's art deco type](https://www.sessions.edu/notes-on-design/type-in-history-cassandres-art-deco/)).

**Visual signatures:**
1. **Strict bilateral symmetry** and a dominant central axis ([Made Good Designs: art deco graphic design](https://madegooddesigns.com/art-deco-graphic-design/)).
2. **Sunbursts and fans:** radiating lines from a central point, perhaps the single most iconic deco motif (same source).
3. **Stepped / ziggurat silhouettes** (setback skyscrapers, stepped frames), chevrons and zigzags in stacked bands.
4. **Metallic line-work:** thin gold or chrome inlines, double and triple pinstripe borders, corner ornaments.
5. **Tall geometric capitals** with high contrast or hairline strokes, widely tracked.
6. **Theatrical grammar:** proscenium arches, velvet curtains, cinema marquees with chasing bulbs, spotlights, the Gatsby party.

### 4.2 Layout and information architecture

- **Centre-axis layout.** Every section is symmetric about the vertical centre. Content lives in a central column framed by ornamental borders. Two-column features come as *mirrored pairs* (left and right equal).
- **The frame is the layout.** Each section sits inside a stepped/chamfered frame with a double gold rule, like a poster or elevator door. Corner ornaments anchor it.
- **IA as a programme / evening:** Overture (hero) → Act I, II, III (features) → Intermission (quote or stats) → Finale (CTA) → Credits (footer). Alternatively a hotel or building metaphor: lobby → floors (the elevator dial indicates section) → penthouse (CTA).
- **Vertical rhythm emphasises height:** tall narrow columns, vertical fluting lines, setback stepping as sections narrow towards the CTA (a ziggurat page silhouette).

### 4.3 Signature interactions and scroll behaviour

**How scroll feels:** stately, glamorous and *choreographed*. Movements are slow (600 to 1200 ms equivalents), eased with sine curves, and always symmetric: what happens on the left happens mirrored on the right. Think of a Busby Berkeley overhead shot, an elevator rising past floors, or theatre curtains parting. Never snappy, never bouncy.

**What scroll drives:**
- **Curtain reveal (the overture).** Scroll parts a pair of curtain panels (velvet with gold fringe, or geometric gold-lacquer doors like elevator doors) from the centre line to reveal the hero. A proscenium arch frames the stage. A spotlight cone sweeps once.
- **Sunburst fan-outs.** At each section's start, rays radiate from a central point (behind the headline or the product) and *fan open* with scroll, like a fan or a sunrise. The rays are spokes of a wheel that rotate slowly with scroll position, never randomly.
- **Symmetric fan-out of features.** Features are dealt from the centre outward in mirrored pairs (feature 1 left and feature 2 right arrive together, sliding outward from behind a central medallion). Cards can open like a fan or a hand of cards pivoting from a bottom-centre point.
- **Stepped / ziggurat reveals.** Content blocks unveil in tiers from the centre up or down (each tier a setback), like a skyscraper being built floor by floor.
- **Elevator indicator.** A semicircular dial with an arrow needle (a 1930s elevator floor indicator) sweeps as you scroll between sections. This is the persistent progress/nav element, and few devices are more deco.
- **Marquee lights.** A cinema marquee with chasing bulbs frames a headline or stat. The bulbs chase as you scroll (scroll velocity drives chase speed) and light up fully on arrival.

**Headline arrival:** letters rise symmetrically from the centre letter outwards, or a gold inline traces around each glyph and then the fill gilds in (a gradient sweep, a "gilding" shimmer passing once). Display caps with wide tracking. A chevron or rule extends from both sides of the headline simultaneously.

**Stats:** presented as *marquee billing* ("NOW SHOWING: 12,000 TEAMS"), or as numerals in sunburst medallions, or as stepped bar ziggurats where taller tiers mean bigger numbers. Numbers tick like a split-flap or odometer with ease-in-out, and a final gold shimmer settles each one.

**Feature list:** a symmetric triptych or mirrored pairs in arched frames (doors / niches). Each frame's arch draws in gold line, then an icon set in a geometric medallion appears.

**Section transitions:** iris and doors. Curtains close and reopen. Elevator doors close at the end of a floor and open on the next. A sunburst wipe radiates from centre. Chevron bands slide horizontally in opposite directions (left band and right band meet at centre).

**Hover / pointer:** gold shimmer (a light sweep across metallic line-work, following pointer X), an inline brightening, a fan unfolding slightly. Buttons glow like marquee bulbs. Pointer parallax is allowed, but it must be *mirrored* for symmetric elements.

**CTA:** the grand finale. Curtains close behind a spotlit CTA, marquee bulbs at full brightness, a ticket-stub or invitation-card shape ("ADMIT ONE", "YOU ARE CORDIALLY INVITED"). The button is framed by a stepped gold border and the sunburst rays converge on it.

**References:**
- Doof! Media's "Art Deco Hero Section" on Awwwards ([Awwwards](https://www.awwwards.com/inspiration/art-deco-hero-section-doof-media)).
- Poklonnaya 9, a Moscow residential project with an art-deco-inspired facade, has an award-winning site ([Videinfra case](https://videinfra.com/work/poklonnaya-9)).
- Codrops' CSS-only marquee and glowing text marquee techniques ([CSS-only marquee](https://tympanus.net/codrops/?p=48796); [Glowing text marquee](https://tympanus.net/codrops/tag/marquee/)). A CSS string-of-bulbs pen ([CodePen kupietz](https://codepen.io/kupietz/pen/dPbNywN)) is adaptable to chasing marquee bulbs.

### 4.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Centred, symmetric: logo medallion in the centre, links split evenly left and right, separated by small diamonds (◆). Or an elevator floor dial. |
| Buttons | Stepped/chamfered rectangles (cut corners via `clip-path`) with a double gold border, caps text with wide tracking. Hover: gold light sweep. Primary CTA: ticket-stub shape with notched sides. |
| Cards / features | Arched or stepped frames (the shape of an elevator door or a cinema niche), fan-pleat headers, corner ornaments. Arranged in mirrored pairs or triptychs. |
| Stats | Marquee billing boards with bulbs, sunburst medallions, split-flap counters. |
| Timeline / steps | A vertical fluted column or skyscraper: each step a floor, ascending. Or a programme ("ACT I · ACT II"). |
| Quote | Framed in a medallion or proscenium. Large stylised quotation marks as fan shapes. Attribution in small caps between two short gold rules. |
| FAQ | "PROGRAMME NOTES": accordion rows separated by chevron rules. Opening unfolds like a fan (scaleY from the centre). |
| Footer | Theatre credits / building cornerstone: symmetric, centred, sunburst crown, "EST. 2024" in Roman-numeral style. |
| Images | Cut into arches, octagons or stepped frames. Duotone black and gold or sepia. Product renders lit dramatically on black with a single spotlight. |

### 4.5 Typography and colour

- **Display:**
  - **Limelight**: high-contrast deco geometric, theatre/Hollywood connotation ([Fine Print School on Limelight](https://www.fineprintschool.com/free-fonts/limelight)).
  - **Poiret One**: hairline geometric deco, for large signage only ([Google Fonts](https://fonts.google.com/specimen/Poiret+One/about)).
  - **Federo**: classic deco caps.
  - **Monoton**: multi-inline neon/marquee, for one word at a time.
  - **Italiana** or **Marcellus**: refined classical caps.
- **Text:** **Josefin Sans** 300 to 600 (geometric 1920s sans with tiny x-height, works for body), or **Marcellus** for serif body ([Made Good Designs: best art deco fonts](https://madegooddesigns.com/best-art-deco-fonts/)). Deco faces want ALL CAPS with wide tracking (0.15 to 0.35em) at large sizes.
- **Palette:**
  - Onyx `#0B0B0C`, gold `#C9A227` (highlight `#E9D18B`, shadow `#8A6D1C`), champagne `#EDE1C3`, ivory `#F6F0E1`
  - Emerald `#0F5E4E`, peacock teal `#114B5F`, oxblood `#5C1A1B`, chrome `#BFC5CC`
  - Gold as text on black passes (about 8:1). Gold on ivory does not: use onyx text on ivory.

### 4.6 Implementation

- **Curtains / doors:** two pinned panels with `transform: translateX(∓n%)` scrubbed by scroll, or `clip-path: inset()` from centre. Velvet folds can be an SVG `feTurbulence` pattern or a pre-rendered texture with a subtle `background-position` shift for swaying.
- **Sunbursts:** an SVG with N rays (`<path>` wedges) generated programmatically. Fan-open via `rotate` and `scale` per ray with a staggered timeline, or a `conic-gradient(from …, gold 0 2deg, transparent 2deg 10deg)` repeated, revealed by a radial mask.
- **Gold:** don't use flat yellow. Use a multi-stop linear gradient (`#8A6D1C → #E9D18B → #C9A227 → #8A6D1C`) via `background-clip: text` or SVG `linearGradient`. Animate `background-position` for the shimmer. Keep shimmer to a single pass per reveal.
- **Marquee bulbs:** a grid of round elements with staggered `animation-delay` (custom property per index) driving brightness and `box-shadow` glow. Chase speed is bound to scroll velocity via a CSS variable.
- **Symmetry enforcement:** author one side and mirror it with `transform: scaleX(-1)` on a duplicated subtree, so choreography is truly symmetric.
- **Performance:** glow `box-shadow` on many bulbs is expensive. Use pre-rendered radial-gradient bulb images, or a canvas for 100+ bulbs. Avoid large animated `filter: blur`.
- **Accessibility:** hairline Poiret One at small sizes is illegible: minimum 32 px, display only. Chasing bulbs: keep each bulb's on/off rate low, and since the chase is a *moving* pattern, pause it on `prefers-reduced-motion` and after 5 s of no scroll (WCAG 2.2.2 pause/stop for auto-moving content). Curtains must not trap content: the hero copy is in the DOM and readable without the curtain animation.

### 4.7 Anti-patterns

- **Cheap version:** a black-and-gold "luxury" template (Playfair Display, gold gradients everywhere, soft glows) with no symmetry, no geometry and generic fade-ups. Also: Gatsby clip-art (feathers, champagne), overused gold-glitter textures, Great Gatsby film fonts copied wholesale.
- Over-ornamenting every element. Deco works with one dominant motif, a tight palette and confident symmetry (Made Good Designs, above).
- Bouncy or springy easing (anachronistic and cheap). Asymmetric choreography.
- **Same-as-Bauhaus trap:** both are geometric 1920s modernisms. Deco is *symmetric, ornamental, metallic and theatrical*. Bauhaus is *asymmetric, unornamented, flat primaries*. Deco reveals from the *centre*, Bauhaus composes from the *edges and diagonals*.
- **Same-as-Anime trap:** a curtain reveal and a title-card reveal are both "big reveals". Deco is *slow and continuous with eased doors*. Anime is *hard cuts with impact*. Never hard-cut in deco.

### 4.8 UX signature

**You attend an opening night.** Scrolling parts a pair of gold-lacquered doors on the central axis to reveal a spotlit headline under a fanning sunburst. Every section after that unfolds *symmetrically from the centre*: features dealt in mirrored pairs, stats billed on a marquee with chasing bulbs, an elevator dial in the nav sweeping floor by floor as you rise through the building. The motion is slow, eased and ceremonial, and each scene ends with doors closing and reopening on the next. The finale is a spotlit "ADMIT ONE" invitation CTA where the sunburst rays converge. The feeling is *occasion and glamour*: the visitor is a guest being shown in, not a user being shown features.

---

## 5. Neo-brutalism

### 5.1 Origin and defining aesthetic

Web brutalism (around 2014 onward, catalogued on brutalistwebsites.com by Pascal Deville) celebrated rawness. Neo-brutalism (also "neubrutalism", around 2020 to 2023) keeps the exposed structure and hard edges but applies them with intent: friendly, colourful and highly usable ([uxdesign.cc: Neubrutalism is taking over the web](https://uxdesign.cc/neubrutalism-is-taking-over-the-web-e9d09e0fe441); [Made Good Designs: neobrutalism](https://madegooddesigns.com/neobrutalism-web-design/)). The flagship is **Gumroad's 2021 relaunch** under Sahil Lavingia: cream background, hot pink, thin-to-thick black outlines, and hard 4 px offset shadows with zero blur on every card, button and badge, intended to feel approachable for first-time creators ([webdesignhot Gumroad design.md](https://www.webdesignhot.com/design.md/gumroad/)). That source notes the live homepage may no longer serve shadows. Figma's web presence, Readymag and Goodkids are other cited examples ([Rometheme: Neubrutalism trend](https://rometheme.net/neubrutalism-trend-in-website/)).

**Visual signatures:**
1. **Hard offset shadows,** 0 blur, often black and sometimes coloured. They read like stacked paper cut-outs, not material elevation ([theplusaddons: neo-brutalism](https://theplusaddons.com/blog/neo-brutalism-web-design/)).
2. **Thick black borders** (2 to 5 px) on everything.
3. **Flat, clashing saturated fills:** pink, yellow, lime, violet, coral on cream or white. No gradients.
4. **Stickers and badges:** rotated pills, starbursts ("NEW!", "50% OFF"), emoji-scale illustrations, hand-drawn doodles and arrows.
5. **Marquee bands:** full-width tilted strips of repeating text.
6. **Oversized grotesque type** and raw layout: visible grids, overlapping blocks, deliberate misalignment.

### 5.2 Layout and information architecture

- **Pinboard / desk metaphor.** Sections are surfaces onto which blocks, stickers, notes and windows are *placed*: slightly rotated (±1° to 4°), overlapping, layered. Order is clear but placement feels hand-made.
- **Bento grids with thick gutters**, each cell a different colour, outlined, shadowed.
- **Windowed UI** (fake OS windows with title bars and traffic-light buttons) as containers is a common sub-motif.
- **Marquee bands as section dividers.** Rotated -2° to 3°, crossing each other in an X at hero or CTA.
- **IA is direct and loud:** big claims, short copy, lots of social proof (sticker testimonials), pricing as tear-off tickets.

### 5.3 Signature interactions and scroll behaviour

**How scroll feels:** *tactile and physical*, events and not scrubs. Elements don't glide in proportion to scroll. They *slap* onto the surface when you cross a threshold (a fast drop with a spring overshoot and a tiny settle rotation), like stickers on a laptop or a deck of cards dealt on a table. Scrolling back doesn't reverse them neatly: they stay where they landed. The page *accumulates*.

**What scroll drives:**
- **Sticker slaps.** Cards and badges enter from above or the side with scale 1.2 → 0.96 → 1 and rotation randomised in a seeded range, landing with a shadow that grows from 0 to the full offset at impact. That is the "contact" moment and the signature micro-interaction.
- **Marquee bands driven by scroll velocity.** Bands run at a base speed, scroll velocity speeds them up, and scroll direction reverses them. Two bands crossing in opposite directions.
- **Stacking decks.** Feature cards pile on top of each other in a pinned section (each new one slaps on top, slightly offset and rotated), building a physical stack that becomes the "feature list". The previous cards remain visible underneath.
- **Draggable everything.** Stickers, cards and the hero's illustration pieces can be grabbed and thrown (pointer drag with inertia and bounds). This turns "browsing" into "fiddling" and is the clearest UX difference from the other styles.
- **Pop-up windows.** Sections open as fake OS windows that appear with a hard pop (scale from 0.9, no fade), and can be closed or dragged.

**Headline arrival:** words drop in as separate blocks, each on its own highlight block (yellow marker rectangle behind the word that slaps in first), or the headline is already there and a hand-drawn underline or circle doodle scribbles on with scroll. A starburst sticker slaps onto the headline's corner last ("NEW!").

**Stats:** big numbers on coloured blocks with hard shadows. Charts as chunky outlined bar blocks. The "counting" happens as a *flip* (stepped jump to the final number with a bounce), not a smooth odometer. Stats can be stickers ("10K+ creators" as a rotated badge).

**Feature list:** a bento grid of outlined coloured tiles that slap in staggered (left to right, 60 to 90 ms apart). Each tile's icon is a chunky illustration. On hover a tile lifts (shadow grows) and slightly rotates.

**Section transitions:** no fancy transitions. Hard edges between full-bleed coloured sections, a marquee band crossing the boundary, or the next section's background slapping in as a block sliding over the previous one with a hard border.

**Hover / pointer:** the canonical neo-brutal button. Hover: translate (-2px, -2px) and shadow grows from 4 to 6 px. Active: translate (4px, 4px) and shadow drops to 0, so the button is physically "pressed into" the page ([theplusaddons](https://theplusaddons.com/blog/neo-brutalism-web-design/); [21st.dev Brutal Button](https://21st.dev/@radiumcoders/components/brutal-button.md)). A custom cursor as a chunky arrow or emoji sticker is common. Stickers wiggle on hover.

**CTA:** a huge, physical button you want to press, often with a hand-drawn arrow pointing at it ("click me →"), crossed marquee bands behind it, and a confetti or sticker burst on click (flat shapes, no glow).

**References:**
- Gumroad (gumroad.com, check the current state; see the caveat above).
- Figma, Readymag, Goodkids, Pizza Pizza ([Rometheme](https://rometheme.net/neubrutalism-trend-in-website/)).
- neobrutalism.dev, a shadcn-based React/Tailwind component set including Marquee and Image Card. Its maintenance status is unclear ([neobrutalism.dev docs](https://www.neobrutalism.dev/docs)).
- brutalistwebsites.com as the historical catalogue.

### 5.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | A thick-bordered bar (or floating pill) with hard shadow. Links as outlined chips. The active chip is filled with a colour. Mobile menu slides down as a block with a hard bottom border. |
| Buttons | 3 px black border, flat colour fill, 4 px hard black offset shadow, 4 to 8 px radius or square. Hover lifts, active presses (shadow to 0). |
| Cards / features | Coloured tiles, black border, hard shadow, slight rotation. Bento grid. Window chrome optional. |
| Stats | Big numbers on colour blocks, sticker badges, chunky outlined bar charts. |
| Timeline / steps | Numbered stickers (big circled numerals) connected by a hand-drawn dashed arrow. Steps slap in sequentially. |
| Quote | Testimonial "stickers" or tweet-style cards scattered at angles, with avatar in a thick-bordered circle. Draggable. |
| FAQ | Outlined accordion blocks. Open state changes fill colour and the "+" becomes "−" with a hard snap. The open panel has its own shadow. |
| Footer | A giant wordmark (viewport-wide), marquee band, link columns in outlined boxes, a sticker ("made with ♥"). |
| Images | Product screenshots in thick-bordered frames with hard shadows, often in fake browser/OS windows. Cut-out photos with white sticker borders (`drop-shadow` outline), doodles drawn over. |

### 5.5 Typography and colour

- **Fonts:**
  - **Display:** **Archivo Black**, **Bricolage Grotesque** 700 to 800, **Space Grotesk** 700, **Lexend Mega** (wide), **Rubik Mono One** for stickers.
  - **Body:** **Space Grotesk** 400/500, **Public Sans**, **DM Sans**.
  - **Hand-drawn accents:** **Gochi Hand** or **Caveat**, sparingly.
  - Mixed case, tight tracking on display (-0.03em), big sizes (clamp up to 9 to 12 vw).
- **Palette:**
  - Cream `#FFF4E0` (or paper white `#FFFDF7`), ink `#000000`
  - Hot pink `#FF90E8` (Gumroad-like), yellow `#FFC900`, lime `#B8FF5C`, violet `#A388EE`, coral `#FF7A5C`, sky `#7FD3FF`, teal `#23A094`
  - Black-on-colour pairings pass AAA comfortably. One source reports black on white at 21:1 ([theplusaddons](https://theplusaddons.com/blog/neo-brutalism-web-design/)).

### 5.6 Implementation

- **Shadows:** `box-shadow: 4px 4px 0 0 #000` (no blur). For sticker outlines on cut-out images: `filter: drop-shadow(3px 0 0 #fff) drop-shadow(-3px 0 0 #fff) drop-shadow(0 3px 0 #fff) drop-shadow(0 -3px 0 #fff) drop-shadow(4px 4px 0 #000)`. That is expensive, so pre-bake for many stickers.
- **Slap-in:** IntersectionObserver or ScrollTrigger `onEnter` fires a spring animation, not a scrubbed tween. Use Motion One or GSAP with an `elastic.out(1, 0.6)`/`back.out(2)` ease, around 350 to 450 ms. Seed rotations per element from its ID so layout is deterministic between visits.
- **Drag:** Pointer Events with `setPointerCapture`, velocity tracking, a simple inertia and bounds clamp (GSAP Draggable plus InertiaPlugin, or about 60 lines of custom code). Persist positions in `sessionStorage` for fun.
- **Marquee:** duplicated content with `translateX(-50%)` keyframes. Tie `animation-duration` or a `playbackRate` (Web Animations API) to scroll velocity, and flip `animation-direction` on scroll up ([Codrops CSS-only marquee](https://tympanus.net/codrops/?p=48796)).
- **Performance:** cheap overall (DOM, transforms). Watch `drop-shadow` filter stacks and too many simultaneous springs. Cap them.
- **Accessibility:**
  - High contrast is a strength.
  - Rotated text should stay under about 5° for body copy.
  - Draggable items must not be the only way to read content, and need keyboard alternatives (focusable, arrow keys nudge) or must be purely decorative.
  - Marquees must pause on hover/focus and under reduced motion (WCAG 2.2.2), and repeated marquee text should be `aria-hidden` except for one copy.
  - Under reduced motion, slaps become instant placement (no overshoot).

### 5.7 Anti-patterns

- **Cheap version:** adding `border: 2px solid black; box-shadow: 4px 4px 0 black` to an otherwise standard SaaS template. This is the most cloned look of 2022 to 2023 and reads as a Tailwind theme, not an identity. Also: blurred shadows, gradients, too many colours at once (more than 4 accents), and stickers as decoration with no message.
- Ugly-as-excuse: tiny low-contrast text or broken layout called "brutalist".
- **Same-as-Pixel trap:** hard shadows plus chunky UI plus bright colours can look like pixel UI. Neo-brutal has *smooth vectors, springy physics and rotations*. Pixel has *stepped corners, stepped frames, no rotation*.
- **Same-as-Bauhaus trap:** see 1.7. Neo-brutal is *borders, shadows, mess and play*. Bauhaus is *pure composition*.

### 5.8 UX signature

**The page is a desk you fill up and can mess with.** Every scroll threshold slaps something onto the surface with a satisfying thunk: a feature tile dropping into the bento grid, a testimonial sticker landing at a jaunty angle, a "NEW!" starburst whacking onto the headline corner. Things stay where they land, so the page *accumulates* into a collage. Marquee bands speed up and reverse with your scroll. Anything can be grabbed and flung, and every button physically sinks into the page when pressed. The feeling is *tactile irreverence*: it's the only style where the visitor is invited to rearrange the site.

---

## 6. 2D anime intro (anime TV opening, "OP")

### 6.1 Origin and defining aesthetic

The TV anime OP is a roughly 89-second (1:30) music-video sequence synced to the theme song. It introduces characters, teases the arc and carries staff credits, and is often directed by specialist storyboarders. Shingo Yamashita, for example, directed and storyboarded the openings for *Jujutsu Kaisen* OP1 and *Chainsaw Man* ("KICK BACK", a dense homage to films like *Pulp Fiction* and *Reservoir Dogs*, which passed 100 million YouTube views) ([Anime Corner: Chainsaw Man OP references](https://animecorner.me/chainsaw-man-opening-references-a-bunch-of-classic-movies/); [Anime Corner: 100M views](https://animecorner.me/chainsaw-man-opening-surpasses-100-million-views-on-youtube/)). Other canonical references:

- **Cowboy Bebop** ("Tank!"): erratic flashes on a black-and-white canvas synced to horns and drums, flat pink/blue/yellow/green panels behind black silhouettes, free-form kinetic text ([Art of the Title](https://www.artofthetitle.com/title/cowboy-bebop/)).
- **Neon Genesis Evangelion:** Hideaki Anno's choice of Matisse EB, an extra-bold Mincho serif, cropped and compressed for title cards, gave the series a consistent typographic identity from title cards to NERV interfaces ([Fonts In Use](https://fontsinuse.com/uses/28760/neon-genesis-evangelion); [Fontworks interview](https://route2015.otakumode.com/interview/01/2/)).
- **Kill la Kill** (Trigger, Imaishi): screen-filling Raglan Punch kanji telops, with impact prioritised over legibility ([Fontworks column](https://en.fontworks.co.jp/column/393/)).
- The **Tokyo Ravens** OP bookends its title card with a sliding cast split-screen and a punch at the camera, and borrows Utena's half-second "flash of something cool" cuts ([Animetics](https://animetics.net/tag/anime-openings/)).

**Visual signatures (the grammar):**
1. **Cold open / pre-title hook:** a silent beat or single held image, then the music hits.
2. **Title card smash:** the logo slams in on a musical accent with a flash, a shake and debris. It is often bookended by strong shots.
3. **Speed lines and focus lines** (radial *shūchūsen*, linear *ryūsen*) behind characters in motion.
4. **Impact frames:** 1 to 3 frames of stylised, often monochrome or colour-inverted imagery at a hit. Usually built from layered effects: darkened background, flash frame, linear or radial lines, glow and inversion. Popularised by Yutaka Nakamura's work (*Cowboy Bebop*, *One Punch Man*, *My Hero Academia*) ([80.lv: impact frames](https://80.lv/articles/learn-how-to-add-accents-to-your-animations-with-impact-frames); [Know Your Meme](https://knowyourmeme.com/memes/cultures/impact-frames)).
5. **Character cut-ins and "vs" splits:** diagonal split-screens, eyes-only close-up strips, a sliding cast line-up.
6. **Sakuga flourishes:** a burst of fluid, smeared, high-frame-count animation within otherwise limited animation (on twos or threes).
7. **Freeze frames with captions:** a held pose with a giant kanji/katakana caption or name card (character name in Latin and Japanese).
8. **Credits text:** staff names in small, neat type, placed in negative space and timed to cuts.
9. **Beat-synced cuts:** cuts on the downbeat, with faster cutting in the chorus.
10. **Eyecatch:** a 2 to 6 second card at the ad break with the logo and a character illustration, made by the production itself ([Wikipedia: Bumper / eyecatch](https://en.wikipedia.org/wiki/Bumper_(broadcasting)); [AnimeNation: purpose of eyecatches](https://www.animenation.net/blog/?p=368)).
11. **Colour flashes:** full-frame flat colour on accents. The **ending pose** is a group shot / final pose on the last chord, then a hard cut to black.

Persona 5's UI is the game-world translation of this grammar: black/red/white, angular text boxes, "explosive snap-shift" transitions and character pose animations per menu item. Atlus's director says readability needed a lot of iteration ([Prototypr: video game UX awards](https://blog.prototypr.io/the-video-game-user-experience-awards-9d63afda9f5c); [Kotaku on Hashino](https://kotaku.com/-metaphor-refantazio-persona-5-menu-ui-hashino-1851667088)). It is the best existing reference for "anime OP energy as interactive UI".

### 6.2 Layout and information architecture

- **The site is the OP, and the OP is a storyboard.** IA maps to an OP's structure (roughly the TV-size song's sections):

| OP beat | Site section | Content |
|---|---|---|
| Cold open (0 to 5 s) | Hero preload | Single held image, silence, one line of text |
| Intro hit / **title card smash** | Hero | Product logo slams in |
| Verse A: character intros | Features | Each feature = a "character" with name card, cut-in and freeze-frame caption |
| Pre-chorus: build-up | How it works | Faster cuts, rising tension, speed lines |
| Chorus: sakuga action | The money shot / demo | The product in action: big motion sequence, impact frames on key claims |
| **Eyecatch** | Mid-page breather | Logo card plus mascot, a stats or quote "intermission" |
| Bridge: quiet moment | Testimonial / story | Slow pan, single character, soft colour |
| Final chorus plus **ending pose** | CTA | Full cast line-up, logo, CTA |
| Credits overlay throughout | Footer and microcopy | Small staff-credit-style text in corners |

- **Frame composition = 16:9 shots.** Sections are full-viewport *shots*, never scrolling ribbons. Inside a shot, the *camera* moves (pan, zoom, truck), not the page.
- **Persistent HUD-less frame:** no visible scrollbar feel. An optional timecode or "EP. 01" counter and a subtle song-section label ("CHORUS") can serve as progress.

### 6.3 Signature interactions and scroll behaviour

**How scroll feels:** you are *scrubbing the OP's timeline*. Scroll position is the playhead, and the site is cut on a beat grid. Within a shot, motion is continuous and scrubbed (pans, zooms, a character's run cycle). Between shots there is a **hard cut**: no crossfade, no slide. Crossing a cut boundary changes the shot on a single frame, often with a 1 to 2 frame flash or impact frame. Some boundaries are **holds**: scroll keeps moving but the image freezes (freeze-frame with caption) for a defined scroll distance, giving rhythm. Scroll *feels* like editing.

**What scroll drives:**
- **Beat grid.** The author defines a BPM (or simply N cuts). The engine places cut points at equal scroll intervals (for example every 60 vh = 1 bar) and snaps to them gently (`scroll-snap` proximity or programmatic settle), so the visitor always rests on a composed frame, never between shots. Optional music (muted by default, user opt-in) is then *seeked* by scroll position. Opt-in audio makes the site feel like the real thing.
- **Cold open → title smash.** First screen is a held still with one line ("Every hero starts somewhere."). The first scroll notch triggers the smash: logo scales from 3× to 1× in about 2 frames with ease-out-expo, screen shake (8 to 12 px, decaying over 6 frames), radial focus lines burst, debris shards fly. The flash is a *single* low-luminance colour frame, not white strobing (see accessibility).
- **Speed-line transitions.** Between features, linear speed lines streak across the frame in the direction of the next shot's motion, a character or product "whooshes" through, and hard cut.
- **Character cut-ins / "vs" splits.** Comparisons (us vs them, before vs after) are a diagonal split-screen: two panels slam in from opposite corners, a "VS" glyph impacts the seam with focus lines. Or three eye-strip cut-ins stack horizontally to introduce a team or integrations.
- **Freeze-frame captions.** At each feature's climax, the image freezes (desaturates slightly, a halftone or paper-texture overlay appears) and a giant vertical katakana/kanji caption plus a Latin name card slams in: "機能 01 / AUTOSYNC". This is the anime equivalent of a feature card, and the hold lasts for a defined scroll distance.
- **Sakuga burst.** The chorus section is one long pinned shot with an elaborate scrubbed animation sequence (sprite sheet, video frames on canvas or a Lottie/Rive animation), drawn on 2s mostly and on 1s for the climax. This is where the product demo becomes a *fight scene*.
- **Eyecatch card.** Halfway down, a self-contained card (logo plus mascot illustration plus a small tagline, often with a "jingle" sting if audio is on) appears as a hold. Before it is "A-part", after it is "B-part". This gives the page an act break.
- **Credits.** Staff-credit-style microcopy (small type, neat columns) appears in negative space and changes with each cut: "Design: ___ / Engine: ___", or customer logos credited as "In association with". Classy, and very OP.
- **Ending pose.** The CTA section is the final group shot: all features/characters line up (cast line-up slide), the logo returns, the last impact, and the CTA button sits in the composition. Then a cut to black with a small "To be continued →" or "NEXT EPISODE" link (secondary CTA: docs or blog).

**Headline arrival:** slam. Either a whole-word scale-down from huge with an impact frame, or a stacked Evangelion-style title card: heavy Mincho, compressed and cropped, mixed sizes, white on black, held for a beat. Japanese and English headline pairs are characteristic (katakana or kanji large, English small, or vice versa).

**Stats:** delivered as *power levels* or "damage numbers". A number smashes in with focus lines and a shake, possibly counting up rapidly on 2s (stepped) and slamming to the final value with an impact frame. Or as a vertical name-card freeze-frame: "稼働率 99.99% UPTIME".

**Feature list:** a *cast introduction*. Each feature has a shot: an action pose (product UI or mascot), a name card slide-in (diagonal colour band with the name), a freeze caption, then a hard cut to the next. Three to six features fit an OP's verse naturally.

**Section transitions:** hard cuts, smash cuts, speed-line whips, colour-flash cuts (one frame of flat brand colour), a diagonal wipe (Persona-like slanted panels), iris-out to the eyecatch. Never fade-up.

**Hover / pointer:** subtle in-frame: hovering a character or feature triggers a micro cut-in (eyes strip), a 2-frame "shine" glint (the classic sparkle on a blade or glasses), or a slanted highlight panel snapping in behind the item (Persona 5 menu style). Buttons have an angular slanted shape with a quick ink-smear on hover.

**CTA:** the *ending pose*. Cast line-up, logo, the CTA in an angular red panel. Clicking triggers one final impact frame (non-flashing variant) and the "next episode" card. Persona 5's "explosive snap-shift" is the reference for click feedback.

**References:**
- Persona 5 menus (above).
- Awwwards "website opening animation" for L'Étude, tagged jump cut and motion design ([Awwwards](https://www.awwwards.com/inspiration/l-etude-website-opening-animation-letude)).
- Official anime sites are usually static key-visual portals. The opportunity here is precisely that few websites have adopted *OP editing grammar* as scroll behaviour. Fan GSAP projects show the demand ([dev.to: interactive One Piece site with GSAP](https://dev.to/bharath_d_2005/bring-anime-to-life-on-the-web-how-i-built-an-interactive-one-piece-website-with-gsap-7a0)).
- Manga effect-line generators and shaders for speed and focus lines ([Uhiyama Lab Effect Line Maker](https://uhiyama-lab.com/en/tools/effect-line-maker/); [Godot speedlines shader](https://godotshaders.com/shader/speedlines-manga-style/)).

### 6.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Minimal during the "OP": a small corner logo plus "EP.01" timecode. Opening the menu is a Persona-style slanted panel slam with an angular item list, the selected item enlarged with a colour flash and a character pose. |
| Buttons | Slanted parallelograms (`skewX(-12deg)` with counter-skewed text) or angular clip-path shapes. Bold Japanese plus English label. Hover: ink-smear sweep and glint. Press: 2-frame impact (scale 0.94, shake 2 px). |
| Cards / features | "Name cards": diagonal colour band, huge vertical kanji/katakana, Latin name, small descriptor. Shown as freeze-frames, not grid cards. |
| Stats | Power-level slams with focus lines. Vertical stat captions. |
| Timeline / steps | Episode list ("EP.01 SETUP / EP.02 CONNECT / EP.03 LAUNCH") or a storyboard strip (numbered panels, "C-012" cut numbers). |
| Quote | The bridge: a soft, slow, quiet shot (sky, wind, petals) with the quote as subtitle-style text (white, outlined) at the bottom of frame. Its contrast with the loud sections is the point. |
| FAQ | "Next episode preview" style: each question is an episode title; or a character dialogue exchange with portrait cut-ins. |
| Footer | **Credits roll**: staff-credit typesetting (role in small caps, name in larger weight, two columns), studio logo, "© 2026 ___ / Production Committee" pastiche. Ending card. |
| Images | Cel-shaded (2 to 3 tone) illustrations or UI screenshots composited with speed lines, halftone and paper texture. Product renders with a toon shader and an ink outline. |

### 6.5 Typography and colour

- **Japanese-capable fonts (Google):**
  - **Dela Gothic One**: ultra-heavy gothic for title smashes and kanji captions.
  - **Shippori Mincho B1** 800 or **Zen Antique**: heavy Mincho for Evangelion-style title cards, compress via `transform: scaleX(.8)` or set huge and crop.
  - **Mochiy Pop One**: casual round gothic based on handwriting by young Japanese women, meant for manga, magazines and signs. Good for comedic or slice-of-life OPs and mascots ([Google Fonts](https://fonts.google.com/specimen/Mochiy+Pop+One/about)).
  - **M PLUS 1** / **M PLUS Rounded 1c**: 7 weights, Thin to Black, for credits and body ([Google Fonts](https://fonts.google.com/specimen/M+PLUS+Rounded+1c/about)).
  - **RocknRoll One**, **Reggae One**, **Rampart One**: novelty title options. **DotGothic16**: for a retro OP.
- **Latin pairing:** **Anton** or **Bebas Neue** (condensed caps for name cards), **Inter Tight** or **M PLUS 1** for credits. Avoid **Bangers** (Western comic, not anime).
- **Case and setting:** vertical Japanese (`writing-mode: vertical-rl`) for captions, English caps tracked wide for credits, mixed sizes in title cards.
- **Palettes** (OPs have a *per-show* palette, so let the brand pick one of these):
  - **Shōnen action:** ink `#0A0A12`, white `#FFFFFF`, signal red `#E60033`, electric yellow `#FFE600`, sky `#2FA4FF`.
  - **Persona-like:** black `#000000`, red `#D7000F`, white `#FFFFFF`.
  - **Bebop pop panels:** `#F25C9A` pink, `#2D6CDF` blue, `#F7D23E` yellow, `#3BB273` green, silhouettes `#111111`.
  - **Slice-of-life / sakura:** `#FFF7F2` cream, `#F7A8C4` sakura, `#9AD0EC` sky, `#6B5B95` cel-shadow lavender.
  - **Impact-frame mode:** pure black/white inversion plus one accent at most.

### 6.6 Implementation

- **Timeline engine:** a master GSAP timeline (or a custom one) with labelled cuts. Scroll maps to timeline progress with `scrub` (`scrub: true` within shots). Cuts are implemented as `set()` calls at labels (instant property changes), not tweens. Holds are timeline gaps with no change. Snap to labels with ScrollTrigger `snap: { snapTo: 'labelsDirectional', duration: 0.2 }`.
- **Compositing layer:** a full-screen canvas (2D or WebGL) for speed lines, focus lines, debris, halftone and screen shake. DOM layer above for real text (titles, captions, credits).
  - **Speed lines:** procedurally drawn wedges from a focal point with per-frame jitter on 2s (redraw every other frame for that hand-drawn "boil").
  - **Shake:** translate the composited stage with decaying noise.
  - **Impact frame:** a CSS `filter: invert(1) contrast(2)` or a shader threshold on the shot layer for 2 frames.
- **Sakuga sequences:** image sequence on canvas scrubbed by scroll (the AirPods technique, [CSS-Tricks](https://css-tricks.com/?p=308477)), Rive or Lottie with scroll-bound playhead, or WebM/AV1 video with `currentTime` seeking (keyframe-dense encoding needed). Animate on 2s by quantising the playhead to 12 fps for authenticity.
- **Audio (optional):** Web Audio with the track's `currentTime` mapped to scroll progress when the user opts in. Plus stings on cuts. Never autoplay.
- **Performance:** preload the next 2 shots' assets. Decode image sequences in a worker (`createImageBitmap`). Cap canvas DPR at 2. Kill the effects layer when off-screen.
- **Accessibility and photosensitivity (critical):**
  - **WCAG 2.3.1:** no more than three flashes in any one-second period unless below the general and red flash thresholds. Saturated red flashing has a stricter test ([W3C Understanding 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)). The 1997 *Pokémon* "Dennou Senshi Porygon" broadcast, with rapid red/blue alternation, sent hundreds of Japanese viewers to hospital and led Japanese broadcasters to adopt flash guidelines (general knowledge).
  - Engine rules for impact frames and colour flashes:
    1. Hard limit of **at most 1 flash event per 1 s of scroll-time and never more than 3/s**, enforced by the engine even if the visitor scrolls fast (debounce cuts' flash effects by wall-clock time, not scroll position).
    2. Flash frames use **reduced luminance change** (for example invert to dark grey `#222`, not white), with flash area limited.
    3. **No saturated red full-frame flashes.**
    4. Inversion impact frames are **opt-in "full intensity" mode**. The default is a "safe impact": shake plus focus lines plus scale, with no luminance flip.
    5. `prefers-reduced-motion`: disable shake, flashes and speed-line animation. Cuts become instant still frames, and the site reads as a storyboard/manga page sequence. That is still on-style.
  - Also: real text for all captions (Japanese captions get `lang="ja"` and an English equivalent), a skip-intro control on the cold open, keyboard navigation between cuts (arrow or Page keys move one cut), and contrast for credits over imagery (outline or text-shadow, at least 4.5:1).

### 6.7 Anti-patterns

- **Cheap version:** an anime girl illustration as a hero image plus a Japanese font plus sakura petals falling, on a normal scroll page. Also: Bangers or comic-book fonts, Google-translated nonsense kanji (have every Japanese string checked by a speaker; meaningless kanji is the most common and most embarrassing failure), excessive white strobing, fading between every section (anime cuts), constant shake (impact only means something if rare).
- Copying real show logos, characters or OP storyboards shot-for-shot (IP and taste issues). Pastiche the *grammar*, not the property.
- **Same-as-Pixel trap:** see 2.7. Anime = *cinematic camera plus cuts plus music time*. Pixel = *turn-based steps plus menus*.
- **Same-as-Neo-brutalism trap:** both "slam" things in. The neo-brutal slap is a *physical object landing* that stays and accumulates. The anime smash is a *camera event* (shake, lines, flash) inside a shot that is **replaced by the next cut**. Anime never accumulates; it edits.
- **Same-as-Art-deco trap:** title reveals in both. Deco = *slow, centred, eased doors*. Anime = *instant, off-centre, diagonal, with impact*.

### 6.8 UX signature

**Your scroll wheel is the playhead of a 90-second anime opening.** The page opens on a silent held frame. The first notch drops the beat: the product's title smashes onto the screen with focus lines and a shake. From then on the site *cuts* and never slides: each feature is a character introduced in a hard cut, a speed-line whip, a freeze-frame with a giant vertical katakana name card. A diagonal "VS" split pits before against after. The chorus is one long scrubbed sakuga sequence of the product in action. An eyecatch card marks the halfway point. Everything ends on the full-cast ending pose with the CTA and a "NEXT EPISODE" card, while staff-credit microcopy ticks by in the corners. The feeling is *hype and momentum*: the visitor is not reading a page, they are *editing a trailer* with their thumb, cut by cut, on the beat.

---

## Contrast table: six UX signatures

| | **Bauhaus** | **Pixel art** | **Blueprint** | **Art deco** | **Neo-brutalism** | **Anime OP** |
|---|---|---|---|---|---|---|
| **Metaphor** | A poster being composed | A game being played | A drawing being drafted | An opening night | A desk being cluttered | A trailer being edited |
| **One scroll notch =** | Moves shapes toward the next composed state | One step / one dialog page | Pen advances along the drawing | Curtain or doors open a little further | Crosses a threshold, and something slaps down | Playhead advances; may cross a hard cut |
| **Time feel** | Continuous, snaps to designed states | Quantised steps, 12 fps sprites | Continuous, linear, constant speed | Slow, eased, ceremonial | Event bursts with spring overshoot | Continuous within shots, hard cuts between, freeze holds |
| **Spatial logic** | Fixed frame, asymmetric diagonals, rotation | Side-scroll level or overworld map, integer pixels | Camera pans and zooms over one big sheet | Mirror symmetry about the centre axis | Free placement, rotation, overlap; draggable | 16:9 shots with camera moves inside |
| **Persistence** | Same shapes persist and change role | Player avatar persists; HUD accumulates score | Drawing accumulates to completion | Scenes replace each other via doors/curtains | Objects accumulate and stay where they land | Nothing persists; each cut replaces the last |
| **Headline arrives by** | Blocks sliding along grid axes and locking to bars | Typewriter in a dialog box / logo bounce | Single-stroke lettering plotted in | Symmetric rise plus gold gilding sweep | Words slapped on marker blocks, sticker last | Title-card smash with focus lines and shake |
| **Stats as** | Geometric diagrams (wedges, bars) | Segmented HUD / RPG stat bars | Dimension lines with values in the gap | Marquee billing, split-flap counters | Big numbers on shadowed blocks, sticker badges | Power-level slams, vertical name-card captions |
| **Feature list as** | Primitives that grow to dominate the poster | Items from "?" blocks: ITEM GET! | Numbered balloons keyed to a BOM | Mirrored pairs fanning out from centre | Bento tiles slapping in, stacking decks | Cast intro: cut-in, name card, freeze-frame |
| **Section transition** | Giant primitive wipe | Mosaic / iris / screen flip | Camera pan along the sheet; revision cloud | Curtains / elevator doors | Hard colour block plus marquee band | Hard cut, speed-line whip, colour-flash cut |
| **Pointer** | Rigid 90° rotations, grid-unit slides | Blinking ▶ cursor, inverted selection | CAD crosshair with coordinates, hover dimensions | Gold shimmer sweep, mirrored parallax | Grab and fling; buttons press into page | Glint, slanted highlight panel, micro cut-in |
| **CTA** | The poster resolves into an arrow at the button | COURSE CLEAR → CONTINUE? menu | APPROVED stamp in the title block | Spotlit ADMIT ONE invitation | Huge pressable button, hand-drawn arrow | Ending pose plus NEXT EPISODE card |
| **Signature curve** | `power2.inOut` plus slight overshoot | `steps(n)` | `linear` | `sine.inOut` (long) | `back.out` / spring | Instant `set()` cuts plus `expo.out` within shots |
| **Main a11y risk** | Yellow text contrast; rotated text order | Pixel font legibility; scroll hijack; typewriter for screen readers | Thin low-contrast lines carrying info | Hairline fonts; auto-moving bulbs | Drag-only content; endless marquees | **Photosensitive flashes (WCAG 2.3.1)**; shake |
| **Reduced-motion fallback** | Static poster per state | Plain linear "read as page" mode | Completed drawing with annotation fades | Doors open; static symmetric layout | Instant placement, paused marquees | Storyboard/manga page sequence of still frames |

**Rule for the engine:** each style must implement its own row from *"One scroll notch ="* to *"CTA"*. A style that shares any three of those cells with another style is a reskin and should fail review.
