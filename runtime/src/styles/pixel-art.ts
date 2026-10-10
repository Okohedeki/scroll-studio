/**
 * Pixel art: the site is a game. A title screen says PRESS START; scrolling is the controller. Each wheel notch walks
 * a sprite through one long side-scrolling level (whole art pixels, stepped walk frames, no momentum: when the
 * scroll stops, the player stops and taps a foot). Every section is a stop: a sign, ? blocks that pop ITEM GET!
 * cards, a gear monitor, a save crystal with the status sheet, milestone flags with an overworld map, an NPC whose
 * dialog advances one notch at a time, a sage with an ASK ABOUT menu, and the flagpole: COURSE CLEAR and CONTINUE?.
 * The document keeps a real height (scrollbar, keyboard, anchors all work); READ AS PAGE shows the plain manual.
 * Everything is drawn here on one canvas from tiny pixel maps; there are no images.
 */
import { $, $$, onFrame, reduced } from "./_kit";

// ---------------------------------------------------------------- palette (PICO-8) and pixel maps
const PAL: Record<string, string> = {
  k: "#000000", n: "#1d2b53", p: "#7e2553", g: "#008751", b: "#ab5236", d: "#5f574f", l: "#c2c3c7", w: "#fff1e8",
  r: "#ff004d", o: "#ffa300", y: "#ffec27", G: "#00e436", B: "#29adff", v: "#83769c", P: "#ff77a8", s: "#ffccaa",
};
const BODY = [
  "...BBBB...",
  "..BBBBBB..",
  "..BwBBBB..",
  "..ssssss..",
  "..sssksk..",
  "..ssssss..",
  "...ssss...",
  "..yyyyyy..",
  ".yyyyyyyy.",
  ".syyyyyys.",
  "..yyyyyy..",
];
const LEGS = [
  ["..nn..nn..", "..nn..nn..", ".bbb..bbb."],
  ["..nn...nn.", ".nn....nn.", "bbb....bbb"],
  ["...nnnn...", "...nnn....", "...bbbb..."],
  [".nn..nn...", "nn....nn..", "bb.....bbb"],
];
const TAP = ["..nn..nn..", "..nn..nn..", ".bbb..b.bb"];
const HAT_SAGE = ["....p.....", "...ppp....", "..ppppp...", ".ppppppp.."];
const ITEMS: Record<string, string[]> = {
  star: ["...yy...", "...yy...", "yyyyyyyy", ".yyyyyy.", "..yyyy..", ".yy..yy.", "yy....yy", "........"],
  heart: [".rr..rr.", "rrrrrrrr", "rrwrrrrr", "rrrrrrrr", ".rrrrrr.", "..rrrr..", "...rr...", "........"],
  gem: ["..BBBB..", ".BwwBBB.", "BwBBBBBB", ".BBBBBB.", "..BBBB..", "...BB...", "........", "........"],
  key: [".yyy....", "y...y...", "y...yyyy", "y...y.y.", ".yyy..y.", "........", "........", "........"],
  potion: ["...ll...", "...ll...", "..llll..", ".GGGGGG.", "GGwGGGGG", "GGGGGGGG", ".GGGGGG.", "........"],
  shield: ["BBBBBBBB", "BwwBBBBB", "BwBBBBBB", "BBBBBBBB", ".BBBBBB.", "..BBBB..", "...BB...", "........"],
  clock: ["..wwww..", ".wkwwww.", "wwwkwwww", "wwwkkkww", "wwwwwwww", ".wwwwww.", "..wwww..", "........"],
  coin: ["..yyyy..", ".yyoyyy.", "yyyoyyyy", "yyyoyyyy", "yyyoyyyy", ".yyoyyy.", "..yyyy..", "........"],
};
const QMARK = [".www.", "w...w", "....w", "...w.", "..w..", ".....", "..w.."];

const hash = (n: number) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
const vnoise = (x: number, seed: number) => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return hash(i + seed * 97) * (1 - u) + hash(i + 1 + seed * 97) * u; };
const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));

function recolor(rows: string[], map: Record<string, string>) { return rows.map((r) => [...r].map((c) => map[c] ?? c).join("")); }
function blit(g: CanvasRenderingContext2D, rows: string[], x: number, y: number, flip = false) {
  const w = rows[0].length;
  for (let j = 0; j < rows.length; j++) {
    const r = rows[j];
    for (let i = 0; i < w; i++) {
      const c = r[flip ? w - 1 - i : i];
      if (c === ".") continue;
      g.fillStyle = PAL[c] || c;
      g.fillRect(x + i, y + j, 1, 1);
    }
  }
}
function spriteURL(rows: string[], scale: number) {
  const c = document.createElement("canvas");
  c.width = rows[0].length * scale; c.height = rows.length * scale;
  const g = c.getContext("2d")!;
  g.scale(scale, scale);
  blit(g, rows, 0, 0);
  return c.toDataURL();
}

// ---------------------------------------------------------------- the level
type Obj = { kind: string; x: number; i?: number; data?: any };
type Zone = {
  el: HTMLElement; type: string; idx: number;
  x0: number; x1: number; trig: number;            // world x: start, end, where its window opens
  y0: number; yT: number; y1: number;              // scroll: start, end of travel, end of lock
  steps: number; objs: Obj[];
};

const K = 2.3;          // scroll px per art px of walking
const GROUND = 34;      // ground band height (art px)
const TITLE_SCROLL = 150;

export default function start() {
  const root = document.documentElement;
  const main = $("main");
  const canvas = $<HTMLCanvasElement>(".px-canvas");
  const hud = $("#px-hud");
  if (!main || !canvas || !hud) return;
  const sections = [...main.children] as HTMLElement[];
  const hasScenes = !!main.querySelector("[data-scene]");
  const modeBtn = $<HTMLButtonElement>(".px-mode", hud)!;
  const startBtn = $<HTMLButtonElement>(".px-startbtn", hud)!;
  const pauseEl = $<HTMLElement>("#px-pause")!;
  const banner = $(".px-banner")!;

  // ------------------------------------------------ sprites for the DOM (item icons, portraits)
  $$(".px-icon").forEach((el) => {
    const k = [...el.classList].find((c) => c.startsWith("px-icon--"))?.slice(9) || "star";
    el.style.backgroundImage = `url(${spriteURL(ITEMS[k] || ITEMS.star, 6)})`;
  });
  const npcPal = (name: string) => {
    let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    const hats = ["r", "p", "G", "o", "b"], coats = ["P", "G", "r", "v", "B"];
    return { B: hats[h % hats.length], y: coats[(h >> 3) % coats.length] };
  };
  $$(".px-portrait").forEach((el) => {
    const who = el.closest(".px-sec")?.querySelector(".px-name")?.textContent || "npc";
    el.style.backgroundImage = `url(${spriteURL(recolor(BODY.slice(0, 7), npcPal(who)), 8)})`;
  });
  $$(".px-status__face").forEach((el) => { el.style.backgroundImage = `url(${spriteURL(BODY.slice(0, 7), 6)})`; });

  // ------------------------------------------------ mode: game or read-as-page
  let game = !hasScenes;
  try { if (sessionStorage.getItem("px-mode") === "page") game = false; } catch { /* storage blocked */ }
  if (!hasScenes) { modeBtn.hidden = false; startBtn.hidden = false; }

  // quotes are split into dialog pages: whole sentences, about two lines each
  $$(".px-dialog--npc").forEach((d) => {
    const text = ($(".px-say", d)!.textContent || "").trim().replace(/\s+/g, " ");
    const sentences = text.match(/[^.!?]+[.!?]+["')\]]*\s*|[^.!?]+$/g) || [text];
    const pages: string[] = [];
    let cur = "";
    for (const sn of sentences.map((x) => x.trim())) {
      if (cur && (cur + " " + sn).length > 110) { pages.push(cur); cur = sn; } else cur = (cur + " " + sn).trim();
      while (cur.length > 150) { const cut = cur.lastIndexOf(" ", 110); pages.push(cur.slice(0, cut)); cur = cur.slice(cut + 1); }
    }
    if (cur) pages.push(cur);
    (d.closest(".px-sec") as any).__pages = pages;
  });

  // ------------------------------------------------ zones from the sections
  const zones: Zone[] = [];
  let worldEnd = 0, totalScroll = 0;
  function layoutZones() {
    zones.length = 0;
    let x = 40, y = 0;
    sections.forEach((el, idx) => {
      const type = el.dataset.zone || (el.matches("[data-scene]") ? "scene" : "other");
      const z: Zone = { el, type, idx, x0: x, x1: x, trig: x, y0: y, yT: y, y1: y, steps: 0, objs: [] };
      const n = (sel: string) => el.querySelectorAll(sel).length;
      if (type === "hero" && idx === 0) {
        z.y1 = z.yT = TITLE_SCROLL;
        z.trig = x - 999;
      } else {
        let travel = 150, lock = 0;
        if (type === "intro") { z.objs.push({ kind: "sign", x: x + 110 }); z.trig = x + 80; travel = 170; }
        else if (type === "features") {
          const k = Math.max(1, n(".px-item"));
          for (let i = 0; i < k; i++) z.objs.push({ kind: "block", x: x + 70 + i * 100, i });
          z.trig = x + 60; travel = 70 + k * 100 + 40;
        } else if (type === "product") { z.objs.push({ kind: "tv", x: x + 100 }); z.trig = x + 70; travel = 190; }
        else if (type === "stats") { z.objs.push({ kind: "crystal", x: x + 90 }); z.trig = x + 70; travel = 150; }
        else if (type === "timeline") {
          const k = Math.max(1, n(".px-node"));
          for (let i = 0; i < k; i++) z.objs.push({ kind: "flag", x: x + 50 + i * 80, i });
          z.trig = x + 30; travel = 50 + k * 80 + 30;
        } else if (type === "quote") { z.objs.push({ kind: "npc", x: x + 130 }); z.trig = x + 100; travel = 112; lock = Math.max(1, ((el as any).__pages || [1]).length); }
        else if (type === "faq") { z.objs.push({ kind: "sage", x: x + 120 }); z.trig = x + 90; travel = 102; lock = Math.max(1, n(".px-qa__i")); }
        else if (type === "cta") { z.objs.push({ kind: "pole", x: x + 150 }, { kind: "castle", x: x + 200 }); z.trig = x + 150; travel = 150; lock = 2; }
        else { z.objs.push({ kind: "sign", x: x + 90 }); z.trig = x + 60; travel = 150; }
        z.x1 = x + travel;
        z.yT = y + travel * K;
        z.steps = lock;
        z.y1 = z.yT + lock * 130;
        x = z.x1; y = z.y1;
      }
      y = z.y1; zones.push(z);
    });
    worldEnd = x + 260;
    totalScroll = y;
    if (game) main!.style.height = `${Math.ceil(totalScroll + innerHeight)}px`;
  }

  // quote pages are known once their text is split
  const pagesOf = (z: Zone) => (z.el as any).__pages as string[] | undefined;

  function xAt(y: number) {
    for (const z of zones) {
      if (y < z.y0) return z.x0;
      if (y <= z.yT) return z.x0 + (z.x1 - z.x0) * clamp((y - z.y0) / Math.max(1, z.yT - z.y0));
      if (y <= z.y1) return z.x1;
    }
    return zones.length ? zones[zones.length - 1].x1 : 0;
  }
  const zoneAtScroll = (y: number) => { let k = 0; zones.forEach((z, i) => { if (y >= z.y0) k = i; }); return k; };
  const stopY = (z: Zone) => (z.type === "hero" ? 0 : z.y0 + (z.trig + 4 - z.x0) * K);

  // ------------------------------------------------ canvas
  const g = canvas.getContext("2d")!;
  const buf = document.createElement("canvas"), bg = buf.getContext("2d")!;
  const tiny = document.createElement("canvas"), tg = tiny.getContext("2d")!;
  let S = 4, W = 320, H = 200, GY = 160;
  function size() {
    S = Math.max(3, Math.min(6, Math.round(Math.min(innerHeight / 175, innerWidth / 150))));
    W = Math.ceil(innerWidth / S); H = Math.ceil(innerHeight / S); GY = H - GROUND;
    for (const c of [canvas!, buf]) { c.width = W; c.height = H; }
    canvas!.style.width = W * S + "px"; canvas!.style.height = H * S + "px";
    g.imageSmoothingEnabled = false; bg.imageSmoothingEnabled = false; tg.imageSmoothingEnabled = false;
    root.style.setProperty("--px-s", String(S));
    root.style.setProperty("--px-ground", `${GROUND * S}px`);
  }

  // ------------------------------------------------ state
  let px = 40, target = 40, face = 1, walking = false, walkF = 0, lastStepT = 0, lastY = scrollY, firstFrame = true;
  const hitAt = new Map<string, number>();          // block key -> time it was hit
  const collected = new Set<string>();
  const flagsPassed = new Set<string>();
  let score = 0, shownScore = -1, timeLeft = 400, timeT = performance.now(), clearT = 0, poleT = 0;
  let mosaic = 0, mosaicDir = 0, mosaicCb: (() => void) | null = null, mosaicT = 0;

  // ------------------------------------------------ drawing
  function drawBG(cx: number, t: number) {
    const G = bg;
    G.fillStyle = PAL.B; G.fillRect(0, 0, W, GY);
    // dithered horizon band
    G.fillStyle = PAL.w;
    for (let y = GY - 26; y < GY; y++) for (let x = (y & 1); x < W; x += y > GY - 12 ? 2 : 4) G.fillRect(x, y, 1, 1);
    // clouds (0.2)
    const c0 = Math.floor((cx * 0.2) / 120) - 1;
    for (let k = c0; k < c0 + W / 120 + 3; k++) {
      const x = Math.round(k * 120 + hash(k) * 60 - cx * 0.2), y = 18 + Math.round(hash(k + 9) * 40);
      const w = 22 + Math.round(hash(k + 3) * 18);
      G.fillStyle = PAL.w;
      G.fillRect(x + 4, y, w - 8, 2); G.fillRect(x + 1, y + 2, w - 2, 5); G.fillRect(x, y + 4, w, 4); G.fillRect(x + 8, y - 3, 10, 3);
      G.fillStyle = PAL.l; G.fillRect(x + 1, y + 8, w - 2, 1);
    }
    // mountains (0.35)
    for (let x = 0; x < W; x++) {
      const wx = x + cx * 0.35;
      const h = Math.round(30 + 34 * vnoise(wx / 46, 1) + 10 * vnoise(wx / 13, 2));
      G.fillStyle = PAL.v; G.fillRect(x, GY - h, 1, h);
      if (h > 54) { G.fillStyle = PAL.w; G.fillRect(x, GY - h, 1, Math.min(4, h - 54)); }
    }
    // hills (0.6)
    for (let x = 0; x < W; x++) {
      const wx = x + cx * 0.6;
      const h = Math.round(12 + 16 * vnoise(wx / 30, 4));
      G.fillStyle = PAL.g; G.fillRect(x, GY - h, 1, h);
      G.fillStyle = PAL.G; G.fillRect(x, GY - h, 1, 1);
    }
    // ground (1.0)
    G.fillStyle = PAL.b; G.fillRect(0, GY, W, GROUND);
    G.fillStyle = PAL.G; G.fillRect(0, GY, W, 3);
    G.fillStyle = PAL.g; G.fillRect(0, GY + 3, W, 1);
    const t0 = Math.floor(cx / 8);
    for (let k = t0; k < t0 + W / 8 + 2; k++) {
      const x = k * 8 - cx;
      G.fillStyle = PAL.d;
      G.fillRect(x + Math.floor(hash(k) * 7), GY + 8 + Math.floor(hash(k + 1) * 20), 2, 1);
      G.fillStyle = PAL.o;
      if (hash(k + 5) > 0.7) G.fillRect(x + 3, GY + 14 + Math.floor(hash(k + 2) * 14), 1, 1);
      // tufts and flowers
      if (hash(k + 11) > 0.82) { G.fillStyle = PAL.G; G.fillRect(x + 2, GY - 2, 1, 2); G.fillRect(x + 4, GY - 3, 1, 3); G.fillRect(x + 6, GY - 2, 1, 2); }
      if (hash(k + 17) > 0.93) { G.fillStyle = PAL.P; G.fillRect(x + 3, GY - 4, 2, 2); G.fillStyle = PAL.G; G.fillRect(x + 3, GY - 2, 1, 2); }
    }
  }

  function drawObj(o: Obj, z: Zone, cx: number, t: number, now: number) {
    const G = bg, x = Math.round(o.x - cx);
    if (x < -80 || x > W + 80) return;
    if (o.kind === "sign") {
      G.fillStyle = PAL.b; G.fillRect(x + 9, GY - 16, 2, 16);
      G.fillStyle = PAL.b; G.fillRect(x, GY - 28, 20, 13);
      G.fillStyle = PAL.s; G.fillRect(x + 1, GY - 27, 18, 11);
      G.fillStyle = PAL.d; G.fillRect(x + 3, GY - 24, 12, 1); G.fillRect(x + 3, GY - 21, 14, 1); G.fillRect(x + 3, GY - 18, 9, 1);
    } else if (o.kind === "block") {
      const key = `${z.idx}:${o.i}`;
      const hit = hitAt.get(key);
      const bump = hit && now - hit < 180 ? [0, -2, -3, -2, -1][Math.min(4, Math.floor((now - hit) / 36))] : 0;
      const y = GY - 46 + bump;
      if (hit) {
        G.fillStyle = PAL.b; G.fillRect(x, y, 16, 16);
        G.fillStyle = PAL.d; G.fillRect(x, y + 15, 16, 1); G.fillRect(x + 15, y, 1, 16);
        G.fillStyle = PAL.k; G.fillRect(x + 2, y + 2, 1, 1); G.fillRect(x + 13, y + 2, 1, 1); G.fillRect(x + 2, y + 13, 1, 1); G.fillRect(x + 13, y + 13, 1, 1);
        // the item pops out in an arc and vanishes into the inventory
        const dt = now - hit;
        if (dt < 560 && !reduced) {
          const f = Math.floor(dt / 70);
          const iy = y - 10 - [0, 6, 10, 12, 12, 10, 7, 3][Math.min(7, f)];
          const name = (z.el.querySelectorAll(".px-item")[o.i!] as HTMLElement | undefined)?.dataset.icon || "star";
          blit(G, ITEMS[name] || ITEMS.star, x + 4, iy);
        }
      } else {
        const blink = Math.floor(t * 2) % 4 === 0;
        G.fillStyle = PAL.b; G.fillRect(x, y, 16, 16);
        G.fillStyle = blink ? PAL.y : PAL.o; G.fillRect(x + 1, y + 1, 14, 14);
        G.fillStyle = PAL.y; G.fillRect(x + 1, y + 1, 14, 1); G.fillRect(x + 1, y + 1, 1, 14);
        G.fillStyle = PAL.b; G.fillRect(x + 2, y + 2, 1, 1); G.fillRect(x + 13, y + 2, 1, 1); G.fillRect(x + 2, y + 13, 1, 1); G.fillRect(x + 13, y + 13, 1, 1);
        blit(G, QMARK.map((r) => r.replace(/w/g, "b")), x + 6, y + 5);
        blit(G, QMARK, x + 5, y + 4);
      }
    } else if (o.kind === "tv") {
      G.fillStyle = PAL.d; G.fillRect(x + 8, GY - 8, 3, 8); G.fillRect(x + 37, GY - 8, 3, 8);
      G.fillStyle = PAL.d; G.fillRect(x, GY - 44, 48, 36);
      G.fillStyle = PAL.l; G.fillRect(x + 1, GY - 43, 46, 1);
      G.fillStyle = PAL.n; G.fillRect(x + 3, GY - 41, 42, 28);
      const sc = Math.floor(t * 3) % 3;
      G.fillStyle = PAL.B; G.fillRect(x + 6, GY - 38, 18, 2);
      G.fillStyle = PAL.w; G.fillRect(x + 6, GY - 33, 34, 4);
      G.fillStyle = PAL.l; G.fillRect(x + 6, GY - 27, 30, 3); G.fillRect(x + 6, GY - 22, 26, 3);
      G.fillStyle = PAL.G; G.fillRect(x + 6 + sc, GY - 17, 12, 2);
      G.fillStyle = PAL.r; G.fillRect(x + 42, GY - 11, 2, 2);
    } else if (o.kind === "crystal") {
      const bob = reduced ? 0 : [0, -1, -2, -1][Math.floor(t * 4) % 4];
      const y = GY - 30 + bob;
      G.fillStyle = PAL.d; G.fillRect(x - 2, GY - 4, 16, 4); G.fillStyle = PAL.l; G.fillRect(x - 2, GY - 4, 16, 1);
      const rows = ["....BB....", "...BwBB...", "..BwBBBB..", ".BwBBBBBn.", "BBBBBBBBnn", ".BBBBBBnn.", "..BBBBnn..", "...BBnn...", "....nn...."];
      blit(G, rows, x, y);
      if (Math.floor(t * 2) % 2 && !reduced) { G.fillStyle = PAL.w; G.fillRect(x - 3, y + 2, 1, 1); G.fillRect(x + 12, y + 7, 1, 1); }
    } else if (o.kind === "flag") {
      const passed = flagsPassed.has(`${z.idx}:${o.i}`);
      G.fillStyle = PAL.l; G.fillRect(x, GY - 26, 1, 26);
      G.fillStyle = passed ? PAL.G : PAL.r; G.fillRect(x + 1, GY - 26, 8, 6);
      G.fillStyle = PAL.w; G.fillRect(x + 3, GY - 24, 2, 2);
      G.fillStyle = PAL.d; G.fillRect(x - 2, GY - 1, 5, 1);
    } else if (o.kind === "npc" || o.kind === "sage") {
      const who = z.el.querySelector(".px-name")?.textContent || "npc";
      let rows = recolor([...BODY, ...LEGS[0]], o.kind === "sage" ? { B: "p", y: "v" } : npcPal(who));
      if (o.kind === "sage") rows = [...HAT_SAGE, ...rows.slice(3)];
      const idle = Math.floor(t * 2) % 2 === 0;
      blit(G, idle ? rows : [...rows.slice(0, -3), ...TAP], x, GY - rows.length, true);
      if (o.kind === "sage" || active === z.idx) {
        // a speech mark over the head
        const by = GY - rows.length - 12 + (reduced ? 0 : Math.floor(t * 2) % 2);
        G.fillStyle = PAL.w; G.fillRect(x + 1, by, 9, 8); G.fillRect(x + 3, by + 8, 2, 2);
        G.fillStyle = PAL.k; blit(G, (o.kind === "sage" ? QMARK : ["..k..", "..k..", "..k..", "..k..", ".....", "..k..", "....."]).map((r) => r.replace(/w/g, "k")), x + 3, by + 1);
      }
    } else if (o.kind === "pole") {
      G.fillStyle = PAL.l; G.fillRect(x, GY - 88, 2, 88);
      G.fillStyle = PAL.y; G.fillRect(x - 1, GY - 92, 4, 4);
      const dt = poleT ? now - poleT : 0;
      const fy = poleT ? Math.min(70, Math.floor(dt / 40) * 4) : 0;
      G.fillStyle = PAL.G; G.fillRect(x - 12, GY - 86 + fy, 12, 9);
      G.fillStyle = PAL.w; G.fillRect(x - 8, GY - 83 + fy, 3, 3);
      G.fillStyle = PAL.d; G.fillRect(x - 3, GY - 6, 8, 6);
    } else if (o.kind === "castle") {
      G.fillStyle = PAL.l; G.fillRect(x, GY - 40, 56, 40);
      for (let i = 0; i < 7; i++) G.fillRect(x + i * 8, GY - 46, 5, 6);
      G.fillStyle = PAL.d;
      for (let r = 0; r < 5; r++) for (let i = 0; i < 7; i++) G.fillRect(x + i * 8 + (r % 2) * 4, GY - 36 + r * 8, 6, 1);
      G.fillStyle = PAL.k; G.fillRect(x + 22, GY - 18, 12, 18); G.fillRect(x + 24, GY - 20, 8, 2);
      G.fillStyle = PAL.k; G.fillRect(x + 8, GY - 30, 5, 6); G.fillRect(x + 43, GY - 30, 5, 6);
    }
  }

  function drawPlayer(cx: number, t: number, now: number) {
    let legs = LEGS[0];
    if (walking) legs = LEGS[walkF % 4];
    else if (!reduced && Math.floor(t * 2) % 2 === 1) legs = TAP;
    let body = BODY;
    if (!reduced && Math.floor(t * 10) % 37 === 0) body = BODY.map((r, i) => (i === 4 ? "..ssssss.." : r));
    blit(bg, [...body, ...legs], Math.round(px - cx) - 5, GY - 14, face < 0);
  }

  function render(t: number, now: number) {
    const cx = Math.max(0, Math.min(worldEnd - W, Math.round(px - W * 0.36)));
    drawBG(cx, t);
    for (const z of zones) for (const o of z.objs) drawObj(o, z, cx, t, now);
    drawPlayer(cx, t, now);
    if (mosaic > 1) {
      const w = Math.max(1, Math.ceil(W / mosaic)), h = Math.max(1, Math.ceil(H / mosaic));
      tiny.width = w; tiny.height = h; tg.imageSmoothingEnabled = false;
      tg.drawImage(buf, 0, 0, w, h);
      g.imageSmoothingEnabled = false;
      g.drawImage(tiny, 0, 0, w, h, 0, 0, W, H);
    } else g.drawImage(buf, 0, 0);
  }

  // ------------------------------------------------ typewriter dialogs (the words stay in the page for everyone)
  type Typer = { src: HTMLElement; out: HTMLElement; text: string; t0: number; done: boolean };
  const typers = new Map<HTMLElement, Typer>();
  function typer(src: HTMLElement): Typer {
    let ty = typers.get(src);
    if (ty) return ty;
    const out = document.createElement("p");
    out.className = "px-typed " + [...src.classList].filter((c) => c !== "px-type").join(" ");
    out.setAttribute("aria-hidden", "true");
    src.classList.add("px-sr");
    src.after(out);
    ty = { src, out, text: (src.textContent || "").trim(), t0: 0, done: true };
    typers.set(src, ty);
    return ty;
  }
  function say(ty: Typer, text: string, instant: boolean) {
    ty.text = text;
    ty.t0 = performance.now();
    ty.done = instant || reduced;
    ty.out.textContent = ty.done ? text : "";
  }
  function tickTypers(now: number) {
    typers.forEach((ty) => {
      if (ty.done) return;
      const n = Math.floor(((now - ty.t0) / 1000) * 48);
      if (n >= ty.text.length) { ty.done = true; ty.out.textContent = ty.text; return; }
      ty.out.textContent = ty.text.slice(0, n);
    });
  }
  const finishTyping = () => typers.forEach((ty) => { if (!ty.done) { ty.done = true; ty.out.textContent = ty.text; } });

  // quotes become pages; FAQs a menu and an answer box
  $$(".px-dialog--npc").forEach((d) => typer($(".px-say", d)!));
  $$(".px-dialog--sign .px-type").forEach((p) => typer(p));
  const faqs = $$(".px-ask").map((box) => {
    const items = $$(".px-qa__i", box);
    const list = document.createElement("div");
    list.className = "px-askmenu";
    const ans = document.createElement("div");
    ans.className = "px-answer";
    const ansSrc = document.createElement("p");
    ansSrc.className = "px-body px-answer__t";
    ansSrc.setAttribute("aria-live", "polite");
    ans.appendChild(ansSrc);
    const btns = items.map((it, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "px-menu__i";
      b.innerHTML = $("dt", it)!.innerHTML;
      b.addEventListener("click", () => { pickFaq(f, i, false); });
      list.appendChild(b);
      return b;
    });
    $(".px-qa", box)!.classList.add("px-sr");
    box.append(list, ans);
    const f = { box, items, btns, ansSrc, sel: -1, ty: null as Typer | null, pinned: -1 };
    return f;
  });
  function pickFaq(f: typeof faqs[number], i: number, instant: boolean) {
    if (f.sel === i) return;
    f.sel = i;
    f.btns.forEach((b, j) => { b.classList.toggle("is-sel", j === i); b.setAttribute("aria-pressed", String(j === i)); });
    const a = $("dd", f.items[i])!.textContent || "";
    f.ansSrc.textContent = a;
    if (!f.ty) f.ty = typer(f.ansSrc);
    say(f.ty, a.trim(), instant);
  }

  // ------------------------------------------------ zone windows
  let active = -2, activeSub = -1;
  function setActive(i: number, sub: number, instant: boolean) {
    if (i !== active) {
      zones.forEach((z, j) => z.el.classList.toggle("is-on", j === i));
      active = i;
      activeSub = -99;
      const z = zones[i];
      if (z && z.type !== "hero") {
        banner.textContent = `World 1-${z.idx}`;
        banner.classList.remove("is-on"); void banner.offsetWidth; banner.classList.add("is-on");
        $(".px-hud__world b", hud!)!.textContent = `1-${z.idx}`;
        $$(".px-dialog--sign .px-type", z.el).forEach((p) => { const ty = typer(p); say(ty, ty.text, instant); });
        if (z.type === "stats") { z.el.classList.remove("is-fill"); void z.el.offsetWidth; z.el.classList.add("is-fill"); }
        if (z.type === "cta") { clearT = performance.now() - (instant ? 5000 : 0); }
      } else if (z) $(".px-hud__world b", hud!)!.textContent = "1-0";
    }
    if (sub !== activeSub) {
      activeSub = sub;
      const z = zones[i];
      if (!z) return;
      if (z.type === "features") $$(".px-item", z.el).forEach((it, j) => it.classList.toggle("is-on", j === sub));
      if (z.type === "timeline") {
        const nodes = $$(".px-node", z.el);
        nodes.forEach((it, j) => { it.classList.toggle("is-on", j === sub); it.classList.toggle("is-done", j < sub); });
        let det = $(".px-map__detail", z.el);
        if (!det) { det = document.createElement("div"); det.className = "px-map__detail"; det.setAttribute("aria-hidden", "true"); $(".px-map", z.el)!.appendChild(det); }
        const nd = nodes[clamp(sub, 0, nodes.length - 1)];
        if (nd) det.innerHTML = `<p class="px-node__t">${$(".px-node__t", nd)?.innerHTML || ""}</p><p class="px-body">${$(".px-body", nd)?.innerHTML || ""}</p>`;
      }
      if (z.type === "quote") {
        const pages = pagesOf(z) || [];
        const p = clamp(sub, 0, pages.length - 1);
        const ty = typer($(".px-say", z.el)!);
        say(ty, pages[p] || "", instant);
        z.el.classList.toggle("is-last", p >= pages.length - 1);
      }
      if (z.type === "faq") { const f = faqs.find((x) => z.el.contains(x.box)); if (f) pickFaq(f, clamp(sub, 0, f.items.length - 1), instant); }
    }
  }

  // ------------------------------------------------ course clear: the tally
  const tallies = $$(".px-tally");
  function runTally(now: number) {
    const z = zones[active];
    if (!z || z.type !== "cta" || !clearT) return;
    const dt = now - clearT;
    const el = $(".px-tally", z.el);
    if (!el) return;
    el.hidden = false;
    const items = collected.size, f = clamp((dt - 300) / 900);
    const stepped = Math.floor(f * 12) / 12;
    const rows = [["Items", `${Math.round(items * stepped)} ×1000`], ["Time", `${Math.round(timeLeft * stepped)} ×10`], ["Total", String(Math.round((items * 1000 + timeLeft * 10 + score) * stepped)).padStart(6, "0")]];
    const html = rows.map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join("");
    if (el.innerHTML !== html) el.innerHTML = html;
    z.el.classList.toggle("is-menu", dt > 1300 || reduced);
  }
  void tallies;

  // ------------------------------------------------ jumps: mosaic out, move, mosaic in
  function goTo(y: number, fx = true) {
    const doIt = () => { scrollTo({ top: y, behavior: "instant" as ScrollBehavior }); px = target = xAt(y); finishTyping(); };
    if (!fx || reduced) { doIt(); return; }
    mosaicCb = doIt; mosaicDir = 1; mosaicT = performance.now(); mosaic = 1;
  }
  function tickMosaic(now: number) {
    if (!mosaicDir) return;
    const steps = [1, 2, 4, 8, 16];
    const k = Math.floor((now - mosaicT) / 45);
    if (mosaicDir === 1) {
      mosaic = steps[Math.min(4, k)];
      root.classList.add("px-mosaic");
      if (k >= 4) { mosaicCb?.(); mosaicCb = null; mosaicDir = -1; mosaicT = now; }
    } else {
      mosaic = steps[Math.max(0, 4 - k)];
      if (k >= 4) { mosaicDir = 0; mosaic = 1; root.classList.remove("px-mosaic"); }
    }
  }
  const zoneForEl = (t: Element) => zones.find((z) => z.el === t || z.el.contains(t));
  addEventListener("click", (e) => {
    const a = (e.target as Element).closest?.("a") as HTMLAnchorElement | null;
    if (!a) return;
    const href = a.getAttribute("href") || "";
    if (!href.startsWith("#")) return;
    if (!pauseEl.hidden && pauseEl.contains(a)) closePause();
    if (!game) return;
    if (href === "#") { if (a.closest(".px-hud, .px-pause")) { e.preventDefault(); e.stopPropagation(); goTo(0); } return; }
    const t = document.querySelector(href);
    const z = t && zoneForEl(t);
    if (!z) return;
    e.preventDefault(); e.stopPropagation();
    goTo(stopY(z));
  }, { capture: true });

  // the A button: space / enter advance to the next stop (or dialog page); shift goes back
  function stops() {
    const out: number[] = [0];
    zones.forEach((z) => {
      if (z.type === "hero") return;
      if (z.type === "features" || z.type === "timeline") z.objs.forEach((o) => out.push(z.y0 + (o.x - z.x0 + (z.type === "features" ? 4 : 2)) * K));
      else out.push(stopY(z));
      for (let s = 1; s <= z.steps; s++) out.push(Math.min(z.y1 - 1, z.yT + s * 130 - 60));
    });
    return out.sort((a, b) => a - b);
  }
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !pauseEl.hidden) { closePause(); return; }
    if (!game || e.metaKey || e.ctrlKey || e.altKey) return;
    const tEl = (e.target instanceof Element ? e.target : document.body) as HTMLElement;
    if (tEl.closest("a, button, input, textarea, select, summary")) return;
    if (e.key === " " || e.key === "Enter" || e.key === "PageDown" || e.key === "PageUp") {
      e.preventDefault();
      if (typers.size && [...typers.values()].some((t) => !t.done)) { finishTyping(); return; }
      const back = e.shiftKey || e.key === "PageUp";
      const list = stops(), y = scrollY;
      const next = back ? [...list].reverse().find((s) => s < y - 4) : list.find((s) => s > y + 4);
      if (next != null) scrollTo({ top: next, behavior: "instant" as ScrollBehavior });
    }
  });
  $(".px-start")?.addEventListener("click", () => { if (game) scrollTo({ top: stops()[1] ?? TITLE_SCROLL, behavior: "instant" as ScrollBehavior }); });
  $$(".px-dialog").forEach((d) => d.addEventListener("click", finishTyping));

  // menus: a blinking cursor follows hover / focus
  $$(".px-menu, .px-askmenu, .px-pause__list").forEach((m) => {
    m.addEventListener("pointerover", (e) => { const it = (e.target as Element).closest(".px-menu__i, a, button"); if (it && m.contains(it)) { m.querySelectorAll(".is-sel").forEach((x) => x.classList.remove("is-sel")); it.classList.add("is-sel"); } });
    m.addEventListener("focusin", (e) => { const it = e.target as Element; m.querySelectorAll(".is-sel").forEach((x) => x.classList.remove("is-sel")); it.classList.add("is-sel"); });
    m.addEventListener("keydown", (e) => {
      const k = (e as KeyboardEvent).key;
      if (k !== "ArrowDown" && k !== "ArrowUp") return;
      const items = [...m.querySelectorAll<HTMLElement>("a, button")].filter((x) => !x.hidden);
      const i = items.indexOf(document.activeElement as HTMLElement);
      if (i < 0) return;
      e.preventDefault();
      items[(i + (k === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
    });
  });
  $$(".px-again").forEach((b) => { b.hidden = false; b.addEventListener("click", () => goTo(0)); });

  // pause menu (START)
  function closePause() { pauseEl.hidden = true; startBtn.setAttribute("aria-expanded", "false"); }
  startBtn.addEventListener("click", () => { const open = pauseEl.hidden; pauseEl.hidden = !open; startBtn.setAttribute("aria-expanded", String(open)); if (open) pauseEl.querySelector<HTMLElement>("a, button")?.focus(); });
  $(".px-pause__page", pauseEl)?.addEventListener("click", () => { closePause(); setMode(false); });

  // ------------------------------------------------ switching between the game and the page
  function setMode(on: boolean) {
    const fromEl = active >= 0 ? zones[active]?.el : null;
    game = on;
    try { sessionStorage.setItem("px-mode", on ? "game" : "page"); } catch { /* storage blocked */ }
    root.classList.toggle("px-game", on);
    root.classList.toggle("px-page", !on);
    modeBtn.textContent = on ? "Read as page" : "Play";
    modeBtn.setAttribute("aria-pressed", String(!on));
    if (on) {
      layoutZones();
      const z = fromEl ? zones.find((x) => x.el === fromEl) : null;
      scrollTo({ top: z ? stopY(z) : 0, behavior: "instant" as ScrollBehavior });
      px = target = xAt(scrollY); firstFrame = true;
    } else {
      main!.style.height = "";
      zones.forEach((z) => z.el.classList.remove("is-on"));
      active = -2;
      typers.forEach((ty) => { ty.done = true; });
      if (fromEl) fromEl.scrollIntoView({ behavior: "instant" as ScrollBehavior });
    }
  }
  modeBtn.addEventListener("click", () => setMode(!game));

  // no smooth-scroll momentum in the game: a notch is a step
  addEventListener("wheel", (e) => { if (game) e.stopImmediatePropagation(); }, { capture: true, passive: true });

  // ------------------------------------------------ boot
  size();
  layoutZones();
  root.classList.toggle("px-game", game);
  root.classList.toggle("px-page", !game);
  modeBtn.textContent = game ? "Read as page" : "Play";
  if (game && location.hash.length > 1) {
    const t = document.querySelector(location.hash);
    const z = t && zoneForEl(t);
    if (z) scrollTo({ top: stopY(z), behavior: "instant" as ScrollBehavior });
  }
  addEventListener("resize", () => { size(); if (game) layoutZones(); });

  const itemsEl = $(".px-hud__items b", hud)!, scoreEl = $(".px-hud__score b", hud)!, timeEl = $(".px-hud__time b", hud)!;
  let lastRender = 0;
  onFrame(({ y, t }) => {
    if (!game) return;
    const now = performance.now();
    target = xAt(y);
    if (firstFrame) { px = target; firstFrame = false; }
    // the player walks at a constant speed to where the scroll says (no easing, no momentum); far jumps teleport
    const d = target - px;
    if (Math.abs(d) > 260) px = target;
    else if (Math.abs(d) >= 1) { px += Math.sign(d) * Math.min(Math.abs(d), 2.4); face = Math.sign(d); }
    else px = target;
    walking = Math.abs(target - px) >= 1;
    if (walking && now - lastStepT > 90) { walkF++; lastStepT = now; }
    if (Math.abs(y - lastY) > 30) { finishTyping(); lastY = y; }

    // what the player has reached
    const instant = performance.now() - (start as any).__t0 < 600 || reduced;
    // blocks hit and flags passed anywhere behind the player (a fresh load mid-level has already played them)
    for (const z of zones) {
      if (z.type !== "features" && z.type !== "timeline") continue;
      for (const o of z.objs) {
        if (px < o.x + (z.type === "features" ? 4 : -4)) continue;
        const key = `${z.idx}:${o.i}`;
        if (z.type === "features" && !hitAt.has(key)) { hitAt.set(key, instant ? now - 5000 : now); collected.add(key); score += 1000; }
        if (z.type === "timeline" && !flagsPassed.has(key)) { flagsPassed.add(key); score += 200; }
      }
    }
    let zi = -1, sub = -1;
    zones.forEach((z, i) => {
      if (z.type === "hero") { if (y < TITLE_SCROLL * 0.6) zi = i; return; }
      if (px >= z.trig && px <= z.x1 + 60 && y >= z.y0 - 1) zi = i;
    });
    if (zi >= 0) {
      const z = zones[zi];
      if (z.type === "features" || z.type === "timeline") {
        z.objs.forEach((o, j) => { if (px >= o.x + (z.type === "features" ? 4 : -4)) sub = j; });
        if (sub < 0 && z.type === "timeline") sub = 0;
      } else if (z.steps) sub = Math.floor(clamp((y - z.yT) / 130, 0, z.steps - 0.001));
      if (z.type === "cta" && !poleT && px >= z.objs[0].x - 2) poleT = instant ? now - 9000 : now;
    }
    setActive(zi, sub, instant);
    tickTypers(now);
    runTally(now);
    tickMosaic(now);

    // HUD
    itemsEl.innerHTML = `<i class="px-star"></i>×${collected.size}`;
    const visited = zones.filter((z) => px >= z.trig && z.type !== "hero").length;
    const target_ = score + visited * 100;
    if (shownScore < target_) shownScore = Math.min(target_, shownScore + 50);
    const sc = String(Math.max(0, shownScore)).padStart(6, "0");
    if (scoreEl.textContent !== sc) scoreEl.textContent = sc;
    if (!reduced && !clearT && now - timeT > 600 && timeLeft > 0) { timeT = now; timeLeft--; timeEl.textContent = String(timeLeft); }

    // the level at up to 30 frames a second (sprites step at 10)
    if (now - lastRender > 32 || mosaicDir) { lastRender = now; render(t, now); }
  });
  (start as any).__t0 = performance.now();
}
