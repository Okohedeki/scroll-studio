/**
 * theme.art frames for style experiences. The compiler writes the config into <script id="ss-art"> and ships one
 * grayscale sprite sheet (frames stacked top to bottom). loadArt() decodes it into per-frame "subject" masks
 * (0 = background, 1 = subject, whichever way round the image was lit); styles turn them into characters, points...
 */
export interface ArtFrames { n: number; w: number; h: number; fps: number; label: string; mask: Float32Array[] }

export function artConfig(): { sheet: string; frames: number; w: number; h: number; fps: number; invert: boolean; label: string } | null {
  const el = document.getElementById("ss-art");
  if (!el) return null;
  try { return JSON.parse(el.textContent || "null"); } catch { return null; }
}

let cache: Promise<ArtFrames | null> | null = null;
export function loadArt(): Promise<ArtFrames | null> {
  if (cache) return cache;
  const cfg = artConfig();
  if (!cfg) return (cache = Promise.resolve(null));
  cache = new Promise((res) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = cfg.w; c.height = cfg.h * cfg.frames;
      const ctx = c.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(img, 0, 0);
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      const mask: Float32Array[] = [];
      for (let f = 0; f < cfg.frames; f++) {
        const m = new Float32Array(cfg.w * cfg.h);
        const o = f * cfg.w * cfg.h;
        for (let i = 0; i < m.length; i++) { const v = d[(o + i) * 4] / 255; m[i] = cfg.invert ? 1 - v : v; }
        mask.push(m);
      }
      res({ n: cfg.frames, w: cfg.w, h: cfg.h, fps: cfg.fps, label: cfg.label, mask });
    };
    img.onerror = () => res(null);
    img.src = cfg.sheet;
  });
  return cache;
}

/** Average of the mask over one cell of a cols x rows grid laid over the frame (box filter, so small grids stay clean). */
function cellAvg(m: Float32Array, w: number, h: number, x0: number, y0: number, x1: number, y1: number) {
  const xa = Math.max(0, Math.floor(x0)), xb = Math.min(w, Math.max(xa + 1, Math.ceil(x1)));
  const ya = Math.max(0, Math.floor(y0)), yb = Math.min(h, Math.max(ya + 1, Math.ceil(y1)));
  let s = 0, n = 0;
  for (let y = ya; y < yb; y++) for (let x = xa; x < xb; x++) { s += m[y * w + x]; n++; }
  return n ? s / n : 0;
}

/** The frame as text: cols x rows characters from a density ramp (space = background). */
export function asciiFrame(a: ArtFrames, f: number, cols: number, rows: number, ramp = " .:-=+*#%@", floor = 0.24): string {
  const m = a.mask[((f % a.n) + a.n) % a.n];
  const sx = a.w / cols, sy = a.h / rows;
  let out = "";
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      // background (below the floor) is blank; above it, a contrast curve so the subject reads as solid shapes
      const v = (cellAvg(m, a.w, a.h, c * sx, r * sy, (c + 1) * sx, (r + 1) * sy) - floor) / (1 - floor);
      out += v <= 0 ? " " : ramp[Math.min(ramp.length - 1, Math.max(1, Math.round(Math.pow(v, 1.2) * (ramp.length - 1))))];
    }
    if (r < rows - 1) out += "\n";
  }
  return out;
}

/** Rows that keep the frame's proportions for a text grid of `cols` columns with cells chW x lineH pixels. */
export function rowsFor(a: ArtFrames, cols: number, chW: number, lineH: number) {
  return Math.max(4, Math.round(cols * (a.h / a.w) * (chW / lineH)));
}
