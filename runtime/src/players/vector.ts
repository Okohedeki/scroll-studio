/**
 * vector: an SVG drawing whose paths stroke themselves in order, then fill.
 * Steps split the scroll into phases: the first non-intro step draws the outlines, the next fills them,
 * any later steps hold the finished drawing (a slow push-in keeps it alive).
 */
import type { PlayerFactory } from "../lib/types";
import { clamp, cssVar, easeInOut } from "../lib/util";

const factory: PlayerFactory = async (cfg, ctx) => {
  const text = await (await fetch(cfg.svg)).text();
  const wrap = document.createElement("div");
  Object.assign(wrap.style, { position: "absolute", inset: "0", display: "flex", alignItems: "center", justifyContent: "center",
    background: cfg.background || "transparent", padding: "4%" });
  wrap.innerHTML = text;
  ctx.visual.appendChild(wrap);
  const svg = wrap.querySelector("svg")!;
  Object.assign(svg.style, { width: "100%", height: "100%", overflow: "visible", transformOrigin: "50% 50%" });
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  const ink = cssVar("--ink") || "#222", accent = cssVar("--accent") || "#c40";
  const paths = [...svg.querySelectorAll<SVGPathElement>("path")];
  const n = paths.length;
  // thin strokes for dense engravings, bolder for simple logos
  const sw = n > 2000 ? 0.7 : n > 400 ? 1.1 : 2;
  paths.forEach((p) => {
    p.setAttribute("pathLength", "1");
    p.style.fill = cfg.colors === "ink" ? ink : cfg.colors === "accent" ? accent : p.dataset.fill || ink;
    p.style.fillOpacity = "0";
    p.style.stroke = cfg.colors === "accent" ? accent : ink;
    p.style.strokeWidth = String(sw);
    p.style.vectorEffect = "non-scaling-stroke";
    p.style.strokeDasharray = "1";
    p.style.strokeDashoffset = "1";
  });

  const phases = ctx.data.steps.map((s, i) => (s.intro ? -1 : i)).filter((i) => i >= 0);
  const drawStep = phases[0], fillStep = phases[1];
  const shown = new Float32Array(n).fill(-1), filled = new Float32Array(n).fill(-1);

  return {
    update(s) {
      // without steps, the whole scene progress drives both phases
      const d = drawStep !== undefined ? s.steps[drawStep] ?? 0 : clamp(s.p / 0.6);
      const f = fillStep !== undefined ? s.steps[fillStep] ?? 0 : clamp((s.p - 0.55) / 0.35);
      const de = easeInOut(clamp(d * 1.05)), fe = clamp(f * 1.1);
      for (let i = 0; i < n; i++) {
        const o = i / n;
        const v = clamp((de - o * 0.85) / 0.15);
        if (v !== shown[i]) { shown[i] = v; paths[i].style.strokeDashoffset = String(1 - v); }
        const fv = clamp((fe - o * 0.6) / 0.4);
        if (fv !== filled[i]) { filled[i] = fv; paths[i].style.fillOpacity = String(fv); paths[i].style.strokeOpacity = String(1 - fv * 0.85); }
      }
      const hold = phases.slice(2).reduce((a, i) => a + (s.steps[i] ?? 0), 0);
      svg.style.transform = `scale(${1 + 0.06 * clamp(hold)})`;
    },
  };
};
export default factory;
