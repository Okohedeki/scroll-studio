/**
 * Liquid morph: one canvas paints the whole fluid. Each section is a region of colour; the edges between regions are
 * wobbling menisci that bulge as they cross the screen and with scroll speed. One protagonist blob (smooth-union
 * metaballs, glossy candy) morphs into each section's idea as the boundary passes mid-screen; scroll velocity drives a
 * damped spring that stretches it along the scroll axis and makes it ripple, then wobble back. Stats are droplets that
 * divide out of one drop; features are milk droplets in a fusion carousel, joined by necks; the pointer is a small
 * droplet that merges with the blob. Headings melt in and end crisp. Reduced motion: static shapes, 200 ms crossfades
 * between end shapes, no velocity deformation, no wobble.
 */
import { $, $$, onFrame, onSeen, chars, reduced, pinned } from "./_kit";
import { clamp } from "../lib/util";

type Ball = { x: number; y: number; r: number; m: number };
type Sec = { el: HTMLElement; type: string; top: number; h: number; color: [number, number, number] };
const sstep = (a: number, b: number, v: number) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
const MAXB = 18, PROT = 6;

export default function start() {
  const root = document.documentElement;
  root.classList.add("lq-live");
  const mobile = () => innerWidth < 760;

  // ---------------------------------------------------------------- regions (sections + the footer pool)
  const els: HTMLElement[] = [];
  $$<HTMLElement>("main > *").forEach((c) => {
    const s = c.matches("section") ? c : c.querySelector<HTMLElement>(":scope > section") || c;
    els.push(s);
  });
  const foot = $<HTMLElement>(".ss-footer");
  if (foot) els.push(foot);
  const parse = (c: string): [number, number, number] | null => {
    const m = c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/);
    if (!m || (m[4] !== undefined && parseFloat(m[4]) < 0.5)) return null;
    return [+m[1] / 255, +m[2] / 255, +m[3] / 255];
  };
  const page = parse(getComputedStyle(document.body).backgroundColor) || [1, 0.957, 0.925];
  const secs: Sec[] = els.map((el) => ({ el, type: el.dataset.lq || (el === foot ? "footer" : "other"), top: 0, h: 0, color: parse(getComputedStyle(el).backgroundColor) || page }));

  let vw = innerWidth, vh = innerHeight;
  function layout() {
    vw = innerWidth; vh = innerHeight;
    for (const s of secs) { s.top = s.el.getBoundingClientRect().top + scrollY; s.h = s.el.offsetHeight; }
  }

  // ---------------------------------------------------------------- melting headings
  $$<HTMLElement>(".lq-melt").forEach((h) => {
    if (reduced) return;
    chars(h);
    onSeen(h, () => h.classList.add("is-in"), 0.2);
  });

  // ---------------------------------------------------------------- features: the fusion carousel
  const feats = $$<HTMLElement>(".lq-features").map((sec) => ({
    sec, drops: $$<HTMLElement>(".lq-drop", sec), hint: $<HTMLElement>(".lq-features__hint span", sec), pos: 0, shown: -1,
  }));
  feats.forEach((f) => f.drops.forEach((d, i) => {
    const go = () => {
      const n = f.drops.length, r = f.sec.getBoundingClientRect(), L = r.height - innerHeight;
      const p = n > 1 ? 0.08 + 0.84 * (i / (n - 1)) : 0.5;
      scrollTo({ top: r.top + scrollY + L * p, behavior: reduced ? "auto" : "smooth" });
    };
    d.addEventListener("click", go);
    d.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  }));
  function updateFeatures() {
    for (const f of feats) {
      const r = f.sec.getBoundingClientRect();
      if (r.bottom < -50 || r.top > vh + 50) continue;
      const n = f.drops.length, p = pinned(f.sec);
      const pos = reduced ? Math.round(clamp((p - 0.08) / 0.84) * (n - 1)) : clamp((p - 0.08) / 0.84) * (n - 1);
      f.pos = pos;
      const D = f.drops[0] ? f.drops[0].offsetWidth : 400;
      f.drops.forEach((d, i) => {
        const dl = i - pos, ad = Math.abs(dl);
        const s = 1 - 0.5 * Math.min(1, ad) - 0.12 * Math.max(0, Math.min(2, ad - 1));
        const x = Math.sign(dl) * (Math.min(1, ad) * D * 0.775 + Math.max(0, ad - 1) * D * 0.5);
        d.style.setProperty("--x", x.toFixed(1) + "px");
        d.style.setProperty("--s", s.toFixed(3));
        d.style.setProperty("--b", clamp(1 - ad * 2.2).toFixed(2));
        d.setAttribute("aria-current", ad < 0.5 ? "true" : "false");
      });
      const cur = Math.round(pos);
      if (cur !== f.shown && f.hint) { f.shown = cur; f.hint.textContent = String(cur + 1).padStart(2, "0"); }
    }
  }

  // ---------------------------------------------------------------- stats: one drop divides
  const stats = $$<HTMLElement>(".lq-stats").map((sec) => ({
    sec, stage: $<HTMLElement>(".lq-stats__stage", sec)!, cells: $$<HTMLElement>(".lq-cell", sec), d: 1,
    vals: $$<HTMLElement>(".lq-cell__v", sec).map((v) => ({ b: v.querySelector("b")!, n: v.dataset.n ? parseFloat(v.dataset.n) : NaN, raw: v.querySelector("b")!.textContent || "", dec: (v.dataset.n || "").split(".")[1]?.length || 0, shown: "" })),
  }));
  function updateStats() {
    for (const st of stats) {
      const r = st.sec.getBoundingClientRect();
      if (r.bottom < -50 || r.top > vh + 50) continue;
      const q = pinned(st.sec);
      const d = reduced ? 1 : sstep(0.1, 0.62, q);
      st.d = d;
      const sr = st.stage.getBoundingClientRect(), cx = sr.left + sr.width / 2, cy = sr.top + sr.height / 2;
      st.cells.forEach((c, i) => {
        const cr = c.getBoundingClientRect(), drop = c.firstElementChild as HTMLElement;
        drop.style.setProperty("--dx", ((cx - (cr.left + cr.width / 2)) * (1 - d)).toFixed(1) + "px");
        drop.style.setProperty("--dy", ((cy - (cr.top + cr.height / 2)) * (1 - d)).toFixed(1) + "px");
        drop.style.setProperty("--ds", (0.34 + 0.66 * d).toFixed(3));
        drop.style.setProperty("--do", sstep(0.5, 0.88, d).toFixed(2));
        const v = st.vals[i];
        if (v) {
          let txt = v.raw;
          if (!isNaN(v.n) && d < 1) { txt = (v.n * sstep(0.45, 0.95, d)).toFixed(v.dec); if (v.raw.includes(",")) txt = Number(txt).toLocaleString("en-US"); }
          if (txt !== v.shown) { v.b.textContent = txt; v.shown = txt; }
        }
      });
    }
  }

  // ---------------------------------------------------------------- timeline: a stream that lands each step
  const flows = $$<HTMLElement>(".lq-stream").map((ol) => ({ ol, svg: null as SVGSVGElement | null, path: null as SVGPathElement | null, head: null as SVGCircleElement | null, samples: [] as { l: number; y: number }[], len: 0, nodes: [] as number[], items: $$<HTMLElement>(".lq-landing", ol), landed: [] as boolean[] }));
  const NS = "http://www.w3.org/2000/svg";
  function buildFlows() {
    for (const f of flows) {
      f.svg?.remove();
      const or = f.ol.getBoundingClientRect();
      const pts = $$<HTMLElement>(".lq-landing__drop", f.ol).map((d) => { const r = d.getBoundingClientRect(); return { x: r.left + r.width / 2 - or.left, y: r.top + r.height / 2 - or.top }; });
      if (!pts.length) continue;
      const W = or.width, H = or.height;
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", "lq-flow"); svg.setAttribute("width", String(W)); svg.setAttribute("height", String(H));
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("aria-hidden", "true");
      const id = "lqg" + Math.random().toString(36).slice(2, 7);
      svg.innerHTML = `<defs><linearGradient id="${id}c" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffb86b"/><stop offset=".5" stop-color="#ff6b9a"/><stop offset="1" stop-color="#8b7bff"/></linearGradient>
        <filter id="${id}g" x="-50%" y="-5%" width="200%" height="110%"><feGaussianBlur stdDeviation="6"/><feColorMatrix values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 22 -9"/></filter></defs>`;
      let d = `M ${pts[0].x} 0`;
      let prev = { x: pts[0].x, y: 0 };
      const sway = Math.min(70, W * 0.08);
      pts.forEach((p, i) => {
        const dy = p.y - prev.y, s = (i % 2 ? 1 : -1) * sway;
        d += ` C ${prev.x + s} ${prev.y + dy * 0.4}, ${p.x + s} ${p.y - dy * 0.4}, ${p.x} ${p.y}`;
        prev = p;
      });
      d += ` C ${prev.x - sway} ${prev.y + 60}, ${prev.x} ${H - 40}, ${prev.x} ${H}`;
      const track = document.createElementNS(NS, "path");
      track.setAttribute("d", d); track.setAttribute("fill", "none"); track.setAttribute("stroke", `rgba(27,21,48,.1)`); track.setAttribute("stroke-width", "10"); track.setAttribute("stroke-linecap", "round");
      const g = document.createElementNS(NS, "g");
      g.setAttribute("filter", `url(#${id}g)`);
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", d); path.setAttribute("fill", "none"); path.setAttribute("stroke", `url(#${id}c)`); path.setAttribute("stroke-width", "11"); path.setAttribute("stroke-linecap", "round");
      const head = document.createElementNS(NS, "circle");
      head.setAttribute("r", "15"); head.setAttribute("fill", "#ff6b9a");
      g.appendChild(path); g.appendChild(head);
      svg.appendChild(track); svg.appendChild(g);
      f.ol.prepend(svg);
      const len = path.getTotalLength();
      path.style.strokeDasharray = `${len} ${len}`;
      f.samples = [];
      for (let k = 0; k <= 160; k++) { const l = len * k / 160; f.samples.push({ l, y: path.getPointAtLength(l).y }); }
      f.nodes = pts.map((p) => { let best = 0, bd = 1e9; for (const s of f.samples) { const pp = path.getPointAtLength(s.l); const dd = Math.hypot(pp.x - p.x, pp.y - p.y); if (dd < bd) { bd = dd; best = s.l; } } return best; });
      f.svg = svg; f.path = path; f.head = head; f.len = len; f.landed = f.items.map(() => false);
    }
  }
  function updateFlows() {
    for (const f of flows) {
      if (!f.path || !f.head) continue;
      const or = f.ol.getBoundingClientRect();
      if (or.bottom < -100 || or.top > vh + 100) continue;
      const yy = reduced ? 1e9 : vh * 0.64 - or.top;
      let l = f.len;
      if (yy < f.samples[f.samples.length - 1].y) { l = 0; for (const s of f.samples) { if (s.y <= yy) l = s.l; else break; } }
      if (yy <= 0) l = 0;
      f.path.style.strokeDashoffset = String(f.len - l);
      const p = f.path.getPointAtLength(Math.max(0.01, l));
      f.head.setAttribute("cx", p.x.toFixed(1)); f.head.setAttribute("cy", p.y.toFixed(1));
      f.head.setAttribute("r", l <= 0.5 || l >= f.len - 1 ? "0" : "15");
      f.nodes.forEach((nl, i) => {
        const on = l >= nl - 6;
        if (on !== f.landed[i]) { f.landed[i] = on; f.items[i].classList.toggle("is-landed", on); }
      });
    }
  }

  // ---------------------------------------------------------------- faq: answers spring open, membranes bend
  const membranes: { path: SVGPathElement; b: number; v: number }[] = [];
  $$<HTMLDetailsElement>(".lq-q").forEach((d, i, all) => {
    const path = d.querySelector<SVGPathElement>(".lq-q__membrane path");
    const m = path ? { path, b: 0, v: 0 } : null;
    if (m) membranes.push(m);
    const ans = d.querySelector<HTMLElement>(".lq-q__a");
    const sum = d.querySelector("summary");
    if (!ans || !sum || reduced) return;
    let anim = 0;
    sum.addEventListener("click", (e) => {
      e.preventDefault();
      cancelAnimationFrame(anim);
      const next = all[i + 1]?.querySelector<SVGPathElement>(".lq-q__membrane path");
      const kick = (p: SVGPathElement | null | undefined, v: number) => { const mm = membranes.find((x) => x.path === p); if (mm) mm.v += v; };
      if (d.open) {
        const h0 = ans.offsetHeight; let t0 = 0;
        const step = (now: number) => { t0 ||= now; const k = clamp((now - t0) / 260); ans.style.height = (h0 * (1 - k * k)).toFixed(1) + "px"; if (k < 1) anim = requestAnimationFrame(step); else { d.open = false; ans.style.height = ""; } };
        anim = requestAnimationFrame(step);
        kick(next, -160);
      } else {
        d.open = true;
        const h = ans.scrollHeight; let x = 0, v = 0, last = 0;
        ans.style.height = "0px";
        const step = (now: number) => {
          const dt = last ? Math.min(0.033, (now - last) / 1000) : 0.016; last = now;
          v += (170 * (h - x) - 13 * v) * dt; x += v * dt;
          ans.style.height = Math.max(0, x).toFixed(1) + "px";
          if (Math.abs(h - x) > 0.5 || Math.abs(v) > 2) anim = requestAnimationFrame(step); else ans.style.height = "";
        };
        anim = requestAnimationFrame(step);
        kick(path, 140); kick(next, 260);
      }
    });
  });
  function updateMembranes(dt: number) {
    for (const m of membranes) {
      if (Math.abs(m.b) < 0.05 && Math.abs(m.v) < 0.05) continue;
      m.v += (-200 * m.b - 9 * m.v) * dt; m.b += m.v * dt;
      m.path.setAttribute("d", `M0 10 Q50 ${(10 + m.b).toFixed(2)} 100 10`);
    }
  }

  // ---------------------------------------------------------------- nav: a gooey pill that stretches between links
  const links = $$<HTMLAnchorElement>(".ss-nav__links a[href^='#']");
  const targets = links.map((a) => document.getElementById(a.getAttribute("href")!.slice(1)));
  const pill = document.createElement("i");
  pill.className = "lq-pill"; pill.setAttribute("aria-hidden", "true");
  links[0]?.parentElement?.prepend(pill);
  let pl = 0, pr = 0, plv = 0, prv = 0, pillInit = false, navOn = -1;
  function updateNav(dt: number) {
    if (!links.length) return;
    let on = -1;
    targets.forEach((t, i) => { if (t && t.getBoundingClientRect().top < vh * 0.5) on = i; });
    if (on !== navOn) { navOn = on; links.forEach((a, i) => a.classList.toggle("is-on", i === on)); pill.classList.toggle("is-on", on >= 0); }
    if (on < 0) return;
    const a = links[on], L = a.offsetLeft, R = L + a.offsetWidth;
    if (!pillInit || reduced) { pl = L; pr = R; pillInit = true; }
    const right = R > pr;   // moving right: the right edge leads
    const kl = right ? 70 : 260, kr = right ? 260 : 70;
    plv += (kl * (L - pl) - 2 * Math.sqrt(kl) * plv) * dt; pl += plv * dt;
    prv += (kr * (R - pr) - 2 * Math.sqrt(kr) * prv) * dt; pr += prv * dt;
    pill.style.left = pl.toFixed(1) + "px"; pill.style.width = Math.max(0, pr - pl).toFixed(1) + "px";
  }

  // ---------------------------------------------------------------- magnetic buttons
  const mags = $$<HTMLElement>(".lq-btn, .ss-nav .ss-btn");
  let mx = -1e4, my = -1e4, ptrOn = false;
  addEventListener("pointermove", (e) => {
    mx = e.clientX; my = e.clientY; ptrOn = e.pointerType === "mouse" || e.pointerType === "pen";
    if (reduced || !ptrOn) return;
    for (const b of mags) {
      const r = b.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const near = mx > r.left - 50 && mx < r.right + 50 && my > r.top - 50 && my < r.bottom + 50;
      b.style.setProperty("--tx", near ? clamp((mx - cx) * 0.22, -12, 12).toFixed(1) + "px" : "0px");
      b.style.setProperty("--ty", near ? clamp((my - cy) * 0.3, -9, 9).toFixed(1) + "px" : "0px");
    }
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => { ptrOn = false; });

  // ---------------------------------------------------------------- protagonist shapes
  const lerpB = (a: Ball, b: Ball, t: number): Ball => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, r: a.r + (b.r - a.r) * t, m: a.m + (b.m - a.m) * t });
  function shape(s: Sec): Ball[] {
    const W = vw, H = vh, M = Math.min(W, H), mob = mobile();
    const B = (x: number, y: number, r: number, m = 0): Ball => ({ x, y, r, m });
    const rect = s.el.getBoundingClientRect();
    switch (s.type) {
      case "hero": {
        const cx = mob ? W * 0.66 : W * 0.75, cy = mob ? H * 0.27 : H * 0.5, R0 = mob ? W * 0.3 : M * 0.27;
        return [B(cx, cy, R0), B(cx + R0 * 0.35, cy - R0 * 0.42, R0 * 0.62), B(cx - R0 * 0.4, cy + R0 * 0.38, R0 * 0.66), B(cx - R0 * 0.62, cy + R0 * 1.12, R0 * 0.2), B(cx + R0 * 0.9, cy - R0 * 0.95, R0 * 0.14), B(cx, cy, R0 * 0.5)];
      }
      case "intro": {
        const cx = mob ? W * 0.3 : W * 0.19, cy = mob ? H * 0.2 : H * 0.36, R0 = mob ? W * 0.2 : M * 0.15;
        return [B(cx, cy, R0), B(cx, cy + R0 * 1.25, R0 * 0.55), B(cx, cy + R0 * 2.05, R0 * 0.3), B(cx - R0 * 0.32, cy - R0 * 0.18, R0 * 0.72), B(cx + R0 * 0.34, cy - R0 * 0.1, R0 * 0.7), B(cx, cy + R0 * 2.6, R0 * 0.16)];
      }
      case "features": {
        const st = s.el.querySelector<HTMLElement>(".lq-features__stage") || s.el;
        const sr = st.getBoundingClientRect(), r = M * (mob ? 0.05 : 0.045);
        const D0 = (s.el.querySelector<HTMLElement>(".lq-drop")?.offsetWidth || 360);
        const yy = sr.top + Math.min(sr.height, H) * (mob ? 0.64 : 0.62) + D0 * 0.5;
        return [-0.06, 0.18, 0.4, 0.6, 0.82, 1.06].map((u, i) => B(W * u, yy + Math.sin(i * 1.9) * r * 0.6, r * (i % 2 ? 1.15 : 0.9)));
      }
      case "product": {
        const m = s.el.querySelector<HTMLElement>("[data-lq-anchor]");
        const r = m ? m.getBoundingClientRect() : rect;
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2, R0 = mob ? W * 0.36 : M * 0.3;
        return [B(cx, cy, R0), B(cx - R0 * 0.42, cy + R0 * 0.36, R0 * 0.72), B(cx + R0 * 0.38, cy - R0 * 0.42, R0 * 0.66), B(cx + R0 * 0.5, cy + R0 * 0.5, R0 * 0.45), B(cx - R0 * 0.8, cy - R0 * 0.72, R0 * 0.16), B(cx + R0 * 1.02, cy + R0 * 0.92, R0 * 0.12)];
      }
      case "stats": {
        const st = stats.find((x) => x.sec === s.el);
        const sr = st ? st.stage.getBoundingClientRect() : rect;
        const cx = sr.left + sr.width / 2, cy = sr.top + Math.min(sr.height, H) / 2, d = st ? st.d : 1, R0 = M * 0.17 * Math.pow(1 - d, 1.4);
        return [B(cx, cy, R0), B(cx, cy, R0 * 0.8), B(cx + R0 * 0.2, cy, R0 * 0.7), B(cx - R0 * 0.2, cy, R0 * 0.7), B(cx, cy + R0 * 0.2, R0 * 0.6), B(cx, cy - R0 * 0.2, R0 * 0.6)];
      }
      case "timeline": {
        const cx = mob ? W * 1.08 : W * -0.02, cy = mob ? H * 0.9 : H * 0.5, R0 = mob ? W * 0.2 : M * 0.2;
        return [B(cx, cy, R0), B(cx, cy - R0 * 0.6, R0 * 0.7), B(cx, cy + R0 * 0.6, R0 * 0.7), B(cx + (mob ? -1 : 1) * R0 * 1.15, cy + R0 * 0.2, R0 * 0.2), B(cx + (mob ? -1 : 1) * R0 * 1.55, cy + R0 * 0.35, R0 * 0.1), B(cx, cy, R0 * 0.5)];
      }
      case "quote": {
        const f = s.el.querySelector<HTMLElement>(".lq-quote__blob");
        const r = f ? f.getBoundingClientRect() : rect;
        const rr = Math.max(r.height * 0.5, r.width * (mob ? 0.62 : 0.22));
        const xs = mob ? [0.5, 0.5, 0.5, 0.5] : [0.25, 0.43, 0.6, 0.77];
        const ys = mob ? [0.3, 0.45, 0.58, 0.72] : [0.5, 0.47, 0.53, 0.5];
        const rs = mob ? [r.width * 0.62, r.width * 0.6, r.width * 0.6, r.width * 0.55] : [rr * 0.9, rr, rr, rr * 0.9];
        return [...xs.map((u, i) => B(r.left + r.width * u, r.top + r.height * ys[i], rs[i], 1)),
          B(r.left + r.width * 0.2, r.bottom + M * 0.02, M * 0.05, 1), B(r.left + r.width * 0.13, r.bottom + M * 0.1, M * 0.026, 1)];
      }
      case "faq": {
        const R0 = M * (mob ? 0.16 : 0.14), y = H + R0 * 0.35;
        return [B(W * 0.08, y, R0), B(W * 0.3, y + R0 * 0.2, R0 * 1.1), B(W * 0.52, y, R0), B(W * 0.74, y + R0 * 0.15, R0 * 1.15), B(W * 0.96, y, R0), B(W * 0.86, y - R0 * 1.25, R0 * 0.2)];
      }
      case "cta": {
        const b = s.el.querySelector<HTMLElement>(".lq-btn") || s.el;
        const r = b.getBoundingClientRect(), R0 = Math.max(r.width * 0.42, M * 0.15), cx = r.left + r.width / 2, cy = r.top + r.height / 2 + R0 * 0.3;
        return [B(cx, cy + R0 * 0.1, R0), B(cx - R0 * 0.85, cy + R0 * 0.3, R0 * 0.62), B(cx + R0 * 0.9, cy + R0 * 0.2, R0 * 0.66), B(cx + R0 * 0.1, cy + R0 * 0.75, R0 * 0.6), B(cx - R0 * 1.55, cy - R0 * 0.3, R0 * 0.15), B(cx + R0 * 1.65, cy + R0 * 0.85, R0 * 0.12)];
      }
      case "footer": {
        const R0 = M * 0.1;
        return [0.12, 0.3, 0.5, 0.7, 0.88, 0.5].map((u, i) => B(W * u, rect.top - R0 * 0.2, i === 5 ? R0 * 0.4 : R0 * (0.8 + (i % 2) * 0.4)));
      }
      default: {
        const cx = W * 0.92, cy = H * 0.78, R0 = M * 0.08;
        return [B(cx, cy, R0), B(cx - R0 * 0.4, cy, R0 * 0.7), B(cx + R0 * 0.4, cy, R0 * 0.7), B(cx, cy - R0 * 0.3, R0 * 0.6), B(cx, cy + R0 * 0.3, R0 * 0.6), B(cx - R0 * 1.4, cy + R0, R0 * 0.2)];
      }
    }
  }

  // ---------------------------------------------------------------- the fluid renderer
  const canvas = $<HTMLCanvasElement>(".lq-canvas");
  const gl = canvas ? makeGL(canvas) : null;
  if (gl) root.classList.add("lq-gl");

  // spring state
  let sv = 0, svv = 0, rmT = -1, rmFrom: Ball[] | null = null, rmTo = -1, prevBase: Ball[] | null = null;
  let pX = -1e4, pY = -1e4, pR = 0;
  const balls = new Float32Array(MAXB * 4);

  layout();
  buildFlows();
  onFrame(({ y, v, dt, t }) => {
    dt = dt || 0.016;
    updateFeatures(); updateStats(); updateFlows(); updateMembranes(dt); updateNav(dt);
    if (!gl) return;
    // velocity spring: stretch, squash, wobble
    if (!reduced) {
      const target = clamp(v / 42, -1, 1) * 0.5;
      svv += (70 * (target - sv) - 7.5 * svv) * dt; sv += svv * dt;
    }
    const stretch = clamp(sv * 0.7, -0.32, 0.55);
    const ripple = Math.min(1.2, Math.abs(sv) * 2 + Math.abs(svv) * 0.12);

    // protagonist: the shape of the section at mid-screen, morphing as each boundary passes
    const yc = y + vh / 2, w = Math.min(vh * 0.45, 420);
    let i = 0;
    while (i < secs.length - 1 && yc >= secs[i + 1].top - w) i++;
    // i is the last section whose transition has started; t is its progress
    let base: Ball[];
    const tr = i > 0 ? sstep(secs[i].top - w, secs[i].top + w, yc) : 1;
    if (reduced) {
      const want = i > 0 && tr < 0.5 ? i - 1 : i;
      if (want !== rmTo) { rmFrom = prevBase; rmTo = want; rmT = 0; }
      rmT = Math.min(1, rmT + dt / 0.2);
      const target = shape(secs[want]);
      base = rmFrom ? target.map((b, k) => ({ ...b, r: rmT < 0.5 ? rmFrom![k].r * (1 - rmT * 2) : b.r * (rmT * 2 - 1), x: rmT < 0.5 ? rmFrom![k].x : b.x, y: rmT < 0.5 ? rmFrom![k].y : b.y, m: rmT < 0.5 ? rmFrom![k].m : b.m })) : target;
      prevBase = target;
    } else if (i > 0 && tr < 1) {
      const A = shape(secs[i - 1]), B = shape(secs[i]);
      const e = tr;
      base = A.map((a, k) => lerpB(a, B[k], sstep(k * 0.06, 0.7 + k * 0.06, e)));
    } else base = shape(secs[i]);

    let n = 0;
    const lag = reduced ? 0 : -sv * 30;
    for (let k = 0; k < PROT && n < MAXB; k++) { const b = base[k]; balls[n * 4] = b.x; balls[n * 4 + 1] = b.y + lag * (0.6 + k * 0.1); balls[n * 4 + 2] = Math.max(0, b.r); balls[n * 4 + 3] = b.m; n++; }
    // content droplets: carousel drops and stat cells, where they are on screen
    for (const f of feats) for (const d of f.drops) {
      if (n >= MAXB - 1) break;
      const r = d.getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh || r.right < -40 || r.left > vw + 40) continue;
      balls[n * 4] = r.left + r.width / 2; balls[n * 4 + 1] = r.top + r.height / 2; balls[n * 4 + 2] = r.width / 2; balls[n * 4 + 3] = 1; n++;
    }
    for (const st of stats) for (const c of st.cells) {
      if (n >= MAXB - 1) break;
      const r = (c.firstElementChild as HTMLElement).getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh) continue;
      balls[n * 4] = r.left + r.width / 2; balls[n * 4 + 1] = r.top + r.height / 2; balls[n * 4 + 2] = r.width / 2; balls[n * 4 + 3] = 1; n++;
    }
    // the pointer's droplet
    if (!reduced && ptrOn) { pX += (mx - pX) * Math.min(1, dt * 9); pY += (my - pY) * Math.min(1, dt * 9); pR += (17 - pR) * Math.min(1, dt * 6); }
    else pR += (0 - pR) * Math.min(1, dt * 6);
    if (pR > 0.5 && n < MAXB) { balls[n * 4] = pX; balls[n * 4 + 1] = pY; balls[n * 4 + 2] = pR; balls[n * 4 + 3] = 0; n++; }

    // region boundaries in view
    const bnd: number[] = [], bul: number[] = [], cols: number[] = [];
    let first = 0;
    for (let k = 1; k < secs.length; k++) if (secs[k].top - y < -160) first = k;
    cols.push(...secs[first].color);
    for (let k = first + 1; k < secs.length && bnd.length < 6; k++) {
      const by = secs[k].top - y;
      if (by > vh + 160) break;
      bnd.push(by);
      const rise = reduced ? 0 : -46 * Math.sin(Math.PI * clamp(by / vh));
      bul.push(rise + (reduced ? 0 : sv * 110));
      cols.push(...secs[k].color);
    }
    gl.draw({ t: reduced ? 0 : t, bnd, bul, cols, balls, n, stretch: reduced ? 0 : stretch, ripple: reduced ? 0 : ripple });
  });

  let rt = 0;
  addEventListener("resize", () => { clearTimeout(rt); rt = window.setTimeout(() => { layout(); buildFlows(); gl?.resize(); }, 200); });
  addEventListener("load", () => { layout(); buildFlows(); });
  if (document.fonts) document.fonts.ready.then(() => { layout(); buildFlows(); });
  if ("ResizeObserver" in window) { let q = 0; new ResizeObserver(() => { cancelAnimationFrame(q); q = requestAnimationFrame(layout); }).observe(document.body); }
}

// ==================================================================== WebGL: regions, menisci, metaballs

function makeGL(canvas: HTMLCanvasElement) {
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false, premultipliedAlpha: false, powerPreference: "high-performance" });
  if (!gl) return null;
  const mob = innerWidth < 760;
  let scale = Math.min(devicePixelRatio || 1, 2) * (mob ? 0.62 : 0.6);
  const resize = () => { canvas.width = Math.round(innerWidth * scale); canvas.height = Math.round(innerHeight * scale); gl.viewport(0, 0, canvas.width, canvas.height); };
  resize();
  const vs = `attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }`;
  const fs = `precision highp float;
  uniform vec2 uRes; uniform float uPx; uniform float uT; uniform vec2 uVW;
  uniform float uB[6]; uniform float uBul[6]; uniform vec3 uC[7]; uniform int uNB;
  uniform vec4 uBall[${MAXB}]; uniform int uN; uniform float uStr; uniform float uRip;
  float surf(float x, float fi, float bul){ return sin(x*0.0047 + uT*0.9 + fi*1.7)*12.0 + sin(x*0.0113 - uT*1.35 + fi)*5.0 + bul*exp(-pow((x - uVW.x*0.5)/(uVW.x*0.4), 2.0)); }
  float field(vec2 p, out float milk){
    float d = 1e4; float mw = 0.0; float tw = 0.0; const float K = 64.0;
    for (int i = 0; i < ${MAXB}; i++){
      if (i >= uN) break;
      vec4 b = uBall[i];
      if (b.z < 0.5) continue;
      vec2 q = p - b.xy;
      q.y /= (1.0 + uStr); q.x *= (1.0 + uStr*0.32);
      float di = length(q) - b.z;
      float fi = float(i);
      di += sin(q.x*0.045 + uT*3.1 + fi) * sin(q.y*0.05 - uT*2.3 + fi) * uRip * min(b.z, 130.0) * 0.12;
      di += sin(q.x*0.018 + uT*0.6 + fi*2.0) * sin(q.y*0.021 - uT*0.5) * min(b.z, 200.0) * 0.05;
      float h = clamp(0.5 + 0.5*(di - d)/K, 0.0, 1.0);
      d = mix(di, d, h) - K*h*(1.0 - h);
      float w = exp(clamp(-di, -120.0, 120.0) / 22.0);
      mw += w*b.w; tw += w;
    }
    milk = tw > 0.0 ? mw/tw : 0.0;
    return d;
  }
  void main(){
    vec2 p = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y) / uPx;
    // regions and their menisci
    vec3 col = uC[0];
    float edge = 1e4;
    for (int k = 0; k < 6; k++){
      if (k >= uNB) break;
      float e = p.y - (uB[k] + surf(p.x, float(k), uBul[k]));
      if (e > 0.0) { col = uC[k + 1]; }
      if (abs(e) < abs(edge)) edge = e;
    }
    if (edge > 0.0 && edge < 3.0) col = mix(col, vec3(1.0), 0.28 * (1.0 - edge/3.0));
    if (edge < 0.0 && edge > -22.0) col *= 1.0 - 0.07*(1.0 + edge/22.0);
    // the blob, its shadow and its gloss
    float milk; float d = field(p, milk);
    if (d < 70.0) {
      float ms; float ds = field(p - vec2(10.0, 26.0), ms);
      col *= 1.0 - 0.13*smoothstep(46.0, -10.0, ds)*step(0.0, d);
    }
    if (d < 2.0) {
      float m2; float dx = field(p + vec2(1.5, 0.0), m2) - d; float dy = field(p + vec2(0.0, 1.5), m2) - d;
      vec2 g = normalize(vec2(dx, dy) + 1e-5);
      float depth = clamp(-d / 58.0, 0.0, 1.0);
      float hgt = sqrt(1.0 - (1.0 - depth)*(1.0 - depth));
      vec3 n = normalize(vec3(g * (1.0 - hgt) * 1.7, hgt + 0.12));
      vec3 L = normalize(vec3(-0.45, -0.65, 0.62));
      float diff = clamp(dot(n, L), 0.0, 1.0);
      float spec = pow(clamp(dot(n, normalize(L + vec3(0.0, 0.0, 1.0))), 0.0, 1.0), 70.0);
      float rim = pow(max(1.0 - n.z, 0.0), 2.2);
      float u = clamp(p.x / uVW.x * 0.55 + p.y / uVW.y * 0.35 + n.x*0.18 - n.y*0.1 + sin(uT*0.25)*0.06, 0.0, 1.0);
      vec3 c1 = vec3(1.0, 0.72, 0.42), c2 = vec3(1.0, 0.42, 0.6), c3 = vec3(0.545, 0.48, 1.0);
      vec3 candy = u < 0.5 ? mix(c1, c2, u*2.0) : mix(c2, c3, (u - 0.5)*2.0);
      vec3 cand = candy*(0.6 + 0.48*diff) + rim*vec3(0.6, 0.45, 1.0)*0.4 + spec*0.95;
      vec3 milkC = vec3(1.0, 0.98, 0.965);
      vec3 mlk = milkC*(0.9 + 0.1*diff) + rim*vec3(1.0, 0.55, 0.72)*0.35 + spec*0.5;
      vec3 shaded = mix(cand, mlk, smoothstep(0.35, 0.75, milk));
      col = mix(col, shaded, smoothstep(1.4, -1.4, d));
    }
    gl_FragColor = vec4(col, 1.0);
  }`;
  const sh = (type: number, src: string) => {
    const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.warn(gl.getShaderInfoLog(s));
    return s;
  };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null;
  gl.useProgram(prog);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const ap = gl.getAttribLocation(prog, "p"); gl.enableVertexAttribArray(ap); gl.vertexAttribPointer(ap, 2, gl.FLOAT, false, 0, 0);
  const U = (n: string) => gl.getUniformLocation(prog, n);
  const uRes = U("uRes"), uPx = U("uPx"), uT = U("uT"), uVW = U("uVW"), uB = U("uB"), uBul = U("uBul"), uC = U("uC"), uNB = U("uNB"), uBall = U("uBall"), uN = U("uN"), uStr = U("uStr"), uRip = U("uRip");
  const B6 = new Float32Array(6), BU6 = new Float32Array(6), C7 = new Float32Array(21);
  let slow = 0;
  return {
    resize,
    draw(o: { t: number; bnd: number[]; bul: number[]; cols: number[]; balls: Float32Array; n: number; stretch: number; ripple: number }) {
      const t0 = performance.now();
      B6.fill(1e5); BU6.fill(0); C7.fill(0);
      o.bnd.forEach((v, i) => { B6[i] = v; BU6[i] = o.bul[i]; });
      C7.set(o.cols.slice(0, 21));
      gl.uniform2f(uRes, canvas.width, canvas.height); gl.uniform1f(uPx, canvas.width / innerWidth); gl.uniform1f(uT, o.t); gl.uniform2f(uVW, innerWidth, innerHeight);
      gl.uniform1fv(uB, B6); gl.uniform1fv(uBul, BU6); gl.uniform3fv(uC, C7); gl.uniform1i(uNB, o.bnd.length);
      gl.uniform4fv(uBall, o.balls); gl.uniform1i(uN, o.n); gl.uniform1f(uStr, o.stretch); gl.uniform1f(uRip, o.ripple);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      // a slow GPU gets a coarser fluid rather than a slow page
      if (performance.now() - t0 > 14) { if (++slow > 20 && scale > 0.35) { scale *= 0.8; resize(); slow = 0; } } else slow = Math.max(0, slow - 1);
    },
  };
}
