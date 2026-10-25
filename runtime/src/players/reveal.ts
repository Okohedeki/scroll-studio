/**
 * film + reveal: the film drawn through a WebGL shader. Everything is in the section's `base` look (black and white,
 * dimmed, blurred or tinted) except where a region's mask, scaled by how revealed that region is at this scroll position,
 * lets the film's own colour through.
 *
 * Two videos are scrubbed together: the colour film and a grayscale mask atlas (up to four regions per video, each a tile
 * of a 2x2 grid) encoded with the same frame rate, frame count and GOP. A seek is issued to both at the middle of the same
 * frame, and the canvas is only drawn when BOTH have landed, so a mask frame is never drawn over a different film frame.
 * Returns null when WebGL2 is unavailable (the caller then plays the colour film as it is).
 *
 * The pointer (`pointer:` on the film, lib/pointer.ts) is drawn in the same pass: a lens brings the film's colour in under the
 * pointer as well as in the regions, a light darkens the film and follows the pointer with a pool of warm light. A film with
 * a pointer and no reveal plays through here too, with no regions.
 */
import type { PlayerContext, Player } from "../lib/types";
import { clamp, follow, hexToRgb, isMobile, reducedMotion } from "../lib/util";
import { fetchBlobURL } from "../lib/util";
import { amountsAt, type RevealKey } from "../lib/revealKeys";
import { POINTER_GLSL, pointerEnv, readPointer, trackPointer, uniforms as pointerUniforms, type PointerCfg } from "../lib/pointer";

interface MaskVideo { video: string; mobile?: string; regions: string[]; cols: number; rows: number; tile: [number, number] }
interface Cfg {
  video: string; videoMobile?: string; fps?: number;
  reveal?: { base: string; strength: number; ease: string; regions: string[]; keys: RevealKey[]; feather: number; masks: MaskVideo[]; fps: number };
}

const VERT = `#version 300 es
in vec2 aPos; out vec2 vUv;
void main() { vUv = vec2(aPos.x * 0.5 + 0.5, 0.5 - aPos.y * 0.5); gl_Position = vec4(aPos, 0.0, 1.0); }`;

/** The fragment shader for one reveal config: the base look, and one mask lookup per region (tile of an atlas). */
type RevealCfg = NonNullable<Cfg["reveal"]>;
function fragment(rv: RevealCfg, tints: boolean, ptr: PointerCfg | null = null): string {
  const lines: string[] = [];
  let r = 0;
  rv.masks.forEach((m, g) => {
    m.regions.forEach((_, slot) => {
      const col = slot % m.cols, row = Math.floor(slot / m.cols);
      // inset by half a texel of the tile so bilinear filtering never reads the neighbouring tile
      lines.push(`  { vec2 tl = clamp(vUv, uInset[${g}].xy, 1.0 - uInset[${g}].xy);
    float m = texture(uMask${g}, (vec2(${col}.0, ${row}.0) + tl) / vec2(${m.cols}.0, ${m.rows}.0)).r;
    k = 1.0 - (1.0 - k) * (1.0 - m * uAmt[${r}]); }`);
      r++;
    });
  });
  const base = rv.base;
  const baseCode = base === "none" ? "vec3 b = c;"
    : base === "mono" ? "vec3 b = vec3(lum(c));"
    : base === "dim" ? "vec3 b = mix(c, vec3(lum(c)), 0.55) * 0.55;"
    : base === "blur" ? "vec3 b = blurred();"
    : "float l = lum(c); vec3 b = l < 0.5 ? uTint * (l * 2.0) : uTint + (1.0 - uTint) * (l * 2.0 - 1.0);";
  void tints;
  return `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uFilm;
${rv.masks.map((_, g) => `uniform sampler2D uMask${g};`).join("\n")}
uniform vec2 uInset[${Math.max(1, rv.masks.length)}];
uniform float uAmt[${Math.max(1, rv.regions.length)}];
uniform float uStrength; uniform vec3 uTint; uniform float uBlur; uniform vec2 uAspect;
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
${ptr ? POINTER_GLSL : ""}
vec3 blurred() {
  vec3 acc = texture(uFilm, vUv).rgb; float w = 1.0;
  for (int i = 0; i < 16; i++) {
    float a = float(i) * 2.39996; float rr = sqrt((float(i) + 0.5) / 16.0);
    vec2 d = vec2(cos(a), sin(a)) * rr * uBlur * uAspect;
    acc += texture(uFilm, vUv + d).rgb; w += 1.0;
  }
  return acc / w;
}
void main() {
  vec3 c = texture(uFilm, vUv).rgb;
  float k = 0.0;
${lines.join("\n")}
  k *= uStrength;
  ${baseCode}
${ptr?.mode === "lens" ? "  k = max(k, ptrLens(vUv) * uPtrStr);" : ""}
  o = vec4(mix(b, c, k), 1.0);
${ptr?.mode === "lens" ? "  o.rgb = ptrRim(o.rgb, vUv);" : ""}
${ptr?.mode === "light" ? "  o.rgb = ptrLight(o.rgb, vUv, 1.0, vec2(0.0));" : ""}
}`;
}

function compile(gl: WebGL2RenderingContext, type: number, src: string): WebGLShader {
  const s = gl.createShader(type)!;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error("reveal shader: " + gl.getShaderInfoLog(s));
  return s;
}

function makeVideo(): HTMLVideoElement {
  const v = document.createElement("video");
  v.muted = true; v.playsInline = true; v.preload = "auto";
  return v;
}

async function load(v: HTMLVideoElement, url: string, onProgress: (f: number) => void) {
  try { v.src = await fetchBlobURL(url, onProgress, "video/mp4"); } catch { v.src = url; }
  await new Promise<void>((resolve) => {
    if (v.readyState >= 2) return resolve();
    v.addEventListener("loadeddata", () => resolve(), { once: true });
    v.addEventListener("error", () => resolve(), { once: true });
  });
}

export default async function reveal(cfg: Cfg, ctx: PlayerContext): Promise<Player | null> {
  const ptr = readPointer(ctx.section, cfg, cfg.reveal?.base);
  // a film with a pointer and no reveal: no regions, the base look is the pointer's (a light shows the film as it is)
  const rv: RevealCfg = cfg.reveal ?? { base: ptr?.base ?? "none", strength: 1, ease: "smooth", regions: [], keys: [], feather: 0, masks: [], fps: cfg.fps ?? 24 };
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2", { alpha: false, antialias: false, powerPreference: "high-performance" });
  if (!gl) return null;

  const mobile = isMobile();
  const film = makeVideo();
  const maskVideos = rv.masks.map(() => makeVideo());
  const fetchWeights = [0.7, ...rv.masks.map(() => 0.25 / rv.masks.length)];
  const got = fetchWeights.map(() => 0);
  const report = () => ctx.progress(0.95 * got.reduce((a, f, i) => a + f * fetchWeights[i], 0) / fetchWeights.reduce((a, b) => a + b, 0));
  await Promise.all([
    load(film, mobile && cfg.videoMobile ? cfg.videoMobile : cfg.video, (f) => { got[0] = f; report(); }),
    ...rv.masks.map((m, i) => load(maskVideos[i], mobile && m.mobile ? m.mobile : m.video, (f) => { got[i + 1] = f; report(); })),
  ]);
  const all = [film, ...maskVideos];
  if (all.some((v) => v.readyState < 2)) return null;

  const fps = rv.fps || 24;
  const duration = Math.min(...all.map((v) => v.duration || 0));
  const frames = Math.max(1, Math.round(duration * fps));

  // ---- program
  let prog: WebGLProgram;
  try {
    prog = gl.createProgram()!;
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, fragment(rv, rv.base[0] === "#", ptr)));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog) || "link failed");
  } catch (err) {
    console.warn("[scroll-studio] reveal: shader failed, playing the colour film", err);
    return null;
  }
  gl.useProgram(prog);
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);   // one big triangle
  const loc = gl.getAttribLocation(prog, "aPos");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  const textures: WebGLTexture[] = [];
  const makeTex = (unit: number) => {
    const t = gl.createTexture()!;
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    textures.push(t);
    return t;
  };
  all.forEach((_, i) => makeTex(i));
  gl.uniform1i(gl.getUniformLocation(prog, "uFilm"), 0);
  rv.masks.forEach((_, g) => gl.uniform1i(gl.getUniformLocation(prog, `uMask${g}`), g + 1));
  const insets = new Float32Array(rv.masks.flatMap((m) => [0.5 / m.tile[0] * (mobile ? 2 : 1), 0.5 / m.tile[1] * (mobile ? 2 : 1)]));
  if (insets.length) gl.uniform2fv(gl.getUniformLocation(prog, "uInset"), insets);
  const uAmt = gl.getUniformLocation(prog, "uAmt");
  gl.uniform1f(gl.getUniformLocation(prog, "uStrength"), rv.strength);
  if (rv.base[0] === "#") gl.uniform3fv(gl.getUniformLocation(prog, "uTint"), hexToRgb(rv.base));
  const w0 = film.videoWidth || 1920, h0 = film.videoHeight || 1080;
  const scale = Math.min(1, (mobile ? 1280 : 1920) / w0);
  canvas.width = Math.round(w0 * scale); canvas.height = Math.round(h0 * scale);
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.uniform1f(gl.getUniformLocation(prog, "uBlur"), 0.012);
  gl.uniform2f(gl.getUniformLocation(prog, "uAspect"), 1, w0 / h0);
  ctx.visual.appendChild(canvas);
  // the pointer: the canvas is the film's size shown with object-fit: cover, so the lens is mapped through that
  const track = ptr ? trackPointer(canvas, { rest: ptr.rest, radius: ptr.radius }, pointerEnv()) : null;
  const uPtr = { c: gl.getUniformLocation(prog, "uPtrC"), r: gl.getUniformLocation(prog, "uPtrR"), asp: gl.getUniformLocation(prog, "uPtrAsp") };
  if (ptr) {
    gl.uniform1f(gl.getUniformLocation(prog, "uPtrSoft"), ptr.softness);
    gl.uniform1f(gl.getUniformLocation(prog, "uPtrStr"), ptr.strength);
    gl.uniform3fv(gl.getUniformLocation(prog, "uPtrCol"), ptr.color);
  }

  const ids = rv.regions;
  const amt = new Float32Array(Math.max(1, ids.length));
  let shown = -1, drawnAmt = "";

  function upload() {
    all.forEach((v, i) => {
      gl!.activeTexture(gl!.TEXTURE0 + i);
      gl!.bindTexture(gl!.TEXTURE_2D, textures[i]);
      gl!.texImage2D(gl!.TEXTURE_2D, 0, gl!.RGBA, gl!.RGBA, gl!.UNSIGNED_BYTE, v);
    });
  }
  function draw(a: Record<string, number>) {
    ids.forEach((id, i) => { amt[i] = a[id] ?? 0; });
    gl!.uniform1fv(uAmt, amt);
    if (track && ptr) {
      const pu = pointerUniforms(track.pos, ptr.radius, canvas.getBoundingClientRect(), { w: canvas.width, h: canvas.height });
      gl!.uniform2fv(uPtr.c, pu.centre); gl!.uniform1f(uPtr.r, pu.radius); gl!.uniform1f(uPtr.asp, pu.aspect);
    }
    gl!.drawArrays(gl!.TRIANGLES, 0, 3);
    drawnAmt = Array.from(amt).join(",");
  }

  // ---- paired seeking: both videos to the middle of the same frame; draw when both have landed
  let busy = false, want = 0, timer = 0, seekId = 0;
  let amounts = amountsAt(rv.keys, ids, 0, rv.ease, reducedMotion);
  const debug = ((window as any).__ssReveal ||= {}) as Record<string, any>;   // read by tests and the Browser pane
  debug.videos = all;
  function seek(fi: number) {
    busy = true; want = fi;
    const id = ++seekId;
    let finished = false;
    const t = (fi + 0.5) / fps;
    let pending = all.length;
    const finish = () => {
      if (finished || id !== seekId) return;
      finished = true; clearTimeout(timer);
      busy = false; shown = want;
      upload(); draw(amounts);
      debug.frame = shown;
      debug.times = all.map((v) => v.currentTime);
      debug.onDraw?.(shown);
    };
    const landedOne = () => { if (--pending <= 0) finish(); };
    timer = window.setTimeout(finish, 800);      // never deadlock on a seek that doesn't report
    for (const v of all) {
      if (Math.abs(v.currentTime - t) < 1e-4) { queueMicrotask(landedOne); continue; }
      v.addEventListener("seeked", landedOne, { once: true });
      v.currentTime = t;
    }
  }
  seek(0);
  await new Promise<void>((resolve) => { const w = () => (busy ? requestAnimationFrame(w) : resolve()); w(); });

  // iOS only decodes frames for seeking after a user gesture touches the element
  addEventListener("touchstart", () => { all.forEach((v) => v.play().then(() => v.pause()).catch(() => {})); }, { once: true, passive: true });

  let current = 0;
  return {
    resize() { track?.dirty(); },
    update(s) {
      const moved = track ? track.update(s.t) : false;
      amounts = amountsAt(rv.keys, ids, s.p, rv.ease, reducedMotion);
      const target = s.p * (frames - 1) / fps;
      current += (target - current) * follow;
      const fi = clamp(Math.round(current * fps), 0, frames - 1);
      debug.p = s.p; debug.amounts = amounts;
      if (fi !== shown && !busy) seek(fi);
      else if (!busy && (moved || ids.map((id) => Math.fround(amounts[id] ?? 0)).join(",") !== drawnAmt)) draw(amounts);
    },
  };
}
