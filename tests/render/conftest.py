"""Render tests: real pages in real Chromium. They run only inside the pinned Playwright image (tests/render/README.md,
SS_RENDER=1), where fonts and the browser build are the same on every machine; anywhere else they are skipped and the ordinary `tests` workflow is unaffected."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ENABLED = os.environ.get("SS_RENDER") == "1"
HERE = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config, items):
    ours = [i for i in items if HERE in Path(str(i.fspath)).parents]
    for item in ours:
        if not ENABLED:
            item.add_marker(pytest.mark.skip(reason="render tests run inside the Playwright image only: set SS_RENDER=1 (tests/render/README.md)"))
        elif "look" in getattr(getattr(item, "callspec", None), "params", {}):
            # with pytest-xdist every look's tests go to one worker, which builds that look and loads each page once
            item.add_marker(pytest.mark.xdist_group(item.callspec.params["look"]))


class Looks:
    """The kitchen-sink site, one folder per look, built the first time a look is asked for and served by the engine's
    own static server (it sets the JavaScript MIME types Python's does not on Windows)."""

    def __init__(self, root: Path):
        from engine.serve import serve
        self.root, self.built = root, set()
        self.httpd = serve(root, 0, background=True)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def url(self, look: str) -> str:
        import harness
        if look not in self.built:
            harness.build(self.root, look)
            self.built.add(look)
        return self.base

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture(scope="session")
def runs(tmp_path_factory):
    """runs(look, viewport, reduced) -> harness.Run; each load happens once and is shared by every test that asks."""
    import harness
    from playwright.sync_api import sync_playwright
    looks = Looks(tmp_path_factory.mktemp("render-site"))
    cache: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def get(look: str, viewport: str, reduced: bool):
            key = (look, viewport, reduced)
            if key not in cache:
                cache[key] = harness.load(browser, looks.url(look), look, viewport, reduced)
            return cache[key]
        yield get
        browser.close()
    looks.close()
