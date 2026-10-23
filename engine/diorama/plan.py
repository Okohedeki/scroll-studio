"""From a `diorama` scene to a plan the page draws: the world's ground and props, the resolved places, and the camera's
beats (one per step: the world seen whole, or a dive to a place) with where in the scroll each rests."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import recipes, recipes2
from .recipes import HERO, WATER_KINDS, dress, pal_of, resolve_where, snap_free, face_default
from .world import GRID, World

VERSION = 1
DEFAULT_SIZE = {"harbour": 30.0, "town": 30.0, "desk": 22.0, "factory": 26.0, "studio": 22.0}


def _base_of(sec) -> str:
    return sec.world.base or ("round" if sec.world.kind in ("harbour", "town") else "square")


def step_windows(steps) -> list[tuple[float, float]]:
    """Where each step sits in the scene's progress (0-1): its share of the scroll, as the page lays the cards out."""
    total = sum(s.length for s in steps) or 1.0
    out, acc = [], 0.0
    for s in steps:
        out.append((acc / total, (acc + s.length) / total))
        acc += s.length
    return out


def resolve_places(w: World, sec, pal, rng) -> list[dict]:
    spots = dict(w.spots)
    used: set[str] = set()
    placed: list[dict] = []
    for i, pl in enumerate(sec.places):
        kind = pl.kind
        spot = None
        loc = resolve_where(w, pl.where, spots)
        if loc is not None:
            x, z, face = loc
            for name, sp in spots.items():
                if abs(sp.x - x) < 1e-6 and abs(sp.z - z) < 1e-6:
                    spot = sp
                    used.add(name)
        else:
            face = None
            want = [sp for n, sp in spots.items() if n not in used and (kind is None or kind in sp.kinds)
                    and (sp.water == (kind in WATER_KINDS))]
            if not want:
                want = [sp for n, sp in spots.items() if n not in used and not sp.water]
            if want:
                spot = want[0]
                used.add(spot.name)
                x, z, face = spot.x, spot.z, spot.face
            else:
                a = 2 * math.pi * i / max(len(sec.places), 1) + 0.6
                x, z = math.cos(a) * w.R * 0.55, math.sin(a) * w.R * 0.55
        if kind is None:
            kind = spot.kinds[0] if spot is not None and spot.kinds else "house"
        h, r = HERO.get(kind, (3.0, 2.0))
        water_kind = kind in WATER_KINDS
        if loc is not None and spot is None or (spot is None and loc is None):
            x, z = snap_free(w, x, z, r * pl.scale * 0.7, water_ok=water_kind)
        yaw = face if face is not None else face_default(w, x, z, water_pref=not water_kind)
        if pl.where is not None and not isinstance(pl.where, str) and face is None:
            yaw = face_default(w, x, z)
        rec = {"name": pl.name, "kind": kind, "x": x, "z": z, "yaw": yaw, "scale": pl.scale, "h": h * pl.scale,
               "r": r * pl.scale, "step": pl.step, "side": pl.side, "sign": pl.sign or pl.name, "color": pl.color}
        placed.append(rec)
    # the heroes first (they reserve their ground), then each place's dressing and sign
    for pl in placed:
        w.add(pl["kind"], pl["x"], pl["z"], pl["yaw"], pl["scale"], pl["color"], 0, pl["r"] * 0.9, place=placed.index(pl))
    for pl in placed:
        dress(sec.world.kind, w, pl, pal, rng)
        sx, sz = recipes.local(pl["x"], pl["z"], pl["yaw"], -(pl["r"] + 1.1), min(pl["r"] * 0.15, 0.6) + 0.3)
        if not w.inside_pt(sx, sz, 0.3) or (w.water_at(sx, sz) and pl["kind"] not in WATER_KINDS):
            sx, sz = recipes.local(pl["x"], pl["z"], pl["yaw"], (pl["r"] + 1.1), min(pl["r"] * 0.15, 0.6) + 0.3)
        w.add("sign", sx, sz, pl["yaw"], 1.05 + 0.1 * min(pl["scale"], 2), None, 0, 0.4, text=pl["sign"], of=placed.index(pl))
    # the view cone in front of each hero stays free of scenery, so the camera has a clear look at it
    for pl in placed:
        if pl["kind"] in WATER_KINDS:
            continue
        for off in (-20, 0, 20):
            a = pl["yaw"] + math.radians(off)
            for d in (pl["r"] + 2.6, pl["r"] + 5.0):
                w.occ.append((pl["x"] + math.sin(a) * d, pl["z"] + math.cos(a) * d, 1.0))
    return placed


def assign_steps(sec, placed: list[dict]) -> list[Optional[int]]:
    """For each step: the index of the place it lives at, or None for a wide beat (an intro, a closing step)."""
    n = len(sec.steps)
    out: list[Optional[int]] = [None] * n
    taken: set[int] = set()
    for pi, pl in enumerate(placed):
        if pl["step"] is not None and pl["step"] < n:
            out[pl["step"]] = pi
            taken.add(pi)
    # steps that name a place in their state
    names = {pl["name"].lower(): pi for pi, pl in enumerate(placed)}
    for si, st in enumerate(sec.steps):
        nm = str((st.state or {}).get("place", "")).lower()
        if nm and nm in names and out[si] is None and names[nm] not in taken:
            out[si] = names[nm]
            taken.add(names[nm])
    rest = [pi for pi in range(len(placed)) if pi not in taken]
    for si, st in enumerate(sec.steps):
        if out[si] is None and not st.intro and rest and not (st.state or {}).get("wide"):
            out[si] = rest.pop(0)
    return out


# height and footprint radius of what can stand between the camera and a place (world units at scale 1)
BLOCKERS = {"tree": (2.2, 0.7), "pine": (2.0, 0.6), "house": (3.0, 1.2), "shop": (3.6, 1.4), "cafe": (3.4, 1.4), "warehouse": (2.7, 2.3),
            "office": (3.8, 1.6), "container": (1.1, 1.3), "lighthouse": (8.6, 1.2), "windmill": (7.0, 1.4), "crane": [(5.2, 1.9, 0, 0), (5.7, 1.4, 0, 2.0), (5.7, 1.4, 0, 4.5), (5.7, 1.4, 0, 7.0)],
            "stall": (2.2, 1.0), "tank": (5.0, 1.8), "silo": (7.0, 1.5), "chimney": (9.0, 0.9), "clocktower": (8.0, 1.3), "ferry": (3.0, 1.8),
            "monitor": (3.0, 1.6), "laptop": (1.5, 1.8), "sofa": (2.0, 2.0), "shelf": (4.2, 1.5), "softbox": (5.0, 1.0), "easel": (4.2, 1.3),
            "plant": (2.6, 1.0), "deskLamp": (3.8, 0.8), "robot": (3.8, 1.4), "conveyor": (1.8, 2.2), "boat": (1.5, 0.9), "fountain": (2.2, 1.5)}


# how far from its front a kind of hero reads best (a crane's boom wants a profile, a stall a three-quarter view)
PREFER = {"crane": 64.0, "conveyor": 50.0, "robot": 40.0, "windmill": 30.0, "ferry": 45.0, "boat": 45.0, "easel": 32.0}
OFFSETS = (-84, -72, -64, -56, -42, -30, -18, -6, 0, 6, 18, 30, 42, 56, 64, 72, 84)


def yaw_options(w: World, pl: dict, target, dist: float, pitch: float, base_deg: float, prefer: float) -> list[tuple[float, float]]:
    """Camera azimuths near `base_deg` (the place's front) and what each costs: how much of the sight line to the place,
    and of a cone round it, is blocked by tall things, whether the camera would leave the base, and a little for turning
    away from the preferred three-quarter view."""
    tx, ty, tz = target
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    own = (pl["x"], pl["z"])
    blockers = []
    for p in w.props:
        spec = BLOCKERS.get(p["k"])
        if spec is None or (abs(p["x"] - own[0]) < 1e-6 and abs(p["z"] - own[1]) < 1e-6):
            continue
        for h, r, dx, dz, *ymin in (spec if isinstance(spec, list) else [(*spec, 0, 0)]):
            bx = p["x"] + (dz * math.sin(p["r"]) + dx * math.cos(p["r"])) * p["s"]
            bz = p["z"] + (dz * math.cos(p["r"]) - dx * math.sin(p["r"])) * p["s"]
            lo = (ymin[0] if ymin else 0.0) * p["s"]
            blockers.append((bx, bz, p["y"] + lo, h * p["s"], r * p["s"]))
    out = []
    for off in OFFSETS:
        yaw = math.radians(base_deg + off)
        cx, cy, cz = tx + dist * math.sin(yaw) * cp, ty + dist * sp, tz + dist * math.cos(yaw) * cp
        blocked = 0.0
        px, pz = -math.cos(yaw), math.sin(yaw)         # sideways, for the edges of the view cone
        for lat in (-3.0, 0.0, 3.0):
            for k in range(2, 38):
                t = k / 40
                x, y, z = tx + (cx - tx) * t + px * lat * t, ty + (cy - ty) * t, tz + (cz - tz) * t + pz * lat * t
                for bx, bz, by, bh, br in blockers:
                    if (x - bx) ** 2 + (z - bz) ** 2 < br * br and by <= y < by + bh:
                        blocked += 1.0 if lat == 0 else 0.6
                        break
        # tall things close to the lens and inside the picture become big blurred shapes in the corner of the frame
        near = 0.0
        view = math.atan2(tx - cx, tz - cz)
        for bx, bz, by, bh, br in blockers:
            d = math.hypot(bx - cx, bz - cz)
            if bh < 2.6 or d > dist * 0.8 or d < 1e-6:
                continue
            ang = abs((math.atan2(bx - cx, bz - cz) - view + math.pi) % (2 * math.pi) - math.pi)
            if ang < math.radians(26) and by + bh > cy - 2.0:
                near += 1.0 - d / (dist * 0.8)
        out.append((base_deg + off, 0.5 * blocked + 1.4 * near + 0.03 * abs(abs(off) - abs(prefer))))
    return out


def _turn(a: float, b: float, mode: str) -> float:
    """Degrees the camera swings going from azimuth a to b: the short way, or always one way round."""
    d = (b - a) % 360.0
    if mode == "ccw":
        return d
    if mode == "cw":
        return d - 360.0 if d > 1e-6 else 0.0
    return d - 360.0 if d > 180.0 else d


def choose_yaws(options: list[list[tuple[float, float]]], mode: str) -> list[float]:
    """The azimuth for each place, in order: cheapest sight lines overall, and the least swinging between places
    (a Viterbi pass over every place's options)."""
    if not options:
        return []
    cost = [[c for _, c in options[0]]]
    back: list[list[int]] = [[0] * len(options[0])]
    for i in range(1, len(options)):
        row, br = [], []
        for yj, cj in options[i]:
            best, bk = 1e18, 0
            for k, (yk, _) in enumerate(options[i - 1]):
                tot = cost[i - 1][k] + 0.005 * abs(_turn(yk, yj, mode))
                if tot < best:
                    best, bk = tot, k
            row.append(best + cj)
            br.append(bk)
        cost.append(row)
        back.append(br)
    k = min(range(len(cost[-1])), key=lambda j: cost[-1][j])
    path = [k]
    for i in range(len(options) - 1, 0, -1):
        k = back[i][k]
        path.append(k)
    path.reverse()
    return [options[i][k][0] for i, k in enumerate(path)]


def camera_plan(w: World, sec, placed: list[dict], stepmap: list[Optional[int]]) -> dict:
    cam = sec.camera
    tan_half = math.tan(math.radians(cam.fov) / 2)
    beats = []
    prev_yaw: Optional[float] = None
    view_side = 1 if sec.side == "right" else -1
    if sec.layout == "overlay":
        view_side = 1
    framing: dict[int, tuple] = {}
    options = []
    order = [pi for pi in stepmap if pi is not None]
    for n, pi in enumerate(order):
        pl = placed[pi]
        gy = w.height_at(pl["x"], pl["z"])
        fr = max(2.6 * pl["r"], min(pl["h"], 9.0) + 1.6)
        dist = fr / (0.72 * 2 * tan_half) / cam.dive
        tgt = (pl["x"], gy + min(pl["h"], 9.0) * 0.44, pl["z"])
        framing[pi] = (gy, dist, tgt)
        options.append(yaw_options(w, pl, tgt, dist, cam.dive_pitch, math.degrees(pl["yaw"]), PREFER.get(pl["kind"], 24.0)))
    chosen = dict(zip(order, choose_yaws(options, cam.orbit)))
    for si, pi in enumerate(stepmap):
        if pi is not None:
            pl = placed[pi]
            gy, dist, tgt = framing[pi]
            yaw = chosen[pi]
            side = {"left": -1, "right": 1}.get(pl["side"] or "", view_side)
            cap = sec.steps[si].place if sec.layout == "overlay" else None
            if cap and not pl["side"]:        # a caption set on the left leaves the world the right of the picture
                side = -1 if cap.endswith("right") else 1 if cap.endswith("left") else side
            beats.append({"kind": "place", "place": pi, "yaw": yaw, "pitch": cam.dive_pitch, "dist": round(dist, 2),
                          "target": [round(pl["x"], 3), round(gy + min(pl["h"], 9.0) * 0.44, 3), round(pl["z"], 3)],
                          "side": side})
        else:
            beats.append({"kind": "wide", "yaw": None, "pitch": cam.pitch, "dist": None, "target": [0, 0.5, 0], "side": 0})
    # wide beats take their yaw from the neighbours: before the first place, 38 degrees behind it; after, 38 past it
    place_idx = [i for i, b in enumerate(beats) if b["kind"] == "place"]
    if place_idx:
        first, last = place_idx[0], place_idx[-1]
        for i, b in enumerate(beats):
            if b["kind"] != "wide":
                continue
            if i < first:
                b["yaw"] = beats[first]["yaw"] - 38.0
            elif i > last:
                b["yaw"] = beats[last]["yaw"] + 38.0
            else:
                lo = max(j for j in place_idx if j < i)
                hi = min(j for j in place_idx if j > i)
                b["yaw"] = (beats[lo]["yaw"] + beats[hi]["yaw"]) / 2
    else:
        for b in beats:
            b["yaw"] = 20.0
    # unwrap the yaws into one continuous orbit
    for b in beats:
        y = b["yaw"]
        if prev_yaw is None:
            b["yaw"] = round(y, 2)
        else:
            d = (y - prev_yaw) % 360.0
            if cam.orbit == "ccw":
                pass
            elif cam.orbit == "cw":
                d = d - 360.0 if d > 1e-6 else 0.0
            else:
                d = d - 360.0 if d > 180.0 else d
            b["yaw"] = round(prev_yaw + d, 2)
        prev_yaw = b["yaw"]
    wins = step_windows(sec.steps)
    for b, (a, c) in zip(beats, wins):
        b["a"], b["b"] = round(a, 5), round(c, 5)
    return {"fov": cam.fov, "pitch": cam.pitch, "dive_pitch": cam.dive_pitch, "hold": cam.hold, "drift": cam.drift,
            "fit": round(w.R * 1.14, 2), "beats": beats}


def seat_signs(w: World, placed: list[dict], camera: dict):
    """Each place's sign goes beside it as the camera sees it (towards the copy, facing the lens), so it is in the focal
    plane and readable when the camera has dived in."""
    by_place = {b["place"]: b for b in camera["beats"] if b["kind"] == "place"}
    for p in w.props:
        if p["k"] != "sign" or p.get("of") not in by_place:
            continue
        pl = placed[p["of"]]
        b = by_place[p["of"]]
        th = math.radians(b["yaw"])
        rx, rz = math.cos(th), -math.sin(th)            # the camera's right, on the ground
        fx, fz = math.sin(th), math.cos(th)             # towards the camera
        water_kind = pl["kind"] in WATER_KINDS
        for sd in ((1, -1) if b["side"] >= 0 else (-1, 1)):
            d = pl["r"] * 0.7 + 1.0
            x, z = pl["x"] + rx * sd * d + fx * 0.5, pl["z"] + rz * sd * d + fz * 0.5
            if w.inside_pt(x, z, 0.4) and (water_kind or not w.water_at(x, z)):
                p["x"], p["z"], p["r"] = round(x, 3), round(z, 3), round(th, 3)
                p["y"] = round(max(w.height_at(x, z), w.water_level), 3)
                break
        p.pop("of", None)


def build(sec, table: str, draft: bool = False):
    """The whole plan and the ground texture (uint8 N x N x 3) for a diorama scene."""
    wd = sec.world
    kind = wd.kind
    size = wd.size or DEFAULT_SIZE[kind]
    w = World(size, _base_of(sec), wd.seed, wd.density, draft)
    pal = pal_of(w, wd.palette, kind)
    rng = np.random.default_rng(wd.seed + 101)
    info = recipes.setup(kind, w, pal, wd)
    placed = resolve_places(w, sec, pal, rng)
    recipes.fill(kind, w, pal, info, rng)
    for ex in wd.props:
        w.add(ex.kind, ex.at[0], ex.at[1], math.radians(ex.turn), ex.scale, ex.color, 0, 0.5 * ex.scale)
    w.finish_props()
    for pl in placed:
        pl["y"] = round(w.height_at(pl["x"], pl["z"]), 3)
    stepmap = assign_steps(sec, placed)
    camera = camera_plan(w, sec, placed, stepmap)
    seat_signs(w, placed, camera)
    w.bake_ao()
    hg = w.height_grid(GRID)
    plan = {
        "v": VERSION, "kind": kind, "size": size, "base": w.base, "table": table,
        "water": {"level": w.water_level, "has": bool(w.has_water)},
        "grid": GRID, "heights": [round(float(v), 2) for v in hg.reshape(-1)],
        "palette": pal, "edge": recipes2.EDGES.get(kind),
        "props": w.props,
        "places": [{"name": p["name"], "kind": p["kind"], "x": round(p["x"], 3), "y": p["y"], "z": round(p["z"], 3),
                    "yaw": round(p["yaw"], 3), "h": round(p["h"], 2), "r": round(p["r"], 2), "sign": p["sign"]} for p in placed],
        "steps": stepmap,
        "camera": camera,
    }
    return plan, w.texture(), w
