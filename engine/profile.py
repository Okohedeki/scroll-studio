"""`studio build --profile`: where a build's time goes, per stage, section and backend (issue #172).

Every stage appends what it did (ran, fresh, locked, migrated) and its seconds; the model router's records for the build
add which backend each image, edit and text job ran on. The report is written to .build/profile.json and printed as a
short table, slowest first, so speed work starts from measurements rather than guesses.
"""
from __future__ import annotations

import json
import platform
import time
from collections import defaultdict
from pathlib import Path


def router_jobs(build: Path, since: float) -> list[dict]:
    path = build / "_router" / "records.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("at", 0) >= since - 1:
            out.append(entry)
    return out


def report(stages: list[dict], jobs: list[dict], wall: float, draft: bool = False) -> dict:
    """The profile: totals, per section, per stage name and per backend."""
    by_section: dict = defaultdict(float)
    by_stage: dict = defaultdict(lambda: {"runs": 0, "seconds": 0.0})
    for s in stages:
        by_section[s["section"]] += s["seconds"]
        if s["state"] == "ran":
            by_stage[s["stage"]]["runs"] += 1
            by_stage[s["stage"]]["seconds"] += s["seconds"]
    by_backend: dict = defaultdict(lambda: {"jobs": 0, "seconds": 0.0})
    for j in jobs:
        b = by_backend[f"{j.get('backend')} ({j.get('model')})"]
        b["jobs"] += 1
        b["seconds"] += j.get("seconds") or 0.0
    ran = [s for s in stages if s["state"] == "ran"]
    return {
        "wall_seconds": round(wall, 1),
        "stage_seconds": round(sum(s["seconds"] for s in ran), 1),
        "stages": {"ran": len(ran), "cached": len(stages) - len(ran)},
        "draft": draft,
        "machine": {"system": platform.system(), "python": platform.python_version()},
        "by_section": {k: round(v, 1) for k, v in sorted(by_section.items(), key=lambda kv: -kv[1])},
        "by_stage": {k: {**v, "seconds": round(v["seconds"], 1)}
                     for k, v in sorted(by_stage.items(), key=lambda kv: -kv[1]["seconds"])},
        "by_backend": {k: {**v, "seconds": round(v["seconds"], 1)} for k, v in by_backend.items()},
        "detail": stages,
    }


def table(rep: dict, top: int = 12) -> str:
    lines = [f"profile: {rep['wall_seconds']:.1f} s wall, {rep['stage_seconds']:.1f} s in "
             f"{rep['stages']['ran']} stages that ran ({rep['stages']['cached']} cached)"]
    for name, v in list(rep["by_stage"].items())[:top]:
        lines.append(f"  {name:<28} {v['runs']:>3} runs  {v['seconds']:>8.1f} s")
    for name, v in rep["by_backend"].items():
        lines.append(f"  backend {name:<40} {v['jobs']:>3} jobs  {v['seconds']:>8.1f} s")
    return "\n".join(lines)


class Profiler:
    """Collects a build's stages (pass .stages as options["profile"]) and writes the report."""

    def __init__(self, build: Path, draft: bool = False):
        self.build, self.draft, self.stages, self.t0 = build, draft, [], time.time()

    def finish(self) -> dict:
        rep = report(self.stages, router_jobs(self.build, self.t0), time.time() - self.t0, self.draft)
        self.build.mkdir(parents=True, exist_ok=True)
        (self.build / "profile.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
        return rep
