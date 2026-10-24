/** Test helpers: the environment a runtime module reads (media queries, the screen, scroll, layout boxes) set from a test. */
import { vi } from "vitest";

/** What `matchMedia` answers (see setup.ts). Changing it after a module is imported has no effect on constants the
 * module read at import: use `fresh` for those. */
export const media = { reduced: false, mobile: false };
export const resetMedia = () => { media.reduced = false; media.mobile = false; };

/** The screen: viewport size and scroll position. */
export function screen(o: { w?: number; h?: number; y?: number } = {}) {
  const { w = 1280, h = 800, y = 0 } = o;
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: w });
  Object.defineProperty(window, "innerHeight", { configurable: true, writable: true, value: h });
  Object.defineProperty(window, "scrollY", { configurable: true, writable: true, value: y });
  Object.defineProperty(document.documentElement, "clientWidth", { configurable: true, value: w });
}
export const scrollTo = (y: number) => { Object.defineProperty(window, "scrollY", { configurable: true, writable: true, value: y }); };

/** Give an element a layout box (jsdom has none). `top` is its viewport top; the rest follows from the size. */
export function box(el: Element, top: number, height: number, o: { left?: number; width?: number } = {}) {
  const { left = 0, width = 1280 } = o;
  const r = { top, bottom: top + height, left, right: left + width, width, height, x: left, y: top, toJSON: () => ({}) } as DOMRect;
  el.getBoundingClientRect = () => r;
  for (const [k, v] of [["offsetHeight", height], ["offsetWidth", width], ["clientHeight", height], ["clientWidth", width], ["offsetTop", top], ["offsetLeft", left]] as const) {
    Object.defineProperty(el, k, { configurable: true, value: v });
  }
}

/** Move an element that already has a box (a scroll), keeping its size. */
export function moveTo(el: Element, top: number) {
  const r = el.getBoundingClientRect();
  box(el, top, r.height, { left: r.left, width: r.width });
}

/** Import a module again with a clean module registry (for the ones that read `location`, `matchMedia` or a global at import). */
export async function fresh<T>(load: () => Promise<T>): Promise<T> {
  vi.resetModules();
  return load();
}

/** A run of animation frames, called by hand. */
export function frames() {
  const queue: FrameRequestCallback[] = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => { queue.push(cb); return queue.length; });
  let now = 0;
  return {
    /** run the callbacks queued so far (they may queue the next frame) */
    step(dt = 16) { now += dt; const run = queue.splice(0); run.forEach((cb) => cb(now)); },
    get pending() { return queue.length; },
  };
}

export const html = (markup: string) => { document.body.innerHTML = markup; return document.body; };

/** What the scene controller hands a player. */
export function playerCtx(steps: { intro?: boolean; length?: number }[] = []) {
  const section = document.createElement("section");
  const visual = document.createElement("div");
  section.appendChild(visual);
  document.body.appendChild(section);
  const progress = vi.fn();
  const data = { hud: { kind: "none", fields: [], events: [], clock: null, scales: [], legend: [] }, steps: steps.map((s) => ({ title: "t", length: 1, ...s })), layout: "overlay", length: 1 } as any;
  return { section, visual, progress, data };
}

/** What a player sees every frame. */
export const frameState = (p: number, o: Record<string, unknown> = {}) => ({ p, steps: [] as number[], active: -1, t: 0, mx: 0, my: 0, ...o }) as any;

/** Load a module the way the page does for `?p=<p>` (eased values jump straight to their target), with the media features given. */
export async function atPage<T>(load: () => Promise<T>, o: { p?: number; reduced?: boolean; mobile?: boolean } = {}): Promise<T> {
  history.replaceState(null, "", o.p === undefined ? "/" : `/?p=${o.p}`);
  media.reduced = !!o.reduced;
  media.mobile = !!o.mobile;
  vi.resetModules();
  return load();
}
