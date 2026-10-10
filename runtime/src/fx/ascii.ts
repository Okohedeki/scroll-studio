/** ascii: a slowly drifting noise field drawn as characters of increasing density; the scroll stirs it. */
import { fit, type Bg } from "./index";

const RAMP = " .,:;-~=+*#%@";

const make: Bg = (canvas, colors) => {
  const ctx = canvas.getContext("2d")!;
  let phase = 0, last = 0;
  return (t, sv) => {
    const [w, h] = fit(canvas, ctx, 1);
    const dt = Math.min(0.05, t - last || 0.016);
    last = t;
    phase += dt * (0.25 + sv * 3);
    ctx.clearRect(0, 0, w, h);
    const cell = w < 700 ? 12 : 14;
    ctx.font = `${cell}px ${getComputedStyle(document.documentElement).getPropertyValue("--font-mono")}`;
    ctx.textBaseline = "top";
    const cols = Math.ceil(w / (cell * 0.62)), rows = Math.ceil(h / cell);
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const u = x / cols, v = y / rows;
        let n = Math.sin(u * 7 + phase) * Math.cos(v * 5 - phase * 0.7) + Math.sin((u + v) * 9 - phase * 1.3) * 0.6
              + Math.sin(Math.hypot(u - 0.7, v - 0.4) * 14 - phase * 2) * 0.5;
        n = (n + 2.1) / 4.2;
        // keep the middle (where the copy sits) quieter
        n *= 0.45 + 0.55 * Math.min(1, Math.abs(u - 0.5) * 2.6);
        const k = Math.floor(n * (RAMP.length - 1));
        if (k <= 0) continue;
        ctx.globalAlpha = 0.1 + n * 0.45;
        ctx.fillStyle = k > RAMP.length - 3 ? colors.accent : colors.ink;
        ctx.fillText(RAMP[k], x * cell * 0.62, y * cell);
      }
    }
    ctx.globalAlpha = 1;
  };
};
export default make;
