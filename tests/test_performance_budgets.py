"""Size budgets: the browser runtime and a built page may not grow past what tests/performance_budgets.json allows.

What is measured (bytes, so it is the same on every machine):

  runtime   the entry bundle (index.js), studio.css, every lazily loaded chunk of engine/compile/static/runtime on its own
            (by name without the content hash: `map-CC4wvtNu.js` is `map.js`), and the whole folder, which the compiler
            copies into every built site. A new chunk has no budget until one is added on purpose.
  pages     for each example, the page the compiler emits for a stand-in compile (engine/compile/layout_snapshot.py
            `page_html`: the HTML with the inline CSS and the inline JSON and scripts it writes) plus the stylesheet of the
            example's style. What every site ships regardless of the example (the entry and studio.css) is budgeted under
            `runtime`, so a change to the page template or a style stylesheet shows up here and nowhere else.

Each budget is the size at the time it was set plus about 10%. When growth is the point of a change, raise the budgets
deliberately, look at the diff of tests/performance_budgets.json, and say in the pull request why the page got heavier:

    UPDATE_PERFORMANCE_BUDGETS=1 python -m pytest tests/test_performance_budgets.py

That raises only what is over (or new) and drops what no longer exists; it never lowers one, so when a change makes
something lighter, lower its budget by hand in the same pull request. Frame times are not measured here: that needs a real
browser and is a separate, slower job.

No GPU, no browser, no network."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from engine.compile import themes
from engine.compile.layout_snapshot import page_html
from engine.project import Project

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "engine" / "compile" / "static" / "runtime"
BUDGETS = Path(__file__).resolve().parent / "performance_budgets.json"
EXAMPLES = sorted((ROOT / "examples").glob("*/site.yaml"), key=lambda p: p.parent.name)
UPDATE = os.environ.get("UPDATE_PERFORMANCE_BUDGETS") == "1"
MARGIN = 1.10           # a budget is the size when it was set, plus this much,
ROUND_UP_TO = 100       # rounded up to a whole hundred bytes
HOW_TO_RAISE = ("If the growth is intended, raise the budget on purpose (and say why in the pull request):\n"
                "    UPDATE_PERFORMANCE_BUDGETS=1 python -m pytest tests/test_performance_budgets.py")


# ---------------------------------------------------------------- the logic (unit tested below)

def budget_for(size: int) -> int:
    """The budget for something of this size: 10% more, to a whole hundred bytes."""
    return -(-int(size * MARGIN) // ROUND_UP_TO) * ROUND_UP_TO


def chunk_key(filename: str) -> str:
    """`map-CC4wvtNu.js` -> `map.js`: Vite puts an 8-character content hash before the extension."""
    return re.sub(r"-[A-Za-z0-9_-]{8}(\.js)$", r"\1", filename)


def over_budget(what: str, sizes: dict[str, int], budgets: dict[str, int]) -> list[str]:
    """One line per thing that is over its budget or has none."""
    lines = []
    for key in sorted(sizes):
        size, budget = sizes[key], budgets.get(key)
        if budget is None:
            lines.append(f"{what} {key}: {size:,} bytes and no budget (suggested: {budget_for(size):,})")
        elif size > budget:
            lines.append(f"{what} {key}: {size:,} bytes, over its budget of {budget:,} by {size - budget:,} ({100 * (size - budget) / budget:.1f}%)")
    return lines


def raised(sizes: dict[str, int], budgets: dict[str, int]) -> dict[str, int]:
    """The budgets after a deliberate raise: what is over or new gets a fresh budget, what is gone is dropped, nothing is lowered."""
    return {k: (budgets[k] if k in budgets and sizes[k] <= budgets[k] else budget_for(sizes[k])) for k in sorted(sizes)}


def read_budgets() -> dict:
    return json.loads(BUDGETS.read_text(encoding="utf-8"))


def write_budgets(data: dict) -> None:
    BUDGETS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def runtime_sizes() -> dict:
    """Entry, stylesheet, total and each chunk of the committed runtime."""
    if not (RUNTIME / "index.js").exists():
        pytest.skip("the runtime is not built (npm run build:runtime)")
    chunks: dict[str, int] = {}
    for f in sorted((RUNTIME / "chunks").glob("*.js")):
        key = chunk_key(f.name)
        assert key not in chunks, f"two chunks are called {key}: the budgets are keyed by name without the hash"
        chunks[key] = f.stat().st_size
    total = sum(f.stat().st_size for f in RUNTIME.rglob("*") if f.is_file())
    return {"entry": (RUNTIME / "index.js").stat().st_size, "css": (RUNTIME / "studio.css").stat().st_size, "total": total, "chunks": chunks}


def page_weight(site_yaml: Path) -> int:
    """HTML (with its inline CSS, JSON and scripts) of the stand-in page, plus the style's own stylesheet."""
    site = Project(site_yaml.parent).load()
    weight = len(page_html(site).encode("utf-8"))
    style = themes.resolve(site.theme)["style"]
    if style:
        weight += len(themes.style_css(style).encode("utf-8"))
    return weight


# ---------------------------------------------------------------- the logic, on made-up numbers

def test_a_budget_is_ten_percent_more_to_a_whole_hundred_bytes():
    assert budget_for(1000) == 1100
    assert budget_for(40796) == 44900
    assert budget_for(1570) == 1800
    assert budget_for(1) == 100
    assert all(budget_for(n) >= n * 1.1 - 1e-9 and budget_for(n) % 100 == 0 for n in (1, 99, 1234, 46255, 1058092))


def test_chunk_names_lose_their_content_hash():
    assert chunk_key("map-CC4wvtNu.js") == "map.js"
    assert chunk_key("GLTFLoader-Bga6aQjg.js") == "GLTFLoader.js"
    assert chunk_key("_art-C_tXfIzL.js") == "_art.js"
    assert chunk_key("anime-intro-BmHzmk39.js") == "anime-intro.js"
    assert chunk_key("light-DAW-M88A.js") == "light.js"        # a hash can contain a dash
    assert chunk_key("scene3d-DkRnNWzE.js") == "scene3d.js"
    assert chunk_key("plain.js") == "plain.js"


def test_what_is_over_budget_or_has_none_is_named():
    lines = over_budget("chunk", {"a.js": 1100, "b.js": 1101, "c.js": 50}, {"a.js": 1100, "b.js": 1100})
    assert len(lines) == 2
    assert lines[0].startswith("chunk b.js: 1,101 bytes, over its budget of 1,100 by 1")
    assert lines[1] == "chunk c.js: 50 bytes and no budget (suggested: 100)"
    assert over_budget("chunk", {"a.js": 5}, {"a.js": 5, "gone.js": 9}) == []      # a budget with nothing to measure is not an error here


def test_a_deliberate_raise_lifts_what_is_over_adds_what_is_new_drops_what_is_gone_and_lowers_nothing():
    budgets = {"fits.js": 5000, "grew.js": 1100, "gone.js": 900, "lighter.js": 9000}
    sizes = {"fits.js": 4000, "grew.js": 1500, "new.js": 200, "lighter.js": 1000}
    assert raised(sizes, budgets) == {"fits.js": 5000, "grew.js": 1700, "lighter.js": 9000, "new.js": 300}


# ---------------------------------------------------------------- the real thing

def test_the_budget_file_says_how_to_raise_a_budget():
    data = read_budgets()
    assert "UPDATE_PERFORMANCE_BUDGETS=1" in " ".join(data["_comment"])
    assert set(data) == {"_comment", "runtime", "pages"}
    assert set(data["runtime"]) == {"entry", "css", "total", "chunks"}


def test_the_runtime_stays_within_its_budgets():
    sizes, data = runtime_sizes(), read_budgets()
    flat = {"entry": sizes["entry"], "css": sizes["css"], "total": sizes["total"]}
    if UPDATE:
        top = raised(flat, {k: v for k, v in data["runtime"].items() if k != "chunks"})
        data["runtime"] = {"entry": top["entry"], "css": top["css"], "total": top["total"], "chunks": raised(sizes["chunks"], data["runtime"]["chunks"])}
        write_budgets(data)
        return
    budgets = data["runtime"]
    lines = over_budget("runtime", flat, budgets) + over_budget("runtime chunk", sizes["chunks"], budgets["chunks"])
    assert not lines, "\n  ".join(["the runtime grew past its budget:"] + lines) + "\n" + HOW_TO_RAISE


def test_no_budget_outlives_the_chunk_or_example_it_was_for():
    if UPDATE:
        return                      # the raise above and below already dropped them
    data = read_budgets()
    assert set(data["runtime"]["chunks"]) <= set(runtime_sizes()["chunks"]), \
        f"budgets for chunks that no longer exist: {sorted(set(data['runtime']['chunks']) - set(runtime_sizes()['chunks']))}; remove them from tests/performance_budgets.json"
    assert set(data["pages"]) <= {p.parent.name for p in EXAMPLES}, \
        f"budgets for examples that no longer exist: {sorted(set(data['pages']) - {p.parent.name for p in EXAMPLES})}; remove them from tests/performance_budgets.json"


@pytest.mark.parametrize("site_yaml", EXAMPLES, ids=lambda p: p.parent.name)
def test_a_built_page_stays_within_its_weight_budget(site_yaml: Path):
    name, weight = site_yaml.parent.name, page_weight(site_yaml)
    data = read_budgets()
    if UPDATE:
        names = {p.parent.name for p in EXAMPLES}
        pages = {k: v for k, v in data["pages"].items() if k in names}          # an example that is gone loses its budget
        pages.update(raised({name: weight}, pages))
        data["pages"] = dict(sorted(pages.items()))
        write_budgets(data)
        return
    lines = over_budget("page", {name: weight}, data["pages"])
    assert not lines, "\n  ".join(["a built page got heavier than its budget (HTML, inline CSS and JS, and the style's stylesheet):"] + lines) + "\n" + HOW_TO_RAISE
