/**
 * Glassmorphism: windows over a living world.
 *
 *   world     one fixed layer of colour orbs drifting at 0.42x the scroll (differential parallax), with a slow
 *             Lissajous drift and a palette interpolated section by section (hue drift, never a cut)
 *   depth     [data-depth] panes move faster (near) or slower (behind) than the page
 *   condense  panes arrive frost first, then text (.gl-in)
 *   specular  a rim light and sheen follow the pointer; tilt panes lean 2-4 degrees toward it
 *   stack     features: a stack of panes collapsed into one slab fans apart in depth as you scroll (pinned)
 *   lens      product: a pinned glass lens whose copy changes in steps while the scene turns beneath it
 *   widgets   stats: rings fill with the scroll, numbers count up once when the widget condenses
 *   dock      timeline: a glass magnifier slides over the active step
 */
import { $, $$, onFrame, onSeen, pinSequence, reduced, through } from "./_kit";
import { clamp, lerp, smooth } from "../lib/util";

type RGB = [number, number, number];
const PALETTES: RGB[][] = [
  [[110, 86, 207], [255, 95, 162], [47, 211, 245], [255, 184, 107]],   // violet, pink, cyan, amber
  [[52, 110, 255], [47, 211, 245], [120, 86, 230], [70, 230, 190]],    // cool blue
  [[176, 76, 255], [255, 84, 176], [92, 104, 255], [255, 140, 96]],    // magenta
  [[24, 196, 220], [64, 226, 160], [96, 132, 255], [190, 240, 110]],   // lagoon
  [[255, 160, 80], [255, 92, 140], [255, 206, 110], [150, 92, 255]],   // amber rose
  [[86, 104, 255], [168, 92, 255], [52, 186, 255], [255, 116, 196]],   // indigo
];
const FINALE: RGB[] = [[255, 92, 168], [124, 92, 255], [40, 214, 255], [255, 196, 84]];
const mobile = () => matchMedia("(max-width: 900px)").matches;

export default function start() {
  const root = document.documentElement;
  root.classList.add("gl-live");
  stacks();
  lenses();
  condense();
  world();
  depth();
  specular();
  widgets();
  docks();
}

// ---------------------------------------------------------------- arrivals
function condense() {
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("gl-in"); io.unobserve(e.target); }
  }), { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
  $$(".gl-cond").forEach((el) => io.observe(el));
}

// ---------------------------------------------------------------- the living world
function world() {
  const host = $(".gl-world");
  if (!host) return;
  const orbs = $$<HTMLElement>(".gl-orb", host);
  const lead = $(".gl-orb--lead", host);
  const sections = $$<HTMLElement>("main > section, main > div > section, main > .gl-sec");
  const seen = new Set<HTMLElement>();
  const secs = sections.filter((s) => { const top = (s.closest(".gl-sec") as HTMLElement) || s; if (seen.has(top)) return false; seen.add(top); return true; });
  const pal = secs.map((s, i) => (s.dataset.gl === "finale" || (i === secs.length - 1 && s.classList.contains("gl-cta")) ? FINALE : PALETTES[i % PALETTES.length]));
  // world-space layout of the drifting orbs: x (0-1 of width), y (in screen heights inside a 2.4-screen tile)
  const spec = orbs.filter((o) => o !== lead).map((o, i) => ({
    el: o, x: [0.14, 0.86, 0.5, 0.1, 0.72, 0.34][i % 6], y: [0.15, 0.55, 1.05, 1.5, 1.95, 2.25][i % 6],
    s: [0.62, 0.56, 0.66, 0.46, 0.44, 0.4][i % 6], ph: i * 1.7, sp: 0.06 + (i % 3) * 0.02,
  }));
  orbs.forEach((o) => { o.style.left = "0"; o.style.top = "0"; o.style.translate = "none"; });
  const hero = $(".gl-hero .gl-h1") || $(".gl-hero");
  let mx = 0, my = 0, pmx = 0, pmy = 0;
  addEventListener("pointermove", (e) => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; }, { passive: true });
  let lastKey = "";
  onFrame(({ y, t, vh }) => {
    const W = innerWidth, vmax = Math.max(W, vh), tile = 2.4 * vh;
    pmx += (mx - pmx) * 0.04; pmy += (my - pmy) * 0.04;
    const drift = reduced ? 0 : 1, par = reduced ? 0 : 0.42;
    for (const o of spec) {
      const size = o.s * vmax;
      let cy = o.y * vh - y * par + Math.cos(t * o.sp * 0.8 + o.ph) * vh * 0.05 * drift;
      cy = ((cy + 0.7 * vh) % tile + tile) % tile - 0.7 * vh;
      const cx = o.x * W + Math.sin(t * o.sp + o.ph) * W * 0.05 * drift - pmx * 40;
      o.el.style.width = o.el.style.height = size.toFixed(0) + "px";
      o.el.style.transform = `translate3d(${(cx - size / 2).toFixed(1)}px, ${(cy - size / 2 - pmy * 30).toFixed(1)}px, 0)`;
    }
    // the lead orb drifts behind the hero headline as the hero is left
    if (lead && hero) {
      const r = hero.getBoundingClientRect();
      const k = clamp(-r.top / Math.max(1, vh) + 0.4);
      const size = 0.4 * vmax;
      const cx = r.left + r.width * lerp(0.18, 0.86, reduced ? 0.5 : k) + pmx * 60;
      const cy = r.top + r.height * 0.5 + pmy * 40;
      lead.style.width = lead.style.height = size.toFixed(0) + "px";
      lead.style.transform = `translate3d(${(cx - size / 2).toFixed(1)}px, ${(cy - size / 2).toFixed(1)}px, 0)`;
      lead.style.opacity = String(clamp(1.3 - Math.max(0, -r.top) / vh));
    }
    // hue drift: interpolate palettes between section centres
    if (!secs.length) return;
    const mid = vh / 2;
    let f = 0;
    const centres = secs.map((s) => { const r = s.getBoundingClientRect(); return r.top + Math.min(r.height, vh) / 2; });
    if (mid <= centres[0]) f = 0;
    else if (mid >= centres[centres.length - 1]) f = centres.length - 1;
    else for (let i = 0; i < centres.length - 1; i++) {
      if (mid >= centres[i] && mid < centres[i + 1]) {
        // hold each section's colours through its middle, hand over across the gap
        const span = centres[i + 1] - centres[i];
        f = i + smooth(0.25, 0.85, (mid - centres[i]) / span);
        break;
      }
    }
    const a = pal[Math.floor(f)], b = pal[Math.min(pal.length - 1, Math.floor(f) + 1)], k = f - Math.floor(f);
    const key = f.toFixed(3);
    if (key === lastKey) return;
    lastKey = key;
    for (let j = 0; j < 4; j++) {
      const c = a[j].map((v, n) => Math.round(lerp(v, b[j][n], k)));
      host.style.setProperty(`--o${j + 1}`, c.join(" "));
      document.documentElement.style.setProperty(`--o${j + 1}`, c.join(" "));
    }
  });
}

// ---------------------------------------------------------------- differential parallax of panes
function depth() {
  if (reduced) return;
  const items = $$<HTMLElement>("[data-depth]").filter((el) => !el.closest(".sx-stage")).map((el) => ({ el, d: parseFloat(el.dataset.depth || "1"), off: 0 }));
  if (!items.length) return;
  onFrame(({ vh }) => {
    const k = mobile() ? 0.5 : 1;
    for (const it of items) {
      if (it.d === 1) continue;
      const r = it.el.getBoundingClientRect();
      if (r.bottom < -200 || r.top > vh + 200) continue;
      const natural = r.top + r.height / 2 - it.off;
      const off = clamp((natural - vh / 2) * (it.d - 1) * k, -140, 140);
      if (Math.abs(off - it.off) < 0.2) continue;
      it.off = off;
      it.el.style.setProperty("--py", off.toFixed(1) + "px");
    }
  });
}

// ---------------------------------------------------------------- specular rim, sheen and tilt
function specular() {
  if (matchMedia("(hover: none)").matches) return;
  const tilts = new Map<HTMLElement, { rx: number; ry: number; tx: number; ty: number }>();
  let current: HTMLElement | null = null;
  addEventListener("pointermove", (e) => {
    const el = (e.target as Element)?.closest?.<HTMLElement>(".gl-pane, .gl-bar") || null;
    if (current && current !== el) { const s = tilts.get(current); if (s) { s.tx = 0; s.ty = 0; } }
    current = el;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    el.style.setProperty("--mx", px.toFixed(0) + "px");
    el.style.setProperty("--my", py.toFixed(0) + "px");
    if (!reduced && el.classList.contains("gl-tilt")) {
      const s = tilts.get(el) || { rx: 0, ry: 0, tx: 0, ty: 0 };
      const amt = r.width > 700 ? 2 : 4;
      s.tx = -(py / r.height - 0.5) * amt;
      s.ty = (px / r.width - 0.5) * amt;
      tilts.set(el, s);
    }
  }, { passive: true });
  document.addEventListener("pointerleave", () => { if (current) { const s = tilts.get(current); if (s) { s.tx = 0; s.ty = 0; } current = null; } });
  onFrame(() => {
    tilts.forEach((s, el) => {
      s.rx += (s.tx - s.rx) * 0.1; s.ry += (s.ty - s.ry) * 0.1;
      el.style.setProperty("--rx", s.rx.toFixed(2) + "deg");
      el.style.setProperty("--ry", s.ry.toFixed(2) + "deg");
      if (Math.abs(s.rx) + Math.abs(s.ry) < 0.01 && s.tx === 0 && s.ty === 0) { el.style.removeProperty("--rx"); el.style.removeProperty("--ry"); tilts.delete(el); }
    });
  });
}

// ---------------------------------------------------------------- features: exploded layers
function stacks() {
  $$<HTMLElement>('.gl-features[data-gl="stack"]').forEach((sec) => {
    const stack = $("[data-stack]", sec);
    if (!stack) return;
    const layers = $$<HTMLElement>(".gl-layer", stack);
    const n = layers.length;
    const vertical = mobile();
    if (n < 2 || n > (vertical ? 4 : 6) || reduced) return;
    sec.classList.add("gl-x");
    layers.forEach((l, i) => { l.style.zIndex = String(i + 1); if (i < n - 4) l.classList.add("gl-flat"); });
    let geo = { w: 0, h: 0, lw: 0, lh: 0, dx: 0, dy: 0 };
    const measure = () => {
      const r = stack.getBoundingClientRect();
      const W = r.width, H = r.height;
      const lw = vertical ? W : Math.min(520, Math.max(320, W * 0.42));
      stack.style.setProperty("--lw", lw + "px");
      const lh = Math.max(...layers.map((l) => l.offsetHeight));
      const dx = vertical ? 0 : Math.min(340, (W - lw) / (n - 1));
      const dy = vertical ? Math.min(lh - 18, (H - lh) / (n - 1)) : Math.min(lh * 0.62, Math.max(40, (H - lh) / (n - 1)));
      geo = { w: W, h: H, lw, lh, dx, dy };
    };
    pinSequence(sec, 1.4, (_s, p) => {
      if (!geo.w || geo.w !== stack.getBoundingClientRect().width) measure();
      const k = reduced ? 1 : smooth(0.06, 0.72, p);
      const ease = 1 - Math.pow(1 - k, 3);
      const { lw, lh, dx, dy } = geo;
      const totalW = lw + dx * (n - 1), totalH = lh + dy * (n - 1);
      layers.forEach((l, i) => {
        const depthBack = n - 1 - i;                     // the last layer is the nearest
        const x = vertical ? -lw / 2 : -totalW / 2 + i * dx;
        const yy = vertical ? -totalH / 2 + i * dy : -totalH / 2 + i * dy;
        const cx = lerp(-lw / 2 + depthBack * -3, x, ease);
        const cy = lerp(-lh / 2 + depthBack * -5, yy, ease);
        const sc = 1 - depthBack * 0.035 * ease;
        const rot = (vertical ? 0 : -4) * (1 - ease) + (vertical ? 0 : 0);
        l.style.transform = `translate3d(${cx.toFixed(1)}px, ${cy.toFixed(1)}px, 0) perspective(1200px) rotateY(${(rot - 6 * ease * (vertical ? 0 : 1)).toFixed(2)}deg) rotateX(${(3 * (1 - ease)).toFixed(2)}deg) scale(${sc.toFixed(3)})`;
        l.style.opacity = String(1 - depthBack * 0.06 * ease);
      });
    }, 0.9);
    addEventListener("resize", () => { geo.w = 0; });
  });
}

// ---------------------------------------------------------------- product: the pinned lens
function lenses() {
  $$<HTMLElement>('.gl-product[data-gl="lens"]').forEach((sec) => {
    const pages = $$<HTMLElement>("[data-page]", sec);
    const n = pages.length;
    if (reduced) return;
    const turn = $(".gl-scene__turn", sec);
    const glow = $(".gl-scene__glow", sec);
    const dots = $(".gl-lens__dots", sec);
    const opts = $$<HTMLElement>(".gl-opts li", sec);
    const phoneOpts = $$<HTMLElement>(".gl-scene .ss-app__opt", sec);
    if (dots) dots.innerHTML = pages.map(() => "<i></i>").join("");
    const dotEls = dots ? $$<HTMLElement>("i", dots) : [];
    sec.classList.add("gl-x");
    let active = -1, hl = -1;
    const sel = Math.max(0, opts.findIndex((o) => o.classList.contains("is-on")));
    pinSequence(sec, Math.max(2, n), (s, p) => {
      const steps = Math.max(2, n);
      const page = Math.min(n - 1, Math.floor((s / steps) * n));
      if (page !== active) {
        active = page;
        pages.forEach((pg, i) => pg.classList.toggle("is-on", i === page));
        dotEls.forEach((d, i) => d.classList.toggle("is-on", i === page));
      }
      // inside the options page, the highlight walks the list and comes back to the chosen one
      const optPage = pages.findIndex((pg) => pg.querySelector(".gl-opts"));
      if (opts.length > 1 && optPage >= 0) {
        const local = (s / steps) * n - optPage;
        const want = local > 0 && local < 1 ? Math.min(opts.length - 1, Math.floor(local * (opts.length + 1))) % opts.length : sel;
        const idx = local >= 1 ? sel : want;
        if (idx !== hl) {
          hl = idx;
          opts.forEach((o, i) => o.classList.toggle("is-on", i === idx));
          phoneOpts.forEach((o, i) => o.classList.toggle("is-on", i === idx));
        }
      }
      if (turn) {
        const side = sec.classList.contains("gl-product--left") ? -1 : 1;
        turn.style.setProperty("--turn", (side * lerp(-24, 18, p)).toFixed(2) + "deg");
        turn.style.setProperty("--lift", (lerp(40, -40, p)).toFixed(1) + "px");
        // the scene slides in under the lens and out again, so it is seen frosted through the glass mid-way
        turn.style.setProperty("--shift", (side * (mobile() ? 0 : lerp(14, -30, Math.sin(p * Math.PI)))).toFixed(1) + "%");
      }
      if (glow) glow.style.transform = `translate(${(Math.sin(p * Math.PI * 2) * 12).toFixed(1)}%, ${(lerp(10, -10, p)).toFixed(1)}%) scale(${(0.9 + Math.sin(p * Math.PI) * 0.25).toFixed(3)})`;
    }, 0.85);
  });
}

// ---------------------------------------------------------------- stats: widget rings and count-ups
function widgets() {
  const ws = $$<HTMLElement>(".gl-widget");
  if (!ws.length) return;
  ws.forEach((w) => {
    const v = $("[data-gl-count]", w);
    if (!v || reduced) return;
    const raw = v.dataset.glCount || "";
    const end = parseFloat(raw.replace(/,/g, ""));
    const dec = (raw.split(".")[1] || "").length;
    const grouped = raw.includes(",");
    const fmt = (x: number) => { const s = x.toFixed(dec); return grouped ? Number(s).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : s; };
    v.setAttribute("aria-label", raw);
    v.textContent = fmt(0);
    onSeen(w, () => {
      const t0 = performance.now(), dur = 1500;
      const step = (now: number) => {
        const k = clamp((now - t0) / dur);
        v.textContent = fmt(end * (1 - Math.pow(1 - k, 3)));
        if (k < 1) requestAnimationFrame(step); else v.textContent = raw;
      };
      requestAnimationFrame(step);
    }, 0.25);
  });
  if (reduced) return;
  onFrame(({ vh }) => {
    for (const w of ws) {
      const r = w.getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh) continue;
      w.style.setProperty("--ringk", smooth(0.08, 0.5, through(w)).toFixed(3));
    }
  });
}

// ---------------------------------------------------------------- timeline: the magnifier dock
function docks() {
  $$<HTMLElement>("[data-dock]").forEach((dock) => {
    const steps = $$<HTMLElement>(".gl-step", dock);
    const lens = $(".gl-dock__lens", dock);
    const n = steps.length;
    if (!lens || !n) return;
    let last = -1;
    onFrame(({ vh }) => {
      const r = dock.getBoundingClientRect();
      if (r.bottom < -vh || r.top > vh * 2) return;
      const p = reduced ? 0 : smooth(0.22, 0.72, through(dock));
      const k = p * (n - 1);
      const key = Math.round(k * 1000) + (mobile() ? 0.5 : 0);
      if (key === last) return;
      last = key;
      const a = steps[Math.floor(k)], b = steps[Math.min(n - 1, Math.floor(k) + 1)], f = k - Math.floor(k);
      if (mobile()) {
        const y = lerp(a.offsetTop, b.offsetTop, f), h = lerp(a.offsetHeight, b.offsetHeight, f);
        lens.style.setProperty("--ly", (y - steps[0].offsetTop).toFixed(1) + "px");
        lens.style.setProperty("--lh", h.toFixed(1) + "px");
        lens.style.top = steps[0].offsetTop + "px";
      } else {
        lens.style.removeProperty("top");
        lens.style.setProperty("--lx", (lerp(a.offsetLeft, b.offsetLeft, f) - steps[0].offsetLeft).toFixed(1) + "px");
      }
      steps.forEach((s, i) => s.style.setProperty("--act", (1 - clamp(Math.abs(i - k))).toFixed(3)));
    });
  });
}
