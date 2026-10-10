/**
 * Bauhaus: you compose a poster. One fixed stage holds the same primitives for the whole page (a red circle, a black
 * bar, a yellow triangle, a blue square, a half-disc, a dot and two rules). Every section is one or more designed
 * resting states of that stage; scrolling holds a state, then moves every primitive rigidly (power-curve ease with a
 * little overshoot) to its place in the next one. The circle that is the sun behind the headline becomes a feature,
 * then the pie chart, rides the timeline's diagonal bar, and finally is the button. Section changes are giant
 * primitive wipes (the square, circle or triangle grows to become the next poster's ground) or a black bar sweep.
 * Headline words slide out from behind the poster's left edge and lock; everything else slides along a grid axis.
 * Reduced motion: each state is a static poster; posters swap with a short crossfade.
 */
import { $$, onFrame, reduced } from "./_kit";

const COL = { paper: "#efe8da", blue: "#1f4e9c", red: "#be1e2d", yellow: "#f2c230", black: "#111111" };
type Bg = keyof typeof COL;
type Id = "h" | "q" | "t" | "b" | "c" | "d" | "r1" | "r2";
const IDS: Id[] = ["h", "q", "t", "b", "c", "d", "r1", "r2"];
const SHAPE_COL: Record<Id, Bg> = { c: "red", q: "blue", t: "yellow", b: "black", h: "black", d: "black", r1: "black", r2: "black" };
interface Sh { x: number; y: number; w: number; h: number; r: number; o: number; pie: number }
type Comp = Record<Id, Sh>;
interface Geo { W: number; H: number; L: number; top: number; Wst: number; Hst: number; S: number; P: boolean; X: (f: number) => number; Y: (f: number) => number }
interface Slide { el: HTMLElement; dir: string; dist: number; last: string }
interface Word { el: HTMLElement; dx: number; last: string }
interface Sec {
  el: HTMLElement; kind: string; n: number; first: number; poster: HTMLElement;
  words: Word[]; slides: Slide[]; items: HTMLElement[]; side: string;
  stats: { v: number; kind: "pie" | "squares" | "bar" | "zero"; max: number }[];
  bgs: Bg; top: number; hs: number; cutAfter: boolean; link: HTMLElement | null;
}
interface St { sec: Sec; sub: number; bg: Bg; comp: Comp }

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease2 = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const outCubic = (t: number) => 1 - Math.pow(1 - t, 3);
/** power ease in-out with a small overshoot at the end: mechanical, then a rigid settle */
const shapeEase = (t: number) => {
  const e = ease2(t);
  return t > 0.6 && t < 1 ? e + 0.06 * Math.sin(Math.PI * ((t - 0.6) / 0.4)) : e;
};
const HOLD = 0.38;

export default function start() {
  const secEls = $$<HTMLElement>("main section.bh");
  if (!secEls.length) return;
  const root = document.documentElement;

  // ------------------------------------------------------------ stage
  const stage = document.createElement("div");
  stage.className = "bh-stage";
  stage.setAttribute("aria-hidden", "true");
  const bgEl = document.createElement("div"); bgEl.className = "bh-stage__bg";
  const wipeEl = document.createElement("div"); wipeEl.className = "bh-stage__wipe";
  stage.append(bgEl, wipeEl);
  const shapes = {} as Record<Id, HTMLElement>;
  for (const id of IDS) { const s = document.createElement("i"); s.className = `bh-sh bh-sh--${id}`; stage.appendChild(s); shapes[id] = s; }
  const band = document.createElement("div"); band.className = "bh-band"; band.setAttribute("aria-hidden", "true");
  document.body.prepend(stage);
  document.body.appendChild(band);

  // ------------------------------------------------------------ sections
  const navLinks = $$<HTMLAnchorElement>(".bh-index__links a");
  const defaultBg: Record<string, Bg> = { hero: "paper", intro: "blue", features: "paper", product: "yellow", stats: "paper", timeline: "paper", quote: "red", faq: "paper", cta: "paper" };
  let prevBg: Bg | null = null;
  const secs: Sec[] = secEls.map((el) => {
    const kind = el.dataset.bh || "intro";
    const poster = el.querySelector<HTMLElement>(".bh-poster")!;
    let items: HTMLElement[] = [];
    if (kind === "features") items = $$(".bh-feat", el);
    if (kind === "stats") items = $$(".bh-stat", el);
    if (kind === "timeline") items = $$(".bh-step", el);
    const n = Math.max(1, items.length && (kind === "features" || kind === "stats" || kind === "timeline") ? items.length : 1);
    let bg: Bg = defaultBg[kind] || "paper";
    if (bg !== "paper" && bg === prevBg) bg = "paper";
    prevBg = bg;
    // words of the head, each wrapped so it can slide out from behind the left edge
    const words: Word[] = [];
    el.querySelectorAll<HTMLElement>(".bh-words").forEach((h) => splitWords(h).forEach((w) => words.push({ el: w, dx: 0, last: "" })));
    const slides = $$<HTMLElement>(".bh-slide", poster).map((s) => ({ el: s, dir: s.dataset.from || "b", dist: 0, last: "" }));
    let stats: Sec["stats"] = [];
    if (kind === "stats") {
      const vals = items.map((li) => parseFloat(li.dataset.v || "") );
      const units = items.map((li) => (li.dataset.unit || "").trim());
      const maxBar = Math.max(1, ...vals.filter((v, i) => isFinite(v) && units[i] !== "%" && v > 24));
      stats = vals.map((v, i) => {
        const pct = units[i] === "%" || /%$/.test(items[i].dataset.v || "");
        let k: "pie" | "squares" | "bar" | "zero" = "bar";
        if (!isFinite(v)) k = "bar";
        else if (pct && v >= 0 && v <= 100) k = "pie";
        else if (v === 0) k = "zero";
        else if (Number.isInteger(v) && v > 0 && v <= 24) k = "squares";
        return { v: isFinite(v) ? v : 1, kind: k, max: maxBar };
      });
      items.forEach((li, i) => {
        const fig = li.querySelector<HTMLElement>(".bh-stat__fig")!;
        const st = stats[i];
        const count = st.kind === "squares" ? st.v : st.kind === "bar" ? 11 : 0;
        for (let k = 0; k < count; k++) fig.appendChild(document.createElement("i"));
      });
    }
    const link = navLinks.find((a) => el.id && a.getAttribute("href") === "#" + el.id) || null;
    return { el, kind, n, first: 0, poster, words, slides, items, side: el.classList.contains("bh--left") ? "left" : "right", stats, bgs: bg, top: 0, hs: 1, cutAfter: false, link };
  });
  // a section the style doesn't draw (a gallery, a scene...) between two posters: no transition across it
  secs.forEach((s, i) => {
    let n = s.el.parentElement!.matches("main") ? s.el.nextElementSibling : s.el.parentElement!.nextElementSibling;
    s.cutAfter = !!n && i < secs.length - 1 && !(n.matches("section.bh") || !!n.querySelector?.(":scope > section.bh"));
  });

  const legendMarks = new Map<Sec, HTMLElement>();
  secs.filter((s) => s.kind === "stats").forEach((s) => {
    const m = document.createElement("i"); m.className = "bh-legend-mark"; m.setAttribute("aria-hidden", "true");
    s.poster.appendChild(m); legendMarks.set(s, m);
  });

  root.classList.add("bh-live");
  let states: St[] = [];
  let g: Geo;

  // ------------------------------------------------------------ compositions
  function geo(): Geo {
    const W = innerWidth, H = innerHeight, P = W <= 760 || W / H < 0.8;
    const L = P ? 0 : 64, top = P ? 56 : 0, Wst = W - L, Hst = H - top;
    return { W, H, L, top, Wst, Hst, P, S: Math.min(Wst, Hst), X: (f) => L + f * Wst, Y: (f) => top + f * Hst };
  }
  function compose(sec: Sec, sub: number, bg: Bg): Comp {
    const P = g.P, S = g.S;
    const mirror = sec.kind === "product" && sec.side === "left";
    const mx = (x: number) => (mirror ? 1 - x : x);
    const sq = (x: number, y: number, s: number, r = 0, o = 1): Sh => ({ x: g.X(mx(x)), y: g.Y(y), w: s * S, h: s * S, r: mirror ? -r : r, o, pie: 1 });
    const bar = (x: number, y: number, w: number, h: number, r = 0): Sh => ({ x: g.X(mx(x)), y: g.Y(y), w: w * g.Wst, h: h * S, r: mirror ? -r : r, o: 1, pie: 1 });
    const rule = (x: number, y: number, w: number, px: number, r = 0): Sh => ({ x: g.X(mx(x)), y: g.Y(y), w: w * g.Wst, h: px, r, o: 1, pie: 1 });
    const vrule = (x: number, y: number, h: number, px: number): Sh => ({ x: g.X(mx(x)), y: g.Y(y), w: px, h: h * g.Hst, r: 0, o: 1, pie: 1 });
    let c: Comp;
    switch (sec.kind) {
      case "hero":
        c = P ? { c: sq(0.7, 0.2, 0.6), t: sq(0.18, 0.31, 0.3), q: sq(0.92, 0.43, 0.12), b: bar(0.5, 0.415, 1.2, 0.03, -10), h: sq(0.1, 0.05, 0.18, 180), r1: vrule(0.035, 0.72, 0.42, 8), r2: rule(0.5, 0.985, 0.6, 5), d: sq(0.42, 0.07, 0.06) }
          : { c: sq(0.75, 0.42, 0.64), q: sq(0.935, 0.85, 0.12), t: sq(0.575, 0.83, 0.22), b: bar(0.74, 0.76, 0.6, 0.042, 24), h: sq(0.9, 0.12, 0.2, 180), r1: vrule(0.072, 0.42, 0.44, 10), r2: rule(0.3, 0.94, 0.44, 6), d: sq(0.53, 0.16, 0.055) };
        break;
      case "intro":
        c = P ? { c: sq(0.82, 0.1, 0.18), t: sq(0.72, 0.27, 0.36, 90), q: sq(0.5, 0.2, 0.1, 0, 0), b: bar(0.38, 0.4, 0.66, 0.028), h: sq(0.12, 0.97, 0.18), r1: vrule(0.95, 0.7, 0.5, 6), r2: rule(0.28, 0.035, 0.4, 5), d: sq(0.3, 0.2, 0.06) }
          : { c: sq(0.86, 0.2, 0.2), q: sq(0.5, 0.5, 0.1, 0, 0), t: sq(0.83, 0.66, 0.44, 90), b: bar(0.28, 0.66, 0.4, 0.036), h: sq(0.1, 0.92, 0.2), r1: vrule(0.94, 0.5, 0.8, 8), r2: rule(0.3, 0.09, 0.4, 6), d: sq(0.66, 0.3, 0.05) };
        break;
      case "features": {
        const n = sec.items.length;
        c = P ? { c: sq(0.88, 0.1, 0.1), t: sq(0.7, 0.08, 0.08), q: sq(0.94, 0.25, 0.06), h: sq(1.2, 0.3, 0.12, 270), d: sq(1.15, 0.36, 0.04), b: bar(0.5, 0.565, 1, 0.012), r1: rule(0.5, 0.995, 1, 5), r2: vrule(0.035, 0.18, 0.2, 6) }
          : { c: sq(0.93, 0.1, 0.12), t: sq(0.62, 0.1, 0.1), q: sq(0.95, 0.5, 0.08), h: sq(0.93, 0.1, 0.15, 270), d: sq(0.56, 0.1, 0.04), b: { x: g.X(0.535), y: g.Y(0.47), w: 0.022 * S, h: 0.8 * g.Hst, r: 0, o: 1, pie: 1 }, r1: rule(0.77, 0.965, 0.38, 5), r2: vrule(0.072, 0.3, 0.34, 10) };
        const keys: Id[] = ["t", "q", "c", "h", "d"];
        for (let j = 0; j < Math.min(n, 5); j++) {
          const id = keys[j];
          if (j === sub) c[id] = P ? sq(0.72, 0.4, 0.3, 0) : sq(0.77, 0.44, 0.54, 0);
          else { const p = legendSpot(n, j); c[id] = { x: p.cx, y: p.cy, w: p.s, h: p.s, r: id === "t" ? 90 : 0, o: 1, pie: 1 }; }
        }
        break;
      }
      case "product":
        c = P ? { c: sq(0.62, 0.21, 0.5), t: sq(0.3, 0.3, 0.1, 0, 0), q: sq(0.12, 0.37, 0.1, 45), b: bar(0.5, 0.995, 0.8, 0.025), h: sq(0.12, 0.08, 0.16, 90), r1: vrule(0.035, 0.75, 0.3, 6), r2: rule(0.2, 0.22, 0.3, 5), d: sq(0.25, 0.3, 0.05) }
          : { c: sq(0.76, 0.4, 0.52), t: sq(0.5, 0.5, 0.1, 0, 0), q: sq(0.935, 0.86, 0.12, 45), b: bar(0.36, 0.95, 0.5, 0.032), h: sq(0.58, 0.1, 0.15, 90), r1: vrule(0.072, 0.5, 0.4, 10), r2: rule(0.44, 0.06, 0.26, 6), d: sq(0.6, 0.86, 0.05) };
        break;
      case "stats": {
        const st = sec.stats[sub] || { v: 1, kind: "bar", max: 1 };
        c = P ? { c: sq(0.88, 0.06, 0.12), b: bar(0.5, 0.99, 0.9, 0.02), t: sq(0.9, 0.47, 0.1), q: sq(0.1, 0.05, 0.08), h: sq(0.1, 0.13, 0.12, 180), d: sq(0.3, 0.05, 0.04), r1: vrule(0.035, 0.62, 0.2, 6), r2: rule(0.5, 0.42, 0.9, 4) }
          : { c: sq(0.93, 0.13, 0.13), b: bar(0.27, 0.95, 0.42, 0.03), t: sq(0.935, 0.85, 0.13), q: sq(0.06, 0.1, 0.08), h: sq(0.44, 0.08, 0.12, 180), d: sq(0.38, 0.88, 0.04), r1: vrule(0.072, 0.62, 0.24, 10), r2: rule(0.7, 0.8, 0.5, 5) };
        if (st.kind === "pie") { c.c = P ? sq(0.6, 0.22, 0.46) : sq(0.7, 0.45, 0.66); c.c.pie = clamp(st.v / 100); }
        if (st.kind === "bar") {
          const w = (P ? 0.8 : 0.48) * g.Wst * clamp(st.v / st.max, 0.06, 1);
          const x0 = g.X(P ? 0.1 : 0.44);
          c.b = { x: x0 + w / 2, y: g.Y(P ? 0.26 : 0.52), w, h: 0.09 * S, r: 0, o: 1, pie: 1 };
        }
        if (st.kind === "zero") c.r1 = P ? rule(0.5, 0.3, 0.8, 7) : rule(0.7, 0.6, 0.42, 7);
        break;
      }
      case "timeline": {
        const { p0, p1 } = diag();
        const len = Math.hypot(p1.x - p0.x, p1.y - p0.y), ang = (Math.atan2(p1.y - p0.y, p1.x - p0.x) * 180) / Math.PI;
        const node = nodeAt(sec.items.length, sub);
        c = P ? { t: sq(0.9, 0.97, 0.1, 180), q: sq(1.2, 0.5, 0.06, 45), h: sq(-0.2, 0.9, 0.12), d: sq(0.84, 0.36, 0.04), r1: vrule(0.035, 0.12, 0.12, 6), r2: rule(0.7, 0.995, 0.5, 4) } as Comp
          : { t: sq(0.92, 0.86, 0.15, 180), q: sq(0.6, 0.92, 0.07, 45), h: sq(0.07, 0.95, 0.12), d: sq(0.4, 0.1, 0.04), r1: vrule(0.072, 0.18, 0.2, 10), r2: rule(0.82, 0.965, 0.3, 5) } as Comp;
        c.b = { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2, w: len * 1.08, h: (P ? 0.04 : 0.05) * S, r: ang, o: 1, pie: 1 };
        const cs = (P ? 0.15 : 0.1) * S;
        c.c = { x: node.x, y: node.y, w: cs, h: cs, r: 0, o: 1, pie: 1 };
        break;
      }
      case "quote":
        c = P ? { c: sq(0.5, 0.5, 0.2, 0, 0), q: sq(0.1, 0.94, 0.1), t: sq(0.86, 0.08, 0.16, 180), b: bar(0.5, 0.985, 0.9, 0.02), h: sq(0.9, 0.94, 0.14), d: sq(0.8, 0.2, 0.05), r1: vrule(0.035, 0.5, 0.4, 6), r2: rule(0.3, 0.06, 0.3, 5) }
          : { c: sq(0.5, 0.5, 0.2, 0, 0), q: sq(0.08, 0.87, 0.12), t: sq(0.9, 0.17, 0.22, 180), b: bar(0.5, 0.94, 0.84, 0.024), h: sq(0.92, 0.82, 0.2), d: sq(0.85, 0.42, 0.05), r1: vrule(0.072, 0.5, 0.5, 10), r2: rule(0.62, 0.07, 0.28, 6) };
        break;
      case "faq":
        c = P ? { c: sq(0.88, 0.1, 0.12), b: bar(0.5, 0.995, 1, 0.015), t: sq(0.7, 0.1, 0.08, 270), q: sq(1.2, 0.5, 0.05), h: sq(-0.2, 0.5, 0.1), d: sq(0.78, 0.16, 0.03), r1: vrule(0.035, 0.15, 0.15, 6), r2: rule(1.3, 0.5, 0.2, 5) }
          : { c: sq(0.2, 0.74, 0.28), b: { x: g.X(0.48), y: g.Y(0.5), w: 0.02 * S, h: 0.86 * g.Hst, r: 0, o: 1, pie: 1 }, t: sq(0.14, 0.47, 0.1, 270), q: sq(0.34, 0.9, 0.09), h: sq(0.07, 0.93, 0.13), d: sq(0.37, 0.6, 0.04), r1: vrule(0.072, 0.2, 0.2, 10), r2: rule(0.2, 0.42, 0.22, 6) };
        break;
      case "cta":
      default:
        c = P ? { b: bar(0.33, 0.7, 0.52, 0.05), t: sq(0.63, 0.7, 0.14, 90), c: sq(0.8, 0.7, 0.36), q: sq(0.06, 0.7, 0.06, 45), h: sq(0.15, 0.645, 0.08), d: sq(0.15, 0.755, 0.035), r1: rule(0.1, 0.63, 0.1, 5, -35), r2: rule(0.1, 0.77, 0.1, 5, 35) }
          : { b: bar(0.4, 0.64, 0.48, 0.06), t: sq(0.67, 0.64, 0.17, 90), c: sq(0.82, 0.64, 0.28), q: sq(0.1, 0.64, 0.08, 45), h: sq(0.19, 0.565, 0.11), d: sq(0.19, 0.72, 0.045), r1: rule(0.12, 0.55, 0.09, 6, -35), r2: rule(0.12, 0.73, 0.09, 6, 35) };
        break;
    }
    // a primitive in the ground's own colour has become the ground: hide it
    for (const id of IDS) if (SHAPE_COL[id] === bg) c[id] = { ...c[id], o: 0 };
    return c;
  }
  function legendSpot(n: number, j: number) {
    const s = (g.P ? 0.07 : 0.05) * g.S;
    const step = g.P ? Math.min(0.13, 0.5 / Math.max(1, n - 1)) : Math.min(0.13, 0.36 / Math.max(1, n - 1));
    return { cx: g.X((g.P ? 0.08 : 0.585) + j * step), cy: g.Y(g.P ? 0.4 : 0.9), s };
  }
  function diag() {
    return g.P ? { p0: { x: g.X(0.06), y: g.Y(0.94) }, p1: { x: g.X(0.94), y: g.Y(0.56) } }
      : { p0: { x: g.X(0.05), y: g.Y(0.76) }, p1: { x: g.X(0.96), y: g.Y(0.16) } };
  }
  function nodeAt(n: number, j: number) {
    const { p0, p1 } = diag();
    const k = n > 1 ? 0.1 + (0.8 * j) / (n - 1) : 0.5;
    return { x: lerp(p0.x, p1.x, k), y: lerp(p0.y, p1.y, k) };
  }

  // ------------------------------------------------------------ layout (on load and resize)
  function layout() {
    g = geo();
    states = [];
    secs.forEach((s) => {
      s.first = states.length;
      s.el.style.setProperty("--n", String(s.n));
      for (let k = 0; k < s.n; k++) states.push({ sec: s, sub: k, bg: s.bgs, comp: compose(s, k, s.bgs) });
    });
    // reset live transforms, then measure the resting layout
    secs.forEach((s) => {
      s.words.forEach((w) => { w.el.style.transform = ""; w.last = ""; });
      s.slides.forEach((sl) => { sl.el.style.transform = ""; sl.last = ""; });
    });
    secs.forEach((s) => {
      const r = s.el.getBoundingClientRect();
      s.top = r.top + scrollY;
      s.hs = r.height / s.n;
      s.words.forEach((w) => {
        const head = w.el.closest<HTMLElement>(".bh-words")!;
        const hr = head.getBoundingClientRect(), wr = w.el.getBoundingClientRect();
        w.dx = wr.right - hr.left + 24;
      });
      s.slides.forEach((sl) => {
        const rr = sl.el.getBoundingClientRect();
        sl.dist = sl.dir === "l" ? rr.right + 30 : sl.dir === "r" ? g.W - rr.left + 30 : sl.dir === "t" ? rr.bottom + 30 : g.H - rr.top + 30;
      });
      if (s.kind === "features") {
        const box = s.poster.querySelector<HTMLElement>(".bh-feats")!.getBoundingClientRect();
        s.el.style.setProperty("--fw", Math.min(box.width, 560) + "px");
        s.items.forEach((li) => { li.style.setProperty("--fw", Math.min(box.width, 560) + "px"); });
        (s as any).copy = { x: box.left - g.L, y: box.top - g.top };
      }
      if (s.kind === "timeline") {
        s.items.forEach((li, j) => {
          const node = nodeAt(s.items.length, j);
          const no = li.querySelector<HTMLElement>(".bh-step__no")!;
          no.style.left = node.x - g.L + "px"; no.style.top = node.y - g.top + "px";
          const txt = li.querySelector<HTMLElement>(".bh-step__txt")!;
          if (g.P) { txt.style.left = g.Wst * 0.06 + "px"; txt.style.top = g.Hst * 0.35 + "px"; }
          else {
            const tw = Math.min(330, g.W * 0.42);
            txt.style.left = Math.min(node.x - g.L + 40, g.Wst - tw - 30) + "px";
            txt.style.top = node.y - g.top + 90 + "px";
          }
        });
      }
      if (s.kind === "stats") {
        s.items.forEach((li, j) => {
          const st = s.stats[j];
          const fig = li.querySelector<HTMLElement>(".bh-stat__fig")!;
          const cells = [...fig.children] as HTMLElement[];
          if (st.kind === "squares") {
            const cols = Math.ceil(Math.sqrt(st.v * 1.6)), size = (g.P ? 0.085 : 0.075) * g.S, gap = size * 0.28;
            const rows = Math.ceil(st.v / cols);
            const cx = g.X(g.P ? 0.62 : 0.7) - g.L, cy = g.Y(g.P ? 0.22 : 0.46) - g.top;
            cells.forEach((cell, k) => {
              const col = k % cols, row = Math.floor(k / cols);
              cell.style.width = cell.style.height = size + "px";
              cell.style.left = cx + (col - (cols - 1) / 2) * (size + gap) - size / 2 + "px";
              cell.style.top = cy + (row - (rows - 1) / 2) * (size + gap) - size / 2 + "px";
            });
          } else if (st.kind === "bar") {
            const x0 = g.X(g.P ? 0.1 : 0.44) - g.L, span = (g.P ? 0.8 : 0.48) * g.Wst, y = g.Y(g.P ? 0.26 : 0.52) - g.top + 0.045 * g.S + 10;
            cells.forEach((cell, k) => {
              cell.style.width = "4px"; cell.style.height = (k % 5 === 0 ? 22 : 12) + "px";
              cell.style.left = x0 + (span * k) / (cells.length - 1) - 2 + "px"; cell.style.top = y + "px";
              cell.style.background = "#111";
            });
          }
        });
      }
    });
    lastKey = "";
  }

  // ------------------------------------------------------------ frame
  const t0 = performance.now();
  const startedAtTop = scrollY < 10;
  let lastKey = "";
  const shapeLast: Record<string, string> = {};
  let lastY = -1, idleSince = performance.now(), settling = false, userInput = 0;
  ["wheel", "touchstart", "keydown", "pointerdown"].forEach((ev) => addEventListener(ev, () => { userInput = performance.now(); settling = false; }, { passive: true }));

  function locate(y: number): { i: number; f: number } {
    for (let k = 0; k < secs.length; k++) {
      const s = secs[k];
      if (y < s.top) return { i: s.first, f: 0 };   // in a gap before this poster (a section the style doesn't draw)
      if (y < s.top + s.n * s.hs) {
        const local = (y - s.top) / s.hs, j = Math.floor(local);
        return { i: s.first + j, f: local - j };
      }
    }
    return { i: states.length - 1, f: 0 };
  }

  function render(y: number) {
    let { i, f } = locate(y);
    let A = states[i], B: St | undefined = states[i + 1];
    let t = 0;
    if (B && !(A.sub === A.sec.n - 1 && A.sec.cutAfter) && f > HOLD) t = (f - HOLD) / (1 - HOLD);
    if (reduced && t >= 0.5) { A = B!; B = states[i + 2]; t = 0; }
    if (!B) t = 0;
    const intro = startedAtTop && !reduced ? clamp((performance.now() - t0) / 1300) : 1;

    // primitives
    const te = shapeEase(t);
    for (const id of IDS) {
      const a = A.comp[id], b = B ? B.comp[id] : a;
      const x = lerp(a.x, b.x, te), yy = lerp(a.y, b.y, te), w = Math.max(0, lerp(a.w, b.w, te)), h = Math.max(0, lerp(a.h, b.h, te));
      const r = lerp(a.r, b.r, te), o = t < 0.5 ? a.o : b.o;
      let pie = 1;
      if (id === "c") {
        if (b.pie < 1 && a.pie >= 1) pie = t < 0.5 ? 1 - ease2(t * 2) * (1 - 0) : ease2((t - 0.5) * 2) * b.pie;
        else if (b.pie < 1 && a.pie < 1) pie = t < 0.5 ? lerp(a.pie, 0, ease2(t * 2)) : lerp(0, b.pie, ease2((t - 0.5) * 2));
        else if (a.pie < 1) pie = lerp(a.pie, 1, ease2(t));
        else pie = 1;
        if (t === 0) pie = a.pie;
      }
      // shapes enter the very first poster by sliding in from the stage edges
      let ix = 0;
      if (intro < 1 && i === 0) ix = (1 - outCubic(clamp(intro * 1.4 - IDS.indexOf(id) * 0.05))) * (x > g.W / 2 ? g.W - x + w : -(x + w));
      const key = `${x.toFixed(1)},${yy.toFixed(1)},${w.toFixed(1)},${h.toFixed(1)},${r.toFixed(2)},${o},${pie.toFixed(3)},${ix.toFixed(1)}`;
      if (shapeLast[id] === key) continue;
      shapeLast[id] = key;
      const el = shapes[id];
      el.style.width = w + "px"; el.style.height = h + "px";
      el.style.transform = `translate(${(x - w / 2 + ix).toFixed(1)}px, ${(yy - h / 2).toFixed(1)}px) rotate(${r.toFixed(2)}deg)`;
      el.style.opacity = String(o);
      if (id === "c") el.style.background = pie >= 0.999 ? "" : `conic-gradient(#be1e2d 0 ${(pie * 360).toFixed(2)}deg, #f2c230 0)`;
    }

    // ground and wipes
    const key = `${i}|${t.toFixed(4)}`;
    if (key !== lastKey) {
      lastKey = key;
      bgEl.style.background = COL[A.bg];
      if (B && t > 0 && B.bg !== A.bg) {
        const e = ease2(t);
        wipeEl.style.background = COL[B.bg];
        wipeEl.style.clipPath = wipeShape(A, B.bg, e);
      } else wipeEl.style.clipPath = "circle(0px at 0 0)";
      if (B && t > 0 && B.sec !== A.sec && B.bg === A.bg) band.style.clipPath = bandShape(ease2(t));
      else band.style.clipPath = "polygon(0 0, 0 0, 0 0)";
    }

    // posters
    for (const s of secs) {
      let p = 0, bg: Bg = s.bgs;
      if (s === A.sec) p = B && B.sec !== s ? 1 - clamp(t / 0.45) : 1;
      if (B && s === B.sec && B.sec !== A.sec) p = clamp((t - 0.55) / 0.45);
      if (s === A.sec && i === 0) p *= intro;
      const on = p > 0.001;
      if (s.poster.classList.contains("is-on") !== on) s.poster.classList.toggle("is-on", on);
      if (s.poster.dataset.bg !== bg) s.poster.dataset.bg = bg;
      if (s.link) s.link.classList.toggle("is-on", (t < 0.5 ? A.sec : B?.sec) === s);
      if (!on && !s.poster.dataset.wasOn) continue;
      s.poster.dataset.wasOn = on ? "1" : "";
      drawPoster(s, reduced ? (on ? 1 : 0) : p, A, B, t);
    }
  }

  function wipeShape(A: St, to: Bg, e: number): string {
    const src: Id | null = to === "blue" ? "q" : to === "red" ? "c" : to === "yellow" ? "t" : null;
    const far = (x: number, y: number) => Math.max(Math.hypot(x, y), Math.hypot(g.W - x, y), Math.hypot(x, g.H - y), Math.hypot(g.W - x, g.H - y));
    if (src) {
      const s = A.comp[src];
      const R = far(s.x, s.y) * 1.05 * e + (s.w / 2) * (1 - e);
      if (src === "c") return `circle(${R.toFixed(1)}px at ${s.x.toFixed(1)}px ${s.y.toFixed(1)}px)`;
      if (src === "q") {
        const a = R * 1.0, rad = (s.r * Math.PI) / 180, cs = Math.cos(rad), sn = Math.sin(rad);
        const pts = [[-a, -a], [a, -a], [a, a], [-a, a]].map(([px, py]) => `${(s.x + px * cs - py * sn).toFixed(1)}px ${(s.y + px * sn + py * cs).toFixed(1)}px`);
        return `polygon(${pts.join(",")})`;
      }
      const a = R * 2.1, rad = (s.r * Math.PI) / 180;
      const pts = [0, 120, 240].map((d) => { const an = rad + ((d - 90) * Math.PI) / 180; return `${(s.x + Math.cos(an) * a).toFixed(1)}px ${(s.y + Math.sin(an) * a).toFixed(1)}px`; });
      return `polygon(${pts.join(",")})`;
    }
    const R = far(0, g.H) * e;
    return `circle(${R.toFixed(1)}px at 0px ${g.H}px)`;
  }
  function bandShape(e: number): string {
    const k = 0.577 * g.H, bw = Math.max(g.W, g.H) * 0.34;
    const c = lerp(-bw - 10, g.W + k + 10, e);
    return `polygon(${c}px 0, ${c + bw}px 0, ${c + bw - k}px ${g.H}px, ${c - k}px ${g.H}px)`;
  }

  function drawPoster(s: Sec, p: number, A: St, B: St | undefined, t: number) {
    const nw = s.words.length, dw = nw > 1 ? Math.min(0.07, 0.45 / (nw - 1)) : 0, span = Math.max(0.3, 1 - dw * (nw - 1) - 0.1);
    s.words.forEach((w, j) => {
      const k = outCubic(clamp((p - j * dw) / span));
      const tr = k >= 1 ? "" : `translateX(${(-(1 - k) * w.dx).toFixed(1)}px)`;
      if (tr !== w.last) { w.el.style.transform = tr; w.last = tr; }
    });
    s.slides.forEach((sl, j) => {
      const k = outCubic(clamp((p - 0.18 - j * 0.07) / 0.55));
      const d = (1 - k) * sl.dist;
      const tr = k >= 1 ? "" : sl.dir === "l" ? `translateX(${-d}px)` : sl.dir === "r" ? `translateX(${d}px)` : sl.dir === "t" ? `translateY(${-d}px)` : `translateY(${d}px)`;
      if (tr !== sl.last) { sl.el.style.transform = tr; sl.last = tr; }
    });
    if (!s.items.length) { if (s.kind === "cta") drawCta(s, p, A, B, t); return; }
    // which item is active: blended across sub-states of the same section
    const act = s.items.map((_, j) => {
      if (A.sec === s && B && B.sec === s) return j === A.sub ? 1 - ease2(t) : j === B.sub ? ease2(t) : 0;
      if (A.sec === s) return j === A.sub ? 1 : 0;
      if (B && B.sec === s) return j === B.sub ? 1 : 0;
      return 0;
    });
    const enter = outCubic(clamp((p - 0.2) / 0.6));
    if (s.kind === "features") {
      const copy = (s as any).copy as { x: number; y: number };
      s.items.forEach((li, j) => {
        const a = act[j];
        const spot = legendSpot(s.items.length, j);
        const lx = spot.cx + spot.s * 0.75 - g.L, ly = spot.cy - spot.s * 0.55 - g.top;
        const sc = lerp(g.P ? 0.26 : 0.3, 1, a);
        const x = lerp(lx, copy.x, a) + (1 - enter) * (g.W - lerp(lx, copy.x, a) + 40), yy = lerp(ly, copy.y, a);
        li.style.transform = `translate(${x.toFixed(1)}px, ${yy.toFixed(1)}px) scale(${sc.toFixed(4)})`;
        li.style.setProperty("--a", clamp((a - 0.75) / 0.25).toFixed(3));
        li.style.zIndex = a > 0.5 ? "2" : "1";
        const h3 = li.querySelector<HTMLElement>("h3");
        if (h3 && g.P) h3.style.opacity = a > 0.5 ? "1" : "0";
        else if (h3) h3.style.opacity = "";
      });
    } else if (s.kind === "stats") {
      const n = s.items.length;
      const bigX = g.X(g.P ? 0.06 : 0.42) - g.L, bigY = g.Y(g.P ? 0.36 : 0.27) - g.top;
      let markX = 0, markY = 0;
      s.items.forEach((li, j) => {
        const a = act[j];
        const v = li.querySelector<HTMLElement>(".bh-stat__v")!;
        const lgX = g.X(g.P ? 0.06 + (0.88 * j) / n : 0.44 + (0.52 * j) / n) - g.L, lgY = g.Y(g.P ? 0.9 : 0.885) - g.top;
        const sc = lerp(g.P ? 0.3 : 0.17, 1, a);
        const x = lerp(lgX, bigX, a) + (1 - enter) * (g.W - lgX + 40), yy = lerp(lgY, bigY, a);
        v.style.transform = `translate(${x.toFixed(1)}px, ${yy.toFixed(1)}px) scale(${sc.toFixed(4)})`;
        li.style.setProperty("--a", clamp((a - 0.6) / 0.4).toFixed(3));
        li.style.zIndex = a > 0.5 ? "2" : "1";
        if (a > 0.5) { markX = lgX - 18; markY = lgY + 8; }
        // squares pop in one by one as the stat becomes active (rigid steps, no easing)
        const cells = [...li.querySelectorAll<HTMLElement>(".bh-stat__fig i")];
        const st = s.stats[j];
        if (st.kind === "squares") cells.forEach((cell, k) => { cell.style.transform = a * cells.length > k + 0.3 ? "" : "scale(0)"; });
      });
      const m = legendMarks.get(s);
      if (m) m.style.transform = `translate(${markX}px, ${markY}px)`;
    } else if (s.kind === "timeline") {
      s.items.forEach((li, j) => {
        const a = act[j];
        li.classList.toggle("is-on", a > 0.5);
        li.classList.toggle("is-shown", a > 0.02);
        li.style.setProperty("--a", (clamp((a - 0.5) / 0.5) * enter).toFixed(3));
        const no = li.querySelector<HTMLElement>(".bh-step__no")!;
        const k = outCubic(clamp((p - 0.1 - j * 0.08) / 0.5));
        no.style.transform = k >= 1 ? "" : `scale(${k.toFixed(3)})`;
      });
    }
  }

  function drawCta(s: Sec, p: number, A: St, B: St | undefined, t: number) {
    const go = s.poster.querySelector<HTMLElement>(".bh-go");
    if (!go) return;
    const st = A.sec === s ? A : B && B.sec === s ? B : null;
    if (!st) return;
    const c = st.comp.c;
    // the label rides the red circle; it shows once the circle has docked
    const a = A.sec === s && (!B || B.sec === s) ? 1 : clamp((t - 0.7) / 0.3);
    go.style.setProperty("--d", c.w + "px");
    go.style.transform = `translate(${(c.x - c.w / 2 - g.L).toFixed(1)}px, ${(c.y - c.h / 2 - g.top).toFixed(1)}px)`;
    go.style.setProperty("--a", (a * (p > 0.5 ? 1 : 0)).toFixed(3));
  }

  // gentle settle: when the visitor stops between two designed states, finish the move to the nearer one
  function settle(y: number) {
    if (reduced || settling) return;
    const { i, f } = locate(y);
    const A = states[i];
    if (!A || !states[i + 1] || f <= HOLD + 0.02 || f >= 0.995) return;
    if (A.sub === A.sec.n - 1 && A.sec.cutAfter) return;
    const s = A.sec, base = s.top + (i - s.first) * s.hs;
    const target = f < HOLD + (1 - HOLD) * 0.5 ? base + s.hs * (HOLD - 0.02) : base + s.hs + 1;
    const from = y, t0s = performance.now(), dur = 420;
    settling = true;
    const step = (now: number) => {
      if (!settling) return;
      const k = clamp((now - t0s) / dur);
      scrollTo(0, from + (target - from) * ease2(k));
      if (k < 1) requestAnimationFrame(step); else settling = false;
    };
    requestAnimationFrame(step);
  }

  layout();
  addEventListener("resize", () => { layout(); render(scrollY); });
  document.fonts?.ready.then(() => { layout(); render(scrollY); });
  onFrame(({ y }) => {
    const now = performance.now();
    if (y !== lastY) { lastY = y; idleSince = now; }
    else if (!settling && now - idleSince > 240 && now - userInput > 240 && now - idleSince < 300) settle(y);
    render(y);
  });
}

/** Wrap each word of a heading (inline markup kept) so it can move on its own. */
function splitWords(el: HTMLElement): HTMLElement[] {
  const out: HTMLElement[] = [];
  const label = el.textContent || "";
  const walk = (node: Node) => {
    if (node.nodeType === 3) {
      const frag = document.createDocumentFragment();
      (node.textContent || "").split(/(\s+)/).forEach((part) => {
        if (!part) return;
        if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
        const w = document.createElement("span");
        w.className = "bh-w";
        w.textContent = part;
        frag.appendChild(w);
        out.push(w);
      });
      node.parentNode!.replaceChild(frag, node);
    } else if (node.nodeType === 1 && (node as Element).tagName !== "BR") [...node.childNodes].forEach(walk);
  };
  [...el.childNodes].forEach(walk);
  el.setAttribute("aria-label", label);
  return out;
}
