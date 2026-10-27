/**
 * stages: the maths of scrolling through a sequence of aligned stills (players/stages.ts): where the scroll holds, how far
 * a pixel has been revealed, where the front's band is, and how a picture is fitted into the stage.
 */
import { describe, expect, it } from "vitest";
import { fitTransform, frontAt, revealAt, stageAt } from "../src/players/stages";

const holds = [{ t: 0, a: 0.1, b: 0.2 }, { t: 1, a: 0.4, b: 0.5 }, { t: 3, a: 0.8, b: 0.9 }];

describe("stageAt", () => {
  it("holds still on each step's stage and eases between them", () => {
    expect(stageAt(0, holds)).toBe(0);
    expect(stageAt(0.15, holds)).toBe(0);
    expect(stageAt(0.45, holds)).toBe(1);
    expect(stageAt(0.3, holds)).toBeCloseTo(0.5, 6);         // half-way between holds, half-way between stages
    expect(stageAt(0.65, holds)).toBeCloseTo(2, 6);          // a step may skip a stage: it passes through it
    expect(stageAt(1, holds)).toBe(3);
    expect(stageAt(0.5, [])).toBe(0);
  });
  it("only moves forward as the scroll does", () => {
    let last = -1;
    for (let p = 0; p <= 1; p += 0.01) { const v = stageAt(p, holds); expect(v).toBeGreaterThanOrEqual(last); last = v; }
  });
});

describe("revealAt and frontAt", () => {
  it("reveals nothing at the start and everything at the end, in the order of the map", () => {
    for (const s of [0, 0.3, 1]) { expect(revealAt(s, 0, 0.05)).toBe(0); expect(revealAt(s, 1, 0.05)).toBe(1); }
    expect(revealAt(0.2, 0.5, 0.05)).toBe(1);               // early pixels are in by half-way
    expect(revealAt(0.8, 0.5, 0.05)).toBe(0);               // late ones are not yet
  });
  it("puts the band on the front, and none before or after the reveal", () => {
    expect(frontAt(0.5, 0, 0.05, 0.02)).toBe(0);
    expect(frontAt(0.5, 1, 0.05, 0.02)).toBe(0);
    const at = 0.5;
    const f = (at + 0.025) / 1.05;                          // the front's centre reaches s = 0.5 here
    expect(frontAt(at, f, 0.05, 0.02)).toBeCloseTo(1, 6);
    expect(frontAt(0.1, f, 0.05, 0.02)).toBeLessThan(1e-6);
  });
});

describe("fitTransform", () => {
  it("contains a square picture against the right edge of a wide stage", () => {
    const t = fitTransform({ fit: "contain", position: [1, 0.5], zoom: 1 }, 1600, 900, 1000, 1000);
    const pw = 900 / 1600;                                  // the picture's width in stage widths
    expect(t.sx).toBeCloseTo(1 / pw, 6);
    expect(t.sy).toBeCloseTo(1, 6);
    expect(t.ox).toBeCloseTo(1 - pw / 2, 6);                // its right edge on the stage's
    expect(t.oy).toBeCloseTo(0.5, 6);
  });
  it("contains it at the bottom of a tall stage, smaller with zoom", () => {
    const t = fitTransform({ fit: "contain", position: [0.5, 1], zoom: 0.8 }, 390, 844, 1000, 1000);
    const ph = (390 / 844) * 0.8;
    expect(t.sy).toBeCloseTo(1 / ph, 6);
    expect(t.oy).toBeCloseTo(1 - ph / 2, 6);
  });
  it("covers a tall stage, keeping the chosen point in view but never showing past the picture's edge", () => {
    const left = fitTransform({ fit: "cover", position: [0, 0.5], zoom: 1 }, 390, 844, 1600, 900);
    const pw = (1600 / 900) / (390 / 844);
    expect(left.sy).toBeCloseTo(1, 6);
    expect(left.ox).toBeCloseTo(pw / 2, 6);                 // the picture's left edge on the stage's left edge
    const mid = fitTransform({ fit: "cover", position: [0.5, 0.5], zoom: 1 }, 390, 844, 1600, 900);
    expect(mid.ox).toBeCloseTo(0.5, 6);
  });
});
