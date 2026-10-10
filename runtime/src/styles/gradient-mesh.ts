/**
 * Gradient mesh: weather. Scrolling changes the conditions of one continuous field; it never moves you between
 * scenes. Nothing pins, snaps or cuts.
 *
 *   field     one fixed WebGL canvas paints a noise-warped four-colour field, but only inside the page's mesh zones
 *             ([data-gm-zone]: the hero band, the product band, card patches, the closing band), read from the DOM
 *             every frame. Outside them it is transparent, so the calm ground shows.
 *   palette   the four colours interpolate between section palettes over about a screen of scroll
 *   velocity  fast scrolling ruffles the field (at most ~15% more amplitude), settling over 1-2 s when you stop
 *   pointer   a low, heavily lagged attractor bends the field near the cursor; card patches wake on hover
 *   arrivals  the headline rises line by line; copy rises 14px once; figures count up once, slowly
 *   timeline  the rail fills with the field's colours as you read down it
 */
import { $, $$, onFrame, onSeen, reduced } from "./_kit";
import { clamp, lerp, smooth } from "../lib/util";

type RGB = [number, number, number];
const hex = (h: string): RGB => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255) as RGB;
const PALS: RGB[][] = [
  ["#ef008f", "#6ec3f4", "#7038ff", "#ffba27"],   // hero: magenta, sky, violet, gold
  ["#00d4ff", "#3ee1a8", "#80e9ff", "#635bff"],   // cool developer teal
  ["#635bff", "#a960ee", "#90e0ff", "#ff6ec7"],   // lilac
  ["#1a1f71", "#635bff", "#00d4ff", "#80e9ff"],   // deep enterprise navy
  ["#ff7a59", "#ffba27", "#ef008f", "#a960ee"],   // warm
].map((p) => p.map(hex));
const mobile = () => matchMedia("(max-width: 900px)").matches;
const MAXZ = 12;

export default function start() {
  document.documentElement.classList.add("gm-live");
  lines();
  rises();
  counts();
  rail();
  navState();
  parallax();
  field();
}

// ---------------------------------------------------------------- arrivals
function lines() {
  $$<HTMLElement>("[data-gm-lines]").forEach((h) => {
    const words: HTMLElement[] = [];
    const label = (h.textContent || "").trim();
    const walk = (node: Node) => {
      if (node.nodeType === 3) {
        const frag = document.createDocumentFragment();
        (node.textContent || "").split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
          const w = document.createElement("span"); w.className = "gm-w"; w.textContent = part;
          words.push(w); frag.appendChild(w);
        });
        node.parentNode!.replaceChild(frag, node);
      } else [...node.childNodes].forEach(walk);
    };
    [...h.childNodes].forEach(walk);
    h.setAttribute("aria-label", label);
    const assign = () => {
      let line = -1, top = -1e9;
      for (const w of words) { if (w.offsetTop > top + 4) { line++; top = w.offsetTop; } w.style.setProperty("--l", String(line)); }
    };
    assign();
    document.fonts?.ready.then(assign);
  });
}

function rises() {
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("gm-in"); io.unobserve(e.target); }
  }), { threshold: 0.2, rootMargin: "0px 0px -6% 0px" });
  $$(".gm-rise, [data-gm-lines]").forEach((el) => io.observe(el));
}

function counts() {
  $$<HTMLElement>("[data-gm-count]").forEach((v) => {
    const raw = v.dataset.gmCount || "";
    const end = parseFloat(raw.replace(/,/g, ""));
    const dec = (raw.split(".")[1] || "").length, grouped = raw.includes(",");
    if (reduced || !isFinite(end)) return;
    const fmt = (x: number) => (grouped ? x.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : x.toFixed(dec));
    v.setAttribute("aria-label", raw);
    v.textContent = fmt(0);
    onSeen(v.closest(".gm-figure") || v, () => {
      const t0 = performance.now(), dur = 2100;
      const step = (now: number) => {
        const k = clamp((now - t0) / dur);
        v.textContent = fmt(end * (1 - Math.pow(1 - k, 4)));
        if (k < 1) requestAnimationFrame(step); else v.textContent = raw;
      };
      requestAnimationFrame(step);
    }, 0.4);
  });
}

function rail() {
  $$<HTMLElement>("[data-gm-line]").forEach((list) => {
    const fill = $(".gm-steps__rail i", list);
    const steps = $$<HTMLElement>(".gm-step", list);
    onFrame(({ vh }) => {
      const r = list.getBoundingClientRect();
      if (r.bottom < -vh || r.top > vh * 2) return;
      const k = reduced ? 1 : clamp((vh * 0.62 - r.top) / Math.max(1, r.height));
      fill?.style.setProperty("--fill", k.toFixed(4));
      steps.forEach((s) => s.classList.toggle("is-on", reduced || s.getBoundingClientRect().top < vh * 0.62));
    });
  });
}

function navState() {
  const hero = $(".gm-hero");
  const root = document.documentElement;
  onFrame(() => {
    const past = !hero || hero.getBoundingClientRect().bottom < 90;
    if (past !== root.classList.contains("gm-past")) root.classList.toggle("gm-past", past);
  });
}

function parallax() {
  if (reduced) return;
  const els = $$<HTMLElement>("[data-gm-par]").map((el) => ({ el, d: parseFloat(el.dataset.gmPar || "1"), off: 0 }));
  onFrame(({ vh }) => {
    for (const it of els) {
      const r = it.el.getBoundingClientRect();
      if (r.bottom < -200 || r.top > vh + 200) continue;
      const c = r.top + r.height / 2 - it.off;
      it.off = clamp((c - vh / 2) * (it.d - 1), -80, 80);
      it.el.style.transform = `translate3d(0, ${it.off.toFixed(1)}px, 0)`;
    }
  });
}

// ---------------------------------------------------------------- the field
const VERT = `attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `precision highp float;
uniform vec2 uRes; uniform float uScale;
uniform vec3 uC0; uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3; uniform vec3 uGround;
uniform float uAmp; uniform vec3 uPtr;
uniform int uN;
uniform vec4 uR[${MAXZ}]; uniform vec4 uE[${MAXZ}]; uniform vec4 uK[${MAXZ}]; uniform vec4 uW[${MAXZ}];
vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
float sdRound(vec2 p, vec2 b, float r){ vec2 q = abs(p) - b + r; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r; }
void main(){
  vec2 px = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y);
  float mask = 0.0; vec4 R = vec4(0.0); vec4 K = vec4(0.0); vec4 W = vec4(0.0);
  for (int i = 0; i < ${MAXZ}; i++) {
    if (i >= uN) break;
    vec4 r = uR[i]; vec4 e = uE[i];
    float lx = clamp((px.x - r.x) / max(r.z, 1.0), 0.0, 1.0);
    float m;
    if (uK[i].w > 1.5) {            // a rounded patch, top corners rounded (the card clips the rest)
      float rad = uK[i].y;
      vec2 c = vec2(r.x + r.z * 0.5, r.y + (r.w + rad) * 0.5);
      m = clamp(0.5 - sdRound(px - c, vec2(r.z, r.w + rad) * 0.5, rad), 0.0, 1.0) * clamp(r.y + r.w - px.y + 0.5, 0.0, 1.0);
    } else {                         // a band with angled top and bottom edges
      float yt = r.y + mix(e.x, e.y, lx); float yb = r.y + r.w - mix(e.z, e.w, lx);
      m = clamp(px.y - yt + 0.5, 0.0, 1.0) * clamp(yb - px.y + 0.5, 0.0, 1.0) * clamp(px.x - r.x + 0.5, 0.0, 1.0) * clamp(r.x + r.z - px.x + 0.5, 0.0, 1.0);
    }
    if (m > mask) { mask = m; R = r; K = uK[i]; W = uW[i]; }
  }
  if (mask <= 0.0) { gl_FragColor = vec4(0.0); return; }
  float s = K.x;
  float t = K.z;
  vec2 uv = px / (uRes.y * 0.9) ;
  // pointer: a hand near water
  vec2 d = px - uPtr.xy; float infl = exp(-dot(d, d) / (220.0 * 220.0 * uScale * uScale)) * uPtr.z;
  uv += normalize(d + 0.0001) * infl * 0.05;
  vec2 q = vec2(snoise(vec3(uv * 0.8, t * 0.35)), snoise(vec3(uv * 0.8 + 5.2, t * 0.35)));
  vec2 w = uv + q * 0.55 * uAmp;
  float n1 = snoise(vec3(w * 0.7, t * 0.5)) * 0.5 + 0.5;
  float n2 = snoise(vec3(w * 1.05 + 3.1, t * 0.6)) * 0.5 + 0.5;
  float n3 = snoise(vec3(w * 0.55 + 7.7, t * 0.42)) * 0.5 + 0.5;
  vec3 col = uC0;
  col = mix(col, uC1, smoothstep(0.32, 0.78, n1));
  col = mix(col, uC2, smoothstep(0.38, 0.82, n2));
  col = mix(col, uC3, smoothstep(0.5, 0.9, n3) * 0.9);
  // a resting patch is quieter: paler, closer to the ground
  col = mix(mix(col, uGround, 0.5), col, s);
  col += infl * 0.06 * s;
  // the hero darkens a little under the nav, so its white links read
  if (K.w > 0.5 && K.w < 1.5) col = mix(col, vec3(0.04, 0.1, 0.2), 0.52 * (1.0 - smoothstep(20.0 * uScale, 150.0 * uScale, px.y - R.y)));
  // mist behind copy that sits on the field
  if (W.w > 0.0) {
    vec2 wc = R.xy + W.xy * R.zw; vec2 wr = R.zw * W.z;
    float dd = length((px - wc) / wr);
    col = mix(col, uGround, W.w * (1.0 - smoothstep(0.25, 1.0, dd)));
  }
  col += (hash(px + fract(t)) - 0.5) * 0.045;     // grain against banding
  gl_FragColor = vec4(col * mask, mask);
}`;

function field() {
  const canvas = $<HTMLCanvasElement>(".gm-field");
  if (!canvas) return;
  const gl = canvas.getContext("webgl", { premultipliedAlpha: true, antialias: false, alpha: true }) as WebGLRenderingContext | null;
  if (!gl) return;
  const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader"); return s; };
  let prog: WebGLProgram;
  try {
    prog = gl.createProgram()!;
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error("link");
  } catch (err) { console.warn("[gradient-mesh] field unavailable", err); return; }
  gl.useProgram(prog);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = (n: string) => gl.getUniformLocation(prog, n);
  const u = { res: U("uRes"), scale: U("uScale"), c: [0, 1, 2, 3].map((i) => U(`uC${i}`)), ground: U("uGround"), amp: U("uAmp"), ptr: U("uPtr"), n: U("uN"), r: U("uR"), e: U("uE"), k: U("uK"), w: U("uW") };
  gl.uniform3fv(u.ground, hex("#f6f9fc"));
  document.documentElement.classList.add("gm-gl");

  type Zone = { el: HTMLElement; kind: number; cutT: number; cutB: number; rest: number; s: number; target: number; t: number; wash: number[]; mwash: number[]; radius: number };
  const zones: Zone[] = $$<HTMLElement>("[data-gm-zone]").map((el) => {
    const kindName = el.dataset.gmZone;
    const nums = (a?: string) => (a ? a.split(",").map(Number) : [0, 0, 0, 0]);
    const rest = parseFloat(el.dataset.rest || "1");
    return { el, kind: kindName === "patch" ? 2 : el.classList.contains("gm-zone--hero") ? 1 : 0, cutT: parseFloat(el.dataset.cutT || "0"), cutB: parseFloat(el.dataset.cutB || "0"),
      rest, s: rest, target: rest, t: Math.random() * 20, wash: nums(el.dataset.wash), mwash: nums(el.dataset.mwash || el.dataset.wash), radius: parseFloat(el.dataset.r || "0") };
  });
  // card patches wake on hover
  $$<HTMLElement>("[data-gm-card]").forEach((card) => {
    const z = zones.find((z) => card.contains(z.el));
    if (!z) return;
    card.addEventListener("pointerenter", () => { z.target = 1; });
    card.addEventListener("pointerleave", () => { z.target = z.rest; });
  });

  // palettes per section, handed over between section centres
  const secs = $$<HTMLElement>("main > section, main > .gm-sec, main > div > section");
  const pal = secs.map((s, i) => { const p = s.dataset.gmPal; return PALS[p != null ? +p : i % PALS.length]; });
  let ptr = { x: -9999, y: -9999, z: 0 }, ptrT = { x: -9999, y: -9999, z: 0 };
  addEventListener("pointermove", (e) => { ptrT = { x: e.clientX, y: e.clientY, z: 1 }; if (ptr.x < -999) ptr = { ...ptrT, z: 0 }; }, { passive: true });
  document.addEventListener("pointerleave", () => { ptrT.z = 0; });

  let W = 0, H = 0, scale = 1, boost = 0, frame = 0, lastKey = "";
  const resize = () => {
    scale = Math.min(devicePixelRatio || 1, 2) * (mobile() ? 0.6 : 0.5);
    W = Math.max(1, Math.round(innerWidth * scale)); H = Math.max(1, Math.round(innerHeight * scale));
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; gl.viewport(0, 0, W, H); }
    lastKey = "";
  };
  resize();
  addEventListener("resize", resize);
  const R = new Float32Array(MAXZ * 4), E = new Float32Array(MAXZ * 4), K = new Float32Array(MAXZ * 4), Wa = new Float32Array(MAXZ * 4);
  const root = document.documentElement;
  let palKey = "";

  onFrame(({ v, dt, vh, y }) => {
    // the conditions: velocity -> turbulence, eased back over ~1.5 s
    const want = reduced ? 0 : Math.min(0.15, Math.abs(v) * 0.012);
    boost += (want - boost) * (want > boost ? 0.15 : 0.025);
    ptr.x += (ptrT.x - ptr.x) * 0.06; ptr.y += (ptrT.y - ptr.y) * 0.06; ptr.z += (ptrT.z - ptr.z) * 0.05;
    // palette
    const mid = vh / 2;
    const centres = secs.map((s) => { const r = s.getBoundingClientRect(); return r.top + r.height / 2; });
    let f = 0;
    if (centres.length) {
      if (mid <= centres[0]) f = 0;
      else if (mid >= centres[centres.length - 1]) f = centres.length - 1;
      else for (let i = 0; i < centres.length - 1; i++) if (mid >= centres[i] && mid < centres[i + 1]) {
        const k = (mid - centres[i]) / (centres[i + 1] - centres[i]);
        f = i + (reduced ? (k > 0.5 ? 1 : 0) : smooth(0.15, 0.85, k));
        break;
      }
    }
    const i0 = Math.floor(f), kk = f - i0;
    const a = pal[i0] || PALS[0], b = pal[Math.min(pal.length - 1, i0 + 1)] || a;
    const cols = [0, 1, 2, 3].map((j) => a[j].map((c, n) => lerp(c, b[j][n], kk)) as RGB);
    const pk = f.toFixed(3);
    if (pk !== palKey) {
      palKey = pk;
      cols.forEach((c, j) => root.style.setProperty(`--gm${j + 1}`, "#" + c.map((x) => Math.round(x * 255).toString(16).padStart(2, "0")).join("")));
    }
    // zones on screen
    let n = 0, active = false;
    const small = mobile();
    for (const z of zones) {
      z.s += (z.target - z.s) * 0.06;
      if (Math.abs(z.target - z.s) > 0.01) active = true;
      z.t += reduced ? 0 : dt * (0.32 + 0.7 * z.s) * (1 + boost * 3);
      if (n >= MAXZ) continue;
      const r = z.el.getBoundingClientRect();
      if (r.bottom <= 0 || r.top >= vh || r.width < 1) continue;
      const o = n * 4;
      R[o] = r.left * scale; R[o + 1] = r.top * scale; R[o + 2] = r.width * scale; R[o + 3] = r.height * scale;
      // the angle of a band shifts a degree or two as it crosses the screen
      const drift = reduced ? 0 : ((r.top + r.height / 2) / vh - 0.5) * 1.5;
      const tt = Math.tan(((z.cutT ? z.cutT + drift : 0) * Math.PI) / 180) * r.width * scale;
      const tb = Math.tan(((z.cutB ? z.cutB - drift : 0) * Math.PI) / 180) * r.width * scale;
      // positive angle: the edge rises to the right
      E[o] = tt > 0 ? tt : 0; E[o + 1] = tt > 0 ? 0 : -tt;
      E[o + 2] = tb > 0 ? 0 : -tb; E[o + 3] = tb > 0 ? tb : 0;
      K[o] = z.s; K[o + 1] = z.radius * scale; K[o + 2] = z.t; K[o + 3] = z.kind;
      const wsh = small ? z.mwash : z.wash;
      Wa[o] = wsh[0]; Wa[o + 1] = wsh[1]; Wa[o + 2] = wsh[2] || 0.5; Wa[o + 3] = wsh[3] || 0;
      n++;
    }
    if (!n) { if (lastKey !== "empty") { gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); lastKey = "empty"; } return; }
    // reduced motion: draw only when something changed; otherwise ~30 fps at rest, 60 while scrolling or hovering
    const moving = Math.abs(v) > 0.3 || active || ptr.z > 0.02 || boost > 0.005;
    frame++;
    const key = `${y.toFixed(0)}|${pk}|${n}|${innerWidth}`;
    if (reduced && key === lastKey) return;
    if (!reduced && !moving && frame % 2) return;
    lastKey = key;
    gl.uniform2f(u.res, W, H); gl.uniform1f(u.scale, scale);
    cols.forEach((c, j) => gl.uniform3fv(u.c[j], c));
    gl.uniform1f(u.amp, 1 + boost);
    gl.uniform3f(u.ptr, ptr.x * scale, ptr.y * scale, reduced ? 0 : ptr.z);
    gl.uniform1i(u.n, n);
    gl.uniform4fv(u.r, R); gl.uniform4fv(u.e, E); gl.uniform4fv(u.k, K); gl.uniform4fv(u.w, Wa);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  });
}
