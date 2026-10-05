"""chart: a CSV becomes a compact JSON series file; the runtime draws and animates it with D3."""
from __future__ import annotations

import csv
import json

from ..inputs import resolve_path
from ..project import BuildContext, BuildError, file_key
from ..spec import ChartScene


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
        out.write_text(json.dumps({"series": data}, separators=(",", ":")))
        ctx.log(f"  {len(data)} series, {sum(len(v) for v in data.values())} points")

    ctx.stage("data", {"src": file_key(src), "x": sec.x, "y": sec.y, "s": sec.series, "inc": sec.include}, [out], run)
    return {"data": ctx.url(out), "kind": sec.kind, "yScale": sec.y_scale, "yLabel": sec.y_label, "unit": sec.unit,
            "source": sec.source, "colors": sec.colors, "credits": [sec.source] if sec.source else []}
