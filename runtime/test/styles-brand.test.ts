/**
 * A brand on a style (theme.from): the compiler sets --skin-<role> on the page to the brand's colour for each role of the
 * style's palette (engine/compile/themes.py `skin`), and what a style draws in its runtime reads it through `skin` (_kit).
 * Without a brand nothing is set and every style draws the colours it always did.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { atPage, frames, html, screen } from "./helpers";

const root = () => document.documentElement;
const brand = (vars: Record<string, string>) => Object.entries(vars).forEach(([k, v]) => root().style.setProperty(`--skin-${k}`, v));

beforeEach(() => { vi.useFakeTimers(); screen({ w: 1280, h: 800, y: 0 }); });
afterEach(() => { root().removeAttribute("style"); vi.unstubAllGlobals(); });

describe("skin", () => {
  const kit = () => atPage(() => import("../src/styles/_kit"));

  it("is the style's own colour when the page sets none", async () => {
    const { skin, skinRgb, skinRgba, skinNum } = await kit();
    expect(skin("accent", "#be1e2d")).toBe("#be1e2d");
    expect(skinRgb("accent", "#be1e2d")).toEqual([190, 30, 45]);
    expect(skinRgba("ink", "#fff7ee", 0.5)).toBe("rgba(255, 247, 238, 0.5)");
    expect(skinNum("bg", 0x0a0a0b)).toBe(0x0a0a0b);
  });

  it("is the brand's colour for the role when the page sets one, in every shape the styles draw with", async () => {
    brand({ accent: "#0b6e4f", "accent-text": "#095a40", ink: "#1d2a24", bg: "#fbf7ef" });
    const { skin, skinRgb, skinRgba, skinNum } = await kit();
    expect(skin("accent", "#be1e2d")).toBe("#0b6e4f");
    expect(skin("accent_text", "#a51a27")).toBe("#095a40");          // yaml names with an underscore, CSS names with a hyphen
    expect(skinRgb("accent", "#be1e2d")).toEqual([11, 110, 79]);
    expect(skinRgba("ink", "#fff7ee", ".25")).toBe("rgba(29, 42, 36, .25)");
    expect(skinNum("bg", 0x0a0a0b)).toBe(0xfbf7ef);
    expect(skin("accent2", "#1f4e9c")).toBe("#1f4e9c");              // a role the brand leaves alone keeps the style's colour
  });
});

describe("a style wearing a brand", () => {
  it("neo-brutalism sets its headline words on the brand's marks, and keeps the marks that are its own", async () => {
    brand({ accent: "#0b6e4f", accent2: "#f2a541", bg2: "#f1ede4" });
    html(`<main><section class="nb-hero"><h1 data-nb-words>One two three four five six</h1></section></main>`);
    const f = frames();
    const mod = await atPage(() => import("../src/styles/neo-brutalism"));
    (mod as { default: () => void }).default();
    f.step();
    const marks = [...document.querySelectorAll<HTMLElement>(".nb-word")].map((w) => w.style.getPropertyValue("--c"));
    expect(marks).toEqual(["#f1ede4", "#b8ff5c", "#0b6e4f", "#7fd3ff", "#ff7a5c", "#f2a541"]);
  });

  it("neo-brutalism draws the same marks as ever with no brand", async () => {
    html(`<main><section class="nb-hero"><h1 data-nb-words>One two three</h1></section></main>`);
    const mod = await atPage(() => import("../src/styles/neo-brutalism"));
    (mod as { default: () => void }).default();
    const marks = [...document.querySelectorAll<HTMLElement>(".nb-word")].map((w) => w.style.getPropertyValue("--c"));
    expect(marks).toEqual(["#ffc900", "#b8ff5c", "#ff90e8"]);
  });

  it("scratch-film lights its strip in the brand's ink; the dyes are film stock and stay", async () => {
    brand({ ink: "#e8f1ff" });
    const film = await atPage(() => import("../src/styles/_film-draw"));
    expect(film.LAMP).toBe("#e8f1ff");
    expect(film.lamp(0.6)).toBe("rgba(232, 241, 255, 0.6)");
    expect(film.MARKS[0]).toBe("#12b8d8");
  });

  it("scratch-film lights its strip as it always did with no brand", async () => {
    const film = await atPage(() => import("../src/styles/_film-draw"));
    expect(film.LAMP).toBe("#fff6df");
    expect(film.lamp(0.6)).toBe("rgba(255, 246, 223, 0.6)");
  });
});
