/**
 * Neon glow: walking a night street. Each [data-sign] is redrawn as SVG tubes over its real text (glass outline,
 * two pre-blurred halos, a near-white core), laid word by word where the browser set the text. Every section's
 * primary sign runs a power state: unlit glass until it reaches the reading band, then a two-dip stutter and steady
 * light (spill on the wall, reflections on the wet ground); leaving, it dims to warm-off and then glass. The room
 * colour follows the sign you are at. Features light in sequence like a sign chaser; stats are segmented tube
 * numerals that light segment by segment; the timeline is one tube drawn along the wall as you scroll; the CTA is the
 * OPEN sign switching on with a clunk. Reduced motion: signs light and dim with a short fade, no flicker, no buzz.
 */
import { $, $$, onFrame, reduced, pinned } from "./_kit";
import { clamp } from "../lib/util";

const NS = "http://www.w3.org/2000/svg";
type Sign = { el: HTMLElement; sec: HTMLElement | null; primary: boolean; lit: boolean; color: string };

export default function start() {
  const root = document.documentElement;
  root.classList.add("ng-live");
  const measure = document.createElement("canvas").getContext("2d")!;

  // ---------------------------------------------------------------- signs as tubes
  const signs: Sign[] = $$<HTMLElement>("[data-sign]").map((el) => ({
    el, sec: el.closest<HTMLElement>(".ng-front"), primary: !el.closest(".ng-fsign"), lit: false, color: "",
  }));

  function buildSign(s: Sign) {
    const el = s.el, txt = el.querySelector<HTMLElement>(".ng-sign__txt") || el;
    el.querySelector(".ng-tubes")?.remove();
    const er = el.getBoundingClientRect();
    if (er.width < 2) return;
    const cs0 = getComputedStyle(el);
    const c1 = cs0.getPropertyValue("--tube").trim() || "#ff2a6d", c2 = cs0.getPropertyValue("--tube2").trim() || c1;
    s.color = c1;
    const hero = el.classList.contains("ng-sign--hero");
    const items: { t: string; x: number; y: number; font: string; size: number; ls: string; col: string; lag?: boolean }[] = [];
    const range = document.createRange();
    const walker = document.createTreeWalker(txt, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement!;
      const cs = getComputedStyle(parent);
      const size = parseFloat(cs.fontSize);
      const font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      measure.font = font;
      const col = parent.closest("em") ? c2 : c1;
      const text = node.textContent || "";
      const re = hero ? /\S/g : /\S+/g;
      let m: RegExpExecArray | null;
      while ((m = re.exec(text))) {
        range.setStart(node, m.index); range.setEnd(node, m.index + m[0].length);
        const r = range.getClientRects()[0];
        if (!r) continue;
        const asc = measure.measureText(m[0]).fontBoundingBoxAscent || size * 0.9;
        items.push({ t: m[0], x: r.left - er.left, y: r.top - er.top + asc, font: cs.fontFamily, size, ls: cs.letterSpacing === "normal" ? "0" : cs.letterSpacing, col });
      }
    }
    if (!items.length) return;
    if (hero) {
      const letters = items.map((it, i) => ({ it, i })).filter(({ it }) => /[a-z]/i.test(it.t));
      const pick = letters[Math.floor(letters.length * 0.38)];
      if (pick) pick.it.lag = true;
    }
    const W = Math.ceil(er.width), H = Math.ceil(er.height);
    const wrap = document.createElement("div");
    wrap.className = "ng-tubes";
    wrap.setAttribute("aria-hidden", "true");
    const size0 = items[0].size;
    const layer = (cls: string, f: (t: SVGTextElement, it: typeof items[0]) => void, filter = "") => {
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", cls); svg.setAttribute("width", String(W)); svg.setAttribute("height", String(H)); svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      if (filter) svg.style.filter = filter;
      for (const it of items) {
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", it.x.toFixed(1)); t.setAttribute("y", it.y.toFixed(1));
        t.setAttribute("font-family", it.font); t.setAttribute("font-size", String(it.size)); t.setAttribute("letter-spacing", it.ls);
        if (it.lag) t.setAttribute("class", "ng-lag");
        t.textContent = it.t;
        f(t, it);
        svg.appendChild(t);
      }
      wrap.appendChild(svg);
    };
    layer("ng-glass", () => {});
    layer("ng-halo2", (t, it) => { t.setAttribute("fill", it.col); }, `blur(${(size0 * 0.32).toFixed(1)}px)`);
    layer("ng-halo", (t, it) => { t.setAttribute("fill", it.col); t.setAttribute("stroke", it.col); t.setAttribute("stroke-width", (it.size * 0.05).toFixed(2)); }, `blur(${(size0 * 0.085).toFixed(1)}px)`);
    layer("ng-core", (t, it) => { t.setAttribute("stroke", it.col); t.setAttribute("stroke-width", Math.max(0.6, it.size * 0.022).toFixed(2)); });
    el.appendChild(wrap);
    el.classList.add("has-tubes");
  }

  // ---------------------------------------------------------------- stats: segmented tube numerals
  const SEG: Record<string, string> = { "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g" };
  const P: Record<string, [number, number, number, number]> = {
    a: [12, 6, 44, 6], b: [50, 11, 50, 45], c: [50, 55, 50, 89], d: [12, 94, 44, 94], e: [6, 55, 6, 89], f: [6, 11, 6, 45], g: [12, 50, 44, 50],
  };
  function buildSeg(v: HTMLElement) {
    v.querySelector(".ng-seg")?.remove();
    const val = (v.dataset.seg || "").trim(), unit = (v.dataset.unit || "").trim();
    if (!val) return;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "ng-seg"); svg.setAttribute("aria-hidden", "true");
    const glass = document.createElementNS(NS, "g"), lit = document.createElementNS(NS, "g");
    lit.setAttribute("class", "lit");
    let x = 0, n = 0;
    const seg = (d: [number, number, number, number], ox: number) => {
      for (const [g, cls] of [[glass, "g"], [lit, "l"]] as const) {
        const ln = document.createElementNS(NS, "line");
        ln.setAttribute("x1", String(d[0] + ox)); ln.setAttribute("y1", String(d[1])); ln.setAttribute("x2", String(d[2] + ox)); ln.setAttribute("y2", String(d[3]));
        ln.setAttribute("class", cls);
        if (cls === "l") ln.style.transitionDelay = `${n * 55}ms`;
        g.appendChild(ln);
      }
      n++;
    };
    const glyph = (ch: string, size: number, ox: number) => {
      for (const [g, cls] of [[glass, "gt"], [lit, "lt"]] as const) {
        const t = document.createElementNS(NS, "text");
        t.setAttribute("x", String(ox)); t.setAttribute("y", String(size === 100 ? 94 : 44)); t.setAttribute("font-size", String(size)); t.setAttribute("class", cls);
        if (cls === "lt") t.style.transitionDelay = `${n * 55}ms`;
        t.textContent = ch;
        g.appendChild(t);
      }
      n++;
    };
    for (const ch of val) {
      if (SEG[ch]) { for (const s of SEG[ch]) seg(P[s], x); x += 72; }
      else if (ch === "." || ch === ",") { glyph(ch, 100, x - 10); x += 26; }
      else if (ch === " ") x += 30;
      else { glyph(ch, 100, x); x += 66; }
    }
    if (unit) { glyph(unit, 40, x + 6); x += 6 + unit.length * 24; }
    svg.setAttribute("viewBox", `-8 -4 ${x + 12} 108`);
    svg.style.aspectRatio = `${x + 20} / 112`;
    svg.appendChild(glass); svg.appendChild(lit);
    v.prepend(svg);
    v.classList.add("has-seg");
  }
  const cells = $$<HTMLElement>(".ng-cell");
  const boards = $$<HTMLElement>(".ng-stats").map((sec) => ({ sec, cells: $$<HTMLElement>(".ng-cell", sec), on: false, t0: 0 }));

  // ---------------------------------------------------------------- timeline: one tube along the wall
  const routes = $$<HTMLElement>(".ng-route").map((ol) => ({ ol, svg: null as SVGSVGElement | null, h: null as SVGPathElement | null, c: null as SVGPathElement | null, len: 0, samples: [] as { l: number; y: number }[], nodes: [] as number[], stops: $$<HTMLElement>(".ng-stop", ol), lit: [] as boolean[] }));
  function buildRoute(rt: typeof routes[0]) {
    rt.svg?.remove();
    const or = rt.ol.getBoundingClientRect();
    const pts = $$<HTMLElement>(".ng-stop__hook", rt.ol).map((h) => { const r = h.getBoundingClientRect(); return { x: r.left - or.left, y: r.top - or.top }; });
    if (!pts.length) return;
    let d = `M ${pts[0].x} ${-60}`;
    let a = { x: pts[0].x, y: -60 };
    for (const b of pts) {
      const dx = b.x - a.x, dy = b.y - a.y;
      if (Math.abs(dx) < 1) d += ` V ${b.y}`;
      else {
        const mid = a.y + dy * 0.5, s = Math.sign(dx), r = Math.max(2, Math.min(30, Math.abs(dx) / 2, Math.abs(dy) / 4));
        d += ` V ${mid - r} Q ${a.x} ${mid} ${a.x + s * r} ${mid} H ${b.x - s * r} Q ${b.x} ${mid} ${b.x} ${mid + r} V ${b.y}`;
      }
      a = b;
    }
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "ng-line"); svg.setAttribute("width", String(or.width)); svg.setAttribute("height", String(or.height)); svg.setAttribute("aria-hidden", "true");
    const mk = (cls: string) => { const p = document.createElementNS(NS, "path"); p.setAttribute("d", d); p.setAttribute("class", cls); svg.appendChild(p); return p; };
    mk("g"); rt.h = mk("h"); rt.c = mk("c");
    rt.ol.prepend(svg);
    rt.svg = svg; rt.len = rt.h.getTotalLength();
    rt.samples = [];
    for (let k = 0; k <= 200; k++) { const l = rt.len * k / 200; rt.samples.push({ l, y: rt.h.getPointAtLength(l).y }); }
    rt.nodes = pts.map((p) => { let best = 0, bd = 1e9; for (const s of rt.samples) { const q = rt.h!.getPointAtLength(s.l); const dd = Math.hypot(q.x - p.x, q.y - p.y); if (dd < bd) { bd = dd; best = s.l; } } return best; });
    rt.lit = rt.stops.map(() => false);
    for (const p of [rt.h, rt.c]) p.style.strokeDasharray = `${rt.len} ${rt.len}`;
  }
  function updateRoutes(vh: number) {
    for (const rt of routes) {
      if (!rt.h || !rt.c) continue;
      const or = rt.ol.getBoundingClientRect();
      if (or.bottom < -200 || or.top > vh + 200) continue;
      const line = reduced ? 1e9 : vh * 0.62 - or.top;
      let l = 0;
      for (const s of rt.samples) { if (s.y <= line) l = s.l; else break; }
      if (line >= rt.samples[rt.samples.length - 1].y) l = rt.len;
      const off = String(rt.len - l);
      rt.h.style.strokeDashoffset = off; rt.c.style.strokeDashoffset = off;
      rt.nodes.forEach((nl, i) => { const on = l >= nl - 4; if (on !== rt.lit[i]) { rt.lit[i] = on; rt.stops[i].classList.toggle("is-lit", on); } });
    }
  }

  // ---------------------------------------------------------------- features: the sign sequencer
  const seqs = $$<HTMLElement>(".ng-features").map((sec) => ({ sec, stage: $<HTMLElement>(".ng-features__stage", sec)!, items: $$<HTMLElement>(".ng-fsign", sec), on: -2, free: false }));
  function layoutSeqs() {
    for (const q of seqs) {
      q.sec.classList.remove("is-free");
      q.free = q.stage.scrollHeight > innerHeight + 4;
      q.sec.classList.toggle("is-free", q.free);
    }
  }
  function updateSeqs(vh: number) {
    for (const q of seqs) {
      const r = q.sec.getBoundingClientRect();
      const inView = r.top < vh * 0.6 && r.bottom > vh * 0.3;
      let act = -1;
      if (inView) {
        if (q.free) q.items.forEach((it, i) => { const ir = it.getBoundingClientRect(); if (ir.top < vh * 0.62) act = i; });
        else act = Math.min(q.items.length - 1, Math.floor(clamp((pinned(q.sec) - 0.04) / 0.9) * q.items.length));
      }
      if (act === q.on) continue;
      q.on = act;
      q.items.forEach((it, i) => {
        const sg = it.querySelector(".ng-sign");
        sg?.classList.toggle("is-lit", i === act);
        sg?.classList.toggle("is-idle", act >= 0 && i < act);
        it.querySelector(".ng-plaque")?.classList.toggle("is-lit", i <= act);
      });
    }
  }

  // ---------------------------------------------------------------- the pointer: a hand near the glass
  const torch = $<HTMLElement>(".ng-torch");
  let mx = -1e4, my = -1e4;
  addEventListener("pointermove", (e) => {
    mx = e.clientX; my = e.clientY;
    if (!torch || e.pointerType === "touch" || reduced) return;
    torch.style.setProperty("--tx", mx + "px"); torch.style.setProperty("--ty", my + "px");
    torch.classList.add("is-on");
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => torch?.classList.remove("is-on"));

  // ---------------------------------------------------------------- nav
  const links = $$<HTMLAnchorElement>(".ss-nav__links a[href^='#']");
  const targets = links.map((a) => document.getElementById(a.getAttribute("href")!.slice(1)));
  let navOn = -2, room = "";
  const opens = $$<HTMLElement>("[data-open]").map((el) => ({ el, sec: el.closest<HTMLElement>(".ng-front"), t: 0, on: false }));

  function light(s: Sign, on: boolean) {
    if (s.lit === on) return;
    s.lit = on;
    s.el.classList.toggle("is-lit", on);
    if (s.sec) s.sec.classList.toggle("is-lit", signs.some((o) => o.primary && o.sec === s.sec && o.lit));
  }

  // ---------------------------------------------------------------- go
  const buildAll = () => {
    signs.forEach(buildSign);
    $$<HTMLElement>("[data-seg]").forEach(buildSeg);
    routes.forEach(buildRoute);
    layoutSeqs();
  };
  const fontsReady = document.fonts ? document.fonts.ready : Promise.resolve();
  let ready = false;
  Promise.race([fontsReady, new Promise((r) => setTimeout(r, 2500))]).then(() => { buildAll(); ready = true; });
  let rtm = 0, lastW = innerWidth;
  addEventListener("resize", () => { clearTimeout(rtm); rtm = window.setTimeout(() => { if (Math.abs(innerWidth - lastW) > 2) { lastW = innerWidth; buildAll(); } else { routes.forEach(buildRoute); layoutSeqs(); } }, 200); });
  addEventListener("load", () => { if (ready) routes.forEach(buildRoute); });
  $$<HTMLDetailsElement>(".ng-q").forEach((d) => d.addEventListener("toggle", () => routes.forEach(buildRoute)));

  onFrame(({ vh, t }) => {
    if (!ready) return;
    // primary signs: power on in the reading band, off behind you
    let best: Sign | null = null, bd = 1e9;
    for (const s of signs) {
      if (!s.primary) continue;
      const r = s.el.getBoundingClientRect();
      const on = r.top < vh * 0.72 && r.bottom > vh * 0.1;
      light(s, on);
      if (on) { const d = Math.abs((r.top + r.bottom) / 2 - vh * 0.45); if (d < bd) { bd = d; best = s; } }
    }
    if (best && best.color && best.color !== room) { room = best.color; root.style.setProperty("--room", room); }
    // the hand near the glass brightens the sign it is near
    for (const s of signs) {
      if (!s.lit) continue;
      const r = s.el.getBoundingClientRect();
      const dx = Math.max(r.left - mx, 0, mx - r.right), dy = Math.max(r.top - my, 0, my - r.bottom);
      const near = reduced ? 0 : clamp(1 - Math.hypot(dx, dy) / 260);
      s.el.parentElement?.style.setProperty("--near", near.toFixed(2));
    }
    updateSeqs(vh);
    updateRoutes(vh);
    // stats boards: cells light one after another, segment by segment
    for (const b of boards) {
      const r = b.sec.getBoundingClientRect();
      const on = r.top < vh * 0.62 && r.bottom > vh * 0.25;
      if (on && !b.on) { b.on = true; b.t0 = t; b.sec.classList.add("is-lit"); }
      if (!on && b.on) { b.on = false; b.sec.classList.remove("is-lit"); b.cells.forEach((c) => c.classList.remove("is-lit")); }
      if (b.on) b.cells.forEach((c, i) => { if (!c.classList.contains("is-lit") && (reduced || t - b.t0 > 0.15 + i * 0.32)) c.classList.add("is-lit"); });
    }
    // the OPEN sign switches on once its wall is lit
    for (const o of opens) {
      const orr = o.el.getBoundingClientRect();
      const lit = (!!o.sec && o.sec.classList.contains("is-lit")) || (orr.top < vh * 0.85 && orr.bottom > vh * 0.08);
      if (lit && !o.t) o.t = t;
      if (!lit) { o.t = 0; if (o.on) { o.on = false; o.el.classList.remove("is-on"); } }
      if (lit && !o.on && (reduced || t - o.t > 0.95)) { o.on = true; o.el.classList.add("is-on"); }
      if (o.sec) o.sec.classList.toggle("is-lit", o.on || signs.some((sg) => sg.primary && sg.sec === o.sec && sg.lit));
    }
    let on = -1;
    targets.forEach((tg, i) => { if (tg && tg.getBoundingClientRect().top < vh * 0.5) on = i; });
    if (on !== navOn) { navOn = on; links.forEach((a, i) => a.classList.toggle("is-on", i === on)); }
  });
  void cells;
}
