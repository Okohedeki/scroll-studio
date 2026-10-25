"""The page every look is rendered from: a "kitchen sink" spec holding every block type and a `type` scene in each layout
(steps, buttons, fact lines), so a style or preset meets everything a spec can put on a page. Only content that needs no
GPU: blocks and `type` scenes build with no render, and the images are gradients the engine draws itself (no model)."""
from __future__ import annotations

import re
from typing import Any

BTN = {"label": "Start building", "href": "#cta"}


def _grad(colors: list[str], angle: float = 160) -> dict:
    # grain 0: the picture is the same pixels on every machine, so the screenshots are
    return {"gradient": {"colors": colors, "angle": angle, "grain": 0.0}, "size": [1280, 720]}


def spec(theme: dict) -> dict:
    """The site.yaml as a dict. `theme` is {"preset": ...} or {"style": ...}."""
    return {
        "name": "Kitchen Sink",
        "description": "Every block type and scene layout on one page.",
        "theme": theme,
        "nav": {"cta": BTN},
        "footer": {"left": "Footer left words", "right": "Footer right words"},
        "sections": [
            {"type": "hero", "id": "hero", "nav_label": "Top", "badge": {"text": "Now open", "href": "#intro", "tag": "New"},
             "title": "One <em>page</em> holds everything", "body": "Every block type appears once on this page.",
             "buttons": [dict(BTN, icon="arrow"), {"label": "Read more", "href": "#intro", "icon": "play", "look": "ghost"}],
             "image": _grad(["#1d2b64", "#f8cdda"]), "frame": "card",
             "rating": {"score": 4.6, "text": "from 1,400 readers"},
             "signup": {"action": "mailto:hello@example.com", "label": "Your email", "button": "Get the letter",
                        "note": "Signup note words."},
             "stats": [{"value": "61%", "label": "Hero figure one"}, {"value": "35k", "label": "Hero figure two"},
                       {"value": "9 days", "label": "Hero figure three"}],
             "logos": {"title": "Logo strip title", "items": [{"name": "Northwind"}, {"name": "Lumen", "href": "#"},
                                                              {"name": "Halden"}]}},
            {"type": "intro", "id": "intro", "nav_label": "Intro", "kicker": "Introduction", "title": "A short <em>introduction</em>",
             "body": "Paragraph text that explains the page in plain words."},
            {"type": "features", "id": "features", "nav_label": "Features", "kicker": "Features", "title": "Three features",
             "items": [{"title": "Alpha feature", "body": "Alpha body copy."}, {"title": "Beta feature", "body": "Beta body copy."},
                       {"title": "Gamma feature"}]},
            {"type": "stats", "id": "stats", "items": [{"value": "12", "label": "Twelve things"},
                                                       {"value": "3", "unit": "%", "label": "Three percent"},
                                                       {"value": "480", "label": "Four hundred eighty"}]},
            {"type": "stats", "id": "figures", "look": "divided", "items": [{"value": "36", "label": "Divided figure one"},
                                                                            {"value": "7", "unit": "x", "label": "Divided figure two"}]},
            {"type": "logos", "id": "logos", "title": "Partner logos", "items": [{"name": "Acme Works"}, {"name": "Globex"},
                                                                                {"name": "Initech", "href": "#"}]},
            {"type": "signup", "id": "signup", "kicker": "Letters", "title": "Stay in <em>touch</em>",
             "body": "Signup block body words.", "action": "https://example.com/subscribe", "button": "Subscribe now",
             "note": "Signup block note.", "rating": {"score": 4.9, "text": "from block readers"}},
            {"type": "timeline", "id": "timeline", "kicker": "History", "title": "How it went",
             "items": [{"when": "2024", "title": "Then we began", "body": "The first step."},
                       {"when": "2025", "title": "Later we grew"}, {"when": "2026", "title": "Now we ship"}]},
            {"type": "quote", "id": "quote", "text": "A quoted line worth reading.", "who": "Someone Careful"},
            {"type": "gallery", "id": "gallery", "kicker": "Work", "title": "A small gallery",
             "items": [{"title": "First tile", "href": "#", "kicker": "One", "body": "First tile body.", "image": _grad(["#134e5e", "#71b280"])},
                       {"title": "Second tile", "href": "#", "image": _grad(["#42275a", "#734b6d"], 20)},
                       {"title": "Third tile", "href": "#"}]},
            {"type": "product", "id": "product", "kicker": "Product", "title": "The product panel", "body": "Copy beside the product shot.",
             "tags": ["Tag one", "Tag two"], "buttons": [BTN], "note": "From a small price", "image": _grad(["#232526", "#414345"], 120)},
            {"type": "strip", "id": "strip", "kicker": "Strip", "title": "A sliding strip", "body": "Photos slide sideways.",
             "items": [{"image": _grad(["#ff9966", "#ff5e62"]), "caption": "Strip caption one"},
                       {"image": _grad(["#56ab2f", "#a8e063"], 40), "caption": "Strip caption two"},
                       {"image": _grad(["#4568dc", "#b06ab3"], 80)}, {"image": _grad(["#0f2027", "#2c5364"], 100)}]},
            {"type": "orbit", "id": "orbit", "kicker": "Orbit", "title": "Services in orbit", "body": "Around one centre.",
             "center": "Core", "items": [{"label": "Service x", "status": "Live"}, {"label": "Service y", "status": "Developing"},
                                         {"label": "Service z", "status": "Roadmap"}, {"label": "Service w"}]},
            {"type": "faq", "id": "faq", "title": "Questions", "items": [{"q": "Why one page?", "a": "Because every style must cope."},
                                                                           {"q": "Does it scroll?", "a": "It does, in every look."}]},
            {"type": "type", "id": "words", "nav_label": "Words", "mode": "reveal", "length": 3,
             "text": "Words light up in reading order as you scroll.",
             "steps": [{"kicker": "Overlay", "title": "Overlay <em>caption</em>", "body": "Overlay body words.",
                        "badge": {"text": "Caption badge", "icon": "dot"}, "button": dict(BTN, icon="external"), "at": [0.1, 0.5]},
                       {"block": "stats", "at": "right", "show": [0.5, 0.75],
                        "items": [{"value": "24", "label": "Stat step one"}, {"value": "7", "unit": "x", "label": "Stat step two"}]},
                       {"block": "quote", "at": {"x": 0.08, "y": 0.3, "w": 0.5}, "show": [0.75, 1],
                        "text": "A quote shown as a step.", "who": "Step Quoter"}]},
            {"type": "type", "id": "split", "layout": "split", "text": "Split text.",
             "steps": [{"title": "Split caption", "body": "Split body words.", "fact": "Split fact line"},
                       {"title": "Split second", "fact": "Second fact line"}]},
            {"type": "type", "id": "cards", "layout": "cards", "text": "Cards text.", "frame": "card",
             "steps": [{"title": "Cards caption", "body": "Cards body words.", "fact": "Cards fact line", "length": 0.8},
                       {"block": "features", "items": [{"title": "Card feature", "body": "A block as a card."}], "length": 0.8},
                       {"title": "Cards second", "button": {"label": "Card button", "href": "#"}, "length": 0.8}]},
            {"type": "cta", "id": "cta", "title": "Ready when you are", "button": BTN},
        ],
    }


# the text keys whose values the page must show as real HTML text
_TEXT_KEYS = {"title", "body", "kicker", "label", "q", "a", "text", "who", "when", "caption", "fact", "badge",
              "note", "center", "status", "unit", "left", "right", "tag", "button", "name"}
# a count-up shows its number only once it has finished: these are checked with reduced motion only
_NUMBERS = {"value"}


def norm(s: str) -> str:
    """Tags out, entities and whitespace collapsed, lower case: how the page text and the spec text are compared."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip().lower()


def words(node: Any = None, numbers: bool = True) -> list[str]:
    """Every string of the spec the page must show, normalised (the type scenes' `text`, which the page may set as
    one word per element, is checked word by word)."""
    out: list[str] = []

    def walk(n: Any, key: str = "") -> None:
        if isinstance(n, dict):
            for k, v in n.items():
                if k in ("theme", "href", "image", "id", "nav_label", "mode", "layout", "at", "action", "icon", "look"):
                    continue
                walk(v, k)
        elif isinstance(n, list):
            for v in n:
                walk(v, key)
        elif isinstance(n, str):
            if key in _TEXT_KEYS or (numbers and key in _NUMBERS) or key == "tags":
                out.append(norm(n))
    walk(spec({}) if node is None else node)
    return sorted(set(w for w in out if w))
