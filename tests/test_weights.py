"""Model weights are verified before they are used: downloads are hashed (and refused on a mismatch), and torch files
are never fully unpickled. Small fake files and a fake downloader: no network, no GPU."""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

import pytest

from engine import doctor, weights
from engine.backends import comfy_setup
from engine.weights import ChecksumError

ROOT = Path(__file__).resolve().parent.parent
GOOD = b"pretend weights"
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()
URL = "https://example.com/models/fake.pth"


class Custom:      # a Python object inside a checkpoint, as a hostile one would carry
    pass


def fetcher(data: bytes):
    def fetch(url: str, path: str) -> None:
        Path(path).write_bytes(data)
    return fetch


# ---------------------------------------------------------------- downloads

def test_a_matching_download_is_moved_into_place(tmp_path):
    dest = tmp_path / "models" / "fake.pth"
    out = weights.download_verified(URL, dest, GOOD_SHA, log=lambda m: None, fetch=fetcher(GOOD))
    assert out == dest and dest.read_bytes() == GOOD
    assert not list(dest.parent.glob("*.part"))


def test_a_mismatch_deletes_the_download_and_names_everything(tmp_path):
    dest = tmp_path / "fake.pth"
    with pytest.raises(ChecksumError) as e:
        weights.download_verified(URL, dest, GOOD_SHA, log=lambda m: None, fetch=fetcher(b"something else"))
    msg = str(e.value)
    assert "fake.pth" in msg and GOOD_SHA in msg and hashlib.sha256(b"something else").hexdigest() in msg and URL in msg
    assert not dest.exists() and not list(tmp_path.glob("*.part"))


def test_a_mismatch_leaves_an_existing_file_alone(tmp_path):
    dest = tmp_path / "fake.pth"
    dest.write_bytes(b"older copy")
    with pytest.raises(ChecksumError):
        weights.download_verified(URL, dest, GOOD_SHA, log=lambda m: None, fetch=fetcher(b"tampered"))
    assert dest.read_bytes() == b"older copy"


def test_a_failed_download_leaves_no_partial_file(tmp_path):
    def boom(url, path):
        Path(path).write_bytes(b"half")
        raise OSError("connection reset")
    with pytest.raises(OSError):
        weights.download_verified(URL, tmp_path / "fake.pth", GOOD_SHA, fetch=boom)
    assert list(tmp_path.iterdir()) == []


def test_an_unpinned_download_is_used_with_a_warning(tmp_path):
    logged: list[str] = []
    dest = tmp_path / "fake.pth"
    weights.download_verified(URL, dest, None, log=logged.append, fetch=fetcher(GOOD))
    assert dest.read_bytes() == GOOD
    assert any("warning" in m and "fake.pth" in m and "not verified" in m for m in logged)


def test_the_checksum_accepts_the_prefixed_and_upper_case_forms_and_rejects_junk(tmp_path):
    f = tmp_path / "w.bin"
    f.write_bytes(GOOD)
    weights.check_sha256(f, "sha256:" + GOOD_SHA.upper(), URL)
    with pytest.raises(ValueError):
        weights.check_sha256(f, "abc123", URL)


# ---------------------------------------------------------------- studio setup-comfy

def _fake_comfy(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "ComfyUI"
    (root / "custom_nodes").mkdir(parents=True)
    monkeypatch.setattr(comfy_setup, "comfy_dir", lambda: root)
    monkeypatch.setattr(comfy_setup, "PACKS", {})
    monkeypatch.setattr(comfy_setup, "OWN", tmp_path / "no-nodes")
    monkeypatch.setattr(comfy_setup.shutil, "copytree", lambda *a, **k: None)
    return root


def test_setup_comfy_refuses_a_download_that_does_not_match_models_yaml(tmp_path, monkeypatch):
    root = _fake_comfy(tmp_path, monkeypatch)
    monkeypatch.setattr(weights.urllib.request, "urlretrieve", lambda url, path: Path(path).write_bytes(b"not gfpgan"))
    with pytest.raises(ChecksumError, match="GFPGANv1.4.pth"):
        comfy_setup.install(lambda m: None)
    assert not (root / "models" / "facerestore_models" / "GFPGANv1.4.pth").exists()
    assert not list((root / "models").rglob("*.part"))


def test_setup_comfy_keeps_a_download_that_matches(tmp_path, monkeypatch):
    root = _fake_comfy(tmp_path, monkeypatch)
    monkeypatch.setattr(comfy_setup, "pinned_sha256", lambda rel: GOOD_SHA)
    monkeypatch.setattr(weights.urllib.request, "urlretrieve", lambda url, path: Path(path).write_bytes(GOOD))
    changed = comfy_setup.install(lambda m: None)
    assert "facerestore_models/GFPGANv1.4.pth" in changed
    assert (root / "models" / "facerestore_models" / "GFPGANv1.4.pth").read_bytes() == GOOD


# ---------------------------------------------------------------- models.yaml

def test_every_sha256_in_models_yaml_is_a_real_looking_hash_or_null():
    entries = weights.model_entries()
    assert entries and all("sha256" in m for m in entries), "every ComfyUI model records a sha256 (null = not pinned yet)"
    for m in entries:
        assert m["sha256"] is None or re.fullmatch(r"[0-9a-f]{64}", m["sha256"]), m["file"]
    assert weights.pinned_sha256("facerestore_models/GFPGANv1.4.pth"), "the file the engine downloads itself must be pinned"
    assert len({m["sha256"] for m in entries if m["sha256"]}) == len([m for m in entries if m["sha256"]]), "no hash copied twice"


def test_doctor_reports_pinned_files_and_verifies_the_ones_on_disk(tmp_path, monkeypatch):
    [row] = doctor.checksum_checks()
    assert "pinned" in row["detail"]
    root = tmp_path / "ComfyUI"
    f = root / "models" / "facerestore_models" / "GFPGANv1.4.pth"
    f.parent.mkdir(parents=True)
    f.write_bytes(GOOD)
    monkeypatch.setattr(comfy_setup, "comfy_dir", lambda: root)
    rows = doctor.verify_models()
    assert len(rows) == 1 and not rows[0]["ok"] and "does not match" in rows[0]["detail"]


# ---------------------------------------------------------------- torch files

def test_every_torch_load_in_the_engine_is_weights_only():
    """A pickle can run code when loaded. Anything that needs more than tensors must be written as its own exception
    (with a checksum), not slipped in as a bare torch.load."""
    bad = []
    for f in (ROOT / "engine").rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in ("torch.load", "pickle.load", "pickle.loads", "joblib.load"):
                kw = {k.arg: k.value for k in node.keywords}
                ok = ast.unparse(node.func) == "torch.load" and isinstance(kw.get("weights_only"), ast.Constant) and kw["weights_only"].value is True
                if not ok:
                    bad.append(f"{f.relative_to(ROOT).as_posix()}:{node.lineno}")
    assert not bad, "torch.load needs weights_only=True (and nothing else may unpickle): " + ", ".join(bad)


def test_numpy_files_never_allow_pickles():
    """numpy refuses pickles by default; nothing may switch that on."""
    for f in (ROOT / "engine").rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in ("np.load", "numpy.load"):
                kw = {k.arg: k.value for k in node.keywords}
                allowed = kw.get("allow_pickle")
                assert allowed is None or (isinstance(allowed, ast.Constant) and allowed.value is False), \
                    f"{f.relative_to(ROOT).as_posix()}:{node.lineno} np.load must not allow pickles"


def test_gsplat_checkpoints_load_weights_only_and_refuse_other_objects(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    from engine.backends import splats
    n = 4
    state = {"means": torch.zeros(n, 3), "quats": torch.zeros(n, 4), "scales": torch.zeros(n, 3),
             "opacities": torch.zeros(n), "sh0": torch.zeros(n, 1, 3)}
    good = tmp_path / "ok.pt"
    torch.save({"step": 1, "splats": state}, good)
    seen = {}
    real = torch.load
    monkeypatch.setattr(torch, "load", lambda *a, **k: (seen.update(k), real(*a, **k))[1])
    out = splats.read(good)
    assert seen.get("weights_only") is True and out["means"].shape == (n, 3)

    bad = tmp_path / "bad.pt"
    torch.save({"splats": state, "extra": Custom()}, bad)
    with pytest.raises(ValueError, match="more than tensors"):
        splats.read(bad)
