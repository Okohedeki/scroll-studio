/**
 * The element engine: every scene's copy, in every layout, from the layout model the compiler writes (`.ss-layout`,
 * engine/layout.py): which step each element is, the window of the scene's progress it shows over, and how it enters
 * and leaves. Overlay captions turn on and off by their windows; split and cards steps are measured where they sit on
 * the screen as they scroll past. Either way the scene learns the step on screen by its index in the spec, not by where
 * its element happens to be in the page.
 */
import { clamp, follow } from "./util";
import type { SectionData } from "./types";

export type Motion = "fade" | "rise" | "wipe" | "type-on" | "scale" | "none";

/** One step in the layout model, in page order. `show` is its window (split/cards: its share of the scroll). */
export interface LayoutElement { step: number; show: [number, number]; enter?: Motion; exit?: Motion }

/** The scene's elements in page order: the compiler's `.ss-layout`, or, for markup that does not carry it, the steps
 * in page order with the windows the markup or the section data give. */
export function readElements(section: HTMLElement, data: Pick<SectionData, "steps">): LayoutElement[] {
  const tag = section.querySelector<HTMLScriptElement>("script.ss-layout");
  if (tag) {
    try { return JSON.parse(tag.textContent || "{}").elements || []; } catch { /* fall through to the markup */ }
  }
  const caps = [...section.querySelectorAll<HTMLElement>(".ss-caption")];
  const n = caps.length || section.querySelectorAll(".ss-step").length;
  return Array.from({ length: n }, (_, i) => {
    const c = caps[i], at = data.steps?.[i]?.at;
    const show: [number, number] = c?.dataset.from != null ? [+c.dataset.from, +(c.dataset.to ?? 1)] : at ? [at[0], at[1]] : [0, 1];
    return { step: i, show };
  });
}

/** Words as spans that can rise or appear one by one, each delayed `pace` seconds after the one before (a caption's
 * rise, or its words typed on). Returns how many there are. */
export function splitWords(el: HTMLElement, pace = 0.045) {
  let i = 0;
  const walk = (node: Node) => {
    if (node.nodeType === 3) {
      const frag = document.createDocumentFragment();
      (node.textContent || "").split(/(\s+)/).forEach((part) => {
        if (!part) return;
        if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
        const w = document.createElement("span"); w.className = "ss-w";
        const s = document.createElement("span"); s.textContent = part;
        s.style.transitionDelay = (0.06 + i++ * pace).toFixed(3) + "s";
        w.appendChild(s); frag.appendChild(w);
      });
      node.parentNode!.replaceChild(frag, node);
    } else [...node.childNodes].forEach(walk);
  };
  [...el.childNodes].forEach(walk);
  return i;
}

interface Caption { el: HTMLElement; step: number; from: number; to: number; state: string }
interface Card { el: HTMLElement; step: number; val: number; moves: boolean }

export class Elements {
  readonly list: LayoutElement[];
  readonly captions: Caption[] = [];
  readonly cards: Card[] = [];
  /** per-step local progress of the split/cards steps, eased (what a player sees as `steps`) */
  readonly stepVals: number[];
  lastActive = -1;

  constructor(section: HTMLElement, data: Pick<SectionData, "steps">) {
    this.list = readElements(section, data);
    section.querySelectorAll<HTMLElement>(".ss-caption").forEach((el, k) => {
      const pace = el.dataset.enter === "type-on" ? 0.11 : 0.045;      // typed on: about nine words a second
      el.querySelectorAll<HTMLElement>(".ss-split-words").forEach((t) => splitWords(t, pace));
      const e = this.list[k];
      this.captions.push({ el, step: e ? e.step : k, from: e ? e.show[0] : +el.dataset.from!, to: e ? e.show[1] : +el.dataset.to!, state: "idle" });
    });
    section.querySelectorAll<HTMLElement>(".ss-step").forEach((el, k) => {
      const e = this.list[k];
      const moves = !!(el.dataset.enter || el.dataset.exit);
      if (moves && (el.dataset.enter === "type-on" || el.dataset.exit === "type-on")) {
        const title = el.querySelector<HTMLElement>(".ss-h1, .ss-h2");
        if (title) {
          el.style.setProperty("--n", String(splitWords(title)));
          title.querySelectorAll<HTMLElement>(".ss-w > span").forEach((s, i) => s.style.setProperty("--i", String(i)));
        }
      }
      this.cards.push({ el, step: e ? e.step : k, val: 0, moves });
    });
    this.stepVals = this.cards.map(() => 0);
  }

  /** Overlay captions: each is idle before its window, on inside it (both ends included) and off after it. Returns the
   * step of the last caption on (-1 when none). */
  windows(p: number): number {
    let active = -1;
    for (const c of this.captions) {
      const next = p >= c.from && p <= c.to ? "on" : p > c.to ? "off" : "idle";
      if (next !== c.state) {
        c.el.classList.toggle("ss-on", next === "on");
        c.el.classList.toggle("ss-off", next === "off");
        c.state = next;
      }
      if (next === "on") active = c.step;
    }
    return active;
  }

  /** Split and cards steps: each one's progress is how far the middle of the screen has gone through it (eased); the
   * scene's is their average weighted by `length`. A step is active while the middle is inside it; its emphasis (`--on`)
   * and, for a step with its own motion (`enter`, `exit`), how far it has entered and left (`--in`, `--out`, 0-1) follow
   * its position. */
  measure(lengths: number[]): { p: number; active: number } {
    let total = 0, done = 0, active = -1;
    this.cards.forEach((c, i) => {
      const r = c.el.getBoundingClientRect();
      const at = (innerHeight * 0.5 - r.top) / Math.max(1, r.height);   // how far the middle of the screen is through it
      const target = clamp(at);
      this.stepVals[i] += (target - this.stepVals[i]) * follow;
      if (Math.abs(target - this.stepVals[i]) < 5e-4) this.stepVals[i] = target;
      const on = target > 0 && target < 1;
      c.el.classList.toggle("ss-active", on);
      // card emphasis is a function of scroll position, not a timed fade, so it never trails a fast scroll: full while
      // the middle of the screen is inside the step, fading out over a tenth of the step either side (from the unclamped
      // position: clamped, it never leaves 1)
      c.el.style.setProperty("--on", (clamp((at + 0.1) / 0.1) * clamp((1.1 - at) / 0.1)).toFixed(3));
      if (c.moves) {
        // a step's own motion: it enters as its top rises from 90% to 55% down the screen and leaves as its bottom
        // rises from 60% to 20% (the card is pinned in between)
        c.el.style.setProperty("--in", clamp((innerHeight * 0.9 - r.top) / (innerHeight * 0.35)).toFixed(3));
        c.el.style.setProperty("--out", clamp((r.bottom - innerHeight * 0.2) / (innerHeight * 0.4)).toFixed(3));
      }
      if (on) active = c.step;
      const h = lengths[c.step] || 1;
      total += h; done += this.stepVals[i] * h;
    });
    this.lastActive = active;
    return { p: total ? done / total : 0, active };
  }
}
