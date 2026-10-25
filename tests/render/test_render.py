"""Every look (32 styles, 10 presets, and a few styles wearing a brand) rendered in Chromium at a desktop and a phone size."""
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



BRAND_LOOKS = pytest.mark.parametrize("look", [l for l in harness.LOOKS if l.startswith("brand-")])


@BRAND_LOOKS
def test_a_style_wears_the_brand_it_is_given(runs, look):
    """The page sets --skin-<role> for each palette role the brand re-colours (what a style's runtime reads), the colours
    the compiler worked out for it, and the styles that draw in their runtime ran with them without an error."""
    from engine.compile import themes
    from engine.spec import Site
    theme = themes.resolve(Site.model_validate(harness.spec_for(look)).theme)
    run = runs(look, "desktop", True)
    assert run.ready, f"{run.label} never became ready"
    assert run.skin == {role.replace("_", "-"): c for role, c in theme["skin"]["roles"].items()}
    assert {"accent", "bg", "ink"} <= set(run.skin), f"{look}: the brand's palette is not on the page: {run.skin}"
