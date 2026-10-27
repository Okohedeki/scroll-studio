/**
 * The automation kit: clean production machines, a robot arm, a storage tower, a floor of tiles and the carrier decks
 * that movers ride on. Same conventions as kit.ts (origin at the middle of the base, front towards +z, about a metre a
 * unit), with one more: every machine is a tunnel along x at floor height (0.6 high, 1.2 deep), open at the front, so a
 * mover on a route along x passes through it and the camera sees what it carries while it is inside.
 */
import * as THREE from "three";
import { PAT, shade } from "./mesher";
import type { Mesher } from "./mesher";
import type { KitCtx } from "./kit";

type Builder = (c: KitCtx) => void;
const BODY = "#eef1f4", BODY2 = "#dde2e8", INK = "#232833", STEEL = "#aeb6bf", DARK = "#3a3f47", GLASS = "#b8dcef";
const TUNNEL = 0.62;          // the tunnel's height
const accentOf = (c: KitCtx) => c.p.c?.[0] ?? "#0085e0";

/** a cylinder lying along x (h long), centred at (x, y, z) */
function cylX(M: Mesher, r: number, h: number, x: number, y: number, z: number, color: string, seg = 16, o = {}) {
  M.push(); M.at(x, y, z); M.roll(Math.PI / 2); M.cyl(r, r, h, 0, -h / 2, 0, color, seg, o); M.pop();
}
/** a cylinder lying along z (h long), centred at (x, y, z) */
function cylZ(M: Mesher, r: number, h: number, x: number, y: number, z: number, color: string, seg = 16, o = {}) {
  M.push(); M.at(x, y, z); M.pitch(Math.PI / 2); M.cyl(r, r, h, 0, -h / 2, 0, color, seg, o); M.pop();
}
/** a stack light on a post: green lit, amber and red dark */
function beacon(M: Mesher, x: number, y: number, z: number) {
  M.cyl(0.03, 0.03, 0.22, x, y, z, STEEL, 8);
  M.cyl(0.07, 0.07, 0.1, x, y + 0.22, z, "#8b2d2d", 12);
  M.cyl(0.07, 0.07, 0.1, x, y + 0.32, z, "#9a7a2c", 12);
  M.use("emit"); M.cyl(0.07, 0.07, 0.1, x, y + 0.42, z, "#7dff9a", 12); M.use("main");
  M.cyl(0.06, 0.07, 0.04, x, y + 0.52, z, DARK, 12);
}
/** a small lit screen with rows of status */
function panel(M: Mesher, w: number, h: number, x: number, y: number, z: number, accent: string) {
  M.box(w + 0.06, h + 0.06, 0.04, x, y - 0.03, z - 0.02, INK);
  M.use("emit");
  M.box(w, h, 0.02, x, y, z, "#dfeefc");
  const rows = 4;
  for (let i = 0; i < rows; i++) M.box(w * (0.45 + 0.12 * ((i * 3) % 4)), h / rows * 0.36, 0.024, x - w * 0.08, y + h - (i + 0.75) * (h / rows), z + 0.004, i === 0 ? accent : "#9fc0e4");
  M.use("main");
}
/** the tunnel's two plinths and its back wall, a floor plate under it, feet */
function tunnelBase(M: Mesher, W: number, D: number, accent: string) {
  const side = 0.28;
  for (const sx of [-1, 1]) {
    M.rbox(side, TUNNEL, D, sx * (W / 2 - side / 2), 0, 0, BODY2, 0.04);
    M.box(side + 0.01, 0.05, D + 0.01, sx * (W / 2 - side / 2), 0.0, 0, INK);
  }
  M.box(W - 2 * side, TUNNEL, 0.14, 0, 0, -D / 2 + 0.07, BODY2);
  M.box(W - 2 * side, 0.03, D - 0.2, 0, 0, 0.0, "#c9cfd6", { pat: PAT.metal });
  // the tunnel's mouth: an accent rim round the front opening
  M.box(W - 2 * side + 0.02, 0.05, 0.05, 0, TUNNEL - 0.05, D / 2 - 0.02, accent);
  M.use("emit"); M.box(W - 2 * side - 0.2, 0.012, 0.08, 0, TUNNEL - 0.075, D / 2 - 0.2, "#f2f8ff"); M.use("main");
}
/** a soft light in the tunnel (no shadows), so a load inside it reads against the machine's shade */
function workLight(c: KitCtx, D: number) {
  const l = new THREE.PointLight("#f4f8ff", 1.6, 2.6, 1.6);
  l.castShadow = false;
  c.add(l, 0, TUNNEL - 0.12, D / 2 - 0.25);
}
/** the machine's upper body over the tunnel: a rounded hood with a window, a navy band, a screen and a beacon */
function hood(M: Mesher, W: number, D: number, H: number, accent: string, opts: { window?: boolean; screen?: boolean } = {}) {
  const h = H - TUNNEL;
  M.rbox(W, h, D, 0, TUNNEL, 0, BODY, 0.08);
  M.box(W + 0.01, 0.14, D + 0.01, 0, TUNNEL, 0, INK);
  M.box(W + 0.012, 0.035, D + 0.012, 0, TUNNEL + 0.14, 0, accent);
  if (opts.window !== false) {
    M.use("glass");
    M.box(W * 0.62, h * 0.48, 0.03, -W * 0.08, TUNNEL + 0.28, D / 2 + 0.005, GLASS, { ao: false });
    M.use("main");
    M.box(W * 0.62 + 0.06, 0.04, 0.05, -W * 0.08, TUNNEL + 0.26, D / 2 + 0.01, STEEL);
  }
  if (opts.screen !== false) panel(M, 0.34, 0.24, W / 2 - 0.36, TUNNEL + 0.36, D / 2 + 0.02, accent);
  beacon(M, W / 2 - 0.16, H, -D / 2 + 0.2);
}

// ---------------------------------------------------------------- machines
/** a stencil printer: a squeegee sweeps across a stencil frame over the tunnel */
const printer: Builder = (c) => {
  const M = c.M, a = accentOf(c), W = 2.4, D = 1.7, H = 1.85;
  tunnelBase(M, W, D, a);
  workLight(c, D);
  hood(M, W, D, H, a, { window: false });
  // a tilted control screen on an arm at the right, and a paste cartridge rack on the lid
  M.box(0.06, 0.5, 0.06, W / 2 + 0.12, H - 0.7, D / 2 - 0.2, STEEL);
  M.push(); M.at(W / 2 + 0.12, H - 0.2, D / 2 - 0.12); M.pitch(-0.35); panel(M, 0.42, 0.3, 0, 0, 0.0, a); M.pop();
  M.use("glass"); M.box(W * 0.56, (H - TUNNEL) * 0.42, 0.03, -W * 0.1, TUNNEL + 0.26, D / 2 + 0.005, GLASS, { ao: false }); M.use("main");
  for (let i = 0; i < 4; i++) M.cyl(0.07, 0.07, 0.28, -W / 2 + 0.4 + i * 0.22, H, -0.25, i === 0 ? a : "#f4f6f8", 14);
  // the stencil frame, open in the middle so what is under it shows
  for (const sz of [-0.5, 0.5]) M.box(1.3, 0.04, 0.08, 0, 0.42, sz, STEEL, { pat: PAT.metal });
  for (const sx of [-0.62, 0.62]) M.box(0.08, 0.04, 1.0, sx, 0.42, 0, STEEL, { pat: PAT.metal });
  M.box(1.16, 0.012, 0.86, 0, 0.43, 0, "#c3cad2", { pat: PAT.metal });
  c.part(0, 0.47, 0, (m) => {
    m.aoOn = false;
    m.box(0.05, 0.09, 0.98, 0, 0, 0, "#7b848e");
    m.box(0.16, 0.06, 0.18, 0, 0.09, 0, a);
    m.cyl(0.02, 0.02, 0.06, 0, 0.15, 0, STEEL, 6);
  }, (o, t) => { o.position.x = Math.sin(t * 0.9) * 0.48; });
};
/** a pick-and-place machine: a glass canopy over a gantry whose head of nozzles darts over the tunnel; banks of reels
 * of parts feed it from both sides */
const placer: Builder = (c) => {
  const M = c.M, a = accentOf(c), W = 2.8, D = 2.0, H = 1.95;
  tunnelBase(M, W, D, a);
  workLight(c, D);
  // the body round the canopy: a frame with a navy band, the canopy glass on top and front
  M.rbox(W, 0.42, D, 0, TUNNEL, 0, BODY, 0.06);
  M.box(W + 0.01, 0.12, D + 0.01, 0, TUNNEL, 0, INK);
  M.box(W + 0.012, 0.035, D + 0.012, 0, TUNNEL + 0.12, 0, a);
  const top = TUNNEL + 0.42, ch = H - top;
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) M.box(0.08, ch, 0.08, sx * (W / 2 - 0.04), top, sz * (D / 2 - 0.04), BODY2);
  M.box(W, 0.08, D, 0, H - 0.08, 0, BODY);
  // a dark panel only at the back, so the gantry shows against it from the front through the open frame
  M.box(W - 0.16, ch - 0.1, 0.02, 0, top, -D / 2 + 0.04, "#2c3442");
  M.box(W - 0.16, 0.04, 0.05, 0, top + ch - 0.12, D / 2 - 0.04, a);
  // the gantry: rails along x inside the canopy, a beam across them and a head on the beam
  for (const sz of [-0.6, 0.6]) M.box(W - 0.3, 0.05, 0.08, 0, top + ch * 0.62, sz, "#7b848e");
  c.part(0, top + ch * 0.62, 0, (m) => {
    m.aoOn = false;
    m.box(0.14, 0.12, 1.36, 0, -0.04, 0, "#5c636b");
    m.box(0.16, 0.03, 1.38, 0, 0.08, 0, a);
  }, (o, t) => { o.position.x = Math.sin(t * 0.8) * 0.7; });
  c.part(0, top + ch * 0.62 - 0.12, 0, (m) => {
    m.aoOn = false;
    m.rbox(0.24, 0.22, 0.22, 0, -0.05, 0, INK, 0.03);
    m.box(0.25, 0.04, 0.23, 0, 0.1, 0, a);
    for (const nz of [-0.06, 0.06]) m.cyl(0.014, 0.014, 0.18, 0, -0.23, nz, "#d7dce2", 6);
  }, (o, t) => {
    o.position.x = Math.sin(t * 0.8) * 0.7;
    o.position.z = Math.sin(t * 2.1) * 0.45;
    o.position.y = top + ch * 0.62 - 0.12 - Math.max(0, Math.sin(t * 4.2)) * 0.14;
  });
  // feeder banks on the left and right: reels of parts standing in a row
  for (const sx of [-1, 1]) {
    M.box(0.5, 0.5, D - 0.3, sx * (W / 2 + 0.25), 0, 0, BODY2);
    for (let i = 0; i < 6; i++) {
      const z = -D / 2 + 0.35 + i * ((D - 0.7) / 5);
      cylX(M, 0.22, 0.05, sx * (W / 2 + 0.25), 0.72, z, i % 3 === 1 ? a : "#f4f6f8", 18);
      cylX(M, 0.06, 0.06, sx * (W / 2 + 0.25), 0.72, z, DARK, 10);
    }
  }
  beacon(M, W / 2 - 0.12, H, -D / 2 + 0.12);
};
/** a reflow oven: a long low tunnel with heating zones that glow, and heaters over the tunnel */
const oven: Builder = (c) => {
  const M = c.M, a = accentOf(c), W = 3.6, D = 1.6, H = 1.35;
  tunnelBase(M, W, D, a);
  workLight(c, D);
  const h = H - TUNNEL;
  M.rbox(W, h, D, 0, TUNNEL, 0, BODY, 0.08);
  M.box(W + 0.01, 0.12, D + 0.01, 0, TUNNEL, 0, INK);
  M.box(W + 0.012, 0.035, D + 0.012, 0, TUNNEL + 0.12, 0, a);
  // the zones: grooves in the lid and a lit window each on the front
  const Z = 6;
  for (let i = 1; i < Z; i++) M.box(0.03, 0.02, D + 0.02, -W / 2 + i * (W / Z), H - 0.01, 0, BODY2);
  for (let i = 0; i < Z; i++) {
    const x = -W / 2 + (i + 0.5) * (W / Z);
    M.box(W / Z - 0.14, 0.2, 0.03, x, TUNNEL + 0.24, D / 2 - 0.005, INK);
  }
  M.use("emit");
  for (let i = 0; i < Z; i++) {
    const x = -W / 2 + (i + 0.5) * (W / Z);
    M.box(W / Z - 0.2, 0.14, 0.02, x, TUNNEL + 0.27, D / 2 + 0.012, i < 2 ? "#ffb15c" : i < 4 ? "#ff8a3d" : "#ff6a2c");
    M.box(W / Z - 0.16, 0.025, D - 0.4, x, TUNNEL - 0.06, 0, "#ff7a32");          // the heaters over the tunnel
  }
  M.use("main");
  M.box(0.06, 0.4, 0.06, W / 2 - 0.2, H, -D / 2 + 0.2, STEEL);
  M.cyl(0.12, 0.12, 0.1, W / 2 - 0.2, H + 0.4, -D / 2 + 0.2, STEEL, 14);
  panel(M, 0.3, 0.2, -W / 2 + 0.35, TUNNEL + 0.3, D / 2 + 0.02, a);
};
/** an inspection station: a camera with a ring of light on an arch, a line of light scanning across the tunnel */
const scanner: Builder = (c) => {
  const M = c.M, a = accentOf(c), W = 2.2, D = 1.5, H = 2.3;
  tunnelBase(M, W, D, a);
  workLight(c, D);
  for (const sx of [-1, 1]) M.rbox(0.26, H - TUNNEL - 0.3, 0.5, sx * (W / 2 - 0.13), TUNNEL, -0.2, BODY, 0.05);
  M.rbox(W, 0.36, 0.7, 0, H - 0.36, -0.2, BODY, 0.06);
  M.box(W + 0.01, 0.06, 0.71, 0, H - 0.36, -0.2, a);
  // the camera: a body, a lens and a ring of light, looking straight down
  M.rbox(0.36, 0.42, 0.36, 0, H - 0.78, 0.0, INK, 0.05);
  M.cyl(0.11, 0.13, 0.2, 0, H - 0.98, 0.0, DARK, 18);
  M.use("emit"); M.torus(0.2, 0.025, 0, H - 1.0, 0.0, "#d9f1ff", Math.PI / 2, 28); M.use("main");
  c.part(0, TUNNEL + 0.01, 0, (m) => {
    m.aoOn = false;
    m.use("emit");
    m.box(0.03, 0.01, 1.1, 0, 0, 0, "#7fd4ff");
    m.use("main");
  }, (o, t) => { o.position.x = Math.sin(t * 1.3) * 0.6; });
  panel(M, 0.4, 0.28, W / 2 - 0.4, H - 0.32, 0.16, a);
  beacon(M, -W / 2 + 0.13, H, -0.2);
};
/** an automated storage tower: reels of parts on shelves behind glass, a lift that runs up and down the front */
const storage: Builder = (c) => {
  const M = c.M, a = accentOf(c), W = 2.1, D = 1.9, H = 4.6;
  tunnelBase(M, W, D, a);
  workLight(c, D);
  M.rbox(W, H - TUNNEL, D, 0, TUNNEL, 0, BODY, 0.08);
  M.box(W + 0.01, 0.14, D + 0.01, 0, TUNNEL, 0, INK);
  // the shelves of reels, seen through a tall window
  M.box(W * 0.74, H - TUNNEL - 0.7, 0.03, 0, TUNNEL + 0.4, D / 2 - 0.01, "#2c3442");
  const rows = 9, cols = 5;
  for (let r = 0; r < rows; r++) {
    const y = TUNNEL + 0.55 + r * ((H - TUNNEL - 1.0) / (rows - 1));
    M.box(W * 0.72, 0.02, 0.08, 0, y - 0.17, D / 2 + 0.02, STEEL);
    for (let k = 0; k < cols; k++) {
      const x = -W * 0.3 + k * (W * 0.6 / (cols - 1));
      cylZ(M, 0.13, 0.04, x, y, D / 2 + 0.04, (r * cols + k) % 7 === 0 ? a : (r + k) % 2 ? "#f4f6f8" : "#dfe5ec", 16);
    }
  }
  M.box(0.06, H - TUNNEL - 0.4, 0.06, -W * 0.39, TUNNEL + 0.2, D / 2 + 0.08, STEEL);
  M.box(0.06, H - TUNNEL - 0.4, 0.06, W * 0.39, TUNNEL + 0.2, D / 2 + 0.08, STEEL);
  c.part(0, TUNNEL + 0.3, D / 2 + 0.12, (m) => {
    m.aoOn = false;
    m.box(W * 0.8, 0.06, 0.12, 0, 0, 0, a);
    m.rbox(0.3, 0.16, 0.18, 0, 0.06, 0.02, INK, 0.03);
    cylZ(m, 0.13, 0.04, 0, 0.28, 0.06, "#f4f6f8", 16);
  }, (o, t) => { o.position.y = TUNNEL + 0.3 + (0.5 - 0.5 * Math.cos(t * 0.45)) * (H - TUNNEL - 1.2); });
  panel(M, 0.36, 0.26, W / 2 - 0.3, TUNNEL + 0.3, D / 2 + 0.03, a);
  beacon(M, W / 2 - 0.2, H, -D / 2 + 0.2);
};
/** a robot arm, white with joints in the accent, reaching down and up in a slow pick-and-place loop */
const arm: Builder = (c) => {
  const M = c.M, a = accentOf(c);
  M.cyl(0.42, 0.48, 0.16, 0, 0, 0, INK, 22);
  M.cyl(0.32, 0.36, 0.22, 0, 0.16, 0, BODY2, 22);
  const L1 = 1.0, L2 = 0.85;
  const turret = c.meshOf((m) => {
    m.cyl(0.26, 0.3, 0.28, 0, 0, 0, BODY, 20);
    m.push(); m.at(0, 0.36, 0); m.roll(Math.PI / 2); m.cyl(0.17, 0.17, 0.42, 0, -0.21, 0, a, 18); m.pop();
  });
  const shoulder = new THREE.Group(); shoulder.position.y = 0.36; turret.add(shoulder);
  shoulder.add(c.meshOf((m) => { m.rbox(0.2, L1, 0.22, 0, 0, 0, BODY, 0.08); }));
  const elbow = new THREE.Group(); elbow.position.y = L1; shoulder.add(elbow);
  elbow.add(c.meshOf((m) => {
    m.push(); m.roll(Math.PI / 2); m.cyl(0.13, 0.13, 0.3, 0, -0.15, 0, a, 16); m.pop();
    m.rbox(0.16, L2, 0.16, 0, 0, 0, BODY, 0.06);
    m.cyl(0.09, 0.09, 0.12, 0, L2, 0, INK, 12);
    m.box(0.18, 0.03, 0.06, 0, L2 + 0.12, 0, DARK);
    m.box(0.025, 0.12, 0.06, -0.075, L2 + 0.0, 0, DARK); m.box(0.025, 0.12, 0.06, 0.075, L2 + 0.0, 0, DARK);
  }));
  c.add(turret, 0, 0.38, 0, (o, t) => {
    const s = 0.5 + 0.5 * Math.sin(t * 1.1);
    o.rotation.y = Math.sin(t * 0.55) * 1.1;
    shoulder.rotation.x = 0.35 + 0.5 * s;
    elbow.rotation.x = 1.0 + 0.55 * s;
  });
};
/** a carrier deck: a flat rounded square that floats over the floor, lit underneath, with the accent along its sides */
const carrier: Builder = (c) => {
  const M = c.M, a = accentOf(c), col = c.p.c?.[1] ?? "#2a3342";
  M.rbox(0.88, 0.1, 0.88, 0, 0.02, 0, col, 0.05);
  M.box(0.9, 0.025, 0.9, 0, 0.05, 0, a);
  M.rbox(0.8, 0.02, 0.8, 0, 0.12, 0, shade(col, 1.25), 0.02);
  M.use("emit"); M.box(0.7, 0.012, 0.7, 0, 0.0, 0, "#8fd3ff"); M.use("main");
  for (const sx of [-0.36, 0.36]) for (const sz of [-0.36, 0.36]) M.cyl(0.03, 0.03, 0.012, sx, 0.14, sz, "#c9d1da", 8);
};
/** a floor of tiles (planar-motor tiles, pavers): `size` world units across, one-unit tiles, raised a little */
const tiles: Builder = (c) => {
  const M = c.M, a = accentOf(c), s = c.p.s || 1;
  const [w, d] = c.p.size ?? [6, 6];
  const nx = Math.max(1, Math.round(w)), nz = Math.max(1, Math.round(d));
  const lw = nx / s, ld = nz / s, cell = 1 / s;
  M.box(lw + 0.12 / s, 0.05, ld + 0.12 / s, 0, 0, 0, "#3a4250");
  const top = c.p.c?.[1] ?? "#4a5464";
  for (let i = 0; i < nx; i++) for (let j = 0; j < nz; j++) {
    const x = -lw / 2 + (i + 0.5) * cell, z = -ld / 2 + (j + 0.5) * cell;
    M.box(cell - 0.05 / s, 0.025, cell - 0.05 / s, x, 0.05, z, (i + j) % 2 ? top : shade(top, 1.06), { pat: PAT.metal });
  }
  M.use("emit");
  for (let i = 0; i <= nx; i += 2) for (let j = 0; j <= nz; j += 2) M.box(0.05 / s, 0.012, 0.05 / s, -lw / 2 + i * cell, 0.075, -ld / 2 + j * cell, a);
  M.use("main");
};

export const KIT3: Record<string, Builder> = { printer, placer, oven, scanner, storage, arm, carrier, tiles };
