/**
 * ASCII art: the page is a terminal session that answers you. As each section scrolls in, its prompt types a command
 * (about 45 characters a second) and the output prints line by line; scrolling back un-types it. Time is quantised:
 * characters swap, nothing eases. A render pane turns an ASCII model of the product with the scroll, a tmux status
 * bar is the nav, j/k/0-9/?/enter work, and the call to action is a command you copy or run with ENTER.
 * Reduced motion: everything is printed at once.
 */
import { $, $$, onFrame, reduced, chars } from "./_kit";

const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const RAMP = " .:-=+*#%@";
const NOISE = "!<>-_\\/[]{}=+*^?#%&$";

/** Rasterise text with a font and return it as characters: half blocks (crisp banner) or a density ramp. */
function rasterText(text: string, px: number, weight: number, mode: "blocks" | "ramp"): string[] {
  const c = document.createElement("canvas");
  const g = c.getContext("2d", { willReadFrequently: true })!;
  const font = `${weight} ${px}px "JetBrains Mono", ui-monospace, monospace`;
  g.font = font;
  const w = Math.ceil(g.measureText(text).width) + 2, h = Math.ceil(px * 1.25);
  c.width = w; c.height = h;
  g.font = font; g.fillStyle = "#fff"; g.textBaseline = "top";
  g.fillText(text, 1, Math.round(px * 0.1));
  const d = g.getImageData(0, 0, w, h).data;
  const a = (x: number, y: number) => (y < h ? d[(y * w + x) * 4 + 3] / 255 : 0);
  const rows: string[] = [];
  if (mode === "blocks") {
    for (let y = 0; y < h; y += 2) {
      let s = "";
      for (let x = 0; x < w; x++) { const t = a(x, y) > 0.45, b = a(x, y + 1) > 0.45; s += t && b ? "█" : t ? "▀" : b ? "▄" : " "; }
      rows.push(s);
    }
  } else {
    for (let y = 0; y < h; y += 2) {
      let s = "";
      for (let x = 0; x < w; x++) { const v = (a(x, y) + a(x, y + 1)) / 2; s += RAMP[Math.min(RAMP.length - 1, Math.round(v * (RAMP.length - 1)))]; }
      rows.push(s);
    }
  }
  // trim blank rows and the common blank margin
  while (rows.length && !rows[0].trim()) rows.shift();
  while (rows.length && !rows[rows.length - 1].trim()) rows.pop();
  const left = Math.min(...rows.map((r) => r.search(/\S/)).filter((i) => i >= 0));
  return rows.map((r) => r.slice(left).replace(/\s+$/, ""));
}

/** An in-page link target; a href that is not a valid selector simply has none. */
const safeQ = (sel: string) => { try { return document.querySelector<HTMLElement>(sel); } catch { return null; } };

export default function start() {
  const root = document.documentElement;
  root.classList.add("tx-live");
  const bin = $(".tx-env")?.dataset.bin || "app";
  $$(".tx-bin").forEach((s) => { s.textContent = s.classList.contains("tx-up") ? bin.toUpperCase() : bin; });

  // no smoothing: wheel steps land where they land (capture runs before the page's smooth scroller)
  addEventListener("wheel", (e) => e.stopImmediatePropagation(), { capture: true, passive: true });

  // character cell size
  const probe = document.createElement("span");
  probe.textContent = "MMMMMMMMMM";
  probe.style.cssText = "position:absolute;visibility:hidden;white-space:pre;font:400 var(--tx-size, 15px)/var(--tx-lh, 1.5) 'JetBrains Mono', monospace";
  const main = $("main")!;
  main.appendChild(probe);
  let chW = 9, lineH = 22;
  const cell = () => { const r = probe.getBoundingClientRect(); chW = r.width / 10 || 9; lineH = r.height || 22; };
  cell();

  // ------------------------------------------------ banners (the hero's FIGlet-style name, neofetch's logo)
  function banners() {
    cell();
    $$(".tx-banner").forEach((pre) => {
      const cols = Math.floor((pre.parentElement!.clientWidth || 600) / chW) - 1;
      let rows: string[] = [];
      for (let px = 18; px >= 7; px--) { rows = rasterText(bin.toUpperCase(), px, 800, "blocks"); if (Math.max(...rows.map((r) => r.length)) <= cols) break; }
      pre.textContent = rows.join("\n");
    });
    $$(".tx-neo__logo").forEach((pre) => {
      const letter = (bin.match(/[a-z0-9]/i)?.[0] || "#").toUpperCase();
      pre.textContent = rasterText(letter, innerWidth < 700 ? 18 : 30, 800, "ramp").join("\n");
    });
  }
  banners();
  document.fonts?.ready.then(() => { banners(); measure(); });

  // ------------------------------------------------ ASCII images: pictures are printed as characters (toggle to see)
  $$<HTMLImageElement>(".tx-img img").forEach((img) => {
    const fig = img.closest("figure")!;
    const go = () => {
      const cols = Math.max(20, Math.floor(fig.clientWidth / chW) - 1);
      const rows = Math.max(8, Math.round(cols * (img.naturalHeight / Math.max(1, img.naturalWidth)) * chW / lineH));
      const c = document.createElement("canvas");
      c.width = cols; c.height = rows;
      const g = c.getContext("2d", { willReadFrequently: true })!;
      try {
        g.drawImage(img, 0, 0, cols, rows);
        const d = g.getImageData(0, 0, cols, rows).data;
        let out = "";
        for (let y = 0; y < rows; y++) { for (let x = 0; x < cols; x++) { const i = (y * cols + x) * 4; const l = (0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]) / 255; out += RAMP[Math.round(l * (RAMP.length - 1))]; } out += "\n"; }
        const pre = document.createElement("pre");
        pre.className = "tx-art";
        pre.setAttribute("aria-hidden", "true");
        pre.textContent = out;
        const btn = document.createElement("button");
        btn.type = "button"; btn.className = "tx-btn tx-art__toggle"; btn.textContent = "[ view image ]";
        btn.addEventListener("click", () => { const on = fig.classList.toggle("is-image"); btn.textContent = on ? "[ view ascii ]" : "[ view image ]"; });
        fig.prepend(pre); fig.appendChild(btn); fig.classList.add("is-ascii");
      } catch { /* cross-origin image: leave the picture as it is */ }
    };
    if (img.complete && img.naturalWidth) go(); else img.addEventListener("load", go, { once: true });
  });

  // ------------------------------------------------ the session: commands type, output prints
  type Sec = { el: HTMLElement; prompt: HTMLElement | null; cmd: HTMLElement[]; lines: HTMLElement[]; pTop: number; lTops: number[]; typed: number; printed: number; nextT: number; nums: HTMLElement[] };
  const secs: Sec[] = $$(".tx-sec").map((el) => {
    const prompt = $(".tx-prompt", el);
    const kbd = $(".tx-cmd", el);
    const cmd = kbd && !reduced ? chars(kbd) : [];
    const lines = $$(".tx-out .tx-l", el).filter((l) => !l.parentElement!.closest(".tx-l"));
    return { el, prompt, cmd, lines, pTop: 0, lTops: [], typed: -1, printed: -1, nextT: 0, nums: $$(".tx-num", el) };
  });
  const cursor = document.createElement("span");
  cursor.className = "tx-cursor";
  cursor.setAttribute("aria-hidden", "true");

  function measure() {
    cell();
    const sy = scrollY;
    secs.forEach((s) => {
      s.pTop = s.prompt ? s.prompt.getBoundingClientRect().top + sy : s.el.getBoundingClientRect().top + sy;
      s.lTops = s.lines.map((l) => l.getBoundingClientRect().top + sy);
    });
  }
  measure();
  addEventListener("resize", () => { banners(); measure(); });
  addEventListener("load", measure);

  const showChars = (s: Sec, n: number) => s.cmd.forEach((c, i) => { const v = i < n ? "visible" : "hidden"; if (c.style.visibility !== v) c.style.visibility = v; });
  const showLines = (s: Sec, n: number) => s.lines.forEach((l, i) => { const on = i < n; if (l.classList.contains("is-hid") === on) l.classList.toggle("is-hid", !on); });
  const tickNums = (s: Sec) => s.nums.forEach((el) => {
    if (el.dataset.done || reduced) return;
    const raw = el.textContent || "";
    if (!/^\d[\d,]*$/.test(raw.trim())) { el.dataset.done = "1"; return; }
    el.dataset.done = "1";
    const end = parseInt(raw.replace(/,/g, ""), 10);
    let k = 0;
    const steps = Math.min(end, 18);
    const iv = setInterval(() => { k++; el.textContent = String(Math.round((end * k) / Math.max(1, steps))); if (k >= steps) { clearInterval(iv); el.textContent = raw; } }, 40);
  });
  if (reduced) secs.forEach((s) => { s.typed = s.cmd.length; s.printed = s.lines.length; });
  else secs.forEach((s) => { showChars(s, 0); showLines(s, 0); s.typed = 0; s.printed = 0; });
  const resetSec = (s: Sec) => { if (reduced) return; s.typed = 0; s.printed = 0; showChars(s, 0); showLines(s, 0); };

  let lastCursorHost: HTMLElement | null = null, lastInput = -1e9, lastSessY = scrollY, jumpT = -1e9;
  for (const ev of ["wheel", "touchstart", "keydown", "pointerdown"]) addEventListener(ev, () => { lastInput = performance.now(); }, { passive: true, capture: true });
  function runSession(now: number, y: number) {
    const trig = y + innerHeight * 0.9;
    // a jump the visitor did not make (a page opened mid-way, a scripted scroll) prints what is already above at once
    if (Math.abs(y - lastSessY) > innerHeight && now - lastInput > 1500) jumpT = now;
    lastSessY = y;
    if (now - jumpT < 700) for (const s of secs) {
      if (s.pTop >= trig) continue;
      s.typed = s.cmd.length; showChars(s, s.typed);
      let n = 0; s.lTops.forEach((t, i) => { if (t < trig) n = i + 1; });
      if (n > s.printed) { s.printed = n; showLines(s, n); }
    }
    let latest: HTMLElement | null = null;
    for (const s of secs) {
      if (s.pTop > trig + innerHeight && s.typed === 0) continue;
      const cmdTarget = s.pTop < trig ? s.cmd.length : 0;
      let lineTarget = 0;
      if (s.typed >= s.cmd.length && cmdTarget) { for (let i = 0; i < s.lTops.length; i++) if (s.lTops[i] < trig) lineTarget = i + 1; }
      if (now < s.nextT) { if (s.printed > 0 || s.typed > 0) latest = s.printed > 0 ? s.lines[s.printed - 1] : s.prompt; continue; }
      if (s.printed > lineTarget) { s.printed = Math.max(lineTarget, s.printed - 2); showLines(s, s.printed); s.nextT = now + 16; }
      else if (s.typed > cmdTarget && s.printed === 0) { s.typed = Math.max(cmdTarget, s.typed - 3); showChars(s, s.typed); s.nextT = now + 16; }
      else if (s.typed < cmdTarget) { s.typed++; showChars(s, s.typed); s.nextT = now + 16 + Math.random() * 26; if (s.typed === cmdTarget) s.nextT += 140; }
      else if (s.printed < lineTarget) {
        const behind = lineTarget - s.printed;
        s.printed += Math.max(1, Math.floor(behind / 5));
        showLines(s, s.printed);
        s.nextT = now + 34;
        if (s.nums.length && s.printed > 0) { const host = s.nums[0].closest(".tx-l"); if (host && s.lines.indexOf(host as HTMLElement) < s.printed) tickNums(s); }
      }
      if (s.printed > 0) latest = s.lines[s.printed - 1];
      else if (s.typed > 0) latest = s.prompt;
    }
    // the cursor parks after the last thing printed
    const host = latest || secs[0]?.prompt || null;
    if (host && host !== lastCursorHost) { lastCursorHost = host; host.appendChild(cursor); }
  }

  // ------------------------------------------------ status bar: windows, clock, keys
  const wins = $$<HTMLAnchorElement>(".tx-win");
  const winTargets = wins.map((a) => { const h = a.getAttribute("href") || "#"; return h.length > 1 ? safeQ(h) : null; });
  const clockEl = $(".tx-clock");
  const kbdBtn = $<HTMLButtonElement>(".tx-kbd"), helpBtn = $<HTMLButtonElement>(".tx-help-btn"), help = $<HTMLElement>(".tx-help");
  let kbdOn = true;
  try { kbdOn = localStorage.getItem("tx-keys") !== "0"; } catch { /* storage blocked */ }
  if (kbdBtn) {
    kbdBtn.hidden = false;
    const sync = () => { kbdBtn.textContent = kbdOn ? "keys:on" : "keys:off"; kbdBtn.setAttribute("aria-pressed", String(kbdOn)); };
    sync();
    kbdBtn.addEventListener("click", () => { kbdOn = !kbdOn; try { localStorage.setItem("tx-keys", kbdOn ? "1" : "0"); } catch { /* blocked */ } sync(); });
  }
  if (helpBtn && help) { helpBtn.hidden = false; helpBtn.addEventListener("click", () => { help.hidden = !help.hidden; }); }

  // jumps are a screen clear and a cut, never a smooth scroll
  const clearEl = document.createElement("div");
  clearEl.className = "tx-clear";
  clearEl.setAttribute("aria-hidden", "true");
  document.body.appendChild(clearEl);
  function jump(target: HTMLElement | null) {
    const top = target ? target.getBoundingClientRect().top + scrollY - 12 : 0;
    const sec = target ? secs.find((s) => s.el === target || s.el.contains(target)) : null;
    if (reduced) { scrollTo({ top, behavior: "instant" as ScrollBehavior }); return; }
    clearEl.classList.add("is-on");
    setTimeout(() => {
      if (sec && Math.abs(top - scrollY) > 4) resetSec(sec);
      scrollTo({ top, behavior: "instant" as ScrollBehavior });
      setTimeout(() => clearEl.classList.remove("is-on"), 60);
    }, 70);
  }
  addEventListener("click", (e) => {
    const a = (e.target as Element).closest?.("a") as HTMLAnchorElement | null;
    if (!a) return;
    const href = a.getAttribute("href") || "";
    if (!href.startsWith("#")) return;
    if (a.classList.contains("tx-go")) return;   // the CTA handles itself
    if (href === "#") { if (a.closest(".tx-bar")) { e.preventDefault(); e.stopPropagation(); jump(null); } return; }
    const t = safeQ(href);
    if (!t) return;
    e.preventDefault(); e.stopPropagation();
    jump(t);
  }, { capture: true });

  const order = () => [...main.children].filter((c) => c !== probe) as HTMLElement[];
  function stepSection(d: number) {
    const all = order();
    let cur = 0;
    all.forEach((c, i) => { if (c.getBoundingClientRect().top <= innerHeight * 0.3) cur = i; });
    jump(all[clamp(cur + d, 0, all.length - 1)] || null);
  }
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && help && !help.hidden) { help.hidden = true; return; }
    if (!kbdOn || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = (e.target instanceof Element ? e.target : document.body) as HTMLElement;
    if (t.closest("input, textarea, select, [contenteditable]")) return;
    if (e.key === "j") stepSection(1);
    else if (e.key === "k") stepSection(-1);
    else if (e.key === "g") jump(null);
    else if (e.key === "G") scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" as ScrollBehavior });
    else if (e.key === "?") { if (help) help.hidden = !help.hidden; }
    else if (/^[0-9]$/.test(e.key)) { const w = wins.find((a) => a.dataset.k === e.key); if (w) { e.preventDefault(); w.click(); } }
    else if (e.key === "Enter" && !t.closest("a, button, summary")) {
      const go = $<HTMLAnchorElement>(".tx-go");
      if (go) { const r = go.getBoundingClientRect(); if (r.top < innerHeight && r.bottom > 0) { e.preventDefault(); go.click(); } }
    }
  });

  // ------------------------------------------------ hover: links scramble once, then resolve (stepped)
  if (!reduced) $$(".tx-btn, .tx-win, .tx-bar__cta").forEach((el) => {
    let busy = false;
    el.addEventListener("pointerenter", () => {
      if (busy || el.children.length > 1) return;
      const node = [...el.childNodes].find((n) => n.nodeType === 3 && (n.textContent || "").trim()) as Text | undefined;
      if (!node) return;
      busy = true;
      const orig = node.data;
      let f = 0;
      const iv = setInterval(() => {
        f++;
        const keep = Math.floor((orig.length * f) / 6);
        node.data = [...orig].map((c, i) => (i < keep || c === " " || c === "[" || c === "]" ? c : NOISE[Math.floor(Math.random() * NOISE.length)])).join("");
        if (f >= 6) { clearInterval(iv); node.data = orig; busy = false; }
      }, 40);
    });
  });

  // ------------------------------------------------ the call to action: a command you copy, or ENTER
  $$(".tx-box").forEach((box) => {
    const go = $<HTMLAnchorElement>(".tx-go", box);
    const done = $(".tx-done", box);
    const copy = $<HTMLElement>(".tx-copy", box);
    const href = go?.getAttribute("href") || "#";
    const url = href && href !== "#" && !href.startsWith("#") ? go!.href : location.origin + location.pathname;
    if (copy) {
      copy.hidden = false;
      $(".tx-copy__cmd", copy)!.textContent = `$ open ${url}`;
      $(".tx-copy__btn", copy)!.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(`open ${url}`); if (done) done.textContent = "✓ copied to clipboard"; }
        catch { if (done) done.textContent = "✗ clipboard blocked: select the line and copy it"; }
      });
    }
    go?.addEventListener("click", (e) => {
      if (done) done.textContent = `> ${go.textContent?.replace(/[[\]]/g, "").trim().toLowerCase()} ... [ OK ]`;
      if (href === "#") e.preventDefault();
      else if (href.startsWith("#")) { e.preventDefault(); jump(safeQ(href)); }
    });
  });

  // ------------------------------------------------ the render pane: an ASCII model turned by the scroll
  const pane = $(".tx-pane"), pre = $(".tx-render"), statPre = $(".tx-stat");
  const hasPhone = !!$(".tx-phone");
  const pts = buildModel(hasPhone ? "phone" : "torus");
  let mxp = -999, myp = -999;
  pane?.addEventListener("pointermove", (e) => { const r = pre!.getBoundingClientRect(); mxp = (e.clientX - r.left) / chW; myp = (e.clientY - r.top) / lineH; });
  pane?.addEventListener("pointerleave", () => { mxp = myp = -999; });
  const velHist: number[] = Array(14).fill(0);
  let lastRender = 0, lastKey = "";

  // ------------------------------------------------ the frame loop
  let lastWin = -1, measureT = 0, lastDoc = 0;
  onFrame(({ y, v, t }) => {
    const now = performance.now();
    if (t - measureT > 1.5) { measureT = t; const d = document.documentElement.scrollHeight; if (d !== lastDoc) { lastDoc = d; measure(); } }
    if (!reduced) runSession(now, y);
    else if (!cursor.parentElement) secs[secs.length - 1]?.lines.slice(-1)[0]?.appendChild(cursor);

    // status bar: the active window and the clock
    let w = 0;
    winTargets.forEach((el, i) => { if (el && el.getBoundingClientRect().top < innerHeight * 0.4) w = i; });
    if (w !== lastWin) { lastWin = w; wins.forEach((a, i) => { a.classList.toggle("is-on", i === w); if (i === w) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); }); }
    if (clockEl) { const d = new Date(); const c = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; if (clockEl.textContent !== c) clockEl.textContent = c; }

    // the render pane at 12 frames a second, only when something changed
    if (pane && pre && pane.getClientRects().length && now - lastRender > 83) {
      lastRender = now;
      velHist.push(Math.min(1, Math.abs(v) / 40)); velHist.shift();
      const docEnd = Math.max(1, document.documentElement.scrollHeight - innerHeight);
      const p = clamp(y / docEnd);
      const step = Math.round(p * 96);                       // quantised: 96 positions over the page
      const cols = Math.max(20, Math.floor(pre.clientWidth / chW));
      const rows = Math.max(10, Math.floor(pre.clientHeight / lineH));
      const key = [step, cols, rows, Math.round(mxp), Math.round(myp)].join(",");
      if (key !== lastKey) { lastKey = key; pre.textContent = renderModel(pts, cols, rows, (step / 96) * Math.PI * 2.5 + 0.6, chW / lineH, mxp, myp); }
      if (statPre) {
        const sec = order().filter((c) => c.getBoundingClientRect().top < innerHeight * 0.5).length;
        const bar = Math.round(p * 14);
        const spark = velHist.map((x) => "▁▂▃▄▅▆▇█"[Math.round(x * 7)]).join("");
        statPre.textContent = `pos   [${"█".repeat(bar)}${"░".repeat(14 - bar)}] ${String(Math.round(p * 100)).padStart(3)}%\nsect  ${String(Math.max(1, sec)).padStart(2, "0")}/${String(order().length).padStart(2, "0")}\nvel   ${spark}\nkeys  j k  0-9  ?  enter`;
      }
    }
  });
}

// ---------------------------------------------------------------- the model: surface points with normals
type P = [number, number, number, number, number, number, number];   // x y z nx ny nz albedo
function buildModel(kind: "phone" | "torus"): P[] {
  const out: P[] = [];
  if (kind === "torus") {
    for (let th = 0; th < Math.PI * 2; th += 0.05) for (let ph = 0; ph < Math.PI * 2; ph += 0.02) {
      const ct = Math.cos(th), st = Math.sin(th), cp = Math.cos(ph), sp = Math.sin(ph);
      const r = 1 + 0.45 * ct;
      out.push([r * cp, 0.45 * st, r * sp, ct * cp, st, ct * sp, 1]);
    }
    return out;
  }
  const a = 0.5, b = 1.0, c = 0.07, rad = 0.13, s = 0.011;
  const inRound = (u: number, v: number) => {
    const dx = Math.max(0, Math.abs(u) - (a - rad)), dy = Math.max(0, Math.abs(v) - (b - rad));
    return dx * dx + dy * dy <= rad * rad;
  };
  for (let u = -a; u <= a; u += s) for (let v = -b; v <= b; v += s) {
    if (!inRound(u, v)) continue;
    // front: a dark screen with bright rows of interface, a notch and a button bar
    let alb = 0.95;
    const inScreen = Math.abs(u) < a - 0.05 && Math.abs(v) < b - 0.06;
    if (inScreen) {
      alb = 0.42;
      const row = (b - 0.06 - v);
      if (Math.abs(u) < 0.12 && row < 0.07) alb = 0.05;                                // notch
      else if (row > 0.22 && row < 0.3 && Math.abs(u) < 0.32) alb = 1;                 // title
      else if ([0.5, 0.78, 1.06].some((r0) => row > r0 && row < r0 + 0.2) && Math.abs(u) < a - 0.1) alb = row < 0.7 ? 0.85 : 0.55;   // options
      else if (row > 1.62 && row < 1.76 && Math.abs(u) < 0.34) alb = 1;                // button
    }
    out.push([u, v, c, 0, 0, 1, alb]);
    const cam = (u + 0.28) ** 2 + (v - 0.78) ** 2 < 0.012;
    out.push([u, v, -c, 0, 0, -1, cam ? 1 : 0.7]);
  }
  for (let v = -b + rad; v <= b - rad; v += s) for (let z = -c; z <= c; z += s) { out.push([a, v, z, 1, 0, 0, 0.8]); out.push([-a, v, z, -1, 0, 0, 0.8]); }
  for (let u = -a + rad; u <= a - rad; u += s) for (let z = -c; z <= c; z += s) { out.push([u, b, z, 0, 1, 0, 0.8]); out.push([u, -b, z, 0, -1, 0, 0.8]); }
  return out;
}

const SHADE = ".,-~:;=!*#$@";
function renderModel(pts: P[], cols: number, rows: number, ang: number, aspect: number, mx: number, my: number): string {
  const n = cols * rows;
  const zb = new Float32Array(n);
  const ch = new Uint8Array(n);
  const ca = Math.cos(ang), sa = Math.sin(ang), tilt = 0.32, ct = Math.cos(tilt), st = Math.sin(tilt);
  const K = Math.min(rows * 0.42, cols * aspect * 0.42), dist = 4;
  const L = [0.4, 0.45, 0.8];
  const ll = Math.hypot(L[0], L[1], L[2]);
  for (const [x, y, z, nx, ny, nz, alb] of pts) {
    // spin about y, then tilt about x
    const x1 = x * ca + z * sa, z1 = -x * sa + z * ca;
    const y2 = y * ct - z1 * st, z2 = y * st + z1 * ct;
    const nx1 = nx * ca + nz * sa, nz1 = -nx * sa + nz * ca;
    const ny2 = ny * ct - nz1 * st, nz2 = ny * st + nz1 * ct;
    const ooz = 1 / (dist - z2);
    const px = Math.floor(cols / 2 + (K * x1 * ooz * dist) / aspect);
    const py = Math.floor(rows / 2 - K * y2 * ooz * dist);
    if (px < 0 || px >= cols || py < 0 || py >= rows) continue;
    const i = py * cols + px;
    if (ooz <= zb[i]) continue;
    zb[i] = ooz;
    const lum = (nx1 * L[0] + ny2 * L[1] + nz2 * L[2]) / ll;
    const l = (0.18 + 0.82 * Math.max(0, lum)) * alb;
    ch[i] = 1 + Math.max(0, Math.min(SHADE.length - 1, Math.floor(l * (SHADE.length - 0.01))));
  }
  let s = "";
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      let k = ch[y * cols + x];
      if (k && mx > -900) { const d = Math.hypot((x - mx) * 0.5, y - my); if (d < 5) k = Math.min(SHADE.length, k + Math.round((5 - d) * 0.8)); }
      s += k ? SHADE[k - 1] : " ";
    }
    s += "\n";
  }
  return s;
}
