/**
 * Wireframe 3D: you fly through the blueprint. One three.js world drawn only in edges (fat lines, hidden lines removed
 * by background-coloured occluders) holds the product (a phone built from parts), a measuring yard, a contoured
 * survey terrain with a route, all on a CAD floor grid. Scrolling IS the camera: one continuous Catmull-Rom spline runs
 * through a station per section (front 3/4, front elevation with a section cut sweeping down, exploded view, render,
 * dimensions, route waypoints, rear note, plan, final assembly), easing to settle at each. The copy is pinned to the
 * model by leader lines; headlines plot on as outline type; numbers are dimension lines that grow up the towers; the
 * features are the phone's parts flying apart with numbered balloons keyed to a parts list; at the product the line
 * drawing solidifies (faces fill, the app appears on the screen, edges fade) and the last station reassembles it,
 * APPROVED FOR BUILD. The pointer is an inspection probe: parts light up with their dimensions, a drag orbits a little
 * and springs back, the toolbar's axis gizmo turns with the camera. Reduced motion: cuts between fixed stations.
 */
import * as THREE from "three";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { $, $$, onFrame, reduced, chars } from "./_kit";

const BG = 0x0a0a0b, INK = 0xd9dde3, CONS = 0x2b3038, CONS2 = 0x3a3f47, HI = 0x4da3ff;
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (t: number) => t * t * (3 - 2 * t);
const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

interface Station { pos: THREE.Vector3; target: THREE.Vector3; fov: number }
interface Part { group: THREE.Group; edges: LineSegments2; occ: THREE.Mesh; solid: THREE.Mesh; z0: number; t: number; name: string; dims: string; idx: number; top: THREE.Vector3 }
interface Sec {
  el: HTMLElement; kind: string; call: HTMLElement | null; plots: { el: HTMLElement; spans: HTMLElement[]; last: number }[];
  a: number; b: number; top: number; len: number; travel: number; occ: number; view: string;
  rows: HTMLElement[]; dims: HTMLElement[];
}

export default function start() {
  const secEls = $$<HTMLElement>("main section.wf-st");
  if (!secEls.length) return;
  const root = document.documentElement;
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  } catch (err) {
    console.warn("[wireframe-3d] no WebGL; showing the static drawing sheets", err);
    return;
  }
  root.classList.add("wf-live");
  const canvas = renderer.domElement;
  canvas.className = "wf-canvas";
  canvas.setAttribute("aria-hidden", "true");
  document.body.prepend(canvas);
  const hud = document.createElementNS("http://www.w3.org/2000/svg", "svg") as SVGSVGElement;
  hud.setAttribute("class", "wf-hud"); hud.setAttribute("aria-hidden", "true");
  document.body.appendChild(hud);
  renderer.setClearColor(BG, 1);

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(BG, 40, 190);
  const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 0.1, 600);
  scene.add(new THREE.HemisphereLight(0xc8d8ff, 0x1a1c20, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.7); sun.position.set(12, 24, 18); scene.add(sun);

  // ------------------------------------------------------------ materials and line helpers
  const mats: LineMaterial[] = [];
  const lineMat = (color: number, width: number, opacity = 1) => {
    const m = new LineMaterial({ color, linewidth: width, transparent: opacity < 1, opacity, fog: true } as any);
    mats.push(m);
    return m;
  };
  const mInk = lineMat(INK, 1.35), mHi = lineMat(HI, 1.8), mCons = lineMat(CONS, 1), mCons2 = lineMat(CONS2, 1), mDim = lineMat(INK, 1, 0.55), mRoute = lineMat(HI, 2);
  const mOcc = new THREE.MeshBasicMaterial({ color: BG, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  const segs = (arr: number[], mat: LineMaterial) => { const g = new LineSegmentsGeometry(); g.setPositions(arr); return new LineSegments2(g, mat); };
  const edgesOf = (geom: THREE.BufferGeometry, mat: LineMaterial, angle = 24) => {
    const g = new LineSegmentsGeometry().fromEdgesGeometry(new THREE.EdgesGeometry(geom, angle));
    return new LineSegments2(g, mat);
  };
  const solidOf = (geom: THREE.BufferGeometry, mat: THREE.Material = mOcc) => new THREE.Mesh(geom, mat);
  function rr(w: number, h: number, r: number) {
    const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r);
    s.quadraticCurveTo(x + w, y + h, x + w - r, y + h); s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    return s;
  }

  // ------------------------------------------------------------ the sections and what the world needs from them
  const counts: Record<string, number> = {};
  const secs: Sec[] = secEls.map((el) => {
    const kind = el.dataset.wf || "intro";
    const occ = counts[kind] = (counts[kind] ?? -1) + 1;
    const call = el.querySelector<HTMLElement>(".wf-call");
    if (call && (kind === "intro" || kind === "product" || kind === "quote")) call.classList.add("is-right");
    const plots = $$<HTMLElement>(".wf-plot", el).map((p) => ({ el: p, spans: chars(p), last: -1 }));
    return { el, kind, call, plots, a: 0, b: 0, top: 0, len: 1, travel: 0, occ, view: el.dataset.view || kind, rows: $$<HTMLElement>("[data-i]", el), dims: $$<HTMLElement>(".wf-dim", el) };
  });
  const featSec = secs.find((s) => s.kind === "features");
  const nFeat = featSec ? Math.max(1, featSec.rows.length) : 0;
  const tlSec = secs.find((s) => s.kind === "timeline");
  const nWp = tlSec ? Math.max(1, tlSec.rows.length) : 3;

  // ------------------------------------------------------------ the floor: a CAD grid
  {
    const minor: number[] = [], major: number[] = [];
    for (let i = -140; i <= 140; i += 4) {
      const arr = i % 20 === 0 ? major : minor;
      arr.push(i, 0, -140, i, 0, 140, -140, 0, i, 140, 0, i);
    }
    scene.add(segs(minor, mCons), segs(major, mCons2));
  }

  // ------------------------------------------------------------ the product: a phone made of parts
  const PH = { w: 7.2, h: 15, y: 8.1 };
  const parts: Part[] = [];
  const phone = new THREE.Group();
  scene.add(phone);
  {
    const plinthG = new THREE.BoxGeometry(13, 0.6, 7);
    const plinth = new THREE.Group();
    plinth.add(solidOf(plinthG), edgesOf(plinthG, mInk));
    plinth.position.set(0, 0.3, 0);
    scene.add(plinth);
    const kinds = ["glass", "display", "board", "battery", "back"];
    const P = Math.max(5, nFeat);
    const thick = [0.12, 0.2, 0.32, 0.38, 0.26];
    let z = 0.55;
    for (let i = 0; i < P; i++) {
      const k = i % 5, t = thick[k];
      z -= t + 0.02;
      const g = new THREE.Group();
      const w = k === 3 ? 5.4 : PH.w - (k === 1 ? 0.2 : 0), h = k === 3 ? 9.6 : PH.h - (k === 1 ? 0.2 : 0);
      const shape = rr(w, h, k === 3 ? 0.35 : 1.1);
      const geom = new THREE.ExtrudeGeometry(shape, { depth: t, bevelEnabled: false, curveSegments: 6 });
      const occ = solidOf(geom);
      const solidMat = new THREE.MeshStandardMaterial({ color: k === 0 ? 0x1c222b : 0x3a414c, roughness: k === 0 ? 0.25 : 0.6, metalness: 0.45, transparent: true, opacity: 0 });
      const solid = new THREE.Mesh(geom, solidMat);
      solid.renderOrder = 2;
      const edges = edgesOf(geom, mInk);
      g.add(occ, solid, edges);
      // part details, drawn in line on the part's front face
      const det: number[] = [];
      const f = t + 0.01;
      const rect = (cx: number, cy: number, rw: number, rh: number) => { const x0 = cx - rw / 2, x1 = cx + rw / 2, y0 = cy - rh / 2, y1 = cy + rh / 2; det.push(x0, y0, f, x1, y0, f, x1, y0, f, x1, y1, f, x1, y1, f, x0, y1, f, x0, y1, f, x0, y0, f); };
      if (k === 1) rect(0, 0.2, 6.2, 13.2);
      if (k === 2) { rect(-1.6, 4.6, 2.2, 2.2); rect(1.4, 5, 2, 1.2); rect(1.4, 3.4, 2, 1); rect(0, -1.5, 5, 3.2); rect(-2, -5.6, 1.2, 1.2); rect(1.2, -5.6, 3, 0.8); }
      if (k === 3) { rect(0, 0, 4.4, 8.6); det.push(-0.5, 0.6, f, 0.5, 0.6, f, 0, 0.1, f, 0, 1.1, f, -0.5, -0.8, f, 0.5, -0.8, f); }
      if (k === 4) {
        const bump = new THREE.ExtrudeGeometry(rr(2.8, 2.8, 0.7), { depth: 0.3, bevelEnabled: false, curveSegments: 5 });
        const bm = new THREE.Group(); bm.add(solidOf(bump), edgesOf(bump, mInk)); bm.position.set(-1.6, 5, -0.3); g.add(bm);
        for (const [cx, cy] of [[-2.2, 5.6], [-1, 4.4], [-2.2, 4.4]] as [number, number][]) {
          const cyl = new THREE.CylinderGeometry(0.45, 0.45, 0.14, 18); cyl.rotateX(Math.PI / 2);
          const cg = new THREE.Group(); cg.add(solidOf(cyl), edgesOf(cyl, mInk, 30)); cg.position.set(cx, cy, -0.36); g.add(cg);
        }
      }
      if (det.length) g.add(segs(det, mDim));
      g.position.set(0, PH.y, z);
      phone.add(g);
      const fname = featSec?.rows[i]?.querySelector("b")?.textContent?.trim();
      parts.push({ group: g, edges, occ, solid, z0: z, t, name: (fname || kinds[k]).toUpperCase(), dims: `${w.toFixed(1)} × ${h.toFixed(1)} × ${t.toFixed(2)}`, idx: i, top: V(w / 2, h / 2, t) });
    }
  }
  // the app on the screen: drawn from the page's own device data into a texture
  const screenTex = new THREE.CanvasTexture(drawScreen());
  screenTex.colorSpace = THREE.SRGBColorSpace;
  const screenMat = new THREE.MeshBasicMaterial({ map: screenTex, transparent: true, opacity: 0, toneMapped: false, fog: false });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(6.2, 13.2), screenMat);
  screen.position.set(0, 0.2, 0.13);
  parts[0].group.add(screen);
  screen.renderOrder = 3;

  // ------------------------------------------------------------ the section cut (front elevation station)
  const cutPlane = new THREE.Group();
  {
    const w = 11, d = 5;
    cutPlane.add(segs([-w / 2, 0, -d / 2, w / 2, 0, -d / 2, w / 2, 0, -d / 2, w / 2, 0, d / 2, w / 2, 0, d / 2, -w / 2, 0, d / 2, -w / 2, 0, d / 2, -w / 2, 0, -d / 2], mHi));
    const hatch: number[] = [];
    for (let i = -w / 2; i < w / 2; i += 0.6) hatch.push(i, 0, -d / 2, Math.min(w / 2, i + d), 0, Math.min(d / 2, -d / 2 + (w / 2 - i)));
    cutPlane.add(segs(hatch, lineMat(HI, 1, 0.35)));
    cutPlane.visible = false;
    scene.add(cutPlane);
  }

  // ------------------------------------------------------------ the measuring yard: stats as dimensioned towers
  type Tower = { dim: THREE.Group; h: number; x: number; z: number };
  const yards = new Map<Sec, { at: THREE.Vector3; towers: Tower[] }>();
  secs.filter((sc) => sc.kind === "stats").forEach((sc) => {
    const at = V(30, 0, -6 - sc.occ * 26), towers: Tower[] = [];
    const vals = sc.dims.map((d) => parseFloat(d.dataset.v || ""));
    const max = Math.max(1e-6, ...vals.filter((v) => isFinite(v)));
    vals.forEach((v, j) => {
      const h = !isFinite(v) ? 6 : v === 0 ? 0.25 : 1.6 + 11 * (v / max);
      const x = at.x + j * 5.2, z = at.z;
      const bg = new THREE.BoxGeometry(2.6, h, 2.6);
      const tw = new THREE.Group(); tw.add(solidOf(bg), edgesOf(bg, mInk)); tw.position.set(x, h / 2, z); scene.add(tw);
      // floors drawn as horizontal hatches
      const fl: number[] = [];
      for (let y = 1; y < h; y += 1) fl.push(-1.3, y - h / 2, 1.31, 1.3, y - h / 2, 1.31);
      if (fl.length) tw.add(segs(fl, mDim));
      const dim = new THREE.Group();
      const dx = 2.4, a = 0.35;
      dim.add(segs([0, 0, 0, 0, h, 0, -dx + 0.2, 0, 0, 0.4, 0, 0, -dx + 0.2, h, 0, 0.4, h, 0, -a, a * 1.6, 0, 0, 0, 0, a, a * 1.6, 0, 0, 0, 0, -a, h - a * 1.6, 0, 0, h, 0, a, h - a * 1.6, 0, 0, h, 0], mHi));
      dim.position.set(x + 1.3 + dx, 0, z + 1.3);
      scene.add(dim);
      towers.push({ dim, h, x: x + 1.3 + dx, z: z + 1.3 });
    });
    yards.set(sc, { at, towers });
  });

  // ------------------------------------------------------------ the survey: contour terrain and a route with waypoints
  const hgt = (x: number, z: number) => 7 * Math.exp(-((x - 62) ** 2 + (z - 14) ** 2) / 260) + 5 * Math.exp(-((x - 86) ** 2 + (z - 44) ** 2) / 220) + 3 * Math.exp(-((x - 44) ** 2 + (z - 42) ** 2) / 160);
  {
    const out: number[] = [];
    const x0 = 26, x1 = 110, z0 = 0, z1 = 70, st = 1.2;
    for (let lv = 0.6; lv < 8; lv += 0.8) {
      for (let x = x0; x < x1; x += st) for (let z = z0; z < z1; z += st) {
        const c = [hgt(x, z), hgt(x + st, z), hgt(x + st, z + st), hgt(x, z + st)];
        const p = [[x, z], [x + st, z], [x + st, z + st], [x, z + st]];
        const pts: number[][] = [];
        for (let e = 0; e < 4; e++) {
          const a = c[e], b = c[(e + 1) % 4];
          if ((a < lv) !== (b < lv)) { const t = (lv - a) / (b - a); const pa = p[e], pb = p[(e + 1) % 4]; pts.push([lerp(pa[0], pb[0], t), lerp(pa[1], pb[1], t)]); }
        }
        if (pts.length >= 2) out.push(pts[0][0], lv, pts[0][1], pts[1][0], lv, pts[1][1]);
        if (pts.length === 4) out.push(pts[2][0], lv, pts[2][1], pts[3][0], lv, pts[3][1]);
      }
    }
    scene.add(segs(out, mCons2));
  }
  const routeCurve = new THREE.CatmullRomCurve3([V(38, 0, 6), V(50, 0, 22), V(62, 0, 30), V(72, 0, 18), V(84, 0, 28), V(92, 0, 52)], false, "centripetal");
  const routePts = routeCurve.getSpacedPoints(160).map((p) => V(p.x, hgt(p.x, p.z) + 0.15, p.z));
  const routeArr: number[] = [], dashArr: number[] = [];
  routePts.forEach((p, i) => { if (!i) return; const q = routePts[i - 1]; routeArr.push(q.x, q.y, q.z, p.x, p.y, p.z); if (i % 2) dashArr.push(q.x, q.y, q.z, p.x, p.y, p.z); });
  const routeDash = segs(dashArr, mDim); scene.add(routeDash);
  const routeLine = segs(routeArr, mRoute); scene.add(routeLine);
  const wps: THREE.Vector3[] = [];
  for (let j = 0; j < nWp; j++) {
    const p = routePts[Math.round(((j + 0.5) / nWp) * (routePts.length - 1))];
    const ring: number[] = [];
    for (let k = 0; k < 20; k++) { const a0 = (k / 20) * Math.PI * 2, a1 = ((k + 1) / 20) * Math.PI * 2; ring.push(p.x + Math.cos(a0) * 1.1, p.y + 5, p.z + Math.sin(a0) * 1.1, p.x + Math.cos(a1) * 1.1, p.y + 5, p.z + Math.sin(a1) * 1.1); }
    scene.add(segs([p.x, p.y, p.z, p.x, p.y + 5, p.z, ...ring], mInk));
    wps.push(V(p.x, p.y + 5, p.z));
  }

  // ------------------------------------------------------------ stations: one camera path through the whole page
  const C = V(0, PH.y, 0);
  const around = (target: THREE.Vector3, off: THREE.Vector3, occ: number, fov: number): Station => {
    const o = off.clone().applyAxisAngle(V(0, 1, 0), (occ * 28 * Math.PI) / 180);
    return { pos: target.clone().add(o), target: target.clone(), fov };
  };
  const ortho = (target: THREE.Vector3, dir: THREE.Vector3, fov: number, height: number): Station => {
    const d = height / 2 / Math.tan((fov * Math.PI) / 360);
    return { pos: target.clone().add(dir.clone().normalize().multiplyScalar(d)), target: target.clone(), fov };
  };
  const stations: Station[] = [];
  const featCenter = V(0, PH.y, -1 + (Math.max(5, nFeat) - 1) * 1.2);
  secs.forEach((s) => {
    s.a = stations.length;
    switch (s.kind) {
      case "hero": stations.push(around(C, V(15, 4.5, 27), s.occ, 38)); break;
      case "intro": stations.push(ortho(C.clone().add(V(0, 0, 0)), V(0, 0.08, 1), 9, 21)); break;
      case "features": {
        const n = Math.max(1, nFeat);
        for (let j = 0; j < n; j++) stations.push(around(featCenter, V(-26, 6, 18).applyAxisAngle(V(0, 1, 0), (j - (n - 1) / 2) * 0.12), s.occ, 40));
        break;
      }
      case "product": stations.push(around(V(1.5, PH.y + 0.2, 0), V(9, 2.5, 27), s.occ, 34)); break;
      case "stats": {
        const n = Math.max(1, s.dims.length);
        const at = yards.get(s)!.at;
        stations.push({ pos: V(at.x + ((n - 1) * 5.2) / 2 + 1.5, 6, at.z).add(V(4, 7, 30 + n * 2)), target: V(at.x + ((n - 1) * 5.2) / 2 + 1.5, 6, at.z), fov: 38 });
        break;
      }
      case "timeline": wps.forEach((w) => stations.push({ pos: w.clone().add(V(-10, 9, 16)), target: w.clone().add(V(0, -2, 0)), fov: 42 })); break;
      case "quote": stations.push(around(V(-1.4, PH.y + 4.6, -0.6), V(-9, 3, -16), s.occ, 36)); break;
      case "faq": stations.push({ pos: V(30, 112, 24), target: V(30, 0, 20), fov: 40 }); break;
      case "cta": stations.push(around(V(-3, PH.y - 0.5, 0), V(17, 6, 31), s.occ, 36)); break;
      default: stations.push(around(V(-26, 4, 20), V(10, 8, 22), s.occ, 40));
    }
    s.b = stations.length - 1;
  });
  const posCurve = new THREE.CatmullRomCurve3(stations.map((s) => s.pos), false, "centripetal", 0.5);
  const tgtCurve = new THREE.CatmullRomCurve3(stations.map((s) => s.target), false, "centripetal", 0.5);
  if (stations.length === 1) { posCurve.points.push(stations[0].pos.clone()); tgtCurve.points.push(stations[0].target.clone()); }
  const NS = Math.max(2, posCurve.points.length);

  // ------------------------------------------------------------ layout
  let W = innerWidth, H = innerHeight, mobile = false, distK = 1;
  function layout() {
    W = innerWidth; H = innerHeight; mobile = W <= 760;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, mobile ? 1.5 : 1.75));
    renderer.setSize(W, H, false);
    camera.aspect = W / H;
    // portrait screens: pull back to keep the subject's width, and lift the image centre above the bottom callout
    distK = W / H < 1 ? Math.pow(1 / (W / H), 0.7) : 1;
    if (mobile) camera.setViewOffset(W, H, 0, H * 0.2, W, H); else camera.clearViewOffset();
    camera.updateProjectionMatrix();
    mats.forEach((m) => m.resolution.set(W, H));
    hud.setAttribute("viewBox", `0 0 ${W} ${H}`);
    secs.forEach((s, k) => {
      const n = s.b - s.a + 1;
      const screens = s.kind === "hero" ? 1.3 : s.kind === "faq" ? 1.8 : s.kind === "stats" ? 1.7 : s.kind === "product" ? 1.9 : s.kind === "cta" ? 1.7 : 1.3 + (n - 1) * 0.65;
      s.el.style.setProperty("--len", screens.toFixed(2));
      s.travel = k === 0 ? 0 : Math.min(0.42, 0.75 / screens);
    });
    secs.forEach((s) => { const r = s.el.getBoundingClientRect(); s.top = r.top + scrollY; s.len = Math.max(1, r.height); });
    // a long headline shrinks until it fits its callout
    $$<HTMLElement>(".wf-head").forEach((h) => {
      h.style.fontSize = "";
      let fs = parseFloat(getComputedStyle(h).fontSize), guard = 0;
      while (h.offsetHeight > H * (mobile ? 0.26 : 0.4) && fs > 24 && guard++ < 30) { fs *= 0.93; h.style.fontSize = fs + "px"; }
    });
    dirty = true;
  }

  // ------------------------------------------------------------ scroll -> camera
  interface Cam { u: number; si: number; q: number; stop: number; arrived: number }
  function camAt(y: number): Cam {
    let si = 0;
    for (let k = 0; k < secs.length; k++) if (y >= secs[k].top - 1) si = k;
    const s = secs[si], q = clamp((y - s.top) / s.len), n = s.b - s.a + 1;
    const prevB = si > 0 ? secs[si - 1].b : s.a;
    if (q < s.travel) {
      const t = q / s.travel;
      if (reduced) return { u: t < 0.5 ? prevB : s.a, si: t < 0.5 ? si - 1 : si, q, stop: 0, arrived: t < 0.5 ? 1 : 0 };
      return { u: lerp(prevB, s.a, smooth(t)), si, q, stop: 0, arrived: t };
    }
    const r = ((q - s.travel) / Math.max(1e-6, 1 - s.travel)) * n;
    const j = Math.min(n - 1, Math.floor(r)), f = r - j;
    let u = s.a + j;
    if (j > 0 && f < 0.35 && !reduced) u = s.a + j - 1 + smooth(f / 0.35);
    return { u, si, q, stop: j, arrived: 1 };
  }

  // ------------------------------------------------------------ pointer: probe, highlight, drag-orbit
  const ray = new THREE.Raycaster(), mouse = new THREE.Vector2(-9, -9), groundPl = new THREE.Plane(V(0, 1, 0), 0);
  let hoverPart: Part | null = null, dragging = false, dragX = 0, dragY = 0, yaw = 0, pitch = 0;
  const probe = $<HTMLElement>("[data-probe]");
  addEventListener("pointermove", (e) => {
    mouse.set((e.clientX / W) * 2 - 1, -(e.clientY / H) * 2 + 1);
    if (dragging) { yaw = clamp(yaw - (e.clientX - dragX) * 0.004, -0.4, 0.4); pitch = clamp(pitch + (e.clientY - dragY) * 0.003, -0.25, 0.25); dragX = e.clientX; dragY = e.clientY; }
    probeDirty = true; dirty = true;
  }, { passive: true });
  canvas.addEventListener("pointerdown", (e) => { if (e.pointerType !== "mouse") return; dragging = true; dragX = e.clientX; dragY = e.clientY; });
  addEventListener("pointerup", () => { dragging = false; });
  let probeDirty = false;
  function runProbe() {
    if (!probeDirty) return;
    probeDirty = false;
    ray.setFromCamera(mouse, camera);
    const hit = ray.intersectObjects(parts.map((p) => p.occ), false)[0];
    const p = hit ? parts.find((pt) => pt.occ === hit.object) || null : null;
    if (p !== hoverPart) { if (hoverPart) hoverPart.edges.material = mInk; hoverPart = p; dirty = true; }
    const gp = new THREE.Vector3();
    if (probe && ray.ray.intersectPlane(groundPl, gp)) probe.textContent = `X ${gp.x.toFixed(2)} · Z ${gp.z.toFixed(2)}`;
  }

  // ------------------------------------------------------------ toolbar, title block, gizmo
  const tb = { view: $<HTMLElement>('[data-tb="view"]'), scale: $<HTMLElement>('[data-tb="scale"]'), sheet: $<HTMLElement>('[data-tb="sheet"]'), rev: $<HTMLElement>('[data-tb="rev"]') };
  const views = $$<HTMLElement>(".wf-bar__views [data-k]");
  const gx = $<SVGLineElement>(".wf-gizmo .ax-x"), gy = $<SVGLineElement>(".wf-gizmo .ax-y"), gz = $<SVGLineElement>(".wf-gizmo .ax-z");
  const gtx = $<SVGTextElement>(".wf-gizmo .t-x"), gty = $<SVGTextElement>(".wf-gizmo .t-y"), gtz = $<SVGTextElement>(".wf-gizmo .t-z");
  function settledY(k: number) { const s = secs[k]; return s ? s.top + s.len * s.travel + 2 : 0; }
  function go(y: number) {
    const from = scrollY, t0 = performance.now(), dur = Math.min(1700, 500 + Math.abs(y - from) * 0.06);
    const step = (now: number) => { const k = clamp((now - t0) / dur); scrollTo(0, from + (y - from) * smooth(k)); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  views.forEach((v) => v.addEventListener("click", (e) => { e.preventDefault(); e.stopImmediatePropagation(); go(settledY(+(v.dataset.k || 0))); }, true));
  addEventListener("click", (e) => {
    const a = (e.target as Element).closest?.("a[href^='#']") as HTMLAnchorElement | null;
    if (!a || a.closest(".wf-bar__views")) return;
    const id = a.getAttribute("href")!;
    const k = id.length > 1 ? secs.findIndex((s) => "#" + s.el.id === id) : 0;
    if (k < 0) return;
    e.preventDefault(); e.stopImmediatePropagation();
    go(id.length > 1 ? settledY(k) : 0);
  }, true);

  // ------------------------------------------------------------ frame
  const t0 = performance.now(), startTop = scrollY < 10;
  let dirty = true, lastY = -1, lastStation = -1, fadeT = 0;
  const tmp = new THREE.Vector3();
  const toScreen = (v: THREE.Vector3): [number, number, boolean] => { tmp.copy(v).project(camera); return [(tmp.x * 0.5 + 0.5) * W, (-tmp.y * 0.5 + 0.5) * H, tmp.z < 1]; };

  function frame(y: number) {
    const now = performance.now();
    const intro = !reduced && startTop ? clamp((now - t0 - 200) / 1700) : 1;
    const springing = !dragging && (Math.abs(yaw) > 1e-4 || Math.abs(pitch) > 1e-4);
    if (y === lastY && !dirty && intro >= 1 && !springing && fadeT <= 0) return;
    lastY = y; dirty = false;
    if (springing) { yaw *= 0.9; pitch *= 0.9; }
    const c = camAt(y);
    const s = secs[c.si];
    // reduced motion: a 200 ms dip to black on every station change instead of flying
    if (reduced) {
      const st = Math.round(c.u);
      if (st !== lastStation) { if (lastStation >= 0) { fadeT = 1; canvas.style.transition = "none"; canvas.style.opacity = "0"; requestAnimationFrame(() => { canvas.style.transition = "opacity .2s linear"; canvas.style.opacity = "1"; }); } lastStation = st; }
      fadeT = 0;
    }
    const tu = c.u / Math.max(1, NS - 1);
    const pos = posCurve.getPoint(clamp(tu)), tgt = tgtCurve.getPoint(clamp(tu));
    const i0 = Math.floor(c.u), i1 = Math.min(stations.length - 1, i0 + 1);
    camera.fov = lerp(stations[Math.min(i0, stations.length - 1)].fov, stations[i1].fov, c.u - i0);
    // drag-orbit within limits, springing back to the authored path
    const off = pos.clone().sub(tgt).multiplyScalar(distK).applyAxisAngle(V(0, 1, 0), yaw);
    if (off.length() < 15 * distK) off.setLength(15 * distK);   // between stations the path never grazes the model
    const right = V(0, 1, 0).cross(off).normalize();
    off.applyAxisAngle(right, pitch);
    camera.position.copy(tgt).add(off);
    { const away = camera.position.clone().sub(C); const minD = 13 * distK; if (away.length() < minD) camera.position.copy(C).add(away.setLength(minD)); }
    camera.lookAt(tgt);
    camera.updateProjectionMatrix();

    // world state driven by where we are
    const prog = (k: number) => (k === c.si ? c.q : k < c.si ? 1 : 0);
    // exploded view: apart while the features station holds, reassembled by the final assembly
    let explode = 0;
    secs.forEach((sc, k) => {
      if (sc.kind !== "features") return;
      if (k === c.si) explode = Math.max(explode, reduced ? 1 : clamp((c.q - sc.travel * 0.4) / (sc.travel * 0.6 + 0.08)));
      if (k === c.si - 1) explode = Math.max(explode, reduced ? 0 : 1 - smooth(clamp(c.q / Math.max(0.01, secs[c.si].travel))));
    });
    const P = parts.length;
    parts.forEach((p, i) => { p.group.position.z = p.z0 + explode * (P - 1 - i) * 2.5; });
    // render moment: the line drawing solidifies at the product and at the final assembly
    let solid = 0;
    secs.forEach((sc, k) => {
      if (sc.kind !== "product" && sc.kind !== "cta") return;
      if (k === c.si) solid = Math.max(solid, reduced ? 1 : clamp((c.q - sc.travel * 0.7) / 0.22));
      if (k === c.si - 1 && sc.kind === "product") solid = Math.max(solid, reduced ? 0 : 1 - clamp(c.q / Math.max(0.01, secs[c.si].travel * 0.6)));
    });
    parts.forEach((p) => { (p.solid.material as THREE.MeshStandardMaterial).opacity = solid; p.solid.visible = solid > 0.001; });
    screenMat.opacity = solid; screen.visible = solid > 0.001;
    mInk.opacity = 1 - solid * 0.62; mInk.transparent = solid > 0; mDim.opacity = 0.55 * (1 - solid * 0.7);
    // section cut sweeping down the front elevation
    const introK = secs.findIndex((sc) => sc.kind === "intro");
    cutPlane.visible = introK >= 0 && (c.si === introK || (c.si === introK + 1 && c.q < secs[c.si].travel * 0.5));
    if (cutPlane.visible) { const k = c.si === introK ? clamp((c.q - secs[introK].travel) / (1 - secs[introK].travel)) : 1; cutPlane.position.set(0, PH.y + PH.h / 2 - 0.5 - k * (PH.h - 1), 0); }
    // dimension lines grow up the towers
    secs.forEach((sc, k) => {
      const y2 = yards.get(sc);
      if (!y2) return;
      const grow = reduced ? (c.si >= k ? 1 : 0) : k === c.si ? clamp((c.q - sc.travel * 0.8) / 0.25) : k < c.si ? 1 : 0;
      y2.towers.forEach((t, j) => { t.dim.scale.y = Math.max(0.001, clamp(grow * 1.4 - j * 0.12)); });
    });
    // the route: driven part solid, the road ahead dashed
    const tlK = secs.findIndex((sc) => sc.kind === "timeline");
    let route = 0;
    if (tlK >= 0) { const sc = secs[tlK]; route = c.si > tlK ? 1 : c.si < tlK ? 0 : clamp((c.u - sc.a + 0.5) / (sc.b - sc.a + 1)); }
    (routeLine.geometry as any).instanceCount = Math.round(route * (routePts.length - 1));
    // highlighted part: the probed one, else the feature being read
    const featK = secs.findIndex((sc) => sc.kind === "features");
    const activePart = hoverPart ? hoverPart.idx : c.si === featK ? c.stop : -1;
    parts.forEach((p, i) => { p.edges.material = i === activePart ? mHi : mInk; });

    renderer.render(scene, camera);

    // ---------------------------------------------------------- overlay: callouts, leaders, balloons, labels
    let svg = "";
    secs.forEach((sc, k) => {
      let p = 0;
      if (k === c.si) p = reduced ? 1 : clamp((c.q - sc.travel * 0.86) / Math.max(0.03, sc.travel * 0.14 + 0.03));
      if (k === 0 && c.si === 0) p = Math.min(p || 1, intro);
      if (k === c.si - 1 && !reduced) p = 1 - clamp(c.q / Math.max(0.01, secs[c.si].travel * 0.3));
      const on = p > 0.01;
      const call = sc.call;
      if (call) {
        call.classList.toggle("is-on", on);
        if (on) {
          call.style.opacity = (sc.kind === "stats" ? 1 : clamp(p * 2)).toFixed(3);
          call.style.clipPath = p >= 1 || sc.kind === "stats" ? "" : `inset(0 ${((1 - clamp(p * 1.6)) * 100).toFixed(1)}% 0 0)`;
        }
      }
      sc.plots.forEach((pl) => {
        const k2 = clamp((p - 0.15) / 0.65);
        if (k2 === pl.last) return;
        pl.last = k2;
        const n = pl.spans.length;
        pl.spans.forEach((sp, i) => { const v = clamp(k2 * n * 1.15 - i * 1.15 + 1); sp.style.clipPath = v >= 1 ? "" : `inset(0 ${((1 - v) * 100).toFixed(0)}% 0 0)`; });
        pl.el.classList.toggle("is-filled", k2 >= 1);
      });
      if (!on) { sc.dims.forEach((d) => { d.style.visibility = "hidden"; }); return; }
      // leader from the callout to its point on the model
      const anchorName = call?.dataset.anchor;
      const anchor = anchorName ? anchorPoint(anchorName, c.stop) : null;
      if (call && anchor && p > 0.6) {
        const [ax, ay, vis] = toScreen(anchor);
        if (vis) svg += leader(call.getBoundingClientRect(), ax, ay, sc.kind === "features");
      }
      if (sc.kind === "features") {
        sc.rows.forEach((r, j) => r.classList.toggle("is-on", j === c.stop && k === c.si));
        for (let j = 0; j < Math.min(sc.rows.length, parts.length); j++) {
          const pt = parts[j];
          const [bx, by, vis] = toScreen(pt.group.localToWorld(pt.top.clone()));
          if (!vis) continue;
          const isOn = j === c.stop && k === c.si;
          const ox = bx + 34, oy = by - 26 - j * 4;
          svg += `<path class="${isOn ? "acc" : ""}" d="M${bx} ${by} L${ox - 10} ${oy}"/><circle class="dot" cx="${bx}" cy="${by}" r="2"/><circle class="bal${isOn ? " is-on" : ""}" cx="${ox}" cy="${oy}" r="11"/><text class="baltext${isOn ? " is-on" : ""}" x="${ox}" y="${oy + 4}">${j + 1}</text>`;
        }
      }
      if (sc.kind === "timeline") {
        sc.rows.forEach((r, j) => { r.classList.toggle("is-on", j === c.stop); r.classList.toggle("is-ahead", j > c.stop); });
        wps.forEach((w, j) => {
          const [wx, wy, vis] = toScreen(w);
          if (!vis) return;
          svg += `<text x="${wx + 10}" y="${wy - 8}" ${j === c.stop ? 'style="fill:#4da3ff"' : ""}>WP${String(j + 1).padStart(2, "0")}</text>`;
        });
      }
      if (sc.kind === "stats") {
        sc.dims.forEach((d, j) => {
          const t = yards.get(sc)?.towers[j];
          if (!t) { d.style.visibility = "hidden"; return; }
          const [sx, sy, vis] = toScreen(V(t.x, t.h * Math.max(0.001, t.dim.scale.y) * 0.5, t.z));
          const show = vis && t.dim.scale.y > 0.3;
          d.style.visibility = show ? "" : "hidden";
          if (show) d.style.transform = `translate(${(sx + 14).toFixed(1)}px, ${(sy - d.offsetHeight / 2).toFixed(1)}px)`;
          d.style.opacity = clamp((t.dim.scale.y - 0.3) / 0.5).toFixed(3);
        });
      }
    });
    if (hoverPart) {
      const [hx, hy, vis] = toScreen(hoverPart.group.localToWorld(V(-PH.w / 2, PH.h / 2, hoverPart.t)));
      if (vis) svg += `<path class="acc" d="M${hx} ${hy} L${hx - 30} ${hy - 30} H${hx - 60}"/><text x="${hx - 64}" y="${hy - 36}" text-anchor="end" style="fill:#4da3ff">${hoverPart.name} · ${hoverPart.dims}</text>`;
    }
    hud.innerHTML = svg;
    // toolbar, title block, gizmo
    if (tb.view) tb.view.textContent = s.view;
    if (tb.sheet) tb.sheet.textContent = `${c.si + 1} OF ${secs.length}`;
    if (tb.scale) tb.scale.textContent = "1:" + (camera.position.distanceTo(tgt) / 10).toFixed(1);
    if (tb.rev) tb.rev.textContent = "ABCDEFGHJKLMNP"[Math.min(13, c.si)];
    views.forEach((v) => v.classList.toggle("is-on", +(v.dataset.k || -1) === c.si));
    const inv = camera.quaternion.clone().invert();
    const ax = (v: THREE.Vector3, l: SVGLineElement | null, t: SVGTextElement | null) => { const p = v.applyQuaternion(inv); l?.setAttribute("x2", (p.x * 18).toFixed(1)); l?.setAttribute("y2", (-p.y * 18).toFixed(1)); t?.setAttribute("x", (p.x * 23 - 3).toFixed(1)); t?.setAttribute("y", (-p.y * 23 + 3).toFixed(1)); };
    ax(V(1, 0, 0), gx, gtx); ax(V(0, 1, 0), gy, gty); ax(V(0, 0, 1), gz, gtz);
  }
  function anchorPoint(name: string, stop: number): THREE.Vector3 | null {
    switch (name) {
      case "top": return V(PH.w * 0.25, PH.y + PH.h / 2, parts[0].group.position.z + 0.2);
      case "cut": return cutPlane.position.clone().add(V(5.5, 0, 2.5));
      case "screen": return parts[0].group.localToWorld(V(2.2, -1, 0.2));
      case "p0": { const pt = parts[Math.min(stop, parts.length - 1)]; return pt.group.localToWorld(V(-PH.w / 2, 0, pt.t)); }
      case "w0": return wps[Math.min(stop, wps.length - 1)] || null;
      case "bump": return parts[Math.min(4, parts.length - 1)].group.localToWorld(V(-1.6, 5, -0.5));
      case "plan": return V(0, 0.6, 3.5);
    }
    return null;
  }
  function leader(r: DOMRect, ax: number, ay: number, acc: boolean) {
    const right = ax > r.right, left = ax < r.left;
    const x0 = right ? r.right : left ? r.left : r.left + r.width / 2;
    const y0 = right || left ? clamp(ay, r.top + 20, r.bottom - 20) : ay < r.top ? r.top : r.bottom;
    const mx = right ? x0 + 28 : left ? x0 - 28 : x0;
    const my = right || left ? y0 : y0 + (ay < r.top ? -24 : 24);
    return `<path class="${acc ? "acc" : ""}" d="M${x0} ${y0} L${mx} ${my} L${ax} ${ay}"/><circle class="dot" cx="${ax}" cy="${ay}" r="3"/><circle cx="${ax}" cy="${ay}" r="7" style="fill:none"/>`;
  }

  layout();
  addEventListener("resize", () => { layout(); frame(scrollY); });
  document.fonts?.ready.then(() => { layout(); frame(scrollY); });
  onFrame(({ y }) => { runProbe(); frame(y); });
}

/** The app screen as a texture: the page's own device data (app, title, label, note, options, button). */
function drawScreen(): HTMLCanvasElement {
  const cv = document.createElement("canvas");
  cv.width = 620; cv.height = 1320;
  const g = cv.getContext("2d")!;
  g.fillStyle = "#0d1015"; g.fillRect(0, 0, cv.width, cv.height);
  const app = document.querySelector<HTMLElement>("[data-device] .ss-app");
  const txt = (sel: string) => app?.querySelector(sel)?.textContent?.trim() || "";
  const font = (w: number, s: number, fam = "Archivo, sans-serif") => `${w} ${s}px ${fam}`;
  g.fillStyle = "#d9dde3"; g.font = font(500, 26, "JetBrains Mono, monospace"); g.fillText("9:41", 40, 64);
  let y = 150;
  g.fillStyle = "#4da3ff"; g.font = font(500, 26, "JetBrains Mono, monospace"); g.fillText((txt(".ss-app__name") || "APP").toUpperCase(), 40, y); y += 76;
  g.fillStyle = "#ffffff"; g.font = font(700, 60);
  y = wrap(g, txt(".ss-app__title") || "Your screen", 40, y, 540, 66) + 30;
  g.fillStyle = "#9aa3ad"; g.font = font(500, 24, "JetBrains Mono, monospace"); g.fillText((txt(".ss-app__label") || "").toUpperCase(), 40, y); y += 44;
  g.fillStyle = "#c9ced6"; g.font = font(400, 28); y = wrap(g, txt(".ss-app__note"), 40, y, 540, 38) + 34;
  const opts = app ? [...app.querySelectorAll<HTMLElement>(".ss-app__opt")] : [];
  (opts.length ? opts : [null, null, null]).forEach((o) => {
    const on = !!o?.classList.contains("is-on");
    g.strokeStyle = on ? "#4da3ff" : "#3a3f47"; g.lineWidth = on ? 4 : 2;
    g.fillStyle = on ? "rgba(77,163,255,.12)" : "rgba(255,255,255,.03)";
    roundRect(g, 40, y, 540, 130, 22); g.fill(); g.stroke();
    g.fillStyle = on ? "#9cc9ff" : "#e6e9ee"; g.font = font(600, 36); g.fillText(o?.querySelector("b")?.textContent || "—", 70, y + 58);
    g.fillStyle = "#8f98a3"; g.font = font(400, 26); g.fillText(o?.querySelector("small")?.textContent || "", 70, y + 100);
    y += 152;
  });
  const btn = txt(".ss-app__btn");
  if (btn) { g.fillStyle = "#4da3ff"; roundRect(g, 40, cv.height - 190, 540, 110, 55); g.fill(); g.fillStyle = "#04101f"; g.font = font(700, 34); g.textAlign = "center"; g.fillText(btn, 310, cv.height - 122); g.textAlign = "left"; }
  return cv;
}
function wrap(g: CanvasRenderingContext2D, text: string, x: number, y: number, w: number, lh: number) {
  if (!text) return y;
  const words = text.split(/\s+/);
  let line = "";
  for (const wd of words) {
    const t = line ? line + " " + wd : wd;
    if (g.measureText(t).width > w && line) { g.fillText(line, x, y); line = wd; y += lh; } else line = t;
  }
  if (line) { g.fillText(line, x, y); y += lh; }
  return y;
}
function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}
