"""World recipes, part two: the town, the desk, the factory floor and the studio. Same contract as recipes.py: `setup`
(heights, ground paint, named spots), `fill` (scenery) and `dress` (what stands round each place)."""
from __future__ import annotations

import math

import numpy as np

from .fields import box_sdf, hex_rgb, segment_sdf, smoothstep
from .recipes import (WALLS, D, paint_cobbles, paint_grass, paint_path, paint_rect, paint_water_bed)
from .world import Spot, World, yaw_of

EDGES = {
    "harbour": None, "town": None,
    "desk": {"lip": "#c99a63", "soil": "#b4824d", "clay": "#a47340", "stone": "#8d6236", "plinth": "#6d4a2c", "plinthTop": "#8a6038"},
    "factory": {"lip": "#c9ccd0", "soil": "#b5b9be", "clay": "#9fa4aa", "stone": "#7e848b", "plinth": "#4a5058", "plinthTop": "#6a727b"},
    "studio": {"lip": "#e3c496", "soil": "#cfa974", "clay": "#b98f5c", "stone": "#8f6a40", "plinth": "#3a3f47", "plinthTop": "#555c66"},
}


def paint_road(w: World, pts, width=1.9, color="#5e6268", dashes=True, edge="#efeae0"):
    """A street along a polyline: a light kerb, asphalt, and a dashed middle line."""
    import cv2
    kerb = w.polyline(pts, width + 0.5)
    road = w.polyline(pts, width)
    land = (~w.water).astype(np.float32) if w.has_water else 1.0
    n = w.noise(90, 2, 9)
    w.blend(cv2.GaussianBlur(kerb, (0, 0), 0.7) * land, edge, 0.95)
    w.blend_map(cv2.GaussianBlur(road, (0, 0), 0.7) * land, hex_rgb(color) * (0.94 + 0.1 * n[..., None]))
    if dashes:
        pl = np.array(pts, float)
        seglen = np.hypot(*(pl[1:] - pl[:-1]).T)
        total = seglen.sum()
        samples = np.linspace(0, total, int(total / 0.55) + 1)
        cum = np.concatenate([[0], np.cumsum(seglen)])
        xs = np.interp(samples, cum, pl[:, 0])
        zs = np.interp(samples, cum, pl[:, 1])
        canvas = np.zeros((w.N, w.N), np.uint8)
        for i in range(0, len(xs) - 1, 2):
            w.polyline([(xs[i], zs[i]), (xs[i + 1], zs[i + 1])], 0.11, canvas=canvas)
        d = canvas.astype(np.float32) / 255
        w.blend(cv2.GaussianBlur(d, (0, 0), 0.6) * road * land, "#f4ead0", 0.95)
    w.road = np.maximum(w.road, road * land)
    return road


def paint_wood(w: World, base="#c58f56", plank=3.0, dark=0.82):
    """Planks of wood grain running along x: a desk top or a studio floor."""
    import cv2
    N = w.N
    rng = np.random.default_rng(w.seed + 5)
    g = rng.random((max(8, N // 64), N // 3)).astype(np.float32)
    g = cv2.resize(g, (N, N), interpolation=cv2.INTER_CUBIC)       # long streaks along x
    g2 = cv2.resize(rng.random((N // 12, N // 24)).astype(np.float32), (N, N), interpolation=cv2.INTER_CUBIC)
    row = np.floor((w.Z + w.R) / plank)
    tone = np.mod(np.sin(row * 12.9898) * 43758.5453, 1.0)
    seam = smoothstep(0.045, 0.01, np.abs(np.mod(w.Z + w.R, plank) - 0.0)) + smoothstep(0.045, 0.01, np.abs(np.mod(w.Z + w.R, plank) - plank))
    col = hex_rgb(base) * (0.9 + 0.14 * g[..., None] + 0.08 * g2[..., None] + (tone[..., None] - 0.5) * 0.12)
    col = col * (1 - np.clip(seam, 0, 1)[..., None] * (1 - dark))
    w.col = col.astype(np.float32)


def paint_concrete(w: World, base="#c4c7cb", cell=5.0):
    n1 = w.noise(6, 3, 2)
    n2 = w.noise(120, 2, 4)
    col = hex_rgb(base) * (0.93 + 0.1 * n1[..., None] + 0.05 * n2[..., None])
    joints = smoothstep(0.04, 0.01, np.abs(np.mod(w.X + w.R, cell) - 0.0)) + smoothstep(0.04, 0.01, np.abs(np.mod(w.Z + w.R, cell) - 0.0))
    w.col = (col * (1 - np.clip(joints, 0, 1)[..., None] * 0.14)).astype(np.float32)


def paint_hazard(w: World, cx, cz, hx, hz, line=0.22):
    """A rectangle of yellow safety line."""
    sdf = box_sdf(w.X, w.Z, cx, cz, hx, hz, 0)
    m = smoothstep(line / 2 + w.px, line / 2 - w.px, np.abs(sdf + line))
    w.blend(m, "#f2c230", 0.95)


def _rect_keep(w: World, cx, cz, hx, hz, pad=0.3):
    sdf = box_sdf(w.X, w.Z, cx, cz, hx, hz, 0)
    w.keep = np.maximum(w.keep, smoothstep(pad, -pad, sdf))


# ---------------------------------------------------------------- town

def town(w: World, pal, spec_world):
    k = w.R / 15.0
    P = lambda x, z: (x * k, z * k)
    X, Z = w.X, w.Z
    # a river from the west edge, curving to the front edge; a hill with the windmill behind
    rpts = [P(-17, 6.5), P(-9, 7.2), P(-3.5, 9.5), P(1.0, 12.0), P(3.5, 17)]
    river = np.minimum.reduce([segment_sdf(X, Z, a, b, 1.15 * k) for a, b in zip(rpts, rpts[1:])]) + (w.noise(8, 2, 21) - 0.5) * 0.5 * k
    hill = 1.5 * np.exp(-(((X - 9.5 * k) ** 2 + (Z - (-9.0 * k)) ** 2) / (2 * (3.0 * k) ** 2)))
    hill2 = 0.7 * np.exp(-(((X - (-8.5 * k)) ** 2 + (Z - (-8.5 * k)) ** 2) / (2 * (3.4 * k) ** 2)))
    w.h = (hill + hill2 + (w.noise(4, 2, 31) - 0.5) * 0.1 - 1.2 * smoothstep(0.4, -0.3, river)).astype(np.float32)
    w.h[~w.inside] = np.minimum(w.h[~w.inside], 0.0)
    w.finish_terrain()
    paint_grass(w, "#93c862", "#7fb653")
    paint_water_bed(w, "#8ad7e6", "#2d8cbc")
    sand = smoothstep(1.2, 0.1, w.dw) * (~w.water)
    w.blend(sand.astype(np.float32), "#ecd8a2")
    w.blend(smoothstep(0.16, 0.0, np.abs(w.dw)) * 0.6, "#ffffff")
    # streets: a main street across, a cross street, a ring round the square
    main = [P(-15, 0.8), P(-8, 0.5), P(0, 1.0), P(8, 0.6), P(15, 1.4)]
    cross = [P(1.5, -15), P(1.0, -7), P(0.2, 0.8), P(-0.6, 7.6)]
    side = [P(-15, -6.5), P(-8, -5.8), P(-2.5, -5.2), P(1.0, -5.0)]
    for pts, wd in ((main, 2.0), (cross, 1.9), (side, 1.6)):
        paint_road(w, pts, wd * k ** 0)
    cx, cz = P(0.4, 0.9)
    paint_cobbles(w, cx, cz, 3.0 * k, "#d4c7b0", "#b3a68f")
    w.bay = (cx, cz)
    w.streets = [main, cross, side]
    # park: a lawn a shade lighter, with a path
    paint_path(w, [P(-12, -11), P(-8, -9), P(-5.5, -8.4)], 0.8)
    spots = [
        Spot("square", cx, cz, yaw_of(0.2, 1.0), ("fountain", "clocktower")),
        Spot("tower", *P(0.8, -3.6), yaw_of(0.0, 1.0), ("clocktower", "office")),
        Spot("street", *P(-6.0, 3.6), yaw_of(0.0, -1.0), ("shop", "cafe")),
        Spot("market", *P(7.0, 3.6), yaw_of(-0.3, -1.0), ("stall", "cafe")),
        Spot("mill", *P(9.5, -9.0), yaw_of(-0.3, 1.0), ("windmill",)),
        Spot("hall", *P(-8.5, -8.0), yaw_of(0.4, 1.0), ("office", "shop")),
        Spot("river", *P(-6.8, 9.8), yaw_of(0.1, -1.0), ("cafe", "shop")),
        Spot("park", *P(10.8, 8.2), yaw_of(-0.7, -0.6), ("fountain", "stall")),
    ]
    w.spots = {s.name: s for s in spots}
    return {"k": k}


def town_fill(w: World, pal, info, rng):
    k = info["k"]
    dens = w.density
    # the bridge where the main street crosses the river
    for pts in w.streets:
        for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
            for t in np.linspace(0, 1, 30):
                x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
                if w.water_at(x, z) and not any(abs(b["x"] - x) < 3 and abs(b["z"] - z) < 3 for b in w.props if b["k"] == "bridge"):
                    yaw = math.atan2(x1 - x0, z1 - z0)
                    w.add("bridge", x, z, yaw, 1.0, None, 0, 0.1, dy=0.0, len=4.6)
    # houses along the streets, facing them
    def line_houses(pts, spacing, side_off, n_skip=0):
        pl = np.array(pts, float)
        seg = np.hypot(*(pl[1:] - pl[:-1]).T)
        cum = np.concatenate([[0], np.cumsum(seg)])
        for s in np.arange(1.8, cum[-1] - 1.0, spacing):
            xs, zs = np.interp(s, cum, pl[:, 0]), np.interp(s, cum, pl[:, 1])
            i = min(int(np.searchsorted(cum, s) - 1), len(pts) - 2)
            tx, tz = pl[i + 1] - pl[i]
            tn = math.hypot(tx, tz) or 1.0
            nx, nz = -tz / tn, tx / tn
            for sd in (-1, 1):
                if rng.random() > 0.8 * min(dens, 1.3):
                    continue
                x, z = xs + nx * sd * side_off, zs + nz * sd * side_off
                yaw = yaw_of(-nx * sd, -nz * sd) + rng.normal(0, 0.05)
                if not w.free(x, z, 1.25, margin=0.15):
                    continue
                kind = ["house", "house", "house", "shop", "house", "cafe"][int(rng.integers(0, 6))]
                rad = 1.3 if kind == "house" else 1.5
                w.add(kind, x, z, yaw, rng.uniform(0.92, 1.08), pal[int(rng.integers(0, len(pal)))], int(rng.integers(0, 4)), rad,
                      wall=WALLS[int(rng.integers(0, len(WALLS)))])
    for pts in w.streets:
        line_houses(pts, 2.9 * k, 2.7 * k)
    # lamps along the streets
    for pts in w.streets:
        pl = np.array(pts, float)
        for i in range(len(pts) - 1):
            for t in np.linspace(0.1, 0.9, 4):
                x, z = pl[i][0] + (pl[i + 1][0] - pl[i][0]) * t, pl[i][1] + (pl[i + 1][1] - pl[i][1]) * t
                tx, tz = pl[i + 1] - pl[i]
                tn = math.hypot(tx, tz) or 1
                lx, lz = x - tz / tn * 1.35, z + tx / tn * 1.35
                if w.free(lx, lz, 0.3, road=False, margin=0.1) and not w.water_at(lx, lz) and w.keep[w._ij(lx, lz)] < 0.2:
                    w.add("lamp", lx, lz, 0.0, 1.0, None, 0, 0.3)
    centres = []
    for _ in range(int(round(10 * dens)) + 1):
        for _t in range(300):
            x, z = rng.uniform(-w.R, w.R, 2)
            if w.inside_pt(x, z, 1.5) and not w.water_at(x, z) and w.free(x, z, 1.5, margin=0.1) and all((x - cx) ** 2 + (z - cz) ** 2 > 18 for cx, cz in centres):
                centres.append((x, z))
                break
    def tree(x, z):
        v = int(rng.integers(0, 2)) if rng.random() < 0.7 else 2
        w.add("tree" if v < 2 else "pine", x, z, rng.uniform(0, 6.28), rng.uniform(0.8, 1.25), None, v, 0.8)
    def around():
        cx, cz = centres[int(rng.integers(0, len(centres)))]
        return cx + rng.normal(0, 2.2), cz + rng.normal(0, 2.2)
    if centres:
        w.scatter(int(round(44 * dens)), tree, 0.8, lambda x, z: True, margin=0.2, tries=60, sample=around)
    rim = lambda x, z: w.R - 2.4 < math.hypot(x, z) < w.R - 1.0
    w.scatter(int(round(14 * dens)), tree, 0.8, rim, margin=0.1, tries=200)
    w.scatter(int(round(26 * dens)), lambda x, z: w.add("bush", x, z, rng.uniform(0, 6.28), rng.uniform(0.7, 1.2), None, 0, 0.5), 0.5, lambda x, z: True, margin=0.2)
    w.scatter(int(round(8 * dens)), lambda x, z: w.add("rock", x, z, rng.uniform(0, 6.28), rng.uniform(0.5, 1.0), None, int(rng.integers(0, 3)), 0.4), 0.4,
              lambda x, z: 0 < w.dwater(x, z) < 3.0, margin=0.2, road=False)


def dress_town(w: World, pl: dict, pal, rng):
    k = pl["kind"]
    if k == "clocktower":
        D(w, pl, [("bench", -3.0, 2.6, 0.1, 0.9), ("bench", 3.0, 2.6, -0.1, 0.9), ("lamp", -2.4, 3.2), ("lamp", 2.4, 3.2), ("tree", -3.6, -0.8, 0, 0.9, None, 0, 0.8), ("tree", 3.6, -0.8, 0, 0.9, None, 1, 0.8)])
    elif k == "fountain":
        D(w, pl, [("bench", -3.4, 0.0, math.pi / 2, 0.9), ("bench", 3.4, 0.0, -math.pi / 2, 0.9), ("bench", 0, -3.4, math.pi, 0.9), ("lamp", -3.2, 2.6), ("lamp", 3.2, 2.6)])
    elif k == "windmill":
        D(w, pl, [("tree", 3.8, -1.0, 0, 1.0, None, 0, 0.9), ("bush", 3.0, 2.4, 0, 0.8), ("bush", -2.8, 2.8, 0, 1.0), ("fence", -2.0, 3.8, 0, 1, None, 0, 0.3, 0)])
    elif k == "stall":
        D(w, pl, [("crate", 2.3, 0.5, 0.2, 1, None, 0, 0.6), ("barrel", -2.3, 0.4, 0, 1, None, 0, 0.5), ("stall", -4.2, -0.6, 0.25, 0.9, pal[2], 1, 1.6), ("stall", 4.4, -0.8, -0.25, 0.9, pal[1], 2, 1.6), ("lamp", 3.1, 2.2)])
    else:
        D(w, pl, [("tree", 3.0, -1.2, 0, 1.0, None, 0, 0.9), ("bench", -2.6, 2.0, 0.2, 0.9), ("lamp", 2.6, 2.6), ("bush", -3.0, -0.6, 0, 0.9)])


# ---------------------------------------------------------------- desk

def desk(w: World, pal, spec_world):
    k = w.R / 15.0
    P = lambda x, z: (x * k, z * k)
    w.h[:] = 0
    w.finish_terrain()
    paint_wood(w, "#c9915a", 3.1 * k)
    # a desk mat, a coaster and a cable
    mat = box_sdf(w.X, w.Z, 0.0, 1.0 * k, 9.6 * k, 6.4 * k, 0) - 0.4 * k
    w.blend(w.aa(mat, 1.2), "#39434f")
    w.blend(smoothstep(0.07, 0.0, np.abs(mat + 0.25 * k)) * w.aa(mat, 1.2), "#5b6878", 0.8)
    w.keep = np.maximum(w.keep, 0.0)
    paint_path(w, [P(-4, -12), P(-3.2, -9), P(-2.2, -6.8)], 0.22, "#232830")
    spots = [
        Spot("centre", *P(0, 2.2), 0.0, ("laptop",)), Spot("back", *P(0, -6.0), 0.0, ("monitor",)),
        Spot("right", *P(8.4, 1.0), -0.35, ("mug", "notebook")), Spot("left", *P(-8.8, -0.6), 0.35, ("books", "notebook")),
        Spot("corner", *P(-10.2, -9.4), 0.5, ("plant",)), Spot("lamp", *P(10.4, -8.2), -0.5, ("deskLamp",)),
        Spot("front", *P(-5.8, 8.8), 0.2, ("notebook", "mug")), Spot("front-right", *P(8.4, 8.6), -0.3, ("mug", "plant", "books")),
    ]
    w.spots = {s.name: s for s in spots}
    return {"k": k}


def desk_fill(w: World, pal, info, rng):
    k = info["k"]
    extra = [("pencils", 12.0, -3.2, 0.3, 1.0, None), ("books", -12.2, -7.2, 0.4, 0.8, pal[1]), ("mug", -2.4, -11.0, 0.0, 0.75, pal[3]),
             ("notebook", 4.6, 6.2, -0.4, 0.8, pal[0]), ("plant", 12.0, 3.4, 0, 0.6, None)]
    for kind, x, z, yaw, s, col in extra:
        x, z = x * k, z * k
        if w.free(x, z, 1.1 * s, road=False, margin=0.1):
            w.add(kind, x, z, yaw, s, col, 0, 1.1 * s)


def dress_desk(w: World, pl: dict, pal, rng):
    k = pl["kind"]
    if k == "laptop":
        D(w, pl, [("mug", 4.0, -1.2, 0.0, 0.7, pal[2], 0, 0.7), ("pencils", -3.8, -1.0, 0, 0.8)])
    elif k == "monitor":
        D(w, pl, [("plant", -3.8, 0.4, 0, 0.6), ("books", 3.8, 0.2, 0.3, 0.55, pal[1])])


# ---------------------------------------------------------------- factory

def factory(w: World, pal, spec_world):
    k = w.R / 15.0
    P = lambda x, z: (x * k, z * k)
    w.h[:] = 0
    w.finish_terrain()
    paint_concrete(w, "#c8cbd0", 5.0 * k)
    # an aisle down the middle, walkways in yellow, a painted line for the conveyor and the robot cell
    paint_rect(w, 0, 0.8 * k, 14.2 * k, 1.5 * k, 0, "#6b727b", keep=False, edge="#9aa2ab")
    paint_hazard(w, 0, 0.8 * k, 14.2 * k, 1.5 * k)
    paint_rect(w, -7.5 * k, -8.2 * k, 5.2 * k, 3.2 * k, 0, "#9aa2ab", keep=True, edge="#f2c230")
    paint_hazard(w, -7.5 * k, -8.2 * k, 5.2 * k, 3.2 * k)
    paint_rect(w, 8.0 * k, -8.2 * k, 5.2 * k, 3.2 * k, 0, "#9aa2ab", keep=True, edge="#f2c230")
    paint_hazard(w, 8.0 * k, -8.2 * k, 5.2 * k, 3.2 * k)
    paint_rect(w, 0, 9.0 * k, 11.0 * k, 3.4 * k, 0, "#b4b8be", keep=True, edge="#f2c230", stripes=2.4 * k)
    paint_hazard(w, 0, 9.0 * k, 11.0 * k, 3.4 * k)
    spots = [
        Spot("line", *P(-7.5, -8.4), 0.0, ("conveyor",)), Spot("cell", *P(8.0, -8.6), -0.2, ("robot",)),
        Spot("tanks", *P(-10.5, 8.6), 0.4, ("tank", "silo")), Spot("silo", *P(10.5, 8.6), -0.4, ("silo", "tank")),
        Spot("stack", *P(2.5, -12.0), 0.0, ("chimney",)), Spot("dock", *P(0.0, 9.0), 0.0, ("warehouse",)),
        Spot("office", *P(12.2, 0.2), -1.57, ("office",)), Spot("yard", *P(-12.6, -0.5), 1.57, ("warehouse", "office")),
    ]
    w.spots = {s.name: s for s in spots}
    return {"k": k}


def factory_fill(w: World, pal, info, rng):
    k = info["k"]
    for _ in range(int(round(9 * w.density))):
        x, z = rng.uniform(-w.R * 0.9, w.R * 0.9, 2)
        if w.free(x, z, 0.8, road=False, margin=0.3) and abs(z - 0.8 * k) > 2.4:
            if rng.random() < 0.5:
                w.add("crate", x, z, rng.uniform(0, 6.28), 1.3, None, 0, 0.8)
            else:
                w.add("barrel", x, z, 0, 1.4, None, int(rng.integers(0, 2)), 0.6)
    for fx, fz, fy in ((-3.2, 3.8, 0.6), (5.5, -2.8, -2.4)):
        x, z = fx * k, fz * k
        if w.free(x, z, 1.4, road=False, margin=0.2):
            w.add("forklift", x, z, fy, 1.0, pal[0], 0, 1.4)
    for sx in np.linspace(-13 * k, 13 * k, 7):
        for sz in (-2.4 * k, 4.4 * k):
            if w.free(sx, sz, 0.3, road=False, margin=0.1):
                w.add("bollard", sx, sz, 0, 1.1, None, 0, 0.3)
    for lx, lz in ((-13.5 * k, 12.5 * k), (13.5 * k, 12.5 * k), (-13.5 * k, -12.8 * k), (13.5 * k, -12.8 * k)):
        if w.free(lx, lz, 0.4, road=False, margin=0.05):
            w.add("lamp", lx, lz, 0, 1.6, None, 0, 0.4)


def dress_factory(w: World, pl: dict, pal, rng):
    k = pl["kind"]
    if k == "tank":
        D(w, pl, [("crate", 3.4, 1.0, 0.2, 1.2, None, 0, 0.8), ("barrel", -3.4, 1.2, 0, 1.3, None, 1, 0.6), ("bollard", 2.6, 3.4)])
    elif k == "conveyor":
        D(w, pl, [("crate", 4.6, -1.4, 0.3, 1.4, None, 0, 0.9), ("crate", 5.4, -0.2, 0.1, 1.2, None, 0, 0.8), ("barrel", -4.6, -1.0, 0, 1.4, None, 0, 0.6)])
    elif k == "robot":
        D(w, pl, [("crate", 3.0, 2.0, 0.2, 1.3, None, 0, 0.8), ("crate", 3.4, 3.4, 0.5, 1.1, None, 0, 0.7)])


# ---------------------------------------------------------------- studio

def studio(w: World, pal, spec_world):
    k = w.R / 15.0
    P = lambda x, z: (x * k, z * k)
    w.h[:] = 0
    w.finish_terrain()
    paint_wood(w, "#e2bd8a", 2.6 * k, 0.86)
    # a big rug under the set and a seamless paper sweep (a pale rectangle) at the back
    paint_rect(w, 0, -7.8 * k, 10.0 * k, 4.8 * k, 0, "#f3efe6", keep=False, edge="#d9d2c4")
    rug = box_sdf(w.X, w.Z, -6.0 * k, 6.6 * k, 6.0 * k, 3.8 * k, 0) - 0.3 * k
    w.blend(w.aa(rug, 1.2), pal[3] if len(pal) > 3 else "#2d3a4a", 0.95)
    w.blend(smoothstep(0.12 * k, 0.0, np.abs(rug + 0.5 * k)) * w.aa(rug, 1.2), "#f4efe4", 0.9)
    w.keep = np.maximum(w.keep, 0.0)
    spots = [
        Spot("sweep", *P(0.0, -7.4), 0.0, ("camera", "softbox")), Spot("easel", *P(-9.6, -1.8), 0.5, ("easel",)),
        Spot("lights", *P(9.2, -7.2), -0.5, ("softbox",)), Spot("desk", *P(8.6, 3.2), -0.5, ("monitor", "speaker")),
        Spot("lounge", *P(-6.0, 7.4), 0.0, ("sofa",)), Spot("shelf", *P(-11.8, -9.8), 0.4, ("shelf",)),
        Spot("speaker", *P(12.4, -1.8), -0.9, ("speaker", "plant")), Spot("corner", *P(11.4, 10.4), -0.6, ("plant", "speaker")),
    ]
    w.spots = {s.name: s for s in spots}
    return {"k": k}


def studio_fill(w: World, pal, info, rng):
    k = info["k"]
    extra = [("plant", 12.4, 6.2, 0, 0.9, None), ("plant", -12.8, 3.8, 0, 0.8, None), ("pencils", 6.4, 5.6, 0.3, 0.8, None),
             ("camera", -3.4, -3.2, 0.9, 0.7, None), ("speaker", 3.6, -11.6, 0.2, 0.8, None), ("books", 5.0, 9.4, 0.2, 0.7, pal[1])]
    for kind, x, z, yaw, s, col in extra:
        x, z = x * k, z * k
        if w.free(x, z, 1.1 * s, road=False, margin=0.1):
            w.add(kind, x, z, yaw, s, col, 0, 1.1 * s)


def dress_studio(w: World, pl: dict, pal, rng):
    k = pl["kind"]
    if k == "sofa":
        D(w, pl, [("plant", 3.6, 0.0, 0, 0.8), ("pencils", -3.4, 2.0, 0, 0.7)])
    elif k == "easel":
        D(w, pl, [("crate", 2.4, 0.6, 0.2, 1.0, None, 0, 0.6), ("plant", -2.6, -0.4, 0, 0.7)])
