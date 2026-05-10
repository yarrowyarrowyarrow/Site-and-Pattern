import json

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db import polycultures
from src.db import plants as plants_db


ROLES = [
    "canopy",
    "understory",
    "groundcover",
    "nitrogen_fixer",
    "dynamic_accumulator",
    "pest_repellent",
    "pollinator",
    "windbreak",
    "other",
]

# Role → preferred plant_type filters (used to sort/filter the plant combo)
ROLE_TYPE_HINTS = {
    "canopy":              ["tree"],
    "understory":          ["shrub", "vine"],
    "groundcover":         ["groundcover", "herb"],
    "nitrogen_fixer":      None,  # filter by permaculture_uses instead
    "dynamic_accumulator": None,
    "pest_repellent":      ["herb", "shrub"],
    "pollinator":          ["herb", "shrub"],
    "windbreak":           ["tree", "shrub"],
    "other":               None,  # show all
}


class OffsetCanvas(QWidget):
    """Mini canvas for visually positioning a polyculture member by clicking."""

    offsetChanged = pyqtSignal(float, float)  # offset_x, offset_y in metres

    def __init__(self, radius_m: float = 10.0, parent=None):
        super().__init__(parent)
        self._radius_m = radius_m   # half-width of canvas in metres
        self._offset_x = 0.0
        self._offset_y = 0.0
        self.setFixedSize(180, 180)
        self.setToolTip("Click to set member offset from polyculture centre")
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_offset(self, x: float, y: float):
        self._offset_x = max(-self._radius_m, min(self._radius_m, x))
        self._offset_y = max(-self._radius_m, min(self._radius_m, y))
        self.update()

    def offset(self) -> tuple[float, float]:
        return self._offset_x, self._offset_y

    def mousePressEvent(self, event):
        self._update_from_mouse(event.position())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_from_mouse(event.position())

    def _update_from_mouse(self, pos: QPointF):
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        scale = self._radius_m / (min(w, h) / 2)
        self._offset_x = round((pos.x() - cx) * scale, 1)
        self._offset_y = round((cy - pos.y()) * scale, 1)  # Y flipped
        self._offset_x = max(-self._radius_m, min(self._radius_m, self._offset_x))
        self._offset_y = max(-self._radius_m, min(self._radius_m, self._offset_y))
        self.update()
        self.offsetChanged.emit(self._offset_x, self._offset_y)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # Background
        p.fillRect(0, 0, w, h, QColor(20, 32, 20))

        # Grid lines
        pen = QPen(QColor(46, 74, 46), 1)
        p.setPen(pen)
        steps = 5
        for i in range(steps + 1):
            frac = i / steps
            x = int(frac * w)
            y = int(frac * h)
            p.drawLine(x, 0, x, h)
            p.drawLine(0, y, w, y)

        # Crosshair at centre
        pen.setColor(QColor(100, 160, 100))
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(int(cx), 0, int(cx), h)
        p.drawLine(0, int(cy), w, int(cy))

        # Centre dot
        p.setBrush(QBrush(QColor(102, 187, 106)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 4, 4)

        # Member position dot
        scale = (min(w, h) / 2) / self._radius_m
        mx = cx + self._offset_x * scale
        my = cy - self._offset_y * scale  # Y flipped
        p.setBrush(QBrush(QColor(255, 167, 38)))
        p.drawEllipse(QPointF(mx, my), 6, 6)

        # Label
        p.setPen(QColor(200, 230, 201))
        p.setFont(QFont("Arial", 8))
        p.drawText(4, 12, f"±{self._radius_m}m")
        p.drawText(4, h - 4, f"({self._offset_x:.1f}, {self._offset_y:.1f})m")
        p.end()


class AddMemberDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Polyculture Member")
        self.setMinimumWidth(420)

        self._all_plants = plants_db.get_all_plants()

        layout = QFormLayout(self)

        # Role comes first — it filters the plant list
        self.role_combo = QComboBox()
        for r in ROLES:
            self.role_combo.addItem(r.replace("_", " ").title(), r)
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
        layout.addRow("Role:", self.role_combo)

        self.plant_combo = QComboBox()
        layout.addRow("Plant:", self.plant_combo)

        # Visual offset editor
        offset_group = QGroupBox("Position (click or drag to set offset)")
        offset_layout = QHBoxLayout(offset_group)

        self._canvas = OffsetCanvas(radius_m=10.0)
        offset_layout.addWidget(self._canvas)

        # Spin boxes alongside for fine-tuning
        spin_col = QVBoxLayout()
        spin_col.addStretch()
        x_row = QHBoxLayout()
        x_row.addWidget(QLabel("X:"))
        self.offset_x = QDoubleSpinBox()
        self.offset_x.setRange(-50, 50)
        self.offset_x.setSuffix(" m")
        self.offset_x.setDecimals(1)
        x_row.addWidget(self.offset_x)
        spin_col.addLayout(x_row)

        y_row = QHBoxLayout()
        y_row.addWidget(QLabel("Y:"))
        self.offset_y = QDoubleSpinBox()
        self.offset_y.setRange(-50, 50)
        self.offset_y.setSuffix(" m")
        self.offset_y.setDecimals(1)
        y_row.addWidget(self.offset_y)
        spin_col.addLayout(y_row)
        spin_col.addStretch()
        offset_layout.addLayout(spin_col)

        layout.addRow(offset_group)

        # Sync canvas ↔ spinboxes
        self._canvas.offsetChanged.connect(self._on_canvas_offset)
        self.offset_x.valueChanged.connect(self._on_spin_offset)
        self.offset_y.valueChanged.connect(self._on_spin_offset)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        # Populate plant list for the default role
        self._on_role_changed()

    def _on_canvas_offset(self, x: float, y: float):
        self.offset_x.blockSignals(True)
        self.offset_y.blockSignals(True)
        self.offset_x.setValue(x)
        self.offset_y.setValue(y)
        self.offset_x.blockSignals(False)
        self.offset_y.blockSignals(False)

    def _on_spin_offset(self):
        self._canvas.blockSignals(True)
        self._canvas.set_offset(self.offset_x.value(), self.offset_y.value())
        self._canvas.blockSignals(False)

    def _on_role_changed(self):
        """Filter plant combo based on selected role."""
        role = self.role_combo.currentData()
        type_hints = ROLE_TYPE_HINTS.get(role)

        self.plant_combo.clear()

        # Special filtering for function-based roles
        perm_keyword = None
        if role == "nitrogen_fixer":
            perm_keyword = "nitrogen"
        elif role == "dynamic_accumulator":
            perm_keyword = "accumulator"

        preferred = []
        others = []

        for p in self._all_plants:
            label = f"{p['common_name']} ({p['plant_type']})"
            ptype = p.get("plant_type", "")
            puses = (p.get("permaculture_uses") or "").lower()

            if perm_keyword and perm_keyword in puses:
                preferred.append((label, p["id"]))
            elif type_hints and ptype in type_hints:
                preferred.append((label, p["id"]))
            else:
                others.append((label, p["id"]))

        # Show matching plants first, then a separator, then the rest
        for label, pid in preferred:
            self.plant_combo.addItem(label, pid)

        if preferred and others:
            self.plant_combo.insertSeparator(len(preferred))

        for label, pid in others:
            self.plant_combo.addItem(label, pid)

    def get_data(self):
        return {
            "plant_id": self.plant_combo.currentData(),
            "role": self.role_combo.currentData(),
            "offset_x": self.offset_x.value(),
            "offset_y": self.offset_y.value(),
        }


class PolyculturePanel(QWidget):
    placePolycultureRequested = pyqtSignal(dict)  # polyculture data with members

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh_polyculture_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        label = QLabel("<b>Polyculture Library</b>  <span style='color:#90a4ae;font-weight:normal;'>(saved polycultures)</span>")
        layout.addWidget(label)

        # Search/filter box
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search polycultures...")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._refresh_polyculture_list)
        layout.addWidget(self._search_box)

        # Polyculture tree (parent polycultures + variations as children)
        self.polyculture_tree = QTreeWidget()
        self.polyculture_tree.setHeaderHidden(True)
        self.polyculture_tree.setIndentation(16)
        self.polyculture_tree.setMouseTracking(True)
        self.polyculture_tree.currentItemChanged.connect(self._on_polyculture_selected)
        self.polyculture_tree.itemDoubleClicked.connect(self._on_double_click_place)
        layout.addWidget(self.polyculture_tree)

        # Buttons row 1
        btn_row1 = QHBoxLayout()
        self.new_btn = QPushButton("New Polyculture")
        self.new_btn.clicked.connect(self._on_new_polyculture)
        btn_row1.addWidget(self.new_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_polyculture)
        btn_row1.addWidget(self.delete_btn)

        self.dup_btn = QPushButton("Duplicate")
        self.dup_btn.setEnabled(False)
        self.dup_btn.clicked.connect(self._on_duplicate_polyculture)
        btn_row1.addWidget(self.dup_btn)

        self.variation_btn = QPushButton("+ Variation")
        self.variation_btn.setEnabled(False)
        self.variation_btn.setToolTip("Create a variation of this polyculture")
        self.variation_btn.clicked.connect(self._on_add_variation)
        btn_row1.addWidget(self.variation_btn)
        layout.addLayout(btn_row1)

        # Detail area
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        layout.addWidget(self.detail_text)

        # Members list
        members_label = QLabel("<b>Members</b>")
        layout.addWidget(members_label)

        self.members_list = QListWidget()
        self.members_list.setMaximumHeight(120)
        layout.addWidget(self.members_list)

        # Member buttons
        member_btns = QHBoxLayout()
        self.add_member_btn = QPushButton("Add Member")
        self.add_member_btn.setEnabled(False)
        self.add_member_btn.clicked.connect(self._on_add_member)
        member_btns.addWidget(self.add_member_btn)

        self.remove_member_btn = QPushButton("Remove")
        self.remove_member_btn.setEnabled(False)
        self.remove_member_btn.clicked.connect(self._on_remove_member)
        member_btns.addWidget(self.remove_member_btn)
        layout.addLayout(member_btns)

        # Wire once here — NOT inside _on_polyculture_selected to avoid accumulation
        self.members_list.currentItemChanged.connect(
            lambda c, p: self.remove_member_btn.setEnabled(c is not None)
        )

        # Action buttons
        btn_row2 = QHBoxLayout()
        self.place_btn = QPushButton("Place on Map")
        self.place_btn.setEnabled(False)
        self.place_btn.clicked.connect(self._on_place)
        btn_row2.addWidget(self.place_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        btn_row2.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import)
        btn_row2.addWidget(self.import_btn)
        layout.addLayout(btn_row2)

    def _refresh_polyculture_list(self, _filter_text=None):
        self.polyculture_tree.clear()
        search = (self._search_box.text().strip().lower()
                  if hasattr(self, '_search_box') else "")

        for g in polycultures.get_all_polycultures(top_level_only=True):
            polyculture_detail = polycultures.get_polyculture_by_id(g["id"])
            members = polyculture_detail.get("members", []) if polyculture_detail else []
            member_names = [m["common_name"] for m in members]

            # Search filter: match polyculture name, description, or member names
            children = polycultures.get_polyculture_children(g["id"])
            child_match = False
            if search:
                polyculture_match = (
                    search in g["name"].lower()
                    or search in (g.get("description") or "").lower()
                    or any(search in n.lower() for n in member_names)
                )
                for child in children:
                    cd = polycultures.get_polyculture_by_id(child["id"])
                    cm = [m["common_name"] for m in (cd.get("members", []) if cd else [])]
                    if (search in child["name"].lower()
                            or any(search in n.lower() for n in cm)):
                        child_match = True
                if not polyculture_match and not child_match:
                    continue

            # Build tooltip: member summary
            roles_summary = ", ".join(
                f"{m['common_name']} ({(m.get('role') or '').replace('_',' ')})"
                for m in members[:5]
            )
            if len(members) > 5:
                roles_summary += f", +{len(members)-5} more"
            tooltip = f"{g['name']}\n{g.get('description', '')[:120]}\n\nMembers: {roles_summary}"

            item = QTreeWidgetItem([g["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, g["id"])
            item.setToolTip(0, tooltip)
            self.polyculture_tree.addTopLevelItem(item)

            for child in children:
                cd = polycultures.get_polyculture_by_id(child["id"])
                cm = cd.get("members", []) if cd else []
                child_roles = ", ".join(
                    f"{m['common_name']} ({(m.get('role') or '').replace('_',' ')})"
                    for m in cm[:5]
                )
                child_tooltip = f"{child['name']}\n{child.get('description','')[:120]}\n\nMembers: {child_roles}"

                child_item = QTreeWidgetItem([child["name"]])
                child_item.setData(0, Qt.ItemDataRole.UserRole, child["id"])
                child_item.setToolTip(0, child_tooltip)
                item.addChild(child_item)
            if children:
                item.setExpanded(True)

    def _on_double_click_place(self, item, column):
        """Double-click a polyculture to immediately enter placement mode."""
        polyculture_id = item.data(0, Qt.ItemDataRole.UserRole)
        if polyculture_id is None:
            return
        polyculture = polycultures.get_polyculture_by_id(polyculture_id)
        if polyculture:
            self.placePolycultureRequested.emit(polyculture)

    def _on_polyculture_selected(self, current, previous):
        has_selection = current is not None
        self.delete_btn.setEnabled(has_selection)
        self.dup_btn.setEnabled(has_selection)
        self.place_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)
        self.add_member_btn.setEnabled(has_selection)
        # Only allow adding variations to top-level polycultures
        is_top_level = has_selection and (current.parent() is None)
        self.variation_btn.setEnabled(is_top_level)

        if not has_selection:
            self.detail_text.clear()
            self.members_list.clear()
            return

        polyculture_id = current.data(0, Qt.ItemDataRole.UserRole)
        polyculture = polycultures.get_polyculture_by_id(polyculture_id)
        if not polyculture:
            return

        lines = [
            f"<b>{polyculture['name']}</b>",
            f"Center: {polyculture.get('center_plant_name', 'None')}",
        ]
        if polyculture.get("description"):
            lines.append(polyculture["description"])
        lines.append(f"Members: {len(polyculture.get('members', []))}")
        # Show variation count for top-level
        children = polycultures.get_polyculture_children(polyculture_id)
        if children:
            lines.append(f"Variations: {len(children)}")
        self.detail_text.setHtml("<br>".join(lines))

        self.members_list.clear()
        for m in polyculture.get("members", []):
            role = (m.get("role") or "").replace("_", " ")
            text = f"{m['common_name']} — {role} ({m['offset_x']}m, {m['offset_y']}m)"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, m["id"])
            self.members_list.addItem(item)

        self.remove_member_btn.setEnabled(False)

    def _get_selected_polyculture_id(self):
        item = self.polyculture_tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def _on_new_polyculture(self):
        name, ok = QInputDialog.getText(self, "New Polyculture", "Polyculture name:")
        if not ok or not name.strip():
            return

        desc, ok = QInputDialog.getText(self, "New Polyculture", "Description (optional):")
        if not ok:
            desc = ""

        try:
            polycultures.create_polyculture(name.strip(), desc.strip(), None)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create polyculture:\n{e}")
            return
        self._refresh_polyculture_list()

    def _on_delete_polyculture(self):
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        reply = QMessageBox.question(
            self, "Delete Polyculture", "Delete this polyculture from the library?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                polycultures.delete_polyculture(polyculture_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete polyculture:\n{e}")
                return
            self._refresh_polyculture_list()

    def _on_duplicate_polyculture(self):
        polyculture_id = self._get_selected_polyculture_id()
        if not polyculture_id:
            return
        try:
            polycultures.duplicate_polyculture(polyculture_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not duplicate polyculture:\n{e}")
            return
        self._refresh_polyculture_list()

    def _on_add_variation(self):
        """Create a variation of the selected top-level polyculture."""
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        try:
            new_id = polycultures.duplicate_polyculture(polyculture_id, as_variation=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create variation:\n{e}")
            return
        if new_id:
            self._refresh_polyculture_list()

    def _on_add_member(self):
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return

        dialog = AddMemberDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["plant_id"] is None:
                QMessageBox.warning(self, "No Plant Selected",
                                    "Please select a plant before adding a member.")
                return
            try:
                polycultures.add_polyculture_member(
                    polyculture_id, data["plant_id"], data["role"],
                    data["offset_x"], data["offset_y"]
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add member:\n{e}")
                return
            # Re-select to refresh members
            self._on_polyculture_selected(self.polyculture_tree.currentItem(), None)

    def _on_remove_member(self):
        item = self.members_list.currentItem()
        if item is None:
            return
        member_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            polycultures.remove_polyculture_member(member_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not remove member:\n{e}")
            return
        self._on_polyculture_selected(self.polyculture_tree.currentItem(), None)

    def _on_place(self):
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        polyculture = polycultures.get_polyculture_by_id(polyculture_id)
        if polyculture:
            self.placePolycultureRequested.emit(polyculture)

    def _on_export(self):
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        data = polycultures.export_polyculture(polyculture_id)
        if not data:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Polyculture", f"{data['name']}.polyculture.json",
            "Polyculture Files (*.polyculture.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export", f"Polyculture exported to {path}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Polyculture", "", "Polyculture Files (*.polyculture.json);;JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
            return

        polyculture_id, warnings = polycultures.import_polyculture(data)
        self._refresh_polyculture_list()

        if warnings:
            QMessageBox.warning(
                self, "Import Warnings",
                "Polyculture imported with warnings:\n" + "\n".join(warnings)
            )
        else:
            QMessageBox.information(self, "Import", "Polyculture imported successfully!")
