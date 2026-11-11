"""reveal: colour that comes into the film where the camera looks, driven by scroll.

The film is rendered once, in full colour. This stage makes the masks that let the page show it as black and white (or
dimmed, or blurred, or tinted) everywhere except in the regions the spec names, and colour in through each region as the
section scrolls (the browser draws every frame with a WebGL shader: runtime/src/players/reveal.ts).

Per region, cached by its own key:
  reveal_ground_<id>  the region's prompt -> boxes on the `at` frame (Florence-2, through ComfyUI), or the spec's box
  reveal_track_<id>   SAM 2.1 video predictor seeded with those boxes/points on that frame, tracked forward and backward
                      through the whole film (soft masks, 960x540, uint8 .npz)
Then, for the whole section:
  reveal_pack         the regions' masks, feathered, packed up to four to a grayscale video (a 2x2 atlas of 960x544
                      tiles) with the film's own frame rate, frame count and GOP, so a mask frame scrubs with its film
                      frame; a half-size copy for phones; a poster and end frame with the reveal applied.

`composite` and `amounts_at` are the CPU twins of the shader and of the runtime's key easing: the poster, the storyboard
and the tests use them, so what the page does and what the engine shows agree.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import numpy as np

from .project import BuildContext, BuildError, ffmpeg, file_key, probe
from .spec import FilmScene, Reveal, RevealRegion

TILE = (960, 544)         # one mask in the atlas: the 16:9 film frame, a little taller to stay macroblock-aligned
WORK = (960, 540)         # what SAM 2.1 and Florence-2 see: the film cropped to 16:9 at this size
VERSION = 1               # bump when masks would come out differently for the same inputs
CROP169 = "crop='min(iw,ih*16/9)':'min(ih,iw*9/16)'"      # the same crop film.encode applies

TRACKERS = {"large": "sam2.1_hiera_large.safetensors", "base_plus": "sam2.1_hiera_base_plus.safetensors"}
FLORENCE = "microsoft/Florence-2-large"


# ---------------------------------------------------------------- the key easing (runtime twin: players/reveal.ts)

def region_keys(rv: Reveal) -> list[dict]:
    """The spec's keys, or one region after another over 0.2-0.9 of the section when it gives none."""
    if rv.keys:
        return sorted(rv.keys, key=lambda k: k["at"])
    n = len(rv.regions)
    out = []
    for i, r in enumerate(rv.regions):
        a, b = 0.2 + 0.7 * i / n, 0.2 + 0.7 * (i + 1) / n
        out += [{"at": round(a, 4), r.id: 0.0}, {"at": round(b - 0.02, 4), r.id: 1.0}]
    return sorted(out, key=lambda k: k["at"])


def amounts_at(keys: list[dict], ids: list[str], p: float, ease: str = "smooth", reduced: bool = False) -> dict[str, float]:
    """How revealed each region is (0-1) at section progress p. A region's keys are the keys that name it; before the
    first it holds that key's value, after the last it holds that one, between two it eases (smoothstep or linear).
    `reduced` (prefers-reduced-motion): no easing, each region jumps to a key's value as soon as that key is reached."""
    out = {}
    for rid in ids:
        ks = [(k["at"], k[rid]) for k in keys if rid in k]
        if not ks:
            out[rid] = 0.0
            continue
        if p <= ks[0][0]:
            out[rid] = ks[0][1]
            continue
        v = ks[-1][1]
        for (a0, v0), (a1, v1) in zip(ks, ks[1:]):
            if p < a1:
                if reduced:
                    v = v1 if v1 != v0 else v0      # a change has started: jump to where it ends
                else:
                    t = (p - a0) / max(a1 - a0, 1e-9)
                    t = t * t * (3 - 2 * t) if ease == "smooth" else t
                    v = v0 + (v1 - v0) * t
                break
        out[rid] = float(v)
    return out


# ---------------------------------------------------------------- the CPU compositor (shader twin)

def _hex(c: str) -> np.ndarray:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return np.array([int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


def base_treatment(rgb: np.ndarray, base: str) -> np.ndarray:
    """The un-revealed look of an RGB float image (0-1): mono, dim, blur, or a duotone through a tint colour."""
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    if base == "mono":
        return np.repeat(lum[..., None], 3, axis=2)
    if base == "dim":
        grey = np.repeat(lum[..., None], 3, axis=2)
        return (rgb * 0.45 + grey * 0.55) * 0.55
    if base == "blur":
        import cv2
        return cv2.GaussianBlur(rgb, (0, 0), max(rgb.shape[1] / 160, 2.0))
    tint = _hex(base)
    l = lum[..., None]
    lo = tint * (l * 2)
    hi = tint + (1 - tint) * (l * 2 - 1)
    return np.where(l < 0.5, lo, hi)


def composite(rgb8: np.ndarray, masks: dict[str, np.ndarray], amounts: dict[str, float], base: str,
              strength: float = 1.0) -> np.ndarray:
    """uint8 RGB frame + {region: HxW 0-1 mask at the frame's size} + amounts -> uint8 RGB, base look everywhere and
    colour where mask x amount (the several regions combine as a union)."""
    f = rgb8.astype(np.float32) / 255
    b = base_treatment(f, base)
    k = np.zeros(f.shape[:2], dtype=np.float32)
    for rid, m in masks.items():
        k = 1 - (1 - k) * (1 - np.clip(m, 0, 1) * amounts.get(rid, 0.0))
    k = (k * strength)[..., None]
    return np.clip((b * (1 - k) + f * k) * 255 + 0.5, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- frames of the film

def beat_spans(sec: FilmScene, durs: list[float], fade: float) -> dict[str, tuple[float, float]]:
    from .scenes.film import beat_spans as spans
    return spans(sec, durs, fade)


def film_frame(sec: FilmScene, at, nframes: int, fps: float, spans: Optional[dict]) -> int:
    """The frame of the joined film a region's `at` names."""
    if at.frame is not None:
        f = at.frame
    elif at.seconds is not None:
        f = round(at.seconds * fps)
    elif at.beat:
        if not spans or at.beat not in spans:
            raise BuildError(f"reveal: `at.beat: {at.beat}` needs a beats film with a beat of that id")
        a, b = spans[at.beat]
        f = round((a + (b - a) * at.t) * (nframes - 1))
    else:
        f = round(at.t * (nframes - 1))
    return max(0, min(nframes - 1, int(f)))


def spans_of(sec: FilmScene, ctx: BuildContext) -> Optional[dict]:
    """Each beat's span of the joined film (0-1), from the beat clips on disk (as pin_steps times the captions)."""
    if not sec.beats:
        return None
    durs = []
    for b in sec.beats:
        clip = ctx.work / "beats" / b.id / "clip.mp4"
        if not clip.exists():
            return None
        durs.append(float(probe(clip)["duration"]))
    from .scenes.film import join_fades
    return beat_spans(sec, durs, join_fades(sec, durs))


# ---------------------------------------------------------------- choosing what the prompt found

def split_owner(prompt: str) -> tuple[str, Optional[str]]:
    """"the woman's hand" -> ("hand", "the woman"); "the shoes of the woman and the man" -> ("shoes", "the woman and the man");
    anything else -> (prompt, None)."""
    p = prompt.strip().rstrip(".")
    m = re.match(r"^(?:the |a |an |her |his )?(?P<own>[\w\s-]+?)'s (?P<y>.+)$", p, re.I)
    if m:
        return m["y"].strip(), "the " + m["own"].strip()
    m = re.match(r"^(?:the |a |an )?(?P<y>[\w\s-]+?) of (?P<own>.+)$", p, re.I)
    if m:
        return m["y"].strip(), m["own"].strip()
    return p, None


def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inside(b, owners) -> float:
    """The share of box b that lies inside any of the owner boxes."""
    if not owners:
        return 1.0
    best = 0.0
    for o in owners:
        w = max(0.0, min(b[2], o[2]) - max(b[0], o[0]))
        h = max(0.0, min(b[3], o[3]) - max(b[1], o[1]))
        best = max(best, w * h / max(_area(b), 1e-9))
    return best


def choose_boxes(found: list[list[float]], pick, owners: Optional[list[list[float]]] = None) -> list[list[float]]:
    """Which of the boxes the search found to follow: those inside the owner boxes (if any are), then `pick`."""
    boxes = [b for b in found if _area(b) < 0.9]         # a box around the whole picture is the search giving up
    boxes = boxes or list(found)
    if owners:
        inside = [b for b in boxes if _inside(b, owners) >= 0.6]
        boxes = inside or boxes
    if not boxes:
        return []
    if isinstance(pick, int):
        return [boxes[min(pick, len(boxes) - 1)]]
    key = {"first": None, "largest": lambda b: -_area(b), "smallest": lambda b: _area(b), "left": lambda b: b[0] + b[2],
           "right": lambda b: -(b[0] + b[2]), "top": lambda b: b[1] + b[3], "bottom": lambda b: -(b[1] + b[3]),
           "center": lambda b: abs(b[0] + b[2] - 1) + abs(b[1] + b[3] - 1)}
    if pick == "all":
        return boxes
    return [sorted(boxes, key=key[pick])[0]] if key[pick] else [boxes[0]]


# ---------------------------------------------------------------- ComfyUI graphs

NODES = ("SSRevealTrack", "SSRevealGround", "DownloadAndLoadSAM2Model", "DownloadAndLoadFlorence2Model")


def preflight(ctx: Optional[BuildContext] = None) -> None:
    """Fail before a film renders if ComfyUI is up but lacks the reveal nodes (a down ComfyUI is left to the stages that
    need it: cached masks build without it)."""
    from .fidelity import is_planning
    from .backends import comfy
    if is_planning() or not comfy.alive():
        return
    _need_nodes(ctx.log if ctx else print)


def _need_nodes(log) -> None:
    from .backends import comfy
    missing = []
    for n in NODES:
        try:
            comfy._req(f"/object_info/{n}")
        except Exception:
            missing.append(n)
    if missing:
        raise BuildError("reveal needs ComfyUI custom nodes it can't see: " + ", ".join(missing) + ". Run `studio setup-comfy` "
                         "(installs ComfyUI-segment-anything-2, ComfyUI-Florence2 and DesignAI's own nodes), restart "
                         "ComfyUI when its queue is empty, then build again. `studio doctor` lists what is missing.")


def ground_graph(image_name: str, text: str, task: str = "caption_to_phrase_grounding") -> dict:
    return {
        "img": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "fl": {"class_type": "DownloadAndLoadFlorence2Model", "inputs": {"model": FLORENCE, "precision": "fp16"}},
        "gr": {"class_type": "SSRevealGround", "inputs": {"image": ["img", 0], "florence2_model": ["fl", 0], "text": text, "task": task}},
    }


def track_graph(video_name: str, frame: int, prompts: list[dict], tracker: str, prefix: str, start: int, end: int) -> dict:
    return {
        "vid": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "comp": {"class_type": "GetVideoComponents", "inputs": {"video": ["vid", 0]}},
        "sam": {"class_type": "DownloadAndLoadSAM2Model", "inputs": {"model": TRACKERS[tracker], "segmentor": "video",
                                                                       "device": "cuda", "precision": "fp16"}},
        "tr": {"class_type": "SSRevealTrack", "inputs": {"sam2_model": ["sam", 0], "images": ["comp", 0], "frame_index": frame,
                                                          "prompts": json.dumps(prompts), "start": start, "end": end}},
        "img": {"class_type": "MaskToImage", "inputs": {"mask": ["tr", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["img", 0], "filename_prefix": prefix}},
    }


def ground(frame_png: Path, text: str, task: str = "caption_to_phrase_grounding") -> list[dict]:
    """Florence-2 on one frame: [{"box": [x0, y0, x1, y1] (0-1), "label": str}]."""
    from .backends import comfy
    out = comfy.run_outputs(ground_graph(comfy.upload(str(frame_png)), text, task), poll=2)
    return json.loads(out["gr"]["text"][0])["boxes"]


def find_boxes(png: Path, prompt: str, pick, within: Optional[str] = None, log=print) -> tuple[list, list, Optional[list]]:
    """The boxes a region's prompt names on one image: Florence-2 grounding, narrowed to the matches inside the owner
    ("the girl's shoes" -> shoes inside the girl; or `within`), then `pick`. Returns (chosen boxes, every match's box,
    the owner boxes or None). `reveal` and the image editor's `region` both find things this way."""
    what, owner = split_owner(prompt)
    owner = within or owner
    matches = ground(png, what if owner else prompt)
    owners = [m["box"] for m in ground(png, owner)] if owner else None
    if owner and not owners:
        log(f"    note: '{owner}' was not found on the frame; keeping every '{what}'")
    return choose_boxes([m["box"] for m in matches], pick, owners), [m["box"] for m in matches], owners


# ---------------------------------------------------------------- stages

def _work_clip(src: Path, ctx: BuildContext) -> Path:
    """The film at working size, cropped like the encode: the one clip every region is found on and tracked through."""
    dst = ctx.work / "reveal" / "work.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)

    def run():
        ffmpeg("-i", src, "-vf", f"{CROP169},scale={WORK[0]}:{WORK[1]}:flags=area", "-an", "-c:v", "libx264", "-crf", "10",
               "-preset", "fast", "-pix_fmt", "yuv420p", "-g", "12", dst, log=ctx.log)
    ctx.stage("reveal_work", {"src": file_key(src), "size": WORK, "v": VERSION}, [dst], run)
    return dst


def _frame_png(clip: Path, n: int, dst: Path) -> Path:
    ffmpeg("-i", clip, "-vf", f"select=eq(n\\,{n})", "-frames:v", "1", dst)
    if not dst.exists():
        raise BuildError(f"could not read frame {n} of {clip}")
    return dst


def region_prompts(rg: RevealRegion, found: list[list[float]]) -> list[dict]:
    """SAM's prompts for a region: one object per box (the union is the region), the spec's points ride along."""
    pos = [list(p) for p in rg.points]
    neg = [list(p) for p in rg.negative_points]
    items = [{"box": b} for b in found]
    if not items:
        items = [{}]
    for it in items:
        if neg:
            it["points"], it["labels"] = [*neg], [0] * len(neg)
    for p in pos:           # a positive point goes with the box that holds it, else it is its own object
        host = next((it for it in items if it.get("box") and it["box"][0] <= p[0] <= it["box"][2] and it["box"][1] <= p[1] <= it["box"][3]), None)
        if host is None and items == [{}]:
            host = items[0]
        if host is None:
            items.append({"points": [p], "labels": [1]})
        else:
            host.setdefault("points", []).append(p)
            host.setdefault("labels", []).append(1)
    return [it for it in items if it]


def shots_of(sec: FilmScene, ctx: BuildContext, rv: Reveal, clip: Path, nframes: int, fps: float,
             spans: Optional[dict]) -> list[tuple[int, int]]:
    """The film's shots as inclusive frame ranges: a beats film's beats (cut in the middle of each crossfade), else
    `reveal.cuts`, else the cuts ffmpeg's scene detection finds in the working clip."""
    cuts: list[int] = []
    if rv.cuts:
        cuts = [round(t * fps) for t in rv.cuts]
    elif spans:
        order = [spans[b.id] for b in sec.beats]
        cuts = [round((x[1] + y[0]) / 2 * (nframes - 1)) for x, y in zip(order, order[1:])]
    else:
        out = ctx.work / "reveal" / "cuts.json"

        def find():
            import subprocess
            from .config import settings
            r = subprocess.run([settings()["ffmpeg"], "-hide_banner", "-i", str(clip), "-vf", "select='gt(scene,0.4)',showinfo",
                                "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            ts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
            out.write_text(json.dumps([round(t * fps) for t in ts]))
        ctx.stage("reveal_cuts", {"clip": file_key(clip), "v": VERSION}, [out], find)
        cuts = json.loads(out.read_text()) if out.exists() else []
    cuts = sorted({c for c in cuts if 0 < c < nframes})
    edges = [0, *cuts, nframes]
    return [(a, b - 1) for a, b in zip(edges, edges[1:])]


def track_region(sec: FilmScene, ctx: BuildContext, rv: Reveal, rg: RevealRegion, src: Path, clip: Path, nframes: int,
                 fps: float, spans: Optional[dict], shots: list[tuple[int, int]]) -> list[Path]:
    """Stages reveal_ground_<id> and reveal_track_<id> for each of the region's `at` frames (a seed); each is tracked
    inside the shot that holds it. Returns the masks files (uint8, frames x 540 x 960; empty outside the seed's shot)."""
    from .backends import comfy
    rdir = ctx.work / "reveal" / rg.id
    rdir.mkdir(parents=True, exist_ok=True)
    files = []
    seeds = rg.seeds
    for k, at in enumerate(seeds):
        sfx = f"_{k}" if len(seeds) > 1 else ""
        frame = film_frame(sec, at, nframes, fps, spans)
        a, b = next(s for s in shots if s[0] <= frame <= s[1])
        gj = rdir / f"ground{sfx}.json"
        if rg.box:
            found = [list(rg.box)]
            gj.write_text(json.dumps({"frame": frame, "boxes": found, "source": "box"}))
        elif rg.prompt:
            gkey = {"clip": file_key(clip), "frame": frame, "prompt": rg.prompt, "pick": rg.pick, "within": rg.within, "v": VERSION}

            def find(frame=frame, gj=gj, sfx=sfx, at=at):
                png = _frame_png(clip, frame, rdir / f"frame{sfx}.png")
                boxes, found_all, owners = find_boxes(png, rg.prompt, rg.pick, rg.within, ctx.log)
                if not boxes:
                    raise BuildError(f"reveal region '{rg.id}': nothing matching \"{rg.prompt}\" on frame {frame}"
                                     f"{'' if at.beat is None else ' of beat ' + at.beat}. Move `at`, reword the prompt, "
                                     f"or give `box` / `points`.")
                gj.write_text(json.dumps({"frame": frame, "boxes": boxes, "found": found_all,
                                          "owner": owners, "source": "prompt"}))
                _draw_boxes(png, boxes, rdir / f"ground{sfx}.jpg")
            ctx.stage(f"reveal_ground_{rg.id}{sfx}", gkey, [gj], find)
            found = json.loads(gj.read_text())["boxes"] if gj.exists() else []
        else:
            found = []
        prompts = region_prompts(rg, found)
        out = rdir / f"masks{sfx}.npz"
        key = {"clip": file_key(clip), "frame": frame, "shot": [a, b], "prompts": prompts, "tracker": rv.tracker, "v": VERSION}

        def run(frame=frame, a=a, b=b, prompts=prompts, out=out, sfx=sfx):
            _need_nodes(ctx.log)
            name = comfy.upload(str(clip))
            images = comfy.run(track_graph(name, frame, prompts, rv.tracker, f"studio/reveal_{ctx.section_id}_{rg.id}", a, b), poll=2)
            got = Path(comfy.fetch(images, str(rdir / f"png{sfx}")))
            from PIL import Image
            part = np.stack([np.asarray(Image.open(p).convert("L")) for p in sorted(got.glob("*.png"))])
            if len(part) != b - a + 1:
                raise BuildError(f"reveal region '{rg.id}': {len(part)} masks for the {b - a + 1} frames of its shot")
            arr = np.zeros((nframes, *part.shape[1:]), dtype=np.uint8)
            arr[a:b + 1] = part
            np.savez_compressed(out, masks=arr)
            import shutil
            shutil.rmtree(got, ignore_errors=True)
        ctx.stage(f"reveal_track_{rg.id}{sfx}", key, [out], run)
        files.append(out)
    return files


def _draw_boxes(png: Path, boxes, dst: Path) -> None:
    from PIL import Image, ImageDraw
    im = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(im)
    for b in boxes:
        d.rectangle([b[0] * im.width, b[1] * im.height, b[2] * im.width, b[3] * im.height], outline=(255, 40, 80), width=3)
    im.save(dst, quality=88)


# ---------------------------------------------------------------- packing

def _grow(m: np.ndarray, px: float) -> np.ndarray:
    if not px:
        return m
    import cv2
    r = max(1, int(round(abs(px))))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.dilate(m, k) if px > 0 else cv2.erode(m, k)


def tile_masks(masks: np.ndarray, feather: float, grow: int, tile: tuple[int, int]) -> np.ndarray:
    """(frames, 540, 960) uint8 -> (frames, tile h, tile w) uint8, grown, feathered (`feather` px of the 1920-wide film)."""
    import cv2
    out = np.empty((len(masks), tile[1], tile[0]), dtype=np.uint8)
    sigma = feather / 2 * (tile[0] / 1920) / 1.0
    for i, m in enumerate(masks):
        m = cv2.resize(m, tile, interpolation=cv2.INTER_LINEAR)
        m = _grow(m, grow * tile[0] / 1920)
        if sigma > 0.2:
            m = cv2.GaussianBlur(m, (0, 0), sigma)
        out[i] = m
    return out


def atlas_layout(n: int) -> tuple[int, int]:
    """Columns and rows of the tile grid for n regions (up to four per video)."""
    return (1, 1) if n == 1 else (2, 1) if n == 2 else (2, 2)


def encode_atlas(tiles: list[np.ndarray], fps: float, gop: int, dst: Path, crf: int = 14, log=None) -> tuple[int, int]:
    """Pack the regions' tiles (each frames x h x w) into one grayscale H.264 video; returns the grid (cols, rows)."""
    import subprocess
    from .config import settings
    cols, rows = atlas_layout(len(tiles))
    th, tw = tiles[0].shape[1:]
    n = len(tiles[0])
    W, H = tw * cols, th * rows
    cmd = [settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
           "-r", f"{fps:.6f}", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0", "-an", "-movflags", "+faststart", str(dst)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frame = np.zeros((H, W), dtype=np.uint8)
    for i in range(n):
        for k, t in enumerate(tiles):
            r, c = divmod(k, cols)
            frame[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t[i]
        p.stdin.write(frame.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise BuildError("ffmpeg failed to encode the mask video")
    return cols, rows


def _union(parts: list[np.ndarray]) -> np.ndarray:
    out = parts[0]
    for q in parts[1:]:
        out = np.maximum(out, q)
    return out


def pack(sec: FilmScene, ctx: BuildContext, rv: Reveal, region_files: dict[str, list[Path]], src: Path, fps: float, gop: int) -> dict:
    """Stage reveal_pack: mask videos (desktop + phone), poster and end frame with the reveal applied. Returns the
    `reveal` config the runtime reads."""
    ids = [r.id for r in rv.regions]
    groups = [ids[i:i + 4] for i in range(0, len(ids), 4)]
    web = ctx.web
    outs = []
    for gi in range(len(groups)):
        outs += [web / f"mask-{gi}.mp4", web / f"mask-{gi}-mobile.mp4"]
    poster, end = web / "poster-reveal.jpg", web / "end-reveal.jpg"
    key = {"regions": {r.id: [[file_key(f) for f in region_files[r.id]], r.grow] for r in rv.regions}, "feather": rv.feather, "gop": gop,
           "fps": round(fps, 4), "base": rv.base, "strength": rv.strength, "keys": region_keys(rv), "ease": rv.ease,
           "film": file_key(src), "v": VERSION}

    def run():
        loaded = {r.id: _union([np.load(f)["masks"] for f in region_files[r.id]]) for r in rv.regions}
        grow = {r.id: r.grow for r in rv.regions}
        n = len(next(iter(loaded.values())))
        for gi, g in enumerate(groups):
            for suffix, tile, crf in (("", TILE, 14), ("-mobile", (TILE[0] // 2, TILE[1] // 2), 20)):
                tiles = [tile_masks(loaded[i], rv.feather, grow[i], tile) for i in g]
                encode_atlas(tiles, fps, gop, web / f"mask-{gi}{suffix}.mp4", crf=crf, log=ctx.log)
                del tiles
        # poster / end frame: the film's first and last frame with the reveal at 0 and at 1 of the section
        small = {i: tile_masks(loaded[i][[0, n - 1]], rv.feather, grow[i], WORK) for i in ids}
        for dst, idx, p in ((poster, 0, 0.0), (end, 1, 1.0)):
            frame = ctx.work / "reveal" / f"_f{idx}.png"
            ffmpeg(*(["-sseof", "-0.1"] if idx else []), "-i", src, "-vf", f"{CROP169},scale={WORK[0]}:{WORK[1]}", "-frames:v", "1",
                   *(["-update", "1"] if idx else []), frame)
            from PIL import Image
            rgb = np.asarray(Image.open(frame).convert("RGB"))
            comp = composite(rgb, {i: small[i][idx] / 255 for i in ids},
                             amounts_at(region_keys(rv), ids, p, rv.ease), rv.base, rv.strength)
            Image.fromarray(comp).resize((1920, 1080), Image.LANCZOS).save(dst, quality=90)
    ctx.stage("reveal_pack", key, outs + [poster, end], run)
    masks = []
    for gi, g in enumerate(groups):
        cols, rows = atlas_layout(len(g))
        masks.append({"video": ctx.url(web / f"mask-{gi}.mp4"), "mobile": ctx.url(web / f"mask-{gi}-mobile.mp4"),
                      "regions": g, "cols": cols, "rows": rows, "tile": list(TILE)})
    return {"base": rv.base, "strength": rv.strength, "ease": rv.ease, "regions": ids, "keys": region_keys(rv),
            "feather": rv.feather, "masks": masks, "fps": round(fps, 4), "poster": ctx.url(poster), "end": ctx.url(end)}


# ---------------------------------------------------------------- the section

def build(sec: FilmScene, ctx: BuildContext, src: Path, cfg: dict) -> dict:
    """The reveal config for the film's page config (masks made and cached as needed). Called by film.build after the
    film is encoded, with the same source file."""
    rv = sec.reveal
    ctx.log(f"  reveal: {len(rv.regions)} region(s), base {rv.base}")
    info = probe(src, "stream=width,height,r_frame_rate,nb_read_frames")
    fps = _fps(info.get("r_frame_rate"))
    nframes = _count_frames(src)
    clip = _work_clip(src, ctx)
    spans = spans_of(sec, ctx)
    shots = shots_of(sec, ctx, rv, clip, nframes, fps, spans)
    ctx.log(f"  {len(shots)} shot(s): " + ", ".join(f"{a}-{b}" for a, b in shots))
    files = {}
    for rg in rv.regions:
        ctx.log(f"  region {rg.id}")
        files[rg.id] = track_region(sec, ctx, rv, rg, src, clip, nframes, fps, spans, shots)
    out = pack(sec, ctx, rv, files, src, fps, sec.gop)
    cfg.update(poster=out.pop("poster"), end=out.pop("end"))
    return out


def _fps(r) -> float:
    a, _, b = str(r or "24/1").partition("/")
    return float(a) / float(b or 1)


def _count_frames(src: Path) -> int:
    import subprocess
    from .config import settings
    out = subprocess.run([settings()["ffprobe"], "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_read_frames", "-of", "csv=p=0", str(src)], capture_output=True, text=True, check=True)
    return int(out.stdout.strip())
