/** The one-take page: each stop's blocks arrive as the camera slows into it and leave as it moves on; the rail names the places. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { attach, type JourneyCfg } from "../src/players/journey";
import { box, html, media, screen } from "./helpers";

const cfg: JourneyCfg = {
  duration: 10,
  map: [[0, 0], [0.5, 4], [1, 10]],
  rail: true,
  stops: [
    { id: "hearth", label: "Hearth", p0: 0, p1: 0.2, in: [0, 0], out: [0.25, 0.35], focus: [0.2, 0.5] },
    { id: "attic", label: "Attic", p0: 0.5, p1: 0.7, in: [0.4, 0.5], out: [0.8, 0.9], focus: [0.8, 0.3] },
  ],
};

function page() {
  html(`<section id="s"><div class="ss-track"><div class="ss-visual"></div>
      <article class="jy-stop" data-stop="hearth"><a href="#x" id="inside">link</a></article>
      <article class="jy-stop" data-stop="attic"></article>
      <nav class="jy-rail"><a data-stop="hearth" href="#hearth">Hearth</a><a data-stop="attic" href="#attic">Attic</a></nav>
    </div></section>`);
  const section = document.getElementById("s")!;
  const track = section.querySelector<HTMLElement>(".ss-track")!;
  box(track, -100, 4800);
  const video = document.createElement("video");
  const api = attach(cfg, { section, visual: section.querySelector<HTMLElement>(".ss-visual")! }, video)!;
  const stop = (id: string) => section.querySelector<HTMLElement>(`.jy-stop[data-stop="${id}"]`)!;
  const dot = (id: string) => section.querySelector<HTMLElement>(`.jy-rail a[data-stop="${id}"]`)!;
  return { section, track, video, api, stop, dot };
}

beforeEach(() => { screen({ w: 1280, h: 800, y: 300 }); history.replaceState(null, "", "/"); });

describe("journey stops", () => {
  it("marks the section live and maps progress to film time through the map", () => {
    const { section, api } = page();
    expect(section.classList.contains("jy-live")).toBe(true);
    expect(api.time(0.25)).toBeCloseTo(2, 12);
    expect(api.time(0.75)).toBeCloseTo(7, 12);
  });

  it("a stop that is there from the first frame is on at progress 0, and the next is off", () => {
    const { api, stop } = page();
    api.update(0);
    expect(stop("hearth").classList.contains("jy-on")).toBe(true);
    expect(stop("hearth").style.getPropertyValue("--in")).toBe("1.000");
    expect(stop("hearth").style.getPropertyValue("--out")).toBe("0.000");
    expect(stop("attic").classList.contains("jy-on")).toBe(false);
    expect(stop("attic").style.getPropertyValue("--in")).toBe("0.000");
  });

  it("a stop arrives over its in-window and leaves over its out-window", () => {
    const { api, stop } = page();
    api.update(0.45);
    expect(stop("attic").style.getPropertyValue("--in")).toBe("0.500");
    expect(stop("attic").classList.contains("jy-on")).toBe(true);
    expect(stop("hearth").style.getPropertyValue("--out")).toBe("1.000");
    expect(stop("hearth").classList.contains("jy-on")).toBe(false);
    api.update(0.85);
    expect(stop("attic").style.getPropertyValue("--out")).toBe("0.500");
    api.update(0.95);
    expect(stop("attic").classList.contains("jy-on")).toBe(false);
  });

  it("the rail marks the stop whose hold is nearest, and says so to assistive tech", () => {
    const { api, dot } = page();
    api.update(0.05);
    expect(dot("hearth").classList.contains("jy-here")).toBe(true);
    expect(dot("hearth").getAttribute("aria-current")).toBe("true");
    expect(dot("attic").getAttribute("aria-current")).toBeNull();
    api.update(0.45);
    expect(dot("attic").classList.contains("jy-here")).toBe(true);
    expect(dot("attic").getAttribute("aria-current")).toBe("true");
    expect(dot("hearth").classList.contains("jy-here")).toBe(false);
    expect(dot("hearth").getAttribute("aria-current")).toBeNull();
  });

  it("on a phone the crop follows each stop's focus, travelling between them with the camera", () => {
    media.mobile = true;
    const { api, video } = page();
    api.update(0.1);
    expect(video.style.objectPosition).toBe("20.0% 50.0%");
    api.update(0.3);                                   // a third of the way from the end of one stop to the start of the next
    expect(video.style.objectPosition).toBe("40.0% 43.3%");
    api.update(0.6);
    expect(video.style.objectPosition).toBe("80.0% 30.0%");
  });

  it("on a desktop screen the crop is left alone, and a crop set on a phone is cleared", () => {
    media.mobile = true;
    const { api, video } = page();
    api.update(0.6);
    expect(video.style.objectPosition).not.toBe("");
    media.mobile = false;
    api.update(0.6);
    expect(video.style.objectPosition).toBe("");
  });
});

describe("journey navigation", () => {
  it("a click on a rail link scrolls to the middle of that stop's hold, through Lenis when it is there", () => {
    const { dot } = page();
    const scrollTo = vi.fn();
    (window as any).__ssLenis = { scrollTo };
    const outer = vi.fn();
    document.addEventListener("click", outer);
    const ev = new MouseEvent("click", { bubbles: true, cancelable: true });
    dot("attic").dispatchEvent(ev);
    // top of the track in the document: -100 + 300; the stop's hold is centred on progress 0.6 of (4800 - 800)
    expect(scrollTo).toHaveBeenCalledWith(-100 + 300 + 0.6 * 4000 + 1, { duration: 1.6 });
    expect(ev.defaultPrevented).toBe(true);
    expect(outer).not.toHaveBeenCalled();             // the page's own anchor handler never sees it
    delete (window as any).__ssLenis;
  });

  it("without Lenis the page scrolls smoothly itself", () => {
    const { dot } = page();
    dot("hearth").dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    expect(window.scrollTo).toHaveBeenCalledWith({ top: -100 + 300 + 0.1 * 4000 + 1, behavior: "smooth" });
  });

  it("tabbing into a stop that is off screen brings the page to it; one that is on screen is left", () => {
    const { section, stop } = page();
    const scrollTo = vi.fn();
    (window as any).__ssLenis = { scrollTo };
    stop("hearth").classList.add("jy-on");
    section.querySelector<HTMLElement>("#inside")!.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
    expect(scrollTo).not.toHaveBeenCalled();
    stop("hearth").classList.remove("jy-on");
    section.querySelector<HTMLElement>("#inside")!.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    delete (window as any).__ssLenis;
  });

  it("a link to a stop (#attic) lands on it, but not in a ?p= capture", () => {
    vi.useFakeTimers();
    history.replaceState(null, "", "/#attic");
    const scrollTo = vi.fn();
    (window as any).__ssLenis = { scrollTo };
    page();
    vi.advanceTimersByTime(500);
    expect(scrollTo).toHaveBeenCalledTimes(1);
    scrollTo.mockClear();
    history.replaceState(null, "", "/?p=0.5#attic");
    page();
    vi.advanceTimersByTime(500);
    expect(scrollTo).not.toHaveBeenCalled();
    delete (window as any).__ssLenis;
  });
});
