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
    QListWidget, QListWidgetItem,
)


# ── Background fetcher ───────────────────────────────────────────────────────

class _SiteFetchWorker(QObject):
    """Runs in its own QThread; emits a signal per dataset as it completes."""

    progress  = pyqtSignal(str)               # status message
    rainfall  = pyqtSignal(object)            # dict | None
    soil      = pyqtSignal(object)
    elevation = pyqtSignal(object)
    hardiness = pyqtSignal(object)
    finished  = pyqtSignal(dict)              # combined result dict

    def __init__(self, lat: float, lng: float):
        super().__init__()
        self.lat, self.lng = lat, lng
        self._cancelled = False

    @pyqtSlot()
    def run(self):
        # Imported lazily so unit tests don't pull urllib at import time.
        from src.property_data import (
            fetch_rainfall, fetch_soil, fetch_elevation, fetch_hardiness,
        )
        out = {"lat": self.lat, "lng": self.lng}

        steps = [
            ("hardiness", "Looking up hardiness zone…",       fetch_hardiness, self.hardiness),
            ("elevation", "Sampling Copernicus DEM…",         fetch_elevation, self.elevation),
            ("rainfall",  "Computing ERA5-Land rainfall…",    fetch_rainfall,  self.rainfall),
            ("soil",      "Querying SoilGrids…",              fetch_soil,      self.soil),
        ]
        for key, msg, fn, sig in steps:
            if self._cancelled:
                break
            self.progress.emit(msg)
            try:
                value = fn(self.lat, self.lng)
            except Exception:
                value = None
            out[key] = value
            sig.emit(value)

        self.finished.emit(out)

    def cancel(self):
        self._cancelled = True


# ── Geocode worker (Nominatim, Alberta-bounded) ─────────────────────────────

class _GeocodeWorker(QObject):
    """Runs a single forward-geocode request off the UI thread."""

    results = pyqtSignal(list)        # list[{label, lat, lng}]
    failed  = pyqtSignal(str)         # error message

    def __init__(self, query: str):
        super().__init__()
        self._query = query

    @pyqtSlot()
    def run(self):
        try:
            from src.property_data import geocode_alberta
            hits = geocode_alberta(self._query) or []
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
        self._auto_color = "#5d4037"
        self._contour_color = "#795548"
        self._build_ui()
        self._set_empty_state()

    # ── Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

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

        # ── Hardiness ────────────────────────────────────────────────
        # Order: zone → rainfall → soil sit directly under the pin so
        # the most-asked-for site stats are visible without scrolling.
        self._hard_box = QGroupBox("Hardiness zone")
        self._hard_box.setStyleSheet(_GROUP_STYLE)
        hl = QFormLayout(self._hard_box)
        self._lbl_zone   = QLabel("—")
        self._lbl_zone.setStyleSheet("color: #c8e6c9; font-weight: bold; font-size: 14px;")
        self._lbl_hard_src = QLabel("")
        self._lbl_hard_src.setStyleSheet("color: #78909c; font-size: 10px;")
        self._lbl_hard_src.setWordWrap(True)
        hl.addRow("Zone:", self._lbl_zone)
        hl.addRow("Source:", self._lbl_hard_src)
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

        # ── Slope analysis (area) ───────────────────────────────────
        # Now hosts the single-point Elevation/slope readout (top), the
        # auto-generated contour/ramp controls (middle), and the manual
        # Contour-line drawing controls (bottom — formerly on the
        # Analysis tab).
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

        # ── Manual contour-line drawing (moved from Analysis tab) ───
        contour_header = QLabel("<b>Draw contour line (manual)</b>")
        contour_header.setStyleSheet("color: #a5d6a7; margin-top: 6px;")
        slope_layout.addWidget(contour_header)

        contour_info = QLabel(
            "Draw manual contour lines to indicate terrain slope. Helps\n"
            "place swales, ponds, and water features. Click points on the\n"
            "map to draw, double-click to finish."
        )
        contour_info.setWordWrap(True)
        contour_info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        slope_layout.addWidget(contour_info)

        contour_form = QFormLayout()
        contour_form.setContentsMargins(0, 0, 0, 0)

        self._contour_elevation = QDoubleSpinBox()
        self._contour_elevation.setRange(0, 2000)
        self._contour_elevation.setSingleStep(0.5)
        self._contour_elevation.setValue(0)
        self._contour_elevation.setSuffix(" m")
        contour_form.addRow("Elevation:", self._contour_elevation)

        self._contour_interval = QDoubleSpinBox()
        self._contour_interval.setRange(0.1, 10.0)
        self._contour_interval.setSingleStep(0.5)
        self._contour_interval.setValue(1.0)
        self._contour_interval.setSuffix(" m")
        contour_form.addRow("Interval:", self._contour_interval)

        cc_row = QHBoxLayout()
        self._contour_color_btn = QPushButton()
        self._contour_color_btn.setFixedSize(28, 28)
        self._contour_color_btn.setStyleSheet(
            f"background: {self._contour_color}; border: 1px solid #4a7a4a; "
            f"border-radius: 4px;"
        )
        self._contour_color_btn.clicked.connect(self._pick_contour_color)
        cc_row.addWidget(self._contour_color_btn)
        cc_row.addStretch()
        contour_form.addRow("Color:", cc_row)

        self._contour_labels = QCheckBox("Show elevation labels")
        self._contour_labels.setChecked(True)
        contour_form.addRow(self._contour_labels)

        self._contour_slope_arrows = QCheckBox("Show downhill arrows")
        self._contour_slope_arrows.setChecked(True)
        self._contour_slope_arrows.setToolTip(
            "Show arrows indicating downhill direction between contour lines"
        )
        contour_form.addRow(self._contour_slope_arrows)

        slope_layout.addLayout(contour_form)

        contour_btn_row = QHBoxLayout()
        btn_draw_contour = QPushButton("Draw Contour Line")
        btn_draw_contour.setStyleSheet(
            "QPushButton { background: #5d4037; color: #efebe9; "
            "border: 1px solid #795548; border-radius: 4px; padding: 6px; "
            "font-weight: bold; }"
            "QPushButton:hover { background: #6d4c41; }"
        )
        btn_draw_contour.clicked.connect(self._on_draw_contour)
        contour_btn_row.addWidget(btn_draw_contour)

        btn_clear_contour = QPushButton("Clear All")
        btn_clear_contour.setStyleSheet(_BTN_SECONDARY)
        btn_clear_contour.clicked.connect(self.contour_cleared.emit)
        contour_btn_row.addWidget(btn_clear_contour)
        slope_layout.addLayout(contour_btn_row)

        layout.addWidget(self._slope_box)

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

        self._thread = QThread(self)
        self._worker = _SiteFetchWorker(self._lat, self._lng)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._lbl_status.setText)
        self._worker.hardiness.connect(self._on_hardiness)
        self._worker.elevation.connect(self._on_elevation)
        self._worker.rainfall.connect(self._on_rainfall)
        self._worker.soil.connect(self._on_soil)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _cancel_thread(self):
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(500)
        self._cleanup_thread()

    def _cleanup_thread(self):
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
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

    def _on_elevation(self, data):
        if not data:
            self._lbl_elev.setText("Unavailable")
            return
        self._lbl_elev.setText(f"{data['elevation_m']:.1f} m")
        self._lbl_slope.setText(
            f"{data['slope_pct']:.2f} %  ({data['slope_deg']:.2f}°)"
        )
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

    def _on_finished(self, result: dict):
        self._lbl_status.setText("Site data ready.")
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

    # ── Manual contour drawing ─────────────────────────────────────────────

    def _pick_contour_color(self):
        color = QColorDialog.getColor(
            QColor(self._contour_color), self, "Contour color"
        )
        if color.isValid():
            self._contour_color = color.name()
            self._contour_color_btn.setStyleSheet(
                f"background: {self._contour_color}; "
                f"border: 1px solid #4a7a4a; border-radius: 4px;"
            )

    def _on_draw_contour(self):
        self.contour_requested.emit({
            "elevation_m":       self._contour_elevation.value(),
            "interval_m":        self._contour_interval.value(),
            "color":             self._contour_color,
            "show_labels":       self._contour_labels.isChecked(),
            "show_slope_arrows": self._contour_slope_arrows.isChecked(),
        })
        # Auto-increment elevation for next contour line.
        self._contour_elevation.setValue(
            self._contour_elevation.value() + self._contour_interval.value()
        )

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
        self._geo_thread = QThread(self)
        self._geo_worker = _GeocodeWorker(query)
        self._geo_worker.moveToThread(self._geo_thread)
        self._geo_thread.started.connect(self._geo_worker.run)
        self._geo_worker.results.connect(self._on_geocode_results)
        self._geo_worker.failed.connect(
            lambda msg: self._lbl_status.setText(f"Search failed: {msg}")
        )
        self._geo_worker.results.connect(self._geo_thread.quit)
        self._geo_worker.failed.connect(self._geo_thread.quit)
        self._geo_thread.finished.connect(self._cleanup_geocode)
        self._geo_thread.start()

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
        if self._geo_thread is not None and self._geo_thread.isRunning():
            self._geo_thread.quit()
            self._geo_thread.wait(200)
        self._cleanup_geocode()

    def _cleanup_geocode(self):
        if self._geo_worker is not None:
            self._geo_worker.deleteLater()
            self._geo_worker = None
        if self._geo_thread is not None:
            self._geo_thread.deleteLater()
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
