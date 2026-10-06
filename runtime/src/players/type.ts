/**
 * type: kinetic typography driven by scroll.
 *   reveal  a passage whose words light up in reading order
 *   stack   lines that slam in one after another
 *   swap    a fixed phrase with one word that rolls through a list
 *   scale   one phrase that starts enormous and settles, then breaks apart
 */
import type { PlayerFactory } from "../lib/types";
import { clamp, easeInOut, smooth } from "../lib/util";

function words(html: string): string[] {
  // one span per word; an accent span covering several words becomes one <em> per word, punctuation stays attached
  const expanded = html.replace(/<em>(.*?)<\/em>/g, (_, inner: string) => inner.split(/\s+/).map((w) => `<em>${w}</em>`).join(" "));
  return expanded.split(/\s+/).filter(Boolean);
}

const factory: PlayerFactory = async (cfg, ctx) => {
  const box = document.createElement("div");
  box.className = "ss-type ss-type--" + cfg.mode;
  ctx.visual.appendChild(box);
  const style = document.createElement("style");
  style.textContent = `
  .ss-type { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 0 var(--gutter); }
  .ss-type__text { font-family: var(--font-display); font-weight: var(--display-weight); letter-spacing: -.035em; line-height: 1.02; max-width: 1500px; }
  .ss-type--reveal .ss-type__text { font-size: clamp(36px, 5.2vw, 92px); text-wrap: balance; }
  .ss-type--reveal span { opacity: .34; transition: opacity .25s linear; }   /* readable before it lights up: the first screen never looks empty */
  .ss-type--reveal span.on { opacity: 1; }
  .ss-type--stack .ss-type__text { font-size: clamp(44px, 8.4vw, 160px); line-height: .92; text-transform: uppercase; }
  .ss-type--stack .ln { display: block; will-change: transform, opacity; }
  .ss-type--swap .ss-type__text { font-size: clamp(44px, 7vw, 132px); text-align: center; }
  .ss-type--swap .roll { display: inline-block; position: relative; overflow: hidden; vertical-align: bottom; height: 1.06em; color: var(--accent); }
  .ss-type--swap .roll i { display: block; height: 1.06em; line-height: 1.06em; font-style: normal; white-space: nowrap; will-change: transform; }
  @media (max-width: 600px) { .ss-type--swap .roll { display: block; margin: 0 auto; } }   /* the rolling word gets its own line on phones */
  .ss-type--scale .ss-type__text { font-size: clamp(60px, 12vw, 240px); white-space: nowrap; text-transform: uppercase; }
  .ss-type--scale .ch { display: inline-block; will-change: transform, opacity; }
  `;
  box.appendChild(style);
  const text = document.createElement("div");
  text.className = "ss-type__text";
  box.appendChild(text);

  let update: (p: number) => void = () => {};
  if (cfg.mode === "reveal") {
    text.innerHTML = words(cfg.text).map((w) => `<span>${w}</span>`).join(" ");
    const spans = [...text.querySelectorAll("span")];
    update = (p) => { const n = Math.round(clamp((p - 0.08) / 0.8) * spans.length); spans.forEach((s, i) => s.classList.toggle("on", i < n)); };
  } else if (cfg.mode === "stack") {
    const lines: string[] = cfg.lines?.length ? cfg.lines : cfg.text.split(/\s*\/\s*|\n/);
    text.innerHTML = lines.map((l) => `<span class="ln">${l}</span>`).join("");
    const els = [...text.querySelectorAll<HTMLElement>(".ln")];
    update = (p) => els.forEach((el, i) => {
      const k = smooth(i / (els.length + 1), (i + 0.9) / (els.length + 1), p);
      el.style.opacity = String(k);
      el.style.transform = `translate3d(${(1 - k) * (i % 2 ? 8 : -8)}vw, 0, 0) skewX(${(1 - k) * -8}deg)`;
    });
  } else if (cfg.mode === "swap") {
    const list: string[] = cfg.words.length ? cfg.words : ["—"];
    text.innerHTML = `${cfg.text} <span class="roll">${list.map((w) => `<i>${w}</i>`).join("")}</span>`;
    const roll = text.querySelector<HTMLElement>(".roll")!, items = [...roll.querySelectorAll<HTMLElement>("i")];
    const width = Math.max(...items.map((i) => i.getBoundingClientRect().width));
    roll.style.width = width + "px";
    update = (p) => {
      const f = clamp(p * 1.1) * (list.length - 1);
      const i = Math.floor(f), t = easeInOut(clamp((f - i - 0.6) / 0.4));
      items.forEach((el) => { el.style.transform = `translateY(${-(i + t) * 100}%)`; });
    };
  } else {
    text.innerHTML = [...(cfg.text as string)].map((c) => `<span class="ch">${c === " " ? "&nbsp;" : c}</span>`).join("");
    const chars = [...text.querySelectorAll<HTMLElement>(".ch")];
    update = (p) => {
      const settle = easeInOut(clamp(p / 0.5));
      text.style.transform = `scale(${2.6 - 1.6 * settle})`;
      const burst = smooth(0.7, 1, p);
      chars.forEach((c, i) => {
        const dir = (i / Math.max(1, chars.length - 1) - 0.5) * 2;
        c.style.transform = `translate3d(${dir * burst * 40}vw, ${Math.sin(i * 2.3) * burst * 30}vh, 0) rotate(${dir * burst * 40}deg)`;
        c.style.opacity = String(1 - burst);
      });
    };
  }
  return { update: (s) => update(s.p) };
};
export default factory;
