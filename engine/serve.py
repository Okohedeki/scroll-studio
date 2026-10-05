"""Static server for a built site (dist/) with HTTP Range support (browsers need it to seek video)."""
import http.server
import os
import re
import sys

import threading


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
