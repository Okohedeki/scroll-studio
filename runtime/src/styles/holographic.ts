/**
 * Holographic: scroll is the viewing angle. Every [data-hg-plate] turns through an arc as it travels through the
 * screen (feature cards in a staggered wave), its spectral sheen band (--b) sweeps with the angle, and its latent
 * content (--lat) shows only inside a narrow band of angles. The pointer is the light source (tilt, glare); on phones
 * an opt-in gyroscope adds tilt. Sections materialise behind a projector scan line and de-resolve as they leave.
 * Stats count up during their materialise scan; the timeline is a volume of slices the camera travels through.
 * Reduced motion: plates rest at a fixed flattering angle, latent content shown, no scan (a fade), no jitter.
 */
import { $, $$, onFrame, reduced, through, pinned } from "./_kit";
import { clamp } from "../lib/util";

const sstep = (a: number, b: number, v: number) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };

type Plate = {
  el: HTMLElement; range: number; off: number; wave: number; rare: boolean; grid: HTMLElement | null;
  px: number; py: number; tpx: number; tpy: number; gx: number; gy: number; glare: number; tglare: number; last: string;
};

export default function start() {
  const root = document.documentElement;
  root.classList.add("hg-live");
  if (reduced) root.classList.add("hg-rm");

  // ---------------------------------------------------------------- plates
  const plates: Plate[] = $$<HTMLElement>("[data-hg-plate]").map((el) => ({
    el, range: parseFloat(el.dataset.range || "25"), off: parseFloat(el.dataset.off || "0"),
    wave: el.dataset.wave ? parseInt(el.dataset.wave, 10) : -1, rare: el.hasAttribute("data-rare"), grid: el.closest<HTMLElement>(".hg-binder"),
    px: 0, py: 0, tpx: 0, tpy: 0, gx: 50, gy: 30, glare: 0, tglare: 0, last: "",
  }));
  plates.forEach((p) => {
    if (reduced) return;
    p.el.addEventListener("pointermove", (e) => {
      if (e.pointerType === "touch") return;
      const r = p.el.getBoundingClientRect();
      const x = clamp((e.clientX - r.left) / r.width), y = clamp((e.clientY - r.top) / r.height);
      p.tpx = (x - 0.5) * 2; p.tpy = (y - 0.5) * 2; p.gx = x * 100; p.gy = y * 100; p.tglare = 1;
    });
    p.el.addEventListener("pointerleave", () => { p.tpx = 0; p.tpy = 0; p.tglare = 0; });
  });

  // ---------------------------------------------------------------- feature cards turn over
  $$<HTMLElement>(".hg-slot").forEach((slot) => {
    const btn = slot.querySelector<HTMLButtonElement>(".hg-flip");
    const toggle = () => { const on = slot.classList.toggle("is-flipped"); btn?.setAttribute("aria-pressed", String(on)); };
    btn?.addEventListener("click", toggle);
    slot.querySelector(".hg-tcard")?.addEventListener("click", (e) => { if (!(e.target as HTMLElement).closest("a")) toggle(); });
  });

  // ---------------------------------------------------------------- foil buttons: the glint follows the pointer
  $$<HTMLElement>(".hg-btn--foil").forEach((b) => b.addEventListener("pointermove", (e) => {
    const r = b.getBoundingClientRect();
    b.style.setProperty("--bx", (((e.clientX - r.left) / r.width) * 100).toFixed(0) + "%");
  }));

  // ---------------------------------------------------------------- gyroscope, opt-in
  let gx = 0, gy = 0, gyro = false;
  const tilt = $<HTMLButtonElement>(".hg-tilt");
  if (tilt && !reduced && "DeviceOrientationEvent" in window && matchMedia("(hover: none) and (pointer: coarse)").matches && navigator.maxTouchPoints > 0 && "ontouchstart" in window) {
    tilt.hidden = false;
    tilt.addEventListener("click", async () => {
      if (gyro) { gyro = false; gx = gy = 0; tilt.setAttribute("aria-pressed", "false"); return; }
      const D = DeviceOrientationEvent as unknown as { requestPermission?: () => Promise<string> };
      try { if (D.requestPermission && (await D.requestPermission()) !== "granted") return; } catch { return; }
      gyro = true; tilt.setAttribute("aria-pressed", "true");
    });
    addEventListener("deviceorientation", (e) => {
      if (!gyro) return;
      gx = clamp((e.gamma || 0) / 30, -1, 1); gy = clamp(((e.beta || 0) - 45) / 30, -1, 1);
    });
  }

  // ---------------------------------------------------------------- sections: projection scan in, de-resolve out
  const secs = $$<HTMLElement>(".hg-sec").map((el) => ({ el, state: "off" as "off" | "on" | "out" }));
  const counted = new WeakSet<HTMLElement>();
  function project(s: { el: HTMLElement; state: string }, vh: number) {
    const r = s.el.getBoundingClientRect();
    if (s.state !== "on" && r.top < vh * 0.72 && r.bottom > vh * 0.3) {
      s.el.classList.remove("is-out"); void s.el.offsetWidth; s.el.classList.add("is-on"); s.state = "on";
      if (!counted.has(s.el)) { counted.add(s.el); countUp(s.el); }
    } else if (s.state === "on" && r.bottom < vh * 0.22) {
      s.el.classList.remove("is-on"); s.el.classList.add("is-out"); s.state = "out";
    } else if (s.state === "out" && r.top > vh) {
      s.el.classList.remove("is-out"); s.state = "off";
    }
  }
  function countUp(sec: HTMLElement) {
    const nums = $$<HTMLElement>(".hg-num[data-n]", sec);
    if (!nums.length || reduced) return;
    const items = nums.map((n) => { const b = n.querySelector("b")!; const raw = b.textContent || ""; const v = parseFloat(n.dataset.n!); const dec = (n.dataset.n!.split(".")[1] || "").length; b.textContent = (0).toFixed(dec); return { b, raw, v, dec }; });
    const t0 = performance.now();
    const step = (now: number) => {
      const k = clamp((now - t0 - 250) / 1100), e = 1 - Math.pow(1 - k, 3);
      items.forEach((it) => { const v = (it.v * e).toFixed(it.dec); it.b.textContent = k >= 1 ? it.raw : it.raw.includes(",") ? Number(v).toLocaleString("en-US") : v; });
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // ---------------------------------------------------------------- timeline: travel through the slices
  const vols = $$<HTMLElement>(".hg-timeline").map((sec) => ({ sec, panes: $$<HTMLElement>(".hg-pane", sec), bar: $<HTMLElement>(".hg-depthbar", sec) }));
  function updateVolumes(vh: number) {
    for (const v of vols) {
      const r = v.sec.getBoundingClientRect();
      if (r.bottom < -100 || r.top > vh + 100) continue;
      const n = v.panes.length, p = pinned(v.sec);
      const pos = reduced ? Math.round(p * (n - 1)) : clamp((p - 0.05) / 0.85) * (n - 1);
      const gap = innerWidth < 760 ? 360 : 520;
      v.panes.forEach((pane, i) => {
        const d = i - pos;               // >0: still ahead (deeper), <0: passed (behind the viewer)
        const z = -d * gap;
        const o = d < 0 ? clamp(1 + d * 2.4) : clamp(1 - d * 0.42);
        pane.style.setProperty("--z", z.toFixed(1) + "px");
        pane.style.setProperty("--o", o.toFixed(3));
        pane.style.zIndex = String(100 - Math.round(Math.abs(d) * 10));
        pane.style.visibility = o < 0.01 ? "hidden" : "";
      });
      v.bar?.style.setProperty("--dp", clamp(pos / Math.max(1, n - 1)).toFixed(3));
    }
  }

  // ---------------------------------------------------------------- nav: active link; page progress tints the foil
  const links = $$<HTMLAnchorElement>(".ss-nav__links a[href^='#']");
  const targets = links.map((a) => document.getElementById(a.getAttribute("href")!.slice(1)));
  let navOn = -2, spLast = -1;

  onFrame(({ y, dt, t, vh }) => {
    dt = dt || 0.016;
    for (const s of secs) project(s, vh);
    updateVolumes(vh);
    const sp = Math.round(clamp(y / Math.max(1, document.documentElement.scrollHeight - vh)) * 400) / 400;
    if (sp !== spLast) { spLast = sp; root.style.setProperty("--hg-sp", String(sp)); }
    let on = -1;
    targets.forEach((tg, i) => { if (tg && tg.getBoundingClientRect().top < vh * 0.5) on = i; });
    if (on !== navOn) { navOn = on; links.forEach((a, i) => a.classList.toggle("is-on", i === on)); }

    const grids = new Map<HTMLElement, number>();
    for (const p of plates) {
      const r = p.el.getBoundingClientRect();
      if (r.bottom < -80 || r.top > vh + 80) continue;
      const k = Math.min(1, dt * 7);
      p.px += (p.tpx - p.px) * k; p.py += (p.tpy - p.py) * k; p.glare += (p.tglare - p.glare) * k;
      let a: number;
      if (reduced) a = -8;
      else if (p.wave >= 0 && p.grid) {
        let g = grids.get(p.grid);
        if (g === undefined) { g = through(p.grid); grids.set(p.grid, g); }
        a = p.range * Math.sin(Math.PI * 2 * (g * 1.5 - p.wave * 0.13));
      } else a = clamp((through(p.el) - 0.5 - p.off) * 2.2, -1, 1) * p.range;
      const tiltY = reduced ? 0 : p.px * 14 + gx * 16, tiltX = reduced ? 0 : -p.py * 10 - gy * 10;
      const ry = a + tiltY, rx = (reduced ? 3 : -a * 0.1) + tiltX;
      let b = clamp((ry / (p.range + 14)) * 0.55 + 0.5);
      if (p.rare && !reduced) b = clamp(0.5 + 0.42 * Math.sin(t * 0.55) + p.px * 0.25);
      const lat = reduced ? 1 : 1 - sstep(2.5, 7, Math.abs(ry));
      const rim = clamp(Math.abs(ry) / (p.range + 10));
      const glare = reduced ? 0 : Math.max(p.glare, p.rare ? 0.35 : 0);
      const gxp = p.glare > 0.02 ? p.gx : 50 - ry * 1.6, gyp = p.glare > 0.02 ? p.gy : 30 + rx * 2;
      const key = `${ry.toFixed(2)}|${rx.toFixed(2)}|${b.toFixed(3)}|${glare.toFixed(2)}`;
      if (key === p.last) continue;
      p.last = key;
      const st = p.el.style;
      st.setProperty("--ry", ry.toFixed(2) + "deg");
      st.setProperty("--rx", rx.toFixed(2) + "deg");
      st.setProperty("--b", b.toFixed(3));
      st.setProperty("--lat", lat.toFixed(3));
      st.setProperty("--rim", rim.toFixed(3));
      st.setProperty("--glare", glare.toFixed(3));
      st.setProperty("--gx", gxp.toFixed(1) + "%");
      st.setProperty("--gy", gyp.toFixed(1) + "%");
    }
  });
}
