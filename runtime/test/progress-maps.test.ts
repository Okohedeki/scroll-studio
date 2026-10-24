/** The maps from scroll progress to something else: reveal keys, the one-take film clock, the light's time of day. */
import { describe, expect, it } from "vitest";
import { amountsAt, type RevealKey } from "../src/lib/revealKeys";
import { timeAt as filmTime } from "../src/players/journey";
import { celestial, timeAt as lightTime } from "../src/players/light";

describe("reveal keys (amountsAt)", () => {
  const keys: RevealKey[] = [{ at: 0, a: 0 }, { at: 0.5, a: 1 }, { at: 1, a: 0 }];

  it("holds the first key's value before it and the last key's value after it", () => {
    const ks: RevealKey[] = [{ at: 0.2, a: 0.3 }, { at: 0.8, a: 0.9 }];
    expect(amountsAt(ks, ["a"], 0).a).toBe(0.3);
    expect(amountsAt(ks, ["a"], 0.2).a).toBe(0.3);
    expect(amountsAt(ks, ["a"], 1).a).toBe(0.9);
    expect(amountsAt(ks, ["a"], 0.8).a).toBe(0.9);
  });

  it("eases between two keys with smoothstep by default", () => {
    expect(amountsAt(keys, ["a"], 0.25).a).toBeCloseTo(0.5, 12);
    expect(amountsAt(keys, ["a"], 0.125).a).toBeCloseTo(0.15625, 12);
    expect(amountsAt(keys, ["a"], 0.5).a).toBe(1);
    expect(amountsAt(keys, ["a"], 0.75).a).toBeCloseTo(0.5, 12);
  });

  it("interpolates linearly when asked", () => {
    expect(amountsAt(keys, ["a"], 0.125, "linear").a).toBeCloseTo(0.25, 12);
  });

  it("a region with no key is 0, and a key that does not name a region is ignored for it", () => {
    const ks: RevealKey[] = [{ at: 0, a: 1 }, { at: 0.5, b: 1 }, { at: 1, a: 0 }];
    const out = amountsAt(ks, ["a", "b", "c"], 0.5, "linear");
    expect(out.c).toBe(0);
    expect(out.b).toBe(1);                    // only one key names b: it holds everywhere
    expect(out.a).toBeCloseTo(0.5, 12);       // a eases across the key that skips it
  });

  it("does not depend on the order keys are written in", () => {
    const shuffled = [keys[2], keys[0], keys[1]];
    for (const p of [0, 0.1, 0.5, 0.9, 1]) expect(amountsAt(shuffled, ["a"], p)).toEqual(amountsAt(keys, ["a"], p));
  });

  it("reduced motion has no easing: a region jumps to the end value as soon as the change begins, and holds when nothing changes", () => {
    const out = amountsAt(keys, ["a"], 0.01, "smooth", true);
    expect(out.a).toBe(1);
    expect(amountsAt(keys, ["a"], 0.6, "smooth", true).a).toBe(0);
    const flat: RevealKey[] = [{ at: 0, a: 0.4 }, { at: 0.5, a: 0.4 }, { at: 1, a: 1 }];
    expect(amountsAt(flat, ["a"], 0.25, "smooth", true).a).toBe(0.4);
  });

  it("a window of zero length does not divide by zero", () => {
    const step: RevealKey[] = [{ at: 0.5, a: 0 }, { at: 0.5, a: 1 }];
    for (const p of [0.4, 0.5, 0.6]) expect(Number.isFinite(amountsAt(step, ["a"], p).a)).toBe(true);
    expect(amountsAt(step, ["a"], 0.6).a).toBe(1);
  });
});

describe("one-take film clock (journey timeAt)", () => {
  const map = [[0, 0], [0.4, 2], [0.6, 2], [1, 5]];

  it("is linear between the map's points", () => {
    expect(filmTime(map, 0.2)).toBeCloseTo(1, 12);
    expect(filmTime(map, 0.8)).toBeCloseTo(3.5, 12);
  });

  it("holds still across a hold (two points at the same film time)", () => {
    for (const p of [0.4, 0.5, 0.6]) expect(filmTime(map, p)).toBe(2);
  });

  it("clamps to the first and last film time outside the map", () => {
    expect(filmTime(map, -1)).toBe(0);
    expect(filmTime(map, 0)).toBe(0);
    expect(filmTime(map, 1)).toBe(5);
    expect(filmTime(map, 2)).toBe(5);
  });

  it("a jump (two points at the same progress) takes the later film time and never divides by zero", () => {
    const jump = [[0, 0], [0.5, 1], [0.5, 4], [1, 5]];
    expect(filmTime(jump, 0.5)).toBe(1);
    expect(filmTime(jump, 0.50001)).toBeCloseTo(4, 3);
    const degenerate = [[0, 0], [0, 3]];
    expect(filmTime(degenerate, 0.5)).toBe(3);
  });
});

describe("time of day (light)", () => {
  const holds = [{ t: 0, a: 0, b: 0.2 }, { t: 1, a: 0.4, b: 0.6 }, { t: 3, a: 0.8, b: 1 }];

  it("holds each time while its step is read", () => {
    expect(lightTime(0, holds)).toBe(0);
    expect(lightTime(0.2, holds)).toBe(0);
    expect(lightTime(0.4, holds)).toBe(1);
    expect(lightTime(0.5, holds)).toBe(1);
    expect(lightTime(0.9, holds)).toBe(3);
    expect(lightTime(1, holds)).toBe(3);
  });

  it("travels between holds, smoothly (no jump at either end of the journey)", () => {
    expect(lightTime(0.3, holds)).toBeCloseTo(0.5, 12);                    // the middle of the first journey
    const eps = 1e-6;
    expect(lightTime(0.2 + eps, holds)).toBeCloseTo(0, 5);
    expect(lightTime(0.4 - eps, holds)).toBeCloseTo(1, 5);
    let prev = -1;
    for (let p = 0; p <= 1; p += 0.01) { const t = lightTime(p, holds); expect(t).toBeGreaterThanOrEqual(prev - 1e-12); prev = t; }
  });

  it("is time 0 with no holds, and the first hold before it", () => {
    expect(lightTime(0.5, [])).toBe(0);
    expect(lightTime(0, [{ t: 2, a: 0.3, b: 0.4 }])).toBe(2);
    expect(lightTime(1, [{ t: 2, a: 0.3, b: 0.4 }])).toBe(2);
  });

  describe("celestial: the sun's arc, and the moon's after dark", () => {
    const sun = { rise: [0.1, 0.5], noon: [0.5, 0.06], set: [0.92, 0.5] };

    it("the sun stands at its rise point at 5:30 and its set point at 20:30", () => {
      const r = celestial(5.5, sun), s = celestial(20.5, sun);
      expect(r.x).toBeCloseTo(0.1, 12); expect(r.y).toBeCloseTo(0.5, 12); expect(r.k).toBeCloseTo(0, 12);
      expect(s.x).toBeCloseTo(0.92, 12); expect(s.y).toBeCloseTo(0.5, 12);
      expect(r.moon).toBe(false); expect(s.moon).toBe(false);
    });

    it("passes through the noon point at the middle of the day, as high as it gets", () => {
      const n = celestial(13, sun);
      expect(n.u).toBeCloseTo(0.5, 12);
      expect(n.x).toBeCloseTo(0.5, 6);
      expect(n.y).toBeCloseTo(0.06, 6);
      expect(n.k).toBeCloseTo(1, 12);
    });

    it("the moon takes the arc between 20:30 and 5:30, across midnight", () => {
      const dusk = celestial(21, sun), mid = celestial(1, sun), dawn = celestial(5, sun);
      expect(dusk.moon && mid.moon && dawn.moon).toBe(true);
      expect(mid.u).toBeCloseTo((25 - 20.5) / 9, 12);
      expect(dusk.u).toBeLessThan(mid.u);
      expect(mid.u).toBeLessThan(dawn.u);
      expect(celestial(2, sun).u).toBeCloseTo(celestial(26, sun).u, 12);   // hour 2 is the same as 26 (the same night)
    });
  });
});
