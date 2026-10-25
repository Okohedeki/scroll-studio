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
| `film` with `video_model: wan` | + the Wan 2.2 files in `engine/models.yaml` (~67 GB: two i2v experts for beats and art, two Fun Control experts for takes, UMT5, the VAE, two LoRAs) and ~32 GB of free system RAM. Same 24 GB GPU. |
| `film` with `reveal` or `faces: restore`, an image `edit:` with `region` | + `studio setup-comfy` (SAM 2.1, Florence-2, GFPGAN: ~2.5 GB, section 4); a region edit also needs Qwen-Image-Edit like any `edit:`. |
| `film` or `parallax` with `place: {kind: behind \| surface \| sky}` (type in the world) | + Depth Anything V2 (downloads on first use, like `parallax`); a `surface`, or a `behind` named by a prompt, also needs the `reveal` setup above (SAM 2.1, Florence-2: `studio setup-comfy`). A `sky` or a `behind` with a depth number needs no ComfyUI. |
| `film` with `take.product` | + the product's 3D model (.glb/.gltf/.obj/.fbx/.stl/.ply). `from_photo:` instead needs TRELLIS (below). |
| `site.product`, `showroom`, product stills | + Blender. STEP/STP models need `cascadio` (OpenCascade) and 3MF needs `trimesh` + `lxml`: `pip install -e .[cad]` (in `.[all]`). `scene:` stills need ComfyUI (Z-Image, Qwen-Image-Edit). |
| `splat` | A scan as a 3DGS `.ply` (any) or a gsplat `.pt` checkpoint (needs PyTorch to read). No GPU at build time. |
| `diorama` | Nothing beyond the package (NumPy, OpenCV, Pillow lay the world out on the CPU in seconds; no models, no GPU, no Blender). Visitors need WebGL 2. `studio diorama --strip` photographs the built site and needs Chrome. |

`studio doctor` (or the Toolchain page in the UI) shows what this machine has, and opens with what it can build without a GPU.
No GPU: [Try it on a laptop](laptop.md).

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

`studio inspect` (the polish report) needs nothing more: OpenCV, SciPy and NumPy are core dependencies and it runs on the
CPU. Its optional `--embed` drift check also needs `pip install -e .[embed]` (open_clip_torch) and the LAION CLIP ViT-H/14
weights (`laion/CLIP-ViT-H-14-laion2B-s32B-b79K`, 3.9 GB, MIT) already in the Hugging Face cache; it never downloads them
(`huggingface-cli download laion/CLIP-ViT-H-14-laion2B-s32B-b79K open_clip_pytorch_model.bin` fetches them once).

`studio inspect --page` (the polish report of a built page) needs Playwright's Chromium, which `playwright` (a core
dependency) downloads once with `playwright install chromium`; it runs headless, on the CPU, with no network.

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
   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-SeedVR2_VideoUpscaler (`beat_restore`, `take.restore`, and the
   upscale of a frozen moment, `freeze.upscale`; it downloads its ~8 GB of weights into `models/SEEDVR2` on first use,
   and without them a frozen moment falls back to a local Lanczos upscale). Deep zoom (`freeze.detail`) also uses SeedVR2
   and Z-Image Turbo (already listed); layered depth (`freeze.layers`) uses Florence-2, SAM 2.1 and Qwen-Image-Edit through
   the nodes `studio setup-comfy` installs for `reveal` and region edits. No new weights.
2. Download the models listed in `engine/models.yaml` into ComfyUI's model folders (or point
   `extra_model_paths.yaml` at another drive).
   Optional: `camera.backend: uni3c` (keyed camera moves on moving beats) wants the Uni3C camera controlnet,
   `Wan21_Uni3C_controlnet_fp16.safetensors` (about 2 GB, Apache-2.0,
   [Kijai/WanVideo_comfy](https://huggingface.co/Kijai/WanVideo_comfy/blob/main/Wan21_Uni3C_controlnet_fp16.safetensors)),
   in ComfyUI's `models/model_patches/`. It is not installed by default and nothing else needs it: the default backends,
   `ltx` and `wan`, use models you already have. `studio doctor` lists it.
3. Start it and leave it running:
   ```bash
   python main.py --listen 127.0.0.1 --port 8188 --reserve-vram 1.5
   ```
   On Windows set `PYTHONUTF8=1` first. Close games before rendering; they take VRAM and stall renders.

Scroll Studio talks to ComfyUI at `comfy_url` (default http://127.0.0.1:8188).

**Wan 2.2 (optional second video model, `video_model: wan`).** Download the eight Wan files listed in
`engine/models.yaml` from https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged into the same folders (Wan needs
no custom nodes: its nodes ship with ComfyUI). The experts are fp8 14B models of ~14 GB each; on a 24 GB card ComfyUI
holds one on the GPU and swaps to the other half-way through sampling, so keep ~32 GB of system RAM free. If a file
sits in a subfolder or under another name, set it in `studio.toml` under `[wan]` (see `studio.example.toml`);
`studio doctor` asks ComfyUI which files it can load and lists every Wan file as found or missing, with its URL.

**Reveal and faces (optional: `reveal:` and `faces: restore` on a film).** Both run in ComfyUI. `studio setup-comfy`
clones kijai's [ComfyUI-segment-anything-2](https://github.com/kijai/ComfyUI-segment-anything-2) (Apache-2.0) and
[ComfyUI-Florence2](https://github.com/kijai/ComfyUI-Florence2) (MIT) into `custom_nodes/`, copies Scroll Studio's own
`scroll_studio_nodes` there (it holds SAM 2.1 tracking with box prompts and the face repair, and bundles GFPGAN's
network definition under its Apache-2.0 licence) and downloads GFPGAN v1.4 (~350 MB) into `models/facerestore_models/`.
Set `comfy_dir` in `studio.toml` first if ComfyUI isn't at `<model_dir>/ComfyUI`. Then **restart ComfyUI when its queue is
empty** so it loads the nodes. SAM 2.1 Hiera Large (0.45 GB, `models/sam2/`) and Florence-2 large (1.5 GB,
`models/LLM/`) download on the first reveal build, and facexlib's face detector and mask (0.2 GB) on the first `faces`
build. The stages need ~4 GB of VRAM and, per frame of film, ~6 MB of system RAM. `studio doctor` lists every node and file.

## 5. TRELLIS (optional: a product model from one photo)

`take.product.from_photo` turns a product photo into a mesh with TRELLIS before rendering it. Install TRELLIS in
its own environment, then tell Scroll Studio how to run it (`studio.toml` or environment variables):

```toml
trellis_python = "/path/to/trellis/venv/bin/python"      # TRELLIS_PYTHON
trellis_script = "/path/to/trellis/image_to_mesh.py"       # TRELLIS_SCRIPT: --dir <work> reads object.png, writes mesh.ply
```

A real model (`model:`) always looks better than a reconstruction; use the photo route when there is no model.

## 6. Claude

- **Claude Code**: open the repo; `.mcp.json` registers the `scroll-studio` MCP server and the `scroll-site` skill
  teaches the workflow. Ask for a site in plain language.
- **Claude Desktop / other MCP clients**: add a server that runs `python -m engine.mcp_server` with the repo as the
  working directory.
