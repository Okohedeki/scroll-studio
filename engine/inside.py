"""The product as the set (`type: inside`): the camera's route through a product.

Pure planning, no Blender: from the product's parts report (`engine/product.py` `product_info`: every part's name,
path, centre, size and explode offset) and the section's stops, this module decides where the camera stands at every
stop, how it flies between them and which slice of the scroll each stop and its copy get. The renderer
(`backends/blender_scripts/inside.py`) only draws the frames this plan describes, so the plan can be tested, printed
(`studio inside`), and cached per frame.

Public API

    parts_of(info) -> list[Part]                  the parts report as objects
    find(parts, pattern, what) -> list[Part]      parts a glob matches (BuildError with suggestions when none)
    auto_stops(parts, n) -> list[InsideStop]      stops for a model whose spec names none
    resolve(sec, info) -> Resolved                stops resolved to parts, boxes, framing and camera sides
    make_plan(sec, info, aspect) -> Plan          the route: per-frame camera, timeline, windows for the copy
    schedule_steps(steps, plan) -> None           sets `at` on steps that have none, matched to the stops in order

Coordinates are the product's: metres, z up, the front facing -y (the normalised GLB seen in Blender), the base
centre at the origin. Angles follow the product views: yaw 0 looks at the front, 90 at the right side; pitch is the
camera's height above the horizon.
"""
from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .project import BuildError
from .layout import set_window, window
from .spec import InsideScene, InsideStop

SENSOR = 36.0                       # mm, full frame width
WIDE_LENS = 32.0                    # the opening and closing shot
WIDE_VIEW = (-35.0, 22.0)           # yaw, pitch of the opening shot
WIDE_OFFSET = 0.5                   # the opening and closing shots use this share of the scene's `offset`
EDGE_WINDOW = 0.28                  # how far into the flights on either side a stop's copy stays on screen
DRIFT_YAW = 2.2                     # degrees the camera creeps around a stop while it rests
DRIFT_PUSH = 0.035                  # share of the distance it creeps in
VERSION = 1


# ---------------------------------------------------------------- parts

@dataclass
class Part:
    index: int
    name: str
    mesh: str
    path: str
    triangles: int
    centre: np.ndarray
    size: np.ndarray
    explode: np.ndarray
    anchor: bool = False

    def names(self) -> list[str]:
        """What a glob can match: the part, its mesh, every assembly above it and the whole path (lower case)."""
        segs = [s for s in self.path.split("/") if s]
        tails = ["/".join(segs[i:]) for i in range(len(segs))]      # 'Driver/Cone' as well as 'Speaker/Driver/Cone'
        return [n.lower() for n in [self.name, self.mesh, *segs, *tails] if n]

    def box(self, explode: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        c = self.centre + self.explode * explode
        return c - self.size / 2, c + self.size / 2

    @property
    def extent(self) -> float:
        return float(np.max(self.size))


def parts_of(info: dict) -> list[Part]:
    out = []
    for p in info.get("parts", []):
        out.append(Part(p["index"], p["name"], p.get("mesh") or p["name"], p.get("path") or p["name"], int(p.get("triangles", 0)),
                        np.array(p["centre"], float), np.array(p["size"], float),
                        np.array(p.get("explode") or [0, 0, 0], float), bool(p.get("anchor"))))
    return out


def matches(part: Part, pattern: str) -> bool:
    pat = pattern.lower()
    return any(fnmatch.fnmatchcase(n, pat) for n in part.names())


def find(parts: list[Part], pattern: str, what: str = "stop") -> list[Part]:
    """The parts a glob names. A match on part names wins; only when none matches is the mesh, assembly or path
    searched (so `Housing/*` finds every part inside an assembly, and a part's own name never drags in a neighbour)."""
    pat = pattern.lower()
    hit = [p for p in parts if fnmatch.fnmatchcase(p.name.lower(), pat)] or [p for p in parts if matches(p, pattern)]
    if hit:
        return hit
    names = sorted({p.name for p in parts})
    near = difflib.get_close_matches(pattern.strip("*"), names, n=5, cutoff=0.3)
    if not near:
        stem = pattern.strip("*").lower()
        near = [n for n in names if stem and (stem[:4] in n.lower())][:5]
    hint = f" Closest names: {', '.join(near)}." if near else f" The model's parts include: {', '.join(names[:8])}."
    raise BuildError(f"{what}: no part matches {pattern!r} ({len(parts)} parts in the model).{hint} "
                     f"`studio product <project> --parts` lists every name; globs are case-insensitive and also match "
                     f"assembly names ('Housing/*').")


def bounds(parts: list[Part], explode: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    boxes = [p.box(explode) for p in parts]
    return np.min([b[0] for b in boxes], axis=0), np.max([b[1] for b in boxes], axis=0)


# ---------------------------------------------------------------- automatic stops

def _stem(name: str) -> str:
    name = re.sub(r"\.\d+$", "", name)
    return re.sub(r"[_\-. ]*\d+$", "", name)


def _pretty(name: str) -> str:
    s = _stem(name.split("/")[-1])
    s = re.sub(r"^(LFR\d+|GFW\d+|FW|SF)[_-]", "", s, flags=re.I)
    s = re.sub(r"[_\-]+", " ", s).strip()
    return (s[:1].upper() + s[1:].lower()) if s else name


def auto_stops(parts: list[Part], n: int, scene_id: str = "inside") -> list[InsideStop]:
    """Stops for a model whose spec names none: the most distinct named parts, in a tour order. Parts that share a
    name stem (a keyboard's keys) are one stop, framed together."""
    if len(parts) < 2:
        raise BuildError(f"inside '{scene_id}': the product's model is a single mesh, so there are no named parts to stop "
                         f"at. Give the stops a `point` (a place inside the product, in 0-1 of its bounds), or use a "
                         f"model with several parts (STEP/3MF assemblies and multi-object glTF keep their part names).")
    lo, hi = bounds(parts)
    diag = float(np.linalg.norm(hi - lo))
    groups: dict[str, list[Part]] = {}
    for p in parts:
        if p.extent < 0.02 * diag or p.triangles < 24:
            continue
        groups.setdefault(_stem(p.name) or p.name, []).append(p)
    cands = []
    for stem, ps in groups.items():
        glo, ghi = bounds(ps)
        biggest = max(ps, key=lambda q: q.extent)
        if len(ps) > 1 and float(np.max(ghi - glo)) > 2.5 * biggest.extent:
            ps = [biggest]          # scattered copies (screws, standoffs) are not one place: keep the largest
            glo, ghi = bounds(ps)
        vol = sum(float(np.prod(np.maximum(q.size, 1e-6))) for q in ps)
        cands.append({"stem": stem, "parts": ps, "centre": (glo + ghi) / 2, "ext": float(np.max(ghi - glo)), "vol": vol,
                      "score": (vol ** (1 / 3)) * (1 + 0.15 * math.log(len(ps)))})
    if not cands:
        cands = [{"stem": p.name, "parts": [p], "centre": p.centre, "ext": p.extent, "vol": 1.0, "score": p.extent} for p in parts]
    n = max(1, min(n, len(cands)))
    cands.sort(key=lambda c: -c["score"])
    chosen = [cands[0]]
    while len(chosen) < n:
        def gain(c):
            d = min(float(np.linalg.norm(c["centre"] - k["centre"])) for k in chosen) / diag
            return (d + 0.05) * (c["score"] ** 0.5)
        chosen.append(max((c for c in cands if c not in chosen), key=gain))
    # tour: from the left-most, always to the nearest unvisited stop
    todo = sorted(chosen, key=lambda c: c["centre"][0])
    tour = [todo.pop(0)]
    while todo:
        nxt = min(todo, key=lambda c: float(np.linalg.norm(c["centre"] - tour[-1]["centre"])))
        todo.remove(nxt)
        tour.append(nxt)
    out = []
    for c in tour:
        multi = len(c["parts"]) > 1
        out.append(InsideStop(part=(c["stem"] + "*") if multi else c["parts"][0].name, label=_pretty(c["stem"])))
    return out


# ---------------------------------------------------------------- resolved stops

@dataclass
class Resolved:
    """One stop, resolved against the model."""
    index: int
    label: str
    spec: InsideStop
    parts: list[Part]
    focus_parts: list[Part]
    lo: np.ndarray
    hi: np.ndarray
    aim: np.ndarray
    focus: np.ndarray
    span: float
    lens: float
    fstop: float
    roll: float
    explode: float
    yaw: float
    pitch: float
    distance: float
    cam: np.ndarray
    hold: float
    travel: float

    def describe(self) -> dict:
        return {"label": self.label, "pattern": self.spec.part or f"point {list(self.spec.point)}",
                "parts": [p.name for p in self.parts][:12], "matched": len(self.parts),
                "span_mm": round(self.span * 1000, 1), "lens": self.lens, "fstop": self.fstop,
                "from": {"yaw": round(self.yaw), "pitch": round(self.pitch)}, "distance_mm": round(self.distance * 1000),
                "explode": self.explode}


@dataclass
class Resolution:
    stops: list[Resolved]
    parts: list[Part]
    lo: np.ndarray
    hi: np.ndarray
    notes: list[str] = field(default_factory=list)


def _segment_hits_box(a: np.ndarray, b: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> bool:
    d = b - a
    t0, t1 = 0.0, 1.0
    for i in range(3):
        if abs(d[i]) < 1e-12:
            if a[i] < lo[i] or a[i] > hi[i]:
                return False
        else:
            u0, u1 = (lo[i] - a[i]) / d[i], (hi[i] - a[i]) / d[i]
            if u0 > u1:
                u0, u1 = u1, u0
            t0, t1 = max(t0, u0), min(t1, u1)
            if t0 > t1:
                return False
    return True


def direction(yaw: float, pitch: float) -> np.ndarray:
    y, p = math.radians(yaw), math.radians(pitch)
    return np.array([math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)])


def _wrap(a: float) -> float:
    return (a + 180) % 360 - 180


def _fov(lens: float, aspect: float) -> tuple[float, float]:
    """Horizontal and vertical field of view (radians); aspect is width / height."""
    h = 2 * math.atan(SENSOR / 2 / lens)
    return h, 2 * math.atan(math.tan(h / 2) / aspect)


def resolve(sec: InsideScene, info: dict, stops: Optional[list[InsideStop]] = None, aspect: float = 16 / 9) -> Resolution:
    parts = parts_of(info)
    if not parts:
        raise BuildError(f"inside '{sec.id}': the product's model has no parts (is it empty?)")
    lo, hi = bounds(parts)
    diag = float(np.linalg.norm(hi - lo))
    specs = stops if stops is not None else sec.stops
    notes: list[str] = []
    if not specs:
        n = len([s for s in sec.steps if not s.intro]) or 5
        specs = auto_stops(parts, n, sec.id)
        notes.append(f"no stops in the spec: chose {len(specs)} from the model's parts "
                     f"({', '.join(s.label or s.part for s in specs)})")
    out: list[Resolved] = []
    prev_yaw = WIDE_VIEW[0]
    for i, st in enumerate(specs):
        what = f"inside '{sec.id}' stop {i + 1}"
        explode = float(st.explode if st.explode is not None else sec.explode)
        if st.part is not None:
            hit = find(parts, st.part, what)
            slo, shi = bounds(hit, explode)
            label = st.label or _pretty(hit[0].name if len(hit) == 1 else _stem(hit[0].name) or st.part)
            aim = slo + (shi - slo) * np.array(st.aim)
        else:
            hit = []
            f = np.array(st.point)
            elo, ehi = bounds(parts, explode)
            aim = elo + (ehi - elo) * f
            slo = shi = aim
            label = st.label or f"point {i + 1}"
        focus_parts = find(parts, st.focus, what + " focus") if st.focus else hit
        if st.focus and focus_parts:
            flo, fhi = bounds(focus_parts, explode)
            focus = (flo + fhi) / 2
        else:
            focus = aim
        ext = float(np.max(shi - slo)) if hit else 0.02 * diag
        lens = float(st.lens or sec.lens)
        if st.span is not None:
            span = st.span / 1000.0
        else:
            span = min(max(ext * 1.7, 0.012 * diag), 0.4 * diag)
        fstop = float(st.fstop or sec.fstop)
        # camera side: given, or the clearest way in near the previous side
        yaw, pitch = st.yaw, st.pitch
        dist = span * lens / SENSOR + 0.5 * (float(np.max(shi - slo)) if hit else 0.0) * 0.6
        if yaw is None or pitch is None:
            cy, cp = _choose_side(parts, hit, aim, dist, prev_yaw, st.yaw, st.pitch)
            yaw = cy if yaw is None else yaw
            pitch = cp if pitch is None else pitch
        cam = aim + direction(yaw, pitch) * dist
        out.append(Resolved(i, label, st, hit, focus_parts, slo, shi, aim, focus, span, lens, fstop, float(st.roll), explode,
                            float(yaw), float(pitch), dist, cam, float(st.hold), float(st.travel)))
        prev_yaw = float(yaw)
    return Resolution(out, parts, lo, hi, notes)


def _choose_side(parts: list[Part], target: list[Part], aim: np.ndarray, dist: float, prev_yaw: float,
                 fixed_yaw: Optional[float], fixed_pitch: Optional[float]) -> tuple[float, float]:
    """The side to come in from: open (little in the way), close to where the camera came from, and a camera height
    that reads as a macro shot (15 to 40 degrees)."""
    ids = {p.index for p in target}
    others = [p for p in parts if p.index not in ids]
    yaws = [fixed_yaw] if fixed_yaw is not None else [prev_yaw + d for d in range(-180, 181, 20)]
    pitches = [fixed_pitch] if fixed_pitch is not None else [14, 24, 34, 48, 64]
    lo, hi = bounds(parts)
    diag = float(np.linalg.norm(hi - lo))
    best, best_cost = (prev_yaw, 26.0), 1e9
    for yw in yaws:
        for pt in pitches:
            cam = aim + direction(yw, pt) * dist
            block = 0.0
            for p in others:
                plo, phi = p.box()
                if _segment_hits_box(aim + direction(yw, pt) * dist * 0.05, cam, plo, phi):
                    block += min(1.0, (p.extent / max(dist, 1e-6)) * 0.5 + 0.05) * (1.0 if p.extent > 0.1 * diag else 0.4)
            turn = ((abs(_wrap(yw - prev_yaw)) - 28.0) / 120.0) ** 2
            height = ((pt - 28.0) / 40.0) ** 2
            cost = 1.0 * min(block, 3.0) + 1.6 * turn + 0.5 * height
            if cost < best_cost:
                best, best_cost = (_wrap(yw), float(pt)), cost
    return best


# ---------------------------------------------------------------- the route

def _smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else np.array([0.0, 0.0, 1.0])


@dataclass
class Pose:
    cam: np.ndarray
    target: np.ndarray
    focus: np.ndarray
    lens: float
    fstop: float
    roll: float
    explode: float
    off: float = 1.0         # share of the scene's `offset` (the wide shots sit nearer the middle)


@dataclass
class Segment:
    kind: str                # "hold" | "travel"
    stop: int                # hold: the stop. travel: the stop it arrives at (-1: back to the wide shot)
    t0: float                # screens
    t1: float
    a: Optional[Pose] = None
    b: Optional[Pose] = None
    stop_a: int = -1         # travel: the stop it leaves (-1: the wide shot)


@dataclass
class Plan:
    version: int
    frames: list[dict]
    segments: list[Segment]
    screens: float
    stops: list[Resolved]
    wide: Pose
    windows: list[dict]              # per stop: {"stop", "arrive", "leave", "frame", "copy": [from, to]} in 0-1
    intro_window: Optional[tuple[float, float]]
    outro_window: Optional[tuple[float, float]]
    notes: list[str]

    def digest(self) -> str:
        return hashlib.sha1(json.dumps(self.frames, sort_keys=True).encode()).hexdigest()[:12]

    def describe(self) -> dict:
        return {"screens": round(self.screens, 2), "frames": len(self.frames), "stops": [s.describe() for s in self.stops],
                "windows": self.windows, "intro": self.intro_window, "outro": self.outro_window, "notes": self.notes}


def wide_pose(res: Resolution, aspect: float, offset: float = 0.0) -> Pose:
    lo, hi = res.lo, res.hi
    centre = (lo + hi) / 2
    size = hi - lo
    flat = size[2] < 0.15 * float(np.linalg.norm(size))
    yaw, pitch = (-30.0, 38.0) if flat else WIDE_VIEW
    fh, fv = _fov(WIDE_LENS, aspect)
    fwd = -direction(yaw, pitch)
    right = _unit(np.cross(fwd, [0, 0, 1.0]))
    up = np.cross(right, fwd)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]) - centre
    er = float(np.max(np.abs(corners @ right)))
    eu = float(np.max(np.abs(corners @ up)))
    ed = float(np.max(np.abs(corners @ fwd)))
    fill = min(0.86, 0.95 * (1 - WIDE_OFFSET * offset))      # the product fills this much of the frame, off-centre by the offset
    d = max(er / (math.tan(fh / 2) * fill), eu / (math.tan(fv / 2) * fill)) + ed
    target = centre
    return Pose(target + direction(yaw, pitch) * d, target, centre, WIDE_LENS, 5.6, 0.0, 0.0, WIDE_OFFSET)


def stop_pose(r: Resolved) -> Pose:
    return Pose(r.cam.copy(), r.aim.copy(), r.focus.copy(), r.lens, r.fstop, r.roll, r.explode, 1.0)


def _drift(p: Pose, u: float, sign: float) -> Pose:
    """The camera creeps around and in while it rests: u 0-1 across the hold."""
    off = p.cam - p.target
    th = math.radians(DRIFT_YAW) * sign * (2 * u - 1)
    c, s = math.cos(th), math.sin(th)
    off2 = np.array([off[0] * c - off[1] * s, off[0] * s + off[1] * c, off[2]]) * (1 - DRIFT_PUSH * u)
    return Pose(p.target + off2, p.target.copy(), p.focus.copy(), p.lens, p.fstop, p.roll, p.explode, p.off)


def _travel(a: Pose, b: Pose, u: float) -> Pose:
    s = _smooth(u)
    oa, ob = a.cam - a.target, b.cam - b.target
    out_dir = _unit(_unit(oa) + _unit(ob))
    if float(np.linalg.norm(_unit(oa) + _unit(ob))) < 0.3:
        out_dir = np.array([0.0, 0.0, 1.0])
    span = float(np.linalg.norm(b.cam - a.cam))
    ctrl = (a.cam + b.cam) / 2 + out_dir * span * 0.28
    cam = (1 - s) ** 2 * a.cam + 2 * (1 - s) * s * ctrl + s ** 2 * b.cam
    # the look point leads the camera a little, so the move reads as a glance ahead
    sl = _smooth(min(1.0, u * 1.12 + 0.02))
    target = a.target + (b.target - a.target) * sl
    focus = a.focus + (b.focus - a.focus) * s
    lens = math.exp(math.log(a.lens) + (math.log(b.lens) - math.log(a.lens)) * s)
    fstop = math.exp(math.log(a.fstop) + (math.log(b.fstop) - math.log(a.fstop)) * s)
    fstop *= 1 + 0.9 * math.sin(math.pi * s)          # the aperture closes in flight: more stays sharp while things rush past
    return Pose(cam, target, focus, lens, fstop, a.roll + (b.roll - a.roll) * s, a.explode + (b.explode - a.explode) * s,
                a.off + (b.off - a.off) * s)


def make_plan(sec: InsideScene, res: Resolution, aspect: float = 16 / 9) -> Plan:
    stops = res.stops
    wide = wide_pose(res, aspect, sec.offset)
    segs: list[Segment] = []
    t = 0.0

    def hold(i: int, dur: float) -> Segment:
        nonlocal t
        p = stop_pose(stops[i])
        sign = 1.0 if i % 2 == 0 else -1.0
        s = Segment("hold", i, t, t + dur, _drift(p, 0.0, sign), _drift(p, 1.0, sign))
        t += dur
        return s

    if sec.establish:
        segs.append(Segment("hold", -1, t, t + 0.7, wide, wide))
        t += 0.7
    for i, st in enumerate(stops):
        if i == 0 and not sec.establish:
            pass
        else:
            a = segs[-1].b
            b = _drift(stop_pose(st), 0.0, 1.0 if i % 2 == 0 else -1.0)
            segs.append(Segment("travel", i, t, t + st.travel, a, b, stop_a=segs[-1].stop))
            t += st.travel
        segs.append(hold(i, st.hold))
    if sec.outro == "wide":
        segs.append(Segment("travel", -1, t, t + 1.3, segs[-1].b, wide, stop_a=len(stops) - 1))
        t += 1.3
        segs.append(Segment("hold", -1, t, t + 0.6, wide, wide))
        t += 0.6
    total = t
    n = max(8, int(round(total * sec.density)))
    frames = []
    for k in range(n):
        tau = total * k / (n - 1)
        seg = next((s for s in segs if tau <= s.t1 + 1e-9), segs[-1])
        u = (tau - seg.t0) / max(seg.t1 - seg.t0, 1e-9)
        if seg.kind == "hold":
            pose = Pose(seg.a.cam + (seg.b.cam - seg.a.cam) * u, seg.a.target + (seg.b.target - seg.a.target) * u,
                        seg.a.focus.copy(), seg.a.lens, seg.a.fstop, seg.a.roll, seg.a.explode, seg.a.off)
            near = seg.stop
        else:
            pose = _travel(seg.a, seg.b, u)
            near = seg.stop if u >= 0.5 else seg.stop_a
        frames.append({"k": k, "p": round(k / (n - 1), 6), "cam": _r(pose.cam), "target": _r(pose.target), "focus": _r(pose.focus),
                       "lens": round(pose.lens, 3), "fstop": round(pose.fstop, 3), "roll": round(pose.roll, 3),
                       "explode": round(pose.explode, 4), "off": round(pose.off, 4), "stop": int(near), "rest": seg.kind == "hold" and seg.stop >= 0})
        if sec.light:            # only then: a flight with one light keeps the frames (and frame caches) it always had
            frames[-1]["light"] = light_at(sec, k / (n - 1))
    windows, intro, outro = _windows(segs, stops, total, n, sec)
    return Plan(VERSION, frames, segs, total, stops, wide, windows, intro, outro, res.notes)


def _hex_lin(h: str) -> np.ndarray:
    c = np.array([int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lin_hex(c: np.ndarray) -> str:
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)
    return "#" + "".join(f"{int(round(float(np.clip(v, 0, 1)) * 255)):02x}" for v in s)


def light_at(sec: InsideScene, p: float) -> dict:
    """The flight's light at scene progress p: each value eased between the keys that set it (the scene's own value
    where no key does), held before the first key and after the last. Colours blend in linear light."""
    out = {}
    for name in ("exposure", "ambient", "lamp", "rim", "lamp_color"):
        keys = [(k.at, getattr(k, name)) for k in sec.light if getattr(k, name) is not None]
        own = getattr(sec, name)
        if not keys:
            out[name] = own
            continue
        if name == "lamp_color":
            keys = [(a, _hex_lin(v)) for a, v in keys]
        if p <= keys[0][0]:
            v = keys[0][1]
        elif p >= keys[-1][0]:
            v = keys[-1][1]
        else:
            i = next(j for j in range(1, len(keys)) if p <= keys[j][0])
            (a0, v0), (a1, v1) = keys[i - 1], keys[i]
            s = _smooth((p - a0) / max(a1 - a0, 1e-9))
            v = v0 + (v1 - v0) * s
        out[name] = _lin_hex(v) if name == "lamp_color" else round(float(v), 4)
    return out


def _r(v: np.ndarray) -> list[float]:
    return [round(float(x), 6) for x in v]


def _windows(segs: list[Segment], stops: list[Resolved], total: float, n: int, sec: InsideScene):
    def prog(x: float) -> float:
        return round(min(1.0, max(0.0, x / total)), 5)
    windows = []
    for i, st in enumerate(stops):
        h = next(s for s in segs if s.kind == "hold" and s.stop == i)
        tin = next((s for s in segs if s.kind == "travel" and s.stop == i), None)
        tout = next((s for s in segs if s.kind == "travel" and s.stop_a == i), None)
        c0 = h.t0 - (EDGE_WINDOW * (tin.t1 - tin.t0) if tin else 0.0)
        c1 = h.t1 + (EDGE_WINDOW * (tout.t1 - tout.t0) if tout else 0.0)
        mid = (h.t0 + h.t1) / 2
        windows.append({"stop": i, "label": st.label, "arrive": prog(h.t0), "leave": prog(h.t1),
                        "frame": int(round(mid / total * (n - 1))), "copy": [prog(c0), prog(c1) if tout or sec.outro == "wide" else 1.0]})
    first = segs[0]
    intro = None
    if first.kind == "hold" and first.stop == -1:
        tin = next((s for s in segs if s.kind == "travel" and s.stop == 0), None)
        intro = (0.0, prog(first.t1 + (0.3 * (tin.t1 - tin.t0) if tin else 0.0)))
    outro = None
    if sec.outro == "wide":
        back = segs[-2]
        outro = (prog(back.t0 + (back.t1 - back.t0) * 0.55), 1.0)
    return windows, intro, outro


# ---------------------------------------------------------------- the copy

def schedule_steps(steps, plan: Plan, outro: str = "wide") -> list[dict]:
    """Give steps without an `at` their place on the route: leading `intro` steps share the opening wide shot, the
    next steps go to the stops in order, the rest share the pull-back (or the last stop's rest, when the route ends
    there). Returns what was scheduled, per step."""
    intro = [s for s in steps if s.intro]
    rest = [s for s in steps if not s.intro]
    n = len(plan.windows)
    done = []

    def share(items, lo, hi):
        if not items:
            return
        gap = 0.012 if len(items) > 1 else 0.0
        w = (hi - lo) / len(items)
        for j, s in enumerate(items):
            if window(s) is None:
                set_window(s, round(lo + j * w + (gap if j else 0), 4), round(lo + (j + 1) * w - gap, 4))
                done.append({"title": s.title, "at": list(window(s))})

    if intro:
        a, b = plan.intro_window or (0.0, plan.windows[0]["copy"][0])
        share(intro, a, max(b - 0.004, a + 0.01))
    for i, s in enumerate(rest[:n]):
        w = plan.windows[i]["copy"]
        lo = w[0]
        hi = w[1]
        # neighbours never overlap: end a little before the next stop's copy begins
        if i + 1 < n:
            hi = min(hi, plan.windows[i + 1]["copy"][0] - 0.004)
        if window(s) is None:
            set_window(s, round(lo, 4), round(max(hi, lo + 0.01), 4))
            done.append({"title": s.title, "at": list(window(s))})
    extra = rest[n:]
    if extra:
        if outro == "wide" and plan.outro_window:
            a, b = plan.outro_window
            a = max(a, plan.windows[-1]["copy"][1] + 0.004)
            share(extra, a, b)
        else:
            w = plan.windows[-1]
            share(extra, w["arrive"] + (w["leave"] - w["arrive"]) * 0.5, 1.0)
    return done
