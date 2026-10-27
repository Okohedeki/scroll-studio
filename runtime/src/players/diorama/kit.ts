/**
 * The prop kit: every thing a diorama is made of, drawn from primitives with toy proportions (chunky, a little
 * too saturated, windows and doors a bit too big). A builder draws one prop in its own frame: origin at the middle of
 * its base, front towards +z, one unit about a metre of the toy. Animated parts (blades, boats, flags, beams) are
 * separate objects added through ctx.part / ctx.add; everything else is baked into the world's few big meshes.
 */
import * as THREE from "three";
import { Mesher, PAT, hash, shade } from "./mesher";
import type { PropRec } from "./types";
import { KIT2 } from "./kit2";
import { KIT3 } from "./kit3";

export interface KitCtx {
  M: Mesher;
  p: PropRec;
  palette: string[];
  pick<T>(arr: T[], salt?: number): T;
  rnd(salt?: number): number;
  /** an animated piece: drawn into its own mesher (local frame, origin at the pivot), parented to the world at the prop's local point */
  part(lx: number, ly: number, lz: number, build: (m: Mesher) => void, tick?: (o: THREE.Group, t: number) => void): void;
  /** any object, positioned at a local point of the prop, with an optional animation */
  add(obj: THREE.Object3D, lx: number, ly: number, lz: number, tick?: (o: THREE.Object3D, t: number) => void): void;
  /** a piece drawn in its own frame as a group of meshes in the world's materials (for jointed things built as a hierarchy) */
  meshOf(build: (m: Mesher) => void): THREE.Group;
}
type Builder = (c: KitCtx) => void;

export const WALLS = ["#f4ead8", "#f0dcc0", "#e9efe8", "#f7e3d0", "#efe2c6"];
const GREENS = ["#4f9d45", "#60b04e", "#3f8c47", "#6fb450"];
const WOOD = "#b98550", WOOD_D = "#8b6038", TRIM = "#fbf6ea", STONE = "#bdb6a9", DARK = "#3a3f47", GLASS = "#a9dff0";

const wallOf = (c: KitCtx) => c.p.wall ?? c.pick(WALLS);
const roofOf = (c: KitCtx) => c.p.c?.[0] ?? c.pick(c.palette);

function windowAt(M: Mesher, x: number, y: number, z: number, w: number, h: number, facing = 0, shutters?: string) {
  // a window in a wall: facing 0 = +z face at z, 1 = -z, 2 = +x, 3 = -x
  M.push(); M.at(x, y, z);
  if (facing === 1) M.yaw(Math.PI); else if (facing === 2) M.yaw(Math.PI / 2); else if (facing === 3) M.yaw(-Math.PI / 2);
  M.box(w + 0.1, h + 0.1, 0.05, 0, 0, 0, TRIM);
  M.use("glass"); M.box(w, h, 0.06, 0, 0, 0, GLASS, { ao: false }); M.use("main");
  M.box(0.035, h, 0.075, 0, 0, 0, TRIM); M.box(w, 0.035, 0.075, 0, h * 0.5 - 0.0, 0, TRIM);
  M.box(w + 0.2, 0.05, 0.14, 0, -0.04, 0.03, TRIM);
  if (shutters) { M.box(w * 0.38, h + 0.04, 0.04, -(w / 2 + w * 0.26), 0, 0, shutters); M.box(w * 0.38, h + 0.04, 0.04, (w / 2 + w * 0.26), 0, 0, shutters); }
  M.pop();
}
function doorAt(M: Mesher, x: number, z: number, w: number, h: number, color: string, facing = 0) {
  M.push(); M.at(x, 0, z);
  if (facing === 1) M.yaw(Math.PI); else if (facing === 2) M.yaw(Math.PI / 2); else if (facing === 3) M.yaw(-Math.PI / 2);
  M.box(w + 0.12, h + 0.06, 0.05, 0, 0, 0, TRIM);
  M.box(w, h, 0.07, 0, 0, 0.005, color, { pat: PAT.planks });
  M.sphere(0.025, w * 0.32, h * 0.48, 0.05, "#f2c95a", 6);
  M.box(w + 0.3, 0.07, 0.34, 0, 0, 0.14, STONE);
  M.pop();
}

// ---------------------------------------------------------------- scenery
const tree: Builder = (c) => {
  const M = c.M, v = c.p.v, g = c.p.c?.[0] ?? c.pick(GREENS);
  M.cyl(0.07, 0.11, 0.5, 0, 0, 0, "#7a5233", 8);
  if (v === 0) {
    M.ico(0.66, 0, 1.05, 0, g, 1, 0.95, { pat: PAT.foliage });
    M.ico(0.46, 0.34, 0.78, 0.12, shade(g, 1.06), 1, 1, { pat: PAT.foliage });
    M.ico(0.42, -0.3, 1.42, -0.1, shade(g, 0.94), 1, 1, { pat: PAT.foliage });
  } else {
    M.ico(0.74, 0, 1.18, 0, g, 2, 0.92, { pat: PAT.foliage });
  }
};
const pine: Builder = (c) => {
  const M = c.M, g = c.pick(["#2f7a4c", "#3b8a52", "#2a6e49"]);
  M.cyl(0.07, 0.1, 0.4, 0, 0, 0, "#6d4a2e", 8);
  M.cone(0.7, 0.8, 0, 0.35, 0, g, 12, { pat: PAT.foliage });
  M.cone(0.56, 0.75, 0, 0.85, 0, shade(g, 1.08), 12, { pat: PAT.foliage });
  M.cone(0.4, 0.7, 0, 1.35, 0, shade(g, 1.16), 12, { pat: PAT.foliage });
};
const bush: Builder = (c) => {
  const g = c.p.c?.[0] ?? c.pick(GREENS, 3);
  c.M.ico(0.34, 0, 0.26, 0, g, 1, 0.8, { pat: PAT.foliage });
  c.M.ico(0.26, 0.28, 0.2, 0.1, shade(g, 1.08), 1, 0.8, { pat: PAT.foliage });
  c.M.ico(0.22, -0.24, 0.17, -0.08, shade(g, 0.92), 1, 0.8, { pat: PAT.foliage });
};
const rock: Builder = (c) => {
  const col = c.pick(["#a9a59d", "#b6b1a7", "#9a968f"]);
  c.M.ico(0.4, 0, 0.18, 0, col, 0, 0.7, { pat: PAT.sand });
  if (c.p.v > 0) c.M.ico(0.24, 0.36, 0.1, 0.12, shade(col, 1.06), 0, 0.7, { pat: PAT.sand });
};
const lamp: Builder = (c) => {
  const M = c.M;
  M.cyl(0.07, 0.09, 0.08, 0, 0, 0, DARK, 8);
  M.cyl(0.03, 0.045, 1.45, 0, 0.06, 0, DARK, 8);
  M.cyl(0.14, 0.04, 0.06, 0, 1.46, 0, DARK, 10);
  M.use("emit"); M.sphere(0.12, 0, 1.62, 0, "#ffe7a6", 10); M.use("main");
  M.cone(0.17, 0.12, 0, 1.7, 0, DARK, 10);
};
const bench: Builder = (c) => {
  const M = c.M;
  M.box(0.85, 0.06, 0.3, 0, 0.3, 0, WOOD, { pat: PAT.deck, par: c.p.r });
  M.box(0.85, 0.3, 0.05, 0, 0.36, -0.14, WOOD, { pat: PAT.deck, par: c.p.r });
  for (const sx of [-0.36, 0.36]) { M.box(0.05, 0.3, 0.26, sx, 0, 0, DARK); }
};
const fence: Builder = (c) => {
  const M = c.M, len = c.p.len ?? 2, n = Math.max(2, Math.round(len / 0.45));
  for (let i = 0; i < n; i++) {
    const x = -len / 2 + (len * i) / (n - 1);
    M.box(0.07, 0.5, 0.07, x, 0, 0, TRIM);
  }
  M.box(len, 0.05, 0.04, 0, 0.18, 0, TRIM); M.box(len, 0.05, 0.04, 0, 0.36, 0, TRIM);
};
const crate: Builder = (c) => {
  const M = c.M, col = c.pick(["#c9914f", "#bd8444", "#d49d5a"]);
  M.rbox(0.5, 0.48, 0.5, 0, 0, 0, col, 0.03, { pat: PAT.planks });
  M.box(0.52, 0.05, 0.05, 0, 0.12, 0.25, WOOD_D); M.box(0.52, 0.05, 0.05, 0, 0.32, 0.25, WOOD_D);
};
const barrel: Builder = (c) => {
  const M = c.M, col = c.p.v === 1 ? "#2f6fa8" : "#9b673a";
  M.cyl(0.2, 0.17, 0.52, 0, 0, 0, col, 14, { pat: PAT.planks });
  M.cyl(0.215, 0.215, 0.04, 0, 0.12, 0, DARK, 14); M.cyl(0.215, 0.215, 0.04, 0, 0.36, 0, DARK, 14);
};
const bollard: Builder = (c) => {
  c.M.cyl(0.1, 0.13, 0.34, 0, 0, 0, DARK, 10); c.M.cyl(0.14, 0.14, 0.06, 0, 0.3, 0, "#f2c230", 10);
};
const buoy: Builder = (c) => {
  const M = c.M, col = c.p.c?.[0] ?? "#e8423a";
  c.part(0, 0, 0, (m) => {
    m.aoOn = false;
    m.cone(0.2, 0.5, 0, -0.05, 0, col, 12); m.cyl(0.2, 0.2, 0.12, 0, 0.18, 0, "#ffffff", 12); m.cone(0.2, 0.3, 0, 0.3, 0, col, 12);
    m.use("emit"); m.sphere(0.05, 0, 0.66, 0, "#ffe9a0", 8); m.use("main");
  }, (o, t) => { o.position.y = Math.sin(t * 1.4 + c.p.x) * 0.04; o.rotation.z = Math.sin(t * 1.1 + c.p.z) * 0.06; });
  void M;
};
const flag: Builder = (c) => {
  const M = c.M;
  M.cyl(0.025, 0.03, 2.1, 0, 0, 0, TRIM, 8);
  M.sphere(0.05, 0, 2.14, 0, "#f2c95a", 8);
  c.part(0.03, 1.75, 0, (m) => { m.aoOn = false; m.box(0.62, 0.36, 0.02, 0.31, 0, 0, "#e8503a"); m.box(0.62, 0.12, 0.025, 0.31, 0.12, 0, "#ffffff"); },
    (o, t) => { o.rotation.y = Math.sin(t * 2.4 + c.p.x) * 0.22; });
};

// ---------------------------------------------------------------- buildings
const house: Builder = (c) => {
  const M = c.M, v = c.p.v % 4, wall = wallOf(c), roof = roofOf(c), door = c.pick(["#3d6a8a", "#8a3d3d", "#3d7a5a", "#d9a53a"], 5);
  let w = 2.0, d = 1.7, h = 1.25;
  if (v === 2) { w = 1.8; d = 1.6; h = 2.05; }
  M.box(w + 0.08, 0.14, d + 0.08, 0, 0, 0, "#b9b2a6");
  M.box(w, h, d, 0, 0.1, 0, wall, { pat: PAT.plaster });
  const top = h + 0.1;
  if (v === 2) M.hip(w, d, 0.95, 0.16, 0, top, 0, roof);
  else M.gable(w, d, 0.85, 0.15, 0, top, 0, roof, wall);
  // door and windows (toy-sized)
  doorAt(M, -0.4, d / 2, 0.36, 0.66, door);
  windowAt(M, 0.5, 0.45, d / 2, 0.36, 0.34, 0, door);
  if (v === 2) { windowAt(M, -0.4, 1.35, d / 2, 0.34, 0.34, 0, door); windowAt(M, 0.5, 1.35, d / 2, 0.34, 0.34, 0, door); }
  windowAt(M, 0, 0.5, -d / 2, 0.34, 0.32, 1);
  windowAt(M, 0.0, v === 2 ? 1.35 : 0.5, d * 0.1, 0.32, 0.32, 2); windowAt(M, 0.0, v === 2 ? 1.35 : 0.5, -d * 0.1, 0.32, 0.32, 3);
  if (v === 1) {   // attic dormer on the front slope
    M.box(0.5, 0.34, 0.3, 0.35, top + 0.14, 0.34, wall); M.gable(0.5, 0.3, 0.22, 0.05, 0.35, top + 0.48, 0.34, roof, wall);
    M.use("glass"); M.box(0.26, 0.2, 0.04, 0.35, top + 0.22, 0.5, GLASS); M.use("main");
  }
  if (v === 3) {   // a lean-to wing
    M.box(0.9, 0.85, 1.2, w / 2 + 0.4, 0.1, -0.1, wall, { pat: PAT.plaster }); M.gable(0.9, 1.2, 0.4, 0.1, w / 2 + 0.4, 0.95, -0.1, roof, wall);
    windowAt(M, w / 2 + 0.4, 0.45, 0.5, 0.3, 0.3, 0);
  }
  if (v !== 2) { M.box(0.22, 0.6, 0.22, 0.52, top + 0.28, -0.35, "#b0614a", { pat: PAT.brick }); M.box(0.28, 0.06, 0.28, 0.52, top + 0.86, -0.35, "#8d4d3b"); }
};
const shop: Builder = (c) => {
  const M = c.M, wall = wallOf(c), roof = roofOf(c), aw = c.pick(c.palette, 9);
  const w = 2.3, d = 1.8, h = 2.05;
  M.box(w + 0.1, 0.14, d + 0.1, 0, 0, 0, "#b9b2a6");
  M.box(w, h, d, 0, 0.1, 0, wall, { pat: PAT.plaster });
  M.box(w + 0.12, 0.1, d + 0.12, 0, 0.1 + 0.95, 0, TRIM);                    // cornice between floors
  M.gable(w, d, 0.8, 0.14, 0, h + 0.1, 0, roof, wall);
  // shop window and door below, awning, two windows above
  M.use("glass"); M.box(1.0, 0.7, 0.06, 0.45, 0.28, d / 2 + 0.01, GLASS); M.use("main");
  M.box(1.1, 0.06, 0.1, 0.45, 0.22, d / 2 + 0.03, TRIM);
  doorAt(M, -0.6, d / 2, 0.4, 0.72, aw);
  for (let i = 0; i < 8; i++) {   // striped awning, sloping out
    M.push(); M.at(-0.55 + i * 0.26, 0.98, d / 2 + 0.28); M.pitch(-0.28);
    M.box(0.26, 0.05, 0.6, 0, 0, 0, i % 2 ? "#fffaf0" : aw); M.pop();
  }
  windowAt(M, -0.55, 1.42, d / 2, 0.4, 0.4, 0, aw); windowAt(M, 0.55, 1.42, d / 2, 0.4, 0.4, 0, aw);
  windowAt(M, 0, 1.3, -d / 2, 0.4, 0.4, 1); windowAt(M, 0, 1.3, 0, 0.4, 0.4, 2); windowAt(M, 0, 1.3, 0, 0.4, 0.4, 3);
  M.box(0.8, 0.28, 0.05, 0.45, 1.02 + 0.0, d / 2 + 0.05, "#fffaf0");         // sign board over the window
  M.box(0.22, 0.6, 0.22, -0.7, h + 0.45, -0.4, "#b0614a", { pat: PAT.brick });
  if (c.p.k === "cafe") {
    for (const sx of [-0.2, 1.1]) {
      c.M.cyl(0.03, 0.03, 0.7, sx, 0, d / 2 + 1.0, DARK, 6);
      c.M.cyl(0.36, 0.36, 0.04, sx, 0.7, d / 2 + 1.0, "#f4efe4", 14);
      c.M.cone(0.55, 0.22, sx, 1.1, d / 2 + 1.0, c.pick(c.palette, 11), 14);
      c.M.cyl(0.015, 0.015, 0.4, sx, 0.72, d / 2 + 1.0, DARK, 6);
      for (const sz of [-0.38, 0.38]) c.M.cyl(0.14, 0.14, 0.03, sx + sz, 0.36, d / 2 + 1.0, "#f4efe4", 8);
    }
  }
};
const warehouse: Builder = (c) => {
  const M = c.M, col = c.p.c?.[0] ?? "#8fa2b6", w = 4.4, d = 2.9, h = 1.8;
  M.box(w + 0.1, 0.14, d + 0.1, 0, 0, 0, "#9c9a95");
  M.box(w, h, d, 0, 0.1, 0, "#ece7dc", { pat: PAT.ribs });
  // low gable roof running along x: draw it rotated
  M.push(); M.at(0, h + 0.1, 0); M.yaw(Math.PI / 2); M.gable(d, w, 0.8, 0.16, 0, 0, 0, col, "#ece7dc", { pat: PAT.ribs }); M.pop();
  // big roller door and a pedestrian door at the front (+z), windows along the side
  M.box(1.7, 1.3, 0.08, -0.7, 0.1, d / 2, shade(col, 0.78), { pat: PAT.ribs });
  for (let i = 0; i < 6; i++) M.box(1.7, 0.03, 0.1, -0.7, 0.25 + i * 0.2, d / 2, "#d9dee5");
  doorAt(M, 1.4, d / 2, 0.42, 0.78, "#d9503a");
  for (const sx of [-1.7, 0.1, 1.7]) { M.use("glass"); M.box(0.5, 0.26, 0.05, sx, 1.4, d / 2 + 0.01, GLASS); M.use("main"); }
  M.box(2.0, 0.2, 1.0, -0.7, 0.0, d / 2 + 0.55, "#9c9a95");                      // loading apron
  M.cyl(0.22, 0.22, 0.8, w / 2 - 0.2, 0.1, -d / 2 + 0.3, "#cfd3d8", 14, { pat: PAT.metal });
};
const office: Builder = (c) => {
  const M = c.M, wall = wallOf(c), roof = roofOf(c), w = 2.9, d = 2.1, h = 2.3;
  M.box(w + 0.1, 0.16, d + 0.1, 0, 0, 0, "#b9b2a6");
  M.box(w, h, d, 0, 0.1, 0, wall, { pat: PAT.brick });
  M.box(w + 0.14, 0.12, d + 0.14, 0, 1.15, 0, TRIM);
  M.box(w + 0.18, 0.1, d + 0.18, 0, h + 0.1, 0, TRIM);
  M.hip(w, d, 0.7, 0.16, 0, h + 0.2, 0, roof);
  doorAt(M, 0, d / 2, 0.5, 0.82, "#3d6a8a");
  for (const sx of [-1.0, 1.0]) { windowAt(M, sx, 0.4, d / 2, 0.4, 0.5, 0, "#3d6a8a"); }
  for (const sx of [-1.0, 0, 1.0]) windowAt(M, sx, 1.45, d / 2, 0.38, 0.5, 0, "#3d6a8a");
  for (const z of [-0.5, 0.5]) { windowAt(M, 0, 0.5, z, 0.34, 0.45, 2); windowAt(M, 0, 0.5, z, 0.34, 0.45, 3); windowAt(M, 0, 1.45, z, 0.34, 0.45, 2); windowAt(M, 0, 1.45, z, 0.34, 0.45, 3); }
  // a clock over the door, a flagpole on the roof
  M.cyl(0.24, 0.24, 0.06, 0, 1.95, d / 2 + 0.02, "#fffaf0", 16); M.box(0.03, 0.18, 0.02, 0, 1.96, d / 2 + 0.07, DARK); M.box(0.12, 0.03, 0.02, 0.04, 1.98, d / 2 + 0.07, DARK);
  M.cyl(0.025, 0.03, 1.2, 0.0, h + 0.7, 0, TRIM, 8);
  M.box(0.4, 0.22, 0.02, 0.22, h + 1.6, 0, "#d9503a");
};
const stall: Builder = (c) => {
  const M = c.M, col = c.p.c?.[0] ?? c.pick(c.palette, 2), v = c.p.v;
  M.rbox(1.9, 0.62, 0.8, 0, 0, 0, WOOD, 0.03, { pat: PAT.planks });
  M.box(2.0, 0.06, 0.9, 0, 0.62, 0, shade(WOOD, 1.1));
  for (const sx of [-0.93, 0.93]) { M.cyl(0.04, 0.04, 1.9, sx, 0, 0.34, WOOD_D, 8); M.cyl(0.04, 0.04, 1.6, sx, 0, -0.34, WOOD_D, 8); }
  for (let i = 0; i < 8; i++) {   // striped canopy, higher at the back
    M.push(); M.at(-0.9 + i * 0.255 + 0.1, 1.78, 0.04); M.pitch(0.32);
    M.box(0.255, 0.05, 1.0, 0, 0, 0, i % 2 ? "#fffaf0" : col); M.pop();
  }
  for (let i = 0; i < 8; i++) M.box(0.255, 0.1, 0.04, -0.9 + i * 0.255 + 0.1, 1.5, 0.52, i % 2 ? "#fffaf0" : col);
  // wares: crates of fruit, loaves, a scale
  const fruit = ["#e8503a", "#f2b32a", "#7fbf4a", "#f08a3a"];
  for (let i = 0; i < 3; i++) {
    const x = -0.62 + i * 0.62;
    M.rbox(0.46, 0.14, 0.4, x, 0.68, 0.08, WOOD_D, 0.02);
    for (let k = 0; k < 5; k++) M.sphere(0.075, x - 0.14 + (k % 3) * 0.14, 0.86 + (k > 2 ? 0.05 : 0), 0.08 + (k % 2) * 0.08 - 0.04, fruit[(i + (v || 0) + k) % fruit.length], 8);
  }
  M.cyl(0.06, 0.08, 0.1, 0.0, 0.68, -0.22, DARK, 8);
};
const container: Builder = (c) => {
  const M = c.M, col = c.p.c?.[0] ?? c.pick(c.palette), L = 2.4, W = 1.0, H = 1.0;
  M.box(L, H, W, 0, 0, 0, col, { pat: PAT.ribs });
  M.box(L + 0.04, 0.08, W + 0.04, 0, 0, 0, shade(col, 0.75)); M.box(L + 0.04, 0.08, W + 0.04, 0, H - 0.08, 0, shade(col, 0.75));
  for (const sx of [-L / 2, L / 2]) for (const sz of [-W / 2, W / 2]) M.box(0.08, H, 0.08, sx, 0, sz, shade(col, 0.7));
  // door end with locking bars (the +x end)
  M.box(0.03, H - 0.12, W - 0.1, L / 2 + 0.01, 0.06, 0, shade(col, 0.88));
  for (const sz of [-0.2, 0.2]) M.box(0.04, H - 0.14, 0.03, L / 2 + 0.03, 0.06, sz, "#cfd3d8");
};
const boat: Builder = (c) => hullBoat(c, c.p.k === "ferry");

function hullBoat(c: KitCtx, ferry: boolean) {
  const v = c.p.v % 3, col = c.p.c?.[0] ?? c.pick(c.palette, 4);
  const L = ferry ? 4.4 : 2.4, W = ferry ? 1.7 : 1.0, H = ferry ? 0.55 : 0.34;
  c.part(0, 0, 0, (m) => {
    m.aoOn = false;
    const n = 9, sec: THREE.Vector3[][] = [];
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const hw = W / 2 * (t < 0.55 ? (0.78 + 0.22 * t / 0.55) : Math.cos((t - 0.55) / 0.45 * Math.PI / 2) ** 0.7);
      const z = -L / 2 + L * t, yd = H * (1 + 0.28 * t * t * t);
      sec.push([new THREE.Vector3(0, -0.04, z), new THREE.Vector3(-hw * 0.5, yd * 0.28, z), new THREE.Vector3(-hw, yd * 0.55, z), new THREE.Vector3(-hw * 1.04, yd, z),
                new THREE.Vector3(hw * 1.04, yd, z), new THREE.Vector3(hw, yd * 0.55, z), new THREE.Vector3(hw * 0.5, yd * 0.28, z), new THREE.Vector3(0, -0.04, z)]);
    }
    const colors = [shade(col, 0.55), shade(col, 0.55), "#fffaf0", "#cbb27a", "#fffaf0", shade(col, 0.55), shade(col, 0.55)];
    for (let i = 0; i < n; i++) for (let k = 0; k < 7; k++) m.quad(sec[i][k], sec[i + 1][k], sec[i + 1][k + 1], sec[i][k + 1], colors[k]);
    // deck cap
    const deck = ferry ? "#e5d3a8" : "#c9a36a";
    for (let i = 0; i < n; i++) m.quad(sec[i][3], sec[i + 1][3], sec[i + 1][4], sec[i][4], deck, { pat: PAT.deck, par: 0 });
    const yTop = H * 1.02;
    if (ferry) {
      m.rbox(1.3, 0.55, 2.4, 0, yTop, -0.25, "#fffaf0", 0.06); m.rbox(1.05, 0.5, 1.7, 0, yTop + 0.55, -0.35, "#fffaf0", 0.06);
      m.use("glass"); m.box(1.34, 0.2, 2.0, 0, yTop + 0.2, -0.25, "#2b4a63"); m.box(1.08, 0.18, 1.4, 0, yTop + 0.74, -0.35, "#2b4a63"); m.use("main");
      m.rbox(1.15, 0.08, 1.9, 0, yTop + 1.04, -0.35, col, 0.03);
      m.cyl(0.2, 0.24, 0.8, 0, yTop + 1.0, -0.7, col, 14); m.cyl(0.21, 0.21, 0.14, 0, yTop + 1.6, -0.7, "#222a33", 14);
      for (const sx of [-0.62, 0.62]) m.torus(0.13, 0.04, sx, yTop + 0.35, 0.65, "#e8503a", 0, 10);
    } else if (v === 1) {
      m.cyl(0.03, 0.04, 2.4, 0, yTop, 0.1, "#e9e2d0", 8);
      m.tri(new THREE.Vector3(0, yTop + 0.25, 0.14), new THREE.Vector3(0, yTop + 2.35, 0.14), new THREE.Vector3(0, yTop + 0.2, 0.95), "#fffaf0");
      m.tri(new THREE.Vector3(0, yTop + 0.25, 0.06), new THREE.Vector3(0, yTop + 2.1, 0.06), new THREE.Vector3(0, yTop + 0.2, -0.65), col);
    } else {
      m.rbox(0.62, 0.42, 0.9, 0, yTop, -0.2, "#fffaf0", 0.05);
      m.use("glass"); m.box(0.66, 0.16, 0.5, 0, yTop + 0.16, -0.1, "#2b4a63"); m.use("main");
      m.rbox(0.7, 0.05, 1.0, 0, yTop + 0.42, -0.2, col, 0.02);
      if (v === 2) { m.cyl(0.025, 0.03, 0.9, 0, yTop + 0.42, -0.5, DARK, 6); m.box(0.5, 0.03, 0.03, 0, yTop + 1.1, -0.5, DARK); }
    }
  }, (o, t) => {
    const ph = c.p.x * 0.7 + c.p.z * 0.4;
    o.position.y = Math.sin(t * 1.3 + ph) * 0.035 - 0.02;
    o.rotation.z = Math.sin(t * 0.9 + ph) * 0.025; o.rotation.x = Math.sin(t * 1.1 + ph * 1.3) * 0.015;
  });
}

const pier: Builder = (c) => {
  const M = c.M, len = c.p.len ?? 5.2, w = 1.5;
  M.box(w, 0.12, len, 0, 0.0, len / 2 - 0.4, WOOD, { pat: PAT.deck, par: c.p.r });
  for (let i = 0; i < Math.round(len / 1.1) + 1; i++) for (const sx of [-w / 2 + 0.06, w / 2 - 0.06]) M.cyl(0.075, 0.085, 1.5, sx, -1.25, -0.2 + i * 1.1, WOOD_D, 8);
  for (const sx of [-w / 2 + 0.07, w / 2 - 0.07]) for (const z of [len * 0.3, len - 0.7]) M.cyl(0.07, 0.09, 0.3, sx, 0.1, z, DARK, 8);
};

// ---------------------------------------------------------------- landmarks
const lighthouse: Builder = (c) => {
  const M = c.M, red = c.p.c?.[0] ?? "#d9503a";
  M.cyl(1.25, 1.3, 0.32, 0, 0, 0, "#9c9a95", 20);
  const segs = [["#fffaf0", 1.0], [red, 0.95], ["#fffaf0", 0.9], [red, 0.85], ["#fffaf0", 0.8]] as const;
  let y = 0.3, r = 1.05;
  segs.forEach(([col, hgt], i) => {
    const r1 = r - 0.045 * hgt * 2.4;
    M.cyl(r1, r, hgt * 1.15, 0, y, 0, col, 24, { pat: PAT.stripes });
    y += hgt * 1.15; r = r1;
  });
  // windows up the tower, a door at the foot
  doorAt(M, 0, 1.05, 0.42, 0.78, "#3d6a8a");
  for (const [yy, rr] of [[1.9, 0.95], [3.3, 0.88], [4.5, 0.82]] as const) { M.use("glass"); M.box(0.2, 0.34, 0.07, 0, yy, rr, "#2b4a63"); M.use("main"); }
  // gallery with railing
  M.cyl(r + 0.28, r + 0.18, 0.12, 0, y, 0, "#2f3a44", 24);
  for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2; M.cyl(0.02, 0.02, 0.34, Math.cos(a) * (r + 0.24), y + 0.12, Math.sin(a) * (r + 0.24), "#2f3a44", 5); }
  M.torus(r + 0.24, 0.025, 0, y + 0.46, 0, "#2f3a44", Math.PI / 2, 24);
  // lantern room
  M.use("glass"); M.cyl(r * 0.62, r * 0.62, 0.72, 0, y + 0.12, 0, "#ffe9a8", 14); M.use("main");
  M.use("emit"); M.sphere(0.2, 0, y + 0.5, 0, "#fff3c0", 10); M.use("main");
  for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; M.box(0.04, 0.76, 0.04, Math.cos(a) * r * 0.63, y + 0.12, Math.sin(a) * r * 0.63, "#2f3a44"); }
  M.cone(r * 0.78, 0.55, 0, y + 0.84, 0, red, 18); M.sphere(0.09, 0, y + 1.44, 0, "#2f3a44", 8);
  // the sweeping beam: two soft additive cones turning round the lantern
  const beam = new THREE.Group();
  const bm = new THREE.MeshBasicMaterial({ color: new THREE.Color("#fff0b0"), transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
  for (const s of [1, -1]) {
    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.9, 6.5, 20, 1, true), bm);
    cone.rotation.z = -Math.PI / 2 * s; cone.position.x = 3.4 * s; beam.add(cone);
  }
  beam.renderOrder = 3;
  c.add(beam, 0, y + 0.5, 0, (o, t) => { o.rotation.y = t * 0.9; });
};
const crane: Builder = (c) => {
  const M = c.M, Y = "#f2b21c", G = "#5c636b", span = 3.4, depth = 3.2, H = 4.6;
  // four legs, portal beams, a long boom out over the water (+z) with a trolley on it
  for (const sx of [-span / 2, span / 2]) for (const sz of [-depth / 2 + 0.2, depth / 2 - 0.2]) {
    M.box(0.24, H, 0.24, sx, 0, sz, Y, { pat: PAT.metal }); M.box(0.4, 0.14, 0.4, sx, 0, sz, G);
    M.cyl(0.14, 0.14, 0.12, sx, -0.0, sz + (sz > 0 ? 0.35 : -0.35), DARK, 10);
  }
  for (const sz of [-depth / 2 + 0.2, depth / 2 - 0.2]) { M.box(span + 0.3, 0.28, 0.3, 0, H, sz, Y); M.box(span, 0.18, 0.18, 0, 2.3, sz, Y); }
  for (const sx of [-span / 2, span / 2]) { M.box(0.18, 0.18, depth, sx, H + 0.05, 0, Y); M.box(0.14, 0.14, depth - 0.4, sx, 2.3, 0, Y); }
  // cab and machinery house
  M.rbox(1.0, 0.7, 1.1, -span / 2 + 0.4, H + 0.3, -0.3, "#e9e2cf", 0.05); M.use("glass"); M.box(0.62, 0.32, 0.04, -span / 2 + 0.4, H + 0.55, 0.28, "#2b4a63"); M.use("main");
  // boom: a lattice of two chords and zigzag, reaching out and a little up
  const boomLen = 7.6;
  M.push(); M.at(0, H + 0.34, 0); M.pitch(-0.07);
  for (const sx of [-0.5, 0.5]) { M.box(0.1, 0.1, boomLen, sx, 0, depth / 2 - 1.0, Y); M.box(0.08, 0.08, boomLen, sx, 0.55, depth / 2 - 1.0, Y); }
  for (let i = 0; i < 18; i++) {
    const z = depth / 2 - 1.0 + i * (boomLen / 18);
    M.box(1.1, 0.05, 0.05, 0, 0.02, z, Y); M.box(1.1, 0.05, 0.05, 0, 0.56, z, Y);
    for (const sx of [-0.5, 0.5]) { M.push(); M.at(sx, 0.02, z); M.pitch((i % 2 ? 1 : -1) * 0.6); M.box(0.05, 0.6, 0.05, 0, 0, 0, Y); M.pop(); }
  }
  M.pop();
  M.box(1.4, 0.7, 0.8, 0, H + 0.34, -depth / 2 - 0.9, G);        // counterweight at the back
  // the trolley + hoist cables + a hanging container, running along the boom
  const boxCol = c.pick(c.palette, 6);
  c.part(0, H + 0.18, depth / 2 + 1.8, (m) => {
    m.aoOn = false;
    m.rbox(0.9, 0.22, 0.5, 0, 0, 0, G, 0.03);
    m.cyl(0.015, 0.015, 2.1, -0.3, -2.1, 0.1, DARK, 4); m.cyl(0.015, 0.015, 2.1, 0.3, -2.1, 0.1, DARK, 4);
    m.box(2.4, 0.1, 1.0, 0, -2.2, 0, G);
    m.box(2.4, 1.0, 1.0, 0, -3.2, 0, boxCol, { pat: PAT.ribs });
  }, (o, t) => { o.position.z = depth / 2 + 2.6 + Math.sin(t * 0.35) * 1.5; });
};
const windmill: Builder = (c) => {
  const M = c.M, roof = c.p.c?.[0] ?? "#c4433a";
  M.cyl(1.25, 1.35, 0.6, 0, 0, 0, "#b0614a", 20, { pat: PAT.brick });
  M.cyl(0.78, 1.18, 3.0, 0, 0.6, 0, "#f4ead8", 20, { pat: PAT.plaster });
  M.cone(0.95, 1.1, 0, 3.55, 0, roof, 20);
  doorAt(M, 0, 1.3, 0.44, 0.8, "#3d6a8a");
  for (const [y, r] of [[1.6, 1.07], [2.4, 0.97]] as const) windowAt(M, 0, y, r, 0.3, 0.38, 0, "#3d6a8a");
  M.box(0.14, 0.14, 0.14, 0, 3.55, 0.75, "#2f3a44");
  // blades turn on the front
  c.part(0, 3.5, 0.95, (m) => {
    m.aoOn = false;
    m.push(); m.pitch(Math.PI / 2); m.cyl(0.16, 0.16, 0.3, 0, -0.15, 0, "#2f3a44", 12); m.pop();
    for (let i = 0; i < 4; i++) {
      m.push(); m.roll(i * Math.PI / 2);
      m.box(0.1, 3.4, 0.07, 0, 0, 0, "#7a5233");
      for (let k = 0; k < 6; k++) m.box(0.5, 0.3, 0.03, 0.26, 0.5 + k * 0.4, 0.03, k % 2 ? "#fffaf0" : "#ece4d0");
      m.pop();
    }
  }, (o, t) => { o.rotation.z = -t * 0.55; });
};

const STUB: Builder = (c) => { c.M.rbox(1.2, 1.2, 1.2, 0, 0, 0, "#c0b8ac", 0.1); };

export const KIT: Record<string, Builder> = {
  tree, pine, bush, rock, lamp, bench, fence, crate, barrel, bollard, buoy, flag,
  house, shop, cafe: shop, warehouse, office, stall, container, boat, ferry: boat, pier, lighthouse, crane, windmill,
  ...KIT2,
  ...KIT3,
};

export function builderFor(kind: string): Builder {
  const b = KIT[kind];
  if (!b) { console.warn("[diorama] unknown prop kind", kind); return STUB; }
  return b;
}

export { hash };
