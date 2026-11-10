> Style research from DesignAI by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. Licensed under the GNU AGPL-3.0 with additional terms (NOTICE.md): credit it with this notice, unchanged, wherever it is used, and don't present it as your own work.

# DesignAI style research: styles 30 and 31

**Paint on glass, Multiplane**

Prepared 2026-10-19 for the DesignAI engine, as part of the animation-technique batch (styles 22 to 33). The question is the one the earlier research asked: **what does one notch of the scroll wheel mean here?** Paint-on-glass is one picture that is never cut, only reworked: every frame is the last frame with some paint moved, and nothing can be un-painted. The multiplane camera is a stack of painted glass sheets at measured distances under one lens, where the only controls are how far down the camera is and where it is focused. In both, the visitor's scroll is given the technique's own control. Fonts and colours come after.

> **How to read the citations.** URLs are inline. Where a claim comes from general knowledge and not from a source I retrieved, I say "(general knowledge)". Where I only saw a search engine's excerpt of a page (the page itself refused to load), I say "(search snippet)". Where sources disagree I say so and give both. Treat named works as references to check.

---

## Cross-cutting principle: two more scroll models

| Style | What scroll *is* | Time quantisation | Motion curve | Spatial axis | Primary renderer |
|---|---|---|---|---|---|
| Paint on glass | The painter's hand. Scroll distance is how many brush strokes are laid toward the next picture; stop and the painting stops half reworked | None: strokes come as fast as you scroll, a few dozen a frame at most; a slow boil of tiny strokes runs when it settles | Coarse strokes first, fine last (a painter's order); each stroke starts in the old paint and drags it into the new colour | One flat pane lit from behind; the words lie on the glass in front of it | One 2D canvas under the page; strokes are drawn bristle by bristle |
| Multiplane | The crank of the camera stand: how far the lens has run down through the stack, and where it is focused | None: continuous, with a hold while a section is read | Camera trucks in with a plateau at each section; focus follows with a lag (the pull) | The real depth axis: every plate and every plane of words at a distance from the lens; things grow by 1/distance | DOM planes (text) and painted canvases, all `transform`/`opacity` on the compositor |

The table matters because the batch is crowded. `sand` also makes one picture on a light table and reworks it by hand; the difference is in what the hand can do (here: colour, wet paint dragged along a stroke, wet-on-wet, never a density field of grains) and in what scroll is (distance travelled, not a sweep per scene). `pop-up-book` and `paper-cut-out` have depth, but as one physical object with a hinge; the multiplane has a lens and distances. The existing `parallax` scene (one photo, a depth map, a 2.5D move) and the generic "parallax page" are named and ruled out in section 2.7.

---

## 1. Paint on glass

### 1.1 Origin and defining aesthetic

Paint-on-glass animation uses "slow-drying oil paints on sheets of glass", moved frame by frame; gouache mixed with glycerine is sometimes used instead ([Wikipedia: Paint-on-glass animation](https://en.wikipedia.org/wiki/Paint-on-glass_animation)). Aleksandr Petrov is the best-known practitioner and has used it in seven films, all award-winning; Caroline Leaf's *The Street* (1976), Witold Giersz, Georges Schwizgebel, Vladimir Samsonov, Natalya Orlova, Wendy Tilby, Martine Chartrand and Karel Zeman are on the same list (same page).

Petrov's *The Old Man and the Sea* (1999) was painted from March 1997 to April 1999: more than 29,000 frames, about 20 minutes, in pastel oils on glass, with his fingertips and brushes, on several sheets of glass at different levels, each coated with slow-drying paint and each about four times the size of an A4 canvas; after every frame he slightly modified the painting for the next. The camera was a specially built motion-control rig carrying an IMAX camera ([Wikipedia: The Old Man and the Sea](https://en.wikipedia.org/wiki/The_Old_Man_and_the_Sea_(1999_film)); [Wikipedia: Petrov](https://en.wikipedia.org/wiki/Aleksandr_Petrov_(animator)); [Open Culture](https://www.openculture.com/2024/08/hemingways-the-old-man-and-the-sea-painted-on-29000-frames-of-glass.html) for the slow-drying oils and the fingers). It won the 2000 Academy Award for Best Animated Short Film and the Annecy Grand Prix (Wikipedia, same page). Searching for a lightbox I found only that producers and interviewers describe the glass as "lit from behind" or backlit (search snippet); the Wikipedia articles do not mention it, so treat backlighting as widely reported, not confirmed in a primary source. One search result called the reworking a "palimpsest" (search snippet).

*Loving Vincent* (2017) is the same principle in another medium: 65,000 frames, each an oil painting on canvas, by 125 painters from over 20 countries, about six years. Actors were filmed against green screen, edited as live action, then every frame was shot onto a blank canvas and painted over; the painters painted over each frame after photographing it, **so only about 1,000 of the 65,000 paintings survived** ([Wikipedia: Loving Vincent](https://en.wikipedia.org/wiki/Loving_Vincent)). That fact is the design rule for this style: paint cannot be un-painted, only painted over.

Caroline Leaf's NFB description for *The Street* has her working "directly under the camera, adding and subtracting paint over a glass surface"; another source lists her paint-on-glass work as watercolour and gouache finger-painting (search snippets: [Wikipedia: Leaf](https://en.wikipedia.org/wiki/Caroline_Leaf)). Georges Schwizgebel is a neighbour more than a member: sources disagree on his medium (acrylic on celluloid per a Swiss Films essay, "impasto" per Donald Crafton, oil on glass only by a blog's guess), but agree that metamorphosis is his basic form and that he avoids cuts so the picture keeps flowing, with up to four years for a six-minute film ([Swiss Films essay](https://www.swissfilms.ch/upload/media/legacy/2723/5566_Schwizgebel_en.pdf), [Crafton](https://voices.uchicago.edu/massculture/2017/10/08/october-13-2017-donald-crafton); search snippets).

**Visual signatures:**
1. **One picture, never cut.** Scenes morph into each other because the same paint is moved (general knowledge from the films above; the Wikipedia page for *The Old Man and the Sea* describes dreams and memories but not the morphing itself).
2. **Visible hand.** Fingertips and brushes leave strokes and ridges; **impasto** is paint thick enough that "brush or knife strokes remain visible" and the raised paint "catches light" ([Wikipedia: Impasto](https://en.wikipedia.org/wiki/Impasto)).
3. **Wet-on-wet.** New paint laid into paint that is still wet, finished before the first layers dry ([Wikipedia: Alla prima](https://en.wikipedia.org/wiki/Alla_prima)).
4. **Wiping out.** Scratching or wiping through the paint to show what is beneath it is **sgraffito**, "scratching through a top layer to expose a contrasting layer" ([Wikipedia: Sgraffito](https://en.wikipedia.org/wiki/Sgraffito)); on lit glass what shows beneath is light (general knowledge).
5. **Luminous colour.** Because the glass is lit from behind the paint glows (reported, see above).
6. **Boil.** Every frame repainted by hand makes the brushwork shimmer; *Loving Vincent* is the best-known case (general knowledge).

### 1.2 Layout and information architecture

- **The site is one pane.** A fixed canvas under every section holds the painting; the page's words lie on the glass in front of it as ordinary HTML. The canvas is the only picture; nothing is a background image per section.
- **A section is made of beats.** A beat is a section, or one item of a list (each feature, each timeline step, each question). A beat has a painting it wants to be; the runtime knows each beat's place on the page.
- **The painting is composed around the words.** The measured box of a beat's copy gets a quiet, darker ground in the painting, and the luminous place (the sun, the window glow, the eye of a swirl) goes to the side where the words are not. Hero, intro and so on alternate sides, so the light moves across the page.
- **The colour script.** Disney and Pixar plan a film's colour in a "colour script" (general knowledge); the page has one: a palette per beat that moves from dusk through night toward a new dawn, anchored on the site's own accent hue, so the painting belongs to the brand. A rail of swatches down the left edge is that script; the active swatch is wet and glossy; clicking one scrolls to the scene.
- **Reading order** is the document's: title, body, buttons.

### 1.3 Signature interactions and scroll behaviour

**How scroll feels:** you are moving the painter's hand across a picture that cannot go back. The page has not "scrolled the next picture in"; the paint is being pushed into it.

**What scroll drives:**
- **Strokes, by scroll distance.** Each beat has an anchor; the stretch of scroll between two anchors is the stretch in which the brush works (the first and last sixth of it hold, so a beat rests). Within it, how many of the transition's strokes have been laid is a smooth function of how far you have gone. On desktop a transition is 520 strokes (260 on a phone), at most about 26 laid per frame (11 on a phone); a long jump (a nav link) lays them as fast as the cap allows and then finishes the picture.
- **Coarse to fine.** Stroke 1 is wide (12 per cent of the screen's short side) and long, stroke 520 is about 7 px: the order a painter works in, and the order Hertzmann's painterly rendering uses (a large-brush sketch first, then smaller brushes only where the picture still differs from the source: [Hertzmann, SIGGRAPH 98](https://mrl.cs.nyu.edu/publications/painterly98/)).
- **Where the picture disagrees.** Each stroke starts at the worst of eight random cells: the place where what is on the glass differs most from what it is becoming. So the picture converges without a plan, and a smear or a half-finished transition is repaired where it is worst.
- **Wet paint carried.** A stroke starts in the colour that is already there and runs into the new colour (a gradient along the stroke), so the old picture is dragged, not faded. Direction follows the picture: along the iso-luminance edges where they are strong, along a flow field (a swirl round the light, vertical in forest, flat in sea) where they are not (after Hertzmann's strokes that follow image gradients; Litwinowicz's impressionist filter does the same for video: [SIGGRAPH 97](https://history.siggraph.org/?p=117290)).
- **No rewind.** Scrolling back does not undo strokes. The page heads for the earlier beat and lays new strokes toward it, counted from the moment you turned round; at the beat the picture is again fully painted, but not the same strokes. This is the *Loving Vincent* fact above, kept: only the last painting exists.
- **Stop and it stops.** Halfway through a transition the glass shows a half-reworked picture, held. It is the one place the page looks unfinished, and it is the point.
- **Settling and the boil.** When it arrives, the brush finishes what it missed and stops. After that, two tiny strokes every third of a second keep the surface alive (a repainted frame's shimmer) at the colour already under them, so a smear you made does not slowly disappear.

**Headline arrival:** brushed in: a sweep with a wet edge crosses the headline left to right once, when the beat first comes to rest (a mask gradient, one element). Body copy and buttons rise a little behind it.

**Stats:** figures in the display italic, very large, with **runs of paint** (drips) hanging under each one, slowly growing and falling away in a loop.

**Feature list:** one beat per feature, with the numeral in amber glow (a long tag such as "Light jet" becomes a small label instead); the painting changes between them (the light slides along the horizon and the clouds are repainted while the landscape stays), so a list is the picture being worked on for a while, not a deck of slides.

**Section transition:** the repainting is the transition: nothing is cut or crossfaded. A different landscape (sea, hills, swirl, village, forest, field) is the target of each section; between two such sections the old landscape is dragged away into the new one.

**Hover / pointer:** **a finger in the wet paint.** Moving the pointer drags what is under it: the canvas is copied onto itself shifted by the move through a soft circle, so the real brushwork and colour are pushed along and left as a smudge. The smudge stays until a later stroke paints over it. Pressing makes the finger bigger. On touch, a drag that stays a drag smears; one the browser takes as a scroll is a scroll (nothing here uses `touch-action` or stops default scrolling), so scrolling is the main gesture on a phone and a tap or short drag is the finger.

**CTA:** the final painting at its most luminous; the button is a blob of fresh paint with a wet highlight that squashes when hovered.

**Real-world references:** I found no scroll site that repaints one picture into the next by strokes. What exists are brush **reveals**: Framer's "Brush+" uses brush textures as masks painted along preset paths, "Paint Reveal" uses brush strokes that fade, "Fluid Reveal WebGL" follows the cursor with a simulated fluid (search snippets: [Brush](https://www.framer.com/marketplace/components/brush/), [Paint Reveal](https://www.framer.com/marketplace/components/paint-reveal/), [Fluid Reveal](https://www.framer.com/marketplace/components/fluid-reveal-webgl/)). They uncover an existing image through a mask; they do not rework it. Curtis et al.'s computer-generated watercolour models glazes with a shallow-water simulation ([SIGGRAPH 97](https://grail.cs.washington.edu/projects/watercolor/)); I did not use a fluid solver because a smudge by self-copy reads the same at pointer speed and costs nothing.

### 1.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | A wordmark in italic, links in mono caps, the call to action as a daub of amber paint (an irregular blob radius). A fixed rail of swatches, one per scene, is the contents; on a phone it is a thin strip along the top edge. A small counter at the foot counts strokes and says `wet` while paint is moving and `set` when it has stopped |
| Hero | The painting is the hero. The headline is set very large and brushed in; the lede and buttons rise behind it. If the hero has a picture, **the painting is made from it**: the picture is the target the brush paints toward, so it reads as a painted copy of the photo; a phone device stays real beside the words |
| Buttons | Daubs: irregular rounded shapes with a wet highlight; the primary is amber paint, the rest a dark glass outline |
| Intro | Kicker in mono, headline brushed in, lede below |
| Features | One beat per item (above) |
| Product | Words one side, the real phone on the other (never painted); tags as small daubs; a supplied product picture is painted like the hero |
| Stats | Large figures with runs of paint |
| Timeline | A title card at the foot of the painting per step: the `when` in a small mono slate, the title, the note; one beat each |
| Quote | The saying large and italic over a swirl; the attribution is a painter's signature with a brushed underline |
| FAQ | A title beat, then one question per beat; the answer lies in a **wiped window**: a torn-edged patch of cream glass (sgraffito: the paint wiped away to the light) that is itself swept open with a ragged edge when the beat arrives. Native `<details>`, open |
| CTA | The giant headline and the paint-blob button |
| Gallery, strip, orbit | Slides of glass (a thin lit border, the picture, a caption); a roll of plates; daubs round a gold hub |
| Scenes (films) | Untouched: the scene's stage sits over the pane |
| Footer | Mono, on the glass |

### 1.5 Typography and colour

- **Display:** **Fraunces** (Google Fonts) at `SOFT` 100 and `WONK` 1, weight 500: soft, wonky terminals that survive being brushed in. Large sizes use the optical-size axis.
- **Body:** **Newsreader**, a reading serif with optical size.
- **Marginalia:** **IBM Plex Mono** for kickers, the stroke counter and slates.
- **Palette:** pane black-blue `#0b0e16`, cream ink `#f3e7d1`, amber `#e69a3c` (the site's accent), cold `#4fa7b8`. The painting's own colours come from the colour script (above): sky, a glow in the accent hue, far/mid/near planes, deep shadow. Hues are mixed along the shorter way round the wheel: a plain lerp between an orange and a blue passes through green, which I found out by building it.

### 1.6 Implementation

- **One canvas, 2D.** `runtime/src/styles/paint-on-glass.ts`. Device pixel ratio capped at 1.5 (1.25 on a phone). No WebGL: strokes are filled polygons and thin lines, one fixed canvas.
- **The brush** (`_brush.ts`): a stroke is a ribbon along a Catmull-Rom path, full at the start (brush pressed), swelling then thinning, with a ragged edge; a gradient from the old colour to the new; two to four bristle streaks along it (lighter on the side the light falls on, darker on the other, so strokes read as raised ridges: impasto); at the tail the paint breaks into separate bristle lines. Roughly six canvas calls per stroke.
- **The targets** (`_pg-scenes.ts`): a few hundred cells across (5 to 6 px), composed from the palette with gradients, a luminous glow, ridges from value noise, stars and clouds; six landscapes, or the supplied picture drawn cover-fit and deepened according to its mean brightness. A quiet ground under the measured copy box keeps the words legible.
- **Two grids.** A colour map of what is on the glass (`cur`) and of what it is becoming (`tgt`), both at cell resolution. Strokes read `cur` for the old colour and error, `tgt` for the new colour and direction, and write their colour into `cur`.
- **The phase.** Beat centres on the page give a scroll position a fractional beat index; the plateau at each end (a smoothstep between 0.16 and 0.84 of the way) is what makes a beat rest. The brush's heading (which beat it paints toward) changes when the direction of travel changes; progress is counted from where you turned.
- **The smudge.** The canvas is drawn onto itself, offset by the pointer's move, through two soft circular clips (alpha 0.62 and 0.5); the colour map's cells are moved the same way.
- **Frame cost.** Measured headless Chrome with the GPU, 1440 x 900: 60 fps while scrolling at about 110 px per step; a 4x CPU-throttled 390 px phone viewport: median 16.7 ms, one frame over 33 ms in a full scroll of a 22-beat page. (The test machine's GPU was shared.)
- **Accessibility:** all words are real text in reading order; the canvas is `aria-hidden`; the swatch rail has labels; native FAQ; no flashing: the boil changes colour by at most 3.5 per cent in two strokes a third of a second.
- **Reduced motion:** the painter's hand is not moving: each beat's finished painting is laid in one step when it comes into view, no boil, no smear, no reveals. Still the same pictures. **Without JavaScript:** a dark pane with two pools of colour per section behind ordinary copy; the supplied picture shows as a dim plate.

### 1.7 Anti-patterns

- **A canvas of generative noise behind a normal page.** If scroll does not move paint, it is a wallpaper.
- **A crossfade between two pictures.** The old colour has to travel (be dragged) into the new.
- **A mask reveal dressed as paint.** Reveals uncover; this reworks. No stroke here hides a finished image under it that has been there all along.
- **Pretending scroll back rewinds.** Rewinding the paint is the one thing the medium cannot do (only about 1,000 of *Loving Vincent*'s 65,000 canvases survived).
- **Same-as-sand trap:** sand is a density field of grains on a light table, monochrome amber, shaped by a hand that sweeps once per scene (clearing, pouring, carving). Here the material is coloured oil paint, the unit is a stroke that carries colour, scroll is distance travelled (any amount, either way), and the pointer drags paint instead of making furrows.
- **Same-as-rotoscope trap:** rotoscope develops a live film into ink; here nothing is live and nothing is traced.
- **Text that boils.** The boil is in the paint only.

### 1.8 UX signature

**You are working a wet painting with your hand.** The page is one oil painting on a pane lit from behind, painted under your scroll: each notch lays strokes that start in the old colour and drag it into the next scene, coarse brush first, always where the picture is furthest wrong. Stop and it stops half done; scroll back and it paints toward the earlier scene with new strokes, because paint cannot be un-painted. When it arrives the surface keeps shimmering with tiny repainted strokes, and your pointer is a finger that smears it.

---

## 2. Multiplane

### 2.1 Origin and defining aesthetic

Lotte Reiniger and Carl Koch built an early multiplane camera for *The Adventures of Prince Achmed* (1926): multiple glass layers under a fixed overhead camera (design from 1923). Berthold Bartosch used a similar setup for *L'Idée* (1932). In 1933 Ub Iwerks built a more advanced one, partly from salvaged Chevrolet parts, for Iwerks Studio ([Wikipedia: Multiplane camera](https://en.wikipedia.org/wiki/Multiplane_camera); the D23 entry also says Iwerks built a horizontal one at his own studio: [D23](https://d23.com/a-to-z/multiplane-camera)). William Garity developed Disney's, completed in early 1937 and tested on the Silly Symphony *The Old Mill*, which won the 1937 Academy Award for Animated Short Film. It used **up to seven layers of oil-painted glass** under a vertical, movable camera, in Technicolor, and "a camera crew of up to a dozen technicians might be required to operate and advance each of the planes" (Wikipedia). D23 says the vertical stand held **up to six background layers**; sources differ on six or seven, depending on whether the character plane is counted (I give both). Garity's team received a Scientific and Technical Academy Award (D23).

The Walt Disney Family Museum quotes Disney's aim as more depth and a less flat look: turn a painting "into several planes" and move the camera through them. The vertical version stood over a dozen feet tall, with the camera at the top and layers at different heights under it. For *Pinocchio* the Red Lobster Inn interior in sequence seven used **as many as nine levels at once**; the shot ran about 16 seconds on screen, used roughly 23 feet of film and a crew of five took 46 consecutive hours to shoot it. For "Goes to School" Garity built a **horizontal** version with a plane across a whole room, five large glass paintings in mechanical frames, lit from all sides, the camera moving through one frame at a time, at $45,000 one of the most expensive single shots in animation then ([Walt Disney Family Museum](https://www.waltdisney.org/blog/machine-imagination-walt-disneys-pinocchio-and-multiplane-camera)). It was used in *Pinocchio*, *Fantasia*, *Bambi* and *Sleeping Beauty* among others; *The Fox and the Hound* has one multiplane shot; *The Little Mermaid* (1989) was the last Disney film to use it (Wikipedia; D23 says *Oliver & Company* was the last to shoot multiplane scenes on the original stand: a conflict I leave unresolved). Three original Disney cameras survive (Burbank, San Francisco, Paris).

**How it works** (Wikipedia): layers move past the camera at different speeds and distances and are photographed frame by frame; closer layers move faster, giving parallax and depth; parts of each layer are left transparent; moving background and foreground in opposite directions makes a rotation (the Evil Queen's potion scene in *Snow White*); in the sample pan the plane nearest the camera is strongly out of focus; extras were distortion glass for water ripples, reflections, filters and planar lighting for flicker. One blog says distant levels moved more slowly and were "naturally blurred and out of focus" and operators varied the spacing between planes ([Manton Reece](https://www.manton.org/2013/06/17/multiplane.html)), which contradicts the Wikipedia sample on which plane is soft; focus depended on where the lens was set, which I take to be the more physical account (general knowledge: depth of field comes from the lens, the aperture and the distances). It also solved tracking shots that keep perspective (a distant moon staying the same size) and made forward motion cheaper than hand animation (Wikipedia).

**Visual signatures:**
1. **Real distances.** Everything is a flat plate at a measured distance; the picture is the camera's view of the stack.
2. **Parallax and growth together.** Lateral moves shift near plates more than far ones; moves toward the stack make every plate grow by 1/distance: the push-in that no flat 2D layering gives (general knowledge from the above; the Wikipedia article gives only the speed difference).
3. **Plates are painted with the distance in them.** Far plates pale, bluer and lower in contrast, near plates dark and warm-edged (atmospheric perspective: general knowledge); the Disney Museum ties the camera to fog and mist in *Pinocchio*.
4. **Transparent edges.** Each sheet is clear where the next should show.
5. **Focus as a tool.** What is in focus is a decision; near plates are soft.
6. **Backgrounds with a centre.** Tyrus Wong's impressionistic forest paintings for *Bambi* had more detail near the centre and less at the edges, to guide the eye to the characters ([Wikipedia: Bambi](https://en.wikipedia.org/wiki/Bambi): the page says nothing of the multiplane).

### 2.2 Layout and information architecture

- **The site is a stack of stacks.** Each section is a set-up: a stack of painted plates (a sky, a far plate, a middle plate, a mist, near plates in front of the words, and a fat foreground plate to sweep past). The words are planes too, at the focal distance.
- **Beats and the crank.** A section is made of beats, as in paint-on-glass; the page's scroll is the length of travel each beat's camera move takes. The words are fixed layers over the scroll, so the page's own scrollbar and keyboard behaviour are untouched.
- **Reading order** is the document's; each beat's words are a plane, and a prop (the phone, a picture) is a second plane at its own distance. A link focused in a plane that is not on show brings its beat to the lens.
- **A gauge.** A thin vertical rule on the right edge is the camera stand's column: the plates of the stack in front of the lens as ticks (near, text, mid, far) at their distances, a ring for the focus, a lens at the top. A readout at the foot shows the set-up, the truck (how far the camera has run) and the focus.

### 2.3 Signature interactions and scroll behaviour

**How scroll feels:** you are the person turning the crank. Within a section the world holds still for reading, with only a slow drift; then the camera runs and the whole stack moves at once.

**What scroll drives:**
- **The truck.** Between sections the camera runs 1.2 distance units (one unit is lens to words). Every plate at distance *d* is scaled 1/*d* about the centre: the near plate (resting at 0.7, so 1.43x) and the words (1.0) grow as the lens closes on them and leave the frame; plates ahead emerge from the mist: the next stack's far plate (1.55) fades in as it comes inside about 2.0.
- **Plates fade by distance.** A plate is solid near its resting distance, goes into the mist beyond about 1.1x it, and is gone before it reaches the lens (below 0.4x).
- **Focus is pulled.** The focus distance follows the plane the words are on with a lag of about a fifth of a second; every plate's softness is how far 1/*d* is from 1/focus. Each plate has a sharp canvas and a soft twin (a sixth of the size, enlarged by the browser) and the twin's opacity is the blur, so no blur filter runs per frame on large layers; the words use a stepped `blur()` (one step per pixel of defocus).
- **Inside a list, a plate sweeps past.** Between two items of a list (features, timeline steps, questions) the camera barely moves (0.05 per item, under 0.16 for a whole list, so the words never pass a middle plate) and a foreground plate of trunks is swept across the glass at 1.9x scale: the old words fade as it passes the middle of the picture and the new ones arrive behind it. This is the multiplane idiom of a fast foreground plate covering a change.
- **Hold and drift.** The first 38 per cent of each section's scroll holds, the last 10 per cent too; the camera runs in between. With no pointer, the camera drifts sideways by about a quarter of the pointer's range, so the glass is never dead still.

**Headline arrival:** by the camera: the title is a plane that arrives from beyond the mist and comes into focus as the lens reaches it.

**Stats:** figures on one plane at focal distance, over the mist.

**Feature list:** one beat per item, with the plate of trunks sweeping between them.

**Section transition:** the truck itself: the old stack's near plates and words pass the lens and leave; the new stack's plates come out of the mist; the sky behind cross-dissolves.

**Hover / pointer:** the pointer **trucks the camera sideways** (up to 5 per cent of the width at the focal distance: near plates move by 1/0.7 as much, far ones 1/1.55) and, **when it rests on painted glass for 0.6 seconds, pulls focus to that plate**: the soft twin of the plate under it goes away, the words go soft by up to about two pixels, the gauge's ring jumps. Moving 36 px ends it. It is checked by reading one pixel of alpha from the plate under the pointer, nearest to the lens first, so a rack goes to what you point at and not to the sky. On touch there is only the scroll (and the slight drift); nothing is intercepted.

**CTA:** the last stack's words at rest, over the largest moon, the button a plain plaque.

**Real-world references:** parallax on the web grew out of the multiplane idea (Wikipedia: [Parallax scrolling](https://en.wikipedia.org/wiki/Parallax_scrolling) says it "grew out of the multiplane camera technique"; Brett Taylor's 2007 JavaScript version and Paul Annett's 2008 Silverback CSS one). Keith Clark's pure-CSS version puts layers at different `translateZ` under a `perspective` and scales them back up to their authored size ([keithclark.co.uk](https://keithclark.co.uk/articles/pure-css-parallax-websites); [Chrome: Performant parallaxing](https://developer.chrome.com/blog/performant-parallaxing), with the scale formula (perspective − distance) / perspective). Those fix the camera and the layers' size and move the layers at different speeds as the page scrolls; the multiplane camera moves *toward* the stack. The CSS-parallax write-ups also warn that layering makes content harder to reach and that a Purdue study found parallax "did not necessarily improve the overall user experience" and a second study that it "may cause certain people to experience nausea" ([Wikipedia: Parallax scrolling](https://en.wikipedia.org/wiki/Parallax_scrolling)); that is why the camera holds while reading, why drift is small and why reduced motion turns the camera off.

### 2.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Wordmark in italic Cormorant, links in mono caps with an amber underline, the call to action a plain amber plaque. The gauge and the readout (see 2.2) are the camera stand |
| Hero | The first stack: sky, far plate, middle plate, mist, near plates; the title is huge on the left, the image (if any) is a **cel**, a picture on a sheet of acetate on its own plane at 1.16 behind the words, the phone a prop at 0.84 in front |
| Buttons | Plaques: a flat rectangle with a second outline set off by 3 px; the primary amber |
| Intro | Kicker with a short amber rule, title, lede |
| Features | A head beat and one per item, with a large amber italic numeral (a long tag becomes the kicker) and the sweeping plate between them |
| Product | Words on one side, the real phone (0.84) on the other; a product picture is a cel |
| Stats | Large italic figures, labels in mono caps |
| Timeline | One card per step: the `when` on a slate, the title, the note, centred |
| Quote | The saying large and italic, the attribution on a rule |
| FAQ | A title beat then one question per beat, `Q.` in amber, the answer on an amber rule; native `<details>`, open |
| CTA | The last stack; the giant title and a large plaque |
| Gallery, strip, orbit | Cels (tiles on acetate); a roll of cels; moons round a gold hub as a prop plane at 0.9 |
| Scenes (films) | The stacks step aside while a scene is on screen (`html.mp-scene`), and come back when it leaves |
| Footer | A dark band above the glass (z-index above every plane) |

### 2.5 Typography and colour

- **Display:** **Cormorant Garamond**, 600, italic for emphasis: the high-contrast serifs of 1930s to 1940s title cards (general knowledge), without imitating a specific lettering.
- **Body:** **Lora**.
- **Marginalia:** **DM Mono**, for the gauge, readout, kickers and slates.
- **Palette:** night `#14111f`, cream `#f6ecd9`, amber `#f0a05c`, mist `#9db6d9`. The plates' colours come from the same colour script as paint-on-glass (a sky, a glow in the accent hue, far/mid/near/deep planes), so near plates are the darkest and far plates the palest, as atmospheric perspective has it.

### 2.6 Implementation

- **Planes, not 3D.** `runtime/src/styles/multiplane.ts`. Each plate and each plane of words is a fixed full-size element transformed by `translate` and `scale(1/d)` about the centre of the screen; that is all the perspective there is (a single formula), which keeps text legible (the layer is re-rasterised at its scale when it is not animating), lets depth sort with `z-index` across plates and words together (one stacking context: sections are not `isolate`d in the live page), and works on every browser. The scale/translate arithmetic is the one in Chrome's performant-parallax note.
- **The plates** (`_mp-plates.ts`): painted once per stack, on demand, one plate per idle callback, with the same brush (`_brush.ts`): ridges, conifers, village, trunks, leaves, grass, rocks, mist, a sky with a moon placed away from the words; atmospheric perspective by colour; the left and right edges feathered to nothing so no hard edge shows while the glass is smaller than the view. Four recipes (village, forest, mountains, meadow) cycle by section. Plates cost 2 to 22 ms each to paint on the test machine.
- **Plate geometry.** A plate is painted as if the screen were looking at it from rest, in screen fractions (`X(0..1)`, `Y(0..1)`), so a painter thinks in screen terms and the glass can be bigger than the view. Far plates are 1.55 distance away; the mist is placed between the middle plate and the words (1.12) so it hazes the picture without veiling the words.
- **Opacity** is set on the canvases, not on the wrapper (a wrapper with fractional opacity makes the compositor draw the plate into a surface of its full size first).
- **Stacks:** the current stack and the one ahead are built; stacks more than one away are released. While a scene is on screen nothing is drawn.
- **Frame cost.** Planes are compositor layers (`will-change`) so moving them costs no repaint; a layer keeps the scale it was painted at, so a plane at rest is released for one frame and painted again, crisp. That one change took a scroll through the 22-beat test page from 35 frames over 33 ms (of 397) to 3 to 9 on a quiet GPU in headless Chrome at 1440 x 900. The test machine's GPU is shared with image generation, and when it was at 100 per cent the same page dropped many more frames (and so did paint-on-glass, less); I did not get a clean phone-class measurement of multiplane and say so. Painting a plate takes 2 to 22 ms, one plate per idle callback.
- **Fit.** Words or props taller or wider than the glass are scaled to fit (they are fixed planes; nothing may be cut off).
- **Accessibility:** words in reading order; the plates are `aria-hidden`; planes not on show are fully transparent and not layers (and still in the tab order); focus into one brings its beat to the lens. No scroll interception. The pointer's rack is optional.
- **Phones:** plates are painted smaller (0.58 of device pixels), props reduced, the gallery a horizontal roll, the gauge hidden.
- **Reduced motion and no JavaScript:** there is no camera. Each section is a still diorama behind ordinary copy: with the runtime (reduced motion) the plates are painted once and composited at rest on a canvas behind the section; without it, three layers of hills and a sky in CSS gradients.

### 2.7 Anti-patterns

- **The `parallax` scene.** The engine's `parallax` scene (`engine/scenes/parallax.py`) takes **one photo per step**, estimates a depth map for it with a model and plays back a 2.5D camera move over that picture. Multiplane has no photograph and no depth model: it is a stack of separately painted plates, a real distance per plate, and the camera moves down through section after section. They also scroll differently: the scene is scrubbed by scroll position through one picture; multiplane's words are planes in the same world as the plates.
- **A generic parallax page.** Layers that slide at different speeds as you scroll (a `translateY` per layer) have no distance, no growth and no focus; the camera has not moved. Here the plates grow by 1/distance, pass the lens and are out of focus by distance. Parallax between two layers is a side effect of the stack, not the effect.
- **An infinite zoom through text.** A tunnel with words in it, if the words are never in focus and the scene never rests, tires and, for some people, makes them ill ([Wikipedia: Parallax scrolling](https://en.wikipedia.org/wiki/Parallax_scrolling) on nausea). The camera holds while reading, the near plates are mostly at the edges, and reduced motion is a still.
- **Blur everywhere.** Blur is by distance from the focus plane, not a style: the words are sharp at rest.
- **Same-as-pop-up-book trap:** the pop-up book is one object with a hinge; its scroll is an angle. Multiplane has no object; it has a lens and distances.
- **Same-as-paper-cut-out trap:** cut-out sheets swing on pins in one plane; these plates never move sideways except by parallax and the sweep.
- **Same-as-paint-on-glass trap:** the sister style paints one picture on one pane; this one paints many sheets and never reworks any of them.

### 2.8 UX signature

**You turn the crank of a multiplane camera.** The page is a stack of painted glass under one lens. The words are a sheet at the focal distance: hold still to read, then scroll and the camera trucks down through the stack, the near plate and the words growing past the lens and leaving, the next stack coming up out of the mist, the focus pulled to the new words. Inside a list a foreground plate of trunks sweeps past at speed and changes the words behind it. The pointer slides the camera and, resting on a hill, pulls focus to it; a gauge down the edge shows where every plate is and where the focus is.

---

## Contrast table: the two signatures against their nearest neighbours

| | **Paint on glass** | **Multiplane** | Sand | Pop-up book | Paper cut-out | `parallax` scene | Generic parallax |
|---|---|---|---|---|---|---|---|
| **One scroll notch =** | Lays some strokes toward the next painting | Runs the camera a little further down the stack | A fraction of a sweep of a hand across the sand | Turns a board page a few degrees | The top sheet swings further off its pin | Moves the camera on one photo's depth map | Moves each layer by its own factor |
| **Time feel** | Strokes come as fast as you scroll, coarse then fine; stops where you stop | Continuous with a hold while reading; focus lags | One sweep per scene, then fingers finish | Continuous turn with a spring | Swing and sway | Scrubbed | Linear |
| **Spatial logic** | One flat pane, words in front | A real depth axis, planes at distances, growth by 1/d | One flat light table | One 3D book | Flat sheets on pins | A depth-mapped photo | Flat layers, offsets |
| **Persistence** | The last painting only; nothing rewinds | The sky cross-dissolves; near plates and words leave | The sand picture accumulates | The book and its pages | Sheets stack | The photo | Layers |
| **Headline arrives by** | A brush sweep with a wet edge | The title plane coming out of the mist into focus | Written in sand | Die-cut words rising | Hung words | n/a | Fade/slide |
| **Stats as** | Large figures with runs of paint | Large figures at focal distance | Poured numerals | Strips out of slots | Paper tags | n/a | Count-up |
| **Feature list as** | The light moves along the horizon while the picture is reworked | The camera barely moves; a plate of trunks sweeps past the swap | Discs and drawn ripples | Stand-up cards | A fan on one pin | n/a | Cards |
| **Section transition** | The old paint is dragged into the new | The camera trucks in; the next stack emerges from the mist | A sweep of a hand | The page turn | A sheet swings off | Next photo | Scroll |
| **Pointer** | A finger that smears the wet paint | Trucks the camera; resting pulls focus to the plate under it | Furrows with ridges | Orbit the table; drag tabs | Pushes the sway | Tilts the view | Mouse parallax |
| **CTA** | A blob of fresh paint | A plaque over the last stack | A ring of sand | The last tab | The last tag | n/a | Button |
| **Reduced motion** | Each painting laid in one step | Still dioramas of the plates | Still sand pictures | Opened dioramas | Still arrangements | The photo | Static |

Paint on glass and sand share a metaphor (a hand on a lit surface) and nothing else in the table; multiplane and the `parallax` scene share the word "depth" and nothing else. Neither is a reskin by the review rule.
