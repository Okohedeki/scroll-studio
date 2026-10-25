"""code: a flight through a codebase, following an agent at work. Nothing to render ahead of time: the builder reads
the files, splits edits into diff lines, lays the route out over the scroll, and pins steps to the files they talk about.
"""
from pathlib import Path

from ..layout import set_window, window
from ..project import BuildContext, BuildError
from ..spec import CodeScene

LANGS = {".php": "php", ".ts": "ts", ".tsx": "tsx", ".js": "js", ".jsx": "tsx", ".mjs": "js", ".py": "py", ".go": "go",
         ".rs": "rust", ".rb": "rb", ".java": "java", ".kt": "kt", ".swift": "swift", ".c": "c", ".h": "c", ".cpp": "c",
         ".cs": "cs", ".sh": "sh", ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".css": "css",
         ".html": "html", ".sql": "sql", ".md": "md"}

# share of the scroll: the opening dive, each kind of file, the pull-back at the end
W_TERMINAL, W_READ, W_EDIT, W_RUN, W_OUTRO = 1.7, 0.42, 1.3, 1.5, 0.9


def build(sec: CodeScene, ctx: BuildContext, theme: dict) -> dict:
    files = []
    for f in sec.files:
        src = f.code
        if f.file:
            p = ctx.project.path(f.file)
            if not p.exists():
                raise BuildError(f"[{sec.id}] {f.path}: file {f.file} not found")
            src = p.read_text(encoding="utf-8", errors="replace")
        if src is None:
            raise BuildError(f"[{sec.id}] {f.path} needs `code` or `file`")
        raw = src.rstrip("\n").split("\n")
        if f.kind == "edit":
            lines = []
            for ln in raw:
                op = ln[:1] if ln[:1] in "+- " and ln else " "
                lines.append([op, ln[1:] if ln[:1] in "+- " and ln else ln])
        else:
            lines = [[" ", ln] for ln in raw]
        changed = sum(1 for op, _ in lines if op != " ")
        lang = f.lang or LANGS.get(Path(f.path).suffix.lower(), "sh" if f.kind == "run" else "txt")
        label = f.label or {"read": "Read", "edit": "Edit", "run": "$"}[f.kind]
        weight = {"read": W_READ, "edit": W_EDIT + 0.035 * changed, "run": W_RUN}[f.kind] * f.weight
        files.append({"path": f.path, "kind": f.kind, "lang": lang, "label": label, "todo": f.todo, "lines": lines, "w": weight})

    # the route over the scroll: [from, to] for the dive, every file, and the pull-back
    segs = ([("terminal", W_TERMINAL)] if sec.terminal else []) + [(i, f["w"]) for i, f in enumerate(files)] + [("outro", W_OUTRO)]
    total = sum(w for _, w in segs)
    acc, spans = 0.0, {}
    for key, w in segs:
        spans[key] = (round(acc / total, 4), round((acc + w) / total, 4))
        acc += w
    for i, f in enumerate(files):
        f["at"] = spans[i]
        del f["w"]

    # steps pinned to the route: state.file is a path (or a list of paths: the span from the first to the last).
    # A path can be on the route twice (read, then edited): each step takes the next match after the previous step's.
    def find(path: str, after: int) -> int:
        hits = [i for i, f in enumerate(files) if f["path"] == path]
        return next((i for i in hits if i >= after), hits[-1] if hits else -1)
    cursor = 0
    for st in sec.steps:
        pin = (st.state or {}).get("file")
        if pin is None or window(st) is not None:
            continue
        keys = pin if isinstance(pin, list) else [pin]
        ranges = []
        for k in keys:
            if k in ("terminal", "outro"):
                if k not in spans:
                    raise BuildError(f"[{sec.id}] step '{st.title}' is pinned to {k}, but the scene has no {k}")
                ranges.append(spans[k])
            elif (i := find(k, cursor)) >= 0:
                ranges.append(spans[i])
                cursor = i
            else:
                raise BuildError(f"[{sec.id}] step '{st.title}' is pinned to {k}, which is not in files")
        a, b = min(r[0] for r in ranges), max(r[1] for r in ranges)
        pad = (b - a) * 0.06
        set_window(st, round(a + pad, 4), round(b - pad * 0.5, 4))

    return {
        "terminal": sec.terminal.model_dump() if sec.terminal else None,
        "terminalAt": spans.get("terminal"),
        "outroAt": spans["outro"],
        "files": files,
        "tree": sec.tree,
        "colors": code_colors(sec, theme),
        "mono": theme["fonts"].get("mono") or "JetBrains Mono",
    }


def code_colors(sec, theme: dict) -> dict:
    """The colours the code world is drawn in: the page's, or with `surface:` on the scene the section's own (an editor
    is dark, so `surface: dark` on a light site puts the code in a dark room, captions and all)."""
    colors = {k: theme["colors"].get(k) for k in ("bg", "ink", "accent", "accent2")}
    if sec.surface and all(theme["colors"].get(k) for k in ("bg", "bg2", "ink", "accent2")):
        from ..compile.themes import surface_hex
        s = surface_hex(theme["colors"], theme.get("mode", "dark"), sec.surface)
        colors.update(bg=s["bg"], ink=s["ink"])
    return colors
