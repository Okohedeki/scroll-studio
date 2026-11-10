"""`studio inspect`: the polish report. Synthetic line-art films stand in for a render, so the measurements are checked
against things whose truth is known (a soft stretch, a one-frame flicker, a dissolve, a bright seam). No GPU, no ComfyUI."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import cv2
import numpy as np
import pytest

from engine.polish import analyze as A
from engine.polish import metrics as M
from engine.project import Project

W, H, FPS = 960, 544, 24


# ---------------------------------------------------------------- synthetic material

def scene(seed: int, w: int = W, h: int = H, bg: int = 232) -> np.ndarray:
    """A line-art scene: a pale ground and dark outlined shapes (BGR)."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), bg, np.uint8)
    for _ in range(26):
        cx, cy = int(rng.integers(40, w - 40)), int(rng.integers(40, h - 40))
        r = int(rng.integers(14, 60))
        tone = int(rng.integers(20, 150))
        if rng.random() < 0.5:
            cv2.circle(img, (cx, cy), r, (tone,) * 3, -1)
            cv2.circle(img, (cx, cy), r, (10, 10, 10), 2)
        else:
            cv2.rectangle(img, (cx - r, cy - r // 2), (cx + r, cy + r // 2), (tone,) * 3, -1)
            cv2.rectangle(img, (cx - r, cy - r // 2), (cx + r, cy + r // 2), (10, 10, 10), 2)
    for k in range(4):
        cv2.putText(img, "DesignAI %d" % k, (int(rng.integers(10, w // 2)), int(rng.integers(40, h - 20))),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (15, 15, 15), 2, cv2.LINE_AA)
    return img


def shifted(img: np.ndarray, dx: float, dy: float = 0.0) -> np.ndarray:
    m = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REPLICATE)


def enlarged(img: np.ndarray, k: int = 4) -> np.ndarray:
    """What a picture looks like when it was enlarged k times from fewer pixels."""
    h, w = img.shape[:2]
    return cv2.resize(cv2.resize(img, (w // k, h // k), interpolation=cv2.INTER_AREA), (w, h), interpolation=cv2.INTER_CUBIC)


def write_video(path: Path, frames, fps: int = FPS) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()
    return path


def gray(img: np.ndarray) -> np.ndarray:
    return M.gray_f32(img)


# ---------------------------------------------------------------- the measurements

def test_fine_detail_separates_an_enlarged_picture_from_a_sharp_one():
    s = scene(1)
    sharp, soft = M.spectral_detail(gray(s)), M.spectral_detail(gray(enlarged(s, 4)))
    assert sharp["detail"] > 2.5e-4, sharp                       # the "fine" side of the softness threshold
    assert soft["detail"] < 8e-5, soft                           # the "clearly upscaled" side
    assert sharp["detail"] > 20 * soft["detail"]


def test_edge_width_grows_with_enlargement():
    s = scene(2)
    w_sharp = M.edge_stats(gray(s))["width"]
    w_soft = M.edge_stats(gray(enlarged(s, 4)))["width"]
    assert w_sharp is not None and w_soft is not None
    assert w_soft > 1.8 * w_sharp


def test_rim_fraction_fires_on_bright_seams_not_on_clean_edges():
    def flat_shapes(seam: bool) -> np.ndarray:
        img = np.full((H, W, 3), 170, np.uint8)
        rng = np.random.default_rng(3)
        for _ in range(18):
            x, y = int(rng.integers(40, W - 200)), int(rng.integers(40, H - 140))
            w_, h_ = int(rng.integers(60, 190)), int(rng.integers(50, 120))
            if seam:                                    # a bright rim 3 px outside the shape: the depth-warp seam
                cv2.rectangle(img, (x - 5, y - 5), (x + w_ + 5, y + h_ + 5), (255, 255, 255), 3)
            cv2.rectangle(img, (x, y), (x + w_, y + h_), (12, 12, 12), -1)
        return img
    clean, seamed = M.edge_stats(gray(flat_shapes(False))), M.edge_stats(gray(flat_shapes(True)))
    assert clean["rim"] is not None and clean["rim"] < 0.05
    assert seamed["rim"] is not None and seamed["rim"] > 0.4


def test_motion_is_explained_by_flow_but_a_dissolve_is_not():
    a, b = scene(4), scene(5)
    ga = M.resize_w(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), M.FLOW_W)
    moved = M.resize_w(cv2.cvtColor(shifted(a, 12, 5), cv2.COLOR_BGR2GRAY), M.FLOW_W)
    mixed = M.resize_w(cv2.cvtColor(cv2.addWeighted(a, 0.5, b, 0.5, 0), cv2.COLOR_BGR2GRAY), M.FLOW_W)
    walk = M.step_stats(ga, moved)
    dissolve = M.step_stats(ga, mixed)
    assert walk["resid"] < 0.5 * walk["plain"]                  # it moved
    assert dissolve["resid"] > 0.8 * dissolve["plain"]          # it changed


def test_join_mismatch_tells_continuation_from_scene_change():
    a = scene(6)
    same = M.mismatch(a, shifted(a, 3, 1))
    other = M.mismatch(a, scene(7, bg=60))
    assert same["luma"] < A.RELATED_LUMA and same["edges"] < 0.6
    assert other["luma"] > A.RELATED_LUMA


# ---------------------------------------------------------------- a whole film

def film_frames() -> tuple[list[np.ndarray], dict]:
    """12 s: sharp (0-3), enlarged (3-6), sharp with a one-frame flicker at 7.5 and a cut glitch at 8.5 (6-9.5), a
    dissolve from one scene into another over 9.5-10.1 and sharp again to 12."""
    s1, s2 = scene(10), scene(11)
    out = []
    for i in range(12 * FPS):
        t = i / FPS
        f = shifted(s1, 0.8 * i)
        if 3 <= t < 6:
            f = enlarged(f, 4)
        elif 9.5 <= t < 10.1:
            k = (t - 9.5) / 0.6
            f = cv2.addWeighted(f, 1 - k, shifted(s2, 0.8 * i), k, 0)
        elif t >= 10.1:
            f = shifted(s2, 0.8 * i)
        out.append(f)
    out[int(7.5 * FPS)] = np.clip(out[int(7.5 * FPS)].astype(np.int16) + 45, 0, 255).astype(np.uint8)    # flicker
    out[int(8.5 * FPS)] = scene(12, bg=90)                                                                        # glitch frame
    return out, {"soft": (3.5, 5.5), "sharp": (0.5, 2.5), "flicker": 7.5, "glitch": 8.5, "dissolve": (9.4, 10.5)}


@pytest.fixture(scope="module")
def synthetic_scan(tmp_path_factory):
    frames, truth = film_frames()
    path = write_video(tmp_path_factory.mktemp("film") / "film.mp4", frames)
    sc = A.scan_film(path)
    st = A.steps_of(sc)
    return sc, st, truth


def peak(rows, lo, hi, key="sev"):
    v = [r[key] for r in rows if lo <= r["t"] <= hi]
    return max(v) if v else 0.0


def test_softness_is_flagged_where_the_picture_was_enlarged(synthetic_scan):
    sc, st, truth = synthetic_scan
    rows = A.score_softness(sc)
    assert peak(rows, *truth["soft"]) > 0.7
    assert peak(rows, *truth["sharp"]) < 0.2
    assert peak(rows, 6.5, 9.0) < 0.2                            # sharp again after the soft stretch


def test_a_flicker_and_a_glitch_are_pops(synthetic_scan):
    sc, st, truth = synthetic_scan
    rows = A.score_pops(st)
    flick = [r for r in rows if r["kind"] == "flash" and abs(r["t"] - truth["flicker"]) < 0.3]
    assert flick and flick[0]["sev"] > 0.5, rows
    jump = [r for r in rows if r["kind"] == "jump" and abs(r["t"] - truth["glitch"]) < 0.3]
    assert jump and jump[0]["sev"] > 0.5, rows
    # nothing else in the clean stretches
    assert not [r for r in rows if r["sev"] > 0.4 and 0.3 < r["t"] < 7.0 and r["kind"] != "stutter"]


def test_a_dissolve_inside_a_clip_is_a_morph_and_a_walk_is_not(synthetic_scan):
    sc, st, truth = synthetic_scan
    rows = A.score_morphs(st)
    assert peak(rows, *truth["dissolve"]) > 0.5, rows
    assert peak(rows, 0.5, 7.0) < 0.3                            # (the glitch at 8.5 is a pop, and also unexplained change)


def test_drift_stays_quiet_on_a_steady_look(synthetic_scan):
    sc, st, truth = synthetic_scan
    span = A.BeatSpan("film", 0.0, 12.0, None, "film")
    rows = A.score_drift(sc, st, [span], 0.0)
    assert peak(rows, 0.0, 9.0) < 0.4


# ---------------------------------------------------------------- a project

SPEC = textwrap.dedent('''\
    name: Polish test
    sections:
      - id: story
        type: film
        beat_res: [960, 544]
        beat_fade: 1.0
        beats:
          - id: a
            seconds: 4
            prompt: harbour
            motion: it drifts
          - id: b
            seconds: 4
            prompt: harbour closer
            motion: it drifts
          - id: c
            seconds: 4
            prompt: another place
            motion: it drifts
''')


def crossfade(clips: list[list[np.ndarray]], fade_frames: int) -> list[np.ndarray]:
    out = list(clips[0])
    for nxt in clips[1:]:
        base = out[:-fade_frames]
        tail = out[-fade_frames:]
        mixed = [cv2.addWeighted(a, 1 - (k + 1) / (fade_frames + 1), b, (k + 1) / (fade_frames + 1), 0)
                 for k, (a, b) in enumerate(zip(tail, nxt[:fade_frames]))]
        out = base + mixed + list(nxt[fade_frames:])
    return out


@pytest.fixture
def project(tmp_path):
    """A film of three beats: b picks up where a ended (a continuation), c is another place (a scene change)."""
    root = tmp_path / "p"
    (root / "inputs").mkdir(parents=True)
    (root / "site.yaml").write_text(SPEC, encoding="utf-8")
    s1, s2 = scene(20), scene(21, bg=40)
    n = 4 * FPS
    a = [shifted(s1, 0.5 * i) for i in range(n)]
    b = [shifted(s1, 0.5 * (n - 1) + 0.2 * i) for i in range(n)]          # starts on a's last frame
    c = [shifted(s2, 0.5 * i) for i in range(n)]
    build = root / ".build" / "story"
    for bid, clip in (("a", a), ("b", b), ("c", c)):
        write_video(build / "beats" / bid / "clip.mp4", clip)
    write_video(build / "gen" / "beats.mp4", crossfade([a, b, c], FPS))
    return Project(root)


def test_plan_spans_follow_the_engine_join(project):
    from engine.polish.run import plan_spans
    site = project.load()
    sec = site.sections[0]
    spans, fade = plan_spans(project, sec, 10.0)
    assert fade == pytest.approx(1.0)
    assert [round(s.start, 2) for s in spans] == [0.0, 3.0, 6.0]
    assert [round(s.end, 2) for s in spans] == [4.0, 7.0, 10.0]


def test_inspect_section_writes_json_html_and_pictures_and_is_cached(project):
    from engine import polish
    rep = polish.inspect_section(project, "story", log=lambda m: None)
    jpath, hpath = polish.report_path(project, "story")
    assert jpath.exists() and hpath.exists()
    assert rep["cached"] is False
    assert [b["id"] for b in rep["beats"]] == ["a", "b", "c"]
    assert set(rep["beats"][0]["scores"]) == set(polish.METRICS)
    assert rep["seconds"] and rep["timeline"]["pops"]
    on_disk = json.loads(jpath.read_text(encoding="utf-8"))
    assert on_disk["key"] == rep["key"]
    html = hpath.read_text(encoding="utf-8")
    assert "Polish report: story" in html and "Second by second" in html
    for x in rep["issues"]:
        assert x["reason"] and x["hint"] and x["level"] in ("slight", "visible", "bad")
        if x.get("thumb"):
            assert (jpath.parent / x["thumb"]).exists()
    # joins: a to b is one scene, b to c a scene change that is a dissolve on purpose
    j_ab, j_bc = rep["joins"]
    assert j_ab["related"] is True and j_bc["related"] is False and j_bc["sev"] == 0.0
    assert [b["scene"] for b in rep["beats"]] == [0, 0, 1]
    # unchanged film: the saved report, at once
    again = polish.inspect_section(project, "story", log=lambda m: None)
    assert again["cached"] is True and again["key"] == rep["key"]
    # a different film (the clip is rendered again) measures again
    film = project.build / "story" / "gen" / "beats.mp4"
    write_video(film, crossfade([[shifted(scene(30), 0.4 * i) for i in range(4 * FPS)]] * 3, FPS))
    third = polish.inspect_section(project, "story", log=lambda m: None)
    assert third["cached"] is False and third["key"] != rep["key"]


def test_a_film_that_is_not_built_says_so(project):
    from engine import polish
    (project.build / "story" / "gen" / "beats.mp4").unlink()
    with pytest.raises(polish.Nothing, match="no built film"):
        polish.inspect_section(project, "story", log=lambda m: None)


def test_beat_badges_name_the_worst_problem_and_know_a_stale_film(project):
    from engine import polish
    from engine.polish.run import content_key
    assert polish.beat_badges(project) == {}                     # no report yet: no badges
    rep = polish.inspect_section(project, "story", log=lambda m: None)
    badges = polish.beat_badges(project)
    assert set(badges) == {"a", "b", "c"}
    for b in rep["beats"]:
        badge = badges[b["id"]]
        assert badge["scores"] == b["scores"] and badge["report"] == "story.html" and badge["stale"] is False
        if b["worst"]:
            assert badge["metric"] == b["worst"]["metric"] and badge["reason"] == b["worst"]["reason"]
            assert rep["issues"][badge["anchor"]]["beat"] == b["id"]
    film = project.build / "story" / "gen" / "beats.mp4"
    write_video(film, [scene(40)] * (10 * FPS))
    assert content_key(film) != rep["film"]["content"]
    assert all(b["stale"] for b in polish.beat_badges(project).values())


def test_cli_prints_json_and_the_editor_state_carries_the_badge(project):
    from typer.testing import CliRunner

    from engine import polish
    from engine.cli import app
    from engine.storyboard.edit.workspace import Workspace
    runner = CliRunner()
    res = runner.invoke(app, ["inspect", str(project.root), "--section", "story", "--json"])
    assert res.exit_code == 0, res.output
    rep = json.loads(res.stdout[res.stdout.index("{"):])
    assert rep["section"] == "story" and len(rep["beats"]) == 3
    shots = {s["id"]: s for s in Workspace(project).state()["shots"] if s["section"] == "story"}
    assert set(shots) == {"a", "b", "c"}
    assert all(s["polish"] and s["polish"]["report"] == "story.html" for s in shots.values())
    assert set(polish.beat_badges(project)) == set(shots)


def test_a_video_file_is_one_shot(tmp_path, project):
    from engine import polish
    clip = write_video(tmp_path / "x.mp4", [shifted(scene(50), 0.6 * i) for i in range(3 * FPS)])
    rep = polish.inspect_video(project, str(clip), log=lambda m: None)
    assert rep["section"] == "x" and [b["id"] for b in rep["beats"]] == ["x"]
    assert polish.report_path(project, "x")[1].exists()


def test_a_crossfade_between_shots_that_do_not_line_up_ghosts_and_one_that_does_not(tmp_path):
    """A continuation: the outgoing shot still moves while the incoming one holds the last frame, so at mid-fade the two
    pictures are far out of line (a double image). With both held there is nothing to see."""
    s1 = scene(60)
    n = 2 * FPS
    moving = [shifted(s1, 6.0 * i) for i in range(n)]
    hold_moving = [moving[-1]] * n
    hold_a = [moving[0]] * n
    hold_b = [moving[0]] * n
    ghost = tmp_path / "ghost"
    write_video(ghost / "a.mp4", moving)
    write_video(ghost / "b.mp4", hold_moving)
    still = tmp_path / "still"
    write_video(still / "a.mp4", hold_a)
    write_video(still / "b.mp4", hold_b)
    for folder, expect_bad in ((ghost, True), (still, False)):
        spans = [A.BeatSpan("a", 0.0, 2.0, folder / "a.mp4"), A.BeatSpan("b", 1.0, 3.0, folder / "b.mp4")]
        (j,) = A.score_joins(spans, 1.0)
        assert j["related"] is True
        if expect_bad:
            assert j["disp"] > 60 and j["sev"] > 0.9, j
        else:
            assert j["disp"] < 5 and j["sev"] == 0.0, j


def test_a_video_section_is_one_shot_and_its_badge_is_named_by_the_section(tmp_path):
    from engine import polish
    root = tmp_path / "v"
    (root / "inputs").mkdir(parents=True)
    (root / "site.yaml").write_text("name: V\nsections:\n  - id: reel\n    type: film\n    video: inputs/reel.mp4\n", encoding="utf-8")
    write_video(root / "inputs" / "reel.mp4", [shifted(scene(70), 0.6 * i) for i in range(3 * FPS)])
    project = Project(root)
    rep = polish.inspect_section(project, "reel", log=lambda m: None)
    assert [b["id"] for b in rep["beats"]] == ["film"] and rep["joins"] == []
    assert set(polish.beat_badges(project)) == {"reel"}
