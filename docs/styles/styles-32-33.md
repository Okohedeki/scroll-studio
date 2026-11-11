> Style research from DesignAI by Edeki Okoh: https://github.com/Okohedeki/designai. Licensed under the GNU AGPL-3.0 with additional terms (NOTICE.md): credit it with this notice, unchanged, wherever it is used, and don't present it as your own work.

# DesignAI style research: styles 32 and 33

**Scratch film, Smears**

Prepared 2026-10-19 for the DesignAI engine, as part of the animation-technique batch (styles 22 to 33). Both techniques are about **time**, and both are drawn, not photographed. Direct-on-film animation puts every mark on the strip itself: nothing is shot, so every frame is a new drawing and the film is the picture. The Spider-Verse look is a timing system laid over computer animation: drawings held on twos, a smear where a pose changes, colour offset where a lens would blur. The question this research keeps asking is the earlier one: **what does one notch of the scroll wheel mean here?** In scratch film it is *film pulled through a gate*. In smears it is *a pose change that has to be drawn between*. Fonts and colours come after.

> **How to read the citations.** URLs are inline. Where a claim comes from general knowledge and not from a source I retrieved, I say "(general knowledge)". Where I only saw a search engine's excerpt of a page (the page itself refused to load or I could not read it), I say "(search snippet)". Pages read in full are cited without a tag. Quotations are kept under fifteen words; check them against the live page before reuse. Treat named works as references to check. Where the brief for this batch named a person or tool and I found no source for it, I left it out and say so below.

---

## Cross-cutting principle: two more clocks

| Style | What scroll *is* | Time quantisation | Motion curve | Spatial axis | Primary renderer |
|---|---|---|---|---|---|
| Scratch film | How much film has been pulled through the gate. One frame of strip is a fixed length of scroll; the footage counter, the sprocket holes and the optical track all travel with the page, 1:1 | Pull-down: the text moves in steps of one perforation (a quarter of a frame), at most 24 steps a second. The drawn picture is re-drawn on every frame that crosses the gate, so a new drawing per frame (on ones), never repeated | Intermittent: the claw yanks the strip and the gate holds it. At rest the strip is seated exactly. Run-on scratches are the one thing that is continuous | A vertical strip in a gate: sprocket rails and a drawn soundtrack down the edge, the projected frame filling the screen, intertitles pinned on it | Real HTML over one 2D canvas (the projected frame) and a thin canvas strip (the film itself) |
| Smears | How fast the pose is changing. The page is sampled twelve times a second; each change of pose is drawn through a smear frame; very fast scrolling gives multiples and streak lines | Twos (a new drawing every second frame of a 24-a-second clock), with ones for the small furniture and threes for the backdrop. The picture holds between drawings; no frame is ever blurred | Snap and hold: a pose is held, a smear covers the move, the next pose is held. Impact frames mark a change of section | A flat printed sheet with off-register colour plates; depth is shown by how far the colours slip, not by blur | Real HTML (text-shadow and drop-shadow plates, individual transform properties) over a halftone backdrop in CSS |

The batch is crowded with stepped, frame-based techniques, and these two must not be mistaken for them. `flipbook` and `zoetrope` make the scroll a frame counter and `stop-motion` makes it the shutter; their unit is a **page, a figure or an exposure of a physical set**. Scratch film's unit is a **length of film**, and what changes frame to frame is a *drawing on the emulsion*, not an object; its picture is also a running projection (it plays itself when you stop scrolling, and you can stop the projector), where stop-motion is dead between exposures. `retro-vhs` is video: scan lines, tracking error, a CRT. Scratch film is celluloid: perforations, a gate, dye and emulsion. Smears shares only the idea of working on twos with stop-motion, and differs in what it does with the in-between: stop-motion has none (a hop is poses), smears draws it, as a smear. `comic-book` is panels and speech balloons and `halftone` resolves images from dots; smears has neither panels nor dot-built pictures. Its dots are a texture, and what makes it a style is the timing.

---

## 1. Scratch film

### 1.1 Origin and defining aesthetic

Drawn-on-film animation, also called direct animation or animation without a camera, is made by working on the film strip itself. On blank film you draw, paint, stamp or tape objects; on black developed film you scratch, etch, sand or punch. It is mostly done on 16 mm or Super 8, and 35 mm gives more working area and leaves the optical soundtrack open for drawn sound ([Wikipedia: Drawn-on-film animation](https://en.wikipedia.org/wiki/Drawn-on-film_animation)).

**Len Lye.** *A Colour Box* (1935) was commissioned by the GPO Film Unit through John Grierson for £30 plus materials, and Wikipedia calls it Lye's first direct animation to get a public release. It was painted as long continuous patterns on 35 mm with no frame lines and few splices, using combs and sticks, to a beguine, "The Belle Creole", on which Lye marked cues ([Wikipedia: A Colour Box](https://en.wikipedia.org/wiki/A_Colour_Box)). Lye's later tools included dyes, stencils, airbrushes, felt-tips, stamps, combs and surgical instruments ([Wikipedia: Len Lye](https://en.wikipedia.org/wiki/Len_Lye)). *Free Radicals* was made in 1958 and revised in 1979 (the later cut is four minutes). It was scratched on black film, which leaves "only light against darkness", with dental tools and an arrowhead, to Bagirmi drum recordings; it took second prize among 400 entries at the 1958 Brussels World's Fair, and the Library of Congress selected it in 2008 ([Len Lye Foundation](https://www.lenlyefoundation.com/films/33/)). Lye described the marks as "white ziggle-zag-splutter and scratches" ([Ngā Taonga](https://www.ngataonga.org.nz/search-use-collection/search/F7706/)). One account says he held his hand high over the film so he could not see the marks as he made them, which is why the lines look "spastic" in his word (the second-hand quotation is from the film's Wikipedia page; check it against Horrocks's *Zizz!* before reuse; [Wikipedia: Free Radicals](https://en.wikipedia.org/wiki/Free_Radicals_(1979_film))). Lye wanted "pure figures of motion", not moving objects or patterns ([otherfilm](https://otherfilm.org/?p=575)).

**Norman McLaren.** McLaren, a pioneer of "drawn-on-film animation", "visual music" and "graphical sound", scratched and painted stock early because he lacked camera access; he made *Dots* and *Loops* in New York in 1940 (released 1949) and founded the NFB's Studio A in 1943 ([Wikipedia: Norman McLaren](https://en.wikipedia.org/wiki/Norman_McLaren)). *Begone Dull Care* (1949, with Evelyn Lambart; 7 min 48 s) was made with India ink, watercolour, cell paint, dust, brushes, sprayers, crumpled paper and mesh or lace as stencils; dust on wet dye formed circles, black paint dried in crackle patterns, and a knife on black emulsion made the dotted middle section; Oscar Peterson (24) improvised the piano ([Wikipedia: Begone Dull Care](https://en.wikipedia.org/wiki/Begone_Dull_Care); the NFB says they "painted colours, shapes, and transformations directly on to their filmstrip", [NFB](https://nfb.ca/film/begone_dull_care)). The film is 35 mm (search snippet: [TIFF](https://cfe.tiff.net/content/films/begone-dull-care)). *Blinkity Blank* (1955) was engraved directly onto black leader; McLaren left some frames blank, "sprinkling on the empty band of time"; its score is Maurice Blackburn's improvised jazz plus sounds scratched onto the optical track; it won the Cannes short Palme d'Or ([Wikipedia: Blinkity Blank](https://en.wikipedia.org/wiki/Blinkity_Blank)). *Pen Point Percussion* shows how sound appears on a film's soundtrack and then makes synthetic sound by marking the strip ([NFB](https://nfb.ca/film/pen_point_percussion)). Wikipedia lists *Synchromy* (1971) as photographing rectangular line cards onto the optical track to make notes (search snippet: [Wikipedia: Synchromy](https://en.wikipedia.org/wiki/Synchromy)).

**Stan Brakhage.** *Mothlight* (1963) used moth wings, petals and grass pressed between two strips of 16 mm splicing tape and contact-printed by a lab ([Wikipedia: Mothlight](https://en.wikipedia.org/wiki/Mothlight)); Canyon Cinema lists it as three minutes, colour, silent, between clear mylar tape ([Canyon Cinema](https://canyoncinema.com/catalog/film/?i=401)). Materials had to be thin and translucent, and he had first failed to film live moths (search snippet: [Far Out](https://faroutmagazine.co.uk/mothlight-stan-brakhage-totality-of-nature/)).

**Harry Smith** worked on the film surface with dyeing, drawing, bleaching, masking, stamping and batik-derived operations, and the results are "fields of movement and vibrating colour" ([Senses of Cinema](https://www.sensesofcinema.com/2005/cteq/early_abstractions/)). **Steven Woloshen** has worked without a camera since 1982, on 35 mm CinemaScope only since 1999, with leader, markers, inks, brushes and craft knives, often to jazz ([Wikipedia: Steven Woloshen](https://en.wikipedia.org/wiki/Steven_Woloshen)); his book is *Scratch, Crackle & Pop!* (2015) (search snippet: [Re:Voir](https://re-voir.com/shop/en/steven-woloshen/990-scratch-crackle-pop-the-whole-grains-approach-to-making-films-without-a-camera.html); the brief's "Scratch, Dig & Dye" does not match anything I found). **Lis Rhodes**'s *Light Music* (1975/76) prints pen-and-ink line patterns on the optical edge so that the lines play as sound (search snippet: [Tate](https://www.tate.org.uk/file/transform-lis-rhodes-and-aura-satz-programme-notes)).

**The medium itself.**
- **35 mm** is 34.976 mm wide with four perforations per frame down both edges; the perforation pitch is 4.74 to 4.75 mm; it runs 16 frames to the foot, 90 feet a minute at 24 fps; and the optical track sits between the perforations and the image ([Wikipedia: 35 mm movie film](https://en.wikipedia.org/wiki/35_mm_movie_film)). **16 mm** has one perforation per frame, 40 frames to the foot, and leaves the other edge free for sound ([Wikipedia: 16 mm film](https://en.wikipedia.org/wiki/16_mm_film)).
- **The gate.** Projectors hold the film flat in a gate under a spring pressure plate; 8 mm and 16 mm machines pull it with a claw (pawl) in the perforation, and 35 mm with an intermittent sprocket, usually a Geneva drive; the shutter blocks the light during the pull-down and flickers at 48 Hz, sometimes 72 Hz ([Wikipedia: Movie projector](https://en.wikipedia.org/wiki/Movie_projector)). Gate weave is frame-to-frame misalignment in the gate (the page defines it for telecine; that it shows as a small wobble on a projector is general knowledge; [Wikipedia: Gate weave](https://en.wikipedia.org/wiki/Gate_weave)).
- **Optical sound** is a strip beside the picture; a variable-area track varies the width of the white area with the signal, and is read by an exciter lamp and a photocell ([Wikipedia: Optical sound](https://en.wikipedia.org/wiki/Optical_sound)). Because it is read by light, it can be drawn by hand.
- **Why scratched leader is white.** Scratching black leader removes the emulsion and shows the clear base (general knowledge).

**Visual signatures:**
1. **The film is the picture.** No lens, no scene. Marks live on the strip and may cross frame lines; A Colour Box has none to speak of.
2. **A new drawing every frame.** Because each frame is marked by hand (Lye held his hand high and could not see what he made) nothing is registered from one frame to the next. The line "boils" ([TV Tropes: Line Boil](https://tvtropes.org/pmwiki/pmwiki.php/Main/LineBoil), search snippet) harder than any traced line.
3. **Two stocks.** Black leader scratched to light (Free Radicals, the dotted section of Begone Dull Care) and clear leader dyed and painted (A Colour Box, Begone Dull Care, Harry Smith).
4. **Saturated dye, textured by the process.** Dust on wet dye, crackle, stencils of lace and mesh, combs: the textures are accidents of materials (Begone Dull Care, above).
5. **Rhythm.** The pictures are timed to jazz, a beguine or drums (Lye, McLaren and Peterson, Woloshen, above); McLaren's blanks are rests.
6. **Sound you can see.** The optical track beside the picture can carry drawn marks that play as notes (McLaren, Rhodes).
7. **Pressed matter.** *Mothlight* has no drawing at all: real wings and petals pressed in tape, printed.

### 1.2 Layout and information architecture

- **The site is a reel being run through a viewer.** The screen is the **gate**: the frame under it is projected, full screen. A strip of film runs down the left edge (sprocket holes, the actual neighbouring frames, an optical track), and the page's sections are **reels**. A section's text is printed in the film: **intertitles**, white lettering on black leader, over the dancing picture.
- **The first heading on the page is the `<h1>`**, lettered large directly on the picture; the rest of the copy sits on black intertitle plates, which are what keeps the text readable whatever the picture does behind it.
- **Reading order is the HTML order**: slate (kicker), title, body, items, buttons. The page works without JavaScript as stacked reels on a still, scratched background; the strip is a CSS rail.
- **The nav is a reel list**: a number and a name per reel along the top edge, with the footage counter ("FT 0412 + 08", feet and frames at 16 frames to the foot) in the corner.
- **Scenes** (film, 3D, charts) are left alone in their own player and shown with a gate border and an edge code; they keep their own scroll model.

### 1.3 Signature interactions and scroll behaviour

**How scroll feels:** like having your hand on the film. It does not glide; it is **pulled**. Every few pixels the strip is yanked a notch and held, the picture on the screen is a new drawing each time, and when you let go the film is seated in the gate with a small bump.

**What scroll drives:**
- **Pull-down.** Page text is moved in steps of one perforation, a quarter of a frame, never more than 24 steps a second (a longer step when you go faster, so the rate holds). The true scroll position is only reached at rest, when the claw seats the strip: a short, damped settle. This is the intermittent movement of a projector or a viewer, applied to the page itself (the projector mechanism is cited above).
- **The strip is continuous.** The sprocket rails, the edge code and the neighbouring frames in the strip travel with the scroll 1:1, so you see the film moving at the true speed while the text steps. This is the Steenbeck look: the strip beside the screen.
- **Run-on scratches.** Vertical scratches that belong to the strip, at fixed positions, travel with it, so at speed they streak. Scratches and dust on film run along its length (general knowledge).
- **A new drawing on every frame.** The projection changes the picture as each frame passes the gate, up to 24 times a second; a drawing is a pure function of the frame number, so scrolling back plays the same drawings backwards. The motifs are drawn by rules (spirals, bursts, dashes, bars, dots, combs and stencilled stripes) with a random hand on top, in black-leader and dyed-leader tones. The projector also runs by itself slowly when you stop, so the film is never dead; a Hold switch stops it.
- **Splices.** The handover between sections is a splice: a strip of tape across the film, a change of stock (black to dyed leader), and one frame of flash leader.
- **The beat.** A counter of bars and beats (120 a minute, 12 frames a beat) runs on the footage; the footage counter shows it. With sound on, each frame passing the gate plays a note and every beat a drum, as in McLaren's drawn sound: the picture is the score (this is the style's own design, not a claim about his method).
- **Camera:** none. The only moves are the pull-down and the settle.

**Headline arrival:** scratched in. The letters of the title appear two at a time as it reaches the gate, each redrawn with a hand-wobble of a pixel or two while the film runs, like a title scratched on emulsion with a needle.

**Stats:** **sound-track numerals.** Each figure is large lettering over a variable-area waveform drawn from its own characters, the way a hand-drawn optical track plays: the number is printed, never counted up.

**Feature list:** **frames of a strip.** Each feature is a frame of the film, with sprocket edge, frame lines and an edge number, stacked as a strip, tilted a fraction of a degree as if spliced by hand.

**Section transition:** **the splice** above.

**Hover / pointer:** **the pointer is a needle.** Press and drag on the picture (not on text) and a white scratch is drawn into the emulsion of the frame under it; it belongs to the strip, so it travels away with the film when you scroll. Taps leave a dot, as in McLaren's *Dots* (a name, not a claim about method). It never takes a vertical gesture on touch: scratching only follows horizontal strokes, and `touch-action: pan-y` is kept.

**CTA:** the **tail leader**: an end card with the button set in a ring like an iris, and the footage counter running out.

**Real-world references:** I could not verify any web project that imitates scratch-on-film animation; searches return generic old-film overlay filters (search snippet: [jMonkeyEngine forum](https://hub.jmonkeyengine.org/t/old-film-effect-filter/25464)). A React filmstrip component is a sticky stage with a clipped gate and drawn perforation rows ([jas.it.com](https://jas.it.com/src/filmstrip.jsx), a personal site of unknown provenance). I found no verified award-listed filmstrip scroll site.

### 1.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Reel list along the top edge: numbers and names in mono; the current reel marked with a cue dot. The footage counter and a Run (the projector, on or off) and a Sound switch bottom left. |
| Hero | Reel 1: the title is lettered large on the picture, with the kicker and badge on a slate strip, the body on an intertitle plate. A hero image or phone sits in a **taped-in frame** with edge code. |
| Buttons | A frame with sprocket ticks above and below; the primary is a dye colour (cyan, magenta or yellow, never red). |
| Intro | Title lettered on the picture, body on a plate. |
| Features | A strip of frames, one per feature, with edge numbers. |
| Product | A projection screen: the image or phone in a frame; tags as edge-print labels. |
| Stats | Numerals over a drawn optical track. |
| Timeline | A bar sheet: rows of bars with a bar number, the step's "when" and title; the playhead is the beat counter. |
| Quote | An intertitle card: the quote lettered large on black leader, attribution as a credit. |
| FAQ | Reel cans: each question is a tape label; native `<details>`; the answer on a plate. |
| CTA | Tail leader; the button in a ring like an iris. |
| Gallery, strip | Contact strips: frames with sprocket edges and numbers. |
| Orbit | A reel: a hub with sprocket holes and the items around it. |
| Scenes | Left in their own player behind a gate border. |
| Footer | Colophon in edge-print mono. |

### 1.5 Typography and colour

- **Display:** **Londrina Solid**, a hand-cut sans in capitals, thick enough to look painted or scratched on leader; its weights run from hairline to black.
- **Body:** **Hanken Grotesk**, a plain grotesque so intertitles stay legible.
- **Edge print and counters:** **Share Tech Mono**, for edge codes, the footage counter and slates.
- **Palette:** black leader `#080808`, lamp white `#fff6df`, and dyes in the manner of Lye and McLaren: cyan `#12b8d8`, magenta `#e0338f`, yellow `#f2c814`, orange `#f08a1c`, green `#2ab56a`. No saturated red, so that nothing reads as a red flash (WCAG, below). The dye colours used for colour flicker are chosen so that their relative luminances lie within a band of 0.1.

### 1.6 Implementation

- **A belt, not native scroll, for the text.** Consecutive blocks are moved into a pinned stage (a sticky, viewport-high box), and a belt inside it is translated by JavaScript. Native scroll still drives the page and the track height; the belt's offset equals the true scroll position, except for the pull-down steps. Everything the belt shows is real HTML. Scenes are outside the belt and keep native scroll.
- **The film is a cache.** The picture is a pure function of `(frame number, tone)` and is drawn at low resolution into a small LRU of off-screen bitmaps; the strip draws neighbouring frames from the same cache at thumbnail size. The projection redraws only when the frame number changes (at most 24 times a second) and ambient 6 a second when idle.
- **The pull-down** writes `translate` on the belt only; nothing animates by CSS; nothing writes a custom property on the root.
- **Sound** is optional and off by default. It is a few Web Audio oscillators and a noise burst fired as marks pass the gate; it needs a click to start.
- **Phones:** the rail narrows, the thumbnails stay; steps are smaller (a perforation of 9 px); plates are full width; no drawing is taken by a vertical swipe.
- **Accessibility:** text is real, in reading order; the canvases and rails are `aria-hidden`. A Run switch stops the projector when you are not scrolling and satisfies the pause requirement for moving content. Text never moves faster than the page scrolls.
- **Flashing.** The criterion (WCAG 2.3.1) is no more than three flashes in any one second unless under the thresholds: a pair of opposing luminance changes of 10 % or more of maximum relative luminance, where the darker image is below 0.80, over an area larger than about 341 by 256 pixels at 1024 by 768; a red flash is any pair of opposing transitions involving saturated red ([W3C Understanding 2.3.1](https://www.w3.org/WAI/WCAG21/Understanding/three-flashes-or-below-threshold.html)). Here: scratches, dust and dots are thin and small; large dye fields change hue only, within a luminance band of 0.1, and no faster than 12 times a second; the flash frame at a splice is a single frame of a middling colour, rate-limited so that two can never fall within 450 ms; no red anywhere.
- **Reduced motion and no JS:** no belt, no pull-down, no projection loop. Each reel is a still: a scratched background drawn once in CSS or canvas, the strip as a static rail, every plate in place, the Run and Sound switches hidden.

### 1.7 Anti-patterns

- **A grain overlay and a vignette.** Old-film overlays are loops of dust over clean content; they read as old live action, not as drawn film (general knowledge, and the search results above).
- **Smooth tweened motion.** Direct-on-film frames are each drawn; nothing is registered, and nothing glides.
- **Sepia and rounded corners.** That is nostalgia, not saturated dye or emulsion removal.
- **Strobing.** Flicker is the point of the technique and also the hazard. Keep to the limits above.
- **Same-as-retro-vhs trap:** retro-vhs is video (scan lines, tracking, a CRT). Scratch film has perforations, a gate and no scan lines at all.
- **Same-as-flipbook trap:** a flipbook is pages turned by a thumb; here the strip is pulled and the drawing is on the emulsion.
- **Same-as-stop-motion trap:** stop-motion is dead between exposures and moves physical pieces; scratch film runs by itself, moves nothing physical, and steps the text only while you pull.

### 1.8 UX signature

**You are pulling a strip of drawn film through a gate.** The screen is the projection of whatever frame is in the gate, a new scratched or painted drawing every frame, dancing to a beat. The film itself runs down the left edge with its sprocket holes and its drawn soundtrack, moving as fast as you scroll, while the text on the screen steps through the gate a perforation at a time and seats with a bump when you stop. Between reels the film is spliced, the stock changes from black leader to dyed leader, and a single flash frame marks the cut. Press the mouse and you scratch the emulsion with a needle; turn the sound on and the picture plays.

---

## 2. Smears

### 2.1 Origin and defining aesthetic

*Spider-Man: Into the Spider-Verse* (2018) was animated by Sony Pictures Imageworks in Vancouver, with a crew that reached 142 by August 2018, at one point 177, the largest Imageworks had used for a film ([Wikipedia](https://en.wikipedia.org/wiki/Spider-Man:_Into_the_Spider-Verse)); VFX Voice reports more than 150 animators, and names Josh Beveridge as head of animation ([VFX Voice](https://vfxvoice.com/?p=5908138)). The brief for this batch named other people for the animation department that I could not find sources for, and a "Bret St. Clair" for the line tool; the line tool's machine-learning write-up is by Pav Grochola ([fxguide](https://www.fxguide.com/?p=246246)). I use none of the unsupported names.

**Twos, and a mixture.** The film was animated at 24 frames a second ("on ones") or 12 ("on twos", each image repeated), and both could appear in one scene; the producers called the effect "crunchy" ([Wikipedia](https://en.wikipedia.org/wiki/Spider-Man:_Into_the_Spider-Verse)). Cartoon Brew says it was mostly on twos, with some scenes on ones and on threes, and that VFX supervisor Danny Dimian found splined animation on ones too smooth ([Cartoon Brew](https://www.cartoonbrew.com/feature-film/if-its-not-broke-break-it-sony-imageworks-renegade-approach-to-spider-man-into-the-spider-verse-167321.html)). Beveridge says twos does not mean "mathematically every other frame": animators mixed timings within a shot, and the only limits were avoiding strobing and mushy motion ([VFX Voice](https://vfxvoice.com/?p=5908138)). Dimian called the result "snappy": "sometimes it's two, sometimes it's on threes" ([fxguide](https://www.fxguide.com/?p=244678)). Twos "freed us up" from realism and were another tool for dynamic poses ([Nerdist](https://nerdist.com/article/into-the-spider-verse-animation-vfx-fixing-whats-broken/)); director Bob Persichetti says holding three frames becomes noticeable, which is why they chose twos, and that new algorithms for hair and cloth were needed because twos removed the simulated motion ([Dark Horizons](https://www.darkhorizons.com/?p=109512)). In the forest swing Miles is on 12 fps to show inexperience and Peter on 24 ([Wikipedia](https://en.wikipedia.org/wiki/Spider-Man:_Into_the_Spider-Verse)); in *Across the Spider-Verse* (2023) the mix runs from ones to sixes, Spider-Punk was pushed onto fours and sixes with limbs split off at different rates, and a "StepSets" tool republished scenes at different rates so effects matched ([Before & Afters](https://beforesandafters.com/2023/06/28/this-was-the-first-cg-animated-movie-ive-ever-heard-of-that-actually-had-a-dedicated-inking-team/)). Wikipedia says Spider-Punk's body and guitar are on different frame rates ([Wikipedia: Across the Spider-Verse](https://en.wikipedia.org/wiki/Spider-Man:_Across_the_Spider-Verse)).

**No motion blur.** Persichetti: "there's not one frame of motion blur anywhere in the movie" ([Dark Horizons](https://www.darkhorizons.com/?p=109512)). Dimian says any frame you stop on is solid and sharp, and movement is suggested with drawn streak lines and lines that follow form ([VFX Voice](https://vfxvoice.com/?p=5908138)). Fast pans smear and streak the backgrounds in a "very graphic treatment" ([Cartoon Brew](https://www.cartoonbrew.com/feature-film/if-its-not-broke-break-it-sony-imageworks-renegade-approach-to-spider-man-into-the-spider-verse-167321.html)). Wikipedia names this motion smearing, an older 2D technique, and gives a 1942 Looney Tunes short as a precedent ([Wikipedia](https://en.wikipedia.org/wiki/Spider-Man:_Into_the_Spider-Verse)).

**Colour offset in place of focus.** There is no depth-of-field blur: the lens effect is a colour offset driven by z-depth, which Dimian says "isn't a blur", and the team studied misprinted comics ([VFX Voice](https://vfxvoice.com/?p=5908138)). fxguide says the image is splintered and offset, which reads as defocus ([fxguide](https://www.fxguide.com/?p=244678)). Cartoon Brew says it "still feels like a racking camera" and that a rule was adopted to avoid smooth gradations. Foundry names the tool, ChromaShifter, "originally created for handling the color offsetting effect" ([Foundry](https://www.foundry.com/insights/film-tv/graphic-look-in-comp-spiderman)).

**Halftone and hatching.** Foundry: the printed-comic look was "created almost entirely in comp", with tools called Hatcher and Thresher; halftones scaled with light and dots were added to flares ([Foundry](https://www.foundry.com/insights/film-tv/graphic-look-in-comp-spiderman)). Transitions use dot patterns rather than smooth gradients, including "Kirby dots" after Jack Kirby ([Cartoon Brew](https://www.cartoonbrew.com/feature-film/if-its-not-broke-break-it-sony-imageworks-renegade-approach-to-spider-man-into-the-spider-verse-167321.html)). Dimian warns that heavy hatching, oversized dots or bold lines can compete with a character's emotion ([Nerdist](https://nerdist.com/article/into-the-spider-verse-animation-vfx-fixing-whats-broken/)).

**Lines, captions, glitch.** Lines are drawn in 3D on the characters and can react to light or not ([Dark Horizons](https://www.darkhorizons.com/?p=109512)); there are acting lines and form lines, drawn by hand, rigged, or "drawn through machine learning" ([VFX Voice](https://vfxvoice.com/?p=5908138)); the ML first pass was a scikit-learn regressor trained in Houdini on about 600 frames per character ([fxguide](https://www.fxguide.com/?p=246246)). On-screen captions give exposition, sound-effect words fill the frame, and characters and buildings glitch during "dimensional earthquakes", with several cameras styled differently on one animation for a cubist look ([fxguide](https://www.fxguide.com/?p=244678)). Each dimension has its own look: Peni Parker draws on anime and manga, Noir is black and white, Spider-Ham is as cartoony as possible; animation co-director Patrick O'Keefe is quoted calling it "making five movies" ([Wikipedia](https://en.wikipedia.org/wiki/Spider-Man:_Into_the_Spider-Verse)). *Across* has six styles, with Gwen's Earth-65 a watercolour wash ([AWN](https://www.awn.com/news/spider-man-across-spider-verse-feature-six-different-art-styles)).

**The wider family, and where it stops.** *The Mitchells vs. the Machines* (2021) is Imageworks' hand-painted, watercolour-textured follow-up, with 2D drawings over the 3D in "Katie-Vision" ([Wikipedia](https://en.wikipedia.org/wiki/The_Mitchells_vs._the_Machines); [Before & Afters](https://beforesandafters.com/2021/04/29/behind-the-early-2d-3d-test-for-the-mitchells-vs-the-machines/)), but animation supervisor Alan Hawkins says the team did **not** use the on-twos approach there ([Before & Afters](https://beforesandafters.com/2021/04/29/the-way-we-animated-those-was-completely-new/)). So the painterly texture and the stepped timing are separate things, and only the second is this style. *Puss in Boots: The Last Wish* (2022) is "in a painting, but also still CG"; director Joel Crawford credits Spider-Verse for the confidence, and says action often drops to twos, fours and sparser while grounded moments are on ones ([Cartoon Brew](https://www.cartoonbrew.com/feature-film/puss-in-boots-joel-crawford-inbtwn-224324.html)); per a snippet, in the bar fight the wolf is on ones and Puss on twos so that stepped animation makes Puss fantastical (search snippet: [TheWrap](https://www.thewrap.com/puss-in-boots-the-last-wish-director-joel-crawford/)).

**The classical roots.** A smear frame is an in-between that simulates motion blur; **multiples** duplicate the subject along its path without distorting it; earlier smears extended the motion lines of comics; Tex Avery and Chuck Jones at Warner Bros. standardised the modern concept ([Wikipedia: Smear frame](https://en.wikipedia.org/wiki/Smear_frame)). Ken Harris called it an "elongated inbetween"; Eric Goldberg popularised "smears"; drybrush is a blur that usually does not deform the cel ([Cartoon Research](https://cartoonresearch.com/index.php/the-partial-and-mostly-lost-history-of-animation-smear-terminology/)). On ones is 24 drawings a second, twos is 12, threes is 8 ([ID Tech](https://www.idtech.com/blog/what-does-animating-on-ones-twos-and-threes-mean)). Squash and stretch, anticipation and timing are among Johnston and Thomas's twelve principles ([Wikipedia](https://en.wikipedia.org/wiki/Twelve_basic_principles_of_animation)).

**Print terms.** Ben-Day dots (1879) are equal-size dots used in comics, enlarged by Lichtenstein; halftone dots vary in size ([Wikipedia: Ben-Day dots](https://en.wikipedia.org/wiki/Ben-Day_dots)). CMYK screens are set at angles to avoid moiré ([Wikipedia: Halftone](https://en.wikipedia.org/wiki/Halftone)). Misregistration is a shift between colour layers that can leave stray colour or white gaps ([Wikipedia: Printing registration](https://en.wikipedia.org/wiki/Printing_registration)).

**Visual signatures:**
1. **Holds and snaps, not glides.** Poses are held; the time between is short or drawn as a smear.
2. **A smear frame at the move.** A stretched shape (and sometimes multiples) in the one frame where the pose changes; never a soft blur.
3. **Streak lines instead of blur.** Motion is shown by drawn lines.
4. **Colour offset instead of focus.** Out-of-focus things are the ones whose colour plates slip.
5. **Mixed frame rates in one picture.** Ones, twos and threes in the same shot; a body and its guitar at different rates.
6. **Printed surfaces.** Ben-Day dots, hatching, a captions-and-panels grammar, but a restrained amount.
7. **Impact frames** at the biggest moments (the design name for a single held frame that breaks the pattern; I found no source tying the term to Spider-Verse, so treat it as the style's own word).

### 2.2 Layout and information architecture

- **The site is a run of printed sheets, each from a different dimension.** A sheet is a full-bleed field of flat print colour with a halftone backdrop, cut at an angle (a clipped, slanted edge), with the headline set huge in a condensed slab and the body on a tilted scrap of paper. Each section gets one of four looks in turn (a dimension): *print* (cyan, magenta and yellow dots on cream), *ink* (black hatching with one spot colour), *riso* (two overprinted fluorescent inks on off-white) and *pop* (electric purple and acid green). The look sets the colours, the dot or hatch texture and the cadence of the backdrop.
- **Reading order** is the HTML order; the first heading is the `<h1>`; the page works without JavaScript as stacked sheets in their dimension colours.
- **Furniture:** a thin captions bar along the top (the site name in a yellow caption box, the sections as small caption boxes); a mini frame-rate readout in the corner ("12 · TWOS", or "24 · ONES" when you slow to a crawl), as the timing is the subject.
- **Scenes** are left in their own player with a printed frame.

### 2.3 Signature interactions and scroll behaviour

**How scroll feels:** like flicking through the key poses of a storyboard that someone has had to animate between. Nothing glides. The page holds, jumps, holds; and in the one frame of the jump it is drawn as a streak.

**What scroll drives:**
- **The sample.** The page position is read twelve times a second (the beat of twos); between reads nothing moves. Content is shown at the position of the last read, so there is a lag of at most 83 ms, and at rest it is exact.
- **The smear.** When a sample moves the page, the first frame of the move is the **smear**: the page content sits at the mid-point and the "actors" (headlines, numerals, images, cards and buttons) are stretched along the direction of travel in proportion to the distance moved, with a coloured echo of the old and new positions. The next frame is the new pose, sharp, and it is held. Nothing is blurred: the stretch is a scale, the echo is a silhouette in a flat colour.
- **Multiples at speed.** When the speed passes a threshold the smear gains multiples: up to four echoes of the actor strung along its path in cyan, magenta and yellow plates, like a print with the plates slipping (the press running fast), and streak lines in the backdrop.
- **Misregistration is depth.** At rest, every actor has a small constant offset between its colour plates (a pixel or two), the way the offset replaces focus in the film. The offset is biggest on the backdrop and smallest on the actor under the pointer or with keyboard focus, so a hover or a focus is a **rack focus by offset**, not a blur.
- **Mixed cadence.** The actors move on twos (12 a second), the backdrop's halftone drifts on threes (8 a second), and small furniture (the corner readout, the pointer's trail) moves on ones (24 a second). It is a deliberate mix, as in the film's mix of rates; the content text is never given less than twos.
- **Impact frames.** When a new section's sheet crosses the middle of the screen while you are scrolling fast, the picture breaks for two frames (83 ms) into one **impact frame**: a flat field of the incoming dimension's colour, black speed lines from the centre, a halftone burst, the old sheet's headline cut out of it; then the new sheet snaps in with a short shake on twos. At most one impact in 520 ms (two a second); not at slow speeds; no red; the frame's colour is chosen to stay within the thresholds below.
- **Arrival:** an actor entering the view pops (a squash-and-stretch overshoot on twos) with a smear on the first frame.
- **Camera:** none; the only camera move is the shake after an impact.

**Headline arrival:** each line of the headline lands on its own: a smear from below, a stretched overshoot, a settled pose; the lines are three colour plates that settle into register one after another.

**Stats:** **stamped numerals.** Each figure is huge, set with multiples trailing down the page (the echo copies stepping away in the plate colours), and pops on a hold.

**Feature list:** **variants.** Three cards, each in a different medium (printed dots, hatched ink, riso), tilted a degree or two, like the different looks of the film's characters; the one with focus is sharp and the others slip.

**Section transition:** an **impact frame** above, then the new sheet's dimension: its colours, its texture, its cadence.

**Hover / pointer:** the pointer leaves a **trail of multiples** on ones: three echoes of a small coloured mark, a streak when you move fast. Hovering or tapping an actor holds a pose: it squashes, stretches and holds, with a smear on the first frame. Nothing captures a scroll gesture.

**CTA:** a big slanted button on a burst of speed lines, popped last; the tap or click is its own small impact.

**Real-world references:** I found no web project that does on-twos stepping, smears or scroll-driven Spider-Verse timing. What exists is texture work: a halftone editor on CodePen inspired by the film's dots ([DEV](https://dev.to/madsstoumann/into-the-halftone-verse-1ckl)), a Three.js thread on halftone and chromatic aberration on text (search snippet: [three.js forum](https://discourse.threejs.org/t/halftone-chromatic-aberration-effect-on-text/82243)), and a Unity asset with a CMYK offset (search snippet: [itch.io](https://lucy-creates.itch.io/spider-verse-effects)). The CSS `steps()` function is the native tool for stepped timing ([MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/easing-function)), but it steps over time, not per pose.

### 2.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | A caption bar: the site name in a yellow caption box, sections as small captions; the readout "12 · TWOS" at the corner. |
| Hero | Sheet 1 (print): the headline in three stacked plates (cyan, magenta, black), the lede on a tilted paper scrap, buttons as slanted stickers. An image or phone is a cut-out with a hard colour offset behind it. |
| Buttons | A slanted parallelogram sticker with an offset plate; the primary is magenta or yellow, never red. |
| Intro | A diagonal split: title huge on one side, body on a tilted scrap on the other. |
| Features | Three variants in three media; the focused one sharp. |
| Product | The phone as a cut-out with three echoes trailing behind it, tags as stickers. |
| Stats | Stamped numerals with multiples. |
| Timeline | A diagonal rail of key poses: each step a frame at an alternating tilt, joined by speed lines; the "when" as a caption box. |
| Quote | A huge caption box with a halftone burst behind. |
| FAQ | Torn tabs; native `<details>`; opening is a snap with a smear. |
| CTA | A burst of speed lines, a big slanted button. |
| Gallery, strip | Prints pasted at angles with offset plates. |
| Orbit | Stickers on a ring, with a streak as the ring turns. |
| Scenes | In their own player behind a printed frame. |
| Footer | Fine print in mono on the sheet. |

### 2.5 Typography and colour

- **Display:** **Anton**, a tall condensed face that survives being stretched and echoed; set in capitals, with `<em>` as the second plate colour.
- **Body:** **Archivo**, a grotesque with a width axis for the captions.
- **Captions and readout:** **Space Mono**.
- **Palette:** per dimension. *Print*: paper `#f4ecd8`, ink `#16141a`, cyan `#16b5e0`, magenta `#ec2f8c`, yellow `#ffd72e`. *Ink*: paper `#ecebe6`, ink `#101012`, spot `#ff3d8b`. *Riso*: off-white `#f2efe6`, fluorescent orange `#ff6a3d`, blue `#2f4bff`. *Pop*: purple `#5b2bd9`, acid `#c6f432`, ink `#120a2a`. No saturated red; pink is used instead.

### 2.6 Implementation

- **Same belt as scratch film.** Blocks are moved into a sticky stage and a belt translated by JavaScript; the belt shows the position of the last sample. Scenes stay outside.
- **A 24-a-second clock** (`requestAnimationFrame`, ticks of 41.7 ms): even ticks take the sample, odd ticks hold. A tick with a changed sample is a smear tick. All motion is a function of the tick number; nothing runs between ticks except the pointer trail.
- **Actors** are marked in the templates (`data-sa`). A smear writes `scale`, `translate` and a filter of stacked `drop-shadow`s (the plates) on the actors in view only, at twelve a second, never on the root. Text gets the same effect from stacked `text-shadow`s. No `blur()` anywhere.
- **The backdrop** is CSS gradients (dots, hatching, stripes) on a layer whose `background-position` and plate offsets are changed at eight a second.
- **Impact frames** are one fixed overlay (an SVG data-URI of speed lines, a radial dot mask) shown for two ticks, rate-limited by time.
- **Phones:** the smear is a stretch only (no filter stacks) below a size or speed budget; the echoes are text only (no filter stacks on pictures); the trail is off on touch.
- **Accessibility:** real text in reading order; the overlays are `aria-hidden`; focus moves the belt to the focused element. Flashing: the impact frame is one pair of opposing changes, at most two in a second (520 ms apart), a flat mid-luminance colour field with black lines, and no saturated red (the thresholds are as in 1.6). The smear itself changes no luminance over a large area.
- **Reduced motion and no JS:** no belt, no sampling, no smears, no impact frames. Each sheet is a still print in its dimension, with the plates at their resting offsets; the readout is hidden.

### 2.7 Anti-patterns

- **A comic filter over the page.** A static halftone or posterise at 60 fps, with no holds, no per-element rates, no offset logic, no smear: that is the lazy version. The look is a timing system (Foundry's and Cartoon Brew's accounts above), not a texture.
- **Motion blur.** The film has none; the style has none. A `filter: blur` anywhere is a bug.
- **Panels and speech balloons.** That is `comic-book`.
- **Dots that make the picture.** That is `halftone`. Dots here are a backdrop texture and a transition device.
- **Too much print.** Dimian's warning (above): dots, hatching and bold lines must not compete with the content.
- **Painterly instead of stepped.** Mitchells and Puss are painterly; Hawkins says Mitchells did not use twos. Texture alone is not this style.
- **Same-as-stop-motion trap:** stop-motion is dead between exposures and has no in-between; smears is sampled in time and draws the in-between as a smear.

### 2.8 UX signature

**The page holds on twos and draws the move.** You flick, and nothing glides: the sheet holds, jumps, holds, and in the one frame between, its headline and its cards are stretched into a streak with their colour plates trailing, as if the press had slipped. Go faster and the streak becomes multiples. Cross into the next section while moving and the picture breaks into a single impact frame of flat colour and speed lines, then snaps into a new dimension with its own print texture and its own cadence. Slow down and everything locks into register, the one thing in focus and the rest slipping. No blur anywhere.

---

## Contrast table: the two signatures against their nearest neighbours

| | **Scratch film** | **Smears** | Retro VHS | Flipbook | Stop-motion | Comic book | Halftone |
|---|---|---|---|---|---|---|---|
| **One scroll notch =** | Pulls the strip a notch through the gate | Changes the pose; the move is drawn as a smear | Moves the tape; tracking error | Flips to the next page | One more exposure | The eye to the next panel | Resolves more dots |
| **Time feel** | Pull-down steps (to 24 a second); picture re-drawn each frame; runs by itself when idle | Sampled at 12 a second; backdrop on threes, furniture on ones; holds | Continuous with tracking noise | Frame steps at scroll speed | Twos, capped at 12; dead between | Stepped panel by panel | Continuous |
| **Spatial logic** | A strip beside a projection screen | Flat printed sheets with plates | A CRT screen | A pad of paper | A miniature set | A pinned page of panels | Dot field |
| **Persistence** | Scratches stay on the strip | Plates slip, not stay | Tape artefacts | Pages accumulate | The set stays | Pages replace | Image stays |
| **Headline arrives by** | Scratched in, two letters at a time | Three plates landing with smears | Glitched in | Drawn frame by frame | Clay letters placed | Caption slides | Dots form |
| **Stats as** | Numerals over a drawn optical track | Stamped numerals with multiples | Counters | (flipbook's own) | Alphabet blocks | Starburst numerals | Dot numerals |
| **Feature list as** | Frames of a strip | Variants in three media | Menu | (flipbook's own) | Felt cards | Action panels | Dot cards |
| **Section transition** | A splice and a flash frame | An impact frame, a new dimension | Channel change | Run of pages | Strike and dress | Zoom out, turn | Dots dissolve |
| **Pointer** | A needle that scratches the emulsion | A trail of multiples; rack focus by offset | Cursor glitch | Grab the corner | Pokes a piece | Panel lifts | Dots scatter |
| **CTA** | Tail leader and an iris | Speed-line burst and a slanted button | Tape end | (flipbook's own) | Felt button, bunting | "Your turn!" panel | Dot button |
| **Reduced motion** | Still reels on scratched backgrounds | Still prints in each dimension | Still frame | A single page | Finished tableaux | Full pages | Static dots |

Scratch film shares no cell with its neighbours beyond the word "frame", and smears shares only the cadence of twos with stop-motion. Neither shares three, so neither is a reskin by the review rule.
