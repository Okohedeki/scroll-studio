/**
 * Living details (lib/live.ts, players/liveStill.ts): reading the build's settings, where a region is on the picture, the
 * timing and maths of each kind (every motion periodic, so the loop has no seam), the uniform pack, the mask atlas, the frame
 * clock, reduced motion and pausing, and the layer laid over a plain picture.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { media } from "./helpers";
import {
  atlasCells, boxAspect, dirOf, driftOffset, due, edge, emptyPack, flowAt, FPS, hash, hexRgb, KINDS, LIVE_GLSL, local, maskAtlas,
  packView, parsePos, PER, PERIOD, pictureRect, POINTS, readLive, riseField, riseGrid, screenOver, shouldRun, star, sweepBand,
  sweepBeam, twinkle, uvMap, type LiveDetail,
} from "../src/lib/live";

const D = (o: Partial<LiveDetail> & { kind: LiveDetail["kind"] }): LiveDetail =>
  readLive([{ box: [0.2, 0.2, 0.6, 0.6], color: "#ffeecc", ...o }])[0];

describe("reading the build's settings", () => {
  it("fills defaults and keeps what is valid", () => {
    const [d] = readLive([{ kind: "drift", box: [0.1, 0.2, 0.5, 0.6] }]);
    expect(d).toEqual({ kind: "drift", box: [0.1, 0.2, 0.5, 0.6], speed: 1, strength: 0.6, softness: 0.25, count: 12, color: "#ffffff",
      angle: 0, origin: null, mask: null, points: [] });
    const [g] = readLive([{ kind: "sweep", box: [0, 0, 1, 1], speed: 9, strength: -1, count: 99, color: "#A0b0C0", origin: [0.1, 0.9],
      mask: "m.png", points: [[0.5, 0.5, 2], [0.1], "x"] }]);
    expect(g.speed).toBe(4); expect(g.strength).toBe(0); expect(g.count).toBe(POINTS);
    expect(g.color).toBe("#A0b0C0"); expect(g.origin).toEqual([0.1, 0.9]); expect(g.mask).toBe("m.png");
    expect(g.points).toEqual([[0.5, 0.5, 1]]);
  });
  it("leaves out anything malformed, and keeps at most four", () => {
    expect(readLive(null)).toEqual([]);
    expect(readLive({ kind: "drift" })).toEqual([]);
    expect(readLive([null, { kind: "sparkle", box: [0, 0, 1, 1] }, { kind: "drift" }, { kind: "drift", box: [0.5, 0, 0.4, 1] },
      { kind: "drift", box: [0, 0, 1] }])).toEqual([]);
    expect(readLive(Array(6).fill({ kind: "glint", box: [0, 0, 1, 1] }))).toHaveLength(PER);
  });
});

describe("where the region is", () => {
  it("a point of the picture in the box, and the box's soft edge", () => {
    const b: [number, number, number, number] = [0.2, 0.4, 0.6, 0.8];
    expect(local([0.4, 0.6], b)[0]).toBeCloseTo(0.5, 9); expect(local([0.4, 0.6], b)[1]).toBeCloseTo(0.5, 9);
    expect(edge([0.5, 0.5], 0.25)).toBe(1);
    expect(edge([-0.01, 0.5], 0.25)).toBe(0);
    expect(edge([0.5, 1.01], 0.25)).toBe(0);
    expect(edge([0.125, 0.5], 0.25)).toBeCloseTo(0.5, 5);          // half way through the soft edge
    expect(edge([0.01, 0.5], 0)).toBe(1);                            // no softness: a hard box
    expect(boxAspect(b, 16 / 9)).toBeCloseTo(16 / 9, 5);
  });
  it("a picture's rectangle in its box by object-fit, and the shader's map onto it", () => {
    expect(parsePos("left")).toBe(0); expect(parsePos("bottom")).toBe(1); expect(parsePos("center")).toBe(0.5);
    expect(parsePos("25%")).toBe(0.25); expect(parsePos("junk")).toBe(0.5);
    // a 2:1 picture covering a 100 x 100 box: 200 wide, centred
    expect(pictureRect(100, 100, 2, "cover", "50% 50%")).toEqual({ x: -50, y: 0, w: 200, h: 100 });
    expect(pictureRect(100, 100, 2, "cover", "left")).toEqual({ x: -0, y: 0, w: 200, h: 100 });
    expect(pictureRect(100, 100, 2, "contain", "50% 50%")).toEqual({ x: 0, y: 25, w: 100, h: 50 });
    expect(pictureRect(100, 100, 2, "fill", "50% 50%")).toEqual({ x: 0, y: 0, w: 100, h: 100 });
    expect(pictureRect(100, 100, 2, "none", "50% 50%")).toBeNull();
    expect(pictureRect(0, 100, 2, "cover", "50%")).toBeNull();
    const m = uvMap(100, 100, { x: -50, y: 0, w: 200, h: 100 });
    expect(m).toEqual([0.5, 1, 0.25, -0]);
    expect([0 * m[0] + m[2], 1 * m[0] + m[2]]).toEqual([0.25, 0.75]);   // the box shows the middle half of the picture
  });
});

describe("the kinds", () => {
  const right = dirOf(0), down = dirOf(90);
  it("directions: 0 to the right, 90 down", () => {
    expect(right[0]).toBeCloseTo(1); expect(right[1]).toBeCloseTo(0);
    expect(down[0]).toBeCloseTo(0); expect(down[1]).toBeCloseTo(1);
  });
  it("drift slides to and fro along its direction, as far as its strength says, and loops", () => {
    expect(driftOffset(0, 1, right)).toEqual([0, 0]);
    const q = driftOffset(PERIOD.drift / 4, 1, right);
    expect(q[0]).toBeCloseTo(0.035); expect(q[1]).toBeCloseTo(0);
    expect(driftOffset((3 * PERIOD.drift) / 4, 0.5, down)[1]).toBeCloseTo(-0.0175);
    const a = driftOffset(3.3, 0.7, right), b = driftOffset(3.3 + PERIOD.drift, 0.7, right);
    expect(a[0]).toBeCloseTo(b[0], 9);
  });
  it("a sweep crosses once in the first half of its cycle and is dark in the second", () => {
    const at = (x: number, t: number) => sweepBand([x, 0.5], t, right, 1);
    // the band's centre moves left to right over the pass
    const peakAt = (t: number) => [0.1, 0.3, 0.5, 0.7, 0.9].reduce((best, x) => (at(x, t) > at(best, t) ? x : best), 0.1);
    expect(peakAt(PERIOD.sweep * 0.12)).toBeLessThan(peakAt(PERIOD.sweep * 0.25));
    expect(peakAt(PERIOD.sweep * 0.25)).toBeLessThan(peakAt(PERIOD.sweep * 0.4));
    expect(at(0.5, PERIOD.sweep * 0.25)).toBeGreaterThan(0.5);
    expect(at(0.5, PERIOD.sweep * 0.75)).toBe(0);
    expect(at(0.5, PERIOD.sweep * 0.5)).toBeCloseTo(0, 5);       // fades out at the end of a pass, never NaN
    expect(at(0.3, 1.1)).toBeCloseTo(at(0.3, 1.1 + PERIOD.sweep), 9);
    expect(sweepBand([0.5, 0.5], -1, right, 2)).toBeGreaterThanOrEqual(0);     // negative time wraps
  });
  it("a beam turns round its origin once a cycle", () => {
    const o: [number, number] = [0.5, 0.5];
    expect(sweepBeam([0.9, 0.5], 0, right, o, 1)).toBeGreaterThan(0.5);        // starts along its direction
    expect(sweepBeam([0.1, 0.5], 0, right, o, 1)).toBeLessThan(0.01);
    expect(sweepBeam([0.1, 0.5], PERIOD.beam / 2, right, o, 1)).toBeGreaterThan(0.5);
    expect(sweepBeam([0.5, 0.9], PERIOD.beam / 4, right, o, 1)).toBeGreaterThan(0.5);   // a quarter turn: pointing down
    expect(sweepBeam([0.7, 0.2], 2, right, o, 1.5)).toBeCloseTo(sweepBeam([0.7, 0.2], 2 + PERIOD.beam, right, o, 1.5), 9);
  });
  it("a glint twinkles briefly each cycle, its star brightest at the point with four rays", () => {
    expect(twinkle(0, 0)).toBe(0);
    expect(twinkle(PERIOD.glint * 0.175, 0)).toBeCloseTo(1);
    expect(twinkle(PERIOD.glint * 0.5, 0)).toBe(0);
    expect(twinkle(0, 0.175)).toBeCloseTo(1);                     // the phase staggers it
    expect(twinkle(-1, 0.3)).toBeCloseTo(twinkle(-1 + PERIOD.glint, 0.3), 9);
    expect(star([0, 0], 0.02)).toBe(1);
    const ray = star([0.02, 0], 0.02), diag = star([0.014, 0.014], 0.02);
    expect(ray).toBeGreaterThan(diag * 3);                          // along a ray, much brighter than between them
    expect(star([0, 0.02], 0.02)).toBeCloseTo(ray, 9);
    expect(star([0.2, 0.2], 0.02)).toBeLessThan(1e-6);
  });
  it("rise: a grid shaped to the box, specks only between its fades, moving up", () => {
    expect(riseGrid(12, 1)).toEqual([3, 4]);
    expect(riseGrid(1, 0.1)).toEqual([2, 2]);
    const field = (t: number) => { let s = 0; for (let x = 0; x < 1; x += 0.02) for (let y = 0; y < 1; y += 0.02) s += riseField([x, y], t, 16, 1); return s; };
    expect(field(0)).toBeGreaterThan(0);
    for (let x = 0; x < 1; x += 0.05) { expect(riseField([x, 0.001], 2, 16, 1)).toBeCloseTo(0, 3); expect(riseField([x, 0.999], 2, 16, 1)).toBeCloseTo(0, 2); }
    // the brightest speck in a column is higher up a moment later
    const peak = (t: number) => { let best = [0, 0]; for (let y = 0.45; y < 0.85; y += 0.002) for (let x = 0; x < 1; x += 0.01) { const v = riseField([x, y], t, 16, 1); if (v > best[0]) best = [v, y]; } return best[1]; };
    expect(peak(0.3)).toBeLessThan(peak(0) + 0.01);
    expect(hash(1, 2)).toBeGreaterThanOrEqual(0); expect(hash(1, 2)).toBeLessThan(1); expect(hash(1, 2)).toBe(hash(1, 2));
  });
  it("flow: a small displacement mostly across its ripples, a shimmer near 1, and still at strength 0", () => {
    let most = 0;
    for (let i = 0; i < 50; i++) {
      const f = flowAt([i * 0.031, i * 0.017], i * 0.3, 1, right);
      most = Math.max(most, Math.hypot(...f.d));
      expect(Math.abs(f.shimmer - 1)).toBeLessThanOrEqual(0.05 + 1e-9);
    }
    expect(most).toBeGreaterThan(0.001); expect(most).toBeLessThan(0.007);
    const across = flowAt([0.3, 0.2], 1, 1, right).d;              // ripples run along x: the big motion is in y
    expect(Math.abs(across[1])).toBeGreaterThan(0);
    expect(flowAt([0.3, 0.2], 1, 0, right)).toEqual({ d: [0, 0], shimmer: 1 });
  });
  it("light is laid over like a screen: never darker, never past white", () => {
    expect(screenOver(0.2, 0)).toBeCloseTo(0.2); expect(screenOver(0.2, 1)).toBe(1); expect(screenOver(0.5, 0.5)).toBe(0.75);
    expect(screenOver(0.5, 2)).toBe(1);
  });
});

describe("the uniforms", () => {
  it("packs each view's details, its glint points after the ones before, and leaves unused slots empty", () => {
    const pack = emptyPack(2);
    expect(pack.box).toHaveLength(2 * PER * 4); expect(pack.p).toHaveLength(2 * POINTS * 4);
    const pts: [number, number, number][] = [[0.1, 0.2, 1], [0.3, 0.4, 0.5], [0.5, 0.6, 0.7]];
    packView(pack, 1, [
      D({ kind: "glint", points: pts, count: 2 } as any),
      D({ kind: "sweep", origin: [0.1, 0.9], angle: 90 } as any),
      D({ kind: "glint", points: pts } as any),
    ], [null, [0.5, 0, 0.25, 0.25]]);
    const slot = (arr: Float32Array, k: number) => [...arr.slice((PER + k) * 4, (PER + k) * 4 + 4)];
    expect(slot(pack.a, 0)[0]).toBe(KINDS.glint);
    expect(slot(pack.b, 0).slice(2)).toEqual([POINTS, 2]);              // view 1's points start at POINTS; count caps them
    expect(slot(pack.b, 2).slice(2)).toEqual([POINTS + 2, 3]);          // the second glint's follow the first's
    expect([...pack.p.slice((POINTS + 2) * 4, (POINTS + 2) * 4 + 3)].map((v) => +v.toFixed(3))).toEqual([0.1, 0.2, 1]);
    const sw = slot(pack.b, 1);
    expect(sw[0]).toBeCloseTo(0); expect(sw[1]).toBeCloseTo(1); expect(sw[2]).toBeCloseTo(0.1); expect(sw[3]).toBeCloseTo(0.9);
    expect(slot(pack.m, 1)).toEqual([0.5, 0, 0.25, 0.25]); expect(slot(pack.m, 0)).toEqual([0, 0, 0, 0]);
    expect(slot(pack.c, 0).map((v) => +v.toFixed(3))).toEqual([1, 0.933, 0.8, 2]);
    expect(slot(pack.a, 3)).toEqual([0, 0, 0, 0]);                      // no fourth detail: kind 0, skipped
    expect([...pack.a.slice(0, PER * 4)].every((v) => v === 0)).toBe(true);   // view 0 untouched
    const drift = emptyPack(1);
    packView(drift, 0, [D({ kind: "drift" })]);
    expect([...drift.b.slice(2, 4)]).toEqual([-99, -99]);               // no origin, no points
    packView(drift, 0, []);                                             // repacking clears what was there
    expect([...drift.a].every((v) => v === 0)).toBe(true);
    expect(hexRgb("#ff8000")).toEqual([1, 128 / 255, 0]);
  });
  it("the GLSL declares what the pack fills and the functions the players call", () => {
    for (const n of ["uLvBox", "uLvA", "uLvB", "uLvC", "uLvM", "uLvP", "uLvT", "uLvAsp", "uLvMask", "vec3 liveApply("]) expect(LIVE_GLSL).toContain(n);
    expect(LIVE_GLSL).toContain(`#define LV_PER ${PER}`);
    expect(LIVE_GLSL).not.toMatch(/pow\(\(s - c\)/);                    // pow of a negative number is undefined in GLSL
  });
});

describe("the mask atlas", () => {
  it("lays cells in a near-square grid, inset half a texel", () => {
    expect(atlasCells(1).cells).toEqual([[0.5 / 256, 0.5 / 256, 255 / 256, 255 / 256]]);
    const g = atlasCells(5);
    expect([g.cols, g.rows]).toEqual([3, 2]);
    expect(g.cells[4][0]).toBeCloseTo((256 + 0.5) / 768); expect(g.cells[4][1]).toBeCloseTo((256 + 0.5) / 512);
  });
  it("draws only the masks there are; one that fails to load gets no cell", async () => {
    expect(await maskAtlas([null, undefined], async () => document.createElement("canvas"))).toEqual({ canvas: null, cells: [null, null] });
    const out = await maskAtlas(["a.png", null, "bad.png"], async (u) => { if (u === "bad.png") throw new Error("404"); return document.createElement("canvas"); });
    expect(out.canvas?.width).toBe(512); expect(out.canvas?.height).toBe(256);
    expect(out.cells[0]).toEqual(atlasCells(2).cells[0]); expect(out.cells[1]).toBeNull(); expect(out.cells[2]).toBeNull();
  });
});

describe("the clock, reduced motion and pausing", () => {
  it("30 frames a second, the first at once", () => {
    expect(FPS).toBe(30);
    expect(due(0, -1)).toBe(true);
    expect(due(1000, 990)).toBe(false);
    expect(due(1033, 1000)).toBe(true);
    expect(due(1010, 1000, 60)).toBe(false); expect(due(1016, 1000, 60)).toBe(true);
  });
  it("moves only on screen, in a visible tab, without reduced motion", () => {
    expect(shouldRun(true, false, false)).toBe(true);
    expect(shouldRun(false, false, false)).toBe(false);
    expect(shouldRun(true, true, false)).toBe(false);
    expect(shouldRun(true, false, true)).toBe(false);
  });
});

// ---------------------------------------------------------------- the layer over a plain picture

interface Obs { cb: (es: unknown[]) => void; targets: Element[] }
let observers: Obs[] = [];

async function fresh() {
  vi.resetModules();
  return import("../src/players/liveStill");
}

describe("players/liveStill: the layer over a plain picture", () => {
  beforeEach(() => {
    observers = [];
    document.body.innerHTML = "";
    vi.stubGlobal("IntersectionObserver", class {
      o: Obs;
      constructor(cb: Obs["cb"]) { this.o = { cb, targets: [] }; observers.push(this.o); }
      observe(el: Element) { this.o.targets.push(el); }
      disconnect() {}
    });
    vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  });
  afterEach(() => { media.reduced = false; delete (window as any).__ssLive; });

  const entry = (d: unknown[] = [{ kind: "drift", box: [0.1, 0.1, 0.5, 0.5] }]) => JSON.stringify({ r: 1.5, d }).replace(/"/g, "&quot;");

  it("lays a canvas beside each marked <img> and over a marked backdrop, and skips what it cannot read", async () => {
    document.body.innerHTML = `<div class="m"><img id="a" src="a.webp" data-live="${entry()}"></div>
      <section id="b" style="background-image:url(b.webp)" data-live="${entry()}"></section>
      <img id="c" src="c.webp" data-live="{nope"><img id="d" src="d.webp" data-live="${entry([{ kind: "sparkle", box: [0, 0, 1, 1] }])}">`;
    const { start } = await fresh();
    const items = start();
    expect(items).toHaveLength(2);
    const a = document.getElementById("a")!, b = document.getElementById("b")!;
    expect(a.nextElementSibling?.className).toBe("ss-live");
    expect(a.nextElementSibling?.getAttribute("aria-hidden")).toBe("true");
    expect(b.firstElementChild?.className).toBe("ss-live");
    expect((b.firstElementChild as HTMLElement).style.zIndex).toBe("-1");
    expect(document.querySelectorAll(".ss-live")).toHaveLength(2);
    expect(items.every((i) => i.state === "idle")).toBe(true);           // nothing set up until it is near
  });

  it("with reduced motion it does nothing at all: the still picture", async () => {
    media.reduced = true;
    document.body.innerHTML = `<img src="a.webp" data-live="${entry()}">`;
    const { start } = await fresh();
    expect(start()).toEqual([]);
    expect(document.querySelector(".ss-live")).toBeNull();
  });

  it("without WebGL2 the layer is removed when the picture comes near", async () => {
    document.body.innerHTML = `<img id="a" src="a.webp" data-live="${entry()}">`;
    const { start } = await fresh();
    const [it] = start();
    HTMLCanvasElement.prototype.getContext = (() => null) as any;
    observers[0].cb([{ target: it.host, isIntersecting: true }]);
    expect(it.state).toBe("failed");
    expect(document.querySelector(".ss-live")).toBeNull();
    observers[1].cb([{ target: it.host, isIntersecting: true }]);         // seen later: still nothing, no error
    expect(it.seen).toBe(true);
  });

  it("a page without marked pictures starts nothing", async () => {
    const { start } = await fresh();
    expect(start()).toEqual([]);
    expect(observers).toHaveLength(0);
  });
});
