"""Writing a site from a brief (issue #191): an outline, then each section against a real pattern of its type.

Every call is a routed TextJob (engine/router), so a local model does the writing unless the project's `models:` asks
for a provider. Each answer is parsed as JSON, checked by the spec's own models and by a few rules of craft, and sent
back with the problems when it fails, a few times at most.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional

import yaml

from . import bank as bank_mod, catalog

Log = Callable[[str], None]

SYSTEM = """You are the lead designer and copywriter at a studio that builds scroll-driven websites with DesignAI, an
engine where each section of a page is a scene the visitor scrolls through (films, live 3D worlds, depth photos lit by
the pointer, code fly-throughs) or a plain block (features, stats, quotes, a call to action).

How you write:
- Concrete and specific to this brief: name the actual thing, how it works, who it is for. Use the brief's own facts.
- Short sentences. Headlines of at most eight words; wrap the phrase that should carry the accent in <em>...</em>.
- No filler and no stock phrases: never write unlock, seamless, elevate, revolutionize, cutting-edge, game-changer,
  empower, robust, leverage, supercharge, next-level, world-class, best-in-class, effortless, or exclamation marks.
- Never name real companies, real people or real products as customers, partners, quotes or logos; invent plausible ones.
- Image and film prompts describe one concrete picture: its subject, setting, composition and light. Leave out the
  medium, style and lens (photoreal, illustration, 3D render, 50mm): the page's art direction sets those for every
  picture at once, so every prompt must work in any medium. No text, logos or screens with writing in pictures.
- Numbers only from the brief, or plainly countable product facts (one decorator, zero lost jobs). Never invent usage
  figures, uptime, customer counts or awards.

Answer with one JSON object and nothing else."""

BANNED = ("unlock", "seamless", "elevate", "revolutioniz", "cutting-edge", "game-changer", "game changer", "empower",
          "robust", "leverage", "supercharge", "next-level", "world-class", "best-in-class", "effortless", "with ease",
          "peace of mind", "hassle-free", "lightning-fast", "blazing")
COPY_KEYS = ("title", "kicker", "body", "text", "label", "caption", "q", "a", "fact", "badge", "note", "who", "hint")


class WriteError(RuntimeError):
    pass


def parse_json(text: str) -> Any:
    """The first JSON object in a model's answer (it may wrap it in prose or a code fence)."""
    text = text or ""
    start = text.find("{")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            return obj
        except ValueError:
            start = text.find("{", start + 1)
    raise WriteError("the answer held no JSON object")


def copy_strings(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in COPY_KEYS and isinstance(v, str):
                out.append(re.sub(r"<[^>]+>", "", v))
            elif isinstance(v, (dict, list)):
                out += copy_strings(v)
    elif isinstance(node, list):
        for v in node:
            out += copy_strings(v)
    return out


def _grams(text: str, n: int = 6) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


PROMPT_KEYS = ("generate", "prompt", "motion", "scene")
STYLE_WORDS = re.compile(r"\b(photo-?real(istic)?|cinematic|illustration|illustrated|3d render|rendered|render|"
                         r"anime|watercolou?r|oil painting|digital art|\d{2,3}\s?mm|lens|hdr|8k|4k|unreal engine|octane)\b",
                         re.I)
WRITING = re.compile(r"[\"“”][^\"“”]{2,40}[\"“”]|'[A-Z][^']{1,40}'|"
                     r"\b(labell?ed|that says|lettering|text on|written on|logo)\b", re.I)


def prompts_in(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in PROMPT_KEYS and isinstance(v, str):
                out.append(v)
            elif isinstance(v, (dict, list)):
                out += prompts_in(v)
    elif isinstance(node, list):
        for v in node:
            out += prompts_in(v)
    return out


FIGURE_KEYS = ("value", "unit", "when")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def invented_figures(section: dict, brief: str) -> list[str]:
    """Figures in the copy that the brief never gave: invented uptime, customer counts and dates read as lies."""
    if section.get("type") == "code":            # code and its output are the product's own, not claims
        return []
    texts = copy_strings(section)

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in FIGURE_KEYS and isinstance(v, (str, int, float)) and not isinstance(v, bool):
                    texts.append(str(v))
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(section)
    given = set(NUMBER.findall(brief or ""))
    return sorted({n for t in texts for n in NUMBER.findall(re.sub(r"<[^>]+>", "", t))} - given)


def craft_problems(section: dict, pattern: Optional[dict]) -> list[str]:
    """What a section breaks besides the schema: files it cannot have, stock phrases, copy lifted from its pattern,
    and picture prompts that ask for writing or set their own style over the page's art direction."""
    problems = []
    for prompt in prompts_in(section):
        style = STYLE_WORDS.search(prompt)
        if style:
            problems.append(f"a picture prompt sets its own style ({style.group(0)!r}); describe only what is in the "
                            "picture, the art direction sets the style")
            break
    for prompt in prompts_in(section):
        words = WRITING.search(prompt)
        if words:
            problems.append(f"a picture prompt asks for writing ({words.group(0)!r}); pictures hold no text or logos")
            break
    files = bank_mod.files_in(section)
    if files:
        problems.append(f"it names files ({', '.join(files[:3])}); a generated site has none: make every picture with "
                        "{\"generate\": \"<prompt>\"}")
    copy = " ".join(copy_strings(section)).lower()
    used = [w for w in BANNED if w in copy]
    if used:
        problems.append(f"it uses stock phrases ({', '.join(used)}); say the specific thing instead")
    if "!" in copy:
        problems.append("it uses exclamation marks")
    if pattern is not None:
        lifted = _grams(" ".join(copy_strings(pattern))) & _grams(" ".join(copy_strings(section)))
        if lifted:
            problems.append("it repeats the pattern's own words (" + " ".join(next(iter(lifted))) + "); write new copy "
                            "for this brief")
    return problems


def page_problems(sections: list[dict]) -> dict[str, list[str]]:
    """{section id: problems} for references between sections the spec cannot check one section at a time."""
    out: dict[str, list[str]] = {}
    seen: list[str] = []
    for s in sections:
        bg = s.get("background")
        if isinstance(bg, str) and bg.startswith("scene:") and bg[6:] not in seen:
            out.setdefault(s["id"], []).append(f"background {bg!r} names no scene above it; leave background out")
        seen.append(s["id"])
    return out


def plan_problems(project) -> dict[str, list[str]]:
    """{section id: why the build planner cannot plan it}: the engine's own checks, with nothing rendered."""
    from ..plan import plan_build
    try:
        plan = plan_build(project)
    except Exception as e:                     # the whole page fails to plan: blame nobody in particular
        return {"": [f"{type(e).__name__}: {e}"]}
    return {sid: [re.sub(r"^\w+Error: (\[[^\]]+\] )?", "", msg)] for sid, msg in plan.errors.items()}


PATH_KEYS = {"path", "file"}
WORDS_KEYS = set(COPY_KEYS) | {"nav_label", "prompt", "todo", "logo", "model", "name", "role", "value", "unit", "quote",
                               "subtitle", "headline", "cue"}


def skeleton(node: Any, key: str = "", parent: str = "") -> Any:
    """A pattern with its words taken out: the structure, field names and settings stay, every piece of copy, picture
    prompt, path and code becomes a placeholder, so the model learns the shape and writes the content new."""
    if isinstance(node, dict):
        return {k: skeleton(v, k, key) for k, v in node.items()}
    if isinstance(node, list):
        return [skeleton(v, key, parent) for v in node]
    if not isinstance(node, str):
        return node
    if key == "prompt" and parent == "terminal":
        return "<the task, as a developer would type it>"
    if key in PROMPT_KEYS:
        return "<describe one picture: subject, setting, composition, light>"
    if key == "code":
        return f"<about {max(1, node.count(chr(10)))} lines of real code or output for this product>"
    if key in PATH_KEYS:
        return "<a path or command>"
    if key in WORDS_KEYS:
        n = len(re.sub(r"<[^>]+>", "", node).split())
        return f"<new words, about {n}>" if n > 1 else "<a word>"
    return node


def chain_film(section: dict) -> dict:
    """A film is one place: every beat after the first starts on the last frame of the beat before it, so the cuts
    between beats never jump (a beat that already names its own start image is left alone only if it chains)."""
    beats = section.get("beats") if section.get("type") == "film" else None
    if not isinstance(beats, list):
        return section
    for prev, beat in zip(beats, beats[1:]):
        if not (isinstance(prev, dict) and isinstance(beat, dict) and prev.get("id")):
            continue
        image = beat.get("image")
        if isinstance(image, dict) and "beat_frame" in image:
            continue
        beat["image"] = {"beat_frame": {"beat": prev["id"], "at": "last"}}
    for beat in beats:                           # a separately generated end frame would morph into the next start
        if isinstance(beat, dict) and isinstance(beat.get("end_image"), dict) and "beat_frame" not in beat["end_image"]:
            beat.pop("end_image")
    return section


IMAGE_KEYS = {"file", "generate", "gradient", "product", "scene", "size", "seed", "crop", "edit", "beat_frame", "match",
              "credit", "cinemagraph"}


def repair(node: Any) -> Any:
    """Fix the slips a model makes the same way every time: a `generate` prompt set on a card or a step instead of in
    its `image`, and picture fields given as a bare prompt string."""
    if isinstance(node, list):
        return [repair(v) for v in node]
    if not isinstance(node, dict):
        return node
    node = {k: repair(v) for k, v in node.items()}
    if "generate" in node and set(node) - IMAGE_KEYS and "image" not in node:
        image = {"generate": node.pop("generate")}
        for k in ("size", "seed"):
            if k in node and not isinstance(node[k], dict):
                image[k] = node.pop(k)
        node["image"] = image
    return node


def prune(section: dict) -> Optional[dict]:
    """The section with optional fields of the wrong shape left out, if that is all that stops it validating."""
    import copy

    from pydantic import TypeAdapter, ValidationError

    from ..spec import Section
    check = TypeAdapter(Section)
    sec = copy.deepcopy(section)
    for _ in range(40):                                          # one wrong field per pass
        try:
            check.validate_python(sec)
            return sec
        except ValidationError as e:
            errs = [err for err in e.errors() if err["type"] != "missing"]
            if not errs:
                return None
            loc = list(errs[0]["loc"][1:])
            while loc and not isinstance(loc[-1], str):          # never drop list items: drop the field holding them
                loc.pop()
            if not loc or loc in (["type"], ["id"]):
                return None
            parent = sec
            for k in loc[:-1]:
                parent = parent[k] if isinstance(parent, (dict, list)) else None
                if parent is None:
                    return None
            if not isinstance(parent, dict) or loc[-1] not in parent:
                return None
            trial = copy.deepcopy(sec)
            node = trial
            for k in loc[:-1]:
                node = node[k]
            del node[loc[-1]]
            try:
                check.validate_python(trial)
            except ValidationError as e2:
                if any(err["type"] == "missing" and list(err["loc"][1:]) == loc for err in e2.errors()):
                    return None                                  # a required field: dropping it is no fix
            sec = trial
    return None


def schema_problems(section: dict) -> list[str]:
    from pydantic import TypeAdapter, ValidationError

    from ..spec import Section
    try:
        TypeAdapter(Section).validate_python(section)
    except ValidationError as e:
        out = []
        for err in e.errors()[:8]:
            where = ".".join(str(x) for x in err["loc"][1:]) or "(section)"
            out.append(f"{where}: {err['msg']}")
        return out
    return []


def _ask(prompt: str, seed: int, policy, build, log: Log, temperature: float = 0.7, max_tokens: int = 8000,
         attempts: int = 3) -> str:
    """One text job; a server error (a local model still loading, a dropped connection) is retried after a pause."""
    import time

    from ..router import TextJob, route
    job = TextJob(prompt, system=SYSTEM, max_tokens=max_tokens, temperature=temperature, seed=seed, json=True)
    for n in range(attempts):
        try:
            return route(job, policy=policy, build=build, log=log).text or ""
        except Exception as e:                  # httpx errors, provider errors: the model, not the request, failed
            if n == attempts - 1:
                raise WriteError(f"the text model failed: {type(e).__name__}: {e}") from None
            log(f"  text model: {type(e).__name__}; trying again in {10 * (n + 1)} s")
            time.sleep(10 * (n + 1))
    return ""


def outline(brief: str, entries: list[dict], want: tuple[str, ...], count: int, seed: int, policy=None, build=None,
            log: Log = print, tries: int = 3) -> dict:
    """{name, description, audience, promise, voice, sections: [{id, type, purpose, headline, interactive}]}."""
    import random
    entries = list(entries)
    random.Random(seed).shuffle(entries)          # the list's order is not a page order; never let it become one
    menu = "\n".join(f"- {e['type']}{' (scene)' if e['scene'] else ''}"
                     f"{' [interactive: ' + ', '.join(e['interactive']) + ']' if e['interactive'] else ''}: {e['about']}"
                     for e in entries)
    offer = catalog.offering(want, entries)
    must = "; ".join(f"{k}: one of {', '.join(v)}" for k, v in offer.items() if v)
    ask = f"""Brief:
{brief}

First find the story: who the page is for, the one thing it must prove, and one concrete picture or metaphor that
belongs to this subject and no other (if it would fit any company, it is not the picture). Every scene on the page is
set in that picture's world. Then plan a landing page of {count} sections that tells the story as an arc, each section
with one job (show, prove, explain, reassure, ask). Section types you can use, in no particular order:
{menu}

Rules:
- Open on a scene, never on a plain block. End on a cta.
- Include a section for each of these interactive kinds ({must}).
- Prefer scenes for the story and blocks for facts; never two blocks of the same type in a row.
- Use each type at most twice.
- Order the sections as the story needs; the list above is not an order.

Return:
{{"name": "the brand name", "description": "one sentence for search results",
  "audience": "who it is for", "promise": "the one thing the page must prove", "voice": "how it sounds, in five words",
  "image": "the one concrete picture every scene is set in, in a sentence",
  "sections": [{{"id": "a-short-id-naming-what-it-shows", "type": "<type>", "purpose": "what this section does for the story",
                "headline": "its headline", "interactive": null}}]}}"""
    types = {e["type"] for e in entries}
    problems: list[str] = []
    for attempt in range(tries):
        prompt = ask if not problems else ask + "\n\nYour last plan had these problems; fix them:\n- " + "\n- ".join(problems)
        try:
            plan = parse_json(_ask(prompt, seed + attempt, policy, build, log))
        except WriteError as e:
            problems = [str(e)]
            continue
        secs = plan.get("sections") or []
        scenes = {e["type"] for e in entries if e["scene"]}
        tidy_ids(secs)
        open_on_a_scene(secs, scenes)
        problems = []
        if len(str(plan.get("image") or "").split()) < 5:
            problems.append("give the page its image: one concrete picture from this subject, in a sentence")
        for s in secs:
            if s.get("type") not in types:
                problems.append(f"{s.get('type')!r} is not one of the section types listed")
        if secs and secs[-1].get("type") != "cta":
            problems.append("the last section must be a cta")
        if secs and secs[0].get("type") not in scenes:
            problems.append("the first section must be a scene")
        assign_interactive(secs, offer)
        for k, allowed in offer.items():
            if allowed and not any(s.get("interactive") == k for s in secs):
                problems.append(f"no section can show the {k} kind: add a section of type {' or '.join(allowed)}")
        if not 3 <= len(secs) <= count + 2:
            problems.append(f"plan {count} sections, not {len(secs)}")
        if not problems:
            return plan
        log(f"  outline: try {attempt + 1}: " + "; ".join(problems))
    raise WriteError("the outline still breaks the rules after %d tries: %s" % (tries, "; ".join(problems)))


TYPE_HINT = {
    "film": "A film is one continuous camera journey through one place: every beat continues where the last one ended "
            "(the same place, the same light, the camera moving on), never a cut to an unrelated scene. 3 to 5 beats.",
    "code": "Every step pinned to a file must name a path that is in files; files of kind run hold a command and its "
            "output. Leave the terminal out unless the pattern needs it.",
    "scene3d": "Levels use only the presets the pattern shows or these: cell-field, cell, nucleus, helix, galaxy, "
               "star-system, planet, network, lattice, particles.",
}



def tidy_ids(secs: list[dict]) -> None:
    """Section ids become page anchors and storyboard names. The engine keeps them tidy itself (a model asked to keeps
    slipping): lowercase kebab case, without the type in front, never just a type and a number, each used once."""
    seen: set[str] = set()
    for i, s in enumerate(secs):
        kind = str(s.get("type") or "section")
        sid = re.sub(r"[^a-z0-9]+", "-", str(s.get("id") or "").lower()).strip("-")
        if kind != "cta" and sid.startswith(kind + "-"):
            sid = sid[len(kind) + 1:]
        if not sid or not sid[0].isalpha() or re.fullmatch(rf"({re.escape(kind)}|section)-?\d+", sid):
            words = re.findall(r"[a-z]+", re.sub(r"<[^>]+>", "", str(s.get("headline") or "")).lower())
            sid = "-".join(w for w in words if len(w) > 2)[:32].strip("-") or kind
        base, n = sid, 2
        while sid in seen:
            sid, n = f"{base}-{n}", n + 1
        seen.add(sid)
        s["id"] = sid


def open_on_a_scene(secs: list[dict], scenes: set[str]) -> None:
    """A page opens on a scene: when the model put a block first, the first scene moves up to open it."""
    if secs and secs[0].get("type") not in scenes:
        first = next((i for i, s in enumerate(secs) if s.get("type") in scenes), None)
        if first is not None:
            secs.insert(0, secs.pop(first))


def assign_interactive(secs: list[dict], offer: dict[str, list[str]]) -> None:
    """Mark which section shows each interactive kind: the model's own marks where they fit, else the first free
    section of a type that can show it (the model chooses the types; the engine keeps the bookkeeping)."""
    for s in secs:
        k = s.get("interactive")
        if k not in offer or s.get("type") not in offer.get(k, []):
            s["interactive"] = None
    for k, allowed in sorted(offer.items(), key=lambda kv: len(kv[1])):     # the kinds with fewest homes first
        if any(s.get("interactive") == k for s in secs):
            continue
        free = next((s for s in secs if s.get("type") in allowed and not s.get("interactive")), None)
        if free is not None:
            free["interactive"] = k


INTERACTIVE_HINT = {
    "pointer": 'Give it a pointer the visitor plays with: "pointer": {"mode": "light"} (a torch over a dark picture) '
               'or {"mode": "lens"} (a circle showing the picture\'s colour through a muted page).',
    "3d": "It is live 3D the visitor moves through; keep its places, levels or stops tied to the copy.",
    "code": "Show the product's real usage: files a developer would touch, with short realistic code.",
    "film": "Write the film as a few beats, each a concrete camera move through one continuous place.",
}


def section(brief: str, plan: dict, item: dict, pattern: dict, seed: int, policy=None, build=None, log: Log = print,
            tries: int = 3, known: Optional[list[str]] = None) -> tuple[Optional[dict], list[str]]:
    """One section of the plan, written against its pattern; (section, problems left) and None when it never passed."""
    others = "\n".join(f"- {s.get('id')}: {s.get('type')}, {s.get('headline')}" for s in plan.get("sections", []))
    hint = " ".join(x for x in (TYPE_HINT.get(item.get("type"), ""), INTERACTIVE_HINT.get(item.get("interactive") or "", ""))
                    if x)
    ask = f"""Brief:
{brief}

The page: {plan.get('name')}, for {plan.get('audience')}. Its promise: {plan.get('promise')}. Voice: {plan.get('voice')}.
Sections, in order:
{others}

Write the section "{item.get('id')}" ({item.get('type')}): {item.get('purpose')}. Headline idea: {item.get('headline')}.
{hint}

The page's image, which every picture and film on it belongs to: {plan.get('image')}

Here is the shape of a real {item.get('type')} section, with its words taken out, as a pattern for field names and
structure (fill every <placeholder> with new content for this brief):
{json.dumps(skeleton(pattern), ensure_ascii=False)}

Return one JSON object for the new section, with "type": "{item.get('type')}" and "id": "{item.get('id')}". Keep the
pattern's structure and settings (lengths, modes, strengths) where they suit; rewrite every piece of copy and every
image or film prompt for this brief. Make every picture with {{"generate": "<prompt>"}}, never a file."""
    problems: list[str] = list(known or [])
    for attempt in range(tries):
        prompt = ask if not problems else ask + "\n\nYour last answer had these problems; fix them:\n- " + "\n- ".join(problems)
        try:
            sec = parse_json(_ask(prompt, seed + attempt, policy, build, log))
        except WriteError as e:
            problems = [str(e)]
            continue
        sec = chain_film(repair(sec))
        sec["type"], sec["id"] = item.get("type"), item.get("id")
        schema = schema_problems(sec)
        if schema:
            pruned = prune(sec)
            if pruned is not None:
                sec, schema = pruned, []
        craft = craft_problems(sec, pattern)
        lost = [k for k in ("steps", "items", "beats") if (pattern or {}).get(k) and not sec.get(k)]
        if lost:
            schema = schema + [f"it has no {k}; write them as the pattern does" for k in lost]
        figures = invented_figures(sec, brief)
        if figures:                              # a hard rule, unlike the craft notes: never ship an invented figure
            schema = schema + [f"it gives figures the brief does not ({', '.join(figures[:4])}); use only the brief's "
                               "facts, in words, or leave the figure out"]
        if not schema and (not craft or attempt == tries - 1):
            if craft:
                log(f"  {item.get('id')}: kept with notes: " + "; ".join(craft[:2]))
            return sec, []
        problems = schema + craft
        log(f"  {item.get('id')}: try {attempt + 1}: " + "; ".join(problems[:3]))
    return None, problems


def assemble(plan: dict, sections: list[dict]) -> dict:
    """The site: its sections, a nav to the named ones and the call to action."""
    links = [{"label": s.get("nav_label") or _short(s), "href": f"#{s['id']}"} for s in sections[1:-1]
             if s.get("type") not in ("cta", "logos", "quote")][:3]
    cta = next((s for s in reversed(sections) if s.get("type") == "cta"), None)
    nav: dict = {"links": links}
    if cta and isinstance(cta.get("button"), dict) and cta["button"].get("label"):
        nav["cta"] = {"label": cta["button"]["label"], "href": f"#{cta['id']}"}
    return {"name": plan.get("name") or "Untitled", "description": plan.get("description") or "", "nav": nav,
            "sections": sections}


def _short(s: dict) -> str:
    title = re.sub(r"<[^>]+>", "", str(s.get("title") or s.get("kicker") or s["id"]))
    words = title.split()
    return " ".join(words[:3]).rstrip(".,:;") if words else s["id"]


def dump(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)
