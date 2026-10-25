/**
 * The visitor's pointer reveals the picture (`pointer:` on a parallax or film section, engine/spec.py Pointer).
 *
 * A lens is a soft circle under the pointer that shows a second layer through the first (the picture's colour through a
 * black-and-white page, or a second picture of the same view); light is a torch, a pool of warm light on a darkened picture
 * that rakes across the shapes of a photo's depth map. This module is the part that is not drawing: where the lens is
 * (mouse, finger, resting point), the numbers the shader is given, and the light's falloff, mirrored in GLSL by
 * POINTER_GLSL below. The players (parallax, reveal) draw it in their own single pass.
 *
 * Where it sits:
 *   mouse (a device that can hover)  under the pointer while it is over the picture, eased a little; back to `rest` when it
 *                                    leaves (and before it ever arrives: keyboard users see the static version)
 *   finger (a phone)                 above the finger while it touches, so the finger does not cover it; with no touch it
 *                                    rests at `rest` and drifts gently around it
 *   reduced motion                   at `rest`, still: no following, no drift (it never moves by itself or with the pointer)
 * `update()` says whether it moved, so a player redraws only then; nothing runs while the pointer is still, and a section
 * off screen is not updated at all (the scroll core stops ticking it).
 */
import { clamp } from "./util";

export type PointerMode = "lens" | "light";
/** The spec's settings as the page carries them (`.ss-pointer`), with the defaults filled in. */
export interface PointerCfg {
  mode: PointerMode;
  /** what the lens shows: the picture's own colour, or a second picture (the builder's `layers`, one per photo) */
  layer: "colour" | "picture";
  /** the look outside the lens: none, mono, dim, blur or a hex tint */
  base: string;
  radius: number; softness: number; strength: number;
  color: [number, number, number];
  rest: [number, number];
  /** the second pictures, one per photo (null: that photo has no lens) */
  layers: (string | null)[];
}

export const DEFAULTS = {
  lens: { radius: 0.2, strength: 1 },
  light: { radius: 0.32, strength: 0.85 },
};

function hex(h: string): [number, number, number] {
  let s = h.replace("#", "");
  if (s.length === 3) s = [...s].map((c) => c + c).join("");
  return [0, 2, 4].map((i) => parseInt(s.slice(i, i + 2), 16) / 255) as [number, number, number];
}

/** The section's pointer settings (`.ss-pointer`, written by the compiler only when the spec has `pointer:`), merged with
 * what the scene builder resolved (`cfg.pointer.layers`); null when the section has none. `fallbackBase` is the look a
 * colour lens uses when the spec names none (a film's own `reveal.base`). */
export function readPointer(section: HTMLElement, cfg: any, fallbackBase = "mono"): PointerCfg | null {
  const el = section.querySelector<HTMLScriptElement>(":scope > .ss-pointer");
  if (!el) return null;
  let spec: any;
  try { spec = JSON.parse(el.textContent || "{}"); } catch { return null; }
  const mode: PointerMode = spec.mode === "light" ? "light" : "lens";
  const layer = spec.layer === "picture" ? "picture" : "colour";
  const d = DEFAULTS[mode];
  return {
    mode, layer,
    base: mode === "light" ? "none" : spec.base ?? (layer === "colour" ? fallbackBase : "none"),
    radius: spec.radius ?? d.radius,
    softness: clamp(spec.softness ?? 0.35),
    strength: clamp(spec.strength ?? d.strength),
    color: hex(spec.color || "#ffd7a8"),
    rest: [clamp(spec.rest?.[0] ?? 0.62), clamp(spec.rest?.[1] ?? 0.42)],
    layers: Array.isArray(cfg?.pointer?.layers) ? cfg.pointer.layers : [],
  };
}

// ---------------------------------------------------------------- the maths (pure)

export interface Box { left: number; top: number; width: number; height: number }

/** A point on the screen (client px) as 0-1 across and down a box; inside or not. */
export function localPoint(x: number, y: number, r: Box): { u: number; v: number; inside: boolean } {
  const u = (x - r.left) / Math.max(1, r.width), v = (y - r.top) / Math.max(1, r.height);
  return { u, v, inside: u >= 0 && u <= 1 && v >= 0 && v <= 1 };
}

/** The lens radius in css px: a share of the picture's shorter side. */
export const radiusPx = (radius: number, r: Box) => radius * Math.min(r.width, r.height);

/** On a phone the lens sits above the finger: its centre a radius and a little more higher, so its lower edge clears the
 * fingertip. Returned as how far up, in 0-1 of the box's height. */
export function fingerLift(radius: number, r: Box): number {
  return (radiusPx(radius, r) + 12) / Math.max(1, r.height);
}

/** Where the lens rests when no pointer is on the picture; on a phone (`drift`) it wanders slowly around that point, a small
 * figure-of-eight about 9 s around, so the page hints that it can be touched. */
export function restAt(t: number, rest: [number, number], drift: boolean): [number, number] {
  if (!drift) return [rest[0], rest[1]];
  const w = (Math.PI * 2) / 9;
  return [clamp(rest[0] + 0.05 * Math.sin(t * w)), clamp(rest[1] + 0.035 * Math.sin(t * w * 2 + 0.6))];
}

/** A point in a box (0-1) as 0-1 of a picture shown in it with `object-fit: cover` (media px size; the box's own aspect when
 * the canvas fills the box exactly), and the scale from box px to the picture's displayed px. */
export function coverMap(u: number, v: number, r: Box, media: { w: number; h: number } | null): { x: number; y: number; shownH: number } {
  if (!media) return { x: u, y: v, shownH: r.height };
  const s = Math.max(r.width / media.w, r.height / media.h);
  return { x: (u - 0.5) * r.width / (media.w * s) + 0.5, y: (v - 0.5) * r.height / (media.h * s) + 0.5, shownH: media.h * s };
}

/** What the shader needs this frame: the centre in the picture's 0-1 coordinates (y down), the radius in picture heights,
 * and the picture's aspect (so the circle is round on screen). */
export function uniforms(pos: [number, number], radius: number, r: Box, media: { w: number; h: number } | null) {
  const m = coverMap(pos[0], pos[1], r, media);
  const aspect = media ? media.w / media.h : r.width / Math.max(1, r.height);
  return { centre: [m.x, m.y] as [number, number], radius: radiusPx(radius, r) / Math.max(1, m.shownH), aspect };
}

/** The lens: 1 inside, 0 outside, a soft edge `softness` wide (d is the distance from the centre in radii). */
export function lensMask(d: number, softness: number): number {
  const a = 1 - Math.max(softness, 0.01), t = clamp((d - a) / (1 - a));
  return 1 - t * t * (3 - 2 * t);
}

/** How much of the torch's light reaches a point d radii from its centre: full in the middle, easing down across the pool,
 * a soft edge, and a dim spill beyond it like a real torch's (never quite nothing near the pool). 0-1, falling with d. */
export function lightFalloff(d: number, softness: number): number {
  const s = Math.max(softness, 0.01);
  const t = clamp((d - (1 - s)) / (2 * s));
  const edge = 1 - t * t * (3 - 2 * t);
  const spill = 0.45 / (1 + 6 * d * d);
  return Math.max(edge * (1 - 0.35 * Math.min(d, 1) * Math.min(d, 1)), spill);
}

// ---------------------------------------------------------------- the controller

export interface PointerEnv {
  /** prefers-reduced-motion */
  reduced: boolean;
  /** the device can hover (a mouse or trackpad); false on phones and tablets */
  hover: boolean;
  /** listen to these events (window by default) */
  target?: EventTarget;
}

export interface PointerTrack {
  /** where the lens is now, 0-1 of the box */
  pos: [number, number];
  /** advance to time t (seconds); true when the lens moved since the last call (so the player redraws) */
  update(t: number): boolean;
  /** the box the lens lives in changed size */
  dirty(): void;
  dispose(): void;
}

/** Follows the mouse or finger over `el` (the picture's box), as the module comment describes. */
export function trackPointer(el: HTMLElement, cfg: Pick<PointerCfg, "rest" | "radius">, env: PointerEnv): PointerTrack {
  const target = env.target ?? window;
  const pos: [number, number] = [cfg.rest[0], cfg.rest[1]];
  let client: { x: number; y: number; touch: boolean } | null = null;
  let last = -1, moved = true;
  const offs: (() => void)[] = [];
  const on = (type: string, fn: (e: any) => void) => {
    target.addEventListener(type, fn, { passive: true });
    offs.push(() => target.removeEventListener(type, fn));
  };
  if (!env.reduced) {
    on("pointermove", (e: PointerEvent) => { if (e.pointerType !== "touch") client = { x: e.clientX, y: e.clientY, touch: false }; });
    on("pointerout", (e: PointerEvent) => { if (!e.relatedTarget && client && !client.touch) client = null; });   // left the window
    const touch = (e: TouchEvent) => { const p = e.touches[0]; client = p ? { x: p.clientX, y: p.clientY, touch: true } : null; };
    on("touchstart", touch); on("touchmove", touch);
    on("touchend", touch); on("touchcancel", () => { client = null; });
  }

  function goal(t: number): [number, number] {
    if (client) {
      const r = el.getBoundingClientRect();
      const p = localPoint(client.x, client.y, r);
      if (client.touch) return [clamp(p.u), clamp(p.v - fingerLift(cfg.radius, r))];
      if (p.inside) return [p.u, p.v];
    }
    return restAt(t, cfg.rest, !env.hover && !env.reduced);
  }

  return {
    pos,
    update(t: number) {
      const dt = last < 0 ? 1 : clamp(t - last, 0, 0.1);
      last = t;
      if (env.reduced) { const m = moved; moved = false; return m; }
      const [gx, gy] = goal(t);
      const k = client ? 1 - Math.exp(-dt * 18) : 1 - Math.exp(-dt * 4);     // snappy under the hand, a slow glide home
      const nx = pos[0] + (gx - pos[0]) * k, ny = pos[1] + (gy - pos[1]) * k;
      const settle = Math.abs(gx - nx) < 2e-4 && Math.abs(gy - ny) < 2e-4;
      const x = settle ? gx : nx, y = settle ? gy : ny;
      const changed = moved || x !== pos[0] || y !== pos[1];
      pos[0] = x; pos[1] = y; moved = false;
      return changed;
    },
    dirty() { moved = true; },
    dispose() { offs.forEach((f) => f()); },
  };
}

/** The device answers for a page: reduced motion and whether it can hover. */
export function pointerEnv(): PointerEnv {
  return {
    reduced: matchMedia("(prefers-reduced-motion: reduce)").matches,
    hover: matchMedia("(hover: hover) and (pointer: fine)").matches,
  };
}

// ---------------------------------------------------------------- the GLSL (one function set, used by both players)

/** The look outside the lens, as a GLSL expression body on `c` (the picture's colour); `blur` is the player's own blurred
 * sample `bl`. */
export function baseGlsl(base: string): string {
  if (base === "mono") return "vec3(dot(c, vec3(0.2126, 0.7152, 0.0722)))";
  if (base === "dim") return "mix(c, vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))), 0.55) * 0.55";
  if (base === "blur") return "bl";
  if (/^#[0-9a-f]{3,6}$/i.test(base)) {
    const [r, g, b] = hex(base).map((v) => v.toFixed(4));
    return `ptrTint(c, vec3(${r}, ${g}, ${b}))`;
  }
  return "c";
}

/** Uniforms and helpers: uPtrC centre (0-1, y down), uPtrR radius in picture heights, uPtrAsp picture aspect, uPtrSoft edge,
 * uPtrStr strength, uPtrCol light colour. ptrFalloff mirrors lightFalloff above; ptrRim draws the lens's edge; ptrLight shades a colour with the torch,
 * from a depth (near = 1) and its gradient when the picture has a depth map (grad = 0 and dep = 1 when it has none). */
export const POINTER_GLSL = `
uniform vec2 uPtrC; uniform float uPtrR, uPtrAsp, uPtrSoft, uPtrStr; uniform vec3 uPtrCol;
float ptrDist(vec2 p) { return length((p - uPtrC) * vec2(uPtrAsp, 1.0)) / max(uPtrR, 1e-4); }
float ptrLens(vec2 p) { float a = 1.0 - max(uPtrSoft, 0.01); return 1.0 - smoothstep(a, 1.0, ptrDist(p)); }
float ptrFalloff(float d) {
  float s = max(uPtrSoft, 0.01);
  float edge = 1.0 - smoothstep(1.0 - s, 1.0 + s, d);
  float m = min(d, 1.0);
  return max(edge * (1.0 - 0.35 * m * m), 0.45 / (1.0 + 6.0 * d * d));
}
// the lens's rim: a hairline of light at its edge and a faint shadow just outside, so it reads as a lens even where the two
// layers are alike (a grey wall is grey in both)
vec3 ptrRim(vec3 c, vec2 p) {
  float d = ptrDist(p), w = fwidth(d) * 1.2;
  float ring = 1.0 - smoothstep(0.0, w, abs(d - 1.0));
  float shade = smoothstep(1.0, 1.0 + w * 2.0, d) * (1.0 - smoothstep(1.0 + w * 2.0, 1.0 + w * 14.0, d));
  return c * (1.0 - 0.18 * shade) + 0.28 * ring * (1.0 - c);
}
vec3 ptrTint(vec3 c, vec3 t) { float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); return l < 0.5 ? t * (l * 2.0) : t + (1.0 - t) * (l * 2.0 - 1.0); }
vec3 ptrLight(vec3 col, vec2 p, float dep, vec2 grad) {
  float d = ptrDist(p);
  float I = ptrFalloff(d);
  float amb = 1.0 - 0.92 * uPtrStr;
  // the lamp hangs a little in front of the picture, above the pointer; a surface's slope (from the depth gradient) turns it
  // towards or away from the lamp, so light rakes across shapes, and farther things get less of it
  vec3 n = normalize(vec3(-grad / (1.0 + length(grad)), 1.0));     // softly limited: a depth jump (an outline) is not a slope
  vec3 toL = vec3((uPtrC - p) * vec2(uPtrAsp, 1.0), uPtrR * 0.9 + (1.0 - dep) * 0.35);
  vec3 L = normalize(toL);
  float lam = max(dot(n, L), 0.0);
  float shape = clamp(lam / max(L.z, 0.2), 0.0, 1.8);    // 1 on a surface facing the viewer, more where it faces the lamp
  float reach = mix(0.45, 1.0, dep);
  float spec = pow(max(dot(reflect(-L, n), vec3(0.0, 0.0, 1.0)), 0.0), 24.0) * (1.0 - n.z) * 6.0;
  vec3 lit = uPtrCol * I * reach * mix(1.0, shape, 0.7);
  return col * (amb + lit * 1.15) + uPtrCol * clamp(spec, 0.0, 1.0) * I * reach * 0.22;
}
`;
