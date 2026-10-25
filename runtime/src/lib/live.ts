/**
 * Living details: one small thing alive in a still picture (`live:` on an image input, engine/spec.py LiveDetail; the build
 * side is engine/live.py). Five kinds, each drawn by the page from the picture itself, so no GPU is needed at build time:
 *
 *   sweep  a soft band of light slides across the region now and then; with `origin`, a beam turns round that point
 *   glint  small four-pointed twinkles, one after another, on the region's brightest points (found at build time)
 *   drift  the region slides slowly to and fro inside soft edges (clouds, mist); with a prompt's mask, the thing itself
 *   rise   soft specks rise through the region and fade near its top (embers, bubbles, dust in a beam)
 *   flow   a gentle wavy shimmer, the picture displaced along ripples (water)
 *
 * This module is the part that is not drawing: reading the build's settings, the maths of each kind (mirrored line for line
 * by LIVE_GLSL, which the players include in their own pass), packing the uniforms, the mask atlas and the frame clock. The
 * drawing happens in players/parallax.ts (inside the photo's pass) and players/liveStill.ts (a layer over a plain <img>).
 * Times are in seconds; every motion is periodic, so the loop never shows a seam.
 */
import { clamp } from "./util";

export type LiveKind = "sweep" | "glint" | "drift" | "rise" | "flow";
export const KINDS: Record<LiveKind, number> = { sweep: 1, glint: 2, drift: 3, rise: 4, flow: 5 };
/** details per picture, and glint points per picture (the spec's caps) */
export const PER = 4, POINTS = 24;

/** One detail as the build writes it (engine/live.py `page_detail`). */
export interface LiveDetail {
  kind: LiveKind;
  /** x0, y0, x1, y1 in 0-1 of the picture */
  box: [number, number, number, number];
  speed: number; strength: number; softness: number; count: number;
  /** the light's colour, resolved from the theme at build time */
  color: string;
  /** degrees, 0 to the right, 90 down */
  angle: number;
  /** sweep: the beam's pivot, 0-1 of the region (null: a sliding band) */
  origin: [number, number] | null;
  /** a soft mask over the box (a prompt's region), or none */
  mask?: string | null;
  /** glint: the bright points, x, y (0-1 of the picture) and a size 0-1 */
  points?: [number, number, number][];
}

const num = (v: unknown, d: number, lo: number, hi: number) => (typeof v === "number" && Number.isFinite(v) ? clamp(v, lo, hi) : d);

/** The details the page carries, checked and with defaults; anything malformed is left out (the picture just stays still). */
export function readLive(raw: unknown): LiveDetail[] {
  if (!Array.isArray(raw)) return [];
  const out: LiveDetail[] = [];
  for (const d of raw) {
    if (!d || typeof d !== "object" || !(d.kind in KINDS) || !Array.isArray(d.box) || d.box.length !== 4) continue;
    const [x0, y0, x1, y1] = d.box.map((v: unknown) => num(v, 0, 0, 1));
    if (!(x1 > x0 && y1 > y0)) continue;
    out.push({
      kind: d.kind, box: [x0, y0, x1, y1],
      speed: num(d.speed, 1, 0.1, 4), strength: num(d.strength, 0.6, 0, 1), softness: num(d.softness, 0.25, 0, 0.5),
      count: Math.round(num(d.count, 12, 1, POINTS)),
      color: typeof d.color === "string" && /^#[0-9a-f]{6}$/i.test(d.color) ? d.color : "#ffffff",
      angle: num(d.angle, 0, -360, 360),
      origin: Array.isArray(d.origin) && d.origin.length === 2 ? [num(d.origin[0], 0.5, -2, 3), num(d.origin[1], 0.5, -2, 3)] : null,
      mask: typeof d.mask === "string" ? d.mask : null,
      points: Array.isArray(d.points) ? d.points.slice(0, POINTS).filter((p: unknown) => Array.isArray(p) && p.length >= 2)
        .map((p: number[]) => [num(p[0], 0.5, 0, 1), num(p[1], 0.5, 0, 1), num(p[2], 1, 0, 1)] as [number, number, number]) : [],
    });
    if (out.length === PER) break;
  }
  return out;
}

// ---------------------------------------------------------------- the maths (pure; LIVE_GLSL mirrors it)

const TAU = Math.PI * 2;
const smoothstep = (a: number, b: number, x: number) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
export const dirOf = (angle: number): [number, number] => [Math.cos((angle * Math.PI) / 180), Math.sin((angle * Math.PI) / 180)];

/** How long each kind's cycle is, in seconds at speed 1 (a speed of 2 halves it). */
export const PERIOD = { sweep: 7, beam: 9, glint: 3.2, drift: 16, flow: 0 } as const;

/** The region's weight at a point: 1 inside the box, easing to 0 over `softness` (a share of the box) at its edges, 0 outside.
 * `l` is the point in 0-1 of the box. */
export function edge(l: [number, number], softness: number): number {
  if (l[0] < 0 || l[0] > 1 || l[1] < 0 || l[1] > 1) return 0;
  const s = Math.max(softness, 1e-3);
  return smoothstep(0, s, l[0]) * smoothstep(0, s, 1 - l[0]) * smoothstep(0, s, l[1]) * smoothstep(0, s, 1 - l[1]);
}

/** A point of the picture (0-1) in 0-1 of a box. */
export const local = (q: [number, number], b: [number, number, number, number]): [number, number] =>
  [(q[0] - b[0]) / (b[2] - b[0]), (q[1] - b[1]) / (b[3] - b[1])];

/** The box's own aspect on screen (width over height), from the picture's aspect. */
export const boxAspect = (b: [number, number, number, number], aspect: number) => ((b[2] - b[0]) * aspect) / (b[3] - b[1]);

/** drift: how far the region has slid at time t (already times speed), in picture heights: to and fro along `dir`, a slow sine
 * 16 s round, as far as 0.035 picture heights at full strength. */
export function driftOffset(t: number, strength: number, dir: [number, number]): [number, number] {
  const a = 0.035 * strength * Math.sin((TAU * t) / PERIOD.drift);
  return [dir[0] * a, dir[1] * a];
}

/** sweep (a sliding band): its brightness at `l` (0-1 of the box) at time t. A pass takes the first half of each 7 s cycle,
 * the band crossing from one side to the other along `dir`, swelling in and out; the rest of the cycle is dark. */
export function sweepBand(l: [number, number], t: number, dir: [number, number], ba: number): number {
  const k = Math.max(ba, 1);
  const p = [(l[0] - 0.5) * ba / k, (l[1] - 0.5) / k];
  const s = p[0] * dir[0] + p[1] * dir[1];
  const x = (((t / PERIOD.sweep) % 1) + 1) % 1 / 0.5;
  if (x > 1) return 0;
  const c = -0.8 + 1.6 * smoothstep(0, 1, x);
  return Math.exp(-(((s - c) / 0.07) ** 2)) * Math.sqrt(Math.max(0, Math.sin(Math.PI * x)));
}

/** sweep with an origin: a beam turning round it, once every 9 s, starting along `dir`; brightest near the pivot. */
export function sweepBeam(l: [number, number], t: number, dir: [number, number], origin: [number, number], ba: number): number {
  const k = Math.max(ba, 1);
  const v = [(l[0] - origin[0]) * ba / k, (l[1] - origin[1]) / k];
  const a = Math.atan2(v[1], v[0]);
  const th = Math.atan2(dir[1], dir[0]) + (TAU * t) / PERIOD.beam;
  const d = Math.abs(((((a - th + Math.PI) % TAU) + TAU) % TAU) - Math.PI);
  return Math.exp(-((d / 0.16) ** 2)) * (0.55 + 0.45 * Math.exp(-Math.hypot(v[0], v[1]) * 1.5));
}

/** glint: how lit a twinkle is at time t (phase 0-1 staggers them): a quick swell and fade over the first 35% of its 3.2 s
 * cycle, dark the rest of it. */
export function twinkle(t: number, phase: number): number {
  const ph = ((((t / PERIOD.glint) + phase) % 1) + 1) % 1;
  return ph < 0.35 ? Math.sin((Math.PI * ph) / 0.35) ** 2 : 0;
}

/** glint: the four-pointed star's brightness at offset d (picture heights) from its point, for a star of radius r. */
export function star(d: [number, number], r: number): number {
  const ax = Math.abs(d[0]) / r, ay = Math.abs(d[1]) / r;
  const core = Math.exp(-(ax * ax + ay * ay) * 6);
  const rays = Math.exp(-ax * ax * 60 - ay * 3) + Math.exp(-ay * ay * 60 - ax * 3);
  return Math.min(1, core + 0.6 * rays);
}

/** A stable random number 0-1 for a cell (the GLSL's lvHash; floats differ a little between CPU and GPU, which is fine). */
export const hash = (x: number, y: number) => { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); };

/** rise: the grid the specks live in, about `count` cells, shaped to the box. */
export function riseGrid(count: number, ba: number): [number, number] {
  const cols = Math.max(2, Math.round(Math.sqrt(count * ba)));
  return [cols, Math.max(2, Math.round(count / cols))];
}

/** rise: the specks' brightness at `l` (0-1 of the box) at time t. The grid scrolls up a box height every 11 s; each cell may
 * hold one soft speck, swaying a little and flickering; they fade in from the bottom and out before the top. */
export function riseField(l: [number, number], t: number, count: number, ba: number): number {
  const [cols, rows] = riseGrid(count, ba);
  const u = l[0] * cols, vy = (l[1] + t * 0.09) * rows;
  const cx = Math.floor(u), cy = Math.floor(vy);
  const h = hash(cx, cy), h2 = hash(cx + 7.1, cy + 1.7), h3 = hash(cx + 3.3, cy + 9.2);
  if (h3 < 0.45) return 0;
  const f = [u - cx, vy - cy];
  const c = [0.3 + 0.4 * h + 0.15 * Math.sin(t * 1.1 + h * TAU), 0.3 + 0.4 * h2];
  const sx = ba / cols, sy = 1 / rows, m = Math.min(sx, sy);
  const d = [(f[0] - c[0]) * sx / m, (f[1] - c[1]) * sy / m];
  const r = 0.1 + 0.08 * h2;
  const fade = smoothstep(0, 0.45, l[1]) * (1 - smoothstep(0.85, 1, l[1]));
  return Math.exp(-(d[0] * d[0] + d[1] * d[1]) / (r * r)) * (0.7 + 0.3 * Math.sin(t * 3 + h * 20)) * fade;
}

/** flow: how far the picture is displaced at point p (picture heights from its top left) and time t, in picture heights, and
 * a little shimmer of light (a factor near 1). Ripples run along `dir`: the displacement is mostly across it. */
export function flowAt(p: [number, number], t: number, strength: number, dir: [number, number]): { d: [number, number]; shimmer: number } {
  const across = [-dir[1], dir[0]];
  const a1 = (p[0] * across[0] + p[1] * across[1]) * 38 + t * 1.6;
  const a2 = (p[0] * dir[0] + p[1] * dir[1]) * 11 - t * 0.9;
  const k = strength / 0.6;
  const w1 = Math.sin(a1 + Math.sin(a2)) * 0.0022 * k, w2 = Math.cos(a1 * 0.7 - t) * 0.0012 * k;
  return { d: [across[0] * w1 + dir[0] * w2, across[1] * w1 + dir[1] * w2], shimmer: 1 + 0.05 * strength * Math.sin(a1 * 1.3 + a2) };
}

/** Light laid over a colour like a screen print of light (never darkens, never clips). */
export const screenOver = (c: number, l: number) => 1 - (1 - c) * (1 - clamp(l));

// ---------------------------------------------------------------- the uniforms

export function hexRgb(h: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255) as [number, number, number];
}

/** What LIVE_GLSL reads, for `views` pictures of up to PER details and POINTS glint points each. */
export interface LivePack { box: Float32Array; a: Float32Array; b: Float32Array; c: Float32Array; m: Float32Array; p: Float32Array }
export function emptyPack(views: number): LivePack {
  const n = views * PER * 4;
  return { box: new Float32Array(n), a: new Float32Array(n), b: new Float32Array(n), c: new Float32Array(n), m: new Float32Array(n),
    p: new Float32Array(views * POINTS * 4) };
}

/** Write one picture's details into view `v` of a pack (slots v*PER.., points v*POINTS..). `cells` are the mask atlas cells
 * (x, y, w, h in 0-1 of the atlas, null: no mask), one per detail. Unused slots get kind 0 and are skipped by the shader. */
export function packView(pack: LivePack, v: number, details: LiveDetail[], cells: ([number, number, number, number] | null)[] = []) {
  for (let k = 0; k < PER; k++) {
    const i = (v * PER + k) * 4, d = details[k];
    for (const arr of [pack.box, pack.a, pack.b, pack.c, pack.m]) arr.fill(0, i, i + 4);
    if (!d) continue;
    const dir = dirOf(d.angle);
    pack.box.set(d.box, i);
    pack.a.set([KINDS[d.kind], d.speed, d.strength, d.softness], i);
    let z = -99, w = -99;
    if (d.kind === "sweep" && d.origin) [z, w] = d.origin;
    if (d.kind === "glint") {
      // this detail's points follow the ones before it in the picture's share of the points
      const first = details.slice(0, k).reduce((n, e) => n + (e.kind === "glint" ? Math.min(e.points?.length ?? 0, e.count) : 0), 0);
      const pts = (d.points ?? []).slice(0, Math.min(d.count, POINTS - first));
      pts.forEach((p, j) => pack.p.set([p[0], p[1], p[2], hash(j + 0.37, k + 1.3)], (v * POINTS + first + j) * 4));
      z = v * POINTS + first; w = pts.length;
    }
    pack.b.set([dir[0], dir[1], z, w], i);
    pack.c.set([...hexRgb(d.color), d.count], i);
    const cell = cells[k];
    if (cell) pack.m.set(cell, i);
  }
}

/** Mask atlas: `n` square cells in a grid, each cell's x, y, w, h in 0-1 of the atlas (a half texel in, so a cell never
 * bleeds into the next). */
export function atlasCells(n: number, cell = 256): { cols: number; rows: number; cells: [number, number, number, number][] } {
  const cols = Math.max(1, Math.ceil(Math.sqrt(n))), rows = Math.max(1, Math.ceil(n / cols));
  const W = cols * cell, H = rows * cell;
  const cells: [number, number, number, number][] = [];
  for (let i = 0; i < n; i++) {
    const cx = i % cols, cy = Math.floor(i / cols);
    cells.push([(cx * cell + 0.5) / W, (cy * cell + 0.5) / H, (cell - 1) / W, (cell - 1) / H]);
  }
  return { cols, rows, cells };
}

/** Draw the masks into one atlas canvas (missing or failed ones get no cell). */
export async function maskAtlas(urls: (string | null | undefined)[], load: (u: string) => Promise<CanvasImageSource>):
  Promise<{ canvas: HTMLCanvasElement | null; cells: ([number, number, number, number] | null)[] }> {
  const want = urls.map((u, i) => (u ? i : -1)).filter((i) => i >= 0);
  if (!want.length) return { canvas: null, cells: urls.map(() => null) };
  const S = 256, grid = atlasCells(want.length, S);
  const canvas = document.createElement("canvas");
  canvas.width = grid.cols * S; canvas.height = grid.rows * S;
  const g = canvas.getContext("2d");
  const cells: ([number, number, number, number] | null)[] = urls.map(() => null);
  await Promise.all(want.map(async (i, j) => {
    try {
      const im = await load(urls[i]!);
      g?.drawImage(im, (j % grid.cols) * S, Math.floor(j / grid.cols) * S, S, S);
      cells[i] = grid.cells[j];
    } catch { /* no mask: the box alone */ }
  }));
  return { canvas, cells };
}

// ---------------------------------------------------------------- where the picture is

/** A CSS position value (object-position / background-position) as 0-1. */
export function parsePos(v: string): number {
  if (v === "left" || v === "top") return 0;
  if (v === "right" || v === "bottom") return 1;
  if (v === "center") return 0.5;
  const n = parseFloat(v);
  return Number.isFinite(n) ? n / 100 : 0.5;
}

/** The rectangle a picture of aspect r occupies in a W x H box (px), by object-fit / background-size and position; null for
 * a fit this does not know (the detail is then not drawn). */
export function pictureRect(W: number, H: number, r: number, fit: string, pos: string): { x: number; y: number; w: number; h: number } | null {
  if (!W || !H || !r) return null;
  const p = pos.split(/\s+/), px = parsePos(p[0] ?? "50%"), py = parsePos(p[1] ?? p[0] ?? "50%");
  let w: number, h: number;
  if (fit === "cover") { h = Math.max(W / r, H); w = h * r; }
  else if (fit === "contain" || fit === "scale-down") { h = Math.min(W / r, H); w = h * r; }
  else if (fit === "fill" || fit === "100% 100%") { w = W; h = H; }
  else return null;
  return { x: (W - w) * px, y: (H - h) * py, w, h };
}

/** The shader's map from the layer's 0-1 (y down) to the picture's 0-1: q = uv * xy + zw. */
export const uvMap = (W: number, H: number, rc: { x: number; y: number; w: number; h: number }): [number, number, number, number] =>
  [W / rc.w, H / rc.h, -rc.x / rc.w, -rc.y / rc.h];

// ---------------------------------------------------------------- the clock

/** 30 frames a second is plenty for slow light and drift, and half the work of 60. */
export const FPS = 30;
/** Whether a frame is due at `now` (ms) after the last one drawn at `last` (ms; -1: never). */
export const due = (now: number, last: number, fps = FPS) => last < 0 || now - last >= 1000 / fps - 1;

/** Whether the details should move at all: on screen, the tab visible, and the visitor not asking for less motion. */
export const shouldRun = (seen: boolean, hidden: boolean, reduced: boolean) => seen && !hidden && !reduced;

// ---------------------------------------------------------------- the GLSL

/** Uniforms and functions for a pass that draws living details; define LV_VIEWS (pictures in the pass) before it. Call
 * `liveApply(img, q, c, v, alpha)` with the picture's colour c at q (0-1, y down) for view v: it returns the colour with the
 * view's details applied and raises `alpha` to how much it changed (for a layer laid over the picture). */
export const LIVE_GLSL = `
#define LV_PER ${PER}
#define LV_POINTS ${POINTS}
uniform vec4 uLvBox[LV_VIEWS * LV_PER], uLvA[LV_VIEWS * LV_PER], uLvB[LV_VIEWS * LV_PER], uLvC[LV_VIEWS * LV_PER], uLvM[LV_VIEWS * LV_PER];
uniform vec4 uLvP[LV_VIEWS * LV_POINTS];
uniform float uLvT, uLvAsp;
uniform sampler2D uLvMask;
const float LV_TAU = 6.28318530718;
float lvHash(vec2 p) { return fract(sin(p.x * 127.1 + p.y * 311.7) * 43758.5453); }
float lvRegion(int i, vec2 q) {
  vec4 b = uLvBox[i];
  vec2 l = (q - b.xy) / (b.zw - b.xy);
  if (l.x < 0.0 || l.x > 1.0 || l.y < 0.0 || l.y > 1.0) return 0.0;
  float s = max(uLvA[i].w, 1e-3);
  vec2 e = smoothstep(vec2(0.0), vec2(s), l) * smoothstep(vec2(0.0), vec2(s), 1.0 - l);
  float m = e.x * e.y;
  vec4 c = uLvM[i];
  if (c.z > 0.0) m *= texture(uLvMask, c.xy + l * c.zw).r;
  return m;
}
float lvSweep(vec2 l, float t, vec2 dir, vec2 o, float ba) {
  float k = max(ba, 1.0);
  if (o.x > -50.0) {
    vec2 v = (l - o) * vec2(ba, 1.0) / k;
    float th = atan(dir.y, dir.x) + LV_TAU * t / 9.0;
    float d = abs(mod(atan(v.y, v.x) - th + 3.14159265, LV_TAU) - 3.14159265);
    float e = d / 0.16;
    return exp(-e * e) * (0.55 + 0.45 * exp(-length(v) * 1.5));
  }
  vec2 p = (l - 0.5) * vec2(ba, 1.0) / k;
  float s = dot(p, dir);
  float x = fract(t / 7.0) / 0.5;
  if (x > 1.0) return 0.0;
  float c = -0.8 + 1.6 * smoothstep(0.0, 1.0, x);
  float e = (s - c) / 0.07;
  return exp(-e * e) * sqrt(max(sin(3.14159265 * x), 0.0));
}
float lvGlint(vec2 q, int first, int n, float t, float s) {
  float I = 0.0;
  for (int j = 0; j < LV_POINTS; j++) {
    if (j >= n) break;
    vec4 pt = uLvP[first + j];
    vec2 d = (q - pt.xy) * vec2(uLvAsp, 1.0);
    float r = 0.016 * (0.6 + 0.4 * pt.z) * (0.7 + 0.5 * s);
    if (abs(d.x) > r * 3.0 || abs(d.y) > r * 3.0) continue;
    float ph = fract(t / 3.2 + pt.w);
    float sw = sin(3.14159265 * ph / 0.35);
    float tw = ph < 0.35 ? sw * sw : 0.0;
    vec2 a = abs(d) / r;
    float st = exp(-dot(a, a) * 6.0) + 0.6 * (exp(-a.x * a.x * 60.0 - a.y * 3.0) + exp(-a.y * a.y * 60.0 - a.x * 3.0));
    I += tw * min(st, 1.0);
  }
  return min(I, 1.0);
}
float lvRise(vec2 l, float t, float count, float ba) {
  float cols = max(2.0, floor(sqrt(count * ba) + 0.5));
  float rows = max(2.0, floor(count / cols + 0.5));
  vec2 g = vec2(l.x * cols, (l.y + t * 0.09) * rows);
  vec2 cell = floor(g), f = g - cell;
  float h = lvHash(cell), h2 = lvHash(cell + vec2(7.1, 1.7)), h3 = lvHash(cell + vec2(3.3, 9.2));
  if (h3 < 0.45) return 0.0;
  vec2 c = vec2(0.3 + 0.4 * h + 0.15 * sin(t * 1.1 + h * LV_TAU), 0.3 + 0.4 * h2);
  vec2 sc = vec2(ba / cols, 1.0 / rows);
  vec2 d = (f - c) * sc / min(sc.x, sc.y);
  float r = 0.1 + 0.08 * h2;
  float fade = smoothstep(0.0, 0.45, l.y) * (1.0 - smoothstep(0.85, 1.0, l.y));
  return exp(-dot(d, d) / (r * r)) * (0.7 + 0.3 * sin(t * 3.0 + h * 20.0)) * fade;
}
vec3 liveApply(sampler2D img, vec2 q, vec3 col, int v, inout float alpha) {
  for (int k = 0; k < LV_PER; k++) {
    int i = v * LV_PER + k;
    vec4 A = uLvA[i];
    int kind = int(A.x + 0.5);
    if (kind == 0) continue;
    vec4 b = uLvBox[i];
    float reach = kind == 3 ? 0.04 * A.z / min(uLvAsp, 1.0) + 0.002 : 0.0;
    if (q.x < b.x - reach || q.x > b.z + reach || q.y < b.y - reach || q.y > b.w + reach) continue;
    float t = uLvT * A.y, s = A.z;
    vec2 dir = uLvB[i].xy;
    if (kind == 3) {
      vec2 off = dir * 0.035 * s * sin(LV_TAU * t / 16.0);
      vec2 offUv = vec2(off.x / uLvAsp, off.y);
      float m = max(lvRegion(i, q), lvRegion(i, q - offUv));
      if (m <= 0.0) continue;
      col = mix(col, texture(img, q - offUv).rgb, m);
      alpha = max(alpha, m);
      continue;
    }
    float m = lvRegion(i, q);
    if (m <= 0.0) continue;
    if (kind == 5) {
      vec2 p = q * vec2(uLvAsp, 1.0), across = vec2(-dir.y, dir.x);
      float a1 = dot(p, across) * 38.0 + t * 1.6, a2 = dot(p, dir) * 11.0 - t * 0.9, kk = s / 0.6;
      vec2 d = across * sin(a1 + sin(a2)) * 0.0022 * kk + dir * cos(a1 * 0.7 - t) * 0.0012 * kk;
      vec3 w = texture(img, q + vec2(d.x / uLvAsp, d.y)).rgb * (1.0 + 0.05 * s * sin(a1 * 1.3 + a2));
      col = mix(col, clamp(w, 0.0, 1.0), m);
      alpha = max(alpha, m);
      continue;
    }
    vec2 l = (q - b.xy) / (b.zw - b.xy);
    float ba = (b.z - b.x) * uLvAsp / (b.w - b.y);
    float I = kind == 1 ? lvSweep(l, t, dir, uLvB[i].zw, ba)
            : kind == 2 ? lvGlint(q, int(uLvB[i].z + 0.5), int(uLvB[i].w + 0.5), t, s)
            : lvRise(l, t, uLvC[i].w, ba);
    // a sweep is a broad light, so gentler; glints and specks are small, so brighter
    float gain = kind == 1 ? 0.7 : kind == 2 ? 1.4 : 1.2;
    vec3 light = clamp(uLvC[i].rgb * I * s * m * gain, 0.0, 1.0);
    col = 1.0 - (1.0 - col) * (1.0 - light);
    alpha = max(alpha, max(light.r, max(light.g, light.b)));
  }
  return col;
}
`;
