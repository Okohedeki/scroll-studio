"""The code scene's colours (engine/scenes/code.py): the page's, or the section's own `surface:`, so a light site can put
its code in a dark editor room with captions to match. No GPU, no browser."""
from __future__ import annotations

from engine.compile import themes
from engine.scenes.code import code_colors
from engine.spec import Site


def scene(**kw) -> tuple:
    site = Site.model_validate({"name": "x", "theme": {"preset": "paper"}, "sections": [
        {"id": "c", "type": "code", "files": [{"path": "a.py", "code": "print(1)"}], **kw}]})
    return site.sections[0], themes.resolve(site.theme)


def test_the_code_world_takes_the_page_colours_by_default():
    sec, theme = scene()
    assert code_colors(sec, theme)["bg"] == theme["colors"]["bg"]


def test_a_dark_surface_puts_the_code_in_a_dark_room_on_a_light_site():
    sec, theme = scene(surface="dark")
    c = code_colors(sec, theme)
    assert theme["mode"] == "light"
    assert themes._lum(themes._rgb(c["bg"])) < 0.05 < themes._lum(themes._rgb(c["ink"]))
    assert c["bg"] == themes.surface_hex(theme["colors"], "light", "dark")["bg"]
    assert c["accent"] == theme["colors"]["accent"]
