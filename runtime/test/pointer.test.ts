/**
 * The pointer's lens and light (lib/pointer.ts): reading the page's settings, the maths (where the lens is on the picture, the
 * finger lift, the resting drift, the light's falloff) and the controller that follows mouse and finger, stays still with
 * reduced motion and reports a move only when there was one (so a player redraws only then).
 */
import { describe, expect, it } from "vitest";
import { box, media } from "./helpers";
import {
  baseGlsl, coverMap, DEFAULTS, fingerLift, lensMask, lightFalloff, localPoint, POINTER_GLSL, pointerEnv, radiusPx, readPointer,
  restAt, trackPointer, uniforms,
} from "../src/lib/pointer";

const R = { left: 100, top: 50, width: 800, height: 400 };

function section(json: string | null) {
  const s = document.createElement("section");
  if (json !== null) s.innerHTML = `<script type="application/json" class="ss-pointer">${json}</script>`;
  document.body.appendChild(s);
  return s;
}

/** an event with the fields the controller reads (jsdom has no PointerEvent or Touch) */
function fire(target: EventTarget, type: string, fields: Record<string, unknown>) {
  const e = new Event(type);
  Object.assign(e, fields);
  target.dispatchEvent(e);
}

describe("reading the page's settings", () => {
  it("a section without `.ss-pointer` has no pointer (nothing changes for it)", () => {
    expect(readPointer(section(null), {})).toBeNull();
  });

  it("a lens on colour: the defaults filled in, the base falls back to the film's own (or mono)", () => {
    const p = readPointer(section(`{"mode": "lens", "layer": "colour"}`), {})!;
    expect(p).toMatchObject({ mode: "lens", layer: "colour", base: "mono", radius: DEFAULTS.lens.radius, strength: 1, softness: 0.35, rest: [0.62, 0.42], layers: [] });
    expect(p.color.map((c) => Math.round(c * 255))).toEqual([255, 215, 168]);
    expect(readPointer(section(`{"mode": "lens"}`), {}, "dim")!.base).toBe("dim");
  });

  it("a lens on a second picture shows the photo as it is outside, and takes the builder's pictures", () => {
    const p = readPointer(section(`{"mode": "lens", "layer": "picture", "radius": 0.3, "rest": [0.2, 0.9]}`), { pointer: { layers: ["a.jpg", null] } })!;
    expect(p).toMatchObject({ layer: "picture", base: "none", radius: 0.3, rest: [0.2, 0.9], layers: ["a.jpg", null] });
  });

  it("light: its own defaults, the picture as it is under it, a short hex colour", () => {
    const p = readPointer(section(`{"mode": "light", "base": "mono", "color": "#fff", "strength": 0.5}`), {})!;
    expect(p).toMatchObject({ mode: "light", base: "none", radius: DEFAULTS.light.radius, strength: 0.5, color: [1, 1, 1] });
    expect(readPointer(section(`{"mode": "light"}`), {})!.strength).toBe(DEFAULTS.light.strength);
  });

  it("broken JSON is no pointer, not a broken page", () => {
    expect(readPointer(section(`{mode: lens`), {})).toBeNull();
  });
});

describe("the maths", () => {
  it("a screen point as 0-1 of the picture's box, and whether it is on it", () => {
    expect(localPoint(500, 250, R)).toEqual({ u: 0.5, v: 0.5, inside: true });
    expect(localPoint(50, 250, R).inside).toBe(false);
    expect(localPoint(500, 500, R).inside).toBe(false);
  });

  it("the radius is a share of the shorter side", () => {
    expect(radiusPx(0.2, R)).toBe(80);
  });

  it("on a phone the lens sits above the finger: a radius and 12 px, so its lower edge clears the fingertip", () => {
    const phone = { left: 0, top: 0, width: 390, height: 600 };
    expect(fingerLift(0.2, phone)).toBeCloseTo((78 + 12) / 600);
  });

  it("at rest it stays put, or (on a phone) wanders a little around the point and comes back", () => {
    expect(restAt(3, [0.6, 0.4], false)).toEqual([0.6, 0.4]);
    const pts = [0, 1, 2, 3, 4, 5, 6, 7, 8].map((t) => restAt(t, [0.6, 0.4], true));
    for (const [x, y] of pts) { expect(Math.abs(x - 0.6)).toBeLessThanOrEqual(0.05); expect(Math.abs(y - 0.4)).toBeLessThanOrEqual(0.035); }
    expect(new Set(pts.map((p) => p.join())).size).toBeGreaterThan(5);
    expect(restAt(9, [0.6, 0.4], true)[0]).toBeCloseTo(restAt(0, [0.6, 0.4], true)[0]);
    expect(restAt(0, [1, 0], true).every((v) => v >= 0 && v <= 1)).toBe(true);
  });

  it("a canvas that fills the box maps straight through; a film shown with object-fit: cover is mapped through the crop", () => {
    expect(coverMap(0.25, 0.75, R, null)).toEqual({ x: 0.25, y: 0.75, shownH: 400 });
    // a 16:9 film in a 2:1 box: the film is as wide as the box and its top and bottom are cut off
    const m = coverMap(0.5, 0, R, { w: 1600, h: 900 });
    expect(m.x).toBeCloseTo(0.5);
    expect(m.y).toBeCloseTo(0.5 - 0.5 * 400 / 450);
    expect(m.shownH).toBeCloseTo(450);
  });

  it("the shader's numbers: centre on the picture, radius in picture heights, the picture's aspect", () => {
    expect(uniforms([0.5, 0.5], 0.2, R, null)).toEqual({ centre: [0.5, 0.5], radius: 80 / 400, aspect: 2 });
    const f = uniforms([0.5, 0.5], 0.2, R, { w: 1600, h: 900 });
    expect(f.radius).toBeCloseTo(80 / 450);
    expect(f.aspect).toBeCloseTo(16 / 9);
  });

  it("the lens is full inside, gone outside, with an edge as soft as asked", () => {
    expect(lensMask(0, 0.35)).toBe(1);
    expect(lensMask(0.6, 0.35)).toBe(1);
    expect(lensMask(1, 0.35)).toBe(0);
    expect(lensMask(0.825, 0.35)).toBeCloseTo(0.5);
    expect(lensMask(1, 0)).toBe(0);              // a sharp lens: a 1% edge
    expect(lensMask(0.985, 0)).toBe(1);
    expect(lensMask(0.5, 0)).toBe(1);
  });

  it("the torch: full in the middle, falling off smoothly, a soft edge and a dim spill beyond", () => {
    expect(lightFalloff(0, 0.35)).toBe(1);
    let prev = 2;
    for (let d = 0; d <= 3; d += 0.05) {
      const v = lightFalloff(d, 0.35);
      expect(v).toBeLessThanOrEqual(prev + 1e-9);
      expect(v).toBeGreaterThan(0);
      expect(v).toBeLessThanOrEqual(1);
      prev = v;
    }
    expect(lightFalloff(0.5, 0.35)).toBeGreaterThan(0.85);       // the pool is bright across
    expect(lightFalloff(1.5, 0.35)).toBeLessThan(0.05);          // and dim well beyond its edge
    expect(lightFalloff(1, 0.05)).toBeLessThan(lightFalloff(1, 0.6));   // a soft edge reaches further
  });

  it("the looks outside the lens, as GLSL", () => {
    expect(baseGlsl("mono")).toContain("dot(c");
    expect(baseGlsl("dim")).toContain("0.55");
    expect(baseGlsl("blur")).toBe("bl");
    expect(baseGlsl("#ff0000")).toBe("ptrTint(c, vec3(1.0000, 0.0000, 0.0000))");
    expect(baseGlsl("none")).toBe("c");
    expect(POINTER_GLSL).toContain("float ptrFalloff(float d)");
    expect(POINTER_GLSL).toContain("vec3 ptrLight(");
  });

  it("the device: reduced motion from the media query", () => {
    media.reduced = true;
    expect(pointerEnv().reduced).toBe(true);
    media.reduced = false;
    expect(pointerEnv()).toEqual({ reduced: false, hover: false });
  });
});

describe("following the mouse and the finger", () => {
  function setup(env: { reduced?: boolean; hover?: boolean } = {}) {
    const el = document.createElement("div");
    document.body.appendChild(el);
    box(el, R.top, R.height, { left: R.left, width: R.width });
    const target = new EventTarget();
    const t = trackPointer(el, { rest: [0.6, 0.4], radius: 0.2 }, { reduced: !!env.reduced, hover: env.hover ?? true, target });
    /** run frames at 60 fps until the lens settles; how many frames reported a move */
    const settle = (from = 0, n = 240) => { let moves = 0; for (let i = 1; i <= n; i++) if (t.update(from + i / 60)) moves++; return moves; };
    return { el, t, target, settle };
  }

  it("starts at rest, reports that once, then nothing while nothing moves (no redraws)", () => {
    const { t, settle } = setup();
    expect(t.update(0)).toBe(true);
    expect(t.pos).toEqual([0.6, 0.4]);
    expect(settle()).toBe(0);
  });

  it("goes to the mouse over the picture, eased, lands exactly, then stops reporting", () => {
    const { t, target, settle } = setup();
    t.update(0);
    fire(target, "pointermove", { pointerType: "mouse", clientX: 300, clientY: 150 });   // u 0.25, v 0.25
    expect(t.update(1 / 60)).toBe(true);
    expect(t.pos[0]).toBeGreaterThan(0.25);
    expect(t.pos[0]).toBeLessThan(0.6);
    expect(settle(1 / 60)).toBeGreaterThan(5);
    expect(t.pos).toEqual([0.25, 0.25]);
    expect(t.update(10)).toBe(false);
  });

  it("goes home when the mouse leaves the picture, or the window", () => {
    const { t, target, settle } = setup();
    fire(target, "pointermove", { pointerType: "mouse", clientX: 300, clientY: 150 });
    settle();
    fire(target, "pointermove", { pointerType: "mouse", clientX: 950, clientY: 150 });   // off the box
    settle(5, 600);
    expect(t.pos).toEqual([0.6, 0.4]);
    fire(target, "pointermove", { pointerType: "mouse", clientX: 300, clientY: 150 });
    settle(20);
    fire(target, "pointerout", { relatedTarget: document.body });   // into another element: still following
    settle(30);
    expect(t.pos).toEqual([0.25, 0.25]);
    fire(target, "pointerout", { relatedTarget: null });             // out of the window
    settle(40, 600);
    expect(t.pos).toEqual([0.6, 0.4]);
  });

  it("a finger: above it while it touches (even past the edge, clamped), home when it lifts", () => {
    const { t, target, settle } = setup({ hover: false });
    fire(target, "pointermove", { pointerType: "touch", clientX: 300, clientY: 150 });   // a touch's pointer events are ignored
    fire(target, "touchstart", { touches: [{ clientX: 500, clientY: 350 }] });           // u 0.5, v 0.75
    settle();
    expect(t.pos[0]).toBeCloseTo(0.5);
    expect(t.pos[1]).toBeCloseTo(0.75 - (80 + 12) / 400);
    fire(target, "touchmove", { touches: [{ clientX: 500, clientY: 60 }] });
    settle(5);
    expect(t.pos[1]).toBe(0);
    fire(target, "pointerout", { relatedTarget: null });          // a finger is not let go of by leaving the window
    fire(target, "touchend", { touches: [] });
    settle(10, 900);
    const home = restAt(10 + 900 / 60, [0.6, 0.4], true);
    expect(t.pos[0]).toBeCloseTo(home[0], 2);
    fire(target, "touchstart", { touches: [{ clientX: 500, clientY: 350 }] });
    fire(target, "touchcancel", {});
    expect(t.update(30)).toBe(true);
  });

  it("on a phone with nothing touching it drifts gently (so it keeps moving, slowly)", () => {
    const { t, settle } = setup({ hover: false });
    t.update(0);
    const a = [...t.pos];
    expect(settle(0, 120)).toBeGreaterThan(100);
    expect(Math.hypot(t.pos[0] - a[0], t.pos[1] - a[1])).toBeLessThan(0.1);
  });

  it("reduced motion: it stays at rest whatever the mouse or the finger does, and asks for one draw", () => {
    const { t, target, settle } = setup({ reduced: true, hover: false });
    expect(t.update(0)).toBe(true);
    fire(target, "pointermove", { pointerType: "mouse", clientX: 300, clientY: 150 });
    fire(target, "touchstart", { touches: [{ clientX: 500, clientY: 350 }] });
    expect(settle()).toBe(0);
    expect(t.pos).toEqual([0.6, 0.4]);
    t.dirty();                       // the canvas was resized (cleared): one more draw
    expect(t.update(9)).toBe(true);
    expect(t.update(10)).toBe(false);
  });

  it("dispose stops listening", () => {
    const { t, target, settle } = setup();
    settle();
    t.dispose();
    fire(target, "pointermove", { pointerType: "mouse", clientX: 300, clientY: 150 });
    expect(settle(5)).toBe(0);
    expect(t.pos).toEqual([0.6, 0.4]);
  });

  it("listens on the window by default", () => {
    const el = document.createElement("div");
    box(el, R.top, R.height, { left: R.left, width: R.width });
    const t = trackPointer(el, { rest: [0.5, 0.5], radius: 0.2 }, { reduced: false, hover: true });
    fire(window, "pointermove", { pointerType: "mouse", clientX: 300, clientY: 150 });
    for (let i = 1; i < 300; i++) t.update(i / 60);
    expect(t.pos).toEqual([0.25, 0.25]);
    t.dispose();
  });
});
