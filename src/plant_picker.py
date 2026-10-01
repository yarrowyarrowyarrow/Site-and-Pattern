"""
plant_picker.py — search, filters, order and the plant list, as one widget
(F192, V3.00).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Until V3.00 three screens picked plants and each was partial: Browse could
place but had no keystone, specialist, pet-safe or easy-to-find filter; the
Plant Directory had those and no fruit month, ecoregion or perennial filter;
the community builder had a checkbox, four single-choice dropdowns and a list
of plain strings ("Boreal Yarrow  (herb)"), filtered in Python. All three are
this widget now, over one vocabulary (``src/plant_filters.py``) and one list
(``src/plant_list_view.py``).

Top to bottom: a search box; a line that says which filters are on, with a
button that unfolds them and one that clears them; the nine facets and nine
qualities; the count and the order; the list. **Narrow pickers start folded.**
Eighteen controls do not fit above a list in a 437 px column that already had
fourteen, and the folded line is also where a filter the app set (a dropped
pin ticks "Restoring toward") stops being silent.

The order offers "Recorded near this site" only where there is a site, and it
ranks, never filters (``plant_filters.order_plants``).
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit,
    QListView, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from src import plant_filters as pf
from src.filter_widgets import (
    COMBO_STYLE, CheckableComboBox, build_ecoregion_tree,
)
from src.plant_list_view import (
    _PLANT_OBJ_ROLE, _RESULTS_LIST_STYLE, PlantListModel, PlantRowDelegate,
    _colour_icon, _type_icon,
)

_CHIP_STYLE = (
    "QPushButton { background: #1e2e1e; color: #a8b8b0; "
    "border: 1px solid #2e4a2e; border-radius: 3px; padding: 3px 8px; "
    "font-size: 12px; min-height: 18px; }"
    "QPushButton:checked { background: #2e5a2e; color: #e8f5e9; "
    "border-color: #66bb6a; }"
    "QPushButton:hover { border-color: #4a7a4a; }"
    "QPushButton:focus { border: 2px solid #ffe082; }"
)
_DIM = "color: #a8b8b0; font-size: 12px;"
_SEARCH = ("QLineEdit { background: #16241a; border: 1px solid #2e4a2e; "
           "border-radius: 4px; padding: 5px 8px; color: #c8e6c9; "
           "font-size: 13px; }"
           "QLineEdit:focus { border: 2px solid #ffe082; }")
_SMALL_BTN = ("QToolButton, QPushButton { background: transparent; "
              "color: #c8e6c9; border: 1px solid #2e4a2e; border-radius: 3px; "
              "padding: 2px 8px; font-size: 12px; min-height: 20px; }"
              "QToolButton:checked { border-color: #66bb6a; }"
              "QToolButton:hover, QPushButton:hover { border-color: #4a7a4a; }"
              "QToolButton:focus, QPushButton:focus { border: 2px solid #ffe082; }")


class PlantPicker(QWidget):
    """One plant picker. ``wide`` lays the filters out for a window rather than
    a side panel and shows them unfolded; ``draggable`` lets rows be dragged
    (onto the Browse tab's mix); ``list_apart`` leaves :attr:`view` for the
    owner to place (the Directory puts it in a splitter beside the page, under
    filters that span the window)."""

    #: The result set changed (a search ran, or the order did).
    results_changed = pyqtSignal()
    #: The filters or the search text changed; carries :meth:`criteria`.
    criteria_changed = pyqtSignal(dict)

    def __init__(self, parent=None, *, wide: bool = False,
                 filters_open: Optional[bool] = None,
                 criteria: Optional[dict] = None, order: str = "name",
                 draggable: bool = False, list_apart: bool = False,
                 search_fn: Optional[Callable] = None):
        super().__init__(parent)
        self._wide = wide
        self._search_fn = search_fn
        self._criteria: dict = dict(criteria or {})
        self._extra: dict = {}
        self._rows: list = []
        # "suits" needs a site; set_site makes it the order once there is one.
        self._order = order if order != "suits" else "name"
        self._user_ordered = False
        self._site = None
        self._zone = None
        self._hint: Optional[Callable] = None
        self._animals: Optional[dict] = None

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(
            "Search plants by name or role…")
        self.search_box.setAccessibleName("Search plants")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setStyleSheet(_SEARCH)
        self.search_box.setText(self._criteria.get("query") or "")
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._on_search_text)
        self.search_box.textChanged.connect(lambda _t: self._search_timer.start())
        col.addWidget(self.search_box)

        self._build_filter_line(col)
        self._build_filters(col)
        self.set_filters_open(wide if filters_open is None else filters_open)

        count_row = QHBoxLayout()
        count_row.setSpacing(6)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(_DIM)
        count_row.addWidget(self.count_label, 1)
        order_label = QLabel("Order")
        order_label.setStyleSheet(_DIM)
        count_row.addWidget(order_label)
        self.order_combo = QComboBox()
        self.order_combo.setAccessibleName("Order plants by")
        order_label.setBuddy(self.order_combo)
        for key, label, tip in pf.ORDERS:
            self.order_combo.addItem(label, key)
            self.order_combo.setItemData(self.order_combo.count() - 1, tip,
                                         Qt.ItemDataRole.ToolTipRole)
        self.order_combo.setStyleSheet(COMBO_STYLE)
        self._sync_order_combo()
        self.order_combo.activated.connect(self._on_order_chosen)
        count_row.addWidget(self.order_combo)
        col.addLayout(count_row)

        self.model = PlantListModel(self)
        self.view = QListView()
        self.view.setAccessibleName("Plants")
        self.delegate = PlantRowDelegate(self.view)
        self.view.setModel(self.model)
        self.view.setItemDelegate(self.delegate)
        self.view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.view.setUniformItemSizes(False)
        self.view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setStyleSheet(_RESULTS_LIST_STYLE)
        if draggable:
            self.view.setDragEnabled(True)
            self.view.setDragDropMode(QListView.DragDropMode.DragOnly)
            self.view.setDefaultDropAction(Qt.DropAction.CopyAction)
        if not list_apart:
            col.addWidget(self.view, 1)

    # ── The filter line and the filters ─────────────────────────────────────

    def _build_filter_line(self, col):
        line = QHBoxLayout()
        line.setSpacing(6)
        self.filters_button = QToolButton()
        self.filters_button.setCheckable(True)
        self.filters_button.setAccessibleName("Filters")
        self.filters_button.setToolTip("Show or hide the filters")
        self.filters_button.setStyleSheet(_SMALL_BTN)
        self.filters_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filters_button.toggled.connect(self.set_filters_open)
        line.addWidget(self.filters_button, 0, Qt.AlignmentFlag.AlignTop)
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(_DIM)
        self.summary_label.setWordWrap(True)
        line.addWidget(self.summary_label, 1)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setAccessibleName("Clear all filters")
        self.clear_button.setToolTip("Untick every filter")
        self.clear_button.setStyleSheet(_SMALL_BTN)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear_filters)
        line.addWidget(self.clear_button, 0, Qt.AlignmentFlag.AlignTop)
        col.addLayout(line)

    def _build_filters(self, col):
        self.filter_area = QWidget()
        area = QVBoxLayout(self.filter_area)
        area.setContentsMargins(0, 0, 0, 2)
        area.setSpacing(4)
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        per_row = 5 if self._wide else 2
        self.combos: dict = {}
        for i, f in enumerate(pf.FACETS):
            combo = CheckableComboBox(placeholder=f.placeholder)
            if f.values is None:
                build_ecoregion_tree(combo)
            else:
                icon_for = (_type_icon if f.key == "type" else
                            _colour_icon if f.key == "colour" else None)
                for key, label in f.values.items():
                    combo.add_check_item(
                        label, key, icon=icon_for(key) if icon_for else None)
            combo.setStyleSheet(COMBO_STYLE)
            combo.setToolTip(f.tip)
            combo.setAccessibleName(f"{f.label} filter")
            combo.setAccessibleDescription(f.tip)
            combo.lineEdit().setAccessibleName(f"{f.label} filter")
            combo.set_checked_keys([str(v) for v in
                                    (self._criteria.get(f.key) or [])])
            combo.selectionChanged.connect(
                lambda k=f.key: self._on_facet(k))
            grid.addWidget(combo, i // per_row, i % per_row)
            self.combos[f.key] = combo
        area.addLayout(grid)

        chips = QWidget()
        flow = FlowLayout(chips, spacing=4)
        self.chips: dict = {}
        for q in pf.QUALITIES:
            btn = QPushButton(q.label)
            btn.setCheckable(True)
            btn.setChecked(bool(self._criteria.get(q.key)))
            btn.setToolTip(q.tip)
            btn.setAccessibleDescription(q.tip)
            btn.setStyleSheet(_CHIP_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.toggled.connect(lambda _on, k=q.key: self._on_quality(k))
            flow.addWidget(btn)
            self.chips[q.key] = btn
        area.addWidget(chips)
        col.addWidget(self.filter_area)

    def set_filters_open(self, on: bool):
        self.filter_area.setVisible(bool(on))
        self.filters_button.blockSignals(True)
        self.filters_button.setChecked(bool(on))
        self.filters_button.blockSignals(False)
        self.filters_button.setText("Filters ▾" if on else "Filters ▸")

    def filters_open(self) -> bool:
        return self.filter_area.isVisibleTo(self)

    def _refresh_summary(self):
        bits = pf.summary(self._criteria)
        self.summary_label.setText(" · ".join(bits) if bits else "None on")
        self.summary_label.setAccessibleName(
            "Filters on: " + ", ".join(bits) if bits else "No filters on")
        self.clear_button.setVisible(bool(bits))

    # ── Criteria ────────────────────────────────────────────────────────────

    def criteria(self) -> dict:
        return dict(self._criteria)

    def set_criteria(self, criteria: Optional[dict], *, refresh: bool = True):
        """Show exactly these filters. **Replaces** rather than merges: a
        window kept between uses would otherwise AND today's request onto
        whatever was left in it last time."""
        self._criteria = dict(criteria or {})
        self.search_box.blockSignals(True)
        self.search_box.setText(self._criteria.get("query") or "")
        self.search_box.blockSignals(False)
        for key, combo in self.combos.items():
            combo.set_checked_keys(
                [str(v) for v in (self._criteria.get(key) or [])])
        for key, btn in self.chips.items():
            btn.blockSignals(True)
            btn.setChecked(bool(self._criteria.get(key)))
            btn.blockSignals(False)
        if refresh:
            self.refresh()

    def set_facet(self, key: str, values) -> None:
        """Set one facet, leaving the others (a dropped pin ticking its
        region)."""
        values = [str(v) for v in (values or [])]
        if self.combos[key].checked_keys() == values:
            return
        self.combos[key].set_checked_keys(values)
        self._criteria[key] = values
        self.refresh()

    def clear_filters(self):
        query = self._criteria.get("query") or ""
        self.set_criteria({"query": query} if query else {})
        self.criteria_changed.emit(self.criteria())

    def _on_search_text(self):
        self.refresh()
        self.criteria_changed.emit(self.criteria())

    def _on_facet(self, key: str):
        self._criteria[key] = self.combos[key].checked_keys()
        self.refresh()
        self.criteria_changed.emit(self.criteria())

    def _on_quality(self, key: str):
        self._criteria[key] = self.chips[key].isChecked()
        self.refresh()
        self.criteria_changed.emit(self.criteria())

    def set_extra(self, **kwargs):
        """Search arguments the app sets rather than the reader: the site's
        soil pH. ``None`` removes one."""
        changed = False
        for key, value in kwargs.items():
            if value is None:
                changed |= self._extra.pop(key, None) is not None
            elif self._extra.get(key) != value:
                self._extra[key] = value
                changed = True
        if changed:
            self.refresh()

    # ── Order ───────────────────────────────────────────────────────────────

    def set_site(self, coords, zone=None):
        """Where the design is, so "Recorded near this site" can be offered.
        Until the reader picks an order themselves, a site makes it the
        order."""
        coords = tuple(coords) if coords else None
        if coords == self._site and zone == self._zone:
            return
        self._site, self._zone = coords, zone
        if not self._user_ordered or (self._order == "suits" and not coords):
            self._order = "suits" if coords else (
                "name" if self._order == "suits" else self._order)
        self._sync_order_combo()
        self._reorder()

    def set_hint(self, hint: Optional[Callable]):
        """Lift the rows ``hint(row)`` is true for to the top (the builder's
        "matches the layer you chose")."""
        self._hint = hint
        self._reorder()

    def order(self) -> str:
        return self._order

    def set_order(self, key: str):
        self._order = key
        self._user_ordered = True
        self._sync_order_combo()
        self._reorder()

    def _on_order_chosen(self, index: int):
        self.set_order(self.order_combo.itemData(index))

    def _sync_order_combo(self):
        model = self.order_combo.model()
        for i in range(self.order_combo.count()):
            if self.order_combo.itemData(i) == "suits":
                item = model.item(i)
                item.setEnabled(self._site is not None)
                if self._site is None:
                    item.setToolTip("Drop a pin on your site to rank plants "
                                    "by what has been recorded near it.")
        idx = self.order_combo.findData(self._order)
        self.order_combo.blockSignals(True)
        self.order_combo.setCurrentIndex(max(0, idx))
        self.order_combo.blockSignals(False)

    def _ordered(self, rows) -> list:
        if self._order == "wildlife" and self._animals is None:
            self._animals = pf.animals_per_plant()
        return pf.order_plants(rows, self._order, site=self._site,
                               zone=self._zone, wildlife_counts=self._animals,
                               hint=self._hint)

    def _reorder(self):
        if not self._rows:
            return
        current = (self.current_plant() or {}).get("id")
        self._rows = self._ordered(self._rows)
        self.model.set_plants(self._rows)
        if current:
            self.select_plant_id(current)
        self.results_changed.emit()

    # ── Searching ───────────────────────────────────────────────────────────

    def refresh(self):
        """Run the search now and show the result. Reads the search box, so a
        refresh straight after typing does not wait for the debounce."""
        self._search_timer.stop()
        self._criteria["query"] = self.search_box.text()
        self._refresh_summary()
        search_fn = self._search_fn
        if search_fn is None:
            from src.db.plants import search_plants as search_fn
        kwargs = pf.criteria_to_kwargs(self._criteria)
        kwargs.update(self._extra)
        try:
            rows = search_fn(**kwargs)
        except Exception as exc:                                # noqa: BLE001
            self.count_label.setText(f"Search failed: {exc}")
            return
        self._rows = self._ordered(rows)
        self.model.set_plants(self._rows)
        n = len(self._rows)
        self.count_label.setText(
            "No plants match" if not n else f"{n} plant{'s' if n != 1 else ''}")
        self.results_changed.emit()

    def rows(self) -> list:
        return list(self._rows)

    def current_plant(self) -> Optional[dict]:
        rows = self.view.selectionModel().selectedIndexes()
        return (rows[0].data(_PLANT_OBJ_ROLE) or None) if rows else None

    def select_plant_id(self, plant_id) -> bool:
        """Highlight ``plant_id`` if it is in the list; ``False`` if not."""
        for row, plant in enumerate(self._rows):
            if plant_id and plant.get("id") == plant_id:
                self.view.setCurrentIndex(self.model.index(row))
                return True
        return False


class FlowLayout(QLayout):
    """Children laid left to right, wrapping at the width there is: the chips
    fit a 1000 px window in two rows and a 240 px column in five, with nobody
    choosing a number per row."""

    def __init__(self, parent=None, spacing: int = 4):
        super().__init__(parent)
        self._items = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect, move=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _place(self, rect: QRect, *, move: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line > 0:
                x = rect.x()
                y += line + self._gap
                line = 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            line = max(line, hint.height())
        return y + line - rect.y()
