import json

from PyQt6.QtCore import (
    Qt, pyqtSignal, QPointF, QRectF, QSettings, QMimeData, QByteArray, QTimer,
)
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
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
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db import polycultures
from src.filter_widgets import make_multi_combo


# Drag a community from the library tree → drop on the "Plant Communities Mix"
# (V1.87, mirrors the plant drag-to-mix on the Plant Library tab).
_COMMUNITY_MIME = "application/x-sap-community-id"


class _CommunityTree(QTreeWidget):
    """Library tree whose rows can be dragged (carrying the community id)."""

    def mimeTypes(self):
        return [_COMMUNITY_MIME]

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction

    def mimeData(self, items):
        md = QMimeData()
        for it in items:
            pid = it.data(0, Qt.ItemDataRole.UserRole)
            if pid:
                md.setData(_COMMUNITY_MIME, QByteArray(str(int(pid)).encode()))
                break
        return md


class _CommunityMixDropGroupBox(QGroupBox):
    """The 'Plant Communities Mix' box, made a drop target so a community can be
    dragged from the library straight in. ``on_drop`` receives the community id."""

    def __init__(self, title: str, on_drop, parent=None):
        super().__init__(title, parent)
        self._on_drop = on_drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(_COMMUNITY_MIME):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(_COMMUNITY_MIME):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasFormat(_COMMUNITY_MIME):
            try:
                pid = int(bytes(e.mimeData().data(_COMMUNITY_MIME)).decode())
            except (ValueError, TypeError):
                return
            self._on_drop(pid)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)
from src.db import plants as plants_db
from src.placement_controls import _QTY_SPIN_STYLE


# Community-tree height bounds. With nothing selected the tree fills the panel
# (uncapped) so the user sees as many communities as fit; once a community is
# selected it shrinks to ~7 rows and hands the room to the members list +
# description card below. _TREE_EXPANDED_MAX is Qt's QWIDGETSIZE_MAX; the
# collapsed height is computed from the live row height × _TREE_COLLAPSED_ROWS.
_TREE_EXPANDED_MAX = 16_777_215
# Raised from 7 in V2.30. The cap hands room to the members list + description
# card, which is right — but it was also the binding constraint once the mix
# stopped stealing space, so the library showed seven rows of sixty on a tall
# window for no reason.
_TREE_COLLAPSED_ROWS = 10
# ...and a FLOOR, which the panel never had. The tree was the only stretch
# child with no minimum height, so it was the only widget in the column that
# could be squeezed, and everything that grew below it grew at its expense.
_TREE_MIN_ROWS = 6
# The community mix scrolls past this many rows instead of growing without end.
_MIX_ROWS_VISIBLE = 4

# "Group By" lenses for the community library (V1.88). Each key (other than
# "none") matches a facet from polycultures.get_community_facets(); the panel
# buckets communities under bold, unselectable category nodes.
_GROUP_BY_OPTIONS = [
    ("none",      "No grouping"),
    ("function",  "By Function"),
    ("habitat",   "By Habitat"),
    ("structure", "By Structure"),
    ("sun",       "By Sun"),
    ("moisture",  "By Moisture"),
]
_GROUP_COMBO_STYLE = (
    "QComboBox { background: #1e2e1e; color: #c8e6c9; border: 1px solid #2e4a2e; "
    "border-radius: 3px; padding: 1px 6px; font-size: 11px; }"
    "QComboBox:hover { border-color: #4a7a4a; }"
    "QComboBox QAbstractItemView { background: #1e2e1e; color: #c8e6c9; "
    "border: 1px solid #2e4a2e; selection-background-color: #2e5a2e; }"
)

# Sort orders for the community library (V2.13). Keys match
# polycultures.sort_community_ids; label prefix keeps the closed combo legible
# next to the facet dropdowns.
_SORT_BY_OPTIONS = [
    ("name",     "Sort: A–Z"),
    ("members",  "Sort: Most members"),
    ("wildlife", "Sort: Most wildlife"),
    ("native",   "Sort: Most native"),
    ("modified", "Sort: Recently changed"),
]

# Facet filter dropdowns (V2.13): (facet key, placeholder). Facet keys match
# polycultures.facet_filter_choices() / the entry["facets"] labels.
_FACET_FILTER_SPECS = [
    ("sun",       "Any sun"),
    ("moisture",  "Any moisture"),
    ("structure", "Any structure"),
    ("habitat",   "Any habitat"),
    ("function",  "Any function"),
]


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
        s = self._scale()
        for idx in range(len(self._members) - 1, -1, -1):
            m = self._members[idx]
            mx, my = self._world_to_pixel(m["offset_x"], m["offset_y"])
            # Match the painted canopy disc so the whole visible plant is
            # grabbable. A fixed 12px only covered the tiny centre pip, so
            # clicks on the disc missed and fell through to the "add" path —
            # popping the "Pick a plant" modal instead of starting a drag.
            r_px = max(8.0, (float(m.get("spacing_m") or 1.0) / 2.0) * s)
            if (px - mx) ** 2 + (py - my) ** 2 <= r_px * r_px:
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


def next_free_offset(members, radius_m: float, *, gap_m: float = 0.8) -> tuple:
    """Where the keyboard puts the next member: the first point of a sunflower
    spiral out from the centre that is ``gap_m`` clear of every member and
    inside ``radius_m``. Deterministic, so the same steps give the same
    community. Falls back to the centre when the circle is full."""
    import math
    taken = [(float(m.get("offset_x") or 0), float(m.get("offset_y") or 0))
             for m in members or []]
    golden = math.pi * (3 - math.sqrt(5))
    for k in range(400):
        r = 0.9 * math.sqrt(k)
        if r > radius_m - 0.3:
            break
        x, y = r * math.cos(k * golden), r * math.sin(k * golden)
        if all((x - tx) ** 2 + (y - ty) ** 2 >= gap_m ** 2 for tx, ty in taken):
            return round(x, 2), round(y, 2)
    return 0.0, 0.0


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


class PolycultureBuilderDialog(QDialog):
    """One-screen visual editor for a polyculture (create or modify).

    Replaced the older one-plant-at-a-time AddMemberDialog flow. The
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
            "Pick a plant + role on the left, then click the grid (or press Enter"
            " in the list) to place it. Right-click a placed plant, or Delete in "
            "Members, to remove it. Drag to reposition. Native habitat plant "
            "communities typically have 5–8 species.</span>"
        )
        tip.setWordWrap(True)
        outer.addWidget(tip)

        body = QHBoxLayout()

        # Left — the plant picker every plant list shares (F192, V3.00): the
        # search, the filters and the list the Browse tab and the Plant
        # Directory show. Until V3.00 this was a checkbox, four single-choice
        # dropdowns and a list of plain strings, filtered here in Python. It
        # starts on natives only, as the checkbox did, and the layer and
        # functions chosen below lift matching plants to the top.
        from src.plant_picker import PlantPicker
        picker_col = QVBoxLayout()
        picker_col.addWidget(QLabel("<b>Plants</b>"))
        self.picker = PlantPicker(self, criteria={"native_only": True})
        self.picker.setMinimumWidth(240)
        picker_col.addWidget(self.picker, 1)

        layer_label = QLabel("<b>Layer</b>")
        picker_col.addWidget(layer_label)
        self.layer_combo = QComboBox()
        layer_label.setBuddy(self.layer_combo)   # read with it (V3.02)
        self.layer_combo.setAccessibleName("Layer")
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

        # The layer and functions chosen lift matching plants to the top.
        self.layer_combo.currentIndexChanged.connect(self._refresh_hint)
        for cb in self.function_checks.values():
            cb.toggled.connect(self._refresh_hint)

        body.addLayout(picker_col, 1)

        # Centre — visual canvas with zoom slider
        centre_col = QVBoxLayout()
        self.canvas = PolycultureGridCanvas(self, radius_m=6.0)
        self._zoom_label = QLabel(self._zoom_label_text(self.canvas.radius_m()))
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        centre_col.addWidget(self._zoom_label)

        zoom_row = QHBoxLayout()
        zoom_label = QLabel("Zoom:")
        zoom_row.addWidget(zoom_label)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        zoom_label.setBuddy(self._zoom_slider)
        self._zoom_slider.setAccessibleName("Zoom")
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
        # The grid is drawn and takes the mouse; Members is its text, and the
        # keyboard's way in (V3.02): Enter in the plant list adds the plant,
        # Delete in Members removes one.
        self.canvas.setAccessibleName("Community layout")
        self.canvas.setAccessibleDescription(
            "Click to add the plant chosen on the left, right-click a plant to "
            "remove it, drag to move it. From the keyboard, Enter in the plant "
            "list adds it and Delete in Members removes one.")
        from src.place_action import ListGestures
        self._list_gestures = ListGestures(self.picker.view)
        self._list_gestures.place.connect(lambda _index: self._add_at_next_spot())
        centre_col.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignHCenter)

        self.count_label = QLabel("0 plants placed")
        self.count_label.setStyleSheet("color: #90a4ae; font-size: 11px;")
        centre_col.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignHCenter)

        arrange_btn = QPushButton("Auto-arrange by layer")
        arrange_btn.setToolTip(
            "Place members by vegetation layer: tree(s) centred, shrubs ringed "
            "around them, perennials in the next band, groundcover filling the "
            "rest. Replaces the current positions; drag to fine-tune afterward.")
        arrange_btn.clicked.connect(self._on_auto_arrange)
        centre_col.addWidget(arrange_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        arrange_radius_row = QHBoxLayout()
        radius_label = QLabel("Max radius:")
        arrange_radius_row.addWidget(radius_label)
        self._arrange_radius_slider = QSlider(Qt.Orientation.Horizontal)
        radius_label.setBuddy(self._arrange_radius_slider)
        self._arrange_radius_slider.setAccessibleName("Auto-arrange radius")
        # 2..30 m placement radius. 6 m matches the shipped communities.
        self._arrange_radius_slider.setRange(2, 30)
        self._arrange_radius_slider.setValue(6)
        self._arrange_radius_slider.setToolTip(
            "Cap how far Auto-arrange spreads the community outward. "
            "6 m matches the built-in communities; raise it for larger plantings."
        )
        self._arrange_radius_label = QLabel("6 m")
        self._arrange_radius_label.setStyleSheet("color: #90a4ae; font-size: 11px;")
        self._arrange_radius_slider.valueChanged.connect(
            lambda v: self._arrange_radius_label.setText(f"{v} m")
        )
        arrange_radius_row.addWidget(self._arrange_radius_slider, 1)
        arrange_radius_row.addWidget(self._arrange_radius_label)
        centre_col.addLayout(arrange_radius_row)
        body.addLayout(centre_col, 0)

        # Right — current members
        right_col = QVBoxLayout()
        members_label = QLabel("<b>Members</b>")
        right_col.addWidget(members_label)
        self.member_list = QListWidget()
        members_label.setBuddy(self.member_list)
        self.member_list.setAccessibleName("Members")
        self.member_list.setMinimumWidth(220)
        for key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            QShortcut(QKeySequence(key), self.member_list,
                      context=Qt.ShortcutContext.WidgetShortcut,
                      activated=self._remove_current_member)
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

        self.picker.refresh()

    def _refresh_hint(self, *_):
        """Lift the plants that match the layer and functions chosen to the top
        of the list. Nothing is hidden: the old role dropdown sorted matches
        first and left the rest pickable, and so does this."""
        layer_hint = LAYER_TYPE_HINTS.get(self.layer_combo.currentData() or "")
        keywords = [FUNCTION_PERM_KEYWORDS[fn]
                    for fn, cb in self.function_checks.items()
                    if cb.isChecked() and fn in FUNCTION_PERM_KEYWORDS]
        if not layer_hint and not keywords:
            self.picker.set_hint(None)
            return

        def matches(plant: dict) -> bool:
            if layer_hint and (plant.get("plant_type") or "") in layer_hint:
                return True
            uses = (plant.get("permaculture_uses") or "").lower()
            return any(kw in uses for kw in keywords)

        self.picker.set_hint(matches)

    def _selected_plant(self) -> dict | None:
        return self.picker.current_plant()

    def _on_canvas_add(self, x_m: float, y_m: float):
        plant = self._selected_plant()
        if plant is None:
            QMessageBox.information(
                self, "Pick a plant",
                "Select a plant from the list on the left, then click the grid "
                "(or press Enter in the list) to place it."
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

    def _add_at_next_spot(self):
        """The keyboard's add: the plant chosen in the list, at the first free
        spot of a sunflower spiral out from the centre (V3.02)."""
        if self._selected_plant() is None:
            return
        x_m, y_m = next_free_offset(self.canvas.get_members(),
                                    self.canvas.radius_m())
        self._on_canvas_add(x_m, y_m)

    def _remove_current_member(self):
        row = self.member_list.currentRow()
        if row < 0:
            return
        self._on_canvas_remove(row)
        if self.member_list.count():
            self.member_list.setCurrentRow(min(row, self.member_list.count() - 1))

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

    def _on_auto_arrange(self):
        """Lay the members out concentrically by layer (trees centred, shrubs
        ringed, perennials then groundcover filling) — F22. Non-destructive: only
        runs on click; the user can still drag afterward."""
        from src import planting_spacing
        members = self.canvas.get_members()
        if not members:
            return
        max_radius = float(self._arrange_radius_slider.value())
        arranged, radius = planting_spacing.arrange_concentric(
            members, max_radius_m=max_radius)
        # Grow the visible canvas + zoom slider so the arrangement fits.
        need = max(3.0, radius + 1.0)
        if need > self.canvas.radius_m():
            r = min(30.0, need)
            self.canvas.setRadius(r)
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(int(round(r)))
            self._zoom_slider.blockSignals(False)
            self._zoom_label.setText(self._zoom_label_text(r))
        self.canvas.set_members(arranged)
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


class _CreaturePickerDialog(QDialog):
    """Small modal picker for the "For a creature…" community generator: a
    grouped combo of native bees (genus-first) and butterflies & moths, mirroring
    the 3D fly-through's selector. ``pick()`` returns ``{"fid", "name"}`` or
    ``None`` if cancelled."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Design a community for a creature")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Choose a native pollinator. Its nectar plants — and, for a "
            "butterfly or moth, the host plants its caterpillars need — become "
            "a ready-to-plant community."))
        self._combo = QComboBox()
        self._populate(self._combo)
        layout.addWidget(self._combo)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _populate(combo):
        def _header(text):
            combo.addItem(text, userData=None)
            item = combo.model().item(combo.count() - 1)
            if item is not None:
                item.setEnabled(False)

        try:
            from src.bee_habitat import list_target_bees
            bees = list_target_bees()
        except Exception:      # noqa: BLE001
            bees = []
        genus = None
        for b in bees:
            if b["genus"] != genus:
                genus = b["genus"]
                _header(f"── {genus} ──")
            label = (f"    {b['common_name']} (any {b['genus']})" if b["is_group"]
                     else f"    {b['common_name']}")
            combo.addItem(label, userData={"fid": b["id"], "name": b["common_name"]})
        try:
            from src.lep_habitat import list_target_lepidoptera
            leps = list_target_lepidoptera()
        except Exception:      # noqa: BLE001
            leps = []
        if leps:
            _header("── Butterflies & Moths ──")
            for lp in leps:
                icon = "🌙" if lp["kind"] == "moth" else "🦋"
                combo.addItem(f"    {icon} {lp['common_name']}",
                              userData={"fid": lp["id"], "name": lp["common_name"]})
        for i in range(combo.count()):
            if combo.itemData(i) is not None:
                combo.setCurrentIndex(i)
                break

    def selected(self):
        return self._combo.itemData(self._combo.currentIndex())

    @classmethod
    def pick(cls, parent):
        dlg = cls(parent)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.selected()


class PolyculturePanel(QWidget):
    placePolycultureRequested = pyqtSignal(dict)  # polyculture data with members
    placementCancelled = pyqtSignal()             # nothing left to place (V2.37)
    # What the map is armed with, for the placement bar over it (V2.98):
    # {"armed", "what", "kind", "qty", "mix"}. See src/placement_bar_flow.py.
    armedChanged = pyqtSignal(dict)
    fillAreaRequested = pyqtSignal(int, float, bool)  # polyculture_id, cell spacing (m), matrix (F22)
    fillCommunityMixRequested = pyqtSignal(object, float, bool)  # [{id,weight,name,polyculture}], spacing, matrix (F22)
    # Emitted when the panel creates a brand-new community (e.g. via
    # "Save stack as Community" from the Plants tab), so external views
    # can refresh their library lists.
    communityCreated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # True while the map is armed with this panel's selected community.
        # MainWindow calls set_armed(False) when placement ends, so the bar
        # can never claim the map is listening when it isn't.
        self._armed = False
        # What was armed, captured at arming time, and whether it was the mix
        # (a setting that moves re-arms the same thing, not the selection).
        self._armed_what = ""
        self._armed_mix = False
        # The community a Place action named (V2.99), apart from the one being
        # looked at: re-arms use it, so a search or a glance elsewhere cannot
        # change what the map holds.
        self._armed_community_id = None
        from src.placement_arming import rearm_timer
        self._rearm_timer = rearm_timer(self, self._rearm)
        self._build_ui()
        self._refresh_polyculture_list()

    def _build_ui(self):
        # One column that scrolls when it cannot fit, rather than squeezing
        # its sections into each other: with a full mix at 1366 × 768 the
        # sections needed 806 px of a 670 px column (V2.98).
        from src.scroll_column import scroll_column
        layout = scroll_column(self)
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

        # Search box + a compact "Group By" lens dropdown beside it: pivot the
        # library between a flat list and category folders along an ecological
        # lens (Habitat / Structure / Sun / Moisture) without losing vertical
        # space (V1.88). Typing is debounced 200 ms (same rhythm as the Plant
        # Library) so the batched refresh runs once per pause, not per key.
        self._group_by = settings.value(
            "plant_communities/group_by", "none", type=str)
        self._sort_by = settings.value(
            "plant_communities/sort_by", "name", type=str)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._refresh_polyculture_list)
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search communities...")
        self._search_box.setAccessibleName("Search communities")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(
            lambda _t: self._search_timer.start())
        search_row.addWidget(self._search_box, 1)

        self._group_combo = QComboBox()
        self._group_combo.setToolTip(
            "Group the library by an ecological lens — pivot between\n"
            "environmental views (Habitat / Sun / Moisture) and spatial\n"
            "structure (Canopy / Understory / …)."
        )
        self._group_combo.setStyleSheet(_GROUP_COMBO_STYLE)
        self._group_combo.setAccessibleName("Group communities by")
        for key, label in _GROUP_BY_OPTIONS:
            self._group_combo.addItem(label, key)
        _gi = self._group_combo.findData(self._group_by)
        if _gi >= 0:
            self._group_combo.setCurrentIndex(_gi)   # before connecting → no early refresh
        self._group_combo.currentIndexChanged.connect(self._on_group_by_changed)
        search_row.addWidget(self._group_combo)
        layout.addLayout(search_row)

        # ── Facet filters + sort (V2.13) ──────────────────────────────────
        # Same multi-select UX as the Plant Library: OR within a facet, AND
        # across facets. Values are derived from each community's member
        # plants (polycultures.get_library_index), so a community shows up
        # under what it actually is, not what it was named.
        choices = polycultures.facet_filter_choices()
        self._facet_combos: dict = {}
        for facet, placeholder in _FACET_FILTER_SPECS:
            combo = make_multi_combo(
                placeholder, {label: label for label in choices[facet]},
                on_change=self._refresh_polyculture_list)
            # Named for a screen reader, which read all five as "combo box"
            # (V3.02); the placeholder is not a name.
            combo.setAccessibleName(f"{facet.capitalize()} filter")
            combo.lineEdit().setAccessibleName(f"{facet.capitalize()} filter")
            self._facet_combos[facet] = combo
        self._facet_combos["sun"].setToolTip(
            "Dominant sun need across the community's members.")
        self._facet_combos["moisture"].setToolTip(
            "Dominant moisture need across the community's members.")
        self._facet_combos["structure"].setToolTip(
            "Tallest vegetation layer the community reaches.")
        self._facet_combos["habitat"].setToolTip(
            "Ecoregions the member plants are documented from. A community\n"
            "belongs to every region its plants grow in, so it can appear\n"
            "under several; Generalist = no recorded region.")
        self._facet_combos["function"].setToolTip(
            "Ecological functions the community serves (from its members'\n"
            "use tags). A community can serve several.")

        filter_row1 = QHBoxLayout()
        filter_row1.setSpacing(4)
        filter_row1.addWidget(self._facet_combos["sun"], 1)
        filter_row1.addWidget(self._facet_combos["moisture"], 1)
        layout.addLayout(filter_row1)

        filter_row2 = QHBoxLayout()
        filter_row2.setSpacing(4)
        filter_row2.addWidget(self._facet_combos["structure"], 1)
        filter_row2.addWidget(self._facet_combos["habitat"], 1)
        layout.addLayout(filter_row2)

        filter_row3 = QHBoxLayout()
        filter_row3.setSpacing(4)
        filter_row3.addWidget(self._facet_combos["function"], 1)
        self._sort_combo = QComboBox()
        self._sort_combo.setToolTip(
            "Order the library — alphabetical, biggest communities, most\n"
            "wildlife supported, most Alberta-native, or recently changed."
        )
        self._sort_combo.setStyleSheet(_GROUP_COMBO_STYLE)
        self._sort_combo.setAccessibleName("Order communities by")
        for key, label in _SORT_BY_OPTIONS:
            self._sort_combo.addItem(label, key)
        _si = self._sort_combo.findData(self._sort_by)
        if _si >= 0:
            self._sort_combo.setCurrentIndex(_si)  # before connecting → no early refresh
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        filter_row3.addWidget(self._sort_combo, 1)
        self._result_count = QLabel("")
        self._result_count.setStyleSheet("color: #78909c; font-size: 11px;")
        filter_row3.addWidget(self._result_count)
        layout.addLayout(filter_row3)

        # Polyculture tree (parent polycultures + variations as children)
        self.polyculture_tree = _CommunityTree()
        self.polyculture_tree.setAccessibleName("Plant communities")
        self.polyculture_tree.setHeaderHidden(True)
        self.polyculture_tree.setIndentation(16)
        self.polyculture_tree.setMouseTracking(True)
        # Drag a community out of the library onto the "Plant Communities Mix"
        # box (V1.87).
        self.polyculture_tree.setDragEnabled(True)
        self.polyculture_tree.setDragDropMode(
            QAbstractItemView.DragDropMode.DragOnly)
        # Selecting shows the community; Enter, a double-click, the Place
        # button or the context menu place it (V2.99, src/place_action.py).
        self.polyculture_tree.currentItemChanged.connect(self._on_polyculture_selected)
        from src.place_action import ListGestures
        gestures = ListGestures(self.polyculture_tree)
        gestures.place.connect(self._on_list_place)
        gestures.choose.connect(self._on_list_choose)
        self.polyculture_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.polyculture_tree.customContextMenuRequested.connect(
            self._on_tree_context_menu
        )
        # Height is dynamic (see _on_polyculture_selected): with nothing
        # selected the tree fills the panel (stretch 1, uncapped) so the user
        # sees as many communities as fit; once a community is selected it
        # shrinks to ~7 rows and the members list + description card take over.
        self.polyculture_tree.setMaximumHeight(_TREE_EXPANDED_MAX)
        # A real floor: whatever else the panel wants to show, the library keeps
        # at least this many rows. Applied again after the first layout pass in
        # _apply_tree_floor(), when sizeHintForRow() finally knows the metrics.
        self.polyculture_tree.setMinimumHeight(_TREE_MIN_ROWS * 19)
        layout.addWidget(self.polyculture_tree, 1)

        # Community-mix stack — populated by right-click → "Add to Mix".
        # When ≥2 communities are in the mix, Row/Grid/Circle placement
        # distributes communities across positions in their ratios.
        self._mix_communities: list[dict] = []
        self._MIX_COMMUNITY_MAX = 8

        # Buttons row 1
        btn_row1 = QHBoxLayout()
        self.new_btn = QPushButton("New Community")
        self.new_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.new_btn.clicked.connect(self._on_new_polyculture)
        btn_row1.addWidget(self.new_btn)

        # "For a creature…" — generate a community tailored to a native bee,
        # butterfly or moth from its nectar + larval-host plants (V2.12).
        self.creature_btn = QPushButton("🦋 For a creature…")
        self.creature_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.creature_btn.setToolTip(
            "Build a plant community tailored to a native bee, butterfly or "
            "moth — its nectar plants and (for butterflies/moths) the host "
            "plants its caterpillars need.")
        self.creature_btn.clicked.connect(self._on_creature_community)
        btn_row1.addWidget(self.creature_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_polyculture)
        btn_row1.addWidget(self.delete_btn)

        self.dup_btn = QPushButton("Duplicate")
        self.dup_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.dup_btn.setEnabled(False)
        self.dup_btn.clicked.connect(self._on_duplicate_polyculture)
        btn_row1.addWidget(self.dup_btn)

        self.variation_btn = QPushButton("+ Variation")
        self.variation_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.variation_btn.setEnabled(False)
        self.variation_btn.setToolTip("Create a variation of this plant community")
        self.variation_btn.clicked.connect(self._on_add_variation)
        btn_row1.addWidget(self.variation_btn)
        layout.addLayout(btn_row1)

        # Second button row: Edit / Export / Import grouped with the library
        # actions above (Place on Map lives in the Placement panel instead).
        btn_row2 = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setToolTip("Open the visual builder for this plant community")
        self.edit_btn.clicked.connect(self._on_edit_polyculture)
        btn_row2.addWidget(self.edit_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.export_btn.setEnabled(False)
        self.export_btn.setToolTip("Export this community to a .plant-community.json file")
        self.export_btn.clicked.connect(self._on_export)
        btn_row2.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.setStyleSheet(_POLY_MGMT_BTN_STYLE)
        self.import_btn.setToolTip("Import a community from a .plant-community.json or .polyculture.json file")
        self.import_btn.clicked.connect(self._on_import)
        btn_row2.addWidget(self.import_btn)
        layout.addLayout(btn_row2)

        # ── Selected community: name + "Anchored on X · N plants" header ──
        # Shown above the members so the list sits directly under the title
        # (the long Problem/Context description follows below).
        self._community_header = QLabel("")
        self._community_header.setTextFormat(Qt.TextFormat.RichText)
        self._community_header.setWordWrap(True)
        # Place rides on the name's row (V2.99), so it costs the list no
        # height; its accessible name says which community it places.
        from src.place_action import PlaceButton
        self._place_btn = PlaceButton("community", compact=True)
        self._place_btn.clicked.connect(
            lambda: self._place_community(self._get_selected_polyculture_id()))
        self._community_header_row = QWidget()
        header_row = QHBoxLayout(self._community_header_row)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.addWidget(self._community_header, 1)
        header_row.addWidget(self._place_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._community_header_row.setVisible(False)
        layout.addWidget(self._community_header_row)

        # ── Members (full compact list, auto-sized to its content) ───────
        # The pattern toggle rides on the right of this label row (rather than
        # in its own band) so there's no empty strip above the description.
        self._show_description = QSettings().value(
            "plant_communities/show_description", True, type=bool
        )
        self._members_label = QLabel("<b>Members</b>")
        self._members_label.setVisible(False)
        members_header = QHBoxLayout()
        members_header.addWidget(self._members_label)
        members_header.addStretch(1)
        self.description_toggle_btn = self._build_description_toggle_btn()
        members_header.addWidget(self.description_toggle_btn)
        layout.addLayout(members_header)

        self._members_scroll = QScrollArea()
        self._members_scroll.setWidgetResizable(True)
        self._members_scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Height set to fit every row (up to a ceiling) in _render_member_rows,
        # so the whole members list is visible without scrolling for normal
        # community sizes.
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

        # ── Pattern description card ─────────────────────────────────────
        # (The show/hide toggle lives on the Members label row above; the
        # _show_description preference was read there.)
        # The Alexander pattern card (F4): Problem / Context / Forces / Solution
        # / Related, rendered with include_header=False (the name + "Anchored
        # on …" line is shown above in self._community_header). QTextBrowser →
        # clickable related-pattern links. stretch=1: fills the remaining space.
        self.detail_text = QTextBrowser()
        self.detail_text.setAccessibleName("Community details")
        self.detail_text.setOpenLinks(False)   # we handle community: links ourselves
        # 96, not 120 (V2.98): the card scrolls itself, and at 1366 × 768 the
        # extra 24 px was what made the whole column scroll by 15.
        self.detail_text.setMinimumHeight(96)
        # Hidden until a community is selected — otherwise the empty card (also
        # stretch 1) competes with the tree for space and the list can't fill
        # the panel on open. The selection handler shows/hides it from here.
        self.detail_text.setVisible(False)
        self.detail_text.anchorClicked.connect(self._on_pattern_link)
        layout.addWidget(self.detail_text, 1)

        # ── Placement settings: built here, shown in the bar over the map ───
        # Until V2.98 these and the mix shared a collapsible "Placement" section
        # at the foot of this column, which does not scroll: selecting a
        # community and opening it left the list 6 of 61 rows and the pattern
        # buttons 11 px (0 px at 1366 × 768). The settings now live in the bar
        # (src/placement_bar_flow.py adopts them); the mix stays, because
        # communities are dragged into it from the list.
        self._build_community_pattern_controls()
        self._build_community_mix_controls(layout)

    def _build_community_mix_controls(self, parent_layout):
        """Inline ratio-mix builder for placing several plant communities
        in a row/grid/circle at user-set ratios. Right-click a community
        in the tree → 'Add to Community Mix'."""
        mix_box = _CommunityMixDropGroupBox(
            "Plant Communities Mix", self._add_to_community_mix)
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
            "Drag or right-click communities here to build a mix."
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
        # The rows scroll past four. Un-capped, eight communities added ~200 px
        # of hard, non-shrinkable content to a pane that sits at stretch 0, and
        # a QVBoxLayout gives a stretch-0 child its whole sizeHint before the
        # stretch children get anything — so every row added came straight out
        # of the community list above, which is the reported bug: the library
        # collapsed to about three visible rows out of sixty.
        self._mix_community_scroll = QScrollArea()
        self._mix_community_scroll.setWidgetResizable(True)
        self._mix_community_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._mix_community_scroll.setWidget(self._mix_community_rows)
        self._mix_community_scroll.setMaximumHeight(_MIX_ROWS_VISIBLE * 26 + 8)
        self._mix_community_scroll.setVisible(False)
        ml.addWidget(self._mix_community_scroll)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._mix_community_place_btn = QPushButton("Place mix")
        self._mix_community_place_btn.setStyleSheet(_POLY_BTN_STYLE)
        self._mix_community_place_btn.setEnabled(False)
        self._mix_community_place_btn.setToolTip(
            "Place the whole mix: in a row unless the bar over the map says "
            "otherwise."
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
        # Hidden while the mix is empty, as in the plant mix.
        self._mix_community_actions = QWidget()
        btn_row.setContentsMargins(0, 0, 0, 0)
        self._mix_community_actions.setLayout(btn_row)
        self._mix_community_actions.setVisible(False)
        ml.addWidget(self._mix_community_actions)

        # Minimum vertical policy, the call src/plant_panel.py makes too: the
        # strip takes its sizeHint and no more, so a growing mix cannot
        # out-compete the stretch children above it.
        mix_box.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Minimum)
        self._mix_community_box = mix_box
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
        # The plant list's menu leads with its plain verb (the review's
        # favourite control in the panel); communities lacked it (V2.99).
        act_place = menu.addAction(f"Place {item.text(0).strip()} on Map")
        act_place.triggered.connect(
            lambda: self._place_community(int(polyculture_id)))
        menu.addSeparator()
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
        self._mix_community_actions.setVisible(n > 0)
        # An armed mix follows its rows, like an armed species list does; with
        # fewer than two left there is no mix, and the map stands down.
        if self._armed and self._armed_mix:
            if n >= 2:
                self._rearm()
            else:
                self.placementCancelled.emit()
        if n == 0:
            self._mix_community_status.setText(
                "Drag or right-click communities here to build a mix."
            )
            self._mix_community_rows.setVisible(False)
            self._mix_community_scroll.setVisible(False)
            self._mix_community_place_btn.setEnabled(False)
            self._mix_community_clear_btn.setEnabled(False)
            return
        if n == 1:
            self._mix_community_status.setText(
                "1 community — add ≥1 more to activate."
            )
        else:
            self._mix_community_status.setText(self._mix_status_text())
        self._mix_community_rows.setVisible(True)
        self._mix_community_scroll.setVisible(True)
        self._mix_community_clear_btn.setEnabled(True)
        self._mix_community_place_btn.setEnabled(n >= 2)

        for idx, c in enumerate(self._mix_communities):
            row = self._build_community_mix_row(idx, c)
            self._mix_community_layout.addWidget(row)
        # Ask Qt to recompute geometry once the new rows have been laid out and
        # contribute to sizeHint.
        QTimer.singleShot(0, self._refit_mix_pane)

    def _fit_mix_rows(self):
        """Show every row up to _MIX_ROWS_VISIBLE, then scroll. A scroll area
        asks for its minimum, not its content: measured in V2.98, a
        two-community mix got 34 px of the 70 its rows need."""
        cap = _MIX_ROWS_VISIBLE * 26 + 8
        self._mix_community_scroll.setFixedHeight(
            min(self._mix_community_rows.sizeHint().height() + 2, cap))

    def _mix_status_text(self) -> str:
        ratios = ":".join(str(int(c["weight"])) for c in self._mix_communities)
        return (f"{len(self._mix_communities)} communities at {ratios}. "
                "Place mix plants them together.")

    def _refit_mix_pane(self):
        """Recompute the mix strip's geometry after the mix grows/shrinks.

        Its rows scroll past _MIX_ROWS_VISIBLE, so it settles at a bounded
        height; this just asks Qt to notice promptly rather than on the next
        unrelated resize, and re-applies the community list's floor.
        """
        if hasattr(self, "_mix_community_scroll"):
            self._fit_mix_rows()
        if hasattr(self, "_mix_community_box"):
            self._mix_community_box.updateGeometry()
        self._apply_tree_floor()

    def _apply_tree_floor(self):
        """Hold the community list to _TREE_MIN_ROWS of real rows.

        Derived from the live row height rather than a fixed pixel count, the
        same way the collapsed maximum is — before the first layout pass
        sizeHintForRow() returns 0, hence the 19 px fallback the build-time call
        also uses.
        """
        row_h = self.polyculture_tree.sizeHintForRow(0)
        if row_h <= 0:
            row_h = 19
        self.polyculture_tree.setMinimumHeight(row_h * _TREE_MIN_ROWS + 4)

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
            if len(self._mix_communities) >= 2:
                self._mix_community_status.setText(self._mix_status_text())
            if self._armed_mix:
                self._on_pattern_params_changed()   # the armed mix's ratios

    def _on_place_community_mix(self):
        """Arm the community mix.

        We embed the mix in the same ``pattern`` dict the single-community
        flow uses; app.py recognises ``params['community_mix']`` and
        dispatches to per-anchor community expansion. Single places one
        community, so from Single it switches to Row, where it used to open a
        dialog telling you to change the pattern yourself."""
        if len(self._mix_communities) < 2:
            return
        if self.placement_widget.kind == "single":
            self._armed = False              # no re-arm on the way through
            self._rearm_timer.stop()
            self.placement_widget.set_kind("row")
        pattern = self.placement_widget.current_pattern()
        kind = pattern["kind"]
        spacing = float(self.pattern_spacing.value() or 4.0)
        if kind == "fill":
            # Fill an area with the community mix. With Matrix planting ticked the
            # whole mix dissolves into one matrix (every member of every community
            # pooled, ground layer knitting, taller plants scattered); otherwise
            # whole community units are scattered.
            self.fillCommunityMixRequested.emit(
                [
                    {"id": int(c["id"]), "weight": int(c["weight"]),
                     "name": c["name"], "polyculture": c["polyculture"]}
                    for c in self._mix_communities
                ],
                spacing,
                bool((pattern.get("params") or {}).get("matrix")),
            )
            self._arm_as("", mix=True)
            return
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
        self._arm_as("", mix=True)

    def _build_community_pattern_controls(self):
        """The shared placement controls (Single/Row/Grid/Circle/Fill + their
        settings) plus Community spacing, for the placement bar to adopt."""
        from src.placement_controls import PlacementControlsWidget, labelled_unit

        # show_fill_spacing=False: a community/mix is placed as units (or a
        # matrix), never as a scatter of single plants, so the only meaningful
        # spacing is the gap *between* units — the Community spacing control
        # below drives every multi mode (Fill Area + Row/Grid/Circle).
        self.placement_widget = PlacementControlsWidget(
            show_canopy_base=False,
            show_fill_spacing=False,
        )
        self.placement_widget.patternChanged.connect(
            self._on_pattern_params_changed)
        self.placement_widget.patternKindChanged.connect(
            self._on_placement_kind_changed)

        self.pattern_spacing = QDoubleSpinBox()
        self.pattern_spacing.setRange(0.5, 100.0)
        self.pattern_spacing.setDecimals(1)
        self.pattern_spacing.setValue(4.0)
        self.pattern_spacing.setSuffix(" m")
        self.pattern_spacing.setFixedWidth(96)
        self.pattern_spacing.setToolTip(
            "Centre-to-centre spacing between community units — the gap between "
            "whole communities for Fill Area and Row/Grid/Circle alike. "
            "Defaults to 2× the selected community's natural radius "
            "(its widest member offset)."
        )
        # It feeds what is armed, so it announces a change like every other
        # setting (the V2.38 rule). It did not, and the map kept the old gap.
        self.pattern_spacing.valueChanged.connect(self._on_pattern_params_changed)
        # Single places one community where you click — no inter-unit gap.
        self._spacing_box = labelled_unit(
            "Community spacing", self.pattern_spacing, "Community spacing")
        self.placement_widget.add_extra(
            self._spacing_box, ("row", "grid", "circle", "fill"))

    def _on_placement_kind_changed(self, kind: str):
        """Changing Row → Grid is choosing what to place, so re-arm with it.
        Fill Area included since V2.98: choosing it in the bar starts the
        drawing. (Community spacing shows for every pattern but Single: the
        controls widget applies that rule.)"""
        if getattr(self, "_armed", False):
            self._rearm_timer.stop()
            self._rearm()

    def _refresh_polyculture_list(self, _filter_text=None):
        self.polyculture_tree.clear()
        search = (self._search_box.text().strip().lower()
                  if hasattr(self, '_search_box') else "")
        group_by = getattr(self, "_group_by", "none")

        # One batched index for the whole refresh (V2.13) — search, facet
        # filters and sorting are pure-Python passes over it; no per-community
        # queries.
        index = polycultures.get_library_index()
        facet_filters = self._active_facet_filters()
        passed = polycultures.filter_library(
            index, search=search, facets=facet_filters)
        ordered = polycultures.sort_community_ids(
            index, list(passed), getattr(self, "_sort_by", "name"))

        if hasattr(self, "_result_count"):
            n = len(ordered)
            self._result_count.setText(
                f"{n} communit{'y' if n == 1 else 'ies'}")

        filtering = bool(search or facet_filters)
        built = [(cid, self._make_community_item(index, cid, passed[cid],
                                                 filtering))
                 for cid in ordered]

        if group_by == "none":
            for _cid, item in built:
                self.polyculture_tree.addTopLevelItem(item)
            return

        # Grouped: bucket communities under bold, unselectable category nodes.
        # The "function" and "habitat" lenses are multi-valued (a list of
        # labels), so a community can appear under several folders — a community
        # genuinely belongs to every ecoregion its members grow in, and filing it
        # under only the commonest one hid it from the rest (V2.37). Since a
        # QTreeWidgetItem may only have one parent, the 2nd+ folder gets a clone
        # (clone keeps the UserRole community id + nested variations, so
        # selection/placement still work).
        # Buckets sort A–Z; within a bucket the active sort order holds.
        buckets: dict[str, list] = {}
        for cid, item in built:
            val = index[cid]["facets"].get(group_by)
            labels = val if isinstance(val, list) else [val or "Other"]
            if not labels:
                labels = ["Other"]
            for i, label in enumerate(labels):
                node = item if i == 0 else item.clone()
                buckets.setdefault(label, []).append(node)
        for label in sorted(buckets):
            group_node = QTreeWidgetItem([f"{label}  ({len(buckets[label])})"])
            font = group_node.font(0)
            font.setBold(True)
            group_node.setFont(0, font)
            group_node.setForeground(0, QColor("#a5d6a7"))
            # Enabled (so it expands) but NOT selectable or draggable — a pure
            # category folder.
            group_node.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.polyculture_tree.addTopLevelItem(group_node)
            for item in buckets[label]:
                group_node.addChild(item)
            group_node.setExpanded(True)

    def _active_facet_filters(self) -> dict:
        """Facet name → checked labels, for facets with anything checked."""
        combos = getattr(self, "_facet_combos", None) or {}
        out = {}
        for facet, combo in combos.items():
            checked = combo.checked_keys()
            if checked:
                out[facet] = checked
        return out

    @staticmethod
    def _community_tooltip(entry) -> str:
        roles_summary = ", ".join(
            f"{name} ({(role or '').replace('_', ' ')})"
            for name, role in entry["members_brief"][:5])
        if entry["member_count"] > 5:
            roles_summary += f", +{entry['member_count'] - 5} more"
        return (f"{entry['name']}\n{(entry['description'] or '')[:120]}"
                f"\n\nMembers: {roles_summary}")

    def _make_community_item(self, index, cid, passinfo, filtering):
        """Build the tree item for one passing top-level community, its
        variations nested. When the parent only got in because a variation
        matched, just the matching variations are shown (and expanded)."""
        entry = index[cid]
        item = QTreeWidgetItem([entry["name"]])
        item.setData(0, Qt.ItemDataRole.UserRole, cid)
        item.setToolTip(0, self._community_tooltip(entry))

        child_ids = (entry["children"] if (not filtering or passinfo["self"])
                     else passinfo["children"])
        for kid in child_ids:
            child_item = QTreeWidgetItem([index[kid]["name"]])
            child_item.setData(0, Qt.ItemDataRole.UserRole, kid)
            child_item.setToolTip(0, self._community_tooltip(index[kid]))
            item.addChild(child_item)
        if child_ids:
            # Expand when the user has globally enabled variation display, or
            # the active filters hit a variation under this parent.
            item.setExpanded(bool(self._show_variations
                                  or (filtering and passinfo["children"])))
        return item

    # ── Cross-link API (Site tab → library, V2.13) ───────────────────────────

    def set_habitat_filter(self, ecoregion_keys, *, clear_others: bool = True):
        """Pre-set the Habitat facet from ecoregion keys (e.g.
        ``["aspen_parkland"]``) — the Site tab's "browse reference communities
        for this ecoregion" link lands here. Unknown keys are ignored;
        ``clear_others`` resets the other facets first so the user sees the
        ecoregion's communities, not an accidental intersection."""
        labels = [polycultures.ECOREGION_LABELS[k]
                  for k in (ecoregion_keys or [])
                  if k in polycultures.ECOREGION_LABELS]
        if clear_others:
            for combo in self._facet_combos.values():
                combo.set_checked_keys([])
        self._facet_combos["habitat"].set_checked_keys(labels)
        self._refresh_polyculture_list()

    def clear_filters(self):
        """Uncheck every facet filter (search text and grouping untouched)."""
        for combo in self._facet_combos.values():
            combo.set_checked_keys([])
        self._refresh_polyculture_list()

    def _on_sort_changed(self, _idx=0):
        """Re-order the library by the chosen sort key and persist it."""
        self._sort_by = self._sort_combo.currentData() or "name"
        QSettings().setValue("plant_communities/sort_by", self._sort_by)
        self._refresh_polyculture_list()

    def _on_group_by_changed(self, _idx=0):
        """Pivot the library to a new grouping lens and rebuild the tree."""
        self._group_by = self._group_combo.currentData() or "none"
        QSettings().setValue("plant_communities/group_by", self._group_by)
        self._refresh_polyculture_list()

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

    def _build_description_toggle_btn(self) -> QPushButton:
        """The "▾ Hide pattern / ▸ Show pattern" toggle that rides on the right
        of the Members label row. Reads ``self._show_description`` (set just
        before this is called in ``_build_ui``)."""
        btn = QPushButton(
            "▾ Hide pattern" if self._show_description
            else "▸ Show pattern"
        )
        btn.setStyleSheet(
            "QPushButton { background: transparent; color: #90a4ae; "
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "padding: 1px 8px; font-size: 10px; }"
            "QPushButton:hover { color: #c8e6c9; border-color: #4a7a4a; }"
        )
        btn.setToolTip(
            "Show or hide the pattern card (problem / context / forces / "
            "solution) to make more room for the members list above."
        )
        btn.setVisible(False)  # shown once a community is selected
        btn.clicked.connect(self._on_toggle_description)
        return btn

    def _on_toggle_description(self):
        """Flip the show-description preference. Hiding frees room for the
        members list below. No-op with nothing selected (the toggle is hidden
        then, but guard anyway so a stray call can't reveal an empty card)."""
        self._show_description = not self._show_description
        QSettings().setValue(
            "plant_communities/show_description", self._show_description
        )
        self.description_toggle_btn.setText(
            "▾ Hide pattern" if self._show_description
            else "▸ Show pattern"
        )
        if self.polyculture_tree.currentItem() is not None:
            self.detail_text.setVisible(self._show_description)

    def _select_polyculture_in_tree(self, polyculture_id) -> bool:
        """Make the tree row for ``polyculture_id`` current (walks parents +
        children). Returns True if found. Setting it current drives
        ``_on_polyculture_selected`` so the card refreshes."""
        root = self.polyculture_tree.invisibleRootItem()
        for i in range(root.childCount()):
            top = root.child(i)
            if top.data(0, Qt.ItemDataRole.UserRole) == polyculture_id:
                self.polyculture_tree.setCurrentItem(top)
                return True
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, Qt.ItemDataRole.UserRole) == polyculture_id:
                    top.setExpanded(True)
                    self.polyculture_tree.setCurrentItem(child)
                    return True
        return False

    def _on_pattern_link(self, url):
        """Follow a ``community:{id}`` related-pattern link to that community."""
        text = url.toString()
        if not text.startswith("community:"):
            return
        try:
            target = int(text.split(":", 1)[1])
        except (ValueError, IndexError):
            return
        self._select_polyculture_in_tree(target)

    def _community_at(self, index):
        item = self.polyculture_tree.itemFromIndex(index)
        pid = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        return item, pid

    def _on_list_place(self, index):
        """Enter or a double-click on a community: place it, in the pattern the
        bar shows (a double-click placed Single whatever it said until V2.98)."""
        item, pid = self._community_at(index)
        if pid is not None:
            self.polyculture_tree.setCurrentItem(item)
            self._place_community(pid)

    def _on_list_choose(self, index):
        """A finished click or an arrow key onto a community. While this panel
        is placing, the list is a palette: what you choose is placed next."""
        _item, pid = self._community_at(index)
        if self._armed and pid is not None and (
                self._armed_mix or pid != self._armed_community_id):
            self._place_community(pid)

    def _place_community(self, polyculture_id):
        """A Place action named this community: arm the map with it. Its
        natural diameter becomes the spacing as it comes in, and only then, so
        a spacing you set lasts while you place it (until V2.98 a community
        armed with the previous one's)."""
        if polyculture_id is None:
            return
        if self._armed_mix or polyculture_id != self._armed_community_id:
            self._armed_mix = False
            self._armed_community_id = polyculture_id
            try:
                natural_r = polycultures.community_natural_radius(
                    polycultures.get_polyculture_by_id(polyculture_id))
                was = self.pattern_spacing.blockSignals(True)
                self.pattern_spacing.setValue(round(max(0.5, natural_r * 2.0), 1))
                self.pattern_spacing.blockSignals(was)
            except Exception:  # noqa: BLE001 — a spacing is not worth a failed arm
                pass
        self._on_place()

    def _on_polyculture_selected(self, current, previous):
        # A "Group By" category node carries no id — treat it as no selection
        # (it can become the *current* item via keyboard nav even though it
        # isn't selectable).
        current_id = (current.data(0, Qt.ItemDataRole.UserRole)
                      if current is not None else None)
        has_selection = current_id is not None
        self.delete_btn.setEnabled(has_selection)
        self.dup_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)
        self.edit_btn.setEnabled(has_selection)
        # Variations are only addable to top-level communities. A top-level
        # community's tree parent is either nothing (flat view) or a group
        # folder (grouped view, no id) — never another community.
        parent_item = current.parent() if current is not None else None
        parent_is_community = (
            parent_item is not None
            and parent_item.data(0, Qt.ItemDataRole.UserRole) is not None)
        is_top_level = has_selection and not parent_is_community
        self.variation_btn.setEnabled(is_top_level)

        if not has_selection:
            # Let the community list reclaim the whole panel: uncap the tree
            # and hide the (empty) description card so it doesn't hold space.
            self.polyculture_tree.setMaximumHeight(_TREE_EXPANDED_MAX)
            self._community_header_row.setVisible(False)
            self._place_btn.set_subject("")
            self._members_label.setVisible(False)
            self.description_toggle_btn.setVisible(False)
            self.detail_text.clear()
            self.detail_text.setVisible(False)
            self._render_member_rows([])
            return

        # A community is selected: shrink the tree to _TREE_COLLAPSED_ROWS so
        # the members list + description card get the room. Derive the height
        # from the live row height (+4 for the frame) rather than a fixed px so
        # it tracks the actual row metrics.
        row_h = self.polyculture_tree.sizeHintForRow(0)
        if row_h <= 0:
            row_h = 19  # fallback before first layout
        self.polyculture_tree.setMaximumHeight(row_h * _TREE_COLLAPSED_ROWS + 4)
        self._apply_tree_floor()

        polyculture = polycultures.get_polyculture_by_id(current_id)
        if not polyculture:
            return

        members = polyculture.get("members", [])

        # Header: community name + "Anchored on X · N plants", shown directly
        # above the members list.
        center = polyculture.get("center_plant_name") or "—"
        name = polyculture.get("name") or "—"
        self._community_header.setText(
            f"<b style='color:#a5d6a7;'>{name}</b><br>"
            f"<span style='color:#9e9e9e; font-size:11px;'>Anchored on "
            f"{center} · {len(members)} plants</span>"
        )
        self._community_header_row.setVisible(True)
        self._place_btn.set_subject(name if name != "—" else "")
        self._members_label.setVisible(True)
        self.description_toggle_btn.setVisible(True)
        self.detail_text.setVisible(self._show_description)
        self._render_member_rows(members)

        # Description: the Alexander pattern (F4) — authored problem/context/
        # forces/solution plus the live derived facts, with clickable related
        # links. include_header=False since the name/anchored line is shown
        # above in the header label.
        try:
            from src import pattern_language
            pattern = pattern_language.build_pattern(
                polyculture,
                all_communities=polycultures.get_all_polycultures(
                    top_level_only=False),
            )
            self.detail_text.setHtml(
                pattern_language.pattern_card_html(pattern, include_header=False))
        except Exception:  # noqa: BLE001 — never let the card break selection
            self.detail_text.setHtml(polyculture.get("description") or "")
        # That is all selecting does since V2.99: from V2.37 it armed the map,
        # so reading about a community readied the next click to plant it.

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

        # Size the scroll area to show the whole (collapsed) members list up to
        # a ceiling — beyond that it scrolls. A deterministic per-row estimate
        # (~26 px/row + padding); sizeHint() is unreliable here because the
        # container layout isn't activated yet right after insertWidget.
        n = len(members)
        ceiling = 300
        desired = min(ceiling, n * 26 + 6) if n else 0
        self._members_scroll.setMaximumHeight(desired)
        # The floor is BELOW the ceiling, not equal to it. Pinning min == max
        # made this pane perfectly rigid up to 300 px, so on a short window it
        # was another block of space the community list had to surrender. It now
        # yields down to about four rows and scrolls, and the list keeps its own
        # floor (_apply_tree_floor).
        self._members_scroll.setMinimumHeight(min(desired, 4 * 26 + 6))

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
            from src.plant_list_view import labels_csv
            zmin = plant.get("hardiness_zone_min")
            zmax = plant.get("hardiness_zone_max")
            if zmin and zmax:
                zones = f"Z{zmin}–{zmax}"
            elif zmin:
                zones = f"Z{zmin}+"
            else:
                zones = "—"
            sun = labels_csv(plant.get("sun_requirement"), _SUN_LABELS)
            water = labels_csv(plant.get("water_needs"), _WATER_LABELS)
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

    def _on_creature_community(self):
        """Generate a plant community tailored to a chosen native pollinator
        (bee, butterfly or moth) and add it to the library (V2.12)."""
        creature = _CreaturePickerDialog.pick(self)
        if creature is None:
            return
        try:
            from src.creature_community import build_creature_community
            community = build_creature_community(creature["fid"])
        except Exception as e:      # noqa: BLE001
            QMessageBox.critical(self, "Error",
                                 f"Could not build the community:\n{e}")
            return
        if not community or not community["members"]:
            QMessageBox.information(
                self, "Nothing to plant yet",
                f"The plant database doesn't yet record plants that support "
                f"the {creature['name']}, so there's no community to build.")
            return
        try:
            new_id = polycultures.create_polyculture(
                community["name"], community["description"], None)
            polycultures.replace_polyculture_members(new_id, community["members"])
        except Exception as e:      # noqa: BLE001
            QMessageBox.critical(self, "Error",
                                 f"Could not save the community:\n{e}")
            return
        self._refresh_polyculture_list()
        self._select_polyculture_in_tree(new_id)

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
    # via the "Edit in Builder…" button. The one-at-a-time AddMemberDialog,
    # kept "in case external code or tests still import it", had no caller
    # and was a fourth plant picker; it went with V3.00's one picker (F192).

    # ── Arming ────────────────────────────────────────────────────────────────

    def _on_pattern_params_changed(self):
        from src.placement_arming import request_rearm
        request_rearm(self)

    def _rearm(self):
        """A setting moved: re-arm whatever is armed, the mix or the
        community. Choosing Single sets the mix aside (it cannot be placed
        one community at a time) for the selected community; with none, the
        map stands down rather than keep what the bar no longer shows.
        Nothing, if the map stood down meanwhile (the debounce lands here)."""
        if not self._armed:
            return
        if self._armed_mix and self.placement_widget.kind != "single":
            self._on_place_community_mix()
        elif self._armed_mix:
            selected = self._get_selected_polyculture_id()
            if selected is None:
                self.placementCancelled.emit()
            else:
                self._place_community(selected)
        elif self._armed_community_id is not None:
            self._on_place()
        else:
            self.placementCancelled.emit()

    def set_armed(self, armed: bool):
        """Told by MainWindow when placement mode ends (Esc, another tool)."""
        if not armed:
            self._rearm_timer.stop()
        if getattr(self, "_armed", False) == bool(armed):
            return
        self._armed = bool(armed)
        if not armed:
            self._armed_mix = False
        self._announce_armed()

    def _arm_as(self, what: str, *, mix: bool = False):
        self._armed_what = what or ""
        self._armed_mix = bool(mix)
        self._armed = True
        self._announce_armed()

    def _announce_armed(self):
        """Tell the placement bar what the map holds (or that it holds nothing)."""
        self.armedChanged.emit({
            "armed": self._armed,
            "what": self._armed_what,
            "kind": self.placement_widget.kind,
            "qty": 1,
            "mix": len(self._mix_communities) if self._armed_mix else 0,
        })

    def placement_controls(self):
        """The pattern controls, for the placement bar to adopt (V2.98)."""
        return self.placement_widget

    def _on_place(self):
        """Arm the map with the community a Place action named, in the bar's
        pattern. See :meth:`_place_community` for how one comes in."""
        polyculture_id = self._armed_community_id
        if polyculture_id is None:
            return
        polyculture = polycultures.get_polyculture_by_id(polyculture_id)
        if not polyculture:
            return
        name = polyculture.get("name") or ""

        # Attach the pattern config so app.py knows whether to single-place
        # the community or to fan it across a row/grid/circle.
        pattern = self.placement_widget.current_pattern()
        kind = pattern["kind"]
        if kind == "fill":
            # Draw-an-area fill: whole community units scattered inside the
            # polygon (app enters fill-draw mode on this signal). With Matrix
            # planting ticked, the community dissolves into a groundcover matrix
            # with taller members scattered through it (F22).
            self.fillAreaRequested.emit(
                int(polyculture_id),
                float(self.pattern_spacing.value() or 4.0),
                bool((pattern.get("params") or {}).get("matrix")))
            self._arm_as(name)
            return
        if kind != "single":
            spacing = float(self.pattern_spacing.value() or 4.0)
            polyculture = dict(polyculture)
            polyculture["pattern"] = {
                "kind": kind,
                "spacing_m": spacing,
                "params": pattern.get("params") or {},
            }
        self.placePolycultureRequested.emit(polyculture)
        self._arm_as(name)

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

# What the map is armed with is said by the placement bar over the map
# (src/placement_bar.py), in words from src/placement_arming.py — shared with the
# plant browser, which arms the same map.

# Compact, low-prominence style for the library management buttons (New /
# Delete / Duplicate / Variation / Edit / Export / Import) — mirrors the
# placement-mode segmented buttons (placement_controls._PATTERN_SEG_STYLE) so
# they read as secondary controls, not primary CTAs. The prominent green
# _POLY_BTN_STYLE stays on the "Place on Map" / "Place Mix on Map" actions.
_POLY_MGMT_BTN_STYLE = """
QPushButton {
    background: #1e2e1e;
    color: #c8e6c9;
    border: 1px solid #2e4a2e;
    border-radius: 3px;
    padding: 4px 6px;
    font-size: 11px;
}
QPushButton:hover    { border-color: #4a7a4a; background: #243824; }
QPushButton:pressed  { background: #2e5a2e; }
QPushButton:disabled { color: #4a6a4a; border-color: #243824; }
"""
