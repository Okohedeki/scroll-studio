/**
 * A style's own experience (runtime/src/styles/<style>.ts): its scroll mechanics and interactions, run against a small page
 * built the way the style's templates build one. Two styles in depth (neo-brutalism's desk and kinetic-type's reading
 * pin), and every style against a bare page, with and without reduced motion.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { atPage, box, frames, html, moveTo, screen } from "./helpers";

type Observed = { cb: (es: unknown[]) => void; targets: Element[]; opts: unknown };
let observers: Observed[] = [];
function stubIntersectionObserver() {
  observers = [];
  vi.stubGlobal("IntersectionObserver", class {
    o: Observed;
    constructor(cb: Observed["cb"], opts: unknown) { this.o = { cb, targets: [], opts }; observers.push(this.o); }
    observe(el: Element) { this.o.targets.push(el); }
    unobserve(el: Element) { this.o.targets = this.o.targets.filter((t) => t !== el); }
    disconnect() { this.o.targets = []; }
  });
}
beforeEach(() => { vi.useFakeTimers(); screen({ w: 1280, h: 800, y: 0 }); });
afterEach(() => vi.unstubAllGlobals());

async function start(style: string, o: { reduced?: boolean } = {}) {
  const f = frames();
  const mod = await atPage(() => import(`../src/styles/${style}.ts`), o);
  (mod as { default: () => void }).default();
  return f;
}
const hit = (target: Element, over: Record<string, unknown> = {}) => ({ target, isIntersecting: true, boundingClientRect: { bottom: 500 }, ...over });

// ---------------------------------------------------------------------------------------------------------------- neo-brutalism
describe("neo-brutalism: a desk you fill up", () => {
  const MARKS = ["#ffc900", "#b8ff5c", "#ff90e8"];
  const page = `<main>
    <section class="nb-hero"><h1 data-nb-words>Make <em>bold</em> things</h1><div data-nb-slap="last" id="badge"></div></section>
    <section id="feat"><div data-nb-slap id="t1"></div><div data-nb-slap id="t2"></div><div data-nb-slap id="t3"></div></section>
  </main>`;

  it("sets the headline word by word on marker blocks, which land one after another, and the sticker last", async () => {
    html(page);
    stubIntersectionObserver();
    await start("neo-brutalism");
    expect(document.documentElement.classList.contains("nb-js")).toBe(true);
    const h1 = document.querySelector("h1")!;
    const words = [...h1.querySelectorAll<HTMLElement>(".nb-word")];
    expect(words.map((w) => w.textContent)).toEqual(["Make", "bold", "things"]);
    expect(words[1].querySelector(".nb-txt")!.innerHTML).toBe("<em>bold</em>");
    expect(words.map((w) => w.style.getPropertyValue("--c"))).toEqual(MARKS);
    expect(h1.getAttribute("aria-label")).toBe("Make bold things");        // the page still says it
    expect(words.every((w) => w.getAttribute("aria-hidden") === "true")).toBe(true);
    const down = () => words.filter((w) => w.classList.contains("is-down")).length;
    expect(down()).toBe(0);
    vi.advanceTimersByTime(150); expect(down()).toBe(1);
    vi.advanceTimersByTime(150); expect(down()).toBe(2);
    vi.advanceTimersByTime(150); expect(down()).toBe(3);
    const badge = document.getElementById("badge")!;
    expect(badge.classList.contains("is-down")).toBe(false);
    vi.advanceTimersByTime(260 + 150);
    expect(badge.classList.contains("is-down")).toBe(true);            // the sticker whacks on once the words are down
  });

  it("slaps a thing on when it crosses the threshold, staggering the ones that arrive together, and it stays", async () => {
    html(page);
    stubIntersectionObserver();
    await start("neo-brutalism");
    const io = observers[0];
    expect(io.targets.map((t) => t.id)).toEqual(["t1", "t2", "t3"]);       // the sticker belongs to the headline, not here
    const [t1, t2, t3] = ["t1", "t2", "t3"].map((id) => document.getElementById(id)!);
    io.cb([hit(t1), hit(t2), hit(t3)]);
    expect(io.targets).toEqual([]);                                        // each is watched until it has landed
    vi.advanceTimersByTime(0);
    expect([t1, t2, t3].map((t) => t.classList.contains("is-down"))).toEqual([true, false, false]);
    vi.advanceTimersByTime(85);
    expect([t1, t2, t3].map((t) => t.classList.contains("is-down"))).toEqual([true, true, false]);
    vi.advanceTimersByTime(85);
    expect(t3.classList.contains("is-down")).toBe(true);
  });

  it("a thing already scrolled past is simply there; one that is below the screen is left alone", async () => {
    html(page);
    stubIntersectionObserver();
    await start("neo-brutalism");
    const [t1, t2] = ["t1", "t2"].map((id) => document.getElementById(id)!);
    observers[0].cb([hit(t1, { isIntersecting: false, boundingClientRect: { bottom: -50 } }), hit(t2, { isIntersecting: false, boundingClientRect: { bottom: 1500 } })]);
    expect(t1.classList.contains("is-down")).toBe(true);                   // at once, with no timers run
    vi.advanceTimersByTime(1000);
    expect(t2.classList.contains("is-down")).toBe(false);
    expect(observers[0].targets.map((t) => t.id)).toContain("t2");        // and still watched
  });

  it("with reduced motion everything is already on the desk", async () => {
    html(page);
    stubIntersectionObserver();
    await start("neo-brutalism", { reduced: true });
    expect(document.documentElement.classList.contains("nb-js")).toBe(false);
    expect(document.getElementById("badge")!.classList.contains("is-down")).toBe(true);
    expect(document.querySelectorAll(".nb-word")).toHaveLength(0);          // the headline is left as it is
  });

  describe("the deck: each feature card slaps on top of the last", () => {
    const deck = `<section data-nb-deck id="deck"><p data-nb-count></p><div data-nb-card id="c0"></div><div data-nb-card id="c1"></div><div data-nb-card id="c2"></div></section>`;

    it("is pinned for a screen plus 0.62 of a screen a card, and lands a card once its step is 0.2 in", async () => {
      html(`<main>${deck}</main>`);
      stubIntersectionObserver();
      const f = await start("neo-brutalism");
      expect(document.documentElement.classList.contains("nb-deck-on")).toBe(true);
      const track = document.querySelector<HTMLElement>(".sx-track")!;
      expect(track.style.height).toBe("286svh");
      box(track, 0, 3000);
      const cards = [0, 1, 2].map((i) => document.getElementById("c" + i)!);
      const count = document.querySelector("[data-nb-count]")!;
      const at = (p: number) => { moveTo(track, -p * 2200); f.step(); return [cards.filter((c) => c.classList.contains("is-down")).length, count.textContent]; };
      expect(at(0)).toEqual([0, "0"]);
      expect(at(0.1)).toEqual([1, "1"]);              // step 0.3
      expect(at(0.5)).toEqual([2, "2"]);              // step 1.5
      expect(at(1)).toEqual([3, "3"]);
      expect(at(0)).toEqual([3, "3"]);                // scrolling back does not undo them: the page accumulates
    });

    it("is not used on a narrow screen, where the cards slap by threshold like everything else", async () => {
      html(`<main>${deck}</main>`);
      stubIntersectionObserver();
      vi.spyOn(window, "matchMedia").mockImplementation((q: string) => ({ matches: /max-width:\s*900px/.test(q), media: q, addEventListener() {}, removeEventListener() {} }) as MediaQueryList);
      await start("neo-brutalism");
      expect(document.documentElement.classList.contains("nb-deck-on")).toBe(false);
      expect(observers[0].targets.map((t) => t.id)).toEqual(["c0", "c1", "c2"]);
    });
  });

  it("things marked draggable can be nudged with the arrow keys (12px, 40 with shift) and kept inside their section", async () => {
    html(`<main><section id="s"><div data-nb-drag id="win" tabindex="0"></div></section></main>`);
    stubIntersectionObserver();
    await start("neo-brutalism");
    const s = document.getElementById("s")!, win = document.getElementById("win")!;
    box(s, 0, 600, { left: 0, width: 1000 });
    const dx = () => parseFloat(win.style.getPropertyValue("--dx") || "0");
    // it sits at left 100, 200 wide, 100 high, and moves with its own --dx/--dy like the real element does
    win.getBoundingClientRect = () => ({ left: 100 + dx(), top: 100 + parseFloat(win.style.getPropertyValue("--dy") || "0"), width: 200, height: 100,
      right: 300, bottom: 200, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    const key = (k: string, shift = false) => win.dispatchEvent(new KeyboardEvent("keydown", { key: k, shiftKey: shift, bubbles: true, cancelable: true }));
    key("ArrowRight");
    expect(win.style.getPropertyValue("--dx")).toBe("12.0px");
    key("ArrowRight", true);
    expect(win.style.getPropertyValue("--dx")).toBe("52.0px");
    key("ArrowUp");
    expect(win.style.getPropertyValue("--dy")).toBe("-12.0px");
    // the section's right edge less 60% of its width is 780; the element's box is read before the move is written, so it can
    // overshoot by the one step that was in flight
    for (let i = 0; i < 40; i++) key("ArrowRight", true);
    const right = dx();
    expect(right).toBeGreaterThanOrEqual(780); expect(right).toBeLessThanOrEqual(780 + 40);
    key("ArrowRight", true);
    expect(dx()).toBe(right);                                            // it stops there
    for (let i = 0; i < 40; i++) key("ArrowLeft", true);
    const left = dx();
    expect(left).toBeLessThanOrEqual(-180); expect(left).toBeGreaterThanOrEqual(-180 - 40);   // the left edge less 40% of its width
    key("ArrowLeft", true);
    expect(dx()).toBe(left);
    const ev = new KeyboardEvent("keydown", { key: "a", bubbles: true, cancelable: true });
    win.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(false);                             // other keys are left alone
  });

  it("a marquee band runs on scroll velocity, against its own direction, wrapping seamlessly, and holds while the pointer is on it", async () => {
    html(`<main><div data-nb-band="-1" id="band"><div class="nb-band__row"><span>go </span></div></div></main>`);
    stubIntersectionObserver();
    const row = document.querySelector<HTMLElement>(".nb-band__row")!;
    Object.defineProperty(row, "scrollWidth", { configurable: true, value: 600 });
    const band = document.getElementById("band")!;
    box(band, 100, 60);
    const f = await start("neo-brutalism");
    expect(row.children).toHaveLength(2);                               // the row is doubled so it can wrap
    f.step(16); f.step(16);
    const x1 = parseFloat(/translate3d\((-?[\d.]+)px/.exec(row.style.transform)![1]);
    expect(x1).toBeLessThan(0); expect(x1).toBeGreaterThan(-300);
    for (let i = 0; i < 200; i++) f.step(16);
    const x2 = parseFloat(/translate3d\((-?[\d.]+)px/.exec(row.style.transform)![1]);
    expect(x2).toBeLessThanOrEqual(0); expect(x2).toBeGreaterThan(-300);   // always inside one repeat
    band.dispatchEvent(new Event("pointerenter"));
    for (let i = 0; i < 300; i++) f.step(16);
    const held = row.style.transform;
    f.step(16);
    expect(row.style.transform).toBe(held);                               // stopped, give or take rounding
  });

  it("a click on a confetti button bursts 40 flat pieces from it, and nothing with reduced motion", async () => {
    // (document-level listeners from the styles started in earlier tests are still there, so call this page's own)
    for (const reduced of [false, true]) {
      html(`<main><button data-nb-confetti id="go">Go</button></main>`);
      stubIntersectionObserver();
      const add = vi.spyOn(document, "addEventListener");
      await start("neo-brutalism", { reduced });
      const click = add.mock.calls.find(([type]) => type === "click")![1] as (e: unknown) => void;
      const go = document.getElementById("go")!;
      box(go, 100, 40, { left: 100, width: 80 });
      click({ target: go });
      const pieces = document.querySelectorAll<HTMLElement>(".nb-confetti");
      expect(pieces).toHaveLength(reduced ? 0 : 40);
      if (!reduced) {
        expect(pieces[0].style.left).toBe("140px");                       // from the middle of the button
        expect(pieces[0].style.top).toBe("120px");
        expect(new Set([...pieces].map((p) => p.style.background)).size).toBeGreaterThan(3);
      }
      add.mockRestore();
    }
  });

  it("marks the nav chip of the section that has reached the middle of the screen", async () => {
    html(`<nav><a data-nb-nav href="#one" id="a1"></a><a data-nb-nav href="#two" id="a2"></a></nav><main><section id="one"></section><section id="two"></section></main>`);
    stubIntersectionObserver();
    const f = await start("neo-brutalism");
    box(document.getElementById("one")!, -100, 700); box(document.getElementById("two")!, 600, 700);
    f.step();
    expect([...document.querySelectorAll("a")].map((a) => a.classList.contains("is-current"))).toEqual([true, false]);
    moveTo(document.getElementById("two")!, 300);
    f.step();
    expect([...document.querySelectorAll("a")].map((a) => a.classList.contains("is-current"))).toEqual([false, true]);
  });
});

// ---------------------------------------------------------------------------------------------------------------- kinetic-type
describe("kinetic-type: the sentence is read word by word", () => {
  const page = `<main><section data-kt-read id="intro"><h2 class="kt-read">One two three four</h2><p class="kt-intro__body">body</p><div class="kt-btns"></div></section></main>`;
  const setup = async (o: { reduced?: boolean } = {}) => {
    html(page);
    stubIntersectionObserver();
    return start("kinetic-type", o);
  };

  it("pins the intro for 3.3 screens, splitting the sentence into words that light up in reading order", async () => {
    const f = await setup();
    expect(document.documentElement.classList.contains("kt-js")).toBe(true);
    const track = document.querySelector<HTMLElement>(".sx-track")!;
    expect(track.style.height).toBe("330svh");
    box(track, 0, 3000);
    const words = [...document.querySelectorAll<HTMLElement>(".kt-read .sx-word")];
    expect(words.map((w) => w.textContent)).toEqual(["One", "two", "three", "four"]);
    expect(words.every((w) => w.getAttribute("aria-hidden") === "true")).toBe(true);
    const lit = () => words.filter((w) => w.style.opacity === "1").length;
    const at = (p: number) => { moveTo(track, -p * 2200); f.step(); };
    at(0); expect(lit()).toBe(0);
    expect(words[0].style.opacity).toBe("0.14");                   // dimmed, not gone: the sentence can be read before it lights
    at(0.5); expect(lit()).toBe(2);
    at(0.78); expect(lit()).toBe(4);
    at(1); expect(lit()).toBe(4);
  });

  it("the copy under the sentence arrives after the last word: fading in and rising over the next 12%", async () => {
    const f = await setup();
    const track = document.querySelector<HTMLElement>(".sx-track")!;
    box(track, 0, 3000);
    const body = document.querySelector<HTMLElement>(".kt-intro__body")!;
    const at = (p: number) => { moveTo(track, -p * 2200); f.step(); return [+body.style.opacity, body.style.transform]; };
    expect(at(0)).toEqual([0, "translateY(30.0px)"]);
    expect(at(0.7)).toEqual([0, "translateY(30.0px)"]);
    const [o, t] = at(0.86);
    expect(o).toBeCloseTo(0.5, 6);
    expect(t).toBe("translateY(15.0px)");
    expect(at(1)).toEqual([1, "translateY(0.0px)"]);
  });

  it("with reduced motion the sentence is left whole and nothing pins", async () => {
    await setup({ reduced: true });
    expect(document.querySelector(".sx-track")).toBeNull();
    expect(document.querySelector(".kt-read")!.textContent).toBe("One two three four");
    expect(document.querySelector(".sx-word")).toBeNull();
  });
});

// ---------------------------------------------------------------------------------------------------------------- every style
describe("every style's experience", () => {
  const styles = Object.keys(import.meta.glob("../src/styles/[a-z]*.ts")).map((p) => /([^/]+)\.ts$/.exec(p)![1]);

  it("finds the styles", () => { expect(styles.length).toBeGreaterThanOrEqual(30); });

  it.each(styles)("%s starts on a bare page, and again with reduced motion, without throwing", async (style) => {
    stubIntersectionObserver();
    for (const reduced of [false, true]) {
      html(`<header id="ss-nav"></header><main><section><h1>Title</h1><p>Words</p></section></main>`);
      const mod = await atPage(() => import(`../src/styles/${style}.ts`), { reduced });
      expect(typeof (mod as { default: unknown }).default).toBe("function");
      expect(() => (mod as { default: () => void }).default()).not.toThrow();
    }
  });
});
