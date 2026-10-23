"""The CLA check (.github/scripts/cla.js): who has to sign, what counts as signing, what the bot says."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLA = ROOT / ".github" / "scripts" / "cla.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def js(expr: str):
    code = f"const c = require({json.dumps(str(CLA))}); process.stdout.write(JSON.stringify({expr}));"
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def commit(login=None, uid=None, name="Someone"):
    return {"author": {"login": login, "id": uid} if login else None, "commit": {"author": {"name": name}}}


def test_signing_sentence_matches_the_workflow_filter():
    workflow = (ROOT / ".github" / "workflows" / "cla.yml").read_text(encoding="utf-8")
    assert js("c.SENTENCE") in workflow


@pytest.mark.parametrize("body,ok", [
    ("I have read the CLA Document and I hereby sign the CLA", True),
    ("  I have read the CLA Document and I hereby sign the CLA.\n", True),
    ("I have read the CLA Document and I hereby sign the CLA, but", False),
    ("recheck", False),
    (None, False),
])
def test_is_signing(body, ok):
    assert js(f"c.isSigning({json.dumps(body)})") is ok


def test_authors_skip_bots_and_the_maintainer_and_keep_unlinked_commits():
    commits = [commit("Fede046", 1), commit("Fede046", 1), commit("dependabot[bot]", 2), commit("Okohedeki", 3),
               commit(name="Laptop User")]
    people = js(f"c.authors({json.dumps(commits)})")
    assert people == [{"login": "Fede046", "id": 1}, {"login": None, "name": "Laptop User"}]


def test_unsigned_and_messages():
    signatures = {"signedContributors": [{"name": "Fede046", "id": 1}]}
    people = [{"login": "Fede046", "id": 1}, {"login": "new-person", "id": 9}, {"login": None, "name": "Laptop User"}]
    missing = js(f"c.unsigned({json.dumps(people)}, {json.dumps(signatures)})")
    assert [p.get("login") for p in missing] == ["new-person", None]
    text = js(f"c.message({json.dumps(missing)})")
    assert "@new-person" in text and "Laptop User" in text and js("c.SENTENCE") in text
    assert "All contributors have signed" in js("c.message([])")
