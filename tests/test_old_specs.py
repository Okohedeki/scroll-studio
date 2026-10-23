"""Old specs keep building (docs/compatibility.md): every example spec from every release tag must still validate and
compile to a page.

tests/fixtures/old_specs/<tag>/ holds each example's site.yaml as it was at that tag (only the versions that differ).
The page is rendered with stand-ins for every render, the way the layout snapshots and conformance tests do, so no GPU
or inputs are needed. After a release, add its examples:

    python tests/test_old_specs.py v1.5.0
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CORPUS = Path(__file__).parent / "fixtures" / "old_specs"
SPECS = sorted(CORPUS.glob("v*/*.yaml"))


def test_the_corpus_covers_every_release():
    tags = {p.parent.name for p in SPECS}
    assert {"v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0", "v1.4.0"} <= tags


@pytest.mark.parametrize("path", SPECS, ids=[f"{p.parent.name}/{p.stem}" for p in SPECS])
def test_old_spec_still_builds(path):
    from engine.compile.layout_snapshot import _find, page_html, parse
    from engine.spec import Site

    site = Site.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    main = _find(parse(page_html(site)), "main")
    sections = [c for c in main.children if c.tag != "script"]
    assert len(sections) == len(site.sections), "a section no longer renders"


def add_release(tag: str) -> int:
    """Copy the examples of a new release tag into the corpus, skipping specs identical to one already there."""
    root = Path(__file__).resolve().parents[1]
    have = {hashlib.sha256(p.read_bytes()).hexdigest() for p in SPECS}
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", tag], cwd=root, capture_output=True, text=True,
                           check=True).stdout.split()
    added = 0
    for name in names:
        parts = name.split("/")
        if len(parts) != 3 or parts[0] != "examples" or parts[2] != "site.yaml":
            continue
        data = subprocess.run(["git", "show", f"{tag}:{name}"], cwd=root, capture_output=True, check=True).stdout
        data = data.replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() in have:
            continue
        out = CORPUS / tag / f"{parts[1]}.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        added += 1
    return added


if __name__ == "__main__":
    print(f"added {add_release(sys.argv[1])} specs")
