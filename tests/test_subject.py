"""One subject kept across a story film (`subject:` on a film section): which beats start on the reference edited into
their scene, the editor's instruction, and that films without one are untouched. No ComfyUI."""
from __future__ import annotations

from engine.camera_beats import start_ref
from engine.spec import FilmScene, ImageInput, subject_instruction

KEYS = [{"t": 0, "box": [0, 0, 1, 1]}, {"t": 1, "box": [0.2, 0.2, 0.6, 0.6]}]


def sec(**kw) -> FilmScene:
    return FilmScene.model_validate({"id": "s", "beats": [
        {"id": "a", "prompt": "She waits on a rainy platform at night", "motion": "rain falls", "seconds": 3, "seed": 4},
        {"id": "b", "prompt": "p", "motion": "m", "seconds": 3, "image": "inputs/own.png"},
        {"id": "a2", "prompt": "p", "motion": "m", "seconds": 3, "camera": KEYS},
        {"id": "c", "prompt": "p", "motion": "m", "seconds": 3, "camera": {"keys": KEYS[1:], "continues": True}},
        {"id": "d", "prompt": "Close on her face in a cafe", "motion": "she smiles", "seconds": 3, "camera": "dolly-in"},
    ], **kw})


SUBJECT = {"image": "inputs/hero.png", "name": "the woman in the red coat"}


def test_without_a_subject_beats_start_as_before():
    s = sec()
    assert s.subject is None and "subject" not in s.model_dump(mode="json", exclude_defaults=True)
    ref = start_ref(s, 0, (1920, 1088))
    assert isinstance(ref, ImageInput) and ref.generate == s.beats[0].prompt and ref.seed == 4


def test_a_subject_is_edited_into_every_beat_that_has_no_image_of_its_own():
    s = sec(subject=SUBJECT)
    a = start_ref(s, 0, (1920, 1088))
    assert a.generate is None and a.edit is not None and a.edit.source == "inputs/hero.png" and a.edit.seed == 4
    assert "rainy platform at night" in a.edit.instruction and "the woman in the red coat" in a.edit.instruction
    assert start_ref(s, 1, (1920, 1088)) == "inputs/own.png"                  # its own image wins
    assert start_ref(s, 3, (1920, 1088)).beat_frame is not None               # a continued camera starts on the last frame
    assert start_ref(s, 4, (1920, 1088)).edit is not None                     # named moves too


def test_the_instruction_keeps_what_the_spec_says():
    from engine.spec import Subject
    text = subject_instruction(Subject(image="x.png", name="the cup", keep="glaze and shape"), "On a beach at dawn.")
    assert text.startswith("Show the cup from this image in a new photograph: On a beach at dawn.")
    assert "same glaze and shape" in text
