"""What the render tests share: building the kitchen-sink site in every look, loading a look in Chromium, the checks run
on a loaded page (health, accessibility).

A *look* is one way the page can be dressed: `style-<name>` for each of the 32 styles (engine/styles/),
`preset-<name>` for each of the 10 theme presets (engine/themes.yaml, the default look) and `brand-<name>` for a few styles
wearing a brand (theme.from) that is not their own. Every look is built by the
engine's own compiler into one folder, served by the engine's own server, and loaded at two viewports.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from engine.compile import themes
import kitchen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AXE_JS = ROOT / "node_modules" / "axe-core" / "axe.min.js"
ALLOW = HERE / "axe-allow.yaml"

# Styles that draw colours in their runtime (canvas, SVG, WebGL) or their templates, wearing a brand (issue #125): a light
# brand on two light styles, a dark one on three dark styles (a style that requires a room keeps it). They are loaded and
# checked like every other look, with the brand's colours in everything the style draws, and must still run clean and pass
# axe; test_a_style_wears_the_brand_it_is_given checks the page carries the brand's palette for the runtime to read.
BRANDS = {
    "light": {"mode": "light", "colors": {"bg": "#fbf7ef", "bg2": "#f1ede4", "ink": "#1d2a24", "accent": "#0b6e4f",
                                          "accent2": "#f2a541", "accent_ink": "#ffffff"},
              "fonts": {"display": "Fraunces", "body": "Inter"}, "radius": "10px"},
    "dark": {"mode": "dark", "colors": {"bg": "#0d1117", "bg2": "#161b22", "ink": "#e6edf3", "accent": "#2ea043",
                                        "accent2": "#a371f7", "accent_ink": "#04130a"},
             "fonts": {"display": "Sora", "body": "Manrope"}, "radius": "12px"},
}
BRAND_LOOKS = {"bauhaus": "light", "zoetrope": "light", "neon-glow": "dark", "wireframe-3d": "dark", "pixel-art": "dark"}
LOOKS = ([f"style-{n}" for n in sorted(themes.styles())] + [f"preset-{n}" for n in sorted(themes.presets())]
         + [f"brand-{n}" for n in sorted(BRAND_LOOKS)])
VIEWPORTS = {"desktop": (1280, 800), "phone": (390, 844)}
POSITIONS = ("top", "mid", "end")       # where overflow and accessibility are checked: top, half way down, bottom


# Math.random is seeded and the date starts at a fixed minute, so a style that scatters things (particles, grain, stars) or
# shows a clock (the ascii-art status bar) draws the same way each run; time still passes
SEED_RANDOM = """(() => {
  let s = 0x2545F491; Math.random = () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 1e9) / 1e9; };
  const T0 = Date.UTC(2026, 0, 15, 12, 0, 5), Real = Date, t = () => T0 + performance.now();
  const Fake = new Proxy(Real, { construct: (R, a) => a.length ? new R(...a) : new R(t()), apply: () => new Real(t()).toString(),
                                 get: (R, k) => k === 'now' ? t : R[k] });
  globalThis.Date = Fake;
})();"""


def own_looks(look: str) -> tuple[str, ...]:
    """The looks whose recorded problems a look has: its own, and for a style wearing a brand, the style's (a problem in the
    style's markup is the same problem in any colours)."""
    kind, name = look.split("-", 1)
    return (look, f"style-{name}") if kind == "brand" else (look,)


def spec_for(look: str) -> dict:
    kind, name = look.split("-", 1)
    theme = {"style": name} if kind == "style" else {"style": name, "from": BRANDS[BRAND_LOOKS[name]]} if kind == "brand" else {"preset": name}
    return kitchen.spec(theme)


def build(root: Path, look: str) -> None:
    """The kitchen-sink site in one look: root/looks/<look>/ (the runtime is shared, at root/runtime/). Built on first
    use, so running one look builds one look."""
    from engine.compile.compiler import build_site
    from engine.config import STATIC
    from engine.project import Project
    if not (root / "runtime").exists():
        shutil.copytree(STATIC / "runtime", root / "runtime")
    proj = root / "projects" / look
    proj.mkdir(parents=True)
    (proj / "site.yaml").write_text(yaml.safe_dump(spec_for(look), sort_keys=False, allow_unicode=True), encoding="utf-8")
    notes: list[str] = []
    build_site(Project(proj), log=notes.append, out=root / "looks" / look, runtime_href="../../runtime/", link_base="../../")
    # fonts are self-hosted at build time (engine/compile/fonts.py); a build that fell back to linking Google Fonts would
    # render in whatever the machine has, and every screenshot would differ
    assert (root / "looks" / look / "fonts" / "fonts.css").exists(),         f"{look}: the fonts were not downloaded (is the network up?): {[n for n in notes if 'fonts' in n]}"


# ---------------------------------------------------------------- loading a look

@dataclass
class Run:
    """What one load of one look at one viewport showed."""
    look: str
    viewport: str
    reduced: bool
    errors: list[str] = field(default_factory=list)      # console errors, page errors, failed requests
    ready: bool = False
    h1: int = -1
    overflow: list[str] = field(default_factory=list)    # horizontal overflow, measured at each stop
    missing: list[str] = field(default_factory=list)     # spec text that is not on the page
    axe: list[dict] = field(default_factory=list)        # serious / critical violations, merged over the stops
    skin: dict[str, str] = field(default_factory=dict)   # --skin-<role> on the page: what the style's runtime reads of a brand

    @property
    def label(self) -> str:
        return f"{self.look} at {self.viewport}, {'reduced motion' if self.reduced else 'with motion'}"


def _overflow(page, width: int) -> Optional[int]:
    """How far the page is wider than the viewport, or None. innerWidth is not used alone: with a layout wider than the
    screen it grows with the content."""
    wide = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
    return wide - width if wide > width + 1 else None


def _settle(page, ms: int = 250) -> None:
    page.wait_for_timeout(ms)
    page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def _squash(s: str) -> str:
    """Text with no whitespace at all: a style may set lines as blocks with nothing between them in the markup
    ("holds" + "everything"), which reads fine and is not the page's fault."""
    return re.sub(r"\s+", "", kitchen.norm(s))


def _page_text(page) -> str:
    return _squash(page.evaluate("document.body.textContent"))


def _axe(page) -> list[dict]:
    """axe-core on the page as it stands: serious and critical violations, each node with its selector, its ancestry
    (`path`, outermost first, what the allowlist matches), its markup and what axe measured (a colour-contrast node says
    which colours and what ratio)."""
    res = page.evaluate("""axe.run(document, {resultTypes: ['violations'], elementRef: true}).then(r => r.violations.map(v => ({
        id: v.id, impact: v.impact, help: v.help,
        nodes: v.nodes.map(n => { const d = (n.any[0] || {}).data || {}; const path = [];
          for (let e = n.element; e && e.nodeType === 1 && path.length < 8; e = e.parentElement)
            path.unshift(e.tagName.toLowerCase() + [...e.classList].map(c => '.' + c).join(''));
          return {target: n.target.join(' '), path: path.join(' > '), html: n.html.slice(0, 140),
                  data: d.contrastRatio ? `${d.contrastRatio}:1 ${d.fgColor} on ${d.bgColor}` : ''}; })})))""")
    return [v for v in res if v["impact"] in ("serious", "critical")]


def load(browser, base: str, look: str, viewport: str, reduced: bool) -> Run:
    """Open the look, wait for the runtime to say it is ready, and take its measurements. With motion the page is also
    scrolled through (the style's scroll code runs); with reduced motion it stops at each position for the checks
    and the accessibility scan, so nothing is mid-fade."""
    w, h = VIEWPORTS[viewport]
    run = Run(look, viewport, reduced)
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, has_touch=viewport == "phone",
                              reduced_motion="reduce" if reduced else "no-preference", locale="en-US", timezone_id="UTC")
    try:
        page = ctx.new_page()
        page.add_init_script(SEED_RANDOM)
        page.on("console", lambda m: run.errors.append(f"console: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: run.errors.append(f"page error: {e}"))
        page.on("requestfailed", lambda r: run.errors.append(f"request failed: {r.url}"))
        page.goto(f"{base}/looks/{look}/index.html", wait_until="load")
        try:
            page.wait_for_function("document.documentElement.dataset.ssReady === '1'", timeout=45_000)
            run.ready = True
        except Exception:
            return run
        # the loader fades out after ready, and a style's own module may still be starting up
        page.wait_for_function("!document.getElementById('ss-loader') && (!document.documentElement.dataset.style || "
                               "document.documentElement.dataset.ssStyle === 'ready')", timeout=15_000)
        page.evaluate("document.fonts.ready")
        run.skin = page.evaluate("""Object.fromEntries(['bg', 'bg2', 'ink', 'ink2', 'ink3', 'line', 'accent', 'accent2', 'accent-text', 'accent-ink']
            .map(r => [r, getComputedStyle(document.documentElement).getPropertyValue('--skin-' + r).trim()]).filter(([, v]) => v))""")
        _settle(page, 400)
        if reduced:
            # reveals are CSS transitions: with none, a section that has come into view is in its resting state at once
            page.add_style_tag(content="*, *::before, *::after { transition: none !important; }")
        else:
            _scroll_through(page, run, h)
        run.h1 = page.evaluate("document.querySelectorAll('h1').length")
        have = _page_text(page)
        run.missing = [t for t in kitchen.words(numbers=reduced) if _squash(t) not in have]
        if reduced:
            _read_through(page)
            page.add_script_tag(path=str(AXE_JS))
            seen: dict[tuple, dict] = {}
            for pos in POSITIONS:
                _go(page, pos)
                if (o := _overflow(page, w)) is not None:
                    run.overflow.append(f"{pos}: {o}px wider than the {w}px viewport")
                for v in _axe(page):
                    seen.setdefault(v["id"], dict(v, nodes=[]))["nodes"].extend(v["nodes"])
            run.axe = list(seen.values())
    finally:
        ctx.close()
    return run


def _read_through(page) -> None:
    """Scroll the page top to bottom a screen at a time and back: sections reveal as they come into view, and one that has
    not been reached is still invisible (axe would measure it at opacity 0)."""
    for _ in range(80):
        page.evaluate("scrollBy(0, innerHeight)")
        page.wait_for_timeout(40)
        if page.evaluate("scrollY + innerHeight >= document.documentElement.scrollHeight - 2"):
            break
    page.evaluate("scrollTo(0, 0)")
    _settle(page)


def _go(page, pos: str) -> None:
    page.evaluate("""(pos) => { const max = document.documentElement.scrollHeight - innerHeight;
                      scrollTo(0, pos === 'top' ? 0 : pos === 'mid' ? Math.round(max / 2) : max); }""", pos)
    _settle(page)


def _scroll_through(page, run: Run, height: int) -> None:
    """Wheel the whole page down in about a dozen big steps (smooth-scroll and the style's scroll handlers run as they do
    for a reader), measuring overflow on the way, then back to the top."""
    w = page.viewport_size["width"]
    page.mouse.move(w / 2, height / 2)
    step = max(height * 1.5, page.evaluate("document.documentElement.scrollHeight") / 12)
    for _ in range(30):
        page.mouse.wheel(0, step)
        page.wait_for_timeout(100)
        y, bottom = page.evaluate("[scrollY, scrollY + innerHeight >= document.documentElement.scrollHeight - 2]")
        if _overflow(page, w) is not None:
            page.wait_for_timeout(500)                   # an element mid-flight is not overflow: it must stay out
            if (o := _overflow(page, w)) is not None:
                run.overflow.append(f"scrolling, at y={round(y)}: {o}px wider than the {w}px viewport")
                break
        if bottom:
            break
    page.evaluate("scrollTo(0, 0)")
    _settle(page)


# ---------------------------------------------------------------- accessibility allowlist

def allowed() -> list[dict]:
    """tests/render/axe-allow.yaml: [{rule, look, selector, reason}], the findings known and accepted. `look` is a look
    name or `*` (default; a style's entries also hold for that style wearing a brand); `selector` is a regex searched in the node's ancestry (default: any node)."""
    return yaml.safe_load(ALLOW.read_text(encoding="utf-8")) or [] if ALLOW.exists() else []


def unexpected(run: Run) -> list[dict]:
    """The run's violations with the allowlisted nodes taken out (a violation with no nodes left is dropped)."""
    rules = [a for a in allowed() if a.get("look", "*") in ("*", *own_looks(run.look))]
    out = []
    for v in run.axe:
        left = [n for n in v["nodes"] if not any(a["rule"] == v["id"] and re.search(a.get("selector", ""), n["path"]) for a in rules)]
        if left:
            out.append(dict(v, nodes=left))
    return out


def describe(v: dict, limit: int = 3) -> str:
    where = "; ".join(f"{n['path'][-90:]}  {n['html']}  {n.get('data', '')}" for n in v["nodes"][:limit])
    return f"{v['id']} ({v['impact']}, {len(v['nodes'])} nodes): {v['help']}: {where}"


# ---------------------------------------------------------------- known problems

KNOWN = HERE / "known-issues.yaml"
CHECKS = ("ready", "errors", "h1", "missing", "overflow")


def problems(run: Run) -> dict[str, str]:
    """check -> what is wrong, for a run of a look (an empty dict is a clean page)."""
    if not run.ready:
        return {"ready": "the page never set data-ss-ready"}
    out = {}
    if run.errors:
        out["errors"] = f"console/page errors: {run.errors[:3]}"
    if run.h1 != 1:
        out["h1"] = f"{run.h1} <h1> after the JavaScript ran (needs exactly one)"
    if run.missing:
        out["missing"] = f"spec text missing from the page: {run.missing[:8]}"
    if run.overflow:
        out["overflow"] = f"horizontal overflow: {run.overflow[:3]}"
    return out


def known(run: Run) -> dict[str, str]:
    """check -> reason, the problems tests/render/known-issues.yaml accepts for this run: [{look, check, viewport?, motion?,
    reason}] (viewport desktop|phone, motion with|reduced; omitted = both). Those tests are marked xfail instead of failing,
    so CI is green with a bug on record and red for a new one."""
    entries = yaml.safe_load(KNOWN.read_text(encoding="utf-8")) if KNOWN.exists() else None
    return {e["check"]: e["reason"] for e in entries or []
            if e["look"] in own_looks(run.look) and e.get("viewport", run.viewport) == run.viewport
            and e.get("motion", "reduced" if run.reduced else "with") == ("reduced" if run.reduced else "with")}
