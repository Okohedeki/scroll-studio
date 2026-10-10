/**
 * Blueprint: you watch the product being engineered on one living drawing sheet. Every section is a view laid out on
 * one large sheet (a snake of views, three across on desktop, two on phones). Scroll position IS pen position: a
 * plotter pen at constant speed draws each view in drafting order (construction lines, lettering, visible outline,
 * hidden lines, centre lines, dimensions, leaders and balloons, hatching, notes, title fields), lifts, and the camera
 * pans linearly along the sheet's grid lines to the next view. Holding still leaves a half-drawn line where it is.
 * Stats are dimension lines whose values count in once both arrowheads land; features are balloons keyed to a bill of
 * materials while the assembly separates; the quote is a redline cloud; the finale stamps APPROVED and zooms out to
 * the whole completed sheet. Reduced motion (or a page with scenes): the views stay stacked, drawn complete, and
 * their annotation layer fades in as each view is reached.
 */
import { $, $$, onFrame, reduced } from "./_kit";

type Kind = "path" | "letter" | "count" | "show" | "wipe" | "stamp";
interface Item {
  el: HTMLElement | SVGElement; kind: Kind; key: number; len: number; start: number; hot: number;
  lines?: { l: number; r: number; t: number; b: number }[]; total?: number; last: number; cy?: number;
  num?: { node: Text; text: string; v: number; dec: number };
}
interface View { el: HTMLElement; items: Item[]; ink: number; x: number; y: number; w: number; h: number; title: string; zone: string; overlay?: SVGSVGElement; lastS: number; draw: number }
interface Seg { kind: "pan" | "draw" | "dwell" | "zoom" | "hold"; v: number; y0: number; len: number }

const SVGNS = "http://www.w3.org/2000/svg";
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const CAT_LEN: Record<string, number> = { show: 36, count: 70, stamp: 60 };

export default function start() {
  const main = $<HTMLElement>("main");
  const bpViews = $$<HTMLElement>("main section.bp-view");
  if (!main || !bpViews.length) return;
  const root = document.documentElement;
  const flow = reduced || !!document.querySelector("[data-scene]");
  root.classList.add(flow ? "bp-flow" : "bp-live", "bp-drawn");
  if (matchMedia("(pointer: fine)").matches) root.classList.add("bp-cursor");

  // every section on the page is a view; ones the style doesn't draw are framed as "DETAIL" views
  const secEls = $$<HTMLElement>(":scope > section, :scope > div > section", main);
  secEls.forEach((s) => { if (!s.classList.contains("bp-view")) { s.classList.add("bp-view", "bp-foreign"); s.dataset.view = "DETAIL"; } });

  let sheet: HTMLElement | null = null, paper: SVGSVGElement | null = null, spacer: HTMLElement | null = null;
  if (!flow) {
    sheet = document.createElement("div");
    sheet.className = "bp-sheet bp-grid";
    while (main.firstChild) sheet.appendChild(main.firstChild);
    main.appendChild(sheet);
    paper = document.createElementNS(SVGNS, "svg") as SVGSVGElement;
    paper.setAttribute("class", "bp-sheet__paper");
    paper.setAttribute("aria-hidden", "true");
    sheet.prepend(paper);
    spacer = document.createElement("div");
    spacer.className = "bp-spacer";
    spacer.setAttribute("aria-hidden", "true");
    main.after(spacer);
  }

  const views: View[] = secEls.map((el) => ({ el, items: [], ink: 0, x: 0, y: 0, w: 0, h: 0, title: el.dataset.view || "VIEW", zone: "", lastS: -1, draw: 0 }));
  const tb = {
    view: $<HTMLElement>('[data-tb="view"]'), sheet: $<HTMLElement>('[data-tb="sheet"]'), pen: $<HTMLElement>('[data-tb="pen"]'),
    scale: $<HTMLElement>('[data-tb="scale"]'), rev: $<HTMLElement>('[data-tb="rev"]'),
  };
  const zoneLinks = $$<HTMLAnchorElement>(".bp-bar__zones a");
  const rx = $<HTMLElement>(".bp-rule--x"), ry = $<HTMLElement>(".bp-rule--y");

  let segs: Seg[] = [], total = 0, vw = innerWidth, vh = innerHeight, sheetW = 0, sheetH = 0;
  let introPen = flow ? 1e9 : 0, introTarget = 0;
  const tIntro = performance.now();

  // ------------------------------------------------------------ build one view's drawing
  function buildView(v: View, index: number) {
    v.overlay?.remove();
    const el = v.el;
    const vr = el.getBoundingClientRect();
    const ox = vr.left, oy = vr.top, W = vr.width, H = vr.height;
    const rel = (r: DOMRect) => ({ l: r.left - ox, t: r.top - oy, r: r.right - ox, b: r.bottom - oy, w: r.width, h: r.height, cx: r.left - ox + r.width / 2, cy: r.top - oy + r.height / 2 });
    const svg = document.createElementNS(SVGNS, "svg") as SVGSVGElement;
    svg.setAttribute("class", "bp-ink" + (flow ? " bp-anno" : ""));
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("viewBox", `0 0 ${W.toFixed(0)} ${H.toFixed(0)}`);
    el.prepend(svg);
    v.overlay = svg;
    const items: Item[] = [];
    const domOrder = new Map<Element, number>();
    $$<HTMLElement>("*", el).forEach((n, i) => domOrder.set(n, i));
    const ord = (n: Element | null) => (n && domOrder.get(n)) || 0;
    const add = (cat: number, near: Element | null, sub: number, node: SVGElement | HTMLElement, kind: Kind, len: number, hot = -1) => {
      items.push({ el: node, kind, key: cat * 1e6 + ord(near) * 20 + sub, len, start: 0, hot, last: -1 });
    };
    const path = (d: string, cls: string, cat: number, near: Element | null, sub = 0, hot = -1) => {
      const p = document.createElementNS(SVGNS, "path");
      p.setAttribute("d", d); p.setAttribute("class", cls);
      svg.appendChild(p);
      const len = (p as SVGPathElement).getTotalLength();
      if (/ red| dot|k5h/.test(" " + cls)) { add(cat, near, sub, p, "show", CAT_LEN.show, hot); return p; }
      p.setAttribute("pathLength", "1");
      add(cat, near, sub, p, "path", Math.max(8, cls === "k0" ? len * 0.3 : len), hot);
      return p;
    };
    const arrow = (x: number, y: number, ang: number, cat: number, near: Element | null, sub: number) => {
      const a = 11, w = 3.6, c = Math.cos(ang), s = Math.sin(ang);
      const p1 = [x - a * c + w * s, y - a * s - w * c], p2 = [x - a * c - w * s, y - a * s + w * c];
      path(`M${x} ${y} L${p1[0]} ${p1[1]} L${p2[0]} ${p2[1]} Z`, "k5h", cat, near, sub);
    };

    // frame of the view and its corner registration marks (pre-printed: construction weight)
    const fx0 = W <= 760 ? 10 : 24, fy0 = W <= 760 ? 60 : 72;
    const frameP = path(`M${fx0} ${fy0} H${W - fx0} V${H - fx0} H${fx0} Z`, "k0", 0, el.firstElementChild, 0);
    items.pop(); frameP.removeAttribute("pathLength");
    // construction lines off the main drawing's extents, across the whole view
    const draw = el.querySelector<HTMLElement>(".bp-draw svg, .bp-draw .bp-device, .bp-draw .bp-photo, .bp-redline, .bp-approve, .bp-dims");
    if (draw) {
      const d = rel(draw.getBoundingClientRect());
      path(`M${fx0} ${d.t} H${W - fx0}`, "k0", 0, draw, 1);
      path(`M${fx0} ${d.b} H${W - fx0}`, "k0", 0, draw, 2);
      path(`M${d.l} ${fy0} V${H - fx0}`, "k0", 0, draw, 3);
      path(`M${d.r} ${fy0} V${H - fx0}`, "k0", 0, draw, 4);
    }
    // lettering guidelines (baseline and cap line) under each line of the titles
    $$<HTMLElement>(".bp-title", el).forEach((t) => {
      lineBoxes(t).forEach((ln, i) => {
        const r0 = t.getBoundingClientRect();
        const y1 = r0.top - oy + ln.t + (ln.b - ln.t) * 0.2, y2 = r0.top - oy + ln.t + (ln.b - ln.t) * 0.86;
        path(`M${fx0 + 8} ${y1} H${Math.min(W - fx0, r0.left - ox + ln.r + 60)}`, "k0", 0, t, 5 + i * 2);
        path(`M${fx0 + 8} ${y2} H${Math.min(W - fx0, r0.left - ox + ln.r + 60)}`, "k0", 0, t, 6 + i * 2);
      });
    });

    // template drawables
    $$<HTMLElement>("[data-pen]", el).forEach((n) => {
      const cat = +(n.dataset.pen || 8);
      const hotAttr = n.closest<HTMLElement>("[data-hot]")?.dataset.hot;
      const hot = hotAttr != null ? +hotAttr : -1;
      if (n instanceof SVGElement) {
        const geoms = n instanceof SVGGeometryElement ? [n] : $$<SVGGeometryElement>("path, line, rect, circle, polyline, polygon, ellipse", n);
        if (n.tagName.toLowerCase() === "text") { add(cat, n, 0, n, "show", CAT_LEN.show, hot); return; }
        geoms.forEach((gm, j) => {
          if (gm.classList.contains("bp-anchor")) return;
          const sc = (gm.getScreenCTM()?.a || 1);
          const len = gm.getTotalLength() * sc;
          const dashed = getComputedStyle(gm).strokeDasharray !== "none" && !gm.hasAttribute("pathLength");
          if (dashed) add(cat, n, j, gm, "show", CAT_LEN.show, hot);
          else { gm.setAttribute("pathLength", "1"); add(cat, n, j, gm, "path", Math.max(6, len), hot); }
        });
        return;
      }
      if (n.classList.contains("bp-letter")) {
        const lines = lineBoxes(n);
        const tot = lines.reduce((a, l) => a + (l.r - l.l), 0);
        items.push({ el: n, kind: "letter", key: cat * 1e6 + ord(n) * 20, len: Math.max(20, tot * (cat === 1 ? 0.7 : 0.28)), start: 0, hot, lines, total: tot, last: -1 });
      } else if (n.classList.contains("bp-count")) {
        const tn = [...n.childNodes].find((c) => c.nodeType === 3 && /\d/.test(c.textContent || "")) as Text | undefined;
        const m = tn?.textContent?.match(/-?\d[\d,]*(\.\d+)?/);
        const it: Item = { el: n, kind: "count", key: cat * 1e6 + ord(n) * 20 + 10, len: CAT_LEN.count, start: 0, hot, last: -1 };
        if (tn && m) it.num = { node: tn, text: tn.textContent || "", v: parseFloat(m[0].replace(/,/g, "")), dec: (m[1] || "").length ? m[1].length - 1 : 0 };
        items.push(it);
      } else add(cat, n, 0, n, "show", CAT_LEN.show, hot);
    });
    // the drawn phone and photos plot from the top down
    $$<HTMLElement>(".bp-device, .bp-photo", el).forEach((d) => add(2, d, 0, d, "wipe", d.getBoundingClientRect().height * 1.4));
    $$<HTMLElement>(".bp-detail-circle", el).forEach((d) => add(4, d, 0, d, "show", CAT_LEN.show));

    // leaders from notes to the drawing
    $$<HTMLElement>("[data-leader]", el).forEach((note) => {
      const name = note.dataset.leader!;
      let target: Element | null = el.querySelector(`[data-anchor="${name}"]`);
      if (!target && name === "pick") target = el.querySelector(".ss-app__opt.is-on, .ss-app__btn, .ss-phone");
      if (!target) target = el.querySelector(".ss-phone, .bp-draw svg");
      if (!target) return;
      const tr = rel(target.getBoundingClientRect());
      const lines = note.classList.contains("bp-letter") ? lineBoxes(note) : [];
      const nr = rel(note.getBoundingClientRect());
      const first = lines[0];
      const toRight = tr.cx > nr.r - 10;
      const sx = toRight ? (first ? nr.l + first.r : nr.r) + 14 : nr.l - 14, sy = first ? nr.t + (first.t + first.b) / 2 : nr.t + 14;
      const shx = sx + (toRight ? 30 : -30);
      let ax = tr.w > 2 ? (toRight ? tr.l : tr.r) : tr.cx, ay = tr.cy;
      if (name === "top" && tr.w > 2) { ax = tr.l + tr.w * 0.7; ay = tr.t; }
      path(`M${sx} ${sy} H${shx} L${ax} ${ay}`, "k6", 6, note, 0);
      if (note.dataset.term === "dot") path(`M${ax - 4} ${ay} a4 4 0 1 0 8 0 a4 4 0 1 0 -8 0`, "dot", 6, note, 1);
      else arrow(ax, ay, Math.atan2(ay - sy, ax - shx), 6, note, 1);
    });

    // dimensions: baseline dimensioning from one datum, each claim measured on a stepped part
    const dims = $$<HTMLElement>(".bp-dim", el);
    if (dims.length) {
      const list = el.querySelector<HTMLElement>(".bp-dims")!;
      const lr = rel(list.getBoundingClientRect());
      const x0 = lr.l + 6;
      const partTop = lr.b + 26, partH = 54;
      let maxX = x0;
      dims.forEach((d, j) => {
        const vEl = d.querySelector<HTMLElement>(".bp-dim__v")!;
        const vr2 = rel(vEl.getBoundingClientRect());
        const dr = rel(d.getBoundingClientRect());
        const y = vr2.cy, zero = d.classList.contains("is-zero");
        const x1 = zero ? x0 : dr.r;
        maxX = Math.max(maxX, x1);
        if (!zero) {
          path(`M${x1} ${y - 16} V${partTop - 3}`, "k5", 5, vEl, 0);
          path(`M${x0} ${y} H${vr2.l - 6}`, "k5", 5, vEl, 1);
          path(`M${vr2.r + 6} ${y} H${x1}`, "k5", 5, vEl, 2);
          arrow(x0, y, Math.PI, 5, vEl, 3);
          arrow(x1, y, 0, 5, vEl, 4);
        } else {
          path(`M${x0 - 46} ${y} H${x0}`, "k5", 5, vEl, 1);
          path(`M${x0 + 46} ${y} H${x0}`, "k5", 5, vEl, 2);
          arrow(x0, y, 0, 5, vEl, 3);
          arrow(x0, y, Math.PI, 5, vEl, 4);
        }
        if (j === 0) path(`M${x0} ${lr.t - 10} V${partTop - 3}`, "k5", 5, list, 0);
      });
      // the part being measured: a stepped profile, drawn as visible outline before the dimensions
      const steps = dims.map((d) => (d.classList.contains("is-zero") ? x0 : rel(d.getBoundingClientRect()).r)).sort((a, b) => a - b);
      let dd = `M${x0} ${partTop + partH} V${partTop}`;
      steps.forEach((sx2, k) => { dd += ` H${sx2} V${partTop + 8 + (k + 1) * (partH - 16) / steps.length}`; });
      dd += ` V${partTop + partH} Z`;
      path(dd, "k2", 2, list, 0);
      path(`M${x0 - 20} ${partTop + partH / 2} H${maxX + 20}`, "k0", 4, list, 1);
    }

    // tables: rules plotted row by row, each row's text right after its rules
    $$<HTMLTableElement>(".bp-bom, .bp-revs", el).forEach((tbl) => {
      const rows = [...tbl.rows];
      if (!rows.length) return;
      const tr0 = rel(tbl.getBoundingClientRect());
      rows.forEach((row, ri) => {
        const rr = rel(row.getBoundingClientRect());
        const cat = 8;
        const cells = [...row.cells];
        const lineAt = (d: string, sub: number) => {
          const p = path(d, "k5", cat, row, sub);
          return p;
        };
        lineAt(`M${tr0.l} ${rr.t} H${tr0.r}`, 0);
        cells.forEach((c, ci) => { const cr = rel(c.getBoundingClientRect()); lineAt(`M${cr.l} ${rr.t} V${rr.b}`, 1 + ci); });
        lineAt(`M${tr0.r} ${rr.t} V${rr.b}`, 9);
        if (ri === rows.length - 1) lineAt(`M${tr0.l} ${rr.b} H${tr0.r}`, 10);
      });
    });
    // re-key table text so it follows its row's rules
    $$<HTMLTableElement>(".bp-bom, .bp-revs", el).forEach((tbl) => {
      [...tbl.rows].forEach((row) => {
        items.forEach((it) => { if (it.el instanceof HTMLElement && row.contains(it.el) && it.el !== row) it.key = 8 * 1e6 + ord(row) * 20 + 12 + (it.key % 20) / 20; });
      });
    });

    // the redline cloud around the reviewer's note
    $$<HTMLElement>("[data-cloud]", el).forEach((q) => {
      const r = rel(q.getBoundingClientRect());
      path(cloud(r.l - 10, r.t - 10, r.r + 10, r.b + 10), "k6 cloud", 9, q, 0);
    });
    // the stamp goes last of all
    $$<HTMLElement>(".bp-stamp", el).forEach((s) => add(10, s, 0, s, "stamp", CAT_LEN.stamp));
    $$<HTMLElement>(".bp-vtitle", el).forEach((s) => add(9, s, 0, s, "show", CAT_LEN.show));
    if (el.classList.contains("bp-foreign")) $$<HTMLElement>(":scope > *:not(svg)", el).forEach((c) => add(8, c, 0, c, "show", 300));

    // redline cloud paths are styled red but still plot
    $$<SVGPathElement>("path.cloud", svg).forEach((p) => p.setAttribute("class", "k6 red"));
    items.sort((a, b) => a.key - b.key);
    // where each stroke sits, so a camera on a tall view can follow the pen down
    for (const it of items) {
      const r = (it.el as Element).getBoundingClientRect();
      it.cy = r.height < vh * 0.6 && it.key >= 1e6 ? (r.top + r.bottom) / 2 - oy : undefined;
    }
    let s = 0;
    for (const it of items) { it.start = s; s += it.len; }
    v.items = items;
    v.ink = s;
    v.lastS = -1;
    if (index === 0) {
      // the first view's construction and title plot in on load
      const t = items.filter((it) => it.key < 2e6);
      introTarget = t.length ? t[t.length - 1].start + t[t.length - 1].len : 0;
    }
    if (flow) setPen(v, 1e12);
  }

  // ------------------------------------------------------------ pen
  function setPen(v: View, s: number) {
    if (s === v.lastS) return;
    v.lastS = s;
    let hot = -1;
    for (const it of v.items) {
      const k = clamp((s - it.start) / it.len);
      if (k > 0 && k < 1 && it.hot >= 0) hot = it.hot;
      if (k === it.last) continue;
      it.last = k;
      const el = it.el as any;
      switch (it.kind) {
        case "path":
          el.style.strokeDasharray = "1 1";
          el.style.strokeDashoffset = String(1 - k);
          el.style.visibility = k > 0 ? "" : "hidden";
          break;
        case "show":
          el.style.visibility = k > 0 ? "" : "hidden";
          break;
        case "wipe":
          el.style.clipPath = k >= 1 ? "" : `inset(0 0 ${((1 - k) * 100).toFixed(2)}% 0)`;
          break;
        case "letter":
          el.style.clipPath = letterClip(it, k);
          break;
        case "count":
          el.style.visibility = k > 0 ? "" : "hidden";
          if (it.num) {
            const n = it.num;
            it.num.node.textContent = k >= 1 ? n.text : n.text.replace(/-?\d[\d,]*(\.\d+)?/, (n.v * k).toFixed(n.dec));
          }
          break;
        case "stamp":
          el.classList.toggle("is-on", k > 0);
          v.el.classList.toggle("is-approved", k > 0);
          break;
      }
    }
    if (v.el.classList.contains("bp-view--features")) {
      if (s >= v.ink) hot = -1;
      if (!hovering) setHot(v.el, hot);
    }
    // the assembly separates while its balloons are drawn, from assembled to exploded
    const ex = v.el.querySelector<SVGSVGElement>(".bp-explode");
    if (ex) {
      const balloons = v.items.filter((it) => it.hot >= 0 && it.kind !== "path");
      const first = v.items.find((it) => it.key >= 4e6);
      const a = first ? first.start : v.ink * 0.3;
      const b = balloons.length ? balloons[balloons.length - 1].start : v.ink * 0.7;
      const e = flow ? 1 : clamp((s - a) / Math.max(1, b - a));
      const dx = +(ex.dataset.dx || 90), dy = +(ex.dataset.dy || 34);
      const parts = $$<SVGGElement>(".bp-part", ex);
      const n = parts.length;
      parts.forEach((p) => {
        const i = +(p.dataset.i || 0);
        const xe = i * dx, ye = (n - 1 - i) * dy, xa = i * 4, ya = (n - 1) * dy - i * 4;
        p.setAttribute("transform", `translate(${lerp(xa, xe, e).toFixed(2)} ${lerp(ya, ye, e).toFixed(2)})`);
      });
    }
  }
  function letterClip(it: Item, k: number): string {
    if (k >= 1) return "";
    if (k <= 0 || !it.lines || !it.lines.length) return "polygon(0 0, 0 0, 0 0)";
    let rem = k * (it.total || 1);
    const pts: string[] = ["0px " + (it.lines[0].t - 6) + "px"];
    let lastB = it.lines[0].b;
    for (const ln of it.lines) {
      if (rem <= 0) break;
      const w = ln.r - ln.l;
      const x = ln.l + Math.min(w, rem) + (rem >= w ? 6 : 0);
      rem -= w;
      pts.push(`${x.toFixed(1)}px ${(ln.t - 6).toFixed(1)}px`, `${x.toFixed(1)}px ${(ln.b + 8).toFixed(1)}px`);
      lastB = ln.b + 8;
    }
    pts.push(`0px ${lastB.toFixed(1)}px`);
    return `polygon(${pts.join(",")})`;
  }
  let hovering = false;
  function setHot(viewEl: HTMLElement, i: number) {
    $$<SVGGElement>(".bp-part", viewEl).forEach((p) => p.classList.toggle("is-hot", +(p.dataset.i || -9) === i));
    $$<HTMLElement>(".bp-bom tr[data-i]", viewEl).forEach((r) => r.classList.toggle("is-hot", +(r.dataset.i || -9) === i));
  }
  views.forEach((v) => {
    v.el.addEventListener("pointerover", (e) => {
      const t = (e.target as Element).closest?.("[data-i]") as HTMLElement | null;
      if (!t || !v.el.contains(t)) return;
      hovering = true; setHot(v.el, +(t.dataset.i || -1));
    });
    v.el.addEventListener("pointerout", (e) => {
      const t = (e.target as Element).closest?.("[data-i]");
      if (!t) return;
      hovering = false; setHot(v.el, -1);
    });
  });

  // ------------------------------------------------------------ layout
  function layout() {
    vw = innerWidth; vh = innerHeight;
    const mobile = vw <= 760;
    // stats: each dimension's length follows its value (rank-safe: 32% to 100% of the list)
    $$<HTMLElement>(".bp-dims", main!).forEach((list) => {
      const ds = $$<HTMLElement>(".bp-dim", list);
      const vals = ds.map((d) => parseFloat(d.dataset.v || ""));
      const max = Math.max(1e-9, ...vals.filter((x) => isFinite(x)));
      ds.forEach((d, i) => {
        const x = vals[i];
        d.classList.toggle("is-zero", x === 0);
        d.style.setProperty("--len", x === 0 ? "auto" : `${(isFinite(x) ? 32 + 68 * (x / max) : 60).toFixed(1)}%`);
        if (x === 0) { d.style.width = "auto"; d.style.justifyItems = "start"; d.style.paddingLeft = "56px"; } else { d.style.width = ""; d.style.justifyItems = ""; d.style.paddingLeft = ""; }
      });
    });
    // a long drawing title shrinks until it fits its view
    $$<HTMLElement>(".bp-title", main!).forEach((t) => {
      t.style.fontSize = "";
      let fs = parseFloat(getComputedStyle(t).fontSize), guard = 0;
      const lim = vh * (mobile ? 0.3 : t.closest(".bp-view--hero") ? 0.42 : 0.3);
      while (t.offsetHeight > lim && fs > 26 && guard++ < 30) { fs *= 0.93; t.style.fontSize = fs + "px"; }
    });
    $$<HTMLElement>(".bp-btn", document).forEach((b) => b.setAttribute("data-w", (b.offsetWidth / 4).toFixed(1)));
    if (!flow && sheet) {
      sheet.style.transform = "none";
      const cols = mobile ? 2 : 3, G = Math.round(vw * (mobile ? 0.18 : 0.12)), M = Math.round(Math.max(48, vw * 0.06));
      views.forEach((v) => { v.el.style.width = vw + "px"; v.el.style.minHeight = vh + "px"; v.el.style.left = "0px"; v.el.style.top = "0px"; });
      const heights = views.map((v) => Math.max(vh, v.el.offsetHeight));
      let rowTop = M;
      for (let r = 0; r * cols < views.length; r++) {
        const row = views.slice(r * cols, r * cols + cols);
        const rh = Math.max(...row.map((_, j) => heights[r * cols + j]));
        row.forEach((v, j) => {
          const col = r % 2 === 0 ? j : cols - 1 - j;
          v.x = M + col * (vw + G); v.y = rowTop; v.w = vw; v.h = heights[r * cols + j];
          v.el.style.left = v.x + "px"; v.el.style.top = v.y + "px"; v.el.style.minHeight = v.h + "px";
        });
        rowTop += rh + G;
      }
      sheetW = 2 * M + cols * vw + (cols - 1) * G;
      sheetH = rowTop - G + M;
      sheet.style.width = sheetW + "px"; sheet.style.height = sheetH + "px";
      drawPaper(M);
    }
    views.forEach((v, i) => buildView(v, i));
    if (!flow) {
      // the scroll timeline: pen ink converts to scroll at one constant rate, so the pen speed never changes
      const inks = views.map((v) => v.ink);
      const median = [...inks].sort((a, b) => a - b)[Math.floor(inks.length / 2)] || 1;
      const rate = (vh * 1.5) / median;
      segs = []; let y = 0;
      views.forEach((v, i) => {
        if (i > 0) { const p = views[i - 1]; const len = (Math.abs(v.x - p.x) + Math.abs(v.y - p.y)) * 0.32; segs.push({ kind: "pan", v: i, y0: y, len }); y += len; }
        v.draw = clamp(v.ink * rate, vh * 0.8, vh * 2.8) + Math.max(0, v.h - vh) * 0.6;
        segs.push({ kind: "draw", v: i, y0: y, len: v.draw }); y += v.draw;
        segs.push({ kind: "dwell", v: i, y0: y, len: vh * 0.3 }); y += vh * 0.3;
      });
      segs.push({ kind: "zoom", v: views.length - 1, y0: y, len: vh * 1.1 }); y += vh * 1.1;
      segs.push({ kind: "hold", v: views.length - 1, y0: y, len: vh * 0.5 }); y += vh * 0.5;
      total = y;
      spacer!.style.height = total + vh + "px";
      (window as any).__bpSegs = segs;
    }
    views.forEach((v) => {
      const href = v.el.id ? "#" + v.el.id : "";
      v.zone = zoneOf(v);
      zoneLinks.forEach((a) => { if (href && a.getAttribute("href") === href) { const z = a.querySelector(".bp-zone"); if (z) z.textContent = v.zone; } });
    });
    lastY = -1;
  }
  function zoneOf(v: View) {
    if (flow || !sheetW) return "";
    const c = Math.min(8, Math.floor(((v.x + v.w / 2) / sheetW) * 8) + 1), r = Math.min(5, Math.floor(((v.y + Math.min(v.h, vh) / 2) / sheetH) * 6));
    return "ABCDEF"[r] + c;
  }
  function drawPaper(M: number) {
    if (!paper) return;
    paper.setAttribute("viewBox", `0 0 ${sheetW} ${sheetH}`);
    paper.setAttribute("width", String(sheetW)); paper.setAttribute("height", String(sheetH));
    let s = `<rect x="${M / 2}" y="${M / 2}" width="${sheetW - M}" height="${sheetH - M}" fill="none" stroke="#e8f1ff" stroke-width="3"/>`;
    s += `<rect x="${M / 2 + 14}" y="${M / 2 + 14}" width="${sheetW - M - 28}" height="${sheetH - M - 28}" fill="none" stroke="#e8f1ff" stroke-width="1"/>`;
    for (let i = 0; i < 8; i++) {
      const x = M / 2 + ((sheetW - M) * (i + 0.5)) / 8, xe = M / 2 + ((sheetW - M) * (i + 1)) / 8;
      if (i < 7) s += `<path d="M${xe} ${M / 2} v14 M${xe} ${sheetH - M / 2} v-14" stroke="#e8f1ff"/>`;
      s += `<text x="${x}" y="${M / 2 + 11}" fill="#e8f1ff" font-family="IBM Plex Mono, monospace" font-size="11" text-anchor="middle">${i + 1}</text>`;
      s += `<text x="${x}" y="${sheetH - M / 2 - 3}" fill="#e8f1ff" font-family="IBM Plex Mono, monospace" font-size="11" text-anchor="middle">${i + 1}</text>`;
    }
    for (let i = 0; i < 6; i++) {
      const y = M / 2 + ((sheetH - M) * (i + 0.5)) / 6, ye = M / 2 + ((sheetH - M) * (i + 1)) / 6;
      if (i < 5) s += `<path d="M${M / 2} ${ye} h14 M${sheetW - M / 2} ${ye} h-14" stroke="#e8f1ff"/>`;
      s += `<text x="${M / 2 + 7}" y="${y + 4}" fill="#e8f1ff" font-family="IBM Plex Mono, monospace" font-size="11" text-anchor="middle">${"ABCDEF"[i]}</text>`;
      s += `<text x="${sheetW - M / 2 - 7}" y="${y + 4}" fill="#e8f1ff" font-family="IBM Plex Mono, monospace" font-size="11" text-anchor="middle">${"ABCDEF"[i]}</text>`;
    }
    paper.innerHTML = s;
  }

  // ------------------------------------------------------------ frame
  let lastY = -1, camX = 0, camY = 0, camZ = 1, curView = 0;
  function frame(y: number) {
    if (!flow && introPen < introTarget) introPen = introTarget * clamp((performance.now() - tIntro - 250) / 1700);
    if (y === lastY && !(introPen > 0 && introPen < introTarget)) return;
    lastY = y;
    if (flow) { flowHud(); return; }
    const yy = clamp(y, 0, total);
    let seg = segs[segs.length - 1];
    for (const s of segs) if (yy >= s.y0 && yy < s.y0 + s.len) { seg = s; break; }
    const k = clamp((yy - seg.y0) / Math.max(1, seg.len));
    const vi = seg.v, v = views[vi];
    // pen positions for every view: earlier views complete, later ones blank
    views.forEach((w, i) => {
      let s = i < vi ? 1e12 : i > vi ? 0 : seg.kind === "pan" ? 0 : seg.kind === "draw" ? k * w.ink : 1e12;
      if (i === 0) s = Math.max(s, introPen);
      setPen(w, s);
    });
    // camera
    if (seg.kind === "pan") {
      const p = views[vi - 1];
      // along the sheet's grid lines: horizontal first, then vertical
      const pY = p.y + follow(p, p.ink), dxv = v.x - p.x, dyv = v.y - pY;
      const tot = Math.abs(dxv) + Math.abs(dyv) || 1, split = Math.abs(dxv) / tot;
      camX = split > 0 ? p.x + dxv * clamp(k / split) : v.x;
      camY = split < 1 ? pY + dyv * clamp((k - split) / (1 - split)) : pY;
      camZ = 1;
    } else if (seg.kind === "draw") { camX = v.x; camY = v.y + follow(v, k * v.ink); camZ = 1; }
    else if (seg.kind === "dwell") { camX = v.x; camY = v.y + follow(v, v.ink); camZ = 1; }
    else {
      const fit = Math.min((vw * 0.92) / sheetW, ((vh - 70) * 0.9) / sheetH);
      const z = seg.kind === "zoom" ? lerp(1, fit, k) : fit;
      const fx = v.x, fy = v.y + follow(v, v.ink);
      const tx = (sheetW * fit - vw) / 2, ty = (sheetH * fit - vh) / 2 - 20;
      const kk = seg.kind === "zoom" ? k : 1;
      // interpolate the screen-space offset so the zoom stays linear
      camZ = z;
      camX = lerp(fx, tx / fit, kk) ; camY = lerp(fy, ty / fit, kk);
      const sx = lerp(-fx, -tx, kk), sy = lerp(-fy, -ty, kk);
      sheet!.style.transform = `translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px) scale(${z.toFixed(4)})`;
      hud(vi, seg, k, z);
      return;
    }
    sheet!.style.transform = `translate(${(-camX).toFixed(1)}px, ${(-camY).toFixed(1)}px)`;
    hud(vi, seg, k, 1);
  }
  /** camera offset inside a tall view: the lowest point the pen has reached so far, kept near mid-screen */
  function follow(v: View, s: number) {
    const room = Math.max(0, v.h - vh);
    if (!room) return 0;
    let m = vh * 0.5;
    for (const it of v.items) {
      if (it.start > s) break;
      if (it.cy == null) continue;
      const k = clamp((s - it.start) / it.len);
      const target = Math.max(m, it.cy);
      m = m + (target - m) * k;
    }
    return clamp(m - vh * 0.5, 0, room);
  }
  function hud(vi: number, seg: Seg, k: number, z: number) {
    const v = views[vi];
    curView = vi;
    if (tb.view) tb.view.textContent = seg.kind === "zoom" || seg.kind === "hold" ? "SHEET COMPLETE" : v.title + (v.zone ? " · " + v.zone : "");
    if (tb.sheet) tb.sheet.textContent = `${vi + 1} OF ${views.length}`;
    if (tb.pen) tb.pen.textContent = seg.kind === "pan" ? "UP" : seg.kind === "draw" ? Math.round(k * 100) + "%" : "UP";
    if (tb.scale) tb.scale.textContent = z > 0.99 ? "1:1" : "1:" + (1 / z).toFixed(1);
    if (tb.rev) tb.rev.textContent = "ABCDEFGHJKLMNPRSTUVWXYZ"[Math.min(22, vi)];
    rx?.style.setProperty("--rx", (-camX * z).toFixed(1) + "px");
    ry?.style.setProperty("--ry", (-camY * z).toFixed(1) + "px");
    zoneLinks.forEach((a) => a.classList.toggle("is-on", !!v.el.id && a.getAttribute("href") === "#" + v.el.id));
  }
  function flowHud() {
    let vi = 0;
    views.forEach((v, i) => { if (v.el.getBoundingClientRect().top < vh * 0.5) vi = i; });
    const v = views[vi];
    if (tb.view) tb.view.textContent = v.title;
    if (tb.sheet) tb.sheet.textContent = `${vi + 1} OF ${views.length}`;
    if (tb.pen) tb.pen.textContent = "100%";
    zoneLinks.forEach((a) => a.classList.toggle("is-on", !!v.el.id && a.getAttribute("href") === "#" + v.el.id));
  }

  // anchors: a view's id lives on the sheet, so jump to where that view is fully drawn
  if (!flow) {
    addEventListener("click", (e) => {
      const a = (e.target as Element).closest?.("a[href^='#']") as HTMLAnchorElement | null;
      if (!a) return;
      const id = a.getAttribute("href")!;
      let target = 0;
      if (id.length > 1) {
        const i = views.findIndex((v) => "#" + v.el.id === id || !!v.el.querySelector(id.replace(/([^\w#-])/g, "\\$1")));
        if (i < 0) return;
        const s = segs.find((sg) => sg.kind === "dwell" && sg.v === i);
        target = s ? s.y0 + 2 : 0;
      }
      e.preventDefault(); e.stopImmediatePropagation();
      const from = scrollY, t0 = performance.now(), dur = Math.min(1600, 500 + Math.abs(target - from) * 0.05);
      const step = (now: number) => { const q = clamp((now - t0) / dur); scrollTo(0, from + (target - from) * (q < 0.5 ? 2 * q * q : 1 - Math.pow(-2 * q + 2, 2) / 2)); if (q < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step);
    }, true);
  } else {
    const io = new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) en.target.querySelector(".bp-ink")?.classList.add("is-seen"); }), { threshold: 0.15 });
    views.forEach((v) => io.observe(v.el));
  }
  // the approval stamp also lands on click
  $$<HTMLAnchorElement>(".bp-btn--approve").forEach((b) => b.addEventListener("click", () => {
    const s = b.closest(".bp-view")?.querySelector(".bp-stamp"); s?.classList.add("is-on"); b.closest(".bp-view")?.classList.add("is-approved");
  }));
  // CAD crosshair with sheet coordinates (in drawing millimetres at 1:1, four pixels to the millimetre)
  const cross = $<HTMLElement>(".bp-cross"), xy = $<HTMLElement>(".bp-cross__xy");
  if (cross && root.classList.contains("bp-cursor")) {
    addEventListener("pointermove", (e) => {
      cross.style.setProperty("--cx", e.clientX + "px"); cross.style.setProperty("--cy", e.clientY + "px");
      const sx = flow ? e.clientX : camX + e.clientX / camZ, sy = flow ? e.clientY + scrollY : camY + e.clientY / camZ;
      if (xy) xy.textContent = `X ${(sx / 4).toFixed(1)}  Y ${(sy / 4).toFixed(1)}`;
    }, { passive: true });
  }

  layout();
  let rt = 0;
  addEventListener("resize", () => { clearTimeout(rt); rt = window.setTimeout(() => { layout(); frame(scrollY); }, 120); });
  document.fonts?.ready.then(() => { layout(); frame(scrollY); });
  onFrame(({ y }) => frame(y));
}

/** Line boxes of an element's text, relative to its own border box. */
function lineBoxes(el: HTMLElement): { l: number; r: number; t: number; b: number }[] {
  const box = el.getBoundingClientRect();
  const range = document.createRange();
  range.selectNodeContents(el);
  const rects = [...range.getClientRects()].filter((r) => r.width > 0.5);
  const lines: { l: number; r: number; t: number; b: number }[] = [];
  for (const r of rects) {
    const t = r.top - box.top, b = r.bottom - box.top, l = r.left - box.left, rr = r.right - box.left;
    const ln = lines.find((x) => Math.abs((x.t + x.b) / 2 - (t + b) / 2) < Math.max(4, (b - t) * 0.35));
    if (ln) { ln.l = Math.min(ln.l, l); ln.r = Math.max(ln.r, rr); ln.t = Math.min(ln.t, t); ln.b = Math.max(ln.b, b); }
    else lines.push({ l, r: rr, t, b });
  }
  lines.sort((a, b) => a.t - b.t);
  return lines;
}

/** A revision cloud: scallops all the way round a rectangle. */
function cloud(x0: number, y0: number, x1: number, y1: number): string {
  const r = 16;
  let d = `M${x0} ${y0}`;
  const side = (ax: number, ay: number, bx: number, by: number) => {
    const len = Math.hypot(bx - ax, by - ay), n = Math.max(2, Math.round(len / (r * 2.2)));
    const sx = (bx - ax) / n, sy = (by - ay) / n;
    for (let i = 0; i < n; i++) d += ` a${r} ${r} 0 0 1 ${sx.toFixed(1)} ${sy.toFixed(1)}`;
  };
  side(x0, y0, x1, y0); side(x1, y0, x1, y1); side(x1, y1, x0, y1); side(x0, y1, x0, y0);
  return d;
}
