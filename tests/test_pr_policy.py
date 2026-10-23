"""The pull request policy (.github/scripts/pr_policy.js): titles, linked issues, fragments, tiers and labels.

The policy is JavaScript because it runs in actions/github-script; these tests call its pure functions through node.
They also keep the policy, the labels file and the issue forms in step."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / ".github" / "scripts" / "pr_policy.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def js(expr: str):
    """Evaluate an expression with the policy module bound to `p` and return it as JSON."""
    code = f"const p = require({json.dumps(str(POLICY))}); process.stdout.write(JSON.stringify({expr}));"
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def labels_file() -> set[str]:
    return {l["name"] for l in yaml.safe_load((ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))}


@pytest.mark.parametrize("title", [
    "fix(runtime): end reveals on transform none",
    "feat(spec)!: one layout model for every scene",
    "docs: governance and rules per area",
    "chore(deps): bump vite from 6.4.3 to 6.4.5",
    "test: `layout_snapshot` covers the cuts",
])
def test_good_titles(title):
    assert js(f"p.titleProblems({json.dumps(title)})") == []


@pytest.mark.parametrize("title,needle", [
    ("Reveal: end on transform none", "must look like"),
    ("feature: add particles options", "not a type"),
    ("fix(renderer): flicker", "not an area"),
    ("fix: Flicker on resize", "lower case"),
    ("fix: flicker on resize.", "full stop"),
])
def test_bad_titles(title, needle):
    problems = js(f"p.titleProblems({json.dumps(title)})")
    assert problems and needle in " ".join(problems)


def test_linked_numbers():
    body = "Closes #13, fixes #14 and part of #37.\nRefs Okohedeki/scroll-studio#9. Mentions #99 only."
    assert sorted(js(f"p.linkedNumbers({json.dumps(body)})")) == [9, 13, 14, 37]
    assert js("p.linkedNumbers(null)") == []


def issue(number, labels, state="open", pr=False):
    return {"number": number, "state": state, "labels": labels, "isPullRequest": pr}


@pytest.mark.parametrize("issues,core,ok", [
    ([], False, False),
    ([issue(1, ["status: accepted"])], False, True),
    ([issue(1, ["status: needs-triage"])], False, False),
    ([issue(1, ["status: accepted"], state="closed")], False, False),
    ([issue(1, ["status: accepted"])], True, False),               # core needs an agreed design
    ([issue(1, ["status: accepted", "status: design-approved"])], True, True),
    ([issue(1, ["status: accepted"], pr=True)], False, False),     # a pull request is not an issue
    ([issue(1, []), issue(2, ["status: accepted"])], False, True),
])
def test_issue_rules(issues, core, ok):
    problems = js(f"p.issueProblems({json.dumps(issues)}, {json.dumps(core)})")
    assert (problems == []) == ok, problems


@pytest.mark.parametrize("files,core", [
    (["runtime/src/players/frames.ts", "engine/compile/static/runtime/scroll-studio.js"], True),
    (["runtime/src/styles/bauhaus.ts", "engine/compile/static/runtime/scroll-studio.js",
      "engine/compile/static/runtime/chunks/bauhaus-abc.js", "engine/styles/bauhaus/style.css"], False),
    (["engine/compile/static/runtime/scroll-studio.js"], True),     # a bundle change with no source is suspicious
    (["engine/spec.py"], True),
    (["engine/compile/templates/blocks.html.j2"], True),
    (["engine/backends/comfy.py"], True),
    (["engine/cli.py"], True),
    ([".github/workflows/tests.yml"], True),
    (["LICENSE"], True),
    (["engine/styles/README.md"], True),
    (["engine/styles/bauhaus/style.yaml", "docs/styles/bauhaus.md"], False),
    (["engine/scenes/inside.py", "tests/test_inside.py", "docs/scenes.md", "changes/13.added.md"], False),
    (["examples/meridian/site.yaml"], False),
])
def test_tiers(files, core):
    assert js(f"p.isCore({json.dumps(files)})") is core


def test_areas():
    files = ["runtime/src/styles/bauhaus.ts", "engine/spec.py", "docs/guide.md", "README.md", "ui/package.json"]
    assert set(js(f"p.areas({json.dumps(files)})")) == {
        "area: runtime", "area: styles", "area: spec", "area: docs", "area: ui", "area: packaging"}


def test_size_ignores_generated_files():
    changes = [{"filename": "engine/compile/static/runtime/chunks/map.js", "changes": 5000},
               {"filename": "package-lock.json", "changes": 900},
               {"filename": "runtime/src/players/map.ts", "changes": 40}]
    assert js(f"p.sizeLabel({json.dumps(changes)})") == "size: s"
    assert js('p.sizeLabel([{"filename": "engine/spec.py", "changes": 1200}])') == "size: xl"


def change(name, status="added"):
    return {"filename": name, "status": status, "changes": 1}


@pytest.mark.parametrize("title,files,labels,ok", [
    ("feat(scenes): light keys", [change("changes/13.added.md")], [], True),
    ("feat(scenes): light keys", [change("engine/inside.py")], [], False),
    ("feat(scenes): light keys", [change("engine/inside.py")], ["skip-changelog"], True),
    ("docs: fix a link", [change("docs/guide.md")], [], True),
    ("fix: crash", [change("changes/+crash.fixed.md")], [], True),
    ("fix: crash", [change("changes/crash.md")], [], False),            # not a fragment name
    ("fix: crash", [change("changes/README.md", "modified")], [], False),
    ("feat(spec)!: one layout model", [change("changes/13.added.md")], [], False),
    ("feat(spec)!: one layout model", [change("changes/13.added.md"), change("changes/13.breaking.md")], [], True),
])
def test_fragment_rules(title, files, labels, ok):
    problems = js(f"p.fragmentProblems({json.dumps(title)}, {json.dumps(files)}, {json.dumps(labels)})")
    assert (problems == []) == ok, problems


def test_fragment_kinds_match_towncrier():
    tomllib = pytest.importorskip("tomllib")
    cfg = tomllib.loads((ROOT / "towncrier.toml").read_text(encoding="utf-8"))["tool"]["towncrier"]
    assert set(js("p.FRAGMENT_KINDS")) == {t["directory"] for t in cfg["type"]}


def test_every_label_the_automation_uses_exists():
    have = labels_file()
    used = set(js("Object.keys(p.AREAS)")) | {"tier: core", "status: accepted", "status: design-approved",
                                              "skip-changelog", "release", "status: needs-info", "status: stale",
                                              "status: needs-triage"}
    used |= {f"size: {s}" for s in ("xs", "s", "m", "l", "xl")}
    for form in (ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"):
        used |= set((yaml.safe_load(form.read_text(encoding="utf-8")) or {}).get("labels") or [])
    assert used <= have, f"labels used but not in .github/labels.yml: {sorted(used - have)}"


def test_title_scopes_cover_the_documented_areas():
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for scope in js("p.SCOPES"):
        if scope not in ("deps", "release"):        # used by bots
            assert f"`{scope}`" in contributing, f"title area {scope} is not documented in CONTRIBUTING.md"
