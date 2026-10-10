"""Gaussian splats for the web: read a scan, trim it, write a small file the runtime can load.

Reads
  .ply   the standard 3D Gaussian Splatting layout (x y z, f_dc_*, f_rest_*, opacity, scale_*, rot_*)
  .pt    a gsplat checkpoint ({"splats": {means, quats, scales, opacities, sh0, shN}}) - needs torch

Writes
  .spz   Niantic's compressed format, version 2 (gzip; ~16 bytes per splat without SH, ~25 with degree 1).
         Read by Spark in the runtime.
  .ply   the same standard layout, SH degree 0 (as a fallback or for other viewers)

Trimming: drop near-invisible splats, keep the N most opaque, and optionally crop to a box. Positions are kept
in the scan's own frame; the scene spec orients the room (`up`, `rotation`).
"""
from __future__ import annotations

import gzip
import struct
from pathlib import Path

import numpy as np

SH_C0 = 0.28209479177387814


def read_ply(path: Path) -> dict:
    with open(path, "rb") as f:
        header, props = [], []
        n = 0
        while True:
            line = f.readline().decode("ascii").strip()
            header.append(line)
            if line.startswith("element vertex"):
                n = int(line.split()[-1])
            elif line.startswith("property"):
                _, typ, name = line.split()
                props.append((name, typ))
            elif line == "end_header":
                break
        fmt = {"float": "f4", "double": "f8", "uchar": "u1", "int": "i4", "uint": "u4"}
        dtype = np.dtype([(name, "<" + fmt[typ]) for name, typ in props])
        data = np.frombuffer(f.read(n * dtype.itemsize), dtype=dtype, count=n)
    means = np.stack([data["x"], data["y"], data["z"]], 1).astype(np.float32)
    sh0 = np.stack([data["f_dc_0"], data["f_dc_1"], data["f_dc_2"]], 1).astype(np.float32)
    rest = sorted((p for p, _ in props if p.startswith("f_rest_")), key=lambda s: int(s[7:]))
    shN = None
    if rest:
        k = len(rest) // 3   # ply stores channel-major: all coefficients of R, then G, then B
        arr = np.stack([data[p] for p in rest], 1).astype(np.float32).reshape(n, 3, k)
        shN = np.transpose(arr, (0, 2, 1))   # -> (n, k, 3): coefficient-major, channel inner
    return {
        "means": means, "sh0": sh0, "shN": shN,
        "opacities": data["opacity"].astype(np.float32),          # logits
        "scales": np.stack([data["scale_0"], data["scale_1"], data["scale_2"]], 1).astype(np.float32),   # log
        "quats": np.stack([data["rot_0"], data["rot_1"], data["rot_2"], data["rot_3"]], 1).astype(np.float32),  # w x y z
    }


def read_gsplat(path: Path) -> dict:
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    s = ck["splats"] if "splats" in ck else ck
    g = lambda k: s[k].detach().float().cpu().numpy()
    shN = g("shN") if "shN" in s else None
    return {"means": g("means"), "sh0": g("sh0").reshape(-1, 3), "shN": shN,
            "opacities": g("opacities").reshape(-1), "scales": g("scales"), "quats": g("quats")}


def read(path: Path) -> dict:
    ext = path.suffix.lower()
    if ext == ".ply":
        return read_ply(path)
    if ext == ".pt":
        return read_gsplat(path)
    raise ValueError(f"unsupported splat source {ext} (use .ply or a gsplat .pt checkpoint)")


def trim(s: dict, max_splats: int = 600_000, min_opacity: float = 0.04, crop=None, max_scale: float = 0.0) -> dict:
    """Keep the most opaque splats, drop the faint ones and (max_scale > 0) the oversized smears that scans
    leave in the air, crop to [x0, y0, z0, x1, y1, z1] if given."""
    alpha = 1 / (1 + np.exp(-s["opacities"]))
    keep = alpha >= min_opacity
    if max_scale > 0:
        keep &= np.exp(s["scales"]).max(axis=1) <= max_scale
    if crop:
        lo, hi = np.array(crop[:3]), np.array(crop[3:])
        keep &= np.all((s["means"] >= lo) & (s["means"] <= hi), axis=1)
    idx = np.nonzero(keep)[0]
    if len(idx) > max_splats:
        order = np.argsort(-alpha[idx])[:max_splats]
        idx = np.sort(idx[order])
    out = {k: (v[idx] if isinstance(v, np.ndarray) else v) for k, v in s.items()}
    return out


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def write_spz(s: dict, path: Path, sh_degree: int = 1, fractional_bits: int = 12) -> None:
    """SPZ version 2: 16-byte header + gzip(positions, alphas, colors, scales, rotations, sh)."""
    n = len(s["means"])
    sh_degree = min(sh_degree, 3 if s["shN"] is not None else 0)
    body = bytearray()
    # positions: 24-bit fixed point, little-endian
    fixed = np.round(s["means"].astype(np.float64) * (1 << fractional_bits)).astype(np.int64)
    fixed = np.clip(fixed, -(1 << 23), (1 << 23) - 1).astype(np.int32)
    u = (fixed & 0xFFFFFF).astype(np.uint32)
    pos = np.stack([u & 0xFF, (u >> 8) & 0xFF, (u >> 16) & 0xFF], 2).astype(np.uint8).reshape(-1)
    body += pos.tobytes()
    body += np.clip(np.round(_sigmoid(s["opacities"]) * 255), 0, 255).astype(np.uint8).tobytes()
    body += np.clip(np.round(s["sh0"] * (0.15 * 255) + 127.5), 0, 255).astype(np.uint8).tobytes()
    body += np.clip(np.round((s["scales"] + 10.0) * 16.0), 0, 255).astype(np.uint8).tobytes()
    q = s["quats"].astype(np.float64)
    q /= np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-9)
    q[q[:, 0] < 0] *= -1                      # w >= 0 so xyz alone recover it
    rot = np.clip(np.round((q[:, 1:4] + 1) * 127.5), 0, 255).astype(np.uint8)   # readers map byte/127.5 - 1
    body += rot.tobytes()
    if sh_degree > 0:
        k = {1: 3, 2: 8, 3: 15}[sh_degree]
        sh = s["shN"][:, :k, :].astype(np.float64)          # (n, k, 3): coefficient outer, channel inner
        qsh = np.round(sh * 128)
        bucket = np.ones((1, k, 1))
        bucket[:, 3:, :] = 16                                 # 4 bits for degree 2+
        bucket[:, :3, :] = 8                                  # 5 bits for degree 1
        qsh = np.floor((qsh + bucket / 2) / bucket) * bucket
        body += np.clip(qsh + 128, 0, 255).astype(np.uint8).reshape(-1).tobytes()   # readers map (byte - 128) / 128
    header = struct.pack("<IIIBBBB", 0x5053474E, 2, n, sh_degree, fractional_bits, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:                      # the whole file, header included, is one gzip stream
        f.write(gzip.compress(header + bytes(body), compresslevel=9))


def write_ply(s: dict, path: Path) -> None:
    """Standard 3DGS ply, SH degree 0."""
    n = len(s["means"])
    names = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity", "scale_0", "scale_1", "scale_2",
             "rot_0", "rot_1", "rot_2", "rot_3"]
    arr = np.concatenate([s["means"], s["sh0"], s["opacities"][:, None], s["scales"], s["quats"]], 1).astype("<f4")
    head = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n%s\nend_header\n" % (
        n, "\n".join(f"property float {m}" for m in names))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(head.encode("ascii"))
        f.write(arr.tobytes())


def bounds(s: dict) -> dict:
    m = s["means"]
    lo, hi = np.percentile(m, 2, axis=0), np.percentile(m, 98, axis=0)
    return {"min": lo.round(2).tolist(), "max": hi.round(2).tolist(), "center": ((lo + hi) / 2).round(2).tolist(),
            "count": int(len(m))}
