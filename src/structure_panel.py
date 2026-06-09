"""
structure_panel.py — Side-panel tab for browsing and placing structures,
drawing hedgerows, and creating custom shapes on the map.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QFrame, QPushButton,
    QSizePolicy, QScrollArea, QGroupBox, QComboBox,
    QSpinBox, QDoubleSpinBox, QColorDialog, QFormLayout,
    QTextEdit, QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPixmap, QPainter, QFont, QIcon

from src.db.structures import (
    STRUCTURES, STRUCTURE_CATEGORIES, get_structure, get_all_structures,
)


# ── Colour helpers ────────────────────────────────────────────────────────────

def _color_icon(hex_color: str, size: int = 16) -> QIcon:
    """Create a small square icon filled with the given colour."""
    pm = QPixmap(size, size)
    pm.fill(QColor(hex_color))
    return QIcon(pm)


# ═════════════════════════════════════════════════════════════════════════════
#  Structures tab  (S1)
# ═════════════════════════════════════════════════════════════════════════════

class StructurePanel(QWidget):
    """
    Panel for browsing structures, hedgerow drawing, and custom shapes.
    Contains three inner tabs: Structures | Hedgerow | Shapes.
    """

    # Signals
    place_structure_requested = pyqtSignal(dict)        # structure def dict
    place_hedgerow_requested = pyqtSignal(dict)         # {species, style, color}
    place_shape_requested = pyqtSignal(dict)            # {fill, stroke, label, shape_type}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        from src.fill_tab_widget import FillTabWidget
        self._tabs = FillTabWidget()
        # Document mode lets the bar span the full width so FillTabWidget can
        # stretch Structures/Hedgerow/Shapes edge-to-edge.
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab { padding: 4px 10px; }"
        )

        # ── Tab 1: Structures ─────────────────────────────────────────
        self._structures_tab = QWidget()
        self._build_structures_tab()
        self._tabs.addTab(self._structures_tab, "Structures")

        # ── Tab 2: Hedgerow ───────────────────────────────────────────
        self._hedgerow_tab = QWidget()
        self._build_hedgerow_tab()
        self._tabs.addTab(self._hedgerow_tab, "Hedgerow")

        # ── Tab 3: Shapes ─────────────────────────────────────────────
        self._shapes_tab = QWidget()
        self._build_shapes_tab()
        self._tabs.addTab(self._shapes_tab, "Shapes")

        layout.addWidget(self._tabs)

    # ── Structures tab ────────────────────────────────────────────────

    def _build_structures_tab(self):
        layout = QVBoxLayout(self._structures_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search structures...")
        self._search.textChanged.connect(self._filter_structures)
        layout.addWidget(self._search)

        # Category filter
        self._cat_combo = QComboBox()
        self._cat_combo.addItem("All Categories")
        for cat in STRUCTURE_CATEGORIES:
            self._cat_combo.addItem(cat)
        self._cat_combo.currentTextChanged.connect(self._filter_structures)
        layout.addWidget(self._cat_combo)

        # Structure list
        self._struct_list = QListWidget()
        self._struct_list.setAlternatingRowColors(True)
        self._struct_list.setStyleSheet(
            "QListWidget { background: #1a2a1a; border: 1px solid #2e4a2e; }"
            "QListWidget::item { padding: 6px 4px; border-bottom: 1px solid #1e3a1e; }"
            "QListWidget::item:selected { background: #2e5a2e; }"
            "QListWidget::item:alternate { background: #1e2e1e; }"
        )
        self._struct_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._struct_list, 1)

        # Detail area
        self._detail_frame = QFrame()
        self._detail_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self._detail_frame.setStyleSheet(
            "QFrame { background: #1e2e1e; border: 1px solid #2e4a2e; border-radius: 4px; padding: 6px; }"
        )
        detail_layout = QVBoxLayout(self._detail_frame)
        detail_layout.setContentsMargins(6, 6, 6, 6)
        detail_layout.setSpacing(4)

        self._detail_name = QLabel("")
        self._detail_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #a5d6a7;")
        detail_layout.addWidget(self._detail_name)

        self._detail_desc = QLabel("")
        self._detail_desc.setWordWrap(True)
        self._detail_desc.setStyleSheet("color: #90a4ae; font-size: 11px;")
        detail_layout.addWidget(self._detail_desc)

        self._detail_info = QLabel("")
        self._detail_info.setStyleSheet("color: #78909c; font-size: 11px;")
        detail_layout.addWidget(self._detail_info)

        layout.addWidget(self._detail_frame)

        # Size override
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size (m):"))
        self._size_spin = QDoubleSpinBox()
        self._size_spin.setRange(0.5, 50.0)
        self._size_spin.setSingleStep(0.5)
        self._size_spin.setValue(3.0)
        size_row.addWidget(self._size_spin)
        layout.addLayout(size_row)

        # Place button
        self._btn_place = QPushButton("Place on Map")
        self._btn_place.setEnabled(False)
        self._btn_place.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }"
            "QPushButton:disabled { background: #263238; color: #546e7a; border-color: #37474f; }"
        )
        self._btn_place.clicked.connect(self._on_place_clicked)
        layout.addWidget(self._btn_place)

        # Existing on-site trees/buildings moved to Site → Shade (V1.59), where
        # they sit alongside the shade map and OSM import.

        self._populate_structures()

    def _populate_structures(self):
        self._struct_list.clear()
        for s in STRUCTURES:
            item = QListWidgetItem(f"{s['icon']}  {s['name']}")
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setToolTip(s["description"])
            self._struct_list.addItem(item)

    def _filter_structures(self):
        text = self._search.text().lower()
        cat = self._cat_combo.currentText()
        self._struct_list.clear()
        for s in STRUCTURES:
            if cat != "All Categories" and s["category"] != cat:
                continue
            if text and text not in s["name"].lower() and text not in s["description"].lower():
                continue
            item = QListWidgetItem(f"{s['icon']}  {s['name']}")
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setToolTip(s["description"])
            self._struct_list.addItem(item)

    def _on_selection_changed(self, current, _prev):
        if not current:
            self._btn_place.setEnabled(False)
            self._detail_name.setText("")
            self._detail_desc.setText("")
            self._detail_info.setText("")
            return
        sid = current.data(Qt.ItemDataRole.UserRole)
        s = get_structure(sid)
        if not s:
            return
        self._btn_place.setEnabled(True)
        self._detail_name.setText(f"{s['icon']}  {s['name']}")
        self._detail_desc.setText(s["description"])
        info_parts = [
            f"Category: {s['category']}",
            f"Default size: {s['size_m']}m",
        ]
        if s.get("maintenance_hours_year"):
            info_parts.append(f"Maintenance: ~{s['maintenance_hours_year']} hrs/year")
        self._detail_info.setText("  |  ".join(info_parts))
        self._size_spin.setValue(s["size_m"])

    def _on_place_clicked(self):
        item = self._struct_list.currentItem()
        if not item:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        s = get_structure(sid)
        if not s:
            return
        # Create placement dict with size override
        placement = dict(s)
        placement["size_m"] = self._size_spin.value()
        self.place_structure_requested.emit(placement)

    # ── Hedgerow tab (S2) ─────────────────────────────────────────────

    def _build_hedgerow_tab(self):
        layout = QVBoxLayout(self._hedgerow_tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Draw a hedgerow or fence line on the map. Click points to "
            "define the line, then double-click to finish."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        # Style
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._hedge_style = QComboBox()
        self._hedge_style.addItems([
            "Hedge (green, filled)",
            "Fence (brown, dashed)",
            "Living Fence (mixed)",
            "Windbreak (dense, tall)",
        ])
        form.addRow("Style:", self._hedge_style)

        self._hedge_width = QDoubleSpinBox()
        self._hedge_width.setRange(0.5, 5.0)
        self._hedge_width.setSingleStep(0.5)
        self._hedge_width.setValue(1.5)
        self._hedge_width.setSuffix(" m")
        form.addRow("Width:", self._hedge_width)

        self._hedge_spacing = QDoubleSpinBox()
        self._hedge_spacing.setRange(0.3, 5.0)
        self._hedge_spacing.setSingleStep(0.1)
        self._hedge_spacing.setValue(1.0)
        self._hedge_spacing.setSuffix(" m")
        form.addRow("Plant spacing:", self._hedge_spacing)

        layout.addLayout(form)

        # Species (optional, free text for now)
        layout.addWidget(QLabel("Species (optional):"))
        self._hedge_species = QLineEdit()
        self._hedge_species.setPlaceholderText("e.g. Caragana, Lilac, Dogwood...")
        layout.addWidget(self._hedge_species)

        # Color picker
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self._hedge_color = "#4caf50"
        self._hedge_color_btn = QPushButton()
        self._hedge_color_btn.setFixedSize(28, 28)
        self._hedge_color_btn.setStyleSheet(
            f"background: {self._hedge_color}; border: 1px solid #4a7a4a; border-radius: 4px;"
        )
        self._hedge_color_btn.clicked.connect(self._pick_hedge_color)
        color_row.addWidget(self._hedge_color_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        # Draw button
        self._btn_hedge = QPushButton("Draw Hedgerow on Map")
        self._btn_hedge.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }"
        )
        self._btn_hedge.clicked.connect(self._on_hedge_draw)
        layout.addWidget(self._btn_hedge)

        layout.addStretch()

    def _pick_hedge_color(self):
        color = QColorDialog.getColor(QColor(self._hedge_color), self, "Hedgerow Color")
        if color.isValid():
            self._hedge_color = color.name()
            self._hedge_color_btn.setStyleSheet(
                f"background: {self._hedge_color}; border: 1px solid #4a7a4a; border-radius: 4px;"
            )

    def _on_hedge_draw(self):
        style_map = {
            0: "hedge",
            1: "fence",
            2: "living_fence",
            3: "windbreak",
        }
        self.place_hedgerow_requested.emit({
            "style": style_map.get(self._hedge_style.currentIndex(), "hedge"),
            "width_m": self._hedge_width.value(),
            "spacing_m": self._hedge_spacing.value(),
            "species": self._hedge_species.text().strip(),
            "color": self._hedge_color,
        })

    # ── Shapes tab (S3) ──────────────────────────────────────────────

    def _build_shapes_tab(self):
        layout = QVBoxLayout(self._shapes_tab)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info = QLabel(
            "Draw custom shapes on the map for garden beds, pathways, patios, "
            "and other areas. Click points to define, double-click to finish."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #90a4ae; font-size: 11px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        # Shape presets — the general beds/paths set plus the lawn-to-habitat
        # conversion zones (N2), whose labels/colours come from src.lawn_zones so
        # the drawer and the conversion tally never drift.
        from src.lawn_zones import ZONE_TYPES
        self._shape_preset = QComboBox()
        self._shape_preset.addItems([
            "Garden Bed",
            "Pathway",
            "Patio / Deck",
            "Lawn Area",
            "Mulch Area",
            "Water Feature",
            "Custom",
        ])
        self._shape_preset.insertSeparator(self._shape_preset.count())
        self._shape_preset.addItems([spec["label"] for spec in ZONE_TYPES.values()])
        self._shape_preset.currentIndexChanged.connect(self._on_shape_preset_changed)
        form.addRow("Type:", self._shape_preset)

        layout.addLayout(form)

        # Label
        layout.addWidget(QLabel("Label:"))
        self._shape_label = QLineEdit()
        self._shape_label.setPlaceholderText("e.g. Front garden bed")
        layout.addWidget(self._shape_label)

        # Colors
        color_form = QFormLayout()

        # Fill color
        fill_row = QHBoxLayout()
        self._shape_fill = "#4caf50"
        self._shape_fill_btn = QPushButton()
        self._shape_fill_btn.setFixedSize(28, 28)
        self._shape_fill_btn.setStyleSheet(
            f"background: {self._shape_fill}; border: 1px solid #4a7a4a; border-radius: 4px;"
        )
        self._shape_fill_btn.clicked.connect(self._pick_shape_fill)
        fill_row.addWidget(self._shape_fill_btn)
        fill_row.addStretch()
        color_form.addRow("Fill:", fill_row)

        # Stroke color
        stroke_row = QHBoxLayout()
        self._shape_stroke = "#2e7d32"
        self._shape_stroke_btn = QPushButton()
        self._shape_stroke_btn.setFixedSize(28, 28)
        self._shape_stroke_btn.setStyleSheet(
            f"background: {self._shape_stroke}; border: 1px solid #4a7a4a; border-radius: 4px;"
        )
        self._shape_stroke_btn.clicked.connect(self._pick_shape_stroke)
        stroke_row.addWidget(self._shape_stroke_btn)
        stroke_row.addStretch()
        color_form.addRow("Stroke:", stroke_row)

        # Fill opacity
        self._shape_opacity = QDoubleSpinBox()
        self._shape_opacity.setRange(0.0, 1.0)
        self._shape_opacity.setSingleStep(0.05)
        self._shape_opacity.setValue(0.25)
        color_form.addRow("Opacity:", self._shape_opacity)

        # Stroke pattern
        self._shape_pattern = QComboBox()
        self._shape_pattern.addItems(["Solid", "Dashed", "Dotted"])
        color_form.addRow("Line style:", self._shape_pattern)

        layout.addLayout(color_form)

        # Shade height — when > 0 the drawn perimeter becomes a shade caster
        # (a tree canopy or building footprint) instead of a flat area shape.
        height_form = QFormLayout()
        self._shape_height = QDoubleSpinBox()
        self._shape_height.setRange(0.0, 60.0)
        self._shape_height.setSingleStep(0.5)
        self._shape_height.setValue(0.0)
        self._shape_height.setSuffix(" m")
        self._shape_height.setToolTip(
            "Height of the structure/canopy. 0 = a flat area shape (no shade).\n"
            "Set a height to cast a shadow from this footprint (e.g. 8 m for a\n"
            "house, 6 m for a mature tree canopy).")
        height_form.addRow("Casts shade — height:", self._shape_height)
        layout.addLayout(height_form)

        # Draw button
        self._btn_shape = QPushButton("Draw Shape on Map")
        self._btn_shape.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }"
        )
        self._btn_shape.clicked.connect(self._on_shape_draw)
        layout.addWidget(self._btn_shape)

        layout.addStretch()

        # Apply first preset
        self._on_shape_preset_changed(0)

    _SHAPE_PRESETS = {
        "Garden Bed":     {"fill": "#4caf50", "stroke": "#2e7d32", "opacity": 0.25, "pattern": "Solid"},
        "Pathway":        {"fill": "#8d6e63", "stroke": "#5d4037", "opacity": 0.35, "pattern": "Dashed"},
        "Patio / Deck":   {"fill": "#78909c", "stroke": "#546e7a", "opacity": 0.40, "pattern": "Solid"},
        "Lawn Area":      {"fill": "#66bb6a", "stroke": "#43a047", "opacity": 0.15, "pattern": "Dotted"},
        "Mulch Area":     {"fill": "#795548", "stroke": "#5d4037", "opacity": 0.30, "pattern": "Solid"},
        "Water Feature":  {"fill": "#42a5f5", "stroke": "#1565c0", "opacity": 0.30, "pattern": "Solid"},
        "Custom":         {"fill": "#9e9e9e", "stroke": "#616161", "opacity": 0.25, "pattern": "Solid"},
    }

    def _on_shape_preset_changed(self, _idx):
        name = self._shape_preset.currentText()
        preset = self._SHAPE_PRESETS.get(name)
        if preset is None:
            # A lawn-conversion zone (or the separator): pull its style from
            # src.lawn_zones; fall back to Custom for the empty separator row.
            from src.lawn_zones import ZONE_TYPES
            zspec = next((s for s in ZONE_TYPES.values() if s["label"] == name),
                         None)
            preset = ({"fill": zspec["fill"], "stroke": zspec["stroke"],
                       "opacity": zspec["opacity"], "pattern": "Solid"}
                      if zspec else self._SHAPE_PRESETS["Custom"])
        self._shape_fill = preset["fill"]
        self._shape_stroke = preset["stroke"]
        self._shape_fill_btn.setStyleSheet(
            f"background: {self._shape_fill}; border: 1px solid #4a7a4a; border-radius: 4px;"
        )
        self._shape_stroke_btn.setStyleSheet(
            f"background: {self._shape_stroke}; border: 1px solid #4a7a4a; border-radius: 4px;"
        )
        self._shape_opacity.setValue(preset["opacity"])
        pattern_idx = ["Solid", "Dashed", "Dotted"].index(preset["pattern"])
        self._shape_pattern.setCurrentIndex(pattern_idx)
        if name != "Custom":
            self._shape_label.setPlaceholderText(f"e.g. {name}")

    def _pick_shape_fill(self):
        color = QColorDialog.getColor(QColor(self._shape_fill), self, "Fill Color")
        if color.isValid():
            self._shape_fill = color.name()
            self._shape_fill_btn.setStyleSheet(
                f"background: {self._shape_fill}; border: 1px solid #4a7a4a; border-radius: 4px;"
            )

    def _pick_shape_stroke(self):
        color = QColorDialog.getColor(QColor(self._shape_stroke), self, "Stroke Color")
        if color.isValid():
            self._shape_stroke = color.name()
            self._shape_stroke_btn.setStyleSheet(
                f"background: {self._shape_stroke}; border: 1px solid #4a7a4a; border-radius: 4px;"
            )

    def _on_shape_draw(self):
        pattern_map = {"Solid": "", "Dashed": "8 4", "Dotted": "2 4"}
        self.place_shape_requested.emit({
            "shape_type": self._shape_preset.currentText(),
            "label": self._shape_label.text().strip(),
            "fill_color": self._shape_fill,
            "stroke_color": self._shape_stroke,
            "fill_opacity": self._shape_opacity.value(),
            "dash_array": pattern_map.get(self._shape_pattern.currentText(), ""),
            # >0 → the drawn footprint casts shade (canopy / building perimeter).
            "height_m": self._shape_height.value(),
        })
