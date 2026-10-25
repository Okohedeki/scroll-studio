/**
 * Living details on a plain picture (`live:` on a hero, product, strip or gallery image, or a section backdrop; the maths and
 * the GLSL are lib/live.ts). Not a scene player: the compiler marks every place such a picture is shown (an <img>, or an
 * element with it as a CSS background) with data-live="{r, d}" (the picture's aspect and its details), and this lays one
 * small WebGL canvas over it that redraws the picture only where a detail lives, with alpha everywhere else, so outside the
 * details the page shows the <img> itself.
 *
 *   sets up when the picture is a screen away, draws only while it is on screen and the tab is visible, at 30 frames a second
 *   reduced motion, no WebGL2, a fit it does not know: nothing at all (the still picture)
 *   copies the image's own transform (a hero's slow zoom) and opacity, so the layer stays on the picture
 *
 * Every page is complete without this file.
 */
import { due, emptyPack, LIVE_GLSL, maskAtlas, packView, pictureRect, readLive, shouldRun, uvMap, type LiveDetail } from "../lib/live";
import { loadImage } from "../lib/util";

const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`;

const FS = `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
#define LV_VIEWS 1
${LIVE_GLSL}
uniform sampler2D uImg;
uniform vec4 uMap;
void main(){
  vec2 q = uv * uMap.xy + uMap.zw;
  if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) { o = vec4(0.0); return; }
  vec3 c = texture(uImg, q).rgb;
  float a = 0.0;
  vec3 f = liveApply(uImg, q, c, 0, a);
  // premultiplied: over the picture underneath (which is c) this gives exactly f, and nothing where a is 0
  o = a > 0.0 ? vec4(clamp(f - c * (1.0 - a), 0.0, 1.0), a) : vec4(0.0);
}`;

interface Item {
  host: HTMLElement; img: boolean; r: number; details: LiveDetail[]; canvas: HTMLCanvasElement;
  near: boolean; seen: boolean; state: "idle" | "loading" | "ready" | "failed"; draw: ((t: number) => void) | null;
  tf: string; op: string; size: string;
}

const reduced = matchMedia("(prefers-reduced-motion: reduce)");

function setup(it: Item): void {
  if (it.state !== "idle") return;
  it.state = "loading";
  const gl = it.canvas.getContext("webgl2", { premultipliedAlpha: true, antialias: false });
  if (!gl) { fail(it); return; }
  const src = it.img ? ((it.host as HTMLImageElement).currentSrc || (it.host as HTMLImageElement).src)
    : (getComputedStyle(it.host).backgroundImage.match(/url\(["']?([^"')]+)["']?\)/) || [])[1];
  if (!src) { fail(it); return; }
  Promise.all([loadImage(src), maskAtlas(it.details.map((d) => d.mask), loadImage)]).then(([im, atlas]) => {
    const sh = (type: number, code: string) => {
      const s = gl.createShader(type)!; gl.shaderSource(s, code); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader");
      return s;
    };
    const prog = gl.createProgram()!;
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog); gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const U = (n: string) => gl.getUniformLocation(prog, n);
    const tex = (unit: number, source: TexImageSource) => {
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    };
    tex(0, im);
    const blank = document.createElement("canvas"); blank.width = blank.height = 1;
    tex(1, atlas.canvas || blank);
    gl.uniform1i(U("uImg"), 0); gl.uniform1i(U("uLvMask"), 1);
    const pack = emptyPack(1);
    packView(pack, 0, it.details, atlas.cells);
    gl.uniform4fv(U("uLvBox"), pack.box); gl.uniform4fv(U("uLvA"), pack.a); gl.uniform4fv(U("uLvB"), pack.b);
    gl.uniform4fv(U("uLvC"), pack.c); gl.uniform4fv(U("uLvM"), pack.m); gl.uniform4fv(U("uLvP"), pack.p);
    gl.uniform1f(U("uLvAsp"), it.r);
    const uT = U("uLvT"), uMap = U("uMap");
    gl.clearColor(0, 0, 0, 0);
    it.draw = (t: number) => {
      const c = it.canvas, cs = getComputedStyle(it.host);
      const W = c.clientWidth, H = c.clientHeight;
      const rc = pictureRect(W, H, it.r, it.img ? cs.objectFit : cs.backgroundSize, it.img ? cs.objectPosition : cs.backgroundPosition);
      if (!rc) { c.style.display = "none"; return; }
      const dpr = Math.min(devicePixelRatio || 1, 2), size = `${Math.round(W * dpr)}x${Math.round(H * dpr)}`;
      if (size !== it.size) { it.size = size; c.width = Math.max(1, Math.round(W * dpr)); c.height = Math.max(1, Math.round(H * dpr)); gl.viewport(0, 0, c.width, c.height); }
      gl.uniform4fv(uMap, uvMap(W, H, rc));
      gl.uniform1f(uT, t);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
    it.state = "ready";
    kick();
  }).catch(() => fail(it));
}

function fail(it: Item) { it.state = "failed"; it.canvas.remove(); }

/** The layer takes the image's box (an <img>; a backdrop's layer fills its host by CSS). */
function place(it: Item) {
  if (!it.img) return;
  const { host, canvas } = it, s = canvas.style, cs = getComputedStyle(host);
  s.left = host.offsetLeft + "px"; s.top = host.offsetTop + "px";
  s.width = host.offsetWidth + "px"; s.height = host.offsetHeight + "px";
  s.borderRadius = cs.borderRadius; s.transformOrigin = cs.transformOrigin;
  s.clipPath = cs.clipPath === "none" ? "" : cs.clipPath;
  it.tf = ""; it.op = "";
}

let items: Item[] = [];
let running = false;
const t0 = performance.now();
let last = -1;

function frame(now: number) {
  let any = false;
  const draw = due(now, last);
  if (draw) last = now;
  for (const it of items) {
    if (it.state !== "ready" || !shouldRun(it.seen, document.hidden, reduced.matches)) continue;
    any = true;
    if (it.img) {
      const cs = getComputedStyle(it.host);
      if (cs.transform !== it.tf) { it.tf = cs.transform; it.canvas.style.transform = it.tf === "none" ? "" : it.tf; }
      if (cs.opacity !== it.op) { it.op = cs.opacity; it.canvas.style.opacity = it.op; }
    }
    if (draw) it.draw!((now - t0) / 1000);
  }
  if (any) requestAnimationFrame(frame); else running = false;      // nothing on screen: no work at all
}
function kick() { if (!running && items.some((i) => i.state === "ready" && shouldRun(i.seen, document.hidden, reduced.matches))) { running = true; requestAnimationFrame(frame); } }

export function start(): Item[] {
  items = [];
  if (reduced.matches) return items;
  for (const host of document.querySelectorAll<HTMLElement>("[data-live]")) {
    let e: { r?: number; d?: unknown };
    try { e = JSON.parse(host.dataset.live || ""); } catch { continue; }
    const details = readLive(e.d);
    if (!details.length || !e.r) continue;
    const img = host instanceof HTMLImageElement;
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    canvas.className = "ss-live";
    canvas.style.cssText = "position:absolute;pointer-events:none;display:block";
    if (img) {
      host.insertAdjacentElement("afterend", canvas);
      const z = getComputedStyle(host).zIndex;
      if (z !== "auto") canvas.style.zIndex = z;
    } else {
      // a background: the layer is the first child, behind the section's content, over its background
      if (getComputedStyle(host).position === "static") host.style.position = "relative";
      host.style.isolation = "isolate";
      canvas.style.inset = "0"; canvas.style.width = "100%"; canvas.style.height = "100%"; canvas.style.zIndex = "-1";
      host.prepend(canvas);
    }
    items.push({ host, img, r: e.r, details, canvas, near: false, seen: false, state: "idle", draw: null, tf: "", op: "", size: "" });
  }
  if (!items.length) return items;
  (window as unknown as { __ssLive: Item[] }).__ssLive = items;
  const of = (el: Element) => items.find((i) => i.host === el)!;
  const nearIO = new IntersectionObserver((es) => {
    for (const en of es) { const it = of(en.target); it.near = en.isIntersecting; if (it.near) setup(it); }
  }, { rootMargin: "100% 0px 100% 0px" });
  const seenIO = new IntersectionObserver((es) => {
    for (const en of es) { const it = of(en.target); it.seen = en.isIntersecting; if (it.seen) setup(it); }
    kick();
  }, { threshold: [0, 0.01] });
  const relayout = () => items.forEach(place);
  const ro = new ResizeObserver(relayout);
  for (const it of items) {
    nearIO.observe(it.host); seenIO.observe(it.host); ro.observe(it.host);
    if (it.img) it.host.addEventListener("load", relayout);
    place(it);
  }
  addEventListener("resize", relayout, { passive: true });
  document.addEventListener("visibilitychange", kick);
  reduced.addEventListener("change", () => {
    // asking for less motion mid-visit: back to the still picture, now
    if (reduced.matches) items.forEach((it) => { it.canvas.style.display = "none"; });
    else { items.forEach((it) => { it.canvas.style.display = "block"; }); kick(); }
  });
  return items;
}
