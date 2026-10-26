/**
 * Scroll Studio runtime. Mounts a player into every [data-scene] section and drives it from scroll.
 * Pages are complete without this script; it adds the motion.
 */
import Lenis from "lenis";
import "./styles.css";
import { clamp, debugP, follow, params, reducedMotion, scaleAt, themeTokens } from "./lib/util";
import { makeBlocks } from "./lib/blocks";
import { Elements } from "./lib/elements";
import type { FrameState, Player, PlayerFactory, SectionData } from "./lib/types";

document.documentElement.classList.add("js");
// A style's own experience (runtime/src/styles/<style>.ts): its scroll mechanics, transitions and interactions.
const EXPERIENCES = import.meta.glob<{ default: () => void }>("./styles/[a-z]*.ts");
const styleName = document.documentElement.dataset.style;
if (styleName && EXPERIENCES[`./styles/${styleName}.ts`]) {
  EXPERIENCES[`./styles/${styleName}.ts`]().then((m) => m.default())
    .finally(() => { document.documentElement.dataset.ssStyle = "ready"; });
} else if (styleName) document.documentElement.dataset.ssStyle = "ready";

const PLAYERS: Record<string, () => Promise<{ default: PlayerFactory }>> = {
  film: () => import("./players/video"),
  sequence: () => import("./players/frames"),
  artwork: () => import("./players/artwork"),
  scene3d: () => import("./players/scene3d"),
  parallax: () => import("./players/parallax"),
  type: () => import("./players/type"),
  vector: () => import("./players/vector"),
  chart: () => import("./players/chart"),
  map: () => import("./players/map"),
  splat: () => import("./players/splat"),
  code: () => import("./players/code"),
  showroom: () => import("./players/showroom"),
  diorama: () => import("./players/diorama"),
  inside: () => import("./players/frames"),
  light: () => import("./players/light"),
};

let mx = 0, my = 0;
addEventListener("pointermove", (e) => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; }, { passive: true });
const t0 = performance.now();

// ---------------------------------------------------------------- scene controller
class Scene {
  el: HTMLElement;
  type: string;
  data: SectionData;
  cfg: any;
  player: Player | null = null;
  track: HTMLElement;
  /** the scene's copy: captions and steps, their windows and motions (lib/elements.ts) */
  els: Elements;
  stepEls: HTMLElement[];
  stepVals: number[];
  p = 0;
  hud: Record<string, any> = {};
  scaleOverride: string | null = null;
  loaded = 0;
  onProgress: () => void = () => {};

  constructor(el: HTMLElement) {
    this.el = el;
    this.type = el.dataset.scene!;
    this.cfg = JSON.parse(el.querySelector<HTMLScriptElement>(".ss-config")!.textContent || "{}");
    this.data = JSON.parse(el.querySelector<HTMLScriptElement>(".ss-section")!.textContent || "{}");
    this.track = el.querySelector<HTMLElement>(".ss-track") || el;
    this.els = new Elements(el, this.data);
    this.stepEls = this.els.cards.map((c) => c.el);
    this.stepVals = this.els.stepVals;
    const q = (s: string) => el.querySelectorAll<HTMLElement>(s);
    this.hud = {
      fields: [...q("[data-field]")], events: [...q(".ss-events li")], clock: el.querySelector("[data-clock]"),
      bar: el.querySelector("[data-bar]"), scale: el.querySelector("[data-scale]"), cue: el.querySelector(".ss-cue"),
      outro: el.querySelector(".ss-outro"), pnum: el.querySelector("[data-pnum]"), ptitle: el.querySelector("[data-ptitle]"),
      pbar: el.querySelector("[data-pbar]"), ppct: el.querySelector("[data-ppct]"),
    };
  }

  async mount() {
    const load = PLAYERS[this.type];
    if (!load) return;
    try {
      const factory = (await load()).default;
      this.player = await factory(this.cfg, {
        section: this.el, visual: this.el.querySelector<HTMLElement>(".ss-visual")!, data: this.data,
        setScale: (label) => { this.scaleOverride = label; },
        progress: (f) => { this.loaded = Math.max(this.loaded, Math.min(1, f)); this.onProgress(); },
      });
      this.el.classList.add("ss-ready");
    } catch (err) {
      console.error(`[scroll-studio] ${this.type} player failed`, err);
      this.el.classList.add("ss-failed");
    }
    this.loaded = 1;
    this.onProgress();
  }

  near(): boolean {
    const r = this.el.getBoundingClientRect();
    return r.bottom > -innerHeight * 0.5 && r.top < innerHeight * 1.5;
  }

  rawProgress(): number {
    const r = this.track.getBoundingClientRect();
    return clamp(-r.top / Math.max(1, r.height - innerHeight));
  }

  tick(t: number) {
    if (!this.near()) return;
    const layout = this.data.layout;
    let active = -1;
    const held = cuts?.holding(this.el) ?? null;   // a cut is playing on this section (it moves its rectangle): progress stays where it was
    if (held != null) {
      active = this.els.lastActive;
    } else if (layout === "overlay") {
      const raw = this.rawProgress();
      this.p += (raw - this.p) * follow;
      if (Math.abs(raw - this.p) < 1e-4) this.p = raw;
    } else {
      const m = this.els.measure(this.data.steps.map((s) => s.length));
      this.p = m.p;
      active = m.active;
    }
    const p = this.p;
    const on = this.els.windows(p);       // the step whose caption is on screen (by its index in the spec)
    if (on >= 0) active = on;
    this.updateHud(p, active);
    const state: FrameState = { p, steps: this.stepVals, active, t, mx, my };
    this.player?.update(state);
  }

  updateHud(p: number, active: number) {
    const h = this.data.hud, H = this.hud;
    if (H.cue) H.cue.style.opacity = String(1 - clamp(p / 0.03));
    if (H.outro) H.outro.style.opacity = String(clamp((p - 0.975) / 0.025) * 0.85);
    if (h.kind === "telemetry") {
      const zero = h.clock?.zero ?? 0;
      const flight = clamp((p - zero) / (1 - zero));
      h.fields.forEach((f, i) => {
        const v = (f.from ?? 0) + (f.to - (f.from ?? 0)) * Math.pow(flight, f.curve ?? 1.5);
        if (H.fields[i]) H.fields[i].textContent = f.grouping ? Math.round(v).toLocaleString("en-US") : v.toFixed(f.decimals ?? 1);
      });
      H.events.forEach((li: HTMLElement) => li.classList.toggle("ss-done", p >= +li.dataset.at!));
      if (h.clock && H.clock) {
        const { start, end } = h.clock;
        const secs = p < zero ? start * (1 - p / Math.max(zero, 1e-6)) : flight * end;
        const s = Math.abs(secs), pad = (n: number) => String(Math.floor(n)).padStart(2, "0");
        H.clock.textContent = `${secs < 0 ? "-" : "+"}${pad(s / 3600)}:${pad((s % 3600) / 60)}:${pad(s % 60)}`;
      }
      if (H.bar) H.bar.style.transform = `scaleX(${p})`;
    } else if (h.kind === "scale" && H.scale) {
      const intro = this.data.steps.filter((s) => s.intro).length;
      const z = this.stepVals.slice(intro).reduce((a, b) => a + b, 0);
      H.scale.textContent = this.scaleOverride ?? scaleAt(h.scales, z);
    } else if (h.kind === "progress") {
      const st = active >= 0 ? this.data.steps[active] : null;
      const real = st && !st.intro;
      const done = p >= 0.999;
      if (H.pnum) H.pnum.textContent = real ? st!.kicker?.match(/\d+/)?.[0] ?? String(active) : done ? "✓" : "—";
      if (H.ptitle) H.ptitle.textContent = real ? plainText(st!.title || "") : done ? "Complete" : (h.scales[0] || "");
      if (H.pbar) H.pbar.style.transform = `scaleX(${p})`;
      if (H.ppct) H.ppct.textContent = String(Math.round(p * 100));
    }
  }
}

// ---------------------------------------------------------------- boot
const scenes = [...document.querySelectorAll<HTMLElement>("[data-scene]")].map((el) => new Scene(el));

const nav = document.getElementById("ss-nav");
const updateBlocks = makeBlocks((el) => cuts?.holding(el) != null);
// Film grammar between sections (`transition:`, lib/cuts.ts): loaded only by pages that carry cuts.
let cuts: import("./lib/cuts").CutsApi | null = null;
if (document.getElementById("ss-cuts")) import("./lib/cuts").then((m) => { cuts = m.makeCuts(); });
// The nav reads in the colours of the section under it: a dark film on a light site gets a dark nav, and back.
const surfaced = [...document.querySelectorAll<HTMLElement>("main [class*='ss-surface-']")]
  .filter((el) => el.matches("section, .ss-panel, .ss-backdrop") && !el.closest(".ss-caption--block, .ss-card--block"));   // not a block shown as a step
let navSurface = "";

/** A title's words without its markup (`<em>` and the like), for a `textContent` slot. Tags are removed until none are
 *  left, so a nested `<<em>em>` can't leave one behind. */
function plainText(html: string): string {
  let text = html;
  let before;
  do {
    before = text;
    text = text.replace(/<[^<>]*>/g, "");
  } while (text !== before);
  return text;
}

function surfaceUnderNav() {
  if (!nav) return;
  const y = nav.offsetHeight / 2;
  let found = "";
  for (const el of cuts ? [...surfaced].reverse() : surfaced) {   // during a cut the section on top is the later one
    if (cuts && el.closest(".ss-cut-off")) continue;
    const r = el.getBoundingClientRect();
    if (r.top <= y && r.bottom > y) { found = (el.className.match(/ss-surface-(\w+)/) || [])[1] || ""; break; }
  }
  if (found !== navSurface) {
    if (navSurface) nav.classList.remove("ss-surface-" + navSurface);
    if (found) nav.classList.add("ss-surface-" + found);
    navSurface = found;
  }
}
function frame() {
  const t = (performance.now() - t0) / 1000;
  cuts?.update();
  for (const s of scenes) s.tick(t);
  updateReveals();
  updateBlocks();
  nav?.classList.toggle("ss-solid", scrollY > 40);
  surfaceUnderNav();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// Resizing a canvas clears it; redraw in the same task so a blank frame is never painted
addEventListener("resize", () => {
  const t = (performance.now() - t0) / 1000;
  scenes.forEach((s) => { if (s.player?.resize) { s.player.resize(); s.tick(t); } });
});

// Smooth scrolling (off for reduced motion and for ?p= captures); started once loading finishes.
// `scroll.speed` in the spec (window.__ssScroll) paces it: the smoothing catches up that much faster, anchor
// scrolls take that much less time, and the scroll-driven reveals finish over that much less travel.
const pace = Math.max(0.25, Number((window as any).__ssScroll?.speed) || 1);
let lenis: Lenis | null = null;
function startSmoothScroll() {
  if (reducedMotion || debugP !== null || lenis) return;
  lenis = new Lenis({ lerp: Math.min(0.5, (themeTokens.follow ?? 0.1) * pace) });
  (window as any).__ssLenis = lenis;   // players that scroll the page to a place (the one-take page's rail)
  const raf = (time: number) => { lenis!.raf(time); requestAnimationFrame(raf); };
  requestAnimationFrame(raf);
}

// ---------------------------------------------------------------- loading screen
// Every scene loads its media completely (videos downloaded, frames decoded, tiles drawn) before the page
// unlocks, so scrolling never outruns the assets. Progress = average of the scenes plus fonts and images.
const loaderEl = document.getElementById("ss-loader");
const loaderCfg = (window as any).__ssLoader || { maxWait: 45, minTime: 0.6 };
const extras: Promise<unknown>[] = [document.fonts?.ready ?? Promise.resolve()];
document.querySelectorAll<HTMLElement>(".ss-cta__bg").forEach((el) => {
  const m = el.style.backgroundImage.match(/url\(["']?([^"')]+)/);
  if (m) extras.push(new Promise((r) => { const im = new Image(); im.onload = im.onerror = r; im.src = m[1]; }));
});
let extrasDone = 0;
extras.forEach((p) => p.then(() => { extrasDone++; renderProgress(); }));
function renderProgress() {
  if (!loaderEl) return;
  const total = scenes.length + extras.length;
  const f = total ? (scenes.reduce((a, s) => a + s.loaded, 0) + extrasDone) / total : 1;
  (loaderEl.querySelector(".ss-loader__bar i") as HTMLElement).style.transform = `scaleX(${f})`;
  loaderEl.querySelector(".ss-loader__pct span")!.textContent = String(Math.round(f * 100));
}
scenes.forEach((s) => { s.onProgress = renderProgress; });
const t0load = performance.now();
const everything = Promise.all([...scenes.map((s) => s.mount()), ...extras]);
const giveUp = new Promise((r) => setTimeout(r, loaderCfg.maxWait * 1000));
Promise.race([everything, giveUp]).then(async () => {
  const wait = loaderCfg.minTime * 1000 - (performance.now() - t0load);
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  renderProgress();
  if (debugP === null) scrollTo(0, 0);
  document.documentElement.classList.remove("ss-loading");
  document.documentElement.dataset.ssReady = "1";   // snapshots and recordings wait for this
  if (loaderEl) { loaderEl.classList.add("ss-leaving"); setTimeout(() => loaderEl.remove(), 900); }
  startSmoothScroll();
  if (debugP !== null) jump?.();
});
document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]').forEach((a) => a.addEventListener("click", (e) => {
  const id = a.getAttribute("href")!;
  if (id.length < 2) return;
  const target = document.querySelector(id);
  if (!target) return;
  e.preventDefault();
  const settled = cuts?.docTop(target);   // a section in a cut is reached where it sits with no cut holding it (after the cut that leads into it)
  if (settled != null) { if (lenis) lenis.scrollTo(settled, { duration: 1.4 / pace }); else scrollTo(0, settled); }
  else if (lenis) lenis.scrollTo(target as HTMLElement, { duration: 1.4 / pace });
  else target.scrollIntoView();
}));

// ?p=0.5&s=<scene id>: jump so that scene sits at that progress (snapshots, recordings, UI preview)
let jump: (() => void) | null = null;
if (debugP !== null) {
  const target = debugP;
  const go = () => {
    const id = params.get("s");
    const sc = (id && scenes.find((s) => s.el.id === id)) || scenes[0];
    if (!sc) return;
    const top = cuts?.docTop(sc.el) ?? sc.el.getBoundingClientRect().top + scrollY;
    if (sc.data.layout === "overlay") {
      scrollTo(0, top + (sc.track.offsetHeight - innerHeight) * target);
    } else {
      const first = sc.stepEls[0], last = sc.stepEls[sc.stepEls.length - 1];
      if (!first) return;
      const a = first.getBoundingClientRect().top + scrollY - innerHeight * 0.5;
      const b = last.getBoundingClientRect().bottom + scrollY - innerHeight * 0.5;
      scrollTo(0, a + (b - a) * target);
    }
  };
  jump = go;
  addEventListener("load", go);
  setTimeout(go, 300);
}

// ---------------------------------------------------------------- reveals + count-ups
// Driven by scroll position, not timers: text is fully in by the time it is a fifth of the way up the
// viewport, however fast the page is scrolled, and count-ups finish before the number reaches mid-screen.
const reveals = [...document.querySelectorAll<HTMLElement>(".ss-reveal")].map((el, i) => ({
  el, lag: (i % 4) * 0.25, k: -1,
  counts: [...el.querySelectorAll<HTMLElement>("[data-count]")].map((v) => ({
    v, end: parseFloat(v.dataset.count!), sup: v.querySelector("sup")?.outerHTML || "",
    dec: (v.dataset.count!.split(".")[1] || "").length, k: -1,
    group: /\d,\d{3}/.test(v.textContent || ""),          // written with thousands separators: count up with them
  })),
}));
const enterShare = themeTokens.enter ?? 0.2;     // theme.motion.enter: the share of the screen a block arrives over
let revealY = NaN, revealH = NaN;
function updateReveals() {
  if (scrollY === revealY && innerHeight === revealH) return;
  revealY = scrollY; revealH = innerHeight;
  for (const r of reveals) {
    const top = r.el.getBoundingClientRect().top;
    const k = reducedMotion ? 1 : clamp((innerHeight * 0.98 - top) / (innerHeight * enterShare / pace) - r.lag);
    if (k !== r.k) {
      r.k = k;
      r.el.style.opacity = k.toFixed(3);
      r.el.style.transform = k < 1 ? `translateY(${((1 - k) * 22).toFixed(1)}px)` : "none";
    }
    for (const c of r.counts) {
      const kc = reducedMotion ? 1 : clamp((innerHeight * 0.95 - top) / (innerHeight * 0.4 / pace));
      if (kc === c.k) continue;
      c.k = kc;
      const n = c.end * (1 - Math.pow(1 - kc, 3));
      c.v.innerHTML = (c.group ? n.toLocaleString("en-US", { minimumFractionDigits: c.dec, maximumFractionDigits: c.dec })
        : n.toFixed(c.dec)) + c.sup;
    }
  }
}
reveals.forEach((r) => r.el.classList.add("ss-in"));
document.querySelectorAll<HTMLVideoElement>(".ss-tile video").forEach((v) => {
  const tile = v.closest(".ss-tile")!;
  tile.addEventListener("mouseenter", () => v.play().catch(() => {}));
  tile.addEventListener("mouseleave", () => v.pause());
});

// ---------------------------------------------------------------- cinemagraphs (image inputs with `cinemagraph:`)
if (document.querySelector("[data-cine]")) import("./lib/cinemagraph").then((m) => m.start());
// ---------------------------------------------------------------- living details (image inputs with `live:`)
if (document.querySelector("[data-live]")) import("./players/liveStill").then((m) => m.start());
