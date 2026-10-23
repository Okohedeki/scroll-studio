"""The deep-zoom render (engine/zoom.py) and the layered render (engine/layers.py): freeze.Renderer over a pyramid of
tiles and, optionally, a stack of planes.

Per frame the camera's view is a width `w` of the frame. The depth the camera marches through is composed for that view
(the base depth refined by every tile that is on), then the colour is sampled from the base and from each level's
tiles, coarse to fine. A level is on in proportion to `lod_alpha` (the view's width against the tile's, so detail fades
in as the camera arrives and out as it leaves), a tile fades out at its own border (`FEATHER`), and tiles of one level
that overlap are blended by those weights. Because every tile carries its parent's low frequencies exactly, fading a
level in adds fine detail only: nothing moves and nothing changes colour.

With planes the same machinery runs once per plane, back to front. Each plane has its own depth texture (composed from
the base and the tiles like the single depth map), is marched and sampled on its own, and is laid over what is behind it
by its alpha (also composed from the pyramid); the background plane (the frame with the subjects painted out) goes
first. A subject plane's colour has the plate's share removed at the edge (`layers.estimate_foreground`), so it carries
no fringe of the old background when it moves.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np

from .zoom import FEATHER, VIEW_PAD, TileImage, lod_alpha


def _renderer_class():
    from .freeze import Renderer

    class PyramidRenderer(Renderer):
        DEPTH_MARGIN = 1.7          # the view's depth texture is this much wider than the view (the parallax looks outside it)

        def __init__(self, rgb, depth, size, tiles: Sequence[TileImage], device=None, layers=None):
            super().__init__(rgb, depth, size, device)
            self.layers = layers
            self.tiles = []
            for t in sorted(tiles, key=lambda t: t.level):
                g = {"t": t, "rgb": self._mip_chain(self._img(t.rgb)), "depth": [self._map(t.depth)]}
                if layers is not None:
                    g["bg"] = self._mip_chain(self._img(t.bg))
                    g["alpha"] = [self._mip_chain(self._map(t.alpha[p].astype(np.float32) / 255)) for p in range(len(t.alpha))]
                    g["pdepth"] = [[self._map(t.pdepth[p])] for p in range(len(t.pdepth))]
                    g["bgdepth"] = [self._map(t.bgdepth)]
                self.tiles.append(g)
            if layers is not None:
                from .layers import base_background
                self.P = layers.alpha.shape[0]
                bg = base_background(np.asarray(rgb), layers)
                self.base = {"bg": self._mip_chain(self._img(bg)),
                             "alpha": [self._mip_chain(self._map(layers.alpha[p])) for p in range(self.P)],
                             "pdepth": [self._map(layers.depth[p]) for p in range(self.P)],
                             "bgdepth": self._map(layers.bg_depth)}
                self.plate0 = self._mip_chain(self._img(layers.plate))

        # -- uploads
        def _img(self, a):
            return self.torch.from_numpy(np.ascontiguousarray(a)).to(self.dev).permute(2, 0, 1)[None].float()

        def _map(self, a):
            return self.torch.from_numpy(np.ascontiguousarray(a, dtype=np.float32)).to(self.dev)[None, None]

        def _mip_chain(self, x):
            mips = [x]
            while mips[-1].shape[-1] > self.W // 2 and len(mips) < 4:
                mips.append(self.torch.nn.functional.avg_pool2d(mips[-1], 2))
            return mips

        # -- which tiles count in this view
        def _active(self, cx, cy, w):
            out = []
            half = w * VIEW_PAD * 0.6
            for g in self.tiles:
                t = g["t"]
                a = lod_alpha(w, t.size)
                if a <= 1e-3:
                    continue
                if cx + half < t.box[0] or cx - half > t.box[2] or cy + half < t.box[1] or cy - half > t.box[3]:
                    continue
                out.append((g, a))
            return out

        def _weight(self, t, u):
            """(local grid (1, h, w, 2) in -1..1, feather weight (h, w)) of tile `t` at base positions `u` (h, w, 2)."""
            torch = self.torch
            uv = (u - torch.tensor([t.box[0], t.box[1]], device=self.dev)) / t.size
            e = (torch.minimum(uv, 1 - uv).amin(dim=-1) / FEATHER).clamp(0, 1)
            return (uv.clamp(0, 1) * 2 - 1)[None], e * e * (3 - 2 * e)

        def _compose(self, u, base, active, pick, texels):
            """Coarse to fine: `base`, then for each level the weight-averaged tiles' channel (`pick(g)` -> its mip list),
            laid over it by coverage x alpha. `texels(t)`: the tile's texels per output pixel (the mip to read), or None for a
            channel without mips (read bilinear)."""
            F = self.torch.nn.functional
            out = base
            i = 0
            while i < len(active):
                lvl = active[i][0]["t"].level
                num = den = None
                while i < len(active) and active[i][0]["t"].level == lvl:
                    g, a = active[i]
                    t = g["t"]
                    grid, wt = self._weight(t, u)
                    wt = wt * a
                    mips = pick(g)
                    if texels is None:
                        val = F.grid_sample(mips[0], grid, mode="bilinear", padding_mode="border", align_corners=False)[0]
                    else:
                        val = self._sample_mips(mips, grid, texels(t))
                    num = val * wt if num is None else num + val * wt
                    den = wt if den is None else den + wt
                    i += 1
                cov = den.clamp(max=1.0)
                out = out * (1 - cov) + (num / den.clamp(min=1e-6)) * cov
            return out

        # -- the depth of this view
        def _local_depth(self, c, w, active, base_tex, pick):
            """The depth texture the march reads: `base_tex` (1,1,h,w over the whole frame) refined by the tiles' channel."""
            F = self.torch.nn.functional
            m = self.DEPTH_MARGIN
            hd, wd = max(8, int(self.H / 2 * m)), max(8, int(self.W / 2 * m))
            o = self._grid_of(wd, hd)                                   # -0.5 .. 0.5
            u = (c + w * m * o).clamp(0, 1)
            base = F.grid_sample(base_tex, self._grid(u), mode="bilinear", padding_mode="border", align_corners=False)[0]
            self._d0 = c - w * m / 2
            self._dsz = w * m
            self._dtex = self._compose(u, base, active, pick, None)[None]

        def _march(self, c, s, w, e, f):
            """freeze.Renderer._march against this view's depth texture (finer than the base depth wherever a tile is on)."""
            torch = self.torch
            F = torch.nn.functional
            o = self.o_solve
            n = self.STEPS
            hit = star = prev_gap = prev_d = None
            for k in range(n + 1):
                d = 1.0 - k / n
                u = self._source_at(c, s, w, e, f, d, o).clamp(0, 1)
                ul = ((u - self._d0) / self._dsz).clamp(0, 1)
                gap = F.grid_sample(self._dtex, self._grid(ul), mode="bilinear", padding_mode="border", align_corners=False)[0, 0] - d
                if k == 0:
                    hit = gap >= 0
                    star = torch.where(hit, torch.ones_like(gap), torch.zeros_like(gap))
                else:
                    new = (~hit) & (gap >= 0)
                    frac = (-prev_gap) / (gap - prev_gap).clamp(min=1e-6)
                    star = torch.where(new, prev_d + (d - prev_d) * frac, star)
                    hit = hit | new
                prev_gap, prev_d = gap, d
            return star

        def _sample_mips(self, mips, grid, texels_per_px):
            F = self.torch.nn.functional
            lod = min(max(math.log2(max(texels_per_px, 1e-6)), 0.0), len(mips) - 1)
            lo, fr = int(lod), lod - int(lod)
            out = F.grid_sample(mips[lo], grid, mode="bicubic", padding_mode="border", align_corners=False)
            if fr > 0.02 and lo + 1 < len(mips):
                out = out * (1 - fr) + F.grid_sample(mips[lo + 1], grid, mode="bicubic", padding_mode="border",
                                                     align_corners=False) * fr
            return out[0]

        # -- where each pixel of the output comes from
        def _positions(self, c, s, w, e, f, shifting, active, base_tex, pick):
            torch = self.torch
            F = torch.nn.functional
            if shifting:
                self._local_depth(c, w, active, base_tex, pick)
                star = self._march(c, s, w, e, f)[None, None]
                star = F.interpolate(star, size=(self.H, self.W), mode="bilinear", align_corners=False)[0, 0]
                u = self._source_at(c, s, w, e, f, star, self.o)
            else:
                u = c + w * self.o
            return u.clamp(0, 1)

        def frame(self, cx: float, cy: float, w: float, sx: float, sy: float, e: float, f: float):
            torch = self.torch
            c = torch.tensor([cx, cy], device=self.dev)
            s = torch.tensor([sx, sy], device=self.dev)
            shifting = bool(sx or sy or e)
            active = self._active(cx, cy, w)
            base_texels = max(w * self.src_w / self.W, 1e-6)
            tex = lambda t: t.rgb.shape[1] * w / (t.size * self.W)
            if self.layers is None:
                u = self._positions(c, s, w, e, f, shifting, active, self.depth, lambda g: g["depth"])
                base = self._sample_mips(self.levels, self._grid(u), base_texels)
                return self._compose(u, base, active, lambda g: g["rgb"], tex)
            return self._layered(c, s, w, e, f, shifting, active, base_texels, tex)

        def _layered(self, c, s, w, e, f, shifting, active, base_texels, tex):
            """Planes back to front: the background, then each subject plane over it."""
            B = self.base
            u = self._positions(c, s, w, e, f, shifting, active, B["bgdepth"], lambda g: g["bgdepth"])
            out = self._compose(u, self._sample_mips(B["bg"], self._grid(u), base_texels), active, lambda g: g["bg"], tex)
            for p in range(self.P):
                u = self._positions(c, s, w, e, f, shifting, active, B["pdepth"][p], lambda g, p=p: g["pdepth"][p])
                grid = self._grid(u)
                rgb = self._compose(u, self._sample_mips(self.levels, grid, base_texels), active, lambda g: g["rgb"], tex)
                bg = self._compose(u, self._sample_mips(B["bg"], grid, base_texels), active, lambda g: g["bg"], tex)
                a = self._compose(u, self._sample_mips(B["alpha"][p], grid, base_texels), active,
                                  lambda g, p=p: g["alpha"][p], tex).clamp(0, 1)
                fg = self._foreground(rgb, a, bg)
                out = out * (1 - a) + fg * a
            return out

        def _foreground(self, rgb, a, plate):
            """foreground = (pixel - (1 - a) * plate) / a at the soft edge, the pixel where alpha is solid (or nearly nothing)."""
            fg = ((rgb - (1 - a) * plate) / a.clamp(min=0.08)).clamp(0, 255)
            k = ((a - 0.04) / 0.2).clamp(0, 1)
            return rgb * (1 - k) + fg * k

    return PyramidRenderer


def render_frames(rgb: np.ndarray, depth: np.ndarray, tiles: Sequence[TileImage], camera, *, size: tuple[int, int],
                  seconds: float, first_frame: int = 0, parallax: float = 0.6, dolly: Optional[float] = None,
                  ease: str = "inOutSine", blur: float = 0.0, grain: float = 0.0, seed: int = 7, fps: int = 24,
                  device: Optional[str] = None, layers=None):
    """freeze.render_frames over a pyramid of tiles: the same camera, parallax, blur and grain, but every pixel is taken
    from the finest tile that covers it. `rgb`, `depth`: the base level (what freeze.render_frames takes). `layers`: a
    layers.LayerSet, and every tile then carries its planes: the frame is rendered plane by plane."""
    from .freeze import CameraPath, Timeline
    n = max(2, int(round(seconds * fps)))
    path = CameraPath(camera, ease)
    small = depth
    if depth.shape[1] > 480:
        import cv2
        small = cv2.resize(depth, (480, max(1, round(480 * depth.shape[0] / depth.shape[1]))), interpolation=cv2.INTER_AREA)
    tl = Timeline(path, seconds, small, parallax, dolly, fps)
    r = _renderer_class()(rgb, depth, size, tiles, device, layers)
    subs = 5 if blur > 0 else 1
    for i in range(first_frame, n):
        acc = None
        for j in range(subs):
            off = (j / (subs - 1) - 0.5) * blur if subs > 1 else 0.0
            fr = r.frame(**tl.at((i + off) / (n - 1)))
            acc = fr if acc is None else acc + fr
        fr = acc / subs
        if grain > 0:
            fr = r.grain(fr, grain, seed * 100003 + i)
        yield r.to_u8(fr)
