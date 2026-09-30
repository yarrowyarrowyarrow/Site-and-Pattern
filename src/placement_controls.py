"""Shared placement-controls strip used by the Plants tab and the Plant
Communities tab. Owns the Single/Row/Grid/Circle/Fill selector, the settings of
each pattern (count, rows × columns + stagger, circle total + fill, fill spacing
+ matrix), overlap, and the canopy-base toggle.

Since V2.98 it lives in the placement bar over the map (``src/placement_bar.py``)
rather than in a collapsible section of the side panel, and it is laid out as one
wrapping line (``src/flow_layout.py``) instead of a stack of rows. **Only the
current pattern's settings are shown**: Overlap and the canopy toggle were on
screen in Single and Fill too, where ``current_pattern()`` never reads them, and
a number that does nothing is a number somebody sets and then distrusts.

Tabs embed an instance, call ``current_pattern()`` for the pattern dict, and
inject their own tab-specific keys (``polyculture`` for the Plants-tab mix,
``community_mix`` for the Communities-tab mix) into ``params``. Controls a tab
owns (the Plants tab's Qty, the Communities tab's spacing) join the same line
through :meth:`add_extra`, so they wrap with the rest.

Unstyled on purpose: the bar's style sheet styles everything inside it, the
tab-owned extras included, so the two tabs cannot drift apart in look.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from src.flow_layout import FlowLayout


# Still used by the two panels' mix rows, which stay in the side panel.
_QTY_SPIN_STYLE = """
QSpinBox {
    background: #1a2a1a;
    color: #c8e6c9;
    border: 1px solid #2e4a2e;
    border-radius: 3px;
    padding: 2px 4px;
    font-size: 13px;
}
QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #2e4a2e;
    background: #243824;
}
QSpinBox::up-button:hover { background: #2e5a2e; }
QSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #a5d6a7;
    width: 0; height: 0;
}
QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #2e4a2e;
    background: #243824;
}
QSpinBox::down-button:hover { background: #2e5a2e; }
QSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a5d6a7;
    width: 0; height: 0;
}
"""

# The patterns, in button order: (key, label, tooltip).
PATTERNS = (
    ("single", "Single", "One click, one placement"),
    ("row", "Row", "Click the start, then the end: fills a line"),
    ("grid", "Grid", "Click two opposite corners: fills a rectangle"),
    ("circle", "Circle", "Click the centre, then the edge: a ring or a disc"),
    ("fill", "Fill area", "Draw an area on the map: fills it evenly"),
)

# Which settings each pattern reads. Overlap and the canopy toggle feed the
# spacing of the multi-cell patterns only.
_SPACED = ("row", "grid", "circle")


def _unit(*widgets) -> QWidget:
    """Group a label and its control so they wrap as one item."""
    unit = QWidget()
    row = QHBoxLayout(unit)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    for w in widgets:
        row.addWidget(w)
    return unit


def labelled_unit(text: str, control: QWidget, name: str) -> QWidget:
    """``text`` beside ``control``, with ``name`` as the control's accessible
    name ("Row count", not the bare "Count" a screen reader would otherwise
    read with no context)."""
    label = QLabel(text)
    label.setBuddy(control)
    control.setAccessibleName(name)
    return _unit(label, control)


class PlacementControlsWidget(QWidget):
    """Single/Row/Grid/Circle/Fill pattern controls. Self-contained; emits
    ``patternKindChanged`` so embedders can react (e.g. show a quantity that
    only Single uses)."""

    patternKindChanged = pyqtSignal(str)
    # Any change to WHAT would be placed — the kind, or any of its parameters.
    #
    # Until V2.38 only the kind was announced, which was harmless while the user
    # pressed "Place on Map" after setting things up: current_pattern() was read
    # fresh at that moment. Once selecting a plant started arming the map
    # (V2.37), the pattern was read at SELECTION time instead, so a Count set
    # afterwards never reached the map — you asked for 11 in a row and got the
    # 3 that "auto" derived from the spacing. Every control that feeds
    # current_pattern() emits this now, so "what is armed" cannot drift from
    # "what is on screen".
    patternChanged = pyqtSignal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        show_canopy_base: bool = True,
        show_fill_spacing: bool = True,
    ):
        super().__init__(parent)
        self._kind = "single"
        self._show_canopy_base = show_canopy_base
        self._extras: list[tuple[QWidget, tuple | None]] = []
        self.setAccessibleName("Placement pattern")

        self._flow = FlowLayout(self, h_spacing=12, v_spacing=6)
        self._flow.setContentsMargins(0, 0, 0, 0)

        # ── The pattern selector ──────────────────────────────────────────
        seg_unit = QWidget()
        seg = QHBoxLayout(seg_unit)
        seg.setContentsMargins(0, 0, 0, 0)
        seg.setSpacing(2)
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        for key, label, tip in PATTERNS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setProperty("pattern_kind", key)
            btn.setProperty("segment", True)
            self._btn_group.addButton(btn)
            seg.addWidget(btn)
            if key == "single":
                btn.setChecked(True)
        self._btn_group.buttonClicked.connect(self._on_kind_changed)
        self._flow.addWidget(seg_unit)

        # ── Row: count + drift ────────────────────────────────────────────
        self._row_count = QSpinBox()
        self._row_count.setRange(0, 200)
        self._row_count.setValue(0)
        self._row_count.setSpecialValueText("auto")
        self._row_count.setFixedWidth(76)
        self._row_count.setToolTip(
            "How many along the line. Auto works it out from the spacing.")
        self._row_drift = QCheckBox("Drift")
        self._row_drift.setToolTip(
            "Lay the group out as a flowing, organic drift along the line you "
            "draw (Rainer/West 'designed communities' style) rather than an even "
            "straight row — the most natural look for grasses and forbs."
        )
        row_unit = _unit(labelled_unit("Count", self._row_count, "Row count"),
                         self._row_drift)

        # ── Grid: rows × columns + stagger ────────────────────────────────
        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(0, 200)
        self._grid_rows.setSpecialValueText("auto")
        self._grid_rows.setFixedWidth(72)
        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(0, 200)
        self._grid_cols.setSpecialValueText("auto")
        self._grid_cols.setFixedWidth(72)
        self._grid_stagger = QCheckBox("Stagger")
        self._grid_stagger.setToolTip(
            "Hex-pack: offset every other row by half a column")
        grid_unit = _unit(labelled_unit("Rows", self._grid_rows, "Grid rows"),
                          labelled_unit("Columns", self._grid_cols, "Grid columns"),
                          self._grid_stagger)

        # ── Circle: total + fill ──────────────────────────────────────────
        self._circle_count = QSpinBox()
        self._circle_count.setRange(0, 2000)
        self._circle_count.setSpecialValueText("auto")
        self._circle_count.setFixedWidth(80)
        self._circle_count.setToolTip(
            "Total items in the placement.\n"
            "Auto = derive from spacing — perimeter mode uses arc length, "
            "fill mode packs the whole disc.\n"
            "Otherwise: that many items on the perimeter (no fill) or in the "
            "hex-pack disc (fill), closest-to-centre first."
        )
        self._circle_fill = QCheckBox("Fill (hex)")
        self._circle_fill.setToolTip(
            "Honeycomb-pack the whole disc so every item has six "
            "equidistant neighbours. Use Total to cap the count for large "
            "radii."
        )
        circle_unit = _unit(labelled_unit("Total", self._circle_count, "Circle total"),
                            self._circle_fill)

        # ── Fill area: spacing + matrix planting ──────────────────────────
        # The Communities tab supplies its own spacing (the gap between whole
        # communities), so it hides this one with show_fill_spacing=False.
        self._fill_spacing = QDoubleSpinBox()
        self._fill_spacing.setRange(0.3, 20.0)
        self._fill_spacing.setSingleStep(0.1)
        self._fill_spacing.setDecimals(1)
        self._fill_spacing.setValue(1.5)
        self._fill_spacing.setSuffix(" m")
        self._fill_spacing.setFixedWidth(90)
        self._fill_spacing.setToolTip(
            "Centre-to-centre spacing of the scattered plants. Starts at the "
            "plant's own spacing (a mix: the widest of its plants)."
        )
        self._fill_spacing_unit = labelled_unit("Spacing", self._fill_spacing,
                                            "Fill spacing")
        self._fill_spacing_unit.setVisible(show_fill_spacing)
        self._fill_matrix = QCheckBox("Matrix planting")
        self._fill_matrix.setToolTip(
            "Rainer/West matrix planting: the ground-layer species (grasses / "
            "groundcovers) fill the area as a connective matrix while the taller "
            "feature plants are scattered through it. For a community, its "
            "groundcover-layer members are the matrix; for a plant mix the "
            "ground-layer species are picked automatically."
        )
        fill_unit = _unit(self._fill_spacing_unit, self._fill_matrix)

        self._units = {"row": row_unit, "grid": grid_unit,
                       "circle": circle_unit, "fill": fill_unit}
        for unit in self._units.values():
            self._flow.addWidget(unit)

        # ── Overlap + canopy base (row / grid / circle only) ──────────────
        # A spin box, not the slider it was until V2.98: the slider's value was
        # only readable from a separate label, and the accessibility tree
        # announced it as "Placement Mode".
        self._overlap = QSpinBox()
        self._overlap.setRange(-100, 50)
        self._overlap.setSingleStep(5)
        self._overlap.setValue(0)
        self._overlap.setSuffix(" %")
        self._overlap.setFixedWidth(86)
        self._overlap.setToolTip(
            "Spacing relative to the reference width (see Canopy width).\n"
            "  −100% = double spacing (centres 2× reference apart)\n"
            "     0% = at nominal spacing\n"
            "   +50% = half spacing (dense overlap)\n"
            "Effective spacing = reference × (1 − overlap)."
        )
        self._overlap_unit = labelled_unit("Overlap", self._overlap, "Overlap")
        self._flow.addWidget(self._overlap_unit)

        # Reference width: planting spacing (default) vs mature canopy.
        # The Communities tab hides this — a community isn't a single canopy.
        self._canopy_base_checkbox = QCheckBox("Canopy width")
        self._canopy_base_checkbox.setToolTip(
            "Off: overlap is measured against the planting spacing.\n"
            "On: overlap is measured against the mature canopy width — "
            "useful when you care about leaf-area competition more than "
            "nursery spacing recommendations."
        )
        self._flow.addWidget(self._canopy_base_checkbox)

        self._apply_visibility()

        # Announce every parameter current_pattern() reads. Gathered in one list
        # at the end rather than wired at each construction site, so a control
        # added later is visibly absent from it — the failure mode is silent
        # otherwise, and it is the map quietly placing the previous thing.
        for _control in (self._row_count, self._grid_rows, self._grid_cols,
                         self._circle_count, self._fill_spacing,
                         self._overlap):
            _control.valueChanged.connect(self._emit_pattern_changed)
        for _control in (self._row_drift, self._grid_stagger, self._circle_fill,
                         self._fill_matrix, self._canopy_base_checkbox):
            _control.toggled.connect(self._emit_pattern_changed)

    def _emit_pattern_changed(self, *_args):
        self.patternChanged.emit()

    # ── Public API ────────────────────────────────────────────────────

    @property
    def kind(self) -> str:
        return self._kind

    def set_kind(self, kind: str) -> None:
        for btn in self._btn_group.buttons():
            if btn.property("pattern_kind") == kind:
                btn.setChecked(True)
                self._on_kind_changed(btn)
                return

    def add_extra(self, widget: QWidget, kinds=None) -> None:
        """Put a tab-owned control on the same wrapping line, shown only for
        the patterns in ``kinds`` (every pattern when ``None``)."""
        self._extras.append((widget, tuple(kinds) if kinds else None))
        self._flow.addWidget(widget)
        self._apply_visibility()

    def current_pattern(self) -> dict:
        """Build the pattern dict ``{kind, params}``. Tab-specific keys
        like ``polyculture`` or ``community_mix`` are the caller's job
        to inject into ``params`` after the fact."""
        kind = self._kind
        overlap = self._overlap.value() / 100.0
        use_canopy = self._canopy_base_checkbox.isChecked()
        if kind == "row":
            params = {
                "count": self._row_count.value() or None,
                "overlap": overlap,
                "use_canopy": use_canopy,
                "drift": self._row_drift.isChecked(),
            }
        elif kind == "grid":
            params = {
                "rows": self._grid_rows.value() or None,
                "cols": self._grid_cols.value() or None,
                "stagger": self._grid_stagger.isChecked(),
                "overlap": overlap,
                "use_canopy": use_canopy,
            }
        elif kind == "circle":
            params = {
                "count": self._circle_count.value() or None,
                "fill": self._circle_fill.isChecked(),
                "overlap": overlap,
                "use_canopy": use_canopy,
            }
        elif kind == "fill":
            params = {
                "spacing": float(self._fill_spacing.value()),
                "matrix": self._fill_matrix.isChecked(),
            }
        else:
            return {"kind": "single", "params": {}}
        return {"kind": kind, "params": params}

    def fill_spacing(self) -> float:
        """Convenience accessor for the Fill Area spacing (metres)."""
        return float(self._fill_spacing.value())

    def set_fill_spacing(self, metres) -> None:
        """Start the fill at the plants' own spacing (V2.98). It had defaulted
        to 1.5 m whatever was being planted, while the mix line above it said
        "~0.3 m spacing": a forb fill came out about 25 times sparser than the
        plants' own guidance. Clamped to the spin box's range.

        Silent: a default is not the user changing the pattern, and the caller
        arms straight after, so announcing it would only queue a second re-arm.
        """
        try:
            value = float(metres)
        except (TypeError, ValueError):
            return
        if value > 0:
            was = self._fill_spacing.blockSignals(True)
            self._fill_spacing.setValue(value)
            self._fill_spacing.blockSignals(was)

    # ── Internals ─────────────────────────────────────────────────────

    def _apply_visibility(self) -> None:
        kind = self._kind
        for key, unit in self._units.items():
            unit.setVisible(key == kind)
        self._overlap_unit.setVisible(kind in _SPACED)
        self._canopy_base_checkbox.setVisible(
            self._show_canopy_base and kind in _SPACED)
        for widget, kinds in self._extras:
            widget.setVisible(kinds is None or kind in kinds)

    def _on_kind_changed(self, btn):
        self._kind = btn.property("pattern_kind") or "single"
        self._apply_visibility()
        self.patternKindChanged.emit(self._kind)
