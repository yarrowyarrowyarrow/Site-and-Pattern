"""
src/web_assets.py — an internal ``app://`` URL scheme that serves the bundled
web assets from a real, secure origin (V1.77).

The built-in 3D viewer (``html/scene3d.html``) is an ES-module app: it imports
three.js + Spark via ``<script type="module">`` + an importmap. Loaded over a
``file://`` URL (as it was through V1.76) those module imports are at the mercy
of the bundled Chromium's ``file://`` module rules — which a newer Chromium
(pulled by the first CI-built Windows installer in V1.76) tightened, breaking
the viewer with a misleading "needs the network once" notice even when online.

Serving the page and its vendored modules from a registered custom scheme gives
them a normal **same-origin secure context**, so module loading no longer
depends on ``file://`` quirks, CDNs, or the Chromium version. The 2D map keeps
using ``file://`` — it loads Leaflet with classic ``<script src>`` tags, which
were never affected.

Two routes under one scheme:

* ``app://assets/<path>``      → ``<repo>/html/<path>`` (bundled viewer + vendor)
* ``app://localfile/<abspath>``→ an arbitrary local file (the Gaussian-splat
  ``.ply`` the user imported), so Spark fetches it same-origin instead of
  cross-scheme from ``file://``.

Usage (see ``main.py``)::

    register_scheme()          # MUST run before the QApplication is created
    app = QApplication(...)
    install_handler()          # installs on the default profile

``src/map3d_widget.py`` then loads :func:`builtin_viewer_url` and turns splat
paths into :func:`local_file_url`.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QBuffer, QIODevice, QUrl
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineUrlRequestJob,
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
)

from src.resources import resource_path

SCHEME = b"app"
_ASSETS_HOST = "assets"
_LOCALFILE_HOST = "localfile"

# Keep a module-level reference so the installed handler isn't garbage-collected
# while the profile still routes requests to it.
_handler: "_AppSchemeHandler | None" = None

_MIME = {
    ".html": b"text/html",
    ".htm": b"text/html",
    ".js": b"text/javascript",
    ".mjs": b"text/javascript",
    ".css": b"text/css",
    ".json": b"application/json",
    ".wasm": b"application/wasm",
    ".png": b"image/png",
    ".jpg": b"image/jpeg",
    ".jpeg": b"image/jpeg",
    ".gif": b"image/gif",
    ".svg": b"image/svg+xml",
    ".ply": b"application/octet-stream",
}


def _mime_for(path: str) -> bytes:
    return _MIME.get(os.path.splitext(path)[1].lower(), b"application/octet-stream")


def register_scheme() -> None:
    """Register the ``app`` scheme. Must be called *before* the ``QApplication``
    is constructed (a hard Qt requirement) and is a no-op if already registered."""
    if QWebEngineUrlScheme.schemeByName(SCHEME).name():
        return  # already registered (e.g. a second window/profile)
    scheme = QWebEngineUrlScheme(SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme        # secure context for modules
        | QWebEngineUrlScheme.Flag.LocalScheme       # local app content
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.CorsEnabled       # allow fetch/XHR/module loads
    )
    QWebEngineUrlScheme.registerScheme(scheme)


def install_handler(profile: "QWebEngineProfile | None" = None) -> None:
    """Install the asset handler on ``profile`` (the default profile if omitted).
    Call once, after the ``QApplication`` exists."""
    global _handler
    if profile is None:
        profile = QWebEngineProfile.defaultProfile()
    if _handler is None:
        _handler = _AppSchemeHandler()
    profile.installUrlSchemeHandler(SCHEME, _handler)


def builtin_viewer_url() -> str:
    """URL for the built-in three.js viewer served from the ``app`` scheme."""
    return f"app://{_ASSETS_HOST}/scene3d.html"


def local_file_url(path: str) -> str:
    """``app://localfile`` URL for a local file (the imported splat ``.ply``), so
    the viewer fetches it same-origin instead of cross-scheme from ``file://``."""
    # QUrl.fromLocalFile gives a leading-'/' , forward-slashed path on every OS
    # ("/home/u/x.ply" or "/C:/Users/u/x.ply"); reuse it under our scheme/host.
    local = QUrl.fromLocalFile(os.path.abspath(path))
    out = QUrl()
    out.setScheme("app")
    out.setHost(_LOCALFILE_HOST)
    out.setPath(local.path())
    return out.toString()


class _AppSchemeHandler(QWebEngineUrlSchemeHandler):
    """Serves bundled assets (``app://assets/``) and whitelisted local files
    (``app://localfile/``) as in-memory replies."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Resolve the html/ root the same frozen-aware way as everything else.
        self._html_root = os.path.realpath(resource_path("html"))

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:  # noqa: N802 (Qt)
        url = job.requestUrl()
        host = url.host()
        if host == _ASSETS_HOST:
            target = self._resolve_asset(url.path())
        elif host == _LOCALFILE_HOST:
            target = self._resolve_localfile(url.path())
        else:
            target = None

        if not target or not os.path.isfile(target):
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        try:
            with open(target, "rb") as fh:
                data = fh.read()
        except OSError:
            job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
            return

        buf = QBuffer(job)            # parented to the job so it outlives the read
        buf.setData(data)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(_mime_for(target), buf)

    def _resolve_asset(self, path: str) -> "str | None":
        rel = path.lstrip("/")
        target = os.path.realpath(os.path.join(self._html_root, rel))
        # Containment check: never serve anything outside html/ (no ../ escape).
        if target == self._html_root or target.startswith(self._html_root + os.sep):
            return target
        return None

    def _resolve_localfile(self, path: str) -> "str | None":
        # QUrl path is "/abs/..." on POSIX and "/C:/abs/..." on Windows.
        local = path.lstrip("/") if sys.platform.startswith("win") else path
        return os.path.normpath(local)
