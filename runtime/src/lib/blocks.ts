/**
 * Scroll motion for content blocks and the stack layout. Everything here is a pure function of scroll
 * position (no timers), and every block is complete without it.
 *
 *   stack   each .ss-panel is sticky; the panel being covered shrinks slightly and darkens (--cover).
 *           Panels taller than the screen stick by their bottom edge, so their own content scrolls first.
 *   hero    the photo zooms and the copy lifts away as the hero is left (--hero-p)
 *   product the image and phone drift against the scroll (--float)
 *   strip   the row of photos slides sideways (--strip, in px)
 *   orbit   services sit on two rings that turn in opposite directions
 */
import { clamp, reducedMotion } from "./util";

export function makeBlocks() {
  const panels = [...document.querySelectorAll<HTMLElement>(".ss-panel")];
  const heroes = [...document.querySelectorAll<HTMLElement>(".ss-hero")];
  const floats = [...document.querySelectorAll<HTMLElement>("[data-float]")];
  const strips = [...document.querySelectorAll<HTMLElement>("[data-strip]")];
  const orbits = [...document.querySelectorAll<HTMLElement>("[data-orbit]")].map((stage) => {
    stage.classList.add("ss-orbit--live");
    return { stage, items: [...stage.querySelectorAll<HTMLElement>(".ss-orbit__item")] };
  });
  if (!panels.length && !heroes.length && !floats.length && !strips.length && !orbits.length) return () => {};

  const covers = new Map<HTMLElement, number>();
  let lastY = NaN, lastH = NaN, lastDoc = NaN;

  // In the stack layout an element's motion follows its panel: entering (0 -> .5), then being covered (.5 -> 1).
  // In the normal flow it follows the element's own trip across the screen.
  function progress(el: HTMLElement): number {
    if (reducedMotion) return 0.5;
    const panel = el.closest<HTMLElement>(".ss-panel");
    if (panel) {
      const enter = clamp(1 - panel.getBoundingClientRect().top / innerHeight);
      return (enter + (covers.get(panel) ?? 0)) / 2;
    }
    const r = el.getBoundingClientRect();
    return clamp((innerHeight - r.top) / (innerHeight + r.height));
  }

  return function update() {
    const doc = document.documentElement.scrollHeight;
    if (scrollY === lastY && innerHeight === lastH && doc === lastDoc) return;
    const resized = innerHeight !== lastH || doc !== lastDoc;
    lastY = scrollY; lastH = innerHeight; lastDoc = doc;

    if (resized) panels.forEach((p) => { p.style.top = Math.min(0, innerHeight - p.offsetHeight) + "px"; });
    panels.forEach((p, i) => {
      const next = panels[i + 1];
      const k = next && !reducedMotion ? clamp(1 - next.getBoundingClientRect().top / innerHeight) : 0;
      covers.set(p, k);
      p.style.setProperty("--cover", k.toFixed(3));
    });

    for (const h of heroes) {
      const panel = h.closest<HTMLElement>(".ss-panel");
      const r = h.getBoundingClientRect();
      const k = reducedMotion ? 0 : panel ? covers.get(panel) ?? 0 : clamp(-r.top / Math.max(1, r.height));
      h.style.setProperty("--hero-p", k.toFixed(3));
    }
    for (const f of floats) f.style.setProperty("--float", (progress(f) * 2 - 1).toFixed(3));
    for (const s of strips) {
      const travel = Math.max(0, s.scrollWidth - innerWidth);
      s.style.setProperty("--strip", (progress(s) * travel).toFixed(1));
    }
    for (const { stage, items } of orbits) {
      const W = stage.clientWidth;
      // Too narrow for two legible rings (phones): keep the static wrapped layout from the stylesheet.
      const live = W >= 480;
      if (stage.classList.contains("ss-orbit--live") !== live) {
        stage.classList.toggle("ss-orbit--live", live);
        if (!live) items.forEach((el) => { el.style.transform = ""; });
      }
      if (!live) continue;
      const p = progress(stage), inner = Math.ceil(items.length / 2);
      // Radii come from the circles' real size: the outer ring just fits the stage and the inner ring sits one
      // circle (plus a gap) inside it, so circles on different rings never touch however far they turn.
      const s = items[0]?.offsetWidth || 100;
      const outer = W / 2 - s / 2 - 4, innerR = Math.max(s * 0.8, outer - s - 14);
      stage.style.setProperty("--r-in", innerR.toFixed(1) + "px");
      stage.style.setProperty("--r-out", outer.toFixed(1) + "px");
      items.forEach((el, i) => {
        const ring = i < inner ? 0 : 1, n = ring ? items.length - inner : inner, j = ring ? i - inner : i;
        const turn = ring ? -p * Math.PI / 3 : p * Math.PI / 2;
        const a = (j / n) * Math.PI * 2 - Math.PI / 2 + turn + (ring ? Math.PI / n : 0);
        const rad = ring ? outer : innerR;
        el.style.transform = `translate(${(Math.cos(a) * rad).toFixed(1)}px, ${(Math.sin(a) * rad).toFixed(1)}px)`;
      });
    }
  };
}
