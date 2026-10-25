/**
 * Flipbook drawings: the pencil animation in each section's field, one call per page. Every stroke is jittered with a
 * seed that includes the page number, so each page is "redrawn by hand" and held drawings boil slightly from page to
 * page, as real flipbook drawings do. Graphite for the line, the animator's blue pencil for construction lines and
 * paths, red pencil for keys and accents.
 */
import type { ArtFrames } from "./_art";
import { skin } from "./_kit";

// the red pencil is the style's accent, so a brand's accent; graphite, blue pencil and paper are the animator's tools
export const LEAD = "#2f2f33", BLUE = "#3461b0", RED = skin("accent", "#c4452e"), PAPER = "#f7f3ea";
export const HAND = '"Caveat", "Comic Sans MS", cursive', MONO = '"Courier Prime", monospace';
const TAU = Math.PI * 2;
const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = (t: number) => { t = clamp(t); return t * t * (3 - 2 * t); };

export interface Device { app?: string; title?: string; label?: string; button?: string; options?: string[]; selected?: string }
export interface Run {
  type: string;
  pages: number;
  items: { start: number; end: number }[];   // page ranges (local) of each item's own run
  lead: number;                              // pages before the first item
  device?: Device | null;
  stats?: { value: string; unit: string }[];
  whens?: string[];
  tags?: string[];
  word?: string;
  art?: ArtFrames | null;
  img?: HTMLImageElement | null;
}
export interface Rect { x: number; y: number; w: number; h: number }

function rng(seed: number) {
  let s = (Math.abs(Math.floor(seed)) % 2147483646) + 1;
  return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
}

/** A pencil line through points: two light passes, each point nudged a little (the boil). */
export function pencil(ctx: CanvasRenderingContext2D, pts: [number, number][], seed: number, color = LEAD, w = 2, jit = 1.1, passes = 2, close = false) {
  if (pts.length < 2) return;
  const r = rng(seed);
  ctx.strokeStyle = color; ctx.lineCap = "round"; ctx.lineJoin = "round";
  for (let p = 0; p < passes; p++) {
    ctx.globalAlpha = p === 0 ? 0.9 : 0.45;
    ctx.lineWidth = p === 0 ? w : w * 0.7;
    ctx.beginPath();
    const n = close ? pts.length + 1 : pts.length;
    for (let i = 0; i < n; i++) {
      const [x, y] = pts[i % pts.length];
      const jx = (r() - 0.5) * 2 * jit, jy = (r() - 0.5) * 2 * jit;
      if (i === 0) ctx.moveTo(x + jx, y + jy); else ctx.lineTo(x + jx, y + jy);
    }
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}
function seg(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, seed: number, color = LEAD, w = 2) {
  const n = Math.max(2, Math.round(Math.hypot(x1 - x0, y1 - y0) / 14));
  const pts: [number, number][] = [];
  for (let i = 0; i <= n; i++) pts.push([x0 + (x1 - x0) * (i / n), y0 + (y1 - y0) * (i / n)]);
  pencil(ctx, pts, seed, color, w);
}
function ring(ctx: CanvasRenderingContext2D, cx: number, cy: number, rx: number, ry: number, seed: number, color = LEAD, w = 2, frac = 1, a0 = -Math.PI / 2) {
  const r = rng(seed + 3);
  const n = Math.max(6, Math.round(40 * frac));
  const pts: [number, number][] = [];
  const wob = 1 + (r() - 0.5) * 0.04;
  for (let i = 0; i <= n; i++) {
    const a = a0 + (i / n) * TAU * frac * 1.04;
    pts.push([cx + Math.cos(a) * rx * wob, cy + Math.sin(a) * ry]);
  }
  pencil(ctx, pts, seed, color, w);
}
/** Parallel hatching inside the current clip path. */
function hatch(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, seed: number, color = LEAD, gap = 6, alpha = 0.5, angle = -0.9) {
  const r = rng(seed + 9);
  ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = 1.1;
  const c = Math.cos(angle), s = Math.sin(angle), L = w + h;
  ctx.beginPath();
  for (let d = -L; d < L; d += gap + (r() - 0.5) * 1.5) {
    const mx = x + w / 2 + d * -s, my = y + h / 2 + d * c;
    ctx.moveTo(mx - c * L, my - s * L); ctx.lineTo(mx + c * L, my + s * L);
  }
  ctx.stroke(); ctx.restore();
}
function hand(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, size: number, color = LEAD, align: CanvasTextAlign = "center", weight = 700) {
  ctx.font = `${weight} ${size}px ${HAND}`; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = "alphabetic";
  ctx.fillText(text, x, y); ctx.textAlign = "left";
}

// ---------------------------------------------------------------- the page itself
/** Paper, field guide and the animator's notation; the drawing goes on top. */
export function pageFurniture(ctx: CanvasRenderingContext2D, W: number, H: number, field: Rect, page: number, total: number, scene: number, local: number, pages: number) {
  ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
  const r = rng(page * 7 + 1);
  // tooth and the odd smudge
  ctx.fillStyle = "rgba(90, 80, 60, .05)";
  for (let i = 0; i < (W * H) / 900; i++) ctx.fillRect(r() * W, r() * H, 1 + r() * 2, 1);
  const gx = W * (0.2 + r() * 0.6), gy = H * (0.3 + r() * 0.5);
  const g = ctx.createRadialGradient(gx, gy, 2, gx, gy, W * 0.12);
  g.addColorStop(0, "rgba(60, 60, 70, .035)"); g.addColorStop(1, "rgba(60, 60, 70, 0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // peg holes along the top edge (the peg bar sits over them)
  ctx.fillStyle = skin("bg", "#1f2427");     // the table seen through the peg holes
  const cx = W / 2;
  ctx.beginPath(); ctx.arc(cx, 17, 6, 0, TAU); ctx.fill();
  for (const d of [-1, 1]) { ctx.beginPath(); ctx.ellipse(cx + d * Math.min(W * 0.21, 150), 17, 15, 5, 0, 0, TAU); ctx.fill(); }
  // field guide
  ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = "rgba(52, 97, 176, .32)"; ctx.lineWidth = 1;
  ctx.strokeRect(field.x + 0.5, field.y + 0.5, field.w - 1, field.h - 1); ctx.restore();
  ctx.strokeStyle = "rgba(52, 97, 176, .3)"; ctx.lineWidth = 1;
  const fx = field.x + field.w / 2, fy = field.y + field.h / 2;
  ctx.beginPath(); ctx.moveTo(fx - 6, fy); ctx.lineTo(fx + 6, fy); ctx.moveTo(fx, fy - 6); ctx.lineTo(fx, fy + 6); ctx.stroke();
  // notation and page number
  ctx.font = `${Math.max(11, Math.round(W * 0.012))}px ${MONO}`; ctx.fillStyle = "rgba(52, 97, 176, .75)"; ctx.textBaseline = "alphabetic";
  ctx.fillText(`SC ${String(scene).padStart(2, "0")} · ${String(local + 1).padStart(2, "0")}/${pages}`, 18, H - 14);
  ctx.textAlign = "right"; ctx.fillStyle = LEAD; ctx.font = `700 ${Math.max(18, Math.round(W * 0.022))}px ${HAND}`;
  ctx.fillText(String(page + 1), W - 18, H - 12);
  ctx.textAlign = "left";
  void total;
}

/** The drawing on local page f of a run. */
export function drawField(ctx: CanvasRenderingContext2D, run: Run, f: number, R: Rect, seed: number) {
  ctx.save();
  ctx.beginPath(); ctx.rect(R.x, R.y, R.w, R.h); ctx.clip();
  const s = seed * 1000 + f * 17;
  switch (run.type) {
    case "hero": run.art ? artFrame(ctx, run.art, f, R, s) : run.img?.naturalWidth ? photo(ctx, run.img, f, run.pages, R, s) : bounce(ctx, f, run.pages, R, s, false); break;
    case "intro": plane(ctx, f, run.pages, R, s); break;
    case "features": shapes(ctx, run, f, R, s); break;
    case "product": run.device ? phone(ctx, run.device, f, run.pages, R, s) : run.img?.naturalWidth ? photo(ctx, run.img, f, run.pages, R, s) : phone(ctx, null, f, run.pages, R, s); break;
    case "stats": stats(ctx, run, f, R, s); break;
    case "timeline": walker(ctx, run, f, R, s); break;
    case "quote": talker(ctx, f, run.pages, R, s); break;
    case "faq": asks(ctx, run, f, R, s); break;
    case "cta": theEnd(ctx, f, run.pages, R, s, run.word || "The End"); break;
    default: bounce(ctx, f, run.pages, R, s, false);
  }
  ctx.restore();
}

// ---------------------------------------------------------------- hero: the bouncing ball (or the theme artwork)
function ballAt(t: number, R: Rect) {
  const x = R.x + R.w * (0.1 + 0.8 * t);
  const u = t * 3.4, k = Math.floor(u), ph = u - k;
  const H0 = R.h * 0.62 * Math.pow(0.58, k);
  const y = R.y + R.h * 0.84 - 4 * ph * (1 - ph) * H0;
  return { x, y, ph, k, H0 };
}
function bounce(ctx: CanvasRenderingContext2D, f: number, P: number, R: Rect, s: number, rest: boolean) {
  const g = R.y + R.h * 0.84, rad = Math.min(R.w, R.h) * 0.07;
  seg(ctx, R.x + R.w * 0.04, g + rad, R.x + R.w * 0.96, g + rad, s + 1, LEAD, 1.6);
  // the animator's path, in blue
  const path: [number, number][] = [];
  for (let i = 0; i <= 80; i++) { const b = ballAt(i / 80, R); path.push([b.x, b.y]); }
  ctx.save(); ctx.setLineDash([3, 6]); pencil(ctx, path, 5, BLUE, 1.2, 0.3, 1); ctx.restore();
  const t = rest ? 1 : clamp(f / Math.max(1, P * 0.72));
  const b = ballAt(t, R);
  const contact = b.ph < 0.07 || b.ph > 0.93;
  const fast = Math.abs(0.5 - b.ph) > 0.32 && !contact;
  const sx = contact && b.H0 > R.h * 0.05 ? 1.3 : fast ? 0.86 : 1, sy = contact && b.H0 > R.h * 0.05 ? 0.72 : fast ? 1.16 : 1;
  ctx.save(); ctx.translate(b.x, b.y + rad - rad * sy); ctx.scale(sx, sy);
  ctx.beginPath(); ctx.arc(0, 0, rad, 0, TAU); ctx.save(); ctx.clip(); hatch(ctx, -rad, -rad, rad * 2, rad * 2, s, RED, 4, 0.75); ctx.restore();
  ring(ctx, 0, 0, rad, rad, s + 2, LEAD, 2.2);
  ctx.restore();
  ctx.fillStyle = "rgba(47, 47, 51, .18)";
  ctx.beginPath(); ctx.ellipse(b.x, g + rad + 2, rad * (1.1 - 0.5 * (g - b.y) / R.h), rad * 0.18, 0, 0, TAU); ctx.fill();
  if (contact && b.H0 > R.h * 0.05) for (const d of [-1, 1]) seg(ctx, b.x + d * rad * 1.4, g + rad - 2, b.x + d * rad * 2.1, g + rad * 0.3, s + d, LEAD, 1.4);
}

const artCache = new WeakMap<ArtFrames, HTMLCanvasElement[]>();
function artFrame(ctx: CanvasRenderingContext2D, a: ArtFrames, f: number, R: Rect, s: number) {
  const i = (f * 2) % a.n;
  let list = artCache.get(a); if (!list) { list = []; artCache.set(a, list); }
  if (!list[i]) {
    const c = document.createElement("canvas"); c.width = a.w; c.height = a.h;
    const x = c.getContext("2d")!; const im = x.createImageData(a.w, a.h); const m = a.mask[i];
    const r = rng(i + 3);
    for (let p = 0; p < m.length; p++) {
      // fade towards the edges so the drawing never reads as a cut-out rectangle
      const px = (p % a.w) / a.w - 0.5, py = Math.floor(p / a.w) / a.h - 0.5;
      const vig = clamp(1.25 - Math.hypot(px * 1.1, py) * 2.3);
      const v = clamp((m[p] - 0.2) / 0.6) * vig;
      const grain = 0.75 + r() * 0.5;
      im.data[p * 4] = 47; im.data[p * 4 + 1] = 47; im.data[p * 4 + 2] = 51; im.data[p * 4 + 3] = Math.round(clamp(Math.pow(v, 1.15) * grain) * 235);
    }
    x.putImageData(im, 0, 0); list[i] = c;
  }
  const sc = Math.min(R.w / a.w, R.h / a.h) * 0.96;
  const dw = a.w * sc, dh = a.h * sc;
  const jx = (rng(s)() - 0.5) * 1.5;
  ctx.drawImage(list[i], R.x + (R.w - dw) / 2 + jx, R.y + (R.h - dh) / 2, dw, dh);
}

/** A photograph printed in graphite on the page, the camera easing in a little page by page (a photo flipbook). */
function photo(ctx: CanvasRenderingContext2D, img: HTMLImageElement, f: number, P: number, R: Rect, s: number) {
  const t = clamp(f / Math.max(1, P - 1));
  const r = rng(s);
  const sc = Math.max(R.w / img.naturalWidth, R.h / img.naturalHeight) * (1.02 + 0.08 * ease(t));
  const dw = img.naturalWidth * sc, dh = img.naturalHeight * sc;
  ctx.save();
  ctx.globalCompositeOperation = "multiply";
  try { ctx.filter = "grayscale(1) contrast(1.25) brightness(1.08)"; } catch { /* colour then */ }
  ctx.drawImage(img, R.x + (R.w - dw) / 2 + (r() - 0.5) * 2, R.y + (R.h - dh) / 2 + (r() - 0.5) * 2, dw, dh);
  ctx.restore();
  // fade into the paper at the edges, so it reads as printed on the sheet
  const g = ctx.createRadialGradient(R.x + R.w / 2, R.y + R.h / 2, Math.min(R.w, R.h) * 0.3, R.x + R.w / 2, R.y + R.h / 2, Math.max(R.w, R.h) * 0.62);
  g.addColorStop(0, "rgba(247, 243, 234, 0)"); g.addColorStop(1, "rgba(247, 243, 234, .96)");
  ctx.fillStyle = g; ctx.fillRect(R.x, R.y, R.w, R.h);
  ctx.fillStyle = "rgba(247, 243, 234, .18)";
  for (let i = 0; i < 260; i++) ctx.fillRect(R.x + r() * R.w, R.y + r() * R.h, 1 + r() * 2, 1);
}

// ---------------------------------------------------------------- intro: a paper plane loops the loop
function planeAt(t: number, R: Rect) {
  const L = ease(clamp((t - 0.3) / 0.42));
  const rad = Math.min(R.h * 0.26, R.w * 0.16);
  const x = R.x + R.w * (0.08 + 0.84 * t) + rad * Math.sin(TAU * L) - R.w * 0.12 * L * 0;
  const y = R.y + R.h * 0.66 - R.h * 0.14 * Math.sin(Math.PI * t) - rad * (1 - Math.cos(TAU * L));
  return [x, y] as [number, number];
}
function plane(ctx: CanvasRenderingContext2D, f: number, P: number, R: Rect, s: number) {
  const path: [number, number][] = [];
  for (let i = 0; i <= 120; i++) path.push(planeAt(i / 120, R));
  ctx.save(); ctx.setLineDash([3, 6]); pencil(ctx, path, 4, BLUE, 1.2, 0.3, 1); ctx.restore();
  const t = clamp(f / Math.max(1, P - 3));
  const [x, y] = planeAt(t, R), [x2, y2] = planeAt(Math.min(1, t + 0.01), R);
  const a = Math.atan2(y2 - y, x2 - x);
  // speed lines behind it
  for (let i = 1; i <= 3; i++) { const [px, py] = planeAt(Math.max(0, t - i * 0.025), R); seg(ctx, px, py + (i - 2) * 5, px - 14, py + (i - 2) * 5, s + i, LEAD, 1); }
  const L = Math.min(R.w, R.h) * 0.17;
  ctx.save(); ctx.translate(x, y); ctx.rotate(a);
  const top: [number, number][] = [[L * 0.6, 0], [-L * 0.5, -L * 0.36], [-L * 0.32, 0], [L * 0.6, 0]];
  const bot: [number, number][] = [[L * 0.6, 0], [-L * 0.5, L * 0.18], [-L * 0.32, 0]];
  ctx.beginPath(); ctx.moveTo(top[0][0], top[0][1]); top.forEach(([px, py]) => ctx.lineTo(px, py)); ctx.closePath();
  ctx.save(); ctx.clip(); hatch(ctx, -L, -L, L * 2, L * 2, s, LEAD, 5, 0.25); ctx.restore();
  pencil(ctx, top, s + 1, LEAD, 2); pencil(ctx, bot, s + 2, LEAD, 1.8);
  seg(ctx, -L * 0.32, 0, L * 0.6, 0, s + 3, RED, 1.4);
  ctx.restore();
}

// ---------------------------------------------------------------- features: one shape morphing into the next
const SHAPES: ((a: number) => [number, number])[] = [
  (a) => [Math.cos(a), Math.sin(a)],                                                   // circle
  (a) => { const c = Math.cos(a), s = Math.sin(a), m = Math.max(Math.abs(c), Math.abs(s)); return [c / m * 0.86, s / m * 0.86]; }, // square
  (a) => polyPt(a, 3, -Math.PI / 2),
  (a) => { const k = 5, b = (a + Math.PI / 2) % (TAU / k); const r = 0.55 + 0.45 * Math.abs(Math.cos((b / (TAU / k)) * Math.PI)); return [Math.cos(a) * r, Math.sin(a) * r]; }, // star-ish
  (a) => polyPt(a, 6, 0),
  (a) => polyPt(a, 4, -Math.PI / 2),                                                   // diamond
];
function polyPt(a: number, n: number, rot: number): [number, number] {
  const sec = TAU / n, b = ((a - rot) % sec + sec) % sec;
  const r = Math.cos(sec / 2) / Math.cos(b - sec / 2);
  return [Math.cos(a) * r, Math.sin(a) * r];
}
function shapePts(i: number, cx: number, cy: number, r: number, k: number): [number, number][] {
  const out: [number, number][] = [];
  const A = SHAPES[i % SHAPES.length], B = SHAPES[(i + 1) % SHAPES.length];
  for (let j = 0; j < 72; j++) {
    const a = (j / 72) * TAU - Math.PI / 2;
    const p = A(a), q = B(a);
    out.push([cx + (p[0] + (q[0] - p[0]) * k) * r, cy + (p[1] + (q[1] - p[1]) * k) * r]);
  }
  return out;
}
function shapes(ctx: CanvasRenderingContext2D, run: Run, f: number, R: Rect, s: number) {
  const cx = R.x + R.w / 2, cy = R.y + R.h * 0.5, r = Math.min(R.w, R.h) * 0.34;
  let idx = -1, k = 0;
  run.items.forEach((it, i) => { if (f >= it.start) { idx = i; k = f - it.start; } });
  if (idx < 0) {
    // the lead: a dot that swells into the first shape
    const g = ease(f / Math.max(1, run.lead));
    ring(ctx, cx, cy, r * g * 0.9 + 2, r * g * 0.9 + 2, s, LEAD, 2, clamp(g * 1.2));
    return;
  }
  const m = idx === 0 ? 1 : ease(k / 4);
  const pts = idx === 0 ? shapePts(0, cx, cy, r * (0.9 + 0.1 * ease(k / 3)), 0) : shapePts(idx - 1, cx, cy, r, m);
  ctx.save(); ctx.beginPath(); pts.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.clip();
  hatch(ctx, R.x, R.y, R.w, R.h, s, idx % 2 ? BLUE : RED, 7, clamp((k - 2) / 4) * 0.55);
  ctx.restore();
  pencil(ctx, pts, s + 1, LEAD, 2.4, 1.2, 2, true);
  // the in-betweens' ghosts: the last two drawings, faint (an animator's onion skin)
  if (idx > 0 && k < 5) pencil(ctx, shapePts(idx - 1, cx, cy, r, Math.max(0, m - 0.3)), s + 4, "rgba(52, 97, 176, .45)", 1.2, 1, 1, true);
  const tag = run.tags?.[idx] || String(idx + 1).padStart(2, "0");
  hand(ctx, tag, cx, cy + r * 0.2, r * 0.62, LEAD);
}

// ---------------------------------------------------------------- product: the phone sketched in, then tapped
function rrPath(x: number, y: number, w: number, h: number, r: number, n = 12): [number, number][] {
  const pts: [number, number][] = [];
  const corners: [number, number, number][] = [[x + w - r, y + r, -Math.PI / 2], [x + w - r, y + h - r, 0], [x + r, y + h - r, Math.PI / 2], [x + r, y + r, Math.PI]];
  for (const [cx, cy, a0] of corners) for (let i = 0; i <= n; i++) { const a = a0 + (i / n) * (Math.PI / 2); pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); }
  pts.push(pts[0]);
  return pts;
}
function part(pts: [number, number][], k: number) { return pts.slice(0, Math.max(2, Math.round(pts.length * clamp(k)))); }
function phone(ctx: CanvasRenderingContext2D, d: Device | null, f: number, P: number, R: Rect, s: number) {
  const t = clamp(f / Math.max(1, P - 4));
  const ph = R.h * 0.9, pw = Math.min(ph * 0.5, R.w * 0.7);
  const x = R.x + (R.w - pw) / 2, y = R.y + (R.h - ph) / 2;
  // construction in blue
  const c = clamp(t / 0.25);
  seg(ctx, x + pw / 2, y - 8, x + pw / 2, y - 8 + (ph + 16) * c, s + 1, BLUE, 1);
  seg(ctx, x - 10, y + ph / 2, x - 10 + (pw + 20) * c, y + ph / 2, s + 2, BLUE, 1);
  if (c > 0.3) ring(ctx, x + pw / 2, y + ph / 2, pw * 0.62, ph * 0.56, s + 3, "rgba(52, 97, 176, .55)", 1, clamp((c - 0.3) / 0.7));
  // outline in graphite
  const o = clamp((t - 0.18) / 0.3);
  if (o > 0) {
    pencil(ctx, part(rrPath(x, y, pw, ph, pw * 0.14), o), s + 4, LEAD, 2.6);
    if (o > 0.7) pencil(ctx, part(rrPath(x + pw * 0.06, y + pw * 0.06, pw * 0.88, ph - pw * 0.12, pw * 0.09), (o - 0.7) / 0.3), s + 5, LEAD, 1.4);
  }
  // screen contents
  const sc = clamp((t - 0.45) / 0.3);
  const ix = x + pw * 0.14, iw = pw * 0.72;
  if (sc > 0) {
    if (d?.app) hand(ctx, d.app, ix, y + ph * 0.13, pw * 0.1, BLUE, "left", 600);
    if (sc > 0.15 && d?.title) {
      const words = d.title.split(" "); const l1 = words.slice(0, 2).join(" "), l2 = words.slice(2).join(" ");
      hand(ctx, l1, ix, y + ph * 0.23, pw * 0.13, LEAD, "left");
      if (l2) hand(ctx, l2, ix, y + ph * 0.31, pw * 0.13, LEAD, "left");
    }
    const opts = (d?.options?.length ? d.options : ["", "", ""]).slice(0, 3);
    opts.forEach((txt, i) => {
      const k = clamp((sc - 0.3 - i * 0.18) / 0.2);
      if (k <= 0) return;
      const oy = y + ph * (0.4 + i * 0.13), oh = ph * 0.1;
      pencil(ctx, part(rrPath(ix, oy, iw, oh, 6, 4), k), s + 10 + i, LEAD, 1.6);
      if (k > 0.8) hand(ctx, txt.slice(0, 16), ix + 10, oy + oh * 0.68, pw * 0.085, LEAD, "left", 600);
    });
    if (sc > 0.9) { pencil(ctx, rrPath(ix, y + ph * 0.83, iw, ph * 0.075, ph * 0.035, 4), s + 20, LEAD, 1.6); hand(ctx, (d?.button || "").slice(0, 18), ix + iw / 2, y + ph * 0.88, pw * 0.08, LEAD, "center", 600); }
  }
  // the tap
  const tp = clamp((t - 0.78) / 0.22);
  if (tp > 0) {
    const opts = d?.options || [];
    const si = Math.max(0, opts.indexOf(d?.selected || ""));
    const oy = y + ph * (0.4 + si * 0.13), oh = ph * 0.1;
    if (tp > 0.5) {
      ctx.save(); ctx.beginPath(); ctx.rect(ix, oy, iw, oh); ctx.clip(); hatch(ctx, ix, oy, iw, oh, s + 30, RED, 4, 0.55); ctx.restore();
      for (let i = 1; i <= 2; i++) ring(ctx, ix + iw * 0.78, oy + oh / 2, 8 + i * 9 * tp, 6 + i * 6 * tp, s + 40 + i, RED, 1.4);
    }
    // finger coming in from the lower right
    const fx = ix + iw * 0.78 + (1 - ease(tp * 1.6)) * pw * 0.7, fy = oy + oh * 0.6 + (1 - ease(tp * 1.6)) * ph * 0.4;
    const fw = pw * 0.17;
    pencil(ctx, [[fx + fw * 0.5, fy + ph], [fx + fw * 0.5, fy + fw * 0.5], [fx + fw * 0.35, fy + fw * 0.1], [fx, fy], [fx - fw * 0.35, fy + fw * 0.1], [fx - fw * 0.5, fy + fw * 0.5], [fx - fw * 0.5, fy + ph]], s + 50, LEAD, 2.2);
    pencil(ctx, [[fx - fw * 0.25, fy + fw * 0.35], [fx, fy + fw * 0.2], [fx + fw * 0.25, fy + fw * 0.35]], s + 51, LEAD, 1.2);
  }
}

// ---------------------------------------------------------------- stats: counted on paper
function parseNum(v: string) { const n = parseFloat(v.replace(/[^0-9.\-]/g, "")); return isFinite(n) ? n : NaN; }
function stats(ctx: CanvasRenderingContext2D, run: Run, f: number, R: Rect, s: number) {
  let idx = -1, k = 0, len = 1;
  run.items.forEach((it, i) => { if (f >= it.start) { idx = i; k = f - it.start; len = it.end - it.start; } });
  if (idx < 0) { hand(ctx, "let's count…", R.x + R.w / 2, R.y + R.h * 0.55, R.h * 0.14, BLUE, "center", 600); return; }
  const st = run.stats?.[idx] || { value: "", unit: "" };
  const n = parseNum(st.value);
  const p = clamp(k / Math.max(1, len - 3));
  const cx = R.x + R.w * 0.38, cy = R.y + R.h * 0.5;
  let shown = st.value;
  if (/%/.test(st.unit) && n >= 0 && n <= 100) {
    const rad = Math.min(R.w * 0.3, R.h * 0.4);
    const a1 = -Math.PI / 2 + TAU * (n / 100) * p;
    ctx.save(); ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, rad, -Math.PI / 2, a1); ctx.closePath(); ctx.clip();
    hatch(ctx, cx - rad, cy - rad, rad * 2, rad * 2, s, RED, 5, 0.7); ctx.restore();
    ring(ctx, cx, cy, rad, rad, s + 1, LEAD, 2.2);
    seg(ctx, cx, cy, cx, cy - rad, s + 2, LEAD, 1.6);
    seg(ctx, cx, cy, cx + Math.cos(a1) * rad, cy + Math.sin(a1) * rad, s + 3, LEAD, 1.6);
    shown = String(Math.round(n * p));
  } else if (Number.isInteger(n) && n >= 1 && n <= 30) {
    const count = Math.min(n, Math.round(n * p));
    const rows = Math.ceil(n / 5 / Math.max(1, Math.floor((R.w * 0.46) / (Math.min(R.w * 0.04, 16) * 5.2)))); const mh = R.h * (rows > 1 ? 0.22 : 0.3), gap = Math.min(R.w * 0.04, 16), groupW = gap * 5.2;
    const perRow = Math.max(1, Math.floor((R.w * 0.46) / groupW));
    for (let i = 0; i < count; i++) {
      const g = Math.floor(i / 5), j = i % 5, row = Math.floor(g / perRow), col = g % perRow;
      const gx = R.x + R.w * 0.08 + col * groupW, gy = R.y + R.h * (rows > 1 ? 0.18 : 0.3) + row * (mh + 16);
      if (j < 4) seg(ctx, gx + j * gap, gy, gx + j * gap + 2, gy + mh, s + i, LEAD, 2.2);
      else seg(ctx, gx - gap * 0.4, gy + mh * 0.8, gx + gap * 3.6, gy + mh * 0.15, s + i, RED, 2.2);
    }
    shown = String(count);
  } else if (n === 0) {
    ring(ctx, cx, cy, R.h * 0.24, R.h * 0.3, s, LEAD, 2.6, clamp(p * 1.3));
    if (p > 0.8) hand(ctx, "none!", cx + R.h * 0.35, cy - R.h * 0.22, R.h * 0.12, RED, "left");
    shown = "0";
  } else {
    const bw = R.w * 0.42 * p, by = cy - R.h * 0.08;
    ctx.save(); ctx.beginPath(); ctx.rect(R.x + R.w * 0.06, by, bw, R.h * 0.16); ctx.clip(); hatch(ctx, R.x, by, R.w, R.h * 0.16, s, RED, 4, 0.7); ctx.restore();
    pencil(ctx, [[R.x + R.w * 0.06, by], [R.x + R.w * 0.06 + bw, by], [R.x + R.w * 0.06 + bw, by + R.h * 0.16], [R.x + R.w * 0.06, by + R.h * 0.16]], s + 1, LEAD, 2, 1.1, 2, true);
    if (isFinite(n)) shown = String(Math.round(n * p)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
  const unit = p >= 1 && st.unit ? (/^[a-z]/i.test(st.unit) ? " " : "") + st.unit : "";
  hand(ctx, `${shown}${unit}`, R.x + R.w * 0.94, R.y + R.h * 0.62, Math.min(R.h * 0.3, R.w * 0.16), LEAD, "right");
  if (p >= 1) seg(ctx, R.x + R.w * 0.56, R.y + R.h * 0.68, R.x + R.w * 0.9, R.y + R.h * 0.66, s + 70, RED, 2);
}

// ---------------------------------------------------------------- timeline: a walk past the milestones
function stick(ctx: CanvasRenderingContext2D, x: number, g: number, h: number, phase: number, s: number, walking: boolean) {
  const leg = h * 0.25, bob = walking ? Math.abs(Math.sin(phase)) * h * 0.02 : 0;
  const hip = g - leg * 1.9 + bob, neck = hip - h * 0.3;
  const sw = walking ? Math.sin(phase) * 0.55 : 0;
  for (const side of [1, -1]) {
    const a = sw * side;
    const knee: [number, number] = [x + Math.sin(a) * leg, hip + Math.cos(a) * leg];
    const bend = walking ? Math.max(0, Math.cos(phase) * side) * 0.6 : 0;
    const foot: [number, number] = [knee[0] + Math.sin(a - bend) * leg, knee[1] + Math.cos(a - bend) * leg];
    pencil(ctx, [[x, hip], knee, foot, [foot[0] + 7, foot[1]]], s + side, side > 0 ? LEAD : "rgba(47,47,51,.55)", 2.4);
    const arm = -a * 0.8;
    pencil(ctx, [[x, neck + 6], [x + Math.sin(arm) * leg * 0.8, neck + 6 + Math.cos(arm) * leg * 0.8], [x + Math.sin(arm + 0.3) * leg * 1.5, neck + 6 + Math.cos(arm + 0.3) * leg * 1.5]], s + 4 + side, side > 0 ? LEAD : "rgba(47,47,51,.55)", 2);
  }
  pencil(ctx, [[x, hip], [x + 2, neck]], s + 7, LEAD, 2.6);
  ring(ctx, x + 3, neck - h * 0.09, h * 0.08, h * 0.09, s + 8, LEAD, 2.2);
}
function walker(ctx: CanvasRenderingContext2D, run: Run, f: number, R: Rect, s: number) {
  const n = Math.max(1, run.items.length);
  const g = R.y + R.h * 0.8;
  seg(ctx, R.x + 8, g, R.x + R.w - 8, g, s + 1, LEAD, 1.8);
  const px = (i: number) => R.x + R.w * (n === 1 ? 0.7 : 0.16 + 0.74 * (i / (n - 1)));
  let idx = -1, k = 0, len = 1;
  run.items.forEach((it, i) => { if (f >= it.start) { idx = i; k = f - it.start; len = it.end - it.start; } });
  const from = idx <= 0 ? R.x + R.w * 0.04 : px(idx - 1), to = idx < 0 ? R.x + R.w * 0.04 : px(idx);
  const walkK = idx < 0 ? 0 : clamp(k / Math.max(1, len - 3));
  const wx = from + (to - from) * walkK;
  for (let i = 0; i < n; i++) {
    const x = px(i), reached = i < idx || (i === idx && walkK >= 1);
    seg(ctx, x, g, x, g - R.h * 0.42, s + 20 + i, LEAD, 2);
    if (reached) pencil(ctx, [[x, g - R.h * 0.42], [x + R.h * 0.14, g - R.h * 0.37], [x, g - R.h * 0.32]], s + 30 + i, RED, 2, 1, 2);
    else pencil(ctx, [[x, g - R.h * 0.42], [x + R.h * 0.12, g - R.h * 0.38], [x, g - R.h * 0.34]], s + 30 + i, "rgba(52,97,176,.6)", 1.2, 1, 1);
    const w = run.whens?.[i] || "";
    hand(ctx, w.slice(0, 12), x, g + R.h * 0.13, Math.min(R.h * 0.1, 26), reached ? LEAD : BLUE, "center", 600);
  }
  stick(ctx, wx, g, R.h * 0.5, f * 1.6, s + 50, walkK > 0 && walkK < 1);
}

// ---------------------------------------------------------------- quote: a profile, speaking
function talker(ctx: CanvasRenderingContext2D, f: number, P: number, R: Rect, s: number) {
  const S = Math.min(R.h * 0.72, R.w * 0.5), ox = R.x + R.w * 0.08, oy = R.y + R.h * 0.18;
  const open = f % 2 === 0 && f < P - 3;
  const P0: [number, number][] = [[0.3, 0.05], [0.55, 0], [0.74, 0.08], [0.8, 0.25], [0.785, 0.31], [0.9, 0.46], [0.8, 0.49], [0.815, 0.55], [open ? 0.75 : 0.78, 0.58], [0.8, open ? 0.65 : 0.62], [0.765, open ? 0.72 : 0.69], [0.78, 0.78], [0.66, 0.85], [0.62, 1.05]];
  pencil(ctx, P0.map(([a, b]) => [ox + a * S, oy + b * S] as [number, number]), s, LEAD, 2.4);
  pencil(ctx, [[0.3, 0.05], [0.14, 0.2], [0.12, 0.45], [0.24, 0.7], [0.3, 0.8], [0.28, 1.05]].map(([a, b]) => [ox + a * S, oy + b * S] as [number, number]), s + 1, LEAD, 2.2);
  ring(ctx, ox + 0.66 * S, oy + 0.3 * S, S * 0.02, S * 0.02, s + 2, LEAD, 2);
  const g = ease(f / Math.max(1, P * 0.5));
  const bx = R.x + R.w * 0.72, by = R.y + R.h * 0.34, rx = R.w * 0.26 * (0.3 + 0.7 * g), ry = R.h * 0.22 * (0.3 + 0.7 * g);
  ring(ctx, bx, by, rx, ry, s + 3, LEAD, 2);
  pencil(ctx, [[bx - rx * 0.6, by + ry * 0.75], [ox + 0.95 * S, oy + 0.56 * S], [bx - rx * 0.25, by + ry * 0.95]], s + 4, LEAD, 2);
  const lines = Math.min(3, Math.floor(f / 3));
  for (let i = 0; i < lines; i++) seg(ctx, bx - rx * 0.6, by - ry * 0.35 + i * ry * 0.35, bx + rx * (0.55 - i * 0.12), by - ry * 0.35 + i * ry * 0.35, s + 10 + i, BLUE, 1.6);
}

// ---------------------------------------------------------------- faq: a question mark that becomes an answer
function asks(ctx: CanvasRenderingContext2D, run: Run, f: number, R: Rect, s: number) {
  let idx = -1, k = 0, len = 1;
  run.items.forEach((it, i) => { if (f >= it.start) { idx = i; k = f - it.start; len = it.end - it.start; } });
  const cx = R.x + R.w / 2, g = R.y + R.h * 0.86;
  seg(ctx, R.x + R.w * 0.2, g, R.x + R.w * 0.8, g, s, LEAD, 1.6);
  const answered = idx >= 0 && k >= Math.ceil(len * 0.45);
  const hop = answered ? 0 : Math.abs(Math.sin(f * 1.1)) * R.h * 0.12;
  const size = R.h * 0.7;
  ctx.save(); ctx.translate(cx, g - 6 - hop);
  if (!answered) ctx.rotate(Math.sin(f * 1.3) * 0.12);
  hand(ctx, answered ? "!" : "?", 0, 0, size, answered ? RED : LEAD);
  ctx.restore();
  if (answered) for (let i = 0; i < 6; i++) { const a = -Math.PI / 2 + (i - 2.5) * 0.42; seg(ctx, cx + Math.cos(a) * size * 0.42, g - size * 0.45 + Math.sin(a) * size * 0.42, cx + Math.cos(a) * size * 0.56, g - size * 0.45 + Math.sin(a) * size * 0.56, s + i, RED, 1.8); }
  if (idx >= 0) hand(ctx, `Q${idx + 1}`, R.x + R.w * 0.08, R.y + R.h * 0.18, R.h * 0.12, BLUE, "left", 600);
}

// ---------------------------------------------------------------- cta: the ball comes home, "The End"
function theEnd(ctx: CanvasRenderingContext2D, f: number, P: number, R: Rect, s: number, word: string) {
  const t = clamp(f / Math.max(1, P - 5));
  const txt = "The End";
  const n = Math.round(txt.length * clamp((t - 0.35) / 0.45));
  hand(ctx, txt.slice(0, n), R.x + R.w / 2, R.y + R.h * 0.42, Math.min(R.h * 0.3, R.w * 0.2), LEAD);
  if (t > 0.85) seg(ctx, R.x + R.w * 0.24, R.y + R.h * 0.5, R.x + R.w * 0.76, R.y + R.h * 0.48, s + 1, RED, 2.4);
  const sub: Rect = { x: R.x, y: R.y + R.h * 0.5, w: R.w, h: R.h * 0.48 };
  bounce(ctx, f, Math.max(4, Math.round(P * 0.9)), sub, s + 5, false);
  void word;
}
