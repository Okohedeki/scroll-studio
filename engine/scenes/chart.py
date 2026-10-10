"""chart: a CSV becomes a compact JSON series file; the runtime draws and animates it with D3.

Callouts are resolved here, at build time, from the data itself ({series, at: max|min|first|last|<x>, label}),
so a story's "peaked at 2,397 GW in 2025" is read from the numbers, not typed in.
"""
from __future__ import annotations

import csv
import json

from ..inputs import resolve_path
from ..project import BuildContext, BuildError, file_key
from ..spec import ChartScene


def _fmt(v: float, style: str, unit: str) -> str:
    if style == "percent":
        return f"{v:.0f}%" if abs(v) >= 10 else f"{v:.1f}%"
    if style == "compact":
        for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
            if abs(v) >= div:
                return f"{v / div:.1f}".rstrip("0").rstrip(".") + suf + unit
        return f"{v:,.0f}{unit}"
    if style == "integer":
        return f"{v:,.0f}{unit}"
    return (f"{v:,.0f}" if abs(v) >= 10 else f"{v:,.1f}") + unit


def _fmt_x(x: float) -> str:
    return str(int(x)) if 1800 < x < 2200 and float(x).is_integer() else (f"{x:,.0f}" if abs(x) >= 10 else f"{x:g}")


def resolve_callouts(sec: ChartScene, data: dict[str, list]) -> list[dict]:
    out = []
    for c in sec.callouts:
        pts = data.get(c["series"])
        if not pts:
            raise BuildError(f"callout series '{c['series']}' is not in the chart")
        at = c.get("at", "last")
        if at == "max":
            x, y = max(pts, key=lambda p: p[1])
        elif at == "min":
            x, y = min(pts, key=lambda p: p[1])
        elif at == "first":
            x, y = pts[0]
        elif at == "last":
            x, y = pts[-1]
        else:
            match = [p for p in pts if p[0] == float(at)]
            if not match:
                raise BuildError(f"callout: {c['series']} has no point at x = {at}")
            x, y = match[0]
        label = c.get("label", "{y}").replace("{y}", _fmt(y, sec.format, sec.unit)).replace("{x}", _fmt_x(x))
        out.append({"series": c["series"], "x": x, "label": label, "step": c.get("step")})
    return out


def build(sec: ChartScene, ctx: BuildContext, theme: dict) -> dict:
    src = resolve_path(ctx.project, sec.data, ctx.log)
    out = ctx.web / "data.json"

    def run():
        with open(src, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise BuildError(f"{sec.data} is empty")
        for col in [sec.x, sec.y] + ([sec.series] if sec.series else []):
            if col not in rows[0]:
                raise BuildError(f"column '{col}' not in {sec.data} (have: {', '.join(rows[0])})")
        series: dict[str, list] = {}
        for r in rows:
            name = r[sec.series] if sec.series else sec.y
            if sec.include and name not in sec.include:
                continue
            try:
                series.setdefault(name, []).append([float(r[sec.x]), float(r[sec.y])])
            except ValueError:
                continue
        names = sec.include or list(series)[:12]
        data = {n: sorted(series[n]) for n in names if n in series}
        missing = [n for n in names if n not in series]
        if missing:
            ctx.log(f"  warning: no rows for {missing}")
        callouts = resolve_callouts(sec, data)
        out.write_text(json.dumps({"series": data, "callouts": callouts}, separators=(",", ":")))
        ctx.log(f"  {len(data)} series, {sum(len(v) for v in data.values())} points, {len(callouts)} callouts")

    ctx.stage("data", {"src": file_key(src), "x": sec.x, "y": sec.y, "s": sec.series, "inc": sec.include,
                       "call": sec.callouts, "fmt": sec.format, "unit": sec.unit}, [out], run)
    return {"data": ctx.url(out), "kind": sec.kind, "yScale": sec.y_scale, "yLabel": sec.y_label, "unit": sec.unit,
            "format": sec.format, "source": sec.source, "colors": sec.colors, "credits": [sec.source] if sec.source else []}
