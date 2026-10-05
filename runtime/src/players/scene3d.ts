/**
 * scene3d: a zoom journey through nested levels. Each level is a generator preset framed at scale 1
 * with the thing we dive into at its origin; scrolling one step zooms one level deeper (×zoom).
 * The last level never zooms past; an optional `final` beat (e.g. molecule docking) plays on the last step.
 */
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import type { PlayerFactory } from "../lib/types";
import { clamp, cssVar, follow, isMobile, rng, smooth } from "../lib/util";
import { makeKit, PRESETS, type LevelObj } from "./scene3d/presets";

const factory: PlayerFactory = async (cfg, ctx) => {
  const canvas = document.createElement("canvas");
  ctx.visual.appendChild(canvas);
  const bg = new THREE.Color(cfg.background || cssVar("--bg") || "#000");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance", preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.setClearColor(bg, 1);
  renderer.toneMapping = cfg.style === "solid" ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping;
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(bg.getHex(), 0.02);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 2000);
  camera.position.set(0, 0, 30);
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const [bs, br, bt] = cfg.bloom || [0.5, 0.45, 0.12];
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), bs, br, bt);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  if (cfg.style === "solid") {
    scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(-20, 18, 25); scene.add(sun);
  }

  const kit = makeKit(cfg, rng(cfg.seed ?? 7));
  const levels: LevelObj[] = [];
  for (const lv of cfg.levels) {
    const make = PRESETS[lv.preset];
    if (!make) { console.warn(`[scene3d] unknown preset ${lv.preset}`); continue; }
    const obj = await make(lv.params || {}, kit);
    scene.add(obj.group);
    levels.push(obj);
  }
  const dust = kit.points(900, () => new THREE.Vector3(kit.rnd(-60, 60), kit.rnd(-35, 35), kit.rnd(-60, 10)),
    new THREE.Color(cfg.dust || "#8fb8d8").getHex(), 0.1, 0.35);
  scene.add(dust);

  // non-intro steps: the first `nz` zoom, the last one plays the final beat when `final` is set
  const idx = ctx.data.steps.map((s, i) => (s.intro ? -1 : i)).filter((i) => i >= 0);
  const finalStep = cfg.final ? idx[idx.length - 1] : -1;
  const zoomSteps = idx.filter((i) => i !== finalStep);
  const ZOOM = cfg.zoom || 14, LN = Math.log(ZOOM), last = levels.length - 1;
  const side = (ctx.section.className.includes("ss-side-left") ? -1 : 1);

  function setOpacity(obj: THREE.Object3D, k: number) {
    obj.traverse((o: any) => {
      const m = o.material; if (!m) return;
      for (const mm of Array.isArray(m) ? m : [m]) {
        if (mm.userData.base === undefined) mm.userData.base = mm.uniforms?.opacity ? mm.uniforms.opacity.value : mm.opacity;
        if (mm.uniforms?.opacity) mm.uniforms.opacity.value = mm.userData.base * k;
        else { mm.opacity = mm.userData.base * k; mm.transparent = true; }
      }
    });
  }

  function resize() {
    const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false); composer.setSize(w, h); bloom.resolution.set(w, h);
    camera.aspect = w / h;
    const cards = ctx.data.layout === "cards";
    camera.setViewOffset(w, h, cards && !isMobile() ? -w * 0.14 * side : 0, 0, w, h);
    camera.updateProjectionMatrix();
  }
  resize();

  let z = 0, cx = 0, cy = 0;
  return {
    resize,
    update(s) {
      const target = zoomSteps.reduce((a, i) => a + (s.steps[i] ?? 0), 0);
      z += (target - z) * (follow === 1 ? 1 : 0.08);
      const fin = finalStep >= 0 ? s.steps[finalStep] ?? 0 : 0;
      levels.forEach((lv, i) => {
        const d = z - i;
        const sc = i === last ? Math.exp(Math.min(d, 0) * LN) * (1 + 0.1 * Math.max(d, 0)) : Math.exp(d * LN);
        lv.group.scale.setScalar(sc);
        const vis = smooth(-0.75, -0.15, d) * (i === last ? 1 : 1 - smooth(0.5, 0.95, d));
        lv.group.visible = vis > 0.002;
        if (lv.group.visible) setOpacity(lv.group, vis);
        lv.update?.(s.t, i === last ? fin : 0, d);
      });
      cx += (s.mx * 1.6 - cx) * 0.04; cy += (-s.my * 1.0 - cy) * 0.04;
      camera.position.set(cx, cy, 30);
      camera.lookAt(0, 0, 0);
      dust.rotation.y = s.t * 0.01;
      composer.render();
    },
  };
};
export default factory;
