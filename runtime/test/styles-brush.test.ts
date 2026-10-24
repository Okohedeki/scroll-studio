/** The painted styles' toolkit: seeded random, value noise, colour conversions and the colour script. */
import { describe, expect, it } from "vitest";
import { clamp, colourScript, fbm, hash, hsl, lerp, lum, mix, parseColor, rgba, rng, smooth, themeColor, toHsl, vnoise, type RGB } from "../src/styles/_brush";

const near = (a: number[], b: number[], d = 6) => a.forEach((v, i) => expect(v).toBeCloseTo(b[i], d));

describe("maths", () => {
  it("clamp, lerp and smooth", () => {
    expect([clamp(-1), clamp(0.3), clamp(2), clamp(5, 1, 3)]).toEqual([0, 0.3, 1, 3]);
    expect(lerp(2, 4, 0.25)).toBe(2.5);
    expect(smooth(0, 1, 0.5)).toBe(0.5);
    expect(smooth(0, 1, -1)).toBe(0);
    expect(smooth(0, 1, 9)).toBe(1);
  });
});

describe("seeded random", () => {
  it("rng repeats for a seed, differs between seeds and stays in [0, 1)", () => {
    const a = rng(5), b = rng(5), c = rng(6);
    const xs = Array.from({ length: 8 }, () => a());
    expect(Array.from({ length: 8 }, () => b())).toEqual(xs);
    expect(Array.from({ length: 8 }, () => c())).not.toEqual(xs);
    const r = rng(99);
    let sum = 0;
    for (let i = 0; i < 2000; i++) { const v = r(); expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThan(1); sum += v; }
    expect(sum / 2000).toBeGreaterThan(0.45);
    expect(sum / 2000).toBeLessThan(0.55);
  });

  it("hash is a pure function of the index and the seed, in [0, 1)", () => {
    expect(hash(7)).toBe(hash(7));
    expect(hash(7)).not.toBe(hash(8));
    expect(hash(7, 1)).not.toBe(hash(7, 2));
    for (let i = -50; i < 50; i++) { const h = hash(i, 3); expect(h).toBeGreaterThanOrEqual(0); expect(h).toBeLessThan(1); }
  });
});

describe("noise", () => {
  it("vnoise is the hash itself on the lattice and smooth in between", () => {
    expect(vnoise(3, 4)).toBe(vnoise(3, 4));
    expect(vnoise(3, 4, 1)).not.toBe(vnoise(3, 4, 2));
    for (let x = 0; x < 6; x += 0.37) for (let y = 0; y < 6; y += 0.41) {
      const v = vnoise(x, y);
      expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThan(1);
      expect(Math.abs(vnoise(x + 0.001, y) - v)).toBeLessThan(0.02);       // continuous
    }
  });

  it("fbm stays in 0-1, repeats, and more octaves add detail without changing the range", () => {
    expect(fbm(1.5, 2.5, 1)).toBe(fbm(1.5, 2.5, 1));
    for (let i = 0; i < 100; i++) { const v = fbm(i * 0.31, i * 0.17, 2, 4); expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThanOrEqual(1); }
    expect(fbm(0.3, 0.7, 0, 1)).not.toBe(fbm(0.3, 0.7, 0, 3));
  });
});

describe("colour", () => {
  it("hsl: the primaries, greys, hue wrapping and clamped saturation and lightness", () => {
    near(hsl(0, 1, 0.5), [255, 0, 0]);
    near(hsl(120, 1, 0.5), [0, 255, 0]);
    near(hsl(240, 1, 0.5), [0, 0, 255]);
    near(hsl(60, 1, 0.5), [255, 255, 0]);
    near(hsl(200, 0, 0.4), [102, 102, 102]);
    near(hsl(-120, 1, 0.5), hsl(240, 1, 0.5));
    near(hsl(480, 1, 0.5), hsl(120, 1, 0.5));
    near(hsl(0, 5, 2), [255, 255, 255]);
    near(hsl(0, 1, 0), [0, 0, 0]);
  });

  it("toHsl is hsl's inverse, and a grey has no hue or saturation", () => {
    for (const c of [[200, 40, 30], [10, 220, 90], [50, 60, 250], [128, 128, 20]] as RGB[]) {
      const [h, s, l] = toHsl(c);
      near(hsl(h, s, l), c, 4);
    }
    expect(toHsl([90, 90, 90])).toEqual([0, 0, 90 / 255]);
    expect(toHsl([255, 0, 0])[0]).toBe(0);
    expect(toHsl([0, 255, 0])[0]).toBeCloseTo(120, 9);
    expect(toHsl([0, 0, 255])[0]).toBeCloseTo(240, 9);
  });

  it("mix, rgba and lum", () => {
    expect(mix([0, 100, 200], [100, 200, 0], 0.5)).toEqual([50, 150, 100]);
    expect(rgba([10.4, 20.6, 30], 0.5)).toBe("rgba(10,21,30,0.5)");
    expect(rgba([1, 2, 3])).toBe("rgba(1,2,3,1)");
    expect(lum([255, 255, 255])).toBeCloseTo(1, 12);
    expect(lum([0, 0, 0])).toBe(0);
    expect(lum([0, 255, 0])).toBeGreaterThan(lum([255, 0, 0]));       // green reads brighter than red
  });

  it("parseColor reads hex (3, 6 and 8 digits), rgb() and rgba()", () => {
    expect(parseColor("#fff")).toEqual([255, 255, 255]);
    expect(parseColor("#1a2b3c")).toEqual([26, 43, 60]);
    expect(parseColor("  #1A2B3C  ")).toEqual([26, 43, 60]);
    expect(parseColor("#11223344")).toEqual([17, 34, 51]);            // the alpha is dropped
    expect(parseColor("rgb(10, 20, 30)")).toEqual([10, 20, 30]);
    expect(parseColor("rgba(10 20 30 / .5)")).toEqual([10, 20, 30]);
  });

  it("parseColor asks the browser for any other colour (a name), and falls back for what it cannot read", () => {
    expect(parseColor("red")).toEqual([255, 0, 0]);
    expect(parseColor("black")).toEqual([0, 0, 0]);
    expect(parseColor("not a colour")).toEqual([200, 160, 90]);
    expect(parseColor("", [1, 2, 3])).toEqual([1, 2, 3]);
    expect(parseColor(undefined as unknown as string, [4, 5, 6])).toEqual([4, 5, 6]);
  });

  it("themeColor reads a custom property of the page as a colour, with a fallback", () => {
    document.documentElement.style.setProperty("--accent", "#336699");
    expect(themeColor("--accent", [0, 0, 0])).toEqual([51, 102, 153]);
    expect(themeColor("--nothing", [9, 8, 7])).toEqual([9, 8, 7]);
  });
});

describe("colourScript", () => {
  const accent: RGB = [200, 80, 40];

  it("makes one palette per scene, repeatably", () => {
    expect(colourScript(5, accent)).toHaveLength(5);
    expect(colourScript(0, accent)).toEqual([]);
    expect(colourScript(1, accent)).toHaveLength(1);
    expect(colourScript(4, accent)).toEqual(colourScript(4, accent));
  });

  it("anchors the glow on the site's own accent hue, which `spread` lets drift", () => {
    const h0 = toHsl(accent)[0];
    expect(colourScript(3, accent)[0].hue).toBeCloseTo(h0 + Math.sin(0.7) * 55, 9);
    for (const p of colourScript(6, accent, 0)) expect(p.hue).toBeCloseTo(h0, 9);
    const wide = colourScript(6, accent, 2).map((p) => p.hue), narrow = colourScript(6, accent, 0.5).map((p) => p.hue);
    expect(Math.max(...wide) - Math.min(...wide)).toBeGreaterThan(Math.max(...narrow) - Math.min(...narrow));
  });

  it("every colour of every palette is a valid 0-255 triple", () => {
    for (const day of [0, 0.25, 0.8]) for (const p of colourScript(7, accent, 1.3, day)) {
      for (const k of ["skyTop", "skyLow", "glow", "far", "mid", "near", "deep", "accent", "light"] as const) {
        expect(p[k]).toHaveLength(3);
        for (const v of p[k]) { expect(Number.isFinite(v)).toBe(true); expect(v).toBeGreaterThanOrEqual(-1e-9); expect(v).toBeLessThanOrEqual(255 + 1e-9); }
      }
    }
  });

  it("planes recede into mist: the near plane is darker than the mid, which is darker than the far", () => {
    for (const p of colourScript(6, accent)) {
      expect(lum(p.near)).toBeLessThan(lum(p.mid));
      expect(lum(p.mid)).toBeLessThan(lum(p.far));
      expect(lum(p.deep)).toBeLessThan(lum(p.near));
    }
  });

  it("the glow is the lightest of the scene's own colours, and the light lighter still", () => {
    for (const p of colourScript(6, accent)) {
      expect(lum(p.light)).toBeGreaterThan(lum(p.glow));
      expect(lum(p.glow)).toBeGreaterThan(lum(p.skyTop));
    }
  });
});
