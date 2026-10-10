/**
 * Particles: one conserved swarm of points on one fixed canvas. Every scene of the page is a formation of the same
 * N points (sampled from [data-form] sources in its sticky stage: the headline's own letterforms, the phone, the
 * stat digits, feature icons, the timeline stream, the CTA's gravity well, the wordmark at the end). Scroll scrubs
 * the swarm from one formation to the next with a per-particle stagger and a turbulent vortex at mid-flight; the
 * pointer is a force field with spring-back; a tap sends a shockwave. Reduced motion: formations are static and
 * scenes change by a short crossfade.
 */
import { $, $$, onFrame, reduced } from "./_kit";
import { clamp, rng } from "../lib/util";

const TAU = Math.PI * 2;
const sstep = (a: number, b: number, v: number) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };

type Pt = { x: number; y: number };
type Form = {
  x: Float32Array; y: Float32Array; a: Float32Array; h: Float32Array; w: Float32Array;   // targets (stage-relative), alpha, hot, wander
  c?: Int16Array;                                                                         // feature cluster per point (-1 = dust)
};
type Scene = {
  el: HTMLElement; stage: HTMLElement | null; type: string; pinned: boolean; index: number;
  h0: number; h1: number;
  form: Form | null; subs: Form[];
  copyK: number; resK: number;
  centers: Pt[]; tight: number[]; active: number; hover: number;
  path: Float32Array | null; pathStep: number; nodeLen: number[];
  items: HTMLElement[]; vals: { el: HTMLElement; n: number; dec: number; shown: string }[];
  well: HTMLElement | null; wellC: Pt; wellR: number;
};

export default function start() {
  const canvas = $<HTMLCanvasElement>(".px-canvas");
  if (!canvas) return;
  const root = document.documentElement;
  root.classList.add("px-live");
  const bailout = setTimeout(() => { if (!ready) root.classList.remove("px-live"); }, 4000);

  const mobile = innerWidth < 760;
  const N = mobile ? 7000 : 16000;
  const R = rng(20240917);
  // per-particle constants
  const rA = new Float32Array(N), rB = new Float32Array(N), rC = new Float32Array(N), rD = new Float32Array(N), z = new Float32Array(N);
  for (let i = 0; i < N; i++) { rA[i] = R(); rB[i] = R(); rC[i] = R(); rD[i] = R(); z[i] = Math.pow(R(), 0.8); }
  // state
  const ox = new Float32Array(N), oy = new Float32Array(N), vx = new Float32Array(N), vy = new Float32Array(N);
  const px = new Float32Array(N), py = new Float32Array(N);
  const sx = new Float32Array(N), sy = new Float32Array(N);   // the scatter the swarm assembles from on load
  for (let i = 0; i < N; i++) { sx[i] = R() * innerWidth; sy[i] = R() * innerHeight; }
  // per-frame targets of the two formations in play
  const TA = mkForm(N), TB = mkForm(N);
  const out = new Float32Array(N * 4);

  // ---------------------------------------------------------------- renderer
  const gfx = makeRenderer(canvas, N, z, mobile);

  // ---------------------------------------------------------------- scenes
  const scenes: Scene[] = [];
  const blocks: HTMLElement[] = [];
  $$<HTMLElement>("main > *").forEach((c) => {
    const s = c.matches("section") ? c : c.querySelector<HTMLElement>(":scope > section");
    if (s) blocks.push(s);
  });
  const end = $<HTMLElement>(".px-end");
  if (end) blocks.push(end);
  blocks.forEach((el, index) => {
    const type = el.dataset.px || (el.classList.contains("ss-scene") ? "media" : "other");
    const stage = el.classList.contains("px-scene") ? $<HTMLElement>(".px-stage", el) : null;
    scenes.push({
      el, stage, type, index, pinned: !!stage && !el.classList.contains("px-scene--free"), h0: 0, h1: 0,
      form: null, subs: [], copyK: -1, resK: -1, centers: [], tight: [], active: -1, hover: -1,
      path: null, pathStep: 1, nodeLen: [], items: [], vals: [], well: null, wellC: { x: 0, y: 0 }, wellR: 60,
    });
  });
  if (!scenes.length) return;

  // stepped scenes keep their items
  scenes.forEach((s) => {
    if (s.type === "features") {
      s.items = $$<HTMLElement>(".px-feat", s.el);
      s.items.forEach((li, i) => {
        const on = () => { s.hover = i; };
        const off = () => { if (s.hover === i) s.hover = -1; };
        li.addEventListener("pointerenter", on); li.addEventListener("pointerleave", off);
        li.addEventListener("focus", on); li.addEventListener("blur", off);
      });
    }
    if (s.type === "stats") {
      s.items = $$<HTMLElement>(".px-stat", s.el);
      s.vals = $$<HTMLElement>(".px-stat__v b", s.el).map((b) => {
        const raw = (b.parentElement as HTMLElement).dataset.n;
        return { el: b, n: raw ? parseFloat(raw) : NaN, dec: raw && raw.includes(".") ? raw.split(".")[1].length : 0, shown: b.textContent || "" };
      });
    }
    if (s.type === "timeline") s.items = $$<HTMLElement>(".px-step", s.el);
    if (s.type === "cta") s.well = $<HTMLElement>(".px-well", s.el);
  });

  // ---------------------------------------------------------------- layout: when is each formation held
  let vw = innerWidth, vh = innerHeight;
  const docTop = (el: HTMLElement) => el.getBoundingClientRect().top + scrollY;
  function layout() {
    vw = innerWidth; vh = innerHeight;
    for (const s of scenes) {
      const T = docTop(s.el), H = s.el.offsetHeight;
      if (s.pinned) {
        const L = Math.max(0, H - vh);
        const stepped = s.type === "features" || s.type === "stats" || s.type === "timeline";
        s.h0 = T + L * (stepped ? 0.1 : 0.16);
        s.h1 = T + L * (stepped ? 0.86 : 0.7);
      } else if (H > vh) { s.h0 = T - vh * 0.25; s.h1 = T + H - vh * 0.75; }
      else { const c = T + H / 2 - vh / 2; s.h0 = c - vh * 0.12; s.h1 = c + vh * 0.12; }
    }
    scenes[0].h0 = -1e9;
    for (let i = 1; i < scenes.length; i++) if (scenes[i].h0 < scenes[i - 1].h1 + 40) scenes[i].h0 = scenes[i - 1].h1 + 40;
    for (const s of scenes) if (s.h1 < s.h0) s.h1 = s.h0;
    scenes[scenes.length - 1].h1 = 1e9;
  }

  // ---------------------------------------------------------------- formations
  const work = document.createElement("canvas");
  const wctx = work.getContext("2d", { willReadFrequently: true })!;
  function build() {
    for (const s of scenes) {
      try { buildScene(s); } catch (err) { s.form = dustForm(0.3); console.warn("particles: formation fallback", err); }
    }
  }
  function buildScene(s: Scene) {
    s.subs = [];
    if (!s.stage || s.type === "faq") { s.form = dustForm(s.type === "faq" ? 0.26 : 0.2); return; }
    const sr = s.stage.getBoundingClientRect();
    const W = sr.width, H = Math.min(sr.height, vh * 1.15);
    const S = W * H > 900000 ? 0.45 : 0.6;
    const start = (w = W, h = H) => {
      work.width = Math.max(2, Math.ceil(w * S)); work.height = Math.max(2, Math.ceil(h * S));
      wctx.setTransform(S, 0, 0, S, 0, 0); wctx.clearRect(0, 0, w, h);
    };
    const rel = (el: Element) => { const r = el.getBoundingClientRect(); return { x: r.left - sr.left, y: r.top - sr.top, w: r.width, h: r.height }; };

    if (s.type === "stats") {
      const box = $<HTMLElement>(".px-stats__matter", s.stage);
      const b = box ? rel(box) : { x: W * 0.4, y: H * 0.2, w: W * 0.5, h: H * 0.6 };
      for (const li of s.items) {
        const v = li.querySelector<HTMLElement>(".px-stat__v");
        start();
        drawDigits(wctx, v?.dataset.v || "0", v?.dataset.unit || "", b);
        s.subs.push(sample(S, 0.86, 0.7));
      }
      s.form = s.subs[0] || dustForm(0.3);
      return;
    }
    if (s.type === "timeline") {
      const nodes = $$<HTMLElement>("[data-node]", s.stage).map((n) => { const r = rel(n); return { x: r.x + r.w / 2, y: r.y + r.h / 2 }; });
      buildPath(s, nodes);
      s.form = dustForm(0.3, true, W, H);
      return;
    }
    if (s.type === "cta") {
      if (s.well) { const r = rel(s.well); s.wellC = { x: r.x + r.w / 2, y: r.y + r.h / 2 }; s.wellR = r.w / 2; }
      else { s.wellC = { x: W / 2, y: H / 2 }; s.wellR = 60; }
      s.form = dustForm(0.3, true, W, H);
      return;
    }
    start();
    const parts = $$<HTMLElement>("[data-form]", s.stage);
    let cluster = 0;
    s.centers = [];
    for (const el of parts) {
      const kind = el.dataset.form!;
      const r = rel(el);
      if (r.w < 2 || r.h < 2) continue;
      if (kind === "text") drawText(wctx, el, sr, s.type === "hero" ? 0.05 : 0.022, 0);
      else if (kind === "phone") drawPhone(wctx, el, sr);
      else if (kind === "image") drawImage(wctx, el as HTMLImageElement, r, S);
      else if (kind === "box") drawBox(wctx, r);
      else if (kind === "icon") {
        drawIcon(wctx, parseInt(el.dataset.icon || "0", 10), r, cluster);
        s.centers.push({ x: r.x + r.w / 2, y: r.y + r.h / 2 });
        cluster++;
      }
    }
    const share = s.type === "features" ? 0.84 : s.type === "end" ? 0.8 : s.type === "hero" ? 0.9 : 0.86;
    s.form = sample(S, share, s.type === "end" ? 0.5 : 0.75, s.type === "features", s.type === "end" ? "floor" : "air");
    if (s.type === "features") { s.tight = s.centers.map(() => -1); }
  }

  /** Sample the work canvas into a formation: share of the points on ink (weighted by alpha), the rest as dust. */
  function sample(S: number, share: number, dustA: number, clusters = false, dust: "air" | "floor" = "air"): Form {
    const W = work.width, H = work.height;
    const img = wctx.getImageData(0, 0, W, H).data;
    const idx: number[] = [], cum: number[] = [];
    let tot = 0;
    for (let p = 0, n = W * H; p < n; p++) {
      const a = img[p * 4 + 3];
      if (a > 10) { tot += a; idx.push(p); cum.push(tot); }
    }
    const f = mkForm(N, clusters);
    const onInk = idx.length ? Math.round(N * share) : 0;
    for (let i = 0; i < N; i++) {
      if (i < onInk) {
        const r = R() * tot;
        let lo = 0, hi = cum.length - 1;
        while (lo < hi) { const m = (lo + hi) >> 1; if (cum[m] < r) lo = m + 1; else hi = m; }
        const p = idx[lo], q = p * 4;
        f.x[i] = ((p % W) + R()) / S; f.y[i] = (Math.floor(p / W) + R()) / S;
        f.a[i] = 0.62 + 0.38 * (img[q + 3] / 255);
        f.h[i] = img[q] > 128 ? 1 : 0;
        f.w[i] = 1.1;
        if (f.c) f.c[i] = Math.max(0, Math.round((img[q + 1] - 8) / 16));
      } else {
        f.x[i] = R() * W / S;
        f.y[i] = dust === "floor" ? H / S - Math.pow(R(), 2.2) * H / S * 0.22 : R() * H / S;
        f.a[i] = dustA * (0.35 + 0.65 * R());
        f.h[i] = R() < 0.05 ? 1 : 0;
        f.w[i] = dust === "floor" ? 2 : 9;
        if (f.c) f.c[i] = -1;
      }
    }
    // shuffle so the ink/dust split is spread over the particle ids (each formation gets a fresh mapping)
    for (let i = N - 1; i > 0; i--) {
      const j = Math.floor(R() * (i + 1));
      swap(f.x, i, j); swap(f.y, i, j); swap(f.a, i, j); swap(f.h, i, j); swap(f.w, i, j);
      if (f.c) { const t = f.c[i]; f.c[i] = f.c[j]; f.c[j] = t; }
    }
    return f;
  }
  function dustForm(alpha: number, _stage = false, W = vw, H = vh): Form {
    const f = mkForm(N);
    for (let i = 0; i < N; i++) { f.x[i] = R() * W; f.y[i] = R() * H; f.a[i] = alpha * (0.3 + 0.7 * R()); f.h[i] = R() < 0.04 ? 1 : 0; f.w[i] = 12; }
    return f;
  }

  function buildPath(s: Scene, nodes: Pt[]) {
    s.path = null; s.nodeLen = [];
    if (!nodes.length) return;
    const pts: Pt[] = [];
    const g0 = nodes.length > 1 ? { x: nodes[1].x - nodes[0].x, y: nodes[1].y - nodes[0].y } : { x: 120, y: 0 };
    const gl0 = Math.hypot(g0.x, g0.y) || 1;
    const lead = Math.min(gl0 * 0.8, 260);
    pts.push({ x: nodes[0].x - g0.x / gl0 * lead, y: nodes[0].y - g0.y / gl0 * lead });
    nodes.forEach((n, i) => {
      pts.push(n);
      const m = nodes[i + 1];
      if (m) {
        const dx = m.x - n.x, dy = m.y - n.y, l = Math.hypot(dx, dy) || 1, w = (i % 2 ? 1 : -1) * Math.min(26, l * 0.12);
        pts.push({ x: (n.x + m.x) / 2 - dy / l * w, y: (n.y + m.y) / 2 + dx / l * w });
      }
    });
    const ln = nodes[nodes.length - 1], lp = pts[pts.length - 2] || pts[0];
    const ex = ln.x - lp.x, ey = ln.y - lp.y, el = Math.hypot(ex, ey) || 1;
    pts.push({ x: ln.x + ex / el * Math.min(lead, 140), y: ln.y + ey / el * Math.min(lead, 140) });
    // Catmull-Rom, then resample by arc length
    const dense: Pt[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
      for (let k = 0; k < 24; k++) {
        const t = k / 24, t2 = t * t, t3 = t2 * t;
        dense.push({
          x: 0.5 * (2 * p1.x + (-p0.x + p2.x) * t + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
          y: 0.5 * (2 * p1.y + (-p0.y + p2.y) * t + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3),
        });
      }
    }
    dense.push(pts[pts.length - 1]);
    const cl = [0];
    for (let i = 1; i < dense.length; i++) cl.push(cl[i - 1] + Math.hypot(dense[i].x - dense[i - 1].x, dense[i].y - dense[i - 1].y));
    const total = cl[cl.length - 1], K = 700, step = total / (K - 1);
    const path = new Float32Array(K * 2);
    let j = 0;
    for (let k = 0; k < K; k++) {
      const d = k * step;
      while (j < cl.length - 2 && cl[j + 1] < d) j++;
      const t = clamp((d - cl[j]) / ((cl[j + 1] - cl[j]) || 1));
      path[k * 2] = dense[j].x + (dense[j + 1].x - dense[j].x) * t;
      path[k * 2 + 1] = dense[j].y + (dense[j + 1].y - dense[j].y) * t;
    }
    s.path = path; s.pathStep = step;
    s.nodeLen = nodes.map((n) => {
      let best = 0, bd = 1e12;
      for (let k = 0; k < K; k++) { const d = (path[k * 2] - n.x) ** 2 + (path[k * 2 + 1] - n.y) ** 2; if (d < bd) { bd = d; best = k; } }
      return best * step;
    });
  }

  // ---------------------------------------------------------------- per-frame formation targets
  let T = 0;
  /** Write scene s's targets (in viewport px) into out at local hold progress k. */
  function fill(s: Scene, o: Form, k: number, offx: number, offy: number, relax: number) {
    const f = s.form!;
    if (s.type === "features" && f.c && s.centers.length) {
      const n = s.centers.length;
      const want = s.hover >= 0 ? s.hover : Math.min(n - 1, Math.floor(clamp(k) * n));
      if (want !== s.active) { s.active = want; s.items.forEach((li, i) => li.classList.toggle("is-on", i === want)); }
      for (let c = 0; c < n; c++) {
        const target = c === want ? 1 : 0;
        s.tight[c] = s.tight[c] < 0 || reduced ? target : s.tight[c] + (target - s.tight[c]) * Math.min(1, dtNow * 5);
      }
      for (let i = 0; i < N; i++) {
        const c = f.c[i];
        let x = f.x[i], y = f.y[i], a = f.a[i], h = f.h[i];
        if (c >= 0 && c < n) {
          const t = s.tight[c], cc = s.centers[c], spread = 1.32 - 0.32 * t, j = (1 - t) * 26 * rD[i];
          x = cc.x + (x - cc.x) * spread + Math.cos(rC[i] * TAU) * j;
          y = cc.y + (y - cc.y) * spread + Math.sin(rC[i] * TAU) * j;
          a *= 0.26 + 0.74 * t;
          h = Math.max(h, t > 0.5 && rB[i] < 0.12 ? 1 : 0);
        }
        o.x[i] = x + offx; o.y[i] = y + offy; o.a[i] = a; o.h[i] = h; o.w[i] = f.w[i];
      }
      return;
    }
    if (s.type === "stats" && s.subs.length) {
      const n = s.subs.length, seg = clamp(k) * n, j = Math.min(n - 1, Math.floor(seg)), u = seg - j;
      const A = s.subs[j], B = s.subs[Math.min(n - 1, j + 1)];
      const t = j < n - 1 ? sstep(0.62, 1, u) : 0;
      if (s.active !== j) { s.active = j; s.items.forEach((li, i) => li.classList.toggle("is-on", i === j)); }
      // the active value counts up as its digits condense
      s.vals.forEach((v, i) => {
        let txt = v.el.dataset.raw || (v.el.dataset.raw = v.el.textContent || "");
        if (i === j && !isNaN(v.n) && !reduced) {
          const kk = sstep(0, 0.42, j === 0 ? u : u);
          txt = (v.n * kk).toFixed(v.dec);
          if (v.n >= 1000) txt = Number(txt).toLocaleString("en-US");
        }
        if (txt !== v.shown) { v.el.textContent = txt; v.shown = txt; }
      });
      for (let i = 0; i < N; i++) {
        const ti = t <= 0 ? 0 : sstep(rA[i] * 0.35, rA[i] * 0.35 + 0.65, t);
        const m = Math.sin(Math.PI * ti) * 38;
        o.x[i] = A.x[i] + (B.x[i] - A.x[i]) * ti + m * Math.sin(rB[i] * TAU + T) + offx;
        o.y[i] = A.y[i] + (B.y[i] - A.y[i]) * ti + m * Math.cos(rC[i] * TAU + T) + offy;
        o.a[i] = A.a[i] + (B.a[i] - A.a[i]) * ti; o.h[i] = ti < 0.5 ? A.h[i] : B.h[i]; o.w[i] = A.w[i];
      }
      return;
    }
    if (s.type === "timeline" && s.path) {
      const P = s.path, K = P.length / 2, L = s.pathStep * (K - 1), nl = s.nodeLen, n = nl.length;
      const reach = n > 1 ? nl[0] + (nl[n - 1] - nl[0]) * clamp(k * 1.06) : nl[0] || L;
      let act = 0;
      for (let q = 0; q < n; q++) if (nl[q] <= reach + 2) act = q;
      if (s.active !== act) { s.active = act; s.items.forEach((li, i) => li.classList.toggle("is-on", i <= act)); }
      for (let i = 0; i < N; i++) {
        const role = rA[i];
        let x: number, y: number, a: number, h = 0;
        if (role < 0.56) {
          const u = (rB[i] + T * 0.05 * (0.5 + rC[i])) % 1;
          const d = u * Math.min(L, reach + 30);
          const kf = d / s.pathStep, k0 = Math.min(K - 2, Math.floor(kf)), tt = kf - k0;
          const x0 = P[k0 * 2], y0 = P[k0 * 2 + 1], x1 = P[k0 * 2 + 2], y1 = P[k0 * 2 + 3];
          const dl = Math.hypot(x1 - x0, y1 - y0) || 1, nn = (rD[i] - 0.5) * (rD[i] - 0.5) * 4 * (rC[i] < 0.5 ? -1 : 1) * 9;
          x = x0 + (x1 - x0) * tt - (y1 - y0) / dl * nn; y = y0 + (y1 - y0) * tt + (x1 - x0) / dl * nn;
          a = 0.5 + 0.4 * z[i]; h = rC[i] < 0.06 ? 1 : 0;
        } else if (role < 0.86 && n) {
          const q = i % n, node = nl[q] <= reach + 2;
          const kq = Math.min(K - 1, Math.round(nl[q] / s.pathStep));
          const rr = (node ? 20 : 40) * Math.pow(rB[i], node ? 1.6 : 0.8), th = rC[i] * TAU;
          x = P[kq * 2] + Math.cos(th) * rr; y = P[kq * 2 + 1] + Math.sin(th) * rr * (node ? 0.8 : 1);
          a = node ? 0.92 : 0.16; h = node && q === act && rD[i] < 0.35 ? 1 : 0;
        } else { x = f.x[i]; y = f.y[i]; a = f.a[i]; h = f.h[i]; }
        o.x[i] = x + offx; o.y[i] = y + offy; o.a[i] = a; o.h[i] = h; o.w[i] = role < 0.86 ? 0.8 : 10;
      }
      return;
    }
    if (s.type === "cta") {
      const C = s.wellC, R0 = s.wellR + 16, span = Math.min(vw, vh) * (mobile ? 0.5 : 0.46);
      wellPull += ((wellHot ? 1 : 0) - wellPull) * Math.min(1, dtNow * 4);
      const sc = 1 - 0.42 * wellPull, spin = 1 + 1.8 * wellPull;
      for (let i = 0; i < N; i++) {
        if (rD[i] < 0.86) {
          const r = R0 + Math.pow(rA[i], 1.7) * span, w = 0.55 * Math.pow(R0 / r, 1.5) * spin;
          wellAng[i] += reduced ? 0 : w * dtNow;
          const th = rB[i] * TAU + wellAng[i];
          const cs = Math.cos(th), sn = Math.sin(th);
          o.x[i] = C.x + cs * r * sc + offx; o.y[i] = C.y + sn * r * 0.4 * sc + offy;
          o.a[i] = (0.3 + 0.65 * (1 - (r - R0) / span)) * (0.75 + 0.25 * sn); o.h[i] = rC[i] < 0.1 ? 1 : 0; o.w[i] = 0.6;
        } else { o.x[i] = f.x[i] + offx; o.y[i] = f.y[i] + offy; o.a[i] = f.a[i]; o.h[i] = f.h[i]; o.w[i] = f.w[i]; }
      }
      return;
    }
    // static formation, relaxing into a soft halo once its crisp HTML layer has resolved over it
    const rx = relax * 9;
    for (let i = 0; i < N; i++) {
      o.x[i] = f.x[i] + offx + (rx ? Math.cos(rC[i] * TAU) * rx * rD[i] : 0);
      o.y[i] = f.y[i] + offy + (rx ? Math.sin(rC[i] * TAU) * rx * rD[i] : 0);
      o.a[i] = f.a[i] * (1 - relax * 0.62 * (f.w[i] < 2 ? 1 : 0)); o.h[i] = f.h[i]; o.w[i] = f.w[i];
    }
  }
  const wellAng = new Float32Array(N);
  let wellPull = 0, wellHot = false, dtNow = 0.016;

  // ---------------------------------------------------------------- pointer, taps, bursts
  let mx = -1e4, my = -1e4, pvx = 0, pvy = 0, lmx = 0, lmy = 0, pointerOn = false;
  addEventListener("pointermove", (e) => { mx = e.clientX; my = e.clientY; pointerOn = e.pointerType !== "touch"; }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => { pointerOn = false; });
  const waves: { x: number; y: number; t0: number }[] = [];
  addEventListener("pointerdown", (e) => { if (e.pointerType === "touch" && !reduced) waves.push({ x: e.clientX, y: e.clientY, t0: T }); }, { passive: true });
  function impulse(x: number, y: number, radius: number, power: number) {
    if (reduced) return;
    for (let i = 0; i < N; i++) {
      const dx = px[i] - x, dy = py[i] - y, d = Math.hypot(dx, dy);
      if (d > radius || d < 0.01) continue;
      const k = (1 - d / radius) * power * (0.5 + 0.5 * rA[i]);
      vx[i] += dx / d * k; vy[i] += dy / d * k;
    }
  }
  scenes.forEach((s) => {
    if (s.well) {
      s.well.addEventListener("pointerenter", () => { wellHot = true; });
      s.well.addEventListener("pointerleave", () => { wellHot = false; });
      s.well.addEventListener("focus", () => { wellHot = true; });
      s.well.addEventListener("blur", () => { wellHot = false; });
      s.well.addEventListener("click", () => { const r = s.well!.getBoundingClientRect(); wellPull = 0; impulse(r.left + r.width / 2, r.top + r.height / 2, 560, 1500); });
    }
    if (s.type === "faq") $$<HTMLDetailsElement>("details", s.el).forEach((d) => d.addEventListener("toggle", () => {
      if (!d.open) return;
      const r = d.querySelector("summary")!.getBoundingClientRect();
      impulse(r.left + r.width * 0.5, r.top + r.height / 2, 170, 520);
      layout();
    }));
  });

  // ---------------------------------------------------------------- nav: a little swarm marks the active link
  const navLinks = $$<HTMLAnchorElement>(".ss-nav__links a[href^='#']");
  const navTargets = navLinks.map((a) => document.getElementById(a.getAttribute("href")!.slice(1)));
  const dots = document.createElement("span");
  dots.className = "px-navdots";
  dots.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 9; i++) { const d = document.createElement("i"); d.style.transitionDelay = `${i * 45}ms`; dots.appendChild(d); }
  navLinks[0]?.parentElement?.appendChild(dots);
  let navOn = -2;
  function updateNav() {
    let on = -1;
    navTargets.forEach((t, i) => { if (t && t.getBoundingClientRect().top < vh * 0.5) on = i; });
    if (on === navOn) return;
    navOn = on;
    navLinks.forEach((a, i) => a.classList.toggle("is-on", i === on));
    dots.classList.toggle("is-on", on >= 0);
    if (on < 0) return;
    const a = navLinks[on], cx = a.offsetLeft + a.offsetWidth / 2;
    [...dots.children].forEach((d, i) => {
      const j = i - 4;
      (d as HTMLElement).style.transform = `translate(${(cx + j * 3.4 + Math.sin(i * 7.1) * 1.5).toFixed(1)}px, ${(1 + (i % 3) * 1.6).toFixed(1)}px)`;
    });
  }

  // ---------------------------------------------------------------- HUD
  const hudCount = $<HTMLElement>("[data-px-count]"), hudForm = $<HTMLElement>("[data-px-form]"), hudState = $<HTMLElement>("[data-px-state]");
  if (hudCount) hudCount.textContent = N.toLocaleString("en-US").replace(/,/g, " ");
  let hudLast = "";

  // ---------------------------------------------------------------- the frame
  let ready = false, t0 = 0, fadeK = 1, lastShown = -1;
  const setVar = (s: Scene, k: number, r: number) => {
    k = Math.round(k * 100) / 100; r = Math.round(r * 100) / 100;
    if (k !== s.copyK) { s.el.style.setProperty("--k", String(k)); s.copyK = k; }
    if (r !== s.resK) { s.el.style.setProperty("--r", String(r)); s.resK = r; }
  };
  const offOf = (s: Scene) => {
    if (!s.stage) return { x: 0, y: 0 };
    const r = s.stage.getBoundingClientRect();
    return { x: r.left, y: r.top };
  };

  onFrame(({ y, v, dt, t }) => {
    if (!ready) return;
    if (t0 < 0) t0 = t;
    T = t; dtNow = dt || 0.016;
    // which formations are in play
    let a = 0;
    while (a < scenes.length - 1 && y > scenes[a].h1) a++;
    let b = a, p = 0;
    if (a > 0 && y < scenes[a].h0) { b = a; a = a - 1; p = clamp((y - scenes[a].h1) / Math.max(1, scenes[b].h0 - scenes[a].h1)); }
    const SA = scenes[a], SB = scenes[b];
    const kA = clamp((y - SA.h0) / Math.max(1, SA.h1 - SA.h0)), kB = clamp((y - SB.h0) / Math.max(1, SB.h1 - SB.h0));
    const intro = reduced ? 1 : clamp((t - t0) / 1.5);

    // copy and crisp layers
    for (const s of scenes) {
      let k = 0, r = 0;
      if (reduced) { k = 1; r = 1; }
      else if (s === SA && s === SB) { k = 1; r = 1; }
      else if (s === SA) { k = 1 - sstep(0, 0.28, p); r = 1 - sstep(0, 0.14, p); }
      else if (s === SB) { k = sstep(0.62, 0.95, p); r = sstep(0.9, 1, p); }
      if (s === scenes[0] || s === SA || s === SB) { k *= sstep(0.45, 0.9, intro); r *= sstep(0.72, 1, intro); }
      setVar(s, k, r);
    }

    // reduced motion: hold the nearest formation, swap with a short fade
    if (reduced) {
      const show = p < 0.5 ? a : b;
      if (show !== lastShown) { if (lastShown >= 0) fadeK = 0; lastShown = show; }
      fadeK = Math.min(1, fadeK + dt / 0.3);
      const S = scenes[show], o = offOf(S);
      fill(S, TA, show === a ? kA : kB, o.x, o.y, 0);
      for (let i = 0; i < N; i++) { out[i * 4] = TA.x[i]; out[i * 4 + 1] = TA.y[i]; out[i * 4 + 2] = TA.a[i] * (0.45 + 0.55 * z[i]); out[i * 4 + 3] = TA.h[i]; }
      gfx.draw(out, Math.abs(fadeK * 2 - 1));
      hud(show, 0);
      updateNav();
      return;
    }

    const oA = offOf(SA);
    fill(SA, TA, kA, oA.x, oA.y, SA.type === "hero" || SA.type === "product" ? Math.max(0, SA.resK) : 0);
    if (p > 0) { const oB = offOf(SB); fill(SB, TB, kB, oB.x, oB.y, 0); }

    // pointer velocity
    pvx = (mx - lmx) / Math.max(dt, 0.008); pvy = (my - lmy) / Math.max(dt, 0.008); lmx = mx; lmy = my;
    const PR = mobile ? 70 : 110, PR2 = PR * PR;
    const cx = vw / 2, cy = vh / 2, dir = a % 2 ? -1 : 1;
    const vel = clamp(v, -45, 45);
    const k = 26, c = 7.2;
    for (let i = 0; i < N; i++) {
      let x = TA.x[i], yy = TA.y[i], al = TA.a[i], h = TA.h[i], w = TA.w[i];
      if (p > 0) {
        const bx = TB.x[i], by = TB.y[i];
        const d = clamp(0.3 * (clamp(bx / vw) * 0.55 + rA[i] * 0.45), 0, 0.4);
        const ti = sstep(d, d + 0.6, p);
        x += (bx - x) * ti; yy += (by - yy) * ti;
        al += (TB.a[i] - al) * ti; h = ti < 0.5 ? h : TB.h[i]; w += (TB.w[i] - w) * ti;
        const m = Math.sin(Math.PI * ti);
        if (m > 0.001) {
          const dx = x - cx, dy = yy - cy, dl = Math.hypot(dx, dy) + 1;
          const ang = m * (0.7 + 0.9 * rA[i]) * dir * (1.25 - Math.min(1, dl / (vw * 0.6)) * 0.5);
          const cs = Math.cos(ang), sn = Math.sin(ang), push = m * (30 + 230 * rB[i]);
          x = cx + dx * cs - dy * sn + dx / dl * push;
          yy = cy + dx * sn + dy * cs + dy / dl * push;
          x += m * 34 * Math.sin(yy * 0.012 + t * 1.6 + rC[i] * 6.3);
          yy += m * 34 * Math.cos(x * 0.011 + t * 1.2 + rD[i] * 6.3);
          al *= 1 - 0.25 * m;
        }
      }
      // breathing drift and depth parallax
      const wa = w * (0.6 + 0.8 * z[i]);
      x += Math.sin(t * (0.35 + 0.5 * rA[i]) + rB[i] * TAU) * wa;
      yy += Math.cos(t * (0.3 + 0.45 * rC[i]) + rD[i] * TAU) * wa - vel * (z[i] - 0.35) * 2.2;
      // assemble from scatter on load
      if (intro < 1) {
        const ti = sstep(rA[i] * 0.35, rA[i] * 0.35 + 0.65, intro), m = Math.sin(Math.PI * ti);
        x = sx[i] + (x - sx[i]) * ti + m * 60 * Math.sin(rB[i] * TAU + t);
        yy = sy[i] + (yy - sy[i]) * ti + m * 60 * Math.cos(rC[i] * TAU + t);
      }
      // the pointer is a hand through the sand; springs pull each point home
      let fx = -k * ox[i] - c * vx[i], fy = -k * oy[i] - c * vy[i];
      if (pointerOn) {
        const dx = x + ox[i] - mx, dy = yy + oy[i] - my;
        if (dx < PR && dx > -PR && dy < PR && dy > -PR) {
          const d2 = dx * dx + dy * dy;
          if (d2 < PR2 && d2 > 0.01) {
            const d = Math.sqrt(d2), f = (1 - d / PR) * (1 - d / PR);
            fx += dx / d * 3200 * f - dy / d * 900 * f + pvx * f * 5;
            fy += dy / d * 3200 * f + dx / d * 900 * f + pvy * f * 5;
          }
        }
      }
      for (let q = 0; q < waves.length; q++) {
        const wv = waves[q], age = t - wv.t0, rr = age * 760;
        const dx = x - wv.x, dy = yy - wv.y, d = Math.hypot(dx, dy) + 0.01, band = Math.abs(d - rr);
        if (band < 46) { const f = (1 - band / 46) * (1 - age / 1.3) * 4200; fx += dx / d * f; fy += dy / d * f; }
      }
      vx[i] += fx * dt; vy[i] += fy * dt;
      ox[i] += vx[i] * dt; oy[i] += vy[i] * dt;
      const X = x + ox[i], Y = yy + oy[i];
      px[i] = X; py[i] = Y;
      out[i * 4] = X; out[i * 4 + 1] = Y; out[i * 4 + 2] = al * (0.45 + 0.55 * z[i]); out[i * 4 + 3] = h;
    }
    for (let q = waves.length - 1; q >= 0; q--) if (t - waves[q].t0 > 1.3) waves.splice(q, 1);
    gfx.draw(out, 1);
    hud(p > 0.5 ? b : a, p);
    updateNav();
  });

  function hud(i: number, p: number) {
    const st = p <= 0 ? "assembled" : p < 0.3 ? "dispersing" : p < 0.7 ? "in transit" : "condensing";
    const key = i + st;
    if (key === hudLast) return;
    hudLast = key;
    if (hudForm) hudForm.textContent = String(i + 1).padStart(2, "0");
    if (hudState) hudState.textContent = st;
  }

  // ---------------------------------------------------------------- go
  const go = () => {
    layout();
    build();
    ready = true;
    t0 = -1;
    clearTimeout(bailout);
  };
  const fontsReady = document.fonts ? document.fonts.ready : Promise.resolve();
  Promise.race([fontsReady, new Promise((r) => setTimeout(r, 2500))]).then(go).catch(() => root.classList.remove("px-live"));
  let rt = 0, lastW = innerWidth;
  addEventListener("resize", () => {
    clearTimeout(rt);
    rt = window.setTimeout(() => {
      layout();
      if (Math.abs(innerWidth - lastW) > 40 || !mobile) { lastW = innerWidth; build(); }
      gfx.resize();
    }, 220);
  });
  addEventListener("load", () => { if (ready) { layout(); if (document.querySelector("[data-form='image']")) build(); } });
  if ("ResizeObserver" in window) new ResizeObserver(() => { if (ready) layout(); }).observe(document.body);
}

// ==================================================================== helpers

function mkForm(N: number, clusters = false): Form {
  return { x: new Float32Array(N), y: new Float32Array(N), a: new Float32Array(N), h: new Float32Array(N), w: new Float32Array(N), c: clusters ? new Int16Array(N) : undefined };
}
function swap(a: Float32Array, i: number, j: number) { const t = a[i]; a[i] = a[j]; a[j] = t; }

const INK = "rgba(0,0,0,", HOT = "rgba(255,0,0,";

/** Draw an element's text at its laid-out position (every word where the browser put it), in its own font. */
function drawText(ctx: CanvasRenderingContext2D, el: HTMLElement, sr: DOMRect, halo: number, cluster: number) {
  const range = document.createRange();
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement!;
    const cs = getComputedStyle(parent);
    const hot = !!parent.closest("em");
    const size = parseFloat(cs.fontSize);
    ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    (ctx as any).letterSpacing = cs.letterSpacing === "normal" ? "0px" : cs.letterSpacing;
    const col = (hot ? "rgba(255," : "rgba(0,") + (8 + cluster * 16) + ",0,";
    ctx.fillStyle = col + "1)";
    ctx.strokeStyle = col + "1)";
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(1, size * halo);
    const text = node.textContent || "";
    const re = /\S+/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
      range.setStart(node, m.index); range.setEnd(node, m.index + m[0].length);
      const r = range.getClientRects()[0];
      if (!r) continue;
      let word = m[0];
      if (cs.textTransform === "uppercase") word = word.toUpperCase();
      const asc = ctx.measureText(word).fontBoundingBoxAscent || size * 0.9;
      const x = r.left - sr.left, y = r.top - sr.top + asc;
      ctx.fillText(word, x, y);
      if (halo > 0) ctx.strokeText(word, x, y);
    }
  }
}

function rr(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  if ((ctx as any).roundRect) (ctx as any).roundRect(x, y, w, h, r);
  else ctx.rect(x, y, w, h);
}

function drawPhone(ctx: CanvasRenderingContext2D, el: HTMLElement, sr: DOMRect) {
  const rel = (e: Element) => { const r = e.getBoundingClientRect(); return { x: r.left - sr.left, y: r.top - sr.top, w: r.width, h: r.height }; };
  const ph = el.querySelector(".ss-phone") || el;
  const p = rel(ph);
  ctx.lineWidth = Math.max(3, p.w * 0.018); ctx.strokeStyle = INK + "1)";
  rr(ctx, p.x, p.y, p.w, p.h, p.w * 0.15); ctx.stroke();
  ctx.fillStyle = INK + "0.07)"; ctx.fill();
  const scr = el.querySelector(".ss-phone__screen");
  if (scr) { const s = rel(scr); ctx.lineWidth = 1.2; ctx.strokeStyle = INK + "0.45)"; rr(ctx, s.x, s.y, s.w, s.h, s.w * 0.13); ctx.stroke(); }
  const notch = el.querySelector(".ss-phone__bar i");
  if (notch) { const n = rel(notch); ctx.fillStyle = INK + "1)"; rr(ctx, n.x, n.y, n.w, n.h, n.h / 2); ctx.fill(); }
  const media = el.querySelector(".ss-phone__screen > img, .ss-phone__screen > video");
  if (media) { const m = rel(media); ctx.fillStyle = INK + "0.3)"; ctx.fillRect(m.x, m.y, m.w, m.h); }
  el.querySelectorAll<HTMLElement>(".ss-app__opt").forEach((o) => {
    const r = rel(o), on = o.classList.contains("is-on");
    ctx.lineWidth = on ? 2.2 : 1.2; ctx.strokeStyle = (on ? HOT : INK) + (on ? "1)" : "0.7)");
    rr(ctx, r.x, r.y, r.w, r.h, 12); ctx.stroke();
    if (on) { ctx.fillStyle = HOT + "0.3)"; ctx.fill(); }
  });
  el.querySelectorAll<HTMLElement>(".ss-app__btn").forEach((o) => { const r = rel(o); ctx.fillStyle = INK + "0.9)"; rr(ctx, r.x, r.y, r.w, r.h, r.h / 2); ctx.fill(); });
  el.querySelectorAll<HTMLElement>(".ss-app__title, .ss-app__name, .ss-app__label, .ss-app__note, .ss-app__opt b, .ss-phone__bar span").forEach((t) => drawText(ctx, t, sr, 0.04, 0));
}

function drawImage(ctx: CanvasRenderingContext2D, img: HTMLImageElement, r: { x: number; y: number; w: number; h: number }, S: number) {
  if (!img.complete || !img.naturalWidth) { drawBox(ctx, r); return; }
  try {
    const c = document.createElement("canvas");
    const w = Math.max(2, Math.round(r.w * S)), h = Math.max(2, Math.round(r.h * S));
    c.width = w; c.height = h;
    const x = c.getContext("2d", { willReadFrequently: true })!;
    // object-fit: contain/cover is approximated as cover
    const ir = img.naturalWidth / img.naturalHeight, br = w / h;
    let sw = img.naturalWidth, sh = img.naturalHeight, sx0 = 0, sy0 = 0;
    if (getComputedStyle(img).objectFit === "contain") {
      const dw = ir > br ? w : h * ir, dh = ir > br ? w / ir : h;
      x.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
    } else {
      if (ir > br) { sw = sh * br; sx0 = (img.naturalWidth - sw) / 2; } else { sh = sw / br; sy0 = (img.naturalHeight - sh) / 2; }
      x.drawImage(img, sx0, sy0, sw, sh, 0, 0, w, h);
    }
    const d = x.getImageData(0, 0, w, h);
    for (let i = 0; i < d.data.length; i += 4) {
      const lum = (0.2126 * d.data[i] + 0.7152 * d.data[i + 1] + 0.0722 * d.data[i + 2]) / 255;
      const a = d.data[i + 3] / 255 * (0.05 + 0.95 * Math.pow(1 - lum, 1.3));
      d.data[i] = 0; d.data[i + 1] = 8; d.data[i + 2] = 0; d.data[i + 3] = Math.round(a * 255);
    }
    x.putImageData(d, 0, 0);
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(c, Math.round(r.x * S), Math.round(r.y * S)); ctx.restore();
  } catch { drawBox(ctx, r); }
}

function drawBox(ctx: CanvasRenderingContext2D, r: { x: number; y: number; w: number; h: number }) {
  ctx.lineWidth = 2.5; ctx.strokeStyle = INK + "1)"; ctx.strokeRect(r.x, r.y, r.w, r.h);
  ctx.fillStyle = INK + "0.1)"; ctx.fillRect(r.x, r.y, r.w, r.h);
}

/** Loose icon shapes for feature clusters, cycling through eight. The green channel carries the cluster id. */
function drawIcon(ctx: CanvasRenderingContext2D, k: number, r: { x: number; y: number; w: number; h: number }, cluster: number) {
  const s = Math.min(r.w, r.h) * 0.84, cy = r.y + r.h / 2;
  const left = r.w > r.h * 1.2;   // in a wide slot the icon sits at the start (aligned with the text)
  const x0 = left ? r.x + s / 2 : r.x + r.w / 2, y0 = cy;
  const col = "rgba(0," + (8 + cluster * 16) + ",0,";
  ctx.strokeStyle = col + "1)"; ctx.fillStyle = col + "0.16)";
  ctx.lineWidth = Math.max(2, s * 0.075); ctx.lineCap = "round"; ctx.lineJoin = "round";
  const R0 = s / 2;
  ctx.beginPath();
  switch (k % 8) {
    case 0: ctx.arc(x0, y0, R0 * 0.9, 0, TAU); ctx.stroke(); ctx.fill(); ctx.beginPath(); ctx.arc(x0, y0, R0 * 0.2, 0, TAU); ctx.fillStyle = col + "1)"; ctx.fill(); break;
    case 1: for (let q = 0; q < 3; q++) { ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x0 - R0 * (0.95 - q * 0.08), y0 - R0 * 0.8 + q * R0 * 0.62, R0 * (1.9 - q * 0.5), R0 * 0.36, R0 * 0.18) : ctx.rect(x0 - R0, y0 - R0 * 0.8 + q * R0 * 0.62, R0 * 1.9, R0 * 0.36); ctx.stroke(); } break;
    case 2: ctx.moveTo(x0, y0 - R0 * 0.95); ctx.lineTo(x0 + R0 * 0.9, y0 + R0 * 0.7); ctx.lineTo(x0 - R0 * 0.9, y0 + R0 * 0.7); ctx.closePath(); ctx.stroke(); ctx.fill(); break;
    case 3: for (let a = 0; a < TAU * 2.6; a += 0.05) { const rr2 = R0 * 0.08 + a / (TAU * 2.6) * R0 * 0.85; const X = x0 + Math.cos(a) * rr2, Y = y0 + Math.sin(a) * rr2; a ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); } ctx.stroke(); break;
    case 4: for (let q = 0; q < 6; q++) { const a = q / 6 * TAU - Math.PI / 2; const X = x0 + Math.cos(a) * R0 * 0.92, Y = y0 + Math.sin(a) * R0 * 0.92; q ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); } ctx.closePath(); ctx.stroke(); ctx.fill(); break;
    case 5: for (let q = 0; q < 10; q++) { const a = q / 10 * TAU - Math.PI / 2, rr2 = q % 2 ? R0 * 0.42 : R0 * 0.95; const X = x0 + Math.cos(a) * rr2, Y = y0 + Math.sin(a) * rr2; q ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); } ctx.closePath(); ctx.stroke(); ctx.fill(); break;
    case 6: for (let q = 1; q <= 3; q++) { ctx.beginPath(); ctx.arc(x0, y0 + R0 * 0.6, R0 * 0.38 * q, -Math.PI * 0.82, -Math.PI * 0.18); ctx.stroke(); } ctx.beginPath(); ctx.arc(x0, y0 + R0 * 0.6, R0 * 0.12, 0, TAU); ctx.fillStyle = col + "1)"; ctx.fill(); break;
    default: ctx.moveTo(x0 - R0 * 0.85, y0); ctx.lineTo(x0 + R0 * 0.85, y0); ctx.moveTo(x0, y0 - R0 * 0.85); ctx.lineTo(x0, y0 + R0 * 0.85); ctx.stroke(); ctx.beginPath(); ctx.arc(x0, y0, R0 * 0.95, 0, TAU); ctx.lineWidth *= 0.5; ctx.stroke();
  }
}

/** A stat's value as big digits fitted into the matter box (the unit set smaller beside it, in the accent). */
function drawDigits(ctx: CanvasRenderingContext2D, value: string, unit: string, b: { x: number; y: number; w: number; h: number }) {
  const fam = getComputedStyle(document.documentElement).getPropertyValue("--font-display") || "sans-serif";
  let size = b.h * 0.95;
  const fit = () => {
    ctx.font = `400 ${size}px ${fam}`;
    const wv = ctx.measureText(value).width;
    ctx.font = `400 ${size * 0.36}px ${fam}`;
    const wu = unit ? ctx.measureText(unit).width + size * 0.06 : 0;
    return wv + wu;
  };
  (ctx as any).letterSpacing = "0px";
  let w = fit();
  if (w > b.w * 0.96) { size *= (b.w * 0.96) / w; w = fit(); }
  const x = b.x + (b.w - w) / 2, base = b.y + b.h / 2 + size * 0.36;
  ctx.font = `400 ${size}px ${fam}`;
  ctx.fillStyle = INK + "1)"; ctx.strokeStyle = INK + "1)"; ctx.lineWidth = size * 0.035; ctx.lineJoin = "round";
  ctx.fillText(value, x, base); ctx.strokeText(value, x, base);
  if (unit) {
    const wv = ctx.measureText(value).width;
    ctx.font = `400 ${size * 0.36}px ${fam}`;
    ctx.fillStyle = HOT + "1)"; ctx.strokeStyle = HOT + "1)"; ctx.lineWidth = size * 0.02;
    ctx.fillText(unit, x + wv + size * 0.06, base - size * 0.42); ctx.strokeText(unit, x + wv + size * 0.06, base - size * 0.42);
  }
}

// ==================================================================== rendering: soft round points, ink on paper

function makeRenderer(canvas: HTMLCanvasElement, N: number, z: Float32Array, mobile: boolean) {
  const css = getComputedStyle(document.documentElement);
  const hex = (v: string, d: [number, number, number]): [number, number, number] => {
    const m = v.trim().match(/^#?([0-9a-f]{6})$/i);
    if (!m) return d;
    const n = parseInt(m[1], 16);
    return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255];
  };
  const ink = hex(css.getPropertyValue("--ink"), [0.08, 0.08, 0.08]);
  const hot = hex(css.getPropertyValue("--accent"), [1, 0.3, 0.18]);
  const dpr = Math.min(devicePixelRatio || 1, mobile ? 2 : 1.75);
  const gl = canvas.getContext("webgl", { antialias: false, alpha: true, premultipliedAlpha: true, powerPreference: "high-performance" });
  const resize = () => {
    canvas.width = Math.round(innerWidth * dpr); canvas.height = Math.round(innerHeight * dpr);
    if (gl) gl.viewport(0, 0, canvas.width, canvas.height);
  };
  resize();
  if (!gl) {
    // canvas 2D fallback: every fourth point, as small squares
    const ctx = canvas.getContext("2d")!;
    const col = (c: [number, number, number], a: number) => `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${a.toFixed(2)})`;
    return {
      resize,
      draw(buf: Float32Array, alpha: number) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, innerWidth, innerHeight);
        for (let i = 0; i < N; i += 3) {
          const s = 1.2 + 1.4 * z[i];
          ctx.fillStyle = col(buf[i * 4 + 3] > 0.5 ? hot : ink, buf[i * 4 + 2] * alpha);
          ctx.fillRect(buf[i * 4] - s / 2, buf[i * 4 + 1] - s / 2, s, s);
        }
      },
    };
  }
  const vs = `attribute vec4 aP; attribute float aS; uniform vec2 uRes; uniform float uDpr; varying float vA; varying float vH;
    void main(){ vec2 p = aP.xy / uRes * 2.0 - 1.0; gl_Position = vec4(p.x, -p.y, 0.0, 1.0); gl_PointSize = aS * uDpr; vA = aP.z; vH = aP.w; }`;
  const fs = `precision mediump float; varying float vA; varying float vH; uniform vec3 uInk; uniform vec3 uHot; uniform float uAlpha;
    void main(){ float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.18, d) * vA * uAlpha; vec3 c = mix(uInk, uHot, step(0.5, vH)); gl_FragColor = vec4(c * a, a); }`;
  const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s; };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(prog); gl.useProgram(prog);
  const sizes = new Float32Array(N);
  for (let i = 0; i < N; i++) sizes[i] = (mobile ? 1.15 : 1.25) + (mobile ? 1.3 : 1.6) * z[i];
  const bS = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, bS); gl.bufferData(gl.ARRAY_BUFFER, sizes, gl.STATIC_DRAW);
  const aS = gl.getAttribLocation(prog, "aS"); gl.enableVertexAttribArray(aS); gl.vertexAttribPointer(aS, 1, gl.FLOAT, false, 0, 0);
  const bP = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, bP); gl.bufferData(gl.ARRAY_BUFFER, N * 16, gl.DYNAMIC_DRAW);
  const aP = gl.getAttribLocation(prog, "aP"); gl.enableVertexAttribArray(aP); gl.vertexAttribPointer(aP, 4, gl.FLOAT, false, 0, 0);
  const uRes = gl.getUniformLocation(prog, "uRes"), uDpr = gl.getUniformLocation(prog, "uDpr"), uAlpha = gl.getUniformLocation(prog, "uAlpha");
  gl.uniform3fv(gl.getUniformLocation(prog, "uInk"), ink); gl.uniform3fv(gl.getUniformLocation(prog, "uHot"), hot);
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.clearColor(0, 0, 0, 0);
  return {
    resize,
    draw(buf: Float32Array, alpha: number) {
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform2f(uRes, innerWidth, innerHeight); gl.uniform1f(uDpr, dpr); gl.uniform1f(uAlpha, alpha);
      gl.bindBuffer(gl.ARRAY_BUFFER, bP); gl.bufferSubData(gl.ARRAY_BUFFER, 0, buf);
      gl.drawArrays(gl.POINTS, 0, N);
    },
  };
}
