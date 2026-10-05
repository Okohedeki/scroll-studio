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
import sys

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
        raise RuntimeError(f"{os.path.basename(str(cmd[0]))} failed ({p.returncode}):
{(p.stderr or p.stdout)[-3000:]}")


def ff(*args):
    sh([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args])


def stage_blockout(shot, out):
    bdir = os.path.join(out, "blockout")
    w, h = shot["preview_res"]
    bl = shot.get("blockout", {})
    if bl.get("file"):   # user scene: its camera animation drives the shot
        cmd = [BLENDER, "-b", bl["file"], "--python-exit-code", "1", "--python", os.path.join(SCRIPTS, "file_blockout.py"), "--"]
    else:
        cmd = [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "-P", os.path.join(SCRIPTS, "presets", bl.get("preset", "rocket_launch").replace("-", "_") + ".py"), "--"]
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
    kcfg = shot["keyframes"]
    w, h = kcfg.get("res", [1536, 864])
    bdir = os.path.join(out, "blockout")
    kdir = os.path.join(out, "keyframes")
    os.makedirs(kdir, exist_ok=True)
    depth_frames = sorted(glob.glob(os.path.join(bdir, "depth", "*.png")))
    for spec in kcfg["frames"]:
        name = spec["name"]
        if args.only and name != args.only:
            continue
        idx = keyframe_index(spec["t"], shot["fps"])
        depth_src = depth_frames[idx if idx < 0 else min(idx, len(depth_frames) - 1)]
        depth = os.path.join(kdir, f"depth_{name}_{w}x{h}.png")
        blur = spec.get("depth_blur", 0)
        ff("-i", depth_src, "-vf", f"scale={w}:{h}:flags=lanczos" + (f",gblur=sigma={blur}" if blur else ""), depth)
        depth_name = ltx_comfy.upload(depth)
        spec_cfg = dict(kcfg, control_strength=spec.get("control_strength", kcfg.get("control_strength", 0.8)))
        for i in range(args.variants):
            seed = kcfg.get("seed", 7) + i
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
    base = dict(shot["ltx"])
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

    def upload_still(src, name):
        dst = os.path.join(gdir, f"{name}_{shot['id']}_{w}x{h}.png")
        ff("-i", src, "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}", dst)
        return ltx_comfy.upload(dst)

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
            images = ltx_comfy.run(graph)
            fdir = ltx_comfy.fetch(images, os.path.join(gdir, tag))
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


def stage_upscale(shot, out, args):
    """Upscale the finished film in overlapping, cross-faded chunks.

    method "seedvr2" (default): SeedVR2 restoration -> 4K (gen/gen_4k.mp4). Removes the render's grain
      and redraws fine detail; shot["upscale"]: resolution (short side, 2160), batch_size (4n+1),
      blocks_to_swap, chunk, overlap.
    method "ltx": LTX latent upsampler + short refine -> 2x (gen/gen_up.mp4); sigmas, chunk, overlap.
    """
    import numpy as np
    from PIL import Image
    ucfg = dict(shot["ltx"], **shot.get("upscale", {}))
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
