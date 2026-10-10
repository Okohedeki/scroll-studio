/**
 * Style effects (theme.style). The compiler writes the style's fx settings into <html data-fx>:
 *
 *   bg       a canvas drawn behind hero, intro and CTA panels: particles | wireframe | ascii
 *   text     how headings and numbers arrive: kinetic | flap | scramble
 *   pointer  track the pointer (holographic foil)
 *   vhs      a running tape counter
 *
 * Every style also gets --sp (page progress 0-1), --sv (eased scroll speed 0-1), --mx/--my (pointer, -0.5..0.5)
 * on <html>, so its stylesheet can react to the scroll without any code of its own. Headings get .fx-seen the
 * first time they come on screen. With reduced motion, backgrounds draw one still frame and text arrives as is.
 */
import { clamp, reducedMotion } from "../lib/util";

export type Bg = (canvas: HTMLCanvasElement, colors: { ink: string; accent: string; accent2: string; bg: string }) => (t: number, sv: number, p: number) => void;

const BGS: Record<string, () => Promise<{ default: Bg }>> = {
  particles: () => import("./particles"),
  wireframe: () => import("./wireframe"),
  ascii: () => import("./ascii"),
};

const HEADINGS = ".ss-hero .ss-h1, .ss-block .ss-h2, .ss-cta .ss-display, .ss-block .ss-display, .ss-step .ss-h1, .ss-step .ss-h2, .ss-step .ss-display";

export function startFx(): void {
  const root = document.documentElement;
  let fx: { bg?: string; text?: string; pointer?: boolean; vhs?: boolean } = {};
  try { fx = JSON.parse(root.dataset.fx || "{}"); } catch { /* no effects */ }

  // ---- scroll and pointer variables, every frame
  let lastY = scrollY, sv = 0, mx = 0, my = 0, tmx = 0, tmy = 0;
  if (fx.pointer) addEventListener("pointermove", (e) => { tmx = e.clientX / innerWidth - 0.5; tmy = e.clientY / innerHeight - 0.5; }, { passive: true });
  const counter = fx.vhs ? Object.assign(document.createElement("div"), { className: "fx-counter", ariaHidden: "true" }) : null;
  if (counter) document.body.appendChild(counter);

  // ---- headings: .fx-seen once on screen; text effects split them first
  const heads = [...document.querySelectorAll<HTMLElement>(HEADINGS)];
  const nums = [...document.querySelectorAll<HTMLElement>(".ss-stats .ss-v, .ss-product__stats .ss-v")];
  if (fx.text && !reducedMotion) import("./text").then((m) => m.prepare(fx.text!, heads, nums));
  const io = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (!e.isIntersecting) return;
    e.target.classList.add("fx-seen");
    e.target.dispatchEvent(new CustomEvent("fx:seen"));
    io.unobserve(e.target);
  }), { threshold: 0.35 });
  [...heads, ...nums].forEach((h) => io.observe(h));

  // ---- canvas backgrounds behind the big quiet panels
  const layers: { host: HTMLElement; canvas: HTMLCanvasElement; draw: ReturnType<Bg>; on: boolean }[] = [];
  if (fx.bg && BGS[fx.bg]) {
    const hosts = new Set<HTMLElement>();
    document.querySelectorAll<HTMLElement>(".ss-hero:not(.ss-hero--media), .ss-cta").forEach((h) => hosts.add(h));
    document.querySelectorAll<HTMLElement>(".ss-intro2").forEach((i) => { const s = i.closest<HTMLElement>(".ss-block"); if (s) hosts.add(s); });
    BGS[fx.bg]().then(({ default: make }) => {
      const cs = getComputedStyle(root);
      const colors = { ink: cs.getPropertyValue("--ink").trim(), accent: cs.getPropertyValue("--accent").trim(),
                       accent2: cs.getPropertyValue("--accent-2").trim(), bg: cs.getPropertyValue("--bg").trim() };
      const vis = new IntersectionObserver((entries) => entries.forEach((e) => {
        const l = layers.find((x) => x.host === e.target);
        if (l) l.on = e.isIntersecting;
      }));
      hosts.forEach((host) => {
        const canvas = document.createElement("canvas");
        canvas.className = "fx-bg";
        canvas.setAttribute("aria-hidden", "true");
        host.prepend(canvas);
        if (getComputedStyle(host).position === "static") host.style.position = "relative";
        host.style.isolation = "isolate";
        const l = { host, canvas, draw: make(canvas, colors), on: true };
        layers.push(l);
        vis.observe(host);
        if (reducedMotion) l.draw(4, 0, 0.3);
      });
      const style = document.createElement("style");
      style.textContent = ".fx-bg { position: absolute; inset: 0; width: 100%; height: 100%; z-index: -1; pointer-events: none; }";
      document.head.appendChild(style);
    });
  }

  const t0 = performance.now();
  function frame(now: number) {
    const dy = Math.abs(scrollY - lastY);
    lastY = scrollY;
    sv += (clamp(dy / 60) - sv) * 0.12;
    mx += (tmx - mx) * 0.08; my += (tmy - my) * 0.08;
    const doc = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    const p = clamp(scrollY / doc);
    root.style.setProperty("--sp", p.toFixed(4));
    root.style.setProperty("--sv", (reducedMotion ? 0 : sv).toFixed(3));
    if (fx.pointer) { root.style.setProperty("--mx", mx.toFixed(3)); root.style.setProperty("--my", my.toFixed(3)); }
    const t = (now - t0) / 1000;
    if (counter) {
      const s = Math.floor(t + p * 3600);
      counter.textContent = `SP ${String(Math.floor(s / 3600)).padStart(1, "0")}:${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    }
    if (!reducedMotion) for (const l of layers) if (l.on) l.draw(t, sv, p);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

/** Size a canvas to its box at device resolution (capped); returns the CSS size. */
export function fit(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, maxDpr = 1.5): [number, number] {
  const w = canvas.clientWidth, h = canvas.clientHeight, d = Math.min(devicePixelRatio || 1, maxDpr);
  if (canvas.width !== Math.round(w * d) || canvas.height !== Math.round(h * d)) {
    canvas.width = Math.round(w * d);
    canvas.height = Math.round(h * d);
  }
  ctx.setTransform(d, 0, 0, d, 0, 0);
  return [w, h];
}
