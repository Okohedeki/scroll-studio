> Style research from DesignAI by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. Licensed under the GNU AGPL-3.0 with additional terms (NOTICE.md): credit it with this notice, unchanged, wherever it is used, and don't present it as your own work.

# DesignAI style research: styles 22 and 23

**Pinscreen, Sand animation**

Prepared 2026-10-12 for the DesignAI engine. These are the first two of the animation-technique batch (styles 22 to 27). The question for this batch is sharper than for the earlier ones: scroll-driven pages are everywhere now, so each style starts from a classic technique's own *mechanic* and asks what "scrolling" becomes inside it. Wheel and touch scroll stay the main input, but the technique decides what that input does.

> **How to read the citations.** URLs are inline. Where a claim comes from general knowledge of the films or the craft and not from a source I retrieved, I say "(general knowledge)". Pin counts and release years differ between sources; where they do, I give the range and say so.

---

## Cross-cutting principle: two physical media, two different verbs

Both techniques make one continuous image out of a physical material under a camera, and both are *straight-ahead*: the artist destroys each picture to make the next one. That is exactly why they must not feel alike on the page. The pinscreen is a **relief**: its material only moves in depth, and light turns depth into tone. Sand is a **layer**: its material only moves sideways, and light passes *through* it. So the two verbs are different: you *press* a pinscreen and you *sweep* sand.

| Style | What scroll *is* | Time quantisation | Motion curve | Spatial axis | Primary renderer |
|---|---|---|---|---|---|
| Pinscreen | Pushing pins: a wave rolls through the board from the next picture's subject, a wall of pins pushed out with ripples behind it; the old picture lies ahead of it, the new one behind. A raking lamp turns depth into tone | Continuous scrub, exactly reversible; the pins follow the wave physically and flash as they move | A radial wave: a lit trough, a wall of depth, damped ripples, the lamp lowering while it runs | **Z only.** Pins never move sideways; the wave travels across the board, the lamp swings between plates | One WebGL fragment shader drawing every pin and its cast shadow from a depth-and-motion texture |
| Sand | The side of a hand sweeping an arc across a light table: the old picture piles into a moving front of grains, some thrown ahead, and the new one lies behind it, clean | Gestural and **history-dependent**: the table remembers. Scrolling back sweeps again rather than rewinding; furrows stay until a sweep takes them | An arm's arc (rotation about an elbow off-screen), then a fingertip carving or a pinch of sand pouring, at hand speed | **Lateral, top-down.** Silhouettes on light; nothing has depth except ridges | A CPU density field (mass moved only where the hand passes) shaded grain by grain as backlit sand, plus grains in flight drawn as points |

How they sit against the existing styles: `particles` re-forms a conserved swarm of points by moving them through space (a swirl), with a pointer force field that springs back. The pinscreen's pins never leave their holes, and its pointer is mainly a *lamp*. Sand has no points at all: it is a continuous field that changes only where a hand touches it, and its marks stay. `liquid-morph` blends shapes smoothly with no material logic; `halftone` modulates dot size on a print screen (no depth, no light direction); `blueprint` draws with a linear pen. Neither new style shares its scroll model with any of them.

---

## 22. Pinscreen

### 22.1 Origin and defining aesthetic

The pinscreen (French *écran d'épingles*) was developed in Paris by Alexandre Alexeieff and Claire Parker; their tests began in 1932 and Parker registered the patent in 1935 ([Wikipedia: Pinscreen animation](https://en.wikipedia.org/wiki/Pinscreen_animation)). It is a white board pierced by a dense grid of holes, each holding a sliding black pin. A light from the side makes each pin cast a shadow: a pin pushed out casts a long shadow and the board goes dark there, a pin pushed flush casts none and the board stays white, and everything between is a grey ([NFB blog: Animation techniques, pinscreen](https://blog.nfb.ca/?p=34378); [Wikipedia](https://en.wikipedia.org/wiki/Pinscreen_animation)). The image is therefore literally *chiaroscuro made of depth*: the pair wanted the depth and contrast of chiaroscuro rather than the flatness of cel animation ([Open Culture](https://www.openculture.com/2021/01/innovative-pinscreen-animations-of-kafka-gogol-and-mussorgsk.html)).

- **Scale.** Counts vary by source: the original screens had "over a million" pins ([Wikipedia](https://en.wikipedia.org/wiki/Pinscreen_animation)); Britannica's animation entry gives some 500,000 (search summary of Britannica, not retrieved directly). The NFB's board has 240,000 ([NFB blog](https://blog.nfb.ca/?p=34378)); the screen for *Before the Law* had over a million ([John Coulthart](https://johncoulthart.com/feuilleton/tag/claire-parker)).
- **Working method.** Pins are set with tools; Wikipedia lists improvised ones (lamp bulbs, spoons, forks, Matryoshka dolls). Each frame is a small change from the last, photographed, then re-sculpted ([Wikipedia](https://en.wikipedia.org/wiki/Pinscreen_animation); [NFB blog](https://blog.nfb.ca/?p=34378)). In the 1972 NFB demonstration film the two work on **both sides of the board**: Alexeieff pushes pins in from the front to make light areas, Parker pushes them back out from behind to restore the black ([John Coulthart](https://johncoulthart.com/feuilleton/tag/claire-parker)). That two-sided gesture is the mechanic this style is built on.
- **Films.** *Une nuit sur le mont chauve* (*Night on Bald Mountain*, 1933), *En passant* (1943), *The Nose* (1963), *Pictures at an Exhibition* (1972), *Three Moods* (1980) ([John Coulthart](https://johncoulthart.com/feuilleton/2015/05/28/the-pinscreen-works-of-alexandre-alexeieff-claire-parker)); and the prologue to Orson Welles's *The Trial* (1962), Kafka's parable "Before the Law" in pinscreen stills under Welles's voice ([Open Culture](https://www.openculture.com/2014/09/kafka-illustrated-with-pinscreen-art.html); [Wikipedia](https://en.wikipedia.org/wiki/Pinscreen_animation)). They also made still pinscreen illustrations for books, including an edition of *Doctor Zhivago* ([John Coulthart](https://johncoulthart.com/feuilleton/tag/claire-parker)).
- **After them.** Jacques Drouin used the NFB board for three decades; *Mindscape* (*Le Paysagiste*, 1976) is a painter who walks into his own landscape, 7.5 minutes and 17 awards ([Wikipedia: Mindscape](https://en.wikipedia.org/wiki/Mindscape_(1976_film))); the NFB counts 10,800 designs for it ([NFB blog](https://blog.nfb.ca/?p=34378)). Michèle Lemieux followed (*Here and the Great Elsewhere*, 2012). The CNC restored the pair's last screen, the Épinette (1977), in 2015; Justine Vuylsteker's *Embraced* (2018) came out of its residency ([Wikipedia](https://en.wikipedia.org/wiki/Pinscreen_animation)). The executive-toy "Pin Art" relief board, credited to Ward Fleming, is the version most visitors will have touched ([Exploratorium store](https://www.exploratoriumstore.com/products/classic-pin-screen)).
- **Digital precedent.** Lopes and Gomes published a computer model of the pinscreen in 1992 ([Eurographics digital library](https://diglib.eg.org/handle/10.2312/6759)). I found no web pinscreen that drives scroll.

**Visual signatures:**
1. **Tone from shadow, not ink.** Greys are soft and velvety, with a fine regular grain; critics compare the films to "an animated engraving" ([John Coulthart](https://johncoulthart.com/feuilleton/tag/claire-parker)). There are no outlines, only light falling off forms.
2. **A raking light.** All shadows point the same way. Where the board is flat it is pure white; where it is fully out it is near black.
3. **Metamorphosis.** Because the board is re-sculpted in place, one form melts into the next instead of cutting (a face becomes a window, a horse becomes a cloud) (general knowledge of *Night on Bald Mountain* and *Mindscape*).
4. **Monochrome, nocturnal.** Gogol, Mussorgsky, Kafka: dream and night. Drouin experimented with coloured light ([NFB blog](https://blog.nfb.ca/?p=34378)) but the canon is black and white.

### 22.2 Layout and information architecture

- **The page is one board.** A single fixed board fills the viewport behind everything, inside a thin dark frame. Every section is a *plate*: one picture set on the board. The site reads like a sequence of book plates (Alexeieff's illustrated editions) or the stills of *The Trial* prologue.
- **Plates replace sections.** Each section keeps its place in the document as a scroll spacer (so anchors and the outline still work), and its copy appears in a fixed stage over the board while the plate is set. A section with several items (features, timeline, stats) is a run of plates.
- **Calm zones.** Body copy is ordinary ink text on the white board. Each plate's picture is composed around it: the runtime measures where the copy sits and keeps those pins flush, so text always sits on clean white (4.5:1 is guaranteed by the board colour, not by luck).
- **Display type is relief.** Headlines, big numerals, the phone, images and films are set *in pins*. Their DOM text stays in place, selectable and read by screen readers, but transparent over its own relief.

### 22.3 Signature interactions and scroll behaviour

**How scroll feels:** pressing. The page never slides. You are pushing a picture through a board: slow, tactile, exact, a little grainy. Stop anywhere and the board holds a half-made relief that still reads.

**What one scroll notch does:** it moves pins in depth, and only in depth.
- **The relief tide.** Between two plates, a flat *platen* presses the outgoing picture back into the board from the front: its highest pins (the blacks) are levelled first, so the old image loses contrast tone by tone. At the same time the incoming picture is pushed through from behind like a hand pressed into a Pin Art toy: it first appears as a flat grey silhouette and then deepens, its blacks arriving last. Height of a pin = max(min(old, front plane), min(new, back plane)). This is literally the two-sided Alexeieff/Parker gesture.
- **Stick-slip grain.** Each pin has its own friction, so pins move in small jumps rather than gliding. The tide shimmers grain by grain, like the board being worked frame by frame (time quantisation per pin, not per frame).
- **The lamp swings.** Each plate has its own lamp angle; between plates the light travels across the top of the board, so shadows rotate while the relief changes. A tiny dial in the frame shows where the lamp is.
- **Reversible scrub.** Scroll back and the tide runs back exactly. That is a deliberate contrast with sand (23), where the table remembers.

**Headline arrival:** pushed through from behind. The letterforms rise as a pale grey silhouette, then their strokes deepen to black as the plate settles. Never typed, never faded, never sliding.

**Stats: a sundial.** The figures stand in relief in a row. Scrolling through the stats plate swings the lamp in an arc over them; the figure the light reaches is pushed to full depth (black, long shadows) while the others sink back to low relief. One by one, like reading a sundial.

**Feature list:** one plate per feature. A huge relief numeral and the feature title in relief, the body in ink beside it, and a row of small bosses (one per feature) along the bottom with the current one pushed out.

**Section transitions:** the relief tide plus the lamp swing. Never a fade, wipe or slide.

**Pointer:**
- **Hover is the lamp.** On a mouse, moving the pointer nudges the raking light (within about 35°), so every shadow on the board swings with your hand. The relief is re-lit, not moved.
- **Press is the burin.** Press and drag to push pins in: you draw white lines into the picture. The trace holds for a moment and then the pins are pushed back out from behind, slowly (Parker restoring the black).
- **Touch.** A finger swiping to scroll leaves a pressed trail along its path that recovers the same way. The listener is passive, so scrolling is never blocked.

**CTA:** the button sits on a raised relief slab. Hovering presses that slab into the board (its pins sink under the pointer, as the toy does under a palm); the CTA headline above it is in full relief.

**Real-world references:** the films above; McLaren's NFB film *Pinscreen* (1973) of the demonstration, which also shows Caroline Leaf trying the board ([NFB blog](https://blog.nfb.ca/?p=34378); [Wikipedia](https://en.wikipedia.org/wiki/Pinscreen_animation)); the Exploratorium pinscreen table ([Exploratorium store](https://www.exploratoriumstore.com/products/classic-pin-screen)).

### 22.4 Component treatments

| Component | Treatment |
|---|---|
| Nav / chrome | A thin dark iron frame around the board. Wordmark and nav links engraved on the frame's top rail in small caps typewriter; a lamp dial and a plate counter ("plate 04 / 17") on the bottom rail. |
| Hero | Headline in full relief, pushed through on load (the board starts flat). Badge as a typewritten label, lede and buttons in ink in a calm zone. Picture: the site's image or `theme.art` in relief; animated art plays as true pinscreen animation (the board re-set every frame). |
| Intro | One plate: the title in relief across the top two-thirds, kicker and body in ink below it. |
| Features | A run of plates, one per feature: relief numeral, relief title, ink body, a row of bosses as the index. |
| Product | The phone in relief: body raised, screen recessed, its rows embossed, the selected option pushed further out. Copy in ink. A product image becomes relief. |
| Stats | The sundial: relief figures in a row, the lamp sweeping across, the reached figure pushed to full depth. Labels in ink under each figure. |
| Timeline | A ridge of pins rises left to right across the board as you scroll, with a boss at each step; the current step's "when" in relief, its text in ink. |
| Quote | Ink text, large, on clean board; two giant relief quotation marks and a relief rule. The lamp drops lower for this plate so shadows lengthen (night). |
| FAQ | Questions in ink as a real `<details>` list; a giant relief "?"; opening an answer pushes a short row of pins out beside it. |
| CTA | Relief headline; the button on a relief slab that sinks when hovered. |
| Footer | Typewritten colophon on the frame's bottom rail. |
| Images, films | Luminance becomes pin depth (dark = out). Film and image-sequence scenes play *on the board*: each frame is re-pinned, the original video hidden; captions sit on white label cards. |
| Unknown blocks | Default markup in ink over a flat board with a relief border. |

### 22.5 Typography and colour

- **Display (relief): Yeseva One.** A heavy fat-face didone with Cyrillic, drawn by Jovanny Lemonad: thick stems survive being set in pins, the hairlines dissolve into the grain like an engraving, and its Russian flavour nods to Alexeieff (general knowledge).
- **Body: Spectral** 300 to 600, a book serif made for screens: the plates read like an illustrated edition.
- **Labels: Courier Prime.** Typewritten production notes, plate numbers, the lamp dial.
- **Palette (monochrome, cool):** board white `#e9e8e3`, frame iron `#1d1e20`, ink `#161616`, pin steel `#26282b`, a cold lamp-white highlight. Accent is ink. No hue anywhere but the faint warmth of the board.

### 22.6 Implementation

- **One fixed WebGL canvas.** The pins' depths live in a small texture (one texel per pin: about 240 x 150 on a laptop, 110 x 240 on a phone). A full-screen fragment shader draws, per pixel, the board, the pin head in its cell (a dark disc with a lamp-side glint) and the cast shadows of up to 12 pins upwind of it (segments of length proportional to depth, widening into penumbra). Cost is constant per pixel and independent of the pin count.
- **Pictures are composed at pin resolution** on an offscreen 2D canvas, one pixel per pin: relief type drawn with the DOM's own font at each word's measured position, images and video frames as luminance, the phone as shapes. Copy rectangles are cleared to flush.
- **CPU per frame:** for every pin, target = tide(old, new, t) + pointer press field; display depth follows with per-pin stick-slip friction. 40,000 pins of typed-array arithmetic is well under a millisecond.
- **Scroll mapping:** each section is a spacer; plates are anchors at fixed scroll positions; between anchors the middle 60% is the tide, the rest holds. Anchor links land on settled plates.
- **Performance:** render only when something changed (tide, lamp, press, video); pause when the tab is hidden. Pitch about 6 CSS px on desktop and 3.6 on phones; device pixel ratio capped at 2 (1.5 on phones).
- **Without WebGL or JavaScript:** sections in normal flow on a white board with a CSS dot texture, headlines in ink with a raking text-shadow.

### 22.7 Anti-patterns

- **Halftone confusion.** Dots that grow and shrink on a flat grid are halftone (style 15). Pins are all the same size; tone comes from *shadow length in one light direction*. If you lose the light direction, you have made halftone.
- **Particles confusion.** Pins never leave their holes. Nothing flies, swirls or reassembles sideways.
- **3D pin forests.** Rendering thousands of instanced cylinders with a perspective camera reads as a tech demo and loses the drawing. The board is seen square-on; the depth is only in the light.
- **Colour.** Tinted lamps and gradients make it a screensaver. Stay monochrome.
- **Fading text in.** Headlines arrive as relief, body copy as ink with the plate.

### 22.8 Reduced-motion fallback

The board stays, as a *printed* pinscreen: each plate is a still relief, swapped in one step at the section boundary (no tide, no lamp swing, no grain shimmer). Pressing still leaves a trace, which recovers without animation after a pause. It remains unmistakably a pinscreen still, like a page from the *Zhivago* edition.

### 22.8b Revision after review (v2)

The first build was a white board with black relief type: correct, but plain and sparse, the transition (a quiet tide) didn't land, and pin-made headlines were soft. The rework:

- **Every plate is a full pinscreen picture.** The board is lamp-lit and mostly dark, as Alexeieff's plates are: a pool of light falling off to deep black with smoky grain in it, and in it a subject modelled by the lamp (theme.art and images in tone; big numerals, ghost words, the phone and the CTA slab sculpted from a distance-field height and lit from the lamp's side, with cast shadows).
- **The transition is a wave.** A circle rolls out from the next plate's subject: a trough the lamp floods with light, then a wall of pins pushed out, then damped ripples; the old picture ahead of it, the new one behind. The lamp lowers while it runs so the moving pins throw long shadows, and pins in motion flash. The copy is revealed by the same circle.
- **Type is crisp.** Headlines and body are real ivory HTML on deep black (the pins behind the copy stand fully out, feathered so it reads as shadow, not a box); the pins answer each headline with a soft lit relief of its words behind it. Pins alone carry only the big display numerals and ghost words.

### 22.9 UX signature

**You don't scroll the page; you send a wave through a board of pins.** One lamp-lit board holds the whole site, and every plate is a full pinscreen picture, deep blacks to soft greys, its numerals, words and phone modelled by the light. Each scroll rolls a wave out from the next picture: a lit trough, a wall of pins, ripples behind it, the new picture settling in its wake while the lamp swings. Headlines stay crisp in ivory over the black; your hand moves the light, and pressing draws lines the board slowly pushes back out. Pins never move sideways.

---

## 23. Sand animation

### 23.1 Origin and defining aesthetic

Sand animation is sand on a sheet of glass lit from below, worked by hand and filmed from above. Light shows through where the sand is thin and is blocked where it is thick, so the images are silhouettes with soft, grainy gradations; varying the density gives smoke or cloud ([Wikipedia: Sand animation](https://en.wikipedia.org/wiki/Sand_animation)). It is done two ways: **frame by frame** (change the sand slightly, shoot a frame, repeat) and as **live performance**, drawn in real time and projected for an audience ([Wikipedia](https://en.wikipedia.org/wiki/Sand_animation)).

- **Caroline Leaf** found it in Derek Lamb's animation class at Harvard, with beach sand on a lightbox; her first film was *Sand, or Peter and the Wolf* (1968 or 1969 depending on source) ([Wikipedia: Caroline Leaf](https://en.wikipedia.org/wiki/Caroline_Leaf); [Wikipedia: Sand animation](https://en.wikipedia.org/wiki/Sand_animation)). *The Owl Who Married a Goose: An Eskimo Legend* (NFB, 1974; some sources say 1976) was drawn in sand on glass lit from beneath, with Inuit artist Agnes Nanogak ([Wikipedia](https://en.wikipedia.org/wiki/The_Owl_Who_Married_a_Goose:_An_Eskimo_Legend)). *The Metamorphosis of Mr. Samsa* (1977): play sand on opaque glass lit from below, photographed from above ([Wikipedia](https://en.wikipedia.org/wiki/The_Metamorphosis_of_Mr._Samsa)).
- **Leaf's own account** is the brief for this style. She never learned to edit and was afraid of making a cut, so she *drew her transitions* from one scene to the next: "scene-shifting, shape-shifting". She works "straight ahead, under the camera", and to remove something she sweeps it back into a pile of sand; the fingerprints in the sand show the hand ([Harvard Film Archive conversation](https://harvardfilmarchive.org/conversations/330)). Under-the-camera work destroys each image to make the next, and she pressed the sand into different densities to shade it ([Senses of Cinema](https://www.sensesofcinema.com/?p=3999)). A lecture record has her calling sand a form of metamorphosis ([CU Digital Library](https://cudl.colorado.edu/luna/servlet/detail/CUB~45~45~3~1254497:Caroline-Leaf,-First-Person-Cinema)).
- **Others.** Gisèle and Ernest "Nag" Ansorge (Switzerland, from the 1960s; *Les corbeaux*, 1967); Eli Noyes's *Sandman* (1973) and the *Sand Alphabet* for *Sesame Street*; Co Hoedeman's *The Sand Castle* (1977, Academy Award) ([Wikipedia](https://en.wikipedia.org/wiki/Sand_animation)). Ferenc Cakó's *Ab Ovo* (1987, short film prize at Cannes) and, from 1996, sand animation as a *live performance*, which he is credited with developing first ([Cannes](https://www.festival-cannes.com/en/f/ab-ovo-homoknyomok/); [KAFF](https://2023.kaff.hu/en/magyar-zsuri/ferenc-cako)). Kseniya Simonova's 2009 *Ukraine's Got Talent* performance on an illuminated sand table, projected on a big screen: a couple on a bench under the stars is obliterated by warplanes, then becomes a weeping woman's face ([Christian Science Monitor](https://m.csmonitor.com/World/Global-News/2009/0930/ukraines-got-talent-kseniya-simonova-brings-nation-to-tears); [Wikipedia](https://en.wikipedia.org/wiki/Kseniya_Simonova)).

**Visual signatures:**
1. **One take.** The picture is never cut. Every new image is made out of the old one's sand.
2. **Backlit silhouettes.** Warm light through glass; thick sand near-black, thin sand amber and grainy at the edges.
3. **The hand's vocabulary** (general knowledge of live sand performance): the *sweep* with the side of the hand (wipes and piles), the *fingertip* (draws light lines by pushing sand aside, leaving ridges), the *pinch pour* (a thin stream of sand draws dark lines), the *palm press* or thumbprint (round light dimples), and sprinkling for texture.
4. **Ghosts.** Swept areas keep faint traces of what was there.

### 23.2 Layout and information architecture

- **The page is one light table.** A single fixed table fills the viewport. Every section is a *scene* drawn in the same sand. No section has its own background, box or card.
- **Sections are scroll spacers** with a fixed stage for their copy, so anchors land and the document outline is kept.
- **Copy sits on clean glass.** Each scene's sand picture is composed around the copy: the runtime keeps the glass under the text swept clear, so dark umber text reads on glowing amber (well over 4.5:1). Headlines and numerals are made of sand; body copy is ink on light.
- **The DOM is swept with the sand.** The copy of the outgoing scene is clipped away by the same arc that sweeps its sand, and the incoming copy is uncovered behind the hand. Text never fades.

### 23.3 Signature interactions and scroll behaviour

**How scroll feels:** a live performance you are conducting. One continuous take; the hand only ever moves where you push it.

**What one scroll notch does:** moves the side of a hand a little further along an arc across the table.
- **The sweep.** Each transition is one arm's arc, swung from an elbow off the edge of the table (bottom-left, then top-right, then bottom-right, so no two sweeps look the same). Ahead of the hand the old scene is untouched. Under it, the sand that the new scene doesn't need is scooped into a ridge that travels with the hand and grows as it gathers; where the new scene needs sand, the ridge pays it out. Behind the hand lies the new scene, with a faint ghost of the old one in the grain. Stop scrolling and the hand stops mid-sweep, ridge and all.
- **History.** Nothing is a crossfade, so nothing simply rewinds. Scroll back up and the hand sweeps the other way, rebuilding the earlier scene out of the later one's sand; the ghosts are of whatever was there. Furrows you drew stay until a sweep passes over them.
- **Then the fingers work.** After the sweep, the last stretch before each scene settles is the hand finishing the drawing: a fingertip carves the headline out of the sand slab, or a pinch of sand pours the numerals.

**Headline arrival:** carved. A slab of sand is swept in, then a fingertip carves the letters out of it, left to right, as you scroll the last stretch: glowing letters in dark sand, with little ridges at their edges.

**Stats: poured.** Each figure is drawn by a thin stream of sand from pinched fingers, one figure after another; the falling stream is visible at the pour point. The labels sit in ink under them.

**Feature list:** one scene per feature: a thumbprint (palm-pressed disc of light) holding the poured feature number, the feature title carved into a slab beside it, the body in ink.

**Section transitions:** the arm's sweep. Never a cut.

**Pointer:** a fingertip. Moving the mouse grazes the sand (a faint shallow trail); pressing and dragging draws a full furrow, light down the middle with ridges of displaced sand either side. Marks are permanent until the next sweep. On touch, the finger swiping to scroll furrows the table as it goes (passive listener, scrolling is never blocked).

**CTA:** the last sweep gathers the sand into a ring; the button glows in the clear glass at its centre; the headline is carved above.

### 23.4 Component treatments

| Component | Treatment |
|---|---|
| Nav / chrome | No bar. The table's wooden rim carries the wordmark and links in small caps; a hand-written scene counter ("scene 3 of 12") in the corner. Restyled default nav, so the links stay. |
| Hero | Poured dunes along the foot of the table, the headline carved into a slab, the badge and lede in ink. `theme.art` or the hero image as a sand silhouette. |
| Intro | Carved title slab; body in ink on glass; a fingertip spiral flourish. |
| Features | A run of scenes, one per feature: thumbprint with the poured number, carved title, ink body. |
| Product | The phone as a sand silhouette whose screen is swept clear: the real HTML screen glows through the glass. |
| Stats | Poured figures, one after another, labels in ink. |
| Timeline | A winding furrow drawn by a fingertip through a field of sand, a step at a time, with a thumbprint at each step; the step's text in ink beside it. |
| Quote | The table covered edge to edge, and an oval swept clear in the middle (an iris made of sand); the quote in large italic ink inside it, a giant poured quotation mark. |
| FAQ | Questions in ink as a real `<details>` list on glass; a carved "?" slab. |
| CTA | A ring of gathered sand around the glowing button; carved headline. |
| Footer | Ink colophon on the rim. |
| Images, films | Luminance becomes sand density (silhouettes). Film and sequence scenes keep their own players; the table dims to a sand frame around them. |
| Unknown blocks | Default markup in ink on clean glass, framed by poured sand borders. |

### 23.5 Typography and colour

- **Carved and poured display: Caveat** 500 to 700. A finger in sand writes a rounded, quick, monoline hand; a casual script carves cleanly and reads as drawn on the spot.
- **Body: Alegreya** 400 to 700: a calligraphic book serif with warmth, for the storybook register of Leaf and the NFB.
- **Labels: Alegreya Sans SC.**
- **Palette (warm, backlit):** glass light `#f6dfb0` (centre) falling to `#e4ad62` at the rim, sand umber `#2c1a0c`, transmitted amber `#c9762c`, ink `#24150a`, rim walnut `#3a2516`.

### 23.6 Implementation

- **A density field** at about 2.5 CSS px per cell (around 576 x 360 on a laptop, 160 x 340 on a phone), in a Float32Array. Sand only moves where the hand or the pointer is.
- **The sweep**: the hand is a line from a pivot outside the screen, at angle phi(scroll). Each frame, the cells between the previous and current angle are processed: excess sand over the target goes into a load per radial band, deficits are paid from it (or from the hand when it runs out), and a small fraction of the old density is left as a ghost. The load is drawn as a ridge just ahead of the hand.
- **Carve and pour** are masks drawn at cell resolution (the headline in the DOM's font, the numerals stroked); progress is scroll-driven so a scene is always finished at its anchor.
- **Rendering**: one fragment shader. Transmittance exp(-k * density) with per-pixel grain noise (thin sand breaks into grains), light colour falling off from the centre, transmitted light warming to amber, and a top-light from the density gradient so ridges catch a highlight.
- **DOM clipping**: the stages are clipped with `clip-path: path()` to the swept sector (incoming) and its complement (outgoing, with `evenodd`), updated every frame with the hand.
- **Performance**: upload the field only when it changed, cap the grid on phones, pause when hidden.

### 23.7 Anti-patterns

- **Particles confusion.** No flying swarm and no re-forming points: nothing moves unless a hand pushes it.
- **Falling-sand game.** Gravity-sim sand (Sandspiel-style cellular automata) is a different thing; this is a top-down table.
- **Beige texture skin.** A sandy background image with normal sections on it is a reskin. The table must be the only surface.
- **Crossfades.** Any fade between scenes breaks the medium: sand cannot fade, it can only be moved.
- **Rewinding.** Scrubbing back to an exact earlier frame makes it feel like video. Let the hand sweep again.

### 23.8 Reduced-motion fallback

Each scene is a still sand drawing on the table, swapped in one step at the section boundary: no sweep, no carve, no pour. Pointer furrows still work (the visitor makes them). It reads as a sand picture, a still from Leaf's films.

### 23.8b Revision after review (v2)

The first build read as brown paint: dark slabs behind headlines, a sweep that looked like a clipped arc, and ghosts of old scenes that looked like dirt. The rework:

- **Grains.** The table is shaded grain by grain: every grain-sized spot is covered or not by chance in proportion to the sand there (with clumping), so thin sand glows amber with single grains showing, thick sand goes dark, edges break into scattered grains, and a few quartz grains glint. Shapes are composed soft, so their edges fall apart into grains as real sand does.
- **No slabs.** Headlines are crisp HTML ink on the glowing glass, written on left to right as the fingers go, with a little sand spilled along their strokes. Big numerals are poured (sand only). Pictures are built from thin and thick sand: dunes, finger-drawn ripples, a spiral, a ringed disc around a poured numeral, the phone's outline with its real screen glowing through, a drift with a question mark cleared through it, an iris for the quote, a ring for the CTA.
- **The sweep pushes grains.** The front is a mound that grows with what it gathers, with a long granular slope ahead of it, and grains are thrown off the front, roll ahead and settle (where the front collects them again). The copy is uncovered behind the pile with a soft conic mask, not a hard clip.
- **Clean scenes.** The hand leaves the next scene clean; the only residue is the odd settled grain.

### 23.9 UX signature

**One sand picture, never cut, and your scroll is the hand.** A warm light table holds the whole site, every grain visible. Each scroll swings the side of a hand across it in an arm's arc: the old scene piles into a moving mound of grains, some rolling ahead of it, and the next scene lies clean behind it, its words uncovered as the pile passes. Then the fingers finish: the headline is written on, numbers are poured, ripples and spirals are drawn. The table remembers: go back up and the hand sweeps the other way, and every furrow you draw stays until the next sweep takes it.
