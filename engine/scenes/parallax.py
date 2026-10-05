"""parallax: one photo per step, each given an estimated depth map and played back as a 2.5D camera move."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from ..inputs import credit, image_key, resolve_image
from ..project import BuildContext, BuildError, file_key
from ..spec import ParallaxScene

VERSION = 2


def build(sec: ParallaxScene, ctx: BuildContext, theme: dict) -> dict:
    from ..backends import depth as depthmod
    # every step with an image is a chapter (an intro step may have one); other non-intro steps are an error
    if any(s.image is None for s in sec.steps if not s.intro):
        raise BuildError(f"parallax section '{sec.id}': every non-intro step needs an `image`")
    idx = [i for i, s in enumerate(sec.steps) if s.image is not None]
    if not idx:
        raise BuildError(f"parallax section '{sec.id}' has no images")
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
        if credit(st.image):
            credits.append(credit(st.image))
    return {"chapters": chapters, "move": sec.move, "strength": sec.strength, "end": chapters[-1]["image"],
            "poster": chapters[0]["image"], "credits": credits}
