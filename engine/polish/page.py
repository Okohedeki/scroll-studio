"""Polish report for a built page: `studio inspect <project> --page`.

Headless Chromium (Playwright) loads dist/ from the engine's own preview server at a desktop size (1440x900) and a phone
size (390x844, 2x), with reduced motion on so the page holds still, and stops at each section's key positions: a block at
each screen of its height, a scene at each of its captions or steps. At every stop it takes the screenshot a visitor
would see, then the same page with every word hidden (and with the scrims hidden), and measures the pixels behind each
piece of text. What it reads out of the page and the pictures goes to page_metrics.py, which turns it into findings:

    text over a picture   busy-ness behind the words, WCAG contrast against the real pixels, a scrim doing the work
    type                  headline against body size, characters per line, headline lines on a phone
    pictures              blown up beyond their pixels, a face cut by the frame, text across a face
    layout                horizontal overflow, the hero's button below the fold, text over text

Nothing here needs a GPU or a network. Outputs: <project>/.build/inspect/page/report.json, the screenshots and one
contact sheet per size with the findings marked.
"""
from __future__ import annotations

import io
import json
import statistics
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import unquote

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import page_metrics as M
from .api import Nothing

# name -> (width, height, device pixel ratio, a phone: touch and mobile viewport)
VIEWPORTS = {"desktop": (1440, 900, 1.0, False), "phone": (390, 844, 2.0, True)}
MAX_STOPS = {"block": 4, "scene": 8}          # most screenshots taken of one section

STILL = ("*, *::before, *::after { transition: none !important; animation-duration: 0s !important; "
         "animation-delay: 0s !important; scroll-behavior: auto !important; caret-color: transparent !important }")
HIT = "* { pointer-events: auto !important }"            # while text is located, so a covered panel's words are not counted
NO_TEXT = ("*, *::before, *::after { color: transparent !important; text-shadow: none !important; "
           "-webkit-text-fill-color: transparent !important; -webkit-text-stroke: 0 !important; caret-color: transparent !important } "
           "svg text { fill: transparent !important }")
NO_SCRIM = "[data-pp-scrim] { visibility: hidden !important } .ss-caption::before { display: none !important }"

# ---------------------------------------------------------------- what the page tells us

PLAN_JS = """() => {
  const vh = innerHeight, docH = document.documentElement.scrollHeight;
  const top = el => el.getBoundingClientRect().top + scrollY;
  const kindOf = el => el.tagName === 'FOOTER' ? 'footer' : el.classList.contains('ss-scene') ? (el.dataset.scene || 'scene')
    : (([...el.classList].find(c => /^ss-(?!block|surface|panel)[a-z]+$/.test(c)) || 'ss-block').slice(3));
  const els = [...document.querySelectorAll('section.ss-block, section.ss-scene, footer')];
  const clamp = y => Math.max(0, Math.min(docH - vh, Math.round(y)));
  const spread = (ys, n) => ys.length <= n ? ys : Array.from({length: n}, (_, i) => ys[Math.round(i * (ys.length - 1) / (n - 1))]);
  return {docH, sections: els.map((el, i) => {
    const kind = kindOf(el), label = el.id || `${kind}-${i + 1}`;
    el.setAttribute('data-pp-section', label);
    const t = top(el), h = el.getBoundingClientRect().height, scene = el.classList.contains('ss-scene');
    let ys = [];
    if (scene) {
      const track = el.querySelector('.ss-track');
      el.querySelectorAll('.ss-caption').forEach(c => { if (track) { const th = track.getBoundingClientRect().height;
        ys.push(top(track) + ((+c.dataset.from + +c.dataset.to) / 2) * (th - vh)); } });
      el.querySelectorAll('.ss-step').forEach(s => { const r = (s.querySelector('.ss-card') || s).getBoundingClientRect();
        ys.push(r.top + scrollY + (r.height < 0.8 * vh ? r.height / 2 - vh / 2 : -0.12 * vh)); });      // the words, not the step's whole run
      ys = ys.length ? ys.sort((a, b) => a - b) : [t];
    } else if (kind === 'footer') ys = [t + h - vh];
    else for (let y = t; ys.length < 12 && (y === t || y < t + h - 0.25 * vh); y += vh) ys.push(y);
    return {label, kind, scene, top: t, height: h, ys: ys.map(clamp)};
  })};
}"""

COLLECT_JS = """() => {
  const vw = innerWidth, vh = innerHeight;
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  const rgba = css => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = css; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const cs = el => getComputedStyle(el);
  const opac = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(cs(e).opacity); return o; };
  const sel = el => el.id ? '#' + el.id : el.tagName.toLowerCase() + [...el.classList].filter(c => !/^ss-(in|on|off|reveal|ready)$/.test(c)).slice(0, 2).map(c => '.' + c).join('');
  const sectionOf = el => { const s = el.closest('[data-pp-section]'); return s ? s.getAttribute('data-pp-section') : el.closest('nav, header') ? 'nav' : 'page'; };
  document.querySelectorAll('[data-pp-scrim]').forEach(e => e.removeAttribute('data-pp-scrim'));

  // what is behind a point, top to bottom (elementsFromPoint, with every element hit-testable): scrims on the way down, then a
  // picture (over it) or an opaque surface (not over a picture), so a phone's screen or a card hides the photo behind it
  const behind = (root, x, y) => {
    const veils = [];
    for (const e of document.elementsFromPoint(x, y)) {
      if (root.contains(e)) continue;
      const s = cs(e), r = e.getBoundingClientRect(), tag = e.tagName;
      if (s.visibility === 'hidden' || opac(e) < 0.1) continue;
      if (s.position === 'fixed' && r.width >= vw * 0.98 && r.height >= vh * 0.98 && !/^(IMG|VIDEO)$/.test(tag) && !s.backgroundImage.includes('url(')) continue;
      if (/^(IMG|VIDEO|CANVAS)$/.test(tag) && r.width >= 48 && r.height >= 48) return {kind: tag.toLowerCase(), veils};
      if (s.backgroundImage.includes('url(')) return {kind: 'background', veils};
      const a = rgba(s.backgroundColor)[3], bare = !e.textContent.trim();
      if (bare && (s.backgroundImage.includes('gradient') || (a > 0.02 && a < 0.98))) { veils.push(e); continue; }
      if (a >= 0.98 || e === document.body || e === document.documentElement) return {kind: null, veils: []};
    }
    return {kind: null, veils: []};
  };

  // text, grouped by the block it sits in
  const roots = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode: n => /\\S/.test(n.nodeValue) &&
    !n.parentElement.closest('script, style, noscript, svg, template') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT});
  for (let n; (n = walker.nextNode());) {
    let r = n.parentElement;
    while (r.parentElement && cs(r).display.startsWith('inline') && !/^(A|BUTTON|LABEL)$/.test(r.tagName)) r = r.parentElement;
    (roots.get(r) || roots.set(r, []).get(r)).push(n);
  }
  const items = [];
  for (const [root, nodes] of roots) {
    const s = cs(root), o = opac(root);
    if (s.visibility === 'hidden' || o < 0.5 || !/[\\p{L}\\p{N}]/u.test(root.textContent)) continue;       // an icon glyph is not copy
    const fs = parseFloat(s.fontSize), words = [];
    for (const n of nodes) { const re = /\\S+/g; let m;
      while ((m = re.exec(n.nodeValue))) { const g = document.createRange(); g.setStart(n, m.index); g.setEnd(n, m.index + m[0].length);
        const rs = g.getClientRects(); if (!rs.length || rs[0].width < 1 || rs[0].height < 1) continue;
        words.push({x0: rs[0].left, y0: rs[0].top, x1: rs[0].right, y1: rs[0].bottom, n: m[0].length + 1}); } }
    if (!words.length) continue;
    const lines = [];
    for (const w of words) { const L = lines.find(l => Math.abs((l.y0 + l.y1) / 2 - (w.y0 + w.y1) / 2) < fs * 0.5);
      if (L) { L.x0 = Math.min(L.x0, w.x0); L.x1 = Math.max(L.x1, w.x1); L.y0 = Math.min(L.y0, w.y0); L.y1 = Math.max(L.y1, w.y1); L.n += w.n; }
      else lines.push({x0: w.x0, y0: w.y0, x1: w.x1, y1: w.y1, n: w.n}); }
    lines.sort((a, b) => a.y0 - b.y0);
    const seen = lines.filter(l => l.y0 >= -2 && l.y1 <= vh + 2 && l.x1 > 0 && l.x0 < vw);
    if (!seen.length) continue;
    const mid = seen[Math.floor(seen.length / 2)], hit = document.elementFromPoint((mid.x0 + mid.x1) / 2, (mid.y0 + mid.y1) / 2);
    if (hit && !root.contains(hit) && !hit.contains(root)) continue;            // covered by something else
    const rect = [Math.min(...seen.map(l => l.x0)), Math.min(...seen.map(l => l.y0)), Math.max(...seen.map(l => l.x1)), Math.max(...seen.map(l => l.y1))];
    const tag = root.tagName, cls = typeof root.className === 'string' ? root.className : '';
    const role = /^H[1-4]$/.test(tag) || /\\bss-(h1|h2|h3|display)\\b/.test(cls) ? 'headline'
      : (tag === 'A' && /btn/.test(cls)) || tag === 'BUTTON' ? 'cta'
      : /^(P|LI|BLOCKQUOTE|FIGCAPTION|DD)$/.test(tag) || /\\bss-(body|lede|fact)\\b/.test(cls) ? 'body' : 'label';
    const col = rgba(s.color), cxm = (rect[0] + rect[2]) / 2;
    const pts = [.1, .5, .9].map(f => [mid.x0 + (mid.x1 - mid.x0) * f, (mid.y0 + mid.y1) / 2]);
    const found = pts.map(pt => behind(root, pt[0], pt[1])), under = found.filter(f => f.kind), veils = new Set(under.flatMap(f => f.veils));
    veils.forEach(e => e.setAttribute('data-pp-scrim', '1'));
    items.push({text: nodes.map(n => n.nodeValue.trim()).join(' ').replace(/\\s+/g, ' ').slice(0, 160), sel: sel(root), role, size: fs,
      weight: parseInt(s.fontWeight) || 400, color: [col[0], col[1], col[2], col[3] * o], section: sectionOf(root),
      caption: !!root.closest('.ss-caption, .ss-step'), hero: !!root.closest('.ss-hero'),
      side: cxm < vw / 3 ? 'left' : cxm > vw * 2 / 3 ? 'right' : 'center', rect,
      seen: seen.map(l => [l.x0, l.y0, l.x1, l.y1]), nlines: lines.length, chars: lines.map(l => l.n - 1),
      over: [...new Set(under.map(f => f.kind))], veils: veils.size, device: !!root.closest('.ss-phone')});
  }

  // layout: the page wider than the screen, and the hero's first button at the top of the page
  const sw = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  let overflow = null;
  if (sw > vw + 1) {
    const cul = [];
    for (const el of document.body.querySelectorAll('*')) { const r = el.getBoundingClientRect();
      if (r.right <= vw + 2 || !r.width || !r.height || cs(el).visibility === 'hidden') continue;
      let clipped = false;
      for (let e = el.parentElement; e && e !== document.body; e = e.parentElement) if (cs(e).overflowX !== 'visible') { clipped = true; break; }
      if (!clipped) cul.push([r.right, sel(el) + ' in ' + sectionOf(el)]); }
    cul.sort((a, b) => b[0] - a[0]);
    overflow = {px: sw - vw, culprits: [...new Set(cul.map(c => c[1] + ' (reaches ' + Math.round(cul.find(d => d[1] === c[1])[0]) + ' px)'))].slice(0, 3),
                section: cul.length ? cul[0][1].split(' in ').pop() : 'page'};
  }
  const ctas = [];                           // each hero standing at the top of the screen: its first button against the fold
  for (const hero of document.querySelectorAll('[data-pp-section].ss-hero')) {
    if (Math.abs(hero.getBoundingClientRect().top) > 6) continue;
    const b = hero.querySelector('a.ss-btn, a[class*=btn], button');
    if (b) { const r = b.getBoundingClientRect();
      ctas.push({label: b.textContent.trim(), top: r.top, bottom: r.bottom, fold: vh, box: [r.left, r.top, r.right, r.bottom], section: hero.getAttribute('data-pp-section')}); }
  }
  return {items, overflow, ctas, veils: document.querySelectorAll('[data-pp-scrim]').length};
}"""

IMAGES_JS = """async () => {
  const out = [], opac = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  const pos = p => p.split(' ').map(v => v.endsWith('%') ? parseFloat(v) / 100 : 0.5);
  const load = url => new Promise(res => { const i = new Image(); i.onload = () => res([i.naturalWidth, i.naturalHeight]); i.onerror = () => res([0, 0]); i.src = url; });
  for (const el of document.body.querySelectorAll('*')) {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    if (r.width < 48 || r.height < 48 || s.visibility === 'hidden' || opac(el) < 0.1) continue;
    let url, nat, fit, at;
    if (el.tagName === 'IMG') { url = el.currentSrc; nat = [el.naturalWidth, el.naturalHeight]; fit = s.objectFit; at = pos(s.objectPosition); }
    else { const m = s.backgroundImage.match(/url\\(["']?([^"')]+)["']?\\)/); if (!m) continue;
      url = new URL(m[1], location.href).href; nat = await load(url); fit = s.backgroundSize === 'cover' ? 'cover' : s.backgroundSize === 'contain' ? 'contain' : 'none';
      at = pos(s.backgroundPosition); }
    if (!url || url.startsWith('data:') || /\\.svg(\\?|$)/i.test(url) || nat[0] < 8 || nat[1] < 8) continue;
    const sec = el.closest('[data-pp-section]');
    out.push({path: new URL(url).pathname, natural: nat, box: [r.width, r.height], fit, at, doc: [r.left + scrollX, r.top + scrollY],
              section: sec ? sec.getAttribute('data-pp-section') : 'page'});
  }
  return out;
}"""


# ---------------------------------------------------------------- the browser

def _chromium(p):
    try:
        return p.chromium.launch(args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--hide-scrollbars"])
    except Exception as e:
        raise Nothing("a page check needs Playwright's Chromium: run `playwright install chromium` "
                      f"({str(e).strip().splitlines()[0][:120]})")


def _settle(page, ms: int) -> None:
    page.wait_for_timeout(ms)
    page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def _shot(page) -> np.ndarray:
    return np.array(Image.open(io.BytesIO(page.screenshot())).convert("RGB"))


def _open(browser, base: str, viewport: str):
    """The page at one size, loaded, ready and still. Returns (context, page) or raises Nothing if it never gets ready."""
    w, h, dpr, phone = VIEWPORTS[viewport]
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, is_mobile=phone, has_touch=phone,
                              reduced_motion="reduce", locale="en-US", timezone_id="UTC")
    page = ctx.new_page()
    page.goto(f"{base}/index.html", wait_until="load")
    try:
        page.wait_for_function("document.documentElement.dataset.ssReady === '1'", timeout=45_000)
        page.wait_for_function("!document.getElementById('ss-loader') && (!document.documentElement.dataset.style || "
                               "document.documentElement.dataset.ssStyle === 'ready')", timeout=15_000)
    except Exception:
        ctx.close()
        raise Nothing(f"the page never became ready at {viewport} size (the runtime did not set data-ss-ready)")
    page.evaluate("document.fonts.ready")
    page.add_style_tag(content=STILL)
    # sections reveal as they come into view and lazy pictures load: read the page through once, then back to the top
    for _ in range(120):
        page.evaluate("scrollBy(0, innerHeight)")
        page.wait_for_timeout(40)
        if page.evaluate("scrollY + innerHeight >= document.documentElement.scrollHeight - 2"):
            break
    try:
        page.wait_for_function("[...document.images].every(i => i.complete)", timeout=10_000)
    except Exception:
        pass
    page.evaluate("scrollTo(0, 0)")
    _settle(page, 300)
    return ctx, page


def _stops(plan: dict, only: Optional[str]) -> list[dict]:
    """[{y, sections}] one per scroll position, in page order: where the page is photographed."""
    at: dict[int, list[str]] = {}
    for s in plan["sections"]:
        if only and s["label"] != only:
            continue
        ys = s["ys"]
        cap = MAX_STOPS["scene" if s["scene"] else "block"]
        if len(ys) > cap:
            ys = [ys[round(i * (len(ys) - 1) / (cap - 1))] for i in range(cap)]
        for y in ys:
            at.setdefault(y, []).append(s["label"])
    return [{"y": y, "sections": at[y]} for y in sorted(at)]


def _crop(img: np.ndarray, box, dpr: float) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = (int(round(v * dpr)) for v in box)
    return img[max(0, y0):min(h, max(y1, y0 + 1)), max(0, x0):min(w, max(x1, x0 + 1))]


_cascade = None


def detect_faces(rgb: np.ndarray) -> Optional[list[tuple[float, float, float, float]]]:
    """Faces found by OpenCV's bundled frontal-face cascade, as (x0, y0, x1, y1) in 0-1 of the picture, or None if this
    OpenCV has no cascade files. A cheap check: it finds upright faces looking at the camera, and misses the rest."""
    global _cascade
    import cv2
    if _cascade is None:
        path = Path(getattr(getattr(cv2, "data", None), "haarcascades", "")) / "haarcascade_frontalface_default.xml"
        _cascade = cv2.CascadeClassifier(str(path)) if path.exists() else False
    if not _cascade:
        return None
    h, w = rgb.shape[:2]
    k = min(1.0, 800 / max(w, 1))
    g = cv2.equalizeHist(cv2.cvtColor(cv2.resize(rgb, (max(1, int(w * k)), max(1, int(h * k)))), cv2.COLOR_RGB2GRAY))
    found = _cascade.detectMultiScale(g, scaleFactor=1.1, minNeighbors=7, minSize=(max(24, int(g.shape[1] * 0.05)),) * 2)
    gh, gw = g.shape
    return [(x / gw, y / gh, (x + fw) / gw, (y + fh) / gh) for x, y, fw, fh in found]


def _walk(page, plan: dict, stops: list[dict], viewport: str, out: Path, log: Callable[[str], None]) -> dict:
    """Photograph every stop and read the page at it. Returns {stops, items, text, overflow, cta}: each stop's
    screenshot path, every piece of text (and those over a picture with their measurements), and the layout facts."""
    w, h, dpr, _ = VIEWPORTS[viewport]
    items, text, overflow, ctas = [], [], [], []
    for n, stop in enumerate(stops):
        page.evaluate(f"scrollTo(0, {stop['y']})")
        _settle(page, 700 if any(s["scene"] and s["label"] in stop["sections"] for s in plan["sections"]) else 350)
        page.add_style_tag(content=HIT).evaluate("e => e.id = 'pp-hit'")
        facts = page.evaluate(COLLECT_JS)
        page.evaluate("document.getElementById('pp-hit').remove()")
        final = _shot(page)
        path = out / f"{viewport}-{n:02d}.jpg"
        Image.fromarray(final).save(path, quality=88)
        stop["path"] = path.name
        clean = raw = None
        if any(i["over"] for i in facts["items"]):
            tag = page.add_style_tag(content=NO_TEXT)
            _settle(page, 60)
            clean = _shot(page)
            if facts["veils"]:
                veil = page.add_style_tag(content=NO_SCRIM)
                _settle(page, 60)
                raw = _shot(page)
                veil.evaluate("e => e.remove()")
            tag.evaluate("e => e.remove()")
            _settle(page, 60)
        faces = detect_faces(clean) if clean is not None else None
        for it in facts["items"]:
            it["shot"] = n
            it["viewport"] = viewport
            if it["over"] and clean is not None:
                it["measure"] = _measure(it, clean, raw, dpr, faces, (w, h))
                text.append(it)
        items += facts["items"]
        if facts["overflow"]:
            overflow.append(dict(facts["overflow"], shot=n))
        ctas += [dict(c, shot=n) for c in facts["ctas"]]
        log(f"  {viewport} {n + 1}/{len(stops)}: {', '.join(stop['sections'])} ({len(facts['items'])} text blocks)")
    return {"stops": stops, "items": items, "text": text, "overflow": overflow, "cta": ctas}


def _measure(it: dict, clean: np.ndarray, raw: Optional[np.ndarray], dpr: float, faces, size) -> dict:
    """The picture behind one piece of text: busy-ness of its box, contrast against the pixels behind each line, the same
    with the scrims hidden, how busy each third of the shot is across its rows, and the faces its lines cover."""
    busy = M.busyness(_crop(clean, it["rect"], dpr))
    behind = np.concatenate([_crop(clean, b, dpr).reshape(-1, 3) for b in it["seen"]])
    r, g, b, a = it["color"]
    m = {"busy": busy["score"], "edge": busy["edge"], "contrast": M.text_contrast(behind, (r, g, b), a)}
    if raw is not None:
        behind_raw = np.concatenate([_crop(raw, bx, dpr).reshape(-1, 3) for bx in it["seen"]])
        rc = M.text_contrast(behind_raw, (r, g, b), a)
        rc["shift"] = round(abs(m["contrast"]["backdrop_lum"] - rc["backdrop_lum"]), 3)
        m["raw"] = rc
    rows = (int(it["rect"][1] * dpr), int(it["rect"][3] * dpr))
    m["calm"] = M.calmest_side(clean, rows)
    if faces:
        W, H = size
        m["faces"] = [f for f in faces if any(M.face_overlap((f[0] * W, f[1] * H, f[2] * W, f[3] * H), tuple(b)) >= 0.2 for b in it["seen"])]
    return m


# ---------------------------------------------------------------- findings

def _text_findings(text: list[dict]) -> list[dict]:
    out = []
    for it in text:
        m = it["measure"]
        out += M.text_findings({"text": it["text"], "role": it["role"], "size": it["size"], "weight": it["weight"],
                                "caption": it["caption"], "hero": it["hero"], "section": it["section"],
                                "viewport": it["viewport"], "shot": it["shot"], "box": it["rect"], "busy": m["busy"],
                                "contrast": m["contrast"], "raw": m.get("raw"), "calm": m["calm"], "side": it["side"]})
        if m.get("faces"):
            out.append(M.finding("warn", "text-over-face", it["section"], it["viewport"],
                                 f"{it['role']} \"{it['text'][:34]}\" sits across a face in the picture",
                                 "move the caption off the face with `place: left` or `right`, or regenerate the shot with "
                                 "the subject on the other side", it["shot"], it["rect"]))
    return out


def _type_facts(items: list[dict]) -> dict:
    """{(viewport, section): {headline, body, bodies, headlines}} from every text block seen, once per block."""
    seen, out = set(), {}
    for it in items:
        if it["section"] in ("nav", "page") or it.get("device"):      # a phone mock's screen is not the page's type
            continue
        key = (it["viewport"], it["section"], it["text"][:60])
        if key in seen:
            continue
        seen.add(key)
        f = out.setdefault((it["viewport"], it["section"]), {"headline": [], "body": [], "bodies": [], "headlines": []})
        entry = {"text": it["text"], "lines": it["chars"], "nlines": it["nlines"], "shot": it["shot"], "box": it["rect"]}
        if it["role"] == "headline":
            f["headline"].append(it["size"])
            f["headlines"].append(entry)
        elif it["role"] == "body":
            f["body"].append(it["size"])
            f["bodies"].append(entry)
    return out


def _ink(line: list[float]) -> tuple[float, float, float, float]:
    """A line's box without its leading: letters fill the middle 60% of the line box, so two tight lines do not overlap."""
    pad = (line[3] - line[1]) * 0.2
    return (line[0], line[1] + pad, line[2], line[3] - pad)


def _overlaps(items: list[dict]) -> list[tuple[str, str, dict]]:
    """(viewport, section, {a, b, share, box}) for each pair of text blocks, seen at the same stop, whose lines cross."""
    found, seen = [], set()
    by_shot: dict[tuple, list[dict]] = {}
    for it in items:
        by_shot.setdefault((it["viewport"], it["shot"]), []).append(it)
    for (vp, _), group in by_shot.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if "nav" in (a["section"], b["section"]):       # a fixed nav always crosses what scrolls under it
                    continue
                share = max((M.overlap(_ink(la), _ink(lb)) for la in a["seen"] for lb in b["seen"]), default=0.0)
                key = (vp, a["text"][:40], b["text"][:40])
                if share >= M.OVERLAP_MIN and key not in seen:
                    seen.add(key)
                    box = [min(a["rect"][0], b["rect"][0]), min(a["rect"][1], b["rect"][1]),
                           max(a["rect"][2], b["rect"][2]), max(a["rect"][3], b["rect"][3])]
                    found.append((vp, a["section"] if a["section"] == b["section"] else a["section"],
                                  {"a": a["text"], "b": b["text"], "share": share, "box": box, "shot": a["shot"]}))
    return found


def _image_facts(imgs: list[dict], stops: list[dict], viewport: str, dist: Path, faces_cache: dict) -> list[dict]:
    h, dpr = VIEWPORTS[viewport][1], VIEWPORTS[viewport][2]
    out = []
    for im in imgs:
        cy = im["doc"][1] + im["box"][1] / 2
        n = next((i for i, s in enumerate(stops) if s["y"] <= cy <= s["y"] + h), None)
        rect = ([im["doc"][0], im["doc"][1] - stops[n]["y"], im["doc"][0] + im["box"][0], im["doc"][1] - stops[n]["y"] + im["box"][1]]
                if n is not None else None)
        file = dist / unquote(im["path"]).lstrip("/")
        face = None
        if file.exists():
            if file not in faces_cache:
                try:
                    faces_cache[file] = detect_faces(np.array(Image.open(file).convert("RGB")))
                except Exception:
                    faces_cache[file] = None
            window = M.crop_window(tuple(im["natural"]), tuple(im["box"]), im["fit"], tuple(im["at"]))
            shares = [M.face_in_frame(f, window) for f in faces_cache[file] or []]
            face = min((s for s in shares if s > 0), default=None)
        out.append({"src": file.name, "section": im["section"], "viewport": viewport, "natural": im["natural"], "box": im["box"],
                    "dpr": dpr, "fit": im["fit"], "shot": n, "rect": rect, "face": face,
                    "upscale": M.upscale(tuple(im["natural"]), tuple(im["box"]), dpr, im["fit"])})
    return out


def _dedupe(findings: list[dict]) -> list[dict]:
    """One finding per (check, viewport, section, what is named): the same paragraph seen at two stops, or a nav link seen
    over every section, is reported once, at its worst."""
    best: dict[tuple, dict] = {}
    for f in findings:
        key = (f["check"], f["viewport"], f["section"], f["subject"])
        if key not in best or (f["severity"] == "fail" and best[key]["severity"] != "fail"):
            best[key] = f
    return list(best.values())


# ---------------------------------------------------------------- the sheet

COLORS = {"fail": (214, 40, 40), "warn": (232, 150, 20), "clean": (40, 160, 90)}


def _sheet(out: Path, viewport: str, stops: list[dict], findings: list[dict]) -> Optional[Path]:
    """One contact sheet for a size: every screenshot, labelled with its section, a coloured frame by its worst finding
    and a box on each finding (red fails, amber warns)."""
    shots = [(n, s) for n, s in enumerate(stops)]
    if not shots:
        return None
    w, h, dpr, _ = VIEWPORTS[viewport]
    tw = 520 if viewport == "desktop" else 230
    cols = 3 if viewport == "desktop" else 6
    th = round(tw * h / w)
    bar = 30
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + bar + 8) + 8), (24, 24, 24))
    try:
        font = ImageFont.load_default(size=13)
    except TypeError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    k = tw / w
    for i, (n, stop) in enumerate(shots):
        x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + bar + 8)
        mine = [f for f in findings if f["viewport"] == viewport and f["shot"] == n]
        worst = M.verdict(mine)
        im = Image.open(out / stop["path"]).convert("RGB").resize((tw, th), Image.LANCZOS)
        sheet.paste(im, (x, y + bar))
        d.rectangle([x - 2, y - 2, x + tw + 1, y + bar + th + 1], outline=COLORS[worst], width=3)
        fails, warns = sum(f["severity"] == "fail" for f in mine), sum(f["severity"] == "warn" for f in mine)
        d.text((x + 4, y + 5), f"{n + 1}  {', '.join(stop['sections'])[:28]}", fill=(235, 235, 235), font=font)
        if mine:
            tag = f"{fails} fail  {warns} warn" if viewport == "desktop" else f"{fails}f {warns}w"
            d.text((x + tw - 4 - d.textlength(tag, font=font), y + 5), tag, fill=COLORS[worst], font=font)
        for f in mine:
            if f["box"]:
                b = [x + f["box"][0] * k, y + bar + f["box"][1] * k, x + f["box"][2] * k, y + bar + f["box"][3] * k]
                d.rectangle(b, outline=COLORS[f["severity"]], width=2)
    path = out / f"sheet-{viewport}.jpg"
    sheet.save(path, quality=88)
    return path


# ---------------------------------------------------------------- the report

def inspect_page(project, only: Optional[str] = None, log: Callable[[str], None] = print) -> dict:
    """Check the built page of a project. Raises Nothing if there is nothing built or no Chromium."""
    from playwright.sync_api import sync_playwright
    from ..serve import serve
    dist = Path(project.dist)
    if not (dist / "index.html").exists():
        raise Nothing("not built yet: run `studio build` first")
    out = Path(project.build) / "inspect" / "page"
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("*.jpg")) + list(out.glob("*.json")):
        old.unlink()
    httpd = serve(dist, 0, background=True)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    t0 = time.time()
    findings, sections, walked, images, faces_cache = [], {}, {}, [], {}
    try:
        with sync_playwright() as p:
            browser = _chromium(p)
            try:
                for viewport in VIEWPORTS:
                    ctx, page = _open(browser, base, viewport)
                    try:
                        plan = page.evaluate(PLAN_JS)
                        if only and not any(s["label"] == only for s in plan["sections"]):
                            raise Nothing(f"no section '{only}' on the page (sections: "
                                          f"{', '.join(s['label'] for s in plan['sections'])})")
                        for s in plan["sections"]:
                            sections.setdefault(s["label"], {"id": s["label"], "kind": s["kind"]})
                        stops = _stops(plan, only)
                        # pictures are measured before the walk: sticky panels sit at their own place on an unscrolled page
                        images += _image_facts(page.evaluate(IMAGES_JS), stops, viewport, dist, faces_cache)
                        walked[viewport] = _walk(page, plan, stops, viewport, out, log)
                    finally:
                        ctx.close()
            finally:
                browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    for viewport, wk in walked.items():
        findings += _text_findings(wk["text"])
        for (vp, section), f in _type_facts(wk["items"]).items():
            body = statistics.median(f["body"]) if f["body"] else None
            head = max(f["headline"]) if f["headline"] else None
            sections[section].setdefault(viewport, {}).update(headline_px=head, body_px=body,
                                                              ratio=M.type_ratio(head, body) if head and body else None)
            findings += M.type_findings(section, vp, head, body, f["bodies"], f["headlines"])
        for o in wk["overflow"]:
            findings += M.layout_findings(o["section"] if o["section"] in sections else "page", viewport, o["shot"], o, None, [])
        for c in wk["cta"]:
            findings += M.layout_findings(c["section"], viewport, c["shot"], None, c, [])
        for vp, section, o in _overlaps(wk["items"]):
            findings += M.layout_findings(section, vp, o["shot"], None, None, [o])
    for im in images:
        findings += M.image_findings(im)
    findings = _dedupe([f for f in findings if not only or f["section"] == only])
    order = {s: i for i, s in enumerate(list(sections) + ["nav", "page"])}
    findings.sort(key=lambda f: (f["severity"] != "fail", order.get(f["section"], 99), f["viewport"], f["check"]))
    sheets = {vp: _sheet(out, vp, wk["stops"], findings) for vp, wk in walked.items()}
    for sec in sections.values():
        mine = [f for f in findings if f["section"] == sec["id"]]
        sec["fails"], sec["warns"] = sum(f["severity"] == "fail" for f in mine), sum(f["severity"] == "warn" for f in mine)
    skipped = []
    if detect_faces(np.zeros((64, 64, 3), np.uint8)) is None:
        skipped.append("faces: this OpenCV has no face cascade, so face crops and text over faces were not checked")
    skipped.append("pictures drawn by the page's scripts (parallax photos, films, 3D scenes) have no size to check: only <img> "
                   "elements and CSS background images are measured for upscaling and cropping")
    skipped.append("faces: only upright faces looking at the camera are found; the cheap detector misses profiles and tilted heads")
    report = {"project": Path(project.root).name, "generated": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - t0, 1),
              "viewports": {k: {"width": v[0], "height": v[1], "dpr": v[2]} for k, v in VIEWPORTS.items()},
              "summary": {"verdict": M.verdict(findings), "fails": sum(f["severity"] == "fail" for f in findings),
                          "warns": sum(f["severity"] == "warn" for f in findings), "sections": len(sections),
                          "stops": {vp: len(wk["stops"]) for vp, wk in walked.items()}},
              "sections": list(sections.values()), "findings": findings,
              "text_over_pictures": [{"section": it["section"], "viewport": it["viewport"], "role": it["role"],
                                      "text": it["text"][:80], "size": it["size"], "busy": it["measure"]["busy"],
                                      "contrast": it["measure"]["contrast"], "without_scrim": it["measure"].get("raw"),
                                      "shot": it["shot"]} for wk in walked.values() for it in wk["text"]],
              "pictures": [{k: v for k, v in im.items() if k not in ("rect", "shot")} for im in images],
              "stops": {vp: [{"n": i + 1, "y": s["y"], "sections": s["sections"], "file": s["path"]} for i, s in enumerate(wk["stops"])]
                        for vp, wk in walked.items()},
              "sheets": {vp: p.name for vp, p in sheets.items() if p}, "folder": str(out), "skipped": skipped}
    (out / "report.json").write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    return report


def table(r: dict, width: int = 100) -> str:
    """The report as text: a row per section (fails and warns at each size), then every finding with its fix."""
    import textwrap
    s = r["summary"]
    lines = [f"Page polish: {r['project']}: {s['verdict']}: {s['fails']} fail, {s['warns']} warn "
             f"({s['sections']} sections, {r['seconds']:g} s)", ""]
    lines.append(f"{'section':<26}{'desktop':>14}{'phone':>14}")
    for sec in r["sections"]:
        cells = []
        for vp in ("desktop", "phone"):
            mine = [f for f in r["findings"] if f["section"] == sec["id"] and f["viewport"] == vp]
            fails, warns = sum(f["severity"] == "fail" for f in mine), sum(f["severity"] == "warn" for f in mine)
            cells.append(f"{fails} fail {warns} warn" if mine else "clean")
        lines.append(f"{sec['id'][:25]:<26}{cells[0]:>14}{cells[1]:>14}")
    for f in r["findings"]:
        if f["section"] not in {x["id"] for x in r["sections"]}:
            lines.append(f"{f['section']:<26}{'':>14}{'':>14}  ({f['viewport']}: {f['check']})")
    if r["findings"]:
        lines.append("")
    for f in r["findings"]:
        head = f"{f['severity'].upper():<5} {f['section']} | {f['viewport']} | {f['check']}"
        lines += [head] + textwrap.wrap(f["what"], width, initial_indent="      ", subsequent_indent="      ")
        lines += textwrap.wrap("fix: " + f["fix"], width, initial_indent="      ", subsequent_indent="           ")
    lines += ["", f"report: {Path(r['folder']) / 'report.json'}"] + [f"sheet:  {Path(r['folder']) / n}" for n in r["sheets"].values()]
    lines += ["not checked: " + x for x in r["skipped"]]
    return "\n".join(lines)
