"""stages: one subject through its states, a sequence of stills of exactly the same view, scrolled through in order.

Each stage's picture is resolved like any image input and fitted to the first stage's exact size (a log line says when a
shape differed, since the stages only line up when they are the same view). A `map` reveal's greyscale picture is fitted
the same way. The page (runtime/src/players/stages.ts) draws two neighbouring stages in one WebGL pass and reveals the
next through a fade, a straight wipe or the map, with an optional band of light along the front; it holds still on each
stage while its step is read (`schedule`, the same holds as a `light` scene). Everything here runs on the CPU.

  s<i>.webp / s<i>-s.webp   each stage, desktop and phone widths
  map<i>.png                the reveal map of stage i (map reveals)
  layer.webp                the pointer lens's second picture, if any
  poster.jpg                the first stage, for the loader and for pages without WebGL
"""
from __future__ import annotations

from PIL import Image, ImageOps

from ..inputs import credit, image_key, resolve_image
from ..layout import set_window, window, windows_by_length
from ..project import BuildContext, BuildError, file_key
from ..spec import StagesScene

VERSION = 1
HOLD_FLOOR = 0.02            # the shortest hold, as a share of the scene, so a headline always has a still picture
PER_STAGE = 2.2              # overlay length per stage, screen heights, when the spec leaves `length` at 0


def stage_index(sec: StagesScene, pin) -> int:
    """A step's `state.stage` (an id or an index) as an index."""
    if isinstance(pin, int) and not isinstance(pin, bool):
        return pin
    return [st.id for st in sec.stages].index(pin)


def schedule(sec: StagesScene) -> tuple[list[int], list[dict]]:
    """Which stage each step sits at, and where the picture holds still while that step is read: {t, a, b} in scene
    progress. Steps without a pin are spread over the stages in order (or follow the pinned step before them). Overlay
    steps without their own `show` are timed here so a caption is on screen while its stage holds."""
    n = len(sec.steps)
    if n == 0:
        raise BuildError(f"stages '{sec.id}': give the section steps (what to say at each stage)")
    pins = [(st.state or {}).get("stage") for st in sec.steps]
    ns = len(sec.stages)
    out: list[int] = []
    for i, pin in enumerate(pins):
        if pin is not None:
            out.append(stage_index(sec, pin))
        elif all(p is None for p in pins):
            out.append(round(i * (ns - 1) / max(n - 1, 1)))
        else:
            out.append(out[-1] if out else 0)
    if sec.layout == "overlay":
        if sec.length <= 0:
            sec.length = round(PER_STAGE * max(ns, n, 2), 2)
        spans = [window(st) or (i / n, (i + 1) / n) for i, st in enumerate(sec.steps)]
    else:
        spans = windows_by_length(sec.steps)
    holds = []
    for (a, b), t in zip(spans, out):
        c, hw = (a + b) / 2, max(HOLD_FLOOR, sec.hold * (b - a) / 2)
        holds.append({"t": t, "a": round(c - hw, 4), "b": round(c + hw, 4)})
    if sec.layout == "overlay":
        for i, (st, h, (a, b)) in enumerate(zip(sec.steps, holds, spans)):
            if window(st) is None:
                m = 0.1 * (b - a)
                set_window(st, 0.0 if i == 0 else round(h["a"] - m, 4), 1.0 if i == n - 1 else round(h["b"] + m, 4))
    return out, holds


def stage_at(p: float, holds: list[dict]) -> float:
    """The stage (fractional: 2.5 is half-way through revealing the fourth stage over the third) at scene progress `p`:
    still through each hold, then easing to the next step's stage. The CPU twin of `stageAt` in the player."""
    if not holds:
        return 0.0
    if p <= holds[0]["a"]:
        return float(holds[0]["t"])
    for i, h in enumerate(holds):
        if p <= h["b"] or i + 1 >= len(holds):
            return float(h["t"])
        nx = holds[i + 1]
        if p < nx["a"]:
            k = min(1.0, max(0.0, (p - h["b"]) / max(nx["a"] - h["b"], 1e-9)))
            return h["t"] + (nx["t"] - h["t"]) * k * k * (3 - 2 * k)
    return float(holds[-1]["t"])


def front_colour(color: str, colors: dict) -> str:
    """A front's colour as #rrggbb: a theme role resolved against the site's colours, or the hex itself."""
    from ..medium import _lum, hexc
    if color.startswith("#"):
        return hexc(color)
    c = {k: v for k, v in (colors or {}).items() if isinstance(v, str) and v.strip().startswith("#")}
    bg, ink = c.get("bg", "#fafaf8"), c.get("ink", "#141418")
    light, dark = (bg, ink) if _lum(bg) >= _lum(ink) else (ink, bg)
    roles = {**c, "light": light, "dark": dark}
    return hexc(roles.get(color) or roles.get("accent") or ink)


def _frame(f) -> dict:
    return {"fit": f.fit, "position": list(f.position), "zoom": f.zoom}


def build(sec: StagesScene, ctx: BuildContext, theme: dict) -> dict:
    step_stages, holds = schedule(sec)
    srcs = [resolve_image(ctx.project, st.image, ctx.log) for st in sec.stages]
    with Image.open(srcs[0]) as im0:
        size = im0.size
    W = min(sec.width, size[0])
    H = round(size[1] * W / size[0])
    small_w = max(480, round(W * 2 / 3))
    small_h = round(H * small_w / W)

    def fitted(src, i, what) -> Image.Image:
        im = Image.open(src)
        if abs(im.width / im.height - size[0] / size[1]) > 0.01:
            ctx.log(f"  note: {what} {i} is not the shape of stage 0: cropped to it (stages line up only when every "
                    f"picture is the same view)")
        return ImageOps.fit(im.convert("RGB"), (W, H), Image.LANCZOS)

    colors = (theme or {}).get("colors", {})
    out_stages, credits = [], []
    for i, (st, src) in enumerate(zip(sec.stages, srcs)):
        big, sm = ctx.web / f"s{i}.webp", ctx.web / f"s{i}-s.webp"

        def run(src=src, i=i, big=big, sm=sm):
            im = fitted(src, i, "stage")
            im.save(big, "WEBP", quality=90, method=4)
            im.resize((small_w, small_h), Image.LANCZOS).save(sm, "WEBP", quality=88, method=4)

        ctx.stage(f"stage{i}", {"v": VERSION, "img": image_key(st.image), "file": file_key(src), "w": W, "h": H,
                                "first": file_key(srcs[0])}, [big, sm], run)
        rv = st.reveal
        reveal = {"kind": rv.kind if i else "none", "angle": rv.angle, "soft": rv.softness}
        if i and rv.kind == "map":
            msrc = resolve_image(ctx.project, rv.map, ctx.log)
            mp = ctx.web / f"map{i}.png"

            def run_map(msrc=msrc, i=i, mp=mp):
                fitted(msrc, i, "reveal map").convert("L").resize((small_w, small_h), Image.BILINEAR).save(mp, optimize=True)

            ctx.stage(f"map{i}", {"v": VERSION, "img": image_key(rv.map), "file": file_key(msrc), "w": small_w,
                                  "first": file_key(srcs[0])}, [mp], run_map)
            reveal["map"] = ctx.url(mp)
        if i and rv.front is not None:
            reveal["front"] = {"color": front_colour(rv.front.color, colors), "width": rv.front.width,
                               "strength": rv.front.strength, "where": rv.front.where}
        out_stages.append({"id": st.id, "img": ctx.url(big), "imgS": ctx.url(sm), "reveal": reveal})
        ctx.progress((i + 1) / len(sec.stages), f"stage {i + 1}/{len(sec.stages)}")
        if credit(st.image):
            credits.append(credit(st.image))

    poster = ctx.web / "poster.jpg"
    ctx.stage("poster", {"v": VERSION, "first": file_key(srcs[0]), "w": W},
              [poster], lambda: fitted(srcs[0], 0, "stage").save(poster, quality=86))
    cfg = {"w": W, "h": H, "stages": out_stages, "holds": holds, "stepStages": step_stages, "drift": sec.drift,
           "fit": _frame(sec.fit), "phone": _frame(sec.phone or sec.fit), "layout": sec.layout,
           "poster": ctx.url(poster), "end": out_stages[-1]["img"], "credits": credits}
    if sec.pointer is not None and sec.pointer.pictures:
        ref = sec.pointer.pictures[0]
        lsrc = resolve_image(ctx.project, ref, ctx.log)
        lay = ctx.web / "layer.webp"
        ctx.stage("layer", {"v": VERSION, "img": image_key(ref), "file": file_key(lsrc), "w": W, "h": H,
                            "first": file_key(srcs[0])},
                  [lay], lambda: fitted(lsrc, 0, "pointer layer").save(lay, "WEBP", quality=90, method=4))
        cfg["pointer"] = {"layers": [ctx.url(lay)]}
        if credit(ref):
            credits.append(credit(ref))
    return cfg
