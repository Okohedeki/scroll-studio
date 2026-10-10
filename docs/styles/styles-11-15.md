# Scroll Studio style research: styles 11-15

**Styles covered:** Gradient mesh, Comic book, Split-flap (Solari board), Retro VHS, Halftone

**Why this brief exists:** In the previous engine, all 20 styles shared one page skeleton and one set of interactions, with only the CSS skin changing. This brief treats each style as a separate **interaction model**. That means a different metaphor for what scrolling *is*, a different way content arrives, and different component behaviour, as well as different fonts and colours. Every section closes with a "UX signature", and the table at the end checks that no two styles share one.

**How claims are sourced:** URLs are cited inline. Some statements are practitioner knowledge rather than sourced fact, such as exact timings, recommended values and some historical detail. Those are flagged as *(practitioner note)* or written as recommendations, so they are not mistaken for citations.

---

## 1. Gradient mesh

### 1.1 Origin and defining aesthetic

The look comes from vector "gradient mesh" tools (Illustrator's mesh tool, and later Figma and Sketch mesh plugins). It reached the web as the animated WebGL hero on the 2020 **stripe.com** redesign. Stripe's background is a WebGL canvas, not CSS. Its minified code was reverse-engineered by the community into a small `MiniGl` wrapper: a plane mesh whose vertices are displaced by layered noise over time, with colours blended from a four-colour palette. Uniforms include `u_time`, wave layers, base and active colours, and a "darken top" term ([GSAP forum thread](https://gsap.com/community/forums/topic/24837-animating-gradients/), [reconstructed Gradient.js](https://huggingface.co/spaces/moh1456/nim/blob/main/stripe-gradient-animation/src/Gradient.js), [gist](https://gist.github.com/oaluna/3cc459a57259583464ee305f6153ba46)). The reconstruction is credited to Kevin Hufnagl and is packaged as **whatamesh** ([whatamesh.vercel.app](https://whatamesh.vercel.app), referenced by [Codrops' Stripe lava-lamp tutorial](https://tympanus.net/codrops/2022/09/26/how-to-recreate-stripes-lava-lamp-gradient-with-three-js), [anim-gradient on npm](https://npmjs.com/package/anim-gradient)). Anthony Hobday's teardown notes that the pulsing gradient fuses the nav bar and hero into one surface, which saves space and pulls the eye to the headline ([anthonyhobday.com](https://anthonyhobday.com/sideprojects/attentiontodetail/stripe.html)). Stripe's later homepage kept gradient "waves" but built them in a custom tool with controls for blur, grain, rotation, thickness and texture ([YC podcast with Katie Dill](https://pod.wave.co/podcast/y-combinator-startup-podcast/stripe-head-of-design-katie-dill-breaks-down-their-new-website)).

**Visual signatures**
1. **A living field of 3-5 colour blobs** that drift and fold into each other, never resolving into a linear stop-to-stop gradient. It reads as liquid or silk, not as a sunset.
2. **An angled cut.** On 2020 stripe.com the gradient sat in a band clipped at a steep diagonal, and that slant echoed through the page *(practitioner note)*.
3. **Grain or noise over the gradient**, which hides 8-bit banding and makes flat digital colour feel physical ([InstantGradient on grain](https://instantgradient.com/blog/grainy-gradients), [gggrain](https://fffuel.co/gggrain/)).
4. **Editorial calm around the colour.** Huge whitespace, a dark navy or near-black type colour, a single neo-grotesk family, thin dashed column guides. Stripe's dashed vertical lines exposed the layout grid ([DEV discussion](https://dev.to/ben/what-are-some-examples-of-great-landing-pages-5e41/comments)).
5. **Slow motion.** Loops are measured in seconds, not hundreds of milliseconds. Nothing snaps.

### 1.2 Layout and information architecture
- **One long, unbroken vertical document.** The structure is: hero → logos → 3-4 product "chapters" → developer or proof section → global stats → CTA band → footer. Sections are not separated by rules or colour blocks. Separation comes from whitespace (160-240px desktop) and from the mesh appearing, dimming and reappearing.
- **A 12-column grid with visible or implied hairline guides.** Content alternates between a wide left text column (5-6 cols) and a right-side product mock that "floats" slightly over the gradient band.
- **The mesh is a bookend, not wallpaper.** It shows up at full strength in the hero, then as small local patches (a card, a CTA band, the footer). This keeps the calm. A full-page mesh behind body text is the cheap version.
- **Bento grids for features** were introduced on the newer Stripe homepage, with hover modals (same YC podcast).

### 1.3 Signature interactions and scroll behaviour
**The scroll metaphor is weather.** Scrolling doesn't move you between discrete scenes. It changes the conditions of one continuous field.

- **Scroll drives palette and phase, not position.** Keep one fixed WebGL canvas behind the page. As the reader moves through sections, interpolate the four colour uniforms toward each section's palette. For example: hero purple/pink/orange, then a cool teal "developer" section, then a deep navy "enterprise" section. The handoff happens over roughly a viewport of scroll, so a section *dissolves* into the next. There are no wipes, no pins, no snapping.
- **Velocity becomes turbulence.** Map smoothed scroll velocity to a small increase in noise amplitude and speed. When the reader stops, the field eases back to its resting flow over 1-2s. The page "breathes" with the reader. Keep the effect subtle: an amplitude change of about 15% at most.
- **Pointer bends the field.** A low-amplitude attractor under the cursor warps the mesh a few percent, with heavy lag (lerp 0.04-0.08). It should feel like a hand near water, not a spotlight.
- **Headline arrival:** line-by-line rise of 8-16px with opacity from 0, staggered 80-120ms, at 700-1000ms with an expo or quart ease-out. An optional extra: the headline's text fill samples the same gradient (`background-clip: text`), so the words look cut out of the mesh. Stripe's own gradient headline drew criticism in the DEV thread above, so use it once.
- **Section transitions** are colour handoffs plus generous whitespace. The only geometric motion is the angled band edge, which can shift its angle a few degrees with scroll.
- **Stats** are large, light-weight numerals with tabular figures (`font-variant-numeric: tabular-nums`). They count up slowly (1.5-2.5s ease-out) once, when they are 40% visible, and never again. Use a small gradient-filled unit ("+ 135 countries"). A world or globe visual is optional; Stripe used one *(practitioner note)*.
- **Feature list:** a bento grid of quiet cards on white or near-white. Each card holds a tiny local mesh, or a conic-gradient border, that wakes up on hover. The colour brightens, the field speeds up and a soft glow follows the pointer inside the card. Everything else stays still.
- **CTA:** a pill button in the brand ink. On hover, the arrow glyph extends a stem and slides about 3px (the "hover arrow" pattern familiar from Stripe *(practitioner note)*). A secondary ghost button sits beside it. The final CTA band brings the full mesh back at hero intensity.

### 1.4 Component treatments
| Component | Treatment |
|---|---|
| Nav | Transparent over the hero mesh, white text, mega-menu panels that open with a 150ms fade plus 4px drop and a caret that slides to the hovered item. It turns solid white with a hairline shadow after the hero. |
| Buttons | Pill radius, solid ink or white, 600 weight. Arrow micro-interaction. No gradient-filled buttons, because the mesh is the only gradient. |
| Cards / features | White, 8-12px radius, ultra-soft multi-layer shadow. A local mini-mesh or conic border appears on hover. |
| Stats | Big light numerals. Gradient used only on the unit or a thin underline. Dashed column guide behind. |
| Timeline / steps | A thin vertical line whose stroke fills with the gradient as you scroll (scroll-linked `stroke-dashoffset`). Step dots fill with colour when reached. |
| Testimonial | Large serif-italic quote (accent family) on a pale ground, small round avatar, company logo. Crossfade 600ms between quotes, no carousel arrows. |
| FAQ | Accordions on white. A plus rotates to an x, height animates 200-250ms. Very quiet. |
| Footer | Either a final mesh band behind the CTA, or a light grey multi-column sitemap. The mesh does not appear behind dense links. |
| Media | Floating product UI mocks with deep soft shadows that "hover" over the band edge and parallax at 0.9-0.95x. |

### 1.5 Typography and colour
- **Type (Google Fonts):** **Inter Tight** 500-600 for display, tracking -0.02 to -0.035em, sentence case. **Inter** 400 or 450 for body at 17-18px with 1.55 line-height. Optional accent: **Instrument Serif** italic for one word or the quote style. Alternatives: **Manrope**, **Figtree**. Stripe itself uses Söhne, which is not on Google ([fontalternatives](https://fontalternatives.com/inspiration/stripe-sohne/)).
- **Colour:** ground `#F6F9FC`, ink `#0A2540` (deep navy), brand anchor `#635BFF` ([secondhand design-system notes](https://opendesigner.io/nl/blog/recreating-stripe-linear-vercel-design-systems-with-design-md)). The four mesh stops commonly reproduced from Stripe's CSS are `#EF008F`, `#6EC3F4`, `#7038FF`, `#FFBA27` *(practitioner note; verify against whatamesh defaults)*. A cool section palette might be `#00D4FF`, `#3EE1A8`, `#80E9FF`, `#0A2540`. A dark section: `#0A2540` → `#1A1F71` with `#635BFF` glints.

### 1.6 Implementation
- **WebGL (recommended):** a single full-viewport `<canvas>` with a subdivided plane, vertex displacement by simplex noise and colour mixing in the fragment shader. Use [whatamesh/MiniGl](https://whatamesh.vercel.app) as reference, or **Paper Shaders**: a zero-dependency vanilla or React library with an animated *Mesh Gradient* (flowing colour spots on separate trajectories), *Static Mesh Gradient* (up to 10 spots, warping, grain) and *Grain Gradient* ([shaders.paper.design](https://shaders.paper.design/static-mesh-gradient), [grain gradient](https://shaders.paper.design/grain-gradient)). Pin the 0.0.x version.
- **CSS fallback:** 4-5 stacked `radial-gradient()`s with registered `@property` colour and position custom properties animated by keyframes, plus an SVG `feTurbulence` grain layer.
- **Scroll linking:** drive section palettes from IntersectionObserver or from CSS scroll-driven animations (`animation-timeline: view()` / `scroll()`, [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll-driven_animations/Timelines), [WebKit guide](https://webkit.org/blog/17101/a-guide-to-scroll-driven-animations-with-just-css/)). Feed the result into the shader uniforms.
- **Performance:** Stripe-style WebGL "sucks up a ton of battery" (GSAP thread). Pause the rAF loop when the canvas is off-screen; the original had a ScrollObserver for this, per the gist. Render at 0.5x DPR, cap at 30fps when idle, and drop to a static frame on `navigator.hardwareConcurrency <= 4` or save-data.
- **Accessibility:** `prefers-reduced-motion: reduce` gives a static mesh with no velocity turbulence and instant palette changes. Check text contrast against the *brightest* point of the field, or keep text off the mesh entirely. Grain must not reduce small-text legibility.

### 1.7 Anti-patterns
- A mesh behind every section, which turns "editorial calm" into a screensaver.
- Gradient buttons, gradient text everywhere, glassmorphism cards on the mesh.
- Fast or saturated looping (sub-3s cycles), rainbow hue spins, banding with no grain.
- Generic "aurora blobs" (5 blurred circles drifting on black) with no palette logic and no scroll relationship. This is the default 21st.dev look ([example](https://21st.dev/@dev.yadhakim/components/aurora-background)).
- **What makes it feel like another style:** If you add pinned scroll scenes, snapping or discrete reveals, it becomes "cinematic". If you darken it and add neon, it becomes synthwave or VHS. Its identity is *continuity*. Any hard cut breaks it.

### 1.8 UX signature
Scrolling a gradient-mesh site should feel like drifting through one continuous, slowly breathing colour field that *responds to how you move*. It ruffles slightly when you scroll fast and settles when you stop. As you pass from one product chapter to the next, the whole atmosphere quietly shifts hue rather than cutting to a new scene. Nothing snaps, pins or announces itself. The content floats on generous white space and the colour does the storytelling. The visitor should leave with a sense of calm competence, not a memory of any single animation.

---

## 2. Comic book

### 2.1 Origin and defining aesthetic
American comic books (1930s onward) and newspaper Sunday strips (1890s onward) were printed by letterpress and later offset. Cheap shading and secondary colours came from the **Ben Day process**. Benjamin Day invented it in 1879: fine dot patterns in cyan, magenta, yellow and black mix optically, so yellow and cyan dots make green and sparse magenta dots make pink ([Wikipedia: Ben Day process](https://en.wikipedia.org/wiki/Ben_Day_process), [publicdelivery.org](https://publicdelivery.org/what-is/ben-day-dots)). Colour pages were hand-separated onto up to nine acetate sheets per page, and the black plate was engraved separately ([Legion of Andy, Ben Day series](https://legionofandy.com/2016/03/04/the-history-of-ben-day-dots-part-6-letterpress-printing-1890s-early-sunday-comics/)). Pop art, Lichtenstein especially, later made the dots iconic.

**Panel grammar (the essential part):**
- **Panels and gutters.** The gutter is the white space between panels. Vertical gutters are often thinner than horizontal ones, so the reader groups each row ([Glossary of comics terminology](https://en.wikipedia.org/wiki/Glossary_of_comics_terminology)).
- **Closure.** McCloud's *Understanding Comics* argues that the reader's mind fills the gutter: "nothing is seen between panels" yet the reader builds a continuous reality. He classifies six panel-to-panel transitions: moment, action, subject, scene, aspect and non-sequitur ([Hooded Utilitarian on closure](https://www.hoodedutilitarian.com/tag/closure/)). **For the web, the gutter is where scroll lives.**
- **Reading order.** Left to right, top to bottom, in a Z-path. Panel *shape* carries meaning: wide panels for establishing shots, tall for falls or height, slanted for action, borderless for timelessness or memory. Characters break the frame for impact.
- **Captions vs balloons.** Captions are rectangles holding narration ("MEANWHILE..."), often yellow and pinned to a panel corner. Speech balloons are ovals with tails pointing at the speaker's mouth, and tails should not cross ([Comicraft glossary](https://balloontales.com/?p=418), [lettering legibility guide](https://cmerritthoughton.substack.com/p/is-your-lettering-chaos-on-the-page)). Other types: thought balloons (cloud plus bubble trail), whisper balloons (dashed), shout and burst balloons (spiky) and double-outline balloons for emphasis ([Blambot grammar](https://blambot.com/articles_grammar.shtml)). Lettering conventions: all caps, bold italic for stressed words, ellipses of exactly three dots across balloons, double dash for interruption, and roughly one letter-width of "air" inside a balloon (Blambot, Comicraft).
- **SFX lettering.** Sound effects are hand-drawn display letters integrated into the art at the action's scale, angle and energy, often with outline, drop shadow and a slight perspective ("KRAK!", "WHAM").

**Visual signatures:** black ink holding lines of uneven weight; flat CMYK brights with Ben-Day tints; white gutters on off-white newsprint; all-caps lettering in balloons; explosive SFX; cover furniture (issue number, price box, publisher corner box).

### 2.2 Layout and information architecture
- **The page is the unit, not the section.** Group content into "pages" or "issues", each a 4-9 panel grid. A **splash page** is the hero: one full-bleed panel with the title logo and an intro caption. Each subsequent chapter is one page.
- Common grids: the 9-panel grid (3×3, rhythmic and steady), a 6-panel grid, and 2 wide plus 3 narrow tiers. A **wide establishing panel** opens each page. **Inset panels** carry details such as a stat or a close-up of a UI element.
- **Two reading models.** (a) *Print page:* a pinned viewport with guided panning across a page grid. (b) *Webtoon or infinite canvas:* a vertical strip where panels are spaced out for phones and balloons and SFX float in the white space between panels ([UX Collective on comic UX](https://uxdesign.cc/the-best-ux-for-comics-so-far-b0c75bc76c03)). Use (a) on desktop and (b) on mobile. This is a real UX difference, not just responsive reflow.
- A product story maps naturally to comic structure: **problem (villain) → hero arrives (product) → action sequence (features) → resolution (results) → "NEXT ISSUE" (CTA)**.

### 2.3 Signature interactions and scroll behaviour
**The scroll metaphor is the reader's eye moving through a page.** Scroll doesn't move the page. It moves *attention* from panel to panel.

- **Guided view on scroll (desktop).** Pin each page. Scroll steps through panels in reading order, using discrete steps with scroll-snap or a ScrollTrigger timeline with labels. The camera zooms and pans so the active panel is near full-size, and panels already read dim to about 60% rather than disappearing. At the end of the page the camera **zooms out to show the whole page**, the "closure moment", before the next page slides or flips in. This is Marvel Infinite Comics / comiXology Guided View translated to scroll. In Infinite Comics a swipe brought in new balloons, a new panel or a change of focus instead of a page turn ([designboom](https://www.designboom.com/technology/marvel-re-evolution-digital-and-ar-comic-books/), [Comics Beat](https://www.comicsbeat.com/marvel-to-reveal-infinite-plans-at-sxsw)). Critics found full Guided View "nauseating" when it hid context (UX Collective, above). That is why the zoom-out moment and the dimmed read panels matter.
- **Precedents to study:**
  - **Ten Years Away** (Studio375, 2026), a scroll-driven horizontal comic. A fixed React Three Fiber canvas camera drifts through each chapter's panels, Lenis provides smooth scroll, and GSAP animates captions and titles above the canvas. Panels enter scattered, slide into place and merge into the full page. The cursor leaves a **halftone dot trail** ([Codrops case study](https://tympanus.net/codrops/2026/07/08/ten-years-away-designing-an-interactive-comic-for-studio375s-tenth-anniversary/), [DesignRush](https://www.designrush.com/best-designs/websites/ten-years-away-website-design)).
  - **The Boat** (SBS, 2015, Nam Le and Matt Huynh). A vertical scrolling graphic novel with 222 illustrations and 59 animated sequences, parallax that sways text like a boat, sound design and an optional auto-scroll ([SBS](https://www.sbs.com.au/aboutus/2015/04/29/sbs-online-releases-first-ever-interactive-graphic-novel/), [SBS sound and vision](https://www.sbs.com.au/movies/article/2015/04/27/sound-and-vision-boat)).
  - **Hobo Lobo of Hamelin** ([hobolobo.net](http://hobolobo.net)). A horizontal parallax comic where each chapter is one wide page of layered images moving at different speeds, replacing gutters with an unbroken timeline ([ELMCIP](https://elmcip.net/creative-work/hobo-lobo-hamelin)).
  - Awwwards: **The Hybrid4 Graphic Novel** (SOTD 2012, [link](https://www.awwwards.com/sites/the-hybrid4-graphic-novel)) and **Soul Reaper HTML5 Scroll Book** ([link](https://www.awwwards.com/sites/soul-reaper-html5-scroll-book)).
- **Balloons pop in sequence within a panel.** Once a panel is active, its caption slides in from its corner (120ms). Then balloons appear in reading order, each scaling 0.6 → 1.06 → 1 from the tail's anchor point (about 180ms with a back-out ease), 250-400ms apart. Text is real HTML, never baked into images.
- **SFX slam.** An SFX word enters at about 1.8x scale with a -8° rotation and lands with a 2-3 frame camera shake (2-4px). It is the only shake on the page. Speed lines or burst rays radiate behind it.
- **Headline arrival:** the title logo is lettered as a comic masthead and lands as a slam on the splash page. The subtitle arrives as a yellow caption box ("IN A WORLD OF BROKEN CHECKOUTS..."). The headline *is* narration.
- **Stats** are not number cards. They appear as **SFX lettering inside a starburst** ("10×!" "99.9%!") or as a narrator caption with a hero reaction ("THAT'S 40% FASTER!"). Count-ups are a mismatch here. Comics show a frozen moment, so the number slams in already final.
- **Feature list = an action sequence.** Each feature is one panel in a 4-6 panel page. The caption carries the feature name, the balloon carries the benefit in a character's voice, and the panel art shows the UI in use. Vary McCloud transitions: action-to-action for workflow steps, aspect-to-aspect for a feature's facets.
- **Hover/pointer:** the hovered panel lifts (translate -3px, hard offset shadow grows from 4px to 8px with no blur) and its Ben-Day tint intensifies. An optional halftone cursor trail, as in Ten Years Away.
- **CTA:** the last panel of the last page shows a hero pointing at the reader, a balloon reading "YOUR TURN!" and a burst-shaped button. Under it sits a **"NEXT ISSUE →"** caption, or a cover-style price box ("FREE · ISSUE #1"). The button press does a tiny SFX ("CLICK!") burst.

### 2.4 Component treatments
| Component | Treatment |
|---|---|
| Nav | A **cover masthead**: logo lettered like a title, an issue number and date box, a corner box with a mascot head. Menu items read as "CHAPTER 1 · 2 · 3". The current chapter is shown as a highlighted issue number. On mobile, a thumbnail "page strip". |
| Buttons | Thick 3px black outline, flat brand fill, hard offset shadow (4px 4px 0 #000), all-caps lettering. Press = shadow collapses to 0 and the button translates 4px. Primary CTA can be a burst shape. |
| Cards / features | **Panels**: black borders of varying weight, white gutters, a caption box in a corner. Never rounded corners or soft shadows. |
| Stats | Starburst SFX numerals with outline and drop shadow. |
| Timeline / steps | A horizontal **strip** of 3-5 panels, a single row like a newspaper daily strip. Use "LATER..." and "THE NEXT DAY..." captions as step labels. |
| Testimonial | A character portrait panel with a speech balloon pointing at the speaker. Name and role in a small caption. Multiple testimonials form a "letters page" or crowd panel with several balloons. |
| FAQ | A conversation. The reader-character asks in a balloon on the left, the mascot answers on the right. Expanding = the answer balloon pops in. Thought balloons for "you might be wondering..." |
| Footer | A **back cover / letters page**: a parody mail-order ad block ("SEND NO MONEY!"), credits box styled like comic credits ("WRITTEN BY... ART BY... LETTERS BY..."), legal in tiny all caps. |
| Media | All imagery inked: black outlines, flat fills, Ben-Day shadows. Photos must be posterised and inked, or placed inside a panel as a "TV screen" within the art. |

### 2.5 Typography and colour
- **Type (Google Fonts):** **Bangers** (400, all caps, tracking 0.02-0.04em) for SFX and display. **Comic Neue** 700 or bold italic, all caps, for balloon lettering; it is a sensible Comic Sans replacement with good legibility. **Luckiest Guy** or **Bowlby One SC** for chapter titles. **Permanent Marker** for handwritten asides. Keep long-form body (legal, FAQ answers) in a plain sans such as **Inter** at 16px, because all-caps comic lettering in paragraphs fails readability.
- **Colour (process approximations):** newsprint `#FBF5E6`, ink `#111111`, process cyan `#00AEEF`, magenta `#EC008C`, yellow `#FFF200`, caption yellow `#FFE45C`, hero red `#E8262B`, deep blue `#1B4F9C`. Ben-Day tints come from uniform dots of these colours at 30-50% coverage over white.

### 2.6 Implementation
- **Page grid:** CSS Grid with explicit `grid-template-areas` per page layout. Use `clip-path: polygon()` for slanted panels and SVG `<path>` for balloons and tails (a tail anchor point per balloon) so balloons scale crisply.
- **Guided camera:** pin the page container (GSAP ScrollTrigger `pin` with a labelled timeline, or CSS `position: sticky` plus scroll-driven animations). Animate a wrapper `transform: scale() translate()` to frame each panel. Compute the frame from `getBoundingClientRect()` of the panel and only animate transforms. A WebGL camera (R3F, as in Ten Years Away) is optional for depth or parallax.
- **Ben-Day:** `radial-gradient(circle, color 30%, transparent 31%)` with `background-size: 6px 6px`, on a pseudo-element with `mix-blend-mode: multiply` ([CSS-IRL halftone patterns](https://css-irl.info/css-halftone-patterns/)). Ben-Day dots are uniform-size tints, not tone-varying halftone. That distinguishes comic from the Halftone style.
- **Inking photos:** an SVG filter chain (`feColorMatrix` → threshold via `feComponentTransfer` discrete → edge via `feConvolveMatrix`), or pre-process assets server-side in the engine pipeline.
- **Accessibility:** balloons and captions must be real text in DOM reading order. Order them as a sequence per panel, with `aria-label`s such as "Panel 3 of 6". Avoid all-caps for anything over about 25 words. Under `prefers-reduced-motion`, disable camera zooms and shake, show full pages with all balloons visible and make scroll ordinary. Provide a "read as page / read as strip" toggle. Watch contrast of white lettering on yellow; use black on yellow.

### 2.7 Anti-patterns
- Comic Sans; random "POW!" bursts on every section; dots on everything.
- Content placed in ordinary cards that merely have black borders. Without **sequence** (panels that depend on each other and are read in order), it's just a bold-outline skin, which is the brutalist style.
- Speech balloons containing marketing paragraphs. Balloons hold short spoken lines of about 25 words at most.
- Count-up stats, fade-up reveals and smooth parallax, all of which are borrowed from generic SaaS.
- **What makes it feel like another style:** If you use halftone dots on photos, it reads as the *Halftone* style. If you drop the panel sequencing and keep thick borders and offset shadows, it reads as neo-brutalism. Comic is defined by **closure and sequence**: the gutter between moments.

### 2.8 UX signature
Scrolling a comic-book site should feel like *reading a page with your eyes guided*. Each scroll tick moves the frame to the next panel in Z-order. The caption slides in, the speech balloons pop up one after another in the character's voice, and a sound effect occasionally slams in and shakes the frame. At the end of every page the camera pulls back and you see the whole page you just read, gutters and all, before turning to the next. Your product story is told as a sequence of moments with characters and narration, not as a stack of sections.

---

## 3. Split-flap (Solari board)

### 3.1 Origin and defining aesthetic
Solari di Udine introduced the flap display in 1956, and it spread to hundreds of rail and air terminals ([Monocle](https://monocle.com/business/solari-italian-design-airport-signs/)). Split-flap boards were the standard public timetable in airports and stations from the 1960s to the 1990s, called "Solari boards" (or *Pragotron* in Central Europe) ([Wikipedia](https://en.wikipedia.org/wiki/Split-flap_display)). The Solari Cifra 5 clock (1957, Gino Valle) put the mechanism in homes, and the Cifra 3 (1965) had input from Massimo Vignelli (Wikipedia). Boards were removed in waves: Metro-North by 2014, New York Penn Station in 2016, Philadelphia 30th Street in 2019 ([PhillyVoice](https://www.phillyvoice.com/30th-street-station-solari-board-amtrak-spit-flap-arrivals-departures-sign-officially-leaving/), [Billy Penn](https://billypenn.com/2022/12/05/amtrak-flipboard-philadelphia-30th-street-station-solari-historic-display/)). Today the look lives on in **Vestaboard** (6 rows × 22 columns = 132 characters; Note: 3 × 15) ([vestaboard.com](https://www.vestaboard.com/split-flap-display)).

**How real boards behave (design-relevant):**
- **Mechanism.** Each character position is its own drum or wheel of silkscreened flaps, up to **40 flaps per wheel**. Early versions had four drums of 10 digits for clocks, and 40 flaps allowed words ([Monocle](https://monocle.com/business/solari-italian-design-airport-signs/), [myflyright](https://myflyright.com/blog/the-nostalgic-charm-of-solari-boards-a-journey-through-airport-history)). Larger flaps could carry whole words, such as a destination city or airline logo, on one flap (Wikipedia). That is why destination fields often flip as a *single* unit while time fields flip per digit.
- **One-way sequential cycling.** A drum can only advance forward through its fixed character order, so changing B to A means riffling through almost the whole drum. A split-flap "may cycle through many flaps" and is slower than LED or flip-dot (Wikipedia). The result: **each cell settles at a different moment**, and an update is a ripple of clatter that thins out as cells land.
- **Home position.** Units zero on a blank flap using a Hall sensor. Drive pulses step one flap per polarity reversal, and a hobbyist reports impulses of 40ms to more than 1000ms controlling flip speed ([r/arduino controller post](https://redlib.hackliberty.org/r/arduino/comments/1kmmfs6/split_flap_controller)). A practical web value is **40-70ms per flap step**, so a worst-case full revolution of 40 flaps takes about 1.6-2.8s *(practitioner note)*.
- **Rows and columns.** Typically: **TIME | DESTINATION | VIA / CALLING AT | TRAIN or FLIGHT No. | PLATFORM or GATE | REMARKS / STATUS**. Boards are often bilingual in Italy ("PARTENZE / DEPARTURES"). Remarks show "ON TIME", "DELAYED 10", "BOARDING", "CANCELLED", sometimes on coloured flaps, plus small indicator lamps that blink for boarding *(practitioner note)*. When the top service departs, **the whole board re-flips so every row moves up one line**. That rolling, cascading update is the board's most recognisable event.
- **Legibility.** White characters silkscreened on black flaps, readable from very acute angles ([Monocle](https://monocle.com/business/solari-italian-design-airport-signs/)). A thin horizontal hinge line splits every character.
- **Sound.** A "distinct metallic flapping sound" that draws attention to updates. When the MBTA replaced its Solari boards at North and South Station, it kept a *generated* flapping noise to signal boarding updates (Wikipedia, [Travel Update](https://travelupdate.com/departures-arrivals-boards-sound/)). The sound is functional: it means "something changed, look up".

**Visual signatures:** a black grid of fixed-width character cells; a hinge line through every glyph; uppercase condensed sans; colour-coded status flaps; tabular row structure; a station clock; asynchronous ripple updates.

### 3.2 Layout and information architecture
- **The page is a board.** Content is constrained to a fixed character grid: for example, 22-32 columns on desktop and 12-16 on mobile. Copy *must* be written for the grid, with abbreviations, short words and no paragraphs on the board. That constraint is the style. Long-form text lives on a separate "information desk" panel beneath the board, set in normal type.
- **IA as a timetable.** Every section is a row, a "departure". Columns map to meaning:
  - TIME → order or step ("01", "02", or a literal time)
  - DESTINATION → the feature or section name
  - VIA → the one-line benefit
  - GATE → where it lives in the product, or a link target
  - STATUS → "NEW", "LIVE", "BETA", "SOON" on coloured flaps
- **Header strip:** board title (DEPARTURES / ARRIVALS, or the product name), station clock and date. **Footer ticker:** a single-line "message row" that flips through announcements.

### 3.3 Signature interactions and scroll behaviour
**The scroll metaphor is time passing at the station.** The board stays put in a sticky viewport and *updates* as you scroll.

- **Scroll = the clock advancing.** A station clock in the header maps scroll progress to time, for example 09:00 → 09:45 across the page. Each section threshold is a "departure". When crossed, the top row departs and **every row re-flips upward one line** in a cascade: row by row from the top, 60-90ms stagger per row and 15-30ms per cell within a row, each cell riffling through intermediate characters to its target. Scrolling back reverses it, with "arrivals" flipping back in.
- **The active row expands.** The row at the top, "NOW BOARDING", gets an indicator lamp blinking slowly (1Hz, safe) and opens a detail panel below the board containing the section's full content, screenshot and CTA. So the board is the index *and* the transition engine.
- **Section transitions = board refresh.** For a major chapter change, the whole board clears to blank in a diagonal wave from top-left, then repopulates with the new chapter's rows. A full refresh takes about 1.2-2s. Use it rarely; it's the style's "big moment".
- **Headline arrival:** the hero headline is set on the board. Cells start blank, riffle through the character set, and settle left to right with randomised per-cell landing times, so the word "resolves" with a shimmering edge. The subhead flips in as a second row after the first row's last cell lands. Never all cells at once: the asynchronous settle is the authenticity cue.
- **Stats:** digit-only drums (0-9 plus blank), so numbers *count* naturally by flipping digit by digit like an odometer. The units digit spins fastest and the higher digits tick over less often. Labels sit in a separate word-flap ("UPTIME", "CUSTOMERS"). A stat changing is a real event: do it once on entry, with sound if enabled.
- **Feature list** = the departures table itself, with STATUS flaps colour-coded. Hovering a row gives it a **single-flap twitch** (one cell rattles one step and back, about 120ms), a tactile acknowledgement. Clicking a row makes it the boarding row.
- **Sound:** opt-in only, muted by default with a speaker toggle in the header. When on, play short recorded flap clicks, one per flap step per cell, polyphony-limited so a refresh becomes a natural clatter that thins out. Audio needs a user gesture because of autoplay policy. FlipOff handles this with a single Web Audio clip and a click-to-enable ([FlipOff](https://claudeskills.info/skills/aradotso/trending-skills/flipoff-split-flap-display/)), and react-split-flap-display uses a recorded Vestaboard flip and notes that sound duration must be ≤ step duration ([GitHub](https://github.com/tthompson-figma/react-split-flap-display)).
- **CTA:** the final row reads "YOUR TRIP · GATE 1 · BOARDING" with the indicator lamp. The button is a physical "ticket" or "BOARD →" key. On press, the STATUS flap flips to "CONFIRMED".

### 3.4 Component treatments
| Component | Treatment |
|---|---|
| Nav | A station header strip: board name left, live clock right (flip digits), section links as small word-flaps. The current section's flap shows a lamp. Bilingual secondary labels are a nice touch. |
| Buttons | Rectangular, dark, with a split hinge line across the middle. On press, the top half flips down (rotateX -180°, 150ms) to reveal the pressed state. |
| Cards / features | Rows, not cards. Detail content sits in an "information desk" panel below the board, in normal type. |
| Stats | Digit drums with an odometer cadence. Unit labels on whole-word flaps. |
| Timeline / steps | **"CALLING AT"** stop list. A vertical list of stations with times, a moving "current position" marker and statuses ("DEPARTED", "NEXT", "LATER"). |
| Testimonial | A **message board**: a 6×22 Vestaboard-style grid that flips a short quote (≤ 120 chars) in, holds 6-8s, then flips to the next. Attribution on a small flap row below. |
| FAQ | A **queries board**: questions are rows. Selecting one flips the lower "ANSWER" board, short, with a full text answer in the info desk. One open at a time, as a real board shows one thing at a time. |
| Footer | A ticker message row cycling announcements, plus a plain dark legal area with a small Solari-style analog-digital clock. |
| Media | Screenshots live in the info desk in a bezel. Images can enter with a "flap" reveal: the image split into horizontal strips that flip down in sequence. Use sparingly. |

### 3.5 Typography and colour
- **Type (Google Fonts):** board characters in **Roboto Condensed** 600-700 or **Barlow Condensed** 600, uppercase only, in fixed-width cells. Monospaced alternative: **JetBrains Mono** 700 or **Space Mono** 700. Digits in **Oswald** 600 for tall station-clock numerals. Info-desk body copy in **Inter** or **IBM Plex Sans**, 400. Non-Google option: *Departure Mono* (OFL).
- **Colour:** housing `#0B0B0C`, flap `#1C1C1E` (top half) and `#161618` (bottom half, slightly darker to imply light from above), hinge `#000000` with a 1px `#2A2A2D` highlight, characters `#F2F0E8` (warm white). Status flaps: green `#1E9E5A`, amber `#F2A900`, red `#D7262E`, blue `#1F5FAF`. Page around the board: concrete grey `#2B2D30` or a station-wall cream `#E9E4D8` for an architectural frame.

### 3.6 Implementation
- **Cell DOM:** each cell has four half-elements: current top, current bottom, next top, next bottom. On step, the current top rotates `rotateX(-90deg)` and then the next bottom rotates from `90deg` to `0`. Bob Rost's demo runs the previous-top and next-bottom transitions simultaneously ([bobrost.com demo](https://bobrost.com/demos/airport_board/index.html)). Use `transform-style: preserve-3d`, `backface-visibility: hidden` and `perspective: 300px` on the cell. Add a brief darkening gradient on the falling flap for shading.
- **Cycling:** a fixed character order (space, A-Z, 0-9, punctuation). Each cell steps forward from its current to its target. An implementation that "clatters forward through the character set until it lands" is the authentic one ([jas.it.com splitflap.jsx](https://jas.it.com/src/splitflap.jsx)). Cap steps at about 12-15 for long changes by jumping the start index, so updates stay under 1s while still visibly riffling.
- **Scale:** a 6×32 board has 192 cells. Use one rAF scheduler for all cells instead of per-cell timers. Animate only `transform`. For more than about 400 cells, render to **Canvas 2D** (draw half-glyphs from a pre-rendered glyph atlas, with a skewY or scaleY squash to fake rotation).
- **Libraries/references:** Framer SplitFlap (triggers on load or scroll-into-view, riffle length, stagger, reduced-motion support) ([Framer](https://www.framer.com/marketplace/components/splitflap/)), svelte-split-flap ([GitHub](https://github.com/socketopp/svelte-split-flap)), FlipOff (vanilla, Web Audio).
- **Accessibility:** the board is decorative over a real text layer. Each row should be an `aria-live="polite"` region updated only with the *final* text, never intermediate letters, or hidden from AT with an equivalent visible table in the info desk. Under `prefers-reduced-motion`, cells change instantly (or with a single 1-step flip) and the cascade is replaced by a simple crossfade. Sound off by default. Keep uppercase strings short and use real `<table>` semantics for the timetable.

### 3.7 Anti-patterns
- Flipping straight to the target in one step (a "card flip"), which reads as a flip-clock widget, not a Solari.
- Every cell landing simultaneously. This is the number-one tell of a fake.
- Mixed-case, proportional text or paragraphs on the board.
- Constant idle flipping and autoplay sound.
- Using split-flap as decoration on headings while the page scrolls like any other site. **The board must be the IA**, with rows as sections and refreshes as transitions.
- **What makes it feel like another style:** If you add phosphor green and scanlines, it reads as terminal or VHS. If the flap becomes a smooth card rotation with soft shadows, it reads as generic 3D cards. Its identity is the **fixed grid plus asynchronous mechanical settle plus timetable semantics**.

### 3.8 UX signature
Scrolling a split-flap site should feel like standing in a station hall while time passes. A fixed board fills the screen, the clock in the corner advances as you scroll, and at each "departure" the entire timetable clatters upward one row. Hundreds of little flaps riffle and land at slightly different moments until the board falls quiet again, and the row now "boarding" opens to show its detail. You never feel like you're scrolling *down a page*. You feel like you're watching one board *update*, and every change is an event you hear (if you opt in) and see ripple across the grid.

---

## 4. Retro VHS

### 4.1 Origin and defining aesthetic
This is the home-video era (late 1970s to early 2000s): VCR playback, camcorder footage, rental-store tapes, TV channels. The aesthetic is the *failure modes* of analog magnetic tape and the CRT it played on, plus the VCR's on-screen display (OSD).

**Artifacts and behaviours (be specific):**
- **Head-switching noise:** a band of horizontal distortion at the bottom of the frame, caused by the rotating playback heads switching. TVs hid it with overscan, and some decks masked it with black. On worn tapes the band "bounces" ([AV Artifact Atlas](https://avartifactatlas.com/artifacts/head_switching_noise.html)).
- **Tracking errors:** horizontal noise bars that roll vertically when the tape path doesn't line up with the heads. The user fixes them with a TRACKING +/- control, and the bars slide out of frame as tracking "locks" *(practitioner note)*.
- **Chroma bleed/smear:** colour shifts horizontally, classically trailing to the right, giving red and cyan fringes offset from the luma ([shaders.com VHS docs](https://shaders.com/docs/components/vhs)). Low colour resolution leaves soft, over-saturated reds.
- **Transport modes:** PLAY ▶, PAUSE ‖ (a jittery frame with noise bars on cheap decks), FF ▶▶ and REW ◀◀. *Search* at 3-9x shows the picture with several noise bands. Stop is often a blue screen.
- **OSD:** blocky monospaced white or green text with a black outline, at screen corners: `PLAY ▶`, `SP`/`EP`, tape counter `0:12:47`, `CH 03`, `TRACKING ▮▮▮▮▯▯`. Camcorder burn-ins: `● REC`, `JUL 14 1994`, `9:42 PM`. A "blue background" when there's no signal. VCR setup menus (CLOCK SET, CH PRESET) with a `▶` cursor.
- **Channel change:** a split second of snow and static hiss, then the new picture with `CH 04` top-right, fading after about 3s.
- **CRT layer:** scanlines, slight barrel curvature, vignette, phosphor glow (bloom on highlights).

**Visual signatures:** OSD text, a tape counter or timestamp, rolling tracking bars, RGB fringing, snow, blue screen, 4:3 frames inside a widescreen page, rental-tape labels and cases.

### 4.2 Layout and information architecture
- **The page is a tape, or a TV with channels.** Two IA models:
  - **Tape model (linear):** the site is one tape. Sections are chapters at counter positions (`0:00:00 INTRO`, `0:04:12 FEATURES` ...). The nav is the tape's **index label** (the handwritten sticker on the spine).
  - **Channel model (random-access):** sections are channels. Nav is a channel number pad (`CH 01-07`), and moving between sections is a channel change.
  
  Use the tape model for narrative scroll and the channel model for nav jumps. They combine well: scroll plays the tape, nav changes the channel.
- Content is framed in a **4:3 "screen"** (rounded CRT corners, bezel optional) centred on a dark room-tone ground. OSD sits at the screen corners, not the page corners.
- **A "tape shelf" index:** feature collections as spines on a rental-store shelf, each with a genre sticker and a "BE KIND REWIND" label.

### 4.3 Signature interactions and scroll behaviour
**The scroll metaphor is the transport.** Scroll *is* the tape moving under the heads.

- **Scroll velocity → playback mode with live OSD.** At rest: `PAUSE ‖`, with a subtly jittering frame and one faint noise bar. Slow scroll down: `PLAY ▶` with a clean image. Fast scroll: `▶▶ ×4` / `SEARCH` with 2-3 noise bands, horizontal smear and the OSD counter racing. Scroll up: `◀◀ REW` with the reverse search look. The **tape counter** (top-right) maps to scroll position and shows the chapter name on hover. This is the style's core: the reader always sees what "speed" they're watching at.
- **Tracking lock as the reveal.** Each new section (or its hero media) enters *mistracked*: 2-3 noise bars rolling through it, slight vertical roll, chroma offset of 6-8px. Over about 600-900ms the bars slide off-frame, the chroma converges and the image "locks". This replaces fade-up. Optional: the user can nudge tracking with the pointer's x position or a TRACKING slider in the OSD, a delightful bit of agency.
- **Channel change for nav jumps.** Clicking a nav item gives 150-250ms of low-contrast snow with hiss (if sound is on), a cut to the new section and `CH 04 FEATURES` in green OSD that fades after 3s. A slow full-screen strobe of snow is a photosensitivity hazard; see 4.6.
- **Headline arrival:** typed out as OSD text (blocky monospace, character by character at 30-40ms) in the corner of a blue screen, *or* as a chrome title card that tracks in. Large display headlines get a persistent 1-2px RGB fringe that intensifies only during scroll motion.
- **Stats:** presented as a **VCR setup menu**. A list on a blue screen, a `▶` cursor highlighting the current row as you scroll past, values right-aligned with dot leaders (`UPTIME ......... 99.99%`). Or as counter values (`REC TIME 1,204 HRS`). Numbers "roll" like a mechanical tape counter.
- **Feature list:** either the **OSD menu** (arrow keys work, selection inverts row colours), or the **tape shelf**. Choosing a tape plays an "insert" sequence: the cassette slides into a slot, a whir, about 400ms of blue screen, then `PLAY ▶` and the feature "plays" in the 4:3 screen.
- **Pointer:** hovering media causes a slight tracking wobble (horizontal offset of a few scanlines). The cursor itself can be a small OSD arrow.
- **End of tape = end of page.** The last section ends in snow (low contrast). An "AUTO REWIND" prompt plays a fast reverse scroll to the top with REW effects (≤ 1.5s, skippable), and a tape-ejecting sound if enabled.
- **CTA:** **`● REC`**. The button is the camcorder record dot ("START RECORDING" = sign up). On press, the `● REC` OSD blinks slowly and the timestamp starts running.

### 4.4 Component treatments
| Component | Treatment |
|---|---|
| Nav | A **channel strip** (CH 01 ... CH 06, labels beneath), or a handwritten tape-spine label listing chapters with counter positions. The current channel is shown in the OSD. A small sticky tape counter shows overall progress. |
| Buttons | Physical VCR buttons: dark grey, rectangular, with silver or embossed icons (▶ ‖ ■ ◀◀ ▶▶ ●). Pressed = inset shadow plus a "clunk". The primary CTA is the red ● REC. |
| Cards / features | **Cassette cards** (labelled tape fronts with a handwritten-marker title), **rental cases** (clamshell with a genre sticker and price tag) or OSD menu rows. |
| Stats | VCR setup menu rows with dot leaders, or tape counter readouts. |
| Timeline / steps | The **tape counter timeline**: a horizontal tape-position bar with chapter ticks (0:00 / 0:04 / 0:09) and a playhead. Scroll scrubs it. Steps are "chapters". |
| Testimonial | **Camcorder home videos**: 4:3 frame, `● REC` and a date burn-in, slight handheld shake (reduced-motion safe), quote as a VHS-style subtitle. Or a "viewer mail" segment card. |
| FAQ | **TV listings / program guide**: times, show names (questions), short descriptions (answers) expanding in a guide grid. Avoid Teletext block graphics, which belong to a different style. |
| Footer | **End credits** rolling slowly upward (pausable), then a generic copyright warning screen parody (no real agency seals), then blue screen. |
| Media | Everything in 4:3 with scanlines, soft focus, reduced chroma resolution, dated colour grade. Video loops get a timestamp burn-in. |

### 4.5 Typography and colour
- **Type:** **VT323** (Google, 400) for OSD text, uppercase, tracking 0.04em, sized in multiples for crisp pixels. Alternatives: **Share Tech Mono**, **Silkscreen**. The canonical **VCR OSD Mono** (Riciery Leal, DaFont, over 4M downloads) is not on Google Fonts, so verify its licence ([Designbeep](https://designbeep.com/2026/04/19/vcr-osd-mono-font/)). **Super-VCR Mono** is CC BY 4.0 and recommends 12px multiples ([DaFont](https://www.dafont.com/super-vcr-mono.font)). Tape-label handwriting: **Permanent Marker**. Box-art and chrome titles: **Audiowide** or **Righteous**. Body copy outside the screen in **IBM Plex Mono** or **Inter**. Avoid **Press Start 2P**, which is 8-bit game, a different era.
- **Colour:** no-signal blue `#0026FF` (OSD blue screen; tweak toward `#1A2BD8` to reduce glare), OSD white `#F4F4F4` with black 2px outline, OSD green `#3CFF7A`, REC red `#FF2A2A`, chroma fringe pair `#FF2BD6` / `#2BF0FF`, CRT black `#07070A`, room tone `#121016`, tape-label cream `#EDE6D3`, rental-sticker yellow `#FFD400`.

### 4.6 Implementation
- **WebGL post-process (recommended):** render the screen region (DOM snapshot via texture, or render media and canvases directly) through a fragment shader with:
  - per-line UV x-offset from noise, scaled by `u_glitch` (tracking jitter; [freefrontend spectral effect](https://freefrontend.com/code/interactive-spectral-3d-ghost-effect-2026-02-23/))
  - rolling bands: `smoothstep` bands moving on `y + time`
  - chroma offset: sample R and B with ±x offset
  - horizontal blur for low chroma resolution, scanlines, vignette and a bottom head-switching band
  
  Drive `u_glitch` from smoothed scroll velocity. References: [shaders.com VHS](https://shaders.com/docs/components/vhs), [Godot VHS/CRT shader](https://godotshaders.com/shader/vhs-and-crt-monitor-effect/) (port to GLSL), [VFX-JS](https://tympanus.net/codrops/2025/01/20/vfx-js-webgl-effects-made-easy/) for applying custom fragment shaders to DOM elements, `@react-three/postprocessing` Scanline ([sbcode](https://sbcode.net/react-three-fiber/scanline)).
- **CSS-only layer for text:** RGB split via `text-shadow: -2px 0 #ff2bd6, 2px 0 #2bf0ff`. Glitch slices via `clip-path` on pseudo-elements ([alvarotrigo CSS glitch](https://alvarotrigo.com/fullPage/css-glitch-effect/)). Scanlines via `repeating-linear-gradient` overlay. Noise via SVG `feTurbulence` with `baseFrequency` animated at a low frame rate.
- **Keep text crisp.** Apply heavy distortion only to media and the "screen" layer. Body text gets at most a static 1px fringe. Distorted text is unreadable.
- **Photosensitivity (critical):** WCAG 2.3.1 (Level A) forbids content that flashes more than 3 times in any 1-second period, unless it is below the general and red flash thresholds. Flashing confined to a small area (about 21,824 px² at typical viewing) passes ([DAISY KB](https://kb.daisy.org/publishing/docs/wcag/three-flashes-or-below-threshold.html), [TestParty guide](https://testparty.ai/blog/wcag-2-3-1-three-flashes-or-below-threshold-2025-guide)). Rules for the engine:
  - static/snow must be **low-contrast** (luminance range ≤ about 20%) and never strobe full-screen
  - channel-change bursts ≤ 250ms, once per user action, never looped
  - no red flashing; REC blink ≤ 1Hz
  - noise and roll intensity clamp
  - **`prefers-reduced-motion: reduce` disables velocity glitching, rolling bars, jitter and channel static entirely** (OSD and static scanlines can stay)
  - a visible "TRACKING: CLEAN" toggle that turns effects off for everyone
- **Performance:** one shared WebGL canvas, not per-element shaders. Run at 0.75x DPR. Pause when the tab is hidden. Noise texture is precomputed. Effects idle at near-zero cost when scroll velocity is 0.

### 4.7 Anti-patterns
- Permanent heavy glitch over everything, which makes content illegible and is a seizure risk.
- Using generic "glitch" (digital datamosh, pixel-sorting, cyberpunk neon) instead of *analog* VHS artifacts. Digital glitch is a different aesthetic.
- Synthwave sunsets and grids by default. That's "outrun", adjacent but not VHS.
- OSD text that doesn't *mean* anything. The counter must reflect scroll position, and PLAY/FF must reflect velocity.
- Autoplay hiss or static sound.
- **What makes it feel like another style:** If you keep scanlines but drop the transport metaphor, it becomes CRT or terminal. If you use halftone-like noise as texture only, it blurs into Halftone or riso "grain". VHS's identity is **time-based degradation tied to playback state**. The other styles' degradations (print dots, misregistration) are spatial and static.

### 4.8 UX signature
Scrolling a VHS site should feel like *operating a VCR*. The page is a tape and your scroll wheel is the transport. Scroll gently and the OSD says `PLAY ▶` and the picture is clean. Flick the wheel and it jumps to `▶▶ SEARCH` with noise bars tearing through the frame and the tape counter racing. Stop and it shudders on `PAUSE ‖`. Every new section arrives mistracked and visibly locks into place, nav jumps are channel changes, and reaching the end of the page means the tape runs out and offers to rewind. The visitor feels physically in control of a fragile analog medium.

---

## 5. Halftone

### 5.1 Origin and defining aesthetic
Halftone is the printing technique that renders continuous tone (photographs) as a grid of dots that vary in **size** (AM screening) at a fixed screen frequency. Coarse newspapers ran about 65-85 lpi and magazines 133-150 lpi. CMYK separations use different screen angles (classically C 15°, M 75°, Y 0°, K 45°) to avoid moiré, producing the characteristic rosette pattern *(practitioner note)*. It is related to but distinct from the uniform-dot **Ben Day** tints of comics ([Wikipedia: Ben Day](https://en.wikipedia.org/wiki/Ben_Day_process)). Its web revival draws on three print traditions:
- **Newspaper / broadsheet grammar:** masthead with dateline, edition and price; folds ("above the fold"); multi-column justified text with hairline column rules; kickers, decks and bylines; jump lines ("Continued on A6"); pull quotes; photo captions and credits. Awwwards' newspaper roundup notes paper textures, big headlines, clean grids and retro typography ([Awwwards](https://www.awwwards.com/newspaper-inspired-websites.html)). **Paperfolio** by Niccolo Miranda (Awwwards Site of the Month, November 2021) based its grid on newspaper blocks using *Guardian* terminology, with a menu like torn newspaper pages ([Awwwards](https://www.awwwards.com/niccolo-miranda-paperfolio-wins-sotm-november-2021.html)).
- **Riso / zine:** two- or three-colour spot inks (fluorescent pink, yellow, blue) overprinted with **misregistration** and grain. Riso colours aren't exact Pantone or RGB matches ([SAIC Everything Riso PDF](https://sites.saic.edu/servicebureau/wp-content/uploads/sites/20/2025/03/EverythingRiso_2024.pdf)). The slight plate offset is the signature ([Shutterstock riso tutorial](https://www.shutterstock.com/blog/photoshop-tutorial-mimic-risograph-effect), [Jonathan Stephens, Advanced Riso](https://jonathanstephens.us/play/riso/)).
- **Print production marks:** registration targets (crosshair in circle), colour bars, crop marks, slug lines, plate labels (C/M/Y/K).

**Visual signatures:** photos made of visible size-varying dots; duotone (black plus one spot colour); misregistered overprint; newsprint or uncoated paper texture; strict column grid with rules; blackletter or high-contrast serif masthead; printer's marks at the margins.

### 5.2 Layout and information architecture
- **A broadsheet or zine, read in columns.** The hero is a **front page**: masthead across the top (name, "VOL. 3 · NO. 12", date, price or "FREE"), a lead headline spanning 4-6 columns, a big halftone lead photo with caption, then 2-3 secondary "stories" in narrower columns. There is a fold line partway down.
- **Section = newspaper section** (News / Features / Business / Opinion / Classifieds), each with a section front.
- **Text is laid out in true multi-column flow** on desktop (`columns: 3`, justified, hyphenated, with drop caps), collapsing to one column on mobile. Body copy is a meaningful *part* of the design, not hidden.
- **Riso variant:** a zine of single spreads, two spot colours, bigger type, collage, overprint.

### 5.3 Signature interactions and scroll behaviour
**The scroll metaphor is reading printed matter, and print coming into being.**

- **Images resolve from dots.** As a photo enters the viewport, its halftone screen starts coarse (very low lpi: big dots, abstract) and refines to a fine screen as it reaches the reading position. Scroll progress is the screen frequency. It never fully becomes a smooth photo: it ends as a fine print screen, and the reader can see the dots up close. Out-of-view images return to coarse. A Framer "Shader Shift" component does a related stylized-to-photo scroll reveal ([Framer](https://www.framer.com/marketplace/components/shader-shift/)). Paper Shaders includes halftone dot shaders (round, square, mosaic) ([21st.dev listing](https://21st.dev/@paper-design/components/halftone-dots.md)).
- **Plate-by-plate printing (signature transition).** Major sections or the hero print in **separations**: yellow plate lands, then magenta, cyan and black. Each plate slides in slightly **misregistered** (3-6px offset) and settles toward register, as if the press were pulling a sheet. For riso: colour 1, then colour 2 overprinted with `multiply`, and the offset stays slightly off, which is authentic. About 200ms per plate, once per section.
- **Headline arrival = ink impression, not motion.** No fly-ins. The headline appears in place with a brief **ink spread** (1-2px blur and slight weight gain resolving crisp over about 250ms), like a letterpress kiss. Optional: in the riso variant, a 2-colour misregistered shadow drifts into near-register. Typography is the hero, so it should feel *printed*, not animated.
- **Reading in columns.** On desktop, long articles use horizontal column flow within a pinned "page", or simply clean vertical columns. Jump lines ("Continued on Features, B2 →") are in-page anchor links that "turn" to that section with a quick page-turn or fold. Section fronts have a **fold line**: as you scroll past it, the top half of the page darkens slightly like a fold.
- **Pointer = the loupe (linen tester).** On desktop, hovering any halftone image shows a **circular magnifier** following the cursor that reveals the enlarged dot structure and rosette, with a printer's-loupe rim and measuring scale. This is the style's tactile delight and is unique to halftone.
- **Stats** are **printed infographics**: bar or area charts built from dot fields (density = value), big numerals with a halftone fill, "BY THE NUMBERS" boxes with hairline rules, small-caps labels, source lines in 9pt. No count-up: newspapers print final numbers. Charts can "ink in" plate by plate.
- **Feature list** = **classifieds** or a **"INSIDE TODAY" index**. Tight columns of small ads with all-caps bold lead words ("FAST. Deploys in 30s...") and boxed display ads for the hero features. Or a department index with page numbers that link down.
- **Section transitions:** a new page. Either a horizontal fold or crease shadow with paper texture continuing, or a new "section front" masthead (smaller: "BUSINESS"). Nothing smooth or cinematic.
- **CTA = a clip-out coupon.** Dashed border with a ✂ icon, "CLIP AND MAIL TODAY" heading, form fields drawn as underlines. On submit, the coupon "cuts out", with the dashed border tearing away and the coupon lifting with a slight shadow. Or a "SUBSCRIBE · ONLY $0" box in the masthead ear.

### 5.4 Component treatments
| Component | Treatment |
|---|---|
| Nav | **Masthead plus section bar**: paper name centred in blackletter or display serif, dateline and edition row ruled above and below, section links in small caps separated by bullets. The ears (top corners) hold the weather box and price or CTA. On scroll it collapses to a slim "running head" with the paper name and page number. |
| Buttons | Rectangular, ink black with no radius, small-caps or condensed label. Hover = inverse (paper on ink). Riso variant: spot-colour fill with misregistered black outline offset 2px. |
| Cards / features | **Stories** in columns with kicker, headline, deck, byline and a halftone thumb. Separated by hairline rules, not boxes or shadows. Hero features become **boxed display ads**. |
| Stats | Dot-field charts, a "BY THE NUMBERS" sidebar, tabular figures in a serif with old-style numerals for body and lining for tables. |
| Timeline / steps | A **"Timeline" sidebar** in a narrow column with dates in bold small caps and hairline rules. Or a numbered "HOW IT WORKS" diagram drawn as a print infographic with leader lines. |
| Testimonial | **Pull quotes** set large in italic serif between thick and thin rules, or a **"Letters to the Editor"** column with sign-offs ("— J. Park, Brooklyn"). |
| FAQ | An **"Ask the Editor"** Q&A column. Q in bold, A in body. Expand reveals the answer below a rule. |
| Footer | A **colophon / imprint**: publisher, printing info ("Printed in 2 colours on 80gsm"), registration target, CMYK colour bar, crop marks at the corners, page number. |
| Media | Every photo screened (mono halftone or duotone), with caption and photo credit. Riso variant: 2-colour overprint with grain. Hover gives the loupe. |

### 5.5 Typography and colour
- **Type (Google Fonts):** masthead in **UnifrakturMaguntia** (blackletter) or **Playfair Display** 900. Headlines in **Playfair Display** 700-900, tight leading (1.0-1.05), slight negative tracking, sentence case. Condensed kickers and decks in **Oswald** 500, uppercase with tracking 0.06em. Body in **Libre Caslon Text** or **Source Serif 4** at 17px with justified text and `hyphens: auto`. Captions and bylines in **Libre Franklin** 600 small caps (the Franklin Gothic newspaper tradition). Riso variant: **Archivo Black** or **Space Grotesk** 700 headlines with a heavier, grotesque, zine attitude.
- **Colour:** newsprint `#F3EFE6` (or riso paper `#FBF8F1`), ink `#141414` (never pure black on paper), rules `#141414` at 1px. Spot or riso palettes (screen approximations from SAIC): fluorescent pink `#FF48B0`, yellow `#FFE800`, blue `#0075BF` ([SAIC PDF](https://sites.saic.edu/servicebureau/wp-content/uploads/sites/20/2025/03/EverythingRiso_2024.pdf)). Classic duotone: ink plus one spot colour (e.g. `#141414` + `#FF48B0`, or `#1D3B6F` + `#FFE800`). CMYK plate colours for the separation transition: `#00AEEF`, `#EC008C`, `#FFF200`, `#141414`.

### 5.6 Implementation
- **Halftone images (WebGL, recommended):** a fragment shader divides UV space into a rotated grid of cells (angle uniform). It samples image luminance at the cell centre and draws a circle with radius ∝ √(darkness), with antialiased edges via `fwidth`. A `u_cellSize` uniform is driven by scroll progress for the resolve-from-dots effect. For CMYK, run four passes at different angles and multiply-composite them. References: luma.gl Color Halftone pass ([docs](https://luma.gl/docs/api-reference/shadertools/shader-passes/color-halftone)), Paper Shaders halftone dots, the column.com dot halftone test ([link](https://column.com/dot-halftone-test)).
- **Pure CSS halftone:** a dot pattern (`radial-gradient`) over a tonal map, combined with blend modes and `contrast()` / `blur()` filters ([Frontend Masters, "Pure CSS Halftone in 3 declarations"](https://frontendmasters.com/blog/pure-css-halftone-effect-in-3-declarations/), [Lean Rada](https://leanrada.com/notes/pure-css-halftone/), [CSS-IRL](https://css-irl.info/css-halftone-patterns/)). Caveat: it works best when dots or background are black or white, because colours distort.
- **Duotone / riso:** grayscale-and-contrast the image, then overlay ink layers with `mix-blend-mode: multiply` inside `isolation: isolate`. Offset one layer with `transform: translate()` for misregistration ([MDN mix-blend-mode](https://developer.mozilla.org/en-US/docs/Web/CSS/mix-blend-mode), [Jonathan Stephens](https://jonathanstephens.us/play/riso/)). Add SVG `feTurbulence` grain.
- **Columns:** CSS multi-column (`columns: 18rem; column-rule: 1px solid; column-gap: 2rem;`), `text-align: justify; hyphens: auto;`, `initial-letter: 3` for drop caps (with fallback), `break-inside: avoid` for figures.
- **Loupe:** a second, enlarged instance of the shader (or CSS `background-size` ×4 of a pre-rendered halftone) inside a circular `clip-path` positioned at the pointer. Hide on touch and offer tap-to-magnify.
- **Performance:** render each image to its own canvas only while in view, or use one shared WebGL context with scissor regions. Pre-bake static halftones server-side in the engine pipeline and reserve live shaders for the resolve effect and the loupe.
- **Accessibility:** halftone and duotone photos lose detail, so keep alt text descriptive and offer a "view original" link. Justified narrow columns can create rivers, so use `hyphens: auto` and avoid justification under about 45ch measure. Ink `#141414` on `#F3EFE6` passes AAA. Never place body text on halftone fields. Fluorescent pink and yellow fail contrast as text colours, so use them only for fills and shapes. Under `prefers-reduced-motion`, show images at final screen, skip the plate-registration animation and keep the loupe (it's pointer-driven, not autonomous motion).

### 5.7 Anti-patterns
- A uniform dot overlay on everything, which is the comic Ben-Day look. Halftone dots must **vary with tone**.
- A "newspaper template" with fake lorem columns and an old-paper JPG texture with coffee stains.
- Smooth parallax and fade-up reveals, which are cinematic SaaS motion foreign to print.
- Misregistration so large it reads as a 3D-glasses anaglyph or as VHS chroma bleed.
- Too many spot colours. Riso discipline is two, at most three.
- **What makes it feel like another style:** If you add panels, balloons and SFX, it becomes Comic. If you animate the dots constantly or add scanlines, it drifts toward VHS or CRT. If you drop the columns and mastheads and keep only duotone photos, it becomes a generic "editorial" skin. Halftone's identity is **print grammar (columns, masthead, rules, marks) plus tone-from-dots that you can inspect**.

### 5.8 UX signature
Scrolling a halftone site should feel like *reading a freshly printed paper*. You start at a front page with a masthead and a lead story in columns. As each photograph scrolls into reading position, it resolves from coarse abstract dots into a fine printed screen. Section fronts print themselves plate by plate, with yellow, magenta, cyan and black landing slightly out of register and settling. Hovering any image with a printer's loupe reveals the rosette of dots underneath. Information is presented the way print does it, in columns, pull quotes, classifieds and a clip-out coupon, so the visitor *reads* rather than watches.

---

## Contrast table: UX signatures

| | Gradient mesh | Comic book | Split-flap | Retro VHS | Halftone |
|---|---|---|---|---|---|
| **What scrolling *is*** | Weather: drifting through one continuous field | The eye moving panel to panel through a page | Time passing at a station; the board updates | Tape transport (PLAY / FF / REW) | Reading printed columns |
| **Scroll structure** | Continuous, never pinned or snapped | Pinned pages, stepped panel-by-panel guided view, zoom-out per page | Sticky board, discrete "departures", row cascade | Free scroll; velocity sets playback mode | Normal vertical reading; pages and fold lines |
| **How content arrives** | Gentle line rise; palette dissolves between sections | Caption slides, balloons pop in order, SFX slam | Characters riffle and settle asynchronously | Arrives mistracked, then "locks" | Ink impression; images resolve from dots; plates register |
| **Section transition** | Hue handoff (no cut) | Page zoom-out then page turn | Whole-board clear and repopulate | Channel change (brief low-contrast snow) | New section front / fold |
| **Stats** | Light numerals, slow single count-up | Starburst SFX numerals, no count | Digit drums, odometer cadence | VCR setup-menu rows / tape counter | Dot-field infographics, final numbers |
| **Feature list** | Quiet bento; local mesh wakes on hover | Action sequence of panels | Departures-table rows with status flaps | OSD menu or tape shelf ("insert tape") | Classifieds / "Inside" index |
| **Pointer delight** | Field bends near cursor | Panel lifts, hard shadow | Single-flap twitch on row hover | Tracking wobble / tracking knob | Printer's loupe reveals dots |
| **CTA** | Pill + extending hover arrow; mesh returns | "Your turn!" final panel, "Next issue" | "Now boarding, Gate 1" row, lamp | ● REC "start recording" | Clip-out coupon |
| **Sound (opt-in)** | None | Optional SFX click | Flap clatter (signature) | Hiss, clunk, whir | Paper rustle (optional) |
| **Core motion risk** | Battery; low-contrast text on bright mesh | Zoom/shake nausea | Cell-count performance; screen-reader noise | **Photosensitive flashing**; legibility | Rivers in justified text; detail loss in photos |
| **Reduced-motion mode** | Static mesh | Full pages, normal scroll | Instant cell changes, crossfade | No glitch, roll or static; OSD stays | Final-screen images, no plate animation |

**Engine implication:** each style needs its own **scroll controller**:
- continuous uniform-driver (mesh)
- pinned stepper with camera (comic)
- sticky state machine with event cascade (split-flap)
- velocity-to-mode mapper (VHS)
- in-view progress per media element plus column layout (halftone)

It also needs its own **component vocabulary**: bento / panel / row / menu / column. These five are not interchangeable skins over one template. Swapping the CSS while keeping the controller would recreate the original problem.
