/** sequence: pre-rendered frames drawn to a canvas (Apple-style product scrolls). */
import type { PlayerFactory } from "../lib/types";
import { follow, isMobile } from "../lib/util";

const factory: PlayerFactory = async (cfg, ctx) => {
  const set = isMobile() && cfg.mobile ? cfg.mobile : cfg.desktop;
  const count: number = cfg.count;
  const canvas = document.createElement("canvas");
  ctx.visual.appendChild(canvas);
  ctx.visual.style.background = cfg.background || "transparent";
  const g = canvas.getContext("2d", { alpha: true })!;
  const frames: (HTMLImageElement | null)[] = new Array(count).fill(null);
  const url = (i: number) => `${set.base}${String(i + 1).padStart(4, "0")}.${set.ext}`;

  // Load in passes: every 16th frame, then every 8th ... so scrubbing is usable almost immediately.
  const order: number[] = [];
  for (let step = 16; step >= 1; step /= 2) for (let i = 0; i < count; i += step) if (!order.includes(i)) order.push(i);
  let next = 0;
  const pump = () => {
    if (next >= order.length) return;
    const i = order[next++];
    const im = new Image();
    im.decoding = "async";
    im.onload = () => { frames[i] = im; dirty = true; pump(); };
    im.onerror = () => pump();
    im.src = url(i);
  };
  for (let k = 0; k < 6; k++) pump();

  let dpr = 1, dirty = true, cur = 0, drawn = -1;
  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    const r = canvas.getBoundingClientRect();
    canvas.width = Math.round(r.width * dpr);
    canvas.height = Math.round(r.height * dpr);
    dirty = true;
  }
  resize();

  function nearest(i: number): HTMLImageElement | null {
    for (let d = 0; d < count; d++) {
      if (frames[i - d]) return frames[i - d];
      if (frames[i + d]) return frames[i + d];
    }
    return null;
  }

  return {
    resize,
    update(s) {
      cur += (s.p * (count - 1) - cur) * follow;
      const i = Math.round(cur);
      if (i === drawn && !dirty) return;
      const im = nearest(i);
      if (!im) return;
      const cw = canvas.width, ch = canvas.height;
      const fit = cfg.fit === "contain" ? Math.min : Math.max;
      const k = fit(cw / im.naturalWidth, ch / im.naturalHeight);
      const w = im.naturalWidth * k, h = im.naturalHeight * k;
      g.clearRect(0, 0, cw, ch);
      const shift = isMobile() ? 0 : (cfg.shift || 0) * cw;
      g.drawImage(im, (cw - w) / 2 + shift, (ch - h) / 2, w, h);
      drawn = frames[i] ? i : -1;
      dirty = false;
    },
  };
};
export default factory;
