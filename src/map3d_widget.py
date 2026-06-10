"""
src/map3d_widget.py — Map3DWidget scaffold (D1 foundation).

A ``QWebEngineView`` that mirrors ``src/map_widget.MapWidget`` for a 3D viewport.
It loads the built map3d fork from ``web3d/dist/`` when that build is present (see
``web3d/README.md``); until then it shows a small placeholder so the widget can be
constructed without crashing. Sun and per-plant growth state are pushed through
``src/map3d_js`` (guarded ``window.permaSetSun`` / ``window.permaSetPlants`` hooks)
and the shared ``src/scene3d`` state — so this wiring is ready the moment the fork
is built and its hooks register. The widget is intentionally NOT mounted in the
main window yet (no built scene to show); mounting is the next D1 step.
"""

from __future__ import annotations

import os
from datetime import datetime

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

from src import map3d_js


_PLACEHOLDER_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#16201a;color:#90a4ae;
font-family:sans-serif;display:flex;align-items:center;justify-content:center;
text-align:center}div{max-width:340px;padding:20px;line-height:1.5}
b{color:#a5d6a7}code{color:#80cbc4}</style></head><body><div>
<b>3D view</b><br>Build the map3d fork to enable it — apply
<code>web3d/map3d-sun-shadows.patch</code> and copy its <code>dist/</code> in
(see <code>web3d/README.md</code>). Sun &amp; growth are already wired.
</div></body></html>"""


def dist_index_path() -> str | None:
    """Path to the built map3d ``index.html`` if it exists, else ``None``."""
    try:
        from src.resources import resource_path
        p = resource_path("web3d", "dist", "index.html")
    except Exception:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "web3d", "dist", "index.html")
    return p if p and os.path.exists(p) else None


class Map3DWidget(QWebEngineView):
    """Embedded 3D viewport — loads the built map3d fork when present, else a
    placeholder. Sun/scene are driven via ``map3d_js`` + ``scene3d``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        dist = dist_index_path()
        self.has_scene = bool(dist)
        if dist:
            self.load(QUrl.fromLocalFile(dist))
        else:
            self.setHtml(_PLACEHOLDER_HTML)

    def run_js(self, js: str):
        if js:
            self.page().runJavaScript(js)

    def set_sun_for(self, lat: float, lng: float, when: datetime):
        """Point the 3D sun for a place/time (reuses ``src/solar`` via map3d_js)."""
        self.run_js(map3d_js.set_sun_for(lat, lng, when))

    def set_scene(self, placed_plants, year: int, get_plant=None):
        """Push per-plant 3D state for ``placed_plants`` at ``year`` to the scene,
        using the shared ``src/scene3d`` state so it matches the 2D timeline."""
        from src.scene3d import placed_plants_3d_state
        records = placed_plants_3d_state(placed_plants, year, get_plant=get_plant)
        self.run_js(map3d_js.set_plants(records))
