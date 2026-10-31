"""
shade_features.py — Site › Sun & Shade › Existing features (V3.37).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The owner: the existing features "should be accessible within Sun & Shade. As
a collapsible (initially collapsed) drop down that allows you to pick the
features that the sun path shade will then reflect."

What casts the shade was entered one tab away, on Site › Features, and could
only be deleted, never set aside: seeing the shade without a neighbour's tree
meant removing the tree. This section lists every tree and building already on
the site, ticked while it casts shade. Unticking one keeps it in the design
(drawn, planted around, in the 3D preview) and takes its shade out of the
shade map, the planting zones and Plan My Yard alike, through the one rule in
``shade.casters_from_project`` (``SHADE_OFF``). Scan this area is here too, so
the casters can be brought in where the shade is looked at.

The rows and their words are Qt-free (``sun_shade.caster_rows``); this is the
widget, and ``shade_features_flow`` connects it to the design.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractScrollArea, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from src import sun_shade
from src.ui_style import BTN_SECONDARY

TITLE = "Existing features"
#: The list grows to this many rows, then scrolls inside the page.
_ROWS_SHOWN = 8


class ShadeFeatures(QWidget):
    """A disclosure button, closed when the app opens, and under it the list."""

    #: The person ticked or unticked rows: (feature indexes, casts shade).
    shade_switched = pyqtSignal(list, bool)
    #: The ticks changed some other way (undo, redo, a file opened), so a
    #: shade map on screen is out of date.
    casting_changed = pyqtSignal()
    frame_requested = pyqtSignal(float, float)
    scan_requested = pyqtSignal()
    by_hand_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # The Details ▸ pattern of Site Info: a flat button that takes focus.
        self.toggle = QPushButton()
        self.toggle.setCheckable(True)
        self.toggle.setFlat(True)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setAccessibleName(TITLE)
        self.toggle.setToolTip("Pick which trees and buildings cast the shade.")
        self.toggle.setStyleSheet(
            "QPushButton { color: #a5d6a7; border: none; text-align: left; "
            "padding: 2px 4px; font-size: 13px; }"
            "QPushButton:focus { border: 1px solid #ffe082; }")
        self.toggle.toggled.connect(self._open)
        lay.addWidget(self.toggle)

        self.body = QWidget()
        self.body.setAccessibleName(TITLE)
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)
        hint = QLabel("Ticked ones cast shade. Untick one to see the shade "
                      "without it: it stays in the design.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #90a4ae; font-size: 12px;")
        body.addWidget(hint)
        self.empty = QLabel("None yet. Scan this area finds the buildings and "
                            "trees around the yard.")
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet("color: #ffcc80; font-size: 12px;")
        body.addWidget(self.empty)

        from src.on_this_design_panel import _WrapToList
        from src.plant_list_view import _RESULTS_LIST_STYLE
        self.list = QListWidget()
        self.list.setAccessibleName("Existing features: ticked ones cast shade")
        self.list.setStyleSheet(_RESULTS_LIST_STYLE)
        self.list.setWordWrap(True)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setItemDelegate(_WrapToList(self.list))
        # As tall as its rows, up to _ROWS_SHOWN, then it scrolls.
        self.list.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.list.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Maximum)
        self.list.setMaximumHeight(_ROWS_SHOWN * 28 + 6)
        self.list.setToolTip("Space ticks or unticks a row; a row picked "
                             "shows where it is on the map.")
        self.list.itemChanged.connect(self._ticked)
        self.list.currentItemChanged.connect(self._frame)
        body.addWidget(self.list)

        ticks = QHBoxLayout()
        self.all_on = QPushButton("Tick all")
        self.all_off = QPushButton("Untick all")
        for button, on in ((self.all_on, True), (self.all_off, False)):
            button.setStyleSheet(BTN_SECONDARY)
            button.clicked.connect(lambda _c=False, on=on: self._switch_all(on))
            ticks.addWidget(button)
        body.addLayout(ticks)

        self.scan = QPushButton("Scan this area")
        self.scan.setStyleSheet(BTN_SECONDARY)
        self.scan.setToolTip(
            "Buildings from OpenStreetMap and trees from the canopy-height map, "
            "as on Site › Features, then a list to untick what is not there.")
        self.scan.clicked.connect(self.scan_requested.emit)
        body.addWidget(self.scan)
        # Drawing and marking by hand stay on Site › Features, behind View ›
        # Advanced tools as they are there (src/advanced_tools.py).
        self.by_hand_box = QWidget()
        bh = QHBoxLayout(self.by_hand_box)
        bh.setContentsMargins(0, 0, 0, 0)
        by_hand = QPushButton("Draw or mark one by hand…")
        by_hand.setStyleSheet(BTN_SECONDARY)
        by_hand.setToolTip("Opens Site › Features, where a tree or building "
                           "the scan missed can be drawn or marked.")
        by_hand.clicked.connect(self.by_hand_requested.emit)
        bh.addWidget(by_hand)
        body.addWidget(self.by_hand_box)

        # What Site › Features' status line says (a scan's progress, its
        # result, why OpenStreetMap did not answer), said here too.
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #ffcc80; font-size: 12px;")
        self.status.setVisible(False)            # until there is something
        body.addWidget(self.status)

        self.body.setVisible(False)
        lay.addWidget(self.body)
        self.refresh(None)

    # ── What it shows ────────────────────────────────────────────────────────

    def refresh(self, project, site_config=None) -> None:
        """Show ``project``'s existing features. Rebuilds the list only when
        its rows changed, so a tick, an undo or a plant dragged elsewhere
        leaves the keyboard where it was."""
        rows = sun_shade.caster_rows(project, site_config)
        old = self._rows
        key = [(r["index"], r["text"]) for r in rows]
        same = key == [(r["index"], r["text"]) for r in old]
        moved = same and any(a["on"] != b["on"] for a, b in zip(rows, old))
        self._rows = rows
        blocked = self.list.blockSignals(True)
        if same:
            for i, row in enumerate(rows):
                self.list.item(i).setCheckState(_state(row["on"]))
        else:
            # The row picked stays picked if its feature is still there.
            was = self.list.currentRow()
            was = (old[was]["index"], old[was]["text"]) if 0 <= was < len(
                old) else None
            current = key.index(was) if was in key else -1
            self.list.clear()
            for i, row in enumerate(rows):
                item = QListWidgetItem(row["text"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(_state(row["on"]))
                item.setData(Qt.ItemDataRole.UserRole, i)
                if row["where"]:
                    item.setToolTip(
                        "In the middle of the yard"
                        if row["where"] == "in the middle"
                        else f"{row['where']} of the middle of the yard")
                self.list.addItem(item)
            if 0 <= current < len(rows):
                self.list.setCurrentRow(current)
        self.list.blockSignals(blocked)
        self.list.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        self.all_on.setEnabled(any(not r["on"] for r in rows))
        self.all_off.setEnabled(any(r["on"] for r in rows))
        self._label()
        if moved:
            self.casting_changed.emit()

    def set_status(self, text: str) -> None:
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _label(self) -> None:
        n = len(self._rows)
        on = sum(1 for r in self._rows if r["on"])
        count = ("" if not n else f" ({n})" if on == n
                 else f" ({on} of {n} cast shade)")
        arrow = "▾" if self.toggle.isChecked() else "▸"
        self.toggle.setText(f"{TITLE}{count} {arrow}")

    def _open(self, on: bool) -> None:
        self.body.setVisible(bool(on))
        self._label()

    # ── What the person does ─────────────────────────────────────────────────

    def _ticked(self, item) -> None:
        row = self._rows[item.data(Qt.ItemDataRole.UserRole)]
        on = item.checkState() == Qt.CheckState.Checked
        if on == row["on"]:
            return
        # Held here at once, so the refresh the change brings finds nothing
        # moved and does not ask for the shade twice.
        row["on"] = on
        self._label()
        self.shade_switched.emit([row["index"]], on)

    def _switch_all(self, on: bool) -> None:
        rows = [r for r in self._rows if r["on"] != on]
        if not rows:
            return
        for row in rows:
            row["on"] = on
        blocked = self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(_state(on))
        self.list.blockSignals(blocked)
        self._label()
        self.shade_switched.emit([r["index"] for r in rows], on)

    def _frame(self, item, _previous=None) -> None:
        if item is None:
            return
        centre = self._rows[item.data(Qt.ItemDataRole.UserRole)]["centre"]
        if centre:
            self.frame_requested.emit(*centre)


def _state(on: bool):
    return Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
