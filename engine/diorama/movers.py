"""Things that move on a diorama: movers on routes (driven by the scroll or by time) and crowds wandering a grid.

    route_path(points, radius)      a route as dense points with rounded corners, and its length
    project(path, x, z)             how far along a path the point nearest (x, z) is
    scroll_mover(...)               a scroll mover's path and its stops (arc length, the step it waits through, its load)
    simulate_traffic(...)           a few minutes of grid traffic that never collides, as key frames per mover

Everything is deterministic (seeded) and runs on the CPU in well under a second for dozens of movers."""
from __future__ import annotations

import math
from typing import Callable, Optional

import numpy as np

VERSION = 1


def route_path(points: list[tuple[float, float]], radius: float = 0.6, step: float = 0.15) -> tuple[list[list[float]], float]:
    """Dense points along a polyline whose corners are rounded with arcs of `radius` (shrunk where the legs are short),
    spaced about `step` apart; and the path's length. A single point is a path of length 0."""
    pts = [tuple(map(float, p)) for p in points]
    pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 1e-6]
    if len(pts) < 2:
        return [[round(pts[0][0], 4), round(pts[0][1], 4)]] if pts else [], 0.0
    # each corner becomes a short quadratic curve between two points set back from it along its legs
    out: list[tuple[float, float]] = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = np.array(pts[i - 1]), np.array(pts[i]), np.array(pts[i + 1])
        l1, l2 = np.linalg.norm(b - a), np.linalg.norm(c - b)
        r = min(radius, l1 * 0.45, l2 * 0.45)
        p0 = b + (a - b) / l1 * r
        p2 = b + (c - b) / l2 * r
        out.append(tuple(p0))
        for t in np.linspace(0, 1, 9)[1:-1]:
            q = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p2
            out.append(tuple(q))
        out.append(tuple(p2))
    out.append(pts[-1])
    arr = np.array(out)
    seg = np.hypot(*(arr[1:] - arr[:-1]).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(cum[-1])
    n = max(2, int(math.ceil(total / step)) + 1)
    s = np.linspace(0, total, n)
    xs, zs = np.interp(s, cum, arr[:, 0]), np.interp(s, cum, arr[:, 1])
    return [[round(float(x), 4), round(float(z), 4)] for x, z in zip(xs, zs)], round(total, 4)


def path_at(path: list[list[float]], total: float, s: float) -> tuple[float, float]:
    """The point `s` along a dense path (the twin of `pathAt` in the page's diorama/movers.ts)."""
    n = len(path)
    if n == 0:
        return 0.0, 0.0
    if n == 1 or total <= 0:
        return path[0][0], path[0][1]
    f = min(1.0, max(0.0, s / total)) * (n - 1)
    i = min(n - 2, int(f))
    u = f - i
    a, b = path[i], path[i + 1]
    return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u


def project(path: list[list[float]], x: float, z: float) -> tuple[float, float]:
    """(arc length along `path` of the point nearest (x, z), its distance from the path)."""
    if len(path) < 2:
        return 0.0, math.dist(path[0], (x, z)) if path else 0.0
    arr = np.array(path)
    a, b = arr[:-1], arr[1:]
    d = b - a
    ll = np.maximum((d * d).sum(1), 1e-12)
    t = np.clip(((np.array([x, z]) - a) * d).sum(1) / ll, 0, 1)
    q = a + d * t[:, None]
    dist = np.hypot(q[:, 0] - x, q[:, 1] - z)
    k = int(np.argmin(dist))
    seg = np.sqrt(ll)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    return float(cum[k] + seg[k] * t[k]), float(dist[k])


def scroll_mover(points: list[tuple[float, float]], stops: list[dict], radius: float = 0.6) -> dict:
    """A scroll mover's path and stops. `stops` are {x, z, step, carry} in route order. With `points` the path is that
    route and each stop sits at the point of it nearest the stop (never behind the stop before); without, the path runs
    stop to stop. Returns {path, len, stops: [{s, step, carry, off}]} (`off`: how far the stop was from the route)."""
    pts = list(points) if points else [(st["x"], st["z"]) for st in stops]
    path, total = route_path(pts, radius)
    out, last = [], 0.0
    for st in stops:
        s, off = project(path, st["x"], st["z"])
        s = max(s, last)
        out.append({"s": round(s, 4), "step": st["step"], "carry": st.get("carry"), "off": round(off, 3)})
        last = s
    return {"path": path, "len": total, "stops": out}


# ---------------------------------------------------------------- grid traffic

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def grid_nodes(area, cell: float, blocked: Callable[[float, float], bool]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The grid inside `area` (x0, z0, x1, z1): node xs, zs, and which nodes are free."""
    x0, z0, x1, z1 = area
    nx, nz = int(math.floor((x1 - x0) / cell + 1e-6)), int(math.floor((z1 - z0) / cell + 1e-6))
    ox, oz = x0 + (x1 - x0 - nx * cell) / 2 + cell / 2, z0 + (z1 - z0 - nz * cell) / 2 + cell / 2
    xs = ox + np.arange(nx) * cell
    zs = oz + np.arange(nz) * cell
    free = np.array([[not blocked(float(x), float(z)) for x in xs] for z in zs], bool)
    return xs, zs, free


def simulate_traffic(area, cell: float, count: int, speed: float, pause: float, blocked: Callable[[float, float], bool],
                     seed: int = 7, duration: float = 120.0, dt: float = 0.05) -> dict:
    """`count` movers wandering the grid for `duration` seconds without ever sharing a cell: a mover reserves the next
    cell before it sets off and keeps its own until it arrives, so they can neither meet nor swap places. Each goes
    straight more often than it turns, rests `pause` at each cell, and waits when its way is taken. Returns
    {T, keys: [[t, x, z, t, x, z, ...] per mover]}: the times a mover starts and ends each move, and where it is then
    (between two keys it travels in a straight line, easing in and out)."""
    rng = np.random.default_rng(seed)
    xs, zs, free = grid_nodes(area, cell, blocked)
    nz, nx = free.shape
    cells = [(i, j) for i in range(nz) for j in range(nx) if free[i, j]]
    if not cells:
        return {"T": duration, "keys": [], "cell": cell}
    count = min(count, max(1, len(cells) // 3))
    start = [cells[k] for k in rng.choice(len(cells), size=count, replace=False)]
    occ: dict[tuple[int, int], int] = {c: a for a, c in enumerate(start)}
    pos = list(start)
    heading = [DIRS[int(rng.integers(0, 4))] for _ in range(count)]
    move_t = cell / speed
    state = [("rest", float(rng.uniform(0, pause + move_t))) for _ in range(count)]      # staggered starts
    target: list[Optional[tuple[int, int]]] = [None] * count
    keys = [[0.0, float(xs[c[1]]), float(zs[c[0]])] for c in start]
    t = 0.0
    while t < duration:
        for a in rng.permutation(count):
            kind, until = state[a]
            if t < until:
                continue
            if kind == "move":                      # arrived: release the cell it left
                i, j = pos[a]
                occ.pop((i, j), None)
                pos[a] = target[a]
                target[a] = None
                keys[a] += [round(t, 3), float(xs[pos[a][1]]), float(zs[pos[a][0]])]
                state[a] = ("rest", t + pause * float(rng.uniform(0.6, 1.6)))
                continue
            # resting: pick a way on
            i, j = pos[a]
            order = list(DIRS)
            rng.shuffle(order)
            if rng.random() < 0.6:
                order.remove(heading[a])
                order.insert(0, heading[a])
            back = (-heading[a][0], -heading[a][1])
            order.remove(back)
            order.append(back)                     # turning round is the last resort
            went = False
            for d in order:
                ni, nj = i + d[1], j + d[0]
                if 0 <= ni < nz and 0 <= nj < nx and free[ni, nj] and (ni, nj) not in occ:
                    occ[(ni, nj)] = a
                    target[a] = (ni, nj)
                    heading[a] = d
                    keys[a] += [round(t, 3), float(xs[j]), float(zs[i])]
                    state[a] = ("move", t + move_t)
                    went = True
                    break
            if not went:
                state[a] = ("rest", t + 0.3)
        t += dt
    return {"T": round(duration, 3), "keys": [[round(v, 3) for v in k] for k in keys], "cell": cell}


def position(keys: list[float], t: float) -> tuple[float, float]:
    """Where a traffic mover is at time t (seconds, within the loop): the CPU twin of the page's own playback."""
    n = len(keys) // 3
    if n == 0:
        return 0.0, 0.0
    ts = keys[0::3]
    if t <= ts[0]:
        return keys[1], keys[2]
    k = int(np.searchsorted(ts, t, side="right")) - 1
    if k >= n - 1:
        return keys[-2], keys[-1]
    t0, t1 = ts[k], ts[k + 1]
    u = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
    u = u * u * (3 - 2 * u)
    return keys[3 * k + 1] + (keys[3 * k + 4] - keys[3 * k + 1]) * u, keys[3 * k + 2] + (keys[3 * k + 5] - keys[3 * k + 2]) * u
