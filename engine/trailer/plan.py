"""The cut: which shots, from which of the site's renders, for how long, with which words.

A plan is a list of `Shot`s on a beat grid. Shots come from what `studio build` already rendered (a film's take,
beats or video; scroll recordings of other sections; product stills when `site.product` exists), so a trailer costs
almost nothing extra. `derive()` writes the default cut for `trailer: {}`; `explicit()` resolves `trailer.shots`.
"""
from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..project import BuildError, Project, probe
from ..spec import FilmScene, Site, Trailer, is_scene

ALLOWED = re.compile(r"&lt;(/?)(em|b|i|br|strong)\s*/?&gt;")


def rich(text: Optional[str]) -> str:
    """Copy as safe HTML: everything escaped except <em>, <b>, <i>, <strong>, <br> (as on the site)."""
    if not text:
        return ""
    return ALLOWED.sub(lambda m: f"<{m.group(1)}{m.group(2)}>", html.escape(str(text), quote=False))


def plain(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def read_beats(text: Optional[str], beat: float, floor: int = 4) -> int:
    """Beats a caption needs on screen: half a second to land, a third of a second a word, rounded up to whole
    pairs of beats, never under `floor`."""
    words = len(plain(text).split())
    if not words:
        return floor
    need = 0.9 + 0.32 * words
    n = math.ceil(need / beat)
    return max(floor, n + (n % 2))


@dataclass
class Shot:
    kind: str                       # film | record | still | card | end
    beats: int
    role: str = "shot"              # hook | middle | reveal | features | end | shot (explicit)
    label: str = ""
    src: Optional[Path] = None      # film / still: the media file
    t0: float = 0.0                 # film: first second used
    speed: float = 1.0
    hold: bool = False              # film: freeze the frame at t0
    caption: str = ""               # safe HTML
    kicker: str = ""
    callouts: list[str] = field(default_factory=list)
    zoom: Optional[tuple[float, float]] = None
    focus: Optional[tuple[float, float]] = None
    section: Optional[str] = None
    track: Optional[str] = None     # film section id whose take has a product track
    span: tuple[float, float] = (0.0, 1.0)   # record: part of the section's scroll
    text: str = ""                  # card: the headline

    def key(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "src"}
        d["src"] = str(self.src) if self.src else None
        return d


# ---------------------------------------------------------------- films the site already rendered

@dataclass
class Film:
    sec: FilmScene
    src: Path
    dur: float
    fps: float
    spans: dict[str, tuple[float, float]]    # beat id -> seconds

    @property
    def has_product(self) -> bool:
        return bool(self.sec.take and self.sec.take.product)

    def step_range(self, i: int) -> tuple[float, float]:
        """Seconds of the film under step i, as the site shows it."""
        st = self.sec.steps[i]
        if st.at is not None:
            return st.at[0] * self.dur, st.at[1] * self.dur
        pin = (st.state or {}).get("beat")
        if pin is not None:
            if pin not in self.spans:
                raise BuildError(f"trailer: step '{plain(st.title)}' is pinned to beat {pin}, which is not in the film")
            a, b = self.spans[pin]
            part = (st.state or {}).get("part")
            if part:
                a, b = a + (b - a) * float(part[0]), a + (b - a) * float(part[1])
            pad = (b - a) * 0.1      # as film.beats_film pins its captions
            return a + pad, b - pad * 0.6
        n = len(self.sec.steps)
        return i / n * self.dur, (i + 1) / n * self.dur


def film_source(project: Project, sec: FilmScene) -> Optional[Path]:
    """The best finished footage of a film section: the take with its product composited, the restored or joined
    beats, the generated film, or the scroll encode as a last resort. None if it was never built."""
    if sec.video:
        p = project.path(sec.video)
        return p if p.exists() else None
    gen = project.build / sec.id / "gen"
    if sec.take:
        names = ["take.mp4", "gen_sr.mp4", "gen_up.mp4", "gen.mp4"] if sec.take.product else ["gen_sr.mp4", "gen_up.mp4", "gen.mp4"]
    elif sec.beats:
        names = (["gen_sr.mp4"] if sec.beat_restore else []) + ["beats.mp4"]
    else:
        names = ["gen_sr.mp4", "gen_up.mp4", "gen.mp4"]
    for n in names:
        if (gen / n).exists():
            return gen / n
    web = project.build / sec.id / "web" / "film.mp4"
    return web if web.exists() else None


def load_film(project: Project, sec: FilmScene) -> Optional[Film]:
    src = film_source(project, sec)
    if src is None:
        return None
    info = probe(src)
    dur = float(info.get("duration") or 0)
    num, _, den = str(info.get("r_frame_rate", "24/1")).partition("/")
    fps = float(num) / float(den or 1)
    spans: dict[str, tuple[float, float]] = {}
    if sec.beats:
        durs = []
        for b in sec.beats:
            clip = project.build / sec.id / "beats" / b.id / "clip.mp4"
            durs.append(float(probe(clip)["duration"]) if clip.exists() else b.seconds - b.trim)
        fade = min(sec.beat_fade, *(d / 3 for d in durs)) if len(durs) > 1 else 0
        total = sum(durs) - fade * (len(durs) - 1)
        k, t = dur / total if total else 1.0, 0.0     # scale to the footage actually on disk
        for b, d in zip(sec.beats, durs):
            spans[b.id] = (t * k, (t + d) * k)
            t += d - fade
    return Film(sec, src, dur, fps, spans)


# ---------------------------------------------------------------- copy the site already has

def callout_lines(site: Site) -> tuple[list[str], str]:
    """Short feature lines for the callouts and a kicker for them: a product block's tags, else a features block's
    titles, else the stats."""
    for s in site.sections:
        if s.type == "product" and s.tags:
            return [plain(t) for t in s.tags[:4]], plain(s.kicker or s.title)
    for s in site.sections:
        if s.type == "features" and s.items:
            return [plain(i.title) for i in s.items[:4]], plain(s.kicker or "")
    for s in site.sections:
        if s.type == "stats" and s.items:
            return [plain(f"{i.value}{(' ' + i.unit) if i.unit else ''} {i.label}") for i in s.items[:4] if i.value], ""
    return [], ""


def section_headline(sec) -> tuple[str, str]:
    """(title, kicker) a section shows first."""
    if is_scene(sec):
        st = next((s for s in sec.steps if s.title), None)
        return (st.title, st.kicker or "") if st else ("", "")
    return getattr(sec, "title", None) or getattr(sec, "text", None) or "", getattr(sec, "kicker", None) or ""


def end_card(site: Site, t: Trailer) -> dict:
    cta, url = t.cta, t.url
    if cta is None:
        if site.nav.cta:
            cta = site.nav.cta.label
        else:
            btn = next((s.button for s in site.sections if s.type == "cta" and getattr(s, "button", None)), None)
            cta = btn.label if btn else None
    if url is None and site.nav.cta and site.nav.cta.href.startswith(("http://", "https://")):
        url = re.sub(r"^https?://(www\.)?", "", site.nav.cta.href).rstrip("/")
    disclaimer = t.disclaimer
    product = getattr(site, "product", None)       # site.product (the product feature), when present
    if disclaimer is None and product is not None and getattr(product, "concept", False):
        maker = getattr(product, "maker", None)
        disclaimer = f"Concept page. Not affiliated with {maker}." if maker else "Concept page."
    logo = site.nav.logo if site.nav.logo and site.nav.logo.startswith("M") else None
    return {"title": rich(t.title or site.name), "tagline": rich(t.tagline if t.tagline is not None else site.description),
            "cta": plain(cta or ""), "url": plain(url or ""), "disclaimer": plain(disclaimer or ""), "logo": logo}


# ---------------------------------------------------------------- the cut

class Planner:
    def __init__(self, project: Project, site: Site, t: Trailer, log: Callable[[str], None] = print,
                 tracks: Optional[dict] = None):
        """tracks: film section id -> the take's product track (take.py --pass track), so shots of the product can be
        cut where it is biggest in frame."""
        self.project, self.site, self.t, self.log = project, site, t, log
        self.tracks = tracks or {}
        self.beat = 60.0 / t.bpm
        self.films: dict[str, Film] = {}
        for s in site.sections:
            if s.type == "film":
                f = load_film(project, s)
                if f is None:
                    log(f"  note: film section '{s.id}' has not been built (no footage); run `studio build` first to use it")
                else:
                    self.films[s.id] = f

    # -- film windows
    def product_size(self, f: Film, t: float) -> float:
        """The product's height as a fraction of the frame at second t of a take (0 when off screen)."""
        tr = self.tracks.get(f.sec.id)
        if not tr:
            return 0.0
        fr = tr["frames"]
        e = fr[min(len(fr) - 1, max(0, int(round(t * tr["fps"]))))]
        if not e or not (-0.05 < e["c"][0] < 1.05 and -0.05 < e["c"][1] < 1.05):
            return 0.0
        return max(0.0, e["box"][3] - e["box"][1])

    def _biggest(self, f: Film, a: float, L: float) -> Optional[float]:
        """Start of the L-second window, from `a - L` on, where the product is biggest in frame on average (the
        take's closest approach), or None without a track."""
        if f.sec.id not in self.tracks or f.dur <= L:
            return None
        step = 2.0 / f.fps
        best, best_t = -1.0, None
        t0 = max(0.0, a - L)
        while t0 <= f.dur - L + 1e-6:
            k = 12
            score = sum(self.product_size(f, t0 + L * j / (k - 1)) for j in range(k)) / k
            if score > best + 1e-4:
                best, best_t = score, t0
            t0 += step
        return best_t

    def _window(self, f: Film, a: float, b: float, beats: int, speed: float, after: float = 0.0,
                align: str = "start") -> float:
        """First second of a `beats`-long window under [a, b], not overlapping the previous shot of the same film
        when there is room, inside the film."""
        L = beats * self.beat * speed
        if align == "end":
            t0 = b - L
        elif b - a >= L:
            t0 = a
        else:
            t0 = (a + b) / 2 - L / 2
        if t0 < after and after + L <= f.dur + 1e-6:
            t0 = after
        return max(0.0, min(t0, f.dur - L))

    def film_shot(self, f: Film, step: Optional[int], rng: Optional[tuple[float, float]], beats: Optional[int],
                  role: str, after: float, caption=None, kicker=None, speed: float = 1.0) -> Shot:
        title, kick = "", ""
        if step is not None:
            if not 0 <= step < len(f.sec.steps):
                raise BuildError(f"trailer: section '{f.sec.id}' has no step {step}")
            a, b = f.step_range(step)
            title, kick = f.sec.steps[step].title, f.sec.steps[step].kicker or ""
        elif rng is not None:
            a, b = rng
        else:
            a, b = 0.0, f.dur
        cap = title if caption is None else caption
        n = beats or read_beats(cap, self.beat, 8 if role in ("hook", "reveal") else 4)
        t0 = self._window(f, a, b, n, speed, after, align="end" if role == "reveal" and f.has_product else "start")
        if role == "reveal" and f.has_product:   # show the real product where it is biggest in frame
            t0 = self._biggest(f, a, n * self.beat * speed) or t0
        zoom = None    # takes with a product push in on it automatically (see frame.product_zoom)
        return Shot("film", n, role, label=f"{f.sec.id}" + (f" step {step}" if step is not None else ""), src=f.src,
                    t0=t0, speed=speed, caption=rich(cap), kicker=plain(kick if kicker is None else kicker),
                    zoom=zoom, section=f.sec.id, track=f.sec.id if f.has_product else None)

    # -- the default cut
    def derive(self) -> list[Shot]:
        t, beat, bar = self.t, self.beat, 4
        segs = [(f, i) for f in self.films.values() for i, st in enumerate(f.sec.steps) if st.title]
        if not segs and self.films:
            segs = [(f, None) for f in self.films.values()]
        lines, lines_kicker = callout_lines(self.site)
        product_film = next((f for f in self.films.values() if f.has_product), None)
        stills = product_stills_available(self.project, self.site)
        use_callouts = bool(lines) and (product_film is not None or stills or any(
            s.type == "product" for s in self.site.sections))
        end_s = t.end_beats * beat
        shots: list[Shot] = []
        if segs:
            hook = segs[0]
            reveal = None
            if len(segs) > 1:
                # the product reveal: the last step of the film with the product in it, else the last step
                cands = [sg for sg in segs[1:] if sg[0].has_product] or segs[1:]
                reveal = cands[-1]
            middle = [sg for sg in segs[1:] if sg is not reveal]
            fixed = (read_beats(self._title(hook), beat, 8) + (read_beats(self._title(reveal), beat, 8) if reveal else 0)
                     + (2 * len(lines) if use_callouts else 0)) * beat + end_s
            chosen: list = []
            for k in range(min(4, len(middle)), -1, -1):   # as many middle shots as fit, spread over the story
                pick = [middle[x] for x in sorted({round(j * (len(middle) - 1) / max(k - 1, 1)) for j in range(k)})]
                if fixed + sum(read_beats(self._title(m), beat, bar) for m in pick) * beat <= t.seconds + bar * beat / 2:
                    chosen = pick
                    break
            order = [hook] + chosen + ([reveal] if reveal else [])
            ends: dict[str, float] = {}
            for j, (f, i) in enumerate(order):
                role = "hook" if j == 0 else "reveal" if reveal is not None and j == len(order) - 1 else "middle"
                s = self.film_shot(f, i, None, None, role, ends.get(f.sec.id, 0.0))
                ends[f.sec.id] = s.t0 + s.beats * beat * s.speed
                shots.append(s)
        else:
            shots = self._recorded_cut()
        if use_callouts:
            shots.append(self._callouts(lines, lines_kicker, shots))
        shots.append(Shot("end", t.end_beats, "end", label="end card"))
        return shots

    def _title(self, seg) -> str:
        if seg is None:
            return ""
        f, i = seg
        return f.sec.steps[i].title if i is not None else ""

    def _callouts(self, lines: list[str], kicker: str, shots: list[Shot]) -> Shot:
        """Feature callouts on the beat: over product stills when the product feature is there, else over the
        product reveal's last frame, held, with the push-in carrying on."""
        n = 2 * len(lines)
        views = product_stills_available(self.project, self.site)
        if views:
            return Shot("still", n, "features", label="callouts over product stills", callouts=lines, kicker=kicker,
                        zoom=(1.02, 1.12), text="three-quarter")
        last = next((s for s in reversed(shots) if s.kind == "film"), None)
        if last is None:
            return Shot("card", n, "features", label="callouts", callouts=lines, kicker=kicker)
        t_end = last.t0 + last.beats * self.beat * last.speed - 1.0 / 24
        return Shot("film", n, "features", label="callouts over the reveal", src=last.src, t0=max(0.0, t_end),
                    hold=True, callouts=lines, kicker=kicker, zoom=last.zoom, section=last.section,
                    track=last.track)

    def _recorded_cut(self) -> list[Shot]:
        """No film on the site: record the opening sections scrolling, captioned with their own headlines."""
        if not (self.project.dist / "index.html").exists():
            raise BuildError("trailer: the site has no film and is not built; run `studio build` first so its "
                             "sections can be recorded")
        out = []
        for s in self.site.sections:
            if s.type in ("stats", "faq", "gallery") or not getattr(s, "id", None):
                continue
            title, kicker = section_headline(s)
            if not title:
                continue
            role = "hook" if not out else "middle"
            n = read_beats(title, self.beat, 8 if role == "hook" else 6)
            out.append(Shot("record", n, role, label=f"record {s.id}", section=s.id, span=(0.0, 0.6)))
            if len(out) == 4:
                break
        if not out:
            raise BuildError("trailer: nothing to cut from; give sections ids and headlines, or list `trailer.shots`")
        return out

    # -- trailer.shots
    def explicit(self) -> list[Shot]:
        out: list[Shot] = []
        ends: dict[str, float] = {}
        beat = self.beat
        for k, s in enumerate(self.t.shots):
            sources = [x for x in (s.section or s.beat, s.product, s.card) if x]
            if len(sources) != 1:
                raise BuildError(f"trailer shot {k + 1}: give exactly one of section/beat, product or card")
            if s.product:
                if not product_stills_available(self.project, self.site):
                    self.log(f"  trailer shot {k + 1}: skipped: product stills need `site.product` and the product "
                             f"feature (engine/product.py), which this engine does not have yet")
                    continue
                cap = s.caption or ""
                out.append(Shot("still", s.beats or read_beats(cap, beat, 4), label=f"product {s.product}",
                                text=s.product, caption=rich(cap), kicker=plain(s.kicker), callouts=s.callouts,
                                zoom=s.zoom or (1.02, 1.12), focus=s.focus))
                continue
            if s.card:
                out.append(Shot("card", s.beats or read_beats(s.card, beat, 4), label="card", text=rich(s.card),
                                kicker=plain(s.kicker), callouts=s.callouts))
                continue
            sec_id = s.section
            rng = s.range
            if s.beat:
                f = next((f for f in self.films.values() if s.beat in f.spans), None)
                if f is None:
                    raise BuildError(f"trailer shot {k + 1}: no built beats film has a beat '{s.beat}'")
                sec_id, rng = f.sec.id, rng or f.spans[s.beat]
                if s.range:   # a range given with a beat is relative to the beat
                    a0 = f.spans[s.beat][0]
                    rng = (a0 + s.range[0], a0 + s.range[1])
            sec = next((x for x in self.site.sections if getattr(x, "id", None) == sec_id), None)
            if sec is None:
                raise BuildError(f"trailer shot {k + 1}: no section with id '{sec_id}'")
            if sec.type == "film":
                f = self.films.get(sec.id)
                if f is None:
                    raise BuildError(f"trailer shot {k + 1}: film '{sec.id}' has not been built; run `studio build`")
                cap = s.caption
                if cap is None and s.beat:   # the step pinned to that beat
                    st = next((x for x in f.sec.steps if (x.state or {}).get("beat") == s.beat), None)
                    cap = st.title if st else ""
                    if s.kicker is None and st is not None:
                        s = s.model_copy(update={"kicker": st.kicker})
                role = "reveal" if (s.zoom is None and k == len(self.t.shots) - 1 and f.has_product) else "shot"
                shot = self.film_shot(f, s.step, rng, s.beats, role, ends.get(f.sec.id, 0.0) if rng is None else 0.0,
                                      caption=cap, kicker=s.kicker, speed=s.speed)
                if rng is not None:
                    shot.t0 = max(0.0, min(rng[0], f.dur - 1.0 / f.fps))
                shot.hold, shot.callouts, shot.focus = s.hold, s.callouts, s.focus
                if s.zoom:
                    shot.zoom = s.zoom
                if not self.t.captions:
                    shot.caption = shot.kicker = ""
                ends[f.sec.id] = shot.t0 + shot.beats * beat * shot.speed
                out.append(shot)
            else:
                # a recorded section shows its own copy: no caption over it unless one is given
                cap = s.caption or ""
                out.append(Shot("record", s.beats or read_beats(cap, beat, 6), label=f"record {sec.id}", section=sec.id,
                                caption=rich(cap), kicker=plain(s.kicker or ""),
                                span=tuple(s.range) if s.range else (0.0, 0.6), callouts=s.callouts, speed=s.speed))
        if not out:
            raise BuildError("trailer: no usable shots")
        out.append(Shot("end", self.t.end_beats, "end", label="end card"))
        return out

    def plan(self) -> list[Shot]:
        shots = self.explicit() if self.t.shots else self.derive()
        if not self.t.captions:
            for s in shots:
                s.caption = ""
                s.kicker = "" if not s.callouts else s.kicker
        return shots


# ---------------------------------------------------------------- product stills (the product feature)

def product_stills_available(project: Project, site: Site) -> bool:
    """True when the engine has product stills (engine/product.py, `product_still`) and the site declares a product."""
    if getattr(site, "product", None) is None:
        return False
    try:
        from .. import product as _product   # noqa: F401
        return hasattr(_product, "product_still")
    except ImportError:
        return False


def product_still(project: Project, site: Site, view: str, size: tuple[int, int], background: Optional[str],
                  log: Callable[[str], None]) -> Path:
    """Render (or reuse) a still of site.product from `view` through the product feature. Only the arguments its
    `product_still` accepts are passed, so the two features can evolve independently."""
    import inspect
    from .. import product as _product
    fn = _product.product_still
    want = {"project": project, "site": site, "view": view, "size": size, "background": background, "log": log}
    params = inspect.signature(fn).parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        kwargs = want
    else:
        kwargs = {k: v for k, v in want.items() if k in params}
    out = fn(**kwargs)
    return Path(out)
