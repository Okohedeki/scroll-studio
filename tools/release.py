"""Release helper (docs/maintainers/releasing.md).

    python tools/release.py prepare 1.5.0     bump the version and gather changes/ into CHANGELOG.md
    python tools/release.py notes 1.5.0       print that version's changelog section (the release workflow uses it)
    python tools/release.py check v1.5.0      fail unless the tag matches pyproject.toml's version
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:rc\d+)?$")


def project_version(pyproject: str) -> str:
    project = re.search(r"^\[project\]\n(.*?)(?=^\[)", pyproject, re.S | re.M).group(1)
    return re.search(r'^version = "([^"]+)"', project, re.M).group(1)


def bump(pyproject: str, version: str) -> str:
    """pyproject.toml with [project].version set to `version`; nothing else changes."""
    if not SEMVER.match(version):
        raise ValueError(f"{version} is not MAJOR.MINOR.PATCH (or MAJOR.MINOR.PATCHrcN)")
    start = pyproject.index("[project]\n")
    end = pyproject.find("\n[", start + 1)
    end = len(pyproject) if end < 0 else end
    head, block, tail = pyproject[:start], pyproject[start:end], pyproject[end:]
    new, n = re.subn(r'^version = "[^"]+"', f'version = "{version}"', block, count=1, flags=re.M)
    if n != 1:
        raise ValueError("no version line in [project]")
    return head + new + tail


def notes(changelog: str, version: str) -> str:
    """The body of `## <version> ...` in CHANGELOG.md, without its heading."""
    m = re.search(rf"^## {re.escape(version)}\b.*?\n(.*?)(?=^## |\Z)", changelog, re.S | re.M)
    if not m:
        raise LookupError(f"CHANGELOG.md has no section for {version}")
    return m.group(1).strip() + "\n"


def prepare(version: str) -> None:
    py = ROOT / "pyproject.toml"
    old = project_version(py.read_text(encoding="utf-8"))
    py.write_text(bump(py.read_text(encoding="utf-8"), version), encoding="utf-8", newline="\n")
    subprocess.run([sys.executable, "-m", "towncrier", "build", "--yes", "--version", version,
                    "--date", dt.date.today().isoformat()], cwd=ROOT, check=True)
    print(f"{old} -> {version}. Review CHANGELOG.md (edit the section into prose if it helps), then:\n"
          f"  git switch -c release/v{version} && git commit -am 'chore(release): {version}'\n"
          f"  open a pull request labelled `release`; after it merges, tag main: git tag -s v{version} && git push origin v{version}")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("prepare", "notes", "check"):
        print(__doc__)
        return 2
    cmd, arg = argv
    if cmd == "prepare":
        prepare(arg)
    elif cmd == "notes":
        sys.stdout.write(notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), arg))
    else:
        version = project_version((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        if arg.removeprefix("v") != version:
            print(f"tag {arg} does not match pyproject.toml version {version}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
