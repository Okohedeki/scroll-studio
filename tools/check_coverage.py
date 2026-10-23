"""Fail when test coverage drops below the floors in tests/coverage_floors.json.

    python tools/check_coverage.py coverage.json [--floors tests/coverage_floors.json] [--markdown "$GITHUB_STEP_SUMMARY"]

`coverage.json` comes from `pytest --cov --cov-report=json:coverage.json`. The floors file has a `total` and an `areas` map
of repository paths (a folder or a single file) to a whole percent; an area is the sum of the statements of every measured
file under that path. Floors only go up: when a change lifts a number by RAISE_AT points or more, the table asks for the
floor to be raised in the same pull request, so a later change cannot give the coverage back unnoticed."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

RAISE_AT = 2.0          # points above its floor at which an area asks for the floor to be raised
DEFAULT_FLOORS = Path(__file__).resolve().parent.parent / "tests" / "coverage_floors.json"


@dataclass
class Row:
    area: str
    floor: float
    percent: float | None       # None: nothing measured under this path
    statements: int

    @property
    def status(self) -> str:
        if self.percent is None:
            return "missing"
        if self.percent < self.floor:
            return "below"
        return "raise" if self.percent >= self.floor + RAISE_AT else "ok"


def area_percent(files: dict, area: str) -> tuple[float | None, int]:
    """(percent covered, statements) of the files at or under `area`, paths compared with forward slashes."""
    covered = total = 0
    for name, entry in files.items():
        path = name.replace("\\", "/")
        if path == area or path.startswith(area.rstrip("/") + "/"):
            covered += entry["summary"]["covered_lines"]
            total += entry["summary"]["num_statements"]
    return (100.0 * covered / total if total else None), total


def evaluate(report: dict, floors: dict) -> list[Row]:
    totals = report["totals"]
    rows = [Row("total", float(floors["total"]), float(totals["percent_covered"]), int(totals["num_statements"]))]
    for area, floor in floors.get("areas", {}).items():
        percent, statements = area_percent(report["files"], area)
        rows.append(Row(area, float(floor), percent, statements))
    return rows


def table(rows: list[Row], markdown: bool = False) -> str:
    head = ["area", "statements", "covered", "floor", "status"]
    body = [[r.area, str(r.statements), "-" if r.percent is None else f"{r.percent:.1f}%", f"{r.floor:g}%",
             {"ok": "ok", "raise": "raise the floor", "below": "BELOW THE FLOOR", "missing": "NOT MEASURED"}[r.status]]
            for r in rows]
    if markdown:
        lines = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
        return "\n".join(lines + ["| " + " | ".join(row) + " |" for row in body])
    widths = [max(len(x[i]) for x in [head] + body) for i in range(len(head))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in [head] + body)


def advice(rows: list[Row], floors_file: str = "tests/coverage_floors.json") -> list[str]:
    out = []
    for r in rows:
        if r.status == "below":
            out.append(f"{r.area}: {r.percent:.1f}% is under its floor of {r.floor:g}%. Add tests for the code you changed "
                       "(the floors are what the suite covered before this change).")
        elif r.status == "missing":
            out.append(f"{r.area}: no measured file under this path; fix or remove it in {floors_file}.")
    raised = [f"{r.area} to {int(r.percent)}" for r in rows if r.status == "raise"]
    if raised:
        out.append(f"Raise the floors in {floors_file} (they only go up): " + ", ".join(raised) + ".")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("coverage_json", type=Path)
    ap.add_argument("--floors", type=Path, default=DEFAULT_FLOORS)
    ap.add_argument("--markdown", type=Path, help="append the table here as Markdown (CI passes $GITHUB_STEP_SUMMARY)")
    args = ap.parse_args(argv)
    report = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    floors = json.loads(args.floors.read_text(encoding="utf-8"))
    rows = evaluate(report, floors)
    print(table(rows))
    notes = advice(rows)
    for n in notes:
        print(n)
    if args.markdown:
        with args.markdown.open("a", encoding="utf-8") as f:
            f.write("### Coverage\n\n" + table(rows, markdown=True) + "\n\n" + "".join(f"- {n}\n" for n in notes) + "\n")
    return 1 if any(r.status in ("below", "missing") for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
