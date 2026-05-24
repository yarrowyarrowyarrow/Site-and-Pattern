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
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db import polycultures
from src.db import plants as plants_db
from src.db import recipes as recipes_db


# Vegetation layer (single-select) — the physical position of a plant in
# the community's vertical structure. Each member sits in exactly one
# layer.
LAYERS = [
    "overstory",
    "understory",
    "shrub_layer",
    "groundcover",
    "herbaceous",
    "vine",
    "root",
]

# Ecological functions (multi-select) — what the plant DOES. A member can
# have several (e.g. understory + windbreak + pollinator).
FUNCTIONS = [
    "nitrogen_fixer",
    "soil_builder",
    "pest_deterrent",
    "pollinator",
    "windbreak",
]

# Legacy single-value role list — still used by older saved data and by
# code paths that haven't migrated to layer/functions. Kept exported so
# external callers don't break.
ROLES = LAYERS + FUNCTIONS + ["other"]

# Legacy role names → new role names. Used when reading saved polycultures
# so old projects still render with the new vegetation-layer language.
_LEGACY_ROLE_ALIASES = {
    "canopy":              "overstory",
    "dynamic_accumulator": "soil_builder",
    "pest_repellent":      "pest_deterrent",
}

# Layer → preferred plant_type filters (used to sort/filter the plant combo)
LAYER_TYPE_HINTS = {
    "overstory":           ["tree"],
    "understory":          ["tree", "shrub"],
    "shrub_layer":         ["shrub"],
    "groundcover":         ["groundcover", "herb"],
    "herbaceous":          ["herb"],
    "vine":                ["vine"],
    "root":                ["root"],
}

# Function → permaculture-uses substring used to surface matching plants.
FUNCTION_PERM_KEYWORDS = {
    "nitrogen_fixer":   "nitrogen",
    "soil_builder":     "soil_builder",
    "pest_deterrent":   "pest",
    "pollinator":       "pollinator",
    "windbreak":        "windbreak",
}

# Kept as a compatibility shim for any external caller that still imports it.
ROLE_TYPE_HINTS = {
    **{layer: hints for layer, hints in LAYER_TYPE_HINTS.items()},
    "nitrogen_fixer":      None,
    "soil_builder":        None,
    "pest_deterrent":      ["herb", "shrub"],
    "pollinator":          ["herb", "shrub"],
    "windbreak":           ["tree", "shrub"],
    "other":               None,
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
        self.setToolTip("Click to set member offset from the community centre")
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
        self.setWindowTitle("Add Plant Community Member")
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
        elif role == "soil_builder":
            perm_keyword = "soil_builder"

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

    radiusChanged = pyqtSignal(float)

    def __init__(self, parent=None, radius_m: float = 6.0):
        super().__init__(parent)
        self._radius_m = float(radius_m)
        self._members: list[dict] = []
        self._dragging_idx: int | None = None
        self.setFixedSize(360, 360)
        self.setMouseTracking(True)

    def set_members(self, members):
        self._members = [dict(m) for m in members]
        self.update()

    def setRadius(self, radius_m: float):
        """Change the visible radius (zoom). Members keep their offsets;
        clicks outside the new visible radius are rejected, so the user
        must zoom out before placing far-away members."""
        radius_m = max(1.0, float(radius_m))
        if abs(radius_m - self._radius_m) < 1e-3:
            return
        self._radius_m = radius_m
        self.radiusChanged.emit(self._radius_m)
        self.update()

    def radius_m(self) -> float:
        return self._radius_m

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

        # Members — each plant is drawn at its mature canopy diameter
        # (sourced from spacing_meters) so the grid is visually
        # accurate to scale instead of using a uniform dot. A small
        # centre pip in the dot colour keeps very large canopies
        # legible when they overlap.
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        for m in self._members:
            mx, my = self._world_to_pixel(m["offset_x"], m["offset_y"])
            color = QColor(m.get("color") or "#66bb6a")
            # Canopy radius in metres → pixels. Fall back to a 0.5 m
            # radius for legacy members that never recorded a spacing.
            spacing_m = float(m.get("spacing_m") or 1.0)
            r_px = max(4.0, (spacing_m / 2.0) * s)

            # Semi-transparent canopy disc so overlaps stay visible.
            canopy_fill = QColor(color)
            canopy_fill.setAlpha(110)
            p.setBrush(QBrush(canopy_fill))
            p.setPen(QPen(color.darker(140), 1.2))
            p.drawEllipse(QPointF(mx, my), r_px, r_px)

            # Solid centre pip so the planting point is unambiguous.
            p.setBrush(QBrush(color))
            p.setPen(QPen(QColor("#0d1f0d"), 1))
            p.drawEllipse(QPointF(mx, my), 4, 4)

            p.setPen(QColor("#e8f5e9"))
            label = (m.get("common_name", "") or "")[:20]
            p.drawText(int(mx) + int(r_px) + 4, int(my) + 4, label)
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
        self.setWindowTitle("Plant Community Builder" if polyculture_id is None
                            else "Edit Plant Community")
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
        self.name_input.setPlaceholderText("e.g. Saskatoon Berry Community")
        meta.addRow("Name:", self.name_input)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Optional notes about this plant community")
        meta.addRow("Description:", self.desc_input)
        outer.addLayout(meta)

        tip = QLabel(
            "<span style='color:#90a4ae;font-size:11px;'>"
            "Pick a plant + role on the left, then click the grid to place it. "
            "Right-click a placed plant to remove. Drag to reposition. "
            "Native habitat plant communities typically have 5–8 species.</span>"
        )
        tip.setWordWrap(True)
        outer.addWidget(tip)

        body = QHBoxLayout()

        # Left — plant picker. Filters mirror the main Plants tab so
        # users can drill into the catalogue while building a mix
        # without leaving the dialog (Phase 4 — search parity).
        from src.plant_panel import (
            _TYPE_LABELS, _SUN_LABELS, _WATER_LABELS, _USE_LABELS,
        )
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

        def _build_combo(items):
            cb = QComboBox()
            for label, data in items:
                cb.addItem(label, userData=data)
            cb.currentIndexChanged.connect(self._refresh_plant_list)
            return cb

        filt_row1 = QHBoxLayout()
        self.type_combo = _build_combo(
            [("All types", "")]
            + [(lbl, key) for key, lbl in _TYPE_LABELS.items()]
        )
        self.sun_combo = _build_combo(
            [("Any sun", "")]
            + [(lbl, key) for key, lbl in _SUN_LABELS.items()]
        )
        filt_row1.addWidget(self.type_combo)
        filt_row1.addWidget(self.sun_combo)
        picker_col.addLayout(filt_row1)

        filt_row2 = QHBoxLayout()
        self.water_combo = _build_combo(
            [("Any water", "")]
            + [(lbl, key) for key, lbl in _WATER_LABELS.items()]
        )
        self.use_combo = _build_combo(
            [("Any use", "")]
            + [(lbl, key) for key, lbl in _USE_LABELS.items()]
        )
        filt_row2.addWidget(self.water_combo)
        filt_row2.addWidget(self.use_combo)
        picker_col.addLayout(filt_row2)

        self.plant_list = QListWidget()
        self.plant_list.setMinimumWidth(220)
        picker_col.addWidget(self.plant_list, 1)

        picker_col.addWidget(QLabel("<b>Layer</b>"))
        self.layer_combo = QComboBox()
        self.layer_combo.addItem("(none)", None)
        for layer in LAYERS:
            self.layer_combo.addItem(layer.replace("_", " ").title(), layer)
        self.layer_combo.setToolTip(
            "Vegetation layer — the plant's physical position in the canopy."
        )
        picker_col.addWidget(self.layer_combo)

        picker_col.addWidget(QLabel("<b>Functions</b>"))
        functions_box = QFrame()
        functions_box.setStyleSheet(
            "QFrame { background: #18241a; border: 1px solid #2e4a2e; "
            "border-radius: 3px; }"
        )
        fl = QVBoxLayout(functions_box)
        fl.setContentsMargins(6, 4, 6, 4)
        fl.setSpacing(2)
        self.function_checks: dict[str, QCheckBox] = {}
        for fn in FUNCTIONS:
            cb = QCheckBox(fn.replace("_", " ").title())
            cb.setStyleSheet("QCheckBox { color: #c8e6c9; font-size: 11px; }")
            self.function_checks[fn] = cb
            fl.addWidget(cb)
        functions_box.setToolTip(
            "Ecological functions — what this plant does in the community.\n"
            "Multiple functions per plant are fine (e.g. understory + windbreak + pollinator)."
        )
        picker_col.addWidget(functions_box)

        # Filter the plant picker as soon as the user changes layer/function.
        self.layer_combo.currentIndexChanged.connect(self._refresh_plant_list)
        for cb in self.function_checks.values():
            cb.toggled.connect(self._refresh_plant_list)

        body.addLayout(picker_col, 1)

        # Centre — visual canvas with zoom slider
        centre_col = QVBoxLayout()
        self.canvas = PolycultureGridCanvas(self, radius_m=6.0)
        self._zoom_label = QLabel(self._zoom_label_text(self.canvas.radius_m()))
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        centre_col.addWidget(self._zoom_label)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom:"))
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        # 3..30 m visible radius. 6 m is the default.
        self._zoom_slider.setRange(3, 30)
        self._zoom_slider.setValue(int(self.canvas.radius_m()))
        self._zoom_slider.setToolTip(
            "Visible radius of the community canvas. "
            "The community itself has no fixed size — this only changes "
            "how much area you can see and place into at once."
        )
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_row.addWidget(self._zoom_slider, 1)
        centre_col.addLayout(zoom_row)

        self.canvas.memberAdded.connect(self._on_canvas_add)
        self.canvas.memberRemoved.connect(self._on_canvas_remove)
        self.canvas.memberMoved.connect(self._on_canvas_move)
        centre_col.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignHCenter)

        # "Populate from Recipe" — autofills the canvas with hex-packed
        # members in the ratios from a saved recipe.
        populate_row = QHBoxLayout()
        populate_row.addWidget(QLabel("Populate from recipe:"))
        self._recipe_combo = QComboBox()
        self._recipe_combo.setToolTip(
            "Pick a saved Recipe and click Populate to fill the canvas "
            "with hex-packed members in the recipe's ratios."
        )
        self._refresh_recipe_combo()
        populate_row.addWidget(self._recipe_combo, 1)
        populate_btn = QPushButton("Populate")
        populate_btn.clicked.connect(self._on_populate_from_recipe)
        populate_row.addWidget(populate_btn)
        centre_col.addLayout(populate_row)

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
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save Community")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._refresh_plant_list()

    def _refresh_plant_list(self, *_):
        text = (self.plant_search.text() or "").strip().lower()
        ab_only = self.ab_only.isChecked()
        type_f  = (self.type_combo.currentData()  if hasattr(self, "type_combo")  else "") or ""
        sun_f   = (self.sun_combo.currentData()   if hasattr(self, "sun_combo")   else "") or ""
        water_f = (self.water_combo.currentData() if hasattr(self, "water_combo") else "") or ""
        use_f   = (self.use_combo.currentData()   if hasattr(self, "use_combo")   else "") or ""

        # Layer + functions bias the plant ordering — matching plants
        # sort to the top. They do not hard-filter so the user can still
        # pick anything (matches the spirit of the previous role combo).
        layer_sel = (self.layer_combo.currentData()
                     if hasattr(self, "layer_combo") else None)
        fn_selected = [fn for fn, cb in getattr(self, "function_checks", {}).items()
                       if cb.isChecked()]
        layer_hint = LAYER_TYPE_HINTS.get(layer_sel or "", None)
        fn_keywords = [FUNCTION_PERM_KEYWORDS[fn] for fn in fn_selected
                       if fn in FUNCTION_PERM_KEYWORDS]

        self.plant_list.clear()
        preferred: list[tuple[str, str, dict]] = []  # (display_name, ptype, plant)
        others: list[tuple[str, str, dict]] = []

        for p in self._all_plants:
            if ab_only and not _truthy_int(p.get("native_to_alberta")):
                continue
            if type_f and (p.get("plant_type") or "") != type_f:
                continue
            if sun_f and (p.get("sun_requirement") or "") != sun_f:
                continue
            if water_f and (p.get("water_needs") or "") != water_f:
                continue
            if use_f:
                uses_raw = (p.get("permaculture_uses") or "").lower()
                tokens = {
                    t.strip()
                    for chunk in uses_raw.split(",")
                    for t in chunk.split("|")
                }
                if use_f.lower() not in tokens:
                    continue
            name = p.get("common_name", "") or ""
            sci = p.get("scientific_name", "") or ""
            if text and text not in name.lower() and text not in sci.lower():
                continue
            ptype = p.get("plant_type", "") or ""
            puses = (p.get("permaculture_uses") or "").lower()

            matches_layer = bool(layer_hint) and ptype in layer_hint
            matches_fn = any(kw in puses for kw in fn_keywords) if fn_keywords else False
            entry = (name, ptype, p)
            if matches_layer or matches_fn:
                preferred.append(entry)
            else:
                others.append(entry)

        def _add(items):
            for name, ptype, p in items:
                item = QListWidgetItem(f"{name}  ({ptype})" if ptype else name)
                item.setData(Qt.ItemDataRole.UserRole, p)
                self.plant_list.addItem(item)

        _add(preferred)
        if preferred and others:
            sep = QListWidgetItem("─────")
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            self.plant_list.addItem(sep)
        _add(others)

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
        layer = self.layer_combo.currentData()
        functions = [fn for fn, cb in self.function_checks.items() if cb.isChecked()]
        # Legacy single-value role: layer wins, then first function, else 'other'.
        role = layer or (functions[0] if functions else "other")
        self.canvas.add_member({
            "plant_id":    plant["id"],
            "common_name": plant.get("common_name", ""),
            "role":        role,
            "layer":       layer,
            "functions":   functions,
            "color":       _plant_color_for_member(plant),
            "spacing_m":   float(plant.get("spacing_meters") or 1.0),
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
            tags = []
            if m.get("layer"):
                tags.append(m["layer"].replace("_", " "))
            for fn in (m.get("functions") or []):
                tags.append(fn.replace("_", " "))
            if not tags and m.get("role"):
                tags.append((m.get("role") or "").replace("_", " "))
            tag_str = ", ".join(tags) or "—"
            self.member_list.addItem(QListWidgetItem(
                f"{m.get('common_name','?')} — {tag_str} "
                f"({m.get('offset_x',0):+.1f}, {m.get('offset_y',0):+.1f}) m"
            ))
        n = len(members)
        if n < 5:
            note = "  (aim for 5–8)"
        elif n > 8:
            note = "  (large community; consider trimming)"
        else:
            note = "  ✓ in the 5–8 sweet spot for native plant communities"
        self.count_label.setText(f"{n} plant{'s' if n != 1 else ''} placed{note}")

    def _on_clear_all(self):
        self.canvas.set_members([])
        self._refresh_member_list()

    # ── Zoom slider ─────────────────────────────────────────────────────────

    @staticmethod
    def _zoom_label_text(radius_m: float) -> str:
        return (
            f"<b>Community layout</b> "
            f"<span style='color:#90a4ae;'>(~{radius_m:.0f} m visible radius)</span>"
        )

    def _on_zoom_changed(self, value: int):
        self.canvas.setRadius(float(value))
        self._zoom_label.setText(self._zoom_label_text(float(value)))

    # ── Populate from recipe ────────────────────────────────────────────────

    def _refresh_recipe_combo(self):
        self._recipe_combo.blockSignals(True)
        self._recipe_combo.clear()
        try:
            recipes = recipes_db.get_all_recipes()
        except Exception:
            recipes = []
        if not recipes:
            self._recipe_combo.addItem("(no saved recipes)", None)
            self._recipe_combo.setEnabled(False)
        else:
            self._recipe_combo.addItem("— select a recipe —", None)
            for r in recipes:
                self._recipe_combo.addItem(r.get("name") or "(unnamed)", r.get("id"))
            self._recipe_combo.setEnabled(True)
        self._recipe_combo.blockSignals(False)

    def _on_populate_from_recipe(self):
        recipe_id = self._recipe_combo.currentData()
        if not recipe_id:
            QMessageBox.information(
                self, "Pick a recipe",
                "Select a saved Recipe from the dropdown first.\n"
                "Create one in the Plant Community tab → Recipes section."
            )
            return
        try:
            recipe = recipes_db.get_recipe_by_id(int(recipe_id))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not load recipe:\n{exc}")
            return
        if not recipe or not recipe.get("members"):
            QMessageBox.information(self, "Empty recipe",
                                    "That recipe has no members.")
            return

        from src.polyculture import (
            hex_pack_disc_local, resolve_spacing, assign_species,
            optimize_layout,
        )
        species = recipes_db.recipe_to_species_list(recipe)
        spacing_m = species.get("effective_spacing_m") or resolve_spacing(
            species["species"], "max"
        )
        radius_m = self.canvas.radius_m()
        positions = hex_pack_disc_local(radius_m, spacing_m)
        if not positions:
            QMessageBox.information(
                self, "No room",
                f"The recipe's effective spacing ({spacing_m:.1f} m) is "
                f"too wide for the current visible radius ({radius_m:.0f} m).\n"
                "Zoom out and try again."
            )
            return

        # Assign species to positions in the recipe's ratios, then permute
        # to spread same-species members apart. assign_species/optimize_layout
        # expect [lat, lng] but treat them generically as 2D — passing local
        # (x, y) tuples works because the distance metric is symmetric.
        pseudo_latlng = [[y, x] for (x, y) in positions]
        assignments = assign_species(pseudo_latlng, species["species"])
        try:
            assignments = optimize_layout(pseudo_latlng, assignments)
        except Exception:
            pass

        plants_by_id = {p["id"]: p for p in self._all_plants}
        members = []
        for (x_m, y_m), sp in zip(positions, assignments):
            plant = plants_by_id.get(int(sp["id"])) or {}
            members.append({
                "plant_id":    sp["id"],
                "common_name": sp.get("common_name") or plant.get("common_name", ""),
                "role":        "other",
                "layer":       None,
                "functions":   [],
                "color":       (sp.get("color") or _plant_color_for_member(plant)),
                "spacing_m":   float(sp.get("spacing_m") or 1.0),
                "offset_x":    round(x_m, 2),
                "offset_y":    round(y_m, 2),
            })
        self.canvas.set_members(members)
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
                "layer":       m.get("layer"),
                "functions":   list(m.get("functions") or []),
                "color":       _plant_color_for_member(plant or {}),
                "spacing_m":   float((plant or {}).get("spacing_meters") or 1.0),
                "offset_x":    float(m.get("offset_x") or 0.0),
                "offset_y":    float(m.get("offset_y") or 0.0),
            })
        self.canvas.set_members(members)

    def _on_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required",
                                "Please give the plant community a name.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name":        self.name_input.text().strip(),
            "description": self.desc_input.text().strip(),
            "members":     self.canvas.get_members(),
        }


class _RecipePlantPicker(QDialog):
    """Tiny modal to pick a plant to add to a recipe."""

    def __init__(self, parent=None, exclude_ids: set | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add plant to recipe")
        self.setMinimumSize(380, 460)
        self._chosen: dict | None = None

        all_plants = plants_db.get_all_plants()
        excluded = exclude_ids or set()
        all_plants = [p for p in all_plants if p.get("id") not in excluded]

        layout = QVBoxLayout(self)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search plants…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._refresh)
        layout.addWidget(self._search)

        self._ab_only = QCheckBox("Alberta natives only")
        self._ab_only.setChecked(True)
        self._ab_only.toggled.connect(self._refresh)
        layout.addWidget(self._ab_only)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_accept_item)
        layout.addWidget(self._list, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._all_plants = all_plants
        self._refresh()

    def _refresh(self, *_):
        text = (self._search.text() or "").strip().lower()
        ab_only = self._ab_only.isChecked()
        self._list.clear()
        for p in self._all_plants:
            if ab_only and not _truthy_int(p.get("native_to_alberta")):
                continue
            name = p.get("common_name", "") or ""
            sci = p.get("scientific_name", "") or ""
            if text and text not in name.lower() and text not in sci.lower():
                continue
            ptype = p.get("plant_type", "")
            it = QListWidgetItem(f"{name}  ({ptype})" if ptype else name)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self._list.addItem(it)

    def _on_accept(self):
        it = self._list.currentItem()
        if it is None:
            self.reject()
            return
        self._chosen = it.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _on_accept_item(self, item):
        self._chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def chosen(self) -> dict | None:
        return self._chosen


class RecipePanel(QWidget):
    """Persistent Recipe (ratio-only polyculture mix) editor.

    Recipes live in the polyculture_recipes/polyculture_recipe_members
    tables and can be:
      - placed on the map via the Plants tab (Place Mix flow), or
      - used to auto-populate a Community circle in the builder
        (Populate from Recipe), or
      - derived from an existing Community via the "→ Recipe" button.
    """

    recipesChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_recipe_id: int | None = None
        self._draft_members: list[dict] = []  # working copy until Save
        self._build_ui()
        self._refresh_recipe_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel(
            "<b>Polyculture Recipes</b> "
            "<span style='color:#90a4ae;font-weight:normal;'>"
            "(ratio mixes — no spatial layout)</span>"
        ))

        # Top row: recipe list
        self._recipe_list = QListWidget()
        self._recipe_list.setMaximumHeight(160)
        self._recipe_list.currentItemChanged.connect(self._on_recipe_selected)
        layout.addWidget(self._recipe_list)

        # Action buttons row
        btn_row = QHBoxLayout()
        for label, slot in [
            ("New", self._on_new),
            ("Duplicate", self._on_duplicate),
            ("Delete", self._on_delete),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(_POLY_BTN_STYLE)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        # Detail editor
        form = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Goldenrod + Aster mix")
        form.addRow("Name:", self._name_input)
        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText("Optional description")
        form.addRow("Description:", self._desc_input)
        layout.addLayout(form)

        layout.addWidget(QLabel("<b>Members</b>"))
        # Member rows live in a container; each row carries its own
        # ratio spinner and × button.
        self._members_container = QWidget()
        self._members_layout = QVBoxLayout(self._members_container)
        self._members_layout.setContentsMargins(0, 0, 0, 0)
        self._members_layout.setSpacing(2)
        layout.addWidget(self._members_container)

        self._empty_label = QLabel(
            "<span style='color:#78909c;'>No members yet — click "
            "Add Plant… to build the mix.</span>"
        )
        layout.addWidget(self._empty_label)

        bottom_btn_row = QHBoxLayout()
        self._add_plant_btn = QPushButton("Add Plant…")
        self._add_plant_btn.setStyleSheet(_POLY_BTN_STYLE)
        self._add_plant_btn.clicked.connect(self._on_add_plant)
        bottom_btn_row.addWidget(self._add_plant_btn)

        self._save_btn = QPushButton("Save Changes")
        self._save_btn.setStyleSheet(_POLY_BTN_STYLE)
        self._save_btn.clicked.connect(self._on_save)
        bottom_btn_row.addWidget(self._save_btn)

        self._populate_btn = QPushButton("→ New Community")
        self._populate_btn.setStyleSheet(_POLY_BTN_STYLE)
        self._populate_btn.setToolTip(
            "Create a new Plant Community by hex-packing this recipe "
            "into a circle (using the current ratios)."
        )
        self._populate_btn.clicked.connect(self._on_populate_community)
        bottom_btn_row.addWidget(self._populate_btn)

        bottom_btn_row.addStretch(1)
        layout.addLayout(bottom_btn_row)

        layout.addStretch(1)
        self._enable_detail(False)

    def refresh(self):
        """Re-pull recipes from the DB (called when other panes mutate them)."""
        self._refresh_recipe_list()

    # ── Recipe list ─────────────────────────────────────────────────────

    def _refresh_recipe_list(self):
        current_id = self._current_recipe_id
        self._recipe_list.blockSignals(True)
        self._recipe_list.clear()
        try:
            recipes = recipes_db.get_all_recipes()
        except Exception:
            recipes = []
        for r in recipes:
            it = QListWidgetItem(r.get("name") or "(unnamed)")
            it.setData(Qt.ItemDataRole.UserRole, r.get("id"))
            self._recipe_list.addItem(it)
            if current_id is not None and r.get("id") == current_id:
                self._recipe_list.setCurrentItem(it)
        self._recipe_list.blockSignals(False)
        if self._recipe_list.currentItem() is None:
            self._load_recipe(None)

    def _on_recipe_selected(self, current, _previous):
        if current is None:
            self._load_recipe(None)
            return
        recipe_id = current.data(Qt.ItemDataRole.UserRole)
        self._load_recipe(recipe_id)

    def _load_recipe(self, recipe_id):
        self._current_recipe_id = recipe_id
        if recipe_id is None:
            self._name_input.clear()
            self._desc_input.clear()
            self._draft_members = []
            self._render_members()
            self._enable_detail(False)
            return
        try:
            recipe = recipes_db.get_recipe_by_id(int(recipe_id))
        except Exception:
            recipe = None
        if not recipe:
            self._load_recipe(None)
            return
        self._name_input.setText(recipe.get("name") or "")
        self._desc_input.setText(recipe.get("description") or "")
        self._draft_members = [
            {
                "plant_id": m["plant_id"],
                "common_name": m.get("common_name", ""),
                "plant_type": m.get("plant_type", ""),
                "spacing_meters": m.get("spacing_meters") or 1.0,
                "weight": int(m.get("weight") or 1),
                "marker_color": m.get("marker_color")
                                or m.get("plant_marker_color") or None,
            }
            for m in (recipe.get("members") or [])
        ]
        self._render_members()
        self._enable_detail(True)

    def _enable_detail(self, enabled: bool):
        self._name_input.setEnabled(enabled)
        self._desc_input.setEnabled(enabled)
        self._add_plant_btn.setEnabled(enabled)
        self._save_btn.setEnabled(enabled)
        self._populate_btn.setEnabled(enabled)

    # ── Members editor ──────────────────────────────────────────────────

    def _render_members(self):
        # Clear container
        while self._members_layout.count():
            it = self._members_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        if not self._draft_members:
            self._empty_label.setVisible(True)
            return
        self._empty_label.setVisible(False)
        for idx, member in enumerate(self._draft_members):
            row = self._build_member_row(idx, member)
            self._members_layout.addWidget(row)

    def _build_member_row(self, idx: int, member: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background: #1e2e1e; border: 1px solid #2e4a2e; "
            "border-radius: 3px; }"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 2, 4, 2)
        rl.setSpacing(4)

        name = QLabel(member.get("common_name") or "—")
        name.setStyleSheet("color: #c8e6c9; font-size: 11px;")
        rl.addWidget(name, 1)

        spin = QSpinBox()
        spin.setRange(1, 99)
        spin.setValue(int(member.get("weight") or 1))
        spin.setFixedWidth(48)
        spin.setToolTip("Ratio weight for this species in the mix.")
        spin.valueChanged.connect(lambda v, i=idx: self._on_weight_changed(i, v))
        rl.addWidget(spin)

        rm = QPushButton("✕")
        rm.setFixedSize(20, 20)
        rm.setStyleSheet(
            "QPushButton { background: transparent; color: #ef9a9a; "
            "border: 1px solid transparent; border-radius: 3px; }"
            "QPushButton:hover { border-color: #8a4a4a; background: #2e1a1a; }"
        )
        rm.clicked.connect(lambda _checked=False, i=idx: self._on_remove_member(i))
        rl.addWidget(rm)
        return row

    def _on_weight_changed(self, idx: int, value: int):
        if 0 <= idx < len(self._draft_members):
            self._draft_members[idx]["weight"] = max(1, int(value))

    def _on_remove_member(self, idx: int):
        if 0 <= idx < len(self._draft_members):
            self._draft_members.pop(idx)
            self._render_members()

    # ── Actions ─────────────────────────────────────────────────────────

    def _on_new(self):
        name, ok = QInputDialog.getText(
            self, "New Recipe", "Name for the new recipe:"
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if recipes_db.get_recipe_by_name(name) is not None:
            QMessageBox.warning(self, "Name in use",
                                "A recipe with that name already exists.")
            return
        try:
            new_id = recipes_db.create_recipe(name)
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not create recipe:\n{exc}")
            return
        self._current_recipe_id = new_id
        self._refresh_recipe_list()
        self.recipesChanged.emit()

    def _on_duplicate(self):
        if self._current_recipe_id is None:
            return
        try:
            new_id = recipes_db.duplicate_recipe(int(self._current_recipe_id))
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not duplicate recipe:\n{exc}")
            return
        if new_id:
            self._current_recipe_id = new_id
            self._refresh_recipe_list()
            self.recipesChanged.emit()

    def _on_delete(self):
        if self._current_recipe_id is None:
            return
        reply = QMessageBox.question(
            self, "Delete Recipe",
            f"Delete recipe '{self._name_input.text()}'?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            recipes_db.delete_recipe(int(self._current_recipe_id))
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not delete recipe:\n{exc}")
            return
        self._current_recipe_id = None
        self._refresh_recipe_list()
        self.recipesChanged.emit()

    def _on_add_plant(self):
        excluded = {m["plant_id"] for m in self._draft_members}
        picker = _RecipePlantPicker(self, exclude_ids=excluded)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return
        plant = picker.chosen()
        if not plant or not plant.get("id"):
            return
        self._draft_members.append({
            "plant_id": plant["id"],
            "common_name": plant.get("common_name", ""),
            "plant_type": plant.get("plant_type", ""),
            "spacing_meters": plant.get("spacing_meters") or 1.0,
            "weight": 1,
            "marker_color": plant.get("marker_color") or None,
        })
        self._render_members()

    def _on_save(self):
        if self._current_recipe_id is None:
            return
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required",
                                "Please give the recipe a name.")
            return
        # Detect a name collision with a different recipe.
        existing = recipes_db.get_recipe_by_name(name)
        if existing and existing.get("id") != self._current_recipe_id:
            QMessageBox.warning(self, "Name in use",
                                "Another recipe already uses that name.")
            return
        try:
            recipes_db.update_recipe(
                int(self._current_recipe_id),
                name=name,
                description=self._desc_input.text().strip(),
            )
            recipes_db.replace_recipe_members(
                int(self._current_recipe_id), self._draft_members
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not save recipe:\n{exc}")
            return
        self._refresh_recipe_list()
        self.recipesChanged.emit()

    def _on_populate_community(self):
        """Create a new Plant Community pre-populated from this recipe."""
        if self._current_recipe_id is None or not self._draft_members:
            return
        name, ok = QInputDialog.getText(
            self, "New Community from Recipe",
            "Name for the new plant community:",
            text=(self._name_input.text() or "New Community"),
        )
        if not ok or not name.strip():
            return
        dialog = PolycultureBuilderDialog(self, polyculture_id=None)
        # Pre-fill the name, then trigger the populate flow via the
        # builder's recipe combo.
        dialog.name_input.setText(name.strip())
        # Find the current recipe entry in the combo and run populate.
        for i in range(dialog._recipe_combo.count()):
            if dialog._recipe_combo.itemData(i) == self._current_recipe_id:
                dialog._recipe_combo.setCurrentIndex(i)
                break
        dialog._on_populate_from_recipe()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            new_id = polycultures.create_polyculture(
                data["name"], data["description"], None
            )
            polycultures.replace_polyculture_members(new_id, data["members"])
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not create community:\n{exc}")
            return
        QMessageBox.information(
            self, "Community created",
            f"Plant community '{data['name']}' created from recipe."
        )


class PolyculturePanel(QWidget):
    placePolycultureRequested = pyqtSignal(dict)  # polyculture data with members
    # Emitted when a recipe is created, updated, or deleted so the
    # builder dialog (and any other view) can refresh.
    recipesChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh_polyculture_list()

    def _build_ui(self):
        from PyQt6.QtWidgets import QTabWidget
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Two sub-tabs: Communities (spatial library) and Recipes (ratio-only mixes).
        tabs = QTabWidget()
        outer.addWidget(tabs)

        # ── Communities sub-tab ─────────────────────────────────────────
        communities_widget = QWidget()
        layout = QVBoxLayout(communities_widget)
        layout.setContentsMargins(8, 8, 8, 8)

        label = QLabel("<b>Plant Community Library</b>  <span style='color:#90a4ae;font-weight:normal;'>(saved communities)</span>")
        layout.addWidget(label)

        # Search/filter box
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search communities...")
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
        self.new_btn = QPushButton("New Community")
        self.new_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.new_btn.clicked.connect(self._on_new_polyculture)
        btn_row1.addWidget(self.new_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_polyculture)
        btn_row1.addWidget(self.delete_btn)

        self.dup_btn = QPushButton("Duplicate")
        self.dup_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.dup_btn.setEnabled(False)
        self.dup_btn.clicked.connect(self._on_duplicate_polyculture)
        btn_row1.addWidget(self.dup_btn)

        self.variation_btn = QPushButton("+ Variation")
        self.variation_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.variation_btn.setEnabled(False)
        self.variation_btn.setToolTip("Create a variation of this plant community")
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
        self.edit_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setToolTip(
            "Open the visual builder for this plant community"
        )
        self.edit_btn.clicked.connect(self._on_edit_polyculture)
        member_btns.addWidget(self.edit_btn)
        member_btns.addStretch(1)
        layout.addLayout(member_btns)

        # Action buttons
        btn_row2 = QHBoxLayout()
        self.place_btn = QPushButton("Place on Map")
        self.place_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.place_btn.setEnabled(False)
        self.place_btn.clicked.connect(self._on_place)
        btn_row2.addWidget(self.place_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        btn_row2.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.import_btn.clicked.connect(self._on_import)
        btn_row2.addWidget(self.import_btn)

        self.derive_recipe_btn = QPushButton("→ Recipe")
        self.derive_recipe_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.derive_recipe_btn.setEnabled(False)
        self.derive_recipe_btn.setToolTip(
            "Derive a Recipe (ratio mix) from this community's member counts"
        )
        self.derive_recipe_btn.clicked.connect(self._on_derive_recipe)
        btn_row2.addWidget(self.derive_recipe_btn)
        layout.addLayout(btn_row2)

        # ── Pattern controls for community placement ─────────────────────
        self._build_community_pattern_controls(layout)

        tabs.addTab(communities_widget, "Communities")

        # ── Recipes sub-tab ──────────────────────────────────────────────
        self.recipe_panel = RecipePanel(self)
        # Bi-directional refresh: any change inside the Recipes pane bubbles
        # up; changes elsewhere (e.g. Derive Recipe button) push back down.
        self.recipe_panel.recipesChanged.connect(self.recipesChanged.emit)
        self.recipesChanged.connect(self.recipe_panel.refresh)
        tabs.addTab(self.recipe_panel, "Recipes")

    def _build_community_pattern_controls(self, parent_layout):
        """Add a small pattern selector (Single/Row/Grid/Circle) under the
        Communities action buttons. When the selected pattern is non-Single,
        clicking Place on Map enters a multi-anchor placement: each click
        drops a row/grid/circle of the selected community."""
        box = QGroupBox("Place as pattern")
        box.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        bl = QVBoxLayout(box)
        bl.setContentsMargins(6, 4, 6, 4)
        bl.setSpacing(3)

        kind_row = QHBoxLayout()
        kind_row.addWidget(QLabel("Pattern:"))
        self.pattern_combo = QComboBox()
        for label, kind in [("Single", "single"), ("Row", "row"),
                            ("Grid", "grid"), ("Circle", "circle")]:
            self.pattern_combo.addItem(label, kind)
        kind_row.addWidget(self.pattern_combo, 1)
        bl.addLayout(kind_row)

        spacing_row = QHBoxLayout()
        spacing_row.addWidget(QLabel("Cell spacing:"))
        self.pattern_spacing = QDoubleSpinBox()
        self.pattern_spacing.setRange(0.5, 100.0)
        self.pattern_spacing.setDecimals(1)
        self.pattern_spacing.setValue(4.0)
        self.pattern_spacing.setSuffix(" m")
        self.pattern_spacing.setToolTip(
            "Centre-to-centre spacing between community instances. "
            "Defaults to 2× the selected community's natural radius "
            "(its widest member offset)."
        )
        spacing_row.addWidget(self.pattern_spacing)
        bl.addLayout(spacing_row)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Count (row/circle):"))
        self.pattern_count = QSpinBox()
        self.pattern_count.setRange(0, 200)
        self.pattern_count.setValue(0)
        self.pattern_count.setSpecialValueText("auto")
        self.pattern_count.setToolTip(
            "Number of communities for row/circle patterns "
            "(auto = derived from spacing). Ignored for grid."
        )
        count_row.addWidget(self.pattern_count)
        bl.addLayout(count_row)

        parent_layout.addWidget(box)

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
        self.derive_recipe_btn.setEnabled(has_selection)
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
            tags = []
            if m.get("layer"):
                tags.append(m["layer"].replace("_", " "))
            for fn in (m.get("functions") or []):
                tags.append(fn.replace("_", " "))
            if not tags and m.get("role"):
                tags.append((m.get("role") or "").replace("_", " "))
            tag_str = ", ".join(tags) or "—"
            text = f"{m['common_name']} — {tag_str} ({m['offset_x']}m, {m['offset_y']}m)"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, m["id"])
            self.members_list.addItem(item)

        # Pre-fill the cell-spacing field with the community's natural diameter.
        try:
            natural_r = polycultures.community_natural_radius(polyculture)
            self.pattern_spacing.setValue(round(max(0.5, natural_r * 2.0), 1))
        except Exception:
            pass

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
            QMessageBox.critical(self, "Error", f"Could not create plant community:\n{e}")
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
            QMessageBox.critical(self, "Error", f"Could not save plant community:\n{e}")
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
            self, "Delete Plant Community",
            "Delete this plant community from the library?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                polycultures.delete_polyculture(polyculture_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete plant community:\n{e}")
                return
            self._refresh_polyculture_list()

    def _on_duplicate_polyculture(self):
        polyculture_id = self._get_selected_polyculture_id()
        if not polyculture_id:
            return
        try:
            polycultures.duplicate_polyculture(polyculture_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not duplicate plant community:\n{e}")
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
        if not polyculture:
            return

        # Attach the pattern config so app.py knows whether to single-place
        # the community or to fan it across a row/grid/circle.
        kind = self.pattern_combo.currentData() or "single"
        if kind != "single":
            spacing = float(self.pattern_spacing.value() or 4.0)
            count_val = self.pattern_count.value()
            polyculture = dict(polyculture)
            polyculture["pattern"] = {
                "kind": kind,
                "spacing_m": spacing,
                "count": (None if count_val == 0 else int(count_val)),
            }
        self.placePolycultureRequested.emit(polyculture)

    def _on_derive_recipe(self):
        """Derive a Recipe (ratio mix) from the selected community.

        Member counts per plant_id become weights, GCD-reduced so a
        4:2:2 community becomes 2:1:1. Prompts for a recipe name and
        emits recipesChanged so the Recipes tab refreshes.
        """
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        polyculture = polycultures.get_polyculture_by_id(polyculture_id)
        if not polyculture or not polyculture.get("members"):
            return

        from math import gcd
        from functools import reduce
        counts: dict[int, int] = {}
        for m in polyculture.get("members") or []:
            pid = m.get("plant_id")
            if not pid:
                continue
            counts[pid] = counts.get(pid, 0) + 1
        if not counts:
            return
        g = reduce(gcd, counts.values())
        if g > 1:
            counts = {pid: c // g for pid, c in counts.items()}

        default_name = f"{polyculture.get('name', 'Community')} recipe"
        name, ok = QInputDialog.getText(
            self, "Derive Recipe from Community",
            "Name for the new recipe:", text=default_name,
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        # Avoid UNIQUE-constraint collision by suffixing.
        target_name = name
        suffix = 2
        while recipes_db.get_recipe_by_name(target_name) is not None:
            target_name = f"{name} {suffix}"
            suffix += 1

        try:
            recipe_id = recipes_db.create_recipe(target_name)
            recipes_db.replace_recipe_members(recipe_id, [
                {"plant_id": pid, "weight": w} for pid, w in counts.items()
            ])
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not create recipe:\n{exc}")
            return

        self.recipesChanged.emit()
        QMessageBox.information(
            self, "Recipe created",
            f"Recipe '{target_name}' created with "
            f"{len(counts)} species in ratio "
            f"{':'.join(str(c) for c in counts.values())}.\n\n"
            "Find it under the Recipes tab."
        )

    def _on_export(self):
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        data = polycultures.export_polyculture(polyculture_id)
        if not data:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plant Community", f"{data['name']}.polyculture.json",
            "Plant Community Files (*.polyculture.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export", f"Plant community exported to {path}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Plant Community", "",
            "Plant Community Files (*.polyculture.json);;JSON Files (*.json)"
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
                "Plant community imported with warnings:\n" + "\n".join(warnings)
            )
        else:
            QMessageBox.information(self, "Import", "Plant community imported successfully!")


# Mirror plant_panel._PLACE_BTN_STYLE so every action button in the
# Polyculture tab looks pressable, gives hover/pressed feedback, and
# stays visually consistent with the "Place Mix on Map" button users
# see one tab over.
_POLY_BTN_STYLE = """
QPushButton {
    background: #2e7d32;
    color: #e8f5e9;
    border: none;
    border-radius: 4px;
    padding: 7px 12px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover    { background: #388e3c; }
QPushButton:pressed  { background: #1b5e20; }
QPushButton:disabled { background: #2a3a2a; color: #4a6a4a; }
"""
