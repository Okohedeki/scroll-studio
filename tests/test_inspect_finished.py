"""`studio inspect` on a film section with `finish:` measures the finished film (what the page plays), not the film
before the finishing pass."""
from __future__ import annotations

import os

from engine.polish.run import film_candidates, find_film
from engine.project import Project
from engine.spec import FilmScene


def _sec(**kw):
    return FilmScene.model_validate({"id": "s", "beats": [{"id": "a", "prompt": "p", "motion": "m"}], **kw})


def _touch(p, t):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    os.utime(p, (t, t))
    return p


def test_a_finished_film_is_inspected_after_its_finishing_pass(tmp_path):
    (tmp_path / "site.yaml").write_text("name: T\nsections: []\n", encoding="utf-8")
    project = Project(tmp_path)
    g = project.build / "s" / "gen"
    beats = _touch(g / "beats.mp4", 1000)
    assert find_film(project, _sec()) == beats                       # no finish: the joined film, as before
    sec = _sec(finish=True)
    assert find_film(project, sec) == beats                          # finish not built yet
    restore = _touch(g / "finish" / "restore.mp4", 2000)
    assert find_film(project, sec) == restore
    clean = _touch(g / "finish" / "clean.mp4", 2001)
    assert find_film(project, sec) == clean                          # the last stage the page plays
    assert find_film(project, _sec(finish={"denoise": 0, "sharpen": 0})) == restore   # no clean stage in this pass


def test_a_finished_file_older_than_its_film_is_a_leftover(tmp_path):
    (tmp_path / "site.yaml").write_text("name: T\nsections: []\n", encoding="utf-8")
    project = Project(tmp_path)
    g = project.build / "s" / "gen"
    _touch(g / "finish" / "clean.mp4", 1000)
    beats = _touch(g / "beats.mp4", 2000)                             # re-joined since: the finish is stale
    assert find_film(project, _sec(finish=True)) == beats
    assert g / "finish" / "clean.mp4" not in film_candidates(project, _sec(finish=True))
