"""Check an installed copy of Scroll Studio: the CI `install` job runs this with the virtualenv's Python, from outside the
checkout, after installing the built wheel.

    python -I tools/install_check.py --checkout . [--sdist dist/scroll_studio-<version>.tar.gz]

It fails when the install is not self-contained: a data file the checkout tracks under engine/ (templates, styles, the
runtime bundle, themes.yaml, models.yaml, Blender scripts) that did not get packaged, or an example that does not compile
to the layout recorded in tests/snapshots/layout from the installed package alone. `-I` keeps the checkout out of the
import path, so the imports below can only come from site-packages."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
from pathlib import Path


def tracked_engine_files(checkout: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(checkout), "ls-files", "-z", "--", "engine"], capture_output=True, check=True)
    return [p for p in out.stdout.decode().split("\0") if p]


def check_installed(checkout: Path) -> list[str]:
    import engine
    package = Path(engine.__file__).resolve().parent
    problems = []
    if package.is_relative_to(checkout.resolve()):
        return [f"engine was imported from the checkout ({package}), not from the installed package"]
    root = package.parent
    missing = [p for p in tracked_engine_files(checkout) if not (root / p).is_file()]
    problems += [f"not installed: {p}" for p in missing]
    return problems


def check_sdist(checkout: Path, sdist: Path) -> list[str]:
    with tarfile.open(sdist) as t:
        # members are <name>-<version>/engine/...: drop the first component
        names = {m.name.split("/", 1)[1] for m in t.getmembers() if "/" in m.name}
    return [f"not in the sdist: {p}" for p in tracked_engine_files(checkout) if p not in names]


def check_standins(checkout: Path) -> list[str]:
    """Compile every example's page with stand-ins for the renders, through the installed templates, themes and styles,
    and compare with the recorded layout."""
    import json
    from engine.compile.layout_snapshot import diff_layout, layout_snapshot
    problems = []
    snapshots = checkout / "tests" / "snapshots" / "layout"
    for site_yaml in sorted((checkout / "examples").glob("*/site.yaml")):
        name = site_yaml.parent.name
        try:
            snap = layout_snapshot(site_yaml)
        except Exception as e:      # a missing template or style is an exception here
            problems.append(f"{name}: could not compile ({e.__class__.__name__}: {e})")
            continue
        old = json.loads((snapshots / f"{name}.json").read_text(encoding="utf-8"))
        lines = diff_layout(old, snap)
        if lines:
            problems.append(f"{name}: the installed package lays the page out differently ({len(lines)} differences, first: {lines[0]})")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--checkout", type=Path, required=True, help="the repository checkout (read for the file list, the examples and the snapshots)")
    ap.add_argument("--sdist", type=Path, help="also check that this source distribution carries the same files")
    args = ap.parse_args()
    checkout = args.checkout.resolve()
    problems = check_installed(checkout)
    if args.sdist:
        problems += check_sdist(checkout, args.sdist)
    if not problems:
        problems += check_standins(checkout)
    for p in problems[:50]:
        print("FAIL", p)
    if problems:
        print(f"{len(problems)} problem(s): fix [tool.setuptools.package-data] in pyproject.toml if a data file is missing")
        return 1
    print("install ok: every tracked engine file is packaged and every example compiles from the installed package")
    return 0


if __name__ == "__main__":
    sys.exit(main())
