/**
 * The camera's choreography. Each step is a beat: the world seen whole (a wide beat) or a place the camera has dived
 * to. A beat rests while its content is on screen; between two beats the camera lifts out, sweeps round the whole
 * diorama, and dives in to the next place. The three motions overlap (the orbit starts while the lift is still
 * rising, the dive begins before the orbit has stopped), so the path is one swooping arc, not three moves.
 */
import * as THREE from "three";
import type { Beat, CameraPlan } from "./types";

export interface CamState {
  yaw: number;           // degrees: camera azimuth round the target (0: on the +z side looking north)
  pitch: number;         // degrees above the horizon
  dist: number;          // distance from the target
  target: THREE.Vector3;
  shift: number;         // screen shift of the subject, as a fraction of the width (positive: to the right)
  open: number;          // 0 at a place, 1 in the wide orbit view
  beat: number;          // index of the beat the camera is at or heading for
}

const ss = (a: number, b: number, x: number) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export class Rig {
  beats: Beat[];
  rest: [number, number][];
  wideShift = 0;
  constructor(private plan: CameraPlan, public wideDist: () => number, private viewSide: number, public diveShift: () => number, public wideShiftOf: () => number, private distScale: () => number = () => 1,
              private follow: () => THREE.Vector3 | null = () => null, private minDist: (r: number) => number = () => 0) {
    this.beats = plan.beats;
    const g = (1 - plan.hold) / 2;
    this.rest = this.beats.map((b, i) => {
      const w = b.b - b.a;
      return [i === 0 ? -1 : b.a + g * w, i === this.beats.length - 1 ? 2 : b.b - g * w] as [number, number];
    });
  }

  private pose(b: Beat, wide: boolean) {
    if (b.kind === "wide") return { pitch: this.plan.pitch, dist: this.wideDist(), target: new THREE.Vector3(0, 0.5, 0), shift: this.wideShiftOf() };
    return {
      pitch: b.pitch, dist: Math.max((b.dist as number) * this.distScale(), b.r ? this.minDist(b.r) : 0), target: new THREE.Vector3(...b.target),
      shift: (b.side || this.viewSide) * this.diveShift(),
    };
  }

  /** the camera state for scene progress p */
  at(p: number, out: CamState): CamState {
    const bs = this.beats, n = bs.length;
    let i = 0;
    for (; i < n; i++) if (p <= this.rest[i][1]) break;
    if (i >= n) i = n - 1;
    const inRest = p >= this.rest[i][0] && p <= this.rest[i][1];
    if (inRest) return this.fromBeat(i, p, out);
    // between beats i-1 and i
    const a = i - 1, b = i;
    if (a < 0) return this.fromBeat(0, p, out);
    const t0 = this.rest[a][1], t1 = this.rest[b][0];
    const u = Math.min(1, Math.max(0, (p - t0) / Math.max(1e-6, t1 - t0)));
    const A = bs[a], B = bs[b];
    const pa = this.pose(A, false), pb = this.pose(B, false), wide = this.pose({ kind: "wide" } as Beat, true);
    if (this.plan.travel === "glide" && A.kind === "place" && B.kind === "place") return this.glide(a, b, u, pa, pb, out);
    const up = A.kind === "place" ? ss(0.0, 0.38, u) : 1;
    const down = B.kind === "place" ? 1 - ss(0.62, 1.0, u) : 1;
    const o = Math.min(up, down);
    const v = ss(0.35, 0.65, u);
    const dA = pa.dist, dB = pb.dist;
    const closeDist = Math.exp(lerp(Math.log(dA), Math.log(dB), v));
    const closePitch = lerp(pa.pitch, pb.pitch, v);
    const closeTarget = pa.target.clone().lerp(pb.target, v);
    const closeShift = lerp(pa.shift, pb.shift, v);
    out.dist = Math.exp(lerp(Math.log(closeDist), Math.log(wide.dist), o));
    out.pitch = lerp(closePitch, wide.pitch, o);
    out.target.copy(closeTarget).lerp(wide.target, o);
    out.shift = lerp(closeShift, wide.shift, o);
    out.yaw = lerp(A.yaw + this.drift(a, 1), B.yaw + this.drift(b, 0), ss(0.18, 0.82, u));
    out.open = o;
    out.beat = u < 0.5 ? a : b;
    return out;
  }

  /** glide: straight from one place to the next at about the same height, easing back a little on the way so the
   * picture opens up, the target riding with the scroll mover when there is one (it travels between the two places) */
  private glide(a: number, b: number, u: number, pa: ReturnType<Rig["pose"]>, pb: ReturnType<Rig["pose"]>, out: CamState): CamState {
    const A = this.beats[a], B = this.beats[b];
    const v = ss(0.0, 1.0, u);
    out.dist = Math.exp(lerp(Math.log(pa.dist), Math.log(pb.dist), v)) * (1 + 0.32 * Math.sin(Math.PI * u));
    out.pitch = lerp(pa.pitch, pb.pitch, v) + 6 * Math.sin(Math.PI * u);
    out.target.copy(pa.target).lerp(pb.target, v);
    const f = this.follow();
    if (f) { out.target.x = f.x; out.target.z = f.z; }
    out.shift = lerp(pa.shift, pb.shift, v);
    out.yaw = lerp(A.yaw, B.yaw, v);
    out.open = 0;
    out.beat = u < 0.5 ? a : b;
    return out;
  }

  /** a wide beat's slow orbit while it rests: the yaw wanders +-10 degrees across its window */
  private drift(i: number, end: number) {
    const b = this.beats[i];
    return b.kind === "wide" ? (end ? 10 : -10) : 0;
  }

  private fromBeat(i: number, p: number, out: CamState): CamState {
    const b = this.beats[i], q = this.pose(b, false);
    const [r0, r1] = this.rest[i];
    out.pitch = q.pitch; out.dist = q.dist; out.target.copy(q.target); out.shift = q.shift;
    let yaw = b.yaw;
    if (b.kind === "wide") {
      const lo = Math.max(r0, b.a), hi = Math.min(r1, b.b);
      const u = Math.min(1, Math.max(0, (p - lo) / Math.max(1e-6, hi - lo)));
      yaw += lerp(-10, 10, u);
    }
    out.yaw = yaw; out.open = b.kind === "wide" ? 1 : 0; out.beat = i;
    return out;
  }

  /** the pose of beat i itself (reduced motion: no travel) */
  still(i: number, out: CamState): CamState {
    const b = this.beats[Math.max(0, Math.min(this.beats.length - 1, i))];
    const q = this.pose(b, false);
    out.pitch = q.pitch; out.dist = q.dist; out.target.copy(q.target); out.shift = q.shift; out.yaw = b.yaw;
    out.open = b.kind === "wide" ? 1 : 0; out.beat = Math.max(0, Math.min(this.beats.length - 1, i));
    return out;
  }
}
