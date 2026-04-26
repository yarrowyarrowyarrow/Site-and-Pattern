"""
analysis_panel.py — Side-panel tab for site analysis overlays.

Contains four inner tabs:
  A1: Sun Path / Shadow overlay
  A2: Sector Analysis layer
  A3: Slope / Contour indicator
  A4: Wind / Windbreak effect
"""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QFormLayout, QTabWidget, QSlider, QCheckBox, QColorDialog,
    QGroupBox, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


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

    # Season view
    season_changed = pyqtSignal(str)        # "Spring" | "Summer" | "Fall" | "Winter"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("QTabBar::tab { padding: 4px 8px; }")

        self._build_sun_tab()
        self._build_sector_tab()
        self._build_contour_tab()
        self._build_wind_tab()
        self._build_season_tab()

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
            "Show the sun's arc across the sky and shadow\n"
            "direction arrows for the selected date.\n"
            "Helps place shade-sensitive crops."
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
        self._sun_arc_radius.setToolTip("Radius of the sun path arc display in metres")
        arc_row.addWidget(self._sun_arc_radius)
        arc_row.addStretch()
        form.addRow(arc_row)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_show = QPushButton("Show Sun Path")
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
            "Draw directional sector wedges on the map for\n"
            "sun, wind, frost, noise, views — standard\n"
            "permaculture sector analysis."
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
        btn_show = QPushButton("Add Sectors")
        btn_show.setToolTip("Add selected sectors to map (accumulates — use Clear to reset)")
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
            "Draw manual contour lines to indicate terrain\n"
            "slope. Helps place swales, ponds, and water\n"
            "features correctly.\n\n"
            "Click points on the map to draw a contour line,\n"
            "double-click to finish. Add multiple lines at\n"
            "different elevations."
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
            "Mark prevailing wind direction. Windbreak\n"
            "structures and hedges show a shelter zone\n"
            "behind them (10× their height).\n\n"
            "Edmonton prevailing: NW in summer, W in winter."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

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

    # ═════════════════════════════════════════════════════════════════════════
    #  Season View
    # ═════════════════════════════════════════════════════════════════════════

    def _build_season_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Preview how your landscape looks in different\n"
            "seasons. Deciduous plants fade in winter,\n"
            "herbaceous perennials disappear, evergreens\n"
            "stay full."
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
