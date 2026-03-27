"""
plant_panel.py — Right-side panel: plant browser, search, filters, detail view,
place-on-map, and placed-plants list.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QFrame,
    QPushButton, QSizePolicy, QScrollArea, QSplitter,
    QFormLayout, QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter, QFont, QBrush

# ── Type colours ──────────────────────────────────────────────────────────────
_TYPE_COLORS: dict[str, str] = {
    "tree":        "#2e7d32",
    "shrub":       "#558b2f",
    "herb":        "#7cb342",
    "groundcover": "#c6a817",
    "vine":        "#00838f",
    "root":        "#6d4c41",
}

_TYPE_LABELS: dict[str, str] = {
    "tree":        "Tree",
    "shrub":       "Shrub",
    "herb":        "Herb / Perennial",
    "groundcover": "Groundcover",
    "vine":        "Vine",
    "root":        "Root / Bulb",
}

_SUN_LABELS: dict[str, str] = {
    "full_sun":      "Full Sun",
    "partial_shade": "Partial Shade",
    "full_shade":    "Full Shade",
}

_WATER_LABELS: dict[str, str] = {
    "low":    "Low",
    "medium": "Medium",
    "high":   "High",
}

_USE_LABELS: dict[str, str] = {
    "nitrogen_fixer":    "Nitrogen Fixer",
    "dynamic_accumulator": "Dynamic Accumulator",
    "pollinator":        "Pollinator Plant",
    "windbreak":         "Windbreak",
    "food_forest":       "Food Forest",
    "medicine":          "Medicinal",
    "wildlife_habitat":  "Wildlife Habitat",
    "pioneer":           "Pioneer",
    "biomass":           "Biomass / Chop-Drop",
    "groundcover":       "Groundcover",
    "pest_repellent":    "Pest Repellent",
}


def _type_icon(plant_type: str) -> QIcon:
    """Return a small coloured circle icon for the given plant type."""
    color_hex = _TYPE_COLORS.get(plant_type, "#78909c")
    pix = QPixmap(14, 14)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color_hex)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 12, 12)
    p.end()
    return QIcon(pix)


# ── Plant list item ───────────────────────────────────────────────────────────

_PLANT_ID_ROLE  = Qt.ItemDataRole.UserRole
_PLANT_OBJ_ROLE = Qt.ItemDataRole.UserRole + 1


def _make_list_item(plant: dict) -> QListWidgetItem:
    """Build a two-line QListWidgetItem for the results list."""
    zone_str = ""
    zmin = plant.get("hardiness_zone_min")
    zmax = plant.get("hardiness_zone_max")
    if zmin and zmax:
        zone_str = f"Z{zmin}–{zmax}"
    elif zmin:
        zone_str = f"Z{zmin}+"

    sci  = plant.get("scientific_name") or ""
    line = f"{sci}  ·  {zone_str}" if sci else zone_str

    item = QListWidgetItem()
    item.setIcon(_type_icon(plant.get("plant_type", "")))
    item.setText(f"{plant['common_name']}\n{line}")
    item.setData(_PLANT_ID_ROLE,  plant["id"])
    item.setData(_PLANT_OBJ_ROLE, plant)
    item.setSizeHint(QSize(0, 48))
    item.setToolTip(
        f"{plant['common_name']} ({sci})\n"
        f"Type: {_TYPE_LABELS.get(plant.get('plant_type',''), plant.get('plant_type',''))}\n"
        f"Zones: {zone_str}"
    )
    return item


# ── Main widget ───────────────────────────────────────────────────────────────

class PlantPanel(QWidget):
    """Right-hand panel for browsing, filtering and placing plants."""

    place_plant_requested = pyqtSignal(int, str)   # plant_id, common_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_zone: Optional[int] = None
        self._selected_plant: Optional[dict] = None
        self._placed_counts: dict[int, int] = {}   # plant_id -> count

        # Debounce timer for search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._run_search)

        self._build_ui()
        self._run_search()   # populate on startup

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QLabel("  Plant Browser")
        header.setFixedHeight(32)
        header.setStyleSheet(
            "background:#1b3a1b; color:#a5d6a7; font-weight:bold; "
            "font-size:13px; border-bottom:1px solid #2e4a2e;"
        )
        root.addWidget(header)

        # Main split: browser (top) vs detail+placed (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        # ── Top: search + filters + results ───────────────────────────────
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(8, 8, 8, 4)
        top_layout.setSpacing(4)

        # Search box
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search plants…")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_search_changed)
        top_layout.addWidget(self._search_box)

        # Filter row 1: Type + Sun
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self._type_combo = self._make_combo(
            [("All types", "")]
            + [(lbl, key) for key, lbl in _TYPE_LABELS.items()]
        )
        self._sun_combo = self._make_combo(
            [("Any sun", "")]
            + [(lbl, key) for key, lbl in _SUN_LABELS.items()]
        )
        row1.addWidget(self._type_combo)
        row1.addWidget(self._sun_combo)
        top_layout.addLayout(row1)

        # Filter row 2: Water + Use
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        self._water_combo = self._make_combo(
            [("Any water", "")]
            + [(lbl, key) for key, lbl in _WATER_LABELS.items()]
        )
        self._use_combo = self._make_combo(
            [("Any use", "")]
            + [(lbl, key) for key, lbl in _USE_LABELS.items()]
        )
        row2.addWidget(self._water_combo)
        row2.addWidget(self._use_combo)
        top_layout.addLayout(row2)

        # Zone filter toggle
        zone_row = QHBoxLayout()
        zone_row.setSpacing(4)
        self._zone_filter_btn = QPushButton("Filter by current zone")
        self._zone_filter_btn.setCheckable(True)
        self._zone_filter_btn.setToolTip(
            "When checked, only shows plants suitable for the detected hardiness zone"
        )
        self._zone_filter_btn.toggled.connect(self._run_search)
        self._zone_label = QLabel("Zone: —")
        self._zone_label.setStyleSheet("color: #78909c; font-size: 11px;")
        zone_row.addWidget(self._zone_filter_btn)
        zone_row.addWidget(self._zone_label)
        zone_row.addStretch()
        top_layout.addLayout(zone_row)

        # Result count label
        self._result_count = QLabel("Results: —")
        self._result_count.setStyleSheet("color: #78909c; font-size: 11px;")
        top_layout.addWidget(self._result_count)

        # Results list
        self._results_list = QListWidget()
        self._results_list.setSpacing(1)
        self._results_list.setUniformItemSizes(False)
        self._results_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._results_list.currentItemChanged.connect(self._on_selection_changed)
        self._results_list.itemDoubleClicked.connect(self._on_place_clicked)
        top_layout.addWidget(self._results_list)

        splitter.addWidget(top)

        # ── Bottom: detail view + placed plants ───────────────────────────
        bottom = QWidget()
        bot_layout = QVBoxLayout(bottom)
        bot_layout.setContentsMargins(8, 4, 8, 8)
        bot_layout.setSpacing(6)

        # Detail group
        self._detail_group = QGroupBox("Selected Plant")
        self._detail_group.setVisible(False)
        detail_layout = QFormLayout(self._detail_group)
        detail_layout.setSpacing(4)
        detail_layout.setContentsMargins(8, 8, 8, 8)

        self._d_common  = QLabel()
        self._d_sci     = QLabel()
        self._d_type    = QLabel()
        self._d_zones   = QLabel()
        self._d_sun     = QLabel()
        self._d_water   = QLabel()
        self._d_uses    = QLabel()
        self._d_uses.setWordWrap(True)
        self._d_notes   = QLabel()
        self._d_notes.setWordWrap(True)
        self._d_notes.setStyleSheet("color: #90a4ae; font-size: 11px;")

        bold_font = QFont()
        bold_font.setBold(True)
        self._d_common.setFont(bold_font)

        detail_layout.addRow("",          self._d_common)
        detail_layout.addRow("Species:",  self._d_sci)
        detail_layout.addRow("Type:",     self._d_type)
        detail_layout.addRow("Zones:",    self._d_zones)
        detail_layout.addRow("Sun:",      self._d_sun)
        detail_layout.addRow("Water:",    self._d_water)
        detail_layout.addRow("Uses:",     self._d_uses)
        detail_layout.addRow("Notes:",    self._d_notes)

        bot_layout.addWidget(self._detail_group)

        # Place on Map button
        self._place_btn = QPushButton("Place on Map")
        self._place_btn.setEnabled(False)
        self._place_btn.setToolTip("Click to enter plant-placement mode on the map")
        self._place_btn.clicked.connect(self._on_place_clicked)
        self._place_btn.setStyleSheet(_PLACE_BTN_STYLE)
        bot_layout.addWidget(self._place_btn)

        # Placed plants section
        placed_header = QLabel("On This Design")
        placed_header.setStyleSheet(
            "color: #a5d6a7; font-weight: bold; border-top: 1px solid #2e4a2e; "
            "padding-top: 6px;"
        )
        bot_layout.addWidget(placed_header)

        self._placed_count_label = QLabel("None placed yet")
        self._placed_count_label.setStyleSheet("color: #78909c; font-size: 11px;")
        bot_layout.addWidget(self._placed_count_label)

        self._placed_list = QListWidget()
        self._placed_list.setMaximumHeight(120)
        self._placed_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._placed_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bot_layout.addWidget(self._placed_list)

        splitter.addWidget(bottom)
        splitter.setSizes([320, 240])

    # ── Filter helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _make_combo(items: list[tuple[str, str]]) -> QComboBox:
        cb = QComboBox()
        for label, data in items:
            cb.addItem(label, userData=data)
        cb.currentIndexChanged.connect(lambda _: None)  # placeholder
        return cb

    def _combo_value(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return data if data else ""

    # ── Search / filter ───────────────────────────────────────────────────────

    def _on_search_changed(self, _text: str):
        self._search_timer.start()

    def _run_search(self):
        try:
            from src.db.plants import search_plants
        except Exception:
            return

        # Wire filter combo signals on first run
        if not hasattr(self, "_filters_wired"):
            self._type_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._sun_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._water_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._use_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._filters_wired = True

        zone = self._current_zone if self._zone_filter_btn.isChecked() else None

        try:
            plants = search_plants(
                query       = self._search_box.text().strip(),
                plant_type  = self._combo_value(self._type_combo),
                sun_req     = self._combo_value(self._sun_combo),
                water_needs = self._combo_value(self._water_combo),
                perm_use    = self._combo_value(self._use_combo),
                zone        = zone,
            )
        except Exception as exc:
            self._result_count.setText(f"Error: {exc}")
            return

        self._results_list.clear()
        for p in plants:
            self._results_list.addItem(_make_list_item(p))

        n = len(plants)
        self._result_count.setText(f"Results: {n}")

    # ── Selection / detail ────────────────────────────────────────────────────

    def _on_selection_changed(self, current: Optional[QListWidgetItem], _prev):
        if current is None:
            self._selected_plant = None
            self._detail_group.setVisible(False)
            self._place_btn.setEnabled(False)
            return

        plant = current.data(_PLANT_OBJ_ROLE)
        self._selected_plant = plant
        self._show_detail(plant)
        self._place_btn.setEnabled(True)

    def _show_detail(self, plant: dict):
        zmin = plant.get("hardiness_zone_min")
        zmax = plant.get("hardiness_zone_max")
        zone_str = f"Z{zmin} – Z{zmax}" if zmin and zmax else "—"

        uses_raw = plant.get("permaculture_uses") or ""
        uses_nice = ", ".join(
            _USE_LABELS.get(u.strip(), u.strip())
            for u in uses_raw.split(",") if u.strip()
        )

        self._d_common.setText(plant.get("common_name", ""))
        self._d_sci.setText(plant.get("scientific_name") or "—")
        self._d_type.setText(_TYPE_LABELS.get(plant.get("plant_type", ""), "—"))
        self._d_zones.setText(zone_str)
        self._d_sun.setText(_SUN_LABELS.get(plant.get("sun_requirement", ""), "—"))
        self._d_water.setText(_WATER_LABELS.get(plant.get("water_needs", ""), "—"))
        self._d_uses.setText(uses_nice or "—")
        self._d_notes.setText(plant.get("notes") or "")

        self._detail_group.setVisible(True)

    # ── Place on map ──────────────────────────────────────────────────────────

    def _on_place_clicked(self, _item=None):
        if self._selected_plant:
            self.place_plant_requested.emit(
                self._selected_plant["id"],
                self._selected_plant["common_name"],
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def set_zone(self, zone: Optional[int]):
        """Called by the main window when the hardiness zone changes."""
        self._current_zone = zone
        if zone:
            self._zone_label.setText(f"Zone {zone}")
            self._zone_filter_btn.setToolTip(
                f"Filter to Zone {zone}-compatible plants"
            )
        else:
            self._zone_label.setText("Zone: —")
        if self._zone_filter_btn.isChecked():
            self._run_search()

    def on_plant_placed(self, plant_id: int, common_name: str):
        """Notify the panel that a plant was placed on the map."""
        self._placed_counts[plant_id] = self._placed_counts.get(plant_id, 0) + 1
        self._refresh_placed_list()

    def clear_placed(self):
        """Clear the placed-plants list (e.g. on New project)."""
        self._placed_counts.clear()
        self._refresh_placed_list()

    def load_placed(self, plants: list[dict]):
        """Reload placed-plants list from a loaded project."""
        self._placed_counts.clear()
        for p in plants:
            pid = p.get("plant_id", 0)
            self._placed_counts[pid] = self._placed_counts.get(pid, 0) + 1
        self._refresh_placed_list()

    def _refresh_placed_list(self):
        self._placed_list.clear()
        if not self._placed_counts:
            self._placed_count_label.setText("None placed yet")
            return

        # Look up names
        try:
            from src.db.plants import get_plant
            total = 0
            for pid, count in sorted(self._placed_counts.items()):
                p = get_plant(pid)
                name = p["common_name"] if p else f"Plant #{pid}"
                item = QListWidgetItem(f"{name}  ×{count}")
                item.setIcon(_type_icon(p["plant_type"] if p else ""))
                self._placed_list.addItem(item)
                total += count
            self._placed_count_label.setText(
                f"{total} plant{'s' if total != 1 else ''} placed"
                f" ({len(self._placed_counts)} species)"
            )
        except Exception:
            self._placed_count_label.setText(
                f"{sum(self._placed_counts.values())} plants placed"
            )


# ── Stylesheets ───────────────────────────────────────────────────────────────

_RESULTS_LIST_STYLE = """
QListWidget {
    background: #1a2a1a;
    border: 1px solid #2e4a2e;
    border-radius: 4px;
    color: #c8e6c9;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 3px 6px;
    border-bottom: 1px solid #1f341f;
}
QListWidget::item:selected {
    background: #2e5a2e;
    color: #e8f5e9;
}
QListWidget::item:hover {
    background: #243824;
}
"""

_PLACE_BTN_STYLE = """
QPushButton {
    background: #2e7d32;
    color: #e8f5e9;
    border: none;
    border-radius: 4px;
    padding: 7px 12px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover  { background: #388e3c; }
QPushButton:pressed { background: #1b5e20; }
QPushButton:disabled { background: #2a3a2a; color: #4a6a4a; }
"""
