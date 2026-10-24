"""Deprecation warnings (docs/compatibility.md): a deprecated field or value keeps validating, and every use of it is
reported with where it is, what replaces it and when it goes. Nothing is deprecated yet, so the mechanism is proved on
a small model defined here, and wired in through a field of the real Site marked for the test only."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Literal, Optional

import pytest
import yaml
from pydantic import Field

from engine import docsgen
from engine.spec import Deprecation, Model, Site, deprecated, deprecated_all, deprecation_tail, deprecations

ROOT = Path(__file__).resolve().parent.parent


class Inner(Model):
    old: Optional[str] = Field(None, json_schema_extra=deprecated("2.0.0", "`new`"))
    new: Optional[str] = None


class Item(Model):
    id: str
    kind: Literal["a", "b", "c"] = Field("a", json_schema_extra=deprecated_all(
        deprecated("2.0.0", "`kind: a`", value="b"), deprecated("3.0.0", note="Pick another.", value="c")))
    inner: Optional[Inner] = None
    by_name: dict[str, Inner] = Field(default_factory=dict)
    plain: int = Field(0, json_schema_extra=lambda schema: None)      # a callable is not a mark


class Doc(Model):
    items: list[Item] = Field(default_factory=list)
    gone: Optional[str] = Field(None, json_schema_extra=deprecated("2.0.0"))
    pair: tuple[Inner, Inner] = (Inner(), Inner())


def texts(doc) -> list[str]:
    return [d.text for d in deprecations(doc)]


# ---------------------------------------------------------------- collecting

def test_a_deprecated_field_still_validates_and_warns_once_per_use():
    doc = Doc.model_validate({"items": [{"id": "x", "inner": {"old": "1"}}, {"id": "y", "inner": {"old": "2"}}]})
    assert doc.items[0].inner.old == "1"
    uses = deprecations(doc)
    assert [(d.path, d.section) for d in uses] == [("items[0].inner.old", "x"), ("items[1].inner.old", "y")]
    assert uses[0].removed_in == "2.0.0" and uses[0].replacement == "`new`"
    assert uses[0].text == "items[0].inner.old (section 'x'): deprecated and will be removed in 2.0.0. Use `new` instead."


def test_a_field_left_unset_or_at_its_default_is_not_a_use():
    assert deprecations(Doc()) == []
    assert deprecations(Doc.model_validate({"items": [{"id": "x", "inner": {"new": "fine"}}]})) == []


def test_a_field_without_a_replacement_says_only_when_it_goes():
    [use] = deprecations(Doc(gone="x"))
    assert use.section is None and use.replacement is None
    assert use.text == "gone: deprecated and will be removed in 2.0.0."


def test_only_the_deprecated_value_of_a_field_warns():
    ok = Doc.model_validate({"items": [{"id": "x", "kind": "a"}]})
    assert deprecations(ok) == []
    bad = Doc.model_validate({"items": [{"id": "x", "kind": "b"}, {"id": "y", "kind": "c"}]})
    assert texts(bad) == [
        "items[0].kind (section 'x'): the value 'b' is deprecated and will be removed in 2.0.0. Use `kind: a` instead.",
        "items[1].kind (section 'y'): the value 'c' is deprecated and will be removed in 3.0.0. Pick another."]


def test_uses_inside_dicts_and_tuples_are_found_in_field_order():
    doc = Doc.model_validate({"items": [{"id": "x", "by_name": {"k": {"old": "1"}}}], "pair": [{"old": "1"}, {}]})
    assert [d.path for d in deprecations(doc)] == ["items[0].by_name.k.old", "pair[0].old"]


def test_a_value_of_none_can_be_the_deprecated_one():
    class M(Model):
        x: Optional[str] = Field("a", json_schema_extra=deprecated("2.0.0", value=None))
    assert deprecations(M(x="a")) == [] and len(deprecations(M(x=None))) == 1
    assert "the value None is deprecated" in deprecations(M(x=None))[0].text


def test_marks_describe_themselves_in_the_json_schema():
    props = Doc.model_json_schema()["properties"]
    assert props["gone"]["deprecated"] is True
    assert props["gone"]["x-deprecated"] == [{"removed_in": "2.0.0"}]
    kind = Item.model_json_schema()["properties"]["kind"]
    assert "deprecated" not in kind       # the field is fine, only two of its values are not
    assert [r["value"] for r in kind["x-deprecated"]] == ["b", "c"]
    assert deprecated_all(deprecated("2.0.0"), deprecated("2.0.0", value="b"))["deprecated"] is True


def test_the_sentence_and_the_json_form_carry_the_parts():
    rule = deprecated("2.0.0", "`y`", note="See the guide.")["x-deprecated"][0]
    assert deprecation_tail(rule) == "will be removed in 2.0.0. Use `y` instead. See the guide."
    d = Deprecation("a.b", "s", "2.0.0", "`y`")
    assert str(d) == d.text and d.as_dict() == {"path": "a.b", "section": "s", "removed_in": "2.0.0",
                                                "replacement": "`y`", "text": d.text}


# ---------------------------------------------------------------- the reference

def test_the_generated_reference_marks_deprecated_fields_and_values():
    docs = docsgen.SpecDocs()
    gone = docs.field_row("Site", "gone", Doc.model_json_schema()["properties"]["gone"], False, "site")
    assert "**Deprecated:** will be removed in 2.0.0." in gone
    kind = docs.field_row("Site", "kind", Item.model_json_schema()["properties"]["kind"], False, "site")
    assert "**Deprecated value** `\"b\"`: will be removed in 2.0.0. Use `kind: a` instead." in kind
    assert "**Deprecated value** `\"c\"`" in kind


# ---------------------------------------------------------------- the real spec

def test_nothing_is_deprecated_today():
    assert not any("x-deprecated" in json.dumps(p) for p in Site.model_json_schema()["$defs"].values())
    assert "x-deprecated" not in json.dumps(Site.model_json_schema())


EXAMPLES = sorted((ROOT / "examples").glob("*/site.yaml")) + sorted((ROOT / "tests" / "fixtures" / "old_specs").glob("v*/*.yaml"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: f"{p.parent.name}/{p.stem}" if p.name != "site.yaml" else p.parent.name)
def test_examples_and_the_old_spec_corpus_use_nothing_deprecated(path):
    assert deprecations(yaml.safe_load(path.read_text(encoding="utf-8"))) == []


@pytest.fixture
def old_description(monkeypatch):
    """Site.description, marked deprecated for the length of a test."""
    monkeypatch.setattr(Site.model_fields["description"], "json_schema_extra",
                        deprecated("2.0.0", "`name`", note="Say it in the first section."))
    return "Site.description"


SPEC = "name: Demo\ndescription: old words\nsections:\n  - {type: intro, id: hello, title: Hi}\n"


def test_a_raw_spec_is_validated_then_checked(old_description):
    assert [d.path for d in deprecations(yaml.safe_load(SPEC))] == ["description"]
    assert deprecations({"name": "Demo", "sections": []}) == []
    with pytest.raises(Exception):
        deprecations({"sections": []})        # invalid: raises as validation does anywhere else


def project_in(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    (root / "demo" / "inputs").mkdir(parents=True)
    (root / "demo" / "site.yaml").write_text(SPEC, encoding="utf-8")
    return root


def test_studio_build_prints_each_use_as_a_warning(old_description, tmp_path):
    from typer.testing import CliRunner

    from engine.cli import app
    root = project_in(tmp_path)
    res = CliRunner().invoke(app, ["build", str(root / "demo"), "--plan"])
    assert res.exit_code == 0, res.output
    assert ("warning: description: deprecated and will be removed in 2.0.0. Use `name` instead. "
            "Say it in the first section.") in res.output
    (root / "demo" / "site.yaml").write_text(SPEC.replace("description: old words\n", ""), encoding="utf-8")
    res = CliRunner().invoke(app, ["build", str(root / "demo"), "--plan"])
    assert res.exit_code == 0 and "warning" not in res.output


def test_the_mcp_tool_writes_the_spec_and_names_each_use(old_description, tmp_path, monkeypatch):
    from engine import mcp_server
    monkeypatch.setattr(mcp_server, "PROJECTS", project_in(tmp_path))
    out = mcp_server.set_spec("demo", SPEC)
    assert out["ok"] and [(d["path"], d["removed_in"], d["replacement"]) for d in out["deprecations"]] == [
        ("description", "2.0.0", "`name`")]
    assert "deprecated and will be removed in 2.0.0" in out["deprecations"][0]["text"]
    assert mcp_server.set_spec("demo", SPEC.replace("description: old words\n", "")) == {"ok": True, "deprecations": []}
    assert mcp_server.set_spec("demo", "name: [")["ok"] is False


def test_the_studio_server_save_names_each_use(old_description, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from engine.server import app as server
    monkeypatch.setattr(server, "PROJECTS", project_in(tmp_path))
    c = TestClient(server.app, base_url="http://127.0.0.1:8970")      # the server answers only its own host (local_only.py)
    r = c.put("/api/projects/demo/spec", json={"yaml": textwrap.dedent(SPEC)})
    assert r.status_code == 200 and [d["path"] for d in r.json()["deprecations"]] == ["description"]
    r = c.put("/api/projects/demo/spec", json={"data": {"name": "Demo", "sections": []}})
    assert r.status_code == 200 and r.json()["deprecations"] == []
