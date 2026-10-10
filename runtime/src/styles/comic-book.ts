/**
 * Comic book: reading a page with your eyes guided.
 *
 * Desktop: every page with two or more panels pins, and a camera (a transform on the page sheet) steps through its
 * panels in Z-order: the page arrives whole, the camera frames panel 1, 2, ... (each held for a beat, then a short
 * eased move), the live panel's caption slides in and its balloons pop in reading order, panels already read dim
 * to about 60%, and at the end the camera pulls back to the whole page (the closure moment) before the page turns
 * over on its left edge to show the next one, already waiting underneath.
 * Phones (and "read as strip"): a vertical webtoon strip; each panel pops as it reaches the middle of the screen.
 * Reduced motion: whole printed pages with every balloon showing, ordinary scroll.
 */
import { $, $$, onFrame, onSeen, reduced } from "./_kit";
import { clamp } from "../lib/util";

type Box = { x: number; y: number; w: number; h: number };
type Cam = { cx: number; cy: number; z: number };
type Page = {
  sec: HTMLElement; sheet: HTMLElement; panels: HTMLElement[]; n: number;
  track?: HTMLElement; stage?: HTMLElement; turner?: HTMLElement;
  boxes: Box[]; W: number; H: number; lead: number; turn: boolean; travel: number;
  cam: Cam | null; frame: number; closed: boolean;
};

const U = 0.8;          // screens of scroll per camera step
const TURN = 0.75;      // screens of scroll for the page turn
const HOLD = 0.42;      // share of each step the frame holds before the camera moves on

const smooth = (a: number, b: number, v: number) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };

export default function start(): void {
  const root = document.documentElement;
  const phone = matchMedia("(max-width: 760px)");
  const store = { get: () => { try { return localStorage.getItem("cb-read"); } catch { return null; } },
                  set: (v: string) => { try { localStorage.setItem("cb-read", v); } catch { /* private mode */ } } };

  const all = $$<HTMLElement>(".cb-page");
  const pages: Page[] = all.filter((s) => s.hasAttribute("data-guided")).map((sec) => {
    const sheet = $<HTMLElement>(".cb-sheet", sec)!;
    const panels = $$<HTMLElement>(":scope > .cb-panel", sheet);
    return { sec, sheet, panels, n: panels.length, boxes: [], W: 1, H: 1, lead: 0, turn: false, travel: 0, cam: null, frame: -1, closed: false };
  }).filter((p) => p.n >= 2);

  // ---------------------------------------------------------------- arrivals
  let stageShake: HTMLElement | null = null;
  function pop(panel: HTMLElement, shakeHost?: HTMLElement) {
    if (panel.classList.contains("is-pop")) return;
    panel.classList.add("is-pop");
    if (reduced) return;
    // the SFX slam (and the first starburst) land with a 2-3 frame camera shake: the only shake on the page
    const slam = panel.querySelector(".cb-sfx--slam, .cb-burst--slam");
    const host = shakeHost || stageShake;
    if (slam && host) setTimeout(() => host.animate(
      [{ transform: "translate(0,0)" }, { transform: "translate(4px,-3px)" }, { transform: "translate(-3px,3px)" }, { transform: "translate(2px,-1px)" }, { transform: "translate(0,0)" }],
      { duration: 110, easing: "steps(4, end)" }), slam.classList.contains("cb-sfx--slam") ? 680 : 260);
  }

  if (reduced) {
    // printed pages: everything showing, nothing moves (no .cb-js, so nothing is hidden)
    chapters();
    return;
  }
  root.classList.add("cb-js");
  $$(".cb-splash").forEach((s) => requestAnimationFrame(() => { s.classList.add("is-pop"); $$(".cb-panel", s).forEach((el) => el.classList.add("is-pop")); }));

  // ---------------------------------------------------------------- modes
  let mode: "guided" | "strip" = "strip";
  const toggle = $<HTMLButtonElement>(".cb-mode");
  const label = toggle?.querySelector<HTMLElement>("[data-mode-label]");

  function build(p: Page, i: number) {
    const track = document.createElement("div"); track.className = "cb-track";
    const stage = document.createElement("div"); stage.className = "cb-stage";
    const turner = document.createElement("div"); turner.className = "cb-turner";
    p.sheet.replaceWith(track);
    turner.appendChild(p.sheet); stage.appendChild(turner); track.appendChild(stage);
    Object.assign(p, { track, stage, turner, cam: null, frame: -1, closed: false });
    p.sec.classList.add("is-reading");
    p.sec.style.zIndex = String(200 - i);
    // a page turns over only when the next section is another guided page waiting underneath it
    const next = p.sec.nextElementSibling;
    p.turn = !!next && pages.some((q) => q.sec === next);
    const prev = p.sec.previousElementSibling;
    p.lead = prev && pages.some((q) => q.sec === prev && q.turn) ? TURN : 0;
    p.travel = p.lead + (p.n + 1) * U + 0.5 * U + (p.turn ? TURN : 0.25);
    track.style.height = `${(p.travel + 1) * 100}svh`;
    p.sec.style.marginTop = p.lead ? `-${(TURN + 1) * 100}svh` : "";
  }
  function unbuild(p: Page) {
    if (!p.track) return;
    p.track.replaceWith(p.sheet);
    p.sheet.style.transform = "";
    p.sec.classList.remove("is-reading", "is-closed");
    p.sec.style.zIndex = ""; p.sec.style.marginTop = "";
    p.panels.forEach((el) => el.classList.remove("is-live", "is-read"));
    p.track = p.stage = p.turner = undefined;
  }
  let mastH = 62;
  function measure() {
    mastH = parseFloat(getComputedStyle(root).getPropertyValue("--cb-mast")) || 62;
    for (const p of pages) {
      if (!p.track) continue;
      p.W = p.sheet.offsetWidth; p.H = p.sheet.offsetHeight;
      p.boxes = p.panels.map((el) => ({ x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight }));
    }
  }
  function setMode(m: "guided" | "strip", keepPlace = false) {
    if (m === mode) return;
    const anchor = keepPlace ? all.find((s) => s.getBoundingClientRect().bottom > innerHeight * 0.4) : null;
    mode = m;
    root.classList.toggle("cb-guided", m === "guided");
    root.classList.toggle("cb-strip", m === "strip");
    if (m === "guided") pages.forEach(build); else pages.forEach(unbuild);
    measure();
    if (label) label.textContent = m === "guided" ? "strip" : "page";
    toggle?.setAttribute("aria-pressed", String(m === "strip"));
    if (anchor) anchor.scrollIntoView();
  }
  const want = () => (phone.matches || store.get() === "strip" ? "strip" : "guided");
  root.classList.add("cb-strip");
  setMode(want());
  if (toggle) {
    toggle.hidden = false;
    toggle.addEventListener("click", () => { const m = mode === "guided" ? "strip" : "guided"; store.set(m); setMode(m, true); });
  }
  phone.addEventListener("change", () => setMode(want(), true));
  addEventListener("resize", measure);
  document.fonts?.ready.then(measure);
  addEventListener("load", measure);

  // strip panels (and pages that never pin) pop as they reach the middle of the screen
  $$<HTMLElement>(".cb-page:not(.cb-splash) .cb-panel").forEach((panel) => {
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (!e.isIntersecting) return;
      const page = pages.find((p) => p.panels.includes(panel));
      if (mode === "guided" && page?.track) return;   // the camera decides in guided view
      pop(panel, panel);
    }), { rootMargin: "-30% 0px -30% 0px" });
    io.observe(panel);
  });

  // ---------------------------------------------------------------- the camera
  function frameCam(p: Page, k: number, aw: number, ah: number): Cam {
    const fit = Math.min(1, (aw * 0.95) / p.W, (ah * 0.94) / p.H);
    if (k <= 0 || k >= p.n + 1 || !p.boxes[k - 1]) return { cx: p.W / 2, cy: p.H / 2, z: fit };
    const b = p.boxes[k - 1];
    const z = Math.max(fit, Math.min((aw * 0.9) / b.w, (ah * 0.86) / b.h, 2.3));
    return { cx: b.x + b.w / 2, cy: b.y + b.h / 2, z };
  }

  onFrame(({ dt, vh }) => {
    chaptersTick();
    if (mode !== "guided") return;
    for (const p of pages) {
      if (!p.track || !p.turner) continue;
      const r = p.track.getBoundingClientRect();
      if (r.bottom < -vh || r.top > vh * 2) continue;
      const s = -r.top / vh;                                   // screens scrolled into the track
      const u = (s - p.lead) / U;
      let phi = 0;                                             // camera frame: 0 whole, 1..n panels, n+1 whole again
      if (u > 0) { const i = Math.floor(u), f = u - i; phi = Math.min(p.n + 1, i + smooth(HOLD, 1, f)); }
      const turn = p.turn ? clamp((s - p.lead - (p.n + 1.5) * U) / TURN) : 0;

      // reading state: the frame the camera is (mostly) on
      const k = Math.min(p.n + 1, Math.floor(phi + 0.4));
      if (k !== p.frame) {
        p.frame = k;
        const closed = k >= p.n + 1;
        p.sec.classList.toggle("is-closed", closed);
        p.sec.classList.toggle("is-reading", !closed);
        p.panels.forEach((el, j) => {
          el.classList.toggle("is-live", j === k - 1);
          el.classList.toggle("is-read", j < k - 1);
        });
        if (k >= 1 && k <= p.n) { stageShake = p.stage!; pop(p.panels[k - 1]); }
      }

      // the camera: interpolate centre and log-zoom between the two frames, then ease toward it
      const aw = innerWidth, ah = vh - mastH;
      const a = frameCam(p, Math.floor(phi), aw, ah), b = frameCam(p, Math.ceil(phi), aw, ah), t = phi - Math.floor(phi);
      const target: Cam = { cx: a.cx + (b.cx - a.cx) * t, cy: a.cy + (b.cy - a.cy) * t, z: Math.exp(Math.log(a.z) + (Math.log(b.z) - Math.log(a.z)) * t) };
      if (!p.cam) p.cam = { ...target };
      const e = 1 - Math.exp(-dt * 11);
      p.cam.cx += (target.cx - p.cam.cx) * e; p.cam.cy += (target.cy - p.cam.cy) * e;
      p.cam.z = Math.exp(Math.log(p.cam.z) + (Math.log(target.z) - Math.log(p.cam.z)) * e);
      const tx = p.W / 2 - p.cam.z * p.cam.cx, ty = p.H / 2 - p.cam.z * p.cam.cy;
      p.sheet.style.transform = `translate3d(${tx.toFixed(2)}px, ${ty.toFixed(2)}px, 0) scale(${p.cam.z.toFixed(4)})`;
      p.turner.style.transform = turn > 0 ? `rotateY(${(-turn * 104).toFixed(2)}deg)` : "";
      p.turner.style.setProperty("--turn", turn.toFixed(3));
    }
  });

  // ---------------------------------------------------------------- the CLICK! on the big buttons
  document.addEventListener("click", (ev) => {
    const a = (ev.target as HTMLElement).closest?.(".cb-burstbtn, .cb-btn--hot");
    if (!a) return;
    const fx = document.createElement("span");
    fx.className = "cb-click"; fx.textContent = "Click!"; fx.setAttribute("aria-hidden", "true");
    fx.style.left = `${(ev as MouseEvent).clientX}px`; fx.style.top = `${(ev as MouseEvent).clientY}px`;
    document.body.appendChild(fx);
    setTimeout(() => fx.remove(), 700);
  });

  chapters();
}

// ---------------------------------------------------------------- the current chapter lights up in the masthead
let chapterLinks: { a: HTMLElement; el: HTMLElement }[] = [];
let lastChapterY = NaN;
function chapters() {
  chapterLinks = $$<HTMLAnchorElement>(".cb-chapters a[href^='#']").map((a) => ({ a, el: document.getElementById(a.getAttribute("href")!.slice(1))! })).filter((c) => c.el);
  chaptersTick();
  if (reduced) addEventListener("scroll", chaptersTick, { passive: true });
}
function chaptersTick() {
  if (scrollY === lastChapterY) return;
  lastChapterY = scrollY;
  let cur: HTMLElement | null = null;
  for (const c of chapterLinks) if (c.el.getBoundingClientRect().top <= innerHeight * 0.5) cur = c.a;
  chapterLinks.forEach((c) => c.a.classList.toggle("is-current", c.a === cur));
}
