"""
map_widget.py — QtWebEngine wrapper around the Leaflet map.

Exposes a MapBridge QObject whose slots are callable from JavaScript via
QWebChannel. Python code calls self.map_widget.run_js(...) to invoke JS
functions defined in map.html.
"""

import os
import sys
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
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

    # Map view changed (pan / zoom / programmatic setView). Carries the
    # current view centre + zoom so consumers — most notably the address
    # finder — can bias their queries against where the user is looking.
    map_moved = pyqtSignal(float, float, int)      # lat, lng, zoom

    # A property boundary polygon was completed (id, points list, color name)
    boundary_complete = pyqtSignal(str, list, str)

    # Boundary geometry changed via vertex/move/scale drag (id, new points)
    boundary_geom_changed = pyqtSignal(str, list)

    # Boundary color or label toggles changed (id, color, showLengths, showArea)
    boundary_props_changed = pyqtSignal(str, str, bool, bool)

    # Boundary removed via context menu (id)
    boundary_removed = pyqtSignal(str)

    # A plant was placed on the map
    plant_placed = pyqtSignal(int, str, float, float)  # id, name, lat, lng

    # A plant marker was clicked
    plant_marker_clicked = pyqtSignal(str, int, float, float)  # markerId, plantId, lat, lng

    # A plant marker was right-click removed
    plant_removed = pyqtSignal(str, int, float, float)         # markerId, plantId, lat, lng

    # A single placed plant was dragged to a new location
    plant_moved = pyqtSignal(str, int, float, float, float, float)
    # ^ markerId, plantId, oldLat, oldLng, newLat, newLng

    # An entire placement group (polyculture etc.) was dragged
    plant_group_moved = pyqtSignal(str, str, str)
    # ^ groupId, originals_json, moved_json
    # both JSON strings are arrays of {markerId, plantId, lat, lng}.

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

    # Polyculture removal signal
    polyculture_removed = pyqtSignal(str, float, float)                   # polycultureName, centerLat, centerLng

    # Contour signals
    contour_complete = pyqtSignal(str, float, str)                  # pointsJson, elevation, color
    contour_removed = pyqtSignal(str, float, str)                   # pointsJson, elevation, color

    # Auto-terrain (slope contour generation) signals
    # Emitted when JS reports the bbox to compute over (viewport getter or
    # free-draw rectangle finished). bbox is {south, north, west, east}.
    terrain_bbox_ready = pyqtSignal(dict)
    terrain_bbox_cancelled = pyqtSignal()

    # Sun path signals
    sun_anchor_placed = pyqtSignal(float, float)   # lat, lng — user clicked anchor
    sun_path_removed  = pyqtSignal()
    anchor_cancelled  = pyqtSignal(str)            # mode that was cancelled

    # Sector signals
    sector_anchor_placed   = pyqtSignal(float, float)     # lat, lng
    sector_group_removed   = pyqtSignal(str)              # sid
    sector_group_moved     = pyqtSignal(str, float, float) # sid, lat, lng
    sector_group_rotated   = pyqtSignal(str, float)        # sid, rotationDeg
    sector_group_resized   = pyqtSignal(str, float)        # sid, radiusM

    # Site pin (search-bar pin drop / drag / right-click remove)
    site_pin_placed  = pyqtSignal(float, float, str)   # lat, lng, label
    site_pin_removed = pyqtSignal()

    # Pattern placement (Single-burst, Row, Grid, Circle).
    # positions_json is a JSON-encoded [[lat,lng], ...] list. pattern_kind
    # tags the gesture so Python can record provenance ('single' | 'burst' |
    # 'row' | 'grid' | 'circle').
    pattern_placed = pyqtSignal(int, str, float, str, str, str, str)
        # plant_id, common_name, spacing_m, plant_type, custom_color,
        # positions_json, pattern_kind

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

    @pyqtSlot(float, float, int)
    def onMapMoved(self, lat: float, lng: float, zoom: int):
        self.map_moved.emit(lat, lng, zoom)

    @pyqtSlot(float, float, str)
    def onSitePinPlaced(self, lat: float, lng: float, label: str):
        self.site_pin_placed.emit(lat, lng, label or "")

    @pyqtSlot()
    def onSitePinRemoved(self):
        self.site_pin_removed.emit()

    @pyqtSlot(str, str, str)
    def onBoundaryComplete(self, bid: str, coords_json: str, color: str):
        import json
        try:
            coords = json.loads(coords_json)
            self.boundary_complete.emit(bid, coords, color)
        except Exception:
            pass

    @pyqtSlot(str, str)
    def onBoundaryGeomChanged(self, bid: str, coords_json: str):
        import json
        try:
            coords = json.loads(coords_json)
            self.boundary_geom_changed.emit(bid, coords)
        except Exception:
            pass

    @pyqtSlot(str, str, bool, bool)
    def onBoundaryPropsChanged(self, bid: str, color: str, show_lengths: bool, show_area: bool):
        self.boundary_props_changed.emit(bid, color, show_lengths, show_area)

    @pyqtSlot(str)
    def onBoundaryRemoved(self, bid: str):
        self.boundary_removed.emit(bid)

    @pyqtSlot(float, float)
    def onSunAnchorPlaced(self, lat: float, lng: float):
        self.sun_anchor_placed.emit(lat, lng)

    @pyqtSlot()
    def onSunPathRemoved(self):
        self.sun_path_removed.emit()

    @pyqtSlot(str)
    def onAnchorCancelled(self, mode: str):
        self.anchor_cancelled.emit(mode)

    @pyqtSlot(float, float)
    def onSectorAnchorPlaced(self, lat: float, lng: float):
        self.sector_anchor_placed.emit(lat, lng)

    @pyqtSlot(str)
    def onSectorGroupRemoved(self, sid: str):
        self.sector_group_removed.emit(sid)

    @pyqtSlot(str, float, float)
    def onSectorGroupMoved(self, sid: str, lat: float, lng: float):
        self.sector_group_moved.emit(sid, lat, lng)

    @pyqtSlot(str, float)
    def onSectorGroupRotated(self, sid: str, rotation_deg: float):
        self.sector_group_rotated.emit(sid, rotation_deg)

    @pyqtSlot(str, float)
    def onSectorGroupResized(self, sid: str, radius_m: float):
        self.sector_group_resized.emit(sid, radius_m)

    @pyqtSlot(int, str, float, float)
    def onPlantPlaced(self, plant_id: int, common_name: str, lat: float, lng: float):
        self.plant_placed.emit(plant_id, common_name, lat, lng)

    @pyqtSlot(int, str, float, str, str, str, str)
    def onPatternPlaced(self, plant_id: int, common_name: str, spacing_m: float,
                        plant_type: str, custom_color: str,
                        positions_json: str, pattern_kind: str):
        self.pattern_placed.emit(
            plant_id, common_name, spacing_m, plant_type,
            custom_color, positions_json, pattern_kind,
        )

    @pyqtSlot(str, int, float, float)
    def onPlantMarkerClick(self, marker_id: str, plant_id: int, lat: float, lng: float):
        self.plant_marker_clicked.emit(marker_id, plant_id, lat, lng)

    @pyqtSlot(str, int, float, float)
    def onPlantRemoved(self, marker_id: str, plant_id: int, lat: float, lng: float):
        self.plant_removed.emit(marker_id, plant_id, lat, lng)

    @pyqtSlot(str, int, float, float, float, float)
    def onPlantMoved(self, marker_id: str, plant_id: int,
                     old_lat: float, old_lng: float,
                     new_lat: float, new_lng: float):
        self.plant_moved.emit(
            marker_id, plant_id, old_lat, old_lng, new_lat, new_lng
        )

    @pyqtSlot(str, str, str)
    def onPlantGroupMoved(self, group_id: str,
                          originals_json: str, moved_json: str):
        self.plant_group_moved.emit(group_id, originals_json, moved_json)

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

    # ── Polyculture slots ───────────────────────────────────────────────────────────

    @pyqtSlot(str, float, float)
    def onPolycultureRemoved(self, polyculture_name: str, center_lat: float, center_lng: float):
        self.polyculture_removed.emit(polyculture_name, center_lat, center_lng)

    # ── Contour removal slot ──────────────────────────────────────────────────

    @pyqtSlot(str, float, str)
    def onContourRemoved(self, points_json: str, elevation: float, color: str):
        self.contour_removed.emit(points_json, elevation, color)

    # ── Terrain bbox slots ────────────────────────────────────────────────────

    @pyqtSlot(float, float, float, float)
    def onTerrainBboxReady(self, south: float, north: float, west: float, east: float):
        self.terrain_bbox_ready.emit({
            "south": south, "north": north, "west": west, "east": east,
        })

    @pyqtSlot()
    def onTerrainBboxCancelled(self):
        self.terrain_bbox_cancelled.emit()


class _LoggingPage(QWebEnginePage):
    """QWebEnginePage that forwards every JS console.* + uncaught error to
    Python stderr. Without this, anything Leaflet/our JS prints or throws
    is silently swallowed inside the WebEngine sandbox — exactly the
    "no terminal errors are reported" symptom users hit when the map
    misbehaves."""

    _LEVEL = {
        QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel:    "info",
        QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "warn",
        QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:   "ERROR",
    }

    def javaScriptConsoleMessage(self, level, message, line, source_id):
        tag = self._LEVEL.get(level, str(level))
        src = (source_id or "").rsplit("/", 1)[-1] or "?"
        sys.stderr.write(f"[js:{tag}] {src}:{line}  {message}\n")
        sys.stderr.flush()


class MapWidget(QWebEngineView):
    """
    QWebEngineView subclass that hosts the Leaflet map defined in
    html/map.html.  Provides helper methods for every JS function so that
    callers never have to format JS strings themselves.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Install the logging page BEFORE wiring the QWebChannel so any
        # JS error / warning that fires during page load surfaces on
        # stderr instead of disappearing into the sandbox.
        self.setPage(_LoggingPage(self))
        # Catch render-subprocess crashes. When QtWebEngine's renderer
        # process dies (often during a canvas/GPU paint with bad input),
        # JS halts mid-tick — no errors, no heartbeat, map goes blank.
        # That's exactly the polyculture-placement symptom. Logging this
        # signal turns an invisible crash into a single stderr line we
        # can grep for.
        self.page().renderProcessTerminated.connect(self._on_render_terminated)
        self.bridge = MapBridge()
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self._channel)
        # Cache the most recent map view centre + zoom (updated on every
        # JS moveend). Consumers that need to bias work against "where
        # the user is looking" — currently the address finder — can read
        # last_center directly without going through an async readback.
        self._last_center: tuple[float, float] | None = None
        self._last_zoom:   int | None = None
        self.bridge.map_moved.connect(self._on_map_moved)

        # Allow the local HTML file to load remote tile/CDN URLs (needed on Windows)
        s = self.page().settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)

        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "html", "map.html"
        )
        self.load(QUrl.fromLocalFile(html_path))

    def _on_map_moved(self, lat: float, lng: float, zoom: int):
        self._last_center = (lat, lng)
        self._last_zoom = zoom

    def _on_render_terminated(self, status, exit_code):
        # status is QWebEnginePage.RenderProcessTerminationStatus; print
        # both raw and name so we can read it without consulting the docs.
        name = getattr(status, "name", str(status))
        sys.stderr.write(
            f"[webengine] *** RENDER PROCESS TERMINATED *** status={name} "
            f"exit_code={exit_code}\n"
        )
        sys.stderr.flush()

    @property
    def last_center(self) -> "tuple[float, float] | None":
        """Latest known (lat, lng) centre of the map view, or None
        if the map hasn't reported a moveend yet."""
        return self._last_center

    # ── JS helpers ────────────────────────────────────────────────────────────

    def run_js(self, js: str):
        self.page().runJavaScript(js)

    def set_mode(self, mode: str, plant_id: int = 0, common_name: str = "",
                 spacing_m: float = 1.0, plant_type: str = "herb",
                 quantity: int = 1, custom_color: str = "",
                 pattern: dict | None = None,
                 mature_canopy_m: float | None = None):
        """Switch the map interaction mode.

        For plant mode, `pattern` may be:
          {"kind": "single"}  (default — current click-to-place behaviour)
          {"kind": "row",    "params": {"count": int|None, "overlap": 0..1}}
          {"kind": "grid",   "params": {"rows": N|None, "cols": N|None,
                                         "overlap": 0..1, "stagger": bool}}
          {"kind": "circle", "params": {"count": N|None, "overlap": 0..1,
                                         "fill": bool}}
        """
        if mode == 'plant' and plant_id:
            import json as _json
            payload = {
                "id": plant_id,
                "common_name": common_name,
                "spacing_m": spacing_m,
                "plant_type": plant_type,
                "quantity": quantity,
                "custom_color": custom_color or "",
                "pattern": pattern or {"kind": "single"},
                # Mature canopy width — drawn as the outer ghost ring during
                # row/burst/grid preview. Falls back to spacing × 1.5 JS-side
                # when missing, mirroring the get_plant fallback.
                "mature_canopy_m": mature_canopy_m or (spacing_m * 1.5),
            }
            js = f"setMode('plant', JSON.parse({_json.dumps(_json.dumps(payload))}));"
        else:
            js = f"setMode({repr(mode)});"
        self.run_js(js)

    def cancel_draw(self):
        self.run_js("cancelDraw();")

    def clear_measure(self):
        self.run_js("clearMeasure();")

    def clear_all(self):
        self.run_js("clearAll();")

    def set_satellite_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setSatelliteVisible({v});")

    def set_boundary_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setBoundaryVisible({v});")

    def set_measurements_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setMeasureVisible({v});")

    def set_plants_visible(self, visible: bool):
        v = 'true' if visible else 'false'
        self.run_js(f"setPlantsVisible({v});")

    def load_boundary(self, boundary_data: dict):
        """Load a boundary from a saved project. boundary_data has id/points/color/showLengths/showArea."""
        import json
        self.run_js(f"loadBoundary({json.dumps(json.dumps(boundary_data))});")

    def load_plant_marker(self, plant_id: int, common_name: str, lat: float, lng: float,
                          spacing_m: float = 1.0, plant_type: str = "herb",
                          custom_color: str = "", group_id: str = ""):
        color_arg = f", '{custom_color}'" if custom_color else ", null"
        group_arg = f", {repr(group_id)}" if group_id else ", null"
        self.run_js(
            f"loadPlantMarker({plant_id}, {repr(common_name)}, {lat}, {lng}, "
            f"{spacing_m}, {repr(plant_type)}{color_arg}{group_arg});"
        )

    def set_view(self, lat: float, lng: float, zoom: int = 14):
        self.run_js(f"setView({lat}, {lng}, {zoom});")

    def invalidate_size(self):
        """Force Leaflet to recompute the map container size.

        Safe to call before the map is ready; the JS side feature-checks
        `map` before invoking `invalidateSize`. Useful any time the host
        QWidget reflows (sidebar collapse, splitter drag, window resize)
        or after a synchronous burst of Python work that may have starved
        the WebEngine paint queue — both scenarios can leave Leaflet's
        canvas renderer cached at a stale size, which manifests as a blank
        map with dead zoom/satellite controls.
        """
        self.run_js(
            "if (typeof map !== 'undefined' && map && map.invalidateSize) "
            "{ map.invalidateSize(false); }"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Coalesce resize bursts (splitter drag, window restore, sidebar
        # collapse) into one invalidateSize per event-loop tick so we don't
        # spam runJavaScript dozens of times during a drag.
        if not getattr(self, "_pending_invalidate", False):
            self._pending_invalidate = True
            QTimer.singleShot(0, self._do_invalidate)

    def _do_invalidate(self):
        self._pending_invalidate = False
        self.invalidate_size()

    def place_site_pin(self, lat: float, lng: float, label: str = ""):
        """Place (or move) the property pin without going through the search box."""
        import json as _json
        self.run_js(
            f"placeSitePin({lat}, {lng}, {_json.dumps(label or '')});"
        )

    def clear_site_pin(self):
        self.run_js("clearSitePin(false);")

    def set_site_pin_drop_mode(self, active: bool):
        """Toggle the crosshair cursor while the user is arming a pin drop."""
        flag = "true" if active else "false"
        self.run_js(f"setSitePinDropMode({flag});")

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

    def set_grid_style(self, color: str, opacity: float):
        """Update the on-map grid colour and opacity (0..1)."""
        import json as _json
        self.run_js(
            f"setGridStyle({_json.dumps(color)}, {float(opacity)});"
        )

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

    def enter_sun_anchor_mode(self):
        """Enter sun-path anchor placement mode (user clicks map to place)."""
        self.run_js("setMode('sun_anchor');")

    def enter_sector_anchor_mode(self):
        """Enter sector anchor placement mode."""
        self.run_js("setMode('sector_anchor');")

    def draw_sun_path(self, data: dict, lat: float = None, lng: float = None):
        """Draw the sun path arc and shadow arrows on the map."""
        import json
        if lat is not None and lng is not None:
            self.run_js(
                f"drawSunPath(JSON.parse({json.dumps(json.dumps(data))}), {lat}, {lng});"
            )
        else:
            self.run_js(f"drawSunPath(JSON.parse({json.dumps(json.dumps(data))}));")

    def clear_sun_path(self):
        self.run_js("clearSunPath();")

    def draw_sectors(self, data: dict, lat: float = None, lng: float = None):
        """Draw sector analysis wedges on the map at the given anchor."""
        import json
        if lat is not None and lng is not None:
            self.run_js(
                f"drawSectors(JSON.parse({json.dumps(json.dumps(data))}), {lat}, {lng});"
            )
        else:
            self.run_js(f"drawSectors(JSON.parse({json.dumps(json.dumps(data))}));")

    def clear_sectors(self):
        self.run_js("clearSectors();")

    def set_zoom_sensitivity(self, level: str):
        """Set zoom sensitivity: 'fine'|'normal'|'fast'|'coarse'."""
        self.run_js(f"setZoomSensitivity({repr(level)});")

    def set_contour_mode(self, config: dict):
        """Enter contour drawing mode."""
        import json
        self.run_js(f"setMode('contour', JSON.parse({json.dumps(json.dumps(config))}));")

    def clear_contours(self):
        self.run_js("clearContours();")

    # ── Auto terrain (slope contours / ramp) ──────────────────────────────────

    def request_terrain_viewport(self):
        """Ask JS for the current viewport bbox; signalled back via terrain_bbox_ready."""
        self.run_js("emitTerrainBboxFromViewport();")

    def request_terrain_boundary_bbox(self):
        """Ask JS to compute the bbox of the (single) drawn property boundary."""
        self.run_js("emitTerrainBboxFromBoundary();")

    def enter_terrain_draw_mode(self):
        """Enter free-draw rectangle mode for picking a terrain bbox."""
        self.run_js("setMode('terrain_rect');")

    def draw_auto_contours(self, contours: list[dict], color: str, show_labels: bool):
        """Render generated contour lines on the map. Replaces existing auto layer."""
        import json as _json
        payload = {
            "contours":    contours,
            "color":       color,
            "show_labels": bool(show_labels),
        }
        self.run_js(
            f"drawAutoContours(JSON.parse({_json.dumps(_json.dumps(payload))}));"
        )

    def draw_slope_overlay(self, png_data_url: str, bbox: dict, opacity: float):
        """Render the slope ramp PNG as an ImageOverlay. Replaces any existing one."""
        import json as _json
        payload = {
            "image":   png_data_url,
            "bbox":    bbox,
            "opacity": float(opacity),
        }
        self.run_js(
            f"drawSlopeOverlay(JSON.parse({_json.dumps(_json.dumps(payload))}));"
        )

    def set_slope_overlay_opacity(self, opacity: float):
        self.run_js(f"setSlopeOverlayOpacity({float(opacity)});")

    def clear_auto_terrain(self):
        """Remove auto-generated contours and slope overlay."""
        self.run_js("clearAutoTerrain();")

    def draw_wind_overlay(self, data: dict):
        """Draw wind direction arrows and shelter zones."""
        import json
        self.run_js(f"drawWindOverlay(JSON.parse({json.dumps(json.dumps(data))}));")

    def clear_wind_overlay(self):
        self.run_js("clearWindOverlay();")
