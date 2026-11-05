"""Generating a site from a brief (engine/sitegen): the checks every model answer goes through, and one whole run with
the text model stood in."""
from __future__ import annotations

import json

import pytest
import yaml

from engine import sitegen
from engine.sitegen import bank as bank_mod, catalog, write


def test_parse_json_finds_the_object_inside_prose():
    assert write.parse_json('Sure. ```json\n{"a": {"b": 1}}\n``` done') == {"a": {"b": 1}}
    with pytest.raises(write.WriteError):
        write.parse_json("no object here")


def test_craft_flags_style_words_writing_files_and_stock_phrases():
    sec = {"type": "hero", "id": "x", "title": "Ship it, seamless!",
           "image": {"generate": "a cinematic photo of a harbour at dusk"},
           "items": [{"image": {"generate": "a shop sign that says 'Open Late'"}}, {"image": {"file": "inputs/a.png"}}]}
    found = " | ".join(write.craft_problems(sec, None))
    assert "sets its own style" in found and "cinematic" in found
    assert "asks for writing" in found
    assert "names files" in found
    assert "seamless" in found and "exclamation" in found


def test_craft_passes_a_plain_description_and_flags_copy_lifted_from_the_pattern():
    pattern = {"type": "intro", "id": "p", "body": "every order is packed by hand in a small room above the shop"}
    clean = {"type": "intro", "id": "x", "body": "Jobs wait in lanes and run in order.",
             "image": {"generate": "a water wheel turning beside a stone channel, morning light from the left"}}
    assert write.craft_problems(clean, pattern) == []
    lifted = dict(clean, body="Yes: every order is packed by hand in a small room above the shop.")
    assert any("repeats the pattern" in p for p in write.craft_problems(lifted, pattern))


def test_the_engine_tidies_section_ids():
    secs = [{"id": "film-0", "type": "film", "headline": "The <em>wheel</em> turns"}, {"id": "Features-Lanes", "type": "features"},
            {"id": "lanes", "type": "stats"}, {"id": "cta", "type": "cta"}]
    write.tidy_ids(secs)
    assert [s["id"] for s in secs] == ["the-wheel-turns", "lanes", "lanes-2", "cta"]


def test_a_page_that_opens_on_a_block_opens_on_its_first_scene():
    secs = [{"id": "a", "type": "hero"}, {"id": "b", "type": "features"}, {"id": "c", "type": "film"}, {"id": "d", "type": "cta"}]
    write.open_on_a_scene(secs, {"film", "parallax"})
    assert [s["id"] for s in secs] == ["c", "a", "b", "d"]


def test_interactive_kinds_go_to_sections_that_can_show_them():
    offer = {"3d": ["scene3d", "diorama"], "pointer": ["parallax", "film"]}
    secs = [{"id": "a", "type": "film", "interactive": "3d"}, {"id": "b", "type": "diorama"}, {"id": "c", "type": "cta"}]
    write.assign_interactive(secs, offer)
    assert [s["interactive"] for s in secs] == ["pointer", "3d", None]


def test_repair_moves_a_stray_prompt_into_the_image():
    fixed = write.repair({"items": [{"title": "Lanes", "generate": "a channel splitting in two", "seed": 4}]})
    assert fixed["items"][0] == {"title": "Lanes", "image": {"generate": "a channel splitting in two", "seed": 4}}


def test_the_bank_holds_file_free_patterns_from_the_examples():
    bank = bank_mod.load()
    assert bank, "the examples should give at least one pattern"
    for kind, patterns in bank.items():
        assert all(not bank_mod.files_in(p) for p in patterns), kind
    entries = catalog.entries(bank)
    assert any(e["type"] == "cta" for e in entries)
    assert not any(e["type"] in catalog.NEEDS_PRODUCT for e in entries)


class _Backend:
    name, local = "stand-in", False

    def model(self, kind):
        return "stand-in-model"


def test_a_whole_run_writes_a_valid_project(tmp_path, monkeypatch):
    bank = bank_mod.load()
    scene = next(k for k in ("type", "scene3d", "diorama", "code") if k in bank)
    block = next(k for k in ("features", "intro", "stats") if k in bank)
    plan = {"name": "Testbrand", "description": "A test brand.", "audience": "testers", "promise": "it works",
            "voice": "plain", "image": "a mill race feeding a wheel at the speed it turns", "sections": [{"id": "opening", "type": scene, "purpose": "open", "headline": "Hello"},
                                           {"id": "what-it-does", "type": block, "purpose": "facts", "headline": "Facts"},
                                           {"id": "ask", "type": "cta", "purpose": "ask", "headline": "Try it"}]}
    asked = []

    def fake_ask(prompt, seed, policy, build, log, **kw):
        asked.append(prompt)
        if "First find the story" in prompt:
            return json.dumps(plan)
        kind = prompt.split('"type": "', 1)[1].split('"', 1)[0]
        return json.dumps(bank_mod.pattern(kind, bank))       # valid by construction; its copy is reused, so the last
                                                              # try keeps it with notes, as a real weak answer would be
    monkeypatch.setattr(write, "_ask", fake_ask)
    monkeypatch.setattr(sitegen, "text_backend", lambda policy=None: _Backend())
    record = sitegen.generate(tmp_path / "testbrand", "A brand for testing.", want=(), count=3, looks=False,
                              log=lambda m: None)
    data = yaml.safe_load((tmp_path / "testbrand" / "project.yaml").read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["outputs"]["site"]["sections"]]
    assert ids[0] == "opening" and ids[-1] == "ask"
    assert data["brief"] == "A brand for testing." and data["name"] == "Testbrand"
    assert record["model"] == "stand-in-model"
    saved = json.loads((tmp_path / "testbrand" / "generate.json").read_text(encoding="utf-8"))
    assert saved["outline"]["sections"][0]["id"] == "opening"


def test_patterns_reach_the_model_without_their_words():
    pattern = {"type": "code", "id": "wire", "length": 9, "surface": "dark",
               "files": [{"path": "app/jobs.py", "kind": "edit", "code": "a\nb\nc\n"}],
               "steps": [{"title": "Five lines <em>to a durable job.</em>", "state": {"file": "app/jobs.py"},
                          "enter": "type-on", "image": {"generate": "a mill wheel at dawn"}}]}
    shape = write.skeleton(pattern)
    text = json.dumps(shape)
    for leaked in ("app/jobs.py", "durable", "mill wheel"):
        assert leaked not in text
    assert shape["length"] == 9 and shape["surface"] == "dark" and shape["steps"][0]["enter"] == "type-on"
    assert shape["files"][0]["kind"] == "edit"


def test_film_beats_chain_into_one_take():
    film = {"type": "film", "id": "f", "beats": [
        {"id": "a", "prompt": "x", "image": {"generate": "x"}},
        {"id": "b", "prompt": "y", "image": {"generate": "y"}},
        {"id": "c", "prompt": "z", "image": {"beat_frame": {"beat": "a", "at": "first"}}}]}
    beats = write.chain_film(film)["beats"]
    assert beats[0]["image"] == {"generate": "x"}
    assert beats[1]["image"] == {"beat_frame": {"beat": "a", "at": "last"}}
    assert beats[2]["image"] == {"beat_frame": {"beat": "a", "at": "first"}}


def test_a_terminal_task_is_not_mistaken_for_a_picture_prompt():
    shape = write.skeleton({"terminal": {"prompt": "make it durable"}, "image": {"prompt": "a wheel"}})
    assert "developer" in shape["terminal"]["prompt"] and "picture" in shape["image"]["prompt"]


def test_figures_the_brief_never_gave_are_caught():
    brief = "A queue that retries every job 5 times."
    sec = {"type": "stats", "id": "s", "items": [{"value": "99.9%", "label": "uptime"}, {"value": "5", "label": "retries"}],
           "title": "Since 2024"}
    assert write.invented_figures(sec, brief) == ["2024", "99.9"]
    assert write.invented_figures({"type": "code", "id": "c", "title": "Runs 1,204 jobs"}, brief) == []


def test_a_chained_film_drops_generated_end_frames():
    film = {"type": "film", "id": "f", "beats": [{"id": "a", "end_image": {"generate": "x"}},
                                                 {"id": "b", "end_image": {"beat_frame": {"beat": "a"}}}]}
    beats = write.chain_film(film)["beats"]
    assert "end_image" not in beats[0] and beats[1]["end_image"] == {"beat_frame": {"beat": "a"}}


def test_a_backdrop_look_loses_fit_on_a_page_of_places():
    from engine.directions import vocab, writer
    from engine.directions.brief import Brief
    studio = next(s for s in vocab.SCHOOLS if s.objects_only)
    base = Brief("X", "", domains={"tech": 1.0}, moods={"calm": 1.0})
    places = Brief("X", "", domains={"tech": 1.0}, moods={"calm": 1.0}, places=True)
    plain_fit, _ = writer.fit_of(studio, base, None, 1)
    place_fit, why = writer.fit_of(studio, places, None, 1)
    assert place_fit == pytest.approx(plain_fit / 2) and any("backdrop" in w for w in why)
