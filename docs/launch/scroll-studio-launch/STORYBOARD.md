---
format: 1920x1080
duration: 38s
message: "Grey blocks in, cinematic scroll sites out: all local, no API keys"
arc: BAB — before → after → bridge (it scrolls) → three ways → mechanism → CTA
audience: developers and creative technologists browsing the GitHub repo
mode: autonomous
music: cinematic electronic pulse, confident and modern, steady build, warm synth bass, no vocals
---

## Video direction

- **Palette (frame.md, Broadside):** dark register throughout: ground `ink-black`, type `cream`, secondary type `cream-muted`, the single accent `fire-orange` (wipe seam, rule stubs, kickers, key words). Frame 4 is the one `orange` register frame (ground `fire-orange`, type `ink-black`), the chapter break. No other hues; the footage supplies all colour.
- **Type (frame.md):** display / h1 / h2 in Barlow, lowercase, heavy, negative tracking; kickers and tags in IBM Plex Mono uppercase `label`. Slide chrome is suppressed on every frame (declarative frames).
- **Footage is the hero.** The film and site recordings are real product output: never tint, blur or stylise them beyond a dim when type sits on top. Video sits in flat rectangles with a 1px `border-dark` hairline, square corners, no shadow, no browser chrome.
- **Motion grammar:** long-tail `power3` settles, no overshoot, no bounce. Reveals are paced to the on-screen line (there is no voiceover; the supers are the script, and each super line is one cue). Type enters per word or by a clip-mask wipe; footage enters by scale-swap or wipe. Velocity-matched seams inside frames.
- **Rhythm:** F1 slow and quiet (the plain blockout); F2 is the climax of the angle (the wipe); F3 lifts; F4 is a fast held chapter card (breather); F5/F6 are mirrored showcase beats; F7 builds; F8 is a still held lockup.
- **Negative list:** no bouncy eases, no lazy breathing, no back-half slow push/pan on type, no floating bokeh or purple/blue "AI" gradients, no fake UI chrome or cursors, no film grain/scanlines over the footage, no infinite loops, no randomness. Slideshow (front-load then freeze) and screensaver (everything drifting) are both failures.
- **Caption band:** no captions (music only), but keep the bottom ~10% free of key type for README-thumbnail legibility.

## Frame 1 — This is a blockout

- scene: The grey Blender blockout plays full-bleed while the line "this is a blockout." types on
- duration: 4.5s
- poster: 3.5s
- transition_in: cut
- status: outline
- type: hook
- beat: curiosity
- voiceover: "This is a blockout. — Grey boxes. A camera path."
- asset_candidates: assets/film-before.mp4 — the grey Blender blockout, 18 s, plays from media 0 s
- blueprint: kinetic-type-beats (Adapt)
- focal: assets/film-before.mp4
- roles: film-before = background (full-bleed, dim to ~70% so type reads)
- sfx: none
- src: compositions/frames/01-blockout.html

Adapt: keep the statement-builds-across-beats signature; the "full-screen beats" sit over the blockout footage instead of a flat field.
Scene 1 (0.0–0.6s): film-before full-bleed from media 0 s (the pad, grey towers), at ~70% brightness. Nothing else. Hard open.
Scene 2 (0.6–2.2s): lower-left third, h1 "this is a blockout." enters per word (`dynamic-content-sequencing`), long-tail settle; a 36×2 fire-orange rule stub draws in above it.
Scene 3 (2.2–3.6s): beneath, a mono `label` line swaps in place by hard cut (`discrete-text-sequence`): "BLENDER" → "GREY BOXES" → "A CAMERA PATH". The footage keeps playing (camera begins to lift).
Scene 4 (3.6–4.5s): held read. The type stays put; footage carries the motion.
- handoff_out: film-before video element: full-bleed x=0 y=0 1920×1080, scale 1, opacity 1, brightness 0.7, playing at 1× at media time 4.5 s at the cut. The h1 and label do not continue.

## Frame 2 — Same camera. Rendered.

- scene: An orange seam sweeps across the frame; behind it the grey blockout becomes the finished film, frame-locked
- duration: 7s
- poster: 3.0s
- transition_in: cut
- status: outline
- type: product_intro
- beat: reveal (the before/after climax)
- voiceover: "Same camera. Same timing. — Rendered locally with LTX-2.3."
- asset_candidates: assets/film-before.mp4 — blockout, continue from media 4.5 s; assets/film-after.mp4 — the finished film, same timeline, from media 4.5 s
- blueprint: compose (wipe reveal; signature = the frame-locked before/after seam)
- focal: assets/film-after.mp4
- roles: film-after = background (full-bleed, under the before) · film-before = background (full-bleed, on top, clipped by the seam)
- sfx: none
- src: compositions/frames/02-wipe.html
- handoff_in: film-before full-bleed x=0 y=0 1920×1080, scale 1, opacity 1, brightness 0.7 → animate brightness to 1.0 over the first 0.4 s; media time 4.5 s at frame start; playing 1×.

Both videos play in lockstep from media 4.5 s (data-media-start 4.5 for both), stacked full-bleed: film-after below, film-before above with a `clip-path: inset(0 0 0 X%)` (the before is shown to the right of the seam, the after to the left).
Scene 1 (0.0–0.8s): before only (seam at x = 0%). Mono tag "BEFORE" top-right, cream-muted, enters with a clip wipe.
Scene 2 (0.8–4.2s): the signature move. A 2px fire-orange vertical seam travels left → right from 0% to 100% on a slow `power2.inOut` (one continuous move); the after film is revealed behind it (rocket climbing through dawn clouds over the blockout's grey sky). Mono tag "AFTER" top-left appears as the seam passes ~15%. As the seam crosses the middle (~2.2s), h2 "same camera. same timing." reveals per word at upper-left third.
Scene 3 (4.2–5.6s): seam exits right edge and fades; "BEFORE" tag is gone with it. The h2 line swaps (waterfall cut, `cut-catalog.md`) to "rendered locally." with "ltx-2.3" in fire-orange.
Scene 4 (5.6–7.0s): mono `label` beneath: "BLENDER DEPTH → LTX-2.3 · NO API KEYS". Held read over the film (above the clouds).
- handoff_out: film-after full-bleed x=0 y=0 1920×1080, scale 1, opacity 1, brightness 1, playing 1×, media time 11.5 s at the cut. Type does not continue.

## Frame 3 — Then it scrolls

- scene: The film shrinks into a framed panel and becomes the live scroll site with its mission HUD
- duration: 5s
- poster: 3.5s
- transition_in: cut
- status: outline
- type: feature_showcase
- beat: lift
- voiceover: "Then it scrolls. — 01 · AI film."
- asset_candidates: assets/film-after.mp4 — finished film, continue from media 11.5 s; assets/site-rocket.mp4 — scroll-through of the Lodestar Orbital site, 9 s
- blueprint: device-surface-showcase (Adapt)
- focal: assets/site-rocket.mp4
- roles: film-after = background (full-bleed at start, then shrinks) · site-rocket = cutout (the floating panel)
- sfx: none
- src: compositions/frames/03-scrolls.html
- handoff_in: film-after full-bleed x=0 y=0 1920×1080, scale 1, opacity 1, brightness 1, media time 11.5 s, playing 1×.

Adapt: keep the floating-window hero with its screens cycling a real flow; no device bezel, no browser chrome — a flat panel with a 1px hairline.
Scene 1 (0.0–1.0s): film-after continues full-bleed (stage separation in black space).
Scene 2 (1.0–1.9s): card morph-anchor (`card-morph-anchor`): the full-bleed film scales down to a right-weighted panel (~68% width, right edge at pad-x, vertically centred in the top 90%) on `power3.inOut`; at the end of the move it cross-dissolves into site-rocket.mp4 (from media 1.5 s) at the same rect. Ground behind is ink-black.
Scene 3 (1.9–3.4s): left column: kicker "01 — AI FILM" (fire-orange mono), then h2 "then it scrolls." per-word reveal.
Scene 4 (3.4–5.0s): body line in cream-muted reveals beneath: "the film is scrubbed by your scroll. mission hud included." Held read; the site recording keeps scrolling.

## Frame 4 — Made three ways

- scene: Orange chapter card, "made three ways." with the three ways cycling in place
- duration: 3s
- poster: 2.6s
- transition_in: push-slide LEFT
- status: outline
- type: benefit_highlight
- beat: chapter / breather
- voiceover: "Made three ways. — AI film. Real art. Live 3D."
- asset_candidates: none
- blueprint: kinetic-type-beats (Reproduce)
- focal: the line itself
- roles: none (type only, orange register)
- sfx: none
- src: compositions/frames/04-three-ways.html

Orange register: ground fire-orange, type ink-black.
Scene 1 (0.0–0.9s): display "made three ways." enters per word, left-aligned at the vertical centre; mono catalogue numeral "01 / 02 / 03" faint top-left.
Scene 2 (0.9–2.4s): below it, an fadelist-item line swaps in place by hard cut (`discrete-text-sequence`): "ai film." → "real art, drawn live." → "live 3d." — each on its own beat; the numeral's matching digit goes full ink as each lands.
Scene 3 (2.4–3.0s): held on "live 3d."

## Frame 5 — The Mona Lisa, drawn as you scroll

- scene: The art-school site draws the Mona Lisa as it scrolls, in a panel on the left; copy on the right
- duration: 5s
- poster: 3.8s
- transition_in: push-slide LEFT
- status: outline
- type: feature_showcase
- beat: wonder
- voiceover: "02 · Real artwork, drawn live. — The Mona Lisa, built as you scroll."
- asset_candidates: assets/site-mona.mp4 — scroll-through of the Atelier Sfumato site, 9 s
- blueprint: device-surface-showcase (Adapt)
- focal: assets/site-mona.mp4
- roles: site-mona = cutout (the panel)
- sfx: none
- src: compositions/frames/05-mona.html

Adapt: mirrored layout of Frame 3 (panel left, copy right) so the pair reads as a set; flat panel, 1px hairline, no chrome.
Scene 1 (0.0–0.8s): panel (~62% width, left edge at pad-x, vertically centred) enters with a clip-mask wipe up; site-mona.mp4 plays from media 2.0 s (guides → contours drawing).
Scene 2 (0.8–2.2s): right column: kicker "02 — REAL ARTWORK, DRAWN LIVE" then h2 "the mona lisa, built as you scroll." per-word reveal.
Scene 3 (2.2–5.0s): body (cream-muted): "guides → charcoal → graphite → umber → glaze. from the real painting." reveals by phrase on its arrows (`dynamic-content-sequencing`). Held read while the painting fills in.

## Frame 6 — Tissue to molecule

- scene: The biomedical three.js site zooms from cells to a docking molecule, panel on the right
- duration: 5s
- poster: 3.8s
- transition_in: push-slide LEFT
- status: outline
- type: feature_showcase
- beat: scale
- voiceover: "03 · Live 3D. — From tissue to molecule, in one scroll."
- asset_candidates: assets/site-bio.mp4 — scroll-through of the Cellwright Bio site, 9 s
- blueprint: device-surface-showcase (Adapt)
- focal: assets/site-bio.mp4
- roles: site-bio = cutout (the panel)
- sfx: none
- src: compositions/frames/06-bio.html

Adapt: same as Frame 3's layout (panel right, copy left) so 3/5/6 alternate right/left/right.
Scene 1 (0.0–0.8s): panel (~68% width, right edge at pad-x, vertically centred) enters with a clip-mask wipe up; site-bio.mp4 plays from media 2.5 s (into the cell → nucleus).
Scene 2 (0.8–2.2s): left column: kicker "03 — LIVE 3D" then h2 "tissue to molecule, in one scroll." per-word reveal.
Scene 3 (2.2–5.0s): a stat-card reveals beneath: stat-value "100 µm → 0.3 nm" (fire-orange) with mono label "SIX ORDERS OF MAGNITUDE · THREE.JS". Held read.

## Frame 7 — One GPU. No API keys.

- scene: The pipeline draws itself as four stations joined by an orange line, then the local-only claim lands
- duration: 5.5s
- poster: 4.8s
- transition_in: crossfade 0.4s
- status: outline
- type: benefit_highlight
- beat: mechanism → trust
- voiceover: "Blender blockout → Z-Image keyframes → LTX-2.3 → scroll site. — One RTX 4090. No API keys."
- asset_candidates: assets/film-before.mp4 — station 1 thumbnail; assets/film-after.mp4 — station 3 thumbnail
- blueprint: spatial-pan-stations (Adapt)
- focal: the orange line connecting the stations
- roles: film-before = supporting (small thumbnail, station 1) · film-after = supporting (small thumbnail, station 3)
- sfx: none
- src: compositions/frames/07-pipeline.html

Adapt: keep the stations-on-one-line signature, but no camera pan: the frame is wide enough for four stations in a full-width strip across the upper-middle; the travelling element is the orange line drawing station to station (`svg-path-draw`).
Scene 1 (0.0–0.6s): kicker "HOW IT WORKS" top-left. A 2px fire-orange line starts drawing from the left margin.
Scene 2 (0.6–3.4s): four stations reveal as the line reaches each (≈0.7s apart): each = mono numeral + h3 name + a small 16:9 thumbnail tile (1px hairline) above it. 1 "blender blockout" (film-before thumb, media 9 s, still), 2 "z-image keyframes" (no thumb: a mono "8-STEP · DEPTH CONTROLNET" tag), 3 "ltx-2.3 film" (film-after thumb, media 9 s, still), 4 "scroll site" (mono "SCRUB · WEBGL · THREE.JS" tag).
Scene 3 (3.4–5.5s): below the strip, h1 "one rtx 4090. no api keys." per-word reveal, "no api keys." in fire-orange. Held read.

## Frame 8 — Scroll Studio

- scene: Wordmark lockup "scroll studio" with the repo URL; still hold to the end
- duration: 3.5s
- poster: 2.5s
- transition_in: crossfade 0.5s
- status: outline
- type: cta
- beat: lockup
- voiceover: "Scroll Studio. — github.com/Okohedeki/scroll-studio"
- asset_candidates: none
- blueprint: logo-assemble-lockup (Adapt)
- focal: the wordmark
- roles: none
- sfx: none
- src: compositions/frames/08-end.html

Adapt: the wordmark is type; it assembles by per-letter cascade, no logo mark.
Scene 1 (0.0–1.2s): display "scroll studio" assembles letter by letter (rise + clip, `power3`), centred-left at the optical middle; a 36×2 fire-orange rule stub draws in above it.
Scene 2 (1.2–2.0s): mono label beneath: "GITHUB.COM/OKOHEDEKI/SCROLL-STUDIO", then a smaller cream-muted line "scroll-driven sites · local ai film · no api keys".
Scene 3 (2.0–3.5s): still hold. Final 0.4s: the whole frame fades to ink-black (the only real exit in the video).
