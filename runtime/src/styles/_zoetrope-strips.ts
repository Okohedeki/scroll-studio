/**
 * Zoetrope strips: each section's 12-frame paper strip, drawn in the browser in the manner of a Victorian
 * chromolithographed "Wheel of Life" strip (cream paper, black silhouettes, vermilion, Prussian blue, ochre ground,
 * ruled frames numbered underneath, a printed title along the top). Every subject is a closed loop: frame 11 leads back
 * into frame 0. Used by zoetrope.ts both as the drum's texture and, laid flat, as the reduced-motion still.
 */
import type { ArtFrames } from "./_art";
import { skin, skinRgba } from "./_kit";

export type Motif = "ball" | "word" | "bird" | "walker" | "turn" | "parade" | "question" | "quote" | "cta" | "art" | "picture" | "coin" | "bars" | "sun" | "pan";
export interface Device { app?: string; title?: string; label?: string; note?: string; button?: string; options?: string[]; selected?: string }
export interface StripSpec {
  motif: Motif;
  label: string;           // printed along the top margin
  number: number;          // strip number ("No. 3")
  maker: string;           // site name, printed in the bottom margin
  word?: string;           // word / cta: the letters that hop
  tag?: string;            // small numeral printed in each frame's corner
  stats?: { value: string; unit: string }[];
  device?: Device | null;
  art?: ArtFrames | null;
  img?: HTMLImageElement | null;
  travel?: boolean;        // a parade: the figures march round the drum instead of animating in place
}

export const FRAMES = 12;
// the print: its ink, red and blue are the style's ink and two accents (a brand's colours when it wears one); the paper and the rest are the card stock's
const PAPER = "#efe2c4", PAPER2 = "#e2cfa6", INK = skin("ink", "#1b1611"), RED = skin("accent", "#c8402a"), BLUE = skin("accent2", "#2b5079"), OCHRE = "#c78f2a", SKY = "#dfe0cf";
const DISPLAY = '"Bodoni Moda", Georgia, serif', SLAB = '"Alfa Slab One", Georgia, serif';
const TAU = Math.PI * 2;

export async function stripFonts() {
  try {
    await Promise.all([
      document.fonts.load(`800 40px ${DISPLAY}`), document.fonts.load(`italic 500 20px ${DISPLAY}`), document.fonts.load(`20px ${SLAB}`),
    ]);
  } catch { /* fall back to Georgia */ }
}

/** Frame width in px for a strip of this pixel budget; the strip is 12 frames wide. */
export function stripSize(fw: number) {
  const mt = Math.round(fw * 0.1), fh = Math.round(fw * 0.86), mb = Math.round(fw * 0.16);
  return { fw, fh, mt, mb, w: fw * FRAMES, h: mt + fh + mb };
}

export function drawStrip(spec: StripSpec, fw: number): HTMLCanvasElement {
  const S = stripSize(fw);
  const c = document.createElement("canvas");
  c.width = S.w; c.height = S.h;
  const ctx = c.getContext("2d")!;
  // paper with a little tooth
  ctx.fillStyle = PAPER; ctx.fillRect(0, 0, S.w, S.h);
  let seed = 7 + spec.number * 13;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  ctx.fillStyle = "rgba(120, 90, 40, .07)";
  for (let i = 0; i < S.w * S.h / 260; i++) ctx.fillRect(rnd() * S.w, rnd() * S.h, 1 + rnd() * 1.5, 1);
  // printed top band
  ctx.fillStyle = PAPER2; ctx.fillRect(0, 0, S.w, S.mt);
  ctx.fillStyle = INK; ctx.font = `${Math.round(S.mt * 0.56)}px ${SLAB}`; ctx.textBaseline = "middle";
  const head = `No. ${spec.number}  ·  ${spec.label.toUpperCase()}  ·  `;
  const hw = ctx.measureText(head).width;
  for (let x = fw * 0.12; x < S.w; x += hw) ctx.fillText(head, x, S.mt * 0.55);
  // frames
  for (let k = 0; k < FRAMES; k++) {
    const x = k * fw, y = S.mt;
    ctx.save();
    ctx.beginPath(); ctx.rect(x, y, fw, S.fh); ctx.clip();
    drawFrame(ctx, spec, k, x, y, fw, S.fh);
    ctx.restore();
  }
  // rules between frames and along the edges
  ctx.fillStyle = INK;
  ctx.fillRect(0, S.mt - 2, S.w, 3); ctx.fillRect(0, S.mt + S.fh - 1, S.w, 3);
  for (let k = 0; k <= FRAMES; k++) ctx.fillRect(k * fw - 2, S.mt, 4, S.fh);
  // numbers underneath and the maker's line
  ctx.font = `italic 500 ${Math.round(S.mb * 0.38)}px ${DISPLAY}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (let k = 0; k < FRAMES; k++) ctx.fillText(String(k + 1), k * fw + fw / 2, S.mt + S.fh + S.mb * 0.36);
  ctx.font = `${Math.round(S.mb * 0.24)}px ${SLAB}`; ctx.fillStyle = "rgba(27, 22, 17, .62)";
  const maker = `${spec.maker.toUpperCase()}  ·  THE WHEEL OF LIFE`;
  for (let k = 1; k < FRAMES; k += 4) ctx.fillText(maker, k * fw + fw, S.mt + S.fh + S.mb * 0.76);
  ctx.textAlign = "left";
  return c;
}

// ---------------------------------------------------------------- one frame
export function drawFrame(ctx: CanvasRenderingContext2D, s: StripSpec, k: number, x: number, y: number, w: number, h: number) {
  const p = k / FRAMES;
  switch (s.motif) {
    case "ball": ball(ctx, p, k, x, y, w, h); break;
    case "word": word(ctx, s.word || "", p, x, y, w, h, false); break;
    case "cta": cta(ctx, s.word || "", p, x, y, w, h); break;
    case "bird": bird(ctx, p, x, y, w, h); break;
    case "walker": walker(ctx, p, x, y, w, h); break;
    case "turn": turn(ctx, s.device || null, p, x, y, w, h); break;
    case "picture": picture(ctx, s.img || null, p, x, y, w, h); break;
    case "parade": parade(ctx, s.stats || [], k, x, y, w, h); break;
    case "question": question(ctx, p, x, y, w, h); break;
    case "quote": quote(ctx, p, k, x, y, w, h); break;
    case "art": art(ctx, s.art || null, p, x, y, w, h); break;
    case "coin": coin(ctx, s.tag || String(s.number), p, x, y, w, h); break;
    case "bars": bars(ctx, s.stats || [], p, x, y, w, h); break;
    case "sun": sun(ctx, p, x, y, w, h); break;
    case "pan": pan(ctx, s.img || null, p, x, y, w, h); break;
  }
  if (s.motif === "coin") return;
  if (s.tag) {
    ctx.fillStyle = INK; ctx.font = `${Math.round(h * 0.085)}px ${SLAB}`; ctx.textBaseline = "top";
    ctx.fillText(s.tag, x + w * 0.09, y + h * 0.06);
  }
}

function ground(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, g = 0.8, col = OCHRE) {
  ctx.fillStyle = col; ctx.fillRect(x, y + h * g, w, h * (1 - g));
  ctx.fillStyle = INK; ctx.fillRect(x, y + h * g - 1, w, 2);
  ctx.fillStyle = "rgba(27, 22, 17, .22)";
  for (let i = 0; i < 6; i++) ctx.fillRect(x + w * (0.08 + i * 0.16), y + h * (g + 0.06 + (i % 2) * 0.06), w * 0.07, 2);
}

function ball(ctx: CanvasRenderingContext2D, p: number, k: number, x: number, y: number, w: number, h: number) {
  ground(ctx, x, y, w, h);
  const g = y + h * 0.8, R = h * 0.105;
  const t = p;                       // 0 = contact, .5 = top of the arc
  const lift = 4 * t * (1 - t) * h * 0.5;
  let sx = 1, sy = 1;
  if (k === 0) { sx = 1.32; sy = 0.68; } else if (k === 1 || k === 11) { sx = 0.86; sy = 1.18; }
  const cx = x + w / 2, cy = g - R * sy - lift;
  // shadow
  ctx.fillStyle = "rgba(27, 22, 17, .35)";
  const sh = 1 - lift / (h * 0.55);
  ctx.beginPath(); ctx.ellipse(cx, g + h * 0.025, R * 1.2 * (0.45 + 0.55 * sh), R * 0.22 * (0.45 + 0.55 * sh), 0, 0, TAU); ctx.fill();
  ctx.save(); ctx.translate(cx, cy); ctx.scale(sx, sy);
  ctx.fillStyle = RED; ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = INK; ctx.stroke();
  ctx.strokeStyle = PAPER; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(0, 0, R * 0.62, -2.6, -1.7); ctx.stroke();
  ctx.restore();
  if (k === 0) {   // dust puffs on contact
    ctx.strokeStyle = INK; ctx.lineWidth = 2;
    for (const d of [-1, 1]) { ctx.beginPath(); ctx.moveTo(cx + d * R * 1.5, g - 4); ctx.lineTo(cx + d * R * 2.2, g - R * 0.6); ctx.stroke(); }
  }
}

/** Letters hopping in a travelling wave, each squashing as it lands. */
function word(ctx: CanvasRenderingContext2D, text: string, p: number, x: number, y: number, w: number, h: number, light: boolean, base = 0.74) {
  if (!light) ground(ctx, x, y, w, h, 0.8, PAPER2);
  const t = text.trim() || "·";
  let size = h * 0.34;
  ctx.font = `800 ${size}px ${DISPLAY}`;
  const tw = ctx.measureText(t).width;
  if (tw > w * 0.84) { size *= (w * 0.84) / tw; ctx.font = `800 ${size}px ${DISPLAY}`; }
  const total = ctx.measureText(t).width;
  let cx = x + (w - total) / 2;
  const by = y + h * base;
  ctx.textBaseline = "alphabetic";
  let li = 0;
  for (const ch of t) {
    const cw = ctx.measureText(ch).width;
    if (ch !== " ") {
      const ph = TAU * p - li * 0.62;
      const hop = Math.max(0, Math.sin(ph));
      const land = Math.max(0, -Math.sin(ph)) * (Math.cos(ph) > 0 ? 1 : 0);
      const dy = -hop * h * 0.24;
      const sy = 1 + hop * 0.1 - land * 0.16, sx = 1 - hop * 0.06 + land * 0.12;
      ctx.save(); ctx.translate(cx + cw / 2, by + dy); ctx.scale(sx, sy);
      if (!light) { ctx.fillStyle = "rgba(27, 22, 17, .25)"; ctx.beginPath(); ctx.ellipse(0, -dy + 4, cw * 0.4 * (1 - hop * 0.5), 3, 0, 0, TAU); ctx.fill(); }
      ctx.fillStyle = hop > 0.85 ? RED : (light ? PAPER : INK);
      ctx.fillText(ch, -cw / 2, 0);
      if (light) { ctx.lineWidth = Math.max(1.5, size * 0.04); ctx.strokeStyle = INK; ctx.strokeText(ch, -cw / 2, 0); }
      ctx.restore();
      li++;
    }
    cx += cw;
  }
}

function cta(ctx: CanvasRenderingContext2D, text: string, p: number, x: number, y: number, w: number, h: number) {
  const cx = x + w / 2, cy = y + h * 0.55;
  const rays = 16, rot = p * (TAU / (rays / 2));
  for (let i = 0; i < rays; i++) {
    const a0 = rot + (i / rays) * TAU, a1 = a0 + TAU / rays;
    ctx.fillStyle = i % 2 ? PAPER : "#e9b48a";
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a0) * w, cy + Math.sin(a0) * w); ctx.lineTo(cx + Math.cos(a1) * w, cy + Math.sin(a1) * w); ctx.fill();
  }
  ctx.fillStyle = RED; ctx.beginPath(); ctx.arc(cx, cy, h * 0.13, 0, TAU); ctx.fill();
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.stroke();
  // ribbon banner
  const bh = h * 0.26, by = y + h * 0.16;
  ctx.fillStyle = PAPER; ctx.fillRect(x + w * 0.04, by, w * 0.92, bh);
  ctx.strokeStyle = INK; ctx.lineWidth = 2.5; ctx.strokeRect(x + w * 0.04, by, w * 0.92, bh);
  ctx.save(); ctx.beginPath(); ctx.rect(x + w * 0.04, by - h * 0.2, w * 0.92, bh + h * 0.2); ctx.clip();
  word(ctx, text, p, x, by - h * 0.5, w, h, false, 0.5 + 0.86 * (bh / h));
  ctx.restore();
}

function bird(ctx: CanvasRenderingContext2D, p: number, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = SKY; ctx.fillRect(x, y, w, h);
  // clouds drift one frame-width per loop (seamless)
  ctx.strokeStyle = "rgba(43, 80, 121, .5)"; ctx.lineWidth = 2;
  for (let i = -1; i < 2; i++) {
    const cxl = x + ((i + 1 - p) % 2) * w * 0.9 + w * 0.1, cyl = y + h * (0.22 + (i + 1) * 0.25);
    ctx.beginPath(); ctx.arc(cxl, cyl, h * 0.04, Math.PI, 0); ctx.arc(cxl + h * 0.07, cyl - h * 0.02, h * 0.05, Math.PI, 0); ctx.arc(cxl + h * 0.15, cyl, h * 0.035, Math.PI, 0); ctx.stroke();
  }
  ctx.fillStyle = BLUE; ctx.fillRect(x, y + h * 0.88, w, h * 0.12);
  const a = Math.sin(TAU * p);           // wing angle: +1 up, -1 down
  const bob = -Math.sin(TAU * p + 0.8) * h * 0.04;
  const cx = x + w * 0.5, cy = y + h * 0.5 + bob;
  const span = w * 0.4, tipY = -a * h * 0.3, midY = -a * h * 0.12;
  ctx.fillStyle = INK;
  for (const d of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(cx + d * w * 0.03, cy - h * 0.02);
    ctx.quadraticCurveTo(cx + d * span * 0.45, cy + midY - h * 0.06, cx + d * span, cy + tipY);
    ctx.quadraticCurveTo(cx + d * span * 0.55, cy + midY + h * 0.04, cx + d * w * 0.03, cy + h * 0.035);
    ctx.fill();
  }
  ctx.beginPath(); ctx.ellipse(cx, cy, w * 0.11, h * 0.04, 0, 0, TAU); ctx.fill();
  ctx.beginPath(); ctx.arc(cx + w * 0.1, cy - h * 0.02, h * 0.035, 0, TAU); ctx.fill();
  ctx.fillStyle = OCHRE; ctx.beginPath(); ctx.moveTo(cx + w * 0.13, cy - h * 0.025); ctx.lineTo(cx + w * 0.17, cy - h * 0.012); ctx.lineTo(cx + w * 0.13, cy); ctx.fill();
  ctx.fillStyle = INK; ctx.beginPath(); ctx.moveTo(cx - w * 0.1, cy); ctx.lineTo(cx - w * 0.17, cy - h * 0.03); ctx.lineTo(cx - w * 0.16, cy + h * 0.03); ctx.fill();
}

function limb(ctx: CanvasRenderingContext2D, x0: number, y0: number, a1: number, a2: number, l1: number, l2: number) {
  const x1 = x0 + Math.sin(a1) * l1, y1 = y0 + Math.cos(a1) * l1;
  const x2 = x1 + Math.sin(a2) * l2, y2 = y1 + Math.cos(a2) * l2;
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  return [x2, y2];
}

/** A gentleman in a top hat walking on the spot while milestone posts slide past behind him. */
function walker(ctx: CanvasRenderingContext2D, p: number, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = SKY; ctx.fillRect(x, y, w, h);
  ground(ctx, x, y, w, h, 0.84);
  const g = y + h * 0.84;
  // posts: one every 0.75 frame widths, moving left a whole spacing per loop
  const sp = w * 0.75;
  for (let i = -1; i < 3; i++) {
    const px = x + i * sp - p * sp + w * 0.2;
    ctx.fillStyle = INK; ctx.fillRect(px - 2, g - h * 0.34, 4, h * 0.34);
    ctx.fillStyle = RED; ctx.beginPath(); ctx.moveTo(px + 2, g - h * 0.34); ctx.lineTo(px + w * 0.13, g - h * 0.3); ctx.lineTo(px + 2, g - h * 0.26); ctx.fill();
  }
  const ph = TAU * p;
  const L = h * 0.17, bob = Math.abs(Math.cos(ph)) * h * 0.012;
  const hipX = x + w * 0.5, hipY = g - L * 1.95 + bob;
  ctx.strokeStyle = INK; ctx.lineCap = "round"; ctx.lineJoin = "round";
  // far leg and arm (lighter), then near
  for (const [side, alpha] of [[1, 0.55], [0, 1]] as const) {
    const q = ph + side * Math.PI;
    const thigh = -0.5 * Math.sin(q);
    const shin = thigh + 0.65 * Math.max(0, Math.cos(q));
    ctx.globalAlpha = alpha; ctx.lineWidth = h * 0.045;
    limb(ctx, hipX, hipY, thigh, shin - 0.05, L, L);
    // arm swings opposite to the leg
    const arm = 0.42 * Math.sin(q);
    ctx.lineWidth = h * 0.035;
    limb(ctx, hipX + w * 0.01, hipY - L * 1.15, arm, arm - 0.35, L * 0.62, L * 0.55);
  }
  ctx.globalAlpha = 1;
  // coat
  ctx.fillStyle = INK;
  ctx.beginPath();
  ctx.moveTo(hipX - w * 0.045, hipY - L * 1.25); ctx.lineTo(hipX + w * 0.05, hipY - L * 1.25);
  ctx.lineTo(hipX + w * 0.07, hipY + L * 0.2); ctx.lineTo(hipX - w * 0.075, hipY + L * 0.35); ctx.fill();
  // head and top hat
  const hy = hipY - L * 1.25 - h * 0.06;
  ctx.beginPath(); ctx.arc(hipX + w * 0.008, hy, h * 0.05, 0, TAU); ctx.fill();
  ctx.fillRect(hipX - w * 0.05, hy - h * 0.06, w * 0.11, h * 0.018);
  ctx.fillRect(hipX - w * 0.03, hy - h * 0.15, w * 0.07, h * 0.1);
  ctx.fillStyle = RED; ctx.fillRect(hipX - w * 0.03, hy - h * 0.075, w * 0.07, h * 0.016);
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

/** The phone on a turntable: twelve views round 360 degrees. */
function turn(ctx: CanvasRenderingContext2D, d: Device | null, p: number, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = SKY; ctx.fillRect(x, y, w, h);
  const cx = x + w / 2, base = y + h * 0.86;
  ctx.fillStyle = OCHRE; ctx.beginPath(); ctx.ellipse(cx, base, w * 0.34, h * 0.06, 0, 0, TAU); ctx.fill();
  ctx.strokeStyle = INK; ctx.lineWidth = 2; ctx.stroke();
  ctx.fillStyle = INK; ctx.fillRect(cx - w * 0.34, base, w * 0.68, h * 0.05);
  ctx.fillStyle = OCHRE; ctx.beginPath(); ctx.ellipse(cx, base, w * 0.34, h * 0.06, 0, 0, Math.PI); ctx.fill();
  const ph = TAU * p, co = Math.cos(ph), si = Math.sin(ph);
  const H = h * 0.64, W = H * 0.5, D = W * 0.14;
  const top = base - H - h * 0.01;
  const fw = Math.abs(co) * W, sw = Math.abs(si) * D;
  const total = fw + sw;
  const left = cx - total / 2;
  const faceX = si > 0 ? left + sw : left, sideX = si > 0 ? left : left + fw;
  // side band
  ctx.fillStyle = "#3a2f25"; roundRect(ctx, sideX, top + 4, sw + 2, H - 8, 2); ctx.fill();
  if (fw < 1.5) return;
  ctx.save();
  roundRect(ctx, faceX, top, fw, H, Math.min(fw * 0.18, W * 0.14)); ctx.fillStyle = INK; ctx.fill(); ctx.clip();
  if (co > 0) {
    // the screen, foreshortened by scaling x
    ctx.translate(faceX, top); ctx.scale(fw / W, 1);
    const m = W * 0.06;
    ctx.fillStyle = PAPER; roundRect(ctx, m, m, W - 2 * m, H - 2 * m, W * 0.08); ctx.fill();
    ctx.fillStyle = INK; ctx.font = `600 ${Math.round(W * 0.09)}px ${DISPLAY}`; ctx.textBaseline = "top";
    ctx.fillText((d?.app || "").slice(0, 12), m * 2.2, m * 2.4);
    ctx.font = `800 ${Math.round(W * 0.12)}px ${DISPLAY}`;
    const title = (d?.title || "").split(" ");
    ctx.fillText(title.slice(0, 2).join(" ").slice(0, 14), m * 2.2, m * 4.6);
    if (title.length > 2) ctx.fillText(title.slice(2).join(" ").slice(0, 14), m * 2.2, m * 4.6 + W * 0.14);
    const opts = (d?.options?.length ? d.options : ["", "", ""]).slice(0, 3);
    opts.forEach((o, i) => {
      const oy = H * 0.42 + i * H * 0.13;
      const sel = d?.selected ? o === d.selected : i === 0;
      ctx.fillStyle = sel ? RED : "rgba(27, 22, 17, .12)";
      roundRect(ctx, m * 1.8, oy, W - m * 3.6, H * 0.1, 4); ctx.fill();
      ctx.fillStyle = sel ? PAPER : INK; ctx.font = `600 ${Math.round(W * 0.075)}px ${DISPLAY}`; ctx.textBaseline = "middle";
      ctx.fillText(o.slice(0, 13), m * 2.8, oy + H * 0.05);
    });
    ctx.fillStyle = INK; roundRect(ctx, m * 1.8, H * 0.83, W - m * 3.6, H * 0.08, H * 0.04); ctx.fill();
  } else {
    ctx.fillStyle = "#2b231c"; ctx.fillRect(faceX, top, fw, H);
    ctx.fillStyle = PAPER2; ctx.beginPath(); ctx.ellipse(faceX + fw * 0.3, top + H * 0.1, fw * 0.1, W * 0.05, 0, 0, TAU); ctx.fill();
    ctx.fillStyle = RED; ctx.beginPath(); ctx.ellipse(faceX + fw / 2, top + H * 0.5, fw * 0.14, W * 0.07, 0, 0, TAU); ctx.fill();
  }
  ctx.restore();
  // a glint that sweeps across the face
  ctx.strokeStyle = "rgba(255, 255, 255, .35)"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(faceX + fw * 0.2, top + 6); ctx.lineTo(faceX + fw * 0.2, top + H - 6); ctx.stroke();
}

/** A picture (product shot) turning on a stand, for products without a phone. */
function picture(ctx: CanvasRenderingContext2D, img: HTMLImageElement | null, p: number, x: number, y: number, w: number, h: number) {
  if (!img || !img.naturalWidth) { ball(ctx, p, Math.round(p * FRAMES), x, y, w, h); return; }
  ctx.fillStyle = SKY; ctx.fillRect(x, y, w, h);
  ground(ctx, x, y, w, h, 0.86);
  const co = Math.cos(TAU * p);
  const ih = h * 0.6, iw = Math.min(w * 0.8, ih * img.naturalWidth / img.naturalHeight);
  ctx.save(); ctx.translate(x + w / 2, y + h * 0.5); ctx.scale(Math.max(0.04, Math.abs(co)), 1);
  if (co > 0) ctx.drawImage(img, -iw / 2, -ih / 2, iw, ih); else { ctx.fillStyle = INK; ctx.fillRect(-iw / 2, -ih / 2, iw, ih); }
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.strokeRect(-iw / 2, -ih / 2, iw, ih);
  ctx.restore();
}

/** One cartouche per frame, the stats in turn; on the drum they march round instead of animating in place. */
function parade(ctx: CanvasRenderingContext2D, stats: { value: string; unit: string }[], k: number, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = k % 2 ? PAPER : "#ead8b2"; ctx.fillRect(x, y, w, h);
  if (!stats.length) return;
  const st = stats[k % stats.length];
  const cx = x + w / 2, cy = y + h * 0.48;
  ctx.fillStyle = PAPER; ctx.beginPath(); ctx.ellipse(cx, cy, w * 0.4, h * 0.34, 0, 0, TAU); ctx.fill();
  ctx.strokeStyle = INK; ctx.lineWidth = 4; ctx.stroke();
  ctx.lineWidth = 1.5; ctx.beginPath(); ctx.ellipse(cx, cy, w * 0.36, h * 0.3, 0, 0, TAU); ctx.stroke();
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * TAU;
    ctx.fillStyle = i % 2 ? RED : OCHRE;
    ctx.beginPath(); ctx.arc(cx + Math.cos(a) * w * 0.4, cy + Math.sin(a) * h * 0.34, h * 0.022, 0, TAU); ctx.fill();
  }
  let size = h * 0.3;
  ctx.font = `800 ${size}px ${DISPLAY}`;
  const vw = ctx.measureText(st.value).width;
  if (vw > w * 0.56) { size *= (w * 0.56) / vw; ctx.font = `800 ${size}px ${DISPLAY}`; }
  ctx.fillStyle = INK; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  ctx.fillText(st.value, cx, cy + size * 0.3);
  if (st.unit) { ctx.fillStyle = RED; ctx.font = `italic 500 ${Math.round(h * 0.09)}px ${DISPLAY}`; ctx.fillText(st.unit, cx, cy + size * 0.3 + h * 0.11); }
  ctx.textAlign = "left";
  // a banner under the cartouche
  ctx.fillStyle = BLUE; ctx.fillRect(x, y + h * 0.9, w, h * 0.1);
}

function question(ctx: CanvasRenderingContext2D, p: number, x: number, y: number, w: number, h: number) {
  ground(ctx, x, y, w, h, 0.84, PAPER2);
  // the question mark hops and rocks on its dot, squashing as it lands
  const ph = TAU * p, up = Math.max(0, Math.sin(ph)), land = Math.max(0, -Math.sin(ph));
  const co = 0.75 + 0.25 * Math.cos(ph);
  const hop = up * h * 0.14;
  const size = Math.min(h * 0.62, w * 0.9);
  ctx.save(); ctx.translate(x + w / 2, y + h * 0.8 - hop); ctx.rotate(Math.sin(ph * 2) * 0.16);
  ctx.scale(1 + land * 0.18, 1 - land * 0.16);
  ctx.font = `900 ${size}px ${DISPLAY}`; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  ctx.fillStyle = up > 0.7 ? RED : INK; ctx.fillText("?", 0, -size * 0.05);
  ctx.restore();
  ctx.fillStyle = "rgba(27, 22, 17, .3)";
  ctx.beginPath(); ctx.ellipse(x + w / 2, y + h * 0.86, w * 0.14 * (0.6 + 0.4 * Math.abs(co)), h * 0.02, 0, 0, TAU); ctx.fill();
}

const PROFILE: [number, number][] = [
  [0.3, 0.05], [0.55, 0.0], [0.74, 0.08], [0.8, 0.25], [0.785, 0.31], [0.9, 0.46], [0.8, 0.49], [0.815, 0.55], [0.78, 0.58],
  [0.8, 0.62], [0.765, 0.69], [0.78, 0.76], [0.66, 0.83], [0.62, 1.02], [0.28, 1.02], [0.3, 0.78], [0.17, 0.55], [0.17, 0.28],
];
/** A silhouette portrait in a cameo frame, speaking: the mouth opens on alternate frames, the balloon swells. */
function quote(ctx: CanvasRenderingContext2D, p: number, k: number, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = "#ead8b2"; ctx.fillRect(x, y, w, h);
  const cx = x + w * 0.36, cy = y + h * 0.56, rx = w * 0.27, ry = h * 0.34;
  ctx.fillStyle = PAPER; ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, TAU); ctx.fill();
  ctx.strokeStyle = OCHRE; ctx.lineWidth = 7; ctx.stroke(); ctx.strokeStyle = INK; ctx.lineWidth = 2; ctx.stroke();
  ctx.beginPath(); ctx.ellipse(cx, cy, rx - 6, ry - 6, 0, 0, TAU); ctx.lineWidth = 1; ctx.stroke();
  ctx.save(); ctx.beginPath(); ctx.ellipse(cx, cy, rx - 4, ry - 4, 0, 0, TAU); ctx.clip();
  const open = k % 2 === 0;
  const S = h * 0.56, ox = cx - S * 0.52, oy = cy - S * 0.44;
  const pts = PROFILE.map(([a, b], i) => [ox + a * S - (i === 8 && open ? S * 0.035 : 0), oy + b * S + (i >= 9 && i <= 11 && open ? S * 0.03 : 0)]);
  ctx.fillStyle = INK; ctx.beginPath();
  ctx.moveTo((pts[0][0] + pts[pts.length - 1][0]) / 2, (pts[0][1] + pts[pts.length - 1][1]) / 2);
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    ctx.quadraticCurveTo(a[0], a[1], (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
  }
  ctx.fill();
  ctx.beginPath(); ctx.arc(ox + 0.2 * S, oy + 0.22 * S, 0.12 * S, 0, TAU); ctx.fill();   // hair bun
  ctx.fillStyle = RED; ctx.fillRect(ox + 0.22 * S, oy + 0.3 * S, 0.06 * S, 0.02 * S); // ribbon
  ctx.restore();
  const sc = 0.82 + 0.18 * Math.sin(TAU * p);
  const bx = x + w * 0.77, by = y + h * 0.25;
  ctx.save(); ctx.translate(bx, by); ctx.scale(sc, sc);
  ctx.fillStyle = PAPER; ctx.strokeStyle = INK; ctx.lineWidth = 2.5;
  ctx.beginPath(); ctx.ellipse(0, 0, w * 0.2, h * 0.14, 0, 0, TAU); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-w * 0.1, h * 0.1); ctx.lineTo(-w * 0.2, h * 0.24); ctx.lineTo(-w * 0.02, h * 0.13); ctx.fill(); ctx.stroke();
  ctx.fillStyle = PAPER; ctx.fillRect(-w * 0.09, h * 0.08, w * 0.09, h * 0.05);
  ctx.fillStyle = RED; ctx.font = `800 ${Math.round(h * 0.2)}px ${DISPLAY}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText("“ ”", 0, h * 0.04);
  ctx.restore(); ctx.textAlign = "left";
}

const artCache = new WeakMap<ArtFrames, HTMLCanvasElement[]>();
function artFrame(a: ArtFrames, f: number): HTMLCanvasElement {
  let list = artCache.get(a);
  if (!list) { list = []; artCache.set(a, list); }
  if (list[f]) return list[f];
  const c = document.createElement("canvas"); c.width = a.w; c.height = a.h;
  const x = c.getContext("2d")!; const im = x.createImageData(a.w, a.h); const m = a.mask[f];
  for (let i = 0; i < m.length; i++) {
    const v = Math.max(0, Math.min(1, (m[i] - 0.16) / 0.6));
    im.data[i * 4] = 27; im.data[i * 4 + 1] = 22; im.data[i * 4 + 2] = 17; im.data[i * 4 + 3] = Math.round(Math.pow(v, 0.9) * 255);
  }
  x.putImageData(im, 0, 0);
  return (list[f] = c);
}
function art(ctx: CanvasRenderingContext2D, a: ArtFrames | null, p: number, x: number, y: number, w: number, h: number) {
  if (!a) { ball(ctx, p, Math.round(p * FRAMES), x, y, w, h); return; }
  ctx.fillStyle = "#ead8b2"; ctx.fillRect(x, y, w, h);
  // a vermilion sun behind the subject, the lithograph's second colour
  ctx.fillStyle = RED; ctx.beginPath(); ctx.arc(x + w * 0.5, y + h * 0.34, h * 0.2, 0, TAU); ctx.fill();
  const f = Math.floor(p * a.n) % a.n;
  const sc = Math.max(w / a.w, h / a.h);
  const dw = a.w * sc, dh = a.h * sc;
  ctx.drawImage(artFrame(a, f), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
}

/** A coin spinning on its edge and hopping, the feature's number struck on its face. */
function coin(ctx: CanvasRenderingContext2D, tag: string, p: number, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = SKY; ctx.fillRect(x, y, w, h);
  ground(ctx, x, y, w, h, 0.84);
  const q = p + 0.5 / FRAMES;   // half a step on: no frame catches the coin exactly edge-on
  const co = Math.cos(TAU * q), hop = Math.abs(Math.sin(TAU * q)) * h * 0.1;
  const R = Math.min(w, h) * 0.3, cx = x + w / 2, cy = y + h * 0.5 - hop;
  ctx.fillStyle = "rgba(27, 22, 17, .28)";
  ctx.beginPath(); ctx.ellipse(cx, y + h * 0.86, R * (0.5 + 0.5 * Math.abs(co)), h * 0.025, 0, 0, TAU); ctx.fill();
  const ex = Math.max(0.06, Math.abs(co));
  ctx.fillStyle = "#8a6420"; ctx.beginPath(); ctx.ellipse(cx + (co >= 0 ? -1 : 1) * R * 0.08 * (1 - ex), cy, R * ex + R * 0.08 * (1 - ex), R, 0, 0, TAU); ctx.fill();
  ctx.fillStyle = co >= 0 ? "#e2b54a" : "#d9a63c"; ctx.beginPath(); ctx.ellipse(cx, cy, R * ex, R, 0, 0, TAU); ctx.fill();
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.stroke();
  ctx.lineWidth = 1.5; ctx.beginPath(); ctx.ellipse(cx, cy, R * ex * 0.84, R * 0.84, 0, 0, TAU); ctx.stroke();
  ctx.save(); ctx.translate(cx, cy); ctx.scale(ex, 1);
  ctx.fillStyle = INK; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  if (co >= 0) { ctx.font = `800 ${Math.round(R * (tag.length > 2 ? 0.62 : 0.9))}px ${DISPLAY}`; ctx.fillText(tag, 0, R * 0.04); }
  else { ctx.font = `${Math.round(R * 0.9)}px ${DISPLAY}`; ctx.fillText("\u2605", 0, R * 0.04); }
  ctx.restore(); ctx.textAlign = "left";
}

/** The stats as columns that pump up and down in turn, each crowned with its figure. */
function bars(ctx: CanvasRenderingContext2D, stats: { value: string; unit: string }[], p: number, x: number, y: number, w: number, h: number) {
  ctx.fillStyle = PAPER; ctx.fillRect(x, y, w, h);
  ground(ctx, x, y, w, h, 0.86, PAPER2);
  const n = Math.max(1, stats.length), gap = w * 0.06, bw = (w - gap * (n + 1)) / n;
  const cols = [RED, BLUE, OCHRE, INK];
  stats.forEach((st, i) => {
    const pump = 0.5 + 0.5 * Math.sin(TAU * p - i * (TAU / n));
    const H = h * (0.2 + 0.46 * pump);
    const bx = x + gap + i * (bw + gap), by = y + h * 0.86 - H;
    ctx.fillStyle = cols[i % cols.length]; ctx.fillRect(bx, by, bw, H);
    ctx.strokeStyle = INK; ctx.lineWidth = 2.5; ctx.strokeRect(bx, by, bw, H);
    ctx.fillStyle = "rgba(255, 255, 255, .25)"; ctx.fillRect(bx + bw * 0.12, by + 4, bw * 0.12, Math.max(0, H - 8));
    let size = Math.min(bw * 0.62, h * 0.13);
    ctx.font = `800 ${size}px ${DISPLAY}`;
    const label = st.value + (st.unit && st.unit.length < 3 ? st.unit : "");
    const tw = ctx.measureText(label).width;
    if (tw > bw * 1.3) { size *= (bw * 1.3) / tw; ctx.font = `800 ${size}px ${DISPLAY}`; }
    ctx.fillStyle = INK; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
    ctx.fillText(label, bx + bw / 2, by - size * 0.25);
  });
  ctx.textAlign = "left";
}

/** A sunburst turning one ray-pair per loop, a red sun at its heart. */
function sun(ctx: CanvasRenderingContext2D, p: number, x: number, y: number, w: number, h: number) {
  const cx = x + w / 2, cy = y + h * 0.58;
  const rays = 18, rot = p * (TAU / (rays / 2));
  for (let i = 0; i < rays; i++) {
    const a0 = rot + (i / rays) * TAU, a1 = a0 + TAU / rays;
    ctx.fillStyle = i % 2 ? PAPER : "#efc39b";
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a0) * w * 1.5, cy + Math.sin(a0) * w * 1.5); ctx.lineTo(cx + Math.cos(a1) * w * 1.5, cy + Math.sin(a1) * w * 1.5); ctx.fill();
  }
  const r = Math.min(w, h) * 0.2 * (1 + 0.06 * Math.sin(TAU * p * 2));
  ctx.fillStyle = RED; ctx.beginPath(); ctx.arc(cx, cy, r, 0, TAU); ctx.fill();
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.stroke();
  ctx.fillStyle = BLUE; ctx.fillRect(x, y + h * 0.86, w, h * 0.14);
  ctx.fillStyle = INK; ctx.fillRect(x, y + h * 0.86, w, 2);
}

export interface Box { x: number; y: number; w: number; h: number }
export interface CardLayout { W: number; H: number; fig: Box; text: Box }
export const CARD_PAPER = "#f8f1df";

/** One printed card of the ring: border, header, the figure in pose k, footer. The text is baked on by the caller. */
export function drawCard(ctx: CanvasRenderingContext2D, L: CardLayout, spec: StripSpec, k: number, total: number) {
  const { W, H } = L;
  ctx.fillStyle = CARD_PAPER; ctx.fillRect(0, 0, W, H);
  const u = Math.min(W / 1000, H / 660) * (W < H ? 1.6 : 1);
  const m = Math.max(10, 18 * u);
  ctx.strokeStyle = INK; ctx.lineWidth = Math.max(2, 3 * u); ctx.strokeRect(m, m, W - 2 * m, H - 2 * m);
  ctx.lineWidth = Math.max(1, 1.2 * u); ctx.strokeRect(m + 6 * u, m + 6 * u, W - 2 * m - 12 * u, H - 2 * m - 12 * u);
  ctx.fillStyle = RED;
  for (const [cx, cy] of [[m, m], [W - m, m], [m, H - m], [W - m, H - m]]) { ctx.beginPath(); ctx.arc(cx, cy, 7 * u + 2, 0, TAU); ctx.fill(); }
  const hy = (L.fig.y < L.text.y ? L.fig.y : L.text.y) * 0.5 + m * 0.5 + 2;
  ctx.fillStyle = INK; ctx.textBaseline = "middle";
  ctx.font = `${Math.round(Math.max(12, 20 * u))}px ${SLAB}`; ctx.textAlign = "left";
  ctx.fillText(`No. ${spec.number}`, m + 22 * u, hy);
  if (W > H) { ctx.textAlign = "center"; ctx.font = `italic 500 ${Math.round(Math.max(12, 19 * u))}px ${DISPLAY}`; ctx.fillText(spec.label.slice(0, 48), W / 2, hy); }
  ctx.textAlign = "right"; ctx.font = `${Math.round(Math.max(11, 16 * u))}px ${SLAB}`; ctx.fillStyle = RED;
  ctx.fillText(`FIG. ${k + 1} OF ${total}`, W - m - 22 * u, hy);
  ctx.textAlign = "left";
  const f = L.fig;
  ctx.save(); ctx.beginPath(); ctx.rect(f.x, f.y, f.w, f.h); ctx.clip();
  drawFrame(ctx, spec.motif === "coin" ? spec : { ...spec, tag: undefined }, k, f.x, f.y, f.w, f.h);
  ctx.restore();
  ctx.strokeStyle = INK; ctx.lineWidth = Math.max(2, 3 * u); ctx.strokeRect(f.x, f.y, f.w, f.h);
  const low = Math.max(f.y + f.h, L.text.y + L.text.h);
  ctx.font = `${Math.round(Math.max(10, 13 * u))}px ${SLAB}`; ctx.fillStyle = skinRgba("ink", "#1d1611", 0.6); ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(`${spec.maker.toUpperCase()}  ·  THE WHEEL OF LIFE`, W / 2, (low + H - m) / 2);
  ctx.textAlign = "left";
}

/** The back of a card: a printed pattern, the maker's name in a cartouche. */
export function drawBack(ctx: CanvasRenderingContext2D, W: number, H: number, maker: string) {
  ctx.fillStyle = "#b5321b"; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "rgba(255, 236, 200, .35)"; ctx.lineWidth = 2;
  for (let i = -H; i < W; i += 22) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i + H, H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(i + H, 0); ctx.lineTo(i, H); ctx.stroke(); }
  const m = Math.min(W, H) * 0.05;
  ctx.strokeStyle = "#f2d38a"; ctx.lineWidth = 6; ctx.strokeRect(m, m, W - 2 * m, H - 2 * m);
  ctx.fillStyle = CARD_PAPER; ctx.beginPath(); ctx.ellipse(W / 2, H / 2, W * 0.3, H * 0.16, 0, 0, TAU); ctx.fill();
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.stroke();
  ctx.fillStyle = INK; ctx.font = `${Math.round(Math.min(W * 0.06, H * 0.09))}px ${SLAB}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(maker.toUpperCase().slice(0, 16), W / 2, H / 2);
  ctx.textAlign = "left";
}

/** A photograph seen as the view from a passing train: the window travels across it and back, the picture breathing. */
function pan(ctx: CanvasRenderingContext2D, img: HTMLImageElement | null, p: number, x: number, y: number, w: number, h: number) {
  if (!img || !img.naturalWidth) { ball(ctx, p, Math.round(p * FRAMES), x, y, w, h); return; }
  const t = 0.5 - 0.5 * Math.cos(TAU * p);               // there and back in one loop
  const zoom = 1.25 + 0.08 * Math.sin(TAU * p);
  const sc = Math.max(w / img.naturalWidth, h / img.naturalHeight) * zoom;
  const dw = img.naturalWidth * sc, dh = img.naturalHeight * sc;
  ctx.drawImage(img, x - (dw - w) * t, y - (dh - h) * 0.5, dw, dh);
  // a lithograph's warm cast and a printed edge
  ctx.fillStyle = "rgba(239, 226, 196, .18)"; ctx.fillRect(x, y, w, h);
}
