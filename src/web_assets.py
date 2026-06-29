"""
src/web_assets.py — a localhost HTTP server for the built-in 3D viewer (V1.77).

The 3D viewer (``html/scene3d.html``) is an ES-module app: it imports three.js +
Spark via ``<script type="module">`` + an importmap. Served over ``file://`` —
or a custom URL scheme — ES-module loading is at the mercy of the bundled
Chromium's local-origin rules, which a newer Chromium (pulled by the first
CI-built Windows installer) tightened, breaking the viewer with a "needs the
network" notice even online.

Serving it over a real ``http://127.0.0.1`` origin sidesteps all of that:
localhost is a normal, *secure* browsing context where ES modules, importmaps,
``fetch`` and MIME types behave exactly like any ordinary web page. The 2D map
is untouched — it loads Leaflet via classic ``<script>`` tags over ``file://``
and was never affected.

The server binds to ``127.0.0.1`` on an ephemeral port, serves the bundled
``html/`` tree read-only, plus a ``/__localfile`` route for a single imported
Gaussian-splat ``.ply`` (which lives outside ``html/``). It runs in a daemon
thread for the app's lifetime and starts lazily on first use.

Public API (used by ``src/map3d_widget.py``):
    builtin_viewer_url()  -> "http://127.0.0.1:<port>/scene3d.html"
    local_file_url(path)  -> "http://127.0.0.1:<port>/__localfile?path=..."
"""

from __future__ import annotations

import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from src.resources import resource_path

_server: "ThreadingHTTPServer | None" = None
_base_url: "str | None" = None
_lock = threading.Lock()


def _log(msg: str) -> None:
    """Append a 3D-viewer diagnostic line to ~/site-and-pattern-debug.log (opened and
    closed per call, so it survives even while the app is still running). This
    file is the durable trace we use to diagnose why the viewer won't start on a
    user's box.

    The same line is echoed to stderr only when ``PERMADESIGN_DEBUG`` is set, so
    a normal ``python main.py`` run keeps a clean terminal — every 3D-view open
    otherwise prints a dozen benign 200/checkpoint lines. Set the env var (e.g.
    ``PERMADESIGN_DEBUG=1``) to get the live terminal trace back."""
    import sys
    import time
    line = f"[web_assets {time.strftime('%H:%M:%S')}] {msg}"
    try:
        with open(os.path.join(os.path.expanduser("~"),
                               "site-and-pattern-debug.log"), "a",
                  encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    if os.environ.get("PERMADESIGN_DEBUG"):
        try:
            print(line, file=sys.stderr, flush=True)
        except Exception:
            pass

# Explicit JS MIME for module scripts — Chromium refuses to execute a
# `<script type="module">` whose response isn't a JavaScript MIME type.
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".wasm": "application/wasm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ply": "application/octet-stream",
}


def _mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return (_MIME.get(ext)
            or mimetypes.guess_type(path)[0]
            or "application/octet-stream")


def _html_root() -> str:
    return os.path.realpath(resource_path("html"))


class _Handler(BaseHTTPRequestHandler):
    # Silence the default per-request stderr logging.
    def log_message(self, *args):  # noqa: D401
        pass

    def do_GET(self):  # noqa: N802 (http.server API)
        parsed = urlparse(self.path)

        # Chromium auto-requests /favicon.ico for any loaded page; the embedded
        # viewer has no tab and ships no icon, so answer a quiet 204 instead of
        # letting it fall through to a (harmless but noisy) logged 404.
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # Diagnostic checkpoint endpoint: the viewer page pings this so we can
        # see how far its script got (independent of the JS console, which on
        # some boxes never reaches Python). Returns 204.
        if parsed.path == "/__log":
            qs = parse_qs(parsed.query)
            _log("page: " + (qs.get("m") or [""])[0])
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if parsed.path == "/__localfile":
            qs = parse_qs(parsed.query)
            raw = (qs.get("path") or [""])[0]
            target = os.path.normpath(raw) if raw else None
            # Only ever hand out the imported splat point cloud, never an
            # arbitrary file, even though we're bound to loopback.
            if (target and target.lower().endswith(".ply")
                    and os.path.isfile(target)):
                self._serve(target)
            else:
                _log(f"404 {parsed.path}")
                self.send_error(404)
            return

        root = _html_root()
        target = os.path.realpath(os.path.join(root, parsed.path.lstrip("/")))
        # Containment: never serve anything outside the bundled html/ tree.
        if target == root or target.startswith(root + os.sep):
            self._serve(target, parsed.path)
        else:
            _log(f"404 (outside root) {parsed.path}")
            self.send_error(404)

    def _serve(self, target: str, url_path: str = ""):
        if not target or not os.path.isfile(target):
            _log(f"404 (missing) {url_path or target}")
            self.send_error(404)
            return
        try:
            with open(target, "rb") as fh:
                data = fh.read()
        except OSError:
            _log(f"500 (read failed) {url_path or target}")
            self.send_error(404)
            return
        mime = _mime_for(target)
        _log(f"200 {url_path or os.path.basename(target)}  [{mime}]  {len(data)}B")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError as e:
            _log(f"write failed for {url_path}: {e}")


def _ensure_server() -> str:
    """Start the loopback server once (idempotent) and return its base URL."""
    global _server, _base_url
    with _lock:
        if _server is not None:
            return _base_url  # type: ignore[return-value]
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        srv.daemon_threads = True
        port = srv.server_address[1]
        threading.Thread(
            target=srv.serve_forever, name="web-assets-server", daemon=True
        ).start()
        _server = srv
        _base_url = f"http://127.0.0.1:{port}"
        _log(f"server started at {_base_url}  (html root: {_html_root()})")
        return _base_url


def builtin_viewer_url() -> str:
    """URL for the built-in three.js viewer (starts the server on first call)."""
    return _ensure_server() + "/scene3d.html"


def local_file_url(path: str) -> str:
    """Same-origin URL for a local splat ``.ply`` so the viewer can fetch it."""
    return _ensure_server() + "/__localfile?path=" + quote(os.path.abspath(path))
