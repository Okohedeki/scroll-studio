# Scroll Studio style research: styles 06 to 10

**Styles:** Glassmorphism, Kinetic typography, Isometric, Clay 3D (claymorphism), ASCII art
**Purpose:** give each style its own UX (layout, information architecture, scroll grammar, interaction model) and not just its own UI skin. Each brief ends with a "UX signature". A comparison table closes the document.

> Reading note: "Motion grammar" lines describe the *kind* of motion the engine should use (easing family, what scroll drives, continuous or stepped). This is the main lever that stops two styles from feeling the same once fonts and colours are removed.

---

## 1. Glassmorphism

### 1.1 Origin and defining aesthetic

- **Lineage:** Windows Vista "Aero Glass" (2007), the iOS 7 blur layers (2013), Microsoft Fluent "Acrylic" (2017), and macOS Big Sur / iOS 14 (2020). Michal Malewicz named it "glassmorphism" in *Glassmorphism in user interfaces* (UX Collective, 22 Nov 2020) ([uxdesign.cc](https://uxdesign.cc/glassmorphism-in-user-interfaces-1f39bb1308c9)). The name spread with a hashtag soon after ([Webflow](https://webflow.com/blog/glassmorphism); [Frontend Focus summary](https://frontendfoc.us/link/103643/rss)). It came back in 2023 with Apple visionOS windows and in June 2025 with Apple's **Liquid Glass**, which adds refraction, specular rims and fluid morphing to plain frosted blur ([LogRocket](https://blog.logrocket.com/how-create-liquid-glass-effects-css-and-svg/); [ekino on Medium](https://medium.com/ekino-france/liquid-glass-in-css-and-svg-839985fcb88d)).
- **Malewicz's four rules:** translucency through background blur, depth through stacked floating layers, vivid colour *behind* the glass, and a faint light edge. He argues that seeing through the layers lets users read hierarchy, because they can tell which pane sits on top ([uxdesign.cc](https://uxdesign.cc/glassmorphism-in-user-interfaces-1f39bb1308c9)).
- **Visual signatures (all six are needed for it to read as glass):**
  1. Frosted panes: `backdrop-filter: blur(12–24px) saturate(140–180%)` over a low-alpha white or tinted fill.
  2. A **saturated, moving world behind** the panes: aurora gradients, blurred colour orbs, a product photo or video. Glass over a flat background is invisible.
  3. A 1px hairline rim, brighter at the top-left (`rgba(255,255,255,.25–.4)`). Liquid Glass adds a specular highlight and chromatic fringe at the edge.
  4. Several z-layers at once: a pane on a pane on a backdrop, with soft large drop shadows.
  5. Fine grain or noise (2 to 5% opacity) on the pane, which stops it looking like a flat grey rectangle.
  6. Rounded continuous corners (16 to 32px, or full pills for chrome).

### 1.2 Layout and information architecture

- **Two planes:** (a) a full-bleed, continuous **backdrop world** that runs the whole page length and changes hue per section, and (b) **floating glass panels** that hold all the content. Content never sits straight on the backdrop. It always sits on glass.
- **Grid:** a loose 12-column grid with panes offset at different depths. Panes overlap one another and overlap backdrop objects on purpose, because the overlap is where the effect shows. A *bento of panes* works for features. Dense dashboards look like iOS Control Center or widget stacks.
- **Section separation:** no rules, borders or background bands. A section ends when the backdrop changes (orbs drift, a new hue arrives, a new product image moves behind). The page reads as one continuous space seen through moving windows.
- **Grouping:** related content shares a pane. Sub-groups are *inner panes* with a slightly stronger tint, which gives a nested glass hierarchy. On light themes, keep glass for chrome and cards and put long text on a near-solid surface ([superdesign guidance](https://superdesign.dev/styles/glassmorphism/website)).

### 1.3 Signature interactions and scroll behaviour

- **What scroll drives: things moving *behind* glass.** Glass only reads as glass when the world behind it moves. The core pattern is **differential parallax**. The backdrop moves at 0.3 to 0.6x scroll speed, panes at 1x, and foreground "near" panes at 1.1 to 1.3x. Every pane then refracts a changing image. The visitor sees colour sliding *under* the content.
- **Pinned lens:** a large glass pane is pinned (sticky) while a vivid scene (product render, video, gradient object) scrolls or rotates beneath it. Copy on the pane changes in steps while the "lens" stays put. This is Apple's visionOS / Vision Pro product-page language: windows float over a live environment ([apple.com/apple-vision-pro](https://www.apple.com/apple-vision-pro/)).
- **Exploded layers (feature reveal):** a stack of 3 to 5 panes starts collapsed into one, then fans apart in z (translateZ, scale and y-offset) as you scroll. You can see each layer through the others. This makes the "layered" claim literal.
- **Panel arrival:** panes *condense*. Opacity goes 0 to 1 and the pane rises 24 to 40px, with a short delay between the frost layer and the text layer. Don't animate the blur radius (expensive). Cross-fade a pre-blurred backdrop layer instead.
- **Headline:** large, light or regular weight on a big hero pane. A colour orb drifts behind the letters on scroll, so the headline appears lit by it. Liquid Glass variant: the headline sits under a small moving "lens" pill that magnifies or refracts it.
- **Stats:** small square glass widgets (iOS-widget metaphor), number large and light (300 to 400), label small. Numbers count up when the pane condenses. A ring or progress arc inside the widget can fill on scroll.
- **Feature list:** a bento of panes, or a "dock". Hover enlarges a pane and brightens its rim. Scroll-pinned: the backdrop recolours per feature while the pane content swaps.
- **Pointer:** a **specular highlight follows the cursor**. Set a radial-gradient at `--mx/--my` on the pane's rim and sheen layer, add 2 to 5 degrees of tilt, and optionally a small parallax of the backdrop orb against the pointer. The [FreeFrontend glass collection](https://freefrontend.com/css-glassmorphism/) documents cursor-tracked frost and SVG-noise buttons.
- **Section transitions:** continuous. The backdrop interpolates hue, and orbs reposition and morph (a WebGL gradient mesh or blurred SVG blobs), so nothing cuts.
- **CTA:** the primary CTA is **solid** (filled with the brightest backdrop hue, or white with dark text) and sits on a glass slab. Glass-only CTAs fail contrast. Hover adds a rim glow and a slight lift. Liquid Glass variant: the pill "wobbles" or morphs on press (scale 0.97 with a spring back).
- **Motion grammar:** smooth, continuous, eased (cubic-out, 600 to 900ms equivalents). Scroll smoothing (Lenis) suits it. No bounce, no steps. The emotion is calm depth.

### 1.4 Component treatments

| Component | Glassmorphism treatment |
|---|---|
| Nav | A **floating detached pill**, centred or right, 12 to 16px from the top. Frosted, with a hairline rim. It shrinks and gets more opaque after about 80px of scroll. Use Josh Comeau's extended-backdrop technique so the blur also samples content just *below* the bar ([joshwcomeau.com](https://joshwcomeau.com/css/backdrop-filter)). |
| Buttons | Primary: solid fill and pill shape. Secondary: glass pill with a rim. Tertiary: text with an underline glow. |
| Cards / features | Glass panes with a nested inner pane for the icon. Icons are monochrome white line icons or small refractive 3D glass objects. |
| Stats | iOS-style widgets (2x2 grid of square panes). Large light numerals with a small caps label. |
| Timeline / steps | Panes stacked in z. The active step comes forward (scale 1, full opacity, stronger blur) and inactive steps recede (scale 0.92, 50% opacity). Alternative: a horizontal dock of steps with a glass "magnifier" sliding over the active one. |
| Testimonial | A large pane with the avatar in a glass circle. The quote is light weight, about 28px. The backdrop behind it is a blurred close-up of the customer's photo, so their colours tint the glass. |
| FAQ | Each item is a slim glass bar. When it expands, the body pane uses a denser tint (alpha 0.6 or more) for readability. |
| Footer | One wide glass slab over the final, most saturated backdrop. Links are in columns. Optionally a giant faint wordmark sits *behind* the glass so it reads blurred. |
| Images / media | Media lives **behind** the glass, as backdrop, not inside cards. Inside a pane, images get rounded corners and a glass bezel frame. |

### 1.5 Typography and colour

- **Fonts (Google):** Inter or Inter Tight (closest to SF Pro), Manrope, Plus Jakarta Sans, Outfit, Figtree. Display 500 to 600 with tracking -0.02 to -0.03em. Body 400 with tracking 0. Sentence case. Large numerals in 300.
- **Dark palette (default):** base `#0B0B1A`; orbs `#6E56CF` (violet), `#FF5FA2` (pink), `#2FD3F5` (cyan), `#FFB86B` (amber); glass fill `rgba(255,255,255,0.08–0.16)`; rim `rgba(255,255,255,0.28)`; text `#FFFFFF` and `#C9CCE0` (secondary).
- **Light palette:** base `#EEF1F8`; orbs `#A5B4FC`, `#F9A8D4`, `#67E8F9`; glass `rgba(255,255,255,0.55)`; rim `rgba(255,255,255,0.8)`; text `#0F172A`.
- Rule: the backdrop holds all the saturation. The UI itself stays near-neutral.

### 1.6 Implementation techniques and caveats

- **CSS core:** `background: rgba(255,255,255,.1); backdrop-filter: blur(16px) saturate(160%); border: 1px solid rgba(255,255,255,.28); box-shadow: 0 8px 32px rgba(0,0,0,.25);` plus an inline SVG `feTurbulence` noise layer. Support for `backdrop-filter` is about 97% (Safari 18 dropped the prefix requirement in Sept 2024) ([Webflow](https://webflow.com/blog/glassmorphism); [web.dev](https://web.dev/articles/backdrop-filter)).
- **Better frost (Comeau):** put the backdrop in a child at `height: 200%`, trim it with `mask-image` (not `overflow:hidden`, which clips before filtering in Chrome), and add `pointer-events:none`. Add a separate `.backdrop-edge` with `blur(8px) brightness(120%)` for a glassy edge. Use SVG masks for rounded corners. A known Firefox bug breaks `backdrop-filter` on sticky elements whose ancestor has overflow plus radius ([joshwcomeau.com](https://joshwcomeau.com/css/backdrop-filter)).
- **Liquid Glass (refraction):** `backdrop-filter: url(#lens)` pointing at an SVG `feDisplacementMap`. This works **only in Chromium**. Safari and Firefox fall back to plain blur, and refraction can't extend beyond the element's box ([LogRocket](https://blog.logrocket.com/how-create-liquid-glass-effects-css-and-svg/); [buildmvpfast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026); [liquid-glass-js](https://cdn.jsdelivr.net/npm/liquid-glass-js@0.1.0/README.md)). Treat it as a progressive enhancement.
- **3D glass objects:** three.js `MeshPhysicalMaterial` with `transmission`, `thickness` and `roughness` ([Codrops: Transparent Glass and Plastic in Three.js](https://tympanus.net/codrops/?p=57089)), or drei `MeshTransmissionMaterial` for refractive hero objects ([Codrops: light and refraction in a glass torus](https://tympanus.net/codrops/?p=89382)).
- **Backdrop:** a WebGL gradient mesh (a cheap fragment shader on one quad), or 3 to 5 large blurred SVG/CSS blobs animated with transform only.
- **Performance:** every `backdrop-filter` element needs a readback of the pixels behind it and a blur pass *whenever anything behind it changes*, which in a parallax page means every scroll frame. Cap it at about 3 or 4 large blurred surfaces per viewport. Never animate the blur radius. Keep blur at 24px or less on mobile. Stacking many blurred layers full-screen hurts mid-range Android ([buildmvpfast](https://www.buildmvpfast.com/blog/liquid-glass-css-backdrop-filter-recipes-2026)). Use `@supports not (backdrop-filter: blur(1px))` to fall back to `rgba(20,20,35,.85)`.
- **Accessibility:** contrast must pass against the **worst-case** pixel that can pass behind the pane. Raise the tint alpha until it does (often 0.5 or more for body text) or add a dark scrim. Respect `prefers-reduced-transparency` where supported (raise alpha to about 0.9) and `prefers-reduced-motion` (freeze backdrop drift and parallax, keep the static colours).

### 1.7 Anti-patterns

- Glass cards on a **static** gradient. Nothing moves behind them, so they read as grey translucent boxes. This is the number one cliché.
- Every element in glass, including body text, buttons and inputs. Contrast collapses and hierarchy disappears, which defeats Malewicz's point about readable depth.
- Purple-to-pink stock gradient with three identical floating cards: the 2021 Dribbble template.
- Animating `blur()` values, or 10 or more blurred elements on screen (jank).
- Using the glass CTA as the primary action.
- **Sameness risk:** glass collapses into Clay or generic "soft UI" if depth comes from *shadows* instead of *transparency plus parallax*. It collapses into any "dark SaaS" page if the backdrop doesn't move. Its depth must be optical (see-through), never physical (mass).

### 1.8 UX signature

Scrolling a glassmorphic site should feel like **looking through a stack of windows at a living world moving behind them**. The content panes stay calm and readable while saturated colour, light and product imagery slide, drift and recolour *underneath* at a different speed. The visitor feels depth because the backdrop changes through the glass, not because of shadows. The key moment is a pinned glass lens: the words stay still while the scene beneath it transforms. No other style asks the visitor to watch what is *behind* the content.

---

## 2. Kinetic typography

### 2.1 Origin and defining aesthetic

- **Lineage:** experimental film (Len Lye, Norman McLaren), Saul Bass's title sequences from the 1950s (*The Man with the Golden Arm*, *North by Northwest*, *Psycho*), where letterforms act as metaphors, and Pablo Ferro ([FEVR history](https://wearefevr.com/the-history-of-kinetic-typography); [Eye Magazine](https://eyemagazine.com/feature/article/jump-cuts)). Kyle Cooper's *Se7en* titles (1995). Muriel Cooper's MIT Visible Language Workshop "Information Landscapes" demo (TED5, 1994), which flew through 3D typographic space. On the web: the Flash-era work of Yugo Nakamura, then variable fonts (OpenType 1.8, 2016). Today **DIA** (Mitch Paone and Meg Donohoe) define "kinetic identities", where motion is part of the brand system ([dia.tv](https://dia.tv/); [Creative Review](https://www.creativereview.co.uk/dia-agency-typography-motion-design/)).
- **Visual signatures:**
  1. **Type is the image.** Words are set at 10 to 30vw, cropped by the viewport, filling the screen edge to edge.
  2. **Elastic letterforms:** variable-font axes (weight, width, slant) change in real time, so words stretch, inflate and condense.
  3. **Marquee rows:** infinite horizontal bands of text, often several rows running in opposite directions.
  4. **Split-text motion:** lines rise from masks, letters stagger, scramble or rotate about chosen transform origins ([Codrops On-Scroll Typography Animations](https://tympanus.net/codrops/2023/01/18/on-scroll-typography-animations)).
  5. A **two-colour, high-contrast palette** with one shock accent, and hard inversions.
  6. Rhythm: motion is timed like music (beats, holds, cuts) rather than as decorative easing.

### 2.2 Layout and information architecture

- **A full-bleed typographic canvas.** No cards, no boxed grid. A 12-column grid exists only to anchor the small text (labels, body copy) in a narrow column against the giant type.
- **Extreme scale contrast:** 20vw display words next to 12 to 14px uppercase labels. Little mid-size type. Sparse density per screen, with one idea per viewport.
- **Sections are words.** Each section opens with one giant word or short phrase ("FAST.", "PRIVATE.", "YOURS.") that acts as both heading and visual. Sections are separated by **colour inversions** (ink on paper, then paper on ink) and by hard cuts, not by spacing or borders.
- **Grouping is typographic:** feature lists are rows of huge words, and stats are giant numerals. Images are rare, used as small inserts *inside* or *between* letters (image in the counter of an "O", or images revealed behind knocked-out text: [Codrops SVG clip-path text](https://tympanus.net/codrops/2024/01/10/experimental-on-scroll-text-animations-with-svg-clip-path); [image expanding within typography](https://tympanus.net/codrops/2024/04/02/on-scroll-expanding-image-animation-within-typography)).

### 2.3 Signature interactions and scroll behaviour

- **What scroll drives: the letterforms themselves, coupled to velocity.**
  - **Velocity-coupled marquees:** marquee rows have a base speed. Scroll velocity adds to it, scroll direction can flip it, and a spring settles it back. Built as `useScroll → useVelocity → useSpring` driving the x offset ([Magic UI Velocity Scroll](https://magicui.design/docs/components/scroll-based-velocity); [motion.dev scroll docs](https://motion.dev/docs/react-scroll-animations)). Personal portfolios such as dennissnellenberg.com popularised a giant name marquee that reverses with scroll direction.
  - **Velocity skew and stretch:** fast scrolling skews lines (skewY up to about 8 degrees), stretches them vertically (scaleY up to 1.15) or blurs them, then they spring back when scrolling stops ([Framer Scroll Velocity Blur](https://www.framer.com/community/marketplace/components/scroll-velocity-blur/)). Codrops' *On-Scroll Letter Animations* moves letters by scroll direction and speed ([Codrops 2021](https://tympanus.net/codrops/2021/01/20/on-scroll-letter-animations)).
  - **Axis scrubbing:** as a word enters, `wdth` goes from 50 to 150 and `wght` from 100 to 900, so the word *inflates* to fill the line. As it leaves, it condenses.
  - **Pinned sentence reading:** a paragraph is pinned and words light up one by one (opacity 0.15 to 1) at reading pace as you scroll. The visitor reads at scroll speed.
  - **Zoom-through:** a giant word scales up until the visitor passes through a letter's counter into the next section ("type as a portal").
- **Headline arrival:** each line rises from an `overflow:hidden` mask (y 110% to 0, staggered 60 to 90ms, expo-out), or letters scramble and settle. Then the headline *keeps responding*, flexing as scrolling begins, so it is never a static block.
- **Numbers:** huge (15 to 25vw) **odometer reels**. Each digit is a vertical strip of 0 to 9 that rolls to its value, scrubbed by scroll rather than timed. Optionally the units ("×", "%", "ms") are set in a contrasting italic serif.
- **Feature list:** a **hover list**. Each feature is a full-width row with a 6 to 10vw word. On hover the row inverts colour, the word widens (wdth axis), and a small image or video follows the cursor. On touch devices, scroll position sets the active row.
- **Pointer:** proximity-based axis modulation. Letters near the cursor get heavier or wider (a "font weight by cursor distance" field, which works well with Roboto Flex or Anybody). A custom cursor shows a short verb ("DRAG", "PLAY").
- **Section transitions:** hard cuts on the beat, full-screen colour inversions, giant words wiping across as marquees. Avoid soft cross-fades.
- **CTA:** the CTA *is* a giant word or marquee ("START NOW → START NOW →"). Hover speeds the marquee, inverts colours, or makes the letters swap order or jump. Add a magnetic pull to a circular "Go" button.
- **Motion grammar:** physics with momentum (springs coupled to velocity), punctuated by snappy expo-out reveals and hard cuts. Motion has *rhythm*: hold, hit, hold.

### 2.4 Component treatments

| Component | Kinetic typography treatment |
|---|---|
| Nav | Minimal: wordmark left, 2 or 3 uppercase links plus a "MENU" word right. Opening the menu gives a full-screen overlay of huge stacked links that slide in line by line. Hovering a link stretches it (wdth). |
| Buttons | Text-first. An uppercase label with an arrow. Hover rolls the label vertically (the old label exits up and a duplicate enters from below). |
| Cards / features | No cards. Use full-width rows separated by 1px rules (the hover list described above). |
| Stats | Odometer numerals at 20vw. One stat per viewport, or three stats stacked as a "type poster". |
| Timeline / steps | Giant step numbers ("01", "02") pinned on the left. Step words slide horizontally across a pinned frame (horizontal scroll section) driven by vertical scroll. |
| Testimonial | A pull quote set at display size with the scroll-lit word-by-word reveal. The attribution is a tiny uppercase label. |
| FAQ | Questions as large type rows. Opening one makes the answer *type in* or rise line by line. The "+" rotates to "×". |
| Footer | A massive wordmark or CTA marquee spanning the full width, often cropped at the bottom edge of the viewport. Small links sit above it. |
| Images / media | Rare, small, and in service of the type: cursor-follow previews, images clipped into letters, video inside a word's counter. |

### 2.5 Typography and colour

- **Variable families with expressive axes (Google):** **Anybody** (wdth 50–150, wght 100–900), **Roboto Flex** (wdth, wght, opsz, GRAD, slnt, XTRA…), **Bricolage Grotesque** (opsz, wdth, wght), **Archivo** (wdth 62–125), **Big Shoulders**, **Unbounded**, **Syne**. For contrast, **Instrument Serif** italic or **Fraunces** (SOFT and WONK axes) on accent words.
- Display: UPPERCASE, leading 0.82 to 0.9, tracking -0.03 to -0.05em. Labels: uppercase 11 to 13px, tracking +0.08em. Body: 16 to 18px in the same family at a normal width.
- **Palettes (two colours plus a shock accent):** ink `#0A0A0A` / paper `#F2EFE8` / acid `#D4FF3A`; or ink `#111111` / paper `#FFFFFF` / signal red `#FF3B00`; or inverted electric `#1B1BFF` on `#F5F5F0`. Inversions swap ink and paper per section.

### 2.6 Implementation techniques and caveats

- **Split text:** GSAP SplitText (free since GSAP 3.13; it adds aria handling and masks) or SplitType. Animate only `transform` and `opacity` on spans.
- **Scroll:** GSAP ScrollTrigger with scrub, plus Lenis. Or native CSS scroll-driven animations (`animation-timeline: view()` with `animation-range: entry 20% cover 40%`) for reveals, gated by `@supports` because it isn't Baseline yet ([Tyler Gaw: scroll-driven write-on](https://tylergaw.com/blog/css-scroll-driven-write-on/); [CSSWG explainer](https://drafts.csswg.org/scroll-animations-1/EXPLAINER.html)).
- **Velocity:** read `ScrollTrigger.getVelocity()` or a Motion `useVelocity`, clamp, spring-smooth, and map to skew, scale and marquee time-scale.
- **Variable axes:** animate `font-variation-settings` or registered custom properties (`@property --wdth`). This re-shapes and re-rasterises glyphs **every frame**, so limit it to one or two display lines, not paragraphs. Use `contain: layout paint` on animated lines.
- **WebGL type:** MSDF text on meshes for 3D twisting type ([Codrops: Kinetic Typography with Three.js](https://tympanus.net/codrops/?p=49770)). For a click-driven page transition, see [Codrops Kinetic Typography Page Transition](https://tympanus.net/codrops/2021/09/29/kinetic-typography-page-transition).
- **Accessibility:**
  - **WCAG 2.2.2 (Pause, Stop, Hide):** auto-moving content running longer than 5 seconds needs a pause mechanism. Infinite marquees need a pause control or must stop under `prefers-reduced-motion`.
  - Split text must keep the real string readable by screen readers: `aria-label` on the parent and `aria-hidden` on the letter spans.
  - Under reduced motion: no velocity skew, no zoom-through, marquees static (or one slow loop), reveals become simple fades.
  - Huge cropped words must not be the only carrier of meaning. Keep a real heading.
  - Don't let skew or blur make text unreadable mid-scroll for long.
  - Practical limit: two or three split-text elements in view at once on older phones ([studiomeyer guide](https://studiomeyer.io/en/blog/kinetische-typografie)).

### 2.7 Anti-patterns

- Every paragraph fading up on enter. That is "scroll-reveal everything", not kinetic typography.
- A marquee bolted onto an otherwise normal card layout.
- Random letter staggers with no rhythm and no meaning. Bass's lesson is that motion should *mean* something (split letters for a split mind) ([Eye Magazine](https://eyemagazine.com/feature/article/jump-cuts)).
- Using a static font where a variable axis is the whole point. Too many typefaces.
- Body copy that moves or scrambles.
- **Sameness risk:** it becomes ASCII art if it turns into monospace and typing. It becomes generic "big bold SaaS" if the type is large but *passive*. It must react to **velocity and the pointer**, not just appear once. The type should behave like a material with elasticity and momentum.

### 2.8 UX signature

Scrolling a kinetic-type site should feel like **playing an instrument made of letters**. The faster you scroll, the more the words skew, stretch and race. When you stop, they spring back and settle into a held typographic pose. Headlines inflate across the screen as they arrive, sentences light up word by word at your reading pace, and marquees surge and reverse with your gestures. There are no cards and few images: the typography *is* the scenery, and your scroll velocity is the conductor.

---

## 3. Isometric

### 3.1 Origin and defining aesthetic

- **Lineage:** axonometric drawing has existed for centuries (e.g. the Chinese scroll *Along the River During the Qingming Festival*). William Farish formalised isometric drawing in *On Isometric Perspective* (1822), and Bauhaus and De Stijl architects used axonometry ([linearity](https://www.linearity.io/blog/isometric-design/); [imarc](https://www.imarc.com/blog/designs-you-should-know-about)). Games: Zaxxon (1982), Marble Madness, SimCity 2000 (1993), Diablo II. Pixel artists use the **2:1 pixel step** (about 26.57 degrees, not a true 30) because 30-degree lines jag ([Pixel Parmesan](https://pixelparmesan.com/fundamentals-of-isometric-pixel-art/); [Slynyrd](https://www.slynyrd.com/blog/2025/1/23/pixelblog-54-isometric-pixel-art)). Then the eBoy pixel cities, ustwo's **Monument Valley** (2014), which uses Escher-like 3D geometry staged for a fixed camera ([Unity case study](https://activation.unity3d.com/case-study/monument-valley)), and Oskar Stålberg's Townscaper. The web had a corporate isometric-illustration wave around 2017 to 2021 ([Speckyboy](https://speckyboy.com/isometric-illustrations-web-design/); [Envato](https://elements.envato.com/learn/isometric-design-trend-web-design)). Codrops connects it to the nostalgia of Populous and Transport Tycoon ([Codrops: Crafting Generative CSS Worlds, 2025](https://tympanus.net/codrops/2025/11/10/crafting-generative-css-worlds)).
- **Visual signatures:**
  1. **Parallel projection:** no vanishing point. Objects keep their size at any depth, and vertical edges stay vertical.
  2. A diamond (rhombic) ground grid at 30 degrees, or 26.57 degrees for 2:1.
  3. **Three-tone face shading** from one fixed light: top face lightest, left face mid, right face darkest.
  4. Miniature "diorama" worlds: cut-away rooms, floating islands, server stacks, city blocks, often on a floating base slab with a visible soil cross-section.
  5. Tiny figures and props to show scale. Precise, clean geometry.
  6. Systems drawn as **exploded stacks** (layers lifted apart) and connected by pipes, roads and data lines.

### 3.2 Layout and information architecture

- **A map, not a page.** Information architecture is *spatial*. The site is one continuous isometric world (city, factory, island chain, circuit board), and each section is a **district or station** on it. Sections are separated by *distance on the map*.
- **Two coordinate systems:** the **world** is isometric, while **UI overlays stay orthogonal and flat** (callout cards, labels, HUD). Text set on isometric planes is hard to read, so use it only for short signage.
- **Callouts:** numbered markers on world objects with leader lines to flat labels. This is the "technical illustration" information pattern.
- **Density:** small objects, high detail, lots of empty "ground". Body copy is short and placed in floating cards anchored to world positions.
- **Grouping:** related features share a plot or building and are connected by roads or pipes, so a relationship is shown as a physical link.

### 3.3 Signature interactions and scroll behaviour

- **What scroll drives: a camera gliding across a miniature world, and the world building itself.**
  - **Camera pan along a path:** the orthographic camera keeps one fixed angle and translates laterally across the diorama from station to station as you scroll, so the world slides past diagonally. A fixed-angle camera is both the calmest option and the cheapest to build ([scroll-world skill notes](https://www.ui-skills.com/skills/oso95/scroll-world)). Zoom, by changing the orthographic frustum, is reserved for "enter this building" moments.
  - **Build-up:** tiles drop in from above and land with a small settle. Buildings extrude upward from the ground (scaleZ 0 to 1). Roads draw themselves. The visitor watches the product being *constructed*, much like Townscaper's block-pop.
  - **Exploded stack:** a product drawn as stacked layers (UI / API / data / infra) separates vertically as you scroll. Each layer's label slides out to the side, then the stack recompresses.
  - **Travelling token:** a packet, car or character moves along the road or pipe in step with scroll progress, linking the stations (how it works / pipeline / steps).
- **Hover:** the tile or building **lifts** (translateZ 8 to 16px, shadow grows), its top face brightens, and a flat label pops. On click, the camera eases to centre on it.
- **Headline:** sits on the flat overlay plane at top-left while the world assembles beside it. Alternatively the headline is extruded isometric 3D letters lying on the ground, which the camera passes.
- **Stats:** **isometric bar towers**, extruded columns rising to their value. A small flat number label floats above each, and a scale figure stands next to the towers for size.
- **Feature list:** each feature is a building on the map. Scrolling flies to it, highlights it (other buildings desaturate to 40%) and shows its card.
- **Section transitions:** never cuts. The camera pans from district to district. A district can "unbuild" (sink into the ground) as the next one rises.
- **CTA:** the final station, where the world is complete. Use a large isometric **keycap button** (top plus two shaded sides) that physically depresses on press (the top translates down and the side faces shrink).
- **Navigation:** a **minimap** or legend with a "you are here" marker. Clicking a district pans the camera there.
- **Motion grammar:** linear-to-gentle easing for camera pans (constant speed, like a model railway), with small mechanical settles on landing (back-out, low overshoot). Everything is precise and toy-like, never squishy. Ideally all motion runs along the three isometric axes.

### 3.4 Component treatments

| Component | Isometric treatment |
|---|---|
| Nav | A flat top bar plus a corner minimap of the world. Links equal districts. |
| Buttons | Isometric keycaps or extruded blocks with three-tone sides that press down. Secondary buttons are flat outline buttons on the HUD layer. |
| Cards / features | Flat white cards with a thin border, pinned to world objects by a leader line and a numbered marker. Small isometric icon per card, drawn on the same grid and light. |
| Stats | Extruded bar towers. Alternatively a pie as an isometric cylinder segment. |
| Timeline / steps | A road, conveyor belt or pipe with stations. A token travels along it with scroll. |
| Testimonial | A tiny person on the map with a speech-bubble card. Optionally the customer's "building" is in the world. |
| FAQ | Flat accordion cards on the HUD plane. Opening one highlights a related object in the world, if relevant. |
| Footer | The **underside** of the world slab: a cross-section of strata (soil, pipes, foundations) with footer links laid out like a legend. |
| Images / media | Product screenshots mapped onto isometric screens (devices or billboards in the world) rather than shown flat, with optional click-to-expand to flat. |

### 3.5 Typography and colour

- **Fonts (Google):** Space Grotesk, Sora, DM Sans or Rubik for UI (500 to 700 headings, sentence case, tracking -0.01em). Pixel-iso variant: **Silkscreen**, **Press Start 2P** or **VT323**, for labels only. Technical callouts: **JetBrains Mono** or **IBM Plex Mono** in small caps for coordinates and numbers.
- **"Blueprint pastel" palette:** sky `#CFE8F3`, ground `#F3EBDD`; neutral block faces top `#FFFFFF` / left `#DCE3EC` / right `#B3C3D6`; accent block faces top `#FF8A65` / left `#F4643F` / right `#D24A28`; secondary `#2EC4B6`; ink and lines `#1D2B3A`.
- **Night-ops variant:** ground `#0F1630`, faces `#2A3A6B` / `#1E2B52` / `#152040`, emissive accents `#4DF0FF` and `#FF4D9D`.
- Rule: every colour exists as a three-tone face set (top +12% lightness, right -15%). That is how the engine keeps the light consistent.

### 3.6 Implementation techniques and caveats

- **CSS 3D:** a plane with `transform: rotateX(60deg) rotateZ(-45deg)` and `transform-style: preserve-3d`. Stack layers with `translateZ(n * h)`. Use a very large `perspective` (about 8000px) for near-isometric, or none for true parallel projection ([Codrops 2025](https://tympanus.net/codrops/2025/11/10/crafting-generative-css-worlds); [Codrops: Isometric and 3D Grids, 2016](https://tympanus.net/codrops/2016/05/25/isometric-and-3d-grids/); [Tuts+](https://webdesign.tutsplus.com/create-an-isometric-layout-with-3d-transforms--cms-27134t)). There is also a 2D trick, `rotate(-60deg) skewY(30deg)`, that avoids preserve-3d ([CodePen post](https://codepen.io/andybarefoot/post/isometric-layout-with-css-grid)).
- **SVG:** compute tile positions with `x = (col − row)·w/2`, `y = (col + row)·h/2` (2:1). This is cheap, crisp and accessible to style. Best for illustration-heavy dioramas and for extruding stat towers.
- **three.js:** `OrthographicCamera` at `(d, d, d)` looking at the origin gives true isometric (about 35.264 degrees down, 45 degrees around) ([Frontend Masters](https://frontendmasters.com/courses/canvas-webgl/capabilities-of-three-js-isometric-perspective)). Use baked lighting textures and Draco or Meshopt GLB for dioramas, and a Raycaster for hover ([freefrontend dioramas](https://freefrontend.com/javascript-diorama/)). Pan the camera with a GSAP ScrollTrigger-scrubbed timeline ([svilenkovic](https://svilenkovic.com/3d/how-to-make-scroll-driven-3d)). Use instancing for many tiles. For interiors, an orthographic camera can't see inside walls, so cut away the front walls.
- **Performance:** many `preserve-3d` DOM nodes create many compositor layers, so keep DOM isometric scenes under about 200 faces, and use SVG or WebGL beyond that. Baked lighting lets the world look rich at near-zero runtime cost.
- **Accessibility:** the world is decorative. Content must exist in a **linear DOM order** (sections, headings) that the camera merely follows. Keyboard focus on a feature card should pan the camera to its building. Under `prefers-reduced-motion`, show a static overview map with cards and no camera flights. Check small labels on pastel ground against WCAG AA.

### 3.7 Anti-patterns

- The 2018 corporate cliché: a generic isometric stock illustration (people on giant phones, floating servers) as a hero image above a normal page. That is decoration, not information architecture.
- Mixed projections: perspective objects in an isometric scene, or inconsistent light direction per object.
- Body text skewed onto isometric planes (unreadable).
- Perspective camera dollies and FOV zooms, which break the parallel-projection contract.
- Overcrowded worlds with no empty ground.
- **Sameness risk:** becomes Clay 3D if objects get soft, blobby and perspective-lit with squishy bounces. Becomes generic "3D hero" if the world is only a hero image and the rest is cards. The isometric UX is **navigating a map with a fixed god's-eye camera**. If scroll doesn't move you across a space, it isn't isometric UX.

### 3.8 UX signature

Scrolling an isometric site should feel like **flying a fixed-angle drone across a tiny, precise model world that builds itself as you arrive**. The camera never tilts or zooms in perspective. It glides diagonally from district to district while tiles drop into place, buildings extrude, layers explode apart to show the stack, and a little packet travels the road between features. The page is a *map you traverse*, with a minimap telling you where you are. Understanding comes from seeing how the pieces physically connect.

---

## 4. Clay 3D (claymorphism)

### 4.1 Origin and defining aesthetic

- **Lineage:** stop-motion claymation (Gumby, Aardman), toy design, and the 2019 to 2021 wave of soft-lit Blender/C4D "toy" renders. Microsoft's **Fluent 3D emoji** (2021) explored clay and wood-carving looks before settling on dimensional, clay-like forms ([Fluent emoji making-of, via elevenforum](https://www.elevenforum.com/t/the-making-of-fluent-emoji-for-windows-11.4340/)). The UI term **claymorphism** was coined around Dec 2021 by Michal Malewicz (Hype4) as a successor to his neumorphism: elements *float* above the background instead of being extruded from it, which fixes neumorphism's contrast and affordance problems ([UX Collective: Claymorphism in User Interfaces](https://uxdesign.cc/claymorphism-in-user-interfaces-1757fabaa377); [theplusaddons](https://theplusaddons.com/blog/claymorphism/)). Adrian Bece's **clay.css** library popularised the CSS recipe ([LogRocket](https://blog.logrocket.com/?p=189948); [OpenReplay](https://blog.openreplay.com/implementing-claymorphism-with-css/)).
- **Visual signatures:**
  1. **Inflated, puffy forms:** very large radii (about 25% of element height), with nothing sharp.
  2. **Double inner shadow plus soft outer shadow:** a dark inset bottom-right, a light inset top-left and a big diffuse drop shadow, e.g. `inset -0.6em -0.6em 1em #bfd1ff, inset 0.4em 0.4em 0.5em #eff3ff, 0.8em 0.8em 2em #bfd1ff` ([superdesign](https://www.superdesign.dev/styles/claymorphism); [OpenReplay](https://blog.openreplay.com/implementing-claymorphism-with-css/)).
  3. **Pastel, candy palette** with shadows *tinted* by the object colour (never grey).
  4. **Matte 3D clay objects and characters:** rounded mascots, chunky icons and "clay noodles", lit by soft top-left key light ([BlenderNation claymorphism asset pack](https://www.blendernation.com/2023/08/05/easy-claymorphism-asset-pack-with-geometry-nodes/)).
  5. **Playful overlap:** 3D objects break out of card edges and peek over them.
  6. Tactility: things look pressable, squeezable and handmade.

### 4.2 Layout and information architecture

- **Chunky, roomy and friendly.** A bento grid of puffy tiles of varied size, generous gutters (24 to 40px), centred hero compositions, low density, and short copy.
- **Objects as protagonists:** one 3D clay mascot or product object accompanies the visitor through the page, much as Kriss AI uses clay-textured rooms and flowing camera moves to feel warm ([Vev 3D examples](https://www.vev.design/blog/3d-website-examples/)).
- **Section separation:** soft coloured "trays" (big rounded containers inset into the page) or blobby wavy section edges, each section in a different pastel. Never hairline rules.
- **Grouping:** related content sits in one tray. Tiles inside a tray can merge with gooey connections (metaball joins) to show relationships.

### 4.3 Signature interactions and scroll behaviour

- **What scroll drives: physical, squishy objects with mass and springiness.**
  - **Drop-and-squash arrivals:** cards and objects fall into place, then squash and stretch on landing (scaleY 0.85 / scaleX 1.1, springing to 1). These are the classic animation principles, which no other style uses.
  - **Scroll-scrubbed clay hero:** a clay object (product or mascot) tumbles, inflates, morphs or gets "sculpted" as you scroll. A Blender image sequence suits Scroll Studio's frame pipeline best, with Spline or three.js for live versions. Spline's own site is a reference for draggable, spinnable playful objects ([One Page Love: Spline](https://onepagelove.com/spline-design)).
  - **Jelly lag:** scroll velocity feeds a spring on each tile's skew and scale, so tiles wobble like jelly when you fling the page and settle when you stop. It differs from kinetic type's velocity skew: here it is *damped wobble of mass*, not *speed lines*.
  - **Inflation:** elements scale from 0.6 to 1 with overshoot (`back.out(2)` or a spring with low damping), as if pumped up.
- **Hover and press:** **press-in**. Buttons squish (scale 0.96, translateY 3px, outer shadow shrinks, inner shadow deepens). Cards dent toward the cursor (small tilt plus local highlight). 3D icons bob, rotate 15 degrees and blink. A blob cursor softly merges with buttons (goo filter).
- **Headline:** words drop in one by one like toys falling into a box, each bouncing. Or the key word is a 3D **inflated balloon-letter** render that wobbles.
- **Stats:** numbers inside chunky pill badges or "clay coins" that pop in with a spring. Progress shown as a tube of paste or a jelly bar filling, with a tiny wobble at the end.
- **Feature list:** a bento of puffy tiles, each with its own 3D clay icon (Fluent-emoji-like) that rotates gently and squashes when hovered.
- **Section transitions:** blobby morphs. A tray stretches into the next tray's shape, or the mascot carries you there (jumps from section to section with scroll).
- **CTA:** a giant **candy button** (deep tinted inset plus outer shadow) that physically pushes in on press and rebounds. Optionally the mascot points at it or presses it at the end of the scroll.
- **Motion grammar:** springs everywhere: low damping, visible overshoot, squash and stretch. Playful timing (anticipation, then action, then follow-through). Elastic, never linear.

### 4.4 Component treatments

| Component | Clay 3D treatment |
|---|---|
| Nav | A floating puffy pill bar (opaque pastel, *not* translucent), radius 999px. Active link in a pressed-in "dimple" state. |
| Buttons | Candy buttons: saturated pastel fill, two inset shadows plus an outer shadow, label in a rounded bold font. They press and rebound. |
| Cards / features | Puffy tiles with radius 32 to 48px. A 3D clay icon breaks the top edge. Each tile has a different pastel. |
| Stats | Clay coins or pills holding big rounded numerals. Bar charts as rounded jelly columns. |
| Timeline / steps | Stepping-stone pills along a curvy path. A clay ball rolls from stone to stone with scroll. |
| Testimonial | A speech-bubble clay shape with the avatar in a puffy round frame. A small 3D emoji reaction pops on enter. |
| FAQ | Pill-shaped questions that "inflate" downward to show the answer (height spring with overshoot). The chevron is a little clay knob. |
| Footer | A big rounded tray in the darkest pastel, with the mascot waving. Links appear as small pills. |
| Images / media | Screenshots in puffy device frames. Photos masked in blobs or squircles. Product shots re-rendered as clay versions where possible. |

### 4.5 Typography and colour

- **Fonts (Google):** **Nunito** (800 to 900 display), **Fredoka** (variable wdth and wght), **Baloo 2**, **Quicksand**, **Varela Round**, **M PLUS Rounded 1c**, and **Lexend** for readable body. Sentence case, tracking 0 to +0.01em, display 700 to 900, line-height 1.1.
- **Palette (pastel candy):** background `#F4EEFF`; tiles lilac `#C9B8FF`, peach `#FFC9A8`, mint `#B8F0D8`, butter `#FFE7A0`, sky `#A8D8FF`, bubblegum `#FFB3D1`; CTA `#7B5CFF` with tinted shadow `#5A3FD6`; ink `#2B2140` (deep plum instead of black).
- Shadows: object hue at about -25% lightness for outer and inner-dark shadows, and +15% for the inner highlight. Never neutral grey.

### 4.6 Implementation techniques and caveats

- **CSS:** shadow stack (outer plus two insets) and large radius ([OpenReplay](https://blog.openreplay.com/implementing-claymorphism-with-css/); [tailwindcss-claymorphism](https://github.com/dulltackle/tailwindcss-claymorphism); [Speckyboy snippets](https://speckyboy.com/css-snippets-claymorphism/)). SVG goo filter (`feGaussianBlur` plus `feColorMatrix` alpha threshold) for merging blobs and the blob cursor.
- **3D:** three.js `MeshMatcapMaterial` with a clay matcap (cheapest convincing clay), or `MeshPhysicalMaterial` with roughness 0.6 to 0.8, low clearcoat and `sheen`. Use a hemisphere light plus a soft key, and baked AO. Rounded geometry (RoundedBoxGeometry, SDF or marching-cubes blobs for morphs). Or a Spline embed (no-code) ([Webflow Spline sites](https://webflow.com/made-in-webflow/spline)).
- **Pre-rendered:** Blender Cycles clay renders as scroll-scrubbed image sequences or video (AVIF/WebP frames). Soft GI and subsurface look far better offline than in real time, and this matches Scroll Studio's frame pipeline.
- **Springs:** Motion springs, GSAP `elastic`/`back`, or react-spring. Map velocity to wobble with a damped spring.
- **Performance:** animating `box-shadow` repaints large blurred areas every frame. Instead animate `transform`, and cross-fade a pseudo-element that holds the "pressed" shadow. Keep 3D to one hero object plus pre-rendered icons (PNG or WebP sprites), not a dozen live meshes.
- **Accessibility:** pastel text is the trap. Use dark ink (`#2B2140` on `#F4EEFF` comfortably passes AA) and never white on pastel. Shadow depth alone must not signal state (add a label, icon or focus ring: a 3px ink outline offset 3px). Under `prefers-reduced-motion`, remove bounces, squash and wobble, and use 150ms fades. Clay improves on neumorphism for contrast but still needs care for low-contrast-sensitivity users ([OpenReplay](https://blog.openreplay.com/implementing-claymorphism-with-css/)).

### 4.7 Anti-patterns

- Neumorphism in disguise: same-colour-as-background elements with grey shadows (low contrast, ambiguous affordance).
- Applying the inset-shadow recipe to *everything*, including text containers and inputs, until the page looks like a bag of marshmallows with no hierarchy.
- Grey or black drop shadows (kills the candy feel). Sharp corners mixed with puffy ones.
- Random unrelated 3D stock emoji scattered as decoration. The object should mean something ([a1.gallery 3D](https://www.a1.gallery/style/3d)).
- Static clay: puffy visuals with flat, linear, corporate motion.
- **Sameness risk:** becomes Glassmorphism if panels go translucent. Becomes Isometric if the 3D goes orthographic and crisp. Becomes generic "3D SaaS" if the motion lacks squash, stretch and overshoot. Clay's identity is **mass and elasticity**: things you could squeeze.

### 4.8 UX signature

Scrolling a clay site should feel like **playing with soft toys on a table**. Everything has weight and squish: cards drop in and squash on landing, tiles wobble like jelly when you fling the page, buttons push in under your finger and bounce back, and a friendly clay mascot or product tumbles, inflates and gets sculpted as you scroll. It is the only style where the visitor senses *mass and elasticity*. The emotional payoff is delight and safety: tactile, forgiving and handmade.

---

## 5. ASCII art

### 5.1 Origin and defining aesthetic

- **Lineage:** typewriter art (late 1800s), Ken Knowlton and Leon Harmon's symbol-mosaic *Studies in Perception I* at Bell Labs (1966), the ASCII standard (1963), line-printer art, BBS and ANSI art groups of the 1980s and 1990s, FIGlet banners (1991), aalib/libcaca (1997), and net.art (Vuk Ćosić's ASCII films, 1998). The demoscene influenced today's generative ASCII artists such as **Andreas Gysin (ertdfgcvb)**, whose ASCII live-coding playground treats each character cell like a fragment-shader pixel ([play.ertdfgcvb.xyz](https://play.ertdfgcvb.xyz/); [Slanted](https://www.slanted.de/?p=782030); [Korben](https://korben.info/ascii-playground-creative-coding-ertdfgcvb.html)). It has returned in developer marketing (terminal emulators, CLIs, AI-agent tools). The animated ASCII ghost on **ghostty.org** is a widely discussed hero ([rahulc0dy write-up](https://rahulc0dy.is-a.dev/stories/the-fun-of-ascii-art-and-animations)). The "terminal aesthetic" has been framed as a return of texture against glossy, generic design ([Medium essay](https://medium.com/@phazeline/the-terminal-aesthetic-and-the-return-of-texture-to-the-web-ed37ee8183bd); [ezascii](https://ezascii.com/blog/the-comeback-of-console-aesthetics-and-ascii-art)).
- **Visual signatures:**
  1. A **monospace character grid**: everything aligns to cells, and images are made of characters by luminance (` .:-=+*#%@` is the three.js default ramp: [threejs AsciiEffect](https://threejs.org/docs/pages/AsciiEffect.html)).
  2. **Box-drawing frames** (`┌─┐ │ └─┘ ═ ║`), rulers, and `[ brackets ]`.
  3. **FIGlet banner** headlines (big letters made of characters).
  4. **Phosphor palettes** (green or amber on black) or "printout" (black on paper), with no gradients or soft shadows ([designmd ASCII/TUI](https://designmd.app/library/ascii-terminal)).
  5. **Blinking block cursor**, `$` prompts, `[ OK ]` logs, progress bars `[████░░░░]`, sparklines `▁▂▃▅▇`.
  6. **Stepped, discrete time:** characters swap, they never tween.

### 5.2 Layout and information architecture

- **A terminal session, a README or a man page.** Information architecture is *sequential and textual*: a prompt, a command, then output. Alternatively it follows document conventions such as `NAME / SYNOPSIS / OPTIONS / EXAMPLES` or `README.md` headings.
- **Strict cell grid:** widths in `ch`, line-height equal to one cell (about 1.2 to 1.5), and columns aligned with spaces like `ls -l`. Left-aligned and dense (60 to 100 characters per line), with lots of structure and no decorative whitespace.
- **Section separation:** ASCII rules (`────────`, `========`), `## headings`, `[01] SECTION` indices, or a "screen clear" between scenes.
- **Grouping:** boxes drawn with box characters, indented trees (`├──`, `└──`), and tables with aligned columns. Optionally a **TUI layout** (panes split like tmux or htop, with a status bar at the bottom).

### 5.3 Signature interactions and scroll behaviour

- **What scroll drives: a command-and-response session, printed in discrete steps.**
  - **Scroll types and prints:** each section begins with a prompt `~/product $ ▌`. Scrolling *types* a command at a scroll-scrubbed rate (`product --features`), then the output prints line by line (a list, a table, a log). Scrolling back un-types it. The visitor drives a fake shell session.
  - **ASCII render scrubbing:** the product or a 3D model is rendered *as characters* (shader-based) and rotates or deforms with scroll, like Ghostty's ghost but scroll-controlled. Character density rises as you approach (sparse dots resolving into dense glyphs).
  - **Decode/resolve:** headings and images start as noise characters and *resolve* into the real text or image as they enter (scramble-decode). GSAP ScrambleText or a custom per-cell resolver.
  - **Progress as text:** `[██████████░░░░░] 67%` bars and `[ OK ]` boot-log lines tick in as the section scrolls.
- **Hover:** **inverse video**. The hovered line or item swaps foreground and background like a selected TUI menu entry, and the cursor becomes a block `█`. Hovering a link scrambles it once. In ASCII fields, characters near the pointer brighten, densify or ripple, so the field reacts per cell (ertdfgcvb-style).
- **Headline:** a FIGlet banner that **prints line by line** or decodes from noise, with a blinking cursor parked after it. The real text is also present as a semantic `h1`.
- **Stats:** `htop`/`neofetch`-style blocks. Aligned label-value tables (`latency ........ 12ms`), bar meters and sparklines. Numbers tick up as discrete integer increments (no easing).
- **Feature list:** **`--help` output**. Each feature is a flag (`--offline   works without network`), or a `tree` listing, or a numbered menu `[1] Sync [2] Share [3] Secure` that the visitor can operate with keys.
- **Section transitions:** screen clear (`clear`), scanline wipe, character rain, or a glitch frame. Use instant cuts with stepped animation (`steps()`), never smooth cross-fades.
- **CTA:** a **copyable install command** in a box (`$ curl -fsSL get.product.sh | sh   [copy]`), and/or an interactive prompt "Press ENTER to start ▌" that really works with the keyboard. On copy, print `✓ copied to clipboard`.
- **Keyboard first:** number keys and j/k navigate sections, and `?` shows shortcuts. A status bar lists them.
- **Motion grammar:** **quantised and discrete.** Typing cadence (30 to 60 characters per second with jitter), frame-stepped animation at 12 to 24fps, glyph substitution and cursor blink. No easing curves, no blur, no scaling. This is the most important difference from every other style.

### 5.4 Component treatments

| Component | ASCII treatment |
|---|---|
| Nav | A tmux/vim-style status bar: `[1]home [2]features [3]pricing  ── product v2.1 ── 12:04`. The active item is shown in inverse video. |
| Buttons | `[ Get started ]` or `> Get started_` in brackets. Hover gives inverse video and press shows `[▓▓▓▓]` for an instant. |
| Cards / features | Box-drawn panels (`┌─ Sync ──────┐`) or `--help` flags. Icons are small ASCII glyph art (3 to 5 lines). |
| Stats | Aligned tables, `[████░░]` meters, sparklines, `neofetch` layout (ASCII logo left, specs right). |
| Timeline / steps | A boot log (`[ OK ] Step 1: Install`), a numbered shell script, or `git log --graph` lines (`* ─┬─`). |
| Testimonial | An email-style quoted reply (`> This saved our team...`) with a `-- name, role` signature, or a `git commit` message. |
| FAQ | A man-page section, or a `[+] Question` / `[-] Question` toggle that prints the answer as output. |
| Footer | vim empty-buffer tildes (`~`), `EOF`, a status line, the licence, and an ASCII logo. |
| Images / media | Rendered through an ASCII filter (canvas or shader), with an optional toggle to show the real image. Video can play as live ASCII. |

### 5.5 Typography and colour

- **Fonts (Google):** **JetBrains Mono**, **IBM Plex Mono**, **Space Mono**, **Geist Mono**, **Martian Mono**, **DM Mono**. Retro CRT: **VT323**. Use one family, two weights (400 and 700), and avoid italics. Case is mixed for body. Headings are UPPERCASE or FIGlet. Tracking 0, because the grid depends on it.
- **Palettes:** phosphor `#33FF66` on `#050A05` (dim `#1A7F33`); amber `#FFB000` on `#120C00`; modern printout `#111111` on `#F5F2EA` with accent `#FF4F00`; Solarized-esque `#93A1A1` on `#002B36` with accent `#2AA198`. Inverse-video highlight swaps foreground and background.
- Optional CRT layer (scanlines, slight bloom, curvature). Use it sparingly and turn it off under reduced motion or high contrast.

### 5.6 Implementation techniques and caveats

- **Content:** real DOM text in `<pre>` or monospace blocks for anything that must be read, copied or indexed. Use box-drawing in text, not images.
- **Animated fields (fast):** Canvas 2D with a **pre-rendered glyph atlas** (`drawImage` per cell, not `fillText`), or a **WebGL fragment shader**. Sample a scene or video into cells, compute luminance, and index into a glyph atlas texture ([Codrops: Creating an ASCII Shader Using OGL](https://tympanus.net/codrops/?p=82209); [offscreencanvas WebGL ASCII](https://offscreencanvas.com/issues/webgl-ascii/)).
- **three.js `AsciiEffect`** is easy (resolution, charset, invert) but DOM-based. It rebuilds a large text block every frame, so it is slow at high resolution and best for small heroes ([threejs docs](https://threejs.org/docs/pages/AsciiEffect.html); [drei AsciiRenderer](https://drei.docs.pmnd.rs/abstractions/ascii-renderer)).
- **Typing and printing:** scroll progress maps to a character index (`text.slice(0, n)`). Use `steps()` CSS animations for the cursor blink.
- **Performance:** the shader approach is O(cells) on the GPU and trivial. A canvas atlas handles about 20k cells at 60fps on desktop. Cap cell count on mobile (bigger cells). Pause off-screen fields with IntersectionObserver.
- **Accessibility:**
  - ASCII art is gibberish to screen readers. Wrap it in `role="img"` with an `aria-label`, or mark it `aria-hidden` and provide a real heading.
  - Typing effects must never *hide* content from assistive technology or from impatient users. Under `prefers-reduced-motion`, print instantly.
  - Avoid flicker and glitch frames that flash more than 3 times per second (WCAG 2.3.1).
  - Phosphor green on black has good contrast, but dimmed text must still pass AA.
  - Keep reading line length at 80ch or less.
  - Keyboard shortcuts must not hijack screen-reader keys. Make them toggleable.

### 5.7 Anti-patterns

- "Hacker movie" clichés: Matrix rain everywhere, green-on-black with fake "ACCESS GRANTED", typing so slow the visitor waits.
- Monospace font on a normal SaaS layout with rounded cards and gradients. That's just a font change.
- ASCII as an image (PNG of characters). It loses crispness, copyability and the live per-cell feel.
- Smooth tweened fades and easing on character elements, which breaks the discrete-time contract.
- Unreadable art-as-content, such as key copy only inside FIGlet.
- **Sameness risk:** becomes Kinetic typography if characters scale, stretch or skew with easing. Becomes "dark dev SaaS" if the terminal is only a hero screenshot. ASCII's UX is **command and response in quantised time on a fixed cell grid**.

### 5.8 UX signature

Scrolling an ASCII site should feel like **operating a terminal session that answers you**. Each scroll step types a command at the blinking prompt and the machine prints its reply line by line: feature lists as `--help` output, stats as meters and tables, a product model rendered live in characters that rotates as you scroll. Everything snaps to a character grid and changes in discrete ticks, with no easing, glow or depth. The page is keyboard-friendly, ends with a real command you copy, and makes the visitor feel like an insider talking directly to the machine.

---

## Contrast table: UX signatures

| | Glassmorphism | Kinetic typography | Isometric | Clay 3D | ASCII art |
|---|---|---|---|---|---|
| **Core metaphor** | Windows over a living world | An instrument made of letters | A miniature model world seen from a drone | Soft toys on a table | A terminal session |
| **Information architecture** | Floating panes over one continuous backdrop | Full-bleed type canvas, one idea per screen | A spatial map: districts and stations, flat callouts | Puffy bento trays, mascot guide | Sequential command, then output; man page or README |
| **What scroll drives** | Differential parallax: the world moves *behind* glass, pinned lens | Letterforms: velocity skew, axis inflation, marquee speed, word-by-word reading | Orthographic camera pan, build-up, exploded stacks, travelling token | Drop-and-squash, jelly wobble, sculpted clay hero | Typing commands, printing output, ASCII render rotation, decode |
| **Source of depth** | Optical (transparency, blur, parallax) | None, purely 2D (scale contrast instead) | Geometric (parallel projection, three-tone faces) | Physical (mass, soft shadows, squish) | None (flat cell grid) |
| **Motion grammar** | Smooth eased cubic-out, continuous | Momentum springs plus snappy expo reveals and hard cuts on rhythm | Constant-speed glides, mechanical settles, axis-locked | Low-damping springs, overshoot, squash and stretch | Quantised steps, typing cadence, no easing |
| **Pointer** | Specular highlight and tilt | Proximity changes font axes, cursor-follow previews | Tiles lift, camera focuses on click | Press-in squish, blob cursor | Inverse video, scramble, per-cell field ripple, keyboard nav |
| **Stats** | iOS-style glass widgets | Odometer reels at 20vw | Extruded bar towers | Clay coins and jelly bars | Meters, tables, sparklines |
| **Feature list** | Glass bento / exploded layers | Hover list of giant words | Buildings on the map | Puffy tiles with 3D clay icons | `--help` flags / `tree` |
| **CTA** | Solid pill on a glass slab | A giant word or marquee | Isometric keycap at the final station | Candy button that pushes in | Copyable install command / "Press ENTER" |
| **Section transition** | Backdrop hue drift (no cuts) | Colour inversions and hard cuts | Camera pans to the next district | Blob morph / mascot hop | `clear`, scanline wipe, glitch frame |
| **Must never become** | Static gradient plus grey cards | Passive big type with fade-ups | An iso hero image over a normal page | Neumorphism / linear-motion 3D | Monospace skin on a SaaS template |
