import json
import re

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
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


class PolycultureGridCanvas(QWidget):
    """Visual grid for placing polyculture members at offsets from the centre.

    The canvas is a square widget showing a circle of radius ``radius_m``
    metres with a 1m grid overlay; each member dot is drawn at its
    (offset_x, offset_y) position. The user interacts via three signals:

      * ``memberAdded(x, y)``      — left-click on empty space
      * ``memberRemoved(idx)``     — right-click on an existing dot
      * ``memberMoved(idx, x, y)`` — drag an existing dot (live updates)

    The canvas does not own the member data; the parent dialog calls
    ``set_members`` whenever the underlying list changes (after add /
    remove / move) so the canvas only paints what it's told to paint.
    """

    memberAdded   = pyqtSignal(float, float)
    memberRemoved = pyqtSignal(int)
    memberMoved   = pyqtSignal(int, float, float)

    def __init__(self, parent=None, radius_m: float = 12.0):
        super().__init__(parent)
        self._radius_m = radius_m
        self._members: list[dict] = []
        self._dragging_idx: int | None = None
        self.setFixedSize(360, 360)
        self.setMouseTracking(True)

    def set_members(self, members):
        self._members = [dict(m) for m in members]
        self.update()

    def add_member(self, member: dict):
        self._members.append(dict(member))
        self.update()

    def remove_member(self, idx: int):
        if 0 <= idx < len(self._members):
            self._members.pop(idx)
            self.update()

    def get_members(self) -> list[dict]:
        return [dict(m) for m in self._members]

    # ── Coordinate helpers ──────────────────────────────────────────────────
    def _scale(self) -> float:
        return min(self.width(), self.height()) / 2 / self._radius_m

    def _world_to_pixel(self, x_m: float, y_m: float) -> tuple[float, float]:
        cx = self.width() / 2
        cy = self.height() / 2
        s = self._scale()
        return cx + x_m * s, cy - y_m * s   # north = up

    def _pixel_to_world(self, px: float, py: float) -> tuple[float, float]:
        cx = self.width() / 2
        cy = self.height() / 2
        s = self._scale()
        return (px - cx) / s, (cy - py) / s

    def _hit_test(self, px: float, py: float) -> int | None:
        for idx in range(len(self._members) - 1, -1, -1):
            m = self._members[idx]
            mx, my = self._world_to_pixel(m["offset_x"], m["offset_y"])
            if (px - mx) ** 2 + (py - my) ** 2 <= 12 ** 2:
                return idx
        return None

    # ── Painting ────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        p.fillRect(self.rect(), QColor("#0d1f0d"))

        cx = self.width() / 2
        cy = self.height() / 2
        s = self._scale()

        # 1m grid lines
        p.setPen(QPen(QColor(74, 122, 74, 80), 1))
        steps = int(self._radius_m)
        for k in range(-steps, steps + 1):
            x = cx + k * s
            p.drawLine(int(x), 0, int(x), self.height())
            y = cy + k * s
            p.drawLine(0, int(y), self.width(), int(y))

        # Boundary circle
        p.setPen(QPen(QColor("#4a7a4a"), 1.5))
        p.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        p.drawEllipse(QPointF(cx, cy), self._radius_m * s, self._radius_m * s)

        # Centre cross
        p.setPen(QPen(QColor("#a5d6a7"), 2))
        p.drawLine(int(cx) - 5, int(cy), int(cx) + 5, int(cy))
        p.drawLine(int(cx), int(cy) - 5, int(cx), int(cy) + 5)

        # Members
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        for m in self._members:
            mx, my = self._world_to_pixel(m["offset_x"], m["offset_y"])
            color = QColor(m.get("color") or "#66bb6a")
            p.setBrush(QBrush(color))
            p.setPen(QPen(QColor("#0d1f0d"), 1))
            p.drawEllipse(QPointF(mx, my), 8, 8)
            p.setPen(QColor("#e8f5e9"))
            label = (m.get("common_name", "") or "")[:20]
            p.drawText(int(mx) + 11, int(my) + 4, label)
        p.end()

    # ── Mouse handling ──────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        px, py = ev.position().x(), ev.position().y()
        hit = self._hit_test(px, py)
        if ev.button() == Qt.MouseButton.LeftButton:
            if hit is not None:
                self._dragging_idx = hit
            else:
                x_m, y_m = self._pixel_to_world(px, py)
                if (x_m * x_m + y_m * y_m) ** 0.5 > self._radius_m:
                    return
                self.memberAdded.emit(x_m, y_m)
        elif ev.button() == Qt.MouseButton.RightButton and hit is not None:
            self.memberRemoved.emit(hit)

    def mouseMoveEvent(self, ev):
        if self._dragging_idx is None:
            return
        px, py = ev.position().x(), ev.position().y()
        x_m, y_m = self._pixel_to_world(px, py)
        if (x_m * x_m + y_m * y_m) ** 0.5 > self._radius_m:
            return
        self.memberMoved.emit(self._dragging_idx, x_m, y_m)

    def mouseReleaseEvent(self, _ev):
        self._dragging_idx = None


def _plant_color_for_member(plant: dict) -> str:
    """Pick a representative dot colour for a polyculture member."""
    if plant and plant.get("marker_color"):
        return plant["marker_color"]
    t = (plant or {}).get("plant_type", "")
    return {
        "tree":        "#388e3c",
        "shrub":       "#66bb6a",
        "herb":        "#9ccc65",
        "vine":        "#7cb342",
        "groundcover": "#aed581",
    }.get(t, "#66bb6a")


def _truthy_int(v) -> int:
    """Coerce dirty plant-DB values to a safe 0/1 int.

    The seeding JSON has historically contained malformed strings like
    ``'1?'`` for ``native_to_alberta``; SQLite's flexible typing lets
    those land in a column declared INTEGER, so consumers that call
    ``int(...)`` on them blow up with ``ValueError``. This helper
    handles every shape we've seen — bool, int, float, ``'1'``,
    ``'1?'``, ``'  1.0  '``, ``''``, ``None`` — and falls through to 0.
    """
    if v is None or v is False:
        return 0
    if v is True:
        return 1
    if isinstance(v, (int, float)):
        return 1 if v else 0
    s = str(v).strip()
    if not s:
        return 0
    m = re.match(r"-?\d+", s)
    try:
        return 1 if (m and int(m.group(0)) != 0) else 0
    except ValueError:
        return 0


class PolycultureBuilderDialog(QDialog):
    """One-screen visual editor for a polyculture (create or modify).

    Replaces the older one-plant-at-a-time AddMemberDialog flow. The
    user fills in name + description, picks plants from an Alberta-
    native-first list on the left, picks a role, then clicks the grid
    in the middle to drop them at metre offsets. Right-click removes,
    drag repositions. Save commits the whole polyculture in one go.
    """

    def __init__(self, parent=None, polyculture_id: int | None = None):
        super().__init__(parent)
        self._polyculture_id = polyculture_id
        self.setWindowTitle("Polyculture Builder" if polyculture_id is None
                            else "Edit Polyculture")
        self.setMinimumSize(820, 560)
        self._all_plants = plants_db.get_all_plants()
        self._build_ui()
        if polyculture_id is not None:
            self._load_existing(polyculture_id)
        self._refresh_member_list()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        meta = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Saskatoon Berry Polyculture")
        meta.addRow("Name:", self.name_input)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Optional notes about this polyculture")
        meta.addRow("Description:", self.desc_input)
        outer.addLayout(meta)

        tip = QLabel(
            "<span style='color:#90a4ae;font-size:11px;'>"
            "Pick a plant + role on the left, then click the grid to place it. "
            "Right-click a placed plant to remove. Drag to reposition. "
            "Alberta polycultures typically have 5–8 plants.</span>"
        )
        tip.setWordWrap(True)
        outer.addWidget(tip)

        body = QHBoxLayout()

        # Left — plant picker
        picker_col = QVBoxLayout()
        picker_col.addWidget(QLabel("<b>Plants</b>"))
        self.ab_only = QCheckBox("Alberta natives only")
        self.ab_only.setChecked(True)
        self.ab_only.toggled.connect(self._refresh_plant_list)
        picker_col.addWidget(self.ab_only)
        self.plant_search = QLineEdit()
        self.plant_search.setPlaceholderText("Search plants…")
        self.plant_search.setClearButtonEnabled(True)
        self.plant_search.textChanged.connect(self._refresh_plant_list)
        picker_col.addWidget(self.plant_search)
        self.plant_list = QListWidget()
        self.plant_list.setMinimumWidth(220)
        picker_col.addWidget(self.plant_list, 1)

        picker_col.addWidget(QLabel("<b>Role</b>"))
        self.role_combo = QComboBox()
        for r in ROLES:
            self.role_combo.addItem(r.replace("_", " ").title(), r)
        picker_col.addWidget(self.role_combo)

        body.addLayout(picker_col, 1)

        # Centre — visual canvas
        centre_col = QVBoxLayout()
        centre_col.addWidget(QLabel("<b>Polyculture layout (~12 m radius)</b>"))
        self.canvas = PolycultureGridCanvas(self)
        self.canvas.memberAdded.connect(self._on_canvas_add)
        self.canvas.memberRemoved.connect(self._on_canvas_remove)
        self.canvas.memberMoved.connect(self._on_canvas_move)
        centre_col.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignHCenter)
        self.count_label = QLabel("0 plants placed")
        self.count_label.setStyleSheet("color: #90a4ae; font-size: 11px;")
        centre_col.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addLayout(centre_col, 0)

        # Right — current members
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("<b>Members</b>"))
        self.member_list = QListWidget()
        self.member_list.setMinimumWidth(220)
        right_col.addWidget(self.member_list, 1)
        clear_btn = QPushButton("Clear all")
        clear_btn.clicked.connect(self._on_clear_all)
        right_col.addWidget(clear_btn)
        body.addLayout(right_col, 1)

        outer.addLayout(body, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save Polyculture")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._refresh_plant_list()

    def _refresh_plant_list(self, *_):
        text = (self.plant_search.text() or "").strip().lower()
        ab_only = self.ab_only.isChecked()
        self.plant_list.clear()
        for p in self._all_plants:
            if ab_only and not _truthy_int(p.get("native_to_alberta")):
                continue
            name = p.get("common_name", "") or ""
            sci = p.get("scientific_name", "") or ""
            if text and text not in name.lower() and text not in sci.lower():
                continue
            ptype = p.get("plant_type", "")
            item = QListWidgetItem(f"{name}  ({ptype})" if ptype else name)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.plant_list.addItem(item)

    def _selected_plant(self) -> dict | None:
        item = self.plant_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_canvas_add(self, x_m: float, y_m: float):
        plant = self._selected_plant()
        if plant is None:
            QMessageBox.information(
                self, "Pick a plant",
                "Select a plant from the list on the left, then click the grid to place it."
            )
            return
        self.canvas.add_member({
            "plant_id":    plant["id"],
            "common_name": plant.get("common_name", ""),
            "role":        self.role_combo.currentData(),
            "color":       _plant_color_for_member(plant),
            "offset_x":    round(x_m, 2),
            "offset_y":    round(y_m, 2),
        })
        self._refresh_member_list()

    def _on_canvas_remove(self, idx: int):
        self.canvas.remove_member(idx)
        self._refresh_member_list()

    def _on_canvas_move(self, idx: int, x_m: float, y_m: float):
        members = self.canvas.get_members()
        if 0 <= idx < len(members):
            members[idx]["offset_x"] = round(x_m, 2)
            members[idx]["offset_y"] = round(y_m, 2)
            self.canvas.set_members(members)
            self._refresh_member_list()

    def _refresh_member_list(self):
        members = self.canvas.get_members()
        self.member_list.clear()
        for m in members:
            self.member_list.addItem(QListWidgetItem(
                f"{m.get('common_name','?')} — {m.get('role','')} "
                f"({m.get('offset_x',0):+.1f}, {m.get('offset_y',0):+.1f}) m"
            ))
        n = len(members)
        if n < 5:
            note = "  (aim for 5–8)"
        elif n > 8:
            note = "  (large polyculture; consider trimming)"
        else:
            note = "  ✓ in the 5–8 sweet spot for Alberta polycultures"
        self.count_label.setText(f"{n} plant{'s' if n != 1 else ''} placed{note}")

    def _on_clear_all(self):
        self.canvas.set_members([])
        self._refresh_member_list()

    def _load_existing(self, polyculture_id: int):
        rec = polycultures.get_polyculture_by_id(polyculture_id)
        if not rec:
            return
        self.name_input.setText(rec.get("name", "") or "")
        self.desc_input.setText(rec.get("description", "") or "")
        plants_by_id = {p["id"]: p for p in self._all_plants}
        members = []
        for m in rec.get("members", []):
            plant = plants_by_id.get(m.get("plant_id"))
            members.append({
                "plant_id":    m.get("plant_id"),
                "common_name": (plant or {}).get(
                    "common_name", m.get("common_name", "")
                ),
                "role":        m.get("role", "other"),
                "color":       _plant_color_for_member(plant or {}),
                "offset_x":    float(m.get("offset_x") or 0.0),
                "offset_y":    float(m.get("offset_y") or 0.0),
            })
        self.canvas.set_members(members)

    def _on_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required",
                                "Please give the polyculture a name.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name":        self.name_input.text().strip(),
            "description": self.desc_input.text().strip(),
            "members":     self.canvas.get_members(),
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

        # Single "Edit" button — opens the visual builder pre-loaded
        # with the selected polyculture so add / move / remove all
        # happen in one screen instead of one plant at a time.
        member_btns = QHBoxLayout()
        self.edit_btn = QPushButton("Edit in Builder…")
        self.edit_btn.setEnabled(False)
        self.edit_btn.setToolTip(
            "Open the visual polyculture builder for this polyculture"
        )
        self.edit_btn.clicked.connect(self._on_edit_polyculture)
        member_btns.addWidget(self.edit_btn)
        member_btns.addStretch(1)
        layout.addLayout(member_btns)

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
        self.edit_btn.setEnabled(has_selection)
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

    def _get_selected_polyculture_id(self):
        item = self.polyculture_tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def _on_new_polyculture(self):
        """Open the visual builder for a brand-new polyculture.

        Both the polyculture row and its full member set are committed
        in one go when the user hits Save in the dialog.
        """
        dialog = PolycultureBuilderDialog(self, polyculture_id=None)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            new_id = polycultures.create_polyculture(
                data["name"], data["description"], None
            )
            polycultures.replace_polyculture_members(new_id, data["members"])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create polyculture:\n{e}")
            return
        self._refresh_polyculture_list()

    def _on_edit_polyculture(self):
        """Open the visual builder pre-loaded with the selected polyculture.

        Save commits name + description + the full new member set,
        replacing the previous members atomically.
        """
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        dialog = PolycultureBuilderDialog(self, polyculture_id=polyculture_id)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            polycultures.update_polyculture(
                polyculture_id, data["name"], data["description"]
            )
            polycultures.replace_polyculture_members(
                polyculture_id, data["members"]
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save polyculture:\n{e}")
            return
        self._refresh_polyculture_list()
        # Re-select the same polyculture so the right-pane detail
        # refreshes against the new member set.
        for i in range(self.polyculture_tree.topLevelItemCount()):
            top = self.polyculture_tree.topLevelItem(i)
            if top.data(0, Qt.ItemDataRole.UserRole) == polyculture_id:
                self.polyculture_tree.setCurrentItem(top)
                break

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

    # NOTE: the per-member Add / Remove buttons were retired in favour
    # of the visual builder dialog (`PolycultureBuilderDialog`) opened
    # via the "Edit in Builder…" button. AddMemberDialog is kept above
    # in case external code or tests still import it.

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
