/**
 * Isometric: flying a fixed-angle drone across a tiny model world that builds itself as you arrive. The whole page is
 * one map: every section is a district on a chain of floating plots joined by roads. The camera never tilts or zooms
 * in perspective; scrolling glides it along the grid axes, at constant speed with a small mechanical settle, from
 * district to district (and from building to building inside one). As a district comes into view its slab drops in
 * chunk by chunk, buildings extrude, props pop. Features are buildings (the active one lights, the rest desaturate),
 * stats are extruded towers with flat labels, the product is an exploded stack of layers beside a standing screen, the
 * steps are stations on a road a token drives along, the quote is a tiny person with a speech bubble, and the last
 * district zooms out over the finished world to a keycap button. All copy stays on the flat HUD plane, pinned to the
 * world by leader lines; a minimap shows where you are. Reduced motion: no flights, the world is built, the camera
 * cuts to each district.
 */
import { $, $$, onFrame, reduced } from "./_kit";

const NS = "http://www.w3.org/2000/svg";
const TW = 32, TH = 16, ZH = 36;
type Pal = [string, string, string];
const PAL: Record<string, Pal> = {
  white: ["#ffffff", "#dce3ec", "#b3c3d6"], accent: ["#ff8a65", "#f4643f", "#d24a28"], teal: ["#7fe0d6", "#2ec4b6", "#21998e"],
  ground: ["#f3ebdd", "#dcc9a8", "#c4ad86"], road: ["#aab7c7", "#8e9caf", "#77869b"], tree: ["#9fd69e", "#78bb77", "#5b9c5e"],
  ink: ["#4a5a70", "#34445a", "#1d2b3a"], yellow: ["#ffd98a", "#f5bd52", "#d99d2c"], glass: ["#e3f4fb", "#bfe0ef", "#9cc8de"], trunk: ["#c9a27a", "#a8835e", "#8a6a4b"],
};
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const proj = (x: number, y: number, z: number): [number, number] => [(x - y) * TW, (x + y) * TH - z * ZH];
const backOut = (t: number) => { const c = 1.4; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
/** constant speed, then a small mechanical overshoot and settle */
const glide = (t: number) => (t < 0.86 ? t / 0.86 : 1 + 0.018 * Math.sin((Math.PI * (t - 0.86)) / 0.14));

class Box {
  g: SVGGElement; t: SVGPolygonElement; l: SVGPolygonElement; r: SVGPolygonElement;
  ext = 1; drop = 1; lift = 0; key = ""; name = ""; sec = -1; stop = -1;
  constructor(public x: number, public y: number, public w: number, public d: number, public h: number, public z0: number, pal: Pal, public delay = 0, cls = "") {
    this.g = document.createElementNS(NS, "g") as SVGGElement;
    this.g.setAttribute("class", "iso-b " + cls);
    const mk = (c: string, fill: string) => { const p = document.createElementNS(NS, "polygon") as SVGPolygonElement; p.setAttribute("class", c); p.setAttribute("fill", fill); this.g.appendChild(p); return p; };
    this.l = mk("l", pal[1]); this.r = mk("r", pal[2]); this.t = mk("t", pal[0]);
    this.draw();
  }
  get depth() { return this.x + this.w / 2 + this.y + this.d / 2 + this.z0 * 0.01; }
  draw() {
    const H = Math.max(0.001, this.h * this.ext), z = this.z0, x = this.x, y = this.y, w = this.w, d = this.d;
    const key = H.toFixed(3);
    if (key !== this.key) {
      this.key = key;
      const pts = (a: [number, number, number][]) => a.map(([px, py, pz]) => proj(px, py, pz).map((v) => v.toFixed(1)).join(",")).join(" ");
      this.t.setAttribute("points", pts([[x, y, z + H], [x + w, y, z + H], [x + w, y + d, z + H], [x, y + d, z + H]]));
      this.l.setAttribute("points", pts([[x, y + d, z], [x + w, y + d, z], [x + w, y + d, z + H], [x, y + d, z + H]]));
      this.r.setAttribute("points", pts([[x + w, y, z], [x + w, y + d, z], [x + w, y + d, z + H], [x + w, y, z + H]]));
    }
    const dy = -(1 - this.drop) * 7 * ZH - this.lift;
    this.g.setAttribute("transform", dy ? `translate(0 ${dy.toFixed(1)})` : "");
    this.g.style.visibility = this.drop <= 0 || this.ext <= 0.001 ? "hidden" : "";
  }
}

interface Sec {
  el: HTMLElement; kind: string; hud: HTMLElement | null; top: number; len: number; glideFrac: number;
  items: HTMLElement[]; labels: HTMLElement[]; screen: HTMLElement | null; d: District; name: string;
}
interface District {
  i: number; cx: number; cy: number; g: SVGGElement; chunks: Box[]; blds: Box[]; props: Box[]; anchors: Record<string, [number, number, number]>;
  stops: [number, number, number][]; build: number; feat: Box[][]; stack: Box[]; towers: Box[]; tokenG?: SVGGElement; route?: [number, number][];
  stations?: Box[]; device?: Box; extras: SVGElement[];
}

export default function start() {
  const secEls = $$<HTMLElement>("main section.iso-sec");
  if (!secEls.length) return;
  const root = document.documentElement;
  root.classList.add("iso-live");

  const world = document.createElementNS(NS, "svg") as SVGSVGElement;
  world.setAttribute("class", "iso-world"); world.setAttribute("aria-hidden", "true");
  const cam = document.createElementNS(NS, "g") as SVGGElement;
  world.appendChild(cam);
  const lead = document.createElementNS(NS, "svg") as SVGSVGElement;
  lead.setAttribute("class", "iso-leaders"); lead.setAttribute("aria-hidden", "true");
  document.body.prepend(world);
  document.body.appendChild(lead);
  const label = document.createElement("div"); label.className = "iso-label"; label.setAttribute("aria-hidden", "true"); document.body.appendChild(label);
  const screens = document.createElement("div"); screens.className = "iso-screens"; document.body.appendChild(screens);

  // ------------------------------------------------------------ build the world, one district per section
  const bridges = document.createElementNS(NS, "g") as SVGGElement; cam.appendChild(bridges);
  const secs: Sec[] = secEls.map((el, i) => {
    const kind = el.dataset.iso || "intro";
    const cx = i * 22, cy = i % 2 ? 5 : -5;
    const g = document.createElementNS(NS, "g") as SVGGElement;
    cam.appendChild(g);
    const d: District = { i, cx, cy, g, chunks: [], blds: [], props: [], anchors: {}, stops: [[cx, cy, 0]], build: -1, feat: [], stack: [], towers: [], extras: [] };
    const items = $$<HTMLElement>(".iso-list > li", el);
    const labels = [...$$<HTMLElement>(".iso-stat", el), ...$$<HTMLElement>(".iso-layers li", el)];
    const screen = el.querySelector<HTMLElement>("[data-screen]");
    if (screen) screens.appendChild(screen);
    const hud = el.querySelector<HTMLElement>(".iso-hud");
    const sec: Sec = { el, kind, hud, top: 0, len: 1, glideFrac: 0, items, labels, screen, d, name: el.dataset.name || kind };
    buildDistrict(sec);
    return sec;
  });
  // roads between plots: along x, then along y (grid axes only), as raised bridges between the islands
  secs.forEach((s, i) => {
    if (!i) return;
    const a = secs[i - 1].d, b = s.d;
    const bx = new Box(a.cx + 7, a.cy - 0.8, b.cx - a.cx - 7, 1.6, 0.25, -0.25, PAL.road, 0, "bridge");
    bridges.appendChild(bx.g);
    if (a.cy !== b.cy) {
      const y0 = Math.min(a.cy, b.cy) - 0.8, y1 = Math.max(a.cy, b.cy) + 0.8;
      const by = new Box(b.cx - 0.8, y0, 1.6, y1 - y0, 0.25, -0.25, PAL.road, 0, "bridge");
      bridges.appendChild(by.g);
    }
  });

  function buildDistrict(s: Sec) {
    const d = s.d, { cx, cy } = d, i = d.i;
    const all: Box[] = [];
    const B = (x: number, y: number, w: number, dd: number, h: number, pal: Pal, z0 = 0, cls = "") => { const b = new Box(cx + x, cy + y, w, dd, h, z0, pal, 0, cls); all.push(b); return b; };
    // the slab: 3 x 3 chunks that drop in from the centre outwards, with a soil edge
    for (let a = 0; a < 3; a++) for (let c = 0; c < 3; c++) {
      const ch = new Box(cx - 7 + a * (14 / 3), cy - 7 + c * (14 / 3), 14 / 3, 14 / 3, 1.4, -1.4, PAL.ground, (Math.abs(a - 1) + Math.abs(c - 1)) * 0.07 + (a + c) * 0.01, "chunk");
      // grid lines on the chunk's top
      const gl = document.createElementNS(NS, "path");
      let p = "";
      for (let k = 1; k < 4; k++) {
        const t = k * (14 / 3) / 4;
        const [x1, y1] = proj(ch.x + t, ch.y, 0), [x2, y2] = proj(ch.x + t, ch.y + ch.d, 0);
        const [x3, y3] = proj(ch.x, ch.y + t, 0), [x4, y4] = proj(ch.x + ch.w, ch.y + t, 0);
        p += `M${x1} ${y1}L${x2} ${y2}M${x3} ${y3}L${x4} ${y4}`;
      }
      gl.setAttribute("d", p); gl.setAttribute("stroke", "rgba(29,43,58,.09)"); gl.setAttribute("fill", "none");
      ch.g.appendChild(gl);
      d.chunks.push(ch);
    }
    const tree = (x: number, y: number, s2 = 1) => { const t1 = B(x, y, 0.3, 0.3, 0.5 * s2, PAL.trunk, 0, "prop"); const t2 = B(x - 0.35, y - 0.35, 1, 1, 0.9 * s2, PAL.tree, 0.5 * s2, "prop"); d.props.push(t1, t2); };
    const person = (x: number, y: number, pal = PAL.ink) => { const b1 = B(x, y, 0.4, 0.4, 0.7, pal, 0, "prop"); const b2 = B(x + 0.05, y + 0.05, 0.3, 0.3, 0.3, PAL.yellow, 0.7, "prop"); d.props.push(b1, b2); return [cx + x + 0.2, cy + y + 0.2, 1.1] as [number, number, number]; };
    const bld = (b: Box, name = "") => { b.name = name; b.sec = i; d.blds.push(b); b.g.classList.add("iso-hit"); return b; };
    const road = (pts: [number, number][]) => {
      for (let k = 1; k < pts.length; k++) {
        const [x0, y0] = pts[k - 1], [x1, y1] = pts[k];
        const rx = Math.min(x0, x1) - 0.6, ry = Math.min(y0, y1) - 0.6;
        const rb = B(rx, ry, Math.abs(x1 - x0) + 1.2, Math.abs(y1 - y0) + 1.2, 0.06, PAL.road, 0, "road");
        d.props.push(rb);
      }
    };
    const n = s.items.length || s.labels.length;
    switch (s.kind) {
      case "hero": {
        const dev = bld(B(-1.2, -0.4, 3, 0.8, 5.6, PAL.white), "the app");
        d.device = dev;
        bld(B(-5, -5, 2.2, 2.2, 1.6, PAL.white), ""); bld(B(-5, -2, 2.2, 1.6, 1, PAL.accent), "");
        bld(B(3, -5.5, 2.4, 2, 2.4, PAL.white), ""); bld(B(3.4, -5.1, 1.6, 1.2, 0.6, PAL.teal, 2.4), "");
        tree(-5.5, 3.5); tree(-3.6, 4.6, 0.8); tree(4.6, 3.2); tree(5.3, 5.2, 0.7);
        person(1.6, 2.6); person(-2.6, 2.2, PAL.accent);
        road([[-7, 1.6], [7, 1.6]]);
        d.anchors.main = [cx + 0.3, cy, 5.6];
        break;
      }
      case "intro": {
        // a calendar that fills from the top: tall blocks at the back, empty slots at the front
        for (let r = 0; r < 4; r++) for (let c = 0; c < 5; c++) {
          const full = r + (c % 2) * 0.5 < 2.6;
          const h = full ? 2.6 - r * 0.55 + ((c * 7 + r * 3) % 3) * 0.2 : 0.15;
          bld(B(-5 + c * 2.1, -5 + r * 2.1, 1.6, 1.6, h, full ? (r === 0 && c === 2 ? PAL.accent : PAL.white) : PAL.glass), full ? "booked" : "free");
        }
        tree(5, 4.4, 0.8); person(3.6, 5);
        d.anchors.main = [cx - 1, cy - 4, 3];
        break;
      }
      case "features": {
        const k = Math.max(1, n);
        for (let j = 0; j < k; j++) {
          const x = -5 + (k === 1 ? 5 : (10 * j) / (k - 1)) - 1, y = j % 2 ? 1.5 : -3;
          const name = s.items[j]?.querySelector("h3")?.textContent || "";
          const parts: Box[] = [];
          const t = j % 4;
          if (t === 0) { parts.push(bld(B(x, y, 2, 2, 3.4, PAL.white), name), bld(B(x + 0.4, y + 0.4, 1.2, 1.2, 0.8, PAL.teal, 3.4), name)); }
          else if (t === 1) { parts.push(bld(B(x, y, 2.6, 1.4, 1.6, PAL.white), name), bld(B(x, y + 1.4, 1.2, 1.4, 2.6, PAL.white), name)); }
          else if (t === 2) { parts.push(bld(B(x, y, 2.4, 2.4, 1.2, PAL.white), name), bld(B(x + 0.4, y + 0.4, 1.6, 1.6, 1.2, PAL.white, 1.2), name), bld(B(x + 0.8, y + 0.8, 0.8, 0.8, 1.2, PAL.white, 2.4), name)); }
          else { parts.push(bld(B(x, y, 2.8, 2, 1.8, PAL.white), name), bld(B(x + 0.3, y + 0.3, 2.2, 1.4, 0.4, PAL.yellow, 1.8), name)); }
          parts.forEach((p) => { p.stop = j; });
          d.feat.push(parts);
          const top = Math.max(...parts.map((p) => p.z0 + p.h));
          d.anchors["f" + j] = [cx + x + 1, cy + y + 1, top];
          d.stops.push([cx + x + 1, cy + y + 1, 0]);
        }
        road([[-7, -0.5], [7, -0.5]]);
        tree(-6, 5.3, 0.8); tree(5.6, -5.8, 0.8); person(0.5, 4.4);
        d.stops.shift();
        break;
      }
      case "product": {
        const dev = bld(B(0.6, -3.2, 4.6, 0.9, 8.6, PAL.white), "screen");
        d.device = dev;
        const m = Math.max(2, n || 3);
        for (let j = 0; j < m; j++) {
          const pal = j === m - 1 ? PAL.accent : j % 2 ? PAL.teal : PAL.white;
          const b = B(-5.2, -1.4, 3.6, 3.6, 0.4, pal, 0.05 + j * 0.42, "layer");
          d.stack.push(b);
        }
        person(-1, 4.6); tree(5, 4.6, 0.8);
        d.anchors.main = [cx + 2.9, cy - 2.3, 8.6];
        break;
      }
      case "stats": {
        const vals = s.labels.map((l) => parseFloat(l.dataset.v || ""));
        const max = Math.max(1e-6, ...vals.filter((v) => isFinite(v)));
        const k = Math.max(1, vals.length);
        vals.forEach((v, j) => {
          const h = !isFinite(v) ? 2.5 : v === 0 ? 0.12 : 0.6 + 5.4 * (v / max);
          const x = -6.2 + (k === 1 ? 5.2 : (11 * j) / (k - 1)), y = -1.6 + (j % 2) * 1.4;
          const b = bld(B(x, y, 1.6, 1.6, h, j % 2 ? PAL.teal : PAL.accent), s.labels[j].querySelector("span")?.textContent || "");
          d.towers.push(b);
          d.anchors["s" + j] = [cx + x + 0.8, cy + y + 0.8, h];
        });
        person(5.4, 3.8); person(6.1, 4.6, PAL.accent);
        d.anchors.main = [cx, cy, 2];
        break;
      }
      case "timeline": {
        const route: [number, number][] = [[-6, -4.5], [5, -4.5], [5, 0], [-5, 0], [-5, 4.5], [6, 4.5]];
        road(route);
        d.route = route.map(([x, y]) => [cx + x, cy + y]);
        const k = Math.max(1, n);
        d.stations = [];
        const lenTot = routeLen(d.route);
        for (let j = 0; j < k; j++) {
          const at = pointAt(d.route, ((j + 0.5) / k) * lenTot);
          const st = bld(new Box(at[0] - 0.7, at[1] - 1.9, 1.4, 1.2, 1.2, 0, PAL.white, 0, ""), s.items[j]?.querySelector("h3")?.textContent || "");
          all.push(st);
          d.stations.push(st);
          const flag = new Box(at[0] - 0.1, at[1] - 1.5, 0.2, 0.2, 1.4, 1.2, PAL.ink, 0, "prop"); all.push(flag); d.props.push(flag);
          d.anchors["t" + j] = [at[0], at[1] - 1.3, 2.6];
          d.stops.push([at[0], at[1], 0]);
        }
        d.stops.shift();
        const tk = new Box(0, 0, 0.9, 0.9, 0.6, 0.06, PAL.accent, 0, "token");
        d.tokenG = tk.g; (d as any).token = tk;
        tree(6, -6.2, 0.7); tree(-6.4, 6, 0.8);
        break;
      }
      case "quote": {
        bld(B(-1.5, 1, 3.2, 0.7, 0.45, PAL.trunk), "bench");
        d.anchors.person = person(-0.2, -0.4, PAL.accent);
        tree(-4.5, -4, 1.1); tree(3.6, -3.8, 0.9); tree(4.6, 3.6, 1); tree(-5, 3.8, 0.8);
        break;
      }
      case "faq": {
        const k1 = bld(B(-1.5, -1.5, 3, 3, 2.2, PAL.white), "help desk");
        bld(B(-1.9, -1.9, 3.8, 3.8, 0.35, PAL.teal, 2.2), "help desk");
        d.anchors.main = [cx, cy, 2.6];
        const qm = document.createElementNS(NS, "text");
        const [qx, qy] = proj(k1.x + 1.5, k1.y + 3, 1.3);
        qm.setAttribute("transform", `matrix(.894 .447 0 1 ${qx - 8} ${qy})`);
        qm.setAttribute("font-size", "34"); qm.setAttribute("fill", "#d24a28"); qm.textContent = "?";
        k1.g.appendChild(qm);
        person(3.5, 2.5); person(4.5, 1.8, PAL.accent); tree(-5, 4, 0.9);
        break;
      }
      case "cta": {
        bld(B(-3, -3, 6, 6, 0.3, PAL.white), "plaza");
        bld(B(-2, -2, 4, 4, 0.5, PAL.teal, 0.3), "fountain");
        bld(B(-0.5, -0.5, 1, 1, 2.2, PAL.accent, 0.8), "beacon");
        tree(-6, -6, 0.9); tree(5.5, -6, 0.9); tree(-6, 5.4, 0.9); tree(5.4, 5.4, 0.9);
        person(3.6, 0); person(-3.8, 1, PAL.accent);
        d.anchors.main = [cx, cy, 3];
        break;
      }
      default:
        tree(-2, -2); tree(2, 1); person(0, 3);
        d.anchors.main = [cx, cy, 1];
    }
    // paint back to front
    d.chunks.forEach((c) => d.g.appendChild(c.g));
    all.filter((b) => b.g.classList.contains("road")).forEach((b) => d.g.appendChild(b.g));
    const rest = all.filter((b) => !b.g.classList.contains("road")).sort((a, b) => a.depth - b.depth);
    rest.forEach((b) => d.g.appendChild(b.g));
    if (d.tokenG) d.g.appendChild(d.tokenG);
    d.props = d.props.filter((p) => !p.g.classList.contains("road")).concat(all.filter((b) => b.g.classList.contains("road")));
    // delays: buildings extrude in order, props pop last
    d.blds.forEach((b, k) => { b.delay = 0.32 + (k / Math.max(1, d.blds.length)) * 0.3; });
    d.stack.forEach((b, k) => { b.delay = 0.36 + k * 0.06; });
    d.props.forEach((b, k) => { b.delay = 0.62 + (k / Math.max(1, d.props.length)) * 0.2; });
    d.g.style.display = "none";
  }

  // ------------------------------------------------------------ hover: tiles lift, a flat label pops, click flies there
  let hoverBox: Box | null = null;
  const allBlds = secs.flatMap((s) => s.d.blds);
  allBlds.forEach((b) => {
    b.g.addEventListener("pointerenter", () => { hoverBox = b; b.lift = 10; b.g.classList.add("is-lift"); b.draw(); if (b.name) { label.textContent = b.name; label.classList.add("is-on"); } });
    b.g.addEventListener("pointerleave", () => { if (hoverBox === b) hoverBox = null; b.lift = 0; b.g.classList.remove("is-lift"); b.draw(); label.classList.remove("is-on"); });
    b.g.addEventListener("click", () => flyTo(b.sec, b.stop));
  });
  world.addEventListener("pointermove", (e) => { label.style.left = e.clientX + "px"; label.style.top = e.clientY + "px"; });
  world.style.pointerEvents = "auto";

  // ------------------------------------------------------------ layout
  let W = innerWidth, H = innerHeight, mobile = false, scale = 1, ax = 0, ay = 0;
  function layout() {
    W = innerWidth; H = innerHeight; mobile = W <= 760;
    scale = mobile ? 0.6 : clamp(W / 1500, 0.72, 1.25);
    ax = mobile ? W * 0.5 : W * 0.66; ay = mobile ? H * 0.36 : H * 0.56;
    lead.setAttribute("viewBox", `0 0 ${W} ${H}`);
    secs.forEach((s) => {
      const n = s.d.stops.length;
      const lenScreens = s.kind === "hero" ? 1.3 : s.kind === "cta" ? 2.1 : s.kind === "product" ? 1.9 : s.kind === "stats" ? 1.5 : 1.0 + n * 0.7;
      s.el.style.setProperty("--len", lenScreens.toFixed(2));
    });
    secs.forEach((s, i) => {
      const r = s.el.getBoundingClientRect();
      s.top = r.top + scrollY; s.len = Math.max(1, r.height - (i === secs.length - 1 ? H * 0.9 : 0));
      s.glideFrac = i === 0 ? 0 : Math.min(0.4, (H * 0.6) / s.len);
    });
    drawMini();
    lastY = -1;
  }

  // ------------------------------------------------------------ camera along the map
  function axisPath(a: number[], b: number[], t: number): [number, number, number] {
    const dx = b[0] - a[0], dy = b[1] - a[1], ax2 = Math.abs(dx), tot = ax2 + Math.abs(dy) || 1, d = t * tot;
    if (d <= ax2 && ax2 > 0) return [a[0] + Math.sign(dx) * d, a[1], 0];
    if (!dy) return [a[0] + Math.sign(dx) * d, a[1], 0];
    return [b[0], a[1] + Math.sign(dy) * (d - ax2), 0];
  }
  interface CamState { p: [number, number, number]; si: number; q: number; stop: number; arrive: number; zoom: number }
  function camAt(y: number): CamState {
    let si = 0;
    for (let k = 0; k < secs.length; k++) if (y >= secs[k].top - 1) si = k;
    const s = secs[si];
    const q = clamp((y - s.top) / s.len);
    const stops = s.d.stops;
    const prev = si > 0 ? secs[si - 1].d.stops[secs[si - 1].d.stops.length - 1] : stops[0];
    if (reduced) {
      const j = Math.min(stops.length - 1, Math.floor(clamp((q - s.glideFrac) / Math.max(1e-6, 1 - s.glideFrac)) * stops.length));
      return { p: stops[Math.max(0, j)], si, q, stop: Math.max(0, j), arrive: 1, zoom: s.kind === "cta" ? 1 : 0 };
    }
    if (q < s.glideFrac) {
      const t = glide(q / s.glideFrac);
      return { p: axisPath(prev, stops[0], t), si, q, stop: 0, arrive: q / s.glideFrac, zoom: 0 };
    }
    const r = ((q - s.glideFrac) / Math.max(1e-6, 1 - s.glideFrac)) * stops.length;
    const j = Math.min(stops.length - 1, Math.floor(r)), f = r - j;
    let p = stops[j];
    if (j > 0 && f < 0.3) p = axisPath(stops[j - 1], stops[j], glide(f / 0.3));
    const zoom = s.kind === "cta" ? clamp((q - s.glideFrac) / 0.45) : 0;
    return { p, si, q, stop: j, arrive: 1, zoom };
  }

  // ------------------------------------------------------------ minimap
  const mini = $<SVGSVGElement>(".iso-mini__map"), miniHere = $<HTMLElement>(".iso-mini__here");
  let miniMarker: SVGCircleElement | null = null, miniT = { s: 1, ox: 0, oy: 0 };
  function drawMini() {
    if (!mini) return;
    const box = mini.getBoundingClientRect();
    if (!box.width) return;
    const pts = secs.map((s) => proj(s.d.cx, s.d.cy, 0));
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const pad = 7 * TW;
    const minX = Math.min(...xs) - pad, maxX = Math.max(...xs) + pad, minY = Math.min(...ys) - pad * 0.6, maxY = Math.max(...ys) + pad * 0.6;
    const s = Math.min(box.width / (maxX - minX), box.height / (maxY - minY));
    miniT = { s, ox: (box.width - (maxX - minX) * s) / 2 - minX * s, oy: (box.height - (maxY - minY) * s) / 2 - minY * s };
    mini.setAttribute("viewBox", `0 0 ${box.width} ${box.height}`);
    const m = (x: number, y: number) => { const [px, py] = proj(x, y, 0); return [px * s + miniT.ox, py * s + miniT.oy]; };
    let out = `<polyline fill="none" stroke="#8e9caf" stroke-width="2" points="${secs.map((sc) => m(sc.d.cx, sc.d.cy).join(",")).join(" ")}"/>`;
    secs.forEach((sc, i) => {
      const c = [m(sc.d.cx - 7, sc.d.cy - 7), m(sc.d.cx + 7, sc.d.cy - 7), m(sc.d.cx + 7, sc.d.cy + 7), m(sc.d.cx - 7, sc.d.cy + 7)];
      out += `<g class="d" data-i="${i}"><polygon points="${c.map((p) => p.join(",")).join(" ")}" fill="#f3ebdd" stroke="#9fb3c8"/></g>`;
    });
    out += `<circle class="here" r="4.5" fill="#d24a28" stroke="#fff" stroke-width="2"/>`;
    mini.innerHTML = out;
    miniMarker = mini.querySelector("circle.here");
    $$<SVGGElement>(".d", mini).forEach((g) => g.addEventListener("click", () => flyTo(+(g.dataset.i || 0), -1)));
  }
  function flyTo(si: number, stop: number) {
    const s = secs[si];
    if (!s) return;
    const n = s.d.stops.length;
    const target = s.top + s.len * (s.glideFrac + (1 - s.glideFrac) * ((Math.max(0, stop) + 0.5) / n)) - 2;
    const from = scrollY, t0 = performance.now(), dur = Math.min(1500, 500 + Math.abs(target - from) * 0.08);
    const step = (now: number) => { const k = clamp((now - t0) / dur); scrollTo(0, from + (target - from) * k); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }

  // ------------------------------------------------------------ frame
  const t0 = performance.now();
  const startTop = scrollY < 10;
  let lastY = -1;
  const navLinks = $$<HTMLAnchorElement>(".iso-bar__links a");
  function frame(y: number) {
    const now = performance.now();
    const intro = !reduced && startTop ? clamp((now - t0 - 150) / 1900) : 1;
    if (y === lastY && intro >= 1) return;
    lastY = y;
    const c = camAt(y);
    const cs = secs[c.si];
    // camera transform (the last district zooms out over the whole world)
    let s = scale, target = c.p;
    if (c.zoom > 0) {
      const pts = secs.map((sc) => proj(sc.d.cx, sc.d.cy, 0));
      const minX = Math.min(...pts.map((p) => p[0])) - 8 * TW, maxX = Math.max(...pts.map((p) => p[0])) + 8 * TW;
      const minY = Math.min(...pts.map((p) => p[1])) - 9 * TH, maxY = Math.max(...pts.map((p) => p[1])) + 9 * TH;
      const fit = Math.min((W * 0.92) / (maxX - minX), (H * (mobile ? 0.5 : 0.62)) / (maxY - minY));
      const z = reduced ? 1 : c.zoom;
      s = lerp(scale, Math.min(scale, fit), z);
      const [px, py] = proj(c.p[0], c.p[1], 0);
      const cxw = (minX + maxX) / 2, cyw = (minY + maxY) / 2;
      const sx = lerp(px, cxw, z), sy = lerp(py, cyw, z);
      const axz = lerp(ax, W / 2, z), ayz = lerp(ay, mobile ? H * 0.34 : H * 0.62, z);
      cam.setAttribute("transform", `translate(${(axz - sx * s).toFixed(1)} ${(ayz - sy * s).toFixed(1)}) scale(${s.toFixed(4)})`);
      camT = { s, tx: axz - sx * s, ty: ayz - sy * s };
    } else {
      const [px, py] = proj(target[0], target[1], 0);
      cam.setAttribute("transform", `translate(${(ax - px * s).toFixed(1)} ${(ay - py * s).toFixed(1)}) scale(${s.toFixed(4)})`);
      camT = { s, tx: ax - px * s, ty: ay - py * s };
    }

    // build each district as the camera arrives (and unbuild it if you scroll back)
    secs.forEach((sc, k) => {
      let bp: number;
      if (reduced) bp = k <= c.si + 1 ? 1 : 0;
      else if (k === 0) bp = Math.max(intro, k < c.si ? 1 : 0);
      else if (k < c.si) bp = 1;
      else if (k > c.si) bp = 0;
      else bp = clamp((c.q - sc.glideFrac * 0.3) / (sc.glideFrac * 0.7 + (H * 0.55) / sc.len));
      if (k === c.si + 1 && !reduced) bp = 0;
      setBuild(sc, bp, k === c.si ? c : null);
    });

    // HUD: the current district's cards, items, labels and leaders
    let paths = "";
    secs.forEach((sc, k) => {
      let p = 0;
      if (k === c.si) p = reduced ? 1 : clamp((c.q - sc.glideFrac * 0.85) / Math.max(0.02, sc.glideFrac * 0.2 + 0.04));
      if (k === 0 && c.si === 0) p = Math.min(1, intro * 1.6 - 0.2);
      if (k === c.si - 1 && !reduced) { const nx = secs[c.si]; p = 1 - clamp(c.q / Math.max(0.01, nx.glideFrac * 0.25)); }
      const on = p > 0.01;
      if (sc.hud) {
        sc.hud.classList.toggle("is-on", on);
        if (on || sc.hud.dataset.p !== "0") {
          sc.hud.dataset.p = on ? "1" : "0";
          const kids = [...sc.hud.children] as HTMLElement[];
          kids.forEach((kid, j) => {
            if (kid.classList.contains("iso-stats") || kid.classList.contains("iso-layers")) return;
            const kp = clamp(p * 1.4 - j * 0.15);
            kid.style.opacity = kp.toFixed(3);
            kid.style.transform = kp >= 1 ? "" : `translateY(${((1 - backOut(kp)) * 18).toFixed(1)}px)`;
          });
        }
      }
      if (sc.screen) sc.screen.classList.toggle("is-on", k === c.si && sc.d.build > 0.5);
      if (!on) { sc.items.forEach((li) => { li.style.visibility = "hidden"; }); sc.labels.forEach((l) => { l.style.visibility = "hidden"; }); return; }
      // items: the active feature or step card, pinned to its building or station
      const active = k === c.si ? c.stop : sc.items.length - 1;
      sc.items.forEach((li, j) => {
        const isOn = j === active;
        li.style.visibility = isOn ? "" : "hidden";
        if (isOn) {
          const a = sc.d.anchors[li.dataset.anchor || ""];
          if (a) paths += leader(li, a);
        }
      });
      if (sc.kind === "features") sc.d.feat.forEach((parts, j) => parts.forEach((b) => { b.g.classList.toggle("is-on", j === active); b.g.classList.toggle("is-dim", j !== active); }));
      if (sc.kind === "timeline" && sc.d.stations) sc.d.stations.forEach((b, j) => b.g.classList.toggle("is-on", j <= active));
      // main card leader
      const card = sc.hud?.querySelector<HTMLElement>("[data-anchor]:not(li)");
      if (card && card.dataset.anchor && sc.d.anchors[card.dataset.anchor] && !sc.items.length) paths += leader(card, sc.d.anchors[card.dataset.anchor]);
      // labels floating over towers and layers
      sc.labels.forEach((l, j) => {
        const a = sc.d.anchors[l.dataset.anchor || ""];
        if (!a) { l.style.visibility = "hidden"; return; }
        const [sx, sy] = toScreen(a);
        const lp = clamp(p * 1.3 - j * 0.08) * (sc.kind === "stats" ? clamp(sc.d.build * 1.4 - 0.3 - j * 0.05) : 1);
        l.style.visibility = lp > 0.02 ? "" : "hidden";
        l.style.opacity = lp.toFixed(3);
        if (sc.kind === "stats" && mobile) {
          // phones: the figures sit in a flat card under the towers instead of floating over them
        } else if (sc.kind === "stats") {
          const w = l.offsetWidth, h = l.offsetHeight;
          l.style.transform = `translate(${(sx - w / 2).toFixed(1)}px, ${(sy - h - 26 + (1 - lp) * 10).toFixed(1)}px)`;
          paths += `<path d="M${sx} ${sy - 26} V${sy - 3}"/><circle cx="${sx}" cy="${sy}" r="3"/>`;
        } else {
          const off = mobile ? 70 : 120;
          const lx = Math.max(8, sx - off - l.offsetWidth), ly = sy - l.offsetHeight / 2;
          l.style.transform = `translate(${(lx - (1 - lp) * 20).toFixed(1)}px, ${ly.toFixed(1)}px)`;
          paths += `<path d="M${lx + l.offsetWidth + 4} ${sy} H${sx - 3}"/><circle cx="${sx}" cy="${sy}" r="3"/>`;
        }
      });
      if (sc.screen && sc.d.device) placeScreen(sc.screen, sc.d.device);
    });
    lead.innerHTML = paths;
    navLinks.forEach((a) => a.classList.toggle("is-on", a.getAttribute("href") === "#" + cs.el.id));
    // minimap marker
    if (miniMarker) {
      const [px, py] = proj(c.p[0], c.p[1], 0);
      miniMarker.setAttribute("cx", (px * miniT.s + miniT.ox).toFixed(1)); miniMarker.setAttribute("cy", (py * miniT.s + miniT.oy).toFixed(1));
      $$<SVGGElement>(".d", mini!).forEach((g, i) => g.classList.toggle("is-on", i === c.si));
      if (miniHere) miniHere.textContent = String(c.si + 1).padStart(2, "0") + " / " + String(secs.length).padStart(2, "0");
    }
  }
  let camT = { s: 1, tx: 0, ty: 0 };
  const toScreen = (a: [number, number, number]): [number, number] => { const [px, py] = proj(a[0], a[1], a[2]); return [px * camT.s + camT.tx, py * camT.s + camT.ty]; };
  function leader(el: HTMLElement, a: [number, number, number]) {
    const r = el.getBoundingClientRect();
    if (!r.width) return "";
    const [sx, sy] = toScreen(a);
    const right = sx > r.right;
    const x0 = right ? r.right : sx < r.left ? r.left : r.left + r.width / 2;
    const y0 = right || sx < r.left ? Math.min(r.bottom - 12, Math.max(r.top + 12, r.top + 34)) : sy < r.top ? r.top : r.bottom;
    // a flat leader: out along the card, then up the isometric 26.57 degree diagonal to the pin
    const mx = right ? x0 + 24 : x0 - 24;
    return `<path d="M${x0} ${y0} H${mx} L${sx} ${sy}"/><circle class="ring" cx="${sx}" cy="${sy}" r="6"/><circle cx="${sx}" cy="${sy}" r="2.5"/>`;
  }
  function placeScreen(el: HTMLElement, dev: Box) {
    const phone = el.firstElementChild as HTMLElement | null;
    if (!phone) return;
    const Wel = phone.offsetWidth || 260, Hel = phone.offsetHeight || 530;
    const ins = 0.18, top = dev.z0 + dev.h * dev.ext - 0.25, bottom = dev.z0 + 0.35;
    const yv = dev.y + dev.d;
    const o = toScreen([dev.x + ins, yv, top]), ex = toScreen([dev.x + dev.w - ins, yv, top]), ey = toScreen([dev.x + ins, yv, bottom]);
    const dy = -(1 - dev.drop) * 7 * ZH * camT.s - dev.lift * camT.s;
    el.style.transform = `matrix(${((ex[0] - o[0]) / Wel).toFixed(5)}, ${((ex[1] - o[1]) / Wel).toFixed(5)}, ${((ey[0] - o[0]) / Hel).toFixed(5)}, ${((ey[1] - o[1]) / Hel).toFixed(5)}, ${o[0].toFixed(1)}, ${(o[1] + dy).toFixed(1)})`;
    el.style.opacity = clamp((dev.ext - 0.85) / 0.15).toFixed(3);
  }

  function setBuild(sc: Sec, bp: number, c: CamState | null) {
    const d = sc.d;
    const sub = c ? `${c.q.toFixed(4)}` : "";
    const key = bp.toFixed(4) + sub;
    if ((d as any).key === key) return;
    (d as any).key = key;
    d.build = bp;
    d.g.style.display = bp > 0 ? "" : "none";
    if (bp <= 0) return;
    for (const ch of d.chunks) { ch.drop = backOut(clamp((bp - ch.delay) / 0.22)); if (clamp((bp - ch.delay) / 0.22) <= 0) ch.drop = 0; ch.draw(); }
    for (const b of d.blds) { const k = clamp((bp - b.delay) / 0.26); b.ext = k <= 0 ? 0 : backOut(k); b.draw(); }
    for (const b of d.props) { const k = clamp((bp - b.delay) / 0.14); b.ext = k <= 0 ? 0 : backOut(k); b.draw(); }
    // stats towers rise to their values; the product's stack separates and recompresses; the token drives the road
    if (sc.kind === "product") {
      const q = c ? c.q : 1;
      const e = reduced ? 1 : clamp((q - sc.glideFrac - 0.05) / 0.3) * (1 - clamp((q - 0.86) / 0.14) * 0.6);
      d.stack.forEach((b, j) => {
        const k = clamp((bp - b.delay) / 0.2);
        b.z0 = 0.05 + j * (0.42 + e * 1.15);
        b.ext = k <= 0 ? 0 : backOut(k); b.key = ""; b.draw();
        d.anchors["l" + j] = [b.x + b.w, b.y + b.d / 2, b.z0 + 0.2];
      });
    }
    if (sc.kind === "timeline" && d.route && (d as any).token) {
      const tk = (d as any).token as Box;
      const q = c ? c.q : 1;
      const n = Math.max(1, sc.items.length);
      const r = clamp((q - sc.glideFrac) / Math.max(1e-6, 1 - sc.glideFrac)) * n;
      const L = routeLen(d.route);
      const along = clamp((Math.min(n - 0.5, Math.max(0.5, r)) / n) * L, 0, L);
      const [x, y] = pointAt(d.route, along);
      tk.x = x - 0.45; tk.y = y - 0.45; tk.key = "";
      tk.ext = clamp((bp - 0.7) / 0.1); tk.drop = 1; tk.draw();
    }
  }

  layout();
  addEventListener("resize", () => { layout(); frame(scrollY); });
  document.fonts?.ready.then(() => { layout(); frame(scrollY); });
  onFrame(({ y }) => frame(y));
}

function routeLen(r: [number, number][]) { let s = 0; for (let i = 1; i < r.length; i++) s += Math.abs(r[i][0] - r[i - 1][0]) + Math.abs(r[i][1] - r[i - 1][1]); return s; }
function pointAt(r: [number, number][], d: number): [number, number] {
  for (let i = 1; i < r.length; i++) {
    const l = Math.abs(r[i][0] - r[i - 1][0]) + Math.abs(r[i][1] - r[i - 1][1]);
    if (d <= l) { const t = l ? d / l : 0; return [lerp(r[i - 1][0], r[i][0], t), lerp(r[i - 1][1], r[i][1], t)]; }
    d -= l;
  }
  return r[r.length - 1];
}
