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

    # A plant marker was right-click removed
    plant_removed = pyqtSignal(str, int, float, float)         # markerId, plantId, lat, lng

    # Annotation requests
    annotate_requested = pyqtSignal(float, float)              # lat, lng
    annotation_removed = pyqtSignal(str)                       # annotation id

    # Structure signals
    structure_placed = pyqtSignal(str, str, float, float, float)  # structId, name, lat, lng, sizeM
    structure_removed = pyqtSignal(str, str, float, float)        # markerId, structId, lat, lng

    # Hedgerow signals
    hedgerow_complete = pyqtSignal(str, str, str, str, float, int)  # id, pointsJson, species, style, lengthM, numPlants
    hedgerow_removed = pyqtSignal(str, str)                         # id, pointsJson

    # Shape signals
    shape_complete = pyqtSignal(str, str, str, str, str, str, float, str, float)
        # id, pointsJson, label, shapeType, fillColor, strokeColor, fillOpacity, dashArray, areaM2
    shape_removed = pyqtSignal(str)                                 # id

    # Guild removal signal
    guild_removed = pyqtSignal(str, float, float)                   # guildName, centerLat, centerLng

    # Contour signals
    contour_complete = pyqtSignal(str, float, str)                  # pointsJson, elevation, color
    contour_removed = pyqtSignal(str, float, str)                   # pointsJson, elevation, color

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

    @pyqtSlot(str, int, float, float)
    def onPlantRemoved(self, marker_id: str, plant_id: int, lat: float, lng: float):
        self.plant_removed.emit(marker_id, plant_id, lat, lng)

    @pyqtSlot(float, float)
    def onAnnotateRequested(self, lat: float, lng: float):
        self.annotate_requested.emit(lat, lng)

    @pyqtSlot(str)
    def onAnnotationRemoved(self, annotation_id: str):
        self.annotation_removed.emit(annotation_id)

    # ── Structure slots ───────────────────────────────────────────────────────

    @pyqtSlot(str, str, float, float, float)
    def onStructurePlaced(self, struct_id: str, name: str, lat: float, lng: float, size_m: float):
        self.structure_placed.emit(struct_id, name, lat, lng, size_m)

    @pyqtSlot(str, str, float, float)
    def onStructureRemoved(self, marker_id: str, struct_id: str, lat: float, lng: float):
        self.structure_removed.emit(marker_id, struct_id, lat, lng)

    # ── Hedgerow slots ────────────────────────────────────────────────────────

    @pyqtSlot(str, str, str, str, float, int)
    def onHedgerowComplete(self, hedge_id: str, points_json: str, species: str,
                           style: str, length_m: float, num_plants: int):
        self.hedgerow_complete.emit(hedge_id, points_json, species, style, length_m, num_plants)

    @pyqtSlot(str, str)
    def onHedgerowRemoved(self, hedge_id: str, points_json: str):
        self.hedgerow_removed.emit(hedge_id, points_json)

    # ── Shape slots ───────────────────────────────────────────────────────────

    @pyqtSlot(str, str, str, str, str, str, float, str, float)
    def onShapeComplete(self, shape_id: str, points_json: str, label: str,
                        shape_type: str, fill_color: str, stroke_color: str,
                        fill_opacity: float, dash_array: str, area_m2: float):
        self.shape_complete.emit(shape_id, points_json, label, shape_type,
                                 fill_color, stroke_color, fill_opacity, dash_array, area_m2)

    @pyqtSlot(str)
    def onShapeRemoved(self, shape_id: str):
        self.shape_removed.emit(shape_id)

    # ── Contour slots ─────────────────────────────────────────────────────────

    @pyqtSlot(str, float, str)
    def onContourComplete(self, points_json: str, elevation: float, color: str):
        self.contour_complete.emit(points_json, elevation, color)

    # ── Guild slots ───────────────────────────────────────────────────────────

    @pyqtSlot(str, float, float)
    def onGuildRemoved(self, guild_name: str, center_lat: float, center_lng: float):
        self.guild_removed.emit(guild_name, center_lat, center_lng)

    # ── Contour removal slot ──────────────────────────────────────────────────

    @pyqtSlot(str, float, str)
    def onContourRemoved(self, points_json: str, elevation: float, color: str):
        self.contour_removed.emit(points_json, elevation, color)


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
                 spacing_m: float = 1.0, plant_type: str = "herb",
                 quantity: int = 1, custom_color: str = ""):
        """Switch the map interaction mode ('none'|'boundary'|'plant'|'zone')."""
        if mode == 'plant' and plant_id:
            color_js = f", custom_color: '{custom_color}'" if custom_color else ""
            js = (
                f"setMode('plant', {{id: {plant_id}, "
                f"common_name: {repr(common_name)}, "
                f"spacing_m: {spacing_m}, "
                f"plant_type: {repr(plant_type)}, "
                f"quantity: {quantity}"
                f"{color_js}}});"
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
                          spacing_m: float = 1.0, plant_type: str = "herb",
                          custom_color: str = ""):
        color_arg = f", '{custom_color}'" if custom_color else ", null"
        self.run_js(
            f"loadPlantMarker({plant_id}, {repr(common_name)}, {lat}, {lng}, "
            f"{spacing_m}, {repr(plant_type)}{color_arg});"
        )

    def load_zone_center(self, lat: float, lng: float):
        self.run_js(f"loadZoneCenter({lat}, {lng});")

    def set_view(self, lat: float, lng: float, zoom: int = 14):
        self.run_js(f"setView({lat}, {lng}, {zoom});")

    def set_labels_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setLabelsVisible({v});")

    def update_marker_color(self, plant_id: int, color: str):
        self.run_js(f"updateMarkerColor({plant_id}, '{color}');")

    def place_annotation(self, ann_id: str, lat: float, lng: float, text: str):
        self.run_js(
            f"placeAnnotation({repr(ann_id)}, {lat}, {lng}, {repr(text)});"
        )

    def set_canopy_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setCanopyVisible({v});")

    def set_snap_enabled(self, enabled: bool, grid_size: float = 1.0):
        e = 'true' if enabled else 'false'
        self.run_js(f"setSnapEnabled({e}, {grid_size});")

    # ── Structure helpers ─────────────────────────────────────────────────────

    def set_structure_mode(self, struct_def: dict):
        """Enter structure placement mode with a structure definition."""
        import json
        self.run_js(f"setMode('structure', JSON.parse({json.dumps(json.dumps(struct_def))}));")

    def load_structure(self, struct_def: dict, lat: float, lng: float):
        """Load a structure from a saved project."""
        import json
        self.run_js(f"loadStructure(JSON.parse({json.dumps(json.dumps(struct_def))}), {lat}, {lng});")

    # ── Hedgerow helpers ──────────────────────────────────────────────────────

    def set_hedgerow_mode(self, hedge_config: dict):
        """Enter hedgerow drawing mode."""
        import json
        self.run_js(f"setMode('hedgerow', JSON.parse({json.dumps(json.dumps(hedge_config))}));")

    def load_hedgerow(self, hedge_def: dict):
        """Load a hedgerow from a saved project."""
        import json
        self.run_js(f"loadHedgerow(JSON.parse({json.dumps(json.dumps(hedge_def))}));")

    # ── Shape helpers ─────────────────────────────────────────────────────────

    def set_shape_mode(self, shape_config: dict):
        """Enter custom shape drawing mode."""
        import json
        self.run_js(f"setMode('shape', JSON.parse({json.dumps(json.dumps(shape_config))}));")

    def load_shape(self, shape_def: dict):
        """Load a custom shape from a saved project."""
        import json
        self.run_js(f"loadShape(JSON.parse({json.dumps(json.dumps(shape_def))}));")

    def set_structures_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(
            f"Object.values(structureMarkers).forEach(function(g) {{"
            f"  if ({v}) g.addTo(map); else map.removeLayer(g);"
            f"}});"
            f"Object.values(hedgerowLayers).forEach(function(g) {{"
            f"  if ({v}) g.addTo(map); else map.removeLayer(g);"
            f"}});"
            f"Object.values(shapeLayers).forEach(function(g) {{"
            f"  if ({v}) g.addTo(map); else map.removeLayer(g);"
            f"}});"
        )

    # ── Analysis overlay helpers (A1-A4) ──────────────────────────────────────

    def draw_sun_path(self, data: dict):
        """Draw the sun path arc and shadow arrows on the map."""
        import json
        self.run_js(f"drawSunPath(JSON.parse({json.dumps(json.dumps(data))}));")

    def clear_sun_path(self):
        self.run_js("clearSunPath();")

    def draw_sectors(self, data: dict):
        """Draw sector analysis wedges on the map."""
        import json
        self.run_js(f"drawSectors(JSON.parse({json.dumps(json.dumps(data))}));")

    def clear_sectors(self):
        self.run_js("clearSectors();")

    def set_contour_mode(self, config: dict):
        """Enter contour drawing mode."""
        import json
        self.run_js(f"setMode('contour', JSON.parse({json.dumps(json.dumps(config))}));")

    def clear_contours(self):
        self.run_js("clearContours();")

    def draw_wind_overlay(self, data: dict):
        """Draw wind direction arrows and shelter zones."""
        import json
        self.run_js(f"drawWindOverlay(JSON.parse({json.dumps(json.dumps(data))}));")

    def clear_wind_overlay(self):
        self.run_js("clearWindOverlay();")
