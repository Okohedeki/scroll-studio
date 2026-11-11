"""Reading the brief: what the site is about and how it wants to feel, from its own spec.

Input is the site (name, description, section copy), the optional `directions:` block (brief, moods, constraints) and the
look the site has today. Output is a `Brief`: weighted domains (hospitality, tech, food ...) and moods (calm, bold ...)
that the writer matches schools against. Plain keyword matching on the owner's words: no model, nothing sent anywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..spec import Directions, Site
from . import vocab

COPY_KEYS = ("title", "kicker", "body", "tag", "caption", "label", "text", "badge", "hint", "note", "fact", "q", "a", "tags",
             "words", "description", "who", "when", "left", "right")
SKIP = {"prompt", "generate", "keyframes", "ltx", "take", "data", "state", "hud", "theme", "image", "video", "backdrop",
        "credit", "callouts", "imagery", "directions", "product", "trailer", "nav", "footer", "pages", "loader", "wan"}


def plain(text) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(text or ""))).strip()


def _collect(node, out: list, depth: int = 0) -> None:
    if depth > 8:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            if k in SKIP:
                continue
            if k in COPY_KEYS and isinstance(v, str):
                out.append(plain(v))
            elif k in COPY_KEYS and isinstance(v, list) and all(isinstance(x, str) for x in v):
                out.extend(plain(x) for x in v)
            elif isinstance(v, (dict, list)):
                _collect(v, out, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _collect(v, out, depth + 1)


def copy_of(raw: dict) -> list[str]:
    """Every piece of visible copy in the spec, in page order (names and headlines first)."""
    out = [plain(raw.get("name")), plain(raw.get("description"))]
    _collect(raw.get("sections") or [], out)
    return [t for t in out if t]


@dataclass
class Brief:
    name: str
    description: str
    brief: str = ""
    domains: dict = field(default_factory=dict)        # domain -> 0..1
    moods: dict = field(default_factory=dict)          # mood -> 0..1
    notes: list = field(default_factory=list)          # how the brief was read, for the board
    cfg: Directions = field(default_factory=Directions)
    current: dict = field(default_factory=dict)        # the look the site has today
    places: bool = False                               # the page has scenes set in a place (films, relit views ...)

    def public(self) -> dict:
        return {"name": self.name, "description": self.description, "brief": self.brief,
                "domains": {k: round(v, 2) for k, v in sorted(self.domains.items(), key=lambda x: -x[1]) if v},
                "moods": {k: round(v, 2) for k, v in sorted(self.moods.items(), key=lambda x: -x[1]) if v},
                "notes": self.notes}


def _score_words(text: str, table: dict) -> dict:
    words = re.findall(r"[a-z][a-z-]+", text.lower())
    out = {}
    for key, listing in table.items():
        vocab_words = set(listing.split())
        n = 0
        for w in words:
            if w in vocab_words or (len(w) > 4 and any(w.startswith(v) and len(v) >= 4 for v in vocab_words)):
                n += 1
        if n:
            out[key] = n
    return out


def current_look(site: Site) -> dict:
    from ..compile import themes
    try:
        t = themes.resolve(site.theme)
    except Exception:
        t = {"colors": {}, "fonts": {}, "mode": "dark"}
    return {"preset": site.theme.preset, "style": site.theme.style, "mode": t["mode"], "colors": t["colors"],
            "fonts": t["fonts"], "imagery": site.imagery.model_dump(mode="json") if site.imagery else None}


PLACE_SCENES = {"film", "light", "parallax", "diorama", "splat", "map"}

PRESET_DOMAIN = {"night": "tech", "brass": "luxury", "paper": "art", "lab": "science", "cosmos": "space", "studio": "retail",
                 "dusk": "hospitality", "ink": "events", "blueprint": "architecture", "clinic": "health"}


def read(site: Site, raw: dict, cfg: Optional[Directions] = None) -> Brief:
    cfg = cfg or site.directions or Directions()
    copy = copy_of(raw)
    own = " ".join(copy)
    brief_text = plain(cfg.brief)
    dom = _score_words(own, vocab.DOMAIN_WORDS)
    dom_brief = _score_words(brief_text, vocab.DOMAIN_WORDS)
    for k, n in dom_brief.items():                    # the owner's own brief counts three times
        dom[k] = dom.get(k, 0) + 3 * n
    preset = PRESET_DOMAIN.get(site.theme.preset)
    if preset and not site.theme.style:
        dom[preset] = dom.get(preset, 0) + 1.0        # the preset the author chose says something about the subject
    top = max(dom.values()) if dom else 0
    domains = {k: v / top for k, v in dom.items()} if top else {}
    mood_raw = _score_words(brief_text + " " + " ".join(cfg.moods), vocab.MOOD_WORDS)
    for m in cfg.moods:                               # a mood named outright counts fully
        m = m.strip().lower()
        if m in vocab.MOOD_WORDS:
            mood_raw[m] = mood_raw.get(m, 0) + 2
    top = max(mood_raw.values()) if mood_raw else 0
    moods = {k: v / top for k, v in mood_raw.items()} if top else {}
    for d, w in domains.items():                      # what the subject usually wants, at half weight
        for m in vocab.DOMAIN_MOODS.get(d, "").split():
            moods[m] = moods.get(m, 0) + 0.5 * w * (0.5 if top else 1.0)
    notes = []
    if domains:
        notes.append("reads as " + ", ".join(k for k, _ in sorted(domains.items(), key=lambda x: -x[1])[:3]))
    else:
        notes.append("no strong subject in the copy: directions are chosen for range, not fit")
    if moods:
        notes.append("leans " + ", ".join(k for k, _ in sorted(moods.items(), key=lambda x: -x[1])[:4]))
    places = any(getattr(sec, "type", None) in PLACE_SCENES for sec in site.sections)
    if places:
        notes.append("its pictures are places")
    return Brief(plain(site.name), plain(site.description), brief_text, domains, moods, notes, cfg, current_look(site),
                 places)
