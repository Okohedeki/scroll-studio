/** Scroll motion for content blocks and the stack layout: everything is a pure function of the scroll position. */
import { beforeEach, describe, expect, it } from "vitest";
import { box, fresh, html, media, moveTo, screen, scrollTo } from "./helpers";

const H = 800;
const prop = (el: Element, name: string) => (el as HTMLElement).style.getPropertyValue(name);

async function blocks(markup: string, held?: (el: Element) => boolean) {
  html(markup);
  screen({ w: 1280, h: H, y: 0 });
  const { makeBlocks } = await fresh(() => import("../src/lib/blocks"));
  return makeBlocks(held);
}

beforeEach(() => screen({ w: 1280, h: H, y: 0 }));

describe("makeBlocks", () => {
  it("does no work on a page without blocks", async () => {
    const update = await blocks("<main><p>plain</p></main>");
    expect(update()).toBeUndefined();
  });

  describe("stack: each panel is sticky and the one being covered shrinks and darkens", () => {
    async function stack() {
      const update = await blocks(`<div class="ss-panel" id="p0"></div><div class="ss-panel" id="p1"></div><div class="ss-panel" id="p2"></div>`);
      const p = [0, 1, 2].map((i) => document.getElementById("p" + i)!);
      return { update, p };
    }

    it("--cover is how far the next panel has come up: 0 while it is a screen below, 1 once it has arrived", async () => {
      const { update, p } = await stack();
      box(p[0], 0, H); box(p[1], H, H); box(p[2], 2 * H, H);
      scrollTo(1); update();
      expect(prop(p[0], "--cover")).toBe("0.000");
      moveTo(p[1], H / 2); scrollTo(2); update();
      expect(prop(p[0], "--cover")).toBe("0.500");
      moveTo(p[1], 0); scrollTo(3); update();
      expect(prop(p[0], "--cover")).toBe("1.000");
      moveTo(p[1], -50); scrollTo(4); update();       // past the top: still just covered
      expect(prop(p[0], "--cover")).toBe("1.000");
    });

    it("the last panel is never covered", async () => {
      const { update, p } = await stack();
      box(p[0], 0, H); box(p[1], 0, H); box(p[2], 0, H);
      scrollTo(1); update();
      expect(prop(p[2], "--cover")).toBe("0.000");
    });

    it("a panel taller than the screen sticks by its bottom edge, so its own content scrolls first", async () => {
      const { update, p } = await stack();
      box(p[0], 0, 2 * H); box(p[1], 2 * H, H); box(p[2], 3 * H, H);
      scrollTo(1); update();
      expect(p[0].style.top).toBe(`${-H}px`);
      expect(p[1].style.top).toBe("0px");        // a panel that fits sticks to the top
    });

    it("measures again when the screen resizes, and only then", async () => {
      const { update, p } = await stack();
      box(p[0], 0, 1000); box(p[1], H, H); box(p[2], 2 * H, H);
      scrollTo(1); update();
      expect(p[0].style.top).toBe("-200px");
      box(p[0], 0, 1200);
      scrollTo(2); update();                      // scrolled, not resized: the old measure stands
      expect(p[0].style.top).toBe("-200px");
      screen({ w: 1280, h: 600, y: 2 }); update();
      expect(p[0].style.top).toBe("-600px");
    });
  });

  describe("hero: the photo zooms and the copy lifts away as the hero is left", () => {
    it("--hero-p follows how far the hero has scrolled off the top", async () => {
      const update = await blocks(`<section class="ss-hero" id="h"></section>`);
      const h = document.getElementById("h")!;
      box(h, 0, 700); scrollTo(1); update();
      expect(prop(h, "--hero-p")).toBe("0.000");
      moveTo(h, -350); scrollTo(2); update();
      expect(prop(h, "--hero-p")).toBe("0.500");
      moveTo(h, -900); scrollTo(3); update();
      expect(prop(h, "--hero-p")).toBe("1.000");
    });

    it("a hero in the stack layout follows its own panel being covered", async () => {
      const update = await blocks(`<div class="ss-panel" id="p0"><section class="ss-hero" id="h"></section></div><div class="ss-panel" id="p1"></div>`);
      const [p0, p1, h] = ["p0", "p1", "h"].map((id) => document.getElementById(id)!);
      box(p0, 0, H); box(p1, H * 0.25, H); box(h, 0, H);
      scrollTo(1); update();
      expect(prop(h, "--hero-p")).toBe("0.750");
    });

    it("is left alone while a cut is playing on it", async () => {
      let held = true;
      const update = await blocks(`<section class="ss-hero" id="h"></section>`, () => held);
      const h = document.getElementById("h")!;
      box(h, -350, 700); scrollTo(1); update();
      expect(prop(h, "--hero-p")).toBe("");
      held = false; scrollTo(2); update();
      expect(prop(h, "--hero-p")).toBe("0.500");
    });
  });

  describe("float: images drift against the scroll", () => {
    it("--float runs from -1 as the element enters at the bottom to +1 as it leaves at the top", async () => {
      const update = await blocks(`<div data-float id="f"></div>`);
      const f = document.getElementById("f")!;
      box(f, H, 400); scrollTo(1); update();
      expect(prop(f, "--float")).toBe("-1.000");
      moveTo(f, (H - 400) / 2); scrollTo(2); update();
      expect(prop(f, "--float")).toBe("0.000");
      moveTo(f, -400); scrollTo(3); update();
      expect(prop(f, "--float")).toBe("1.000");
    });
  });

  describe("strip: the row of photos slides sideways", () => {
    it("--strip is the row's overflow times the element's trip across the screen", async () => {
      const update = await blocks(`<div data-strip id="s"></div>`);
      const s = document.getElementById("s")!;
      box(s, (H - 200) / 2, 200);
      Object.defineProperty(s, "scrollWidth", { configurable: true, value: 2280 });
      scrollTo(1); update();
      expect(prop(s, "--strip")).toBe("500.0");          // halfway: half of the 1000px the row overflows by
    });

    it("a row that fits does not move", async () => {
      const update = await blocks(`<div data-strip id="s"></div>`);
      const s = document.getElementById("s")!;
      box(s, 100, 200);
      Object.defineProperty(s, "scrollWidth", { configurable: true, value: 900 });
      scrollTo(1); update();
      expect(prop(s, "--strip")).toBe("0.0");
    });
  });

  describe("orbit: services sit on two rings that turn in opposite directions", () => {
    const orbit = (n: number) => `<div data-orbit id="o">${Array.from({ length: n }, (_, i) => `<span class="ss-orbit__item" id="i${i}"></span>`).join("")}</div>`;

    it("too narrow for two legible rings, it keeps the static layout and clears any placement", async () => {
      const update = await blocks(orbit(4));
      const o = document.getElementById("o")!;
      box(o, 100, 300, { width: 400 });
      document.getElementById("i0")!.style.transform = "translate(1px, 1px)";
      scrollTo(1); update();
      expect(o.classList.contains("ss-orbit--live")).toBe(false);
      expect(document.getElementById("i0")!.style.transform).toBe("");
    });

    it("on a wide stage it places every item on its ring and turns them with the scroll", async () => {
      const update = await blocks(orbit(4));
      const o = document.getElementById("o")!;
      const items = [0, 1, 2, 3].map((i) => document.getElementById("i" + i)!);
      box(o, (H - 600) / 2, 600, { width: 600 });
      items.forEach((it) => box(it, 0, 100, { width: 100 }));
      scrollTo(1); update();
      expect(o.classList.contains("ss-orbit--live")).toBe(true);
      // outer ring fits the stage: 600 / 2 - 100 / 2 - 4 = 246; the inner ring is one circle and a gap inside it
      expect(prop(o, "--r-out")).toBe("246.0px");
      expect(prop(o, "--r-in")).toBe("132.0px");
      // halfway through its trip the first item of the inner ring sits at the radius of that ring
      const [x0, y0] = items[0].style.transform.match(/-?[\d.]+/g)!.map(Number);
      expect(Math.hypot(x0, y0)).toBeCloseTo(132, 0);
      const first = items[0].style.transform;
      moveTo(o, -600); scrollTo(2); update();
      expect(items[0].style.transform).not.toBe(first);
    });
  });

  it("does not recompute when neither the scroll position nor the screen has changed", async () => {
    const update = await blocks(`<div data-float id="f"></div>`);
    const f = document.getElementById("f")!;
    box(f, H, 400); scrollTo(1); update();
    expect(prop(f, "--float")).toBe("-1.000");
    moveTo(f, 0);                  // the layout moved, the scroll did not (a cut or an animation moved it)
    update();
    expect(prop(f, "--float")).toBe("-1.000");
    scrollTo(2); update();
    expect(prop(f, "--float")).not.toBe("-1.000");
  });

  it("reduced motion: every element rests mid-way, nothing is covered", async () => {
    media.reduced = true;
    const update = await blocks(`<div class="ss-panel" id="p0"><div data-float id="f"></div></div><div class="ss-panel" id="p1"></div><section class="ss-hero" id="h"></section>`);
    const [p0, p1, f, h] = ["p0", "p1", "f", "h"].map((id) => document.getElementById(id)!);
    box(p0, 0, H); box(p1, 100, H); box(f, 50, 100); box(h, -300, 700);
    scrollTo(1); update();
    expect(prop(p0, "--cover")).toBe("0.000");
    expect(prop(f, "--float")).toBe("0.000");
    expect(prop(h, "--hero-p")).toBe("0.000");
  });
});
