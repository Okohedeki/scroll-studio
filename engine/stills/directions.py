"""Art directions for product stills: where the product stands, the light, the palette and the mood.

A text backend (engine/router) writes them from the brief when one can run; otherwise, or when its answer can't be
read, a seeded local composer picks them from the vocabulary below. Either way the set is spread out: no two directions
share a setting or a light, so the candidates differ in kind, not just in seed.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from typing import Callable, Optional

HEX = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class Direction:
    id: str
    name: str
    setting: str
    light: str
    palette: tuple[str, str, str]      # backdrop, surface, accent
    mood: str
    source: str = "local"              # local, or the backend that wrote it

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Direction":
        return cls(d["id"], d["name"], d["setting"], d["light"], tuple(d["palette"]), d["mood"], d.get("source", "local"))


SETTINGS = [
    ("Stone ledge", "a pale limestone ledge against a plaster wall"),
    ("Kitchen counter", "a quiet kitchen counter of honed marble, a window out of frame"),
    ("Workbench", "a worn oak workbench with a few tools pushed aside"),
    ("Linen table", "a table under creased natural linen"),
    ("Terrazzo plinth", "a terrazzo plinth in an empty gallery room"),
    ("Garden step", "a mossy garden step in soft shade"),
    ("Studio sweep", "a seamless paper sweep in a photo studio"),
    ("Bathroom shelf", "a tiled bathroom shelf beside a small mirror"),
    ("Desk corner", "the corner of a tidy desk with a closed notebook"),
    ("Sand dune", "rippled sand at the edge of a dune"),
    ("Concrete floor", "polished concrete in a bright warehouse"),
    ("Water's edge", "flat wet rocks at the water's edge"),
    ("Bookshelf", "an open shelf among a few hardback books"),
    ("Café table", "a small round café table on a pavement"),
]

LIGHTS = [
    ("morning window light", "soft morning light from a window to the left, long gentle shadows"),
    ("hard noon sun", "hard midday sun, crisp short shadows, deep blue sky reflected"),
    ("overcast daylight", "even overcast daylight, almost no shadow"),
    ("golden hour", "low warm golden-hour sun raking across the surface"),
    ("studio softbox", "a large overhead softbox and a white bounce card"),
    ("dappled shade", "dappled light through leaves"),
    ("blue hour", "cool blue-hour dusk light with one warm lamp"),
    ("spotlit", "a single narrow spotlight on a dark room, falling off fast"),
    ("backlit haze", "backlit with a light haze, glowing edges"),
    ("candle warm", "warm low light from candles out of frame"),
]

MOODS = ["calm", "crisp", "warm", "playful", "quiet luxury", "fresh", "earthy", "graphic", "nostalgic", "bold"]

PALETTES = [
    ("Chalk and clay", ("#efe9e1", "#d9c7b2", "#b5653a")),
    ("Sea glass", ("#e3eeec", "#a9c9c2", "#2f6f73")),
    ("Ink and paper", ("#f4f2ee", "#cfcac2", "#1f2430")),
    ("Moss", ("#e4e6d8", "#9ea87c", "#3f4a2c")),
    ("Apricot", ("#fbe9d9", "#f2b98f", "#c4532d")),
    ("Midnight", ("#1c2233", "#2e3a55", "#e0b86a")),
    ("Rose dust", ("#f3e3e1", "#d9a9a5", "#7d3b48")),
    ("Citrus", ("#fbf6dc", "#f1d45c", "#2f7d4a")),
    ("Slate", ("#dfe3e8", "#8d98a6", "#2b3440")),
    ("Terracotta", ("#f1e0d2", "#c97d55", "#5a2c1d")),
    ("Lavender haze", ("#ece8f4", "#b9add6", "#4b3f72")),
    ("Charcoal", ("#2a2a2c", "#4a4a4f", "#d7d2c8")),
]


def local(n: int, seed: int, avoid: tuple[str, ...] = ()) -> list[Direction]:
    """n directions picked by `seed`, no setting or light repeated (nor any in `avoid`, the names already used)."""
    rng = random.Random(f"stills:{seed}")
    settings = [s for s in SETTINGS if s[0] not in avoid]
    if len(settings) < n:          # every setting used already: start the list again rather than repeat inside a set
        settings = SETTINGS[:]
    lights, palettes = LIGHTS[:], PALETTES[:]
    for xs in (settings, lights, palettes):
        rng.shuffle(xs)
    out = []
    for i in range(n):
        sname, setting = settings[i % len(settings)]
        lname, light = lights[i % len(lights)]
        pname, palette = palettes[i % len(palettes)]
        mood = MOODS[rng.randrange(len(MOODS))]
        out.append(Direction(f"d{seed}-{i + 1}", f"{sname}, {lname}", setting, light, palette, mood))
    return out


PROMPT = """Write {n} art directions for photographs of one product: {describe}.
Brief: {brief}
They must differ in kind: different settings, different light, different palettes{avoid}.
Answer with JSON only, a list of objects with these keys:
  name     a short name, 2 to 5 words
  setting  where the product stands, one phrase, no product in it
  light    the light, one phrase
  palette  three hex colours: backdrop, surface, accent
  mood     one or two words"""


def parse(text: str, n: int, seed: int, source: str) -> list[Direction]:
    """Directions from a text backend's answer; ValueError when it can't be read."""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("no JSON list in the answer")
    items = json.loads(m.group(0))
    out = []
    for i, it in enumerate(items[:n]):
        palette = tuple(c for c in (it.get("palette") or []) if isinstance(c, str) and HEX.fullmatch(c))
        if len(palette) != 3 or not all(isinstance(it.get(k), str) and it[k].strip() for k in ("name", "setting", "light")):
            raise ValueError(f"direction {i + 1} is incomplete")
        out.append(Direction(f"d{seed}-{i + 1}", it["name"].strip()[:60], it["setting"].strip()[:200],
                             it["light"].strip()[:200], palette, str(it.get("mood") or "calm").strip()[:40], source))
    if len(out) < n:
        raise ValueError(f"only {len(out)} of {n} directions")
    return out


def write(n: int, seed: int, describe: str, brief: str, policy=None, build=None, avoid: tuple[str, ...] = (),
          log: Callable[[str], None] = print) -> list[Direction]:
    """n directions: from a text backend when one can run, else (or on an unreadable answer) composed locally."""
    from ..router import NoBackend, TextJob, choose, route
    try:
        choose("text", policy)
    except NoBackend:
        return local(n, seed, avoid)
    note = f"; not like: {', '.join(avoid)}" if avoid else ""
    job = TextJob(PROMPT.format(n=n, describe=describe or "a product", brief=brief or "none given", avoid=note),
                  system="You are an art director for product photography. Be concrete and varied.", max_tokens=2000)
    try:
        r = route(job, None, policy, build=build, log=log)
        return parse(r.text or "", n, seed, r.backend)
    except Exception as e:     # a provider error or an answer that can't be read: the local composer still works
        log(f"  directions: the text backend's answer was not usable ({e}); composing them locally")
        return local(n, seed, avoid)


def named(directions: list[Direction]) -> tuple[str, ...]:
    return tuple(d.name.split(",")[0] for d in directions)


def by_id(directions: list[Direction], id: str) -> Optional[Direction]:
    return next((d for d in directions if d.id == id), None)
