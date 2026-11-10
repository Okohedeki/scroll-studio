> Style research from DesignAI by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. Licensed under the GNU AGPL-3.0 with additional terms (NOTICE.md): credit it with this notice, unchanged, wherever it is used, and don't present it as your own work.

# DesignAI style research: styles 26 and 27

**Pop-up book, Rotoscope**

Prepared 2026-10-12 for the DesignAI engine, as part of the animation-technique batch (styles 22 to 27). These two styles start from a physical or photographic technique and ask the same question the earlier research asked: **what does one notch of the scroll wheel mean here?** A pop-up book is a machine whose only input is the angle the page is opened to. Rotoscoping is a process whose input is live footage and whose output is a drawing. In both, the visitor's scroll is given that input. Fonts and colours come after.

> **How to read the citations.** URLs are inline. Where a claim comes from general knowledge and not from a source I retrieved, I say "(general knowledge)". Where I only saw a search engine's excerpt of a page (the page itself refused to load), I say "(search snippet)". Treat named works as references to check.

---

## Cross-cutting principle: two more scroll models

| Style | What scroll *is* | Time quantisation | Motion curve | Spatial axis | Primary renderer |
|---|---|---|---|---|---|
| Pop-up book | The opening angle of a board page. One input drives every fold, tab and wheel on the spread | Continuous; each spread rests open while its mechanism (tab, wheel, flap) runs, then the next page turns | Paper spring: an eased turn that settles with a small overshoot; tabs slide linearly | A real 3D object on a table: an upright back page and a flat base page, pieces standing between them at measured depths from the gutter | CSS 3D transforms over real HTML (no canvas), one pinned book |
| Rotoscope | How far the tracer's hand has got: the shot moves from live footage through roughs and clean ink to ink and paint, and back to pencil as you leave | Two clocks. The footage runs in real time and every drawing changes **on twos** (12 a second); scroll changes the *stage of the trace*, never the frame | Stepped: line boil re-draws on twos; the develop stages cross-fade region by region (strong edges first, paint in blots) | A fixed light table: the projected plate fills the viewport, pegged paper sheets carry the text | One WebGL canvas (edge detection, posterisation, boil) under DOM sheets |

The table matters because the batch is crowded with frame-based techniques. `flipbook` and `zoetrope` make the scroll a frame counter; `anime-intro` makes it a playhead. Rotoscope deliberately does **not**: its footage plays on its own clock, and scrolling changes how *drawn* it is. The pop-up book is the only style in the engine whose page is a single physical object with a hinge, where the scroll is an angle.

---

## 1. Pop-up book

### 1.1 Origin and defining aesthetic

Movable books are older than printed books. The Benedictine monk Matthew Paris put volvelles (rotating paper discs) in his *Chronica Majora*, begun around 1240, to work out holy days, and is usually called the first known movable-book maker ([Wikipedia: Pop-up book](https://en.wikipedia.org/wiki/Pop-up_book); [Popuplady history](https://popuplady.com/?p=93)). Ramon Llull is said to have used volvelles in the early 14th century, though no example made by him survives ([Wikipedia](https://en.wikipedia.org/wiki/Pop-up_book)). Children's movables begin with Robert Sayer's harlequinades from about 1765: two engraved sheets, the second cut and hinged so each flap lifts on its own, each verse ending with an instruction to turn a flap ([Bodleian Libraries](https://blogs.bodleian.ox.ac.uk/theconveyor/harlequinades/)).

The 19th century built the mechanisms. Dean & Son claimed in 1860 to be the "originator" of movable books; its New Scenic Books of about 1856 had ribbon-linked cut-out layers that rise when a flap is lifted, "probably the first" pop-ups in today's sense, and it introduced tab-operated "living pictures" in the 1860s ([UNT Libraries: Dean & Son](https://exhibits.library.unt.edu/pop-ups/dean-and-son/)). Lothar Meggendorfer (1847 to 1925) made up to about 200 movable books from 1878; one tab in his books drives a set of levers that animate several figures at once ([UNT: Meggendorfer](https://exhibits.library.unt.edu/pop-ups/lothar-meggendorfer/)). The V&A holds a 1979 reproduction of his *International Circus* (first published 1887) and calls him the "chief innovator" of mechanical toy books ([V&A](https://collections.vam.ac.uk/item/O1527532)). Ernest Nister's Nuremberg firm (c. 1891 to 1900) refined "venetian blind" dissolving pictures into four or five slats, and made panorama books whose scenes, tabbed to the facing page, **stand up automatically when the page turns** ([UNT: Nister](https://exhibits.library.unt.edu/pop-ups/ernest-nister/)).

Twentieth-century pop-ups made the page-opening the engine. S. Louis Giraud's Bookano annuals (1929 to 1949) were sold as "living models" that unfold across a spread and can be seen from several angles ([UNT: Giraud](https://exhibits.library.unt.edu/pop-ups/s-louis-giraud/)). Vojtěch Kubašta (1914 to 1992), trained as an architect and a designer of puppet-theatre sets, made stage-like scenes for the Prague publisher Artia: **text parallel to the spine, and a page that opens to a right angle to show the scenery** ([The Henry Ford](https://www.thehenryford.org/collections/explore/articles/vojtech-kubasta-beyond-borders)). Waldo Hunt founded Graphics International in 1965 partly because Kubašta's books could not be exported to the US, then Intervisual ([UNT](https://library.unt.edu/rarebooks/exhibits/popup2/present.htm)). Jan Pieńkowski's *Haunted House* (Heinemann, 1979), engineered by Tor Lokvig, won the Kate Greenaway Medal and had sold over a million copies by 1992 ([Wikipedia: Pieńkowski](https://en.wikipedia.org/wiki/Jan_Pie%C5%84kowski); [UNT](https://library.unt.edu/rarebooks/exhibits/popup/haunted.htm)). Robert Sabuda won the Movable Book Society's first Meggendorfer Prize in 1998 ([Popuplady](https://popuplady.com/?p=93)); with Matthew Reinhart he made the *Encyclopedia Prehistorica* volumes (search snippet: [BookPage](https://www.bookpage.com/interviews/20107-robert-sabuda-matthew-reinhart-childrens/)). David A. Carter's *One Red Dot* is a book of paper sculptures in a five-book colour series (search snippet: [MIT Press Bookstore](https://mitpressbookstore.mit.edu/book/9780689877698)).

The Smithsonian Libraries surveyed the field in "Paper Engineering: Fold, Pull, Pop and Turn" (2010 to 2011), grouping the books into movables, pop-ups, folding mechanisms and fantastic forms ([Smithsonian Libraries](https://library.si.edu/digital-library/exhibition/paper-engineering)).

**Visual signatures:**
1. **The gutter is the origin of everything.** Every piece is glued across or near the fold and is driven by the page opening (general knowledge; the Popuplady glossary defines a pop-up as an illustration that rises "when activated by the opening of a page", [glossary](https://popuplady.com/?p=95)).
2. **Parallel and V-folds.** A parallel fold's creases run parallel to the spine; it is a parallelogram that "lies flat at 180° and only comes into dimension when held at less than 180°". A V-fold's three creases meet at one point on the gutter ([Georgia Tech Paper Museum](https://paper.gatech.edu/index.php/kinetic-joy/physics-paper-engineering)).
3. **90° and 180° designs.** Pieces cut from the base page are fully 3D at 90° and lie flat again at 180°; pieces added on top are fully extended at 180° ([Utah Old and Rare Books](https://oab.lib.utah.edu/?p=3478)). Kubašta's stage books are the 90° kind.
4. **Movables alongside pop-ups:** pull-tabs, volvelles and wheels seen through die-cut windows, lift-the-flaps, slat transformations ([Popuplady glossary](https://popuplady.com/?p=95)).
5. **Die-cut paper with a margin round the cut, flat litho colour, board pages, cast shadows** (general knowledge). Printing ranged from German chromolithography to Giraud's cruder photolitho ([UNT](https://exhibits.library.unt.edu/pop-ups/s-louis-giraud/)).
6. **It is hand-made.** Modern pop-ups are die-cut and assembled by hand, around a thousand workers on one title (search snippet: [Reading Rockets](https://www.readingrockets.org/videos/meet-authors/made-china)).

### 1.2 Layout and information architecture

- **The site is one book.** A pinned table with one book on it. The first hero is the **cover** (cloth boards, a pasted paper label with the headline, a gold seal for the badge), read straight down from above, so the `<h1>` is the first thing seen and fully legible. Each following section is a **spread**.
- **A spread is a 90° stage (Kubašta).** The **wall** (the upright back page) carries the reading text, printed flat and facing the visitor. The **floor** (the base page) carries the pieces, printed captions and tabs. Pieces stand between them at measured depths from the gutter. This reads far better on a screen than a 180° book seen from above, where everything standing is edge-on to the camera.
- **Reading order:** kicker and title, then body, then the pieces. Spread folios are printed in the corners (pp. 4–5), and the running head counts them.
- **Long content paginates like a book.** FAQs run three flaps a spread with "continued" on the next; anything the book cannot bind (a film scene, a gallery) sits between volumes as a loose plate, and the book after it starts with its own cover.

### 1.3 Signature interactions and scroll behaviour

**How scroll feels:** like opening a heavy board book one page at a time. The page resists, swings, and settles with a little spring; the scene stands up as it does.

**What scroll drives:**
- **The opening angle and nothing else.** One notch turns the board a few degrees. Every piece is a child of the page it stands on and takes its angle from the angle between its two pages: the turning leaf folds the old scene flat against the wall *while* the new scene rises out of the gutter under it. That is the real mechanism of Nister's panoramas, where the scene "stands up automatically when the page turns" ([UNT](https://exhibits.library.unt.edu/pop-ups/ernest-nister/)).
- **Parallel-fold geometry, kept honest.** A piece at depth *d* stays parallel to the wall at every angle (the parallelogram linkage). A piece is never taller than the floor in front of it (1 − *d*), so it folds flat inside the closed book: the same rule a paper engineer obeys ([Georgia Tech](https://paper.gatech.edu/index.php/kinetic-joy/physics-paper-engineering)).
- **The mechanism runs while the spread rests open.** After a page has turned, the next stretch of scroll works the spread's movable: a pull-tab pushes cards forward one at a time, strips with the figures rise out of slots, a wheel turns the timeline through a window, flaps lift for answers, a sunburst turns behind the call to action.
- **Camera:** top-down on the closed cover, tilting to the stage as the cover rises. A small pull-back during each turn. The pointer orbits the table a few degrees, enough to show the depth.

**Headline arrival:** the headline is **die-cut**: cut out of card with a paper margin round every letter and stood up on parallel folds, the plain words on one piece and the emphasised words on a second piece in front. It rises out of the gutter with the page, and its letter-shaped shadow lengthens on the floor as it stands.

**Stats:** **pull-tabs and slots.** Each figure is printed on a strip hidden in a slot cut in the wall; its tab pokes out of the floor's front edge. As you scroll, the tabs pull out one after another and the strips rise. Not a count-up: the number is printed, and is revealed by a mechanism.

**Feature list:** **stand-up cards with a slide.** One die-cut card per feature (arched, rounded and square tops, each with its colour band and numeral), staggered at two depths. A pull-tab slides the active card forward on its slot. On a phone the cards stand one behind another, and each in turn folds forward flat to reveal the next.

**Section transition:** **the page turn is the transition**, and it is mechanical: the leaf that turns is the floor of one spread and the wall of the next, so one motion folds one scene away and builds the other.

**Hover / pointer:** a small orbit of the camera around the table; pull-tabs and the wheel can be **grabbed and dragged**. Dragging writes to the scroll position, so gesture and scroll never disagree, and nothing traps the page (the tab is the only `touch-action: none` area).

**CTA:** the last spread. A turning sunburst (a half-wheel behind the title) and the button stood up at the front as a ticket: **the last tab**.

**Real-world references:** Lynn Fisher's 2020 lynnandtonic.com refresh built a pop-up-book header with gradient fold shading and single-axis pull-tabs ([case study](https://lynnandtonic.com/thoughts/entries/case-study-2020-refresh/)). Codrops' PFold paper unfolding ([2012](https://tympanus.net/codrops/2012/10/17/pfold-paper-like-unfolding-effect/)) and 3D Book Showcase ([2013](https://tympanus.net/codrops/2013/01/08/3d-book-showcase)) show CSS 3D paper. Google's "Paper Planes" folds paper in WebGL ([Google](https://experiments.withgoogle.com/paper-planes)). I found no award-winning scroll site built on pop-up mechanics.

### 1.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Ribbon bookmarks hanging from the top edge (the contents); the active one drops lower. The running head names the book in small caps. A page count ("pp. 8–9") in the corner. |
| Hero | The cover: cloth boards with a gilt rule, a pasted label (title, rule, lede, buttons), a gold scalloped seal for the badge, "scroll to open the book" in gold. A hero image becomes a tipped-in plate on the label. A later hero is a title spread with a framed picture standing behind die-cut words. |
| Buttons | Printed paper labels with a hard bottom edge that press down; the primary is vermilion. |
| Intro | Wall: kicker, lead paragraph, a printed sun. Floor: the die-cut headline in two layers in front of two die-cut hills. |
| Features | Stand-up cards on parallel folds, two depths, a pull-tab that slides the active one forward; a printed wallpaper backdrop. |
| Product | Wall: the copy and printed labels for tags. Floor: the phone on a stand-up card in front of a mustard halo; a pull-tab moves the selection down the phone's options. |
| Stats | Slots in the wall with strips that rise; tabs at the front edge; bunting standing behind. |
| Timeline | A volvelle: a paper wheel turning behind a window, one step per sector; flags stand along a printed path on the floor, the current one darker. Without JS (or with reduced motion) the steps print as a list. |
| Quote | A speech balloon cut from card, standing; the attribution printed on the floor. |
| FAQ | Lift-the-flap: each question on a flap hinged at the top; the answer printed underneath, with the question repeated. Real `<details>`. |
| CTA | Die-cut title, a turning half-sunburst behind it, the button as a standing ticket. |
| Unbound blocks / scenes | Loose plates between volumes: a paper sheet on a cloth border. |
| Footer | A colophon in italic on the table. |

### 1.5 Typography and colour

- **Display:** **Caprasimo**, a chunky 1970s storybook serif that survives being die-cut with a fat paper margin.
- **Body:** **Literata**, a book face (variable optical size), for the wall text and folios.
- **Labels:** **Courier Prime** for tab instructions ("PULL", "TURN THE WHEEL").
- **Palette:** board stock `#f6eddb`, print ink `#251d17`, vermilion `#c23b23`, cobalt `#2b5797`, mustard `#e7a92e`, leaf green `#2f7a5c`, teal cloth `#1d4a52`, gold foil `#d9b462`, the table `#2a2421` under a warm lamp pool. Flat colour only, as in offset litho; paper grain from an SVG noise.

### 1.6 Implementation

- **CSS 3D, not WebGL**, so every word is real, selectable, accessible text, and the still version works without JavaScript. The book is one `preserve-3d` tree: table → camera → book → spreads → wall, floor → pieces.
- **One variable per spread drives it all.** The runtime writes the two leaf angles (`--tw`, `--tf`) on each spread; CSS derives the opening angle `--a` and every piece's rotation (`rotateX(a − 180°)` about its base, which keeps it parallel to the wall), its cast shadow (a copy rotated back onto the floor and stretched by `sin(a)`), and its shading.
- **Leaf stacking:** each leaf is offset along its own normal, so a stack of flat leaves and a stack of upright leaves both sort correctly. Backs are `backface-visibility: hidden`; cards that can lie face up get a printed back.
- **Only the spreads either side of the moving leaf are rendered**; the rest are `visibility: hidden`, so the layer count stays small on phones.
- **Spring:** the displayed leaf angle follows the scroll target with a damped spring (slight overshoot), snapped on the first frame so a reload lands in place.
- **Camera fit:** the book's size is solved by projecting the wall's top and the tabs at the front edge through the stage's perspective, so the open book fills the space under the running head on any screen; phones get a portrait book.
- **Accessibility:** the cover holds the `<h1>`; reading order is title, body, pieces; tab and wheel drags are optional (scroll does the same); FAQ is native `<details>`.
- **Reduced motion and no JS:** no binding, no turning. Each spread is a still, fully opened diorama in CSS 3D, stacked down the page; strips raised, wheel printed as a list.

### 1.7 Anti-patterns

- **A page-curl effect on a normal page.** Critics have said the skeuomorphic curl "just slows the reader down for the sake of showing off" ([Scientific American, 2013](https://www.scientificamerican.com/article/apple-shouldnt-make-software-look-like-real-objects)). The page turn here is not decoration: it is the mechanism that builds the scene.
- **Pieces that slide or fade in independently of the page.** If a piece moves while the page is still, it is a parallax layer, not a pop-up. Only the pull-tab stretch moves things on an open spread, and there's a visible tab for it.
- **Text printed on the pieces at grazing angles.** Reading text belongs on the wall, facing the visitor (Kubašta put text parallel to the spine).
- **Same-as-comic-book trap:** both turn pages. Comic-book reads panel to panel inside a flat page and zooms out before turning. The pop-up book's page is an object in 3D whose angle *is* the content.
- **Same-as-flipbook trap:** flipbook flips many thin pages fast to animate a drawing. Here one stiff board page turns per section, slowly, and the animation is the paper engineering.

### 1.8 UX signature

**You open a book, and the scene stands up.** A cloth-bound book lies closed on a lamp-lit table with the headline on its cover. Scroll, and the cover swings up and becomes the back wall of a little paper stage while the next scene rises out of the gutter on parallel folds, every piece leaning with the page and throwing a longer shadow as it stands. Each turn of the page folds one scene flat and builds the next in the same motion. While a spread is open, the scroll works its machinery: tabs pull figures out of slots, a wheel turns the steps through a window, flaps lift on the answers. The button is the last tab. No other style has a single physical object with a hinge whose angle is the scroll.

---

## 2. Rotoscope

### 2.1 Origin and defining aesthetic

Max Fleischer patented the rotoscope as US 1,242,674, "Method of producing moving-picture cartoons", filed December 6, 1915 and granted October 9, 1917. A projector on an inclined platform shows filmed live action one frame at a time onto a screen; the artist traces each frame onto paper, then advances the film with a pull-cord and ratchet ([Google Patents](https://patents.google.com/patent/US1242674A/en)). Dave Fleischer, who had worked as a clown, was filmed in a clown suit; the traced figure became Koko the Clown of *Out of the Inkwell* (from 1918) ([Fleischer Studios](https://fleischerstudios.com/origins); [Wikipedia: Rotoscoping](https://en.wikipedia.org/wiki/Rotoscoping)). The first test was "only about one minute long, and took a year to create" ([Fleischer Studios](https://fleischerstudios.com/origins)). Cab Calloway's dancing was rotoscoped for Betty Boop's *Minnie the Moocher* (1932) and *Snow-White* (1933) ([Kozak's Classic Cinema](https://www.kozaksclassiccinema.com/betty-boop-the-cab-calloway-cartoons-1932-1933/)).

Disney used live action as reference: Marge Champion, 13 when scouted, was filmed for Snow White and her movements were rotoscoped as "detailed reference" ([Cartoon Brew](https://www.cartoonbrew.com/rip/marge-champion-actor-and-dancer-who-was-model-for-snow-white-dies-at-101-197986.html)); stills show "thin, black outlines penciled over the actual image" ([Library of Congress](https://blogs.loc.gov/music/2018/06/marge-champion-fairest-of-them-all-the-towering-talent-behind-disneys-snow-white-and-the-seven-dwarfs/)). Ralph Bakshi's *The Lord of the Rings* (1978) printed each live-action frame and placed it behind a cel to paint; its crowds are "solarized" live action, and the rotoscoping "varies from strongly drawn to almost absent" ([Wikipedia](https://en.wikipedia.org/wiki/The_Lord_of_the_Rings_(1978_film))); Bakshi later said he should have used the footage as a guide rather than tracing it (same source). *Wizards*, *American Pop* (1981) and *Fire and Ice* (1983) used it heavily ([Wikipedia: Rotoscoping](https://en.wikipedia.org/wiki/Rotoscoping)).

a-ha's "Take On Me" (1985, directed by Steve Barron) had Michael Patterson draw over segments and Candace Reckinger do the mattes: about 3,000 frames over 16 weeks. The pencil-drawn hero's hand reaches out of the comic page to pull the reader in, and a portal is real on one side and drawn on the other ([Wikipedia: Take On Me](https://en.wikipedia.org/wiki/Take_On_Me); [befores & afters](https://beforesandafters.com/2020/02/20/a-has-rotoscoped-1985-music-video-for-take-on-me-has-been-watched-a-lot/)). Its drawn lines "visibly shake, smudge, and fade" ([Animated](https://animated.substack.com/p/a-ha-take-on-me-how-a-pencil-sketch)). Bob Sabiston's Rotoshop interpolates hand-drawn vector shapes over video ([Wikipedia: Sabiston](https://en.wikipedia.org/wiki/Bob_Sabiston)); Richard Linklater's *Waking Life* (2001) gave individual characters to different animators, so the style keeps changing ([Wikipedia](https://en.wikipedia.org/wiki/Waking_Life); [frieze](https://frieze.com/article/walking-line)), and *A Scanner Darkly* (2006) used about 30 new artists in five teams, with the shifting "scramble suit" ([Wikipedia](https://en.wikipedia.org/wiki/A_Scanner_Darkly_(film))). Jordan Mechner filmed his brother running and jumping and drew over it for *Prince of Persia* (1989) ([Engadget](https://www.engadget.com/2011-03-15-jordan-mechner-on-prince-of-persia-respecting-game-writers.html)); Éric Chahi overlaid video for *Another World* (1991) ([Wikipedia](https://en.wikipedia.org/wiki/Another_World_(video_game))). Amazon's *Undone* (2019, Hisko Hulsing, rotoscoping by Minnow Mountain) was the first episodic series made this way ([Animation Magazine](https://animationmagazine.net/2020/08/director-hisko-hulsing-discusses-the-cutting-edge-hybrid-animation-of-amazons-annie-nominated-undone)).

**Visual signatures:**
1. **Real motion under a drawn surface.** The weight and timing are live action's; the surface is ink.
2. **Line boil.** The wobble of hand-drawn lines when every frame is redrawn, most visible on still things ([TV Tropes](https://tvtropes.org/pmwiki/pmwiki.php/Main/LineBoil)); Squigglevision loops five drawings to make it on purpose ([Fox Renderfarm](https://www.foxrenderfarm.com/share/what-is-squigglevision/)).
3. **On twos:** a new drawing every second frame, 12 a second ([Wikipedia: Inbetweening](https://en.wikipedia.org/wiki/Inbetweening)).
4. **A ladder of abstraction:** from almost-live (Bakshi's solarised crowds) through pencil (Take On Me) to flat colour shapes (Scanner Darkly).
5. **Two worlds in register:** the reference and the drawing; Take On Me's portal and reaching hand.
6. **The animation desk:** light table, peg bar registering the sheets ([FutureLearn glossary](https://ugc.futurelearn.com/uploads/files/26/1e/261e85c8-3b25-41eb-895e-c76b4ddc4eba/GLOSSARY.pdf)), onion skin (see-through views of neighbouring drawings, [GarageFarm](https://garagefarm.net/blog/mastering-onion-skinning-in-animation)), the exposure sheet with a row per frame ([Toon Boom](https://docs.toonboom.com/help/harmony-12-2/premium/basics/xsheet-and-timeline.html)), the field guide and timing charts (general knowledge).

### 2.2 Layout and information architecture

- **The site is a reel of shots on a light table.** Each section is a **shot** pinned on the table. Its **plate** (the reference footage) fills the viewport under the paper: the hero's video or photo, `theme.art` (Halcyon's steaming cup), a product shot, a scene's film. A text-only shot traces the page's own footage (its first photo or poster), framed differently (wide, a close-up on the steam, the cup, the rim, the side), the way a film covers one action from several set-ups. Only a page with no media at all falls back to a **type plate**: its heading set huge, white on black, traced.
- **Text lives on pegged sheets of animation paper:** three peg holes along the top, a slate line ("SC 03 · What it does · Model sheet"), hand lettering, a drawn border that boils.
- **Contents are an exposure sheet** down the right edge: one row per shot, the current one ringed in red pencil, a frame counter that ticks in twos and the name of the stage the trace is at (live action, roughs, clean-up, ink & paint, onion skin).

### 2.3 Signature interactions and scroll behaviour

**How scroll feels:** you are the tracer's hand. The film keeps running; you decide how much of it has been drawn.

**What scroll drives:**
- **The stage of the trace, not the frame.** One notch moves the shot along the rotoscope process. Entering a shot, the footage is **live** (the projection on the paper, warm and slightly faded); blue-pencil **roughs** appear on its strongest edges, doubled and wandering, with the field guide faintly behind; **clean-up** inks the strong edges first, then the weaker ones; **ink and paint** floods posterised flat colour in blot by blot until the photo is gone. The shot holds there while you read. Leaving, the paint drains and the line drops back to pencil.
- **Onion skin as persistence.** The drawing you just left stays as a **red-pencil onion skin** over the next shot's live footage, fading as the new trace begins. That is the only thing that survives between sections, and it is the animator's own tool for seeing the previous drawing.
- **Two clocks.** The footage plays in real time, but the canvas only takes a new drawing on twos: the frame changes 12 times a second and the line boil re-seeds with it. Scroll never scrubs the film.
- **Boil everywhere a hand would have drawn:** the edges in the plate, every border (an SVG displacement filter whose seed changes on twos), and the lettering itself (Shantell Sans' bounce axis is redrawn on twos).

**Headline arrival:** lettered in. First a blue-pencil outline (hollow letters), then ink fills it, all while the lettering boils.

**Stats:** **key numbers on timing charts.** Each figure is circled in red the way a key drawing is numbered, above an inked timing chart (the ladder of inbetween ticks, spaced for an ease), with its label as the note.

**Feature list:** **key drawings.** A model sheet: one panel per feature, each a different key of the same footage (different frames, different framing), inked in red and black, with the feature as the animator's note under it.

**Section transition:** **re-trace with onion skin.** The outgoing drawing falls back to pencil, the next shot's footage comes up live under it, and the old lines stay on in red until the new trace is under way.

**Hover / pointer:** **your motion is traced.** An inked cursor redraws the pointer on twos, two onion-skin ghosts in blue pencil behind it. On touch, a drag leaves an inked stroke that boils and fades. The product's phone is the one thing that is **never traced**: crisp live action in a drawn world, tagged "Live action · not traced", with an inked outline that wobbles round it on twos and never quite fits.

**CTA:** **step back out of the drawing.** The final shot is ink and paint; the button is drawn (ink border, boiling, hand-lettered). Hover or focus it and it develops into a crisp, solid, real button, while the plate behind it develops back to live footage. Take On Me in reverse.

**Real-world references:** I found no rotoscoped scroll site. The closest is Ribbit's Awwwards case study, a scroll-scrubbed hand-animated sequence ([Awwwards](https://www.awwwards.com/ribbit-case-study.html)). The CSS-Tricks "Squigglevision" technique switches feTurbulence and feDisplacementMap filters to make line boil ([CSS-Tricks](https://css-tricks.com/?p=311126)).

### 2.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | The exposure sheet: SC numbers and nav labels in mono, the current row ringed in red pencil. The head shows the frame counter (on twos) and the trace stage. Phones keep the head and counter. |
| Hero | Shot 01, tone "paint" (navy, teal, ochre, cream): the plate fills the screen and develops on load from live to ink and paint; the headline is lettered on a pegged sheet on the left. |
| Buttons | Drawn: an ink border that boils, hand lettering; the primary is painted vermilion once the cel is. |
| Intro | Close-up (the steam), tone "graphite": ink line and diagonal hatching on paper. |
| Features | A model sheet of key drawings, tone "ink" (black line, a red wash). |
| Product | Tone "flat" (plum, red, ochre: Scanner Darkly); the live phone is untraced, with its wobbling outline. |
| Stats | Circled key numbers on timing charts, on sheets over a dimmed graphite plate. |
| Timeline | The exposure sheet as a table: Frame (the "when"), Action (title and note), and a Dial column. |
| Quote | Tone "kodalith": two-level black and paper, Bakshi's high contrast; the quote lettered as dialogue. |
| FAQ | Retake notes: numbered R1, R2..., questions lettered, answers in hand. Native `<details>`. |
| CTA | Final frame: the drawn button that develops into a real one. |
| Scenes, galleries, strips | Traced where they stand: a film scene is projected live and inked as it plays; gallery and strip photos are inked and painted. |
| Footer | Mono colophon on paper under a ruled edge. |

### 2.5 Typography and colour

- **Lettering and body:** **Shantell Sans** (Shantell Martin's marker hand). Its Informal and Bounce axes make one family do two jobs: fully informal and bouncing for the lettering, near-formal and still for body notes. The bounce axis redrawn on twos is the lettering's boil.
- **Slates and the X-sheet:** **Martian Mono**.
- **Palette:** animation bond `#f6f2e8` on a warm light table, ink `#18171c`, blue pencil `#3a66c8`, red pencil `#c8372a`. Paint palettes per tone: paint (`#1c2340` `#2f6a70` `#e3a548` `#f7efdf`), flat (`#2b1f33` `#b8382c` `#efb457` `#fbf3e3`), graphite (pencil greys), kodalith (black and paper).

### 2.6 Implementation

- **One WebGL canvas** fixed behind the page; sheets are DOM above it. The owner shot's plate is drawn full-screen; key drawings, film scenes and gallery photos are drawn at their own rects.
- **Edges:** a Sobel gradient at a radius scaled to the source's pixel size, on the boil-displaced footage, gives one line per edge whichever side is dark (the XDoG idea of thresholded edges for an ink look, [Winnemöller et al. 2012](https://www.cs.princeton.edu/courses/archive/spring15/cos426/papers/Winnemoeller12.pdf); posterised shading as in Real-Time Video Abstraction, [Winnemöller, Olsen and Gooch 2006](https://research.adobe.com/publication/real-time-video-abstraction)). The clean-up threshold falls as the stage advances, so strong edges ink first.
- **Roughs:** a second, offset, sparser pass with graphite grain, in blue.
- **Paint:** luminance posterised into the tone's four colours, flooded through a low-frequency noise threshold so it arrives in blots.
- **Boil:** a value-noise displacement of the sample coordinates, re-seeded on twos; the same seed drives the SVG border filter and the lettering's bounce.
- **Footage:** theme.art frames repacked into a grid (a tall strip can exceed a phone's texture limit) and drawn at twice size with smoothing; videos and 2D canvases uploaded only on twos and only when near the viewport. The canvas renders on twos plus whenever the page scrolls.
- **Phones:** device pixel ratio 1, smaller line radius and boil; sheets dock at the bottom with the plate above.
- **Accessibility:** every word is real text in reading order; the canvas and plates are `aria-hidden`. The boil is a few pixels of displacement, never a luminance flash; no full-screen strobe.
- **Reduced motion:** no pinning, no boil, footage held on one frame; every plate is drawn once as a finished ink-and-paint still. Without JavaScript the plates show as high-contrast inked stills (CSS filters) behind the sheets.

### 2.7 Anti-patterns

- **A toon filter over a normal page.** If scroll doesn't change the trace, it's a filter, not rotoscoping.
- **Scrubbing the film with the scroll.** That is the playhead of anime-intro, the frame counter of flipbook and zoetrope. Here the film runs on its own clock and the scroll moves the drawing.
- **Smooth 60 fps drawings.** A traced line that changes every frame at 60 fps reads as video noise; on twos reads as drawn.
- **Boiling body text.** The bounce boil is only for lettering; notes stay still and readable.
- **Same-as-blueprint trap:** blueprint's pen draws the lines at constant speed as you scroll. Here nothing is drawn stroke by stroke: the whole frame changes stage, region by region, over live footage.
- **Same-as-halftone trap:** halftone resolves images from dots. Rotoscope never uses dots; it is line, hatching and flat paint.

### 2.8 UX signature

**You are the tracer's hand.** Each section is a shot of live footage projected onto a light table, already playing. Scroll into it and blue-pencil roughs find its edges, clean ink follows, and flat cel paint floods in blot by blot until the photo is gone and a boiling ink-and-paint frame holds while you read the hand-lettered sheet pinned over it. Scroll on and the drawing falls back to pencil and stays as a red onion skin over the next shot's footage. The film never stops and never scrubs; the scroll only changes how drawn it is. The phone is the one thing left real, and the last button steps back out of the drawing into the real world.

---

## Contrast table: the two signatures against their nearest neighbours

| | **Pop-up book** | **Rotoscope** | Comic book | Flipbook | Blueprint | Anime OP |
|---|---|---|---|---|---|---|
| **One scroll notch =** | Turns a board page a few degrees; every piece follows the angle | Moves the shot one step along the trace (live → roughs → ink → paint → pencil) | Moves the eye to the next panel | Flips to the next page / frame | Pen advances along the drawing | Playhead advances; may cross a hard cut |
| **Time feel** | Continuous turn with a paper spring; mechanisms run on rest | Footage in real time on twos; trace stage continuous; boil on twos | Stepped panel by panel | Frame steps at scroll speed | Continuous, linear | Cuts and holds |
| **Spatial logic** | One 3D book on a table: upright wall, flat floor, pieces at depths | Fixed light table: full-screen plate, pegged sheets | Pinned page of panels | A pad of paper | Camera pans over one sheet | 16:9 shots |
| **Persistence** | The book persists; turned leaves stack on the wall | The last drawing persists as a red onion skin | Pages replace each other | Pages accumulate under the thumb | The drawing accumulates | Nothing persists |
| **Headline arrives by** | Die-cut words rising out of the gutter | Pencil outline, then ink, lettering boiling | Caption slides, balloon pops | Drawn frame by frame | Single-stroke lettering plotted in | Title-card smash |
| **Stats as** | Strips pulled up out of slots by tabs | Circled key numbers on timing charts | Starburst numerals | (flipbook's own) | Dimension lines | Power-level slams |
| **Feature list as** | Stand-up cards slid forward by a pull-tab | Key drawings on a model sheet | Action panels | (flipbook's own) | Balloons keyed to a BOM | Cast cut-ins |
| **Section transition** | The page turn folds one scene flat and builds the next | Re-trace: pencil, live footage, onion skin | Zoom out, page turn | Run of pages | Camera pan; revision cloud | Hard cut |
| **Pointer** | Orbit the table; drag tabs and the wheel | Traced ghost cursor on twos; touch strokes | Panel lifts | Grab the corner | CAD crosshair | Glint |
| **CTA** | The last tab, a ticket before a turning sunburst | Drawn button that develops into a real one | "Your turn!" panel | (flipbook's own) | APPROVED stamp | NEXT EPISODE card |
| **Reduced motion** | Open spreads, still dioramas, wheel as a list | Finished ink-and-paint stills, no boil | Full pages | A single page | Completed drawing | Storyboard page |

Pop-up book and comic book share one cell in spirit (a page turn), and rotoscope shares none with its neighbours. Neither shares three, so neither is a reskin by the review rule.
