/**
 * map: a non-interactive MapLibre map whose camera and routes follow scroll. Each step's `state`:
 * {center: [lng, lat], zoom, pitch, bearing, routes: {id: 0-1}}. Between steps the camera eases from the
 * previous state, dipping out when the two places are far apart (like flyTo, but scrubbable).
 */
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { PlayerFactory } from "../lib/types";
import { clamp, easeInOut, isMobile, lerp } from "../lib/util";

interface Cam { center: [number, number]; zoom: number; pitch: number; bearing: number; routes: Record<string, number> }

const factory: PlayerFactory = async (cfg, ctx) => {
  const el = document.createElement("div");
  Object.assign(el.style, { position: "absolute", inset: "0" });
  ctx.visual.appendChild(el);
  if (cfg.dark) el.style.filter = "brightness(.62) saturate(.55) contrast(1.08)";

  const steps = ctx.data.steps;
  const cams: Cam[] = [];
  let prev: Cam = { center: [0, 20], zoom: 1.5, pitch: 0, bearing: 0, routes: {} };
  for (const s of steps as any[]) {
    const st = s.state || {};
    const cur: Cam = { center: st.center ?? prev.center, zoom: st.zoom ?? prev.zoom, pitch: st.pitch ?? 0, bearing: st.bearing ?? 0,
      routes: { ...prev.routes, ...(st.routes || {}) } };
    cams.push(cur);
    prev = cur;
  }

  const map = new maplibregl.Map({
    container: el, style: cfg.style, interactive: false, attributionControl: { compact: true },
    center: cams[0]?.center ?? [0, 20], zoom: cams[0]?.zoom ?? 1.5, pitch: cams[0]?.pitch ?? 0, bearing: cams[0]?.bearing ?? 0,
    canvasContextAttributes: { preserveDrawingBuffer: true }, maxPitch: 75,
  } as any);
  let ready = false;
  const lengths: Record<string, number[]> = {};
  map.on("load", () => {
    for (const r of cfg.routes) {
      const acc = [0];
      for (let i = 1; i < r.coords.length; i++) {
        const [a, b] = [r.coords[i - 1], r.coords[i]];
        acc.push(acc[i - 1] + Math.hypot(b[0] - a[0], b[1] - a[1]));
      }
      lengths[r.id] = acc;
      map.addSource(`route-${r.id}`, { type: "geojson", data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [] } } });
      map.addLayer({ id: `route-${r.id}-glow`, type: "line", source: `route-${r.id}`, layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": r.color, "line-width": 10, "line-opacity": 0.25, "line-blur": 6 } });
      map.addLayer({ id: `route-${r.id}`, type: "line", source: `route-${r.id}`, layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": r.color, "line-width": 3.2 } });
    }
    for (const m of cfg.markers) {
      const dot = document.createElement("div");
      dot.className = "ss-map-marker";
      dot.innerHTML = `<i></i><span>${m.label}</span>`;
      new maplibregl.Marker({ element: dot, anchor: "left" }).setLngLat([m.lng, m.lat]).addTo(map);
    }
    ready = true;
  });
  const style = document.createElement("style");
  style.textContent = `
    .ss-map-marker { display: flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 11px; letter-spacing: .12em;
      text-transform: uppercase; color: #fff; text-shadow: 0 1px 6px rgba(0,0,0,.7); pointer-events: none; }
    .ss-map-marker i { width: 10px; height: 10px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 4px rgba(var(--accent-rgb), .3), 0 0 14px var(--accent); margin-left: -5px; }
    .maplibregl-ctrl-attrib { font-size: 10px; }`;
  ctx.visual.appendChild(style);

  // ready = style loaded and the first view's tiles drawn (capped, so a slow tile server can't block the page)
  // (polls tile state instead of waiting for "idle", which also needs painting and stalls in background tabs)
  await new Promise<void>((resolve) => {
    const t0 = performance.now();
    const check = () => {
      if ((map.isStyleLoaded() && map.areTilesLoaded()) || performance.now() - t0 > 12000) return resolve();
      setTimeout(check, 150);
    };
    map.once("load", check);
  });
  ctx.progress(1);

  const slice = (id: string, coords: number[][], f: number) => {
    const acc = lengths[id], total = acc[acc.length - 1], target = total * clamp(f);
    let i = 1;
    while (i < acc.length && acc[i] < target) i++;
    if (i >= acc.length) return coords;
    const t = (target - acc[i - 1]) / Math.max(acc[i] - acc[i - 1], 1e-9);
    const a = coords[i - 1], b = coords[i];
    return [...coords.slice(0, i), [lerp(a[0], b[0], t), lerp(a[1], b[1], t)]];
  };
  const drawn: Record<string, number> = {};

  return {
    resize: () => map.resize(),
    update(s) {
      if (!ready || !cams.length) return;
      let k = 0;
      for (let i = 0; i < steps.length; i++) if ((s.steps[i] ?? 0) > 0) k = i;
      const a = cams[Math.max(0, k - 1)], b = cams[k];
      const t = easeInOut(clamp((s.steps[k] ?? 0) / 0.7));
      const far = Math.hypot(b.center[0] - a.center[0], b.center[1] - a.center[1]);
      const dip = Math.min(4, Math.log2(1 + far / 4)) * Math.sin(Math.PI * t);
      let db = b.bearing - a.bearing;
      if (db > 180) db -= 360; else if (db < -180) db += 360;
      // keep the subject clear of the text cards: shift the camera's centre into the open side
      const w = el.clientWidth, cards = ctx.data.layout === "cards" && !isMobile();
      const left = ctx.section.className.includes("ss-side-left");
      map.jumpTo({
        padding: cards ? { left: left ? 0 : w * 0.36, right: left ? w * 0.36 : 0, top: 0, bottom: 0 } : { left: 0, right: 0, top: 0, bottom: 0 },
        center: [lerp(a.center[0], b.center[0], t), lerp(a.center[1], b.center[1], t)],
        zoom: lerp(a.zoom, b.zoom, t) - dip,
        pitch: lerp(a.pitch, b.pitch, t), bearing: a.bearing + db * t,
      });
      for (const r of cfg.routes) {
        const f = lerp(a.routes[r.id] ?? 0, b.routes[r.id] ?? 0, clamp((s.steps[k] ?? 0) / 0.85));
        if (Math.abs((drawn[r.id] ?? -1) - f) < 1e-4) continue;
        drawn[r.id] = f;
        (map.getSource(`route-${r.id}`) as maplibregl.GeoJSONSource).setData({ type: "Feature", properties: {},
          geometry: { type: "LineString", coordinates: f > 0 ? slice(r.id, r.coords, f) : [] } });
      }
    },
  };
};
export default factory;
