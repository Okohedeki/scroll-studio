"""parallax: one photo per step, each given an estimated depth map and played back as a 2.5D camera move. A step
without a photo of its own is another caption over the photo before it (the camera keeps moving through that photo's
step), so several captions can be placed and timed over one picture."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageOps

from ..inputs import credit, image_key, resolve_image
from ..project import BuildContext, BuildError, file_key
from ..spec import ParallaxScene

VERSION = 2


def build(sec: ParallaxScene, ctx: BuildContext, theme: dict) -> dict:
    from ..backends import depth as depthmod
    # every step with an image is a chapter; a step without one (a caption, or a block step) shows over the photo
    # before it
    idx = [i for i, s in enumerate(sec.steps) if s.image is not None]
    if not idx:
        raise BuildError(f"parallax section '{sec.id}' has no images: give at least one step an `image`")
    steps = [sec.steps[i] for i in idx]
    chapters, credits = [], []
    for i, st in enumerate(steps):
        src = resolve_image(ctx.project, st.image, ctx.log)
        img_out, dep_out = ctx.web / f"photo{i}.jpg", ctx.web / f"photo{i}-depth.png"

        def run(src=src, img_out=img_out, dep_out=dep_out):
            im = Image.open(src).convert("RGB")
            if im.width > sec.width:
                im = im.resize((sec.width, round(sec.width * im.height / im.width)), Image.LANCZOS)
            im.save(img_out, quality=90, optimize=True, progressive=True)
            d = depthmod.estimate(im, sec.depth_model)
            # Grow near regions a few pixels so foreground edges carry their own colour when they move,
            # instead of smearing the background into them; then soften the steps.
            d8 = (d * 255).astype(np.uint8)
            r = max(2, im.width // 400)
            d8 = cv2.dilate(d8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
            d8 = cv2.GaussianBlur(d8, (0, 0), r * 0.8)
            dw = min(1280, im.width)
            Image.fromarray(d8).resize((dw, round(dw * im.height / im.width)), Image.BICUBIC).save(dep_out, optimize=True)

        key = {"v": VERSION, "img": image_key(st.image), "file": file_key(src), "w": sec.width, "m": sec.depth_model}
        ctx.stage(f"photo{i}", key, [img_out, dep_out], run)
        ctx.progress((i + 1) / len(steps), f"photo {i + 1}/{len(steps)}")
        d = np.asarray(Image.open(dep_out), np.float32) / 255
        focus = float(np.percentile(d, 40))
        chapters.append({"step": idx[i], "image": ctx.url(img_out), "depth": ctx.url(dep_out), "focus": round(focus, 3),
                         "move": sec.moves[i] if i < len(sec.moves) else sec.move})
        frame = phone_frame(st.image, img_out)
        if frame is not None:
            chapters[-1]["frame"] = frame
        if st.world is not None:      # type in the world (engine/world.py): this step's title set inside its photograph
            from .. import world
            chapters[-1]["world"] = world.build_photo(sec, ctx, i, idx[i], st, img_out, dep_out)
        if getattr(st.image, "live", None):      # living details on this photo (engine/live.py), drawn in the photo's own pass
            chapters[-1]["live"] = live_details(ctx, st.image, src, img_out, theme)
        if credit(st.image):
            credits.append(credit(st.image))
    cfg = {"chapters": chapters, "move": sec.move, "strength": sec.strength, "end": chapters[-1]["image"],
           "poster": chapters[0]["image"], "credits": credits}
    if sec.pointer is not None and sec.pointer.pictures:       # the lens's second pictures, one per photo
        cfg["pointer"] = {"layers": pointer_layers(sec, ctx, credits)}
    return cfg


def phone_frame(ref, shown) -> float | None:
    """Where a phone's narrow view of a photo with a calm side (`calm: left | right`) sits across it, 0-1 as CSS
    object-position takes it: leaning toward the calm side only as far as the words need (engine/medium.py phone_crop,
    the rule a hero's picture follows). None for a photo without a calm side, which a phone shows from its middle."""
    side = getattr(ref, "calm", None)
    if side not in ("left", "right"):
        return None
    from ..medium import phone_crop
    with Image.open(shown) as im:
        return round(phone_crop(im.convert("RGB"), side)["x"], 3)


def pointer_layers(sec: ParallaxScene, ctx: BuildContext, credits: list[str]) -> list:
    """Each photo's second picture for the pointer lens (`pointer.layer`), cropped to the photo's shape and resized to its
    exact size, so the page samples both through the same camera move and depth warp. None for a photo without one."""
    out: list = []
    for i, ref in enumerate(sec.pointer.pictures):
        if ref is None:
            out.append(None)
            continue
        photo = ctx.web / f"photo{i}.jpg"
        src = resolve_image(ctx.project, ref, ctx.log)
        dst = ctx.web / f"layer{i}.jpg"

        def run(src=src, photo=photo, dst=dst):
            with Image.open(photo) as ph:
                size = ph.size
            im = Image.open(src).convert("RGB")
            if abs(im.width / im.height - size[0] / size[1]) > 0.02:
                ctx.log(f"  note: pointer layer {i} is not the shape of photo {i}: cropped to it (the lens lines up best "
                        f"when both are the same view at the same size)")
            ImageOps.fit(im, size, Image.LANCZOS).save(dst, quality=90, optimize=True, progressive=True)

        key = {"v": 1, "img": image_key(ref), "file": file_key(src), "photo": file_key(photo)}
        ctx.stage(f"layer{i}", key, [dst], run)
        out.append(ctx.url(dst))
        if credit(ref):
            credits.append(credit(ref))
    return out


def live_details(ctx: BuildContext, ref, src, shown, theme: dict) -> list:
    """A photo's living details for the page; their masks (a prompt's region) are copied in beside the photo."""
    import shutil
    from .. import live

    def url(p):
        shutil.copy(p, ctx.web / p.name)
        return ctx.url(ctx.web / p.name)
    out = live.page_details(ctx.project, ref, src, shown, (theme or {}).get("colors", {}), url, ctx.log)
    if out:
        ctx.log(f"  live: {live.summary(out)}")
    return out
