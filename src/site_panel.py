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

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QFrame, QGroupBox, QScrollArea,
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


# ── Panel widget ─────────────────────────────────────────────────────────────

class SitePanel(QWidget):
    """Panel that shows the current property pin and its auto-filled data."""

    pin_drop_requested = pyqtSignal()             # user wants to click the map
    pin_clear_requested = pyqtSignal()
    site_data_updated  = pyqtSignal(dict)         # full result dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lat: Optional[float] = None
        self._lng: Optional[float] = None
        self._label: str = ""
        self._thread: Optional[QThread] = None
        self._worker: Optional[_SiteFetchWorker] = None
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
            "Type an address in the map's search bar to drop a property\n"
            "pin. Site data fills in automatically from public sources.\n"
            "Drag the pin to refine; right-click on the pin to remove."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # Pin info
        pin_box = QGroupBox("Property pin")
        pin_box.setStyleSheet(_GROUP_STYLE)
        pin_layout = QFormLayout(pin_box)
        self._lbl_label = QLabel("—")
        self._lbl_label.setWordWrap(True)
        self._lbl_coords = QLabel("—")
        pin_layout.addRow("Location:", self._lbl_label)
        pin_layout.addRow("Coordinates:", self._lbl_coords)
        layout.addWidget(pin_box)

        # Action buttons
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
        layout.addLayout(btn_row)

        self._lbl_status = QLabel("")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setStyleSheet(
            "color: #ffcc80; font-size: 11px; padding: 2px 4px;"
        )
        layout.addWidget(self._lbl_status)

        # ── Hardiness ────────────────────────────────────────────────
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

        # ── Elevation / slope ───────────────────────────────────────
        self._elev_box = QGroupBox("Elevation & slope")
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
        layout.addWidget(self._elev_box)

        # ── Rainfall ────────────────────────────────────────────────
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

        # ── Soil ────────────────────────────────────────────────────
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
