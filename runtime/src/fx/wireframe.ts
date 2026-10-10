/** wireframe: a perspective grid terrain rolling toward the viewer, with rolling hills; the scroll pushes it faster. */
import { fit, type Bg } from "./index";

const make: Bg = (canvas, colors) => {
  const ctx = canvas.getContext("2d")!;
  const cols = 34, rows = 26;
  let travel = 0, last = 0;
  const height = (x: number, z: number) =>
    Math.sin(x * 0.55 + z * 0.25) * 0.8 + Math.sin(x * 0.21 - z * 0.37) * 1.4 + Math.max(0, Math.abs(x) - 5) * 0.55;
  return (t, sv, p) => {
    const [w, h] = fit(canvas, ctx);
    const dt = Math.min(0.05, t - last || 0.016);
    last = t;
    travel += dt * (0.8 + sv * 9);
    ctx.clearRect(0, 0, w, h);
    const horizon = h * (0.42 + p * 0.1), f = w * 0.9, camY = 2.6;
    const proj = (x: number, y: number, z: number): [number, number] => [w / 2 + (x * f) / z, horizon + ((camY - y) * f) / z];
    const off = travel % 1;
    const grid: [number, number][][] = [];
    for (let r = 0; r < rows; r++) {
      const z = rows - r + 1.2 - off, row: [number, number][] = [];
      for (let c = 0; c < cols; c++) {
        const x = (c - (cols - 1) / 2) * 0.9;
        row.push(proj(x, height(x, z + Math.floor(travel)), z));
      }
      grid.push(row);
    }
    ctx.lineWidth = 1;
    for (let r = 0; r < rows; r++) {
      const fade = r / rows;
      ctx.strokeStyle = colors.accent;
      ctx.globalAlpha = 0.08 + fade * 0.5;
      ctx.beginPath();
      grid[r].forEach(([x, y], c) => (c ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.stroke();
      if (r) {
        ctx.beginPath();
        for (let c = 0; c < cols; c++) { ctx.moveTo(...grid[r - 1][c]); ctx.lineTo(...grid[r][c]); }
        ctx.stroke();
      }
    }
    // a sun disc on the horizon, cut by scan lines
    ctx.globalAlpha = 0.5;
    const R = Math.min(w, h) * 0.16;
    const g = ctx.createLinearGradient(0, horizon - R * 1.6, 0, horizon);
    g.addColorStop(0, colors.accent2); g.addColorStop(1, colors.accent);
    ctx.fillStyle = g;
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, w, horizon); ctx.clip();
    ctx.beginPath(); ctx.arc(w / 2, horizon - R * 0.35, R, 0, Math.PI * 2); ctx.fill();
    ctx.globalCompositeOperation = "destination-out";
    for (let i = 0; i < 7; i++) ctx.fillRect(0, horizon - R * 0.35 + i * R * 0.13, w, 2 + i * 0.8);
    ctx.restore();
    ctx.globalAlpha = 1;
  };
};
export default make;
