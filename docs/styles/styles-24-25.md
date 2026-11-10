> Style research from DesignAI by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. Licensed under the GNU AGPL-3.0 with additional terms (NOTICE.md): credit it with this notice, unchanged, wherever it is used, and don't present it as your own work.

# DesignAI style research: styles 24 and 25

**Zoetrope, Flipbook**

Prepared 2026-10-12 for the DesignAI engine, as part of the animation-technique batch (styles 22 to 27). These two styles come from the two oldest ways of making drawings move by hand: a drum you spin and a pad you thumb. Both are pre-cinema toys, and both answer the batch's question in a different way: *what does scrolling become inside this technique?* In the zoetrope, the page is **a prize wheel of cards under a strobe**: you spin it, the figures come alive while it is fast, and it lands on one card you can open. In the flipbook, scrolling is **the thumb**: every notch lets go of one page, and the drawing is wherever your thumb has got to.

> **How to read the citations.** URLs are inline. Where a claim comes from general animation or design knowledge and not from a source I retrieved, I say "(general knowledge)". Some figures (frame counts, installation sizes) differ between sources; where they do I say so instead of picking one silently.

---

## Cross-cutting principle: two pre-cinema scroll models

| Style | What scroll *is* | Time quantisation | Motion curve | Spatial axis | Primary renderer |
|---|---|---|---|---|---|
| Zoetrope | **A prize wheel you spin and land.** The whole landing page is one ring of cards on a turntable, one card per element; the scroll wheel, a swipe or fling, a drag, the spin button or the arrows give it a spin | A closed loop of 12 poses on every card. While the wheel is fast the strobe steps every figure on one pose per card past the pointer, so the whole ring is alive; slow, it is still pictures | Real inertia: impulse in, friction out, then a spring that lands square on one card with a small overshoot; the pointer ticks over the pegs | Rotation about a vertical axis: a ring of printed cards, the front one square on and largest, the far side of the ring above it | One WebGL canvas (three.js turntable, a printed face and a 12-pose atlas per card) plus the real HTML of a card shown in a dialog when it is picked |
| Flipbook | **The thumb on a pad.** One wheel notch (about 100 px) releases one page; scroll position is the page number, forwards and backwards | Discrete pages. Each page is one drawing; a slow scroll bends the next page's corner, the notch lets it go | A released page peels over in about a quarter of a second (fast start, settling as it lies over). A fast scroll riffles several pages in flight at once | Depth: a pad of paper seen from above, hinged at a peg bar along its top edge; pages peel up from the lower corner and fold over the top | Canvas 2D (a fold-and-reflect page peel, pencil drawings with line boil) plus real DOM text on the resting page |

Neither model is used by any of the 21 existing styles. Kinetic type and liquid morph react to scroll *velocity* too, but as a deformation of the content (skew, wobble); in the zoetrope speed decides whether the figures are alive, and the page itself is an object you spin and land rather than a column you read down. Pixel art steps frames, but its frames are a sprite walking through a level; the flipbook's frames are the pages of the site itself, and you move through them like paper.

---

## 24. Zoetrope

### 24.1 Origin and defining aesthetic

William George Horner described the device in 1833 or 1834 as the *daedaleum*; he published it but never patented it ([Museum of the History of Science, Oxford](https://www.mhs.ox.ac.uk/exhibits/fancy-names-and-fun-toys/zoetrope/); [Wikipedia: Zoetrope](https://en.wikipedia.org/wiki/Zoetrope)). The toy as people know it is William E. Lincoln's: he applied for a US patent on 27 July 1866 as assignor to Milton Bradley, granted 23 April 1867 (Wikipedia, above; Oxford gives a conflicting later date). Lincoln's version put **the slits on a band above the pictures**, which is what made the picture strips easy to swap, and Milton Bradley sold the strips in numbered series of twelve (Wikipedia, above). James Clerk Maxwell fitted concave lenses to the slits in 1868 to remove the distortion (Oxford, above), and made strips of physics subjects such as vortex rings (Wikipedia). British makers sold it as "The Wheel of Life"; the Science Museum holds strips such as a horse and rider jumping a fence and two acrobats back-flipping ([Science Museum Group: Wheel of Life No. 30](https://collection.sciencemuseum.org.uk/objects/co8593655/zoetrope-strip); [Wheel of Life strip](https://collection.sciencemuseumgroup.org.uk/objects/co8593656/zoetrope-strip-the-wheel-of-life)).

Émile Reynaud's **praxinoscope** (1877) replaced the slits with a ring of twelve mirrors at the centre, one per picture, which gave a brighter, steadier image ([Wikipedia: Praxinoscope](https://en.wikipedia.org/wiki/Praxinoscope)). The zoetrope never died: Toshio Iwai supervised the Ghibli Museum's 3D Totoro zoetrope (2001), figures on a turntable that come alive under a strobe ([Boing Boing visit](https://boingboing.net/2010/07/26/a-visit-to-spirited.html); Wikipedia), and Pixar's *Toy Story* zoetrope, built with Gregory Barsamian and Toshio Iwai, mounts posed maquettes on a turntable lit by a strobe ([Academy Museum](https://www.academymuseum.org/en/content/article/toy-story-3d-zoetrope); sources disagree on the number of figures). John Edmark's 3D-printed "blooming" sculptures are shot at a shutter or strobe synchronised to one flash per 137.5° of rotation, the golden angle, so the petals appear to flow ([Motionographer](https://motionographer.com/2015/01/16/fibonacci-zoetrope-sculptures/); [Dezeen](https://www.dezeen.com/?p=631400)). Eric Dyer films spinning "cinetropes" with a fast-shutter camera, which does the slits' job ([UMBC IRC: Bellows](https://irc.umbc.edu/bellows-zoetropic-filmmaking/)).

The most important reference for a *scroll* site is the **linear zoetrope**. Bill Brand's *Masstransiscope* (1980) puts 228 hand-painted panels behind a row of slits in the disused Myrtle Avenue subway station; the passing train is what "spins" it, and riders see about twenty seconds of animation ([nycsubway.org](https://www.nycsubway.org/wiki/Artwork:_Masstransiscope_(Bill_Brand)); [Creative Time](https://creativetime.org/projects/masstransiscope/)). Joshua Spodek's tunnel advertisements (Atlanta, 2001, then Washington, BART and New York) work the same way (Wikipedia). In both, **the viewer's own motion makes the picture**, and a train that is too slow sees only slivers. That is exactly the relation between a visitor's scroll speed and the drum in this style.

**Visual signatures:**
1. **The drum.** A black or lacquered cylinder on a turned stand, a band of narrow vertical slits round its upper half, the picture strip glimpsed inside through them.
2. **The strip.** A long paper band of 12 (sometimes 13) frames separated by rules, printed in chromolithograph colours on cream: black silhouettes, vermilion, Prussian blue, ochre. A printed title and series number along the edge ("No. 3").
3. **Cyclic subjects.** A juggler, a horse, a bird beating its wings, a ball bouncing, an acrobat. Every subject is a **loop**: the last frame leads back to the first.
4. **The box of strips.** The toy came with a box of interchangeable strips; part of the ritual is choosing the next one, dropping it into the drum and giving it a spin.
5. **Flicker and darkness.** Through the slits the picture is dim and slightly flickering; the eye fills it in (general knowledge).

**How the illusion works, and why it matters for the mechanic.** Each slit gives the eye a brief look at the frame opposite, then blocks the view until the next slit arrives with the next frame in the same place, so the frames do not smear (Wikipedia, above). With as many slits as frames, the subject animates on the spot; draw one frame more or fewer than there are slits and the figures appear to travel round the drum (general knowledge). Below a certain rate the pictures read as separate snapshots; the brain links them into motion (the beta effect, not retinal "persistence") once they arrive fast enough. Early film ran between 12 and 24 frames a second ([UAL research paper on persistence of vision and apparent motion](https://ualresearchonline.arts.ac.uk/id/eprint/21202/2/f4fb8655-0e0a-461f-8852-163a38bd629c.pdf)); hand-made flip animation is commonly said to look smooth from about 12 to 15 ([RAFT activity guide](https://raft.net/wp-content/uploads/2020/08/280-Animated-Flip-Books.pdf)). A strobe zoetrope does not need the eye's threshold at all: the strobe freezes each pose, and the figures read as alive as soon as the flashes step them on. So the style lights its strobe at about two and a half cards a second past the pointer, which any spin crosses: under it, still pictures travelling round a ring; over it, every figure on the ring alive at once.

> **Revisions (2026-10-12).** *v1* was a small lacquered drum in a dark parlour, spun by scroll speed, with the copy beside it: too small, too dark, the animation hard to see, the copy disconnected. *v2* rebuilt it as a giant bright 3D strobe zoetrope (Ghibli Museum, Pixar), one deck of twelve cards per section of a scrolling page. The owner liked it and asked for more: "every question should be different, and I should be able to spin it and land on something... each card is a landing page element and when I click the card shoots out and I can read it. So rather than sections on a landing page it's these cards." What follows is *v3*.

### 24.2 Layout and information architecture

- **The landing page is one wheel.** There is no column of sections. One turntable fills the screen, and on it stands one printed card for every element of the page, in reading order: the hero, each feature, the product, each stat, each step, the quote, each question, the call to action, and any scene or other block. The ring grows with the content (8 to 30 cards and more): the radius follows the card count, the card keeps its size, so a big site is a bigger wheel, not smaller print.
- **A card face is a title and a figure.** Each face is the same Victorian printed card (number, the element's label such as "What it does · 2 of 3", the figure in a ruled frame, a short title, the maker's line). The full text is not on the face: it is in the card you open.
- **Every figure is different.** Each card gets its own 12-pose loop, chosen from about forty figures (a bulb glowing on, a magnifier sweeping a line of text, a door swinging open, a key turning, scales tipping, a jack-in-the-box, a paper plane looping, a clock running through twelve hours, an hourglass flipping, gears meshing, a spinning top, a juggler, a rocket, a tear-off calendar, an envelope opening, a tumbler, a bell, a kite, the moon's phases, a die, a pie filling to the stat's percentage, an odometer rolling to the stat's figure, the phone turning on its turntable, the theme artwork, a photograph panned like the view from a train, twelve frames sampled from a film, a strip's photos passing behind slits like the *Masstransiscope*...). The choice reads the card's words (a question about price gets the scales, "who" the magnifier, a step on "Day 1" the calendar, a stat in hours the clock) and the card's kind, and never repeats on one wheel.
- **The open card.** Picking a card opens it as a dialog over a dimmed table: the printed card, large, its figure still playing, and the element's complete real HTML (headline, body, buttons, the phone for the product, the answer to the question, a film's footage with its captions).
- **Furniture.** A lid band (wordmark, the site's section links, the call to action), a brass pointer over the front card, the winner's label under it with an Open button, a strobe lamp with the spin button at the lower left, a one-line hint.

### 24.3 Signature interactions and scroll behaviour

**How it feels:** a prize wheel at a fair, printed in 1870. You flick the scroll wheel or swipe and the table spins; the pointer chatters over the brass pegs; while it is fast the strobe lamp lights and every figure on the ring comes alive at once; it slows with real inertia, the pointer ticks, and it lands square on one card with a little bounce. The pointer turns gold, the lamp stays lit, the winning card leans forward and plays its loop, and its title appears under it with an Open button. Spin again, or open what you won.

**The inputs:**
- **Scroll wheel or trackpad:** each notch is a push of about 3 cards a second; pushes in the same direction build speed but saturate near 12 cards a second (a burst cannot stack without limit, and a trackpad's momentum tail only tops it up); scrolling the other way brakes and can reverse it. The page does not scroll: the wheel is the page.
- **Touch:** swipe sideways or up to spin, the release speed is the fling; tap a card to open it.
- **Mouse:** drag to turn it directly, release to fling; click any visible card to open it; click the table while it spins and a hand brake slows it onto a card.
- **The spin button (and Space):** a spin of at least one full turn that lands on a random card in about three and a half seconds. The launch speed is found by bisection on the wheel's own coasting, so it is real inertia and still ends on the chosen card.
- **Arrow keys:** turn one card; Enter opens the front card; Home and End go to the first and last.
- **Section links (nav, buttons, `#` links):** turn the wheel the short way round to that section's first card; from inside an open card they close it first.

**The strobe:** above about 3 cards a second the lamp lights and the figures step on one pose per card that passes the pointer (each card offset in its loop), so the whole ring is animated; below about 2.2 they freeze. The wheel is always drawn at its true speed, so you watch it decelerate. Nothing flashes on screen: the effect is in what each frame draws.

**The landing:** friction is mostly constant (Coulomb) with a little drag, so speed falls almost linearly: a single notch moves a card or two and lands in under a second, three notches in about two seconds, a hard spin or a fling in about three. Below 1.6 cards a second the wheel picks the card it will stop on and decelerates onto it at a believable constant rate (the pointer ticking past the last pegs), then the clapper catches: a small spring with a little overshoot. The landing is announced to assistive technology ("Card 7 of 19, Feature: Smart batching. Press Enter to open it.").

**Opening a card:** the card leaves its slot and flies at the viewer, turning edge-on, and the paper card turns the rest of the way in front of a dimmed, blurred table. Close it (close button, a click outside, Esc, a swipe down on touch) and it turns back and flies home to its slot. The wheel stays where it was. The dialog is modal, focus moves into it and is trapped there, and returns to where it was on close.

**Headline, stats, features, transitions, CTA:** the headline is the hero card's title and opens to the full `<h1>` card; each stat is its own card (a clock, a pie, an odometer, an hourglass...); each feature, step and question is its own card with its own figure; there are no section transitions, only the turning of the wheel; the call to action is a card like the others, with a sunburst, whose button is the real link.

**Real-world references:** prize wheels and roulette for the spin, the pegs and the landing; the Ghibli Museum and Pixar strobe zoetropes for a ring of figures that comes alive under a strobe; Milton Bradley and *Wheel of Life* strips for the printed look; *Masstransiscope* for the strip seen through slits.

### 24.4 Component treatments

| Element | Card face (title + figure) | Opened card |
|---|---|---|
| Hero | The headline; the theme artwork, a photograph panned, or a steaming cup | Badge, `<h1>`, body, buttons (and a hero phone, if any) |
| Intro | Its title; a bird in flight | Kicker, title, body, button |
| Each feature | Its title; a figure of its own (a coin with its number, a bell, gears...) | Section line, tag, title, body, meter |
| Product | Its title; the phone turning, or the product picture | Kicker, title, body, tags or stats, buttons, note, and the real HTML phone |
| Each stat | Its figure (value and unit); a clock, pie, odometer or hourglass | The figure set huge, its label |
| Each step | Its title; a calendar, key, walker, sunrise... | Section line, when, title, body |
| Quote | The speaker; a speaking cameo | The quote, the attribution |
| Each question | The question; a bulb, magnifier, door, key, scales... | Section line, the question, the answer |
| CTA | Its title; a sunburst | Kicker, title, the button (a real link) |
| Film scene | Its first caption; twelve frames sampled from the film | The film playing, every caption |
| Strip, gallery | Its title; its photos passing behind slits | The block's own markup |
| Orbit, other blocks | Its title; satellites circling | The block's own markup |

### 24.5 Typography and colour

As v2: **Bodoni Moda** (display), **Alfa Slab One** (labels, numbers, buttons), **Libre Caslon Text** (body), **Cutive Mono**; ivory wall `#f3ead6`, card paper `#f8f1df`, ink `#1d1611`, vermilion `#c8371e`, Prussian blue `#1f4f8a`, gold `#b8892e`, red patterned card backs. The landed state turns the pointer gold and lights the lamp; the strobe cools the room and dims its edges a little.

### 24.6 Implementation

- **Markup:** every element is an `<article class="zt-el">` with its title, label and kind as data attributes, the cards grouped in their sections in reading order. Without JavaScript, and with reduced motion, this is the page: a grid of printed cards under the section headings, each figure drawn still. With JavaScript the list stays in the page, visually hidden, for assistive technology; the article moves into the dialog when its card is opened and back when it closes. Scenes get a card built from their captions and footage; other blocks open as their own markup.
- **Turntable:** three.js; a disc and rim sized from the card count, a plinth and a brass peg per card, each card a thin box with an unlit printed face (exact colours) and a printed back, leaning back by the camera's elevation so the front card faces the camera square on. Faces are drawn into canvases a couple per frame; the twelve poses of each figure near the front are drawn into a 4 × 3 atlas shown on a plane over the face's figure frame, and the pose is chosen by moving the atlas offset (no redrawing per frame). Atlases far from the front are dropped.
- **Physics:** integrated in real time with fixed 1/240 s sub-steps (a long frame takes several steps; time is never slowed). Free: `dω/dt = −(2.9 + 0.42|ω|)·sign ω` cards a second; a wheel push adds `3 × deltaY/100` scaled by the room left under 12 cards a second; the other way brakes at 1.7×. Land: from 1.6 cards a second, constant deceleration onto the chosen card (kept between 0.8 and 2.4 × the friction). Bounce: spring k 300, damping 22. Hand brake: 5 × friction. Button and links: firmer friction (3.5) and a launch speed found by bisection on the coast. Rendering happens only when the wheel, a pose, a flight or a texture changes; the winner plays its loop twice, then the page is still.
- **Figures:** `_zoetrope-figures.ts`, one function per figure, pose 0 always a good still; the choice reads the card's words with a table of hints, then the kind's own list, then anything unused.
- **Performance:** pixel ratio capped at 2, textures sized to the card, a film's twelve frames sampled once at 320 px, the dialog's figure redrawn at 8 frames a second while it is open.

### 24.7 Anti-patterns

- **A vertical page with a wheel in it.** The wheel is the page; a scrolling column under it would make the wheel decoration.
- **Repeated figures.** Two cards with the same loop make the ring read as a pattern, not a deck of different things. Every card has its own.
- **Spinning without landing.** A wheel that drifts to a stop between cards, or that you cannot steer to a card, misses the point. It always lands square on one card, and the pointer and lamp say which.
- **Text on the turntable.** The faces carry a title and a figure only; reading happens in the opened card, at a comfortable size.
- **Real flashing.** Never flash the screen for the strobe (WCAG 2.3.1).
- **Same-as-Pop-up-book trap:** paper on a table, but the pop-up book is a hinge you open; this is a wheel you spin, and its pieces never fold.

### 24.8 Reduced-motion fallback

No turntable. The page is the list of cards: section headings, then each element as a printed card with its figure drawn still and its full text. Nothing moves; it reads as a deck of zoetrope cards laid out on the table.

### 24.9 UX signature

**You spin the page and land on what you read.** The whole site is a fairground wheel of printed cards on a strobe zoetrope, one card for every part of the page, each with a figure of its own: a bulb for one question, a magnifier for the next, scales for the third. Flick it and it spins, the pointer chattering over the pegs and every figure coming alive under the strobe; it slows, ticks, and lands with a little bounce, the lamp lit and the winner leaning forward. Click it and the card flies out, flips and opens in your hands. The feeling is *a toy you keep spinning*.

---

## 25. Flipbook

### 25.1 Origin and defining aesthetic

The flipbook is the first animation with a **linear** sequence of pictures instead of a circular one. John Barnes Linnett patented it as the *kineograph* on 18 March 1868 ([Wikipedia: Flip book](https://en.wikipedia.org/wiki/Flip_book); [Wikipedia: John Barnes Linnett](https://en.wikipedia.org/wiki/John_Barnes_Linnett)); Pierre-Hubert Desvignes is credited with a similar "folioscope" around 1860 ([Museum of the History of Science, Oxford: Kinora](https://www.mhs.ox.ac.uk/exhibits/fancy-names-and-fun-toys/kinora/)). Max Skladanowsky showed his serial photographs as a flipbook in 1894, a year before his projector; Herman Casler's Mutoscope (1894) mechanised it with the pages on a crank-turned drum, a fixture of penny arcades; Henry William Short's Filoscope (1897) held the book in a metal case with a lever (Wikipedia; Oxford, above). The German name says how it is used: *Daumenkino*, "thumb cinema" (Wikipedia).

It is also the animator's own medium. Animators "flip" and "roll" their drawings between their fingers to check timing before anything is shot, and the drawings sit on punched animation paper held by a peg bar so every page registers with the next (general knowledge; [Scout Life: how to make a flipbook](https://scoutlife.org/hobbies-projects/projects/156969/how-to-make-an-animated-flipbook/) on peg bars, binder clips and light boxes). The Walt Disney Family Museum's guide asks for at least 20 pages glued along a binding edge ([WDFM: How to Make a Flipbook](https://www.waltdisney.org/sites/default/files/2020-04/WDFM_HowToMakeaFlipbookFinal2.pdf)); guides commonly suggest 30 to 60 pages for one to two seconds, and about 12 drawings a second (or 24 pages "on twos") for smooth motion ([RAFT activity guide](https://raft.net/wp-content/uploads/2020/08/280-Animated-Flip-Books.pdf)). Living makers: Volker Gerling walks across Germany making photographic flipbook portraits (36 shots in 12 seconds) and performs them under a camera as *Portraits in Motion*, a Total Theatre Award winner at the 2015 Edinburgh Fringe ([Total Theatre](https://totaltheatre.org.uk/volker-gerling-portraits-in-motion/); [CBC](https://amp.cbc.ca/lite/story/1.3944209)); Andy Murphy (Andymation) makes long pencil flipbooks and kits ([The Kid Should See This](https://thekidshouldseethis.com/post/how-to-make-a-flipbook-andymation)). Walt Disney Animation Studios has opened its films since 2007 with a logo that evokes a flipbook (Wikipedia, above).

**Visual signatures:**
1. **Paper and pencil.** Off-white bond paper, graphite line, the animator's blue rough pencil and red key pencil, smudges, erased construction lines.
2. **Line boil.** Every page is redrawn by hand, so even a held drawing shimmers slightly from page to page (general knowledge).
3. **The stack.** Page edges visible in thin lines along the bottom and side, thinning as you go; page numbers in the corner; a clip or peg bar holding it.
4. **The bend.** A page bent under the thumb before it is let go, then the slap as it lands.
5. **Classic exercises.** The bouncing ball, the paper plane, the walk cycle, a shape morphing into another, hand-lettering that writes itself (general knowledge).

### 25.2 Layout and information architecture

- **The site is one pad.** A single pad of animation paper lies on a dark desk, centred, held at the top by a peg bar. It never scrolls away; the *pages* go. The pad is landscape on desktop and portrait on phones.
- **Each section is a run of pages.** A section owns a run of 10 to 40 pages, sized from its content. On those pages its drawing animates and its text is written in. Item lists are runs within the run (features, stats, steps, questions).
- **The page layout.** Desktop: text column on the left of the page (kicker as a pencil label, handwritten headline, body), animation field on the right inside a faint field-guide rectangle. Phone: field on top, text below. Every page carries its number in the corner and the scene and frame count in animator's notation ("SC 03 · 07/18").
- **Index tabs (nav).** Section names stick out of the pad's right edge as paper tabs at their depth in the stack; tabs of sections already flipped are gone. Clicking one thumbs straight to it. On phones the header carries the page counter and a menu.
- **The desk.** Furniture lives off the page: the wordmark and nav CTA, a pencil-written page counter ("p. 37 of 142") and a short hint at the start ("thumb the corner").

### 25.3 Signature interactions and scroll behaviour

**How scroll feels:** like thumbing a pad. Each wheel notch lets go of one page. Scrolling slowly bends the next page's corner up under your thumb; the notch releases it and it whips up and over the peg bar. Scroll fast and the pages riffle, several in the air at once, and the drawing animates; scroll back and they fall back down in order. Stop and the page under your thumb holds still (but its line still boils a little).

**What scroll drives:**
- **Page number.** Scroll position maps to a page index (about 100 px per page on desktop, 70 px on touch). Released pages fly on their own short clock, in order, so the riffle is always physical even when the scroll is smoothed.
- **The drawing.** Every page is one frame of the section's animation, drawn procedurally in pencil with a per-page seed (line boil).
- **The writing.** Headlines are hand-lettered in: each page shows a few more letters, as if the animator wrote the title across the first pages of the run. Body text follows word by word. A run always ends with held pages where everything is complete, so reading never waits on motion.
- **Stack depth.** The page edges along the bottom thin out as you go, and the index tabs disappear as their sections are flipped past.

**Headline arrival:** written by hand, a few letters per page, so the speed of your thumb is the speed of the pencil.

**Stats:** counted on paper. A small integer is drawn as tally marks, one mark per page, struck through in fives; a percentage is a pie wedge shaded a little more on each page; anything else is a hatched bar that grows. The figure is written beside it as the count reaches it.

**Feature list:** a morph. The field holds a shape that turns into the next shape across the pages between features (circle, square, triangle, star...), the classic in-betweening exercise; each feature's title is ticked off on a hand-drawn checklist in the text column as its run arrives.

**Section transitions:** there are none in the usual sense. The last page of one section is followed by the first page of the next, and you thumb straight through.

**Pointer:** grab the corner. A dog-ear on the lower right corner invites it: pressing there and dragging up peels the page with your finger, and letting go past about a third flips it (and moves the scroll by one page); otherwise it drops back. Pressing and holding the corner riffles forward like a thumb until you let go. Only that small zone takes the pointer, so a normal swipe still scrolls.

**CTA:** the last run. A ball bounces in from the edge, lands on the page's hand-drawn button and comes to rest; "The End" is written in. The button is the real link.

**Real-world references:** Volker Gerling's thumb cinema for the performance of flipping; Andymation for the pencil look and long runs; the Disney Animation opening for the flipbook as a brand moment; animation paper and peg bars for the furniture.

### 25.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Index tabs on the pad's right edge at their depth in the stack; a pencil page counter on the desk. Default nav hidden. |
| Buttons | Drawn boxes: a double pencil outline with a hatched shadow. Primary is filled with red pencil hatching. Hover shifts the hatching. |
| Hero | Run 1. The `<h1>` hand-lettered in over the first pages. Field: the theme artwork's frames drawn in graphite if the site has `theme.art`, otherwise a bouncing ball with squash and stretch. |
| Intro | A paper plane loops across the field and glides out. Kicker as a pencil label. |
| Features | A morphing shape, one form per feature, the tag written inside; a checklist of titles ticks off as each feature's run arrives, its body written underneath. |
| Product | The phone sketched in: construction lines, outline, then the screen from the device data (title, options), then a finger taps the selected option. Tags as pencil labels. |
| Stats | Per stat: tally marks, a shaded pie or a hatched bar, counted page by page; value and label written beside. |
| Timeline | A stick figure walks a ground line past posts labelled with each step's `when`; the current step's text is written below. |
| Quote | A pencil profile speaking, mouth opening and closing, a balloon growing; the quote written word by word, then the name. |
| FAQ | A question mark hops, then straightens into an exclamation mark as the answer is written in. Native `<details>` underneath for no-JS. |
| CTA | The bouncing ball lands on the button; "The End". |
| Gallery, strip, orbit, unknown | A bouncing-ball run with the default markup on the page. |
| Film and other scenes | Inserts: the scene slides up over the desk and plays full width; the pad is waiting underneath, on the next section's first page, when it has passed. Unknown block types are treated the same way. |

### 25.5 Typography and colour

- **Display:** **Caveat** (variable 400 to 700), a quick, slanted pencil hand for headlines.
- **Body:** **Kalam** (300, 400, 700), an upright, legible print hand for body copy.
- **Mono:** **Courier Prime** for page numbers and animator's notation.
- **Palette:** desk `#1f2427` (dark slate, a light box's surround), desk text `#e9e4d8`; paper `#f7f3ea`; graphite `#2f2f33`; blue rough pencil `#3f6fc4`; red key pencil `#c4452e` (accent); paper shadow and edges in warm greys.

### 25.6 Implementation

- **One pad stage, fixed.** A canvas for the stack and resting page, the resting page's text as real DOM laid exactly over it, and a second canvas above for pages in flight (so a flying page can cover the text of the page beneath it).
- **Page textures.** Each page is drawn into an offscreen canvas (paper, field guide, drawing for that frame). When a page leaves, its text is baked into its texture from the live DOM: each character's layout position (`offsetLeft`/`offsetTop`, unaffected by transforms) and computed font, so the flying page matches the text it carried. A small cache keeps recent pages.
- **Peel.** A flying page folds along a line that starts across the lower right corner and sweeps up to the hinge, turning level as it goes. The part on the hinge side is drawn flat; the part beyond the line is reflected over it (one affine reflection in canvas 2D) and shows the back of the sheet, paper with a faint mirror of the drawing, lit along the fold and casting a soft shadow. Where the sheet has lifted, the next page shows through with a shadow along the fold. When the fold reaches the hinge the whole sheet lies over the top and fades. (A first version bent the page in perspective slices about the hinge; seen from above it read as a page tilting towards you rather than turning, so it was replaced.)
- **Flights.** Target page = scroll / step. Each page has a flip value 0..1 that eases to 0 or 1 at a fixed speed, in order (a page lifts only after the one above it is under way), so fast scrolling gives a riffle and scrolling back drops pages in reverse order.
- **Sections:** each block becomes a spacer `pages × step` tall; its text face is fixed over the page and shown while its run is under the thumb. Scene sections keep their own height and the pad steps aside.
- **Performance:** canvases at a capped pixel ratio, drawings cached per page, the loop idles when no page is moving and nothing is boiling on screen.

### 25.7 Anti-patterns

- **The magazine page-turn.** A two-page spread with a left-to-right page curl (turn.js, StPageFlip and their kin, built to show catalogues as books: [StPageFlip](https://www.cssscript.com/book-page-flip-animation/)) is a digital brochure, and it is also what the pop-up-book style does with spreads. The flipbook is a *pad*: one page at a time, many pages, small changes between them.
- **Slides with a page-turn transition.** If each page holds a different layout, it is a slide deck. Pages in a run must differ by small increments, so flipping animates.
- **A smooth tween.** Interpolating the drawing continuously between pages kills the medium. The drawing changes only when a page changes.
- **Same-as-Pixel-art trap:** both step frames. Pixel art is a game world you walk through, timed by turns; the flipbook is paper you thumb, timed by your thumb, with pencil line and physical page flights.
- **Same-as-Split-flap trap:** a split-flap flap also rotates about a horizontal hinge. Flaps are rigid and mechanical, all at once; flipbook pages bend, curl and fly one after another, and carry drawings.
- **Same-as-Comic-book trap:** comics guide the eye across panels in space. The flipbook never shows two frames side by side; time replaces space.

### 25.8 Reduced-motion fallback

No flights, no riffle, no writing-in. Each section is shown as **one finished pad page** in a normal reading flow: the last drawing of its run, the full text, the page number and the field guide. The technique stays recognisable as a still: a page torn from a flipbook.

### 25.9 UX signature

**Your scroll is the thumb on the corner of a pad.** The whole site is one pad of animation paper clipped to a peg bar. Each notch of the wheel lets go of a page, which peels up from the corner and folds over the top, and the drawing underneath has moved on a little: a ball bounces, a paper plane loops, a phone is sketched in line by line, tally marks count the stats, a stick figure walks past the milestones. Headlines are lettered in by hand a few letters per page, so your thumb is the pencil. Scroll fast and the pages riffle into motion; scroll back and they fall back in order; grab the corner and flip one yourself. The stack thins as you go and the index tabs disappear behind you, until the last page says "The End" over the button. The feeling is *handmade time*: the visitor animates the site with their own thumb.

---

## Contrast table: the two signatures against their nearest neighbours

| | **Zoetrope** | **Flipbook** | Kinetic type | Pixel art | Split-flap |
|---|---|---|---|---|---|
| **One scroll notch =** | Adds spin to a prize wheel of cards; it slows with inertia and lands on one | Releases one page | Skews and stretches words with speed | One step of a walking sprite | Advances the station clock |
| **Time feel** | Fling, coast, tick, land with a bounce; figures alive while fast | Discrete pages, each released page whips over | Spring back when you stop | Turn-based, 8 to 12 fps | Events with a mechanical riffle |
| **Spatial logic** | The whole page is one ring of element cards on a turntable | A pad seen from above, pages hinged at the top | Full-bleed type | Side-scrolling level | A fixed board of rows |
| **Persistence** | One wheel, every element always on it | One pad; pages leave, the stack thins | None | Avatar and HUD | Board persists, rows shift |
| **Headline arrives by** | Landing on the hero card and opening it | Hand-lettered, a few letters per page | Inflates across the screen | Typewriter in a dialog box | Flaps riffle to the letters |
| **Stats as** | A card each: clock, pie, odometer, hourglass | Tally marks, pie shading, a hatched bar, counted per page | Huge type | RPG bars | Board cells |
| **Feature list as** | A card each, every one with its own figure | A shape morphing between features; checklist ticks | Marquees | ITEM GET! | Departures |
| **Section transition** | None: the wheel turns to the next card | None: the next page is the next section | Type surge | Mosaic or iris | Whole board re-flips |
| **Pointer** | Drag or fling to spin; click a card to open it | Grab the corner and flip; hold the edge to riffle | Hover skew | Menu cursor | Sound toggle |
| **CTA** | A card on the wheel; the button inside is the real link | Ball lands on the drawn button, "The End" | Big type | CONTINUE? | Boarding row |
| **Reduced motion** | The deck of cards as a list | A finished pad page per section | Static type | Plain page | Instant board |
