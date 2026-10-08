"""
filter_area.py — the plant picker's filters, the everyday ones first (V3.14).

The owner, of the Plant Library's filters: "This is also so so busy and needs
work." Unfolded in the side panel the picker showed every filter at once: nine
dropdowns in five rows and ten toggles in three, nineteen controls above a list
that then began halfway down the column.

Now the four dropdowns and four toggles a person choosing plants for a yard
reaches for first are shown, and the other ten wait behind **More filters**,
which says how many of them are on. Nothing is further than one click, a filter
that is on is still a removable chip on the line above either tier, and the
Plant Directory, a window with room, opens with both tiers showing.

:data:`EVERYDAY` is the choice, in one place. It is a judgment, made for the
owner's aim of useful, available plants in real yards: what the plant is, the
light and water it needs, where it can be bought, whether it belongs here,
whether it can be found, and whether it is safe around a dog. Moving a key in
or out of it is the whole change.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QToolButton, QVBoxLayout, QWidget

from src import plant_filters as pf
from src.filter_status import SMALL_BUTTON, QualityChips, wrapped
from src.filter_widgets import (
    COMBO_STYLE, CheckableComboBox, build_ecoregion_tree,
)
from src.plant_list_view import _colour_icon, _type_icon

#: Shown before "More filters", by facet or quality key (``plant_filters``).
EVERYDAY = ("type", "sun", "water", "availability",
            "native_only", "edmonton_native", "common_only", "pet_safe_only")


class FilterArea(QWidget):
    """Every facet as a dropdown and every quality as a toggle, in two tiers.
    ``combos`` and ``chips`` hold all of them by key, whichever tier they are
    in; ``soil`` is the site's soil pH toggle, among the everyday ones."""

    #: A facet's key, when its ticks change.
    facet_changed = pyqtSignal(str)
    #: A quality's key, when its toggle is flipped.
    quality_toggled = pyqtSignal(str)

    def __init__(self, criteria: dict, *, wide: bool = False, parent=None):
        super().__init__(parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 2)
        col.setSpacing(4)
        per_row = 5 if wide else 2
        self.combos: dict = {}
        self._hidden_on = 0
        col.addLayout(self._grid([f for f in pf.FACETS if f.key in EVERYDAY],
                                 criteria, per_row))
        self.everyday_chips = QualityChips(
            [q for q in pf.QUALITIES if q.key in EVERYDAY], criteria)
        col.addWidget(self.everyday_chips)

        self.more_button = QToolButton()
        self.more_button.setCheckable(True)
        self.more_button.setStyleSheet(SMALL_BUTTON)
        self.more_button.setAccessibleName("More filters")
        tip = ("Role, the region you are restoring toward, bloom and fruit "
               "months, flower colour and six more toggles.")
        self.more_button.setToolTip(wrapped(tip))
        self.more_button.setAccessibleDescription(tip)
        col.addWidget(self.more_button)

        self.more = QWidget()
        self.more.setAccessibleName("More filters")
        more_col = QVBoxLayout(self.more)
        more_col.setContentsMargins(0, 0, 0, 0)
        more_col.setSpacing(4)
        more_col.addLayout(self._grid(
            [f for f in pf.FACETS if f.key not in EVERYDAY], criteria, per_row))
        self.more_chips = QualityChips(
            [q for q in pf.QUALITIES if q.key not in EVERYDAY], criteria,
            soil=False)
        more_col.addWidget(self.more_chips)
        col.addWidget(self.more)

        self.chips = {**self.everyday_chips.buttons, **self.more_chips.buttons}
        self.soil = self.everyday_chips.soil
        for chips in (self.everyday_chips, self.more_chips):
            chips.toggled.connect(self.quality_toggled)
        self.more_button.toggled.connect(self.set_more_open)
        self.set_more_open(wide)
        self.show_hidden_on(criteria)

    def _grid(self, facets, criteria: dict, per_row: int) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        for i, f in enumerate(facets):
            combo = CheckableComboBox(placeholder=f.placeholder,
                                      rule=pf.rule(f))
            combo.set_face(lambda keys, f=f: pf.face(f, keys))
            if f.values is None:
                build_ecoregion_tree(combo)
            else:
                icon_for = (_type_icon if f.key == "type" else
                            _colour_icon if f.key == "colour" else None)
                for key, label in f.values.items():
                    combo.add_check_item(
                        label, key, icon=icon_for(key) if icon_for else None)
            combo.setStyleSheet(COMBO_STYLE)
            combo.setToolTip(wrapped(f.tip))
            combo.setAccessibleName(f"{f.label} filter")
            combo.setAccessibleDescription(f.tip)
            combo.lineEdit().setAccessibleName(f"{f.label} filter")
            combo.set_checked_keys([str(v) for v in (criteria.get(f.key) or [])])
            combo.selectionChanged.connect(
                lambda k=f.key: self.facet_changed.emit(k))
            grid.addWidget(combo, i // per_row, i % per_row)
            self.combos[f.key] = combo
        return grid

    def describe(self, key: str, tip: str) -> None:
        """What a toggle keeps, whichever tier it is in."""
        for chips in (self.everyday_chips, self.more_chips):
            chips.describe(key, tip)

    def set_more_open(self, on: bool) -> None:
        self.more.setVisible(bool(on))
        self.more_button.blockSignals(True)
        self.more_button.setChecked(bool(on))
        self.more_button.blockSignals(False)
        self._label()

    def more_open(self) -> bool:
        return self.more.isVisibleTo(self)

    def show_hidden_on(self, criteria: dict) -> None:
        """Count the filters past "More filters" that are on, for its label: a
        filter the reader cannot see is never silent (the chips say it too)."""
        self._hidden_on = sum(1 for key, _w in pf.filters_on(criteria)
                              if key != "query" and key not in EVERYDAY)
        self._label()

    def _label(self) -> None:
        if self.more_open():
            self.more_button.setText("Fewer filters ▴")
        elif self._hidden_on:
            self.more_button.setText(f"More filters ▸  {self._hidden_on} on")
        else:
            self.more_button.setText("More filters ▸")
