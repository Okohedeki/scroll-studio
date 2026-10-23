"""Keep the local servers local: answer only requests that were really addressed to this machine.

Every server here binds to 127.0.0.1, but that alone does not stop other web pages. Any page open in the builder's
browser can send requests to 127.0.0.1, and a DNS-rebinding site can make its own name point there. Two checks close both:

- Host: the request's `Host` header must be 127.0.0.1, localhost or [::1] with this server's own port (400 otherwise). A
  rebound `evil.example:5180` arrives with `Host: evil.example:5180` and is refused.
- Origin: a request that changes something (POST, PUT, PATCH, DELETE) and carries an `Origin` (or, without one, a `Referer`)
  must come from one of those same local origins (403 otherwise). A form or script on another site cannot get past this.

`LocalOnly` is the ASGI middleware every FastAPI app uses; `host_allowed` is the same Host check for the plain
http.server preview (engine/serve.py).
"""
from __future__ import annotations

import os
from typing import Iterable, Optional
from urllib.parse import urlsplit

LOCAL_NAMES = ("127.0.0.1", "localhost", "[::1]")
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# `npm run dev:ui` serves the Studio UI from the Vite dev server (ui/vite.config.ts) and proxies /api to `studio ui`; the
# browser's Host and Origin there are its own port. Local names only, so this opens nothing to other sites.
UI_DEV_PORTS = (5181,)


def _split_host(value: str) -> tuple[str, Optional[int]]:
    """'localhost:5180' -> ('localhost', 5180); '[::1]:5180' -> ('[::1]', 5180); 'localhost' -> ('localhost', None)."""
    value = value.strip().lower()
    if value.startswith("["):
        name, _, rest = value.partition("]")
        name += "]"
        port = rest[1:] if rest.startswith(":") else ""
    else:
        name, _, port = value.partition(":")
    return name, int(port) if port.isdigit() else (None if not port else -1)


def host_allowed(host: Optional[str], server_port: Optional[int], extra_ports: Iterable[int] = ()) -> bool:
    """Is this `Host` header one of ours? The port must be this server's own (or an allowed extra); no port means 80."""
    if not host:
        return False
    name, port = _split_host(host)
    if name not in LOCAL_NAMES or port == -1:
        return False
    ports = {p for p in (server_port, *extra_ports) if p}
    return (port if port is not None else 80) in ports


def local_origins(server_port: Optional[int], extra_ports: Iterable[int] = ()) -> set[str]:
    out = set()
    for port in {p for p in (server_port, *extra_ports) if p}:
        for name in LOCAL_NAMES:
            out.add(f"http://{name}:{port}")
            if port == 80:
                out.add(f"http://{name}")
    return out


def origin_allowed(origin: Optional[str], referer: Optional[str], server_port: Optional[int], extra_ports: Iterable[int] = ()) -> bool:
    """For a request that changes something: no Origin and no Referer is a command-line or same-origin tool and passes; an
    Origin (else the Referer's origin) that is not one of ours does not."""
    if origin is None and referer is None:
        return True
    seen = origin
    if seen is None:
        parts = urlsplit(referer or "")
        seen = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else "invalid"
    return seen.strip().lower() in local_origins(server_port, extra_ports)


class LocalOnly:
    """ASGI middleware: Host check on every request, Origin/Referer check on every request that changes something."""

    def __init__(self, app, extra_ports: Iterable[int] = ()) -> None:
        self.app = app
        extra = [int(p) for p in os.environ.get("STUDIO_UI_DEV_PORT", "").split(",") if p.strip().isdigit()]
        self.extra_ports = tuple(extra_ports) + tuple(extra)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        port = (scope.get("server") or (None, None))[1]
        if not host_allowed(headers.get("host"), port, self.extra_ports):
            await self._refuse(scope, receive, send, 400, "Host not allowed: this server only answers to 127.0.0.1, localhost "
                                                          "and [::1] on its own port.")
            return
        changes = scope["type"] == "websocket" or scope.get("method", "GET") in UNSAFE_METHODS
        if changes and not origin_allowed(headers.get("origin"), headers.get("referer"), port, self.extra_ports):
            await self._refuse(scope, receive, send, 403, "Cross-origin request refused: only pages served by this server "
                                                          "may change anything here.")
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _refuse(scope, receive, send, status: int, message: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = message.encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode()),
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})
