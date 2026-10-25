/**
 * Smears: Spider-Verse timing on a page. The belt that carries the sheets is sampled twelve times a second (on twos, on a
 * 24-a-second clock): nothing glides, the page holds a pose, and in the one frame where the pose changes the content is drawn
 * at the mid-point and every actor (headline, card, numeral, button, picture) is stretched along the move, with colour plates
 * trailing it; faster scrolling adds multiples (echoes of the actor strung along its path, in the three plate colours, with
 * text-shadow and drop-shadow; there is no blur anywhere). The plates also slip: the faster the page moves, the further each
 * actor's colour plates are out of register, and the actor you point at or focus is the one that stays in register, so a
 * hover is a rack focus by offset. Different layers keep different cadences: actors on twos, the backdrop's print screen on
 * threes, the pointer's trail on ones. Crossing into another sheet while moving breaks the picture for two frames into one
 * impact frame (flat colour, speed lines, dots) and shakes the page on twos; at most one in 450 ms, never when moving
 * slowly, never red. Actors pop in on twos with a squash and stretch the first time they come into view, and hop when poked.
 * theme.art is drawn as a halftone in two misregistered plates, redrawn on twos.
 * Reduced motion: no belt, no sampling, no smears; each sheet is a still print with its plates at rest.
 * Research: docs/styles/styles-32-33.md, section 2.
 */
import { $, $$, onFrame, reduced, skinRgba } from "./_kit";
import { makeBelts, measure, watch, trueOffset, yInBelt, wireLinks, beltOf, type Belt } from "./_belt";
import { loadArt, type ArtFrames } from "./_art";

const TICK = 1000 / 24;
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const hash = (a: number, b = 0, c = 0): number => {
  let x = Math.imul(a ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul((b | 0) + 0x7f4a7c15, 0xc2b2ae35) ^ Math.imul((c | 0) + 0x165667b1, 0x27d4eb2f);
  x ^= x >>> 15; x = Math.imul(x, 0x2c1b3c6d); x ^= x >>> 12; x = Math.imul(x, 0x297a2d39); x ^= x >>> 15;
  return (x >>> 0) / 4294967296;
};

// poses (one per two ticks): scale x, scale y
const POP: [number, number][] = [[0.5, 1.55], [1.2, 0.84], [0.96, 1.06], [1, 1]];
const POKE: [number, number][] = [[1.1, 0.86], [0.95, 1.1], [1, 1]];
const HIT: Record<string, string> = { night: "#c01a74", ink: "#d9a400", riso: "#e5701c", pop: "#7fb00c" };

interface Actor {
  el: HTMLElement; kind: string; belt: Belt | null; y: number; h: number; text: boolean; box: boolean;
  seen: boolean; arrN: number; pokeN: number; key: string; mx: string; focus: boolean; id: number; sheet: number;
}
interface Sheet { el: HTMLElement; top: number; dim: string; back: HTMLElement | null }

export default function start() {
  const main = $<HTMLElement>("main");
  const sheetEls = $$<HTMLElement>(".sa-sheet", main || document);
  if (!main || !sheetEls.length) return;
  const html = document.documentElement;

  // ------------------------------------------------------------ theme.art: a halftone in two plates, on twos
  const arts = $$<HTMLElement>("[data-sa-art]").map((host) => ({ host, c: $<HTMLCanvasElement>("canvas", host)! })).filter((a) => a.c);
  let art: ArtFrames | null = null;
  function halftone(c: HTMLCanvasElement, tick: number) {
    const A = art;
    if (!A) return;
    const cw = 300, ch = Math.round(cw * A.h / A.w);
    if (c.width !== cw) { c.width = cw; c.height = ch; }
    const ctx = c.getContext("2d")!;
    ctx.fillStyle = "#0d0620"; ctx.fillRect(0, 0, cw, ch);
    const m = A.mask[Math.floor(tick / 2) % A.n], sx = A.w / cw, sy = A.h / ch;
    const at = (x: number, y: number) => (x < 0 || y < 0 || x >= cw || y >= ch ? 0 : m[Math.floor(y * sy) * A.w + Math.floor(x * sx)]);
    const plate = (ang: number, color: string, dx: number, dy: number) => {
      const g = 7, ca = Math.cos(ang), sa = Math.sin(ang);
      ctx.fillStyle = color; ctx.globalCompositeOperation = "lighter";
      for (let u = -cw; u < cw * 1.6; u += g) for (let v = -cw; v < cw * 1.6; v += g) {
        const x = u * ca - v * sa + dx, y = u * sa + v * ca + dy;
        if (x < 0 || y < 0 || x >= cw || y >= ch) continue;
        const k = at(x - dx, y - dy);
        if (k < 0.12) continue;
        ctx.beginPath(); ctx.arc(x, y, g * 0.62 * Math.sqrt(k), 0, 7); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    };
    plate(0.26, skinRgba("accent2", "#17d4ff", 0.9), -2, 0);       // the cyan and magenta plates are the style's two accents
    plate(1.31, skinRgba("accent", "#ff3d9a", 0.9), 2, 1.5);
  }
  loadArt().then((a) => { art = a; arts.forEach((x) => { halftone(x.c, 6); x.host.classList.add("sa-drawn"); }); });

  if (reduced) return;                                         // the still prints are the reduced-motion page
  html.classList.add("sa-live");
  const phone = matchMedia("(max-width: 760px)");
  const fine = matchMedia("(pointer: fine)").matches;

  // ------------------------------------------------------------ the belt, the sheets, the actors
  const belts = makeBelts(main, (el) => el.matches("section.sa-sheet") && !el.querySelector("[data-scene]"));
  const sheets: Sheet[] = sheetEls.map((el) => ({ el, top: 0, dim: el.dataset.dim || "night", back: $<HTMLElement>(".sa-back", el) }));
  let aid = 0;
  const actors: Actor[] = $$<HTMLElement>("[data-sa]", main).map((el) => {
    el.classList.add("sa-actor");
    const kind = el.dataset.sa || "card";
    const sheet = sheets.findIndex((s) => s.el.contains(el));
    return { el, kind, belt: null, y: 0, h: 0, text: kind === "title" || kind === "num", box: !(kind === "title" || kind === "num"), seen: false, arrN: -1, pokeN: -99, key: "", mx: "", focus: false, id: aid++, sheet };
  });
  const navLinks = $$<HTMLAnchorElement>(".sa-head__nav a");
  const rate = $<HTMLElement>(".sa-rate"), rateB = $<HTMLElement>("[data-sa-rate]");
  const impact = $<HTMLElement>(".sa-impact"), trail = $<HTMLElement>(".sa-trail");
  rate?.removeAttribute("hidden");
  const trailDots = trail ? [...trail.children] as HTMLElement[] : [];

  let vh = innerHeight, vw = innerWidth, dirty = true;
  function layout() {
    vh = innerHeight; vw = innerWidth;
    measure(belts);
    for (const s of sheets) { const b = beltOf(belts, s.el); s.top = b ? b.top + yInBelt(b, s.el) : s.el.getBoundingClientRect().top + scrollY; }
    for (const a of actors) { const b = beltOf(belts, a.el); a.belt = b; a.y = b ? yInBelt(b, a.el) : 0; a.h = Math.max(1, a.el.offsetHeight); }
    dirty = true;
  }
  const stageTop = (b: Belt) => (scrollY < b.top ? b.top - scrollY : Math.min(0, b.top + Math.max(b.h, b.vh) - b.vh - scrollY));

  // ------------------------------------------------------------ the pointer: rack focus by offset, pokes, a trail of multiples
  let focused: Actor | null = null;
  const actorOf = (t: EventTarget | null) => { const el = (t as HTMLElement | null)?.closest?.<HTMLElement>("[data-sa]"); return el ? actors.find((a) => a.el === el) || null : null; };
  let clock = 0;
  const poke = (a: Actor) => { a.pokeN = clock; };
  main.addEventListener("pointerover", (e) => { if (e.pointerType === "touch") return; const a = actorOf(e.target); if (a && a !== focused) { focused = a; if (a.kind !== "title") poke(a); dirty = true; } });
  main.addEventListener("pointerout", (e) => { const a = actorOf(e.relatedTarget); if (!a && focused) { focused = null; dirty = true; } });
  main.addEventListener("click", (e) => { if ((e.target as HTMLElement).closest("a, button, summary")) { const a = actorOf(e.target); if (a) poke(a); return; } const a = actorOf(e.target); if (a) poke(a); });
  document.addEventListener("focusin", (e) => { const a = actorOf(e.target); if (a) { focused = a; a.seen = true; a.arrN = Math.max(a.arrN, 0); dirty = true; } });
  document.addEventListener("focusout", () => { focused = null; dirty = true; });
  const mouse = { x: -99, y: -99, t: 0 };
  const hist: [number, number][] = [];
  if (fine) addEventListener("pointermove", (e) => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.t = performance.now(); });
  if (fine && trail) trail.removeAttribute("hidden");

  // ------------------------------------------------------------ the clock: 24 ticks a second, samples on the even ones
  let lastN = -1, lastY = scrollY, lastNow = performance.now(), speed = 0, lastMove = 0;
  let impactN = -99, impactAt = 0, lastSheet = -1, shakeN = -99;
  const state = new Map<Belt, { pose: number; from: number; to: number; smear: boolean }>();
  for (const b of belts) state.set(b, { pose: trueOffset(b), from: 0, to: 0, smear: false });
  let rateWord = "HOLD", rateAt = 0, rateHold = 0;

  function sheetIndexAt(y: number) {
    let k = 0;
    for (let i = 0; i < sheets.length; i++) if (sheets[i].top <= y + vh * 0.42) k = i;
    return k;
  }

  function tick(n: number, now: number) {
    clock = n;
    const y = scrollY;
    const even = n % 2 === 0;
    const dyTick = y - lastY;
    const dt = Math.max(0.001, (now - lastNow) / 1000);
    speed += (Math.abs(dyTick) / dt - speed) * 0.5; if (dyTick === 0) speed *= 0.5; if (speed < 1) speed = 0;
    if (dyTick !== 0) lastMove = now;
    lastY = y; lastNow = now;

    // impact frame: a new sheet crosses the middle of the screen while you are moving fast
    const si = sheetIndexAt(y);
    if (lastSheet >= 0 && si !== lastSheet && speed > 450 && now - impactAt > 520 && impact) {
      impactAt = now; impactN = n; shakeN = n + 2;
      const incoming = sheets[Math.max(si, lastSheet)].dim;
      impact.dataset.d = incoming;
      impact.style.setProperty("--hit", HIT[incoming] || HIT.night);
      impact.style.setProperty("--a", `${(Math.random() * 360) | 0}deg`);
      impact.hidden = false;
    }
    lastSheet = si;
    if (impact && !impact.hidden && n >= impactN + 2) impact.hidden = true;

    // the belts: sampled on even ticks; a changed sample is drawn through one smear frame
    let maxD = 0;
    for (const b of belts) {
      const st = state.get(b)!;
      if (y < b.top - vh * 1.5 || y > b.top + Math.max(b.h, b.vh) + vh * 1.5) { st.pose = trueOffset(b); st.smear = false; continue; }
      if (even) {
        const T = trueOffset(b, y);
        if (Math.abs(T - st.pose) >= 1) { st.from = st.pose; st.to = T; st.pose = T; st.smear = true; maxD = Math.max(maxD, Math.abs(T - st.from)); }
        else st.smear = false;
      } else st.smear = false;
      const disp = st.smear ? (st.from + st.to) / 2 : st.pose;
      let sx = 0, sy = 0;
      if (n >= shakeN && n < shakeN + 6) { const k = 1 - (n - shakeN) / 6; sx = (hash(n >> 1, 1) - 0.5) * 18 * k; sy = (hash(n >> 1, 2) - 0.5) * 12 * k; }
      b.belt.style.translate = `${sx.toFixed(1)}px ${(-disp + sy).toFixed(2)}px`;
      b.shown = disp;
    }
    const smearing = belts.some((b) => state.get(b)!.smear);
    const fast = speed > 1100;

    // the backdrops: a print screen that drifts on threes, its plates slipping with speed
    if (n % 3 === 0) {
      const slip = (3 + Math.min(9, speed / 160)).toFixed(1);
      for (const s of sheets) {
        if (!s.back) continue;
        const top = s.top - y;
        if (top > vh * 1.2 || top + s.el.offsetHeight < -vh * 0.2) continue;
        s.back.style.setProperty("--bx", `${((hash(n, 3) - 0.5) * 8).toFixed(1)}px`);
        s.back.style.setProperty("--by", `${((hash(n, 4) - 0.5) * 8).toFixed(1)}px`);
        s.el.style.setProperty("--mx", slip);
      }
    }

    // the actors: poses on twos; a smear frame stretches them along the move; multiples at speed
    for (const a of actors) {
      const b = a.belt;
      if (!b) continue;
      const st = state.get(b)!;
      const disp = st.smear ? (st.from + st.to) / 2 : st.pose;
      const top = stageTop(b) + a.y - disp;
      const hide = () => { if (a.key !== "hidden") { a.key = "hidden"; a.el.style.opacity = "0"; } };
      if (top > vh * 1.15) {                                   // below the screen: unseen, and it will pop again when it comes back from below
        if (a.seen && top > vh * 1.5) { a.seen = false; a.arrN = -1; }
        if (!a.seen) hide();
        continue;
      }
      if (top + a.h < -vh * 0.3) {                             // far above: settled
        if (!a.seen) { a.seen = true; a.arrN = n - 99; }
        if (a.key === "hidden") { a.key = ""; a.el.style.opacity = ""; }
        continue;
      }
      if (!a.seen && (top < vh * 0.93 || b.range - trueOffset(b, y) < 3)) { a.seen = true; a.arrN = n; }
      if (!a.seen) { hide(); continue; }
      // the pose: arrival pop, then pokes, then the smear stretch
      let psx = 1, psy = 1;
      const ta = Math.floor((n - a.arrN) / 2);
      if (ta >= 0 && ta < POP.length - 1) { psx = POP[ta][0]; psy = POP[ta][1]; }
      const tp = Math.floor((n - a.pokeN) / 2);
      if (tp >= 0 && tp < POKE.length - 1) { psx *= POKE[tp][0]; psy *= POKE[tp][1]; }
      let d = 0, dir = 1;
      if (st.smear) { d = Math.abs(st.to - st.from); dir = st.to >= st.from ? 1 : -1; if (top > vh || top + a.h < 0) d = 0; }
      const cap = a.kind === "plate" ? 1 : a.kind === "card" ? 1.28 : 2.6;
      const stretch = d > 0 ? Math.min(cap, 1 + Math.min(d / a.h, 1.6)) : 1;
      psy *= stretch; psx *= d > 0 ? 1 / Math.sqrt(stretch) : 1;
      // plates: how far out of register this actor is
      let mx = 3 + Math.min(8, speed / 220);
      if (focused) mx = a === focused || a.el.contains(focused.el) || focused.el.contains(a.el) ? 1 : 6 + Math.min(8, speed / 220);
      const mxs = (Math.round(mx * 2) / 2).toFixed(1);
      // multiples: echoes along the path, in the three plate colours
      const ne = a.kind === "plate" ? 0 : d > 260 ? 3 : d > 110 ? 2 : d > 40 ? 1 : 0;
      let fx = "";
      if (ne > 0) {
        const e = [0.34, 0.68, 1].slice(0, ne).map((q, i) => `0 ${(dir * d * q).toFixed(0)}px 0 var(--p${"abc"[i]})`);
        if (a.text) fx = `calc(var(--mx) * -1px) 0 0 var(--pa), calc(var(--mx) * 1px) calc(var(--mx) * .45px) 0 var(--pb), ${e.join(", ")}`;
        else if (!phone.matches && fast && a.h * (a.el.offsetWidth || 1) < 260000) fx = e.map((s) => `drop-shadow(${s})`).join(" ");
      }
      const key = `${psx.toFixed(3)}|${psy.toFixed(3)}|${mxs}|${fx}`;
      if (key !== a.key) {
        a.key = key;
        const s = a.el.style;
        s.opacity = "";
        s.scale = psx === 1 && psy === 1 ? "" : `${psx.toFixed(3)} ${psy.toFixed(3)}`;
        if (a.mx !== mxs) { a.mx = mxs; s.setProperty("--mx", mxs); }
        if (a.text) s.textShadow = fx; else s.filter = fx;
      }
    }

    // the pointer's trail: multiples on ones
    if (fine && trail && trailDots.length) {
      const alive = now - mouse.t < 700;
      trail.hidden = !alive;
      if (alive) {
        hist.unshift([mouse.x, mouse.y]); if (hist.length > 8) hist.pop();
        trailDots.forEach((dot, i) => {
          const h0 = hist[Math.min(hist.length - 1, i * 2)] || hist[0], h1 = hist[Math.min(hist.length - 1, i * 2 + 1)] || h0;
          const vx = h0[0] - h1[0], vy = h0[1] - h1[1], sp = Math.hypot(vx, vy);
          dot.style.translate = `${h0[0].toFixed(0)}px ${h0[1].toFixed(0)}px`;
          dot.style.rotate = `${(Math.atan2(vy, vx) * 57.3).toFixed(0)}deg`;
          dot.style.scale = `${(1 + Math.min(4, sp / 7)).toFixed(2)} ${(1 / (1 + Math.min(1.5, sp / 30))).toFixed(2)}`;
        });
      }
    }

    // art, the readout, the nav
    if (even) arts.forEach((a2) => { const r = a2.host.getBoundingClientRect(); if (r.bottom > 0 && r.top < vh) halftone(a2.c, n); });
    const word = speed < 2 && now - lastMove > 250 ? "HOLD" : ne3(maxD, fast, smearing);
    if (word !== rateWord && now - rateAt > 160) { rateWord = word; rateAt = now; if (rateB) rateB.textContent = word; }
    if (n % 6 === 0) {
      let id = "";
      for (const s of sheets) if (s.top <= y + vh * 0.42 && s.el.id) id = s.el.id;
      navLinks.forEach((a3) => a3.classList.toggle("is-on", !!id && a3.getAttribute("href") === `#${id}`));
    }
    dirty = false;
  }
  function ne3(maxD: number, fast: boolean, smearing: boolean) { return fast ? "MULTIPLES" : smearing && maxD > 14 ? "SMEAR" : "TWOS"; }

  // ------------------------------------------------------------ wire up
  layout();
  watch(belts, () => { layout(); });
  addEventListener("resize", layout);
  phone.addEventListener?.("change", layout);
  document.fonts?.ready.then(layout);
  addEventListener("load", layout);
  setTimeout(layout, 900);
  wireLinks(belts);
  onFrame(() => {
    const now = performance.now();
    const n = Math.floor(now / TICK);
    if (n !== lastN) { lastN = n; tick(n, now); }
  });
}
