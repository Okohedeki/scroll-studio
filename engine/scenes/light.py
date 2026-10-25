"""light: one place, relit from dawn to night as the page scrolls (engine/light.py has the pieces, light_presets.py the
named times). Stages, each cached by what it depends on (an unchanged spec rebuilds nothing):

  world         the place, resolved and cut to the working size
  depth         Depth Anything V2 on the world, edge-aligned (the browser's drift and mist read it)
  sky           the sky as a mask (Florence-2 + SAM 2.1 through engine/region.py; a depth/gradient guess without them)
  time_<id>     one time of day: the world relit by Qwen-Image-Edit with the geometry locked (measured, warped back onto
                the world, retried with another seed when it still drifts), or the world itself, or the spec's own picture
  maps          between neighbouring times: the low-frequency light-change field and the lamp map (what turns on); per
                time: the colours text is set in; written with a drift report next to the renders
  web           the pictures as WebP, two sizes
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from .. import light, light_presets
from ..inputs import credit, image_key, resolve_image
from ..layout import set_window, window, windows_by_length
from ..project import BuildContext, BuildError, file_key
from ..spec import LightScene, LightSun

VERSION = 3              # bump when the cheap stages (maps, web, depth, sky) would come out differently
RELIGHT_VERSION = 1      # bump when a time of day would come out differently: it re-renders every relight
HOLD_FLOOR = 0.01


def _hours(clock: Optional[str]) -> Optional[float]:
    m = re.fullmatch(r"\s*(\d{1,2})[:.h](\d{2})\s*", clock or "")
    return int(m.group(1)) + int(m.group(2)) / 60 if m else None


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _world_source(sec: LightScene, ctx: BuildContext) -> Path:
    """The world picture: a file, an image input, or `scene:<id>` (the first frame another scene built)."""
    w = sec.world
    if isinstance(w, str) and w.startswith("scene:"):
        sid = w[6:]
        cfg = ctx.project.build / sid / "config.json"
        if not cfg.exists():
            raise BuildError(f"light '{sec.id}': world is {w}, but that scene has not been built yet (build it first)")
        c = json.loads(cfg.read_text())
        rel = c.get("poster") or c.get("end")
        if not rel:
            raise BuildError(f"light '{sec.id}': scene '{sid}' has no still to use as a world")
        p = ctx.project.build / sid / "web" / Path(rel).relative_to(f"assets/{sid}")
        if not p.exists():
            raise BuildError(f"light '{sec.id}': {p} is missing")
        return p
    return resolve_image(ctx.project, w, ctx.log)


def _sizes(src: Path, width: int) -> tuple[int, int]:
    w0, h0 = Image.open(src).size
    w = min(width, w0) // 16 * 16
    h = round(h0 * w / w0) // 16 * 16
    return w, max(16, h)


def _times_meta(sec: LightScene) -> list[dict]:
    """Per time: id, label, clock text, hours (interpolated from neighbours when a free-text time has none), haze, lit."""
    out = []
    for i, t in enumerate(sec.times):
        p = light_presets.PRESETS.get(t.preset) if t.preset else None
        hours = _hours(t.clock) if t.clock else (p["hours"] if p else None)
        out.append({"id": t.id, "i": i, "label": (p["label"] if p else t.id.replace("-", " ").capitalize()),
                    "clock": t.clock or (p["clock"] if p else None), "hours": hours,
                    "haze": t.haze if t.haze is not None else (p["haze"] if p else 0.0),
                    "lit": t.lit if t.lit is not None else (p["lit"] if p else False),
                    "sun": (p["sun"] if p else "high")})
    known = [i for i, m in enumerate(out) if m["hours"] is not None]
    for i, m in enumerate(out):
        if m["hours"] is None:
            lo = max((k for k in known if k < i), default=None)
            hi = min((k for k in known if k > i), default=None)
            if lo is not None and hi is not None:
                m["hours"] = out[lo]["hours"] + (out[hi]["hours"] - out[lo]["hours"]) * (i - lo) / (hi - lo)
            elif lo is not None:
                m["hours"] = out[lo]["hours"] + 1.5 * (i - lo)
            elif hi is not None:
                m["hours"] = out[hi]["hours"] - 1.5 * (hi - i)
            else:
                m["hours"] = 6 + 2.5 * i
        if not m["clock"]:
            hh = m["hours"] % 24
            m["clock"] = f"{int(hh):02d}:{int(round((hh % 1) * 60)) % 60:02d}"
    return out


def schedule(sec: LightScene) -> tuple[list[int], list[dict]]:
    """Which time each step sits at, and where the light holds still while its step is read: {t, a, b} in section
    progress (a hold is the middle `hold` share of the step's stretch). Overlay steps without `at` are given even
    stretches (their captions are scheduled here), split and cards steps take theirs from `length`."""
    ids = [t.id for t in sec.times]
    n = len(sec.steps)
    if n == 0:
        raise BuildError(f"light '{sec.id}': give the section steps (the sections of the day)")
    pins = [(st.state or {}).get("time") for st in sec.steps]
    nt = len(ids)
    out: list[int] = []
    for i, pin in enumerate(pins):
        if pin is not None:
            out.append(ids.index(pin))
        elif not any(pins):
            out.append(round(i * (nt - 1) / max(n - 1, 1)))
        else:
            out.append(out[-1] if out else 0)
    if sec.layout == "overlay":
        if sec.length <= 0:
            sec.length = round(2.6 * max(n, 2), 2)
        spans = [window(st) or (i / n, (i + 1) / n) for i, st in enumerate(sec.steps)]
    else:
        spans = windows_by_length(sec.steps)
    holds = []
    for (a, b), t in zip(spans, out):
        c, hw = (a + b) / 2, max(HOLD_FLOOR, sec.hold * (b - a) / 2)
        holds.append({"t": t, "a": round(c - hw, 4), "b": round(c + hw, 4)})
    if sec.layout == "overlay":
        # a headline is on screen while the light holds (and a little either side): the change itself passes between
        # headlines, with nothing over it, and a caption never sits on a picture that has become another time
        for i, (st, h, (a, b)) in enumerate(zip(sec.steps, holds, spans)):
            if window(st) is None:
                m = 0.1 * (b - a)
                set_window(st, 0.0 if i == 0 else round(h["a"] - m, 4), 1.0 if i == n - 1 else round(h["b"] + m, 4))
    return out, holds


def time_at(p: float, holds: list[dict]) -> float:
    """The time index (fractional: 2.5 is half-way from the third time to the fourth) at section progress `p`. The CPU
    twin of `timeAt` in runtime/src/players/light.ts: the light holds still through each step's hold, then eases to the
    next step's time (smoothstep) before the next hold begins."""
    if not holds:
        return 0.0
    if p <= holds[0]["a"]:
        return float(holds[0]["t"])
    for i, h in enumerate(holds):
        if p <= h["b"]:
            return float(h["t"])
        if i + 1 >= len(holds):
            return float(h["t"])
        n = holds[i + 1]
        if p < n["a"]:
            k = min(1.0, max(0.0, (p - h["b"]) / max(n["a"] - h["b"], 1e-9)))
            return h["t"] + (n["t"] - h["t"]) * k * k * (3 - 2 * k)
    return float(holds[-1]["t"])


def build(sec: LightScene, ctx: BuildContext, theme: dict) -> dict:
    from .. import region as regionmod
    from ..spec import EditRegion
    draft = bool(ctx.options.get("draft"))
    times = _times_meta(sec)
    ids = [t["id"] for t in times]
    step_times, holds = schedule(sec)

    # ---- the world
    src = _world_source(sec, ctx)
    W, H = _sizes(src, sec.width)
    world_png = ctx.work / "world.png"

    def make_world():
        im = Image.open(src).convert("RGB")
        im = im.resize((W, H), Image.LANCZOS) if im.size != (W, H) else im
        im.save(world_png)
    ctx.stage("world", {"v": VERSION, "file": file_key(src), "size": [W, H]}, [world_png], make_world)
    world = light.load_rgb(world_png)
    wkey = _digest([file_key(world_png)])

    # ---- depth
    depth_png = ctx.work / "depth.png"
    ctx.stage("depth", {"v": VERSION, "world": wkey, "model": sec.depth_model}, [depth_png],
              lambda: Image.fromarray(light.depth_map(world, sec.depth_model)).save(depth_png))
    depth = np.asarray(Image.open(depth_png))

    # ---- the sky (sun glow clip, stars and glare kept out of the lamps)
    sky_png = ctx.work / "sky.png"
    sun = sec.sun if isinstance(sec.sun, LightSun) else (LightSun() if sec.sun else None)
    skyq = (sun.sky if sun and sun.sky else "the sky")

    def make_sky():
        try:
            if draft:
                raise RuntimeError("draft build")
            m = np.asarray(Image.open(regionmod.find(ctx.project, world_png, EditRegion(prompt=skyq), ctx.log)).convert("L"),
                           np.float32) / 255
        except Exception as e:     # no ComfyUI nodes, or nothing found: a guess from depth and smoothness
            ctx.log(f"  sky: {str(e).splitlines()[0][:120]}; using a depth-based guess")
            m = light.sky_mask_fallback(world, depth)
        import cv2
        m = cv2.resize(m, (480, round(480 * H / W)), interpolation=cv2.INTER_AREA)
        Image.fromarray(np.clip(m * 255, 0, 255).astype(np.uint8)).save(sky_png)
    ctx.stage("sky", {"v": VERSION, "world": wkey, "q": skyq, "draft": draft}, [sky_png], make_sky)
    sky = np.asarray(Image.open(sky_png), np.float32) / 255

    # ---- the times
    tdir = ctx.work / "times"
    tdir.mkdir(exist_ok=True)
    imgs: list[Optional[np.ndarray]] = [None] * len(sec.times)
    reports: list[Optional[dict]] = [None] * len(sec.times)
    # what each time is relit from: the world, or (chain) its neighbour nearer the world's time. The anchor goes first, then
    # outward, so every source is built before the time that is made from it
    anchor = ids.index(sec.world_time) if sec.world_time else None
    sources: list[Optional[int]] = [None] * len(sec.times)           # None: the world itself
    order = list(range(len(sec.times)))
    if sec.structure.chain:
        a0 = anchor if anchor is not None else -1
        order = ([anchor] if anchor is not None else []) + list(range(a0 + 1, len(sec.times))) + list(range(a0 - 1, -1, -1))
        for i in range(len(sec.times)):
            if i == anchor:
                continue
            sources[i] = (i - 1 if i - 1 >= 0 else None) if i > a0 else i + 1
    for i in order:
        t = sec.times[i]
        tid = t.id
        png, js = tdir / f"{tid}.png", tdir / f"{tid}.json"
        if sources[i] is None:
            base_png, base_img, base_key = world_png, world, wkey
        else:
            base_png = tdir / f"{ids[sources[i]]}.png"
            base_img = imgs[sources[i]]
            base_key = _digest([file_key(base_png)])
        if t.image is not None:
            msrc = resolve_image(ctx.project, t.image, ctx.log)
            key = {"v": RELIGHT_VERSION, "world": base_key, "image": image_key(t.image), "file": file_key(msrc), "align": sec.structure.align}
            legacy = None
            mode = "image"
        elif tid == sec.world_time:
            key = {"v": RELIGHT_VERSION, "world": wkey, "anchor": True}
            legacy = None
            mode = "anchor"
        else:
            instr = light_presets.instruction(t.preset, t.prompt)
            seed0 = t.seed if t.seed is not None else sec.seed + 13 * i
            steps = max(4, sec.edit_steps // 2) if draft else sec.edit_steps
            st = sec.structure
            # the limit and the retries are not part of the key: a picture that was made stays the picture (a time that
            # failed its limit is warned about on every build; give it another `seed:` to redo it)
            strength = t.strength if t.strength is not None else st.strength
            key = {"v": RELIGHT_VERSION, "light": light.RELIGHT_VERSION, "world": base_key, "ins": instr, "seed": seed0, "steps": steps,
                   "align": st.align, "strength": strength}
            legacy = None
            mode = "relight"

        def run(tid=tid, mode=mode, t=t, png=png, js=js, i=i):
            if mode == "anchor":
                Image.fromarray(world).save(png)
                js.write_text(json.dumps({"anchor": True, "raw": {"drift": 0, "drift_p90": 0, "edges": 1},
                                          "aligned": {"drift": 0, "drift_p90": 0, "edges": 1}, "ok": True}))
                return
            if mode == "image":
                cand = light.load_rgb(msrc, (W, H))
                img, rep = light.align(base_img, cand, None, sec.structure.align)
            else:
                seeds = [seed0 + 1000 * j for j in range(1 + (0 if draft else sec.structure.retries))]
                ctx.log(f"  relighting '{tid}' (Qwen-Image-Edit, {steps} steps)")
                img, rep = light.relight_locked(base_img, base_png, instr, seeds, steps, sec.structure.max_drift,
                                                sec.structure.align, tdir, tid, ctx.log, strength)
            if sources[i] is not None:       # relative to the world, too: a chain must not wander
                rep["to_world"] = light.measure(world, img)["drift"]
                rep["source"] = ids[sources[i]]
            Image.fromarray(img).save(png)
            js.write_text(json.dumps(rep, indent=1))
        ctx.stage(f"time_{tid}", key, [png, js], run, legacy=legacy)
        ctx.progress(0.1 + 0.6 * (order.index(i) + 1) / len(sec.times), f"time {order.index(i) + 1}/{len(sec.times)}")
        imgs[i] = light.load_rgb(png)
        reports[i] = json.loads(js.read_text())
        reports[i]["ok"] = bool(reports[i].get("anchor")) or reports[i]["aligned"]["drift"] <= sec.structure.max_drift
        if not reports[i]["ok"]:
            ctx.log(f"  warning: '{tid}' is still {reports[i]['aligned']['drift']:.2f}px from "
                    f"{'the world' if sources[i] is None else ids[sources[i]]} (limit {sec.structure.max_drift}); give that time "
                    f"another `seed:`, or raise structure.max_drift")

    # ---- the maps between times, and the colours at each time
    mdir = ctx.work / "maps"
    mdir.mkdir(exist_ok=True)
    meta_json = ctx.work / "maps.json"
    tkeys = [file_key(tdir / f"{t.id}.png") for t in sec.times]
    pair_files = [mdir / f"ratio{k}.png" for k in range(len(times) - 1)] + [mdir / f"flow{k}.png" for k in range(len(times) - 1)]
    lamps_key = [l.model_dump(mode="json") for l in sec.lamps]

    def make_maps():
        meta = {"pairs": [], "tokens": []}
        for k in range(len(times) - 1):
            a, b = imgs[k], imgs[k + 1]
            Image.fromarray(light.ratio_map(world, a, b)).save(mdir / f"ratio{k}.png")
            fl, gl = light.pair_flow(a, b)
            Image.fromarray(fl).save(mdir / f"flow{k}.png")
            allow = None
            hint = True if times[k + 1]["lit"] and not times[k]["lit"] else False if times[k]["lit"] and not times[k + 1]["lit"] else None
            if sec.lamps:
                import cv2
                if hint is None:     # both lit or both dark: whichever picture has more small bright features
                    hint = bool(light._top_hat(light.luma(b), 41).sum() >= light._top_hat(light.luma(a), 41).sum())
                lit = sec.times[k + 1].id if hint else sec.times[k].id
                ms = []
                for spec in sec.lamps:
                    try:
                        mk = regionmod.find(ctx.project, tdir / f"{lit}.png", EditRegion(prompt=spec.prompt), ctx.log)
                        ms.append(np.asarray(Image.open(mk).convert("L"), np.float32) / 255)
                    except Exception as e:
                        ctx.log(f"  lamps '{spec.prompt}': {str(e).splitlines()[0][:140]}; using what changed between the pictures")
                if ms:
                    allow = np.maximum.reduce([cv2.resize(m, (W, H)) for m in ms])
            lamp = light.lamp_map(a, b, sky=sky, allow=allow, glow=max([l.glow for l in sec.lamps] or [1.0]),
                                  grow=sec.lamps[0].grow if sec.lamps else 2, seed=5 + k,
                                  turns_on=hint)
            entry = {"ratio": f"ratio{k}.png", "flow": f"flow{k}.png", "glide": gl["glide"], "lamp": None, "color": None, "count": 0}
            if lamp is not None:
                f = mdir / f"lamp{k}.png"
                Image.fromarray(lamp["map"], "RGBA").save(f)
                color = next((l.color for l in sec.lamps if l.color), None) or lamp["color"]
                entry.update(lamp=f.name, color=color, count=lamp["count"], turns_on=lamp["turns_on"],
                             glow=max([l.glow for l in sec.lamps] or [1.0]))
            meta["pairs"].append(entry)
        for im in imgs:
            tk = light.tokens(im)
            tk["fog"] = light.fog_color(im, sky)
            meta["tokens"].append(tk)
        meta_json.write_text(json.dumps(meta))
    ctx.stage("maps", {"v": VERSION, "light": light.VERSION, "times": tkeys, "lamps": lamps_key, "sky": file_key(sky_png)},
              [meta_json, *pair_files], make_maps)
    meta = json.loads(meta_json.read_text())

    # ---- the report and the web files
    (ctx.work / "report.json").write_text(json.dumps(
        {"times": [{"id": t["id"], "clock": t["clock"], **r} for t, r in zip(times, reports)],
         "pairs": [{"from": ids[k], "to": ids[k + 1], "lamps": p["count"], "glide": p["glide"]} for k, p in enumerate(meta["pairs"])]}, indent=1))

    small_w = max(480, round(W * 2 / 3) // 16 * 16)
    web_files = []
    for i, t in enumerate(sec.times):
        web_files += [ctx.web / f"t{i}.webp", ctx.web / f"t{i}-s.webp"]
    web_files += [ctx.web / "depth.png", ctx.web / "sky.png", ctx.web / "poster.jpg"]
    web_files += [ctx.web / p["ratio"] for p in meta["pairs"]] + [ctx.web / p["flow"] for p in meta["pairs"]]
    web_files += [ctx.web / p["lamp"] for p in meta["pairs"] if p["lamp"]]

    def make_web():
        import shutil
        for i, im in enumerate(imgs):
            pil = Image.fromarray(im)
            pil.save(ctx.web / f"t{i}.webp", "WEBP", quality=88, method=4)
            pil.resize((small_w, round(H * small_w / W)), Image.LANCZOS).save(ctx.web / f"t{i}-s.webp", "WEBP", quality=86, method=4)
        shutil.copy(depth_png, ctx.web / "depth.png")
        shutil.copy(sky_png, ctx.web / "sky.png")
        Image.fromarray(imgs[0]).resize((1280, round(H * 1280 / W)), Image.LANCZOS).save(ctx.web / "poster.jpg", quality=84)
        for p in meta["pairs"]:
            shutil.copy(mdir / p["ratio"], ctx.web / p["ratio"])
            shutil.copy(mdir / p["flow"], ctx.web / p["flow"])
            if p["lamp"]:
                shutil.copy(mdir / p["lamp"], ctx.web / p["lamp"])
    ctx.stage("web", {"v": VERSION, "times": tkeys, "w": W, "small": small_w, "maps": file_key(meta_json)}, web_files, make_web)

    cfg_times = []
    for i, (t, tk) in enumerate(zip(times, meta["tokens"])):
        cfg_times.append({**{k: t[k] for k in ("id", "label", "clock", "hours", "haze", "lit", "sun")},
                          "img": ctx.url(ctx.web / f"t{i}.webp"), "imgS": ctx.url(ctx.web / f"t{i}-s.webp"), "tokens": tk,
                          "drift": reports[i].get("aligned", {}).get("drift", 0)})
    pairs = [{"ratio": ctx.url(ctx.web / p["ratio"]), "flow": ctx.url(ctx.web / p["flow"]), "glide": p["glide"], "lamp": ctx.url(ctx.web / p["lamp"]) if p["lamp"] else None,
              "color": p["color"], "glow": p.get("glow", 1.0), "count": p["count"]} for p in meta["pairs"]]
    credits = [credit(sec.world)] if credit(sec.world) else []
    return {
        "w": W, "h": H, "times": cfg_times, "pairs": pairs, "holds": holds, "stepTimes": step_times,
        "depth": ctx.url(ctx.web / "depth.png"), "sky": ctx.url(ctx.web / "sky.png"),
        "sun": sun.model_dump(mode="json") if sun else None, "mist": sec.mist, "drift": sec.drift, "follow": sec.follow,
        "clock": sec.clock, "blend": sec.blend, "layout": sec.layout, "focus": list(sec.focus),
        "poster": ctx.url(ctx.web / "poster.jpg"), "end": ctx.url(ctx.web / f"t{len(times) - 1}.webp"),
        "credits": credits,
    }
