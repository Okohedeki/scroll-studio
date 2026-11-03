/**
 * Film helpers shared by the players that draw a film themselves in WebGL (world: type in the world): a muted video that
 * is scrubbed rather than played, loaded completely first, and a group of videos that are seeked to the middle of the same
 * frame and only drawn when every one of them has landed there (so an atlas frame is never drawn over a different film frame).
 */
import { fetchBlobURL, smooth } from "./util";

export function makeVideo(): HTMLVideoElement {
  const v = document.createElement("video");
  v.muted = true; v.playsInline = true; v.preload = "auto";
  return v;
}

export async function loadVideo(v: HTMLVideoElement, url: string, onProgress: (f: number) => void): Promise<void> {
  try { v.src = await fetchBlobURL(url, onProgress, "video/mp4"); } catch { v.src = url; }
  await new Promise<void>((resolve) => {
    if (v.readyState >= 2) return resolve();
    v.addEventListener("loadeddata", () => resolve(), { once: true });
    v.addEventListener("error", () => resolve(), { once: true });
  });
}

export class PairedSeeker {
  busy = false;
  shown = -1;
  private id = 0;
  private timer = 0;
  constructor(private videos: HTMLVideoElement[], private fps: number, private onLanded: (frame: number) => void) {}

  seek(frame: number): void {
    this.busy = true;
    const id = ++this.id;
    let finished = false;
    const t = (frame + 0.5) / this.fps;
    let pending = this.videos.length;
    const finish = () => {
      if (finished || id !== this.id) return;
      finished = true; clearTimeout(this.timer);
      this.busy = false; this.shown = frame;
      this.onLanded(frame);
    };
    const landed = () => { if (--pending <= 0) finish(); };
    this.timer = window.setTimeout(finish, 800);      // never deadlock on a seek that does not report
    for (const v of this.videos) {
      if (Math.abs(v.currentTime - t) < 1e-4) { queueMicrotask(landed); continue; }
      v.addEventListener("seeked", landed, { once: true });
      v.currentTime = t;
    }
  }
}

/** A beat of a story film as the build describes it (engine/scenes/film.py `beat_stills`): its span over the film (0-1 of
 * the scroll), the point a portrait phone keeps in view, and a still for reduced motion. */
export interface FilmBeat { id: string; p0: number; p1: number; focus: [number, number] | null; still: string }

/** Where a portrait phone looks at scroll progress `p`: the focus of the beat on screen, travelling (eased) from one beat's
 * point to the next through the stretch where the two dissolve into each other; a hard cut jumps. Null when no beat sets a
 * focus (the film stays centred, as it always has). */
export function beatFocusAt(beats: FilmBeat[], p: number): [number, number] | null {
  if (!beats.length || !beats.some((b) => b.focus)) return null;
  const at = (b: FilmBeat): [number, number] => b.focus || [0.5, 0.5];
  let i = 0;
  while (i + 1 < beats.length && p >= beats[i + 1].p0) i++;
  const cur = at(beats[i]);
  const prev = beats[i - 1];
  if (prev && p < prev.p1 && prev.p1 > beats[i].p0) {          // inside the dissolve from the beat before
    const from = at(prev), k = smooth(beats[i].p0, prev.p1, p);
    return [from[0] + (cur[0] - from[0]) * k, from[1] + (cur[1] - from[1]) * k];
  }
  return cur;
}

/** The beat whose still stands for the film at progress `p` (reduced motion): the last one that has begun. */
export function beatIndexAt(beats: FilmBeat[], p: number): number {
  let i = 0;
  while (i + 1 < beats.length && p >= beats[i + 1].p0) i++;
  return i;
}

/** object-position for a point of the picture, as CSS. */
export const focusCss = (f: [number, number]) => `${(f[0] * 100).toFixed(1)}% ${(f[1] * 100).toFixed(1)}%`;
