"""
analysis_panel.py — Side-panel tab for site analysis overlays.

Contains inner tabs:
  A1: Sun Path / Shadow overlay
  A2: Sector Analysis layer
  A3: Slope / Contour indicator
  A4: Wind / Windbreak effect
  H1: Habitat Value Score (Tallamy-style composite scoring of native habitat quality)
"""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QFormLayout, QTabWidget, QSlider, QCheckBox, QColorDialog,
    QGroupBox, QFrame, QTextEdit, QDial, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool, QRunnable
from PyQt6.QtGui import QColor, QPixmap


class AnalysisPanel(QWidget):
    """Panel with analysis overlay controls (A1-A4)."""

    # A1: Sun path
    sun_path_requested = pyqtSignal(dict)   # {lat, lng, date_key, show_shadows}
    sun_path_cleared = pyqtSignal()

    # A2: Sector analysis
    sector_requested = pyqtSignal(dict)     # {sectors: [{name, azimuth, spread, color}], lat, lng, radius}
    sector_cleared = pyqtSignal()

    # A3: Contour
    contour_requested = pyqtSignal(dict)    # {interval_m, color, show_labels}
    contour_cleared = pyqtSignal()

    # A4: Wind/windbreak
    wind_requested = pyqtSignal(dict)       # {direction, speed_label, show_shelter}
    wind_cleared = pyqtSignal()
    wind_data_requested = pyqtSignal()      # fetch real wind data for the site
    # Live wind-shadow overlay (V1.68).
    wind_shadow_toggled = pyqtSignal(bool)
    wind_angle_changed_live = pyqtSignal(int)   # dial scrub (JS-only redraw)
    wind_shadow_commit = pyqtSignal(int)        # dial released (Python merge)
    # Snow-catch microsites (Step 3): winter drifts in the lee of windbreaks.
    snow_catch_toggled = pyqtSignal(bool)

    # Season view
    season_changed = pyqtSignal(str)        # "Spring" | "Summer" | "Fall" | "Winter"

    # A cached species photo finished downloading off-thread — re-render the
    # Habitat tab's species gallery (F11 / I1). Emitted from a worker thread;
    # Qt delivers it to the GUI thread.
    galleryImageReady = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._placed_plants: list[dict] = []
        self._structures: list[dict] = []
        self._last_habitat_result = None          # for the species gallery re-render
        self._gallery_warmed: set[str] = set()    # image urls already fetched once
        self._lawn_conversion: dict | None = None  # for the F10 counterfactual
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        from src.ui_style import inner_tab_stylesheet
        from src.fill_tab_widget import FillTabWidget
        self._tabs = FillTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setUsesScrollButtons(False)
        self._tabs.tabBar().setExpanding(True)
        # Tighter horizontal padding than the stock sub-tab style: this strip
        # holds five labels and has to fit the side panel's 260px minimum on
        # macOS too, whose system font renders wider than Windows/Linux at the
        # same 11px (same trick as the top-level strip in app.py).
        self._tabs.setStyleSheet(inner_tab_stylesheet()
                                 + "QTabBar::tab { padding: 4px 6px; }")

        self._build_sun_tab()
        self._build_sector_tab()
        # Manual contour drawing moved to Site → Slope analysis (it's
        # site-scale terrain analysis and lives next to the auto-contour
        # generator there).
        self._build_wind_tab()
        self._build_season_tab()
        self._build_habitat_tab()
        self._build_bee_tab()

        layout.addWidget(self._tabs)

    # ═════════════════════════════════════════════════════════════════════════
    #  A1 — Sun Path / Shadow
    # ═════════════════════════════════════════════════════════════════════════

    def _build_sun_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Show the sun's arc across the sky and shadow direction arrows "
            "for the selected date. Helps place shade-sensitive crops."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._sun_date = QComboBox()
        self._sun_date.addItems([
            "Summer Solstice (Jun 21)",
            "Winter Solstice (Dec 21)",
            "Spring Equinox (Mar 20)",
            "Fall Equinox (Sep 22)",
            "Last Frost (~May 7)",
            "First Frost (~Sep 23)",
            "Today",
        ])
        form.addRow("Date:", self._sun_date)

        self._sun_time_slider = QSlider(Qt.Orientation.Horizontal)
        self._sun_time_slider.setRange(0, 2)  # 0=morning, 1=noon, 2=evening
        self._sun_time_slider.setValue(1)
        self._sun_time_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._sun_time_label = QLabel("Show: All day arc")
        form.addRow(self._sun_time_label, self._sun_time_slider)

        self._sun_shadows = QCheckBox("Show shadow direction arrows")
        self._sun_shadows.setChecked(True)
        form.addRow(self._sun_shadows)

        self._sun_shadow_length = QCheckBox("Show shadow length indicators")
        self._sun_shadow_length.setChecked(False)
        form.addRow(self._sun_shadow_length)

        arc_row = QHBoxLayout()
        arc_row.addWidget(QLabel("Arc radius:"))
        self._sun_arc_radius = QSpinBox()
        self._sun_arc_radius.setRange(20, 500)
        self._sun_arc_radius.setValue(80)
        self._sun_arc_radius.setSuffix(" m")
        self._sun_arc_radius.setToolTip(
            "Minimum arc radius in metres. The arc auto-sizes to ~22% of the\n"
            "viewport so it's always legible — this value sets a lower bound."
        )
        arc_row.addWidget(self._sun_arc_radius)
        arc_row.addStretch()
        form.addRow(arc_row)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_show = QPushButton("Place Sun Path…")
        btn_show.setToolTip("Click this then click the map to place the sun path anchor")
        btn_show.setStyleSheet(
            "QPushButton { background: #e65100; color: #fff3e0; border: 1px solid #ff6d00; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #ff6d00; }"
        )
        btn_show.clicked.connect(self._on_show_sun_path)
        btn_row.addWidget(btn_show)

        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_clear.clicked.connect(self.sun_path_cleared.emit)
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

        # Results area
        self._sun_info = QLabel("")
        self._sun_info.setWordWrap(True)
        self._sun_info.setStyleSheet("color: #ffcc80; font-size: 11px; padding: 4px;")
        layout.addWidget(self._sun_info)

        layout.addStretch()
        self._tabs.addTab(tab, "Sun Path")

    def _on_show_sun_path(self):
        from src.solar import KEY_DATES
        date_map = {
            0: "Summer Solstice",
            1: "Winter Solstice",
            2: "Spring Equinox",
            3: "Fall Equinox",
            4: "Last Frost (~May 7)",
            5: "First Frost (~Sep 23)",
            6: "today",
        }
        date_key = date_map.get(self._sun_date.currentIndex(), "today")
        if date_key == "today":
            d = date.today()
        else:
            d = KEY_DATES.get(date_key, date.today())

        self.sun_path_requested.emit({
            "date": d.isoformat(),
            "date_label": self._sun_date.currentText(),
            "show_shadows": self._sun_shadows.isChecked(),
            "show_shadow_length": self._sun_shadow_length.isChecked(),
            "arc_radius": self._sun_arc_radius.value(),
        })

    def set_sun_info(self, text: str):
        self._sun_info.setText(text)

    # ═════════════════════════════════════════════════════════════════════════
    #  A2 — Sector Analysis
    # ═════════════════════════════════════════════════════════════════════════

    def _build_sector_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Draw directional wedges on the map for sun, wind, frost flow, "
            "noise, views — site analysis of environmental influences."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # Preset sectors
        self._sector_checks: list[tuple[QCheckBox, dict]] = []
        presets = [
            {"name": "Summer Sun",    "azimuth": 180, "spread": 120, "color": "#ff9800"},
            {"name": "Winter Sun",    "azimuth": 180, "spread": 60,  "color": "#ffc107"},
            {"name": "NW Wind",       "azimuth": 315, "spread": 45,  "color": "#42a5f5"},
            {"name": "Cold North",    "azimuth": 0,   "spread": 60,  "color": "#90caf9"},
            {"name": "Frost Pocket",  "azimuth": 0,   "spread": 90,  "color": "#b3e5fc"},
            {"name": "Noise (Road)",  "azimuth": 90,  "spread": 45,  "color": "#ef5350"},
            {"name": "Good View",     "azimuth": 180, "spread": 90,  "color": "#66bb6a"},
            {"name": "Fire Risk",     "azimuth": 225, "spread": 45,  "color": "#ff5722"},
        ]

        sectors_group = QGroupBox("Sector Presets")
        sectors_group.setStyleSheet(
            "QGroupBox { border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 8px; padding-top: 12px; }"
            "QGroupBox::title { color: #a5d6a7; }"
        )
        sg_layout = QVBoxLayout(sectors_group)
        sg_layout.setSpacing(2)

        for preset in presets:
            row = QHBoxLayout()
            cb = QCheckBox(preset["name"])
            cb.setStyleSheet(f"color: {preset['color']};")
            row.addWidget(cb)

            # Azimuth spinner
            az = QSpinBox()
            az.setRange(0, 359)
            az.setValue(preset["azimuth"])
            az.setSuffix("°")
            az.setFixedWidth(82)
            row.addWidget(az)

            # Spread spinner
            sp = QSpinBox()
            sp.setRange(10, 180)
            sp.setValue(preset["spread"])
            sp.setSuffix("°")
            sp.setFixedWidth(75)
            row.addWidget(sp)

            sg_layout.addLayout(row)
            self._sector_checks.append((cb, {
                "name": preset["name"],
                "color": preset["color"],
                "az_spin": az,
                "sp_spin": sp,
            }))

        layout.addWidget(sectors_group)

        # Radius
        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("Radius (m):"))
        self._sector_radius = QSpinBox()
        self._sector_radius.setRange(10, 500)
        self._sector_radius.setValue(80)
        self._sector_radius.setSuffix(" m")
        radius_row.addWidget(self._sector_radius)
        layout.addLayout(radius_row)

        btn_row = QHBoxLayout()
        btn_show = QPushButton("Place Sectors…")
        btn_show.setToolTip("Click then click the map to place sector anchor; drag centre to move, orange handle to resize, purple to rotate; right-click centre to remove")
        btn_show.setStyleSheet(
            "QPushButton { background: #1565c0; color: #e3f2fd; border: 1px solid #1976d2; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #1976d2; }"
        )
        btn_show.clicked.connect(self._on_show_sectors)
        btn_row.addWidget(btn_show)

        btn_clear = QPushButton("Clear All")
        btn_clear.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_clear.clicked.connect(self.sector_cleared.emit)
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

        layout.addStretch()
        self._tabs.addTab(tab, "Sectors")

    def _on_show_sectors(self):
        sectors = []
        for cb, data in self._sector_checks:
            if cb.isChecked():
                sectors.append({
                    "name": data["name"],
                    "azimuth": data["az_spin"].value(),
                    "spread": data["sp_spin"].value(),
                    "color": data["color"],
                })
        if not sectors:
            return
        self.sector_requested.emit({
            "sectors": sectors,
            "radius_m": self._sector_radius.value(),
        })

    # ═════════════════════════════════════════════════════════════════════════
    #  A3 — Slope / Contour
    # ═════════════════════════════════════════════════════════════════════════

    def _build_contour_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Draw manual contour lines to indicate terrain slope. Helps "
            "place swales, ponds, and water features correctly.\n\n"
            "Click points on the map to draw a contour line, double-click "
            "to finish. Add multiple lines at different elevations."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._contour_elevation = QDoubleSpinBox()
        self._contour_elevation.setRange(0, 2000)
        self._contour_elevation.setSingleStep(0.5)
        self._contour_elevation.setValue(0)
        self._contour_elevation.setSuffix(" m")
        form.addRow("Elevation:", self._contour_elevation)

        self._contour_interval = QDoubleSpinBox()
        self._contour_interval.setRange(0.1, 10.0)
        self._contour_interval.setSingleStep(0.5)
        self._contour_interval.setValue(1.0)
        self._contour_interval.setSuffix(" m")
        form.addRow("Interval:", self._contour_interval)

        self._contour_color = "#795548"
        color_row = QHBoxLayout()
        self._contour_color_btn = QPushButton()
        self._contour_color_btn.setFixedSize(28, 28)
        self._contour_color_btn.setStyleSheet(
            f"background: {self._contour_color}; border: 1px solid #4a7a4a; border-radius: 4px;"
        )
        self._contour_color_btn.clicked.connect(self._pick_contour_color)
        color_row.addWidget(self._contour_color_btn)
        color_row.addStretch()
        form.addRow("Color:", color_row)

        self._contour_labels = QCheckBox("Show elevation labels")
        self._contour_labels.setChecked(True)
        form.addRow(self._contour_labels)

        # Slope arrow toggle
        self._contour_slope_arrows = QCheckBox("Show downhill arrows")
        self._contour_slope_arrows.setChecked(True)
        self._contour_slope_arrows.setToolTip("Show arrows indicating downhill direction between contour lines")
        form.addRow(self._contour_slope_arrows)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_draw = QPushButton("Draw Contour Line")
        btn_draw.setStyleSheet(
            "QPushButton { background: #5d4037; color: #efebe9; border: 1px solid #795548; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #6d4c41; }"
        )
        btn_draw.clicked.connect(self._on_draw_contour)
        btn_row.addWidget(btn_draw)

        btn_clear = QPushButton("Clear All")
        btn_clear.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_clear.clicked.connect(self.contour_cleared.emit)
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

        # Note about auto-generated contours: that UI moved to Site →
        # "Slope analysis (area)" because it's site-scale terrain analysis,
        # not a manual annotation.
        moved_note = QLabel(
            "ℹ Looking for auto-generated contours from elevation data?\n"
            "→ Site tab → Slope analysis."
        )
        moved_note.setWordWrap(True)
        moved_note.setStyleSheet(
            "color: #90a4ae; font-size: 11px; font-style: italic; "
            "padding: 6px 4px;"
        )
        layout.addWidget(moved_note)

        layout.addStretch()
        self._tabs.addTab(tab, "Contours")

    def _pick_contour_color(self):
        color = QColorDialog.getColor(QColor(self._contour_color), self, "Contour Color")
        if color.isValid():
            self._contour_color = color.name()
            self._contour_color_btn.setStyleSheet(
                f"background: {self._contour_color}; border: 1px solid #4a7a4a; border-radius: 4px;"
            )

    def _on_draw_contour(self):
        self.contour_requested.emit({
            "elevation_m": self._contour_elevation.value(),
            "interval_m": self._contour_interval.value(),
            "color": self._contour_color,
            "show_labels": self._contour_labels.isChecked(),
            "show_slope_arrows": self._contour_slope_arrows.isChecked(),
        })
        # Increment elevation for next contour line
        self._contour_elevation.setValue(
            self._contour_elevation.value() + self._contour_interval.value()
        )

    # ═════════════════════════════════════════════════════════════════════════
    #  A4 — Wind / Windbreak
    # ═════════════════════════════════════════════════════════════════════════

    def _build_wind_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Fetch real seasonal wind data (Open-Meteo, free) for this site, or "
            "set the prevailing direction by hand. Windbreaks and hedges show a "
            "shelter zone behind them (10× their height)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # ── Real wind data (seasonal rose + current reading) ───────────────
        btn_fetch = QPushButton("Fetch wind data (Open-Meteo)")
        btn_fetch.setStyleSheet(
            "QPushButton { background: #00695c; color: #e0f2f1; "
            "border: 1px solid #00897b; border-radius: 4px; padding: 6px; "
            "font-weight: bold; } QPushButton:hover { background: #00897b; }")
        btn_fetch.setToolTip(
            "Download a seasonal wind rose + current reading for this location. "
            "Cached for offline use after the first fetch.")
        btn_fetch.clicked.connect(self.wind_data_requested.emit)
        layout.addWidget(btn_fetch)

        from src.wind_rose_widget import WindRoseWidget
        self._wind_rose = WindRoseWidget()
        layout.addWidget(self._wind_rose)

        self._wind_current_lbl = QLabel("")
        self._wind_current_lbl.setStyleSheet("color: #b3e5fc; font-size: 12px;")
        layout.addWidget(self._wind_current_lbl)

        self._wind_status_lbl = QLabel("")
        self._wind_status_lbl.setWordWrap(True)
        self._wind_status_lbl.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(self._wind_status_lbl)

        self._wind_advice_lbl = QLabel("")
        self._wind_advice_lbl.setWordWrap(True)
        self._wind_advice_lbl.setStyleSheet(
            "color: #c5e1a5; font-size: 11px; font-style: italic;")
        layout.addWidget(self._wind_advice_lbl)

        # ── Live wind shadow (V1.68): per-plant sheltered zones that update as
        # you turn the dial or drag a plant.
        self._wind_shadow_chk = QCheckBox("Live wind shadow (sheltered zones)")
        self._wind_shadow_chk.setToolTip(
            "Show the leeward shelter of trees/shrubs, merged and porosity-aware. "
            "Turn the dial or drag a plant to see it update live.")
        self._wind_shadow_chk.toggled.connect(self.wind_shadow_toggled.emit)
        layout.addWidget(self._wind_shadow_chk)

        # Snow-catch microsites (Step 3): winter snow drifts into the lee of
        # windbreaks — deeper-insulated, moister, slightly warmer planting spots.
        self._snow_catch_chk = QCheckBox("Snow catch (winter drifts in lee)")
        self._snow_catch_chk.setToolTip(
            "Show where winter snow drifts into the shelter of trees, shrubs and "
            "structures — insulated, moister microsites. Uses the prevailing "
            "winter wind from the fetched wind rose.")
        self._snow_catch_chk.toggled.connect(self.snow_catch_toggled.emit)
        layout.addWidget(self._snow_catch_chk)

        dial_row = QHBoxLayout()
        self._wind_dial = QDial()
        self._wind_dial.setRange(0, 359)
        self._wind_dial.setWrapping(True)
        self._wind_dial.setNotchesVisible(True)
        self._wind_dial.setValue(270)
        self._wind_dial.setFixedSize(90, 90)
        self._wind_dial.valueChanged.connect(self._on_wind_dial)
        self._wind_dial.sliderReleased.connect(
            lambda: self.wind_shadow_commit.emit(self._wind_dial.value()))
        dial_row.addWidget(self._wind_dial)
        self._wind_dial_lbl = QLabel("Wind from 270°")
        self._wind_dial_lbl.setStyleSheet("color: #b3e5fc; font-size: 11px;")
        dial_row.addWidget(self._wind_dial_lbl)
        dial_row.addStretch()
        layout.addLayout(dial_row)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._wind_dir = QComboBox()
        self._wind_dir.addItems([
            "N (0°)", "NNE (22°)", "NE (45°)", "ENE (67°)",
            "E (90°)", "ESE (112°)", "SE (135°)", "SSE (157°)",
            "S (180°)", "SSW (202°)", "SW (225°)", "WSW (247°)",
            "W (270°)", "WNW (292°)", "NW (315°)", "NNW (337°)",
        ])
        self._wind_dir.setCurrentIndex(14)  # NW default for Edmonton
        form.addRow("Wind from:", self._wind_dir)

        self._wind_speed = QComboBox()
        self._wind_speed.addItems(["Light", "Moderate", "Strong", "Very Strong"])
        self._wind_speed.setCurrentIndex(1)
        form.addRow("Typical:", self._wind_speed)

        self._wind_shelter = QCheckBox("Show shelter zones behind windbreaks")
        self._wind_shelter.setChecked(True)
        self._wind_shelter.setToolTip(
            "Hedgerows and windbreak structures show a\n"
            "sheltered zone (10× height) on the leeward side"
        )
        form.addRow(self._wind_shelter)

        self._wind_arrows = QCheckBox("Show wind flow arrows")
        self._wind_arrows.setChecked(True)
        form.addRow(self._wind_arrows)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_show = QPushButton("Show Wind Overlay")
        btn_show.setStyleSheet(
            "QPushButton { background: #0277bd; color: #e1f5fe; border: 1px solid #0288d1; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #0288d1; }"
        )
        btn_show.clicked.connect(self._on_show_wind)
        btn_row.addWidget(btn_show)

        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet(
            "QPushButton { background: #37474f; color: #b0bec5; border: 1px solid #546e7a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #455a64; }"
        )
        btn_clear.clicked.connect(self.wind_cleared.emit)
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

        layout.addStretch()
        self._tabs.addTab(tab, "Wind")

    _WIND_AZIMUTHS = [0, 22, 45, 67, 90, 112, 135, 157,
                      180, 202, 225, 247, 270, 292, 315, 337]

    def _on_show_wind(self):
        az = self._WIND_AZIMUTHS[self._wind_dir.currentIndex()]
        self.wind_requested.emit({
            "direction_from": az,
            "speed_label": self._wind_speed.currentText(),
            "show_shelter": self._wind_shelter.isChecked(),
            "show_arrows": self._wind_arrows.isChecked(),
        })

    # ── Real wind data (V1.67) ──────────────────────────────────────────────

    def set_wind_status(self, text: str):
        self._wind_status_lbl.setText(text)

    def set_wind_advice(self, text: str):
        self._wind_advice_lbl.setText(text or "")

    def _on_wind_dial(self, value: int):
        self._wind_dial_lbl.setText(f"Wind from {value}°")
        self.wind_angle_changed_live.emit(value)

    def set_wind_data(self, rose: dict, current: dict | None):
        """Populate the Wind tab from a fetched rose + current reading: draw the
        rose, set the prevailing-direction/speed controls to the data, and show
        the live reading. Also surfaces a windbreak hint via the design hook in
        the controller (which reads the same rose from the cache)."""
        if not rose:
            self.set_wind_status(
                "Wind data unavailable (offline and nothing cached).")
            self._wind_rose.set_block(None)
            return
        annual = rose.get("annual") or {}
        self._wind_rose.set_block(annual)

        from src.wind import dir_index, speed_category
        prevailing = annual.get("prevailing_deg")
        if prevailing is not None:
            self._wind_dir.setCurrentIndex(dir_index(prevailing))
            blocked = self._wind_dial.blockSignals(True)
            self._wind_dial.setValue(int(prevailing) % 360)
            self._wind_dial.blockSignals(blocked)
            self._wind_dial_lbl.setText(f"Wind from {int(prevailing) % 360}°")
        cat = speed_category(annual.get("mean_speed"))
        idx = self._wind_speed.findText(cat)
        if idx >= 0:
            self._wind_speed.setCurrentIndex(idx)

        if current:
            self._wind_current_lbl.setText(
                f"Now: {current['speed']:.0f} km/h from {current['dir_label']}"
                + (f", gusts {current['gusts']:.0f}" if current.get("gusts")
                   else ""))
        else:
            self._wind_current_lbl.setText("")

        label = annual.get("prevailing_label") or "—"
        mean = annual.get("mean_speed")
        calm = annual.get("calm_pct")
        src = rose.get("source", "")
        self.set_wind_status(
            f"Prevailing {label} · mean {mean:.0f} km/h · calm {calm:.0f}%  "
            f"({src}). Click 'Show Wind Overlay' to apply.")

    # ═════════════════════════════════════════════════════════════════════════
    #  Season View
    # ═════════════════════════════════════════════════════════════════════════

    def _build_season_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Preview how your landscape looks in different seasons. "
            "Deciduous plants fade in winter, herbaceous perennials "
            "disappear, evergreens stay full."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        row = QHBoxLayout()
        row.addWidget(QLabel("Season:"))
        self._season_combo = QComboBox()
        self._season_combo.addItems(["Summer", "Spring", "Fall", "Winter"])
        self._season_combo.setCurrentIndex(0)
        row.addWidget(self._season_combo)
        layout.addLayout(row)

        apply_btn = QPushButton("Apply Season View")
        apply_btn.clicked.connect(self._on_season_apply)
        layout.addWidget(apply_btn)

        reset_btn = QPushButton("Reset (Summer)")
        reset_btn.clicked.connect(lambda: (
            self._season_combo.setCurrentIndex(0),
            self._on_season_apply(),
        ))
        layout.addWidget(reset_btn)

        layout.addStretch()
        self._tabs.addTab(tab, "Season")

    def _on_season_apply(self):
        self.season_changed.emit(self._season_combo.currentText())

    # ═════════════════════════════════════════════════════════════════════════
    #  H1 — Habitat Value Score
    # ═════════════════════════════════════════════════════════════════════════

    def _build_habitat_tab(self):
        # Scrollable page: this tab is tall (score, value, species gallery,
        # breakdown, tips, shade) and used to overlap when squeezed into a fixed
        # height. A scroll area lets it grow instead (matches site_panel).
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        tab = QWidget()
        page.setWidget(tab)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "How much native habitat your design actually provides — scored "
            "0–100 from native ratio, keystone species, host plants, bird "
            "food, vegetation-layer diversity, habitat structures, and bloom "
            "continuity."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        btn = QPushButton("Calculate Habitat Value")
        btn.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }"
        )
        btn.clicked.connect(self._calc_habitat_score)
        layout.addWidget(btn)

        # Big score readout
        self._habitat_score_label = QLabel("—")
        self._habitat_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._habitat_score_label.setStyleSheet(
            "color: #c8e6c9; font-size: 32px; font-weight: bold; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; padding: 12px;"
        )
        layout.addWidget(self._habitat_score_label)

        # Lawn-equivalent counterfactual (F10, P6/P8): the Tallamy contrast made
        # explicit — what this design provides vs. the ≈0 a conventional lawn of
        # the same ground would. Hidden until a score is computed.
        self._lawn_counterfactual_label = QLabel("")
        self._lawn_counterfactual_label.setWordWrap(True)
        self._lawn_counterfactual_label.setVisible(False)
        self._lawn_counterfactual_label.setStyleSheet(
            "color: #dcedc8; font-size: 11px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;"
        )
        layout.addWidget(self._lawn_counterfactual_label)

        # Species galleries (F11 / I1) — photos that make the value tangible.
        # "Species doing the work" = the plants (keystone / host / bird-food
        # first); "Species supported" = the fauna those plants feed/host. Both
        # show cached photos immediately and warm the rest in the background.
        def _gallery_strip(title: str):
            lbl = QLabel(title)
            lbl.setStyleSheet(
                "color: #a5d6a7; font-size: 12px; font-weight: bold; "
                "padding: 4px 0 2px 0;")
            lbl.setVisible(False)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setFixedHeight(122)
            area.setVisible(False)
            area.setStyleSheet(
                "background: #14241a; border: 1px solid #2e4a2e; border-radius: 4px;")
            inner = QWidget()
            row = QHBoxLayout(inner)
            row.setContentsMargins(6, 6, 6, 6)
            row.setSpacing(8)
            row.addStretch()   # keep cards left-aligned
            area.setWidget(inner)
            layout.addWidget(lbl)
            layout.addWidget(area)
            return lbl, area, row

        (self._species_gallery_label, self._species_gallery,
         self._species_gallery_row) = _gallery_strip("Species doing the work")
        (self._fauna_gallery_label, self._fauna_gallery,
         self._fauna_gallery_row) = _gallery_strip("Species supported")
        self.galleryImageReady.connect(self._on_gallery_image_ready)

        # Breakdown
        self._habitat_breakdown = QLabel("")
        self._habitat_breakdown.setWordWrap(True)
        self._habitat_breakdown.setStyleSheet(
            "color: #c8e6c9; font-size: 11px; padding: 8px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; "
            "font-family: 'Consolas', 'Courier New', monospace;"
        )
        self._habitat_breakdown.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._habitat_breakdown.setMinimumHeight(220)
        layout.addWidget(self._habitat_breakdown)

        # Tips for raising your score
        tips_label = QLabel("Tips for raising your score")
        tips_label.setStyleSheet("color: #a5d6a7; font-size: 12px; font-weight: bold; padding: 4px 0 2px 0;")
        layout.addWidget(tips_label)

        self._habitat_tips = QTextEdit()
        self._habitat_tips.setReadOnly(True)
        self._habitat_tips.setStyleSheet(
            "QTextEdit { background: #1a2a1a; color: #c8e6c9; "
            "border: 1px solid #2e4a2e; border-radius: 4px; padding: 6px; "
            "font-size: 11px; }"
        )
        self._habitat_tips.setMinimumHeight(160)
        layout.addWidget(self._habitat_tips)

        # Shade-zone breakdown — read-only summary of the cached shade tags
        # (Site tab → "Classify planting zones"). Shown here so the light mix is
        # visible alongside habitat value without recomputing the shade grid.
        shade_label = QLabel("Light / shade mix")
        shade_label.setStyleSheet(
            "color: #a5d6a7; font-size: 12px; font-weight: bold; padding: 4px 0 2px 0;")
        layout.addWidget(shade_label)

        self._shade_breakdown = QLabel(
            "Run 'Classify planting zones' on the Site tab to see the\n"
            "full-sun / partial-shade / full-shade mix.")
        self._shade_breakdown.setWordWrap(True)
        self._shade_breakdown.setStyleSheet(
            "color: #c8e6c9; font-size: 11px; padding: 6px; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;")
        layout.addWidget(self._shade_breakdown)

        # Reference link
        ref = QLabel(
            "Based on Doug Tallamy's keystone-species framework "
            "(homegrownnationalpark.org) — high-value native species support "
            "90% of insect biodiversity."
        )
        ref.setWordWrap(True)
        ref.setStyleSheet("color: #607d8b; font-size: 10px; font-style: italic;")
        layout.addWidget(ref)

        # Short tab label so all five fit the strip even with macOS's wider
        # font; the page itself carries the full "Habitat Value" wording.
        self._tabs.addTab(page, "Habitat")

    # ═════════════════════════════════════════════════════════════════════════
    #  Bees — "Design for a bee" habitat builder (F37)
    # ═════════════════════════════════════════════════════════════════════════

    _FIT_CHIP = {
        "good":      ("#1b5e20", "#a5d6a7", "good fit"),
        "plausible": ("#33450f", "#dcedc8", "workable"),
        "unknown":   ("#37474f", "#b0bec5", "—"),
    }
    _MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def _build_bee_tab(self):
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        tab = QWidget()
        page.setWidget(tab)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Design habitat for a specific native bee. Pick a target — a whole "
            "genus or a single species — to see which of your plants feed it, how "
            "to give it a place to nest, and whether your design blooms across its "
            "flight season."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        self._bee_selector = QComboBox()
        self._bee_selector.setStyleSheet("QComboBox { padding: 4px; }")
        self._populate_bee_selector()
        self._bee_selector.currentIndexChanged.connect(self._update_bee_plan)
        layout.addWidget(self._bee_selector)

        # Summary: photo + facts
        summ = QHBoxLayout()
        summ.setSpacing(8)
        self._bee_photo = QLabel("🐝")
        self._bee_photo.setFixedSize(96, 72)
        self._bee_photo.setScaledContents(False)
        self._bee_photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bee_photo.setStyleSheet(
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "background: #14241a; font-size: 30px;")
        summ.addWidget(self._bee_photo, 0, Qt.AlignmentFlag.AlignTop)
        self._bee_summary = QLabel("")
        self._bee_summary.setWordWrap(True)
        self._bee_summary.setTextFormat(Qt.TextFormat.RichText)
        self._bee_summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._bee_summary.setStyleSheet("color: #c8e6c9; font-size: 11px;")
        summ.addWidget(self._bee_summary, 1)
        layout.addLayout(summ)

        def _section(title: str) -> QLabel:
            hdr = QLabel(title)
            hdr.setStyleSheet(
                "color: #a5d6a7; font-size: 12px; font-weight: bold; "
                "padding: 6px 0 2px 0;")
            layout.addWidget(hdr)
            body = QLabel("")
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setStyleSheet(
                "color: #c8e6c9; font-size: 11px; padding: 8px; "
                "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px;")
            body.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(body)
            return body

        self._bee_floral = _section("Floral hosts — plants that feed this bee")
        self._bee_nesting = _section("Nesting — give it a place to live")
        self._bee_forage = _section("Forage across the flight season")

        self._bee_footnote = QLabel("")
        self._bee_footnote.setWordWrap(True)
        self._bee_footnote.setStyleSheet(
            "color: #607d8b; font-size: 10px; font-style: italic;")
        layout.addWidget(self._bee_footnote)

        # Re-render the bee photo when a warmed image lands (shared signal).
        self.galleryImageReady.connect(self._render_bee_photo)

        self._tabs.addTab(page, "Bees")
        self._bee_tab_index = self._tabs.indexOf(page)
        # Recompute the plan lazily when the Bees tab is opened, so "in your
        # design" and forage coverage stay live without recomputing on every
        # plant placement.
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._update_bee_plan()

    def _on_tab_changed(self, idx: int):
        if idx == getattr(self, "_bee_tab_index", -1):
            self.refresh_bee_tab()

    def _populate_bee_selector(self):
        """Fill the target-bee combo, grouped genus-first with disabled headers."""
        combo = self._bee_selector
        combo.blockSignals(True)
        combo.clear()
        try:
            from src.bee_habitat import list_target_bees
            bees = list_target_bees()
        except Exception:  # noqa: BLE001 — never let a data issue break the panel
            bees = []
        current_genus = None
        for b in bees:
            if b["genus"] != current_genus:
                current_genus = b["genus"]
                combo.addItem(f"── {current_genus} ──", userData=None)
                idx = combo.count() - 1
                item = combo.model().item(idx)
                if item is not None:
                    item.setEnabled(False)
            if b["is_group"]:
                label = f"    {b['common_name']} (any {b['genus']})"
            else:
                label = f"    {b['common_name']}  ·  {b['scientific_name']}"
            combo.addItem(label, userData=b["id"])
        combo.blockSignals(False)
        # Select the first real (enabled) entry.
        for i in range(combo.count()):
            if combo.itemData(i) is not None:
                combo.setCurrentIndex(i)
                break

    def _current_bee_id(self):
        return self._bee_selector.itemData(self._bee_selector.currentIndex())

    def _placed_plant_ids(self) -> list[int]:
        ids: list[int] = []
        for p in (self._placed_plants or []):
            pid = p.get("plant_id")
            if pid is not None:
                try:
                    ids.append(int(pid))
                except (TypeError, ValueError):
                    pass
        return ids

    def _update_bee_plan(self, *args):
        """Build and render the habitat plan for the selected bee."""
        fid = self._current_bee_id()
        if fid is None:
            return
        try:
            from src.bee_habitat import build_bee_habitat_plan
            plan = build_bee_habitat_plan(fid, plant_ids=self._placed_plant_ids())
        except Exception:  # noqa: BLE001
            plan = None
        if plan is None:
            self._bee_summary.setText("<i>No data for this bee yet.</i>")
            for lbl in (self._bee_floral, self._bee_nesting, self._bee_forage):
                lbl.setText("—")
            self._bee_footnote.setText("")
            return
        self._bee_plan = plan
        self._render_bee_summary(plan)
        self._render_bee_photo()
        self._render_bee_floral(plan)
        self._render_bee_nesting(plan)
        self._render_bee_forage(plan)
        src = (plan.attrs or {}).get("source") or ""
        conf = {"documented": "well-documented", "partial": "partly documented",
                "thin": "sparse"}.get(plan.data_confidence, plan.data_confidence)
        self._bee_footnote.setText(
            f"Data confidence: {conf}. Floral matches shown as documented "
            f"(plant↔bee records) or inferred (genus-level hosts). {src}")

    def _render_bee_summary(self, plan):
        bee = plan.bee or {}
        a = plan.attrs or {}
        tongue = a.get("tongue_length")
        nest = a.get("nesting_habit")
        season = a.get("flight_season")
        cons = a.get("conservation_status")
        bits = [f"<b>{bee.get('common_name','')}</b> "
                f"<span style='color:#90a4ae;'><i>{bee.get('scientific_name','')}</i></span>"]
        facts = []
        if tongue and tongue != "unknown":
            facts.append(f"{tongue}-tongued")
        elif tongue == "unknown":
            facts.append("tongue not characterised")
        if season:
            facts.append(f"flies {season}")
        if facts:
            bits.append("<span style='color:#a5d6a7;'>" + " · ".join(facts) + "</span>")
        if cons:
            colour = "#ff8a65" if "risk" in cons.lower() else "#90a4ae"
            bits.append(f"<span style='color:{colour};'>{cons}</span>")
        desc = bee.get("description") or ""
        if desc:
            bits.append(f"<span style='color:#c8e6c9;'>{desc}</span>")
        self._bee_summary.setText("<br>".join(bits))

    def _render_bee_photo(self):
        """Show the selected bee's cached photo (warming it if needed), else 🐝."""
        plan = getattr(self, "_bee_plan", None)
        if plan is None:
            return
        url = (plan.bee or {}).get("image_url") or ""
        if not url:
            self._bee_photo.setText("🐝")
            self._bee_photo.setPixmap(QPixmap())
            return
        try:
            from src.image_cache import get_cached_image
            path = get_cached_image(url)
        except Exception:  # noqa: BLE001
            path = None
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                self._bee_photo.setText("")
                self._bee_photo.setScaledContents(True)
                self._bee_photo.setPixmap(pm)
                return
        # not cached yet — keep the icon and warm it in the background
        self._bee_photo.setText("🐝")
        if url not in self._gallery_warmed:
            self._gallery_warmed.add(url)
            self._warm_gallery_images([(url,
                                        (plan.bee or {}).get("image_attribution", ""),
                                        (plan.bee or {}).get("image_license", ""))])

    def _render_bee_floral(self, plan):
        matches = plan.floral_matches or []
        if not matches:
            self._bee_floral.setText(
                "<i>No floral-host plants matched — this is often a cuckoo bee "
                "that feeds itself by parasitising a host bee (see Nesting).</i>")
            return
        in_design = [m for m in matches if m.in_users_list]
        rows = []
        if in_design:
            rows.append("<b>In your design:</b>")
            rows.extend(self._bee_match_row(m) for m in in_design[:12])
            rows.append("<br><b>Also good to add:</b>")
            others = [m for m in matches if not m.in_users_list]
        else:
            rows.append("<b>Plants that feed this bee:</b>")
            others = matches
        rows.extend(self._bee_match_row(m) for m in others[:14])
        self._bee_floral.setText("".join(f"<div style='padding:1px 0;'>{r}</div>"
                                          for r in rows))

    def _bee_match_row(self, m) -> str:
        bg, fg, txt = self._FIT_CHIP.get(m.tongue_form_fit, self._FIT_CHIP["unknown"])
        chip = (f"<span style='background:{bg}; color:{fg}; border-radius:3px; "
                f"padding:0 4px; font-size:9px;'>{txt}</span>")
        bloom = f" <span style='color:#90a4ae;'>· {m.bloom_period}</span>" if m.bloom_period else ""
        basis = "" if m.confidence == "documented" else \
                " <span style='color:#78909c; font-size:9px;'>(genus match)</span>"
        star = "★ " if m.in_users_list else ""
        return (f"{star}{m.common_name} {chip}{bloom}{basis}")

    def _render_bee_nesting(self, plan):
        g = plan.nesting
        parts = [f"<b>{g.headline}</b>"]
        if g.structures:
            names = ", ".join(s.get("name", "") for s in g.structures)
            parts.append(f"<span style='color:#a5d6a7;'>Structures: {names}</span>")
        for a in g.actions:
            parts.append(f"• {a}")
        self._bee_nesting.setText("".join(f"<div style='padding:1px 0;'>{p}</div>"
                                           for p in parts))

    def _render_bee_forage(self, plan):
        f = plan.forage
        if not f.flight_months:
            self._bee_forage.setText(f"<i>{f.note}</i>")
            return
        flight = set(f.flight_months)
        covered = set(f.covered_months)
        cells = []
        for mo in range(3, 11):    # Mar–Oct strip
            abbr = self._MONTH_ABBR[mo]
            if mo not in flight:
                style = "color:#4a5a4a;"
            elif mo in covered:
                style = "background:#1b5e20; color:#c8e6c9; border-radius:3px;"
            else:
                style = "background:#5d3a1a; color:#ffcc80; border-radius:3px;"
            cells.append(f"<span style='{style} padding:2px 5px; margin:0 1px;'>{abbr}</span>")
        strip = "".join(cells)
        legend = ("<div style='color:#90a4ae; font-size:9px; padding-top:4px;'>"
                  "green = a plant in bloom for it · orange = flying but no bloom "
                  "(a gap to fill)</div>")
        note = f"<div style='padding-top:4px;'>{f.note}</div>"
        sug = ""
        if f.suggestions:
            names = ", ".join(s.common_name for s in f.suggestions[:6])
            sug = (f"<div style='padding-top:4px; color:#a5d6a7;'>"
                   f"Fill the gap with: {names}</div>")
        self._bee_forage.setText(strip + note + legend + sug)

    def refresh_bee_tab(self):
        """Re-render the bee plan against the current placed plants (call after
        the design changes so 'in your design' / forage coverage stay live)."""
        if hasattr(self, "_bee_selector"):
            self._update_bee_plan()

    def set_shade_breakdown(self, counts: dict | None):
        """Render the cached shade-tag mix (``{tag: n}`` from
        shade_zones.tag_counts), or a prompt when nothing is classified yet.
        Called by the main window after classification / project load."""
        if not hasattr(self, "_shade_breakdown"):
            return
        total = sum((counts or {}).values())
        if not total:
            self._shade_breakdown.setText(
                "Run 'Classify planting zones' on the Site tab to see the\n"
                "full-sun / partial-shade / full-shade mix.")
            return

        def _pct(n):
            return f"{n} ({n * 100 // total}%)"
        self._shade_breakdown.setText(
            f"Across {total} classified spots:\n"
            f"  ☀️  Full sun       {_pct(counts.get('full_sun', 0))}\n"
            f"  ⛅  Partial shade  {_pct(counts.get('partial_shade', 0))}\n"
            f"  🌑  Full shade     {_pct(counts.get('full_shade', 0))}")

    # Structure ids that contribute to habitat value — re-exported from
    # src/habitat_score.py (where the scoring maths lives now) so the
    # tips builder below and the score stay in lock-step.
    from src.habitat_score import HABITAT_STRUCTURE_IDS as _HABITAT_STRUCTURE_IDS

    def set_placed_plants(self, plants: list[dict]):
        """Update the list of placed plants (from app.py)."""
        self._placed_plants = plants
        # Keep the bee plan live if its tab is the one on screen.
        if (hasattr(self, "_bee_tab_index")
                and self._tabs.currentIndex() == self._bee_tab_index):
            self.refresh_bee_tab()

    def set_structures(self, structures: list[dict]):
        """Update the list of placed structures (from app.py)."""
        self._structures = structures

    def set_lawn_conversion(self, summary: dict | None):
        """Store the lawn-conversion summary (from ``lawn_zones.conversion_summary``)
        so the F10 counterfactual can ground its contrast in the converted area.
        Re-renders the counterfactual if a score is already on screen."""
        self._lawn_conversion = summary or None
        if getattr(self, "_last_habitat_result", None) is not None:
            self._render_lawn_counterfactual(self._last_habitat_result)

    def _render_lawn_counterfactual(self, result):
        """Show the design's habitat value beside the ≈0 of an equivalent lawn
        (F10). Never raises — the counterfactual is a nicety, not the score."""
        lbl = getattr(self, "_lawn_counterfactual_label", None)
        if lbl is None:
            return
        try:
            from src.lawn_zones import lawn_counterfactual, format_lawn_counterfactual
            cf = lawn_counterfactual(result, self._lawn_conversion)
            lines = format_lawn_counterfactual(cf)
        except Exception:  # noqa: BLE001
            lines = []
        if not lines:
            lbl.setVisible(False)
            return
        head = lines[0]
        rest = lines[1:]
        html = (f"<b>vs. lawn</b><br>{head}"
                + ("<br><span style='color:#90a4ae;font-size:10px;'>"
                   + "<br>".join(rest) + "</span>" if rest else ""))
        lbl.setText(html)
        lbl.setVisible(True)

    def _calc_habitat_score(self):
        # Scoring maths moved to src/habitat_score.py (Chunk 6) so the
        # headless scripting API and this panel share one implementation.
        # The panel keeps all the rendering below.
        from src.habitat_score import compute_habitat_score, HabitatScoreError
        try:
            result = compute_habitat_score(self._placed_plants, self._structures)
        except HabitatScoreError:
            self._habitat_score_label.setText("?")
            self._habitat_breakdown.setText("Plant database unavailable.")
            self._lawn_counterfactual_label.setVisible(False)
            return
        if result is None:
            self._habitat_score_label.setText("—")
            self._habitat_breakdown.setText("Place some plants and structures first.")
            self._lawn_counterfactual_label.setVisible(False)
            return

        total_int = result.total
        grade = result.grade

        # Score colour
        if total_int >= 75:
            color = "#a5d6a7"
        elif total_int >= 50:
            color = "#dcedc8"
        elif total_int >= 25:
            color = "#fff59d"
        else:
            color = "#ffab91"

        self._habitat_score_label.setText(f"{total_int} / 100")
        self._habitat_score_label.setStyleSheet(
            f"color: {color}; font-size: 32px; font-weight: bold; "
            "background: #1a2a1a; border: 1px solid #2e4a2e; border-radius: 4px; padding: 12px;"
        )

        # Lawn-equivalent counterfactual (F10): this design vs. the ≈0 of an
        # equivalent lawn, grounded in the converted area when zones are drawn.
        self._last_habitat_result = result
        self._render_lawn_counterfactual(result)

        # Species photos that make the value tangible (F11 / I1): the plants
        # doing the work and the fauna they support.
        try:
            self._render_galleries(result)
        except Exception:  # noqa: BLE001 — galleries are a nicety, never break the score
            for w in (self._species_gallery_label, self._species_gallery,
                      self._fauna_gallery_label, self._fauna_gallery):
                w.setVisible(False)

        # Breakdown text — layout unchanged from the pre-extraction code;
        # values now come off the HabitatScore result.
        lines = [
            f"{grade}",
            "",
            f"Native ratio        {result.native_ratio*100:5.0f}%    {result.score_native:4.1f} / 20",
            f"  ({result.native_species} of {result.n_species} species native to AB)",
            "",
            f"Keystone species   {len(result.keystone_species):4d}     {result.score_keystone:4.1f} / 15",
            f"Host plants        {len(result.host_species):4d}     {result.score_host:4.1f} / 10",
            f"Bird-food species  {len(result.bird_species):4d}     {result.score_bird:4.1f} / 10",
            "",
            f"Vegetation layers  {len(result.layers_present):4d}/5   {result.score_layers:4.1f} / 15",
            f"  ({', '.join(result.layers_present) or '—'})",
            "",
            f"Habitat structures {len(result.habitat_struct_types):4d}     {result.score_structs:4.1f} / 10",
            f"  ({', '.join(result.habitat_struct_types) or '—'})",
            "",
            f"Bloom continuity   {len(result.bloom_months)}/7 mo   {result.score_bloom:4.1f} / 20",
            "",
            # Informational fauna support (NOT summed into the headline, so
            # existing scores stay stable as the fauna dataset grows). The
            # lepidoptera line counts larval-host species (schema v13); the
            # per-taxon line counts distinct native fauna the design supports
            # across all taxa (schema v20 expansion).
            f"Lepidoptera supported  {result.n_lepidoptera_supported:4d}    (larval-host species)",
        ]
        if getattr(result, "fauna_by_taxon", None):
            _taxon_label = {
                "lepidoptera": "butterflies/moths", "bird": "birds",
                "bee": "bees", "other_insect": "other insects",
                "mammal": "mammals",
            }
            parts = [f"{n} {_taxon_label.get(t, t)}"
                     for t, n in result.fauna_by_taxon.items()]
            lines.append("Wildlife supported   " + ", ".join(parts))
        # Food-web completeness (F3): does the design close the Tallamy chain
        # (host plants → caterpillars → the birds that eat them)? Informational,
        # never summed into the headline.
        food_web = getattr(result, "food_web", None)
        if food_web:
            _food_web_msg = {
                "complete": "Food web   supports caterpillars and the "
                            "birds that eat them",
                "no_birds": "Food web   caterpillars, but no bird support "
                            "yet; add berry/seed plants",
                "no_hosts": "Food web   birds, but no host plants yet; "
                            "add caterpillar hosts",
                "empty":    "Food web   no host plants or bird support yet",
            }
            _fw_line = _food_web_msg.get(food_web.get("status"))
            if _fw_line:
                lines.append(_fw_line)
        if result.gap_months:
            month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                           "Jul","Aug","Sep","Oct","Nov","Dec"]
            lines.append(
                "  Gap months: " + ", ".join(month_names[m-1] for m in result.gap_months)
            )
        lines.append("")
        lines.append(f"Total {result.n_total_plants} plants, {result.n_species} species")

        # Estimated plant cost (schema v19) — a range, AB retail estimate.
        try:
            from src.sourcing import estimate_cost, format_cost
            low, high = estimate_cost(self._placed_plants)
            if high > 0:
                lines.append(
                    f"Est. plant cost    {format_cost(low, high)}   (AB retail estimate)")
        except Exception:  # noqa: BLE001 — cost is a nicety, never break the score
            pass

        self._habitat_breakdown.setText("\n".join(lines))

        # ── Tips: targeted suggestions for the lowest-scoring categories ──
        # Use the DB-backed id set (matches the pre-extraction behaviour
        # of keying off plant_rows.keys()).
        placed_ids = set(result.scored_plant_ids)
        tips_html = self._build_habitat_tips(
            native_ratio=result.native_ratio,
            n_keystone=len(result.keystone_species),
            n_host=len(result.host_species),
            n_bird=len(result.bird_species),
            layers_present=set(result.layers_present),
            habitat_struct_types=set(result.habitat_struct_types),
            gap_months=result.gap_months,
            placed_ids=placed_ids,
        )
        self._habitat_tips.setHtml(tips_html)

    # ── Species gallery (F11 / I1): photos of the design's high-value species ──

    def _gallery_species(self, result) -> list:
        """The design's species worth picturing, highest-value first (keystone →
        host → bird-food → other natives), limited to those with an image URL.
        Returns ``(name, cached_path_or_None, url, attribution, license)`` tuples."""
        from src.db.plants import get_plant
        from src.image_cache import get_cached_image
        recs: dict = {}
        for pid in getattr(result, "scored_plant_ids", None) or []:
            try:
                r = get_plant(pid)
            except Exception:  # noqa: BLE001
                r = None
            if r and r.get("image_url") and r.get("common_name"):
                recs.setdefault(r["common_name"], r)
        priority = (list(result.keystone_species) + list(result.host_species)
                    + list(result.bird_species))
        out: list = []
        seen: set = set()

        def _add(r):
            nm = r.get("common_name")
            if not nm or nm in seen:
                return
            seen.add(nm)
            url = r.get("image_url")
            out.append((nm, get_cached_image(url), url,
                        r.get("image_attribution", ""), r.get("image_license", "")))

        for nm in priority:
            if nm in recs:
                _add(recs[nm])
        for r in recs.values():
            if r.get("native_to_alberta"):
                _add(r)
        return out[:12]

    def _make_species_card(self, name: str, path: str) -> QWidget:
        """A small thumbnail + caption card for one species."""
        card = QWidget()
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        thumb = QLabel()
        thumb.setFixedSize(96, 72)
        thumb.setScaledContents(True)
        pm = QPixmap(path)
        if not pm.isNull():
            thumb.setPixmap(pm)
        thumb.setStyleSheet("border: 1px solid #2e4a2e; border-radius: 3px;")
        cap = QLabel(name)
        cap.setWordWrap(True)
        cap.setFixedWidth(96)
        cap.setStyleSheet("color: #c8e6c9; font-size: 9px;")
        v.addWidget(thumb)
        v.addWidget(cap)
        return card

    def _fauna_gallery_species(self, result) -> list:
        """The fauna the design supports, deduped, limited to those with an image
        URL. Returns ``(name, cached_path_or_None, url, attribution, license)``."""
        from src.db.fauna import fauna_for_plants
        from src.image_cache import get_cached_image
        ids = list(getattr(result, "scored_plant_ids", None) or [])
        if not ids:
            return []
        try:
            rows = fauna_for_plants(ids)
        except Exception:  # noqa: BLE001
            return []
        out: list = []
        seen: set = set()
        for f in rows:
            nm = f.get("common_name")
            url = f.get("image_url")
            key = f.get("id") if f.get("id") is not None else nm
            if not nm or not url or key in seen:
                continue
            seen.add(key)
            out.append((nm, get_cached_image(url), url,
                        f.get("image_attribution", ""), f.get("image_license", "")))
        return out[:12]

    def _fill_gallery(self, label, area, row, items) -> list:
        """Fill one gallery strip: cached photos become cards now; the rest are
        returned as ``(url, attr, lic)`` pending tuples to warm. Shows the strip
        only when at least one photo is ready."""
        while row.count() > 1:                       # keep the trailing stretch
            it = row.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        pending: list = []
        shown = 0
        for name, path, url, attr, lic in items:
            if path:
                row.insertWidget(row.count() - 1, self._make_species_card(name, path))
                shown += 1
            elif url and url not in self._gallery_warmed:
                pending.append((url, attr, lic))
        label.setVisible(shown > 0)
        area.setVisible(shown > 0)
        return pending

    def _render_galleries(self, result):
        """Render both photo strips (plants doing the work + fauna supported),
        warming any not-yet-cached photos; the strips re-render as they land."""
        pending = self._fill_gallery(
            self._species_gallery_label, self._species_gallery,
            self._species_gallery_row, self._gallery_species(result))
        pending += self._fill_gallery(
            self._fauna_gallery_label, self._fauna_gallery,
            self._fauna_gallery_row, self._fauna_gallery_species(result))
        if pending:
            for url, _attr, _lic in pending:
                self._gallery_warmed.add(url)
            self._warm_gallery_images(pending)

    def _warm_gallery_images(self, pending: list):
        """Fetch+cache the not-yet-cached species photos off the UI thread,
        re-rendering the strip as each lands (mirrors plant_list_view's warm)."""
        sig = self.galleryImageReady

        class _FetchTask(QRunnable):
            def __init__(self, url, attr, lic):
                super().__init__()
                self._url, self._attr, self._lic = url, attr, lic

            def run(self):
                try:
                    from src.image_cache import resolve_image
                    if resolve_image(self._url, self._attr, self._lic):
                        sig.emit()
                except Exception:  # noqa: BLE001 — a missing photo is not an error
                    pass

        for url, attr, lic in pending:
            QThreadPool.globalInstance().start(_FetchTask(url, attr, lic))

    def _on_gallery_image_ready(self):
        res = self._last_habitat_result
        if res is not None:
            try:
                self._render_galleries(res)
            except Exception:  # noqa: BLE001
                pass

    # Canonical layer names paired with the plant_types that fulfil them.
    _LAYER_TO_PLANT_TYPES = {
        "overstory":   ["tree"],
        "shrub":       ["shrub"],
        "herbaceous":  ["herb", "root"],
        "groundcover": ["groundcover"],
        "vine":        ["vine"],
    }

    _STRUCTURE_NAMES = {
        "pond":             "Pond",
        "swale":            "Bioswale",
        "rain_garden":      "Rain Garden",
        "rain_barrel":      "Rain Barrel",
        "native_bee_log":   "Native Bee Habitat Log",
        "bee_hotel":        "Bee Hotel",
        "brush_pile":       "Brush Pile",
        "snag":             "Snag (standing deadwood)",
        "rock_xeriscape":   "Rock Xeriscape",
        "native_lawn_patch":"Native Lawn Patch",
    }

    def _build_habitat_tips(
        self, *,
        native_ratio: float,
        n_keystone: int,
        n_host: int,
        n_bird: int,
        layers_present: set[str],
        habitat_struct_types: set[str],
        gap_months: list[int],
        placed_ids: set[int],
    ) -> str:
        """Return an HTML string of targeted tips for raising the habitat
        score. Each suggestion lists concrete Alberta-native examples
        pulled from the plant DB, excluding species already in the design."""
        try:
            from src.db.plants import get_connection
            conn = get_connection()
        except Exception:
            return "<p style='color:#90a4ae;'>Tips unavailable — plant DB not loaded.</p>"

        def examples_for_tag(tag: str, limit: int = 5) -> list[str]:
            """Native AB plants tagged `tag`, not yet placed, alphabetical.

            Schema v13: resolved via the plant_uses junction so the query
            is index-driven instead of a full-table LIKE scan.
            """
            sql = (
                "SELECT p.common_name FROM plants p "
                "JOIN plant_uses pu ON pu.plant_id = p.id "
                "JOIN uses u ON u.id = pu.use_id "
                "WHERE p.native_to_alberta = 1 AND u.key = ?"
            )
            params: list = [tag]
            if placed_ids:
                sql += " AND p.id NOT IN (" + ",".join("?" * len(placed_ids)) + ")"
                params += list(placed_ids)
            sql += " ORDER BY p.common_name"
            try:
                rows = conn.execute(sql, params).fetchall()
            except Exception:
                return []
            return [r["common_name"] for r in rows][:limit]

        def examples_for_layer(layer: str, limit: int = 5) -> list[str]:
            ptypes = self._LAYER_TO_PLANT_TYPES.get(layer, [])
            if not ptypes:
                return []
            placeholders = ",".join("?" * len(ptypes))
            sql = (
                "SELECT common_name FROM plants "
                f"WHERE native_to_alberta = 1 AND plant_type IN ({placeholders})"
            )
            params: list = list(ptypes)
            if placed_ids:
                sql += " AND id NOT IN (" + ",".join("?" * len(placed_ids)) + ")"
                params += list(placed_ids)
            sql += " ORDER BY common_name"
            try:
                rows = conn.execute(sql, params).fetchall()
            except Exception:
                return []
            return [r["common_name"] for r in rows][:limit]

        def examples_for_bloom_month(month_num: int, limit: int = 4) -> list[str]:
            """Native AB plants whose bloom_period covers `month_num`."""
            try:
                rows = conn.execute(
                    "SELECT common_name, bloom_period FROM plants "
                    "WHERE native_to_alberta = 1 AND bloom_period IS NOT NULL "
                    "  AND bloom_period <> ''"
                ).fetchall()
            except Exception:
                return []
            matches = []
            for r in rows:
                if month_num in self._parse_month_range(r["bloom_period"] or ""):
                    if r["common_name"] not in matches:
                        matches.append(r["common_name"])
            # Cheap filter against placed names (best-effort: we don't have
            # ids here, so we compare by name)
            placed_names: set[str] = set()
            if placed_ids:
                try:
                    qmarks = ",".join("?" * len(placed_ids))
                    placed_rows = conn.execute(
                        f"SELECT common_name FROM plants WHERE id IN ({qmarks})",
                        list(placed_ids)
                    ).fetchall()
                    placed_names = {r["common_name"] for r in placed_rows}
                except Exception:
                    pass
            matches = [m for m in matches if m not in placed_names]
            matches.sort()
            return matches[:limit]

        try:
            tips: list[str] = []
            month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                           "Jul","Aug","Sep","Oct","Nov","Dec"]

            if native_ratio < 0.70:
                pct = int(round(native_ratio * 100))
                tips.append(
                    f"<b style='color:#a5d6a7;'>Lift the native ratio ({pct}%).</b> "
                    f"Every cultivar you swap for an Alberta native raises this score "
                    f"directly. Aim for 70%+ native — that's the Tallamy threshold for "
                    f"functional habitat."
                )

            if n_keystone < 5:
                examples = examples_for_tag("keystone_species")
                if examples:
                    tips.append(
                        f"<b style='color:#a5d6a7;'>Add keystone species "
                        f"({n_keystone} of 5).</b> Keystones support the bulk of local "
                        f"insect biodiversity. Try: {', '.join(examples)}."
                    )

            if n_host < 10:
                examples = examples_for_tag("host_plant")
                if examples:
                    tips.append(
                        f"<b style='color:#a5d6a7;'>Add host plants "
                        f"({n_host} of 10).</b> Specialist caterpillars need specific "
                        f"native hosts. Try: {', '.join(examples)}."
                    )

            if n_bird < 10:
                examples = examples_for_tag("bird_food")
                if examples:
                    tips.append(
                        f"<b style='color:#a5d6a7;'>Add bird-food species "
                        f"({n_bird} of 10).</b> Berries, seed heads, and cones feed "
                        f"resident and migratory birds. Try: {', '.join(examples)}."
                    )

            missing_layers = {"overstory","shrub","herbaceous","groundcover","vine"} - layers_present
            # Vine is often optional; surface it last
            order = ["overstory","shrub","herbaceous","groundcover","vine"]
            for layer in order:
                if layer not in missing_layers:
                    continue
                examples = examples_for_layer(layer)
                if not examples:
                    continue
                tips.append(
                    f"<b style='color:#a5d6a7;'>Add a {layer} layer.</b> "
                    f"Try: {', '.join(examples)}."
                )

            missing_structs = [
                sid for sid in self._HABITAT_STRUCTURE_IDS
                if sid not in habitat_struct_types
            ]
            if len(habitat_struct_types) < 5 and missing_structs:
                names = [self._STRUCTURE_NAMES.get(s, s) for s in missing_structs[:5]]
                tips.append(
                    f"<b style='color:#a5d6a7;'>Add habitat structures "
                    f"({len(habitat_struct_types)} of 5).</b> Structural diversity "
                    f"shelters wildlife year-round. Try: {', '.join(names)}."
                )

            if gap_months:
                gap_lines = []
                for m in gap_months[:3]:  # cap at 3 most-urgent gaps
                    examples = examples_for_bloom_month(m)
                    if examples:
                        gap_lines.append(
                            f"<i>{month_names[m-1]}:</i> {', '.join(examples)}"
                        )
                if gap_lines:
                    tips.append(
                        "<b style='color:#a5d6a7;'>Fill nectar gaps.</b> "
                        "Plants blooming in the gap months — "
                        + "; ".join(gap_lines)
                    )

            if not tips:
                return (
                    "<p style='color:#a5d6a7;'>You're hitting every category. "
                    "Keep adding species diversity and small structural elements "
                    "(snags, brush piles, water features) as your habitat matures.</p>"
                )

            body = "<ul style='margin:0;padding-left:18px;'>"
            for t in tips:
                body += f"<li style='margin-bottom:6px;'>{t}</li>"
            body += "</ul>"
            return body
        finally:
            conn.close()

    @staticmethod
    def _parse_month_range(text: str) -> list[int]:
        """Parse 'June-August' / 'May' style strings to month numbers (1-12).

        Thin delegate to src.habitat_score.parse_month_range so the panel's
        bloom-month tips and the score's bloom component use identical
        parsing."""
        from src.habitat_score import parse_month_range
        return parse_month_range(text)
