export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const smooth = (a: number, b: number, v: number) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
export const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export const params = new URLSearchParams(location.search);
/** ?p=0.4 (with optional ?s=<scene id>) jumps to that progress: used by snapshots, recordings and the UI preview. */
export const debugP: number | null = params.has("p") ? clamp(parseFloat(params.get("p") || "0")) : null;
export const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
/** Lerp factor for eased scroll values; 1 = jump straight to the target. */
export const follow = reducedMotion || debugP !== null ? 1 : 0.14;
export const isMobile = () => matchMedia("(max-width: 760px)").matches;

export function hexToRgb(hex: string): [number, number, number] {
  let h = hex.replace("#", "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255) as [number, number, number];
}

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const im = new Image();
    im.decoding = "async";
    im.onload = () => res(im);
    im.onerror = () => rej(new Error("failed to load " + src));
    im.src = src;
  });
}

/** Deterministic PRNG so procedural scenes look the same on every visit. */
export function rng(seed = 7) {
  let s = seed % 2147483647 || 1;
  return (a = 0, b = 1) => { s = (s * 16807) % 2147483647; return a + (b - a) * (s / 2147483647); };
}

// ---- scale labels ("100 µm", "2 nm", "8 kpc") interpolated in log space across steps
const UNITS: Record<string, number> = {
  "pm": 1e-12, "nm": 1e-9, "µm": 1e-6, "um": 1e-6, "mm": 1e-3, "cm": 1e-2, "m": 1, "km": 1e3,
  "au": 1.496e11, "AU": 1.496e11, "ly": 9.461e15, "pc": 3.086e16, "kpc": 3.086e19, "Mpc": 3.086e22,
};
const LADDERS: string[][] = [["nm", "µm", "mm", "m", "km"], ["km", "AU", "ly", "kpc", "Mpc"]];

export function parseScale(label: string): { v: number; unit: string } | null {
  const m = label.trim().match(/^([\d.,]+)\s*([^\d\s]+)$/);
  if (!m || !(m[2] in UNITS)) return null;
  return { v: parseFloat(m[1].replace(/,/g, "")) * UNITS[m[2]], unit: m[2] };
}

export function formatScale(metres: number, near: string[]): string {
  const ladder = LADDERS.find((l) => near.some((u) => l.includes(u))) || LADDERS[0];
  let unit = ladder[0];
  for (const u of ladder) if (metres >= UNITS[u] * 0.999) unit = u;
  const v = metres / UNITS[unit];
  const txt = v >= 10 ? Math.round(v).toLocaleString("en-US") : v.toFixed(1).replace(/\.0$/, "");
  return txt + " " + unit;
}

export function scaleAt(labels: string[], z: number): string {
  if (!labels.length) return "";
  const i = Math.max(0, Math.min(labels.length - 1, Math.floor(z)));
  const j = Math.min(labels.length - 1, i + 1);
  const a = parseScale(labels[i]), b = parseScale(labels[j]);
  if (!a || !b || i === j) return labels[Math.round(clamp(z, 0, labels.length - 1))];
  const t = clamp(z - i);
  return formatScale(Math.exp(Math.log(a.v) * (1 - t) + Math.log(b.v) * t), [a.unit, b.unit]);
}

/** Download a file completely, reporting progress, and return it as a blob URL (instant seeking afterwards). */
export async function fetchBlobURL(url: string, onProgress: (f: number) => void, type?: string): Promise<string> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  const total = Number(r.headers.get("content-length") || 0);
  if (!r.body || !total) { const b = await r.blob(); onProgress(1); return URL.createObjectURL(b); }
  const reader = r.body.getReader();
  const chunks: Uint8Array[] = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    onProgress(Math.min(1, got / total));
  }
  return URL.createObjectURL(new Blob(chunks as BlobPart[], { type: type || r.headers.get("content-type") || "" }));
}

/** Load an image and decode it off the main thread so drawing it later never stalls. */
export async function loadBitmap(src: string): Promise<ImageBitmap | HTMLImageElement> {
  const im = await loadImage(src);
  try { return await createImageBitmap(im); } catch { return im; }
}
