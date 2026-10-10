/** particles: drifting points joined by faint lines when close; the field speeds up and spreads with the scroll. */
import { rng } from "../lib/util";
import { fit, type Bg } from "./index";

const make: Bg = (canvas, colors) => {
  const ctx = canvas.getContext("2d")!;
  const r = rng(11);
  const pts = Array.from({ length: 90 }, () => ({ x: r(), y: r(), vx: r(-1, 1), vy: r(-1, 1), s: r(0.6, 2.2), hot: r() < 0.18 }));
  let last = 0;
  return (t, sv) => {
    const [w, h] = fit(canvas, ctx);
    const dt = Math.min(0.05, t - last || 0.016);
    last = t;
    ctx.clearRect(0, 0, w, h);
    const n = w < 700 ? 50 : pts.length, speed = 0.012 + sv * 0.12, link = Math.min(170, w * 0.14);
    for (let i = 0; i < n; i++) {
      const a = pts[i];
      a.x = (a.x + a.vx * speed * dt + 1) % 1;
      a.y = (a.y + a.vy * speed * dt - sv * 0.08 * dt + 1) % 1;
    }
    ctx.lineWidth = 1;
    for (let i = 0; i < n; i++) {
      const a = pts[i], ax = a.x * w, ay = a.y * h;
      for (let j = i + 1; j < n; j++) {
        const b = pts[j], dx = ax - b.x * w, dy = ay - b.y * h, d = Math.hypot(dx, dy);
        if (d < link) {
          ctx.globalAlpha = (1 - d / link) * 0.35;
          ctx.strokeStyle = a.hot || b.hot ? colors.accent : colors.ink;
          ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(b.x * w, b.y * h); ctx.stroke();
        }
      }
    }
    for (let i = 0; i < n; i++) {
      const a = pts[i];
      ctx.globalAlpha = a.hot ? 0.95 : 0.6;
      ctx.fillStyle = a.hot ? colors.accent : colors.ink;
      ctx.beginPath(); ctx.arc(a.x * w, a.y * h, a.s * (a.hot ? 1.5 : 1), 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  };
};
export default make;
