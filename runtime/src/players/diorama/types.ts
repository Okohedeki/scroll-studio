export interface PropRec {
  k: string; x: number; y: number; z: number; r: number; s: number; v: number;
  c?: string[]; text?: string; wall?: string; place?: number; len?: number; size?: [number, number];
}
export interface PlaceRec { name: string; kind: string; x: number; y: number; z: number; yaw: number; h: number; r: number; sign: string }
export interface Beat {
  kind: "wide" | "place"; place?: number; yaw: number; pitch: number; dist: number | null; r?: number;
  target: [number, number, number]; side: number; a: number; b: number;
}
export interface CameraPlan { fov: number; pitch: number; dive_pitch: number; hold: number; drift: number; fit: number; beats: Beat[]; travel?: "orbit" | "glide" }
export interface Plan {
  v: number; kind: string; size: number; base: "round" | "square"; table: string;
  water: { level: number; has: boolean }; grid: number; heights: number[];
  palette?: string[]; edge?: Record<string, string> | null;
  props: PropRec[]; places: PlaceRec[]; steps: (number | null)[]; camera: CameraPlan;
  movers?: MoverRec[]; traffic?: TrafficRec[];
}
/** a mover on a route (engine/diorama/movers.py): a scroll mover waits at its stops while their steps are on screen */
export interface MoverRec {
  id: string; kind: string; drive: "scroll" | "time"; scale: number; color: string | null; hover: number; speed: number;
  carry: string | null; carry_size: [number, number]; path: [number, number][]; len: number;
  stops: { s: number; step: number | null; carry: string | null }[];
}
/** a crowd wandering a grid: key frames [t, x, z, ...] per mover, played on a loop of T seconds */
export interface TrafficRec {
  kind: string; scale: number; hover: number; colors: string[]; carry: (string | null)[]; carry_size: [number, number];
  T: number; cell: number; keys: number[][];
}
export interface DioramaCfg {
  plan: string; ground: string; poster?: string; map?: string;
  look: { tilt_shift: number; saturation: number; sun: string; table: string; grain: number; vignette: number };
  side: number; layout: string; credits?: string[];
}
