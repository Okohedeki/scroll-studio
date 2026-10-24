"""Every look (32 styles, 10 presets) rendered in Chromium at a desktop and a phone size."""
from __future__ import annotations

import pytest

import harness

LOOKS = pytest.mark.parametrize("look", harness.LOOKS)
VIEWPORTS = pytest.mark.parametrize("viewport", list(harness.VIEWPORTS))


@LOOKS
@VIEWPORTS
@pytest.mark.parametrize("reduced", [False, True], ids=["motion", "reduced"])
def test_the_page_runs_clean(runs, look, viewport, reduced):
    run = runs(look, viewport, reduced)
    found, accepted = harness.problems(run), harness.known(run)
    new = {c: m for c, m in found.items() if c not in accepted}
    assert not new, f"{run.label}: " + "; ".join(new.values())
    if found:
        pytest.xfail("known issue: " + "; ".join(accepted[c] for c in found))


@LOOKS
@VIEWPORTS
def test_no_serious_accessibility_violations(runs, look, viewport):
    run = runs(look, viewport, True)
    assert run.ready, f"{run.label} never became ready"
    bad = harness.unexpected(run)
    assert not bad, f"{run.label}: " + " | ".join(harness.describe(v) for v in bad)

