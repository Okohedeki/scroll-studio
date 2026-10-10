/**
 * Anime intro: the scroll wheel is the playhead of a TV anime opening.
 *
 * Every .ai-sec pins (a track as long as its shots, a sticky stage), and consecutive sections overlap so the next
 * one takes the screen on the exact frame the last one ends: a HARD CUT, never a slide or a fade. Inside a shot the
 * camera moves with the playhead (quantised to twelve-ish steps a shot, animation "on twos"); crossing a cut swaps
 * the shot on one frame and fires its entrance (expo-out, a few frames). Some shots freeze part-way (name cards);
 * the chorus is one long scrubbed sakuga shot. One canvas, moved into whichever shot is live, draws the focus lines,
 * speed lines, debris and clouds procedurally, redrawn every other frame for the hand-drawn boil.
 *
 * Photosensitivity: impacts are "safe": shake + lines + scale, no luminance flash, every shot dark, and impact
 * effects are rate-limited by wall-clock time however fast the visitor scrolls. Reduced motion: no opening at all;
 * the page stays the storyboard (numbered still frames) the stylesheet draws by default.
 */
import { $, $$, onFrame, reduced } from "./_kit";
import { clamp, rng } from "../lib/util";

type Shot = {
  el: HTMLElement; sec: Sec; index: number; len: number; start: number; kind: string; fx: string[]; dir: number;
  focus: [number, number]; impact: number; freeze: number; impactAt: number; song: string; hit: boolean;
};
type Sec = { el: HTMLElement; shots: Shot[]; total: number; track: HTMLElement; stage: HTMLElement; overlap: boolean; active: number };

const STEPS = 14;          // camera positions per shot: movement inside a shot is held, then jumps (on twos)

export default function start(): void {
  const root = document.documentElement;
  const main = $("main");

  // ---------------------------------------------------------------- page furniture (also in the storyboard)
  const eye = $<HTMLElement>(".ai-sec--eyecatch");
  if (eye && main) {
    const kids = [...main.children].filter((c) => c.matches(".ai-sec, section, .ss-block"));
    if (kids.length >= 3) { main.insertBefore(eye, kids[Math.floor(kids.length / 2)]); eye.hidden = false; }
  }
  const lineup = $(".ai-lineup");
  if (lineup) $$(".ai-namecard__name").forEach((n, i) => {
    const s = document.createElement("span"); s.textContent = n.textContent || ""; s.style.setProperty("--i", String(i)); lineup.appendChild(s);
  });
  menu();
  if (reduced) return;                       // the storyboard is the reduced-motion version

  root.classList.add("ai-op");
  const siteName = $(".ai-hud__logo b")?.textContent || document.title;

  // ---------------------------------------------------------------- sections become pinned tracks of shots
  const flowNext = (el: Element) => el.nextElementSibling || (el.parentElement?.tagName === "MAIN" ? el.parentElement.nextElementSibling : null);
  const secs: Sec[] = [];
  const shots: Shot[] = [];
  $$<HTMLElement>(".ai-sec").filter((s) => !s.hidden).forEach((el, si, list) => {
    const els = $$<HTMLElement>(":scope > .ai-shot", el);
    if (!els.length) return;
    const track = document.createElement("div"); track.className = "ai-track";
    const stage = document.createElement("div"); stage.className = "ai-stage";
    els.forEach((s) => stage.appendChild(s));
    track.appendChild(stage); el.appendChild(track);
    const sec: Sec = { el, shots: [], total: 0, track, stage, overlap: si > 0 && flowNext(list[si - 1]) === el, active: -1 };
    for (const s of els) {
      const d = s.dataset;
      const f = (d.focus || "0.5,0.5").split(",").map(Number) as [number, number];
      const shot: Shot = { el: s, sec, index: shots.length, len: parseFloat(d.len || "1"), start: sec.total, kind: (s.className.match(/ai-shot--(\w+)/) || [])[1] || "",
        fx: (d.fx || "").split(/\s+/).filter(Boolean), dir: Number(d.dir || 1), focus: f, impact: Number(d.impact || 0),
        freeze: d.freeze ? Number(d.freeze) : 2, impactAt: d.impactAt ? Number(d.impactAt) : 2, song: d.song || "", hit: false };
      sec.total += shot.len;
      sec.shots.push(shot); shots.push(shot);
    }
    secs.push(sec);
  });
  if (!secs.length) return;

  let vh = innerHeight;
  function layout() {
    vh = innerHeight;
    root.style.setProperty("--ai-vh", `${vh}px`);
    for (const s of secs) {
      s.track.style.height = `${(s.total + 1) * vh}px`;
      s.el.style.marginTop = s.overlap ? `${-vh}px` : "";
    }
  }
  layout();
  addEventListener("resize", layout);

  // ---------------------------------------------------------------- the effects layer: one canvas
  const cv = document.createElement("canvas");
  cv.className = "ai-fx"; cv.setAttribute("aria-hidden", "true");
  const ctx = cv.getContext("2d")!;
  let W = 0, H = 0, dpr = 1;
  function sizeCanvas() {
    dpr = Math.min(2, devicePixelRatio || 1); W = innerWidth; H = innerHeight;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  }
  sizeCanvas();
  addEventListener("resize", sizeCanvas);

  let live: Shot | null = null;
  let cutAt = 0, lastImpact = -1e9, shakeAmp = 0, shakeT0 = 0, frameNo = 0, extraFocusT = -1e9, extraFocus: [number, number] = [0.5, 0.5];
  let debris: { x: number; y: number; vx: number; vy: number; r: number; va: number; a: number; c: string }[] = [];
  const now = () => performance.now();

  function impact(amp: number, at?: [number, number], shards = false) {
    const t = now();
    if (t - lastImpact < 450) return;        // wall-clock limit: never a burst of impacts, however fast the scroll
    lastImpact = t;
    shakeAmp = amp; shakeT0 = t;
    if (at) { extraFocus = at; extraFocusT = t; }
    if (shards) {
      const R = rng(Math.floor(t));
      debris = Array.from({ length: 16 }, () => {
        const a = R(0, Math.PI * 2), sp = R(700, 1500);
        return { x: W / 2, y: H / 2, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, r: R(8, 26), va: R(-12, 12), a: R(0, 6), c: R() > 0.5 ? "#ffe600" : "#fff7ee" };
      });
    }
  }

  function drawFocus(cx: number, cy: number, strength: number, seed: number) {
    const R = rng(seed), out = Math.hypot(W, H) * 0.75;
    ctx.fillStyle = `rgba(255, 247, 238, ${0.16 + 0.42 * strength})`;
    ctx.beginPath();
    for (let i = 0; i < 110; i++) {
      const a = R(0, Math.PI * 2), sp = R(0.002, 0.011);
      const inner = Math.min(W, H) * R(0.3, 0.52) * (1.18 - 0.3 * strength);
      ctx.moveTo(cx + Math.cos(a - sp) * out, cy + Math.sin(a - sp) * out);
      ctx.lineTo(cx + Math.cos(a + sp) * out, cy + Math.sin(a + sp) * out);
      ctx.lineTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner);
    }
    ctx.fill();
  }
  function drawSpeed(dir: number, density: number, seed: number, t: number) {
    const R = rng(seed);
    ctx.fillStyle = `rgba(255, 247, 238, ${0.1 + 0.14 * density})`;
    ctx.beginPath();
    const n = Math.round(26 + 40 * density);
    for (let i = 0; i < n; i++) {
      const y = R(0, H), th = R(1, 3.5) * (0.6 + density * 0.5), len = W * R(0.18, 0.7);
      const x0 = ((R(0, W * 1.6) + t * 2600 * dir) % (W * 1.6) + W * 1.6) % (W * 1.6) - W * 0.3;
      const tail = x0 - len * dir;
      ctx.moveTo(x0, y); ctx.lineTo(tail, y - th / 2); ctx.lineTo(tail, y + th / 2);
    }
    ctx.fill();
  }
  function drawClouds(k: number) {
    const R = rng(11);
    for (let c = 0; c < 6; c++) {
      const bx = R(-0.2, 1.1) * W + k * W * 0.22 * (c % 2 ? 1 : 0.6), by = R(0.08, 0.6) * H, s = R(0.6, 1.4) * Math.min(W, H) * 0.09;
      for (let tone = 0; tone < 2; tone++) {
        ctx.fillStyle = tone ? "rgba(214, 196, 236, .5)" : "rgba(104, 86, 150, .55)";
        ctx.beginPath();
        for (let j = 0; j < 5; j++) {
          const ox = (j - 2) * s * 0.9, oy = -Math.abs(j - 2) * -s * 0.18 - (j % 2) * s * 0.35 - (tone ? s * 0.18 : 0);
          ctx.moveTo(bx + ox + s, by + oy); ctx.arc(bx + ox, by + oy, s * (tone ? 0.82 : 1), 0, Math.PI * 2);
        }
        ctx.fill();
      }
    }
  }

  function drawFx(t: number, k: number) {
    frameNo++;
    if (frameNo % 2 && !debris.length) return;          // the boil: lines are redrawn on twos
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (!live) return;
    const T = now(), since = T - cutAt, seed = Math.floor(T / 34);
    const fx = live.fx;
    if (fx.includes("clouds")) drawClouds(k);
    if (fx.includes("speed")) {
      const frozen = live.kind === "cast" && k >= live.freeze;
      if (!frozen) drawSpeed(live.dir, fx.includes("whip") && since < 320 ? 1.6 : 0.45, seed, t);
    }
    if (fx.includes("focus")) drawFocus(live.focus[0] * W, live.focus[1] * H, Math.exp(-since / 380), seed);
    if (T - extraFocusT < 700) drawFocus(extraFocus[0] * W, extraFocus[1] * H, Math.exp(-(T - extraFocusT) / 300), seed + 7);
    if (debris.length) {
      const dt = 1 / 60;
      debris = debris.filter((d) => (d.r *= 0.985) > 3 && d.x > -50 && d.x < W + 50 && d.y > -50 && d.y < H + 50);
      for (const d of debris) {
        d.x += d.vx * dt; d.y += d.vy * dt; d.vy += 900 * dt; d.a += d.va * dt;
        ctx.save(); ctx.translate(d.x, d.y); ctx.rotate(d.a); ctx.fillStyle = d.c;
        ctx.beginPath(); ctx.moveTo(0, -d.r); ctx.lineTo(d.r * 0.6, d.r * 0.7); ctx.lineTo(-d.r * 0.5, d.r * 0.4); ctx.fill(); ctx.restore();
      }
    }
  }

  // ---------------------------------------------------------------- HUD: song section, staff credit, cut number, timecode
  const hud = { song: $("[data-song]"), credit: $("[data-credit]"), cut: $("[data-cut]"), tc: $("[data-tc]") };
  const roles = ["Original concept", "Series composition", "Storyboard", "Animation director", "Key animation", "Colour design", "Theme song", "Director"];
  const names = [siteName, ...$$(".ai-menu a").map((a) => (a.childNodes[a.childNodes.length - 1]?.textContent || "").trim()).filter(Boolean), "Scroll Studio"];

  function onCut(shot: Shot) {
    live = shot;
    cutAt = now();
    shot.el.insertBefore(cv, shot.el.querySelector(".ai-cam"));
    shot.hit = false;
    if (hud.song) hud.song.textContent = shot.song;
    if (hud.cut) hud.cut.textContent = `C-${String(shot.index + 1).padStart(3, "0")}`;
    if (hud.credit) hud.credit.innerHTML = `<b>${roles[shot.index % roles.length]}</b><span></span>`;
    hud.credit?.querySelector("span")?.append(names[shot.index % names.length]);
    if (shot.impact) impact(shot.impact, undefined, shot.fx.includes("debris"));
    if (shot.kind === "power") countUp(shot.el);
  }

  function countUp(el: HTMLElement) {
    const v = el.querySelector<HTMLElement>(".ai-power__v");
    if (!v) return;
    const final = v.dataset.final ?? (v.dataset.final = v.textContent || "");
    const n = parseFloat(final.replace(/,/g, ""));
    if (!isFinite(n) || n === 0) return;
    el.querySelector(".ai-power")?.setAttribute("aria-label", final + (el.querySelector(".ai-power__u")?.textContent || ""));
    const dec = (final.split(".")[1] || "").length, t0 = now();
    const tick = () => {
      const p = clamp((now() - t0 - 200) / 260);
      v.textContent = p >= 1 ? final : (Math.floor(p * 6) / 6 * n).toFixed(dec);   // stepped, on twos
      if (p < 1 && live?.el === el) requestAnimationFrame(tick); else v.textContent = final;
    };
    requestAnimationFrame(tick);
  }

  // ---------------------------------------------------------------- the playhead
  onFrame(({ t }) => {
    let cur: Shot | null = null, curK = 0;
    for (const S of secs) {
      const r = S.track.getBoundingClientRect();
      const started = !S.overlap || r.top <= 0.5;
      const onScreen = r.bottom > 0 && r.top < vh;
      S.stage.classList.toggle("is-shown", started && onScreen);
      if (!(started && onScreen)) continue;
      const s = clamp(-r.top / vh, 0, S.total - 1e-4);
      let i = S.shots.findIndex((sh) => s < sh.start + sh.len);
      if (i < 0) i = S.shots.length - 1;
      const sh = S.shots[i];
      if (i !== S.active) {
        S.shots.forEach((x, j) => x.el.classList.toggle("is-on", j === i));
        S.active = i;
      }
      const k = clamp((s - sh.start) / sh.len);
      const kq = Math.floor(Math.min(k, sh.freeze) * STEPS) / STEPS;
      sh.el.style.setProperty("--k", kq.toFixed(3));
      sh.el.classList.toggle("is-freeze", k >= sh.freeze);
      if (r.top <= 0.5 || S === secs[0]) { cur = sh; curK = k; }
    }
    if (cur && cur !== live) onCut(cur);
    if (cur) {
      if (cur.kind === "sakuga") sakuga(cur, curK);
      const g = clamp(scrollY / Math.max(1, document.documentElement.scrollHeight - vh)) * 90;
      if (hud.tc) hud.tc.textContent = `${String(Math.floor(g / 60)).padStart(2, "0")}:${String(Math.floor(g % 60)).padStart(2, "0")}`;
    }
    // shake: decaying noise on the live stage, about six frames
    if (live) {
      const e = (now() - shakeT0) / 1000;
      const a = shakeAmp * Math.exp(-e * 18);
      live.sec.stage.style.transform = a > 0.4 ? `translate(${((Math.random() - 0.5) * 2 * a).toFixed(1)}px, ${((Math.random() - 0.5) * 2 * a).toFixed(1)}px)` : "";
    }
    drawFx(t, curK);
  });

  // the sakuga shot: options flick on twos, then the chosen one takes the hit
  function sakuga(shot: Shot, k: number) {
    const opts = $$<HTMLElement>(".ss-app__opt", shot.el);
    if (!opts.length) return;
    const chosen = Math.max(0, opts.findIndex((o) => o.classList.contains("is-on")));
    let hit = -1;
    if (k >= shot.impactAt) hit = chosen;
    else if (k > 0.25) hit = Math.floor(((k - 0.25) / (shot.impactAt - 0.25)) * opts.length * 2) % opts.length;
    opts.forEach((o, i) => o.classList.toggle("is-hit", i === hit));
    if (k >= shot.impactAt && !shot.hit) {
      shot.hit = true;
      const r = opts[chosen].getBoundingClientRect();
      impact(6, [(r.left + r.width / 2) / innerWidth, (r.top + r.height / 2) / innerHeight]);
    }
    if (k < shot.impactAt - 0.05) shot.hit = false;
  }

  // ---------------------------------------------------------------- cuts by keyboard and links: jump, never scrub through
  const cutTop = (sh: Shot) => sh.sec.track.getBoundingClientRect().top + scrollY + sh.start * vh + 2;
  const go = (y: number) => window.scrollTo({ top: Math.max(0, y), behavior: "instant" as ScrollBehavior });
  addEventListener("keydown", (e) => {
    if ((e.target as HTMLElement).closest?.("input, textarea, select, [contenteditable]") || e.altKey || e.ctrlKey || e.metaKey) return;
    const fwd = ["ArrowDown", "PageDown", " "].includes(e.key) && !e.shiftKey, back = ["ArrowUp", "PageUp"].includes(e.key) || (e.key === " " && e.shiftKey);
    if (!fwd && !back) return;
    if (e.key === " " && (e.target as HTMLElement).closest?.("a, button")) return;
    const i = live ? live.index : -1;
    const next = shots[clamp(i + (fwd ? 1 : -1), 0, shots.length - 1)];
    if (!next || next === live) return;
    e.preventDefault();
    go(cutTop(next));
  });
  document.addEventListener("click", (e) => {
    const a = (e.target as HTMLElement).closest?.("a[href^='#']") as HTMLAnchorElement | null;
    if (!a) return;
    const id = a.getAttribute("href")!;
    let y: number | null = null;
    if (a.classList.contains("ai-skip")) {
      const after = secs[secs.findIndex((s) => s.el.contains(a)) + 1];
      y = after ? after.track.getBoundingClientRect().top + scrollY + 2 : null;
    } else if (id === "#") y = 0;
    else {
      const target = document.getElementById(id.slice(1));
      const sec = target && secs.find((s) => s.el === target || s.el.contains(target));
      if (sec) y = sec.track.getBoundingClientRect().top + scrollY + 2;
    }
    if (y === null) return;
    e.preventDefault(); e.stopPropagation();
    closeMenu();
    go(y);
  }, true);
}

// ---------------------------------------------------------------- the slanted menu
let closeMenu = () => {};
function menu() {
  const btn = $<HTMLButtonElement>(".ai-hud__menu"), panel = $<HTMLElement>(".ai-menu");
  if (!btn || !panel) return;
  const set = (open: boolean) => {
    panel.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", String(open));
    if (open) panel.querySelector<HTMLElement>("a")?.focus();
  };
  closeMenu = () => set(false);
  btn.addEventListener("click", () => set(!panel.classList.contains("is-open")));
  addEventListener("keydown", (e) => { if (e.key === "Escape" && panel.classList.contains("is-open")) { set(false); btn.focus(); } });
  document.addEventListener("click", (e) => { if (panel.classList.contains("is-open") && !panel.contains(e.target as Node) && !btn.contains(e.target as Node)) set(false); });
  panel.addEventListener("click", (e) => { if ((e.target as HTMLElement).closest("a")) set(false); });
}
