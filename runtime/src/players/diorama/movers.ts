/**
 * Movers on the diorama (engine/diorama/movers.py lays them out). A scroll mover's place on its route follows the page:
 * it waits at each stop while that stop's step is on screen (the camera's rest at that beat) and travels between stops
 * as the page scrolls; what it carries changes while it waits at a stop. A time mover loops its route at its speed.
 * Traffic plays key frames worked out at build time (straight moves along a grid, eased, never two in one cell) on a
 * loop. Each mover is a prop of the kit with the carried picture laid on its deck.
 */
import * as THREE from "three";
import type { MoverRec, TrafficRec } from "./types";

const ss = (a: number, b: number, x: number) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

/** A point `s` along a dense path of total length `len` (and the unit direction there). */
export function pathAt(path: [number, number][], len: number, s: number): { x: number; z: number; dx: number; dz: number } {
  const n = path.length;
  if (n === 0) return { x: 0, z: 0, dx: 1, dz: 0 };
  if (n === 1 || len <= 0) return { x: path[0][0], z: path[0][1], dx: 1, dz: 0 };
  const f = Math.min(1, Math.max(0, s / len)) * (n - 1);
  const i = Math.min(n - 2, Math.floor(f)), u = f - i;
  const a = path[i], b = path[i + 1];
  const dx = b[0] - a[0], dz = b[1] - a[1], l = Math.hypot(dx, dz) || 1;
  return { x: a[0] + dx * u, z: a[1] + dz * u, dx: dx / l, dz: dz / l };
}

/**
 * The knots (scene progress, arc length) of a scroll mover. `rests[k]` is the window in which step k's beat rests. The
 * mover sits at the route's start until the first step's rest ends (unless the first step is a stop), waits through each
 * stop's rest, travels between them, and, when the route goes on past the last stop, reaches its end as the last step
 * comes to rest.
 */
export function timeline(stops: { s: number; step: number | null }[], rests: [number, number][], len: number): [number, number][] {
  const cl = (v: number) => Math.min(1, Math.max(0, v));
  const k: [number, number][] = [[0, 0]];
  const st = stops.filter((s) => s.step != null && rests[s.step as number]);
  if (st.length && st[0].step !== 0 && rests[0]) k.push([cl(Math.min(rests[0][1], rests[st[0].step as number][0])), 0]);
  for (const s of st) {
    const [a, b] = rests[s.step as number];
    k.push([cl(a), s.s], [cl(b), s.s]);
  }
  const last = st.length ? st[st.length - 1] : null;
  const n = rests.length;
  if (len > (last ? last.s : 0) + 1e-3) {
    const endAt = last && (last.step as number) < n - 1 ? cl(rests[n - 1][0]) : 1;
    k.push([Math.max(endAt, k[k.length - 1][0]), len], [1, len]);
  } else k.push([1, k[k.length - 1][1]]);
  // never backwards in time
  for (let i = 1; i < k.length; i++) if (k[i][0] < k[i - 1][0]) k[i][0] = k[i - 1][0];
  return k;
}

/** Arc length at progress p: held at a knot, eased between knots. */
export function arcAt(knots: [number, number][], p: number): number {
  if (!knots.length) return 0;
  if (p <= knots[0][0]) return knots[0][1];
  for (let i = 1; i < knots.length; i++) {
    const [p1, s1] = knots[i], [p0, s0] = knots[i - 1];
    if (p <= p1) return p1 <= p0 ? s1 : s0 + (s1 - s0) * ss(p0, p1, p);
  }
  return knots[knots.length - 1][1];
}

/** What a scroll mover carries at progress p: the picture before, the one after and how far it has changed (a stop's
 * load changes over the middle of its rest). */
export function loadAt(initial: string | null, stops: { step: number | null; carry: string | null }[], rests: [number, number][], p: number):
  { from: string | null; to: string | null; mix: number } {
  let cur = initial;
  for (const s of stops) {
    if (!s.carry || s.step == null || !rests[s.step]) continue;
    const [a0, b0] = rests[s.step];
    const a = Math.max(0, a0), b = Math.min(1, b0);
    const m = ss(a + (b - a) * 0.2, a + (b - a) * 0.6, p);
    if (m <= 0) return { from: cur, to: cur, mix: 0 };
    if (m < 1) return { from: cur, to: s.carry, mix: m };
    cur = s.carry;
  }
  return { from: cur, to: cur, mix: 0 };
}

/** Where a traffic mover is at time t (seconds within its loop): the twin of `position` in engine/diorama/movers.py. */
export function trafficAt(keys: number[], t: number): [number, number] {
  const n = Math.floor(keys.length / 3);
  if (!n) return [0, 0];
  if (t <= keys[0]) return [keys[1], keys[2]];
  let lo = 0, hi = n - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (keys[3 * mid] <= t) lo = mid; else hi = mid - 1; }
  if (lo >= n - 1) return [keys[3 * n - 2], keys[3 * n - 1]];
  const t0 = keys[3 * lo], t1 = keys[3 * lo + 3];
  let u = t1 <= t0 ? 0 : (t - t0) / (t1 - t0);
  u = u * u * (3 - 2 * u);
  return [keys[3 * lo + 1] + (keys[3 * lo + 4] - keys[3 * lo + 1]) * u, keys[3 * lo + 2] + (keys[3 * lo + 5] - keys[3 * lo + 2]) * u];
}

// ---------------------------------------------------------------- the objects

export type PropMaker = (kind: string, colors: string[], scale: number) => { obj: THREE.Group; top: number; tick: (t: number) => void };

interface Deck { group: THREE.Group; a: THREE.Mesh; b: THREE.Mesh }

function deck(loader: THREE.TextureLoader, cache: Map<string, THREE.Texture>, w: number, d: number): Deck {
  const g = new THREE.Group();
  const geo = new THREE.PlaneGeometry(w, d).rotateX(-Math.PI / 2);
  const mk = (y: number, transparent: boolean) => {
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: 0.55, metalness: 0.05, transparent, opacity: transparent ? 0 : 1 }));
    m.position.y = y; m.receiveShadow = true; m.castShadow = false; m.visible = false;
    g.add(m);
    return m;
  };
  return { group: g, a: mk(0.012, false), b: mk(0.016, true) };
}

export function texFor(loader: THREE.TextureLoader, cache: Map<string, THREE.Texture>, url: string | null): THREE.Texture | null {
  if (!url) return null;
  let t = cache.get(url);
  if (!t) {
    t = loader.load(url);
    t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
    cache.set(url, t);
  }
  return t;
}

function setDeck(dk: Deck, loader: THREE.TextureLoader, cache: Map<string, THREE.Texture>, from: string | null, to: string | null, mix: number) {
  const ta = texFor(loader, cache, from), tb = texFor(loader, cache, to);
  const ma = dk.a.material as THREE.MeshStandardMaterial, mb = dk.b.material as THREE.MeshStandardMaterial;
  if (ma.map !== ta) { ma.map = ta; ma.needsUpdate = true; }
  dk.a.visible = !!ta;
  if (mb.map !== tb) { mb.map = tb; mb.needsUpdate = true; }
  dk.b.visible = !!tb && mix > 0.001 && to !== from;
  mb.opacity = mix;
}

export class Movers {
  private loader = new THREE.TextureLoader();
  private cache = new Map<string, THREE.Texture>();
  private items: { rec: MoverRec; obj: THREE.Group; deck: Deck; knots: [number, number][] | null; tick: (t: number) => void; top: number }[] = [];
  private crowd: { rec: TrafficRec; obj: THREE.Group; deck: Deck; keys: number[]; ph: number; tick: (t: number) => void }[] = [];
  /** where the scroll mover is now (the camera follows it), or null without one */
  hero: THREE.Vector3 | null = null;

  constructor(private group: THREE.Group, movers: MoverRec[], traffic: TrafficRec[], make: PropMaker, private heightAt: (x: number, z: number) => number) {
    for (const rec of movers) {
      const m = make(rec.kind, rec.color ? [rec.color] : [], rec.scale);
      const dk = deck(this.loader, this.cache, rec.carry_size[0], rec.carry_size[1]);
      dk.group.position.y = m.top; m.obj.add(dk.group);
      group.add(m.obj);
      this.items.push({ rec, obj: m.obj, deck: dk, knots: null, tick: m.tick, top: m.top });
      if (rec.drive === "scroll") this.hero = new THREE.Vector3();
    }
    for (const rec of traffic) {
      rec.keys.forEach((keys, i) => {
        const col = rec.colors.length ? [rec.colors[i % rec.colors.length]] : [];
        const m = make(rec.kind, col, rec.scale);
        const dk = deck(this.loader, this.cache, rec.carry_size[0], rec.carry_size[1]);
        dk.group.position.y = m.top; m.obj.add(dk.group);
        const pic = rec.carry.length ? rec.carry[i % rec.carry.length] : null;
        setDeck(dk, this.loader, this.cache, pic, pic, 0);
        group.add(m.obj);
        this.crowd.push({ rec, obj: m.obj, deck: dk, keys, ph: i * 1.7, tick: m.tick });
      });
    }
  }

  /** the scroll mover's knots, from the camera's rest windows (set once the rig knows them) */
  setRests(rests: [number, number][]) {
    for (const it of this.items) if (it.rec.drive === "scroll") it.knots = timeline(it.rec.stops, rests, it.rec.len);
    this.rests = rests;
  }
  private rests: [number, number][] = [];

  update(p: number, t: number, still: boolean) {
    for (const it of this.items) {
      const r = it.rec;
      let s: number;
      if (r.drive === "scroll") s = arcAt(it.knots || [[0, 0]], p);
      else s = r.len > 0 ? ((still ? 0 : t) * r.speed) % r.len : 0;
      const q = pathAt(r.path, r.len, s);
      const y = Math.max(0, this.heightAt(q.x, q.z)) + r.hover + (still ? 0 : Math.sin(t * 2.1 + s) * 0.008);
      it.obj.position.set(q.x, y, q.z);
      if (r.kind !== "carrier") it.obj.rotation.y = Math.atan2(q.dx, q.dz);
      if (r.drive === "scroll") {
        const ld = loadAt(r.carry, r.stops, this.rests, p);
        setDeck(it.deck, this.loader, this.cache, ld.from, ld.to, ld.mix);
        this.hero?.set(q.x, y + it.top, q.z);
      } else setDeck(it.deck, this.loader, this.cache, r.carry, r.carry, 0);
      if (!still) it.tick(t);
    }
    for (const c of this.crowd) {
      const T = c.rec.T || 1;
      const tt = still ? 3 : ((t % T) + T) % T;
      const [x, z] = trafficAt(c.keys, tt);
      c.obj.position.set(x, Math.max(0, this.heightAt(x, z)) + c.rec.hover + (still ? 0 : Math.sin(t * 2.3 + c.ph) * 0.008), z);
      if (!still) c.tick(t);
    }
  }
}
