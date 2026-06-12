"""Shared placement-controls widget used by the Plants tab and the Plant
Communities tab. Owns the Single/Row/Grid/Circle mode selector, the per-mode
parameter panels (count, rows×cols + stagger, circle total + fill), the
overlap slider, and the canopy-base toggle.

Tabs embed an instance, call ``current_pattern()`` for the pattern dict,
and inject their own tab-specific keys (``polyculture`` for the Plants-tab
stack, ``community_mix`` for the Communities-tab mix) into ``params``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


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

_PATTERN_SEG_STYLE = """
QPushButton {
    background: #1e2e1e;
    color: #c8e6c9;
    border: 1px solid #2e4a2e;
    border-radius: 3px;
    padding: 4px 6px;
    font-size: 11px;
}
QPushButton:checked {
    background: #2e7d32;
    color: #e8f5e9;
    border-color: #66bb6a;
    font-weight: bold;
}
QPushButton:hover:!checked {
    border-color: #4a7a4a;
    background: #243824;
}
"""


def _small_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #90a4ae; font-size: 11px;")
    return lbl


class PlacementControlsWidget(QWidget):
    """Single/Row/Grid/Circle pattern controls — count, stagger, fill,
    overlap slider, canopy-base toggle. Self-contained; emits
    ``patternKindChanged`` so embedders can react (e.g. enable/disable
    a burst-quantity spinner that lives outside this widget)."""

    patternKindChanged = pyqtSignal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        show_canopy_base: bool = True,
        title: str = "Placement Mode",
    ):
        super().__init__(parent)
        self._kind = "single"

        wrap = QGroupBox(title)
        wrap.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(wrap)

        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # ── Mode segmented buttons ────────────────────────────────────
        seg = QHBoxLayout()
        seg.setSpacing(2)
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        for key, label, tip in [
            ("single", "Single", "Click to place one item at a time"),
            ("row",    "Row",    "Click start, then end — fills a line"),
            ("grid",   "Grid",   "Click two opposite corners — fills a rectangle"),
            ("circle", "Circle", "Click centre, then radius — places items on a circle"),
            ("fill",   "Fill Area", "Draw an area on the map — fills it evenly at the spacing below"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setStyleSheet(_PATTERN_SEG_STYLE)
            btn.setProperty("pattern_kind", key)
            self._btn_group.addButton(btn)
            seg.addWidget(btn)
            if key == "single":
                btn.setChecked(True)
        self._btn_group.buttonClicked.connect(self._on_kind_changed)
        outer.addLayout(seg)

        # ── Stacked per-mode parameter panels ──────────────────────────
        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        # Single — no parameters (parent panel may provide a burst Qty spinner).
        single_panel = QWidget()
        sl = QVBoxLayout(single_panel)
        sl.setContentsMargins(0, 0, 0, 0)
        single_hint = QLabel("Click on the map to place one at a time.")
        single_hint.setStyleSheet("color: #78909c; font-size: 11px;")
        sl.addWidget(single_hint)
        self._stack.addWidget(single_panel)

        # Row — count input.
        row_panel = QWidget()
        rl = QHBoxLayout(row_panel)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        rl.addWidget(_small_label("Count:"))
        self._row_count = QSpinBox()
        self._row_count.setRange(0, 200)
        self._row_count.setValue(0)
        self._row_count.setSpecialValueText("auto")
        self._row_count.setToolTip("0 = auto from spacing; otherwise force this many items")
        self._row_count.setStyleSheet(_QTY_SPIN_STYLE)
        self._row_count.setFixedWidth(80)
        rl.addWidget(self._row_count)
        rl.addStretch()
        self._stack.addWidget(row_panel)

        # Grid — rows × cols + stagger.
        grid_panel = QWidget()
        gl = QHBoxLayout(grid_panel)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(4)
        gl.addWidget(_small_label("Rows:"))
        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(0, 200)
        self._grid_rows.setSpecialValueText("auto")
        self._grid_rows.setStyleSheet(_QTY_SPIN_STYLE)
        self._grid_rows.setFixedWidth(70)
        gl.addWidget(self._grid_rows)
        gl.addWidget(_small_label("Columns:"))
        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(0, 200)
        self._grid_cols.setSpecialValueText("auto")
        self._grid_cols.setStyleSheet(_QTY_SPIN_STYLE)
        self._grid_cols.setFixedWidth(70)
        gl.addWidget(self._grid_cols)
        self._grid_stagger = QCheckBox("Stagger")
        self._grid_stagger.setToolTip("Hex-pack: offset every other row by half a column")
        gl.addWidget(self._grid_stagger)
        gl.addStretch()
        self._stack.addWidget(grid_panel)

        # Circle — total + fill.
        circle_panel = QWidget()
        cl = QHBoxLayout(circle_panel)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        cl.addWidget(_small_label("Total:"))
        self._circle_count = QSpinBox()
        self._circle_count.setRange(0, 2000)
        self._circle_count.setSpecialValueText("auto")
        self._circle_count.setToolTip(
            "Total items in the placement.\n"
            "0 (auto) = derive from spacing — perimeter mode uses arc length, "
            "fill mode packs the whole disc.\n"
            "Otherwise: that many items on the perimeter (no fill) or in the "
            "hex-pack disc (fill), closest-to-centre first."
        )
        self._circle_count.setStyleSheet(_QTY_SPIN_STYLE)
        self._circle_count.setFixedWidth(80)
        cl.addWidget(self._circle_count)
        self._circle_fill = QCheckBox("Fill (hex)")
        self._circle_fill.setToolTip(
            "Honeycomb-pack the whole disc so every item has six "
            "equidistant neighbours. Use the Total spinner to cap the "
            "count for large radii."
        )
        cl.addWidget(self._circle_fill)
        cl.addStretch()
        self._stack.addWidget(circle_panel)

        # Fill Area — spacing of the scattered items (draw the polygon on the map).
        fill_panel = QWidget()
        fl = QHBoxLayout(fill_panel)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(4)
        fl.addWidget(_small_label("Spacing:"))
        self._fill_spacing = QDoubleSpinBox()
        self._fill_spacing.setRange(0.3, 20.0)
        self._fill_spacing.setSingleStep(0.5)
        self._fill_spacing.setValue(1.5)
        self._fill_spacing.setSuffix(" m")
        self._fill_spacing.setFixedWidth(85)
        self._fill_spacing.setToolTip(
            "Centre-to-centre spacing of the scattered items. For a community "
            "(or community mix) this is the gap between whole community units."
        )
        self._fill_spacing.setStyleSheet(_QTY_SPIN_STYLE)
        fl.addWidget(self._fill_spacing)
        fl.addWidget(_small_label("Click Place, then draw the area."))
        fl.addStretch()
        self._stack.addWidget(fill_panel)

        # ── Overlap / gap slider (applies to all multi modes) ─────────
        ov = QHBoxLayout()
        ov.setSpacing(4)
        ov.addWidget(_small_label("Overlap:"))
        self._overlap_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlap_slider.setRange(-100, 50)
        self._overlap_slider.setValue(0)
        self._overlap_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._overlap_slider.setTickInterval(25)
        self._overlap_slider.setToolTip(
            "Spacing relative to the reference width (see toggle below).\n"
            "  −100% = double spacing (centres 2× reference apart)\n"
            "     0% = at nominal spacing\n"
            "   +50% = half spacing (dense overlap)\n"
            "Effective spacing = reference × (1 − overlap)."
        )
        ov.addWidget(self._overlap_slider, 1)
        self._overlap_label = QLabel("0%")
        self._overlap_label.setStyleSheet(
            "color: #a5d6a7; font-size: 11px; min-width: 40px;"
        )
        ov.addWidget(self._overlap_label)
        self._overlap_slider.valueChanged.connect(
            lambda v: self._overlap_label.setText(f"{v:+d}%" if v else "0%")
        )
        outer.addLayout(ov)

        # Reference-width toggle: planting spacing (default) vs mature canopy.
        # Plant Communities tab hides this — a community isn't a single canopy.
        self._canopy_base_checkbox = QCheckBox("Base on mature canopy")
        self._canopy_base_checkbox.setToolTip(
            "When off, overlap is measured against planting spacing.\n"
            "When on, overlap is measured against the mature canopy width — "
            "useful when you care about leaf-area competition more than "
            "nursery spacing recommendations."
        )
        self._canopy_base_checkbox.setStyleSheet(
            "color: #a5d6a7; font-size: 11px;"
        )
        outer.addWidget(self._canopy_base_checkbox)
        if not show_canopy_base:
            self._canopy_base_checkbox.hide()

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

    def current_pattern(self) -> dict:
        """Build the pattern dict ``{kind, params}``. Tab-specific keys
        like ``polyculture`` or ``community_mix`` are the caller's job
        to inject into ``params`` after the fact."""
        kind = self._kind
        overlap = self._overlap_slider.value() / 100.0
        use_canopy = self._canopy_base_checkbox.isChecked()
        if kind == "row":
            params = {
                "count": self._row_count.value() or None,
                "overlap": overlap,
                "use_canopy": use_canopy,
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
            params = {"spacing": float(self._fill_spacing.value())}
        else:
            return {"kind": "single", "params": {}}
        return {"kind": kind, "params": params}

    def fill_spacing(self) -> float:
        """Convenience accessor for the Fill Area spacing (metres)."""
        return float(self._fill_spacing.value())

    # ── Internals ─────────────────────────────────────────────────────

    def _on_kind_changed(self, btn):
        kind = btn.property("pattern_kind") or "single"
        self._kind = kind
        idx = {"single": 0, "row": 1, "grid": 2, "circle": 3, "fill": 4}.get(kind, 0)
        self._stack.setCurrentIndex(idx)
        self.patternKindChanged.emit(kind)
