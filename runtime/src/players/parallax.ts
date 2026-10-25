/**
 * parallax: each photo + its estimated depth map becomes a 2.5D camera move. One chapter per step with a photo (a step
 * without one is a caption over the photo before it); chapters crossfade as the next photo's step begins. Pointer adds a
 * little look-around.
 *
 * Type in the world (engine/world.py `build_photo`): a step with `place: {kind: ...}` has its title set in its photograph.
 * behind / sky: the title sits at a depth in the photo's own depth map, so the layers the camera moves past it pass in front
 * of it; surface: it is painted on a surface found in the photo, in the surface's own perspective, light and grain.
 */
import type { PlayerFactory } from "../lib/types";
import { clamp, easeInOut, loadImage, reducedMotion, smooth } from "../lib/util";
import { baseGlsl, POINTER_GLSL, pointerEnv, readPointer, trackPointer, uniforms as pointerUniforms, type PointerCfg } from "../lib/pointer";
import { WORLD_GLSL } from "../lib/worldGlsl";
import type { LiveDetail } from "../lib/live";
import { contrastWith, inkFor, layout, PAD, probeStyle, rasterize, type Layout, type WorldStyle } from "../lib/worldText";

const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`;

// pointer (lib/pointer.ts): PTR_MODE 0 none, 1 lens, 2 light; PTR_LAYER 1 the photo's colour through `base`, 2 a second picture
// living details (lib/live.ts, `live:` on a step's photo): LIVE_GLSL, drawn on each view's photo where it is sampled
const fragment = (ptr: PointerCfg | null, liveGlsl = "") => `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
#define PAD ${PAD.toFixed(3)}
#define PTR_MODE ${ptr ? (ptr.mode === "light" ? 2 : 1) : 0}
#define PTR_LAYER ${ptr?.layer === "picture" ? 2 : 1}
#define RELIEF 0.08
${WORLD_GLSL}
${ptr ? POINTER_GLSL : ""}
${liveGlsl ? `#define LIVE 1
#define LV_VIEWS 2
${liveGlsl}` : ""}
${ptr ? `vec3 ptrBase(vec3 c, vec3 bl) { return ${baseGlsl(ptr.base)}; }` : ""}
uniform sampler2D imgA, depA, imgB, depB, mskA, mskB, uText, layA, layB;
uniform float hasLayA, hasLayB;
uniform vec2 scaleA, scaleB;      // cover-fit uv scale per image
uniform vec3 camA, camB;          // x, y offset and zoom per chapter
uniform float mixAB, strength, focusA, focusB;
uniform float grade;              // 0..1 vignette amount
// the title of each view's chapter, if it has one (type in the world)
uniform float uOnT[2], uInT[2];
uniform int uKindT[2];
uniform mat3 uMT[2];
uniform vec4 uBoxT[2], uCellT[2], uAT[2], uBT[2];

vec3 sampleView(sampler2D img, sampler2D dep, sampler2D msk, sampler2D lay, float hasLay, vec2 sc, vec3 cam, float focus, int v){
  vec2 c = (uv - .5) / (sc * cam.z) + .5;
  vec2 dir = cam.xy * strength;
  // solve uv' + (d(uv') - focus) * dir = c by fixed-point iteration: near pixels move further
  vec2 q = c;
  for (int i = 0; i < 6; i++) {
    float d = texture(dep, q).r;
    q = c - (d - focus) * dir;
  }
  q = clamp(q, vec2(.001), vec2(.999));
  vec3 col = texture(img, q).rgb;
#ifdef LIVE
  float la = 0.0;
  col = liveApply(img, q, col, v, la);
#endif
  if (uOnT[v] > 0.002) {
    int kind = uKindT[v];
    // behind / sky: where the title's own depth puts it on screen; surface: on the photo's surface point itself
    vec2 qt = kind == 2 ? q : clamp(c - (uAT[v].x - focus) * dir, vec2(.001), vec2(.999));
    vec3 pq = uMT[v] * vec3(qt, 1.0);
    vec2 pl = pq.xy / pq.z;
    vec2 lc = (pl - uBoxT[v].xy) / (uBoxT[v].zw * (1.0 + 2.0 * PAD)) + 0.5;
    vec2 dx = dFdx(lc), dy = dFdy(lc);
    vec2 inb = step(vec2(0.0), lc) * step(lc, vec2(1.0));
    float bl = exp2(uAT[v].w);
    vec4 t = textureGrad(uText, uCellT[v].xy + clamp(lc, 0.0, 1.0) * uCellT[v].zw, dx * uCellT[v].zw * bl, dy * uCellT[v].zw * bl);
    float cov = t.a * inb.x * inb.y * step(0.0, pq.z);
    if (cov > 0.002) {
      vec3 ink = t.rgb / max(t.a, 1e-4);
      vec3 near = textureLod(img, q, 1.6).rgb, locl = textureLod(img, q, 3.6).rgb, air = textureLod(img, q, 6.5).rgb;
      if (kind != 2) col = worldBehindSky(col, ink, cov, col, near, locl, air, texture(dep, q).r, uAT[v], uBT[v], uOnT[v], uInT[v], kind, uv.y);
      else col = worldSurface(col, ink, cov, col, near, locl, pl, texture(msk, q).r, uBT[v], uOnT[v], uInT[v], lc.x);
    }
  }
#if PTR_MODE == 1
  // the lens: the second layer through a soft circle under the pointer (on screen), sampled through the same depth warp as
  // the photo so it lines up whatever the camera does; outside it, the photo in the base look
  float lm = ptrLens(uv) * uPtrStr;
  vec3 outside = ptrBase(col, ${ptr?.base === "blur" ? "textureLod(img, q, 3.5).rgb" : "col"});
#if PTR_LAYER == 2
  col = hasLay > 0.5 ? ptrRim(mix(outside, texture(lay, q).rgb, lm), uv) : outside;
#else
  col = ptrRim(mix(outside, col, lm), uv);
#endif
#elif PTR_MODE == 2
  // the torch: the depth map's gradient is the surface's slope, in picture heights (x scaled by the photo's aspect)
  // (read a little blurred, from a smaller mip, so the light follows the big shapes and not the depth map's steps)
  vec2 ts = 4.0 / vec2(textureSize(dep, 0));
  float gx = textureLod(dep, q + vec2(ts.x, 0.0), 1.5).r - textureLod(dep, q - vec2(ts.x, 0.0), 1.5).r;
  float gy = textureLod(dep, q + vec2(0.0, ts.y), 1.5).r - textureLod(dep, q - vec2(0.0, ts.y), 1.5).r;
  vec2 grad = vec2(gx / (2.0 * ts.x) / (sc.x / sc.y * uPtrAsp), gy / (2.0 * ts.y)) * RELIEF;
  col = ptrLight(col, uv, texture(dep, q).r, grad);
#endif
  return col;
}
void main(){
  vec3 a = sampleView(imgA, depA, mskA, layA, hasLayA, scaleA, camA, focusA, 0);
  vec3 b = mixAB > 0.001 ? sampleView(imgB, depB, mskB, layB, hasLayB, scaleB, camB, focusB, 1) : a;
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

const KIND = { behind: 0, sky: 1, surface: 2 } as const;
interface WorldCh {
  kind: keyof typeof KIND; m: number[]; plane: [number, number]; box: [number, number, number]; depth?: number; soft?: number; blur?: number;
  tone?: number; mask?: string; lines?: number;
  style: { align: "left" | "center" | "right"; caps: boolean; track: number; weight: number | null; color: string; haze: number; fog: number; wear: number; relief: number; lines: number | null };
}
interface Live { ch: number; w: WorldCh; lay: Layout; cell: { x: number; y: number; w: number; h: number }; enabled: boolean; el: HTMLElement | null }

function inv3(m: number[]): number[] | null {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-12) return null;
  const k = 1 / det;
  return [A * k, -(b * i - c * h) * k, (b * f - c * e) * k, B * k, (a * i - c * g) * k, -(a * f - c * d) * k, C * k, -(a * h - b * g) * k, (a * e - b * d) * k];
}

const factory: PlayerFactory = async (cfg, ctx) => {
  const canvas = document.createElement("canvas");
  ctx.visual.appendChild(canvas);
  const gl = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true });
  if (!gl) throw new Error("no webgl2");
  const ptr = readPointer(ctx.section, cfg);
  // living details, one list per photo (engine/live.py); none with reduced motion, and then the module is not even loaded
  const liveMod = !reducedMotion && cfg.chapters.some((c: any) => Array.isArray(c.live) && c.live.length) ? await import("../lib/live") : null;
  const lives: LiveDetail[][] = liveMod ? cfg.chapters.map((c: any) => liveMod.readLive(c.live)) : [];
  const chapters: { img: WebGLTexture; dep: WebGLTexture; msk: WebGLTexture; lay: WebGLTexture | null; w: number; h: number; focus: number; move: string }[] = [];

  const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader"); return s; };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fragment(ptr, liveMod?.LIVE_GLSL)));
  gl.linkProgram(prog); gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = (n: string) => gl.getUniformLocation(prog, n);
  const u = { imgA: U("imgA"), depA: U("depA"), imgB: U("imgB"), depB: U("depB"), scaleA: U("scaleA"), scaleB: U("scaleB"),
    camA: U("camA"), camB: U("camB"), mixAB: U("mixAB"), strength: U("strength"), focusA: U("focusA"), focusB: U("focusB"), grade: U("grade"),
    mskA: U("mskA"), mskB: U("mskB"), uText: U("uText"), on: U("uOnT[0]"), inn: U("uInT[0]"), kind: U("uKindT[0]"), m: U("uMT[0]"),
    box: U("uBoxT[0]"), cell: U("uCellT[0]"), A: U("uAT[0]"), B: U("uBT[0]"),
    hasLayA: U("hasLayA"), hasLayB: U("hasLayB"), ptrC: U("uPtrC"), ptrR: U("uPtrR"), ptrAsp: U("uPtrAsp") };
  gl.uniform1i(u.imgA, 0); gl.uniform1i(u.depA, 1); gl.uniform1i(u.imgB, 2); gl.uniform1i(u.depB, 3);
  gl.uniform1i(u.mskA, 4); gl.uniform1i(u.mskB, 5); gl.uniform1i(u.uText, 6);
  gl.uniform1i(U("layA"), 7); gl.uniform1i(U("layB"), 8);
  if (ptr) {
    gl.uniform1f(U("uPtrSoft"), ptr.softness); gl.uniform1f(U("uPtrStr"), ptr.strength); gl.uniform3fv(U("uPtrCol"), ptr.color);
  }

  function texture(im: HTMLImageElement | null) {
    const t = gl!.createTexture()!;
    gl!.bindTexture(gl!.TEXTURE_2D, t);
    if (im) gl!.texImage2D(gl!.TEXTURE_2D, 0, gl!.RGBA, gl!.RGBA, gl!.UNSIGNED_BYTE, im);
    else gl!.texImage2D(gl!.TEXTURE_2D, 0, gl!.RGBA, 1, 1, 0, gl!.RGBA, gl!.UNSIGNED_BYTE, new Uint8Array([255, 255, 255, 255]));
    gl!.generateMipmap(gl!.TEXTURE_2D);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MIN_FILTER, gl!.LINEAR_MIPMAP_LINEAR);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MAG_FILTER, gl!.LINEAR);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_S, gl!.CLAMP_TO_EDGE);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_T, gl!.CLAMP_TO_EDGE);
    return t;
  }
  let loaded = 0;
  await Promise.all(cfg.chapters.map(async (ch: any, i: number) => {
    const layer = ptr?.layer === "picture" ? ptr.layers[i] : null;     // the lens's second picture for this photo, if any
    const [im, dp, mk, ly] = await Promise.all([loadImage(ch.image), loadImage(ch.depth), ch.world?.mask ? loadImage(ch.world.mask) : Promise.resolve(null),
      layer ? loadImage(layer).catch(() => null) : Promise.resolve(null)]);
    chapters[i] = { img: texture(im), dep: texture(dp), msk: texture(mk), lay: ly ? texture(ly) : null, w: im.naturalWidth, h: im.naturalHeight,
      focus: ch.focus ?? 0.5, move: ch.move || cfg.move || "dolly" };
    ctx.progress(++loaded / cfg.chapters.length);
  }));

  // ---- type in the world: the site's fonts, laid out and drawn into one atlas texture
  const live: Live[] = [];
  const hasWorld = !reducedMotion && cfg.chapters.some((c: any) => c.world);
  let rasterCanvas: HTMLCanvasElement | null = null;
  const st: WorldStyle | null = hasWorld ? probeStyle(ctx.section) : null;
  if (hasWorld && st) {
    try { await document.fonts.ready; await document.fonts.load(`${st.weight} 64px ${st.family}`); await document.fonts.load(`italic ${st.weight} 64px ${st.family}`); } catch { /* ignore */ }
    const stepEls = [...ctx.section.querySelectorAll<HTMLElement>(".ss-step")];
    cfg.chapters.forEach((c: any, k: number) => {
      const w: WorldCh | undefined = c.world;
      const step = ctx.data.steps[c.step ?? k];
      if (!w || !step || !w.m) return;
      const lay = layout(step.title, st, { size: w.box[2], hMax: 0.3 * w.plane[1], lines: w.style.lines ?? undefined, caps: w.style.caps,
                                          track: w.style.track, weight: w.style.weight ?? st.weight, align: w.style.align });
      live.push({ ch: k, w, lay, cell: { x: 0, y: 0, w: 0, h: 0 }, enabled: true, el: stepEls[c.step ?? k] || null });
    });
    const colorOf = (L: Live, em: boolean): string => {
      const s = L.w.style, tone = L.w.tone ?? 0.5;
      const base = s.color === "ink" ? st.ink : s.color === "paper" ? st.paper : s.color === "accent" ? st.accent : /^#|^rgb/i.test(s.color) ? s.color : inkFor(tone, st);
      return !em || s.color !== "auto" ? base : contrastWith(st.emColor, tone, st);
    };
    if (live.length) {
      const raster = rasterize(live.map((L) => ({ layout: L.lay, px: Math.min(2600, Math.max(256, L.lay.wPlane * 2200)), colors: (em: boolean) => colorOf(L, em),
        weight: L.w.style.weight ?? st.weight, track: L.w.style.track, caps: L.w.style.caps, align: L.w.style.align, st })));
      live.forEach((L, k) => { L.cell = raster.cells[k]; });
      rasterCanvas = raster.canvas;
    }
  }
  const tText = gl.createTexture()!;
  if (rasterCanvas) {
    gl.activeTexture(gl.TEXTURE6);
    gl.bindTexture(gl.TEXTURE_2D, tText);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, rasterCanvas);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
  }
  const byChapter = new Map<number, Live>(live.map((L) => [L.ch, L]));
  const arr = { on: new Float32Array(2), inn: new Float32Array(2), kind: new Int32Array(2), m: new Float32Array(18), box: new Float32Array(8),
    cell: new Float32Array(8), A: new Float32Array(8), B: new Float32Array(8) };

  let cw = 1, ch = 1;
  const cover = (c: { w: number; h: number }): [number, number] => {
    const ca = cw / ch, ia = c.w / c.h;
    return ca > ia ? [1, ca / ia] : [ia / ca, 1];
  };
  // a title that the cover-fit would crop (a narrow screen) stays an ordinary card
  function fits() {
    for (const L of live) {
      const c = chapters[L.ch];
      if (!c) continue;
      const [sx, sy] = cover(c);
      const vx = 0.5 / (sx * 1.12), vy = 0.5 / (sy * 1.12);             // half the visible part of the photo, with the camera's zoom
      const Mi = inv3(L.w.m);
      let ok = !!Mi;
      if (Mi) {
        const [cx, cy] = [L.w.box[0], L.w.box[1]], hw = L.lay.wPlane / 2, hh = L.lay.hPlane / 2;
        for (const [px, py] of [[cx - hw, cy - hh], [cx + hw, cy - hh], [cx + hw, cy + hh], [cx - hw, cy + hh]]) {
          const wv = Mi[6] * px + Mi[7] * py + Mi[8];
          const x = (Mi[0] * px + Mi[1] * py + Mi[2]) / wv, y = (Mi[3] * px + Mi[4] * py + Mi[5]) / wv;
          if (Math.abs(x - 0.5) > vx - 0.01 || Math.abs(y - 0.5) > vy - 0.01) ok = false;
        }
      }
      const shown = canvas.getBoundingClientRect().width * (sx > 1 ? sx : 1);      // css px across the whole photo
      if (L.lay.fs * shown < 22) ok = false;
      L.enabled = ok;
      L.el?.classList.toggle("ss-world-on", ok);
    }
  }
  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    cw = canvas.width = Math.max(1, Math.round(r.width * dpr)); ch = canvas.height = Math.max(1, Math.round(r.height * dpr));
    gl!.viewport(0, 0, cw, ch);
    fits();
    drawn = "";            // resizing clears the canvas: the next update draws whatever it is
    track?.dirty();
  }
  // the pointer's lens or light (lib/pointer.ts): it moves only when the pointer does, and the canvas is redrawn only then
  const track = ptr ? trackPointer(canvas, { rest: ptr.rest, radius: ptr.radius }, pointerEnv()) : null;
  const white = texture(null);
  // the details' masks (a prompt's region) in one atlas on unit 9; the pack is rewritten when the two views change
  let liveCells: ([number, number, number, number] | null)[][] = [];
  const livePack = liveMod ? liveMod.emptyPack(2) : null;
  let liveViews = "";
  if (liveMod) {
    const flat = lives.flat();
    const atlas = await liveMod.maskAtlas(flat.map((d) => d.mask), loadImage);
    let n = 0;
    liveCells = lives.map((ds) => ds.map(() => atlas.cells[n++]));
    gl.activeTexture(gl.TEXTURE9);
    gl.bindTexture(gl.TEXTURE_2D, atlas.canvas ? texture(atlas.canvas as unknown as HTMLImageElement) : white);
    gl.uniform1i(U("uLvMask"), 9);
  }
  let drawn = "";
  resize();
  (((window as any).__ssWorld ||= {}) as Record<string, any>).live = live;

  // chapter k plays across step cfg.chapters[k].step
  const steps: number[] = cfg.chapters.map((c: any, k: number) => c.step ?? k);
  let px = 0, py = 0;
  const bind = (unit: number, t: WebGLTexture) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t); };
  const textVis = (local: number) => smooth(0.04, 0.22, local) * (1 - smooth(0.9, 1.0, local));
  function setText(slot: number, k: number, local: number) {
    const L = byChapter.get(k);
    arr.on[slot] = 0;
    if (!L || !L.enabled) return;
    const on = textVis(local);
    if (on < 0.002) return;
    arr.on[slot] = on;
    arr.inn[slot] = clamp(local / 0.35);
    arr.kind[slot] = KIND[L.w.kind];
    arr.m.set([L.w.m[0], L.w.m[3], L.w.m[6], L.w.m[1], L.w.m[4], L.w.m[7], L.w.m[2], L.w.m[5], L.w.m[8]], slot * 9);
    arr.box.set([L.w.box[0], L.w.box[1], L.lay.wPlane, L.lay.hPlane], slot * 4);
    arr.cell.set([L.cell.x, L.cell.y, L.cell.w, L.cell.h], slot * 4);
    const lod = Math.log2(Math.max(1, 1 + (L.w.blur ?? (L.w.kind === "surface" ? 0.8 : 0)) * (canvas.width / 1920) * 0.7));
    arr.A.set([L.w.depth ?? 0, L.w.soft ?? 0.04, L.w.style.haze, lod], slot * 4);
    arr.B.set([L.w.style.fog, L.w.style.wear, L.w.style.relief, L.w.tone ?? 0.5], slot * 4);
  }

  return {
    resize,
    update(s) {
      track?.update(s.t);
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
      // nothing changed since the last frame (the scroll and the pointer are still): the canvas keeps what it shows
      // living details on either view, on screen: a new frame 30 times a second (lib/live.ts); off screen they hold still
      let tick = "";
      if (livePack && liveMod && ((lives[ka]?.length) || (lives[c]?.length))) {
        const r = canvas.getBoundingClientRect();
        if (r.bottom > 0 && r.top < innerHeight && !document.hidden) tick = String(Math.floor(s.t * liveMod.FPS));
      }
      const key = `${ka}|${c}|${local.toFixed(4)}|${fade.toFixed(4)}|${px.toFixed(4)}|${py.toFixed(4)}|${track ? track.pos.join(",") : ""}|${tick}`;
      if (key === drawn) return;
      drawn = key;
      bind(0, a.img); bind(1, a.dep); bind(2, b.img); bind(3, b.dep); bind(4, a.msk); bind(5, b.msk);
      bind(7, a.lay || white); bind(8, b.lay || white);
      gl.uniform1f(u.hasLayA, a.lay ? 1 : 0); gl.uniform1f(u.hasLayB, b.lay ? 1 : 0);
      if (livePack && liveMod) {
        if (liveViews !== `${ka}|${c}`) {
          liveViews = `${ka}|${c}`;
          liveMod.packView(livePack, 0, lives[ka] || [], liveCells[ka]);
          liveMod.packView(livePack, 1, lives[c] || [], liveCells[c]);
          gl.uniform4fv(U("uLvBox"), livePack.box); gl.uniform4fv(U("uLvA"), livePack.a); gl.uniform4fv(U("uLvB"), livePack.b);
          gl.uniform4fv(U("uLvC"), livePack.c); gl.uniform4fv(U("uLvM"), livePack.m); gl.uniform4fv(U("uLvP"), livePack.p);
        }
        gl.uniform1f(U("uLvT"), s.t);
        gl.uniform1f(U("uLvAsp"), b.w / b.h);
      }
      if (track && ptr) {
        const pu = pointerUniforms(track.pos, ptr.radius, canvas.getBoundingClientRect(), null);
        gl.uniform2fv(u.ptrC, pu.centre); gl.uniform1f(u.ptrR, pu.radius); gl.uniform1f(u.ptrAsp, pu.aspect);
      }
      gl.uniform2fv(u.scaleA, cover(a)); gl.uniform2fv(u.scaleB, cover(b));
      gl.uniform3fv(u.camA, camFor(ka, ka === c ? local : 1));
      gl.uniform3fv(u.camB, camFor(c, local));
      gl.uniform1f(u.mixAB, a === b ? 0 : fade);
      gl.uniform1f(u.focusA, a.focus); gl.uniform1f(u.focusB, b.focus);
      gl.uniform1f(u.strength, cfg.strength ?? 1);
      gl.uniform1f(u.grade, cfg.vignette ?? 0.35);
      if (live.length) {
        setText(0, ka, ka === c ? local : 1);
        setText(1, c, local);
        gl.uniform1fv(u.on, arr.on); gl.uniform1fv(u.inn, arr.inn); gl.uniform1iv(u.kind, arr.kind); gl.uniformMatrix3fv(u.m, false, arr.m);
        gl.uniform4fv(u.box, arr.box); gl.uniform4fv(u.cell, arr.cell); gl.uniform4fv(u.A, arr.A); gl.uniform4fv(u.B, arr.B);
      }
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    },
  };
};
export default factory;
