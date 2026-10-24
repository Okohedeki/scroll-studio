"""The docs site: the generated references cover the whole engine, the yaml examples in the docs are valid specs, the
nav lists every page, and the link rewriting and the workflow follow their rules. None of it needs MkDocs installed
(the full strict build runs in the docs workflow); everything here is plain Python.

The yaml rule, in docs/contributing/building-the-docs.md: every ```yaml block in docs/**/*.md and README.md is checked
against engine/spec.py, or opts out with a `# docs: no-validate` comment.
"""
from __future__ import annotations

import importlib.util
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel, TypeAdapter, ValidationError

from engine import docsgen, spec

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OPT_OUT = "docs: no-validate"
PLACEHOLDER = "..."


def load_hooks():
    s = importlib.util.spec_from_file_location("mkdocs_hooks", ROOT / "mkdocs_hooks.py")
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- the generated references

@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> dict[str, str]:
    out = tmp_path_factory.mktemp("reference")
    docsgen.generate(out)
    return {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8") for p in out.rglob("*.md")}


def test_the_generator_writes_every_page(generated):
    assert set(generated) == {"cli.md", "mcp.md", "spec/index.md", "spec/site.md", "spec/scenes.md", "spec/blocks.md",
                              "spec/nested.md"}
    assert all(text.startswith("<!-- Generated") for text in generated.values())


def test_every_spec_model_and_field_has_a_section_and_an_anchor(generated):
    text = "\n".join(t for name, t in generated.items() if name.startswith("spec/"))
    ids = set(re.findall(r'id="([^"]+)"', text)) | set(re.findall(r"\{ #([^ ]+) \}", text))
    models = {n: c for n, c in vars(spec).items()
              if isinstance(c, type) and issubclass(c, BaseModel) and c.__module__ == spec.__name__}
    assert len(models) > 100
    missing = []
    for name, cls in models.items():
        if name == "Model":
            continue
        if name.lower() not in ids:
            missing.append(name)
            continue
        for field, info in ((f.alias or k, f) for k, f in cls.model_fields.items()):      # the YAML key is the alias
            owners = (name, "SceneBase", "BlockBase")      # a scene lists its own fields; the shared ones are on its base
            if not any(f"{o.lower()}-{field}" in ids for o in owners):
                missing.append(f"{name}.{field}")
    assert not missing, f"not in the spec reference: {missing[:20]}"


def test_every_section_type_is_in_the_spec_reference_index(generated):
    index = generated["spec/index.md"]
    for t in spec.SCENE_TYPES:
        assert f"| `{t}` |" in index
    for page in ("site", "scenes", "blocks", "nested"):
        assert f"({page}.md)" in index


def test_field_rows_show_type_default_allowed_values_and_limits(generated):
    scenes = generated["spec/scenes.md"]
    row = next(line for line in scenes.splitlines() if 'id="filmscene-beat_fade"' in line)
    assert "number" in row and "`0.4`" in row and "Constraints: 0 to 2" in row and "crossfade" in row
    row = next(line for line in scenes.splitlines() if 'id="scenebase-layout"' in line)
    assert '`"overlay"`' in row and "Allowed values:" in row and '`"cards"`' in row
    row = next(line for line in generated["spec/site.md"].splitlines() if 'id="site-name"' in line)
    assert "**required**" in row


def test_every_cli_command_is_documented(generated):
    import typer.main

    from engine.cli import app
    group = typer.main.get_command(app)
    assert len(group.commands) == len(app.registered_commands) + len(app.registered_groups) and len(group.commands) > 20
    for name, cmd in group.commands.items():
        for leaf in ([f"{name} {n}" for n in cmd.commands] if hasattr(cmd, "commands") else [name]):
            assert f"## `studio {leaf}`" in generated["cli.md"], leaf
    assert "studio build [OPTIONS] NAME" in generated["cli.md"] and "`--force`" in generated["cli.md"]


def test_every_mcp_tool_is_documented(generated):
    import asyncio

    from engine.mcp_server import mcp
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) > 30
    source = (ROOT / "engine" / "mcp_server.py").read_text(encoding="utf-8")
    assert len(tools) == source.count("@mcp.tool()"), "a tool is registered twice or a decorator was lost"
    for t in tools:
        assert f"## `{t.name}`" in generated["mcp.md"], t.name
        for arg in t.input_schema.get("properties", {}):
            assert f"| `{arg}` |" in generated["mcp.md"], f"{t.name}({arg})"


def test_generated_pages_hold_no_machine_paths(generated):
    # the pages are published, and a default read from studio.toml or the home folder must not end up on them
    from test_no_local_paths import leaks
    for name, text in generated.items():
        assert not leaks(text), f"{name}: {leaks(text)}"


def test_the_help_text_is_escaped_for_markdown():
    assert docsgen.prose("a <b> | c * {#x}") == "a &lt;b> \\| c \\* &#123;#x}"
    assert docsgen.prose("keep `a | <b>` as code") == "keep `a \\| <b>` as code"
    assert docsgen.first_sentence("Join recordings (e.g. two). Then more.") == "Join recordings (e.g. two)."


# ---------------------------------------------------------------- yaml snippets in the docs

FENCE = re.compile(r"^(?P<indent>[ \t]*)```(?:yaml|yml)[ \t]*\n(?P<body>.*?)^(?P=indent)```[ \t]*$", re.S | re.M)
SITE_KEYS = set(spec.Site.model_fields)
MODELS = [c for c in vars(spec).values()
          if isinstance(c, type) and issubclass(c, BaseModel) and c.__module__ == spec.__name__ and c is not spec.Model]


def snippets() -> list[tuple[str, str]]:
    found = []
    files = sorted(DOCS.rglob("*.md")) + [ROOT / "README.md"]
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in FENCE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            found.append((f"{f.relative_to(ROOT).as_posix()}:{line}", textwrap.dedent(m.group("body"))))
    return found


def _real(errors: list[Any], top_level_only_missing: bool = False) -> list[Any]:
    """Errors that are about something written in the snippet. `...` stands for more of the same, so errors caused
    by it do not count; a fragment may leave out the fields its model requires."""
    out = []
    for e in errors:
        if e["input"] == PLACEHOLDER or (isinstance(e["input"], str) and e["input"].strip() == PLACEHOLDER):
            continue
        if top_level_only_missing and e["type"] == "missing" and len(e["loc"]) == 1:
            continue
        out.append(e)
    return out


def check_snippet(text: str) -> list[str]:
    """Problems with one yaml snippet, [] when it is fine or opts out."""
    if OPT_OUT in text:
        return []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [f"not valid YAML: {str(e).splitlines()[0]} (or start the block with `# {OPT_OUT}`)"]
    if isinstance(data, dict) and data and set(data) <= SITE_KEYS:
        site = {"name": "snippet", "sections": []} | data              # a part of a site: name and sections may be left out
        return _messages(_real(_errors(lambda: spec.Site.model_validate(site))))
    if isinstance(data, list) and data and all(isinstance(i, dict) and "type" in i or i == PLACEHOLDER for i in data):
        adapter = TypeAdapter(spec.Section)
        return [m for i in data if i != PLACEHOLDER for m in _messages(_real(_errors(lambda i=i: adapter.validate_python(i))))]
    if isinstance(data, dict) and data:
        return _fragment([data])
    if isinstance(data, list) and data and all(isinstance(i, dict) or i == PLACEHOLDER for i in data):
        return _fragment([i for i in data if i != PLACEHOLDER])              # a list of beats, steps, places ...
    return [f"not a site, a list of sections or a fragment of a model (start the block with `# {OPT_OUT}`)"]


def _fragment(items: list[dict]) -> list[str]:
    """Mappings that are part of a model: valid when some model with all of their fields accepts every one."""
    keys = set().union(*items)
    candidates = [c for c in MODELS if keys <= set(c.model_fields)]
    if not candidates:
        return [f"no model in engine/spec.py has all of the fields {sorted(keys)} (a typo, or start the block with "
                f"`# {OPT_OUT}`)"]
    tries = [[e for item in items for e in _real(_errors(lambda c=c, item=item: c.model_validate(item)),
                                                 top_level_only_missing=True)] for c in candidates]
    return [] if any(not t for t in tries) else _messages(min(tries, key=len))


def _errors(call) -> list[Any]:
    try:
        call()
    except ValidationError as e:
        return e.errors()
    return []


def _messages(errors: list[Any]) -> list[str]:
    return [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in errors]


def test_snippets_are_found():
    found = snippets()
    assert len(found) >= 30 and any(s.startswith("docs/scenes.md") for s, _ in found)


@pytest.mark.parametrize("where, text", snippets(), ids=lambda v: v if isinstance(v, str) and ":" in v and "\n" not in v else "")
def test_every_yaml_snippet_in_the_docs_is_a_valid_spec(where, text):
    problems = check_snippet(text)
    assert not problems, f"{where}\n  " + "\n  ".join(problems[:8])


def test_the_snippet_rule_accepts_what_it_should():
    assert not check_snippet("name: A\nsections:\n  - type: hero\n    title: Hi\n")
    assert not check_snippet("theme: { preset: dusk }\n")                                  # a part of a site
    assert not check_snippet("- type: cta\n  title: Go\n  button: { label: Book, href: '#' }\n")    # sections
    assert not check_snippet("beats:\n  - id: door\n    prompt: a door\n    motion: it opens\n")   # a fragment of a scene
    assert not check_snippet("- id: door\n  seconds: 5\n  freeze: { image: a.png }\n")             # a list of beats
    assert not check_snippet("steps: [...]\n")                                              # placeholders stand for more
    assert not check_snippet("- id: a\n  type: film\n  beats: [...]\n")
    assert not check_snippet("# docs: no-validate (planned, not built yet)\nat: { x: 0.1 }\n")


def test_the_snippet_rule_rejects_what_it_should():
    assert check_snippet("theme: { preset: dusk, bogus: 1 }\n")                             # an unknown key
    assert check_snippet("name: A\nsections:\n  - type: nonsense\n")                         # not a section type
    assert check_snippet("- type: film\n")                                                   # a scene needs an id
    assert check_snippet("beats:\n  - id: door\n    prompt: a\n    motion: b\n    secs: 5\n")      # a typo in a fragment
    assert check_snippet("- id: door\n  seconds: five\n  freeze: { image: a.png }\n")             # a wrong value
    assert check_snippet("kicker: [unterminated\n")                                          # not YAML
    assert check_snippet("nothing_here_has_this_field: 1\n")
    assert check_snippet("- just\n- words\n")


# ---------------------------------------------------------------- the nav and the root pages

def nav_files(nav: Any) -> list[str]:
    out = []
    for item in nav:
        for value in item.values() if isinstance(item, dict) else [item]:
            out += nav_files(value) if isinstance(value, list) else [value]
    return out


def test_the_nav_lists_real_pages_and_every_page_is_in_it():
    hooks = load_hooks()
    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    listed = nav_files(config["nav"])
    generated = {"reference/spec/", "reference/cli.md", "reference/mcp.md"}
    optional = {uri for src, uri in hooks.ROOT_PAGES.items() if not (ROOT / src).is_file()}    # added by later pull requests
    for uri in listed:
        if uri in optional or any(uri.startswith(g) for g in generated):
            continue
        in_docs, from_root = (DOCS / uri).is_file(), uri in hooks.ROOT_PAGES.values()
        assert in_docs or from_root, f"nav lists {uri}, which is neither in docs/ nor a root file"
    for page in sorted(DOCS.rglob("*.md")):
        uri = page.relative_to(DOCS).as_posix()
        if any(uri.startswith(g) for g in generated):
            continue
        assert uri in listed, f"docs/{uri} is not in the nav of mkdocs.yml"
    for src, uri in hooks.ROOT_PAGES.items():
        if (ROOT / src).is_file():
            assert uri in listed, f"{src} exists but its page {uri} is not in the nav"


def test_the_generated_references_are_not_committed():
    import subprocess
    if not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout")
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)      # noqa: E731
    tracked = set(git("ls-files", "docs/reference").stdout.split())
    assert tracked <= {"docs/reference/index.md"}, tracked
    for path in ("docs/reference/spec/index.md", "docs/reference/cli.md", "docs/reference/mcp.md"):
        assert git("check-ignore", "-q", path).returncode == 0, f"{path} must be git-ignored"


# ---------------------------------------------------------------- link rewriting

PAGES = {"docs/guide.md": "guide.md", "docs/styles/index.md": "styles/index.md", "docs/media/logo.svg": "media/logo.svg",
         "CLA.md": "contributing/cla.md", "CONTRIBUTING.md": "contributing/guide.md"}
EXISTING = {"README.md": "file", "LICENSE": "file", "examples": "dir", "examples/fenmoor/site.yaml": "file",
            "engine/styles/README.md": "file", "docs/styles": "dir", ".github/workflows/tests.yml": "file"}
URL = "https://github.com/Okohedeki/scroll-studio"


def link(target: str, origin: str, dest: str) -> str:
    return load_hooks().map_target(target, origin, dest, PAGES, EXISTING.get, URL, "main")


def test_links_to_pages_become_site_links():
    assert link("guide.md#with-claude", "docs/scenes.md", "scenes.md") == "guide.md#with-claude"
    assert link("../CLA.md", "docs/licence.md", "licence.md") == "contributing/cla.md"
    assert link("CLA.md", "CONTRIBUTING.md", "contributing/guide.md") == "cla.md"
    assert link("docs/guide.md", "CONTRIBUTING.md", "contributing/guide.md") == "../guide.md"
    assert link("docs/styles/", "CONTRIBUTING.md", "contributing/guide.md") == "../styles/index.md"
    assert link("media/logo.svg", "docs/guide.md", "guide.md") == "media/logo.svg"


def test_links_to_other_files_become_github_links():
    assert link("../README.md", "docs/guide.md", "guide.md") == f"{URL}/blob/main/README.md"
    assert link("LICENSE", "CONTRIBUTING.md", "contributing/guide.md") == f"{URL}/blob/main/LICENSE"
    assert link("../examples/fenmoor/site.yaml", "docs/guide.md", "guide.md") == f"{URL}/blob/main/examples/fenmoor/site.yaml"
    assert link("../examples/", "docs/examples.md", "examples.md") == f"{URL}/tree/main/examples"
    assert link("engine/styles/README.md#x", "CONTRIBUTING.md", "contributing/guide.md") == f"{URL}/blob/main/engine/styles/README.md#x"


def test_other_links_are_left_alone_so_the_strict_build_reports_them():
    for t in ("https://example.com/a.md", "mailto:a@b.c", "#anchor", "/abs/path", "../outside.md", "../../x"):
        assert link(t, "docs/guide.md", "guide.md") == t
    assert link("../missing-file.md", "docs/guide.md", "guide.md") == "../missing-file.md"     # exists nowhere in the repo
    assert link("../GOVERNANCE.md", "docs/guide.md", "guide.md") == "../GOVERNANCE.md"          # not added yet


def test_code_is_never_rewritten():
    hooks = load_hooks()
    md = "See [`a`](../README.md) and `[x](../README.md)`.\n```md\n[y](../README.md)\n```\n<a href=\"../README.md\">r</a>\n"
    out = hooks.rewrite_links(md, "docs/guide.md", "guide.md", PAGES, EXISTING.get, URL, "main")
    assert out.count(f"{URL}/blob/main/README.md") == 2
    assert "`[x](../README.md)`" in out and "```md\n[y](../README.md)\n```" in out


def test_the_row_of_github_links_is_dropped_from_docs_pages():
    hooks = load_hooks()
    row = "[← README](../README.md) · [Why](why.md) · [Licence](licence.md)\n\n"
    assert hooks.GITHUB_NAV_ROW.sub("", "# T\n\n" + row + "text", count=1).startswith("# T")      # only at the very start
    assert hooks.GITHUB_NAV_ROW.sub("", row + "text") == "text"
    other = "[← README](../README.md) · [Other](other.md)\n\ntext"
    assert hooks.GITHUB_NAV_ROW.sub("", other) == other      # a row without the Why link is not the navigation row


# ---------------------------------------------------------------- the workflow

WORKFLOW = ROOT / ".github" / "workflows" / "docs.yml"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_docs_workflow_follows_the_repo_rules():
    wf = workflow()
    triggers = wf.get("on", wf.get(True))
    assert {"pull_request", "push", "schedule", "workflow_dispatch"} <= set(triggers)
    assert triggers["push"]["branches"] == ["main"]
    assert wf["permissions"] in ({}, {"contents": "read"})
    assert wf["concurrency"]["group"]
    for name, job in wf["jobs"].items():
        assert job["timeout-minutes"] <= 30, name
        steps = job["steps"]
        assert steps[0]["uses"].startswith("step-security/harden-runner@"), name
        assert steps[0]["with"]["egress-policy"] == "audit"
        for s in steps:
            if "uses" in s:
                assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", s["uses"]), f"{name}: pin to a full commit SHA: {s['uses']}"
            if s.get("uses", "").startswith("actions/checkout@"):
                assert s["with"]["persist-credentials"] is False, name
    grants = {n: j.get("permissions", {}) for n, j in wf["jobs"].items()}
    assert [n for n, g in grants.items() if g.get("pages") == "write" or g.get("id-token") == "write"] == ["deploy"]
    assert wf["jobs"]["deploy"]["environment"]["name"] == "github-pages"


def test_the_docs_extra_pins_exact_versions():
    extra = re.search(r"^docs = \[(.*?)\]", (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    pins = re.findall(r'"([^"]+)"', extra)
    assert {p.split("==")[0] for p in pins} >= {"mkdocs", "mkdocs-material", "pymdown-extensions"}
    assert all("==" in p for p in pins), pins
