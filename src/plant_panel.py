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
    QFormLayout, QGroupBox, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
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

_DECIDUOUS_LABELS: dict[str, str] = {
    "deciduous":  "Deciduous",
    "evergreen":  "Evergreen",
    "herbaceous": "Herbaceous (dies back)",
}

_LIFECYCLE_LABELS: dict[str, str] = {
    "perennial": "Perennial",
    "annual":    "Annual",
    "biennial":  "Biennial",
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

        # Permapeople API keys (set via set_api_keys)
        self._pp_key_id:     str = ""
        self._pp_key_secret: str = ""
        self._pp_thread:     Optional[QThread]  = None
        self._pp_worker                         = None
        self._pp_pending_plants: list[dict]     = []   # search results from API

        # Debounce timer for local search
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

        # Main split: browser tabs (top) vs detail+placed (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        # ── Tab widget: Local | Permapeople ───────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(_TAB_STYLE)
        splitter.addWidget(self._tabs)

        # ── Tab 0: Local database ─────────────────────────────────────────
        local_tab = QWidget()
        top_layout = QVBoxLayout(local_tab)
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

        # Zone + native filter row
        zone_row = QHBoxLayout()
        zone_row.setSpacing(4)
        self._zone_filter_btn = QPushButton("Filter by zone")
        self._zone_filter_btn.setCheckable(True)
        self._zone_filter_btn.setToolTip(
            "When checked, only shows plants suitable for the detected hardiness zone"
        )
        self._zone_filter_btn.toggled.connect(self._run_search)
        self._zone_label = QLabel("Zone: —")
        self._zone_label.setStyleSheet("color: #78909c; font-size: 11px;")
        self._native_filter_btn = QPushButton("Native AB")
        self._native_filter_btn.setCheckable(True)
        self._native_filter_btn.setToolTip("Only show plants native to Alberta")
        self._native_filter_btn.toggled.connect(self._run_search)
        zone_row.addWidget(self._zone_filter_btn)
        zone_row.addWidget(self._native_filter_btn)
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

        self._tabs.addTab(local_tab, "Local")

        # ── Tab 1: Permapeople API ─────────────────────────────────────────
        pp_tab = QWidget()
        pp_layout = QVBoxLayout(pp_tab)
        pp_layout.setContentsMargins(8, 8, 8, 4)
        pp_layout.setSpacing(6)

        pp_search_row = QHBoxLayout()
        pp_search_row.setSpacing(4)
        self._pp_search_box = QLineEdit()
        self._pp_search_box.setPlaceholderText("Search Permapeople…")
        self._pp_search_box.setClearButtonEnabled(True)
        self._pp_search_box.returnPressed.connect(self._pp_search)
        self._pp_search_btn = QPushButton("Search")
        self._pp_search_btn.setFixedWidth(60)
        self._pp_search_btn.clicked.connect(self._pp_search)
        pp_search_row.addWidget(self._pp_search_box)
        pp_search_row.addWidget(self._pp_search_btn)
        pp_layout.addLayout(pp_search_row)

        self._pp_status = QLabel("Enter a search term and press Search.")
        self._pp_status.setStyleSheet("color: #78909c; font-size: 11px;")
        self._pp_status.setWordWrap(True)
        pp_layout.addWidget(self._pp_status)

        self._pp_results_list = QListWidget()
        self._pp_results_list.setSpacing(1)
        self._pp_results_list.setUniformItemSizes(False)
        self._pp_results_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._pp_results_list.currentItemChanged.connect(self._pp_on_selection_changed)
        pp_layout.addWidget(self._pp_results_list)

        self._pp_import_btn = QPushButton("Import to Local Database")
        self._pp_import_btn.setEnabled(False)
        self._pp_import_btn.setToolTip(
            "Save selected Permapeople plant to your local database so you can place it on the map"
        )
        self._pp_import_btn.clicked.connect(self._pp_import)
        self._pp_import_btn.setStyleSheet(_PLACE_BTN_STYLE)
        pp_layout.addWidget(self._pp_import_btn)

        self._tabs.addTab(pp_tab, "Permapeople")

        # Show a lock icon on the Permapeople tab if no keys configured
        self._pp_update_tab_label()

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
        self._d_spacing = QLabel()
        self._d_height  = QLabel()
        self._d_bloom   = QLabel()
        self._d_fruit   = QLabel()
        self._d_edible  = QLabel()
        self._d_growth  = QLabel()
        self._d_ph      = QLabel()
        self._d_native  = QLabel()
        self._d_notes   = QLabel()
        self._d_notes.setWordWrap(True)
        self._d_notes.setStyleSheet("color: #90a4ae; font-size: 11px;")
        self._d_companions = QLabel()
        self._d_companions.setWordWrap(True)
        self._d_companions.setStyleSheet("font-size: 11px;")

        bold_font = QFont()
        bold_font.setBold(True)
        self._d_common.setFont(bold_font)

        italic_font = QFont()
        italic_font.setItalic(True)
        self._d_sci.setFont(italic_font)
        self._d_sci.setStyleSheet("color: #90a4ae;")

        detail_layout.addRow("",             self._d_common)
        detail_layout.addRow("Species:",     self._d_sci)
        detail_layout.addRow("Type:",        self._d_type)
        detail_layout.addRow("Zones:",       self._d_zones)
        detail_layout.addRow("Sun:",         self._d_sun)
        detail_layout.addRow("Water:",       self._d_water)
        detail_layout.addRow("Spacing:",     self._d_spacing)
        detail_layout.addRow("Height:",      self._d_height)
        detail_layout.addRow("Bloom:",       self._d_bloom)
        detail_layout.addRow("Fruit:",       self._d_fruit)
        detail_layout.addRow("Edible:",      self._d_edible)
        detail_layout.addRow("Growth:",      self._d_growth)
        detail_layout.addRow("Soil pH:",     self._d_ph)
        detail_layout.addRow("Native AB:",   self._d_native)
        detail_layout.addRow("Uses:",        self._d_uses)
        detail_layout.addRow("Companions:",  self._d_companions)
        detail_layout.addRow("Notes:",       self._d_notes)

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
                native_only = self._native_filter_btn.isChecked(),
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

        ph_min = plant.get("soil_ph_min")
        ph_max = plant.get("soil_ph_max")
        ph_str = f"{ph_min} – {ph_max}" if ph_min and ph_max else "—"

        edible_raw = plant.get("edible_parts") or ""
        edible_str = edible_raw.replace(",", ", ") if edible_raw else "—"

        native_ab = plant.get("native_to_alberta")
        native_str = "Yes" if native_ab else "No"
        if native_ab:
            self._d_native.setStyleSheet("color: #81c784; font-weight: bold;")
        else:
            self._d_native.setStyleSheet("color: #78909c;")

        self._d_common.setText(plant.get("common_name", ""))
        self._d_sci.setText(plant.get("scientific_name") or "—")
        self._d_type.setText(_TYPE_LABELS.get(plant.get("plant_type", ""), "—"))
        self._d_zones.setText(zone_str)
        self._d_sun.setText(_SUN_LABELS.get(plant.get("sun_requirement", ""), "—"))
        self._d_water.setText(_WATER_LABELS.get(plant.get("water_needs", ""), "—"))
        spacing = plant.get("spacing_meters")
        height  = plant.get("mature_height_meters")
        self._d_spacing.setText(f"{spacing} m" if spacing else "—")
        self._d_height.setText(f"{height} m" if height else "—")
        self._d_bloom.setText(plant.get("bloom_period") or "—")
        self._d_fruit.setText(plant.get("fruit_period") or "—")
        self._d_edible.setText(edible_str)
        self._d_growth.setText(
            _DECIDUOUS_LABELS.get(plant.get("deciduous_evergreen", ""), "—")
            + "  ·  "
            + _LIFECYCLE_LABELS.get(plant.get("perennial_or_annual", ""), "—")
        )
        self._d_ph.setText(ph_str)
        self._d_native.setText(native_str)
        self._d_uses.setText(uses_nice or "—")
        self._d_notes.setText(plant.get("notes") or "")

        # Load companion info
        self._load_companions(plant.get("id"))

        self._detail_group.setVisible(True)

    def _load_companions(self, plant_id: Optional[int]):
        if not plant_id:
            self._d_companions.setText("—")
            return
        try:
            from src.db.plants import get_companions
            data = get_companions(plant_id)
            friends = [p["common_name"] for p in data.get("friends", [])]
            enemies = [p["common_name"] for p in data.get("enemies", [])]
            parts = []
            if friends:
                parts.append(
                    f'<span style="color:#81c784">+ {", ".join(friends)}</span>'
                )
            if enemies:
                parts.append(
                    f'<span style="color:#ef9a9a">– {", ".join(enemies)}</span>'
                )
            self._d_companions.setText("<br>".join(parts) if parts else "—")
            self._d_companions.setTextFormat(Qt.TextFormat.RichText)
        except Exception:
            self._d_companions.setText("—")

    # ── Place on map ──────────────────────────────────────────────────────────

    def _on_place_clicked(self, _item=None):
        if self._selected_plant:
            self.place_plant_requested.emit(
                self._selected_plant["id"],
                self._selected_plant["common_name"],
            )

    # ── Permapeople tab ────────────────────────────────────────────────────────

    def _pp_update_tab_label(self):
        has_keys = bool(self._pp_key_id and self._pp_key_secret)
        label = "Permapeople" if has_keys else "Permapeople 🔑"
        self._tabs.setTabText(1, label)
        if not has_keys:
            self._pp_status.setText(
                "No API key configured. Open  Settings → Permapeople API  to add your key."
            )
            self._pp_search_btn.setEnabled(False)
        else:
            if self._pp_status.text().startswith("No API"):
                self._pp_status.setText("Enter a search term and press Search.")
            self._pp_search_btn.setEnabled(True)

    def _pp_search(self):
        query = self._pp_search_box.text().strip()
        if not query:
            return
        if not (self._pp_key_id and self._pp_key_secret):
            self._pp_status.setText("API key not set. Go to Settings first.")
            return

        # Cancel any running thread
        if self._pp_thread and self._pp_thread.isRunning():
            self._pp_thread.quit()
            self._pp_thread.wait()

        self._pp_results_list.clear()
        self._pp_import_btn.setEnabled(False)
        self._pp_status.setText(f"Searching for "{query}"…")
        self._pp_search_btn.setEnabled(False)

        from src.api.permapeople import PermapeopleWorker
        self._pp_thread = QThread(self)
        self._pp_worker = PermapeopleWorker(self._pp_key_id, self._pp_key_secret)
        self._pp_worker.set_query(query)
        self._pp_worker.moveToThread(self._pp_thread)

        self._pp_thread.started.connect(self._pp_worker.search)
        self._pp_worker.results_ready.connect(self._pp_on_results)
        self._pp_worker.error_occurred.connect(self._pp_on_error)
        self._pp_worker.finished.connect(self._pp_thread.quit)
        self._pp_worker.finished.connect(
            lambda: self._pp_search_btn.setEnabled(True)
        )

        self._pp_thread.start()

    def _pp_on_results(self, plants: list):
        self._pp_pending_plants = plants
        self._pp_results_list.clear()
        if not plants:
            self._pp_status.setText("No results found.")
            return
        for p in plants:
            item = QListWidgetItem()
            item.setIcon(_type_icon(p.get("plant_type", "")))
            sci = p.get("scientific_name") or ""
            label = f"{p.get('common_name', 'Unknown')}\n{sci}"
            item.setText(label)
            item.setData(_PLANT_OBJ_ROLE, p)
            item.setSizeHint(QSize(0, 48))
            self._pp_results_list.addItem(item)
        self._pp_status.setText(f"{len(plants)} result{'s' if len(plants) != 1 else ''} found.")

    def _pp_on_error(self, msg: str):
        self._pp_status.setText(f"Error: {msg}")

    def _pp_on_selection_changed(self, current: Optional[QListWidgetItem], _prev):
        if current is None:
            self._pp_import_btn.setEnabled(False)
            self._selected_plant = None
            self._detail_group.setVisible(False)
            self._place_btn.setEnabled(False)
            return
        plant = current.data(_PLANT_OBJ_ROLE)
        # Show in detail panel (no DB id yet, so place btn stays off)
        self._selected_plant = None
        self._show_detail(plant)
        self._place_btn.setEnabled(False)
        self._pp_import_btn.setEnabled(True)

    def _pp_import(self):
        """Import the selected Permapeople plant into the local database."""
        row = self._pp_results_list.currentRow()
        if row < 0 or row >= len(self._pp_pending_plants):
            return
        plant = self._pp_pending_plants[row]
        try:
            from src.db.plants import get_connection
            conn = get_connection()
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO plants
                       (common_name, scientific_name, plant_type,
                        hardiness_zone_min, hardiness_zone_max,
                        sun_requirement, water_needs,
                        native_region, permaculture_uses,
                        spacing_meters, mature_height_meters, notes,
                        bloom_period, fruit_period, native_to_alberta,
                        edible_parts, deciduous_evergreen,
                        soil_ph_min, soil_ph_max, perennial_or_annual)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        plant.get("common_name") or "Unknown",
                        plant.get("scientific_name"),
                        plant.get("plant_type") or "herb",
                        plant.get("hardiness_zone_min"),
                        plant.get("hardiness_zone_max"),
                        plant.get("sun_requirement"),
                        plant.get("water_needs"),
                        plant.get("native_region"),
                        plant.get("permaculture_uses"),
                        plant.get("spacing_meters"),
                        plant.get("mature_height_meters"),
                        plant.get("notes"),
                        plant.get("bloom_period"),
                        plant.get("fruit_period"),
                        0,  # not native to alberta
                        plant.get("edible_parts"),
                        plant.get("deciduous_evergreen"),
                        plant.get("soil_ph_min"),
                        plant.get("soil_ph_max"),
                        plant.get("perennial_or_annual"),
                    )
                )
                conn.commit()
                new_id = cur.lastrowid
            finally:
                conn.close()

            self._pp_status.setText(
                f"Imported "{plant.get('common_name')}" → Local database."
            )
            # Refresh local search and switch to Local tab
            self._run_search()
            self._tabs.setCurrentIndex(0)

            # Select the newly imported plant in the local list
            for i in range(self._results_list.count()):
                item = self._results_list.item(i)
                if item and item.data(_PLANT_ID_ROLE) == new_id:
                    self._results_list.setCurrentItem(item)
                    break

        except Exception as exc:
            self._pp_status.setText(f"Import failed: {exc}")

    # ── Public API ────────────────────────────────────────────────────────────

    def set_api_keys(self, key_id: str, key_secret: str):
        """Called by the main window after the user saves API credentials."""
        self._pp_key_id     = key_id
        self._pp_key_secret = key_secret
        self._pp_update_tab_label()

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

    def on_plant_removed(self, plant_id: int):
        """Notify the panel that a plant marker was removed from the map."""
        if plant_id in self._placed_counts:
            self._placed_counts[plant_id] -= 1
            if self._placed_counts[plant_id] <= 0:
                del self._placed_counts[plant_id]
        self._refresh_placed_list()

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

_TAB_STYLE = """
QTabWidget::pane {
    border: none;
    background: #1a2a1a;
}
QTabBar::tab {
    background: #1b2b1b;
    color: #78909c;
    border: 1px solid #2e4a2e;
    border-bottom: none;
    padding: 5px 12px;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #1a2a1a;
    color: #a5d6a7;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: #243824;
    color: #c8e6c9;
}
"""
