/**
 * stages: one subject through its states. The build made one still per state, every one the same view; here the scroll
 * holds on each stage while its step is read and reveals the next over it between steps:
 *   - fade: the whole picture at once; wipe: a straight front along an angle; map: each pixel arrives when the scroll
 *     reaches its grey in a map picture (black first), so parts land one by one;
 *   - a band of light can travel with the front (a scanning head, a band of heat), only where the picture changes or
 *     across all of it;
 *   - the pictures sit in the stage cropped (cover) or whole (contain), with their own framing on a phone, a slow
 *     push-in over the scene and an idle breath;
 *   - the pointer lens (lib/pointer.ts) shows on the last stage, as the sequence arrives there.
 * Reduced motion: one still per step. No WebGL: the stills as images, one per step.
 */
import type { PlayerFactory } from "../lib/types";
import { clamp, cssVar, hexToRgb, isMobile, loadImage, reducedMotion, smooth } from "../lib/util";
import { baseGlsl, POINTER_GLSL, pointerEnv, readPointer, trackPointer, uniforms as pointerUniforms } from "../lib/pointer";

type Hold = { t: number; a: number; b: number };
type Front = { color: string; width: number; strength: number; where: "change" | "all" };
type Reveal = { kind: "none" | "fade" | "wipe" | "map"; angle: number; soft: number; map?: string; front?: Front };
type StageCfg = { id: string; img: string; imgS: string; reveal: Reveal };
type Frame = { fit: "cover" | "contain"; position: [number, number]; zoom: number };

/** The stage (fractional: 2.5 is half-way through revealing stage 3 over stage 2) at scene progress p: still through each
 * hold, easing to the next step's stage between holds. The twin of `stage_at` in engine/scenes/stages.py. */
export function stageAt(p: number, holds: Hold[]): number {
  if (!holds.length) return 0;
  if (p <= holds[0].a) return holds[0].t;
  for (let i = 0; i < holds.length; i++) {
    const h = holds[i];
    if (p <= h.b || i + 1 >= holds.length) return h.t;
    const n = holds[i + 1];
    if (p < n.a) return h.t + (n.t - h.t) * smooth(h.b, n.a, p);
  }
  return holds[holds.length - 1].t;
}

/** How far a pixel at `s` (its place along the front's travel, 0-1) has been revealed when the reveal is `f` (0-1) of the
 * way through, with a soft edge `soft` wide: 0 before the front reaches it, 1 after. The front starts just before 0 and
 * ends just after 1, so f = 0 shows none of the new stage and f = 1 all of it. The twin of the shader's `reveal`. */
export function revealAt(s: number, f: number, soft: number): number {
  if (f >= 1) return 1;
  const w = Math.max(soft, 1e-3);
  return smooth(s, s + w, f * (1 + w));
}

/** Where a front's band is brightest for a pixel at `s`: a soft bump around the front itself (0 away from it, and 0 once
 * the reveal is complete or not yet begun). */
export function frontAt(s: number, f: number, soft: number, width: number): number {
  if (f <= 0 || f >= 1) return 0;
  const w = Math.max(soft, 1e-3), x = f * (1 + w) - w * 0.5;
  const d = (x - s) / Math.max(width, 1e-3);
  return Math.exp(-d * d);
}

/** The uv transform that puts a W x H picture into a cw x ch stage: the picture's scale per screen axis (as uv = (screen
 * uv - offset) * scale + 0.5), for cover (fill, cropping) or contain (whole, placed at `position`). */
export function fitTransform(fr: Frame, cw: number, ch: number, w: number, h: number): { sx: number; sy: number; ox: number; oy: number } {
  const ca = cw / Math.max(ch, 1), ia = w / Math.max(h, 1);
  const z = Math.max(0.05, fr.zoom);
  // shown size of the picture in stage units (1 = the stage's width / height)
  let pw: number, ph: number;
  if ((fr.fit === "cover") === (ca > ia)) { pw = 1; ph = ca / ia; } else { pw = ia / ca; ph = 1; }
  pw *= z; ph *= z;
  // where the picture's centre sits on the stage: contain places it at `position` inside the free room; cover keeps the
  // picture point `position` in view as near the middle as the crop allows
  let cx: number, cy: number;
  if (fr.fit === "contain" && z <= 1.0001) {
    cx = pw / 2 + (1 - pw) * fr.position[0]; cy = ph / 2 + (1 - ph) * fr.position[1];
  } else {
    const fx = (fr.position[0] - 0.5) * pw, fy = (fr.position[1] - 0.5) * ph;
    cx = 0.5 - clamp(fx, -(pw - 1) / 2, (pw - 1) / 2) * (pw >= 1 ? 1 : 0);
    cy = 0.5 - clamp(fy, -(ph - 1) / 2, (ph - 1) / 2) * (ph >= 1 ? 1 : 0);
    if (pw < 1) cx = pw / 2 + (1 - pw) * fr.position[0];
    if (ph < 1) cy = ph / 2 + (1 - ph) * fr.position[1];
  }
  return { sx: 1 / pw, sy: 1 / ph, ox: cx, oy: cy };
}

const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`;

function fragment(ptr: ReturnType<typeof readPointer>): string {
  return `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
#define PTR_MODE ${ptr ? (ptr.mode === "light" ? 2 : 1) : 0}
#define PTR_LAYER ${ptr?.layer === "picture" ? 2 : 1}
uniform sampler2D imgA, imgB, mapT, layT;
uniform vec4 fitT;            // sx, sy, ox, oy: picture uv = (uv - o) * s + .5
uniform vec3 cam;             // drift x, y and zoom
uniform float f;              // reveal progress of stage B over A, 0-1
uniform int kind;             // 0 none, 1 fade, 2 wipe, 3 map
uniform vec2 dir;             // wipe direction
uniform float soft;
uniform vec3 frontCol; uniform float frontW, frontS, frontAll, hasFront;
uniform vec3 bg;              // the stage's background, outside a contained picture
uniform float ptrOn, hasLay;
${ptr ? POINTER_GLSL : ""}
${ptr ? `vec3 ptrBase(vec3 c, vec3 bl) { return ${baseGlsl(ptr.base)}; }` : ""}
void main(){
  vec2 q = (uv - fitT.zw) * fitT.xy / cam.z + .5 + cam.xy;
  float inside = step(0., q.x) * step(q.x, 1.) * step(0., q.y) * step(q.y, 1.);
  vec2 qc = clamp(q, vec2(.0005), vec2(.9995));
  vec3 A = texture(imgA, qc).rgb, B = texture(imgB, qc).rgb;
  float s = 0.;
  if (kind == 2) { vec2 d = normalize(dir); float lo = min(0., d.x) + min(0., d.y), hi = max(0., d.x) + max(0., d.y); s = (dot(qc, d) - lo) / max(hi - lo, 1e-4); }
  else if (kind == 3) s = texture(mapT, qc).r;
  float w = max(soft, 1e-3);
  float m = kind == 1 ? f : (f >= 1. ? 1. : smoothstep(s, s + w, f * (1. + w)));
  if (kind == 0) m = 0.;
  vec3 col = mix(A, B, m);
  if (hasFront > .5 && kind >= 2 && f > 0. && f < 1.) {
    float x = f * (1. + w) - w * .5;
    float dd = (x - s) / max(frontW, 1e-3);
    float band = exp(-dd * dd);
    // all: across the subject (not the stage's own background around it); change: only where the picture changes
    float subject = max(smoothstep(.03, .1, length(A - bg)), smoothstep(.03, .1, length(B - bg)));
    float change = frontAll > .5 ? subject : smoothstep(.03, .12, length(B - A));
    col += frontCol * band * change * frontS * (1. - col * .5);
  }
#if PTR_MODE == 1
  float lm = ptrLens(q) * uPtrStr * ptrOn;
  if (lm > .0005 || ptrOn > .001) {
    vec3 outside = ptrBase(col, col);
    outside = mix(col, outside, ptrOn);
#if PTR_LAYER == 2
    col = hasLay > .5 ? mix(col, ptrRim(mix(outside, texture(layT, qc).rgb, lm), q), ptrOn) : col;
#else
    col = mix(col, ptrRim(mix(outside, col, lm), q), ptrOn);
#endif
  }
#elif PTR_MODE == 2
  col = mix(col, ptrLight(col, q, 1., vec2(0.)), ptrOn);
#endif
  o = vec4(mix(bg, col, inside), 1.);
}`;
}

const factory: PlayerFactory = async (cfg, ctx) => {
  const stages: StageCfg[] = cfg.stages;
  const holds: Hold[] = cfg.holds;
  const nS = stages.length;
  const small = isMobile() || innerWidth < 900;
  const frame: Frame = isMobile() ? cfg.phone : cfg.fit;
  const still = reducedMotion;
  const poster = ctx.visual.querySelector<HTMLImageElement>(".ss-poster");
  const place = (im: HTMLImageElement) => {
    im.style.objectFit = frame.fit;
    im.style.objectPosition = `${frame.position[0] * 100}% ${frame.position[1] * 100}%`;
    if (frame.zoom !== 1) im.style.transform = `scale(${frame.zoom})`;
  };
  if (poster) place(poster);

  // ---- no WebGL, or reduced motion without it: the stills, one per step
  const canvas = document.createElement("canvas");
  const gl0 = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true });
  if (!gl0) {
    const imgs: HTMLImageElement[] = [];
    await Promise.all(stages.map(async (st, i) => {
      const im = await loadImage(small ? st.imgS : st.img);
      im.alt = ""; im.className = "ss-stage-still"; im.style.opacity = i === 0 ? "1" : "0"; im.style.transition = "opacity .5s";
      place(im); ctx.visual.appendChild(im); imgs[i] = im;
      ctx.progress((i + 1) / nS);
    }));
    return { update(s) { const k = Math.round(stageAt(s.p, holds)); imgs.forEach((im, i) => { im.style.opacity = i === k ? "1" : "0"; }); } };
  }
  const gl: WebGL2RenderingContext = gl0;
  ctx.visual.insertBefore(canvas, ctx.visual.firstChild);
  canvas.setAttribute("aria-hidden", "true");
  const ptr = readPointer(ctx.section, cfg);

  const sh = (type: number, src: string) => {
    const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader");
    return s;
  };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fragment(ptr)));
  gl.linkProgram(prog); gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U: Record<string, WebGLUniformLocation | null> = {};
  for (const n of ["imgA", "imgB", "mapT", "layT", "fitT", "cam", "f", "kind", "dir", "soft", "frontCol", "frontW", "frontS", "frontAll", "hasFront",
    "bg", "ptrOn", "hasLay", "uPtrC", "uPtrR", "uPtrAsp", "uPtrSoft", "uPtrStr", "uPtrCol"]) U[n] = gl.getUniformLocation(prog, n);
  ["imgA", "imgB", "mapT", "layT"].forEach((n, i) => gl.uniform1i(U[n], i));
  if (ptr) { gl.uniform1f(U.uPtrSoft, ptr.softness); gl.uniform1f(U.uPtrStr, ptr.strength); gl.uniform3fv(U.uPtrCol, ptr.color); }

  const tex = (im: TexImageSource | null, mip = true) => {
    const t = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, t);
    if (im) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im);
    else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]));
    if (im && mip) gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, im && mip ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  };
  const blank = tex(null);
  const imgT: WebGLTexture[] = [], mapT: (WebGLTexture | null)[] = [];
  let layT: WebGLTexture | null = null;
  const layUrl: string | null = ptr?.layer === "picture" ? (ptr.layers[0] ?? null) : null;
  const total = nS + stages.filter((s) => s.reveal.map).length + (layUrl ? 1 : 0);
  let loaded = 0;
  const tick = () => ctx.progress(++loaded / Math.max(1, total));
  await Promise.all([
    ...stages.map(async (st, i) => { imgT[i] = tex(await loadImage(small ? st.imgS : st.img)); tick(); }),
    ...stages.map(async (st, i) => { mapT[i] = st.reveal.map ? tex(await loadImage(st.reveal.map), false) : null; if (st.reveal.map) tick(); }),
    layUrl ? loadImage(layUrl).then((im) => { layT = tex(im); tick(); }).catch(() => { layT = null; tick(); }) : Promise.resolve(),
  ]);

  // the lens rests on a point of the picture (`rest`, 0-1 of it), wherever the frame puts the picture on this screen
  const restPic: [number, number] | null = ptr ? [ptr.rest[0], ptr.rest[1]] : null;
  const track = ptr ? trackPointer(canvas, ptr, pointerEnv()) : null;
  let cw = 1, ch = 1;
  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    cw = canvas.width = Math.max(1, Math.round(r.width * dpr)); ch = canvas.height = Math.max(1, Math.round(r.height * dpr));
    gl.viewport(0, 0, cw, ch);
    if (ptr && restPic) {
      const ft = fitTransform(frame, cw, ch, cfg.w, cfg.h);
      ptr.rest[0] = clamp((restPic[0] - 0.5) / ft.sx + ft.ox); ptr.rest[1] = clamp((restPic[1] - 0.5) / ft.sy + ft.oy);
      if (track) { track.pos[0] = ptr.rest[0]; track.pos[1] = ptr.rest[1]; }
    }
    track?.dirty();
  }
  resize();
  const bind = (unit: number, t: WebGLTexture) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t); };
  const bgOf = (): number[] => {
    const v = (getComputedStyle(ctx.section).getPropertyValue("--bg") || cssVar("--bg")).trim(), m = v.match(/\d+(\.\d+)?/g);
    return v.startsWith("#") ? hexToRgb(v) : m && m.length >= 3 ? m.slice(0, 3).map((c) => +c / 255) : [1, 1, 1];
  };
  const bgCol = bgOf();
  let drawn = "";

  return {
    resize,
    update(s) {
      const tau = clamp(still ? Math.round(stageAt(s.p, holds)) : stageAt(s.p, holds), 0, nS - 1);
      const a = Math.min(nS - 2, Math.max(0, Math.floor(tau + 1e-6))), f = clamp(tau - a);
      const B = stages[a + 1];
      const r = B.reveal;
      const dr = still ? 0 : cfg.drift;
      const idle = still ? 0 : s.t;
      const cx = dr * 0.004 * Math.sin(idle * 0.11), cy = dr * 0.003 * Math.cos(idle * 0.083);
      const zoom = 1 + dr * 0.05 * s.p + dr * 0.003 * Math.sin(idle * 0.07);
      // the lens comes in as the sequence arrives at its last stage
      const ptrOn = ptr ? smooth(nS - 1.35, nS - 1, tau) : 0;
      const moved = track ? track.update(s.t) : false;
      const key = `${a}|${f.toFixed(4)}|${zoom.toFixed(5)}|${cx.toFixed(5)}|${cy.toFixed(5)}|${ptrOn.toFixed(3)}|${track ? track.pos.join(",") : ""}|${cw}x${ch}`;
      if (key === drawn && !moved) return;
      drawn = key;
      bind(0, imgT[a]); bind(1, imgT[a + 1]); bind(2, mapT[a + 1] || blank); bind(3, layT || blank);
      const ft = fitTransform(frame, cw, ch, cfg.w, cfg.h);
      gl.uniform4f(U.fitT, ft.sx, ft.sy, ft.ox, ft.oy);
      gl.uniform3f(U.cam, cx, cy, zoom);
      gl.uniform1f(U.f, f);
      gl.uniform1i(U.kind, { none: 0, fade: 1, wipe: 2, map: 3 }[r.kind] ?? 1);
      const ang = (r.angle * Math.PI) / 180;
      gl.uniform2f(U.dir, Math.cos(ang), Math.sin(ang));
      gl.uniform1f(U.soft, r.soft);
      const fr = r.front;
      gl.uniform1f(U.hasFront, fr ? 1 : 0);
      if (fr) {
        const c = hexToRgb(fr.color);
        gl.uniform3f(U.frontCol, c[0], c[1], c[2]); gl.uniform1f(U.frontW, fr.width); gl.uniform1f(U.frontS, fr.strength);
        gl.uniform1f(U.frontAll, fr.where === "all" ? 1 : 0);
      }
      gl.uniform3f(U.bg, bgCol[0], bgCol[1], bgCol[2]);
      gl.uniform1f(U.ptrOn, ptrOn); gl.uniform1f(U.hasLay, layT ? 1 : 0);
      if (track && ptr) {
        // the lens's centre in picture uv: the screen point through the same fit and camera as the picture
        const rc = canvas.getBoundingClientRect();
        const pu = pointerUniforms(track.pos, ptr.radius, rc, null);
        const px = (track.pos[0] - ft.ox) * ft.sx / zoom + 0.5 + cx, py = (track.pos[1] - ft.oy) * ft.sy / zoom + 0.5 + cy;
        gl.uniform2f(U.uPtrC, px, py);
        gl.uniform1f(U.uPtrR, pu.radius * ft.sy / zoom);
        gl.uniform1f(U.uPtrAsp, cfg.w / cfg.h);
      }
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    },
  };
};
export default factory;
