/**
 * Zoetrope: the landing page as one wheel of cards on a giant strobe zoetrope, a prize wheel you spin and land.
 *
 * Every landing-page element is a printed card on one turntable: the hero, each feature, the product, each stat, each
 * step, the quote, each question, the call to action, and any scene or other block. Each card shows a short title and
 * its own figure, a 12-frame loop no other card on the wheel shares. Spin the wheel (scroll wheel, swipe or fling,
 * drag, the spin button, arrow keys): while it turns fast the strobe catches every figure mid-loop so the whole ring
 * comes alive and seems to turn slowly; it slows with real inertia, ticks past the brass pointer, and lands square on
 * one card with a little bounce, the lamp marking the winner. Click or tap a card (or press Enter): it flies out of the
 * ring, flips and becomes the full card, the element's real HTML, over a dimmed table; close it and it flies back.
 *
 * Reduced motion and no WebGL: the page is the plain list of cards, each with its figure drawn still.
 */
import { $, $$, onFrame, reduced, skin, skinNum, skinRgba } from "./_kit";
import { artConfig, loadArt, type ArtFrames } from "./_art";
import { drawFigure, FIGURES, type FigData, type Figure } from "./_zoetrope-figures";
import { drawBack, stripFonts, type Device } from "./_zoetrope-strips";

// the printed cards and the wheel: ink, red and blue are the style's ink and accents (a brand's when it wears one), paper and brass its own
const INK = skin("ink", "#1d1611"), RED = skin("accent", "#c8371e");

const TAU = Math.PI * 2;
const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = (t: number) => 1 - Math.pow(1 - clamp(t), 3);
const easeIO = (t: number) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const phone = () => innerWidth <= 760;
const plain = (el: Element | null) => (el?.textContent || "").replace(/\s+/g, " ").trim();
const POSES = 12;

interface Card {
  i: number;
  el: HTMLElement;           // the article (or the scene / block section) that opens as the full card
  kind: string;
  title: string;
  label: string;
  section: HTMLElement;
  fig: Figure;
  data: FigData;
  home: Comment | null;
  base?: import("three").CanvasTexture;
  atlas?: { tex: import("three").CanvasTexture; canvas: HTMLCanvasElement; done: boolean[] };
  group?: import("three").Group;
  figMesh?: import("three").Mesh;
  pose: number;
}

// ---------------------------------------------------------------- figure choice: every card its own
const HINTS: [RegExp, Figure][] = [
  [/\b(minute|minutes|hour|hours|time|second|morning|clock|o'clock|a\.m\.|p\.m\.)\b/i, "clock"],
  [/\b(day|week|month|calendar|date|schedule|year)\b/i, "calendar"],
  [/\b(secure|private|privacy|lock|key|access|password|sign in|connect)\b/i, "key"],
  [/\b(replace|instead|compare|price|pricing|cost|cheaper|versus|vs|fair)\b/i, "scales"],
  [/\b(see|look|find|search|who|show|view|watch)\b/i, "magnifier"],
  [/\b(idea|learn|smart|why|think|clever)\b/i, "bulb"],
  [/\b(open|start|begin|enter|welcome|join|door)\b/i, "door"],
  [/\b(how|works|engine|automat\w*|override|control|setting|settings|build|builds)\b/i, "gears"],
  [/\b(mail|message|invite|invites|email|send|reply|letter)\b/i, "envelope"],
  [/\b(love|health|care|feel|wellbeing|heart|clinician|doctor)\b/i, "heart"],
  [/\b(wait|later|soon|long|duration|focus|patience)\b/i, "hourglass"],
  [/\b(night|sleep|evening|dark|tonight|bed|rest)\b/i, "moon"],
  [/\b(launch|grow|growth|scale|speed|rocket|new)\b/i, "rocket"],
  [/\b(travel|fly|flight|trip|airport|jet|jets|airfield|airfields|plane)\b/i, "plane"],
  [/\b(sea|ocean|water|calm|flow|wave)\b/i, "waves"],
  [/\b(random|chance|luck|any|anything)\b/i, "dice"],
  [/\b(notify|alert|remind|reminder|call|calls|ring)\b/i, "bell"],
  [/\b(energy|power|wind|green)\b/i, "windmill"],
  [/\b(write|sign|note|draw|paint|mark|diary)\b/i, "pen"],
  [/\b(batch|batching|balance|many|juggle|multi)\b/i, "juggler"],
  [/\b(rhythm|habit|habits|routine|steady|pace)\b/i, "metronome"],
  [/\b(flip|change|switch|turn|shift)\b/i, "tumbler"],
  [/\b(coffee|tea|cup|breakfast)\b/i, "teacup"],
  [/\b(plant|grow|garden|natural)\b/i, "sprout"],
  [/\b(wearable|tracker|spin|top)\b/i, "top"],
];
const POOLS: Record<string, Figure[]> = {
  hero: ["art", "pan", "teacup", "rocket", "ball"],
  intro: ["bird", "sunrise", "kite", "butterfly"],
  feature: ["coin", "gears", "juggler", "spring", "top", "windmill", "bell", "plane", "metronome", "kite"],
  product: ["turn", "picture", "rocket", "gears"],
  stat: ["counter", "clock", "hourglass", "dice", "pie", "metronome"],
  step: ["calendar", "walker", "clock", "key", "sunrise", "door", "sprout", "hourglass", "pen"],
  quote: ["quote", "pen", "envelope"],
  faq: ["bulb", "magnifier", "door", "key", "scales", "spring", "envelope", "question", "gears", "dice", "bell"],
  cta: ["sun", "rocket", "door"],
  film: ["film", "windmill"], gallery: ["tunnel", "pan"], strip: ["tunnel", "pan"], orbit: ["orbit", "gears"],
};
function chooseFigure(c: Card, used: Set<Figure>, hasArt: boolean): Figure {
  const ok = (f: Figure) => {
    if (used.has(f)) return false;
    if (f === "art") return hasArt && c.kind === "hero";
    if (f === "pan" || f === "picture") return !!c.data.img;
    if (f === "turn") return !!c.data.device;
    if (f === "film") return c.kind === "film";
    if (f === "tunnel") return !!(c.data.imgs && c.data.imgs.length);
    if (f === "pie") return /%/.test(c.data.unit || "") || /%/.test(c.data.value || "");
    if (f === "quote") return c.kind === "quote";
    if (f === "walker") return c.kind === "step" || c.kind === "intro";
    return true;
  };
  const txt = `${c.title} ${c.kind === "stat" ? `${c.data.unit} ${c.data.label}` : plain(c.el)}`;
  const pool = POOLS[c.kind] || [];
  const first = pool[0];
  // the kind's signature figure first where it applies (art for the hero, the phone for the product...)
  if (first && ["art", "turn", "quote", "sun", "film", "tunnel", "orbit", "pie"].includes(first) && ok(first)) return first;
  if (c.kind === "stat" && ok("pie")) return "pie";
  if (c.kind === "stat" && /^(h|hr|hrs|hours?|min|mins|minutes?|s|sec|seconds?)$/i.test(c.data.unit || "") && ok("clock")) return "clock";
  // a hint that fits the kind, then the kind's own figures, then any hint, then anything left
  for (const [re, f] of HINTS) if (re.test(txt) && ok(f) && pool.includes(f)) return f;
  for (const f of pool) if (ok(f)) return f;
  for (const [re, f] of HINTS) if (re.test(txt) && ok(f) && c.kind !== "stat") return f;
  for (const f of FIGURES) if (ok(f)) return f;
  return pool[0] || "ball";
}

let lastInput = 0;

/** Spec text with its few allowed tags (em, b, i, br) as nodes; anything else becomes plain text. */
function rich(html: string): DocumentFragment {
  const t = document.createElement("template"); t.innerHTML = html;
  const out = document.createDocumentFragment();
  const walk = (n: Node, into: Node) => {
    n.childNodes.forEach((ch) => {
      if (ch.nodeType === 3) into.appendChild(document.createTextNode(ch.textContent || ""));
      else if (ch.nodeType === 1 && ["EM", "B", "I", "BR"].includes((ch as Element).tagName)) { const e = document.createElement((ch as Element).tagName.toLowerCase()); into.appendChild(e); walk(ch, e); }
      else walk(ch, into);
    });
  };
  walk(t.content, out);
  return out;
}

export default function start() {
  const main = $("main");
  if (!main) return;
  const root = document.documentElement;
  const maker = plain($(".zt-lid__name")) || document.title;

  // ---------------------------------------------------------------- the cards, in reading order
  const cards: Card[] = [];
  const tops = [...main.children] as HTMLElement[];
  for (const t of tops) {
    const sec = (t.tagName === "SECTION" ? t : t.querySelector("section")) as HTMLElement | null;
    if (!sec) continue;
    const arts = $$<HTMLElement>(":scope > .zt-el", sec);
    if (arts.length) {
      for (const a of arts) {
        const kind = a.dataset.ztKind || "card";
        const data: FigData = { number: cards.length + 1, maker, label: a.dataset.ztTitle, tag: a.dataset.ztTag, value: a.dataset.ztValue, unit: a.dataset.ztUnit };
        if (kind === "stat") data.label = plain(a.querySelector(".zt-h"));
        const dev = a.querySelector(".zt-devdata");
        if (dev) { try { data.device = JSON.parse(dev.textContent || "null") as Device; } catch { data.device = null; } }
        data.img = a.querySelector<HTMLImageElement>("[data-zt-img]");
        cards.push({ i: cards.length, el: a, kind, title: a.dataset.ztTitle || plain(a.querySelector(".zt-h")), label: a.dataset.ztLabel || kind, section: sec, fig: "ball", data, home: null, pose: 0 });
      }
      continue;
    }
    // a scene or a block this style has no template for: the whole section is the card
    const scene = sec.dataset.scene;
    const kind = scene || ([...sec.classList].find((k) => k.startsWith("ss-") && !["ss-block", "ss-band", "ss-scene"].includes(k) && !k.startsWith("ss-surface") && !k.startsWith("ss-side") && !k.startsWith("ss-shade") && !k.startsWith("ss-type"))?.slice(3) || "block");
    const head = sec.querySelector("h1, h2, h3, .ss-step h2, .ss-step h3");
    const data: FigData = { number: cards.length + 1, maker, label: plain(head) };
    if (scene === "film") {
      try { const cfg = JSON.parse(sec.querySelector(".ss-config")?.textContent || "{}"); data.label = plain(head) || cfg.title || ""; (data as any).video = cfg.video ? new URL(cfg.video, location.href).href : ""; } catch { /* no film */ }
    }
    data.imgs = $$<HTMLImageElement>("img", sec).filter((im) => !im.classList.contains("ss-poster"));
    const k2 = kind === "film" ? "film" : kind;
    // a scene opens as its own card: its steps as text and its footage playing (the scene itself stays in the page)
    let el: HTMLElement = sec, title = plain(head);
    if (scene) {
      el = document.createElement("article");
      el.className = `zt-el zt-el--scene`;
      let sdata: any = {}, cfg: any = {};
      try { sdata = JSON.parse(sec.querySelector(".ss-section")?.textContent || "{}"); cfg = JSON.parse(sec.querySelector(".ss-config")?.textContent || "{}"); } catch { /* text only */ }
      const body = document.createElement("div"); body.className = "zt-body";
      if (cfg.video) { const v = document.createElement("video"); v.src = new URL(cfg.video, location.href).href; v.muted = true; v.loop = true; v.playsInline = true; v.controls = true; v.preload = "none"; if (cfg.poster) v.poster = new URL(cfg.poster, location.href).href; v.className = "zt-film"; body.appendChild(v); }
      for (const st of sdata.steps || []) {
        if (st.kicker) { const k = document.createElement("span"); k.className = "zt-kicker"; k.textContent = st.kicker; body.appendChild(k); }
        if (st.title) { const h = document.createElement("h3"); h.className = "zt-h"; h.append(rich(st.title)); body.appendChild(h); }
        if (st.body) { const pp = document.createElement("p"); pp.className = "zt-lede"; pp.append(rich(st.body)); body.appendChild(pp); }
      }
      el.appendChild(body);
      title = title || plain(body.querySelector("h3")) || sec.id;
    }
    cards.push({ i: cards.length, el, kind: k2, title: title || sec.id || kind, label: kind === "film" ? "Film" : kind.charAt(0).toUpperCase() + kind.slice(1), section: sec, fig: "ball", data, home: null, pose: 0 });
  }
  if (!cards.length) return;
  const N = cards.length;
  const hasArt = !!artConfig();
  const used = new Set<Figure>();
  for (const c of cards) { c.fig = chooseFigure(c, used, hasArt); used.add(c.fig); }
  const artReady: Promise<ArtFrames | null> = hasArt ? loadArt() : Promise.resolve(null);
  artReady.then((a) => { for (const c of cards) if (c.fig === "art") { c.data.art = a; redraw(c); } });
  for (const c of cards) {
    const ims = [c.data.img, ...(c.data.imgs || [])].filter(Boolean) as HTMLImageElement[];
    for (const im of ims) {
      if (im.loading === "lazy") im.loading = "eager";   // the list is out of sight: its pictures would never load lazily
      if (!im.complete) im.addEventListener("load", () => redraw(c), { once: true });
    }
  }

  if (reduced) { stills(cards); return; }
  let gl: WebGLRenderingContext | null = null;
  try { gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl"); } catch { gl = null; }
  if (!gl) { stills(cards); return; }

  root.classList.add("zt-on");
  const stage = $("#zt-stage")!;
  const wheelEl = $(".zt-wheel")!, live = $(".zt-live")!;
  const pointer = $(".zt-pointer")!, winner = $(".zt-winner")!, strobeEl = $(".zt-strobe")!, hint = $(".zt-hint")!;
  for (const e of [wheelEl, pointer, strobeEl, hint]) e.removeAttribute("hidden");
  const stateEl = $(".zt-strobe__state b"), fpsEl = $(".zt-strobe__fps");
  const dlg = $(".zt-open")!, dlgCard = $(".zt-open__card")!, dlgSlot = $(".zt-open__slot")!, dlgFig = $(".zt-open__fig")!;
  dlgCard.setAttribute("data-lenis-prevent", "");
  // card films: sample twelve frames of the film for its figure
  for (const c of cards) if (c.fig === "film" && (c.data as any).video) sampleFilm(c);

  // ---------------------------------------------------------------- three.js
  let THREE: typeof import("three") | null = null;
  let renderer: import("three").WebGLRenderer, scene: import("three").Scene, camera: import("three").PerspectiveCamera;
  let table: import("three").Group;
  let backTex: import("three").CanvasTexture | null = null;
  let ready = false;
  let R = 3, CW = 0.7, CH = 1, LEAN = 0.24, TOP = 0.07, PLINTH = 0.08;
  const FACE = { W: 600, H: 860, fig: { x: 40, y: 92, w: 520, h: 470 }, title: { x: 46, y: 586, w: 508, h: 186 } };

  function canvasTex(c: HTMLCanvasElement) {
    const t = new THREE!.CanvasTexture(c);
    t.colorSpace = THREE!.SRGBColorSpace;
    t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    return t;
  }

  /** The card's printed face: number, label, the figure in pose 0, the title. */
  function drawFace(c: Card) {
    const s = phone() ? 0.75 : 1;
    const cv = document.createElement("canvas"); cv.width = Math.round(FACE.W * s); cv.height = Math.round(FACE.H * s);
    const x = cv.getContext("2d")!; x.scale(s, s);
    const { W, H } = FACE;
    x.fillStyle = "#f8f1df"; x.fillRect(0, 0, W, H);
    x.strokeStyle = INK; x.lineWidth = 4; x.strokeRect(16, 16, W - 32, H - 32); x.lineWidth = 1.5; x.strokeRect(25, 25, W - 50, H - 50);
    x.fillStyle = RED; for (const [a, b] of [[16, 16], [W - 16, 16], [16, H - 16], [W - 16, H - 16]]) { x.beginPath(); x.arc(a, b, 9, 0, TAU); x.fill(); }
    x.fillStyle = INK; x.font = `26px "Alfa Slab One", Georgia, serif`; x.textBaseline = "middle"; x.fillText(`No. ${c.i + 1}`, 44, 60);
    x.textAlign = "right"; x.fillStyle = skin("accent_text", "#a12a14"); x.font = `16px "Alfa Slab One", Georgia, serif`;
    let lab = c.label.toUpperCase(); while (x.measureText(lab).width > 360 && lab.length > 4) lab = lab.slice(0, -2);
    if (lab !== c.label.toUpperCase()) lab = lab.trim() + "…";
    x.fillText(lab, W - 44, 61); x.textAlign = "left";
    const f = FACE.fig;
    drawFigure(x, c.fig, 0, f.x, f.y, f.w, f.h, c.data);
    x.strokeStyle = INK; x.lineWidth = 4; x.strokeRect(f.x, f.y, f.w, f.h);
    // the title, fitted to three lines
    const t = FACE.title;
    let size = 54, lines: string[] = [];
    for (; size >= 26; size -= 2) {
      x.font = `700 ${size}px "Bodoni Moda", Georgia, serif`;
      lines = wrap(x, c.title, t.w);
      if (lines.length <= 3 && lines.length * size * 1.08 <= t.h) break;
    }
    if (lines.length > 3) { lines = lines.slice(0, 3); lines[2] = lines[2].replace(/\s*\S*$/, "…"); }
    x.fillStyle = INK; x.textAlign = "center"; x.textBaseline = "alphabetic";
    const lh = size * 1.06, y0 = t.y + (t.h - lines.length * lh) / 2 + size * 0.8;
    lines.forEach((ln, k) => x.fillText(ln, W / 2, y0 + k * lh));
    x.font = `14px "Alfa Slab One", Georgia, serif`; x.fillStyle = skinRgba("ink", "#1d1611", 0.55);
    x.fillText(`${maker.toUpperCase()}  ·  OPEN THE CARD`, W / 2, H - 46);
    x.textAlign = "left";
    return cv;
  }
  function wrap(x: CanvasRenderingContext2D, s: string, w: number) {
    const out: string[] = []; let line = "";
    for (const word of s.split(/\s+/)) { const tst = line ? `${line} ${word}` : word; if (x.measureText(tst).width > w && line) { out.push(line); line = word; } else line = tst; }
    if (line) out.push(line);
    return out;
  }
  function redraw(c: Card) {
    if (!ready) return;
    c.base?.dispose(); c.base = undefined;
    if (c.atlas) { c.atlas.tex.dispose(); c.atlas = undefined; }
  }

  async function initGL() {
    THREE = await import("three");
    await stripFonts();
    try { await document.fonts.ready; } catch { /* fallbacks */ }
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, phone() ? 1.25 : 1.5));
    renderer.setClearColor(0x000000, 0);
    stage.appendChild(renderer.domElement);
    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(skinNum("bg", 0xf3ead6), 10, 34);
    camera = new THREE.PerspectiveCamera(30, innerWidth / innerHeight, 0.05, 120);
    scene.add(new THREE.HemisphereLight(0xfff8ec, 0xb9a98c, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.5); key.position.set(-4, 9, 7); scene.add(key);
    const bc = document.createElement("canvas"); bc.width = 300; bc.height = 430; drawBack(bc.getContext("2d")!, 300, 430, maker);
    backTex = canvasTex(bc);
    ready = true;
    build();
    // the wheel arrives spinning and lands on the first card (or the one the address names)
    const home = hashIdx > 0 ? hashIdx : 0;
    wh.th = theta = home - Math.min(N - 1, 4); wh.w = 0;
    spinTo(home, 0, 1);
  }

  function discTex() {
    const S = 1024, cv = document.createElement("canvas"); cv.width = cv.height = S;
    const x = cv.getContext("2d")!, m = S / 2;
    const bands = [RED, "#f8f1df", skin("accent2", "#1f4f8a"), "#f8f1df", "#e2b54a"];
    for (let i = 0; i < 5; i++) { x.fillStyle = bands[i]; x.beginPath(); x.arc(m, m, m * (1 - i * 0.035), 0, TAU); x.fill(); }
    const seg = Math.max(24, N * 2);
    for (let i = 0; i < seg; i++) { x.fillStyle = i % 2 ? "#f3e6c8" : "#ead8af"; x.beginPath(); x.moveTo(m, m); x.arc(m, m, m * 0.83, (i / seg) * TAU, ((i + 1) / seg) * TAU); x.fill(); }
    x.strokeStyle = INK; x.lineWidth = 3; for (const rr of [0.83, 0.5, 0.26]) { x.beginPath(); x.arc(m, m, m * rr, 0, TAU); x.stroke(); }
    x.fillStyle = INK; x.font = `${Math.round(S * 0.05)}px "Alfa Slab One", Georgia, serif`; x.textAlign = "center"; x.textBaseline = "middle";
    x.fillText(maker.toUpperCase().slice(0, 14), m, m - S * 0.025);
    x.font = `italic ${Math.round(S * 0.03)}px "Bodoni Moda", Georgia, serif`; x.fillText("The Wheel of Life", m, m + S * 0.04);
    return cv;
  }

  /** The turntable sized for the deck, a plinth and a card for every element, and the brass pegs between them. */
  function build() {
    if (table) { scene.remove(table); table.traverse((o: any) => o.geometry?.dispose?.()); }
    CW = 0.7; CH = 1;
    R = Math.max(1.05, (CW * 1.2) / (2 * Math.sin(Math.PI / N)));
    LEAN = phone() ? 0.3 : 0.24;
    table = new THREE!.Group(); scene.add(table);
    const rad = R + CW * 0.42;
    const disc = new THREE!.Mesh(new THREE!.CylinderGeometry(rad, rad + 0.04, TOP, 160),
      [new THREE!.MeshStandardMaterial({ color: 0xb8892e, roughness: 0.35, metalness: 0.6 }), new THREE!.MeshStandardMaterial({ map: canvasTex(discTex()), roughness: 0.7 }), new THREE!.MeshStandardMaterial({ color: 0x5a3a1c })]);
    disc.position.y = TOP / 2; table.add(disc);
    const rim = new THREE!.Mesh(new THREE!.TorusGeometry(rad, 0.03, 10, 200), new THREE!.MeshStandardMaterial({ color: 0xd9a63c, roughness: 0.3, metalness: 0.75 }));
    rim.rotation.x = Math.PI / 2; rim.position.y = TOP; table.add(rim);
    const stand = new THREE!.Mesh(new THREE!.CylinderGeometry(0.3 + R * 0.06, 0.5 + R * 0.1, 2.4, 48), new THREE!.MeshStandardMaterial({ color: 0x3b2614, roughness: 0.5, metalness: 0.2 }));
    stand.position.y = -1.2; table.add(stand);
    const plinthGeo = new THREE!.BoxGeometry(CW * 0.48, PLINTH, 0.16), plinthMat = new THREE!.MeshStandardMaterial({ color: 0x7a4a22, roughness: 0.55 });
    const pegGeo = new THREE!.CylinderGeometry(0.022, 0.022, 0.14, 12), pegMat = new THREE!.MeshStandardMaterial({ color: 0xd9a63c, roughness: 0.3, metalness: 0.8 });
    const cardGeo = new THREE!.BoxGeometry(CW, CH, 0.012);
    const figGeo = new THREE!.PlaneGeometry(CW * (FACE.fig.w / FACE.W), CH * (FACE.fig.h / FACE.H));
    const edge = new THREE!.MeshBasicMaterial({ color: 0xe9dcbb });
    const backMat = new THREE!.MeshBasicMaterial({ map: backTex });
    for (const c of cards) {
      const a = c.i * (TAU / N);
      const p = new THREE!.Mesh(plinthGeo, plinthMat); p.position.set(Math.sin(a) * R, TOP + PLINTH / 2, Math.cos(a) * R); p.rotation.y = a; table.add(p);
      const pa = a + Math.PI / N, peg = new THREE!.Mesh(pegGeo, pegMat); peg.position.set(Math.sin(pa) * (rad - 0.06), TOP + 0.07, Math.cos(pa) * (rad - 0.06)); table.add(peg);
      const g = new THREE!.Group();
      const front = new THREE!.MeshBasicMaterial({ color: 0xf8f1df });
      const box = new THREE!.Mesh(cardGeo, [edge, edge, edge, edge, front, backMat]); g.add(box);
      const fm = new THREE!.Mesh(figGeo, new THREE!.MeshBasicMaterial({ transparent: false }));
      const fx = (FACE.fig.x + FACE.fig.w / 2) / FACE.W - 0.5, fy = 0.5 - (FACE.fig.y + FACE.fig.h / 2) / FACE.H;
      fm.position.set(fx * CW, fy * CH, 0.0075); fm.visible = false; g.add(fm);
      g.userData.slot = a;
      placeInSlot(g, a);
      table.add(g);
      c.group = g; c.figMesh = fm;
      c.base?.dispose(); c.base = undefined;
      if (c.atlas) { c.atlas.tex.dispose(); c.atlas = undefined; }
    }
    resize();
  }
  function placeInSlot(g: import("three").Group, a: number) {
    g.position.set(Math.sin(a) * (R - 0.02), TOP + PLINTH + CH / 2, Math.cos(a) * (R - 0.02));
    g.rotation.set(-LEAN, a, 0, "YXZ");
    g.scale.set(1, 1, 1);
  }

  // textures, a little each frame: faces for every card (front first), pose atlases for the cards near the front
  const AT = { cols: 4, rows: 3 };
  function feed(front: number) {
    let budget = 2;
    for (let d = 0; d <= N / 2 && budget > 0; d++) {
      for (const k of d === 0 ? [front] : [front + d, front - d]) {
        const c = cards[((k % N) + N) % N];
        if (!c.base && budget > 0) {
          c.base = canvasTex(drawFace(c));
          const mats = (c.group!.children[0] as import("three").Mesh).material as import("three").MeshBasicMaterial[];
          mats[4].map = c.base; mats[4].color.set(0xffffff); mats[4].needsUpdate = true;
          budget--; dirty = true;
        }
      }
    }
    // pose atlases within reach of the front
    const reach = phone() ? 2 : 3;
    let poses = 4;
    for (let d = 0; d <= reach && poses > 0; d++) {
      for (const k of d === 0 ? [front] : [front + d, front - d]) {
        const c = cards[((k % N) + N) % N];
        if (!c.atlas) {
          const sz = phone() ? 150 : 210, cv = document.createElement("canvas");
          cv.width = sz * AT.cols; cv.height = Math.round(sz * (FACE.fig.h / FACE.fig.w)) * AT.rows;
          c.atlas = { tex: canvasTex(cv), canvas: cv, done: new Array(POSES).fill(false) };
          const m = c.figMesh!.material as import("three").MeshBasicMaterial;
          m.map = c.atlas.tex; c.atlas.tex.repeat.set(1 / AT.cols, 1 / AT.rows); m.needsUpdate = true;
        }
        const at = c.atlas;
        for (let q = 0; q < POSES && poses > 0; q++) {
          if (at.done[q]) continue;
          const cw = at.canvas.width / AT.cols, ch = at.canvas.height / AT.rows;
          const x = at.canvas.getContext("2d")!;
          const col = q % AT.cols, row = Math.floor(q / AT.cols);
          x.save(); x.translate(col * cw, row * ch); x.scale(cw / FACE.fig.w, ch / FACE.fig.h);
          drawFigure(x, c.fig, q / POSES, 0, 0, FACE.fig.w, FACE.fig.h, c.data);
          x.restore();
          at.done[q] = true; at.tex.needsUpdate = true; poses--; dirty = true;
        }
      }
    }
    // drop atlases far from the front
    for (const c of cards) {
      if (!c.atlas) continue;
      const dist = Math.min(((c.i - front) % N + N) % N, ((front - c.i) % N + N) % N);
      if (dist > reach + 2) { c.atlas.tex.dispose(); c.atlas = undefined; c.figMesh!.visible = false; ((c.figMesh!.material) as any).map = null; }
    }
  }
  function showPose(c: Card, q: number) {
    const at = c.atlas;
    if (!at || !at.done[q]) { const v = !!(at && at.done[c.pose]); if (c.figMesh && c.figMesh.visible !== v) { c.figMesh.visible = v; dirty = true; } return; }
    if (c.pose === q && c.figMesh!.visible) return;
    c.pose = q; dirty = true;
    const col = q % AT.cols, row = Math.floor(q / AT.cols);
    at.tex.offset.set(col / AT.cols, 1 - (row + 1) / AT.rows);
    c.figMesh!.visible = true;
  }

  function resize() {
    if (!ready) return;
    renderer.setSize(innerWidth, innerHeight, false);
    camera.aspect = innerWidth / innerHeight;
    dirty = true;
  }

  // ---------------------------------------------------------------- the wheel: inertia, the strobe, the landing
  // A prize wheel, integrated in real time with fixed sub-steps (a slow frame takes several steps, never slows time).
  // free: coasting under mostly constant (Coulomb) friction plus a little drag. land: once it is slow, it picks the card
  // it will stop on and decelerates onto it at a believable constant rate. bounce: the clapper catches the peg, a small
  // spring around the card. rest: landed.
  type Mode = "free" | "land" | "bounce" | "rest";
  interface Wheel { th: number; w: number; mode: Mode; target: number; a: number; bv: number; plan: number | null; brake: boolean; quiet: number; firm: boolean }
  const MU = 2.9, MU_FIRM = 3.5, DRAG = 0.42, WMAX = 12, V_LAND = 1.6, STEP = 1 / 240;
  const wh: Wheel = { th: 0, w: 0, mode: "rest", target: 0, a: 0, bv: 0, plan: null, brake: false, quiet: 1, firm: false };
  let theta = 0;              // what is drawn: wheel position in cards (front card = round(theta) mod N)
  let omega = 0;              // its speed, cards a second
  let phase = 0;              // figure pose clock under the strobe
  let landedAt = -1, landedPulse = 0;
  let dragging = false, dragLast = 0, dragT = 0, dragV = 0, dragMoved = 0, dragStart = 0, spinningAtDown = false;
  let dirty = true, alive = false, aliveHold = 0;
  const frontOf = (t: number) => ((Math.round(t) % N) + N) % N;
  function beginLand(s: Wheel) {
    const sp = Math.abs(s.w), dir = Math.sign(s.w) || 1;
    if (sp < 0.05) { s.target = s.plan !== null ? s.plan : Math.round(s.th); s.bv = 0; s.mode = "bounce"; return; }
    let tgt = s.plan !== null ? s.plan : Math.round(s.th + (dir * sp * sp) / (2 * MU));
    if ((tgt - s.th) * dir < 0.12) tgt += dir;          // never back up onto a card, never stop dead on one
    let dist = (tgt - s.th) * dir, a = (sp * sp) / (2 * dist);
    if (s.plan === null) {                                 // keep the deceleration believable: not a slam, not a creep
      while (a > MU * 2.4) { tgt += dir; dist += 1; a = (sp * sp) / (2 * dist); }
      while (a < MU * 0.8 && dist > 1.1) { tgt -= dir; dist -= 1; a = (sp * sp) / (2 * dist); }
    }
    s.target = tgt; s.a = a; s.mode = "land";
  }
  function step(s: Wheel, h: number) {
    if (s.mode === "free") {
      const sp = Math.abs(s.w);
      // (a button spin is launched harder against firmer friction, so a whole turn or more still lands in 3 to 4 s)
      const dec = ((s.brake ? MU * 5 : s.firm ? MU_FIRM : MU) + DRAG * sp) * h;
      s.th += s.w * h;
      s.w = sp <= dec ? 0 : s.w - Math.sign(s.w) * dec;
      s.quiet += h;
      if (Math.abs(s.w) <= V_LAND && s.quiet > 0.12) beginLand(s);
    } else if (s.mode === "land") {
      const dir = Math.sign(s.target - s.th) || Math.sign(s.w) || 1;
      if (s.w * dir <= 0) s.w = dir * 0.05;
      s.w -= dir * s.a * h;
      s.th += s.w * h;
      if ((s.target - s.th) * dir <= 0 || s.w * dir <= 0.02) { s.bv = Math.max(0, s.w * dir) * dir * 0.45 + dir * 0.18; s.mode = "bounce"; }
    } else if (s.mode === "bounce") {
      const k = 300, d = 22;
      s.bv += (-(s.th - s.target) * k - s.bv * d) * h; s.th += s.bv * h; s.w = s.bv;
      if (Math.abs(s.th - s.target) < 0.0008 && Math.abs(s.bv) < 0.02) { s.th = s.target; s.w = 0; s.bv = 0; s.mode = "rest"; s.plan = null; s.brake = false; s.firm = false; }
    } else s.w = 0;
  }
  /** Where a firm spin launched at speed w0 from th0 would coast to a stop under its friction alone (monotonic in w0,
   *  so a bisection on it is exact); the landing then puts it on the card nearest that point. */
  function stopsAt(th0: number, w0: number) {
    let th = th0, w = Math.abs(w0);
    const h = 1 / 240;
    for (let k = 0; k < 240 * 30 && w > 0; k++) { th += w * h; w = Math.max(0, w - (MU_FIRM + DRAG * w) * h); }
    return th0 + (th - th0) * Math.sign(w0 || 1);
  }
  /** A spin that lands on card `to` after at least `turns` whole turns, its launch speed found by bisection. */
  function spinTo(to: number, minTurns: number, dir = 1) {
    const cur = wh.th;
    let goal = to + Math.round((cur - to) / N) * N;
    while (dir > 0 ? goal < cur + minTurns * N + 0.5 : goal > cur - minTurns * N - 0.5) goal += dir * N;
    if (Math.abs(goal - cur) < 0.6) { wh.plan = goal; wh.w = 0; wh.target = goal; wh.bv = 0; wh.mode = "bounce"; return; }
    let lo = 0.3, hi = 80;
    for (let k = 0; k < 32; k++) { const mid = (lo + hi) / 2, e = stopsAt(cur, dir * mid); if (dir > 0 ? e < goal : e > goal) lo = mid; else hi = mid; }
    wh.w = dir * (lo + hi) / 2; wh.mode = "free"; wh.plan = goal; wh.brake = false; wh.quiet = 1; wh.firm = true; landedAt = -1; dirty = true;
  }
  /** One card on (arrow keys): a short, firm move that settles with the same little bounce. */
  function stepTo(delta: number) {
    const base = wh.mode === "land" || wh.mode === "bounce" ? wh.target : Math.round(wh.th);
    const tgt = base + delta, dir = Math.sign(tgt - wh.th) || delta, dist = Math.abs(tgt - wh.th);
    const a = MU * 2.2;
    wh.plan = tgt; wh.target = tgt; wh.a = a; wh.w = dir * Math.sqrt(2 * a * Math.max(dist, 0.05)); wh.mode = "land"; wh.brake = false; landedAt = -1;
  }
  const userTouched = () => { lastInput = performance.now(); root.classList.add("zt-moved"); };
  /** A push from the scroll wheel: builds speed but saturates near WMAX; the other way brakes (and can reverse). */
  function push(dv: number) {
    if (wh.mode !== "free") { wh.mode = "free"; }
    wh.plan = null; wh.brake = false; wh.quiet = 0; wh.firm = false;
    const sp = Math.abs(wh.w);
    if (sp > 0.05 && Math.sign(dv) !== Math.sign(wh.w)) wh.w += dv * 1.7;
    else { const room = Math.max(0, 1 - sp / WMAX); wh.w = Math.sign(dv) * Math.min(WMAX, sp + Math.abs(dv) * Math.pow(room, 1.1)); }
    landedAt = -1; dirty = true;
  }

  // the scroll wheel spins it
  addEventListener("wheel", (e) => {
    if (openCard || (e.target as Element)?.closest?.(".zt-open")) return;
    e.preventDefault();
    const dy = (e.deltaMode === 1 ? 33 : e.deltaMode === 2 ? 400 : 1) * (Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX);
    // a notch (about 100) is a push of 3 cards a second; small trackpad deltas push in proportion
    push((clamp(dy, -160, 160) / 100) * 3.0);
    userTouched();
  }, { passive: false });

  // drag / swipe / fling on the table; a short tap is a click on a card
  const canvasEl = () => renderer?.domElement;
  stage.addEventListener("pointerdown", (e) => {
    if (openCard) return;
    dragging = true; dragMoved = 0; dragStart = performance.now(); dragLast = e.clientX + e.clientY * 0.8; dragT = performance.now(); dragV = 0;
    spinningAtDown = Math.abs(wh.w) > 0.6 && (wh.mode === "free" || wh.mode === "land");
    try { (e.target as HTMLElement).setPointerCapture?.(e.pointerId); } catch { /* a synthetic pointer */ }
    canvasEl()?.classList.add("is-grab"); userTouched();
  });
  stage.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const pos = e.clientX + e.clientY * 0.8, now = performance.now(), dt = Math.max(1, now - dragT) / 1000;
    const cardPx = Math.max(120, cardWidthPx);
    const d = -(pos - dragLast) / cardPx;
    dragMoved += Math.abs(pos - dragLast);
    if (dragMoved > 8) { wh.th += d; wh.w = 0; wh.mode = "free"; wh.plan = null; landedAt = -1; }
    dragV += (d / dt - dragV) * 0.4;
    dragLast = pos; dragT = now; dirty = true;
  });
  const endDrag = (e: PointerEvent) => {
    if (!dragging) return;
    dragging = false; canvasEl()?.classList.remove("is-grab");
    if (dragMoved <= 8 && performance.now() - dragStart < 450) {
      // a tap while it spins is a hand brake; a tap on a still wheel opens the card under it
      if (spinningAtDown) { wh.brake = true; wh.plan = null; return; }
      const hit = pick(e.clientX, e.clientY); if (hit) open(hit); return;
    }
    if (dragMoved > 8) { wh.w = clamp(dragV, -WMAX * 1.25, WMAX * 1.25); wh.mode = "free"; wh.plan = null; wh.brake = false; wh.quiet = 0.12; wh.firm = false; }
  };
  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", () => { dragging = false; canvasEl()?.classList.remove("is-grab"); wh.quiet = 1; });

  $(".zt-spin")?.addEventListener("click", () => { userTouched(); let to = Math.floor(Math.random() * N); if (to === frontOf(theta) && N > 1) to = (to + 1 + Math.floor(Math.random() * (N - 1))) % N; spinTo(to, 1); });
  $(".zt-winner__open")?.addEventListener("click", () => open(cards[frontOf(theta)]));

  addEventListener("keydown", (e) => {
    if (openCard) {
      if (e.key === "Escape") { e.preventDefault(); close(); }
      else if (e.key === "Tab") trap(e);
      return;
    }
    const t = e.target as HTMLElement;
    if (t && t.closest && t.closest("a, button, input, textarea, select, summary") && t !== wheelEl) return;
    // the arrows belong to the wheel here (stop them reaching other page shortcuts)
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); e.stopPropagation(); userTouched(); stepTo(1); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); e.stopPropagation(); userTouched(); stepTo(-1); }
    else if (e.key === "Enter") { e.preventDefault(); open(cards[frontOf(theta)]); }
    else if (e.key === " " || e.key === "Spacebar") { e.preventDefault(); ($(".zt-spin") as HTMLButtonElement | null)?.click(); }
    else if (e.key === "Home") { e.preventDefault(); spinTo(0, 0, -1); }
    else if (e.key === "End") { e.preventDefault(); spinTo(N - 1, 0, 1); }
  }, true);

  // links to a section turn the wheel to its first card (and close an open card first)
  document.addEventListener("click", (e) => {
    const a = (e.target as Element)?.closest?.("a[href^='#']") as HTMLAnchorElement | null;
    if (!a) return;
    const id = decodeURIComponent(a.getAttribute("href")!.slice(1));
    const idx = id ? cards.findIndex((c) => c.section.id === id || c.el.id === id) : 0;
    if (idx < 0 && id) return;
    e.preventDefault(); e.stopPropagation();
    const go = () => { const cur = frontOf(theta); if (idx !== cur) spinTo(idx, 0, ((idx - cur + N) % N) <= N / 2 ? 1 : -1); };
    if (openCard) { close(); setTimeout(go, 520); } else go();
    userTouched();
  }, true);

  // ---------------------------------------------------------------- picking and opening a card
  let cardWidthPx = 300;
  function pick(x: number, y: number): Card | null {
    if (!ready) return null;
    const ray = new THREE!.Raycaster();
    ray.setFromCamera(new THREE!.Vector2((x / innerWidth) * 2 - 1, -(y / innerHeight) * 2 + 1), camera);
    const hits = ray.intersectObjects(cards.map((c) => c.group!), true);
    for (const h of hits) { let o: any = h.object; while (o && !o.userData.hasOwnProperty("slot")) o = o.parent; const c = cards.find((k) => k.group === o); if (c) return c; }
    return null;
  }
  let openCard: Card | null = null, flight: { c: Card; t0: number; dir: 1 | -1; from: any; to: any } | null = null, lastFocus: HTMLElement | null = null;
  let figTimer = 0;
  function open(c: Card) {
    if (openCard || flight || !ready) return;
    openCard = c; lastFocus = document.activeElement as HTMLElement;
    wh.w = 0; wh.mode = "free"; wh.plan = null; wh.quiet = 1;
    const g = c.group!;
    scene.attach(g);
    const from = { p: g.position.clone(), q: g.quaternion.clone(), s: 1 };
    // in front of the camera, square on, flipped half way (edge on) when the paper card takes over
    const dir = new THREE!.Vector3(); camera.getWorldDirection(dir);
    const dist = camDist * 0.62;
    const pos = camera.position.clone().add(dir.multiplyScalar(dist));
    const q = camera.quaternion.clone().multiply(new THREE!.Quaternion().setFromAxisAngle(new THREE!.Vector3(0, 1, 0), Math.PI / 2));
    flight = { c, t0: performance.now(), dir: 1, from, to: { p: pos, q, s: 1.05 } };
    root.classList.add("zt-opening");
    // move the article into the dialog
    if (c.el.parentNode) { c.home = document.createComment("zt-card"); c.el.parentNode.insertBefore(c.home, c.el); }
    dlgSlot.appendChild(c.el);
    c.el.querySelector<HTMLVideoElement>("video.zt-film")?.play().catch(() => { /* a tap plays it */ });
    c.el.classList.add("is-open");
    $(".zt-open__no")!.textContent = `No. ${c.i + 1}`;
    $(".zt-open__label")!.textContent = c.label;
    const h = c.el.querySelector<HTMLElement>("h1, h2, h3");
    if (h) { if (!h.id) h.id = `zt-h-${c.i}`; dlgCard.setAttribute("aria-labelledby", h.id); }
    // the figure keeps playing in the open card
    dlgFig.innerHTML = "";
    dlgFig.style.display = c.el.querySelector("video.zt-film, .zt-device, .zt-shot") ? "none" : "";   // the footage or the phone is the picture
    const fc = document.createElement("canvas"), fs = Math.min(2, devicePixelRatio || 1);
    fc.width = Math.round(FACE.fig.w * fs * 0.7); fc.height = Math.round(FACE.fig.h * fs * 0.7);
    dlgFig.appendChild(fc);
    let q2 = 0; const fx = fc.getContext("2d")!;
    const tick = () => { fx.setTransform(fc.width / FACE.fig.w, 0, 0, fc.height / FACE.fig.h, 0, 0); drawFigure(fx, c.fig, q2 / POSES, 0, 0, FACE.fig.w, FACE.fig.h, c.data); q2 = (q2 + 1) % POSES; };
    tick(); clearInterval(figTimer); figTimer = window.setInterval(tick, 125);
  }
  function close() {
    if (!openCard || flight) return;
    const c = openCard;
    dlg.classList.remove("is-shown");
    root.classList.remove("zt-dialog");
    clearInterval(figTimer);
    setTimeout(() => {
      dlg.setAttribute("hidden", "");
      // the article goes home
      c.el.querySelector<HTMLVideoElement>("video.zt-film")?.pause();
      if (c.home) { c.home.parentNode!.insertBefore(c.el, c.home); c.home.remove(); c.home = null; } else c.el.remove();
      c.el.classList.remove("is-open");
      const g = c.group!;
      const slot = new THREE!.Group(); table.add(slot); placeInSlot(slot as any, g.userData.slot); slot.updateMatrixWorld(true);
      const p = new THREE!.Vector3(), q = new THREE!.Quaternion(), s = new THREE!.Vector3();
      slot.matrixWorld.decompose(p, q, s); table.remove(slot);
      g.visible = true;
      flight = { c, t0: performance.now(), dir: -1, from: { p: g.position.clone(), q: g.quaternion.clone(), s: g.scale.x }, to: { p, q, s: 1 } };
    }, 230);
  }
  function trap(e: KeyboardEvent) {
    const f = $$<HTMLElement>("a[href], button, summary, [tabindex]:not([tabindex='-1'])", dlgCard).filter((x) => x.offsetParent !== null || x === document.activeElement);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  $(".zt-open__close")?.addEventListener("click", close);
  $(".zt-open__dim")?.addEventListener("click", close);
  // swipe down to close on touch
  let sy0 = -1;
  dlgCard.addEventListener("touchstart", (e) => { sy0 = dlgCard.scrollTop <= 0 ? e.touches[0].clientY : -1; }, { passive: true });
  dlgCard.addEventListener("touchend", (e) => { if (sy0 >= 0 && e.changedTouches[0].clientY - sy0 > 90) close(); sy0 = -1; }, { passive: true });

  function stepFlight(now: number) {
    if (!flight) return;
    const f = flight, g = f.c.group!;
    const dur = f.dir > 0 ? 480 : 520;
    const t = clamp((now - f.t0) / dur), e = easeIO(t);
    g.position.lerpVectors(f.from.p, f.to.p, e);
    g.quaternion.slerpQuaternions(f.from.q, f.to.q, e);
    const s = f.from.s + (f.to.s - f.from.s) * e; g.scale.set(s, s, s);
    dirty = true;
    if (t >= 1) {
      flight = null;
      if (f.dir > 0) {
        g.visible = false;
        dlg.removeAttribute("hidden");
        requestAnimationFrame(() => { dlg.classList.add("is-shown"); root.classList.add("zt-dialog"); root.classList.remove("zt-opening"); ($(".zt-open__close") as HTMLElement)?.focus(); dlgCard.scrollTop = 0; });
      } else {
        table.attach(g); placeInSlot(g, g.userData.slot);
        openCard = null;
        (lastFocus && lastFocus !== document.body && document.contains(lastFocus) && lastFocus.offsetParent !== null ? lastFocus : wheelEl).focus?.({ preventScroll: true } as any);
      }
    }
  }

  // ---------------------------------------------------------------- frame loop
  let lastNow = performance.now(), camDist = 4, shownState = "", lastFront = -1, pointerTilt = 0, pointerV = 0, lastFrac = 0;
  let acc = 0, physT = performance.now(), wasAlive = false, lastTilt = "", lastTheta = NaN, lastVars = "";
  addEventListener("resize", () => { if (ready) { const ph = phone(); if (ph !== wasPhone) { wasPhone = ph; for (const c of cards) redraw(c); build(); } else resize(); } });
  let wasPhone = phone();
  initGL().catch((err) => { console.error("[zoetrope] turntable failed", err); root.classList.remove("zt-on"); stills(cards); });
  // open on the card the address points at, if any
  const hashIdx = location.hash ? cards.findIndex((c) => c.section.id === decodeURIComponent(location.hash.slice(1))) : -1;


  onFrame(() => {
    const now = performance.now(), dt = Math.min(0.25, Math.max(0.001, (now - lastNow) / 1000));
    lastNow = now;
    if (!ready) return;
    stepFlight(now);

    // physics, in real time: as many fixed steps as the frame took (a long frame steps more, it never slows time)
    if (!dragging && !openCard) {
      acc += Math.min(1, Math.max(0, (now - physT) / 1000));
      while (acc >= STEP) {
        const was = wh.mode;
        step(wh, STEP);
        if (alive) phase += Math.abs(wh.w) * STEP;
        acc -= STEP;
        if (was !== "rest" && wh.mode === "rest") landed();
      }
    } else acc = 0;
    physT = now;
    theta = wh.th; omega = dragging ? dragV : wh.w;
    const speed = Math.abs(omega);
    if (speed > 3.0) { alive = true; aliveHold = now + 160; } else if (speed < 2.2 && now > aliveHold) alive = false;
    if (alive !== wasAlive) { root.classList.toggle("zt-alive", alive); wasAlive = alive; }

    // poses: under the strobe every figure steps on one pose per card past the pointer; the winner keeps playing
    const front = frontOf(theta);
    const winnerPlays = landedAt === front && !alive;
    const gpose = Math.floor(phase) % POSES;
    for (const c of cards) {
      let q = c.pose;
      if (alive) q = (gpose + c.i * 5) % POSES;
      else if (winnerPlays && c.i === front) { const k = Math.floor((now - landedPulse) / 140); q = k < POSES * 2 ? k % POSES : 0; }   // the winner plays its loop twice, then rests
      showPose(c, q);
    }
    feed(front);

    // the pointer ticks over the pegs between cards
    const frac = theta - Math.floor(theta);
    if (Math.floor(theta + 0.5) !== Math.floor(lastFrac + 0.5)) { pointerV += (omega >= 0 ? -1 : 1) * Math.min(12, 5 + speed * 0.9); }
    lastFrac = theta;
    for (let k = 0, n = Math.min(12, Math.ceil(dt / 0.016)); k < n; k++) { const h = dt / n; pointerV += (-pointerTilt * 160 - pointerV * 14) * h; pointerTilt += pointerV * h; }
    const tilt = `${clamp(pointerTilt * 9, -28, 28).toFixed(1)}deg`;
    if (tilt !== lastTilt) { pointer.style.setProperty("--tilt", tilt); lastTilt = tilt; }
    void frac;

    // furniture
    const st = alive ? `S${Math.round(Math.min(speed, 24))}` : landedAt === front ? `L${front}` : speed > 0.05 || wh.mode !== "rest" ? "T" : "I";
    if (st !== shownState) {
      shownState = st;
      if (stateEl) stateEl.textContent = alive ? "Strobe" : landedAt === front ? "Landed" : "Lamp";
      if (fpsEl) fpsEl.textContent = alive ? `${Math.round(Math.min(speed, 24))} cards a second` : landedAt === front ? `No. ${front + 1}` : st === "T" ? "turning" : "still";
      root.classList.toggle("zt-landed", landedAt === front && !alive);
    }
    if (front !== lastFront) { lastFront = front; dirty = true; }
    if (theta !== lastTheta) { lastTheta = theta; dirty = true; }
    if (landedAt >= 0 && now - landedPulse < 320) dirty = true;   // the winner leaning forward
    if (dirty || flight) render();
  });

  function landed() {
    const f = frontOf(theta);
    landedAt = f; landedPulse = performance.now();
    const c = cards[f];
    $(".zt-winner__no")!.textContent = `No. ${f + 1}`;
    $(".zt-winner__t")!.textContent = c.title;
    winner.removeAttribute("hidden");
    winner.classList.remove("is-pop"); void winner.offsetWidth; winner.classList.add("is-pop");
    live.textContent = `Card ${f + 1} of ${N}, ${c.label}: ${c.title}. Press Enter to open it.`;
    document.dispatchEvent(new CustomEvent("zt:landed", { detail: { card: f + 1, title: c.title } }));
    pointerV += 6;
    dirty = true;
  }

  function render() {
    const ph = phone(), W = innerWidth, H = innerHeight;
    const disp = theta;
    table.rotation.y = -(disp / N) * TAU;
    // the winner leans forward a touch
    for (const c of cards) {
      if (c === openCard || (flight && flight.c === c)) continue;
      const lift = landedAt === c.i && c.i === frontOf(theta) && !alive ? Math.min(1, (performance.now() - landedPulse) / 260) : 0;
      const a = c.group!.userData.slot;
      c.group!.position.set(Math.sin(a) * (R - 0.02 + lift * 0.06), TOP + PLINTH + CH / 2 + lift * 0.03, Math.cos(a) * (R - 0.02 + lift * 0.06));
    }
    const cardPx = ph ? Math.min(H * 0.5, (W * 0.74) / CW * CH) : Math.min(H * 0.58, (W * 0.36) / CW * CH);
    const fovr = (camera.fov * Math.PI) / 180;
    const d = CH / ((cardPx / H) * 2 * Math.tan(fovr / 2));
    camDist = d;
    cardWidthPx = cardPx * CW / CH;
    const el = LEAN, cy0 = TOP + PLINTH + CH / 2, cz0 = R;
    camera.position.set(0, cy0 + Math.sin(el) * d, cz0 + Math.cos(el) * d);
    camera.lookAt(0, cy0, cz0);
    camera.clearViewOffset(); camera.updateProjectionMatrix();
    const ty = ph ? H * 0.5 : H * 0.53;
    camera.setViewOffset(W, H, 0, H / 2 - ty, W, H);
    camera.updateProjectionMatrix();
    // the pointer sits just above the front card, the winner's label just below it
    const vars = `${(ty - cardPx / 2).toFixed(0)}|${(ty + cardPx / 2).toFixed(0)}|${cardWidthPx.toFixed(0)}`;
    if (vars !== lastVars) {
      lastVars = vars;
      const [a, b, cw] = vars.split("|");
      root.style.setProperty("--zt-top", `${a}px`); root.style.setProperty("--zt-bot", `${b}px`); root.style.setProperty("--zt-cw", `${cw}px`);
    }
    renderer.render(scene, camera);
    dirty = false;
  }

  // a film card's figure: twelve frames sampled from the film
  function sampleFilm(c: Card) {
    const v = document.createElement("video");
    v.muted = true; v.playsInline = true; v.preload = "auto"; v.crossOrigin = "anonymous"; v.src = (c.data as any).video;
    const frames: HTMLCanvasElement[] = [];
    let k = 0;
    const grab = () => {
      const cv = document.createElement("canvas"); cv.width = 320; cv.height = Math.round(320 * (v.videoHeight / Math.max(1, v.videoWidth)));
      cv.getContext("2d")!.drawImage(v, 0, 0, cv.width, cv.height); frames.push(cv);
      k++;
      if (k < POSES) v.currentTime = (v.duration * (k + 0.5)) / POSES;
      else { c.data.frames = frames; redraw(c); v.removeAttribute("src"); v.load(); }
    };
    v.addEventListener("loadeddata", () => { v.currentTime = v.duration * 0.5 / POSES; }, { once: true });
    v.addEventListener("seeked", grab);
    v.addEventListener("error", () => { /* keep the drawn fallback */ });
  }
}

/** Reduced motion, no WebGL: the list of cards, each figure drawn still. */
async function stills(cards: Card[]) {
  await stripFonts();
  for (const c of cards) {
    const host = c.el.querySelector<HTMLElement>(".zt-fig");
    if (!host) continue;
    const draw = () => {
      host.innerHTML = "";
      const b = host.getBoundingClientRect(), k = Math.min(devicePixelRatio || 1, 2);
      const w = Math.max(40, b.width), h = Math.max(40, b.height);
      const cv = document.createElement("canvas"); cv.width = Math.round(w * k); cv.height = Math.round(h * k);
      const x = cv.getContext("2d")!; x.scale(k, k);
      drawFigure(x, c.fig, 0, 0, 0, w, h, c.data);
      host.appendChild(cv);
    };
    draw();
    if (c.fig === "art") loadArt().then((a) => { c.data.art = a; draw(); });
  }
}
