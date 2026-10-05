"""map: a live MapLibre map driven by scroll. Routes are densified here (great circles for flights) so the
runtime can draw them progressively; tiles load from the style URL at view time."""
from __future__ import annotations

import math

from ..project import BuildContext
from ..spec import MapScene


def _great_circle(a, b, n=64):
    (lo1, la1), (lo2, la2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    d = 2 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
    if d == 0:
        return [a]
    out = []
    for i in range(n + 1):
        f = i / n
        A, B = math.sin((1 - f) * d) / math.sin(d), math.sin(f * d) / math.sin(d)
        x = A * math.cos(la1) * math.cos(lo1) + B * math.cos(la2) * math.cos(lo2)
        y = A * math.cos(la1) * math.sin(lo1) + B * math.cos(la2) * math.sin(lo2)
        z = A * math.sin(la1) + B * math.sin(la2)
        out.append([math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))])
    return out


def _densify(pts, geodesic):
    out = []
    for a, b in zip(pts, pts[1:]):
        seg = _great_circle(a, b) if geodesic else [[a[0] + (b[0] - a[0]) * f / 24, a[1] + (b[1] - a[1]) * f / 24] for f in range(25)]
        out.extend(seg if not out else seg[1:])
    return out


def build(sec: MapScene, ctx: BuildContext, theme: dict) -> dict:
    accent = theme["colors"]["accent"]
    routes = [{"id": r.id, "color": r.color or accent, "coords": _densify([list(p) for p in r.points], r.geodesic)} for r in sec.routes]
    return {"style": sec.style, "dark": sec.dark, "routes": routes, "markers": [m.model_dump() for m in sec.markers],
            "credits": ["Map data © OpenStreetMap contributors, tiles by OpenFreeMap"] if "openfreemap" in sec.style else []}
