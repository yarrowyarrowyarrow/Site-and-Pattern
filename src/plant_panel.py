from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .db import plants


TYPE_COLORS = {
    "tree": "#228B22",
    "shrub": "#6B8E23",
    "herb": "#DAA520",
    "groundcover": "#32CD32",
    "vine": "#8B4513",
    "root": "#CD853F",
}


class PlantPanel(QWidget):
    placeRequested = pyqtSignal(int, str, str)  # id, name, type

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plant = None
        self.placed_plants = {}  # {plant_id: {"name": ..., "count": ...}}
        self._build_ui()
        self._load_filters()
        self._do_search()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search plants...")
        self.search_input.textChanged.connect(self._do_search)
        layout.addWidget(self.search_input)

        # Filters row
        filter_layout = QHBoxLayout()
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", None)
        self.type_filter.currentIndexChanged.connect(self._do_search)
        filter_layout.addWidget(self.type_filter)

        self.sun_filter = QComboBox()
        self.sun_filter.addItem("All Sun", None)
        for s in ["full_sun", "partial_shade", "full_shade"]:
            self.sun_filter.addItem(s.replace("_", " ").title(), s)
        self.sun_filter.currentIndexChanged.connect(self._do_search)
        filter_layout.addWidget(self.sun_filter)

        self.water_filter = QComboBox()
        self.water_filter.addItem("All Water", None)
        for w in ["low", "medium", "high"]:
            self.water_filter.addItem(w.title(), w)
        self.water_filter.currentIndexChanged.connect(self._do_search)
        filter_layout.addWidget(self.water_filter)
        layout.addLayout(filter_layout)

        # Splitter for list and detail
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Results list
        self.results_list = QListWidget()
        self.results_list.currentItemChanged.connect(self._on_plant_selected)
        splitter.addWidget(self.results_list)

        # Detail area
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(200)
        detail_layout.addWidget(self.detail_text)

        self.place_btn = QPushButton("Place on Map")
        self.place_btn.setEnabled(False)
        self.place_btn.clicked.connect(self._on_place)
        detail_layout.addWidget(self.place_btn)

        splitter.addWidget(detail_widget)

        # Placed plants section
        placed_group = QGroupBox("Placed Plants")
        placed_layout = QVBoxLayout(placed_group)
        self.placed_list = QListWidget()
        self.placed_list.setMaximumHeight(120)
        placed_layout.addWidget(self.placed_list)
        splitter.addWidget(placed_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter)

    def _load_filters(self):
        for t in plants.get_plant_types():
            self.type_filter.addItem(t.title(), t)

    def _do_search(self):
        query = self.search_input.text().strip()
        plant_type = self.type_filter.currentData()
        sun = self.sun_filter.currentData()
        water = self.water_filter.currentData()

        results = plants.search_plants(query=query, plant_type=plant_type, sun=sun, water=water)
        self.results_list.clear()
        for p in results:
            color = TYPE_COLORS.get(p["plant_type"], "#888")
            zone_range = f"Z{p['hardiness_zone_min']}-{p['hardiness_zone_max']}"
            text = f"{p['common_name']}  ({p['scientific_name']})  {zone_range}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.results_list.addItem(item)

    def _on_plant_selected(self, current, previous):
        if not current:
            self.current_plant = None
            self.detail_text.clear()
            self.place_btn.setEnabled(False)
            return

        p = current.data(Qt.ItemDataRole.UserRole)
        self.current_plant = p
        self.place_btn.setEnabled(True)

        lines = [
            f"<b>{p['common_name']}</b> (<i>{p['scientific_name']}</i>)",
            f"<b>Type:</b> {p['plant_type']}  |  <b>Zone:</b> {p['hardiness_zone_min']}-{p['hardiness_zone_max']}",
            f"<b>Sun:</b> {(p['sun_requirement'] or '').replace('_', ' ')}  |  <b>Water:</b> {p['water_needs']}",
            f"<b>Height:</b> {p['mature_height_meters']}m  |  <b>Spacing:</b> {p['spacing_meters']}m",
        ]
        if p.get("bloom_period"):
            lines.append(f"<b>Bloom:</b> {p['bloom_period']}")
        if p.get("fruit_period"):
            lines.append(f"<b>Fruit:</b> {p['fruit_period']}")
        if p.get("edible_parts"):
            lines.append(f"<b>Edible:</b> {p['edible_parts']}")
        if p.get("permaculture_uses"):
            lines.append(f"<b>Uses:</b> {p['permaculture_uses'].replace(',', ', ')}")
        if p.get("notes"):
            lines.append(f"<br>{p['notes']}")

        self.detail_text.setHtml("<br>".join(lines))

    def _on_place(self):
        if self.current_plant:
            p = self.current_plant
            self.placeRequested.emit(p["id"], p["common_name"], p["plant_type"])

    def add_placed_plant(self, plant_id, name):
        if plant_id in self.placed_plants:
            self.placed_plants[plant_id]["count"] += 1
        else:
            self.placed_plants[plant_id] = {"name": name, "count": 1}
        self._refresh_placed_list()

    def _refresh_placed_list(self):
        self.placed_list.clear()
        for pid, info in sorted(self.placed_plants.items(), key=lambda x: x[1]["name"]):
            self.placed_list.addItem(f"{info['name']} x{info['count']}")

    def clear_placed(self):
        self.placed_plants.clear()
        self.placed_list.clear()
