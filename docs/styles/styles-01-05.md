> Style research from Scroll Studio by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. Licensed under the GNU AGPL-3.0 with additional terms (NOTICE.md): credit it with this notice, unchanged, wherever it is used, and don't present it as your own work.

# Scroll Studio style research, part 1: Particles, Liquid morph, Holographic, Neon glow, Wireframe 3D

Purpose: give each style its own UX (what scrolling does, what the pointer does, how content is contained and how sections hand over), not just its own skin. Each brief ends with a "UX signature" that no other style may use.

**One rule for keeping them apart.** Each style owns a different *primitive* and a different *scroll metaphor*. Two styles must not share both.

| Style | Primitive | Scroll metaphor | What the pointer is |
|---|---|---|---|
| Particles | Points (discrete matter) | Assembly/dispersal: the same matter re-forms into each section's subject | A force field |
| Liquid morph | One continuous surface | Metamorphosis: one body changes shape, nothing ever cuts | A finger pushing a viscous surface |
| Holographic | Angle-dependent light on a film | Rotation: scroll changes the viewing angle, and colour and hidden content are functions of angle | The light source / the viewer's eye |
| Neon glow | Emitted light from tubes on a dark wall | Ignition: walk down a night street while signs power on as you arrive | A power switch / a hand near the glass |
| Wireframe 3D | Edges in 3D space | Travel: the camera flies along a path through a world drawn in lines | An inspection probe (highlight, measure, explode) |

General accessibility note for all five. Parallax and scroll-linked motion fall under WCAG 2.3.3 Animation from Interactions. Its sufficient techniques are `prefers-reduced-motion` (C39/SCR40) and a site-wide motion toggle ([W3C Understanding 2.3.3](https://www.w3.org/WAI/WCAG21/Understanding/animation-from-interactions)). Any flicker must also pass WCAG 2.3.1 Three Flashes, which is Level A ([W3C](https://www.w3.org/WAI/WCAG21/Understanding/three-flashes-or-below-threshold)). Every style below defines a reduced-motion version that stays recognisably that style.

---

## 1. Particles

### 1.1 Origin and defining aesthetic
Particle systems come from film VFX and generative art: Reeves' 1983 "particle systems" paper for *Star Trek II*, then Processing/openFrameworks, then the WebGL era. On the web the canonical arc runs as follows:
- **2014–2016:** particles.js "plexus" backgrounds, which are now a cliché.
- **2019:** GPU-driven interactive particles, such as Codrops' [Interactive Particles with Three.js](https://tympanus.net/codrops/2019/01/17/interactive-particles-with-three-js/) by Bruno Imbrizi, which reacts to mouse and touch through an off-screen texture.
- **Today:** GPGPU particle sims with curl noise and bloom ([Codrops: Crafting a Dreamy Particle Effect with Three.js and GPGPU](https://tympanus.net/codrops/2024/12/19/crafting-a-dreamy-particle-effect-with-three-js-and-gpgpu/), Dec 2024). Each pixel of a float texture holds one particle's position, which lets the page drive tens of thousands of particles.

Notable sites:
- **[igloo.inc](https://www.igloo.inc)** ([Awwwards case study](https://www.awwwards.com/igloo-inc-case-study.html)). Scroll loops endlessly through igloo, ice blocks, portal, particles and back to the igloo ([CCRMA review](https://ccrma.stanford.edu/~devig17/256A/rr3)).
- **[Kin (kin.movie)](https://kin.movie/)** by Oblio. Interactive particle illustration in three.js ([Awwwards element](https://www.awwwards.com/inspiration/particles-interactive-illustration)).
- **DNA Capital.** Its particle-morph animation was reverse-engineered by Codrops ([Replicating the Particles Animation from DNA Capital](https://tympanus.net/codrops/2021/10/18/replicating-the-particles-animation-from-dna-capital-with-three-js/)).

Visual signatures:
1. **Matter, not shapes.** Every object is a cloud of thousands of points, and the outline is only implied by density.
2. **Assembly and dispersal.** Forms condense from noise and dissolve back into it. The in-between state is the beauty.
3. **Additive light.** Overlapping points brighten (additive blending), so dense regions glow and edges stay soft.
4. **Organic drift.** Curl noise or flow fields keep "resting" particles alive, breathing rather than static.
5. **Depth through size and alpha.** Points attenuate with distance, giving parallax depth without geometry.
6. **Sparse type in a big void.** Content sits at the margins so the cloud has room.

### 1.2 Layout and information architecture
- **Canvas-first.** A single fixed full-viewport WebGL canvas sits behind or under the HTML. The page is a sequence of **states of one particle system**, not a stack of boxes.
- **No visible grid or containers.** Sections are separated by **formation changes** (cloud becomes a word, the word becomes a product silhouette), not by background colour bands or rules.
- **Text placement.** Text lives in a narrow column or anchored to a corner (bottom-left or right third), leaving the centre to the formation. Each pinned "scene" has one headline, one or two lines of body and, optionally, a micro-label.
- **Low density.** One idea per viewport. Long content (FAQ, specs) goes in a calmer appendix area where particles thin out to a faint dust field.
- **Grouping is spatial clustering.** Related items are clusters (constellations) in the same cloud, not cards in a row.

### 1.3 Signature interactions and scroll behaviour
- **The scroll feel.** The page feels like the same handful of sand re-forming. **Particle count is conserved across the whole page**, the same N points throughout. Scroll progress scrubs a `uProgress` uniform that interpolates each particle from formation A to formation B with a **per-particle stagger** (random or noise-based delay). The morph reads as a swarm migrating, not a crossfade. The DNA Capital replication and the Peerlist demo that morphs 12k particles between a sphere and text are the reference patterns ([Peerlist](https://peerlist.io/aryanamitarya/project/particle-text-morphing)). Productised versions include Framer's [Particle Morph 3D](https://www.framer.com/marketplace/components/particle-morph-3d), which goes from wave to scroll-driven 3D shape, and [Galaxy Text Morph](https://www.framer.com/marketplace/components/galaxy-text-morph/), which assembles particles into a headline.
- **Section transitions.** Use three phases per handover: **disperse → travel → condense**. At mid-transition the swarm passes through an "explosion" or vortex. That moment is the style's beat, so give it scroll room (pin roughly 100–150vh per morph).
- **Headline arrival.** The headline is sampled into points (canvas `fillText` → `getImageData`; see [Codrops 3D Typing Effects](https://tympanus.net/codrops/2022/11/08/3d-typing-effects-with-three-js/)). Particles fly in from the previous formation and lock into letterforms. The crisp HTML headline then fades in over the cloud once it settles, and the cloud relaxes into a soft halo.
- **Pointer.** The pointer is a **force field**: repulsion (a "hand through sand" wake), swirl, or attraction. Particles spring back over about 0.6–1.2 s. On touch, a tap sends a shockwave ring.
- **Stats.** Use **data-as-matter**. Either the digits themselves are particle formations that condense as the count-up runs, or the quantity is literal: "1 dot = 1,000 users", with the cloud splitting into proportional sub-clusters (a pie chart made of sand). The counted number appears in HTML beside it.
- **Feature list.** A **constellation**. The cloud splits into N clusters, one per feature, each loosely shaped as an icon. Hovering or focusing a feature label pulls its cluster tighter and brighter while the others go diffuse. Scroll-driven, each feature gets a turn as the "condensed" one.
- **CTA.** The CTA is a gravity well. As it enters, ambient particles orbit it. On hover it "inhales" nearby particles; on click they burst outward. It is the only element where particles visibly touch HTML UI.
- **Ending.** The swarm collapses into the logo mark, then ambient drift.

### 1.4 Component treatments
- **Nav.** Minimal: a wordmark and three or four text links, transparent. The active section is a small dot cluster under the link, a particle "cursor" that migrates between links.
- **Buttons.** A thin outline or a text-only button, plus a dot-matrix fill on hover (points sweep in). No heavy fills; they would compete with the cloud.
- **Cards/features.** No boxes. Each is a label, one line and an associated cluster. If cards are unavoidable, use borderless panels with a faint dust texture.
- **Stats.** A large thin numeral plus a particle formation of the digit or proportion.
- **Timeline/steps.** Particles stream along a path. Each step is a node where the stream pools, and scroll moves the "current" along the stream.
- **Quote/testimonial.** The avatar is reconstructed from particles (sampled from the photo's luminance) and resolves into the photo when in view.
- **FAQ.** A calm zone. Plain accordions over a faint, slow dust field; opening an item emits a tiny puff.
- **Footer.** Particles settle like sediment at the bottom. The logo is a formation, and links are plain text.
- **Images/media.** Images enter as point clouds sampled from their pixels (colour preserved), then cross-resolve to the real `<img>`. 3D products use `MeshSurfaceSampler` point clouds.

### 1.5 Typography and colour
- **Fonts.** Light, airy grotesques that do not fight the cloud: **Inter Tight** (200–300 display, 400 body), **Sora** (200/300), **Manrope** (300/500), plus **IBM Plex Mono** or **JetBrains Mono** at 11–12px uppercase with +0.08em tracking for micro-labels and counters. Display in sentence case, large (clamp 48–120px), tight tracking (-0.02em). Avoid heavy weights; they read as "blocks" next to soft matter.
- **Palettes.**
  - *Deep field:* bg `#05060A`, particle core `#E8ECFF`, warm accent `#FFB38A`, cool accent `#7AA2FF`, text `#F2F4FA`, muted `#8A90A6`.
  - *Ink on paper* (the less clichéd choice): bg `#F3F1EC`, particles `#141414` (normal blending, not additive), accent `#FF4D2E`, muted `#9A968E`.
  - *Bioluminescent:* bg `#020B0D`, particles `#5CFFE1` → `#1E7BFF` by depth, accent `#F7FF7A`.

### 1.6 Implementation
- **Sampling targets.** Text from canvas `getImageData`; SVG via `path.getPointAtLength`; meshes via three.js `MeshSurfaceSampler`; images by luminance-weighted sampling. Store each formation as a vertex attribute (`aPosA`, `aPosB`…) or as a row in a DataTexture.
- **Morph.** In the vertex shader, `mix(aPosA, aPosB, smoothstep(d, d+w, uProgress))` with a per-particle delay `d`, plus a curl-noise offset scaled by `sin(PI * t)` so the mid-transition is turbulent.
- **Simulation.** GPGPU (`GPUComputationRenderer`) handles force fields and curl noise (as in the Codrops dreamy-particles tutorial). Bloom is optional via postprocessing.
- **Scroll binding.** GSAP ScrollTrigger (pinned, `scrub: 0.5–1`) with Lenis for smoothness. Codrops' [cinematic 3D scroll with GSAP](https://tympanus.net/codrops/2025/11/19/how-to-build-cinematic-3d-scroll-experiences-with-gsap/) pairs scroll-linked scenes with reactive particles.
- **Performance.**
  - Tier particle counts: about 8–15k mobile, 30–60k desktop, 100k+ only with GPGPU on capable GPUs ([svilenkovic on GPU vs CPU particles](https://svilenkovic.com/3d/particle-effects-website)).
  - Cap DPR at 1.5–2. Pause the render loop when the canvas is off-screen or the tab is hidden.
  - Additive blending is cheap, but overdraw is not: keep point sizes small.
- **Accessibility.**
  - Particle text is decorative (`aria-hidden`). Real headings live in the DOM.
  - With reduced motion, render each formation **already assembled and static**, with no drift, and switch sections by a short opacity crossfade. It still reads as "made of dots".
  - Text over the cloud needs a scrim or a guaranteed-empty region for 4.5:1 contrast.

### 1.7 Anti-patterns
- The particles.js plexus network (dots joined by lines) floating behind a normal SaaS page. It means nothing and dates the site to 2015.
- A starfield or snow drift that never forms anything. Particles must carry content (words, products, numbers).
- New particles spawned per section with a crossfade. That breaks "conservation of matter", which is the whole idea.
- Pointer effects so strong the formation is never readable.
- **Overlap risks.** Particles feels the same as Liquid if the points blur into a goo (keep them discrete and visible). It feels the same as Wireframe if you connect points with lines (no edges, ever). It feels the same as Holographic if you add spectral colour cycling.

### 1.8 UX signature
**"The page is made of one handful of living sand."** From the first frame to the footer, the visitor watches the *same* swarm of points condense into each section's subject (the headline, the product, the number, the logo), then dissolve and migrate to become the next one. Scrolling is the force that re-forms matter, and the pointer is a hand that can disturb it. Nothing ever cuts or fades between sections. Everything is *reassembled*, and the moment of greatest beauty is the turbulent in-between.

**Engine notes.** Scroll model: pinned scenes with a scrubbed morph. Transition primitive: per-particle staggered interpolation through a turbulence peak. Required data: a "formation source" per section (text, SVG, image or model).

---

## 2. Liquid morph

### 2.1 Origin and defining aesthetic
Three converging lineages:
1. **Gooey/metaballs.** Blinn's 1982 "blobby objects"; on the web, Lucas Bebber's SVG gooey filter, which blurs shapes together and then boosts alpha contrast with `feColorMatrix` ([CSS-Tricks: The Gooey Effect](https://css-tricks.com/gooey-effect/); [Codrops: Creative Gooey Effects](https://tympanus.net/codrops/2015/03/10/creative-gooey-effects/)).
2. **SVG path morphing.** Codrops' [Morphing Page Transition](https://tympanus.net/codrops/2017/08/08/morphing-page-transition), [Dynamic Shape Overlays](https://tympanus.net/codrops/2017/10/17/dynamic-shape-overlays-with-svg/) (layered paths flowing into a full-screen shape with a gooey motion) and [On-Scroll Morphing Background Shapes](https://tympanus.net/codrops/2017/05/23/on-scroll-morphing-background-shapes/).
3. **WebGL liquid.**
   - Displacement transitions ([Codrops LiquidDistortion](https://github.com/codrops/LiquidDistortion/)).
   - Raymarched SDF metaballs ([Codrops droplet metaballs](https://tympanus.net/codrops/?p=94983); [liquid raymarching with TSL](https://tympanus.net/codrops/?p=78977)).
   - Noise-displaced blobs, epitomised by 14islands' [Blobmixer](https://www.14islands.com/work/blobmixer) (React Three Fiber, more than 4M views).
   - Stripe's animated mesh gradient (re-implemented as [whatamesh](https://whatamesh.vercel.app/)).
   - Awwwards elements such as Victor Sin's fluid scroll project transition and Dan Paris' morphing About page ([Awwwards](https://www.awwwards.com/inspiration/morphing-effects-in-about-page-dan-paris)).

Visual signatures:
1. **No hard corners and no cuts.** Everything is curved, and every change is continuous.
2. **Merge and split.** Shapes fuse when close and pinch apart with a neck (surface tension).
3. **Viscosity and inertia.** Motion overshoots and settles (springs). Fast scrolling stretches things, and stopping lets them wobble back.
4. **One protagonist shape.** A hero blob or form whose silhouette changes meaning per section.
5. **Glossy or chromatic material.** Mercury/chrome, soap-film, or saturated gradient flesh with soft specular highlights.
6. **Displacement of imagery.** Photos ripple and smear in transitions as if seen through water.

### 2.2 Layout and information architecture
- **Organic, asymmetric flow.** Content blocks are offset left and right and follow the protagonist shape's position, like text wrapping around a stone in a stream (CSS `shape-outside` can literally wrap text around the blob).
- **Sections are not stacked bands.** They are **regions of one continuous fluid**. The boundary between sections is a **moving liquid surface** (a meniscus) that the visitor pushes through, never a straight edge or a repeated static wave divider.
- **Content lives in soft containers.** Pill and capsule shapes with large radii (24–48px) or fully blob-shaped masks. Containers can bulge when the pointer approaches.
- **Medium density.** Two or three content groups per viewport, generous negative space for the form to move through.
- **Grouping by fusion.** Related items are drawn as droplets joined by gooey bridges, and unrelated items float apart.

### 2.3 Signature interactions and scroll behaviour
- **The scroll feel.** Scrolling feels **viscous and continuous**, like moving through honey. Scroll position drives the protagonist's morph target: the hero blob becomes an abstract version of each section's idea (a droplet for "simple", a split pair for "integrations", a ring for "loop"). **Scroll velocity** feeds a deformation uniform: flinging the page stretches the blob along the scroll axis and makes it ripple, and stopping lets it settle with a damped spring. This velocity-to-deformation coupling is the style's tactile signature.
- **Section transitions.** A **liquid wipe**. The next section's colour rises as a fluid surface with a bulging, wobbling edge (Codrops Dynamic Shape Overlays style, layered paths with staggered easing), or the blob grows to fill the viewport and *becomes* the next section's background. Images cross via displacement maps (LiquidDistortion).
- **Headline arrival.** Variable-font morphing. The headline rises with its weight or softness axis animating from thin and "molten" to settled (e.g. Fraunces `SOFT` 100→0, `wght` 300→700), or letters drip into place with a gooey filter that relaxes to crisp. The rule: **letters may melt in, but must end crisp**.
- **Pointer.**
  - The cursor is a droplet that **merges with interactive elements** (the gooey cursor idea; see [Codrops Gooey Cursor](https://tympanus.net/codrops/?p=72438)).
  - Buttons are magnetic and deform toward the cursor.
  - Images bulge under the pointer (displacement lens).
- **Stats.** A **cell division** reveal. A single droplet holding the headline number splits into three or four droplets, each carrying a stat. The numbers count up while the droplets separate and settle, so the stats are "born from" one fact.
- **Feature list.** **Fusion carousel.** Features are droplets on a horizontal stream. Scroll moves them past a focal well, where the focused droplet swells, absorbs its label and expands into a detail panel; the previous one pinches off and shrinks. Alternatively: a parent blob splits into N child blobs, one per feature.
- **CTA.** A liquid button. On hover a fill rises inside it as liquid (a sloshing surface line), and the button surface wobbles. On press it squashes (scale 0.96 with an elastic return). The final CTA section has the protagonist blob pool around the button.
- **Ending.** The fluid drains or pools into the footer.

### 2.4 Component treatments
- **Nav.** A floating capsule. The active indicator is a gooey pill that **stretches** from the old item to the new one (leading edge first, trailing edge catches up) rather than sliding rigidly.
- **Buttons.** Fully rounded. Liquid-fill hover, magnetic pull, elastic press.
- **Cards/features.** Soft blobs or squircles. On hover the border radius morphs (eight-value `border-radius` blob trick) and neighbours repel slightly.
- **Stats.** Numbers inside droplets that split from a parent drop.
- **Timeline/steps.** A flowing stream (an SVG path) with droplets travelling along it. Each step is where a droplet detaches and lands.
- **Quote/testimonial.** The quote inside a speech blob whose outline slowly breathes; the avatar sits in a blob mask.
- **FAQ.** The accordion opens with a liquid stretch: the panel height springs with overshoot and the separator line bends like a membrane.
- **Footer.** A pool. The top edge is a gently animated meniscus, and the content sits "underwater" (slightly deeper tone).
- **Images/media.** Blob-shaped masks that morph on scroll, plus displacement-map transitions between images (ripple, smear).

### 2.5 Typography and colour
- **Fonts.** Soft, variable, plastic:
  - **Fraunces** (variable `SOFT`, `WONK`, `opsz`, `wght`) for display, 300–800.
  - **Recursive** (`CASL` axis for "melting" into casual).
  - **Bricolage Grotesque** (variable width/weight).
  - **DM Sans** or **Manrope** for body (400/500).
  - Sentence case with rounded feel; display tracking -0.03em; body normal.
  - Animate **axes, not just opacity**.
- **Palettes.**
  - *Mercury:* bg `#0E0F12`, chrome gradient `#F5F7FA → #9AA3B2 → #3B4252`, accent `#7CFFCB`.
  - *Candy fluid:* bg `#FFF4EC`, blobs `#FF6B9A`, `#FFB86B`, `#8B7BFF`, text `#1B1530`.
  - *Deep sea:* bg `#03121F`, blob gradient `#0FD3C9 → #2B59FF`, highlight `#E9FFFB`.
  - Gradients must be **smooth and wet**. Use mesh gradients, not stepped stops.

### 2.6 Implementation
- **SVG path morph.**
  - GSAP MorphSVG (free since GSAP 3.13) or flubber for mismatched point counts (flubber is about 53 KB; tune `maxSegmentLength`) ([Motion.dev SVG morphing](https://motion.dev/tutorials/js-svg-path-morphing); [Popmotion morph-svg](https://popmotion.io/learn/morph-svg/)).
  - Bind to a ScrollTrigger scrub, or feed scroll progress into the flubber interpolator.
  - CSS `d: path()` transitions work in Chromium and Firefox when point counts match.
- **Gooey merge.** SVG filter `feGaussianBlur stdDeviation≈10` → `feColorMatrix values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 18 -7"` → `feComposite` to keep content crisp. It is CPU-heavy, so apply it only to small layers ([freefrontend gooey examples warn of this](https://freefrontend.com/javascript-gooey/)).
- **WebGL blob.** Icosphere with vertex displacement by 3D simplex noise (Blobmixer approach). Morph between section targets by lerping noise frequency/amplitude plus a target SDF, and use `MeshPhysicalMaterial` (clearcoat, iridescence or transmission) for gloss.
- **Metaballs.** A raymarched fullscreen quad with `smin` smooth union (Codrops tutorials above), or 2D metaballs in a fragment shader (cheaper).
- **Image transitions.** Displacement-map shader (LiquidDistortion, or curtains.js/OGL). Velocity-driven RGB shift/stretch from Lenis velocity.
- **Springs.** Use spring physics (Motion, react-spring, or a hand-rolled critically damped spring) instead of fixed-duration easing. Viscosity comes from damping.
- **Performance and accessibility.**
  - SVG filters re-rasterise every frame, so keep filtered areas small.
  - Raymarching costs per pixel, so render at 0.5–0.75 resolution and upscale.
  - Never apply velocity distortion to body text.
  - With reduced motion: blobs become static, morphs become 200 ms crossfades between the end shapes, no velocity deformation, no wobble. The shapes still say "liquid" and only the motion is removed.

### 2.7 Anti-patterns
- The 2019 SaaS "decorative blob" behind a stock illustration, and the identical SVG **wave divider** between every section. These are static and meaningless.
- A lava-lamp background that loops on its own regardless of scroll (it must respond to the visitor).
- Gooey filters on text that leave it permanently blurred.
- Every element jiggling. Reserve wobble for the protagonist and interactive elements.
- Confusing Liquid morph with Apple's 2025 "Liquid Glass". That is a refraction/translucency material language (it belongs nearer Glassmorphism), not shape metamorphosis.
- **Overlap risks.** Liquid feels the same as Particles if the blob is made of dots. It feels the same as Holographic if the material becomes an iridescent rainbow film with tilt (keep the emphasis on *shape change*, not angle-dependent colour).

### 2.8 UX signature
**"Nothing cuts; everything becomes."** The visitor scrolls one continuous, viscous body. A single protagonist form morphs to embody each section's idea, splits to present stats and features, and floods the screen to become the next section. Section boundaries are moving liquid surfaces you push through. The page **responds to scroll *speed***: fling it and the world stretches and wobbles; stop and it settles with surface tension. The feeling is tactile physics. Content is born by division and joined by fusion.

**Engine notes.** Scroll model: continuous scroll (few pins) with velocity-coupled deformation. Transition primitive: shape interpolation plus liquid wipe. Required data: a per-section "silhouette idea" (an SVG or parametric blob target).

---

## 3. Holographic

### 3.1 Origin and defining aesthetic
Two lineages that this style should deliberately fuse into one idea: **colour and content depend on viewing angle**.
1. **Physical holograms and iridescent foil.** Gabor invented holography in 1947. Then came security holograms on credit cards and banknotes, holographic stickers and packaging, CD diffraction, and Pokémon holofoil cards. The Y2K revival brought "glossy holographic gradients, watery iridescent colors, and shiny silvers" ([AIGA Eye on Design](https://eyeondesign.aiga.org/the-y2k-aesthetic-is-fully-back-but-can-it-stick-around/)). daisyUI's trend guide lists the signatures as iridescent gradients, spectral shifts, pearlescent surfaces and diffraction highlights, tied to pointer angle, scroll or rotation, with "slow shimmer passes rather than constant random hue cycling" ([daisyUI Holographic/Iridescent](https://trends.daisyui.com/trend/holographic-iridescent-ui/)). The definitive web reference is Simon Goellner's [poke-holo](https://poke-holo.simey.me) ([GitHub](https://github.com/simeydotme/pokemon-cards-css)): CSS transforms, gradients, blend modes and filters that recreate Sword & Shield era holofoils, where tilt changes how light hits the card.
2. **Projected sci-fi holograms.** From Princess Leia's 1977 projection to *Minority Report* and *Iron Man*, and Territory Studio's film UIs (*Blade Runner 2049*: initial, action and loop states per screen; [HUDs+GUIs](https://www.hudsandguis.com/home/2018/blade-runner-2049); [Design Museum Q&A](https://designmuseum.org/exhibitions/past-exhibitions/beazley-designs-of-the-year-2018/qa-with-david-sheldon-hicks-founder-of-territory-studio)). The rendering vocabulary is Fresnel rim light, scanlines, glitch and translucency ([Three.js Journey: Hologram shader](https://threejs-journey.com/lessons/hologram-shader); [ektogamat holographic material](https://github.com/ektogamat/threejs-holographic-material), which exposes Fresnel amount, scanline size, signal speed and blinking).

Visual signatures:
1. **Spectral sheen that moves with angle.** A rainbow band sweeps as the object or viewer turns. It is never a static rainbow gradient.
2. **Pearlescent base.** Silver, pearl or charcoal grounds with soft cyan-violet-rose-lime highlights.
3. **Translucency and depth.** Stacked semi-transparent planes; you can see "into" the object.
4. **Fresnel rims.** Edges glow brighter than faces (the projected hologram look).
5. **Diffraction patterns and latent images.** Foil textures (sparkle, linear, cosmos, starburst) and hidden marks that appear only at certain angles (security-hologram latent images).
6. **Projection artefacts, used sparingly.** Horizontal scanlines, a scan-in line, slight chromatic aberration.

### 3.2 Layout and information architecture
- **Objects on pedestals.** Each section presents **one holographic object or plate** (a product, card, badge or data volume), centred or slightly offset, with dark breathing space around it (daisyUI: isolate foil in hero objects, badges, dividers and selected controls; low-to-moderate density).
- **Depth-layered plates, not a flat grid.** Content groups are **translucent plates stacked in z** (like a holographic display volume). Supporting copy sits on a neutral matte area beside the object, never on the foil.
- **Collectible grids.** For lists (features, team, integrations), a grid of trading-card plates, each tiltable individually. This is the one place a grid appears, and it feels like a binder of collectibles.
- **Sections separated by "projection planes".** A thin luminous horizontal line (the projector beam) scans to wipe in the next section.
- **Moderate density.** Copy is short. The object carries the attention.

### 3.3 Signature interactions and scroll behaviour
- **The scroll feel.** Scrolling **rotates the viewing angle**. Each section's object or plate tilts through an arc (for example -25° to +25° on Y) as it travels through the viewport. The spectral band sweeps across its surface, and the colour of everything is a function of scroll position. The visitor feels they are walking past a holographic exhibit and watching light play across it.
- **Latent reveal.** Each plate hides a second layer (a key number, a micro-message, the product's inner structure) that becomes visible **only within a narrow band of angles**, at mid-scroll of the section. This mirrors real security holograms and is the style's core content mechanic: *the information is in the angle*.
- **Pointer and device.** The pointer is the light source and eye. Moving it tilts the hovered plate (poke-holo style: rotate, glare position, and foil `background-position` all mapped to pointer x/y). On mobile, use `DeviceOrientationEvent` for gyroscope tilt (iOS needs a permission tap, offered as an opt-in "tilt to explore" control), with scroll-driven tilt as the fallback.
- **Section transitions.** A **projection scan**. A bright horizontal line sweeps down, and the next section's hologram materialises behind it (low opacity, scanlines and a slight vertical jitter for about 300 ms, then stabilising to clean). The outgoing hologram de-resolves the same way. This is a materialisation event, distinct from neon's ignition flicker: it is *spatial* (a line sweep), not temporal stuttering of a light source.
- **Headline arrival.** The headline appears in matte type, then a **single slow foil sheen pass** sweeps across it (a one-shot gradient sweep, about 1.2 s). Large display words can carry a permanent subtle foil fill that shifts with scroll, but only at 64px and larger.
- **Stats.** **Volumetric projection.** Each number rises from a small "emitter" base as a translucent extruded numeral with a Fresnel rim, and the count-up happens during the materialise scan. Alternatively, stats are latent: the plate looks blank head-on and the number appears as you scroll past the right angle.
- **Feature list.** A **binder of holo cards**. Features are trading cards in a grid. Scrolling the grid applies a staggered wave of tilt (each card catches the light in sequence like a Mexican wave of shimmer). Hover or focus lifts one card, which enlarges on click (poke-holo behaviour) to show the feature detail on its back (a 3D flip).
- **CTA.** A **foil-stamped seal**. The CTA button is the rarest card, permanently iridescent with a sparkle foil, the only element with continuous (slow) sheen. On hover the sheen follows the pointer and the glare intensifies.

### 3.4 Component treatments
- **Nav.** A translucent pearl capsule (frosted, 1px pearl border). The active item has a tiny holographic underline whose hue tracks scroll position.
- **Buttons.** Primary is foil (layered conic gradient plus noise, `mix-blend-mode: color-dodge`), with sheen on hover. Secondary is matte with a pearl border.
- **Cards/features.** Trading-card plates: tilt, glare and foil pattern, with the back face carrying detail. Different foil patterns (linear, sparkle, cosmos) can distinguish categories.
- **Stats.** Projected volumetric numerals, or latent numbers revealed by angle.
- **Timeline/steps.** Stacked translucent layers in z. Scroll moves the camera *through* the stack (each step is a pane you pass through, like slices of a hologram volume).
- **Quote/testimonial.** Presented as a **certificate with a security hologram seal**: the reviewer's mark or logo in a small foil badge with a latent image.
- **FAQ.** Matte, readable list. The open item gets a thin spectral edge on its left side, and that is all.
- **Footer.** A security strip: a band of diffraction pattern with microtext (brand name repeated) and a hologram badge, like a banknote's foil strip.
- **Images/media.** Product shots get a holographic overlay layer (foil mask) on edges and highlights only. 3D models use a thin-film iridescence material (`MeshPhysicalMaterial.iridescence`) or a Fresnel-scanline hologram shader.

### 3.5 Typography and colour
- **Fonts.** Wide, futuristic display paired with a neutral body. daisyUI suggests **Syncopate, Michroma, Oxanium, Space Grotesk, Zen Dots**. Recommended:
  - **Syncopate 700** or **Michroma 400**, uppercase, +0.12em to +0.2em tracking, for short display lines.
  - **Space Grotesk 400/500** for subheads.
  - **Inter** or **Manrope** 400 for body.
  - **Space Mono** for latent micro-text and serials.
  - Foil fills only on large letterforms.
- **Palettes.**
  - *Pearl (light):* base `#F4F3F8`, surface `#E9E7F0`, text `#16151C`; spectral stops `#7DF9FF`, `#A88BFF`, `#FF9DE2`, `#FFE29A`, `#B8FFB0`.
  - *Obsidian (dark):* base `#0B0B12`, plate `#15151F` at 60% alpha, text `#F0EEF8`, muted `#9C99AE`; same spectral stops at lower saturation; Fresnel rim `#9FF3FF`.
  - Grounding: charcoal, white or soft grey fields with cyan-violet primaries (daisyUI).

### 3.6 Implementation
- **CSS foil** (cheap, accessible):
  - Layered `linear-`, `radial-` and `conic-gradient`s, an SVG `feTurbulence` noise layer, and `mix-blend-mode: color-dodge | overlay | soft-light`, with `filter: brightness() contrast()`.
  - Pointer or scroll maps to CSS custom properties (`--mx`, `--my`, `--angle`) through rAF ([OpenReplay: holographic CSS](https://blog.openreplay.com/creating-holographic-effects-css/), which recommends OKLCH for smoother spectral interpolation; [21st.dev Iridescent Foil](https://21st.dev/@dqnamo/components/iridescent-foil)).
  - Use `@property` to animate gradient angles.
  - Scroll-driven tilt can use CSS `animation-timeline: view()`.
- **WebGL.**
  - Thin-film approximation: hue = f(thickness × cos θ) using `dot(normal, viewDir)`, plus procedural flakes ([Foil sticker shaders tutorial](https://feedbagel.com/post/creating-foil-sticker-effects-with-custom-threejs-shaders)).
  - three.js `MeshPhysicalMaterial` with `iridescence`, `iridescenceIOR` and `iridescenceThicknessRange` gives physically based thin-film for free.
  - Projected hologram: Fresnel plus `fract(worldPos.y * N - time)` scanlines and a vertex glitch, with additive blending and `depthWrite: false`.
- **Performance.**
  - `mix-blend-mode` plus large gradients on many cards is costly. Only animate the hovered/visible cards, and use `will-change: transform` on the tilting element only.
  - Use one WebGL hero object, not many.
- **Accessibility.**
  - Never put body text on iridescent fills. Contrast must be checked against the *worst* angle (spectral highlights can wash out text).
  - With reduced motion: plates rest at a fixed flattering angle, no scroll tilt, no glitch or scan jitter (the scan becomes a fade), and latent content is shown directly. Gyroscope stays opt-in only.

### 3.7 Anti-patterns
- A static rainbow gradient (the "unicorn" or vaporwave pastel wash). Holographic without angle-dependence is just a gradient.
- Constant random hue cycling on everything (daisyUI explicitly warns against it).
- Foil on every component, which kills rarity and hierarchy.
- Overusing the cyan Iron Man HUD (blue lines, rotating rings, fake data). That collapses into "Sci-fi HUD/Wireframe".
- Heavy glitch, which reads as "Glitch" style.
- **Overlap risks.** Holographic feels the same as Neon if it becomes cyan or magenta emissive lines on black (holographic is *reflected/diffracted spectral light on surfaces*; neon is *emitted fixed-colour light from tubes*). It feels the same as Liquid if the foil object melts and morphs (holographic objects are rigid plates that *rotate*).

### 3.8 UX signature
**"The information is in the angle."** Every object is a rigid holographic plate or projection, and **scrolling turns it**. As the visitor moves, spectral light sweeps across surfaces, and hidden latent content (a number, a mark, a message) flashes into view only at the right angle, then fades as the angle passes. The visitor is the light source: pointer or phone tilt lets them play the light across collectible cards. New sections *materialise* behind a projector scan line. The experience is like inspecting a precious, security-printed object, rotating it to find what is hidden in it.

**Engine notes.** Scroll model: per-section scroll-to-rotation mapping (`view()` timelines). Transition primitive: projection scan. Required data: per-section latent content plus foil pattern choice.

---

## 4. Neon glow

### 4.1 Origin and defining aesthetic
Neon signage was introduced commercially by Georges Claude in Paris in 1910 (true neon gas glows red-orange; blues come from argon/mercury, and other colours from phosphor-coated tubes). Its image runs through Las Vegas and Times Square, Tokyo's Kabukichō and Hong Kong, and then cinema: *Blade Runner* (1982), *Tron*, *Drive* (2011). The 2000s–2010s synthwave/outrun revival brought the "neon horizon, magenta-cyan palette… night-drive glow" ([Wikipedia: Synthwave](https://en.wikipedia.org/wiki/Synthwave); [daisyUI Synthwave/Outrun](https://trends.daisyui.com/trend/synthwave-outrun/)). On the web, the CSS vocabulary is stacked `text-shadow`: white tight-blur cores plus wide coloured halos, with a flicker that drops the glow at irregular keyframes ([CSS-Tricks: How to Create Neon Text With CSS, Silvia O'Dwyer](https://css-tricks.com/how-to-create-neon-text-with-css/)). That article also notes that flickering *one* part of a sign looks more real than the whole sign.

Visual signatures (anchored in *real signage* to avoid the generic synthwave look):
1. **Tubes, not text.** Monoline letterforms with rounded terminals and continuous strokes. Where tubes jump between letters, the joins are painted out ("blockout"). Visible **unlit tube glass** (dim grey) when off.
2. **Light spill.** Glow falls onto the wall behind (a soft coloured wash), and onto wet pavement or glass below (reflections).
3. **Ignition and flicker.** Tubes start with a stutter, then hum steadily. One old tube buzzes.
4. **A dark, textured surface.** Brick, concrete, black painted wall, or a rainy window. The surface is what makes the light read.
5. **Mounting hardware.** Brackets, raceways, cables and transformer boxes: the material reality of a sign.
6. **A limited palette per sign.** One or two tube colours per sign. Colour signals the category (a red "OPEN", a blue "BAR").

### 4.2 Layout and information architecture
- **A street at night, scrolled horizontally or vertically.** The page is a sequence of **storefronts and walls**. Each section is a facade or wall area with **one primary sign** (the section headline) plus small **plaques/menus** (body text set plainly on a lit board or in a window).
- **Collage, not grid.** Signs are mounted at varied sizes and positions like a real wall of signs (Kabukichō density in the hero, then calmer single-sign walls). Asymmetric, with overlapping layers (sign in front of window in front of interior).
- **Hierarchy = illumination.** The important thing is the *brightest*, not the biggest. Lit versus unlit is the primary visual structure.
- **Section separation.** By *darkness*: stretches of unlit wall between storefronts, or the street turning a corner. No dividers.
- **Low density.** One sign and a short plaque per screen. Long-form content goes "inside the bar": a warmer interior section, readable and less glowy.

### 4.3 Signature interactions and scroll behaviour
- **The scroll feel.** Walking down a street at night. **Signs power on as they reach you and power down behind you.** Before activation, the tube outline is visible as dim glass (the anticipation). As a section enters (about 30–40% into the viewport), its sign **ignites**: a two- or three-stutter flicker (all under WCAG flash thresholds), then a steady glow, with light spill fading up on the wall. As it leaves, it dims to warm-off and then to unlit glass. Scrolling back re-lights.
- **Section transitions.** A **power handover**. The current sign hums down while the next street's sign stutters on. Ambient light colour (spill on the shared wall or floor) crossfades from one sign colour to the next, so the *room colour* changes with each section. That colour mood shift is a key part of the experience.
- **Headline arrival.** The headline is a sign. Either its tubes **draw on** stroke by stroke (`stroke-dashoffset`, like a tube being filled with gas) and then glow up, or the whole word ignites with one letter lagging and flickering (the "bad tube" detail, only on the hero) ([SVGator neon line tutorial](https://www.svgator.com/tutorials/how-to-create-a-line-animation-with-neon-light-effects); [dev.to flickering neon SVG](https://dev.to/ninjasoards/make-a-flickering-neon-svg-animation-from-scratch-w-illustrator-react-emotion-39gm)).
- **Pointer.**
  - Pointer proximity brightens tubes slightly (as if a hand were near the glass).
  - Hovering a sign-button switches it on fully, with the wall spill expanding.
  - Optionally, the pointer casts a faint coloured light on nearby wall texture (a radial gradient at the cursor tinted by the nearest sign).
- **Stats.** **Price-sign numerals.** Numbers are neon digits (a segmented-tube display, like "24 HR" or motel vacancy signs). The count-up is digits ticking with a tiny flicker per change, or the tubes of each digit lighting segment by segment.
- **Feature list.** A **sign sequencer / marquee chase**. Features are a column or wall of small signs, and as you scroll they switch on one at a time in sequence (the chaser-light rhythm). Only the current feature is fully lit; earlier ones stay at "warm idle" (dimmer) so the wall fills with light as you progress.
- **CTA.** The **"OPEN" sign**. The CTA is the one sign on the page with the classic red-orange (real-neon) colour or the brand's hottest colour. It sits unlit until the final section, then turns on with a satisfying clunk (scale micro-bump, spill bloom). Hovering makes it buzz brighter.

### 4.4 Component treatments
- **Nav.** Small neon wordmark (always lit, low intensity) plus plain text links. The active link gets a thin tube underline that is lit, and the others are unlit glass.
- **Buttons.** Tube outline (rounded rect drawn as a tube with an inset glow on the inner side, as in CSS-Tricks' `inset` box-shadow). Off-state is unlit glass, hover is lit, focus is lit with a visible 2px solid focus ring outside the glow.
- **Cards/features.** Lit window panes or small mounted signs on a wall texture. Card body text sits on a dark matte plaque, not glowing.
- **Stats.** Segmented neon numerals with a tiny "LIVE" or "OPEN 24/7"-style label.
- **Timeline/steps.** A single continuous tube that **draws along a path** as you scroll (`stroke-dashoffset` scrubbed to scroll). Each step is a bend where a small sign hangs and lights when the tube reaches it.
- **Quote/testimonial.** A hand-lettered script neon sign (cursive tube) of a short pull-quote, with the full quote on a plaque below.
- **FAQ.** Questions as small unlit signs. Opening one lights it, and the answer appears on a plaque. Calm, no flicker.
- **Footer.** Closing time. A "CLOSED / SEE YOU TOMORROW" sign, or the wall gradually going dark, with an address-plaque style for links and a single small always-on brand sign.
- **Images/media.** Photos treated as night photography (low key, coloured by the active sign's spill, `mix-blend-mode: screen` for reflections). Video in a "shop window" frame with glass reflections.

### 4.5 Typography and colour
- **Fonts.**
  - Neon-tube display: **Tilt Neon** (Google Fonts, designed as tube lettering), **Monoton** (multi-line retro), **Neonderthaw** (script tube).
  - Script signs: **Yellowtail** or **Mr Dafoe**.
  - Body and plaques: **Barlow** / **Barlow Condensed** (400/600) or **Outfit**, never glowing.
  - Mono for small specs: **DM Mono**.
  - Display mostly lowercase script or uppercase monoline with +0.04em tracking (tube letters need breathing room for glow).
  - Avoid **Orbitron/Audiowide**: they pull toward synthwave and sci-fi HUD.
- **Palettes.**
  - Walls: `#0B0A0E` (black paint), `#16131A` (brick shadow), `#1E1B22` (lifted surface). Plaque text `#E9E4DA`, muted `#8C8594`.
  - *Real neon tubes:* neon red-orange `#FF4E1A`, argon blue `#2F7BFF`, "OPEN" red `#FF2A2A` (avoid in flicker; see the red-flash rule), warm white `#FFE9C7`, mint `#3DFFB4`, hot pink `#FF2A6D`, ice cyan `#05D9E8`, violet `#B14CFF`.
  - Use **max two tube colours per section** and one page-wide hero colour. The tube core is always near-white (`#FFF6F0`), with colour in the halo.

### 4.6 Implementation
- **Glow.**
  - Text: stacked `text-shadow`, e.g. `0 0 2px #fff, 0 0 6px #fff, 0 0 14px C, 0 0 28px C, 0 0 56px C` (CSS-Tricks).
  - Shapes and SVG: duplicated strokes (wide coloured, mid lighter, thin white core) or `filter: drop-shadow()` / SVG `feGaussianBlur` + `feMerge`.
  - Unlit state: a stroke in `rgba(255,255,255,0.08)` plus a subtle inner highlight.
- **Spill.** A large blurred radial-gradient pseudo-element behind each sign in the tube colour with `mix-blend-mode: screen`, animated by opacity only. Reflections come from a vertically flipped, blurred and masked copy (`-webkit-box-reflect` or a duplicate with `transform: scaleY(-1)` and a gradient mask).
- **Ignition.** Do **not** animate `text-shadow`/`box-shadow` values, which is costly (commenters on the CSS-Tricks article report high CPU/GPU). Pre-render the glow on a separate layer and animate **opacity** with stepped keyframes (`steps()` or irregular percentages). Scroll-trigger it with IntersectionObserver or `animation-timeline: view()`.
- **3D option.** A WebGL scene with emissive tube geometry (TubeGeometry along font outlines) plus `UnrealBloomPass`, with wet-floor reflections via `Reflector`. This is premium, not required.
- **Accessibility.**
  - Flicker: no more than three flashes in any one second, small area, and **never flicker saturated red** (WCAG 2.3.1 red flash threshold). Keep flicker on one small element.
  - Glow reduces legibility, so body text is plain, high-contrast, non-glowing.
  - Focus states must be distinct from "lit" (add a solid outline).
  - With reduced motion: signs appear already lit (or lit/unlit with a 150 ms fade), no flicker, no hum. The street metaphor survives through the lit/unlit state change.

### 4.7 Anti-patterns
- Everything glowing, including body text and every border. There is no hierarchy, it causes eye strain, and it reads as "gamer RGB".
- Glow on pure black with no surface, spill or reflection. It looks like a flat sticker, not light.
- Constant flicker on large areas (cheap, nauseating, and a seizure risk).
- The full synthwave kit: magenta-cyan perspective grid, chrome italic Orbitron, sunset. That belongs to a Synthwave/Outrun style and overlaps with Wireframe 3D's grid.
- Six neon colours on one screen.
- **Overlap risks.** Neon feels the same as Holographic if the glow becomes spectral or angle-shifting. It feels the same as Wireframe if signs become glowing 3D outlines in a void (neon is 2D signage on a material surface, about *light and power*, not spatial structure).

### 4.8 UX signature
**"The lights come on as you arrive."** Scrolling is a walk down a night street. Each section is a storefront whose sign sits dark, its unlit glass tubes just visible, until you reach it. Then it stutters to life with a hum and floods the wall and wet ground with its colour. Behind you, signs power down. Emphasis is created by **illumination, not size**, and the mood of the whole page shifts colour with every new sign. The finale is the moment the "OPEN" sign switches on, which is the call to action.

**Engine notes.** Scroll model: continuous scroll with per-section power states (`unlit`, `igniting`, `lit`, `dimming`). Transition primitive: ignition plus ambient spill crossfade. Required data: per-section sign text or SVG plus a tube colour.

---

## 5. Wireframe 3D

### 5.1 Origin and defining aesthetic
Vector displays and early CG: Atari's *Battlezone* (1980), whose "stark green on black, gorgeously defined lines" drew tanks and mountains only in luminous outline ([Retro Gamer via PressReader](https://www.pressreader.com/uk/retro-gamer/20180419/281724090129808)). Its developers say *Tron* (1982) was inspired by it ([Road to VR: Art of Battlezone](https://roadtovr.com/battlezone-psvr-dev-diary-3-the-art-of-battlezone/)). Then *Star Wars*' Death Star briefing, *Elite* (1984), and CAD/engineering drawing (orthographic views, dimension lines, exploded views). As solid polygons replaced empty frames, rendered edges persisted as an aesthetic ([Tron Lines](https://tropedia.fandom.com/wiki/Tron_Lines)).

On the modern web:
- Wireframe-to-solid reveals (Awwwards elements: [3D wireframe, Vaulk](https://www.awwwards.com/inspiration/3d-wireframe-vaulk); [Wireframe Reveal, Poor Charlie's announcement by Devin Jacoviello](https://www.awwwards.com/inspiration/wireframe-reveal-poor-charlies-announcement), tagged wireframe, depth map, mouse interaction; [Page Line Scroll, Behave](https://www.awwwards.com/inspiration/page-line-scroll-behave)).
- Scroll-driven camera fly-throughs ([Codrops: camera fly-through on scroll with Theatre.js + R3F](https://tympanus.net/codrops/?p=70449)).
- Wireframe terrain flyovers ([Framer Infinite Wireframe](https://www.framer.com/marketplace/components/infinite-wireframe/), simplex-noise terrain with top-down to first-person camera).

Visual signatures:
1. **Edges only, or edges first.** Geometry shown as its structural lines; surfaces absent or implied.
2. **Real 3D space and perspective.** Lines converge, rotate and parallax. Depth is cued by line fade or thickness.
3. **Technical annotation.** Dimension lines, leader-line callouts, coordinates, axis gizmos, registration marks.
4. **Hidden-line logic.** Back edges removed or dimmed, giving engineering-drawing clarity.
5. **Wire → solid "render" moment.** Lines fill into shaded surfaces, from blueprint to reality.
6. **Monochrome line colour.** One line colour on a flat ground (vector green, blueprint white-on-blue, or black-on-paper).

### 5.2 Layout and information architecture
- **One navigable world, plus a technical-drawing sheet overlay.** The canvas is a single 3D scene: a world, product or architecture built from lines. The HTML overlay is laid out like a **drawing sheet**:
  - a strict modular grid (visible faint grid lines or dot grid);
  - corner registration marks;
  - a **title block** in a corner (project, scale, revision, sheet n/N), which doubles as section progress;
  - monospace labels.
- **Content anchored to 3D points.** Copy lives in **callouts connected by leader lines to features in the scene** (projected world-to-screen positions each frame), not in floating boxes.
- **Sections = locations or views.** Each section is a camera station: front elevation, side, top, section-cut, exploded, interior. Sections are separated by camera moves, not by page bands.
- **High precision, medium density.** Grids, numbers and labels are everywhere, but light (hairlines and small type), so the world stays primary.
- **Grouping = assemblies.** Related features belong to one sub-assembly of the model and are highlighted together.

### 5.3 Signature interactions and scroll behaviour
- **The scroll feel.** **Camera travel.** Scrolling moves the camera along a spline path (`CatmullRomCurve3`, or Theatre.js-authored keyframes) through the line world. You *fly* from station to station: over terrain, through a building, around and into a product. Smooth, cinematic, continuous, with slight easing into each station so it settles for reading.
- **Section transitions.** Camera moves, *plus* a change of drawing mode: perspective → orthographic snap (a satisfying "CAD view snap" for spec sections), section-cut planes sweeping through the model, or an **exploded view** where parts separate along axes as you scroll.
- **Headline arrival.** The headline is drawn as **stroked outline type** that plots on like a pen plotter (`stroke-dashoffset` per glyph, outline font or `-webkit-text-stroke`). Fill can follow when settled. Meanwhile a construction line extends from the headline to the object it describes.
- **Wire → solid render.** The hero product starts as pure edges and, as you approach it (or at the product section), **solidifies**: faces fill with shaded material, edges fade to subtle. "From design to reality" is the narrative beat. A barycentric-wireframe shader lets the edge-to-surface ratio be a uniform tied to scroll.
- **Pointer.** An **inspection probe**. Hovering a part highlights its edges in the accent colour and pops a callout with its name and dimensions. Dragging orbits slightly within limits, with a spring back to the authored path. Optionally, a crosshair cursor shows live coordinates in the corner HUD.
- **Stats.** **Dimension annotations.** Numbers appear as dimension lines measuring the model ("42 ms ↔", "3.2 kg", "x10 throughput" as a scale bar), with arrowheads extending as the value counts up. Bar comparisons are rendered as wireframe extrusions of different heights.
- **Feature list.** An **exploded view with callouts**. The product separates into components as you scroll. Each component is a feature, with a numbered balloon (①②③, the engineering BOM convention) and a leader line to a short description. A parts list (bill of materials) table at the side tracks which feature is highlighted.
- **CTA.** The **final assembly**. Parts snap back together, the model renders solid, and the camera settles on a hero three-quarter view. The CTA appears in the title block ("APPROVED FOR BUILD") as an outlined button with corner ticks that fill on hover.

### 5.4 Component treatments
- **Nav.** A slim top bar like a CAD toolbar: wordmark, section links as view names (`01 FRONT`, `02 EXPLODED`, `03 SPEC`), and a tiny axis gizmo that rotates with the camera.
- **Buttons.** 1px outline rectangles with corner tick marks (crop-mark corners), mono uppercase labels. Hover fills with a hatch pattern or solid; focus shows a dashed outline.
- **Cards/features.** Orthographic view panels (front/side/top thumbnails of the relevant part) with a label strip. No shadows; hairline borders only.
- **Stats.** Dimension lines with arrowheads and values, or scale bars.
- **Timeline/steps.** Waypoints along the camera path through the world (a line-drawn road/route on terrain). The current step's node is highlighted and the path ahead is dashed (not yet built).
- **Quote/testimonial.** A "revision note" or engineer's annotation: boxed, with a leader to the relevant part, initials and date like a drawing revision table.
- **FAQ.** A **spec sheet** table: questions as rows, answers expanding inline, with a mono row index.
- **Footer.** The **drawing title block**: company, address, "Drawn by / Checked / Scale 1:1 / Sheet 6 of 6", links as table cells, and a revision table holding the changelog link.
- **Images/media.** Photos shown first as an edge-detected line version (Sobel shader or pre-generated SVG trace) that resolves to the photo on hover or in view. 3D models are always line-first.

### 5.5 Typography and colour
- **Fonts.**
  - Technical mono for labels and data: **JetBrains Mono** (300/500), **IBM Plex Mono**, **Space Mono**.
  - Display: **Major Mono Display** (geometric drafting caps) or outlined **Archivo** / **Archivo Expanded** 600 with stroke only.
  - Body: **IBM Plex Sans** 400.
  - Labels UPPERCASE with +0.06–0.1em tracking. Engineering numbering (`A-01`, `REV 3`).
  - **Doto** (dot-matrix) only for HUD readouts.
- **Palettes.** Choose one per site:
  - *Blueprint:* bg `#0B3D91`, grid `#2A5DB0`, lines `#E8F1FF`, accent `#FFD23F`.
  - *Vector CRT:* bg `#030603`, lines `#39FF14` with depth fade to `#0E4D0A`, accent `#FFFFFF` (Battlezone homage; use sparingly).
  - *Drafting paper* (most premium, least clichéd): bg `#F2F0E9`, grid `#DAD6CB`, lines `#111111`, hidden lines `#11111140` dashed, accent `#FF4F00` for highlights/dimensions.
  - *Night CAD:* bg `#0A0A0B`, lines `#D9DDE3`, construction lines `#3A3F47`, accent `#4DA3FF`.

### 5.6 Implementation
- **Edges.**
  - three.js `EdgesGeometry(geom, thresholdAngle)` draws only meaningful creases (clean, CAD-like), versus `WireframeGeometry` (every triangle, noisy; avoid).
  - WebGL `linewidth` is 1px on most platforms, Windows/ANGLE especially, so use `LineSegments2` + `LineMaterial` (fat lines; set `resolution`; `worldUnits` optional) via `LineSegmentsGeometry.fromEdgesGeometry` ([three.js fat-lines notes](https://threepipe.org/notes/gltf-mesh-lines); [pythreejs thick lines on the ANGLE limitation](https://pythreejs.readthedocs.io/en/stable/examples/ThickLines.html); example `webgl_lines_fat_wireframe`).
- **Barycentric wireframe shader.** Anti-aliased, constant-width lines with animatable reveal; used for the wire→solid morph ([glsl-solid-wireframe](https://npmjs.com/package/glsl-solid-wireframe); [Metail: About solid wireframes](https://tech.metail.com/?p=453)).
- **Hidden-line removal.** Render the mesh first in the background colour with `polygonOffset`, then edges on top. For dashed hidden lines, add a second pass with `depthFunc: GreaterDepth` and a dashed material.
- **Depth cue.** Fog or a custom fade of line alpha by view depth.
- **Camera path.** Spline plus `lookAt` targets per station, progress = scroll (GSAP ScrollTrigger scrub, or Theatre.js sequences as in the Codrops tutorial).
- **Callouts.** Project 3D anchor points to screen each frame (`vector.project(camera)`) and position HTML labels plus SVG leader lines. Hide them when occluded (raycast or depth test).
- **2D fallback.** Isometric SVG line drawings with `stroke-dashoffset` plotting. This is also the reduced-motion and low-power path.
- **Performance.**
  - Edge count is the cost driver. Decimate models and use threshold angles of 15–30°.
  - Fat lines are instanced quads, which is fine up to tens of thousands of segments.
  - Cap DPR.
- **Accessibility.**
  - Continuous camera flight is a vestibular risk. With reduced motion, **cut** between fixed stations (each station a static view with a 200 ms fade) and present the exploded view as a static diagram. Lines remain, so the style survives.
  - Callout text must be real DOM text with sufficient contrast against grid lines. Use a background knockout behind labels.

### 5.7 Anti-patterns
- An infinite synthwave terrain with a magenta sunset (that is Synthwave, and collides with Neon).
- A random rotating wireframe icosahedron or globe in the hero as a generic "tech" ornament with no relation to content.
- `WireframeGeometry` showing every triangle: moiré noise, unreadable, "unfinished model" rather than "drawing".
- 1px aliased lines flickering on Windows.
- The particles.js plexus (lines between random points), which is not wireframe.
- An over-busy HUD with fake data.
- **Overlap risks.** Wireframe feels the same as Neon if lines glow heavily with bloom (keep lines crisp, technical, mostly unglowed). It feels the same as Particles if vertices are emphasised as dots. It feels the same as Holographic if lines become translucent cyan projections with scanlines.

### 5.8 UX signature
**"You fly through the blueprint."** The site is a single 3D world drawn only in precise lines, and scrolling *is* the camera moving through it, from station to station like a guided tour of an engineering drawing. Copy is pinned to the model by leader lines, and numbers are dimensions measured on the object. Features are parts of an exploded view that fly apart and reassemble. At the climax, the line drawing **solidifies into the real product**: design becomes reality. The feeling is precise understanding of how the thing is built.

**Engine notes.** Scroll model: one continuous camera spline across the whole page, with eased stations. Transition primitive: camera move plus view-mode change (ortho snap, section cut, explode). Required data: a 3D model or line scene, a station list (camera position and target), and anchor points for callouts.

---

## Contrast table: the five UX signatures

| | Particles | Liquid morph | Holographic | Neon glow | Wireframe 3D |
|---|---|---|---|---|---|
| **Core experience** | One swarm of matter re-forms into each section's subject | One viscous body metamorphoses; nothing ever cuts | Scrolling turns rigid plates; light and hidden content depend on angle | Walking a night street; signs ignite as you arrive | Camera flies through a world drawn in lines; drawing becomes product |
| **Primitive** | Discrete points | Continuous surface | Angle-dependent film/plate | Emissive tube on a material wall | Edges in 3D space |
| **Scroll drives** | `progress` of an assemble/disperse morph (pinned scenes) | Shape target, plus **scroll velocity** → deformation | **Rotation angle** of each plate (`view()` timeline) | **Power state** per section (unlit → igniting → lit → dim) | **Camera position** on one spline |
| **Section transition** | Disperse → turbulent travel → condense | Liquid wipe / the blob floods into the next background | Projector scan line; materialise and de-resolve | Power handover; ambient spill colour crossfade | Camera move plus view-mode change (ortho snap, cut, explode) |
| **Headline arrives by** | Particles locking into letterforms | Variable-font axes melting into crisp | Single foil sheen pass | Tubes drawing on, then ignition stutter | Pen-plotter stroke drawing plus leader line |
| **Stats as** | Data-as-matter (dot proportions, particle digits) | Cell division: one drop splits into stat droplets | Volumetric projected or latent-at-angle numbers | Segmented neon numerals (price/vacancy sign) | Dimension lines measuring the model |
| **Features as** | Constellation clusters | Fusion carousel / parent blob splitting | Binder of tiltable holo cards with flip-backs | Sign sequencer lighting one by one | Exploded view with numbered balloons and BOM |
| **CTA as** | Gravity well that inhales particles | Liquid-fill button the blob pools around | Rarest foil card / security seal | The "OPEN" sign switching on | Final assembly, "Approved for build" |
| **Pointer is** | Force field | Finger in viscous fluid / merging droplet | Light source and eye (and gyroscope) | Hand near the glass / power switch | Inspection probe (highlight, measure) |
| **Layout container** | Void canvas, text at margins | Organic asymmetric flow, soft capsules | Objects on pedestals, z-stacked translucent plates | Storefront collage on textured walls | Technical drawing sheet, callouts anchored to 3D |
| **Reduced-motion version** | Static assembled formations, crossfades | Static blobs, crossfades between end shapes | Fixed angle, latent content shown directly | Signs already lit, no flicker | Cuts between fixed stations, static exploded diagram |
| **Never share with others** | Lines between points; goo | Dots; angle-iridescence | Emissive fixed-colour lines; melting | Spectral shifts; 3D outline worlds | Bloom-heavy glow; vertex dots; scanline projections |
