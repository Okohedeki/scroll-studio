export interface Step {
  kicker?: string; title: string; body?: string; fact?: string;
  at?: [number, number]; length: number; intro?: boolean; hint?: string; state?: any;
}

export interface Hud {
  kind: "telemetry" | "scale" | "progress" | "legend" | "none";
  fields: { label: string; unit?: string; from?: number; to: number; curve?: number; decimals?: number; grouping?: boolean }[];
  events: { at: number; label: string }[];
  clock?: { prefix?: string; start: number; end: number; zero?: number } | null;
  scales: string[];
  legend: { label: string; color: string }[];
}

export interface SectionData { hud: Hud; steps: Step[]; layout: "overlay" | "split" | "cards"; length: number }

/** What a player sees every frame. */
export interface FrameState {
  /** whole-scene progress 0-1 (eased) */
  p: number;
  /** per-step local progress 0-1 (eased), split/cards layouts */
  steps: number[];
  /** index of the step currently on screen, -1 if none */
  active: number;
  /** seconds since the page loaded (for idle animation) */
  t: number;
  /** pointer position -0.5..0.5 */
  mx: number; my: number;
}

export interface PlayerContext {
  section: HTMLElement;
  visual: HTMLElement;
  data: SectionData;
  /** a player can drive the scale HUD itself (e.g. zoom level -> label) */
  setScale?: (label: string) => void;
  /** report loading progress 0-1; the factory's promise resolving means "fully ready" */
  progress: (f: number) => void;
}

export interface Player {
  update(s: FrameState): void;
  resize?(): void;
}

export type PlayerFactory = (cfg: any, ctx: PlayerContext) => Promise<Player>;
