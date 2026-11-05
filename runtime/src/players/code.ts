/**
 * code: a flight through a codebase, following an agent at work.
 *   terminal  the agent's prompt box fills the screen and the task types itself; then the camera dives through it
 *   read      files the agent reads line the corridor; a scan bar sweeps each one as the camera passes
 *   edit      a stop: the removed lines light up red and fold away, the new ones type themselves in green
 *   run       a terminal stop whose output prints line by line (PASS / ✓ / Tests: …)
 *   outro     the camera pulls back over the whole route, every touched file glowing
 * Every pane is real text drawn to a canvas, so the code stays readable at any size.
 */
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import type { PlayerFactory } from "../lib/types";
import { clamp, cssVar, easeInOut, isMobile, lerp, rng, smooth } from "../lib/util";

type Op = " " | "+" | "-";
interface CFile { path: string; kind: "read" | "edit" | "run"; lang: string; label: string; todo?: string | null; lines: [Op, string][]; at: [number, number] }
interface Term { logo: string; prompt: string; agent: string; model: string; provider: string; hints: string[] }

// ---------------------------------------------------------------- highlighting
const KW = new Set(("abstract and as async await break case catch class const continue declare default do else elif enum " +
  "except export extends false final finally fn for foreach from func function go if impl implements import in instanceof " +
  "interface lambda let match mod mut namespace new nil null None package pass private protected pub public raise readonly " +
  "return self static struct super switch this throw true True False try type use var void while with yield def").split(" "));
const C = { text: "#d4d4d8", kw: "#c792ea", str: "#9ece6a", num: "#ff9e64", com: "#5c6370", fn: "#7aa2f7", type: "#e0af68",
  vari: "#f7768e", tag: "#7dcfff", punc: "#8b929b", dim: "#6b7079", add: "#3fb950", del: "#f85149", line: "#4b5059" };
const SLASH = new Set(["php", "ts", "tsx", "js", "go", "rust", "java", "kt", "swift", "c", "cs", "css"]);
const HASH = new Set(["py", "sh", "rb", "yaml", "toml"]);

function tokenize(line: string, lang: string): [string, string][] {
  const com = SLASH.has(lang) ? String.raw`\/\/.*$|\/\*.*?\*\/` : HASH.has(lang) ? "#.*$" : lang === "sql" ? "--.*$" : "(?!x)x";
  const re = new RegExp(`(${com})|('(?:\\\\.|[^'\\\\])*'|"(?:\\\\.|[^"\\\\])*"|\`(?:\\\\.|[^\`\\\\])*\`)|(\\b\\d+(?:\\.\\d+)?\\b)|(\\$[A-Za-z_]\\w*)|(<\\/?[A-Za-z][\\w.]*)|([A-Za-z_]\\w*)(?=\\s*\\()|([A-Za-z_]\\w*)|(\\s+)|(.)`, "g");
  const out: [string, string][] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    const [t] = m;
    if (!t) { re.lastIndex++; continue; }
    const col = m[1] ? C.com : m[2] ? C.str : m[3] ? C.num : m[4] ? C.vari : m[5] ? C.tag : m[6] ? (KW.has(t) ? C.kw : C.fn)
      : m[7] ? (KW.has(t) ? C.kw : /^[A-Z]/.test(t) ? C.type : C.text) : m[8] ? C.text : C.punc;
    out.push([t, col]);
  }
  return out;
}

// ---------------------------------------------------------------- one file, drawn to a canvas
const MOB = isMobile();
const PX = { lh: 31, font: 20, pad: 26, head: 66, gutter: 74 };
const S = 9 / 1200;                      // world units per canvas pixel: the same text size on every pane
// how big code looks: canvas pixels to screen pixels on a 900px-tall screen (scales with the screen)
const TEXT_SCALE = MOB ? 0.5 : 0.74;

function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}

class Pane {
  f: CFile; canvas = document.createElement("canvas"); g: CanvasRenderingContext2D; tex: THREE.CanvasTexture;
  mesh: THREE.Mesh; mat: THREE.MeshBasicMaterial; hpx: number; wpx: number; key = ""; focusPx = 0; glow = 0; base = 1; drawn = 0;
  toks: [string, string][][];
  constructor(f: CFile, private mono: string, private accent: string, aniso: number) {
    this.f = f;
    this.hpx = PX.head + PX.pad * 2 + Math.max(6, f.lines.length) * PX.lh;
    this.g = this.canvas.getContext("2d")!;
    // as wide as the longest line (or the path), so nothing is cut off
    this.g.font = `400 ${PX.font}px "${mono}", ui-monospace, monospace`;
    const cw = this.g.measureText("M").width;
    const longest = Math.max(...f.lines.map(([, t]) => t.length), f.path.length + 14);
    this.wpx = Math.round(clamp((f.kind === "run" ? PX.pad * 2 : PX.gutter + PX.pad * 2 + 22) + longest * cw + 24, 760, 1800));
    this.canvas.width = this.wpx; this.canvas.height = this.hpx;
    this.toks = f.lines.map(([, t]) => tokenize(t, f.lang));
    this.tex = new THREE.CanvasTexture(this.canvas);
    this.tex.colorSpace = THREE.SRGBColorSpace; this.tex.anisotropy = aniso;
    this.tex.minFilter = THREE.LinearMipmapLinearFilter;
    this.mat = new THREE.MeshBasicMaterial({ map: this.tex, transparent: true, depthWrite: false, side: THREE.DoubleSide });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(this.wpx * S, this.hpx * S), this.mat);
  }
  get h() { return this.hpx * S; }
  get w() { return this.wpx * S; }

  /** k: 0-1 through this file's own beat (read sweep, edit, or run output) */
  draw(k: number) {
    const now = performance.now();
    if (k > 0 && k < 1 && now - this.drawn < 30) return;   // mid-animation: skip; the next frame catches up
    const key = this.f.kind === "read" ? (k <= 0 || k >= 1 ? String(k >= 1) : (Math.round(k * 60) / 60).toFixed(3)) : (Math.round(k * 400) / 400).toFixed(4);
    if (key === this.key) return;
    this.key = key; this.drawn = now;
    const g = this.g, f = this.f, W = this.wpx;
    g.clearRect(0, 0, W, this.hpx);
    g.textBaseline = "middle";
    const font = (wgt = 400) => `${wgt} ${PX.font}px "${this.mono}", ui-monospace, monospace`;

    // which lines show, how tall each is, how much of each is typed
    const rows: { i: number; h: number; typed: number; op: Op; n: string }[] = [];
    let num = 0;
    if (f.kind === "edit") {
      const adds = f.lines.map((l, i) => (l[0] === "+" ? i : -1)).filter((i) => i >= 0);
      const fold = smooth(0.18, 0.38, k), a = clamp((k - 0.4) / 0.52) * adds.length;
      f.lines.forEach(([op], i) => {
        if (op === "-") { rows.push({ i, h: 1 - fold, typed: 1, op, n: "" }); return; }
        if (op === "+") {
          const j = adds.indexOf(i), t = clamp(a - j);
          const hh = clamp((a - j) * 4); if (hh > 0.02) num++;   // a line counts once it starts to appear
          rows.push({ i, h: hh, typed: t, op, n: String(num) }); return;
        }
        num++; rows.push({ i, h: 1, typed: 1, op, n: String(num) });
      });
    } else if (f.kind === "run") {
      const shown = Math.floor(clamp(k * 1.12) * f.lines.length);
      f.lines.forEach((_, i) => rows.push({ i, h: i < shown ? 1 : 0, typed: 1, op: " ", n: "" }));
    } else f.lines.forEach((_, i) => rows.push({ i, h: 1, typed: 1, op: " ", n: String(i + 1) }));

    const bodyH = rows.reduce((s, r) => s + r.h * PX.lh, 0);
    const H = Math.min(this.hpx, PX.head + PX.pad * 2 + Math.max(bodyH, f.kind === "run" ? PX.lh * 2 : PX.lh * 4));
    // panel
    roundRect(g, 1, 1, W - 2, H - 2, 18);
    g.fillStyle = f.kind === "run" ? "rgba(8,9,11,0.94)" : "rgba(16,17,20,0.93)"; g.fill();
    g.lineWidth = 2;
    g.strokeStyle = this.glow > 0.01 ? `rgba(${hexRgb(this.accent)},${0.25 + 0.6 * this.glow})` : "rgba(255,255,255,0.09)"; g.stroke();
    // header: tag + path
    g.save(); roundRect(g, 1, 1, W - 2, PX.head, 18); g.clip();
    g.fillStyle = "rgba(255,255,255,0.035)"; g.fillRect(0, 0, W, PX.head); g.restore();
    g.fillStyle = "rgba(255,255,255,0.07)"; g.fillRect(0, PX.head, W, 1);
    const tagCol = f.kind === "edit" ? this.accent : f.kind === "run" ? C.add : C.fn;
    g.font = font(700); const tag = f.kind === "run" ? "$" : f.label;
    const tw = g.measureText(tag).width + 26;
    roundRect(g, PX.pad, PX.head / 2 - 17, tw, 34, 8); g.fillStyle = `rgba(${hexRgb(tagCol)},0.16)`; g.fill();
    g.fillStyle = tagCol; g.fillText(tag, PX.pad + 13, PX.head / 2 + 1);
    const slash = f.path.lastIndexOf("/");
    g.font = font(400); g.fillStyle = C.dim;
    const x0 = PX.pad + tw + 16, dir = f.kind === "run" ? "" : f.path.slice(0, slash + 1);
    g.fillText(dir, x0, PX.head / 2 + 1);
    g.font = font(600); g.fillStyle = "#eceef1";
    g.fillText(f.kind === "run" ? f.path : f.path.slice(slash + 1), x0 + g.measureText(dir).width * (dir ? 1 : 0), PX.head / 2 + 1);

    // body
    let y = PX.head + PX.pad;
    const gx = f.kind === "run" ? PX.pad : PX.gutter + PX.pad, codeX = gx + (f.kind === "run" ? 0 : 22);
    this.focusPx = y;
    g.font = font(400);
    const cw = g.measureText("M").width;
    for (const r of rows) {
      if (r.h < 0.02) continue;
      const lh = r.h * PX.lh, cy = y + lh / 2;
      g.save(); g.beginPath(); g.rect(0, y, W, lh); g.clip();
      if (r.op === "-") {
        const hl = smooth(0, 0.16, k);
        g.fillStyle = `rgba(248,81,73,${0.2 * hl})`; g.fillRect(2, y, W - 4, lh);
        g.fillStyle = `rgba(248,81,73,${0.9 * hl})`; g.fillRect(2, y, 4, lh);
      } else if (r.op === "+") {
        const settle = k >= 1 ? 0.5 : 1;
        g.fillStyle = `rgba(63,185,80,${0.17 * settle})`; g.fillRect(2, y, W - 4, lh);
        g.fillStyle = `rgba(63,185,80,${0.9 * settle})`; g.fillRect(2, y, 4, lh);
        if (r.typed > 0 && r.typed < 1) this.focusPx = y;
      }
      if (f.kind === "run" && r.h > 0) this.focusPx = y;
      if (f.kind !== "run") {
        g.fillStyle = C.line; g.textAlign = "right"; g.fillText(r.n, PX.gutter + PX.pad - 18, cy + 1); g.textAlign = "left";
        if (r.op !== " ") { g.fillStyle = r.op === "+" ? C.add : C.del; g.fillText(r.op, gx, cy + 1); }
      }
      if (f.kind === "run") this.drawRun(f.lines[r.i][1], codeX, cy, cw, font);
      else {
        // typed text: draw tokens up to the typed character count, then a caret
        const total = f.lines[r.i][1].length, upto = Math.round(r.typed * total);
        let x = codeX, n = 0;
        for (const [t, col] of this.toks[r.i]) {
          if (n >= upto) break;
          const part = t.slice(0, upto - n);
          g.fillStyle = r.op === "-" ? mix(col, "#f85149", 0.35 * smooth(0, 0.16, k)) : col;
          g.fillText(part, x, cy + 1);
          x += part.length * cw; n += t.length;
        }
        if (r.typed > 0 && r.typed < 1) { g.fillStyle = this.accent; g.fillRect(x + 1, cy - PX.font * 0.6, Math.max(3, cw * 0.55), PX.font * 1.2); }
      }
      g.restore();
      y += lh;
    }
    // the agent reading: a scan bar down the file
    if (f.kind === "read" && k > 0 && k < 1) {
      const sy = PX.head + PX.pad + k * bodyH;
      const grd = g.createLinearGradient(0, sy - 90, 0, sy + 6);
      grd.addColorStop(0, `rgba(${hexRgb(C.fn)},0)`); grd.addColorStop(1, `rgba(${hexRgb(C.fn)},0.22)`);
      g.fillStyle = grd; g.fillRect(2, Math.max(PX.head, sy - 90), W - 4, Math.min(96, sy - PX.head + 6));
      g.fillStyle = `rgba(${hexRgb(C.fn)},0.85)`; g.fillRect(2, sy, W - 4, 2);
    }
    this.tex.needsUpdate = true;
  }

  drawRun(t: string, x: number, cy: number, cw: number, font: (w?: number) => string) {
    const g = this.g;
    const m = /^(\s*)(PASS|FAIL)(\s+)(.*)$/.exec(t);
    if (m) {
      const lx = x + m[1].length * cw, ok = m[2] === "PASS";
      roundRect(g, lx - 6, cy - 15, cw * 4 + 12, 30, 5); g.fillStyle = ok ? C.add : C.del; g.fill();
      g.font = font(700); g.fillStyle = "#0b0d0f"; g.fillText(m[2], lx, cy + 1);
      g.font = font(600); g.fillStyle = "#eceef1"; g.fillText(m[4], lx + (4 + m[3].length) * cw + 6, cy + 1);
      g.font = font(400); return;
    }
    const ck = /^(\s*)(✓|✔|✗|×)(.*)$/.exec(t);
    if (ck) {
      g.fillStyle = ck[2] === "✓" || ck[2] === "✔" ? C.add : C.del; g.fillText(ck[2], x + ck[1].length * cw, cy + 1);
      const rest = ck[3], tm = /(\s+)([\d.]+s)\s*$/.exec(rest);
      g.fillStyle = "#b9bec6"; g.fillText(tm ? rest.slice(0, tm.index) : rest, x + (ck[1].length + 1) * cw, cy + 1);
      if (tm) { g.fillStyle = C.dim; g.textAlign = "right"; g.fillText(tm[2], this.wpx - PX.pad, cy + 1); g.textAlign = "left"; }
      return;
    }
    const tests = /^(\s*Tests:\s*)(.*)$/.exec(t);
    if (tests) {
      g.font = font(700); g.fillStyle = "#eceef1"; g.fillText(tests[1], x, cy + 1);
      g.fillStyle = C.add; g.fillText(tests[2], x + tests[1].length * cw, cy + 1); g.font = font(400); return;
    }
    g.fillStyle = t.trim().startsWith("$") ? "#eceef1" : "#9aa1aa"; g.fillText(t, x, cy + 1);
  }
}

function hexRgb(h: string) {
  const v = h.replace("#", ""), n = parseInt(v.length === 3 ? v.replace(/./g, (c) => c + c) : v, 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}
function mix(a: string, b: string, t: number) {
  const pa = hexRgb(a).split(",").map(Number), pb = hexRgb(b).split(",").map(Number);
  return `rgb(${pa.map((v, i) => Math.round(v + (pb[i] - v) * t)).join(",")})`;
}

// ---------------------------------------------------------------- the opening terminal
// One window, centred: a slim title bar (the project's name on the left, the model on the right), then a prompt line
// where the task types itself after a `›` in the page's accent, and an optional quiet line of hints under it.

function drawTerminal(g: CanvasRenderingContext2D, W: number, H: number, t: Term, typed: number, sent: number, mono: string, accent2: string) {
  const u = MOB ? Math.min(W / 640, H / 700) : Math.min(W / 1600, H / 900);
  g.fillStyle = "#0b0c0e"; g.fillRect(0, 0, W, H);
  g.textBaseline = "middle";
  const cx = W / 2, cy = H * (MOB ? 0.6 : 0.42);
  const bw = Math.min(W * 0.88, 1040 * u), bar = 54 * u, body = 150 * u, bh = bar + body, bx = cx - bw / 2, by = cy - bh / 2;
  const r = 16 * u;
  // the window, with a soft glow of the accent under it
  g.save(); g.shadowColor = `rgba(${hexRgb(accent2)},0.18)`; g.shadowBlur = 80 * u; g.shadowOffsetY = 24 * u;
  roundRect(g, bx, by, bw, bh, r); g.fillStyle = "#15171a"; g.fill(); g.restore();
  roundRect(g, bx, by, bw, bh, r); g.strokeStyle = "rgba(255,255,255,0.08)"; g.lineWidth = Math.max(1, u); g.stroke();
  g.fillStyle = "rgba(255,255,255,0.05)"; g.fillRect(bx + 1, by + bar, bw - 2, Math.max(1, u));
  // title bar: name left, model right
  const small = Math.round(19 * u);
  g.font = `600 ${small}px "${mono}", monospace`;
  g.fillStyle = "#c9ccd1"; g.fillText(t.logo.replace("|", ""), bx + 28 * u, by + bar / 2);
  const tag = [t.agent, t.model, t.provider].filter(Boolean).join(" · ");
  if (tag) { g.textAlign = "right"; g.font = `400 ${small}px "${mono}", monospace`; g.fillStyle = "#7b8089";
    g.fillText(tag, bx + bw - 28 * u, by + bar / 2); g.textAlign = "left"; }
  // the prompt line
  const fs = Math.round(30 * u), ly = by + bar + body / 2, px = bx + 28 * u;
  g.font = `600 ${fs}px "${mono}", monospace`; g.fillStyle = accent2; g.fillText("›", px, ly);
  const tx = px + g.measureText("›  ").width;
  g.font = `400 ${fs}px "${mono}", monospace`;
  const full = t.prompt, n = Math.round(typed * full.length);
  let shown = full.slice(0, n);
  const maxW = bx + bw - 40 * u - tx;
  while (g.measureText(shown).width > maxW && shown.length > 4) shown = "…" + shown.slice(shown.length - Math.floor(shown.length * 0.9));
  g.fillStyle = "#eceef1"; g.fillText(shown, tx, ly);
  if (typed < 1 && (n > 0 || Math.floor(performance.now() / 500) % 2 === 0)) {
    g.fillStyle = accent2; g.fillRect(tx + g.measureText(shown).width + 4 * u, ly - 16 * u, 3 * u, 32 * u);
  }
  // hints, quiet, under the window (only when the spec gives some)
  if (t.hints.length) {
    g.font = `400 ${small}px "${mono}", monospace`; g.fillStyle = "#6b7079"; g.textAlign = "center";
    g.fillText(t.hints.join("   ·   "), cx, by + bh + 40 * u); g.textAlign = "left";
  }
  // the task is sent: a sweep of the accent across the prompt line
  if (sent > 0 && sent < 1) { g.fillStyle = `rgba(${hexRgb(accent2)},${0.3 * (1 - sent)})`; g.fillRect(bx, by + bar, bw * sent, body); }
}

// ---------------------------------------------------------------- the player
const factory: PlayerFactory = async (cfg, ctx) => {
  const files: CFile[] = cfg.files;
  const term: Term | null = cfg.terminal;
  const tAt: [number, number] | null = cfg.terminalAt;
  const oAt: [number, number] = cfg.outroAt;
  const mono: string = cfg.mono || "JetBrains Mono";
  const accent = cfg.colors?.accent || cssVar("--accent") || "#fab283";
  const accent2 = cfg.colors?.accent2 || "#5c9cf5";
  const bgHex = cfg.colors?.bg || cssVar("--bg") || "#0a0a0b";
  try { await Promise.race([document.fonts.load(`400 20px "${mono}"`), new Promise((r) => setTimeout(r, 2500))]); } catch { /* fallback face */ }
  ctx.progress(0.3);

  const canvas = document.createElement("canvas");
  ctx.visual.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.5));
  const bg = new THREE.Color(bgHex);
  renderer.setClearColor(bg, 1);
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(bg.getHex(), 18, 70);
  const FOV = MOB ? 52 : 40;
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.05, 400);
  const aniso = renderer.capabilities.getMaxAnisotropy();
  let composer: EffectComposer | null = null, bloom: UnrealBloomPass | null = null;
  if (!MOB) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.55, 0.5, 0.9);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());
  }

  // ---- the route: each file gets a pane pose; the camera visits them in order
  const rand = rng(23);
  const panes = files.map((f) => new Pane(f, mono, accent, aniso));
  const cur = new THREE.Vector3(0, 0, -6);
  let yaw = 0, readSide = 1;
  const poses = panes.map((p, i) => {
    const f = p.f, read = f.kind === "read";
    yaw += read ? (rand() - 0.5) * 0.35 : (i % 2 ? 0.55 : -0.55);
    const dir = new THREE.Vector3(Math.sin(yaw), 0, -Math.cos(yaw));
    const right = new THREE.Vector3(Math.cos(yaw), 0, Math.sin(yaw));
    cur.addScaledVector(dir, read ? 9 : 26);
    cur.y += read ? (rand() - 0.5) * 1.6 : (rand() - 0.5) * 3;
    const pos = cur.clone();
    let normal = dir.clone().negate();
    if (read) {
      readSide = -readSide;
      pos.addScaledVector(right, readSide * (p.w * 0.42));
      normal = normal.applyAxisAngle(new THREE.Vector3(0, 1, 0), -readSide * 0.75);   // angled into the corridor
    }
    p.mesh.position.copy(pos);
    p.mesh.lookAt(pos.clone().add(normal));
    scene.add(p.mesh);
    // the camera's right when it faces this pane
    return { pos, normal, right: new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), normal).normalize() };
  });

  // ---- the codebase around the route: the rest of the tree, as dim silhouettes of files
  const tree: string[] = cfg.tree?.length ? cfg.tree : files.map((f) => f.path);
  const nBg = MOB ? 22 : 64;
  const bgPanes: THREE.Mesh[] = [];
  const box = new THREE.Box3(); poses.forEach((p) => box.expandByPoint(p.pos));
  box.expandByScalar(9);
  for (let i = 0; i < nBg; i++) {
    const c = document.createElement("canvas"); c.width = 512; c.height = 360;
    const g = c.getContext("2d")!;
    roundRect(g, 1, 1, 510, 358, 14); g.fillStyle = "rgba(20,21,24,0.85)"; g.fill();
    g.strokeStyle = "rgba(255,255,255,0.08)"; g.lineWidth = 2; g.stroke();
    g.font = `500 17px "${mono}", monospace`; g.fillStyle = "#8b929b"; g.textBaseline = "middle";
    g.fillText(tree[i % tree.length].slice(-44), 18, 26);
    const r2 = rng(i * 7 + 3);
    for (let l = 0; l < 13; l++) {
      let x = 18 + Math.floor(r2() * 4) * 22;
      const y = 62 + l * 22;
      const segs = 1 + Math.floor(r2() * 4);
      for (let s = 0; s < segs && x < 480; s++) {
        const w = 20 + r2() * 110;
        g.fillStyle = [C.kw, C.fn, C.str, C.text, C.type][Math.floor(r2() * 5)];
        g.globalAlpha = 0.5; g.fillRect(x, y - 4, Math.min(w, 494 - x), 8); g.globalAlpha = 1;
        x += w + 12;
      }
    }
    const tx = new THREE.CanvasTexture(c); tx.colorSpace = THREE.SRGBColorSpace;
    const m = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 2.25), new THREE.MeshBasicMaterial({ map: tx, transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide }));
    // keep clear of the route's own panes
    let pos = new THREE.Vector3();
    for (let tries = 0; tries < 12; tries++) {
      pos.set(lerp(box.min.x, box.max.x, rand()), lerp(box.min.y - 4, box.max.y + 4, rand()), lerp(box.min.z, box.max.z, rand()));
      if (poses.every((p) => p.pos.distanceTo(pos) > 6.5)) break;
    }
    m.position.copy(pos);
    m.rotation.set((rand() - 0.5) * 0.3, rand() * Math.PI * 2, (rand() - 0.5) * 0.15);
    scene.add(m); bgPanes.push(m);
  }

  // ---- dust: drifting specks for depth
  const nDust = MOB ? 700 : 2200;
  const dpos = new Float32Array(nDust * 3);
  for (let i = 0; i < nDust; i++) {
    dpos[i * 3] = lerp(box.min.x - 10, box.max.x + 10, rand());
    dpos[i * 3 + 1] = lerp(box.min.y - 10, box.max.y + 10, rand());
    dpos[i * 3 + 2] = lerp(box.min.z - 10, box.max.z + 14, rand());
  }
  const dgeo = new THREE.BufferGeometry(); dgeo.setAttribute("position", new THREE.BufferAttribute(dpos, 3));
  const dust = new THREE.Points(dgeo, new THREE.PointsMaterial({ color: new THREE.Color(accent).lerp(new THREE.Color("#ffffff"), 0.5), size: 0.05, transparent: true, opacity: 0.5, depthWrite: false }));
  scene.add(dust);

  // ---- the trace: a glowing line threading every file on the route, drawn as you go
  const anchors = poses.map((p, i) => p.pos.clone().add(new THREE.Vector3(0, -panes[i].h / 2 - 0.35, 0)));
  anchors.unshift(new THREE.Vector3(0, -1.5, 0));
  const curve = new THREE.CatmullRomCurve3(anchors, false, "centripetal");
  const TSEG = anchors.length * 40;
  const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, TSEG, MOB ? 0.035 : 0.025, 6, false),
    new THREE.MeshBasicMaterial({ color: new THREE.Color(accent).multiplyScalar(MOB ? 1 : 2.2), transparent: true, opacity: 0.9, fog: false }));
  scene.add(tube);
  const tubeCount = (tube.geometry.index as THREE.BufferAttribute).count;

  // ---- the terminal plane, filling the view at the start
  const TD = 10;
  const tcan = document.createElement("canvas"), tg = tcan.getContext("2d")!;
  const ttex = new THREE.CanvasTexture(tcan); ttex.colorSpace = THREE.SRGBColorSpace;
  const tmat = new THREE.MeshBasicMaterial({ map: ttex, transparent: true, depthWrite: false, fog: false });
  const tmesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), tmat);
  tmesh.renderOrder = 10;
  if (term) scene.add(tmesh);
  let termKey = "";

  // ---- todo list overlay (from files with todo:)
  const todos = files.map((f, i) => ({ f, i })).filter((x) => x.f.todo);
  const hudEl = document.createElement("div");
  hudEl.className = "ss-code-todo"; hudEl.setAttribute("aria-hidden", "true");
  hudEl.innerHTML = `<span class="ss-code-todo__h">Todo <b data-n>0/${todos.length}</b></span>` +
    todos.map((t) => `<div class="ss-code-todo__i"><b>[ ]</b><span>${t.f.todo}</span></div>`).join("") +
    `<span class="ss-code-todo__r">${term ? `${term.agent ? `<i>${term.agent}</i> ` : ""}${term.model}` : ""}</span>`;
  const style = document.createElement("style");
  style.textContent = `
  /* the status line along the bottom: todo count, the item in progress, and the agent and model when set */
  .ss-code-todo { position: absolute; left: 0; right: 0; bottom: 0; height: 38px; display: flex; align-items: center; gap: 18px;
    padding: 0 var(--gutter, 24px); font: 500 12.5px/1 "${mono}", ui-monospace, monospace; color: #8b929b; z-index: 4;
    background: rgba(10,10,11,.86); border-top: 1px solid rgba(255,255,255,.07); opacity: 0; transition: opacity .4s; pointer-events: none; }
  .ss-code-todo.on { opacity: 1; }
  .ss-code-todo__h { color: #eceef1; font-weight: 700; white-space: nowrap; } .ss-code-todo__h b { color: ${accent}; font-weight: 700; }
  .ss-code-todo__i { display: none; gap: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; flex: 1; }
  .ss-code-todo__i.now, .ss-code-todo__i.last { display: flex; }
  .ss-code-todo__i b { font-weight: 500; white-space: pre; }
  .ss-code-todo__i.now { color: #eceef1; } .ss-code-todo__i.now b { color: ${accent}; }
  .ss-code-todo__i.done b { color: ${C.add}; }
  .ss-code-todo__r { margin-left: auto; white-space: nowrap; color: #eceef1; } .ss-code-todo__r i { font-style: normal; color: ${accent2}; margin-right: 6px; }
  /* captions over the opening terminal sit low, under the prompt box */
  .ss-code-low.ss-caption { top: auto; bottom: calc(170px - 36vh); transform: none; }
  .ss-code-low .ss-body { max-width: 34ch; }
  @media (max-width: 760px) { .ss-code-todo { font-size: 11px; gap: 10px; } .ss-code-todo__r { display: none; }
    .ss-code-low.ss-caption { top: 50%; bottom: auto; transform: translateY(-50%); } }`;
  ctx.visual.appendChild(style);
  if (todos.length) ctx.visual.appendChild(hudEl);
  const todoEls = [...hudEl.querySelectorAll<HTMLElement>(".ss-code-todo__i")];
  const todoN = hudEl.querySelector<HTMLElement>("[data-n]")!;
  if (tAt) ctx.section.querySelectorAll<HTMLElement>(".ss-caption").forEach((c) => {
    if (+(c.dataset.to || 1) <= tAt[1] + 1e-4) c.classList.add("ss-code-low");
  });

  // ---- camera framing for a pane
  let W = 1, H = 1;
  const tanH = () => Math.tan(THREE.MathUtils.degToRad(FOV / 2));
  function frameFor(i: number, k: number) {
    const p = poses[i], pane = panes[i], read = pane.f.kind === "read";
    const aspect = W / H, t = tanH();
    // distance for a steady text size, pulled back if the pane would not fit beside the captions (desktop) or
    // across the screen (phones)
    const dText = (900 * S) / (2 * t * (read ? TEXT_SCALE * 0.8 : TEXT_SCALE));
    const dFit = pane.w / (2 * t * aspect * (MOB ? 0.96 : 0.6));
    const d = Math.max(4, dText, dFit);
    const viewW = 2 * d * t * aspect, viewH = 2 * d * t;
    const frac = pane.w / viewW;
    const up = new THREE.Vector3(0, 1, 0);
    let offUp = 0;
    if (pane.h > viewH * 0.82) {
      // a tall file: follow the line being worked on
      const focus = pane.h / 2 - pane.focusPx * S;
      const lim = pane.h / 2 - viewH * 0.42;
      offUp = clamp(focus - viewH * 0.08, -lim, lim);
    }
    const target = p.pos.clone().addScaledVector(up, offUp);
    // desktop: the pane's right edge near the screen's, clear of the captions on the left; phones: below the captions
    if (!MOB) target.addScaledVector(p.right, -viewW * (0.965 - frac / 2 - 0.5));
    else target.addScaledVector(up, viewH * 0.14);
    const pos = target.clone().addScaledVector(p.normal, d * (1 - 0.04 * k));
    return { pos, target };
  }
  const startPose = () => ({ pos: new THREE.Vector3(0, 0, TD), target: new THREE.Vector3(0, 0, 0) });
  function overview() {
    const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
    const r = Math.max(size.x, size.z) * 0.48;
    return { pos: c.clone().add(new THREE.Vector3(r * 0.35, r * 0.75, r * 0.95)), target: c };
  }
  const bez = (a: THREE.Vector3, m: THREE.Vector3, b: THREE.Vector3, t: number) =>
    a.clone().multiplyScalar((1 - t) ** 2).addScaledVector(m, 2 * (1 - t) * t).addScaledVector(b, t * t);

  function resize() {
    W = ctx.visual.clientWidth || 1; H = ctx.visual.clientHeight || 1;
    renderer.setSize(W, H, false); composer?.setSize(W, H); bloom?.resolution.set(W, H);
    camera.aspect = W / H; camera.updateProjectionMatrix();
    // the terminal fills the view exactly at its distance
    const th = 2 * TD * tanH(), tw = th * camera.aspect;
    tmesh.scale.set(tw, th, 1);
    const dpr = Math.min(devicePixelRatio || 1, 2);
    tcan.width = Math.round(W * dpr); tcan.height = Math.round(H * dpr); termKey = "";
  }
  resize();

  // the first frame
  panes.forEach((p) => p.draw(0));
  // do every first-time GPU job now, behind the loader: upload each texture and compile the shaders, then draw one
  // frame from the overview so nothing hitches the first time it comes into view mid-scroll
  panes.forEach((p) => renderer.initTexture(p.tex));
  bgPanes.forEach((m) => renderer.initTexture((m.material as THREE.MeshBasicMaterial).map!));
  renderer.compile(scene, camera);
  {
    const o = overview();
    camera.position.copy(o.pos); camera.lookAt(o.target);
    if (composer) composer.render(); else renderer.render(scene, camera);
    camera.position.set(0, 0, TD); camera.lookAt(0, 0, 0);
  }
  ctx.progress(1);

  const cam = { pos: new THREE.Vector3(0, 0, TD), target: new THREE.Vector3() };
  return {
    resize,
    update(s) {
      const p = s.p;
      let pose = startPose(), roll = 0;

      // which beat are we in?
      if (tAt && p < tAt[1]) {
        const u = (p - tAt[0]) / (tAt[1] - tAt[0]);
        const typed = clamp(u / 0.42), sent = smooth(0.44, 0.54, u), dive = easeInOut(clamp((u - 0.5) / 0.5));
        const key = `${typed.toFixed(3)}|${sent.toFixed(2)}|${Math.floor(performance.now() / 500) % 2}`;
        if (term && key !== termKey) { termKey = key; drawTerminal(tg, tcan.width, tcan.height, term, typed, sent, mono, accent2); ttex.needsUpdate = true; }
        if (dive > 0) {
          const a = startPose(), b = frameFor(0, 0);
          pose = { pos: bez(a.pos, new THREE.Vector3(0, 0.3, -3), b.pos, dive), target: a.target.clone().lerp(b.target, smooth(0.3, 1, dive)).add(new THREE.Vector3(0, 0, -6 * (1 - dive) * smooth(0, 0.3, dive))) };
          roll = Math.sin(dive * Math.PI) * 0.06;
        }
      } else if (p >= oAt[0]) {
        const u = easeInOut(clamp((p - oAt[0]) / (oAt[1] - oAt[0])));
        const a = frameFor(files.length - 1, 1), b = overview();
        pose = { pos: a.pos.clone().lerp(b.pos, u), target: a.target.clone().lerp(b.target, u) };
      } else {
        let i = files.findIndex((f) => p >= f.at[0] && p < f.at[1]);
        if (i < 0) i = files.length - 1;
        const f = files[i], u = clamp((p - f.at[0]) / (f.at[1] - f.at[0]));
        const tr = f.kind === "read" ? 0.42 : 0.28;
        const k = clamp((u - tr) / (1 - tr));
        const here = frameFor(i, k);
        if (u < tr) {
          const prev = i > 0 ? frameFor(i - 1, 1) : here;
          const t = easeInOut(u / tr);
          const mid = prev.pos.clone().lerp(here.pos, 0.5).add(new THREE.Vector3(0, 1.4, 0)).addScaledVector(poses[i].normal, 2.5);
          pose = { pos: bez(prev.pos, mid, here.pos, t), target: prev.target.clone().lerp(here.target, smooth(0, 1, t)) };
          roll = Math.sin(t * Math.PI) * (i % 2 ? 0.05 : -0.05);
        } else pose = here;
      }

      // the panes' own beats
      panes.forEach((pane, i) => {
        const f = files[i], u = clamp((p - f.at[0]) / (f.at[1] - f.at[0]));
        const tr = f.kind === "read" ? 0.42 : 0.28;
        const k = p >= f.at[1] ? 1 : clamp((u - tr * 0.6) / (1 - tr * 0.6));
        const on = p >= f.at[0] - 0.02 && p < f.at[1] + 0.02;
        const target = f.kind === "read" ? (on ? 0.6 : 0) : (on ? 1 : p >= f.at[1] ? 0.55 : 0);
        pane.glow += (target - pane.glow) * 0.12;
        pane.draw(f.kind === "read" ? (on ? k : p >= f.at[1] ? 1 : 0) : k);
        // panes ahead fade in from the fog; the one in focus is fully opaque
        pane.base = p >= f.at[0] - 0.12 || p >= oAt[0] ? 1 : 0.55;
      });

      // camera, with a little pointer parallax
      cam.pos.copy(pose.pos); cam.target.copy(pose.target);
      camera.position.copy(cam.pos).add(new THREE.Vector3(s.mx * 0.25, -s.my * 0.18, 0));
      camera.up.set(Math.sin(roll), Math.cos(roll), 0);
      camera.lookAt(cam.target);

      // a pane the camera is about to fly through fades, so it never blocks the one in focus
      const active = files.findIndex((f) => p >= f.at[0] && p < f.at[1]);
      const local = new THREE.Vector3();
      panes.forEach((pane, i) => {
        let fade = 1;
        if (i !== active) {
          pane.mesh.worldToLocal(local.copy(camera.position));
          if (Math.abs(local.x) < pane.w / 2 + 2 && Math.abs(local.y) < pane.h / 2 + 2) fade = smooth(0.8, 6, Math.abs(local.z));
        }
        pane.mat.opacity = pane.base * fade;
        pane.mesh.visible = pane.mat.opacity > 0.01;
      });

      // terminal: opaque until the camera reaches it, gone once through
      if (term) {
        const z = camera.position.z;
        tmat.opacity = tAt && p < tAt[1] ? clamp((z - 0.4) / 2.2) : 0;
        tmesh.visible = tmat.opacity > 0.003;
      }
      // the trace grows with the route
      const routeK = tAt ? clamp((p - tAt[1] * 0.85) / (oAt[0] - tAt[1] * 0.85)) : clamp(p / oAt[0]);
      tube.geometry.setDrawRange(0, Math.floor(tubeCount * routeK / 6) * 6);
      // todo list
      const show = (!tAt || p > tAt[1]) && p < oAt[1] - 0.01;
      hudEl.classList.toggle("on", show);
      let nDone = 0, anyNow = false;
      todos.forEach((t, j) => {
        const f = t.f, done = p >= f.at[0] + (f.at[1] - f.at[0]) * 0.92, now = !done && p >= f.at[0];
        const el = todoEls[j];
        el.classList.toggle("done", done); el.classList.toggle("now", now);
        el.firstElementChild!.textContent = done ? "[✓]" : now ? "[•]" : "[ ]";
        nDone += done ? 1 : 0; anyNow = anyNow || now;
      });
      // between items, the bar shows the last one finished
      todoEls.forEach((el, j) => el.classList.toggle("last", !anyNow && j === Math.max(0, nDone - 1)));
      todoN.textContent = `${nDone}/${todos.length}`;

      dust.rotation.y = s.t * 0.004;
      bgPanes.forEach((m, i) => { m.rotation.y += 0.0006 * (i % 2 ? 1 : -1); });
      if (composer) composer.render(); else renderer.render(scene, camera);
    },
  };
};
export default factory;
