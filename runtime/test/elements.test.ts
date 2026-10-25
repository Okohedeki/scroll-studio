/**
 * The element engine (lib/elements.ts): every scene's copy from the layout model the compiler writes (`.ss-layout`):
 * which step each element is, its window, and its motion; overlay captions by window, split/cards steps by where they sit.
 */
import { beforeEach, describe, expect, it } from "vitest";
import { box, screen } from "./helpers";
import { Elements, readElements, splitWords } from "../src/lib/elements";

const H = 800;
const layoutTag = (elements: object[]) => `<script type="application/json" class="ss-layout">${JSON.stringify({ elements })}</script>`;
function section(inner: string) {
  document.body.innerHTML = `<section>${inner}</section>`;
  return document.querySelector("section")!;
}
const steps = (n: number, over: object[] = []) => Array.from({ length: n }, (_, i) => ({ title: `s${i}`, length: 1, ...(over[i] ?? {}) }));
const states = (els: Elements) => els.captions.map((c) => ["ss-on", "ss-off"].filter((k) => c.el.classList.contains(k)).join("") || "idle");

beforeEach(() => screen({ w: 1280, h: H, y: 0 }));

describe("reading the layout model", () => {
  it("takes the compiler's elements, in page order, with each one's step and window", () => {
    const els = [{ step: 1, show: [0, 1] }, { step: 0, show: [0.2, 0.4], enter: "wipe" }];
    const sec = section(`<div class="ss-caption"></div><div class="ss-caption"></div>${layoutTag(els)}`);
    expect(readElements(sec, { steps: steps(2) })).toEqual(els);
  });

  it("without it, reads the steps in page order: windows from the markup, else from the section data, else the whole scene", () => {
    let sec = section(`<div class="ss-caption" data-from="0.1" data-to="0.3"></div><div class="ss-caption"></div>`);
    expect(readElements(sec, { steps: steps(2, [{}, { at: [0.5, 0.7] }]) })).toEqual([{ step: 0, show: [0.1, 0.3] }, { step: 1, show: [0.5, 0.7] }]);
    sec = section(`<article class="ss-step"></article><article class="ss-step"></article>`);
    expect(readElements(sec, { steps: steps(2) })).toEqual([{ step: 0, show: [0, 1] }, { step: 1, show: [0, 1] }]);
    sec = section(`<div class="ss-caption"></div><script type="application/json" class="ss-layout">not json</script>`);
    expect(readElements(sec, { steps: [] })).toEqual([{ step: 0, show: [0, 1] }]);
  });
});

describe("captions over a stage", () => {
  it("turn on inside their window and off after it, and the active step is the step, not the caption's place in the page", () => {
    // a caption placed with `at` is carried after the ones the layout places: step 0 is the second caption in the page
    const sec = section(`<div class="ss-caption" id="b"></div><div class="ss-caption" id="a"></div>${layoutTag([{ step: 1, show: [0.5, 0.7] }, { step: 0, show: [0.1, 0.3] }])}`);
    const els = new Elements(sec, { steps: steps(2) });
    expect(els.windows(0.05)).toBe(-1);
    expect(states(els)).toEqual(["idle", "idle"]);
    expect(els.windows(0.2)).toBe(0);
    expect(states(els)).toEqual(["idle", "ss-on"]);
    expect(els.windows(0.6)).toBe(1);
    expect(states(els)).toEqual(["ss-on", "ss-off"]);
    expect(els.windows(0.3)).toBe(0);                     // both ends of a window are inside it
    expect(els.windows(0.9)).toBe(-1);
    expect(states(els)).toEqual(["ss-off", "ss-off"]);
  });

  it("split their titles into words, each with the delay of its rise", () => {
    const sec = section(`<div class="ss-caption" data-from="0" data-to="1"><h2 class="ss-split-words">Cold <em>from</em> the source</h2></div>`);
    new Elements(sec, { steps: steps(1) });
    const words = [...sec.querySelectorAll<HTMLElement>(".ss-w > span")];
    expect(words.map((w) => w.textContent)).toEqual(["Cold", "from", "the", "source"]);
    expect(words[3].style.transitionDelay).toBe("0.195s");
    const typed = section(`<div class="ss-caption" data-enter="type-on"><h2 class="ss-split-words">One two three</h2></div>`);
    new Elements(typed, { steps: steps(1) });
    expect([...typed.querySelectorAll<HTMLElement>(".ss-w > span")].map((w) => w.style.transitionDelay)).toEqual(["0.060s", "0.170s", "0.280s"]);
    expect(splitWords(document.createElement("p"))).toBe(0);
  });
});

describe("steps in split and cards", () => {
  function cards(attrs: string[] = ["", ""]) {
    const sec = section(attrs.map((a, i) => `<article class="ss-step" id="st${i}"${a}><div class="ss-card"><h2 class="ss-h2">Step ${i} title</h2></div></article>`).join(""));
    return { sec, els: new Elements(sec, { steps: steps(attrs.length) }) };
  }

  it("each step's progress is how far the middle of the screen has gone through it; the scene's is their length-weighted average", () => {
    const { sec, els } = cards();
    box(sec.querySelector("#st0")!, H / 2 - 400, 400);    // passed
    box(sec.querySelector("#st1")!, H / 2 - 100, 400);    // a quarter through
    expect(els.measure([1, 3])).toEqual({ p: (0.14 + 0.14 * 0.25 * 3) / 4, active: 1 });   // eased 14% a frame
    for (let i = 0; i < 200; i++) els.measure([1, 3]);
    expect(els.measure([1, 3])).toEqual({ p: (1 + 0.25 * 3) / 4, active: 1 });              // then snaps
    expect(els.stepVals).toEqual([1, 0.25]);
    expect(els.lastActive).toBe(1);
    expect(sec.querySelector<HTMLElement>("#st1")!.style.getPropertyValue("--on")).toBe("1.000");
  });

  it("a step with its own motion also says how far it has entered and left; one without does not", () => {
    const { sec, els } = cards([` data-enter="rise"`, ""]);
    const [a, b] = [sec.querySelector<HTMLElement>("#st0")!, sec.querySelector<HTMLElement>("#st1")!];
    box(a, 0.9 * H, 1000); box(b, 2 * H, 1000);            // a's top just in at the bottom: entering starts
    els.measure([1, 1]);
    expect(a.style.getPropertyValue("--in")).toBe("0.000");
    expect(a.style.getPropertyValue("--out")).toBe("1.000");
    expect(b.style.getPropertyValue("--in")).toBe("");
    box(a, 0.725 * H, 1000);                               // half way from 90% to 55% down the screen
    els.measure([1, 1]);
    expect(a.style.getPropertyValue("--in")).toBe("0.500");
    box(a, 0.4 * H - 1000, 1000);                          // its bottom half way from 60% to 20%: half gone
    els.measure([1, 1]);
    expect(a.style.getPropertyValue("--in")).toBe("1.000");
    expect(a.style.getPropertyValue("--out")).toBe("0.500");
    expect(a.style.getPropertyValue("--on")).toBe("1.000");         // the emphasis every step has is unchanged
  });

  it("type-on splits a card's title into numbered words", () => {
    const { sec } = cards([` data-enter="type-on"`, ` data-exit="fade"`]);
    const a = sec.querySelector<HTMLElement>("#st0")!;
    expect(a.style.getPropertyValue("--n")).toBe("3");
    expect([...a.querySelectorAll<HTMLElement>(".ss-w > span")].map((w) => w.style.getPropertyValue("--i"))).toEqual(["0", "1", "2"]);
    expect(sec.querySelector("#st1 .ss-w")).toBeNull();
  });
});
