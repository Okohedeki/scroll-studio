/**
 * parallax: each photo + its estimated depth map becomes a 2.5D camera move. One chapter per non-intro
 * step; chapters crossfade as the next step begins. Pointer adds a little look-around.
 */
import type { PlayerFactory } from "../lib/types";
import { clamp, easeInOut, loadImage, smooth } from "../lib/util";

const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`;

const FS = `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
uniform sampler2D imgA, depA, imgB, depB;
uniform vec2 scaleA, scaleB;      // cover-fit uv scale per image
uniform vec3 camA, camB;          // x, y offset and zoom per chapter
uniform float mixAB, strength, focusA, focusB;
uniform float grade;              // 0..1 vignette amount

vec3 sampleView(sampler2D img, sampler2D dep, vec2 sc, vec3 cam, float focus){
  vec2 c = (uv - .5) / (sc * cam.z) + .5;
  vec2 dir = cam.xy * strength;
  // solve uv' + (d(uv') - focus) * dir = c by fixed-point iteration: near pixels move further
  vec2 q = c;
  for (int i = 0; i < 6; i++) {
    float d = texture(dep, q).r;
    q = c - (d - focus) * dir;
  }
  return texture(img, clamp(q, vec2(.001), vec2(.999))).rgb;
}
void main(){
  vec3 a = sampleView(imgA, depA, scaleA, camA, focusA);
  vec3 b = mixAB > 0.001 ? sampleView(imgB, depB, scaleB, camB, focusB) : a;
  vec3 c = mix(a, b, mixAB);
  float v = smoothstep(1.15, .35, length((uv - .5) * vec2(1.1, 1.)));
  o = vec4(c * mix(1., v, grade), 1.);
}`;

const MOVES: Record<string, (t: number) => [number, number, number]> = {
  dolly: (t) => [0.0, -0.01 + 0.02 * t, 1.04 + 0.1 * t],
  pan: (t) => [-0.03 + 0.06 * t, 0, 1.08],
  orbit: (t) => [Math.sin((t - 0.5) * 2.4) * 0.035, Math.cos((t - 0.5) * 2.4) * 0.012 - 0.01, 1.07],
  rise: (t) => [0, 0.03 - 0.06 * t, 1.06 + 0.03 * t],
};

const factory: PlayerFactory = async (cfg, ctx) => {
  const canvas = document.createElement("canvas");
  ctx.visual.appendChild(canvas);
  const gl = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true });
  if (!gl) throw new Error("no webgl2");
  const chapters: { img: WebGLTexture; dep: WebGLTexture; w: number; h: number; focus: number; move: string }[] = [];

  const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader"); return s; };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(prog); gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = (n: string) => gl.getUniformLocation(prog, n);
  const u = { imgA: U("imgA"), depA: U("depA"), imgB: U("imgB"), depB: U("depB"), scaleA: U("scaleA"), scaleB: U("scaleB"),
    camA: U("camA"), camB: U("camB"), mixAB: U("mixAB"), strength: U("strength"), focusA: U("focusA"), focusB: U("focusB"), grade: U("grade") };
  gl.uniform1i(u.imgA, 0); gl.uniform1i(u.depA, 1); gl.uniform1i(u.imgB, 2); gl.uniform1i(u.depB, 3);

  function texture(im: HTMLImageElement) {
    const t = gl!.createTexture()!;
    gl!.bindTexture(gl!.TEXTURE_2D, t);
    gl!.texImage2D(gl!.TEXTURE_2D, 0, gl!.RGBA, gl!.RGBA, gl!.UNSIGNED_BYTE, im);
    gl!.generateMipmap(gl!.TEXTURE_2D);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MIN_FILTER, gl!.LINEAR_MIPMAP_LINEAR);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MAG_FILTER, gl!.LINEAR);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_S, gl!.CLAMP_TO_EDGE);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_T, gl!.CLAMP_TO_EDGE);
    return t;
  }
  // first chapter first so the page shows something quickly, the rest in the background
  for (let i = 0; i < cfg.chapters.length; i++) {
    const ch = cfg.chapters[i];
    const load = async () => {
      const [im, dp] = await Promise.all([loadImage(ch.image), loadImage(ch.depth)]);
      chapters[i] = { img: texture(im), dep: texture(dp), w: im.naturalWidth, h: im.naturalHeight, focus: ch.focus ?? 0.5, move: ch.move || cfg.move || "dolly" };
    };
    if (i === 0) await load(); else load();
  }

  let cw = 1, ch = 1;
  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    cw = canvas.width = Math.max(1, Math.round(r.width * dpr)); ch = canvas.height = Math.max(1, Math.round(r.height * dpr));
    gl!.viewport(0, 0, cw, ch);
  }
  resize();
  const cover = (c: { w: number; h: number }): [number, number] => {
    const ca = cw / ch, ia = c.w / c.h;
    return ca > ia ? [1, ca / ia] : [ia / ca, 1];
  };

  const steps = ctx.data.steps.map((s, i) => (s.intro ? -1 : i)).filter((i) => i >= 0);
  let px = 0, py = 0;
  const bind = (unit: number, t: WebGLTexture) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t); };

  return {
    resize,
    update(s) {
      // chapter c plays across step steps[c]; the next chapter fades in over the first 18% of its step
      let c = 0;
      for (let k = 0; k < steps.length; k++) if ((s.steps[steps[k]] ?? 0) > 0) c = k;
      c = Math.min(c, cfg.chapters.length - 1);
      const local = clamp(s.steps[steps[c]] ?? 0);
      const prev = Math.max(0, c - 1);
      const fade = c > 0 ? smooth(0, 0.18, local) : 1;
      const A = chapters[prev], B = chapters[c];
      if (!B && !A) return;
      px += (s.mx - px) * 0.05; py += (s.my - py) * 0.05;
      const camFor = (k: number, t: number): [number, number, number] => {
        const m = MOVES[chapters[k]?.move || "dolly"](easeInOut(clamp(t)));
        return [m[0] + px * 0.02, m[1] + py * 0.012, m[2]];
      };
      const a = B && fade >= 1 ? B : A || B!, b = B || A!;
      const ka = a === B ? c : prev;
      bind(0, a.img); bind(1, a.dep); bind(2, b.img); bind(3, b.dep);
      gl.uniform2fv(u.scaleA, cover(a)); gl.uniform2fv(u.scaleB, cover(b));
      gl.uniform3fv(u.camA, camFor(ka, ka === c ? local : 1));
      gl.uniform3fv(u.camB, camFor(c, local));
      gl.uniform1f(u.mixAB, a === b ? 0 : fade);
      gl.uniform1f(u.focusA, a.focus); gl.uniform1f(u.focusB, b.focus);
      gl.uniform1f(u.strength, cfg.strength ?? 1);
      gl.uniform1f(u.grade, cfg.vignette ?? 0.35);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    },
  };
};
export default factory;
