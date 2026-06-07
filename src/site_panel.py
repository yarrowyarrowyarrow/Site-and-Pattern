"""
site_panel.py — Side-panel tab for the property pin and auto-filled site data.

Workflow:

  1. User drops a pin via the in-map search bar (or by clicking "Use Pin
     Drop" and clicking the map).
  2. ``set_pin(lat, lng, label)`` is called from the main window.
  3. The panel kicks off a background fetch for rainfall, soil, elevation
     and hardiness; results stream into the UI as each one returns.
  4. ``site_data_updated`` is emitted when every fetch completes so the
     main window can persist the result into ``project.properties.site_config``.

Network calls happen on a ``QThread`` so the UI never blocks. Errors
return ``None`` from the fetcher and the corresponding row shows
"unavailable".
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFormLayout, QFrame, QGroupBox, QScrollArea, QComboBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QSlider, QColorDialog,
    QListWidget, QListWidgetItem, QProgressBar, QTabWidget,
)


# ── QThread-lifecycle helper ─────────────────────────────────────────────────

def _safe_is_running(thread) -> bool:
    """Return True only if ``thread`` is a still-live QThread that's running.

    The auto-teardown chain wired up in ``_start_fetch`` / ``_run_geocode``
    deletes the underlying C++ QThread once it stops. Our Python proxy
    can outlive that — calling any method on it (including
    ``isRunning()``) then raises
    ``RuntimeError: wrapped C/C++ object of type QThread has been deleted``,
    which is what crashed the app on Clear pin. Treating that as
    "not running" is the right semantics: if the C++ side is gone the
    thread definitely isn't running anymore.
    """
    if thread is None:
        return False
    try:
        return thread.isRunning()
    except RuntimeError:
        return False


# ── Background fetcher ───────────────────────────────────────────────────────

class _SiteFetchWorker(QObject):
    """Runs in its own QThread; emits a signal per dataset as it completes."""

    progress      = pyqtSignal(str)           # status message
    rainfall      = pyqtSignal(object)        # dict | None
    soil          = pyqtSignal(object)
    elevation     = pyqtSignal(object)
    hardiness     = pyqtSignal(object)
    climate       = pyqtSignal(object)        # GDD / frost-window summary
    ecoregion     = pyqtSignal(object)        # auto-detected AB ecoregion
    fast_ready    = pyqtSignal()              # fast batch done — climate may still be loading
    finished      = pyqtSignal(dict)          # combined result dict

    def __init__(self, lat: float, lng: float):
        super().__init__()
        self.lat, self.lng = lat, lng
        self._cancelled = False

    @pyqtSlot()
    def run(self):
        """V1.37: run the five fast fetches *concurrently* via a thread
        pool, then declare "site data ready" as soon as they're all
        in. Total perceived latency drops from ~sum-of-latencies
        (sequential) to ~max-of-latencies (parallel) — typically
        SoilGrids and Open-Meteo elevation run in 0.5-1.5 s and
        used to stack, now they overlap. The slower climate fetch
        still runs as a tail step so the GDD row updates from "—"
        when its result arrives separately.

        Cancellation is best-effort: in-flight HTTP requests can't
        be interrupted, but no further work happens once cancel()
        is called."""
        from concurrent.futures import ThreadPoolExecutor
        from src.property_data import (
            fetch_rainfall, fetch_soil, fetch_elevation, fetch_hardiness,
            fetch_climate, fetch_ecoregion,
        )
        out = {"lat": self.lat, "lng": self.lng}

        fast_steps = [
            ("ecoregion", "Detecting ecoregion…",             fetch_ecoregion, self.ecoregion),
            ("hardiness", "Looking up hardiness zone…",       fetch_hardiness, self.hardiness),
            ("elevation", "Sampling Copernicus DEM…",         fetch_elevation, self.elevation),
            ("rainfall",  "Computing ERA5-Land rainfall…",    fetch_rainfall,  self.rainfall),
            ("soil",      "Querying SoilGrids…",              fetch_soil,      self.soil),
        ]

        def _run_step(fn):
            try:
                return fn(self.lat, self.lng)
            except Exception:
                return None

        # Five concurrent HTTP / local-lookup calls. Sequential total
        # was ~5 seconds; parallel runs in whatever the slowest single
        # fetch takes (usually SoilGrids at ~1-2 s).
        self.progress.emit("Fetching site data…")
        with ThreadPoolExecutor(max_workers=len(fast_steps)) as pool:
            future_to_step = {
                pool.submit(_run_step, fn): (key, sig)
                for key, _msg, fn, sig in fast_steps
            }
            # As each future completes, surface its result via the
            # matching signal — the panel updates incrementally instead
            # of waiting for the whole batch.
            from concurrent.futures import as_completed
            for future in as_completed(future_to_step):
                if self._cancelled:
                    break
                key, sig = future_to_step[future]
                value = future.result()
                out[key] = value
                sig.emit(value)

        # Fast batch is in — flip the user-visible status to ready
        # immediately. The climate signal will still arrive later.
        self.fast_ready.emit()

        if not self._cancelled:
            self.progress.emit("Computing growing-degree days…")
            try:
                value = fetch_climate(self.lat, self.lng)
            except Exception:
                value = None
            out["climate"] = value
            self.climate.emit(value)
            # Clear the progress line once the climate fetch is done —
            # otherwise the "Computing growing-degree days…" message
            # sits there forever even after the GDD row populates.
            self.progress.emit("Site data ready.")

        self.finished.emit(out)

    def cancel(self):
        self._cancelled = True


# ── Geocode worker (Nominatim, Alberta-bounded) ─────────────────────────────

class _GeocodeWorker(QObject):
    """Runs a single forward-geocode request off the UI thread."""

    results = pyqtSignal(list)        # list[{label, lat, lng}]
    failed  = pyqtSignal(str)         # error message

    def __init__(self, query: str,
                 near: "tuple[float, float] | None" = None):
        super().__init__()
        self._query = query
        self._near  = near

    @pyqtSlot()
    def run(self):
        try:
            from src.property_data import geocode_alberta
            hits = geocode_alberta(self._query, near=self._near) or []
            self.results.emit(hits)
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Panel widget ─────────────────────────────────────────────────────────────

class SitePanel(QWidget):
    """Panel that shows the current property pin and its auto-filled data."""

    pin_drop_requested = pyqtSignal()             # user wants to click the map
    pin_clear_requested = pyqtSignal()
    site_data_updated  = pyqtSignal(dict)         # full result dict

    # Address search (geocode + place pin). Emitted when the user has
    # selected a result; MainWindow places the pin on the map and the
    # usual site_pin_placed flow then fills in site data.
    address_resolved = pyqtSignal(float, float, str)   # lat, lng, label

    # Auto-generated slope contours / ramp overlay (formerly on Analysis tab).
    # Lives here because it's site-scale terrain analysis, alongside the
    # single-point elevation/slope readout.
    auto_terrain_requested = pyqtSignal(dict)
    auto_terrain_cleared   = pyqtSignal()
    auto_terrain_opacity   = pyqtSignal(float)    # 0..1, live slider

    # Manual contour line drawing (moved from Analysis tab).
    contour_requested = pyqtSignal(dict)
    contour_cleared   = pyqtSignal()

    # Offline Edmonton terrain dataset download.
    download_edmonton_requested = pyqtSignal()

    # Shade overlay (V1.51): show/clear, live opacity, and a (month, day, hour)
    # time selection for the time-of-day / season view.
    shade_requested = pyqtSignal(dict)    # {"when": (month, day, hour) | None}
    shade_cleared   = pyqtSignal()
    shade_opacity   = pyqtSignal(float)   # 0..1, live slider
    shade_zones_requested = pyqtSignal()  # classify planting zones → tag cache

    # Import existing trees/buildings from OpenStreetMap (V1.51).
    osm_import_requested = pyqtSignal()

    # Import shade-casting footprints from an nDSM GeoTIFF (V1.53).
    footprint_import_requested = pyqtSignal(str)   # tiff path

    # Mark/draw existing shade casters on the Shade sub-tab (V1.59 — relocated
    # from the Structures panel). Reuse the existing placement pipeline.
    place_structure_requested = pyqtSignal(dict)   # existing tree/building point
    place_shape_requested     = pyqtSignal(dict)   # draw footprint / tree canopy

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lat: Optional[float] = None
        self._lng: Optional[float] = None
        self._label: str = ""
        self._thread: Optional[QThread] = None
        self._worker: Optional[_SiteFetchWorker] = None
        self._geo_thread: Optional[QThread] = None
        self._geo_worker: Optional[_GeocodeWorker] = None
        self._geo_debounce: Optional[QTimer] = None
        self._auto_color = "#44cc00"
        self._contour_color = "#795548"
        # Map widget reference, set by MainWindow via attach_map_widget().
        # Used to bias the address-finder search against the current
        # view centre — without it we fall back to all-of-Alberta.
        self._map_widget = None
        self._build_ui()
        self._set_empty_state()

    def attach_map_widget(self, map_widget):
        """Wire the panel to the map widget so the address finder can
        bias its query against the map's current view centre."""
        self._map_widget = map_widget

    # ── Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        """Site panel split into three sub-tabs (mirrors the Plants panel):
        Site Information, Slope, and Shade."""
        from src.ui_style import inner_tab_stylesheet
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(True)
        tabs.setStyleSheet(inner_tab_stylesheet())
        outer.addWidget(tabs)

        self._build_info_page(self._add_scroll_page(tabs, "Site Information"))
        self._build_slope_page(self._add_scroll_page(tabs, "Slope"))
        self._build_shade_page(self._add_scroll_page(tabs, "Shade"))

    def _add_scroll_page(self, tabs, title):
        """Add a scrollable page to the inner tab strip; return its body layout."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        tabs.addTab(scroll, title)
        return layout

    def _build_info_page(self, layout):
        """Site Information sub-tab: property pin/address + climate + soil."""
        info = QLabel(
            "Search an Alberta address below to drop a property pin and\n"
            "auto-fill site data from public sources. Drag the pin to\n"
            "refine; right-click on the pin to remove."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # ── Property pin (with address search) ───────────────────────
        pin_box = QGroupBox("Property pin")
        pin_box.setStyleSheet(_GROUP_STYLE)
        pin_layout = QVBoxLayout(pin_box)
        pin_layout.setSpacing(6)

        # Address search row.
        search_row = QHBoxLayout()
        self._addr_input = QLineEdit()
        self._addr_input.setPlaceholderText("Search Alberta address or place name…")
        self._addr_input.setClearButtonEnabled(True)
        self._addr_input.setStyleSheet(
            "QLineEdit { background: #0d1f0d; color: #e8f5e9; "
            "border: 1px solid #4a7a4a; border-radius: 4px; padding: 4px 6px; }"
            "QLineEdit:focus { border-color: #66bb6a; }"
        )
        self._addr_input.returnPressed.connect(self._on_address_search)
        self._addr_input.textChanged.connect(self._on_address_text_changed)
        search_row.addWidget(self._addr_input, 1)

        self._btn_search = QPushButton("Find")
        self._btn_search.setStyleSheet(_BTN_PRIMARY)
        self._btn_search.clicked.connect(self._on_address_search)
        search_row.addWidget(self._btn_search)
        pin_layout.addLayout(search_row)

        # Suggestion list — empty/hidden until typeahead returns hits.
        self._addr_results = QListWidget()
        self._addr_results.setMaximumHeight(120)
        self._addr_results.setVisible(False)
        self._addr_results.setStyleSheet(
            "QListWidget { background: #0d1f0d; color: #c8e6c9; "
            "border: 1px solid #4a7a4a; border-radius: 4px; }"
            "QListWidget::item:hover { background: #2e4a2e; }"
            "QListWidget::item:selected { background: #2e7d32; color: #ffffff; }"
        )
        self._addr_results.itemClicked.connect(self._on_address_pick)
        pin_layout.addWidget(self._addr_results)

        # Existing pin label / coords readout.
        pin_form = QFormLayout()
        pin_form.setContentsMargins(0, 0, 0, 0)
        self._lbl_label = QLabel("—")
        self._lbl_label.setWordWrap(True)
        self._lbl_coords = QLabel("—")
        pin_form.addRow("Location:", self._lbl_label)
        pin_form.addRow("Coordinates:", self._lbl_coords)
        pin_layout.addLayout(pin_form)

        # Action buttons (manual pin drop / refresh / clear).
        btn_row = QHBoxLayout()
        self._btn_drop = QPushButton("Use Pin Drop…")
        self._btn_drop.setToolTip(
            "Click then click the map to drop the property pin manually"
        )
        self._btn_drop.setStyleSheet(_BTN_PRIMARY)
        self._btn_drop.clicked.connect(self.pin_drop_requested.emit)
        btn_row.addWidget(self._btn_drop)

        self._btn_refresh = QPushButton("Refresh data")
        self._btn_refresh.setStyleSheet(_BTN_SECONDARY)
        self._btn_refresh.clicked.connect(self._refresh_clicked)
        btn_row.addWidget(self._btn_refresh)

        self._btn_clear = QPushButton("Clear pin")
        self._btn_clear.setStyleSheet(_BTN_SECONDARY)
        self._btn_clear.clicked.connect(self.pin_clear_requested.emit)
        btn_row.addWidget(self._btn_clear)
        pin_layout.addLayout(btn_row)

        layout.addWidget(pin_box)

        self._lbl_status = QLabel("")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setStyleSheet(
            "color: #ffcc80; font-size: 11px; padding: 2px 4px;"
        )
        layout.addWidget(self._lbl_status)

        # ── Hardiness + climate ──────────────────────────────────────
        # Order: zone → GDD → frost window → rainfall → soil sit directly
        # under the pin so the most-asked-for site stats are visible
        # without scrolling. GDD/frost rows are V1.35 additions — they
        # show "—" until the climate fetch completes (Open-Meteo
        # archive call, ~3-5 s on first run per location).
        self._hard_box = QGroupBox("Hardiness zone")
        self._hard_box.setStyleSheet(_GROUP_STYLE)
        hl = QFormLayout(self._hard_box)
        self._lbl_zone   = QLabel("—")
        self._lbl_zone.setStyleSheet("color: #c8e6c9; font-weight: bold; font-size: 14px;")
        self._lbl_hard_src = QLabel("")
        self._lbl_hard_src.setStyleSheet("color: #78909c; font-size: 10px;")
        self._lbl_hard_src.setWordWrap(True)
        self._lbl_gdd   = QLabel("—")
        self._lbl_gdd.setStyleSheet("color: #c8e6c9;")
        self._lbl_gdd.setToolTip(
            "Growing-degree days (base 5 °C) — cumulative summer warmth "
            "across the growing season. The single best predictor of "
            "whether a plant has enough heat to flower, fruit, and reach "
            "maturity at this location."
        )
        self._lbl_frost = QLabel("—")
        self._lbl_frost.setStyleSheet("color: #c8e6c9;")
        self._lbl_frost.setToolTip(
            "Average last spring frost → first fall frost, computed "
            "from the last 5 years of daily temperatures."
        )
        self._lbl_ecoregion = QLabel("—")
        self._lbl_ecoregion.setStyleSheet("color: #c8e6c9;")
        self._lbl_ecoregion.setToolTip(
            "Auto-detected from the property's latitude and longitude. "
            "The plant filter's ecoregion dropdown pre-populates from "
            "this value, so the suggestions you see are filtered to "
            "species native to your area. You can still override the "
            "filter manually."
        )
        hl.addRow("Zone:",                self._lbl_zone)
        hl.addRow("Source:",              self._lbl_hard_src)
        hl.addRow("Growing-degree days:", self._lbl_gdd)
        hl.addRow("Frost window:",        self._lbl_frost)
        hl.addRow("Ecoregion:",           self._lbl_ecoregion)
        layout.addWidget(self._hard_box)

        # ── Rainfall (moved up under pin/zone) ──────────────────────
        self._rain_box = QGroupBox("Rainfall (climate normal)")
        self._rain_box.setStyleSheet(_GROUP_STYLE)
        rl = QFormLayout(self._rain_box)
        self._lbl_rain_annual  = QLabel("—")
        self._lbl_rain_monthly = QLabel("—")
        self._lbl_rain_monthly.setWordWrap(True)
        self._lbl_rain_monthly.setStyleSheet(
            "color: #90caf9; font-family: monospace; font-size: 10px;"
        )
        self._lbl_rain_src = QLabel("")
        self._lbl_rain_src.setStyleSheet("color: #78909c; font-size: 10px;")
        self._lbl_rain_src.setWordWrap(True)
        rl.addRow("Annual mean:", self._lbl_rain_annual)
        rl.addRow("Monthly mm:",  self._lbl_rain_monthly)
        rl.addRow("Source:",      self._lbl_rain_src)
        layout.addWidget(self._rain_box)

        # ── Soil (moved up under pin/zone) ──────────────────────────
        self._soil_box = QGroupBox("Soil (top 0–5 cm)")
        self._soil_box.setStyleSheet(_GROUP_STYLE)
        sl = QFormLayout(self._soil_box)
        self._lbl_soil_ph      = QLabel("—")
        self._lbl_soil_texture = QLabel("—")
        self._lbl_soil_mix     = QLabel("—")
        self._lbl_soil_depth   = QLabel("—")
        self._lbl_soil_src     = QLabel("")
        self._lbl_soil_src.setStyleSheet("color: #78909c; font-size: 10px;")
        self._lbl_soil_src.setWordWrap(True)
        sl.addRow("pH (H₂O):",     self._lbl_soil_ph)
        sl.addRow("Texture class:", self._lbl_soil_texture)
        sl.addRow("Sand/Silt/Clay:", self._lbl_soil_mix)
        sl.addRow("Reported depth:", self._lbl_soil_depth)
        sl.addRow("Source:",        self._lbl_soil_src)
        layout.addWidget(self._soil_box)

        layout.addStretch()

    def _build_slope_page(self, layout):
        """Slope sub-tab: single-point elevation/slope, auto contours + slope
        colour ramp, and the offline terrain data download."""
        # Single-point Elevation / slope readout (formerly its own box).
        self._elev_box = QGroupBox("Elevation / slope (at pin)")
        self._elev_box.setStyleSheet(_GROUP_STYLE)
        el = QFormLayout(self._elev_box)
        self._lbl_elev    = QLabel("—")
        self._lbl_slope   = QLabel("—")
        self._lbl_aspect  = QLabel("—")
        self._lbl_elev_src = QLabel("")
        self._lbl_elev_src.setStyleSheet("color: #78909c; font-size: 10px;")
        self._lbl_elev_src.setWordWrap(True)
        el.addRow("Elevation:", self._lbl_elev)
        el.addRow("Slope:",     self._lbl_slope)
        el.addRow("Aspect:",    self._lbl_aspect)
        el.addRow("Source:",    self._lbl_elev_src)

        # ── Slope analysis (area) ───────────────────────────────────
        # Auto-generated contour lines + slope colour-ramp for an
        # area you choose. Pulls from City of Edmonton 0.5 m LiDAR
        # when in Edmonton, otherwise Copernicus DEM (~30 m) via
        # Open-Meteo. Job runs in the background; multiple Generate
        # clicks queue up rather than being rejected.
        self._slope_box = QGroupBox("Slope analysis")
        self._slope_box.setStyleSheet(_GROUP_STYLE)
        slope_layout = QVBoxLayout(self._slope_box)
        slope_layout.setSpacing(6)

        # Single-point readout sits at the top of the slope box.
        slope_layout.addWidget(self._elev_box)

        # Auto-generated contour / ramp section.
        auto_header = QLabel("<b>Auto contours & slope ramp (area)</b>")
        auto_header.setStyleSheet("color: #a5d6a7;")
        slope_layout.addWidget(auto_header)

        slope_info = QLabel(
            "Choose an area, then Generate. Edmonton uses the City's\n"
            "0.5 m LiDAR contours; elsewhere falls back to Copernicus DEM.\n"
            "30 m grid matches the DEM's native resolution — finer settings\n"
            "interpolate but don't add real detail."
        )
        slope_info.setWordWrap(True)
        slope_info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        slope_layout.addWidget(slope_info)

        slope_form = QFormLayout()
        slope_form.setContentsMargins(0, 0, 0, 0)

        self._auto_area_source = QComboBox()
        self._auto_area_source.addItems([
            "Current map view",
            "Drag rectangle on map…",
            "Use property boundary",
        ])
        self._auto_area_source.setToolTip(
            "Where to compute slope. 'Drag rectangle' lets you pick a "
            "smaller area than the current view."
        )
        slope_form.addRow("Area:", self._auto_area_source)

        self._auto_interval = QDoubleSpinBox()
        self._auto_interval.setRange(0.1, 5.0)
        self._auto_interval.setSingleStep(0.5)
        self._auto_interval.setValue(0.5)
        self._auto_interval.setSuffix(" m")
        self._auto_interval.setToolTip("Vertical spacing between contour lines.")
        slope_form.addRow("Interval:", self._auto_interval)

        self._auto_resolution = QDoubleSpinBox()
        self._auto_resolution.setRange(5.0, 60.0)
        self._auto_resolution.setSingleStep(5.0)
        self._auto_resolution.setValue(30.0)        # match Copernicus DEM native res
        self._auto_resolution.setSuffix(" m")
        self._auto_resolution.setToolTip(
            "Horizontal sample spacing for the slope grid.\n"
            "Open-Meteo's underlying DEM is 30 m native; setting this\n"
            "smaller mostly slows the request without adding real detail."
        )
        slope_form.addRow("Slope grid:", self._auto_resolution)

        self._auto_want_contours = QCheckBox("Show contour lines")
        self._auto_want_contours.setChecked(True)
        slope_form.addRow(self._auto_want_contours)

        self._auto_want_slope = QCheckBox("Show slope colour ramp")
        self._auto_want_slope.setChecked(True)
        slope_form.addRow(self._auto_want_slope)

        self._auto_show_labels = QCheckBox("Label every 5th contour")
        self._auto_show_labels.setChecked(True)
        slope_form.addRow(self._auto_show_labels)

        # Contour colour
        color_row = QHBoxLayout()
        self._auto_color_btn = QPushButton()
        self._auto_color_btn.setFixedSize(28, 28)
        self._auto_color_btn.setStyleSheet(
            f"background: {self._auto_color}; border: 1px solid #4a7a4a; "
            f"border-radius: 4px;"
        )
        self._auto_color_btn.clicked.connect(self._pick_auto_color)
        color_row.addWidget(self._auto_color_btn)
        color_row.addStretch()
        slope_form.addRow("Color:", color_row)

        slope_layout.addLayout(slope_form)

        opa_row = QHBoxLayout()
        opa_row.addWidget(QLabel("Ramp opacity:"))
        self._auto_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._auto_opacity_slider.setRange(0, 100)
        self._auto_opacity_slider.setValue(60)
        self._auto_opacity_slider.setToolTip("Transparency of the slope colour ramp.")
        self._auto_opacity_slider.valueChanged.connect(
            lambda v: self.auto_terrain_opacity.emit(v / 100.0)
        )
        opa_row.addWidget(self._auto_opacity_slider)
        slope_layout.addLayout(opa_row)

        self._auto_status = QLabel("")
        self._auto_status.setWordWrap(True)
        self._auto_status.setStyleSheet(
            "color: #ffcc80; font-size: 11px; padding: 2px;"
        )
        slope_layout.addWidget(self._auto_status)

        slope_btn_row = QHBoxLayout()
        btn_auto = QPushButton("Generate")
        btn_auto.setStyleSheet(_BTN_PRIMARY)
        btn_auto.clicked.connect(self._on_auto_terrain_generate)
        slope_btn_row.addWidget(btn_auto)

        btn_auto_clear = QPushButton("Clear")
        btn_auto_clear.setStyleSheet(_BTN_SECONDARY)
        btn_auto_clear.clicked.connect(self.auto_terrain_cleared.emit)
        slope_btn_row.addWidget(btn_auto_clear)
        slope_layout.addLayout(slope_btn_row)

        # The manual "Draw contour line" UI lived here pre-V1.37. It
        # was removed (user feedback: "I'm not sure a scenario where
        # the draw manually option would be useful"). The Auto-contour
        # & slope ramp section above generates contours from the DEM
        # for any chosen area — that covers every real workflow we
        # could think of. The `contour_requested` / `contour_cleared`
        # signals + `_on_draw_contour` / `_pick_contour_color` helpers
        # remain in place (they're cheap) so re-enabling the section
        # is a single block of UI build code if the need arises.

        layout.addWidget(self._slope_box)

        self._build_terrain_data_section(layout)

        layout.addStretch()

    def _build_shade_page(self, layout):
        """Shade sub-tab: shade map, existing shade casters (mark/draw trees and
        buildings), and the OpenStreetMap import."""
        self._build_shade_section(layout)
        self._build_existing_features_section(layout)
        self._build_osm_section(layout)
        layout.addStretch()

    # ── Public API (called from MainWindow) ─────────────────────────────────

    def set_pin(self, lat: float, lng: float, label: str = "", fetch: bool = True):
        """Set the active property pin.

        ``fetch=True`` (the default) starts a background data fetch.
        Pass ``fetch=False`` when restoring a saved project so the cached
        results aren't immediately overwritten by a network round-trip.
        """
        self._lat, self._lng, self._label = lat, lng, label or self._label
        self._lbl_coords.setText(f"{lat:.5f}, {lng:.5f}")
        if self._label:
            self._lbl_label.setText(self._label)
        else:
            self._lbl_label.setText("(custom pin)")
        # Re-clamp the shade time slider to this location's daylight window.
        if hasattr(self, "_shade_season"):
            self._on_shade_season_changed(self._shade_season.currentIndex())
        self._reset_data_rows()
        if fetch:
            self._start_fetch()
        else:
            self._lbl_status.setText("Showing cached data — click Refresh to update.")

    def clear_pin(self):
        """Forget the pin and reset the panel."""
        self._cancel_thread()
        self._lat = self._lng = None
        self._label = ""
        self._set_empty_state()

    def has_pin(self) -> bool:
        return self._lat is not None and self._lng is not None

    def current_coords(self) -> Optional[tuple[float, float]]:
        if self._lat is None or self._lng is None:
            return None
        return self._lat, self._lng

    # ── Internals ───────────────────────────────────────────────────────────

    def _refresh_clicked(self):
        if not self.has_pin():
            self._lbl_status.setText("No pin set — search an address first.")
            return
        self._reset_data_rows()
        self._start_fetch()

    def _set_empty_state(self):
        self._lbl_label.setText("—")
        self._lbl_coords.setText("—")
        self._lbl_status.setText("Drop a pin to auto-fill site data.")
        self._reset_data_rows()

    def _reset_data_rows(self):
        self._lbl_zone.setText("—")
        self._lbl_hard_src.setText("")
        self._lbl_gdd.setText("—")
        self._lbl_frost.setText("—")
        self._lbl_ecoregion.setText("—")
        self._lbl_elev.setText("—")
        self._lbl_slope.setText("—")
        self._lbl_aspect.setText("—")
        self._lbl_elev_src.setText("")
        self._lbl_rain_annual.setText("—")
        self._lbl_rain_monthly.setText("—")
        self._lbl_rain_src.setText("")
        self._lbl_soil_ph.setText("—")
        self._lbl_soil_texture.setText("—")
        self._lbl_soil_mix.setText("—")
        self._lbl_soil_depth.setText("—")
        self._lbl_soil_src.setText("")

    def _start_fetch(self):
        self._cancel_thread()
        if self._lat is None or self._lng is None:
            return
        self._lbl_status.setText("Fetching site data…")

        thread = QThread(self)
        worker = _SiteFetchWorker(self._lat, self._lng)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._lbl_status.setText)
        worker.hardiness.connect(self._on_hardiness)
        worker.elevation.connect(self._on_elevation)
        worker.rainfall.connect(self._on_rainfall)
        worker.soil.connect(self._on_soil)
        worker.climate.connect(self._on_climate)
        worker.ecoregion.connect(self._on_ecoregion)
        worker.fast_ready.connect(self._on_fast_ready)
        worker.finished.connect(self._on_finished)

        # Auto-teardown chain: when the worker emits finished, quit the
        # thread's event loop, then both objects schedule themselves for
        # deletion once the thread has actually stopped running. We never
        # delete a thread synchronously while it could still be executing
        # — that race is what crashed the app on Clear pin.
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _cancel_thread(self):
        """Detach the in-flight site-data worker without blocking.

        Sets the worker's cancelled flag, asks the thread's event loop to
        quit, and drops our references. The auto-teardown chain wired in
        ``_start_fetch`` finishes the cleanup once the worker actually
        returns. Disconnecting the worker's signals beforehand stops the
        cancelled run from clobbering the UI with stale results.
        """
        worker = self._worker
        thread = self._thread
        self._worker = None
        self._thread = None

        if worker is not None:
            try:
                worker.cancel()
            except Exception:
                pass
            for sig_name in ("progress", "hardiness", "elevation",
                             "rainfall", "soil", "climate", "ecoregion",
                             "fast_ready", "finished"):
                try:
                    getattr(worker, sig_name).disconnect()
                except (TypeError, RuntimeError):
                    pass
        if _safe_is_running(thread):
            try:
                thread.quit()
            except RuntimeError:
                pass

    def _cleanup_thread(self):
        # Retained for backward-compat with any external callers; the
        # auto-teardown chain in _start_fetch now handles deletion.
        self._worker = None
        self._thread = None

    # ── Slot handlers (UI thread) ───────────────────────────────────────────

    def _on_hardiness(self, data):
        if not data:
            self._lbl_zone.setText("Unavailable")
            return
        zone = data.get("zone")
        zone_text = f"Zone {zone}" if zone is not None else "Unknown"
        if "avg_extreme_min_c" in data:
            zone_text += f"  ({data['avg_extreme_min_c']:.1f} °C avg min)"
        self._lbl_zone.setText(zone_text)
        self._lbl_hard_src.setText(data.get("source", ""))

    def _on_ecoregion(self, data):
        """Surface the auto-detected ecoregion in the readout and write
        it to the QSettings key the plant panel checks so its filter
        dropdown pre-populates. Only writes the auto key — the user's
        explicit choice (``plant_panel/ab_ecoregion``) is untouched."""
        if not data:
            self._lbl_ecoregion.setText("Outside known regions")
            return
        label = data.get("label") or data.get("key") or "—"
        self._lbl_ecoregion.setText(f"{label}  (auto)")
        # Stash the auto-detected key for the plant panel to pick up
        # on its next refresh. Separate key from the user's explicit
        # choice so a manual override survives a pin move.
        try:
            from PyQt6.QtCore import QSettings
            QSettings().setValue("plant_panel/ab_ecoregion_auto",
                                 data.get("key") or "")
        except Exception:
            pass

    def _on_climate(self, data):
        """Update the GDD₅ + frost-window rows. ``data`` is the dict
        returned by ``src.climate.get_climate_summary`` or ``None`` on
        fetch failure."""
        if not data:
            self._lbl_gdd.setText("Unavailable (offline?)")
            self._lbl_frost.setText("—")
            return
        from src.climate import doy_to_date_label
        gdd = data.get("gdd5_mean")
        if gdd is not None:
            cached_marker = " (cached)" if data.get("cached") else ""
            self._lbl_gdd.setText(
                f"{int(round(gdd))}  ({data.get('years_used', 0)}-yr avg)"
                + cached_marker
            )
        else:
            self._lbl_gdd.setText("—")
        last = data.get("last_spring_frost_doy")
        first = data.get("first_fall_frost_doy")
        free = data.get("frost_free_days")
        if last is not None and first is not None:
            self._lbl_frost.setText(
                f"{doy_to_date_label(last)} → {doy_to_date_label(first)}"
                + (f"  ({free} days)" if free is not None else "")
            )
        else:
            self._lbl_frost.setText("—")

    def _on_elevation(self, data):
        if not data:
            self._lbl_elev.setText("Unavailable")
            return
        self._lbl_elev.setText(f"{data['elevation_m']:.1f} m")
        # V1.37: slope_pct may be None when the pin sits on water — the
        # DEM omits the neighbours we'd need for the gradient. Show "—"
        # rather than throwing on the format call.
        slope_pct = data.get("slope_pct")
        slope_deg = data.get("slope_deg")
        if slope_pct is not None and slope_deg is not None:
            self._lbl_slope.setText(f"{slope_pct:.2f} %  ({slope_deg:.2f}°)")
        else:
            self._lbl_slope.setText("—")
        if data.get("aspect_deg") is not None:
            self._lbl_aspect.setText(
                f"{data['aspect']}  ({data['aspect_deg']:.0f}°)"
            )
        else:
            self._lbl_aspect.setText(data.get("aspect", "—"))
        self._lbl_elev_src.setText(data.get("source", ""))

    def _on_rainfall(self, data):
        if not data:
            self._lbl_rain_annual.setText("Unavailable")
            return
        years = data.get("years_used", "?")
        self._lbl_rain_annual.setText(
            f"{data['annual_mm']:.0f} mm  (over {years} years)"
        )
        months = data.get("monthly_mm") or []
        if len(months) == 12:
            names = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
            row = "  ".join(f"{n}:{int(round(v))}" for n, v in zip(names, months))
            self._lbl_rain_monthly.setText(row)
        self._lbl_rain_src.setText(data.get("source", ""))

    def _on_soil(self, data):
        if not data:
            self._lbl_soil_ph.setText("Unavailable")
            return
        s = data.get("summary") or {}
        ph = s.get("ph_top")
        self._lbl_soil_ph.setText(f"{ph:.1f}" if ph is not None else "—")
        self._lbl_soil_texture.setText(s.get("texture_class") or "—")
        sand = s.get("sand_pct_top")
        silt = s.get("silt_pct_top")
        clay = s.get("clay_pct_top")
        if None not in (sand, silt, clay):
            self._lbl_soil_mix.setText(
                f"{sand:.0f} / {silt:.0f} / {clay:.0f} %"
            )
        depth = s.get("max_reported_depth_cm")
        if depth:
            self._lbl_soil_depth.setText(f"{depth} cm reported")
        self._lbl_soil_src.setText(data.get("source", ""))

    def _on_fast_ready(self):
        """The non-climate fetches are in — flip the user-visible status
        to ready immediately, even though the slower climate call is
        still running in the worker. The climate row will update from
        '—' when its signal arrives."""
        self._lbl_status.setText("Site data ready.")

    def _on_finished(self, result: dict):
        """The worker has finished every step including the slower
        climate fetch. The status text is already 'ready' from
        ``_on_fast_ready``; this signal just propagates the full
        result dict to the rest of the app."""
        self.site_data_updated.emit(result)

    # ── Auto-generated slope analysis ───────────────────────────────────────

    def _pick_auto_color(self):
        color = QColorDialog.getColor(
            QColor(self._auto_color), self, "Contour colour"
        )
        if color.isValid():
            self._auto_color = color.name()
            self._auto_color_btn.setStyleSheet(
                f"background: {self._auto_color}; "
                f"border: 1px solid #4a7a4a; border-radius: 4px;"
            )

    def _on_auto_terrain_generate(self):
        idx = self._auto_area_source.currentIndex()
        area = ("viewport", "draw", "boundary")[idx]
        self.auto_terrain_requested.emit({
            "area_source":         area,
            "interval_m":          self._auto_interval.value(),
            "resolution_m":        self._auto_resolution.value(),
            "want_contours":       self._auto_want_contours.isChecked(),
            "want_slope_overlay":  self._auto_want_slope.isChecked(),
            "show_labels":         self._auto_show_labels.isChecked(),
            "color":               self._auto_color,
            "opacity":             self._auto_opacity_slider.value() / 100.0,
        })
        self._auto_status.setText("Queued — preparing area selection…")

    def set_auto_terrain_status(self, text: str):
        """Called from MainWindow with progress / queue / result info."""
        self._auto_status.setText(text)

    # ── Shade overlay (V1.51) ──────────────────────────────────────────────

    def _build_shade_section(self, parent_layout):
        """Show-shade button + opacity, plus season & time-of-day selectors that
        drive the time-aware shade overlay (src/shade.py + ShadeWorker)."""
        from src.solar import KEY_DATES
        box = QGroupBox("Shade map")
        box.setToolTip("Cast shade from existing trees/buildings and the "
                       "design's own canopy, at a chosen season and time of day.")
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        season_row = QHBoxLayout()
        season_row.addWidget(QLabel("Season:"))
        self._shade_season = QComboBox()
        # data = (month, day). V1.58: the overlay always shows a crisp single
        # instant (a real date + the time slider) so shadows track the sun and
        # match each building's outline — no season-averaged "blob". Planting-zone
        # classification still uses the season average internally (separate path).
        for label, d in KEY_DATES.items():
            self._shade_season.addItem(label, (d.month, d.day))
        self._shade_season.setCurrentIndex(0)          # Summer Solstice
        self._shade_season.currentIndexChanged.connect(self._on_shade_season_changed)
        season_row.addWidget(self._shade_season)
        v.addLayout(season_row)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Time:"))
        self._shade_hour = QSlider(Qt.Orientation.Horizontal)
        # Minutes since midnight in 15-min steps, so shadows sweep smoothly
        # rather than jumping by whole hours. 5 AM – 9 PM local solar by default.
        self._shade_hour.setRange(5 * 60, 21 * 60)
        self._shade_hour.setSingleStep(15)
        self._shade_hour.setPageStep(60)
        self._shade_hour.setValue(15 * 60)      # mid-afternoon: long, clearly
                                                # directional shadows by default
        self._shade_hour_lbl = QLabel("15:00")
        self._shade_hour.valueChanged.connect(
            lambda v: self._shade_hour_lbl.setText(f"{v // 60:02d}:{v % 60:02d}"))
        # Scrub the slider to sweep shadows across the day. A short debounce
        # coalesces rapid drags into one recompute, and only a real day (not
        # "Typical") drives a live overlay — the averaged view has no time.
        self._shade_scrub = QTimer(self)
        self._shade_scrub.setSingleShot(True)
        self._shade_scrub.setInterval(180)
        self._shade_scrub.timeout.connect(self._emit_shade_for_scrub)
        self._shade_hour.valueChanged.connect(self._on_shade_hour_scrubbed)
        time_row.addWidget(self._shade_hour)
        time_row.addWidget(self._shade_hour_lbl)
        v.addLayout(time_row)

        opa_row = QHBoxLayout()
        opa_row.addWidget(QLabel("Opacity:"))
        self._shade_opacity = QSlider(Qt.Orientation.Horizontal)
        self._shade_opacity.setRange(0, 100)
        self._shade_opacity.setValue(50)
        self._shade_opacity.valueChanged.connect(
            lambda val: self.shade_opacity.emit(val / 100.0))
        opa_row.addWidget(self._shade_opacity)
        v.addLayout(opa_row)

        btn_row = QHBoxLayout()
        btn_show = QPushButton("Show shade")
        btn_show.setStyleSheet(_BTN_PRIMARY)
        btn_show.clicked.connect(self._on_show_shade)
        btn_row.addWidget(btn_show)
        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet(_BTN_SECONDARY)
        btn_clear.clicked.connect(self.shade_cleared.emit)
        btn_row.addWidget(btn_clear)
        v.addLayout(btn_row)

        # Classify each planting cell as full sun / partial / full shade from
        # the season-average grid and cache the tags (src/db/shade_zones.py) so
        # plant matching can read them without recomputing.
        btn_classify = QPushButton("Classify planting zones")
        btn_classify.setStyleSheet(_BTN_SECONDARY)
        btn_classify.setToolTip(
            "Tag every spot full sun / partial shade / full shade from the "
            "season-average shade, and cache it for plant matching.")
        btn_classify.clicked.connect(self.shade_zones_requested.emit)
        v.addWidget(btn_classify)

        self._shade_zone_status = QLabel("")
        self._shade_zone_status.setWordWrap(True)
        self._shade_zone_status.setStyleSheet("color: #a5d6a7; font-size: 11px;")
        v.addWidget(self._shade_zone_status)

        parent_layout.addWidget(box)

    def set_shade_zone_status(self, text: str):
        """Show a short result line under the Classify button."""
        if hasattr(self, "_shade_zone_status"):
            self._shade_zone_status.setText(text)

    def _on_show_shade(self):
        season = self._shade_season.currentData()    # (month, day) or None
        when = None
        if season is not None:
            v = self._shade_hour.value()             # minutes since midnight
            when = (season[0], season[1], v // 60, v % 60)
        self.shade_requested.emit({"when": when})

    def _on_shade_season_changed(self, _idx):
        """Clamp the time slider to the chosen day's sunrise→sunset so the user
        scrubs only through real daylight, and label the ends. Falls back to the
        generic 5 AM–9 PM range until a site location is known."""
        season = self._shade_season.currentData()
        if season is None or self._lat is None or self._lng is None:
            self._shade_hour.setRange(5 * 60, 21 * 60)
            return
        try:
            from datetime import date
            from src.solar import sunrise_sunset
            sr, ss = sunrise_sunset(self._lat, self._lng,
                                    date(2025, season[0], season[1]))
            lo = max(0, int(sr * 60))                  # floor sunrise (minutes)
            hi = min(24 * 60 - 1, int(ss * 60) + 15)   # a touch past sunset
            if hi <= lo:
                lo, hi = 5 * 60, 21 * 60
        except Exception:  # noqa: BLE001 — fall back to the generic window
            lo, hi = 5 * 60, 21 * 60
        cur = self._shade_hour.value()
        self._shade_hour.setRange(lo, hi)
        self._shade_hour.setValue(min(max(cur, lo), hi))

    def _on_shade_hour_scrubbed(self, _h):
        """Slider moved — debounce a live overlay recompute (real days only)."""
        if self._shade_season.currentData() is None:
            return                          # averaged view has no time-of-day
        self._shade_scrub.start()           # (re)arm the debounce

    def _emit_shade_for_scrub(self):
        season = self._shade_season.currentData()
        if season is None:
            return
        v = self._shade_hour.value()                 # minutes since midnight
        self.shade_requested.emit(
            {"when": (season[0], season[1], v // 60, v % 60)})

    # ── Existing shade casters: mark/draw trees & buildings ────────────────
    # Relocated from the Structures panel (V1.59) so all shade casters — drawn,
    # marked, and OSM-imported — live together on the Shade sub-tab. Reuses the
    # structure/shape placement pipeline via the panel's signals.

    def _build_existing_features_section(self, layout):
        from src.db.structures import EXISTING_TREE_ID, EXISTING_BUILDING_ID
        box = QGroupBox("Existing features (trees & buildings)")
        box.setStyleSheet(_GROUP_STYLE)
        box.setToolTip(
            "Mark trees and buildings already on your property so the design "
            "generator places shade-loving plants in their cast shade."
        )
        vb = QVBoxLayout(box)
        vb.setContentsMargins(6, 6, 6, 6)
        vb.setSpacing(4)

        hint = QLabel("Set height/size, click a button, then click the map.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #90a4ae; font-size: 11px;")
        vb.addWidget(hint)

        dims = QHBoxLayout()
        dims.addWidget(QLabel("Height (m):"))
        self._exist_height = QDoubleSpinBox()
        self._exist_height.setRange(1.0, 60.0)
        self._exist_height.setSingleStep(0.5)
        self._exist_height.setValue(6.0)
        dims.addWidget(self._exist_height)
        dims.addWidget(QLabel("Size (m):"))
        self._exist_size = QDoubleSpinBox()
        self._exist_size.setRange(0.5, 40.0)
        self._exist_size.setSingleStep(0.5)
        self._exist_size.setValue(6.0)
        self._exist_size.setToolTip("Canopy diameter (tree) or footprint width "
                                    "(building).")
        dims.addWidget(self._exist_size)
        vb.addLayout(dims)

        btns = QHBoxLayout()
        btn_tree = QPushButton("🌳 Mark tree")
        btn_tree.clicked.connect(lambda: self._on_mark_existing(EXISTING_TREE_ID))
        btn_bldg = QPushButton("🏠 Mark building")
        btn_bldg.clicked.connect(
            lambda: self._on_mark_existing(EXISTING_BUILDING_ID))
        btns.addWidget(btn_tree)
        btns.addWidget(btn_bldg)
        vb.addLayout(btns)

        draw_btns = QHBoxLayout()
        btn_tree_outline = QPushButton("🌲 Draw tree canopy")
        btn_tree_outline.setToolTip(
            "Draw a tree canopy outline (click points, double-click to finish). "
            "Uses the height above; casts a tapering tree shadow.")
        btn_tree_outline.clicked.connect(self._on_draw_tree_canopy)
        draw_btns.addWidget(btn_tree_outline)

        btn_outline = QPushButton("✏️ Draw building")
        btn_outline.setToolTip(
            "Draw the building's outline (click corners, double-click to "
            "finish). Uses the height above; casts an accurate shadow.")
        btn_outline.clicked.connect(self._on_draw_building_footprint)
        draw_btns.addWidget(btn_outline)
        vb.addLayout(draw_btns)

        layout.addWidget(box)

    def _on_mark_existing(self, feature_id: str):
        """Emit a placement request for an existing tree/building, reusing the
        structure placement pipeline (the controller routes the reserved id to
        an existing_* feature)."""
        from src.db.structures import existing_feature_def
        payload = existing_feature_def(
            feature_id, size_m=self._exist_size.value(),
            height_m=self._exist_height.value())
        self.place_structure_requested.emit(payload)

    def _on_draw_building_footprint(self):
        """Start shape-draw pre-set as a building footprint at the entered
        height, so the finished polygon becomes a shade-casting canopy."""
        self.place_shape_requested.emit({
            "shape_type": "Building footprint",
            "label": "Building",
            "fill_color": "#8d6e63",
            "stroke_color": "#5d4037",
            "fill_opacity": 0.3,
            "dash_array": "",
            "height_m": self._exist_height.value(),
        })

    def _on_draw_tree_canopy(self):
        """Start shape-draw pre-set as a tree canopy at the entered height; the
        finished polygon becomes a tapering tree shade caster (shape_type
        'Tree canopy' → caster_kind='tree' in the controller)."""
        self.place_shape_requested.emit({
            "shape_type": "Tree canopy",
            "label": "Tree",
            "fill_color": "#44cc00",
            "stroke_color": "#2e7d32",
            "fill_opacity": 0.3,
            "dash_array": "",
            "height_m": self._exist_height.value(),
        })

    # ── Existing features from OpenStreetMap (V1.51) ───────────────────────

    def _build_osm_section(self, parent_layout):
        box = QGroupBox("Existing features (OpenStreetMap)")
        box.setToolTip("Import nearby buildings and mapped trees from "
                       "OpenStreetMap so the design accounts for their shade "
                       "and keeps plants off them. Anything missing can still "
                       "be marked by hand in the Structures tab.")
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 6, 6, 6)
        btn = QPushButton("Import from OpenStreetMap")
        btn.setStyleSheet(_BTN_SECONDARY)
        btn.clicked.connect(self.osm_import_requested.emit)
        v.addWidget(btn)

        # Import shade-casting footprints from a height raster (nDSM GeoTIFF) —
        # the whiteboxtools-style path. Only shown when a backend is available
        # (numpy + shapely present), so a minimal install hides it.
        from src.footprint_extract import extraction_available
        if extraction_available():
            btn_tiff = QPushButton("Import footprints (nDSM GeoTIFF)…")
            btn_tiff.setStyleSheet(_BTN_SECONDARY)
            btn_tiff.setToolTip(
                "Vectorize building/canopy footprints (with heights) from a "
                "normalized-DSM GeoTIFF (DSM minus DEM). They land as "
                "shade-casting footprints you can edit or remove.")
            btn_tiff.clicked.connect(self._on_pick_footprint_tiff)
            v.addWidget(btn_tiff)

        self._osm_status = QLabel("")
        self._osm_status.setWordWrap(True)
        self._osm_status.setStyleSheet("color: #ffcc80; font-size: 11px;")
        v.addWidget(self._osm_status)
        parent_layout.addWidget(box)

    def _on_pick_footprint_tiff(self):
        """Pick an nDSM GeoTIFF and emit the import request with its path."""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Import footprints from nDSM GeoTIFF", "",
            "GeoTIFF (*.tif *.tiff);;All files (*)")
        if path:
            self.footprint_import_requested.emit(path)

    def set_osm_status(self, text: str):
        self._osm_status.setText(text)

    # ── Manual contour drawing (UI removed V1.37) ──────────────────────────
    # Helpers below are intentional no-ops kept as placeholders so any
    # stray callsite — e.g. a saved JSON pulled from an older session —
    # finds the method names and doesn't crash. To re-enable manual
    # contour drawing, restore the QGroupBox section in `_build_ui`
    # and revert these stubs to the pre-V1.37 implementation.

    def _pick_contour_color(self):
        return

    def _on_draw_contour(self):
        return

    # ── Terrain Data section ───────────────────────────────────────────────

    def _build_terrain_data_section(self, layout):
        box = QGroupBox("Terrain Data (offline)")
        box.setStyleSheet(_GROUP_STYLE)
        vl = QVBoxLayout(box)
        vl.setSpacing(6)

        note = QLabel(
            "Download the full City of Edmonton 0.5 m LiDAR contour\n"
            "dataset for instant offline access. One-time download\n"
            "(~1 GB unpacked). SRTM data outside Edmonton is cached\n"
            "automatically as you use it."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #90a4ae; font-size: 11px;")
        vl.addWidget(note)

        self._terrain_status_lbl = QLabel("Checking…")
        self._terrain_status_lbl.setWordWrap(True)
        self._terrain_status_lbl.setStyleSheet("color: #c8e6c9; font-size: 11px;")
        vl.addWidget(self._terrain_status_lbl)

        self._terrain_storage_lbl = QLabel("")
        self._terrain_storage_lbl.setStyleSheet("color: #78909c; font-size: 10px;")
        vl.addWidget(self._terrain_storage_lbl)

        self._terrain_progress = QProgressBar()
        self._terrain_progress.setRange(0, 0)   # indeterminate
        self._terrain_progress.setVisible(False)
        self._terrain_progress.setStyleSheet(
            "QProgressBar { border: 1px solid #2e4a2e; border-radius: 3px;"
            " background: #0d1f0d; height: 10px; }"
            "QProgressBar::chunk { background: #43a047; border-radius: 2px; }"
        )
        vl.addWidget(self._terrain_progress)

        btn_row = QHBoxLayout()
        self._terrain_dl_btn = QPushButton("Download Edmonton Data")
        self._terrain_dl_btn.setStyleSheet(_BTN_PRIMARY)
        self._terrain_dl_btn.clicked.connect(self._on_download_clicked)
        btn_row.addWidget(self._terrain_dl_btn)

        self._terrain_cancel_btn = QPushButton("Cancel")
        self._terrain_cancel_btn.setStyleSheet(_BTN_SECONDARY)
        self._terrain_cancel_btn.setVisible(False)
        btn_row.addWidget(self._terrain_cancel_btn)
        vl.addLayout(btn_row)

        layout.addWidget(box)
        self._refresh_terrain_status()

    def _on_download_clicked(self):
        self._terrain_dl_btn.setEnabled(False)
        self._terrain_cancel_btn.setVisible(True)
        self._terrain_progress.setVisible(True)
        self._terrain_status_lbl.setText("Starting download…")
        self.download_edmonton_requested.emit()

    def set_download_progress(self, features_stored: int, page_num: int, text: str):
        self._terrain_status_lbl.setText(text)
        self._terrain_storage_lbl.setText(self._storage_text())

    def set_terrain_status(self):
        self._terrain_dl_btn.setEnabled(True)
        self._terrain_cancel_btn.setVisible(False)
        self._terrain_progress.setVisible(False)
        self._refresh_terrain_status()

    def _refresh_terrain_status(self):
        try:
            from src.terrain_store import TerrainStore
            store = TerrainStore()
            if store.has_edmonton_data():
                count = store.get_edmonton_feature_count()
                self._terrain_status_lbl.setText(
                    f"Edmonton: {count:,} features — offline ready"
                )
            else:
                self._terrain_status_lbl.setText("No offline Edmonton data.")
            self._terrain_storage_lbl.setText(self._storage_text())
        except Exception:
            self._terrain_status_lbl.setText("No offline Edmonton data.")
            self._terrain_storage_lbl.setText("")

    def _storage_text(self) -> str:
        try:
            from src.terrain_store import TerrainStore
            mb = TerrainStore().db_size_mb()
            return f"Storage used: {mb:.1f} MB" if mb > 0 else ""
        except Exception:
            return ""

    # ── Address search (Nominatim) ─────────────────────────────────────────

    def _on_address_text_changed(self, text: str):
        """Debounced typeahead — fire a geocode after 350 ms of idle."""
        # Cancel any pending debounce timer.
        if self._geo_debounce is None:
            self._geo_debounce = QTimer(self)
            self._geo_debounce.setSingleShot(True)
            self._geo_debounce.timeout.connect(self._on_address_search_typeahead)
        self._geo_debounce.stop()
        if len((text or "").strip()) < 3:
            self._addr_results.clear()
            self._addr_results.setVisible(False)
            return
        self._geo_debounce.start(350)

    def _on_address_search_typeahead(self):
        self._run_geocode(self._addr_input.text())

    def _on_address_search(self):
        # Manual submit (Enter / Find) — show "Searching…" feedback.
        q = self._addr_input.text().strip()
        if not q:
            return
        self._lbl_status.setText("Searching…")
        self._run_geocode(q)

    def _run_geocode(self, query: str):
        # Cancel any in-flight geocode before starting a new one.
        self._cancel_geocode()
        # Bias the search against the map's current view centre when
        # available. Falls through to the all-of-Alberta query when the
        # panel hasn't been wired to a map widget yet (e.g. headless
        # tests).
        near = None
        if self._map_widget is not None:
            near = getattr(self._map_widget, "last_center", None)
        thread = QThread(self)
        worker = _GeocodeWorker(query, near=near)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.results.connect(self._on_geocode_results)
        worker.failed.connect(
            lambda msg: self._lbl_status.setText(f"Search failed: {msg}")
        )
        # Auto-teardown chain — see _start_fetch for why we don't delete
        # threads synchronously.
        worker.results.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.results.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._geo_thread = thread
        self._geo_worker = worker
        thread.start()

    def _on_geocode_results(self, hits: list):
        self._addr_results.clear()
        if not hits:
            self._addr_results.setVisible(False)
            self._lbl_status.setText("No Alberta results.")
            return
        for h in hits:
            item = QListWidgetItem(h["label"])
            item.setData(Qt.ItemDataRole.UserRole, (h["lat"], h["lng"]))
            self._addr_results.addItem(item)
        self._addr_results.setVisible(True)
        self._lbl_status.setText("")

    def _on_address_pick(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        lat, lng = data
        label = item.text()
        self._addr_input.setText(label)
        self._addr_results.clear()
        self._addr_results.setVisible(False)
        self.address_resolved.emit(float(lat), float(lng), label)

    def _cancel_geocode(self):
        """Detach the in-flight geocode worker without blocking — see
        ``_cancel_thread`` for the rationale."""
        worker = self._geo_worker
        thread = self._geo_thread
        self._geo_worker = None
        self._geo_thread = None
        if worker is not None:
            for sig_name in ("results", "failed"):
                try:
                    getattr(worker, sig_name).disconnect()
                except (TypeError, RuntimeError):
                    pass
        if _safe_is_running(thread):
            try:
                thread.quit()
            except RuntimeError:
                pass

    def _cleanup_geocode(self):
        # Retained for backward-compat; teardown is now driven by the
        # signal chain wired up in _run_geocode.
        self._geo_worker = None
        self._geo_thread = None


# ── Styling ──────────────────────────────────────────────────────────────────

_GROUP_STYLE = (
    "QGroupBox { border: 1px solid #2e4a2e; border-radius: 4px; "
    "margin-top: 10px; padding-top: 12px; }"
    "QGroupBox::title { color: #a5d6a7; subcontrol-origin: margin; left: 8px; }"
)

_BTN_PRIMARY = (
    "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047;"
    " border-radius: 4px; padding: 6px; font-weight: bold; }"
    "QPushButton:hover { background: #388e3c; }"
)

_BTN_SECONDARY = (
    "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a;"
    " border-radius: 4px; padding: 6px; }"
    "QPushButton:hover { background: #455a64; }"
)
