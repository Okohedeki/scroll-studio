"""tools/release.py: version bumps and release notes (docs/maintainers/releasing.md)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_tool", ROOT / "tools" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

PYPROJECT = '''[project]
name = "scroll-studio"
version = "1.4.0"
dependencies = ["x"]

[project.optional-dependencies]
dev = ["pytest"]

[tool.other]
version = "9.9.9"
'''


def test_bump_changes_only_the_project_version():
    out = release.bump(PYPROJECT, "1.5.0")
    assert release.project_version(out) == "1.5.0"
    assert 'version = "9.9.9"' in out
    assert out.replace('version = "1.5.0"', 'version = "1.4.0"', 1) == PYPROJECT


@pytest.mark.parametrize("bad", ["1.5", "v1.5.0", "1.5.0-beta", ""])
def test_bump_refuses_bad_versions(bad):
    with pytest.raises(ValueError):
        release.bump(PYPROJECT, bad)


def test_the_real_pyproject_has_a_version():
    assert release.SEMVER.match(release.project_version((ROOT / "pyproject.toml").read_text(encoding="utf-8")))


def test_notes_extracts_one_section():
    changelog = "# Changelog\n\nIntro.\n\n## 1.5.0 · 2026-11-01\n\n### Added\n\n- New.\n\n## 1.4.0 · 2026-10-13\n\n- Old.\n"
    assert release.notes(changelog, "1.5.0") == "### Added\n\n- New.\n"
    assert release.notes(changelog, "1.4.0") == "- Old.\n"
    with pytest.raises(LookupError):
        release.notes(changelog, "1.6.0")


def test_notes_for_the_latest_release_in_the_real_changelog():
    assert release.notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), "1.4.0").strip()


def test_check_compares_the_tag(capsys):
    version = release.project_version((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert release.main(["check", f"v{version}"]) == 0
    assert release.main(["check", "v0.0.1"]) == 1
