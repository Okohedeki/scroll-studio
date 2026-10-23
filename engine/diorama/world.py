"""The ground of a diorama and what stands on it: a numpy canvas (height, colour, masks), props, and the helpers that
recipes use to lay a world out (see recipes.py)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .fields import hex_rgb, smoothstep, value_noise

TEX_FULL, TEX_DRAFT = 2048, 1024
GRID = 129                      # height samples across the base
WATER_LEVEL = -0.15


def yaw_of(fx: float, fz: float) -> float:
    """Yaw (radians) that turns a prop's front (+z) to face the direction (fx, fz)."""
    return math.atan2(fx, fz)


def forward(yaw: float) -> tuple[float, float]:
    return math.sin(yaw), math.cos(yaw)


def right(yaw: float) -> tuple[float, float]:
    return math.cos(yaw), -math.sin(yaw)


@dataclass
class Spot:
    """A named good place on the world: where, which way its front faces, which hero props belong there."""
    name: str
    x: float
    z: float
    face: float                 # yaw
    kinds: tuple = ()
    water: bool = False


class World:
    def __init__(self, size: float, base: str, seed: int, density: float = 1.0, draft: bool = False):
        self.S, self.R, self.base, self.seed, self.density = size, size / 2, base, seed, density
        self.N = TEX_DRAFT if draft else TEX_FULL
        self.rng = np.random.default_rng(seed)
        N, R = self.N, self.R
        xs = (np.arange(N, dtype=np.float32) + 0.5) / N * size - R
        self.X, self.Z = np.meshgrid(xs, xs)               # row index = z (north, -z, at the top of the image)
        self.px = size / N
        self.h = np.zeros((N, N), np.float32)
        self.col = np.zeros((N, N, 3), np.float32)
        self.road = np.zeros((N, N), np.float32)           # 1 where a vehicle could drive (props stay off it)
        self.keep = np.zeros((N, N), np.float32)           # 1 where props stay off for other reasons (yards, plazas)
        self.dw = np.full((N, N), 99.0, np.float32)        # distance to water, world units
        self.props: list[dict] = []
        self.occ: list[tuple[float, float, float]] = []
        self.spots: dict[str, Spot] = {}
        self.water_level = WATER_LEVEL
        self.has_water = False
        self.inside = self._inside(self.X, self.Z)

    # ------------------------------------------------------------ the base outline
    def _inside(self, X, Z, margin: float = 0.0):
        R = self.R - margin
        if self.base == "round":
            return X * X + Z * Z < R * R
        return (np.abs(X / R) ** 8 + np.abs(Z / R) ** 8) < 1.0

    def outline(self, theta: float) -> float:
        """Radius of the base's edge in direction theta."""
        c, s = math.cos(theta), math.sin(theta)
        if self.base == "round":
            return self.R
        return self.R / (abs(c) ** 8 + abs(s) ** 8) ** (1 / 8)

    def inside_pt(self, x: float, z: float, margin: float = 0.0) -> bool:
        R = self.R - margin
        if self.base == "round":
            return x * x + z * z < R * R
        return abs(x / R) ** 8 + abs(z / R) ** 8 < 1.0

    # ------------------------------------------------------------ sampling
    def _ij(self, x: float, z: float) -> tuple[int, int]:
        N = self.N
        i = int(np.clip((z + self.R) / self.S * N, 0, N - 1))
        j = int(np.clip((x + self.R) / self.S * N, 0, N - 1))
        return i, j

    def height_at(self, x: float, z: float) -> float:
        N = self.N
        fx = np.clip((x + self.R) / self.S * N - 0.5, 0, N - 1.001)
        fz = np.clip((z + self.R) / self.S * N - 0.5, 0, N - 1.001)
        j0, i0 = int(fx), int(fz)
        tx, tz = fx - j0, fz - i0
        h = self.h
        a = h[i0, j0] * (1 - tx) + h[i0, j0 + 1] * tx
        b = h[i0 + 1, j0] * (1 - tx) + h[i0 + 1, j0 + 1] * tx
        return float(a * (1 - tz) + b * tz)

    def water_at(self, x: float, z: float) -> bool:
        return self.height_at(x, z) < self.water_level

    def dwater(self, x: float, z: float) -> float:
        i, j = self._ij(x, z)
        return float(self.dw[i, j])

    def grad_dw(self, x: float, z: float, eps: float = 0.4) -> tuple[float, float]:
        """Direction of increasing distance to water (away from the water), unit length."""
        gx = self.dwater(x + eps, z) - self.dwater(x - eps, z)
        gz = self.dwater(x, z + eps) - self.dwater(x, z - eps)
        n = math.hypot(gx, gz)
        return (gx / n, gz / n) if n > 1e-6 else (0.0, 1.0)

    def on_road(self, x: float, z: float) -> bool:
        i, j = self._ij(x, z)
        return bool(self.road[i, j] > 0.2 or self.keep[i, j] > 0.2)

    # ------------------------------------------------------------ terrain
    def finish_terrain(self):
        """Call once the heights are final: finds the water and the distance to it."""
        import cv2
        water = self.h < self.water_level
        self.water = water
        self.has_water = bool(water.any())
        if self.has_water:
            land = (~water).astype(np.uint8)
            self.dw = cv2.distanceTransform(land, cv2.DIST_L2, 5).astype(np.float32) * self.px
            self.dw[water] = -cv2.distanceTransform(water.astype(np.uint8), cv2.DIST_L2, 5)[water] * self.px
        else:
            self.dw[:] = 99.0

    def noise(self, cells: int, octaves: int = 3, seed_off: int = 0) -> np.ndarray:
        rng = np.random.default_rng(self.seed * 7919 + cells * 31 + octaves + seed_off)
        return value_noise(rng, self.N, cells, octaves)

    # ------------------------------------------------------------ painting
    def blend(self, mask, color, alpha: float = 1.0):
        c = hex_rgb(color) if isinstance(color, str) else np.asarray(color, np.float32)
        m = (np.clip(mask, 0, 1) * alpha)[..., None]
        self.col = self.col * (1 - m) + c * m

    def blend_map(self, mask, colmap, alpha: float = 1.0):
        m = (np.clip(mask, 0, 1) * alpha)[..., None]
        self.col = self.col * (1 - m) + colmap * m

    def aa(self, sdf, soft: float = 1.0):
        """Anti-aliased mask from a signed distance (negative inside)."""
        w = self.px * soft
        return smoothstep(w, -w, sdf)

    def polyline(self, pts, width: float, value: float = 1.0, canvas: Optional[np.ndarray] = None) -> np.ndarray:
        """Mask of a polyline of world points with a width in world units (anti-aliased)."""
        import cv2
        N = self.N
        c = np.zeros((N, N), np.uint8) if canvas is None else canvas
        sc = N / self.S
        q = np.array([[(x + self.R) * sc, (z + self.R) * sc] for x, z in pts], np.float32)
        cv2.polylines(c, [np.round(q * 16).astype(np.int32)], False, 255, max(1, int(round(width * sc))), cv2.LINE_AA, shift=4)
        return c.astype(np.float32) / 255

    def circle_mask(self, x: float, z: float, r: float, feather: float = 0.0):
        d = np.hypot(self.X - x, self.Z - z) - r
        return smoothstep(self.px + feather, -self.px - feather * 0, d) if feather == 0 else smoothstep(feather, -feather, d)

    # ------------------------------------------------------------ props
    def free(self, x: float, z: float, rad: float, land: bool = True, road: bool = True, margin: float = 0.4,
             water: bool = False) -> bool:
        if not self.inside_pt(x, z, rad + margin):
            return False
        if land and not water and self.water_at(x, z):
            return False
        if road and self.on_road(x, z):
            return False
        for ox, oz, orad in self.occ:
            if (x - ox) ** 2 + (z - oz) ** 2 < (rad + orad) ** 2:
                return False
        return True

    def add(self, kind: str, x: float, z: float, yaw: float = 0.0, s: float = 1.0, c=None, v: int = 0, rad: float = 0.0,
            dy: float = 0.0, **extra) -> dict:
        p = {"k": kind, "x": round(x, 3), "z": round(z, 3), "r": round(yaw, 3), "s": round(s, 3), "v": v}
        if c is not None:
            p["c"] = [c] if isinstance(c, str) else list(c)
        if dy:
            p["dy"] = round(dy, 3)
        p.update(extra)
        self.props.append(p)
        if rad > 0:
            self.occ.append((x, z, rad))
        return p

    def scatter(self, n: int, make: Callable[[float, float], Optional[bool]], rad: float, area: Callable[[float, float], bool],
                tries: int = 60, rng=None, sample: Optional[Callable[[], tuple[float, float]]] = None, **free_kw) -> int:
        """Try to place `n` things at random points where area(x, z) holds and the spot is free; make() adds each."""
        rng = rng or self.rng
        placed = 0
        for _ in range(n * tries):
            if placed >= n:
                break
            x, z = sample() if sample else rng.uniform(-self.R, self.R, 2)
            if not area(x, z) or not self.free(x, z, rad, **free_kw):
                continue
            if make(x, z) is not False:
                placed += 1
        return placed

    def finish_props(self):
        """Sets every prop on the ground (its height) once the terrain is final."""
        for p in self.props:
            if "y" not in p:
                y = self.height_at(p["x"], p["z"])
                if y < self.water_level:
                    y = self.water_level
                p["y"] = round(y + p.pop("dy", 0.0), 3)
            else:
                p["y"] = round(p["y"] + p.pop("dy", 0.0), 3)

    # ------------------------------------------------------------ baked contact shadows
    # (radius in world units at scale 1, darkness 0-1) of the soft pool of shade a prop leaves on the ground
    AO = {"house": (1.5, 0.42), "shop": (1.7, 0.42), "cafe": (1.7, 0.42), "warehouse": (2.9, 0.4), "office": (2.0, 0.42), "stall": (1.4, 0.36),
          "lighthouse": (1.7, 0.45), "windmill": (1.8, 0.42), "crane": (2.4, 0.18), "container": (1.5, 0.4), "tree": (0.85, 0.38),
          "pine": (0.8, 0.38), "bush": (0.55, 0.34), "rock": (0.5, 0.34), "crate": (0.45, 0.36), "barrel": (0.4, 0.34), "lamp": (0.3, 0.3),
          "bench": (0.6, 0.3), "bollard": (0.25, 0.3), "sign": (0.5, 0.28), "tank": (2.2, 0.4), "silo": (1.9, 0.42), "chimney": (1.3, 0.4),
          "sofa": (2.4, 0.38), "shelf": (1.9, 0.4), "easel": (1.6, 0.3), "laptop": (2.4, 0.4), "monitor": (2.0, 0.4), "mug": (0.9, 0.4),
          "books": (1.5, 0.4), "plant": (1.2, 0.4), "deskLamp": (1.5, 0.36), "notebook": (1.6, 0.3), "softbox": (1.5, 0.3), "camera": (1.2, 0.34),
          "speaker": (1.1, 0.38), "robot": (2.0, 0.36), "conveyor": (3.2, 0.3), "fountain": (2.2, 0.3), "clocktower": (1.7, 0.42)}

    def bake_ao(self):
        N, S, R = self.N, self.S, self.R
        ao = np.zeros((N, N), np.float32)
        for p in self.props:
            spec = self.AO.get(p["k"])
            if spec is None or self.water_at(p["x"], p["z"]) and p["k"] not in ("lighthouse",):
                continue
            r, a = spec[0] * p["s"], spec[1]
            if p.get("dy", 0) > 0.3 or p["k"] == "container" and p.get("y", 0) > self.height_at(p["x"], p["z"]) + 0.5:
                continue
            cx, cz = (p["x"] + R) / S * N, (p["z"] + R) / S * N
            rp = int(r / self.px * 2.2) + 2
            j0, j1, i0, i1 = max(0, int(cx) - rp), min(N, int(cx) + rp + 1), max(0, int(cz) - rp), min(N, int(cz) + rp + 1)
            if j1 <= j0 or i1 <= i0:
                continue
            d2 = (self.X[i0:i1, j0:j1] - p["x"]) ** 2 + (self.Z[i0:i1, j0:j1] - p["z"]) ** 2
            ao[i0:i1, j0:j1] = np.maximum(ao[i0:i1, j0:j1], a * np.exp(-d2 / (r * r) * 1.3))
        self.col = self.col * (1 - ao[..., None] * 0.9)

    # ------------------------------------------------------------ output
    def height_grid(self, n: int = GRID) -> np.ndarray:
        import cv2
        return cv2.resize(self.h, (n, n), interpolation=cv2.INTER_AREA)

    def texture(self) -> np.ndarray:
        return (np.clip(self.col, 0, 1) * 255 + 0.5).astype(np.uint8)
