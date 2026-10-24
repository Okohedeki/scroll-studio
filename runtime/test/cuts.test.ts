/**
 * The cut runtime (lib/cuts.ts): a gap of scroll between two pinned sections, and how far through the gap you are decides
 * what each pin looks like. jsdom has no layout, so the page's boxes are set by hand and read back from the styles written.
 */
import { beforeEach, describe, expect, it } from "vitest";
import { box, fresh, html, media, moveTo, screen, scrollTo } from "./helpers";

const GAP = 1000;   // px of scroll the cut plays over
const W = 1280, H = 800;

async function setup(cfg: Record<string, unknown> = {}, extra = "") {
  const c = { n: 1, a: 0, b: 1, type: "dissolve", length: 1, label: "cut", ...cfg };
  html(`<main>
    <div class="ss-cutw" data-cut-out="1"><div class="ss-cutpin ss-cutpin--out" id="pinA"><section id="a"><h2>Cold</h2></section></div></div>
    <div class="ss-cutw" data-cut-in="1" id="in"><div class="ss-cutgap" id="gap"></div><div class="ss-cutpin ss-cutpin--in" id="pinB"><section id="b"><h2>Warm</h2></section></div></div>
    ${extra}
  </main><script id="ss-cuts" type="application/json">${JSON.stringify([c])}</script>`);
  const $ = (id: string) => document.getElementById(id)!;
  screen({ w: W, h: H, y: 0 });
  box($("gap"), 0, GAP);
  box($("in"), 0, GAP + H);
  box($("pinA"), 0, H);
  box($("pinB"), 0, H);
  const { makeCuts } = await fresh(() => import("../src/lib/cuts"));
  const api = makeCuts()!;
  /** scroll to `pos` (0-1) of the gap and run a frame */
  const goto = (pos: number) => { moveTo($("in"), -pos * GAP); api.update(); };
  const off = (id: string) => $(id).classList.contains("ss-cut-off");
  return { api, goto, $, off, pinA: $("pinA"), pinB: $("pinB") };
}

beforeEach(() => screen({ w: W, h: H, y: 0 }));

describe("makeCuts", () => {
  it("does nothing on a page without cuts", async () => {
    html("<main></main>");
    const { makeCuts } = await fresh(() => import("../src/lib/cuts"));
    expect(makeCuts()).toBeNull();
  });

  it("does nothing with reduced motion: the sections just follow each other", async () => {
    media.reduced = true;
    html(`<script id="ss-cuts" type="application/json">[{"n":1,"type":"dissolve"}]</script>`);
    const { makeCuts } = await fresh(() => import("../src/lib/cuts"));
    expect(makeCuts()).toBeNull();
  });

  it("skips a cut whose wrappers are not on the page, and does nothing if none is left", async () => {
    html(`<script id="ss-cuts" type="application/json">[{"n":7,"type":"dissolve"}]</script>`);
    const { makeCuts } = await fresh(() => import("../src/lib/cuts"));
    expect(makeCuts()).toBeNull();
    expect(document.documentElement.classList.contains("ss-cuts-on")).toBe(false);
  });

  it("switches the page to cut mode and publishes where each cut sits", async () => {
    const { api } = await setup({ label: "dissolve into the warm room" });
    expect(document.documentElement.classList.contains("ss-cuts-on")).toBe(true);
    expect(api.cuts).toHaveLength(1);
    const pub = (window as any).__ssCuts;
    expect(pub.positions()).toEqual([{ n: 1, type: "dissolve", label: "dissolve into the warm room", from: 0, to: GAP, length: GAP }]);
  });
});

describe("how far through the gap", () => {
  it("before the gap only the section above shows; after it only the section below", async () => {
    const { goto, off } = await setup();
    goto(-0.5);   // the gap has not been reached
    expect(off("pinB")).toBe(true);
    expect(off("pinA")).toBe(false);
    goto(1.2);
    expect(off("pinA")).toBe(true);
    expect(off("pinB")).toBe(false);
  });

  it("holds each end still: the cut plays only between `hold` and 1 - `hold` (15% by default)", async () => {
    const { goto, pinB, api } = await setup();
    goto(0.1);
    expect(api.cuts[0].k).toBe(0);
    expect(parseFloat(pinB.style.opacity)).toBe(0);     // nothing of the next picture yet
    goto(0.5);
    expect(api.cuts[0].k).toBeCloseTo(0.5, 12);
    goto(0.9);
    expect(api.cuts[0].k).toBe(1);
  });

  it("`hold` in the spec moves those ends", async () => {
    const { goto, api } = await setup({ hold: 0.3 });
    goto(0.4);
    expect(api.cuts[0].k).toBeCloseTo(0.25, 12);
  });

  it("a gap of no height never divides by zero", async () => {
    const { api, $ } = await setup();
    box($("gap"), 0, 0);
    expect(() => api.update()).not.toThrow();
  });
});

describe("the effects", () => {
  it("dissolve: the picture below fades in by an eased amount, both on screen in between", async () => {
    const { goto, pinA, pinB, off } = await setup({ type: "dissolve" });
    goto(0.5);
    expect(parseFloat(pinB.style.opacity)).toBeCloseTo(0.500, 3);
    expect(off("pinA")).toBe(false);
    expect(off("pinB")).toBe(false);
    goto(0.325);       // k = 0.25: smoothstep(.25) = .15625
    expect(parseFloat(pinB.style.opacity)).toBeCloseTo(0.156, 3);
    // only the picture that is mostly on top takes clicks
    expect(pinA.style.pointerEvents).toBe("");
    expect(pinB.style.pointerEvents).toBe("none");
    goto(0.675);
    expect(parseFloat(pinB.style.opacity)).toBeCloseTo(0.844, 3);
    expect(pinA.style.pointerEvents).toBe("none");
    expect(pinB.style.pointerEvents).toBe("");
  });

  it("cut: the picture changes instantly at `at`, with a slow push on each side of it", async () => {
    const { goto, pinA, pinB, off } = await setup({ type: "cut", at: 0.5 });
    goto(0.3);   // k = 0.2143
    expect(off("pinB")).toBe(true);
    expect(off("pinA")).toBe(false);
    expect(parseFloat(pinA.style.transform.replace("scale(", ""))).toBeGreaterThan(1);
    goto(0.7);
    expect(off("pinA")).toBe(true);
    expect(off("pinB")).toBe(false);
    // the push on the next picture settles toward 1 as the cut ends
    const s = parseFloat(pinB.style.transform.replace("scale(", ""));
    expect(s).toBeGreaterThan(1);
    goto(0.85);
    expect(parseFloat(pinB.style.transform.replace("scale(", ""))).toBeLessThan(s);
  });

  it("cut: `at` moves the instant of the change", async () => {
    const { goto, off } = await setup({ type: "cut", at: 0.8 });
    goto(0.7);   // k = 0.786 < 0.8
    expect(off("pinB")).toBe(true);
    goto(0.75);  // k = 0.857 > 0.8
    expect(off("pinB")).toBe(false);
  });

  it("wipe: the picture below is revealed through a gradient edge along the direction; the one above leaves when it is done", async () => {
    const { goto, pinA, pinB, off } = await setup({ type: "wipe", direction: "right", soft: 0 });
    goto(0.5);
    expect((pinB.style as any).maskImage).toBe("linear-gradient(90deg, #000 50.00%, transparent 50.00%)");
    expect((pinB.style as any).maskSize).toBe(`${W}px ${H}px`);
    expect(off("pinA")).toBe(false);
    goto(0.9);
    expect(off("pinA")).toBe(true);
    expect(pinA).toBeTruthy();
  });

  it("wipe: a soft edge is as wide as `soft`, and an `angle` overrides the direction", async () => {
    const { goto, pinB } = await setup({ type: "wipe", direction: "left", soft: 0.2, angle: 45 });
    goto(0.5);
    // e = 0.5, p = 0.5 * 1.2 = 0.6: the edge runs from 40% to 60%, at the angle + 90
    expect((pinB.style as any).maskImage).toBe("linear-gradient(135deg, #000 40.00%, transparent 60.00%)");
  });

  it("iris: a circle opens from the origin on the picture below, big enough to cover the corner furthest away at the end", async () => {
    const { goto, pinB } = await setup({ type: "iris", origin: [0.5, 0.5], soft: 0 });
    goto(0.5);
    const R = Math.hypot(W / 2, H / 2);
    expect((pinB.style as any).clipPath).toBe(`circle(${(R * 0.5).toFixed(2)}px at ${(W / 2).toFixed(2)}px ${(H / 2).toFixed(2)}px)`);
    goto(0.85);
    expect((pinB.style as any).clipPath).toBe(`circle(${R.toFixed(2)}px at ${(W / 2).toFixed(2)}px ${(H / 2).toFixed(2)}px)`);
  });

  it("iris: an origin in a corner needs the whole diagonal", async () => {
    const { goto, pinB } = await setup({ type: "iris", origin: [0, 0], soft: 0 });
    goto(0.85);
    expect((pinB.style as any).clipPath).toBe(`circle(${Math.hypot(W, H).toFixed(2)}px at 0.00px 0.00px)`);
  });

  it("iris, closing: the picture above closes on the point with the next one waiting behind it", async () => {
    const { goto, pinA, pinB, off } = await setup({ type: "iris", origin: [0.5, 0.5], closing: true });
    goto(0.5);
    expect((pinA.style as any).clipPath).toMatch(/^circle\(/);
    expect(pinA.style.zIndex).toBe("2");
    expect(pinB.style.zIndex).toBe("1");
    expect(off("pinB")).toBe(false);
    goto(0.9);
    expect(off("pinA")).toBe(true);
  });

  it("iris, soft: the edge is a radial gradient mask instead of a clip", async () => {
    const { goto, pinB } = await setup({ type: "iris", origin: [0.5, 0.5], soft: 0.5 });
    goto(0.5);
    expect((pinB.style as any).maskImage).toMatch(/^radial-gradient\(circle at 640\.00px 400\.00px, #000 /);
    expect((pinB.style as any).clipPath).toBe("");
  });

  it("whip: both pictures slide along the direction, the one below arriving as the one above leaves", async () => {
    const { goto, pinA, pinB, off } = await setup({ type: "whip", direction: "left", blur: 1 });
    goto(0.5);
    // the middle of the cut: quart(0.5) = 0.5, so the picture above has moved half a screen; blur peaks at 64px (5% of the width)
    expect(pinA.style.transform).toBe(`translate(${(-W / 2).toFixed(2)}px, 0.00px)`);
    expect(pinB.style.transform).toBe("translate(576.00px, 0.00px)");   // arrives from the far side, overlapping by twice the blur
    expect(pinA.style.filter).toBe("url(#ss-cut-blur-2)");
    expect(pinB.style.filter).toBe("url(#ss-cut-blur-3)");
    expect(off("pinA")).toBe(false);
    goto(0.9);
    expect(off("pinA")).toBe(true);
    expect(off("pinB")).toBe(false);
  });

  it("whip: a vertical direction slides in y and blurs by the height", async () => {
    const { goto, pinA } = await setup({ type: "whip", direction: "down" });
    goto(0.5);
    expect(pinA.style.transform).toBe(`translate(0.00px, ${(H / 2).toFixed(2)}px)`);
  });

  it("an unknown type falls back to a plain cut", async () => {
    const { goto, off } = await setup({ type: "mystery" });
    goto(0.2);
    expect(off("pinB")).toBe(true);
    goto(0.8);
    expect(off("pinA")).toBe(true);
  });

  it("leaving the gap clears everything the cut wrote", async () => {
    const { goto, pinA, pinB } = await setup({ type: "wipe", direction: "left" });
    goto(0.5);
    expect((pinB.style as any).maskImage).not.toBe("");
    goto(1.5);
    expect((pinB.style as any).maskImage).toBe("");
    expect(pinA.style.pointerEvents).toBe("");
    expect(pinB.style.opacity).toBe("");
  });
});

describe("match and carry", () => {
  it("match: with a shape on each side, both pictures zoom toward the shape and swap on it", async () => {
    const { goto, $, pinA, pinB, off } = await setup({ type: "match", at: 0.5, anchors: { a: { sel: "#sa" }, b: { sel: "#sb" } } });
    $("a").insertAdjacentHTML("beforeend", `<i id="sa"></i>`);
    $("b").insertAdjacentHTML("beforeend", `<i id="sb"></i>`);
    box($("sa"), 400, 200, { left: 700, width: 200 });
    box($("sb"), 300, 300, { left: 500, width: 300 });
    goto(0.2);          // k small: measured on entering, A is pushing in
    const early = parseFloat(pinA.style.transform.replace("scale(", ""));
    goto(0.4);          // k = 0.357
    const later = parseFloat(pinA.style.transform.replace("scale(", ""));
    expect(early).toBeGreaterThanOrEqual(1);
    expect(later).toBeGreaterThan(early);
    expect(pinA.style.transformOrigin).toMatch(/px .*px/);
    goto(0.5);
    expect(off("pinB")).toBe(false);
    goto(0.7);          // k = 0.714: B is settling out of its zoom
    expect(off("pinA")).toBe(true);
    expect(parseFloat(pinB.style.transform.replace("scale(", ""))).toBeGreaterThan(1);
    goto(0.84);
    expect(parseFloat(pinB.style.transform.replace("scale(", ""))).toBeLessThan(1.5);
  });

  it("match: without shapes on screen the cut dissolves instead", async () => {
    const { goto, pinB } = await setup({ type: "match", anchors: { a: { sel: "#nothing" }, b: { sel: "#nothing" } } });
    goto(0.5);
    expect(parseFloat(pinB.style.opacity)).toBeCloseTo(0.500, 3);
  });

  it("carry: an element is baked into a fixed layer and flies from its place above to its place below", async () => {
    const { goto, $ } = await setup({ type: "carry", carry: { from: "h2", to: "h2", via: "dissolve" } });
    box($("a").querySelector("h2")!, 100, 80, { left: 100, width: 400 });
    box($("b").querySelector("h2")!, 500, 40, { left: 700, width: 200 });
    goto(0.5);
    const layer = document.querySelector(".ss-cutghost")!;
    expect(layer.children).toHaveLength(2);
    expect($("a").querySelector("h2")!.classList.contains("ss-cut-carried")).toBe(true);
    const [ghostA, ghostB] = [...layer.children] as HTMLElement[];
    expect(parseFloat(ghostA.style.opacity)).toBeGreaterThan(0);
    expect(ghostA.style.transform).toMatch(/^translate\(.*\) scale\(/);
    expect(ghostB.style.opacity).not.toBe("");
    goto(1.5);   // after the cut: the ghosts are gone and the real element is no longer hidden
    expect(layer.children).toHaveLength(0);
    expect($("a").querySelector("h2")!.classList.contains("ss-cut-carried")).toBe(false);
  });
});

describe("what scroll-driven players ask the cuts", () => {
  it("holding: 1 for the section above and 0 for the one below, only while a cut is moving them", async () => {
    const { api, goto, $ } = await setup({ type: "dissolve" });
    goto(0.5);
    expect(api.holding($("a"))).toBe(1);
    expect(api.holding($("b"))).toBe(0);
    expect(api.holding(document.body)).toBeNull();
    goto(0.1);          // the held beat before the cut: sections are where scrolling put them
    expect(api.holding($("a"))).toBeNull();
    goto(0.9);
    expect(api.holding($("b"))).toBeNull();
    goto(1.5);
    expect(api.holding($("b"))).toBeNull();
  });

  it("land: the scroll position at which the section below's own first screen is on show", async () => {
    const { api, goto, $ } = await setup();
    scrollTo(300);
    goto(0.2);          // the wrapper's top is now -200 in the viewport, 100 in the document
    expect(api.land($("b"))).toBe(-200 + 300 + GAP);
    expect(api.land(document.body)).toBeNull();
    expect(api.land($("a"))).toBeNull();
  });

  it("docTop: where an element's own top sits with no cut holding it", async () => {
    const { api, goto, $ } = await setup();
    scrollTo(0);
    goto(0.2);
    // the wrapper of the section below has its gap above it
    expect(api.docTop($("b"))).toBe(-200 + GAP);
    expect(api.docTop(document.body)).toBeNull();
    // the section above is in a wrapper with no gap of its own
    box($("pinA").parentElement!, -50, 800);
    expect(api.docTop($("a"))).toBe(-50);
  });
});
