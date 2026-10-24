/**
 * What jsdom lacks and the runtime reaches for at import time or on every frame. Tests change the environment through
 * `./helpers` (media queries, layout boxes, scroll), never by editing these.
 */
import { afterEach, beforeEach, vi } from "vitest";
import { media, resetMedia } from "./helpers";

// ---- matchMedia: answers the two queries the runtime asks, from `media` in ./helpers
function matchMedia(query: string): MediaQueryList {
  const matches = /prefers-reduced-motion:\s*reduce/.test(query) ? media.reduced : /max-width:\s*760px/.test(query) ? media.mobile : false;
  return {
    matches, media: query, onchange: null,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
  } as MediaQueryList;
}
Object.defineProperty(window, "matchMedia", { configurable: true, writable: true, value: matchMedia });

// ---- observers (no layout in jsdom, so nothing is ever observed; tests that need one install their own)
class NoopObserver { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
for (const name of ["ResizeObserver", "IntersectionObserver"]) {
  Object.defineProperty(globalThis, name, { configurable: true, writable: true, value: NoopObserver });
}

// ---- a 2D canvas context that records what is drawn and measures text as half an em per character
export type FakeContext = CanvasRenderingContext2D & { calls: [string, ...unknown[]][]; alphaAtDraw: number[] };
const NAMED: Record<string, string> = { black: "#000000", white: "#ffffff", red: "#ff0000", lime: "#00ff00", blue: "#0000ff", rebeccapurple: "#663399" };
function fakeContext(canvas: HTMLCanvasElement): FakeContext {
  const calls: [string, ...unknown[]][] = [];
  const alphaAtDraw: number[] = [];
  let fill = "#000000";
  let font = "10px sans-serif";
  const record = (name: string) => (...args: unknown[]) => { calls.push([name, ...args]); if (name === "drawImage") alphaAtDraw.push(target.globalAlpha as number); };
  const target: Record<string, unknown> = {
    canvas, calls, alphaAtDraw, textBaseline: "alphabetic", letterSpacing: "0px", globalAlpha: 1, imageSmoothingQuality: "low",
    get fillStyle() { return fill; },
    // like a real context, a colour is read back normalised: opaque colours as "#rrggbb", and one it cannot read is ignored
    set fillStyle(v: string) {
      const text = String(v).trim().toLowerCase();
      const hex = /^#([0-9a-f]{3})$/.exec(text), hex6 = /^#[0-9a-f]{6}$/.exec(text);
      const rgb = /^rgb\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)\s*\)$/.exec(text);
      if (hex) fill = "#" + [...hex[1]].map((c) => c + c).join("");
      else if (hex6) fill = text;
      else if (rgb) fill = "#" + rgb.slice(1).map((n) => Number(n).toString(16).padStart(2, "0")).join("");
      else if (text in NAMED) fill = NAMED[text];
      else if (/^rgba\(|^hsla?\(/.test(text)) fill = text;
    },
    get font() { return font; },
    set font(v: string) { font = v; },
    measureText(text: string) {
      const px = parseFloat(/([\d.]+)px/.exec(font)?.[1] ?? "10");
      const spacing = parseFloat(String(target.letterSpacing)) || 0;
      return { width: text.length * (px * 0.5 + spacing) } as TextMetrics;
    },
    getImageData: (_x: number, _y: number, w: number, h: number) => ({ data: new Uint8ClampedArray(w * h * 4), width: w, height: h }),
  };
  for (const m of ["fillText", "clearRect", "fillRect", "drawImage", "beginPath", "moveTo", "lineTo", "stroke", "fill", "save", "restore", "translate", "scale", "rotate", "clip", "arc", "setTransform"]) {
    target[m] = record(m);
  }
  return target as unknown as FakeContext;
}
// the class a browser has (jsdom has none): `"letterSpacing" in CanvasRenderingContext2D.prototype` is how the runtime tests for it
class FakeCanvasRenderingContext2D {}
Object.defineProperty(FakeCanvasRenderingContext2D.prototype, "letterSpacing", { value: "0px", writable: true, configurable: true });
Object.defineProperty(globalThis, "CanvasRenderingContext2D", { configurable: true, writable: true, value: FakeCanvasRenderingContext2D });
const contexts = new WeakMap<HTMLCanvasElement, FakeContext>();
HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, kind: string) {
  if (kind !== "2d") return null;
  let c = contexts.get(this);
  if (!c) contexts.set(this, (c = fakeContext(this)));
  return c;
} as typeof HTMLCanvasElement.prototype.getContext;

// ---- a range measures its text at 10px a character (jsdom has no layout, and no Range.getBoundingClientRect)
Range.prototype.getBoundingClientRect = function (this: Range) {
  const w = this.toString().length * 10;
  return { x: 0, y: 0, left: 0, top: 0, right: w, bottom: 16, width: w, height: 16, toJSON: () => ({}) } as DOMRect;
};

// ---- media elements load and play nothing here
HTMLMediaElement.prototype.play = vi.fn(async () => {}) as unknown as typeof HTMLMediaElement.prototype.play;
HTMLMediaElement.prototype.pause = vi.fn() as unknown as typeof HTMLMediaElement.prototype.pause;
HTMLMediaElement.prototype.load = vi.fn() as unknown as typeof HTMLMediaElement.prototype.load;

// ---- Web Animations and SVG path length: nothing animates and a path is 100 long
Element.prototype.animate = vi.fn(() => ({ cancel() {}, finish() {}, play() {}, pause() {}, onfinish: null, finished: Promise.resolve() })) as unknown as typeof Element.prototype.animate;
(SVGElement.prototype as unknown as { getTotalLength: () => number }).getTotalLength = () => 100;

// ---- the rest of what a page has
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
window.scrollBy = vi.fn() as unknown as typeof window.scrollBy;
if (!("fonts" in document)) Object.defineProperty(document, "fonts", { configurable: true, value: { ready: Promise.resolve() } });

beforeEach(() => resetMedia());
afterEach(() => {
  document.head.innerHTML = "";
  document.body.innerHTML = "";
  document.documentElement.removeAttribute("class");
  document.documentElement.removeAttribute("style");
  vi.useRealTimers();
});
