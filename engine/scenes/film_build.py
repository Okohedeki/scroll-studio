"""Film stages: Blender blockout -> Z-Image keyframes -> local LTX-2.3 (ComfyUI) -> optional upscale.

Called by engine/scenes/film.py (the `film` scene type); each stage is cached by its settings.
`shot` is the section's `shot:` mapping from site.yaml, `out` the section's build folder.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess

from ..backends import comfy as ltx_comfy
from ..config import settings

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backends", "blender_scripts")
BLENDER = settings()["blender"]
FFMPEG = settings()["ffmpeg"]


def sh(cmd):
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    # capture and re-print: a child writing straight to fd 1 would corrupt the MCP channel
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.stdout.strip():
        print(p.stdout[-4000:], flush=True)
    if p.returncode != 0:
        raise RuntimeError(f"{os.path.basename(str(cmd[0]))} failed ({p.returncode}):\n{(p.stderr or p.stdout)[-3000:]}")


def ff(*args):
    sh([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args])


def stage_blockout(shot, out):
    bdir = os.path.join(out, "blockout")
    w, h = shot["preview_res"]
    bl = shot.get("blockout", {})
    if bl.get("file"):   # user scene: its camera animation drives the shot
        cmd = [BLENDER, "-b", bl["file"], "--python-exit-code", "1", "--python", os.path.join(SCRIPTS, "file_blockout.py"), "--"]
    elif bl.get("world"):   # a take: world described in the spec (take.json), rendered with its product in place
        sh([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", os.path.join(SCRIPTS, "take.py"), "--",
            "--take", bl["world"], "--pass", "world", "--out", bdir, "--res", f"{w}x{h}"])
        cmd = None
    else:
        cmd = [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", os.path.join(SCRIPTS, "presets", bl.get("preset", "rocket_launch").replace("-", "_") + ".py"), "--"]
    if cmd:
        sh(cmd + ["--out", bdir, "--fps", shot["fps"], "--duration", shot["duration"], "--res", f"{w}x{h}"])
    frames = sorted(glob.glob(os.path.join(bdir, "frames", "*.png")))
    ff("-framerate", str(shot["fps"]), "-i", os.path.join(bdir, "frames", "%04d.png"),
       "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
       os.path.join(bdir, "blockout.mp4"))
    ff("-framerate", str(shot["fps"]), "-i", os.path.join(bdir, "depth", "%04d.png"),
       "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
       os.path.join(bdir, "depth.mp4"))
    shutil.copy(frames[0], os.path.join(bdir, "first.png"))
    shutil.copy(frames[-1], os.path.join(bdir, "last.png"))
    print(f"  blockout: {len(frames)} frames -> {os.path.join(bdir, 'blockout.mp4')}")


def ltx_frames(seconds, fps):
    """LTX wants 8k+1 frames."""
    n = int(round(seconds * fps))
    return ((n + 7) // 8) * 8 + 1 if n % 8 != 1 else n


def keyframe_index(t, fps):
    """Frame index for a keyframe time: 'end' -> -1 (last frame), else snapped to a latent frame (8)."""
    return -1 if t == "end" else int(round(t * fps / 8)) * 8


def stage_keyframes(shot, out, args):
    """Detailed stills from Z-Image Turbo, each locked to the Blender depth of its frame.

    Writes keyframes/<name>_v<n>.png per variant and copies v1 to keyframes/<name>.png;
    choose a different variant by copying it over <name>.png. --only <name> redoes one keyframe.
    """
    if not args.dry_run:
        ltx_comfy.free()
    kcfg = dict(ltx_comfy.ZIMAGE, **shot["keyframes"])   # model files default to engine/models.yaml's names
    w, h = kcfg.get("res", [1536, 864])
    bdir = os.path.join(out, "blockout")
    kdir = os.path.join(out, "keyframes")
    os.makedirs(kdir, exist_ok=True)
    depth_frames = sorted(glob.glob(os.path.join(bdir, "depth", "*.png")))
    for spec in kcfg["frames"]:
        name = spec["name"]
        if args.only and name != args.only:
            continue
        if name in (getattr(args, "skip", None) or ()):
            continue
        idx = keyframe_index(spec["t"], shot["fps"])
        depth_src = depth_frames[idx if idx < 0 else min(idx, len(depth_frames) - 1)]
        depth = os.path.join(kdir, f"depth_{name}_{w}x{h}.png")
        blur = spec.get("depth_blur", 0)
        ff("-i", depth_src, "-vf", f"scale={w}:{h}:flags=lanczos" + (f",gblur=sigma={blur}" if blur else ""), depth)
        depth_name = ltx_comfy.upload(depth)
        spec_cfg = dict(kcfg, control_strength=spec.get("control_strength", kcfg.get("control_strength", 0.8)))
        for i in range(args.variants):
            seed = spec.get("seed", kcfg.get("seed", 7)) + i   # a keyframe may pin its own seed
            graph = ltx_comfy.build_keyframe_graph(spec_cfg, spec["prompt"], depth_name, w, h, seed,
                                                   prefix=f"{shot['id']}/key_{name}")
            if args.dry_run:
                print(f"  dry run: {name} keyframe graph with {len(graph)} nodes")
                break
            images = ltx_comfy.run(graph, poll=2)
            vdir = ltx_comfy.fetch(images, os.path.join(kdir, f"_{name}_v{i + 1}"))
            dst = os.path.join(kdir, f"{name}_v{i + 1}.png")
            shutil.move(os.path.join(vdir, "0001.png"), dst)
            shutil.rmtree(vdir, ignore_errors=True)
            print(f"  {name} keyframe v{i + 1} (seed {seed}) -> {dst}", flush=True)
        if not args.dry_run:
            shutil.copy(os.path.join(kdir, f"{name}_v1.png"), os.path.join(kdir, f"{name}.png"))


def stage_generate(shot, out, args):
    """Local LTX-2.3 via ComfyUI: Blender depth pass = structure and camera, keyframes = detail.

    Long shots are split into ltx.segments ([start, end] seconds, own prompt). Each segment after
    the first starts from the previous segment's real last frame, so the joins are seamless, and
    the segments are concatenated into gen/gen.mp4.
    """
    if not args.dry_run:
        ltx_comfy.free()
    base = dict(ltx_comfy.LTX, **shot["ltx"])            # model files default to engine/models.yaml's names
    if args.res:
        base["res"] = [int(v) for v in args.res.split("x")]
    if args.upscale is not None:
        base["upscale"] = args.upscale
    if args.sampler:
        base["sampler"] = args.sampler
    w, h = base["res"]
    if w % 64 or h % 64:
        # The Union-Control IC-LoRA works on a half-size reference latent (32 px/latent x 2).
        raise SystemExit(f"ltx.res {w}x{h}: both sides must be multiples of 64 (e.g. 1024x576, 768x448)")
    fps = shot["fps"]
    bdir = os.path.join(out, "blockout")
    gdir = os.path.join(out, "gen")
    kdir = os.path.join(out, "keyframes")
    os.makedirs(gdir, exist_ok=True)

    segments = base.pop("segments", None) or [{"id": "main", "range": [0, shot["duration"]]}]
    if args.seconds:
        first = segments[0]
        segments = [dict(first, range=[first["range"][0], first["range"][0] + args.seconds])]
    state_path = os.path.join(gdir, "segments.json")
    state = {}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    seg_files = []        # the files a segment is made from (its resume key covers their content)

    def upload_still(src, name):
        dst = os.path.join(gdir, f"{name}_{shot['id']}_{w}x{h}.png")
        ff("-i", src, "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}", dst)
        seg_files.append(dst)
        return ltx_comfy.upload(dst)

    def digest_of(paths):
        d = hashlib.sha1()
        for q in paths:
            with open(q, "rb") as f:
                d.update(f.read())
        return d.hexdigest()[:16]

    for si, seg in enumerate(segments):
        if args.segment and seg["id"] != args.segment:
            continue
        cfg = dict(base, **{k: v for k, v in seg.items() if k not in ("id", "range", "continue")})
        start = int(round(seg["range"][0] * fps))
        frames = ltx_frames(seg["range"][1] - seg["range"][0], fps)
        last_seg = si == len(segments) - 1
        sid = f"{shot['id']}_{seg['id']}"
        # Latent tokens = (w/32) x (h/32) x latent frames. ~18k tokens (1024x576 x 10 s) and ~13k
        # (1536x896 x 3 s) render in minutes; 42k (1536x896 x 10 s) overflowed VRAM and ran for 8 hours.
        tokens = (w // 32) * (h // 32) * ((frames - 1) // 8 + 1)
        if tokens > cfg.get("max_tokens", 22000) and not args.dry_run:
            raise SystemExit(f"segment {seg['id']}: {frames} frames at {w}x{h} = {tokens} latent tokens, over the "
                             f"~22k that fits in VRAM. Split it into shorter segments (about "
                             f"{max(1, int(22000 / ((w // 32) * (h // 32)) * 8 / fps))} s at this resolution).")

        # Depth guide slice at the exact latent size; pad by repeating the last frame. A blur keeps
        # the camera parallax and big shapes but drops blockout edges, so boxes don't stay boxes.
        blur = cfg.get("guide_blur", 0)
        guide = os.path.join(gdir, f"guide_{sid}_{w}x{h}_{frames}_b{blur}.mp4")
        vf = [f"trim=start_frame={start}", "setpts=PTS-STARTPTS",
              f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={w}:{h}"]
        if blur:
            vf.append(f"gblur=sigma={blur}")
        vf += ["tpad=stop_mode=clone:stop=32", f"fps={fps}"]
        ff("-i", os.path.join(bdir, "depth.mp4"), "-vf", ",".join(vf),
           "-frames:v", str(frames), "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", guide)

        first_name, guides, used = None, [], []
        seg_files.clear()
        if si > 0 and seg.get("continue", True):
            prev = state.get(segments[si - 1]["id"])
            if not prev:
                raise SystemExit(f"segment {seg['id']} continues from {segments[si - 1]['id']}, "
                                 "which has no output yet")
            prev_last = sorted(glob.glob(os.path.join(prev, "*.png")))[-1]
            first_name = upload_still(prev_last, f"{seg['id']}_from_prev")
            cfg["keyframe_strength"] = 1.0
            used.append(f"<{segments[si - 1]['id']} last frame>")
        for spec in shot.get("keyframes", {}).get("frames", []):
            src = os.path.join(kdir, f"{spec['name']}.png")
            g = keyframe_index(spec["t"], fps)
            if g < 0:
                if not last_seg or args.seconds:
                    continue
                local = -1
            else:
                local = g - start
                if frames <= local < frames + 8:      # snapped past the last latent frame of this stretch: pin that one
                    local = ((frames - 1) // 8) * 8
                if local < 0 or local >= frames or (local == 0 and first_name):
                    continue
            if not os.path.exists(src):
                print(f"  keyframe '{spec['name']}' missing - run --stage keyframes")
                continue
            if local == 0:
                first_name = upload_still(src, spec["name"])
                cfg["keyframe_strength"] = spec.get("strength", 1.0)
            else:
                guides.append((upload_still(src, spec["name"]), local, spec.get("strength", 0.8)))
            used.append(spec["name"])
        if first_name is None:
            cfg["keyframe_strength"] = 0  # the i2v node still needs an image; it is bypassed
            first_name = upload_still(os.path.join(bdir, "first.png"), "blockout_first")
        print(f"  [{seg['id']}] {seg['range'][0]}-{seg['range'][1]}s, {frames} frames | keyframes: "
              f"{', '.join(used) or 'none'} | guide blur {blur}, strength {cfg.get('guide_strength', 1.0)}",
              flush=True)

        guide_name = ltx_comfy.upload(guide)
        for i in range(args.variants):
            seed = cfg.get("seed", 42) + i
            smp = "anc" if "ancestral" in cfg.get("sampler", "euler_ancestral_cfg_pp") else "det"
            tag = (f"{seg['id']}_{w}x{h}_{frames}f_s{seed}_{smp}_k{len(used)}_g{cfg.get('guide_strength', 1.0)}b{blur}"
                   f"{'_up' if cfg.get('upscale') else ''}")
            graph = ltx_comfy.build_graph(dict(cfg, seed=seed), guide_name, first_name, frames, w, h, fps,
                                          prefix=f"{shot['id']}/{tag}", guides=guides)
            if args.dry_run:
                path = os.path.join(gdir, f"graph.{seg['id']}.preview.json")
                with open(path, "w") as f:
                    json.dump(graph, f, indent=2)
                print(f"  dry run: graph with {len(graph)} nodes -> {path}")
                break
            # resume: a segment whose prompt, settings, guide, first frame and keyframes are as they were is kept, so a crash
            # in hour two of a long take (or an edit to one prompt) re-paints only what changed, and what follows it
            rkey = hashlib.sha1(json.dumps([cfg, digest_of([guide, *seg_files]), tag, i], sort_keys=True, default=str).encode()).hexdigest()[:16]
            keyfile = os.path.join(gdir, tag, "_resume.txt")
            if (i == 0 and not args.force and os.path.exists(keyfile) and open(keyfile).read() == rkey
                    and len(glob.glob(os.path.join(gdir, tag, "*.png"))) >= frames):
                print(f"  [{seg['id']}] kept: nothing it is made from changed", flush=True)
                if not args.seconds:
                    state[seg["id"]] = os.path.join(gdir, tag)
                    with open(state_path, "w") as f:
                        json.dump(state, f, indent=2)
                continue
            images = ltx_comfy.run(graph)
            fdir = ltx_comfy.fetch(images, os.path.join(gdir, tag))
            if i == 0:
                with open(keyfile, "w") as f:
                    f.write(rkey)
            mp4 = os.path.join(gdir, f"{tag}.mp4")
            ff("-framerate", str(fps), "-i", os.path.join(fdir, "%04d.png"), "-c:v", "libx264", "-crf", "14",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4)
            print(f"  saved {mp4}", flush=True)
            if i == 0 and not args.seconds:
                state[seg["id"]] = fdir  # first variant feeds the next segment and the final cut
                with open(state_path, "w") as f:
                    json.dump(state, f, indent=2)

    if args.dry_run or args.seconds or any(seg["id"] not in state for seg in segments):
        return
    # Join segments: later segments start on the previous last frame, so drop their first frame.
    cut = os.path.join(gdir, "_cut")
    shutil.rmtree(cut, ignore_errors=True)
    os.makedirs(cut)
    n = 0
    for si, seg in enumerate(segments):
        pngs = sorted(glob.glob(os.path.join(state[seg["id"]], "*.png")))
        for src in pngs[1 if si > 0 and seg.get("continue", True) else 0:]:
            n += 1
            shutil.copy(src, os.path.join(cut, f"{n:05d}.png"))
    ff("-framerate", str(fps), "-i", os.path.join(cut, "%05d.png"), "-c:v", "libx264", "-crf", "14",
       "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(gdir, "gen.mp4"))
    shutil.rmtree(cut, ignore_errors=True)
    print(f"  gen.mp4: {n} frames from {len(segments)} segment(s)")


PLATE_ENV_VERSION = 1
COMPOSITE_VERSION = 3


def _blender_pass(cmd, ctx, label):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    tail = []
    for line in p.stdout:
        tail = (tail + [line])[-40:]
        if line.startswith("FRAME ") and ctx is not None:
            n, total = line.split()[1].split("/")
            ctx.progress(int(n) / int(total) * 0.9, f"{label} frame {n}/{total}")
    if p.wait() != 0:
        raise RuntimeError(f"Blender {label} pass failed:\n" + "".join(tail))


def stage_track(out, res):
    """take.py --pass track: the camera per frame and the product's place on screen (product/track.json)."""
    pdir = os.path.join(out, "product")
    _blender_pass([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", os.path.join(SCRIPTS, "take.py"), "--",
                   "--take", os.path.join(out, "take.json"), "--pass", "track", "--out", pdir, "--res", f"{res[0]}x{res[1]}"],
                  None, "track")


def stage_product(shot, out, res, samples, ctx, env=None):
    """Cycles renders the product alone, RGBA with its shadow, through the take's camera (take.py --pass product),
    lit by the plate environments (env.json) unless the layer names a studio `hdri`."""
    pdir = os.path.join(out, "product")
    shutil.rmtree(os.path.join(pdir, "frames"), ignore_errors=True)
    cmd = [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", os.path.join(SCRIPTS, "take.py"), "--",
           "--take", os.path.join(out, "take.json"), "--pass", "product", "--out", pdir,
           "--res", f"{res[0]}x{res[1]}", "--samples", str(samples)]
    if env:
        cmd += ["--env", str(env)]
    print("  $ blender take.py --pass product" + (" (plate light)" if env else ""), flush=True)
    _blender_pass(cmd, ctx, "product")


def _read_frame(film, t, w, h):
    """One frame of the plate at t seconds, as float RGB 0-1 at w x h."""
    import numpy as np
    p = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(film), "-frames:v", "1",
                        "-vf", f"scale={w}:{h}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    if p.returncode != 0 or len(p.stdout) < w * h * 3:
        raise RuntimeError(f"could not read the plate at {t:.2f}s: {p.stderr.decode(errors='replace')[-400:]}")
    return np.frombuffer(p.stdout[:w * h * 3], np.uint8).reshape(h, w, 3).astype(np.float32) / 255


def _srgb_to_linear(x):
    import numpy as np
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def env_from_frame(lin, M, lens, sensor, aspect, W=1024, H=512, lift=3.0):
    """An equirect environment (Blender's layout, world axes, float linear RGB) from one frame seen by a camera.

    lin: the frame as linear float RGB (h, w, 3); M: the camera's 4x4 matrix_world; lens/sensor in mm (sensor fit
    AUTO); aspect: the frame's width / height. Directions inside the frame sample it (lightly blurred); outside,
    its blurred edges continue and fade towards its own sky (top band) and ground (bottom band). Highlights are
    lifted, since a plate is LDR and its bright sky stands in for the light sources."""
    import cv2
    import numpy as np
    fh, fw = lin.shape[:2]
    u = (np.arange(W) + 0.5) / W
    v = 1 - (np.arange(H) + 0.5) / H
    LON, LAT = np.meshgrid((u - 0.5) * 2 * np.pi, (v - 0.5) * np.pi)
    dx, dy, dz = -np.cos(LAT) * np.cos(LON), np.cos(LAT) * np.sin(LON), np.sin(LAT)
    R = np.array(M, dtype=np.float64)[:3, :3]
    cx = R[0, 0] * dx + R[1, 0] * dy + R[2, 0] * dz
    cy = R[0, 1] * dx + R[1, 1] * dy + R[2, 1] * dz
    fwd = -(R[0, 2] * dx + R[1, 2] * dy + R[2, 2] * dz)
    k = lens / sensor
    safe = np.maximum(fwd, 1e-4)
    if aspect >= 1:
        px, py = 0.5 + k * cx / safe, 0.5 - k * aspect * cy / safe
    else:
        px, py = 0.5 + k / aspect * cx / safe, 0.5 - k * cy / safe
    inside = (fwd > 0) & (px >= 0) & (px <= 1) & (py >= 0) & (py <= 1)
    sky = lin[: max(1, fh // 6)].reshape(-1, 3).mean(0)
    ground = lin[-max(1, fh // 6):].reshape(-1, 3).mean(0)
    sharp = cv2.GaussianBlur(lin, (0, 0), 1.2)
    soft = cv2.GaussianBlur(lin, (0, 0), 18 * max(fw, fh) / 480)
    mx = (np.clip(px, 0, 1) * (fw - 1)).astype(np.float32)
    my = (np.clip(py, 0, 1) * (fh - 1)).astype(np.float32)
    a = cv2.remap(sharp, mx, my, cv2.INTER_LINEAR)
    b = cv2.remap(soft, mx, my, cv2.INTER_LINEAR)
    outside = np.maximum(np.maximum(-px, px - 1), np.maximum(-py, py - 1))
    outside = np.where(fwd > 0, np.clip(outside, 0, None), 9.0)
    horizon = np.clip(np.abs(dz) / 0.25, 0, 1)[..., None]
    fall = np.where(dz[..., None] > 0, sky, ground) * horizon + ((sky + ground) / 2) * (1 - horizon)
    wout = np.clip(outside / 0.6, 0, 1)[..., None]
    env = np.where(inside[..., None], a, b * (1 - wout) + fall * wout)
    env = cv2.GaussianBlur(env.astype(np.float32), (0, 0), 3)
    lum = env @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    gain = 1 + lift * np.clip((lum - 0.55) / 0.45, 0, 1) ** 2
    return (env * gain[..., None]).astype(np.float32)


def env_sun(env):
    """Direction (world, unit) and relative strength of the brightest region of an equirect environment."""
    import cv2
    import numpy as np
    H, W = env.shape[:2]
    lum = cv2.GaussianBlur(env @ np.array([0.2126, 0.7152, 0.0722], np.float32), (0, 0), 6)
    lum[H // 2 + H // 20:] *= 0.2           # the light comes from above the horizon
    y, x = np.unravel_index(int(np.argmax(lum)), lum.shape)
    lon, lat = ((x + 0.5) / W - 0.5) * 2 * np.pi, ((1 - (y + 0.5) / H) - 0.5) * np.pi
    lat = max(lat, np.radians(28))           # a window behind the subject still lights it from above, never below
    d = [-np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    contrast = float(lum.max() / max(float(np.median(lum)), 1e-4))
    return [round(float(c), 4) for c in d], round(min(contrast, 8.0), 3)


def stage_plate_env(film, track, env_json, fps, log=print):
    """Environment maps made from the generated frames themselves, one every ~2.5 s of the take (env_from_frame),
    cross-faded by take.py, plus the ground's colour under the product for the shadow catcher."""
    import cv2
    import numpy as np
    with open(track, encoding="utf-8") as f:
        T = json.load(f)
    frames = T["frames"]
    n = len(frames)
    dur = n / fps
    count = max(2, int(round(dur / 2.5)) + 1)
    times = [min(dur - 1.0 / fps, i * dur / (count - 1)) for i in range(count)]
    out_dir = os.path.dirname(str(env_json))
    os.makedirs(out_dir, exist_ok=True)
    fw, fh = 480, 270
    sw, sh = T["size"]
    keys, grounds = [], []
    for i, t in enumerate(times):
        rec = frames[min(n - 1, int(round(t * fps)))]
        lin = _srgb_to_linear(_read_frame(film, t, fw, fh)).astype(np.float32)
        if rec.get("visible") and rec.get("base"):
            bx, by = rec["base"]
            x, y = int(np.clip(bx * fw, 4, fw - 5)), int(np.clip(by * fh + fh * 0.03, 4, fh - 5))
            patch = lin[max(0, y - 8):y + 8, max(0, x - 16):x + 16].reshape(-1, 3)
            if len(patch):
                grounds.append(patch.mean(0))
        env = env_from_frame(lin, rec["camera"], float(T["lens"]), float(T["sensor"]), sw / sh)
        path = os.path.join(out_dir, f"env_{i:02d}.hdr")
        cv2.imwrite(path, env[..., ::-1])
        keys.append({"t": round(t, 3), "file": path})
    ground = (np.median(np.array(grounds), axis=0) if grounds else np.array([0.18, 0.18, 0.18])).tolist()
    with open(env_json, "w", encoding="utf-8") as f:
        json.dump({"keys": keys, "ground": [round(c, 4) for c in ground], "strength": 1.0}, f, indent=1)
    log(f"  plate light: {len(keys)} environments from the generated frames")


class PlateMatch:
    """Grades a product pass to its plate, frame after frame: black level, white balance and saturation from the
    plate (smoothed over time so nothing flickers), the plate's softness and grain, and a light wrap of the plate's
    colour at the product's rim. The shadow (alpha over black RGB) takes the plate's black level."""

    def __init__(self, grade=True, grain=None, soften=0.0, seed=7, tint=0.25):
        import numpy as np
        self.grade, self.sigma, self.soften, self.tint = grade, grain, soften, tint
        self.state = None
        self.rng = np.random.default_rng(seed)
        self.luma = np.array([0.2126, 0.7152, 0.0722], np.float32)

    def apply(self, plate, rgba):
        """plate: float RGB 0-1 (h, w, 3); rgba: float straight-alpha RGBA 0-1, same size. Returns float RGB."""
        import cv2
        import numpy as np
        rgb, al = rgba[..., :3], rgba[..., 3:4]
        if self.grade:
            luma = self.luma
            small = cv2.resize(plate, (160, 90), interpolation=cv2.INTER_AREA).reshape(-1, 3)
            lum = small @ luma
            black = np.percentile(small, 1.0, axis=0)
            mid = small[(lum > np.percentile(lum, 25)) & (lum < np.percentile(lum, 85))]
            mean = mid.mean(0) if len(mid) else small.mean(0)
            tint = mean / max(float(mean @ luma), 1e-3)
            sat = float(np.mean(small.max(1) - small.min(1)))
            if self.sigma is None:
                g = cv2.cvtColor((plate * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
                hp = g - cv2.GaussianBlur(g, (0, 0), 1.5)
                self.sigma = float(np.clip(np.median(np.abs(hp)) * 1.4826, 0, 6))
            cur = np.concatenate([black, tint, [sat]])
            self.state = cur if self.state is None else self.state * 0.92 + cur * 0.08
            black, tint, sat = self.state[:3], self.state[3:6], self.state[6]
            # white balance a quarter of the way to the plate's mid-tone tint (the plate light already colours
            # it), saturation nudged towards the plate's
            rgb = rgb * (1 + self.tint * (tint - 1))
            solid = al[..., 0] > 0.5
            prod_sat = float(np.mean((rgb.max(2) - rgb.min(2))[solid])) if solid.any() else sat
            k = float(np.clip(sat / max(prod_sat, 1e-3), 0.75, 1.1))
            y = (rgb @ luma)[..., None]
            rgb = y + (rgb - y) * k
            rgb = black + (1 - black) * np.clip(rgb, 0, 1)            # lift blacks to the plate's black level
            if self.soften > 0.05:
                rgb = cv2.GaussianBlur(rgb, (0, 0), self.soften)
                al = cv2.GaussianBlur(al[..., 0], (0, 0), self.soften * 0.8)[..., None]
            blur_pl = cv2.GaussianBlur(plate, (0, 0), 6)
            edge = np.clip(al[..., 0] - cv2.erode(al[..., 0], np.ones((5, 5), np.uint8)), 0, 1)[..., None]
            rgb = rgb * (1 - 0.35 * edge) + blur_pl * 0.35 * edge
            if self.sigma:
                rgb = rgb + self.rng.normal(0, self.sigma / 255, rgb.shape[:2] + (1,)).astype(np.float32)
        return plate * (1 - al) + np.clip(rgb, 0, 1) * al


def read_rgba(path, size):
    """A product frame as float straight-alpha RGBA at size (w, h), or None when it is empty."""
    import cv2
    import numpy as np
    rgba = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if rgba is None or rgba.ndim < 3 or rgba.shape[2] < 4 or not rgba[..., 3].any():
        return None
    rgba = cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA).astype(np.float32) / (65535 if rgba.dtype == np.uint16 else 255)
    if rgba.shape[1::-1] != tuple(size):
        rgba = cv2.resize(rgba, tuple(size), interpolation=cv2.INTER_AREA)
    return rgba


def plate_softness(film, height):
    """Blur (px) that matches a crisp render to a plate upscaled from a lower resolution."""
    src_h = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height",
                                "-of", "csv=p=0", str(film)], capture_output=True, text=True).stdout.strip() or height)
    return max(0.0, 0.45 * (height / max(src_h, 1) - 1))


def stage_composite(film, pdir, dst, fps, res, grade=True, grain=None, track=None, log=print):
    """The product frames over the generated world, graded to it (PlateMatch), encoded for the film stages."""
    import numpy as np
    w, h = res
    pngs = sorted(glob.glob(os.path.join(pdir, "frames", "*.png")))
    match = PlateMatch(grade, grain, plate_softness(film, h) if grade else 0.0)
    dec = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(film),
                            "-vf", f"scale={w}:{h}:flags=lanczos,fps={fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "medium",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)], stdin=subprocess.PIPE)
    count = 0
    for path in pngs:
        raw = dec.stdout.read(w * h * 3)
        if len(raw) < w * h * 3:
            break
        rgba = read_rgba(path, (w, h))
        if rgba is None:
            enc.stdin.write(raw)
        else:
            plate = np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32) / 255
            out = match.apply(plate, rgba)
            enc.stdin.write((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        count += 1
    # the film ends with the product pass (LTX's 8k+1 frames leave one plate frame over): never a frame without it
    dec.stdout.close()
    dec.kill()
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("compositing the take failed (ffmpeg)")
    dec.wait()
    print(f"  take.mp4: world + product ({count} frames) at {w}x{h}"
          + (f", graded to the plate (grain {match.sigma or 0:.1f}, soften {match.soften:.2f}px)" if grade else ""), flush=True)


def stage_upscale(shot, out, args):
    """Upscale the finished film in overlapping, cross-faded chunks.

    method "seedvr2" (default): SeedVR2 restoration -> 4K (gen/gen_4k.mp4). Removes the render's grain
      and redraws fine detail; shot["upscale"]: resolution (short side, 2160), batch_size (4n+1),
      blocks_to_swap, chunk, overlap.
    method "ltx": LTX latent upsampler + short refine -> 2x (gen/gen_up.mp4); sigmas, chunk, overlap.
    """
    import numpy as np
    from PIL import Image
    ucfg = dict(ltx_comfy.LTX, **shot["ltx"], **shot.get("upscale", {}))
    ucfg.pop("segments", None)
    method = ucfg.get("method", "seedvr2")
    fps = shot["fps"]
    gdir = os.path.join(out, "gen")
    src = args.source or os.path.join(gdir, "gen.mp4")
    if not os.path.exists(src):
        raise SystemExit(f"nothing to upscale: {src} - run --stage generate first")
    # Cache key = method + target + the exact source file, so a re-rendered film or a new target size
    # never reuses stale chunks (that once passed off an old 4K chunk as a new 1440p test).
    st_ = os.stat(src)
    tag = f"{method}{ucfg.get('resolution', 2160) if method == 'seedvr2' else 'x2'}_{st_.st_size}_{int(st_.st_mtime)}"
    key = hashlib.md5(tag.encode()).hexdigest()[:8]  # short: Windows tools fail on paths > 260 chars
    udir = os.path.join(gdir, "up", key)
    os.makedirs(udir, exist_ok=True)
    if not args.dry_run:
        ltx_comfy.free()

    total = int(subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
         "stream=nb_read_frames", "-of", "csv=p=0", src], capture_output=True, text=True, check=True).stdout.strip())
    # 4K frames are held as float32 in RAM (~100 MB each), so SeedVR2 works in shorter chunks.
    chunk = ucfg.get("chunk", 49 if method == "seedvr2" else 97)
    overlap = ucfg.get("overlap", 8 if method == "seedvr2" else 16)
    starts = list(range(0, max(total - chunk, 0) + 1, chunk - overlap))
    if starts[-1] + chunk < total:
        starts.append(total - chunk)  # last chunk ends exactly on the final frame
    if args.seconds:
        starts = starts[:1]

    segments = shot["ltx"].get("segments") or [{"range": [0, shot["duration"]], "prompt": shot["ltx"].get("prompt", "")}]

    def prompt_at(frame):
        t = frame / fps
        for seg in segments:
            if seg["range"][0] <= t <= seg["range"][1]:
                return seg.get("prompt") or shot["ltx"].get("prompt", "")
        return segments[-1].get("prompt") or shot["ltx"].get("prompt", "")

    detail = (f"SeedVR2 {ucfg.get('model', '7b sharp fp8')} -> {ucfg.get('resolution', 2160)}p, batch {ucfg.get('batch_size', 9)}"
              if method == "seedvr2" else f"LTX 2x, sigmas {ucfg.get('sigmas', '0.725, 0.421875, 0.0')}")
    print(f"  {total} frames -> {len(starts)} chunk(s) of {chunk} (overlap {overlap}) | {detail}")
    chunk_dirs = []
    for ci, s in enumerate(starts):
        cdir = os.path.join(udir, f"c{ci:02d}")
        n = min(chunk, total - s)
        if os.path.isdir(cdir) and len(glob.glob(os.path.join(cdir, "*.png"))) >= n and not args.force:
            print(f"  chunk {ci} (frames {s}-{s + n - 1}) already done")
            chunk_dirs.append((s, cdir))
            continue
        clip = os.path.join(udir, f"in{ci:02d}.mp4")
        ff("-i", src, "-vf", f"trim=start_frame={s}:end_frame={s + chunk},setpts=PTS-STARTPTS,"
           f"tpad=stop_mode=clone:stop={chunk},fps={fps}", "-frames:v", str(chunk),
           "-c:v", "libx264", "-crf", "8", "-pix_fmt", "yuv420p", clip)
        if method == "seedvr2":
            graph = ltx_comfy.build_seedvr2_graph(ucfg, ltx_comfy.upload(clip), prefix=f"{shot['id']}/uhd_{ci:02d}")
        else:
            graph = ltx_comfy.build_upscale_graph(ucfg, ltx_comfy.upload(clip), chunk, fps,
                                                  prompt_at(s + chunk // 2), prefix=f"{shot['id']}/up_{ci:02d}")
        if args.dry_run:
            print(f"  dry run: chunk {ci} graph with {len(graph)} nodes")
            return
        print(f"  chunk {ci + 1}/{len(starts)}: frames {s}-{s + n - 1}", flush=True)
        images = ltx_comfy.run(graph)
        ltx_comfy.fetch(images[:n], cdir)
        chunk_dirs.append((s, cdir))

    # Stitch: linear cross-fade across each overlap.
    final = os.path.join(udir, "frames")
    shutil.rmtree(final, ignore_errors=True)
    os.makedirs(final)
    owner = {}
    for s, cdir in chunk_dirs:
        for i, path in enumerate(sorted(glob.glob(os.path.join(cdir, "*.png")))):
            owner.setdefault(s + i, []).append(path)
    for f in range(total if not args.seconds else len(owner)):
        paths = owner[f]
        if len(paths) == 1:
            shutil.copy(paths[0], os.path.join(final, f"{f + 1:05d}.png"))
            continue
        # frame f sits in the tail of the earlier chunk and the head of the later one
        a, b = paths[0], paths[-1]
        later_start = max(s for s, _ in chunk_dirs if s <= f)
        earlier_end = max(s + chunk - 1 for s, _ in chunk_dirs if s < later_start)
        span = max(earlier_end - later_start, 1)
        w = (f - later_start) / span
        img = (1 - w) * np.asarray(Image.open(a), dtype=np.float32) + w * np.asarray(Image.open(b), dtype=np.float32)
        Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(final, f"{f + 1:05d}.png"))
    dst = os.path.join(gdir, "gen_sr.mp4" if method == "seedvr2" else "gen_up.mp4")
    if args.seconds:  # a test chunk must never replace the real film
        dst = dst.replace(".mp4", "_test.mp4")
    ff("-framerate", str(fps), "-i", os.path.join(final, "%05d.png"), "-c:v", "libx264", "-crf", "14",
       "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst)
    w, h = Image.open(os.path.join(final, "00001.png")).size
    print(f"  {os.path.basename(dst)}: {len(os.listdir(final))} frames at {w}x{h}")


def stage_generate_wan(shot, out, wout, args, log=print):
    """A take's world painted by Wan 2.2 Fun Control (`video_model: wan`): the Blender depth guide is the control
    video, so the world follows the exact camera the product is rendered through.

    Same segments and prompts as `ltx:`. Wan runs at 16 fps in clips of <= 81 frames: a longer segment is split
    into even clips. The first clip starts on the keyframe at its start time (if any; also a segment with
    `continue: false`); every later clip starts on the previous clip's real last frame, so the joins are seamless. Each clip also gets a reference still (the keyframe inside
    its range, else the first keyframe) that steers the look. The joined 16 fps frames are retimed to the take's fps
    (FFmpeg minterpolate by default) so frame i matches the product pass frame i. Writes <wout>/gen/gen.mp4.
    """
    import time
    from pathlib import Path
    from ..animate import retime, wan_size, wan_split
    wan = dict(shot.get("wan") or {})
    ltx = shot["ltx"]
    fps, wfps = shot["fps"], ltx_comfy.WAN_FPS
    pw, ph = shot["preview_res"]
    w, h = wan_size(pw, ph, wan.get("res"))
    bdir = os.path.join(out, "blockout")
    kdir = os.path.join(out, "keyframes")
    gdir = os.path.join(wout, "gen")
    os.makedirs(gdir, exist_ok=True)
    seed0 = wan.get("seed", ltx.get("seed", 42))
    neg = wan.get("negative_prompt") or ltx.get("negative_prompt", "")
    blur = wan["guide_blur"] if wan.get("guide_blur") is not None else ltx.get("guide_blur", 0)
    keys = []
    for spec in shot.get("keyframes", {}).get("frames", []):
        t = shot["duration"] if spec["t"] == "end" else float(spec["t"])
        src = os.path.join(kdir, f"{spec['name']}.png")
        if os.path.exists(src):
            keys.append((t, src))
    keys.sort()

    # clips: (prompt, first 16 fps frame, frame count), segment by segment
    clips = []
    segments = ltx.get("segments") or [{"id": "main", "range": [0, shot["duration"]], "prompt": ltx.get("prompt", "")}]
    if args.seconds:
        segments = [dict(segments[0], range=[segments[0]["range"][0], segments[0]["range"][0] + args.seconds])]
    for seg in segments:
        a = int(round(seg["range"][0] * wfps))
        n = max(5, (int(round(seg["range"][1] * wfps)) - a) // 4 * 4 + 1)
        for k in wan_split(n, int(wan.get("max_frames", ltx_comfy.WAN_MAX_FRAMES))):
            fresh = not clips or (a == int(round(seg["range"][0] * wfps)) and not seg.get("continue", True))
            clips.append((seg.get("prompt") or ltx.get("prompt", ""), a, k, seg["id"], fresh))
            a += k - 1

    def still(src, name):
        dst = os.path.join(gdir, f"{name}_{w}x{h}.png")
        ff("-i", src, "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}", dst)
        return ltx_comfy.upload(dst)

    raw = os.path.join(gdir, "frames16")
    shutil.rmtree(raw, ignore_errors=True)
    os.makedirs(raw)
    ltx_comfy.free()
    n_out, start = 0, None
    for ci, (prompt, a, k, sid, fresh) in enumerate(clips):
        t0, t1 = a / wfps, (a + k - 1) / wfps
        if fresh:   # the take's first clip (or a segment with continue: false) starts on its keyframe, if one is there
            at = [src for t, src in keys if abs(t - t0) <= 0.5 / wfps]
            start = still(at[0], f"start{ci}") if at else None
        inside = [src for t, src in keys if t0 <= t <= t1]
        ref_src = inside[0] if inside else (keys[0][1] if keys else None)
        ref = still(ref_src, f"ref{ci}") if ref_src and wan.get("ref", True) else None
        guide = os.path.join(gdir, f"guide{ci}_{w}x{h}_{a}_{k}_b{blur}.mp4")
        vf = [f"fps={wfps}", f"trim=start_frame={a}", "setpts=PTS-STARTPTS",
              f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={w}:{h}"]
        if blur:
            vf.append(f"gblur=sigma={blur}")
        vf += ["tpad=stop_mode=clone:stop=32"]
        ff("-i", os.path.join(bdir, "depth.mp4"), "-vf", ",".join(vf), "-frames:v", str(k),
           "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", "-r", str(wfps), guide)
        log(f"  [wan {sid} {ci + 1}/{len(clips)}] {t0:.2f}-{t1:.2f}s, {k} frames at {w}x{h} | start: "
            f"{'none' if not start else 'keyframe' if fresh else 'previous clip'} | ref: "
            f"{os.path.basename(ref_src) if ref else 'none'}")
        t = time.time()
        graph = ltx_comfy.build_wan_graph(wan, prompt, neg, w, h, k, seed0 + ci, prefix=f"{shot['id']}/wan_{ci:02d}",
                                          start_image=start, control_video=ltx_comfy.upload(guide), ref_image=ref)
        cdir = ltx_comfy.fetch(ltx_comfy.run(graph), os.path.join(gdir, f"_c{ci:02d}"))
        pngs = sorted(glob.glob(os.path.join(cdir, "*.png")))
        for p in pngs[1 if ci else 0:]:
            n_out += 1
            shutil.move(p, os.path.join(raw, f"{n_out:04d}.png"))
        shutil.rmtree(cdir, ignore_errors=True)
        log(f"  clip {ci + 1}: {k} frames in {time.time() - t:.0f}s")
        start = still(os.path.join(raw, f"{n_out:04d}.png"), f"chain{ci}")
    ltx_comfy.free()
    frames = retime(Path(raw), Path(gdir) / "frames24", wfps, fps, None, wan.get("interpolate", "mci"), log)
    ff("-framerate", str(fps), "-i", os.path.join(gdir, "frames24", "%04d.png"), "-c:v", "libx264", "-crf", "14",
       "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(gdir, "gen.mp4" if not args.seconds else "gen_test.mp4"))
    log(f"  gen.mp4 (wan): {n_out} frames at {wfps} fps -> {len(frames)} at {fps} fps")
