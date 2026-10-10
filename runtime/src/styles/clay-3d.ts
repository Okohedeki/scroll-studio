/**
 * Clay 3D: soft toys on a table. Everything has mass and elasticity.
 *
 *   drops    cards fall into place and squash on landing (.cl-in starts the keyframes, staggered by --d)
 *   words    the headline's words drop in one by one like toys into a box
 *   trays    each tray inflates as it arrives (scroll-scrubbed elastic overshoot) with a blobby outline settling round
 *   jelly    scroll velocity feeds a damped spring per tile: fling the page and the tiles wobble, then settle
 *   dent     tiles lean toward the pointer with a soft highlight
 *   buddy    a clay mascot hops from tray to tray as you scroll: a parabolic hop with a tumble, squash on landing,
 *            blinks, and points at the CTA at the end
 *   stones   a clay ball rolls along the stepping-stone path with the scroll
 *   faq      answers inflate downward with a springy overshoot
 */
import { $, $$, onFrame, reduced, through } from "./_kit";
import { clamp, lerp, smooth } from "../lib/util";

const mobile = () => matchMedia("(max-width: 900px)").matches;
const elastic = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : Math.pow(2, -9 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3.2)) + 1);

export default function start() {
  document.documentElement.classList.add("cl-live");
  words();
  drops();
  trays();
  jelly();
  stones();
  buddy();
  faq();
  navDimple();
}

function words() {
  $$<HTMLElement>("[data-cl-words]").forEach((h) => {
    let i = 0;
    const label = h.textContent || "";
    const walk = (node: Node) => {
      if (node.nodeType === 3) {
        const frag = document.createDocumentFragment();
        (node.textContent || "").split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
          const w = document.createElement("span");
          w.className = "cl-word";
          w.style.setProperty("--w", String(i++));
          w.textContent = part;
          frag.appendChild(w);
        });
        node.parentNode!.replaceChild(frag, node);
      } else [...node.childNodes].forEach(walk);
    };
    [...h.childNodes].forEach(walk);
    h.setAttribute("aria-label", label.trim());
    // the rest of the hero drops in after the last word lands
    const n = i;
    h.closest("section")?.querySelectorAll<HTMLElement>(".cl-drop").forEach((el) => {
      const d = parseFloat(el.style.getPropertyValue("--d") || "0");
      if (d > 2) el.style.setProperty("--d", String(d + Math.max(0, n - 3) * 1.1));
    });
  });
}

function drops() {
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("cl-in"); io.unobserve(e.target); }
  }), { threshold: 0.15, rootMargin: "0px 0px -5% 0px" });
  $$(".cl-drop, .cl-pop, [data-cl-words], .cl-bubble").forEach((el) => io.observe(el));
}

// trays inflate as they arrive; their outline starts blobby and settles round (scroll-scrubbed, so no timer to trail)
function trays() {
  if (reduced) return;
  const ts = $$<HTMLElement>('[data-cl="tray"]');
  const last = new Map<HTMLElement, number>();
  onFrame(({ vh }) => {
    for (const t of ts) {
      const r = t.getBoundingClientRect();
      if (r.top > vh * 1.1 || r.bottom < -vh * 0.2) continue;
      const k = clamp((vh - r.top) / (vh * 0.55));
      const e = elastic(k);
      if (last.get(t) === Math.round(e * 1000)) continue;
      last.set(t, Math.round(e * 1000));
      t.style.setProperty("--k", e.toFixed(3));
      const b = 1 - clamp(k * 1.4);       // blobbiness, 1 -> 0
      if (b > 0.001) {
        const R = (a: number) => `${(56 + a * b).toFixed(0)}px`;
        t.style.borderRadius = `${R(90)} ${R(30)} ${R(100)} ${R(40)} / ${R(20)} ${R(110)} ${R(30)} ${R(120)}`;
      } else t.style.borderRadius = "";
    }
  });
}

// damped springs fed by scroll velocity (and the pointer, for the dent)
function jelly() {
  const els = $$<HTMLElement>("[data-jelly]");
  if (!els.length) return;
  const st = els.map((el, i) => ({ el, x: 0, v: 0, k: 150 + (i % 5) * 30, c: 7 + (i % 3), rx: 0, ry: 0, trx: 0, try: 0, on: false }));
  if (!matchMedia("(hover: none)").matches && !reduced) {
    addEventListener("pointermove", (e) => {
      const host = (e.target as Element)?.closest?.<HTMLElement>("[data-dent]");
      for (const s of st) {
        if (s.el === host) {
          const r = s.el.getBoundingClientRect();
          const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
          s.trx = (py - 0.5) * 6; s.try = -(px - 0.5) * 8;
          s.el.style.setProperty("--mx", (px * 100).toFixed(0) + "%");
          s.el.style.setProperty("--my", (py * 100).toFixed(0) + "%");
        } else { s.trx = 0; s.try = 0; }
      }
    }, { passive: true });
  }
  if (reduced) return;
  onFrame(({ v, dt, vh }) => {
    const target = clamp(-v * 0.55, -16, 16);
    const h = Math.min(dt, 1 / 30);
    for (const s of st) {
      const r = s.el.getBoundingClientRect();
      if (r.bottom < -50 || r.top > vh + 50) { if (s.on) { s.el.style.transform = ""; s.on = false; s.x = s.v = 0; } continue; }
      // two half-steps keep the low-damping spring stable at 30 fps
      for (let k = 0; k < 2; k++) {
        const a = -s.k * (s.x - target) - s.c * s.v;
        s.v += a * h / 2; s.x += s.v * h / 2;
      }
      s.rx += (s.trx - s.rx) * 0.12; s.ry += (s.try - s.ry) * 0.12;
      const mag = Math.abs(s.x);
      if (mag < 0.02 && Math.abs(s.v) < 0.02 && Math.abs(s.rx) + Math.abs(s.ry) < 0.02) {
        if (s.on) { s.el.style.transform = ""; s.on = false; }
        continue;
      }
      s.on = true;
      s.el.style.transform = `perspective(900px) rotateX(${s.rx.toFixed(2)}deg) rotateY(${s.ry.toFixed(2)}deg) skewY(${(s.x * 0.22).toFixed(2)}deg) scale(${(1 + mag * 0.004).toFixed(4)}, ${(1 - mag * 0.006).toFixed(4)})`;
    }
  });
}

// the stepping-stone path and the ball rolling along it
function stones() {
  $$<HTMLElement>("[data-path]").forEach((wrap) => {
    const svg = $<SVGSVGElement>("svg", wrap)!;
    const path = $<SVGPathElement>("path", wrap)!;
    const ball = $(".cl-ball", wrap);
    const dots = $$<HTMLElement>(".cl-stone__dot", wrap);
    if (!dots.length || !path) return;
    let len = 0, key = "";
    const build = () => {
      const w = wrap.getBoundingClientRect();
      const pts = dots.map((d) => { const r = d.getBoundingClientRect(); return [r.left + r.width / 2 - w.left, r.top - w.top - 6]; });
      const k = pts.map((p) => p.join(",")).join(" ");
      if (k === key) return;
      key = k;
      svg.setAttribute("viewBox", `0 0 ${w.width} ${w.height}`);
      let d = `M${pts[0][0]},${pts[0][1]}`;
      for (let i = 1; i < pts.length; i++) {
        const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
        const lift = Math.min(54, Math.hypot(x1 - x0, y1 - y0) * 0.25);
        d += ` C${x0 + (x1 - x0) * 0.3},${Math.min(y0, y1) - lift} ${x0 + (x1 - x0) * 0.7},${Math.min(y0, y1) - lift} ${x1},${y1}`;
      }
      path.setAttribute("d", d);
      len = path.getTotalLength();
    };
    onFrame(({ vh }) => {
      const r = wrap.getBoundingClientRect();
      if (r.bottom < -vh || r.top > vh * 2) return;
      build();
      if (!ball || !len) return;
      const p = reduced ? 1 : smooth(0.25, 0.75, through(wrap));
      // the ball rests on each stone a moment: ease the travel between stones
      const n = dots.length - 1;
      const seg = p * n, i = Math.min(n - 1, Math.floor(seg)), f = seg - i;
      const ease = f < 0.5 ? 4 * f * f * f : 1 - Math.pow(-2 * f + 2, 3) / 2;
      const at = n > 0 ? ((i + (p >= 1 ? 1 : ease)) / n) * len : 0;
      const pt = path.getPointAtLength(Math.min(len, at));
      ball.style.transform = `translate(${pt.x.toFixed(1)}px, ${(pt.y - 16).toFixed(1)}px) rotate(${((at / 20) * 57.3).toFixed(0)}deg)`;
    });
    addEventListener("resize", () => { key = ""; });
  });
}

// the buddy: hops between seats (one per tray, alternating sides), tumbling in the air and squashing on landing
function buddy() {
  const el = $(".cl-buddy");
  if (!el) return;
  const body = $(".cl-buddy__body", el)!;
  const shadow = $(".cl-buddy__shadow", el)!;
  const hero = $('[data-cl="hero"]');
  const trays = $$<HTMLElement>('[data-cl="tray"]');
  const stops: HTMLElement[] = [...(hero ? [hero] : []), ...trays];
  const ctaSeat = $('[data-seat="cta"]');
  if (!stops.length) return;
  // blink now and then
  const blink = () => { el.classList.add("is-blink"); setTimeout(() => el.classList.remove("is-blink"), 140); setTimeout(blink, 2600 + Math.random() * 3200); };
  setTimeout(blink, 1800);
  let squash = 0, squashV = 0, lastI = -1, landed = true;
  onFrame(({ vh, dt, t, v }) => {
    const W = innerWidth, small = mobile();
    const size = el.offsetWidth;
    const seat = (i: number): [number, number, number] => {
      const s = stops[i];
      if (s === hero && !small) {
        const r = s.getBoundingClientRect();
        return [W * 0.82 - size / 2, clamp(r.top + vh * 0.66, -size * 2, vh) - size, 1.45];
      }
      const lastStop = i === stops.length - 1 && ctaSeat && s.contains(ctaSeat);
      if (lastStop) {
        const btn = $(".cl-cta .cl-candy");
        const r = (btn || ctaSeat!).getBoundingClientRect();
        const x = small ? W - size - 10 : Math.min(W - size - 20, r.right + 40);
        return [x, clamp(r.bottom - size + 10, 80, vh - size - 10), 1.1];
      }
      const left = i % 2 === 1;
      const tr = s.getBoundingClientRect();
      const margin = Math.max(8, (W - tr.width) / 2 - size * 0.55);
      const x = small ? (left ? 6 : W - size - 6) : left ? Math.max(6, margin - size * 0.35) : Math.min(W - size - 6, W - margin - size * 0.65);
      const y = small ? vh - size - 70 : vh * 0.7 - size;
      return [x, y, 1];
    };
    // fractional stop index: hold each stop through its middle, hop across the hand-over
    const mid = vh * 0.55;
    const tops = stops.map((s) => s.getBoundingClientRect());
    let f = 0;
    for (let i = 0; i < stops.length; i++) {
      const r = tops[i];
      if (mid >= r.top) {
        f = i;
        const next = tops[i + 1];
        if (next) f = i + smooth(next.top - vh * 0.3, next.top + vh * 0.05, mid + 0) ;
      }
    }
    if (reduced) f = Math.round(f);
    const i = Math.floor(f), k = f - i;
    const a = seat(i), b = seat(Math.min(stops.length - 1, i + 1));
    const x = lerp(a[0], b[0], k);
    const arc = Math.sin(Math.PI * k) * (small ? 90 : 190);
    const y = lerp(a[1], b[1], k) - arc;
    const sc = lerp(a[2], b[2], k) * (1 + Math.sin(Math.PI * k) * 0.12);   // inflates in the air
    const dir = b[0] >= a[0] ? 1 : -1;
    const tumble = reduced ? 0 : k * 360 * dir;
    // landing: kick a squash spring when a hop completes
    const airborne = k > 0.04 && k < 0.96;
    if (airborne) landed = false;
    else if (!landed) { landed = true; squashV += 9; }
    if (i !== lastI) { lastI = i; }
    const h = Math.min(dt, 1 / 30);
    const acc = -260 * squash - 11 * squashV;
    squashV += acc * h; squash += squashV * h;
    const vel = reduced ? 0 : clamp(Math.abs(v) * 0.01, 0, 0.12);
    const breathe = reduced ? 0 : Math.sin(t * 2.2) * 0.02;
    const stretch = airborne ? 0.1 * Math.sin(Math.PI * k) : 0;
    const sy = 1 + breathe + stretch - clamp(squash, -0.3, 0.3) * 0.35 - vel;
    const sx = 1 - breathe * 0.6 - stretch * 0.7 + clamp(squash, -0.3, 0.3) * 0.3 + vel * 0.8;
    el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) scale(${sc.toFixed(3)})`;
    body.style.transform = `rotate(${tumble.toFixed(1)}deg) scale(${sx.toFixed(3)}, ${sy.toFixed(3)})`;
    shadow.style.transform = `translateY(${arc.toFixed(1)}px) scale(${(1 - arc / 400).toFixed(3)})`;
    shadow.style.opacity = String(clamp(1 - arc / 260));
    const atCta = ctaSeat && i >= stops.length - 1 - (k > 0.9 ? 1 : 0) && stops[stops.length - 1].contains(ctaSeat) && f > stops.length - 1.1;
    el.classList.toggle("is-point", !!atCta);
  });
}

// answers inflate downward with overshoot
function faq() {
  $$<HTMLDetailsElement>(".cl-q-pill").forEach((d) => {
    d.addEventListener("toggle", () => {
      if (!d.open || reduced) return;
      const a = $(".cl-q-pill__a", d);
      if (!a) return;
      const h = a.offsetHeight;
      a.animate([
        { height: "0px", transform: "scaleY(.6)", opacity: 0 },
        { height: `${h * 1.1}px`, transform: "scaleY(1.06)", opacity: 1, offset: 0.55 },
        { height: `${h * 0.97}px`, transform: "scaleY(.98)", offset: 0.78 },
        { height: `${h}px`, transform: "none", opacity: 1 },
      ], { duration: 620, easing: "ease-out" });
      d.animate([{ transform: "scale(1.02, .97)" }, { transform: "scale(.99, 1.02)" }, { transform: "none" }], { duration: 500, easing: "ease-out" });
    });
  });
}

// the nav link for the section in view sits in a pressed-in dimple
function navDimple() {
  const links = $$<HTMLAnchorElement>(".ss-nav__links a");
  const map = links.map((a) => ({ a, s: document.querySelector<HTMLElement>(a.getAttribute("href") || "") })).filter((x) => x.s);
  if (!map.length) return;
  let cur: HTMLAnchorElement | null = null;
  onFrame(({ vh }) => {
    let best: HTMLAnchorElement | null = null;
    for (const m of map) { const r = m.s!.getBoundingClientRect(); if (r.top < vh * 0.5 && r.bottom > vh * 0.3) best = m.a; }
    if (best !== cur) { cur?.classList.remove("cl-on"); best?.classList.add("cl-on"); cur = best; }
  });
}
