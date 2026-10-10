/**
 * Toolkit for style experiences (runtime/src/styles/<style>.ts). An experience restructures nothing the page needs
 * to work without JavaScript: the static page is complete, and these helpers add the style's own scroll mechanics.
 */
import { clamp, reducedMotion } from "../lib/util";

export const reduced = reducedMotion;
export const $ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document) => root.querySelector<T>(sel as any) as T | null;
export const $$ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document) => [...root.querySelectorAll<T>(sel as any)] as T[];

type FrameFn = (f: { y: number; v: number; dt: number; t: number; vh: number }) => void;
const frames: FrameFn[] = [];
let lastY = scrollY, lastT = performance.now(), vel = 0, running = false;
/** Run fn every animation frame with the scroll position, an eased scroll velocity (px per frame) and time. */
export function onFrame(fn: FrameFn) {
  frames.push(fn);
  if (running) return;
  running = true;
  const t0 = performance.now();
  const tick = (now: number) => {
    const dt = Math.min(0.05, (now - lastT) / 1000);
    lastT = now;
    vel += ((scrollY - lastY) - vel) * 0.2;
    lastY = scrollY;
    const f = { y: scrollY, v: reduced ? 0 : vel, dt, t: (now - t0) / 1000, vh: innerHeight };
    for (const fn of frames) fn(f);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/** 0 when the element's top reaches the bottom of the screen, 1 when its bottom leaves the top. */
export function through(el: Element): number {
  const r = el.getBoundingClientRect();
  return clamp((innerHeight - r.top) / (innerHeight + r.height));
}

/** Progress of a pinned track: 0 when its top hits the top of the screen, 1 when its bottom hits the bottom. */
export function pinned(track: Element): number {
  const r = track.getBoundingClientRect();
  return clamp(-r.top / Math.max(1, r.height - innerHeight));
}

/**
 * Turn a section into a pinned sequence: the section gets a tall track (steps x screens) and a sticky stage that
 * holds its content; onStep receives the fractional step (0 .. n) as the visitor scrolls. Returns the stage.
 */
export function pinSequence(section: HTMLElement, steps: number, onStep: (s: number, p: number) => void, screensPerStep = 0.9): HTMLElement {
  const stage = document.createElement("div");
  stage.className = "sx-stage";
  while (section.firstChild) stage.appendChild(section.firstChild);
  const track = document.createElement("div");
  track.className = "sx-track";
  track.style.height = `${100 + steps * screensPerStep * 100}svh`;
  track.appendChild(stage);
  section.appendChild(track);
  section.classList.add("sx-pinned");
  onFrame(() => { const p = reduced ? 1 : pinned(track); onStep(p * steps, p); });
  return stage;
}

/** Wrap every character of el's text (inline markup kept) in a span; returns the spans in reading order. */
export function chars(el: HTMLElement, cls = "sx-ch"): HTMLSpanElement[] {
  const out: HTMLSpanElement[] = [];
  const label = el.textContent || "";
  const walk = (node: Node) => {
    if (node.nodeType === 3) {
      const frag = document.createDocumentFragment();
      (node.textContent || "").split(/(\s+)/).forEach((part) => {
        if (!part) return;
        if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
        const w = document.createElement("span");
        w.className = "sx-word";
        for (const c of part) {
          const s = document.createElement("span");
          s.className = cls;
          s.textContent = c;
          s.style.setProperty("--i", String(out.length));
          w.appendChild(s);
          out.push(s);
        }
        frag.appendChild(w);
      });
      node.parentNode!.replaceChild(frag, node);
    } else [...node.childNodes].forEach(walk);
  };
  [...el.childNodes].forEach(walk);
  el.setAttribute("aria-label", label);
  return out;
}

/** Show the first round(k * n) characters (typewriter driven by a 0-1 value, e.g. scroll progress). */
export function typeTo(spans: HTMLElement[], k: number) {
  const n = Math.round(clamp(k) * spans.length);
  spans.forEach((s, i) => { s.style.visibility = i < n ? "visible" : "hidden"; });
}

/** Run once when el is first at least `threshold` on screen. */
export function onSeen(el: Element, fn: () => void, threshold = 0.3) {
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { io.disconnect(); fn(); } }), { threshold });
  io.observe(el);
}

/** Inject a stylesheet once (for rules that only make sense once the experience has restructured the page). */
export function css(text: string) {
  const s = document.createElement("style");
  s.textContent = text;
  document.head.appendChild(s);
}

css(`.sx-pinned { padding-top: 0 !important; padding-bottom: 0 !important; }
.sx-track { position: relative; }
.sx-stage { position: sticky; top: 0; height: 100vh; height: 100svh; overflow: hidden; }
.sx-word { display: inline-block; white-space: nowrap; }
.sx-ch { display: inline-block; }`);
