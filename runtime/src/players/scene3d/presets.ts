/**
 * Level presets for scene3d. Each builds a group framed at scale 1 (about 20 units across) with the thing
 * the camera dives into sitting at the origin. Params come straight from site.yaml (`levels[].params`).
 *
 * biology: cell-field, cell, nucleus, helix (final: dock)
 * space:   galaxy, star-system, planet
 * generic: network, lattice, particles, gltf
 */
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { smooth } from "../../lib/util";

export interface LevelObj {
  group: THREE.Group;
  /** t = seconds, fin = final-beat progress (last level only), d = zoom distance from this level */
  update?: (t: number, fin: number, d: number) => void;
}
type Rnd = (a?: number, b?: number) => number;
export type Kit = ReturnType<typeof makeKit>;
export type Preset = (p: any, k: Kit) => LevelObj | Promise<LevelObj>;

const col = (v: any, d: string | number) => new THREE.Color(v ?? d).getHex();

export function makeKit(cfg: any, rnd: Rnd) {
  // Fluorescence look: additive fresnel glow, brighter at the silhouette like a membrane seen edge-on.
  function glow(color: number | string, { power = 2.4, base = 0.06, intensity = 1.2, opacity = 1 } = {}) {
    if (cfg.style === "solid") {
      return new THREE.MeshStandardMaterial({ color: new THREE.Color(color), roughness: 0.45, metalness: 0.1, transparent: opacity < 1, opacity });
    }
    return new THREE.ShaderMaterial({
      uniforms: { color: { value: new THREE.Color(color) }, power: { value: power }, base: { value: base },
                  intensity: { value: intensity }, opacity: { value: opacity } },
      vertexShader: `
        varying vec3 vN; varying vec3 vV;
        void main(){
          mat4 m = modelViewMatrix;
          #ifdef USE_INSTANCING
            m = modelViewMatrix * instanceMatrix;
          #endif
          vec4 mv = m * vec4(position, 1.0);
          vN = normalize(mat3(m) * normal); vV = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 color; uniform float power, base, intensity, opacity;
        varying vec3 vN; varying vec3 vV;
        void main(){
          float f = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), power);
          float a = (f * intensity + base) * opacity;
          gl_FragColor = vec4(color * a, a);
        }`,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    });
  }
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const g = c.getContext("2d")!, grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, "rgba(255,255,255,1)"); grd.addColorStop(0.35, "rgba(255,255,255,.45)"); grd.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
  const DOT = new THREE.CanvasTexture(c);

  function points(n: number, sample: (i: number) => THREE.Vector3, color: number, size: number, opacity = 1, colors?: (i: number) => THREE.Color) {
    const pos = new Float32Array(n * 3), cols = colors ? new Float32Array(n * 3) : null;
    for (let i = 0; i < n; i++) {
      const p = sample(i); pos.set([p.x, p.y, p.z], i * 3);
      if (cols) { const cc = colors!(i); cols.set([cc.r, cc.g, cc.b], i * 3); }
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    if (cols) geo.setAttribute("color", new THREE.BufferAttribute(cols, 3));
    return new THREE.Points(geo, new THREE.PointsMaterial({ color: cols ? 0xffffff : color, vertexColors: !!cols, size, map: DOT,
      transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true }));
  }
  const inSphere = (r: number) => { let v: THREE.Vector3; do { v = new THREE.Vector3(rnd(-1, 1), rnd(-1, 1), rnd(-1, 1)); } while (v.length() > 1); return v.multiplyScalar(r); };
  const tube = (pts: THREE.Vector3[], r: number, mat: THREE.Material, seg = 120) =>
    new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), seg, r, 6), mat);
  const sprite = (color: number, scale: number, opacity = 1) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: DOT, color, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending }));
    s.scale.setScalar(scale); return s;
  };
  return { glow, points, inSphere, tube, sprite, rnd, DOT, cfg };
}

// ================================================================ biology

const cellField: Preset = (p, k) => {
  const g = new THREE.Group();
  const n = p.count ?? 70, mem = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 40, 28), k.glow(col(p.membrane, "#45f0a0"), { power: 3.0, base: 0.012, intensity: 0.7 }), n);
  const nuc = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 28, 20), k.glow(col(p.nucleus, "#5b8cff"), { power: 1.6, base: 0.07, intensity: 0.65 }), n);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), pp = new THREE.Vector3(), placed: THREE.Vector3[] = [];
  for (let i = 0; i < n; i++) {
    if (i === 0) pp.set(0, 0, 0);
    else { let ok = false, tries = 0; do { pp.set(k.rnd(-22, 22), k.rnd(-13, 13), k.rnd(-14, 3)); ok = pp.length() > 3.4 && placed.every((o) => o.distanceTo(pp) > 3.1); } while (!ok && ++tries < 200); }
    placed.push(pp.clone());
    const r = i === 0 ? 1.7 : k.rnd(1.0, 1.6);
    q.setFromEuler(new THREE.Euler(k.rnd(0, 6), k.rnd(0, 6), k.rnd(0, 6)));
    s.set(r * k.rnd(1, 1.25), r, r * k.rnd(0.85, 1.1));
    mem.setMatrixAt(i, m.compose(pp, q, s));
    nuc.setMatrixAt(i, m.compose(pp.clone().add(new THREE.Vector3(k.rnd(-0.2, 0.2), k.rnd(-0.2, 0.2), 0)), q, s.clone().multiplyScalar(0.36)));
  }
  g.add(mem, nuc);
  g.add(k.points(260, () => new THREE.Vector3(k.rnd(-24, 24), k.rnd(-14, 14), k.rnd(-12, 6)), 0x9fffd0, 0.1, 0.35));
  return { group: g, update: (t) => { g.rotation.y = t * 0.02; } };
};

const cell: Preset = (p, k) => {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.SphereGeometry(9, 64, 48), k.glow(col(p.membrane, "#45f0a0"), { power: 3.0, base: 0.015, intensity: 1.3 })));
  g.add(new THREE.Mesh(new THREE.SphereGeometry(2.6, 48, 36), k.glow(col(p.nucleus, "#5b8cff"), { power: 1.4, base: 0.14, intensity: 1.2 })));
  g.add(new THREE.Mesh(new THREE.SphereGeometry(0.8, 24, 18), k.glow(0xb9c8ff, { power: 1.2, base: 0.25, intensity: 0.8 })));
  const mito = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.28, 1.0, 6, 16), k.glow(col(p.mito, "#ff7a45"), { power: 1.8, base: 0.08 }), 34);
  const m = new THREE.Matrix4();
  for (let i = 0; i < 34; i++) {
    const pp = k.inSphere(1).normalize().multiplyScalar(k.rnd(3.6, 7.8));
    mito.setMatrixAt(i, m.compose(pp, new THREE.Quaternion().setFromEuler(new THREE.Euler(k.rnd(0, 6), k.rnd(0, 6), k.rnd(0, 6))), new THREE.Vector3(1, k.rnd(0.8, 1.6), 1)));
  }
  g.add(mito);
  g.add(k.points(700, () => k.inSphere(1).normalize().multiplyScalar(k.rnd(3.2, 8.6)), 0xfff1a8, 0.16, 0.8));
  for (let j = 0; j < 7; j++) {
    const pts: THREE.Vector3[] = [], a0 = k.rnd(0, 6.28), tilt = k.rnd(-1, 1);
    for (let i = 0; i < 9; i++) { const a = a0 + i * 0.45, r = 3.2 + i * 0.12 + k.rnd(0, 0.3); pts.push(new THREE.Vector3(Math.cos(a) * r, tilt * r * 0.4 + k.rnd(-0.3, 0.3), Math.sin(a) * r)); }
    g.add(k.tube(pts, 0.05, k.glow(0xff9fe0, { power: 1.0, base: 0.3, intensity: 0.4, opacity: 0.7 }), 60));
  }
  return { group: g, update: (t) => { g.rotation.y = t * 0.05; } };
};

const nucleus: Preset = (p, k) => {
  const g = new THREE.Group();
  const blue = col(p.color, "#5b8cff");
  g.add(new THREE.Mesh(new THREE.SphereGeometry(9.5, 64, 48), k.glow(blue, { power: 3.2, base: 0.02, intensity: 1.2 })));
  for (let j = 0; j < (p.fibres ?? 34); j++) {
    const pts: THREE.Vector3[] = [], pp = k.inSphere(7.5);
    for (let i = 0; i < 30; i++) { pp.add(new THREE.Vector3(k.rnd(-1, 1), k.rnd(-1, 1), k.rnd(-1, 1)).multiplyScalar(0.9)); if (pp.length() > 8.5) pp.multiplyScalar(0.85); pts.push(pp.clone()); }
    g.add(k.tube(pts, k.rnd(0.06, 0.12), k.glow(j % 5 === 0 ? 0x8fb2ff : blue, { power: 1.0, base: 0.25, intensity: 0.5, opacity: 0.75 }), 160));
  }
  const locus: THREE.Vector3[] = [];
  for (let i = 0; i < 80; i++) { const a = i * 0.5; locus.push(new THREE.Vector3(Math.cos(a) * 0.7, (i - 40) * 0.05, Math.sin(a) * 0.7)); }
  g.add(k.tube(locus, 0.09, k.glow(col(p.target, "#ff4fd8"), { power: 0.8, base: 0.5, intensity: 0.8 }), 300));
  return { group: g, update: (t) => { g.rotation.y = t * 0.05; } };
};

const helix: Preset = (p, k) => {
  const g = new THREE.Group(), dna = new THREE.Group(), target = new THREE.Group();
  g.add(dna); dna.add(target);
  const BASE = [0x45f0a0, 0xff6b6b, 0xffd166, 0x5b8cff];
  const bp = p.pairs ?? 64, rise = 0.55, R = 2.1, turn = (2 * Math.PI) / 10.5, groove = Math.PI * 0.78;
  const strand = (off: number) => { const pts: THREE.Vector3[] = []; for (let i = 0; i <= bp * 4; i++) { const t = i / 4, a = t * turn + off; pts.push(new THREE.Vector3(Math.cos(a) * R, (t - bp / 2) * rise, Math.sin(a) * R)); } return pts; };
  for (const off of [0, groove]) dna.add(k.tube(strand(off), 0.22, k.glow(col(p.strand, "#7fe3ff"), { power: 1.4, base: 0.2, intensity: 1.0 }), 900));
  const rungGeo = new THREE.CylinderGeometry(0.11, 0.11, 1, 10);
  for (let i = 0; i < bp; i++) {
    const a = i * turn, y = (i - bp / 2) * rise;
    const p1 = new THREE.Vector3(Math.cos(a) * R, y, Math.sin(a) * R), p2 = new THREE.Vector3(Math.cos(a + groove) * R, y, Math.sin(a + groove) * R);
    const mid = p1.clone().lerp(p2, 0.5), b = Math.floor(k.rnd(0, 4)), pair = [1, 0, 3, 2][b];
    const isTarget = Math.abs(i - bp / 2) <= 4;
    for (const [from, c] of [[p1, BASE[b]], [p2, BASE[pair]]] as [THREE.Vector3, number][]) {
      const half = new THREE.Mesh(rungGeo, k.glow(c, { power: 0.9, base: 0.35, intensity: 0.9 }));
      const dir = mid.clone().sub(from); half.scale.set(1, dir.length(), 1);
      half.position.copy(from.clone().add(mid).multiplyScalar(0.5));
      half.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
      (isTarget ? target : dna).add(half);
    }
  }
  const mag = col(p.target, "#ff4fd8");
  const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(R + 0.55, R + 0.55, 9 * rise + 0.6, 48, 1, true), k.glow(mag, { power: 2.2, base: 0.02, intensity: 1.4, opacity: 0 }));
  target.add(sleeve);
  const molecule = new THREE.Group();
  const atoms = [[0, 0, 0], [0.9, 0.4, 0], [1.7, -0.1, 0.3], [-0.9, 0.3, 0.2], [-1.6, -0.4, -0.2], [0.2, 1.0, -0.5], [2.5, 0.4, 0.1]];
  const atomCol = [0xffffff, 0x7fe3ff, 0xffffff, mag, 0xffffff, 0xffd166, 0x7fe3ff];
  atoms.forEach((a, i) => { const s = new THREE.Mesh(new THREE.SphereGeometry(i === 0 ? 0.42 : 0.32, 24, 16), k.glow(atomCol[i], { power: 1.1, base: 0.45, intensity: 1.0 })); s.position.set(a[0], a[1], a[2]); molecule.add(s); });
  [[0, 1], [1, 2], [0, 3], [3, 4], [0, 5], [2, 6]].forEach(([i, j]) => {
    const a = new THREE.Vector3(...atoms[i] as [number, number, number]), b = new THREE.Vector3(...atoms[j] as [number, number, number]), d = b.clone().sub(a);
    const cyl = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, d.length(), 8), k.glow(0xdfe9f2, { power: 0.8, base: 0.4, intensity: 0.6 }));
    cyl.position.copy(a.clone().add(b).multiplyScalar(0.5)); cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()); molecule.add(cyl);
  });
  const molStart = new THREE.Vector3(11, 4, 6), molEnd = new THREE.Vector3(Math.cos(Math.PI * 0.39) * (R + 1.1), 0, Math.sin(Math.PI * 0.39) * (R + 1.1));
  molecule.position.copy(molStart);
  const dock = p.dock !== false;
  if (dock) g.add(molecule);
  g.rotation.z = -0.5;
  const sleeveMat = sleeve.material as THREE.ShaderMaterial;
  return {
    group: g,
    update(t, fin) {
      const glowK = smooth(0.05, 0.35, fin);
      if (sleeveMat.uniforms) sleeveMat.uniforms.opacity.value = glowK * (0.75 + 0.25 * Math.sin(t * 3));
      target.children.forEach((c: any) => { if (c !== sleeve && c.material?.uniforms) c.material.uniforms.intensity.value = 0.9 + glowK * 1.6; });
      const md = smooth(0.25, 0.85, fin);
      molecule.position.lerpVectors(molStart, molEnd, md);
      molecule.rotation.set(t * 0.6 * (1 - md), t * 0.4 * (1 - md) + md * 1.2, 0);
      molecule.visible = fin > 0.1;
      dna.rotation.y = -t * 0.25 * (1 - smooth(0.5, 0.9, fin) * 0.9);
    },
  };
};

// ================================================================ space

const galaxy: Preset = (p, k) => {
  const g = new THREE.Group(), body = new THREE.Group();
  const arms = p.arms ?? 4, R = p.radius ?? 15, n = p.stars ?? 60000;
  const core = new THREE.Color(p.core ?? "#ffd29a"), arm = new THREE.Color(p.arm ?? "#7ea6ff"), hot = new THREE.Color(p.hot ?? "#c3a6ff");
  // the star we dive into sits on arm 0 at 55% radius; the galaxy is offset so it lands on the origin
  const r0 = R * 0.55, a0 = r0 * 0.42;
  const target = new THREE.Vector3(Math.cos(a0) * r0, 0, Math.sin(a0) * r0);
  const tmp = new THREE.Color();
  body.add(k.points(n, (i) => {
    const r = Math.pow(k.rnd(), 1.6) * R, a = (i % arms) / arms * Math.PI * 2 + r * 0.42 + k.rnd(-0.35, 0.35) * (1.2 - r / R);
    const spread = 0.25 + 0.9 * (1 - r / R);
    return new THREE.Vector3(Math.cos(a) * r + k.rnd(-spread, spread), k.rnd(-0.35, 0.35) * (1 - r / R * 0.7), Math.sin(a) * r + k.rnd(-spread, spread));
  }, 0xffffff, p.starSize ?? 0.12, 1.0, () => {
    const u = k.rnd();
    return tmp.copy(core).lerp(arm, Math.min(1, u * 1.4)).lerp(hot, k.rnd() < 0.08 ? 0.8 : 0).clone();
  }));
  body.add(k.points(4000, () => k.inSphere(1).multiply(new THREE.Vector3(2.2, 0.7, 2.2)), col(p.core, "#ffd29a"), 0.09, 0.45));
  body.add(k.sprite(col(p.core, "#ffcf8a"), 4.5, 0.28));
  // dust lanes: dark-ish violet haze along the arms adds depth without washing out the core
  body.add(k.points(9000, (i) => {
    const r = R * (0.25 + 0.75 * k.rnd()), a = (i % arms) / arms * Math.PI * 2 + r * 0.42 + 0.18;
    return new THREE.Vector3(Math.cos(a) * r + k.rnd(-0.5, 0.5), k.rnd(-0.12, 0.12), Math.sin(a) * r + k.rnd(-0.5, 0.5));
  }, col(p.haze, "#6d5cff"), 0.35, 0.05));
  body.position.copy(target).multiplyScalar(-1);
  g.add(body);
  g.add(k.sprite(col(p.target, "#fff1c9"), 1.0, 1), k.sprite(col(p.target, "#ffd9a0"), 2.6, 0.35));
  g.rotation.set(p.tilt ?? 0.9, 0, 0.25);
  return { group: g, update: (t) => { g.rotation.y = Math.sin(t * 0.05) * 0.08; } };
};

const starSystem: Preset = (p, k) => {
  const g = new THREE.Group();
  const star = new THREE.Vector3(...((p.star ?? [-9, 0, -3]) as [number, number, number]));
  const orbitR = star.length();
  const sun = new THREE.Group(); sun.position.copy(star);
  sun.add(new THREE.Mesh(new THREE.SphereGeometry(1.6, 48, 32), k.glow(col(p.sun, "#ffb45a"), { power: 0.9, base: 0.9, intensity: 1.2 })));
  sun.add(k.sprite(col(p.sun, "#ffb45a"), 14, 0.8), k.sprite(0xffffff, 4, 0.9));
  g.add(sun);
  const ringMat = new THREE.LineBasicMaterial({ color: col(p.orbit, "#a98bff"), transparent: true, opacity: 0.35 });
  const radii = p.orbits ?? [3.2, 5.6, orbitR, 13.5, 17.5];
  const planets: { mesh: THREE.Object3D; r: number; a: number; w: number }[] = [];
  radii.forEach((r: number, i: number) => {
    const pts: THREE.Vector3[] = [];
    for (let j = 0; j <= 160; j++) { const a = (j / 160) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r).add(star)); }
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), ringMat));
    const isTarget = Math.abs(r - orbitR) < 1e-3;
    const size = isTarget ? 0.7 : k.rnd(0.25, 0.6);
    const m = new THREE.Mesh(new THREE.SphereGeometry(size, 32, 24), k.glow(isTarget ? col(p.planet, "#5fb6ff") : [0xd9a873, 0xbfc7d6, 0xe3c48f, 0x9fd0ff][i % 4],
      { power: 1.4, base: 0.35, intensity: 1.1 }));
    const a = isTarget ? Math.atan2(-star.z, -star.x) : k.rnd(0, 6.28);
    planets.push({ mesh: m, r, a, w: isTarget ? 0 : 0.6 / Math.pow(r, 1.2) });
    g.add(m);
  });
  g.add(k.points(400, () => k.inSphere(1).multiply(new THREE.Vector3(9, 0.3, 9)).add(star).add(new THREE.Vector3(0, 0, 0)).multiplyScalar(1.6), 0xc9b8ff, 0.06, 0.4));
  g.rotation.set(p.tilt ?? 0.42, 0, 0);
  return {
    group: g,
    update(t) {
      for (const pl of planets) {
        const a = pl.a + t * pl.w;
        pl.mesh.position.set(Math.cos(a) * pl.r, 0, Math.sin(a) * pl.r).add(star);
      }
    },
  };
};

const NOISE = `
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
float snoise(vec3 v){const vec2 C=vec2(1./6.,1./3.);const vec4 D=vec4(0.,.5,1.,2.);vec3 i=floor(v+dot(v,C.yyy));vec3 x0=v-i+dot(i,C.xxx);
vec3 g=step(x0.yzx,x0.xyz);vec3 l=1.-g;vec3 i1=min(g.xyz,l.zxy);vec3 i2=max(g.xyz,l.zxy);vec3 x1=x0-i1+C.xxx;vec3 x2=x0-i2+C.yyy;vec3 x3=x0-D.yyy;
i=mod289(i);vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
float n_=.142857142857;vec3 ns=n_*D.wyz-D.xzx;vec4 j=p-49.*floor(p*ns.z*ns.z);vec4 x_=floor(j*ns.z);vec4 y_=floor(j-7.*x_);
vec4 x=x_*ns.x+ns.yyyy;vec4 y=y_*ns.x+ns.yyyy;vec4 h=1.-abs(x)-abs(y);vec4 b0=vec4(x.xy,y.xy);vec4 b1=vec4(x.zw,y.zw);
vec4 s0=floor(b0)*2.+1.;vec4 s1=floor(b1)*2.+1.;vec4 sh=-step(h,vec4(0.));vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
vec3 p0=vec3(a0.xy,h.x);vec3 p1=vec3(a0.zw,h.y);vec3 p2=vec3(a1.xy,h.z);vec3 p3=vec3(a1.zw,h.w);
vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);m=m*m;return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));}
float fbm(vec3 p){float f=0.,a=.5;for(int i=0;i<6;i++){f+=a*snoise(p);p*=2.03;a*=.5;}return f;}`;

const planet: Preset = (p, k) => {
  const g = new THREE.Group(), R = p.radius ?? 6;
  const light = new THREE.Vector3(...((p.light ?? [-1, 0.25, 0.35]) as [number, number, number])).normalize();
  const uniforms = {
    t: { value: 0 }, light: { value: light }, opacity: { value: 1 }, seed: { value: p.seed ?? 3.7 },
    ocean: { value: new THREE.Color(p.ocean ?? "#0b2a5b") }, land: { value: new THREE.Color(p.land ?? "#5c7a3a") },
    desert: { value: new THREE.Color(p.desert ?? "#b89a64") }, ice: { value: new THREE.Color("#eef4ff") },
    city: { value: new THREE.Color(p.city ?? "#ffb35c") }, seaLevel: { value: p.sea ?? 0.0 },
  };
  const surf = new THREE.ShaderMaterial({
    uniforms, transparent: true,
    vertexShader: `varying vec3 vP; varying vec3 vN; varying vec3 vW;
      void main(){ vP = position; vN = normalize(mat3(modelMatrix) * normal); vec4 w = modelMatrix * vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: NOISE + `
      uniform vec3 light, ocean, land, desert, ice, city; uniform float t, opacity, seed, seaLevel;
      varying vec3 vP; varying vec3 vN; varying vec3 vW;
      float warped(vec3 p){ vec3 q = vec3(fbm(p + seed), fbm(p + vec3(5.2, 1.3, 2.8) + seed), fbm(p + vec3(1.7, 9.2, 4.1) + seed)); return fbm(p + 1.6 * q); }
      void main(){
        vec3 n = normalize(vP);
        float h = warped(n * 1.25);                       // continents
        float detail = fbm(n * 9.0 + seed * 3.);          // mountains, coastlines
        float lat = abs(n.y);
        float landMask = smoothstep(seaLevel - 0.01, seaLevel + 0.02, h + detail * 0.06);
        float depth = clamp((seaLevel - h) * 3.0, 0., 1.);
        vec3 sea = mix(ocean * 1.6 + vec3(0.0, 0.08, 0.1), ocean * 0.55, depth);
        float dry = smoothstep(-0.1, 0.35, fbm(n * 2.2 + seed * 2.) + (0.35 - lat) * 0.6);
        vec3 ground = mix(land * (0.7 + 0.5 * detail), desert * (0.85 + 0.3 * detail), dry);
        ground = mix(ground, vec3(0.42, 0.38, 0.34), smoothstep(0.35, 0.6, h + detail * 0.3) * 0.6);   // highlands
        vec3 c = mix(sea, ground, landMask);
        c = mix(c, ice, smoothstep(0.74, 0.86, lat + detail * 0.08));
        // clouds: two warped layers drifting at different speeds
        vec3 cn = n * 2.3 + vec3(t * 0.004, 0., t * 0.002);
        float clouds = smoothstep(0.05, 0.55, warped(cn + 11.) * 0.9 + fbm(n * 7. + t * 0.003) * 0.25);
        vec3 N = normalize(vN);
        float ndl = dot(N, light);
        float diff = smoothstep(-0.08, 1.0, ndl);
        vec3 lit = c * (0.015 + 1.15 * diff);
        float night = smoothstep(0.05, -0.25, ndl);
        float lights = landMask * smoothstep(0.55, 0.9, snoise(n * 55. + seed)) * smoothstep(0.3, 0.6, fbm(n * 6. + seed)) * (1. - lat);
        lit += city * lights * night * (1. - clouds) * 1.4;
        vec3 V = normalize(cameraPosition - vW);
        float spec = pow(max(dot(reflect(-light, N), V), 0.), 60.) * (1. - landMask) * diff;
        lit += vec3(1., 0.95, 0.85) * spec * 0.7;
        lit = mix(lit, vec3(1.) * (0.02 + 1.05 * diff), clouds * 0.9);
        float rim = pow(1. - max(dot(N, V), 0.), 3.);
        lit += vec3(0.35, 0.6, 1.0) * rim * diff * 0.6;   // atmospheric scattering at the limb
        gl_FragColor = vec4(lit, opacity);
      }`,
  });
  g.add(new THREE.Mesh(new THREE.SphereGeometry(R, 128, 96), surf));
  const atmo = new THREE.ShaderMaterial({
    uniforms: { light: { value: light }, color: { value: new THREE.Color(p.atmosphere ?? "#5fb6ff") }, opacity: { value: 1 } },
    vertexShader: `varying vec3 vN; varying vec3 vV; void main(){ vec4 mv = modelViewMatrix * vec4(position,1.); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform vec3 color; uniform float opacity; varying vec3 vN; varying vec3 vV;
      void main(){ float f = pow(1. - abs(dot(vN, vV)), 2.6); gl_FragColor = vec4(color * f * 1.6, f * opacity); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.BackSide,
  });
  const shell = new THREE.Mesh(new THREE.SphereGeometry(R * 1.06, 96, 64), atmo);
  g.add(shell);
  let moon: THREE.Mesh | null = null;
  if (p.moon !== false) {
    moon = new THREE.Mesh(new THREE.SphereGeometry(R * 0.22, 48, 32), new THREE.MeshBasicMaterial({ color: 0x9a9aa6, transparent: true }));
    g.add(moon);
  }
  const ring: THREE.Mesh[] = [];
  if (p.satellites) {
    for (let i = 0; i < p.satellites; i++) {
      const s = k.sprite(col(p.satColor, "#ffffff"), 0.35, 0.9);
      (s as any).userData = { r: R * k.rnd(1.15, 1.5), a: k.rnd(0, 6.28), w: k.rnd(0.15, 0.35), tilt: k.rnd(-0.9, 0.9) };
      g.add(s); ring.push(s as any);
    }
  }
  g.rotation.z = 0.35;
  return {
    group: g,
    update(t) {
      uniforms.t.value = t;
      g.children[0].rotation.y = t * 0.03;
      if (moon) moon.position.set(Math.cos(t * 0.08) * R * 2.4, Math.sin(t * 0.08) * R * 0.5, Math.sin(t * 0.08) * R * 2.4);
      for (const s of ring) { const u = (s as any).userData; const a = u.a + t * u.w; s.position.set(Math.cos(a) * u.r, Math.sin(a) * u.r * u.tilt, Math.sin(a) * u.r); }
    },
  };
};

// ================================================================ generic

const network: Preset = (p, k) => {
  const g = new THREE.Group(), n = p.nodes ?? 160, R = p.radius ?? 9;
  const nodes: THREE.Vector3[] = [new THREE.Vector3()];
  for (let i = 1; i < n; i++) nodes.push(p.shape === "plane" ? new THREE.Vector3(k.rnd(-R * 1.6, R * 1.6), k.rnd(-R, R), k.rnd(-2, 2)) : k.inSphere(R));
  const nodeMat = k.glow(col(p.color, "#7fe3ff"), { power: 1.0, base: 0.5, intensity: 1.0 });
  const geo = new THREE.SphereGeometry(1, 16, 12);
  const inst = new THREE.InstancedMesh(geo, nodeMat, n);
  const m = new THREE.Matrix4();
  nodes.forEach((v, i) => inst.setMatrixAt(i, m.compose(v, new THREE.Quaternion(), new THREE.Vector3().setScalar(i === 0 ? 0.55 : k.rnd(0.08, 0.2)))));
  g.add(inst);
  const edges: number[] = [], pairs: [number, number][] = [];
  nodes.forEach((a, i) => {
    const near = nodes.map((b, j) => [a.distanceTo(b), j] as [number, number]).filter(([d, j]) => j !== i && d < (p.link ?? R * 0.42)).sort((x, y) => x[0] - y[0]).slice(0, 3);
    near.forEach(([, j]) => { if (i < j) { edges.push(a.x, a.y, a.z, nodes[j].x, nodes[j].y, nodes[j].z); pairs.push([i, j]); } });
  });
  const eg = new THREE.BufferGeometry(); eg.setAttribute("position", new THREE.Float32BufferAttribute(edges, 3));
  g.add(new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: col(p.edge, "#3c6e8f"), transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false })));
  const pulses = Array.from({ length: Math.min(60, pairs.length) }, () => {
    const s = k.sprite(col(p.pulse, "#ffffff"), 0.35, 1); g.add(s);
    return { s, pair: pairs[Math.floor(k.rnd(0, pairs.length))], off: k.rnd(0, 1), sp: k.rnd(0.2, 0.6) };
  });
  g.add(k.sprite(col(p.color, "#7fe3ff"), 3, 0.7));
  return {
    group: g,
    update(t) {
      g.rotation.y = t * 0.04;
      for (const q of pulses) { const f = (t * q.sp + q.off) % 1; q.s.position.lerpVectors(nodes[q.pair[0]], nodes[q.pair[1]], f); }
    },
  };
};

const lattice: Preset = (p, k) => {
  const g = new THREE.Group(), n = p.size ?? 5, a = p.spacing ?? 2.4;
  const atomA = k.glow(col(p.a, "#7fe3ff"), { power: 1.0, base: 0.45, intensity: 1.0 }), atomB = k.glow(col(p.b, "#ffb45a"), { power: 1.0, base: 0.45, intensity: 1.0 });
  const bond = k.glow(col(p.bond, "#4a6a8a"), { power: 0.8, base: 0.25, intensity: 0.4, opacity: 0.7 });
  const sph = new THREE.SphereGeometry(0.32, 20, 14), cyl = new THREE.CylinderGeometry(0.05, 0.05, a, 6);
  const h = (n - 1) / 2;
  for (let x = 0; x < n; x++) for (let y = 0; y < n; y++) for (let z = 0; z < n; z++) {
    const pos = new THREE.Vector3((x - h) * a, (y - h) * a, (z - h) * a);
    const s = new THREE.Mesh(sph, (x + y + z) % 2 ? atomB : atomA); s.position.copy(pos); g.add(s);
    if (x < n - 1) { const c = new THREE.Mesh(cyl, bond); c.position.copy(pos).add(new THREE.Vector3(a / 2, 0, 0)); c.rotation.z = Math.PI / 2; g.add(c); }
    if (y < n - 1) { const c = new THREE.Mesh(cyl, bond); c.position.copy(pos).add(new THREE.Vector3(0, a / 2, 0)); g.add(c); }
    if (z < n - 1) { const c = new THREE.Mesh(cyl, bond); c.position.copy(pos).add(new THREE.Vector3(0, 0, a / 2)); c.rotation.x = Math.PI / 2; g.add(c); }
  }
  return { group: g, update: (t) => { g.rotation.set(0.5 + Math.sin(t * 0.1) * 0.1, t * 0.08, 0); } };
};

const particles: Preset = (p, k) => {
  const g = new THREE.Group();
  const a = new THREE.Color(p.color ?? "#a98bff"), b = new THREE.Color(p.color2 ?? "#5fb6ff"), tmp = new THREE.Color();
  g.add(k.points(p.count ?? 20000, () => k.inSphere(1).multiply(new THREE.Vector3(14, 7, 10)), 0xffffff, 0.12, 0.7,
    () => tmp.copy(a).lerp(b, k.rnd()).clone()));
  g.add(k.sprite(col(p.core, "#ffffff"), 2.2, 0.9));
  return { group: g, update: (t) => { g.rotation.y = t * 0.02; } };
};

const gltf: Preset = async (p) => {
  const g = new THREE.Group();
  const loaded = await new GLTFLoader().loadAsync(p.url);
  const model = loaded.scene;
  const box = new THREE.Box3().setFromObject(model), size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  const s = (p.size ?? 12) / Math.max(size.x, size.y, size.z);
  model.position.sub(center).multiplyScalar(s); model.scale.setScalar(s);
  g.add(model);
  return { group: g, update: (t) => { g.rotation.y = t * (p.spin ?? 0.1); } };
};

export const PRESETS: Record<string, Preset> = {
  "cell-field": cellField, cell, nucleus, helix,
  galaxy, "star-system": starSystem, planet,
  network, lattice, particles, gltf,
};
