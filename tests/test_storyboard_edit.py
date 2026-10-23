"""The storyboard edit workspace: editing site.yaml in place, the shot model, variants, approvals, and that the cache
digests the build uses did not move. No ComfyUI, Blender or GPU is needed."""
from __future__ import annotations

import hashlib
import json
import textwrap

import pytest
import yaml

from engine.inputs import edit_path, generated_path
from engine.project import Project, file_key
from engine.spec import ImageInput
from engine.storyboard.edit import approvals, shots, specdoc, variants
from engine.storyboard.edit.render import cache_target, with_recipe
from engine.storyboard.edit.workspace import Workspace, coerce

SPEC = textwrap.dedent('''\
    # a page with comments that must survive
    name: Test   # trailing comment
    theme: { preset: night, colors: { bg: "#0b0b0d", accent:  "#ff8200" } }
    sections:
      - id: story
        type: film
        beat_res: [1024, 576]
        beats:
          # the first shot
          - id: a
            seconds: 4
            seed: 21
            prompt: 'It''s a harbour, at dawn: boats'
            motion: the camera drifts
            image:
              edit:
                instruction: crop to the left
                source:
                  edit:
                    instruction: relight, golden hour
                    source: { generate: "a harbour at dawn", seed: 11, size: [1024, 576] }
          - id: b
            seconds: 4
            prompt: second shot
            motion: it moves
            image:
              edit:
                instruction: crop to the right
                source:
                  edit:
                    instruction: relight, golden hour
                    source: { generate: "a harbour at dawn", seed: 11, size: [1024, 576] }
          - id: c
            prompt: third shot draws its own still
            motion: it moves
            end_image: inputs/end.png
        steps:
          - { title: Hello <em>there.</em>, state: { beat: a } }
          - title: Second
            state: { beat: b }
      - type: cta
        title: Go
        button: { label: Go, href: "#" }
    footer:
      left: Footer
''')


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "p"
    (root / "inputs").mkdir(parents=True)
    (root / "site.yaml").write_text(SPEC, encoding="utf-8")
    from PIL import Image
    Image.new("RGB", (64, 36), "#335577").save(root / "inputs" / "end.png")
    return Project(root)


# ---------------------------------------------------------------- the build's cache keys did not move

def test_cache_digests_unchanged(project):
    """generated_path / edit_path are the formulas resolve_image always used (the feel example stays fully cached)."""
    ref = ImageInput(generate="a harbour at dawn", seed=11, size=(1024, 576))
    w, h = (int(v) // 16 * 16 for v in ref.size)
    old = hashlib.sha1(json.dumps([ref.generate, w, h, ref.seed]).encode()).hexdigest()[:12]
    assert generated_path(project, ref).name == f"{old}.png"
    src = project.root / "inputs" / "end.png"
    e = ImageInput(edit={"source": "inputs/end.png", "instruction": "x", "seed": 3, "steps": 30})
    old = hashlib.sha1(json.dumps([[file_key(src)], "x", 3, 30, 2]).encode()).hexdigest()[:12]
    assert edit_path(project, e, [src]).name == f"edit_{old}.png"


def test_pinned_digest_values(project):
    # computed with the engine before this feature existed; these must never change
    ref = ImageInput(generate="a harbour at dawn", seed=11, size=(1024, 576))
    assert generated_path(project, ref).name == "4cf7c5ad188a.png"


# ---------------------------------------------------------------- editing site.yaml

def edit(text, *ops):
    return specdoc.apply_ops(text, list(ops))


def test_splice_changes_only_the_edited_text():
    new = edit(SPEC, specdoc.Op(("sections", 0, "beats", 0, "seconds"), 6),
               specdoc.Op(("sections", 0, "steps", 1, "title"), "Second, edited"),
               specdoc.Op(("theme", "colors", "accent"), "#00ff00"))
    a, b = SPEC.splitlines(), new.splitlines()
    assert len(a) == len(b)
    changed = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    assert len(changed) == 3                      # three lines, nothing else (comments, alignment, flow maps intact)
    assert "# the first shot" in new and "# trailing comment" in new and 'accent:  "#00ff00"' in new
    assert yaml.safe_load(new)["sections"][0]["beats"][0]["seconds"] == 6


def test_splice_quoting_and_new_keys():
    new = edit(SPEC, specdoc.Op(("sections", 0, "beats", 0, "prompt"), "Don't panic: it's fine"),
               specdoc.Op(("sections", 0, "beats", 1, "seed"), 99),                    # a new key in a block mapping
               specdoc.Op(("sections", 0, "beats", 0, "image", "edit", "source", "edit", "source", "credit"), "Me"))  # in a flow one
    data = yaml.safe_load(new)
    beats = data["sections"][0]["beats"]
    assert beats[0]["prompt"] == "Don't panic: it's fine"
    assert beats[1]["seed"] == 99
    assert beats[0]["image"]["edit"]["source"]["edit"]["source"]["credit"] == "Me"
    assert "size: [1024, 576], credit: Me }" in new
    specdoc.validate(new)


def test_splice_keeps_crlf():
    text = SPEC.replace("\n", "\r\n")
    new = edit(text, specdoc.Op(("sections", 0, "beats", 1, "seed"), 5), specdoc.Op(("name",), "Renamed"))
    assert "\r\n" in new and "\n" not in new.replace("\r\n", "")
    assert yaml.safe_load(new)["name"] == "Renamed"


def test_delete_a_key():
    new = edit(SPEC, specdoc.Op(("sections", 0, "beats", 0, "seed"), delete=True))
    assert "seed: 21" not in new and "seed" not in yaml.safe_load(new)["sections"][0]["beats"][0]


def test_anchors_survive():
    text = textwrap.dedent('''\
        name: A
        sections:
          - id: s
            type: film
            beats:
              - id: a
                prompt: p
                motion: m
                image: &base { generate: "base", seed: 1, size: [1024, 576] }
              - id: b
                prompt: q
                motion: m
                image: *base
    ''')
    new = edit(text, specdoc.Op(("sections", 0, "beats", 0, "image", "seed"), 9))
    assert "&base" in new and "*base" in new
    d = yaml.safe_load(new)
    assert d["sections"][0]["beats"][1]["image"]["seed"] == 9      # one node: both shots follow


def test_round_trip_fallback_for_what_a_splice_cannot_do():
    new = edit(SPEC, specdoc.Op(("sections", 0, "beats", 2, "end_image"), {"generate": "an ending", "seed": 4}))
    assert yaml.safe_load(new)["sections"][0]["beats"][2]["end_image"] == {"generate": "an ending", "seed": 4}
    assert "# the first shot" in new and "# trailing comment" in new


def test_invalid_edit_is_refused_and_nothing_is_written(project):
    before = project.spec_path.read_bytes()
    with pytest.raises(specdoc.SpecError) as e:
        specdoc.save(project, [specdoc.Op(("sections", 0, "beats", 0, "seconds"), 99)])     # beats are 1 to 10 s
    assert any("seconds" in x["loc"] for x in e.value.errors)
    assert project.spec_path.read_bytes() == before


def test_save_history_undo_and_conflict(project):
    p = project
    r = specdoc.save(p, [specdoc.Op(("sections", 0, "beats", 0, "seconds"), 5)], expect={("sections", 0, "beats", 0, "seconds"): 4})
    assert r["changed"] and (specdoc.history_dir(p) / r["history"]).exists()
    assert specdoc.can_undo(p)
    with pytest.raises(specdoc.Conflict):                    # the page last saw 4; the file now says 5
        specdoc.save(p, [specdoc.Op(("sections", 0, "beats", 0, "seconds"), 6)], expect={("sections", 0, "beats", 0, "seconds"): 4})
    specdoc.undo(p)
    assert yaml.safe_load(p.spec_path.read_text(encoding="utf-8"))["sections"][0]["beats"][0]["seconds"] == 4
    assert p.spec_path.read_text(encoding="utf-8") == SPEC


def test_undo_refuses_when_the_file_changed_since(project):
    specdoc.save(project, [specdoc.Op(("name",), "One")])
    project.spec_path.write_text(project.spec_path.read_text(encoding="utf-8").replace("One", "Two"), encoding="utf-8")
    assert not specdoc.can_undo(project)


# ---------------------------------------------------------------- the shot model

def test_shots_slots_and_shared_steps(project):
    b = shots.build(project)
    assert [s.id for s in b.shots] == ["a", "b", "c"]
    a = b.shot("a")
    assert [sl.id for sl in a.slots] == ["a/still"]
    assert [n.kind for n in a.slots[0].nodes] == ["edit", "edit", "generate"]
    # the relight and the base image are the same in a and b: shared, listed once
    assert [n.shared for n in a.slots[0].nodes] == [False, True, True]
    assert {n.kind for n in b.shared} == {"edit", "generate"} and len(b.shared) == 2
    assert b.shared[0].used_by == ["a", "b"]
    # an edit of a shared field is written in both places
    f = b.shared[1].fields[0]
    assert len(f.paths) == 2 and f.paths[0] != f.paths[1]
    # c draws its own still from its prompt and seed; the end image is a project file
    c = b.shot("c")
    assert [sl.name for sl in c.slots] == ["still", "end"]
    assert c.slots[0].nodes[0].fields[0].paths == [("sections", 0, "beats", 2, "prompt")]
    assert c.slots[1].nodes[0].kind == "file"
    # captions are the steps pinned to the beat
    assert a.field("caption").raw == "Hello <em>there.</em>"
    assert b.shot("cta") is None


def test_every_field_path_points_at_its_value(project):
    b = shots.build(project)
    for s in b.shots:
        for f in s.all_fields():
            for p in f.paths:
                got = specdoc.get(b.raw, p)
                assert (got is specdoc.MISSING and f.raw is None) or got == f.raw, (s.id, f.name, p)


def test_with_recipe_changes_the_seed_in_memory_only(project):
    b = shots.build(project)
    node = b.shot("a").slots[0].nodes[0]
    ref = with_recipe(node, dict(node.recipe(), seed=777))
    assert ref.edit.seed == 777 and node.ref.edit.seed == 7
    assert cache_target(project, b.shot("c").slots[0].nodes[0]).name == generated_path(
        project, b.shot("c").slots[0].nodes[0].ref).name


def test_workspace_save_by_name_and_lock(project):
    ws = Workspace(project)
    ws.set_fields("a", {"caption": "Hi <em>you.</em>", "seconds": 6, "motion": "pans left"})
    d = yaml.safe_load(project.spec_path.read_text(encoding="utf-8"))
    assert d["sections"][0]["steps"][0]["title"] == "Hi <em>you.</em>"
    assert d["sections"][0]["beats"][0]["seconds"] == 6 and d["sections"][0]["beats"][0]["motion"] == "pans left"
    ws.set_lock("a", True)
    assert yaml.safe_load(project.spec_path.read_text(encoding="utf-8"))["sections"][0]["beats"][0]["locked"] is True
    ws.set_lock("a", False)
    assert yaml.safe_load(project.spec_path.read_text(encoding="utf-8"))["sections"][0]["beats"][0]["locked"] is False
    with pytest.raises(Exception):
        ws.set_fields("a", {"nope": 1})
    with pytest.raises(specdoc.SpecError):
        ws.save([{"path": "sections.0.beats.0.seconds", "value": 50}])


def test_shared_edit_reaches_every_place(project):
    ws = Workspace(project)
    b = shots.build(project)
    f = b.shared[1].fields[0]                                  # the base image's prompt
    ws.save([{"path": specdoc.dotted(f.paths[0]), "value": "a harbour at dusk"}])
    d = yaml.safe_load(project.spec_path.read_text(encoding="utf-8"))
    beats = d["sections"][0]["beats"]
    assert beats[0]["image"]["edit"]["source"]["edit"]["source"]["generate"] == "a harbour at dusk"
    assert beats[1]["image"]["edit"]["source"]["edit"]["source"]["generate"] == "a harbour at dusk"
    assert shots.build(project).shared[1].used_by == ["a", "b"]       # still one shared node after the edit


def test_coerce():
    b = shots.build.__globals__["_B"]({})
    f = b.fld("n", "n", "int", ("x",), 3)
    assert coerce(f, "7") == 7 and coerce(f, "") is None
    with pytest.raises(ValueError):
        coerce(f, "2.5")
    g = b.fld("t", "t", "float", ("x",), 3.0)
    assert coerce(g, "4.0") == 4 and coerce(g, "1.5") == 1.5


# ---------------------------------------------------------------- variants and approvals

def test_variants_register_dedupe_history_revert(project, tmp_path):
    from PIL import Image
    imgs = []
    for i in range(3):
        p = tmp_path / f"i{i}.png"
        Image.new("RGB", (32, 18), (i * 60, 10, 10)).save(p)
        imgs.append(p)
    k = "a/still"
    v1 = variants.register(project, k, imgs[0], "c1", {"seed": 1}, "original", 1)
    v2 = variants.register(project, k, imgs[1], "c2", {"seed": 2}, "regenerate", 2, make_current=True)
    again = variants.register(project, k, imgs[1], "c2", {"seed": 2}, "rerun", 2, make_current=True)
    assert again["n"] == v2["n"] == 2 and v1["n"] == 1                 # one entry per cache entry
    variants.push_history(project, k, 1)
    variants.push_history(project, k, 2)
    assert variants.revert_target(project, k)["n"] == 1
    assert variants.used_seeds(project, k) == {1, 2}
    assert variants.file_of(project, k, v2).exists()


def test_one_job_per_image(project):
    lock = variants.claim(project, "a/still", "regenerate")
    with pytest.raises(variants.Busy):
        variants.claim(project, "a/still", "rerun")
    variants.release(lock)
    variants.release(variants.claim(project, "a/still", "rerun"))


def test_approvals_follow_the_shot(project):
    b = shots.build(project)
    assert approvals.summary(project) is None                          # nobody has approved anything: no nagging
    approvals.set_approved(project, b, "a", True)
    s = approvals.summary(project)
    assert s["approved"] == 1 and s["pending"] == ["b", "c"]
    Workspace(project).set_fields("a", {"seconds": 5})
    assert approvals.status(project, shots.build(project))["a"] == "changed"
    approvals.set_approved(project, shots.build(project), "a", True)
    assert approvals.status(project, shots.build(project))["a"] == "approved"


# ---------------------------------------------------------------- picking a variant reproduces the image from cache

def test_pick_writes_the_recipe_and_restores_the_cache(project):
    from PIL import Image
    from engine.storyboard.edit import images
    ws = Workspace(project)
    node = shots.build(project).shot("c").slots[0].nodes[0]
    key = node.key
    # an earlier render of this shot's still with seed 555, from before the cache was cleaned
    ref = with_recipe(node, dict(node.recipe(), seed=555))
    cache = generated_path(project, ref)
    cache.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36), "#aa3300").save(cache)
    variants.register(project, key, cache, images.rel(project, cache), dict(node.recipe(), seed=555), "regenerate", 555, make_current=True)
    cache.unlink()
    res = ws.pick(key, 1)
    assert res["wrote"] == ["seed"] and res["restored_cache"] and res["in_cache"]
    assert yaml.safe_load(project.spec_path.read_text(encoding="utf-8"))["sections"][0]["beats"][2]["seed"] == 555
    assert cache.exists()                                      # the full build now finds exactly that image
    st = ws.state()
    c = next(s for s in st["shots"] if s["id"] == "c")
    top = c["slots"][0]["nodes"][0]
    assert top["image"]["state"] == "current"
    assert [v["current"] for v in top["variants"]][0] is True


def test_revert_goes_back_to_the_previous_image(project):
    from PIL import Image
    from engine.storyboard.edit import images
    ws = Workspace(project)
    node = shots.build(project).shot("c").slots[0].nodes[0]
    key, base = node.key, node.recipe()
    made = []
    for seed in (base["seed"], 601, 602):
        ref = with_recipe(node, dict(base, seed=seed))
        p = generated_path(project, ref)
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 36), (seed % 255, 40, 40)).save(p)
        made.append(variants.register(project, key, p, images.rel(project, p), dict(base, seed=seed), "regenerate", seed, make_current=True))
    ws.pick(key, 3)                       # 602 written into the spec
    ws.pick(key, 2)                       # 601
    res = ws.revert(key)                  # back to 602, the one before
    assert res["reverted_to"] == 3
    assert yaml.safe_load(project.spec_path.read_text(encoding="utf-8"))["sections"][0]["beats"][2]["seed"] == 602


# ---------------------------------------------------------------- the HTTP side

def test_http_save_validation_conflict_and_lock(project):
    from fastapi.testclient import TestClient
    from engine.storyboard.edit.api import make_app
    c = TestClient(make_app(project))
    name = project.name
    st = c.get(f"/api/sb/{name}/state").json()
    assert [s["id"] for s in st["shots"]] == ["a", "b", "c"]
    a = next(s for s in st["shots"] if s["id"] == "a")
    sec = next(f for f in a["fields"] if f["name"] == "seconds")
    # ok
    r = c.post(f"/api/sb/{name}/save", json={"edits": [{"path": sec["paths"][0], "value": "5", "old": sec["raw"]}]})
    assert r.status_code == 200 and r.json()["changed"] == [sec["paths"][0]]
    # the page still holds the old value: refused, nothing overwritten
    r = c.post(f"/api/sb/{name}/save", json={"edits": [{"path": sec["paths"][0], "value": "6", "old": sec["raw"]}]})
    assert r.status_code == 409 and r.json()["conflict"] == [sec["paths"][0]]
    # invalid: 422 with the error, file untouched
    before = project.spec_path.read_bytes()
    r = c.post(f"/api/sb/{name}/save", json={"edits": [{"path": sec["paths"][0], "value": "50", "old": 5}]})
    assert r.status_code == 422 and r.json()["errors"] and project.spec_path.read_bytes() == before
    # a path that is not a field of the spec is refused
    r = c.post(f"/api/sb/{name}/save", json={"edits": [{"path": "footer.left", "value": "x"}]})
    assert r.status_code == 422
    # lock and approve
    assert c.post(f"/api/sb/{name}/lock", json={"shot": "a", "locked": True}).status_code == 200
    assert yaml.safe_load(project.spec_path.read_text(encoding="utf-8"))["sections"][0]["beats"][0]["locked"] is True
    assert c.post(f"/api/sb/{name}/approve", json={"shot": "a", "approved": True}).json()["approval"] == "approved"
    # a locked shot's images are not rendered
    r = c.post(f"/api/sb/{name}/image", json={"key": "a/still", "mode": "rerun"})
    assert r.status_code == 400 and "locked" in r.json()["error"]
    # poll tells the page's own write from an outside one
    p = c.get(f"/api/sb/{name}/poll").json()
    assert p["own"] is True
    project.spec_path.write_text(project.spec_path.read_text(encoding="utf-8").replace("name: Test", "name: Edited outside"), encoding="utf-8")
    assert c.get(f"/api/sb/{name}/poll").json()["own"] is False
    assert c.get(f"/api/sb/{name}/state").json()["name"] == "Edited outside"
    # undo only while the file is as the last save left it
    assert c.post(f"/api/sb/{name}/undo").status_code == 400


def test_keyframe_identity_ignores_an_explicit_default_seed():
    from engine.storyboard.edit.images import keyframe_ident
    frames = [{"name": "room", "t": 0, "prompt": "p"}]
    a = {"keyframes": {"seed": 5, "frames": frames}}
    b = {"keyframes": {"seed": 5, "frames": [{"name": "room", "t": 0, "prompt": "p", "seed": 5}]}}
    c = {"keyframes": {"seed": 5, "frames": [{"name": "room", "t": 0, "prompt": "p", "seed": 6}]}}
    bk = {"w": 1}
    assert keyframe_ident(a, bk, "room") == keyframe_ident(b, bk, "room") != keyframe_ident(c, bk, "room")


# ---------------------------------------------------------------- notes: the inbox an agent works through

def test_notes_lifecycle_and_changes_attach_to_the_working_note(project):
    from engine.storyboard.edit import notes
    ws = Workspace(project)
    n1 = ws.add_note("a", "warmer light, and slower")
    g = ws.add_note("general", "tighten the pacing")
    with pytest.raises(Exception):
        ws.add_note("nope", "x")
    with pytest.raises(Exception):
        ws.add_note("a", "   ")
    ws.set_fields("a", {"seconds": 5})                    # nobody is working on anything yet: nothing is attached
    assert notes.get(project, n1["id"])["changes"] == []
    data = ws.notes_for_agent(claim=True)                 # the agent picks both up
    assert [n["status"] for n in data["notes"]] == ["working", "working"]
    one = next(n for n in data["notes"] if n["id"] == n1["id"])
    assert one["shot_state"]["fields"]["seconds"] == 5 and one["shot_state"]["images"][0]["slot"] == "still"
    assert [s["id"] for s in next(n for n in data["notes"] if n["id"] == g["id"])["storyboard"]] == ["a", "b", "c"]
    ws.set_fields("a", {"motion": "pans slowly"})         # edits to shot a attach to its note and to the general one
    ws.set_fields("b", {"seconds": 6})                    # an edit to b only to the general note
    assert notes.get(project, n1["id"])["changes"] == ["edited motion"]
    assert notes.get(project, g["id"])["changes"] == ["edited motion", "edited seconds"]
    done = notes.resolve(project, n1["id"], "slowed the move", ["kept the light"])
    assert done["status"] == "done" and done["reply"] == "slowed the move" and done["changes"] == ["edited motion", "kept the light"]
    assert ws.notes_for_agent(claim=False)["notes"] == []              # only the general one is left, and it is working
    assert len(ws.notes_for_agent(claim=False, include_working=True)["notes"]) == 1
    notes.reopen(project, n1["id"], "still too warm")
    again = notes.get(project, n1["id"])
    assert again["status"] == "open" and again["text"].endswith("+ still too warm")
    ws.delete_note(n1["id"])
    assert [n["id"] for n in notes.all_notes(project)] == [g["id"]]


def test_notes_http_and_the_page_state(project):
    from fastapi.testclient import TestClient
    from engine.storyboard.edit.api import make_app
    c = TestClient(make_app(project))
    n = project.name
    r = c.post(f"/api/sb/{n}/notes", json={"shot": "b", "text": "less grain"})
    assert r.status_code == 200 and r.json()["note"]["status"] == "open"
    assert c.post(f"/api/sb/{n}/notes", json={"shot": "zzz", "text": "x"}).status_code == 400
    st = c.get(f"/api/sb/{n}/state").json()
    assert [x["text"] for x in st["notes"]] == ["less grain"] and st["vrev"]
    v0 = c.get(f"/api/sb/{n}/poll").json()["vrev"]
    import time
    time.sleep(0.02)
    nid = r.json()["note"]["id"]
    assert c.post(f"/api/sb/{n}/notes/delete", json={"id": nid}).status_code == 200
    assert c.get(f"/api/sb/{n}/poll").json()["vrev"] != v0              # the page reloads when a note changes


# ---------------------------------------------------------------- playing the whole thing

def test_play_info_and_files(project):
    import json as _json
    import time
    from fastapi.testclient import TestClient
    from engine.storyboard.edit.api import make_app
    ws = Workspace(project)
    assert ws.play_info() == {"animatic": None, "standin": None, "dist": None, "rebuilding": False}
    sb = project.root / "storyboard"
    sb.mkdir(exist_ok=True)
    (sb / "animatic.mp4").write_bytes(b"\x00" * 4096)
    board = shots.build(project)
    (sb / "animatic.timeline.json").write_text(_json.dumps({
        "cut_at": time.time() + 1, "duration": 20.0, "shots": [{"id": "a", "t0": 0, "t1": 6}, {"id": "b", "t0": 5.6, "t1": 10}],
        "sigs": {s.id: s.sig() for s in board.shots}, "rev": board.rev}))
    a = ws.play_info()["animatic"]
    assert a["stale"] is False and [s["id"] for s in a["shots"]] == ["a", "b"] and a["duration"] == 20.0
    ws.set_fields("b", {"seconds": 7})                                   # a shot changes after the cut
    a = ws.play_info()["animatic"]
    assert a["stale"] and a["changed"] == ["b"] and "b" in a["reason"]
    # the files are served, with ranges (a video seeks), and so is the built page
    (project.dist).mkdir(exist_ok=True)
    (project.dist / "index.html").write_text("<html>built</html>")
    c = TestClient(make_app(project))
    r = c.get(f"/sb/{project.name}/files/animatic.mp4", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    assert "built" in c.get(f"/sb/{project.name}/dist/index.html").text
    assert c.get(f"/sb/{project.name}/dist/../site.yaml").status_code in (403, 404)
    assert c.get(f"/api/sb/{project.name}/play").json()["dist"]["url"] == "dist/index.html"


def test_storyboard_without_generation_renders_nothing(project, monkeypatch):
    """generate=False: images that are not cached become placeholder cards and no render is attempted."""
    from engine.plan import plan_build
    from engine.storyboard.cards import Maker
    from engine.backends import comfy

    def boom(*a, **k):
        raise AssertionError("a render was attempted")
    monkeypatch.setattr(comfy, "alive", boom)
    monkeypatch.setattr(comfy, "run", boom)
    site = project.load()
    mk = Maker(project, site, plan_build(project), "animatic", {}, None, False, lambda m: None, generate=False)
    cards = mk.cards()
    beat = next(c for c in cards if c.id == "c")
    assert [f.level for f in beat.frames] == ["placeholder", "final"]       # its own still is a card; the end image is a file
