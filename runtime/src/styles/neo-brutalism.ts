/**
 * Neo-brutalism: a desk you fill up and can mess with.
 *
 * Scroll doesn't scrub anything here: crossing a threshold is an EVENT. Tiles, windows, notes and stickers slap
 * onto the surface (a fast drop, a spring overshoot, a small settle rotation, the hard shadow arriving at impact)
 * and then stay where they landed; scrolling back up doesn't undo them, so the page accumulates. The headline's
 * words land one by one on their own marker blocks and a starburst whacks onto its corner last. The feature list is
 * a pinned deck: each card slaps on top of the last. Marquee bands run on scroll velocity and reverse with
 * direction. Anything marked data-nb-drag can be grabbed and flung (with inertia, kept inside its section) or
 * nudged with the arrow keys; buttons sink into the page; the CTA throws flat confetti.
 * Reduced motion: everything is already on the desk, bands stand still, dragging still works.
 */
import { $, $$, onFrame, pinSequence, reduced } from "./_kit";
import { clamp } from "../lib/util";

const MARKS = ["#ffc900", "#b8ff5c", "#ff90e8", "#7fd3ff", "#ff7a5c", "#a388ee"];
const seeded = (i: number) => { const x = Math.sin(i * 12.9898 + 4.1) * 43758.5453; return x - Math.floor(x); };

export default function start(): void {
  const root = document.documentElement;
  if (!reduced) root.classList.add("nb-js");
  let zTop = 70;

  // ---------------------------------------------------------------- the slap
  function slap(el: HTMLElement, instant = false, seed = 0) {
    if (el.classList.contains("is-down")) return;
    el.classList.add("is-down");
    if (instant || reduced) return;
    if (el.dataset.nbSlap === "pop") {     // windows pop open hard: no fade, a tiny overshoot
      el.animate([{ transform: "scale(.88)" }, { transform: "scale(1.025)", offset: 0.6 }, { transform: "none" }], { duration: 240, easing: "cubic-bezier(.2,.9,.3,1)" });
      return;
    }
    const r = (seeded(seed) - 0.5) * 22, dx = (seeded(seed + 3) - 0.5) * 60;
    el.animate([
      { transform: `translate(${dx.toFixed(0)}px, -120px) scale(1.24) rotate(${r.toFixed(1)}deg)`, boxShadow: "0 0 0 0 #000", offset: 0 },
      { transform: `translate(0, 0) scale(.95) rotate(${(-r * 0.22).toFixed(1)}deg)`, offset: 0.52 },
      { transform: `scale(1.03) rotate(${(r * 0.08).toFixed(1)}deg)`, offset: 0.76 },
      { transform: "none" },
    ], { duration: 460, easing: "cubic-bezier(.22,.9,.32,1)" });
    if (el.querySelector("[data-nb-flip]")) flip(el.querySelector<HTMLElement>("[data-nb-flip]")!);
  }

  // stats count by FLIPPING: three stepped jumps, then the real number lands with a bounce
  function flip(v: HTMLElement) {
    const t = [...v.childNodes].find((n) => n.nodeType === 3);
    if (!t) return;
    const final = t.textContent || "";
    if (!/\d/.test(final)) return;
    let i = 0;
    const tick = () => {
      if (i++ < 3) {
        t.textContent = final.replace(/\d/g, () => String(Math.floor(Math.random() * 10)));
        setTimeout(tick, 75);
      } else {
        t.textContent = final;
        v.animate([{ transform: "scale(1.3) rotate(-5deg)" }, { transform: "scale(.94) rotate(1deg)", offset: 0.6 }, { transform: "none" }], { duration: 300, easing: "cubic-bezier(.3,1.4,.5,1)" });
      }
    };
    setTimeout(tick, 220);
  }

  // ---------------------------------------------------------------- headline: words on marker blocks, sticker last
  const h1 = $<HTMLElement>("[data-nb-words]");
  const badge = $<HTMLElement>('[data-nb-slap="last"]', h1?.closest(".nb-hero") || document);
  let heroDone = 0;
  if (h1 && !reduced) {
    const label = (h1.textContent || "").replace(/\s+/g, " ").trim();
    const words: HTMLElement[] = [];
    const make = (html: string) => {
      const w = document.createElement("span"); w.className = "nb-word"; w.setAttribute("aria-hidden", "true");
      w.style.setProperty("--c", MARKS[words.length % MARKS.length]);
      w.style.setProperty("--r", `${((seeded(words.length + 9) - 0.5) * 5).toFixed(1)}deg`);
      w.innerHTML = `<span class="nb-mark"></span><span class="nb-txt">${html}</span>`;
      words.push(w); return w;
    };
    const frag = document.createDocumentFragment();
    h1.childNodes.forEach((n) => {
      const tag = n.nodeType === 1 ? (n as HTMLElement).tagName.toLowerCase() : "";
      (n.textContent || "").split(/\s+/).filter(Boolean).forEach((wd) => {
        const safe = wd.replace(/&/g, "&amp;").replace(/</g, "&lt;");
        frag.appendChild(make(tag ? `<${tag}>${safe}</${tag}>` : safe)); frag.appendChild(document.createTextNode(" "));
      });
    });
    h1.textContent = ""; h1.appendChild(frag); h1.setAttribute("aria-label", label);
    words.forEach((w, i) => setTimeout(() => {
      w.classList.add("is-down");
      w.querySelector(".nb-mark")!.animate([{ transform: "scale(1.35) rotate(7deg)", opacity: 0 }, { transform: "scale(.95)", opacity: 1, offset: 0.6 }, { transform: "none" }], { duration: 260, easing: "cubic-bezier(.2,.9,.3,1)" });
      w.querySelector(".nb-txt")!.animate([{ transform: "translateY(-70%) rotate(-7deg)", opacity: 0 }, { transform: "translateY(5%)", opacity: 1, offset: 0.6 }, { transform: "none" }], { duration: 320, delay: 90, easing: "cubic-bezier(.2,.9,.3,1)", fill: "backwards" });
    }, 150 + i * 150));
    heroDone = 150 + words.length * 150 + 260;
    if (badge) setTimeout(() => slap(badge, false, 99), heroDone);
  } else if (badge) slap(badge, true);

  // ---------------------------------------------------------------- threshold slaps (they stay)
  const deckSec = $<HTMLElement>("[data-nb-deck]");
  const deckOn = !!deckSec && !reduced && !matchMedia("(max-width: 900px)").matches;
  const targets = $$<HTMLElement>("[data-nb-slap]").filter((el) => el !== badge);
  if (!deckOn) targets.push(...$$<HTMLElement>("[data-nb-card]"));
  const queue = new Map<Element, number>();   // per-section stagger
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting && e.boundingClientRect.bottom > 0) continue;
      const el = e.target as HTMLElement;
      io.unobserve(el);
      if (e.boundingClientRect.bottom <= 0) { slap(el, true); continue; }   // already scrolled past: it is simply there
      const sec = el.closest("section, footer") || document.body;
      const n = queue.get(sec) ?? 0;
      queue.set(sec, n + 1);
      const inHero = !!el.closest(".nb-hero");
      const delay = (inHero ? Math.max(0, heroDone - 300) : 0) + n * 85 + (el.dataset.nbSlap === "last" ? 260 : 0);
      setTimeout(() => slap(el, false, targets.indexOf(el)), delay);
    }
  }, { rootMargin: "0px 0px -14% 0px" });
  targets.forEach((el) => io.observe(el));

  // ---------------------------------------------------------------- the deck: each feature card slaps on top of the last
  if (deckSec && deckOn) {
    root.classList.add("nb-deck-on");
    const cards = $$<HTMLElement>("[data-nb-card]", deckSec);
    const count = $<HTMLElement>("[data-nb-count]", deckSec);
    cards.forEach((c, i) => c.style.setProperty("--r", `${((seeded(i + 21) - 0.5) * 9).toFixed(1)}deg`));
    let shown = 0;
    pinSequence(deckSec, cards.length, (s) => {
      cards.forEach((c, i) => { if (s >= i + 0.2 && !c.classList.contains("is-down")) { slap(c, false, i + 40); shown++; } });
      if (count) count.textContent = String(Math.max(shown, cards.filter((c) => c.classList.contains("is-down")).length));
    }, 0.62);
  }

  // ---------------------------------------------------------------- a scribble under the problem, drawn by scroll
  const scribbles = $$<HTMLElement>("[data-nb-scribble] em").map((em) => {
    em.style.cssText = "background:none;border:0;box-shadow:none;transform:none;padding:0";
    em.classList.add("nb-scrib-host");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "nb-scribble"); svg.setAttribute("viewBox", "0 0 200 20"); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = '<path d="M2 12 C 30 4, 52 18, 80 10 S 130 4, 160 11 S 190 14, 198 8 M 12 17 C 60 12, 120 15, 186 13"/>';
    em.appendChild(svg);
    const path = svg.querySelector("path")!;
    const len = path.getTotalLength();
    path.style.strokeDasharray = String(len);
    path.style.strokeDashoffset = reduced ? "0" : String(len);
    return { em, path, len };
  });

  // ---------------------------------------------------------------- the hand-drawn dashed path between the steps
  const pathWrap = $<HTMLElement>("[data-nb-path]");
  let stepPath: SVGPathElement | null = null, stepLen = 0, stepMask: SVGPathElement | null = null;
  function layoutPath() {
    if (!pathWrap) return;
    const svg = pathWrap.querySelector<SVGSVGElement>(".nb-arrow")!;
    const box = pathWrap.getBoundingClientRect();
    const pts = $$<HTMLElement>(".nb-step__n", pathWrap).map((n) => { const r = n.getBoundingClientRect(); return [r.left - box.left + r.width / 2, r.top - box.top + r.height / 2]; });
    if (pts.length < 2) { svg.innerHTML = ""; return; }
    let d = `M${pts[0][0].toFixed(0)} ${pts[0][1].toFixed(0)}`;
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      const bend = (i % 2 ? -1 : 1) * 46;
      d += ` C${(x0 + (x1 - x0) * 0.35).toFixed(0)} ${(y0 + bend).toFixed(0)}, ${(x0 + (x1 - x0) * 0.65).toFixed(0)} ${(y1 + bend).toFixed(0)}, ${x1.toFixed(0)} ${y1.toFixed(0)}`;
    }
    svg.setAttribute("viewBox", `0 0 ${box.width.toFixed(0)} ${box.height.toFixed(0)}`);
    svg.innerHTML = `<defs><mask id="nb-path-mask" maskUnits="userSpaceOnUse"><path d="${d}" stroke="#fff" stroke-width="10" fill="none"/></mask></defs><path d="${d}" mask="url(#nb-path-mask)"/>`;
    stepMask = svg.querySelector("mask path"); stepPath = svg.querySelector(":scope > path");
    stepLen = stepMask!.getTotalLength();
    stepMask!.style.strokeDasharray = String(stepLen);
    stepMask!.style.strokeDashoffset = reduced ? "0" : String(stepLen);
  }
  layoutPath();
  addEventListener("resize", layoutPath);
  document.fonts?.ready.then(layoutPath);
  addEventListener("load", layoutPath);

  // ---------------------------------------------------------------- the footer wordmark spans the viewport, whatever the name
  const mark = $<HTMLElement>(".nb-foot__mark");
  const fitMark = () => {
    if (!mark) return;
    mark.style.fontSize = "";
    const w = mark.scrollWidth, room = mark.clientWidth;
    if (w > room) mark.style.fontSize = `${(parseFloat(getComputedStyle(mark).fontSize) * room / w * 0.98).toFixed(1)}px`;
  };
  fitMark();
  addEventListener("resize", fitMark);
  document.fonts?.ready.then(fitMark);

  // ---------------------------------------------------------------- marquee bands on scroll velocity
  const bands = $$<HTMLElement>("[data-nb-band]").map((band) => {
    const row = $<HTMLElement>(".nb-band__row", band)!;
    row.innerHTML += row.innerHTML;
    const b = { band, row, dir: Number(band.dataset.nbBand) || 1, x: 0, speed: 0, unit: row.scrollWidth / 2, hold: false };
    band.addEventListener("pointerenter", () => { b.hold = true; });
    band.addEventListener("pointerleave", () => { b.hold = false; });
    return b;
  });
  addEventListener("resize", () => bands.forEach((b) => { b.unit = b.row.scrollWidth / 2; }));

  // ---------------------------------------------------------------- the nav chip for the current section
  const chips = $$<HTMLAnchorElement>("[data-nb-nav]").map((a) => ({ a, el: document.getElementById((a.getAttribute("href") || "").slice(1)) })).filter((c) => c.el);

  let sdir = 1;
  onFrame(({ v, dt, vh }) => {
    if (Math.abs(v) > 0.4) sdir = Math.sign(v);
    for (const b of bands) {
      if (reduced || !b.unit) continue;
      const r = b.band.getBoundingClientRect();
      if (r.bottom < -200 || r.top > vh + 200) continue;
      const want = b.hold ? 0 : 55 + Math.abs(v) * 34;
      b.speed += (want - b.speed) * 0.08;
      b.x -= b.speed * dt * b.dir * sdir;
      b.x = ((b.x % b.unit) - b.unit) % b.unit;
      b.row.style.transform = `translate3d(${b.x.toFixed(1)}px, 0, 0)`;
    }
    for (const s of scribbles) {
      if (reduced) break;
      const r = s.em.getBoundingClientRect();
      const k = clamp((vh * 0.85 - r.top) / (vh * 0.35));
      s.path.style.strokeDashoffset = (s.len * (1 - k)).toFixed(1);
    }
    if (stepMask && pathWrap && !reduced) {
      const r = pathWrap.getBoundingClientRect();
      const k = clamp((vh * 0.8 - r.top) / Math.max(1, r.height * 0.85));
      stepMask.style.strokeDashoffset = (stepLen * (1 - k)).toFixed(1);
    }
    let cur: HTMLElement | null = null;
    for (const c of chips) if (c.el!.getBoundingClientRect().top < vh * 0.5) cur = c.a;
    chips.forEach((c) => c.a.classList.toggle("is-current", c.a === cur));
  });

  // ---------------------------------------------------------------- grab and fling
  $$<HTMLElement>("[data-nb-drag]").forEach((el) => {
    let dx = 0, dy = 0, sx = 0, sy = 0, ox = 0, oy = 0, vx = 0, vy = 0, lx = 0, ly = 0, lt = 0, moved = false, raf = 0, id = -1;
    const small = el.offsetWidth < 220;
    if (small) el.style.touchAction = "none";
    const set = () => { el.style.setProperty("--dx", `${dx.toFixed(1)}px`); el.style.setProperty("--dy", `${dy.toFixed(1)}px`); };
    const bounds = () => {
      const sec = (el.closest("section, footer") as HTMLElement) || document.body;
      const s = sec.getBoundingClientRect(), r = el.getBoundingClientRect();
      const bx = r.left - dx, by = r.top - dy;     // where it sits with no drag
      return { minX: s.left - bx - r.width * 0.4, maxX: s.right - bx - r.width * 0.6, minY: s.top - by, maxY: s.bottom - by - r.height * 0.5 };
    };
    const keep = () => { const b = bounds(); dx = clamp(dx, b.minX, b.maxX); dy = clamp(dy, b.minY, b.maxY); };
    el.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || (e.target as HTMLElement).closest("a, button, summary, input, textarea, select")) return;
      if (e.pointerType === "touch" && !small) return;          // big things scroll the page on touch
      if (el.classList.contains("nb-win") && !(e.target as HTMLElement).closest(".nb-win__bar")) return;   // windows move by their title bar
      id = e.pointerId; el.setPointerCapture(id);
      cancelAnimationFrame(raf);
      sx = e.clientX; sy = e.clientY; ox = dx; oy = dy; lx = sx; ly = sy; lt = performance.now(); vx = vy = 0; moved = false;
      el.classList.add("is-dragging"); el.style.zIndex = String(++zTop);
      e.preventDefault();
    });
    el.addEventListener("pointermove", (e) => {
      if (e.pointerId !== id) return;
      dx = ox + e.clientX - sx; dy = oy + e.clientY - sy;
      if (Math.abs(e.clientX - sx) + Math.abs(e.clientY - sy) > 4) moved = true;
      const t = performance.now(), d = Math.max(1, t - lt);
      vx = (e.clientX - lx) / d * 16; vy = (e.clientY - ly) / d * 16; lx = e.clientX; ly = e.clientY; lt = t;
      set();
    });
    const end = (e: PointerEvent) => {
      if (e.pointerId !== id) return;
      id = -1; el.classList.remove("is-dragging");
      const glide = () => {          // inertia, then it stays where it lands
        vx *= 0.9; vy *= 0.9; dx += vx; dy += vy;
        const b = bounds();
        if (dx < b.minX || dx > b.maxX) vx *= -0.4;
        if (dy < b.minY || dy > b.maxY) vy *= -0.4;
        keep(); set();
        if (Math.abs(vx) + Math.abs(vy) > 0.3 && !reduced) raf = requestAnimationFrame(glide);
      };
      raf = requestAnimationFrame(glide);
    };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("click", (e) => { if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; } }, true);
    el.addEventListener("keydown", (e) => {
      if (e.target !== el) return;
      const step = e.shiftKey ? 40 : 12;
      const k: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
      if (!k[e.key]) return;
      e.preventDefault();
      dx += k[e.key][0]; dy += k[e.key][1]; keep(); set();
      el.style.zIndex = String(++zTop);
    });
  });

  // ---------------------------------------------------------------- confetti (flat shapes, no glow)
  document.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest?.("[data-nb-confetti]") as HTMLElement | null;
    if (!btn || reduced) return;
    const r = btn.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    for (let i = 0; i < 40; i++) {
      const p = document.createElement("span");
      p.className = "nb-confetti"; p.setAttribute("aria-hidden", "true");
      const s = 10 + Math.random() * 12, shape = i % 3;
      Object.assign(p.style, { left: `${cx}px`, top: `${cy}px`, width: `${s}px`, height: `${shape === 1 ? s * 0.5 : s}px`, background: MARKS[i % MARKS.length],
        borderRadius: shape === 0 ? "50%" : "2px", clipPath: shape === 2 ? "polygon(50% 0, 100% 100%, 0 100%)" : "", borderWidth: shape === 2 ? "0" : "" });
      document.body.appendChild(p);
      const a = Math.random() * Math.PI * 2, sp = 180 + Math.random() * 320, tx = Math.cos(a) * sp, ty = Math.sin(a) * sp - 160;
      p.animate([{ transform: "translate(-50%,-50%) rotate(0)" }, { transform: `translate(calc(-50% + ${tx * 0.7}px), calc(-50% + ${ty * 0.7}px)) rotate(${Math.random() * 400}deg)`, offset: 0.45 },
        { transform: `translate(calc(-50% + ${tx}px), calc(-50% + ${ty + 520}px)) rotate(${Math.random() * 900}deg)` }], { duration: 1100 + Math.random() * 500, easing: "cubic-bezier(.2,.6,.4,1)" })
        .onfinish = () => p.remove();
    }
  });
}
