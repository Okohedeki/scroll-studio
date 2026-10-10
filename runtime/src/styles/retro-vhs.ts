/**
 * Retro VHS: scrolling is the tape transport. The on-screen display reads the scroll velocity as PLAY, PAUSE,
 * ▶▶ SEARCH or ◀◀ REW (with tracking bands and a colour fringe that grow with speed) and the tape counter follows the
 * scroll position. Every section arrives mistracked and locks; jumps between sections are channel changes; the deck's
 * keys really work (PLAY rolls the page on its own); the end of the page is the end of the tape, with AUTO REWIND.
 *
 * Photosensitivity: noise is low contrast and confined to bands, the channel burst is one 200 ms frame per action,
 * the REC blink is 1 Hz. Reduced motion or TRACKING: CLEAN turn off bands, jitter, fringe and static.
 */
import { $, $$, onFrame, reduced, chars, pinSequence } from "./_kit";

const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const SECS_PER_SCREEN = 37;
const fmt = (s: number) => {
  s = Math.max(0, Math.floor(s));
  return `${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

export default function start() {
  const root = document.documentElement;
  const main = $("main");
  const glass = $(".vhs-glass");
  if (!main || !glass) return;
  const progs = [...main.children] as HTMLElement[];
  const modeEl = $(".vhs-mode")!, counterEl = $(".vhs-counter")!, chEl = $(".vhs-ch")!, trackEl = $(".vhs-track")!, snow = $(".vhs-snow")!;
  const bands = $$(".vhs-bands i");
  const lcdCh = $(".vhs-deck__chn"), lcdCnt = $(".vhs-deck__cnt");
  const labelLinks = $$<HTMLAnchorElement>(".vhs-label__list a");
  const shelves = $$(".vhs-shelf");

  // ------------------------------------------------ TRACKING: AUTO / CLEAN (effects off for everyone who wants it)
  let clean = false;
  try { clean = localStorage.getItem("vhs-clean") === "1"; } catch { /* storage blocked */ }
  const cleanBtns = $$<HTMLButtonElement>(".vhs-clean, .vhs-rk--clean");
  const applyClean = () => {
    root.classList.toggle("vhs-clean", clean);
    cleanBtns.forEach((b) => { b.setAttribute("aria-pressed", String(clean)); const l = b.querySelector("b"); if (l) l.textContent = clean ? "Clean" : "Auto"; });
  };
  applyClean();
  cleanBtns.forEach((b) => b.addEventListener("click", () => {
    clean = !clean;
    try { localStorage.setItem("vhs-clean", clean ? "1" : "0"); } catch { /* storage blocked */ }
    applyClean();
    flashTrack(clean ? "TRACKING  CLEAN" : "TRACKING  AUTO");
  }));
  const fx = () => !reduced && !clean;

  // ------------------------------------------------ geometry: screen rect, chapter positions
  let scrTop = 0, scrH = 1, starts: number[] = [], docEnd = 1;
  const names = progs.map((p, i) => {
    const l = labelLinks.find((a) => a.dataset.ch === String(i));
    const t = l?.querySelector(".vhs-label__n")?.textContent || p.querySelector("h1, h2, h3")?.textContent || `Chapter ${i + 1}`;
    return t.trim().toUpperCase();
  });
  function measure() {
    const r = glass!.getBoundingClientRect();
    scrTop = r.top; scrH = Math.max(1, r.height);
    starts = progs.map((p) => p.getBoundingClientRect().top + scrollY - scrTop);
    docEnd = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    labelLinks.forEach((a) => { const i = Number(a.dataset.ch); const t = a.querySelector(".vhs-label__t"); if (t && starts[i] != null) t.textContent = fmt(Math.max(0, starts[i]) / scrH * SECS_PER_SCREEN); });
    progs.forEach((p, i) => { const c = p.querySelector(".vhs-chap__t"); if (c) c.textContent = fmt(Math.max(0, starts[i]) / scrH * SECS_PER_SCREEN); });
  }
  measure();
  addEventListener("resize", measure);
  addEventListener("load", measure);
  document.fonts?.ready.then(measure);
  const chapterAt = (y: number) => { let k = 0; starts.forEach((s, i) => { if (y + scrH * 0.5 >= s) k = i; }); return k; };

  // ------------------------------------------------ OSD helpers
  let chTimer = 0, trackTimer = 0;
  function flashCh(i: number) {
    chEl.textContent = `CH ${String(i + 1).padStart(2, "0")}  ${names[i] || ""}`;
    chEl.style.opacity = "1";
    clearTimeout(chTimer);
    chTimer = window.setTimeout(() => { chEl.style.opacity = "0"; }, 3000);
  }
  function flashTrack(t: string) {
    trackEl.textContent = t;
    trackEl.style.opacity = "1";
    clearTimeout(trackTimer);
    trackTimer = window.setTimeout(() => { trackEl.style.opacity = "0"; }, 1800);
  }

  // ------------------------------------------------ transport state
  let autoplay = false, recording = false, forced: string | null = null;
  let lastMove = performance.now() - 2000, shownMode = "", pauseSince = 0;
  let current = -1, roll = 0, reel = 0;
  const startT = performance.now();

  const stopAuto = () => { autoplay = false; };
  addEventListener("wheel", () => { stopAuto(); cancelShuttle(); }, { passive: true });
  addEventListener("touchstart", () => { stopAuto(); cancelShuttle(); }, { passive: true });
  addEventListener("keydown", (e) => { if (["ArrowDown", "ArrowUp", "PageDown", "PageUp", " ", "Home", "End"].includes(e.key)) { stopAuto(); cancelShuttle(); } });

  // shuttle: a fast, visible search to a position (FF / REW keys, auto rewind)
  let shuttle: { from: number; to: number; t0: number; dur: number } | null = null;
  function cancelShuttle() { if (shuttle) { shuttle = null; forced = null; } }
  function search(to: number, max = 1500) {
    stopAuto();
    const from = scrollY;
    const d = Math.abs(to - from);
    if (reduced || d < 4) { scrollTo(0, to); return; }
    shuttle = { from, to, t0: performance.now(), dur: Math.min(max, 380 + d * 0.12) };
    forced = to < from ? "◀◀ REW ×9" : "▶▶ ×9 SEARCH";
  }

  // channel change: one low-contrast burst of snow, a cut, and the channel on the OSD
  function channel(i: number) {
    i = clamp(i, 0, progs.length - 1);
    stopAuto(); cancelShuttle();
    const go = () => { scrollTo({ top: Math.max(0, starts[i]), behavior: "instant" as ScrollBehavior }); flashCh(i); };
    if (!fx()) { go(); return; }
    snow.style.transition = "none";
    snow.style.opacity = ".34";
    setTimeout(() => { go(); snow.style.opacity = "0"; }, 200);
  }

  // ● REC: the record key; the OSD switches to REC and the timestamp runs
  let recStart = 0;
  function rec(a: HTMLAnchorElement) {
    if (!recording) { recording = true; recStart = performance.now(); }
    $$(".vhs-recbtn").forEach((b) => b.classList.add("is-rec"));
    const href = a.getAttribute("href") || "";
    if (href.length > 1 && href.startsWith("#")) {
      const t = document.querySelector(href);
      const i = t ? progs.findIndex((p) => p === t || p.contains(t)) : -1;
      if (i >= 0 && i !== current) setTimeout(() => channel(i), 500);
    } else if (href && href !== "#") setTimeout(() => { location.href = a.href; }, reduced ? 0 : 900);
  }

  // every in-page jump is a channel change (capture: runs before the page's own smooth anchor scroll)
  addEventListener("click", (e) => {
    const a = (e.target as Element).closest?.("a") as HTMLAnchorElement | null;
    if (!a) return;
    const href = a.getAttribute("href") || "";
    if (a.matches(".vhs-recbtn, .vhs-rec, .vhs-rk--rec")) { e.preventDefault(); e.stopPropagation(); rec(a); return; }
    if (a.matches(".vhs-rewind")) { e.preventDefault(); e.stopPropagation(); search(0, 1500); return; }
    if (!href.startsWith("#")) return;
    let i = -1;
    if (href === "#") i = a.closest(".vhs-label") ? 0 : -1;
    else { const t = document.querySelector(href); if (t) i = progs.findIndex((p) => p === t || p.contains(t)); }
    if (i < 0) return;
    e.preventDefault(); e.stopPropagation();
    channel(i);
  }, { capture: true });

  // deck and remote keys
  $$<HTMLButtonElement>("[data-act]").forEach((b) => b.addEventListener("click", () => {
    const act = b.dataset.act;
    b.classList.add("is-down"); setTimeout(() => b.classList.remove("is-down"), 160);
    if (act === "play") { cancelShuttle(); autoplay = true; }
    else if (act === "pause") { autoplay = false; cancelShuttle(); lastMove = 0; }
    else if (act === "toggle") { cancelShuttle(); autoplay = !autoplay; if (!autoplay) lastMove = 0; }
    else if (act === "ff") search(starts[Math.min(progs.length - 1, current + 1)] ?? docEnd);
    else if (act === "rew") search(starts[Math.max(0, scrollY > (starts[current] ?? 0) + 40 ? current : current - 1)] ?? 0);
    else if (act === "chup") channel(current + 1);
    else if (act === "chdown") channel(current - 1);
  }));

  // ------------------------------------------------ hero: the headline is typed like OSD text
  const typed = $<HTMLElement>("[data-type]");
  let typeSpans: HTMLElement[] = [];
  if (typed && !reduced && scrollY < 10) {
    typeSpans = chars(typed);
    typeSpans.forEach((s) => { s.style.visibility = "hidden"; });
  }

  // ------------------------------------------------ sections arrive mistracked and lock
  const lockState = new Map<HTMLElement, boolean>();
  function checkLocks() {
    const bottom = scrTop + scrH * 0.8;
    progs.forEach((p) => {
      const r = p.getBoundingClientRect();
      const inView = r.top < bottom && r.bottom > scrTop + scrH * 0.15;
      if (inView && !lockState.get(p)) {
        lockState.set(p, true);
        if (fx() && r.top > scrTop - scrH * 0.3) {
          p.classList.remove("is-locking"); void p.offsetWidth; p.classList.add("is-locking");
          flashTrack("TRACKING ▮▮▮▯▯▯");
          setTimeout(() => p.classList.remove("is-locking"), 900);
        }
      } else if (!inView && lockState.get(p)) lockState.set(p, false);
    });
  }

  // ------------------------------------------------ stats: the setup menu cursor follows the scroll
  const menus = $$(".vhs-prog--stats").map((sec) => {
    const rows = $$(".vhs-menu__row", sec);
    const rolled = new Set<number>();
    return { sec, rows, rolled, cur: -1 };
  });
  function rollValue(row: HTMLElement) {
    const el = row.querySelector<HTMLElement>(".vhs-roll");
    if (!el || reduced) return;
    const raw = (el.textContent || "").trim();
    if (!/^\d[\d,]*(\.\d+)?$/.test(raw)) return;
    const end = parseFloat(raw.replace(/,/g, "")), dec = (raw.split(".")[1] || "").length, t0 = performance.now();
    el.style.minWidth = el.offsetWidth + "px";
    const tick = () => {
      const f = Math.min(1, (performance.now() - t0) / 650);
      el.textContent = f >= 1 ? raw : (end * f).toFixed(dec);
      if (f < 1) setTimeout(tick, 45);   // a mechanical counter: stepped, not smooth
    };
    tick();
  }

  // ------------------------------------------------ timeline: a tape counter bar the scroll scrubs
  const timelines = $$(".vhs-prog--timeline").map((sec) => {
    const chs = $$(".vhs-tl__ch", sec);
    const set = (s: number) => {
      const n = chs.length || 1;
      sec.style.setProperty("--tl", clamp(s / n).toFixed(4));
      const a = Math.min(n - 1, Math.floor(s));
      chs.forEach((c, i) => c.classList.toggle("is-on", i === a));
    };
    let pinnedOn = false;
    if (!reduced && innerWidth > 760 && chs.length > 1) { pinSequence(sec, chs.length, (s) => set(s), 0.55); pinnedOn = true; measure(); }
    return { sec, set, pinnedOn, n: chs.length };
  });

  // ------------------------------------------------ quote: the camcorder's date burn-in
  const now = new Date();
  $$(".vhs-cam__date").forEach((d) => {
    const mon = now.toLocaleString("en-US", { month: "short" }).toUpperCase();
    d.innerHTML = `${mon} ${now.getDate()} ${now.getFullYear()}<br>${now.toLocaleString("en-US", { hour: "numeric", minute: "2-digit" })}`;
  });

  // ------------------------------------------------ features: choosing a tape plays it on the screen
  const player = document.createElement("div");
  player.className = "vhs-play";
  player.hidden = true;
  player.setAttribute("role", "dialog");
  player.setAttribute("aria-modal", "false");
  player.innerHTML = '<p class="vhs-play__k">▶ PLAY</p><h3 class="vhs-play__h"></h3><p class="vhs-play__b"></p><button type="button" class="vhs-key vhs-key--wide vhs-play__x"><b aria-hidden="true">■</b><small>Stop · eject</small></button>';
  glass.appendChild(player);
  let playing: HTMLElement | null = null, playOpenT = 0;
  const closePlayer = () => {
    if (!playing) return;
    player.hidden = true;
    playing.classList.remove("is-playing");
    const t = playing; playing = null;
    t.focus({ preventScroll: true });
  };
  $(".vhs-play__x", player)!.addEventListener("click", closePlayer);
  addEventListener("keydown", (e) => { if (e.key === "Escape") closePlayer(); });
  $$(".vhs-tape").forEach((tape) => {
    const open = () => {
      if (playing) playing.classList.remove("is-playing");
      playing = tape; playOpenT = performance.now();
      tape.classList.add("is-playing");
      $(".vhs-play__h", player)!.innerHTML = tape.querySelector(".vhs-tape__title")?.innerHTML || "";
      $(".vhs-play__b", player)!.innerHTML = tape.querySelector(".vhs-tape__body")?.innerHTML || "";
      player.setAttribute("aria-label", (tape.querySelector(".vhs-tape__title")?.textContent || "") + ", playing");
      player.hidden = false;
      // the tape goes in: a moment of blue screen before the picture
      if (!reduced) { player.classList.add("is-loading"); setTimeout(() => player.classList.remove("is-loading"), 420); }
      setTimeout(() => $<HTMLButtonElement>(".vhs-play__x", player)?.focus({ preventScroll: true }), reduced ? 0 : 430);
    };
    tape.addEventListener("click", open);
    tape.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  });

  // ------------------------------------------------ the frame loop
  let lastVch = -1, lastJitter = 0, jitterX = 0, jitterY = 0, measureT = 0;
  onFrame(({ y, v, dt, t }) => {
    const nowT = performance.now();
    if (t - measureT > 2) { measureT = t; const h = document.documentElement.scrollHeight - innerHeight; if (Math.abs(h - docEnd) > 2) measure(); }

    // drive the page: shuttle search, or PLAY rolling the tape on its own
    if (shuttle) {
      const f = clamp((nowT - shuttle.t0) / shuttle.dur);
      scrollTo(0, shuttle.from + (shuttle.to - shuttle.from) * f);
      if (f >= 1) { shuttle = null; forced = null; lastMove = nowT; }
    } else if (autoplay) {
      if (y >= docEnd - 1) autoplay = false;
      else scrollTo(0, y + Math.max(1, 52 * dt));
    }

    // transport mode from the scroll velocity
    const sv = shuttle ? (shuttle.to < shuttle.from ? -60 : 60) : v;
    if (Math.abs(sv) > 0.35) lastMove = nowT;
    let mode: string;
    if (recording) mode = "● REC  " + fmt((nowT - recStart) / 1000);
    else if (forced) mode = forced;
    else if (autoplay) mode = "PLAY ▶";
    else if (sv > 20) mode = `▶▶ ×${sv > 55 ? 9 : sv > 35 ? 5 : 3} SEARCH`;
    else if (sv < -20) mode = `◀◀ REW ×${sv < -55 ? 9 : sv < -35 ? 5 : 3}`;
    else if (sv > 0.35) mode = "PLAY ▶";
    else if (sv < -0.35) mode = "◀◀ REW";
    else if (nowT - lastMove > 450 && nowT - startT > 1600) mode = "PAUSE ‖";
    else mode = shownMode || "PLAY ▶";
    if (mode !== shownMode) {
      if (mode.startsWith("PAUSE") && !shownMode.startsWith("PAUSE")) pauseSince = nowT;
      shownMode = mode;
      modeEl.textContent = mode;
      modeEl.classList.toggle("is-rec", recording);
    }
    const searching = !!forced || Math.abs(sv) > 20;
    const paused = mode.startsWith("PAUSE");

    // tape counter, current chapter
    const cnt = fmt(y / scrH * SECS_PER_SCREEN);
    if (counterEl.textContent !== cnt) { counterEl.textContent = cnt; if (lcdCnt) lcdCnt.textContent = cnt; }
    const k = chapterAt(y);
    if (k !== current) {
      current = k;
      if (lcdCh) lcdCh.textContent = `CH ${String(k + 1).padStart(2, "0")}`;
      const best = Math.max(-1, ...labelLinks.map((l) => Number(l.dataset.ch)).filter((c) => c <= k));
      labelLinks.forEach((l) => l.classList.toggle("is-on", Number(l.dataset.ch) === best));
      counterEl.title = names[k] || "";
    }

    // typed headline (time based, from load)
    if (typeSpans.length) {
      const n = Math.floor((nowT - startT - 350) / 38);
      typeSpans.forEach((s, i) => { s.style.visibility = i < n ? "visible" : "hidden"; });
      if (n > typeSpans.length) typeSpans = [];
    }

    // picture effects: bands, fringe, jitter (all off for reduced motion and TRACKING: CLEAN)
    if (fx()) {
      const speed = Math.abs(sv);
      roll += dt * (searching ? 0.9 + speed / 60 : 0.12) * (sv < 0 ? -1 : 1);
      bands.forEach((b, i) => {
        let op = 0, hgt = 6;
        if (searching) { op = i < 3 ? 0.6 - i * 0.12 : 0; hgt = 5 + i * 3; }
        else if (paused && i === 0) { op = 0.22; hgt = 4; }
        const pos = searching ? (((roll + i * 0.37) % 1.25) + 1.25) % 1.25 - 0.15 : paused ? 0.68 : -1;
        b.style.opacity = op.toFixed(2);
        b.style.height = hgt + "%";
        b.style.transform = `translateY(${(pos * scrH).toFixed(0)}px)`;
      });
      const vch = Math.min(4, Math.round(speed / 14));
      if (vch !== lastVch) { lastVch = vch; main.style.setProperty("--vch", String(vch)); }
      // jitter: horizontal shake while searching; a short vertical shudder when the tape is first paused
      if (nowT - lastJitter > 70) {
        lastJitter = nowT;
        jitterX = searching ? Math.round((Math.random() - 0.5) * 4) : 0;
        jitterY = paused && nowT - pauseSince < 1100 ? (jitterY ? 0 : 1) : 0;
        main.style.transform = jitterX || jitterY ? `translate(${jitterX}px, ${jitterY}px)` : "";
      }
    } else if (lastVch !== 0 || main.style.transform) {
      lastVch = 0; main.style.setProperty("--vch", "0"); main.style.transform = "";
      bands.forEach((b) => { b.style.opacity = "0"; });
    }

    // reels turn with the tape
    if (shelves.length && Math.abs(sv) > 0.05 || autoplay) {
      reel = (reel + sv * 3 + (autoplay ? 2 : 0)) % 360;
      shelves.forEach((s) => s.style.setProperty("--reel", reel.toFixed(1) + "deg"));
    }

    // the playing tape stops when the tape moves on
    if (playing && nowT - playOpenT > 700 && Math.abs(v) > 6) closePlayer();

    checkLocks();

    // stats menu cursor
    for (const m of menus) {
      const r = m.sec.getBoundingClientRect();
      if (r.bottom < scrTop || r.top > scrTop + scrH) continue;
      const center = scrTop + scrH * 0.5;
      const p = (center - r.top) / Math.max(1, r.height);
      const idx = Math.max(0, Math.min(m.rows.length - 1, Math.floor(p * m.rows.length)));
      if (idx !== m.cur) {
        m.cur = idx;
        m.rows.forEach((row, i) => row.classList.toggle("is-cur", i === idx));
        if (!m.rolled.has(idx)) { m.rolled.add(idx); rollValue(m.rows[idx]); }
      }
    }

    // timelines that are not pinned (phones, reduced motion) still scrub their bar
    for (const tl of timelines) {
      if (tl.pinnedOn) continue;
      const r = tl.sec.getBoundingClientRect();
      if (r.bottom < 0 || r.top > innerHeight) continue;
      tl.set(clamp((scrTop + scrH * 0.6 - r.top) / Math.max(1, r.height)) * tl.n);
    }
  });
}
