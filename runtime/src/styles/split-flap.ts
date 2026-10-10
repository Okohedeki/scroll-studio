/**
 * Split-flap: the page is a station hall. A Solari departures board is fixed at the top; every section is a departure.
 * Scrolling advances the station clock; when it reaches a section's time that service departs and the whole board
 * re-flips up one line, row by row and cell by cell, each cell riffling forward through its drum until it lands.
 * The boarding row shows the section's headline in large flaps and its full text waits at the information desk below.
 *
 * One scheduler steps every cell (no per-cell timers); flaps are four half-glyph layers animated with transforms.
 * Reduced motion: cells change in one step, no riffle and no cascade.
 */
import { $, $$, onFrame, onSeen, reduced } from "./_kit";

// ---------------------------------------------------------------- the drum
const CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,:;'\"-/&!?%+()·@#*";
const DIGITS = "0123456789";
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase()
  .replace(/[‘’`]/g, "'").replace(/[“”]/g, '"').replace(/[–—]/g, "-").replace(/…/g, "...").replace(/\s+/g, " ");

// A cell is two half-glyph layers. One flap step is drawn in two phases without transforms (cheap enough for
// hundreds of cells at once): first the new character's top half drops over the old bottom half (the falling flap,
// shaded), then the bottom half lands.
const tpl = document.createElement("span");
tpl.className = "fc";
tpl.innerHTML = '<span class="fc-t"><i> </i></span><span class="fc-b"><i> </i></span>';

let soundOn = false;
let BOARD_H = 0;
let clicks = 0;

class Cell {
  el: HTMLElement;
  g: Text[];
  set: string;
  cur = 0;
  tgt = 0;
  shown = " ";
  free = "";
  due = 0;
  half = 0;
  step: number;
  constructor(set = CHARS, first = " ") {
    this.set = set;
    this.el = tpl.cloneNode(true) as HTMLElement;
    this.g = [...this.el.querySelectorAll("i")].map((i) => i.firstChild as Text);
    this.step = 52 + Math.random() * 24;
    this.instant(first);
  }
  paint(top: string, bot: string) {
    if (this.g[0].data !== top) this.g[0].data = top;
    if (this.g[1].data !== bot) this.g[1].data = bot;
  }
  instant(ch: string) {
    const i = this.set.indexOf(ch);
    this.cur = this.tgt = i < 0 ? 0 : i;
    this.free = i < 0 ? ch : "";
    this.shown = ch;
    this.half = 0;
    this.paint(ch, ch);
    if (this.el.dataset.f) delete this.el.dataset.f;
    live.delete(this);
  }
  flip(nw: string, now: number) {
    const old = this.shown;
    this.shown = nw;
    this.paint(nw, old);
    this.el.dataset.f = "m";
    this.half = now + Math.min(34, this.step * 0.5);
  }
  land() {
    this.half = 0;
    this.paint(this.shown, this.shown);
    delete this.el.dataset.f;
  }
}

const live = new Set<Cell>();

/** Send a cell to a character: it riffles forward through its drum (at most maxSteps flaps) after `delay` ms. */
function aim(c: Cell, raw: string, delay = 0, maxSteps = 11) {
  const ch = raw || " ";
  if (reduced) { c.instant(ch); return; }
  const N = c.set.length;
  let ti = c.set.indexOf(ch);
  c.free = "";
  if (ti < 0) { c.free = ch; ti = (c.cur + 3) % N; }
  if (ti === c.cur && c.shown === ch) { if (!c.half) live.delete(c); return; }
  let d = (ti - c.cur + N) % N;
  if (d === 0) d = N;
  if (d > maxSteps) c.cur = (ti - maxSteps + N) % N;
  c.tgt = ti;
  c.due = performance.now() + delay;
  live.add(c);
}

function tickCells() {
  if (!live.size) return;
  const now = performance.now();
  clicks = 0;
  for (const c of live) {
    if (c.half && now >= c.half) c.land();
    if (now < c.due) continue;
    const landed = c.cur === c.tgt && c.shown === (c.free || c.set[c.cur]);
    if (landed) { if (!c.half) live.delete(c); continue; }
    c.cur = (c.cur + 1) % c.set.length;
    c.flip(c.cur === c.tgt && c.free ? c.free : c.set[c.cur], now);
    c.due = now + c.step;
    if (soundOn && clicks < 4) { clicks++; clack(); }
  }
}

// ---------------------------------------------------------------- sound (opt-in): a synthesised flap click
let ac: AudioContext | null = null;
let clickBuf: AudioBuffer | null = null;
function clack() {
  if (!ac || !clickBuf) return;
  const s = ac.createBufferSource();
  s.buffer = clickBuf;
  s.playbackRate.value = 0.85 + Math.random() * 0.35;
  const g = ac.createGain();
  g.gain.value = 0.05 + Math.random() * 0.05;
  s.connect(g).connect(ac.destination);
  s.start();
}
function initSound() {
  if (ac) return;
  try {
    ac = new AudioContext();
    const n = Math.floor(ac.sampleRate * 0.022);
    clickBuf = ac.createBuffer(1, n, ac.sampleRate);
    const d = clickBuf.getChannelData(0);
    // two short knocks: the flap leaving the top and hitting the stop
    for (let i = 0; i < n; i++) {
      const t = i / ac.sampleRate;
      const k1 = Math.exp(-t * 900), k2 = t > 0.009 ? Math.exp(-(t - 0.009) * 700) * 0.7 : 0;
      d[i] = (Math.random() * 2 - 1) * (k1 + k2) * 0.9 + Math.sin(t * 2 * Math.PI * 1900) * k1 * 0.4;
    }
  } catch { ac = null; }
}

// ---------------------------------------------------------------- lines of cells
class Line {
  cells: Cell[];
  el: HTMLElement;
  constructor(n: number, cls = "fl", set = CHARS) {
    this.el = document.createElement("span");
    this.el.className = cls;
    this.cells = Array.from({ length: n }, () => new Cell(set));
    this.cells.forEach((c) => this.el.appendChild(c.el));
  }
  get n() { return this.cells.length; }
  /** Set the text (padded / cut to the line). stagger: ms per cell from the left; jitter: random extra ms. */
  set(text: string, delay = 0, stagger = 22, jitter = 160, align: "left" | "right" | "center" = "left") {
    let t = norm(text).slice(0, this.n);
    const pad = this.n - t.length;
    if (align === "right") t = " ".repeat(pad) + t;
    else if (align === "center") t = " ".repeat(Math.floor(pad / 2)) + t;
    t = t.padEnd(this.n, " ");
    this.cells.forEach((c, i) => aim(c, t[i], delay + i * stagger + Math.random() * jitter));
  }
  now(text: string) {
    const t = norm(text).slice(0, this.n).padEnd(this.n, " ");
    this.cells.forEach((c, i) => c.instant(t[i]));
  }
  /** A tactile acknowledgement: one cell rattles one flap forward and back. */
  twitch() {
    if (reduced) return;
    const nonblank = this.cells.filter((c) => c.shown !== " ");
    const c = nonblank[Math.floor(Math.random() * nonblank.length)];
    if (!c || live.has(c)) return;
    const ch = c.shown, i = c.set.indexOf(ch);
    if (i < 0) return;
    const now = performance.now();
    c.flip(c.set[(i + 1) % c.set.length], now);
    c.cur = c.tgt = (i + 1) % c.set.length;
    c.due = now + 1e6;
    live.add(c);
    setTimeout(() => { const t = performance.now(); c.flip(ch, t); c.cur = c.tgt = i; c.due = t; }, 80);
  }
}

/** Greedy word wrap into rows of `cols`; reports whether everything fit. */
function wrap(text: string, cols: number, rows: number): { lines: string[]; fit: boolean } {
  const words = norm(text).trim().split(" ").filter(Boolean);
  const lines: string[] = [];
  let cur = "";
  for (let w of words) {
    while (w.length > cols) { if (cur) { lines.push(cur); cur = ""; } lines.push(w.slice(0, cols)); w = w.slice(cols); }
    if (!cur) cur = w;
    else if (cur.length + 1 + w.length <= cols) cur += " " + w;
    else { lines.push(cur); cur = w; }
  }
  if (cur) lines.push(cur);
  if (lines.length <= rows) return { lines, fit: true };
  const out = lines.slice(0, rows);
  let last = out[rows - 1];
  while (last.length > cols - 3 && last.includes(" ")) last = last.slice(0, last.lastIndexOf(" "));
  out[rows - 1] = (last.length > cols - 3 ? last.slice(0, cols - 3) : last).replace(/[.,;:]$/, "") + "...";
  return { lines: out, fit: false };
}

/** Flap text that may wrap onto several lines of cells (each line as wide as the longest). */
class Multi {
  lines: Line[];
  rows: string[];
  el: HTMLElement;
  text: string;
  constructor(text: string, cols: number, fixed: number, set: string) {
    this.text = text;
    this.rows = fixed ? [text] : wrap(text, cols, 99).lines;
    const n = fixed || Math.max(1, ...this.rows.map((r) => r.length));
    this.el = document.createElement("span");
    this.el.className = "fls";
    this.el.setAttribute("aria-hidden", "true");
    this.lines = this.rows.map(() => new Line(n, "fl", set));
    this.lines.forEach((l) => this.el.appendChild(l.el));
  }
  show(delay = 0, stagger = 22, jitter = 160, rowGap = 90) { this.lines.forEach((l, r) => l.set(this.rows[r] || "", delay + r * rowGap, stagger, jitter)); }
  blank() { this.lines.forEach((l) => l.now("")); }
  now() { this.lines.forEach((l, r) => l.now(this.rows[r] || "")); }
  change(text: string, delay = 0, stagger = 24, jitter = 80) { this.lines[0].set(text, delay, stagger, jitter); }
  changeNow(text: string) { this.lines[0].now(text); }
  twitch() { this.lines[Math.floor(Math.random() * this.lines.length)].twitch(); }
}

/** Upgrade an element's text to flap cells, keeping the words for assistive technology. Text wider than its
 *  container wraps onto more lines of cells; data-cols fixes a one-line width (status flaps). */
function flapify(el: HTMLElement, fixedCols?: number, set = CHARS): Multi {
  const text = norm(el.textContent || "").trim();
  const fixed = fixedCols || Number(el.dataset.cols) || 0;
  const sr = document.createElement("span");
  sr.className = "sf-sr";
  sr.textContent = el.textContent || "";
  el.textContent = "";
  el.classList.add("is-flaps");
  const tone = el.className.match(/sf-tone--(\w+)/);
  if (tone) el.dataset.tone = tone[1];
  // measure one cell in place to know how many fit across
  const probe = new Line(1, "fl", set);
  el.appendChild(probe.el);
  const cw = probe.cells[0].el.getBoundingClientRect().width + (parseFloat(getComputedStyle(probe.cells[0].el).marginRight) || 0);
  const host = el.parentElement!;
  const avail = Math.max(cw, host.clientWidth - (parseFloat(getComputedStyle(host).paddingLeft) || 0) - (parseFloat(getComputedStyle(host).paddingRight) || 0));
  probe.el.remove();
  const cols = Math.max(4, Math.floor(avail / Math.max(1, cw)));
  const m = new Multi(text, cols, fixed, set);
  el.append(sr, m.el);
  return m;
}

// ---------------------------------------------------------------- the hall
type Dep = { time: string; mins: number; dest: string; head: string; sub: string; gate: string; type: string; scene: boolean; el: HTMLElement | null; desk: HTMLElement | null };

export default function start() {
  const root = document.documentElement;
  const boardQ = $("#sf-board");
  if (!boardQ) return;
  const board: HTMLElement = boardQ;
  root.classList.add("sf-live");
  const displayEl = $(".sf-display", board)!;
  const rowsEl = $(".sf-rows", board)!;
  const clockEl = $(".sf-clock", board)!;
  const main = $("main")!;
  const sectionEls = [...main.children] as HTMLElement[];
  const deps: Dep[] = $$<HTMLTableRowElement>("tbody tr", board).map((tr, i) => {
    const [h, m] = (tr.dataset.time || "09:00").split(":").map(Number);
    const el = sectionEls[i] || null;
    return {
      time: tr.dataset.time || "", mins: h * 60 + m, dest: tr.dataset.dest || "", head: tr.dataset.head || "", sub: tr.dataset.sub || "",
      gate: tr.dataset.gate || "", type: tr.dataset.type || "", scene: !!tr.dataset.scene, el,
      desk: el ? (el.matches(".sf-desk") ? el : el.querySelector<HTMLElement>(".sf-desk")) : null,
    };
  });
  if (!deps.length) return;

  // ------------------------------------------------ sound toggle (muted by default; needs a gesture anyway)
  const soundBtn = $<HTMLButtonElement>(".sf-sound", board);
  if (soundBtn) {
    soundBtn.hidden = false;
    soundBtn.addEventListener("click", () => {
      soundOn = !soundOn;
      if (soundOn) { initSound(); ac?.resume(); }
      soundBtn.setAttribute("aria-pressed", String(soundOn));
      $(".sf-sound__l", soundBtn)!.textContent = soundOn ? "Sound on" : "Sound off";
    });
  }

  // ------------------------------------------------ the clock: HH:MM on digit drums
  const clockLine = new Line(5, "fl fl--clock");
  clockEl.textContent = "";
  clockEl.appendChild(clockLine.el);
  const startMins = deps[0].mins - 5;
  const fmt = (m: number) => { const t = ((Math.floor(m) % 1440) + 1440) % 1440; return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`; };
  clockLine.now(fmt(startMins));
  let shownClock = fmt(startMins);

  // ------------------------------------------------ board geometry (rebuilt when the layout class changes)
  type Field = { key: "time" | "dest" | "via" | "gate" | "status"; n: number; line?: Line; wrap?: HTMLElement };
  type Row = { el: HTMLElement; fields: Field[]; dep: number };
  let rows: Row[] = [];
  let dLines: Line[] = [];
  let dTime: Line, dGate: Line, dStat: Line, dStatWrap: HTMLElement;
  let geomKey = "";
  let dCols = 24, dRows = 2;
  let boardH = 0;

  function build() {
    const W = root.clientWidth, H = innerHeight;
    const phone = W < 700, mid = W < 1100;
    const pad = phone ? 12 : mid ? 22 : 34;
    const avail = W - pad * 2;
    // the boarding display: large cells
    const metaW = phone ? 0 : 200;
    dRows = phone ? 3 : 2;
    dCols = phone ? clamp(Math.floor(avail / 25), 12, 16) : clamp(Math.floor((avail - metaW - 28) / 44), 14, 24);
    const cw = Math.floor(Math.min(phone ? 30 : 46, (avail - metaW - 28) / dCols - (phone ? 3 : 4)));
    const ch = Math.round(cw * 1.38);
    // timetable rows: small cells; the via column takes what is left
    const gap = phone ? 6 : 14;
    const scw = phone ? Math.floor((avail - 2 * gap) / 21 - 2) : mid ? 17 : 19;
    const sch = Math.round(scw * 1.45);
    let fields: Field[];
    if (phone) fields = [{ key: "time", n: 5 }, { key: "dest", n: 9 }, { key: "status", n: 7 }];
    else {
      const fixed = mid ? [5, 11, 9] : [5, 14, 2, 9];
      const total = Math.floor((avail - (fixed.length) * gap) / (scw + 2));
      const via = clamp(total - fixed.reduce((a, b) => a + b, 0), 6, 34);
      fields = mid ? [{ key: "time", n: 5 }, { key: "dest", n: 11 }, { key: "via", n: via }, { key: "status", n: 9 }]
        : [{ key: "time", n: 5 }, { key: "dest", n: 14 }, { key: "via", n: via }, { key: "gate", n: 2 }, { key: "status", n: 9 }];
    }
    const dispH = phone ? 30 + dRows * (ch + 4) + 22 : dRows * (ch + 6) + 26;
    const fixedH = 50 + dispH + 24 + 18;
    const rowH = sch + 5;
    const nRows = clamp(Math.floor((H * (phone ? 0.5 : 0.52) - fixedH) / rowH), 1, phone ? 3 : 5);
    const key = [dCols, dRows, cw, scw, nRows, fields.map((f) => f.n).join("-")].join("/");
    if (key === geomKey) return false;
    geomKey = key;
    board.style.setProperty("--pad", pad + "px");
    board.style.setProperty("--dcw", cw + "px");
    board.style.setProperty("--dch", ch + "px");
    board.style.setProperty("--scw", scw + "px");
    board.style.setProperty("--sch", sch + "px");
    board.style.setProperty("--gap", gap + "px");
    board.classList.toggle("is-phone", phone);
    board.classList.toggle("is-mid", mid && !phone);

    // display
    displayEl.textContent = "";
    const meta = document.createElement("div");
    meta.className = "sf-dmeta";
    dTime = new Line(5, "fl fl--s");
    dGate = new Line(2, "fl fl--s");
    dStat = new Line(phone ? 9 : 9, "fl fl--s");
    const mk = (label: string, line: Line, cls: string) => {
      const w = document.createElement("span");
      w.className = cls;
      if (label) { const l = document.createElement("small"); l.textContent = label; w.appendChild(l); }
      w.appendChild(line.el);
      return w;
    };
    meta.append(mk("Time", dTime, "sf-dm sf-dm--time"), mk("Gate", dGate, "sf-dm sf-dm--gate"));
    dStatWrap = mk("", dStat, "sf-dm sf-dm--stat");
    const lamp = document.createElement("i");
    lamp.className = "sf-lamp";
    dStatWrap.prepend(lamp);
    meta.appendChild(dStatWrap);
    const linesEl = document.createElement("div");
    linesEl.className = "sf-dlines";
    dLines = Array.from({ length: dRows }, () => new Line(dCols, "fl fl--big"));
    dLines.forEach((l) => linesEl.appendChild(l.el));
    displayEl.append(meta, linesEl);

    // rows
    rowsEl.textContent = "";
    const head = document.createElement("div");
    head.className = "sf-colhead";
    const LABEL: Record<string, string> = phone ? { time: "Time", dest: "Destination", status: "Status" } as Record<string, string>
      : { time: "Time · Orario", dest: "Destination", via: "Via", gate: "Gate", status: "Status · Note" };
    fields.forEach((f) => { const s = document.createElement("span"); s.textContent = LABEL[f.key]; s.style.setProperty("--n", String(f.n)); s.dataset.k = f.key; head.appendChild(s); });
    rowsEl.appendChild(head);
    rows = Array.from({ length: nRows }, () => {
      const el = document.createElement("div");
      el.className = "sf-row";
      const fs = fields.map((f) => {
        const line = new Line(f.n, "fl fl--s");
        const w = document.createElement("span");
        w.className = "sf-f sf-f--" + f.key;
        w.appendChild(line.el);
        el.appendChild(w);
        return { ...f, line, wrap: w };
      });
      const row: Row = { el, fields: fs, dep: -1 };
      el.addEventListener("pointerenter", () => row.fields.find((f) => f.key === "dest")?.line!.twitch());
      el.addEventListener("click", () => { const d = deps[row.dep]; if (d?.el) go(d.el); });
      rowsEl.appendChild(el);
      return row;
    });
    return true;
  }

  // ------------------------------------------------ what each part of the board says for boarding index k
  let override: { head: string; sub: string; status: string } | null = null;
  const confirmed = new Set<number>();
  const statusFor = (i: number, k: number) => {
    if (confirmed.has(i)) return { t: "CONFIRMED", tone: "ok" };
    if (i === k) return { t: "BOARDING", tone: "board" };
    if (deps[i].type === "cta") return { t: "GATE OPEN", tone: "board" };
    return { t: "ON TIME", tone: "ok" };
  };
  const headFit = new Map<number, boolean>();
  function displayText(k: number) {
    const d = deps[k];
    const head = override ? override.head : d.head;
    const sub = override ? override.sub : d.sub;
    let { lines, fit } = wrap(head, dCols, dRows);
    if (!override) headFit.set(k, fit);
    const subLines = sub ? wrap(sub, dCols, 99).lines.slice(0, 1) : [];
    const out = [...lines];
    const subRow = out.length < dRows && subLines.length ? out.length : -1;
    if (subRow >= 0) out.push(subLines[0]);
    while (out.length < dRows) out.push("");
    return { out, subRow };
  }

  function paintBoard(k: number, mode: "now" | "cascade" | "refresh") {
    const d = deps[k];
    const { out, subRow } = displayText(k);
    const st = override ? { t: override.status, tone: "board" } : statusFor(k, k);
    dStatWrap.dataset.tone = st.tone;
    displayEl.dataset.sub = String(subRow);
    const rowsTxt = rows.map((_, r) => {
      const i = k + 1 + r;
      const dep = deps[i];
      if (!dep) return i === deps.length ? { i: -1, time: "", dest: "", via: "NO FURTHER DEPARTURES", gate: "", status: { t: "", tone: "" } } : null;
      return { i, time: dep.time, dest: dep.dest, via: dep.head, gate: dep.gate, status: statusFor(i, k) };
    });
    if (mode === "now" || reduced) {
      dTime.now(d.time); dGate.now(d.gate); dStat.now(st.t);
      dLines.forEach((l, r) => l.now(out[r]));
      rows.forEach((row, r) => {
        const t = rowsTxt[r];
        row.dep = t ? t.i : -1;
        row.el.classList.toggle("is-empty", !t || t.i < 0);
        row.fields.forEach((f) => {
          f.line!.now(t ? (f.key === "status" ? t.status.t : (t as any)[f.key]) : "");
          if (f.key === "status") f.wrap!.dataset.tone = t ? t.status.tone : "";
        });
      });
      if (reduced && mode !== "now") { board.classList.remove("is-fade"); void board.offsetWidth; board.classList.add("is-fade"); }
      return;
    }
    const base = mode === "refresh" ? 650 : 0;
    // the boarding row first (headline resolves left to right with ragged landings), then each row below
    dTime.set(d.time, base, 30, 60);
    dGate.set(d.gate, base + 60, 30, 60);
    dStat.set(st.t, base + 120, 26, 80);
    dLines.forEach((l, r) => l.set(out[r], base + (r === subRow ? 600 : r * 90), 20, 240));
    rows.forEach((row, r) => {
      const t = rowsTxt[r];
      row.dep = t ? t.i : -1;
      row.el.classList.toggle("is-empty", !t || t.i < 0);
      const rowDelay = base + 140 + r * 75;
      let col = 0;
      row.fields.forEach((f) => {
        const txt = t ? (f.key === "status" ? t.status.t : (t as any)[f.key]) : "";
        f.line!.set(txt, rowDelay + col * 9, 9, 90);
        col += f.n;
        if (f.key === "status") setTimeout(() => { f.wrap!.dataset.tone = t ? t.status.tone : ""; }, rowDelay + col * 12);
      });
    });
  }

  /** The big moment: the whole board clears to blank in a diagonal wave from the top left. */
  function clearWave() {
    if (reduced) return;
    dLines.forEach((l, r) => l.cells.forEach((c, i) => aim(c, " ", (r + i) * 14, 40)));
    [dTime, dGate, dStat].forEach((l, r) => l.cells.forEach((c, i) => aim(c, " ", (r + i) * 14, 40)));
    rows.forEach((row, r) => { let col = 0; row.fields.forEach((f) => f.line!.cells.forEach((c) => aim(c, " ", (r + 2 + col++ * 0.5) * 14, 40))); });
  }

  // desk headings: hidden (still read) when the board shows the whole headline
  function syncHeads() {
    deps.forEach((d, i) => {
      if (!d.desk) return;
      const fit = wrap(d.head, dCols, dRows).fit;
      d.desk.classList.toggle("sf-on-board", fit && !d.scene);
    });
  }

  // ------------------------------------------------ geometry + thresholds
  let thresholds: number[] = [];
  let docEnd = 1;
  function measure() {
    boardH = board.offsetHeight;
    BOARD_H = boardH;
    root.style.setProperty("--sf-board-h", boardH + "px");
    const deskH = innerHeight - boardH;
    const line = boardH + deskH * 0.42;
    thresholds = deps.map((d, i) => (i === 0 || !d.el) ? -Infinity : d.el.getBoundingClientRect().top + scrollY - line);
    // a section with no element (should not happen) inherits the previous threshold
    for (let i = 1; i < thresholds.length; i++) if (!isFinite(thresholds[i])) thresholds[i] = thresholds[i - 1];
    docEnd = Math.max(1, document.documentElement.scrollHeight - innerHeight);
  }

  function boardingAt(y: number) {
    let k = 0;
    for (let i = 1; i < thresholds.length; i++) if (y >= thresholds[i]) k = i;
    return k;
  }

  function clockAt(y: number, k: number) {
    const prev = k === 0 ? startMins : deps[k - 1].mins;
    const a = k === 0 ? 0 : thresholds[k];
    const b = k + 1 < thresholds.length ? thresholds[k + 1] : docEnd;
    const f = clamp((y - a) / Math.max(1, b - a), 0, 1);
    return prev + (deps[k].mins - prev) * f;
  }

  // ------------------------------------------------ navigation: jumps are a full board refresh
  let pendingRefresh = false;
  function go(el: HTMLElement) {
    pendingRefresh = true;
    // the timetable's own links go through the page's smooth anchor scroll; sections without an id scroll directly
    const a = el.id ? board.querySelector<HTMLAnchorElement>(`tbody a[href="#${CSS.escape(el.id)}"]`) : null;
    if (a) a.click();
    else el.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  }
  $$<HTMLAnchorElement>('a[href^="#"]').forEach((a) => {
    const id = a.getAttribute("href")!;
    if (id.length < 2) return;
    a.addEventListener("click", () => {
      const t = document.querySelector(id);
      if (!t) return;
      const i = deps.findIndex((d) => d.el === t || d.el?.contains(t));
      if (i >= 0 && Math.abs(i - current) > 1) pendingRefresh = true;
    }, { capture: true });
  });

  // ------------------------------------------------ boot
  build();
  syncHeads();
  measure();
  let current = boardingAt(scrollY);
  // opening: blank board; if we load at the top the hero headline riffles in, otherwise the board is simply on
  if (scrollY < 10 && !reduced) {
    dLines.forEach((l) => l.now(""));
    paintBoard(current, "cascade");
  } else paintBoard(current, "now");
  let shownStowed = false;

  let lastW = root.clientWidth, lastH = innerHeight;
  addEventListener("resize", () => {
    if (root.clientWidth === lastW && Math.abs(innerHeight - lastH) < 120) return;   // phone toolbars
    lastW = root.clientWidth; lastH = innerHeight;
    if (build()) { syncHeads(); paintBoard(current, "now"); }
    measure();
  });
  addEventListener("load", measure);
  document.fonts?.ready.then(() => measure());
  let measureT = 0;

  onFrame(({ y, t }) => {
    if (t - measureT > 1.5) { measureT = t; const h = board.offsetHeight; if (h !== boardH) measure(); else docEnd = Math.max(1, document.documentElement.scrollHeight - innerHeight); }
    const k = boardingAt(y);
    if (k !== current) {
      const jump = Math.abs(k - current) > 1 && pendingRefresh;
      current = k;
      override = null;
      if (jump) { clearWave(); paintBoard(k, "refresh"); } else paintBoard(k, "cascade");
      pendingRefresh = false;
      deps.forEach((d, i) => d.desk?.classList.toggle("is-boarding", i === k));
      const stowed = deps[k].scene;
      if (stowed !== shownStowed) { shownStowed = stowed; board.classList.toggle("is-stowed", stowed); }
    }
    const c = fmt(clockAt(y, k));
    if (c !== shownClock) { shownClock = c; clockLine.set(c, 0, 40, 30); }
    tickCells();
  });
  deps.forEach((d, i) => d.desk?.classList.toggle("is-boarding", i === current));

  // ------------------------------------------------ the information desk furniture
  initDesk(deps, (i, head, sub, status) => {
    if (i !== current) return;
    override = { head, sub, status };
    paintBoard(current, "cascade");
  }, (i) => {
    confirmed.add(i);
    if (i === current) paintBoard(current, "cascade");
  });
  initTicker();
}

// ---------------------------------------------------------------- desk components
function initDesk(deps: Dep[], board: (i: number, head: string, sub: string, status: string) => void, confirm: (i: number) => void) {
  // plain flap text: blank until the notice is seen, then it riffles in
  const plain = $$(".sf-desk .sf-flap").filter((el) => !el.closest(".sf-tt, .sf-calling, .sf-final, .sf-msg"));
  plain.forEach((el) => {
    const m = flapify(el);
    m.blank();
    onSeen(el, () => m.show(120, 26, 200), 0.6);
  });

  // features: timetable rows; hover twitches one flap, a click makes the row the boarding row
  $$(".sf-tt").forEach((tt) => {
    const desk = tt.closest<HTMLElement>(".sf-desk");
    const di = deps.findIndex((d) => d.desk === desk);
    const rows = $$(".sf-tt__row", tt);
    const lines = rows.map((row) => $$(".sf-flap", row).map((el) => { const m = flapify(el); m.blank(); return m; }));
    onSeen(tt, () => lines.forEach((ls, r) => ls.forEach((m, j) => m.show(r * 110 + j * 140, 22, 160))), 0.25);
    rows.forEach((row, r) => {
      row.addEventListener("pointerenter", () => lines[r][1]?.twitch());
      const pick = () => {
        rows.forEach((x) => x.classList.toggle("is-picked", x === row));
        const title = lines[r][1]?.text || "";
        const st = lines[r][2]?.text || "ON TIME";
        if (di >= 0) board(di, title, "NO. " + (lines[r][0]?.text || ""), st === "ON TIME" ? "BOARDING" : st);
      };
      row.addEventListener("click", pick);
      row.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    });
  });

  // stats: digit drums with an odometer cadence (units spin fastest), once, on entry
  $$(".sf-digits").forEach((el) => {
    const raw = (el.textContent || "").trim();
    const digitsOnly = /^[\d,.]+$/.test(raw);
    const text = norm(raw);
    const sr = document.createElement("span");
    sr.className = "sf-sr";
    sr.textContent = raw;
    el.textContent = "";
    const cells = [...text].map((ch) => new Cell(/\d/.test(ch) ? DIGITS : CHARS, /\d/.test(ch) ? "0" : " "));
    const wrapEl = document.createElement("span");
    wrapEl.className = "fl fl--drum";
    wrapEl.setAttribute("aria-hidden", "true");
    cells.forEach((c) => wrapEl.appendChild(c.el));
    el.append(sr, wrapEl);
    const target = parseFloat(raw.replace(/,/g, ""));
    const decimals = (raw.split(".")[1] || "").length;
    onSeen(el, () => {
      if (reduced || !digitsOnly || !isFinite(target)) { cells.forEach((c, i) => aim(c, text[i], i * 90, 40)); return; }
      const t0 = performance.now(), D = 1300 + Math.min(900, target * 4);
      const step = () => {
        const f = Math.min(1, (performance.now() - t0) / D);
        const v = target * f;
        const nd = text.replace(/\D/g, "").length;
        const s = (f >= 1 ? raw : decimals ? v.toFixed(decimals) : String(Math.floor(v))).replace(/\D/g, "").padStart(nd, "0").slice(-nd);
        let k = 0;
        cells.forEach((c, i) => { if (/\d/.test(text[i])) aim(c, s[k++], 0, 3); else c.instant(text[i]); });
        if (f < 1) requestAnimationFrame(step);
      };
      // leading zeros stay blank-looking only while counting; the final value is exact
      step();
    }, 0.6);
  });

  // product: the bezel opens in horizontal strips that flip down in sequence
  $$("[data-strips]").forEach((bz) => {
    if (reduced) return;
    const n = 9;
    const shutter = document.createElement("div");
    shutter.className = "sf-shutter";
    shutter.setAttribute("aria-hidden", "true");
    for (let i = 0; i < n; i++) { const s = document.createElement("i"); s.style.setProperty("--i", String(i)); shutter.appendChild(s); }
    bz.appendChild(shutter);
    onSeen(bz, () => shutter.classList.add("is-open"), 0.35);
  });

  // timeline: CALLING AT, statuses flip as the train passes each stop
  $$(".sf-calling").forEach((cl) => {
    const stops = $$(".sf-stop", cl);
    const whens = stops.map((s) => { const m = flapify($(".sf-stop__when .sf-flap", s)!); m.blank(); return m; });
    const sts = stops.map((s) => { const el = $(".sf-stop__st .sf-flap", s)!; const m = flapify(el, 8); return { m, el, shown: "" }; });
    const train = $(".sf-calling__train", cl)!;
    onSeen(cl, () => whens.forEach((w, i) => w.show(i * 120, 26, 140)), 0.2);
    onFrame(() => {
      const r = cl.getBoundingClientRect();
      if (r.bottom < 0 || r.top > innerHeight) return;
      const lineY = BOARD_H + (innerHeight - BOARD_H) * 0.55;
      const dots = stops.map((s) => { const d = $(".sf-stop__dot", s)!.getBoundingClientRect(); return d.top + d.height / 2; });
      let reached = -1;
      dots.forEach((y, i) => { if (y <= lineY) reached = i; });
      sts.forEach((s, i) => {
        const last = i === stops.length - 1;
        const t = i <= reached ? (last ? "ARRIVED" : "DEPARTED") : i === reached + 1 ? "NEXT" : "LATER";
        if (t !== s.shown) {
          const first = s.shown === "";
          s.shown = t;
          s.el.dataset.tone = t === "DEPARTED" ? "gone" : t === "NEXT" ? "board" : t === "ARRIVED" ? "ok" : "later";
          if (first) s.m.changeNow(t); else s.m.change(t, 0, 24, 80);
        }
        stops[i].classList.toggle("is-passed", i <= reached);
      });
      const y = clamp(lineY, dots[0], dots[dots.length - 1]) - r.top;
      train.style.transform = `translateY(${y.toFixed(1)}px)`;
    });
  });

  // quote: a message board (Vestaboard-like grid) that flips the words in, cells landing at random
  $$(".sf-msg").forEach((fig) => {
    const boardEl = $(".sf-msg__board", fig)!;
    const textEl = $(".sf-msg__text", fig)!;
    const text = norm(textEl.textContent || "").trim();
    const w = boardEl.clientWidth || 600;
    let cols = clamp(Math.floor(w / 34), 12, 22), res = wrap(text, cols, 7);
    while (!res.fit && cols < 32) { cols += 2; res = wrap(text, cols, 7); }
    if (!res.fit) return;   // too long for a board: the paragraph stays as it is
    const nRows = Math.max(3, res.lines.length + 1);
    const grid = document.createElement("div");
    grid.className = "sf-grid";
    grid.setAttribute("aria-hidden", "true");
    const mcw = Math.floor(Math.min(40, (w - 8) / cols - 4));
    grid.style.setProperty("--mcw", mcw + "px");
    grid.style.setProperty("--mch", Math.round(mcw * 1.42) + "px");
    const lines = Array.from({ length: nRows }, () => new Line(cols, "fl fl--msg"));
    lines.forEach((l) => grid.appendChild(l.el));
    textEl.classList.add("sf-sr");
    boardEl.appendChild(grid);
    const top = Math.floor((nRows - res.lines.length) / 2);
    const rowsTxt = lines.map((_, r) => res.lines[r - top] || "");
    onSeen(grid, () => lines.forEach((l, r) => l.set(rowsTxt[r], 100 + r * 70, 0, 1100, "center")), 0.4);
    const who = $(".sf-msg__who .sf-flap", fig);
    if (who) { const m = flapify(who); m.blank(); onSeen(who, () => m.show(1300, 30, 120), 0.5); }
  });

  // faq: the queries board; choosing a question flips the ANSWER board, one query at a time
  $$(".sf-queries").forEach((qb) => {
    const items = $$(".sf-qa__item", qb);
    if (!items.length) return;
    const uid = Math.random().toString(36).slice(2, 7);
    const list = document.createElement("div");
    list.className = "sf-qlist";
    list.setAttribute("role", "tablist");
    list.setAttribute("aria-label", "Questions");
    const ans = document.createElement("div");
    ans.className = "sf-answer";
    const ansHead = document.createElement("div");
    ansHead.className = "sf-answer__head";
    ansHead.setAttribute("aria-hidden", "true");
    ansHead.innerHTML = "<span>Answer · Risposta</span><b></b>";
    const w0 = qb.clientWidth || 700;
    const w = innerWidth > 900 ? (w0 - 40) * 0.52 : w0;   // the answer board takes the right column on wide screens
    const cols = clamp(Math.floor((w - 36) / 24), 12, 26);
    const aLines = Array.from({ length: 3 }, () => new Line(cols, "fl fl--a"));
    const grid = document.createElement("div");
    grid.className = "sf-agrid";
    const acw = Math.floor(Math.min(24, (w - 36) / cols - 2));
    grid.style.setProperty("--acw", acw + "px");
    grid.style.setProperty("--ach", Math.round(acw * 1.45) + "px");
    grid.setAttribute("aria-hidden", "true");
    aLines.forEach((l) => grid.appendChild(l.el));
    const full = document.createElement("div");
    full.className = "sf-answer__full";
    ans.append(ansHead, grid, full);
    const btns: HTMLButtonElement[] = [];
    const panels: HTMLElement[] = [];
    items.forEach((it, i) => {
      const q = $(".sf-qa__qt", it)!, a = $(".sf-qa__a", it)!;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "sf-qbtn";
      b.id = `sfq-${uid}-${i}`;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-controls", `sfa-${uid}-${i}`);
      b.innerHTML = `<span class="sf-qbtn__n" aria-hidden="true">Q${i + 1}</span><span class="sf-qbtn__t"></span>`;
      $(".sf-qbtn__t", b)!.innerHTML = q.innerHTML;
      const p = document.createElement("div");
      p.className = "sf-apanel";
      p.id = `sfa-${uid}-${i}`;
      p.setAttribute("role", "tabpanel");
      p.setAttribute("aria-labelledby", b.id);
      p.innerHTML = a.innerHTML;
      list.appendChild(b);
      full.appendChild(p);
      btns.push(b);
      panels.push(p);
    });
    const shortOf = (s: string) => {
      const t = norm(s).trim();
      const first = (t.match(/^.*?[.!?](\s|$)/) || [t])[0].trim();
      return wrap(first, cols, 3).lines;
    };
    let sel = -1;
    const pick = (i: number, quiet = false) => {
      if (i === sel) return;
      sel = i;
      btns.forEach((b, j) => { b.setAttribute("aria-selected", String(j === i)); b.tabIndex = j === i ? 0 : -1; b.classList.toggle("is-on", j === i); });
      panels.forEach((p, j) => { p.hidden = j !== i; });
      $("b", ansHead)!.textContent = "Q" + (i + 1);
      const ls = shortOf(panels[i].textContent || "");
      aLines.forEach((l, r) => quiet ? l.now(ls[r] || "") : l.set(ls[r] || "", r * 80, 22, 200));
      if (!quiet && !reduced) { btns[i].classList.remove("is-flip"); void btns[i].offsetWidth; btns[i].classList.add("is-flip"); }
    };
    btns.forEach((b, i) => {
      b.addEventListener("click", () => pick(i));
      b.addEventListener("keydown", (e) => {
        const d = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
        if (!d) return;
        e.preventDefault();
        const j = (sel + d + btns.length) % btns.length;
        pick(j); btns[j].focus();
      });
    });
    $(".sf-qa", qb)!.remove();
    qb.append(list, ans);
    qb.classList.add("is-live");
    aLines.forEach((l) => l.now(""));
    sel = -1;
    btns.forEach((b) => b.setAttribute("aria-selected", "false"));
    onSeen(qb, () => pick(0), 0.3);
    panels.forEach((p, j) => { p.hidden = j !== 0; });
  });

  // cta: NOW BOARDING · GATE 1; pressing the key confirms the ticket
  $$(".sf-final").forEach((row) => {
    const desk = row.closest<HTMLElement>(".sf-desk");
    const di = deps.findIndex((d) => d.desk === desk);
    const lines = $$(".sf-flap", row).map((el) => { const m = flapify(el); m.blank(); return { m, el }; });
    onSeen(row, () => lines.forEach((x, i) => x.m.show(i * 260, 30, 160)), 0.5);
    const key = $<HTMLAnchorElement>(".sf-key--board", desk || document);
    const note = $(".sf-confirm", desk || document);
    key?.addEventListener("click", (e) => {
      const st = lines[lines.length - 1];
      if (row.classList.contains("is-confirmed")) return;
      row.classList.add("is-confirmed");
      st.el.dataset.tone = "ok";
      st.m.change("CONFIRMED", 0, 30, 120);
      if (note) note.textContent = "Ticket confirmed.";
      if (di >= 0) confirm(di);
      const href = key.getAttribute("href") || "";
      if (href && href !== "#") { e.preventDefault(); setTimeout(() => { location.href = key.href; }, reduced ? 0 : 900); }
      else e.preventDefault();
    });
  });

  // keys: the top half flips down when pressed (CSS); keyboard presses get the same state
  $$(".sf-key").forEach((k) => {
    k.addEventListener("keydown", (e) => { if ((e as KeyboardEvent).key === "Enter") { k.classList.add("is-press"); setTimeout(() => k.classList.remove("is-press"), 180); } });
  });
}

// ---------------------------------------------------------------- footer ticker: one row of announcements
function initTicker() {
  const el = $(".sf-ticker");
  if (!el) return;
  const msgs = (el.dataset.msgs || "").split("|").map((s) => s.trim()).filter(Boolean);
  if (!msgs.length) return;
  const w = el.clientWidth || 600;
  const cols = clamp(Math.floor(w / 19), 12, 48);
  const line = new Line(cols, "fl fl--tick");
  el.appendChild(line.el);
  const chunks: string[] = [];
  msgs.forEach((m) => chunks.push(...wrap(m, cols, 99).lines));
  let i = 0;
  line.now("");
  let visible = false, timer = 0;
  const next = () => { line.set(chunks[i % chunks.length], 0, 18, 160); i++; };
  new IntersectionObserver((es) => es.forEach((e) => {
    visible = e.isIntersecting;
    if (visible && !timer) { next(); timer = window.setInterval(() => { if (visible && !document.hidden) next(); }, 6500); }
    if (!visible && timer) { clearInterval(timer); timer = 0; }
  })).observe(el);
}
