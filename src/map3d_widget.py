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
        dist = dist_index_path()
        builtin = builtin_viewer_path()
        self.has_scene = bool(dist)
        self.mode = "fork" if dist else "builtin"
        self._pending_js: list[str] = []
        self._loaded = False
        self.loadFinished.connect(self._on_load_finished)
        page_path = dist or builtin
        if page_path:
            self.load(QUrl.fromLocalFile(page_path))
        else:   # neither shipped (broken bundle) — don't crash the window
            self.setHtml("<html><body style='background:#16201a;color:#90a4ae;"
                         "font-family:sans-serif'><p style='padding:2em'>"
                         "3D viewer assets missing (html/scene3d.html)."
                         "</p></body></html>")

    def _on_load_finished(self, ok: bool):
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
        """Push a full Scene JSON (``src.scene_contract.build_scene``)."""
        self.run_js(map3d_js.set_scene(scene))

    def set_sun_for(self, lat: float, lng: float, when: datetime):
        """Point the 3D sun for a place/time (reuses ``src/solar`` via map3d_js)."""
        self.run_js(map3d_js.set_sun_for(lat, lng, when))

    def set_scene(self, placed_plants, year: int, get_plant=None):
        """Push per-plant 3D state for ``placed_plants`` at ``year`` to the scene,
        using the shared ``src/scene3d`` state so it matches the 2D timeline."""
        from src.scene3d import placed_plants_3d_state
        records = placed_plants_3d_state(placed_plants, year, get_plant=get_plant)
        self.run_js(map3d_js.set_plants(records))
