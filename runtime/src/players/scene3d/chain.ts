/**
 * `chain` preset: a planner (a language model) at the centre hands work to a ring of model stations, and
 * results flow from one station to the next. Each station draws what its model returns, from data in params:
 *
 *   params:
 *     data: chain.json          # optional: fetch the stations from a JSON file next to the page
 *     planner: { label }        # the centre
 *     stations:                 # in pipeline order; the scroll visits them one step each
 *       - { kind: sequence, label, scores: [...] }                  # per-base scores (e.g. a DNA language model)
 *       - { kind: fold,     label, ca: [[x,y,z]...], confidence: [...] }   # backbone, coloured by confidence 0-1
 *       - { kind: complex,  label, ca: [[x,y,z]...], ligand: [[x,y,z]...], bonds: [[i,j]...] }
 *       - { kind: relax,    label, atoms: [[x,y,z]...], energies: [...] }  # energies along the trajectory
 *       - { kind: route,    label, tree: { name, stock?, children: [...] } } # retrosynthesis tree
 *
 * Missing data falls back to a procedural stand-in of the same shape, so a page can be laid out before
 * real outputs exist. Inside scene3d this is meant as the only level: `d` (steps scrolled) picks the station.
 */
import * as THREE from "three";
import { smooth } from "../../lib/util";
import type { Kit, LevelObj } from "./presets";

type V3 = [number, number, number];
const C = (v: any, d: string) => new THREE.Color(v ?? d);
const LOW = new THREE.Color("#ffb45a"), MID = new THREE.Color("#f2f5ff"), HIGH = new THREE.Color("#7fe3ff");
/** confidence 0..1 -> amber (low) .. white .. cyan (high) */
function ramp(x: number, out = new THREE.Color()) {
  const t = Math.min(1, Math.max(0, x));
  return t < 0.5 ? out.copy(LOW).lerp(MID, t * 2) : out.copy(MID).lerp(HIGH, (t - 0.5) * 2);
}
const additive = { transparent: true, depthWrite: false, blending: THREE.AdditiveBlending } as const;

/** centre and scale a point cloud so its largest radius is r */
function fit(pts: V3[], r: number): THREE.Vector3[] {
  const v = pts.map((p) => new THREE.Vector3(p[0], p[1], p[2]));
  const c = v.reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / Math.max(1, v.length));
  const m = Math.max(1e-6, ...v.map((p) => p.distanceTo(c)));
  return v.map((p) => p.sub(c).multiplyScalar(r / m));
}

function textSprite(text: string, color: string, height = 0.55) {
  const pad = 12, fs = 44, cv = document.createElement("canvas"), g = cv.getContext("2d")!;
  g.font = `500 ${fs}px "JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace`;
  cv.width = Math.ceil(g.measureText(text).width) + pad * 2; cv.height = fs + pad * 2;
  g.font = `500 ${fs}px "JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace`;
  g.fillStyle = color; g.textBaseline = "middle"; g.fillText(text, pad, cv.height / 2);
  const tex = new THREE.CanvasTexture(cv); tex.anisotropy = 4;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, opacity: 0.9 }));
  s.scale.set(height * cv.width / cv.height, height, 1);
  return s;
}

/** vertex-coloured tube through pts, colour per point */
function colourTube(pts: THREE.Vector3[], cols: THREE.Color[], r: number, opacity = 0.95) {
  const tubular = Math.max(32, pts.length * 4), radial = 6;
  const geo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), tubular, r, radial);
  const n = geo.attributes.position.count, out = new Float32Array(n * 3), tmp = new THREE.Color();
  for (let j = 0; j < n; j++) {
    const u = Math.floor(j / (radial + 1)) / tubular, x = u * (cols.length - 1), i = Math.floor(x);
    tmp.copy(cols[Math.min(i, cols.length - 1)]).lerp(cols[Math.min(i + 1, cols.length - 1)], x - i);
    out.set([tmp.r, tmp.g, tmp.b], j * 3);
  }
  geo.setAttribute("color", new THREE.BufferAttribute(out, 3));
  return new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, opacity, ...additive }));
}

// ---------------------------------------------------------------- stand-ins (layout before real data)

function standInBackbone(k: Kit, n = 90): V3[] {
  const out: V3[] = []; let p = new THREE.Vector3(), dir = new THREE.Vector3(1, 0, 0);
  for (let i = 0; i < n; i++) {
    const helixPart = Math.floor(i / 14) % 2 === 0;
    if (helixPart) { const a = i * 1.75; out.push([p.x + Math.cos(a) * 0.9, p.y + i * 0.06, p.z + Math.sin(a) * 0.9]); p.add(dir.clone().multiplyScalar(0.25)); }
    else { dir.applyAxisAngle(new THREE.Vector3(k.rnd(-1, 1), k.rnd(-1, 1), k.rnd(-1, 1)).normalize(), 0.6); p.add(dir.clone().multiplyScalar(1.1)); out.push([p.x, p.y, p.z]); }
  }
  return out;
}
const standInTree = { name: "target", children: [
  { name: "a", children: [{ name: "a1", stock: true }, { name: "a2", stock: true }] },
  { name: "b", children: [{ name: "b1", stock: true }, { name: "b2", children: [{ name: "b21", stock: true }, { name: "b22", stock: true }] }] }] };

// ---------------------------------------------------------------- stations

interface Station { group: THREE.Group; anchor: THREE.Vector3; update(t: number, w: number): void; label?: THREE.Sprite }

function sequenceStation(s: any, k: Kit): Station {
  const g = new THREE.Group();
  const raw: number[] = s.scores?.length ? s.scores : Array.from({ length: 72 }, () => k.rnd(-2.2, -0.4));
  const n = Math.min(raw.length, 96), xs = raw.slice(0, n), lo = Math.min(...xs), hi = Math.max(...xs);
  const L = 6.4, R = 0.55, turn = (2 * Math.PI) / 10.5;
  const strand = (off: number) => Array.from({ length: n * 3 + 1 }, (_, i) => { const t = i / 3, a = t * turn + off; return new THREE.Vector3((t / n - 0.5) * L, Math.cos(a) * R, Math.sin(a) * R); });
  for (const off of [0, Math.PI * 0.8]) g.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(strand(off)), n * 4, 0.045, 5),
    new THREE.MeshBasicMaterial({ color: 0x9fb6d8, opacity: 0.55, ...additive })));
  const pos: number[] = [], cols: number[] = [], tmp = new THREE.Color();
  xs.forEach((v, i) => {
    const t = i, a = t * turn, x = (t / n - 0.5) * L;
    pos.push(x, Math.cos(a) * R, Math.sin(a) * R, x, Math.cos(a + Math.PI * 0.8) * R, Math.sin(a + Math.PI * 0.8) * R);
    ramp((v - lo) / Math.max(1e-6, hi - lo), tmp); cols.push(tmp.r, tmp.g, tmp.b, tmp.r, tmp.g, tmp.b);
  });
  const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3));
  g.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, opacity: 1, ...additive })));
  // a read head that sweeps along the sequence while the station is active
  const head = k.sprite(0xffffff, 0.9, 0.9); g.add(head);
  g.rotation.z = 0.35;
  return { group: g, anchor: new THREE.Vector3(), update(t, w) {
    g.rotation.x = t * 0.25;
    head.position.set(((t * 0.18) % 1 - 0.5) * L, 0, 0); head.visible = w > 0.2;
  } };
}

function foldStation(s: any, k: Kit): Station {
  const g = new THREE.Group();
  const ca = fit(s.ca?.length ? s.ca : standInBackbone(k), 2.6);
  const conf: number[] = s.confidence?.length ? s.confidence : ca.map((_, i) => 0.55 + 0.4 * Math.sin(i * 0.21) ** 2);
  const cols = ca.map((_, i) => ramp(conf[Math.min(i, conf.length - 1)]));
  g.add(colourTube(ca, cols, 0.085));
  g.add(k.points(ca.length, (i) => ca[i], 0xffffff, 0.16, 0.8, (i) => cols[i]));
  return { group: g, anchor: new THREE.Vector3(), update(t) { g.rotation.set(0.3, t * 0.18, 0); } };
}

function standInGlobule(k: Kit, n = 130): V3[] {
  // a compact chain: a random walk kept inside a sphere, the shape a folded protein has from far away
  const out: V3[] = []; const p = new THREE.Vector3(), dir = new THREE.Vector3(1, 0, 0);
  for (let i = 0; i < n; i++) {
    dir.add(new THREE.Vector3(k.rnd(-1, 1), k.rnd(-1, 1), k.rnd(-1, 1)).multiplyScalar(0.9)).normalize();
    if (p.length() > 2.4) dir.add(p.clone().normalize().multiplyScalar(-1.2)).normalize();
    p.add(dir.clone().multiplyScalar(0.75)); out.push([p.x, p.y, p.z]);
  }
  return out;
}

function ballAndStick(k: Kit, atoms: THREE.Vector3[], bonds: [number, number][], color: number | string, r: number) {
  const g = new THREE.Group(), m = new THREE.Matrix4(), q = new THREE.Quaternion(), one = new THREE.Vector3(1, 1, 1);
  const balls = new THREE.InstancedMesh(new THREE.SphereGeometry(r, 18, 12), k.glow(color, { power: 1.0, base: 0.5, intensity: 1.1 }), atoms.length);
  atoms.forEach((a, i) => balls.setMatrixAt(i, m.compose(a, q, one))); g.add(balls);
  bonds.forEach(([i, j]) => { if (!atoms[i] || !atoms[j]) return;
    const d = atoms[j].clone().sub(atoms[i]), c = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.32, r * 0.32, d.length(), 8), k.glow(color, { power: 0.8, base: 0.4, intensity: 0.6 }));
    c.position.copy(atoms[i].clone().add(atoms[j]).multiplyScalar(0.5)); c.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()); g.add(c); });
  return g;
}

function complexStation(s: any, k: Kit): Station {
  const g = new THREE.Group(), body = new THREE.Group(); g.add(body);
  const all = [...(s.ca?.length ? s.ca : standInGlobule(k)), ...(s.ligand ?? [])] as V3[];
  const fitted = fit(all, 2.6), nCa = all.length - (s.ligand?.length ?? 0);
  const ca = fitted.slice(0, nCa);
  body.add(colourTube(ca, ca.map((_, i) => new THREE.Color("#5d7bb0").lerp(new THREE.Color("#9fc2ff"), (i % 17) / 34)), 0.1, 0.75));
  body.add(k.sprite(0x5b8cff, 7.5, 0.12));                      // a faint envelope, the protein's surface from afar
  let lig = fitted.slice(nCa), bonds: [number, number][] = s.bonds ?? [];
  if (!lig.length) {
    // stand-in ligand: a six-ring with two substituents, seated in a pocket on the surface
    const out = ca.reduce((a, b) => (b.length() > a.length() ? b : a)).clone().multiplyScalar(0.72);
    lig = Array.from({ length: 6 }, (_, i) => new THREE.Vector3(Math.cos(i * Math.PI / 3) * 0.5, Math.sin(i * Math.PI / 3) * 0.5, 0));
    lig.push(new THREE.Vector3(1.0, 0, 0.1), new THREE.Vector3(-1.0, 0, -0.1), new THREE.Vector3(1.5, 0.4, 0.2));
    lig = lig.map((a) => a.add(out));
    bonds = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], [0, 6], [3, 7], [6, 8]];
  } else if (!bonds.length) bonds = lig.map((_, i) => [i, i + 1] as [number, number]).slice(0, -1);
  const ligC = lig.reduce((a, b) => a.clone().add(b), new THREE.Vector3()).multiplyScalar(1 / lig.length);
  const ligand = ballAndStick(k, lig.map((a) => a.clone().sub(ligC)), bonds, "#45f0a0", 0.2); body.add(ligand);
  const pocket = k.sprite(0x45f0a0, 2.4, 0); pocket.position.copy(ligC); body.add(pocket);
  const start = ligC.clone().add(ligC.clone().normalize().multiplyScalar(3.2)).add(new THREE.Vector3(0, 1.2, 0));
  return { group: g, anchor: new THREE.Vector3(), update(t, w) {
    body.rotation.set(0.25, t * 0.1, 0);
    const dock = smooth(0.3, 0.9, w);
    ligand.position.lerpVectors(start, ligC, dock);
    ligand.rotation.set(t * 0.8 * (1 - dock), t * 0.6 * (1 - dock), 0);
    (pocket.material as THREE.SpriteMaterial).opacity = smooth(0.8, 1, dock) * (0.45 + 0.2 * Math.sin(t * 3));
  } };
}

function relaxStation(s: any, k: Kit): Station {
  const g = new THREE.Group(), crystal = new THREE.Group(); g.add(crystal);
  let atoms: THREE.Vector3[];
  if (s.atoms?.length) atoms = fit(s.atoms, 1.9);
  else { atoms = []; for (let x = -1; x <= 1; x++) for (let y = -1; y <= 1; y++) for (let z = -1; z <= 1; z++) atoms.push(new THREE.Vector3(x, y, z).multiplyScalar(1.05)); }
  const E: number[] = s.energies?.length ? s.energies : Array.from({ length: 40 }, (_, i) => -3 - 1.6 * (1 - Math.exp(-i / 7)) + 0.06 * Math.sin(i * 1.3) * Math.exp(-i / 10));
  // atoms start strained and settle onto their relaxed positions as the station is read
  const strain = atoms.map(() => new THREE.Vector3(k.rnd(-1, 1), k.rnd(-1, 1), k.rnd(-1, 1)).multiplyScalar(0.42));
  const balls = new THREE.InstancedMesh(new THREE.SphereGeometry(0.19, 18, 12), k.glow("#9fc2ff", { power: 1.1, base: 0.4, intensity: 1.0 }), atoms.length);
  crystal.add(balls);
  const pairs: [number, number][] = [];
  const step = Math.min(...atoms.flatMap((a, i) => atoms.slice(i + 1).map((b) => a.distanceTo(b)))) * 1.15;
  atoms.forEach((a, i) => atoms.forEach((b, j) => { if (i < j && a.distanceTo(b) < step) pairs.push([i, j]); }));
  const bpos = new Float32Array(pairs.length * 6), bgeo = new THREE.BufferGeometry(); bgeo.setAttribute("position", new THREE.BufferAttribute(bpos, 3));
  crystal.add(new THREE.LineSegments(bgeo, new THREE.LineBasicMaterial({ color: 0x5b8cff, opacity: 0.7, ...additive })));
  crystal.position.x = -2.1;
  // the energy falling as it relaxes, drawn beside the crystal
  const lo = Math.min(...E), hi = Math.max(...E), W = 2.6, H = 2.2, x0 = 0.2;
  const trace = E.map((e, i) => new THREE.Vector3(x0 + (i / Math.max(1, E.length - 1)) * W, ((e - lo) / Math.max(1e-6, hi - lo) - 0.5) * H, 0));
  const dots = k.points(trace.length, (i) => trace[i], 0x45f0a0, 0.22, 1); g.add(dots);
  const tg = new THREE.BufferGeometry().setFromPoints(trace);
  g.add(new THREE.Line(tg, new THREE.LineBasicMaterial({ color: 0x45f0a0, opacity: 0.9, ...additive })));
  const axis = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x0, H / 2 + 0.2, 0), new THREE.Vector3(x0, -H / 2 - 0.25, 0), new THREE.Vector3(x0 + W, -H / 2 - 0.25, 0)]);
  g.add(new THREE.Line(axis, new THREE.LineBasicMaterial({ color: 0x4a5d7c, opacity: 0.9, ...additive })));
  const head = k.sprite(0x45f0a0, 1.0, 1); g.add(head);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), one = new THREE.Vector3(1, 1, 1), cur = atoms.map((a) => a.clone());
  return { group: g, anchor: new THREE.Vector3(), update(t, w) {
    const prog = smooth(0.15, 0.95, w), left = (1 - prog) ** 1.5;
    atoms.forEach((a, i) => { cur[i].copy(a).addScaledVector(strain[i], left).addScalar(Math.sin(t * 5 + i) * 0.015); balls.setMatrixAt(i, m.compose(cur[i], q, one)); });
    balls.instanceMatrix.needsUpdate = true;
    pairs.forEach(([i, j], n) => bpos.set([cur[i].x, cur[i].y, cur[i].z, cur[j].x, cur[j].y, cur[j].z], n * 6));
    bgeo.attributes.position.needsUpdate = true;
    crystal.rotation.set(0.45, 0.6 + t * 0.12, 0);
    const shown = Math.max(2, Math.round(prog * E.length)); tg.setDrawRange(0, shown); dots.geometry.setDrawRange(0, shown);
    head.position.copy(trace[Math.min(shown, trace.length) - 1]);
  } };
}

function routeStation(s: any, k: Kit): Station {
  const g = new THREE.Group();
  const tree = s.tree ?? standInTree;
  // tidy layout: leaves spread evenly, parents centred over their children, depth goes down
  const nodes: { p: THREE.Vector3; stock: boolean; depth: number }[] = [], edges: [THREE.Vector3, THREE.Vector3][] = [];
  let leaf = 0;
  const depthOf = (n: any): number => 1 + Math.max(0, ...(n.children ?? []).map(depthOf));
  const leaves = (n: any): number => (n.children?.length ? n.children.map(leaves).reduce((a: number, b: number) => a + b, 0) : 1);
  const D = depthOf(tree), Lv = leaves(tree), Wd = Math.min(5.5, 0.9 * Lv), Hd = Math.min(4.2, 1.3 * (D - 1));
  const place = (n: any, depth: number): THREE.Vector3 => {
    let x: number;
    if (n.children?.length) { const kids = n.children.map((c: any) => place(c, depth + 1)); x = kids.reduce((a: number, b: THREE.Vector3) => a + b.x, 0) / kids.length;
      const me = new THREE.Vector3(x, Hd / 2 - (depth / Math.max(1, D - 1)) * Hd, 0); kids.forEach((c: THREE.Vector3) => edges.push([me, c])); nodes.push({ p: me, stock: !!n.stock, depth }); return me; }
    x = Lv > 1 ? (leaf++ / (Lv - 1) - 0.5) * Wd : 0;
    const me = new THREE.Vector3(x, Hd / 2 - (depth / Math.max(1, D - 1)) * Hd, 0); nodes.push({ p: me, stock: n.stock !== false, depth }); return me;
  };
  place(tree, 0);
  const white = new THREE.Color("#f2f5ff"), mint = new THREE.Color("#45f0a0");
  g.add(k.points(nodes.length, (i) => nodes[i].p, 0, 1.25, 1, (i) => (nodes[i].stock ? mint : white)));
  nodes.forEach((nd) => { const h = k.sprite(nd.stock ? 0x45f0a0 : 0xffffff, nd.depth === 0 ? 1.6 : 0.7, 0.35); h.position.copy(nd.p); g.add(h); });
  const ep: number[] = []; edges.forEach(([a, b]) => { const m = new THREE.Vector3(b.x, a.y, 0); ep.push(a.x, a.y, 0, m.x, m.y, 0, m.x, m.y, 0, b.x, b.y, 0); });
  const eg = new THREE.BufferGeometry(); eg.setAttribute("position", new THREE.Float32BufferAttribute(ep, 3));
  const lines = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: 0xc4d4ee, opacity: 1, ...additive })); g.add(lines);
  const segs = ep.length / 6;
  return { group: g, anchor: new THREE.Vector3(), update(t, w) {
    // the route resolves from the target down to the building blocks
    eg.setDrawRange(0, Math.max(0, Math.round(smooth(0.05, 0.9, Math.max(w, 0.25)) * segs)) * 2);
    g.rotation.y = Math.sin(t * 0.3) * 0.25;
  } };
}

const BUILDERS: Record<string, (s: any, k: Kit) => Station> = {
  sequence: sequenceStation, fold: foldStation, complex: complexStation, relax: relaxStation, route: routeStation,
};

// ---------------------------------------------------------------- the planner and the ring

export async function chain(p: any, k: Kit): Promise<LevelObj> {
  if (typeof p.data === "string") {
    try { p = { ...p, ...(await (await fetch(p.data)).json()) }; } catch (e) { console.warn(`[scene3d] chain data ${p.data}`, e); }
  }
  const root = new THREE.Group(), world = new THREE.Group(); root.add(world);
  const violet = C(p.planner?.color, "#a98bff"), mint = C(p.flow, "#45f0a0");
  const specs: any[] = p.stations?.length ? p.stations : [{ kind: "sequence" }, { kind: "fold" }, { kind: "complex" }, { kind: "relax" }, { kind: "route" }];

  // planner: a sphere of tokens with a bright core
  const planner = new THREE.Group(); world.add(planner);
  const N = 1400, golden = Math.PI * (3 - Math.sqrt(5));
  const shell = k.points(N, (i) => { const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), a = i * golden; return new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r).multiplyScalar(1.6 + k.rnd(-0.08, 0.08)); },
    0, 0.09, 0.85, () => violet.clone().lerp(new THREE.Color("#ffffff"), k.rnd(0, 0.35)));
  planner.add(shell);
  const core = k.sprite(violet.getHex(), 3.4, 0.9); planner.add(core);
  const ringPts = Array.from({ length: 129 }, (_, i) => { const a = (i / 128) * Math.PI * 2; return new THREE.Vector3(Math.cos(a) * 2.3, 0, Math.sin(a) * 2.3); });
  const ring = new THREE.Line(new THREE.BufferGeometry().setFromPoints(ringPts), new THREE.LineBasicMaterial({ color: violet, opacity: 0.5, ...additive }));
  ring.rotation.x = 1.2; planner.add(ring);
  const pl = textSprite(p.planner?.label ?? "planner", "#cdbfff", 0.5); pl.position.set(0, -2.7, 0); planner.add(pl);

  // stations on a tilted ring around the planner
  const R = p.radius ?? 6.9, n = specs.length;
  const stations = specs.map((s, i) => {
    const st = (BUILDERS[s.kind] ?? foldStation)(s, k);
    const a = -Math.PI / 2 - Math.PI * 0.18 + (i / n) * Math.PI * 2;
    st.anchor.set(Math.cos(a) * R, Math.sin(a) * R * 0.62, Math.sin(a) * R * -0.35);
    st.group.position.copy(st.anchor);
    if (s.label) { st.label = textSprite(s.label, "#c9d6ea", 0.42); st.label.position.copy(st.anchor).add(new THREE.Vector3(0, -3.2, 0.5)); world.add(st.label); }
    world.add(st.group);
    return st;
  });

  // links: planner -> each station (dispatch), station i -> station i+1 (results)
  const curve = (a: THREE.Vector3, b: THREE.Vector3, lift: number) => new THREE.QuadraticBezierCurve3(a, a.clone().lerp(b, 0.5).add(new THREE.Vector3(0, lift, 2)), b);
  const dispatch = stations.map((s) => curve(new THREE.Vector3(), s.anchor, 1.5));
  const results = stations.slice(0, -1).map((s, i) => curve(s.anchor, stations[i + 1].anchor, -1.2));
  const lineOf = (c: THREE.Curve<THREE.Vector3>, color: THREE.Color, op: number) => {
    const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(c.getPoints(64)), new THREE.LineBasicMaterial({ color, opacity: op, ...additive }));
    world.add(l); return l;
  };
  const dispatchLines = dispatch.map((c) => lineOf(c, violet, 0.12));
  const resultLines = results.map((c) => lineOf(c, mint, 0.18));
  const packets = [...dispatch.map((c, i) => ({ c, i, kind: "d" as const })), ...results.map((c, i) => ({ c, i, kind: "r" as const }))]
    .flatMap((q) => Array.from({ length: 3 }, (_, j) => { const s = k.sprite(q.kind === "d" ? violet.getHex() : mint.getHex(), 0.45, 0.9); world.add(s); return { ...q, s, off: j / 3 }; }));

  // dim every station's materials around their base opacity
  const baseOf = new Map<any, number>();
  const dim = (o: THREE.Object3D, kf: number) => o.traverse((x: any) => { const m = x.material; if (!m) return;
    for (const mm of Array.isArray(m) ? m : [m]) { if (!baseOf.has(mm)) baseOf.set(mm, mm.opacity ?? 1); mm.opacity = baseOf.get(mm)! * kf; mm.transparent = true; } });

  const focus = new THREE.Vector3(), tmp = new THREE.Vector3();
  return {
    group: root,
    update(t, _fin, d) {
      // d counts the steps scrolled; a step's progress is how far the middle of the screen is through its card, so
      // station i is centred at d = i + 0.5. Hold on it while its card is read and glide only as the next card's
      // edge crosses the middle (`glide`, as a fraction of a step); the first station glides in from the overview.
      const e = Math.min(n - 1, d - 0.5), gl = Math.min(0.5, Math.max(0.05, p.glide ?? 0.2));
      const base = Math.round(e), fr = e - base;
      const x = base + (fr > 0.5 - gl ? smooth(0.5 - gl, 0.5, fr) * 0.5 : fr < gl - 0.5 ? -smooth(gl - 0.5, -0.5, fr) * 0.5 : 0);
      const w = stations.map((_, i) => (e < 0 ? (i === 0 ? smooth(-0.5, -0.5 + 2 * gl, e) : 0) : Math.max(0, 1 - Math.abs(x - i))));
      const wsum = w.reduce((a, b) => a + b, 0);
      // glide: the camera's subject moves to the weighted active station and comes closer
      focus.set(0, 0, 0); stations.forEach((s, i) => focus.add(tmp.copy(s.anchor).multiplyScalar(w[i])));
      if (wsum > 0) focus.multiplyScalar(Math.min(1, wsum) / wsum);
      // tall screens (phones) see less of the ring across, so everything is drawn smaller there
      const fitW = Math.max(0.5, Math.min(1, innerWidth / Math.max(1, innerHeight) / 1.25));
      const zoom = ((p.overview ?? 1.12) + (2.3 - (p.overview ?? 1.12)) * smooth(0, 1, Math.min(1, wsum))) * fitW, outer = 1 + 0.1 * Math.max(d, 0);   // scene3d scales the last level by `outer`
      world.scale.setScalar(zoom / outer);
      world.position.copy(focus).multiplyScalar(-zoom / outer);
      world.rotation.y = Math.sin(t * 0.05) * 0.06;
      planner.rotation.y = t * 0.12; ring.rotation.z = t * 0.3;
      (core.material as THREE.SpriteMaterial).opacity = 0.75 + 0.2 * Math.sin(t * 2.2);
      const f = smooth(0, 1, Math.min(1, wsum));
      stations.forEach((s, i) => {
        s.update(t, w[i]); dim(s.group, 0.7 * (1 - f) + f * (0.1 + 0.9 * w[i]));
        if (s.label) (s.label.material as THREE.SpriteMaterial).opacity = 0.75 * (1 - f) + f * smooth(0.55, 0.95, w[i]);
      });
      dim(planner, 1 - 0.7 * f); (pl.material as THREE.SpriteMaterial).opacity = 0.9 * (1 - f);
      dispatchLines.forEach((l, i) => dim(l, 0.6 + 3.5 * w[i]));
      resultLines.forEach((l, i) => dim(l, 0.6 + 3 * Math.max(w[i], w[i + 1] ?? 0)));
      for (const q of packets) {
        const lit = q.kind === "d" ? w[q.i] : Math.max(w[q.i], w[q.i + 1] ?? 0), idle = 0.35 * (1 - f) + 0.08 * f;
        q.s.position.copy(q.c.getPoint((t * 0.35 + q.off) % 1));
        (q.s.material as THREE.SpriteMaterial).opacity = idle + (1 - idle) * lit;
      }
    },
  };
}
