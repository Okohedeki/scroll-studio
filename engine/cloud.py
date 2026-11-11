"""The DesignAI cloud account, for people who can't run DesignAI on their own machine.

Everything here is optional: DesignAI runs locally for free, with open models or your own provider keys. The account
adds two things, paid in credits:

- hosted builds: `studio build my-site --cloud` sends the project to the service, which runs the same build with the
  same open models on its GPU and sends dist/ back. Charged by the GPU minute; nothing runs on your machine.
- provider jobs: the router's last choice for single image, edit, text, speech and video jobs, used only when a
  project's `models:` asks for providers (or pins `cloud`), for builders with no provider keys.

    studio cloud login --email you@example.com      # click the link in the email
    studio cloud status                              # balance, the GPU rate, what each job costs
    studio cloud buy                                 # a checkout page for a credit pack (or --plan, monthly)
    studio cloud workspace create "Shop team"        # a team workspace: one shared balance, seats, invites

Credits belong to a workspace. Everyone has a personal one; `studio cloud workspace use <id>` makes a team's the
one spent from on this machine (or STUDIO_CLOUD_WORKSPACE).

The sign-in is kept in a credentials file in the user's config folder (Windows %APPDATA%\\designai, macOS
~/Library/Application Support/designai, Linux $XDG_CONFIG_HOME/designai), or STUDIO_CLOUD_TOKEN and
STUDIO_CLOUD_URL for CI. STUDIO_CLOUD_DISABLED=1 turns the account off (the service sets it on its own build machine).
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

from .router.core import EditJob, Job, Kind, Result, VideoJob

JOB_TIMEOUT = 45 * 60     # seconds: a long video job on a busy service


class CloudError(RuntimeError):
    pass


def config_dir() -> Path:
    if os.environ.get("STUDIO_CONFIG_DIR"):
        return Path(os.environ["STUDIO_CONFIG_DIR"])
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "designai"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "designai"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "designai"


def _creds_path() -> Path:
    return config_dir() / "cloud.json"


def credentials() -> dict:
    """{url, token, email} of the signed-in account, from the environment first, else the credentials file."""
    saved: dict = {}
    try:
        saved = json.loads(_creds_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    url = os.environ.get("STUDIO_CLOUD_URL") or saved.get("url") or _setting("cloud_url")
    token = os.environ.get("STUDIO_CLOUD_TOKEN") or saved.get("token")
    workspace = os.environ.get("STUDIO_CLOUD_WORKSPACE") or saved.get("workspace")
    return {"url": (url or "").rstrip("/") or None, "token": token, "email": saved.get("email"),
            "workspace": workspace or None}


def _setting(key: str) -> Optional[str]:
    from .config import settings
    return settings().get(key)


def save(url: str, token: str, email: str) -> Path:
    path = _creds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url.rstrip("/"), "token": token, "email": email}, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)       # owner-only on macOS and Linux; Windows keeps the profile folder's own ACL
    except OSError:
        pass
    return path


def use_workspace(wid: Optional[str]) -> None:
    """Spend from this workspace on this machine from now on (None: the personal one)."""
    path = _creds_path()
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CloudError("not signed in: `studio cloud login`")
    saved.pop("workspace", None)
    if wid:
        saved["workspace"] = wid
    path.write_text(json.dumps(saved, indent=2), encoding="utf-8")


def forget() -> bool:
    try:
        _creds_path().unlink()
        return True
    except FileNotFoundError:
        return False


def _client(url: Optional[str] = None, token: Optional[str] = None):
    import httpx
    c = credentials()
    url, token = url or c["url"], token or c["token"]
    if not url:
        raise CloudError("no cloud service set: `studio cloud login --url <service>` (or cloud_url in studio.toml)")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if token and c["workspace"]:
        headers["X-Workspace"] = c["workspace"]
    return httpx.Client(base_url=url, headers=headers, timeout=120)


def _check(r) -> dict:
    if r.status_code == 402:
        raise CloudError(_detail(r) + " Top up with `studio cloud buy`.")
    if r.status_code == 401:
        raise CloudError("the cloud sign-in has expired or was revoked: run `studio cloud login` again")
    if r.status_code >= 400:
        raise CloudError(f"cloud service: {r.status_code} {_detail(r)}")
    return r.json() if r.content else {}


def _detail(r) -> str:
    try:
        d = r.json().get("detail")
        return d if isinstance(d, str) else json.dumps(d)
    except ValueError:
        return r.text[:300]


# ---------------------------------------------------------------- sign-in and account

def login(email: str, url: Optional[str] = None, log: Callable[[str], None] = print, open_link: bool = False) -> dict:
    """Email a sign-in link and wait for it to be clicked; save the account. Returns {email, balance}."""
    url = (url or credentials()["url"] or "").rstrip("/")
    with _client(url, token="") as c:
        start = _check(c.post("/v1/login", json={"email": email}))
        log(f"Sent a sign-in link to {email}. Open it and confirm; this waits for up to "
            f"{start['expires_in'] // 60} minutes.")
        if start.get("dev_link"):          # a service in development mode shows the link instead of emailing it
            log(f"  (development service) sign-in link: {start['dev_link']}")
            if open_link:
                import webbrowser
                webbrowser.open(start["dev_link"])
        deadline = time.time() + start["expires_in"]
        while time.time() < deadline:
            time.sleep(start.get("interval", 2))
            r = c.post("/v1/login/poll", json={"device_code": start["device_code"]})
            if r.status_code == 428:       # not clicked yet
                continue
            got = _check(r)
            save(url, got["token"], got["email"])
            return {"email": got["email"], "balance": got.get("balance")}
    raise CloudError("the sign-in link expired before it was used: run `studio cloud login` again")


def account() -> dict:
    with _client() as c:
        return _check(c.get("/v1/account"))


def checkout(pack: Optional[str] = None, plan: Optional[str] = None) -> str:
    """A checkout link for a credit pack, or for a monthly plan, for the workspace in use."""
    with _client() as c:
        return _check(c.post("/v1/checkout", json={"plan": plan} if plan else {"pack": pack}))["url"]


# ---------------------------------------------------------------- workspaces

def workspaces() -> list[dict]:
    with _client() as c:
        return _check(c.get("/v1/workspaces"))["workspaces"]


def create_workspace(name: str) -> dict:
    with _client() as c:
        return _check(c.post("/v1/workspaces", json={"name": name}))


def workspace(wid: str) -> dict:
    with _client() as c:
        return _check(c.get(f"/v1/workspaces/{wid}"))


def invite(wid: str, email: str, role: str = "member") -> dict:
    with _client() as c:
        r = c.post(f"/v1/workspaces/{wid}/invites", json={"email": email, "role": role})
        if r.status_code == 402:          # seats, not credits
            raise CloudError(_detail(r))
        return _check(r)


def remove(wid: str, email: str) -> str:
    """Take someone out of a workspace, or withdraw their invite; returns which it was."""
    w = workspace(wid)
    email = email.strip().lower()
    with _client() as c:
        for m in w["members"]:
            if m["email"].lower() == email:
                _check(c.delete(f"/v1/workspaces/{wid}/members/{m['id']}"))
                return "removed"
        for i in w["invites"]:
            if i["email"].lower() == email:
                _check(c.delete(f"/v1/workspaces/{wid}/invites/{i['id']}"))
                return "invite withdrawn"
    raise CloudError(f"{email} is not in {w['name']} and has no invite to it")


def logout() -> bool:
    c = credentials()
    if c["url"] and c["token"]:
        try:
            with _client() as cl:
                cl.post("/v1/logout")
        except Exception:
            pass
    return forget()


# ---------------------------------------------------------------- jobs

def _pack(job: Job) -> tuple[dict, dict]:
    """The job as JSON, its input files moved into `inputs` (name -> base64) and replaced by '@name'."""
    data, inputs = asdict(job), {}

    def put(path: Optional[str]) -> Optional[str]:
        if not path:
            return path
        key = str(len(inputs))
        inputs[key] = base64.b64encode(Path(path).read_bytes()).decode()
        return "@" + key
    if isinstance(job, EditJob):
        data["images"] = [put(p) for p in job.images]
    elif isinstance(job, VideoJob):
        data["image"], data["end_image"] = put(job.image), put(job.end_image)
    return data, inputs


def run_job(job: Job, out: Optional[Path], model: Optional[str] = None, backend: Optional[str] = None,
            log: Callable[[str], None] = lambda m: None) -> dict:
    """Send `job` to the service, wait for it, write the output file to `out` (text jobs return it). The answer's
    `credits` is what the job cost and `balance` what is left."""
    data, inputs = _pack(job)
    with _client() as c:
        made = _check(c.post("/v1/jobs", json={"job": data, "inputs": inputs, "model": model, "backend": backend}))
        jid, t0 = made["id"], time.time()
        while True:
            st = _check(c.get(f"/v1/jobs/{jid}"))
            if st["status"] == "done":
                break
            if st["status"] == "failed":
                raise CloudError(f"cloud job failed (its {made.get('credits', 0)} credits were refunded): "
                                 f"{st.get('error') or 'no reason given'}")
            if time.time() - t0 > JOB_TIMEOUT:
                raise CloudError(f"cloud job {jid} did not finish in {JOB_TIMEOUT // 60} minutes")
            time.sleep(1.0 if job.kind in ("text", "image", "edit") else 4.0)
        if out is not None and st.get("has_output"):
            r = c.get(f"/v1/jobs/{jid}/output", timeout=600)
            if r.status_code >= 400:
                _check(r)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
    return st


class CloudBackend:
    """The DesignAI cloud account: every provider job kind, on credits. Available once `studio cloud login` has
    run (or STUDIO_CLOUD_TOKEN is set). The service picks the provider for each kind unless `models.model.<kind>`
    names one of its models."""
    name = "cloud"
    local = False
    kinds: tuple[Kind, ...] = ("image", "edit", "text", "speech", "video")

    def available(self) -> tuple[bool, str]:
        if os.environ.get("STUDIO_CLOUD_DISABLED"):
            return False, "the cloud account is turned off here (STUDIO_CLOUD_DISABLED)"
        c = credentials()
        if not c["token"]:
            return False, "not signed in (studio cloud login)"
        if not c["url"]:
            return False, "no cloud service set (studio cloud login --url)"
        return True, ""

    def model(self, kind: Kind) -> str:
        return "service default"

    def run(self, job: Job, out: Optional[Path], model: Optional[str] = None) -> Result:
        st = run_job(job, out, model)
        from .router.util import _fit
        if out is not None and job.kind in ("image", "edit") and out.exists():
            w, h = (job.width, job.height) if job.kind == "image" else _size(job.images[0])
            _fit(out.read_bytes(), out, w, h)
        return Result(self.name, f"{st.get('backend')}:{st.get('model')}", 0.0, path=out if job.kind != "text" else None,
                      text=st.get("text"), meta={"credits": st.get("credits"), "balance": st.get("balance")})


def _size(path: str) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


# ---------------------------------------------------------------- hosted builds

LEAVE_HOME = {".build", "dist", ".git", "node_modules", "__pycache__", ".venv", ".DS_Store"}
MAX_UPLOAD = 500 * 2**20


def pack_project(folder: Path, archive: Path) -> tuple[int, int]:
    """The project as .tar.gz, leaving out what the build makes (.build, dist) and tool folders. Links are left out
    too: the service takes plain files only. Returns (files, bytes before compression)."""
    files = size = 0
    with tarfile.open(archive, "w:gz") as tar:
        for p in sorted(folder.rglob("*")):
            rel = p.relative_to(folder)
            if any(part in LEAVE_HOME for part in rel.parts) or p.is_symlink() or not p.is_file():
                continue
            tar.add(p, arcname=rel.as_posix(), recursive=False)
            files, size = files + 1, size + p.stat().st_size
    return files, size


def unpack_dist(data: bytes, dest: Path) -> None:
    """dist/ from the service, written into `dest` (replacing it); names that would leave `dest` are refused."""
    tmp = dest.with_name(dest.name + ".cloud-part")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    root = tmp.resolve()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            target = (tmp / m.name).resolve()
            if not (m.isfile() or m.isdir()) or (target != root and root not in target.parents):
                raise CloudError(f"the service sent an unusable file name in dist/: {m.name}")
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(m).read())
    shutil.rmtree(dest, ignore_errors=True)
    tmp.replace(dest)


def build(folder: Path, options: dict, max_minutes: Optional[int] = None, log: Callable[[str], None] = print,
          poll: float = 2.0) -> dict:
    """Run `studio build` for the project in `folder` on the service's GPU; dist/ comes back into the project.
    Credits for up to `max_minutes` are held while it runs; the minutes it used are charged and the rest returned.
    Ctrl+C cancels the build on the service too."""
    with tempfile.TemporaryDirectory() as t, _client() as c:
        archive = Path(t) / "project.tar.gz"
        files, size = pack_project(folder, archive)
        packed = archive.stat().st_size
        if packed > MAX_UPLOAD:
            raise CloudError(f"the project is {packed / 2**20:.0f} MB packed, over the {MAX_UPLOAD // 2**20} MB "
                             "upload limit: keep large inputs as links (https://...) in the spec")
        log(f"uploading {folder.name}: {files} files, {packed / 2**20:.1f} MB")
        form = {"options": json.dumps(options), "project": folder.name}
        if max_minutes:
            form["max_minutes"] = str(max_minutes)
        with open(archive, "rb") as f:
            made = _check(c.post("/v1/builds", data=form, files={"bundle": ("project.tar.gz", f, "application/gzip")},
                                 timeout=1800))
        bid = made["id"]
        log(f"hosted build {bid} on {made.get('gpu') or 'the service GPU'}: {made['rate']} credits a minute, holding "
            f"{made['hold']} for up to {made['max_minutes']} minutes (unused credits come back)")
        since = 0
        try:
            while True:
                st = _check(c.get(f"/v1/builds/{bid}", params={"since": since}))
                for line in st["lines"]:
                    log(line)
                since = st["next"]
                if st["status"] not in ("queued", "running"):
                    break
                if not st["lines"]:
                    time.sleep(poll)
        except KeyboardInterrupt:
            log("cancelling the hosted build...")
            c.post(f"/v1/builds/{bid}/cancel")
            raise
        if st["status"] != "done":
            raise CloudError(f"hosted build {st['status']}: {st.get('error') or 'no reason given'} "
                             f"({st['charged']} credits charged, balance {st['balance']})")
        r = c.get(f"/v1/builds/{bid}/output", timeout=1800)
        if r.status_code >= 400:
            _check(r)
        unpack_dist(r.content, folder / "dist")
        log(f"hosted build done: {st['minutes']} GPU minutes, {st['charged']} credits; balance {st['balance']}")
        return st
