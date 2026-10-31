"""`studio build --profile` (engine/profile.py, issue #172): every stage reports what it did and how long it took, and
the report adds up per stage, section and backend."""
from __future__ import annotations

import json

from engine.profile import Profiler, report, table
from engine.project import BuildContext, Project


def test_stages_append_to_the_profile(tmp_path):
    p = Project(tmp_path / "p")
    stages: list = []
    ctx = BuildContext(p, "hero", log=lambda m: None, options={"profile": stages})
    out = ctx.work / "a.txt"
    ctx.stage("still", {"v": 1}, [out], lambda: out.write_text("x"))
    ctx.stage("still", {"v": 1}, [out], lambda: out.write_text("x"))
    assert [s["state"] for s in stages] == ["ran", "fresh"]
    assert stages[0]["section"] == "hero" and stages[0]["seconds"] >= 0


def test_no_profile_option_records_nothing(tmp_path):
    ctx = BuildContext(Project(tmp_path / "p"), "hero", log=lambda m: None)
    out = ctx.work / "a.txt"
    ctx.stage("still", {"v": 1}, [out], lambda: out.write_text("x"))
    assert "profile" not in ctx.options


def test_report_totals_and_order():
    stages = [{"section": "a", "stage": "film", "state": "ran", "seconds": 30.0},
              {"section": "b", "stage": "still", "state": "ran", "seconds": 4.0},
              {"section": "b", "stage": "still", "state": "ran", "seconds": 6.0},
              {"section": "c", "stage": "depth", "state": "fresh", "seconds": 0.0}]
    jobs = [{"backend": "local:comfy", "model": "z-image-turbo", "seconds": 5.0}]
    rep = report(stages, jobs, wall=42.0)
    assert rep["stage_seconds"] == 40.0 and rep["stages"] == {"ran": 3, "cached": 1}
    assert list(rep["by_stage"]) == ["film", "still"] and rep["by_stage"]["still"]["runs"] == 2
    assert list(rep["by_section"])[0] == "a"
    assert rep["by_backend"]["local:comfy (z-image-turbo)"]["jobs"] == 1
    text = table(rep)
    assert "42.0 s wall" in text and "film" in text and "backend local:comfy" in text


def test_profiler_writes_profile_json_with_the_builds_router_jobs(tmp_path):
    build = tmp_path / ".build"
    prof = Profiler(build)
    rec = build / "_router" / "records.jsonl"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({"at": 0, "backend": "old", "model": "m", "seconds": 1}) + "\n"
                   + json.dumps({"at": prof.t0 + 1, "backend": "new", "model": "m", "seconds": 2}) + "\nnot json\n",
                   encoding="utf-8")
    rep = prof.finish()
    assert list(rep["by_backend"]) == ["new (m)"]
    assert json.loads((build / "profile.json").read_text(encoding="utf-8"))["wall_seconds"] >= 0
