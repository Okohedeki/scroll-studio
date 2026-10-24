/** The players that draw media: vector (an SVG that strokes itself), sequence/inside (pre-rendered frames), film (a scrubbed video). */
import { afterEach, describe, expect, it, vi } from "vitest";
import { easeInOut } from "../src/lib/util";
import { atPage, frameState, playerCtx } from "./helpers";
import type { FakeContext } from "./setup";

afterEach(() => {
  history.replaceState(null, "", "/");
  vi.doUnmock("../src/lib/util");
  vi.doUnmock("../src/players/world");
  vi.doUnmock("../src/players/reveal");
});

/** The real util with some of its loaders replaced. */
function mockUtil(over: Record<string, unknown>) {
  vi.doMock("../src/lib/util", async (orig) => ({ ...(await orig<typeof import("../src/lib/util")>()), ...over }));
}

// ---------------------------------------------------------------------------------------------------------------- vector
describe("vector", () => {
  const svg = (n: number) => `<svg viewBox="0 0 10 10">${Array.from({ length: n }, (_, i) => `<path d="M${i} 0L${i} 9" data-fill="#00ff00"/>`).join("")}</svg>`;
  async function mount(n: number, cfg: Record<string, unknown> = {}, steps: { intro?: boolean }[] = []) {
    vi.stubGlobal("fetch", vi.fn(async () => ({ text: async () => svg(n) })));
    const { default: factory } = await atPage(() => import("../src/players/vector"));
    const ctx = playerCtx(steps);
    const player = await factory({ svg: "/d.svg", ...cfg }, ctx);
    const paths = [...ctx.visual.querySelectorAll<SVGPathElement>("path")];
    return { player, paths, svgEl: ctx.visual.querySelector("svg")! };
  }

  it("starts undrawn and unfilled, every path ready to be stroked in with pathLength 1", async () => {
    const { paths } = await mount(5);
    expect(paths).toHaveLength(5);
    for (const p of paths) {
      expect(p.getAttribute("pathLength")).toBe("1");
      expect(p.style.strokeDashoffset).toBe("1");
      expect(p.style.fillOpacity).toBe("0");
    }
  });

  it("without steps the first 60% of the scroll draws the outlines and the rest fills them", async () => {
    const { player, paths } = await mount(10);
    player.update(frameState(1));
    for (const p of paths) { expect(p.style.strokeDashoffset).toBe("0"); expect(p.style.fillOpacity).toBe("1"); }
    expect(+paths[0].style.strokeOpacity).toBeCloseTo(0.15, 12);               // once filled the outline recedes
    player.update(frameState(0));
    for (const p of paths) { expect(p.style.strokeDashoffset).toBe("1"); expect(p.style.fillOpacity).toBe("0"); }
  });

  it("paths draw in order: an earlier path is never less drawn than a later one", async () => {
    const { player, paths } = await mount(20);
    for (const p of [0.1, 0.2, 0.3, 0.4, 0.5]) {
      player.update(frameState(p));
      const drawn = paths.map((x) => 1 - +x.style.strokeDashoffset);
      expect(drawn).toEqual([...drawn].sort((a, b) => b - a));
    }
    player.update(frameState(0.2));
    const drawn = paths.map((x) => 1 - +x.style.strokeDashoffset);
    expect(drawn[0]).toBe(1);                        // the first path is already complete
    expect(drawn[19]).toBe(0);                       // the last has not begun
  });

  it("with steps, the first real step draws, the next fills, and any later ones hold with a slow push-in", async () => {
    const { player, paths, svgEl } = await mount(4, {}, [{ intro: true }, {}, {}, {}]);
    player.update(frameState(0.9, { steps: [1, 0, 0, 0] }));        // the intro step is not a phase
    expect(paths[0].style.strokeDashoffset).toBe("1");
    player.update(frameState(0.9, { steps: [1, 1, 0, 0] }));
    for (const p of paths) expect(p.style.strokeDashoffset).toBe("0");
    expect(paths[0].style.fillOpacity).toBe("0");
    player.update(frameState(0.9, { steps: [1, 1, 1, 0] }));
    for (const p of paths) expect(p.style.fillOpacity).toBe("1");
    expect(svgEl.style.transform).toBe("scale(1)");
    player.update(frameState(0.9, { steps: [1, 1, 1, 1] }));
    expect(svgEl.style.transform).toBe("scale(1.06)");
  });

  it("the drawing step's progress is eased and overshoots slightly so the last path closes before the step ends", async () => {
    const { player, paths } = await mount(2, {}, [{}, {}]);
    player.update(frameState(0.5, { steps: [0.5, 0] }));
    const de = easeInOut(0.525);
    const expected = (i: number) => Math.min(1, Math.max(0, (de - (i / 2) * 0.85) / 0.15));
    paths.forEach((p, i) => expect(1 - +p.style.strokeDashoffset).toBeCloseTo(expected(i), 6));
  });

  it("colours: ink for fills unless the drawing carries its own, accent when asked", async () => {
    document.documentElement.style.setProperty("--ink", "#102030");
    document.documentElement.style.setProperty("--accent", "#c04000");
    expect((await mount(1, { colors: "ink" })).paths[0].style.fill).toBe("#102030");
    expect((await mount(1, { colors: "accent" })).paths[0].style.fill).toBe("#c04000");
    expect((await mount(1, {})).paths[0].style.fill).toBe("#00ff00");     // its own data-fill
  });
});

// ---------------------------------------------------------------------------------------------------------------- frames
describe("sequence and inside (frames)", () => {
  const cfgFor = (extra: Record<string, unknown> = {}) => ({ count: 5, desktop: { base: "f/", ext: "jpg" }, ...extra });
  const bitmap = (id: number) => ({ id, width: 100, height: 50 });
  const idOf = (url: string) => Number(/(\d+)\.\w+$/.exec(url)![1]) - 1;

  async function mount(cfg: Record<string, unknown>, o: { p?: number | null; reduced?: boolean; mobile?: boolean; fail?: number[] } = {}) {
    const loads: string[] = [];
    mockUtil({ loadBitmap: vi.fn(async (url: string) => { loads.push(url); if (o.fail?.includes(idOf(url))) throw new Error("404"); return bitmap(idOf(url)); }) });
    vi.spyOn(HTMLCanvasElement.prototype, "getBoundingClientRect").mockReturnValue({ width: 800, height: 400, left: 0, top: 0, right: 800, bottom: 400, x: 0, y: 0 } as DOMRect);
    const { default: factory } = await atPage(() => import("../src/players/frames"), { p: o.p === null ? undefined : (o.p ?? 0.5), reduced: o.reduced, mobile: o.mobile });
    const ctx = playerCtx();
    const player = await factory(cfg, ctx);
    const canvas = ctx.visual.querySelector("canvas")!;
    const g = canvas.getContext("2d") as unknown as FakeContext;
    const drawn = () => g.calls.filter(([n]) => n === "drawImage").map(([, img]) => (img as { id: number }).id);
    return { player, ctx, canvas, g, loads, drawn };
  }

  it("downloads every frame (urls numbered from 0001), in an order that fills the timeline evenly, and reports progress", async () => {
    const { loads, ctx } = await mount(cfgFor());
    expect(loads).toEqual(["f/0001.jpg", "f/0005.jpg", "f/0003.jpg", "f/0002.jpg", "f/0004.jpg"]);
    const reported = ctx.progress.mock.calls.map(([f]) => f);
    expect(reported).toEqual([0.2, 0.4, 0.6, 0.8, 1]);
  });

  it("draws the frame the scroll is on", async () => {
    const { player, drawn } = await mount(cfgFor());
    player.update(frameState(0.5));        // frame 2 of 0-4
    expect(drawn()).toEqual([2]);
  });

  it("between two frames it cross-fades by the fractional position", async () => {
    const { player, g, drawn } = await mount(cfgFor());
    player.update(frameState(0.6));        // 2.4
    expect(drawn()).toEqual([2, 3]);
    expect(g.alphaAtDraw[0]).toBe(1);
    expect(g.alphaAtDraw[1]).toBeCloseTo(0.4, 12);
    expect(g.globalAlpha).toBe(1);         // and is put back
  });

  it("does not draw the next frame for a sliver of a fraction", async () => {
    const { player, drawn } = await mount(cfgFor());
    player.update(frameState(0.5 + 0.01 / 4));
    expect(drawn()).toEqual([2]);
  });

  it("does not redraw when the position has hardly moved", async () => {
    const { player, drawn } = await mount(cfgFor());
    player.update(frameState(0.5));
    player.update(frameState(0.5001));
    expect(drawn()).toEqual([2]);
    player.update(frameState(0.55));
    expect(drawn().length).toBeGreaterThan(1);
  });

  it("eases toward the target by 14% a frame, unless the page asked for a jump (?p=) or for reduced motion", async () => {
    const eased = await mount(cfgFor(), { p: null });
    eased.player.update(frameState(1));            // the target is frame 4; one step of the ease gets to 0.56
    expect(eased.drawn()).toEqual([0, 1]);
    expect(eased.g.alphaAtDraw[1]).toBeCloseTo(0.56, 12);
    eased.player.update(frameState(1));            // 0.56 + (4 - 0.56) * 0.14
    expect(eased.drawn().slice(2)).toEqual([1, 2]);
    expect(eased.g.alphaAtDraw[3]).toBeCloseTo(0.0416, 6);
    const jump = await mount(cfgFor(), { p: 0.5 });
    jump.player.update(frameState(1));
    expect(jump.drawn()).toEqual([4]);
  });

  it("a frame that failed to load is skipped, never crashes the scroll", async () => {
    const { player, drawn } = await mount(cfgFor(), { fail: [2] });
    expect(() => player.update(frameState(0.5))).not.toThrow();
    expect(drawn()).toEqual([]);
    player.update(frameState(0));
    expect(drawn()).toEqual([0]);
  });

  it("the last frame draws alone (nothing to fade to)", async () => {
    const { player, drawn } = await mount(cfgFor());
    player.update(frameState(1));
    expect(drawn()).toEqual([4]);
  });

  it("a phone gets its own frames when the scene has them", async () => {
    const { loads } = await mount(cfgFor({ mobile: { base: "m/", ext: "webp" } }), { mobile: true });
    expect(loads.every((u) => u.startsWith("m/") && u.endsWith(".webp"))).toBe(true);
    const desktop = await mount(cfgFor({ mobile: { base: "m/", ext: "webp" } }));
    expect(desktop.loads.every((u) => u.startsWith("f/"))).toBe(true);
  });

  it("with reduced motion a scene with stops shows one still per stop: only those frames are downloaded", async () => {
    const stops = [{ frame: 1, at: [0.2, 0.4] }, { frame: 3, at: [0.6, 0.8] }];
    const { loads, player, drawn } = await mount(cfgFor({ stops }), { reduced: true });
    expect(loads.sort()).toEqual(["f/0001.jpg", "f/0002.jpg", "f/0004.jpg", "f/0005.jpg"]);   // opening, each stop, closing
    player.update(frameState(0.1));
    expect(drawn()).toEqual([0]);
    player.update(frameState(0.3));
    expect(drawn()).toEqual([0, 1]);
    player.update(frameState(0.7));
    expect(drawn()).toEqual([0, 1, 3]);
    player.update(frameState(0.95));
    expect(drawn()).toEqual([0, 1, 3, 4]);
    player.update(frameState(0.96));        // the same still: not drawn again
    expect(drawn()).toEqual([0, 1, 3, 4]);
  });

  it("resize fits the canvas to its box at the device pixel ratio, up to 2", async () => {
    const { player, canvas } = await mount(cfgFor());
    expect(canvas.width).toBe(800);
    Object.defineProperty(window, "devicePixelRatio", { configurable: true, value: 3 });
    player.resize!();
    expect(canvas.width).toBe(1600);
    expect(canvas.height).toBe(800);
    Object.defineProperty(window, "devicePixelRatio", { configurable: true, value: 1 });
  });

  it("falls back to the frames when the world player cannot start", async () => {
    vi.doMock("../src/players/world", () => { throw new Error("no webgl2"); });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { drawn, player } = await mount(cfgFor({ world: {}, video: "v.mp4" }));
    expect(warn).toHaveBeenCalled();
    player.update(frameState(0));
    expect(drawn()).toEqual([0]);
  });
});

// ---------------------------------------------------------------------------------------------------------------- film
describe("film (video player)", () => {
  /** Mounts the player and plays the part of the browser: the video loads, with a duration. */
  async function mount(cfg: Record<string, unknown>, o: { p?: number; reduced?: boolean; mobile?: boolean; duration?: number; blob?: boolean } = {}) {
    const fetchBlobURL = vi.fn(async (url: string, _progress?: (f: number) => void) => { if (o.blob === false) throw new Error("file://"); return "blob:" + url; });
    mockUtil({ fetchBlobURL });
    const { default: factory } = await atPage(() => import("../src/players/video"), { p: o.p ?? 0.5, reduced: o.reduced, mobile: o.mobile });
    const ctx = playerCtx();
    const pending = factory(cfg, ctx);
    const video = await vi.waitFor(() => { const v = ctx.visual.querySelector("video"); if (!v || !v.getAttribute("src")) throw new Error("not yet"); return v; });
    let time = 0, seeking = false;
    Object.defineProperty(video, "duration", { configurable: true, get: () => o.duration ?? 10 });
    Object.defineProperty(video, "currentTime", { configurable: true, get: () => time, set: (v: number) => { time = v; } });
    Object.defineProperty(video, "seeking", { configurable: true, get: () => seeking });
    video.dispatchEvent(new Event("loadeddata"));
    const player = await pending;
    return { player, video, ctx, fetchBlobURL, seek: () => time, setSeeking: (v: boolean) => { seeking = v; } };
  }

  it("downloads the whole file into a muted inline video before the page unlocks", async () => {
    const { video, fetchBlobURL, ctx } = await mount({ video: "/film.mp4" });
    expect(fetchBlobURL).toHaveBeenCalledWith("/film.mp4", expect.any(Function), "video/mp4");
    expect(video.getAttribute("src")).toBe("blob:/film.mp4");
    expect(video.muted).toBe(true);
    expect(video.playsInline).toBe(true);
    expect(ctx.visual.contains(video)).toBe(true);
  });

  it("scales download progress to 95%, leaving the rest for the first frame", async () => {
    const { fetchBlobURL, ctx } = await mount({ video: "/film.mp4" });
    const onProgress = fetchBlobURL.mock.calls[0][1] as (f: number) => void;
    onProgress(1);
    expect(ctx.progress).toHaveBeenLastCalledWith(0.95);
  });

  it("streams the URL when it cannot be downloaded (opened from file://)", async () => {
    const { video } = await mount({ video: "film.mp4" }, { blob: false });
    expect(video.getAttribute("src")).toBe("film.mp4");
  });

  it("a phone gets the lighter film when there is one", async () => {
    expect((await mount({ video: "big.mp4", videoMobile: "small.mp4" }, { mobile: true })).video.getAttribute("src")).toBe("blob:small.mp4");
    expect((await mount({ video: "big.mp4", videoMobile: "small.mp4" })).video.getAttribute("src")).toBe("blob:big.mp4");
  });

  it("scrubs the film to scroll progress (leaving the last 0.05 s unplayed)", async () => {
    const { player, seek } = await mount({ video: "/f.mp4" });
    player.update(frameState(0.5));
    expect(seek()).toBeCloseTo(0.5 * 9.95, 9);
    player.update(frameState(1));
    expect(seek()).toBeCloseTo(9.95, 9);
    player.update(frameState(0));
    expect(seek()).toBeCloseTo(0, 9);
  });

  it("does not ask for a new frame while the last seek is still landing, nor for a movement too small to see", async () => {
    const { player, seek, setSeeking } = await mount({ video: "/f.mp4" });
    player.update(frameState(0.5));
    const at = seek();
    setSeeking(true);
    player.update(frameState(0.9));
    expect(seek()).toBe(at);
    setSeeking(false);
    player.update(frameState(0.5 + 0.005 / 9.95));
    expect(seek()).toBe(at);
  });

  it("a film with no duration (metadata not loaded) is left alone until it has one", async () => {
    const { player, seek, video } = await mount({ video: "/f.mp4" }, { duration: 0 });
    player.update(frameState(0.5));
    expect(seek()).toBe(0.001);          // only the nudge that makes the first frame show
    Object.defineProperty(video, "duration", { configurable: true, get: () => 4 });
    video.dispatchEvent(new Event("loadedmetadata"));
    player.update(frameState(0.5));
    expect(seek()).toBeCloseTo(0.5 * 3.95, 9);
  });

  it("the first touch plays and pauses the video once, so iOS will decode frames for seeking", async () => {
    const { video } = await mount({ video: "/f.mp4" });
    const play = vi.fn(async () => {}), pause = vi.fn();
    video.play = play as unknown as typeof video.play; video.pause = pause;
    window.dispatchEvent(new Event("touchstart"));
    await Promise.resolve();
    expect(play).toHaveBeenCalledTimes(1);
    window.dispatchEvent(new Event("touchstart"));
    expect(play).toHaveBeenCalledTimes(1);
  });

  it("the one-take page with reduced motion shows stills: no film is fetched", async () => {
    mockUtil({ fetchBlobURL: vi.fn() });
    const { default: factory } = await atPage(() => import("../src/players/video"), { reduced: true });
    const ctx = playerCtx();
    const player = await factory({ video: "/f.mp4", journey: { duration: 5, map: [[0, 0], [1, 5]], stops: [] } }, ctx);
    expect(ctx.visual.querySelector("video")).toBeNull();
    expect(() => player.update(frameState(0.5))).not.toThrow();
  });

  it("the reveal shader falls back to the plain colour film when it cannot start", async () => {
    vi.doMock("../src/players/reveal", () => { throw new Error("no webgl2"); });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { video } = await mount({ video: "/f.mp4", reveal: {} });
    expect(video).toBeTruthy();
    expect(warn).toHaveBeenCalled();
  });
});
