"""
filter_widgets.py — Shared search/filter widgets for the side-panel browsers.

The Plant Library grew a filter UX worth reusing (multi-select facet dropdowns,
compact toggle chips, one dark-green style family); this module is that UX
extracted so other panels — first the Plant Community Library (V2.13) — get the
same look and behaviour from one implementation instead of copies.

Contents:
  * ``CheckableComboBox`` — a QComboBox whose items carry checkboxes, for
    "pick several" facet filters (moved from plant_panel.py, V1.84).
  * ``COMBO_STYLE`` / ``TOGGLE_STYLE`` — the shared QSS for facet dropdowns and
    checkable filter chips (formerly locals in PlantPanel._build_ui).
  * ``make_multi_combo`` — factory that builds a styled multi-select facet
    dropdown from a key→label dict and wires its change signal.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QSizePolicy
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel


# ── Shared filter styling ─────────────────────────────────────────────────────
# One dark-green family: the combo shape blends with the toggle-chip palette so
# a row of facets reads as a single control strip.

COMBO_STYLE = (
    "QComboBox { background: #1e2e1e; color: #a5d6a7; border: 1px solid #2e4a2e; "
    "border-radius: 3px; padding: 2px 6px; font-size: 11px; }"
    "QComboBox:hover { border-color: #4a7a4a; }"
    "QComboBox::drop-down { border: none; width: 16px; }"
    "QComboBox QLineEdit { background: transparent; color: #a5d6a7; border: none; }"
    "QComboBox QAbstractItemView { background: #1e2e1e; color: #cfd8dc; "
    "border: 1px solid #2e4a2e; outline: none; "
    "selection-background-color: #2e5a2e; selection-color: #a5d6a7; }"
)

TOGGLE_STYLE = (
    "QPushButton { background: #1e2e1e; color: #78909c; border: 1px solid #2e4a2e; "
    "border-radius: 3px; padding: 2px 6px; font-size: 11px; }"
    "QPushButton:checked { background: #2e5a2e; color: #a5d6a7; border-color: #66bb6a; }"
    "QPushButton:hover { border-color: #4a7a4a; }"
)


# ── Multi-select dropdown (V1.84) ─────────────────────────────────────────────

class CheckableComboBox(QComboBox):
    """A QComboBox whose items carry checkboxes, for "pick several" filters.

    The line-edit area shows the checked labels (or a placeholder when none are
    checked); the popup stays open while toggling so the user can select more
    than one tier in a single trip. ``selectionChanged`` fires on every toggle.
    Used by the rarity/availability filter so the user can show, say, big-box +
    garden-centre + native-nursery plants at once.
    """

    selectionChanged = pyqtSignal()

    def __init__(self, placeholder: str = "Any", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self.setModel(QStandardItemModel(self))
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        le = self.lineEdit()
        le.setReadOnly(True)
        le.setPlaceholderText(placeholder)
        le.installEventFilter(self)
        self.view().viewport().installEventFilter(self)
        self.model().itemChanged.connect(self._on_item_changed)
        # An editable combo otherwise echoes the current item's text; keep the
        # display under our control so it shows the checked labels (or nothing).
        self.currentIndexChanged.connect(lambda _=0: self._refresh_text())
        # Stay flexible, not rigid: expand to share the row evenly and base the
        # size hint on a short minimum (not the longest item) so two combos in a
        # row split 50/50 at any window width — same layout on a 22" or 27"
        # monitor, windowed or full-screen (V1.86).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(6)

    def add_check_item(self, label: str, key: str, icon=None):
        item = QStandardItem(label)
        item.setData(key, Qt.ItemDataRole.UserRole)
        if icon is not None:
            item.setIcon(icon)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        # Set the check state before the item joins the model so the initial
        # state doesn't spuriously fire itemChanged during construction.
        item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        self.model().appendRow(item)
        # Keep no "current" item: an editable combo otherwise paints the current
        # row's icon (e.g. the first Type's colour swatch) in the line edit,
        # which reads as a stray dot next to the placeholder.
        self.setCurrentIndex(-1)
        self._refresh_text()

    def checked_keys(self) -> list[str]:
        out: list[str] = []
        for i in range(self.model().rowCount()):
            it = self.model().item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out

    def set_checked_keys(self, keys, *, emit: bool = False):
        """Check exactly the items whose key is in ``keys`` (others unchecked).

        Silent by default so callers can restore saved state without triggering
        a search; pass ``emit=True`` to fire ``selectionChanged`` once after.
        ``model().blockSignals`` is needed because ``setCheckState`` emits
        ``itemChanged`` (not covered by ``QComboBox.blockSignals``).
        """
        keyset = set(keys)
        self.model().blockSignals(True)
        for i in range(self.model().rowCount()):
            it = self.model().item(i)
            it.setCheckState(
                Qt.CheckState.Checked
                if it.data(Qt.ItemDataRole.UserRole) in keyset
                else Qt.CheckState.Unchecked)
        self.model().blockSignals(False)
        self._refresh_text()
        if emit:
            self.selectionChanged.emit()

    def _event_point(self, event):
        # QMouseEvent.pos() is deprecated in PyQt6; prefer position().
        if hasattr(event, "position"):
            return event.position().toPoint()
        return event.pos()

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        if (obj is self.lineEdit()
                and event.type() == QEvent.Type.MouseButtonRelease):
            self.showPopup()
            return True
        if (obj is self.view().viewport()
                and event.type() == QEvent.Type.MouseButtonRelease):
            idx = self.view().indexAt(self._event_point(event))
            if idx.isValid():
                it = self.model().itemFromIndex(idx)
                it.setCheckState(
                    Qt.CheckState.Unchecked
                    if it.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked)
            return True  # keep the popup open for further toggles
        return super().eventFilter(obj, event)

    def _refresh_text(self):
        labels = [self.model().item(i).text()
                  for i in range(self.model().rowCount())
                  if self.model().item(i).checkState() == Qt.CheckState.Checked]
        self.lineEdit().setText(", ".join(labels))

    def _on_item_changed(self, _item):
        self._refresh_text()
        self.selectionChanged.emit()


def make_multi_combo(placeholder: str, labels: dict, *, style: str = COMBO_STYLE,
                     icon_for=None, on_change=None) -> CheckableComboBox:
    """Build a styled multi-select facet dropdown.

    ``labels`` is a key→label dict; ``icon_for(key)`` (optional) returns a
    per-item QIcon — the Plant Library uses it to put the plant-type colour
    swatch beside each Type, doubling as the map legend. ``on_change`` (optional)
    is connected to ``selectionChanged``.
    """
    combo = CheckableComboBox(placeholder=placeholder)
    for key, lbl in labels.items():
        combo.add_check_item(lbl, key,
                             icon=icon_for(key) if icon_for else None)
    combo.setStyleSheet(style)
    if on_change is not None:
        combo.selectionChanged.connect(on_change)
    return combo
