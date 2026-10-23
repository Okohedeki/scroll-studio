"""Static server for a built site (dist/) with HTTP Range support (browsers need it to seek video)."""
import http.server
import os
import re
import sys

import threading

try:
    from .server.local_only import host_allowed
except ImportError:      # run as a plain script (python engine/serve.py dist 5173)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engine.server.local_only import host_allowed


class Handler(http.server.SimpleHTTPRequestHandler):
    root = "."
    # Windows can map .js to text/plain from the registry; module scripts then refuse to load.
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
                      ".webp": "image/webp", ".avif": "image/avif", ".mp4": "video/mp4", ".webm": "video/webm",
                      ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".wasm": "application/wasm", ".svg": "image/svg+xml"}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=self.root, **kw)

    def log_message(self, *a):
        pass

    def _local(self) -> bool:
        """Only requests really addressed to this machine (127.0.0.1, localhost, [::1] and this port): a page on another
        site that rebinds its DNS name to 127.0.0.1 sends its own name as Host and gets a 400."""
        if host_allowed(self.headers.get("Host"), self.server.server_address[1]):
            return True
        self.send_error(400, "Host not allowed: this preview only answers to 127.0.0.1, localhost and [::1] on its own port")
        return False

    def do_GET(self):
        if self._local():
            super().do_GET()

    def do_HEAD(self):
        if self._local():
            super().do_HEAD()

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        path = self.translate_path(self.path)
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else size - int(m.group(2))
        end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        end = min(end, size - 1)
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self._remaining = None


def serve(root, port=5173, background=False):
    handler = type("RootHandler", (Handler,), {"root": str(root)})
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    if background:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd
    print(f"Serving {root} at http://localhost:{port}  (Ctrl+C to stop)")
    httpd.serve_forever()


if __name__ == "__main__":
    serve(sys.argv[1] if len(sys.argv) > 1 else ".", int(sys.argv[2]) if len(sys.argv) > 2 else 5173)
