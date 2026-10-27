/**
 * Movers on a diorama (players/diorama/movers.ts): where a scroll mover is for a scroll position, what it carries, and
 * where a traffic mover is at a time.
 */
import { describe, expect, it } from "vitest";
import { arcAt, loadAt, pathAt, timeline, trafficAt } from "../src/players/diorama/movers";

const path: [number, number][] = Array.from({ length: 11 }, (_, i) => [i, 0]);

describe("pathAt", () => {
  it("walks a dense path by arc length, clamped to its ends", () => {
    expect(pathAt(path, 10, 2.5)).toMatchObject({ x: 2.5, z: 0, dx: 1, dz: 0 });
    expect(pathAt(path, 10, -3).x).toBe(0);
    expect(pathAt(path, 10, 99).x).toBe(10);
    expect(pathAt([], 0, 1)).toMatchObject({ x: 0, z: 0 });
  });
});

describe("a scroll mover's timeline", () => {
  // steps: 0 wide, 1 stop A, 2 stop B, 3 wide; their rest windows
  const rests: [number, number][] = [[-1, 0.15], [0.3, 0.4], [0.55, 0.65], [0.85, 2]];
  const stops = [{ s: 3, step: 1 }, { s: 6, step: 2 }];
  const k = timeline(stops, rests, 10);
  it("waits at the start, at each stop through its rest, and reaches the end as the last step rests", () => {
    expect(arcAt(k, 0)).toBe(0);
    expect(arcAt(k, 0.15)).toBe(0);
    expect(arcAt(k, 0.3)).toBe(3);
    expect(arcAt(k, 0.35)).toBe(3);
    expect(arcAt(k, 0.4)).toBe(3);
    expect(arcAt(k, 0.475)).toBeCloseTo(4.5, 6);           // half-way between the two stops
    expect(arcAt(k, 0.6)).toBe(6);
    expect(arcAt(k, 0.85)).toBe(10);
    expect(arcAt(k, 1)).toBe(10);
  });
  it("never goes back", () => {
    let last = -1;
    for (let p = 0; p <= 1; p += 0.005) { const s = arcAt(k, p); expect(s).toBeGreaterThanOrEqual(last - 1e-9); last = s; }
  });
  it("what it carries changes in the middle of a stop's rest", () => {
    const st = [{ step: 1, carry: "a.webp" }, { step: 2, carry: "b.webp" }];
    expect(loadAt(null, st, rests, 0.2)).toEqual({ from: null, to: null, mix: 0 });
    const mid = loadAt(null, st, rests, 0.34);
    expect(mid.from).toBe(null); expect(mid.to).toBe("a.webp"); expect(mid.mix).toBeGreaterThan(0); expect(mid.mix).toBeLessThan(1);
    expect(loadAt(null, st, rests, 0.45)).toEqual({ from: "a.webp", to: "a.webp", mix: 0 });
    expect(loadAt(null, st, rests, 0.9)).toEqual({ from: "b.webp", to: "b.webp", mix: 0 });
  });
});

describe("trafficAt", () => {
  // rests at (0,0) until 1 s, moves to (1,0) by 2 s, rests, moves to (1,1) from 3 s to 4 s
  const keys = [0, 0, 0, 1, 0, 0, 2, 1, 0, 3, 1, 0, 4, 1, 1];
  it("rests, then travels each move in a straight line, easing in and out", () => {
    expect(trafficAt(keys, 0.5)).toEqual([0, 0]);
    expect(trafficAt(keys, 1.5)[0]).toBeCloseTo(0.5, 6);
    expect(trafficAt(keys, 1.25)[0]).toBeLessThan(0.25);    // eased: slow off the mark
    expect(trafficAt(keys, 2.5)).toEqual([1, 0]);
    expect(trafficAt(keys, 3.5)[1]).toBeCloseTo(0.5, 6);
    expect(trafficAt(keys, 9)).toEqual([1, 1]);
    expect(trafficAt([], 1)).toEqual([0, 0]);
  });
});
