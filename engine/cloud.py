"""The Scroll Studio cloud account: provider jobs on credits, for builders without API keys of their own.

Everything here is optional. Local models and your own provider keys are free and come first; the account backend is
the router's last choice, and only when `models:` asks for providers (or pins `cloud`). `studio cloud login` signs in
with a link sent to your email:

    studio cloud login --email you@example.com      # opens nothing; click the link in the email
    studio cloud status                              # balance and what each job costs
    studio cloud buy                                 # a checkout page for a credit pack

The sign-in is kept in a credentials file in the user's config folder (Windows %APPDATA%\\scroll-studio, macOS
~/Library/Application Support/scroll-studio, Linux $XDG_CONFIG_HOME/scroll-studio), or STUDIO_CLOUD_TOKEN and
STUDIO_CLOUD_URL for CI. The service's API is small: POST /v1/jobs takes a job and its input images, GET /v1/jobs/<id>
reports it, GET /v1/jobs/<id>/output returns the file.
"""
from __future__ import annotations

import base64
import json
import os
import sys
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
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "scroll-studio"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "scroll-studio"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "scroll-studio"


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
    return {"url": (url or "").rstrip("/") or None, "token": token, "email": saved.get("email")}


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


def checkout(pack: Optional[str] = None) -> str:
    with _client() as c:
        return _check(c.post("/v1/checkout", json={"pack": pack}))["url"]


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
    """The Scroll Studio cloud account: every provider job kind, on credits. Available once `studio cloud login` has
    run (or STUDIO_CLOUD_TOKEN is set). The service picks the provider for each kind unless `models.model.<kind>`
    names one of its models."""
    name = "cloud"
    local = False
    kinds: tuple[Kind, ...] = ("image", "edit", "text", "speech", "video")

    def available(self) -> tuple[bool, str]:
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
