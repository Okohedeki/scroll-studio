"""Imagery: one treatment for every prompt a site sends to the image and video models.

`imagery:` in site.yaml (picked from a direction by `studio directions`) names the medium, light, lens, mood and palette
of the shoot. The prompts in the spec stay about the subject; the treatment is added where the prompt is used:

  * `generate:` images (`resolve_image`), which covers beat frames, parallax steps, backdrops, hero images, theme art
  * a beat's clip prompt (the video model sees the same shoot)
  * a take's / shot's keyframes and segment prompts (`treat_shot`)

A named medium (`medium: risograph`, engine/medium.py) says its recipe's words with its inks named from the theme, and
its post-process runs over every generated still (engine/inputs.py). With `restyle` on (the default) the phrases in the original prompt that the treatment replaces are dropped first
('photorealistic', 'shot on a medium format camera', '35mm lens', 'golden hour'), so a prompt written for one look does
not argue with another. Nothing is added when the site has no `imagery:`, and cache keys only change when it is set.
"""
from __future__ import annotations

import re
from typing import Optional

import yaml

from .spec import Imagery

_CACHE: dict[str, tuple] = {}


def of(project) -> Optional[Imagery]:
    """The site's `imagery:` (read from site.yaml, re-read when the file changes), or None."""
    path = project.spec_path
    try:
        st = path.stat()
    except OSError:
        return None
    hit = _CACHE.get(str(path))
    sig = (st.st_mtime_ns, st.st_size)
    if hit and hit[0] == sig:
        return hit[1]
    im = None
    try:
        with open(path, encoding="utf-8") as f:
            raw = (yaml.safe_load(f) or {}).get("imagery")
        if raw:
            im = Imagery.model_validate(raw)
    except Exception:       # an invalid spec is reported by the build itself
        im = None
    _CACHE[str(path)] = (sig, im)
    return im


# ---------------------------------------------------------------- dropping what the treatment replaces

MEDIUM = re.compile(
    r"^(?:photoreal\w*|hyper-?realistic|cinematic(?: still| photograph| lighting| grade)?|film still|ultra[- ]?detailed|"
    r"highly detailed|intricate details?|[48]k|hdr|sharp focus|award[- ]winning|professional photography|stock photo|"
    r"(?:editorial|travel|architectural|lifestyle|magazine|documentary|product|fashion)(?: \w+)? photography|"
    r"(?:editorial |magazine |travel )?\w*\s?magazine(?: style)?|high-end [\w ]+ (?:advertising )?style|"
    r"(?:shot|taken|captured|photographed) (?:on|with|by) .*|.*\b(?:dslr|medium format|large format|film camera|camera)\b.*|"
    r"(?:\w+ )?(?:photo|photograph|render|illustration)(?:-?realistic)?(?: style)?)$", re.I)
LIGHT = re.compile(r"\b(?:sunlight|sunrise|sunset|golden hour|blue hour|twilight|dusk|dawn|lighting|backlit|rim light|"
                   r"(?:soft |warm |cool |natural |window |diffused |morning |afternoon |evening |ambient |pale |low |"
                   r"harsh |hard )+light|light|shadows?|glow)\b", re.I)
LENS = re.compile(r"(?:\b\d{2,3}\s?mm\b|\blens\b|\bf/\d|shallow depth of field|\bbokeh\b|wide[- ]angle|telephoto|\bmacro\b|"
                  r"depth of field)", re.I)
INLINE_LIGHT = re.compile(r"\s+(?:at|during|in|under|in the) (?:the )?(?:golden hour|blue hour|magic hour|sunrise|sunset|dusk|dawn|twilight)\b", re.I)
LEAD = re.compile(r"^(?:[A-Za-z-]+ ){0,2}(?:photograph|photo|photography|image|picture|render|illustration|painting) of ", re.I)


def _clauses(text: str) -> list[str]:
    return [c.strip() for c in re.split(r",\s+|;\s+|\.\s+", text.strip().rstrip(".")) if c.strip()]


def restyle(prompt: str, im: Imagery) -> str:
    """The prompt without the medium, lens and light phrases that `im` sets itself."""
    out = []
    for i, c in enumerate(_clauses(prompt)):
        words = len(c.split())
        if MEDIUM.match(c):
            continue
        if i == 0:
            c2 = LEAD.sub("", c)
            if c2 != c:
                c = c2[:1].upper() + c2[1:]
        if im.lens and LENS.search(c) and words <= 7:
            continue
        if im.light:
            if LIGHT.search(c) and words <= 6:
                continue
            c = INLINE_LIGHT.sub("", c)
        out.append(c)
    return ", ".join(out) if out else prompt.strip()


def phrase(im: Optional[Imagery], prompt: str, video: bool = False, pal: Optional[dict] = None,
           calm: Optional[str] = None, plain: bool = False) -> str:
    """`prompt` shot the way `im` says. video: the clip prompt (no lens: the camera moves). A named medium
    (engine/medium.py) says its recipe's words, its inks named from `pal`. calm: the side kept quiet for a headline.
    plain: leave the named medium out (an image with `medium: none`)."""
    from . import medium as med
    prompt = (prompt or "").strip()
    named = med.recipe(im.medium) if im is not None else None
    if im is None or (plain and named):
        head = ""
    else:
        head = med.prompt_head(named.name, pal) if named else im.medium.strip().rstrip(".")
    calm_words = med.CALM_WORDS[calm] if calm and not video else ""
    if not prompt:
        return head
    if head and prompt.lower().startswith(head.lower()):      # already treated
        return prompt
    core = restyle(prompt, im) if im is not None and im.restyle else prompt
    core = core.rstrip(". ")
    parts = [calm_words] + ([im.light, None if video else im.lens, im.palette, im.mood] if im is not None else [])
    tail = ". ".join(p.strip().rstrip(".") for p in parts if p)
    return (f"{head}. " if head else "") + f"{core}." + (f" {tail}." if tail else "")


def look(project, medium: Optional[str] = None) -> tuple[Optional[Imagery], Optional[str]]:
    """(the imagery an image is phrased with, the named medium it is drawn in or None): the site's `imagery:`, with an
    image's own `medium:` over it ('none' leaves the site's named medium out)."""
    from . import medium as med
    im = of(project)
    if medium and medium != "none":
        im = im.model_copy(update={"medium": medium}) if im is not None else Imagery(medium=medium)
    named = med.recipe(im.medium) if im is not None and medium != "none" else None
    return im, named.name if named else None


def treat(project, prompt: str, video: bool = False, medium: Optional[str] = None, calm: Optional[str] = None) -> str:
    """The prompt as it is sent to the model for this project: unchanged unless the site sets `imagery:` (or the image
    its own `medium:` or `calm:`)."""
    if not prompt:
        return prompt
    im, named = look(project, medium)
    if im is None and not calm:
        return prompt
    pal = None
    if named:
        from . import medium as med
        pal = med.site_palette(project, named, im)
    return phrase(im, prompt, video, pal, calm, plain=medium == "none")


def treat_shot(project, shot: dict) -> dict:
    """A take's / shot's keyframe and segment prompts treated (a copy; the spec's dicts are left alone)."""
    im, named = look(project)
    if im is None:
        return shot
    pal = None
    if named:
        from . import medium as med
        pal = med.site_palette(project, named, im)

    def ph(prompt: str, video: bool = False) -> str:
        return phrase(im, prompt, video, pal)
    shot = dict(shot)
    kf = shot.get("keyframes")
    if kf and kf.get("frames"):
        kf = dict(kf)
        kf["frames"] = [dict(f, prompt=ph(f["prompt"])) if f.get("prompt") else f for f in kf["frames"]]
        shot["keyframes"] = kf
    ltx = shot.get("ltx")
    if ltx and (ltx.get("segments") or ltx.get("prompt")):
        ltx = dict(ltx)
        if ltx.get("segments"):
            ltx["segments"] = [dict(s, prompt=ph(s["prompt"], video=True)) if s.get("prompt") else s
                               for s in ltx["segments"]]
        if ltx.get("prompt"):
            ltx["prompt"] = ph(ltx["prompt"], video=True)
        shot["ltx"] = ltx
    return shot
