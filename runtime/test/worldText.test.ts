/** Type for the world: typesetting a title into blocks, and choosing ink that reads on footage. Text is measured at half an em per character. */
import { describe, expect, it } from "vitest";
import { contrastOf, contrastWith, inkFor, layout, PAD, probeStyle, rasterize, rgbOf, words, type LayoutOpts, type WorldStyle } from "../src/lib/worldText";
import type { FakeContext } from "./setup";

const st: WorldStyle = {
  family: "Serif", weight: 500, emItalic: true, emColor: "#ff0000", accent: "#ff0000",
  light: "#ffffff", dark: "#000000", ink: "#ffffff", paper: "#000000", tracking: 0, lead: 1,
};
const opts = (o: Partial<LayoutOpts> = {}): LayoutOpts => ({ size: 1, hMax: 10, caps: false, track: 0, weight: 500, align: "center", ...o });

describe("words", () => {
  it("splits into words and carries emphasis across the words it covers", () => {
    expect(words("Cold from <em>the source.</em>")).toEqual([
      { text: "Cold", em: false }, { text: "from", em: false }, { text: "the", em: true }, { text: "source.", em: true },
    ]);
  });

  it("drops other tags, decodes the entities the build writes, and collapses whitespace", () => {
    expect(words("A&nbsp;&amp;  <i>B</i> C &lt;D&gt;").map((w) => w.text)).toEqual(["A", "&", "B", "C", "<D>"]);
  });

  it("is empty for empty markup", () => {
    expect(words("")).toEqual([]);
    expect(words("<em></em>")).toEqual([]);
  });
});

describe("rgbOf", () => {
  it("reads any colour form as 0-1 channels", () => {
    expect(rgbOf("#ffffff")).toEqual([1, 1, 1]);
    expect(rgbOf("#f00")).toEqual([1, 0, 0]);
    expect(rgbOf("rgb(0, 51, 255)")).toEqual([0, 0.2, 1]);
  });
});

describe("contrast", () => {
  it("contrastOf is the WCAG ratio against footage of a given tone", () => {
    expect(contrastOf("#ffffff", 0)).toBeCloseTo(21, 6);
    expect(contrastOf("#000000", 1)).toBeCloseTo(21, 6);
    expect(contrastOf("#ffffff", 1)).toBeCloseTo(1, 6);
  });

  it("inkFor picks whichever of the theme's light and dark reads better", () => {
    expect(inkFor(0.05, st)).toBe(st.light);
    expect(inkFor(0.9, st)).toBe(st.dark);
  });

  it("contrastWith keeps a colour that reads and swaps one that would vanish into the footage", () => {
    expect(contrastWith("#ff0000", 0, st)).toBe("#ff0000");
    const grey = Math.pow(0.5, 1 / 2.2);   // footage whose luminance equals mid grey #808080's
    expect(contrastWith("#bbbbbb", 0.75, st)).toBe(st.dark);
    expect(contrastWith("#7f7f7f", grey, st)).not.toBe("#7f7f7f");
  });
});

describe("layout", () => {
  // four words of two letters: 100 at 100px each (1 em), a space is half an em
  it("uses as many lines as fit under the height limit: more lines make larger type for the same width", () => {
    const l = layout("aa bb cc dd", st, opts({ hMax: 10 }));
    expect(l.lines).toHaveLength(4);
    expect(l.fs).toBeCloseTo(1, 12);
    expect(l.wPlane).toBeCloseTo(1, 12);
    expect(l.hPlane).toBeCloseTo(4, 12);
    expect(l.aspect).toBeCloseTo(0.25, 12);
  });

  it("stops adding lines once the block would stand too tall", () => {
    const l = layout("aa bb cc dd", st, opts({ hMax: 1.5 }));
    expect(l.lines).toHaveLength(3);
    expect(l.fs).toBeCloseTo(0.4, 12);
    expect(l.hPlane).toBeCloseTo(1.2, 12);
  });

  it("balances the lines: the narrowest widest line", () => {
    const l = layout("aa bb cc dd", st, opts({ lines: 2 }));
    expect(l.lines.map((line) => line.map((w) => w.text))).toEqual([["aa", "bb"], ["cc", "dd"]]);
    expect(l.wPlane).toBeCloseTo(1, 12);
  });

  it("`lines` fixes the number of lines, however tall that is", () => {
    const l = layout("aa bb cc dd", st, opts({ lines: 1, hMax: 100 }));
    expect(l.lines).toHaveLength(1);
    expect(l.fs).toBeCloseTo(1 / 5.5, 12);
  });

  it("cuts the type down to fit when even one line is too tall", () => {
    const l = layout("aa bb cc dd", st, opts({ hMax: 0.1 }));
    expect(l.lines).toHaveLength(1);
    expect(l.hPlane).toBeCloseTo(0.1, 12);
    expect(l.wPlane).toBeLessThan(1);
    expect(l.aspect).toBeCloseTo(l.wPlane / l.hPlane, 12);
  });

  it("never makes more lines than words", () => {
    expect(layout("aa bb", st, opts({ hMax: 100 })).lines).toHaveLength(2);
    expect(layout("aa", st, opts({ hMax: 100 })).lines).toHaveLength(1);
    expect(layout("aa", st, opts({ lines: 4, hMax: 100 })).lines).toHaveLength(1);
  });

  it("capitals take a little more leading", () => {
    const plain = layout("aa bb", st, opts({ lines: 2 }));
    const caps = layout("aa bb", st, opts({ lines: 2, caps: true }));
    expect(caps.hPlane / plain.hPlane).toBeCloseTo(1.04, 12);
  });

  it("tracking widens the words", () => {
    const tight = layout("aa bb", st, opts({ lines: 1 })), loose = layout("aa bb", st, opts({ lines: 1, track: 0.1 }));
    expect(loose.fs).toBeLessThan(tight.fs);
  });
});

describe("rasterize", () => {
  const item = (html: string, o: Partial<Parameters<typeof rasterize>[0][number]> = {}) => ({
    layout: layout(html, st, opts({ lines: 2 })), px: 400, colors: (em: boolean) => (em ? "#ff0000" : "#ffffff"),
    weight: 500, track: 0, caps: false, align: "center", st, ...o,
  });

  it("stacks each title's cell down one atlas, each as wide as its block plus padding on both sides", () => {
    const r = rasterize([item("aa bb"), item("cc dd")]);
    expect(r.cells).toHaveLength(2);
    expect(r.canvas.width).toBe(Math.round(400 * (1 + 2 * PAD)));
    expect(r.cells[0].y).toBe(0);
    expect(r.cells[1].y).toBeGreaterThan(r.cells[0].y + r.cells[0].h - 1e-9);
    expect(r.cells[0].w).toBeCloseTo(1, 12);
    for (const c of r.cells) expect(c.y + c.h).toBeLessThanOrEqual(1 + 1e-9);
  });

  it("draws every word, in the colour of its emphasis, in capitals when asked", () => {
    const r = rasterize([item("aa <em>bb</em>", { caps: true })]);
    const g = r.canvas.getContext("2d") as unknown as FakeContext;
    const drawn = g.calls.filter(([n]) => n === "fillText").map(([, t]) => t);
    expect(drawn).toEqual(["AA", "BB"]);
    expect(g.fillStyle).toBe("#ff0000");     // the last word drawn was the emphasised one
  });

  it("shrinks everything to fit the largest texture the device allows", () => {
    const small = rasterize([item("aa bb", { px: 100 }), item("cc dd", { px: 100 }), item("ee ff", { px: 100 })], 400);
    expect(small.canvas.width).toBeLessThanOrEqual(400);
    expect(small.canvas.height).toBeLessThanOrEqual(400);
    expect(small.cells[2].y + small.cells[2].h).toBeLessThanOrEqual(1 + 1e-9);
  });

  it("but never below a quarter of the size asked for: a limit it cannot meet is overrun rather than drawn illegibly small", () => {
    const r = rasterize([item("aa bb"), item("cc dd"), item("ee ff")], 100);
    const asked = Math.round(400 * (1 + 2 * PAD));
    expect(r.canvas.width / asked).toBeGreaterThan(0.2);
    expect(r.canvas.width / asked).toBeLessThanOrEqual(0.25);
  });
});

describe("probeStyle", () => {
  it("reads the page's display type and colours from a probe placed in the section, and removes the probe", () => {
    document.documentElement.style.setProperty("--ink", "#101010");
    document.documentElement.style.setProperty("--bg", "#f0f0f0");
    document.documentElement.style.setProperty("--accent", "#c04000");
    const host = document.createElement("section");
    document.body.appendChild(host);
    const s = probeStyle(host);
    expect(host.children).toHaveLength(0);
    expect(s.ink).toBe("#101010");
    expect(s.paper).toBe("#f0f0f0");
    expect(s.accent).toBe("#c04000");
    // the lighter of ink and background is the light ink
    expect(s.light).toBe("#f0f0f0");
    expect(s.dark).toBe("#101010");
    expect(s.lead).toBeGreaterThan(0);
    expect(s.weight).toBeGreaterThan(0);
  });

  it("on a dark theme the ink is the light one", () => {
    document.documentElement.style.setProperty("--ink", "#eeeeee");
    document.documentElement.style.setProperty("--bg", "#111111");
    const host = document.createElement("section");
    document.body.appendChild(host);
    const s = probeStyle(host);
    expect(s.light).toBe("#eeeeee");
    expect(s.dark).toBe("#111111");
  });
});
