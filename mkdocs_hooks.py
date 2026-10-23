"""MkDocs hooks for the Scroll Studio docs site.

The docs are written to be read on GitHub, so their links point at files in the repository: `../README.md`,
`docs/guide.md`, `CLA.md`, `engine/styles/README.md`. A site build cannot follow those. Rather than copy and edit the
files, this hook leaves them as they are and, while the site is built:

* adds the community files that live at the repository root (CONTRIBUTING, SECURITY, CHANGELOG ...) as pages. Files
  that do not exist yet (GOVERNANCE.md, MAINTAINERS.md, SUPPORT.md) are skipped, so adding one is a nav line only;
* rewrites each relative link to the page it became on the site, or, for a file that is not on the site, to the same
  file on GitHub. A link to something that exists nowhere is left alone, so `mkdocs build --strict` reports it;
* points each generated reference page's "edit" button at the engine source it was generated from.

The link logic is plain functions with no MkDocs imports, so tests/test_docs.py can check it without MkDocs installed.
"""
from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parent

# Repository file -> page on the site. Pages are grouped by the nav in mkdocs.yml.
ROOT_PAGES: dict[str, str] = {
    "CONTRIBUTING.md": "contributing/guide.md",
    "CODE_OF_CONDUCT.md": "contributing/code-of-conduct.md",
    "SECURITY.md": "contributing/security.md",
    "CLA.md": "contributing/cla.md",
    "AGENTS.md": "contributing/agents.md",
    "GOVERNANCE.md": "project/governance.md",
    "MAINTAINERS.md": "project/maintainers.md",
    "SUPPORT.md": "project/support.md",
    "CHANGELOG.md": "project/changelog.md",
    "NOTICE.md": "project/notice.md",
}

# Generated reference page -> the source file its "edit" button should open (path from the docs folder).
GENERATED_SOURCES: dict[str, str] = {
    "reference/spec/": "../engine/spec.py",
    "reference/cli.md": "../engine/cli.py",
    "reference/mcp.md": "../engine/mcp_server.py",
}

SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
INLINE_LINK = re.compile(r"(!?\[[^\]\n]*\]\()(<?)([^)\s<>]+)(>?)((?:\s+\"[^\"]*\")?\))")
REF_DEF = re.compile(r"^(\s{0,3}\[[^\]\n]+\]:\s*)(<?)(\S+?)(>?)(\s*)$", re.M)
HTML_ATTR = re.compile(r"""(\b(?:href|src)=)(["'])([^"']+)(\2)""")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+\1")
# the row of links every docs page opens with, for readers on GitHub; the site has its own navigation
GITHUB_NAV_ROW = re.compile(r"\A\s*\[← README\]\([^)]*\)[^\n]*\(why\.md\)[^\n]*\n+")


def map_target(target: str, origin: str, dest: str, site_pages: dict[str, str], exists: Callable[[str], str | None],
               repo_url: str, branch: str) -> str:
    """Where a relative link should point on the site.

    origin: the repository path of the file the link is written in. dest: the site path of the page it appears on.
    site_pages: repository path -> site path of every file the site serves. exists: 'file', 'dir' or None for a
    repository path. Anything that is not a relative link into the repository comes back unchanged.
    """
    if not target or SCHEME.match(target) or target.startswith(("#", "/")):
        return target
    path, hash_, fragment = target.partition("#")
    path = path.partition("?")[0]
    if not path:
        return target
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(origin), unquote(path)))
    if resolved == ".." or resolved.startswith("../"):
        return target
    suffix = hash_ + fragment
    served = site_pages.get(resolved) or site_pages.get(resolved.rstrip("/") + "/index.md")
    if served:
        return posixpath.relpath(served, posixpath.dirname(dest) or ".") + suffix
    kind = exists(resolved)
    if kind is None:
        return target
    return f"{repo_url.rstrip('/')}/{'tree' if kind == 'dir' else 'blob'}/{branch}/{resolved.rstrip('/')}{suffix}"


def rewrite_links(markdown: str, origin: str, dest: str, site_pages: dict[str, str],
                  exists: Callable[[str], str | None], repo_url: str, branch: str) -> str:
    """Rewrite every relative link outside code. Fenced blocks and `inline code` are left exactly as written."""
    def fix(m: re.Match, target_group: int) -> str:
        groups = list(m.groups())
        groups[target_group] = map_target(groups[target_group], origin, dest, site_pages, exists, repo_url, branch)
        return "".join(groups)

    def prose_line(line: str) -> str:
        # mask `code` first (link text may contain code, so the line is not cut around it)
        spans: list[str] = []

        def mask(m: re.Match) -> str:
            spans.append(m.group(0))
            return f"\x00{len(spans) - 1}\x00"

        text = CODE_SPAN.sub(mask, line)
        text = INLINE_LINK.sub(lambda m: fix(m, 2), text)
        text = REF_DEF.sub(lambda m: fix(m, 2), text)
        text = HTML_ATTR.sub(lambda m: fix(m, 2), text)
        return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)

    out, fence = [], None
    for line in markdown.split("\n"):
        stripped = line.lstrip()
        marker = stripped[:3] if stripped.startswith(("```", "~~~")) else None
        if fence is None and marker:
            fence = marker
            out.append(line)
        elif fence is not None:
            if marker == fence:
                fence = None
            out.append(line)
        else:
            out.append(prose_line(line))
    return "\n".join(out)


# ---------------------------------------------------------------- MkDocs events

def _branch(config) -> str:
    # edit_uri is "edit/<branch>/docs/"
    parts = (config.get("edit_uri") or "").strip("/").split("/")
    return parts[1] if len(parts) > 1 else "main"


def on_files(files, config):
    from mkdocs.structure.files import File

    for source, src_uri in ROOT_PAGES.items():
        path = REPO_ROOT / source
        if not path.is_file():
            continue
        page = File.generated(config, src_uri, content=path.read_text(encoding="utf-8"))
        page.edit_uri = f"../{source}"
        files.append(page)
    for f in files:
        for prefix, source in GENERATED_SOURCES.items():
            if f.src_uri.startswith(prefix):
                f.edit_uri = source
    return files


def _site_pages(files, config) -> dict[str, str]:
    pages = {f"docs/{f.src_uri}": f.src_uri for f in files if f.src_dir == config.docs_dir}
    pages.update({src: uri for src, uri in ROOT_PAGES.items() if files.get_file_from_path(uri)})
    return pages


def _exists(path: str) -> str | None:
    p = REPO_ROOT / path
    return "dir" if p.is_dir() else "file" if p.is_file() else None


def on_page_markdown(markdown, page, config, files):
    src_uri = page.file.src_uri
    root = next((src for src, uri in ROOT_PAGES.items() if uri == src_uri), None)
    if root is None and page.file.src_dir != config.docs_dir:
        return markdown
    origin = root or f"docs/{src_uri}"
    if root is None:
        markdown = GITHUB_NAV_ROW.sub("", markdown, count=1)
    return rewrite_links(markdown, origin, src_uri, _site_pages(files, config), _exists, config["repo_url"],
                         _branch(config))
