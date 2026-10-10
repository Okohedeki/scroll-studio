/**
 * Art deco: an opening night. Slow, sine-eased, symmetric about the centre line; never bouncy.
 *
 *   overture  the hero is a pinned stage: scroll parts the gold-lacquered doors from the centre, the sunburst fans
 *             open, the spotlight sweeps once and the headline rises letter by letter from its centre letter outwards
 *   doors     between scenes the doors close and reopen on the centre line; when they meet, their medallion names
 *             the next act. At the finale they half-close to frame the invitation
 *   dial      the elevator floor dial in the nav sweeps from floor to floor with the scroll
 *   fans      each section's sunburst opens symmetrically as it arrives; at the finale the rays converge
 *   dealing   features are dealt from behind a central medallion in mirrored pairs (scroll-scrubbed)
 *   tiers     the timeline's ziggurat unveils tier by tier from the centre
 *   marquee   chasing bulbs, their speed taken from the scroll velocity; steady and fully lit when the page is idle
 *   drums     billing numbers roll on odometer drums from the centre digit outwards, then a gilding pass
 *   pointer   gold line-work shimmers toward the pointer; mirrored pairs lean in mirror image
 */
import { $, $$, chars, onFrame, onSeen, pinned, reduced } from "./_kit";
import { clamp, lerp, smooth } from "../lib/util";

const sine = (t: number) => 0.5 - Math.cos(Math.PI * clamp(t)) / 2;
const sm = (a: number, b: number, v: number) => sine((v - a) / (b - a));
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"];

export default function start() {
  document.documentElement.classList.add("dc-live");
  navSplit();
  rises();
  overtureAndDoors();
  dial();
  fans();
  dealing();
  tiers();
  bulbs();
  drums();
  notes();
  pointer();
}

// the nav's links split evenly either side of the dial
function navSplit() {
  const nav = $(".ss-nav__in"), links = $(".ss-nav__links"), cta = $(".ss-nav .ss-btn");
  if (!nav || !links) return;
  const as = $$<HTMLAnchorElement>("a", links);
  const right = document.createElement("div");
  right.className = "dc-nav-r";
  as.slice(Math.ceil(as.length / 2)).forEach((a) => right.appendChild(a));
  if (cta) right.appendChild(cta);
  nav.appendChild(right);
}

// letters rise from the centre letter outwards
function rises() {
  $$<HTMLElement>("[data-dc-rise]").forEach((h) => {
    const target = $(".dc-gild", h) || h;
    const spans = chars(target);
    const mid = (spans.length - 1) / 2;
    spans.forEach((s, i) => s.style.setProperty("--o", Math.abs(i - mid).toFixed(1)));
    h.setAttribute("aria-label", target.getAttribute("aria-label") || "");
    target.removeAttribute("aria-label");
    (h as any).__spans = spans;
    if (h.hasAttribute("data-dc-hero")) return;
    const head = h.closest(".dc-head");
    if (reduced) { h.classList.add("dc-in"); head?.classList.add("dc-in"); return; }
    onSeen(h, () => {
      h.classList.add("dc-in"); head?.classList.add("dc-in");
      setTimeout(() => h.classList.add("dc-gilded"), 1100 + spans.length * 30);
    }, 0.4);
  });
  $$<HTMLElement>(".dc-head").forEach((hd) => { if (!hd.querySelector("[data-dc-rise]")) onSeen(hd, () => hd.classList.add("dc-in"), 0.3); });
}

function overtureAndDoors() {
  const doors = $(".dc-doors");
  const hero = $('[data-dc="overture"]');
  const h1 = hero ? $<HTMLElement>("[data-dc-hero]", hero) : null;
  const heroSpans: HTMLElement[] = h1 ? (h1 as any).__spans || [] : [];
  const burst = hero ? $(".dc-burst--hero", hero) : null;
  const spot = hero ? $(".dc-spot", hero) : null;
  const heroRule = hero ? $(".dc-rule", hero) : null;
  const finale = $('[data-dc="finale"]');
  const actEl = doors ? $(".dc-door__num", doors) : null, actWord = doors ? $(".dc-door__act", doors) : null;
  const nameEl = doors ? $(".dc-doors__name", doors) : null, kickEl = doors ? $(".dc-doors__kicker", doors) : null;
  const secs = $$<HTMLElement>("main .dc-sec");
  const mid = heroSpans.length ? (heroSpans.length - 1) / 2 : 0;
  let gilded = false, lastC = -1, lastAct = "";
  if (reduced) {
    if (h1) { heroSpans.forEach((s) => s.style.setProperty("--k", "1")); h1.classList.add("dc-in"); }
    doors?.classList.add("is-open");
    return;
  }
  onFrame(({ vh }) => {
    // overture
    let c = 0, p = 1;
    if (hero) {
      p = pinned(hero);
      c = 1 - sm(0.02, 0.42, p);
      if (burst) burst.style.setProperty("--a", (180 * sm(0.12, 0.75, p)).toFixed(1) + "deg");
      if (spot) spot.style.setProperty("--sweep", lerp(-38, 0, sm(0.25, 0.85, p)).toFixed(1) + "deg");
      const span = Math.max(1, mid);
      heroSpans.forEach((s) => {
        const o = parseFloat(s.style.getPropertyValue("--o")) / span;     // 0 at the centre letter, 1 at the ends
        s.style.setProperty("--k", sm(0.28 + o * 0.22, 0.46 + o * 0.22, p).toFixed(3));
      });
      heroRule?.style.setProperty("--rk", sm(0.5, 0.75, p).toFixed(3));
      if (!gilded && p > 0.72) { gilded = true; h1?.classList.add("dc-gilded"); }
    }
    // between scenes: close on each section boundary as it crosses the centre line
    const centre = vh * 0.5;
    let near = Infinity, nextSec: HTMLElement | null = null, nextIdx = 0;
    for (let i = 1; i < secs.length; i++) {
      if (secs[i - 1] === hero) continue;   // the overture opens on its own
      const top = secs[i].getBoundingClientRect().top;
      const d = Math.abs(top - centre);
      if (d < near) { near = d; nextSec = top > centre - vh * 0.02 ? secs[i] : secs[i]; nextIdx = i; }
    }
    if (near < Infinity) c = Math.max(c, 1 - sm(vh * 0.015, vh * 0.42, near));
    // the finale: the doors half-close to frame the invitation
    if (finale) {
      const r = finale.getBoundingClientRect();
      const k = 1 - sm(0, vh * 0.42, Math.abs(r.top + Math.min(r.height, vh) * 0.5 - vh * 0.5));
      c = Math.max(c, 0.34 * clamp(k));
    }
    if (doors) {
      if (Math.abs(c - lastC) > 0.0005) {
        lastC = c;
        doors.style.setProperty("--c", c.toFixed(4));
        doors.classList.toggle("is-open", c < 0.002);
      }
      // the medallion names the act about to begin
      const s = hero && c > 0.5 && p < 0.5 ? hero : nextSec;
      if (s) {
        const act = s === hero ? "Overture" : (s.dataset.act || "");
        const num = s === hero ? "" : ROMAN[Math.min(20, nextIdx)] || String(nextIdx);
        const key = act + num;
        if (key !== lastAct) {
          lastAct = key;
          if (actEl) actEl.textContent = s === hero ? "◆" : num;
          if (actWord) actWord.textContent = s === hero ? "◆" : "Act";
          if (nameEl) nameEl.textContent = s === hero ? (document.querySelector(".dc-dial__name")?.textContent || "") : act;
          if (kickEl) kickEl.textContent = s === hero ? "Scroll to open the doors" : "Now entering";
        }
      }
    }
  });
}

function dial() {
  const needle = $(".dc-dial__needle");
  const floors = $$<HTMLElement>(".dc-floor");
  const secs = $$<HTMLElement>("main .dc-sec");
  if (!needle || !floors.length || !secs.length) return;
  const angles = floors.map((f) => parseFloat(f.style.getPropertyValue("--a")));
  let cur = -1, ang = angles[0];
  onFrame(({ vh }) => {
    // fractional floor: the last section whose top has passed 45% of the screen, eased through each ride
    let i0 = 0;
    for (let i = 0; i < secs.length; i++) if (secs[i].getBoundingClientRect().top <= vh * 0.45) i0 = i;
    let f = i0;
    const nx = secs[i0 + 1];
    if (nx) f = i0 + sm(vh * 0.95, vh * 0.45, nx.getBoundingClientRect().top);
    const a0 = angles[Math.min(angles.length - 1, Math.floor(f))], a1 = angles[Math.min(angles.length - 1, Math.floor(f) + 1)];
    const target = lerp(a0, a1, f - Math.floor(f));
    ang += (target - ang) * (reduced ? 1 : 0.08);
    needle.style.setProperty("--needle", ang.toFixed(2) + "deg");
    const on = Math.round(f);
    if (on !== cur) { floors[cur]?.classList.remove("is-on"); floors[on]?.classList.add("is-on"); cur = on; }
  });
}

function fans() {
  const sec = $$<HTMLElement>(".dc-burst--section, .dc-burst--star");
  const conv = $$<HTMLElement>(".dc-burst--converge");
  if (reduced) return;
  onFrame(({ vh }) => {
    for (const b of sec) {
      const r = b.getBoundingClientRect();
      if (r.bottom < -vh || r.top > vh * 2) continue;
      b.style.setProperty("--a", (90 * sm(vh * 1.0, vh * 0.35, r.top)).toFixed(1) + "deg");
    }
    for (const b of conv) {
      const s = b.parentElement!.getBoundingClientRect();
      if (s.bottom < 0 || s.top > vh) continue;
      const k = sm(vh * 1.2, vh * 0.55, s.top + s.height * 0.5);
      b.style.setProperty("--r", lerp(68, 20, k).toFixed(1) + "%");
    }
  });
}

function dealing() {
  const pairs = $$<HTMLElement>("[data-dc-pair]");
  if (!pairs.length || reduced) return;
  onFrame(({ vh }) => {
    for (const p of pairs) {
      const r = p.getBoundingClientRect();
      if (r.bottom < -100 || r.top > vh + 100) continue;
      p.style.setProperty("--k", sm(vh * 0.98, vh * 0.55, r.top + r.height * 0.25).toFixed(3));
    }
  });
}

function tiers() {
  const ts = $$<HTMLElement>("[data-dc-tier]");
  if (!ts.length || reduced) return;
  onFrame(({ vh }) => {
    for (const t of ts) {
      const r = t.getBoundingClientRect();
      if (r.bottom < -100 || r.top > vh + 100) continue;
      t.style.setProperty("--r", sm(vh * 0.95, vh * 0.62, r.top).toFixed(3));
    }
  });
}

// marquee bulbs: laid around the frame; the chase is driven by scroll velocity and stops when the page is idle
function bulbs() {
  const hosts = $$<HTMLElement>("[data-dc-bulbs]");
  if (!hosts.length) return;
  document.documentElement.classList.add("dc-bulbs-live");
  type Rig = { host: HTMLElement; box: HTMLElement; list: HTMLElement[]; chase: boolean; key: string };
  const rigs: Rig[] = hosts.map((host) => {
    const chase = host.dataset.dcBulbs === "chase";
    const box = document.createElement("div");
    box.className = "dc-bulbs";
    box.setAttribute("aria-hidden", "true");
    // the ticket is masked (its notches), so its bulbs sit beside it rather than inside it
    if (!chase) { host.parentElement!.appendChild(box); box.style.zIndex = "3"; } else host.appendChild(box);
    return { host, box, list: [], chase, key: "" };
  });
  const lay = (rig: Rig) => {
    const w = rig.host.offsetWidth, h = rig.host.offsetHeight;
    const key = `${w}x${h}`;
    if (key === rig.key) return;
    rig.key = key;
    const inset = rig.chase ? 22 : -18;
    if (!rig.chase) {
      rig.box.style.cssText = `position:absolute; left:${rig.host.offsetLeft}px; top:${rig.host.offsetTop}px; width:${w}px; height:${h}px; z-index:3; pointer-events:none;`;
    }
    const W = w - inset * 2, H = h - inset * 2, gap = 26;
    const nx = Math.max(2, Math.round(W / gap)), ny = Math.max(2, Math.round(H / gap));
    const pts: [number, number][] = [];
    for (let i = 0; i < nx; i++) pts.push([inset + (W * i) / nx, inset]);
    for (let i = 0; i < ny; i++) pts.push([inset + W, inset + (H * i) / ny]);
    for (let i = 0; i < nx; i++) pts.push([inset + W - (W * i) / nx, inset + H]);
    for (let i = 0; i < ny; i++) pts.push([inset, inset + H - (H * i) / ny]);
    rig.box.innerHTML = pts.map(([x, y]) => `<i class="dc-bulb" style="left:${x.toFixed(1)}px; top:${y.toFixed(1)}px"></i>`).join("");
    rig.list = $$<HTMLElement>(".dc-bulb", rig.box);
  };
  let phase = 0, idle = 0, lastStep = -1;
  onFrame(({ v, dt, vh }) => {
    for (const rig of rigs) {
      const r = rig.host.getBoundingClientRect();
      if (r.bottom < -200 || r.top > vh + 200) continue;
      lay(rig);
      if (!rig.chase) continue;
      // at most six chase steps a second: each bulb then changes at most twice a second (well under 3 flashes/s)
      const speed = reduced ? 0 : Math.min(6, Math.abs(v) * 0.9);
      if (speed > 0.15) { phase += speed * dt; idle = 0; } else idle += dt;
      const step = Math.floor(phase);
      const steady = idle > 0.6 || reduced;
      const key = steady ? -2 : step % 3;
      if (key === lastStep) continue;
      lastStep = key;
      rig.list.forEach((b, i) => b.style.setProperty("--on", steady ? "1" : (i + step) % 3 === 0 ? "1" : ".32"));
    }
  });
  addEventListener("resize", () => rigs.forEach((r) => { r.key = ""; }));
}

// odometer drums for the billing numbers
function drums() {
  $$<HTMLElement>("[data-dc-count]").forEach((el) => {
    const raw = el.dataset.dcCount || el.textContent || "";
    if (reduced) return;
    el.setAttribute("aria-label", raw);
    const digits = [...raw].map((ch) => /\d/.test(ch));
    const n = digits.filter(Boolean).length;
    const midD = (n - 1) / 2;
    let di = 0;
    el.innerHTML = [...raw].map((ch) => {
      if (!/\d/.test(ch)) return `<span aria-hidden="true">${ch}</span>`;
      const o = Math.abs(di++ - midD);
      return `<span class="dc-drum" aria-hidden="true"><span style="--o:${o}" data-d="${ch}">${[...Array(10)].map((_, k) => `<i class="dc-digit">${k}</i>`).join("")}</span></span>`;
    }).join("");
    const strips = $$<HTMLElement>("[data-d]", el);
    onSeen(el, () => {
      requestAnimationFrame(() => strips.forEach((s) => s.style.setProperty("--d", s.dataset.d || "0")));
      setTimeout(() => el.closest(".dc-bill")?.classList.add("dc-gilded"), 2400);
    }, 0.5);
  });
}

// programme notes unfold from the centre
function notes() {
  $$<HTMLDetailsElement>(".dc-note-row").forEach((d) => d.addEventListener("toggle", () => {
    if (!d.open || reduced) return;
    $(".dc-note-row__a", d)?.animate([{ transform: "scaleY(0)", opacity: 0 }, { transform: "scaleY(1)", opacity: 1 }], { duration: 800, easing: "cubic-bezier(.37,0,.63,1)" });
  }));
}

function pointer() {
  const root = document.documentElement;
  let px = 0.5, tx = 0.5, mx = 0, tmx = 0;
  addEventListener("pointermove", (e) => { tx = e.clientX / innerWidth; tmx = tx - 0.5; }, { passive: true });
  if (reduced) return;
  onFrame(() => {
    px += (tx - px) * 0.05; mx += (tmx - mx) * 0.05;
    root.style.setProperty("--px", px.toFixed(3));
    root.style.setProperty("--mx", mx.toFixed(3));
  });
  void smooth;
}
