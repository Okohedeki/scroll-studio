/** type: kinetic typography driven by scroll, in its five modes. */
import { afterEach, describe, expect, it } from "vitest";
import { easeInOut } from "../src/lib/util";
import { frameState, playerCtx } from "./helpers";

afterEach(() => history.replaceState(null, "", "/"));

async function mount(cfg: Record<string, unknown>) {
  const { default: factory } = await import("../src/players/type");
  const ctx = playerCtx();
  const player = await factory(cfg, ctx);
  const box = ctx.visual.querySelector<HTMLElement>(".ss-type")!;
  return { player, box, text: box.querySelector<HTMLElement>(".ss-type__text")! };
}

describe("type: reveal", () => {
  it("lights up the words in reading order as the scroll goes from 8% to 88%", async () => {
    const { player, text, box } = await mount({ mode: "reveal", text: "one <em>two three</em> four" });
    expect(box.className).toBe("ss-type ss-type--reveal");
    const spans = [...text.querySelectorAll<HTMLElement>(":scope > span")];
    expect(spans).toHaveLength(4);
    expect(spans[1].innerHTML).toBe("<em>two</em>");     // an accent covering several words is one <em> per word
    const on = () => spans.filter((s) => s.classList.contains("on")).length;
    player.update(frameState(0));
    expect(on()).toBe(0);
    player.update(frameState(0.48));
    expect(on()).toBe(2);
    player.update(frameState(0.88));
    expect(on()).toBe(4);
    player.update(frameState(1));
    expect(on()).toBe(4);
    player.update(frameState(0.2));                        // scrolling back puts them out again
    expect(on()).toBe(1);
  });
});

describe("type: stack", () => {
  it("brings lines in one after another from alternating sides", async () => {
    const { player, text } = await mount({ mode: "stack", text: "", lines: ["alpha", "beta", "gamma"] });
    const lines = [...text.querySelectorAll<HTMLElement>(".ln")];
    expect(lines.map((l) => l.textContent)).toEqual(["alpha", "beta", "gamma"]);
    player.update(frameState(0));
    expect(lines.map((l) => l.style.opacity)).toEqual(["0", "0", "0"]);
    expect(lines[0].style.transform).toBe("translate3d(-8vw, 0, 0) skewX(-8deg)");
    expect(lines[1].style.transform).toBe("translate3d(8vw, 0, 0) skewX(-8deg)");
    player.update(frameState(1));
    expect(lines.map((l) => l.style.opacity)).toEqual(["1", "1", "1"]);
    expect(lines[1].style.transform).toBe("translate3d(0vw, 0, 0) skewX(0deg)");
    // the first line is complete before the last has started
    player.update(frameState(0.25));
    expect(+lines[0].style.opacity).toBe(1);
    expect(+lines[2].style.opacity).toBe(0);
  });

  it("without a list of lines the text is split on ' / ' or newlines", async () => {
    const { text } = await mount({ mode: "stack", text: "one / two\nthree" });
    expect([...text.querySelectorAll(".ln")].map((l) => l.textContent)).toEqual(["one", "two", "three"]);
  });
});

describe("type: swap", () => {
  it("rolls a word through a list, holding each, then moving to the next in the last 40% of its slot", async () => {
    const { player, text } = await mount({ mode: "swap", text: "Built for", words: ["makers", "dreamers", "doers"] });
    const roll = text.querySelector<HTMLElement>(".roll")!;
    const items = [...roll.querySelectorAll<HTMLElement>("i")];
    expect(text.firstChild!.textContent).toBe("Built for ");
    expect(items.map((i) => i.textContent)).toEqual(["makers", "dreamers", "doers"]);
    const y = () => items[0].style.transform;
    player.update(frameState(0));
    expect(y()).toBe("translateY(0%)");
    player.update(frameState(0.5));       // f = 1.1: the second word, still held
    expect(y()).toBe("translateY(-100%)");
    player.update(frameState(0.4));       // f = 0.88: on its way from the first to the second
    expect(parseFloat(y().replace("translateY(", ""))).toBeCloseTo(-easeInOut(0.7) * 100, 9);
    player.update(frameState(1));         // the last word
    expect(y()).toBe("translateY(-200%)");
  });

  it("an empty list shows a dash rather than nothing", async () => {
    const { text } = await mount({ mode: "swap", text: "Hello", words: [] });
    expect(text.querySelector(".roll i")!.textContent).toBe("—");
  });

  it("sizes the roll to its widest word and measures again on resize", async () => {
    const { player, text } = await mount({ mode: "swap", text: "x", words: ["a", "bbb"] });
    const roll = text.querySelector<HTMLElement>(".roll")!;
    expect(roll.style.width).toBe("32px");       // the widest word, plus 2px
    roll.style.width = "";
    player.resize!();
    expect(roll.style.width).toBe("32px");
  });
});

describe("type: scale", () => {
  it("starts enormous, settles by the half-way point, then breaks apart", async () => {
    const { player, text } = await mount({ mode: "scale", text: "Big bang" });
    const chars = [...text.querySelectorAll<HTMLElement>(".ch")];
    expect(chars).toHaveLength(8);
    expect(chars[3].innerHTML).toBe("&nbsp;");        // a space is kept as one, so it still takes room
    player.update(frameState(0));
    expect(text.style.transform).toBe("scale(2.6)");
    player.update(frameState(0.25));
    expect(text.style.transform).toBe(`scale(${2.6 - 1.6 * easeInOut(0.5)})`);
    player.update(frameState(0.5));
    expect(text.style.transform).toBe("scale(1)");
    expect(chars[0].style.opacity).toBe("1");          // whole until 70%
    player.update(frameState(1));
    expect(chars[0].style.opacity).toBe("0");
    expect(chars[0].style.transform).toContain("translate3d(-40vw");   // the first flies left, the last right
    expect(chars[7].style.transform).toContain("translate3d(40vw");
  });
});

describe("type: weight", () => {
  it("fattens words from thin to heavy in reading order", async () => {
    const { player, text } = await mount({ mode: "weight", text: "one two three / four", weights: [100, 900] });
    const words = [...text.querySelectorAll<HTMLElement>(".w")];
    expect(words).toHaveLength(4);
    expect(text.querySelectorAll(".ln")).toHaveLength(2);       // a slash starts a new line, kept whole
    player.update(frameState(0));
    expect(words.map((w) => w.style.fontWeight)).toEqual(["100", "100", "100", "100"]);
    expect(+words[0].style.opacity).toBeCloseTo(0.28, 12);
    player.update(frameState(1));
    expect(words.map((w) => w.style.fontWeight)).toEqual(["900", "900", "900", "900"]);
    expect(words[0].style.opacity).toBe("1");
    player.update(frameState(0.5));
    const ws = words.map((w) => +w.style.fontWeight);
    expect(ws).toEqual([...ws].sort((a, b) => b - a));          // heavier the earlier the word
    expect(ws[0]).toBe(900);
    expect(ws[3]).toBeLessThan(900);
  });

  it("defaults to weights 200-800", async () => {
    const { player, text } = await mount({ mode: "weight", text: "one two" });
    player.update(frameState(0));
    expect((text.querySelector(".w") as HTMLElement).style.fontWeight).toBe("200");
    player.update(frameState(1));
    expect((text.querySelector(".w") as HTMLElement).style.fontWeight).toBe("800");
  });

  it("measuring again keeps the current progress", async () => {
    const { player, text } = await mount({ mode: "weight", text: "one two" });
    player.update(frameState(1));
    player.resize!();
    expect((text.querySelector(".w") as HTMLElement).style.fontWeight).toBe("800");
  });
});
