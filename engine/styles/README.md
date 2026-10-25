# Styles: one spec, different experiences

`theme: { style: <name> }` changes the **experience** of a site, not just its skin: what scrolling does, how
content is laid out and arrives, how the pointer behaves, and how sections hand over. Two styles that share the
same scroll mechanic, layout and transitions are one style in two colours, and fail review.

The research behind each style (origin, layout, scroll and pointer behaviour, components, type, implementation,
anti-patterns, and a one-paragraph UX signature) is in [docs/styles/](../../docs/styles/) (styles-01-05.md ... styles-26-27.md).

## A style is a folder

```
engine/styles/<name>/
  style.yaml        label, about, mode, colors, fonts, font_axes (Google css2 specs for its fonts), radius,
                    optional requires (tokens a brand may not change, below) and cuts.
                    fonts beyond display/body/mono (e.g. masthead: UnifrakturMaguntia) are loaded and exposed as
                    --font-<role> CSS variables
  style.css         everything visual, scoped under html.style-<name>
  blocks.html.j2    its own markup for block types (optional, but every real style has one)
  chrome.html.j2    page furniture around the sections: its own nav, HUD, title block, OSD... (optional)
  scenes.html.j2    its own markup for scene types (optional, rare)
runtime/src/styles/<name>.ts   its experience: scroll controller, transitions, pointer (loaded only for this style)
```

### Wearing a brand (`theme.from`)

A style is a named token set over the preset, and a brand is laid over the style (the order is in the
[guide](../../docs/guide.md#themes-and-brands)). With a brand on, the compiler swaps the style's own palette, every
colour in its `style.yaml` `colors` as `#hex` or `rgb()` anywhere in `style.css`, for the brand's, and its display, body
and mono families (quoted) for the brand's faces. So:

- **Write the palette with the colours your `style.yaml` declares** (or `var(--bg)`, `var(--ink)`, `var(--accent)`...).
  Colours that are not in the palette are the style's own (a CRT's phosphor green, a pin's brass) and stay, and so
  do pure black and white and `accent_ink` (unless it is also another palette colour, such as the background). The brand's accents are held to the contrast your own accent has with your
  background and your `accent_ink` (up to 7:1), so declare the `accent_ink` your stylesheet really sets on the accent.
- **Declare what a brand may not change** in `requires`, a token set laid over the brand. A style drawn for a light or
  dark room requires its `mode`; the brand's palette is then rebuilt in that mode around the brand's accents. A style
  whose mechanic is a typeface requires that face:

  ```yaml
  requires:
    mode: dark
    fonts: { display: Tilt Neon }
  ```

`tests/test_conformance.py` renders every style wearing three unrelated brands (light, dark, saturated) and checks the
contrast rules on each.

### blocks.html.j2

```jinja
{% set types = ["hero", "intro", "features", "product", "stats", "timeline", "quote", "faq", "cta"] %}
{% macro render(b, e, base, loop) %}
  {# b: the block (engine/spec.py), e: compiler extras (e.img, e.screen, e.first...), base: the default
     blocks module (base.render(b, e), base.buttons(list), base.phone(d, screen, clip)), loop: the page loop
     (loop.index0, loop.first, loop.last, loop.length) #}
{% endmacro %}
```

Types not listed fall back to the default markup (and should still be styled). Filters: `| rich` (allows
`<em>`, `<b>`, `<i>`, `<br>`), `| vh`, `| countable`.

### chrome.html.j2

```jinja
{% macro top(site, sections, nav_links) %}...{% endmacro %}   {# before <main> #}
{% macro bottom(site, sections) %}...{% endmacro %}           {# after </main> #}
```

The default nav (`.ss-nav`) and footer (`.ss-footer`) are always rendered; hide them in style.css when the chrome
replaces them.

### The runtime experience

`runtime/src/styles/<name>.ts` exports `default function start(): void`. It runs after the page loads, only for this
style. Use `runtime/src/styles/_kit.ts`: `onFrame` (scroll y, eased velocity, time), `through(el)`, `pinned(track)`,
`pinSequence(section, steps, onStep)`, `chars(el)`, `typeTo(spans, k)`, `onSeen(el, fn)`, `css(text)`, `reduced`.

### theme.art

When the site sets `theme.art`, templates see `art` (`label`, `frames`, `w`, `h`, `fps`, `sheet`) and the page carries
it as `<script id="ss-art">`. `runtime/src/styles/_art.ts` gives the runtime `loadArt()` (each frame as a 0..1 subject
mask, background 0 whichever way the image was lit), `asciiFrame(art, frame, cols, rows)` and `rowsFor(...)`. Draw
the art in your style's own medium; keep it decorative (`role="img"` with the label) so the page still reads without it.

## Rules

`tests/test_conformance.py` checks the folder, the tokens (colour roles, mode, contrast), the block types, the
docs and that every style renders a page holding every block type; the full list is in
[CONTRIBUTING.md](../../CONTRIBUTING.md#consistency-rules).


1. **The page works without JavaScript.** All content is real HTML text in reading order; the first heading on the
   page is the `<h1>`. JavaScript adds the experience; it never holds content hostage (no text that only exists after
   an animation).
2. **Don't use the default motion.** Markup in your templates should not use `ss-reveal` or `data-count` (the
   default fade-up and count-up); your style has its own arrivals.
3. **Reduced motion** (`prefers-reduced-motion: reduce`, `_kit.reduced`): use the fallback from the research
   brief. The style must stay recognisable with motion off.
4. **No flashing** above 3 times a second, never saturated red flashes, nothing that strobes full screen
   (WCAG 2.3.1).
5. **Performance:** animate `transform` and `opacity`; pause canvases and loops off screen; one canvas per page is
   better than one per element.
6. **Phones:** the experience works at 390 px wide (it may simplify, as the brief says).
7. **Everything comes from the spec.** Content, order and counts come from the site's sections; nothing is
   hard-coded for one demo. Handle a spec with more or fewer items, missing optional fields, and repeated block
   types.
8. **Transitions** (`transition:` on a section, see "Edited like a film" in [docs/scenes.md](../../docs/scenes.md#edited-like-a-film-transition)): by default a style takes them, since
   they play on the sections' own wrappers. A style that makes the whole page one object of its own (a book, a wheel, a
   game, one canvas) already plays its own hand-over between sections: give it `cuts: false` in style.yaml and the cuts
   are dropped for it with a note. A style with its own markup should keep its sections' content in one root element
   per section, since the cut moves, scales and blurs that element.
