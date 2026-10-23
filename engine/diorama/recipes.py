"""World recipes: each kind of diorama (harbour, town, desk, factory, studio) lays its ground out (heights, water,
paving), names its good spots, fills in scenery and dresses the places. Everything is seeded: one spec, one world.

Prop kinds the kit draws (runtime/src/players/diorama/kit.ts): tree pine bush rock lamp bench fence crate barrel flag
sign house shop cafe warehouse office stall container boat buoy bollard pier lighthouse crane windmill ferry clocktower
fountain tank chimney conveyor robot silo bridge, and for desks and studios laptop mug books plant deskLamp monitor
notebook easel softbox camera speaker sofa shelf rug."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .fields import box_sdf, ellipse_sdf, hex_rgb, mix, segment_sdf, smoothstep
from .world import Spot, World, forward, right, yaw_of

# kind -> (height, radius) of the hero prop in world units at scale 1 (for framing the dive)
HERO = {
    "lighthouse": (8.6, 1.3), "crane": (9.0, 2.8), "warehouse": (3.4, 3.2), "stall": (2.4, 1.6), "office": (3.8, 2.3),
    "ferry": (3.0, 2.6), "windmill": (7.4, 2.4), "shop": (3.6, 1.9), "cafe": (3.2, 2.1), "clocktower": (8.4, 1.5),
    "fountain": (2.4, 1.9), "tank": (5.2, 2.2), "chimney": (9.5, 1.2), "conveyor": (1.8, 3.8), "robot": (3.8, 1.8),
    "silo": (7.0, 1.7), "house": (3.0, 1.8), "laptop": (1.5, 2.2), "mug": (1.5, 0.8), "books": (1.5, 1.4),
    "plant": (2.6, 1.2), "deskLamp": (3.8, 1.4), "monitor": (3.0, 1.9), "notebook": (0.5, 1.5), "easel": (4.4, 1.7),
    "softbox": (5.0, 1.4), "camera": (3.4, 1.2), "speaker": (3.4, 1.0), "sofa": (2.0, 2.5), "shelf": (4.2, 1.8),
    "boat": (2.2, 1.6), "container": (1.2, 1.4),
}
WATER_KINDS = {"ferry", "boat"}

PALETTES = {
    "harbour": ["#d9503a", "#2f8a9d", "#e8a23a", "#c4433a", "#3d6fa5"],
    "town": ["#c4533c", "#d98b3a", "#4f7f9a", "#8a5a8f", "#cf6f4e"],
    "desk": ["#e0564a", "#3d8fb0", "#e8b23a", "#6aa56a", "#8a6ab0"],
    "factory": ["#e8a23a", "#d9503a", "#3d8fb0", "#6aa56a", "#cfd3d8"],
    "studio": ["#e0564a", "#3d8fb0", "#e8b23a", "#2d3a4a", "#cfd3d8"],
}
WALLS = ["#f4ead8", "#f0dcc0", "#e9efe8", "#f7e3d0", "#efe2c6"]


def local(x, z, yaw, dx, dz):
    """A point `dx` to the right and `dz` in front of (x, z), which faces `yaw`."""
    rx, rz = right(yaw)
    fx, fz = forward(yaw)
    return x + rx * dx + fx * dz, z + rz * dx + fz * dz


def pal_of(w: World, spec_palette: list[str], kind: str) -> list[str]:
    return list(spec_palette) if len(spec_palette) >= 2 else PALETTES[kind]


# ---------------------------------------------------------------- ground painting pieces

def paint_grass(w: World, a="#8fc45f", b="#7bb351", speckle=True):
    n1 = w.noise(5, 3)
    n2 = w.noise(60, 2, 5)
    t = np.clip(n1 * 0.85 + n2 * 0.15, 0, 1)
    ca, cb = hex_rgb(a), hex_rgb(b)
    w.col = mix(ca, cb, t[..., None]) * (0.96 + 0.08 * n2[..., None])
    if speckle:
        rng = np.random.default_rng(w.seed + 11)
        N = w.N
        for color, count in (("#fff7d6", 520), ("#ffd84d", 260), ("#f59bb5", 160), ("#ffffff", 200)):
            ys = rng.integers(0, N, count)
            xs = rng.integers(0, N, count)
            m = np.zeros((N, N), np.float32)
            m[ys, xs] = 1.0
            import cv2
            m = cv2.GaussianBlur(m, (0, 0), max(1.2, N / 700))
            m = np.clip(m * 9, 0, 1)
            w.blend(m, color, 0.85)


def paint_water_bed(w: World, shallow="#79d5e3", deep="#2b86b8"):
    if not w.has_water:
        return
    d = np.clip((w.water_level - w.h) / 1.0, 0, 1)
    bed = mix(hex_rgb(shallow), hex_rgb(deep), smoothstep(0.0, 1.0, d)[..., None])
    n = w.noise(24, 3, 3)
    bed = bed * (0.94 + 0.12 * n[..., None])
    w.blend_map(w.water.astype(np.float32), bed)


def paint_shore_ring(w: World, kerb="#f1eee6", road="#5e6268", kerb_w=0.42, road_w=1.45, gap_mask=None, dashes=True,
                     around=(0.0, 0.0)):
    """The harbour front: a white kerb along the water, a road beside it with a dashed middle line."""
    dw = w.dw
    land = ~w.water
    soft = w.px * 1.2
    k = smoothstep(-soft, soft, dw) * smoothstep(kerb_w + soft, kerb_w - soft, dw)
    r0, r1 = kerb_w, kerb_w + road_w
    r = smoothstep(r0 - soft, r0 + soft, dw) * smoothstep(r1 + soft, r1 - soft, dw)
    if gap_mask is not None:
        r = r * (1 - gap_mask)
    k = k * land
    r = r * land
    # road surface with a little variation
    n = w.noise(90, 2, 9)
    asphalt = hex_rgb(road) * (0.94 + 0.1 * n[..., None])
    w.blend_map(r, asphalt)
    # edge lines
    mid = (r0 + r1) / 2
    line = smoothstep(0.05 + soft, 0.05 - soft, np.abs(dw - mid)) * r
    if dashes:
        th = np.arctan2(w.Z - around[1], w.X - around[0])
        period = max(24, int(2 * math.pi * 7.5 / 1.1))
        dash = (np.mod(th / (2 * math.pi) * period, 1.0) < 0.55).astype(np.float32)
        w.blend(line * dash, "#f4ead0", 0.95)
    w.blend(k, kerb)
    # kerb outer shadow line
    edge = smoothstep(0.05 + soft, 0.05 - soft, np.abs(dw - kerb_w)) * land
    w.blend(edge * 0.35, "#8c8a86")
    w.road = np.maximum(w.road, r)
    return r


def paint_cobbles(w: World, x: float, z: float, rad: float, a="#c9bfae", b="#a89d8b", soft=0.35):
    d = np.hypot(w.X - x, w.Z - z) - rad
    m = smoothstep(w.px, -w.px, d)
    if m.max() <= 0:
        return
    tile = 0.30
    u = w.X / tile
    v = w.Z / tile
    row = np.floor(v)
    u = u + 0.5 * np.mod(row, 2)
    cu = np.floor(u)
    fu, fv = u - cu, v - row
    hsh = np.mod(np.sin(cu * 12.9898 + row * 78.233) * 43758.5453, 1.0)
    base = mix(hex_rgb(a), hex_rgb(b), hsh[..., None] * 0.9)
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    base = base * (0.72 + 0.28 * smoothstep(0.0, 0.14, edge))[..., None]
    w.blend_map(m, base)
    # a soft rim of paler stone
    rim = smoothstep(0.1, 0.0, np.abs(d + 0.12)) * m
    w.blend(rim * 0.5, "#efe8d8")
    w.keep = np.maximum(w.keep, smoothstep(0.3, -0.1, d))


def paint_rect(w: World, cx, cz, hx, hz, rot_deg, color, keep=True, stripes=None, edge="#7a7f86"):
    sdf = box_sdf(w.X, w.Z, cx, cz, hx, hz, rot_deg)
    m = w.aa(sdf, 1.2)
    n = w.noise(70, 2, 13)
    col = hex_rgb(color) * (0.93 + 0.12 * n[..., None])
    w.blend_map(m, col)
    w.blend(smoothstep(0.1, 0.0, np.abs(sdf + 0.08)) * m, edge, 0.6)
    if stripes:
        t = math.radians(rot_deg)
        u = (w.X - cx) * math.cos(t) + (w.Z - cz) * math.sin(t)
        lines = smoothstep(0.045, 0.02, np.abs(np.mod(u + stripes / 2, stripes) - stripes / 2)) * smoothstep(0.0, -0.4, sdf + 0.3)
        w.blend(lines * m, "#f4ead0", 0.75)
    if keep:
        w.keep = np.maximum(w.keep, smoothstep(0.35, -0.15, sdf))
    return m


def paint_path(w: World, pts, width=0.9, color="#d8c9a3", keep=False):
    import cv2
    m = w.polyline(pts, width)
    m = cv2.GaussianBlur(m, (0, 0), 0.8)
    n = w.noise(80, 2, 17)
    w.blend_map(m * (1 - w.road * 0.0), hex_rgb(color) * (0.95 + 0.08 * n[..., None]))
    if keep:
        w.road = np.maximum(w.road, m)
    return m


def paint_field(w: World, cx, cz, hx, hz, rot_deg, color="#d9b84a", rows=0.28):
    sdf = box_sdf(w.X, w.Z, cx, cz, hx, hz, rot_deg)
    m = w.aa(sdf, 1.4)
    t = math.radians(rot_deg)
    v = -(w.X - cx) * math.sin(t) + (w.Z - cz) * math.cos(t)
    furrow = 0.5 + 0.5 * np.sin(v / rows * 2 * math.pi)
    base = hex_rgb(color) * (0.82 + 0.28 * furrow[..., None])
    w.blend_map(m, base)
    w.keep = np.maximum(w.keep, smoothstep(0.2, -0.2, sdf))


# ---------------------------------------------------------------- places: resolving where, dressing

COMPASS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0), "back": (0, -1), "front": (0, 1),
           "left": (-1, 0), "right": (1, 0), "northeast": (1, -1), "northwest": (-1, -1), "southeast": (1, 1),
           "southwest": (-1, 1)}


def resolve_where(w: World, where, spots: dict[str, Spot]) -> Optional[tuple[float, float, Optional[float]]]:
    """(x, z, face or None) from a place's `where`; None when it names nothing."""
    if where is None:
        return None
    if isinstance(where, (tuple, list)):
        x, z = float(where[0]), float(where[1])
        return x, z, None
    text = str(where).lower().replace("-", " ").replace("_", " ").strip()
    for name, sp in spots.items():
        if text == name:
            return sp.x, sp.z, sp.face
    if text in ("centre", "center", "middle"):
        return 0.0, 0.0, None
    dx = dz = 0.0
    hit = False
    tokens = text.split()
    for i, t in enumerate(tokens):
        for key in (t, t + (tokens[i + 1] if i + 1 < len(tokens) else "")):
            if key in COMPASS:
                dx += COMPASS[key][0]
                dz += COMPASS[key][1]
                hit = True
                break
    if hit:
        n = math.hypot(dx, dz) or 1.0
        rad = w.R * (0.82 if "edge" in tokens else 0.58)
        return dx / n * rad, dz / n * rad, None
    if "edge" in tokens:
        return w.R * 0.8, 0.0, None
    for name, sp in spots.items():
        if name in text:
            return sp.x, sp.z, sp.face
    return None


def snap_free(w: World, x: float, z: float, rad: float, water_ok: bool = False) -> tuple[float, float]:
    """Nudge a wanted position to open ground: out of the water, off the road, inside the base."""
    if w.free(x, z, rad, water=water_ok, margin=0.2):
        return x, z
    for r in np.linspace(0.4, w.R * 0.9, 18):
        for a in np.linspace(0, 2 * math.pi, 24, endpoint=False):
            px, pz = x + r * math.cos(a), z + r * math.sin(a)
            if w.free(px, pz, rad, water=water_ok, margin=0.2) and (water_ok or w.dwater(px, pz) > 2.2 or not w.has_water):
                return px, pz
    return x, z


def face_default(w: World, x: float, z: float, water_pref: bool = True) -> float:
    """Which way a thing at (x, z) faces when nothing says: towards the water if it is close, else the viewer."""
    if w.has_water and w.dwater(x, z) < 9.0 and water_pref:
        gx, gz = w.grad_dw(x, z)
        return yaw_of(-gx, -gz)
    return yaw_of(-x * 0.25, 1.0 - z * 0.05)


def D(w: World, pl: dict, items):
    """Dress a place: items are (kind, dx, dz, turn, scale, colour, variant, radius, dy) in the hero's own frame."""
    for it in items:
        kind, dx, dz = it[0], it[1], it[2]
        turn = it[3] if len(it) > 3 else 0.0
        s = it[4] if len(it) > 4 else 1.0
        c = it[5] if len(it) > 5 else None
        v = it[6] if len(it) > 6 else 0
        rad = it[7] if len(it) > 7 else 0.5 * s
        dy = it[8] if len(it) > 8 else 0.0
        s *= pl["scale"] ** 0.5
        x, z = local(pl["x"], pl["z"], pl["yaw"], dx * pl["scale"], dz * pl["scale"])
        if kind in ("boat", "buoy"):
            if not w.water_at(x, z):
                continue
        elif not w.inside_pt(x, z, 0.3) or w.water_at(x, z):
            continue
        w.add(kind, x, z, pl["yaw"] + turn, s, c, v, rad, dy)


def dress_harbour(w: World, pl: dict, pal, rng):
    k = pl["kind"]
    roof = lambda: pal[int(rng.integers(0, len(pal)))]
    if k == "lighthouse":
        D(w, pl, [("house", 3.6, -0.6, 0.5, 0.85, roof(), 0, 1.5), ("rock", -2.3, 0.9, 0, 1.2), ("rock", -3.0, -0.2, 1, 1.6),
                  ("bush", 2.3, 2.0, 0, 0.9), ("bush", -1.8, 2.3, 0, 0.7), ("bench", 3.0, 2.8, 0.3, 0.9), ("lamp", 1.8, 3.4),
                  ("tree", -3.6, -2.4, 0, 1.0, None, 1, 0.8)])
    elif k == "crane":
        D(w, pl, [("container", -4.6, -0.6, math.pi / 2, 1, pal[0], 0, 1.4), ("container", -4.6, -0.6, math.pi / 2, 1, pal[1], 0, 0.1, 1.05),
                  ("container", -4.6, 2.2, math.pi / 2, 1, pal[2], 0, 1.4), ("crate", 3.8, 0.8, 0.2, 1, None, 0, 0.7),
                  ("crate", 4.4, 1.8, 0.5, 0.9, None, 0, 0.6), ("barrel", 3.5, -0.4, 0, 1, None, 0, 0.5), ("bollard", 2.4, 3.6),
                  ("bollard", -2.4, 3.6), ("lamp", 3.2, 3.8)])
    elif k == "stall":
        D(w, pl, [("crate", 2.3, 0.5, 0.2, 1, None, 0, 0.6), ("crate", 2.5, -0.5, 0.5, 0.9, None, 0, 0.5), ("barrel", -2.3, 0.4, 0, 1, None, 0, 0.5),
                  ("stall", -4.2, -0.6, 0.25, 0.9, pal[2], 1, 1.6), ("stall", 4.4, -0.8, -0.25, 0.9, pal[1], 2, 1.6),
                  ("lamp", 3.1, 2.2), ("bench", 0.0, -3.0, math.pi, 1.0)])
    elif k == "windmill":
        D(w, pl, [("tree", 3.8, -1.0, 0, 1.0, None, 0, 0.9), ("tree", -4.2, -1.6, 0, 0.8, None, 1, 0.8), ("bush", 3.0, 2.4, 0, 0.8),
                  ("bush", -2.6, 2.8, 0, 1.0), ("fence", -2.0, 3.8, 0, 1, None, 0, 0.3, 0)])
    elif k in ("office", "warehouse"):
        D(w, pl, [("flag", 3.0, 2.2), ("bench", -3.2, 2.0, 0, 1.0), ("tree", 4.4, -1.0, 0, 1.0, None, 0, 0.9), ("lamp", -2.6, 3.0),
                  ("crate", 3.6, 3.0, 0.3, 0.9, None, 0, 0.5)])
    elif k in ("shop", "cafe", "house"):
        D(w, pl, [("tree", 3.0, -1.2, 0, 1.0, None, 0, 0.9), ("bench", -2.6, 2.0, 0.2, 0.9), ("lamp", 2.6, 2.6), ("bush", -3.0, -0.6, 0, 0.9)])
    elif k == "ferry":
        D(w, pl, [("buoy", 3.8, 2.2, 0, 1.0, "#e8423a"), ("buoy", -3.6, 2.6, 0, 1.0, "#f2c230"), ("boat", -5.0, -1.4, 0.7, 0.7, pal[2], 1, 1.0)])
    else:
        D(w, pl, [("tree", 3.0, -1.0, 0, 1.0, None, 0, 0.9), ("bush", -2.6, 1.2, 0, 0.9), ("lamp", 2.4, 2.4)])


# ---------------------------------------------------------------- the harbour

def harbour(w: World, pal, spec_world):
    k = w.R / 15.0
    P = lambda x, z: (x * k, z * k)
    X, Z = w.X, w.Z

    # --- heights: a bay with a channel to the front edge, a headland hill for the lighthouse, a low rise behind
    bay_c = P(1.6, 1.0)
    bay = ellipse_sdf(X, Z, bay_c[0], bay_c[1], 5.7 * k, 4.0 * k, -14) + (w.noise(7, 3, 21) - 0.5) * 1.2 * k
    chan_pts = [P(3.2, 2.6), P(6.0, 5.2), P(6.9, 9.0), P(10.8, 12.4), P(14.5, 14.8)]
    chan = np.minimum.reduce([segment_sdf(X, Z, a, b, (1.3 - 0.0 * i) * k) for i, (a, b) in enumerate(zip(chan_pts, chan_pts[1:]))]) + (w.noise(9, 2, 23) - 0.5) * 0.5 * k
    sw = np.minimum(bay, chan)
    hill = 1.9 * np.exp(-(((X - (-9.6 * k)) ** 2 + (Z - (-6.2 * k)) ** 2) / (2 * (3.1 * k) ** 2)))
    rise = 0.9 * np.exp(-(((X - 2.0 * k) ** 2 + (Z - (-11.2 * k)) ** 2) / (2 * (3.4 * k) ** 2)))
    land = hill + rise + (w.noise(4, 2, 31) - 0.5) * 0.12
    basin = -1.25 * smoothstep(0.38, -0.34, sw)
    w.h = (land + basin).astype(np.float32)
    w.h[~w.inside] = np.minimum(w.h[~w.inside], 0.0)
    w.finish_terrain()

    # --- paint
    paint_grass(w)
    # beach towards the hill, where the road does not run
    th_hill = math.atan2(-6.2 * k - bay_c[1], -9.6 * k - bay_c[0])
    ang = np.arctan2(Z - bay_c[1], X - bay_c[0])
    da = np.abs(np.arctan2(np.sin(ang - th_hill), np.cos(ang - th_hill)))
    gap = smoothstep(0.55, 0.30, da) * (w.dw < 6)
    sandy = (smoothstep(1.7, 0.1, w.dw) * (~w.water)).astype(np.float32)
    w.blend(sandy * (1 - 0.0), "#ecd8a2")
    paint_water_bed(w)
    paint_shore_ring(w, gap_mask=gap, around=bay_c)
    # foam line at the waterline
    foam = smoothstep(0.16, 0.0, np.abs(w.dw)) * 0.6
    w.blend(foam, "#ffffff")

    # --- spots
    def face_to(x, z, tx, tz):
        return yaw_of(tx - x, tz - z)
    bc = bay_c
    spots = [
        Spot("hill", *P(-9.6, -6.2), yaw_of(-9.6, -6.2), ("lighthouse",)),
        Spot("yard", *P(7.6, -5.5), yaw_of(0.0, 1.0), ("crane", "warehouse")),
        Spot("plaza", *P(-9.4, 5.6), yaw_of(-9.4, 5.6), ("stall", "cafe")),
        Spot("quay", *P(11.0, 0.4), yaw_of(1.0, 0.0), ("office", "warehouse")),
        Spot("meadow", *P(-2.8, -11.2), yaw_of(0.0, 1.0), ("windmill",)),
        Spot("village", *P(-11.0, -1.0), face_to(*P(-11.0, -1.0), *bc), ("shop", "cafe", "house")),
        Spot("bay", *P(0.6, 1.4), yaw_of(0.4, 1.0), ("ferry",), water=True),
        Spot("pier", *P(-1.3, 9.2), yaw_of(0.0, -1.0), ("shop", "cafe")),
    ]
    w.spots = {s.name: s for s in spots}
    w.bay = bc
    return {"bay_c": bc, "k": k}


def harbour_fill(w: World, pal, info, rng):
    k = info["k"]
    bc = info["bay_c"]
    dens = w.density
    # hero places have already reserved their ground. First: lamps along the harbour road
    th = np.linspace(-math.pi, math.pi, 90, endpoint=False)
    lamps = 0
    for a in th:
        # march outward from the bay centre to where the distance to water reaches the lamp line
        for r in np.linspace(1.0, w.R * 1.2, 160):
            x, z = bc[0] + r * math.cos(a), bc[1] + r * math.sin(a)
            if not w.inside_pt(x, z, 0.5):
                break
            if not w.water_at(x, z) and w.dwater(x, z) >= 2.05:
                if lamps % 5 == 0 and w.free(x, z, 0.3, road=False, margin=0.2) and not (w.keep[w._ij(x, z)] > 0.2):
                    w.add("lamp", x, z, a + math.pi, 1.0, None, 0, 0.3)
                lamps += 1
                break
    # the pier into the bay (from the road's outer edge, along the front)
    # boats and buoys on the water
    boats = int(round(5 * dens))
    def boat(x, z):
        w.add("boat", x, z, rng.uniform(0, 6.28), rng.uniform(0.85, 1.1), pal[int(rng.integers(0, len(pal)))], int(rng.integers(0, 3)), 1.1)
    w.scatter(boats, boat, 1.1, lambda x, z: w.dwater(x, z) < -1.2, water=True, road=False, margin=0.6)
    # container yard: stacks behind the crane
    yx, yz = w.spots["yard"].x, w.spots["yard"].z
    paint_rect(w, yx + 0.6 * k, yz - 2.3 * k, 4.8 * k, 2.9 * k, 0, "#7b8088", stripes=2.35 * k)
    cont_cols = ["#d9503a", "#2f6fa8", "#3aa06a", "#e8b23a", "#c4433a", "#7a5aa8"]
    for gx in range(-2, 2):
        for gz in range(0, 2):
            x, z = yx + (gx * 2.35 + 0.8) * k + 0.4 * k, yz - (1.6 + gz * 2.3) * k
            if not w.free(x, z, 1.5, road=False, margin=0.1):
                continue
            h = int(rng.integers(1, 4)) if (gx + gz) % 2 == 0 else int(rng.integers(1, 3))
            for layer in range(h):
                w.add("container", x, z, math.pi / 2 * 0 + (0.0 if gz == 0 else 0.0), 1.0, cont_cols[int(rng.integers(0, len(cont_cols)))],
                      int(rng.integers(0, 2)), 1.5 if layer == 0 else 0.0, 1.05 * layer)
    # the windmill's wheat field
    mx, mz = w.spots["meadow"].x, w.spots["meadow"].z
    paint_field(w, mx - 4.6 * k, mz + 1.2 * k, 2.8 * k, 1.5 * k, -6, "#d9b84a")
    # plaza cobbles
    px, pz = w.spots["plaza"].x, w.spots["plaza"].z
    paint_cobbles(w, px, pz, 3.1 * k)
    # paths from the places to the road
    for name in ("hill", "village", "meadow", "quay"):
        sp = w.spots[name]
        gx, gz = w.grad_dw(sp.x, sp.z)
        pts = [(sp.x, sp.z)]
        x, z = sp.x, sp.z
        for _ in range(60):
            if w.dwater(x, z) <= 2.0:
                break
            x, z = x - gx * 0.25, z - gz * 0.25
            gx, gz = w.grad_dw(x, z)
            pts.append((x, z))
        if len(pts) > 2:
            paint_path(w, pts, 0.75)
    # houses facing the water, on the near land beyond the road
    def house(x, z):
        gx, gz = w.grad_dw(x, z)
        yaw = yaw_of(-gx, -gz) + rng.normal(0, 0.12)
        w.add("house", x, z, yaw, rng.uniform(0.9, 1.1), pal[int(rng.integers(0, len(pal)))], int(rng.integers(0, 4)), 1.35, wall=WALLS[int(rng.integers(0, len(WALLS)))])
    area_house = lambda x, z: 2.7 < w.dwater(x, z) < 8.0 and w.height_at(x, z) < 0.6
    w.scatter(int(round(17 * dens)), house, 1.35, area_house, margin=0.15, tries=160)
    # trees in groups, bushes
    centres = []
    for _ in range(int(round(12 * dens)) + 1):
        for _t in range(400):
            x, z = rng.uniform(-w.R, w.R, 2)
            if w.inside_pt(x, z, 1.5) and not w.water_at(x, z) and w.dwater(x, z) > 3.2 and w.free(x, z, 1.5, margin=0.1)                     and all((x - cx) ** 2 + (z - cz) ** 2 > 20 for cx, cz in centres):
                centres.append((x, z))
                break
    def tree(x, z):
        v = int(rng.integers(0, 2)) if rng.random() < 0.7 else 2
        w.add("tree" if v < 2 else "pine", x, z, rng.uniform(0, 6.28), rng.uniform(0.8, 1.25), None, v, 0.8)
    def near_centre(x, z):
        return w.dwater(x, z) > 3.0 and any((x - cx) ** 2 + (z - cz) ** 2 < 14.0 for cx, cz in centres)
    def around():
        cx, cz = centres[int(rng.integers(0, len(centres)))]
        return cx + rng.normal(0, 2.4), cz + rng.normal(0, 2.4)
    if centres:
        w.scatter(int(round(46 * dens)), tree, 0.8, near_centre, margin=0.2, tries=60, sample=around)
    # a loose fringe of trees along the rim of the base frames the world, like the hedge round a model railway
    rim = lambda x, z: w.R - 2.6 < math.hypot(x, z) < w.R - 1.1 and w.dwater(x, z) > 2.6
    w.scatter(int(round(14 * dens)), tree, 0.8, rim, margin=0.1, tries=300)
    def bush(x, z):
        w.add("bush", x, z, rng.uniform(0, 6.28), rng.uniform(0.7, 1.2), None, 0, 0.5)
    w.scatter(int(round(26 * dens)), bush, 0.5, lambda x, z: w.dwater(x, z) > 2.4, margin=0.2)
    def rock(x, z):
        w.add("rock", x, z, rng.uniform(0, 6.28), rng.uniform(0.5, 1.1), None, int(rng.integers(0, 3)), 0.4)
    w.scatter(int(round(10 * dens)), rock, 0.4, lambda x, z: w.dwater(x, z) < 3.0 and w.dwater(x, z) > 0.0, margin=0.2, road=False)


# ---------------------------------------------------------------- the registry: kind -> (setup, fill, dress)

def setup(kind: str, w: World, pal, spec_world):
    if kind == "harbour":
        return harbour(w, pal, spec_world)
    from . import recipes2
    return getattr(recipes2, kind)(w, pal, spec_world)


def fill(kind: str, w: World, pal, info, rng):
    if kind == "harbour":
        return harbour_fill(w, pal, info, rng)
    from . import recipes2
    return getattr(recipes2, f"{kind}_fill")(w, pal, info, rng)


def dress(kind: str, w: World, pl: dict, pal, rng):
    if kind == "harbour":
        return dress_harbour(w, pl, pal, rng)
    from . import recipes2
    return getattr(recipes2, f"dress_{kind}")(w, pl, pal, rng)
