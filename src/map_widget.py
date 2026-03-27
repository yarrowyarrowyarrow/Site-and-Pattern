"""
map_widget.py — QtWebEngine wrapper around the Leaflet map.

Exposes a MapBridge QObject whose slots are callable from JavaScript via
QWebChannel. Python code calls self.map_widget.run_js(...) to invoke JS
functions defined in map.html.
"""

import os
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel


class MapBridge(QObject):
    """
    Python ↔ JS bridge. Slots are callable from JS; signals notify Python
    listeners (primarily MainWindow / AppWindow).
    """

    # Emitted when the JS map finishes initialising
    map_ready = pyqtSignal()

    # Mouse move → current lat/lng for the status bar
    mouse_moved = pyqtSignal(float, float)        # lat, lng

    # User clicked on the map (generic)
    map_clicked = pyqtSignal(float, float)         # lat, lng

    # A property boundary polygon was completed
    boundary_complete = pyqtSignal(list)           # list of [lat, lng] pairs

    # A plant was placed on the map
    plant_placed = pyqtSignal(int, str, float, float)  # id, name, lat, lng

    # The zone-centre point was placed
    zone_center_placed = pyqtSignal(float, float)  # lat, lng

    # A plant marker was clicked
    plant_marker_clicked = pyqtSignal(str, int, float, float)  # markerId, plantId, lat, lng

    # ── Slots (called from JS) ────────────────────────────────────────────────

    @pyqtSlot()
    def onMapReady(self):
        self.map_ready.emit()

    @pyqtSlot(float, float)
    def onMouseMove(self, lat: float, lng: float):
        self.mouse_moved.emit(lat, lng)

    @pyqtSlot(float, float)
    def onMapClick(self, lat: float, lng: float):
        self.map_clicked.emit(lat, lng)

    @pyqtSlot(str)
    def onBoundaryComplete(self, coords_json: str):
        import json
        try:
            coords = json.loads(coords_json)
            self.boundary_complete.emit(coords)
        except Exception:
            pass

    @pyqtSlot(int, str, float, float)
    def onPlantPlaced(self, plant_id: int, common_name: str, lat: float, lng: float):
        self.plant_placed.emit(plant_id, common_name, lat, lng)

    @pyqtSlot(float, float)
    def onZoneCenterPlaced(self, lat: float, lng: float):
        self.zone_center_placed.emit(lat, lng)

    @pyqtSlot(str, int, float, float)
    def onPlantMarkerClick(self, marker_id: str, plant_id: int, lat: float, lng: float):
        self.plant_marker_clicked.emit(marker_id, plant_id, lat, lng)


class MapWidget(QWebEngineView):
    """
    QWebEngineView subclass that hosts the Leaflet map defined in
    html/map.html.  Provides helper methods for every JS function so that
    callers never have to format JS strings themselves.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bridge = MapBridge()
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self._channel)

        # Allow the local HTML file to load remote tile/CDN URLs (needed on Windows)
        s = self.page().settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)

        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "html", "map.html"
        )
        self.load(QUrl.fromLocalFile(html_path))

    # ── JS helpers ────────────────────────────────────────────────────────────

    def run_js(self, js: str):
        self.page().runJavaScript(js)

    def set_mode(self, mode: str, plant_id: int = 0, common_name: str = "",
                 spacing_m: float = 1.0, plant_type: str = "herb"):
        """Switch the map interaction mode ('none'|'boundary'|'plant'|'zone')."""
        if mode == 'plant' and plant_id:
            js = (
                f"setMode('plant', {{id: {plant_id}, "
                f"common_name: {repr(common_name)}, "
                f"spacing_m: {spacing_m}, "
                f"plant_type: {repr(plant_type)}}});"
            )
        else:
            js = f"setMode({repr(mode)});"
        self.run_js(js)

    def cancel_draw(self):
        self.run_js("cancelDraw();")

    def clear_all(self):
        self.run_js("clearAll();")

    def set_satellite_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setSatelliteVisible({v});")

    def set_boundary_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setBoundaryVisible({v});")

    def set_zones_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setZonesVisible({v});")

    def set_plants_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setPlantsVisible({v});")

    def load_boundary(self, coords: list):
        import json
        self.run_js(f"loadBoundary({json.dumps(json.dumps(coords))});")

    def load_plant_marker(self, plant_id: int, common_name: str, lat: float, lng: float,
                          spacing_m: float = 1.0, plant_type: str = "herb"):
        self.run_js(
            f"loadPlantMarker({plant_id}, {repr(common_name)}, {lat}, {lng}, "
            f"{spacing_m}, {repr(plant_type)});"
        )

    def load_zone_center(self, lat: float, lng: float):
        self.run_js(f"loadZoneCenter({lat}, {lng});")

    def set_view(self, lat: float, lng: float, zoom: int = 14):
        self.run_js(f"setView({lat}, {lng}, {zoom});")
