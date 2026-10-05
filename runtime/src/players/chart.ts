/**
 * chart: a data story. Each step has a `state` ({show, focus, x, y, reveal, marks}); scrolling through a step
 * interpolates from the previous state to this one: axes rescale, series fade in or dim, lines draw across,
 * annotation marks appear.
 */
import { axisBottom, axisLeft, format, line as d3line, area as d3area, scaleLinear, scaleLog, select } from "d3";
import type { PlayerFactory } from "../lib/types";
import { clamp, cssVar, easeInOut, lerp } from "../lib/util";

type Pt = [number, number];
interface State { show: string[]; focus: string[]; x: [number, number]; y: [number, number]; reveal: boolean; marks: any[] }

const factory: PlayerFactory = async (cfg, ctx) => {
  const { series } = await (await fetch(cfg.data)).json() as { series: Record<string, Pt[]> };
  const names = Object.keys(series);
  const all = names.flatMap((n) => series[n]);
  const ext = (i: 0 | 1): [number, number] => [Math.min(...all.map((p) => p[i])), Math.max(...all.map((p) => p[i]))];
  const [x0, x1] = ext(0), [, y1] = ext(1);
  const yMin = cfg.yScale === "log" ? Math.max(1e-3, Math.min(...all.map((p) => p[1]).filter((v) => v > 0))) : 0;
  const palette = cfg.colors?.length ? cfg.colors : [cssVar("--accent"), cssVar("--ink"), "#3b82f6", "#10b981", "#a855f7", "#f43f5e", "#14b8a6", "#eab308"];
  const color = (n: string) => palette[names.indexOf(n) % palette.length];

  // per-step states, each filling gaps from the previous one
  const steps = ctx.data.steps;
  const states: State[] = [];
  let prev: State = { show: names.slice(0, 1), focus: [], x: [x0, x1], y: [yMin, y1 * 1.05], reveal: false, marks: [] };
  steps.forEach((s: any) => {
    const st = s.state || {};
    const cur: State = {
      show: st.show ?? prev.show, focus: st.focus ?? [], x: st.x ?? prev.x,
      y: st.y === "auto" || !st.y ? (st.x || st.show ? autoY(st.show ?? prev.show, st.x ?? prev.x) : prev.y) : st.y,
      reveal: !!st.reveal, marks: st.marks ?? [],
    };
    states.push(cur);
    prev = cur;
  });
  function autoY(show: string[], xr: [number, number]): [number, number] {
    const vals = show.flatMap((n) => (series[n] || []).filter((p) => p[0] >= xr[0] && p[0] <= xr[1]).map((p) => p[1]));
    return vals.length ? [yMin, Math.max(...vals) * 1.08] : [yMin, y1];
  }

  // ---------- DOM
  const box = document.createElement("div");
  Object.assign(box.style, { position: "absolute", inset: "0", display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 2%" });
  ctx.visual.appendChild(box);
  const style = document.createElement("style");
  style.textContent = `
    .ss-chart text { font-family: var(--font-mono); font-size: 11px; fill: var(--ink-3); }
    .ss-chart .domain, .ss-chart .tick line { stroke: var(--line); }
    .ss-chart .grid line { stroke: var(--line); stroke-dasharray: 2 4; }
    .ss-chart .lbl { font-family: var(--font-body); font-size: 13px; font-weight: 600; }
    .ss-chart .mark text { font-family: var(--font-body); font-size: 13px; fill: var(--ink); }
    .ss-chart-src { font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); margin-top: 10px; letter-spacing: .04em; }
    .ss-chart-y { font-family: var(--font-mono); font-size: 11px; color: var(--ink-3); letter-spacing: .1em; text-transform: uppercase; margin-bottom: 8px; }`;
  box.appendChild(style);
  if (cfg.yLabel) { const yl = document.createElement("div"); yl.className = "ss-chart-y"; yl.textContent = cfg.yLabel; box.appendChild(yl); }
  const svgEl = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svgEl.setAttribute("class", "ss-chart");
  Object.assign(svgEl.style, { width: "100%", height: "min(70vh, 620px)", overflow: "visible" });
  box.appendChild(svgEl);
  if (cfg.source) { const src = document.createElement("div"); src.className = "ss-chart-src"; src.textContent = "Source: " + cfg.source; box.appendChild(src); }

  const svg = select(svgEl);
  const gGrid = svg.append("g").attr("class", "grid"), gX = svg.append("g"), gY = svg.append("g"), gLines = svg.append("g"), gMarks = svg.append("g");
  const clipId = "clip-" + Math.random().toString(36).slice(2, 8);
  const clipRect = svg.append("defs").append("clipPath").attr("id", clipId).append("rect");
  gLines.attr("clip-path", `url(#${clipId})`);
  const paths = names.map((n) => ({
    n,
    area: gLines.append("path").attr("fill", color(n)).attr("opacity", 0),
    line: gLines.append("path").attr("fill", "none").attr("stroke", color(n)).attr("stroke-width", 2.5).attr("stroke-linejoin", "round"),
    label: svg.append("text").attr("class", "lbl").attr("fill", color(n)).text(n),
  }));
  const fmt = format(",.0f"), fmtSmall = format(",.1f");
  const nice = (v: number) => (Math.abs(v) >= 10 ? fmt(v) : fmtSmall(v)) + (cfg.unit || "");

  let W = 800, H = 500;
  const M = { l: 56, r: 120, t: 12, b: 28 };
  function resize() { const r = svgEl.getBoundingClientRect(); W = r.width || 800; H = r.height || 500; }
  resize();
  const isYear = x1 > 1800 && x1 < 2200;

  function render(st: State, opacity: Record<string, number>, revealX: number, markK: number) {
    const xs = scaleLinear().domain(st.x).range([M.l, W - M.r]);
    const ys = (cfg.yScale === "log" ? scaleLog().domain([Math.max(st.y[0], yMin), st.y[1]]) : scaleLinear().domain(st.y)).range([H - M.b, M.t]).nice();
    gX.attr("transform", `translate(0,${H - M.b})`).call(axisBottom(xs).ticks(6).tickFormat((d: any) => (isYear ? String(d) : fmt(d))) as any);
    gY.attr("transform", `translate(${M.l},0)`).call(axisLeft(ys).ticks(5, cfg.yScale === "log" ? "~s" : undefined).tickFormat((d: any) => nice(+d)) as any);
    gGrid.attr("transform", `translate(${M.l},0)`).call(axisLeft(ys).ticks(5).tickSize(-(W - M.l - M.r)).tickFormat(() => "") as any);
    gGrid.select(".domain").remove();
    clipRect.attr("x", M.l).attr("y", 0).attr("width", Math.max(0, xs(revealX) - M.l)).attr("height", H);
    const ln = d3line<Pt>().x((p) => xs(p[0])).y((p) => ys(Math.max(p[1], cfg.yScale === "log" ? yMin : -Infinity)));
    const ar = d3area<Pt>().x((p) => xs(p[0])).y0(ys(ys.domain()[0])).y1((p) => ys(Math.max(p[1], cfg.yScale === "log" ? yMin : -Infinity)));
    for (const p of paths) {
      const o = opacity[p.n] ?? 0;
      const d = series[p.n];
      p.line.attr("d", ln(d)).attr("opacity", o);
      p.area.attr("d", cfg.kind === "area" ? ar(d) : null).attr("opacity", o * 0.12);
      const visible = d.filter((q) => q[0] <= Math.min(revealX, st.x[1]) && q[0] >= st.x[0]);
      const last = visible[visible.length - 1];
      if (last && o > 0.05) p.label.attr("x", xs(last[0]) + 8).attr("y", ys(Math.max(last[1], yMin)) + 4).attr("opacity", o).text(`${p.n} ${nice(last[1])}`);
      else p.label.attr("opacity", 0);
    }
    const marks = gMarks.selectAll<SVGGElement, any>("g.mark").data(st.marks, (m: any) => `${m.series}-${m.x}`);
    const enter = marks.enter().append("g").attr("class", "mark");
    enter.append("circle").attr("r", 5).attr("fill", "var(--bg)").attr("stroke-width", 2.5);
    enter.append("text").attr("x", 10).attr("y", -10);
    marks.exit().remove();
    gMarks.selectAll<SVGGElement, any>("g.mark").each(function (m: any) {
      const pt = (series[m.series] || []).find((q) => q[0] === m.x);
      if (!pt) return;
      const px = xs(pt[0]);
      const g = select(this).attr("transform", `translate(${px},${ys(Math.max(pt[1], yMin))})`).attr("opacity", markK);
      g.select("circle").attr("stroke", color(m.series));
      const flip = px > W - M.r - 140;   // near the right edge: put the note on the left, clear of the line label
      g.select("text").text(m.label).attr("text-anchor", flip ? "end" : "start").attr("x", flip ? -12 : 10).attr("y", flip ? 18 : -10);
    });
  }

  return {
    resize,
    update(s) {
      let k = 0;
      for (let i = 0; i < steps.length; i++) if ((s.steps[i] ?? 0) > 0) k = i;
      const t = easeInOut(clamp((s.steps[k] ?? 0) / 0.6));
      const a = states[Math.max(0, k - 1)], b = states[k];
      if (!b) return;
      const st: State = {
        show: b.show, focus: b.focus, reveal: b.reveal, marks: b.marks,
        x: [lerp(a.x[0], b.x[0], t), lerp(a.x[1], b.x[1], t)],
        y: [lerp(a.y[0], b.y[0], t), lerp(a.y[1], b.y[1], t)],
      };
      const opacity: Record<string, number> = {};
      for (const n of names) {
        const wasOn = (k === 0 ? [] : a.show).includes(n) ? (a.focus.length && !a.focus.includes(n) ? 0.25 : 1) : 0;
        const isOn = b.show.includes(n) ? (b.focus.length && !b.focus.includes(n) ? 0.25 : 1) : 0;
        opacity[n] = lerp(wasOn, isOn, k === 0 && b.reveal ? 1 : t);
      }
      const revealX = b.reveal ? lerp(st.x[0], st.x[1], easeInOut(clamp((s.steps[k] ?? 0) / 0.75))) : st.x[1];
      render(st, opacity, revealX, clamp(((s.steps[k] ?? 0) - 0.45) / 0.2));
    },
  };
};
export default factory;
