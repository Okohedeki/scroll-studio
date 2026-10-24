/** What every style experience is built from: the frame loop and scroll helpers (_kit), belts of blocks (_belt), the theme's art frames (_art). */
import { afterEach, describe, expect, it, vi } from "vitest";
import { atPage, box, frames, html, moveTo, screen, scrollToY } from "./helpers";

const kit = (o: { reduced?: boolean } = {}) => atPage(() => import("../src/styles/_kit"), o);

afterEach(() => vi.unstubAllGlobals());

describe("_kit", () => {
  it("$ and $$ select within a root, and $$ returns a real array", async () => {
    const { $, $$ } = await kit();
    html(`<div id="a"><p class="x">1</p><p class="x">2</p></div><p class="x">3</p>`);
    expect($(".x")!.textContent).toBe("1");
    expect($$(".x")).toHaveLength(3);
    expect($$(".x", document.getElementById("a")!).map((e) => e.textContent)).toEqual(["1", "2"]);
    expect($(".nope")).toBeNull();
  });

  describe("onFrame", () => {
    it("runs every function once a frame with the scroll position, an eased velocity, the time step and the screen height", async () => {
      screen({ h: 700, y: 0 });
      const f = frames();
      const { onFrame } = await kit();
      const seen: any[] = [];
      onFrame((s) => seen.push({ ...s }));
      scrollToY(100);
      f.step(16);
      expect(seen[0]).toMatchObject({ y: 100, vh: 700 });
      expect(seen[0].v).toBeCloseTo(20, 12);          // 20% of the 100px moved
      f.step(16);                                     // no more scrolling: the velocity decays by 20% of itself
      expect(seen[1].v).toBeCloseTo(16, 12);
      expect(seen[1].dt).toBeCloseTo(0.016, 12);
      f.step(16);
      expect(seen[2].v).toBeCloseTo(12.8, 12);
      expect(seen[2].t).toBeGreaterThan(seen[1].t);
    });

    it("shares one frame loop however many functions there are", async () => {
      const f = frames();
      const { onFrame } = await kit();
      const a = vi.fn(), b = vi.fn();
      onFrame(a); onFrame(b);
      expect(f.pending).toBe(1);
      f.step();
      expect(a).toHaveBeenCalledTimes(1);
      expect(b).toHaveBeenCalledTimes(1);
    });

    it("caps the time step at 50 ms so a stalled tab does not jump", async () => {
      const f = frames();
      const { onFrame } = await kit();
      const seen: number[] = [];
      onFrame((s) => seen.push(s.dt));
      f.step(1000);
      expect(seen[0]).toBe(0.05);
    });

    it("reports no velocity with reduced motion", async () => {
      screen({ y: 0 });
      const f = frames();
      const { onFrame } = await kit({ reduced: true });
      const seen: number[] = [];
      onFrame((s) => seen.push(s.v));
      scrollToY(500);
      f.step();
      expect(seen).toEqual([0]);
    });
  });

  it("through: 0 when an element's top reaches the bottom of the screen, 1 when its bottom leaves the top", async () => {
    const { through } = await kit();
    screen({ h: 800 });
    html(`<div id="e"></div>`);
    const e = document.getElementById("e")!;
    box(e, 800, 200); expect(through(e)).toBe(0);
    moveTo(e, 400); expect(through(e)).toBeCloseTo(0.4, 12);
    moveTo(e, -200); expect(through(e)).toBe(1);
    moveTo(e, -900); expect(through(e)).toBe(1);
    moveTo(e, 900); expect(through(e)).toBe(0);
  });

  it("pinned: 0 when a track's top hits the top of the screen, 1 when its bottom hits the bottom", async () => {
    const { pinned } = await kit();
    screen({ h: 800 });
    html(`<div id="t"></div>`);
    const t = document.getElementById("t")!;
    box(t, 100, 2800); expect(pinned(t)).toBe(0);
    moveTo(t, 0); expect(pinned(t)).toBe(0);
    moveTo(t, -1000); expect(pinned(t)).toBe(0.5);
    moveTo(t, -2000); expect(pinned(t)).toBe(1);
    box(t, -10, 500); expect(pinned(t)).toBe(1);        // a track no taller than the screen never divides by zero
  });

  describe("pinSequence", () => {
    it("moves a section's content onto a sticky stage inside a tall track, a screen plus the steps' worth", async () => {
      const f = frames();
      const { pinSequence } = await kit();
      html(`<section id="s"><h2>Title</h2><p>Body</p></section>`);
      const s = document.getElementById("s")!;
      const stage = pinSequence(s, 4, () => {}, 0.5);
      expect(s.classList.contains("sx-pinned")).toBe(true);
      const track = s.querySelector<HTMLElement>(".sx-track")!;
      expect(track.style.height).toBe("300svh");           // 100 + 4 steps * 0.5 screens * 100
      expect(track.firstElementChild).toBe(stage);
      expect(stage.className).toBe("sx-stage");
      expect([...stage.children].map((c) => c.tagName)).toEqual(["H2", "P"]);
      expect(f.pending).toBe(1);
    });

    it("reports the fractional step and the progress as the track scrolls, from 0 to the number of steps", async () => {
      screen({ h: 800 });
      const f = frames();
      const { pinSequence } = await kit();
      html(`<section id="s"><p>x</p></section>`);
      const got: [number, number][] = [];
      pinSequence(document.getElementById("s")!, 3, (step, p) => got.push([step, p]));
      const track = document.querySelector<HTMLElement>(".sx-track")!;
      box(track, 0, 3000);
      f.step();
      moveTo(track, -1100); f.step();                       // 1100 of 2200: half way
      moveTo(track, -2200); f.step();
      expect(got).toEqual([[0, 0], [1.5, 0.5], [3, 1]]);
    });

    it("with reduced motion the sequence is already finished", async () => {
      const f = frames();
      const { pinSequence } = await kit({ reduced: true });
      html(`<section id="s"><p>x</p></section>`);
      const got: [number, number][] = [];
      pinSequence(document.getElementById("s")!, 2, (step, p) => got.push([step, p]));
      f.step();
      expect(got).toEqual([[2, 1]]);
    });
  });

  describe("chars", () => {
    it("wraps every character in its own span, in reading order, numbering them, and keeps inline markup", async () => {
      const { chars } = await kit();
      html(`<h1 id="h">Hi <em>you</em> all</h1>`);
      const h = document.getElementById("h")!;
      const spans = chars(h);
      expect(spans.map((s) => s.textContent).join("")).toBe("Hiyouall");
      expect(spans.map((s) => s.style.getPropertyValue("--i"))).toEqual(["0", "1", "2", "3", "4", "5", "6", "7"]);
      expect(spans.every((s) => s.className === "sx-ch")).toBe(true);
      expect(h.querySelectorAll("em .sx-word")).toHaveLength(1);       // markup survives, words stay together
      expect(h.querySelectorAll(".sx-word")).toHaveLength(3);
      expect(h.getAttribute("aria-label")).toBe("Hi you all");        // the page still says the words
      expect(h.textContent).toBe("Hi you all");
    });

    it("collapses runs of whitespace to a single space and takes a custom class", async () => {
      const { chars } = await kit();
      html(`<p id="p">a   b\n c</p>`);
      const p = document.getElementById("p")!;
      const spans = chars(p, "my-ch");
      expect(spans.every((s) => s.className === "my-ch")).toBe(true);
      expect(p.textContent).toBe("a b c");
    });
  });

  it("typeTo shows the first round(k * n) characters, whatever k is", async () => {
    const { typeTo } = await kit();
    const spans = Array.from({ length: 10 }, () => document.createElement("span"));
    const vis = () => spans.map((s) => s.style.visibility === "visible").filter(Boolean).length;
    typeTo(spans, 0); expect(vis()).toBe(0);
    typeTo(spans, 0.34); expect(vis()).toBe(3);
    typeTo(spans, 0.35); expect(vis()).toBe(4);
    typeTo(spans, 1); expect(vis()).toBe(10);
    typeTo(spans, 7); expect(vis()).toBe(10);
    typeTo(spans, -1); expect(vis()).toBe(0);
  });

  it("onSeen runs once, the first time the element is at least `threshold` on screen", async () => {
    const observers: { cb: (es: { isIntersecting: boolean }[]) => void; opts: IntersectionObserverInit; disconnected: boolean }[] = [];
    vi.stubGlobal("IntersectionObserver", class {
      disconnected = false;
      constructor(public cb: any, public opts: any) { observers.push(this as any); }
      observe() {} disconnect() { this.disconnected = true; }
    });
    const { onSeen } = await kit();
    const fn = vi.fn();
    onSeen(document.body, fn, 0.5);
    expect(observers[0].opts).toEqual({ threshold: 0.5 });
    observers[0].cb([{ isIntersecting: false }]);
    expect(fn).not.toHaveBeenCalled();
    observers[0].cb([{ isIntersecting: true }]);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(observers[0].disconnected).toBe(true);
  });

  it("injects the stylesheet the pinned-sequence classes need, once", async () => {
    await kit();
    expect([...document.head.querySelectorAll("style")].some((s) => s.textContent!.includes(".sx-stage"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------------------------------------------------- belts
describe("_belt", () => {
  const belts = () => atPage(() => import("../src/styles/_belt"));
  const page = `<main id="m"><section class="blk" id="a"></section><section class="blk" id="b"></section><section id="scene"></section><section class="blk" id="c"></section></main>`;
  const isBlock = (el: HTMLElement) => el.classList.contains("blk");

  it("groups consecutive blocks into one belt inside a sticky stage; anything else breaks the run", async () => {
    const B = await belts();
    html(page);
    const list = B.makeBelts(document.getElementById("m")!, isBlock);
    expect(list).toHaveLength(2);
    expect(list[0].blocks.map((b) => b.id)).toEqual(["a", "b"]);
    expect(list[1].blocks.map((b) => b.id)).toEqual(["c"]);
    expect([...document.getElementById("m")!.children].map((c) => c.className)).toEqual(["bt-root", "", "bt-root"]);
    expect(list[0].belt.parentElement).toBe(list[0].stage);
    expect(list[0].stage.parentElement).toBe(list[0].root);
    expect(list[0].belt.contains(document.getElementById("b"))).toBe(true);
    expect(document.getElementById("scene")!.parentElement!.id).toBe("m");     // a scene is never put on a belt
  });

  it("measure sizes each root to its belt (at least a screen) and records where it starts and how far it can travel", async () => {
    const B = await belts();
    html(page);
    screen({ h: 800, y: 50 });
    const list = B.makeBelts(document.getElementById("m")!, isBlock);
    box(list[0].belt, 0, 2000); box(list[0].root, 300, 2000);
    box(list[1].belt, 0, 500); box(list[1].root, 3000, 800);
    B.measure(list);
    expect(list[0]).toMatchObject({ h: 2000, vh: 800, range: 1200, top: 350 });
    expect(list[0].root.style.height).toBe("2000px");
    expect(list[1].range).toBe(0);
    expect(list[1].root.style.height).toBe("800px");      // never shorter than the screen
  });

  it("trueOffset is where normal flow would put the belt: the scroll inside the run, clamped to its travel", async () => {
    const B = await belts();
    html(page);
    screen({ h: 800 });
    const [b] = B.makeBelts(document.getElementById("m")!, isBlock);
    box(b.belt, 0, 2000); box(b.root, 1000, 2000);
    B.measure([b]);
    expect(B.trueOffset(b, 500)).toBe(0);
    expect(B.trueOffset(b, 1400)).toBe(400);
    expect(B.trueOffset(b, 9000)).toBe(1200);
  });

  it("setOffset translates the belt up by the offset, and does nothing when the offset has not changed", async () => {
    const B = await belts();
    html(page);
    const [b] = B.makeBelts(document.getElementById("m")!, isBlock);
    B.setOffset(b, 123.456);
    expect(b.belt.style.translate).toBe("0 -123.46px");
    expect(b.shown).toBe(123.456);
    b.belt.style.translate = "sentinel";
    B.setOffset(b, 123.456);
    expect(b.belt.style.translate).toBe("sentinel");
    B.setOffset(b, 5);
    expect(b.belt.style.translate).toBe("0 -5.00px");
  });

  it("beltAt finds the belt the scroll is in or within a screen of; beltOf finds the belt an element is on", async () => {
    const B = await belts();
    html(page);
    screen({ h: 800 });
    const list = B.makeBelts(document.getElementById("m")!, isBlock);
    box(list[0].belt, 0, 1000); box(list[0].root, 1000, 1000);
    box(list[1].belt, 0, 1000); box(list[1].root, 5000, 1000);
    B.measure(list);
    expect(B.beltAt(list, 100)).toBeNull();
    expect(B.beltAt(list, 300)).toBe(list[0]);
    expect(B.beltAt(list, 5500)).toBe(list[1]);
    expect(B.beltOf(list, document.getElementById("c"))).toBe(list[1]);
    expect(B.beltOf(list, document.getElementById("scene"))).toBeNull();
    expect(B.beltOf(list, null)).toBeNull();
  });

  it("scrollTargetFor: the scroll position that puts an element a little below the top, clamped to the belt's travel", async () => {
    const B = await belts();
    html(page);
    screen({ h: 800 });
    const list = B.makeBelts(document.getElementById("m")!, isBlock);
    const [b] = list;
    box(b.belt, 0, 3000); box(b.root, 1000, 3000);
    B.measure(list);
    const a = document.getElementById("a")!, bb = document.getElementById("b")!;
    box(a, 0, 1500); box(bb, 1500, 1500);
    expect(B.yInBelt(b, bb)).toBe(1500);
    expect(B.scrollTargetFor(list, bb)).toBe(Math.round(1000 + 1500 - 800 * 0.12));
    expect(B.scrollTargetFor(list, a)).toBe(1000);                       // near the top of the belt: not above it
    expect(B.scrollTargetFor(list, document.getElementById("scene")!)).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------------- art
describe("_art", () => {
  const art = () => atPage(() => import("../src/styles/_art"));
  const frame = (w: number, h: number, rows: string[]) => {
    // a mask from rows of digits 0-9 (density), one frame
    const m = new Float32Array(w * h);
    rows.forEach((r, y) => [...r].forEach((c, x) => { m[y * w + x] = Number(c) / 9; }));
    return { n: 1, w, h, fps: 12, label: "x", mask: [m] };
  };

  it("artConfig reads the config the compiler writes into #ss-art, and is null without it or when it is not JSON", async () => {
    const { artConfig } = await art();
    expect(artConfig()).toBeNull();
    html(`<script id="ss-art" type="application/json">{"sheet":"s.webp","frames":4,"w":8,"h":6,"fps":12,"invert":false,"label":"x"}</script>`);
    expect(artConfig()).toMatchObject({ sheet: "s.webp", frames: 4, w: 8, h: 6 });
    html(`<script id="ss-art" type="application/json">not json</script>`);
    expect(artConfig()).toBeNull();
  });

  it("asciiFrame turns a mask into characters from a density ramp: blank below the floor, denser for more subject", async () => {
    const { asciiFrame } = await art();
    const a = frame(4, 2, ["0099", "0099"]);
    expect(asciiFrame(a, 0, 4, 2)).toBe("  @@\n  @@");
    const faint = frame(2, 1, ["09"]);
    expect(asciiFrame(faint, 0, 2, 1)).toBe(" @");
    const mid = frame(1, 1, ["5"]);
    const ch = asciiFrame(mid, 0, 1, 1);
    expect(" .:-=+*#%@").toContain(ch);
    expect(ch).not.toBe(" ");
    expect(ch).not.toBe("@");
    // below the floor (0.24) nothing is drawn
    expect(asciiFrame(frame(1, 1, ["2"]), 0, 1, 1)).toBe(" ");
  });

  it("asciiFrame averages the cells when the grid is coarser than the frame, and wraps the frame number", async () => {
    const { asciiFrame } = await art();
    const a = frame(4, 2, ["9900", "9900"]);
    expect(asciiFrame(a, 0, 2, 1)).toBe("@ ");
    expect(asciiFrame(a, 3, 2, 1)).toBe("@ ");     // 3 mod 1 frame
    expect(asciiFrame(a, -2, 2, 1)).toBe("@ ");
    expect(asciiFrame(a, 0, 2, 1, " #")).toBe("# ");   // a custom ramp
  });

  it("rowsFor keeps the frame's proportions for a text grid, with at least 4 rows", async () => {
    const { rowsFor } = await art();
    const a = frame(100, 50, []);
    expect(rowsFor(a, 80, 8, 16)).toBe(Math.round(80 * 0.5 * 0.5));   // 20
    expect(rowsFor(a, 4, 8, 16)).toBe(4);
    expect(rowsFor(a, 80, 8, 8)).toBe(40);
  });

  it("loadArt decodes the sprite sheet into one mask per frame (inverted when the sheet was lit the other way), once", async () => {
    class FakeImage { onload: (() => void) | null = null; onerror: (() => void) | null = null; set src(_: string) { queueMicrotask(() => this.onload?.()); } }
    vi.stubGlobal("Image", FakeImage);
    const { loadArt } = await art();
    html(`<script id="ss-art" type="application/json">{"sheet":"s.webp","frames":2,"w":2,"h":1,"fps":8,"invert":true,"label":"orb"}</script>`);
    // 2 frames of 2x1 pixels: red channel 255, 0 | 0, 255
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(function () {
      return { drawImage() {}, getImageData: () => ({ data: new Uint8ClampedArray([255, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 0, 0, 255]) }) } as never;
    });
    const a = (await loadArt())!;
    expect(a).toMatchObject({ n: 2, w: 2, h: 1, fps: 8, label: "orb" });
    expect([...a.mask[0]]).toEqual([0, 1]);
    expect([...a.mask[1]]).toEqual([1, 0]);
    expect(await loadArt()).toBe(a);
  });

  it("loadArt is null when the page has no art, or the sheet does not load", async () => {
    expect(await (await art()).loadArt()).toBeNull();
    class BadImage { onload: (() => void) | null = null; onerror: (() => void) | null = null; set src(_: string) { queueMicrotask(() => this.onerror?.()); } }
    vi.stubGlobal("Image", BadImage);
    const { loadArt } = await art();
    html(`<script id="ss-art" type="application/json">{"sheet":"s.webp","frames":1,"w":1,"h":1,"fps":8,"invert":false,"label":"x"}</script>`);
    expect(await loadArt()).toBeNull();
  });
});
