"""Scoring one finished film: second by second and beat by beat.

`scan_film` reads a film once and measures it; `score` turns the measurements into severities (0 fine, 1 clearly
visible) for the five things a viewer notices without being able to say why: pops, softness, halos, style drift and
morphs. Thresholds are constants at the top of each scorer, with the clean and the broken values they were set between
(measured on a story-film test page and on examples/feel; see docs/ENGINE.md, "Polish report").

Time is in seconds of the joined film. Everything here is CPU, numpy and OpenCV.
"""
from __future__ import annotations

import math
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from . import metrics as M
from .metrics import ramp

SAMPLES_PER_S = 4            # edge / halo / style samples per second of film
MIN_SEV = 0.40               # an issue is a stretch whose severity reaches this
MERGE_GAP = 0.6              # samples closer than this (seconds) are one stretch
STILL_PX = 8.0               # the picture counts as still while it has moved less than this (px at 384 wide) since the beat began


@dataclass
class BeatSpan:
    id: str
    start: float                       # seconds of the joined film where the beat's own clip starts
    end: float
    clip: Optional[Path] = None
    kind: str = "generated"            # generated | freeze | film
    zoom: Optional[float] = None       # freeze: the tightest framing, as a share of the frame's width
    upscale: float = 1.0
    fade_in: Optional[float] = None    # the join into this beat, seconds of overlap, when it has its own (0: a hard cut)

    @property
    def dur(self) -> float:
        return self.end - self.start


@dataclass
class Scan:
    path: Path
    fps: float
    n: int
    size: tuple[int, int]                              # width, height of the film
    small: list = field(default_factory=list)          # FLOW_W gray uint8 per frame
    luma: np.ndarray = None
    samples: dict = field(default_factory=dict)        # frame index -> {"edge":, "style":}
    step: int = 6                                      # frames between samples


# ---------------------------------------------------------------- reading

class _FfmpegCap:
    """The small part of cv2.VideoCapture this module uses, over an ffmpeg pipe: for films OpenCV's build cannot decode
    (HEVC, AV1, VP9 ...)."""

    def __init__(self, path: Path):
        import subprocess
        from ..config import settings
        from ..project import probe
        info = probe(Path(path), "stream=width,height,r_frame_rate,nb_frames:format=duration")
        self.w, self.h = int(info["width"]), int(info["height"])
        num, _, den = str(info.get("r_frame_rate", "24/1")).partition("/")
        self.fps = float(num) / float(den or 1)
        self.n = int(round(float(info.get("duration") or 0) * self.fps))
        self.proc = subprocess.Popen([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "rawvideo",
                                      "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.ok = self.n > 0

    def isOpened(self):
        return self.ok

    def get(self, prop):
        return {cv2.CAP_PROP_FPS: self.fps, cv2.CAP_PROP_FRAME_COUNT: self.n, cv2.CAP_PROP_FRAME_WIDTH: self.w,
                cv2.CAP_PROP_FRAME_HEIGHT: self.h}.get(prop, 0)

    def read(self):
        size = self.w * self.h * 3
        buf = self.proc.stdout.read(size)
        if len(buf) < size:
            return False, None
        return True, np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3).copy()

    def release(self):
        try:
            self.proc.kill()
        except Exception:
            pass


def open_film(path: Path):
    cap = cv2.VideoCapture(str(path))
    if cap.isOpened() and cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0:
        return cap
    cap.release()
    try:
        alt = _FfmpegCap(path)
        if alt.isOpened():
            return alt
    except Exception:
        pass
    raise RuntimeError(f"cannot read the film {path} (neither OpenCV nor ffmpeg could decode it)")


def scan_film(path: Path, progress: Callable[[float, str], None] = lambda f, m="": None,
              workers: Optional[int] = None) -> Scan:
    """One pass over the film: a small gray copy of every frame (for flow), and edge + style statistics of every
    `step`-th frame at full size."""
    import os
    cap = open_film(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    n_est = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, round(fps / SAMPLES_PER_S))
    sc = Scan(path=path, fps=fps, n=0, size=(W, H), step=step)
    workers = workers or max(2, min(8, (os.cpu_count() or 4) - 1))
    sem = threading.BoundedSemaphore(workers * 3)
    pending: dict = {}

    def job(i, frame):
        try:
            g = M.gray_f32(frame)
            e = M.edge_stats(g, want_points=True)
            e.update(M.spectral_detail(g))
            return {"edge": e, "style": M.style_stats(frame)}
        finally:
            sem.release()

    with ThreadPoolExecutor(workers) as ex:
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            sc.small.append(cv2.cvtColor(M.resize_w(frame, M.FLOW_W), cv2.COLOR_BGR2GRAY))
            if i % step == 0:
                sem.acquire()
                pending[i] = ex.submit(job, i, frame)
            i += 1
            if i % 48 == 0:
                progress(0.5 * min(1.0, i / n_est), f"reading frames ({i}/{n_est})")
        for k, fut in pending.items():
            sc.samples[k] = fut.result()
    cap.release()
    sc.n = i
    sc.luma = np.array([float(g.mean()) for g in sc.small], np.float32)
    return sc


def read_frames(path: Path, idxs: list[int], width: Optional[int] = None) -> dict[int, np.ndarray]:
    """BGR frames of a clip at the given frame indices (sequential read: seeking is not frame-exact in every file)."""
    want = sorted({max(0, int(i)) for i in idxs})
    out: dict[int, np.ndarray] = {}
    if not want:
        return out
    cap = open_film(path)
    last = None
    i = 0
    wi = 0
    while wi < len(want):
        ok, f = cap.read()
        if not ok:
            break
        last = f
        while wi < len(want) and want[wi] == i:
            out[want[wi]] = M.resize_w(f, width) if width else f
            wi += 1
        i += 1
    if last is not None:              # indices past the end get the last frame
        for k in want[wi:]:
            out[k] = M.resize_w(last, width) if width else last
    cap.release()
    return out


# ---------------------------------------------------------------- motion: steps between new frames

def steps_of(sc: Scan, workers: Optional[int] = None,
             progress: Callable[[float, str], None] = lambda f, m="": None) -> dict:
    """Find the frames that are new (video made at 12 fps and written at 24 repeats every frame; a held shot repeats
    its frame), then measure every step from one new frame to the next."""
    import os
    G = sc.small
    n = len(G)
    plain = np.array([float(np.abs(G[i + 1].astype(np.int16) - G[i].astype(np.int16)).mean()) for i in range(n - 1)])
    # frame i+1 is a repeat when it hardly differs from i, compared with what moves nearby
    new = [0]
    for i in range(n - 1):
        lo, hi = max(0, i - 12), min(n - 1, i + 13)
        p90 = float(np.percentile(plain[lo:hi], 90))
        if plain[i] >= max(0.15, 0.2 * p90):
            new.append(i + 1)
    a_idx, b_idx = new[:-1], new[1:]
    workers = workers or max(2, min(8, (os.cpu_count() or 4) - 1))
    res: list = [None] * len(a_idx)
    done = [0]

    def one(k):
        r = M.step_stats(G[a_idx[k]], G[b_idx[k]])
        done[0] += 1
        return r
    with ThreadPoolExecutor(workers) as ex:
        for k, r in enumerate(ex.map(one, range(len(a_idx)))):
            res[k] = r
            if k % 40 == 0:
                progress(0.5 + 0.35 * k / max(1, len(a_idx)), f"measuring motion ({k}/{len(a_idx)})")
    gap = np.array([b - a for a, b in zip(a_idx, b_idx)], np.float32)
    return {"a": np.array(a_idx), "b": np.array(b_idx), "gap": gap, "t": np.array(b_idx) / sc.fps,
            "plain": np.array([r["plain"] for r in res]), "resid": np.array([r["resid"] for r in res]),
            "local": np.array([r["local"] for r in res]), "area": np.array([r["area"] for r in res]), "mot": np.array([r["mot"] for r in res]),
            "dl": np.array([abs(float(sc.luma[b]) - float(sc.luma[a])) for a, b in zip(a_idx, b_idx)]),
            "luma_b": np.array([float(sc.luma[b]) for b in [a_idx[0]] + list(b_idx)]),
            "new_frames": len(new), "frames": n}


# ---------------------------------------------------------------- scorers: each returns series of (t, severity, info)

def _roll_median(x: np.ndarray, i: int, w: int) -> float:
    lo, hi = max(0, i - w), min(len(x), i + w + 1)
    v = np.concatenate([x[lo:i], x[i + 1:hi]])
    return float(np.median(v)) if len(v) else float(x[i])


def score_pops(st: dict) -> list[dict]:
    """Pops inside the film (not at joins: see score_joins).

    jump     the change between two frames that motion cannot explain (flow residual) is many times what its neighbours
             show, over a large part of the picture: a pop, a glitch, a cut. Clean: 0.5-3x. Set between 2.5x (fine) and
             5x (clearly a pop), only when the residual is itself visible (1.5 levels and up) and a quarter to 60% of the
             picture changed by 24 levels (a doves-appear event changes a corner, a pop changes the frame).
    flash    a flicker: one frame whose brightness is off by 3-8 levels or more from both its neighbours, which agree with
             each other (a light that comes on and stays on is an event, not a flicker).
    stutter  while things move, the picture updates fewer than 12 times a second and by a visible amount: judder.
    """
    out = []
    if len(st["t"]) < 3:
        return out
    s = st["resid"] / st["gap"]
    for i in range(len(s)):
        base = max(_roll_median(s, i, 8), 0.6)
        ratio = s[i] / base
        sev = ramp(ratio, 2.5, 5.0) * ramp(s[i], 1.5, 3.0) * ramp(float(st["area"][i]), 0.25, 0.60)
        if sev > 0:
            out.append({"t": float(st["t"][i]), "sev": sev, "kind": "jump", "ratio": float(ratio), "resid": float(s[i]),
                        "area": float(st["area"][i]), "a": int(st["a"][i]), "b": int(st["b"][i])})
    # flicker: one frame brighter or darker than both neighbours, and back (a lasting step is an event, not a flicker)
    L = st["luma_b"]
    for i in range(len(L) - 2):
        d1, d2 = L[i + 1] - L[i], L[i + 2] - L[i + 1]
        if d1 * d2 < 0 and abs(d1 + d2) <= 0.4 * max(abs(d1), abs(d2)):
            mag = min(abs(d1), abs(d2))
            fl = ramp(mag, 3.0, 8.0)
            if fl > 0:
                out.append({"t": float(st["t"][i]), "sev": fl, "kind": "flash", "step": float(mag),
                            "a": int(st["a"][i]), "b": int(st["b"][i + 1])})
    # stutter: windows of a second
    t_all = st["t"]
    for t0 in np.arange(0.0, float(t_all[-1]) - 0.5, 0.5):
        m = (t_all >= t0) & (t_all < t0 + 1.0)
        if m.sum() < 3:
            continue
        rate = float(m.sum())                                   # new frames in a second
        move = float(np.median(st["plain"][m]))
        sev = ramp(rate, 12.0, 6.0) * ramp(move, 1.0, 4.0)
        if sev > 0:
            out.append({"t": float(t0 + 0.5), "sev": sev, "kind": "stutter", "rate": rate, "move": move,
                        "a": int(st["a"][m][0]), "b": int(st["b"][m][-1])})
    return out


def score_morphs(st: dict, skip: tuple = ()) -> list[dict]:
    """Things that appear, dissolve or rearrange rather than move.

    Over every half second, `unexplained` is the share of the picture's change that optical flow cannot account for
    (flow residual / plain difference) and `level` how big that residual is. A walking crowd or a camera push is 0.2-0.5;
    a crowd that dissolves into rows is 0.8-1 at 3-6 levels. Severity from 0.55 to 0.85 unexplained, scaled by the level
    (1.2 levels: nothing, 4.5: full), so a small event is a slight morph and a whole scene rebuilding is a bad one.
    Crossfade windows (`skip`) are the join metric's, not this one's. A window with no flagged neighbour is one event,
    not a rebuild, and counts for under half."""
    out = []
    t = st["t"]
    if len(t) < 4:
        return out
    rows = []
    for t0 in np.arange(0.0, float(t[-1]), 0.25):
        m = (t >= t0) & (t < t0 + 0.5)
        if m.sum() < 2 or any(a <= t0 + 0.25 <= b for a, b in skip):
            continue
        sp, sr = float(st["plain"][m].sum()), float(st["resid"][m].sum())
        q = sr / max(sp, 1e-3)
        level = sr / m.sum()
        sev = ramp(q, 0.55, 0.85) * ramp(level, 1.2, 4.5)
        rows.append({"t": float(t0 + 0.25), "sev": sev, "unexplained": float(q), "level": float(level),
                     "a": int(st["a"][m][0]), "b": int(st["b"][m][-1])})
    for i, r in enumerate(rows):
        near = [rows[j]["sev"] for j in (i - 1, i + 1) if 0 <= j < len(rows) and abs(rows[j]["t"] - r["t"]) < 0.3]
        if r["sev"] > 0 and near and max(near) >= 0.3:
            out.append(r)
        elif r["sev"] > 0:
            out.append({**r, "sev": r["sev"] * 0.45})
    return out


def detail_reference(samples: dict) -> Optional[float]:
    """The section's sharpest: the 90th percentile of its frames' fine-detail index."""
    d = [s["edge"]["detail"] for s in samples.values() if s["edge"].get("detail") and s["edge"]["busy"] >= 1.5]
    return float(np.percentile(d, 90)) if len(d) >= 3 else None


def width_reference(samples: dict) -> Optional[float]:
    """The section's sharpest edges: the 10th percentile of its frames' median edge widths."""
    w = [s["edge"]["width"] for s in samples.values() if s["edge"]["width"] is not None and s["edge"]["n_edges"] >= 300]
    return float(np.percentile(w, 10)) if len(w) >= 3 else None


def score_softness(sc: Scan) -> list[dict]:
    """Effective detail: how much fine detail the busiest parts of the frame hold (`detail`, see metrics.spectral_detail).
    Clean footage and drawings: 0.0003 to 0.01 whatever the content (examples/feel: lowest frame 0.00027, median 0.002;
    the test page's clean beats 0.0006-0.006); a picture enlarged 3.5x or more: 0.00001-0.00013 (the test page's hands close-up
    median 0.00012, the boots 0.00004). Severity from 0.00025 (fine) to 0.00008 (clearly upscaled), on a log scale. Needs
    1.5 levels of gradient in the busy tiles (a blank frame is not soft). The reason also quotes the edge width in pixels (clean 1.5-2.5, upscaled 3+)."""
    out = []
    ref = detail_reference(sc.samples)
    wref = width_reference(sc.samples)
    for i, s in sorted(sc.samples.items()):
        e = s["edge"]
        if not e.get("detail") or e["busy"] < 1.5:
            continue
        lg = math.log10(e["detail"])
        out.append({"t": i / sc.fps, "sev": ramp(lg, math.log10(2.5e-4), math.log10(8e-5)), "detail": e["detail"], "ref": ref,
                    "width": e["width"], "width_ref": wref, "aniso": e["aniso"], "frame": i,
                    "hatch": s["style"]["hatch"]})
    return out


def rim_baseline(sc: Scan) -> tuple[float, int]:
    """What a bright rim beside an edge costs this film's own look: the median over 2-second chunks of the share of clean
    edges with one (ink art 1-3%, rim-lit photography 10%), and how many chunks that is. Halos are scored against it."""
    chunks: dict[int, list] = {}
    for i, s in sc.samples.items():
        e = s["edge"]
        if e["rim"] is not None and e["n_rim"] >= 300:
            chunks.setdefault(int(i / sc.fps // 2), []).append(e["rim"])
    if not chunks:
        return 0.0, 0
    return float(np.median([np.median(v) for v in chunks.values()])), len(chunks)


def score_halos(sc: Scan) -> list[dict]:
    """Bright rims and seams beside clean edges: the share of flat-sided strong edges with one, scored against the film's
    own baseline (`rim_baseline`) so that rim-lit photography is not a halo and ink art with a seam is. Severity from 2.5x
    the baseline (fine) to 5x, and never under 6-10% (at 6% or less a rim is just how edges look). Test page: baseline 3%,
    the hands close-up 19-20% (7x), the boots 9-19%, everything else under 7%. A film under six seconds has no baseline to
    speak of: it is judged on the share alone, from 15% (fine) to 25%. Needs 300 such edges."""
    out = []
    base, n_chunks = rim_baseline(sc)
    base = max(base, 0.02)
    for i, s in sorted(sc.samples.items()):
        e = s["edge"]
        if e["rim"] is None or e["n_rim"] < 300:
            continue
        if n_chunks >= 3:
            sev = ramp(e["rim"] / base, 2.5, 5.0) * ramp(e["rim"], 0.06, 0.10)
        else:
            sev = ramp(e["rim"], 0.15, 0.25)
        out.append({"t": i / sc.fps, "sev": sev, "rim": e["rim"], "base": base, "n": e["n_rim"], "frame": i})
    return out


def groups_of(joins: list[dict], n: int) -> list[int]:
    """Which beats are one scene: a beat joins the group of the one before it when the join is a continuation (the two
    frames that meet look alike), else it starts a new group. Returns a group number per beat."""
    g = [0]
    for i in range(1, n):
        j = next((x for x in joins if x["to_index"] == i), None)
        g.append(g[-1] if j is not None and j["related"] else g[-1] + 1)
    return g


def score_drift(sc: Scan, st: dict, spans: list[BeatSpan], fade: float, groups: Optional[list[int]] = None,
                embed: Optional[dict] = None) -> list[dict]:
    """How far the look moves from where the scene started: from the first second of its group of beats (beats that join
    like one scene, see `groups_of`) and, for what a moving camera does not explain, from where the beat itself started.

    hatch    share of the picture's structure that is weak texture (hatching, pencil, grain) rather than strong lines.
             Test page: clean ink and wash 0.37, the pencil look the turn beat drifts to 0.64. One JND = 0.15. Only against
             a drawn plate (under 0.55): in photographs (feel: 0.71) weak texture is just the content.
    grain    noise in flat areas, only while the frame is as sharp as the plate (a zoom loses grain by itself) and the
             picture has barely moved since the beat began. One JND = x1.65.
    tone, line, sat   histogram, line density, saturation against the beat's own first second, only while the picture
             has barely moved, and only when the change is gross (3 JND: 0.30 / x2.7 / 0.18).
    embed    (with --embed) 1 - cosine of a CLIP image embedding to the beat's own first second, while the picture
             is nearly still (against the scene's plate it measures the content, not the look: the test page's close-ups).

    Severity from 1 JND (fine) to 2 JND (clearly a different look); the worst component is the one reported."""
    out = []
    keys = sorted(sc.samples)
    if not keys:
        return out
    fps = sc.fps
    groups = groups or [0] * len(spans)

    def med(ks, f):
        v = [sc.samples[k]["style"][f] for k in ks if sc.samples[k]["style"][f] == sc.samples[k]["style"][f]]
        return float(np.median(v)) if v else float("nan")

    def own_keys(sp, i):
        lo = sp.start + (fade if i > 0 else 0.0)
        return [k for k in keys if lo <= k / fps < sp.end - (fade if i < len(spans) - 1 else 0.0)]
    plates = {}
    for i, sp in enumerate(spans):
        g = groups[i]
        if g in plates:
            continue
        own = own_keys(sp, i) or [k for k in keys if sp.start <= k / fps < sp.end]
        if not own:
            continue
        pk = [k for k in own if k / fps < (own[0] / fps) + 1.0] or own[:2]
        det = [sc.samples[k]["edge"].get("detail") for k in pk if sc.samples[k]["edge"].get("detail")]
        plates[g] = {"keys": pk, "hatch": med(pk, "hatch"), "fine": med(pk, "fine"), "grain": med(pk, "grain"),
                     "detail": float(np.median(det)) if det else None, "t": pk[0] / fps}
    cam = np.zeros(sc.n + 1)
    for b, mo in zip(st["b"], st["mot"]):
        cam[b:] += mo
    for i, sp in enumerate(spans):
        own = own_keys(sp, i)
        pl = plates.get(groups[i])
        if not own or pl is None:
            continue
        ref = [k for k in own if k / fps < own[0] / fps + 1.0][:4] or own[:2]
        r_tone = np.mean([sc.samples[k]["style"]["tone"] for k in ref], 0)
        r_sat, r_line = med(ref, "sat"), med(ref, "line")
        i0 = ref[0]
        for k in own:
            sy = sc.samples[k]["style"]
            comps = {}
            if (sy["fine"] >= 0.06 and pl["fine"] >= 0.06 and sy["hatch"] == sy["hatch"] and pl["hatch"] == pl["hatch"]
                    and pl["hatch"] < 0.55):          # only for a drawn plate: in a photograph weak texture is just the content
                comps["hatch"] = (abs(sy["hatch"] - pl["hatch"]) / 0.15, sy["hatch"], pl["hatch"])
            d = sc.samples[k]["edge"].get("detail")
            still = abs(cam[k] - cam[min(sc.n, i0)]) < STILL_PX
            if (still and sy["grain"] == sy["grain"] and pl["grain"] == pl["grain"] and pl["grain"] > 0.3 and sy["grain"] > 0.1
                    and d and pl["detail"] and d >= 0.3 * pl["detail"]):
                comps["grain"] = (abs(math.log(sy["grain"] / pl["grain"])) / math.log(1.65), sy["grain"], pl["grain"])
            if still and k not in ref:
                tone = float(np.abs(sy["tone"] - r_tone).sum() / 2) / 0.10
                if tone >= 3.0:
                    comps["tone"] = (tone, None, None)
                if r_line > 0.01 and sy["line"] > 0.005:
                    z = abs(math.log(sy["line"] / r_line)) / math.log(1.4)
                    if z >= 3.0:
                        comps["line"] = (z, sy["line"], r_line)
                z = abs(sy["sat"] - r_sat) / 0.06
                if z >= 3.0:
                    comps["sat"] = (z, sy["sat"], r_sat)
            if embed and still and k not in ref and k in embed.get("frame", {}) and sp.id in embed.get("beat_ref", {}):
                dd = 1.0 - float(np.dot(embed["frame"][k], embed["beat_ref"][sp.id]))
                comps["embed"] = (dd / embed.get("jnd", 0.12), dd, None)
            if not comps:
                continue
            # the most telling component that is a clear change; else the biggest; severity from the biggest
            clear = [c for c in ("embed", "hatch", "grain", "line", "tone", "sat") if c in comps and comps[c][0] >= 1.0]
            name = clear[0] if clear else max(comps, key=lambda c: comps[c][0])
            zmax = max(c[0] for c in comps.values())
            z, v, r = comps[name]
            z = zmax if clear else z
            out.append({"t": k / fps, "sev": ramp(z, 1.0, 2.0), "z": float(z), "what": name, "value": v, "ref": r,
                        "beat": sp.id, "frame": k, "plate_t": pl["t"], "plate_frame": pl["keys"][0] if pl["keys"] else 0,
                        "all": {a: float(b[0]) for a, b in comps.items()}})
    return out


# ---------------------------------------------------------------- joins

# a join is a continuation (the shots are one scene) when the frames that meet look alike: luma and colour
RELATED_LUMA = 30.0
RELATED_CHROMA = 10.0


def score_joins(spans: list[BeatSpan], fade: float, log: Callable[[str], None] = lambda s: None) -> list[dict]:
    """The dissolve between two shots. Two kinds: a scene change (the frames that meet look nothing alike: the test page 1-12 luma
    levels apart, a cut between unrelated scenes 70-80) is a dissolve on purpose and is never a problem; a continuation (the
    new shot picks up where the old one ended) must look like one. In the middle of the crossfade the viewer sees both
    pictures at half strength, so what shows is how far out of line they are (`disp`: the 90th percentile of the optical
    flow that would lay one on the other, in pixels of a 1920 frame; a gap under 20 px is a soft edge, 100 px a plain
    double image) and whether the colours change (`chroma`, Lab levels). Severity from 20 to 100 px, and from 1.0 to 3.5
    levels of colour change; the worse of the two. A hard cut (no fade) is judged on the two frames it joins.
    On the test page at mid-fade: walk to zoom 15 px (fine), zoom to shoes 99 px, shoes to hands 68 px, hands to her 43 px and
    3.1 levels (black coat to orange), her to turn 27 px."""
    out = []
    for i, (prev, cur) in enumerate(zip(spans[:-1], spans[1:]), start=1):
        if prev.clip is None or cur.clip is None or not prev.clip.exists() or not cur.clip.exists():
            continue
        cap = open_film(prev.clip)
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        na = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
        cap = open_film(cur.clip)
        nb = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
        f = fade if cur.fade_in is None else cur.fade_in      # this join's own crossfade (a beat's `fade`), else the film's
        nf = max(1, int(round(f * fps)))
        ia = {s: (na - nf + int(round(s * nf)) - (1 if s == 1.0 else 0)) for s in (0.0, 0.5, 1.0)}
        ib = {s: min(nb - 1, int(round(s * nf))) for s in (0.0, 0.5, 1.0)}
        fa = read_frames(prev.clip, list(ia.values()) + [na - 1], 480)
        fb = read_frames(cur.clip, list(ib.values()), 480)
        mm = {s: M.mismatch(fa[ia[s]], fb[ib[s]]) for s in (0.0, 0.5, 1.0)}
        meet = M.mismatch(fa[na - 1], fb[0])                       # the two frames a cut would join
        related = meet["luma"] <= RELATED_LUMA and meet["chroma"] <= RELATED_CHROMA
        if f < 0.15:
            m0, kind, pair = meet, "cut", (fa[na - 1], fb[0])
        else:
            m0, kind, pair = mm[0.5], "dissolve", (fa[ia[0.5]], fb[ib[0.5]])
        mis = M.misalignment(*pair)
        sev = max(ramp(mis["disp"], 20.0, 100.0), ramp(m0["chroma"], 1.0, 3.5)) if related else 0.0
        out.append({"t": cur.start + f / 2, "t0": cur.start, "t1": cur.start + f, "sev": sev, "kind": kind,
                    "related": bool(related), "from": prev.id, "to": cur.id, "to_index": i, "disp": mis["disp"],
                    "edges": m0["edges"], "luma": m0["luma"], "chroma": m0["chroma"], "meet_luma": meet["luma"],
                    "meet_chroma": meet["chroma"], "phases": {f"{s:.1f}": mm[s]["edges"] for s in mm},
                    "frames": {"a": ia[0.5], "b": ib[0.5], "prev": prev.id, "cur": cur.id}})
    return out
