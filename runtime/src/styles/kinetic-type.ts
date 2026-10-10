/**
 * Kinetic type: an instrument made of letters.
 *
 *  - Giant lines are FITTED: words are packed into lines and each line's width axis (Anybody, wdth 50-150) is set so
 *    it fills the measure exactly; lines too short even at wdth 150 are set bigger. As a giant line arrives it
 *    inflates (wdth and wght up), as it leaves it condenses.
 *  - Scroll velocity drives two springs (--kt-skew, --kt-stretch) that every big line responds to, and the marquees'
 *    speed and direction: fast scrolling skews, stretches and races; stopping springs back to a held pose.
 *  - The intro sentence pins and lights word by word at reading pace; the product title splits open like a portal
 *    around the phone; stats are odometer reels scrubbed by scroll; steps run sideways past a pinned numeral; the
 *    quote has a lens of weight that travels down it; the CTA is a marquee and a magnetic GO.
 * Reduced motion: lines are fitted but still, nothing skews, marquees and pins stop, numbers sit at their value.
 */
import { $, $$, chars, onFrame, pinSequence, reduced } from "./_kit";
import { clamp } from "../lib/util";

const expo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));
const smooth = (t: number) => { t = clamp(t); return t * t * (3 - 2 * t); };

type Line = { outer: HTMLElement; inner: HTMLElement; wd: number };
type Fill = { el: HTMLElement; html: string; lines: Line[]; arrive: boolean; t0: number; last: string[]; pack: number };

export default function start(): void {
  const root = document.documentElement;
  root.classList.add("kt-js");
  const phone = () => matchMedia("(max-width: 760px)").matches;
  menu();

  // ---------------------------------------------------------------- fitted giant lines
  const fills: Fill[] = $$<HTMLElement>("[data-kt-fill]").map((el) => {
    if (/^H[1-6]$/.test(el.tagName)) el.setAttribute("aria-label", (el.textContent || "").replace(/\s+/g, " ").trim());
    return { el, html: el.innerHTML, lines: [], arrive: el.hasAttribute("data-kt-arrive") && !reduced, t0: 0, last: [], pack: Number(el.dataset.ktPack || 50) };
  });
  function tokens(el: HTMLElement): string[] {
    const out: string[] = [];
    el.childNodes.forEach((n) => {
      if (n.nodeType === 3) (n.textContent || "").split(/\s+/).filter(Boolean).forEach((w) => out.push(esc(w)));
      else if (n instanceof HTMLElement) (n.textContent || "").split(/\s+/).filter(Boolean).forEach((w) => out.push(`<${n.tagName.toLowerCase()}>${esc(w)}</${n.tagName.toLowerCase()}>`));
    });
    return out;
  }
  function fit(F: Fill) {
    const el = F.el;
    el.innerHTML = F.html;
    const toks = tokens(el);
    const W = el.clientWidth;
    if (!W || !toks.length) return;
    el.innerHTML = "";
    const probe = document.createElement("span");
    probe.style.cssText = "display:inline-block;white-space:nowrap;visibility:hidden;position:absolute;left:0;top:0";
    el.appendChild(probe);
    const width = (html: string, wd: number) => { probe.innerHTML = html; probe.style.fontVariationSettings = `"wdth" ${wd}`; return probe.getBoundingClientRect().width; };
    const groups: string[][] = [];
    let cur: string[] = [];
    for (const t of toks) {
      const cand = [...cur, t];
      if (cur.length && width(cand.join(" "), F.pack) > W) { groups.push(cur); cur = [t]; } else cur = cand;
    }
    if (cur.length) groups.push(cur);
    const built = groups.map((g) => {
      const html = g.join(" ");
      const w50 = width(html, 50), w150 = width(html, 150);
      let wd = 150, scale = 1;
      if (w150 <= W) scale = Math.min(1.45, W / Math.max(1, w150));
      else {
        wd = clamp(50 + ((W - w50) / Math.max(1, w150 - w50)) * 100, 50, 150);
        const w = width(html, wd);
        wd = clamp(wd + ((W - w) / Math.max(1, w150 - w50)) * 100, 50, 150);
      }
      return { html, wd, scale };
    });
    probe.remove();
    F.lines = built.map((b) => {
      const outer = document.createElement("span"); outer.className = "kt-line";
      const inner = document.createElement("span"); inner.innerHTML = b.html;
      inner.style.fontVariationSettings = `"wdth" ${b.wd.toFixed(1)}`;
      if (b.scale !== 1) outer.style.fontSize = `${b.scale.toFixed(3)}em`;
      outer.appendChild(inner); el.appendChild(outer);
      return { outer, inner, wd: b.wd };
    });
    F.last = [];
  }
  const fitAll = () => fills.forEach(fit);
  fitAll();
  let rz = 0;
  addEventListener("resize", () => { clearTimeout(rz); rz = window.setTimeout(() => { fitAll(); relens(); }, 120); });
  document.fonts?.ready.then(() => { fitAll(); relens(); });
  const tStart = performance.now();
  fills.forEach((F) => { F.t0 = tStart; });

  // the big pieces all lean on the velocity springs
  if (!reduced) $$(".kt-hero__title, .kt-read, .kt-marquee, .kt-stat__v, .kt-step__title, .kt-display, .kt-faq__title, .kt-foot__mark, .kt-row__word").forEach((el) => el.classList.add("kt-flex"));

  // ---------------------------------------------------------------- the sentence, read word by word (pinned)
  const intro = $<HTMLElement>("[data-kt-read]");
  if (intro && !reduced) {
    const read = $<HTMLElement>(".kt-read", intro);
    const after = [...intro.querySelectorAll<HTMLElement>(".kt-intro__body, .kt-btns")];
    if (read) {
      chars(read, "kt-ch");
      const words = $$<HTMLElement>(".sx-word", read);
      words.forEach((w) => w.setAttribute("aria-hidden", "true"));
      pinSequence(intro, 1, (_s, p) => {
        const lit = Math.floor(clamp(p / 0.78) * words.length + 0.0001);
        words.forEach((w, i) => { w.style.opacity = i < lit ? "1" : "0.14"; });
        const a = clamp((p - 0.8) / 0.12);
        after.forEach((el) => { el.style.opacity = String(a); el.style.transform = `translateY(${((1 - a) * 30).toFixed(1)}px)`; });
      }, 2.3);
    }
  }

  // ---------------------------------------------------------------- the product title opens like a portal
  const portal = $<HTMLElement>("[data-kt-portal]");
  if (portal && !reduced && !phone() && portal.querySelector(".kt-portal__media > *")) {
    root.classList.add("kt-portal-on");
    pinSequence(portal, 1, (_s, p) => {
      portal.style.setProperty("--p", smooth(p / 0.72).toFixed(4));
      portal.style.setProperty("--pc", clamp((p - 0.7) / 0.16).toFixed(3));
    }, 1.9);
    fills.filter((F) => portal.contains(F.el)).forEach(fit);
  }

  // ---------------------------------------------------------------- steps run sideways past a pinned numeral
  const steps = $<HTMLElement>("[data-kt-steps]");
  if (steps && !reduced && !phone()) {
    root.classList.add("kt-steps-on");
    const row = $<HTMLElement>(".kt-steps__row", steps)!, num = $<HTMLElement>(".kt-steps__num", steps)!;
    const items = $$<HTMLElement>(".kt-step[data-n]", steps);
    pinSequence(steps, 1, (_s, p) => {
      const travel = Math.max(0, row.scrollWidth - innerWidth * 0.6);
      row.style.transform = `translate3d(${(-p * travel).toFixed(1)}px, 0, 0)`;
      let cur = items[0];
      for (const it of items) if (it.getBoundingClientRect().left < innerWidth * 0.55) cur = it;
      if (cur && num.textContent !== cur.dataset.n) num.textContent = cur.dataset.n || "";
    }, 0.55 * items.length + 0.6);
  }

  // ---------------------------------------------------------------- odometer reels
  const odos = $$<HTMLElement>("[data-kt-odo] .kt-stat__num").map((el) => {
    const txt = el.textContent || "";
    el.textContent = "";
    el.setAttribute("aria-hidden", "true");
    const digits: { strip: HTMLElement; target: number }[] = [];
    const nd = (txt.match(/\d/g) || []).length;
    let seen = 0;
    for (const c of txt) {
      if (/\d/.test(c)) {
        const reel = document.createElement("span"); reel.className = "kt-reel";
        const strip = document.createElement("span"); strip.className = "kt-reel__strip";
        for (let i = 0; i < 30; i++) { const s = document.createElement("span"); s.textContent = String(i % 10); strip.appendChild(s); }
        reel.appendChild(strip); el.appendChild(reel);
        const fromRight = nd - 1 - seen++;
        digits.push({ strip, target: (fromRight === 0 ? 20 : 10) + Number(c) });
      } else el.appendChild(document.createTextNode(c));
    }
    return { el, digits, last: -1 };
  });

  // ---------------------------------------------------------------- the lens of weight (quote)
  const lensEl = $<HTMLElement>("[data-kt-lens]");
  let lensWords: HTMLElement[] = [];
  function relens() {
    if (!lensEl) return;
    if (!lensWords.length) { chars(lensEl, "kt-lch"); lensWords = $$<HTMLElement>(".sx-word", lensEl); lensWords.forEach((w) => w.setAttribute("aria-hidden", "true")); }
    // lock the lines at the heaviest setting so changing weight never rewraps the quote
    lensEl.querySelectorAll(".kt-lline").forEach((l) => l.replaceWith(...l.childNodes));
    lensWords.forEach((w) => { w.style.setProperty("--wg", "900"); w.style.setProperty("--wd", "120"); });
    const rows: HTMLElement[][] = [];
    let top = NaN;
    for (const w of lensWords) { const t = w.offsetTop; if (!rows.length || Math.abs(t - top) > 4) { rows.push([]); top = t; } rows[rows.length - 1].push(w); }
    rows.forEach((r) => {
      const line = document.createElement("span"); line.className = "kt-lline";
      r[0].before(line);
      r.forEach((w, i) => { line.appendChild(w); if (i < r.length - 1) line.appendChild(document.createTextNode(" ")); });
    });
    lensEl.normalize();
    lensWords.forEach((w) => { w.style.setProperty("--wg", "500"); w.style.setProperty("--wd", "92"); });
  }
  relens();

  // ---------------------------------------------------------------- marquees
  const marquees = $$<HTMLElement>("[data-kt-marquee]").map((box) => {
    const row = $<HTMLElement>(".kt-marquee__row", box)!;
    const unit = [...row.childNodes];
    const fill = () => {
      row.querySelectorAll("[data-clone]").forEach((c) => c.remove());
      const one = row.scrollWidth;
      let n = 0;
      while (row.scrollWidth < innerWidth * 2 + one && n++ < 30) unit.forEach((u) => {
        const c = u.cloneNode(true) as HTMLElement;
        if (c.nodeType === 1) { c.setAttribute("data-clone", ""); c.setAttribute("aria-hidden", "true"); c.removeAttribute("id"); if (/^H[1-6]$/.test(c.tagName)) { const s = document.createElement("span"); s.className = c.className; s.innerHTML = c.innerHTML; s.setAttribute("data-clone", ""); s.setAttribute("aria-hidden", "true"); row.appendChild(s); return; } }
        else { const s = document.createElement("span"); s.setAttribute("data-clone", ""); s.textContent = c.textContent; row.appendChild(s); return; }
        row.appendChild(c);
      });
      return one;
    };
    const m = { box, row, dir: Number(box.dataset.ktMarquee) || 1, x: 0, speed: 0, unit: 0, hover: false, focus: false, fill };
    m.unit = fill();
    box.addEventListener("pointerenter", () => { m.hover = true; });
    box.addEventListener("pointerleave", () => { m.hover = false; });
    box.addEventListener("focusin", () => { m.focus = true; });
    box.addEventListener("focusout", () => { m.focus = false; });
    return m;
  });
  addEventListener("resize", () => marquees.forEach((m) => { m.unit = m.fill(); }));

  // ---------------------------------------------------------------- hover list: inversion, wider word, cursor-follow preview
  const list = $<HTMLElement>("[data-kt-list]");
  const preview = $<HTMLElement>(".kt-preview");
  const rows = list ? $$<HTMLElement>(".kt-row", list) : [];
  let px = innerWidth / 2, py = innerHeight / 2, cx = px, cy = py, hoverRow: HTMLElement | null = null;
  addEventListener("pointermove", (e) => { px = e.clientX; py = e.clientY; if (e.pointerType === "mouse") root.classList.add("kt-pointer"); }, { passive: true });
  rows.forEach((r) => {
    r.addEventListener("pointerenter", (e) => {
      if ((e as PointerEvent).pointerType !== "mouse") return;
      hoverRow = r;
      if (preview) {
        preview.querySelector(".kt-preview__n")!.textContent = r.querySelector(".kt-row__n")?.textContent || "";
        preview.querySelector(".kt-preview__t")!.textContent = r.querySelector(".kt-row__word")?.textContent || "";
        preview.classList.add("is-on");
      }
    });
    r.addEventListener("pointerleave", () => { hoverRow = null; preview?.classList.remove("is-on"); });
  });
  const touch = matchMedia("(hover: none)").matches;

  // ---------------------------------------------------------------- cursor with a verb, magnetic GO
  const cursor = $<HTMLElement>(".kt-cursor");
  const go = $<HTMLElement>("[data-kt-magnet]");
  let gx = 0, gy = 0;
  const verbFor = (t: Element | null): string => {
    if (!t) return "";
    if (t.closest(".kt-marquee--cta, .kt-go")) return "Go";
    if (t.closest(".kt-row")) return "View";
    if (t.closest("summary")) return (t.closest("details") as HTMLDetailsElement).open ? "Close" : "Open";
    if (t.closest("a, button")) return "Go";
    return "";
  };
  let verbTarget: Element | null = null;
  addEventListener("pointerover", (e) => { verbTarget = e.target as Element; }, { passive: true });
  $(".kt-marquee--cta")?.addEventListener("click", () => { const a = go as HTMLAnchorElement | null; if (a) a.click(); });

  // ---------------------------------------------------------------- the frame: springs, axes, marquees, reels, lens
  let skew = 0, skewV = 0, sdir = 1;
  onFrame(({ v, dt, vh }) => {
    // velocity springs (underdamped: a little overshoot, then the held pose)
    if (Math.abs(v) > 0.4) sdir = Math.sign(v);
    const target = clamp(v * 0.32, -8, 8);
    skewV += (target - skew) * 0.14; skewV *= 0.76; skew += skewV;
    if (Math.abs(skew) < 0.01 && Math.abs(target) < 0.01) skew = 0;
    root.style.setProperty("--kt-skew", (-skew).toFixed(3));
    root.style.setProperty("--kt-stretch", (1 + Math.min(0.15, Math.abs(skew) / 8 * 0.15)).toFixed(4));

    // fitted lines: inflate arriving, condense leaving
    const now = performance.now();
    for (const F of fills) {
      const r = F.el.getBoundingClientRect();
      if (r.bottom < -40 || r.top > vh + 40) continue;
      const enter = reduced ? 1 : clamp((vh - r.top) / (vh * 0.65));
      const leave = reduced ? 0 : clamp(-r.top / Math.max(1, r.height + vh * 0.25));
      F.lines.forEach((L, i) => {
        let k = Math.min(enter, 1 - leave);
        let rise = 0;
        if (F.arrive) {
          const a = expo(clamp((now - F.t0 - 150 - i * 85) / 1000));
          k *= a; rise = 1 - expo(clamp((now - F.t0 - 150 - i * 85) / 700));
        }
        const wd = 50 + (L.wd - 50) * k, wg = 300 + 500 * k;
        const key = `${wd.toFixed(1)}|${wg.toFixed(0)}|${rise.toFixed(3)}`;
        if (F.last[i] === key) return;
        F.last[i] = key;
        L.inner.style.fontVariationSettings = `"wdth" ${wd.toFixed(1)}`;
        L.inner.style.fontWeight = wg.toFixed(0);
        L.inner.style.transform = rise > 0.001 ? `translateY(${(rise * 110).toFixed(1)}%)` : "";
      });
    }

    // marquees: base speed + velocity, direction follows the scroll, a spring settles the speed
    for (const m of marquees) {
      const r = m.box.getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh || reduced || !m.unit) continue;
      const paused = m.focus || (m.hover && m.box.classList.contains("kt-marquee--big"));
      const want = paused ? 0 : (60 + Math.abs(v) * 42) * (m.hover ? 3 : 1);
      m.speed += (want - m.speed) * 0.08;
      m.x -= m.speed * dt * m.dir * sdir;
      m.x = ((m.x % m.unit) - m.unit) % m.unit;
      m.row.style.transform = `translate3d(${m.x.toFixed(1)}px, 0, 0)`;
    }

    // odometers: rolled by scroll position, never by a timer
    for (const o of odos) {
      const r = o.el.getBoundingClientRect();
      if (r.bottom < -vh * 0.5 || r.top > vh * 1.5) continue;
      const p = reduced ? 1 : smooth((vh - r.top) / (vh * 0.7));
      if (Math.abs(p - o.last) < 0.0005) continue;
      o.last = p;
      o.digits.forEach((d) => { d.strip.style.transform = `translateY(${(-d.target * p).toFixed(3)}em)`; });
    }

    // the lens: weight and width peak on the words crossing the middle of the screen
    if (lensEl && lensWords.length && !reduced) {
      const r = lensEl.getBoundingClientRect();
      if (r.bottom > 0 && r.top < vh) for (const w of lensWords) {
        const b = w.getBoundingClientRect();
        const d = Math.abs(b.top + b.height / 2 - vh * 0.5) / (vh * 0.42);
        const k = 1 - smooth(d);
        w.style.setProperty("--wg", (200 + 700 * k).toFixed(0));
        w.style.setProperty("--wd", (70 + 50 * k).toFixed(1));
      }
    }

    // touch: the row nearest the middle of the screen is the active one
    if (touch && rows.length) {
      let best: HTMLElement | null = null, bd = 1e9;
      for (const r of rows) { const b = r.getBoundingClientRect(); const d = Math.abs(b.top + b.height / 2 - vh * 0.5); if (d < bd && d < vh * 0.3) { bd = d; best = r; } }
      rows.forEach((r) => r.classList.toggle("is-active", r === best));
    }

    // pointer followers
    cx += (px - cx) * 0.2; cy += (py - cy) * 0.2;
    if (cursor) {
      cursor.style.transform = `translate3d(${cx.toFixed(1)}px, ${cy.toFixed(1)}px, 0)`;
      const verb = verbFor(verbTarget);
      cursor.classList.toggle("is-verb", !!verb);
      const sp = cursor.firstElementChild as HTMLElement;
      if (verb && sp.textContent !== verb) sp.textContent = verb;
    }
    if (preview && hoverRow) preview.style.transform = `translate3d(${(cx + 30).toFixed(1)}px, ${(cy - 110).toFixed(1)}px, 0)`;
    if (go && !reduced) {
      const b = go.getBoundingClientRect();
      const dx = px - (b.left - gx + b.width / 2), dy = py - (b.top - gy + b.height / 2);
      const near = Math.hypot(dx, dy) < b.width * 0.9;
      gx += ((near ? dx * 0.35 : 0) - gx) * 0.15; gy += ((near ? dy * 0.35 : 0) - gy) * 0.15;
      go.style.transform = `translate3d(${gx.toFixed(1)}px, ${gy.toFixed(1)}px, 0)`;
    }
  });
}

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// ---------------------------------------------------------------- the full-screen menu
function menu() {
  const btn = $<HTMLButtonElement>(".kt-nav__menu"), panel = $<HTMLElement>(".kt-menu");
  if (!btn || !panel) return;
  const set = (open: boolean) => {
    panel.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", String(open));
    btn.textContent = open ? "Close" : "Menu";
  };
  btn.addEventListener("click", () => set(!panel.classList.contains("is-open")));
  panel.addEventListener("click", (e) => { if ((e.target as HTMLElement).closest("a")) set(false); });
  addEventListener("keydown", (e) => { if (e.key === "Escape") set(false); });
}
