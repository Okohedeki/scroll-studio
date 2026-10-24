/**
 * The runtime's entry (index.ts): the scene controller that turns scroll into progress, captions, the HUD and a player's
 * frame state; scroll reveals and count-ups; the loading screen; anchors; the nav. The page is built by hand (as the
 * compiler's templates would) with layout boxes set per test, and frames are run one at a time.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { atPage, box, frames, moveTo, screen, scrollToY } from "./helpers";

/** every Lenis the page makes, so a test can see how it was set up and what it was asked to scroll to */
const lenis = { instances: [] as { opts: unknown; scrolls: unknown[][] }[] };
vi.mock("lenis", () => ({
  default: class {
    scrolls: unknown[][] = [];
    raf = () => {}; scrollTo = (...a: unknown[]) => { this.scrolls.push(a); };
    constructor(public opts: unknown) { (globalThis as any).__lenisInstances.push(this); }
  },
}));
(globalThis as any).__lenisInstances = lenis.instances;

const H = 800;
const hud = (over: Record<string, unknown> = {}) => ({ kind: "none", fields: [], events: [], clock: null, scales: [], legend: [], ...over });

interface SceneOpts { id?: string; type?: string; cfg?: object; data?: Record<string, unknown>; inner?: string }
/** A scene section as the compiler writes it. */
function scene(o: SceneOpts = {}) {
  const { id = "s1", type = "none", cfg = {}, inner = "" } = o;
  const data = { hud: hud(), steps: [], layout: "overlay", length: 1, ...(o.data ?? {}) };
  return `<section data-scene="${type}" id="${id}">
    <script class="ss-config" type="application/json">${JSON.stringify(cfg)}</script>
    <script class="ss-section" type="application/json">${JSON.stringify(data)}</script>
    <div class="ss-track"><div class="ss-visual"></div></div>${inner}</section>`;
}

interface Boot { markup: string; p?: number; s?: string; reduced?: boolean; loader?: { maxWait: number; minTime: number }; scroll?: { speed: number }; style?: string; now?: boolean }
async function boot(o: Boot) {
  document.body.innerHTML = o.markup;
  if (o.style !== undefined) document.documentElement.dataset.style = o.style;
  screen({ w: 1280, h: H, y: 0 });
  const w = window as any;
  w.__ssLoader = o.loader ?? { maxWait: 1, minTime: 0 };
  w.__ssScroll = o.scroll;
  const f = frames();
  await atPage(() => import("../src/index"), { p: o.p, s: o.s, reduced: o.reduced });
  return f;
}
const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector<T>(sel)!;
/** let the page's own promises (players mounting, the loader) settle */
const settle = async (ms = 50) => { await vi.dynamicImportSettled(); await vi.advanceTimersByTimeAsync(ms); await vi.dynamicImportSettled(); };

beforeEach(() => { vi.useFakeTimers(); lenis.instances.length = 0; });
afterEach(() => {
  const w = window as any; delete w.__ssLoader; delete w.__ssScroll; delete w.__ssLenis;
  history.replaceState(null, "", "/");
  delete document.documentElement.dataset.style; delete document.documentElement.dataset.ssStyle; delete document.documentElement.dataset.ssReady;
  vi.doUnmock("../src/styles/neo-brutalism");
});

describe("progress of an overlay scene", () => {
  it("is how far the scene's track has scrolled past the top, as a fraction of the track beyond one screen", async () => {
    const f = await boot({ markup: scene({ inner: `<div class="ss-caption" id="c" data-from="0.2" data-to="0.6"></div>` }), reduced: true });
    const track = $(".ss-track"), sec = $("#s1");
    box(sec, 0, 4 * H); box(track, 0, 4 * H);
    await settle();
    f.step();                     // the track starts at the top: p = 0
    expect($("#c").classList.contains("ss-on")).toBe(false);
    moveTo(track, -1.2 * H);      // 1.2 screens of the 3 screens of travel: p = 0.4
    scrollToY(1.2 * H); f.step();
    expect($("#c").classList.contains("ss-on")).toBe(true);
    moveTo(track, -3 * H);        // the end of the track: p = 1
    f.step();
    expect($("#c").classList.contains("ss-off")).toBe(true);
    expect($("#c").classList.contains("ss-on")).toBe(false);
  });

  it("is eased toward the scroll position by 14% a frame, then snaps when it is within 0.0001", async () => {
    const f = await boot({ markup: scene({ data: { hud: hud({ kind: "progress", scales: ["Start"] }) }, inner: `<div data-pbar></div><b data-ppct></b>` }) });
    const track = $(".ss-track");
    box($("#s1"), 0, 4 * H); box(track, -3 * H, 4 * H);      // the end: raw progress is 1
    await settle();
    f.step();
    expect($("[data-ppct]").textContent).toBe("14");
    f.step();
    expect($("[data-ppct]").textContent).toBe("26");           // 0.14 + 0.86 * 0.14
    for (let i = 0; i < 80; i++) f.step();
    expect($("[data-ppct]").textContent).toBe("100");
    expect($("[data-pbar]").style.transform).toBe("scaleX(1)");
  });

  it("jumps straight to the target with reduced motion", async () => {
    const f = await boot({ markup: scene({ data: { hud: hud({ kind: "progress", scales: ["Start"] }) }, inner: `<b data-ppct></b>` }), reduced: true });
    box($("#s1"), 0, 4 * H); box($(".ss-track"), -1.5 * H, 4 * H);
    await settle();
    f.step();
    expect($("[data-ppct]").textContent).toBe("50");
  });

  it("does no work for a scene that is more than half a screen away", async () => {
    const f = await boot({ markup: scene({ data: { hud: hud({ kind: "progress", scales: ["Start"] }) }, inner: `<b data-ppct>x</b>` }), reduced: true });
    box($("#s1"), 3 * H, 4 * H); box($(".ss-track"), 3 * H, 4 * H);
    await settle();
    f.step();
    expect($("[data-ppct]").textContent).toBe("x");
    moveTo($("#s1"), 1.4 * H);            // a screen and a bit away: close enough
    f.step();
    expect($("[data-ppct]").textContent).toBe("0");
  });
});

describe("captions and the HUD", () => {
  const dataFor = (over: Record<string, unknown>) => ({ hud: hud(over) });

  it("a caption is idle before its window, on inside it, and off after it", async () => {
    const caps = `<div class="ss-caption" id="a" data-from="0.1" data-to="0.3"></div><div class="ss-caption" id="b" data-from="0.3" data-to="0.5"></div>`;
    const f = await boot({ markup: scene({ inner: caps }), reduced: true });
    box($("#s1"), 0, 5 * H); box($(".ss-track"), 0, 5 * H);
    await settle();
    const at = (p: number) => { moveTo($(".ss-track"), -p * 4 * H); f.step(); return ["a", "b"].map((id) => ["ss-on", "ss-off"].filter((c) => $("#" + id).classList.contains(c)).join("") || "idle"); };
    expect(at(0.05)).toEqual(["idle", "idle"]);
    expect(at(0.2)).toEqual(["ss-on", "idle"]);
    expect(at(0.4)).toEqual(["ss-off", "ss-on"]);
    expect(at(0.9)).toEqual(["ss-off", "ss-off"]);
    expect(at(0.2)).toEqual(["ss-on", "idle"]);          // scrolling back
  });

  it("splits a caption's words into spans that rise one after another", async () => {
    await boot({ markup: scene({ inner: `<div class="ss-caption" data-from="0" data-to="1"><h2 class="ss-split-words">Cold <em>from</em> the source</h2></div>` }) });
    const words = [...document.querySelectorAll<HTMLElement>(".ss-w")];
    expect(words.map((w) => w.textContent)).toEqual(["Cold", "from", "the", "source"]);
    expect(words[1].closest("em")).toBeTruthy();   // the markup around a word survives
    expect(words[0].firstElementChild!.getAttribute("style")).toContain("transition-delay: 0.060s");
    expect(words[3].firstElementChild!.getAttribute("style")).toContain("transition-delay: 0.195s");
  });

  it("telemetry: numbers, the clock and the events follow progress", async () => {
    const h = {
      kind: "telemetry",
      fields: [{ label: "Alt", from: 0, to: 100, curve: 1, decimals: 1 }, { label: "Mass", from: 1000, to: 5000, curve: 1, grouping: true }],
      events: [{ at: 0.5, label: "Stage" }, { at: 0.9, label: "Orbit" }],
      clock: { start: -3600, end: 7200, zero: 0.5 },
    };
    const inner = `<i data-field></i><i data-field></i><ul class="ss-events"><li data-at="0.5"></li><li data-at="0.9"></li></ul><time data-clock></time><div data-bar></div>`;
    const f = await boot({ markup: scene({ data: dataFor(h), inner }), reduced: true });
    box($("#s1"), 0, 5 * H);
    await settle();
    const at = (p: number) => { box($(".ss-track"), -p * 4 * H, 5 * H); f.step(); };
    at(0.75);                                  // flight = (0.75 - 0.5) / 0.5 = 0.5
    const fields = [...document.querySelectorAll("[data-field]")].map((e) => e.textContent);
    expect(fields).toEqual(["50.0", "3,000"]);
    expect($("[data-clock]").textContent).toBe("+01:00:00");
    expect([...document.querySelectorAll(".ss-events li")].map((l) => l.classList.contains("ss-done"))).toEqual([true, false]);   // the events at 0.5 and 0.9
    expect($("[data-bar]").style.transform).toBe("scaleX(0.75)");
    at(0.25);                                  // before zero, the clock counts down: start * (1 - p / zero)
    expect($("[data-clock]").textContent).toBe("-00:30:00");
    expect([...document.querySelectorAll("[data-field]")].map((e) => e.textContent)).toEqual(["0.0", "1,000"]);
    expect([...document.querySelectorAll(".ss-events li")].map((l) => l.classList.contains("ss-done"))).toEqual([false, false]);
  });

  it("telemetry values follow their own curve (1.5 by default)", async () => {
    const h = { kind: "telemetry", fields: [{ label: "v", to: 100 }], events: [], clock: null };
    const f = await boot({ markup: scene({ data: dataFor(h), inner: "<i data-field></i>" }), reduced: true });
    box($("#s1"), 0, 5 * H);
    await settle();
    box($(".ss-track"), -0.5 * 4 * H, 5 * H); f.step();
    expect($("[data-field]").textContent).toBe((100 * Math.pow(0.5, 1.5)).toFixed(1));
  });

  it("progress: the step in view gives the number and the title, with markup stripped; the end says Complete", async () => {
    const h = { kind: "progress", scales: ["Getting ready"] };
    const steps = [{ title: "Intro", intro: true, length: 1 }, { kicker: "Step 02", title: "Mix <em>well</em>", length: 1 }];
    const inner = `<b data-pnum></b><b data-ptitle></b><b data-ppct></b><div class="ss-caption" data-from="0.1" data-to="0.3"></div><div class="ss-caption" data-from="0.4" data-to="0.6"></div>`;
    const f = await boot({ markup: scene({ data: { hud: hud(h), steps }, inner }), reduced: true });
    box($("#s1"), 0, 5 * H);
    await settle();
    const at = (p: number) => { box($(".ss-track"), -p * 4 * H, 5 * H); f.step(); return [$("[data-pnum]").textContent, $("[data-ptitle]").textContent]; };
    expect(at(0)).toEqual(["—", "Getting ready"]);
    expect(at(0.2)).toEqual(["—", "Getting ready"]);            // the intro is not a real step
    expect(at(0.5)).toEqual(["02", "Mix well"]);          // the number is the first number in the kicker
    expect(at(1)).toEqual(["✓", "Complete"]);
  });

  it("scale: the label interpolates in log space across the steps, unless the player sets its own", async () => {
    const h = { kind: "scale", scales: ["1 m", "100 m", "10 km"] };
    const steps = [{ title: "a", intro: true, length: 1 }, { title: "b", length: 1 }, { title: "c", length: 1 }];
    const inner = `<b data-scale></b><div class="ss-step" id="st1"></div><div class="ss-step" id="st2"></div><div class="ss-step" id="st3"></div>`;
    const f = await boot({ markup: scene({ data: { hud: hud(h), steps, layout: "cards" }, inner }), reduced: true });
    const [s1, s2, s3] = ["st1", "st2", "st3"].map((id) => $("#" + id));
    box($("#s1"), 0, 3 * H);
    // each step's progress is how far its centre line has gone through it: 0 before, 1 after
    const place = (a: number, b: number, c: number) => { box(s1, H / 2 - a * 400, 400); box(s2, H / 2 - b * 400, 400); box(s3, H / 2 - c * 400, 400); f.step(); };
    await settle();
    place(0, 0, 0);
    expect($("[data-scale]").textContent).toBe("1 m");           // the intro does not move the scale
    place(1, 0.5, 0);
    expect($("[data-scale]").textContent).toBe("10 m");
    place(1, 1, 0);
    expect($("[data-scale]").textContent).toBe("100 m");
  });

  it("the cue fades out over the first 3% and the outro in over the last 2.5%", async () => {
    const f = await boot({ markup: scene({ inner: `<div class="ss-cue"></div><div class="ss-outro"></div>` }), reduced: true });
    box($("#s1"), 0, 5 * H);
    await settle();
    const at = (p: number) => { box($(".ss-track"), -p * 4 * H, 5 * H); f.step(); return [+$(".ss-cue").style.opacity, +$(".ss-outro").style.opacity]; };
    expect(at(0)).toEqual([1, 0]);
    expect(at(0.015)[0]).toBeCloseTo(0.5, 12);
    expect(at(0.5)).toEqual([0, 0]);
    expect(at(0.9875)[1]).toBeCloseTo(0.425, 12);
    expect(at(1)).toEqual([0, 0.85]);
  });
});

describe("split and cards layouts", () => {
  const steps = [{ title: "a", length: 1 }, { title: "b", length: 3 }];
  const inner = `<div class="ss-step" id="st1"></div><div class="ss-step" id="st2"></div><b data-ppct></b>`;
  const data = { hud: hud({ kind: "progress", scales: ["x"] }), steps, layout: "cards" };

  it("each step's progress is how far its middle has gone through it; the whole is their average weighted by step length", async () => {
    const f = await boot({ markup: scene({ data, inner }), reduced: true });
    box($("#s1"), 0, 3 * H);
    await settle();
    box($("#st1"), H / 2 - 400, 400);          // fully through (target 1)
    box($("#st2"), H / 2 - 200, 400);          // half way
    f.step();
    // (1 * 1 + 0.5 * 3) / 4 = 0.625
    expect($("[data-ppct]").textContent).toBe("63");
  });

  it("marks the step on screen active until it has been passed", async () => {
    const f = await boot({ markup: scene({ data, inner }), reduced: true });
    box($("#s1"), 0, 3 * H);
    await settle();
    box($("#st1"), H / 2 - 200, 400); box($("#st2"), H, 400);
    f.step();
    expect($("#st1").classList.contains("ss-active")).toBe(true);
    expect($("#st2").classList.contains("ss-active")).toBe(false);
    expect($("#st1").style.getPropertyValue("--on")).toBe("1.000");
    box($("#st1"), -400 - 1, 400);             // just through: no longer active
    f.step();
    expect($("#st1").classList.contains("ss-active")).toBe(false);
  });
});

describe("scroll reveals and count-ups", () => {
  it("a revealed element fades and rises in as it crosses the lower part of the screen, each a little later than the one before", async () => {
    const f = await boot({ markup: `<div class="ss-reveal" id="r0"></div><div class="ss-reveal" id="r1"></div><div class="ss-reveal" id="r2"></div>` });
    expect([...document.querySelectorAll(".ss-reveal")].every((e) => e.classList.contains("ss-in"))).toBe(true);
    const r = ["r0", "r1", "r2"].map((id) => $("#" + id));
    r.forEach((e) => box(e, H * 0.98 - 80, 100));          // 80px above the point they start to appear
    scrollToY(1); f.step();
    // k = (0.98H - top) / (0.2H) - lag, lag = 0, 0.25, 0.5
    const k = (80 / (0.2 * H)) ;
    expect(+r[0].style.opacity).toBeCloseTo(k, 3);
    expect(+r[1].style.opacity).toBeCloseTo(k - 0.25, 3);
    expect(+r[2].style.opacity).toBeCloseTo(Math.max(0, k - 0.5), 3);
    expect(r[0].style.transform).toBe(`translateY(${((1 - k) * 22).toFixed(1)}px)`);
    r.forEach((e) => moveTo(e, 0));
    scrollToY(2); f.step();
    for (const e of r) { expect(e.style.opacity).toBe("1"); expect(e.style.transform).toBe(""); }
  });

  it("count-ups finish before the number reaches the middle of the screen, easing out, keeping a <sup> and the decimals", async () => {
    const f = await boot({ markup: `<div class="ss-reveal" id="r"><b data-count="12.5" id="n">0<sup>%</sup></b></div>` });
    box($("#r"), H * 0.95 - 0.2 * H, 100);                // halfway through its 40% of the screen
    scrollToY(1); f.step();
    expect($("#n").innerHTML).toBe(`${(12.5 * (1 - 0.125)).toFixed(1)}<sup>%</sup>`);
    moveTo($("#r"), H * 0.4);
    scrollToY(2); f.step();
    expect($("#n").innerHTML).toBe("12.5<sup>%</sup>");
  });

  it("with reduced motion everything is already in", async () => {
    const f = await boot({ markup: `<div class="ss-reveal" id="r"><b data-count="40" id="n">0</b></div>`, reduced: true });
    box($("#r"), H * 2, 100);
    scrollToY(1); f.step();
    expect($("#r").style.opacity).toBe("1");
    expect($("#n").innerHTML).toBe("40");
  });

  it("`scroll.speed` makes reveals finish over that much less travel", async () => {
    const f = await boot({ markup: `<div class="ss-reveal" id="r"></div>`, scroll: { speed: 2 } });
    box($("#r"), H * 0.98 - 0.1 * H, 100);               // 10% of the screen in: half-way at double speed
    scrollToY(1); f.step();
    expect(+$("#r").style.opacity).toBeCloseTo(1, 3);
  });
});

describe("the nav", () => {
  it("turns solid once the page has scrolled 40px", async () => {
    const f = await boot({ markup: `<header id="ss-nav"></header>` });
    scrollToY(10); f.step();
    expect($("#ss-nav").classList.contains("ss-solid")).toBe(false);
    scrollToY(41); f.step();
    expect($("#ss-nav").classList.contains("ss-solid")).toBe(true);
  });

  it("takes the surface of the section under it, and gives it back when it moves on", async () => {
    const f = await boot({ markup: `<header id="ss-nav"></header><main><section id="a" class="ss-surface-dark"></section><section id="b" class="ss-surface-paper"></section></main>` });
    box($("#ss-nav"), 0, 60);
    box($("#a"), 0, 500); box($("#b"), 500, 500);
    f.step();
    expect($("#ss-nav").classList.contains("ss-surface-dark")).toBe(true);
    moveTo($("#a"), -500); moveTo($("#b"), 0);
    f.step();
    expect($("#ss-nav").classList.contains("ss-surface-dark")).toBe(false);
    expect($("#ss-nav").classList.contains("ss-surface-paper")).toBe(true);
  });
});

describe("players", () => {
  it("a player is mounted for the scene's type and fed the frame state every frame", async () => {
    const f = await boot({ markup: scene({ type: "type", cfg: { mode: "reveal", text: "one two three four" } }), reduced: true });
    await settle();
    expect($("#s1").classList.contains("ss-ready")).toBe(true);
    box($("#s1"), 0, 5 * H);
    box($(".ss-track"), -0.48 * 4 * H, 5 * H);
    f.step();
    expect(document.querySelectorAll(".ss-type__text span.on")).toHaveLength(2);   // p = 0.48: half of the words
  });

  it("a player that fails marks its scene failed and the page carries on", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    await boot({ markup: scene({ type: "vector", cfg: { svg: "/x.svg" } }) });
    await settle();
    expect($("#s1").classList.contains("ss-failed")).toBe(true);
    expect($("#s1").classList.contains("ss-ready")).toBe(false);
    expect(err).toHaveBeenCalled();
  });

  it("a scene type with no player is left as the static page", async () => {
    await boot({ markup: scene({ type: "mystery" }) });
    await settle();
    expect($("#s1").classList.contains("ss-ready")).toBe(false);
    expect($("#s1").classList.contains("ss-failed")).toBe(false);
  });

  it("a resize resizes every player and draws it again at once", async () => {
    const f = await boot({ markup: scene({ type: "type", cfg: { mode: "swap", text: "x", words: ["aa", "bbbb"] } }), reduced: true });
    await settle();
    const roll = $(".ss-type .roll");
    box($("#s1"), 0, 5 * H);
    f.step();
    roll.style.width = "";
    window.dispatchEvent(new Event("resize"));
    expect(roll.style.width).toBe("42px");
  });
});

describe("the loading screen", () => {
  const loader = `<div id="ss-loader"><div class="ss-loader__bar"><i></i></div><div class="ss-loader__pct"><span>0</span></div></div>`;

  it("lifts when everything has loaded: the page is marked ready and scrolled to the top, smooth scrolling starts, the screen is removed", async () => {
    document.documentElement.classList.add("ss-loading");
    await boot({ markup: loader + scene({ type: "type", cfg: { mode: "reveal", text: "a b" } }) });
    await settle();
    expect(document.documentElement.dataset.ssReady).toBe("1");
    expect(document.documentElement.classList.contains("ss-loading")).toBe(false);
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);
    expect($("#ss-loader").classList.contains("ss-leaving")).toBe(true);
    expect($(".ss-loader__bar i").style.transform).toBe("scaleX(1)");
    expect($(".ss-loader__pct span").textContent).toBe("100");
    await settle(1000);
    expect(document.getElementById("ss-loader")).toBeNull();
    expect(lenis.instances).toHaveLength(1);
    expect((window as any).__ssLenis).toBe(lenis.instances[0]);
  });

  it("holds the screen for at least `minTime`", async () => {
    await boot({ markup: loader + scene(), loader: { maxWait: 5, minTime: 2 } });
    await settle(1500);
    expect(document.documentElement.dataset.ssReady).toBeUndefined();
    await settle(700);
    expect(document.documentElement.dataset.ssReady).toBe("1");
  });

  it("gives up waiting after `maxWait` for a scene that never finishes loading", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    await boot({ markup: loader + scene({ type: "vector", cfg: { svg: "/never.svg" } }), loader: { maxWait: 3, minTime: 0 } });
    await settle(2500);
    expect(document.documentElement.dataset.ssReady).toBeUndefined();
    await settle(1000);
    expect(document.documentElement.dataset.ssReady).toBe("1");
  });

  it("smooth scrolling is off for reduced motion and for ?p= captures, and paced by `scroll.speed`", async () => {
    await boot({ markup: scene(), reduced: true });
    await settle();
    expect(lenis.instances).toHaveLength(0);
    await boot({ markup: scene(), p: 0.3 });
    await settle();
    expect(lenis.instances).toHaveLength(0);
    await boot({ markup: scene(), scroll: { speed: 2 } });
    await settle();
    expect(lenis.instances[0].opts).toEqual({ lerp: 0.2 });
    lenis.instances.length = 0;
    await boot({ markup: scene(), scroll: { speed: 10 } });
    await settle();
    expect(lenis.instances[0].opts).toEqual({ lerp: 0.5 });     // never snappier than 0.5
  });
});

describe("anchors", () => {
  const page = `<a href="#two" id="go">go</a><a href="#" id="top">top</a><a href="#nowhere" id="lost">x</a><section id="two"></section>`;

  it("a link to a section scrolls there: through Lenis once it runs, by the browser before", async () => {
    await boot({ markup: page, loader: { maxWait: 5, minTime: 3 } });
    const two = $("#two");
    const scrollIntoView = vi.fn();
    two.scrollIntoView = scrollIntoView;
    const click = (id: string) => { const e = new MouseEvent("click", { bubbles: true, cancelable: true }); $("#" + id).dispatchEvent(e); return e; };
    expect(click("go").defaultPrevented).toBe(true);
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    await settle(4000);                                       // the page is ready: Lenis runs
    const e = click("go");
    expect(e.defaultPrevented).toBe(true);
    expect(lenis.instances[0].scrolls).toEqual([[two, { duration: 1.4 }]]);
  });

  it("a bare # and a link to something that is not there are left to the browser", async () => {
    await boot({ markup: page });
    const click = (id: string) => { const e = new MouseEvent("click", { bubbles: true, cancelable: true }); $("#" + id).dispatchEvent(e); return e; };
    expect(click("top").defaultPrevented).toBe(false);
    expect(click("lost").defaultPrevented).toBe(false);
  });

  it("the scroll takes less time at `scroll.speed` above 1", async () => {
    await boot({ markup: page, scroll: { speed: 2 } });
    await settle();
    $("#two").scrollIntoView = vi.fn();
    $("#go").dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    expect(lenis.instances[0].scrolls).toEqual([[$("#two"), { duration: 0.7 }]]);
  });
});

describe("?p= captures", () => {
  it("jump scrolls so the first scene sits at that progress (overlay layout)", async () => {
    await boot({ markup: scene({ id: "s1" }) + scene({ id: "s2" }), p: 0.25 });
    box($("#s1"), 0, 3 * H); box($(".ss-track"), 0, 3 * H);
    await settle(400);
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0.25 * (3 * H - H));
  });

  it("`s=` picks the scene by id", async () => {
    await boot({ markup: scene({ id: "s1" }) + scene({ id: "s2" }), p: 0.5, s: "s2" });
    const s2 = $("#s2");
    box(s2, 2000, 2 * H);
    box(s2.querySelector<HTMLElement>(".ss-track")!, 2000, 2 * H);
    await settle(400);
    expect(window.scrollTo).toHaveBeenCalledWith(0, 2000 + 0.5 * H);
  });

  it("a split layout jumps between the first step's middle line and the last's", async () => {
    const inner = `<div class="ss-step" id="a"></div><div class="ss-step" id="b"></div>`;
    await boot({ markup: scene({ data: { layout: "split", steps: [{ title: "a", length: 1 }, { title: "b", length: 1 }] }, inner }), p: 0.5 });
    box($("#a"), 400, 400); box($("#b"), 1200, 400);
    await settle(400);
    // from (400 - H/2) to (1600 - H/2) halfway
    expect(window.scrollTo).toHaveBeenCalledWith(0, 400 - H / 2 + 0.5 * (1600 - 400));
  });
});

describe("a style's own experience", () => {
  it("an unknown style, or none, is ready at once", async () => {
    await boot({ markup: scene(), style: "no-such-style" });
    expect(document.documentElement.dataset.ssStyle).toBe("ready");
  });

  it("a known style is started, and the page is marked once it is running", async () => {
    const start = vi.fn();
    vi.doMock("../src/styles/neo-brutalism", () => ({ default: start }));
    await boot({ markup: scene(), style: "neo-brutalism" });
    await settle();
    expect(start).toHaveBeenCalledTimes(1);
    expect(document.documentElement.dataset.ssStyle).toBe("ready");
  });
});

describe("the page without scenes", () => {
  it("still marks the page as js, runs frames and unlocks", async () => {
    const f = await boot({ markup: "<main><p>plain</p></main>" });
    expect(document.documentElement.classList.contains("js")).toBe(true);
    expect(() => f.step()).not.toThrow();
    await settle();
    expect(document.documentElement.dataset.ssReady).toBe("1");
  });
});
