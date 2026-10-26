"""`studio inspect`: find the film of a section, score it, write `.build/inspect/<section>.json` + `.html`.

The report (JSON) is the contract the HTML page, the storyboard badges and the MCP tool all read:

    {version, section, key, film: {path, kind, seconds, fps, size}, beats: [{id, start, end, kind, scores: {metric: 0-100},
     worst: {metric, severity, t, reason, hint} | null}], joins: [...], issues: [{metric, kind, severity, level, t, t0,
     t1, beat, reason, hint, thumb, crop}], seconds: [{t, beat, pops, softness, halos, drift, morphs, worst}],
     timeline: {step, pops: [...], ...}, summary: {worst, counts, verdict}, measures: {...}}

Severity is 0 (fine) to 1 (clearly visible); `level` names it: clean, slight, visible, bad. Scores are 100 - 100 x the
worst severity inside the beat's own stretch of the film.
"""
from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path
from typing import Callable, Optional

import cv2

from . import analyze as A
from .explain import level_of, reason

VERSION = 7
METRICS = ("pops", "softness", "halos", "drift", "morphs")
Log = Callable[[str], None]


# ---------------------------------------------------------------- what to look at

class Nothing(RuntimeError):
    """The section has no built film to inspect."""


def content_key(p: Path) -> str:
    """A key from a file's bytes (size and three 256 KB slices), not its date: a copy of the build has the same key."""
    h = hashlib.sha1()
    size = p.stat().st_size
    h.update(str(size).encode())
    with open(p, "rb") as f:
        for at in (0, max(0, size // 2 - 131072), max(0, size - 262144)):
            f.seek(at)
            h.update(f.read(262144))
    return h.hexdigest()[:16]


def film_candidates(project, sec) -> list[Path]:
    """The films a film section can end up as, newest meaning most processed. The first that exists is inspected."""
    g = project.build / sec.id / "gen"
    if sec.video:
        return [project.path(sec.video)]
    if sec.beats:
        return [g / "gen_sr.mp4", g / "beats.mp4"] if sec.beat_restore else [g / "beats.mp4", g / "gen_sr.mp4"]
    names = ["take.mp4", "gen_sr.mp4", "gen_up.mp4", "gen.mp4"]
    if sec.take and not sec.take.product:
        names = ["gen_sr.mp4", "gen_up.mp4", "gen.mp4"]
    return [g / n for n in names] + [project.build / sec.id / "wan" / "gen" / n for n in names]


def find_film(project, sec) -> Path:
    for c in film_candidates(project, sec):
        if c.exists():
            return c
    raise Nothing(f"section '{sec.id}' has no built film yet (looked for {', '.join(c.name for c in film_candidates(project, sec)[:2])} "
                  f"under {project.build / sec.id}): run `studio build` first")


def _clip_len(p: Path) -> Optional[float]:
    if not p.exists():
        return None
    cap = cv2.VideoCapture(str(p))
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    cap.release()
    return float(n / fps) if n else None


def beat_zoom(b, sec) -> Optional[float]:
    """A frozen beat's tightest framing as a share of the frame's width (the camera's smallest box, widened to the
    beat's aspect, as the engine does)."""
    f = b.freeze
    if f is None:
        return None
    from ..freeze_beats import camera_keys
    keys = [k["box"] if isinstance(k, dict) else k.box for k in camera_keys(f)]
    if not keys:
        return None
    return float(min(max(x1 - x0, y1 - y0) for x0, y0, x1, y1 in keys))


def plan_spans(project, sec, film_seconds: float) -> tuple[list[A.BeatSpan], float]:
    """Where every beat sits in the joined film (the engine joins clips with `xfade`: each starts `fade` before the
    last one ends). Returns the spans and the crossfade length."""
    if not sec.beats:
        return [A.BeatSpan("film", 0.0, film_seconds, None, "film")], 0.0
    durs, clips = [], []
    for b in sec.beats:
        clip = project.build / sec.id / "beats" / b.id / "clip.mp4"
        d = _clip_len(clip)
        durs.append(d if d else float(b.seconds))
        clips.append(clip if d else None)
    fade = min(sec.beat_fade, *(d / 3 for d in durs)) if len(durs) > 1 else 0.0
    spans, t = [], 0.0
    for b, d, c in zip(sec.beats, durs, clips):
        spans.append(A.BeatSpan(b.id, t, t + d, c, "freeze" if b.freeze is not None else "generated",
                                beat_zoom(b, sec), b.freeze.upscale if b.freeze is not None else 1.0))
        t += d - fade
    total = t + fade
    if abs(total - film_seconds) > 0.35 and total > 0:         # the build moved on from the spec: spread the beats over the film
        k = film_seconds / total
        for s in spans:
            s.start *= k; s.end *= k
        fade *= k
    return spans, fade


# ---------------------------------------------------------------- issues

def _owner(spans: list[A.BeatSpan], fade: float, t: float) -> A.BeatSpan:
    """The beat a moment of the film belongs to: its own clip, up to the middle of a crossfade."""
    for i, s in enumerate(spans):
        lo = s.start + (fade / 2 if i > 0 else 0.0)
        hi = s.end - (fade / 2 if i < len(spans) - 1 else 0.0)
        if lo <= t < hi:
            return s
    return spans[-1] if t >= spans[-1].end else spans[0]


def _stretches(rows: list[dict], metric: str, spans, fade, pitch: float = 0.25) -> list[dict]:
    """Rows (t, sev) of one metric and one beat into stretches: consecutive rows at or over MIN_SEV."""
    rows = sorted(rows, key=lambda r: r["t"])
    out, cur = [], None
    for r in rows:
        if r["sev"] < A.MIN_SEV:
            continue
        if cur is not None and r["t"] - cur[-1]["t"] <= A.MERGE_GAP and cur[-1]["_beat"] == r["_beat"]:
            cur.append(r)
        else:
            if cur:
                out.append(cur)
            cur = [r]
    if cur:
        out.append(cur)
    res = []
    for grp in out:
        peak = max(grp, key=lambda r: r["sev"])
        res.append({"metric": metric, "rows": grp, "peak": peak, "t": peak["t"], "t0": max(0.0, grp[0].get("t0", grp[0]["t"] - pitch / 2)),
                    "t1": grp[-1].get("t1", grp[-1]["t"] + pitch / 2), "severity": float(peak["sev"]),
                    "beat": peak["_beat"]})
    return res


def _worst_of(issues: list[dict]) -> Optional[dict]:
    if not issues:
        return None
    w = max(issues, key=lambda i: i["severity"])
    return {k: w[k] for k in ("metric", "kind", "severity", "level", "t", "reason", "hint") if k in w}


# ---------------------------------------------------------------- the run

def inspect_film(path: Path, spans: list[A.BeatSpan], fade: float, out_dir: Path, name: str, spec_info: dict,
                 log: Log = print, progress: Callable[[float, str], None] = lambda f, m="": None,
                 embed: bool = False) -> dict:
    """Score one film file; returns the report (not yet written)."""
    t_start = time.time()
    log(f"inspect {name}: reading {path.name}")
    sc = A.scan_film(path, progress)
    log(f"inspect {name}: measuring motion ({sc.n} frames)")
    st = A.steps_of(sc, progress=progress)
    progress(0.88, "scoring")
    fps = sc.fps
    seconds = sc.n / fps
    joins_win = [(s.start - 0.1, s.start + fade + 0.1) for s in spans[1:]] if fade > 0 else []

    joins = A.score_joins(spans, fade, log)
    groups = A.groups_of(joins, len(spans))
    emb = None
    if embed:
        from . import embed as E
        progress(0.9, "embedding frames (CLIP, CPU)")
        emb = E.embed_samples(sc, spans, fade, log)

    rows = {m: [] for m in METRICS}
    for r in A.score_pops(st):
        r["_beat"] = _owner(spans, fade, r["t"]).id
        r["metric"] = "pops"
        rows["pops"].append(r)
    for j in joins:
        j["_beat"] = j["to"]
        j["metric"] = "pops"
        rows["pops"].append(j)
    for r in A.score_softness(sc):
        r["_beat"] = _owner(spans, fade, r["t"]).id
        rows["softness"].append(r)
    for r in A.score_halos(sc):
        r["_beat"] = _owner(spans, fade, r["t"]).id
        rows["halos"].append(r)
    for r in A.score_drift(sc, st, spans, fade, groups, emb):
        if any(a <= r["t"] <= b for a, b in joins_win):
            continue
        r["_beat"] = r["beat"]
        rows["drift"].append(r)
    for r in A.score_morphs(st, tuple((a - 0.15, b + 0.15) for a, b in joins_win)):
        r["_beat"] = _owner(spans, fade, r["t"]).id
        rows["morphs"].append(r)

    by_id = {s.id: s for s in spans}
    ctx = {"fade": fade, "spans": by_id, "ref_width": A.width_reference(sc.samples), "ref_detail": A.detail_reference(sc.samples),
           "spec": spec_info, "rim_base": A.rim_baseline(sc)[0]}
    issues: list[dict] = []
    for m in METRICS:
        for st_ in _stretches(rows[m], m, spans, fade):
            peak = st_["peak"]
            if m == "drift" and peak.get("what") in ("tone", "line", "sat"):
                st_["severity"] = min(st_["severity"], 0.6)       # these move with the content too: never a "bad"
            why, hint = reason(m, peak, by_id[st_["beat"]], ctx)
            issues.append({"metric": m, "kind": peak.get("kind") or peak.get("what") or m, "severity": round(st_["severity"], 3),
                           "level": level_of(st_["severity"]), "t": round(st_["t"], 2), "t0": round(st_["t0"], 2),
                           "t1": round(st_["t1"], 2), "beat": st_["beat"], "reason": why, "hint": hint,
                           "_peak": peak})
    issues.sort(key=lambda i: (-i["severity"], i["t"]))

    # per beat: score of every metric over the beat's own stretch, and its worst issue
    beats_out = []
    for i, s in enumerate(spans):
        sc_m = {}
        for m in METRICS:
            sev = [r["sev"] for r in rows[m] if r["_beat"] == s.id]
            sc_m[m] = int(round(100 * (1 - (max(sev) if sev else 0.0))))
        mine = [x for x in issues if x["beat"] == s.id]
        beats_out.append({"id": s.id, "start": round(s.start, 3), "end": round(s.end, 3), "kind": s.kind, "scene": groups[i],
                          "scores": sc_m, "worst": _worst_of(mine), "issues": len(mine),
                          "zoom": s.zoom})

    # second by second
    sec_rows = []
    for k in range(int(math.ceil(seconds))):
        row = {"t": k, "beat": _owner(spans, fade, k + 0.5).id}
        for m in METRICS:
            v = [r["sev"] for r in rows[m] if k <= r["t"] < k + 1]
            row[m] = round(max(v), 3) if v else 0.0
        row["worst"] = max(METRICS, key=lambda m: row[m]) if max(row[m] for m in METRICS) >= A.MIN_SEV else None
        sec_rows.append(row)
    pitch = 0.25
    nb = int(math.ceil(seconds / pitch))
    timeline = {"step": pitch}
    for m in METRICS:
        arr = [0.0] * nb
        for r in rows[m]:
            lo = int(r.get("t0", r["t"]) / pitch) if "t0" in r and "t1" in r else int(r["t"] / pitch)
            hi = int(r.get("t1", r["t"]) / pitch) if "t1" in r else lo
            for b in range(max(0, lo), min(nb - 1, hi) + 1):
                arr[b] = max(arr[b], round(float(r["sev"]), 3))
        timeline[m] = arr

    counts = {lv: sum(1 for x in issues if x["level"] == lv) for lv in ("slight", "visible", "bad")}
    worst = _worst_of(issues)
    verdict = level_of(worst["severity"]) if worst else "clean"

    report = {
        "version": VERSION, "name": name, "film": {"path": str(path), "seconds": round(seconds, 3), "fps": fps,
                                                  "size": list(sc.size), "frames": sc.n, "new_frames": st["new_frames"]},
        "fade": round(fade, 3), "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "beats": beats_out, "joins": [{k: v for k, v in j.items() if not k.startswith("_") and k != "frames"} for j in joins],
        "issues": issues, "seconds": sec_rows, "timeline": timeline,
        "summary": {"worst": worst, "counts": counts, "verdict": verdict, "issues": len(issues)},
        "measures": {"width_ref": ctx["ref_width"], "detail_ref": ctx["ref_detail"], "rim_baseline": ctx["rim_base"],
                     "min_severity": A.MIN_SEV,
                     "embed": bool(emb), "seconds_taken": round(time.time() - t_start, 1)},
    }
    # thumbnails of the worst moments (needs the frames again: only now, and only for what is shown)
    progress(0.93, "pictures of the worst moments")
    from .thumbs import make_thumbs
    make_thumbs(report, sc, st, spans, joins, path, out_dir, name, log)
    for x in report["issues"]:
        x.pop("_peak", None)
    return report
