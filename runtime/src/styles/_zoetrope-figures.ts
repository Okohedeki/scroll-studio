/**
 * Zoetrope figures: one 12-frame loop per card, so no two cards on the wheel share an animation. Each figure is drawn
 * in the manner of a Victorian lithographed zoetrope strip (cream, ink, vermilion, Prussian blue, ochre) into a box, for
 * pose p in [0, 1). Pose 0 is always a good still: it is what a card shows at rest. Older figures (ball, bird, walker,
 * phone on a turntable, cameo, coin, sunburst, photo pan, theme art) come from _zoetrope-strips.ts.
 */
import type { ArtFrames } from "./_art";
import { skin } from "./_kit";
import { drawFrame, type Device, type StripSpec } from "./_zoetrope-strips";

export const FIGURES = [
  "bulb", "magnifier", "door", "key", "scales", "spring", "plane", "clock", "hourglass", "metronome", "windmill", "heart",
  "juggler", "rocket", "calendar", "envelope", "gears", "top", "waves", "butterfly", "fish", "bell", "kite", "moon",
  "dice", "pie", "counter", "tumbler", "pen", "orbit", "film", "tunnel", "sprout", "teacup", "sunrise",
  // from the strips
  "ball", "bird", "walker", "turn", "quote", "coin", "sun", "pan", "art", "picture", "question",
] as const;
export type Figure = (typeof FIGURES)[number];

export interface FigData {
  number: number; tag?: string; value?: string; unit?: string; label?: string; maker: string;
  device?: Device | null; img?: HTMLImageElement | null; imgs?: HTMLImageElement[]; art?: ArtFrames | null; frames?: HTMLCanvasElement[];
}

// the print: its ink, red and blue are the style's ink and two accents (a brand's colours when it wears one); the paper and the rest are the card stock's
const PAPER = "#efe2c4", PAPER2 = "#e2cfa6", INK = skin("ink", "#1b1611"), RED = skin("accent", "#c8402a"), BLUE = skin("accent2", "#2b5079"), OCHRE = "#c78f2a", SKY = "#dfe0cf", NIGHT = "#1f3354", GOLD = "#e2b54a";
const DISPLAY = '"Bodoni Moda", Georgia, serif', SLAB = '"Alfa Slab One", Georgia, serif';
const TAU = Math.PI * 2;
const tri = (p: number) => 0.5 - 0.5 * Math.cos(TAU * p);      // 0 at pose 0, 1 halfway, 0 again
type C = CanvasRenderingContext2D;

function rng(seed: number) { let s = seed % 2147483646 + 1; return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646; }
function ground(c: C, x: number, y: number, w: number, h: number, g = 0.82, col = OCHRE) {
  c.fillStyle = col; c.fillRect(x, y + h * g, w, h * (1 - g));
  c.fillStyle = INK; c.fillRect(x, y + h * g - 1.5, w, 3);
}
function disc(c: C, x: number, y: number, r: number, fill: string, stroke = true, lw = 3) {
  c.beginPath(); c.arc(x, y, r, 0, TAU); c.fillStyle = fill; c.fill(); if (stroke) { c.lineWidth = lw; c.strokeStyle = INK; c.stroke(); }
}
function poly(c: C, pts: number[][], fill: string | null, stroke = true, lw = 3) {
  c.beginPath(); pts.forEach(([a, b], i) => (i ? c.lineTo(a, b) : c.moveTo(a, b))); c.closePath();
  if (fill) { c.fillStyle = fill; c.fill(); }
  if (stroke) { c.lineWidth = lw; c.strokeStyle = INK; c.lineJoin = "round"; c.stroke(); }
}
function rrect(c: C, x: number, y: number, w: number, h: number, r: number) {
  c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
function text(c: C, t: string, x: number, y: number, size: number, col = INK, font = DISPLAY, weight = "800", maxW = 0) {
  c.font = `${weight} ${size}px ${font}`;
  if (maxW) { const w = c.measureText(t).width; if (w > maxW) { size *= maxW / w; c.font = `${weight} ${size}px ${font}`; } }
  c.fillStyle = col; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(t, x, y); c.textAlign = "left";
}

/** Draw figure f in pose p into the box (x, y, w, h). */
export function drawFigure(c: C, f: Figure, p: number, x: number, y: number, w: number, h: number, d: FigData) {
  c.save();
  c.beginPath(); c.rect(x, y, w, h); c.clip();
  const m = Math.min(w, h), cx = x + w / 2, cy = y + h / 2;
  const legacy = (motif: StripSpec["motif"], extra: Partial<StripSpec> = {}) =>
    drawFrame(c, { motif, label: d.label || "", number: d.number, maker: d.maker, device: d.device, img: d.img, art: d.art, tag: motif === "coin" ? d.tag : undefined, ...extra }, Math.round(p * 12) % 12, x, y, w, h);
  switch (f) {
    case "ball": case "bird": case "walker": case "turn": case "quote": case "coin": case "sun": case "pan": case "art": case "picture": case "question":
      legacy(f); break;

    case "bulb": {
      c.fillStyle = NIGHT; c.fillRect(x, y, w, h);
      const g = 0.55 + 0.45 * Math.cos(TAU * p);
      const R = m * 0.2, by = cy - m * 0.04;
      const halo = c.createRadialGradient(cx, by, R * 0.4, cx, by, R * 3.2);
      halo.addColorStop(0, `rgba(255, 226, 120, ${0.85 * g})`); halo.addColorStop(1, "rgba(255, 226, 120, 0)");
      c.fillStyle = halo; c.fillRect(x, y, w, h);
      c.save(); c.translate(cx, by); c.rotate(p * (TAU / 10));
      c.strokeStyle = `rgba(255, 220, 110, ${0.4 + 0.6 * g})`; c.lineWidth = 5; c.lineCap = "round";
      for (let i = 0; i < 10; i++) { const a = (i / 10) * TAU; c.beginPath(); c.moveTo(Math.cos(a) * R * 1.55, Math.sin(a) * R * 1.55); c.lineTo(Math.cos(a) * R * (2.1 + 0.3 * g), Math.sin(a) * R * (2.1 + 0.3 * g)); c.stroke(); }
      c.restore();
      disc(c, cx, by, R, `rgb(${Math.round(240 + 15 * g)}, ${Math.round(220 + 20 * g)}, ${Math.round(150 + 60 * g)})`);
      c.fillStyle = "#b9b4a6"; c.fillRect(cx - R * 0.45, by + R * 0.85, R * 0.9, R * 0.55);
      c.strokeStyle = INK; c.lineWidth = 3; c.strokeRect(cx - R * 0.45, by + R * 0.85, R * 0.9, R * 0.55);
      for (let i = 1; i < 3; i++) { c.beginPath(); c.moveTo(cx - R * 0.45, by + R * (0.85 + i * 0.18)); c.lineTo(cx + R * 0.45, by + R * (0.85 + i * 0.18)); c.stroke(); }
      c.strokeStyle = g > 0.5 ? RED : INK; c.lineWidth = 3;
      c.beginPath(); c.moveTo(cx - R * 0.3, by + R * 0.4); for (let i = 0; i <= 6; i++) c.lineTo(cx - R * 0.3 + i * R * 0.1, by + (i % 2 ? -0.05 : 0.1) * R); c.lineTo(cx + R * 0.3, by + R * 0.4); c.stroke();
      break;
    }
    case "magnifier": {
      c.fillStyle = PAPER; c.fillRect(x, y, w, h);
      const r = rng(d.number * 7 + 3), lines: number[][] = [];
      for (let i = 0; i < 7; i++) lines.push([x + w * 0.12, y + h * (0.2 + i * 0.1), w * (0.5 + r() * 0.26)]);
      const drawLines = (s = 1, col = "rgba(27,22,17,.55)") => { c.fillStyle = col; for (const [lx, ly, lw] of lines) { rrect(c, lx, ly - 4 * s, lw, 8 * s, 4 * s); c.fill(); } };
      drawLines();
      const t = tri(p), lx = x + w * (0.3 + 0.4 * t), ly = y + h * (0.42 + 0.08 * Math.sin(TAU * p)), R = m * 0.19;
      c.save(); c.beginPath(); c.arc(lx, ly, R, 0, TAU); c.clip();
      c.fillStyle = "#fff8e6"; c.fillRect(x, y, w, h);
      c.translate(lx, ly); c.scale(1.7, 1.7); c.translate(-lx, -ly); drawLines(1, RED); c.restore();
      c.save(); c.translate(lx, ly); c.rotate(0.75);
      c.fillStyle = INK; rrect(c, R * 0.95, -R * 0.13, R * 1.3, R * 0.26, R * 0.1); c.fill();
      c.restore();
      c.beginPath(); c.arc(lx, ly, R, 0, TAU); c.lineWidth = 8; c.strokeStyle = GOLD; c.stroke(); c.lineWidth = 2.5; c.strokeStyle = INK; c.stroke();
      c.strokeStyle = "rgba(255,255,255,.7)"; c.lineWidth = 4; c.beginPath(); c.arc(lx, ly, R * 0.7, -2.4, -1.6); c.stroke();
      break;
    }
    case "door": {
      c.fillStyle = "#c9b48c"; c.fillRect(x, y, w, h);
      for (let i = 0; i < 6; i++) { c.fillStyle = i % 2 ? "rgba(0,0,0,.04)" : "rgba(255,255,255,.05)"; c.fillRect(x + i * w / 6, y, w / 6, h); }
      ground(c, x, y, w, h, 0.84, "#8b5a2b");
      const dw = w * 0.36, dh = h * 0.6, dx = cx - dw / 2, dy = y + h * 0.84 - dh;
      c.fillStyle = "#fff2b8"; c.fillRect(dx, dy, dw, dh);
      const a = (0.15 + 0.85 * tri(p)) * 1.25, ow = dw * Math.cos(a), skew = dh * 0.12 * Math.sin(a);
      // light on the floor
      c.fillStyle = `rgba(255, 236, 160, ${0.75 * Math.sin(a)})`;
      poly(c, [[dx, dy + dh], [dx + dw, dy + dh], [dx + dw + w * 0.18 * Math.sin(a), y + h], [dx - w * 0.12 * Math.sin(a), y + h]], `rgba(255, 236, 160, ${0.7 * Math.sin(a)})`, false);
      c.lineWidth = 6; c.strokeStyle = INK; c.strokeRect(dx - 3, dy - 3, dw + 6, dh + 3);
      poly(c, [[dx, dy], [dx + ow, dy - skew], [dx + ow, dy + dh + skew], [dx, dy + dh]], RED);
      poly(c, [[dx + ow * 0.18, dy + dh * 0.1], [dx + ow * 0.82, dy + dh * 0.08 - skew * 0.6], [dx + ow * 0.82, dy + dh * 0.45 - skew * 0.2], [dx + ow * 0.18, dy + dh * 0.45]], null, true, 2);
      disc(c, dx + ow * 0.86, dy + dh * 0.55, 6, GOLD, true, 2);
      break;
    }
    case "key": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      rrect(c, x + w * 0.12, cy - h * 0.3, w * 0.34, h * 0.6, 14); c.fillStyle = GOLD; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      disc(c, x + w * 0.29, cy - h * 0.04, m * 0.05, INK, false); poly(c, [[x + w * 0.27, cy], [x + w * 0.31, cy], [x + w * 0.33, cy + h * 0.12], [x + w * 0.25, cy + h * 0.12]], INK, false);
      const rot = tri(p) * (Math.PI / 2), sy = Math.max(0.12, Math.cos(rot));
      c.fillStyle = INK; c.fillRect(x + w * 0.29, cy - 5, w * 0.36, 10);
      c.save(); c.translate(x + w * 0.72, cy); c.scale(1, sy);
      disc(c, 0, 0, m * 0.11, RED); disc(c, 0, 0, m * 0.045, SKY);
      c.restore();
      if (tri(p) > 0.9) { c.strokeStyle = RED; c.lineWidth = 3; for (const a of [-0.6, 0, 0.6]) { c.beginPath(); c.moveTo(x + w * 0.29 + Math.cos(a - 1.57) * m * 0.2, cy - h * 0.04 + Math.sin(a - 1.57) * m * 0.2); c.lineTo(x + w * 0.29 + Math.cos(a - 1.57) * m * 0.28, cy - h * 0.04 + Math.sin(a - 1.57) * m * 0.28); c.stroke(); } }
      break;
    }
    case "scales": {
      c.fillStyle = PAPER; c.fillRect(x, y, w, h);
      ground(c, x, y, w, h, 0.88, PAPER2);
      poly(c, [[cx - m * 0.12, y + h * 0.88], [cx + m * 0.12, y + h * 0.88], [cx + m * 0.03, y + h * 0.3], [cx - m * 0.03, y + h * 0.3]], GOLD);
      const a = Math.sin(TAU * p + 0.6) * 0.26, L = w * 0.36, py = y + h * 0.3;
      const ex = Math.cos(a) * L, ey = Math.sin(a) * L;
      c.lineWidth = 7; c.strokeStyle = INK; c.lineCap = "round"; c.beginPath(); c.moveTo(cx - ex, py - ey); c.lineTo(cx + ex, py + ey); c.stroke();
      disc(c, cx, py, 9, RED);
      for (const [sx, sy, col] of [[cx - ex, py - ey, RED], [cx + ex, py + ey, BLUE]] as const) {
        c.lineWidth = 2; c.beginPath(); c.moveTo(sx, sy); c.lineTo(sx - m * 0.1, sy + h * 0.26); c.moveTo(sx, sy); c.lineTo(sx + m * 0.1, sy + h * 0.26); c.stroke();
        poly(c, [[sx - m * 0.13, sy + h * 0.26], [sx + m * 0.13, sy + h * 0.26], [sx + m * 0.08, sy + h * 0.31], [sx - m * 0.08, sy + h * 0.31]], GOLD);
        if (col === RED) { c.fillStyle = RED; c.fillRect(sx - m * 0.05, sy + h * 0.26 - m * 0.1, m * 0.1, m * 0.1); c.strokeRect(sx - m * 0.05, sy + h * 0.26 - m * 0.1, m * 0.1, m * 0.1); }
        else disc(c, sx, sy + h * 0.26 - m * 0.055, m * 0.055, BLUE);
      }
      break;
    }
    case "spring": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      ground(c, x, y, w, h, 0.86);
      const bx = cx - m * 0.18, bw = m * 0.36, bh = m * 0.26, by = y + h * 0.86 - bh;
      c.fillStyle = RED; c.fillRect(bx, by, bw, bh); c.lineWidth = 3; c.strokeStyle = INK; c.strokeRect(bx, by, bw, bh);
      text(c, "★", cx, by + bh / 2, bh * 0.5, GOLD, DISPLAY, "400");
      const up = Math.sin(Math.PI * ((p + 0.3) % 1)), land = up < 0.15;
      const hy = by - m * 0.08 - up * h * 0.38;
      c.strokeStyle = INK; c.lineWidth = 3; c.beginPath(); c.moveTo(cx, by);
      const n = 8; for (let i = 1; i <= n; i++) c.lineTo(cx + (i % 2 ? 1 : -1) * m * 0.07, by + (hy + m * 0.1 - by) * (i / n));
      c.stroke();
      c.save(); c.translate(cx, hy); c.scale(land ? 1.2 : 1, land ? 0.82 : 1.05);
      disc(c, 0, 0, m * 0.11, GOLD); disc(c, -m * 0.035, -m * 0.02, m * 0.015, INK, false); disc(c, m * 0.035, -m * 0.02, m * 0.015, INK, false);
      c.beginPath(); c.arc(0, m * 0.02, m * 0.04, 0.2, Math.PI - 0.2); c.lineWidth = 2.5; c.stroke();
      c.restore();
      poly(c, [[bx, by], [bx - m * 0.12, by - m * 0.2], [bx - m * 0.1, by - m * 0.23], [bx + 2, by - 2]], BLUE);
      break;
    }
    case "plane": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      for (let i = 0; i < 3; i++) { const ox = ((i / 3 + p) % 1) * (w + 120) - 60; disc(c, x + ox, y + h * (0.2 + i * 0.25), m * 0.05, "#fff", false); disc(c, x + ox + m * 0.06, y + h * (0.2 + i * 0.25) - 6, m * 0.06, "#fff", false); }
      const a = TAU * p, R = m * 0.3;
      const px = cx + Math.cos(a) * R, py = cy + Math.sin(a) * R * 0.75;
      for (let i = 1; i < 9; i++) { const b = a - i * 0.14; disc(c, cx + Math.cos(b) * R, cy + Math.sin(b) * R * 0.75, 4 - i * 0.35, "rgba(43,80,121,.6)", false); }
      const head = Math.atan2(Math.cos(a) * 0.75, -Math.sin(a));
      c.save(); c.translate(px, py); c.rotate(head);
      const L = m * 0.14;
      poly(c, [[L, 0], [-L, -L * 0.7], [-L * 0.5, 0], [-L, L * 0.35]], "#fffaf0");
      c.beginPath(); c.moveTo(L, 0); c.lineTo(-L * 0.5, 0); c.lineWidth = 2; c.strokeStyle = RED; c.stroke();
      c.restore();
      break;
    }
    case "clock": {
      c.fillStyle = PAPER2; c.fillRect(x, y, w, h);
      const R = m * 0.36, ccy = cy - (d.value ? m * 0.06 : 0);
      disc(c, cx, ccy, R + 10, INK, false); disc(c, cx, ccy, R, "#fbf3df");
      for (let i = 0; i < 12; i++) { const a = (i / 12) * TAU; c.lineWidth = i % 3 ? 2 : 5; c.strokeStyle = INK; c.beginPath(); c.moveTo(cx + Math.sin(a) * R * 0.82, ccy - Math.cos(a) * R * 0.82); c.lineTo(cx + Math.sin(a) * R * 0.94, ccy - Math.cos(a) * R * 0.94); c.stroke(); }
      for (const [n, a] of [["12", 0], ["3", 0.25], ["6", 0.5], ["9", 0.75]] as const) text(c, n, cx + Math.sin(a * TAU) * R * 0.66, ccy - Math.cos(a * TAU) * R * 0.66, R * 0.2);
      const ha = TAU * p;
      c.lineCap = "round"; c.strokeStyle = RED; c.lineWidth = 9; c.beginPath(); c.moveTo(cx, ccy); c.lineTo(cx + Math.sin(ha) * R * 0.5, ccy - Math.cos(ha) * R * 0.5); c.stroke();
      c.strokeStyle = INK; c.lineWidth = 5; c.beginPath(); c.moveTo(cx, ccy); c.lineTo(cx, ccy - R * 0.78); c.stroke();
      disc(c, cx, ccy, 8, GOLD);
      if (d.value) { c.fillStyle = INK; rrect(c, cx - m * 0.2, y + h * 0.84, m * 0.4, m * 0.12, 6); c.fill(); text(c, `${d.value}${d.unit || ""}`, cx, y + h * 0.84 + m * 0.06, m * 0.08, "#fff8e6", SLAB, "400", m * 0.36); }
      break;
    }
    case "hourglass": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      const flip = p > 0.84 ? (p - 0.84) / 0.16 : 0, t = p > 0.84 ? 1 : p / 0.84;
      c.save(); c.translate(cx, cy); c.rotate(flip * Math.PI);
      const H = m * 0.36, W = m * 0.22;
      c.fillStyle = "#8b5a2b"; c.fillRect(-W * 1.3, -H - 14, W * 2.6, 14); c.fillRect(-W * 1.3, H, W * 2.6, 14);
      c.fillStyle = "rgba(255,255,255,.55)"; poly(c, [[-W, -H], [W, -H], [6, 0], [W, H], [-W, H], [-6, 0]], "rgba(255,255,255,.55)");
      const top = 1 - t;
      if (flip === 0) {
        c.fillStyle = OCHRE;
        const ty = -H * 0.05 - (H * 0.9) * top; poly(c, [[-W * (0.1 + 0.8 * top), ty], [W * (0.1 + 0.8 * top), ty], [4, -2], [-4, -2]], OCHRE, false);
        const bh = H * 0.85 * t; poly(c, [[-W * 0.95, H], [W * 0.95, H], [W * 0.95 * (1 - bh / H * 0.6), H - bh], [-W * 0.95 * (1 - bh / H * 0.6), H - bh]], OCHRE, false);
        c.fillStyle = OCHRE; c.fillRect(-1.5, 0, 3, H - bh);
      } else { c.fillStyle = OCHRE; poly(c, [[-W * 0.95, H], [W * 0.95, H], [W * 0.4, H * 0.15], [-W * 0.4, H * 0.15]], OCHRE, false); }
      c.lineWidth = 3; c.strokeStyle = INK; poly(c, [[-W, -H], [W, -H], [6, 0], [W, H], [-W, H], [-6, 0]], null);
      c.restore();
      break;
    }
    case "metronome": {
      c.fillStyle = PAPER; c.fillRect(x, y, w, h);
      const bh = m * 0.62, bw = m * 0.42, by = y + h * 0.9;
      poly(c, [[cx - bw / 2, by], [cx + bw / 2, by], [cx + bw * 0.14, by - bh], [cx - bw * 0.14, by - bh]], "#8b5a2b");
      poly(c, [[cx - bw * 0.3, by - bh * 0.15], [cx + bw * 0.3, by - bh * 0.15], [cx + bw * 0.1, by - bh * 0.85], [cx - bw * 0.1, by - bh * 0.85]], PAPER2, true, 2);
      const a = Math.sin(TAU * p + 1.57) * 0.42, px = cx, py = by - bh * 0.18, L = bh * 0.75;
      c.lineWidth = 5; c.strokeStyle = INK; c.lineCap = "round"; c.beginPath(); c.moveTo(px, py); c.lineTo(px + Math.sin(a) * L, py - Math.cos(a) * L); c.stroke();
      c.save(); c.translate(px + Math.sin(a) * L * 0.62, py - Math.cos(a) * L * 0.62); c.rotate(a); c.fillStyle = GOLD; c.fillRect(-12, -9, 24, 18); c.lineWidth = 2.5; c.strokeRect(-12, -9, 24, 18); c.restore();
      disc(c, px, py, 7, RED);
      break;
    }
    case "windmill": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      c.fillStyle = "#9cb37a"; c.beginPath(); c.ellipse(x + w * 0.2, y + h, w * 0.5, h * 0.22, 0, 0, TAU); c.fill(); c.beginPath(); c.ellipse(x + w * 0.9, y + h, w * 0.5, h * 0.18, 0, 0, TAU); c.fill();
      const tx = cx, ty = cy - m * 0.06;
      poly(c, [[tx - m * 0.12, y + h * 0.94], [tx + m * 0.12, y + h * 0.94], [tx + m * 0.06, ty], [tx - m * 0.06, ty]], RED);
      c.fillStyle = INK; c.fillRect(tx - 8, y + h * 0.8, 16, h * 0.14);
      c.save(); c.translate(tx, ty); c.rotate(p * (Math.PI / 2));
      for (let i = 0; i < 4; i++) {
        c.rotate(Math.PI / 2);
        c.fillStyle = INK; c.fillRect(-3, 0, 6, m * 0.36);
        poly(c, [[4, m * 0.08], [m * 0.1, m * 0.08], [m * 0.1, m * 0.36], [4, m * 0.36]], "#fff8e6", true, 2);
        c.strokeStyle = INK; c.lineWidth = 1; for (let k = 1; k < 4; k++) { c.beginPath(); c.moveTo(4, m * (0.08 + k * 0.07)); c.lineTo(m * 0.1, m * (0.08 + k * 0.07)); c.stroke(); }
      }
      c.restore(); disc(c, tx, ty, 8, GOLD);
      break;
    }
    case "heart": {
      c.fillStyle = "#f3d9c9"; c.fillRect(x, y, w, h);
      const beat = Math.max(0, Math.sin(TAU * p * 2)) ** 3;
      const s = m * 0.012 * (1 + 0.16 * beat), hx = cx, hy = cy - m * 0.08;
      c.save(); c.translate(hx, hy); c.scale(s, s);
      c.beginPath(); c.moveTo(0, 12); c.bezierCurveTo(-26, -6, -14, -24, 0, -12); c.bezierCurveTo(14, -24, 26, -6, 0, 12); c.closePath();
      c.fillStyle = RED; c.fill(); c.lineWidth = 3 / s * 0.9; c.strokeStyle = INK; c.stroke();
      c.restore();
      const ly = y + h * 0.82; c.strokeStyle = INK; c.lineWidth = 3; c.beginPath();
      for (let i = 0; i <= 60; i++) { const u = i / 60, ph = (u + p) % 1; const v = ph > 0.45 && ph < 0.55 ? Math.sin((ph - 0.45) / 0.1 * TAU) * h * 0.08 : 0; const X = x + w * 0.08 + u * w * 0.84; if (i) c.lineTo(X, ly - v); else c.moveTo(X, ly - v); }
      c.stroke();
      break;
    }
    case "juggler": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      ground(c, x, y, w, h, 0.9);
      const by = y + h * 0.9;
      c.fillStyle = INK; c.strokeStyle = INK; c.lineCap = "round"; c.lineWidth = 9;
      c.beginPath(); c.moveTo(cx - m * 0.06, by); c.lineTo(cx, by - m * 0.2); c.lineTo(cx + m * 0.06, by); c.stroke();
      poly(c, [[cx - m * 0.08, by - m * 0.2], [cx + m * 0.08, by - m * 0.2], [cx + m * 0.06, by - m * 0.42], [cx - m * 0.06, by - m * 0.42]], RED, true, 2);
      disc(c, cx, by - m * 0.48, m * 0.06, "#f2d3b0");
      const hand = (s: number) => [cx + s * m * 0.16, by - m * 0.36];
      c.lineWidth = 6; for (const s of [-1, 1]) { const [hx, hy] = hand(s); c.beginPath(); c.moveTo(cx + s * m * 0.06, by - m * 0.38); c.lineTo(hx, hy); c.stroke(); }
      const cols = [RED, BLUE, GOLD];
      for (let i = 0; i < 3; i++) {
        const q = (p + i / 3) % 1, side = q < 0.5 ? 1 : -1, u = (q % 0.5) / 0.5;
        const x0 = cx - side * m * 0.16, x1 = cx + side * m * 0.16;
        const bxp = x0 + (x1 - x0) * u, byp = by - m * 0.38 - Math.sin(Math.PI * u) * m * 0.4;
        disc(c, bxp, byp, m * 0.045, cols[i]);
      }
      break;
    }
    case "rocket": {
      c.fillStyle = NIGHT; c.fillRect(x, y, w, h);
      const r = rng(d.number + 11);
      for (let i = 0; i < 26; i++) { const sx = x + r() * w, sy = y + ((r() + p) % 1) * h; c.fillStyle = "rgba(255,248,220,.8)"; c.fillRect(sx, sy, 2, 2 + 10 * 0.6); }
      const bob = Math.sin(TAU * p) * m * 0.03, ry = cy + bob;
      const fl = 0.8 + 0.2 * Math.sin(TAU * p * 3);
      poly(c, [[cx - m * 0.06, ry + m * 0.2], [cx + m * 0.06, ry + m * 0.2], [cx, ry + m * (0.2 + 0.22 * fl)]], GOLD, false);
      poly(c, [[cx - m * 0.03, ry + m * 0.2], [cx + m * 0.03, ry + m * 0.2], [cx, ry + m * (0.2 + 0.12 * fl)]], RED, false);
      poly(c, [[cx - m * 0.09, ry + m * 0.2], [cx - m * 0.16, ry + m * 0.24], [cx - m * 0.09, ry + m * 0.05]], RED);
      poly(c, [[cx + m * 0.09, ry + m * 0.2], [cx + m * 0.16, ry + m * 0.24], [cx + m * 0.09, ry + m * 0.05]], RED);
      c.beginPath(); c.moveTo(cx, ry - m * 0.3); c.quadraticCurveTo(cx + m * 0.12, ry - m * 0.1, cx + m * 0.09, ry + m * 0.2); c.lineTo(cx - m * 0.09, ry + m * 0.2); c.quadraticCurveTo(cx - m * 0.12, ry - m * 0.1, cx, ry - m * 0.3); c.closePath();
      c.fillStyle = "#fbf3df"; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      disc(c, cx, ry - m * 0.06, m * 0.045, BLUE);
      break;
    }
    case "calendar": {
      c.fillStyle = PAPER2; c.fillRect(x, y, w, h);
      const pw = m * 0.56, ph = m * 0.62, px = cx - pw / 2, py = cy - ph / 2 + m * 0.03;
      const day = (Math.round(p * 12) % 12) + 1, prev = day === 1 ? 12 : day - 1;
      c.fillStyle = INK; c.fillRect(px, py - m * 0.06, pw, m * 0.12);
      const page = (n: number) => { c.fillStyle = "#fffaf0"; c.fillRect(0, 0, pw, ph); c.fillStyle = RED; c.fillRect(0, 0, pw, ph * 0.22); c.lineWidth = 3; c.strokeStyle = INK; c.strokeRect(0, 0, pw, ph);
        text(c, "DAY", pw / 2, ph * 0.11, ph * 0.12, "#fff8e6", SLAB, "400"); text(c, String(n), pw / 2, ph * 0.6, ph * 0.46); };
      c.save(); c.translate(px, py); page(day); c.restore();
      c.save(); c.translate(px + pw * 0.62, py + ph * 0.5); c.rotate(0.5); c.translate(-pw / 2, -ph / 2); c.globalAlpha = 0.9; page(prev); c.restore();
      for (let i = 0; i < 5; i++) disc(c, px + pw * (0.15 + i * 0.175), py - m * 0.01, 4, GOLD, false);
      break;
    }
    case "envelope": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      const t = tri(p), open = Math.min(1, t * 2), rise = Math.max(0, t * 2 - 1);
      const ew = m * 0.62, eh = m * 0.4, ex = cx - ew / 2, ey = cy - eh / 2 + m * 0.12;
      const ly = ey + eh * 0.15 - rise * eh * 0.75;
      c.fillStyle = "#fffaf0"; c.fillRect(ex + ew * 0.08, ly, ew * 0.84, eh * 0.8); c.lineWidth = 2; c.strokeStyle = INK; c.strokeRect(ex + ew * 0.08, ly, ew * 0.84, eh * 0.8);
      for (let i = 0; i < 3; i++) { c.fillStyle = "rgba(27,22,17,.5)"; c.fillRect(ex + ew * 0.16, ly + eh * (0.16 + i * 0.13), ew * (0.6 - i * 0.12), 5); }
      poly(c, [[ex, ey], [ex + ew, ey], [ex + ew, ey + eh], [ex, ey + eh]], RED);
      poly(c, [[ex, ey + eh], [cx, ey + eh * 0.45], [ex + ew, ey + eh]], "#b13a22", true, 2);
      const fy = ey + eh * 0.55 * (1 - 2 * open);
      poly(c, [[ex, ey], [cx, fy], [ex + ew, ey]], open > 0.5 ? "#a8331d" : "#d24b30", true, 2.5);
      disc(c, cx, ey + (fy - ey) * 0.75, 8, GOLD, true, 2);
      break;
    }
    case "gears": {
      c.fillStyle = PAPER; c.fillRect(x, y, w, h);
      const gear = (gx: number, gy: number, r: number, teeth: number, rot: number, col: string) => {
        c.save(); c.translate(gx, gy); c.rotate(rot); c.beginPath();
        for (let i = 0; i < teeth * 2; i++) { const a0 = (i / (teeth * 2)) * TAU, a1 = ((i + 1) / (teeth * 2)) * TAU, rr = i % 2 ? r : r * 1.16; c.arc(0, 0, rr, a0, a1); }
        c.closePath(); c.fillStyle = col; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
        disc(c, 0, 0, r * 0.35, PAPER); disc(c, 0, 0, r * 0.12, INK, false);
        for (let i = 0; i < 4; i++) { c.rotate(Math.PI / 2); c.fillStyle = INK; c.fillRect(r * 0.36, -3, r * 0.5, 6); }
        c.restore();
      };
      const R1 = m * 0.26, R2 = m * 0.17;
      gear(cx - m * 0.12, cy + m * 0.02, R1, 12, p * (TAU / 12), RED);
      gear(cx - m * 0.12 + R1 + R2 + m * 0.02, cy - m * 0.12, R2, 8, -p * (TAU / 8) + Math.PI / 8, BLUE);
      break;
    }
    case "top": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      ground(c, x, y, w, h, 0.84, PAPER2);
      const g = y + h * 0.84, tilt = Math.sin(TAU * p) * 0.18;
      c.fillStyle = "rgba(27,22,17,.25)"; c.beginPath(); c.ellipse(cx, g + 4, m * 0.16, m * 0.03, 0, 0, TAU); c.fill();
      c.save(); c.translate(cx, g); c.rotate(tilt);
      const R = m * 0.24;
      c.beginPath(); c.moveTo(0, 0); c.lineTo(-R, -R * 0.9); c.quadraticCurveTo(0, -R * 1.5, R, -R * 0.9); c.closePath(); c.fillStyle = GOLD; c.fill();
      c.save(); c.clip(); for (let i = -3; i < 6; i++) { c.fillStyle = i % 2 ? RED : BLUE; c.fillRect(-R + ((i / 3 + p) % 2) * R, -R * 1.5, R * 0.33, R * 1.6); } c.restore();
      c.beginPath(); c.moveTo(0, 0); c.lineTo(-R, -R * 0.9); c.quadraticCurveTo(0, -R * 1.5, R, -R * 0.9); c.closePath(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      c.fillStyle = INK; c.fillRect(-4, -R * 1.62, 8, R * 0.38);
      c.restore();
      c.strokeStyle = "rgba(27,22,17,.5)"; c.lineWidth = 2; for (const s of [-1, 1]) { c.beginPath(); c.arc(cx, g - m * 0.22, m * 0.32, s > 0 ? -0.3 : Math.PI - 0.3, s > 0 ? 0.3 : Math.PI + 0.3); c.stroke(); }
      break;
    }
    case "waves": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      disc(c, x + w * 0.78, y + h * 0.22, m * 0.08, GOLD, false);
      const wave = (base: number, amp: number, col: string, ph: number) => {
        c.beginPath(); c.moveTo(x, y + h);
        for (let i = 0; i <= 40; i++) { const u = i / 40; c.lineTo(x + u * w, y + h * base - Math.sin((u * 2 + p + ph) * TAU) * amp); }
        c.lineTo(x + w, y + h); c.closePath(); c.fillStyle = col; c.fill(); c.lineWidth = 2.5; c.strokeStyle = INK; c.stroke();
      };
      wave(0.6, m * 0.03, "#7ea3c4", 0.3);
      const by = y + h * 0.62 - Math.sin((1 + p + 0.3) * TAU) * m * 0.03, tilt = Math.cos((1 + p + 0.3) * TAU) * 0.18;
      c.save(); c.translate(cx, by); c.rotate(tilt);
      poly(c, [[-m * 0.16, -m * 0.02], [m * 0.16, -m * 0.02], [m * 0.1, m * 0.06], [-m * 0.1, m * 0.06]], RED);
      c.fillStyle = INK; c.fillRect(-2, -m * 0.26, 4, m * 0.24); poly(c, [[3, -m * 0.25], [m * 0.13, -m * 0.06], [3, -m * 0.06]], "#fffaf0", true, 2);
      c.restore();
      wave(0.72, m * 0.04, BLUE, 0);
      break;
    }
    case "butterfly": {
      c.fillStyle = "#e4ead2"; c.fillRect(x, y, w, h);
      for (let i = 0; i < 3; i++) { const fx = x + w * (0.2 + i * 0.3), fy = y + h * 0.88; c.strokeStyle = "#5b7a3a"; c.lineWidth = 3; c.beginPath(); c.moveTo(fx, y + h); c.lineTo(fx, fy); c.stroke(); for (let k = 0; k < 5; k++) disc(c, fx + Math.cos(k * 1.26) * 9, fy + Math.sin(k * 1.26) * 9, 6, i % 2 ? RED : GOLD, false); }
      const flap = 0.2 + 0.8 * Math.abs(Math.cos(TAU * p)), bob = Math.sin(TAU * p) * m * 0.03;
      c.save(); c.translate(cx, cy - m * 0.06 + bob);
      for (const s of [-1, 1]) {
        c.save(); c.scale(s * flap, 1);
        c.beginPath(); c.ellipse(m * 0.12, -m * 0.08, m * 0.12, m * 0.1, -0.4, 0, TAU); c.fillStyle = BLUE; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
        c.beginPath(); c.ellipse(m * 0.09, m * 0.07, m * 0.08, m * 0.07, 0.4, 0, TAU); c.fillStyle = RED; c.fill(); c.stroke();
        disc(c, m * 0.13, -m * 0.09, m * 0.03, GOLD, false);
        c.restore();
      }
      c.fillStyle = INK; c.beginPath(); c.ellipse(0, 0, m * 0.018, m * 0.11, 0, 0, TAU); c.fill();
      c.restore();
      break;
    }
    case "fish": {
      c.fillStyle = "#cfe0e6"; c.fillRect(x, y, w, h);
      for (let i = 0; i < 6; i++) { const bx = x + w * (0.2 + (i % 3) * 0.12), by = y + h * (1 - ((i / 6 + p) % 1)); c.beginPath(); c.arc(bx, by, 4 + (i % 3) * 2, 0, TAU); c.lineWidth = 2; c.strokeStyle = BLUE; c.stroke(); }
      c.fillStyle = "#5b7a3a"; for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(x + w * (0.65 + i * 0.1), y + h); c.quadraticCurveTo(x + w * (0.6 + i * 0.1) + Math.sin(TAU * p + i) * 12, y + h * 0.7, x + w * (0.66 + i * 0.1), y + h * 0.55); c.lineWidth = 6; c.strokeStyle = "#5b7a3a"; c.stroke(); }
      const tail = Math.sin(TAU * p * 2) * 0.45, fx = cx + Math.sin(TAU * p) * m * 0.05, fy = cy;
      c.save(); c.translate(fx, fy);
      c.save(); c.translate(-m * 0.16, 0); c.rotate(tail); poly(c, [[0, 0], [-m * 0.13, -m * 0.09], [-m * 0.13, m * 0.09]], RED); c.restore();
      c.beginPath(); c.ellipse(0, 0, m * 0.18, m * 0.1, 0, 0, TAU); c.fillStyle = OCHRE; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      disc(c, m * 0.09, -m * 0.02, m * 0.025, "#fff", true, 2); disc(c, m * 0.095, -m * 0.02, m * 0.011, INK, false);
      c.restore();
      break;
    }
    case "bell": {
      c.fillStyle = PAPER2; c.fillRect(x, y, w, h);
      const a = Math.sin(TAU * p) * 0.4, pivotY = y + h * 0.14;
      c.fillStyle = "#8b5a2b"; c.fillRect(cx - m * 0.3, pivotY - 10, m * 0.6, 12);
      c.save(); c.translate(cx, pivotY); c.rotate(a);
      const ca = -a * 0.6;
      c.save(); c.rotate(ca); c.strokeStyle = INK; c.lineWidth = 4; c.beginPath(); c.moveTo(0, m * 0.1); c.lineTo(0, m * 0.5); c.stroke(); disc(c, 0, m * 0.52, m * 0.045, RED); c.restore();
      c.beginPath(); c.moveTo(-m * 0.08, m * 0.06); c.quadraticCurveTo(-m * 0.12, m * 0.3, -m * 0.24, m * 0.46); c.lineTo(m * 0.24, m * 0.46); c.quadraticCurveTo(m * 0.12, m * 0.3, m * 0.08, m * 0.06); c.closePath();
      c.fillStyle = GOLD; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      c.restore();
      if (Math.abs(Math.sin(TAU * p)) > 0.85) { c.strokeStyle = RED; c.lineWidth = 3; const s = Math.sign(Math.sin(TAU * p)); for (let i = 1; i <= 2; i++) { c.beginPath(); c.arc(cx + s * m * 0.3, y + h * 0.55, m * 0.06 * i, -0.8, 0.8); c.stroke(); } }
      break;
    }
    case "kite": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      const sway = Math.sin(TAU * p) * 0.22, kx = cx + Math.sin(TAU * p) * m * 0.06, ky = cy - m * 0.12;
      c.strokeStyle = INK; c.lineWidth = 1.5; c.beginPath(); c.moveTo(kx, ky + m * 0.18); c.quadraticCurveTo(cx - m * 0.1, cy + m * 0.2, x + w * 0.2, y + h); c.stroke();
      c.save(); c.translate(kx, ky); c.rotate(sway);
      poly(c, [[0, -m * 0.2], [m * 0.14, 0], [0, m * 0.18], [-m * 0.14, 0]], RED);
      c.strokeStyle = INK; c.lineWidth = 2; c.beginPath(); c.moveTo(0, -m * 0.2); c.lineTo(0, m * 0.18); c.moveTo(-m * 0.14, 0); c.lineTo(m * 0.14, 0); c.stroke();
      poly(c, [[0, -m * 0.2], [m * 0.14, 0], [0, 0]], GOLD, true, 2);
      for (let i = 0; i < 5; i++) { const tx = Math.sin(TAU * p * 2 + i * 0.9) * m * 0.04, ty = m * (0.22 + i * 0.07); poly(c, [[tx - 7, ty], [tx + 7, ty - 5], [tx + 7, ty + 5]], i % 2 ? BLUE : GOLD, true, 1.5); }
      c.restore();
      break;
    }
    case "moon": {
      c.fillStyle = NIGHT; c.fillRect(x, y, w, h);
      const r = rng(d.number + 5); for (let i = 0; i < 30; i++) { c.fillStyle = "rgba(255,248,220,.75)"; const s = 1 + r() * 2; c.fillRect(x + r() * w, y + r() * h, s, s); }
      const R = m * 0.26, ph = (p + 0.5) % 1;   // pose 0 is the full moon
      disc(c, cx, cy, R, "#3a4a6a", false);
      c.save(); c.beginPath(); c.arc(cx, cy, R, 0, TAU); c.clip();
      const k = Math.cos(TAU * ph);   // 1 new, -1 full
      c.fillStyle = "#fbf0c8";
      c.beginPath();
      if (ph < 0.5) { c.arc(cx, cy, R, -Math.PI / 2, Math.PI / 2); c.ellipse(cx, cy, Math.abs(k) * R, R, 0, Math.PI / 2, -Math.PI / 2, k > 0); }
      else { c.arc(cx, cy, R, Math.PI / 2, -Math.PI / 2); c.ellipse(cx, cy, Math.abs(k) * R, R, 0, -Math.PI / 2, Math.PI / 2, k > 0); }
      c.fill(); c.restore();
      c.beginPath(); c.arc(cx, cy, R, 0, TAU); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      break;
    }
    case "dice": {
      c.fillStyle = "#2f5d3a"; c.fillRect(x, y, w, h);
      const hop = Math.abs(Math.sin(TAU * p)) * m * 0.12, rot = p * (Math.PI / 2);
      c.fillStyle = "rgba(0,0,0,.3)"; c.beginPath(); c.ellipse(cx, cy + m * 0.26, m * 0.18, m * 0.04, 0, 0, TAU); c.fill();
      c.save(); c.translate(cx, cy + m * 0.04 - hop); c.rotate(rot);
      const S = m * 0.3; rrect(c, -S / 2, -S / 2, S, S, S * 0.16); c.fillStyle = "#fffaf0"; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      for (const [a, b] of [[-1, -1], [1, -1], [0, 0], [-1, 1], [1, 1]]) disc(c, a * S * 0.27, b * S * 0.27, S * 0.08, a === 0 ? RED : INK, false);
      c.restore();
      break;
    }
    case "pie": {
      c.fillStyle = PAPER; c.fillRect(x, y, w, h);
      const v = Math.max(0, Math.min(100, parseFloat((d.value || "50").replace(/[^0-9.]/g, "")) || 50)) / 100;
      const f = v * (0.55 + 0.45 * Math.cos(TAU * p)), R = m * 0.3, py = cy - m * 0.06;
      disc(c, py ? cx : cx, py, R, "#fbf3df");
      c.beginPath(); c.moveTo(cx, py); c.arc(cx, py, R, -Math.PI / 2, -Math.PI / 2 + TAU * f); c.closePath(); c.fillStyle = RED; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      c.beginPath(); c.arc(cx, py, R, 0, TAU); c.stroke();
      text(c, `${d.value || ""}${d.unit || ""}`, cx, y + h * 0.88, m * 0.12, INK, DISPLAY, "800", w * 0.8);
      break;
    }
    case "counter": {
      c.fillStyle = PAPER2; c.fillRect(x, y, w, h);
      const val = (d.value || "0").slice(0, 6), n = Math.max(1, val.length);
      const cw = Math.min(w * 0.8 / n, m * 0.22), ch = cw * 1.5, x0 = cx - (cw * n) / 2, y0 = cy - ch / 2 - m * 0.04;
      c.fillStyle = INK; rrect(c, x0 - 12, y0 - 12, cw * n + 24, ch + 24, 10); c.fill();
      for (let i = 0; i < n; i++) {
        const ch0 = val[i], bx = x0 + i * cw;
        c.save(); c.beginPath(); c.rect(bx + 3, y0, cw - 6, ch); c.clip();
        c.fillStyle = "#fbf3df"; c.fillRect(bx + 3, y0, cw - 6, ch);
        if (/[0-9]/.test(ch0)) {
          const roll = ((+ch0 + p * 10) % 10), base = Math.floor(roll), frac = roll - base;
          for (let k = -1; k <= 1; k++) text(c, String((base + k + 10) % 10), bx + cw / 2, y0 + ch / 2 + (k - frac) * ch * -1 * -1 + 0, ch * 0.62, k === 0 && frac < 0.01 ? RED : INK);
        } else text(c, ch0, bx + cw / 2, y0 + ch / 2, ch * 0.6);
        c.restore();
      }
      c.fillStyle = "rgba(255,255,255,.25)"; c.fillRect(x0, y0, cw * n, ch * 0.16);
      if (d.unit) text(c, d.unit, cx, y0 + ch + m * 0.12, m * 0.09, RED, DISPLAY, "600");
      break;
    }
    case "tumbler": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      ground(c, x, y, w, h, 0.88, RED);
      const rot = TAU * p, hop = Math.sin(Math.PI * p) * m * 0.22, gy = y + h * 0.88;
      c.save(); c.translate(cx, gy - m * 0.24 - hop); c.rotate(rot);
      c.strokeStyle = INK; c.lineCap = "round"; c.lineWidth = 8;
      const tuck = Math.sin(Math.PI * p);
      c.beginPath(); c.moveTo(0, -m * 0.06); c.lineTo(0, m * 0.08); c.stroke();
      for (const s of [-1, 1]) { c.beginPath(); c.moveTo(0, m * 0.08); c.lineTo(s * m * 0.06, m * (0.2 - 0.08 * tuck)); c.lineTo(s * m * (0.05 - 0.07 * tuck), m * (0.26 - 0.1 * tuck)); c.stroke(); }
      c.lineWidth = 6; for (const s of [-1, 1]) { c.beginPath(); c.moveTo(0, -m * 0.04); c.lineTo(s * m * (0.12 - 0.06 * tuck), -m * (0.08 + 0.06 * (1 - tuck))); c.stroke(); }
      c.fillStyle = BLUE; c.fillRect(-m * 0.04, -m * 0.07, m * 0.08, m * 0.14);
      disc(c, 0, -m * 0.12, m * 0.05, "#f2d3b0");
      c.restore();
      break;
    }
    case "pen": {
      c.fillStyle = PAPER; c.fillRect(x, y, w, h);
      for (let i = 0; i < 5; i++) { c.fillStyle = "rgba(43,80,121,.18)"; c.fillRect(x + w * 0.08, y + h * (0.3 + i * 0.12), w * 0.84, 1.5); }
      const t = p === 0 ? 1 : p, pts: number[][] = [];
      for (let i = 0; i <= 80; i++) { const u = i / 80; pts.push([x + w * (0.12 + 0.76 * u), cy + Math.sin(u * 14) * m * 0.08 * (1 - u * 0.4) + Math.cos(u * 5) * m * 0.04]); }
      const n = Math.max(2, Math.round(pts.length * t));
      c.strokeStyle = BLUE; c.lineWidth = 4; c.lineCap = "round"; c.lineJoin = "round"; c.beginPath(); pts.slice(0, n).forEach(([a, b], i) => (i ? c.lineTo(a, b) : c.moveTo(a, b))); c.stroke();
      const [tx, ty] = pts[n - 1];
      c.save(); c.translate(tx, ty); c.rotate(-0.7);
      poly(c, [[0, 0], [m * 0.04, -m * 0.06], [m * 0.04, -m * 0.34], [-m * 0.04, -m * 0.34], [-m * 0.04, -m * 0.06]], INK, false);
      poly(c, [[0, 0], [m * 0.03, -m * 0.06], [-m * 0.03, -m * 0.06]], GOLD, true, 2);
      c.fillStyle = GOLD; c.fillRect(-m * 0.04, -m * 0.2, m * 0.08, m * 0.02);
      c.restore();
      break;
    }
    case "orbit": {
      c.fillStyle = NIGHT; c.fillRect(x, y, w, h);
      for (const [rr, n, col, sp] of [[0.18, 1, GOLD, 1], [0.29, 2, RED, -1], [0.4, 1, "#9fc0e0", 1]] as const) {
        c.strokeStyle = "rgba(255,248,220,.35)"; c.lineWidth = 1.5; c.beginPath(); c.ellipse(cx, cy, m * rr, m * rr * 0.62, 0, 0, TAU); c.stroke();
        for (let k = 0; k < n; k++) { const a = TAU * (p * sp + k / n + rr); disc(c, cx + Math.cos(a) * m * rr, cy + Math.sin(a) * m * rr * 0.62, m * 0.035, col, true, 2); }
      }
      disc(c, cx, cy, m * 0.1, "#fbf0c8");
      text(c, (d.label || d.maker || "·").slice(0, 1).toUpperCase(), cx, cy + 1, m * 0.1);
      break;
    }
    case "film": {
      c.fillStyle = INK; c.fillRect(x, y, w, h);
      const fr = d.frames || [], im = fr.length ? fr[Math.round(p * fr.length) % fr.length] : null;
      const pad = m * 0.08;
      if (im) { const sc = Math.max((w - pad * 2) / im.width, (h - pad * 2) / im.height); const dw = im.width * sc, dh = im.height * sc; c.save(); c.beginPath(); c.rect(x + pad, y + pad, w - pad * 2, h - pad * 2); c.clip(); c.drawImage(im, cx - dw / 2, cy - dh / 2, dw, dh); c.restore(); }
      else { c.fillStyle = "#333"; c.fillRect(x + pad, y + pad, w - pad * 2, h - pad * 2); }
      c.fillStyle = PAPER; for (let i = 0; i < 9; i++) { const yy = y + ((i / 9 + p / 9) % 1) * h; c.fillRect(x + pad * 0.3, yy, pad * 0.4, pad * 0.5); c.fillRect(x + w - pad * 0.7, yy, pad * 0.4, pad * 0.5); }
      break;
    }
    case "tunnel": {
      c.fillStyle = "#2a2a2a"; c.fillRect(x, y, w, h);
      const ims = (d.imgs || []).filter((i) => i.naturalWidth);
      const iw = w * 0.5, ih = h * 0.56, ty = cy - ih / 2;
      if (ims.length) {
        const off = p * iw;
        for (let i = -1; i < 4; i++) {
          const im = ims[((i % ims.length) + ims.length) % ims.length], ix = x + i * iw - off + iw * 0.25;
          const sc = Math.max(iw / im.naturalWidth, ih / im.naturalHeight); c.save(); c.beginPath(); c.rect(ix, ty, iw - 6, ih); c.clip();
          c.drawImage(im, ix + (iw - im.naturalWidth * sc) / 2, ty + (ih - im.naturalHeight * sc) / 2, im.naturalWidth * sc, im.naturalHeight * sc); c.restore();
        }
      } else { for (let i = -1; i < 4; i++) { c.fillStyle = i % 2 ? RED : BLUE; c.fillRect(x + i * iw - p * iw, ty, iw - 6, ih); } }
      c.fillStyle = INK; const sl = w / 7; for (let i = 0; i < 8; i++) c.fillRect(x + i * sl, ty - 8, sl * 0.62, ih + 16);
      c.fillStyle = OCHRE; c.fillRect(x, ty - 18, w, 10); c.fillRect(x, ty + ih + 8, w, 10);
      break;
    }
    case "sprout": {
      c.fillStyle = SKY; c.fillRect(x, y, w, h);
      const sway = Math.sin(TAU * p) * m * 0.08, base = y + h * 0.78;
      poly(c, [[cx - m * 0.14, base], [cx + m * 0.14, base], [cx + m * 0.1, y + h * 0.95], [cx - m * 0.1, y + h * 0.95]], RED);
      c.fillStyle = "#6b4a2a"; c.fillRect(cx - m * 0.15, base - 6, m * 0.3, 8);
      const tx = cx + sway, ty = y + h * 0.22;
      c.strokeStyle = "#4f7a33"; c.lineWidth = 6; c.lineCap = "round"; c.beginPath(); c.moveTo(cx, base); c.quadraticCurveTo(cx - sway * 0.4, (base + ty) / 2, tx, ty); c.stroke();
      for (const [u, s] of [[0.45, -1], [0.65, 1]] as const) { const lx = cx + (tx - cx) * u * u, ly = base + (ty - base) * u; c.save(); c.translate(lx, ly); c.rotate(s * (0.7 + Math.sin(TAU * p + u * 4) * 0.15)); c.beginPath(); c.ellipse(s * m * 0.07, 0, m * 0.07, m * 0.03, 0, 0, TAU); c.fillStyle = "#6f9c4a"; c.fill(); c.lineWidth = 2; c.strokeStyle = INK; c.stroke(); c.restore(); }
      for (let k = 0; k < 6; k++) disc(c, tx + Math.cos(k * 1.05) * m * 0.05, ty + Math.sin(k * 1.05) * m * 0.05, m * 0.035, GOLD, true, 1.5);
      disc(c, tx, ty, m * 0.03, RED, true, 1.5);
      break;
    }
    case "teacup": {
      c.fillStyle = PAPER2; c.fillRect(x, y, w, h);
      for (let i = 0; i < 3; i++) {
        c.strokeStyle = "rgba(27,22,17,.45)"; c.lineWidth = 4; c.lineCap = "round"; c.beginPath();
        for (let k = 0; k <= 20; k++) { const u = k / 20, yy = cy - m * 0.06 - u * m * 0.34, xx = cx + (i - 1) * m * 0.08 + Math.sin(u * 6 - TAU * p) * m * 0.03; if (k) c.lineTo(xx, yy); else c.moveTo(xx, yy); }
        c.stroke();
      }
      c.beginPath(); c.ellipse(cx, y + h * 0.82, m * 0.3, m * 0.06, 0, 0, TAU); c.fillStyle = "#fffaf0"; c.fill(); c.lineWidth = 3; c.strokeStyle = INK; c.stroke();
      c.beginPath(); c.moveTo(cx - m * 0.18, cy); c.quadraticCurveTo(cx - m * 0.17, y + h * 0.8, cx, y + h * 0.8); c.quadraticCurveTo(cx + m * 0.17, y + h * 0.8, cx + m * 0.18, cy); c.closePath(); c.fillStyle = RED; c.fill(); c.stroke();
      c.beginPath(); c.ellipse(cx, cy, m * 0.18, m * 0.04, 0, 0, TAU); c.fillStyle = "#5a3418"; c.fill(); c.stroke();
      c.beginPath(); c.arc(cx + m * 0.2, cy + m * 0.1, m * 0.06, -1.2, 1.2); c.lineWidth = 6; c.stroke();
      break;
    }
    case "sunrise": {
      const t = 0.5 + 0.5 * Math.cos(TAU * p);
      const sky = c.createLinearGradient(0, y, 0, y + h); sky.addColorStop(0, `rgb(${Math.round(150 + 90 * t)}, ${Math.round(180 + 50 * t)}, ${Math.round(210 + 20 * t)})`); sky.addColorStop(1, "#f3d9a0");
      c.fillStyle = sky; c.fillRect(x, y, w, h);
      const sy = y + h * (0.72 - 0.34 * t), R = m * 0.14;
      c.save(); c.translate(cx, sy); c.rotate(p * TAU / 8);
      c.strokeStyle = GOLD; c.lineWidth = 5; c.lineCap = "round"; for (let i = 0; i < 8; i++) { const a = (i / 8) * TAU; c.beginPath(); c.moveTo(Math.cos(a) * R * 1.3, Math.sin(a) * R * 1.3); c.lineTo(Math.cos(a) * R * 1.75, Math.sin(a) * R * 1.75); c.stroke(); }
      c.restore();
      disc(c, cx, sy, R, RED);
      c.fillStyle = BLUE; c.beginPath(); c.moveTo(x, y + h); c.lineTo(x, y + h * 0.72); c.quadraticCurveTo(x + w * 0.3, y + h * 0.62, x + w * 0.55, y + h * 0.72); c.quadraticCurveTo(x + w * 0.8, y + h * 0.8, x + w, y + h * 0.7); c.lineTo(x + w, y + h); c.closePath(); c.fill();
      c.fillStyle = INK; c.fillRect(x, y + h * 0.72, w, 2);
      break;
    }
  }
  c.restore();
}
