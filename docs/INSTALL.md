# Installing Scroll Studio

Scroll Studio runs entirely on your machine. What you need depends on which scene types you use:

| Scene type | Needs |
|---|---|
| `type`, `scene3d`, `chart`, `map` | Python + a browser. No GPU (they render live in the page). |
| `vector` | Same; vectorising a raster image (not an SVG) also needs the `vector` extra (vtracer). No GPU. |
| `artwork` | + OpenCV/NumPy (installed with the package). No GPU. `generate:` images also need ComfyUI. |
| `parallax` | + PyTorch (depth estimation). Runs on the CPU; a CUDA GPU is much faster. `generate:` images need ComfyUI. |
| `sequence` | + Blender 4.2+ (Cycles uses the GPU when there is one, otherwise the CPU). |
| `film` | + Blender, FFmpeg, ComfyUI with the LTX-2.3 and Z-Image models, a 24 GB GPU (RTX 4090/5090 class). |
| `film` with `take.product` | + the product's 3D model (.glb/.gltf/.obj/.fbx/.stl/.ply). `from_photo:` instead needs TRELLIS (below). |
| `splat` | A scan as a 3DGS `.ply` (any) or a gsplat `.pt` checkpoint (needs PyTorch to read). No GPU at build time. |

`studio doctor` (or the Toolchain page in the UI) shows what this machine has.

## 1. Core (every site)

- **Python 3.10+** and **Node.js 20+**, **Git**, **FFmpeg 6+** on the PATH.
- **Chrome** (or `playwright install chromium`) for snapshots and recordings.

```bash
git clone https://github.com/Okohedeki/scroll-studio
cd scroll-studio
pip install -e .            # engine, CLI, server, MCP server
npm install && npm run build  # browser runtime + Studio UI
studio doctor
```

The built runtime is committed, so `npm run build` is only needed for the UI or after editing `runtime/src`.

## 2. GPU stages (parallax, film)

Install PyTorch for your CUDA driver first, then the ML extras:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e .[ml]
```

Depth Anything V2 downloads into `<model_dir>/hf` on first use (set `model_dir` in `studio.toml`).

## 3. Blender (sequence, film)

Install Blender 4.2 LTS or newer. Scroll Studio finds it in the default install location, or set `blender = "…"`
in `studio.toml` (copy `studio.example.toml`) or the `BLENDER` environment variable.

## 4. ComfyUI (film, generated images)

1. Install [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and these custom nodes: ComfyUI-LTXVideo,
   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite.
2. Download the models listed in `engine/models.yaml` into ComfyUI's model folders (or point
   `extra_model_paths.yaml` at another drive).
3. Start it and leave it running:
   ```bash
   python main.py --listen 127.0.0.1 --port 8188 --reserve-vram 1.5
   ```
   On Windows set `PYTHONUTF8=1` first. Close games before rendering; they take VRAM and stall renders.

Scroll Studio talks to ComfyUI at `comfy_url` (default http://127.0.0.1:8188).

## 5. TRELLIS (optional: a product model from one photo)

`take.product.from_photo` turns a product photo into a mesh with TRELLIS before rendering it. Install TRELLIS in
its own environment, then tell Scroll Studio how to run it (`studio.toml` or environment variables):

```toml
trellis_python = "D:/ai/TRELLIS/venv/Scripts/python.exe"   # TRELLIS_PYTHON
trellis_script = "D:/ai/TRELLIS/image_to_mesh.py"          # TRELLIS_SCRIPT: --dir <work> reads object.png, writes mesh.ply
```

A real model (`model:`) always looks better than a reconstruction; use the photo route when there is no model.

## 6. Claude

- **Claude Code**: open the repo; `.mcp.json` registers the `scroll-studio` MCP server and the `scroll-site` skill
  teaches the workflow. Ask for a site in plain language.
- **Claude Desktop / other MCP clients**: add a server that runs `python -m engine.mcp_server` with the repo as the
  working directory.
