"""
map_widget.py — QtWebEngine wrapper around the Leaflet map.

Exposes a MapBridge QObject whose slots are callable from JavaScript via
QWebChannel. Python code crosses the boundary the other way through the
MapWidget methods below, which build their JS via the typed builders in
``src/map_js.py`` — never via inline f-strings. If you need a new entry
point, add a builder there and a thin method here.
"""

import os
import sys
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PyQt6.QtWebChannel import QWebChannel

from src import map_js
from src.settings import get_mapbox_token


def _dbg(msg: str) -> None:
    """Append a diagnostic line to ~/permadesign-debug.log.

    Used both for informational tracing AND as part of the load-bearing
    resize machinery (see the block comment above MapWidget.invalidate_size):
    the file write yields to the OS scheduler at exactly the moment we
    need Chromium's renderer IPC to land. Stays file-only so it doesn't
    spam the terminal; for messages users should actually see, use _err.
    """
    try:
        import time
        path = os.path.join(os.path.expanduser("~"), "permadesign-debug.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def _err(msg: str) -> None:
    """Like _dbg but also writes to stderr -- for genuine errors (JS
    exceptions, renderer crashes) that should surface to anyone running
    the app from a terminal."""
    _dbg(msg)
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass


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
    shape_complete = pyqtSignal(str, str, str, str, str, str, float, str, float, float)
        # id, pointsJson, label, shapeType, fillColor, strokeColor, fillOpacity, dashArray, areaM2, heightM
    shape_removed = pyqtSignal(str)                                 # id
    shape_height_changed = pyqtSignal(str, float)                  # id, heightM

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

    @pyqtSlot(str, str, str, str, str, str, float, str, float, float)
    def onShapeComplete(self, shape_id: str, points_json: str, label: str,
                        shape_type: str, fill_color: str, stroke_color: str,
                        fill_opacity: float, dash_array: str, area_m2: float,
                        height_m: float = 0.0):
        self.shape_complete.emit(shape_id, points_json, label, shape_type,
                                 fill_color, stroke_color, fill_opacity,
                                 dash_array, area_m2, height_m)

    @pyqtSlot(str)
    def onShapeRemoved(self, shape_id: str):
        self.shape_removed.emit(shape_id)

    @pyqtSlot(str, float)
    def onShapeHeightChanged(self, shape_id: str, height_m: float):
        self.shape_height_changed.emit(shape_id, height_m)

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
        # Errors go to stderr too; info/warn (and our load-bearing
        # invalidate-reflow console.logs) stay file-only.
        sink = _err if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel else _dbg
        sink(f"[js:{tag}] {src}:{line}  {message}")


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
        self.bridge.map_ready.connect(self._on_map_ready)

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

    def _on_map_ready(self):
        token = get_mapbox_token()
        if token:
            self.set_mapbox_token(token)

    def _on_render_terminated(self, status, exit_code):
        # status is QWebEnginePage.RenderProcessTerminationStatus; print
        # both raw and name so we can read it without consulting the docs.
        name = getattr(status, "name", str(status))
        _err(
            f"[webengine] *** RENDER PROCESS TERMINATED *** status={name} "
            f"exit_code={exit_code}"
        )

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
            self.run_js(map_js.set_mode_with_payload("plant", payload))
        else:
            self.run_js(map_js.set_mode(mode))

    def cancel_draw(self):
        self.run_js(map_js.cancel_draw())

    def clear_measure(self):
        self.run_js(map_js.clear_measure())

    def clear_all(self):
        self.run_js(map_js.clear_all())

    def set_satellite_visible(self, visible: bool):
        self.run_js(map_js.set_satellite_visible(visible))

    def set_mapbox_token(self, token: str):
        self.run_js(map_js.init_mapbox_layer(token))

    def set_boundary_visible(self, visible: bool):
        self.run_js(map_js.set_boundary_visible(visible))

    def set_measurements_visible(self, visible: bool):
        self.run_js(map_js.set_measure_visible(visible))

    def set_plants_visible(self, visible: bool):
        self.run_js(map_js.set_plants_visible(visible))

    def load_boundary(self, boundary_data: dict):
        """Load a boundary from a saved project. boundary_data has id/points/color/showLengths/showArea."""
        self.run_js(map_js.load_boundary(boundary_data))

    def load_plant_marker(self, plant_id: int, common_name: str, lat: float, lng: float,
                          spacing_m: float = 1.0, plant_type: str = "herb",
                          custom_color: str = "", group_id: str = "",
                          community_id: str = ""):
        self.run_js(map_js.load_plant_marker(
            plant_id, common_name, lat, lng,
            spacing_m=spacing_m, plant_type=plant_type,
            custom_color=custom_color or None,
            group_id=group_id or None,
            community_id=community_id or None,
        ))

    def set_view(self, lat: float, lng: float, zoom: int = 14):
        self.run_js(map_js.set_view(lat, lng, zoom))

    # ── LOAD-BEARING RESIZE / INVALIDATE MACHINERY ───────────────────────
    # The block below (invalidate_size + resizeEvent + _do_invalidate) is
    # the result of a long debugging session against the Windows + LiDAR
    # contours + maximise freeze. Several lines that LOOK like debug
    # instrumentation are actually doing real work:
    #
    #   - The `console.log(... map.getContainer().clientWidth ...)` inside
    #     invalidate_size forces Chromium to commit its pending viewport
    #     update before Leaflet measures the container. `void(...)` and
    #     other "I'm just reading clientWidth for the side effect"
    #     idioms get elided by V8; passing the value to console.log keeps
    #     the read live.
    #
    #   - The two console.log calls (one before, one after invalidateSize)
    #     each force a layout reflow, which catches the viewport on either
    #     side of Leaflet's own size update.
    #
    #   - The `_dbg(...)` calls inside resizeEvent / _do_invalidate write
    #     to a file -- the resulting syscall yields to the OS scheduler,
    #     which gives Chromium's separate renderer process time to deliver
    #     pending IPC events between Qt's resize and our invalidate.
    #
    # All three together are what makes "maximise window with LiDAR
    # contours visible" work on Windows. Removing any one of them tends
    # to reintroduce the freeze or the half-painted map. Confirmed in
    # commits 3dcc74b (cleanup) -> cea0c7f (revert).
    # ─────────────────────────────────────────────────────────────────────

    def invalidate_size(self):
        """Force Leaflet to recompute the map container size.

        Safe to call before the map is ready; the JS side feature-checks
        `map` before invoking `invalidateSize`. Useful any time the host
        QWidget reflows (sidebar collapse, splitter drag, window resize)
        or after a synchronous burst of Python work that may have starved
        the WebEngine paint queue — both scenarios can leave Leaflet's
        canvas renderer cached at a stale size, which manifests as a blank
        map with dead zoom/satellite controls.

        The JS string itself lives in ``map_js.invalidate_size()`` —
        *** do not "clean up" the console.log calls there. *** They
        look like debug noise but each one reads clientWidth /
        clientHeight, which forces a Chromium layout reflow as a
        documented browser side effect. Without those reads, on Windows
        the embedded viewport stays at the pre-resize size after a
        maximise and the map paints only into the corner of the widget.
        See the block comment above this method for the full context.
        """
        self.run_js(map_js.invalidate_size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        sz = event.size()
        # _dbg() is load-bearing here: see the block comment above
        # invalidate_size. The file I/O yields to the OS scheduler.
        _dbg(f"[mapwidget] resizeEvent w={sz.width()} h={sz.height()}")
        # Coalesce resize bursts (splitter drag, window restore, sidebar
        # collapse) into one invalidateSize per event-loop tick so we don't
        # spam runJavaScript dozens of times during a drag.
        if not getattr(self, "_pending_invalidate", False):
            self._pending_invalidate = True
            QTimer.singleShot(0, self._do_invalidate)

    def _do_invalidate(self):
        self._pending_invalidate = False
        # _dbg() is load-bearing -- see the block comment above invalidate_size.
        _dbg(f"[mapwidget] _do_invalidate -> invalidate_size (size={self.width()}x{self.height()})")
        self.invalidate_size()

    def place_site_pin(self, lat: float, lng: float, label: str = ""):
        """Place (or move) the property pin without going through the search box."""
        self.run_js(map_js.place_site_pin(lat, lng, label or ""))

    def clear_site_pin(self):
        self.run_js(map_js.clear_site_pin())

    def set_site_pin_drop_mode(self, active: bool):
        """Toggle the crosshair cursor while the user is arming a pin drop."""
        self.run_js(map_js.set_site_pin_drop_mode(active))

    def set_labels_visible(self, visible: bool):
        self.run_js(map_js.set_labels_visible(visible))

    def update_marker_color(self, plant_id: int, color: str):
        self.run_js(map_js.update_marker_color(plant_id, color))

    def place_annotation(self, ann_id: str, lat: float, lng: float, text: str):
        self.run_js(map_js.place_annotation(ann_id, lat, lng, text))

    def set_canopy_visible(self, visible: bool):
        self.run_js(map_js.set_canopy_visible(visible))

    def set_snap_enabled(self, enabled: bool, grid_size: float = 1.0):
        self.run_js(map_js.set_snap_enabled(enabled, grid_size))

    def set_grid_style(self, color: str, opacity: float):
        """Update the on-map grid colour and opacity (0..1)."""
        self.run_js(map_js.set_grid_style(color, opacity))

    # ── Structure helpers ─────────────────────────────────────────────────────

    def set_structure_mode(self, struct_def: dict):
        """Enter structure placement mode with a structure definition."""
        self.run_js(map_js.set_mode_with_payload("structure", struct_def))

    def load_structure(self, struct_def: dict, lat: float, lng: float):
        """Load a structure from a saved project."""
        self.run_js(map_js.load_structure(struct_def, lat, lng))

    # ── Hedgerow helpers ──────────────────────────────────────────────────────

    def set_hedgerow_mode(self, hedge_config: dict):
        """Enter hedgerow drawing mode."""
        self.run_js(map_js.set_mode_with_payload("hedgerow", hedge_config))

    def load_hedgerow(self, hedge_def: dict):
        """Load a hedgerow from a saved project."""
        self.run_js(map_js.load_hedgerow(hedge_def))

    # ── Shape helpers ─────────────────────────────────────────────────────────

    def set_shape_mode(self, shape_config: dict):
        """Enter custom shape drawing mode."""
        self.run_js(map_js.set_mode_with_payload("shape", shape_config))

    def load_shape(self, shape_def: dict):
        """Load a custom shape from a saved project."""
        self.run_js(map_js.load_shape(shape_def))

    def set_structures_visible(self, visible: bool):
        self.run_js(map_js.set_structures_visible(visible))

    # ── Analysis overlay helpers (A1-A4) ──────────────────────────────────────

    def enter_sun_anchor_mode(self):
        """Enter sun-path anchor placement mode (user clicks map to place)."""
        self.run_js(map_js.set_mode("sun_anchor"))

    def enter_sector_anchor_mode(self):
        """Enter sector anchor placement mode."""
        self.run_js(map_js.set_mode("sector_anchor"))

    def draw_sun_path(self, data: dict, lat: float = None, lng: float = None):
        """Draw the sun path arc and shadow arrows on the map."""
        if lat is not None and lng is not None:
            self.run_js(map_js.draw_sun_path(data, lat, lng))
        else:
            self.run_js(map_js.draw_sun_path(data))

    def clear_sun_path(self):
        self.run_js(map_js.clear_sun_path())

    def draw_sectors(self, data: dict, lat: float = None, lng: float = None):
        """Draw sector analysis wedges on the map at the given anchor."""
        if lat is not None and lng is not None:
            self.run_js(map_js.draw_sectors(data, lat, lng))
        else:
            self.run_js(map_js.draw_sectors(data))

    def clear_sectors(self):
        self.run_js(map_js.clear_sectors())

    def set_zoom_sensitivity(self, level: str):
        """Set zoom sensitivity: 'fine'|'normal'|'fast'|'coarse'."""
        self.run_js(map_js.set_zoom_sensitivity(level))

    def set_contour_mode(self, config: dict):
        """Enter contour drawing mode."""
        self.run_js(map_js.set_mode_with_payload("contour", config))

    def clear_contours(self):
        self.run_js(map_js.clear_contours())

    # ── Auto terrain (slope contours / ramp) ──────────────────────────────────

    def request_terrain_viewport(self):
        """Ask JS for the current viewport bbox; signalled back via terrain_bbox_ready."""
        self.run_js(map_js.request_terrain_viewport())

    def request_terrain_boundary_bbox(self):
        """Ask JS to compute the bbox of the (single) drawn property boundary."""
        self.run_js(map_js.request_terrain_boundary_bbox())

    def enter_terrain_draw_mode(self):
        """Enter free-draw rectangle mode for picking a terrain bbox."""
        self.run_js(map_js.set_mode("terrain_rect"))

    def draw_auto_contours(self, contours: list[dict], color: str, show_labels: bool):
        """Render generated contour lines on the map. Replaces existing auto layer."""
        self.run_js(map_js.draw_auto_contours(contours, color, show_labels))

    def draw_slope_overlay(self, png_data_url: str, bbox: dict, opacity: float):
        """Render the slope ramp PNG as an ImageOverlay. Replaces any existing one."""
        self.run_js(map_js.draw_slope_overlay(png_data_url, bbox, opacity))

    def set_slope_overlay_opacity(self, opacity: float):
        self.run_js(map_js.set_slope_overlay_opacity(opacity))

    def draw_shade_overlay(self, png_data_url: str, bbox: dict, opacity: float):
        """Render the shade-fraction PNG as a separate ImageOverlay (V1.51)."""
        self.run_js(map_js.draw_shade_overlay(png_data_url, bbox, opacity))

    def set_shade_overlay_opacity(self, opacity: float):
        self.run_js(map_js.set_shade_overlay_opacity(opacity))

    def clear_shade_overlay(self):
        self.run_js(map_js.clear_shade_overlay())

    def clear_auto_terrain(self):
        """Remove auto-generated contours and slope overlay."""
        self.run_js(map_js.clear_auto_terrain())

    def draw_wind_overlay(self, data: dict):
        """Draw wind direction arrows and shelter zones."""
        self.run_js(map_js.draw_wind_overlay(data))

    def clear_wind_overlay(self):
        self.run_js(map_js.clear_wind_overlay())

    # ── New typed methods for the formerly-direct ``map_widget.run_js(...)``
    # call sites in src/app.py. Each is a one-line wrapper around the
    # matching builder in src.map_js. Keep this section in alphabetical
    # order to make audit grep easy.

    def apply_loaded_contour(self, contour: dict):
        """Re-finish a saved contour on the map (re-uses the JS-side
        in-progress drawing globals)."""
        self.run_js(map_js.restore_contour(contour))

    def clear_selection(self):
        """Clear the current map selection (no delete)."""
        self.run_js(map_js.clear_selection())

    def delete_selected(self):
        """Delete every currently-selected map item."""
        self.run_js(map_js.delete_selected())

    def place_plant_marker(self, plant_id: int, common_name: str,
                            lat: float, lng: float,
                            spacing_m: float = 1.0, plant_type: str = "herb",
                            color: str | None = None,
                            group_id: str | None = None,
                            community_id: str | None = None):
        """Place a plant marker as a fresh user action. Compare to
        ``load_plant_marker`` which is the project-load variant."""
        self.run_js(map_js.place_plant_marker(
            plant_id, common_name, lat, lng,
            spacing_m=spacing_m, plant_type=plant_type,
            color=color, group_id=group_id, community_id=community_id,
        ))

    def revert_plant_position(self, plant_id: int,
                                from_lat: float, from_lng: float,
                                to_lat: float, to_lng: float):
        """Used by undo/redo on a plant drag."""
        self.run_js(map_js.revert_plant_position(
            plant_id, from_lat, from_lng, to_lat, to_lng,
        ))

    def set_crosshair_cursor(self):
        """Force a crosshair cursor on the map — used while arming a
        plant-community click-to-place gesture."""
        self.run_js(map_js.set_crosshair_cursor())

    def set_plant_group_for_latest(self, plant_id: int, lat: float, lng: float,
                                    group_id: str):
        """Tell JS the freshest marker's group id so right-click →
        Delete group works."""
        self.run_js(map_js.set_plant_group_for_latest(
            plant_id, lat, lng, group_id,
        ))

    def set_season_view(self, season: str, pid_visibility: dict):
        """Highlight plants in/out of season for a given month name."""
        self.run_js(map_js.set_season_view(season, pid_visibility))

    def set_timeline_year_by_plant_id(self, year: int, pid_factors: dict):
        """Drive the growth-timeline animation."""
        self.run_js(map_js.set_timeline_year_by_plant_id(year, pid_factors))

    def toggle_legend(self):
        """Toggle the on-map legend overlay."""
        self.run_js(map_js.toggle_legend())

    def undo_boundary(self, boundary_id: str):
        self.run_js(map_js.undo_boundary(boundary_id))

    def undo_custom_shape_by_id(self, shape_id: str):
        self.run_js(map_js.undo_custom_shape_by_id(shape_id))

    def undo_hedgerow_by_id(self, hedge_id: str):
        self.run_js(map_js.undo_hedgerow_by_id(hedge_id))

    def undo_last_contour(self, elevation_m: float):
        self.run_js(map_js.undo_last_contour(elevation_m))

    def undo_place_plant(self, plant_id: int, lat: float, lng: float):
        """Remove the most-recent marker matching (plant_id, lat, lng)."""
        self.run_js(map_js.undo_place_plant(plant_id, lat, lng))

    def undo_structure_at(self, struct_id: str, lat: float, lng: float):
        self.run_js(map_js.undo_structure_at(struct_id, lat, lng))
