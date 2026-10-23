"""tools/check_coverage.py: the floors that keep test coverage from sliding back."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_coverage", ROOT / "tools" / "check_coverage.py")
cc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cc        # dataclasses looks its module up here
_spec.loader.exec_module(cc)


def report(**files):
    """A coverage.json with {path: (covered, statements)}; separators are kept as written."""
    entries = {p: {"summary": {"covered_lines": c, "num_statements": n}} for p, (c, n) in files.items()}
    covered = sum(c for c, _ in files.values())
    total = sum(n for _, n in files.values())
    return {"files": entries, "totals": {"covered_lines": covered, "num_statements": total,
                                         "percent_covered": 100.0 * covered / total}}


WIN_PATH = "engine" + chr(92) + "compile" + chr(92) + "b.py"      # a Windows runner writes backslashes
FAKE = report(**{"engine/spec.py": (90, 100), "engine/compile/a.py": (30, 50), WIN_PATH: (50, 50),
                 "engine/cli.py": (10, 100)})


def by_area(rows):
    return {r.area: r for r in rows}


def test_areas_sum_the_files_under_a_folder_or_name_a_single_file():
    rows = by_area(cc.evaluate(FAKE, {"total": 50, "areas": {"engine/compile": 80, "engine/spec.py": 90,
                                                              "engine/cli.py": 10}}))
    assert rows["engine/compile"].percent == pytest.approx(80.0) and rows["engine/compile"].statements == 100
    assert rows["engine/spec.py"].percent == 90.0
    assert rows["total"].percent == pytest.approx(100 * 180 / 300)


def test_a_folder_name_does_not_match_a_longer_sibling():
    rows = by_area(cc.evaluate(report(**{"engine/spec.py": (1, 1), "engine/spec_extra.py": (0, 9)}),
                               {"total": 1, "areas": {"engine/spec.py": 1}}))
    assert rows["engine/spec.py"].statements == 1


def test_status_ok_below_raise_and_missing():
    rows = by_area(cc.evaluate(FAKE, {"total": 70, "areas": {"engine/compile": 80, "engine/spec.py": 85,
                                                              "engine/cli.py": 50, "engine/gone": 10}}))
    assert rows["total"].status == "below"             # 60% against 70
    assert rows["engine/compile"].status == "ok"       # exactly at the floor
    assert rows["engine/spec.py"].status == "raise"    # 5 points above its floor
    assert rows["engine/cli.py"].status == "below"
    assert rows["engine/gone"].status == "missing"


def test_beating_a_floor_by_two_points_asks_for_it_to_be_raised():
    rows = cc.evaluate(FAKE, {"total": 60, "areas": {"engine/spec.py": 88, "engine/compile": 80}})
    by = by_area(rows)
    assert by["engine/spec.py"].status == "raise" and by["engine/compile"].status == "ok"
    notes = cc.advice(rows)
    assert len(notes) == 1 and "engine/spec.py to 90" in notes[0] and "coverage_floors.json" in notes[0]


def test_the_table_names_each_area_and_flags_the_ones_below(tmp_path):
    rows = cc.evaluate(FAKE, {"total": 70, "areas": {"engine/cli.py": 50}})
    text = cc.table(rows)
    assert "engine/cli.py" in text and "BELOW THE FLOOR" in text and "10.0%" in text
    md = cc.table(rows, markdown=True)
    assert md.splitlines()[0].startswith("| area |") and md.splitlines()[1].startswith("|---")


def test_the_command_exits_nonzero_below_a_floor_and_writes_the_summary(tmp_path, capsys):
    cov = tmp_path / "coverage.json"
    cov.write_text(json.dumps(FAKE))
    floors = tmp_path / "floors.json"
    summary = tmp_path / "summary.md"
    floors.write_text(json.dumps({"total": 50, "areas": {"engine/compile": 80}}))
    assert cc.main([str(cov), "--floors", str(floors), "--markdown", str(summary)]) == 0
    assert "| engine/compile |" in summary.read_text()
    floors.write_text(json.dumps({"total": 61, "areas": {"engine/compile": 80}}))
    assert cc.main([str(cov), "--floors", str(floors)]) == 1
    assert "under its floor of 61%" in capsys.readouterr().out


def test_the_repository_floors_file_is_well_formed():
    floors = json.loads((ROOT / "tests" / "coverage_floors.json").read_text(encoding="utf-8"))
    assert isinstance(floors["total"], int) and 0 < floors["total"] <= 100
    for area, floor in floors["areas"].items():
        assert (ROOT / area).exists(), f"{area} is in coverage_floors.json but not in the repository"
        assert isinstance(floor, int) and 0 <= floor <= 100
