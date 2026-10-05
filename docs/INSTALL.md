# Installing Scroll Studio

Scroll Studio runs entirely on your machine. What you need depends on which scene types you use:

| Scene type | Needs |
|---|---|
| `type`, `scene3d` | Python + a browser. Nothing else (they render live in the page). |
| `artwork` | + OpenCV/NumPy (installed with the package). `generate:` images also need ComfyUI. |
| `parallax` | + PyTorch with CUDA (depth estimation). `generate:` images need ComfyUI. |
| `sequence` | + Blender 4.2+ (renders with Cycles on the GPU). |
| `film` | + Blender, FFmpeg, ComfyUI with the LTX-2.3 and Z-Image models, a 24 GB GPU (RTX 4090/5090 class). |

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

## 5. Claude

- **Claude Code**: open the repo; `.mcp.json` registers the `scroll-studio` MCP server and the `scroll-site` skill
  teaches the workflow. Ask for a site in plain language.
- **Claude Desktop / other MCP clients**: add a server that runs `python -m engine.mcp_server` with the repo as the
  working directory.
