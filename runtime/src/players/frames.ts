/** sequence: pre-rendered frames drawn to a canvas (Apple-style product scrolls).
 *
 * Every frame is downloaded and decoded to an ImageBitmap before the page unlocks, so drawing never stalls.
 * Between two rendered frames the canvas cross-fades by the fractional scroll position, which turns a
 * 96-frame render into continuous motion instead of visible steps. */
import type { PlayerFactory } from "../lib/types";
import { follow, isMobile, loadBitmap } from "../lib/util";

type Frame = ImageBitmap | HTMLImageElement;

const factory: PlayerFactory = async (cfg, ctx) => {
  const set = isMobile() && cfg.mobile ? cfg.mobile : cfg.desktop;
  const count: number = cfg.count;
  const canvas = document.createElement("canvas");
  ctx.visual.appendChild(canvas);
  ctx.visual.style.background = cfg.background || "transparent";
  const g = canvas.getContext("2d", { alpha: true })!;
  g.imageSmoothingQuality = "high";
  const url = (i: number) => `${set.base}${String(i + 1).padStart(4, "0")}.${set.ext}`;
  const frames: (Frame | null)[] = new Array(count).fill(null);

  // Load everything, 8 at a time, in an order that fills the timeline evenly (every 16th, then 8th, ...).
  const order: number[] = [];
  for (let step = 16; step >= 1; step /= 2) for (let i = 0; i < count; i += step) if (!order.includes(i)) order.push(i);
  let done = 0;
  await new Promise<void>((resolve) => {
    let next = 0, active = 0;
    const pump = () => {
      while (active < 8 && next < order.length) {
        const i = order[next++];
        active++;
        loadBitmap(url(i)).then((b) => { frames[i] = b; }).catch(() => {}).finally(() => {
          active--; done++;
          ctx.progress(done / count);
          if (done === count) resolve(); else pump();
        });
      }
    };
    pump();
  });

  let dpr = 1;
  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    const r = canvas.getBoundingClientRect();
    canvas.width = Math.round(r.width * dpr);
    canvas.height = Math.round(r.height * dpr);
    last = -1;
  }
  let last = -1, cur = 0;
  resize();
  const size = (f: Frame) => [(f as any).width || (f as HTMLImageElement).naturalWidth, (f as any).height || (f as HTMLImageElement).naturalHeight];
  function draw(f: Frame, alpha: number) {
    const cw = canvas.width, ch = canvas.height, [fw, fh] = size(f);
    const fit = cfg.fit === "contain" ? Math.min : Math.max;
    const k = fit(cw / fw, ch / fh), w = fw * k, h = fh * k;
    const shift = isMobile() ? 0 : (cfg.shift || 0) * cw;
    g.globalAlpha = alpha;
    g.drawImage(f as CanvasImageSource, (cw - w) / 2 + shift, (ch - h) / 2, w, h);
  }

  return {
    resize,
    update(s) {
      cur += (s.p * (count - 1) - cur) * follow;
      if (Math.abs(cur - last) < 0.002) return;
      last = cur;
      const i = Math.min(count - 1, Math.floor(cur)), t = cur - i;
      const a = frames[i], b = frames[Math.min(count - 1, i + 1)];
      if (!a) return;
      g.clearRect(0, 0, canvas.width, canvas.height);
      draw(a, 1);
      if (b && b !== a && t > 0.01) draw(b, t);
      g.globalAlpha = 1;
    },
  };
};
export default factory;
