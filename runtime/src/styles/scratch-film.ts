/**
 * Scratch film: the page is a strip of drawn film pulled through a gate (Len Lye, Norman McLaren, Stan Brakhage).
 * The screen is the gate. The strip runs down the left edge with its sprocket holes, the neighbouring frames and a drawn
 * optical track, moving exactly as fast as you scroll; the frame in the gate is projected full screen, a new scratched,
 * dyed or pressed drawing for every frame that passes (up to 24 a second, never repeated, never registered). The page's
 * text is carried by a belt that is pulled in steps of one perforation (a quarter of a frame, at most 24 steps a second)
 * and seats with a small bump when you stop: the intermittent movement of a projector, applied to the page. Section
 * handovers are splices (tape across the join, a change of stock, one frame of flash leader). Titles are scratched in a
 * few letters at a time; plates and frames are cut in with a short wipe as they reach the gate. When you are not scrolling
 * the projector keeps running at 6 frames a second (the Run switch stops it). The pointer is a needle: press and drag on the
 * picture and a scratch is drawn into the emulsion, which belongs to the strip and travels away with it. Sound plays the
 * drawn track as marks pass the head. theme.art is engraved as scratched hatching, redrawn every frame.
 * Reduced motion: no belt, no projection; each reel carries one still frame of its stock, the strip is a still rail.
 * Research: docs/styles/styles-32-33.md, section 1.
 */
import { $, $$, chars, onFrame, reduced } from "./_kit";
import { makeBelts, measure, watch, trueOffset, setOffset, yInBelt, wireLinks, beltOf, scrollTargetFor, type Belt } from "./_belt";
import { drawFrame, drawFlash, drawRunOn, hash, FPB, LAMP, lamp, meanLuma, type Tone } from "./_film-draw";
import { loadArt, type ArtFrames } from "./_art";

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));

interface Reel { el: HTMLElement; id: string; top: number; tone: Tone }
interface Title { el: HTMLElement; spans: HTMLElement[]; belt: Belt | null; y: number; h: number; shown: number }
interface Cut { el: HTMLElement; belt: Belt | null; y: number; h: number; s: number; force: boolean }
interface Stroke { pts: number[]; seed: number }

export default function start() {
  const main = $<HTMLElement>("main");
  const reelEls = $$<HTMLElement>(".sf-reel", main || document);
  if (!main || !reelEls.length) return;
  const html = document.documentElement;

  // ------------------------------------------------------------ theme.art engraved as scratched hatching, new every frame
  const arts = $$<HTMLElement>("[data-sf-art]").map((host) => ({ host, c: $<HTMLCanvasElement>("canvas", host)! })).filter((a) => a.c);
  let art: ArtFrames | null = null;
  function engrave(c: HTMLCanvasElement, frame: number) {
    const A = art;
    if (!A) return;
    const cw = 320, ch = Math.round(cw * A.h / A.w);
    if (c.width !== cw) { c.width = cw; c.height = ch; }
    const ctx = c.getContext("2d")!;
    ctx.fillStyle = "#050505"; ctx.fillRect(0, 0, cw, ch);
    ctx.strokeStyle = LAMP; ctx.lineWidth = 1.1; ctx.lineCap = "round";
    const m = A.mask[((Math.floor(frame / 2) % A.n) + A.n) % A.n], sx = A.w / cw, sy = A.h / ch;
    const at = (x: number, y: number) => (x < 0 || y < 0 || x >= cw || y >= ch ? 0 : m[Math.floor(y * sy) * A.w + Math.floor(x * sx)]);
    // needle hatching at two angles, thicker where the picture is brighter; every frame is hatched again by a new hand
    const hatch = (ang: number, gap: number, thr: number, alpha: number, seed: number) => {
      const c = Math.cos(ang), sn = Math.sin(ang), diag = Math.hypot(cw, ch);
      ctx.globalAlpha = alpha;
      for (let o = -diag / 2; o < diag / 2; o += gap) {
        const jo = (hash(Math.round(o), frame, seed) - 0.5) * gap * 0.7;
        let x0 = 0, y0 = 0, on = false;
        for (let t = -diag / 2; t <= diag / 2; t += 2) {
          const x = cw / 2 + c * t - sn * (o + jo), y = ch / 2 + sn * t + c * (o + jo);
          const v = at(x, y) > thr;
          if (v && !on) { on = true; x0 = x; y0 = y; }
          if ((!v || t + 2 > diag / 2) && on) {
            on = false;
            if (Math.hypot(x - x0, y - y0) > 3) { ctx.beginPath(); ctx.moveTo(x0 + (hash(Math.round(x0), Math.round(y0), frame) - 0.5) * 1.6, y0); ctx.lineTo(x + (hash(Math.round(x), Math.round(y), frame + 3) - 0.5) * 1.6, y + (hash(Math.round(y), Math.round(x), frame) - 0.5) * 1.4); ctx.stroke(); }
          }
        }
      }
    };
    hatch(0.62, 3.6, 0.3, 0.8, 11);
    hatch(-0.5, 6.2, 0.7, 0.9, 12);
    ctx.globalAlpha = 1;
  }
  loadArt().then((a) => { art = a; arts.forEach((x) => { engrave(x.c, 7); x.host.classList.add("sf-drawn"); }); });

  // ------------------------------------------------------------ reduced motion: one still frame of each stock behind each reel
  if (reduced) {
    reelEls.forEach((el, i) => {
      const c = document.createElement("canvas"); c.width = 640; c.height = 360;
      drawFrame(c.getContext("2d")!, 640, 360, 9 + i * 37, (el.dataset.tone as Tone) || "leader", 1.6);
      el.style.backgroundImage = `url(${c.toDataURL("image/jpeg", 0.82)})`;
      el.style.backgroundSize = "cover"; el.style.backgroundPosition = "center"; el.style.backgroundRepeat = "no-repeat";
    });
    return;
  }

  html.classList.add("sf-live");
  const gate = $<HTMLCanvasElement>(".sf-gate")!, scratchC = $<HTMLCanvasElement>(".sf-scratch")!, stripC = $<HTMLCanvasElement>(".sf-strip canvas")!;
  const gctx = gate.getContext("2d")!, sctx = scratchC.getContext("2d")!, rctx = stripC.getContext("2d")!;
  const hud = $<HTMLElement>(".sf-hud"), countEl = $<HTMLElement>('[data-sf="count"]'), beatEl = $<HTMLElement>('[data-sf="beat"]');
  const runBtn = $<HTMLButtonElement>('[data-sf="run"]'), soundBtn = $<HTMLButtonElement>('[data-sf="sound"]');
  hud?.removeAttribute("hidden");
  let run = true, sound = false;
  runBtn?.addEventListener("click", () => { run = !run; runBtn.setAttribute("aria-pressed", String(run)); dirty = true; });

  // ------------------------------------------------------------ the belt, the reels, the lettering and the cuts
  const belts = makeBelts(main, (el) => el.matches("section.sf-reel") && !el.querySelector("[data-scene]"));
  const reels: Reel[] = reelEls.map((el) => ({ el, id: el.id, top: 0, tone: (el.dataset.tone as Tone) || "leader" }));
  const titles: Title[] = $$<HTMLElement>(".sf-title", main).map((el) => ({ el, spans: chars(el, "sf-ch"), belt: null, y: 0, h: 0, shown: -1 }));
  const cuts: Cut[] = $$<HTMLElement>(".sf-cut", main).map((el) => ({ el, belt: null, y: 0, h: 0, s: -1, force: false }));
  const navLinks = $$<HTMLAnchorElement>(".sf-head__nav a");
  document.addEventListener("focusin", (e) => { const c = cuts.find((q) => q.el.contains(e.target as Node)); if (c) { c.force = true; dirty = true; } });

  let P = 42, p4 = 10.5, vh = innerHeight, vw = innerWidth, G = vh * 0.4, rail = 76, dpr = 1;
  let gw = 0, gh = 0, lw = 1.3;
  const cssNum = (name: string, d: number) => parseFloat(getComputedStyle(html).getPropertyValue(name)) || d;
  function toneAt(docY: number): Tone {
    let t = reels[0].tone;
    for (const r of reels) { if (r.top <= docY) t = r.tone; else break; }
    return t;
  }
  function layout() {
    vh = innerHeight; vw = innerWidth; G = vh * 0.4;
    P = cssNum("--pitch", 42); p4 = P / 4; rail = cssNum("--rail", 76);
    dpr = Math.min(2, devicePixelRatio || 1);
    measure(belts);
    for (const r of reels) { const b = beltOf(belts, r.el); r.top = b ? b.top + yInBelt(b, r.el) : r.el.getBoundingClientRect().top + scrollY; }
    reels.sort((a, b) => a.top - b.top);
    for (const t of titles) { const b = beltOf(belts, t.el); t.belt = b; t.y = b ? yInBelt(b, t.el) : 0; t.h = t.el.offsetHeight; }
    for (const c of cuts) { const b = beltOf(belts, c.el); c.belt = b; c.y = b ? yInBelt(b, c.el) : 0; c.h = c.el.offsetHeight; }
    const k = vw < 761 ? 1.7 : 2.3;
    gw = Math.ceil(vw / k); gh = Math.ceil(vh / k); lw = Math.max(0.9, gw / 520);
    if (gate.width !== gw || gate.height !== gh) { gate.width = gw; gate.height = gh; }
    scratchC.width = vw; scratchC.height = vh;
    stripC.width = Math.round(rail * dpr); stripC.height = Math.round(vh * dpr);
    thumbs.clear();
    dirty = true; gateDirty = true;
  }

  // ------------------------------------------------------------ the strip: the film beside the screen
  const thumbs = new Map<string, HTMLCanvasElement>();
  function thumb(tone: Tone, frame: number, w: number, h: number): HTMLCanvasElement {
    const key = `${tone}${frame}`;
    let c = thumbs.get(key);
    if (c) return c;
    c = document.createElement("canvas"); c.width = Math.max(4, Math.round(w * dpr)); c.height = Math.max(4, Math.round(h * dpr));
    drawFrame(c.getContext("2d")!, c.width, c.height, frame, tone, Math.max(0.7, dpr * 0.8));
    thumbs.set(key, c);
    if (thumbs.size > 140) thumbs.delete(thumbs.keys().next().value as string);
    return c;
  }
  function drawStrip(ry: number) {
    const ctx = rctx, W = rail, H = vh;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#0b0b0a"; ctx.fillRect(0, 0, W, H);
    const phone = W < 50, lane = phone ? 7 : 9, x1 = phone ? 4 : 7, tr = phone ? 3 : 7;
    const x0 = x1 + lane + 3, pw = W - 2 * (x1 + lane + 3) - tr;
    // sprocket holes, four to the frame, riding with the page
    ctx.fillStyle = lamp(0.6);
    const off = -(((ry % p4) + p4) % p4), hh = p4 * 0.5;
    for (let yy = off - p4; yy < H + p4; yy += p4) { ctx.fillRect(x1, yy, lane, hh); ctx.fillRect(W - x1 - lane, yy, lane, hh); }
    // the frames
    const j0 = Math.floor(ry / P) - 1, j1 = Math.floor((ry + H) / P) + 1;
    for (let j = j0; j <= j1; j++) {
      if (j < 0) continue;
      const top = j * P - ry;
      ctx.drawImage(thumb(toneAt(j * P + P / 2), j, pw, P - 3), x0, top + 1, pw, P - 3);
      for (let s = 0; s < 4; s++) { // the optical track: a variable-area track, one bar per perforation
        const wq = 0.2 + 0.8 * hash(j * 4 + s, 5), bw = tr * wq;
        ctx.fillStyle = lamp(0.85); ctx.fillRect(W - x1 - lane - 2 - tr + (tr - bw) / 2, top + s * p4 + 1.5, bw, p4 - 2.5);
      }
      if (!phone && j % 16 === 0) { ctx.fillStyle = lamp(0.8); ctx.font = "8px 'Share Tech Mono', monospace"; ctx.fillText(`FT ${String(j / 16).padStart(3, "0")}`, x0 + 2, top + 10); }
    }
    // splices
    for (let i = 1; i < reels.length; i++) {
      const ty = reels[i].top - ry;
      if (ty < -20 || ty > H + 20) continue;
      ctx.fillStyle = "rgba(240,222,166,.78)"; ctx.fillRect(0, ty - 6, W, 12);
      ctx.fillStyle = "rgba(0,0,0,.35)"; for (let x = 3; x < W; x += 6) ctx.fillRect(x, ty - 6, 1, 12);
    }
    // the gate
    const gj = Math.floor((ry + G) / P), gtop = gj * P - ry;
    ctx.strokeStyle = LAMP; ctx.lineWidth = 1.5; ctx.strokeRect(x0 - 2, gtop - 0.5, pw + 4, P + 1);
    ctx.fillStyle = LAMP; ctx.beginPath(); ctx.moveTo(0, gtop + P / 2 - 5); ctx.lineTo(x1 - 1, gtop + P / 2); ctx.lineTo(0, gtop + P / 2 + 5); ctx.fill();
  }

  // ------------------------------------------------------------ geometry of the belt on screen
  const stageTop = (b: Belt) => (scrollY < b.top ? b.top - scrollY : Math.min(0, b.top + Math.max(b.h, b.vh) - b.vh - scrollY));

  // ------------------------------------------------------------ sound: the drawn track, played as marks pass the head
  let actx: AudioContext | null = null, master: GainNode | null = null, lastNote = 0;
  const SCALE = [220, 246.94, 293.66, 329.63, 392];
  function audio(): AudioContext | null {
    if (actx) return actx;
    const AC = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AC) return null;
    actx = new AC(); master = actx!.createGain(); master.gain.value = 0.5; master.connect(actx!.destination);
    return actx;
  }
  function note(frame: number, v: number) {
    const a = actx; if (!a || !master || a.state !== "running") return;
    const t = a.currentTime, now = performance.now();
    if (now - lastNote < 38) return;
    lastNote = now;
    const g = a.createGain(), o = a.createOscillator();
    const f = SCALE[Math.floor(hash(frame, 61) * 5)] * (hash(frame, 62) < 0.3 ? 2 : hash(frame, 62) < 0.5 ? 0.5 : 1);
    o.type = hash(frame, 63) < 0.5 ? "square" : "triangle"; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.045 * clamp(0.35 + v / 1500), t + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
    o.connect(g); g.connect(master); o.start(t); o.stop(t + 0.06);
    if (frame % FPB === 0) {                                    // the beat: a low drum
      const k = a.createOscillator(), kg = a.createGain();
      k.frequency.setValueAtTime(110, t); k.frequency.exponentialRampToValueAtTime(48, t + 0.12);
      kg.gain.setValueAtTime(0.16, t); kg.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
      k.connect(kg); kg.connect(master); k.start(t); k.stop(t + 0.18);
    }
  }
  function tick(seed: number) {                                 // a scratch on the optical track: a burst of noise
    const a = actx; if (!a || !master || a.state !== "running") return;
    const len = Math.floor(a.sampleRate * 0.04), buf = a.createBuffer(1, len, a.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (hash(seed, i) * 2 - 1) * (1 - i / len);
    const s = a.createBufferSource(), g = a.createGain(), f = a.createBiquadFilter();
    f.type = "highpass"; f.frequency.value = 2400; g.gain.value = 0.12; s.buffer = buf; s.connect(f); f.connect(g); g.connect(master); s.start();
  }
  soundBtn?.addEventListener("click", () => {
    sound = !sound; soundBtn.setAttribute("aria-pressed", String(sound));
    if (sound) { const a = audio(); a?.resume?.(); }
  });

  // ------------------------------------------------------------ the needle: scratches drawn into the emulsion
  const strokes: Stroke[] = [];
  let pen: { pts: number[]; touch: boolean; x0: number; y0: number; on: boolean; lastTick: number } | null = null;
  const NO_NEEDLE = "a, button, summary, details, input, textarea, select, video, iframe, label, .sf-plate, .sf-fr, .sf-title, .sf-slate, .sf-btn, .sf-hud, .sf-head, .sf-edgeprint, .sf-small, .ss-scene, .ss-phone, .ss-app";
  const eligible = (e: PointerEvent) => !(e.target as HTMLElement).closest?.(NO_NEEDLE) && (e.pointerType !== "mouse" || e.button === 0);
  main.addEventListener("mousedown", (e) => { if (!(e.target as HTMLElement).closest?.(NO_NEEDLE) && e.button === 0) e.preventDefault(); });
  main.addEventListener("pointerdown", (e) => {
    if (!eligible(e)) return;
    pen = { pts: [e.clientX, e.clientY + scrollY], touch: e.pointerType === "touch", x0: e.clientX, y0: e.clientY, on: e.pointerType !== "touch", lastTick: 0 };
  });
  addEventListener("pointermove", (e) => {
    if (!pen) return;
    if (pen.touch && !pen.on) {                                  // a touch is a scratch only if it goes sideways; up and down is the page's
      const dx = Math.abs(e.clientX - pen.x0), dy = Math.abs(e.clientY - pen.y0);
      if (dx + dy < 8) return;
      if (dy > dx * 1.1) { pen = null; return; }
      pen.on = true;
    }
    const n = pen.pts.length;
    if (Math.hypot(e.clientX - pen.pts[n - 2], e.clientY + scrollY - pen.pts[n - 1]) < 3) return;
    pen.pts.push(e.clientX, e.clientY + scrollY);
    if (sound && performance.now() - pen.lastTick > 70) { pen.lastTick = performance.now(); tick(pen.pts.length); }
    dirty = true;
    commitPen(false);
  });
  const stroke = new Map<object, Stroke>();
  function commitPen(final: boolean) {
    if (!pen) return;
    let s = stroke.get(pen);
    if (!s) { s = { pts: pen.pts, seed: (Math.random() * 1e6) | 0 }; stroke.set(pen, s); strokes.push(s); if (strokes.length > 40) strokes.shift(); }
    s.pts = pen.pts;
    if (final) { if (pen.pts.length <= 2) { s.pts = [pen.pts[0], pen.pts[1], pen.pts[0] + 0.5, pen.pts[1] + 0.5]; } stroke.delete(pen); pen = null; }
  }
  const endPen = () => { if (pen && pen.on) commitPen(true); else pen = null; dirty = true; };
  addEventListener("pointerup", endPen);
  addEventListener("pointercancel", () => { pen = null; });
  function drawScratches(frame: number) {
    sctx.clearRect(0, 0, vw, vh);
    if (!strokes.length) return;
    sctx.strokeStyle = lamp(0.92); sctx.lineCap = "round"; sctx.lineJoin = "round"; sctx.lineWidth = 1.7;
    for (const s of strokes) {
      const p = s.pts;
      const y0 = p[1] - scrollY;
      if (y0 < -vh && p[p.length - 1] - scrollY < -vh) continue;
      sctx.beginPath();
      for (let i = 0; i < p.length; i += 2) {
        const jx = (hash(s.seed + i, frame, 1) - 0.5) * 2.2, jy = (hash(s.seed + i, frame, 2) - 0.5) * 2.2;
        if (i === 0) sctx.moveTo(p[i] + jx, p[i + 1] - scrollY + jy); else sctx.lineTo(p[i] + jx, p[i + 1] - scrollY + jy);
      }
      sctx.stroke();
    }
  }

  // ------------------------------------------------------------ the projector
  let dirty = true, gateDirty = true;
  let lastY = scrollY, lastNow = performance.now(), lastMove = 0, speed = 0;
  let lastDraw = 0, lastFrameDrawn = -1, amb = 0, lastAmb = 0, curTone: Tone | null = null, flashUntil = 0, lastFlash = 0, flashing = false;
  let lastFrame = -1, lastRailY = -1e9, lastWob = -1;
  const introStart = performance.now(), introMs = 1500, introDone = scrollY > 40;
  const vel = new Map<Belt, number>();

  function cutState(c: Cut, b: Belt | null): number {
    if (!b) return 4;
    if (c.force) return 4;
    if (b.range - trueOffset(b) < 3) return 4;
    const top = stageTop(b) + c.y - b.shown;
    if (top + c.h < 0) return 4;                                  // already passed: stay cut in
    const span = Math.max(24, Math.min(vh * 0.2, c.h));
    return Math.floor(clamp((vh * 0.95 - top) / span) * 4.999);
  }
  function applyCut(c: Cut, s: number) {
    c.s = s;
    const st = c.el.style;
    // opacity, not visibility: a hidden plate must stay reachable by keyboard (focus cuts it in)
    if (s === 0) { st.opacity = "0"; st.clipPath = ""; }
    else if (s >= 4) { st.opacity = ""; st.clipPath = ""; }
    else { st.opacity = ""; st.clipPath = `inset(0 ${(100 - s * 25).toFixed(0)}% 0 0)`; }
  }
  function lettering(t: Title, frame: number, wobble: boolean) {
    const b = t.belt;
    let n = t.spans.length;
    if (b) {
      const top = stageTop(b) + t.y - b.shown;
      const k = top + t.h < 0 || b.range - trueOffset(b) < 3 ? 1 : clamp((vh * 0.93 - top) / (vh * 0.3));
      const want = k >= 1 ? n : Math.min(n, Math.floor(k * (n + 2) / 2) * 2);   // two letters at a time, a stutter
      if (want !== t.shown) { t.spans.forEach((s, i) => { s.style.visibility = i < want ? "" : "hidden"; }); t.shown = want; }
      if (top > vh || top + t.h < 0) return;
    }
    if (!wobble) return;
    t.spans.forEach((s, i) => {
      if (i >= t.shown && t.shown >= 0) return;
      const a = 1.5;
      s.style.setProperty("--cx", `${((hash(i, frame, 7) - 0.5) * a).toFixed(1)}px`);
      s.style.setProperty("--cy", `${((hash(i, frame, 8) - 0.5) * a).toFixed(1)}px`);
      s.style.setProperty("--cr", `${((hash(i, frame, 9) - 0.5) * 2.4).toFixed(1)}deg`);
    });
  }

  function drawGate(frame: number, y: number, tone: Tone) {
    drawFrame(gctx, gw, gh, frame, tone, lw);
    drawRunOn(gctx, gw, gh, y / 2.3, tone, lw, speed);
    if (speed > 1500) {                                           // too fast to see frames: the picture streaks along the strip
      gctx.fillStyle = lamp(0.22);
      for (let k = 0; k < 16; k++) gctx.fillRect(Math.floor(hash(frame, k, 3) * gw), 0, 1, gh);
    }
    gate.style.translate = `${((hash(frame, 1, 9) - 0.5) * 3).toFixed(1)}px ${((hash(frame, 2, 9) - 0.5) * 3).toFixed(1)}px`;   // gate weave
    lastFrameDrawn = frame; lastDraw = performance.now();
    arts.forEach((a) => { const r = a.host.getBoundingClientRect(); if (r.bottom > 0 && r.top < vh) engrave(a.c, frame); });
  }

  onFrame((f) => {
    const now = performance.now();
    const y = f.y, dtms = Math.max(1, now - lastNow);
    const dy = y - lastY;
    if (dy !== 0) lastMove = now;
    speed += (Math.abs(dy) / (dtms / 1000) - speed) * 0.3; if (dy === 0) speed *= 0.82; if (speed < 1) speed = 0;
    lastNow = now; lastY = y;
    const moving = now - lastMove < 90;
    if (moving) amb = 0;

    // the intro: the film is run up past the gate and seats at the top
    let introY = 0;
    if (!introDone && run && now - introStart < introMs) { const q = (now - introStart) / introMs; introY = (1 - (1 - (1 - q) * (1 - q) * (1 - q))) * P * 34; }

    // the belt: pulled in perforation steps while you pull, seated when you stop
    const step = clamp(Math.ceil(speed / 24 / p4) * p4, p4, P * 3);
    let moved = false;
    for (const b of belts) {
      if (y < b.top - vh * 1.5 || y > b.top + Math.max(b.h, b.vh) + vh * 1.5) { if (b.shown !== trueOffset(b)) setOffset(b, trueOffset(b)); continue; }
      const off = trueOffset(b);
      let disp: number;
      if (off <= 0 || off >= b.range - 0.5) { disp = off; vel.set(b, 0); }
      else if (moving) { disp = Math.floor(off / step) * step; vel.set(b, 0); }
      else {
        const e = off - b.shown; let v = ((vel.get(b) || 0) + e * 0.3) * 0.58;
        disp = b.shown + v; if (Math.abs(off - disp) < 0.35 && Math.abs(v) < 0.35) { disp = off; v = 0; }
        vel.set(b, v);
      }
      if (Math.abs(disp - b.shown) > 0.01) { setOffset(b, disp); moved = true; }
    }

    // the film: which frame is in the gate, which stock, and the beat
    const ry = y + introY;
    const fcur = Math.max(0, Math.floor((ry + G) / P));
    const tone = toneAt(y + G + introY * 0);
    const frameChanged = fcur !== lastFrame;
    if (frameChanged) {
      const d = fcur - lastFrame;
      if (sound && lastFrame >= 0 && Math.abs(d) <= 3) note(fcur, speed);
      lastFrame = fcur;
      if (countEl) countEl.textContent = `FT ${String(Math.floor(fcur / 16)).padStart(4, "0")}+${String(fcur % 16).padStart(2, "0")}`;
      if (beatEl) beatEl.textContent = `${Math.floor(fcur / (FPB * 4)) + 1}.${Math.floor(fcur / FPB) % 4 + 1}`;
    }
    // a splice flashes one frame of leader, never more than 2 a second
    if (curTone && tone !== curTone && now - lastFlash > 450 && moving) {
      lastFlash = now; flashUntil = now + 42; flashing = true;
      drawFlash(gctx, gw, gh, fcur);
    }
    curTone = tone;
    if (now < flashUntil) { /* the flash frame is on the screen */ }
    else {
      const cadence = flashing ? 0 : 1000 / 24;
      let drawNow = false, fr = fcur;
      if (flashing) { drawNow = true; flashing = false; }
      else if ((frameChanged || gateDirty) && now - lastDraw >= cadence) drawNow = true;
      else if (!moving && run && now - lastDraw >= 1000 / 6) { amb++; fr = fcur + amb; drawNow = true; }
      if (drawNow) { gateDirty = false; drawGate(fr, ry, tone); lastAmb = fr; }
    }

    // the strip beside the screen, the text on the belt, the scratches
    if (ry !== lastRailY || dirty || frameChanged) { drawStrip(ry); lastRailY = ry; }
    const wobbleDue = lastAmb !== lastWob && (run || moving);
    const lf = lastAmb;
    for (const t of titles) lettering(t, lf, wobbleDue);
    if (wobbleDue) lastWob = lastAmb;
    if (moved || dirty || frameChanged || moving) for (const c of cuts) { const s = cutState(c, c.belt); if (s !== c.s) applyCut(c, s); }
    if (strokes.length || dirty) drawScratches(lf);

    // the nav follows the reel in the gate
    if (frameChanged || dirty) {
      let id = "";
      for (const r of reels) if (r.top <= y + G && r.id) id = r.id;
      navLinks.forEach((a) => a.classList.toggle("is-on", !!id && a.getAttribute("href") === `#${id}`));
    }
    dirty = false;
  });

  // ------------------------------------------------------------ wire up
  layout();
  watch(belts, () => { layout(); });
  addEventListener("resize", layout);
  document.fonts?.ready.then(layout);
  addEventListener("load", layout);
  setTimeout(layout, 900);
  wireLinks(belts);
  (window as any).__sfY = (id: string) => { const el = document.getElementById(id); return el ? scrollTargetFor(belts, el, 0.05) : null; };
  (window as any).__sfAudit = (tone: Tone, from = 0, count = 120) => {
    const c = document.createElement("canvas"); const L: number[] = [];
    for (let i = 0; i < count; i++) L.push(meanLuma(from + i, tone, c));
    let maxD = 0; for (let i = 1; i < L.length; i++) maxD = Math.max(maxD, Math.abs(L[i] - L[i - 1]));
    return { min: Math.min(...L), max: Math.max(...L), maxStep: maxD };
  };
}
