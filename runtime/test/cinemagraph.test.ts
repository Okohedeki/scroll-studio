/**
 * Cinemagraphs: a still where only one thing moves. The video of the moving part is laid over the still through its mask;
 * it loads when near, plays when seen, and the page is complete without it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { atPage, box, frames, html, media, screen } from "./helpers";

// ---- a page with a controllable IntersectionObserver and media query
interface Obs { cb: (es: unknown[]) => void; opts: IntersectionObserverInit; targets: Element[] }
let observers: Obs[] = [];
let reducedListeners: (() => void)[] = [];
let styles = new Map<Element, Record<string, string>>();

beforeEach(() => {
  observers = []; reducedListeners = []; styles = new Map();
  screen({ w: 1280, h: 800, y: 0 });
  vi.stubGlobal("IntersectionObserver", class {
    o: Obs;
    constructor(cb: Obs["cb"], opts: IntersectionObserverInit) { this.o = { cb, opts, targets: [] }; observers.push(this.o); }
    observe(el: Element) { this.o.targets.push(el); }
    disconnect() {}
  });
  vi.stubGlobal("CSS", { supports: () => true });
  const real = window.matchMedia;
  vi.spyOn(window, "matchMedia").mockImplementation((q: string) => {
    const mql = real(q);
    return { ...mql, get matches() { return media.reduced && /reduced-motion/.test(q); }, addEventListener: (_t: string, fn: () => void) => { reducedListeners.push(fn); } } as unknown as MediaQueryList;
  });
  vi.spyOn(window, "getComputedStyle").mockImplementation((el: Element) => {
    const host = el as HTMLElement;
    return { objectFit: "cover", objectPosition: host.style?.objectPosition || "50% 50%", backgroundSize: "cover", backgroundPosition: host.style?.backgroundPosition || "50% 50%",
      zIndex: "auto", position: "static", transform: "none", opacity: "1", borderRadius: "0px", transformOrigin: "0px 0px", clipPath: "none", ...(styles.get(el) ?? {}) } as unknown as CSSStyleDeclaration;
  });
});
afterEach(() => {
  delete (window as any).__ssCine;
  Object.defineProperty(navigator, "connection", { configurable: true, value: undefined });
  Object.defineProperty(document, "hidden", { configurable: true, value: false });
});

const entry = (b: number[] = [0.1, 0.4, 0.2, 0.2], r = 2) => JSON.stringify({ v: "move.mp4", m: "mask.webp", b, r });
async function start(markup: string, o: { reduced?: boolean } = {}) {
  html(markup);
  const f = frames();
  const { start: go } = await atPage(() => import("../src/lib/cinemagraph"), o);
  go();
  return f;
}
const items = () => (window as any).__ssCine as { host: HTMLElement; layer: HTMLElement; video: HTMLVideoElement | null; state: string; seen: boolean }[] | undefined;
const img = (id = "im", e = entry()) => `<img id="${id}" data-cine='${e}' alt="">`;
const near = (el: Element, on = true) => observers[0].cb([{ target: el, isIntersecting: on }]);
const seen = (el: Element, o: { on?: boolean; ratio?: number; height?: number } = {}) =>
  observers[1].cb([{ target: el, isIntersecting: o.on ?? true, intersectionRatio: o.ratio ?? 0.5, intersectionRect: { height: o.height ?? 0 } }]);

describe("when it does nothing at all (the still, and no work)", () => {
  it("on a page without cinemagraphs", async () => {
    await start("<p>none</p>");
    expect(items()).toBeUndefined();
    expect(observers).toHaveLength(0);
  });

  it("with reduced motion", async () => {
    await start(img(), { reduced: true });
    expect(items()).toBeUndefined();
    expect(document.querySelector(".ss-cine")).toBeNull();
  });

  it("when the visitor asked to save data, or the connection is 2G", async () => {
    for (const connection of [{ saveData: true }, { effectiveType: "2g" }, { effectiveType: "slow-2g" }]) {
      Object.defineProperty(navigator, "connection", { configurable: true, value: connection });
      await start(img());
      expect(items()).toBeUndefined();
    }
    Object.defineProperty(navigator, "connection", { configurable: true, value: { effectiveType: "4g" } });
    await start(img());
    expect(items()).toHaveLength(1);
  });

  it("when the browser cannot mask (no CSS mask-image)", async () => {
    vi.stubGlobal("CSS", { supports: () => false });
    await start(img());
    expect(items()).toBeUndefined();
  });

  it("for an entry that is not JSON or lacks a field", async () => {
    await start(`<img data-cine="{nope"><img data-cine='{"v":"a.mp4","m":"m.webp","r":2}'><img data-cine='{"v":"a.mp4","m":"m.webp","b":[0,0,1,1],"r":0}'>`);
    expect(items()).toBeUndefined();
  });
});

describe("setting up", () => {
  it("puts a hidden, inert layer after each image, and the page's own markup stays where it is", async () => {
    await start(`<div id="wrap">${img("a")}${img("b")}</div>`);
    expect(items()).toHaveLength(2);
    const layers = [...document.querySelectorAll<HTMLElement>(".ss-cine")];
    expect(layers).toHaveLength(2);
    expect(document.getElementById("a")!.nextElementSibling).toBe(layers[0]);
    expect(layers[0].getAttribute("aria-hidden")).toBe("true");
    expect(layers[0].style.display).toBe("none");
    expect(layers[0].style.pointerEvents).toBe("none");
    expect(document.getElementById("wrap")!.querySelectorAll("img")).toHaveLength(2);
  });

  it("a background element gets its layer as the first child, behind its content, with a stacking context of its own", async () => {
    await start(`<section id="bg" data-cine='${entry()}'><h2>Title</h2></section>`);
    const bg = document.getElementById("bg")!;
    expect(bg.firstElementChild!.classList.contains("ss-cine")).toBe(true);
    expect(bg.style.position).toBe("relative");
    expect(bg.style.isolation).toBe("isolate");
    expect((bg.firstElementChild as HTMLElement).style.zIndex).toBe("-1");
  });

  it("a layer takes the stacking order of the image it sits over", async () => {
    html(img());
    styles.set(document.getElementById("im")!, { zIndex: "3" });
    const { start: go } = await atPage(() => import("../src/lib/cinemagraph"));
    go();
    expect(document.querySelector<HTMLElement>(".ss-cine")!.style.zIndex).toBe("3");
  });

  it("loads the video when it is a screen away, and not before", async () => {
    await start(img());
    const host = document.getElementById("im")!;
    expect(observers[0].opts.rootMargin).toBe("100% 0px 100% 0px");
    expect(observers[0].targets).toEqual([host]);
    expect(items()![0].video).toBeNull();
    near(host, false);
    expect(items()![0].video).toBeNull();
    near(host);
    const v = items()![0].video!;
    expect(v.getAttribute("src")).toBe("move.mp4");
    expect(v.muted && v.loop && v.playsInline).toBe(true);
    expect(v.preload).toBe("auto");
    expect(v.getAttribute("aria-hidden")).toBe("true");
    expect(v.tabIndex).toBe(-1);
    expect(items()![0].layer.contains(v)).toBe(true);
    expect(items()![0].state).toBe("loading");
    near(host);
    expect(items()![0].layer.querySelectorAll("video")).toHaveLength(1);     // loaded once
  });
});

describe("laying the video over the still", () => {
  it("the layer takes the image's box and the video sits where the moving part is on the still", async () => {
    await start(img());
    const host = document.getElementById("im")!;
    box(host, 30, 100, { left: 50, width: 200 });                  // 200 x 100: exactly the still's 2:1
    near(host);
    const { layer, video } = items()![0];
    expect(layer.style.display).toBe("block");
    expect([layer.style.left, layer.style.top, layer.style.width, layer.style.height]).toEqual(["50px", "30px", "200px", "100px"]);
    // b = x .1, y .4, w .2, h .2 of the still
    expect([video!.style.left, video!.style.top, video!.style.width, video!.style.height]).toEqual(["20px", "40px", "40px", "20px"]);
  });

  it("follows a still that is cropped to fill its box (object-fit: cover), centred", async () => {
    await start(img());
    const host = document.getElementById("im")!;
    box(host, 0, 100, { width: 100 });                             // a 1:1 box for a 2:1 still: the sides are cropped
    near(host);
    const { video } = items()![0];
    // the picture is 200 wide in a box of 100, 50 cropped off each side; the moving part is at .1-.3 of 200, which that crop
    // mostly hides, so the crop slides all the way to the left edge to show it
    expect(host.style.objectPosition).toBe("0% 50%");
    expect(video!.style.left).toBe("20px");
    expect(video!.style.width).toBe("40px");
  });

  it("slides the crop to keep the moving part in view when a narrow screen would crop it away", async () => {
    await start(img("im", entry([0.1, 0.4, 0.2, 0.2], 2)));
    const host = document.getElementById("im")!;
    box(host, 0, 200, { width: 100 });                             // a tall, narrow box: the still is 400 wide, 150 cropped off each side
    near(host);
    expect(host.style.objectPosition).toBe("10% 50%");              // brings 0.2 of the width (the centre of the moving part) to the middle
    const { video } = items()![0];
    expect([video!.style.left, video!.style.top, video!.style.width, video!.style.height]).toEqual(["10px", "80px", "80px", "40px"]);
  });

  it("leaves the crop alone when the moving part is already in view", async () => {
    await start(img("im", entry([0.4, 0.4, 0.2, 0.2], 2)));
    const host = document.getElementById("im")!;
    box(host, 0, 200, { width: 100 });
    near(host);
    expect(host.style.objectPosition).toBe("");
  });

  it("hides the layer when the box has no size, or the image is fitted in a way it does not know", async () => {
    await start(img());
    const host = document.getElementById("im")!;
    near(host);
    expect(items()![0].layer.style.display).toBe("none");           // no layout yet: nothing to lay over
    box(host, 0, 100, { width: 200 });
    styles.set(host, { objectFit: "none" });
    window.dispatchEvent(new Event("resize"));
    expect(items()![0].layer.style.display).toBe("none");
    styles.set(host, { objectFit: "contain" });
    window.dispatchEvent(new Event("resize"));
    expect(items()![0].layer.style.display).toBe("block");
  });

  it("lays out again on resize", async () => {
    await start(img());
    const host = document.getElementById("im")!;
    box(host, 0, 100, { width: 200 });
    near(host);
    const before = items()![0].video!.style.width;
    box(host, 0, 200, { width: 400 });
    window.dispatchEvent(new Event("resize"));
    expect(items()![0].video!.style.width).not.toBe(before);
    expect(items()![0].video!.style.width).toBe("80px");
  });
});

describe("playing", () => {
  const setup = async () => {
    const f = await start(img());
    const host = document.getElementById("im")!;
    box(host, 0, 100, { width: 200 });
    near(host);
    return { f, host, it: items()![0], play: vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined), pause: vi.spyOn(HTMLMediaElement.prototype, "pause") };
  };

  it("plays while it is on screen, and pauses when it is not", async () => {
    const { host, it, play, pause } = await setup();
    seen(host, { ratio: 0.5 });
    expect(it.seen).toBe(true);
    expect(play).toHaveBeenCalledTimes(1);
    Object.defineProperty(it.video!, "paused", { configurable: true, value: false });
    seen(host, { on: false, ratio: 0 });
    expect(it.seen).toBe(false);
    expect(pause).toHaveBeenCalledTimes(1);
  });

  it("a sliver at the edge of the screen is not worth a decode, unless it takes up half the screen's height", async () => {
    const { host, it, play } = await setup();
    seen(host, { ratio: 0.05, height: 20 });
    expect(it.seen).toBe(false);
    expect(play).not.toHaveBeenCalled();
    seen(host, { ratio: 0.05, height: 400 });
    expect(it.seen).toBe(true);
    seen(host, { ratio: 0.14, height: 20 });
    expect(it.seen).toBe(false);
    seen(host, { ratio: 0.15, height: 20 });
    expect(it.seen).toBe(true);                       // 15% of it is enough
  });

  it("seen also loads a video that was not near yet (a jump straight to it)", async () => {
    await start(img());
    const host = document.getElementById("im")!;
    seen(host);
    expect(items()![0].video).not.toBeNull();
  });

  it("fades the video in once it is playing, and the still stays beneath it", async () => {
    const { it } = await setup();
    expect(it.video!.style.opacity).toBe("0");
    it.video!.dispatchEvent(new Event("playing"));
    expect(it.state).toBe("playing");
    expect(it.video!.style.opacity).toBe("1");
  });

  it("waits for a real frame to fade in when the browser can say so", async () => {
    await start(img());
    const host = document.getElementById("im")!;
    const cbs: (() => void)[] = [];
    HTMLVideoElement.prototype.requestVideoFrameCallback = ((cb: () => void) => { cbs.push(cb); return 1; }) as never;
    try {
      near(host);
      const v = items()![0].video!;
      v.dispatchEvent(new Event("playing"));
      expect(v.style.opacity).toBe("0");
      cbs[0]();
      expect(v.style.opacity).toBe("1");
    } finally { delete (HTMLVideoElement.prototype as any).requestVideoFrameCallback; }
  });

  it("a video that fails to load is removed and never tried again: the still stays", async () => {
    const { host, it } = await setup();
    const v = it.video!;
    v.dispatchEvent(new Event("error"));
    expect(it.state).toBe("failed");
    expect(it.video).toBeNull();
    expect(it.layer.contains(v)).toBe(false);
    near(host);
    expect(it.layer.querySelectorAll("video")).toHaveLength(0);
  });

  it("pauses in a hidden tab", async () => {
    const { host, it, pause } = await setup();
    seen(host);
    Object.defineProperty(it.video!, "paused", { configurable: true, value: false });
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(pause).toHaveBeenCalled();
  });

  it("goes back to the still when reduced motion is turned on while it plays", async () => {
    const { host, it } = await setup();
    seen(host);
    it.video!.dispatchEvent(new Event("playing"));
    expect(it.video!.style.opacity).toBe("1");
    media.reduced = true;
    reducedListeners.forEach((fn) => fn());
    expect(it.video!.style.opacity).toBe("0");
  });

  it("an image's own transform and opacity (a hero's slow zoom) are copied to the layer while it is on screen, and the work stops when nothing is", async () => {
    const { f, host, it } = await setup();
    seen(host);
    styles.set(host, { transform: "matrix(1.1, 0, 0, 1.1, 0, 0)", opacity: "0.5" });
    f.step();
    expect(it.layer.style.transform).toBe("matrix(1.1, 0, 0, 1.1, 0, 0)");
    expect(it.layer.style.opacity).toBe("0.5");
    expect(f.pending).toBe(1);                       // still running while it is seen
    seen(host, { on: false, ratio: 0 });
    f.step();
    expect(f.pending).toBe(0);                       // nothing on screen: no work at all
  });
});
