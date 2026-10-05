/**
 * artwork: an image drawn and painted in stages. Each non-intro step drives one stage:
 *   guides     construction lines (SVG, dashed, accent colour)
 *   lines      contour strokes drawing themselves (SVG)
 *   value      graphite/tonal layer revealed through a brush-order mask (WebGL)
 *   underpaint monochrome lay-in revealed through its mask (WebGL)
 *   colour     the finished image revealed through its mask (WebGL)
 */
import type { PlayerFactory } from "../lib/types";
import { clamp, easeInOut, loadImage } from "../lib/util";

const NS = "http://www.w3.org/2000/svg";

const factory: PlayerFactory = async (cfg, ctx) => {
  const [W, H] = cfg.size as [number, number];
  const easel = document.createElement("div");
  easel.className = "ss-easel";
  Object.assign(easel.style, { position: "relative", height: "100%", maxWidth: "100%", aspectRatio: `${W} / ${H}`, margin: "0 auto" });
  ctx.visual.style.display = "flex";
  ctx.visual.style.justifyContent = "center";
  ctx.visual.appendChild(easel);

  const canvas = document.createElement("canvas");
  Object.assign(canvas.style, { position: "absolute", inset: "0", width: "100%", height: "100%",
    boxShadow: "0 1px 0 rgba(0,0,0,.04), 0 18px 40px -12px rgba(60,40,20,.35), 0 50px 90px -40px rgba(60,40,20,.35)",
    background: cfg.paper || "#f1ebdf" });
  easel.appendChild(canvas);
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid slice");
  Object.assign(svg.style, { position: "absolute", inset: "0", width: "100%", height: "100%" });
  const guidesG = document.createElementNS(NS, "g"), linesG = document.createElementNS(NS, "g");
  svg.append(guidesG, linesG);
  easel.appendChild(svg);
  const style = document.createElement("style");
  style.textContent = `
    .ss-easel path { fill: none; stroke: ${cfg.ink || "#2b2622"}; stroke-opacity: .88; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
    .ss-easel .g line, .ss-easel .g ellipse, .ss-easel .g rect { fill: none; stroke: var(--accent); stroke-width: 1; vector-effect: non-scaling-stroke; stroke-dasharray: 6 5; }
    .ss-easel .g text { font-family: var(--font-mono); font-size: ${Math.round(W / 70)}px; fill: var(--accent); letter-spacing: .08em; }`;
  easel.appendChild(style);
  guidesG.setAttribute("class", "g");

  // step index -> stage: the n-th non-intro step drives the n-th stage
  const stageStep: Record<string, number> = {};
  let k = 0;
  ctx.data.steps.forEach((st, i) => { if (!st.intro && k < cfg.stages.length) stageStep[cfg.stages[k++]] = i; });
  const sp = (s: number[], name: string) => (name in stageStep ? s[stageStep[name]] ?? 0 : 0);

  // ---------- SVG guides and contour strokes
  let guideEls: { el: SVGGeometryElement; label: SVGTextElement | null; i: number; n: number }[] = [];
  let strokes: { p: SVGPathElement; len: number; start: number; shown: number }[] = [], totalLen = 0;
  const waits: Promise<unknown>[] = [];
  if (cfg.guides) waits.push(fetch(cfg.guides).then((r) => r.json()).then(({ guides }) => {
    guideEls = guides.map((g: any, i: number) => {
      let el: SVGGeometryElement;
      if (g.type === "line") {
        el = document.createElementNS(NS, "line") as SVGGeometryElement;
        el.setAttribute("x1", g.a[0]); el.setAttribute("y1", g.a[1]); el.setAttribute("x2", g.b[0]); el.setAttribute("y2", g.b[1]);
      } else if (g.type === "rect") {
        el = document.createElementNS(NS, "rect") as SVGGeometryElement;
        el.setAttribute("x", g.x); el.setAttribute("y", g.y); el.setAttribute("width", g.w); el.setAttribute("height", g.h);
      } else {
        el = document.createElementNS(NS, "ellipse") as SVGGeometryElement;
        el.setAttribute("cx", g.c[0]); el.setAttribute("cy", g.c[1]); el.setAttribute("rx", g.r[0]); el.setAttribute("ry", g.r[1]);
        el.setAttribute("transform", `rotate(${g.rot || 0} ${g.c[0]} ${g.c[1]})`);
      }
      el.setAttribute("pathLength", "1");
      el.style.strokeDasharray = "1"; el.style.strokeDashoffset = "1";
      guidesG.appendChild(el);
      let label: SVGTextElement | null = null;
      if (g.label && (i === 0 || g.label !== guides[i - 1].label)) {
        label = document.createElementNS(NS, "text");
        label.setAttribute("x", String(g.lx ?? Math.min((g.b?.[0] ?? g.c?.[0] ?? g.x) + 10, W * 0.83)));
        label.setAttribute("y", String(g.ly ?? (g.b?.[1] ?? g.c?.[1] ?? g.y) - 10));
        label.textContent = g.label; label.style.opacity = "0";
        guidesG.appendChild(label);
      }
      return { el, label, i, n: guides.length };
    });
  }));
  if (cfg.lines) waits.push(fetch(cfg.lines).then((r) => r.json()).then(({ strokes: s }) => {
    const frag = document.createDocumentFragment();
    let acc = 0;
    strokes = s.map((st: any) => {
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", st.d);
      p.style.strokeDasharray = `${st.len} ${st.len}`;
      p.style.strokeDashoffset = String(st.len);
      frag.appendChild(p);
      const o = { p, len: st.len, start: acc, shown: -1 };
      acc += st.len;
      return o;
    });
    totalLen = acc;
    linesG.appendChild(frag);
  }));

  // ---------- WebGL layer compositing
  const gl = canvas.getContext("webgl2", { antialias: false, premultipliedAlpha: false, preserveDrawingBuffer: true });
  let uni: Record<string, WebGLUniformLocation | null> | null = null, lastKey = "";
  const L = cfg.layers;
  async function initGL() {
    if (!gl) throw new Error("no webgl2");
    const names = ["paper", "tone", "under", "final", "mask_tone", "mask_under", "mask_color"];
    let n = 0;
    const imgs = await Promise.all(names.map((nm) => loadImage(L[nm]).then((im) => { ctx.progress(++n / names.length * 0.9); return im; })));
    const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader"); return s; };
    const prog = gl.createProgram()!;
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, `#version 300 es
      in vec2 p; out vec2 uv;
      void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, `#version 300 es
      precision highp float;
      in vec2 uv; out vec4 o;
      uniform sampler2D paper, tone, under, fin, mT, mU, mC;
      uniform float pT, pU, pC;
      float rv(float m, float p){ float s = .045; return clamp((p * (1. + s) - m) / s, 0., 1.); }
      void main(){
        vec3 c = texture(paper, uv).rgb;
        c = mix(c, texture(tone, uv).rgb,  rv(texture(mT, uv).r, pT));
        c = mix(c, texture(under, uv).rgb, rv(texture(mU, uv).r, pU));
        c = mix(c, texture(fin, uv).rgb,   rv(texture(mC, uv).r, pC));
        o = vec4(c, 1.);
      }`));
    gl.linkProgram(prog); gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const samplers = ["paper", "tone", "under", "fin", "mT", "mU", "mC"];
    imgs.forEach((im, i) => {
      gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
      gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.uniform1i(gl.getUniformLocation(prog, samplers[i]), i);
    });
    uni = { pT: gl.getUniformLocation(prog, "pT"), pU: gl.getUniformLocation(prog, "pU"), pC: gl.getUniformLocation(prog, "pC") };
    resize();
  }
  function resize() {
    if (!gl || !uni) return;
    const r = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.round(r.width * dpr)); canvas.height = Math.max(1, Math.round(r.height * dpr));
    gl.viewport(0, 0, canvas.width, canvas.height);
    lastKey = "";
  }
  waits.push(initGL().catch((e) => {
    console.warn("[artwork] WebGL unavailable, showing the finished image", e);
    const img = document.createElement("img");
    img.src = L.final;
    Object.assign(img.style, { position: "absolute", inset: "0", width: "100%", height: "100%", objectFit: "cover" });
    easel.insertBefore(img, svg);
  }));
  await Promise.all(waits);

  return {
    resize,
    update(s) {
      const st = s.steps;
      const g = sp(st, "guides"), ln = sp(st, "lines"), tv = sp(st, "value"), un = sp(st, "underpaint"), co = sp(st, "colour");
      if (gl && uni) {
        const key = [tv, un, co].map((v) => v.toFixed(4)).join();
        if (key !== lastKey) {
          gl.uniform1f(uni.pT, easeInOut(tv)); gl.uniform1f(uni.pU, easeInOut(un)); gl.uniform1f(uni.pC, easeInOut(co));
          gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
          lastKey = key;
        }
      }
      for (const ge of guideEls) {
        const local = clamp(g * 1.15 * ge.n - ge.i);
        ge.el.style.strokeDashoffset = String(1 - local);
        if (ge.label) ge.label.style.opacity = local > 0.6 ? "1" : "0";
      }
      guidesG.style.opacity = String(1 - clamp((ln - 0.55) / 0.4));
      if (strokes.length) {
        const drawn = easeInOut(clamp(ln * 1.08)) * totalLen;
        for (const sk of strokes) {
          const v = clamp((drawn - sk.start) / sk.len);
          if (v === sk.shown) continue;
          sk.shown = v;
          sk.p.style.strokeDashoffset = String(sk.len * (1 - v));
        }
      }
      linesG.style.opacity = String((1 - 0.55 * tv) * (1 - clamp(un * 1.4)) * (1 - clamp(co * 2)));
    },
  };
};
export default factory;
