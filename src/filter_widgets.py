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

from PyQt6.QtWidgets import (
    QApplication, QComboBox, QSizePolicy, QStyle, QStyledItemDelegate,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt, QEvent, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel


# A second line under an item's label — the place it is, under what it is.
# Ecoregion names carry their geography ("Moist Mixed Grassland" / "Regina,
# Saskatoon"), and packing both into one string is what made the list unreadable:
# every entry elided mid-word ("Moist Mixed Gras...ina (Saskatoon)") so neither
# half survived. Two lines let the name be whole and the place stay secondary.
#: Extra item roles for the three-level tree (V2.67).
DEPTH_ROLE = Qt.ItemDataRole.UserRole + 90
PARENT_ROLE = Qt.ItemDataRole.UserRole + 91
EXPANDED_ROLE = Qt.ItemDataRole.UserRole + 92
LABEL_ROLE = Qt.ItemDataRole.UserRole + 93
#: Pixels from a parent row's left edge that open/close it rather than check it.
_DISCLOSURE_WIDTH = 18

SUBTITLE_ROLE = Qt.ItemDataRole.UserRole + 1


class _TwoLineDelegate(QStyledItemDelegate):
    """Item painter for entries that carry a ``SUBTITLE_ROLE``.

    Items without one paint exactly as before, so a combo can mix both.
    """

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.data(SUBTITLE_ROLE):
            size.setHeight(option.fontMetrics.height() * 2 + 8)
        return size

    def paint(self, painter, option, index):
        subtitle = index.data(SUBTITLE_ROLE)
        if not subtitle:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        title = opt.text
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()

        # Row background first, so both lines sit inside one highlight.
        opt.text = ""
        style.drawPrimitive(
            QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, widget)

        # The tick, drawn here rather than left to the style. Two style paths
        # let us down: CE_ItemViewItem lays the row out from the text it is
        # given, so blanking the text to place the lines by hand took the
        # indicator's column with it; and PE_IndicatorItemViewItemCheck under
        # this view's stylesheet paints nothing the eye can find on a dark
        # ground. An empty box and a tick, in the palette the rest of the panel
        # uses — the same two states the list showed before.
        # NB: index.data(CheckStateRole) hands back a plain int (2), not the
        # Qt.CheckState enum, so comparing against the enum is quietly always
        # False — which is exactly how the tick went missing the first time.
        checked = (index.data(Qt.ItemDataRole.CheckStateRole)
                   == Qt.CheckState.Checked.value)
        box = 12
        check_rect = QRect(option.rect.left() + 5,
                           option.rect.top() + (option.rect.height() - box) // 2,
                           box, box)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setPen(QColor("#66bb6a" if checked else "#4a6a4a"))
        painter.setBrush(QColor("#2e5a2e") if checked else Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(check_rect, 2, 2)
        if checked:
            tick = QFont(option.font)
            tick.setBold(True)
            painter.setFont(tick)
            painter.setPen(QColor("#c8e6c9"))
            painter.drawText(check_rect,
                             int(Qt.AlignmentFlag.AlignCenter), "✓")
        painter.restore()

        painter.save()
        fm = option.fontMetrics
        line_h = fm.height()
        text_x = check_rect.right() + 7
        width = option.rect.right() - text_x - 4
        top = option.rect.top() + 3
        painter.setPen(option.palette.text().color())
        painter.drawText(
            QRect(text_x, top, width, line_h),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            fm.elidedText(title, Qt.TextElideMode.ElideRight, width))

        small = QFont(option.font)
        small.setPointSizeF(max(6.5, option.font.pointSizeF() - 1.5))
        painter.setFont(small)
        painter.setPen(QColor("#78909c"))
        sub_fm = painter.fontMetrics()
        # The title carries its indentation in the string, so it lines up on
        # its own; the subtitle is stored bare — deliberately, so the data is
        # the place and not the layout — and is indented here instead. Without
        # this a nested row's second line sits under the checkbox rather than
        # under its own name, and the indentation stops reading as a hierarchy.
        indent = int(index.data(DEPTH_ROLE) or 0) * option.fontMetrics.horizontalAdvance("      ")
        painter.drawText(
            QRect(text_x + indent, top + line_h - 1, width - indent,
                  sub_fm.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            sub_fm.elidedText(subtitle, Qt.TextElideMode.ElideRight,
                              max(20, width - indent)))
        painter.restore()


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

    def add_check_item(self, label: str, key: str, icon=None, subtitle: str = "",
                       depth: int = 0, parent_key: str = ""):
        """Add one row. ``depth`` indents it and files it under ``parent_key``.

        Rows deeper than the top level start **collapsed**, which is the whole
        reason this exists: twenty-four ecoregions in one flat list is the menu
        the author asked not to have. Six ecozones open to their ecoregions,
        which open to Alberta's subregions.
        """
        item = QStandardItem(label)
        item.setData(key, Qt.ItemDataRole.UserRole)
        item.setData(depth, DEPTH_ROLE)
        item.setData(parent_key, PARENT_ROLE)
        item.setData(label, LABEL_ROLE)
        if depth:
            self._tree = True
        if subtitle:
            item.setData(subtitle, SUBTITLE_ROLE)
            self._ensure_two_line_view()
        if icon is not None:
            item.setIcon(icon)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        # Set the check state before the item joins the model so the initial
        # state doesn't spuriously fire itemChanged during construction.
        item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        self.model().appendRow(item)
        self._redraw_label(item)
        if parent_key:
            # A parent is added before its children, so when *it* was drawn it
            # had none and got no disclosure marker. Redraw it now that it does.
            for row in self._rows():
                if row.data(Qt.ItemDataRole.UserRole) == parent_key:
                    self._redraw_label(row)
                    break
        if depth:
            # Collapsed until its parent is opened. Hiding lives on the view,
            # not the model, so `checked_keys` and `set_checked_keys` keep
            # seeing every row whether it is on screen or not — a filter the
            # user set and then collapsed is still set.
            self.view().setRowHidden(item.row(), True)
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
                point = self._event_point(event)
                if self._has_children(it) and point.x() < _DISCLOSURE_WIDTH:
                    # The left edge of a parent row opens and closes it; the
                    # rest of the row still checks. Two jobs, one row, and the
                    # arrow is the affordance that says so.
                    self._set_expanded(it, not self._is_expanded(it))
                else:
                    it.setCheckState(
                        Qt.CheckState.Unchecked
                        if it.checkState() == Qt.CheckState.Checked
                        else Qt.CheckState.Checked)
            return True  # keep the popup open for further toggles
        return super().eventFilter(obj, event)

    # ── tree behaviour ──────────────────────────────────────────────────
    def _rows(self):
        model = self.model()
        return [model.item(i) for i in range(model.rowCount())]

    def _children_of(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        return [row for row in self._rows()
                if row.data(PARENT_ROLE) == key] if key else []

    def _has_children(self, item) -> bool:
        return bool(self._children_of(item))

    def _is_expanded(self, item) -> bool:
        return bool(item.data(EXPANDED_ROLE))

    def _redraw_label(self, item):
        """Compose the visible text: indent, disclosure marker, label.

        The marker is part of the string rather than painted, so it survives
        the two-line delegate, the elide mode and any future restyling without
        a second code path. A row with no children gets spaces where the
        triangle would be, so labels at one depth still line up.
        """
        label = item.data(LABEL_ROLE) or item.text()
        depth = int(item.data(DEPTH_ROLE) or 0)
        if self._has_children(item):
            marker = "\u25be " if self._is_expanded(item) else "\u25b8 "
        else:
            marker = "   " if getattr(self, "_tree", False) else ""
        item.setText(("      " * depth) + marker + label)

    def _set_expanded(self, item, expanded: bool):
        """Open or close one row, hiding descendants when it closes.

        Closing hides the whole subtree rather than one level, so re-opening a
        branch does not surface grandchildren the user had collapsed.
        """
        item.setData(bool(expanded), EXPANDED_ROLE)
        self._redraw_label(item)
        for child in self._children_of(item):
            self.view().setRowHidden(child.row(), not expanded)
            if not expanded:
                self._set_expanded(child, False)
            elif self._is_expanded(child):
                self._set_expanded(child, True)
        self.view().viewport().update()

    def expand_all(self):
        for row in self._rows():
            if self._has_children(row):
                self._set_expanded(row, True)

    def collapse_all(self):
        for row in self._rows():
            if row.data(DEPTH_ROLE):
                self.view().setRowHidden(row.row(), True)
            row.setData(False, EXPANDED_ROLE)
        self.view().viewport().update()

    def _ensure_two_line_view(self):
        """Install the two-line painter, and widen the popup past the combo.

        The popup inherits the combo's width by default, and these combos share
        a row 50/50 — which is why the full names never fit. The list is free to
        be wider than the control that opens it.
        """
        if getattr(self, "_two_line", False):
            return
        self._two_line = True
        self.setItemDelegate(_TwoLineDelegate(self))
        view = self.view()
        view.setMinimumWidth(280)
        view.setTextElideMode(Qt.TextElideMode.ElideRight)

    def _refresh_text(self):
        labels = [(self.model().item(i).data(LABEL_ROLE)
                   or self.model().item(i).text()).strip()
                  for i in range(self.model().rowCount())
                  if self.model().item(i).checkState() == Qt.CheckState.Checked]
        # Past two, a joined list is guaranteed to elide mid-word and say less
        # than a count would — "3 selected" is at least true and whole.
        if len(labels) > 2:
            self.lineEdit().setText(f"{len(labels)} selected")
        else:
            self.lineEdit().setText(", ".join(labels))
        self.lineEdit().setToolTip(", ".join(labels))

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


def build_ecoregion_tree(combo):
    """Fill the ecoregion combo with ecozone / ecoregion / subregion rows.

    Moisture niches go in last and flat: `riparian` and `wet_meadow` are
    conditions rather than places, they sit inside every ecozone, and
    nesting them anywhere would say something false about where they are.
    """
    from src.ecoregion import MOISTURE_NICHES, ecoregion_display
    from src.ecoregion_tree import tree

    for zone_key, zone_name, _lvl, regions in tree():
        combo.add_check_item(zone_name, zone_key,
                             subtitle=f"{len(regions)} ecoregions")
        for region_key, region_name, _l2, subs in regions:
            _n, where = ecoregion_display(region_key)
            combo.add_check_item(region_name, region_key, subtitle=where,
                                 depth=1, parent_key=zone_key)
            for sub_key, sub_name, _l3, _kids in subs:
                combo.add_check_item(sub_name, sub_key, depth=2,
                                     parent_key=region_key)
    for key, name, where in MOISTURE_NICHES:
        combo.add_check_item(name, key, subtitle=where)
