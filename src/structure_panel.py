"""
structure_panel.py — Placement › Structures: habitat structures to place on
the map (bee hotels, brush piles, ponds, rock piles…).

Until V3.07 this was the Structures tab, with three pages: these structures as
"Habitat", Hedgerow and Shapes. The owner's answers to the V3.05 surface audit
put the structures beside the plants (placing a structure is placing a thing)
and moved the two drawing pages to the Draw row as one Shape tool
(``src/shape_tool.py``), so the panel is the list.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QFrame, QPushButton,
    QComboBox, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from src.db.structures import (
    STRUCTURES, STRUCTURE_CATEGORIES, get_structure, get_all_structures,
)


#: The structures under three headings, by what a person wants one for
#: (V3.21, RM-9; docs/homeowner/03-what-goes.md §6). Every structure in the
#: catalogue is in exactly one group, which a test holds.
STRUCTURE_GROUPS = (
    ("For wildlife", ("pond", "brush_pile", "bee_hotel", "native_bee_log",
                      "snag", "rock_xeriscape")),
    ("For water", ("rain_garden", "rain_barrel", "swale")),
    ("Around the yard", ("raised_bed", "compost_bin", "shed", "fence",
                         "fire_pit", "native_lawn_patch")),
)


# ═════════════════════════════════════════════════════════════════════════════
#  Structures tab  (S1)
# ═════════════════════════════════════════════════════════════════════════════

class StructurePanel(QWidget):
    """The structures list: search, a category, a structure's details, its
    size, and Place on Map."""

    place_structure_requested = pyqtSignal(dict)        # structure def dict

    def __init__(self, parent=None):
        super().__init__(parent)
        # The page is the panel itself since V3.07 (it was the first of three
        # inner tabs); the builder below still fills ``_structures_tab``.
        self._structures_tab = self
        self._build_structures_tab()

    # ── Structures tab ────────────────────────────────────────────────

    def _build_structures_tab(self):
        layout = QVBoxLayout(self._structures_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search structures...")
        self._search.setAccessibleName("Search structures")
        self._search.textChanged.connect(self._filter_structures)
        layout.addWidget(self._search)

        # Category filter
        self._cat_combo = QComboBox()
        self._cat_combo.setAccessibleName("Structure category")
        self._cat_combo.addItem("All Categories")
        for cat in STRUCTURE_CATEGORIES:
            self._cat_combo.addItem(cat)
        self._cat_combo.currentTextChanged.connect(self._filter_structures)
        layout.addWidget(self._cat_combo)

        # Structure list
        self._struct_list = QListWidget()
        self._struct_list.setAccessibleName("Structures")
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
        # By name: a bare "QFrame { border }" also reached the three labels
        # inside (a QLabel is a QFrame), which drew as three empty boxes until
        # a structure was chosen (V3.05 surface audit). Hidden until then.
        self._detail_frame.setObjectName("structureDetail")
        self._detail_frame.setStyleSheet(
            "QFrame#structureDetail { background: #1e2e1e; border: 1px solid "
            "#2e4a2e; border-radius: 4px; padding: 6px; }"
        )
        self._detail_frame.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_frame)
        detail_layout.setContentsMargins(6, 6, 6, 6)
        detail_layout.setSpacing(4)

        self._detail_name = QLabel("")
        self._detail_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #a5d6a7;")
        detail_layout.addWidget(self._detail_name)

        self._detail_desc = QLabel("")
        self._detail_desc.setWordWrap(True)
        self._detail_desc.setStyleSheet("color: #90a4ae; font-size: 12px;")
        detail_layout.addWidget(self._detail_desc)

        self._detail_info = QLabel("")
        self._detail_info.setStyleSheet("color: #90a4ae; font-size: 12px;")
        detail_layout.addWidget(self._detail_info)

        layout.addWidget(self._detail_frame)

        # Size override
        size_row = QHBoxLayout()
        size_label = QLabel("Size (m):")
        size_row.addWidget(size_label)
        self._size_spin = QDoubleSpinBox()
        size_label.setBuddy(self._size_spin)
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

        # Existing on-site trees/buildings moved to Site → Features (V1.59;
        # the tab was 'Features && Shade' until the V2.38 sun/shade merge), where
        # they sit alongside the shade map and OSM import.

        self._populate_structures()

    def _populate_structures(self):
        self._fill(STRUCTURES)

    def _filter_structures(self):
        text = self._search.text().lower()
        cat = self._cat_combo.currentText()
        self._fill([
            s for s in STRUCTURES
            if (cat == "All Categories" or s["category"] == cat)
            and (not text or text in s["name"].lower()
                 or text in s["description"].lower())])

    def _fill(self, structures) -> None:
        """The list under the three headings (V3.21, RM-9), each heading
        shown only when something under it is: a heading cannot be chosen,
        and the arrow keys pass over it."""
        self._struct_list.clear()
        by_id = {s["id"]: s for s in structures}
        for heading, ids in STRUCTURE_GROUPS:
            members = [by_id[i] for i in ids if i in by_id]
            if not members:
                continue
            head = QListWidgetItem(heading)
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            font = head.font()
            font.setBold(True)
            head.setFont(font)
            head.setForeground(QColor("#a5d6a7"))
            self._struct_list.addItem(head)
            for s in members:
                item = QListWidgetItem(f"{s['icon']}  {s['name']}")
                item.setData(Qt.ItemDataRole.UserRole, s["id"])
                item.setToolTip(s["description"])
                self._struct_list.addItem(item)

    def _on_selection_changed(self, current, _prev):
        if not current or current.data(Qt.ItemDataRole.UserRole) is None:
            # Nothing, or a heading (RM-9): nothing to describe or place.
            self._btn_place.setEnabled(False)
            self._detail_name.setText("")
            self._detail_desc.setText("")
            self._detail_info.setText("")
            self._detail_frame.setVisible(False)
            return
        sid = current.data(Qt.ItemDataRole.UserRole)
        s = get_structure(sid)
        if not s:
            return
        self._detail_frame.setVisible(True)
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
