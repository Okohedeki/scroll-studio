/**
 * light: one place relit from dawn to night as you scroll. The build made the same picture at several times of day
 * (geometry locked); here scroll moves continuously through them, and a shader carries the light from one time to the
 * next instead of cross-fading two pictures:
 *   - the low-frequency light change between two times (a smooth field, log-encoded) is applied to both pictures, so
 *     brightness and colour travel together and nothing dips to grey half-way;
 *   - what is left (shadows, the sky's structure, lit and unlit surfaces) is switched by a FRONT of new light that
 *     spreads from where the light arrives (the sun, the moon), reaching the sky first and the near ground last,
 *     with a soft warm edge, so shadows sweep instead of ghosting;
 *   - lamps and windows that turn on (a map from the build) each come on at their own moment, with a halo;
 *   - a sun and a moon glow travel over the sky (clipped to it), mist drifts with distance, and a slow 2.5D drift
 *     through the depth map lets the place breathe;
 *   - the section's colours (ink, accent, the shade behind captions) follow the sky.
 * Reduced motion: one still per step, no drift, no mist movement. No WebGL: the stills as images, one per step.
 */
import { readElements } from "../lib/elements";
import type { PlayerFactory } from "../lib/types";
import { clamp, isMobile, lerp, loadImage, reducedMotion, smooth } from "../lib/util";

const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`;

const FS = `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
uniform sampler2D imgA, imgB, ratioT, lampT, depthT, skyT, flowT;
uniform vec2 sc;            // cover-fit scale
uniform vec2 ctr;           // the picture point the screen's centre looks at
uniform vec3 cam;           // drift x, y and zoom
uniform float strength;     // parallax strength
uniform float focus;        // depth that stays put
uniform float fe;           // progress between the two times, 0-1
uniform float aspect;       // picture width / height
uniform vec2 origin;        // where the new light arrives from, picture uv
uniform float light;        // 1: light-aware transition, 0: plain crossfade
uniform float hasLamp, lampOn, glow;
uniform vec3 lampCol;
uniform float hazeA, hazeB, mistOn;
uniform vec3 fogA, fogB;
uniform vec3 sunCol, edgeCol;
uniform vec2 sunPos;
uniform float sunAmt, sunSize, t;
uniform float vig, grain;

vec3 lin(vec3 c){ return pow(c, vec3(2.2)); }
float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vn(vec2 p){
  vec2 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p){ return .55 * vn(p) + .3 * vn(p * 2.1 + 7.3) + .15 * vn(p * 4.3 + 2.9); }

void main(){
  // 2.5D: solve for the picture point that lands on this pixel (near things move further than far ones)
  vec2 c = (uv - .5) / (sc * cam.z) + ctr;
  vec2 q = c;
  for (int i = 0; i < ITER; i++) { float d = texture(depthT, q).r; q = c - (d - focus) * cam.xy * strength; }
  q = clamp(q, vec2(.001), vec2(.999));

  float d = texture(depthT, q).r;
  float sk = smoothstep(.4, .6, texture(skyT, q).r);          // the sky's edge stays where the roofline is
  // how the place's structure sits differently in the two pictures (the editor redrew it a little): the picture glides
  // along it as the light changes, so edges slide into place instead of cross-fading doubled
  vec3 fl = texture(flowT, q).rgb;
  vec2 F = (fl.rg - .5) * (2. * 24.) * fl.b;
  vec2 Fuv = vec2(F.x / 1024., F.y * aspect / 1024.);
  float s = fe;
  vec3 R = vec3(1.);
  if (light > .5) {
    // the front: new light spreads from its source, sky first, near ground last, ragged edge
    float gr = clamp(length((q - origin) * vec2(aspect, 1.)) / (aspect * .9), 0., 1.);
    float g = .5 * gr + .32 * (1. - d) + .12 * vn(q * vec2(8. * aspect, 8.)) + .06 * q.y;
    g = mix(g, g * .55, sk);
    g = clamp(g, 0., 1.);
    const float w = .42;
    s = smoothstep(g * (1. - w), g * (1. - w) + w, fe);
    // the low-frequency change of light, carried by both pictures to the same in-between light
    R = exp2((texture(ratioT, q).rgb - .5) * 6.);
  }
  vec3 A = lin(texture(imgA, q - s * Fuv).rgb), B = lin(texture(imgB, q + (1. - s) * Fuv).rgb);
  vec3 col, Am = A, Bm = B;
  if (light > .5) {
    Am = A * pow(R, vec3(fe));
    Bm = B * pow(R, vec3(-(1. - fe)));
    col = mix(Am, Bm, s);
    col += edgeCol * (s * (1. - s) * 4.) * .05 * smoothstep(0., .1, fe) * smoothstep(1., .9, fe);
  } else {
    col = mix(A, B, fe);
  }

  // lamps and windows: each its own moment, then a halo
  if (hasLamp > .5) {
    vec4 L = texture(lampT, q);
    float pop = smoothstep(L.g * .6, L.g * .6 + .16, fe);
    vec3 offc = lampOn > .5 ? Am : A;
    vec3 onc = lampOn > .5 ? B : Bm;
    col = mix(col, mix(offc, onc, pop), L.r);
    // the halo is the flash of switching, not a state: the pictures at either end already carry their own glow
    float level = sin(3.14159 * fe);
    col += lampCol * L.b * glow * .45 * level * level;
  }

  // mist: thicker with distance and low on the water, drifting
  if (mistOn > .5) {
    float hz = mix(hazeA, hazeB, fe);
    if (hz > .002) {
      float n = fbm(q * vec2(3.4 * aspect, 2.4) + vec2(t * .010, t * .004));
      float amt = hz * pow(1. - d, 1.25) * (.55 + .7 * n) * mix(.55, 1., smoothstep(.3, .7, q.y));
      col = mix(col, lin(mix(fogA, fogB, fe)), clamp(amt, 0., .85));
    }
  }

  // sun / moon: a glow over the sky only
  if (sunAmt > .002) {
    float dd = length((q - sunPos) * vec2(aspect, 1.));
    float gl = exp(-dd * dd / (2. * sunSize * sunSize)) * .85 + exp(-dd / (sunSize * 2.8)) * .22;
    vec3 add = sunCol * gl * sunAmt * smoothstep(.15, .7, sk);
    col = 1. - (1. - col) * (1. - clamp(add, 0., .95));
  }

  col = pow(max(col, 0.), vec3(1. / 2.2));
  float v = smoothstep(1.2, .4, length((uv - .5) * vec2(1.1, 1.)));
  col *= mix(1., v, vig);
  col += (hash(gl_FragCoord.xy + fract(t) * 17.) - .5) * grain;
  o = vec4(col, 1.);
}`;

type Tok = { bg: number[]; bg2: number[]; ink: number[]; em: number[]; accent: number[]; a2: number; a3: number; dark: boolean; fog?: number[] };
type TimeCfg = { id: string; label: string; clock: string; hours: number; haze: number; lit: boolean; sun: string; img: string; imgS: string; tokens: Tok };
type Pair = { ratio: string; flow?: string | null; lamp: string | null; color: string | null; glow: number; count: number };
type Hold = { t: number; a: number; b: number };

const hex = (h: string): number[] => { const s = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(s.slice(i, i + 2), 16) / 255); };
const mixv = (a: number[], b: number[], k: number) => a.map((v, i) => v + (b[i] - v) * k);
const rgbStr = (c: number[]) => c.map((v) => Math.round(v)).join(", ");

/** Where the light holds still while a step is read, and how it travels between steps: the time index at progress p. */
export function timeAt(p: number, holds: Hold[]): number {
  if (!holds.length) return 0;
  if (p <= holds[0].a) return holds[0].t;
  for (let i = 0; i < holds.length; i++) {
    const h = holds[i];
    if (p <= h.b) return h.t;
    const n = holds[i + 1];
    if (!n) return h.t;
    if (p < n.a) return lerp(h.t, n.t, smooth(h.b, n.a, p));
  }
  return holds[holds.length - 1].t;
}

/** The sun's (or, after dark, the moon's) place on its arc for an hour of the day: picture uv, how high (0-1), and which. */
export function celestial(h: number, sun: any): { x: number; y: number; k: number; u: number; moon: boolean } {
  const rise = sun.rise, noon = sun.noon, set = sun.set;
  const ctrl = [2 * noon[0] - 0.5 * (rise[0] + set[0]), 2 * noon[1] - 0.5 * (rise[1] + set[1])];
  const day = h >= 5.5 && h <= 20.5;
  const hh = h < 5.5 ? h + 24 : h;
  const u = clamp(day ? (h - 5.5) / 15 : (hh - 20.5) / 9);
  const x = (1 - u) * (1 - u) * rise[0] + 2 * u * (1 - u) * ctrl[0] + u * u * set[0];
  const y = (1 - u) * (1 - u) * rise[1] + 2 * u * (1 - u) * ctrl[1] + u * u * set[1];
  return { x, y, k: Math.sin(Math.PI * u), u, moon: !day };
}

const factory: PlayerFactory = async (cfg, ctx) => {
  const times: TimeCfg[] = cfg.times;
  const pairs: Pair[] = cfg.pairs;
  const holds: Hold[] = cfg.holds;
  const nT = times.length;
  const small = isMobile() || innerWidth < 900;
  const still = reducedMotion;

  // ---- the clock and sun-arc in a corner
  let hud: HTMLElement | null = null, hudTime: HTMLElement | null = null, hudLabel: HTMLElement | null = null, hudDot: SVGElement | null = null;
  const dots: HTMLElement[] = [];
  if (cfg.clock) {
    hud = document.createElement("div");
    hud.className = "ss-tod";
    hud.setAttribute("aria-hidden", "true");
    hud.innerHTML = `<svg viewBox="0 0 64 34" width="64" height="34"><path d="M4 31 Q32 -12 60 31" fill="none" stroke="currentColor" stroke-width="1" opacity=".45"/>` +
      `<line x1="2" y1="31" x2="62" y2="31" stroke="currentColor" stroke-width="1" opacity=".45"/><circle class="ss-tod__dot" r="3.6" cx="4" cy="31"/></svg>` +
      `<div class="ss-tod__t"><b class="ss-tod__time">--:--</b><span class="ss-tod__label"></span></div>` +
      `<div class="ss-tod__ticks">${times.map(() => "<i></i>").join("")}</div>`;
    ctx.visual.appendChild(hud);
    hudTime = hud.querySelector(".ss-tod__time"); hudLabel = hud.querySelector(".ss-tod__label");
    hudDot = hud.querySelector(".ss-tod__dot"); dots.push(...hud.querySelectorAll<HTMLElement>(".ss-tod__ticks i"));
  }
  const setHud = (tau: number, sunCfg: any) => {
    if (!hud) return;
    const a = Math.min(nT - 2, Math.max(0, Math.floor(tau))), f = clamp(tau - a);
    const hrs = lerp(times[a].hours, times[Math.min(nT - 1, a + 1)].hours, f);
    const hh = ((hrs % 24) + 24) % 24, m = Math.floor((hh % 1) * 60);
    hudTime!.textContent = `${String(Math.floor(hh)).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
    const near = Math.round(tau);
    hudLabel!.textContent = times[Math.min(nT - 1, Math.max(0, near))].label;
    dots.forEach((d, i) => d.classList.toggle("on", i === near));
    if (hudDot) {
      const c = celestial(hrs, sunCfg || { rise: [0.1, 0.5], noon: [0.5, 0.06], set: [0.92, 0.5] });
      hudDot.setAttribute("cx", (4 + 56 * c.u).toFixed(1));
      hudDot.setAttribute("cy", (31 - Math.sin(Math.PI * c.u) * 21.5).toFixed(1));
      hudDot.classList.toggle("moon", c.moon);
    }
  };

  // ---- the section's colours follow the sky
  const sec = ctx.section;
  let lastTok = -1;
  const applyTokens = (tau: number) => {
    if (!cfg.follow || Math.abs(tau - lastTok) < 0.003) return;
    lastTok = tau;
    const a = Math.min(nT - 1, Math.max(0, Math.floor(tau))), b = Math.min(nT - 1, a + 1), f = clamp(tau - a);
    const A = times[a].tokens, B = times[b].tokens;
    // the veil colour follows the light; the ink does not pass through grey: it holds its own side and flips across the middle
    const k = smooth(0.4, 0.6, f);
    const bg = mixv(A.bg, B.bg, f), bg2 = mixv(A.bg2, B.bg2, f), ink = mixv(A.ink, B.ink, k), em = mixv(A.em, B.em, k), ac = mixv(A.accent, B.accent, k);
    const a2 = lerp(A.a2, B.a2, k), a3 = lerp(A.a3, B.a3, k), st = sec.style;
    st.setProperty("--bg", `rgb(${rgbStr(bg)})`); st.setProperty("--bg-2", `rgb(${rgbStr(bg2)})`);
    st.setProperty("--bg-rgb", rgbStr(bg)); st.setProperty("--ink", `rgb(${rgbStr(ink)})`); st.setProperty("--ink-rgb", rgbStr(ink));
    st.setProperty("--ink-2", `rgba(${rgbStr(ink)}, ${a2.toFixed(2)})`); st.setProperty("--ink-3", `rgba(${rgbStr(ink)}, ${a3.toFixed(2)})`);
    st.setProperty("--line", `rgba(${rgbStr(ink)}, .14)`);
    st.setProperty("--accent", `rgb(${rgbStr(ac)})`); st.setProperty("--accent-text", `rgb(${rgbStr(ac)})`); st.setProperty("--em-color", `rgb(${rgbStr(em)})`);
    sec.dataset.tod = times[Math.round(tau) < 0 ? 0 : Math.min(nT - 1, Math.round(tau))].id;
  };

  // each headline keeps the colours of its own time of day, so its ink never passes through grey while the light changes
  const els = readElements(sec, ctx.data);          // which step each caption is, and its window (lib/elements.ts)
  const capEls = [...sec.querySelectorAll<HTMLElement>(".ss-caption")];
  const cardEls = [...sec.querySelectorAll<HTMLElement>(".ss-step")];
  const tint = (el: HTMLElement | undefined, ti: number) => {
    if (!el || !cfg.follow) return;
    const T = times[Math.max(0, Math.min(nT - 1, ti))].tokens, st = el.style;
    st.setProperty("--ink", `rgb(${rgbStr(T.ink)})`); st.setProperty("--ink-rgb", rgbStr(T.ink)); st.setProperty("--bg-rgb", rgbStr(T.bg));
    st.setProperty("--ink-2", `rgba(${rgbStr(T.ink)}, ${T.a2.toFixed(2)})`); st.setProperty("--ink-3", `rgba(${rgbStr(T.ink)}, ${T.a3.toFixed(2)})`);
    st.setProperty("--accent", `rgb(${rgbStr(T.accent)})`); st.setProperty("--accent-text", `rgb(${rgbStr(T.accent)})`); st.setProperty("--em-color", `rgb(${rgbStr(T.em)})`);
    st.setProperty("--line", `rgba(${rgbStr(T.ink)}, .14)`);
  };
  capEls.forEach((el, k) => tint(el, cfg.stepTimes[els[k]?.step ?? k] ?? 0));
  cardEls.forEach((el, k) => tint(el, cfg.stepTimes[k] ?? 0));

  // the shade behind the text is there while a headline is: between headlines the picture is left bare
  const wins: [number, number][] = els.map((e) => e.show);
  let lastShade = -1;
  const shade = (p: number) => {
    if (sec.dataset.layout === "cards" || (ctx.data as any).layout !== "overlay") return;
    let v = 0;
    for (const [a, b] of wins) v = Math.max(v, smooth(a - 0.05, a + 0.01, p) * (1 - smooth(b - 0.01, b + 0.05, p)));
    if (Math.abs(v - lastShade) > 0.004) { lastShade = v; sec.style.setProperty("--shade", v.toFixed(3)); }
  };

  // ---- no WebGL: the stills, one per step
  const canvas = document.createElement("canvas");
  const gl0 = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true });
  if (!gl0) {
    const imgs: HTMLImageElement[] = [];
    await Promise.all(times.map(async (t, i) => {
      const im = await loadImage(small ? t.imgS : t.img);
      im.className = "ss-light-still"; im.alt = ""; im.style.opacity = i === 0 ? "1" : "0";
      im.style.objectPosition = `${(cfg.focus?.[0] ?? 0.5) * 100}% ${(cfg.focus?.[1] ?? 0.5) * 100}%`;
      ctx.visual.appendChild(im); imgs[i] = im;
    }));
    return {
      update(s) {
        const tau = Math.round(timeAt(s.p, holds));
        imgs.forEach((im, i) => { im.style.opacity = i === tau ? "1" : "0"; });
        applyTokens(tau); setHud(tau, cfg.sun); shade(s.p);
      },
    };
  }
  const gl: WebGL2RenderingContext = gl0;
  ctx.visual.insertBefore(canvas, ctx.visual.firstChild);
  canvas.setAttribute("aria-hidden", "true");

  const iter = small ? 4 : 6;
  const sh = (type: number, src: string) => {
    const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader");
    return s;
  };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS.replace("ITER", String(iter))));
  gl.linkProgram(prog); gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U: Record<string, WebGLUniformLocation | null> = {};
  for (const n of ["imgA", "imgB", "ratioT", "lampT", "depthT", "skyT", "flowT", "sc", "ctr", "cam", "strength", "focus", "fe", "aspect", "origin", "light",
    "hasLamp", "lampOn", "glow", "lampCol", "hazeA", "hazeB", "mistOn", "fogA", "fogB", "sunCol", "edgeCol", "sunPos", "sunAmt", "sunSize", "t", "vig", "grain"]) U[n] = gl.getUniformLocation(prog, n);
  ["imgA", "imgB", "ratioT", "lampT", "depthT", "skyT", "flowT"].forEach((n, i) => gl.uniform1i(U[n], i));

  const tex = (im: HTMLImageElement, mip: boolean, linear = true) => {
    const t = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im);
    if (mip) gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mip ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, linear ? gl.LINEAR : gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  };
  const blank = (rgba: number[]) => {
    const t = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(rgba));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    return t;
  };
  const noLamp = blank([0, 0, 0, 255]), flatRatio = blank([128, 128, 128, 255]), noFlow = blank([128, 128, 0, 255]);

  const total = nT * 1 + pairs.length * 3 + 2;
  let loaded = 0;
  const tick = () => ctx.progress(++loaded / total);
  const imgT: WebGLTexture[] = [];
  const ratioT: WebGLTexture[] = [], lampT: (WebGLTexture | null)[] = [], flowT: (WebGLTexture | null)[] = [];
  let depthT: WebGLTexture = blank([128, 128, 128, 255]), skyT: WebGLTexture = blank([0, 0, 0, 255]);
  let aspect = cfg.w / cfg.h;
  await Promise.all([
    ...times.map(async (t, i) => { const im = await loadImage(small ? t.imgS : t.img); imgT[i] = tex(im, true); aspect = cfg.w / cfg.h; tick(); }),
    ...pairs.map(async (pr, k) => { const im = await loadImage(pr.ratio); ratioT[k] = tex(im, false); tick(); }),
    ...pairs.map(async (pr, k) => { lampT[k] = pr.lamp ? tex(await loadImage(pr.lamp), false) : null; tick(); }),
    ...pairs.map(async (pr, k) => { flowT[k] = pr.flow ? tex(await loadImage(pr.flow), false) : null; tick(); }),
    loadImage(cfg.depth).then((im) => { depthT = tex(im, false); tick(); }),
    loadImage(cfg.sky).then((im) => { skyT = tex(im, false); tick(); }),
  ]);

  let cw = 1, ch = 1;
  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, small ? 1.5 : 2);
    cw = canvas.width = Math.max(1, Math.round(r.width * dpr)); ch = canvas.height = Math.max(1, Math.round(r.height * dpr));
    gl!.viewport(0, 0, cw, ch);
  }
  resize();
  const bind = (unit: number, t: WebGLTexture) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t); };
  const sunCfg = cfg.sun;
  let px = 0, py = 0;

  function sunUniforms(hours: number, haveSun: boolean) {
    if (!haveSun || !sunCfg) { gl.uniform1f(U.sunAmt, 0); gl.uniform2f(U.sunPos, 0.5, 0.2); return { x: 0.5, y: 0.3 }; }
    const c = celestial(hours, sunCfg);
    const col = c.moon ? [0.62, 0.74, 1.0] : mixv([1.0, 0.52, 0.22], [1.0, 0.93, 0.8], smooth(0.05, 0.5, c.k));
    const amt = (c.moon ? 0.32 : 0.55 + 0.25 * (1 - c.k)) * sunCfg.strength * smooth(0.02, 0.18, c.k);
    gl.uniform2f(U.sunPos, c.x, c.y);
    gl.uniform3f(U.sunCol, col[0], col[1], col[2]);
    gl.uniform1f(U.sunAmt, amt);
    gl.uniform1f(U.sunSize, 0.05 * sunCfg.size);
    return c;
  }

  return {
    resize,
    update(s) {
      const tau = clamp(still ? Math.round(timeAt(s.p, holds)) : timeAt(s.p, holds), 0, nT - 1);
      const a = Math.min(nT - 2, Math.max(0, Math.floor(tau + 1e-6))), f = clamp(tau - a);
      const A = times[a], B = times[a + 1], pr = pairs[a];
      // 2.5D drift: a slow idle breath, a push-in and a sideways dolly over the day
      px += (s.mx - px) * 0.05; py += (s.my - py) * 0.05;
      const dr = still ? 0 : cfg.drift;
      const idle = still ? 0 : s.t;
      const cx = dr * (0.012 * Math.sin(idle * 0.11) + 0.016 * (s.p - 0.5)) + px * 0.01 * dr;
      const cy = dr * (0.006 * Math.cos(idle * 0.083)) + py * 0.006 * dr;
      const zoom = 1.035 + dr * 0.025 * (tau / Math.max(1, nT - 1)) + dr * 0.004 * Math.sin(idle * 0.07);
      bind(0, imgT[a]); bind(1, imgT[a + 1]); bind(2, ratioT[a] || flatRatio); bind(3, lampT[a] || noLamp); bind(4, depthT); bind(5, skyT); bind(6, flowT[a] || noFlow);
      const ca = cw / ch;
      const sx = ca > aspect ? 1 : aspect / ca, sy = ca > aspect ? ca / aspect : 1, fo = cfg.focus || [0.5, 0.5];
      gl.uniform2f(U.sc, sx, sy);
      gl.uniform2f(U.ctr, clamp(fo[0], 0.5 / (sx * 1.04), 1 - 0.5 / (sx * 1.04)), clamp(fo[1], 0.5 / (sy * 1.04), 1 - 0.5 / (sy * 1.04)));
      gl.uniform3f(U.cam, cx, cy, zoom);
      gl.uniform1f(U.strength, 1.0); gl.uniform1f(U.focus, 0.55);
      gl.uniform1f(U.fe, f); gl.uniform1f(U.aspect, aspect);
      gl.uniform1f(U.light, cfg.blend === "light" ? 1 : 0);
      // the sun/moon: only by day or when the times say so; its glow also tells the front where the light arrives
      const hours = lerp(A.hours, B.hours, f);
      const c: any = sunUniforms(hours, !!sunCfg);
      const orig = B.sun === "none" && A.sun === "none" ? { x: 0.5, y: 0.9 } : celestial(B.hours, sunCfg || { rise: [0.1, 0.5], noon: [0.5, 0.06], set: [0.92, 0.5] });
      gl.uniform2f(U.origin, orig.x, orig.y);
      const edge = B.tokens.em.map((v) => v / 255);
      gl.uniform3f(U.edgeCol, edge[0], edge[1], edge[2]);
      const hasLamp = !!lampT[a] && pr.lamp;
      gl.uniform1f(U.hasLamp, hasLamp ? 1 : 0);
      if (hasLamp) {
        const col = hex(pr.color || "#ffb35c");
        gl.uniform3f(U.lampCol, col[0], col[1], col[2]);
        gl.uniform1f(U.glow, pr.glow);
        gl.uniform1f(U.lampOn, B.lit && !A.lit ? 1 : A.lit && !B.lit ? 0 : 1);
      }
      gl.uniform1f(U.mistOn, cfg.mist ? 1 : 0);
      gl.uniform1f(U.hazeA, A.haze); gl.uniform1f(U.hazeB, B.haze);
      const fa = A.tokens.fog || A.tokens.bg, fb = B.tokens.fog || B.tokens.bg;
      gl.uniform3f(U.fogA, fa[0] / 255, fa[1] / 255, fa[2] / 255); gl.uniform3f(U.fogB, fb[0] / 255, fb[1] / 255, fb[2] / 255);
      gl.uniform1f(U.t, still ? 0 : s.t);
      gl.uniform1f(U.vig, 0.3); gl.uniform1f(U.grain, 0.012);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      void c;
      applyTokens(tau); setHud(tau, sunCfg); shade(s.p);
    },
  };
};
export default factory;
