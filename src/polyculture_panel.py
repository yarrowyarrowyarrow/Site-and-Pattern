import json
import re

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QSettings
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
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db import polycultures
from src.db import plants as plants_db
from src.placement_controls import _QTY_SPIN_STYLE


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


class PolyculturePanel(QWidget):
    placePolycultureRequested = pyqtSignal(dict)  # polyculture data with members
    fillAreaRequested = pyqtSignal(int, float)    # polyculture_id, cell spacing (m)
    # Emitted when the panel creates a brand-new community (e.g. via
    # "Save stack as Community" from the Plants tab), so external views
    # can refresh their library lists.
    communityCreated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh_polyculture_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Library title with an inline "show / hide variations" toggle on
        # the right. State persisted in QSettings; default hidden.
        settings = QSettings()
        self._show_variations = settings.value(
            "plant_communities/show_variations", False, type=bool
        )

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_label = QLabel(
            "<b>Plant Community Library</b>  "
            "<span style='color:#90a4ae;font-weight:normal;'>(saved communities)</span>"
        )
        title_row.addWidget(title_label, 1)
        self.variations_toggle_btn = QPushButton(
            "▾ Hide variations" if self._show_variations else "▸ Show variations"
        )
        self.variations_toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #90a4ae; "
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "padding: 1px 8px; font-size: 10px; }"
            "QPushButton:hover { color: #c8e6c9; border-color: #4a7a4a; }"
        )
        self.variations_toggle_btn.setToolTip(
            "Show or hide variations (children) of each plant community."
        )
        self.variations_toggle_btn.clicked.connect(self._on_toggle_variations)
        title_row.addWidget(self.variations_toggle_btn)
        layout.addLayout(title_row)

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
        self.polyculture_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.polyculture_tree.customContextMenuRequested.connect(
            self._on_tree_context_menu
        )
        layout.addWidget(self.polyculture_tree)

        # Community-mix stack — populated by right-click → "Add to Mix".
        # When ≥2 communities are in the mix, Row/Grid/Circle placement
        # distributes communities across positions in their ratios.
        self._mix_communities: list[dict] = []
        self._MIX_COMMUNITY_MAX = 8

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

        # Toggle to reveal/hide the description block. Hiding it frees
        # vertical space so more members are visible at once. Persisted
        # in QSettings; default shown (matches the prior behaviour).
        self._show_description = QSettings().value(
            "plant_communities/show_description", True, type=bool
        )
        self.description_toggle_btn = QPushButton(
            "▾ Hide description" if self._show_description
            else "▸ Show description"
        )
        self.description_toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #90a4ae; "
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "padding: 1px 8px; font-size: 10px; }"
            "QPushButton:hover { color: #c8e6c9; border-color: #4a7a4a; }"
        )
        self.description_toggle_btn.setToolTip(
            "Show or hide the community description to make room for "
            "more members in the list below."
        )
        self.description_toggle_btn.clicked.connect(self._on_toggle_description)
        toggle_row = QHBoxLayout()
        toggle_row.addStretch(1)
        toggle_row.addWidget(self.description_toggle_btn)
        layout.addLayout(toggle_row)

        # Detail area
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        self.detail_text.setVisible(self._show_description)
        layout.addWidget(self.detail_text)

        # Members list — compact rows with inline triangle expand. Each
        # row is a custom QFrame (see _build_member_row); detail content
        # (layer/functions + offset) is hidden by default to keep density
        # tight, matching the Plants browser's expand-on-click pattern.
        members_label = QLabel("<b>Members</b>")
        layout.addWidget(members_label)

        self._members_scroll = QScrollArea()
        self._members_scroll.setWidgetResizable(True)
        self._members_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._members_scroll.setMaximumHeight(180)
        self._members_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.members_container = QWidget()
        self._members_layout = QVBoxLayout(self.members_container)
        self._members_layout.setContentsMargins(0, 0, 0, 0)
        self._members_layout.setSpacing(1)
        self._members_layout.addStretch(1)
        self._members_scroll.setWidget(self.members_container)
        layout.addWidget(self._members_scroll)

        # Single action row: Place on Map gets visual priority (stretch=2),
        # Edit shares the row at a smaller weight, Export/Import are
        # compact fixed-width buttons so they don't crowd the primary.
        action_row = QHBoxLayout()
        action_row.setSpacing(4)

        self.place_btn = QPushButton("Place on Map")
        self.place_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.place_btn.setEnabled(False)
        self.place_btn.setMinimumWidth(110)
        self.place_btn.clicked.connect(self._on_place)
        action_row.addWidget(self.place_btn, 2)

        self.fill_area_btn = QPushButton("Fill Area")
        self.fill_area_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.fill_area_btn.setEnabled(False)
        self.fill_area_btn.setToolTip(
            "Draw an area on the map and fill it with this community, scattered "
            "at the cell spacing below."
        )
        self.fill_area_btn.clicked.connect(self._on_fill_area)
        action_row.addWidget(self.fill_area_btn, 1)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setToolTip(
            "Open the visual builder for this plant community"
        )
        self.edit_btn.clicked.connect(self._on_edit_polyculture)
        action_row.addWidget(self.edit_btn, 1)

        self.export_btn = QPushButton("Export")
        self.export_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.export_btn.setEnabled(False)
        self.export_btn.setFixedWidth(64)
        self.export_btn.setToolTip("Export this community to a .plant-community.json file")
        self.export_btn.clicked.connect(self._on_export)
        action_row.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.setStyleSheet(_POLY_BTN_STYLE)
        self.import_btn.setFixedWidth(64)
        self.import_btn.setToolTip("Import a community from a .plant-community.json or .polyculture.json file")
        self.import_btn.clicked.connect(self._on_import)
        action_row.addWidget(self.import_btn)

        layout.addLayout(action_row)

        # ── Pattern controls for community placement ─────────────────────
        self._build_community_pattern_controls(layout)

        # ── Community Mix inline panel ──────────────────────────────────
        self._build_community_mix_controls(layout)

    def _build_community_mix_controls(self, parent_layout):
        """Inline ratio-mix builder for placing several plant communities
        in a row/grid/circle at user-set ratios. Right-click a community
        in the tree → 'Add to Community Mix'."""
        mix_box = QGroupBox("Plant Communities Mix")
        mix_box.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        ml = QVBoxLayout(mix_box)
        ml.setContentsMargins(6, 6, 6, 6)
        ml.setSpacing(3)

        self._mix_community_status = QLabel(
            "Mix off — right-click a community in the list to add it.\n"
            "With ≥2 communities, Row/Grid/Circle will distribute them in "
            "the chosen ratios."
        )
        self._mix_community_status.setWordWrap(True)
        self._mix_community_status.setStyleSheet(
            "color: #78909c; font-size: 10px;"
        )
        ml.addWidget(self._mix_community_status)

        self._mix_community_rows = QWidget()
        self._mix_community_layout = QVBoxLayout(self._mix_community_rows)
        self._mix_community_layout.setContentsMargins(0, 2, 0, 2)
        self._mix_community_layout.setSpacing(2)
        self._mix_community_rows.setVisible(False)
        ml.addWidget(self._mix_community_rows)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._mix_community_place_btn = QPushButton("Place Mix on Map")
        self._mix_community_place_btn.setStyleSheet(_POLY_BTN_STYLE)
        self._mix_community_place_btn.setEnabled(False)
        self._mix_community_place_btn.setToolTip(
            "Place the community mix using the current pattern "
            "(Row / Grid / Circle)."
        )
        self._mix_community_place_btn.clicked.connect(
            self._on_place_community_mix
        )
        btn_row.addWidget(self._mix_community_place_btn)

        self._mix_community_clear_btn = QPushButton("Clear mix")
        self._mix_community_clear_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #ef9a9a; "
            "border: 1px solid #4a2e2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #8a4a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._mix_community_clear_btn.setEnabled(False)
        self._mix_community_clear_btn.clicked.connect(self._clear_community_mix)
        btn_row.addWidget(self._mix_community_clear_btn)
        btn_row.addStretch()
        ml.addLayout(btn_row)

        parent_layout.addWidget(mix_box)

    # ── Tree right-click menu ───────────────────────────────────────────

    def _on_tree_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        item = self.polyculture_tree.itemAt(pos)
        if item is None:
            return
        polyculture_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not polyculture_id:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e2e1e; color: #c8e6c9; "
            "border: 1px solid #2e4a2e; }"
            "QMenu::item:selected { background: #2e4a2e; }"
        )
        in_mix = any(c["id"] == polyculture_id for c in self._mix_communities)
        if in_mix:
            act = menu.addAction("Remove from Community Mix")
            act.triggered.connect(
                lambda: self._remove_from_community_mix(int(polyculture_id))
            )
        else:
            act = menu.addAction("Add to Community Mix")
            act.triggered.connect(
                lambda: self._add_to_community_mix(int(polyculture_id))
            )
            if len(self._mix_communities) >= self._MIX_COMMUNITY_MAX:
                act.setEnabled(False)
                act.setText(f"Mix full ({self._MIX_COMMUNITY_MAX} max)")
        menu.exec(self.polyculture_tree.viewport().mapToGlobal(pos))

    # ── Community-mix state ─────────────────────────────────────────────

    def _add_to_community_mix(self, polyculture_id: int):
        if any(c["id"] == polyculture_id for c in self._mix_communities):
            return
        if len(self._mix_communities) >= self._MIX_COMMUNITY_MAX:
            return
        polyculture = polycultures.get_polyculture_by_id(polyculture_id)
        if not polyculture:
            return
        self._mix_communities.append({
            "id": int(polyculture_id),
            "name": polyculture.get("name") or "(unnamed)",
            "weight": 1,
            "polyculture": polyculture,
        })
        self._refresh_community_mix()

    def _remove_from_community_mix(self, polyculture_id: int):
        before = len(self._mix_communities)
        self._mix_communities = [
            c for c in self._mix_communities if c["id"] != polyculture_id
        ]
        if len(self._mix_communities) != before:
            self._refresh_community_mix()

    def _clear_community_mix(self):
        if not self._mix_communities:
            return
        self._mix_communities = []
        self._refresh_community_mix()

    def _refresh_community_mix(self):
        # Clear existing rows.
        while self._mix_community_layout.count():
            it = self._mix_community_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        n = len(self._mix_communities)
        if n == 0:
            self._mix_community_status.setText(
                "Mix off — right-click a community in the list to add it.\n"
                "With ≥2 communities, Row/Grid/Circle will distribute them "
                "in the chosen ratios."
            )
            self._mix_community_rows.setVisible(False)
            self._mix_community_place_btn.setEnabled(False)
            self._mix_community_clear_btn.setEnabled(False)
            return
        if n == 1:
            self._mix_community_status.setText(
                "Mix: 1 community (need ≥2 to activate).\n"
                "Add at least one more, then choose Row/Grid/Circle."
            )
        else:
            ratios = ":".join(str(int(c["weight"])) for c in self._mix_communities)
            self._mix_community_status.setText(
                f"Plant community mix: {n} communities at {ratios}. "
                f"Pick Row/Grid/Circle and click Place Mix on Map."
            )
        self._mix_community_rows.setVisible(True)
        self._mix_community_clear_btn.setEnabled(True)
        self._mix_community_place_btn.setEnabled(n >= 2)

        for idx, c in enumerate(self._mix_communities):
            row = self._build_community_mix_row(idx, c)
            self._mix_community_layout.addWidget(row)

    def _build_community_mix_row(self, idx: int, community: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background: #1e2e1e; border: 1px solid #2e4a2e; "
            "border-radius: 3px; }"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 2, 4, 2)
        rl.setSpacing(4)
        name = QLabel(community.get("name") or "—")
        name.setStyleSheet("color: #c8e6c9; font-size: 11px;")
        rl.addWidget(name, 1)
        spin = QSpinBox()
        spin.setRange(1, 99)
        spin.setValue(int(community.get("weight") or 1))
        spin.setFixedWidth(56)
        spin.setStyleSheet(_QTY_SPIN_STYLE)
        spin.setToolTip("Ratio weight for this community in the mix.")
        spin.valueChanged.connect(
            lambda v, i=idx: self._on_community_mix_weight_changed(i, v)
        )
        rl.addWidget(spin)
        rm = QPushButton("✕")
        rm.setFixedSize(20, 20)
        rm.setStyleSheet(
            "QPushButton { background: transparent; color: #ef9a9a; "
            "border: 1px solid transparent; border-radius: 3px; }"
            "QPushButton:hover { border-color: #8a4a4a; background: #2e1a1a; }"
        )
        cid = community["id"]
        rm.clicked.connect(
            lambda _checked=False, pid=cid: self._remove_from_community_mix(pid)
        )
        rl.addWidget(rm)
        return row

    def _on_community_mix_weight_changed(self, idx: int, value: int):
        if 0 <= idx < len(self._mix_communities):
            self._mix_communities[idx]["weight"] = max(1, int(value))
            n = len(self._mix_communities)
            if n >= 2:
                ratios = ":".join(
                    str(int(c["weight"])) for c in self._mix_communities
                )
                self._mix_community_status.setText(
                    f"Plant community mix: {n} communities at {ratios}. "
                    f"Pick Row/Grid/Circle and click Place Mix on Map."
                )

    def _on_place_community_mix(self):
        """Emit a placement request for the community mix.

        We embed the mix in the same ``pattern`` dict the single-community
        flow uses; app.py recognises ``params['community_mix']`` and
        dispatches to per-anchor community expansion."""
        if len(self._mix_communities) < 2:
            return
        pattern = self.placement_widget.current_pattern()
        kind = pattern["kind"]
        if kind == "single":
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Pick a pattern",
                "Community mixes need Row, Grid, or Circle pattern. "
                "Switch the pattern above and try again."
            )
            return
        spacing = float(self.pattern_spacing.value() or 4.0)
        # Use the first member of the first community as a representative
        # plant so the JS preview ghost has something to size.
        first = self._mix_communities[0]["polyculture"]
        representative = dict(first)
        params = dict(pattern.get("params") or {})
        params["community_mix"] = [
            {
                "id": c["id"],
                "weight": int(c["weight"]),
                "name": c["name"],
                "polyculture": c["polyculture"],
            }
            for c in self._mix_communities
        ]
        representative["pattern"] = {
            "kind": kind,
            "spacing_m": spacing,
            "params": params,
        }
        self.placePolycultureRequested.emit(representative)

    def _build_community_pattern_controls(self, parent_layout):
        """Shared placement controls (Single/Row/Grid/Circle + overlap +
        stagger + fill) plus a per-community Cell-spacing spinner.

        When the pattern is non-Single, clicking Place on Map enters a
        multi-anchor placement: each click drops a row/grid/circle of
        the selected community."""
        from src.placement_controls import PlacementControlsWidget
        self.placement_widget = PlacementControlsWidget(
            show_canopy_base=False,
            title="Placement Mode",
        )
        parent_layout.addWidget(self.placement_widget)

        spacing_box = QGroupBox("Community spacing")
        spacing_box.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        sl = QHBoxLayout(spacing_box)
        sl.setContentsMargins(8, 12, 8, 6)
        sl.addWidget(QLabel("Cell spacing:"))
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
        sl.addWidget(self.pattern_spacing)
        sl.addStretch(1)
        parent_layout.addWidget(spacing_box)

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
                # Expand when (a) the user has globally enabled variation
                # display, or (b) the active search hit a variation under
                # this parent — in the search case, show only the matching
                # parents expanded.
                if self._show_variations or (search and child_match):
                    item.setExpanded(True)
                else:
                    item.setExpanded(False)

    def _on_toggle_variations(self):
        """Flip the show-variations preference and re-render the tree."""
        self._show_variations = not self._show_variations
        QSettings().setValue(
            "plant_communities/show_variations", self._show_variations
        )
        self.variations_toggle_btn.setText(
            "▾ Hide variations" if self._show_variations
            else "▸ Show variations"
        )
        self._refresh_polyculture_list()

    def _on_toggle_description(self):
        """Flip the show-description preference. Hiding frees ~150 px
        for the members list below."""
        self._show_description = not self._show_description
        QSettings().setValue(
            "plant_communities/show_description", self._show_description
        )
        self.description_toggle_btn.setText(
            "▾ Hide description" if self._show_description
            else "▸ Show description"
        )
        self.detail_text.setVisible(self._show_description)

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
        self.fill_area_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)
        self.edit_btn.setEnabled(has_selection)
        # Only allow adding variations to top-level polycultures
        is_top_level = has_selection and (current.parent() is None)
        self.variation_btn.setEnabled(is_top_level)

        if not has_selection:
            self.detail_text.clear()
            self._render_member_rows([])
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

        self._render_member_rows(polyculture.get("members", []))

        # Pre-fill the cell-spacing field with the community's natural diameter.
        try:
            natural_r = polycultures.community_natural_radius(polyculture)
            self.pattern_spacing.setValue(round(max(0.5, natural_r * 2.0), 1))
        except Exception:
            pass

    # ── Members list (compact rows with inline expand) ─────────────────

    def _render_member_rows(self, members: list):
        """Clear and rebuild the member rows. Each row is a tiny QFrame
        with a triangle toggle for the detail line (layer/functions +
        offset). Matches the visual density target in the design plan
        (~22 px per row vs the legacy QListWidget's ~40 px)."""
        # Remove existing rows but keep the trailing stretch item.
        layout = self._members_layout
        while layout.count() > 1:
            it = layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for m in members:
            row = self._build_member_row(m)
            layout.insertWidget(layout.count() - 1, row)

    def _build_member_row(self, member: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background: #1a2a1a; border: 1px solid #2e4a2e; "
            "border-radius: 3px; }"
        )
        outer = QVBoxLayout(row)
        outer.setContentsMargins(2, 1, 2, 1)
        outer.setSpacing(0)

        # Top line: triangle + common name
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(4)
        triangle = QToolButton()
        triangle.setText("▸")
        triangle.setStyleSheet(
            "QToolButton { background: transparent; color: #90a4ae; "
            "border: none; padding: 0px 2px; font-size: 11px; }"
            "QToolButton:hover { color: #c8e6c9; }"
        )
        triangle.setCursor(Qt.CursorShape.PointingHandCursor)
        head.addWidget(triangle)
        name = QLabel(member.get("common_name") or "—")
        name.setStyleSheet("color: #c8e6c9; font-size: 11px;")
        head.addWidget(name, 1)
        outer.addLayout(head)

        # Detail block — lazy-loaded HTML label matching the Plants
        # browser's expanded row (zones, sun/water, spacing, height,
        # bloom/fruit, edible, uses) plus this member's community-
        # specific tags (layer/functions + offset). Built on first
        # expand so closed rows don't hit the DB.
        detail = QLabel()
        detail.setStyleSheet(
            "QLabel { color: #cfd8dc; font-size: 11px; "
            "padding: 2px 4px 4px 18px; }"
        )
        detail.setTextFormat(Qt.TextFormat.RichText)
        detail.setWordWrap(True)
        detail.setVisible(False)
        outer.addWidget(detail)

        def _build_detail_html():
            try:
                from src.db.plants import get_plant
                plant = get_plant(member.get("plant_id")) or {}
            except Exception:
                plant = {}
            from src.plant_panel import (
                _SUN_LABELS, _WATER_LABELS, _USE_LABELS,
            )
            zmin = plant.get("hardiness_zone_min")
            zmax = plant.get("hardiness_zone_max")
            if zmin and zmax:
                zones = f"Z{zmin}–{zmax}"
            elif zmin:
                zones = f"Z{zmin}+"
            else:
                zones = "—"
            sun = _SUN_LABELS.get(plant.get("sun_requirement", ""), "—")
            water = _WATER_LABELS.get(plant.get("water_needs", ""), "—")
            spacing = plant.get("spacing_meters")
            height = plant.get("mature_height_meters")
            bloom = plant.get("bloom_period") or "—"
            fruit = plant.get("fruit_period") or "—"
            edible = plant.get("edible_parts") or "—"
            uses_raw = plant.get("permaculture_uses") or ""
            uses = ", ".join(
                _USE_LABELS.get(u.strip(), u.strip())
                for u in uses_raw.split(",") if u.strip()
            ) or "—"
            notes = (plant.get("notes") or "").strip()
            sci = plant.get("scientific_name") or ""

            tags = []
            if member.get("layer"):
                tags.append(str(member["layer"]).replace("_", " "))
            for fn in (member.get("functions") or []):
                tags.append(str(fn).replace("_", " "))
            if not tags and member.get("role"):
                tags.append(str(member.get("role") or "").replace("_", " "))
            tag_str = ", ".join(tags) or "—"
            ox = member.get("offset_x", 0)
            oy = member.get("offset_y", 0)

            rows: list[str] = []
            if sci:
                rows.append(f"<i style='color:#90a4ae;'>{sci}</i>")
            rows.append(
                f"<b style='color:#78909c;'>Position:</b> {tag_str} · "
                f"({ox} m, {oy} m)"
            )
            rows.append(f"<b style='color:#78909c;'>Zones:</b> {zones}")
            rows.append(
                f"<b style='color:#78909c;'>Sun · Water:</b> {sun} · {water}"
            )
            rows.append(
                f"<b style='color:#78909c;'>Spacing:</b> "
                f"{f'{spacing} m' if spacing else '—'}"
            )
            rows.append(
                f"<b style='color:#78909c;'>Height:</b> "
                f"{f'{height} m' if height else '—'}"
            )
            rows.append(
                f"<b style='color:#78909c;'>Bloom · Fruit:</b> {bloom} · {fruit}"
            )
            rows.append(f"<b style='color:#78909c;'>Edible:</b> {edible}")
            rows.append(f"<b style='color:#78909c;'>Uses:</b> {uses}")
            if notes:
                rows.append(
                    f"<div style='color:#b0bec5; margin-top: 4px;'>{notes}</div>"
                )
            return "<br>".join(rows)

        def _toggle(_checked=False):
            expanded = not detail.isVisible()
            if expanded and not detail.text():
                detail.setText(_build_detail_html())
            detail.setVisible(expanded)
            triangle.setText("▾" if expanded else "▸")

        triangle.clicked.connect(_toggle)
        # Make the name label clickable too — bigger hit target than
        # the small triangle glyph.
        name.setCursor(Qt.CursorShape.PointingHandCursor)
        name.mousePressEvent = lambda _ev: _toggle()
        return row

    def _get_selected_polyculture_id(self):
        item = self.polyculture_tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def _on_fill_area(self):
        """Ask the app to fill the last-drawn shape with the selected community
        at the current cell spacing (N3′). App resolves the target polygon."""
        poly_id = self._get_selected_polyculture_id()
        if poly_id is None:
            return
        spacing = float(getattr(self, "pattern_spacing", None).value()
                        if getattr(self, "pattern_spacing", None) else 4.0)
        self.fillAreaRequested.emit(int(poly_id), spacing)

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
        pattern = self.placement_widget.current_pattern()
        kind = pattern["kind"]
        if kind != "single":
            spacing = float(self.pattern_spacing.value() or 4.0)
            polyculture = dict(polyculture)
            polyculture["pattern"] = {
                "kind": kind,
                "spacing_m": spacing,
                "params": pattern.get("params") or {},
            }
        self.placePolycultureRequested.emit(polyculture)

    def _on_export(self):
        polyculture_id = self._get_selected_polyculture_id()
        if polyculture_id is None:
            return
        data = polycultures.export_polyculture(polyculture_id)
        if not data:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plant Community",
            f"{data['name']}.plant-community.json",
            "Plant Community Files (*.plant-community.json *.polyculture.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export", f"Plant community exported to {path}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Plant Community", "",
            "Plant Community Files (*.plant-community.json *.polyculture.json);;"
            "JSON Files (*.json)"
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
