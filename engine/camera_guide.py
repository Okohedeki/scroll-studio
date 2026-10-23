"""camera_guide: keyed camera moves on moving (video) beats.

A video model takes camera direction only as words, which it mostly ignores, so "the crowd keeps walking while the
camera pushes in to the girl" used to be impossible: a clip, then a cut to a still. A beat with `camera:` keys gets the
camera it asks for by construction, in four steps (each cached by its own digest in the beat's folder):

    still.png     the beat's start image, fitted to beat_res
    depth.npy     Depth Anything V2 depth of that image (the freeze pipeline's prepare_depth: edge-snapped)
    people.png    the moving subjects (`camera.subjects`, found by Florence-2, cut out by SAM 2.1: engine/region.py)
    guide.mp4     the camera path flown through the image's depth with the freeze renderer (engine/freeze.py), as a
                  depth video, with the moving subjects softened into blobs so the guide fixes the camera and the static
                  world (street, buildings, lamps) but leaves the people free to walk. Beside it: guide_rgb.mp4 (the
                  same move flown through the picture itself, a pure-camera preview and the reference the follow
                  measurement compares against) and guide_static.mp4 (where the static world is, per frame).

The guide then steers a video model along the same machinery a take uses: LTX-2.3 with the IC-LoRA union control
(`build_graph`, the depth guide of film takes) or Wan 2.2 Fun Control (`build_wan_graph`, the guide as the control
video), or Uni3C (the purpose-built camera controlnet; needs a file that is not installed by default).

Whether the camera really follows the keys is measured, not assumed: `follow_error` registers every generated frame
against the pure-camera render of the first frame and reports how far the view is from the keyed one.
"""
from __future__ import annotations

import math
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import freeze as fz
from .freeze import FPS, CameraPath, View
from .project import BuildError

VERSION = 5


# ---------------------------------------------------------------- the path

def camera_path(move) -> CameraPath:
    """The beat's own CameraPath (same keys, same easing as a frozen moment's)."""
    return CameraPath(move.keys, move.ease)


@dataclass
class CameraPlan:
    """The camera over one beat: a path over some stretch [lo, hi] of 0-1. Alone a beat covers all of [0, 1] of its own
    path. Beats that `continue` one another share one smooth path over the whole chain (it rests only at the chain's ends
    and on holds, so the camera's position AND speed carry across each cut), and each covers its own slice."""
    path: CameraPath
    lo: float = 0.0
    hi: float = 1.0

    def at(self, t: float) -> View:
        return self.path.at(self.lo + (self.hi - self.lo) * min(1.0, max(0.0, t)))

    def keys(self, n: int) -> list[dict]:
        """`n` keys, one per frame (t = i / (n - 1)), that reproduce this plan under linear easing: what the freeze
        renderer takes as its camera, so any plan (a slice of a chain, say) renders through the unchanged renderer."""
        out = []
        for i in range(n):
            v = self.at(i / max(n - 1, 1))
            out.append({"t": i / max(n - 1, 1), "box": [v.cx - v.w / 2, v.cy - v.w / 2, v.cx + v.w / 2, v.cy + v.w / 2], "hold": 0.0})
        return out


def chain_of(beats: list, i: int) -> list[int]:
    """Indices of the beats whose camera is one chain with beat `i`: consecutive camera beats, each after the first
    `continues` the one before."""
    lo = i
    while beats[lo].camera is not None and beats[lo].camera.continues and lo > 0 and beats[lo - 1].camera is not None:
        lo -= 1
    hi = i
    while hi + 1 < len(beats) and beats[hi + 1].camera is not None and beats[hi + 1].camera.continues:
        hi += 1
    return list(range(lo, hi + 1))


def plan_for(beats: list, i: int) -> CameraPlan:
    """The CameraPlan of beat `beats[i]` (which has `camera`), alone or as part of a `continues` chain."""
    chain = chain_of(beats, i)
    if len(chain) == 1:
        return CameraPlan(camera_path(beats[i].camera))
    total = sum(beats[j].seconds for j in chain)
    keys, t0 = [], 0.0
    for j in chain:
        b = beats[j]
        for k in b.camera.keys:
            keys.append({"t": (t0 + k.t * b.seconds) / total, "box": list(k.box), "hold": k.hold * b.seconds / total})
        t0 += b.seconds
    path = CameraPath(keys, "flow")
    off = sum(beats[j].seconds for j in chain if j < i)
    return CameraPlan(path, off / total, (off + beats[i].seconds) / total)


def view_at(move, t: float) -> View:
    return camera_path(move).at(t)


# ---------------------------------------------------------------- the guide's pictures

def soften_subjects(depth: np.ndarray, people: np.ndarray, sigma: float, grow: int = 6) -> np.ndarray:
    """`depth` with the moving subjects turned into soft blobs: inside the (grown) mask the depth is the mask-weighted
    blur of the subjects' own depth, so a guide still says "something stands here, this far away" but not "this
    exact silhouette, in this exact pose". `people` is uint8 0-255. sigma is in pixels (0 keeps the depth as it is)."""
    import cv2
    if sigma <= 0:
        return depth
    m = (people > 127).astype(np.uint8) * 255
    if grow > 0:
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
    soft = cv2.GaussianBlur(m, (0, 0), max(1.0, grow / 2)).astype(np.float32) / 255
    num = cv2.GaussianBlur(depth * soft, (0, 0), sigma)
    den = cv2.GaussianBlur(soft, (0, 0), sigma)
    blob = num / np.maximum(den, 1e-4)
    return (depth * (1 - soft) + blob * soft).astype(np.float32)


def _gray3(a: np.ndarray) -> np.ndarray:
    u8 = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    return np.repeat(u8[..., None], 3, axis=2)


def render_streams(rgb: np.ndarray, depth: np.ndarray, people: Optional[np.ndarray], move, plan: CameraPlan, *,
                   size: tuple[int, int], n_frames: int, soften: float, seed: int = 7, device: Optional[str] = None):
    """Yield (guide depth, pure-camera rgb, static-world mask) frames (uint8 arrays: HxWx3, HxWx3, HxW) of the camera
    flown through the image. `n_frames` frames, the camera at t = i / (n - 1); the three streams use one camera path
    and one geometry, so they agree pixel for pixel."""
    W, H = size
    geom = soften_subjects(depth, people, soften) if people is not None else depth
    kw = dict(size=size, seconds=n_frames / FPS, parallax=move.parallax, dolly=move.dolly, ease="linear", seed=seed,
              device=device)
    keys = plan.keys(n_frames)
    g_d = fz.render_frames(_gray3(geom), geom, keys, **kw)
    g_c = fz.render_frames(np.asarray(rgb), geom, keys, **kw)
    stat = (255 - (people if people is not None else np.zeros((H, W), np.uint8))).astype(np.uint8)
    g_m = fz.render_frames(np.repeat(stat[..., None], 3, axis=2), geom, keys, **kw)
    for d, c, m in zip(g_d, g_c, g_m):
        yield d, c, m[..., 0]


@dataclass
class Guide:
    depth: Path          # guide.mp4, what steers the model
    rgb: Path            # guide_rgb.mp4, the picture flown along the same path
    static: Path         # guide_static.mp4, 255 where the static world is
    frames: int
    fps: int


def write_guide(out_dir: Path, rgb: np.ndarray, depth: np.ndarray, people: Optional[np.ndarray], move, plan: CameraPlan, *,
                size: tuple[int, int], n_frames: int, fps: int, soften: float, seed: int = 7,
                name: str = "guide", log: Callable = print) -> Guide:
    """Render the three guide videos into `out_dir` (lossless-ish H.264, `fps` frames a second)."""
    import subprocess
    from .config import settings
    W, H = size
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{name}.mp4", out_dir / f"{name}_rgb.mp4", out_dir / f"{name}_static.mp4"]
    procs = []
    for p in paths:
        procs.append(subprocess.Popen([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                                       "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264",
                                       "-crf", "10", "-preset", "fast", "-pix_fmt", "yuv420p", str(p)], stdin=subprocess.PIPE))
    try:
        for d, c, m in render_streams(rgb, depth, people, move, plan, size=size, n_frames=n_frames, soften=soften, seed=seed):
            procs[0].stdin.write(d.tobytes())
            procs[1].stdin.write(c.tobytes())
            procs[2].stdin.write(np.repeat(m[..., None], 3, axis=2).tobytes())
    finally:
        for p in procs:
            p.stdin.close()
        rcs = [p.wait() for p in procs]
    if any(rcs):
        raise BuildError(f"ffmpeg failed encoding the camera guide (exit {rcs})")
    return Guide(paths[0], paths[1], paths[2], n_frames, fps)


# ---------------------------------------------------------------- generating along the guide

NEGATIVE = ("static camera, camera shake, flicker, morphing, warped body, extra limbs, new objects appearing, text, "
            "watermark, blur, cuts")


def _unique(path: Path, tag: str) -> Path:
    """A copy of `path` under a name that cannot collide in ComfyUI's input folder (uploads overwrite by name)."""
    import hashlib
    h = hashlib.sha1(path.read_bytes()).hexdigest()[:10]
    dst = path.with_name(f"cam_{tag}_{h}{path.suffix}")
    if not dst.exists():
        shutil.copy2(path, dst)
    return dst


def ltx_frames(seconds: float) -> int:
    from .animate import frames_for
    return frames_for(seconds)


def generate_ltx(still: Path, guide: Path, text: str, negative: str, size: tuple[int, int], frames: int, seed: int,
                 work: Path, guide_strength: float = 1.0, log: Callable = print, sampler: str = "euler_ancestral_cfg_pp",
                 control_strength: float = 1.0, keyframe_strength: float = 1.0,
                 anchors: Optional[list[tuple[Path, int, float]]] = None) -> list[Path]:
    """The beat painted by LTX-2.3 along the depth guide: the IC-LoRA union control a take uses (`build_graph`), with
    the start image as the pinned first frame. `anchors`: (image, frame index (-1: the last), strength) keyframes pinned along
    the way (a take's keyframe guides: `LTXVAddGuide`), which keep what things look like. Returns the frames (PNG paths, 24 fps)."""
    from .backends import comfy
    w, h = size
    if w % 64 or h % 64:
        raise BuildError(f"camera move with ltx: the size {w}x{h} must be multiples of 64 (LTX's IC-LoRA works on a "
                         "half-size reference latent): set beat_res to e.g. 1920x1088 -> use 1792x1024, or 1024x576")
    tokens = (w // 32) * (h // 32) * ((frames - 1) // 8 + 1)
    if tokens > 22000:
        raise BuildError(f"camera move with ltx: {frames} frames at {w}x{h} are {tokens} latent tokens, over the ~22k "
                         "that fit in VRAM: lower beat_res or shorten the beat")
    cfg = dict(comfy.LTX, prompt=text, negative_prompt=negative, keyframe_strength=keyframe_strength,
               guide_strength=guide_strength, control_strength=control_strength, seed=seed, sampler=sampler, upscale=False)
    comfy.free()
    guides = [(comfy.upload(str(_unique(img, f"anc{n}"))), idx, st) for n, (img, idx, st) in enumerate(anchors or [])]
    g = comfy.build_graph(cfg, comfy.upload(str(_unique(guide, "ltxg"))), comfy.upload(str(_unique(still, "still"))),
                          frames, w, h, FPS, prefix=f"studio/cam_{work.name}", guides=guides)
    log(f"  camera move: LTX-2.3 along the depth guide ({w}x{h}, {frames} frames)")
    t0 = time.time()
    images = comfy.run(g, poll=3)
    out = work / "frames_ltx"
    if out.exists():
        shutil.rmtree(out)
    comfy.fetch(images, str(out))
    comfy.free()
    log(f"  ltx: {frames} frames in {time.time() - t0:.0f}s")
    return sorted(out.glob("*.png"))


def wan_clip_frames(seconds: float) -> int:
    from .animate import wan_frames
    from .backends import comfy
    return wan_frames(seconds, comfy.WAN_FPS)


def generate_wan(still: Path, guide: Path, text: str, negative: str, size: tuple[int, int], frames: int, seed: int,
                 work: Path, wan: Optional[dict] = None, log: Callable = print, ref: bool = True,
                 start: bool = True) -> list[Path]:
    """The beat painted by Wan 2.2 Fun Control with the guide as the control video (16 fps, `frames` = 4k+1 <= 81). The
    start image is pinned as the first frame and given as the reference still. Returns the 16 fps frames (PNGs)."""
    from .backends import comfy
    wan = dict(wan or {})
    w, h = size[0] // 16 * 16, size[1] // 16 * 16
    if frames > comfy.WAN_MAX_FRAMES:
        raise BuildError(f"camera move with wan: {frames} frames at {comfy.WAN_FPS} fps are more than one clip "
                         f"({comfy.WAN_MAX_FRAMES}, about 5 s): shorten the beat or use backend ltx")
    comfy.free()
    still_name = comfy.upload(str(_unique(still, "wstill")))
    g = comfy.build_wan_graph(wan, text, negative, w, h, frames, seed, prefix=f"studio/camw_{work.name}",
                              start_image=still_name if start else None, ref_image=still_name if ref else None,
                              control_video=comfy.upload(str(_unique(guide, "wang"))))
    log(f"  camera move: Wan 2.2 Fun Control along the guide ({w}x{h}, {frames} frames at {comfy.WAN_FPS} fps)")
    t0 = time.time()
    images = comfy.run(g, poll=3)
    out = work / "frames_wan"
    if out.exists():
        shutil.rmtree(out)
    comfy.fetch(images, str(out))
    comfy.free()
    log(f"  wan: {frames} frames in {time.time() - t0:.0f}s")
    return sorted(out.glob("*.png"))


def encode_pngs(pngs: list[Path], out: Path, fps: int = FPS, crf: int = 14) -> None:
    from .project import ffmpeg
    seq = out.parent / f"_seq_{out.stem}"
    if seq.exists():
        shutil.rmtree(seq)
    seq.mkdir(parents=True)
    for i, p in enumerate(pngs):
        shutil.copy(p, seq / f"{i:04d}.png")
    ffmpeg("-framerate", str(fps), "-i", seq / "%04d.png", "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
           "-pix_fmt", "yuv420p", out)
    shutil.rmtree(seq)


# ---------------------------------------------------------------- measuring: does the camera follow the keys?

def _gray(a: np.ndarray) -> np.ndarray:
    import cv2
    return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)


def register(a: np.ndarray, b: np.ndarray, mask_a: Optional[np.ndarray] = None, mask_b: Optional[np.ndarray] = None,
             min_inliers: int = 10) -> Optional[np.ndarray]:
    """The similarity transform (2x3, cv2 convention) taking points of picture `a` to the same points in `b`, found on
    SIFT features of the (masked) static parts and a RANSAC fit; None when too few features agree."""
    import cv2
    sift = cv2.SIFT_create(nfeatures=2500, contrastThreshold=0.02)
    ka, da = sift.detectAndCompute(_gray(a), None if mask_a is None else (mask_a > 127).astype(np.uint8) * 255)
    kb, db = sift.detectAndCompute(_gray(b), None if mask_b is None else (mask_b > 127).astype(np.uint8) * 255)
    if da is None or db is None or len(ka) < min_inliers or len(kb) < min_inliers:
        return None
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < min_inliers:
        return None
    pa = np.float32([ka[m.queryIdx].pt for m in good])
    pb = np.float32([kb[m.trainIdx].pt for m in good])
    A, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=2.5, maxIters=4000)
    if A is None or int(inl.sum()) < min_inliers:
        return None
    if not 0.2 < math.hypot(A[0, 0], A[1, 0]) < 5.0:        # a degenerate fit, not a camera
        return None
    return A


def view_from_transform(A: np.ndarray, size: tuple[int, int]) -> View:
    """The view of the first picture that a picture related to it by `A` (first -> this) shows: centre and width in 0-1 of
    the first picture (the square units of freeze.View)."""
    W, H = size
    s = math.hypot(A[0, 0], A[1, 0])
    cx = (W / 2 - A[0, 2]) / (s * W)
    cy = (H / 2 - A[1, 2]) / (s * H)
    return View(float(cx), float(cy), float(1.0 / s))


def register_all(frames: list[np.ndarray], static: Optional[list[np.ndarray]] = None) -> list[Optional[np.ndarray]]:
    """The transform (first frame -> frame i, 2x3) of every frame, registered on the static world: directly against the first
    frame, or, when that match fails (a close-up sees only part of it), against the previous good frame chained on.
    The first entry is the identity; None where nothing matched."""
    ident = np.array([[1, 0, 0], [0, 1, 0]], np.float64)
    out: list[Optional[np.ndarray]] = [ident]
    last, prev_i = ident, 0
    for i in range(1, len(frames)):
        ma = None if static is None else static[0]
        mb = None if static is None else static[i]
        A = register(frames[0], frames[i], ma, mb)
        if A is None:
            B = register(frames[prev_i], frames[i], None if static is None else static[prev_i], mb)
            if B is not None:
                A = (np.vstack([B, [0, 0, 1]]) @ np.vstack([last, [0, 0, 1]]))[:2]
        if A is None:
            out.append(None)
            continue
        last, prev_i = A, i
        out.append(A)
    return out


def track_views(frames: list[np.ndarray], static: Optional[list[np.ndarray]] = None) -> list[Optional[View]]:
    """Where the camera was in every frame, measured on the frames themselves (see `register_all`). The first frame is the
    reference: View(0.5, 0.5, 1)."""
    H, W = frames[0].shape[:2]
    return [None if A is None else view_from_transform(A, (W, H)) for A in register_all(frames, static)]


def relative_view(k: View, origin: View) -> View:
    """The view `k` (of the world) as seen in the picture of the view `origin` (so the first frame of a beat that starts
    zoomed in is the reference, as it is in `track_views`)."""
    return View((0.5 + (k.cx - origin.cx) / origin.w), (0.5 + (k.cy - origin.cy) / origin.w), k.w / origin.w)


def follow_error(frames: list[np.ndarray], plan: CameraPlan, static: Optional[list[np.ndarray]] = None,
                 times: Optional[list[float]] = None) -> dict:
    """How far the camera is from the keys, measured on the frames. Per frame i (keyed at t = i / (n - 1)):
    `zoom_err` = |log(measured view width / keyed view width)| as a percentage, `shift_err` = the distance between the
    measured and keyed view centres in keyed-view widths. Returns {"zoom_rms", "zoom_max", "shift_rms", "shift_max",
    "n", "lost", "per_frame": [...]}; frames the measurement could not register are counted in `lost`."""
    n = len(frames)
    views = track_views(frames, static)
    ts = times or [i / max(n - 1, 1) for i in range(n)]
    origin = plan.at(0.0)
    rows, lost = [], 0
    for i, (v, t) in enumerate(zip(views, ts)):
        k = relative_view(plan.at(t), origin)
        if v is None:
            lost += 1
            rows.append({"i": i, "t": t, "key": [k.cx, k.cy, k.w], "got": None})
            continue
        zoom = abs(math.log(max(v.w, 1e-6) / k.w)) * 100
        shift = math.hypot(v.cx - k.cx, v.cy - k.cy) / k.w
        rows.append({"i": i, "t": t, "key": [k.cx, k.cy, k.w], "got": [v.cx, v.cy, v.w], "zoom_err": zoom, "shift_err": shift})
    z = np.array([r["zoom_err"] for r in rows if r["got"]])
    s = np.array([r["shift_err"] for r in rows if r["got"]])
    rms = lambda a: float(np.sqrt((a ** 2).mean())) if len(a) else float("nan")
    return {"n": n, "lost": lost, "zoom_rms": rms(z), "zoom_max": float(z.max()) if len(z) else float("nan"),
            "shift_rms": rms(s), "shift_max": float(s.max()) if len(s) else float("nan"), "per_frame": rows}


def people_motion(frames: list[np.ndarray], people: np.ndarray, static: Optional[list[np.ndarray]] = None) -> dict:
    """Do the people still move? The camera is taken out of every frame (each is warped back onto the first by its own
    registration), then the optical flow between consecutive frames is read inside the people's mask and, as the noise
    floor, over the static world. Returns the median flow in pixels per frame for both and their ratio (a walking
    crowd reads clearly above the floor; a pinned one does not)."""
    import cv2
    H, W = frames[0].shape[:2]
    warped = [None if A is None else cv2.warpAffine(f, cv2.invertAffineTransform(A), (W, H), flags=cv2.INTER_LINEAR,
                                                     borderMode=cv2.BORDER_REPLICATE)
              for f, A in zip(frames, register_all(frames, static))]
    pm = cv2.erode((people > 127).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    sm = ~(cv2.dilate((people > 127).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0)
    pf, sf = [], []
    for a, b in zip(warped, warped[1:]):
        if a is None or b is None:
            continue
        flow = cv2.calcOpticalFlowFarneback(_gray(a), _gray(b), None, 0.5, 3, 21, 3, 5, 1.1, 0)
        mag = np.hypot(flow[..., 0], flow[..., 1])
        pf.append(float(np.median(mag[pm])))
        sf.append(float(np.median(mag[sm])))
    pm_med = float(np.median(pf)) if pf else float("nan")
    sm_med = float(np.median(sf)) if sf else float("nan")
    return {"people_px_per_frame": pm_med, "static_px_per_frame": sm_med, "ratio": pm_med / max(sm_med, 1e-3)}


def read_video(path: Path, size: Optional[tuple[int, int]] = None) -> list[np.ndarray]:
    """Every frame of a video as RGB arrays (optionally resized)."""
    import subprocess
    from .config import settings
    from .project import probe
    info = probe(path)
    w, h = int(info["width"]), int(info["height"])
    vf = ["-vf", f"scale={size[0]}:{size[1]}:flags=area"] if size and tuple(size) != (w, h) else []
    w, h = size or (w, h)
    r = subprocess.run([settings()["ffmpeg"], "-hide_banner", "-loglevel", "error", "-i", str(path), *vf, "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True)
    n = len(r.stdout) // (w * h * 3)
    return [np.frombuffer(r.stdout, np.uint8, w * h * 3, i * w * h * 3).reshape(h, w, 3).copy() for i in range(n)]


UNI3C_FILE = "Wan21_Uni3C_controlnet_fp16.safetensors"
UNI3C_SOURCE = "https://huggingface.co/Kijai/WanVideo_comfy/blob/main/Wan21_Uni3C_controlnet_fp16.safetensors"


def uni3c_name(cfg: Optional[dict] = None) -> str:
    """The Uni3C controlnet's file name in ComfyUI's models/model_patches folder (studio.toml [wan] uni3c to rename).
    Raises a BuildError that names the file, where it goes and where to get it when ComfyUI cannot see it."""
    from .backends import comfy
    from .config import settings
    want = (cfg or {}).get("uni3c") or (settings().get("wan") or {}).get("uni3c") or UNI3C_FILE
    have = comfy.listed("model_patches")
    if have is None or want in have:
        return want                     # ComfyUI not reachable: the run itself will say so
    base = want.replace("\\", "/").rsplit("/", 1)[-1]
    alt = [h for h in have if h.replace("\\", "/").rsplit("/", 1)[-1] == base]
    if alt:
        return alt[0]
    raise BuildError(f"camera backend uni3c: ComfyUI can't see model_patches/{want}. It is the Uni3C camera controlnet "
                     f"(Apache-2.0, about 2 GB, not installed by default): download {UNI3C_SOURCE} into "
                     "<ComfyUI>/models/model_patches/ and restart ComfyUI, or use backend ltx / wan.")


def build_uni3c_graph(wan: dict, text: str, negative: str, size: tuple[int, int], frames: int, seed: int, prefix: str,
                      start_image: str, render_video: str, strength: float = 1.0, uni3c: Optional[str] = None,
                      start_percent: float = 0.0, end_percent: float = 1.0) -> dict:
    """Wan 2.2 image-to-video (the start image pinned) with the Uni3C camera controlnet on both experts: the render
    video (the picture flown along the camera path, `guide_rgb.mp4`) carries the camera, the model carries the motion."""
    from .backends import comfy
    w, h = size
    g = comfy.build_wan_graph(wan, text, negative, w, h, frames, seed, prefix, start_image=start_image)
    g["u3c_patch"] = {"class_type": "ModelPatchLoader", "inputs": {"name": uni3c or uni3c_name(wan)}}
    g["u3c_vid"] = {"class_type": "LoadVideo", "inputs": {"file": render_video}}
    g["u3c_frames"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["u3c_vid", 0]}}
    for tag in ("hi", "lo"):
        shift = g[f"shift_{tag}"]
        g[f"u3c_{tag}"] = {"class_type": "WanUni3CControlnetApply", "inputs": {
            "model": shift["inputs"]["model"], "model_patch": ["u3c_patch", 0], "vae": ["vae", 0],
            "render_video": ["u3c_frames", 0], "strength": float(strength), "start_percent": start_percent,
            "end_percent": end_percent}}
        shift["inputs"]["model"] = [f"u3c_{tag}", 0]
    return g


def generate_uni3c(still: Path, render: Path, text: str, negative: str, size: tuple[int, int], frames: int, seed: int,
                   work: Path, wan: Optional[dict] = None, strength: float = 1.0, log: Callable = print) -> list[Path]:
    """The beat painted by Wan 2.2 i2v steered by Uni3C along the pure-camera render (16 fps, <= 81 frames)."""
    from .backends import comfy
    wan = dict(wan or {})
    name = uni3c_name(wan)                  # fail first, before anything is uploaded or loaded
    w, h = size[0] // 16 * 16, size[1] // 16 * 16
    if frames > comfy.WAN_MAX_FRAMES:
        raise BuildError(f"camera move with uni3c: {frames} frames are more than one Wan clip ({comfy.WAN_MAX_FRAMES}): shorten the beat")
    comfy.free()
    g = build_uni3c_graph(wan, text, negative, (w, h), frames, seed, f"studio/camu_{work.name}",
                          comfy.upload(str(_unique(still, "ustill"))), comfy.upload(str(_unique(render, "u3c"))),
                          strength, name)
    log(f"  camera move: Wan 2.2 + Uni3C along the guide ({w}x{h}, {frames} frames at {comfy.WAN_FPS} fps)")
    t0 = time.time()
    images = comfy.run(g, poll=3)
    out = work / "frames_uni3c"
    if out.exists():
        shutil.rmtree(out)
    comfy.fetch(images, str(out))
    comfy.free()
    log(f"  uni3c: {frames} frames in {time.time() - t0:.0f}s")
    return sorted(out.glob("*.png"))


# ---------------------------------------------------------------- matching the plate (tone and grain)

def noise_level(rgb: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    """The grain of a picture: the standard deviation (0-255) of what a light blur takes out of its luminance, over its flat
    parts (low local gradient), so edges and ink lines do not count as noise."""
    import cv2
    g = _gray(rgb).astype(np.float32)
    hf = g - cv2.GaussianBlur(g, (0, 0), 1.2)
    grad = np.hypot(cv2.Sobel(cv2.GaussianBlur(g, (0, 0), 1.5), cv2.CV_32F, 1, 0), cv2.Sobel(cv2.GaussianBlur(g, (0, 0), 1.5), cv2.CV_32F, 0, 1))
    flat = grad < max(2.0, float(np.percentile(grad, 40)))
    if mask is not None:
        flat &= mask > 127
    return float(hf[flat].std()) if flat.sum() > 200 else 0.0


def tone_match(frames: list[np.ndarray], refs: list[np.ndarray], static: list[np.ndarray], strength: float,
               grain: Optional[float] = None, seed: int = 7, ramp: int = 0) -> list[np.ndarray]:
    """Pull every generated frame toward the plate: per channel, a gain and an offset that make the mean and spread of
    the frame's static world (where `static` is 255) match the same area of the pure-camera render `refs`, smoothed over
    time so nothing flickers, applied `strength` (0-1); then grain is added where the frame is cleaner than `grain` (the
    plate's own noise level) so a clip graded this way does not turn waxy next to the plate. The people are never used
    to measure (they move), but the correction is global, so they take it too. `ramp`: the correction fades in over this
    many frames (frame 0 is left exactly as it is), for a clip that starts on the last frame of another."""
    import cv2
    from scipy.ndimage import gaussian_filter1d
    n = len(frames)
    gains, offs, ok = np.ones((n, 3)), np.zeros((n, 3)), np.zeros(n, bool)
    for k in range(n):
        m = cv2.erode((static[k] > 200).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        if m.mean() < 0.03:
            continue
        a = cv2.GaussianBlur(frames[k], (0, 0), 1.5).astype(np.float32)[m]
        b = cv2.GaussianBlur(refs[k], (0, 0), 1.5).astype(np.float32)[m]
        g = np.clip(b.std(0) / np.maximum(a.std(0), 1.0), 0.7, 1.4)
        gains[k], offs[k], ok[k] = g, b.mean(0) - g * a.mean(0), True
    if not ok.any():
        return frames
    idx = np.arange(n)
    for arr in (gains, offs):
        for c in range(3):                                   # fill frames that could not be measured, then smooth
            arr[:, c] = np.interp(idx, idx[ok], arr[ok, c])
            arr[:, c] = gaussian_filter1d(arr[:, c], max(1.0, n / 24), mode="nearest")
    rng = np.random.default_rng(seed)
    out = []
    for k, f in enumerate(frames):
        x = f.astype(np.float32)
        st = strength * (min(1.0, k / ramp) if ramp > 0 else 1.0)
        if st <= 0:
            out.append(f)
            continue
        y = x * (1 - st + st * gains[k]) + st * offs[k]
        if grain:
            have = noise_level(np.clip(y, 0, 255).astype(np.uint8))
            if have < grain * 0.9:
                add = float(np.sqrt(max(grain ** 2 - have ** 2, 0))) * st
                nz = cv2.GaussianBlur(rng.standard_normal(y.shape[:2]).astype(np.float32), (0, 0), 0.6)
                nz = nz / max(float(nz.std()), 1e-6)
                y = y + nz[..., None] * add
        out.append(np.clip(y + 0.5, 0, 255).astype(np.uint8))
    return out


def people_displacement(frames: list[np.ndarray], people: np.ndarray, static: Optional[list[np.ndarray]] = None) -> dict:
    """How far the people have walked from where they stood in the first frame, with the camera taken out: every frame is
    warped back onto the first by its own similarity registration (on the static world), then the optical flow from the first
    frame to it is read inside the people's mask (and, as the noise floor, over the static world), only where the warped frame
    covers the first. Returns per-frame median displacements in pixels (`people`, `static`) and the summary `end` (mean of
    the last third): a walking crowd reads well above the static floor, a pinned one stays at it."""
    import cv2
    H, W = frames[0].shape[:2]
    g0 = _gray(frames[0])
    pm0 = cv2.erode((people > 127).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    sm0 = ~(cv2.dilate((people > 127).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0)
    pk, sk = [0.0], [0.0]
    mats = register_all(frames, static)
    for i in range(1, len(frames)):
        A = mats[i]
        if A is None:
            pk.append(float("nan")); sk.append(float("nan"))
            continue
        inv = cv2.invertAffineTransform(A)
        warped = cv2.warpAffine(frames[i], inv, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        valid = cv2.erode(cv2.warpAffine(np.ones((H, W), np.uint8), inv, (W, H), flags=cv2.INTER_NEAREST), np.ones((9, 9), np.uint8)) > 0
        flow = cv2.calcOpticalFlowFarneback(g0, _gray(warped), None, 0.5, 4, 31, 4, 5, 1.1, 0)
        mag = np.hypot(flow[..., 0], flow[..., 1])
        a, b = pm0 & valid, sm0 & valid
        pk.append(float(np.median(mag[a])) if a.sum() > 50 else float("nan"))
        sk.append(float(np.median(mag[b])) if b.sum() > 50 else float("nan"))
    n = len(frames)
    tail = slice(2 * n // 3, n)
    end = lambda v: float(np.nanmean(v[tail])) if np.isfinite(v[tail]).any() else float("nan")
    return {"people": pk, "static": sk, "people_end_px": end(np.array(pk)), "static_end_px": end(np.array(sk)),
            "people_max_px": float(np.nanmax(pk)), "width": W}


def stabilised(frames: list[np.ndarray], static: Optional[list[np.ndarray]] = None) -> list[Optional[np.ndarray]]:
    """Every frame warped back onto the first one by its own registration (the camera taken out; None where it could not be
    registered): what the world, and the people walking in it, look like through a camera that never moved."""
    import cv2
    H, W = frames[0].shape[:2]
    return [None if A is None else cv2.warpAffine(f, cv2.invertAffineTransform(A), (W, H), flags=cv2.INTER_LINEAR,
                                                  borderMode=cv2.BORDER_CONSTANT, borderValue=(48, 48, 48))
            for f, A in zip(frames, register_all(frames, static))]


def crop_view(frames: list[Optional[np.ndarray]], view: View) -> list[Optional[np.ndarray]]:
    """The same square view (freeze.View units) cut out of every frame."""
    out = []
    for f in frames:
        if f is None:
            out.append(None)
            continue
        H, W = f.shape[:2]
        x0, x1 = int((view.cx - view.w / 2) * W), int(math.ceil((view.cx + view.w / 2) * W))
        y0, y1 = int((view.cy - view.w / 2) * H), int(math.ceil((view.cy + view.w / 2) * H))
        out.append(np.ascontiguousarray(f[max(y0, 0):y1, max(x0, 0):x1]))
    return out


def contact_sheet(rows: list[tuple[str, list[np.ndarray]]], out: Path, cols: int = 8, cell: int = 320) -> None:
    """A review sheet: one labelled row of frames per entry (each list is sampled to `cols` frames across the beat; a row
    keeps its own aspect ratio inside cells of `cell` pixels across)."""
    from PIL import Image, ImageDraw
    heights = [int(round(cell * fr[0].shape[0] / fr[0].shape[1])) for _, fr in rows]
    sheet = Image.new("RGB", (cols * cell, sum(heights)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    y = 0
    for (label, fr), ch in zip(rows, heights):
        for c in range(cols):
            k = round(c * (len(fr) - 1) / max(cols - 1, 1))
            if fr[k] is not None:
                sheet.paste(Image.fromarray(fr[k]).resize((cell, ch), Image.LANCZOS), (c * cell, y))
        d.rectangle((0, y, 8 + 7 * len(label), y + 14), fill=(0, 0, 0))
        d.text((4, y + 2), label, fill=(255, 220, 0))
        y += ch
    sheet.save(out, quality=88)


def world_view(rel: View, origin: View) -> View:
    """A view measured in a beat's own first frame (`rel`, as `track_views` gives it) as a view of the world, given the view
    `origin` that first frame shows (the inverse of `relative_view`)."""
    return View(origin.cx + (rel.cx - 0.5) * origin.w, origin.cy + (rel.cy - 0.5) * origin.w, rel.w * origin.w)


def zoom_rate(views: list[Optional[View]], fps: float) -> float:
    """The slope of log view width over time (per second) of a stretch of measured views, a straight-line fit (0 when fewer
    than three frames registered)."""
    pts = [(i / fps, math.log(v.w)) for i, v in enumerate(views) if v is not None]
    if len(pts) < 3:
        return 0.0
    t, y = np.array(pts).T
    return float(np.polyfit(t, y, 1)[0])


def join_report(prev: list[np.ndarray], cur: list[np.ndarray], prev_plan: CameraPlan, plan: CameraPlan,
                prev_static: Optional[list[np.ndarray]] = None, static: Optional[list[np.ndarray]] = None,
                fps: float = FPS, span: int = 8) -> dict:
    """How well two beats join at the cut, measured on their frames: the pixel difference between the last frame of `prev`
    and the first of `cur` (0 = the cut is invisible: `cur` starts exactly on it), the mean brightness step, and the camera's
    zoom rate (per second, of log view width) over the last `span` frames before the cut and the first `span` after it,
    both measured and as keyed. A camera that carries across the cut keeps its rate; one that eases to a stop and starts
    again goes to about zero and back."""
    a, b = prev[-1].astype(np.float32), cur[0].astype(np.float32)
    tail = track_views(prev, prev_static)[-span:]
    head = track_views(cur, static)[:span]
    o_prev, o_cur = prev_plan.at(0.0), plan.at(0.0)
    tail_w = [None if v is None else world_view(v, o_prev) for v in tail]
    head_w = [None if v is None else world_view(v, o_cur) for v in head]
    key_before = (math.log(prev_plan.at(1.0).w) - math.log(prev_plan.at(1.0 - 1.0 / max(len(prev) - 1, 1)).w)) * (len(prev) - 1) * fps / len(prev)
    key_after = (math.log(plan.at(1.0 / max(len(cur) - 1, 1)).w) - math.log(plan.at(0.0).w)) * (len(cur) - 1) * fps / len(cur)
    return {"frame_diff": float(np.abs(a - b).mean()), "brightness_step": float(b.mean() - a.mean()),
            "rate_before": zoom_rate(tail_w, fps), "rate_after": zoom_rate(head_w, fps),
            "rate_before_keyed": float(key_before), "rate_after_keyed": float(key_after)}
