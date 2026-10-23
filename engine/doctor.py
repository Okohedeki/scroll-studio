"""`studio doctor`: check every external tool and say which scene types are ready."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

from .config import STATIC, settings


def _ver(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0] if out.returncode == 0 else None
    except Exception:
        return None


def checks() -> list[dict]:
    s = settings()
    res = []
    def add(name, ok, detail, needed_by):
        res.append({"name": name, "ok": bool(ok), "detail": detail or "missing", "needed_by": needed_by})

    add("Node.js", _ver(["node", "--version"]), _ver(["node", "--version"]), "building the runtime and UI")
    add("Runtime bundle", (STATIC / "runtime" / "index.js").exists(), "engine/compile/static/runtime", "every site (npm run build)")
    ff = _ver([s["ffmpeg"], "-version"])
    add("FFmpeg", ff, ff and ff[:40], "film, sequence, recordings")
    bl = _ver([s["blender"], "--version"])
    add("Blender", bl, bl or s["blender"], "film (blockout), sequence")
    try:
        import torch
        gpu = torch.cuda.is_available()
        detail = f"{torch.cuda.get_device_name(0)}, {torch.cuda.get_device_properties(0).total_memory / 2**30:.0f} GB" if gpu else "no CUDA GPU"
        add("PyTorch + CUDA", gpu, detail, "parallax (depth), film")
    except Exception:
        add("PyTorch + CUDA", False, "torch not installed", "parallax (depth), film")
    for mod, need in (("transformers", "parallax (depth)"), ("cv2", "artwork"), ("websocket", "recordings"), ("playwright", "recordings, URL capture"),
                      ("cascadio", "product models in STEP/STP (OpenCascade)"), ("trimesh", "product models in 3MF"),
                      ("lxml", "product models in 3MF")):
        add(mod, importlib.util.find_spec(mod), "installed" if importlib.util.find_spec(mod) else None, need)
    try:
        from .backends import comfy
        add("ComfyUI", comfy.alive(), s["comfy_url"] if comfy.alive() else f"not running at {s['comfy_url']}",
            "film, generated images (`generate:`)")
    except Exception as e:
        add("ComfyUI", False, str(e), "film, generated images")
    res.extend(wan_checks())
    res.extend(uni3c_checks())
    res.extend(reveal_checks())
    res.extend(checksum_checks())
    add("Chrome", shutil.which("chrome") or Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe").exists() or s["chrome"],
        "found", "recordings")
    return res


def wan_checks() -> list[dict]:
    """Every Wan 2.2 file (engine/models.yaml entries with `wan:`), looked up in ComfyUI's own model lists, so a
    file in a subfolder, on another drive behind a junction, or renamed in studio.toml [wan] is found where ComfyUI
    loads it from. Without ComfyUI running, the check can't see them and says so."""
    import yaml
    from .backends import comfy
    entries = [m for m in yaml.safe_load((Path(__file__).parent / "models.yaml").read_text(encoding="utf-8"))["comfyui"]
               if m.get("wan")]
    names = comfy.wan_model_names()
    lists, out = {}, []
    for m in entries:
        key = m["wan"]
        folder = comfy.WAN_FOLDERS[key]
        if folder not in lists:
            lists[folder] = comfy.listed(folder)
        have, want = lists[folder], names[key]
        base = want.replace("\\", "/").rsplit("/", 1)[-1]
        if have is None:
            ok, detail = False, f"{want}: ComfyUI not running, can't check"
        else:
            hit = want if want in have else next((h for h in have if h.replace("\\", "/").rsplit("/", 1)[-1] == base), None)
            ok = hit is not None
            detail = f"{folder}/{hit}" if ok else f"missing {folder}/{want} ({m['size_gb']} GB): {m['source']}"
        out.append({"name": m["name"], "ok": ok, "detail": detail, "needed_by": ", ".join(m.get("used_by", []))})
    return out


def uni3c_checks() -> list[dict]:
    """The optional Uni3C camera controlnet (`camera.backend: uni3c`): found in ComfyUI's model_patches list, or noted as not
    installed (it is not a failure: the other camera backends need nothing extra)."""
    from .backends import comfy
    from . import camera_guide as cg
    have = comfy.listed("model_patches")
    name = "Uni3C camera controlnet (optional)"
    need = "film beats with camera.backend uni3c"
    if have is None:
        return [{"name": name, "ok": False, "detail": "ComfyUI not running, can't check", "needed_by": need}]
    hit = next((h for h in have if h.replace("\\", "/").rsplit("/", 1)[-1] == cg.UNI3C_FILE), None)
    return [{"name": name, "ok": True, "detail": f"model_patches/{hit}" if hit else
             f"not installed (optional, ~2 GB, Apache-2.0): {cg.UNI3C_SOURCE}", "needed_by": need}]


def reveal_checks() -> list[dict]:
    """`reveal` and `faces: restore`: the ComfyUI nodes (asked of ComfyUI itself, so they count only once it has loaded them)
    and the model files that can be seen on disk (SAM 2.1 and Florence-2 download on first use, so missing is a note)."""
    from .backends import comfy, comfy_setup
    out = []
    up = comfy.alive()
    for label, nodes, need, fix in (
            ("ComfyUI nodes: SAM 2.1 + Florence-2 (kijai)", ("DownloadAndLoadSAM2Model", "DownloadAndLoadFlorence2Model"), "film reveal",
             "ComfyUI-segment-anything-2 and ComfyUI-Florence2 in custom_nodes"),
            ("ComfyUI nodes: Scroll Studio (tracking, faces)", ("SSRevealTrack", "SSRevealGround", "SSFaceRestore"), "film reveal, faces: restore",
             "")):
        if not up:
            out.append({"name": label, "ok": False, "detail": "ComfyUI not running, can't check", "needed_by": need})
            continue
        missing = []
        for n in nodes:
            try:
                comfy._req(f"/object_info/{n}")
            except Exception:
                missing.append(n)
        out.append({"name": label, "ok": not missing, "detail": "loaded" if not missing else
                    f"ComfyUI has no {', '.join(missing)}: run `studio setup-comfy`, then restart ComfyUI", "needed_by": need})
    root = comfy_setup.comfy_dir()
    import yaml
    for m in yaml.safe_load((Path(__file__).parent / "models.yaml").read_text(encoding="utf-8"))["comfyui"]:
        if not m.get("node"):
            continue
        if root is None:
            out.append({"name": m["name"], "ok": False, "detail": "ComfyUI folder unknown (set comfy_dir in studio.toml)",
                        "needed_by": ", ".join(m["used_by"])})
            continue
        path = root / "models" / m["file"]
        ok = path.exists()
        auto = m["node"] in ("sam2", "florence2")
        out.append({"name": m["name"], "ok": ok or auto,
                    "detail": str(path) if ok else (f"not downloaded yet: it downloads on first use ({m['size_gb']} GB)" if auto else
                                                    f"missing {path} ({m['size_gb']} GB): `studio setup-comfy`"),
                    "needed_by": ", ".join(m["used_by"])})
    return out


def checksum_checks() -> list[dict]:
    """How many ComfyUI model files in engine/models.yaml have a pinned SHA-256 (the rest are used unverified)."""
    from .weights import model_entries
    entries = model_entries()
    loose = [m["file"] for m in entries if not m.get("sha256")]
    detail = (f"{len(entries) - len(loose)} of {len(entries)} model files pinned" +
              (f"; not pinned yet: {', '.join(loose)}" if loose else "") + ". `studio doctor --verify` hashes the files on disk")
    return [{"name": "Model checksums", "ok": not loose, "detail": detail, "needed_by": "every model download and install"}]


def verify_models() -> list[dict]:
    """Hash every pinned model file found in ComfyUI's models folder and compare it with models.yaml (slow: some are 15 GB)."""
    from .backends import comfy_setup
    from .weights import ChecksumError, check_sha256, model_entries
    root = comfy_setup.comfy_dir()
    if root is None:
        return [{"name": "Model files (SHA-256)", "ok": False, "detail": "ComfyUI folder unknown (set comfy_dir in studio.toml)",
                 "needed_by": "every model"}]
    out = []
    for m in model_entries():
        path = root / "models" / m["file"]
        if not path.exists() or not m.get("sha256"):
            continue
        try:
            check_sha256(path, m["sha256"], m["source"])
            ok, detail = True, f"{m['file']}: matches"
        except ChecksumError as e:
            ok, detail = False, str(e)
        out.append({"name": m["name"], "ok": ok, "detail": detail, "needed_by": ", ".join(m.get("used_by", []))})
    return out or [{"name": "Model files (SHA-256)", "ok": True, "detail": "no pinned model files found on disk", "needed_by": "every model"}]


def report(verify: bool = False) -> None:
    from rich.console import Console
    from rich.table import Table
    t = Table(title="Scroll Studio doctor")
    for c in ("", "Check", "Detail", "Needed by"):
        t.add_column(c)
    for c in checks() + (verify_models() if verify else []):
        t.add_row("[green]✓[/]" if c["ok"] else "[red]✗[/]", c["name"], str(c["detail"]), c["needed_by"])
    Console().print(t)
