/**
 * diorama: a miniature world, live. The plan (engine/diorama/) holds the ground, the props, the places and the camera's
 * beats; here three.js draws it (toy-proportioned props baked into a few meshes, still water, a cut-edge base on a
 * table, a high soft sun), a depth-of-field pass makes it read as a tilt-shift model, and scroll drives the camera:
 * it orbits the whole diorama, dives to the place where a step's content sits, lifts out and travels on. The pointer
 * turns the view a little; reduced motion shows one still view per place; the page scrolls normally throughout.
 */
import * as THREE from "three";
import { readElements } from "../lib/elements";
import type { PlayerFactory } from "../lib/types";
import { cssVar, isMobile, reducedMotion } from "../lib/util";
import type { DioramaCfg, Plan, PropRec } from "./diorama/types";
import { Mesher, hash } from "./diorama/mesher";
import { propMaterial } from "./diorama/materials";
import { buildTable, buildTerrain } from "./diorama/terrain";
import { builderFor, type KitCtx } from "./diorama/kit";
import { Post } from "./diorama/post";
import { Rig, type CamState } from "./diorama/camera";

const SUN: Record<string, { dir: [number, number, number]; color: string; i: number; sky: string; ground: string; hemi: number; env: number; exposure: number }> = {
  golden: { dir: [-0.55, 0.62, 0.62], color: "#ffd6a0", i: 3.3, sky: "#c6dcff", ground: "#e9cfa6", hemi: 0.8, env: 0.7, exposure: 1.02 },
  morning: { dir: [0.62, 0.5, 0.55], color: "#fff0dc", i: 3.0, sky: "#d3e6ff", ground: "#dfe6d0", hemi: 1.05, env: 0.8, exposure: 1.0 },
  noon: { dir: [0.18, 0.95, 0.3], color: "#ffffff", i: 3.2, sky: "#c9defa", ground: "#e8e2d4", hemi: 1.0, env: 0.8, exposure: 0.98 },
  dusk: { dir: [-0.75, 0.24, 0.42], color: "#ffa66b", i: 2.7, sky: "#8fa3e0", ground: "#d89a82", hemi: 0.9, env: 0.7, exposure: 1.05 },
};

function gradientEnv(renderer: THREE.WebGLRenderer, sky: string, ground: string): THREE.Texture {
  const s = new THREE.Scene();
  const g = new THREE.SphereGeometry(50, 24, 16);
  const pos = g.getAttribute("position"), col: number[] = [];
  const top = new THREE.Color(sky), hor = new THREE.Color("#fff3df"), bot = new THREE.Color(ground);
  for (let i = 0; i < pos.count; i++) {
    const y = pos.getY(i) / 50;
    const c = y > 0 ? hor.clone().lerp(top, Math.pow(y, 0.6)) : hor.clone().lerp(bot, Math.pow(-y, 0.8));
    col.push(c.r, c.g, c.b);
  }
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  s.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide })));
  // a bright patch for the sun so glass and water have something to catch
  const sun = new THREE.Mesh(new THREE.SphereGeometry(6, 12, 8), new THREE.MeshBasicMaterial({ color: new THREE.Color(4, 3.4, 2.6) }));
  sun.position.set(-20, 28, 30); s.add(sun);
  const pm = new THREE.PMREMGenerator(renderer);
  const tex = pm.fromScene(s, 0.03).texture;
  pm.dispose();
  return tex;
}

const signWidth = (text: string) => 1.2 + Math.min(1.5, text.length * 0.085);
function signTexture(text: string, font: string, accent: string): { tex: THREE.CanvasTexture; w: number } {
  const c = document.createElement("canvas");
  c.width = 640; c.height = 200;
  const g = c.getContext("2d")!;
  const rr = (x: number, y: number, w: number, h: number, r: number) => { g.beginPath(); g.roundRect(x, y, w, h, r); };
  g.fillStyle = "#fffaf0"; rr(6, 6, 628, 188, 26); g.fill();
  g.lineWidth = 10; g.strokeStyle = accent; rr(14, 14, 612, 172, 20); g.stroke();
  g.fillStyle = "#2b2f36"; g.textAlign = "center"; g.textBaseline = "middle";
  let size = 92;
  do { g.font = `700 ${size}px ${font}`; size -= 4; } while (g.measureText(text).width > 540 && size > 28);
  g.fillText(text, 320, 104);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return { tex, w: signWidth(text) };
}

const factory: PlayerFactory = async (cfgIn, ctx) => {
  const cfg = cfgIn as DioramaCfg;
  const mobile = isMobile();
  const visual = ctx.visual;
  const table = cfg.look.table || cssVar("--bg") || "#f3ead9";
  visual.style.background = table;

  // a flat map of the world stands in until the live scene is up (and stays if WebGL is missing)
  let mapImg: HTMLImageElement | null = null;
  if (cfg.map) { mapImg = new Image(); mapImg.className = "ss-dio-map"; mapImg.alt = ""; mapImg.src = cfg.map; visual.appendChild(mapImg); }

  const canvas = document.createElement("canvas");
  visual.appendChild(canvas);
  const gl = canvas.getContext("webgl2", { antialias: false, powerPreference: "high-performance", preserveDrawingBuffer: true, alpha: false });
  if (!gl) throw new Error("no webgl2");
  const renderer = new THREE.WebGLRenderer({ canvas, context: gl, antialias: false, powerPreference: "high-performance", preserveDrawingBuffer: true });
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  ctx.progress(0.05);
  const [plan, groundTex] = await Promise.all([
    fetch(cfg.plan).then((r) => r.json() as Promise<Plan>),
    new Promise<THREE.Texture>((res, rej) => new THREE.TextureLoader().load(cfg.ground, res, undefined, rej)),
  ]);
  ctx.progress(0.5);
  groundTex.colorSpace = THREE.SRGBColorSpace;
  groundTex.flipY = false;
  groundTex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  groundTex.generateMipmaps = true;
  groundTex.minFilter = THREE.LinearMipmapLinearFilter;

  const R = plan.size / 2;
  const sun = SUN[cfg.look.sun] || SUN.golden;
  renderer.toneMappingExposure = sun.exposure;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(table);
  scene.fog = new THREE.FogExp2(new THREE.Color(table), 0.0035);
  scene.environment = gradientEnv(renderer, sun.sky, sun.ground);
  scene.environmentIntensity = sun.env;

  // ---- light
  const key = new THREE.DirectionalLight(new THREE.Color(sun.color), sun.i);
  const sd = new THREE.Vector3(...sun.dir).normalize();
  key.position.copy(sd).multiplyScalar(R * 4);
  key.castShadow = true;
  const sm = mobile ? 2048 : 4096;
  key.shadow.mapSize.set(sm, sm);
  const sc = key.shadow.camera as THREE.OrthographicCamera;
  sc.left = sc.bottom = -R * 1.25; sc.right = sc.top = R * 1.25; sc.near = R * 1.5; sc.far = R * 8;
  key.shadow.bias = -0.0003; key.shadow.normalBias = 0.03;
  scene.add(key, key.target);
  scene.add(new THREE.HemisphereLight(new THREE.Color(sun.sky), new THREE.Color(sun.ground), sun.hemi));

  // ---- the world
  const uni = { uTime: { value: 0 }, uCloud: { value: reducedMotion ? 0 : 1 } };
  const terrain = buildTerrain(plan, groundTex, uni, mobile);
  scene.add(terrain.group);
  if (terrain.water) {
    (terrain.water.uniforms.uSun.value as THREE.Vector3).copy(sd);
    (terrain.water.uniforms.uSunCol.value as THREE.Color).set(sun.color);
    (terrain.water.uniforms.uSky.value as THREE.Color).set(sun.sky);
  }
  scene.add(buildTable(table, terrain.tableY, R * 1.05));

  const mats = { main: propMaterial("main"), glass: propMaterial("glass"), emit: propMaterial("emit") };
  (mats.main as THREE.MeshStandardMaterial).side = THREE.DoubleSide;
  const world = new THREE.Group();
  scene.add(world);
  const anims: { o: THREE.Object3D; tick: (o: any, t: number) => void }[] = [];
  const palette = plan.palette && plan.palette.length ? plan.palette : ["#d9503a", "#2f8a9d", "#e8a23a", "#c4433a", "#3d6fa5"];

  const M = new Mesher();
  const mesh = (m: Mesher, parent: THREE.Object3D, shadows = true) => {
    const gs = m.geometries();
    (["main", "glass", "emit"] as const).forEach((k) => {
      const g = gs[k]; if (!g) return;
      const me = new THREE.Mesh(g, mats[k]);
      me.castShadow = shadows && k !== "emit"; me.receiveShadow = k !== "emit";
      parent.add(me);
    });
  };
  const signs: { p: PropRec }[] = [];
  const font = cssVar("--font-display") || "Georgia, serif";
  const accent = cssVar("--accent") || "#d9503a";
  for (const p of plan.props) {
    if (p.k === "sign") { signs.push({ p }); }
    const kctx: KitCtx = {
      M, p, palette,
      pick: (arr, salt = 0) => arr[Math.floor(hash(p.x * 13.1 + p.z * 7.7 + salt * 3.3) * arr.length) % arr.length],
      rnd: (salt = 0) => hash(p.x * 9.1 + p.z * 5.3 + salt),
      part(lx, ly, lz, build, tick) {
        const pm = new Mesher();
        pm.begin(0, 0, 0, 0, 1);
        build(pm);
        const outer = new THREE.Group();
        const v = new THREE.Vector3(lx, ly, lz).applyMatrix4(M.m);
        outer.position.copy(v); outer.rotation.y = p.r; outer.scale.setScalar(p.s);
        const inner = new THREE.Group();
        outer.add(inner);
        mesh(pm, inner);
        world.add(outer);
        if (tick) anims.push({ o: inner, tick });
      },
      add(obj, lx, ly, lz, tick) {
        const outer = new THREE.Group();
        outer.position.copy(new THREE.Vector3(lx, ly, lz).applyMatrix4(M.m)); outer.rotation.y = p.r; outer.scale.setScalar(p.s);
        outer.add(obj); world.add(outer);
        if (tick) anims.push({ o: obj, tick });
      },
    };
    M.begin(p.x, p.y, p.z, p.r, p.s);
    if (p.k === "sign") {
      const bw = signWidth(p.text || "");
      M.cyl(0.045, 0.055, 1.35, -bw / 2 + 0.2, 0, 0, "#6e4b2e", 8);
      M.cyl(0.045, 0.055, 1.35, bw / 2 - 0.2, 0, 0, "#6e4b2e", 8);
      M.rbox(bw + 0.08, 0.54, 0.07, 0, 0.8, 0, "#fffaf0", 0.03);
    } else {
      builderFor(p.k)(kctx);
    }
  }
  mesh(M, world);
  // sign faces: a text plane on each sign's board
  await (document as any).fonts?.ready;
  for (const { p } of signs) {
    const { tex, w } = signTexture(p.text || "", font, accent);
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(w, 0.5), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.85 }));
    const m4 = new THREE.Matrix4().makeTranslation(p.x, p.y, p.z).multiply(new THREE.Matrix4().makeRotationY(p.r)).multiply(new THREE.Matrix4().makeScale(p.s, p.s, p.s));
    plane.applyMatrix4(m4); plane.translateY(0.8 + 0.27); plane.translateZ(0.045);
    plane.castShadow = false; plane.receiveShadow = true;
    world.add(plane);
  }
  ctx.progress(0.8);

  // ---- camera, post
  const camera = new THREE.PerspectiveCamera(plan.camera.fov, 1, 1, 420);
  const post = new Post(renderer, { tilt: cfg.look.tilt_shift * (mobile ? 0.7 : 1), saturation: cfg.look.saturation, vignette: cfg.look.vignette, grain: cfg.look.grain, mobile });
  let W = 1, H = 1, aspect = 1;
  const fovFor = () => Math.min(62, plan.camera.fov * (aspect < 0.9 ? 1.3 : 1));
  const wideDist = () => {
    const f = fovFor(), tv = Math.tan(THREE.MathUtils.degToRad(f / 2)), th = tv * aspect;
    const sideRoom = aspect > 1.05 && ctx.data.layout !== "overlay" ? 0.66 : (aspect < 0.9 ? 0.95 : 0.84);
    const byW = plan.camera.fit / (th * sideRoom);
    const byH = (plan.camera.fit * Math.sin(THREE.MathUtils.degToRad(plan.camera.pitch)) + 4.5) / (tv * 0.8);
    return Math.max(byW, byH);
  };
  const rig = new Rig(plan.camera, wideDist, cfg.side, () => (mobile ? 0 : 0.17), () => (mobile || aspect < 1.05 ? 0 : cfg.side * 0.16),
    () => Math.tan(THREE.MathUtils.degToRad(plan.camera.fov / 2)) / Math.tan(THREE.MathUtils.degToRad(fovFor() / 2)));
  const state: CamState = { yaw: 0, pitch: 30, dist: 40, target: new THREE.Vector3(), shift: 0, open: 1, beat: 0 };
  const drift = plan.camera.drift;

  function resize() {
    W = visual.clientWidth || innerWidth; H = visual.clientHeight || innerHeight;
    aspect = W / Math.max(1, H);
    // the scene is drawn at the screen's own pixels up to a budget (the depth of field hides the rest), and the budget
    // shrinks by itself when the machine cannot keep up (see adapt())
    const budget = (mobile ? 1.15e6 : 2.3e6);
    const pr = Math.max(0.45, Math.min(devicePixelRatio || 1, 1.5, Math.sqrt(budget / Math.max(1, W * H))) * quality);
    renderer.setPixelRatio(1);
    renderer.setSize(Math.round(W * pr), Math.round(H * pr), false);
    canvas.style.width = "100%"; canvas.style.height = "100%";
    post.resize(W, H, pr);
    camera.aspect = aspect; camera.fov = fovFor();
    camera.updateProjectionMatrix();
    last = "";
  }
  let last = "";
  let quality = 1, slow = 0, fast = 0, lastT = 0;
  /** dynamic resolution: a frame budget of ~30 ms; a slow stretch lowers the pixel count, a long fast one raises it again */
  function adapt(t: number) {
    const dt = (t - lastT) * 1000; lastT = t;
    if (dt <= 0 || dt > 250) return;
    if (dt > 34) { slow++; fast = 0; } else if (dt < 15) { fast++; slow = 0; } else { slow = 0; fast = 0; }
    if (slow > 24 && quality > 0.5) { quality = Math.max(0.5, quality * 0.8); slow = 0; resize(); }
    else if (fast > 240 && quality < 1) { quality = Math.min(1, quality * 1.15); fast = 0; resize(); }
  }

  // ---- pins: the places' names over the diorama while the camera is up (buttons: jump to the step)
  const pinsEl = document.createElement("div");
  pinsEl.className = "ss-dio-pins";
  visual.appendChild(pinsEl);
  const stepEls = [...ctx.section.querySelectorAll<HTMLElement>(".ss-step, .ss-caption")];
  const order = readElements(ctx.section, ctx.data).map((e) => e.step);     // page order -> step (lib/elements.ts)
  const pins = plan.places.map((pl, i) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "ss-dio-pin"; b.setAttribute("aria-label", `Go to ${pl.name}`);
    b.innerHTML = `<i>${i + 1}</i><span>${pl.name.replace(/</g, "&lt;")}</span>`;
    const si = plan.steps.findIndex((s) => s === i);
    b.addEventListener("click", () => {
      const el = stepEls[order.indexOf(si)];
      if (el) el.scrollIntoView({ block: "center", behavior: reducedMotion ? "auto" : "smooth" });
    });
    pinsEl.appendChild(b);
    return { el: b, v: new THREE.Vector3(pl.x, pl.y + pl.h + 1.0, pl.z), o: -1 };
  });

  const v3 = new THREE.Vector3();
  const pos = new THREE.Vector3();
  let mxs = 0, mys = 0, first = true;
  function frame(p: number, active: number, t: number, mx: number, my: number) {
    if (reducedMotion) {
      const beatIdx = active >= 0 ? active : Math.min(plan.camera.beats.length - 1, plan.camera.beats.findIndex((b) => p <= b.b));
      rig.still(Math.max(0, beatIdx), state);
    } else rig.at(p, state);
    mxs += (mx - mxs) * 0.06; mys += (my - mys) * 0.06;
    const k = reducedMotion ? 0 : drift;
    const yaw = THREE.MathUtils.degToRad(state.yaw + mxs * 12 * k + Math.sin(t * 0.17) * 1.4 * k);
    const pitch = THREE.MathUtils.degToRad(Math.max(5, state.pitch - mys * 5 * k + Math.sin(t * 0.13) * 0.8 * k));
    const dist = state.dist * (1 + Math.sin(t * 0.21) * 0.008 * k);
    pos.set(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch)).multiplyScalar(dist).add(state.target);
    const floor = Math.max(0, terrain.heightAt(pos.x, pos.z)) + 0.9;
    if (pos.y < floor) pos.y = floor;
    camera.position.copy(pos);
    camera.lookAt(state.target);
    const shiftX = state.shift * W;
    const shiftY = mobile ? -(0.1 + 0.1 * (1 - state.open)) * H : 0;
    camera.setViewOffset(W, H, -shiftX, -shiftY, W, H);
    if (!reducedMotion) adapt(t);
    uni.uTime.value = reducedMotion ? 0 : t;
    if (!reducedMotion) for (const a of anims) a.tick(a.o, t);
    camera.updateMatrixWorld();
    post.render(scene, camera, camera.position.distanceTo(state.target), reducedMotion ? 0 : t, 0);
    // pins
    const vis = Math.max(0, (state.open - 0.55) / 0.45);
    for (const pn of pins) {
      v3.copy(pn.v).project(camera);
      const sx = (v3.x * 0.5 + 0.5) * W, sy = (-v3.y * 0.5 + 0.5) * H;
      const o = v3.z < 1 && vis > 0.02 ? vis : 0;
      if (Math.abs(o - pn.o) > 0.01 || o > 0) {
        pn.el.style.opacity = String(o);
        pn.el.style.pointerEvents = o > 0.5 ? "auto" : "none";
        pn.el.tabIndex = o > 0.5 ? 0 : -1;
        pn.el.style.transform = `translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px) translate(-50%, -100%)`;
        pn.o = o;
      }
    }
    if (first) { first = false; if (mapImg) { mapImg.remove(); mapImg = null; } }
  }

  (window as any).__dio = { scene, camera, post, terrain, state, rig, plan, renderer, THREE };   // for tuning in the console
  resize();
  renderer.compile(scene, camera);
  frame(0, -1, 0, 0, 0);
  ctx.progress(1);

  return {
    resize,
    update(s) { frame(s.p, s.active, s.t, s.mx, s.my); },
  };
};
export default factory;
