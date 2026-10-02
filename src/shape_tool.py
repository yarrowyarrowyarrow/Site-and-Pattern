"""
shape_tool.py — Draw › Shape: beds, paths, lawn-conversion zones and the lines
a hedge, fence or windbreak makes, on the Draw row (V3.07).

Until V3.07 these were two pages of the Structures tab, Shapes and Hedgerow, one
tab away from the Draw row's Boundary, which draws the same way. The owner's
answers to the V3.05 surface audit moved Shapes to the Draw row and merged
Hedgerow into it: a hedge is one more thing to draw, and its four kinds join
the list of types. The form shows what the chosen type needs, an area's fill,
outline and shade height or a line's width, spacing and species, and Draw on
the map hands it to the map (``place_shape_requested`` or
``place_hedgerow_requested``, the signals the Structures tab emitted, to the
same handlers).

``ShapeTool`` is the form; ``shape_button`` puts it under a Draw-row button.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPushButton, QToolButton, QVBoxLayout, QWidget,
    QWidgetAction,
)

#: The area presets: fill, outline, opacity and line pattern.
AREA_PRESETS = {
    "Garden Bed":     {"fill": "#4caf50", "stroke": "#2e7d32", "opacity": 0.25, "pattern": "Solid"},
    "Pathway":        {"fill": "#8d6e63", "stroke": "#5d4037", "opacity": 0.35, "pattern": "Dashed"},
    "Patio / Deck":   {"fill": "#78909c", "stroke": "#546e7a", "opacity": 0.40, "pattern": "Solid"},
    "Lawn Area":      {"fill": "#66bb6a", "stroke": "#43a047", "opacity": 0.15, "pattern": "Dotted"},
    "Mulch Area":     {"fill": "#795548", "stroke": "#5d4037", "opacity": 0.30, "pattern": "Solid"},
    "Water Feature":  {"fill": "#42a5f5", "stroke": "#1565c0", "opacity": 0.30, "pattern": "Solid"},
    "Custom":         {"fill": "#9e9e9e", "stroke": "#616161", "opacity": 0.25, "pattern": "Solid"},
}

#: The lines: what the list says, and the style the map draws.
LINE_KINDS = (
    ("Hedge", "hedge"),
    ("Fence", "fence"),
    ("Living fence", "living_fence"),
    ("Windbreak", "windbreak"),
)

_PATTERNS = ("Solid", "Dashed", "Dotted")
_DASH = {"Solid": "", "Dashed": "8 4", "Dotted": "2 4"}


def _swatch_style(colour: str) -> str:
    return f"background: {colour}; border: 1px solid #4a7a4a; border-radius: 4px;"


class ShapeTool(QWidget):
    """The Shape form: a type, then what that type needs, then Draw."""

    place_shape_requested = pyqtSignal(dict)      # an area
    place_hedgerow_requested = pyqtSignal(dict)   # a line
    drawing = pyqtSignal()                         # Draw was pressed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fill, self._stroke = "#4caf50", "#2e7d32"
        self._line_colour = "#4caf50"
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        head = QFormLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self._type = QComboBox()
        self._type.setAccessibleName("What to draw")
        for name in AREA_PRESETS:
            self._type.addItem(name, ("area", name))
        # The lawn-to-habitat conversion zones (N2), whose labels and colours
        # come from src.lawn_zones so the drawer and the tally never drift.
        from src.lawn_zones import ZONE_TYPES
        self._type.insertSeparator(self._type.count())
        for spec in ZONE_TYPES.values():
            self._type.addItem(spec["label"], ("zone", spec["label"]))
        self._type.insertSeparator(self._type.count())
        for words, style in LINE_KINDS:
            self._type.addItem(words, ("line", style))
        self._type.currentIndexChanged.connect(self._on_type_changed)
        head.addRow("Type:", self._type)
        root.addLayout(head)

        self._area = self._build_area()
        self._line = self._build_line()
        root.addWidget(self._area)
        root.addWidget(self._line)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #90a4ae; font-size: 12px;")
        root.addWidget(self._hint)

        self._draw = QPushButton("Draw on the map")
        self._draw.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; border: 1px solid #43a047; "
            "border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #388e3c; }")
        self._draw.clicked.connect(self._on_draw)
        root.addWidget(self._draw)
        self.setFixedWidth(300)
        self._on_type_changed()

    # ── The two forms ─────────────────────────────────────────────────────────

    def _build_area(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        self._label = QLineEdit()
        self._label.setPlaceholderText("e.g. Front garden bed")
        form.addRow("Label:", self._label)

        self._fill_btn = self._swatch("Fill colour", self._pick_fill)
        self._stroke_btn = self._swatch("Outline colour", self._pick_stroke)
        colours = QHBoxLayout()
        colours.addWidget(self._fill_btn)
        colours.addWidget(QLabel("Outline:"))
        colours.addWidget(self._stroke_btn)
        colours.addStretch()
        form.addRow("Fill:", colours)

        self._opacity = QDoubleSpinBox()
        self._opacity.setRange(0.0, 1.0)
        self._opacity.setSingleStep(0.05)
        form.addRow("Opacity:", self._opacity)

        self._pattern = QComboBox()
        self._pattern.addItems(_PATTERNS)
        form.addRow("Line style:", self._pattern)

        # Shade height: above 0 the drawn outline casts shade, as a tree's
        # canopy or a building's footprint, instead of being a flat area.
        self._height = QDoubleSpinBox()
        self._height.setRange(0.0, 60.0)
        self._height.setSingleStep(0.5)
        self._height.setSuffix(" m")
        self._height.setToolTip(
            "0 is a flat area. A height makes the outline cast shade, as a "
            "building (about 8 m) or a mature tree's canopy (about 6 m) does.")
        form.addRow("Casts shade, height:", self._height)
        return box

    def _build_line(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        self._width = QDoubleSpinBox()
        self._width.setRange(0.5, 5.0)
        self._width.setSingleStep(0.5)
        self._width.setValue(1.5)
        self._width.setSuffix(" m")
        form.addRow("Width:", self._width)

        self._spacing = QDoubleSpinBox()
        self._spacing.setRange(0.3, 5.0)
        self._spacing.setSingleStep(0.1)
        self._spacing.setValue(1.0)
        self._spacing.setSuffix(" m")
        form.addRow("Plant spacing:", self._spacing)

        self._species = QLineEdit()
        self._species.setPlaceholderText("e.g. Caragana, Lilac, Dogwood")
        form.addRow("Species (optional):", self._species)

        self._line_btn = self._swatch("Line colour", self._pick_line_colour)
        self._line_btn.setStyleSheet(_swatch_style(self._line_colour))
        row = QHBoxLayout()
        row.addWidget(self._line_btn)
        row.addStretch()
        form.addRow("Colour:", row)
        return box

    def _swatch(self, name: str, on_click) -> QPushButton:
        btn = QPushButton()
        btn.setAccessibleName(name)
        btn.setFixedSize(28, 28)
        btn.clicked.connect(on_click)
        return btn

    # ── State ─────────────────────────────────────────────────────────────────

    def kind(self) -> tuple:
        """``("area" | "zone" | "line", name or style)`` for the chosen type."""
        return self._type.currentData() or ("area", "Custom")

    def set_type(self, words: str) -> bool:
        """Choose a type by what the list says. Returns whether it is listed."""
        i = self._type.findText(words)
        if i >= 0:
            self._type.setCurrentIndex(i)
        return i >= 0

    def _on_type_changed(self, *_):
        what, name = self.kind()
        line = what == "line"
        self._area.setVisible(not line)
        self._line.setVisible(line)
        if line:
            self._hint.setText("Click along the line; double-click to finish.")
            self.adjustSize()
            return
        self._hint.setText("Click its corners; double-click or click the "
                           "first corner to close.")
        preset = AREA_PRESETS.get(name)
        if preset is None:
            from src.lawn_zones import ZONE_TYPES
            spec = next((s for s in ZONE_TYPES.values() if s["label"] == name),
                        None)
            preset = ({"fill": spec["fill"], "stroke": spec["stroke"],
                       "opacity": spec["opacity"], "pattern": "Solid"}
                      if spec else AREA_PRESETS["Custom"])
        self._fill, self._stroke = preset["fill"], preset["stroke"]
        self._fill_btn.setStyleSheet(_swatch_style(self._fill))
        self._stroke_btn.setStyleSheet(_swatch_style(self._stroke))
        self._opacity.setValue(preset["opacity"])
        self._pattern.setCurrentIndex(_PATTERNS.index(preset["pattern"]))
        if name != "Custom":
            self._label.setPlaceholderText(f"e.g. {name}")
        self.adjustSize()

    def _pick(self, current: str, title: str) -> str | None:
        """A colour, from the system's dialog. The dialog closes the menu this
        form sits in (it is a popup), so the menu is opened again where it was,
        with Draw one click away."""
        menu = self.parentWidget()
        where = menu.pos() if isinstance(menu, QMenu) else None
        colour = QColorDialog.getColor(QColor(current), self, title)
        if where is not None and not menu.isVisible():
            menu.popup(where)
        return colour.name() if colour.isValid() else None

    def _pick_fill(self):
        if (c := self._pick(self._fill, "Fill colour")) is not None:
            self._fill = c
            self._fill_btn.setStyleSheet(_swatch_style(c))

    def _pick_stroke(self):
        if (c := self._pick(self._stroke, "Outline colour")) is not None:
            self._stroke = c
            self._stroke_btn.setStyleSheet(_swatch_style(c))

    def _pick_line_colour(self):
        if (c := self._pick(self._line_colour, "Line colour")) is not None:
            self._line_colour = c
            self._line_btn.setStyleSheet(_swatch_style(c))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def area_payload(self) -> dict:
        return {
            "shape_type": self._type.currentText(),
            "label": self._label.text().strip(),
            "fill_color": self._fill,
            "stroke_color": self._stroke,
            "fill_opacity": self._opacity.value(),
            "dash_array": _DASH.get(self._pattern.currentText(), ""),
            # >0 → the drawn footprint casts shade (canopy / building perimeter).
            "height_m": self._height.value(),
        }

    def line_payload(self) -> dict:
        return {
            "style": self.kind()[1],
            "width_m": self._width.value(),
            "spacing_m": self._spacing.value(),
            "species": self._species.text().strip(),
            "color": self._line_colour,
        }

    def _on_draw(self):
        self.drawing.emit()
        if self.kind()[0] == "line":
            self.place_hedgerow_requested.emit(self.line_payload())
        else:
            self.place_shape_requested.emit(self.area_payload())


def shape_button(parent) -> tuple[QToolButton, ShapeTool]:
    """A Draw-row button whose menu is the Shape form; the menu closes when
    Draw is pressed, so the next click lands on the map."""
    button = QToolButton(parent)
    button.setText("▱ Shape")
    button.setCheckable(True)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    button.setStatusTip("Draw a bed, a path, a lawn-conversion zone, or a "
                        "hedge, fence or windbreak")
    button.setToolTip("Draw a shape on the map: a bed, a path, a "
                      "lawn-conversion zone,\nor a line: a hedge, fence, "
                      "living fence or windbreak.")
    menu = QMenu(button)
    tool = ShapeTool(menu)
    action = QWidgetAction(menu)
    action.setDefaultWidget(tool)
    menu.addAction(action)
    tool.drawing.connect(menu.close)
    menu.aboutToShow.connect(tool.adjustSize)
    button.setMenu(menu)
    return button, tool
