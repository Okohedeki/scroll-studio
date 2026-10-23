"""What may be committed. A public repository is cloned by everyone, forever: a stray 200 MB render, a media file in the
engine package or a leaked key cannot be taken back by a later commit. Three rules, checked on the tracked files:

  size     no file over 10 MB, except the allowlist below (each entry says why it is there);
  media    video, 3D, images and other binaries live only where the repository keeps them (example inputs and proofs, the
           showcase, docs/media and the built runtime), not scattered through the engine, tests or docs text;
  secrets  no .env, key, local settings or machine config file is tracked (.gitignore keeps them out; this is the net).

When a rule trips on something you mean to commit, the better answer is usually a different place (a download step, an
`inputs/` folder, a placeholder) before it is an allowlist entry."""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 10 * 1024 * 1024

# Over the size limit on purpose. Keep this list short; new entries need a reason a reviewer will accept.
BIG_FILE_ALLOWLIST = {
    "examples/lodestar-orbital/inputs/film.mp4": "the example's input film: a build starts from real footage, not a stand-in",
}

MEDIA_SUFFIXES = {".mp4", ".webm", ".mov", ".glb", ".gltf", ".ply", ".spz", ".exr", ".npz", ".gif", ".png", ".jpg",
                  ".jpeg", ".webp", ".woff", ".woff2", ".ttf", ".otf", ".ico", ".pdf", ".zip"}
# Where media may live: glob patterns on the repository-relative path.
MEDIA_FOLDERS = [
    "examples/*/inputs/*",       # what an example is built from
    "examples/*/proof/*",        # review images and reports kept as the proof an example works
    "examples/showcase/*",       # the preview clips and posters of the showcase page
    "docs/media/*",              # images in the README and docs
    "engine/compile/static/*",   # the built runtime and its assets
]
# Single files in the wrong place today. Move or delete them rather than adding more.
MEDIA_FILE_ALLOWLIST = {
    "examples/inside-board/inside_inside.jpg": "an unreferenced still next to a site.yaml; belongs in inputs/ or nowhere",
}

FORBIDDEN_NAMES = [".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "studio.toml", "settings.local.json"]
ALLOWED_NAMES = {".env.example"}      # a template with no values


def oversize(sizes: dict[str, int]) -> list[str]:
    return [f"{p}: {n / 1e6:.1f} MB" for p, n in sorted(sizes.items()) if n > MAX_BYTES and p not in BIG_FILE_ALLOWLIST]


def misplaced_media(paths: list[str]) -> list[str]:
    return [p for p in sorted(paths) if PurePosixPath(p).suffix.lower() in MEDIA_SUFFIXES
            and p not in MEDIA_FILE_ALLOWLIST and not any(fnmatch.fnmatchcase(p, g) for g in MEDIA_FOLDERS)]


def secret_files(paths: list[str]) -> list[str]:
    return [p for p in sorted(paths) if PurePosixPath(p).name not in ALLOWED_NAMES
            and any(fnmatch.fnmatchcase(PurePosixPath(p).name, g) for g in FORBIDDEN_NAMES)]


def tracked() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout")
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode()
    return [p for p in out.split("\0") if p and (ROOT / p).is_file()]


def test_the_checks_catch_what_they_are_for():
    assert oversize({"a.bin": MAX_BYTES + 1, "b.bin": MAX_BYTES, next(iter(BIG_FILE_ALLOWLIST)): MAX_BYTES * 3}) \
        == [f"a.bin: {(MAX_BYTES + 1) / 1e6:.1f} MB"]
    assert misplaced_media(["engine/x/clip.mp4", "tests/a.PNG", "examples/a/inputs/b.mp4", "examples/a/proof/c.jpg",
                            "docs/media/readme/d.jpg", "engine/compile/static/runtime/e.woff2", "README.md"]) \
        == ["engine/x/clip.mp4", "tests/a.PNG"]
    assert misplaced_media(["examples/a/inputs/deep/er/b.mp4", "examples/showcase/previews/p.mp4"]) == []
    assert secret_files([".env", "a/.env.local", ".env.example", "k/server.pem", "home/id_rsa", "studio.toml",
                         "studio.example.toml", ".claude/settings.local.json", ".claude/settings.json"]) \
        == [".claude/settings.local.json", ".env", "a/.env.local", "home/id_rsa", "k/server.pem", "studio.toml"]


def test_no_tracked_file_is_over_ten_megabytes():
    files = tracked()
    bad = oversize({p: (ROOT / p).stat().st_size for p in files})
    assert not bad, ("tracked files over 10 MB (host the file elsewhere and download it in a setup step, or, for an "
                     "example's own input, add it to BIG_FILE_ALLOWLIST with a reason):\n  " + "\n  ".join(bad))


def test_every_allowlist_entry_is_still_needed():
    files = set(tracked())
    sizes = {p: (ROOT / p).stat().st_size for p in BIG_FILE_ALLOWLIST if p in files}
    stale = [p for p in BIG_FILE_ALLOWLIST if sizes.get(p, 0) <= MAX_BYTES]
    stale += [p for p in MEDIA_FILE_ALLOWLIST if p not in files]
    assert not stale, "remove these from the allowlists in tests/test_repo_hygiene.py:\n  " + "\n  ".join(stale)


def test_media_files_are_only_where_the_repository_keeps_them():
    bad = misplaced_media(tracked())
    assert not bad, ("media files outside the folders that hold them (" + ", ".join(MEDIA_FOLDERS) + "):\n  "
                     + "\n  ".join(bad))


def test_no_secrets_or_machine_config_are_tracked():
    bad = secret_files(tracked())
    assert not bad, ("files that must stay local (studio.toml, .env, keys, settings.local.json): remove them from git "
                     "with `git rm --cached`:\n  " + "\n  ".join(bad))
