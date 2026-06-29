"""
src/map3d_widget.py — Map3DWidget, the embedded 3D viewport.

A ``QWebEngineView`` that mirrors ``src/map_widget.MapWidget`` for 3D. Two
page sources, picked at construction:

  * the built map3d fork from ``web3d/dist/`` when present (buildings +
    roads context — see ``web3d/README.md``), or
  * the built-in viewer ``html/scene3d.html`` (V1.62) — a self-contained
    three.js scene that renders the *design itself*: terrain, extruded
    buildings/footprints, instanced plant archetypes on the growth
    timeline, boundary, structures, and a sun-driven shadow light.

Both register the same guarded hooks (``window.permaSetSun``,
``window.permaSetPlants``, and — built-in viewer — ``window.permaSetScene``),
driven from Python via ``src/map3d_js`` builders. The widget re-pushes the
last scene on ``loadFinished`` so a push that raced the page load is never
lost (the ``&&`` guards silently drop early calls).
"""

from __future__ import annotations

import os
from datetime import datetime

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

from src import map3d_js


def _repo_path(*parts) -> str:
    try:
        from src.resources import resource_path
        return resource_path(*parts)
    except Exception:
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            *parts)


def dist_index_path() -> str | None:
    """Path to the built map3d ``index.html`` if it exists, else ``None``."""
    p = _repo_path("web3d", "dist", "index.html")
    return p if p and os.path.exists(p) else None


def builtin_viewer_path() -> str | None:
    """Path to the built-in three.js viewer (``html/scene3d.html``)."""
    p = _repo_path("html", "scene3d.html")
    return p if p and os.path.exists(p) else None


class Map3DWidget(QWebEngineView):
    """Embedded 3D viewport — the map3d fork build when present, else the
    built-in scene3d viewer. Sun/scene are driven via ``map3d_js``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Route the viewer's JS console like the 2D map does (src/map_widget):
        # genuine errors go to stderr, but info/warnings go to the debug log
        # only — so benign three.js / ANGLE shader warnings (e.g. Windows'
        # "warning X3203: signed/unsigned mismatch, unsigned assumed") don't
        # clutter the terminal. Set before load() so early messages are caught.
        from src.map_widget import _LoggingPage
        self.setPage(_LoggingPage(self))
        dist = dist_index_path()
        builtin = builtin_viewer_path()
        self.has_scene = bool(dist)
        self.mode = "fork" if dist else "builtin"
        self._pending_js: list[str] = []
        self._loaded = False
        self.loadFinished.connect(self._on_load_finished)

        # The built-in viewer fetches three.js + Spark from a CDN and, for the
        # Gaussian-splat backdrop, loads a local .ply via a file:// URL — both
        # need these relaxations on the file:// page (mirrors MapWidget).
        s = self.settings()
        s.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        from src.web_assets import _log as _wlog
        _wlog(f"Map3DWidget: dist={dist!r} builtin={builtin!r} mode={self.mode}")
        if dist:
            # The map3d fork build (web3d/dist) is a separate, self-contained app
            # with relative assets — keep loading it from file:// as before.
            _wlog(f"loading fork dist via file://: {dist}")
            self.load(QUrl.fromLocalFile(dist))
        elif builtin:
            # The built-in viewer is an ES-module app; serve it (and its vendored
            # three.js + Spark) over a localhost http:// origin so module loading
            # behaves like a normal web page — not subject to file:// origin
            # rules or the bundled Chromium version (see src/web_assets.py).
            from src.web_assets import builtin_viewer_url
            url = builtin_viewer_url()
            _wlog(f"loading built-in viewer via {url}")
            self.load(QUrl(url))
        else:   # neither shipped (broken bundle) — don't crash the window
            self.setHtml("<html><body style='background:#16201a;color:#90a4ae;"
                         "font-family:sans-serif'><p style='padding:2em'>"
                         "3D viewer assets missing (html/scene3d.html)."
                         "</p></body></html>")

    def _on_load_finished(self, ok: bool):
        try:
            from src.web_assets import _log as _wlog
            _wlog(f"loadFinished(ok={ok}) url={self.url().toString()}")
        except Exception:
            pass
        self._loaded = True
        for js in self._pending_js:
            self.page().runJavaScript(js)
        self._pending_js = []

    def run_js(self, js: str):
        if not js:
            return
        if not self._loaded:
            # The page hasn't registered its hooks yet; the && guards would
            # silently drop this call. Queue and replay on loadFinished.
            self._pending_js.append(js)
            return
        self.page().runJavaScript(js)

    def apply_scene(self, scene: dict):
        """Push a full Scene JSON (``src.scene_contract.build_scene``).

        A ``scene["splat"]`` field carries a local file ``path`` for the
        Gaussian-splat backdrop; turn it into a ``file://`` ``url`` Spark can
        fetch (and drop it when the file is gone, so the design still renders).
        """
        splat = scene.get("splat")
        if splat:
            path = splat.get("path")
            if path and os.path.exists(path):
                splat = dict(splat)
                # Serve the .ply from the same localhost origin as the viewer so
                # Spark fetches it same-origin (a file:// URL would be a
                # cross-origin fetch the http:// page would refuse).
                from src.web_assets import local_file_url
                splat["url"] = local_file_url(path)
                scene = dict(scene, splat=splat)
            else:
                scene = dict(scene, splat=None)
        self.run_js(map3d_js.set_scene(scene))

    def capture_ortho(self, rect: dict, callback, *, width: int = 2048):
        """Bake a top-down PNG of the loaded splat backdrop (for the 2D map's
        "yard photo" layer) and hand the data URL to ``callback``. ``rect`` is
        the scene-metre frame ``{min_x, max_x, min_y, max_y}``. The splat must
        already be loaded (call after the 3D view is open); a missing/loading
        splat yields ``''``/``False`` to the callback."""
        if not self._loaded:
            callback("")
            return
        self.page().runJavaScript(map3d_js.capture_ortho(rect, width), callback)

    def set_quality(self, level: int):
        """Set the viewer's geometry detail (0 Low · 1 Medium · 2 High)."""
        self.run_js(map3d_js.set_quality(level))

    def set_sun_for(self, lat: float, lng: float, when: datetime):
        """Point the 3D sun for a place/time (reuses ``src/solar`` via map3d_js)."""
        self.run_js(map3d_js.set_sun_for(lat, lng, when))

    def set_scene(self, placed_plants, year: int, get_plant=None):
        """Push per-plant 3D state for ``placed_plants`` at ``year`` to the scene,
        using the shared ``src/scene3d`` state so it matches the 2D timeline."""
        from src.scene3d import placed_plants_3d_state
        records = placed_plants_3d_state(placed_plants, year, get_plant=get_plant)
        self.run_js(map3d_js.set_plants(records))
