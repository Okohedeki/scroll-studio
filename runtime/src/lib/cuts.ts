/**
 * Film grammar between sections: the browser half of `transition:` (engine/cuts.py, runtime/src/lib/cuts.css).
 *
 * A join with a transition is a gap of scroll in which the section above is pinned at its last screen and the section
 * below is pinned at its first, one over the other. How far the gap has scrolled (k, 0 to 1) drives a cut between the two
 * pins: a hard cut, a dissolve, a wipe, an iris, a whip pan, a match cut on a shared shape, or an element carried
 * from one to the other. The pins are the sections' own wrappers, so it works for every section type. Scrolling is
 * never intercepted: the gap is plain scroll distance.
 */
import "./cuts.css";
import { clamp, isMobile, reducedMotion } from "./util";
import { matchFx, measureMatch } from "./cuts-match";
import { carryFx, endCarry, measureCarry } from "./cuts-carry";
import type { Cut, CutCfg, Fx, Layer, Metrics } from "./cuts-types";
export type { Cut, CutCfg, Fx, Layer, Metrics } from "./cuts-types";

const ease = (x: number) => x * x * (3 - 2 * x);
const win = (k: number, a: number, b: number) => clamp((k - a) / (b - a));
const quart = (t: number) => (t < 0.5 ? 8 * t ** 4 : 1 - 8 * (1 - t) ** 4);
const quartSpeed = (t: number) => (t < 0.5 ? 32 * t ** 3 : 32 * (1 - t) ** 3);   // derivative of quart, peak 4
const DRIFT = 0.035;   // the slow push either side of a cut: a cut on movement, so held pictures are not dead

const DIR: Record<string, [number, number]> = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };
/** CSS gradient angle for an edge travelling in a direction (left: the edge runs right to left). */
const CSS_ANGLE: Record<string, number> = { left: 270, right: 90, up: 0, down: 180 };

export const cssPx = (v: number) => v.toFixed(2) + "px";

// ---------------------------------------------------------------- effects

const MEASURE: Record<string, (c: Cut, m: Metrics) => void> = { match: measureMatch, carry: measureCarry };

const FX: Record<string, Fx> = {
  /** An instant cut at `at`, a beat of hold either side, a slow push on each so the beat is alive. */
  cut(k, c) {
    const at = c.cfg.at ?? 0.5;
    const early = k < at;
    return {
      a: { vis: early, t: `scale(${1 + DRIFT * ease(k / at)})` },
      b: { vis: !early, t: `scale(${1 + DRIFT * (1 - ease((k - at) / (1 - at)))})` },
      live: early ? "a" : "b",
    };
  },

  /** A held cross-dissolve. */
  dissolve(k) {
    const o = ease(k);
    return { a: { vis: o < 1 }, b: { vis: o > 0, o }, live: o > 0.5 ? "b" : "a" };
  },

  /** The next picture revealed along a line. */
  wipe(k, c, m) {
    const e = ease(k);
    const soft = c.cfg.soft ?? 0;
    const dir = c.cfg.direction || "left";
    const angle = c.cfg.angle != null ? c.cfg.angle + 90 : CSS_ANGLE[dir];
    const p = e * (1 + soft);
    const g = `linear-gradient(${angle}deg, #000 ${((p - soft) * 100).toFixed(2)}%, transparent ${(p * 100).toFixed(2)}%)`;
    return { a: { vis: e < 1 }, b: { vis: e > 0, mask: g, maskSize: `${m.W}px ${m.H}px` }, live: e > 0.5 ? "b" : "a" };
  },

  /** A circle opening from a point (or closing on this picture, the next behind it). */
  iris(k, c, m) {
    const e = ease(k);
    const o = c.cfg.origin || [0.5, 0.5];
    const x = o[0] * m.W, y = o[1] * m.H;
    const R = Math.hypot(Math.max(x, m.W - x), Math.max(y, m.H - y));
    const soft = c.cfg.soft ?? 0;
    const circle = (r: number, top: number) => {
      const cy = y - top;
      return soft > 0
        ? { mask: `radial-gradient(circle at ${cssPx(x)} ${cssPx(cy)}, #000 ${cssPx(Math.max(0, r * (1 - soft)))}, transparent ${cssPx(r)})` }
        : { clip: `circle(${cssPx(r)} at ${cssPx(x)} ${cssPx(cy)})` };
    };
    if (c.cfg.closing) {
      // this picture closes on the point (a hard edge), the next one waiting behind it
      const r = R * (1 - e);
      return { a: { vis: e < 1, clip: `circle(${cssPx(r)} at ${cssPx(x)} ${cssPx(y - c.topA)})` }, b: { vis: true },
               live: e > 0.5 ? "b" : "a", front: "a" };
    }
    const r = R * e * (1 + soft);
    return { a: { vis: e < 1 }, b: { vis: e > 0, ...circle(r, 0), maskSize: soft > 0 ? `${m.W}px ${m.H}px` : undefined }, live: e > 0.5 ? "b" : "a" };
  },

  /** A fast directional blur-pan: both pictures slide along `direction`, blurred along it by how fast they move. */
  whip(k, c, m) {
    const t = win(k, 0.12, 0.88);
    const e = quart(t);
    const [dx, dy] = DIR[c.cfg.direction || "left"];
    const blur = (c.cfg.blur ?? 1) * 0.05 * (quartSpeed(t) / 4) * (dx ? m.W : m.H) * (m.small ? 0.6 : 1);
    const lap = blur * 2;   // the pictures overlap by the blur, so the soft edges never show the page behind
    const A = { x: dx * m.W * e, y: dy * m.H * e }, B = { x: dx * (m.W * (e - 1) + lap * (1 - e)), y: dy * (m.H * (e - 1) + lap * (1 - e)) };
    return { a: { vis: e < 1, t: `translate(${cssPx(A.x)}, ${cssPx(A.y)})`, blur: [dx ? blur : 0, dy ? blur : 0] },
             b: { vis: e > 0, t: `translate(${cssPx(B.x)}, ${cssPx(B.y)})`, blur: [dx ? blur : 0, dy ? blur : 0] }, live: e > 0.5 ? "b" : "a" };
  },
};
FX.match = matchFx(FX, { ease, win });
FX.carry = carryFx(FX, { ease, win });

// ---------------------------------------------------------------- the runtime

let svg: SVGSVGElement | null = null;
const blurNodes: SVGFEGaussianBlurElement[] = [];
/** One SVG blur filter per layer, so the two pictures can be blurred by their own amounts along one axis. */
function blurFilter(i: number) {
  if (!svg) {
    svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "0"); svg.setAttribute("height", "0");
    svg.style.cssText = "position:absolute;width:0;height:0;pointer-events:none";
    svg.setAttribute("aria-hidden", "true");
    document.body.appendChild(svg);
  }
  while (blurNodes.length <= i) {
    const id = `ss-cut-blur-${blurNodes.length}`;
    const f = document.createElementNS("http://www.w3.org/2000/svg", "filter");
    f.setAttribute("id", id); f.setAttribute("x", "-5%"); f.setAttribute("y", "-5%"); f.setAttribute("width", "110%"); f.setAttribute("height", "110%");
    f.setAttribute("color-interpolation-filters", "sRGB");
    const g = document.createElementNS("http://www.w3.org/2000/svg", "feGaussianBlur");
    g.setAttribute("stdDeviation", "0 0");
    f.appendChild(g); svg.appendChild(f); blurNodes.push(g);
  }
  return `url(#ss-cut-blur-${i})`;
}

type Cache = Record<string, string>;
const cache = new WeakMap<HTMLElement, Cache>();
function put(el: HTMLElement, p: Record<string, string>) {
  let c = cache.get(el);
  if (!c) cache.set(el, (c = {}));
  for (const k in p) {
    if (c[k] === p[k]) continue;
    c[k] = p[k];
    (el.style as any)[k] = p[k];
  }
}
const RESET = { transform: "", filter: "", clipPath: "", maskImage: "", webkitMaskImage: "", maskSize: "", webkitMaskSize: "",
  maskRepeat: "", webkitMaskRepeat: "", maskPosition: "", webkitMaskPosition: "", opacity: "", transformOrigin: "", zIndex: "",
  willChange: "", pointerEvents: "" };

function touch(c: Cut, el: HTMLElement) { (c.touched ||= new Set()).add(el); }

function writeParts(c: Cut, L: Layer) {
  if (L.inner) {
    touch(c, L.inner.el);
    put(L.inner.el, { transform: L.inner.t, transformOrigin: L.inner.origin, willChange: "transform" });
  }
  if (L.fade) {
    for (const el of L.fade.els) {
      touch(c, el);
      const on = L.fade.o < 0.999;
      el.classList.toggle("ss-cut-faded", on);
      if (on) el.style.setProperty("--cut-fade", L.fade.o.toFixed(3));
    }
  }
}

function write(el: HTMLElement, L: Layer, blurIdx: number, extra: Record<string, string> = {}) {
  const p: Record<string, string> = { ...extra };
  p.transform = L.t || "";
  p.opacity = L.o != null && L.o < 1 ? L.o.toFixed(3) : "";
  p.clipPath = L.clip || "";
  const mask = L.mask || "";
  p.maskImage = p.webkitMaskImage = mask;
  p.maskSize = p.webkitMaskSize = mask ? L.maskSize || "100% 100%" : "";
  p.maskRepeat = p.webkitMaskRepeat = mask ? "no-repeat" : "";
  p.maskPosition = p.webkitMaskPosition = mask ? L.maskPos || "0 0" : "";
  if (L.blur && (L.blur[0] > 0.3 || L.blur[1] > 0.3)) {
    const f = blurFilter(blurIdx);
    blurNodes[blurIdx].setAttribute("stdDeviation", `${L.blur[0].toFixed(2)} ${L.blur[1].toFixed(2)}`);
    p.filter = f;
  } else p.filter = "";
  if (L.origin) p.transformOrigin = L.origin;
  else if (cache.get(el)?.transformOrigin) p.transformOrigin = "";
  put(el, p);
  el.classList.toggle("ss-cut-off", L.vis === false);
}

/** An element's layout height in CSS px, fractions included, whatever transform is on it. */
const layoutHeight = (el: HTMLElement) => parseFloat(getComputedStyle(el).height) || el.offsetHeight;

export interface CutsApi { update(): void; land(el: Element): number | null; docTop(el: Element): number | null; holding(el: Element): 1 | 0 | null; cuts: Cut[] }
export function makeCuts(): CutsApi | null {
  const raw = document.getElementById("ss-cuts");
  if (!raw || reducedMotion) return null;
  const cfgs: CutCfg[] = JSON.parse(raw.textContent || "[]");
  const cuts: Cut[] = [];
  for (const cfg of cfgs) {
    const wIn = document.querySelector<HTMLElement>(`[data-cut-in="${cfg.n}"]`);
    const wOut = document.querySelector<HTMLElement>(`[data-cut-out="${cfg.n}"]`);
    const pinB = wIn?.querySelector<HTMLElement>(":scope > .ss-cutpin--in") || null;
    const pinA = wOut?.querySelector<HTMLElement>(":scope > .ss-cutpin--out") || null;
    const gap = wIn?.querySelector<HTMLElement>(":scope > .ss-cutgap") || null;
    if (!wIn || !wOut || !pinA || !pinB || !gap) continue;
    cuts.push({ cfg, wIn, wOut, pinA, pinB, gap, secA: pinA.querySelector("section"), secB: pinB.querySelector("section"),
      state: "", k: -1, topA: 0, hA: 0, live: "", data: {} });
  }
  if (!cuts.length) return null;
  document.documentElement.classList.add("ss-cuts-on");

  // the pin above holds by its bottom edge, so it needs to know its own height
  const ro = new ResizeObserver((es) => {
    for (const e of es) {
      const el = e.target as HTMLElement;
      el.style.setProperty("--cut-h", layoutHeight(el) + "px");
    }
    dirty = true;
  });
  let dirty = true;
  for (const c of cuts) { ro.observe(c.pinA); c.pinA.style.setProperty("--cut-h", layoutHeight(c.pinA) + "px"); }
  addEventListener("resize", () => { dirty = true; });

  function reset(c: Cut) {
    for (const el of c.touched || []) {
      cache.delete(el);
      el.style.transform = el.style.transformOrigin = el.style.willChange = "";
      el.style.removeProperty("--cut-fade");
      el.classList.remove("ss-cut-faded");
    }
    c.touched?.clear();
    for (const el of [c.pinA, c.pinB]) {
      cache.delete(el);
      for (const k in RESET) (el.style as any)[k] = "";
      el.classList.remove("ss-cut-off");
    }
    endCarry(c);
  }

  function update() {
    const m: Metrics = { W: document.documentElement.clientWidth, H: innerHeight, small: isMobile() };
    for (const c of cuts) {
      const L = c.gap.offsetHeight;
      const top = c.wIn.getBoundingClientRect().top;
      const pos = L > 0 ? clamp(-top / L) : 0;                       // how far the gap has scrolled
      const hold = c.cfg.hold ?? 0.15;                               // held still at each end
      const k = clamp((pos - hold) / (1 - 2 * hold));                // how far the cut has played
      const state = pos <= 0 ? "before" : pos >= 1 ? "after" : "during";
      if (state === c.state && (state !== "during" || (k === c.k && !dirty))) continue;
      const entering = c.state !== "during" && state === "during";
      c.state = state; c.k = k;
      if (state !== "during") {
        reset(c);
        if (state === "before") c.pinB.classList.add("ss-cut-off"); else c.pinA.classList.add("ss-cut-off");
        continue;
      }
      if (entering || dirty) {
        // the held layout, measured with the cut's own styles off
        const keepA = c.pinA.style.cssText, keepB = c.pinB.style.cssText;
        reset(c);
        const ra = c.pinA.getBoundingClientRect();
        c.topA = ra.top; c.hA = ra.height;
        c.data = {};
        MEASURE[c.cfg.type]?.(c, m);
        c.pinA.style.cssText = keepA; c.pinB.style.cssText = keepB;
        cache.delete(c.pinA); cache.delete(c.pinB);
      }
      const fx = FX[c.cfg.type] || FX.cut;
      const r = fx(k, c, m);
      const front = r.front === "a";
      writeParts(c, r.a); writeParts(c, r.b);
      write(c.pinA, r.a, c.cfg.n * 2, { zIndex: front ? "2" : "", willChange: "transform, clip-path", pointerEvents: r.live === "a" ? "" : "none" });
      write(c.pinB, r.b, c.cfg.n * 2 + 1, { zIndex: front ? "1" : "", willChange: "transform, clip-path", pointerEvents: r.live === "b" ? "" : "none" });
      c.live = r.live;
    }
    dirty = false;
  }

  /** The scroll position at which a section's own first screen is on show, for anchor links and ?p= jumps. */
  function land(el: Element): number | null {
    const w = el.closest<HTMLElement>("[data-cut-in]");
    if (!w) return null;
    const c = cuts.find((x) => x.wIn === w);
    if (!c) return null;
    return w.getBoundingClientRect().top + scrollY + c.gap.offsetHeight;
  }

  /** While a cut is moving a section (scaled or shifted, so its rectangle is not where scrolling put it), what it is held at:
   * 1 for the end of the section above, 0 for the start of the section below, null otherwise. Scroll-driven players keep
   * their progress while this is set instead of measuring the section. It is null in the held beats at either end of the
   * cut, where the section is exactly where scrolling put it, so players settle there. */
  function holding(el: Element): 1 | 0 | null {
    for (const c of cuts) {
      if (c.state !== "during" || c.k <= 0 || c.k >= 1) continue;
      if (c.pinA.contains(el)) return 1;
      if (c.pinB.contains(el)) return 0;
    }
    return null;
  }

  /** Where an element's own top sits in the document with no cut holding it: after the cut that leads into it. */
  function docTop(el: Element): number | null {
    const w = el.closest<HTMLElement>(".ss-cutw");
    if (!w) return null;
    let outer: HTMLElement = w;
    for (let p = w.parentElement?.closest<HTMLElement>(".ss-cutw"); p; p = p.parentElement?.closest<HTMLElement>(".ss-cutw")) outer = p;
    const gap = outer.dataset.cutIn != null ? outer.querySelector<HTMLElement>(":scope > .ss-cutgap")?.offsetHeight || 0 : 0;
    return outer.getBoundingClientRect().top + scrollY + gap;
  }

  (window as any).__ssCuts = { cuts: cfgs, positions: () => cuts.map((c) => {
    const L = c.gap.offsetHeight;
    const y = c.wIn.getBoundingClientRect().top + scrollY;
    return { n: c.cfg.n, type: c.cfg.type, label: c.cfg.label, from: y, to: y + L, length: L };
  }) };
  return { update, land, docTop, holding, cuts };
}
