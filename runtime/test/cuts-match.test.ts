/** Match cut geometry: where each side's shape sits, and the zoom plan that makes the two shapes meet. */
import { describe, expect, it } from "vitest";
import { anchorBox, planMatch, type Box } from "../src/lib/cuts-match";
import { box as place, html } from "./helpers";

const W = 1440, H = 900, view: Box = { x: 0, y: 0, w: W, h: H };
const b = (x: number, y: number, w: number, h: number): Box => ({ x, y, w, h });

/** Where a shape's centre lands when its picture is zoomed by s about f. */
const landing = (s: number, f: [number, number], c: [number, number]) => [f[0] + s * (c[0] - f[0]), f[1] + s * (c[1] - f[1])];
const centre = (x: Box): [number, number] => [x.x + x.w / 2, x.y + x.h / 2];

describe("planMatch", () => {
  const cases: [string, Box, Box, number][] = [
    ["shapes that already agree", b(500, 300, 400, 400), b(500, 300, 400, 400), 3],
    ["small to big", b(700, 400, 130, 130), b(500, 200, 330, 330), 3],
    ["big to small", b(400, 150, 500, 500), b(1000, 500, 170, 170), 3],
    ["same size, a way apart", b(150, 300, 260, 260), b(650, 350, 260, 260), 3],
  ];

  it.each(cases)("%s: both shapes land on one point at one size, and only ever zoom in", (_name, A, B, zoom) => {
    const p = planMatch(A, B, view, view, zoom)!;
    expect(p).not.toBeNull();
    const a = landing(p.sA, p.fA, centre(A)), c = landing(p.sB, p.fB, centre(B));
    expect(a[0]).toBeCloseTo(c[0], 6);
    expect(a[1]).toBeCloseTo(c[1], 6);
    expect(Math.sqrt(A.w * A.h) * p.sA).toBeCloseTo(Math.sqrt(B.w * B.h) * p.sB, 6);
    expect(p.sA).toBeGreaterThanOrEqual(1);
    expect(p.sB).toBeGreaterThanOrEqual(1);
    expect(p.mismatch).toBeCloseTo(1, 6);
  });

  it("keeps each zoom's pivot inside its picture, so the picture still covers what it covered", () => {
    for (const [, A, B, zoom] of cases) {
      const p = planMatch(A, B, view, view, zoom)!;
      for (const f of [p.fA, p.fB]) {
        expect(f[0]).toBeGreaterThanOrEqual(-1e-6); expect(f[0]).toBeLessThanOrEqual(W + 1e-6);
        expect(f[1]).toBeGreaterThanOrEqual(-1e-6); expect(f[1]).toBeLessThanOrEqual(H + 1e-6);
      }
    }
  });

  it("gives the bigger zoom to the side with the smaller shape", () => {
    const small = b(700, 400, 100, 100), big = b(500, 250, 300, 300);
    const a = planMatch(small, big, view, view, 3)!, c = planMatch(big, small, view, view, 3)!;
    expect(a.sA).toBeGreaterThan(a.sB);
    expect(c.sB).toBeGreaterThan(c.sA);
  });

  it("caps a huge size ratio at the zoom (times the extra push) and still returns a plan", () => {
    const p = planMatch(b(700, 400, 40, 40), b(500, 200, 400, 400), view, view, 3)!;
    expect(p).not.toBeNull();
    expect(p.sA).toBeLessThanOrEqual(3 * 2.4 + 1e-6);
    expect(p.mismatch).toBeLessThan(1);   // the shapes only nearly coincide
  });

  it("returns null for shapes too far apart to meet without showing a picture's edge (the cut dissolves instead)", () => {
    expect(planMatch(b(5, 5, 100, 100), b(1330, 790, 100, 100), view, view, 1)).toBeNull();
  });

  it("a picture smaller than the screen limits where its pivot may be", () => {
    const bounds = b(400, 200, 640, 400);
    const A = b(600, 300, 200, 200), B = b(620, 320, 200, 200);
    const p = planMatch(A, B, bounds, bounds, 3)!;
    expect(p).not.toBeNull();
    for (const f of [p.fA, p.fB]) {
      expect(f[0]).toBeGreaterThanOrEqual(bounds.x - 1e-6); expect(f[0]).toBeLessThanOrEqual(bounds.x + bounds.w + 1e-6);
      expect(f[1]).toBeGreaterThanOrEqual(bounds.y - 1e-6); expect(f[1]).toBeLessThanOrEqual(bounds.y + bounds.h + 1e-6);
    }
  });
});

describe("anchorBox", () => {
  function pin(frameHtml: string, frameBox: [number, number, number, number]) {
    html(`<div id="pin">${frameHtml}</div>`);
    const el = document.getElementById("pin")!;
    const fr = el.querySelector<HTMLElement>("[data-f]")!;
    place(fr, frameBox[1], frameBox[3], { left: frameBox[0], width: frameBox[2] });
    return el;
  }

  it("is null without an anchor, without a box or sel, or when the element is missing", () => {
    const el = pin(`<div class="ss-visual" data-f></div>`, [0, 0, 1000, 500]);
    expect(anchorBox(el, undefined)).toBeNull();
    expect(anchorBox(el, {})).toBeNull();
    expect(anchorBox(el, { sel: ".nope" })).toBeNull();
    expect(anchorBox(el, { box: [0, 0, 1, 1], of: ".nope" })).toBeNull();
  });

  it("measures a page element by selector, and ignores one with no size", () => {
    html(`<div id="pin"><h2 class="shape"></h2><p class="gone"></p></div>`);
    const el = document.getElementById("pin")!;
    place(el.querySelector(".shape")!, 40, 60, { left: 10, width: 300 });
    place(el.querySelector(".gone")!, 0, 0, { width: 0 });
    expect(anchorBox(el, { sel: ".shape" })).toEqual({ box: { x: 10, y: 40, w: 300, h: 60 }, frame: null });
    expect(anchorBox(el, { sel: ".gone" })).toBeNull();
  });

  it("maps a picture box (0-1) onto a picture that covers its frame: the wider side overflows and is centred", () => {
    // frame 1000x500, picture aspect 1 (square) covering it: 1000x1000, centred, so 250px of it is cropped above and below
    const el = pin(`<div class="ss-visual" data-f></div>`, [0, 0, 1000, 500]);
    const r = anchorBox(el, { box: [0.25, 0.25, 0.75, 0.75], aspect: 1 })!;
    expect(r.box).toEqual({ x: 250, y: 0, w: 500, h: 500 });
    expect(r.frame).toBe(el.querySelector(".ss-visual"));
  });

  it("a picture that is contained shows whole inside its frame instead", () => {
    const el = pin(`<div class="ss-visual" data-f></div>`, [100, 50, 1000, 500]);
    const r = anchorBox(el, { box: [0, 0, 1, 1], aspect: 1, fit: "contain" })!;
    expect(r.box).toEqual({ x: 350, y: 50, w: 500, h: 500 });
  });

  it("scales about the picture's centre when the section's player is doing a slow dolly", () => {
    const el = pin(`<div class="ss-visual" data-f></div>`, [0, 0, 1000, 1000]);
    const r = anchorBox(el, { box: [0.5, 0.5, 1, 1], aspect: 1, scale: 2 })!;
    expect(r.box).toEqual({ x: 500, y: 500, w: 1000, h: 1000 });
  });

  it("finds the frame in order: the section's visual, a hero's media, a backdrop, then the section itself", () => {
    html(`<div id="pin"><section data-f class="x"></section></div>`);
    const el = document.getElementById("pin")!;
    place(el.querySelector("section")!, 0, 100, { width: 200 });
    expect(anchorBox(el, { box: [0, 0, 1, 1], aspect: 2 })!.frame).toBe(el.querySelector("section"));
    html(`<div id="pin"><div class="ss-backdrop" data-f></div><section></section></div>`);
    const el2 = document.getElementById("pin")!;
    place(el2.querySelector("[data-f]")!, 0, 100, { width: 200 });
    expect(anchorBox(el2, { box: [0, 0, 1, 1], aspect: 2 })!.frame).toBe(el2.querySelector(".ss-backdrop"));
  });

  it("`of` names the frame explicitly", () => {
    html(`<div id="pin"><div class="ss-visual"></div><figure class="mine" data-f></figure></div>`);
    const el = document.getElementById("pin")!;
    place(el.querySelector(".mine")!, 0, 100, { width: 100 });
    expect(anchorBox(el, { box: [0, 0, 1, 1], aspect: 1, of: ".mine" })!.frame).toBe(el.querySelector(".mine"));
  });
});
