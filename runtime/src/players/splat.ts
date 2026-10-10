/**
 * splat: a scanned place (Gaussian splats, rendered by Spark) with the camera on a path driven by scroll.
 * Keys are {t, at, look} in the scan's own coordinates; between keys the camera eases along a Catmull-Rom curve.
 */
import * as THREE from "three";
import { SparkRenderer, SplatMesh } from "@sparkjsdev/spark";
import type { PlayerFactory } from "../lib/types";
import { clamp, cssVar, follow, isMobile } from "../lib/util";

const factory: PlayerFactory = async (cfg, ctx) => {
  const canvas = document.createElement("canvas");
  ctx.visual.appendChild(canvas);
  const bg = new THREE.Color(cfg.background || cssVar("--bg") || "#000");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "high-performance", preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, isMobile() ? 1.5 : 2));
  renderer.setClearColor(bg, 1);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(cfg.fov || 60, 1, 0.03, 500);
  camera.up.set(...(cfg.up as [number, number, number]));
  scene.add(new SparkRenderer({ renderer }));
  const mesh = new SplatMesh({ url: cfg.file });
  scene.add(mesh);
  ctx.progress(0.1);
  await mesh.initialized;
  ctx.progress(0.9);

  // camera path: positions and look-at points on centripetal Catmull-Rom curves, parametrised by key time
  const keys = [...cfg.keys].sort((a: any, b: any) => a.t - b.t);
  const pts = keys.map((k: any) => new THREE.Vector3(...k.at));
  const looks = keys.map((k: any) => new THREE.Vector3(...k.look));
  const path = new THREE.CatmullRomCurve3(pts, false, "centripetal", 0.5);
  const lookPath = new THREE.CatmullRomCurve3(looks, false, "centripetal", 0.5);
  const ts = keys.map((k: any) => k.t);
  function u(p: number): number {   // scene progress -> curve parameter, honouring each key's t
    if (p <= ts[0]) return 0;
    for (let i = 0; i < ts.length - 1; i++) {
      if (p <= ts[i + 1]) {
        const k = (p - ts[i]) / Math.max(ts[i + 1] - ts[i], 1e-6);
        return (i + k * k * (3 - 2 * k)) / (ts.length - 1);
      }
    }
    return 1;
  }
  const side = ctx.section.className.includes("ss-side-left") ? -1 : 1;
  function resize() {
    const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const cards = ctx.data.layout === "cards";
    camera.setViewOffset(w, h, cards && !isMobile() ? -w * 0.14 * side : 0, 0, w, h);
    camera.updateProjectionMatrix();
  }
  resize();
  let p = 0;
  const pos = new THREE.Vector3(), look = new THREE.Vector3();
  function draw() {
    const k = u(p);
    path.getPointAt(Math.min(k, 0.9999), pos);
    lookPath.getPointAt(Math.min(k, 0.9999), look);
    camera.position.copy(pos);
    camera.lookAt(look);
    renderer.render(scene, camera);
  }
  draw();
  return {
    resize,
    update(s) {
      const target = ctx.data.layout === "overlay" ? s.p : clamp(s.p);
      p += (target - p) * (follow === 1 ? 1 : 0.12);
      draw();
    },
  };
};
export default factory;
