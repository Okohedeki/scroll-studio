/**
 * Drawings for scratch-film: what a person would put on a strip of film with a needle, a brush and a comb. Every drawing
 * is a pure function of (frame number, tone), so scrolling back plays the same drawings backwards and the strip beside
 * the screen shows exactly what the gate will project. A tone is a stock:
 *   leader   black leader scratched to the lamp (Len Lye's Free Radicals): thin white needle work, dots, specks
 *   dye      clear leader dyed and stencilled (A Colour Box, Begone Dull Care): fields, bars, circles, combs; on twos
 *   pressed  matter pressed between tape (Mothlight): petals, wings and grass laid on amber; on twos
 * Each phrase (3 beats of 12 frames) has its own motifs which move coherently through it, and every frame is a new hand on top
 * of that, so the line boils the way direct animation does: nothing is registered from frame to frame.
 * Photosensitivity: marks are thin or small; the dye grounds sit within a luminance band of 0.04 of one another, dye and
 * pressed frames change at most 12 times a second, and nothing is red.
 */
import { skin, skinRgba } from "./_kit";

export type Tone = "leader" | "dye" | "pressed";
export const TONES: Tone[] = ["leader", "dye", "pressed"];
export const FPB = 12;            // frames per beat (120 beats a minute at 24 frames a second)
export const PHRASE = FPB * 3;

export function hash(a: number, b = 0, c = 0): number {   // 0 .. 1
  let x = Math.imul(a ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul((b | 0) + 0x7f4a7c15, 0xc2b2ae35) ^ Math.imul((c | 0) + 0x165667b1, 0x27d4eb2f);
  x ^= x >>> 15; x = Math.imul(x, 0x2c1b3c6d); x ^= x >>> 12; x = Math.imul(x, 0x297a2d39); x ^= x >>> 15;
  return (x >>> 0) / 4294967296;
}
function rngFrom(seed: number) {
  let s = (seed >>> 0) || 1;
  return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const toneId = (t: Tone) => (t === "leader" ? 1 : t === "dye" ? 2 : 3);

/** The projector lamp: the style's ink, so a brand's. The dyes below are film stock (with their own luminance and no-red rules) and stay. */
export const LAMP = skin("ink", "#fff6df");
export const lamp = (a: number | string) => skinRgba("ink", "#fff6df", a);
/** Dye grounds (deep, dense dye) share one luminance band; marks are the bright dyes. Nothing red. */
export const GROUNDS = ["#5a0f3c", "#0b4a5c", "#5a4308", "#0d4a2c", "#3a1a66"];
export const MARKS = ["#12b8d8", "#e0338f", "#f2c814", "#f08a1c", "#2ab56a"];
export const FLASH = ["#0e7f98", "#a82468", "#9c7f0c"];   // splice flash leaders: middling, never white, never red

type Ctx = CanvasRenderingContext2D;
type R = () => number;

function poly(ctx: Ctx, pts: number[], close = false) {
  ctx.beginPath(); ctx.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
  if (close) ctx.closePath();
}
/** A line drawn with an uneven hand: a few kinks along it. */
function needle(ctx: Ctx, x0: number, y0: number, x1: number, y1: number, r: R, wob: number) {
  const n = 3, pts = [x0, y0];
  for (let i = 1; i < n; i++) { const q = i / n; pts.push(x0 + (x1 - x0) * q + (r() - 0.5) * wob, y0 + (y1 - y0) * q + (r() - 0.5) * wob); }
  pts.push(x1, y1);
  poly(ctx, pts); ctx.stroke();
}

// ---------------------------------------------------------------- leader: white needle work on black
function burst(ctx: Ctx, w: number, h: number, s: number, t: number, r: R, ph: number) {
  const cx = w * (0.5 + 0.3 * Math.sin(t * 5.1 + ph)), cy = h * (0.5 + 0.28 * Math.cos(t * 3.7 + ph * 2));
  const n = 18 + Math.floor(hash(ph, 3) * 22);
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 + t * 1.6 + (r() - 0.5) * 0.12;
    const r0 = s * (0.03 + 0.06 * r()), r1 = s * (0.14 + 0.34 * r() * (0.55 + 0.45 * Math.sin(t * Math.PI)));
    needle(ctx, cx + Math.cos(a) * r0, cy + Math.sin(a) * r0, cx + Math.cos(a) * r1, cy + Math.sin(a) * r1, r, s * 0.012);
  }
}
function spiral(ctx: Ctx, w: number, h: number, s: number, t: number, r: R, ph: number) {
  const arms = 2 + Math.floor(hash(ph, 5) * 2);
  const cx = w * (0.28 + 0.44 * hash(ph, 6)), cy = h * (0.3 + 0.4 * hash(ph, 7));
  for (let a = 0; a < arms; a++) {
    const pts: number[] = [];
    for (let k = 0; k < 64; k++) {
      const ang = k * 0.21 + t * 5 + (a * Math.PI * 2) / arms, rad = k * s * 0.0105 * (0.82 + 0.18 * Math.sin(t * 6.3 + k * 0.1));
      pts.push(cx + Math.cos(ang) * rad + (r() - 0.5) * s * 0.006, cy + Math.sin(ang) * rad + (r() - 0.5) * s * 0.006);
    }
    poly(ctx, pts); ctx.stroke();
  }
}
function dancer(ctx: Ctx, w: number, h: number, s: number, t: number, r: R, ph: number) {
  for (let d = 0; d < 2; d++) {
    let x = w * (0.2 + 0.6 * ((hash(ph, 8 + d) + t * (d ? -0.3 : 0.4) + 1) % 1)), y = h * (0.25 + 0.5 * hash(ph, 12 + d) + 0.08 * Math.sin(t * 9 + d));
    const pts = [x, y];
    for (let i = 0; i < 16; i++) { const a = r() * Math.PI * 2, l = s * (0.035 + 0.09 * r()); x += Math.cos(a) * l; y += Math.sin(a) * l; pts.push(x, y); }
    poly(ctx, pts); ctx.stroke();
    for (let i = 0; i < 12; i++) { ctx.beginPath(); ctx.arc(pts[0] + (r() - 0.5) * s * 0.5, pts[1] + (r() - 0.5) * s * 0.5, s * (0.003 + 0.006 * r()), 0, 7); ctx.fill(); }
  }
}
function comb(ctx: Ctx, w: number, h: number, s: number, t: number, r: R, ph: number) {
  const th = hash(ph, 20) * Math.PI, n = 26, c = Math.cos(th), sn = Math.sin(th);
  const off = (t + hash(ph, 21)) % 1;
  for (let i = 0; i < n; i++) {
    const q = (i / n + off * 0.3) % 1, px = w * 0.5 + (q - 0.5) * s * 1.6 * -sn, py = h * 0.5 + (q - 0.5) * s * 1.6 * c;
    const len = s * (0.12 + 0.55 * hash(ph + i, 22, Math.floor(t * 4)));
    const mid = (r() - 0.5) * s * 0.4;
    needle(ctx, px + c * (mid - len / 2), py + sn * (mid - len / 2), px + c * (mid + len / 2), py + sn * (mid + len / 2), r, s * 0.006);
  }
}
function dots(ctx: Ctx, w: number, h: number, s: number, t: number, r: R, ph: number) {
  const gx = 12 + Math.floor(hash(ph, 30) * 8), cell = w / gx, gy = Math.ceil(h / cell);
  for (let iy = 0; iy < gy; iy++) for (let ix = 0; ix < gx; ix++) {
    const on = hash(ix, iy, ph) * 0.5 + 0.5 * (0.5 + 0.5 * Math.sin(t * Math.PI * 4 + ix * 0.45 + iy * 0.31)) > 0.62;
    if (!on) continue;
    ctx.beginPath(); ctx.arc((ix + 0.5) * cell + (r() - 0.5) * cell * 0.3, (iy + 0.5) * cell + (r() - 0.5) * cell * 0.3, cell * (0.07 + 0.1 * r()), 0, 7); ctx.fill();
  }
}
function rings(ctx: Ctx, w: number, h: number, s: number, t: number, r: R, ph: number) {
  const cx = w * (0.3 + 0.4 * hash(ph, 40)), cy = h * (0.3 + 0.4 * hash(ph, 41));
  for (let k = 0; k < 5; k++) {
    const rad = s * ((t * 0.7 + k * 0.13) % 0.7), a0 = r() * 6.28, span = 1.4 + r() * 4.2;
    const pts: number[] = [];
    for (let i = 0; i <= 28; i++) { const a = a0 + (span * i) / 28; pts.push(cx + Math.cos(a) * rad + (r() - 0.5) * s * 0.006, cy + Math.sin(a) * rad + (r() - 0.5) * s * 0.006); }
    poly(ctx, pts); ctx.stroke();
  }
}
const LEADER_MOTIFS = [burst, spiral, dancer, comb, dots, rings];

function drawLeader(ctx: Ctx, w: number, h: number, frame: number, lw: number) {
  const s = Math.min(w, h) * 1.05;
  ctx.fillStyle = "#050505"; ctx.fillRect(0, 0, w, h);
  const ph = Math.floor(frame / PHRASE), t = (frame % PHRASE) / PHRASE;
  const r = rngFrom(hash(frame, 1, 1) * 4294967296);
  ctx.strokeStyle = LAMP; ctx.fillStyle = LAMP; ctx.lineCap = "round"; ctx.lineJoin = "round";
  // McLaren's rests: a frame in a few is nearly empty, which makes the marks around it blink
  const rest = hash(frame >> 1, 9, 2) < 0.1;
  if (!rest) {
    const m1 = LEADER_MOTIFS[Math.floor(hash(ph, 1, 1) * LEADER_MOTIFS.length)];
    const m2 = LEADER_MOTIFS[Math.floor(hash(ph, 2, 1) * LEADER_MOTIFS.length)];
    ctx.lineWidth = lw * 1.1; ctx.globalAlpha = 0.95; m1(ctx, w, h, s, t, r, ph);
    ctx.lineWidth = lw * 0.8; ctx.globalAlpha = 0.6; m2(ctx, w, h, s, (t + 0.5) % 1, r, ph + 99);
  }
  ctx.globalAlpha = 1; ctx.lineWidth = lw * 0.7;
  const specks = 10 + Math.floor(r() * 14);
  for (let i = 0; i < specks; i++) { ctx.globalAlpha = 0.25 + r() * 0.6; ctx.beginPath(); ctx.arc(r() * w, r() * h, lw * (0.4 + r() * 0.9), 0, 7); ctx.fill(); }
  ctx.globalAlpha = 1;
}

// ---------------------------------------------------------------- dye: colour fields on clear leader
function ragged(ctx: Ctx, x0: number, y0: number, x1: number, y1: number, r: R, bleed: number) {
  const pts: number[] = [];
  const edge = (ax: number, ay: number, bx: number, by: number) => { const n = 6; for (let i = 0; i < n; i++) { const q = i / n; pts.push(ax + (bx - ax) * q + (r() - 0.5) * bleed, ay + (by - ay) * q + (r() - 0.5) * bleed); } };
  edge(x0, y0, x1, y0); edge(x1, y0, x1, y1); edge(x1, y1, x0, y1); edge(x0, y1, x0, y0);
  poly(ctx, pts, true); ctx.fill();
}
function drawDye(ctx: Ctx, w: number, h: number, frame0: number, lw: number) {
  const frame = frame0 & ~1;                                   // dye changes on twos: 12 a second at most
  const ph = Math.floor(frame / PHRASE), t = (frame % PHRASE) / PHRASE;
  const r = rngFrom(hash(frame, 2, 2) * 4294967296);
  const s = Math.min(w, h);
  ctx.fillStyle = GROUNDS[Math.floor(hash(ph, 50) * GROUNDS.length)]; ctx.fillRect(0, 0, w, h);
  const hue = (i: number) => MARKS[(Math.floor(hash(ph, 51) * 5) + i) % 5];
  const kind = Math.floor(hash(ph, 52) * 4);
  // a band of stripes (Colour Box): their edges bleed
  const vertical = hash(ph, 53) < 0.5;
  const bx = vertical ? w * (0.1 + 0.3 * hash(ph, 54)) : 0, by = vertical ? 0 : h * (0.1 + 0.3 * hash(ph, 54));
  const bw = vertical ? w * (0.3 + 0.2 * hash(ph, 55)) : w, bh = vertical ? h : h * (0.3 + 0.2 * hash(ph, 55));
  const n = 7 + Math.floor(hash(ph, 56) * 6), off = (t * 2 + hash(ph, 57)) % 1;
  for (let i = 0; i < n; i++) {
    ctx.fillStyle = hue(i % 3);
    const q0 = (i + off) / (n + 1), q1 = q0 + 0.5 / (n + 1);
    if (vertical) ragged(ctx, bx + bw * q0, by, bx + bw * q1, by + bh, r, lw * 3); else ragged(ctx, bx, by + bh * q0, bx + bw, by + bh * q1, r, lw * 3);
  }
  // circles left by dust on wet dye (Begone Dull Care): a ring of lighter dye with a darker rim
  if (kind === 0 || kind === 2) {
    const cx = w * (0.5 + 0.35 * Math.sin(t * 6 + ph)), cy = h * (0.5 + 0.3 * Math.cos(t * 4 + ph));
    for (let k = 0; k < 9; k++) {
      const a = r() * 6.28, d = s * (0.1 + 0.4 * r()), rad = s * (0.025 + 0.07 * r());
      ctx.fillStyle = hue(k); ctx.globalAlpha = 0.85;
      ctx.beginPath(); ctx.arc(cx + Math.cos(a) * d, cy + Math.sin(a) * d, rad, 0, 7); ctx.fill();
      ctx.globalAlpha = 1; ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.lineWidth = lw; ctx.stroke();
    }
  }
  // squares stepping across (Lye's stencils)
  if (kind === 1 || kind === 3) {
    for (let k = 0; k < 6; k++) {
      const sz = s * (0.05 + 0.1 * hash(ph, 60 + k)), x = ((hash(ph, 70 + k) + t * (k % 2 ? 0.5 : -0.35) + 2) % 1) * (w - sz), y = hash(ph, 80 + k) * (h - sz);
      ctx.fillStyle = hue(k); ragged(ctx, x, y, x + sz, y + sz * (0.6 + 0.8 * hash(ph, 90 + k)), r, lw * 2.5);
    }
  }
  // a comb of fine light lines
  ctx.strokeStyle = lamp(0.7); ctx.lineWidth = lw * 0.7; ctx.lineCap = "round";
  const lines = 14, y0 = h * (0.1 + 0.6 * hash(ph, 99));
  for (let i = 0; i < lines; i++) { const y = y0 + i * lw * 2.2 + (r() - 0.5) * lw; needle(ctx, w * (0.05 + 0.4 * r()), y, w * (0.55 + 0.4 * r()), y + (r() - 0.5) * lw * 3, r, lw * 2); }
  ctx.fillStyle = lamp(0.8);
  for (let i = 0; i < 16; i++) { ctx.beginPath(); ctx.arc(r() * w, r() * h, lw * (0.4 + r() * 0.8), 0, 7); ctx.fill(); }
}

// ---------------------------------------------------------------- pressed: matter between tape (Mothlight)
function drawPressed(ctx: Ctx, w: number, h: number, frame0: number, lw: number) {
  const frame = frame0 & ~1;
  const r = rngFrom(hash(frame, 3, 3) * 4294967296);
  const s = Math.min(w, h);
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "#c49a45"); g.addColorStop(1, "#a97b30");
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  const n = 8 + Math.floor(r() * 7);
  for (let i = 0; i < n; i++) {
    const x = r() * w, y = r() * h, a = r() * Math.PI, kind = Math.floor(r() * 4);
    ctx.save(); ctx.translate(x, y); ctx.rotate(a);
    if (kind === 0) {                                          // petal
      const rx = s * (0.04 + 0.08 * r()), ry = rx * (0.4 + 0.3 * r());
      ctx.fillStyle = `rgba(${90 + (r() * 60) | 0},${40 + (r() * 30) | 0},${20},${0.45 + r() * 0.3})`;
      ctx.beginPath(); ctx.ellipse(0, 0, rx, ry, 0, 0, 7); ctx.fill();
      ctx.strokeStyle = "rgba(255,230,170,.35)"; ctx.lineWidth = lw * 0.6; ctx.beginPath(); ctx.moveTo(-rx, 0); ctx.lineTo(rx, 0); ctx.stroke();
    } else if (kind === 1) {                                   // a wing with veins
      const rx = s * (0.06 + 0.1 * r()), ry = rx * 0.5;
      ctx.fillStyle = "rgba(60,38,18,.4)"; ctx.beginPath(); ctx.ellipse(0, 0, rx, ry, 0, 0, 7); ctx.fill();
      ctx.strokeStyle = "rgba(255,226,160,.45)"; ctx.lineWidth = lw * 0.5;
      for (let k = -3; k <= 3; k++) { ctx.beginPath(); ctx.moveTo(-rx * 0.9, 0); ctx.quadraticCurveTo(0, ry * k * 0.35, rx, ry * k * 0.28); ctx.stroke(); }
    } else if (kind === 2) {                                   // a blade of grass
      ctx.strokeStyle = `rgba(${40 + (r() * 30) | 0},${70 + (r() * 40) | 0},30,.7)`; ctx.lineWidth = lw * (1 + r());
      ctx.beginPath(); ctx.moveTo(-s * 0.1, 0); ctx.quadraticCurveTo(0, (r() - 0.5) * s * 0.1, s * (0.08 + 0.1 * r()), (r() - 0.5) * s * 0.05); ctx.stroke();
    } else {                                                   // seeds
      ctx.fillStyle = "rgba(50,30,12,.7)";
      for (let k = 0; k < 6; k++) { ctx.beginPath(); ctx.arc((r() - 0.5) * s * 0.1, (r() - 0.5) * s * 0.1, lw * (0.6 + r()), 0, 7); ctx.fill(); }
    }
    ctx.restore();
  }
  // the two tapes: the join shows as a pale line across the strip
  ctx.fillStyle = "rgba(255,240,200,.18)"; ctx.fillRect(0, h * 0.5 - lw, w, lw * 2);
  ctx.fillStyle = "rgba(20,12,4,.6)";
  for (let i = 0; i < 18; i++) { ctx.beginPath(); ctx.arc(r() * w, r() * h, lw * (0.3 + r() * 0.6), 0, 7); ctx.fill(); }
}

/** Draw frame `frame` of stock `tone` into a w x h canvas context. lw is the needle width in pixels. */
export function drawFrame(ctx: Ctx, w: number, h: number, frame: number, tone: Tone, lw = Math.max(1, Math.min(w, h) / 220)) {
  ctx.save();
  ctx.globalAlpha = 1; ctx.setLineDash([]);
  if (tone === "leader") drawLeader(ctx, w, h, frame, lw);
  else if (tone === "dye") drawDye(ctx, w, h, frame, lw);
  else drawPressed(ctx, w, h, frame, lw);
  // a hair caught in the gate, three frames at a time
  if (hash(Math.floor(frame / 3), 11, toneId(tone)) < 0.14) {
    const r = rngFrom(hash(Math.floor(frame / 3), 12) * 4294967296);
    ctx.strokeStyle = tone === "leader" ? lamp(0.7) : "rgba(10,6,2,.7)"; ctx.lineWidth = lw * 0.8; ctx.lineCap = "round";
    const side = r() < 0.5, y = r() * h, x0 = side ? 0 : w;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.bezierCurveTo(w * (side ? 0.2 : 0.8), y + (r() - 0.5) * h * 0.3, w * (side ? 0.3 : 0.7), y + (r() - 0.5) * h * 0.4, w * (0.15 + 0.7 * r()), y + (r() - 0.5) * h * 0.5); ctx.stroke();
  }
  ctx.restore();
}

/** One frame of flash leader at a splice: a single middling colour, never white. */
export function drawFlash(ctx: Ctx, w: number, h: number, k: number) {
  ctx.fillStyle = FLASH[Math.abs(k) % FLASH.length]; ctx.fillRect(0, 0, w, h);
}

/**
 * Run-on scratches belong to the strip, not to a frame: vertical lines at fixed places along it that travel with the
 * film. y is the strip position (px) the top of the screen is at.
 */
export function drawRunOn(ctx: Ctx, w: number, h: number, y: number, tone: Tone, lw: number, speed: number) {
  const cols = 9;
  ctx.save();
  ctx.lineCap = "butt"; ctx.lineWidth = lw * 0.8;
  for (let c = 0; c < cols; c++) {
    const x = Math.round(hash(c, 77) * w) + 0.5, seg = 380 + hash(c, 78) * 900, per = Math.floor((y + hash(c, 79) * 5000) / seg);
    if (hash(c, per, 80) > 0.42) continue;
    const y0 = per * seg - hash(c, 79) * 5000, y1 = y0 + seg * (0.4 + hash(c, per, 81) * 0.6);
    ctx.strokeStyle = tone === "leader" ? lamp(0.18 + Math.min(0.4, speed * 0.0002)) : lamp(0.16);
    ctx.beginPath(); ctx.moveTo(x, y0 - y); ctx.lineTo(x + (hash(c, per, 82) - 0.5) * 3, y1 - y); ctx.stroke();
  }
  ctx.restore();
}

/** Mean relative luminance (sRGB, 0..1) of a frame, for the flash audit. */
export function meanLuma(frame: number, tone: Tone, cvs: HTMLCanvasElement): number {
  const w = (cvs.width = 96), h = (cvs.height = 54);
  const ctx = cvs.getContext("2d", { willReadFrequently: true })!;
  drawFrame(ctx, w, h, frame, tone, 0.5);
  const d = ctx.getImageData(0, 0, w, h).data;
  const lin = (v: number) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += 0.2126 * lin(d[i]) + 0.7152 * lin(d[i + 1]) + 0.0722 * lin(d[i + 2]);
  return sum / (d.length / 4);
}
