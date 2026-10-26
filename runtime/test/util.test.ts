import { describe, expect, it, vi } from "vitest";
import { clamp, easeInOut, fetchBlobURL, formatScale, frameOffset, hexToRgb, lerp, loadBitmap, parseScale, rng, scaleAt, smooth } from "../src/lib/util";
import { fresh, media } from "./helpers";

describe("a phone's view of a photo with a calm side", () => {
  it("leans toward the frame by the part of the photo off screen, never past an edge", () => {
    // a 16:9 photo on a 390x844 phone covers about 3.85 screen widths
    const span = (16 / 9) / (390 / 844);
    const [x] = frameOffset(0.26, span, true);
    expect(x).toBeCloseTo((0.26 - 0.5) * (1 - 1 / span), 6);
    expect(frameOffset(0, span, true)[0]).toBeCloseTo(-(1 - 1 / span) / 2, 6);       // its left edge, exactly
    expect(frameOffset(1, span, true)[0]).toBeCloseTo((1 - 1 / span) / 2, 6);
    expect(frameOffset(-2, span, true)[0]).toBeCloseTo(-(1 - 1 / span) / 2, 6);      // clamped to the edge
  });
  it("stays centred without a frame, off a phone, or when the photo fits the screen", () => {
    expect(frameOffset(null, 3, true)).toEqual([0, 0]);
    expect(frameOffset(0.2, 3, false)).toEqual([0, 0]);
    expect(frameOffset(0.2, 1, true)).toEqual([0, 0]);
    expect(frameOffset(0.5, 3, true)[0]).toBeCloseTo(0, 9);
  });
});

describe("scroll maths", () => {
  it("clamp holds a value inside [a, b] and defaults to 0-1", () => {
    expect(clamp(0.4)).toBe(0.4);
    expect(clamp(-3)).toBe(0);
    expect(clamp(9)).toBe(1);
    expect(clamp(5, 2, 4)).toBe(4);
    expect(clamp(1, 2, 4)).toBe(2);
  });

  it("smooth is 0 before the window, 1 after it, and eases through the middle", () => {
    expect(smooth(0.2, 0.6, 0.1)).toBe(0);
    expect(smooth(0.2, 0.6, 0.6)).toBe(1);
    expect(smooth(0.2, 0.6, 0.9)).toBe(1);
    expect(smooth(0.2, 0.6, 0.4)).toBeCloseTo(0.5, 12);
    expect(smooth(0, 1, 0.25)).toBeCloseTo(0.15625, 12);
    let prev = -1;
    for (let v = 0; v <= 1.0001; v += 0.05) { const s = smooth(0, 1, v); expect(s).toBeGreaterThanOrEqual(prev); prev = s; }
  });

  it("easeInOut is symmetric about the middle and pinned at both ends", () => {
    expect(easeInOut(0)).toBe(0);
    expect(easeInOut(1)).toBe(1);
    expect(easeInOut(0.5)).toBe(0.5);
    for (const t of [0.1, 0.25, 0.4]) expect(easeInOut(t) + easeInOut(1 - t)).toBeCloseTo(1, 12);
    expect(easeInOut(0.25)).toBeLessThan(0.25);    // slow start
    expect(easeInOut(0.75)).toBeGreaterThan(0.75); // slow end
  });

  it("lerp interpolates and extrapolates linearly", () => {
    expect(lerp(10, 20, 0)).toBe(10);
    expect(lerp(10, 20, 1)).toBe(20);
    expect(lerp(10, 20, 0.25)).toBe(12.5);
    expect(lerp(10, 20, 2)).toBe(30);
  });
});

describe("hexToRgb", () => {
  it("reads 6-digit and 3-digit colours, with or without #, as 0-1", () => {
    expect(hexToRgb("#ff8000")).toEqual([1, 128 / 255, 0]);
    expect(hexToRgb("00ff00")).toEqual([0, 1, 0]);
    expect(hexToRgb("#f08")).toEqual([1, 0, 136 / 255]);
  });
});

describe("rng", () => {
  it("is deterministic for a seed and different between seeds", () => {
    const a = rng(42), b = rng(42), c = rng(43);
    const xs = Array.from({ length: 5 }, () => a()), ys = Array.from({ length: 5 }, () => b());
    expect(xs).toEqual(ys);
    expect(Array.from({ length: 5 }, () => c())).not.toEqual(xs);
  });

  it("stays inside the requested range", () => {
    const r = rng();
    for (let i = 0; i < 500; i++) { const v = r(-2, 3); expect(v).toBeGreaterThanOrEqual(-2); expect(v).toBeLessThan(3); }
  });

  it("a seed of 0 (or a multiple of the modulus) does not lock the generator at 0", () => {
    expect(rng(0)()).toBeGreaterThan(0);
    expect(rng(2147483647)()).toBeGreaterThan(0);
  });
});

describe("scale labels", () => {
  it("parseScale reads a number and a unit, with thousands separators and a micro sign", () => {
    expect(parseScale("100 µm")).toMatchObject({ unit: "µm" });
    expect(parseScale("100 µm")!.v).toBeCloseTo(100e-6, 15);
    expect(parseScale("1,000 km")).toEqual({ v: 1e6, unit: "km" });
    expect(parseScale("2nm")!.v).toBeCloseTo(2e-9, 18);
    expect(parseScale("8 kpc")?.unit).toBe("kpc");
  });

  it("parseScale rejects what is not a scale", () => {
    expect(parseScale("big")).toBeNull();
    expect(parseScale("12 parsnips")).toBeNull();
    expect(parseScale("")).toBeNull();
  });

  it("formatScale picks the largest unit of the ladder that fits, with a sensible number of digits", () => {
    expect(formatScale(2.5e-6, ["nm", "mm"])).toBe("2.5 µm");
    expect(formatScale(3e-3, ["mm"])).toBe("3 mm");
    expect(formatScale(12_000, ["m", "km"])).toBe("12 km");
    expect(formatScale(1e-9, ["nm"])).toBe("1 nm");
    expect(formatScale(1.496e11 * 3, ["AU", "ly"])).toBe("3 AU");   // the second ladder, when the labels are on it
    expect(formatScale(1e-12, ["nm", "µm"])).toBe("0 nm");          // below the first unit: the first unit
  });

  it("formatScale groups big numbers in thousands", () => {
    expect(formatScale(5e6, ["m", "km"])).toBe("5,000 km");
  });

  it("scaleAt interpolates in log space between neighbouring labels", () => {
    const labels = ["1 m", "100 m"];
    expect(scaleAt(labels, 0)).toBe("1 m");
    expect(scaleAt(labels, 1)).toBe("100 m");
    expect(scaleAt(labels, 0.5)).toBe("10 m");   // the geometric middle
    expect(scaleAt(labels, 7)).toBe("100 m");    // past the end
    expect(scaleAt(labels, -2)).toBe("1 m");     // before the start
  });

  it("scaleAt falls back to the nearer label when a label is not a scale, and to '' with none", () => {
    expect(scaleAt(["near", "far"], 0.4)).toBe("near");
    expect(scaleAt(["near", "far"], 0.6)).toBe("far");
    expect(scaleAt([], 3)).toBe("");
  });
});

describe("what the page asks for", () => {
  const util = () => fresh(() => import("../src/lib/util"));

  it("?p= sets debugP (clamped) and makes eased values jump straight to their target", async () => {
    history.replaceState(null, "", "/?p=0.4&s=intro");
    const u = await util();
    expect(u.debugP).toBe(0.4);
    expect(u.params.get("s")).toBe("intro");
    expect(u.follow).toBe(1);
    history.replaceState(null, "", "/?p=7");
    expect((await util()).debugP).toBe(1);
    history.replaceState(null, "", "/?p=-1");
    expect((await util()).debugP).toBe(0);
    history.replaceState(null, "", "/");
  });

  it("without ?p= scroll values are eased (0.14 per frame)", async () => {
    const u = await util();
    expect(u.debugP).toBeNull();
    expect(u.follow).toBe(0.14);
    expect(u.reducedMotion).toBe(false);
  });

  it("prefers-reduced-motion turns easing off", async () => {
    media.reduced = true;
    const u = await util();
    expect(u.reducedMotion).toBe(true);
    expect(u.follow).toBe(1);
  });

  it("isMobile follows the 760px query when it is asked", async () => {
    const u = await util();
    expect(u.isMobile()).toBe(false);
    media.mobile = true;
    expect(u.isMobile()).toBe(true);
  });

  it("cssVar reads a custom property off the root, trimmed", async () => {
    const u = await util();
    document.documentElement.style.setProperty("--accent", "  #c40 ");
    expect(u.cssVar("--accent")).toBe("#c40");
    expect(u.cssVar("--nothing")).toBe("");
  });
});

describe("loading media", () => {
  const stubBlobURL = (made: Blob[], url: string) => {
    vi.spyOn(URL, "createObjectURL").mockImplementation((b) => { made.push(b as Blob); return url; });
  };

  it("fetchBlobURL reports progress as the body arrives and returns a blob URL", async () => {
    const made: Blob[] = [];
    if (!URL.createObjectURL) (URL as any).createObjectURL = () => "";
    stubBlobURL(made, "blob:x");
    const body = new ReadableStream<Uint8Array>({ start(c) { c.enqueue(new Uint8Array(30)); c.enqueue(new Uint8Array(70)); c.close(); } });
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, body, headers: new Headers({ "content-length": "100", "content-type": "video/mp4" }) })));
    const seen: number[] = [];
    expect(await fetchBlobURL("/a.mp4", (f) => seen.push(f))).toBe("blob:x");
    expect(seen).toEqual([0.3, 1]);
    expect(made[0].size).toBe(100);
    expect(made[0].type).toBe("video/mp4");
  });

  it("fetchBlobURL without a length falls back to one blob and a single 100% report", async () => {
    const made: Blob[] = [];
    if (!URL.createObjectURL) (URL as any).createObjectURL = () => "";
    stubBlobURL(made, "blob:y");
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, body: null, headers: new Headers(), blob: async () => new Blob(["abc"]) })));
    const seen: number[] = [];
    expect(await fetchBlobURL("/a.bin", (f) => seen.push(f), "video/mp4")).toBe("blob:y");
    expect(seen).toEqual([1]);
    expect(made).toHaveLength(1);
  });

  it("fetchBlobURL rejects on an HTTP error, naming the status and the URL", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 404, headers: new Headers() })));
    await expect(fetchBlobURL("/missing.mp4", () => {})).rejects.toThrow("404 /missing.mp4");
  });

  it("loadBitmap decodes off the main thread when it can, and hands back the image when it cannot", async () => {
    class FakeImage {
      decoding = ""; onload: (() => void) | null = null; onerror: (() => void) | null = null;
      set src(_: string) { queueMicrotask(() => this.onload?.()); }
    }
    vi.stubGlobal("Image", FakeImage);
    vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ bitmap: true })));
    expect(await loadBitmap("a.png")).toEqual({ bitmap: true });
    vi.stubGlobal("createImageBitmap", vi.fn(async () => { throw new Error("no"); }));
    expect(await loadBitmap("a.png")).toBeInstanceOf(FakeImage);
  });

  it("loadImage rejects when the image fails", async () => {
    class BadImage {
      decoding = ""; onload: (() => void) | null = null; onerror: (() => void) | null = null;
      set src(_: string) { queueMicrotask(() => this.onerror?.()); }
    }
    vi.stubGlobal("Image", BadImage);
    const { loadImage } = await import("../src/lib/util");
    await expect(loadImage("nope.png")).rejects.toThrow("failed to load nope.png");
  });
});

describe("theme tokens (window.__ssTheme)", () => {
  it("isMobile asks for 760 px unless theme.phone sets one width for the page", async () => {
    const asked: string[] = [];
    const real = window.matchMedia;
    vi.spyOn(window, "matchMedia").mockImplementation((q: string) => { asked.push(q); return real(q); });
    const plain = await fresh(() => import("../src/lib/util"));
    plain.isMobile();
    expect(asked.at(-1)).toBe("(max-width: 760px)");
    expect(plain.themeTokens).toEqual({});
    (globalThis as any).__ssTheme = { phone: 820, enter: 0.3 };
    try {
      const themed = await fresh(() => import("../src/lib/util"));
      themed.isMobile();
      expect(asked.at(-1)).toBe("(max-width: 820px)");
      expect(themed.themeTokens.enter).toBe(0.3);
    } finally {
      delete (globalThis as any).__ssTheme;
      vi.restoreAllMocks();
    }
  });
});
