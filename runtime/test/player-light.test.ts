/**
 * The players that need WebGL2, in the browsers that do not have it: light shows one still per step (and keeps the section's
 * colours, the clock and the headline shade following the sky), the shader players hand over to the plain film.
 * jsdom has no WebGL, so this is the path they take here.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { atPage, frameState, playerCtx } from "./helpers";

afterEach(() => vi.doUnmock("../src/lib/util"));

const tok = (bg: number[], ink: number[]) => ({ bg, bg2: bg.map((v) => v - 5), ink, em: [200, 80, 0], accent: [255, 120, 40], a2: 0.7, a3: 0.5, dark: false });
const times = [
  { id: "dawn", label: "Dawn", clock: "06:00", hours: 6, haze: 0, lit: false, sun: "", img: "dawn.jpg", imgS: "dawn-s.jpg", tokens: tok([10, 20, 30], [240, 240, 240]) },
  { id: "noon", label: "Noon", clock: "13:00", hours: 13, haze: 0, lit: false, sun: "", img: "noon.jpg", imgS: "noon-s.jpg", tokens: tok([200, 210, 220], [20, 20, 20]) },
  { id: "dusk", label: "Dusk", clock: "21:00", hours: 21, haze: 0, lit: true, sun: "", img: "dusk.jpg", imgS: "dusk-s.jpg", tokens: tok([40, 20, 60], [250, 230, 210]) },
];
const holds = [{ t: 0, a: 0, b: 0.2 }, { t: 1, a: 0.4, b: 0.6 }, { t: 2, a: 0.8, b: 1 }];
const cfg = { times, pairs: [], holds, follow: true, clock: true, stepTimes: [0, 1, 2], focus: [0.25, 0.75], sun: { rise: [0.1, 0.5], noon: [0.5, 0.06], set: [0.92, 0.5] } };

async function mountLight(over: Record<string, unknown> = {}, o: { mobile?: boolean } = {}) {
  const loaded: string[] = [];
  vi.doMock("../src/lib/util", async (orig) => ({
    ...(await orig<typeof import("../src/lib/util")>()),
    loadImage: vi.fn(async (src: string) => { loaded.push(src); const im = document.createElement("img"); im.dataset.src = src; return im; }),
  }));
  const { default: factory } = await atPage(() => import("../src/players/light"), { mobile: o.mobile });
  const ctx = playerCtx([{}, {}, {}]);
  ctx.data.steps = [{ title: "a", length: 1, at: [0, 0.2] }, { title: "b", length: 1, at: [0.4, 0.6] }, { title: "c", length: 1, at: [0.8, 1] }];
  ctx.section.innerHTML += `<div class="ss-caption" id="c0"></div><div class="ss-caption" id="c1"></div><div class="ss-caption" id="c2"></div>`;
  const player = await factory({ ...cfg, ...over }, ctx);
  const stills = [...ctx.visual.querySelectorAll<HTMLImageElement>("img.ss-light-still")];
  return { player, ctx, stills, loaded };
}
const shown = (stills: HTMLImageElement[]) => stills.map((s) => s.dataset.src).filter((_, i) => stills[i].style.opacity === "1");

describe("light without WebGL2: one still per time of day", () => {
  it("loads every time's picture, and only the first is showing, framed on the scene's focus", async () => {
    const { stills, loaded } = await mountLight();
    expect(loaded.sort()).toEqual(["dawn.jpg", "dusk.jpg", "noon.jpg"]);
    expect(stills).toHaveLength(3);
    expect(shown(stills)).toEqual(["dawn.jpg"]);
    expect(stills[0].style.objectPosition).toBe("25% 75%");
    expect(stills[0].alt).toBe("");
  });

  it("a phone loads the smaller pictures", async () => {
    const { loaded } = await mountLight({}, { mobile: true });
    expect(loaded.sort()).toEqual(["dawn-s.jpg", "dusk-s.jpg", "noon-s.jpg"]);
  });

  it("shows the time of day the holds put the scroll at: each held while its step is read, the nearer one between", async () => {
    const { player, stills } = await mountLight();
    for (const [p, want] of [[0.1, "dawn.jpg"], [0.45, "noon.jpg"], [0.9, "dusk.jpg"], [0.31, "noon.jpg"], [0.29, "dawn.jpg"]] as [number, string][]) {
      player.update(frameState(p));
      expect(shown(stills)).toEqual([want]);
    }
  });

  it("the section's colours follow the time of day, and say which it is", async () => {
    const { player, ctx } = await mountLight();
    const st = ctx.section.style;
    player.update(frameState(0.5));
    expect(st.getPropertyValue("--bg")).toBe("rgb(200, 210, 220)");
    expect(st.getPropertyValue("--ink")).toBe("rgb(20, 20, 20)");
    expect(st.getPropertyValue("--ink-rgb")).toBe("20, 20, 20");
    expect(st.getPropertyValue("--ink-2")).toBe("rgba(20, 20, 20, 0.70)");
    expect(st.getPropertyValue("--accent")).toBe("rgb(255, 120, 40)");
    expect(ctx.section.dataset.tod).toBe("noon");
    player.update(frameState(0.95));
    expect(st.getPropertyValue("--bg")).toBe("rgb(40, 20, 60)");
    expect(ctx.section.dataset.tod).toBe("dusk");
  });

  it("each headline keeps the ink of its own time of day", async () => {
    const { ctx } = await mountLight();
    const ink = (id: string) => ctx.section.querySelector<HTMLElement>("#" + id)!.style.getPropertyValue("--ink");
    expect([ink("c0"), ink("c1"), ink("c2")]).toEqual(["rgb(240, 240, 240)", "rgb(20, 20, 20)", "rgb(250, 230, 210)"]);
  });

  it("leaves the colours alone when the scene does not ask to follow", async () => {
    const { player, ctx } = await mountLight({ follow: false });
    player.update(frameState(0.5));
    expect(ctx.section.style.getPropertyValue("--bg")).toBe("");
    expect(ctx.section.dataset.tod).toBeUndefined();
    expect(ctx.section.querySelector<HTMLElement>("#c0")!.style.getPropertyValue("--ink")).toBe("");
  });

  it("the clock and the sun-arc in the corner say the time and name it", async () => {
    const { player, ctx } = await mountLight();
    const text = () => [ctx.visual.querySelector(".ss-tod__time")!.textContent, ctx.visual.querySelector(".ss-tod__label")!.textContent];
    expect(text()).toEqual(["--:--", ""]);
    player.update(frameState(0.5));
    expect(text()).toEqual(["13:00", "Noon"]);
    player.update(frameState(0.95));
    expect(text()).toEqual(["21:00", "Dusk"]);
    const ticks = [...ctx.visual.querySelectorAll(".ss-tod__ticks i")].map((i) => i.classList.contains("on"));
    expect(ticks).toEqual([false, false, true]);
    // at 21:00 it is night: the moon, a little way along its arc
    expect(ctx.visual.querySelector(".ss-tod__dot")!.classList.contains("moon")).toBe(true);
    player.update(frameState(0.5));
    expect(ctx.visual.querySelector(".ss-tod__dot")!.classList.contains("moon")).toBe(false);
    expect(+ctx.visual.querySelector(".ss-tod__dot")!.getAttribute("cx")!).toBeCloseTo(4 + 56 * 0.5, 0);   // the sun at the top of its arc
  });

  it("no clock unless asked", async () => {
    const { ctx } = await mountLight({ clock: false });
    expect(ctx.visual.querySelector(".ss-tod")).toBeNull();
  });

  it("the shade behind the headlines is there while one is, and gone between them", async () => {
    const { player, ctx } = await mountLight();
    const shade = () => +ctx.section.style.getPropertyValue("--shade");
    player.update(frameState(0.1));
    expect(shade()).toBe(1);
    player.update(frameState(0.3));
    expect(shade()).toBe(0);
    player.update(frameState(0.5));
    expect(shade()).toBe(1);
    player.update(frameState(0.7));
    expect(shade()).toBe(0);
  });
});

describe("shader players without WebGL2", () => {
  it("reveal hands over (null): the caller plays the colour film as it is", async () => {
    const { default: reveal } = await atPage(() => import("../src/players/reveal"));
    const ctx = playerCtx();
    expect(await reveal({ video: "v.mp4", reveal: { masks: [], regions: [], keys: [], base: "bw", strength: 1, ease: "smooth", feather: 0, fps: 24 } } as any, ctx)).toBeNull();
  });

  it("parallax refuses to start (the page marks the scene failed)", async () => {
    const { default: factory } = await atPage(() => import("../src/players/parallax"));
    await expect(factory({ chapters: [] }, playerCtx())).rejects.toThrow("no webgl2");
  });
});
