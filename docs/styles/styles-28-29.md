> Style research from DesignAI by Edeki Okoh: https://github.com/Okohedeki/designai. Licensed under the GNU AGPL-3.0 with additional terms (NOTICE.md): credit it with this notice, unchanged, wherever it is used, and don't present it as your own work.

# DesignAI style research: styles 28 and 29

**Stop-motion, Paper cut-out**

Prepared 2026-10-18 for the DesignAI engine, as part of the animation-technique batch (styles 22 to 33). These two techniques are close relatives: cut-out animation is itself a kind of stop-motion, and both are photographed from a fixed camera with the hands of an animator just out of shot. They still ask different questions of a scroll site, and the question this research keeps asking is the earlier one: **what does one notch of the scroll wheel mean here?** In stop-motion the honest answer is *one more exposure*: a world that only changes when somebody takes a photograph. In paper cut-out it is *a pull on the strings*: flat pieces that only turn on a pin or slide in a plane, whatever the camera does. Fonts and colours come after.

> **How to read the citations.** URLs are inline. Where a claim comes from general knowledge and not from a source I retrieved, I say "(general knowledge)". Where I only saw a search engine's excerpt of a page (the page itself refused to load or I could not read it), I say "(search snippet)". Pages fetched through a summarising tool are marked "fetched" in my notes, but quotations in this document are kept short and should be checked against the live page before they are reused. Treat named works as references to check.

---

## Cross-cutting principle: two animation techniques, two clocks

| Style | What scroll *is* | Time quantisation | Motion curve | Spatial axis | Primary renderer |
|---|---|---|---|---|---|
| Stop-motion | The shutter. Every few pixels of scroll is one exposure; the world is perfectly still between exposures, and when you stop scrolling nothing moves at all (the one clock that runs by itself is the first set being placed on load) | Hard: poses change **on twos** (a new pose every second exposure) and the picture is never taken faster than 12 times a second, however fast you scroll. Surfaces and letters re-roll their wobble on **every** exposure (boil) | Spaced like an animator's chart: anticipation, fall, a squashed landing, a settle; every move a short run of jumpy poses, never a smooth curve | A locked-off camera on one tabletop set, shot front-on and symmetrical. Depth is only the stack of wall, floor and standing pieces | Real HTML over CSS (felt, card, clay, tape); one canvas per puppet for `theme.art`; the picture is repainted at most 12 times a second |
| Paper cut-out | The pull on a brad. Scroll swings the top sheet aside on its pin; scroll speed swings every hanging piece; scroll distance flaps a paper bird's wings; a linkage opens (a fan, a folding rule, a wheel) | None. Motion is continuous but it has **mass**: every joint is a spring with a little overshoot, and when you stop, things settle back like hanging paper | Damped springs; rigid parts that only rotate on pins and slide in a plane (no squash, no stretch) | Orthographic and flat, shot from above: coloured sheets lying a few millimetres apart on a stand, thin shadows, no perspective | Real HTML with the individual `translate` and `rotate` properties (no layout while it runs); small SVG for the branch, bird and arm |

The batch is crowded with stepped, frame-based techniques. `flipbook` makes the scroll a page counter and `zoetrope` makes the wheel's speed the clock. Stop-motion shares a family likeness with both and is different in three ways that matter. Its unit is an **exposure of one persistent physical set**, not a page that replaces the last, so everything that is not moving this frame stays exactly where it is. It is the only style whose picture is **dead between exposures**: the boil in the lettering and the felt only re-rolls when the shutter fires, the opposite of `rotoscope`'s line boil, which runs on its own clock. And its transition is a set being struck and dressed, with the empty set and the tape marks for the next cast shown in between. Paper cut-out shares only the idea that paper is the material with `pop-up-book`, and it differs on everything else: a pop-up page is a three-dimensional hinge whose angle drives every piece, while a cut-out sheet turns **in its own plane** about a pin, the view is orthographic, and the motion carries weight.

---

## 1. Stop-motion

### 1.1 Origin and defining aesthetic

Stop-motion is defined as animation in which objects are physically manipulated in small increments between individually photographed frames ([Wikipedia: Stop-motion](https://en.wikipedia.org/wiki/Stop-motion)). The same page credits J. Stuart Blackton and Albert E. Smith's *The Humpty Dumpty Circus* as the first stop-motion film but notes that the date is disputed, that the film is lost and that Smith's recollections are "not considered to be very reliable"; Blackton's *The Haunted Hotel* (1907) won broad praise, and Willis O'Brien's work was recognised as a way to make lifelike creatures, including the dinosaurs of *The Lost World* (1925) (same page). Ladislas Starewicz's *Lucanus Cervus* (1910) is described as "apparently the first animated puppet film", and he used dead insects as puppets ([Wikipedia: Ladislas Starevich](https://en.wikipedia.org/wiki/Ladislas_Starevich)). Jiří Trnka's puppets had fixed faces; emotion came from framing and lighting ([Wikipedia: Jiří Trnka](https://en.wikipedia.org/wiki/Ji%C5%99%C3%AD_Trnka)).

Aardman was founded in 1972 by Peter Lord and David Sproxton; Morph grew out of a clay segment, and *A Grand Day Out* (1989) was the first Wallace and Gromit film ([Wikipedia: Aardman Animations](https://en.wikipedia.org/wiki/Aardman_Animations)). Plasticine, developed by William Harbutt in 1897, was preferred because it "did not dry and harden" ([Wikipedia: Claymation](https://en.wikipedia.org/wiki/Claymation)). The studio's visible fingerprints are described by the Science and Media Museum as a deliberate keeping of the handmade quality, and Nick Park's word for it is "thumbiness" (both search snippets: [Science and Media Museum](https://blog.scienceandmediamuseum.org.uk/surprising-stories-about-aardman-animations/), [Factory International](https://www.factoryinternational.org/factoryplus/an-introduction-to-aardman/)). Laika's *Coraline* (2009) used replacement animation: separate upper and lower parts of the head, swapped from frame to frame; director Henry Selick wanted the seams between them visible, and the owner asked for them to be removed digitally ([Wikipedia: Coraline](https://en.wikipedia.org/wiki/Coraline_(film))). Jan Švankmajer works with real objects, which he ages and ornaments, and *Dimensions of Dialogue* (1982) won the Annecy Grand Prix ([Wikipedia: Jan Švankmajer](https://en.wikipedia.org/wiki/Jan_%C5%A0vankmajer)). Norman McLaren's pixilation, with live actors holding a pose while each frame is shot, gave *Neighbours* (1952) ([Wikipedia: Pixilation](https://en.wikipedia.org/wiki/Pixilation); [McLaren](https://en.wikipedia.org/wiki/Norman_McLaren)).

The two films the brief names are the closest model for a screen. Wes Anderson's *Fantastic Mr. Fox* (2009) was shot on twos: the reviewer says it "won't run at the usual 24", and the visual-effects supervisor says the characters were "animated on every two frames, 12 positions per second", and that even the simulated leaves and dirt had to update every second frame ([Den of Geek review](https://www.denofgeek.com/movies/fantastic-mr-fox-blu-ray-review); [Computer Graphics World](https://www.cgw.com/Press-Center/Web-Exclusives/2010/Smart-as-a-Fox.aspx)). The animator Andy Biddle says "Wes wanted the boiling" and that the style was developed to keep the fur moving, with hairspray and gel ([Den of Geek interview](https://www.denofgeek.com/movies/fantastic-mr-fox-animators-interview-ian-mckinnon-andy-biddle-and-andy-ghent/)). *Isle of Dogs* (2018) was also "predominantly on twos", 12 images a second; its animation director says the rough handling gave "a little handmade feel" and that you can see "it's all being touched", and the hair-gelled wool fur kept "a slight shimmer even when the puppet was still" ([Cartoon Brew](https://cartoonbrew.com/feature-film/isle-dogs-animation-director-mark-waring-explains-animate-wes-anderson-film-157358.html); [Dazed](https://www.dazeddigital.com/film-tv/article/39516/1/isle-of-dogs-animators-wes-anderson-interview)). The cinematographer says the lighting palette was "very restrictive", with colour coming from the sets, and that "Wes wants symmetrical compositions" ([American Cinematographer](https://theasc.com/articles/animal-kingdom-isle-of-dogs)). The orange of *Fox* is nearly a rule: Wikipedia says no frame of the film lacks it ([Wikipedia: Fantastic Mr. Fox](https://en.wikipedia.org/wiki/Fantastic_Mr._Fox_(film))). Output is slow: about three minutes in a week for a feature crew ([Dazed](https://www.dazeddigital.com/film-tv/article/39516/1/isle-of-dogs-animators-wes-anderson-interview)).

**Visual signatures:**
1. **On twos.** A new pose every second frame, 12 poses a second ([Cartoon Brew](https://cartoonbrew.com/feature-film/isle-dogs-animation-director-mark-waring-explains-animate-wes-anderson-film-157358.html)). The juddery, stepped look is what an audience reads as "made by hand".
2. **Boil.** Surfaces shimmer from frame to frame because the animator has touched them: fur kept moving on purpose, clay with fingerprints, wool with hair gel (sources above). It is only ever visible on a surface a hand has handled, and only when a new frame is exposed.
3. **Materials, not textures.** Felt, wool, card, plasticine, real fur, wood. Photographed small, so everything is soft-edged and slightly too thick. (General knowledge, supported by the sources above for fur, wool and plasticine.)
4. **A locked-off camera and a symmetrical set.** The frame does not move; the world in it does. Anderson's compositions are symmetrical and planimetric ([American Cinematographer](https://theasc.com/articles/animal-kingdom-isle-of-dogs)).
5. **Replacement animation and holds.** Parts of a puppet are swapped; poses are held; movement is spaced with anticipation, slow-in and slow-out ([Wikipedia: Twelve basic principles of animation](https://en.wikipedia.org/wiki/Twelve_basic_principles_of_animation)).
6. **The animator's rig.** Dragonframe's live view can be blended over any captured frame (the onion skin: normal, frame echo of recent frames, difference modes), you "step, play, capture, repeat", and the X-sheet is a dynamic exposure sheet ([Dragonframe](http://www.dragonframe.com/dragonframe-software/); [Evergreen help wiki](https://helpwiki.evergreen.edu/wiki/index.php/Onionskin_-_Dragonframe)).

### 1.2 Layout and information architecture

- **The site is one miniature set, and every section is a set.** One camera is locked off on a stage that fills the screen. Each section is a **tableau**: a painted-card **wall** with a wallpaper (dots, stripes, diamonds, scallops, gingham, plaid) and a cream skirting board, a **floor** (wood boards or felt), and a **cast** standing on it. The first heading on the page is the `<h1>` of the first set.
- **Composition is front-on and symmetrical where it can be.** The headline is on the wall, centred or on the left; the items stand on the floor in a row. Copy sits on **cardboard cards**; labels are **masking tape** with marker handwriting; the headline is **clay letters**.
- **Reading order is the HTML order**: tape label, headline, copy, items, buttons. The page works without JavaScript as stacked still tableaux.
- **Nav is tape:** the site name and the section links on strips of masking tape along the top edge, the call to action as a felt button. Bottom left is the animator's readout: an **exposure counter** that says "on twos" while you scroll and "held" when you stop, and an **onion skin** switch.
- **Tall sets pan.** A set taller than the screen (every set on a phone) is not scrolled: the camera is panned down it, in steps on twos, while the set is open. Pieces that begin below the first view arrive as the camera reaches them.

### 1.3 Signature interactions and scroll behaviour

**How scroll feels:** like standing behind a locked-off camera with your hand on the cable release. Roll the wheel and the set jumps from pose to pose; stop and it freezes solid.

**What scroll drives:**
- **The exposure count.** A few pixels (one screen divided by about 22, between 26 and 42 px) is one exposure, and the whole page is a function of that number. Scrolling back runs the film backwards, frame for frame, because nothing keeps state.
- **A hard 12-a-second cap.** If you fling the page faster, exposures are skipped, never sped up: each picture is taken at most every 83 ms. Scroll slowly and every exposure shows. This is the same rule as *Fox* shot on twos, applied to the visitor's hand.
- **Idle is dead.** With the scroll still, nothing moves: no loops, no breathing, no shimmer. The first set is the one exception; on load the clock shoots its placement by itself, at 12 a second, so a page does not open on an empty stage.
- **Poses on twos, spaced like a chart.** Every arrival is a run of six poses held for two exposures each: a drop (high, falling faster, a landing that squashes, a settle), a slide, a rise, a pop (scale 0.15, an overshoot, a squash, a settle) and a hang (a pinned piece swinging down). Every exposure each moving piece is a hair off where it was: positions and angles are re-rolled by a deterministic hash of the piece and the exposure number, so the same frame is always the same picture.
- **Clay letters.** The headline is split into letters, each its own piece of plasticine with a thick extruded edge. They are placed one after another, then are never quite still: a fraction of a pixel and a fraction of a degree re-rolled every exposure.
- **The boil.** One overlay of felt grain whose texture is swapped among four every exposure, and a faint lamp highlight that varies by a few per cent. Static things do not boil. A wall is painted card and does not.
- **Strike and dress.** The transition between sections is the set being changed. The old cast is lifted away in jumpy steps (last piece first); the wall drops in from above in six poses; the floor slides across from the right; **tape crosses** (spike marks) show where each prop will stand; the new cast is placed piece by piece. The empty set sits on screen for a beat between them.
- **What scroll shoots inside a set.** Features: the card that has the floor steps forward with a hop and the others dim a little. Timeline: a peg doll hops from stone to stone. FAQ: the cupboard doors open in three steps. Product: the selection moves down the phone's options. Strip: the film advances one frame at a time. Orbit: the marbles turn on their ring in steps.
- **`theme.art`** becomes a **felt puppet**: a rectangular felt applique, cut with scissors and stitched round the edge, built from the art's frames in four tones of felt by brightness, with soft thin wisps as cotton wool. Its frame is replaced every second exposure, which is replacement animation, and its edge is eaten away by a different pinch of noise each time.
- **Camera:** locked off. The only camera moves are the pan down a tall set and the set change itself.

**Headline arrival:** the letters are placed in one by one (about 0.45 of an exposure apart), each dropped, squashed and settled, so a headline takes about a second of scrolling to be built.

**Stats:** **alphabet blocks.** Each figure is printed on a wooden-toy-style cube in felt-and-clay colours with a tape label under it. The cubes are dropped one after another and the number is printed, never counted up.

**Feature list:** **felt cards on the floor**, stitched round the edge, each tilted a degree or so. The active one steps forward and hops as the scroll reaches it.

**Section transition:** the strike and dress above.

**Hover / pointer:** the pointer is the animator's hand. Brushing a card, cube, pill, snapshot or marble nudges it one step (a hop, on twos). A click or tap pokes any piece and it hops; a piece that hangs from a pin swings. Props that carry no copy (the framed picture, the puppet, the phone stand, the sun, the bunting) can be picked up and posed with the mouse, and stay where they are put until the set is rebuilt. The **onion skin** switch draws a dashed blue box where each moving piece stood in the last exposure, as the animator's tool does. Touch: tap pokes; nothing ever captures a vertical swipe, so the page scrolls as normal.

**CTA:** a big felt button that pops in last with a squash; bunting hung across the wall, each pennant swinging when it arrives.

**Real-world references:** I found no verified scroll site that imitates stop-motion. The CSS `steps()` function divides time into equal intervals ([MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/easing-function/steps)), which is the right idea for a stepped look, but it keys stepping to time, not to the scroll, and nothing I found uses it this way. The scroll-to-frame-sequence technique that Apple-style product pages use scrubs a film (search snippet: [Contra case study](https://www.contra.com/p/ecNLXPeE-rushinek-interactive-landing-page-gsap-animation)), which is a playhead, not an exposure.

### 1.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Masking tape across the top: the site name on a yellow strip, one strip per section, the current one pressed down; the call to action a felt button. On a phone only the name and the button remain. |
| Hero | The first set: bunting across the wall, a tape badge, the clay headline, a card with the lede, felt buttons. The prop is the hero image as a framed picture hung from a nail, or the device on a wooden stand, or the `theme.art` puppet, or a felt sun. |
| Buttons | Felt pills with a thick lower edge that press down; the primary is fox-orange. |
| Intro | Title on the wall, copy on a card on the floor, two felt hills in front. |
| Features | Felt cards in a row on the floor; one steps forward as the scroll reaches it. |
| Product | The image on an easel, the phone on a stand, the copy on a card, tags as small felt pills. A scroll step moves the selection down the phone's options. |
| Stats | Alphabet blocks in four colours, dropped in one after another, a tape label under each. |
| Timeline | A row of cardboard cards, each over a stepping stone; a peg doll hops along the stones as the scroll advances. |
| Quote | A cardboard sign on a stick, the quote in clay-weight type, the attribution on tape. |
| FAQ | A cupboard of felt doors; each opens in three steps to show the answer. Real `<details>`. |
| CTA | A large button popped in last, bunting, and the puppet if the site has art. |
| Gallery | Snapshots pegged to a washing line. |
| Strip | A film strip with sprocket holes, advancing one frame at a time. |
| Orbit | Clay marbles on a ring round a felt hub. |
| Scenes | Shown in a viewfinder: a dark bezel round the scene's own player, like the animator's video-assist monitor. A scene keeps its own scroll model; it is not exposure-stepped (see the weak points in the build report). |
| Footer | Marker handwriting on the table. |

### 1.5 Typography and colour

- **Display:** **Fredoka**, rounded and soft, set with a thick extruded edge so that it reads as slabs of plasticine. The research found no verified source for the title lettering of *Fantastic Mr. Fox* (a design blog's "custom, storybook-style" is a search snippet only), though Anderson is known for Futura in other films ([Kottke](https://kottke.org/04/11/futura-and-wes-anderson)); the geometric sans for **body** is therefore **Jost**, a Futura-like face, and is a design choice, not a claim about the film.
- **Labels:** **Gaegu**, a marker hand, on tape. The exposure counter is **Special Elite**, a typewriter face, as on a production slate.
- **Palette:** autumn orange, mustard, olive, brick, teal and tan on a cream and brown ground, in the spirit of *Fox* (the orange rule above): fox-orange `#d2561f`, mustard `#e0a526`, olive `#7f8436`, brick `#a8381f`, teal `#2f6a68`, tan `#cfae74`, cream `#f6e8c9`, brown `#2f2016`, table `#20150e`. Each set has its own paint (wall, floor, clay, felt) so a run of sets does not repeat. Text on felt is cream on a dark felt (checked above 4.5:1) and brown on mustard felt.

### 1.6 Implementation

- **One DOM, no canvas for the set.** Every piece is real HTML. The runtime writes each piece's pose to `translate`, `rotate` and `scale` custom properties once per exposure and to nothing between exposures. A piece's CSS never animates.
- **Exposure clock.** One `onFrame` callback reads the scroll, computes the exposure number for the run on screen, and applies it only if at least 83 ms have passed since the last picture. Everything else (the set timeline, the hold mechanisms, the pans) is a pure function of that integer.
- **A schedule in exposures.** Each set has a start, a placement window, a hold and an end. `PRE` (8) exposures strike the old cast, `FLATS` (12) land the wall and floor, `ARR` (26) place the cast, and the hold length comes from the set's content (and from how far a tall set has to be panned).
- **Performance.** The picture changes at most 12 times a second and nothing runs between pictures, so a phone is idle most of the time. One measured pitfall: setting a custom property on `<html>` (the boil and the lamp, when they were root properties) restyled the whole document and dropped a 4x CPU-throttled phone profile to 22 fps; moving the boil to one overlay element and the lamp to its own element returned it to a steady 60 fps (average frame 16.9 ms, 95th percentile 16.8 ms, in headless Chrome at 390 px with the CPU throttled four times).
- **The puppet.** `theme.art` frames are classified once per frame (felt tone by brightness, wool for thin soft detail, dark felt for an enclosed hole such as coffee in a cup) and cached; each exposure only redraws the eaten edge. It is not specific to one picture.
- **Phones:** the same set, narrower; lists stack in one column; the camera pans down the set on twos.
- **Accessibility:** the page is real text in reading order. Letters are wrapped in spans with the heading's `aria-label`. Keyboard focus inside a set that is not on the stage moves the camera there. The strongest brightness change is a lamp highlight of a few per cent at no more than 12 Hz; there is no flash and no strobe.
- **Reduced motion:** no stage and no counting. Each set is the finished tableau the CSS draws on its own, stacked down the page, the puppet drawn once.

### 1.7 Anti-patterns

- **A jitter filter on a normal page.** Filters apply the same wobble everywhere; a real animator's irregularity comes from the hands and the light, and it only exists where something was touched (my inference from the sources above; one critic's point is that the stop-motion look is about visible construction, not randomness, [MUBI Notebook](https://mubi.com/fr/notebook/posts/the-action-scene-fantastic-mr-fox-and-the-dynamics-of-stop-motion)). Here only handled things boil, and a wall never does.
- **Boiling body text.** Copy sits on cards that do not move; only the clay headline and the felt move.
- **Time-based stepping.** If a page steps at 12 a second whether you scroll or not, it is a screensaver. Here the clock is the scroll.
- **Smooth easing.** An ease curve is the opposite of poses on twos.
- **Same-as-flipbook trap:** flipbook flips pages, each page a new drawing, with a peel. Stop-motion never replaces the picture: the same physical set stays, and pieces in it move.
- **Same-as-zoetrope trap:** zoetrope's life depends on how fast you spin. Here speed has no effect except the 12-a-second cap.
- **Same-as-rotoscope trap:** rotoscope's boil runs on its own clock under live footage; here it re-rolls only when the shutter fires.

### 1.8 UX signature

**You are working the shutter.** A small set, painted card and felt and clay under a hot lamp, stands perfectly still. Scroll, and it jumps: letters of clay are placed one at a time and never quite settle, felt cards drop, squash and settle, a peg doll hops from stone to stone, and the picture in the frame is never taken more than twelve times a second. Stop, and the world freezes solid. Scroll on and the set is struck: the cast is lifted away piece by piece, a bare wall and floor with tape crosses on it hold for a beat, a new wall drops in, and the next cast is placed on its marks. Poke a puppet and it hops, switch on the onion skin and the last frame stays as a ghost, and the picture from `theme.art` is a felt cut-out whose frames are replaced one exposure at a time. No other style is dead between pictures.

---

## 2. Paper cut-out

### 2.1 Origin and defining aesthetic

Cut-out animation is a form of stop-motion with flat characters, props and backgrounds cut from paper, card, fabric or photographs; articulated figures have joints "made with a rivet or pin" ([Wikipedia: Cutout animation](https://en.wikipedia.org/wiki/Cutout_animation)). Pieces are joined with pins or hinges, repositioned frame by frame, and layered as background, midground and foreground ([Filmmaking Lifestyle](https://filmlifestyle.com/what-is-cutout-animation/)). The paper fastener (brad, split pin) is a two-pronged fastener that allows rotation about a joint in mobile paper and cardboard models ([Wikipedia: Paper fastener](https://en.wikipedia.org/wiki/Paper_fastener)), which is where this style gets its hinge. An animation stand's camera always points down, and registration pegs in slots hold the sheets ([Wikipedia: Animation stand](https://en.wikipedia.org/wiki/Animation_stand)).

**Lotte Reiniger** made *The Adventures of Prince Achmed* (premiered 1926, 65 minutes) from cardboard cut-outs and thin sheets of lead, a method the film's page likens to wayang shadow puppets; moving backgrounds were built from layers covered in sand, paint and soap, stars were cardboard with holes held to a strong light, waves were superimposed tissue, and the original prints were tinted ([Wikipedia: The Adventures of Prince Achmed](https://en.wikipedia.org/wiki/The_Adventures_of_Prince_Achmed)). Her figures were tracing paper and cardboard, sometimes 20 to 50 pieces fused together with lead wire, and emotion was carried by gesture, not faces ([Wikipedia: Lotte Reiniger](https://en.wikipedia.org/wiki/Lotte_Reiniger)). She and Carl Koch built an early multiplane device around 1923, with stacked backlit glass and the camera fixed above ([Wikipedia: Multiplane camera](https://en.wikipedia.org/wiki/Multiplane_camera)); the Tübingen museum that holds her estate runs workshops on trick tables "modelled on" hers ([Stadtmuseum Tübingen](https://webarchiv.tuebingen.de/2024-05-08/stadtmuseum/16901/15122.html)). A column's search snippet gives her own account: figures on a glass table lit strongly from below so that the wire hinges disappear, the camera hung above (search snippet, source URL not confirmed; not verified).

**Terry Gilliam** made the cut-out animation for *Monty Python's Flying Circus* (1969 to 1974) by pushing paper pieces in front of a camera, which he called "the easiest form of animation I know", and which, he said, is bad at graceful movement and good at sudden, swift movement, hence the beheadings ([Open Culture](https://www.openculture.com/2014/07/terry-gilliam-reveals-the-secrets-of-monty-python-animations.html)). A Make article summarises his 1974 tutorial ([Make](https://makezine.com/article/craft/how-to_cut-out_animation_with/)). His *Christmas Card* (1968) rearranged Victorian cards copied from the Tate (search snippet: [Weird Retro](https://weirdretro.org.uk/captains-blog/terry-gilliams-christmas-card-1968)). *South Park*'s pilot was made from construction paper ([Wikipedia: The Spirit of Christmas](https://en.wikipedia.org/wiki/The_Spirit_of_Christmas_(short_films))). Yuri Norstein's rig is a different method: a camera above a stack of glass planes (see the multiplane section in the roadmap) ([Wikipedia: Yuri Norstein](https://en.wikipedia.org/wiki/Yuri_Norstein)).

The antecedents are mechanical and worth keeping. Wayang kulit figures are leather on bamboo sticks worked between a lamp and a linen screen ([Wikipedia: Wayang kulit](https://en.wikipedia.org/wiki/Wayang_kulit)); shadow play in general uses flat jointed cut-outs between a light and a translucent screen, with Chinese references from the Northern Song and Karagöz in the Ottoman world ([Wikipedia: Shadow play](https://en.wikipedia.org/wiki/Shadow_play)). Toy theatre, from early nineteenth-century England, sold printed sheets of characters and scenery to cut out and mount on card, with figures on sticks or wires ([Wikipedia: Toy theatre](https://en.wikipedia.org/wiki/Toy_theatre)). The jumping jack or *pantin* is a flat jointed figure whose joints are tied to one pull string so the limbs move together; French pantins were fashionable in the mid-1700s ([Wikipedia: Jumping jack](https://en.wikipedia.org/wiki/Jumping_jack_(toy))). Digital cut-out rigging keeps the same ideas as pegs with pivot points and hierarchies (Toon Boom forum thread, search snippet: [forums.toonboom.com](https://forums.toonboom.com/t/pivot-point-problem/6748)); forward kinematics runs from joint values to the end of a chain and inverse kinematics the other way, from a target to joint values ([Wikipedia: Inverse kinematics](https://en.wikipedia.org/wiki/Inverse_kinematics)).

**Visual signatures:**
1. **Flat and rigid.** Paper cannot squash or stretch; it can only turn on a pin or slide in its plane. Gilliam's own summary of the limits (sudden, swift, not graceful) is the sound of that constraint ([Open Culture](https://www.openculture.com/2014/07/terry-gilliam-reveals-the-secrets-of-monty-python-animations.html)).
2. **Visible joints.** A brad at every joint. (General knowledge; the fastener itself is in [Wikipedia](https://en.wikipedia.org/wiki/Paper_fastener).)
3. **Layers lie a few millimetres apart**, so each piece casts a thin shadow on the one below, hard near the edge and soft further out. Tutorials for layered paper style describe a shadow per layer with a vertical offset (search snippets only: [CreativePro](https://creativepro.com/creating-cutout-image-effects-with-photoshop/), [Red Shark](https://www.redsharkdigital.com/news/how-to-create-layered-cut-out-paper-in-adobe-illustrator)); I found no source that measures the distance, so treat the proportions here as a design choice.
4. **Black silhouettes against saturated coloured grounds, with fine cut detail and backlit tissue** (Reiniger; [Wikipedia: Prince Achmed](https://en.wikipedia.org/wiki/The_Adventures_of_Prince_Achmed); the colour detail is thinly supported, one Cornell page snippet).
5. **Collage from printed paper and engravings** with a white cut margin (Gilliam; "Max Ernst meets Mad Magazine" per [Open Culture](https://www.openculture.com/2014/07/terry-gilliam-reveals-the-secrets-of-monty-python-animations.html)).
6. **One input, many joints.** The pantin's single string and the multiplane's single crank are both a linkage: one pull, many moving parts ([Wikipedia: Jumping jack](https://en.wikipedia.org/wiki/Jumping_jack_(toy))).

### 2.2 Layout and information architecture

- **The site is a stack of coloured sheets on a cutting mat.** Every section is a **sheet** of paper (vermilion, bone, ultramarine, ochre, a black night sheet, sage, rose), as large as the screen, held to the stack by one **brass brad** in a corner (the four corners in turn). Under the sheets, where they swing away, is a green cutting mat with a grid.
- **Composition is a collage, not a symmetrical tableau**: asymmetric, with large flat colour, pieces at angles of a degree or two, black silhouettes of leaves and birds at the edges.
- **Headlines are words on paper strips**: each word its own strip of cream, black or accent paper with a brass pin hole at the top left, hung from that pin; labels are **typewritten** paper pasted on; copy sits on a lighter sheet of paper (a note); buttons are **tickets** with a notch each side.
- **Reading order is the HTML order.** The page works without JavaScript as flat sheets laid down the page, each with a brad.
- **Nav** is paper tabs with a V cut in the bottom edge, hanging from the top.
- **A jointed paper arm** reaches in from the bottom corner of each sheet and points at what the scroll has reached.

### 2.3 Signature interactions and scroll behaviour

**How scroll feels:** like pulling paper off a stack with a pin through its corner: the sheet swings away with weight and a little overshoot, and the sheet underneath wakes up as it is uncovered.

**What scroll drives:**
- **A swing about a pin.** The top sheet turns 100° about its brad (clockwise from the top left or bottom right, anticlockwise from the other two) in about a screen of scroll, a damped spring with a slight overshoot; its shadow lengthens as it lifts. A quarter turn clears the screen, so the sheet sweeps across like a door and is gone. The next sheet is already lying underneath.
- **Pieces unfold on their own pins.** Before its sheet is uncovered, each piece is folded away (rotated 20° to 45° about its pin and pushed off to a side); as the sheet above swings away, each swings into place, overshoots and settles. Headline words fall from above one after another, notes slide in from the side, tickets rise from below.
- **Scroll speed swings the hanging things.** Words, mobile tags, the rod, the balloon and the pinned snapshots sway in proportion to how fast you are scrolling, in either direction, and swing back with decay when you stop. It is a spring, not a loop, so a stopped page is a still page.
- **Scroll distance drives the wings.** A paper bird crosses the sheet as you scroll the section, its two wings pinned at the shoulder and flapping once for every few hundred pixels of scroll. The leaves of a branch at the foot of the sheet are each pinned at their base and rustle with the scroll speed.
- **Linkages inside a sheet.** Features: the cards share **one pin** at their lower edge and fan out from it like a hand of cards; the card the scroll has reached stands up out of the fan. Timeline: a **folding rule**, each link hinged to the next, opens along its length one hinge at a time (forward kinematics: each link's position is the end of the last). FAQ: each question is a flap that swings **ajar** on its pin to uncover the answer beneath it. Stats: a **mobile**, a rod hung from a string with tags hung from the rod. Orbit: **spokes** on a hub turn as the wheel is wound. Strip: a band slides along.
- **The art** becomes a **stencil** in black paper: the bright parts of each frame are cut away so the sheet's colour shows through, and the frame changes with the scroll distance.
- **Camera:** locked off, orthographic, straight down. The only camera move is a pan down a sheet taller than the screen (every sheet on a phone), done as the paper sliding under the lens.

**Headline arrival:** word by word, each word swinging down on its pin and settling.

**Stats:** **a mobile**: tags in paper colours hung by strings from a rod that is itself hung from a string, all of it swaying with the scroll.

**Feature list:** **a fan of cards** on one pin.

**Section transition:** **the sheet swings off its brad**; nothing fades and nothing is cut.

**Hover / pointer:** the pointer sends the **arm**. The arm is three parts pinned at shoulder, elbow and wrist (a sleeve with stripes, a forearm with a lace cuff, a glove with one finger out), solved with two-bone inverse kinematics, drawn as a black silhouette with a white cut margin, and it lives **under the content**, so it never covers text. By default it points at the item the scroll has reached; hover another item and it points there; take the hand and move it, and it springs back when you let go. Words, tags, the rod and snapshots can be taken with the mouse and swung, and a tap flicks one. On a phone the arm is off, taps flick, and nothing captures a vertical swipe.

**CTA:** a ticket on the last sheet, with the art as a small black stencil beside it, a bird crossing and stars cut from the night sheet.

**Real-world references:** I found no award-winning scroll site built on cut-paper mechanics. The nearest are speculative: a January 2026 "papercut" redesign concept (search snippet: [Contra](https://contra.com/p/LEMbYPWR-stay-ease-ui-redesign-papercut-concept-a-premium-stay-ease-w)), torn edges from `clip-path: polygon()` (search snippet: [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_masking/Clipping)). The pop-up-book style in this engine is the nearest in spirit and differs as above.

### 2.4 Component treatments

| Component | Treatment |
|---|---|
| Nav | Paper tabs with a V cut in the bottom edge; the site name on a yellow tab; the current section's tab drops lower. |
| Hero | The cover sheet in vermilion: the headline as hung word strips, a typewritten badge, a note with the lede, ticket buttons, a cut-out photo with a white margin and corner mounts (or the device, or the art as a stencil). A bird crosses and a branch grows from the corner. |
| Buttons | Tickets with a notch each side and a drop shadow; the primary in the sheet's accent. |
| Intro | The headline on the left, the copy on a note at the lower right. |
| Features | A fan of cards on one pin; the one the scroll has reached stands up. |
| Product | The photo with a white margin and corner mounts, the phone beside it, tags as paper pills. |
| Stats | A mobile on the black night sheet: tags in amber, rose, green and cream, a rod and strings, stars cut from the sheet. |
| Timeline | A folding rule; each link a card hinged to the next with a brass brad, opening one at a time. On a phone the links slide in one after another. |
| Quote | A balloon cut from card hung on two strings, swinging, the attribution on a typewritten label. |
| FAQ | Question flaps in three colours that swing ajar over the answers. Real `<details>`. |
| CTA | The headline as hung words, a big ticket, a stencil of the art, stars. |
| Gallery | Snapshots pinned to the sheet with brass pins, each swinging when poked. |
| Strip | A band of mounted pictures sliding along. |
| Orbit | A hub with spokes of paper, a disc on the end of each, turning together. |
| Scenes | Loose, between stands, shown on a dark bezel, with their own scroll model. |
| Footer | The page's credit line on the mat. |

### 2.5 Typography and colour

- **Display:** **Rozha One**, a fat-face Didone display type, the kind of face that was cut for placards and posting-bills in the early nineteenth century; slab and fat faces were first sold in the 1810s and were "traditionally associated with use in circus and other posters" ([Wikipedia: Slab serif](https://en.wikipedia.org/wiki/Slab_serif)). It survives being set on a paper strip at any size. (Choice, not a claim about Gilliam's lettering; I found no source for his typography.)
- **Body:** **Libre Franklin**, a plain grotesque, for notes and cards. **Labels:** **Special Elite**, a typewriter face, for the pasted labels, as on a catalogue card.
- **Palette:** vermilion `#c8372a`, bone `#efe6d2`, ultramarine `#2a5f8a`, ochre `#d9a441`, night `#1b1715` with an amber glow `#f0b45a`, sage `#8fa882`, rose `#e3a595`, cutting mat `#1f3a35`. Black silhouettes `#1b1715` on the light and coloured sheets, cream on the night sheet. A faint fibre grain on every sheet; no gradients on pieces.

### 2.6 Implementation

- **Flat DOM, no canvas for the paper.** Pieces move with `translate` and `rotate` set directly on the element (not custom properties), so a frame changes no layout and restyles only the element. About fifty small layers on a desktop; one stand per run of sheets.
- **Springs.** One small damped spring class (substepped so a slow frame cannot blow it up) drives the sheet swings, every piece's unfold, the fan, the rule's hinges, the flaps, the strip and the arm's hand. The scroll sets the targets; the springs make them heavy.
- **A swing about a pin.** Each sheet's `transform-origin` is its brad; the stack's z-order is fixed and only the top two sheets are on screen. A sheet that was not on the stand and is behind the camera (a jump to a link) simply is not there, so it does not swing past.
- **The arm.** An SVG of three parts and a shadow copy, built once per sheet and placed between the paper and the content; two-bone IK each frame for the one sheet that has it.
- **Silhouettes.** A branch (leaves pinned at their bases), a bird (wings pinned at the shoulder) and cut stars are generated as small SVGs from a seeded generator, never from the site's content. They can be hung or posed independently.
- **Performance:** nothing animates unless the scroll or a spring is moving. A measured run at 390 px with the CPU throttled four times, scrolling continuously for 10 s, gave an average frame of 16.8 ms and a 95th percentile of 16.8 ms in headless Chrome (a mid-range phone is not the same as a throttled desktop; this is a proxy).
- **Accessibility:** real text in reading order; the word strips are `aria-hidden` spans inside a heading that carries the label; the decoration and the arm are `aria-hidden`; keyboard focus on a sheet that is not on the stand moves the stand there. Dragging and the arm are optional.
- **Reduced motion:** no stand; the sheets are laid down as flat paper with their pieces at rest, the bird mid-sky and the branch still.

### 2.7 Anti-patterns

- **Blurry skeuomorphic paper.** Blur and a gradient for a shadow reads as glass or as 2013 iOS; paper shadows are tight near the edge and softer further out (general knowledge). The NN/g note on skeuomorphism's cost, signifiers, is a reason the buttons here look like tickets ([NN/g: Flat design](https://www.nngroup.com/articles/flat-design/)).
- **Squash and stretch.** Paper does not squash; every move here is a rotation on a pin or a slide in the plane.
- **Perspective.** A cut-out is shot flat from above. Putting perspective on a sheet makes it a pop-up page.
- **Idle looping.** A paper page that sways when nobody is scrolling is a screensaver. Everything here is driven by the scroll and settles when it stops.
- **Motion triggers.** MDN warns that scaling or panning large objects can be a vestibular trigger ([MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion)); the big motion here is the sheet swing, which reduced motion removes.
- **Same-as-pop-up-book trap:** pop-up book is one three-dimensional object whose hinge angle is the scroll. A cut-out sheet turns in its own plane, the view is flat, and motion carries weight.
- **Same-as-flipbook trap:** a flipbook peels one page over another with a curl. A sheet here swings off a pin like a door.
- **Same-as-neo-brutalism trap:** objects slapped down and grabbed share only the free placement; this is paper with joints and springs, not a pinboard.

### 2.8 UX signature

**Paper on pins, and an arm that points.** A red sheet is held to a green cutting mat by one brass brad. The words of the headline hang from their own pins, a paper bird crosses with its wings flapping as you scroll, and a jointed black-sleeved arm reaches up from the corner to point at the button. Scroll and the whole sheet swings off its pin with the weight of paper and a little overshoot; the blue sheet under it comes alive as it is uncovered, its cards swinging into place on their pins and its words dropping in. Scroll faster and everything that hangs sways more; stop and it all settles. Inside a sheet the scroll works linkages: a fan of cards opens from one pin, a folding rule opens a hinge at a time, flaps swing ajar over answers, a mobile sways under its tags. Hover an item and the arm points at it; take the hand and move it. No other style is made of rigid paper that only turns on pins.

---

## Contrast table: the two signatures against their nearest neighbours

| | **Stop-motion** | **Paper cut-out** | Flipbook | Zoetrope | Pop-up book | Rotoscope |
|---|---|---|---|---|---|---|
| **One scroll notch =** | One more exposure, taken at most 12 times a second; poses change on twos | A pull on a pin: the sheet turns a few degrees, hanging things swing, a linkage moves | Releases one page | Adds spin to a wheel | Turns a board page a few degrees | Moves the shot along the trace |
| **Time feel** | Dead between pictures; stepped and jumpy; boil re-rolls every exposure | Continuous with weight: springs that overshoot and settle | Stepped pages | Inertia; strobe at speed | Continuous with a paper spring | Footage runs on its own clock; boil on twos |
| **Spatial logic** | One locked-off tabletop set, front-on, symmetrical | One orthographic stack of sheets on a mat, shot from above | A pad of paper | A ring of cards | One 3D book on a table | A light table |
| **Persistence** | The same physical set persists; pieces are lifted and placed | The stack persists; swung sheets are gone | Pages accumulate | The wheel | The book | The last drawing as an onion skin |
| **Headline arrives by** | Clay letters placed one at a time | Words on strips swinging down on pins | Drawn frame by frame | A card on the wheel | Die-cut words rising from the gutter | Pencil outline, then ink |
| **Stats as** | Alphabet blocks dropped on the floor | A mobile: tags hung from a swaying rod | (flipbook's own) | A card with a figure | Strips pulled from slots | Circled key numbers on timing charts |
| **Feature list as** | Felt cards, the speaker steps forward | A fan of cards on one pin | (flipbook's own) | A card each | Stand-up cards on a pull-tab | Key drawings on a model sheet |
| **Section transition** | Strike and dress: cast lifted off, bare set with tape marks, wall dropped, floor slid in, cast placed | The sheet swings off its brad | A run of pages | The wheel lands | The page turn folds one scene and builds the next | Re-trace with onion skin |
| **Pointer** | The animator's hand: pokes, brushes, picks props up; an onion-skin switch | A jointed arm that points and can be moved; hanging pieces can be swung | Grab the corner | Spin and open | Orbit; drag tabs and wheel | A traced ghost cursor |
| **CTA** | A big felt button popped in last under bunting | A ticket on a night sheet with a stencil and stars | (flipbook's own) | A card | The last tab | A drawn button that develops into a real one |
| **Reduced motion** | Finished tableaux stacked down the page | Flat sheets stacked, pieces at rest | A single page | A list of cards | Open spreads | Finished ink-and-paint stills |

Stop-motion shares one cell in spirit with flipbook (stepped by scroll distance) and none of the rest; paper cut-out shares the material with pop-up book and nothing else. Neither shares three, so neither is a reskin by the review rule.
