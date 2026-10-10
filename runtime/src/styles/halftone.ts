/**
 * Halftone: reading a freshly printed paper.
 *
 *   screen    every [data-ht-img] picture is screened into dots on one shared, fixed WebGL canvas (scissored per
 *             picture): ink at 45 degrees, a spot plate at 75 degrees. Scroll progress is the screen frequency:
 *             coarse abstract dots entering, a fine screen at reading position, coarse again leaving.
 *   loupe     hovering a picture shows a printer's loupe: the dots under it magnified (tap on touch screens)
 *   sources   pictures are drawn for print: the site's own image, or (when there is none) an illustration made
 *             on the spot: a sunrise over hills for the front page, the product's phone screen as a press photo
 *   press     section fronts print plate by plate (yellow, magenta, cyan, black), landing off register and settling
 *   ink       the lead headline arrives as an ink impression, not a movement
 *   charts    dot-field charts ink in, spot plate first, then black
 *   running   the masthead gives way to a running head with the section name and page number
 *   fold      passing a section front darkens the page above it a little, like a fold
 *   coupon    clicking the coupon's button cuts it out before following the link
 */
import { $, $$, onFrame, onSeen, reduced } from "./_kit";
import { clamp, lerp, smooth } from "../lib/util";

export default function start() {
  document.documentElement.classList.add("ht-live");
  dateline();
  ink();
  press();
  charts();
  running();
  folds();
  coupon();
  screen();
}

function dateline() {
  const el = $("[data-ht-date]");
  if (el) el.textContent = new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

function ink() {
  $$<HTMLElement>("[data-ht-ink]").forEach((h) => {
    if (reduced) { h.classList.add("ht-inked"); return; }
    onSeen(h, () => setTimeout(() => h.classList.add("ht-inked"), 120), 0.1);
  });
}

function press() {
  if (reduced) return;
  $$<HTMLElement>(".ht-front").forEach((f) => {
    if (!f.querySelector(".ht-plates")) return;
    f.classList.add("ht-press");
    onSeen(f, () => f.classList.add("ht-printed"), 0.5);
  });
}

function charts() {
  $$<HTMLElement>("[data-ht-figs]").forEach((f) => {
    if (reduced) { f.classList.add("ht-printed"); return; }
    onSeen(f, () => f.classList.add("ht-printed"), 0.35);
  });
}

function running() {
  const mast = $("[data-ht-mast]");
  const sec = $("[data-ht-runner]"), page = $("[data-ht-page]");
  const fronts = $$<HTMLElement>("main [data-ht-front]").map((f) => ({ el: (f.closest(".ht-sec") as HTMLElement) || f, name: f.dataset.sec || "", page: f.dataset.page || "" }));
  const root = document.documentElement;
  let last = "";
  onFrame(({ vh }) => {
    const on = !!mast && mast.getBoundingClientRect().bottom < 0;
    if (on !== root.classList.contains("ht-run")) root.classList.toggle("ht-run", on);
    let cur = fronts[0];
    for (const f of fronts) if (f.el.getBoundingClientRect().top < vh * 0.35) cur = f;
    const key = cur ? cur.name + cur.page : "";
    if (cur && key !== last) { last = key; if (sec) sec.textContent = cur.name; if (page) page.textContent = cur.page; }
  });
}

function folds() {
  if (reduced) return;
  const secs = $$<HTMLElement>("main .ht-sec");
  onFrame(({ vh }) => {
    for (let i = 0; i < secs.length - 1; i++) {
      const top = secs[i + 1].getBoundingClientRect().top;
      const d = top > vh || top < -vh ? 0 : smooth(vh * 0.7, vh * 0.15, top) * (1 - smooth(vh * 0.05, -vh * 0.3, top));
      secs[i].style.setProperty("--dim", d.toFixed(3));
    }
  });
}

function coupon() {
  $$<HTMLAnchorElement>("[data-ht-cut]").forEach((a) => {
    a.addEventListener("click", (e) => {
      const c = a.closest<HTMLElement>("[data-ht-coupon]");
      if (!c || reduced || c.classList.contains("is-cut")) return;
      const href = a.getAttribute("href") || "";
      c.classList.add("is-cut");
      if (href.startsWith("#") || e.metaKey || e.ctrlKey) return;   // same page: the cut is the answer
      e.preventDefault();
      setTimeout(() => { location.href = a.href; }, 700);
    });
  });
}

// ---------------------------------------------------------------- picture sources (grayscale, drawn for print)
function sunrise(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d")!;
  const sky = g.createLinearGradient(0, 0, 0, h * 0.7);
  sky.addColorStop(0, "#9a9a9a"); sky.addColorStop(0.5, "#d2d2d2"); sky.addColorStop(1, "#fafafa");
  g.fillStyle = sky; g.fillRect(0, 0, w, h);
  const sx = w * 0.62, sy = h * 0.6, sr = h * 0.13;
  const glow = g.createRadialGradient(sx, sy, sr * 0.6, sx, sy, sr * 4.5);
  glow.addColorStop(0, "rgba(255,255,255,.95)"); glow.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = glow; g.fillRect(0, 0, w, h);
  g.fillStyle = "#ffffff"; g.beginPath(); g.arc(sx, sy, sr, 0, Math.PI * 2); g.fill();
  // clouds
  g.fillStyle = "rgba(90,90,90,.35)";
  for (const [x, y, rx, ry] of [[0.2, 0.2, 0.16, 0.035], [0.32, 0.24, 0.12, 0.03], [0.78, 0.16, 0.14, 0.03], [0.55, 0.32, 0.2, 0.022]]) {
    g.beginPath(); g.ellipse(x * w, y * h, rx * w, ry * h, 0, 0, Math.PI * 2); g.fill();
  }
  const hill = (base: number, amp: number, freq: number, phase: number, shade: string) => {
    g.fillStyle = shade; g.beginPath(); g.moveTo(0, h);
    for (let x = 0; x <= w; x += 6) {
      const t = x / w;
      g.lineTo(x, h * base - Math.sin(t * freq + phase) * h * amp - Math.sin(t * freq * 2.7 + phase * 2) * h * amp * 0.35);
    }
    g.lineTo(w, h); g.closePath(); g.fill();
  };
  hill(0.66, 0.05, 5, 0.6, "#9a9a9a");
  hill(0.74, 0.06, 3.4, 2.2, "#5e5e5e");
  hill(0.86, 0.07, 2.2, 4.1, "#262626");
  // furrows on the near field, in perspective
  g.strokeStyle = "rgba(255,255,255,.18)"; g.lineWidth = 3;
  for (let i = -8; i <= 8; i++) { g.beginPath(); g.moveTo(w * 0.5 + i * w * 0.02, h * 0.82); g.lineTo(w * 0.5 + i * w * 0.16, h); g.stroke(); }
  // birds
  g.strokeStyle = "#2a2a2a"; g.lineWidth = 3; g.lineCap = "round";
  for (const [x, y, s] of [[0.3, 0.38, 14], [0.35, 0.34, 10], [0.4, 0.4, 12]]) {
    g.beginPath(); g.moveTo(x * w - s, y * h); g.quadraticCurveTo(x * w - s / 2, y * h - s / 2, x * w, y * h); g.quadraticCurveTo(x * w + s / 2, y * h - s / 2, x * w + s, y * h); g.stroke();
  }
  const vig = g.createRadialGradient(w / 2, h / 2, h * 0.3, w / 2, h / 2, w * 0.75);
  vig.addColorStop(0, "rgba(0,0,0,0)"); vig.addColorStop(1, "rgba(0,0,0,.35)");
  g.fillStyle = vig; g.fillRect(0, 0, w, h);
  return c;
}

function phonePhoto(w: number, h: number, d: DOMStringMap): HTMLCanvasElement {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d")!;
  const font = (wt: number, px: number, fam = '"Libre Franklin", Arial, sans-serif') => `${wt} ${px}px ${fam}`;
  // a desk under a window light
  const bg = g.createLinearGradient(0, 0, w, h);
  bg.addColorStop(0, "#9c9c9c"); bg.addColorStop(1, "#3a3a3a");
  g.fillStyle = bg; g.fillRect(0, 0, w, h);
  const spot = g.createRadialGradient(w * 0.35, h * 0.3, 10, w * 0.35, h * 0.3, w * 0.9);
  spot.addColorStop(0, "rgba(255,255,255,.55)"); spot.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = spot; g.fillRect(0, 0, w, h);
  // a cup in the corner
  g.fillStyle = "#1e1e1e"; g.beginPath(); g.ellipse(w * 0.86, h * 0.86, w * 0.16, w * 0.13, 0, 0, Math.PI * 2); g.fill();
  g.fillStyle = "#5a5a5a"; g.beginPath(); g.ellipse(w * 0.86, h * 0.86, w * 0.11, w * 0.085, 0, 0, Math.PI * 2); g.fill();
  g.save();
  g.translate(w * 0.48, h * 0.5); g.rotate(-0.12);
  const pw = w * 0.56, ph = pw * 2.05, r = pw * 0.16;
  const rr = (x: number, y: number, ww: number, hh: number, rad: number) => { g.beginPath(); g.roundRect(x, y, ww, hh, rad); };
  g.shadowColor = "rgba(0,0,0,.7)"; g.shadowBlur = 50; g.shadowOffsetX = 26; g.shadowOffsetY = 34;
  g.fillStyle = "#0e0e0e"; rr(-pw / 2, -ph / 2, pw, ph, r); g.fill();
  g.shadowColor = "transparent";
  g.strokeStyle = "#8a8a8a"; g.lineWidth = 3; rr(-pw / 2 + 2, -ph / 2 + 2, pw - 4, ph - 4, r); g.stroke();
  const m = pw * 0.045, sw = pw - m * 2, shh = ph - m * 2, x0 = -pw / 2 + m, y0 = -ph / 2 + m;
  const scr = g.createLinearGradient(x0, y0, x0 + sw, y0 + shh);
  scr.addColorStop(0, "#ffffff"); scr.addColorStop(1, "#dcdcdc");
  g.fillStyle = scr; rr(x0, y0, sw, shh, r * 0.8); g.fill();
  g.fillStyle = "#111"; rr(-sw * 0.16, y0 + sw * 0.04, sw * 0.32, sw * 0.08, sw * 0.04); g.fill();
  let y = y0 + sw * 0.22;
  const px = x0 + sw * 0.08, inner = sw * 0.84;
  g.textBaseline = "top";
  if (d.app) { g.fillStyle = "#6a6a6a"; g.font = font(600, sw * 0.055); g.fillText(d.app, px, y); y += sw * 0.09; }
  if (d.title) {
    g.fillStyle = "#121212"; g.font = font(700, sw * 0.095);
    const words = d.title.split(" "); let line = "";
    for (const wd of words) { const t = line ? line + " " + wd : wd; if (g.measureText(t).width > inner && line) { g.fillText(line, px, y); y += sw * 0.11; line = wd; } else line = t; }
    g.fillText(line, px, y); y += sw * 0.15;
  }
  if (d.label) { g.fillStyle = "#555"; g.font = font(700, sw * 0.045); g.fillText(d.label.toUpperCase(), px, y); y += sw * 0.08; }
  const opts = (d.opts || "").split("|").filter(Boolean).slice(0, 4);
  for (const o of opts) {
    const sel = o.endsWith("*");
    g.fillStyle = sel ? "#e8e8e8" : "#ffffff"; rr(px, y, inner, sw * 0.17, sw * 0.04); g.fill();
    g.strokeStyle = sel ? "#111" : "#b5b5b5"; g.lineWidth = sel ? 5 : 2; rr(px, y, inner, sw * 0.17, sw * 0.04); g.stroke();
    g.fillStyle = "#151515"; g.font = font(700, sw * 0.06); g.fillText(sel ? o.slice(0, -1) : o, px + sw * 0.05, y + sw * 0.055);
    y += sw * 0.21;
  }
  if (!opts.length) for (let i = 0; i < 4; i++) { g.fillStyle = i % 2 ? "#cfcfcf" : "#e2e2e2"; rr(px, y, inner * (0.9 - i * 0.12), sw * 0.05, 6); g.fill(); y += sw * 0.1; }
  if (d.button) {
    const by = y0 + shh - sw * 0.24;
    g.fillStyle = "#141414"; rr(px, by, inner, sw * 0.15, sw * 0.075); g.fill();
    g.fillStyle = "#f0f0f0"; g.font = font(700, sw * 0.058); g.textAlign = "center"; g.fillText(d.button, 0, by + sw * 0.045); g.textAlign = "left";
  }
  // glare across the glass
  const gl = g.createLinearGradient(x0, y0, x0 + sw, y0 + shh * 0.5);
  gl.addColorStop(0, "rgba(255,255,255,0)"); gl.addColorStop(0.5, "rgba(255,255,255,.22)"); gl.addColorStop(0.56, "rgba(255,255,255,0)");
  g.fillStyle = gl; rr(x0, y0, sw, shh, r * 0.8); g.fill();
  g.restore();
  return c;
}

function fromImage(src: string, w: number, h: number): Promise<HTMLCanvasElement> {
  return new Promise((res) => {
    const im = new Image();
    im.crossOrigin = "anonymous";
    im.onload = () => {
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      const g = c.getContext("2d")!;
      const s = Math.max(w / im.naturalWidth, h / im.naturalHeight);
      g.filter = "grayscale(1) contrast(1.15)";
      g.drawImage(im, (w - im.naturalWidth * s) / 2, (h - im.naturalHeight * s) / 2, im.naturalWidth * s, im.naturalHeight * s);
      res(c);
    };
    im.onerror = () => res(sunrise(w, h));
    im.src = src;
  });
}

// ---------------------------------------------------------------- the screen
const VERT = `attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `precision highp float;
uniform vec2 uRes; uniform vec4 uRect; uniform float uCell; uniform vec3 uLoupe; uniform float uZoom; uniform float uAA; uniform sampler2D uTex;
const vec3 PAPER = vec3(0.953, 0.937, 0.902);
const vec3 INK = vec3(0.078, 0.078, 0.078);
const vec3 SPOT = vec3(0.925, 0.0, 0.549);
float lumAt(vec2 p) {
  vec2 uv = p / uRect.zw;
  if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return 1.0;
  return texture2D(uTex, uv).r;
}
float dots(vec2 p, float cell, float ang, float lo, float hi, float aa) {
  float cs = cos(ang), sn = sin(ang);
  vec2 q = vec2(cs * p.x - sn * p.y, sn * p.x + cs * p.y);
  vec2 id = floor(q / cell);
  float best = 0.0;
  for (int dx = -1; dx <= 1; dx++) for (int dy = -1; dy <= 1; dy++) {
    vec2 c = (id + vec2(float(dx), float(dy)) + 0.5) * cell;
    vec2 ip = vec2(cs * c.x + sn * c.y, -sn * c.x + cs * c.y);
    float dark = smoothstep(lo, hi, 1.0 - lumAt(ip));
    float r = sqrt(dark) * cell * 0.71;
    float d = length(q - c);
    best = max(best, 1.0 - smoothstep(r - aa, r + aa, d));
  }
  return best;
}
void main() {
  vec2 px = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y);
  vec2 sp = px - uRect.xy;
  vec2 lp = px - uLoupe.xy;
  float inL = uLoupe.z > 0.0 ? step(length(lp), uLoupe.z) : 0.0;
  float aa = uAA;
  if (inL > 0.5) { sp = (uLoupe.xy - uRect.xy) + lp / uZoom; aa = uAA / uZoom; }
  float k = dots(sp, uCell, 0.7854, 0.08, 1.0, aa);
  float s = dots(sp + vec2(uCell * 0.31, uCell * 0.17), uCell, 1.309, 0.22, 0.8, aa) * (1.0 - 0.6 * k);
  vec3 col = PAPER;
  col *= mix(vec3(1.0), mix(vec3(1.0), SPOT, 0.5), s);
  col *= mix(vec3(1.0), INK, k);
  if (inL > 0.5) col *= 1.0 - 0.18 * smoothstep(0.65, 1.0, length(lp) / uLoupe.z);
  gl_FragColor = vec4(col, 1.0);
}`;

function screen() {
  const figs = $$<HTMLElement>("[data-ht-img]");
  if (!figs.length) return;
  const canvas = document.createElement("canvas");
  canvas.className = "ht-canvas";
  canvas.setAttribute("aria-hidden", "true");
  document.body.appendChild(canvas);
  const gl = canvas.getContext("webgl", { antialias: false, alpha: true, premultipliedAlpha: true }) as WebGLRenderingContext | null;
  if (!gl) { canvas.remove(); return; }
  const mk = (t: number, s: string) => { const o = gl.createShader(t)!; gl.shaderSource(o, s); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o) || ""); return o; };
  const prog = gl.createProgram()!;
  try {
    gl.attachShader(prog, mk(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, mk(gl.FRAGMENT_SHADER, FRAG)); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error("link");
  } catch (err) { console.warn("[halftone] screen unavailable", err); canvas.remove(); return; }
  gl.useProgram(prog);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = (n: string) => gl.getUniformLocation(prog, n);
  const u = { res: U("uRes"), rect: U("uRect"), cell: U("uCell"), loupe: U("uLoupe"), zoom: U("uZoom"), aa: U("uAA"), tex: U("uTex") };
  gl.uniform1i(u.tex, 0);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  document.documentElement.classList.add("ht-gl");

  type Pic = { fig: HTMLElement; plate: HTMLElement; tex: WebGLTexture | null };
  const pics: Pic[] = figs.map((fig) => ({ fig, plate: $(".ht-photo__plate", fig) || fig, tex: null }));
  const upload = (p: Pic, c: HTMLCanvasElement) => {
    const t = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    p.tex = t; dirty = true;
  };
  let dirty = true;
  const build = () => pics.forEach((p) => {
    const r = p.plate.getBoundingClientRect();
    const aspect = r.height / Math.max(1, r.width) || 0.625;
    const w = 1000, h = Math.round(w * aspect);
    const kind = p.fig.dataset.htImg;
    if (kind === "url" && p.fig.dataset.src) fromImage(p.fig.dataset.src, w, h).then((c) => upload(p, c));
    else if (kind === "phone") upload(p, phonePhoto(w, h, p.fig.dataset));
    else upload(p, sunrise(w, h));
  });
  (document.fonts?.ready ?? Promise.resolve()).then(build);

  // the loupe
  const loupeEl = $(".ht-loupe");
  let loupe = { x: 0, y: 0, on: false, pic: null as Pic | null };
  const hit = (x: number, y: number) => pics.find((p) => { const r = p.plate.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; }) || null;
  const place = () => {
    if (!loupeEl) return;
    loupeEl.classList.toggle("is-on", loupe.on);
    if (loupe.on) loupeEl.style.transform = `translate(${loupe.x}px, ${loupe.y}px)`;
  };
  addEventListener("pointermove", (e) => {
    if (e.pointerType === "touch") return;
    const p = hit(e.clientX, e.clientY);
    loupe = { x: e.clientX, y: e.clientY, on: !!p, pic: p };
    place(); dirty = true;
  }, { passive: true });
  addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "touch") return;
    const p = hit(e.clientX, e.clientY);
    loupe = p && !(loupe.on && loupe.pic === p) ? { x: e.clientX, y: e.clientY, on: true, pic: p } : { ...loupe, on: false };
    place(); dirty = true;
  }, { passive: true });
  addEventListener("scroll", () => { if (loupe.on && loupe.pic && !hit(loupe.x, loupe.y)) { loupe.on = false; place(); } }, { passive: true });

  let W = 0, H = 0, scale = 1, key = "";
  const resize = () => {
    scale = Math.min(devicePixelRatio || 1, 2);
    W = Math.round(innerWidth * scale); H = Math.round(innerHeight * scale);
    canvas.width = W; canvas.height = H; dirty = true;
  };
  resize();
  addEventListener("resize", resize);
  const small = () => matchMedia("(max-width: 900px)").matches;

  onFrame(({ y, vh }) => {
    const k2 = `${y.toFixed(1)}|${W}|${H}`;
    if (k2 === key && !dirty) return;
    key = k2; dirty = false;
    gl.viewport(0, 0, W, H);
    gl.disable(gl.SCISSOR_TEST);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.SCISSOR_TEST);
    gl.uniform2f(u.res, W, H);
    gl.uniform1f(u.aa, 0.9 * scale);
    gl.uniform1f(u.zoom, 3.4);
    for (const p of pics) {
      if (!p.tex) continue;
      const r = p.plate.getBoundingClientRect();
      if (r.bottom <= 0 || r.top >= vh || r.width < 2) continue;
      // scroll progress is the screen frequency: fine at reading position, coarse at the edges
      const cy = r.top + r.height / 2;
      const dist = Math.abs(cy - vh * 0.5) / (vh * 0.75);
      const fine = reduced ? 1 : 1 - smooth(0.22, 1.0, dist);
      const coarse = small() ? 22 : 30, fineCell = small() ? 4.2 : 4.8;
      const cell = lerp(coarse, fineCell, Math.pow(fine, 0.75)) * scale;
      const x0 = Math.max(0, Math.floor(r.left * scale)), y0 = Math.max(0, Math.floor(r.top * scale));
      const x1 = Math.min(W, Math.ceil(r.right * scale)), y1 = Math.min(H, Math.ceil(r.bottom * scale));
      if (x1 <= x0 || y1 <= y0) continue;
      gl.scissor(x0, H - y1, x1 - x0, y1 - y0);
      gl.bindTexture(gl.TEXTURE_2D, p.tex);
      gl.uniform4f(u.rect, r.left * scale, r.top * scale, r.width * scale, r.height * scale);
      gl.uniform1f(u.cell, cell);
      const lr = (small() ? 75 : 100) * scale;
      gl.uniform3f(u.loupe, loupe.x * scale, loupe.y * scale, loupe.on && loupe.pic === p ? lr : 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
  });
  void clamp;
}
