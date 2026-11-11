"""`studio import <url>`: a new project from a product page.

The page is read the way `studio remake` reads one (its robots.txt is obeyed, Playwright draws it when it can). From
it come the product's facts: schema.org Product data where the page has it, Open Graph tags, then the page's own
text. Its product pictures are saved into inputs/. A text backend turns the facts into a product profile (what it
is, the main benefit, the outcome a buyer wants, how it looks, who it is for, proof points, objections), keeping to
what the page says; with none, a plainer profile is filled from the facts. The project's outputs (stills, ads,
listing, concepts, video, video ads) start from that profile.

The words and pictures belong to the page's owner: import your own products, or ones you have permission to use."""
from __future__ import annotations

import html as htmlmod
import io
import json
import re
import shutil
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse

from .project import BuildError, Project, child

MAX_PICTURES = 8
MAX_TEXT = 12_000
NOTICE = ("The product's words and pictures come from {host} and belong to its owner. Import your own products, or "
          "ones you have permission to use.")

PROMPT = """Here is what a product page says. Build a product profile for writing ads.

{facts}

Page text:
{text}

Answer with JSON only:
{{"name": "...", "what": "what it is, in a few plain words", "category": "...", "main_benefit": "...",
  "outcome": "what the buyer wants to feel or get", "look": "how it looks: colours, materials, shape",
  "audience": "who buys it", "features": ["..."], "proof": ["reviews, ratings, numbers the page gives"],
  "objections": ["doubts a buyer may have"], "price": "as the page gives it, or empty"}}
Only use what the page supports. Never invent specifications, ratings, numbers or claims; leave a field empty or a
list short instead."""


# ---------------------------------------------------------------- facts from the markup

def _ld_blocks(html: str) -> list:
    out = []
    for m in re.finditer(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html, re.S | re.I):
        raw = htmlmod.unescape(m.group(1)).strip()
        try:
            out.append(json.loads(raw))
        except ValueError:
            try:                                    # a trailing comma or two is common
                out.append(json.loads(re.sub(r",\s*([}\]])", r"\1", raw)))
            except ValueError:
                continue
    return out


def _walk(node):
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement", "hasVariant"):
            if key in node:
                yield from _walk(node[key])


def _is_product(d: dict) -> bool:
    t = d.get("@type")
    return t == "Product" or t == "ProductGroup" or (isinstance(t, list) and ("Product" in t or "ProductGroup" in t))


def _images(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [v.get("url") or v.get("contentUrl") or ""]
    if isinstance(v, list):
        return [u for x in v for u in _images(x)]
    return []


def _text(v) -> str:
    if isinstance(v, dict):
        return str(v.get("name") or "")
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", str(v or ""))).strip()


def _meta(html: str) -> dict:
    out: dict = {}
    for m in re.finditer(r"<meta\b[^>]*>", html, re.I):
        tag = m.group(0)
        key = re.search(r"(?:property|name|itemprop)=[\"']([^\"']+)[\"']", tag, re.I)
        val = re.search(r"content=[\"']([^\"']*)[\"']", tag, re.I)
        if key and val:
            out.setdefault(key.group(1).lower(), htmlmod.unescape(val.group(1)).strip())
    return out


def facts(html: str, url: str) -> dict:
    """What the markup states about the product: name, description, brand, price, rating, pictures."""
    got: dict = {"name": "", "description": "", "brand": "", "price": "", "currency": "", "rating": "",
                 "reviews": "", "images": [], "sku": ""}
    for d in (d for block in _ld_blocks(html) for d in _walk(block) if _is_product(d)):
        got["name"] = got["name"] or _text(d.get("name"))
        got["description"] = got["description"] or _text(d.get("description"))
        got["brand"] = got["brand"] or _text(d.get("brand"))
        got["sku"] = got["sku"] or _text(d.get("sku"))
        got["images"] += _images(d.get("image"))
        offers = d.get("offers")
        for o in (offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []):
            price = o.get("price") or o.get("lowPrice")
            if price and not got["price"]:
                got["price"], got["currency"] = str(price), str(o.get("priceCurrency") or "")
        r = d.get("aggregateRating")
        if isinstance(r, dict) and not got["rating"]:
            got["rating"], got["reviews"] = str(r.get("ratingValue") or ""), str(r.get("reviewCount") or r.get("ratingCount") or "")
    m = _meta(html)
    got["name"] = got["name"] or m.get("og:title") or m.get("twitter:title", "")
    got["description"] = got["description"] or m.get("og:description") or m.get("description", "")
    got["price"] = got["price"] or m.get("product:price:amount") or m.get("og:price:amount", "")
    got["currency"] = got["currency"] or m.get("product:price:currency") or m.get("og:price:currency", "")
    got["brand"] = got["brand"] or m.get("product:brand") or m.get("og:site_name", "")
    got["images"] += [m[k] for k in ("og:image", "og:image:secure_url", "twitter:image") if m.get(k)]
    seen, pics = set(), []
    for u in got["images"]:
        u = urljoin(url, u.strip()) if u else ""
        if u.startswith(("http://", "https://")) and u not in seen:
            seen.add(u)
            pics.append(u)
    got["images"] = pics
    return got


def page_text(html: str, url: str) -> tuple[str, list[str]]:
    """The page's readable text (headings, paragraphs, list items) and its larger pictures, through remake's parser."""
    from .remake import parse_page
    page = parse_page(html, url)
    lines = [x for x in (page.title, page.headline, page.subhead, page.description) if x]
    for seg in page.segments:
        for ev in seg:
            if ev.kind in ("h", "text", "li", "pair", "qa", "quote") and ev.text:
                lines.append(ev.text)
    text = "\n".join(dict.fromkeys(lines))[:MAX_TEXT]
    pics = [im.url for _, im in page.images() if not im.junk]
    return text, pics


# ---------------------------------------------------------------- the profile

def plain_profile(f: dict, text: str) -> dict:
    """A profile from the facts alone, for when no text backend can run: marked as a draft."""
    first = next((ln for ln in text.splitlines() if len(ln) > 40), "")
    what = (f.get("name") or "").strip()
    return {"name": what, "what": what, "category": "", "main_benefit": (f.get("description") or first)[:200],
            "outcome": "", "look": "", "audience": "", "features": [], "objections": [],
            "proof": [f"rated {f['rating']} from {f['reviews']} reviews"] if f.get("rating") and f.get("reviews") else [],
            "price": f"{f.get('currency', '')} {f['price']}".strip() if f.get("price") else "", "draft": True}


def parse_profile(answer: str) -> dict:
    m = re.search(r"\{.*\}", answer or "", re.S)
    if not m:
        raise ValueError("no JSON object in the answer")
    d = json.loads(m.group(0))
    if not str(d.get("name") or d.get("what") or "").strip():
        raise ValueError("the profile has no name")
    out = {}
    for k in ("name", "what", "category", "main_benefit", "outcome", "look", "audience", "price"):
        out[k] = str(d.get(k) or "").strip()[:400]
    for k in ("features", "proof", "objections"):
        v = d.get(k) or []
        out[k] = [str(x).strip()[:200] for x in v if str(x).strip()][:10] if isinstance(v, list) else []
    return out


def profile(f: dict, text: str, models=None, build: Optional[Path] = None, log: Callable = print) -> dict:
    from .router import NoBackend, TextJob, choose, route
    keep = {k: v for k, v in f.items() if k != "images" and v}
    try:
        choose("text", models)
        r = route(TextJob(PROMPT.format(facts=json.dumps(keep, ensure_ascii=False), text=text),
                          system="You read product pages carefully and only state what they support.",
                          max_tokens=1500, json=True), None, models, build=build, log=log)
        got = parse_profile(r.text or "")
        got["source"] = r.backend
        return got
    except NoBackend:
        log("  import: no text backend can run here, so the profile is a draft from the page's own facts")
    except Exception as e:        # an unusable answer: the plain profile still gives a start
        log(f"  import: the text backend's profile was not usable ({e}); writing a draft from the page's facts")
    got = plain_profile(f, text)
    got["source"] = "facts"
    return got


def to_markdown(p: dict, url: str) -> str:
    out = [f"# {p.get('name') or 'Product'}", "", f"From {url}", ""]
    if p.get("draft"):
        out += ["> Draft from the page's own facts: no text backend could run. Fill in what is missing.", ""]
    for k, label in (("what", "What it is"), ("main_benefit", "Main benefit"), ("outcome", "What the buyer wants"),
                     ("look", "Look"), ("audience", "Who it is for"), ("price", "Price")):
        if p.get(k):
            out.append(f"- **{label}:** {p[k]}")
    for k, label in (("features", "Features"), ("proof", "Proof"), ("objections", "Objections to answer")):
        if p.get(k):
            out += ["", f"## {label}", ""] + [f"- {x}" for x in p[k]]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- pictures

def save_pictures(urls: list[str], project: Project, robots, warnings: list, log: Callable = print) -> list[str]:
    import requests
    from PIL import Image

    from .remake import MAX_IMAGE_BYTES, MAX_SIDE, MAX_TOTAL_BYTES, PHOTO, UA
    files: list[str] = []
    total = 0
    for u in urls:
        if len(files) >= MAX_PICTURES:
            break
        if not robots.allowed(u):
            warnings.append(f"robots.txt does not allow {u[:80]}; left out")
            continue
        try:
            with requests.get(u, headers=UA, timeout=20, stream=True) as r:
                r.raise_for_status()
                if not r.headers.get("content-type", "image/").startswith("image/"):
                    continue
                data = r.raw.read(MAX_IMAGE_BYTES + 1, decode_content=True)
            if len(data) > MAX_IMAGE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
                warnings.append(f"{u[:80]} is too large; left out")
                continue
            pic = Image.open(io.BytesIO(data))
            if getattr(pic, "is_animated", False):
                pic.seek(0)
            w, h = pic.size
            if w * h > 60_000_000 or max(w, h) < PHOTO[1] or min(w, h) < 200:
                continue
            pic = pic.convert("RGBA" if "A" in pic.getbands() else "RGB")
            if max(pic.size) > MAX_SIDE:
                k = MAX_SIDE / max(pic.size)
                pic = pic.resize((round(pic.width * k), round(pic.height * k)), Image.LANCZOS)
            ext = ".png" if pic.mode == "RGBA" else ".jpg"
            name = f"product-{len(files) + 1}{ext}"
            pic.save(project.inputs / name, "PNG" if ext == ".png" else "JPEG", quality=92)
            total += len(data)
            files.append(f"inputs/{name}")
            log(f"  picture inputs/{name} ({pic.width}x{pic.height})")
        except Exception as e:     # an unreachable or broken picture is skipped, never fatal
            log(f"  note: picture {u[:70]} not used ({e.__class__.__name__})")
    return files


# ---------------------------------------------------------------- the project

def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:40].strip("-") or "product"


def project_doc(name: str, url: str, prof: dict, pictures: list[str], languages: list[str]) -> dict:
    what = prof.get("what") or prof.get("name") or "the product"
    brief = ". ".join(x for x in (prof.get("main_benefit"), prof.get("outcome")) if x)
    doc: dict = {"name": name, "description": prof.get("name") or what, "brief": brief[:400], "source": url,
                 "languages": languages, "outputs": {}}
    out = doc["outputs"]
    if pictures:
        out["stills"] = {"photo": pictures[0], "describe": what[:120]}
        out["ads"] = {"sizes": ["1x1", "4x5", "9x16"], "cta": "Shop now"}
        out["video"] = {"voiceover": "listing"}
        out["ugc"] = {}
    out["listing"] = {}
    out["concepts"] = {}
    return doc


def import_product(url: str, name: Optional[str] = None, languages: Optional[list[str]] = None,
                   projects: Optional[Path] = None, browser: bool = True, log: Callable = print) -> dict:
    """Read the product page at `url` and write a new project from it. Returns what was made."""
    import yaml

    from .config import settings
    from .project_spec import ProjectSpec
    from .remake import Refused, Robots, read_page
    if not re.match(r"^https?://[^/\s]+", url or ""):
        raise BuildError("give the product page as an http(s) address, e.g. https://shop.example/products/mug")
    robots = Robots()
    if not robots.allowed(url):
        raise Refused(f"{urlparse(url).netloc}'s robots.txt does not allow {url} to be read, so it is not imported")
    log(f"reading {url}")
    html, final = read_page(url, browser, log)
    if final != url and not robots.allowed(final):
        raise Refused(f"the page moved to {final}, which its robots.txt does not allow to be read")
    f = facts(html, final)
    text, page_pics = page_text(html, final)
    if not (f["name"] or text.strip()):
        raise BuildError(f"{final} gave nothing to read (a page drawn by JavaScript reads best with Playwright's "
                         "Chromium installed)")
    name = name or slug(f["name"] or urlparse(final).path.rsplit("/", 1)[-1])
    root = child(projects or Path(settings()["projects"]), name, "project name")
    if root.exists():
        raise BuildError(f"{root} already exists; pick another name with --name")
    warnings: list[str] = []
    (root / "inputs").mkdir(parents=True)
    try:
        project = Project(root)
        pictures = save_pictures(list(dict.fromkeys(f["images"] + page_pics)), project, robots, warnings, log)
        if not pictures:
            warnings.append("no product picture could be saved: add one to inputs/ and set outputs.stills.photo")
        prof = profile(f, text, build=project.build, log=log)
        prof["facts"] = {k: v for k, v in f.items() if k != "images"}
        folder = root / "profile"
        folder.mkdir()
        (folder / "profile.json").write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
        (folder / "profile.md").write_text(to_markdown(prof, final), encoding="utf-8")
        doc = project_doc(name, final, prof, pictures, languages or ["en"])
        ProjectSpec.model_validate(doc)                     # never write an invalid project
        (root / "project.yaml").write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    steps = ["stills", "concepts", "ads", "listing", "ugc"] if pictures else ["concepts", "listing"]
    return {"name": name, "path": str(root), "url": final, "profile": prof, "pictures": pictures,
            "warnings": warnings, "notice": NOTICE.format(host=urlparse(final).netloc),
            "next": [f"studio {s} {name}" for s in steps]}


def load(project: Project) -> dict:
    """The project's product profile (profile/profile.json), or {} when it was not imported."""
    try:
        return json.loads((project.root / "profile" / "profile.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
